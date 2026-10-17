"""Synthetic CPU fixtures for next-identity packaging, never production results."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import builtins
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

from tools.arc2_goal_sprint_20261017 import bootstrap as B, launch as L, materials as M, package as P

ROOT = Path(__file__).resolve().parents[1]


def body_sha(body):
    return hashlib.sha256(body).hexdigest()


class MaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def seal(self, path, value):
        path.write_bytes(M.canonical(value))
        return L.sha(path)

    def adapter(self, name="adapter"):
        try:
            import torch
            from safetensors.torch import save_file
            from tools.arc2_goal_sprint_20261017 import model
        except ModuleNotFoundError as exc:
            self.skipTest("optional tensor fixture dependencies unavailable: " + str(exc))
        root = self.root / name
        root.mkdir()
        # Synthetic tensors only, not a Qwen model or a real training checkpoint.
        state = {"base_model.model.synthetic.lora_A.weight": torch.arange(6, dtype=torch.float32).reshape(2, 3),
                 "base_model.model.synthetic.lora_B.weight": torch.zeros(3, 2)}
        save_file(state, str(root / "adapter_model.safetensors"))
        (root / "adapter_config.json").write_text(json.dumps({"peft_type": "LORA", "task_type": "CAUSAL_LM"}))
        current = {n.replace(".weight", ".default.weight"): v for n, v in state.items()}
        manifest = model.build_resume_manifest(root, expected_state_sha256=model.state_digest(current),
            base_identity=M.base_identity(), origin={"run_id": "synthetic-test-only", "source_sha256": "a" * 64,
            "phase": "pre_public", "public_ttt_applied": False, "public_labels_used": False,
            "run_summary_sha256": "b" * 64, "provider_record_sha256": "c" * 64})
        pin = self.seal(root / "manifest.json", manifest)
        return root, manifest, pin

    def source_rows(self, root):
        return {p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": L.sha(p)}
                for p in root.rglob("*") if p.is_file()}

    def source_adapter(self):
        adapter, manifest, pin = self.adapter()
        source = self.root / "source"
        source.mkdir()
        index = M.package_materials(source, adapter_resume_root=adapter, adapter_resume_manifest_sha256=pin)
        return source, index, self.source_rows(source)

    def curriculum(self):
        from tests.test_arc2_goal_curriculum import fixture_admission, fake_inspect, fake_worker, TRAIN
        from tools.arc2_goal_sprint_20261017 import curriculum as C
        admission = C.Admission.from_load_data(*fixture_admission(), fixture=True)
        root = self.root / "corpus"
        with patch.object(C, "inspect_source", side_effect=fake_inspect), patch.object(C, "_run_worker", side_effect=fake_worker):
            receipt = C.prepare_curriculum("synthetic-not-imported", root, admission=admission, parent_ids=[TRAIN])
        manifest = json.loads((root / "manifest.json").read_bytes())
        return root, manifest, receipt["manifest_sha256"]

    def test_production_identity_exact_and_fresh(self):
        expected = {"model_source": "qwen-lm/qwen-3/Transformers/14b/1",
                    "material_contract_sha256": "8d26b2f04a91147bbb5e11231f614552d36e2862af9b8d2d2b05b273805b69b0"}
        self.assertEqual(M.base_identity(), expected)
        changed = M.base_identity()
        changed["model_source"] = "not-production"
        self.assertEqual(M.base_identity(), expected)

    def test_omitted_parameters_and_materials_remain_omitted(self):
        self.assertEqual(M.validate_solver_parameters(), {})
        self.assertIsNone(M.package_materials(self.root))
        self.assertEqual(M.resolve_materials(self.root, source_files={}), {})
        self.assertFalse((self.root / M.INDEX).exists())

    def test_algorithm_allowlist_matches_actual_runtime(self):
        values = {"sft_loss_mode": "causal_outputs", "ttt_loss_mode": "causal_outputs", "candidate_views": 16,
                  "candidate_ranker": "cross_view_likelihood", "candidate_pool_limit": 16,
                  "rerank_fraction": .25, "likelihood_normalization": "token_mean", "sft_steps": 0}
        try:
            self.assertEqual(M.validate_solver_parameters(values, runtime=True), values)
        except ModuleNotFoundError as exc:
            self.skipTest(str(exc))
        self.assertEqual(M.validate_solver_parameters({}), {})

    def test_invalid_tuning_never_reaches_model_preparation(self):
        invalid = [{"candidate_views": v} for v in (True, 4, "8")] + [
            {"candidate_views": 8, "candidate_pool_limit": 7}, {"candidate_pool_limit": 17},
            {"sft_loss_mode": "all"}, {"ttt_loss_mode": []}, {"candidate_ranker": "answers"},
            {"rerank_fraction": .5}, {"rerank_fraction": float("nan")}, {"likelihood_normalization": "average"},
            {"training_seconds": float("inf")}, {"seed": True}, {"model_path": "/unverified"},
            {"model_base_identity": M.base_identity()}, {"session_deadline_epoch": time.time() + 999999},
            {"adapter_resume": {}}, {"curriculum": {}}]
        for parameters in invalid:
            with self.subTest(parameters=parameters), patch.object(B, "prepare_model") as prepare:
                with self.assertRaises(ValueError):
                    B.bootstrap({"solver_parameters": parameters})
                prepare.assert_not_called()
        for name in ("model_path", "model_base_identity", "adapter_resume", "curriculum"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                B.bootstrap({name: "forbidden"})

    def test_adapter_exact_copy_index_and_source_closure(self):
        source, index, rows = self.source_adapter()
        self.assertEqual(set(rows), {M.INDEX} | {M.ROOTS["adapter_resume"] + "/" + name for name in
            ("manifest.json", "adapter_config.json", "adapter_model.safetensors")})
        resolved = M.resolve_materials(source, index, source_files=rows)
        self.assertEqual(resolved["adapter_resume"]["root"], str(source / M.ROOTS["adapter_resume"]))
        self.assertNotIn("model_base_identity", resolved)
        for bad in ("0" * 64, None):
            with self.assertRaises(ValueError):
                M.resolve_materials(source, bad, source_files=rows)
        incomplete = {name: row for name, row in rows.items() if not name.endswith("safetensors")}
        with self.assertRaisesRegex(ValueError, "source closure"):
            M.resolve_materials(source, index, source_files=incomplete)

    def test_adapter_full_cpu_tensor_validation_not_model_loading(self):
        source, index, rows = self.source_adapter()
        specs = M.resolve_materials(source, index, source_files=rows)
        result = M.validate_runtime_materials(specs, {}, training_root="unused", training_manifest_path="unused", public_path="unused")
        self.assertTrue(result["adapter_tensor_bytes_verified"])
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["adapter_loaded"])
        self.assertFalse(result["training_executed"])

    def test_adapter_wrong_manifest_pin_and_byte_tamper(self):
        root, manifest, pin = self.adapter()
        with self.assertRaisesRegex(ValueError, "external material"):
            M.verify_adapter(root, "0" * 64)
        (root / "adapter_model.safetensors").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "bytes/hash"):
            M.verify_adapter(root, pin)

    def test_adapter_origin_and_identity_must_be_protected(self):
        root, manifest, _ = self.adapter()
        for change in (lambda m: m["base_identity"].update(model_source="synthetic-unverified"),
                       lambda m: m["origin"].update(phase="post_public"),
                       lambda m: m["origin"].update(public_ttt_applied=True),
                       lambda m: m["origin"].update(public_labels_used=True),
                       lambda m: m["origin"].update(run_summary_sha256="bad")):
            value = deepcopy(manifest)
            change(value)
            pin = self.seal(root / "manifest.json", value)
            with self.assertRaises(ValueError):
                M.verify_adapter(root, pin)

    def test_adapter_declared_tensor_tamper_cannot_pass_cpu_prepare(self):
        root, manifest, _ = self.adapter()
        first = next(iter(manifest["exported_tensors"]))
        manifest["exported_tensors"][first]["sha256"] = "0" * 64
        pin = self.seal(root / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "tensor metadata"):
            M.verify_adapter(root, pin, tensors=True)

    def test_extra_files_directories_and_traversal_rejected(self):
        root, manifest, pin = self.adapter()
        for name, directory in (("evaluator.json", False), ("unlisted", True)):
            path = root / name
            path.mkdir() if directory else path.write_bytes(b"must not be copied")
            with self.assertRaisesRegex(ValueError, "unexpected material"):
                M.verify_adapter(root, pin)
            path.rmdir() if directory else path.unlink()
        manifest["files"]["../secret"] = manifest["files"].pop("adapter_config.json")
        pin = self.seal(root / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "exact adapter"):
            M.verify_adapter(root, pin)
        for name in ("../a", "/a", "a//b", "a/./b", "C:/a", "a\\b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                M.exact_inventory(root, {name: {"bytes": 1, "sha256": "a" * 64}}, total_limit=100)

    def test_symlink_and_special_file_rejected(self):
        root, _, pin = self.adapter()
        path = root / "adapter_config.json"
        target = self.root / "config"
        path.rename(target)
        try:
            path.symlink_to(target)
        except OSError as exc:
            if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
                self.skipTest("Windows symlink privilege unavailable")
            raise
        with self.assertRaisesRegex(ValueError, "symlink"):
            M.verify_adapter(root, pin)
        path.unlink()
        target.rename(path)
        if hasattr(os, "mkfifo"):
            os.mkfifo(root / "secret-fifo")
            with self.assertRaisesRegex(ValueError, "inventory"):
                M.verify_adapter(root, pin)

    def test_noncanonical_duplicate_manifest_rejected(self):
        root, _, _ = self.adapter()
        path = root / "manifest.json"
        path.write_bytes(path.read_bytes().replace(b'{', b'{"format":"duplicate",', 1))
        with self.assertRaisesRegex(ValueError, "canonical"):
            M.verify_adapter(root, L.sha(path))

    def test_index_cannot_supply_arbitrary_roots_or_configuration(self):
        source, _, rows = self.source_adapter()
        original = json.loads((source / M.INDEX).read_bytes())
        for update in ({"root": "../adapter"}, {"root": "/tmp/adapter"}, {"model_base_identity": M.base_identity()},
                       {"root": "materials/adapter-resume/../qwen14b"}):
            value = deepcopy(original)
            value["materials"]["adapter_resume"].update(update)
            pin = self.seal(source / M.INDEX, value)
            with self.assertRaisesRegex(ValueError, "fixed source-relative"):
                M.resolve_materials(source, pin, source_files=rows)

    def test_orphan_materials_and_half_specifications_rejected(self):
        (self.root / M.ROOTS["adapter_resume"]).mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "unmanifested"):
            M.resolve_materials(self.root, source_files={})
        for kwargs in ({"adapter_resume_root": "/never-read"}, {"adapter_resume_manifest_sha256": "a" * 64},
                       {"curriculum_root": "/never-read"}, {"curriculum_producer_hashes": {}},
                       {"curriculum_manifest_sha256": "a" * 64}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                M.package_materials(self.root, **kwargs)

    def test_fixture_curriculum_is_never_deployable(self):
        root, manifest, pin = self.curriculum()
        with self.assertRaisesRegex(ValueError, "synthetic fixtures"):
            M.verify_curriculum_inventory(root, pin, manifest["source"]["implementation_sha256"])
        with self.assertRaisesRegex(ValueError, "actual training"):
            M.package_materials(self.root / "destination", curriculum_root=root, curriculum_manifest_sha256=pin,
                                curriculum_producer_hashes=manifest["source"]["implementation_sha256"])

    def test_curriculum_structure_and_production_admission_are_separate(self):
        # Relabel only to exercise structural parsing; actual load_admission is
        # patched to reject. This is not a claim this fixture is production data.
        from tools.arc2_goal_sprint_20261017 import curriculum as C
        root, manifest, _ = self.curriculum()
        manifest["mode"] = "production"
        pin = self.seal(root / "manifest.json", manifest)
        producer = manifest["source"]["implementation_sha256"]
        rows = M.verify_curriculum_inventory(root, pin, producer)
        self.assertEqual(set(rows), set(self.source_rows(root)))
        with patch.object(C, "load_admission", side_effect=ValueError("synthetic admission rejected")) as admission:
            with self.assertRaisesRegex(ValueError, "synthetic admission rejected"):
                M.verify_curriculum(root, pin, producer, training_root="actual-train",
                                    training_manifest_path="actual-manifest", public_path="solver-only")
            admission.assert_called_once_with("actual-train", "actual-manifest", "solver-only")
        wrong = {**producer, next(iter(producer)): "0" * 64}
        with self.assertRaisesRegex(ValueError, "producer identity"):
            M.verify_curriculum_inventory(root, pin, wrong)
        manifest["bundles"][0]["path"] = "../../evaluator.json"
        pin = self.seal(root / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "bundle path"):
            M.verify_curriculum_inventory(root, pin, producer)

    def test_curriculum_full_loader_receives_external_producer_and_admission(self):
        from tools.arc2_goal_sprint_20261017 import curriculum as C
        sentinel = object()
        with patch.object(M, "verify_curriculum_inventory", return_value={"fixture": {}}), \
             patch.object(C, "load_admission", return_value=sentinel) as admission, \
             patch.object(C, "load_curriculum", return_value=({}, {"synthetic_mock": True})) as loader:
            M.verify_curriculum("fixture", "a" * 64, {"fixture": "b" * 64}, training_root="train",
                                training_manifest_path="manifest", public_path="public")
        admission.assert_called_once_with("train", "manifest", "public")
        loader.assert_called_once_with("fixture", admission=sentinel, expected_manifest_sha256="a" * 64,
                                      expected_producer_hashes={"fixture": "b" * 64})

    def metadata(self):
        path = self.root / "metadata.json"
        path.write_text(json.dumps({"id_no": 138123872, "id": "danielwuu/iris-x-learning-agent-20261011",
                                   "is_private": True, "machine_shape": "NvidiaRtxPro6000"}))
        return path

    def test_notebook_optional_pins_and_defaults(self):
        metadata = self.metadata()
        for enabled in (False, True):
            destination = self.root / ("enabled" if enabled else "default")
            options = {"solver_parameters": {"candidate_views": 8, "candidate_ranker": "vote"},
                       "continuation_materials_sha256": "c" * 64} if enabled else {}
            P.build_notebook_only(destination, "synthetic-run", "danielwuu/synthetic-source/1", "a" * 64,
                "danielwuu/synthetic-solver/1", time.time() - 1, source_payload_sha256="b" * 64,
                original_metadata=metadata, **options)
            request = json.loads((destination / "dispatch-request.json").read_bytes())
            self.assertEqual("solver_parameters" in request, enabled)
            self.assertEqual("continuation_materials_sha256" in request, enabled)
            self.assertNotIn("model_base_identity", request)
            self.assertNotIn("adapter_resume", request)
            self.assertEqual(request["session_deadline_epoch"] - request["started_epoch"], 43200)

    def test_optional_notebook_construction_never_imports_ml_dependencies(self):
        metadata = self.metadata()
        real_import = builtins.__import__
        def blocked(name, *args, **kwargs):
            if name in {"torch", "peft", "transformers", "pydantic"} or name.startswith(
                    ("torch.", "peft.", "transformers.", "tools.arc2_goal_sprint_20261017.run")):
                raise AssertionError("portable notebook packaging imported optional ML dependency: " + name)
            return real_import(name, *args, **kwargs)
        with patch.object(builtins, "__import__", side_effect=blocked):
            P.build_notebook_only(self.root / "portable-notebook", "synthetic-run", "danielwuu/synthetic-source/1", "a" * 64,
                "danielwuu/synthetic-solver/1", time.time() - 1, source_payload_sha256="b" * 64,
                original_metadata=metadata, solver_parameters={"candidate_views": 8, "candidate_ranker": "vote"},
                continuation_materials_sha256="c" * 64)

    def test_notebook_rejects_bad_parameters_before_creating_output(self):
        path = self.root / "forbidden"
        with self.assertRaisesRegex(ValueError, "protected"):
            P.build_notebook_only(path, "synthetic-run", "danielwuu/synthetic-source/1", "a" * 64,
                "danielwuu/synthetic-solver/1", time.time() - 1, source_payload_sha256="b" * 64,
                solver_parameters={"model_path": "/bad"})
        self.assertFalse(path.exists())

    def test_source_import_closure_includes_helpers_not_test_fixtures(self):
        paths = {p.relative_to(ROOT).as_posix() for p in P.source_paths(ROOT)}
        self.assertIn("tools/arc2_goal_sprint_20261017/materials.py", paths)
        self.assertIn("tools/arc2_goal_sprint_20261017/curriculum.py", paths)
        self.assertFalse(any("tests/" in n or ".irisx" in n or "evaluator" in n or "test_" in n for n in paths))

    def test_source_build_exact_optional_materials_and_transport_roundtrip(self):
        adapter, _, adapter_pin = self.adapter()
        wheelhouse = self.root / "wheels"
        wheelhouse.mkdir()
        for name in ("pydantic", "pydantic_core", "annotated_types", "typing_inspection"):
            with zipfile.ZipFile(wheelhouse / (name + "-1-py3-none-any.whl"), "w") as archive:
                archive.writestr(name + "-1.dist-info/METADATA", "Name: " + name + "\nVersion: 1\n")
        source = self.root / "review"
        P.build_source(ROOT, source, wheelhouse, "synthetic-next-source", adapter_resume_root=adapter,
                       adapter_resume_manifest_sha256=adapter_pin)
        manifest = json.loads((source / "source-manifest.json").read_bytes())
        index = L.sha(source / M.INDEX)
        M.resolve_materials(source, index, source_files=manifest["files"])
        self.assertFalse(any(n.startswith(".irisx/") or "/evaluator/" in n or n.endswith("model-00001-of-00008.safetensors")
                             for n in manifest["files"]))
        transport = self.root / "transport"
        P.source_transport(source, transport)
        with zipfile.ZipFile(transport / "source-payload.zip.bin") as archive:
            self.assertEqual(set(archive.namelist()), set(manifest["files"]))
            self.assertEqual(archive.read(M.INDEX), (source / M.INDEX).read_bytes())
        self.assertEqual(set(p.name for p in transport.iterdir()), {"source-manifest.json", "source-payload.zip.bin"})

    def model_material_fixture(self):
        source = self.root / "model-source"
        material = source / "materials/qwen14b"
        overlay = material / "hf-overlay"
        overlay.mkdir(parents=True)
        inputs = self.root / "model-input"
        mount = inputs / "qwen-3/transformers/14b/1"
        mount.mkdir(parents=True)
        providers = {"config.json": (b'{"synthetic":true}', "verified-config"),
                     "model.safetensors.index.json": (b'{"weight_map":{}}', "weight-index"),
                     "model-00001.safetensors": (b"synthetic-weight-not-a-real-model", "base-weight")}
        for name, (body, _) in providers.items():
            (mount / name).write_bytes(body)
        (overlay / "config.json").write_bytes(b'{"synthetic_overlay":true}')
        contract = {"provider_files": {name: {"size_bytes": len(body), "sha256": body_sha(body),
                     "runtime_full_sha256_required": True, "role": role} for name, (body, role) in providers.items()},
                    "overlay_files": {"config.json": {"size_bytes": (overlay / "config.json").stat().st_size,
                                                      "sha256": L.sha(overlay / "config.json")}}}
        pin = self.seal(material / "material-contract.json", contract)
        runtime = self.root / "model-runtime"
        runtime.mkdir()
        return source, inputs, mount, overlay, runtime, contract, pin

    def test_prepare_model_verifies_full_shards_index_overlay_before_receipt(self):
        source, inputs, mount, _, runtime, contract, pin = self.model_material_fixture()
        with patch.object(B, "SOURCE", source), patch.object(B, "MODEL_CONTRACT_SHA256", pin), \
             patch.object(M, "MODEL_CONTRACT_SHA256", pin):
            try:
                model_path, actual_mount = B.prepare_model(inputs, runtime)
            except OSError as exc:
                if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
                    self.skipTest("Windows symlink privilege unavailable")
                raise
            receipt = json.loads((runtime / "model-receipt.json").read_bytes())
            self.assertEqual(receipt["model_base_identity"], M.base_identity())
        self.assertEqual(actual_mount, mount)
        self.assertEqual(receipt["model_path"], str(model_path))
        self.assertFalse(receipt["model_loaded"])
        self.assertEqual(set(receipt["verified_sha256"]), set(contract["provider_files"]))
        self.assertEqual((model_path / "config.json").read_bytes(), b'{"synthetic_overlay":true}')

    def test_prepare_model_tamper_or_unverified_weight_cannot_create_receipt(self):
        source, inputs, mount, _, runtime, contract, pin = self.model_material_fixture()
        (mount / "model-00001.safetensors").write_bytes(b"X" * len(b"synthetic-weight-not-a-real-model"))
        with patch.object(B, "SOURCE", source), patch.object(B, "MODEL_CONTRACT_SHA256", pin), \
             patch.object(M, "MODEL_CONTRACT_SHA256", pin):
            with self.assertRaisesRegex(ValueError, "provider hash"):
                B.prepare_model(inputs, runtime)
        self.assertFalse((runtime / "model-receipt.json").exists())

    def test_prepare_model_extra_overlay_is_rejected(self):
        source, inputs, _, overlay, runtime, _, pin = self.model_material_fixture()
        (overlay / "unreviewed-secret.txt").write_text("synthetic-do-not-copy")
        with patch.object(B, "SOURCE", source), patch.object(B, "MODEL_CONTRACT_SHA256", pin), \
             patch.object(M, "MODEL_CONTRACT_SHA256", pin):
            try:
                with self.assertRaisesRegex(ValueError, "mounted inventory"):
                    B.prepare_model(inputs, runtime)
            except OSError as exc:
                if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
                    self.skipTest("Windows symlink privilege unavailable")
                raise
        self.assertFalse((runtime / "model-receipt.json").exists())

    def bootstrap_fixture(self):
        inputs = self.root / "input"
        inputs.mkdir()
        source = inputs / "synthetic-source"
        source.mkdir()
        source_sha = L.write_new(source / "source-manifest.json", {"files": {}})
        for role in ("wheels", "interpreter", "training"):
            (inputs / B.REFERENCES[role].split("/")[1]).mkdir()
        training = inputs / B.REFERENCES["training"].split("/")[1]
        training_sha = L.write_new(training / "manifest.json", {"files": {}})
        solver = inputs / "synthetic-solver/solver"
        solver.mkdir(parents=True)
        for name in ("public-challenges.json", "LICENSE", "NOTICE"):
            (solver / name).write_text("{}")
        solver_sha = L.write_new(solver / "manifest.json", {"files": self.source_rows(solver)})
        mount = inputs / "qwen-3/transformers/14b/1"
        mount.mkdir(parents=True)
        now = time.time() - 1
        request = {"run_id": "synthetic-bootstrap", "started_epoch": now, "session_deadline_epoch": now + 43200,
            "input_root": str(inputs), "working_root": str(self.root / "working"), "runtime_root": str(self.root / "runtime"),
            "source_dataset": "danielwuu/synthetic-source/1", "solver_dataset": "danielwuu/synthetic-solver/1",
            "source_manifest_sha256": source_sha, "evaluation_mode": "external-cpu"}
        return source, training_sha, solver_sha, mount, request

    def test_bootstrap_injects_identity_path_only_after_successful_prepare(self):
        source, training_sha, solver_sha, mount, request = self.bootstrap_fixture()
        order = []
        def install(req, roots, runtime):
            L.write_new(runtime / "runtime-receipt.json", {"synthetic": True})
            return sys.executable, "synthetic-env", {}
        def model(inputs, runtime, **kwargs):
            order.append("verified-model")
            L.write_new(runtime / "model-receipt.json", {"synthetic": True})
            return runtime / "verified-model-path", mount
        def launch(argv, **kwargs):
            config = json.loads(Path(argv[-1]).read_bytes())["solver_config"]
            self.assertEqual(order, ["verified-model"])
            self.assertEqual(config["model_path"], str(Path(request["runtime_root"]) / "verified-model-path"))
            self.assertEqual(config["model_base_identity"], M.base_identity())
            self.assertEqual(config["training_manifest_sha256"], training_sha)
            self.assertNotIn("candidate_views", config)
            self.assertNotIn("adapter_resume", config)
            order.append("launch")
            return subprocess.CompletedProcess(argv, 0)
        with patch.object(B, "SOURCE", source), patch.object(B, "TRAINING_MANIFEST_SHA256", training_sha), \
             patch.object(B, "SOLVER_MANIFEST_SHA256", solver_sha), patch.object(B, "install", side_effect=install), \
             patch.object(B, "prepare_model", side_effect=model), patch.object(B.subprocess, "run", side_effect=launch):
            B.bootstrap(request)
        self.assertEqual(order, ["verified-model", "launch"])

    def test_failed_prepare_cannot_inject_or_launch(self):
        source, training_sha, solver_sha, _, request = self.bootstrap_fixture()
        with patch.object(B, "SOURCE", source), patch.object(B, "TRAINING_MANIFEST_SHA256", training_sha), \
             patch.object(B, "SOLVER_MANIFEST_SHA256", solver_sha), patch.object(B, "install", return_value=("python", "env", {})), \
             patch.object(B, "prepare_model", side_effect=ValueError("synthetic bad base shard")), \
             patch.object(B.subprocess, "run") as run, patch.object(M, "base_identity") as identity:
            with self.assertRaisesRegex(ValueError, "bad base shard"):
                B.bootstrap(request)
            identity.assert_not_called()
            run.assert_not_called()
        self.assertFalse((Path(request["working_root"]) / "launch-request.json").exists())

    def test_prepare_optional_cpu_validation_never_claims_loaded(self):
        source, index, rows = self.source_adapter()
        specs = M.resolve_materials(source, index, source_files=rows)
        runtime = self.root / "runtime"
        runtime.mkdir()
        now = time.time()
        # Uses this CPU test interpreter, not a claimed installed production runtime.
        receipt = B.prepare_continuation({"session_deadline_epoch": now + 1000}, specs, {}, sys.executable,
            os.environ.copy(), runtime, self.root / "unused-training", self.root / "unused-public")
        self.assertTrue(receipt["adapter_tensor_bytes_verified"])
        self.assertFalse(receipt["model_loaded"])
        self.assertFalse(receipt["adapter_loaded"])
        self.assertTrue((runtime / "continuation-receipt.json").is_file())


if __name__ == "__main__":
    unittest.main()
