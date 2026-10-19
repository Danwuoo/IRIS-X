"""Inference-only Qwen3 adapter for the MATH-002 TPU technical qualification.

No training, model-provided Python, API inference, or verifier execution. This
small implementation is deliberately gated by Transformers reference parity;
source inspection and CPU tests alone do not qualify its TPU conversion.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import time
from pathlib import Path


class PreflightError(RuntimeError):
    """A condition that prevents model execution or scientific qualification."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def tpu_preflight() -> dict:
    """Fail closed on CPU, mixed hardware, unsupported kind or device count."""
    # Set before importing JAX; an unavailable TPU must raise, not fall back.
    if "jax" in __import__("sys").modules:
        raise PreflightError("JAX imported before controlled TPU initialization")
    os.environ["JAX_PLATFORMS"] = "tpu"
    import jax
    import jaxlib

    devices = jax.devices()
    kinds = [device.device_kind for device in devices]
    result = {
        "backend": jax.default_backend(), "device_count": len(devices),
        "local_device_count": jax.local_device_count(), "device_kinds": kinds,
        "jax": jax.__version__, "jaxlib": jaxlib.__version__,
        "libtpu": importlib.metadata.version("libtpu"), "devices": [],
        "python": platform.python_version(), "system": platform.system(),
        "host_logical_cpus": os.cpu_count(), "tmp_free_bytes": shutil.disk_usage("/tmp").free,
    }
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        result["host_memory_bytes"] = {}
        for line in meminfo.read_text().splitlines():
            key, value = line.split(":", 1)
            if key in ("MemTotal", "MemAvailable"):
                result["host_memory_bytes"][key] = int(value.split()[0]) * 1024
    for device in devices:
        stats = device.memory_stats() or {}
        result["devices"].append({
            "id": device.id, "kind": device.device_kind, "platform": device.platform,
            "memory": {key: int(stats[key]) for key in
                       ("bytes_limit", "bytes_in_use", "peak_bytes_in_use") if key in stats},
        })
    if result["backend"] != "tpu" or len(devices) != 8 or jax.local_device_count() != 8:
        raise PreflightError("Expected one host with exactly 8 local TPU devices: " + json.dumps(result))
    # JAX/libtpu has reported v5e as 'TPU v5 lite' as well as 'TPU v5e'.
    if any(not re.fullmatch(r"TPU v5(?:e| lite)", kind, re.IGNORECASE) for kind in kinds):
        raise PreflightError("Unqualified device kind: " + json.dumps(result))
    if (jax.__version__, jaxlib.__version__, result["libtpu"]) != ("0.6.2", "0.6.2", "0.0.17"):
        raise PreflightError("Runtime differs from pinned stack: " + json.dumps(result))
    return result


def validate_config(config: dict) -> None:
    required = {"model_type": "qwen3", "hidden_act": "silu", "attention_bias": False,
                "use_sliding_window": False, "rope_scaling": None}
    for key, value in required.items():
        if config.get(key) != value:
            raise PreflightError(f"Unsupported architecture setting {key}")
    if config.get("architectures") != ["Qwen3ForCausalLM"]:
        raise PreflightError("Unsupported model architecture")
    for key in ("num_attention_heads", "num_key_value_heads", "intermediate_size", "vocab_size"):
        if config[key] % 8:
            raise PreflightError(f"Dimension not divisible by 8: {key}")
    if config["num_attention_heads"] % config["num_key_value_heads"]:
        raise PreflightError("Invalid grouped-query attention dimensions")


