"""Real subprocess orchestration and CPU causal math; never public-model quality."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from tests.platform_requirements import requires_linux

from tools.public_calibrated_solver import common, controller
from tools.public_calibrated_solver.evaluation import evaluate
from tools.public_calibrated_solver.synthetic import fixture_plan
from tools.public_calibrated_solver.trace_audit import audit
from tools.public_demo_calibration import core
from tools.public_sft141_diagnostic import contract, model_worker as base
from tools.public_sft141_submission.files import load_json


ROOT = common.ROOT


def write(path, value):
    raw = (json.dumps(value, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return common.sha(raw)


def get(path):
    return load_json(path)[0]


@requires_linux("Real owned Linux process groups, subreaper cleanup and subprocess deadline enforcement")
@unittest.skipUnless(importlib.util.find_spec("torch"), "optional torch is required for actual synthetic CPU tensor subprocess proof")
class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="public-calibrated-tests-")
        cls.root = Path(cls.tmp.name)
        cls.plan = fixture_plan()
        cls.gold = {"answers": {p["task_id"]: [[[3]] for q in p["test"]] for p in cls.plan["parents"]}}
        cls.plan_hash = write(cls.root / "plan.json", cls.plan)
        cls.gold_hash = write(cls.root / "gold.json", cls.gold)
        cls.lock = controller.prepare(cls.root / "plan.json", cls.plan_hash, cls.root / "lock", "synthetic_cpu")
        cls.run_dir, rc = cls.run_solver("complete")
        if rc != 0:
            logs = "\n".join(p.read_text() for p in cls.run_dir.rglob("*.log"))
            raise AssertionError("end-to-end CPU proof failed: " + logs)
        cls.paired = cls.run_dir / "paired"
        cls.base = get(cls.paired / "base_result.json")
        cls.calibration = get(cls.paired / "calibration.json")
        cls.pool = get(cls.paired / "pool.json")
        cls.ranking = get(cls.paired / "ranking.json")
        cls.result = get(cls.paired / "evaluation/result.json")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def run_solver(cls, name, fault="none", age=0, fallback="fail", strategy="demo_weighted"):
        out = cls.root / name
        cmd = [sys.executable, "-m", "tools.public_calibrated_solver", "run",
            "--source-lock", cls.lock["source_lock_path"], "--source-lock-sha256", cls.lock["source_lock_sha256"],
            "--synthetic", "--gold", str(cls.root / "gold.json"), "--gold-sha256", cls.gold_hash,
            "--strategy", strategy, "--fallback", fallback, "--budget-seconds", "60",
            "--synthetic-age-seconds", str(age), "--synthetic-fault", fault, "--output", str(out)]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=65)
        return out, result.returncode

    def audited(self, **changes):
        values = dict(plan=self.plan, gold=self.gold, base_result=self.base,
                      calibration=self.calibration, pool=self.pool, ranking=self.ranking,
                      execution_kind="synthetic_cpu", session_complete=True)
        values.update(changes)
        return evaluate(**values)

    def test_actual_subprocess_pipeline_single_model_original_clock_and_no_gold_import(self):
        watchdog = get(self.run_dir / "watchdog.json")
        closure = get(self.paired / "closure.json")
        worker = get(self.paired / "model/closure.json")
        self.assertEqual(watchdog["status"], "complete")
        self.assertTrue(closure["worker_exited_before_evaluation"])
        self.assertEqual(worker["model_load_count"], 1)
        self.assertTrue(worker["same_backend_all_stages"])
        self.assertFalse(worker["evaluator_imported"])
        self.assertFalse(self.result["scientific_effectiveness_established"])
        intent = get(self.run_dir / "intent.json")
        self.assertNotIn("gold", intent)
        self.assertNotIn("gold_path", intent)
        traces = [get(p) for p in sorted((self.paired / "model/receipts").glob("trace-*.json"))]
        self.assertEqual({r["original_started_monotonic"] for r in traces}, {intent["started_monotonic"]})
        freeze = get(self.paired / "model/calibration_freeze.json")
        starts = [r for r in traces if r["kind"] == "operation_start"]
        generations = [r for r in starts if r["operation"] == "generate"]
        self.assertEqual(len(generations), 123)  # Includes unchanged 3 admission probes.
        self.assertTrue(all(r["event"] > freeze["event"] for r in generations))
        self.assertEqual(sum(r["phase"] == "calibration" for r in starts), 192)
        self.assertTrue(all(r["phase"] == "task_test" for r in generations))
        seal = get(self.paired / "worker_seal.json")
        common.verify_evidence(self.paired / "model", seal["files"])
        self.assertEqual(len(self.pool["rows"]), 120)

    def test_same_pool_all_three_ranks_full_denominators(self):
        self.assertTrue(self.result["scientific_audit_complete"])
        self.assertEqual(self.result["fixed_task_denominator"], 12)
        self.assertEqual(self.result["fixed_query_denominator"], 15)
        for name in ("vote", "rescored", "demo_weighted"):
            m = self.result["coverage_inclusive_metrics"][name]
            self.assertEqual(m["query_denominator"], 15)
            self.assertEqual(m["parent_denominator"], 12)
        for b, r in zip(self.base["queries"], self.ranking["queries"]):
            self.assertEqual(b["vote"], r["uniform_top2"])
            self.assertEqual({c["canonical_key"]: c["count"] for c in b["candidates"]},
                             {c["canonical_key"]: c["count"] for c in r["candidates"]})
        self.assertNotEqual(self.ranking["queries"][0]["uniform_top2"],
                            self.ranking["queries"][0]["weighted_top2"])

    def test_full_operation_cost_audit_counts_admission_separately(self):
        ledger = get(self.paired / "trace_audit.json")
        self.assertTrue(ledger["audit_passed"])
        self.assertTrue(ledger["strict_complete"])
        self.assertEqual(ledger["totals"]["attempted"], 678)
        self.assertEqual(ledger["expected"]["calibration_scores"], 192)
        self.assertEqual(ledger["expected"]["scientific_generations"], 120)
        self.assertEqual(ledger["expected"]["admission_generations"], 3)
        self.assertEqual(ledger["expected"]["admission_scores"], 3)
        self.assertFalse(ledger["costs_unknown"])

    def test_trace_audit_rejects_aggregate_admission_cost_and_orphan_score(self):
        wrong = copy.deepcopy(self.base)
        wrong["context_admission"] = []
        wrong["timings"]["admission_scoring_seconds"] = 0
        ledger = audit(self.plan, self.calibration, wrong, self.paired / "model", True)
        self.assertFalse(ledger["audit_passed"])
        with tempfile.TemporaryDirectory() as d:
            worker = Path(d) / "model"
            shutil.copytree(self.paired / "model", worker)
            raw = next((worker / "generation/receipts").glob("nll-*.json"))
            shutil.copyfile(raw, worker / "generation/receipts/nll-0000-99-0.json")
            ledger = audit(self.plan, self.calibration, self.base, worker, True)
            self.assertFalse(ledger["audit_passed"])
            self.assertFalse(ledger["strict_complete"])

    def test_outer_clock_and_freeze_provenance_cannot_self_consistently_reset(self):
        intent = get(self.run_dir / "intent.json")
        ledger = get(self.paired / "trace_audit.json")
        controller.bind_trace_intent(intent, self.paired / "model", ledger, True)
        with self.assertRaisesRegex(ValueError, "original outer clock"):
            controller.bind_trace_intent(intent, self.paired / "model",
                dict(ledger, original_started_monotonic=intent["started_monotonic"] + 1), True)
        with self.assertRaisesRegex(ValueError, "original work deadline"):
            controller.bind_trace_intent(intent, self.paired / "model",
                dict(ledger, last_trace_elapsed_seconds=45.), True)
        with self.assertRaisesRegex(ValueError, "initial session/source/budget"):
            controller.bind_trace_intent(dict(intent, session_id="different"), self.paired / "model", ledger, True)

    def test_fixed_selection_and_public_export_verified_before_gold(self):
        selection = get(self.paired / "selection.json")
        self.assertEqual(selection["selected_strategy"], "demo_weighted")
        self.assertFalse(selection["evaluation_started"])
        self.assertFalse(selection["score_based_selection"])
        self.assertTrue(get(self.paired / "export_status.json")["verified"])
        path = self.paired / "export/submission.json"
        before = path.read_bytes()
        alternate = {"answers": {p["task_id"]: [[[9]] for q in p["test"]] for p in self.plan["parents"]}}
        self.audited(gold=alternate)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(get(self.paired / "export/closure.json")["scientific_complete"])
        self.assertTrue(get(self.paired / "evaluation/boundary.json")["selection_precedes_gold_read"])

    def test_selection_lineage_recomputes_every_hash_and_eligibility(self):
        intent = get(self.run_dir / "intent.json")
        candidates, selection = controller.selection_values(intent, self.plan, self.base, self.ranking,
            common.sha((self.paired / "challenge.json").read_bytes()))
        self.assertEqual(candidates, get(self.paired / "selected_candidates.json"))
        self.assertEqual(selection, get(self.paired / "selection.json"))
        altered = dict(intent, selected_strategy="vote")
        other, lineage = controller.selection_values(altered, self.plan, self.base, self.ranking,
            common.sha((self.paired / "challenge.json").read_bytes()))
        self.assertNotEqual(other["queries"], candidates["queries"])
        self.assertNotEqual(lineage["intent_sha256"], selection["intent_sha256"])

    def test_rank_replay_without_operation_trace_is_not_scientific_complete(self):
        result = self.audited()
        self.assertFalse(result["scientific_audit_complete"])
        self.assertTrue(result["protocol_trace_audit_required_for_scientific_completion"])

    def test_raw_seal_detects_modified_added_and_missing_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root / "raw.json", {"tokens": [1, 15]})
            seal = common.evidence_manifest(root)
            write(root / "raw.json", {"tokens": [2, 15]})
            with self.assertRaises(ValueError): common.verify_evidence(root, seal)
            (root / "raw.json").unlink()
            with self.assertRaises(ValueError): common.verify_evidence(root, seal)
            write(root / "raw.json", {"tokens": [1, 15]})
            write(root / "extra.json", {})
            with self.assertRaises(ValueError): common.verify_evidence(root, seal)

    def test_rank_and_raw_token_tampering_rejected(self):
        ranking = copy.deepcopy(self.ranking)
        ranking["queries"][0]["weighted_top2"].reverse()
        with self.assertRaises(ValueError): self.audited(ranking=ranking)
        pool = copy.deepcopy(self.pool)
        pool["rows"][0]["token_ids"][0] = 9
        with self.assertRaises(ValueError): self.audited(pool=pool)
        wrong = copy.deepcopy(self.calibration)
        wrong["rows"][0]["spec"]["loss_mask"]["prompt_targets_included"] = True
        with self.assertRaises(ValueError): self.audited(calibration=wrong)

    def test_source_and_public_plan_pins_fail_closed(self):
        with self.assertRaises(ValueError): common.admit(self.plan, self.plan_hash, "public_model")
        plan = copy.deepcopy(self.plan)
        plan["parents"][0]["test"].pop()
        with self.assertRaises(ValueError): common.admit(plan, "fixture", "synthetic_cpu")
        identity = common.sources()
        identity[next(iter(identity))] = "0" * 64
        with self.assertRaises(ValueError): common.verify_sources(identity)
        with self.assertRaises(ValueError): common.frozen(self.root / "plan.json", "0" * 64)

    def test_calibration_failure_keeps_costs_denominator_and_never_promotes_fallback(self):
        out, rc = self.run_solver("calibration-failed", fault="calibration-fail", fallback="copy-input")
        self.assertEqual(rc, 2)
        p = out / "paired"
        calibration = get(p / "calibration.json")
        self.assertEqual(calibration["status"], "partial")
        self.assertEqual(len(calibration["rows"]), 3)
        self.assertIsNone(calibration["rows"][-1]["forward_calls"])
        self.assertFalse((p / "model/generation").exists())
        result = get(p / "evaluation/result.json")
        self.assertFalse(result["scientific_audit_complete"])
        weighted = result["coverage_inclusive_metrics"]["demo_weighted"]
        self.assertEqual(weighted["query_denominator"], 15)
        self.assertEqual(weighted["queries_without_candidates"], 15)
        export = get(p / "export/closure.json")
        self.assertEqual(export["counts"]["fallback_queries"], 15)
        self.assertFalse(export["scientific_complete"])
        self.assertTrue(get(p / "export_status.json")["verified"])
        self.assertEqual(get(out / "watchdog.json")["status"], "partial")

    def test_generation_failure_preserves_missing_views_full_denominator(self):
        out, rc = self.run_solver("generation-failed", fault="generation-fail", fallback="copy-input")
        self.assertEqual(rc, 2)
        result = get(out / "paired/evaluation/result.json")
        self.assertFalse(result["scientific_audit_complete"])
        self.assertEqual(result["fixed_query_denominator"], 15)
        pool = get(out / "paired/pool.json")
        self.assertEqual(len(pool["rows"]), 3)
        self.assertEqual(pool["rows"][-1]["status"], "failed")
        self.assertTrue(any(r["missing_views"] for r in get(out / "paired/ranking.json")["queries"]))

    def test_model_timeout_kills_owned_leaf_and_keeps_original_clock(self):
        # Loading/calibration occurs within the remaining 10s work window; a
        # real sleeping synthetic generation cannot finish under that window.
        out, rc = self.run_solver("model-hung", fault="generation-hang", age=35, fallback="copy-input")
        self.assertEqual(rc, 2)
        seal = get(out / "paired/worker_seal.json")
        self.assertTrue(seal["worker_exited"])
        self.assertTrue(seal["timed_out"])
        self.assertLess(seal["returncode"], 0)
        self.assertEqual(get(out / "intent.json")["synthetic_age_seconds"], 35)
        self.assertEqual(get(out / "watchdog.json")["status"], "partial")
        self.assertGreaterEqual(get(out / "watchdog.json")["budget"]["elapsed_seconds"], 45)
        self.assertEqual(get(out / "paired/evaluation/result.json")["fixed_query_denominator"], 15)

    def test_partial_calibration_and_late_pool_never_false_complete(self):
        calibration = copy.deepcopy(self.calibration)
        calibration["status"] = "partial"
        pool = copy.deepcopy(self.pool)
        pool["calibration_sha256"] = core.digest(calibration)
        ranking = core.rank(self.plan, calibration, pool)
        result = self.audited(calibration=calibration, pool=pool, ranking=ranking, session_complete=False)
        self.assertEqual(result["coverage_inclusive_metrics"]["demo_weighted"]["queries_without_candidates"], 15)
        self.assertFalse(result["scientific_audit_complete"])
        late = copy.deepcopy(self.pool)
        late["rows"][0]["status"] = "deadline"
        rank = core.rank(self.plan, self.calibration, late)
        result = self.audited(pool=late, ranking=rank, session_complete=False)
        self.assertFalse(result["scientific_audit_complete"])
        with self.assertRaises(ValueError): self.audited(pool=late, ranking=rank)

    def test_evaluator_leaf_rejects_changed_seal_without_gold_access(self):
        # Independent replay has to reject the immutable input first, even if
        # the supplied evaluator-only gold pathname does not exist.
        result = subprocess.run([sys.executable, "-m", "tools.public_calibrated_solver", "_evaluate",
            "--intent", str(self.run_dir / "intent.json"), "--intent-sha256", common.sha((self.run_dir / "intent.json").read_bytes()),
            "--evaluation-intent", str(self.paired / "evaluation_intent.json"), "--evaluation-intent-sha256", "0" * 64,
            "--gold", str(self.root / "never-read-gold.json"), "--gold-sha256", "0" * 64,
            "--output", str(self.root / "rejected-evaluator")], cwd=ROOT, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        failure = get(self.root / "rejected-evaluator/failure.json")
        self.assertIn("frozen input bytes changed", failure["message"])
        self.assertFalse((self.root / "rejected-evaluator/boundary.json").exists())


class SmallBoundaryTests(unittest.TestCase):
    def escaped_subject(self, root, delay=120):
        pidfile = Path(root) / "escaped.json"
        leaf = ("import json,os,pathlib,sys,time;"
                "pathlib.Path(sys.argv[1]).write_text(json.dumps({'pid':os.getpid(),'sid':os.getsid(0)}));"
                "time.sleep(120)")
        parent = ("import subprocess,sys,time;"
                  "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]],start_new_session=True);"
                  "time.sleep(float(sys.argv[3]))")
        return [sys.executable, "-c", parent, leaf, str(pidfile), str(delay)], pidfile

    @requires_linux("Linux pidfds and exact lineage cleanup across descendant setsid")
    def test_setsid_escape_is_killed_reaped_without_touching_existing_child(self):
        with tempfile.TemporaryDirectory() as d:
            sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
            tree = controller.OwnedTree()
            cmd, pidfile = self.escaped_subject(d)
            child = subprocess.Popen(cmd, start_new_session=True)
            escaped = None
            try:
                end = time.monotonic() + 3
                while not pidfile.exists() and time.monotonic() < end: time.sleep(.01)
                self.assertTrue(pidfile.exists())
                escaped = get(pidfile)["pid"]
                self.assertNotEqual(os.getsid(child.pid), get(pidfile)["sid"])
                rc, timeout = controller.wait_owned(child, .05, process_group=True, ownership=tree)
                self.assertTrue(timeout)
                self.assertLess(rc, 0)
                self.assertTrue(tree.proven)
                self.assertIsNone(sentinel.poll())
                with self.assertRaises(ProcessLookupError): os.kill(escaped, 0)
                with self.assertRaises(ChildProcessError): os.waitpid(escaped, os.WNOHANG)
            finally:
                if child.poll() is None: child.kill(); child.wait()
                if escaped is not None:
                    try: os.kill(escaped, signal.SIGKILL)
                    except ProcessLookupError: pass
                    try: os.waitpid(escaped, 0)
                    except ChildProcessError: pass
                sentinel.kill(); sentinel.wait()

    @requires_linux("Normal leader exit must not leave an escaped owned descendant")
    def test_normal_exit_with_live_descendant_is_cleaned_but_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            tree = controller.OwnedTree()
            cmd, pidfile = self.escaped_subject(d, .2)
            child = subprocess.Popen(cmd, start_new_session=True)
            with self.assertRaisesRegex(controller.CleanupFailure, "leader exited"):
                controller.wait_owned(child, 3, ownership=tree)
            self.assertTrue(tree.proven)
            with self.assertRaises(ProcessLookupError): os.kill(get(pidfile)["pid"], 0)

    @requires_linux("Unattributed adopted children must not be killed or falsely sealed")
    def test_unattributed_child_fails_cleanup_without_signaling_it(self):
        tree = controller.OwnedTree()
        unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(120)"])
        child = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(120)"])
        try:
            with self.assertRaisesRegex(controller.CleanupFailure, "unattributed"):
                controller.wait_owned(child, .05, ownership=tree)
            self.assertFalse(tree.proven)
            self.assertIsNone(unrelated.poll())
            self.assertIsNotNone(child.poll())
        finally:
            if child.poll() is None: child.kill(); child.wait()
            unrelated.kill(); unrelated.wait()

    @requires_linux("Owned Linux process-group SIGKILL and waitpid reaping")
    def test_whole_process_group_watchdog_terminates_owned_subprocess(self):
        # Match production: unrelated children may already exist in an aggregate
        # test process, so establish ownership before spawning this worker.
        ownership = controller.OwnedTree()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True)
        rc, timeout = controller.wait_owned(child, .05, process_group=True, ownership=ownership)
        self.assertTrue(timeout)
        self.assertLess(rc, 0)
        self.assertIsNotNone(child.poll())

    @requires_linux("Inspection failure must stop the owned child without a false cleanup seal")
    def test_inspection_failure_cleans_direct_child_and_latches_failure(self):
        for already_pinned in (False, True):
            tree = controller.OwnedTree()
            child = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(120)"])
            try:
                if already_pinned:
                    tree.attach(child)
                with patch.object(controller, "_process_snapshot", side_effect=OSError("inspection unavailable")):
                    with self.assertRaises(OSError):
                        controller.wait_owned(child, .05, ownership=tree)
                self.assertIsNotNone(child.poll())
                self.assertFalse(tree.proven)
                self.assertTrue(tree.failed)
                with self.assertRaisesRegex(controller.CleanupFailure, "prior ownership"):
                    tree.terminate()
                self.assertFalse(tree.proven)
            finally:
                if child.poll() is None: child.kill(); child.wait()

    def test_clock_is_inherited_not_reset_and_late_is_not_completed(self):
        now = time.monotonic()
        deadline = common.inherited(60, now - 46)
        self.assertEqual(deadline.start, now - 46)
        self.assertGreater(deadline.remaining(), 0)
        self.assertEqual(deadline.work_remaining(), 0)
        with self.assertRaises(base.BudgetExceeded): deadline.check()

    def test_unsupported_platform_is_rejected_without_launch(self):
        with patch.object(sys, "platform", "win32"), self.assertRaisesRegex(ValueError, "requires Linux"):
            controller.require_linux()

    @requires_linux("POSIX symlink ancestry rejection before output writes")
    def test_symlink_output_parent_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "actual").mkdir()
            (root / "link").symlink_to(root / "actual", target_is_directory=True)
            with self.assertRaises((ValueError, OSError)):
                common.new_artifacts(root / "link/out")
            self.assertFalse((root / "actual/out").exists())

    @unittest.skipUnless(importlib.util.find_spec("torch"), "optional torch is required for actual CPU causal tensor math")
    def test_actual_cpu_causal_loss_full_answer_eos_only(self):
        import torch
        answer = contract.answer_ids([[1, 2]])
        p = 7
        logits = torch.randn(1, p + len(answer) - 1, 16, generator=torch.Generator().manual_seed(7))
        measured = base.full_answer_nll(logits, p, answer)
        expected = sum(float(-torch.log_softmax(logits[0, p - 1 + j], -1)[token]) for j, token in enumerate(answer))
        self.assertAlmostEqual(measured, expected, places=5)
        logits[:, :p - 1, :] = 1000
        self.assertAlmostEqual(base.full_answer_nll(logits, p, answer), measured)

    def test_atomic_artifacts_cannot_replace_prior_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            art = base.Artifacts(Path(d) / "owned")
            art.write("pool.json", {"raw": [1]})
            with self.assertRaises(FileExistsError): art.write("pool.json", {"raw": [2]})
            self.assertEqual(get(art.root / "pool.json"), {"raw": [1]})


if __name__ == "__main__":
    unittest.main()
