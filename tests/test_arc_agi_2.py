from __future__ import annotations

import copy
import contextlib
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from support import ROOT  # noqa: F401  # also places src/ on sys.path

from irisx import arc_agi_2 as arc
from irisx.artifacts import artifact_ref, make_artifact, validate_artifact, write_artifact
from irisx.canonical import digest_bytes, read_json, write_json
from irisx.cli import main as cli_main
from irisx.contracts import CandidateConfiguration, EngineeringTrial, EvaluationResult, load_contract
from irisx.errors import ValidationError


def _task(value: int) -> dict:
    return {
        "train": [{"input": [[value % 10]], "output": [[(value + 1) % 10]]}],
        "test": [{"input": [[(value + 2) % 10]], "output": [[(value % 9) + 1]]}],
    }


def _files_under(upstream: Path) -> list[str]:
    return sorted(
        path.relative_to(upstream).as_posix()
        for path in upstream.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(upstream).parts
    )


def _identity(upstream: Path) -> tuple[str, list[str]]:
    return arc.OFFICIAL_REMOTE, _files_under(upstream)


def _write_source(root: Path) -> None:
    upstream = root / "upstream"
    (upstream / ".git").mkdir(parents=True)
    for index in range(arc.TRAINING_TASK_COUNT):
        write_json(upstream / "data" / "training" / f"{index:08x}.json", _task(index))
    for index in range(arc.EVALUATION_TASK_COUNT):
        write_json(upstream / "data" / "evaluation" / f"{index + 2000:08x}.json", _task(index + 2000))
    payload = arc._build_source_payload(root, materialized_at_utc="2026-09-18T00:00:00Z")
    write_artifact(
        root / "provenance.json",
        make_artifact("irisx/source-provenance", "arc-agi-2-official-source", "1.0.0", payload),
    )


def _resign(path: Path) -> dict:
    value = read_json(path)
    value = make_artifact(value["schema"], value["artifact_id"], value["version"], value["payload"])
    write_json(path, value)
    return value


def _truth_and_solver(trial_root: Path) -> tuple[dict, dict]:
    truth = validate_artifact(read_json(trial_root / arc.TRIAL_FILES["truth"]), kind="irisx/arc-agi-2-evaluator-truth")
    solver = validate_artifact(read_json(trial_root / arc.TRIAL_FILES["solver_cases"]), kind="irisx/arc-agi-2-solver-cases")
    return truth, solver


def _predictions(trial_root: Path, configuration: CandidateConfiguration, correct: int, *, second: bool = False) -> dict:
    truth, _ = _truth_and_solver(trial_root)
    trial = load_contract(trial_root / arc.TRIAL_FILES["trial"], EngineeringTrial)
    workload = load_contract(trial_root / arc.TRIAL_FILES["workload"])
    evaluator = validate_artifact(read_json(trial_root / arc.TRIAL_FILES["evaluator"]), kind="irisx/evaluator-definition")
    cases = []
    for position, case in enumerate(truth["payload"]["cases"]):
        expected = case["expected_outputs"][0]
        incorrect = [[0]] if expected != [[0]] else [[9]]
        attempts = [incorrect, expected] if second and position < correct else [expected, incorrect]
        if position >= correct:
            attempts = [incorrect, incorrect]
        cases.append({"case_id": case["case_id"], "test_predictions": [{"test_index": 0, "attempts": attempts}]})
    return make_artifact(
        "irisx/arc-agi-2-predictions",
        f"{configuration.artifact_id}-predictions",
        "1.0.0",
        {
            "trial_ref": trial.ref(),
            "workload_ref": workload.ref(),
            "evaluator_ref": artifact_ref(evaluator),
            "configuration_ref": configuration.ref(),
            "cases": cases,
        },
    )


def _observations(configuration: CandidateConfiguration) -> dict:
    return make_artifact(
        "irisx/trial-observations",
        f"{configuration.artifact_id}-observations",
        "1.0.0",
        {
            "configuration_ref": configuration.ref(),
            "evaluation_leak_events": 0,
            "network_calls": 0,
            "provider_calls": 0,
            "monetary_cost": 0,
            "identity_binding_failures": 0,
            "runtime_seconds": {"state": "unknown", "value": None, "unit": "seconds"},
            "peak_memory_mb": {"state": "not_evaluated", "value": None, "unit": "mb"},
        },
    )


