from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

import support  # noqa: F401

from irisx.contracts import CandidateConfiguration, EngineeringTrial, EvaluationResult, RequirementSet, load_contract
from irisx.engine import requirement_verdicts, select_configuration, satisfies_hard_requirements
from irisx.errors import ValidationError
from irisx.fixture import prepare_fixture, run_trial


class SelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        fixture = root / "fixture"
        self.run = root / "run"
        prepare_fixture(fixture)
        run_trial(fixture / "trial.json", self.run)
        self.trial = load_contract(self.run / "trial.json", EngineeringTrial)
        self.requirements = load_contract(self.run / "requirements.json", RequirementSet)
        self.baseline_config = load_contract(self.run / "baseline.json", CandidateConfiguration)
        self.candidate_config = load_contract(self.run / "candidate.json", CandidateConfiguration)
        self.baseline = load_contract(self.run / "results/qualification-baseline-result.json", EvaluationResult)
        self.candidate = load_contract(self.run / "results/qualification-candidate-result.json", EvaluationResult)
        self.configurations = {
            self.baseline_config.content_digest: self.baseline_config,
            self.candidate_config.content_digest: self.candidate_config,
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _result(self, original: EvaluationResult, artifact_id: str, **metrics: float) -> EvaluationResult:
        payload = copy.deepcopy(original.payload)
        for name, value in metrics.items():
            payload["metrics"][name] = {"state": "observed", "value": value, "unit": payload["metrics"][name]["unit"]}
        return EvaluationResult(artifact_id, "1.0.0", payload)

    def test_hard_and_soft_requirements_are_distinct(self) -> None:
        verdicts = requirement_verdicts(self.candidate, self.requirements)
        latency = next(item for item in verdicts if item["requirement_id"] == "latency-objective")
        self.assertFalse(latency["hard"])
        self.assertTrue(satisfies_hard_requirements(self.candidate, self.requirements))
        changed = self._result(self.candidate, "slow-candidate-result", latency_ms=99)
        self.assertTrue(satisfies_hard_requirements(changed, self.requirements))

    def test_missing_hard_evidence_is_not_zero_or_success(self) -> None:
        payload = copy.deepcopy(self.candidate.payload)
        payload["metrics"]["critical_failures"] = {"state": "unknown", "value": None, "unit": "count"}
        result = EvaluationResult("unknown-evidence-result", "1.0.0", payload)
        self.assertFalse(satisfies_hard_requirements(result, self.requirements))

    def test_promote_outcome(self) -> None:
        workload = load_contract(self.run / "workload.json")
        decision = select_configuration(self.trial, workload, self.requirements, self.baseline, [self.candidate], self.configurations)
        self.assertEqual(decision.payload["outcome"], "promote")
        self.assertEqual(decision.payload["selected_configuration_ref"], self.candidate_config.ref())

    def test_no_promotion_outcome(self) -> None:
        payload = copy.deepcopy(self.candidate.payload)
        payload["configuration_ref"] = self.baseline_config.ref()
        payload["metrics"]["latency_ms"]["value"] = 8
        eligible_baseline = EvaluationResult("eligible-baseline-result", "1.0.0", payload)
        workload = load_contract(self.run / "workload.json")
        decision = select_configuration(self.trial, workload, self.requirements, eligible_baseline, [self.candidate], self.configurations)
        self.assertEqual(decision.payload["outcome"], "no_promotion")
        self.assertIsNone(decision.payload["selected_result_ref"])

    def test_infeasible_outcome(self) -> None:
        payload = copy.deepcopy(self.baseline.payload)
        payload["configuration_ref"] = self.candidate_config.ref()
        payload["metrics"]["latency_ms"]["value"] = 10
        failed_candidate = EvaluationResult("failed-candidate-result", "1.0.0", payload)
        workload = load_contract(self.run / "workload.json")
        decision = select_configuration(self.trial, workload, self.requirements, self.baseline, [failed_candidate], self.configurations)
        self.assertEqual(decision.payload["outcome"], "infeasible")

    def test_cross_run_or_stale_binding_fails(self) -> None:
        payload = copy.deepcopy(self.candidate.payload)
        payload["workload_ref"] = copy.deepcopy(payload["workload_ref"])
        payload["workload_ref"]["content_digest"] = "sha256:" + "0" * 64
        stale = EvaluationResult("stale-result", "1.0.0", payload)
        with self.assertRaisesRegex(ValidationError, "not comparable"):
            workload = load_contract(self.run / "workload.json")
            select_configuration(self.trial, workload, self.requirements, self.baseline, [stale], self.configurations)

    def test_missing_case_evidence_fails_closed(self) -> None:
        payload = copy.deepcopy(self.candidate.payload)
        payload["cases"] = payload["cases"][:-1]
        incomplete = EvaluationResult("incomplete-result", "1.0.0", payload)
        workload = load_contract(self.run / "workload.json")
        with self.assertRaisesRegex(ValidationError, "cases do not exactly match"):
            select_configuration(self.trial, workload, self.requirements, self.baseline, [incomplete], self.configurations)


if __name__ == "__main__":
    unittest.main()
