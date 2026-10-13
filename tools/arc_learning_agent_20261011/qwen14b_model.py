"""Qwen3 native production-interface backend, with an explicit tiny CPU route.

The Granite NativeModel is inherited for its generation/full-head loss/state
protocol, never constructed in non-Granite mode. Its 100352 production guard
and its own factory remain unchanged. No pretrained Qwen weights are admitted.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import time

from .native_model import NativeModel, NativeGridConstraint, NativeModelError, ContextLimitError, _canonical, _digest, _require
from .qwen14b_profiles import MODEL_KEY, MODEL_ID, REVISION, PROFILE_ID, VOCAB_SIZE, EOS_IDS, authenticate_small_assets, require_pretrained_admission


class Qwen14BModel(NativeModel):
    def __init__(self, model, tokenizer, config=None):
        config = dict(config or {})
        _require(config.get('model_key') == MODEL_KEY, 'exact distinct Qwen14B key required')
        _require(type(config.get('tiny_cpu')) is bool, 'explicit tiny_cpu boolean required')
        if not config['tiny_cpu']:
            require_pretrained_admission(config)
            from .qwen14b_admission import consume_load_evidence
            _loaded = consume_load_evidence(model, tokenizer, config)
        _require(config.get('precision', 'bf16-base-fp32-lora') == 'bf16-base-fp32-lora', 'Qwen14B BF16-base/FP32-LoRA only; no FP8 fallback')
        _require(type(config.get('tensor_parallel_size', 1)) is int and config.get('tensor_parallel_size', 1) == 1, 'Qwen14B tensor parallelism not admitted')
        _require(type(model).__name__ == 'Qwen3ForCausalLM', 'actual native Qwen3ForCausalLM required')
        if config['tiny_cpu']:
            _require(all(p.device.type == 'cpu' for p in model.parameters()), 'tiny Qwen3 fixture is CPU only')
            _require(sum(p.numel() for p in model.parameters()) <= 10_000_000, 'tiny Qwen3 fixture exceeds 10M parameters')
        self.config = config
        self.model, self.tokenizer = model, tokenizer
        self.tiny_cpu, self.closed = config['tiny_cpu'], False
        self._adapter_execution_mode, self._branch_context_active = 'trained', False
        self.context_limit = config.get('context_limit', 2048)
        self.prompt_cap = config.get('prompt_cap', min(1792, self.context_limit - 1))
        self.output_cap = config.get('output_cap', min(256, self.context_limit - 1))
        for name, value, maximum in [('context_limit', self.context_limit, 2048), ('prompt_cap', self.prompt_cap, 1792), ('output_cap', self.output_cap, 256)]:
            _require(type(value) is int and 0 < value <= maximum, 'invalid Qwen14B ' + name)
        _require(self.prompt_cap < self.context_limit and self.output_cap < self.context_limit, 'prompt/output must leave context')
        self.vocab_size = model.get_output_embeddings().weight.shape[0]
        _require(self.vocab_size == VOCAB_SIZE and model.get_input_embeddings().weight.shape[0] == VOCAB_SIZE,
                 'Qwen14B retains all 151936 native input/output rows')
        _require(model.config.model_type == 'qwen3' and model.config.num_hidden_layers in ((1, 2) if self.tiny_cpu else (40,)), 'bounded native Qwen3 tiny topology required')
        import torch
        _require(all(p.dtype == torch.bfloat16 for p in model.parameters()), 'genuine BF16 random base required')
        from .qwen14b_contract import NativePromptContract
        self.prompt_contract = NativePromptContract(tokenizer, vocab_size=self.vocab_size, eos_ids=EOS_IDS,
                                                    context_limit=self.context_limit, output_cap=self.output_cap)
        self._tokenizer_backend_sha256 = hashlib.sha256(tokenizer.backend_tokenizer.to_str().encode()).hexdigest()
        self.native_policy = self._current_policy()
        self.eos_ids = tuple(self.native_policy['generation_eos_ids'])
        self.constraint = NativeGridConstraint(tokenizer, self.eos_ids, tiny_cpu=self.tiny_cpu)
        initial = hashlib.sha256()
        for name, tensor in (sorted(model.named_parameters()) if self.tiny_cpu else []):
            initial.update(_canonical([name, str(tensor.dtype), list(tensor.shape)]))
            initial.update(tensor.detach().cpu().contiguous().view(-1).view(torch.uint8).numpy().tobytes())
        self.identity = {'format': 'irisx/qwen14b-native-interface-v1', 'model_key': MODEL_KEY,
                         'architecture': 'Qwen3ForCausalLM', 'reference_model_id': MODEL_ID, 'reference_revision': REVISION,
                         'profile_id': PROFILE_ID, 'execution_mode': 'native-qwen3-tiny-random-cpu',
                         'random_test_weights': True, 'pretrained_weights_loaded': False, 'production_admitted': False,
                         'full_vocabulary_rows': self.vocab_size, 'actual_hidden_size': model.config.hidden_size,
                         'actual_layers': model.config.num_hidden_layers, 'base_precision': 'bfloat16',
                         'initial_neural_state_sha256': initial.hexdigest(), 'tokenizer_backend_sha256': self._tokenizer_backend_sha256, 'prompt_contract_sha256': self.prompt_contract.contract_sha256,
                         'small_asset_identity': deepcopy(config.get('small_asset_identity'))}
        self.hardware = {'status': 'cpu-fixture-only', 'g4_fit_measured': False, 'four_l4_tp_admitted': False, 'fp8_admitted': False}
        if not self.tiny_cpu:
            self.identity, self.hardware = deepcopy(_loaded)
            self.identity['tokenizer_backend_sha256'] = self._tokenizer_backend_sha256
            self.identity['prompt_contract_sha256'] = self.prompt_contract.contract_sha256
        self.adapter_state_sha256 = None
        self._fingerprint_cache = None
        self.fingerprint_cache_hits = self.fingerprint_rehashes = 0

    @classmethod
    def from_config(cls, config):
        config = dict(config)
        _require(config.get('model_key') == MODEL_KEY, 'exact Qwen14B model key required')
        _require(type(config.get('tiny_cpu', False)) is bool, 'exact tiny_cpu boolean required')
        if not config.get('tiny_cpu', False):
            from .qwen14b_admission import load_reviewed_pretrained
            model, tokenizer, identity, hardware = load_reviewed_pretrained(config)
            return cls(model, tokenizer, {**config, 'tiny_cpu': False})
        _require(config.get('tokenizer_path'), 'authenticated local Qwen14B tokenizer path required')
        assets = authenticate_small_assets(config['tokenizer_path'])
        hidden = config.get('tiny_hidden_size', 16)
        _require(type(hidden) is int and hidden in (8, 16), 'tiny hidden size must be 8 or 16')
        _require(type(config.get('seed', 0)) is int and 0 <= config.get('seed', 0) < 2**63, 'bounded integer fixture seed required')
        import torch
        from transformers import AutoTokenizer, Qwen3Config, Qwen3ForCausalLM
        tokenizer = AutoTokenizer.from_pretrained(config['tokenizer_path'], local_files_only=True, trust_remote_code=False, use_fast=True)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(config.get('seed', 0))
            model = Qwen3ForCausalLM(Qwen3Config(vocab_size=VOCAB_SIZE, hidden_size=hidden,
                intermediate_size=hidden * 2, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1,
                head_dim=hidden // 2, max_position_embeddings=2048, eos_token_id=151645,
                pad_token_id=151643, bos_token_id=151643, attention_dropout=0.0, tie_word_embeddings=False))
            model = model.to(device='cpu', dtype=torch.bfloat16)
        model.generation_config.eos_token_id = list(EOS_IDS)
        model.generation_config.pad_token_id = 151643
        return cls(model, tokenizer, {**config, 'small_asset_identity': assets})

    def _current_policy(self):
        from .qwen14b_contract import resolve_native_eos_policy
        policy = resolve_native_eos_policy(self.tokenizer, self.model.config.to_dict(),
                    self.model.generation_config.to_dict(), expected_ids=list(EOS_IDS))
        _require(self.tokenizer.pad_token_id == 151643 and self.model.generation_config.pad_token_id == 151643,
                 'Qwen14B native pad identity changed')
        return policy

    def _assert_tokenizer_backend(self):
        recipe_guard=getattr(self,'_adapter_recipe_guard',None)
        if recipe_guard is not None:
            recipe_guard()
        _require(hashlib.sha256(self.tokenizer.backend_tokenizer.to_str().encode()).hexdigest() == self._tokenizer_backend_sha256,
                 'native tokenizer backend/normalizer/decoder changed after admission')

    def adapter_fingerprint(self):
        recipe_guard=getattr(self,'_adapter_recipe_guard',None)
        if recipe_guard is not None:
            recipe_guard()
        return super().adapter_fingerprint()

    def _prompt(self, messages):
        self._open()
        self._assert_tokenizer_backend()
        try:
            rendered, ids = self.prompt_contract.prompt(messages)
        except ValueError as exc:
            if 'context' in str(exc):
                raise ContextLimitError('prompt_context_excluded: ' + str(exc)) from exc
            raise
        if len(ids) > self.prompt_cap:
            raise ContextLimitError('prompt_context_excluded: whole Qwen14B prompt exceeds cap')
        return rendered, ids

    def prepare_completion(self, messages, completion):
        self._open()
        self._assert_tokenizer_backend()
        try:
            native = self.prompt_contract.prepare_completion(messages, completion)
            if native['prompt_tokens'] > self.prompt_cap:
                raise ContextLimitError('prompt_context_excluded: whole Qwen14B prompt exceeds cap')
        except ValueError as exc:
            if 'context' in str(exc):
                raise ContextLimitError('completion_context_excluded: ' + str(exc)) from exc
            raise
        return {**native, 'attention_mask': [1] * len(native['input_ids']),
                'completion_tokens': native['supervised_tokens'], 'native_eos_id': self.tokenizer.eos_token_id,
                'completion_rendering_policy': 'exact-native-completed-chat-no-content-normalization'}

    def validate_prepared(self, row):
        keys = self.prompt_contract._PREPARED_KEYS
        _require(type(row) is dict and set(row) == keys | {'attention_mask', 'completion_tokens', 'native_eos_id', 'completion_rendering_policy'},
                 'Qwen14B prepared example fields changed')
        self._open()
        self._assert_tokenizer_backend()
        native = self.prompt_contract.validate_prepared({key: row[key] for key in keys})
        _require(native['prompt_tokens'] <= self.prompt_cap, 'prompt context exceeds cap')
        expected = {**native, 'attention_mask': [1] * len(native['input_ids']),
                    'completion_tokens': native['supervised_tokens'], 'native_eos_id': self.tokenizer.eos_token_id,
                    'completion_rendering_policy': 'exact-native-completed-chat-no-content-normalization'}
        _require(_canonical(row) == _canonical(expected), 'Qwen14B prepared labels/counts/content changed')
        return expected

    def _base_receipt(self, start):
        self._open()
        self._assert_tokenizer_backend()
        self.prompt_contract._assert_tokenizer_unchanged()
        _require(self._current_policy() == self.native_policy, 'Qwen14B native EOS policy changed after admission')
        fingerprint, count = self.adapter_fingerprint()
        return {'elapsed_seconds': time.monotonic() - start, 'valid': False,
                'adapter_execution_mode': self._adapter_execution_mode, 'adapter_fingerprint': fingerprint,
                'adapter_fingerprint_tensor_elements': count, 'adapter_fingerprint_cache_hit': self._last_fingerprint_cache_hit,
                'fingerprint_cache_hits': self.fingerprint_cache_hits, 'fingerprint_rehashes': self.fingerprint_rehashes,
                'adapter_state_sha256': self.adapter_state_sha256, 'model_identity_sha256': _digest(self.identity),
                'tokenizer_sha256': self.constraint.tokenizer_sha256, 'native_eos_ids': list(self.eos_ids),
                'native_policy_sha256': _digest(self.native_policy), 'full_vocabulary_rows': self.vocab_size,
                'tiny_cpu': self.tiny_cpu, 'pretrained_weights_loaded': not self.tiny_cpu, 'production_admitted': False,
                'forward_calls': 0, 'forward_input_tokens': 0, 'dispatched': False, 'model_forward_started': False,
                'kv_cache_policy': 'call-local-discarded-after-every-generation',
                'prompt_contract_sha256': self.prompt_contract.contract_sha256}

    def generate(self, messages, *, kind, seed, max_new_tokens, deadline):
        started = time.monotonic()
        receipt = super().generate(messages, kind=kind, seed=seed, max_new_tokens=max_new_tokens, deadline=deadline)
        if receipt['valid'] and kind == 'program':
            try:
                self.prompt_contract._content_ids(receipt['text'])
                content_ids = receipt['output_token_ids'][:-1]
                registered = set(self.tokenizer.get_vocab().values())
                _require(all(token in registered for token in content_ids) and
                         not set(content_ids) & self.prompt_contract._control_ids,
                         'unregistered/reserved native program token IDs')
            except ValueError as exc:
                receipt.update(valid=False, finish_reason='error', error=str(exc))
        receipt['elapsed_seconds'] = time.monotonic() - started
        return receipt

    def close(self):
        self._adapter_recipe_guard = None
        self.prompt_contract = None
        super().close()
