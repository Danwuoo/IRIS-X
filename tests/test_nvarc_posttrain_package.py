"""Synthetic source/seal tests. No real provider terminal or model score claims."""
import copy
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from tools.nvarc_posttrain_20261017 import bootstrap, package, score
from tools.arc2_goal_sprint_20261017.launch import sha, write_new
from tests.test_nvarc_posttrain_controller import public_fixture, pools, model_identity
from tests.platform_requirements import requires_linux


def closure():
    root = dict(pid=123, birth=1, session=123, state="Z")
    child = dict(pid=124, birth=2, session=123, state="Z")
    return dict(format="irisx/owned-process-closure-v1", scope="dedicated-subreaper-tree",
        closed=True, ownership_complete=True, remaining=[], errors=[], returncode=0,
        worker_returncode=0, owned_identities=[root, child], root_identity=root)


def synthetic_seal(root):
    output = root / "output"
    output.mkdir()
    body = pools(public_fixture(), [[[1]]])
    body.update(run_id="synthetic", format="irisx/arc-offline-pools-v1")
    write_new(output / "pools.json", body)
    for variant in ("2b", "4b"):
        path = output / "public-0" / (variant + "-S")
        path.mkdir(parents=True)
        write_new(path / "pools.json", body)
    write_new(output / "run-summary.json", dict(run_id="synthetic", source_identity="a" * 64,
        solver_status="complete", inherited_exposure_qualified=True, clean_generalization_claimed=False))
    write_new(output / "selected-checkpoints.json", {"synthetic_fixture": True})
    write_new(output / "public-evidence-admission.json", {"source_identity": "a" * 64,
        "models": {v: {"admitted": True, "status": "completed", "path": f"public-0/{v}-S/pools.json"} for v in ("2b", "4b")}})
    write_new(output / "isolation.json", dict(mechanism="dataset-separated-provider-execution",
        evaluator_dataset_absent=True, os_sandbox_claimed=False))
    destination = root / "sealed"
    with patch("tools.arc_learning_agent_20261011.process_guard.verify_closed_proof"):
        receipt = score.seal(output, destination, closure(), "a" * 64)
    terminal = dict(format="irisx/nvarc-provider-terminal-v1", notebook_id=123456, version=1,
        status="COMPLETE", source_verified=True, outputs_verified=True, source_manifest_sha256="a" * 64,
        prediction_seal_sha256=sha(destination / "prediction-seal.json"), pools_sha256=receipt["pools_sha256"],
        verified_terminal_epoch=time.time())
    write_new(root / "terminal.json", terminal)
    evidence = dict(terminal_path=str(root / "terminal.json"), terminal_sha256=sha(root / "terminal.json"),
        seal_sha256=sha(destination / "prediction-seal.json"), source_manifest_sha256="a" * 64)
    return destination, evidence


