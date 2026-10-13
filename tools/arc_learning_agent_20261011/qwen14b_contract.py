"""Mechanical reviewed subset. Upstream SHA256: deb101d2627043f53d1f84c07ef75158d025cb77b8aecbe1173ba8c9985af95a."""
from __future__ import annotations


from dataclasses import dataclass


from contextlib import contextmanager


import hashlib


import importlib.metadata


import json


import math


import os


from pathlib import Path


import re


import struct


import time


class ContractError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ContractError(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


EXPECTED_ENVIRONMENT = {
    'torch': '2.8.0+cu128', 'transformers': '5.8.1', 'tokenizers': '0.22.2',
    'huggingface-hub': '1.32.0', 'safetensors': '0.8.0', 'accelerate': '1.10.1', 'peft': '0.21.0',
}


CANDIDATES = {
    'qwen3.5-27b': ('Qwen/Qwen3.5-27B', 'Qwen3_5ForConditionalGeneration', 'qwen3_5', 248320, 64, 5120),
    'qwen3-14b': ('Qwen/Qwen3-14B', 'Qwen3ForCausalLM', 'qwen3', 151936, 40, 5120),
    'qwen3.5-9b': ('Qwen/Qwen3.5-9B', 'Qwen3_5ForConditionalGeneration', 'qwen3_5', 248320, 32, 4096),
}


@dataclass(frozen=True)
class ReviewedAdmission:
    """Values must come from an independent exact-byte review, never self-attestation.

    No such admission is shipped for 27B/14B. This object is a data contract, not
    permission to publish, download or run. Runtime authorization is separate.
    """
    model_key: str
    revision: str
    manifest_sha256: str
    environment_versions: dict
    backend: str = 'sdpa-and-torch-reference-deltanet'
    precision: str = 'bf16-base-fp32-adapter'
    context_limit: int = 2048
    max_new_tokens: int = 256
    tensor_parallel_size: int = 1

    def validate(self):
        require(self.model_key in CANDIDATES, 'unreviewed model family')
        require(bool(re.fullmatch('[0-9a-f]{40}', self.revision)), 'exact 40-hex source revision required')
        require(bool(re.fullmatch('[0-9a-f]{64}', self.manifest_sha256)), 'independent complete-manifest digest required')
        require(self.environment_versions == EXPECTED_ENVIRONMENT, 'reviewed exact environment required')
        require(self.backend == 'sdpa-and-torch-reference-deltanet', 'unsupported backend; no silent fallback')
        require(self.precision == 'bf16-base-fp32-adapter', 'FP8/quantized training or inference is not admitted')
        require(type(self.context_limit) is int and 1 <= self.context_limit <= 2048, 'bounded prototype context required')
        require(type(self.max_new_tokens) is int and 1 <= self.max_new_tokens < self.context_limit, 'output/context cap invalid')
        require(self.tensor_parallel_size == 1, 'TP/4xL4 is not admitted by this single-GPU prototype')


def _json(path, cap=16 * 1024 * 1024):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= cap, 'bounded regular JSON asset required')
    return json.loads(path.read_text())


