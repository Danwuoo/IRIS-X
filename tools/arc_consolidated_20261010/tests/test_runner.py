"""Runner tests use explicit synthetic mode; no runtime8/model acceptance."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

from tools.arc_consolidated_20261010 import runner, evidence
from tools.arc_consolidated_20261010.ledger import Ledger, digest, BudgetExceeded
from tools.arc_consolidated_20261010.tests.support import TemporaryDirectory


class RunnerTests(unittest.TestCase):
    def test_inert_no_asset_model_or_output_access(self):
        with patch.object(runner.assets, "load_demos", side_effect=AssertionError("asset read")), \
             patch.object(runner.evidence, "safe_root", side_effect=AssertionError("write")):
            self.assertEqual(runner.run("unused", enable_model=True)["status"], "INACTIVE")

    def test_flags_and_smoke_reject_model_enable(self):
        with self.assertRaises(ValueError):
            runner.run("unused", manual_start=1)
        with self.assertRaisesRegex(ValueError, "CPU-only"):
            runner.run("unused", manual_start=True, enable_model=True)

    def test_exact_physical_caps(self):
        smoke = runner.limits_for("SMOKE")
        full = runner.limits_for("FULL")
        self.assertEqual(smoke["coverage_checks"], 128 * 8 + 128)
        self.assertEqual(full["coverage_checks"], 5965 * 8 + 128)
        self.assertEqual(full["cpu_checks"], 47848 + 80 + 3 * 3 * 8 * 64)
        self.assertEqual(full["gas"], 10507200000)
        self.assertEqual(full["physical_calls"], 80)

    def test_missing_linux_produces_complete_diagnostic_archive(self):
        with TemporaryDirectory() as td, patch.object(runner.verifier, "capability", return_value={
            "available": False, "reason": "synthetic unavailable capability; no execution"}):
            result = runner.run(Path(td) / "run", manual_start=True)
            self.assertEqual(result["status"], "partial-inconclusive")
            report = result["report"]
            self.assertFalse(report["gate"]["passed"])
            self.assertEqual(report["coverage"]["planned"], 1024)
            self.assertEqual(report["coverage"]["missing"], 1024)
            self.assertEqual(report["controls"]["missing"], 128)
            self.assertEqual(report["final_accounting"]["charged"]["cpu_checks"], 0)
            self.assertEqual(report["final_accounting"]["charged"]["physical_calls"], 0)
            self.assertIsNotNone(result["archive"])
            with zipfile.ZipFile(result["archive"]["archive"]) as archive:
                seal = json.loads(archive.read("global-seal.json"))
                self.assertTrue(seal["processes"]["model_owner_stopped"])
                self.assertTrue(seal["processes"]["verifier_descendants_stopped"])
                self.assertTrue(any("coverage" in name for name in archive.namelist()))

    def test_synthetic_provider_cannot_enter_production(self):
        with self.assertRaisesRegex(ValueError, "production ledger"):
            runner._run("unused", _test_verify=lambda *a, **k: None)

    def test_outer_no_go_resume_with_unconfirmed_prior_model_ownership_withholds_seal(self):
        for previous in ("unknown-owner", "false-owner-stop", "load-without-owner"):
            with self.subTest(previous=previous), TemporaryDirectory() as td, patch.object(
                    runner.verifier, "capability", return_value={"available": False, "reason": "synthetic no-go"}):
                root = Path(td) / "run"
                first = runner._run(root, evidence_mode="synthetic-test-only")
                self.assertIsNotNone(first["archive"])
                binding = json.loads((root / "run-binding.json").read_bytes())
                ledger = Ledger(root / "ledger", binding["bindings"], binding["limits"])
                with ledger.session(session_seconds=100):
                    if previous == "load-without-owner":
                        ledger.reserve("overhead", "load/prior", {"load_seconds": 1})
                        ledger.finish("load/prior")
                    else:
                        ledger.reserve("overhead", "owner/prior", {"physical_calls": 0})
                        if previous == "false-owner-stop":
                            ledger.record_response("owner/prior", {"model_owner_stopped": False})
                            ledger.finish("owner/prior", outcome="fail")
                archives_before = set((root / "archives").glob("*.zip"))
                # On one arm, complete all CPU work with an explicitly synthetic
                # mismatch callback. Even complete CPU coverage cannot attest
                # that a previous model owner stopped.
                resume_verify = (lambda *a, **k: {"status": "mismatch", "known": True,
                    "all_demos_fit": False, "gas": 1, "wall_seconds": 0.001,
                    "dispatched": True, "owned_descendants_stopped": True}) if previous == "unknown-owner" else None
                resumed = runner._run(root, resume=True, evidence_mode="synthetic-test-only", _test_verify=resume_verify)
                self.assertFalse(resumed["report"]["gate"]["passed"])
                self.assertEqual(resumed["status"], "partial-inconclusive")
                self.assertFalse(resumed["report"]["processes"]["model_owner_stopped"])
                self.assertFalse(resumed["report"]["prior_model_owner_stopped"])
                self.assertIn("withheld", resumed["report"]["global_seal"])
                self.assertIsNone(resumed["archive"])
                self.assertEqual(set((root / "archives").glob("*.zip")), archives_before)
                self.assertEqual(resumed["report"]["coverage"]["planned"], 1024)
                if previous == "unknown-owner":
                    self.assertTrue(resumed["report"]["coverage"]["complete"])
                    self.assertTrue(resumed["report"]["controls"]["complete"])

    def test_prior_stop_helper_requires_every_owner_ack_and_settled_model_load(self):
        cases = [
            ({}, {}, True),
            ({"model/root": {"kind": "model", "status": "complete"}}, {}, False),
            ({"load/prior": {"kind": "overhead", "status": "complete"}}, {}, False),
            ({"owner/prior": {"kind": "overhead", "status": "complete"}}, {}, False),
        ]
        stopped_owner = {"kind": "overhead", "status": "complete", "response": {"file": "test"}}
        cases.append(({"owner/older": stopped_owner, "load/newer": {"kind": "overhead", "status": "complete"}},
                      {"owner/older": {"model_owner_stopped": True}}, False))
        for status in ("reserved", "unknown"):
            for operation, kind in (("model/root", "model"), ("load/prior", "overhead")):
                cases.append(({"owner/prior": stopped_owner, operation: {"kind": kind, "status": status}},
                              {"owner/prior": {"model_owner_stopped": True}}, False))
        for ack in (False, None, 1, True):
            cases.append(({"owner/prior": stopped_owner, "model/root": {"kind": "model", "status": "complete"}},
                          {"owner/prior": {"model_owner_stopped": ack}}, ack is True))
        cases.append(({"owner/prior": stopped_owner, "owner/older": stopped_owner},
                      {"owner/prior": {"model_owner_stopped": True}, "owner/older": {"model_owner_stopped": False}}, False))
        for operations, responses, expected in cases:
            with self.subTest(operations=operations, responses=responses):
                ledger = unittest.mock.Mock()
                ledger.summary.return_value = {"operations": operations}
                ledger.get_response.side_effect = responses.__getitem__
                self.assertIs(runner._prior_model_stopped(ledger), expected)


class EvidenceTests(unittest.TestCase):
    def test_stage_does_not_claim_solver_stop(self):
        with TemporaryDirectory() as td:
            path = evidence.stage_snapshot(td, "controls", {"complete": True}, session_id="one")
            self.assertIn("may remain loaded", json.loads(path.read_bytes())["closure_scope"])

    def test_global_seal_fails_without_proven_stop(self):
        with TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                evidence.seal_and_archive(td, stopped={"model_owner_stopped": False,
                                                       "verifier_descendants_stopped": True},
                                          summary={}, session_id="one")
            self.assertFalse((Path(td) / "archives").exists())

    def test_seal_interruption_preserves_partial_and_new_snapshot(self):
        with TemporaryDirectory() as td:
            evidence.write_new(Path(td) / "receipt.json", {"receipt": 1})
            stopped = {"model_owner_stopped": True, "verifier_descendants_stopped": True}
            with patch.object(evidence.os, "replace", side_effect=OSError("crash before archive rename")):
                with self.assertRaises(OSError):
                    evidence.seal_and_archive(td, stopped=stopped, summary={}, session_id="one")
            partial = Path(td) / "archives/evidence-one.zip.partial"
            before = partial.read_bytes()
            result = evidence.seal_and_archive(td, stopped=stopped, summary={}, session_id="two")
            self.assertEqual(partial.read_bytes(), before)
            self.assertTrue(Path(result["archive"]).is_file())

    def test_new_directory_parent_flush(self):
        with TemporaryDirectory() as td, patch.object(evidence, "fsync_directory", return_value=True) as flush:
            target = Path(td) / "a/b"
            evidence.safe_root(target)
            self.assertIn(unittest.mock.call(Path(td)), flush.call_args_list)
            self.assertIn(unittest.mock.call(Path(td) / "a"), flush.call_args_list)

    def test_receipt_overwrite_and_archive_reuse_reject(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "one.json"
            evidence.write_new(path, {"a": 1})
            with self.assertRaises(ValueError):
                evidence.write_new(path, {"a": 2})
            stopped = {"model_owner_stopped": True, "verifier_descendants_stopped": True}
            evidence.seal_and_archive(td, stopped=stopped, summary={}, session_id="one")
            with self.assertRaises(ValueError):
                evidence.seal_and_archive(td, stopped=stopped, summary={}, session_id="one")


class AccountedVerifierTests(unittest.TestCase):
    task = {"task_id": "synthetic", "demos": [{"input": [[1]], "output": [[1]]}]}
    plan = {"steps": [{"op": "identity"}]}

    def ledger(self, path, profile="SMOKE"):
        limits = runner.limits_for(profile)
        bindings = {key: digest(key) for key in ("source", "task", "model", "prompt", "sampling")}
        bindings.update(budget=digest(limits), mode=digest("synthetic-test-only"))
        return Ledger(path, bindings, limits)

    def checked(self, ledger, verify_fn, resume=False):
        return runner.AccountedVerifier(ledger, cpu_deadline=runner.time.monotonic() + 100,
                                         capability={"available": True}, resume=resume, verify_fn=verify_fn)

    @staticmethod
    def result(known=False, stopped=True):
        return {"status": "fit" if known else "unknown", "known": known, "all_demos_fit": known,
                "gas": 7 if known else None, "wall_seconds": .1, "dispatched": True,
                "owned_descendants_stopped": stopped}

    def model_response(self, ledger, call_id="root-one"):
        ledger.reserve("model", "model/" + call_id, {})
        ledger.record_response("model/" + call_id, {"text": json.dumps(self.plan)})
        ledger.finish("model/" + call_id)

    def test_resumed_stopped_unknown_uses_new_cpu_id_and_same_model_response(self):
        calls = []
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger"
            with self.ledger(path, "FULL").session(session_seconds=1000) as ledger:
                self.model_response(ledger)
                checked = self.checked(ledger, lambda *a, **k: self.result())
                self.assertFalse(checked(self.task, self.plan, scope="model", call_id="root-one")["known"])
            with self.ledger(path, "FULL").session(session_seconds=1000) as ledger:
                def verify(*args, **kwargs):
                    calls.append(ledger.operation("cpu/model/root-one/verification-2")["status"])
                    return self.result(known=True)
                checked = self.checked(ledger, verify, resume=True)
                self.assertTrue(checked(self.task, self.plan, scope="model", call_id="root-one")["known"])
                self.assertTrue(checked(self.task, self.plan, scope="model", call_id="root-one")["known"])
                self.assertTrue(checked.all_stopped)
                self.assertEqual(calls, ["reserved"])
                self.assertEqual(ledger.summary()["charged"]["physical_calls"], 1)
                self.assertEqual(ledger.summary()["charged"]["model_checks"], 2)
                self.assertEqual(ledger.summary()["charged"]["unknown_verifications"], 1)
                new = ledger.operation("cpu/model/root-one/verification-2")
                self.assertEqual(new["metadata"]["model_response_sha256"],
                                 ledger.operation("model/root-one")["response"]["sha256"])

    def test_same_session_unknown_is_cached_and_resume_does_not_loop(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger"
            for iteration in range(2):
                with self.ledger(path, "FULL").session(session_seconds=1000) as ledger:
                    if iteration == 0:
                        self.model_response(ledger)
                    verify = unittest.mock.Mock(return_value=self.result())
                    checked = self.checked(ledger, verify, resume=iteration > 0)
                    for _ in range(3):
                        self.assertFalse(checked(self.task, self.plan, scope="model", call_id="root-one")["known"])
                    self.assertEqual(verify.call_count, 1)
                    self.assertEqual(ledger.summary()["charged"]["model_checks"], iteration + 1)
                    self.assertEqual(ledger.summary()["charged"]["physical_calls"], 1)

    def test_model_verification_without_stop_or_response_never_retries(self):
        for mode in ("no-response", "no-stop"):
            with self.subTest(mode=mode), TemporaryDirectory() as td:
                path = Path(td) / "ledger"
                with self.ledger(path, "FULL").session(session_seconds=1000) as ledger:
                    self.model_response(ledger)
                    verify = unittest.mock.Mock(side_effect=RuntimeError("no stop") if mode == "no-response" else None,
                                                return_value=self.result(stopped=False))
                    checked = self.checked(ledger, verify)
                    if mode == "no-response":
                        with self.assertRaises(RuntimeError):
                            checked(self.task, self.plan, scope="model", call_id="root-one")
                    else:
                        checked(self.task, self.plan, scope="model", call_id="root-one")
                with self.ledger(path, "FULL").session(session_seconds=1000) as ledger:
                    verify = unittest.mock.Mock(side_effect=AssertionError("must not redispatch"))
                    checked = self.checked(ledger, verify, resume=True)
                    self.assertFalse(checked(self.task, self.plan, scope="model", call_id="root-one")["known"])
                    self.assertFalse(checked.all_stopped)
                    self.assertEqual(verify.call_count, 0)
                    self.assertIsNone(ledger.operation("cpu/model/root-one/verification-2"))

    def test_saved_suffix_response_is_finished_and_reused_without_dispatch(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger"
            with self.ledger(path, "FULL").session(session_seconds=1000) as ledger:
                self.model_response(ledger)
                self.checked(ledger, lambda *a, **k: self.result())(
                    self.task, self.plan, scope="model", call_id="root-one")
                original = ledger.operation("cpu/model/root-one")
                ledger.reserve("cpu", "cpu/model/root-one/verification-2", original["budget"],
                               metadata=original["metadata"])
                ledger.record_response("cpu/model/root-one/verification-2", self.result(known=True))
            with self.ledger(path, "FULL").session(session_seconds=1000) as ledger:
                checked = self.checked(ledger, unittest.mock.Mock(side_effect=AssertionError("redispatch")), resume=True)
                self.assertTrue(checked(self.task, self.plan, scope="model", call_id="root-one")["known"])
                self.assertEqual(ledger.operation("cpu/model/root-one/verification-2")["status"], "complete")
                self.assertEqual(ledger.summary()["operation_states"]["responded"], 0)
                self.assertEqual(ledger.summary()["charged"]["unknown_verifications"], 1)
                self.assertEqual(ledger.summary()["charged"]["gas"], 200007)

    def test_model_reverification_cannot_exceed_fixed_eighty_check_cap(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger"
            with self.ledger(path, "FULL").session(session_seconds=1000) as ledger:
                self.model_response(ledger)
                self.checked(ledger, lambda *a, **k: self.result())(
                    self.task, self.plan, scope="model", call_id="root-one")
                ledger.reserve("cpu", "other-model-checks", {"cpu_checks": 79, "model_checks": 79})
                ledger.record_response("other-model-checks", self.result(known=True))
                ledger.finish("other-model-checks")
            with self.ledger(path, "FULL").session(session_seconds=1000) as ledger:
                verify = unittest.mock.Mock(side_effect=AssertionError("stage cap bypass"))
                checked = self.checked(ledger, verify, resume=True)
                with self.assertRaises(BudgetExceeded):
                    checked(self.task, self.plan, scope="model", call_id="root-one")
                self.assertEqual(verify.call_count, 0)
                self.assertEqual(ledger.summary()["charged"]["model_checks"], 80)
                self.assertEqual(ledger.summary()["charged"]["physical_calls"], 1)

    def test_model_cpu_requires_matching_durable_response(self):
        with TemporaryDirectory() as td, self.ledger(Path(td) / "ledger", "FULL").session(session_seconds=1000) as ledger:
            verify = unittest.mock.Mock(side_effect=AssertionError("unbound CPU work"))
            checked = self.checked(ledger, verify, resume=True)
            result = checked(self.task, self.plan, scope="model", call_id="absent-model")
            self.assertFalse(result["known"])
            self.assertEqual(ledger.summary()["charged"]["cpu_checks"], 0)
            self.model_response(ledger)
            with self.assertRaisesRegex(ValueError, "durable model response"):
                checked(self.task, {"steps": [{"op": "flip_horizontal"}]}, scope="model", call_id="root-one")
            self.assertEqual(verify.call_count, 0)

    def test_thrown_verifier_and_two_resumes_never_dispatch_or_attest_stop(self):
        calls = []
        def fail(*args, **kwargs):
            calls.append(1)
            raise RuntimeError("synthetic interrupted child with no stop ack")
        with TemporaryDirectory() as td:
            for iteration in range(3):
                with self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
                    checked = self.checked(ledger, fail, iteration > 0)
                    if iteration == 0:
                        with self.assertRaises(RuntimeError):
                            checked(self.task, self.plan)
                    else:
                        self.assertEqual(checked(self.task, self.plan)["status"], "unknown")
                    self.assertFalse(checked.all_stopped)
                    self.assertEqual(ledger.summary()["charged"]["cpu_checks"], 1)
            self.assertEqual(len(calls), 1)

    def test_durable_unreaped_response_remains_unreaped_on_resume(self):
        result = {"status": "unknown", "known": False, "all_demos_fit": False, "gas": None,
                  "wall_seconds": .1, "dispatched": True, "owned_descendants_stopped": False}
        with TemporaryDirectory() as td:
            for iteration in range(2):
                with self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
                    checked = self.checked(ledger, lambda *a, **k: result, iteration > 0)
                    self.assertEqual(checked(self.task, self.plan)["status"], "unknown")
                    self.assertFalse(checked.all_stopped)
                    self.assertEqual(ledger.summary()["charged"]["unknown_verifications"], 1)

    def test_unknown_observed_cleanup_overrun_is_charged(self):
        result = {"status": "unknown", "known": False, "all_demos_fit": False, "gas": None,
                  "wall_seconds": 20, "dispatched": True, "owned_descendants_stopped": True}
        with TemporaryDirectory() as td, self.ledger(Path(td) / "ledger").session(session_seconds=1000) as ledger:
            checked = self.checked(ledger, lambda *a, **k: result)
            with self.assertRaises(BudgetExceeded):
                checked(self.task, self.plan)
            charged = ledger.summary()["charged"]
            self.assertEqual(charged["verifier_seconds"], 20)
            self.assertEqual(charged["gas"], 200000)

    def test_stage_counters_reject_fraction_and_bool(self):
        for bad in (True, .5):
            limits = runner.limits_for("SMOKE")
            limits["coverage_checks"] = bad
            bindings = {key: digest(key) for key in ("source", "task", "model", "prompt", "sampling", "mode")}
            bindings["budget"] = digest(limits)
            with self.assertRaises(ValueError):
                Ledger("unused", bindings, limits)


if __name__ == "__main__":
    unittest.main()
