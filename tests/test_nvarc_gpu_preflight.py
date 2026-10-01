"""Pure scope and whole-sequence checks for the newly authorized GPU probe."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from irisx.arc_nvarc_gpu_preflight import check_plan, RECIPE, RUN
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from tools.verify_nvarc_gpu_preflight import verify


def fixture_rows():
    return [{"source_id": "fixture", "source_row": i, "puzzle_name": str(i),
             "parent_ids": ["synthetic-parent"], "exposure_tags": ["synthetic-fixture"],
             "input_ids": [12, 14, 10, 1, 13, 12, 15, 10, 2, 13],
             "labels": [-100] * 8 + [2, 13]} for i in range(4)]


def fixture_plan(rows):
    return {"format": "irisx/nvarc-q35-gpu-preflight-v1", "backend": "cpu", "synthetic_fixture": True,
        "world_size": 2, "maximum_optimizer_steps": 2, "packing": False, "source_recipe": RECIPE,
        "maximum_paid_usd": 0, "maximum_generations": 0, "maximum_teacher_calls": 0,
        "sample_digest": digest_value(rows), "checkpoint_steps": [1, 2],
        "maximum_sequence_length": 128, "scheduled_input_tokens": sum(len(x["input_ids"]) for x in rows),
        "maximum_training_tokens": 512, "seed": 24, "run_id": "synthetic-cpu-preflight"}


class GPUPreflightScopeTests(unittest.TestCase):
    def test_fixture_cannot_be_gpu_authority_and_schedule_cannot_be_truncated(self):
        rows = fixture_rows()
        plan = fixture_plan(rows)
        self.assertTrue(check_plan(plan, rows, 2).startswith("sha256:"))
        for name, value in (("backend", "cuda-l4"), ("maximum_sequence_length", 9),
                            ("maximum_training_tokens", 39), ("packing", True),
                            ("maximum_optimizer_steps", 3), ("maximum_generations", 1)):
            altered = copy.deepcopy(plan)
            altered[name] = value
            with self.subTest(name=name), self.assertRaises(ValidationError):
                check_plan(altered, rows, 2)
        altered = copy.deepcopy(rows)
        altered[0]["labels"][-1] = 4
        altered_plan = fixture_plan(altered)
        with self.assertRaises(ValidationError):
            check_plan(altered_plan, altered, 2)

    def test_returned_failure_is_bound_and_archive_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = fixture_rows()
            plan = fixture_plan(rows)
            (root / "plan.json").write_bytes(canonical_bytes(plan))
            (root / "samples.json").write_bytes(canonical_bytes(rows))
            hashes = {"plan": "fixture-plan", "runtime_wheel": "fixture-wheel"}
            (root / "stage-summary.json").write_bytes(canonical_bytes({"payload_sha256": hashes}))
            values = {"plan.json": canonical_bytes(plan), "payload-bindings.json": canonical_bytes(hashes),
                "terminal.json": canonical_bytes({"run_id": RUN, "outcome": "failed", "phase": "hardware-inventory",
                    "error": {"type": "RuntimeError", "message": "four L4s required"},
                    "contains_evaluator_truth": False, "full_sft_completed": False, "packing_verified": False})}
            def archive(name, payload, *, corrupt=False):
                entries = [{"path": key, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
                           for key,value in payload.items()]
                if corrupt:
                    entries[0]["sha256"] = "0" * 64
                index = {"format": "irisx/nvarc-gpu-preflight-archive-v1", "run_id": RUN,
                    "plan_digest": digest_value(plan), "members": entries}
                path = root / name
                with zipfile.ZipFile(path, "x") as target:
                    target.writestr("manifest.json", canonical_bytes(index))
                    for key,value in payload.items():
                        target.writestr(key, value)
                return path
            report = verify(archive("valid.zip", values), root)
            self.assertEqual(report["outcome"], "failed")
            self.assertFalse(report["runtime_verified"])
            self.assertEqual(report["worker_steps_verified"], 0)
            for name, payload, corrupt in (("hash.zip", values, True),
                    ("weights.zip", {**values, "model.safetensors": b"weights"}, False),
                    ("escape.zip", {**values, "../outside.json": b"escape"}, False)):
                with self.subTest(name=name), self.assertRaises(ValidationError):
                    verify(archive(name, payload, corrupt=corrupt), root)


if __name__ == "__main__":
    unittest.main()
