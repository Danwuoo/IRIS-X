from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
ROOT = EXPERIMENT_ROOT.parents[1]
SCRIPTS = EXPERIMENT_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
DEFINITION = json.loads(
    (EXPERIMENT_ROOT / "inputs" / "experiment-definition.json").read_text(encoding="utf-8")
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("hsr1a_runner", SCRIPTS / "run_experiment.py")
oracle = load_module("hsr1a_oracle", SCRIPTS / "state_oracle.py")


class StatefulStabilityDefinitionTests(unittest.TestCase):
    def test_horizon_and_arms_are_frozen(self) -> None:
        self.assertEqual(DEFINITION["cycles"], 10)
        self.assertEqual(DEFINITION["expected_total_cycles"], 120)
        self.assertEqual(len(DEFINITION["fixture_order"]), 6)
        self.assertEqual(
            DEFINITION["arms"],
            ["fresh-workspace-cycle-v0", "persistent-workspace-cycle-v0"],
        )

    def test_frozen_action_and_changed_hashes_reconstruct(self) -> None:
        for row in DEFINITION["fixtures"]:
            action = runner.action_for(row["fixture_id"])
            source = runner.fixture_path(row["fixture_id"]) / row["source_path"]
            changed = runner.candidate_bytes(source.read_bytes(), action)
            self.assertEqual(runner.sha256_bytes(changed), row["expected_changed_sha256"])
            self.assertEqual(len(changed), row["expected_changed_bytes"])
            self.assertEqual(runner.sha256_bytes(runner.canonical_json_bytes(action)), row["action_sha256"])

    def test_oracle_detects_intentional_residual_artifact(self) -> None:
        result = oracle.residual_artifact_self_test()
        self.assertTrue(result["passed"])
        self.assertEqual(result["comparison"]["residual_paths"], ["residual.tmp"])

    def test_apply_rollback_restores_exact_baseline_for_all_fixtures(self) -> None:
        with tempfile.TemporaryDirectory(prefix="irisx-hsr1a-test-") as temporary:
            root = Path(temporary)
            for row in DEFINITION["fixtures"]:
                workspace = root / row["fixture_id"]
                workspace.mkdir()
                shutil.copytree(runner.fixture_path(row["fixture_id"]) / "inputs", workspace / "inputs")
                baseline = oracle.state_manifest(workspace)
                action = runner.action_for(row["fixture_id"])
                paths = runner.apply_action(workspace, row, action)
                changed = oracle.verify_changed_state(
                    workspace,
                    baseline,
                    row["source_path"],
                    row["expected_changed_sha256"],
                    row["expected_changed_bytes"],
                    paths["backup_path"],
                    paths["metadata_path"],
                    row["action_sha256"],
                )
                self.assertTrue(changed["valid"], (row["fixture_id"], changed))
                runner.rollback_action(workspace, paths["metadata_path"])
                restored = oracle.compare_exact(baseline, oracle.state_manifest(workspace))
                self.assertTrue(restored["exact"], (row["fixture_id"], restored))

    def test_oracle_rejects_residual_after_otherwise_successful_rollback(self) -> None:
        row = DEFINITION["fixtures"][0]
        with tempfile.TemporaryDirectory(prefix="irisx-hsr1a-residual-") as temporary:
            workspace = Path(temporary) / "workspace"
            workspace.mkdir()
            shutil.copytree(runner.fixture_path(row["fixture_id"]) / "inputs", workspace / "inputs")
            baseline = oracle.state_manifest(workspace)
            paths = runner.apply_action(workspace, row, runner.action_for(row["fixture_id"]))
            runner.rollback_action(workspace, paths["metadata_path"])
            (workspace / "residual.tmp").write_bytes(b"injected\n")
            restored = oracle.compare_exact(baseline, oracle.state_manifest(workspace))
            self.assertFalse(restored["exact"])
            self.assertEqual(restored["residual_paths"], ["residual.tmp"])


if __name__ == "__main__":
    unittest.main()
