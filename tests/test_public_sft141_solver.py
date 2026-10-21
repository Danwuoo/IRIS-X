"""CPU-only generic-runner tests. Synthetic subprocesses are not model evidence."""
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.public_sft141_diagnostic import contract as codec
from tools.public_sft141_submission import contract as wire
from tools.public_sft141_solver import core, controller, worker
from tools.public_sft141_solver.supervisor import supervised_run
from tests.platform_requirements import requires_linux


def challenge_fixture(n=2):
    return {f"task-{n-i:03d}": {"train": [{"input": [[1, 2]], "output": [[2], [3]]},
                {"input": [[4]], "output": [[5, 6]]}],
                "test": [{"input": [[1, 2, 3], [4, 5, 6]]}] + ([{"input": [[7], [8]]}] if i == 0 else [])}
            for i in range(n)}


class SyntheticBackend:
    def __init__(self, plan, deadline, mode):
        self.mode, self.calls, self.state = mode, 0, 0
        self.max_context = 8192
        self.queries = [q for p in plan["parents"] for q in p["test"]]
        self.order = core.schedule(core.inventory(plan))
        self.metadata = {"backend": "synthetic-CPU-NOT-MODEL", "load_count": 1}
        if mode == "load-fail":
            raise RuntimeError("synthetic load failure")
        if mode in ("descendant", "escape"):
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=mode == "escape")
            self.metadata["owned_child_pid"] = child.pid
            if mode == "escape":
                time.sleep(.2)  # Let observed lineage bind PID and start ticks before reparenting.

    def generate(self, prompt, max_new_tokens, deadline):
        assert max_new_tokens == 931
        begin = time.monotonic()
        _, i, view = self.order[self.calls]
        self.calls += 1
        if self.mode == "hang" and self.calls == 3:
            time.sleep(60)
        if self.mode == "slow":
            time.sleep(.1)
        if self.mode == "fail" and self.calls == 3:
            raise RuntimeError("synthetic OOM-like error; no retry")
        if self.mode == "mutate":
            self.state += 1
        grid = codec.transform(self.queries[i]["input"], view)
        tokens = codec.answer_ids(grid)
        if self.mode == "invalid":
            tokens = [1, 10, 15]
        if self.mode == "no-eos":
            tokens = [1]
        if self.mode == "oversize":
            tokens = [1] * 932
        return {"token_ids": tokens, "seconds": time.monotonic() - begin,
                "memory": {"synthetic": True}, "termination": "eos" if tokens[-1] == 15 else "max_tokens"}


def synthetic_prefix(mode):
    return [sys.executable, str(Path(__file__).resolve()), "--synthetic-worker", mode]


class GenericSolverTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".irisx"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="public-solver-test-", dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def run_synthetic(self, challenge=None, mode="copy", budget=15., fallback="fail"):
        challenge = challenge if challenge is not None else challenge_fixture()
        path = self.base / "challenge.json"
        # Deliberately preserve nonlexicographic insertion order.
        path.write_text(json.dumps(challenge))
        result = controller.run(path, self.base / "never-read-model", self.base / "run", self.base / "export",
            budget_seconds=budget, fallback=fallback, _test_worker_prefix=synthetic_prefix(mode))
        return result, json.loads((self.base / "run/analysis.json").read_text())

    def test_dynamic_inventory_all_support_and_eight_d4(self):
        for n in (1, 2, 120):
            value = challenge_fixture(n)
            plan = core.make_plan(value, "hash")
            core.validate_plan(plan, value, "hash")
            rows = core.inventory(plan)
            self.assertEqual(len(rows), n + 1)
            self.assertEqual([r["task_id"] for r in rows][:2], [next(iter(value))] * 2)
            for row in rows:
                self.assertEqual(row["support_count"], 2)
                task = value[row["task_id"]]
                for v in range(8):
                    prompt = codec.prompt_ids(task["train"], task["test"][row["test_index"]]["input"], v)
                    self.assertEqual(row["prompt_sha256_by_view"][v], wire.digest(wire.canonical(prompt)))
                    self.assertGreater(len(prompt), len(codec.prompt_ids(task["train"][:1], task["test"][0]["input"], v)))
            schedule = core.schedule(rows)
            self.assertEqual([v for _, _, v in schedule[:len(rows)]], [0] * len(rows))
            self.assertEqual([i for _, i, _ in schedule[len(rows):2 * len(rows)]], list(range(len(rows))))

    def test_gold_and_bool_identity_rejected(self):
        challenge = challenge_fixture()
        for field in ("output", "gold", "labels"):
            dirty = deepcopy(challenge)
            dirty[next(iter(dirty))]["test"][0][field] = [[1]]
            with self.assertRaises(ValueError):
                core.make_plan(dirty, "hash")
        plan = core.make_plan(challenge, "hash")
        plan["parents"][0]["test"][1]["test_index"] = True
        with self.assertRaises(ValueError):
            core.validate_plan(plan, challenge, "hash")

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_complete_subprocess_export_and_readback(self):
        result, analysis = self.run_synthetic()
        self.assertTrue(result["whole_budget_met"])
        self.assertEqual(analysis["counts"]["valid_views"], 24)
        self.assertTrue(analysis["all_queries_eight_views_completed"])
        self.assertEqual(analysis["model_state_guard"], "unchanged")
        self.assertEqual(analysis["execution_kind"], "synthetic-injected-no-model-evidence")
        submission = json.loads((self.base / "export/submission.json").read_text())
        closure = json.loads((self.base / "export/closure.json").read_text())
        self.assertEqual(closure["counts"]["singleton_duplicated_queries"], 3)
        self.assertFalse(closure["scientific_complete"])
        for task, inputs in challenge_fixture().items():
            for i, query in enumerate(inputs["test"]):
                self.assertEqual(submission[task][i], {"attempt_1": query["input"], "attempt_2": query["input"]})
        controller.verify(self.base / "run", self.base / "export")
        proc = subprocess.run([sys.executable, "-m", "tools.public_sft141_solver", "verify", "--run-dir", str(self.base / "run"),
                               "--output-dir", str(self.base / "export")], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_actual_120_parent_synthetic_subprocess(self):
        _, analysis = self.run_synthetic(challenge_fixture(120), budget=30.)
        self.assertEqual(len(analysis["queries"]), 121)
        self.assertEqual(analysis["counts"]["valid_views"], 968)

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_context_overflow_skips_only_affected_query(self):
        challenge = challenge_fixture(2)
        first = next(iter(challenge))
        # Same parent's small query fits, large query alone overflows at 8192.
        grid = [[1] * 30 for _ in range(30)]
        challenge[first]["train"] = [{"input": grid, "output": grid}] * 3 + [{"input": grid, "output": [[1] * 30 for _ in range(21)]}]
        challenge[first]["test"] = [{"input": [[1]]}, {"input": grid}]
        _, analysis = self.run_synthetic(challenge, fallback="copy-input")
        self.assertTrue(analysis["queries"][0]["context_admissible"])
        self.assertFalse(analysis["queries"][1]["context_admissible"])
        self.assertEqual(analysis["queries"][1]["completed_views"], [])
        self.assertEqual(analysis["queries"][1]["missing_views"], list(range(8)))
        self.assertTrue(analysis["queries"][2]["all_eight_views_completed"])
        self.assertEqual(analysis["counts"]["valid_views"], 16)

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_deadline_partial_prefix_and_unknown_preserved(self):
        result, analysis = self.run_synthetic(mode="hang", budget=1., fallback="copy-input")
        self.assertEqual(result["stop_reason"], "global-work-deadline")
        self.assertEqual(analysis["counts"]["returned_operations"], 2)
        self.assertEqual(analysis["counts"]["unknown_operations"], 1)
        self.assertEqual([q["completed_views"] for q in analysis["queries"]], [[0], [0], []])
        self.assertFalse(analysis["all_queries_eight_views_completed"])
        self.assertTrue(json.loads((self.base / "run/controller_exit.json").read_text())["cleanup"]["complete"])

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_work_conserving_backfill_without_query_slices(self):
        _, analysis = self.run_synthetic(mode="slow", budget=1., fallback="copy-input")
        lengths = [len(q["completed_views"]) for q in analysis["queries"]]
        self.assertGreater(min(lengths), 0)
        self.assertLessEqual(max(lengths) - min(lengths), 1)
        self.assertGreater(analysis["counts"]["returned_operations"], 3)

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_failed_operation_no_retry_and_full_inventory(self):
        _, analysis = self.run_synthetic(mode="fail", fallback="copy-input")
        self.assertEqual(len(analysis["queries"]), 3)
        self.assertEqual(analysis["counts"]["started_operations"], 3)
        self.assertEqual(analysis["counts"]["failed_operations"], 1)
        self.assertEqual(analysis["counts"]["returned_operations"], 2)
        self.assertFalse(analysis["counts"]["failed_or_unknown_cost_is_complete"])

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_load_failure_explicit_fallback(self):
        _, analysis = self.run_synthetic(mode="load-fail", fallback="copy-input")
        self.assertEqual(analysis["counts"]["started_operations"], 0)
        self.assertEqual(len(analysis["queries"]), 3)
        closure = json.loads((self.base / "export/closure.json").read_text())
        self.assertEqual(closure["counts"]["fallback_queries"], 3)

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_load_failure_default_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "no candidates"):
            self.run_synthetic(mode="load-fail")
        self.assertTrue((self.base / "run/analysis.json").is_file())
        self.assertFalse((self.base / "export/submission.json").exists())

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_strict_invalid_eos_no_repairs(self):
        _, analysis = self.run_synthetic(mode="invalid", fallback="copy-input")
        self.assertEqual(analysis["counts"]["invalid_views"], 24)
        self.assertEqual(analysis["counts"]["valid_views"], 0)
        self.assertTrue(analysis["all_queries_eight_views_completed"])

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_token_limit_protocol_failure_not_eligible(self):
        _, analysis = self.run_synthetic(mode="oversize", fallback="copy-input")
        self.assertEqual(analysis["counts"]["failed_operations"], 1)
        self.assertEqual(analysis["counts"]["valid_views"], 0)

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_model_state_change_invalidates_selection(self):
        _, analysis = self.run_synthetic(mode="mutate", fallback="copy-input")
        self.assertEqual(analysis["model_state_guard"], "changed")
        self.assertTrue(all(not q["selected"] for q in analysis["queries"]))

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_raw_tamper_and_source_mismatch_rejected(self):
        self.run_synthetic()
        root = self.base / "run"
        with patch.object(core, "source_identity", return_value={"sha256": "changed"}):
            with self.assertRaisesRegex(ValueError, "source/plan"):
                controller.verify(root, self.base / "export")
        path = next((root / "worker/receipts").glob("*-end.json"))
        value = json.loads(path.read_text())
        value["raw"]["token_ids"][0] = 9
        path.write_bytes(wire.canonical(value))
        with self.assertRaisesRegex(ValueError, "seal"):
            controller.verify(root, self.base / "export")

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_exclusive_atomic_publication_no_overwrite(self):
        self.run_synthetic()
        before = (self.base / "export/submission.json").read_bytes()
        with self.assertRaises(FileExistsError):
            controller.run(self.base / "challenge.json", self.base / "unused", self.base / "run", self.base / "export",
                           _test_worker_prefix=synthetic_prefix("copy"))
        self.assertEqual((self.base / "export/submission.json").read_bytes(), before)
        self.assertFalse(list((self.base / "export").glob(".*")))
        with self.assertRaises(FileExistsError):
            core.publish(self.base / "run/analysis.json", {})

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_owned_descendant_cleanup_does_not_kill_unrelated(self):
        unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
        self.addCleanup(lambda: unrelated.poll() is None and unrelated.kill())
        self.addCleanup(lambda: unrelated.wait(timeout=5) if unrelated.poll() is not None else None)
        self.run_synthetic(mode="descendant")
        backend = json.loads((self.base / "run/worker/backend.json").read_text())
        self.assertFalse(Path(f"/proc/{backend['owned_child_pid']}").exists())
        self.assertIsNone(unrelated.poll())
        unrelated.terminate()
        unrelated.wait(timeout=5)

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_controller_interrupt_stops_owned_worker(self):
        path = self.base / "challenge.json"
        path.write_text(json.dumps(challenge_fixture()))
        script = ("from tools.public_sft141_solver.controller import run; "
                  f"run({str(path)!r}, {str(self.base / 'unused')!r}, {str(self.base / 'run')!r}, "
                  f"{str(self.base / 'export')!r}, budget_seconds=15, fallback='copy-input', "
                  f"_test_worker_prefix={synthetic_prefix('hang')!r})")
        proc = subprocess.Popen([sys.executable, "-c", script], cwd=ROOT)
        limit = time.monotonic() + 5
        while not (self.base / "run/worker/receipts/00000002-start.json").exists() and time.monotonic() < limit:
            time.sleep(.02)
        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(timeout=5), 0)
        exit_row = json.loads((self.base / "run/controller_exit.json").read_text())
        self.assertEqual(exit_row["stop_reason"], "controller-interrupted")
        self.assertTrue(exit_row["cleanup"]["complete"])
        self.assertTrue((self.base / "export/submission.json").is_file())

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_owned_setsid_escape_is_killed_and_reaped(self):
        self.run_synthetic(mode="escape")
        backend = json.loads((self.base / "run/worker/backend.json").read_text())
        self.assertFalse(Path(f"/proc/{backend['owned_child_pid']}").exists())
        cleanup = json.loads((self.base / "run/controller_exit.json").read_text())["cleanup"]
        self.assertTrue(cleanup["complete"])
        self.assertIn(str(backend["owned_child_pid"]), cleanup["owned_pid_start_ticks"])

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_unattributed_adoption_blocks_seal_without_signalling(self):
        self.run_synthetic()
        root = self.base / "run"
        row = json.loads((root / "controller_exit.json").read_text())
        row["cleanup"]["complete"] = False
        row["cleanup"]["unattributed_adopted_children"] = {"99999999": 1}
        (root / "controller_exit.json").write_bytes(wire.canonical(row))
        with self.assertRaisesRegex(ValueError, "remain"):
            controller.seal_exited(root)

    def test_scheduler_is_not_shared_mutable_plan_state(self):
        plan = core.make_plan(challenge_fixture(), "hash")
        plan["scheduler"]["views"].reverse()
        self.assertEqual(core.SCHEDULER["views"], list(range(8)))
        with self.assertRaises(ValueError):
            core.validate_plan(plan, challenge_fixture(), "hash")

    def test_raw_vote_distinct_lexical_ties_and_token_rejection(self):
        challenge = {"one": {"train": [{"input": [[0]], "output": [[1]]}], "test": [{"input": [[0]]}]}}
        plan = core.make_plan(challenge, "hash")
        rows = core.inventory(plan)
        records = {}
        for ordinal, i, view in core.schedule(rows):
            operation = core.operation_identity(rows, ordinal, i, view)
            grid = [[2]] if view % 2 else [[1]]
            tokens = codec.answer_ids(codec.transform(grid, view))
            records[f"{ordinal:08d}-start.json"] = {"operation": operation, "started_monotonic": float(ordinal)}
            records[f"{ordinal:08d}-end.json"] = {"operation": operation, "outcome": "returned", "elapsed_seconds": .01,
                "error": None, "raw": {"token_ids": tokens, "generated_tokens": len(tokens), "seconds": .01,
                                       "memory": None, "termination": "eos"}}
        analysis, selected = core.reconstruct(plan, records)
        self.assertEqual(selected[("one", 0)], [[[1]], [[2]]])
        self.assertEqual([x["count"] for x in analysis["queries"][0]["candidate_pool"]], [4, 4])
        records["00000000-start.json"]["operation"] = dict(records["00000000-start.json"]["operation"], view=False)
        with self.assertRaisesRegex(ValueError, "identity"):
            core.reconstruct(plan, records)
        for tokens in ([1], [1, 15, 2, 15], [1, 10, 15], [11, 15], [1] * 930 + [15]):
            with self.assertRaises(ValueError):
                codec.parse_answer(tokens)

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_expired_outer_closure_never_claims_completion(self):
        original = controller.seal_exited
        def delayed(root):
            time.sleep(.6)
            return original(root)
        with patch.object(controller, "seal_exited", delayed):
            with self.assertRaises(TimeoutError):
                self.run_synthetic(mode="load-fail", budget=.5, fallback="copy-input")
        self.assertFalse((self.base / "run/completion.json").exists())
        self.assertTrue((self.base / "run/deadline_failure.json").exists())

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_bootstrap_failure_keeps_bounded_real_log(self):
        path = self.base / "challenge.json"
        path.write_text(json.dumps(challenge_fixture()))
        controller.run(path, self.base / "unused", self.base / "run", self.base / "export", fallback="copy-input",
            _test_worker_prefix=[sys.executable, "-c", "raise RuntimeError('synthetic bootstrap failure')"])
        self.assertIn("synthetic bootstrap failure", (self.base / "run/worker.log").read_text())
        analysis = json.loads((self.base / "run/analysis.json").read_text())
        self.assertEqual(analysis["worker_terminal"]["status"], "missing-terminal-not-clean")
        self.assertEqual(analysis["worker_returncode"], 1)
        seal = json.loads((self.base / "run/exited_seal.json").read_text())
        self.assertIn("worker.log", seal["files"])

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_independent_whole_clock_supervisor_success(self):
        path = self.base / "challenge.json"
        path.write_text(json.dumps(challenge_fixture()))
        result = supervised_run(path, self.base / "unused", self.base / "run", self.base / "export",
                                budget_seconds=10, _test_worker_prefix=synthetic_prefix("copy"))
        self.assertTrue(result["hard_watchdog_complete"])
        controller.verify(self.base / "run", self.base / "export")
        outer = json.loads((self.base / "run/outer_completion.json").read_text())
        dispatch = json.loads((self.base / "run/dispatch.json").read_text())
        self.assertEqual(outer["original_start_monotonic"], dispatch["start_monotonic"])
        self.assertEqual(outer["budget_seconds"], 10)
        outer["budget_seconds"] = 11
        (self.base / "run/outer_completion.json").write_bytes(wire.canonical(outer))
        with self.assertRaisesRegex(ValueError, "outer"):
            controller.verify(self.base / "run", self.base / "export")

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_hard_watchdog_interrupts_preprocessing_and_every_closure_stage(self):
        path = self.base / "challenge.json"
        path.write_text(json.dumps(challenge_fixture()))
        for fault in ("read", "source", "seal", "export", "verify"):
            with self.subTest(fault=fault):
                begun = time.monotonic()
                with self.assertRaises(TimeoutError):
                    supervised_run(path, self.base / "unused", self.base / ("run-" + fault), self.base / ("export-" + fault),
                        budget_seconds=.8, fallback="copy-input", _test_worker_prefix=synthetic_prefix("copy"),
                        _test_controller_prefix=[sys.executable, str(Path(__file__).resolve()), "--synthetic-controller", fault])
                self.assertLess(time.monotonic() - begun, 2.5)
                self.assertFalse((self.base / ("run-" + fault) / "outer_completion.json").exists())
                with self.assertRaises((OSError, ValueError)):
                    controller.verify(self.base / ("run-" + fault), self.base / ("export-" + fault))

    @requires_linux("Linux process groups, /proc start identities, subreaping, pidfds, and hard watchdog")
    def test_completion_clock_cannot_be_edited(self):
        self.run_synthetic()
        path = self.base / "run/completion.json"
        receipt = json.loads(path.read_text())
        receipt["budget"]["budget_seconds"] += 1
        path.write_bytes(wire.canonical(receipt))
        with self.assertRaisesRegex(ValueError, "clock"):
            controller.verify(self.base / "run", self.base / "export")

    @requires_linux("Linux independent hard watchdog and interval-timer finalization")
    def test_final_outer_readback_hang_never_creates_valid_completion(self):
        path = self.base / "challenge.json"
        path.write_text(json.dumps(challenge_fixture()))
        original = controller.files.read_bytes
        def blocked_read(target):
            if Path(target).name == "outer_precommit.json":
                time.sleep(60)
            return original(target)
        begun = time.monotonic()
        with patch.object(controller.files, "read_bytes", blocked_read):
            with self.assertRaises(TimeoutError):
                supervised_run(path, self.base / "unused", self.base / "run", self.base / "export",
                    budget_seconds=1., _test_worker_prefix=synthetic_prefix("copy"))
        self.assertLess(time.monotonic() - begun, 2.5)
        self.assertFalse((self.base / "run/outer_completion.json").exists())
        self.assertTrue((self.base / "run/outer_failure.json").exists())
        with self.assertRaises((OSError, ValueError)):
            controller.verify(self.base / "run", self.base / "export")

    def test_model_dependencies_are_optional(self):
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            self.skipTest("optional model dependencies are absent; no GPU/model run authorized")
        self.assertTrue(callable(worker.TransformersBackend))


if __name__ == "__main__" and "--synthetic-worker" in sys.argv:
    _, _, mode, *args = sys.argv
    raise SystemExit(worker.main(args, factory=lambda plan, deadline: SyntheticBackend(plan, deadline, mode)))
elif __name__ == "__main__" and "--synthetic-controller" in sys.argv:
    _, _, fault, *args = sys.argv
    def hang(*args, **kwargs):
        time.sleep(60)
    targets = {"read": (controller.files, "load_json"), "source": (core, "source_identity"),
               "seal": (controller, "seal_exited"), "export": (controller.files, "publish_bundle"),
               "verify": (controller, "verify")}
    owner, name = targets[fault]
    with patch.object(owner, name, hang):
        raise SystemExit(controller.main(args))
elif __name__ == "__main__":
    unittest.main()