def tensor_header(path):
    """Verify bounded native safetensors header and every payload interval."""
    size = Path(path).stat().st_size
    with Path(path).open('rb') as f:
        prefix = f.read(8)
        require(len(prefix) == 8, 'truncated safetensors header')
        n = struct.unpack('<Q', prefix)[0]
        require(1 <= n <= min(64 * 1024 * 1024, size - 8), 'invalid safetensors header size')
        header = json.loads(f.read(n))
    require(type(header) is dict, 'tensor header object required')
    sizes = {'BF16': 2, 'F16': 2, 'F32': 4, 'I64': 8, 'I32': 4, 'BOOL': 1, 'U8': 1}
    inventory, ranges = {}, []
    for name, item in header.items():
        if name == '__metadata__':
            continue
        shape, dtype, offsets = item['shape'], item['dtype'], item['data_offsets']
        require(type(shape) is list and all(type(x) is int and x > 0 for x in shape), 'invalid shape')
        require(dtype in sizes and type(offsets) is list and len(offsets) == 2 and
                all(type(x) is int for x in offsets), 'invalid tensor dtype/offsets')
        count = math.prod(shape)
        require(0 <= offsets[0] < offsets[1] <= size - 8 - n and offsets[1] - offsets[0] == count * sizes[dtype], 'invalid payload span')
        inventory[name] = {'shape': shape, 'dtype': dtype, 'elements': count}
        ranges.append(tuple(offsets))
    cursor = 0
    for start, end in sorted(ranges):
        require(start == cursor, 'overlapping or unaccounted tensor payload')
        cursor = end
    require(inventory and cursor == size - 8 - n, 'incomplete tensor payload')
    return inventory


def validate_local_material(root, manifest_path, admission):
    """Hash all staged bytes against independently pinned manifest before model import.

    The manifest has a closed file inventory, complete shard index, exact config,
    exact template digest, tokenizer IDs and optional exact ignored MTP key list.
    Hashing full weights is intentional. No metadata-only success means load-ready.
    """
    admission.validate()
    root, manifest_path = Path(root).resolve(), Path(manifest_path).resolve()
    require(root.is_dir(), 'local staged model directory required')
    require(sha256(manifest_path) == admission.manifest_sha256, 'manifest digest not independently approved')
    m = _json(manifest_path)
    repo, architecture, model_type, vocab, layers, hidden = CANDIDATES[admission.model_key]
    require(m.get('format') == 'irisx/model-next-material-v1' and
            m.get('repository') == repo and m.get('revision') == admission.revision and
            m.get('model_key') == admission.model_key, 'exact source identity mismatch')
    entries = m.get('files')
    require(type(entries) is dict and 1 <= len(entries) <= 256, 'complete bounded file inventory required')
    for name, item in entries.items():
        rel = Path(name)
        require(not rel.is_absolute() and name and '..' not in rel.parts, 'unsafe material path')
        path = root / rel
        require(path.is_file() and not any(p.is_symlink() for p in [path, *path.parents] if p != root.parent), 'symlinked/nonregular asset denied')
        require(path.stat().st_size == item.get('size_bytes') and sha256(path) == item.get('sha256'), 'asset bytes differ: ' + name)
    require(not any(p.is_symlink() for p in root.rglob('*')), 'unlisted symlink in asset directory')
    observed = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.resolve() != manifest_path}
    require(observed == set(entries), 'unlisted/missing model assets; closed inventory required')
    required = {'config.json', 'generation_config.json', 'tokenizer.json', 'tokenizer_config.json', 'model.safetensors.index.json'}
    require(required <= set(entries), 'incomplete load-bearing asset manifest')
    cfg = _json(root / 'config.json')
    require(cfg.get('architectures') == [architecture] and cfg.get('model_type') == model_type, 'exact native model class/config required')
    require(not cfg.get('auto_map') and not _json(root / 'tokenizer_config.json').get('auto_map'), 'remote-code configurations are unsupported')
    text = cfg.get('text_config', cfg)
    require(text.get('vocab_size') == vocab and text.get('num_hidden_layers') == layers and text.get('hidden_size') == hidden, 'native source dimensions mismatch')
    require(text.get('max_position_embeddings', 0) >= admission.context_limit, 'context exceeds native configuration')
    if model_type == 'qwen3_5':
        require('chat_template.jinja' in entries, 'exact Qwen3.5 native chat template file required')
        require(cfg.get('vision_config') and text.get('layer_types') == [
            'full_attention' if (i + 1) % 4 == 0 else 'linear_attention' for i in range(layers)], 'full conditional hybrid container required')
    index = _json(root / 'model.safetensors.index.json')
    weight_map = index.get('weight_map')
    require(type(weight_map) is dict and weight_map, 'complete tensor-to-shard map required')
    shards = set(weight_map.values())
    require(shards == {n for n in entries if n.endswith('.safetensors')}, 'shard inventory mismatch')
    tensors = {}
    for shard in sorted(shards):
        local = tensor_header(root / shard)
        require(not set(local) & set(tensors), 'duplicate tensor in shards')
        require(set(local) == {n for n, filename in weight_map.items() if filename == shard}, 'index/header exact coverage mismatch')
        tensors.update(local)
    unused = m.get('unused_source_keys', [])
    require(type(unused) is list and len(unused) == len(set(unused)) and set(unused) <= set(tensors), 'invalid exact unused tensor list')
    require(not unused or model_type == 'qwen3_5' and all(n.startswith('mtp.') for n in unused), 'only explicitly inventoried MTP omissions allowed')
    require(all(t['dtype'] in ('BF16', 'F32') for t in tensors.values()), 'non-BF16/F32 source requires separate reviewed conversion')
    require(type(m.get('native_eos_ids')) is list and m['native_eos_ids'] and
            all(type(i) is int and 0 <= i < vocab for i in m['native_eos_ids']) and
            type(m.get('tokenizer_eos_id')) is int and m['tokenizer_eos_id'] in m['native_eos_ids'], 'native EOS policy missing')
    config_eos = text.get('eos_token_id')
    config_eos = [config_eos] if type(config_eos) is int else config_eos
    require(config_eos and set(config_eos) <= set(m['native_eos_ids']), 'native config EOS outside generation stop set')
    require(bool(re.fullmatch('[0-9a-f]{64}', m.get('template_sha256', ''))), 'native template digest missing')
    return m, cfg, tensors


