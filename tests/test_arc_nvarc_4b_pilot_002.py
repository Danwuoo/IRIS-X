"""The distinct repair draft binds the official mount and hardware evidence."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from irisx.arc_nvarc_4b_pilot_002 import hardware_usable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from stage_nvarc_4b_pilot_002 import stage  # noqa: E402


class FourBPilotRepairDraftTests(unittest.TestCase):
    def test_draft_binds_official_mount_and_refuses_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            summary = stage(Path(temp) / "stage")
            kernel = Path(summary["local_kernel_path"])
            metadata = json.loads((kernel / "kernel-metadata.json").read_bytes())
            code = "".join(json.loads((kernel / "kaggle-notebook.ipynb").read_bytes())
                           ["cells"][0]["source"])
            self.assertFalse(summary["approved"])
            self.assertEqual(summary["run_id"], "nvarc-4b-compat-pilot-002")
            self.assertTrue(metadata["id"].startswith("DRAFT-DO-NOT-PUSH/"))
            self.assertTrue(metadata["is_private"])
            self.assertFalse(metadata["enable_internet"])
            self.assertEqual(metadata["machine_shape"], "NvidiaL4")
            self.assertEqual(metadata["competition_sources"],
                             ["arc-prize-2026-arc-agi-2"])
            self.assertEqual(metadata["dataset_sources"],
                             ["danielwuu/irisx-arc-agi-2-trial-002-smoke-001"])
            self.assertIn('plan.get("approved") is not True', code)
            self.assertIn("nvarc-4b-pilot-hardware-preflight.json", code)
            self.assertIn("nvarc-4b-pilot-mount-preflight.json", code)
            self.assertIn("/kaggle/input/competitions/arc-prize-2026-arc-agi-2", code)
            self.assertIn("arc-agi_training_challenges.json", code)
            self.assertNotIn("arc-agi_training_solutions.json", code)
            self.assertIn("irisx.arc_nvarc_4b_pilot_002", code)
            with self.assertRaisesRegex(RuntimeError, "no exact owner launch authorization"):
                exec(compile(code, "draft-notebook", "exec"), {})

    def test_one_usable_l4_is_required_and_observed(self) -> None:
        hardware = {"cuda_available": True, "torch_cuda_device_count": 1,
                    "gpus": [{"index": 0, "name": "NVIDIA L4", "memory_mib": 22563}],
                    "nvidia_smi_exit_code": 0, "nvidia_smi_rows": ["0, NVIDIA L4, 23034"]}
        self.assertTrue(hardware_usable(hardware))
        self.assertFalse(hardware_usable({**hardware, "gpus": [{**hardware["gpus"][0],
                                                               "memory_mib": 21999}]}))
        self.assertFalse(hardware_usable({**hardware, "torch_cuda_device_count": 0,
                                          "gpus": []}))
        self.assertFalse(hardware_usable({**hardware, "nvidia_smi_exit_code": 1}))


if __name__ == "__main__":
    unittest.main()
