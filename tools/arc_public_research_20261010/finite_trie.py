"""Task-independent finite canonical-plan support on authenticated native IDs.

No tokenizer/model is constructed on import. Fake-tokenizer tests establish only
CPU contract behavior, never native-tokenizer or GPU acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import math
import os
from pathlib import Path
import time
import tracemalloc
from types import MappingProxyType

from tools.arc_consolidated_20261010.model_provider import ModelContractError, canonical, digest, _require

VERSION = "irisx/native-finite-plan-trie-v1"
INVENTORY_COUNT = 5965
INVENTORY_SHA256 = "f205b801bbb177cacd560582ddf994ad27c0f934cacd999b7983709d1c0a071e"
NATIVE_ROWS = 100352


@dataclass(frozen=True)
class TrieLimits:
    canonical_bytes: int = 2 * 1024 * 1024
    nodes: int = 1_000_000
    rss_delta_bytes: int = 512 * 1024 * 1024
    setup_seconds: float = 60.0
    output_tokens: int = 2048

    def __post_init__(self):
        for key, cap in (("canonical_bytes", 2 * 1024 * 1024), ("nodes", 1_000_000),
                         ("rss_delta_bytes", 512 * 1024 * 1024), ("output_tokens", 2048)):
            value = getattr(self, key)
            _require(type(value) is int and 0 < value <= cap, "invalid trie " + key + " cap")
        _require(type(self.setup_seconds) in (float, int) and math.isfinite(self.setup_seconds)
                 and 0 < self.setup_seconds <= 60, "invalid trie setup cap")


def rss_bytes():
    """Linux current RSS, rather than a previous process high-water mark."""
    return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")


def normalize_eos(value, vocabulary_ids):
    values = [value] if type(value) is int else value
    _require(type(values) in (list, tuple) and bool(values) and
             all(type(v) is int and 0 <= v < NATIVE_ROWS and v in vocabulary_ids for v in values),
             "unconfirmed native EOS IDs")
    _require(len(set(values)) == len(values), "duplicate native EOS IDs")
    return tuple(sorted(values))


def validate_generation_config(config):
    """Reject inherited processors that could force, suppress or redirect paths.

    Check the *effective* GenerationConfig, not just the sparse JSON. Sampling
    temperature/top_p/do_sample and max_new_tokens are explicit per-call values.
    Native top-k is retained identically in both arms; additional inherited
    processors that alter or suppress finite paths are rejected below.
    """
    _require(type(config) is dict, "effective generation configuration required")
    expected = {
        "num_beams": (1,), "num_beam_groups": (1,), "num_return_sequences": (1,),
        "min_length": (0,), "min_new_tokens": (None, 0),
        "forced_bos_token_id": (None,), "forced_eos_token_id": (None,),
        "suppress_tokens": (None, []), "begin_suppress_tokens": (None, []),
        "bad_words_ids": (None, []), "force_words_ids": (None, []), "constraints": (None, []),
        "sequence_bias": (None, {}), "forced_decoder_ids": (None, []),
        "repetition_penalty": (1.0,), "encoder_repetition_penalty": (1.0,),
        "no_repeat_ngram_size": (0,), "encoder_no_repeat_ngram_size": (0,),
        "diversity_penalty": (0.0,), "length_penalty": (1.0,),
        "exponential_decay_length_penalty": (None,), "guidance_scale": (None, 1.0),
        "penalty_alpha": (None,), "watermarking_config": (None,),
        "token_healing": (None, False), "stop_strings": (None,),
        "typical_p": (1.0,), "min_p": (None, 0.0), "top_h": (None,), "epsilon_cutoff": (0.0,),
        "eta_cutoff": (0.0,), "dola_layers": (None,), "max_time": (None,),
        "remove_invalid_values": (False,), "renormalize_logits": (None, False),
    }
    for key, allowed in expected.items():
        if key in config:
            value = config[key]
            _require(any(type(value) is type(v) and value == v or
                         type(value) in (int, float) and type(v) in (int, float) and value == v
                         for v in allowed), "conflicting generation configuration: " + key)
    _require(not config.get("custom_generate"), "custom generation is forbidden")
    return digest(config)


def resolve_native_policy(tokenizer, model_config, generation_config):
    vocabulary = tokenizer.get_vocab()
    ids = set(vocabulary.values())
    tokenizer_eos = normalize_eos(tokenizer.eos_token_id, ids)
    text_config = model_config.get("text_config", model_config)
    model_eos = normalize_eos(text_config.get("eos_token_id"), ids)
    generation_eos = normalize_eos(generation_config.get("eos_token_id"), ids)
    _require(model_eos == generation_eos, "model/generation native EOS disagreement")
    _require(set(tokenizer_eos) <= set(generation_eos), "tokenizer EOS not in native generation EOS")
    specials = set(tokenizer.all_special_ids)
    _require(set(generation_eos) <= specials, "native EOS is not an authenticated special token")
    pad = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    _require(type(pad) is int and pad in ids and 0 <= pad < NATIVE_ROWS, "scalar native pad policy required")
    configured_pad = generation_config.get("pad_token_id")
    _require(configured_pad is None or type(configured_pad) is int and configured_pad == pad,
             "generation/tokenizer pad disagreement")
    validate_generation_config(generation_config)
    return {"native_eos_ids": list(generation_eos), "tokenizer_eos_ids": list(tokenizer_eos),
            "model_eos_ids": list(model_eos), "pad_token_id": pad,
            "tokenizer_eos_difference": "subset-of-native-generation-eos" if tokenizer_eos != generation_eos else "none",
            "effective_generation_config_sha256": digest(generation_config)}


@dataclass(frozen=True)
class FrozenPlanTrie:
    children: tuple
    terminals: tuple[int, ...]
    canonical_texts: tuple[str, ...]
    token_sequences: tuple[tuple[int, ...], ...]
    plan_hashes: tuple[str, ...]
    native_eos_ids: tuple[int, ...]
    special_ids: tuple[int, ...]
    inventory_sha256: str
    tokenizer_sha256: str
    constraint_sha256: str
    metrics_json: str

    def allowed_suffix_tokens(self, suffix_ids):
        _require(type(suffix_ids) in (tuple, list), "one native suffix sequence required")
        node = 0
        for token in suffix_ids:
            _require(type(token) is int and token in self.children[node], "dead or unexpected native prefix")
            node = self.children[node][token]
        if self.terminals[node] >= 0:
            return list(self.native_eos_ids)
        allowed = list(self.children[node])
        _require(bool(allowed), "empty nonterminal native prefix")
        return allowed

    def validate_completion(self, output_ids):
        _require(type(output_ids) in (list, tuple) and len(output_ids) >= 2 and
                 type(output_ids[-1]) is int and output_ids[-1] in self.native_eos_ids,
                 "complete native terminal EOS required")
        node = 0
        for token in output_ids[:-1]:
            _require(type(token) is int and token in self.children[node], "completion leaves finite native path")
            node = self.children[node][token]
        index = self.terminals[node]
        _require(index >= 0, "early native EOS is not a completed plan")
        return {"plan_sha256": self.plan_hashes[index], "inventory_ordinal": index,
                "terminal_eos_id": output_ids[-1], "content_token_count": len(output_ids) - 1,
                "constraint_sha256": self.constraint_sha256}

    def decoding_binding(self, mode):
        _require(mode in ("raw", "strict"), "unknown finite-pool decoding mode")
        return {"mode": mode, "version": VERSION, "inventory_sha256": self.inventory_sha256,
                "constraint_sha256": self.constraint_sha256, "tokenizer_sha256": self.tokenizer_sha256,
                "native_eos_ids": list(self.native_eos_ids)}


def build_inventory_constraint(plans, tokenizer, native_identity, native_eos_ids, limits=None,
                               *, validate_and_compile=None, _setup_started=None, _rss_baseline=None):
    """Encode *complete* canonical strings. This generic builder permits CPU fixtures.

    Production calls build_native_inventory, which supplies the frozen generator,
    exact inventory count/hash, and trusted validation/compiler. No task inputs.
    """
    limits = limits or TrieLimits()
    began = time.monotonic() if _setup_started is None else _setup_started
    baseline = rss_bytes() if _rss_baseline is None else _rss_baseline
    peak = baseline
    traced_baseline = tracemalloc.get_traced_memory()[0] if tracemalloc.is_tracing() else None
    _require(type(plans) in (list, tuple) and bool(plans), "nonempty finite inventory required")
    _require(type(native_identity) is dict and bool(native_identity), "native tokenizer identity required")
    vocabulary = tokenizer.get_vocab()
    _require(type(vocabulary) is dict and bool(vocabulary) and all(type(k) is str and type(v) is int
             and 0 <= v < NATIVE_ROWS for k, v in vocabulary.items()), "invalid native vocabulary mapping")
    vocab_ids = frozenset(vocabulary.values())
    specials_raw = tokenizer.all_special_ids
    _require(type(specials_raw) in (list, tuple) and all(type(t) is int and t in vocab_ids for t in specials_raw),
             "unauthenticated native special IDs")
    specials = frozenset(specials_raw)
    eos = normalize_eos(native_eos_ids, vocab_ids)
    _require(set(eos) <= specials, "EOS must be an authenticated special token")
    tokenizer_sha = digest({"identity": native_identity, "vocabulary_mapping_sha256": digest(vocabulary),
                            "special_ids": sorted(specials), "native_eos_ids": eos})
    texts, sequences, hashes, seen = [], [], [], set()
    children, terminals, total_bytes = [{}], [-1], 0

    def guard():
        nonlocal peak
        peak = max(peak, rss_bytes())
        _require(time.monotonic() - began <= limits.setup_seconds, "native trie setup time cap")
        _require(peak - baseline <= limits.rss_delta_bytes, "native trie RSS delta cap")
        _require(len(children) <= limits.nodes, "native trie node cap")

    for plan in plans:
        guard()
        text = canonical(plan)
        total_bytes += len(text.encode("utf-8"))
        _require(total_bytes <= limits.canonical_bytes, "canonical inventory text cap")
        _require(text not in seen, "duplicate canonical inventory plan")
        seen.add(text)
        if validate_and_compile is not None:
            validate_and_compile(plan)
        encoded = tokenizer.encode(text, add_special_tokens=False)
        _require(type(encoded) in (tuple, list) and bool(encoded) and
                 all(type(t) is int and t in vocab_ids and t not in specials for t in encoded),
                 "empty, non-native, or special-token plan encoding")
        _require(len(encoded) + 1 <= limits.output_tokens, "plan plus EOS exceeds output reservation")
        _require(tokenizer.decode(encoded, skip_special_tokens=False, clean_up_tokenization_spaces=False) == text,
                 "canonical native decode roundtrip differs")
        node = 0
        for token in encoded:
            _require(terminals[node] < 0, "terminal-prefix relationship")
            if token not in children[node]:
                _require(len(children) < limits.nodes, "native trie node cap")
                children[node][token] = len(children)
                children.append({}); terminals.append(-1)
                if len(children) % 1024 == 0:
                    guard()
            node = children[node][token]
        _require(terminals[node] < 0, "native sequence collision")
        _require(not children[node], "terminal-prefix relationship")
        terminals[node] = len(texts)
        texts.append(text); sequences.append(tuple(encoded)); hashes.append(hashlib.sha256(text.encode()).hexdigest())
    inventory_sha = digest(plans)
    # Freeze every adjacency in sorted native ID order; no mutable task state.
    adjacency = tuple(MappingProxyType(dict(sorted(row.items()))) for row in children)
    constraint_sha = digest({"version": VERSION, "inventory_sha256": inventory_sha,
                             "tokenizer_sha256": tokenizer_sha, "native_eos_ids": eos,
                             "token_sequences": sequences, "limits": asdict(limits)})
    guard()
    metrics = {"setup_seconds": time.monotonic() - began, "nodes": len(children),
               "plans": len(texts), "canonical_bytes": total_bytes,
               "max_content_tokens": max(map(len, sequences)), "rss_baseline_bytes": baseline,
               "rss_peak_observed_bytes": peak, "rss_delta_bytes": max(0, peak - baseline),
               "python_allocation_delta_bytes": (tracemalloc.get_traced_memory()[0] - traced_baseline)
                   if traced_baseline is not None else None}
    return FrozenPlanTrie(adjacency, tuple(terminals), tuple(texts), tuple(sequences), tuple(hashes),
                          eos, tuple(sorted(specials)), inventory_sha, tokenizer_sha, constraint_sha, canonical(metrics))


def build_native_inventory(tokenizer, native_identity, native_eos_ids):
    from tools.arc_consolidated_20261010 import arc_object_ir as ir
    began, baseline = time.monotonic(), rss_bytes()
    plans = ir.base_inventory()
    _require(len(plans) == INVENTORY_COUNT and ir.digest(plans) == INVENTORY_SHA256,
             "frozen 5965 inventory identity differs")
    def compile_checked(plan):
        _require(ir.canonical_json(ir.validate_plan(plan)) == ir.canonical_json(plan), "noncanonical trusted plan")
        ir.compile_plan(plan)
    remaining = 60 - (time.monotonic() - began)
    _require(remaining > 0, "inventory preparation exhausted trie setup cap")
    # Keep identical frozen limit identity while enforcing the overall setup clock.
    trie = build_inventory_constraint(plans, tokenizer, native_identity, native_eos_ids,
                                      validate_and_compile=compile_checked,
                                      _setup_started=began, _rss_baseline=baseline)
    _require(time.monotonic() - began <= 60, "inventory plus trie preparation time cap")
    return trie


@dataclass
class OverheadLedger:
    seconds: float = 0.0
    calls: int = 0
    limit_seconds: float = 120.0

    def __post_init__(self):
        _require(type(self.limit_seconds) in (int, float) and 0 < self.limit_seconds <= 120,
                 "invalid session callback cap")


def make_prefix_callback(trie, prompt_length, call_deadline, overhead_ledger, *, prompt_ids=None,
                         call_overhead_limit=5.0):
    _require(type(prompt_length) is int and prompt_length > 0, "positive exact prompt offset required")
    _require(type(call_deadline) in (int, float) and math.isfinite(call_deadline), "finite callback deadline required")
    _require(type(call_overhead_limit) in (int, float) and 0 < call_overhead_limit <= 5,
             "invalid callback call cap")
    expected = tuple(prompt_ids) if prompt_ids is not None else None
    _require(expected is None or len(expected) == prompt_length, "prompt offset binding differs")
    stats = {"seconds": 0.0, "calls": 0}

    def callback(batch_id, input_ids):
        began = time.monotonic()
        try:
            _require(began < call_deadline, "generation deadline before prefix callback")
            _require(stats["seconds"] < call_overhead_limit and overhead_ledger.seconds < overhead_ledger.limit_seconds,
                     "prefix callback overhead cap")
            _require(type(batch_id) is int and batch_id == 0, "only one native sequence/beam is supported")
            if hasattr(input_ids, "ndim"):
                _require(input_ids.ndim == 1, "prefix callback requires one-dimensional native IDs")
                ids = input_ids.tolist()
            else:
                ids = input_ids
            _require(type(ids) in (tuple, list) and len(ids) >= prompt_length and
                     all(type(t) is int for t in ids), "invalid full input sequence")
            _require(expected is None or tuple(ids[:prompt_length]) == expected, "native prompt offset/content changed")
            stats["last_suffix_ids"] = tuple(ids[prompt_length:])
            return trie.allowed_suffix_tokens(ids[prompt_length:])
        finally:
            elapsed = time.monotonic() - began
            stats["seconds"] += elapsed; stats["calls"] += 1
            overhead_ledger.seconds += elapsed; overhead_ledger.calls += 1
            _require(time.monotonic() < call_deadline, "generation deadline inside prefix callback")
            _require(stats["seconds"] <= call_overhead_limit and overhead_ledger.seconds <= overhead_ledger.limit_seconds,
                     "prefix callback overhead cap")
    callback.stats = stats
    return callback
