"""Synthetic CPU contracts only; never evidence of native GPU generation."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from tools.arc_public_research_20261010 import finite_trie as ft, model_provider as mp
from tools.arc_consolidated_20261010 import arc_object_ir as ir


class ByteTokenizer:
    all_special_ids = [256, 257]
    eos_token_id = 256
    pad_token_id = 256
    def get_vocab(self):
        return {chr(i): i for i in range(256)} | {"EOS": 256, "PAD": 257}
    def encode(self, text, *, add_special_tokens):
        if add_special_tokens is not False:
            raise RuntimeError("special insertion")
        return list(text.encode())
    def decode(self, ids, *, skip_special_tokens, clean_up_tokenization_spaces):
        if skip_special_tokens is not False or clean_up_tokenization_spaces is not False:
            raise RuntimeError("native decode settings")
        return bytes(ids).decode()


def small(tokenizer=None, plans=None, **kwargs):
    return ft.build_inventory_constraint(plans or [{"steps": [{"op": "identity"}]},
        {"steps": [{"op": "transpose"}]}], tokenizer or ByteTokenizer(), {"test_only": True}, [256], **kwargs)


def tasks():
    return [{"task_id": "synthetic_%03d" % i, "demos": [{"input": [[i % 10]], "output": [[i % 10]]}]}
            for i in range(120)]


def requests():
    return mp.build_public_requests(tasks(), {"version": "synthetic", "steps": "trusted-contract"}, "e" * 64)


class TrieTests(unittest.TestCase):
    def test_complete_walk_and_terminal_only_eos(self):
        trie = small()
        for index, sequence in enumerate(trie.token_sequences):
            for length, token in enumerate(sequence):
                allowed = trie.allowed_suffix_tokens(sequence[:length])
                self.assertIn(token, allowed)
                self.assertNotIn(256, allowed)
                self.assertEqual(allowed, sorted(allowed))
            self.assertEqual(trie.allowed_suffix_tokens(sequence), [256])
            self.assertEqual(trie.validate_completion([*sequence, 256])["inventory_ordinal"], index)
        with self.assertRaises(TypeError):
            trie.children[0][0] = 5

    def test_early_eos_extra_braces_repeated_eos_extra_operation_fail(self):
        trie = small(); sequence = trie.token_sequences[0]
        for ids in ([256], [*sequence[:-1], 256], [*sequence, 125, 256],
                    [*sequence, 256, 256], [*sequence, 91, 256], [*sequence, True, 256]):
            with self.subTest(ids=ids), self.assertRaises(mp.ModelContractError):
                trie.validate_completion(ids)
        for prefix in ([999], [256], [*sequence, 125], [True]):
            with self.assertRaises(mp.ModelContractError):
                trie.allowed_suffix_tokens(prefix)

    def test_whole_strings_not_fragments_and_roundtrip(self):
        tokenizer = ByteTokenizer(); original = tokenizer.encode; seen = []
        def encode(text, **kwargs):
            seen.append(text); return original(text, **kwargs)
        tokenizer.encode = encode
        trie = small(tokenizer)
        self.assertEqual(tuple(seen), trie.canonical_texts)
        tokenizer.decode = lambda *a, **kw: "repaired"
        with self.assertRaisesRegex(mp.ModelContractError, "roundtrip"):
            small(tokenizer)

    def test_invalid_ids_specials_empty_vocabulary_hole(self):
        for sequence in ([], [True], [1.0], [-1], [100352], [999], [256], [257]):
            tokenizer = ByteTokenizer(); tokenizer.encode = lambda *a, **kw: sequence
            with self.subTest(sequence=sequence), self.assertRaises(mp.ModelContractError):
                small(tokenizer)

    def test_duplicate_plans_sequence_collision_terminal_prefix(self):
        plan = {"steps": [{"op": "identity"}]}
        with self.assertRaisesRegex(mp.ModelContractError, "duplicate"):
            small(plans=[plan, plan])
        # Deliberately adversarial fake decoder to reach the collision guard.
        tok = ByteTokenizer(); state = {}
        def encode(text, **kw):
            state["text"] = text; return [1]
        tok.encode = encode; tok.decode = lambda *a, **kw: state["text"]
        with self.assertRaisesRegex(mp.ModelContractError, "collision"):
            small(tok)
        for order in (([1], [1, 2]), ([1, 2], [1])):
            seqs = iter(order)
            def encode(text, **kw):
                state["text"] = text; return next(seqs)
            tok.encode = encode
            with self.assertRaisesRegex(mp.ModelContractError, "terminal-prefix"):
                small(tok)

    def test_fixed_caps_and_exact_output_eos_reservation(self):
        for kwargs in ({"nodes": 1}, {"canonical_bytes": 5}, {"output_tokens": 2}):
            with self.assertRaises(mp.ModelContractError):
                small(limits=ft.TrieLimits(**kwargs))
        length = len(mp.canonical({"steps": [{"op": "identity"}]}))
        one = [{"steps": [{"op": "identity"}]}]
        trie = small(plans=one, limits=ft.TrieLimits(output_tokens=length + 1))
        self.assertEqual(trie.validate_completion([*trie.token_sequences[0], 256])["content_token_count"], length)
        with self.assertRaisesRegex(mp.ModelContractError, "reservation"):
            small(plans=one, limits=ft.TrieLimits(output_tokens=length))
        with patch.object(ft, "rss_bytes", side_effect=[0, 513 * 1024 * 1024]):
            with self.assertRaisesRegex(mp.ModelContractError, "RSS"):
                small()
        with patch.object(ft.time, "monotonic", side_effect=[0, 61]):
            with self.assertRaisesRegex(mp.ModelContractError, "time cap"):
                small()
        for kwargs in ({"nodes": 1000001}, {"setup_seconds": 61}, {"rss_delta_bytes": 2**30}, {"output_tokens": 2049}):
            with self.assertRaises(mp.ModelContractError):
                ft.TrieLimits(**kwargs)

    def test_callback_full_prompt_offsets_and_no_empty_fallback(self):
        trie = small(); ledger = ft.OverheadLedger()
        callback = ft.make_prefix_callback(trie, 2, time.monotonic() + 5, ledger, prompt_ids=[7, 8])
        self.assertEqual(callback(0, [7, 8]), [123])
        for batch, ids in ((1, [7, 8]), (True, [7, 8]), (0, [8, 7]), (0, [7]),
                           (0, [[7, 8]]), (0, [7, 8, 999])):
            with self.assertRaises(mp.ModelContractError):
                callback(batch, ids)
        self.assertGreater(ledger.calls, 0)
        expired = ft.make_prefix_callback(trie, 1, time.monotonic() - 1, ledger)
        with self.assertRaisesRegex(mp.ModelContractError, "deadline"):
            expired(0, [7])
        callback = ft.make_prefix_callback(trie, 1, time.monotonic() + 5, ledger)
        ledger.seconds = 121
        with self.assertRaisesRegex(mp.ModelContractError, "overhead"):
            callback(0, [7])

    def test_callback_inside_deadline_and_overhead_caps(self):
        trie = small(); ledger = ft.OverheadLedger()
        callback = ft.make_prefix_callback(trie, 1, 10.0, ledger)
        with patch.object(ft.time, "monotonic", side_effect=[0., 6., 6.]), self.assertRaisesRegex(mp.ModelContractError, "overhead"):
            callback(0, [7])
        self.assertEqual(ledger.seconds, 6.)
        callback = ft.make_prefix_callback(trie, 1, 1.0, ft.OverheadLedger())
        with patch.object(ft.time, "monotonic", side_effect=[0., 2., 2.]), self.assertRaisesRegex(mp.ModelContractError, "deadline"):
            callback(0, [7])

    def test_native_policy_and_config_fail_closed(self):
        tok = ByteTokenizer(); cfg = {"eos_token_id": 256, "pad_token_id": 256}
        self.assertEqual(ft.resolve_native_policy(tok, cfg, cfg)["native_eos_ids"], [256])
        for key, value in (("forced_eos_token_id", 256), ("forced_bos_token_id", 1), ("min_length", 1),
                           ("min_new_tokens", 1), ("num_beams", 2), ("num_return_sequences", 2),
                           ("suppress_tokens", [1]), ("bad_words_ids", [[1]]), ("sequence_bias", {"1": 2}),
                           ("repetition_penalty", 1.1), ("token_healing", True), ("stop_strings", ["}"])):
            with self.subTest(key=key), self.assertRaises(mp.ModelContractError):
                ft.validate_generation_config({key: value})
        for bad in (None, [], [True], [256, 256], 999, [1.0]):
            with self.assertRaises(mp.ModelContractError):
                ft.normalize_eos(bad, set(tok.get_vocab().values()))
        with self.assertRaises(mp.ModelContractError):
            ft.resolve_native_policy(tok, cfg, {**cfg, "eos_token_id": 257})
        tok.pad_token_id = [256]
        with self.assertRaises(mp.ModelContractError):
            ft.resolve_native_policy(tok, cfg, cfg)

    def test_all_5965_frozen_inventory_walk_and_compiler(self):
        # ByteTokenizer deliberately has no claim to native Granite token IDs.
        trie = ft.build_native_inventory(ByteTokenizer(), {"evidence_mode": "fake-byte-tokenizer"}, [256])
        self.assertEqual(trie.inventory_sha256, ft.INVENTORY_SHA256)
        self.assertEqual(len(trie.token_sequences), 5965)
        self.assertEqual(json.loads(trie.metrics_json)["canonical_bytes"], 851931)
        for index, sequence in enumerate(trie.token_sequences):
            for length, token in enumerate(sequence):
                allowed = trie.allowed_suffix_tokens(sequence[:length])
                self.assertIn(token, allowed); self.assertNotIn(256, allowed)
            receipt = trie.validate_completion([*sequence, 256])
            self.assertEqual(receipt["inventory_ordinal"], index)
            self.assertEqual(receipt["plan_sha256"], ir.digest(ir.parse_plan(trie.canonical_texts[index])))


class RequestTests(unittest.TestCase):
    def test_exact_pairs_order_seed_and_data_only(self):
        rows = requests(); self.assertEqual(len(rows), 240)
        self.assertEqual(rows[0].decoding_mode, "raw"); self.assertEqual(rows[2].decoding_mode, "strict")
        for a, b in zip(rows[::2], rows[1::2]):
            self.assertEqual(a.messages_json, b.messages_json); self.assertEqual(a.spec.seed, b.spec.seed)
            self.assertEqual(a.prompt_sha256, b.prompt_sha256); self.assertNotEqual(a.sha256, b.sha256)
            self.assertEqual({a.decoding_mode, b.decoding_mode}, {"raw", "strict"})
        self.assertLess(len(rows[0].messages_json), 8000)
        bad = tasks(); bad[0]["query"] = [[0]]
        with self.assertRaises(mp.ModelContractError):
            mp.build_public_requests(bad, {"version": 1}, "e" * 64)
        with self.assertRaises(mp.ModelContractError):
            mp.build_public_requests(tasks()[:8], {"version": 1}, "e" * 64)

    def test_cache_binds_mode_inventory_tokenizer_eos_constraint(self):
        a, b = requests()[:2]
        policy = {"mode": "raw", "version": ft.VERSION, "inventory_sha256": ft.INVENTORY_SHA256,
                  "constraint_sha256": "c" * 64, "tokenizer_sha256": "d" * 64, "native_eos_ids": [256]}
        pa = mp.PreparedCall(a, (1, 2), mp.canonical(policy))
        pb = mp.PreparedCall(b, (1, 2), mp.canonical({**policy, "mode": "strict"}))
        self.assertNotEqual(pa.cache_sha256, pb.cache_sha256)
        for key, value in (("constraint_sha256", "b" * 64), ("tokenizer_sha256", "b" * 64), ("native_eos_ids", [257])):
            changed = replace(pa, decoding_binding_json=mp.canonical({**policy, key: value}))
            self.assertNotEqual(pa.cache_sha256, changed.cache_sha256)
        with self.assertRaises(mp.ModelContractError):
            replace(pa, decoding_binding_json=mp.canonical({**policy, "inventory_sha256": "b" * 64}))
        self.assertEqual(pa.reservation()["request_sha256"], pa.sha256)

    def test_raw_legal_outside_inventory_retained_ineligible(self):
        plan = {"steps": [{"op": "identity"}, {"op": "identity"}, {"op": "identity"}]}
        text = mp.canonical(plan)
        result = mp.classify_response(text, {ir.digest(p) for p in ir.base_inventory()})
        self.assertEqual(result["status"], "legal_outside_inventory")
        self.assertEqual(result["plan"], plan); self.assertFalse(result["eligible"])
        self.assertEqual(result["response_sha256"], mp.hashlib.sha256(text.encode()).hexdigest())
        self.assertEqual(mp.classify_response(text + "}", set())["status"], "invalid_plan")

    def test_checks_survive_optimized_python(self):
        code = '''from tools.arc_public_research_20261010 import finite_trie as f
try: f.normalize_eos([True], {1})
except ValueError: pass
else: raise RuntimeError("optimized check disabled")
try: f.validate_generation_config({"forced_eos_token_id":1})
except ValueError: pass
else: raise RuntimeError("optimized config check disabled")
'''
        result = subprocess.run([sys.executable, "-B", "-O", "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
