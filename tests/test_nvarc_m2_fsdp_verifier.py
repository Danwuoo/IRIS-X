"""Fail-closed checks for retrieved four-L4 feasibility evidence."""

from __future__ import annotations

import copy
import unittest

from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.verify_nvarc_m2_fsdp import verify_observation


PHASES = ["input_verified", "hardware_gate_complete", "compact_gate_complete",
          "model_loaded", "fsdp_wrapped", "fingerprint_before_complete",
          "forward_start", "forward_complete", "backward_start", "backward_complete",
          "gradient_check_complete", "clip_complete", "optimizer_complete",
          "weight_check_complete", "fingerprint_after_complete",
          "result_gather_complete", "completed"]


def sample():
    plan = {"run_id": "nvarc-m2-fsdp-feasibility-003", "approved": True,
            "maximum_optimizer_steps": 1, "maximum_total_input_tokens": 512,
            "maximum_tokens_per_rank": 128, "maximum_kernel_wall_seconds": 1800,
            "maximum_paid_usd": 0, "compact_material_digest": "sha256:compact",
            "sequences_digest": "sha256:sequences"}
    hardware = {"bf16": True,
                "nvidia_smi_rows": [[str(rank), "NVIDIA L4", "23034", f"GPU-{rank}"]
                                    for rank in range(4)],
                "gpus": [{"index": rank, "name": "NVIDIA L4",
                          "memory_bytes": 23_000_000_000} for rank in range(4)]}
    ranks = [{"rank": rank, "local_rank": rank, "device_uuid": f"GPU-{rank}",
              "name": "NVIDIA L4", "total_memory_bytes": 23_000_000_000,
              "input_tokens": 60, "loss": 1.0 + rank / 10,
              "nonzero_gradient_tensors": 3, "peak_cuda_allocated_mib": 100.0,
              "step_wall_seconds": 2.0,
              "weight_fingerprint_before": [1.0, 2.0],
              "weight_fingerprint_after": [1.5, 2.5]} for rank in range(4)]
    result = {"format": "irisx/nvarc-m2-fsdp-feasibility-result-v1",
              "contains_evaluator_truth": False, "optimizer_steps": 1,
              "compact_material_digest": plan["compact_material_digest"],
              "sequences_digest": plan["sequences_digest"],
              "plan_digest": digest_value(plan),
              "claim": "FSDP one-step compatibility only; no exported ARC-SFT checkpoint",
              "ranks": ranks, "total_input_tokens": 240, "wall_seconds": 10.0}
    terminal = {"return_code": 0, "wall_seconds": 20.0}
    traces = {rank: [{"rank": rank, "phase": phase,
                      **({"input_tokens": 60} if phase == "forward_start" else {})}
                     for phase in PHASES] for rank in range(4)}
    return plan, result, terminal, hardware, traces


class FSDPResultVerifierTests(unittest.TestCase):
    def test_accepts_bounded_observation_and_rejects_tampering(self):
        base = sample()
        self.assertEqual(240, verify_observation(*base)["total_input_tokens"])
        for edit in (
                lambda item: item[1]["ranks"][0].update(
                    weight_fingerprint_after=(1.5, 2.5)),
                lambda item: item[1]["ranks"][3].update(device_uuid="GPU-0"),
                lambda item: item[1]["ranks"][2].update(input_tokens=129),
                lambda item: item[1].update(evaluator_answer=[[1]]),
                lambda item: item[4][1].pop()):
            altered = copy.deepcopy(base)
            edit(altered)
            with self.assertRaises(ValidationError):
                verify_observation(*altered)


if __name__ == "__main__":
    unittest.main()
