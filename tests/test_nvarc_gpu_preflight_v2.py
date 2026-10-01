"""Scope, CPU-state evidence and memory repair constraints without GPU calls."""
import copy
import unittest

from irisx.arc_nvarc_gpu_preflight_v2 import check_plan, MEMORY_POLICY, require_cpu_residency
from irisx.errors import ValidationError
from tests.test_nvarc_gpu_preflight import fixture_rows
from tests.test_nvarc_gpu_preflight import fixture_plan as first_fixture_plan


def fixture_plan(rows):
    value = first_fixture_plan(rows)
    value.update(format="irisx/nvarc-q35-gpu-preflight-v2", memory_policy=copy.deepcopy(MEMORY_POLICY))
    return value


class GPUPreflightV2BoundaryTests(unittest.TestCase):
    def test_cpu_fixture_cannot_grant_gpu_repair_or_change_frozen_workload(self):
        rows = fixture_rows()
        plan = fixture_plan(rows)
        self.assertTrue(check_plan(plan, rows, 2).startswith("sha256:"))
        for key, value in (("backend", "cuda-l4"), ("maximum_sequence_length", 9),
                           ("maximum_optimizer_steps", 3), ("maximum_generations", 1)):
            modified = copy.deepcopy(plan)
            modified[key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError):
                check_plan(modified, rows, 2)
        for key, value in (("fsdp_cpu_offload", False), ("optimizer_foreach", True),
                           ("control_backend", "nccl"), ("activation_checkpoint", "disabled")):
            modified = copy.deepcopy(plan)
            modified["memory_policy"][key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError):
                check_plan(modified, rows, 2)

    def test_cpu_fp32_residency_gate_rejects_gpu_moments_or_reduced_precision(self):
        snapshot = {key: {"cpu/torch.float32": 128} for key in
                    ("parameter_bytes", "gradient_bytes", "optimizer_bytes")}
        require_cpu_residency(snapshot)
        for key in snapshot:
            for wrong in ("cuda/torch.float32", "cpu/torch.bfloat16"):
                modified = copy.deepcopy(snapshot)
                modified[key][wrong] = 1
                with self.subTest(key=key, wrong=wrong), self.assertRaises(ValidationError):
                    require_cpu_residency(modified)


if __name__ == "__main__":
    unittest.main()
