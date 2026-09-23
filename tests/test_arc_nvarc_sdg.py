"""SDG stage identity/accounting and sandbox launch fixture checks."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from irisx.arc_nvarc_data import require_isolated_executor
from irisx.arc_nvarc_sdg import (DockerProgramExecutor, SavedTeacher,
                                 run_stage, run_teacher_pipeline)
from irisx.errors import ValidationError


class FakeTeacher:
    identity = "fake-teacher-v1"
    billed_calls = 1

    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def complete(self, stage, item, prompt):
        self.calls += 1
        if self.fail:
            raise RuntimeError("synthetic provider failure")
        return f"{stage}:{item['record_id']}"


class NvarcSDGTests(unittest.TestCase):
    def test_stage_replay_failure_reservation_and_no_repeat(self) -> None:
        items = [{"record_id": "a", "parent_id": "p", "source_id": "s"}]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            provider = FakeTeacher(fail=True)
            failed = run_stage("summary", items, "prompt", provider, root,
                               seed=3, maximum_calls=1)
            self.assertEqual("failed", failed["records"]["a"]["status"])
            provider.fail = False
            same = run_stage("summary", items, "prompt", provider, root,
                             seed=3, maximum_calls=1)
            self.assertEqual(1, provider.calls)
            self.assertEqual(failed, same)
            self.assertEqual(1, same["reserved_calls"])
            with self.assertRaises(ValidationError):
                run_stage("summary", items, "changed", provider, root,
                          seed=3, maximum_calls=1)

    def test_saved_pipeline_has_four_ordered_stages_and_zero_calls(self) -> None:
        item = {"record_id": "a", "parent_id": "p", "source_id": "s"}
        saved = {f"{stage}:a": stage for stage in
                 ("summary", "mix", "input-logic", "output-logic")}
        with tempfile.TemporaryDirectory() as temp:
            result = run_teacher_pipeline([item], {stage: stage for stage in
                                                  ("summary", "mix", "input-logic", "output-logic")},
                                          SavedTeacher(saved), Path(temp), seed=1,
                                          maximum_calls=0)
            self.assertEqual(0, result["reserved_calls"])
            self.assertEqual(4, len(result["stages"]))
            self.assertEqual("output-logic", result["stages"]["output-logic"]
                             ["records"]["a"]["response"])

    def test_claims_rejected_and_docker_command_is_closed(self) -> None:
        with self.assertRaises(ValidationError):
            require_isolated_executor({"attested": True, "network": "none",
                                       "credentials": "none", "mounts": "restricted",
                                       "cpu_limit": True, "memory_limit": True,
                                       "time_limit": True, "output_limit": True})
        executor = DockerProgramExecutor("local/python@sha256:" + "a" * 64)
        command = executor.command()
        self.assertIn("--network=none", command)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop=ALL", command)
        self.assertIn("--pull=never", command)
        self.assertFalse(any(part.startswith("--mount") or part.startswith("-v") for part in command))
        ast.parse(command[-1])
        with patch("irisx.arc_nvarc_sdg.shutil.which", return_value=None):
            with self.assertRaises(ValidationError):
                executor.execute("def transform(grid): return grid", [[1]])


if __name__ == "__main__":
    unittest.main()
