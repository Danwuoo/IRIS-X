"""UUID repair regressions on generated hardware code and the isolated worker."""

import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from irisx.arc_nvarc_combined import (REPAIR_RUN, activate_plan, check_logical_device, read)
from irisx.arc_nvarc_combined_worker import inventory
from irisx.arc_nvarc_hardware import collect_hardware_inventory, normalize_gpu_uuid
from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError
from tools.nvarc_combined_hardware_probe import (UUIDS, execute_hardware, fake_torch, probe_hardware, records, rows)
from tools.stage_nvarc_combined import DRAFT, HARDWARE_HELPER, render


class HardwareRepairTests(unittest.TestCase):
    def source(self):
        return render({"plan": canonical_bytes(activate_plan(read(DRAFT), run_id=REPAIR_RUN))},
                      {"plan": "plan.json"}, approved=True, run_id=REPAIR_RUN)

    def test_only_full_uuid_forms_are_normalized(self):
        for value in (UUIDS[0], "GPU-" + UUIDS[0], "GPU-" + UUIDS[0].upper()):
            self.assertEqual("GPU-" + UUIDS[0], normalize_gpu_uuid(value))
        for value in (UUIDS[0][:8], "GPU-" + UUIDS[0][:8], "{" + UUIDS[0] + "}",
                      "MIG-" + UUIDS[0], " " + UUIDS[0], None, 1, UUIDS[0].replace("-", "")):
            with self.assertRaisesRegex(ValueError, "full GPU UUID"):
                normalize_gpu_uuid(value)

    def test_exact_generated_parent_hardware_path_and_shared_source(self):
        source = self.source()
        self.assertIn(HARDWARE_HELPER.read_text(encoding="utf-8"), source)
        report = probe_hardware(source)
        self.assertEqual(12, report["cases_passed"])
        self.assertTrue(report["raw_diagnostics_on_rejection"])
        self.assertFalse(report["actual_cuda_devices"])

    def test_worker_maps_one_visible_uuid_to_physical_device_and_keeps_raw_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            parent = execute_hardware(self.source(), records(), rows(), root)
            smi = SimpleNamespace(stdout="\n".join(", ".join(row) for row in rows()))
            with patch.dict("sys.modules", {"torch": fake_torch(records([UUIDS[0]]))}), \
                 patch("subprocess.run", return_value=smi):
                worker = inventory(root / "worker")
            self.assertEqual(0, worker[0]["index"])
            self.assertEqual(3, worker[0]["physical_index"])
            check_logical_device("m2", parent, "GPU-" + UUIDS[0], worker, "GPU-" + UUIDS[0])
            with self.assertRaises(ValidationError):
                check_logical_device("m3", parent, "GPU-" + UUIDS[1], worker, "GPU-" + UUIDS[1])
            wrong = records(["99999999-9999-9999-9999-999999999999"])
            with patch.dict("sys.modules", {"torch": fake_torch(wrong)}), patch("subprocess.run", return_value=smi):
                with self.assertRaisesRegex(ValueError, "Torch UUID missing"):
                    inventory(root / "failed-worker")
            raw = read(root / "failed-worker/hardware-raw.json")
            self.assertEqual(wrong[0]["uuid"], raw["torch_records"][0]["uuid"])
            self.assertEqual(rows(), raw["smi_rows"])
            self.assertIn("Torch UUID missing", raw["error"]["message"])

    def test_raw_observations_precede_mapping_and_survive_collection_failure(self):
        snapshots = []
        torch = fake_torch(records())
        original = torch.cuda.get_device_properties
        def properties(index):
            if index == 1:
                raise RuntimeError("controlled property-read failure")
            return original(index)
        torch.cuda.get_device_properties = properties
        with self.assertRaisesRegex(RuntimeError, "controlled property-read"):
            collect_hardware_inventory(torch, "\n".join(", ".join(row) for row in rows()),
                                       lambda raw: snapshots.append(copy.deepcopy(raw)))
        self.assertEqual([], snapshots[0]["torch_records"])
        first = next(raw for raw in snapshots if raw["torch_records"])
        self.assertEqual(UUIDS[0], first["torch_records"][0]["uuid"])
        self.assertIsNone(first["torch_records"][0]["bf16"])
        self.assertNotIn("normalized_mapping", snapshots[-1])
        self.assertEqual("controlled property-read failure", snapshots[-1]["error"]["message"])


if __name__ == "__main__":
    unittest.main()
