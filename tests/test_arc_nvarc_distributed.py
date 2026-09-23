"""Actual two-rank CPU collective checks; optional in the light Python."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from irisx.arc_nvarc_data import freeze_shards, visible_task
from irisx.arc_nvarc_distributed import supervise, tiny_torch_model
from irisx.canonical import canonical_bytes, digest_value


class NvarcDistributedTests(unittest.TestCase):
    def test_two_rank_cpu_collective_resume_and_failure(self) -> None:
        try:
            import torch
            import torch.distributed as dist
        except ImportError:
            self.skipTest("PyTorch distributed is absent from this interpreter")
        if not dist.is_available() or not dist.is_gloo_available():
            self.skipTest("PyTorch Gloo is unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records = []
            for index in range(4):
                task = visible_task(f"task-{index}", {
                    "train": [{"input": [[index]], "output": [[index + 1]]}],
                    "test": [{"input": [[index + 2]]}]})
                records.append({**task, "parent_id": f"parent-{index}",
                                "source_id": "synthetic", "split": "sft-train"})
            freeze_shards(records, root / "frozen", policy="clean-research")
            config = {"mode": "ddp-full-sft", "device": "cpu", "seed": 7,
                      "learning_rate": 0.01, "max_steps": 4,
                      "maximum_training_tokens": 10000, "max_sequence_length": 128,
                      "gradient_accumulation": 1, "checkpoint_every": 1,
                      "include_unused_visual": True}
            config_path = root / "config.json"
            config_path.write_bytes(canonical_bytes(config, newline=True))
            paused = supervise(config_path=config_path, data_root=root / "frozen",
                               output=root / "resumed", world_size=2,
                               session_wall_seconds=45, maximum_total_wall_seconds=120,
                               fixture=True, stop_after_steps=2)
            self.assertEqual("returned", paused["status"], Path(paused["log"]).read_text(errors="replace"))
            resumed = supervise(config_path=config_path, data_root=root / "frozen",
                                 output=root / "resumed", world_size=2,
                                 session_wall_seconds=45, maximum_total_wall_seconds=120,
                                 fixture=True, resume=True)
            self.assertEqual("returned", resumed["status"], Path(resumed["log"]).read_text(errors="replace"))
            whole = supervise(config_path=config_path, data_root=root / "frozen",
                               output=root / "whole", world_size=2,
                               session_wall_seconds=45, maximum_total_wall_seconds=120,
                               fixture=True)
            self.assertEqual("returned", whole["status"], Path(whole["log"]).read_text(errors="replace"))
            a = torch.load(root / "resumed" / "ddp-training-state.pt", weights_only=False)
            b = torch.load(root / "whole" / "ddp-training-state.pt", weights_only=False)
            self.assertEqual((4, 4, a["tokens_seen"]), (a["step"], a["cursor"], b["tokens_seen"]))
            for key, value in a["model"].items():
                self.assertTrue(torch.equal(value, b["model"][key]), key)
            initial = tiny_torch_model(config["seed"], include_unused_visual=True).state_dict()
            self.assertFalse(torch.equal(initial["embedding.weight"], a["model"]["embedding.weight"]))
            self.assertFalse(torch.equal(initial["head.weight"], a["model"]["head.weight"]))
            self.assertTrue(torch.equal(initial["unused_visual.weight"], a["model"]["unused_visual.weight"]))
            rank0 = json.loads((root / "whole" / "rank-0.json").read_bytes())
            rank1 = json.loads((root / "whole" / "rank-1.json").read_bytes())
            self.assertEqual(set(), set(rank0["assigned_indices"]) & set(rank1["assigned_indices"]))
            failure = supervise(config_path=config_path, data_root=root / "frozen",
                                output=root / "failed", world_size=2,
                                session_wall_seconds=45, maximum_total_wall_seconds=120,
                                fixture=True, fail_rank_step=(1, 1))
            self.assertEqual("worker_failure", failure["status"])
            self.assertTrue(failure["checkpoint_exists"])
            failed_state = torch.load(root / "failed" / "ddp-training-state.pt", weights_only=False)
            self.assertEqual(1, failed_state["step"])
            ledger = json.loads((root / "failed" / "ddp-ledger.json").read_bytes())
            self.assertEqual(45, ledger["charged_wall_seconds"])
            recovered = supervise(config_path=config_path, data_root=root / "frozen",
                                   output=root / "failed", world_size=2,
                                   session_wall_seconds=45, maximum_total_wall_seconds=120,
                                   fixture=True, resume=True)
            self.assertEqual("returned", recovered["status"], Path(recovered["log"]).read_text(errors="replace"))
            self.assertGreater(recovered["charged_wall_seconds"], 45)


if __name__ == "__main__":
    unittest.main()
