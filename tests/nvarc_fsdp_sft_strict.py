"""Actual two-rank Qwen3.5 FSDP checkpoint/resume/export regression."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from irisx.arc_nvarc_fsdp_sft import (package_checkpoint_transport,
                                      restore_checkpoint_transport, verify_checkpoint)
from irisx.arc_nvarc_m2 import (create_tiny_qwen_material, freeze_arc_sft_data,
                                 load_frozen_arc_sft_data)
from irisx.arc_nvarc_representation import verify_model_material
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from tools.nvarc_source_stage import validate_profile_material


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/m2-m3-small.json"
SOURCE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/source"


class FSDPSFTStrictTests(unittest.TestCase):
    def test_two_rank_actual_resume_export_and_tamper(self):
        with tempfile.TemporaryDirectory(prefix="nvarc-fsdp-sft-") as temporary:
            root = Path(temporary)
            config = json.loads(CONFIG.read_bytes())
            freeze_arc_sft_data(config, SOURCE, root / "data")
            sequences = load_frozen_arc_sft_data(config, root / "data")
            sequence_bytes = b"".join(canonical_bytes(item, newline=True) for item in sequences)
            (root / "sequences.jsonl").write_bytes(sequence_bytes)
            model, base_digest = create_tiny_qwen_material(root / "base")
            del model
            (root / "base/dataset-metadata.json").write_bytes(canonical_bytes(
                {"title": "test-only mounted compact material"}, newline=True))
            plan = {"format": "irisx/nvarc-m2-fsdp-sft-v1", "mode": "full-sft",
                    "packing": False, "backend": "cpu", "local_cpu_validation": True,
                    "approved": False, "world_size": 2, "maximum_paid_usd": 0,
                    "maximum_teacher_calls": 0, "maximum_generations": 0,
                    "maximum_optimizer_steps": 2, "maximum_training_tokens": 512,
                    "max_sequence_length": 128, "checkpoint_steps": [1, 2],
                    "gradient_accumulation": 1, "learning_rate": 0.0001,
                    "weight_decay": 0.0, "seed": 24,
                    "compact_material_digest": base_digest,
                    "sequences_sha256": hashlib.sha256(sequence_bytes).hexdigest(),
                    "sequences_digest": digest_value(sequences),
                    "sequence_count": len(sequences)}
            (root / "plan.json").write_bytes(canonical_bytes(plan, newline=True))
            identity = digest_value({"plan": plan, "model_material_digest": base_digest,
                                     "sequences_digest": plan["sequences_digest"]})
            environment = {**os.environ, "PYTHONPATH": str(ROOT / "src") + os.pathsep + str(ROOT)}

            def launch(name: str, *flags: str) -> None:
                command = [sys.executable, str(ROOT / "tools/nvarc_fsdp_cpu_launch.py"),
                           "--plan", str(root / "plan.json"),
                           "--compact", str(root / "base"),
                           "--sequences", str(root / "sequences.jsonl"),
                           "--output", str(root / name), *flags]
                completed = subprocess.run(command, env=environment, capture_output=True,
                                           text=True, timeout=180)
                if completed.returncode:
                    logs = [path.read_text(encoding="utf-8", errors="replace")[-6000:]
                            for path in root.glob(f"{name}-rank-*.log")]
                    self.fail(f"FSDP worker failed: {completed.stdout}\n{completed.stderr}\n{logs}")

            def export(name: str) -> dict:
                command = [sys.executable, "-m", "irisx.arc_nvarc_fsdp_sft",
                           "--plan", str(root / "plan.json"),
                           "--compact", str(root / "base"),
                           "--sequences", str(root / "sequences.jsonl"),
                           "--output", str(root / name), "--export"]
                completed = subprocess.run(command, env=environment, capture_output=True,
                                           text=True, timeout=180)
                self.assertEqual(completed.returncode, 0, completed.stderr[-6000:])
                return json.loads((root / name / "export-chain.json").read_bytes())

            launch("continuous")
            continuous = export("continuous")
            launch("resumed", "--stop-after-steps", "1")
            pause = json.loads((root / "resumed/pause-result.json").read_bytes())
            self.assertEqual((pause["step"], pause["tokens_seen"], pause["stop_reason"]),
                             (1, 120, "controlled_interruption"))
            launch("resumed", "--resume")
            resumed = export("resumed")
            final = json.loads((root / "resumed/final-result.json").read_bytes())
            self.assertEqual((final["step"], final["tokens_seen"], final["forwards"],
                              final["invocation_forwards"]), (2, 240, 4, 2))
            self.assertEqual(continuous["export_material_digest"],
                             resumed["export_material_digest"])
            self.assertEqual(continuous["identity_digest"], identity)
            material = verify_model_material(root / "resumed/export",
                                             resumed["export_material_digest"])
            validate_profile_material("4b", base_digest,
                                      resumed["export_material_digest"], material)
            with self.assertRaises(ValidationError):
                validate_profile_material("4b", "sha256:" + "0" * 64,
                                          resumed["export_material_digest"], material)
            checkpoint = root / "resumed" / final["checkpoint"]["path"]
            verify_checkpoint(checkpoint, identity, 2)
            transport = package_checkpoint_transport(root / "resumed", maximum_member_bytes=200_000)
            self.assertEqual(transport["checkpoint_manifest_digest"],
                             final["checkpoint"]["manifest_digest"])
            self.assertTrue(transport["split_members"])
            restored_path = root / "restored"
            restored = restore_checkpoint_transport(root / "resumed", restored_path)
            self.assertEqual(digest_value(restored), transport["checkpoint_manifest_digest"])
            with (restored_path / "rank-0.pt").open("ab") as stream:
                stream.write(b"tamper")
            with self.assertRaises(ValidationError):
                verify_checkpoint(restored_path, identity, 2)


if __name__ == "__main__":
    unittest.main()
