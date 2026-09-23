"""TRM supervised launch fixture and strict upstream attempt parser."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from irisx.arc_nvarc_trm import (execute_trm_spec, integrate_attempts,
                                 read_trm_prediction_tensors, read_trm_submission,
                                 trm_grid)
from irisx.errors import ValidationError


class NvarcTRMAdapterTests(unittest.TestCase):
    def test_truth_free_raw_tensor_normalization_and_fixture_provenance(self) -> None:
        try:
            import numpy as np
            import torch
        except ImportError:
            self.skipTest("torch and numpy needed for saved TRM tensor fixture")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original_input = [[1, 2], [3, 4]]
            original_output = [[5, 6], [7, 8]]
            augmented_input = np.rot90(np.array(original_input), 1).tolist()
            augmented_output = np.rot90(np.array(original_output), 1).tolist()
            tensor_path = root / "step_1_all_preds.0"
            torch.save({"inputs": torch.tensor([trm_grid(augmented_input)]),
                        "preds": torch.tensor([trm_grid(augmented_output)]),
                        "puzzle_identifiers": torch.tensor([1]),
                        "q_halt_logits": torch.tensor([0.0])}, tensor_path)
            identifiers = root / "identifiers.json"
            identifiers.write_text(json.dumps(["<blank>", "a|||t1|||0123456789"]))
            visible = {"a": {"train": [], "test": [{"input": original_input}]}}
            result = read_trm_prediction_tensors(
                [tensor_path], identifiers, visible,
                invocation={"source_kind": "parser-fixture", "status": "complete"},
                expected_ranks=1)
            self.assertEqual(1, result["test_outputs"])
            self.assertEqual(0, result["invalid_predictions"])
            self.assertEqual(original_output, result["candidates"][("a", 0)][0]["grid"])
            self.assertEqual("trm-fixture", result["candidates"][("a", 0)][0]["branch"])
            self.assertEqual(1, result["candidates"][("a", 0)][0]["votes"])
            with self.assertRaises(ValidationError):
                integrate_attempts([], result["candidates"][("a", 0)], mode="trm-only")

    def test_bounded_invocation_fixture_is_not_model_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec = {"format": "irisx/nvarc-trm-preprocess-spec", "cwd": str(root),
                    "argv": ["unavailable-upstream"], "maximum_wall_seconds": 5,
                    "source_file": str(root / "upstream.py"), "source_sha256": "0" * 64}
            with self.assertRaises(ValidationError):
                execute_trm_spec(spec, root / "unauthorized")
            report = execute_trm_spec(spec, root / "fixture", fixture_command=[
                sys.executable, "-c", "print('synthetic preprocessing launch')"])
            self.assertEqual("complete", report["status"])
            self.assertEqual("launch-fixture", report["source_kind"])
            submission = root / "submission.json"
            submission.write_text(json.dumps({"a": [{f"attempt_{i}": [[i % 10]]
                                                    for i in range(1, 11)}]}))
            with self.assertRaises(ValidationError):
                read_trm_submission(submission, {"a": 1}, invocation=report)
            parser_fixture = {"source_kind": "parser-fixture", "status": "complete"}
            attempts = read_trm_submission(submission, {"a": 1}, invocation=parser_fixture)
            self.assertEqual(10, len(attempts[("a", 0)]))
            self.assertEqual("trm-fixture", attempts[("a", 0)][0]["branch"])
            with self.assertRaises(ValidationError):
                integrate_attempts([], attempts[("a", 0)], mode="trm-only")
            with self.assertRaises(ValidationError):
                read_trm_submission(submission, {"a": 2}, invocation=parser_fixture)


if __name__ == "__main__":
    unittest.main()
