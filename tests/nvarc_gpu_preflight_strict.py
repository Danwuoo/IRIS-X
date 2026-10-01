"""Real two-rank FSDP source loss/schedule/checkpoint integration on tiny CPU."""
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

import torch
from irisx.arc_nvarc_gpu_preflight import token_normalized_loss
from irisx.arc_nvarc_m2 import create_tiny_qwen_material
from irisx.canonical import canonical_bytes, digest_value
from tests.test_nvarc_gpu_preflight import fixture_rows, fixture_plan

ROOT = Path(__file__).resolve().parents[1]


class GPUPreflightStrictTests(unittest.TestCase):
    def test_global_token_loss_gradients_match_independent_concatenation(self):
        torch.manual_seed(24)
        inputs = [torch.randn(1, 5, 3), torch.randn(1, 8, 3)]
        labels = [torch.tensor([[-100, -100, 0, 1, 2]]),
                  torch.tensor([[-100, 1, 2, -100, 0, 1, 2, 0]])]
        model = torch.nn.Linear(3, 4)
        oracle = copy.deepcopy(model)
        count = sum(int((x[:, 1:] != -100).sum()) for x in labels)
        for x, y in zip(inputs, labels):
            loss, _ = token_normalized_loss(model(x), y, world=2, global_supervised_tokens=count)
            (loss / 2).backward()
        logits = torch.cat([oracle(x)[:, :-1].reshape(-1, 4) for x in inputs])
        target = torch.cat([y[:, 1:].reshape(-1) for y in labels])
        torch.nn.functional.cross_entropy(logits, target, ignore_index=-100).backward()
        for left, right in zip(model.parameters(), oracle.parameters()):
            torch.testing.assert_close(left.grad, right.grad)

    def test_source_optimizer_two_rank_checkpoint_resume_matches_continuous(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model, base = create_tiny_qwen_material(root / "model")
            del model
            rows = fixture_rows()
            # Unequal assistant counts make rank-average loss an invalid substitute.
            rows[1]["input_ids"] = rows[1]["input_ids"] * 2
            rows[1]["labels"] = rows[1]["labels"] * 2
            rows[3]["input_ids"] = rows[3]["input_ids"] * 3
            rows[3]["labels"] = rows[3]["labels"] * 3
            plan = fixture_plan(rows)
            plan["base_material_digest"] = base
            (root / "plan.json").write_bytes(canonical_bytes(plan, newline=True))
            (root / "samples.json").write_bytes(canonical_bytes(rows, newline=True))

            def launch(name, flags=()):
                with socket.socket() as sock:
                    sock.bind(("127.0.0.1", 0))
                    port = sock.getsockname()[1]
                command = [sys.executable, "-m", "irisx.arc_nvarc_gpu_preflight", "--plan", str(root / "plan.json"),
                    "--model", str(root / "model"), "--samples", str(root / "samples.json"),
                    "--output", str(root / name), "--scratch", str(root / (name + "-scratch")), *flags]
                processes, logs = [], []
                try:
                    for rank in range(2):
                        log = (root / f"{name}-rank-{rank}.log").open("w", encoding="utf-8")
                        logs.append(log)
                        env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "MASTER_ADDR": "127.0.0.1",
                            "MASTER_PORT": str(port), "WORLD_SIZE": "2", "RANK": str(rank), "LOCAL_RANK": str(rank),
                            "USE_LIBUV": "0", "OMP_NUM_THREADS": "1", "HF_HUB_OFFLINE": "1"}
                        processes.append(subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT))
                    deadline = time.monotonic() + 150
                    while any(p.poll() is None for p in processes):
                        if any(p.poll() not in {None, 0} for p in processes) or time.monotonic() > deadline:
                            self.fail("FSDP preflight worker failed/timed out: " + "\n".join(
                                p.read_text(errors="replace")[-6000:] for p in root.glob(name + "-rank-*.log")))
                        time.sleep(0.2)
                    self.assertEqual([0, 0], [p.returncode for p in processes])
                finally:
                    for p in processes:
                        if p.poll() is None:
                            p.kill()
                            p.wait(timeout=10)
                    for log in logs:
                        log.close()
            launch("continuous")
            launch("resumed", ["--stop-after-step", "1"])
            pause = json.loads((root / "resumed/pause-result.json").read_bytes())
            launch("resumed", ["--resume"])
            continuous = json.loads((root / "continuous/final-result.json").read_bytes())
            final = json.loads((root / "resumed/final-result.json").read_bytes())
            self.assertEqual(continuous["weight_fingerprint_after"], final["weight_fingerprint_after"])
            self.assertEqual(pause["weight_fingerprint_after"], final["restored_fingerprint"])
            self.assertEqual(plan["scheduled_input_tokens"], final["input_tokens"])
            self.assertEqual((2, 4), (final["step"], final["forwards"]))
            self.assertEqual(1e-6, pause["observations"][0][0]["learning_rate"])
            self.assertAlmostEqual(1.495e-6, final["observations"][0][0]["learning_rate"], places=14)
            self.assertFalse((root / "resumed-scratch/checkpoint-step-0001").exists())
            self.assertTrue((root / "resumed/checkpoint-1-manifest.json").is_file())
            self.assertTrue((root / "resumed/checkpoint-2-manifest.json").is_file())
            self.assertFalse(final["packing_verified"])
            self.assertFalse(final["full_sft_completed"])


if __name__ == "__main__":
    unittest.main()
