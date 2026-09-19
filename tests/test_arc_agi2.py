from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

import support  # noqa: F401
from arc_support import make_arc_source, observations, prediction_document

from irisx.arc_agi2 import (
    MODEL_REPOSITORY,
    MODEL_REVISION,
    PUBLIC_EVALUATION_COUNT,
    p2_acceptance,
    prepare_trial,
    score_predictions,
    validate_predictions,
    validate_source,
    validate_trial_bundle,
)
from irisx.artifacts import load_artifact
from irisx.canonical import read_json
from irisx.contracts import CandidateConfiguration, RequirementSet, WorkloadDefinition, load_contract
from irisx.errors import ValidationError


class ArcTrialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.profile = make_arc_source(self.source, evaluation_count=PUBLIC_EVALUATION_COUNT)
        self.trial = self.root / "trial"
        prepare_trial(self.source, self.trial, profile=self.profile)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_complete_120_case_contract_graph_and_frozen_model_binding(self) -> None:
        contract = validate_trial_bundle(self.trial)
        self.assertEqual(contract.artifact_id, "arc-agi-2-trial-001")
        workload = load_contract(self.trial / "workload.json", WorkloadDefinition)
        self.assertEqual(len(workload.payload["cases"]), 120)
        self.assertTrue(workload.payload["frozen"])
        self.assertEqual({case["segment"] for case in workload.payload["cases"]}, {"public_eval"})
        model = load_artifact(self.trial / "model.json", kind="irisx/model-descriptor")
        self.assertEqual(model["payload"]["repository"], MODEL_REPOSITORY)
        self.assertEqual(model["payload"]["revision"], MODEL_REVISION)
        self.assertTrue(model["payload"]["weights_frozen"])
        self.assertEqual(model["payload"]["package_state"], "unbound")

    def test_solver_view_excludes_test_outputs_and_truth_is_local_only(self) -> None:
        solver = load_artifact(self.trial / "solver-cases.json", kind="irisx/arc-solver-cases")
        truth = load_artifact(self.trial / "evaluator-truth.json", kind="irisx/arc-evaluator-truth")
        for case in solver["payload"]["cases"]:
            self.assertTrue(all(set(pair) == {"input"} for pair in case["test"]))
        self.assertTrue(all("expected" in case for case in truth["payload"]["cases"]))
        specialization = load_artifact(self.trial / "specialization.json", kind="irisx/specialization-provenance")
        self.assertFalse(specialization["payload"]["evaluation_material_used"])
        self.assertFalse(specialization["payload"]["result_feedback_used"])
        self.assertEqual(specialization["payload"]["training_task_count"], self.profile.training_count)

    def test_source_revalidation_rejects_changed_bytes_and_wrong_split_count(self) -> None:
        target = self.source / "upstream/data/evaluation/e0000.json"
        original = target.read_bytes()
        target.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValidationError, "digest mismatch"):
            validate_source(self.source, profile=self.profile)
        target.write_bytes(original)
        (self.source / "upstream/data/evaluation/e0001.json").unlink()
        with self.assertRaisesRegex(ValidationError, "provenance|task counts"):
            validate_source(self.source, profile=self.profile)

    def test_source_revalidation_rejects_stale_official_split_index(self) -> None:
        index = self.source / "upstream/data/evaluation.txt"
        index.write_text(index.read_text(encoding="utf-8").replace("e0000", "unknown"), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "provenance|does not exactly enumerate"):
            validate_source(self.source, profile=self.profile)

    def test_pass_at_two_accepts_first_or_second_attempt_and_rejects_neither(self) -> None:
        baseline_config = load_contract(self.trial / "baseline.json", CandidateConfiguration)
        baseline = prediction_document(self.trial, "baseline", 0)
        first_case = baseline["cases"][0]
        expected = [[3]]
        first_case["tests"][0]["attempts"][0]["grid"] = expected
        result = score_predictions(self.trial, baseline, baseline_config, observations(), result_id="first-success")
        self.assertTrue(result.payload["cases"][0]["passed"])

        second = prediction_document(self.trial, "baseline", 0)
        second["cases"][0]["tests"][0]["attempts"][1]["grid"] = expected
        result = score_predictions(self.trial, second, baseline_config, observations(), result_id="second-success")
        self.assertTrue(result.payload["cases"][0]["passed"])

        neither = prediction_document(self.trial, "baseline", 0)
        result = score_predictions(self.trial, neither, baseline_config, observations(), result_id="neither-success")
        self.assertFalse(result.payload["cases"][0]["passed"])

    def test_pass_at_two_rejects_wrong_dimensions_malformed_grids_and_extra_attempts(self) -> None:
        configuration = load_contract(self.trial / "baseline.json", CandidateConfiguration)
        solver = load_artifact(self.trial / "solver-cases.json", kind="irisx/arc-solver-cases")
        base = prediction_document(self.trial, "baseline", 120)
        wrong_dimensions = copy.deepcopy(base)
        wrong_dimensions["cases"][0]["tests"][0]["attempts"][0]["grid"] = [[1], [1, 2]]
        with self.assertRaisesRegex(ValidationError, "rectangular"):
            validate_predictions(wrong_dimensions, solver, configuration.ref())
        malformed = copy.deepcopy(base)
        malformed["cases"][0]["tests"][0]["attempts"][0]["grid"] = [[10]]
        with self.assertRaisesRegex(ValidationError, "0 through 9"):
            validate_predictions(malformed, solver, configuration.ref())
        extra = copy.deepcopy(base)
        extra["cases"][0]["tests"][0]["attempts"].append(copy.deepcopy(extra["cases"][0]["tests"][0]["attempts"][0]))
        with self.assertRaisesRegex(ValidationError, "exactly two"):
            validate_predictions(extra, solver, configuration.ref())

    def test_only_prompts_programs_may_differ(self) -> None:
        candidate_path = self.trial / "candidate.json"
        candidate = load_contract(candidate_path, CandidateConfiguration)
        payload = copy.deepcopy(candidate.payload)
        payload["components"]["workflow_control"] = payload["components"]["prompts_programs"]
        CandidateConfiguration(candidate.artifact_id, candidate.version, payload).write(candidate_path)
        with self.assertRaisesRegex(ValidationError, "specialized candidate|workflow_control components differ"):
            validate_trial_bundle(self.trial)

    def test_p2_acceptance_distinguishes_four_and_five_point_improvements(self) -> None:
        baseline_config = load_contract(self.trial / "baseline.json", CandidateConfiguration)
        candidate_config = load_contract(self.trial / "candidate.json", CandidateConfiguration)
        workload = load_contract(self.trial / "workload.json", WorkloadDefinition)
        requirements = load_contract(self.trial / "requirements.json", RequirementSet)
        baseline = score_predictions(
            self.trial,
            prediction_document(self.trial, "baseline", 90),
            baseline_config,
            observations(),
            result_id="baseline-result",
        )
        plus_four = score_predictions(
            self.trial,
            prediction_document(self.trial, "candidate", 95),
            candidate_config,
            observations(),
            result_id="plus-four-result",
        )
        self.assertFalse(p2_acceptance(baseline, plus_four, requirements, workload)["payload"]["accepted"])
        plus_five = score_predictions(
            self.trial,
            prediction_document(self.trial, "candidate", 96),
            candidate_config,
            observations(),
            result_id="plus-five-result",
        )
        self.assertTrue(p2_acceptance(baseline, plus_five, requirements, workload)["payload"]["accepted"])


if __name__ == "__main__":
    unittest.main()