class SourcePackageTests(unittest.TestCase):
    def test_pinned_vendor_assets_survive_autocrlf_checkout(self):
        # Exercise Git's real checkout conversion without changing this checkout.
        # Pinned source bytes must not be normalized or excused by the packager.
        paths = ["tools/arc2_agent_factory3_bridge_20261014/vendor/" + name
                 for name in ("LICENSE", "NOTICE")]
        committed = {name: subprocess.run(["git", "show", "HEAD:" + name], cwd=package.ROOT,
            check=True, capture_output=True, timeout=30).stdout for name in paths}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True,
                                      capture_output=True, timeout=30)

            git("init", "--quiet")
            (root / ".gitattributes").write_bytes((package.ROOT / ".gitattributes").read_bytes())
            for name, content in committed.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            git("-c", "core.autocrlf=false", "add", ".gitattributes", *paths)
            for name in paths:
                (root / name).unlink()
            git("-c", "core.autocrlf=true", "checkout-index", "--force", "--", *paths)
            for name, content in committed.items():
                with self.subTest(path=name):
                    self.assertEqual((root / name).read_bytes(), content)

    def test_exact_source_transport_and_import_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheels = root / "wheels"
            wheels.mkdir()
            # Minimal wheel METADATA fixtures test packaging only, never install.
            for name in ("pydantic", "pydantic-core", "annotated-types", "typing-inspection"):
                stem = name.replace("-", "_")
                with zipfile.ZipFile(wheels / f"{stem}-1.0-py3-none-any.whl", "w") as archive:
                    archive.writestr(f"{stem}-1.0.dist-info/METADATA", f"Name: {name}\nVersion: 1.0\n")
            result = package.build_capsule(root / "capsule", run_id="nvarc-synthetic-test",
                source_dataset="danielwuu/iris-x-nvarc-synthetic/1", extra_wheelhouse=wheels)
            dataset = root / "capsule/source-dataset"
            manifest = json.loads((dataset / "source-manifest.json").read_bytes())
            self.assertFalse(result["published"])
            self.assertFalse(manifest["contains_model_weights"])
            self.assertFalse(manifest["contains_evaluator_data"])
            self.assertIn("tools/nvarc_posttrain_20261017/model-pins.json", manifest["files"])
            self.assertIn("tools/nvarc_posttrain_20261017/worker.py", manifest["files"])
            self.assertTrue(all(not name.startswith((".irisx/", "tests/")) for name in manifest["files"]))
            unpacked = root / "unpacked"
            unpacked.mkdir()
            with zipfile.ZipFile(dataset / "source-payload.zip.bin") as archive:
                self.assertEqual(set(archive.namelist()), set(manifest["files"]))
                archive.extractall(unpacked)
            for name, row in manifest["files"].items():
                self.assertEqual(sha(unpacked / name), row["sha256"])
            code = ("import sys;sys.path[:0]=" + repr([str(unpacked), str(unpacked / "src")]) + ";"
                "import tools.nvarc_posttrain_20261017.controller as c;"
                "import tools.nvarc_posttrain_20261017.bootstrap as b;"
                "import tools.nvarc_posttrain_20261017.score as s;"
                "assert not any(k=='torch' or k.startswith('torch.') for k in sys.modules);"
                "assert str(c.__file__).startswith(" + repr(str(unpacked)) + ")")
            subprocess.run([sys.executable, "-I", "-B", "-c", code], check=True, cwd=root, timeout=30,
                           capture_output=True, text=True)

    def test_new_private_notebook_only_mounts_selected_models_and_solver_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "notebook"
            result = package.build_notebook(output, run_id="nvarc-synthetic-test",
                source_dataset="danielwuu/iris-x-nvarc-synthetic/1", solver_dataset="danielwuu/iris-x-solver-only/1",
                source_manifest_sha256="a" * 64, source_payload_sha256="b" * 64, started_epoch=time.time())
            metadata = json.loads((output / "kernel-metadata.json").read_bytes())
            notebook = json.loads((output / metadata["code_file"]).read_bytes())
        self.assertFalse(result["published"])
        self.assertTrue(metadata["is_private"])
        self.assertFalse(metadata["enable_internet"])
        self.assertEqual(len(metadata["model_sources"]), 2)
        self.assertTrue(all(value.startswith("sorokin/") for value in metadata["model_sources"]))
        self.assertNotIn(package.REFERENCES["public"], metadata["dataset_sources"])
        text = notebook["cells"][0]["source"]
        self.assertIn("tools/nvarc_posttrain_20261017/bootstrap.py", text)
        self.assertNotIn("tools/arc2_goal_sprint_20261017/bootstrap.py", text)
        compile(text, "<synthetic-loader>", "exec")

    def test_resolve_model_does_not_accept_ambiguous_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for version in ("1", "2"):
                path = root / "qwen3_2b_grids15_sft141/transformers/bfloat16" / version
                path.mkdir(parents=True)
                (path / "config.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "one exact"):
                bootstrap.resolve_model(root, "2b")


class ExposureSealTests(unittest.TestCase):
    def test_admission_requires_exact_source_boolean_and_specialist_path(self):
        valid = {"source_identity": "a" * 64, "models": {
            "2b": {"admitted": True, "path": "public-0/2b-S/pools.json"},
            "4b": {"admitted": False, "path": None}}}
        self.assertEqual(score.admission_paths(valid, "a" * 64), {"2b": "public-0/2b-S/pools.json"})
        changes = [lambda value: value.update(source_identity="b" * 64),
            lambda value: value["models"]["2b"].update(admitted=1),
            lambda value: value["models"]["2b"].update(path="public-0/4b-S/pools.json"),
            lambda value: value["models"]["4b"].update(path="public-0/4b-S/pools.json")]
        for mutate in changes:
            value = copy.deepcopy(valid)
            mutate(value)
            with self.assertRaises(ValueError):
                score.admission_paths(value, "a" * 64)

    @unittest.skipUnless(sys.platform == "linux" and hasattr(os, "pidfd_open"), "Linux owned-tree implementation required")
    @requires_linux("Real outer controller requires Linux pidfd/procfs owned-process closure")
    def test_real_outer_controller_closes_before_sealing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "source/tools/nvarc_posttrain_20261017/bootstrap.py"
            script.parent.mkdir(parents=True)
            script.write_text('''import json,pathlib,sys
c=json.loads(pathlib.Path(sys.argv[2]).read_bytes())
p=pathlib.Path(c['output_root']);p.mkdir()
def save(name,body): (p/name).write_text(json.dumps(body))
records=[{'task_id':str(i),'tests':[{'test_index':j,'input_digest':'sha256:'+'b'*64,'ranked_grids':[]} for j in range(2 if i<47 else 1)]} for i in range(120)]
save('pools.json',{'format':'irisx/arc-offline-pools-v1','run_id':c['run_id'],'records':records})
save('run-summary.json',{'run_id':c['run_id'],'source_identity':c['source_identity'],'solver_status':'failed','inherited_exposure_qualified':True,'clean_generalization_claimed':False})
save('selected-checkpoints.json',{'synthetic_fixture':True})
save('isolation.json',{'mechanism':'dataset-separated-provider-execution','evaluator_dataset_absent':True,'os_sandbox_claimed':False})
''', encoding="utf-8")
            config = dict(python=sys.executable, run_id="synthetic", source_identity="a" * 64,
                          output_root=str(root / "output"), deadline_epoch=time.time() + 120)
            with patch.object(bootstrap, "SOURCE", root / "source"), contextlib.redirect_stdout(io.StringIO()):
                terminal = bootstrap.protected_launch(config, root / "control", {})
            receipt = json.loads((root / "control/sealed/prediction-seal.json").read_bytes())
            self.assertEqual(terminal["status"], "SEALED_AWAITING_EXTERNAL_EVALUATOR")
            self.assertTrue(receipt["closure"]["closed"])
            self.assertTrue(receipt["closure"]["ownership_complete"])
            self.assertEqual(receipt["closure"]["remaining"], [])
            self.assertEqual(receipt["closure"]["worker_returncode"], 0)
            self.assertFalse(terminal["provider_terminal_verified"])

    @requires_linux("Synthetic seal fixture imports the Linux-owned process closure verifier")
    def test_exact_provider_version_and_every_sealed_byte_are_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            sealed, evidence = synthetic_seal(Path(directory))
            score.verify_terminal(sealed, evidence, notebook_id=123456, version=1)
            for identity in ((123456, 2), (999, 1)):
                with self.assertRaises(ValueError): score.verify_terminal(sealed, evidence, notebook_id=identity[0], version=identity[1])
            (sealed / "selected-checkpoints.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "sealed evidence changed"):
                score.verify_terminal(sealed, evidence, notebook_id=123456, version=1)

    @requires_linux("Synthetic seal fixture imports the Linux-owned process closure verifier")
    def test_even_perfect_numeric_score_never_claims_clean_goal(self):
        from tools import arc_offline_evaluation as original
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sealed, evidence = synthetic_seal(root)
            public = root / "public.json"
            public.write_text(json.dumps(public_fixture()))
            metric = {"development_metrics": {"tasks": 120, "tests": 167,
                "metrics": {"pass_at_2": {"numerator": 167, "denominator": 167, "rate": 1.}}}}
            with patch.object(score, "verify_inventory"), \
                    patch.object(original, "load_pinned_reference", return_value=(public_fixture(), {}, {"synthetic": True})), \
                    patch.object(original, "evaluate", return_value=metric):
                result = score.score(sealed, root / "evaluator", public, package.ROOT, evidence, notebook_id=123456, version=1)
            self.assertTrue(result["numeric_threshold_met"])
            self.assertFalse(result["clean_goal_met"])
            self.assertFalse(result["clean_generalization_claimed"])
            self.assertTrue(result["inherited_exposure_qualified"])
            self.assertIsNone(result["official_score"])

    @requires_linux("Synthetic seal fixture imports the Linux-owned process closure verifier")
    def test_bad_terminal_blocks_before_any_evaluator_access(self):
        with tempfile.TemporaryDirectory() as directory:
            sealed, evidence = synthetic_seal(Path(directory))
            evidence["terminal_sha256"] = "0" * 64
            with patch.object(score, "verify_inventory") as inventory:
                with self.assertRaises(ValueError):
                    score.score(sealed, "/not-read/evaluator", "/not-read/public", package.ROOT, evidence,
                                notebook_id=123456, version=1)
            inventory.assert_not_called()

    @requires_linux("Seal integration imports the Linux-owned process closure verifier")
    def test_unclosed_solver_cannot_seal(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch("tools.arc_learning_agent_20261011.process_guard.verify_closed_proof", side_effect=ValueError("live tree")):
            with self.assertRaisesRegex(ValueError, "live tree"):
                score.seal(Path(directory) / "missing", Path(directory) / "sealed", closure(), "a" * 64)
            self.assertFalse((Path(directory) / "sealed").exists())

    @requires_linux("Failure preservation imports the Linux-owned process closure verifier")
    def test_closed_failure_retains_all_missing_queries_without_model_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / "public.json"
            write_new(public, public_fixture())
            mounted = root / "input"
            (mounted / "solver").mkdir(parents=True)
            config = dict(output_root=str(root / "output"), public_path=str(public), run_id="synthetic",
                source_identity="a" * 64, input_root=str(mounted), allowed_input_roots=[str(mounted / "solver")])
            with patch("tools.arc_learning_agent_20261011.process_guard.verify_closed_proof"):
                bootstrap.preserve_failed_denominator(config, closure())
            body = json.loads((root / "output/pools.json").read_bytes())
            summary = json.loads((root / "output/run-summary.json").read_bytes())
            self.assertEqual(sum(len(r["tests"]) for r in body["records"]), 167)
            self.assertTrue(all(not t["ranked_grids"] for r in body["records"] for t in r["tests"]))
            self.assertEqual(summary["solver_status"], "failed")
            self.assertFalse(summary["model_success_claimed"])

    @requires_linux("Failure preservation and seal import the Linux-owned process closure verifier")
    def test_crash_before_merge_preserves_closed_specialist_and_remains_scoreable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = public_fixture()
            write_new(root / "public.json", public)
            (root / "input/solver").mkdir(parents=True)
            specialist = root / "output/public-0/2b-S"
            specialist.mkdir(parents=True)
            write_new(specialist / "pools.json", pools(public, [[[3]]]))
            write_new(root / "output/topology.json", {"device_identity": "synthetic-device"})
            write_new(specialist / "config.json", {"job_id": "2b-S", "mode": "public", "source_identity": "a" * 64,
                "device_identity": "synthetic-device", "workload_identity": "compact-selected-full-public-v1"})
            write_new(root / "output/public-0/wave.json", {"jobs": [{"job_id": "2b-S", "status": "worker_failed",
                "closure_verified": True, "result": None, "ready_receipt": {"job_id": "2b-S", "ready": True,
                    "device": {"device_identity": "synthetic-device"}, "base_identity": model_identity("2b")}}]})
            config = dict(output_root=str(root / "output"), public_path=str(root / "public.json"),
                run_id="synthetic", source_identity="a" * 64, input_root=str(root / "input"),
                allowed_input_roots=[str(root / "input/solver")])
            with patch("tools.arc_learning_agent_20261011.process_guard.verify_closed_proof"):
                bootstrap.preserve_failed_denominator(config, closure())
                receipt = score.seal(root / "output", root / "sealed", closure(), "a" * 64)
            score.verify_ensemble(root / "sealed", receipt, public)
            combined = json.loads((root / "sealed/pools.json").read_bytes())
            self.assertTrue(all(t["ranked_grids"] == [[[3]]] for r in combined["records"] for t in r["tests"]))
            self.assertEqual(json.loads((root / "sealed/run-summary.json").read_bytes())["solver_status"], "failed")

    @requires_linux("Failure preservation and seal import the Linux-owned process closure verifier")
    def test_identity_rejected_raw_public_pool_is_not_reintroduced_by_fallback_or_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = public_fixture()
            write_new(root / "public.json", public)
            (root / "input/solver").mkdir(parents=True)
            specialist = root / "output/public-0/2b-S"
            specialist.mkdir(parents=True)
            write_new(specialist / "pools.json", pools(public, [[[9]]]))
            write_new(root / "output/topology.json", {"device_identity": "synthetic-device"})
            write_new(specialist / "config.json", {"job_id": "2b-S", "mode": "public", "source_identity": "a" * 64,
                "device_identity": "synthetic-device", "workload_identity": "compact-selected-full-public-v1"})
            write_new(root / "output/public-0/wave.json", {"jobs": [{"job_id": "2b-S", "status": "invalid_result",
                "closure_verified": True, "result": {"source_identity": "FOREIGN"}}]})
            config = dict(output_root=str(root / "output"), public_path=str(root / "public.json"),
                run_id="synthetic", source_identity="a" * 64, input_root=str(root / "input"),
                allowed_input_roots=[str(root / "input/solver")])
            with patch("tools.arc_learning_agent_20261011.process_guard.verify_closed_proof"):
                bootstrap.preserve_failed_denominator(config, closure())
                receipt = score.seal(root / "output", root / "sealed", closure(), "a" * 64)
            score.verify_ensemble(root / "sealed", receipt, public)
            self.assertTrue((specialist / "pools.json").exists())  # Physical rejected evidence retained.
            self.assertFalse((root / "sealed/public-0/2b-S/pools.json").exists())
            combined = json.loads((root / "sealed/pools.json").read_bytes())
            self.assertTrue(all(not t["ranked_grids"] for r in combined["records"] for t in r["tests"]))


if __name__ == "__main__": unittest.main()
