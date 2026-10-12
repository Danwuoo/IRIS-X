"""Explicit local native-head model calls, ASCII grid automaton, and exact NLL.

Imports are inert. Production loading retains pinned material/environment/G4
admission. The independent tiny_cpu route creates random small neural weights;
it is not evidence that the 8B model was loaded or that G4 inference ran.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from contextlib import contextmanager
from pathlib import Path

from .grid_codec import decode_grid


class NativeModelError(ValueError):
    pass


class ContextLimitError(NativeModelError):
    pass


def _require(condition, message):
    if not condition:
        raise NativeModelError(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _configuration(value):
    if value is None:
        return {}
    if type(value) is dict:
        return dict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    raise NativeModelError("configuration must be a dictionary or native config")


def _ids(value):
    if hasattr(value, "tolist"):
        value = value.tolist()
    _require(type(value) in (list, tuple) and all(type(v) is int and v >= 0 for v in value),
             "flat native token ID sequence required")
    return list(value)


def _encode(tokenizer, text):
    return _ids(tokenizer.encode(text, add_special_tokens=False))


def _decode(tokenizer, ids):
    return tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)


class TinyByteTokenizer:
    """Deliberately synthetic ASCII test tokenizer; never admitted as production."""
    eos_token_id = 128
    pad_token_id = 128
    bos_token_id = 129
    all_special_ids = [128, 129]
    chat_template = "synthetic-ascii-chat-v1"
    model_max_length = 8192

    def __len__(self):
        return 130

    def get_vocab(self):
        return {**{chr(i): i for i in range(128)}, "<eos>": 128, "<bos>": 129}

    def encode(self, text, add_special_tokens=False):
        _require(type(text) is str and all(ord(c) < 128 for c in text), "tiny tokenizer supports ASCII only")
        return [ord(c) for c in text]

    def decode(self, ids, skip_special_tokens=False, clean_up_tokenization_spaces=False):
        _require(all(type(i) is int and 0 <= i < 130 for i in ids), "invalid tiny native ID")
        return "".join(chr(i) if i < 128 else "" if skip_special_tokens else
                       "<eos>" if i == 128 else "<bos>" for i in ids)

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False,
                            enable_thinking=False, **kwargs):
        text = "".join("[" + m["role"] + "]\n" + m["content"] + "\n" for m in messages)
        if add_generation_prompt:
            text += "[assistant]\n"
        return self.encode(text) if tokenize else text


    @classmethod
    def _fixture(cls):
        return {"format": "irisx/synthetic-ascii-tokenizer-fixture-v1",
                "synthetic_only": True, "production_compatible": False,
                "notice": "CPU unit-test ASCII tokenizer. Not Granite tokenizer material or a production model export.",
                "encoding": "ASCII code points 0..127 map identically to token IDs; no normalization or merging",
                "eos_token_id": cls.eos_token_id, "pad_token_id": cls.pad_token_id,
                "bos_token_id": cls.bos_token_id, "vocab_size": 130,
                "chat_template": cls.chat_template, "model_max_length": cls.model_max_length,
                "vocabulary_sha256": _digest(cls().get_vocab())}

    def save_pretrained(self, save_directory, **kwargs):
        """Persist only this explicitly synthetic, self-describing test fixture.

        Deliberately not named tokenizer.json/tokenizer_config.json: generic HF
        production loaders must not mistake this ASCII fixture for native bytes.
        Existing identical fixtures are idempotent; changed bytes are rejected.
        """
        root = Path(save_directory)
        root.mkdir(parents=True, exist_ok=True)
        path = root / "tiny-byte-tokenizer.json"
        raw = _canonical(self._fixture()) + b"\n"
        if path.exists():
            _require(path.is_file() and path.read_bytes() == raw, "refusing to replace a different tiny tokenizer fixture")
        else:
            with path.open("xb") as handle:
                handle.write(raw)
        return (str(path),)

    @classmethod
    def from_pretrained(cls, directory):
        """Read a bounded exact fixture without importing HF or accessing a network."""
        path = Path(directory) / "tiny-byte-tokenizer.json"
        _require(path.is_file() and path.stat().st_size <= 16384, "bounded local tiny tokenizer fixture required")
        raw = path.read_bytes()
        _require(raw == _canonical(cls._fixture()) + b"\n", "tiny tokenizer fixture policy or bytes changed")
        return cls()


class NativeGridConstraint:
    """A rectangular-grid DFA over proven native ASCII token byte strings.

    A ByteLevel decoder maps its byte-alphabet symbols to bytes and then UTF-8.
    ASCII digit/newline byte strings are UTF-8-complete and concatenative in
    *every* context consisting of the same alphabet. We require that exact
    native decoder and raw base vocabulary, exclude all added tokens, prove the
    eleven one-character paths exist, audit contextual decoding, and re-check
    each actual generated prefix with native decode. A single-token decode
    table alone is deliberately insufficient for admission.
    """
    def __init__(self, tokenizer, eos_ids, *, tiny_cpu=False):
        self.tokenizer = tokenizer
        self.eos_ids = tuple(eos_ids)
        vocabulary = tokenizer.get_vocab()
        _require(type(vocabulary) is dict and len(set(vocabulary.values())) == len(vocabulary),
                 "one-to-one native vocabulary mapping required")
        self.tokenizer_sha256 = _digest(vocabulary)
        backend = getattr(tokenizer, "backend_tokenizer", None)
        if type(tokenizer) is TinyByteTokenizer and tiny_cpu:
            pieces = {ord(c): c for c in "0123456789\n"}
            proof = "explicit-synthetic-ascii-test-tokenizer"
            backend_hash = _digest({"synthetic": tokenizer.chat_template})
        else:
            _require(backend is not None and hasattr(backend, "to_str"),
                     "grid constraints need a proven native ByteLevel backend")
            raw = json.loads(backend.to_str())
            decoder = raw.get("decoder", {})
            _require(type(decoder) is dict and decoder.get("type") == "ByteLevel" and
                     set(decoder) <= {"type", "add_prefix_space", "trim_offsets", "use_regex"},
                     "unproven native decoding pipeline; grid admission denied")
            model = raw.get("model", {})
            _require(model.get("type") == "BPE" and type(model.get("vocab")) is dict,
                     "native ByteLevel BPE vocabulary required")
            added = {item["id"] for item in raw.get("added_tokens", [])}
            pieces = {}
            for token, token_id in model["vocab"].items():
                if token and all(c in "0123456789\u010a" for c in token) and token_id not in added:
                    _require(vocabulary.get(token) == token_id, "backend/native vocabulary disagreement")
                    pieces[token_id] = token.replace("\u010a", "\n")
            proof = "ByteLevel-raw-byte-alphabet-ASCII-concatenativity-with-context-audit"
            backend_hash = hashlib.sha256(backend.to_str().encode()).hexdigest()
        _require(pieces and not set(pieces) & (set(self.eos_ids) | set(tokenizer.all_special_ids)),
                 "special token overlaps grid byte alphabet")
        self.pieces = dict(sorted(pieces.items()))
        # All grids up to 30x30 have a path using these character primitives.
        primitives = {}
        for c in "0123456789\n":
            matches = [token_id for token_id, piece in pieces.items() if piece == c]
            _require(matches, "grid alphabet incomplete: one-character path absent")
            primitives[c] = min(matches)
            _require(_decode(tokenizer, [primitives[c]]) == c, "primitive native decoding differs")
        contexts = [[], [primitives["0"]], [primitives["9"]] * 30,
                    [primitives["0"], primitives["\n"]],
                    [primitives["1"], primitives["2"], primitives["\n"], primitives["3"]],
                    [primitives["8"], primitives["\n"]] * 29 + [primitives["8"]]]
        contextual_checks = 0
        for context in contexts:
            prefix = _decode(tokenizer, context)
            for token_id, piece in self.pieces.items():
                _require(_decode(tokenizer, context + [token_id]) == prefix + piece,
                         "contextual native token decoding is not ASCII-concatenative")
                contextual_checks += 1
        self._allowed_cache = {}
        self.receipt = {"format": "irisx/native-full-grid-constraint-v1", "proof": proof,
                        "tokenizer_sha256": self.tokenizer_sha256, "backend_sha256": backend_hash,
                        "piece_count": len(pieces), "contextual_checks": contextual_checks,
                        "primitive_token_ids": primitives, "native_eos_ids": list(self.eos_ids),
                        "all_rectangles_supported": True, "max_rows": 30, "max_columns": 30,
                        "runtime_contextual_decode": True, "finite_solution_inventory": False,
                        "tiny_cpu": bool(tiny_cpu)}
        self.receipt["constraint_sha256"] = _digest(self.receipt)

    @staticmethod
    def transition(state, text):
        width, rows, column = state
        for char in text:
            if "0" <= char <= "9":
                if column >= (width or 30):
                    return None
                column += 1
            elif char == "\n":
                if column == 0 or rows >= 30 or (width and column != width):
                    return None
                width = width or column
                rows += 1
                column = 0
            else:
                return None
        return width, rows, column

    @staticmethod
    def terminal(state):
        width, rows, column = state
        return column > 0 and (not width or column == width)

    def prefix_state(self, suffix_ids):
        suffix_ids = _ids(suffix_ids)
        state = (0, 1, 0)
        text = ""
        for token_id in suffix_ids:
            _require(token_id in self.pieces, "unexpected/special native grid prefix token")
            piece = self.pieces[token_id]
            state = self.transition(state, piece)
            _require(state is not None, "dead/nonrectangular native grid prefix")
            text += piece
        _require(_decode(self.tokenizer, suffix_ids) == text, "actual contextual native decoding changed")
        return state

    def allowed_tokens(self, suffix_ids):
        state = self.prefix_state(suffix_ids)
        if state not in self._allowed_cache:
            allowed = [token_id for token_id, text in self.pieces.items() if self.transition(state, text) is not None]
            if self.terminal(state):
                allowed.extend(self.eos_ids)
            _require(allowed, "no legal continuation; never substitute EOS")
            self._allowed_cache[state] = tuple(sorted(allowed))
        return list(self._allowed_cache[state])

    def validate_completion(self, output_ids):
        output_ids = _ids(output_ids)
        _require(len(output_ids) >= 2 and output_ids[-1] in self.eos_ids,
                 "complete grid requires an explicit native EOS")
        state = self.prefix_state(output_ids[:-1])
        _require(self.terminal(state), "premature native EOS on incomplete grid")
        text = _decode(self.tokenizer, output_ids[:-1])
        decode_grid(text)
        return text


def audit_tokenizer_assets(path):
    """Hash and exercise staged tokenizer bytes only; never fetch/load weights."""
    from tools.arc_next_models import PINNED_FILES, file_sha256
    root = Path(path)
    names = ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "chat_template.jinja",
             "config.json", "generation_config.json", "vocab.json", "merges.txt")
    for name in names:
        _require(file_sha256(root / name) == PINNED_FILES["granite-4.2-8b"][name],
                 "pinned tokenizer material changed: " + name)
    from transformers import AutoTokenizer
    from tools.arc_public_research_20261010.finite_trie import resolve_native_policy
    tokenizer = AutoTokenizer.from_pretrained(str(root), local_files_only=True, trust_remote_code=False, use_fast=True)
    policy = resolve_native_policy(tokenizer, json.loads((root / "config.json").read_text()),
                                   json.loads((root / "generation_config.json").read_text()))
    constraint = NativeGridConstraint(tokenizer, policy["native_eos_ids"])
    return {**constraint.receipt, "native_policy": policy,
            "authenticated_files": {name: PINNED_FILES["granite-4.2-8b"][name] for name in names},
            "native_vocabulary_rows": max(tokenizer.get_vocab().values()) + 1,
            "model_weights_loaded": False, "gpu_executed": False}


class NativeModel:
    def __init__(self, model, tokenizer, config=None):
        self.config = dict(config or {})
        _require(type(self.config.get("tiny_cpu", False)) is bool, "tiny_cpu must be an exact boolean")
        self.tiny_cpu = self.config.get("tiny_cpu", False)
        self.model, self.tokenizer = model, tokenizer
        self.closed = False
        self._adapter_execution_mode = "trained"
        self._branch_context_active = False
        self.context_limit = self.config.get("context_limit", 8192)
        self.prompt_cap = self.config.get("prompt_cap", 6144)
        self.output_cap = self.config.get("output_cap", 2048)
        for name, value, bound in (("context_limit", self.context_limit, 8192),
                                   ("prompt_cap", self.prompt_cap, 6144), ("output_cap", self.output_cap, 2048)):
            _require(type(value) is int and 0 < value <= bound, "invalid " + name)
        _require(self.prompt_cap < self.context_limit, "prompt must leave completion context")
        vocabulary = tokenizer.get_vocab()
        self.vocab_size = model.get_output_embeddings().weight.shape[0]
        _require(model.get_input_embeddings().weight.shape[0] == self.vocab_size and
                 max(vocabulary.values()) < self.vocab_size, "full native input/output head required")
        if self.tiny_cpu:
            _require(all(p.device.type == "cpu" for p in model.parameters()), "tiny_cpu forbids CUDA weights")
            _require(sum(p.numel() for p in model.parameters()) <= 20_000_000,
                     "tiny_cpu admits at most 20M random test parameters, never 8B weights")
            self.hardware = {"status": "not_run", "reason": "explicit-tiny-cpu-test"}
        else:
            _require(self.vocab_size == 100352, "production retains all 100352 native Granite head rows")
            from tools.arc_next_models import observe_g4_hardware
            import torch
            self.hardware = observe_g4_hardware(torch)
        from tools.arc_public_research_20261010.finite_trie import resolve_native_policy
        from tools.arc_public_research_20261010.model_provider import _effective_generation_config
        self.native_policy = resolve_native_policy(tokenizer, _configuration(model.config),
                    _configuration(_effective_generation_config(model.generation_config)))
        self.eos_ids = tuple(self.native_policy["native_eos_ids"])
        self.constraint = NativeGridConstraint(tokenizer, self.eos_ids, tiny_cpu=self.tiny_cpu)
        self.identity = self.config.get("identity") or {
            "format": "irisx/native-model-identity-v1", "execution_mode": "tiny_cpu" if self.tiny_cpu else "g4",
            "vocab_size": self.vocab_size, "tokenizer_sha256": self.constraint.tokenizer_sha256,
            "random_test_weights": self.tiny_cpu}
        if self.tiny_cpu:
            import torch
            initial = hashlib.sha256()
            for name, tensor in sorted(model.named_parameters(), key=lambda p: p[0]):
                initial.update(_canonical([name, str(tensor.dtype), list(tensor.shape)]))
                initial.update(tensor.detach().cpu().contiguous().view(-1).view(torch.uint8).numpy().tobytes())
            self.identity = {**self.identity, "initial_neural_state_sha256": initial.hexdigest()}
        self.adapter_state_sha256 = None
        self._fingerprint_cache = None
        self.fingerprint_cache_hits = 0
        self.fingerprint_rehashes = 0

    @classmethod
    def from_config(cls, config):
        config = dict(config)
        _require(type(config.get("tiny_cpu", False)) is bool, "tiny_cpu must be an exact boolean")
        if config.get("tiny_cpu", False):
            import torch
            from transformers import AutoTokenizer, GraniteConfig, GraniteForCausalLM
            if config.get("tokenizer_path"):
                tokenizer_root = Path(config["tokenizer_path"])
                _require(tokenizer_root.is_dir(), "tiny tokenizer_path must be a staged local directory")
                if (tokenizer_root / "tiny-byte-tokenizer.json").exists():
                    tokenizer = TinyByteTokenizer.from_pretrained(tokenizer_root)
                else:
                    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_root), local_files_only=True,
                                                             trust_remote_code=False, use_fast=True)
            else:
                tokenizer = TinyByteTokenizer()
            vocab = max(tokenizer.get_vocab().values()) + 1
            hidden = config.get("tiny_hidden_size", 16)
            _require(type(hidden) is int and hidden in (8, 16, 32), "bounded tiny hidden size required")
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(config.get("seed", 0))
                model = GraniteForCausalLM(GraniteConfig(
                    vocab_size=vocab, hidden_size=hidden, intermediate_size=hidden * 2,
                    num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1,
                    max_position_embeddings=8192, eos_token_id=tokenizer.eos_token_id,
                    pad_token_id=tokenizer.pad_token_id, bos_token_id=tokenizer.bos_token_id,
                    attention_dropout=0.0, tie_word_embeddings=False))
            return cls(model.cpu(), tokenizer, config)
        _require(config.get("enabled") is True, "production model loading is default-inert; enabled=True required")
        _require(config.get("model_key", "granite-4.2-8b") == "granite-4.2-8b", "only pinned Granite production route admitted")
        _require(config.get("model_path") and config.get("environment_lock_path"), "local pinned model and environment lock paths required")
        from tools.arc_next_models import load_candidate, observe_g4_hardware
        import torch
        # Gate before any production weight loading, not just before model.to().
        observe_g4_hardware(torch)
        session = load_candidate(config["model_path"], "granite-4.2-8b",
                                 manifest_path=config.get("model_manifest_path"),
                                 environment_lock_path=config["environment_lock_path"], device="cuda:0",
                                 adapter_path=config.get("adapter_path"))
        return cls(session.model, session.tokenizer, {**config, "identity": session.identity})

    def _open(self):
        _require(not self.closed and self.model is not None, "native model is closed")

    def adapter_fingerprint(self):
        """Version-bound current-state fingerprint for serialized train/infer use.

        Authorized training uses optimizer/load_state_dict/no_grad copy_ writes,
        never untracked .data mutation. Every such write changes Tensor._version;
        wrapping, tensor replacement, dtype/device, and trainability also alter
        this cache key. No model-output cache is present. The training-provided
        adapter_state_sha256 is recorded separately and never trusted as this
        tensor fingerprint. Concurrent mutation during inference is unsupported.
        """
        self._open()
        if getattr(self, "_adapter_execution_mode", "trained") == "base":
            # The exact frozen base identity is admitted by the native loader.
            # Disabled LoRA tensors must not be misreported as active weights.
            self._last_fingerprint_cache_hit = False
            return _digest({"identity": self.identity, "execution_mode": "base-adapter-disabled"}), 0
        parameters = [(name, tensor) for name, tensor in sorted(self.model.named_parameters(), key=lambda p: p[0])
                      if tensor.requires_grad or "lora_" in name or "modules_to_save" in name]
        signature = (id(self.model), _digest(self.identity), tuple(
            (name, id(tensor), tensor.data_ptr(), tensor._version, tuple(tensor.shape),
             str(tensor.dtype), str(tensor.device), tensor.requires_grad) for name, tensor in parameters))
        if self._fingerprint_cache is not None and self._fingerprint_cache[0] == signature:
            self.fingerprint_cache_hits += 1
            self._last_fingerprint_cache_hit = True
            return self._fingerprint_cache[1:]
        import torch
        hasher = hashlib.sha256(_canonical(self.identity))
        count = 0
        for name, tensor in parameters:
            hasher.update(_canonical([name, str(tensor.dtype), list(tensor.shape)]))
            hasher.update(tensor.detach().cpu().contiguous().view(-1).view(torch.uint8).numpy().tobytes())
            count += tensor.numel()
        result = hasher.hexdigest(), count
        self._fingerprint_cache = (signature, *result)
        self.fingerprint_rehashes += 1
        self._last_fingerprint_cache_hit = False
        return result

    @contextmanager
    def adapter_branch(self, mode):
        """Temporarily execute the frozen base without changing learned state.

        PEFT's scoped disable operation does not load weights, clear Adam,
        mutate gradients, or restore another task's adapter. Branch identity is
        explicit in every model receipt. Nested/concurrent scopes fail closed.
        """
        self._open()
        _require(mode in {"trained", "base"}, "unknown adapter execution branch")
        _require(not self._branch_context_active, "nested adapter branch forbidden")
        self._branch_context_active = True
        previous = self._adapter_execution_mode
        try:
            if mode == "base":
                _require(bool(getattr(self.model, "peft_config", None)) and
                         callable(getattr(self.model, "disable_adapter", None)),
                         "base branch requires a verified PEFT disable context")
                with self.model.disable_adapter():
                    self._adapter_execution_mode = "base"
                    yield self
            else:
                self._adapter_execution_mode = "trained"
                yield self
        finally:
            self._adapter_execution_mode = previous
            self._branch_context_active = False

    def _prompt(self, messages):
        self._open()
        _require(type(messages) is list and bool(messages) and len(messages) <= 202,
                 "bounded chat messages required")
        for message in messages:
            _require(type(message) is dict and set(message) == {"role", "content"} and
                     message["role"] in {"system", "user", "assistant"} and type(message["content"]) is str,
                     "exact chat role/content messages required")
        _require(messages[-1]["role"] == "user", "generation/scoring prompt must end in a user turn")
        _require(len(_canonical(messages)) <= 262144, "prompt byte cap exceeded")
        rendered = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                                        enable_thinking=False)
        _require(type(rendered) is str and bool(rendered), "native rendered generation prompt required")
        ids = _encode(self.tokenizer, rendered)
        _require(ids and max(ids) < self.vocab_size, "native prompt token outside model vocabulary")
        if len(ids) > self.prompt_cap or len(ids) >= self.context_limit:
            raise ContextLimitError("prompt_context_excluded: whole prompt exceeds cap")
        return rendered, ids

    def prepare_completion(self, messages, completion):
        """Exact shared training/scoring token mask, including one native EOS.

        Completion uses generation's token boundary. Re-encoding the joined text
        must preserve all prompt IDs; a boundary merge is rejected, never guessed.
        A canonical tokenizer EOS terminates supervision (native config may admit
        additional EOS alternatives for generation). No trailing chat newline is
        supervised and no target token is lost to a second shift.
        """
        rendered, prompt = self._prompt(messages)
        _require(type(completion) is str and completion and len(completion.encode()) <= 32768,
                 "bounded nonempty completion required")
        joined = _encode(self.tokenizer, rendered + completion)
        _require(joined[:len(prompt)] == prompt and len(joined) > len(prompt),
                 "native tokenizer boundary merge: completion does not preserve prompt IDs")
        suffix = joined[len(prompt):]
        _require(not set(suffix) & set(self.tokenizer.all_special_ids), "completion text contains native special tokens")
        _require(_decode(self.tokenizer, suffix) == completion,
                 "completion native tokens do not contextually reproduce requested text")
        eos = self.tokenizer.eos_token_id
        _require(type(eos) is int and eos in self.eos_ids, "canonical scalar native EOS required")
        suffix = suffix + [eos]
        ids = prompt + suffix
        if len(ids) > self.context_limit or len(suffix) > self.output_cap:
            raise ContextLimitError("completion_context_excluded: no partial/truncated training or scoring")
        return {"input_ids": ids, "attention_mask": [1] * len(ids),
                "labels": [-100] * len(prompt) + suffix, "prompt_tokens": len(prompt),
                "completion_tokens": len(suffix), "input_tokens": len(ids),
                "prompt_sha256": _digest(prompt), "native_eos_id": eos,
                "completion_rendering_policy": "native-generation-prefix-plus-content-plus-native-EOS"}

    def _base_receipt(self, start):
        from tools.arc_public_research_20261010.finite_trie import resolve_native_policy
        from tools.arc_public_research_20261010.model_provider import _effective_generation_config
        current_policy = resolve_native_policy(self.tokenizer, _configuration(self.model.config),
                            _configuration(_effective_generation_config(self.model.generation_config)))
        _require(current_policy == self.native_policy, "native EOS/generation policy changed after admission")
        fingerprint, tensor_count = self.adapter_fingerprint()
        return {"elapsed_seconds": time.monotonic() - start, "valid": False,
                "adapter_execution_mode": getattr(self, "_adapter_execution_mode", "trained"),
                "adapter_fingerprint": fingerprint, "adapter_fingerprint_tensor_elements": tensor_count,
                "adapter_fingerprint_cache_hit": self._last_fingerprint_cache_hit,
                "fingerprint_cache_hits": self.fingerprint_cache_hits,
                "fingerprint_rehashes": self.fingerprint_rehashes,
                "adapter_state_sha256": self.adapter_state_sha256,
                "model_identity_sha256": _digest(self.identity),
                "tokenizer_sha256": self.constraint.tokenizer_sha256,
                "native_eos_ids": list(self.eos_ids), "native_policy_sha256": _digest(self.native_policy),
                "full_vocabulary_rows": self.vocab_size, "tiny_cpu": self.tiny_cpu,
                "forward_calls": 0, "forward_input_tokens": 0,
                "dispatched": False, "model_forward_started": False}

    @staticmethod
    def _deadline(deadline):
        _require(type(deadline) in (int, float) and math.isfinite(deadline),
                 "finite absolute time.monotonic deadline required")
        return time.monotonic() < deadline

    def generate(self, messages, *, kind, seed, max_new_tokens, deadline):
        start = time.monotonic()
        receipt = {"text": "", "input_tokens": 0, "output_tokens": 0, "output_token_ids": [],
                   "prompt_sha256": None, "finish_reason": "rejected", "elapsed_seconds": 0.0, "valid": False,
                   "forward_calls": 0, "forward_input_tokens": 0,
                "dispatched": False, "model_forward_started": False}
        old_training = None
        try:
            self._open()
            receipt.update(self._base_receipt(start))
            _require(kind in {"grid", "program"}, "generation kind must be grid or program")
            _require(type(seed) is int and 0 <= seed < 2**63, "bounded integer sampling seed required")
            _require(type(max_new_tokens) is int and 0 < max_new_tokens <= self.output_cap,
                     "requested output token cap exceeds admitted bound")
            if not self._deadline(deadline):
                receipt.update(finish_reason="deadline", error="deadline expired before admission")
                return receipt
            rendered, prompt = self._prompt(messages)
            receipt.update(input_tokens=len(prompt), prompt_sha256=_digest(prompt),
                           rendered_prompt_sha256=hashlib.sha256(rendered.encode()).hexdigest(), seed=seed,
                           decoding_mode="native-rectangular-grid-DFA" if kind == "grid" else "unconstrained-native-program-text",
                           constraint_sha256=self.constraint.receipt["constraint_sha256"] if kind == "grid" else None)
            if len(prompt) + max_new_tokens > self.context_limit:
                raise ContextLimitError("prompt plus reserved output exceeds context cap")
            import torch
            device = next(self.model.parameters()).device
            generator = torch.Generator(device=device).manual_seed(seed)
            do_sample = self.config.get("do_sample", True)
            temperature = self.config.get("temperature", 1.0)
            top_p = self.config.get("top_p", 1.0)
            _require(type(do_sample) is bool and type(temperature) in (int, float) and math.isfinite(temperature)
                     and temperature > 0 and type(top_p) in (int, float) and 0 < top_p <= 1,
                     "invalid sampling configuration")
            receipt["sampling"] = {"do_sample": do_sample, "temperature": temperature, "top_p": top_p}
            old_training = self.model.training
            self.model.eval()
            sequence = list(prompt)
            past = None
            with torch.inference_mode():
                for _ in range(max_new_tokens):
                    if not self._deadline(deadline):
                        receipt.update(finish_reason="deadline", error="generation deadline reached")
                        break
                    suffix = receipt["output_token_ids"]
                    allowed = self.constraint.allowed_tokens(suffix) if kind == "grid" else None
                    forward_ids = sequence if past is None else sequence[-1:]
                    inputs = torch.tensor([forward_ids], dtype=torch.long, device=device)
                    mask = torch.ones((1, len(sequence)), dtype=torch.long, device=device)
                    receipt["dispatched"] = receipt["model_forward_started"] = True
                    receipt["forward_calls"] += 1
                    receipt["forward_input_tokens"] += len(forward_ids)
                    result = self.model(input_ids=inputs, attention_mask=mask, past_key_values=past,
                                        use_cache=True, logits_to_keep=1)
                    logits = result.logits[0, -1].float()
                    _require(logits.numel() == self.vocab_size and bool(torch.isfinite(logits).all()),
                             "native full-head logits missing/nonfinite")
                    past = getattr(result, "past_key_values", None)
                    if allowed is not None:
                        selected = torch.tensor(allowed, dtype=torch.long, device=device)
                        logits = logits.index_select(0, selected)
                    else:
                        selected = torch.arange(self.vocab_size, device=device)
                    # Deadline includes forward completion; no later token gets accepted.
                    if not self._deadline(deadline):
                        receipt.update(finish_reason="deadline", error="forward completed after generation deadline")
                        break
                    if do_sample:
                        probabilities = torch.softmax(logits / temperature, dim=-1)
                        if top_p < 1:
                            sorted_p, positions = probabilities.sort(descending=True)
                            keep = sorted_p.cumsum(-1) - sorted_p < top_p
                            sorted_p = sorted_p * keep
                            sampled = positions[torch.multinomial(sorted_p / sorted_p.sum(), 1, generator=generator)[0]]
                        else:
                            sampled = torch.multinomial(probabilities, 1, generator=generator)[0]
                        token_id = int(selected[sampled].item())
                    else:
                        token_id = int(selected[logits.argmax()].item())
                    suffix.append(token_id)
                    sequence.append(token_id)
                    receipt["output_tokens"] = len(suffix)
                    if token_id in self.eos_ids:
                        receipt["finish_reason"] = "eos"
                        break
                    if kind == "grid":
                        self.constraint.prefix_state(suffix)
                else:
                    receipt["finish_reason"] = "length"
            ids = receipt["output_token_ids"]
            content = ids[:-1] if ids and ids[-1] in self.eos_ids else ids
            receipt["text"] = _decode(self.tokenizer, content)
            receipt["output_sha256"] = _digest(ids)
            if receipt["finish_reason"] == "eos":
                if kind == "grid":
                    receipt["text"] = self.constraint.validate_completion(ids)
                _require(bool(receipt["text"]), "empty native completion")
                if not self._deadline(deadline):
                    receipt.update(finish_reason="deadline", error="generation validation completed after deadline")
                else:
                    receipt["valid"] = True
            else:
                receipt.setdefault("error", "native completion lacks terminal EOS")
        except Exception as exc:
            receipt.update(valid=False, error=type(exc).__name__ + ": " + str(exc)[:512])
            if isinstance(exc, ContextLimitError):
                receipt["finish_reason"] = "context_excluded"
            else:
                receipt["finish_reason"] = "error"
        finally:
            if old_training is not None:
                self.model.train(old_training)
            receipt["elapsed_seconds"] = time.monotonic() - start
        return receipt

    def score_completion(self, messages, completion, *, deadline):
        start = time.monotonic()
        receipt = {"nll_sum": None, "token_count": 0, "mean_nll": None, "input_tokens": 0,
                   "elapsed_seconds": 0.0, "valid": False, "output_tokens": 0, "forward_calls": 0, "forward_input_tokens": 0,
                "dispatched": False, "model_forward_started": False}
        old_training = None
        try:
            self._open()
            receipt.update(self._base_receipt(start))
            if not self._deadline(deadline):
                receipt["error"] = "deadline expired before scoring admission"
                return receipt
            prepared = self.prepare_completion(messages, completion)
            # EOS is a target, not an unnecessary final forward input.
            forward_ids = prepared["input_ids"][:-1]
            receipt.update(input_tokens=len(forward_ids), token_count=prepared["completion_tokens"],
                           prompt_tokens=prepared["prompt_tokens"], completion_tokens=prepared["completion_tokens"], prompt_sha256=prepared["prompt_sha256"],
                           completion_token_ids=prepared["input_ids"][prepared["prompt_tokens"]:],
                           completion_sha256=hashlib.sha256(completion.encode()).hexdigest(),
                           scoring_policy="full-native-head-shifted-completion-including-EOS")
            if not self._deadline(deadline):
                receipt["error"] = "deadline expired before scoring forward"
                return receipt
            import torch
            import torch.nn.functional as F
            device = next(self.model.parameters()).device
            inputs = torch.tensor([forward_ids], dtype=torch.long, device=device)
            old_training = self.model.training
            self.model.eval()
            with torch.inference_mode():
                receipt["dispatched"] = receipt["model_forward_started"] = True
                receipt["forward_calls"] = 1
                receipt["forward_input_tokens"] = len(forward_ids)
                result = self.model(input_ids=inputs, attention_mask=torch.ones_like(inputs), use_cache=False,
                                    logits_to_keep=prepared["completion_tokens"])
                logits = result.logits[0]
                _require(logits.shape == (prepared["completion_tokens"], self.vocab_size),
                         "completion shift/full-vocabulary shape mismatch")
                targets = torch.tensor(receipt["completion_token_ids"], dtype=torch.long, device=device)
                # Float32 log-softmax over every native head row, chunked by time only.
                loss = 0.0
                for begin in range(0, len(targets), 64):
                    block = logits[begin:begin + 64].float()
                    loss += float(F.cross_entropy(block, targets[begin:begin + 64], reduction="sum").item())
            _require(math.isfinite(loss), "nonfinite full-vocabulary NLL")
            if not self._deadline(deadline):
                receipt["error"] = "scoring forward completed after deadline"
                return receipt
            receipt.update(nll_sum=loss, mean_nll=loss / len(targets), valid=True)
        except Exception as exc:
            receipt.update(valid=False, error=type(exc).__name__ + ": " + str(exc)[:512])
        finally:
            if old_training is not None:
                self.model.train(old_training)
            receipt["elapsed_seconds"] = time.monotonic() - start
        return receipt

    def close(self):
        self.model = None
        self.tokenizer = None
        self.constraint = None
        self.closed = True
