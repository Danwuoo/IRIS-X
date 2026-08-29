"""Targeted H-V1a checks for challenge semantics and verifier separation."""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = ROOT / "experiments" / "exp-2026-08-30-docops-acceptance-verification" / "scripts" / "run_experiment.py"
CHALLENGE_PATH = ROOT / "experiments" / "exp-2026-08-30-docops-acceptance-verification" / "inputs" / "challenges.json"


def load_runner():
    spec = importlib.util.spec_from_file_location("h_v1a_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load H-V1a runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VerifierSeparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()
        cls.challenge = json.loads(CHALLENGE_PATH.read_text(encoding="utf-8"))

    def test_verifier_interface_excludes_labels_and_actual_outcome(self) -> None:
        parameters = tuple(inspect.signature(self.runner.independent_verifier_decision).parameters)
        self.assertEqual(parameters, ("fixture", "expected_relative_path", "producer_output_json"))

    def test_verifier_does_not_call_actual_outcome_adjudicator(self) -> None:
        canonical = next(
            case for case in self.challenge["cases"]
            if case["challenge_metadata"]["variant_id"] == "canonical-valid"
        )
        fixture = self.runner.resolve_repo_path(canonical["fixture_path"], "fixture")
        with patch.object(self.runner, "adjudicate_actual_outcome", side_effect=AssertionError("circular call")):
            decision, _reason = self.runner.independent_verifier_decision(
                fixture, canonical["expected_path"], canonical["producer_output_json"]
            )
        self.assertEqual(decision, "accept")

    def test_valid_variants_accept_and_invalid_variants_reject(self) -> None:
        observed: dict[str, set[str]] = {}
        for case in self.challenge["cases"]:
            fixture = self.runner.resolve_repo_path(case["fixture_path"], "fixture")
            decision, _reason = self.runner.independent_verifier_decision(
                fixture, case["expected_path"], case["producer_output_json"]
            )
            observed.setdefault(case["challenge_metadata"]["variant_id"], set()).add(decision)
        self.assertEqual(observed["canonical-valid"], {"accept"})
        self.assertEqual(observed["semantic-equivalent-valid"], {"accept"})
        for variant in ("omission-invalid", "fabrication-invalid", "corruption-invalid"):
            self.assertEqual(observed[variant], {"reject"})

    def test_frozen_relation_counts_are_24_equal_and_36_unequal(self) -> None:
        summary = self.challenge["construction_validation"]
        self.assertEqual(summary["semantic_equal_case_count"], 24)
        self.assertEqual(summary["semantic_unequal_case_count"], 36)
        self.assertTrue(summary["all_relations_verified_before_freeze"])


if __name__ == "__main__":
    unittest.main()
