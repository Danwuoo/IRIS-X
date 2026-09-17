from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

import support  # noqa: F401

from irisx.canonical import canonical_bytes
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
from irisx.errors import ValidationError
from irisx.fixture import prepare_fixture, run_trial
from irisx.package import build_package


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = self.root / "fixture"
        self.run = self.root / "run"
        self.package = self.root / "package"
        prepare_fixture(self.fixture)
        run_trial(self.fixture / "trial.json", self.run)
        build_package(self.run, self.package)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_all_eight_contract_families_load(self) -> None:
        expected = {
            "specification.json": DomainSpecification,
            "workload.json": WorkloadDefinition,
            "requirements.json": RequirementSet,
            "candidate.json": CandidateConfiguration,
            "trial.json": EngineeringTrial,
            "results/qualification-candidate-result.json": EvaluationResult,
            "decision.json": SelectionDecision,
        }
        for relative, contract_type in expected.items():
            with self.subTest(relative=relative):
                contract = load_contract(self.run / relative, contract_type)
                self.assertIsInstance(contract, contract_type)
        self.assertIsInstance(load_contract(self.package / "manifest.json", DomainPackageManifest), DomainPackageManifest)

    def test_digest_and_canonical_serialization_are_stable(self) -> None:
        first = load_contract(self.fixture / "specification.json", DomainSpecification)
        second = DomainSpecification.from_dict(copy.deepcopy(first.to_dict()))
        self.assertEqual(first.content_digest, second.content_digest)
        self.assertEqual(canonical_bytes(first.to_dict()), canonical_bytes(second.to_dict()))

    def test_digest_mutation_fails_closed(self) -> None:
        value = load_contract(self.fixture / "specification.json", DomainSpecification).to_dict()
        value["payload"]["description"] = "substituted"
        with self.assertRaisesRegex(ValidationError, "digest mismatch"):
            DomainSpecification.from_dict(value)

    def test_invalid_instances_have_field_paths(self) -> None:
        requirements = load_contract(self.fixture / "requirements.json", RequirementSet)
        value = requirements.to_dict()
        value["payload"]["requirements"][0]["comparator"] = "approximately"
        value.pop("content_digest")
        with self.assertRaisesRegex(ValidationError, r"requirements\[0\]\.comparator"):
            RequirementSet(
                value["artifact_id"],
                value["version"],
                value["payload"],
            )

    def test_unknown_is_distinct_from_observed_zero(self) -> None:
        result = load_contract(self.run / "results/qualification-candidate-result.json", EvaluationResult)
        resources = result.payload["resource_use"]
        self.assertEqual(resources["monetary_cost"], {"state": "observed", "value": 0, "unit": "usd"})
        self.assertEqual(resources["gpu_seconds"], {"state": "unknown", "value": None, "unit": "seconds"})
        invalid = copy.deepcopy(result.payload)
        invalid["resource_use"]["gpu_seconds"]["value"] = 0
        with self.assertRaisesRegex(ValidationError, "must be null"):
            EvaluationResult("invalid-result", "1.0.0", invalid)

    def test_unexpected_contract_fields_fail_closed(self) -> None:
        value = load_contract(self.fixture / "candidate.json", CandidateConfiguration).to_dict()
        value["surprise"] = True
        with self.assertRaisesRegex(ValidationError, "unexpected fields"):
            CandidateConfiguration.from_dict(value)

    def test_source_locator_rejects_windows_traversal(self) -> None:
        workload = load_contract(self.fixture / "workload.json", WorkloadDefinition)
        payload = copy.deepcopy(workload.payload)
        payload["cases"][0]["input_ref"]["locator"] = "..\\outside.json"
        with self.assertRaisesRegex(ValidationError, "canonical relative POSIX logical path"):
            WorkloadDefinition("invalid-workload", "1.0.0", payload)

    def test_manifest_path_rejects_windows_traversal(self) -> None:
        manifest = load_contract(self.package / "manifest.json", DomainPackageManifest)
        payload = copy.deepcopy(manifest.payload)
        payload["artifacts"][0]["path"] = "..\\outside.json"
        with self.assertRaisesRegex(ValidationError, "canonical relative POSIX logical path"):
            DomainPackageManifest("invalid-package", "1.0.0", payload)

    def test_decision_eligible_refs_must_be_considered(self) -> None:
        decision = load_contract(self.run / "decision.json", SelectionDecision)
        payload = copy.deepcopy(decision.payload)
        outside = copy.deepcopy(payload["eligible_result_refs"][0])
        outside["content_digest"] = "sha256:" + "0" * 64
        payload["eligible_result_refs"] = [outside]
        with self.assertRaisesRegex(ValidationError, "must be a subset"):
            SelectionDecision("invalid-selection", "1.0.0", payload)


if __name__ == "__main__":
    unittest.main()