def memory_estimate(config, tensor_inventory, *, sequence_length, adapter_rank=8, batch_size=1):
    """Conservative engineering allowance; NOT measured peak or proof of fit.

    Full-sequence loss/scoring includes logits + float cast + log-softmax/grad
    scratch (12 bytes per token/vocab), not just BF16 output logits.
    """
    t = config.get('text_config', config)
    require(type(sequence_length) is int and 1 <= sequence_length <= 2048 and batch_size == 1, 'only batch1 short-context probe budgeted')
    require(adapter_rank in (4, 8, 16), 'bounded LoRA rank required')
    layers, h, inter, vocab = (t[k] for k in ('num_hidden_layers', 'hidden_size', 'intermediate_size', 'vocab_size'))
    types = t.get('layer_types', ['full_attention'] * layers)
    attn = types.count('full_attention')
    linear = types.count('linear_attention')
    hd = t.get('head_dim', h // t['num_attention_heads'])
    # Full retained conditional container, including unused vision; source-only
    # MTP tensors are excluded by caller only after exact loading-key audit.
    weights = sum(v['elements'] * (4 if v['dtype'] == 'F32' else 2)
                  for n, v in tensor_inventory.items())
    kv = 2 * attn * t['num_key_value_heads'] * hd * sequence_length * 2
    recurrent = linear * (t.get('linear_num_value_heads', 0) * t.get('linear_key_head_dim', 0) * t.get('linear_value_head_dim', 0) * 4)
    conv_dim = 2 * t.get('linear_num_key_heads', 0) * t.get('linear_key_head_dim', 0) + t.get('linear_num_value_heads', 0) * t.get('linear_value_head_dim', 0)
    conv = linear * conv_dim * t.get('linear_conv_kernel_dim', 0) * 4
    # Upper bound over the exact target matrix shapes is computed by the loader;
    # this planner uses per-layer MLP plus full/delta projection dimensions.
    mlp_lora = layers * adapter_rank * 3 * (h + inter)
    q_width = t['num_attention_heads'] * hd * (2 if linear else 1)
    kv_width = t['num_key_value_heads'] * hd
    attn_lora = attn * adapter_rank * (4 * h + 2 * q_width + 2 * kv_width)
    delta_lora = linear * adapter_rank * (5 * h + conv_dim + 2 * t.get('linear_num_value_heads', 0) * t.get('linear_value_head_dim', 0) + 2 * t.get('linear_num_value_heads', 0))
    adapter = (mlp_lora + attn_lora + delta_lora) * 16  # FP32 A/B, grads, Adam m/v
    logits_loss = batch_size * sequence_length * vocab * 12
    # Explicit conservative unmeasured allowance, including full checkpointed
    # hidden states; DeltaNet chunk workspaces still need GPU measurement.
    activation_allowance = layers * sequence_length * h * 2 * 8
    allocator_workspace_reserve = 8 * 2**30
    parts = dict(base_weights_bytes=weights, kv_bytes=kv, recurrent_bytes=recurrent,
                 convolution_bytes=conv, adapter_training_bytes=adapter,
                 full_logits_loss_bytes=logits_loss, activation_allowance_bytes=activation_allowance,
                 allocator_workspace_reserve_bytes=allocator_workspace_reserve)
    return {**parts, 'estimated_required_bytes': sum(parts.values()), 'measured': False,
            'scope': 'BF16 batch1 short-context, FP32 LoRA/Adam; retained full conditional container'}


def resolve_native_eos_policy(tokenizer, model_config, generation_config, *, expected_ids):
    """All sources remain distinct; generation stop set must match reviewed IDs.

    Qwen3.5 canonical chat EOS is248046, while text_config EOS is248044.
    No scalar-equality assumption and no inferred/silent fallback is permitted.
    """
    def normalize(value, source):
        ids = [value] if type(value) is int else value
        require(type(ids) is list and ids and all(type(x) is int and x >= 0 for x in ids)
                and len(set(ids)) == len(ids), 'invalid or ambiguous ' + source + ' EOS IDs')
        return list(ids)
    text = model_config.get('text_config', model_config)
    model_ids = normalize(text.get('eos_token_id'), 'model config')
    generation_ids = normalize(generation_config.get('eos_token_id'), 'generation config')
    reviewed_ids = normalize(expected_ids, 'reviewed')
    require(set(generation_ids) == set(reviewed_ids), 'unexpected native generation EOS set')
    canonical_id = tokenizer.eos_token_id
    require(type(canonical_id) is int and canonical_id in generation_ids and
            set(model_ids) <= set(generation_ids), 'native EOS origin not in reviewed generation set')
    vocabulary = tokenizer.get_vocab()
    registered = set(vocabulary.values())
    require(set(generation_ids) <= registered and set(generation_ids) <= set(tokenizer.all_special_ids),
            'unregistered or non-special native EOS ID')
    spellings = {}
    for token_id in generation_ids:
        spelling = tokenizer.decode([token_id], skip_special_tokens=False, clean_up_tokenization_spaces=False)
        require(spelling and vocabulary.get(spelling) == token_id and
                tokenizer.encode(spelling, add_special_tokens=False) == [token_id], 'ambiguous native EOS terminal mapping')
        spellings[str(token_id)] = spelling
    require(spellings[str(canonical_id)] == tokenizer.eos_token, 'tokenizer EOS spelling disagrees with native mapping')
    return {'tokenizer_canonical_eos_id': canonical_id, 'model_config_eos_ids': model_ids,
            'generation_eos_ids': generation_ids, 'reviewed_eos_ids': reviewed_ids,
            'terminal_spellings': spellings, 'training_terminal_id': canonical_id,
            'fallback_used': False}


class NativePromptContract:
    """Exact native templates and immutable-by-validation prepared examples."""
    _PREPARED_KEYS = {'format', 'contract_sha256', 'messages', 'completion', 'input_ids', 'labels',
                      'supervised_tokens', 'prompt_tokens', 'input_tokens', 'prompt_sha256',
                      'completion_sha256', 'prepared_sha256'}
    _QWEN_FRAMING = ('<|im_start|>', '<|im_end|>', '<|endoftext|>', '<think>', '</think>')

    _WRAPPER_SETTINGS = ('model_max_length', 'padding_side', 'truncation_side', 'model_input_names',
        'clean_up_tokenization_spaces', 'clean_up_tokenization_spaces_for_bpe_even_though_it_will_corrupt_output',
        'split_special_tokens', 'add_prefix_space', 'add_bos_token', 'add_eos_token',
        'pad_token_type_id', 'do_lower_case', 'errors')

    def __init__(self, tokenizer, *, vocab_size, eos_ids, context_limit=2048, output_cap=256,
                 synthetic=False):
        require(type(synthetic) is bool, 'explicit boolean synthetic-tokenizer policy required')
        require(type(vocab_size) is int and vocab_size > 0, 'native full vocabulary size required')
        require(type(context_limit) is int and 1 <= context_limit <= 2048 and
                type(output_cap) is int and 0 < output_cap < context_limit, 'bounded prompt/output policy required')
        require(type(eos_ids) in (list, tuple) and eos_ids and
                all(type(i) is int and 0 <= i < vocab_size for i in eos_ids) and
                len(set(eos_ids)) == len(eos_ids), 'native EOS ID set required')
        self._native_vocab_getter = None
        if not synthetic:
            from transformers.tokenization_utils_tokenizers import TokenizersBackend
            getter = tokenizer.get_vocab
            require(getattr(getter, '__func__', None) is TokenizersBackend.get_vocab and
                    getattr(getter, '__self__', None) is tokenizer,
                    'exact owned native fast-tokenizer vocabulary getter required')
            self._native_vocab_getter = getter.__func__
        vocabulary = tokenizer.get_vocab()
        require(type(vocabulary) is dict and vocabulary and
                all(type(k) is str and type(v) is int and 0 <= v < vocab_size for k, v in vocabulary.items()),
                'native tokenizer IDs must agree with full source output head')
        require(type(tokenizer.eos_token_id) is int and tokenizer.eos_token_id in eos_ids and
                type(tokenizer.eos_token) is str and vocabulary.get(tokenizer.eos_token) == tokenizer.eos_token_id,
                'canonical EOS spelling/mapping required')
        self.tokenizer, self.vocab_size, self.eos_ids = tokenizer, vocab_size, tuple(eos_ids)
        self._synthetic_tokenizer = synthetic
        self.context_limit, self.output_cap = context_limit, output_cap
        self._pipeline_sha256 = self._tokenizer_pipeline_sha256()
        self._vocabulary_sha256 = hashlib.sha256(canonical(vocabulary)).hexdigest()
        if not synthetic:
            state = json.loads(tokenizer.backend_tokenizer.to_str())
            require(state['model']['type'] == 'BPE' and type(state['model']['vocab']) is dict and
                    type(state['added_tokens']) is list, 'reviewed native BPE vocabulary representation required')
            represented = dict(state['model']['vocab'])
            for token in state['added_tokens']:
                require(token['content'] not in represented or represented[token['content']] == token['id'],
                        'conflicting native backend vocabulary/added-token mapping')
                represented[token['content']] = token['id']
            require(represented == vocabulary, 'serialized native backend does not exactly represent get_vocab')
            self.vocabulary_derivation = {'verified': True, 'entries': len(represented),
                'policy': 'serialized-BPE-plus-added-tokens-equals-owned-inherited-get_vocab'}
        else:
            self.vocabulary_derivation = {'verified': False, 'policy': 'synthetic-full-map-check-at-each-boundary'}
        self._template_sha256 = hashlib.sha256(self._native_template().encode()).hexdigest()
        self._canonical_eos_id = tokenizer.eos_token_id
        self._canonical_eos_token = tokenizer.eos_token
        self._special_ids = tuple(sorted(tokenizer.all_special_ids))
        added = tokenizer.get_added_vocab() if hasattr(tokenizer, 'get_added_vocab') else {}
        control_ids = set(self._special_ids)
        control_ids.update(v for k, v in added.items() if k.startswith('<') and k.endswith('>'))
        self._control_ids = frozenset(control_ids)
        self._control_spellings = tuple(sorted(set(self._QWEN_FRAMING) |
            {k for k, v in vocabulary.items() if v in control_ids}))
        self._prepared_cache = {}  # at most8 immutable canonical byte records; never caller-owned lists
        self.prepared_cache_hits = 0
        self.contract_sha256 = hashlib.sha256(canonical({
            'format': 'irisx/model-next-prompt-contract-v3', 'vocabulary_sha256': self._vocabulary_sha256,
            'tokenizer_pipeline_sha256': self._pipeline_sha256, 'synthetic_tokenizer': synthetic,
            'vocabulary_derivation': self.vocabulary_derivation,
            'template_sha256': self._template_sha256, 'canonical_eos_id': self._canonical_eos_id,
            'generation_eos_ids': list(self.eos_ids), 'control_spellings': self._control_spellings,
            'full_vocabulary_size': vocab_size, 'context_limit': context_limit, 'output_cap': output_cap,
            'thinking': False, 'completion_policy': 'exact-native-completed-chat-no-content-normalization'
        })).hexdigest()

    def _native_template(self):
        value = self.tokenizer.get_chat_template() if hasattr(self.tokenizer, 'get_chat_template') else self.tokenizer.chat_template
        require(type(value) is str and value, 'exact native template required')
        return value

    def _tokenizer_pipeline_sha256(self):
        """Hash full Rust pipeline and live wrapper policy at operation boundaries.

        to_str includes normalizer, pre-tokenizer, model/merges, added-token flags,
        postprocessor, decoder, padding and truncation. encode_special_tokens is
        a separate Rust flag, so bind it explicitly. No mutable serialization
        cache is allowed. This is not a guard against arbitrary Python code
        replacement or concurrent mutation; each contract is single-owner.
        """
        tok = self.tokenizer
        backend = getattr(tok, 'backend_tokenizer', None)
        if self._synthetic_tokenizer:
            require(backend is None, 'synthetic fixture must not impersonate a native backend')
            backend_state = {'kind': 'explicit-synthetic-fixture-no-native-backend'}
        else:
            from tokenizers import Tokenizer
            require(type(backend) is Tokenizer, 'exact native fast-tokenizer backend required')
            raw = backend.to_str()
            require(type(raw) is str and 0 < len(raw.encode()) <= 32 * 1024 * 1024,
                    'bounded complete tokenizer backend serialization required')
            backend_state = {'kind': 'tokenizers.Tokenizer',
                'serialized_backend_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                'encode_special_tokens': backend.encode_special_tokens}
        settings = {name: getattr(tok, name) for name in self._WRAPPER_SETTINGS if hasattr(tok, name)}
        # Special-token aliases affect template rendering even with identical
        # registered vocabulary IDs. Their AddedToken flags live in the backend.
        special_map = getattr(tok, 'special_tokens_map', {})
        def strings(value):
            if isinstance(value, (list, tuple)):
                return [strings(x) for x in value]
            return str(value) if value is not None else None
        settings['special_tokens_map'] = {k: strings(v) for k, v in special_map.items()}
        identity = {'class': type(tok).__module__ + '.' + type(tok).__qualname__,
                    'backend': backend_state, 'wrapper_settings': settings}
        return hashlib.sha256(canonical(identity)).hexdigest()

    def _assert_tokenizer_unchanged(self):
        getter = self.tokenizer.get_vocab
        # Exact inherited get_vocab delegates only to this same native Rust
        # backend. Constructor equality proves the complete serialized mapping;
        # unchanged full serialization proves that mapping at every boundary.
        # Keep ownership checks: another tokenizer's identical method is invalid.
        vocabulary_unchanged = (hashlib.sha256(canonical(getter())).hexdigest() == self._vocabulary_sha256
            if self._synthetic_tokenizer else
            getattr(getter, '__func__', None) is self._native_vocab_getter and
            getattr(getter, '__self__', None) is self.tokenizer)
        require(vocabulary_unchanged and self._tokenizer_pipeline_sha256() == self._pipeline_sha256 and
                hashlib.sha256(self._native_template().encode()).hexdigest() == self._template_sha256 and
                self.tokenizer.eos_token_id == self._canonical_eos_id and self.tokenizer.eos_token == self._canonical_eos_token and
                tuple(sorted(self.tokenizer.all_special_ids)) == self._special_ids,
                'native tokenizer/template identity changed after contract construction')

    def _content_spelling(self, content):
        require(type(content) is str, 'text content must be an exact string')
        require(not any(spelling in content for spelling in self._control_spellings),
                'reserved native control spelling in message/completion content')

    def _content_ids(self, content):
        self._content_spelling(content)
        ids = self.tokenizer.encode(content, add_special_tokens=False)
        require(type(ids) is list and all(type(i) is int and 0 <= i < self.vocab_size for i in ids),
                'invalid native content token IDs')
        require(not set(ids) & self._control_ids, 'reserved native control ID in message/completion content')
        return ids

    def _messages(self, messages):
        require(type(messages) is list and 1 <= len(messages) <= 202, 'bounded message list required')
        require(all(type(m) is dict and set(m) == {'role', 'content'} and
                    type(m['role']) is str and m['role'] in ('system', 'user', 'assistant') and
                    type(m['content']) is str for m in messages), 'text-only native messages required')
        require(messages[-1]['role'] == 'user', 'prompt must end in user turn')
        require(len(canonical(messages)) <= 262144, 'prompt byte cap exceeded')
        for m in messages:
            self._content_spelling(m['content'])
        return [dict(m) for m in messages]

    def prompt(self, messages):
        messages = self._messages(messages)
        self._assert_tokenizer_unchanged()
        for m in messages:
            self._content_ids(m['content'])
        rendered = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        require(type(rendered) is str and rendered, 'native no-thinking template required')
        ids = self.tokenizer.encode(rendered, add_special_tokens=False)
        require(type(ids) is list and ids and len(ids) < self.context_limit and
                all(type(i) is int and 0 <= i < self.vocab_size for i in ids), 'prompt context/vocabulary exceeds admission')
        return rendered, ids

    def prepare_completion(self, messages, completion):
        require(type(completion) is str and 0 < len(completion.encode()) <= 32768, 'bounded completion text required')
        self._content_spelling(completion)
        rendered, prompt = self.prompt(messages)
        self._content_ids(completion)
        full = self.tokenizer.encode(rendered + completion, add_special_tokens=False)
        require(full[:len(prompt)] == prompt and len(full) > len(prompt), 'tokenization boundary merge rejected')
        suffix = full[len(prompt):]
        require(not set(suffix) & self._control_ids, 'completion contains native control IDs')
        require(self.tokenizer.decode(suffix, skip_special_tokens=False, clean_up_tokenization_spaces=False) == completion,
                'completion roundtrip failed')
        suffix = suffix + [self._canonical_eos_id]
        ids = prompt + suffix
        require(len(suffix) <= self.output_cap and len(ids) <= self.context_limit,
                'whole completion exceeds context; no truncation')
        messages_copy = [dict(m) for m in messages]
        native = self.tokenizer.apply_chat_template(messages_copy + [{'role': 'assistant', 'content': completion}],
            tokenize=False, add_generation_prompt=False, enable_thinking=False)
        require(native == rendered + completion + self._canonical_eos_token + '\n',
                'noncanonical completion: native completed-chat template changes target content/prefix')
        require(self.tokenizer.encode(native[:-1], add_special_tokens=False) == ids,
                'native completed-chat IDs differ from exact generation-prefix supervision')
        prepared = {'format': 'irisx/model-next-prepared-completion-v2', 'contract_sha256': self.contract_sha256,
                    'messages': messages_copy, 'completion': completion, 'input_ids': ids,
                    'labels': [-100] * len(prompt) + suffix, 'supervised_tokens': len(suffix),
                    'prompt_tokens': len(prompt), 'input_tokens': len(ids),
                    'prompt_sha256': hashlib.sha256(canonical(prompt)).hexdigest(),
                    'completion_sha256': hashlib.sha256(completion.encode()).hexdigest()}
        prepared['prepared_sha256'] = hashlib.sha256(canonical(prepared)).hexdigest()
        if len(self._prepared_cache) >= 8:
            self._prepared_cache.pop(next(iter(self._prepared_cache)))
        self._prepared_cache[prepared['prepared_sha256']] = canonical(prepared)
        return prepared

    def validate_prepared(self, prepared):
        """Never trust mutable masks/counts; rederive the entire canonical example."""
        require(type(prepared) is dict and set(prepared) == self._PREPARED_KEYS, 'exact prepared-example fields required')
        require(prepared['format'] == 'irisx/model-next-prepared-completion-v2' and
                prepared['contract_sha256'] == self.contract_sha256, 'prepared-example identity mismatch')
        for name in ('supervised_tokens', 'prompt_tokens', 'input_tokens'):
            require(type(prepared[name]) is int and prepared[name] > 0, 'invalid prepared ' + name)
        for name in ('contract_sha256', 'prompt_sha256', 'completion_sha256', 'prepared_sha256'):
            require(type(prepared[name]) is str and bool(re.fullmatch('[0-9a-f]{64}', prepared[name])),
                    'invalid prepared hash field: ' + name)
        ids, labels = prepared['input_ids'], prepared['labels']
        require(type(ids) is list and type(labels) is list and ids and len(ids) == len(labels) and
                len(ids) == prepared['input_tokens'] and len(ids) <= self.context_limit, 'invalid prepared context/length')
        require(all(type(i) is int and 0 <= i < self.vocab_size for i in ids) and
                all(type(i) is int and (i == -100 or 0 <= i < self.vocab_size) for i in labels),
                'invalid prepared IDs/labels')
        boundary = prepared['prompt_tokens']
        require(0 < boundary < len(ids) and labels == [-100] * boundary + ids[boundary:],
                'prepared supervision must be contiguous exact next-token suffix; prompt stays masked')
        actual_count = sum(value != -100 for value in labels[1:])
        require(actual_count == prepared['supervised_tokens'] and 1 <= actual_count <= self.output_cap and
                ids[-1] == self._canonical_eos_id, 'prepared count/terminal mismatch')
        payload = {name: value for name, value in prepared.items() if name != 'prepared_sha256'}
        require(hashlib.sha256(canonical(payload)).hexdigest() == prepared['prepared_sha256'],
                'prepared content/hash changed')
        serialized = canonical(prepared)
        known = self._prepared_cache.get(prepared['prepared_sha256'])
        if known is not None:
            # Cache only prior native-proof bytes, never a mutable caller object.
            # Full tokenizer identity remains checked at every trusted call.
            self._assert_tokenizer_unchanged()
            require(serialized == known, 'prepared payload differs from immutable native proof')
            self.prepared_cache_hits += 1
            return json.loads(known)  # independent lists; mutations cannot alter the proof
        expected = self.prepare_completion(prepared['messages'], prepared['completion'])
        # Reconstruct all unknown/self-resigned examples natively. A digest alone
        # is not evidence that the caller supplied a correct mask or target.
        require(serialized == canonical(expected), 'prepared content, identity, hashes or masks changed')
        return expected

