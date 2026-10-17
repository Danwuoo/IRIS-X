"""Compact NVARC Qwen3 continuation, not original Unsloth training parity.

Only the 16-token serialized tokenizer is admitted. Actual upstream AF3 replay
and SFT are inherited; neither grid/DFA filtering nor English prompts exist here.
Checkpoint files contain exact named trainables (including full tiny embeddings
and output head), never a guessed PEFT export remapping or optimizer/RNG resume.
The caller must independently verify base material bytes before supplying its
identity. This module does not load data, evaluate answers, or launch workers.
"""
from __future__ import annotations

from contextlib import nullcontext
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile

import torch
import torch.nn.functional as F

from tools.arc2_goal_sprint_20261017.model import (
    Engine, adapter_state, check_deadline, make_optimizer, restore_state,
    state_digest, tensor_inventory,
)

VOCAB_SIZE, EOS_ID, PAD_ID, MAX_GENERATION, MAX_CONTEXT = 16, 15, 13, 931, 8192
PROJECTIONS = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")
VOCAB = {**{str(i): i for i in range(10)}, "Ċ": 10, "user": 11,
         "assistant": 12, "<|endoftext|>": 13, "<|im_start|>": 14, "<|im_end|>": 15}
OFFICIAL_SHAPES = {
    "2b": dict(num_hidden_layers=28, hidden_size=2048, num_attention_heads=16,
               num_key_value_heads=8, head_dim=128, intermediate_size=6144),
    "4b": dict(num_hidden_layers=36, hidden_size=2560, num_attention_heads=32,
               num_key_value_heads=8, head_dim=128, intermediate_size=9728),
}
FORMAT = "irisx/nvarc-compact-trainable-v1"


