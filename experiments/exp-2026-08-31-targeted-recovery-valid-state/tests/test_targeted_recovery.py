from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = EXPERIMENT_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import final_state_oracle  # noqa: E402
import recovery_common  # noqa: E402


DEFINITION = json.loads(
    (EXPERIMENT_ROOT / "inputs" / "experiment-definition.json").read_text(encoding="utf-8")
)


class TargetedRecoveryDefinitionTests(unittest.TestCase):
    def test_horizon_and_arms_are_frozen(self) -> None:
        self.assertEqual(DEFINITION["repetitions"], 3)
        self.assertEqual(DEFINITION["expected_total_episodes"], 30)
        self.assertEqual(len(DEFINITION["fixtures"]), 5)
        self.assertEqual(DEFINITION["arms"], ["detect-only-v0", "targeted-recovery-v0"])

    def test_recovery_specs_exclude_oracle_and_success_fields(self) -> None:
        for row in DEFINITION["fixtures"]:
            self.assertFalse(
                [key for key in row["recovery_spec"] if "expected" in key or "oracle" in key or "success" in key]
            )

    def test_frozen_failure_and_final_states_reconstruct(self) -> None:
        with tempfile.TemporaryDirectory(prefix="irisx-hrcv1a-test-") as temporary:
            root = Path(temporary)
            for row in DEFINITION["fixtures"]:
                workspace = root / row["fixture_id"]
                built = recovery_common.build_failure_workspace(
                    workspace, row["fixture_id"], row["failure_kind"]
                )
                self.assertEqual(built["manifest"]["manifest_sha256"], row["initial_failure_manifest_sha256"])
                detection = recovery_common.detect_failure(
                    workspace, row["failure_kind"], row["recovery_spec"]
                )
                self.assertTrue(detection["detected"])
                recovery_common.execute_recovery(
                    workspace, row["recovery_policy"], row["recovery_spec"]
                )
                final = final_state_oracle.evaluate(workspace, row["oracle_spec"])
                self.assertTrue(final["final_state_valid"], (row["fixture_id"], final))
                self.assertFalse(final["new_side_effect_violation"])

    def test_paired_failure_states_are_byte_identical(self) -> None:
        row = DEFINITION["fixtures"][0]
        with tempfile.TemporaryDirectory(prefix="irisx-hrcv1a-pair-") as temporary:
            root = Path(temporary)
            first = recovery_common.build_failure_workspace(
                root / "first", row["fixture_id"], row["failure_kind"]
            )
            second = recovery_common.build_failure_workspace(
                root / "second", row["fixture_id"], row["failure_kind"]
            )
            self.assertEqual(first["manifest"], second["manifest"])

    def test_oracle_detects_injected_failed_recovery(self) -> None:
        self.assertTrue(final_state_oracle.failed_recovery_self_test()["passed"])
        row = DEFINITION["fixtures"][0]
        with tempfile.TemporaryDirectory(prefix="irisx-hrcv1a-failed-") as temporary:
            workspace = Path(temporary) / "workspace"
            recovery_common.build_failure_workspace(
                workspace, row["fixture_id"], row["failure_kind"]
            )
            recovery_common.execute_recovery(
                workspace, row["recovery_policy"], row["recovery_spec"]
            )
            (workspace / row["recovery_spec"]["output_path"]).write_bytes(b"{}\n")
            final = final_state_oracle.evaluate(workspace, row["oracle_spec"])
            self.assertFalse(final["final_state_valid"])
            self.assertEqual(final["changed_paths"], [row["recovery_spec"]["output_path"]])


if __name__ == "__main__":
    unittest.main()
