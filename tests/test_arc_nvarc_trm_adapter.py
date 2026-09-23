"""TRM supervised launch fixture and strict upstream attempt parser."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from irisx.arc_nvarc_trm import execute_trm_spec, integrate_attempts, read_trm_submission
from irisx.errors import ValidationError


class NvarcTRMAdapterTests(unittest.TestCase):
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