class FatalUpdateError(RuntimeError):
    """The worker must abort: parameter rollback is NOT optimizer/RNG rollback."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode() + b"\n"


def _identity(value):
    if not isinstance(value, dict) or not value:
        raise ValueError("independently verified nonempty base_identity required")
    return json.loads(_canonical(value))


def validate_tokenizer(tokenizer):
    """Reject the slow Qwen2 fallback that silently discards role words."""
    if (len(tokenizer) != VOCAB_SIZE or tokenizer.get_vocab() != VOCAB
            or tokenizer.eos_token_id != EOS_ID or tokenizer.pad_token_id != PAD_ID):
        raise ValueError("exact compact 16-token vocabulary/EOS/pad contract required")
    probes = {
        "0123456789\n": list(range(11)), "user": [11], "assistant": [12],
        "<|endoftext|>": [13], "<|im_start|>": [14], "<|im_end|>": [15],
        "<|im_start|>user\n12\n34<|im_end|>\n<|im_start|>assistant\n":
            [14, 11, 10, 1, 2, 10, 3, 4, 15, 10, 14, 12, 10],
        "56\n78<|im_end|>": [5, 6, 10, 7, 8, 15],
    }
    for text, expected in probes.items():
        if (tokenizer.encode(text, add_special_tokens=False) != expected
                or tokenizer.decode(expected, skip_special_tokens=False,
                                    clean_up_tokenization_spaces=False) != text):
            raise ValueError("compact tokenizer exact encode/decode probe failed")
    return {"vocab_size": 16, "eos_token_id": 15, "pad_token_id": 13,
            "probe_sha256": hashlib.sha256(_canonical(probes)).hexdigest()}


def load_compact_tokenizer(path):
    from transformers import PreTrainedTokenizerFast
    # AutoTokenizer may select Qwen2's BPE tokenizer for a WordLevel backend.
    # Loading the actual serialized backend avoids that incompatible conversion.
    tokenizer = PreTrainedTokenizerFast(tokenizer_file=str(Path(path) / "tokenizer.json"),
                                        eos_token="<|im_end|>", pad_token="<|endoftext|>",
                                        model_max_length=MAX_CONTEXT)
    validate_tokenizer(tokenizer)
    return tokenizer


def model_contract(config, *, variant=None, test_fixture=False):
    data = config if isinstance(config, dict) else config.to_dict()
    keys = (*next(iter(OFFICIAL_SHAPES.values())).keys(), "vocab_size", "tie_word_embeddings",
            "model_type", "attention_dropout", "attention_bias", "hidden_act", "rms_norm_eps",
            "max_position_embeddings", "layer_types", "bos_token_id", "eos_token_id")
    contract = {key: copy.deepcopy(data.get(key)) for key in keys}
    if (contract["model_type"] != "qwen3" or contract["vocab_size"] != 16
            or contract["tie_word_embeddings"] is not False
            or contract["attention_dropout"] != 0.0 or contract["attention_bias"] is not False
            or contract["bos_token_id"] != 13 or contract["eos_token_id"] != 15):
        raise ValueError("untied dropout-zero compact Qwen3 config required")
    shapes = {key: data.get(key) for key in next(iter(OFFICIAL_SHAPES.values()))}
    if test_fixture:
        if variant not in (None, "tiny"):
            raise ValueError("tiny fixture cannot claim an official variant")
        variant = "tiny"
        if (any(type(value) is not int or value <= 0 for value in shapes.values())
                or shapes["num_hidden_layers"] > 4 or shapes["hidden_size"] > 128):
            raise ValueError("bounded synthetic tiny fixture required")
    else:
        matches = [name for name, expected in OFFICIAL_SHAPES.items() if shapes == expected]
        if len(matches) != 1 or variant not in (None, matches[0]):
            raise ValueError("official NVARC 2b/4b model dimensions differ")
        variant = matches[0]
        if (data.get("architectures") != ["Qwen3ForCausalLM"]
                or data.get("hidden_act") != "silu" or data.get("rms_norm_eps") != 1e-6
                or data.get("max_position_embeddings") != 262144
                or data.get("layer_types") != ["full_attention"] * shapes["num_hidden_layers"]
                or data.get("use_sliding_window") is not False or data.get("sliding_window") is not None):
            raise ValueError("official NVARC architecture/config differs")
    # Transformers 4 stores rope_scaling/rope_theta; 5 migrates the SAME keys
    # into rope_parameters. Canonicalize only that documented representation.
    rope = data.get("rope_parameters")
    if rope is None:
        rope = {**(data.get("rope_scaling") or {}), "rope_theta": data.get("rope_theta")}
    else:
        rope = copy.deepcopy(rope)
    rope.setdefault("rope_type", "default")
    if not test_fixture:
        expected_rope = {"rope_type": "default", "rope_theta": 5000000}
        if variant == "2b":
            expected_rope.update(mrope_interleaved=True, mrope_section=[24, 20, 20])
        if rope != expected_rope:
            raise ValueError("official rotary metadata differs; mrope keys must be preserved")
    contract.update(variant=variant, rope_parameters=rope)
    return contract


def validate_trainables(model, *, rank, alpha, base_dtype):
    """Check every actual tensor and frozen base, not a declared PEFT count."""
    config = model.config
    layers, hidden, intermediate = config.num_hidden_layers, config.hidden_size, config.intermediate_size
    q, kv = config.num_attention_heads * config.head_dim, config.num_key_value_heads * config.head_dim
    dimensions = {"q_proj": (hidden, q), "k_proj": (hidden, kv), "v_proj": (hidden, kv),
                  "o_proj": (q, hidden), "gate_proj": (hidden, intermediate),
                  "up_proj": (hidden, intermediate), "down_proj": (intermediate, hidden)}
    expected = {}
    for layer in range(layers):
        for projection, (inputs, outputs) in dimensions.items():
            block = "self_attn" if projection in PROJECTIONS[:4] else "mlp"
            stem = f"base_model.model.model.layers.{layer}.{block}.{projection}"
            expected[stem + ".lora_A.default.weight"] = (rank, inputs)
            expected[stem + ".lora_B.default.weight"] = (outputs, rank)
    expected["base_model.model.model.embed_tokens.modules_to_save.default.weight"] = (16, hidden)
    expected["base_model.model.lm_head.modules_to_save.default.weight"] = (16, hidden)
    actual = {name: p for name, p in model.named_parameters() if p.requires_grad}
    if (set(actual) != set(expected) or any(tuple(actual[n].shape) != shape
            or actual[n].dtype != torch.float32 for n, shape in expected.items())):
        raise ValueError("actual trainable tensor inventory/shape/FP32 differs")
    if any(p.dtype != base_dtype for p in model.parameters() if not p.requires_grad):
        raise ValueError("frozen base dtype differs")
    if (len(model.peft_config) != 1 or "default" not in model.peft_config):
        raise ValueError("exactly one default adapter required")
    peft = model.peft_config["default"]
    if (model.active_adapter != "default" or peft.inference_mode
            or peft.r != rank or peft.lora_alpha != alpha or not peft.use_rslora
            or peft.lora_dropout != 0 or peft.bias != "none" or peft.use_dora
            or set(peft.target_modules) != set(PROJECTIONS)
            or set(peft.modules_to_save or []) != {"embed_tokens", "lm_head"}
            or peft.rank_pattern or peft.alpha_pattern):
        raise ValueError("seven-projection rsLoRA/full-head-and-embedding config differs")
    embeddings = model.get_input_embeddings().modules_to_save["default"].weight
    head = model.get_output_embeddings().modules_to_save["default"].weight
    if embeddings.data_ptr() == head.data_ptr() or config.tie_word_embeddings:
        raise ValueError("compact embedding and output head must remain untied")
    for _, module in model.named_modules():
        if hasattr(module, "lora_A") and "default" in module.lora_A:
            if not math.isclose(module.scaling["default"], alpha / math.sqrt(rank), rel_tol=1e-12):
                raise ValueError("actual rsLoRA scaling differs")
    checkpointed = [module for module in model.modules() if getattr(module, "gradient_checkpointing", False)]
    if (not model.is_gradient_checkpointing or not checkpointed
            or any(getattr(getattr(module, "_gradient_checkpointing_func", None), "keywords", {}).get("use_reentrant")
                   is not False for module in checkpointed)):
        raise ValueError("actual nonreentrant gradient checkpointing required")
    return {"tensors": {n: {"shape": list(p.shape), "dtype": str(p.dtype)} for n, p in sorted(actual.items())},
            "tensor_count": len(actual), "parameter_count": sum(p.numel() for p in actual.values()),
            "frozen_dtype": str(base_dtype), "trainable_dtype": "torch.float32",
            "rank": rank, "alpha": alpha, "use_rslora": True,
            "target_modules": list(PROJECTIONS), "modules_to_save": ["embed_tokens", "lm_head"]}


class CompactEngine(Engine):
    def __init__(self, model, tokenizer, *, base_identity, variant=None, device=None,
                 seed=0, rank=64, alpha=16, base_dtype=torch.bfloat16, test_fixture=False):
        super().__init__(model, tokenizer, device=device)
        # Resolve cuda without an index to the actual resident parameter device.
        self.device = next(model.parameters()).device
        self.base_identity = _identity(base_identity)
        self.contract = model_contract(model.config, variant=variant, test_fixture=test_fixture)
        self.tokenizer_admission = validate_tokenizer(tokenizer)
        self.trainable_inventory = validate_trainables(model, rank=rank, alpha=alpha, base_dtype=base_dtype)
        self.base_dtype = base_dtype
        self.generator = torch.Generator(device=self.device).manual_seed(seed)
        self._fatal_update = False
        self._checkpoint_loaded = False

    @classmethod
    def from_base(cls, model, tokenizer, *, base_identity, variant=None, rank=64, alpha=16,
                  device=None, seed=0, adapter_seed=None, base_dtype=torch.bfloat16, test_fixture=False):
        from peft import LoraConfig, get_peft_model
        adapter_seed = seed if adapter_seed is None else adapter_seed
        if any(type(value) is not int or not 0 <= value < 2**63 for value in (seed, adapter_seed)):
            raise ValueError("rollout and adapter seeds must be integers in 0..2**63-1")
        if type(rank) is not int or rank < 1 or type(alpha) not in (int, float) or not math.isfinite(alpha) or alpha <= 0:
            raise ValueError("positive finite LoRA rank/alpha required")
        if not test_fixture and (rank != 64 or alpha != 16 or base_dtype != torch.bfloat16):
            raise ValueError("official continuation requires rank64/alpha16 and BF16 frozen base")
        if base_dtype not in (torch.float32, torch.bfloat16):
            raise ValueError("only FP32 fixture or BF16 base supported")
        if model.__class__.__name__ != "Qwen3ForCausalLM":
            raise ValueError("actual Qwen3ForCausalLM required")
        model_contract(model.config, variant=variant, test_fixture=test_fixture)
        validate_tokenizer(tokenizer)
        _identity(base_identity)
        if model.get_input_embeddings().weight.data_ptr() == model.get_output_embeddings().weight.data_ptr():
            raise ValueError("original embedding and output head are tied")
        model.to(device=device or next(model.parameters()).device, dtype=base_dtype)
        model.config.use_cache = False
        resident = next(model.parameters()).device
        # Adapter initialization is independent of both global process randomness
        # and the private rollout stream. Paired arms may explicitly share only
        # adapter_seed while choosing separate seed values for behavior sampling.
        devices = [resident.index] if resident.type == "cuda" else []
        with torch.random.fork_rng(devices=devices):
            torch.random.default_generator.manual_seed(adapter_seed)
            if resident.type == "cuda":
                with torch.cuda.device(resident):
                    torch.cuda.manual_seed(adapter_seed)
            model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=alpha, lora_dropout=0.0,
                use_rslora=True, bias="none", task_type="CAUSAL_LM", target_modules=list(PROJECTIONS),
                modules_to_save=["embed_tokens", "lm_head"]))
        for parameter in model.parameters():
            if parameter.requires_grad:
                parameter.data = parameter.data.float()
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        engine = cls(model, tokenizer, base_identity=base_identity, variant=variant, device=device,
                     seed=seed, rank=rank, alpha=alpha, base_dtype=base_dtype, test_fixture=test_fixture)
        engine.adapter_seed = adapter_seed
        return engine

    @classmethod
    def load(cls, path, *, base_identity, variant=None, rank=64, alpha=16, device="cuda", seed=0, adapter_seed=None):
        from transformers import AutoConfig, Qwen3ForCausalLM
        path = Path(path)
        raw = json.loads((path / "config.json").read_text())
        expected = model_contract(raw, variant=variant)
        tokenizer = load_compact_tokenizer(path)
        config = AutoConfig.from_pretrained(path, local_files_only=True, trust_remote_code=False)
        if model_contract(config, variant=variant) != expected:
            raise ValueError("loaded configuration lost official metadata")
        _identity(base_identity)
        model = Qwen3ForCausalLM.from_pretrained(path, config=config, local_files_only=True,
                    trust_remote_code=False, dtype=torch.bfloat16,
                    attn_implementation="sdpa", device_map={"": device})
        return cls.from_base(model, tokenizer, base_identity=base_identity, variant=variant,
                             rank=rank, alpha=alpha, device=device, seed=seed, adapter_seed=adapter_seed)

    def _healthy(self):
        if self._fatal_update:
            raise FatalUpdateError("engine is poisoned after failed update; abort worker, no optimizer reset/reuse")

    def autocast(self):
        return torch.autocast(self.device.type, dtype=torch.bfloat16) if self.base_dtype == torch.bfloat16 else nullcontext()

    def _tokens(self, ids):
        if (not isinstance(ids, (list, tuple)) or not ids or len(ids) > MAX_CONTEXT
                or any(type(token) is not int or not 0 <= token < VOCAB_SIZE for token in ids)):
            raise ValueError("nonempty bounded original compact token IDs required")

    def completion_logps(self, ids, prompt_length):
        self._healthy()
        self._tokens(ids)
        return super().completion_logps(ids, prompt_length)

    def masked_logps(self, ids, mask):
        self._healthy()
        self._tokens(ids)
        return super().masked_logps(ids, mask)

    def af3_update(self, rows, optimizer, *, expected_groups, group_size, deadline=math.inf):
        self._healthy()
        return super().af3_update(rows, optimizer, expected_groups=expected_groups,
                                  group_size=group_size, deadline=deadline)

    def commit(self, optimizer):
        """Restore parameters on failed mutation, poison engine, abort worker.

        Optimizer state may be partially advanced and is deliberately NOT reset
        or called resumed. Reusing it, replaying or saving this engine is forbidden.
        """
        self._healthy()
        supplied = [p for group in optimizer.param_groups for p in group["params"]]
        if len(supplied) != len(self.parameters) or {id(p) for p in supplied} != {id(p) for p in self.parameters}:
            raise ValueError("optimizer must own the exact trainable inventory only")
        before = None
        try:
            gradients = [p.grad for p in self.parameters if p.grad is not None]
            if not gradients or any(not bool(torch.isfinite(g).all()) for g in gradients):
                raise FloatingPointError("missing or nonfinite trainable gradients")
            norm = torch.nn.utils.clip_grad_norm_(self.parameters, 1.0, error_if_nonfinite=True)
            if norm.item() == 0:
                optimizer.zero_grad(set_to_none=True)
                return {"updated": False, "gradient_norm": 0.0, "reason": "zero_gradient"}
            before = [p.detach().clone() for p in self.parameters]
            self.optimizer_attempts += 1
            optimizer.step()
            if (any(not bool(torch.isfinite(p).all()) for p in self.parameters)
                    or any(not bool(torch.isfinite(v).all()) for state in optimizer.state.values()
                           for v in state.values() if isinstance(v, torch.Tensor))):
                raise FloatingPointError("nonfinite trainable/optimizer state after step")
        except BaseException as error:
            self._fatal_update = True
            if before is not None:
                with torch.no_grad():
                    for parameter, previous in zip(self.parameters, before):
                        parameter.copy_(previous)
            optimizer.zero_grad(set_to_none=True)
            raise FatalUpdateError("update failed; trainables restored if mutated; optimizer/RNG not restored; abort worker") from error
        self.optimizer_steps += 1
        optimizer.zero_grad(set_to_none=True)
        return {"updated": True, "gradient_norm": norm.item()}

    @torch.no_grad()
    def generate(self, prompt_ids, *, count=1, max_new_tokens=MAX_GENERATION,
                 sample=False, deadline=math.inf, generator=None):
        if type(count) is not int or not 1 <= count <= 64:
            raise ValueError("count must be an integer in 1..64")
        return self._generate_batch([prompt_ids] * count, max_new_tokens=max_new_tokens,
                                    sample=sample, deadline=deadline, generator=generator)

    @torch.no_grad()
    def generate_prompts(self, prompts, *, max_new_tokens=MAX_GENERATION, deadline=math.inf):
        if not isinstance(prompts, (list, tuple)) or not 1 <= len(prompts) <= 8:
            raise ValueError("one to eight heterogeneous prompts required")
        return self._generate_batch(prompts, max_new_tokens=max_new_tokens, sample=False, deadline=deadline)

    def _generate_batch(self, prompts, *, max_new_tokens, sample, deadline, generator=None):
        self._healthy()
        if type(max_new_tokens) is not int or not 1 <= max_new_tokens <= MAX_GENERATION or type(sample) is not bool:
            raise ValueError("generation bound must be 1..931 with boolean sample")
        for prompt in prompts:
            self._tokens(prompt)
            if len(prompt) + max_new_tokens > MAX_CONTEXT:
                raise ValueError("prompt plus generation reservation exceeds context")
        check_deadline(deadline)
        prompts = [list(prompt) for prompt in prompts]
        self.model.eval()
        generator = generator if generator is not None else self.generator
        if not isinstance(generator, torch.Generator) or torch.device(generator.device) != self.device:
            raise ValueError("explicit generator must be on the engine device")
        count, width = len(prompts), max(map(len, prompts))
        lengths = list(map(len, prompts))
        tokens = torch.tensor([[PAD_ID] * (width - len(p)) + p for p in prompts], device=self.device)
        attention = torch.tensor([[0] * (width - len(p)) + [1] * len(p) for p in prompts], device=self.device)
        positions = (attention.cumsum(-1) - 1).clamp(min=0)
        cache = out = logits = selected = None
        generated, logps, finished = [[] for _ in prompts], [[] for _ in prompts], [False] * count
        try:
            for step in range(max_new_tokens):
                check_deadline(deadline)
                with self.autocast():
                    out = self.model(input_ids=tokens, attention_mask=attention, position_ids=positions,
                                     past_key_values=cache, use_cache=True, logits_to_keep=1)
                self.forward_calls += 1
                cache = out.past_key_values
                logits = out.logits[:, -1, :].float()
                if logits.shape != (count, 16) or not bool(torch.isfinite(logits).all()):
                    raise FloatingPointError("nonfinite or non-16-vocabulary rollout logits")
                # The complete 16-way distribution is the RL behavior policy.
                selected = torch.multinomial(F.softmax(logits, dim=-1), 1, generator=generator) if sample else logits.argmax(-1, keepdim=True)
                chosen_logps = (logits.gather(1, selected).squeeze(1) - torch.logsumexp(logits, -1)).tolist()
                self.sampled_tokens += sum(not done for done in finished)
                check_deadline(deadline)
                for i, token in enumerate(selected[:, 0].tolist()):
                    if not finished[i]:
                        generated[i].append(token)
                        logps[i].append(chosen_logps[i])
                        finished[i] = token == EOS_ID  # Never stop on ID13 or generation_config extras.
                if all(finished):
                    break
                tokens = selected
                attention = torch.cat((attention, attention.new_ones((count, 1))), dim=1)
                positions = torch.tensor([[length + step] for length in lengths], device=self.device)
            check_deadline(deadline)
            return [{"input_ids": prompts[i] + generated[i], "prompt_length": lengths[i],
                     "completion_ids": generated[i], "behavior_log_probs": [0.0] * lengths[i] + logps[i],
                     "text": self.tokenizer.decode(generated[i], skip_special_tokens=False,
                                                   clean_up_tokenization_spaces=False),
                     "completion_tokens": len(generated[i]), "stop": "completed" if finished[i] else "length"}
                    for i in range(count)]
        finally:
            cache = out = logits = selected = tokens = attention = positions = None

    def _checkpoint_admission(self):
        self._healthy()
        if (model_contract(self.model.config, variant=self.contract["variant"],
                           test_fixture=self.contract["variant"] == "tiny") != self.contract
                or validate_tokenizer(self.tokenizer) != self.tokenizer_admission
                or validate_trainables(self.model, rank=self.trainable_inventory["rank"],
                                       alpha=self.trainable_inventory["alpha"], base_dtype=self.base_dtype)
                    != self.trainable_inventory):
            raise ValueError("model/tokenizer/trainable contract changed after admission")

    def save_checkpoint(self, root, *, origin):
        return save_checkpoint(self, root, origin=origin)

    def load_checkpoint(self, spec):
        return load_checkpoint(self, spec)


def _origin(origin):
    if (not isinstance(origin, dict) or origin.get("phase") != "pre_public"
            or origin.get("public_ttt_applied") is not False or origin.get("public_labels_used") is not False):
        raise ValueError("explicit pre_public, no PUBLIC TTT/labels checkpoint origin required")
    return json.loads(_canonical(origin))


def save_checkpoint(engine, root, *, origin):
    """Publish a new immutable checkpoint directory; never overwrite originals."""
    from safetensors.torch import save
    engine._checkpoint_admission()
    origin = _origin(origin)
    root = Path(root)
    if root.exists() or root.is_symlink():
        raise FileExistsError("checkpoint destination already exists")
    state = adapter_state(engine.model)
    if any(not bool(torch.isfinite(v).all()) for v in state.values()):
        raise ValueError("nonfinite trainables cannot be saved")
    body = save(state)
    manifest = {"format": FORMAT, "base_identity": engine.base_identity, "model_contract": engine.contract,
                "trainable_contract": engine.trainable_inventory, "tokenizer_admission": engine.tokenizer_admission,
                "origin": origin, "trainable_tensors": tensor_inventory(state), "state_sha256": state_digest(state),
                "file": {"name": "trainable_state.safetensors", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()},
                "optimizer_resumed": False, "rng_resumed": False, "fresh_optimizer_required": True}
    raw = _canonical(manifest)
    root.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix="." + root.name + ".", dir=root.parent))
    try:
        for name, content in (("trainable_state.safetensors", body), ("manifest.json", raw)):
            with (staged / name).open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        if root.exists() or root.is_symlink():
            raise FileExistsError("checkpoint destination already exists")
        os.rename(staged, root)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    return {"root": str(root), "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "state_sha256": manifest["state_sha256"], "optimizer_resumed": False,
            "rng_resumed": False, "fresh_optimizer_required": True}


def load_checkpoint(engine, spec):
    """Exact tensor-name restore with all validation preceding any mutation.

    This is a warm start into a fresh engine, not exact training continuation.
    The externally pinned manifest hash and independently admitted base identity
    must both match. No pickle, remote code, key heuristics or optimizer reset.
    """
    from safetensors.torch import load
    engine._checkpoint_admission()
    if engine.optimizer_attempts or engine.optimizer_steps or engine.forward_calls or engine._checkpoint_loaded:
        raise ValueError("checkpoint load requires an unused engine and a new phase optimizer")
    if (not isinstance(spec, dict) or set(spec) != {"root", "manifest_sha256"}
            or not isinstance(spec["manifest_sha256"], str)
            or not re.fullmatch("[0-9a-f]{64}", spec["manifest_sha256"])):
        raise ValueError("strict root and pinned manifest_sha256 required")
    root = Path(spec["root"])
    if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()} != {"manifest.json", "trainable_state.safetensors"}:
        raise ValueError("exact regular checkpoint file inventory required")
    bodies = {}
    for name, limit in (("manifest.json", 8 * 1024**2), ("trainable_state.safetensors", 2 * 1024**3)):
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise ValueError("regular bounded checkpoint file required")
        bodies[name] = path.read_bytes()
    raw, body = bodies["manifest.json"], bodies["trainable_state.safetensors"]
    if hashlib.sha256(raw).hexdigest() != spec["manifest_sha256"]:
        raise ValueError("pinned checkpoint manifest SHA differs")
    manifest = json.loads(raw)
    if raw != _canonical(manifest):
        raise ValueError("canonical manifest required")
    required = {"format", "base_identity", "model_contract", "trainable_contract", "tokenizer_admission", "origin",
                "trainable_tensors", "state_sha256", "file", "optimizer_resumed", "rng_resumed", "fresh_optimizer_required"}
    if (set(manifest) != required or manifest["format"] != FORMAT
            or manifest["base_identity"] != engine.base_identity
            or manifest["model_contract"] != engine.contract
            or manifest["trainable_contract"] != engine.trainable_inventory
            or manifest["tokenizer_admission"] != engine.tokenizer_admission
            or manifest["optimizer_resumed"] is not False or manifest["rng_resumed"] is not False
            or manifest["fresh_optimizer_required"] is not True):
        raise ValueError("checkpoint schema, model identity or training contract differs")
    _origin(manifest["origin"])
    if manifest["file"] != {"name": "trainable_state.safetensors", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}:
        raise ValueError("checkpoint tensor file SHA/bytes differ")
    state = load(body)
    before = adapter_state(engine.model)
    if (set(state) != set(before) or any(v.shape != before[n].shape or v.dtype != before[n].dtype
            or not bool(torch.isfinite(v).all()) for n, v in state.items())
            or tensor_inventory(state) != manifest["trainable_tensors"]
            or state_digest(state) != manifest["state_sha256"]):
        raise ValueError("exact checkpoint tensor inventory/shape/dtype/hash/finiteness differs")
    try:
        restore_state(engine.model, state)
        if state_digest(adapter_state(engine.model)) != manifest["state_sha256"]:
            raise ValueError("restored trainable digest differs")
    except BaseException:
        restore_state(engine.model, before)
        if state_digest(adapter_state(engine.model)) != state_digest(before):
            engine._fatal_update = True
            raise FatalUpdateError("checkpoint rollback failed; abort worker")
        raise
    engine._checkpoint_loaded = True
    return {"manifest_sha256": spec["manifest_sha256"], "state_sha256": manifest["state_sha256"],
            "base_identity": engine.base_identity, "origin": manifest["origin"], "tensor_count": len(state),
            "optimizer_resumed": False, "rng_resumed": False, "fresh_optimizer_required": True}
