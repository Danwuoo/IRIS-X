"""Targeted H-V1b checks for reproducibility and verifier separation."""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = ROOT / "experiments" / "exp-2026-08-30-docops-evidence-binding" / "scripts" / "run_experiment.py"
CHALLENGE_PATH = ROOT / "experiments" / "exp-2026-08-30-docops-evidence-binding" / "inputs" / "challenges.json"


def load_runner():
    spec = importlib.util.spec_from_file_location("h_v1b_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load H-V1b runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EvidenceBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()
        cls.challenge = json.loads(CHALLENGE_PATH.read_text(encoding="utf-8"))

    def test_evidence_verifier_interface_excludes_labels_and_outcomes(self) -> None:
        parameters = tuple(inspect.signature(self.runner.evidence_binding_decision).parameters)
        self.assertEqual(parameters, ("fixture", "required_inputs", "supplied_evidence"))

    def test_all_outputs_are_semantically_correct_successes(self) -> None:
        for case in self.challenge["cases"]:
            fixture = self.runner.resolve_repo_path(case["fixture_path"], "fixture")
            task = self.runner.load_json(fixture / "task.json")
            requirements = self.runner.declared_requirements(task)
            snapshot = self.runner.actual_input_snapshot(fixture, requirements)
            outcome, _reasons = self.runner.adjudicate_actual_outcome(
                fixture,
                case["expected_path"],
                case["producer_output_json"],
                snapshot,
                snapshot,
            )
            semantic, _reason = self.runner.semantic_verifier_decision(
                fixture,
                case["expected_path"],
                case["producer_output_json"],
            )
            self.assertEqual(outcome, "success")
            self.assertEqual(semantic, "accept")

    def test_complete_passes_and_every_invalid_variant_fails(self) -> None:
        observed: dict[str, set[str]] = {}
        for case in self.challenge["cases"]:
            fixture = self.runner.resolve_repo_path(case["fixture_path"], "fixture")
            task = self.runner.load_json(fixture / "task.json")
            decision, _reasons, _observations = self.runner.evidence_binding_decision(
                fixture,
                self.runner.declared_requirements(task),
                case["supplied_evidence"],
            )
            observed.setdefault(case["challenge_metadata"]["variant_id"], set()).add(decision)
        self.assertEqual(observed["complete-correct"], {"sufficient"})
        for variant in self.runner.VARIANTS[1:]:
            self.assertTrue(observed[variant].isdisjoint({"sufficient"}), (variant, observed[variant]))

    def test_real_bytes_are_recomputed_not_looked_up_by_case_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            target = fixture / "input.txt"
            target.write_bytes(b"original")
            requirements = [{"path": "input.txt", "role": "source"}]
            evidence = [{
                "path": "input.txt",
                "role": "source",
                "sha256": self.runner.sha256_bytes(b"original"),
                "bytes": len(b"original"),
            }]
            first, _reasons, observations = self.runner.evidence_binding_decision(
                fixture, requirements, evidence
            )
            self.assertEqual(first, "sufficient")
            self.assertEqual(observations[0]["actual_sha256"], evidence[0]["sha256"])
            target.write_bytes(b"changed")
            second, reasons, observations = self.runner.evidence_binding_decision(
                fixture, requirements, evidence
            )
            self.assertEqual(second, "invalid_binding")
            self.assertIn("hash_mismatch", reasons)
            self.assertNotEqual(observations[0]["actual_sha256"], evidence[0]["sha256"])

    def test_evidence_status_cannot_change_actual_outcome_adjudication(self) -> None:
        case = next(
            item for item in self.challenge["cases"]
            if item["challenge_metadata"]["variant_id"] == "wrong-hash"
        )
        fixture = self.runner.resolve_repo_path(case["fixture_path"], "fixture")
        task = self.runner.load_json(fixture / "task.json")
        requirements = self.runner.declared_requirements(task)
        snapshot = self.runner.actual_input_snapshot(fixture, requirements)
        with patch.object(
            self.runner,
            "evidence_binding_decision",
            side_effect=AssertionError("actual adjudicator must not call evidence verifier"),
        ):
            outcome, _reasons = self.runner.adjudicate_actual_outcome(
                fixture,
                case["expected_path"],
                case["producer_output_json"],
                snapshot,
                snapshot,
            )
        self.assertEqual(outcome, "success")

    def test_frozen_variant_and_fallback_counts(self) -> None:
        self.assertEqual(self.challenge["case_count"], 96)
        self.assertEqual(self.challenge["variant_order"], list(self.runner.VARIANTS))
        self.assertEqual(
            self.challenge["crossed_evidence_applicability"]["counts"],
            {"multi_input_swap": 5, "single_input_next_task": 7},
        )


if __name__ == "__main__":
    unittest.main()
