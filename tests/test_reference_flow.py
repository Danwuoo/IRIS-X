from __future__ import annotations

import contextlib
import copy
import io
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

import support  # noqa: F401

from irisx import cli
from irisx.canonical import digest_bytes
from irisx.contracts import (
    CandidateConfiguration,
    DomainPackageManifest,
    DomainSpecification,
    EngineeringTrial,
    EvaluationResult,
    RequirementSet,
    SelectionDecision,
    WorkloadDefinition,
    load_contract,
)
from irisx.engine import select_configuration
from irisx.errors import ValidationError
from irisx.fixture import prepare_fixture, run_trial, validate_trial
from irisx.package import build_package, verify_package


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def rewrite_evidence_graph(
    root: Path,
    *,
    packaged: bool,
    nonexistent_trial_requirement: bool = False,
    wrong_locator_field: str | None = None,
) -> None:
    """Re-sign an adversarial but structurally valid run or package graph."""

    if packaged:
        specification_path = root / "domain/specification.json"
        workload_path = root / "evaluation/workload.json"
        requirements_path = root / "evaluation/requirements.json"
        trial_path = root / "trial/trial.json"
        decision_path = root / "selection/decision.json"
        baseline_config_path = root / "specialization/configurations/qualification-baseline.json"
        candidate_config_path = root / "specialization/configurations/qualification-candidate.json"
        baseline_result_path = root / "evaluation/results/qualification-baseline-result.json"
        candidate_result_path = root / "evaluation/results/qualification-candidate-result.json"
    else:
        specification_path = root / "specification.json"
        workload_path = root / "workload.json"
        requirements_path = root / "requirements.json"
        trial_path = root / "trial.json"
        decision_path = root / "decision.json"
        baseline_config_path = root / "baseline.json"
        candidate_config_path = root / "candidate.json"
        baseline_result_path = root / "results/qualification-baseline-result.json"
        candidate_result_path = root / "results/qualification-candidate-result.json"

    specification = load_contract(specification_path, DomainSpecification)
    workload = load_contract(workload_path, WorkloadDefinition)
    requirements = load_contract(requirements_path, RequirementSet)
    trial = load_contract(trial_path, EngineeringTrial)
    baseline_config = load_contract(baseline_config_path, CandidateConfiguration)
    candidate_config = load_contract(candidate_config_path, CandidateConfiguration)
    baseline_result = load_contract(baseline_result_path, EvaluationResult)
    candidate_result = load_contract(candidate_result_path, EvaluationResult)

    if wrong_locator_field is not None:
        workload_payload = copy.deepcopy(workload.payload)
        workload_payload["cases"][0][f"{wrong_locator_field}_ref"]["locator"] = f"unrelated/location/{wrong_locator_field}"
        workload = WorkloadDefinition(workload.artifact_id, workload.version, workload_payload)
        specification_payload = copy.deepcopy(specification.payload)
        specification_payload["workload_ref"] = workload.ref()
        specification = DomainSpecification(specification.artifact_id, specification.version, specification_payload)

    trial_payload = copy.deepcopy(trial.payload)
    trial_payload["domain_specification_ref"] = specification.ref()
    trial_payload["workload_ref"] = workload.ref()
    if nonexistent_trial_requirement:
        missing_requirement_ref = copy.deepcopy(requirements.ref())
        missing_requirement_ref["artifact_id"] = "nonexistent-requirements"
        missing_requirement_ref["content_digest"] = "sha256:" + "0" * 64
        trial_payload["requirement_set_ref"] = missing_requirement_ref
    else:
        trial_payload["requirement_set_ref"] = requirements.ref()
    trial = EngineeringTrial(trial.artifact_id, trial.version, trial_payload)

    rebuilt_results: list[EvaluationResult] = []
    for original in (baseline_result, candidate_result):
        payload = copy.deepcopy(original.payload)
        payload["trial_ref"] = trial.ref()
        payload["workload_ref"] = workload.ref()
        rebuilt_results.append(EvaluationResult(original.artifact_id, original.version, payload))
    baseline_result, candidate_result = rebuilt_results
    configurations = {
        baseline_config.content_digest: baseline_config,
        candidate_config.content_digest: candidate_config,
    }
    decision = select_configuration(
        trial,
        workload,
        requirements,
        baseline_result,
        [candidate_result],
        configurations,
    )

    specification.write(specification_path)
    workload.write(workload_path)
    trial.write(trial_path)
    baseline_result.write(baseline_result_path)
    candidate_result.write(candidate_result_path)
    decision.write(decision_path)

    if packaged:
        manifest_path = root / "manifest.json"
        manifest = load_contract(manifest_path, DomainPackageManifest)
        manifest_payload = copy.deepcopy(manifest.payload)
        manifest_payload["domain_specification_ref"] = specification.ref()
        manifest_payload["workload_ref"] = workload.ref()
        manifest_payload["selection_decision_ref"] = decision.ref()
        manifest_payload["measured_result_ref"] = candidate_result.ref()
        for entry in manifest_payload["artifacts"]:
            artifact_path = root.joinpath(*entry["path"].split("/"))
            entry["content_digest"] = digest_bytes(artifact_path.read_bytes())
        DomainPackageManifest(manifest.artifact_id, manifest.version, manifest_payload).write(manifest_path)