def _make_run(trial_root: Path, run_root: Path, candidate_correct: int) -> None:
    shutil.copytree(trial_root, run_root / "trial")
    copied_trial = run_root / "trial"
    baseline = load_contract(copied_trial / arc.TRIAL_FILES["baseline"], CandidateConfiguration)
    candidate = load_contract(copied_trial / arc.TRIAL_FILES["candidate"], CandidateConfiguration)
    assert isinstance(baseline, CandidateConfiguration)
    assert isinstance(candidate, CandidateConfiguration)
    for name, configuration, correct in (
        ("baseline", baseline, 0),
        ("candidate", candidate, candidate_correct),
    ):
        prediction = _predictions(copied_trial, configuration, correct, second=name == "candidate")
        observation = _observations(configuration)
        result = arc._build_evaluation_result_from_structural_evidence(
            copied_trial,
            prediction,
            observation,
            result_id=f"arc-agi-2-trial-001-{name}-result",
        )
        write_artifact(run_root / "predictions" / f"{name}.json", prediction)
        write_artifact(run_root / "observations" / f"{name}.json", observation)
        result.write(run_root / "results" / f"{name}.json")


def _bind_trial(trial_root: Path) -> None:
    asset_path = trial_root / "assets" / "fixture-solver.bin"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(b"offline synthetic solver fixture\n")
    descriptor = make_artifact(
        "irisx/local-solver-descriptor",
        "offline-fixture-solver",
        "1.0.0",
        {
            "kind": "opaque-local-executable-fixture",
            "immutable_identity": "fixture-only-not-a-real-model",
            "asset_path": "assets/fixture-solver.bin",
            "asset_digest": digest_bytes(asset_path.read_bytes()),
            "network_required": False,
        },
    )
    write_artifact(trial_root / arc.OPTIONAL_TRIAL_FILES["model"], descriptor)
    baseline_old = load_contract(trial_root / arc.TRIAL_FILES["baseline"], CandidateConfiguration)
    candidate_old = load_contract(trial_root / arc.TRIAL_FILES["candidate"], CandidateConfiguration)
    trial_old = load_contract(trial_root / arc.TRIAL_FILES["trial"], EngineeringTrial)
    assert isinstance(baseline_old, CandidateConfiguration)
    assert isinstance(candidate_old, CandidateConfiguration)
    assert isinstance(trial_old, EngineeringTrial)

    envelope_old = validate_artifact(read_json(trial_root / arc.TRIAL_FILES["envelope"]), kind="irisx/execution-envelope")
    envelope_payload = copy.deepcopy(envelope_old["payload"])
    envelope_payload["model_solver_ref"] = artifact_ref(descriptor)
    envelope_payload["hardware_identity"] = "synthetic-test-hardware"
    envelope = make_artifact(envelope_old["schema"], envelope_old["artifact_id"], envelope_old["version"], envelope_payload)

    def bound(configuration: CandidateConfiguration) -> CandidateConfiguration:
        payload = copy.deepcopy(configuration.payload)
        payload["components"]["model"] = artifact_ref(descriptor)
        payload["components"]["workflow_control"] = artifact_ref(envelope)
        payload["known_limitations"] = []
        return CandidateConfiguration(configuration.artifact_id, configuration.version, payload)

    baseline = bound(baseline_old)
    candidate = bound(candidate_old)
    trial_payload = copy.deepcopy(trial_old.payload)
    trial_payload["baseline_configuration_ref"] = baseline.ref()
    trial_payload["candidate_configuration_refs"] = [candidate.ref()]
    trial = EngineeringTrial(trial_old.artifact_id, trial_old.version, trial_payload)
    profile_old = validate_artifact(read_json(trial_root / arc.TRIAL_FILES["profile"]), kind="irisx/arc-agi-2-trial-profile")
    profile_payload = copy.deepcopy(profile_old["payload"])
    profile_payload.update(
        {
            "trial_ref": trial.ref(),
            "baseline_configuration_ref": baseline.ref(),
            "candidate_configuration_ref": candidate.ref(),
            "execution_envelope_ref": artifact_ref(envelope),
            "run_authorization_ref": None,
        }
    )
    profile = make_artifact(profile_old["schema"], profile_old["artifact_id"], profile_old["version"], profile_payload)
    baseline.write(trial_root / arc.TRIAL_FILES["baseline"])
    candidate.write(trial_root / arc.TRIAL_FILES["candidate"])
    trial.write(trial_root / arc.TRIAL_FILES["trial"])
    write_artifact(trial_root / arc.TRIAL_FILES["envelope"], envelope)
    write_artifact(trial_root / arc.TRIAL_FILES["profile"], profile)


