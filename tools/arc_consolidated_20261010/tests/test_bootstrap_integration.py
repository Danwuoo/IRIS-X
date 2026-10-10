"""Mock-only bootstrap orchestration; no install, model, GPU or Dataset reads."""
from contextlib import contextmanager, ExitStack
from dataclasses import asdict
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

from tools.arc_consolidated_20261010 import assets, evidence, ledger as ledger_module
from tools.arc_consolidated_20261010 import offline_bootstrap, runner, study_runner
from tools.arc_consolidated_20261010.ledger import BudgetExceeded, Ledger, digest
from tools.arc_consolidated_20261010.tests.support import TemporaryDirectory


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value


class BootstrapIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.scratch = TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name)
        self.root = self.base / "run"
        self.source_root = self.base / "source"
        self.source = {"runner.py": digest("synthetic runner"),
                       "remote_model_owner.py": digest("synthetic owner")}
        self.overlay = {"tools/arc_consolidated_20261010/" + k: v
                        for k, v in self.source.items()}
        self.overlay["tools/__init__.py"] = digest("synthetic initializer")
        self.plan = offline_bootstrap.plan_config({}, str(self.base / "run-environment"))
        self.proof = {name: {"owned_group_stopped": True, "leader_reaped": True,
                             "live_group_members": 0} for name in ("material", "install")}
        self.prepared = {"status": "prepared", "child_stop_proof": self.proof,
            "environment_plan_sha256": self.plan["plan_sha256"],
            "python_command": [str(Path(sys.executable).absolute()), "-I", "-B", "-S"],
            "source_root": str(self.source_root), "model_path": str(self.base / "model"),
            "manifest_path": str(self.base / "model-manifest.json"),
            "environment_lock_path": str(self.base / "environment-lock.json"),
            "actual_environment_lock_sha256": digest("actual installed environment"),
            "asset_receipts": {"synthetic": True, "bytes_checked": 0}}
        self.bounds = {**runner.limits_for("FULL"), "wall_seconds": 1000, "load_seconds": 100}
        self.bindings = {name: digest("synthetic " + name)
                         for name in ("task", "model", "prompt", "sampling", "mode")}
        self.bindings.update(source=digest(self.source), budget=digest(self.bounds))

    def ledger(self):
        return Ledger(self.root / "ledger", self.bindings, self.bounds)

    @contextmanager
    def source_patches(self):
        with patch.object(assets, "source_identity", return_value=self.source), \
             patch.object(assets, "executable_identity", return_value=self.overlay):
            yield

    def test_reservation_is_fsynced_before_prepare_and_success_admission_is_immutable(self):
        clock = Clock()
        fsynced = []
        real_fsync = ledger_module.os.fsync
        ledger = self.ledger()

        def observe_fsync(fd):
            real_fsync(fd)
            rows = [json.loads(line) for line in ledger.journal_path.read_bytes().splitlines()]
            fsynced.append((rows[-1]["event"], rows[-1]["data"].get("id")))

        def prepare(plan, **kwargs):
            self.assertEqual(plan, self.plan)
            self.assertIs(kwargs["enable_model"], True)
            self.assertEqual(kwargs["deadline_seconds"], 100)
            self.assertIn(("reserve", "bootstrap/one"), fsynced)
            self.assertEqual(ledger.operation("bootstrap/one")["status"], "reserved")
            clock.value += 2
            return copy.deepcopy(self.prepared)

        with self.source_patches(), patch.object(runner.time, "monotonic", clock), \
             ledger.session(session_seconds=200), \
             patch.object(ledger_module.os, "fsync", side_effect=observe_fsync), \
             patch.object(offline_bootstrap, "prepare_model_environment", side_effect=prepare):
            config, receipt = runner._bootstrap_environment(self.plan, {"passed": True}, ledger, self.root, "one")
            ready = config["prepared_bootstrap"]
            admission_path = Path(ready["admission_path"])
            admission = json.loads(admission_path.read_bytes())
            expected_fields = {"python_command", "source_root", "model_path", "manifest_path",
                               "environment_lock_path", "actual_environment_lock_sha256"}
            self.assertEqual(set(admission["prepared"]), expected_fields)
            self.assertEqual(set(admission), {"format", "environment_plan_sha256", "source_identity_sha256",
                                              "prepared", "asset_receipts_sha256"})
            self.assertEqual(admission["prepared"], {key: self.prepared[key] for key in expected_fields})
            self.assertEqual(admission["source_identity_sha256"], digest(self.overlay))
            self.assertEqual(admission["asset_receipts_sha256"], digest(self.prepared["asset_receipts"]))
            self.assertEqual(ready["admission_sha256"], hashlib.sha256(admission_path.read_bytes()).hexdigest())
            self.assertEqual((self.root / "runtime" / "environment-binding.json").read_bytes(), admission_path.read_bytes())
            with self.assertRaisesRegex(ValueError, "changed immutable receipt"):
                evidence.write_new(admission_path, {**admission, "format": "changed"})
            self.assertEqual(config["environment_sha256"], self.plan["plan_sha256"])
            self.assertNotEqual(config["environment_sha256"], ready["actual_environment_lock_sha256"])
            self.assertEqual(receipt["elapsed_seconds"], 2)
            self.assertEqual(ledger.summary()["charged"]["load_seconds"], 2)
            self.assertTrue(runner._prior_model_stopped(ledger))

    def test_structured_failure_retains_stop_proof_and_full_reservation_on_resume(self):
        error = offline_bootstrap.BootstrapError("synthetic install failure")
        error.child_stop_proof = self.proof
        with self.source_patches(), self.ledger().session(session_seconds=200) as ledger, \
             patch.object(offline_bootstrap, "prepare_model_environment", side_effect=error):
            with self.assertRaises(offline_bootstrap.BootstrapError):
                runner._bootstrap_environment(self.plan, {"passed": True}, ledger, self.root, "failed")
            receipt = ledger.get_response("bootstrap/failed")
            self.assertIs(receipt["bootstrap_stopped"], True)
            self.assertEqual(receipt["child_stop_proof"], self.proof)
            self.assertEqual(ledger.operation("bootstrap/failed")["status"], "fail")
            self.assertEqual(ledger.summary()["charged"]["load_seconds"], 100)
        with self.ledger().session(session_seconds=100) as ledger:
            self.assertTrue(runner._prior_model_stopped(ledger))
            self.assertEqual(ledger.summary()["charged"]["load_seconds"], 100)

    def test_unknown_or_missing_bootstrap_stop_cannot_be_promoted(self):
        for state, response, expected in (("reserved", None, False), ("unknown", None, False),
                ("responded", {"bootstrap_stopped": True}, False), ("complete", None, False),
                ("fail", {"bootstrap_stopped": False}, False), ("complete", {"bootstrap_stopped": 1}, False),
                ("fail", {"bootstrap_stopped": True}, True)):
            with self.subTest(state=state, response=response):
                operation = {"kind": "overhead", "status": state}
                if response is not None:
                    operation["response"] = {"file": "synthetic"}
                fake = unittest.mock.Mock()
                fake.summary.return_value = {"operations": {"bootstrap/prior": operation}}
                fake.get_response.return_value = response
                self.assertIs(runner._prior_model_stopped(fake), expected)

    def test_observed_bootstrap_overrun_is_retained_and_blocks_resumed_prepare(self):
        self.bounds["load_seconds"] = 10
        self.bindings["budget"] = digest(self.bounds)
        clock = Clock()

        def prepare(*args, **kwargs):
            clock.value += 11
            raise offline_bootstrap.BootstrapError("slow synthetic failure")

        with self.source_patches(), patch.object(runner.time, "monotonic", clock), \
             self.ledger().session(session_seconds=200) as ledger, \
             patch.object(offline_bootstrap, "prepare_model_environment", side_effect=prepare) as prepare_mock:
            with self.assertRaisesRegex(BudgetExceeded, "overrun"):
                runner._bootstrap_environment(self.plan, {"passed": True}, ledger, self.root, "overrun")
            self.assertEqual(ledger.summary()["charged"]["load_seconds"], 11)
            self.assertTrue(ledger.summary()["reservation_overrun"])
            self.assertEqual(prepare_mock.call_count, 1)
        with self.ledger().session(session_seconds=200) as ledger, \
             patch.object(offline_bootstrap, "prepare_model_environment") as prepare_mock:
            with self.assertRaises(BudgetExceeded):
                runner._bootstrap_environment(self.plan, {"passed": True}, ledger, self.root, "resume")
            self.assertTrue(ledger.summary()["reservation_overrun"])
            prepare_mock.assert_not_called()

    def test_source_drift_rejected_before_admission(self):
        with self.source_patches(), self.ledger().session(session_seconds=200) as ledger, \
             patch.object(assets, "executable_identity", return_value={**self.overlay,
                "tools/arc_consolidated_20261010/runner.py": digest("changed")}), \
             patch.object(offline_bootstrap, "prepare_model_environment", return_value=self.prepared):
            with self.assertRaisesRegex(ValueError, "frozen CPU-gate source"):
                runner._bootstrap_environment(self.plan, {"passed": True}, ledger, self.root, "changed")
            self.assertFalse((self.root / "runtime").exists())
            self.assertTrue(runner._prior_model_stopped(ledger))

    def test_actual_environment_drift_rejected_before_new_admission(self):
        with self.source_patches(), self.ledger().session(session_seconds=200) as ledger, \
             patch.object(offline_bootstrap, "prepare_model_environment", return_value=self.prepared):
            runner._bootstrap_environment(self.plan, {"passed": True}, ledger, self.root, "first")
        frozen = (self.root / "runtime" / "environment-binding.json").read_bytes()
        changed = {**self.prepared, "actual_environment_lock_sha256": digest("changed actual environment")}
        with self.source_patches(), self.ledger().session(session_seconds=200) as ledger, \
             patch.object(offline_bootstrap, "prepare_model_environment", return_value=changed):
            with self.assertRaisesRegex(ValueError, "changed immutable receipt"):
                runner._bootstrap_environment(self.plan, {"passed": True}, ledger, self.root, "resume")
            self.assertEqual(ledger.operation("bootstrap/resume")["status"], "fail")
        self.assertEqual((self.root / "runtime" / "environment-binding.json").read_bytes(), frozen)
        self.assertFalse((self.root / "runtime" / "admission-resume.json").exists())

    def test_root_admission_is_accepted_by_remote_owner_source_only_validator(self):
        from tools.arc_consolidated_20261010 import remote_model_owner

        for name, payload in (("tools/arc_consolidated_20261010/runner.py", "synthetic runner"),
                ("tools/arc_consolidated_20261010/remote_model_owner.py", "synthetic owner"),
                ("tools/__init__.py", "synthetic initializer")):
            path = self.source_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(assets.canonical(payload))
        lock = Path(self.prepared["environment_lock_path"])
        lock.write_bytes(assets.canonical({"synthetic_test_only": True}))
        self.prepared["actual_environment_lock_sha256"] = hashlib.sha256(lock.read_bytes()).hexdigest()
        with self.source_patches(), self.ledger().session(session_seconds=200) as ledger, \
             patch.object(offline_bootstrap, "prepare_model_environment", return_value=self.prepared):
            config, _ = runner._bootstrap_environment(self.plan, {"passed": True}, ledger, self.root, "remote")
            verified = remote_model_owner._admission(config["prepared_bootstrap"],
                self.plan["plan_sha256"], self.overlay, synthetic=True)
        self.assertEqual(set(verified), set(self.overlay))
        self.assertEqual({name: hashlib.sha256(raw).hexdigest() for name, raw in verified.items()}, self.overlay)

    @contextmanager
    def fast_runner(self, *, gate_passed):
        # Real outer orchestration/ledger/evidence, with scientific stages
        # replaced by explicit fixtures. This does not attest a production gate.
        plans = [{"synthetic": "placeholder"}]
        profiles = copy.deepcopy(runner.PROFILES)
        profiles["FULL"]["candidates"] = 1
        with ExitStack() as stack:
            stack.enter_context(self.source_patches())
            for target, name, value in ((runner, "PROFILES", profiles),
                    (runner, "BASE_SHA256", digest(plans)), (runner, "CONTROLS_SHA256", digest([]))):
                stack.enter_context(patch.object(target, name, value))
            for target, name, value in ((runner.ir, "base_inventory", plans),
                    (runner.ir, "inventory_manifest", {}), (runner, "synthetic_controls", []),
                    (runner.verifier, "capability", {"available": False, "reason": "mock-only orchestration"}),
                    (runner.stages, "freeze_base_inventory", []),
                    (runner.stages, "run_controls", {"complete": True}),
                    (runner.stages, "run_coverage", {"complete": True, "tasks": []}),
                    (runner.stages, "testability_gate", {"passed": gate_passed}),
                    (runner.stages, "summarize_ordering", {})):
                stack.enter_context(patch.object(target, name, return_value=value))
            yield

    def test_outer_disabled_and_no_go_never_prepare_or_load_model(self):
        for enabled, passed in ((False, True), (True, False)):
            with self.subTest(enabled=enabled, passed=passed), self.fast_runner(gate_passed=passed), \
                 patch.object(offline_bootstrap, "prepare_model_environment") as prepare, \
                 patch.object(study_runner, "run_model_studies") as study:
                result = runner.run(self.base / ("case-" + str(enabled)), manual_start=True,
                                    profile="FULL", enable_model=enabled, session_seconds=200)
                self.assertEqual(result["status"], "complete")
                prepare.assert_not_called()
                study.assert_not_called()

    def test_outer_passed_gate_prepares_before_study_and_environment_stays_outside_archive(self):
        events = []

        def prepare(plan, **kwargs):
            events.append("prepare")
            self.assertTrue(kwargs["gate_receipt"]["passed"])
            self.assertEqual(Path(plan["config"]["work_root"]), self.base / "run-environment")
            work = Path(plan["config"]["work_root"])
            work.mkdir()
            (work / "synthetic-weight-sentinel.bin").write_bytes(b"excluded mock material")
            return copy.deepcopy(self.prepared)

        def study(*args, **kwargs):
            events.append("study")
            config = kwargs["model_config"]
            self.assertEqual(events, ["prepare", "study"])
            self.assertEqual(config["environment_sha256"], self.plan["plan_sha256"])
            self.assertNotEqual(config["environment_sha256"],
                                config["prepared_bootstrap"]["actual_environment_lock_sha256"])
            self.assertTrue(Path(config["prepared_bootstrap"]["admission_path"]).is_file())
            self.assertEqual(config["source_identity"], self.overlay)
            return {"status": "complete", "physical_calls": 0,
                    "stop_ack": {"model_owner_stopped": True}}

        with self.fast_runner(gate_passed=True), \
             patch.object(offline_bootstrap, "prepare_model_environment", side_effect=prepare), \
             patch.object(study_runner, "run_model_studies", side_effect=study):
            result = runner.run(self.root, manual_start=True, profile="FULL",
                                enable_model=True, session_seconds=200)
        self.assertEqual(result["status"], "complete", result["report"].get("error"))
        self.assertEqual(events, ["prepare", "study"])
        with zipfile.ZipFile(result["archive"]["archive"]) as archive:
            names = archive.namelist()
            self.assertIn("runtime/environment-binding.json", names)
            self.assertFalse(any("sentinel" in name or "run-environment" in name for name in names))

    def test_outer_unknown_stop_withholds_seal_and_prevents_resumed_prepare_or_model(self):
        with self.fast_runner(gate_passed=True), \
             patch.object(offline_bootstrap, "prepare_model_environment", side_effect=RuntimeError("no stop proof")) as prepare, \
             patch.object(study_runner, "run_model_studies") as study:
            first = runner.run(self.root, manual_start=True, profile="FULL", enable_model=True, session_seconds=200)
            resumed = runner.run(self.root, manual_start=True, profile="FULL", enable_model=True,
                                 session_seconds=200, resume=True)
            self.assertEqual(prepare.call_count, 1)
            study.assert_not_called()
        for result in (first, resumed):
            self.assertEqual(result["status"], "partial-inconclusive")
            self.assertIsNone(result["archive"])
            self.assertFalse(result["report"]["processes"]["model_owner_stopped"])
            self.assertIn("withheld", result["report"]["global_seal"])
        self.assertEqual(resumed["report"]["model"]["status"], "prior_stop_unconfirmed")

    def test_outer_environment_drift_stops_before_resumed_study_or_cache_use(self):
        changed = {**self.prepared, "actual_environment_lock_sha256": digest("new actual environment")}
        with self.fast_runner(gate_passed=True), \
             patch.object(offline_bootstrap, "prepare_model_environment", side_effect=[self.prepared, changed]) as prepare, \
             patch.object(study_runner, "run_model_studies", return_value={"status": "partial-inconclusive",
                "stop_ack": {"model_owner_stopped": True}}) as study:
            first = runner.run(self.root, manual_start=True, profile="FULL", enable_model=True, session_seconds=200)
            frozen = (self.root / "runtime" / "environment-binding.json").read_bytes()
            resumed = runner.run(self.root, manual_start=True, profile="FULL", enable_model=True,
                                 session_seconds=200, resume=True)
            self.assertEqual(prepare.call_count, 2)
            self.assertEqual(study.call_count, 1)
        self.assertEqual(first["status"], "partial-inconclusive")
        self.assertEqual(resumed["status"], "partial-inconclusive")
        self.assertIn("changed immutable receipt", resumed["report"]["error"]["message"])
        self.assertEqual((self.root / "runtime" / "environment-binding.json").read_bytes(), frozen)

    def test_post_gate_short_session_initialization_respects_export_cutoff(self):
        from tools.arc_consolidated_20261010 import remote_model_owner

        clock = Clock()
        tasks = [{"task_id": task_id, "demos": [{"input": [[1]], "output": [[1]]}]}
                 for task_id in assets.ENGINEERING_IDS]
        environment_hash = digest("synthetic planned environment")
        plan = study_runner.mp.build_study_plan(tasks,
            grammar={"version": study_runner.ir.IR_VERSION, "contract": study_runner.ir.plan_contract()},
            environment_sha256=environment_hash)
        bounds = {**self.bounds, "load_seconds": 2000}
        bindings = {**self.bindings, "mode": digest("production"), "task": digest(tasks),
            "model": plan.model_sha256, "prompt": plan.prompt_template_sha256,
            "sampling": digest(asdict(plan.sampling)), "environment": environment_hash,
            "budget": digest(bounds)}
        ledger = Ledger(self.root / "ledger", bindings, bounds)
        original_owner = remote_model_owner.RemoteModelOwner
        owners = []

        def make_owner(*args, **kwargs):
            owner = original_owner(*args, **kwargs)
            owners.append(owner)
            return owner

        # Exercise the real production deadline admission, then stop at a
        # mocked tokenizer boundary before any process, model or asset access.
        with patch.object(study_runner.time, "monotonic", clock), \
             ledger.session(session_seconds=600), \
             patch.object(remote_model_owner, "RemoteModelOwner", side_effect=make_owner), \
             patch.object(original_owner, "initialize_tokenizer",
                          side_effect=RuntimeError("mock initialization reached")) as initialize, \
             patch.object(remote_model_owner.subprocess, "Popen", side_effect=AssertionError("spawn")):
            result = study_runner.run_model_studies(tasks, {}, {"tasks": []}, ledger,
                session_id="short-session", evidence_mode="production",
                model_config={"environment_sha256": environment_hash,
                    "prepared_bootstrap": self.prepared, "source_identity": self.overlay},
                verify_callback=lambda *args, **kwargs: self.fail("verification reached"))
            initialize.assert_called_once()
            self.assertEqual(result["error"]["message"], "mock initialization reached")
            self.assertEqual(len(owners), 1)
            owner = owners[0]
            reserved = ledger.operation("load/short-session")["budget"]["load_seconds"]
            self.assertGreater(reserved, 0)
            self.assertLessEqual(clock.value + reserved, owner.deadline)
            self.assertEqual(owner._initialization_deadline, clock.value + reserved)
            self.assertGreaterEqual(ledger.remaining_wall_seconds - reserved, 60)
            self.assertEqual(ledger.summary()["charged"]["physical_calls"], 0)
            self.assertTrue(result["stop_ack"]["model_owner_stopped"])


if __name__ == "__main__":
    unittest.main()
