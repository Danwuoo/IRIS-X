"""CPU-only integrity, denial, lifecycle and unchanged-scorer regression checks."""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tools.arc2_goal_sprint_20261017 import launch as L
from tools.arc2_goal_sprint_20261017 import bootstrap as B
from tools.arc2_goal_sprint_20261017 import package as P

ROOT = Path(__file__).resolve().parents[1]


class GoalLauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Pure synthetic metadata fixture, never a claimed provider observation.
        self.original_metadata = {"id_no": 138123872, "id": "danielwuu/iris-x-learning-agent-20261011",
            "is_private": True, "machine_shape": "NvidiaRtxPro6000", "enable_gpu": True,
            "enable_internet": False, "keywords": ["gpu", "synthetic-test"],
            "dataset_sources": [B.REFERENCES["public"], "danielwuu/historical-fixture/1"],
            "model_sources": [B.REFERENCES["model"]], "competition_sources": ["synthetic-preserved-association"]}
        self.metadata_path = self.root / "synthetic-kernel-metadata.json"
        self.metadata_path.write_text(json.dumps(self.original_metadata))

    def tearDown(self):
        self.tmp.cleanup()

    def make_symlink(self, link, target, *, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError:
            if os.name == "nt":
                self.skipTest("Windows symlink creation privilege unavailable")
            raise

    def inventory(self):
        root = self.root / "dataset"
        root.mkdir()
        (root / "clean.json").write_text('{}')
        manifest = {"files": {"clean.json": {"bytes": 2, "sha256": L.sha(root / "clean.json")}}}
        pin = L.write_new(root / "manifest.json", manifest)
        return root, pin

    def test_original_scorer_unchanged(self):
        self.assertEqual(L.sha(ROOT / "tools/arc_offline_evaluation.py"), L.SCORER_SHA256)

    def test_write_new_preserves_consumed_identity(self):
        path = self.root / "record.json"
        first = L.write_new(path, {"x": 1})
        with self.assertRaises(FileExistsError):
            L.write_new(path, {"x": 2})
        self.assertEqual(L.sha(path), first)

    def test_inventory_rejects_bytes_manifest_and_extra_files(self):
        root, pin = self.inventory()
        L.verify_inventory(root, pin)
        (root / "extra-answers.json").write_text('{}')
        with self.assertRaisesRegex(ValueError, "unmanifested"):
            L.verify_inventory(root, pin)
        (root / "extra-answers.json").unlink()
        (root / "clean.json").write_text('{"changed": true}')
        with self.assertRaisesRegex(ValueError, "identity"):
            L.verify_inventory(root, pin)
        with self.assertRaisesRegex(ValueError, "manifest pin"):
            L.verify_inventory(root, "0" * 64)

    def test_inventory_rejects_symlink(self):
        root, pin = self.inventory()
        (root / "clean.json").unlink()
        (self.root / "external.json").write_text('{}')
        self.make_symlink(root / "clean.json", self.root / "external.json")
        with self.assertRaisesRegex(ValueError, "symlink"):
            L.verify_inventory(root, pin)

    def test_allowlist_rejects_original_mount_ancestor(self):
        hidden = self.root / "input/public/evaluator"
        hidden.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "intersects"):
            L.check_allowlist([self.root / "input"], [], [hidden])
        if os.name == "posix":
            with self.assertRaisesRegex(ValueError, "root filesystem"):
                L.check_allowlist(["/"], [], [hidden])
        L.check_allowlist([self.root / "input/public/solver"], [self.root / "output"], [hidden])

    def test_allowlist_rejects_symlink_alias(self):
        hidden = self.root / "evaluator"
        hidden.mkdir()
        alias = self.root / "pretend-code"
        self.make_symlink(alias, hidden, directory=True)
        with self.assertRaisesRegex(ValueError, "intersects"):
            L.check_allowlist([alias], [], [hidden])

    def test_probe_never_reads_body_and_rejects_readable_original(self):
        path = self.root / "manifest.json"
        path.write_text('secret body not read')
        with mock.patch.object(os, "read", side_effect=AssertionError("body read")):
            with self.assertRaisesRegex(L.IsolationUnavailable, "readable"):
                L.assert_denied([path])

    def test_probe_requires_actual_permission_denial(self):
        with mock.patch.object(os, "open", side_effect=PermissionError(errno.EACCES, "denied")):
            self.assertEqual(L.assert_denied(["/original/evaluator"]), ["/original/evaluator"])
        with mock.patch.object(os, "open", side_effect=FileNotFoundError(errno.ENOENT, "missing")):
            with self.assertRaisesRegex(ValueError, "not a permission denial"):
                L.assert_denied(["/original/evaluator"])

    def test_missing_landlock_fails_closed(self):
        with mock.patch.object(L, "landlock_abi", side_effect=L.IsolationUnavailable("unsupported")):
            with self.assertRaises(L.IsolationUnavailable):
                L.apply_landlock(["/usr"], [])

    def test_runtime_allowlist_never_grants_input_or_working_parent(self):
        reads, writes = L.runtime_allowlist(self.root / "source", self.root / "runtime",
            [self.root / "model"], self.root / "training", self.root / "public/solver", self.root / "output")
        self.assertNotIn(str(self.root), reads + writes)
        self.assertNotIn("/kaggle/input", reads + writes)
        self.assertNotIn("/kaggle/working", reads + writes)
        self.assertNotIn("/tmp", reads + writes)
        self.assertNotIn("/proc", reads + writes)
        self.assertIn("/proc/self", reads)

    def test_platform_deadline_not_reset(self):
        with self.assertRaisesRegex(ValueError, "deadline"):
            B.remaining({"session_deadline_epoch": time.time() - 1})

    def test_dataset_resolution_has_no_ambiguous_fallback(self):
        root = self.root / "input"
        (root / "slug").mkdir(parents=True)
        self.assertEqual(B.resolve_dataset(root, "owner/slug/1"), root / "slug")
        (root / "datasets/owner/slug").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "one mounted"):
            B.resolve_dataset(root, "owner/slug/1")

    def test_preflight_notebook_is_inert_model_free_offline(self):
        original = json.loads(self.metadata_path.read_bytes())
        metadata = P.metadata(original, "preflight.ipynb")
        self.assertFalse(metadata["enable_gpu"])
        self.assertFalse(metadata["enable_internet"])
        self.assertNotIn("machine_shape", metadata)
        self.assertTrue(metadata["is_private"])
        self.assertEqual(metadata["id_no"], 138123872)
        self.assertEqual(original["dataset_sources"], metadata["dataset_sources"])
        source = P.preflight_source("synthetic-preflight")
        compile(source, "preflight", "exec")
        self.assertNotIn("from_pretrained", source)
        self.assertIn("evaluator/manifest.json", source)
        self.assertNotIn("data/evaluation", source)

    def test_loader_verifies_before_executing(self):
        source = P.notebook_source({"test": "fixture"})
        compile(source, "loader", "exec")
        self.assertLess(source.index("digest(manifest_path)"), source.index("subprocess.run"))
        self.assertIn("exist_ok=False", source)
        self.assertNotIn("kaggle.api", source)

    def test_new_source_distinct_and_notebook_preserved(self):
        original = json.loads(self.metadata_path.read_bytes())
        result = P.metadata(original, "new.ipynb", source_dataset="danielwuu/irisx-new-private-source/1", enable_gpu=True)
        self.assertIn("danielwuu/irisx-new-private-source/1", result["dataset_sources"])
        self.assertEqual(len(result["dataset_sources"]), 5)
        self.assertFalse(any("granite" in name or "iris-arc-next-runtime" in name for name in result["dataset_sources"]))
        self.assertTrue(result["is_private"])
        self.assertTrue(result["enable_gpu"])
        self.assertFalse(result["enable_internet"])
        self.assertEqual(result["machine_shape"], "NvidiaRtxPro6000")
        self.assertEqual(result["competition_sources"], original["competition_sources"])
        self.assertEqual(original, json.loads(self.metadata_path.read_bytes()))

    def test_source_allowlist_excludes_json_notebooks_outputs_and_secrets(self):
        (self.root / "tools").mkdir()
        (self.root / "src").mkdir()
        (self.root / "notices").mkdir()
        for name in ("safe.py", "private.ipynb", "evaluator.json", ".secret.py"):
            (self.root / "tools" / name).write_text('')
        names = [p.name for p in P.source_paths(self.root, ("tools.safe",))]
        self.assertEqual(names, ["safe.py"])

    def test_source_static_closure_excludes_all_historical_fixtures(self):
        paths = P.source_paths(ROOT)
        names = {p.relative_to(ROOT).as_posix() for p in paths}
        self.assertLess(len(paths), 80)
        self.assertIn("tools/arc_offline_evaluation.py", names)
        self.assertIn("tools/arc2_agent_factory3_bridge_20261014/vendor/LICENSE", names)
        self.assertIn("tools/arc2_agent_factory3_bridge_20261014/vendor/NOTICE", names)
        self.assertIn("research/stage4-e10/native-notices/NOTICE-native.txt", names)
        self.assertFalse(any("/tests/" in p or "/release/" in p or p.endswith(".ipynb") for p in names))

    def test_extra_wheel_lock_closure(self):
        path = ROOT / ".irisx/continuation-20261017/extra-wheels"
        if not path.is_dir():
            self.skipTest("private packaging wheelhouse not present")
        lock = P.wheel_lock(path)
        self.assertEqual({v["name"] for v in lock["files"].values()},
                         {"pydantic", "pydantic-core", "annotated-types", "typing-inspection"})
        self.assertTrue(all(v["source"].startswith("https://pypi.org/") for v in lock["files"].values()))

    def test_seal_refuses_unclosed_solver(self):
        output = self.root / "output"
        output.mkdir()
        (output / "pools.json").write_text('{}')
        with self.assertRaises(ValueError):
            L.seal_predictions(output, self.root / "sealed", {"closed": False}, "0" * 64)
        self.assertFalse((self.root / "sealed").exists())

    @unittest.skipUnless(sys.platform == "linux" and hasattr(os, "pidfd_open"), "real Linux pidfd/subreaper lifecycle required")
    def test_real_subtree_closure_before_seal(self):
        from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard, verify_closed_proof
        output = self.root / "output"
        output.mkdir()
        (output / "pools.json").write_text('{"fixture":true}')
        # A daemon that leaves its process group must also be stopped/reaped.
        code = "import os,time; p=os.fork(); (os.setsid(),time.sleep(20)) if p==0 else None"
        guard = OwnedProcessGuard.spawn([sys.executable, "-I", "-B", "-c", code], evidence_dir=self.root / "tree",
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 10
        while guard.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        proof = guard.stop(timeout=10) if guard.poll() is None else guard.closed_proof()
        self.assertTrue(verify_closed_proof(proof))
        self.assertTrue(proof["closed"])
        self.assertGreaterEqual(len(proof["owned_identities"]), 2)
        seal = L.seal_predictions(output, self.root / "sealed", proof, "a" * 64)
        self.assertEqual(seal["pools_sha256"], L.sha(output / "pools.json"))
        self.assertFalse(seal["generation_may_resume"])

    @unittest.skipUnless(sys.platform == "linux" and hasattr(os, "pidfd_open"), "real Linux pidfd/subreaper lifecycle required")
    def test_score_refuses_tamper_before_evaluator_open(self):
        from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard
        output = self.root / "output"
        output.mkdir()
        (output / "pools.json").write_text('{}')
        guard = OwnedProcessGuard.spawn([sys.executable, "-I", "-B", "-c", "pass"], evidence_dir=self.root / "tree")
        while guard.poll() is None:
            time.sleep(.02)
        L.seal_predictions(output, self.root / "sealed", guard.closed_proof(), "a" * 64)
        prediction = self.root / "sealed/pools.json"
        prediction.chmod(0o600)
        prediction.write_text('{"tampered": true}')
        with mock.patch.object(L, "verify_inventory", side_effect=AssertionError("evaluator was opened")):
            with self.assertRaisesRegex(ValueError, "predictions changed"):
                L.score_sealed(self.root / "sealed", self.root / "evaluator", self.root / "public", ROOT)

    @unittest.skipUnless(sys.platform == "linux" and hasattr(os, "pidfd_open"), "real Linux pidfd/subreaper lifecycle required")
    def test_full_synthetic_120_167_scoring_goal_and_source_integrity(self):
        from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard
        from tools.arc_offline_evaluation import POOL_FORMAT
        from tools.nvarc_native_multitask import digest
        from src.irisx.artifacts import make_artifact
        evaluator = self.root / "evaluator"
        tasks = evaluator / "upstream/data/evaluation"
        tasks.mkdir(parents=True)
        public = {}
        provenance = []
        records = []
        counter = 0
        for i in range(120):
            key = f"{i:08x}"
            count = 2 if i < 47 else 1
            task = {"train": [{"input": [[0]], "output": [[1]]}],
                    "test": [{"input": [[0]], "output": [[1]]} for _ in range(count)]}
            path = tasks / (key + ".json")
            path.write_text(json.dumps(task))
            provenance.append({"path": "data/evaluation/" + path.name,
                "byte_size": path.stat().st_size, "content_digest": "sha256:" + L.sha(path)})
            public[key] = {"train": task["train"], "test": [{"input": [[0]]} for _ in range(count)]}
            tests = []
            for j in range(count):
                tests.append({"test_index": j, "input_digest": digest([[0]]),
                    "ranked_grids": [[[1]]] if counter < 156 else [], "status": "complete"})
                counter += 1
            records.append({"task_id": key, "task_digest": digest(public[key]), "tests": tests, "timings": {}})
        L.write_new(evaluator / "provenance.json", make_artifact("irisx/arc-source-provenance", "synthetic-goal", "1.0.0", {
            "repository": "https://github.com/arcprize/ARC-AGI-2.git", "commit": "f3283f727488ad98fe575ea6a5ac981e4a188e49", "files": provenance}))
        inventory = {p.relative_to(evaluator).as_posix(): {"bytes": p.stat().st_size, "sha256": L.sha(p)}
                     for p in evaluator.rglob("*") if p.is_file()}
        pin = L.write_new(evaluator / "manifest.json", {"files": inventory})
        public_path = self.root / "public.json"
        L.write_new(public_path, public)
        output = self.root / "output"
        output.mkdir()
        L.write_new(output / "pools.json", {"format": POOL_FORMAT, "run_id": "synthetic-goal", "method": "synthetic CPU fixture only",
            "challenges_digest": digest(public), "records": records, "parent_wall_seconds": 1.0})
        L.write_new(output / "run-summary.json", {"run_id": "synthetic-goal", "solver_status": "complete"})
        L.write_new(output / "isolation.json", {"mechanism": "dataset-separated-provider-execution",
            "evaluator_dataset_absent": True, "os_sandbox_claimed": False})
        guard = OwnedProcessGuard.spawn([sys.executable, "-I", "-B", "-c", "pass"], evidence_dir=self.root / "tree")
        while guard.poll() is None:
            time.sleep(.02)
        with mock.patch.object(L, "EVALUATOR_MANIFEST_SHA256", pin):
            L.seal_predictions(output, self.root / "sealed", guard.closed_proof(), "a" * 64)
            result = L.score_sealed(self.root / "sealed", evaluator, public_path, ROOT)
        self.assertEqual(result["queries"], 167)
        self.assertEqual(result["tasks"], 120)
        self.assertEqual(result["pass_at_2"]["numerator"], 156)
        self.assertEqual(result["pass_at_2"]["denominator"], 167)
        self.assertTrue(result["goal_met"])
        self.assertEqual(result["measurement"], "public-development")
        self.assertIsNone(result["official_score"])
        self.assertIsNone(result["hidden_score"])
        self.assertTrue(result["operational_success"])
        self.assertTrue(result["valid_scored_predictions"])
        # Independently exercise foreign-host closure and unchanged scoring.
        with mock.patch.object(L, "EVALUATOR_MANIFEST_SHA256", pin):
            external = self.root / "external-sealed"
            seal = L.seal_predictions(output, external, guard.closed_proof(), "a" * 64)
            seal_sha = L.sha(external / "prediction-seal.json")
            terminal_path = self.root / "provider-terminal.json"
            terminal_sha = L.write_new(terminal_path, {"format": "irisx/goal-provider-terminal-v1",
                "notebook_id": 138123872, "version": 99, "status": "COMPLETE", "source_verified": True,
                "outputs_verified": True, "source_manifest_sha256": "a" * 64, "prediction_seal_sha256": seal_sha,
                "pools_sha256": seal["pools_sha256"], "verified_terminal_epoch": time.time()})
            with mock.patch("tools.arc_learning_agent_20261011.process_guard._read_process", side_effect=AssertionError("foreign PID checked")):
                separate = L.score_sealed(external, evaluator, public_path, ROOT, external_evidence={
                    "terminal_path": str(terminal_path), "terminal_sha256": terminal_sha,
                    "seal_sha256": seal_sha, "source_manifest_sha256": "a" * 64})
            self.assertTrue(separate["goal_met"])
            self.assertIn("parent-verified-provider-terminal", separate["closure_verification"])
            (output / "run-summary.json").unlink()
            incomplete = self.root / "incomplete-sealed"
            L.seal_predictions(output, incomplete, guard.closed_proof(), "a" * 64)
            diagnostic = L.score_sealed(incomplete, evaluator, public_path, ROOT)
        self.assertTrue(diagnostic["score_threshold_met"])
        self.assertFalse(diagnostic["goal_met"])
        self.assertFalse(diagnostic["operational_success"])
        self.assertFalse(diagnostic["model_capability_result"])

    def test_separated_metadata_never_mounts_original_public(self):
        original = json.loads(self.metadata_path.read_bytes())
        data = P.metadata(original, "run.ipynb", source_dataset="danielwuu/new-source/1",
                          solver_dataset="danielwuu/new-solver-projection/1", enable_gpu=True)
        self.assertIn("danielwuu/new-solver-projection/1", data["dataset_sources"])
        self.assertNotIn(B.REFERENCES["public"], data["dataset_sources"])
        self.assertEqual(len(data["dataset_sources"]), 5)

    def test_dataset_separation_denies_original_and_unexpected_mounts(self):
        root = self.root / "input"
        clean = root / "datasets/danielwuu/solver"
        clean.mkdir(parents=True)
        self.assertTrue(L.check_dataset_separation(root, [clean]))
        hidden = clean / "evaluator"
        hidden.mkdir()
        with self.assertRaisesRegex(ValueError, "evaluator directory"):
            L.check_dataset_separation(root, [clean])
        hidden.rmdir()
        extra = root / "other-data"
        extra.mkdir()
        with self.assertRaisesRegex(ValueError, "unexpected input"):
            L.check_dataset_separation(root, [clean])
        extra.rmdir()
        original = root / "iris-x-public120-data-20261010"
        original.mkdir()
        with self.assertRaisesRegex(ValueError, "original evaluator-bearing"):
            L.check_dataset_separation(root, [clean, original])

    def external_fixture(self, status="COMPLETE"):
        sealed = self.root / "sealed"
        sealed.mkdir()
        ids = [{"pid": 10000001 + i, "birth": 40 + i, "session": 10000001, "state": "S"} for i in range(2)]
        seal = {"source_manifest_sha256": "a" * 64, "pools_sha256": "b" * 64, "sealed_epoch": time.time() - 10,
                "isolation": {"mechanism": "dataset-separated-provider-execution", "evaluator_dataset_absent": True,
                              "os_sandbox_claimed": False},
                "closure": {"format": "irisx/owned-process-closure-v1", "scope": "dedicated-subreaper-tree",
                    "closed": True, "ownership_complete": True, "remaining": [], "errors": [],
                    "returncode": 0, "worker_returncode": 0, "root_identity": ids[0], "owned_identities": ids}}
        seal_sha = L.write_new(sealed / "prediction-seal.json", seal)
        terminal = {"format": "irisx/goal-provider-terminal-v1", "notebook_id": 138123872, "version": 49,
            "status": status, "source_verified": True, "outputs_verified": True, "source_manifest_sha256": "a" * 64,
            "prediction_seal_sha256": seal_sha, "pools_sha256": "b" * 64, "verified_terminal_epoch": time.time() - 1}
        path = self.root / "terminal.json"
        terminal_sha = L.write_new(path, terminal)
        evidence = {"terminal_path": str(path), "terminal_sha256": terminal_sha, "seal_sha256": seal_sha,
                    "source_manifest_sha256": "a" * 64}
        return sealed, seal, evidence

    def test_external_closure_does_not_claim_local_proc_verification(self):
        sealed, seal, evidence = self.external_fixture()
        with mock.patch("tools.arc_learning_agent_20261011.process_guard._read_process", side_effect=AssertionError("foreign PID checked locally")):
            result = L.verify_external_closure(sealed, seal, evidence)
        self.assertEqual(result["version"], 49)
        self.assertEqual(result["status"], "COMPLETE")
        evidence["source_manifest_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "binding differs"):
            L.verify_external_closure(sealed, seal, evidence)

    def test_external_closure_rejects_pending_and_unpinned_results(self):
        sealed, seal, evidence = self.external_fixture(status="RUNNING")
        with self.assertRaisesRegex(ValueError, "terminal numeric"):
            L.verify_external_closure(sealed, seal, evidence)
        evidence["seal_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "downloaded seal"):
            L.verify_external_closure(sealed, seal, evidence)

    def test_runtime_receipts_exclude_large_environment(self):
        work = self.root / "working"
        runtime = self.root / "temp"
        work.mkdir()
        runtime.mkdir()
        (runtime / "install.log").write_text('offline install')
        (runtime / "weights.safetensors").write_text('not an output')
        B.preserve_runtime_evidence({"working_root": str(work), "runtime_root": str(runtime), "run_id": "fixture"})
        self.assertEqual([p.name for p in (work / "runtime-evidence").iterdir()], ["install.log"])

    def test_notebook_only_cpu_then_gpu_keeps_immutable_source(self):
        epoch = time.time() - 1
        arguments = ("fixture-run", "danielwuu/new-source/1", "a" * 64, "danielwuu/new-solver/1", epoch)
        cpu = self.root / "cpu"
        gpu = self.root / "gpu"
        P.build_notebook_only(cpu, *arguments, source_payload_sha256="b" * 64, prepare_only=True, original_metadata=self.metadata_path)
        P.build_notebook_only(gpu, *arguments, source_payload_sha256="b" * 64, original_metadata=self.metadata_path)
        metadata = json.loads((cpu / "kernel-metadata.json").read_bytes())
        request = json.loads((cpu / "dispatch-request.json").read_bytes())
        self.assertFalse(metadata["enable_gpu"])
        self.assertNotIn("machine_shape", metadata)
        self.assertTrue(request["prepare_only"])
        self.assertEqual(request["source_manifest_sha256"], "a" * 64)
        self.assertNotIn(B.REFERENCES["public"], metadata["dataset_sources"])
        active = json.loads((gpu / "kernel-metadata.json").read_bytes())
        self.assertEqual(active["machine_shape"], "NvidiaRtxPro6000")
        self.assertEqual(metadata["dataset_sources"], active["dataset_sources"])
        self.assertFalse((cpu / "source-dataset").exists())

    def test_preparation_only_ready_never_launches_solver(self):
        inputs = self.root / "input"
        inputs.mkdir()
        source = inputs / "new-source"
        source.mkdir()
        source_sha = L.write_new(source / "source-manifest.json", {"files": {}})
        for role in ("wheels", "interpreter", "training"):
            (inputs / B.REFERENCES[role].split("/")[1]).mkdir()
        training = inputs / B.REFERENCES["training"].split("/")[1]
        training_sha = L.write_new(training / "manifest.json", {"files": {}})
        solver = inputs / "new-solver/solver"
        solver.mkdir(parents=True)
        for name in ("public-challenges.json", "LICENSE", "NOTICE"):
            (solver / name).write_text('{}')
        solver_sha = L.write_new(solver / "manifest.json", {"files": {
            name: {"bytes": 2, "sha256": L.sha(solver / name)} for name in ("public-challenges.json", "LICENSE", "NOTICE")}})
        mount = inputs / "qwen-3/transformers/14b/1"
        mount.mkdir(parents=True)
        now = time.time() - 1
        request = {"run_id": "fixture-prepare", "started_epoch": now, "session_deadline_epoch": now + 43200,
            "input_root": str(inputs), "working_root": str(self.root / "working"), "runtime_root": str(self.root / "temp"),
            "source_dataset": "danielwuu/new-source/1", "solver_dataset": "danielwuu/new-solver/1",
            "source_manifest_sha256": source_sha, "evaluation_mode": "external-cpu", "prepare_only": True}
        def install(req, roots, runtime):
            L.write_new(runtime / "runtime-receipt.json", {"fixture": True})
            return "/synthetic/python3.12", str(runtime / "venv"), {}
        def model(input_root, runtime, **kwargs):
            L.write_new(runtime / "model-receipt.json", {"fixture": True})
            return runtime / "model", mount
        with mock.patch.object(B, "SOURCE", source), mock.patch.object(B, "TRAINING_MANIFEST_SHA256", training_sha), \
             mock.patch.object(B, "SOLVER_MANIFEST_SHA256", solver_sha), mock.patch.object(B, "install", side_effect=install), \
             mock.patch.object(B, "prepare_model", side_effect=model), \
             mock.patch.object(B.subprocess, "run", side_effect=AssertionError("solver unexpectedly started")):
            ready = B.bootstrap(request)
        self.assertEqual(ready["status"], "READY")
        self.assertFalse(ready["model_loaded"])
        self.assertFalse(ready["gpu_execution_performed"])
        self.assertFalse((self.root / "working/launch-request.json").exists())

    def test_mounted_inventory_rejects_extra_and_symlink(self):
        root, _ = self.inventory()
        self.assertEqual(B.exact_files(root, ("clean.json", "manifest.json")), 2)
        (root / "unknown.bin").write_text('not admitted')
        with self.assertRaisesRegex(ValueError, "mounted inventory"):
            B.exact_files(root, ("clean.json", "manifest.json"))

    def test_opaque_source_transport_preserves_paths_and_pins_before_execution(self):
        review = self.root / "source-review"
        review.mkdir()
        names = ("tools/arc2_goal_sprint_20261017/bootstrap.py", "src/irisx/example.py", "materials/config.json")
        for name in names:
            path = review / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('not executed')
        L.write_new(review / "source-manifest.json", {"files": {name: {
            "bytes": (review / name).stat().st_size, "sha256": L.sha(review / name)} for name in names}})
        inputs = self.root / "input"
        upload = inputs / "new-source"
        fingerprint = P.source_transport(review, upload)
        self.assertEqual({p.name for p in upload.iterdir()}, {"source-payload.zip.bin", "source-manifest.json"})
        manifest = json.loads((upload / "source-manifest.json").read_bytes())
        request = {"source_dataset": "danielwuu/new-source/1", "source_manifest_sha256": fingerprint,
                   "source_payload_sha256": manifest["transport"]["sha256"],
                   "session_deadline_epoch": time.time() + 600, "working_root": str(self.root / "working")}
        code = P.notebook_source(request).replace("/kaggle/input", inputs.as_posix())
        with mock.patch.object(subprocess, "run") as called:
            exec(compile(code, "transport-loader", "exec"), {})
        called.assert_called_once()
        for name in names:
            self.assertEqual((self.root / "working-source" / name).read_bytes(), (review / name).read_bytes())
        (upload / "source-payload.zip.bin").write_bytes(b'tampered')
        request["working_root"] = str(self.root / "another-working")
        with mock.patch.object(subprocess, "run") as called:
            with self.assertRaisesRegex(ValueError, "transport differs"):
                exec(compile(P.notebook_source(request).replace("/kaggle/input", inputs.as_posix()), "tampered-loader", "exec"), {})
        called.assert_not_called()

    def test_flat_solver_projection_and_ambiguity(self):
        root = self.root / "flat"
        root.mkdir()
        names = ("LICENSE", "NOTICE", "public-challenges.json")
        for name in names:
            (root / name).write_text('{}')
        pin = L.write_new(root / "manifest.json", {"files": {
            name: {"bytes": 2, "sha256": L.sha(root / name)} for name in names}})
        with mock.patch.object(B, "SOLVER_MANIFEST_SHA256", pin):
            self.assertEqual(B.solver_projection(root), root)
            (root / "solver").mkdir()
            (root / "solver/manifest.json").write_text('{}')
            with self.assertRaisesRegex(ValueError, "exactly one"):
                B.solver_projection(root)

    def test_live_landlock_denies_outside_file(self):
        try:
            L.landlock_abi()
        except L.IsolationUnavailable as exc:
            self.skipTest(str(exc))
        hidden = self.root / "answers.json"
        hidden.write_text('must not be read')
        code = f"""import sys
sys.path[:0] = [{str(ROOT)!r}]
from tools.arc2_goal_sprint_20261017.launch import apply_landlock, assert_denied
apply_landlock(['/usr', '/lib', '/etc'], [])
assert_denied([{str(hidden)!r}])
print('DENIED')
"""
        result = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DENIED", result.stdout)


if __name__ == "__main__":
    unittest.main()