def _rewrite_unbound_envelope(trial_root: Path, updates: dict) -> None:
    envelope_path = trial_root / arc.TRIAL_FILES["envelope"]
    envelope_old = validate_artifact(read_json(envelope_path), kind="irisx/execution-envelope")
    payload = copy.deepcopy(envelope_old["payload"])
    payload.update(updates)
    envelope = make_artifact(envelope_old["schema"], envelope_old["artifact_id"], envelope_old["version"], payload)
    baseline_old = load_contract(trial_root / arc.TRIAL_FILES["baseline"], CandidateConfiguration)
    candidate_old = load_contract(trial_root / arc.TRIAL_FILES["candidate"], CandidateConfiguration)
    trial_old = load_contract(trial_root / arc.TRIAL_FILES["trial"], EngineeringTrial)
    assert isinstance(baseline_old, CandidateConfiguration)
    assert isinstance(candidate_old, CandidateConfiguration)
    assert isinstance(trial_old, EngineeringTrial)

    def rebind(configuration: CandidateConfiguration) -> CandidateConfiguration:
        configuration_payload = copy.deepcopy(configuration.payload)
        configuration_payload["components"]["workflow_control"] = artifact_ref(envelope)
        return CandidateConfiguration(configuration.artifact_id, configuration.version, configuration_payload)

    baseline = rebind(baseline_old)
    candidate = rebind(candidate_old)
    trial_payload = copy.deepcopy(trial_old.payload)
    trial_payload["baseline_configuration_ref"] = baseline.ref()
    trial_payload["candidate_configuration_refs"] = [candidate.ref()]
    trial = EngineeringTrial(trial_old.artifact_id, trial_old.version, trial_payload)
    profile_path = trial_root / arc.TRIAL_FILES["profile"]
    profile_old = validate_artifact(read_json(profile_path), kind="irisx/arc-agi-2-trial-profile")
    profile_payload = copy.deepcopy(profile_old["payload"])
    profile_payload["execution_envelope_ref"] = artifact_ref(envelope)
    profile_payload["trial_ref"] = trial.ref()
    profile_payload["baseline_configuration_ref"] = baseline.ref()
    profile_payload["candidate_configuration_ref"] = candidate.ref()
    profile = make_artifact(profile_old["schema"], profile_old["artifact_id"], profile_old["version"], profile_payload)
    write_artifact(envelope_path, envelope)
    baseline.write(trial_root / arc.TRIAL_FILES["baseline"])
    candidate.write(trial_root / arc.TRIAL_FILES["candidate"])
    trial.write(trial_root / arc.TRIAL_FILES["trial"])
    write_artifact(profile_path, profile)


