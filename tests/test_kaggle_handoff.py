from __future__ import annotations

import copy
from pathlib import Path
import shutil
import tempfile
import unittest

import support  # noqa: F401
from arc_support import (
    dataset_binding,
    make_arc_source,
    make_model_source,
    make_runtime_wheels,
    observations,
    prediction_document,
    runner_logs,
    write_outbound_binding,
)

from irisx.arc_agi2 import prepare_trial
from irisx.arc_package import build_arc_package, verify_arc_package
from irisx.artifacts import load_artifact
from irisx.canonical import digest_bytes, read_json, write_json
from irisx.errors import ValidationError
from irisx.kaggle import (
    CHECKPOINT_OUTBOUND_PATHS,
    RESULT_PATHS,
    build_outbound_package,
    build_result_package,
    create_model_provenance,
    evaluate_imported_run,
    import_quarantine,
    outbound_manifest_digest,
    preflight,
    verify_outbound_package,
    verify_result_package,
)
from irisx.kaggle_runner_v4 import CHECKPOINT_POLICY
from irisx.transport import RESULT_LIMITS, TRIAL_LIMITS, verify_zip, write_zip


ROOT = Path(__file__).resolve().parents[1]


class KaggleHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        profile = make_arc_source(self.source)
        self.source_profile = profile
        self.trial = self.root / "trial"
        prepare_trial(self.source, self.trial, profile=profile)
        self.model_source = make_model_source(self.root)
        self.binding = write_outbound_binding(self.root)
        self.runtime_wheels = make_runtime_wheels(self.root)
        self.outbound = self.root / "outbound/run-001/trial-input.zip"
        build_outbound_package(
            self.trial,
            self.model_source,
            self.binding,
            self.runtime_wheels,
            self.outbound,
            repository_root=ROOT,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _result_metadata(self) -> dict:
        outbound_manifest, _ = verify_outbound_package(self.outbound)
        metadata = outbound_manifest["metadata"]
        return {
            "trial_manifest_digest": outbound_manifest_digest(outbound_manifest),
            "model_source_provenance_digest": metadata["model"]["source_provenance_digest"],
            "model_dataset": metadata["model_dataset"],
            "bundle_id": outbound_manifest["package_id"],
            "repository_revision": metadata["repository"]["revision"],
            "notebook_digest": metadata["notebook_digest"],
            "runner_digest": metadata["runner_digest"],
            "baseline_configuration_ref": metadata["baseline_configuration_ref"],
            "candidate_configuration_ref": metadata["candidate_configuration_ref"],
            "execution_envelope_ref": metadata["execution_envelope_ref"],
        }

    def _build_result(self, *, baseline_passed: int = 90, candidate_passed: int = 96) -> Path:
        result = self.root / "kaggle/inbound/quarantine/run-001/result-package.zip"
        baseline = prediction_document(self.trial, "baseline", baseline_passed)
        candidate = prediction_document(self.trial, "candidate", candidate_passed)
        build_result_package(
            result,
            "run-001",
            baseline,
            candidate,
            observations(),
            runner_logs(self.trial, baseline, candidate),
            self._result_metadata(),
        )
        return result

    def test_notebook_and_runner_are_thin_offline_adapters(self) -> None:
        notebook = (ROOT / "trials/first-real-domain/kaggle-notebook.ipynb").read_text(encoding="utf-8")
        runner = (ROOT / "src/irisx/kaggle_runner.py").read_text(encoding="utf-8")
        for term in ("/kaggle/input", "/kaggle/working", "NVIDIA RTX PRO 6000", "local_files_only=True", "TRANSFORMERS_OFFLINE"):
            self.assertIn(term, notebook + runner)
        self.assertIn("/kaggle/input/datasets/danielwuu/trial-input", notebook)
        self.assertIn("verify_and_copy_mounted_trial", notebook)
        self.assertIn("model-source-provenance", notebook + runner)
        self.assertIn("INPUT / 'datasets'", notebook)
        self.assertNotIn("model-package.zip", notebook + runner)
        for prohibited in ("pip install", "kaggle api", "requests.get", "openai.", "anthropic."):
            self.assertNotIn(prohibited, (notebook + runner).lower())

    def test_run_002_uses_checkpointing_v4_without_mutating_run_001_adapter(self) -> None:
        binding = write_outbound_binding(self.root / "v4", bundle_id="run-002")
        outbound = self.root / "v4/outbound/run-002/trial-input.zip"
        build_outbound_package(
            self.trial,
            self.model_source,
            binding,
            self.runtime_wheels,
            outbound,
            repository_root=ROOT,
        )
        manifest, _ = verify_outbound_package(outbound)
        _, contents, _ = verify_zip(outbound, limits=TRIAL_LIMITS)
        wheel_paths = {path for path in contents if path.startswith("runtime/wheels/")}
        self.assertEqual(set(contents), CHECKPOINT_OUTBOUND_PATHS | wheel_paths)
        self.assertEqual(manifest["package_id"], "run-002")
        self.assertEqual(manifest["metadata"]["checkpoint_policy"], CHECKPOINT_POLICY)
        self.assertEqual(
            manifest["metadata"]["runner_core_digest"],
            digest_bytes(contents["runtime/runner_core.py"]),
        )
        notebook = contents["runtime/notebook.ipynb"].decode("utf-8")
        runner = contents["runtime/runner.py"].decode("utf-8")
        for term in (
            "checkpoint-package.zip",
            "--resume-checkpoint",
            "after-every-attempt",
            "cumulative-across-sessions",
            "progress.jsonl",
        ):
            self.assertIn(term, notebook + runner)
        self.assertEqual(
            (ROOT / "trials/first-real-domain/kaggle-notebook.ipynb").read_bytes(),
            (ROOT / "trials/first-real-domain/kaggle-notebook-v3.ipynb").read_bytes(),
        )

    def test_run_002_result_requires_complete_checkpoint_resume_evidence(self) -> None:
        binding = write_outbound_binding(self.root / "v4-result", bundle_id="run-002")
        outbound = self.root / "v4-result/outbound/run-002/trial-input.zip"
        build_outbound_package(
            self.trial,
            self.model_source,
            binding,
            self.runtime_wheels,
            outbound,
            repository_root=ROOT,
        )
        outbound_manifest, _ = verify_outbound_package(outbound)
        metadata = outbound_manifest["metadata"]
        result_metadata = {
            "trial_manifest_digest": outbound_manifest_digest(outbound_manifest),
            "model_source_provenance_digest": metadata["model"]["source_provenance_digest"],
            "model_dataset": metadata["model_dataset"],
            "bundle_id": "run-002",
            "repository_revision": metadata["repository"]["revision"],
            "notebook_digest": metadata["notebook_digest"],
            "runner_digest": metadata["runner_digest"],
            "runner_core_digest": metadata["runner_core_digest"],
            "checkpoint_policy": metadata["checkpoint_policy"],
            "baseline_configuration_ref": metadata["baseline_configuration_ref"],
            "candidate_configuration_ref": metadata["candidate_configuration_ref"],
            "execution_envelope_ref": metadata["execution_envelope_ref"],
        }
        baseline = prediction_document(self.trial, "baseline", 90)
        candidate = prediction_document(self.trial, "candidate", 96)
        logs = runner_logs(self.trial, baseline, candidate)
        observed = observations()
        observed["format_version"] = "2.0"
        observed["checkpoint"] = {
            "format": "irisx/arc-agi-2-checkpoint",
            "format_version": "1.0",
            "resume_count": 1,
            "session_count": 2,
            "interrupted_attempts": 1,
            "completed_invocations": len(logs["events"]),
            "total_invocations": len(logs["events"]),
            "cumulative_wall_clock_seconds": observed["wall_clock_seconds"],
            "sessions": [
                {
                    "session_index": index,
                    "hardware": observed["hardware"],
                    "software": observed["software"],
                }
                for index in range(2)
            ],
        }
        result = self.root / "v4-result/kaggle/inbound/quarantine/run-002/result-package.zip"
        build_result_package(
            result,
            "run-002",
            baseline,
            candidate,
            observed,
            logs,
            result_metadata,
        )
        verify_result_package(result, outbound, self.trial)

        observed["checkpoint"]["cumulative_wall_clock_seconds"] += 1
        stale = self.root / "v4-result/stale-result.zip"
        build_result_package(
            stale,
            "run-002",
            baseline,
            candidate,
            observed,
            logs,
            result_metadata,
        )
        with self.assertRaisesRegex(ValidationError, "cumulative wall clock"):
            verify_result_package(stale, outbound, self.trial)

    def test_model_source_and_outbound_package_are_deterministic_and_truth_free(self) -> None:
        second = self.root / "deterministic-copy/outbound/run-001/trial-input.zip"
        build_outbound_package(
            self.trial,
            self.model_source,
            self.binding,
            self.runtime_wheels,
            second,
            repository_root=ROOT,
        )
        self.assertEqual(self.outbound.read_bytes(), second.read_bytes())
        _, contents, _ = verify_zip(self.outbound, limits=TRIAL_LIMITS)
        self.assertNotIn("evaluator-truth.json", "\n".join(contents))
        self.assertFalse(any(b'"expected"' in data for data in contents.values()))
        self.assertFalse(any(b"irisx/evaluation-result" in data for data in contents.values()))
        solver = read_json(self.trial / "solver-cases.json")
        self.assertTrue(all(set(pair) == {"input"} for case in solver["payload"]["cases"] for pair in case["test"]))

    def test_outbound_path_must_match_the_bundle_id(self) -> None:
        mismatched = self.root / "outbound/run-001-v2/trial-input.zip"
        with self.assertRaisesRegex(ValidationError, "parent directory equal to binding.bundle_id"):
            build_outbound_package(
                self.trial,
                self.model_source,
                self.binding,
                self.runtime_wheels,
                mismatched,
                repository_root=ROOT,
            )

    def test_direct_unpacked_model_root_and_sidecar_are_supported(self) -> None:
        direct = self.root / "direct-model"
        shutil.copytree(self.model_source / "source", direct)
        write_json(direct / "dataset-metadata.json", {"id": "fixture-owner/qwen-model"})
        sidecar = direct.parent / f"{direct.name}-provenance.json"
        create_model_provenance(direct, sidecar, require_git_identity=False)
        output = self.root / "direct/outbound/run-001/trial-input.zip"
        build_outbound_package(self.trial, direct, self.binding, self.runtime_wheels, output, repository_root=ROOT)
        manifest, _ = verify_outbound_package(output)
        self.assertEqual(manifest["metadata"]["model"]["source_provenance_digest"], read_json(sidecar)["content_digest"])

    def test_outbound_rejects_undeclared_truth_stale_runner_and_public_dataset(self) -> None:
        manifest, contents, _ = verify_zip(self.outbound, limits=TRIAL_LIMITS)
        changed = dict(contents)
        changed["evaluator-truth.json"] = (self.trial / "evaluator-truth.json").read_bytes()
        injected = self.root / "injected.zip"
        write_zip(injected, manifest["package_kind"], manifest["package_id"], changed, manifest["metadata"], limits=TRIAL_LIMITS)
        with self.assertRaisesRegex(ValidationError, "membership"):
            verify_outbound_package(injected)

        changed = dict(contents)
        changed["runtime/runner.py"] += b"\n# stale\n"
        stale = self.root / "stale-runner.zip"
        write_zip(stale, manifest["package_kind"], manifest["package_id"], changed, manifest["metadata"], limits=TRIAL_LIMITS)
        with self.assertRaisesRegex(ValidationError, "runner source digest"):
            verify_outbound_package(stale)

        binding = read_json(self.binding)
        binding["model_dataset"]["private"] = False
        public = self.root / "public-binding.json"
        write_json(public, binding)
        with self.assertRaisesRegex(ValidationError, "private and immutable"):
            build_outbound_package(
                self.trial,
                self.model_source,
                public,
                self.runtime_wheels,
                self.root / "public/outbound/run-001/trial-input.zip",
                repository_root=ROOT,
            )

    def test_result_is_predictions_and_observations_only_and_import_is_atomic(self) -> None:
        result = self._build_result()
        _, contents, _ = verify_result_package(result, self.outbound, self.trial)
        self.assertEqual(set(contents), RESULT_PATHS)
        self.assertFalse(any(b"irisx/evaluation-result" in data for data in contents.values()))
        self.assertFalse(any(b"irisx/selection-decision" in data for data in contents.values()))
        run_root = self.root / "run"
        normalized = import_quarantine(result, self.outbound, self.trial, run_root)
        self.assertEqual(normalized, run_root / "run-001")
        self.assertTrue((normalized / "import-evidence.json").is_file())
        summary = evaluate_imported_run(self.trial, normalized)
        self.assertEqual(summary["selection_outcome"], "promote")
        self.assertTrue(summary["p2_accepted"])
        self.assertTrue(summary["package_eligible"])

        invalid = self.root / "kaggle/inbound/quarantine/run-002/result-package.zip"
        metadata = self._result_metadata()
        metadata["bundle_id"] = "substituted"
        build_result_package(
            invalid,
            "run-002",
            (baseline := prediction_document(self.trial, "baseline", 90)),
            (candidate := prediction_document(self.trial, "candidate", 96)),
            observations(),
            runner_logs(self.trial, baseline, candidate),
            metadata,
        )
        with self.assertRaisesRegex(ValidationError, "upstream identity"):
            import_quarantine(invalid, self.outbound, self.trial, run_root)
        self.assertFalse((run_root / "run-002").exists())

    def test_result_rejects_hardware_network_credentials_cost_and_incomplete_attempts(self) -> None:
        mutations = {
            "hardware": lambda value: value["hardware"].update({"gpu_model": "Tesla T4"}),
            "internet": lambda value: value.update({"internet_disabled": False}),
            "credentials": lambda value: value.update({"credentials_present": True}),
            "provider": lambda value: value.update({"provider_calls": 1}),
            "cost": lambda value: value.update({"external_paid_cost_usd": 1}),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                observed = observations()
                mutate(observed)
                path = self.root / f"{name}.zip"
                build_result_package(
                    path,
                    "run-001",
                    (baseline := prediction_document(self.trial, "baseline", 90)),
                    (candidate := prediction_document(self.trial, "candidate", 96)),
                    observed,
                    runner_logs(self.trial, baseline, candidate),
                    self._result_metadata(),
                )
                with self.assertRaises(ValidationError):
                    verify_result_package(path, self.outbound, self.trial)

        incomplete = prediction_document(self.trial, "candidate", 96)
        incomplete["cases"][0]["tests"][0]["attempts"].pop()
        path = self.root / "incomplete.zip"
        build_result_package(
            path,
            "run-001",
            (baseline := prediction_document(self.trial, "baseline", 90)),
            incomplete,
            observations(),
            runner_logs(self.trial, baseline, incomplete),
            self._result_metadata(),
        )
        with self.assertRaisesRegex(ValidationError, "exactly two"):
            verify_result_package(path, self.outbound, self.trial)

        baseline = prediction_document(self.trial, "baseline", 90)
        candidate = prediction_document(self.trial, "candidate", 96)
        logs = runner_logs(self.trial, baseline, candidate)
        logs["events"].pop()
        path = self.root / "incomplete-logs.zip"
        build_result_package(
            path,
            "run-001",
            baseline,
            candidate,
            observations(),
            logs,
            self._result_metadata(),
        )
        with self.assertRaisesRegex(ValidationError, "logs do not exactly cover"):
            verify_result_package(path, self.outbound, self.trial)

    def test_preflight_binds_every_static_gate_but_never_authorizes_the_run(self) -> None:
        outbound_manifest, _ = verify_outbound_package(self.outbound)
        envelope = load_artifact(self.trial / "execution-envelope.json", kind="irisx/execution-envelope")
        binding = {
            "model_dataset": outbound_manifest["metadata"]["model_dataset"],
            "trial_dataset": dataset_binding("trial-input"),
            "repository_revision": outbound_manifest["metadata"]["repository"]["revision"],
            "repository_clean": True,
            "notebook_digest": outbound_manifest["metadata"]["notebook_digest"],
            "runner_digest": outbound_manifest["metadata"]["runner_digest"],
            "hardware": {"gpu_count": 1, "gpu_model": "NVIDIA RTX PRO 6000", "gpu_memory_gb": 96},
            "internet_disabled": True,
            "credentials_present": False,
            "provider_calls_enabled": False,
            "external_paid_cost_usd": 0,
            "execution_limits": {
                field: envelope["payload"][field]
                for field in (
                    "attempts_per_test_input", "invocation_limit_per_configuration", "timeout_seconds_per_invocation",
                    "wall_clock_limit_seconds", "seed_policy", "decoding", "output_limits",
                )
            },
            "result_shape": sorted(RESULT_PATHS),
            "quarantine_path": ".irisx/arc-agi-2/trial-001/kaggle/inbound/quarantine/run-001/result-package.zip",
            "retention": read_json(self.binding)["retention"],
            "runtime_dependencies": read_json(self.binding)["runtime_dependencies"],
        }
        binding_path = self.root / "preflight.json"
        write_json(binding_path, binding)
        report = preflight(self.trial, self.model_source, self.outbound, binding_path)
        self.assertTrue(report["payload"]["technical_ready"])
        self.assertFalse(report["payload"]["run_authorized"])
        self.assertIn("owner", report["payload"]["authorization_blockers"][0])

        binding["hardware"]["gpu_model"] = "Tesla T4"
        write_json(binding_path, binding)
        report = preflight(self.trial, self.model_source, self.outbound, binding_path)
        self.assertFalse(report["payload"]["technical_ready"])
        self.assertTrue(any("hardware" in blocker for blocker in report["payload"]["technical_blockers"]))

    def test_run_002_preflight_requires_checkpoint_policy_and_runner_core(self) -> None:
        outbound_binding = write_outbound_binding(self.root / "v4-preflight", bundle_id="run-002")
        outbound = self.root / "v4-preflight/outbound/run-002/trial-input.zip"
        build_outbound_package(
            self.trial,
            self.model_source,
            outbound_binding,
            self.runtime_wheels,
            outbound,
            repository_root=ROOT,
        )
        manifest, _ = verify_outbound_package(outbound)
        envelope = load_artifact(self.trial / "execution-envelope.json", kind="irisx/execution-envelope")
        binding = {
            "model_dataset": manifest["metadata"]["model_dataset"],
            "trial_dataset": dataset_binding("trial-input"),
            "repository_revision": manifest["metadata"]["repository"]["revision"],
            "repository_clean": True,
            "notebook_digest": manifest["metadata"]["notebook_digest"],
            "runner_digest": manifest["metadata"]["runner_digest"],
            "runner_core_digest": manifest["metadata"]["runner_core_digest"],
            "checkpoint_policy": manifest["metadata"]["checkpoint_policy"],
            "hardware": {"gpu_count": 1, "gpu_model": "NVIDIA RTX PRO 6000", "gpu_memory_gb": 96},
            "internet_disabled": True,
            "credentials_present": False,
            "provider_calls_enabled": False,
            "external_paid_cost_usd": 0,
            "execution_limits": {
                field: envelope["payload"][field]
                for field in (
                    "attempts_per_test_input", "invocation_limit_per_configuration", "timeout_seconds_per_invocation",
                    "wall_clock_limit_seconds", "seed_policy", "decoding", "output_limits",
                )
            },
            "result_shape": sorted(RESULT_PATHS),
            "quarantine_path": ".irisx/arc-agi-2/trial-001/kaggle/inbound/quarantine/run-002/result-package.zip",
            "retention": read_json(outbound_binding)["retention"],
            "runtime_dependencies": read_json(outbound_binding)["runtime_dependencies"],
        }
        binding_path = self.root / "v4-preflight/preflight.json"
        write_json(binding_path, binding)
        report = preflight(self.trial, self.model_source, outbound, binding_path)
        self.assertTrue(report["payload"]["technical_ready"])

        del binding["checkpoint_policy"]
        write_json(binding_path, binding)
        report = preflight(self.trial, self.model_source, outbound, binding_path)
        self.assertFalse(report["payload"]["technical_ready"])
        self.assertTrue(any("preflight_binding" in blocker for blocker in report["payload"]["technical_blockers"]))

    def test_eligible_domain_package_is_local_and_independently_recomputed(self) -> None:
        result = self._build_result()
        run = import_quarantine(result, self.outbound, self.trial, self.root / "run")
        evaluate_imported_run(self.trial, run)
        package = self.root / "domain-package"
        build_arc_package(
            self.trial,
            self.source,
            run,
            self.model_source,
            self.outbound,
            result,
            package,
            _source_profile=self.source_profile,
        )
        manifest = verify_arc_package(package, _source_profile=self.source_profile)
        self.assertEqual(manifest.payload["selected_configuration_ref"]["artifact_id"], "arc-agi-2-trial-001-candidate")
        model_copy = package / "deployment/model-source/source/model.safetensors"
        model_copy.write_bytes(model_copy.read_bytes() + b"corrupt")
        with self.assertRaises(ValidationError):
            verify_arc_package(package, _source_profile=self.source_profile)

    def test_domain_package_rejects_valid_improvement_below_five_points(self) -> None:
        result = self._build_result(baseline_passed=90, candidate_passed=95)
        run = import_quarantine(result, self.outbound, self.trial, self.root / "run")
        summary = evaluate_imported_run(self.trial, run)
        self.assertEqual(summary["selection_outcome"], "promote")
        self.assertFalse(summary["p2_accepted"])
        with self.assertRaisesRegex(ValidationError, "five-point"):
            build_arc_package(
                self.trial,
                self.source,
                run,
                self.model_source,
                self.outbound,
                result,
                self.root / "ineligible-package",
                _source_profile=self.source_profile,
            )


if __name__ == "__main__":
    unittest.main()
