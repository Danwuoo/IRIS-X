"""Targeted H-O1a checks for frozen coverage and behavior invariance."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = ROOT / "experiments" / "exp-2026-08-30-docops-profile-instrumentation" / "scripts" / "run_experiment.py"
PROFILE_CONTRACT_PATH = (
    ROOT / "experiments" / "exp-2026-08-30-docops-profile-instrumentation" / "inputs" / "profile-contract.json"
)
MANIFEST_PATH = ROOT / "experiments" / "exp-2026-08-28-docops-readonly-baseline" / "inputs" / "task-manifest.json"
CONFIGURATIONS_PATH = (
    ROOT / "experiments" / "exp-2026-08-28-docops-readonly-baseline" / "inputs" / "configurations.json"
)


def load_runner():
    spec = importlib.util.spec_from_file_location("h_o1a_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load H-O1a runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ProfileInvarianceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()
        cls.baseline = cls.runner.load_baseline_runner()
        profile_contract = json.loads(PROFILE_CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.required_fields = cls.runner.validate_profile_contract(profile_contract)
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        configurations = json.loads(CONFIGURATIONS_PATH.read_text(encoding="utf-8"))
        tasks, configs = cls.baseline.validate_definitions(manifest, configurations)
        cls.row = {**tasks[0], "task_order": 1}
        cls.config = next(config for config in configs if config["id"] == "structured-readonly-v0")

    def test_profile_contract_is_frozen_and_task_relevant(self) -> None:
        self.assertEqual(len(self.required_fields), 17)
        self.assertIn("stages.invocation.wall_ms", self.required_fields)
        self.assertIn("profiler.error", self.required_fields)
        self.assertNotIn("model.tokens", self.required_fields)

    def test_instrumentation_preserves_output_outcome_and_terminal_status(self) -> None:
        off, off_profile = self.runner.execute_episode(
            self.baseline,
            run_id="unit-test",
            row=self.row,
            config=self.config,
            repetition=1,
            arm="instrumentation-off-v0",
            required_fields=self.required_fields,
        )
        on, on_profile = self.runner.execute_episode(
            self.baseline,
            run_id="unit-test",
            row=self.row,
            config=self.config,
            repetition=1,
            arm="instrumentation-on-v0",
            required_fields=self.required_fields,
        )
        self.assertIsNone(off_profile)
        self.assertIsNotNone(on_profile)
        self.assertEqual(off["produced"], on["produced"])
        self.assertEqual(off["actual_outcome"], on["actual_outcome"])
        self.assertEqual(off["terminal_status"], on["terminal_status"])
        self.assertEqual(off["input_snapshot_after"], on["input_snapshot_after"])
        self.assertEqual(off["profile_coverage"]["present_field_count"], 0)
        self.assertEqual(on["profile_coverage"]["present_field_count"], len(self.required_fields))
        self.assertEqual(on["resources"]["instrumentation_event_count"], 5)


if __name__ == "__main__":
    unittest.main()