def _synthetic_result(
    trial: EngineeringTrial,
    workload,
    configuration: CandidateConfiguration,
    passed_count: int,
) -> EvaluationResult:
    cases = []
    for position, workload_case in enumerate(workload.payload["cases"]):
        passed = position < passed_count
        cases.append(
            {
                "case_id": workload_case["case_id"],
                "segment": workload_case["segment"],
                "passed": passed,
                "critical_failure": False,
                "score": 1 if passed else 0,
                "detail": "synthetic structural acceptance-boundary fixture",
            }
        )
    accuracy = passed_count / len(cases)
    zero_count = {"state": "observed", "value": 0, "unit": "count"}
    return EvaluationResult(
        f"{configuration.artifact_id}-{passed_count}-result",
        "1.0.0",
        {
            "trial_ref": trial.ref(),
            "workload_ref": workload.ref(),
            "evaluator_ref": workload.payload["evaluator_ref"],
            "configuration_ref": configuration.ref(),
            "cases": cases,
            "metrics": {
                "accuracy": {"state": "observed", "value": accuracy, "unit": "ratio"},
                f"accuracy.{arc.SEGMENT}": {"state": "observed", "value": accuracy, "unit": "ratio"},
                "critical_failures": zero_count,
                "evaluation_leak_events": zero_count,
                "network_calls": zero_count,
                "provider_calls": zero_count,
                "monetary_cost": {"state": "observed", "value": 0, "unit": "usd"},
                "malformed_or_missing_cases": zero_count,
                "workload_cases": {"state": "observed", "value": len(cases), "unit": "count"},
                "identity_binding_failures": zero_count,
            },
            "resource_use": {
                "network_calls": zero_count,
                "provider_calls": zero_count,
                "monetary_cost": {"state": "observed", "value": 0, "unit": "usd"},
                "runtime_seconds": {"state": "not_evaluated", "value": None, "unit": "seconds"},
                "peak_memory_mb": {"state": "not_evaluated", "value": None, "unit": "mb"},
            },
            "known_limitations": arc.P2_LIMITATIONS,
        },
    )