class ReferenceFlowTests(unittest.TestCase):
    def test_repeated_execution_and_packages_are_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture_a, fixture_b = root / "fixture-a", root / "fixture-b"
            run_a, run_b = root / "run-a", root / "run-b"
            package_a, package_b = root / "package-a", root / "package-b"
            prepare_fixture(fixture_a)
            prepare_fixture(fixture_b)
            run_trial(fixture_a / "trial.json", run_a)
            run_trial(fixture_b / "trial.json", run_b)
            build_package(run_a, package_a)
            build_package(run_b, package_b)
            self.assertEqual(tree_bytes(fixture_a), tree_bytes(fixture_b))
            self.assertEqual(tree_bytes(run_a), tree_bytes(run_b))
            self.assertEqual(tree_bytes(package_a), tree_bytes(package_b))

    def test_fixture_makes_no_network_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), mock.patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
                prepare_fixture(root / "fixture")
                run_trial(root / "fixture/trial.json", root / "run")
                build_package(root / "run", root / "package")
                verify_package(root / "package")

    def test_package_rejects_corruption_missing_and_unexpected_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_fixture(root / "fixture")
            run_trial(root / "fixture/trial.json", root / "run")
            build_package(root / "run", root / "package")
            target = root / "package/evaluation/results/qualification-candidate-result.json"
            target.write_bytes(target.read_bytes() + b" ")
            with self.assertRaisesRegex(ValidationError, "digest mismatch"):
                verify_package(root / "package")

    def test_package_build_rejects_missing_decision_result_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_fixture(root / "fixture")
            run_trial(root / "fixture/trial.json", root / "run")
            (root / "run/results/qualification-baseline-result.json").unlink()
            with self.assertRaisesRegex(ValidationError, "referenced evidence is missing"):
                build_package(root / "run", root / "package")

    def test_package_build_rejects_missing_eligible_result_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_fixture(root / "fixture")
            run_trial(root / "fixture/trial.json", root / "run")
            (root / "run/results/qualification-candidate-result.json").unlink()
            with self.assertRaisesRegex(ValidationError, "referenced evidence is missing"):
                build_package(root / "run", root / "package")

    def test_package_build_recomputes_declared_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_fixture(root / "fixture")
            run_trial(root / "fixture/trial.json", root / "run")
            decision = load_contract(root / "run/decision.json", SelectionDecision)
            baseline = load_contract(root / "run/results/qualification-baseline-result.json", EvaluationResult)
            payload = dict(decision.payload)
            payload["eligible_result_refs"] = [baseline.ref(), *decision.payload["eligible_result_refs"]]
            falsified = SelectionDecision(decision.artifact_id, decision.version, payload)
            falsified.write(root / "run/decision.json")
            with self.assertRaisesRegex(ValidationError, "selection decision semantics"):
                build_package(root / "run", root / "package")

    def test_package_verify_rejects_unencapsulated_baseline_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_fixture(root / "fixture")
            run_trial(root / "fixture/trial.json", root / "run")
            build_package(root / "run", root / "package")
            baseline = root / "package/evaluation/results/qualification-baseline-result.json"
            baseline.unlink()
            with self.assertRaisesRegex(ValidationError, "missing declared files"):
                verify_package(root / "package")

    def test_build_rejects_rebuilt_graph_with_nonexistent_trial_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_fixture(root / "fixture")
            run_trial(root / "fixture/trial.json", root / "run")
            rewrite_evidence_graph(root / "run", packaged=False, nonexistent_trial_requirement=True)
            with self.assertRaisesRegex(ValidationError, "trial.requirement_set_ref"):
                build_package(root / "run", root / "package")

    def test_verify_rejects_rebuilt_package_with_nonexistent_trial_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_fixture(root / "fixture")
            run_trial(root / "fixture/trial.json", root / "run")
            build_package(root / "run", root / "package")
            rewrite_evidence_graph(root / "package", packaged=True, nonexistent_trial_requirement=True)
            with self.assertRaisesRegex(ValidationError, "trial.requirement_set_ref"):
                verify_package(root / "package")

    def test_build_rejects_rebuilt_graph_with_wrong_source_locator(self) -> None:
        for field in ("input", "expected"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                prepare_fixture(root / "fixture")
                run_trial(root / "fixture/trial.json", root / "run")
                rewrite_evidence_graph(root / "run", packaged=False, wrong_locator_field=field)
                with self.assertRaisesRegex(ValidationError, "source locator mismatch"):
                    build_package(root / "run", root / "package")

    def test_verify_rejects_rebuilt_package_with_wrong_source_locator(self) -> None:
        for field in ("input", "expected"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                prepare_fixture(root / "fixture")
                run_trial(root / "fixture/trial.json", root / "run")
                build_package(root / "run", root / "package")
                rewrite_evidence_graph(root / "package", packaged=True, wrong_locator_field=field)
                with self.assertRaisesRegex(ValidationError, "source locator mismatch"):
                    verify_package(root / "package")

    def test_trial_validation_rejects_substituted_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_fixture(root / "fixture")
            candidate = root / "fixture/candidate.json"
            candidate.write_bytes(candidate.read_bytes().replace(b"Deterministic candidate intervention", b"Substituted candidate intervention"))
            with self.assertRaisesRegex(ValidationError, "digest mismatch"):
                validate_trial(root / "fixture/trial.json")

    def test_cli_success_and_failure_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cli.main(["fixture", "prepare", "--output", str(root / "fixture")]), 0)
                self.assertEqual(cli.main(["spec", "validate", str(root / "fixture/specification.json")]), 0)
                self.assertEqual(cli.main(["trial", "validate", str(root / "fixture/trial.json")]), 0)
                self.assertEqual(cli.main(["trial", "run", "--trial", str(root / "fixture/trial.json"), "--output", str(root / "run")]), 0)
                self.assertEqual(cli.main(["package", "build", "--run", str(root / "run"), "--output", str(root / "package")]), 0)
                self.assertEqual(cli.main(["package", "verify", str(root / "package")]), 0)
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(cli.main(["package", "verify", str(root / "missing")]), 2)
            self.assertIn("error", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