def sample_token(logits, rng, temperature: float, top_p: float) -> int:
    """Pinned CPU NumPy PCG64 nucleus sampling; one draw per completion token."""
    import numpy as np
    values = np.asarray(logits, dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise PreflightError("Invalid/nonfinite logits")
    if temperature == 0:
        return int(np.argmax(values))
    if not 0 < temperature <= 2 or not 0 < top_p <= 1:
        raise ValueError("Invalid sampling parameters")
    values = values / temperature
    order = np.argsort(-values, kind="stable")
    probability = np.exp(values[order] - values[order[0]])
    probability /= probability.sum()
    # Keep the first token which crosses the threshold (HF nucleus semantics).
    count = min(len(order), int(np.searchsorted(np.cumsum(probability), top_p)) + 1)
    probability = probability[:count]
    probability /= probability.sum()
    return int(order[int(rng.choice(count, p=probability))])


class JaxQwen3Adapter:
    """Single-sequence, 8-way tensor-parallel BF16 Qwen3 with static KV cache.

    A jitted scan traverses layers. Prefill uses the same single-token cached
    kernel as decode, trading throughput for a small auditable implementation.
    This is not a fused production inference runtime. Costs are measured.
    """

    def __init__(self, model_dir: str | Path, candidate: dict, *, context_length=8192):
        import jax
        import jax.numpy as jnp
        import numpy as np
        from jax.sharding import Mesh, NamedSharding, PartitionSpec as P
        from safetensors import safe_open
        from transformers import AutoTokenizer

        self.jax, self.jnp, self.np = jax, jnp, np
        self.path, self.candidate = Path(model_dir), candidate
        if jax.default_backend() != "tpu" or len(jax.devices()) != 8:
            raise PreflightError("Adapter requires qualified TPU; CPU model execution forbidden")
        self.config = json.loads((self.path / "config.json").read_text())
        validate_config(self.config)
        if not 16 <= context_length <= 8192:
            raise ValueError("Only context lengths 16..8192 are implemented")
        self.context_length = context_length
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.path), local_files_only=True,
                                                       trust_remote_code=False)
        actual_template_hash = hashlib.sha256(self.tokenizer.chat_template.encode()).hexdigest()
        if actual_template_hash != candidate["chat_template_sha256"]:
            raise PreflightError("Tokenizer chat template fingerprint mismatch")
        self.mesh = Mesh(np.array(jax.devices()), ("mp",))
        self.replicated = NamedSharding(self.mesh, P())
        self.cache_sharding = NamedSharding(self.mesh, P(None, None, "mp", None))
        index = json.loads((self.path / "model.safetensors.index.json").read_text())["weight_map"]

        def read(name):
            with safe_open(str(self.path / index[name]), framework="pt", device="cpu") as tensors:
                # NumPy lacks native BF16; preserve BF16 bit patterns through ml_dtypes.
                import ml_dtypes
                import torch
                tensor = tensors.get_tensor(name)
                if tensor.dtype != torch.bfloat16:
                    raise PreflightError("Checkpoint tensor is not BF16: " + name)
                return tensor.view(torch.uint16).numpy().view(ml_dtypes.bfloat16)

        def place(value, spec):
            return jax.device_put(value, NamedSharding(self.mesh, spec))

        cfg = self.config
        layers, heads, kv, dim = (cfg["num_hidden_layers"], cfg["num_attention_heads"],
                                 cfg["num_key_value_heads"], cfg["head_dim"])
        specifications = {
            "q": ("self_attn.q_proj.weight", lambda a: a.T.reshape(cfg["hidden_size"], heads, dim), P(None, None, "mp", None)),
            "k": ("self_attn.k_proj.weight", lambda a: a.T.reshape(cfg["hidden_size"], kv, dim), P(None, None, "mp", None)),
            "v": ("self_attn.v_proj.weight", lambda a: a.T.reshape(cfg["hidden_size"], kv, dim), P(None, None, "mp", None)),
            "o": ("self_attn.o_proj.weight", lambda a: a.T.reshape(heads, dim, cfg["hidden_size"]), P(None, "mp", None, None)),
            "gate": ("mlp.gate_proj.weight", lambda a: a.T, P(None, None, "mp")),
            "up": ("mlp.up_proj.weight", lambda a: a.T, P(None, None, "mp")),
            "down": ("mlp.down_proj.weight", lambda a: a.T, P(None, "mp", None)),
            "input_norm": ("input_layernorm.weight", lambda a: a, P()),
            "post_norm": ("post_attention_layernorm.weight", lambda a: a, P()),
            "q_norm": ("self_attn.q_norm.weight", lambda a: a, P()),
            "k_norm": ("self_attn.k_norm.weight", lambda a: a, P()),
        }
        self.weights = {}
        for name, (suffix, transform, spec) in specifications.items():
            array = np.stack([transform(read(f"model.layers.{layer}.{suffix}")) for layer in range(layers)])
            self.weights[name] = place(array, spec)
            self.weights[name].block_until_ready()
            del array
        self.embedding = place(read("model.embed_tokens.weight"), P("mp", None))
        self.final_norm = place(read("model.norm.weight"), P())
        self.lm_head = (self.embedding.T if cfg["tie_word_embeddings"] else
                        place(read("lm_head.weight").T, P(None, "mp")))
        jax.block_until_ready((self.embedding, self.final_norm, self.lm_head))
        self._step = jax.jit(self._forward, donate_argnums=(5, 6))
        self.first_compile_seconds = None
        self.qualification = None

    def _forward(self, weights, embedding, final_norm, lm_head, token, keys, values, position):
        jax, jnp, cfg = self.jax, self.jnp, self.config
        heads, kv, dim = cfg["num_attention_heads"], cfg["num_key_value_heads"], cfg["head_dim"]
        groups = heads // kv
        inv_freq = 1.0 / (cfg["rope_theta"] ** (jnp.arange(0, dim, 2, dtype=jnp.float32) / dim))
        angle = jnp.concatenate([position * inv_freq, position * inv_freq])
        cos, sin = jnp.cos(angle).astype(jnp.bfloat16), jnp.sin(angle).astype(jnp.bfloat16)

        def norm(x, w):
            fp32 = x.astype(jnp.float32)
            normal = fp32 * jax.lax.rsqrt(jnp.mean(fp32 * fp32, axis=-1, keepdims=True) + cfg["rms_norm_eps"])
            return normal.astype(jnp.bfloat16) * w

        def rotate(x):
            half = jnp.concatenate([-x[..., dim // 2:], x[..., :dim // 2]], axis=-1)
            return x * cos + half * sin

        def layer(hidden, xs):
            w, key_cache, value_cache = xs
            residual = hidden
            x = norm(hidden, w["input_norm"])
            q = rotate(norm(jnp.einsum("i,ihd->hd", x, w["q"]), w["q_norm"]))
            k = rotate(norm(jnp.einsum("i,ihd->hd", x, w["k"]), w["k_norm"]))
            v = jnp.einsum("i,ihd->hd", x, w["v"])
            key_cache = jax.lax.dynamic_update_slice(key_cache, k[None], (position, 0, 0))
            value_cache = jax.lax.dynamic_update_slice(value_cache, v[None], (position, 0, 0))
            scores = jnp.einsum("hgd,thd->hgt", q.reshape(kv, groups, dim), key_cache)
            scores = (scores * (dim ** -0.5)).astype(jnp.float32)
            scores = jnp.where(jnp.arange(self.context_length) <= position, scores, -jnp.inf)
            probabilities = jax.nn.softmax(scores, axis=-1).astype(jnp.bfloat16)
            attended = jnp.einsum("hgt,thd->hgd", probabilities, value_cache).reshape(heads, dim)
            hidden = residual + jnp.einsum("hd,hdi->i", attended, w["o"])
            residual = hidden
            x = norm(hidden, w["post_norm"])
            hidden = residual + (jax.nn.silu(x @ w["gate"]) * (x @ w["up"])) @ w["down"]
            return hidden, (key_cache, value_cache)

        hidden, (keys, values) = jax.lax.scan(layer, embedding[token], (weights, keys, values))
        logits = (norm(hidden, final_norm) @ lm_head).astype(jnp.float32)
        return logits, keys, values

    def empty_cache(self):
        shape = (self.config["num_hidden_layers"], self.context_length,
                 self.config["num_key_value_heads"], self.config["head_dim"])
        # device_put of a host zero array avoids creating an unsharded HBM copy.
        import ml_dtypes
        return tuple(self.jax.device_put(self.np.zeros(shape, dtype=ml_dtypes.bfloat16),
                                        self.cache_sharding) for _ in range(2))

    def compile(self) -> float:
        if self.first_compile_seconds is not None:
            return self.first_compile_seconds
        keys, values = self.empty_cache()
        start = time.monotonic()
        args = (self.weights, self.embedding, self.final_norm, self.lm_head,
                self.jnp.asarray(0, dtype=self.jnp.int32), keys, values,
                self.jnp.asarray(0, dtype=self.jnp.int32))
        self._compiled = self._step.lower(*args).compile()
        self.first_compile_seconds = time.monotonic() - start
        return self.first_compile_seconds

    def encode(self, messages) -> list[int]:
        return self.tokenizer.apply_chat_template(messages, tokenize=True,
                                                  add_generation_prompt=True, enable_thinking=False)

    def generate(self, messages, *, seed: int, max_new_tokens: int = 4096,
                 temperature: float = 0.6, top_p: float = 0.95, deadline=None,
                 qualification_mode=False) -> dict:
        """Generate after qualification; scoring requires precompiled kernels.

        Compilation belongs to the technical preflight before arm budgets start.
        Qualification may compile, with the outer subprocess deadline bounding
        the compiler; scoring never starts a cold compilation inside an arm.
        """
        if not qualification_mode and self.qualification != "passed":
            raise PreflightError("Model is not qualified by reference parity")
        if not 1 <= max_new_tokens <= 4096 or not 0 <= seed < 2**64:
            raise ValueError("Invalid completion/seed limit")
        tokens = self.encode(messages)
        if not tokens or len(tokens) + max_new_tokens > self.context_length:
            raise ValueError("Prompt plus completion exceeds the fixed cache/context ceiling")
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("Deadline before generation")
        was_compiled = self.first_compile_seconds is not None
        if not qualification_mode and not was_compiled:
            raise PreflightError("Scoring requires compilation during qualified preflight")
        self.compile()
        compile_seconds_this_call = 0.0 if was_compiled else self.first_compile_seconds
        start = time.monotonic()
        keys, values = self.empty_cache()
        self.jax.block_until_ready((keys, values))
        allocation_seconds = time.monotonic() - start
        rng = self.np.random.Generator(self.np.random.PCG64(seed))
        position, output, logit_traces = 0, [], []
        prefill_start = time.monotonic()
        for token in tokens:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("Deadline during prefill")
            logits, keys, values = self._compiled(
                self.weights, self.embedding, self.final_norm, self.lm_head,
                self.jnp.asarray(token, dtype=self.jnp.int32), keys, values,
                self.jnp.asarray(position, dtype=self.jnp.int32))
            # Bound outstanding device work; no hidden backlog beyond deadline.
            logits.block_until_ready()
            position += 1
        prefill_seconds = time.monotonic() - prefill_start
        decode_start = time.monotonic()
        stop_reason = "max_tokens"
        for index in range(max_new_tokens):
            if deadline is not None and time.monotonic() >= deadline:
                stop_reason = "deadline"
                break
            host_logits = self.np.asarray(logits)
            if qualification_mode:
                logit_traces.append(host_logits.copy())
            next_token = sample_token(host_logits, rng, temperature, top_p)
            output.append(next_token)
            if next_token == self.tokenizer.eos_token_id:
                stop_reason = "eos"
                break
            if index + 1 < max_new_tokens:
                logits, keys, values = self._compiled(
                    self.weights, self.embedding, self.final_norm, self.lm_head,
                    self.jnp.asarray(next_token, dtype=self.jnp.int32), keys, values,
                    self.jnp.asarray(position, dtype=self.jnp.int32))
                logits.block_until_ready()
                position += 1
        decode_seconds = time.monotonic() - decode_start
        result = {
            "text": self.tokenizer.decode(output, skip_special_tokens=True),
            "prompt_token_ids": tokens, "output_token_ids": output,
            "prompt_tokens": len(tokens), "output_tokens": len(output), "seed": seed,
            "temperature": temperature, "top_p": top_p, "stop_reason": stop_reason,
            "cache_allocation_seconds": allocation_seconds,
            "prefill_seconds": prefill_seconds, "decode_seconds": decode_seconds,
            "time_to_first_token_seconds": allocation_seconds + prefill_seconds,
            "generation_wall_seconds": time.monotonic() - start,
            "decode_tokens_per_second": max(len(output) - 1, 0) / max(decode_seconds, 1e-9),
            "model_revision": self.candidate["revision"],
            "adapter_cold_compile_seconds": self.first_compile_seconds,
        }
        result["cost"] = {
            "prompt_tokens": result["prompt_tokens"], "output_tokens": result["output_tokens"],
            "wall_seconds": result["generation_wall_seconds"] + compile_seconds_this_call,
            "prefill_seconds": prefill_seconds, "decode_seconds": decode_seconds,
            "cold_compile_seconds": compile_seconds_this_call,
        }
        if qualification_mode:
            result["_logits"] = logit_traces
        return result


def transformers_reference(model_dir, token_ids: list[int], *, new_tokens=8, threads=2) -> dict:
    """Official eager BF16 CPU reference; technical prompt only, never panel work."""
    import numpy as np
    import torch
    from transformers import AutoModelForCausalLM

    torch.set_num_threads(threads)
    torch.set_num_interop_threads(1)
    start = time.monotonic()
    model = AutoModelForCausalLM.from_pretrained(
        str(model_dir), torch_dtype=torch.bfloat16, local_files_only=True,
        trust_remote_code=False, attn_implementation="eager", use_safetensors=True)
    model.eval()
    load_seconds = time.monotonic() - start
    output, traces, past = [], [], None
    ids = torch.tensor([token_ids], dtype=torch.long)
    start = time.monotonic()
    with torch.inference_mode():
        for _ in range(new_tokens):
            result = model(input_ids=ids, past_key_values=past, use_cache=True)
            logits = result.logits[0, -1].float().numpy().copy()
            traces.append(logits)
            token = int(np.argmax(logits))
            output.append(token)
            if token == model.config.eos_token_id:
                break
            past = result.past_key_values
            ids = torch.tensor([[token]], dtype=torch.long)
    return {"output_token_ids": output, "_logits": traces,
            "load_seconds": load_seconds, "generation_seconds": time.monotonic() - start}