class ArcAgi2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / "source"
        cls.trial = cls.root / "trial"
        with mock.patch.object(arc, "_validate_source_git_identity", side_effect=_identity):
            _write_source(cls.source)
            arc.validate_source(cls.source)
            arc.prepare_trial(cls.source, cls.trial)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def copy_source(self) -> Path:
        destination = self.root / self._testMethodName / "source"
        shutil.copytree(self.source, destination)
        return destination

    def copy_trial(self) -> Path:
        destination = self.root / self._testMethodName / "trial"
        shutil.copytree(self.trial, destination)
        return destination

    def validate_source(self, source: Path) -> dict:
        with mock.patch.object(arc, "_validate_source_git_identity", side_effect=_identity):
            return arc.validate_source(source)

    def test_source_accepts_exact_identity_and_preserves_bytes(self) -> None:
        provenance = self.validate_source(self.source)
        evaluation = self.source / "upstream" / "data" / "evaluation" / "000007d0.json"
        entry = next(item for item in provenance["payload"]["files"] if item["path"].endswith("000007d0.json"))
        self.assertEqual(entry["content_digest"], digest_bytes(evaluation.read_bytes()))
        self.assertEqual(provenance["payload"]["splits"]["evaluation"]["task_count"], 120)

    def test_source_rejects_wrong_repository_commit_and_stale_manifest(self) -> None:
        for field, value in (("repository", "third-party/arc"), ("pinned_commit", "0" * 40)):
            source = self.copy_source()
            provenance_path = source / "provenance.json"
            provenance = read_json(provenance_path)
            provenance["payload"][field] = value
            write_json(provenance_path, make_artifact(provenance["schema"], provenance["artifact_id"], provenance["version"], provenance["payload"]))
            with self.assertRaises(ValidationError):
                self.validate_source(source)
            shutil.rmtree(source.parent)
        source = self.copy_source()
        provenance = read_json(source / "provenance.json")
        provenance["payload"]["files"][0]["byte_count"] += 1
        write_json(source / "provenance.json", provenance)
        with self.assertRaises(ValidationError):
            self.validate_source(source)

    def test_source_rejects_branch_head_changed_missing_and_extra_tasks(self) -> None:
        with mock.patch.object(arc, "_validate_source_git_identity", side_effect=ValidationError("branch head")):
            with self.assertRaises(ValidationError):
                arc.validate_source(self.source)
        source = self.copy_source()
        task_path = source / "upstream" / "data" / "evaluation" / "000007d0.json"
        value = read_json(task_path)
        value["test"][0]["output"] = [[8]]
        write_json(task_path, value)
        with self.assertRaises(ValidationError):
            self.validate_source(source)
        shutil.rmtree(source.parent)
        source = self.copy_source()
        (source / "upstream" / "data" / "evaluation" / "000007d0.json").unlink()
        with self.assertRaises(ValidationError):
            self.validate_source(source)
        shutil.rmtree(source.parent)
        source = self.copy_source()
        write_json(source / "upstream" / "data" / "evaluation" / "ffffffff.json", _task(9))
        with self.assertRaises(ValidationError):
            self.validate_source(source)

    def test_trial_has_120_frozen_isolated_cases_and_training_only_specialization(self) -> None:
        arc.validate_trial_bundle(self.trial)
        workload = load_contract(self.trial / arc.TRIAL_FILES["workload"])
        solver = validate_artifact(read_json(self.trial / arc.TRIAL_FILES["solver_cases"]), kind="irisx/arc-agi-2-solver-cases")
        truth = validate_artifact(read_json(self.trial / arc.TRIAL_FILES["truth"]), kind="irisx/arc-agi-2-evaluator-truth")
        specialization = validate_artifact(read_json(self.trial / arc.TRIAL_FILES["specialization"]), kind="irisx/specialization-derivation")
        specification = load_contract(self.trial / arc.TRIAL_FILES["specification"])
        baseline = load_contract(self.trial / arc.TRIAL_FILES["baseline"], CandidateConfiguration)
        candidate = load_contract(self.trial / arc.TRIAL_FILES["candidate"], CandidateConfiguration)
        envelope = validate_artifact(read_json(self.trial / arc.TRIAL_FILES["envelope"]), kind="irisx/execution-envelope")
        self.assertEqual(len(workload.payload["cases"]), 120)
        self.assertTrue(workload.payload["frozen"])
        self.assertTrue(all(set(case) == {"case_id", "segment", "demonstrations", "test_inputs"} for case in solver["payload"]["cases"]))
        self.assertEqual(len(specialization["payload"]["influenced_files"]), 1000)
        self.assertTrue(all(item["path"].startswith("data/training/") for item in specialization["payload"]["influenced_files"]))
        self.assertEqual(specialization["payload"]["policy"], arc._policy_from_training_observations(specialization["payload"]["observations"]))
        self.assertEqual(specification.payload["material_refs"][0]["locator"], arc.TRIAL_FILES["source"])
        self.assertEqual(baseline.payload["components"]["workflow_control"], artifact_ref(envelope))
        self.assertEqual(candidate.payload["components"]["workflow_control"], artifact_ref(envelope))
        first_case = workload.payload["cases"][0]
        self.assertEqual(arc._resolve_arc_case_source(solver, first_case, "input")["test_inputs"], solver["payload"]["cases"][0]["test_inputs"])
        self.assertEqual(arc._resolve_arc_case_source(truth, first_case, "expected")["expected_outputs"], truth["payload"]["cases"][0]["expected_outputs"])
        stale_case = copy.deepcopy(first_case)
        stale_case["input_ref"]["locator"] = "materialized/unrelated.json/case/input"
        with self.assertRaisesRegex(ValidationError, "does not resolve exactly"):
            arc._resolve_arc_case_source(solver, stale_case, "input")
        serialized = str(arc.solver_payload(self.trial))
        self.assertNotIn("expected_outputs", serialized)

    def test_specialization_policy_changes_with_training_observations(self) -> None:
        source_ref = {"kind": "irisx/source-provenance", "artifact_id": "source", "version": "1.0.0", "content_digest": "sha256:" + "0" * 64}
        first_task = _task(1)
        second_task = copy.deepcopy(first_task)
        second_task["train"][0]["output"] = [[1, 2]]
        first = arc._training_derivation([("data/training/a.json", first_task, "sha256:" + "1" * 64)], source_ref)
        second = arc._training_derivation([("data/training/a.json", second_task, "sha256:" + "2" * 64)], source_ref)
        self.assertNotEqual(first["payload"]["observations"], second["payload"]["observations"])
        self.assertNotEqual(first["payload"]["policy"], second["payload"]["policy"])

    def test_trial_rejects_workload_mutation_and_unauthorized_component_difference(self) -> None:
        trial = self.copy_trial()
        workload_path = trial / arc.TRIAL_FILES["workload"]
        workload = read_json(workload_path)
        workload["payload"]["cases"].pop()
        write_json(workload_path, workload)
        with self.assertRaises(ValidationError):
            arc.validate_trial_bundle(trial)
        baseline = load_contract(self.trial / arc.TRIAL_FILES["baseline"], CandidateConfiguration)
        candidate = load_contract(self.trial / arc.TRIAL_FILES["candidate"], CandidateConfiguration)
        assert isinstance(baseline, CandidateConfiguration)
        assert isinstance(candidate, CandidateConfiguration)
        for component in ("context_retrieval", "adaptation", "workflow_control"):
            payload = copy.deepcopy(candidate.payload)
            payload["components"][component] = payload["components"]["validation"]
            changed = CandidateConfiguration(candidate.artifact_id, candidate.version, payload)
            with self.assertRaises(ValidationError):
                arc._validate_configuration_equivalence(baseline, changed)
        payload = copy.deepcopy(candidate.payload)
        payload["components"]["model"] = payload["components"]["validation"]
        changed = CandidateConfiguration(candidate.artifact_id, candidate.version, payload)
        with self.assertRaises(ValidationError):
            arc._validate_configuration_equivalence(baseline, changed)

    def test_pass_at_two_first_second_failure_and_strict_malformed_rejection(self) -> None:
        solver = [{"case_id": "case", "test_inputs": [[[1]]]}]
        truth = [{"case_id": "case", "expected_outputs": [[[2]]]}]

        def evidence(attempts: list, *, tests: list | None = None) -> list:
            return [{"case_id": "case", "test_predictions": tests or [{"test_index": 0, "attempts": attempts}]}]

        self.assertTrue(arc.score_predictions(solver, truth, evidence([[[2]], [[0]]]))[0]["passed"])
        self.assertTrue(arc.score_predictions(solver, truth, evidence([[[0]], [[2]]]))[0]["passed"])
        self.assertFalse(arc.score_predictions(solver, truth, evidence([[[0]], [[1]]]))[0]["passed"])
        self.assertFalse(arc.score_predictions(solver, truth, evidence([[[2, 2]], [[0]]]))[0]["passed"])
        for invalid in (
            evidence([[[2]], [[0]], [[1]]]),
            evidence([[[2]]]),
            evidence([[[2], [2, 2]], [[0]]]),
            evidence([[[10]], [[0]]]),
            evidence([[[2]], [[0]]], tests=[{"test_index": 1, "attempts": [[[2]], [[0]]]}]),
        ):
            with self.assertRaises(ValidationError):
                arc.score_predictions(solver, truth, invalid)

    def test_preflight_fails_closed_unbound_and_on_credentials(self) -> None:
        report = arc.preflight_trial(self.trial, environment={})
        self.assertFalse(report["payload"]["ready"])
        self.assertIn("local-model-solver-binding", report["payload"]["blockers"])
        self.assertIn("separate-owner-run-authorization", report["payload"]["blockers"])
        credential_report = arc.preflight_trial(self.trial, environment={"OPENAI_API_KEY": "redacted"})
        self.assertIn("provider-credentials-absent", credential_report["payload"]["blockers"])
        self.assertNotIn("redacted", str(credential_report))

    def test_preflight_rejects_network_provider_cost_and_extra_budget(self) -> None:
        for updates in (
            {"network_enabled": True},
            {"provider_execution": True},
            {"credentials_allowed": True},
            {"maximum_external_cost_usd": 1},
            {"attempt_limit_per_test_input": 3},
            {"solver_invocation_limit_per_configuration": 121},
        ):
            trial = self.copy_trial()
            _rewrite_unbound_envelope(trial, updates)
            with self.assertRaises(ValidationError):
                arc.preflight_trial(trial, environment={})
            shutil.rmtree(trial.parent)

    def test_bound_preflight_rejects_asset_corruption_and_envelope_mismatch(self) -> None:
        trial = self.copy_trial()
        _bind_trial(trial)
        report = arc.preflight_trial(trial, environment={})
        self.assertFalse(report["payload"]["ready"])
        self.assertEqual(report["payload"]["blockers"], ["separate-owner-run-authorization"])
        (trial / "assets" / "fixture-solver.bin").write_bytes(b"corrupt")
        with self.assertRaises(ValidationError):
            arc.preflight_trial(trial, environment={})
        shutil.rmtree(trial.parent)
        trial = self.copy_trial()
        _bind_trial(trial)
        envelope_path = trial / arc.TRIAL_FILES["envelope"]
        envelope = read_json(envelope_path)
        envelope["payload"]["model_solver_ref"] = None
        write_json(envelope_path, make_artifact(envelope["schema"], envelope["artifact_id"], envelope["version"], envelope["payload"]))
        with self.assertRaises(ValidationError):
            arc.preflight_trial(trial, environment={})

    def test_result_evidence_recomputes_and_rejects_tampering(self) -> None:
        run = self.root / self._testMethodName / "run"
        _make_run(self.trial, run, 6)
        with self.assertRaisesRegex(ValidationError, "not admissible"):
            arc.validate_run_results(run)
        candidate = load_contract(run / "results" / "candidate.json", EvaluationResult)
        assert isinstance(candidate, EvaluationResult)
        self.assertEqual(candidate.payload["metrics"]["accuracy"]["value"], 0.05)
        result_path = run / "results" / "candidate.json"
        value = read_json(result_path)
        value["payload"]["metrics"]["accuracy"]["value"] = 1
        write_json(result_path, make_artifact(value["schema"], value["artifact_id"], value["version"], value["payload"]))
        predictions = validate_artifact(read_json(run / "predictions" / "candidate.json"), kind="irisx/arc-agi-2-predictions")
        observations = validate_artifact(read_json(run / "observations" / "candidate.json"), kind="irisx/trial-observations")
        recomputed = arc._build_evaluation_result_from_structural_evidence(
            run / "trial", predictions, observations, result_id="arc-agi-2-trial-001-candidate-result"
        )
        self.assertNotEqual(read_json(result_path), recomputed.to_dict())

    def test_below_five_points_is_valid_but_unaccepted_and_five_points_is_accepted(self) -> None:
        trial = load_contract(self.trial / arc.TRIAL_FILES["trial"], EngineeringTrial)
        workload = load_contract(self.trial / arc.TRIAL_FILES["workload"])
        requirements = load_contract(self.trial / arc.TRIAL_FILES["requirements"])
        baseline = load_contract(self.trial / arc.TRIAL_FILES["baseline"], CandidateConfiguration)
        candidate = load_contract(self.trial / arc.TRIAL_FILES["candidate"], CandidateConfiguration)
        assert isinstance(trial, EngineeringTrial)
        assert isinstance(baseline, CandidateConfiguration)
        assert isinstance(candidate, CandidateConfiguration)
        baseline_result = _synthetic_result(trial, workload, baseline, 0)
        below_result = _synthetic_result(trial, workload, candidate, 5)
        decision = arc.select_configuration(
            trial,
            workload,
            requirements,
            baseline_result,
            [below_result],
            {baseline.content_digest: baseline, candidate.content_digest: candidate},
        )
        acceptance = arc.build_p2_acceptance(trial, workload, requirements, baseline_result, below_result, decision)
        self.assertEqual(decision.payload["outcome"], "promote")
        self.assertAlmostEqual(acceptance["payload"]["absolute_improvement"], 5 / 120)
        self.assertFalse(acceptance["payload"]["accepted"])
        accepted_result = _synthetic_result(trial, workload, candidate, 6)
        decision = arc.select_configuration(
            trial,
            workload,
            requirements,
            baseline_result,
            [accepted_result],
            {baseline.content_digest: baseline, candidate.content_digest: candidate},
        )
        acceptance = arc.build_p2_acceptance(trial, workload, requirements, baseline_result, accepted_result, decision)
        self.assertEqual(acceptance["payload"]["absolute_improvement"], 0.05)
        self.assertTrue(acceptance["payload"]["accepted"])

    def test_exact_six_task_acceptance_boundary_for_every_baseline(self) -> None:
        trial = load_contract(self.trial / arc.TRIAL_FILES["trial"], EngineeringTrial)
        workload = load_contract(self.trial / arc.TRIAL_FILES["workload"])
        requirements = load_contract(self.trial / arc.TRIAL_FILES["requirements"])
        baseline = load_contract(self.trial / arc.TRIAL_FILES["baseline"], CandidateConfiguration)
        candidate = load_contract(self.trial / arc.TRIAL_FILES["candidate"], CandidateConfiguration)
        assert isinstance(trial, EngineeringTrial)
        assert isinstance(baseline, CandidateConfiguration)
        assert isinstance(candidate, CandidateConfiguration)
        configurations = {baseline.content_digest: baseline, candidate.content_digest: candidate}
        for baseline_count in range(115):
            with self.subTest(baseline_count=baseline_count):
                baseline_result = _synthetic_result(trial, workload, baseline, baseline_count)
                candidate_result = _synthetic_result(trial, workload, candidate, baseline_count + 6)
                decision = arc.select_configuration(
                    trial, workload, requirements, baseline_result, [candidate_result], configurations
                )
                acceptance = arc.build_p2_acceptance(
                    trial, workload, requirements, baseline_result, candidate_result, decision
                )
                self.assertEqual(acceptance["payload"]["task_improvement"], 6)
                self.assertTrue(acceptance["payload"]["accepted"])

    def test_package_ineligible_below_gate(self) -> None:
        acceptance = make_artifact(
            "irisx/p2-acceptance",
            "arc-agi-2-trial-001-acceptance",
            "1.0.0",
            {"package_eligible": False},
        )
        with mock.patch.object(
            arc,
            "validate_run_selection",
            return_value=(mock.sentinel.decision, acceptance),
        ):
            with self.assertRaisesRegex(ValidationError, "five-point acceptance gate"):
                arc.build_p2_package(
                    self.root / self._testMethodName / "run",
                    self.root / self._testMethodName / "package",
                )

    def test_trial_local_authorization_cannot_unlock_preflight_or_package(self) -> None:
        bound = self.root / self._testMethodName / "bound"
        shutil.copytree(self.trial, bound)
        _bind_trial(bound)
        authorization = make_artifact(
            "irisx/owner-run-authorization",
            "synthetic-test-run-authorization",
            "1.0.0",
            {"authorized": True},
        )
        write_artifact(bound / "owner-run-authorization.json", authorization)
        with self.assertRaisesRegex(ValidationError, "membership mismatch"):
            arc.preflight_trial(bound, environment={})
        (bound / "owner-run-authorization.json").unlink()
        report = arc.preflight_trial(bound, environment={})
        self.assertFalse(report["payload"]["ready"])
        self.assertEqual(report["payload"]["blockers"], ["separate-owner-run-authorization"])
        run = self.root / self._testMethodName / "run"
        _make_run(bound, run, 6)
        write_artifact(run / "preflight.json", report)
        with self.assertRaisesRegex(ValidationError, "not admissible"):
            arc.select_run(run)
        with self.assertRaisesRegex(ValidationError, "not admissible"):
            arc.build_p2_package(run, self.root / self._testMethodName / "package")

    def test_cli_offline_validation_selection_and_package_commands(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(arc, "_validate_source_git_identity", side_effect=_identity):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(cli_main(["arc-agi-2", "source", "validate", str(self.source)]), 0)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(cli_main(["arc-agi-2", "trial", "validate", str(self.trial)]), 0)
            self.assertEqual(cli_main(["arc-agi-2", "trial", "preflight", str(self.trial)]), 2)

        run = self.root / self._testMethodName / "run"
        _make_run(self.trial, run, 6)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(cli_main(["arc-agi-2", "result", "validate", str(run)]), 2)
            self.assertEqual(cli_main(["arc-agi-2", "select", str(run)]), 2)
        write_artifact(run / "preflight.json", arc.preflight_trial(run / "trial", environment={}))
        package = self.root / self._testMethodName / "package"
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(
                cli_main(["arc-agi-2", "package", "build", "--run", str(run), "--output", str(package)]),
                2,
            )


if __name__ == "__main__":
    unittest.main()
