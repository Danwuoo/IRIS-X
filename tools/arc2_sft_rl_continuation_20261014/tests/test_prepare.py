"""Offline tests using the real pinned public baseline bytes, never evaluator data.

Run normally and under python -O:
    python -m unittest discover -s tools/arc2_sft_rl_continuation_20261014/tests -p test_prepare.py
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

REPOSITORY = Path(__file__).absolute().parents[3]
PREPARE_PATH = REPOSITORY / "tools/arc2_sft_rl_continuation_20261014/prepare.py"
SPEC = importlib.util.spec_from_file_location("arc2_offline_prepare_under_test", PREPARE_PATH)
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


class PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals = {
            name: (REPOSITORY / name).read_bytes()
            for name in (prepare.PINS_PATH, *prepare.SOURCE_PATHS)
        }
        cls.baseline_policy = json.loads(cls.originals[prepare.POLICY_PATH])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arc2-offline-prepare-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repository"
        self.root.mkdir()
        for name, raw in self.originals.items():
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)

    def plan(self):
        return prepare.prepare_plan(self.root)

    def test_real_baseline_fixture_and_inventory_match(self):
        pins = json.loads(self.originals[prepare.PINS_PATH])
        self.assertEqual(pins["baseline_commit"], "cc14bd1a79aac1fe6135017c9e09d4834300675d")
        self.assertEqual(hashlib.sha256(self.originals[prepare.PINS_PATH]).hexdigest(), prepare.PINS_SHA256)
        self.assertEqual(len(pins["files"]), 5)
        for row in pins["files"]:
            with self.subTest(path=row["path"]):
                raw = self.originals[row["path"]]
                self.assertEqual(row["bytes"], len(raw))
                self.assertEqual(row["sha256"], hashlib.sha256(raw).hexdigest())
        result = self.plan()
        self.assertEqual(result["source_identity"]["total_bytes"], 118615)
        self.assertTrue(result["source_identity"]["selected_bytes_verified"])
        self.assertFalse(result["source_identity"]["repository_head_verified"])
        self.assertFalse(result["source_identity"]["complete_repository_verified"])
        self.assertFalse((self.root / ".git").exists())

    def test_real_checkout_matches_isolated_fixture(self):
        self.assertEqual(self.plan(), prepare.prepare_plan(REPOSITORY))

    def test_deterministic_json_and_no_output_writes(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                  for p in self.root.rglob("*") if p.is_file()}
        first = json.dumps(self.plan(), sort_keys=True, allow_nan=False)
        second = json.dumps(self.plan(), sort_keys=True, allow_nan=False)
        self.assertEqual(first, second)
        after = {p.relative_to(self.root).as_posix(): p.read_bytes()
                 for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertNotIn(str(self.root), first)
        self.assertNotIn(str(REPOSITORY), first)

    def test_returned_data_does_not_mutate_future_preparations(self):
        result = self.plan()
        result["scientific_plan"]["anchor"]["updates"] = 64
        result["source_identity"]["files"].clear()
        self.assertEqual(self.plan()["scientific_plan"]["anchor"]["updates"], 256)
        self.assertEqual(len(self.plan()["source_identity"]["files"]), 5)

    def test_all_actions_and_authority_remain_inert(self):
        result = self.plan()
        self.assertEqual(result["status"], "OFFLINE_PREPARATION_ONLY")
        for field in ("dispatch_authorized", "production_admitted", "automatic_next_run",
                      "model_execution_performed", "epoch_or_deadline_sampled",
                      "original_private_admission_reconstructed"):
            self.assertIs(result[field], False)
        self.assertEqual(result["source_identity"]["authority"], "reproducibility-only")
        text = " ".join(result["limitations"])
        self.assertIn("Missing private admission is a blocker", text)
        self.assertIn("not an objective-only causal estimate", text)
        self.assertIn("no prior clock or charge is reset", text)
        self.assertIn("Header-only checkpoint presence", text)

    def test_scientific_sections_retain_exact_pinned_policy_data(self):
        science = self.plan()["scientific_plan"]
        for key in ("identity", "anchor", "rl", "training_panel", "control", "clock_seconds",
                    "reserves_seconds", "gates", "cost_model", "fallback"):
            with self.subTest(section=key):
                self.assertEqual(science[key], self.baseline_policy[key])
        for key, value in self.baseline_policy["evaluation"].items():
            self.assertEqual(science["evaluation"][key], value)

    def test_sft256_anchor_schedule_and_native_identity(self):
        science = self.plan()["scientific_plan"]
        anchor = science["anchor"]
        self.assertEqual(anchor["updates"], 256)
        self.assertEqual(anchor["cosine_schedule_updates"], 256)
        self.assertEqual(anchor["warmup_updates"], 4)
        self.assertEqual(anchor["min_lr_ratio"], 0.1)
        self.assertEqual(anchor["learning_rate"], 2e-4)
        self.assertIs(anchor["same_session_retrain"], True)
        self.assertIs(anchor["historical_tensor_equivalence_claim"], False)
        self.assertEqual(science["identity"], {"model": "Qwen14B", "precision": "BF16 base / FP32 LoRA",
                                               "rank": 8, "single_gpu": True})

    def test_fixed_four_disjoint_64_slot_batches_and_zero_signal_policy(self):
        science = self.plan()["scientific_plan"]
        rl, panel = science["rl"], science["training_panel"]
        self.assertEqual((rl["max_batches"], rl["batch_slots"], rl["max_updates"]), (4, 64, 4))
        self.assertEqual((panel["attempts"], panel["parents"], panel["group_size"]), (256, 32, 8))
        self.assertEqual(panel["fixed_batches_parent_positions"], [[0, 8], [8, 16], [16, 24], [24, 32]])
        self.assertTrue(rl["fixed_policy_within_batch"])
        self.assertTrue(rl["continue_next_disjoint_batch_after_zero_signal"])
        self.assertTrue(rl["stop_on_incomplete_or_numeric_failure"])
        self.assertTrue(rl["rollback_current_batch_only"])
        self.assertFalse(rl["resampling"])
        self.assertFalse(rl["reward_dependent_replacement"])
        self.assertEqual(rl["learning_rate"], 1e-6)
        self.assertEqual((rl["temperature"], rl["top_p"]), (1.0, 1.0))

    def test_control_preserves_whole_wall_matching(self):
        control = self.plan()["scientific_plan"]["control"]
        self.assertEqual(control["restore"], "A")
        self.assertEqual(control["optimizer"], "fresh AdamW constant schedule")
        self.assertEqual(control["max_updates"], 8192)
        self.assertEqual(control["hard_phase_seconds"], 7200)
        self.assertFalse(control["padding"])
        self.assertEqual(control["tolerance"], "min(120,max(5,0.05*actual_B_seconds))")
        for cost in ("setup", "sampling", "rewards", "replay", "hashing", "Python",
                     "failed/rollback", "save/reload", "verification"):
            self.assertIn(cost, control["matched_quantity"])
        self.assertEqual(control["unmatched"], "Report explicitly; never label matched")

    def test_fixed_denominators_tie_order_and_no_ttt(self):
        evaluation = self.plan()["scientific_plan"]["evaluation"]
        self.assertEqual((evaluation["dev_parents"], evaluation["holdout_parents"]), (16, 32))
        self.assertEqual(evaluation["public_denominator"], {"tasks": 120, "queries": 167})
        self.assertEqual(evaluation["selected_PUBLIC_queries"], 167)
        self.assertEqual(evaluation["selected_PUBLIC_views"], 334)
        self.assertEqual(evaluation["tie_break_order"], ["A", "B", "C"])
        self.assertEqual(evaluation["transforms"], [0, 1])
        self.assertEqual((evaluation["TTT_updates"], evaluation["maximum_answers"], evaluation["output_cap"]), (0, 2, 1024))
        self.assertEqual(evaluation["seed"], 1917)
        self.assertIs(evaluation["greedy"], True)
        self.assertIs(evaluation["public_arm_mixing"], False)
        self.assertIs(evaluation["holdout_is_pristine_project_confirmation"], False)
        self.assertEqual(evaluation["missing_or_invalid_answers"], "wrong")
        self.assertEqual(evaluation["primary_phase_order"], [
            "common A", "B fixed-batch prefix", "C matched continuation", "A/B/C dev",
            "freeze selected arm", "selected-arm PUBLIC", "A/B/C held32", "model closure",
            "held scoring and original PUBLIC scorer"])

    def test_full_clock_chain_and_reserves_are_unsampled(self):
        science = self.plan()["scientific_plan"]
        self.assertEqual(science["clock_seconds"], {"absolute": 43200, "inner": 42000,
                                                   "outer": 42180, "provider": 42300})
        self.assertEqual(science["reserves_seconds"]["selected_PUBLIC"], 18000)
        self.assertEqual(science["reserves_seconds"]["closure"], 600)
        self.assertEqual(science["reserves_seconds"]["paired_ABC"], 4200)
        self.assertEqual(science["gates"]["proposed_cumulative_replay_backward_commit_batch_seconds"], 600)
        self.assertEqual(science["gates"]["maximum_absolute_logprob_gap"], 0.2)
        self.assertEqual(science["gates"]["maximum_p95_absolute_logprob_gap"], 0.05)
        self.assertEqual(science["gates"]["minimum_strict_DDIS_coverage"], 1.0)

    def test_artifact_checklist_has_no_created_evidence_or_absolute_paths(self):
        groups = self.plan()["local_executor_artifact_checklist"]
        names = []
        for group in groups:
            self.assertEqual(group["status"], "not_inspected")
            for name in group["relative_names"]:
                self.assertEqual("/".join(prepare._relative(name)), name)
                names.append(name)
        for required in ("AUTHENTICATED-COLLECTION.json", "RETRIEVAL-RECEIPT.json",
                         "TERMINAL-CONSUMER-RAW.json", "TERMINAL-VALIDATION.json",
                         "TERMINAL-CHECKPOINT.json", "owner-clock.json", "session-admission.json",
                         "experiment/frozen-plan.json", "experiment/physical-events.json"):
            self.assertIn(required, names)
        self.assertEqual(len(names), len(set(names)))

    def test_changed_source_same_length_is_rejected(self):
        for name in prepare.SOURCE_PATHS:
            with self.subTest(path=name):
                target = self.root / name
                original = self.originals[name]
                target.write_bytes(bytes([original[0] ^ 1]) + original[1:])
                with self.assertRaisesRegex(prepare.PreparationError, "source byte pin differs"):
                    self.plan()
                target.write_bytes(original)

    def test_each_missing_source_is_rejected(self):
        for name in (prepare.PINS_PATH, *prepare.SOURCE_PATHS):
            with self.subTest(path=name):
                target = self.root / name
                target.unlink()
                with self.assertRaises(prepare.PreparationError):
                    self.plan()
                target.write_bytes(self.originals[name])

    def test_changed_inventory_cannot_self_repin_changed_source(self):
        target = self.root / prepare.POLICY_PATH
        policy = deepcopy(self.baseline_policy)
        policy["anchor"]["updates"] = 64
        target.write_text(json.dumps(policy), encoding="utf-8")
        pins_path = self.root / prepare.PINS_PATH
        pins = json.loads(pins_path.read_bytes())
        for row in pins["files"]:
            if row["path"] == prepare.POLICY_PATH:
                row["bytes"] = target.stat().st_size
                row["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        pins_path.write_text(json.dumps(pins), encoding="utf-8")
        with self.assertRaisesRegex(prepare.PreparationError, "inventory byte pin differs"):
            self.plan()

    def test_stale_sft64_policy_fails_even_semantic_check(self):
        policy = deepcopy(self.baseline_policy)
        policy["anchor"]["updates"] = 64
        with self.assertRaisesRegex(prepare.PreparationError, "anchor.updates"):
            prepare._validate_policy(policy)

    def test_scientific_changes_are_rejected_independent_of_pinning(self):
        changes = [
            ("anchor", "cosine_schedule_updates", 64), ("anchor", "same_session_retrain", False),
            ("rl", "batch_slots", 32), ("rl", "max_batches", 8), ("rl", "resampling", True),
            ("training_panel", "fixed_batches_parent_positions", [[0, 8]] * 4),
            ("control", "matched_quantity", "CUDA-active seconds only"),
            ("control", "padding", True), ("evaluation", "TTT_updates", 1),
            ("evaluation", "dev_parents", 8), ("evaluation", "holdout_parents", 16),
            ("evaluation", "selected_PUBLIC_queries", 166),
            ("evaluation", "primary_phase_order", list(reversed(self.baseline_policy["evaluation"]["primary_phase_order"]))),
            ("evaluation", "greedy", 1), ("evaluation", "transforms", [1, 0]),
            ("clock_seconds", "absolute", 86400),
        ]
        for section, field, changed in changes:
            with self.subTest(section=section, field=field):
                policy = deepcopy(self.baseline_policy)
                policy[section][field] = changed
                with self.assertRaises(prepare.PreparationError):
                    prepare._validate_policy(policy)
        for flag in ("dispatch_authorized", "production_admitted", "hard_completion_guarantee"):
            with self.subTest(flag=flag):
                policy = deepcopy(self.baseline_policy)
                policy[flag] = True
                with self.assertRaises(prepare.PreparationError):
                    prepare._validate_policy(policy)

    def test_file_symlinks_rejected_even_to_identical_bytes(self):
        for name in (prepare.PINS_PATH, *prepare.SOURCE_PATHS):
            with self.subTest(path=name):
                target = self.root / name
                outside = Path(self.temp.name) / "identical-public-file"
                outside.write_bytes(self.originals[name])
                target.unlink()
                target.symlink_to(outside)
                with self.assertRaises(prepare.PreparationError):
                    self.plan()
                target.unlink()
                target.write_bytes(self.originals[name])

    def test_source_directory_symlink_rejected(self):
        real_tools = self.root / "real-tools"
        (self.root / "tools").rename(real_tools)
        (self.root / "tools").symlink_to(real_tools, target_is_directory=True)
        with self.assertRaises(prepare.PreparationError):
            self.plan()

    def test_root_symlink_and_ancestor_symlink_rejected(self):
        alias = Path(self.temp.name) / "linked-repository"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(prepare.PreparationError):
            prepare.prepare_plan(alias)
        ancestor_alias = Path(self.temp.name) / "linked-parent"
        ancestor_alias.symlink_to(Path(self.temp.name), target_is_directory=True)
        with self.assertRaises(prepare.PreparationError):
            prepare.prepare_plan(ancestor_alias / "repository")

    def test_directory_and_fifo_source_rejected_without_reading(self):
        target = self.root / prepare.SOURCE_PATHS[0]
        target.unlink()
        target.mkdir()
        with self.assertRaises(prepare.PreparationError):
            self.plan()
        target.rmdir()
        os.mkfifo(target)
        with self.assertRaisesRegex(prepare.PreparationError, "non-regular source"):
            self.plan()

    def test_oversized_and_empty_source_fail_before_hashing(self):
        target = self.root / prepare.SOURCE_PATHS[0]
        for data in (b"", b"x" * (prepare.MAX_SOURCE_BYTES + 1)):
            with self.subTest(size=len(data)):
                target.write_bytes(data)
                with self.assertRaisesRegex(prepare.PreparationError, "source byte limit"):
                    self.plan()

    def test_source_replacement_during_read_is_detected(self):
        target = self.root / prepare.PINS_PATH
        real_read = os.read
        changed = False

        def replace_after_read(fd, limit):
            nonlocal changed
            chunk = real_read(fd, limit)
            if not changed:
                changed = True
                target.unlink()
                target.write_bytes(self.originals[prepare.PINS_PATH])
            return chunk

        with patch.object(prepare.os, "read", side_effect=replace_after_read):
            with self.assertRaisesRegex(prepare.PreparationError, "source changed during read"):
                self.plan()

    def test_clean_relative_paths_only(self):
        for path in ("/etc/passwd", "../source.py", "a/../b", "a//b", "./a", "a/./b",
                     "a/", "a\\b", "C:/data", "a\x00b", "https://example.com/x", "ümlaut"):
            with self.subTest(path=path):
                with self.assertRaises(prepare.PreparationError):
                    prepare._relative(path)
        with self.assertRaises(prepare.PreparationError):
            prepare.prepare_plan(self.root / ".." / "repository")
        with self.assertRaises(prepare.PreparationError):
            prepare.prepare_plan(str(self.root))

    def test_strict_json_rejects_duplicates_nonfinite_and_nonobjects(self):
        for raw in (b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":Infinity}', b'[]', b'null', b'\xff'):
            with self.subTest(raw=raw):
                with self.assertRaises(prepare.PreparationError):
                    prepare._strict_json(raw)

    def test_no_clock_network_or_subprocess_activity(self):
        blocked = AssertionError("offline preparation attempted an external action")
        with patch.object(time, "time", side_effect=blocked), \
             patch.object(time, "monotonic", side_effect=blocked), \
             patch.object(time, "time_ns", side_effect=blocked), \
             patch.object(time, "perf_counter", side_effect=blocked), \
             patch.object(subprocess, "Popen", side_effect=blocked), \
             patch.object(socket, "socket", side_effect=blocked), \
             patch.object(os, "system", side_effect=blocked), \
             patch.object(os, "getenv", side_effect=blocked):
            self.assertEqual(self.plan()["status"], "OFFLINE_PREPARATION_ONLY")

    def test_import_surface_is_stdlib_only_and_has_no_assert_execution_gate(self):
        tree = ast.parse(PREPARE_PATH.read_text(encoding="utf-8"))
        imports = set()
        calls = set()
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, ast.Assert)
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.add(node.func.id)
        self.assertEqual(imports, {"__future__", "hashlib", "json", "os", "pathlib", "stat"})
        self.assertTrue(calls.isdisjoint({"exec", "eval", "compile", "__import__"}))

    def test_python_sources_are_never_interpreted(self):
        # Exact source hashes are checked as bytes. The source-file strings below
        # describe old entry points, but no such modules may appear as imports.
        import sys
        disallowed = {"owned_runtime", "rl_session", "experiment_flow", "torch", "kaggle"}
        before = {name for name in sys.modules if name.split(".")[0] in disallowed}
        self.plan()
        after = {name for name in sys.modules if name.split(".")[0] in disallowed}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
