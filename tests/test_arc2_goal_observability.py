"""Portable bounded-log tests, not live provider or model-quality evidence."""
from __future__ import annotations

import io
import json
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools.arc2_goal_sprint_20261017 import launch
from tests.platform_requirements import requires_linux


@contextmanager
def diagnostic_descriptor():
    console = mock.Mock()
    console.fileno.return_value = 91
    with mock.patch.object(launch.sys, "stdout", console), \
            mock.patch.object(launch.os, "get_blocking", return_value=True, create=True), \
            mock.patch.object(launch.os, "set_blocking", create=True) as flags, \
            mock.patch.object(launch.os, "write") as writer:
        yield writer, flags


class SolverLogRelayTests(unittest.TestCase):
    def test_separate_reader_cursor_and_bounded_chunks(self):
        reader = io.BytesIO(b"first\nsecond\n")
        with diagnostic_descriptor() as (writer, flags):
            self.assertEqual(launch.relay_solver_log(reader, max_bytes=6), 6)
            writer.assert_called_with(91, b"first\n")
            self.assertEqual(launch.relay_solver_log(reader, max_bytes=7), 7)
            writer.assert_called_with(91, b"second\n")
            self.assertEqual(launch.relay_solver_log(reader), 0)
            self.assertEqual(flags.call_args_list, [mock.call(91, False), mock.call(91, True)] * 2)

    def test_default_read_is_bounded_and_preserves_remaining_log(self):
        reader = io.BytesIO(b"a" * (64 * 1024 + 10))
        with diagnostic_descriptor() as (writer, _):
            self.assertEqual(launch.relay_solver_log(reader), 64 * 1024)
            self.assertEqual(len(writer.call_args.args[1]), 64 * 1024)
        self.assertEqual(reader.read(), b"a" * 10)

    def test_disconnected_console_does_not_abort_solver_owner(self):
        reader = io.BytesIO(b"diagnostic\n")
        with diagnostic_descriptor() as (writer, flags):
            writer.side_effect = BrokenPipeError("observer disconnected")
            self.assertEqual(launch.relay_solver_log(reader), 11)
            flags.assert_called_with(91, True)
        self.assertEqual(reader.tell(), 11)

    def test_malformed_diagnostic_bytes_do_not_abort_relay(self):
        with diagnostic_descriptor() as (writer, _):
            self.assertEqual(launch.relay_solver_log(io.BytesIO(b"\xff\n")), 2)
            writer.assert_called_with(91, "\ufffd\n".encode())

    def test_saturated_or_short_write_is_not_retried(self):
        for error in (BlockingIOError("pipe full"), None):
            with self.subTest(error=error), diagnostic_descriptor() as (writer, flags):
                writer.side_effect = error
                writer.return_value = 1
                self.assertEqual(launch.relay_solver_log(io.BytesIO(b"diagnostic")), 10)
                writer.assert_called_once()
                flags.assert_called_with(91, True)

    def test_no_fileno_drops_optional_observation_without_python_write(self):
        console = io.StringIO()
        with mock.patch.object(launch.sys, "stdout", console):
            self.assertEqual(launch.relay_solver_log(io.BytesIO(b"diagnostic")), 10)
        self.assertEqual(console.getvalue(), "")

    def test_restore_failure_is_best_effort(self):
        with diagnostic_descriptor() as (_, flags):
            flags.side_effect = [None, OSError("descriptor closed")]
            self.assertEqual(launch.relay_solver_log(io.BytesIO(b"diagnostic")), 10)

    def test_unavailable_nonblocking_api_has_no_blocking_fallback(self):
        with diagnostic_descriptor() as (writer, _), \
                mock.patch.object(launch.os, "set_blocking", None, create=True):
            self.assertEqual(launch.relay_solver_log(io.BytesIO(b"diagnostic")), 10)
            writer.assert_not_called()

    @requires_linux("exercise actual Linux stdout pipe saturation without a consuming reader")
    def test_actual_unread_full_pipe_cannot_stall_owner(self):
        code = '''import io, os
from tools.arc2_goal_sprint_20261017 import launch
os.set_blocking(1, False)
while True:
    try: os.write(1, b'x' * 65536)
    except BlockingIOError: break
os.set_blocking(1, True)
launch.relay_solver_log(io.BytesIO(b'y' * 65536))
os._exit(0)
'''
        process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   cwd=Path(__file__).resolve().parents[1])
        try:
            self.assertEqual(process.wait(timeout=5), 0)
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

    def test_invalid_bounds_rejected_even_under_optimized_python(self):
        for limit in (0, -1, True, 1.5, 1024 * 1024 + 1):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                launch.relay_solver_log(io.BytesIO(), max_bytes=limit)


class PrivateCandidateAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "full-candidate-pools.json"
        self.pools = {"run_id": "synthetic", "records": [{"task_id": "task", "tests": [
            {"test_index": 0, "input_digest": "synthetic-input", "ranked_grids": [[[2]], [[1]]]}]}]}
        self.audit = {"format": "irisx/private-full-candidates-v1", "run_id": "synthetic", "records": [
            {"task_id": "task", "test_index": 0, "input_digest": "synthetic-input",
             "candidates": [{"grid": [[1]]}, {"grid": [[2]]}, {"grid": [[3]]}],
             "ranked_candidate_indices": [1, 0, 2]}]}

    def tearDown(self):
        self.temporary.cleanup()

    def check(self):
        self.path.write_text(json.dumps(self.audit), encoding="utf-8")
        return launch.candidate_audit(self.path, self.pools)

    def test_full_pool_is_pinned_but_only_selected_two_are_scored(self):
        receipt = self.check()
        self.assertEqual(receipt["sha256"], launch.sha(self.path))
        self.assertEqual(receipt["queries"], 1)
        self.assertFalse(receipt["used_for_scoring"])
        self.assertEqual(receipt["scored_max_candidates"], 2)

    def test_rank_change_cannot_select_another_posthoc_candidate(self):
        self.audit["records"][0]["ranked_candidate_indices"] = [2, 1, 0]
        with self.assertRaisesRegex(ValueError, "top two differ"):
            self.check()

    def test_duplicate_out_of_range_boolean_or_omitted_rank_rejected(self):
        for rank in ([1, 1, 2], [1, 0, 3], [True, 0, 2], [1, 0]):
            self.audit["records"][0]["ranked_candidate_indices"] = rank
            with self.subTest(rank=rank), self.assertRaisesRegex(ValueError, "permutation"):
                self.check()

    def test_missing_duplicate_or_foreign_query_rejected(self):
        original = self.audit["records"][0]
        for records in ([], [original, original], [{**original, "task_id": "foreign"}]):
            self.audit["records"] = records
            with self.subTest(records=records), self.assertRaisesRegex(ValueError, "coverage|incomplete"):
                self.check()

    def test_wrong_identity_and_nonfinite_values_rejected(self):
        self.audit["run_id"] = "other"
        with self.assertRaisesRegex(ValueError, "identity"):
            self.check()
        self.audit["run_id"] = "synthetic"
        self.audit["untrusted_extra"] = float("nan")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            self.check()

    def test_more_than_sixteen_candidates_rejected(self):
        self.audit["records"][0]["candidates"] = [{"grid": [[0]]}] * 17
        self.audit["records"][0]["ranked_candidate_indices"] = list(range(17))
        with self.assertRaisesRegex(ValueError, "bounded candidate"):
            self.check()

    def test_type_confusion_and_overflow_are_not_exact_bindings(self):
        self.audit["records"][0]["test_index"] = False
        with self.assertRaisesRegex(ValueError, "exact candidate query identity"):
            self.check()
        self.audit["records"][0]["test_index"] = 0
        for cell in (True, 1.0):
            self.audit["records"][0]["candidates"][0]["grid"] = [[cell]]
            with self.assertRaisesRegex(ValueError, "integer candidate grid"):
                self.check()
        self.audit["records"][0]["candidates"][0]["grid"] = [[1]]
        self.path.write_text(json.dumps(self.audit)[:-1] + ', "score": 1e999}')
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            launch.candidate_audit(self.path, self.pools)

    def test_failed_run_may_retain_explicitly_incomplete_audit(self):
        self.audit["records"] = []
        self.path.write_text(json.dumps(self.audit))
        receipt = launch.candidate_audit(self.path, self.pools, require_complete=False)
        self.assertEqual(receipt["expected_queries"], 1)
        self.assertEqual(receipt["missing_queries"], 1)
        self.assertFalse(receipt["complete_coverage"])
        self.assertFalse(receipt["complete_required"])

    @requires_linux("seal integration imports the Linux-owned process closure verifier")
    def test_completed_expanded_solver_requires_audit_at_seal(self):
        root = self.path.parent
        (root / "pools.json").write_text(json.dumps(self.pools))
        proof = {"closed": True, "ownership_complete": True, "worker_returncode": 0}
        for index, policy in enumerate(({"candidate_views": 8, "candidate_ranker": "vote"},
                                        {"candidate_views": 2, "candidate_ranker": "first", "candidate_batch_size": 2})):
            (root / "run-summary.json").write_text(json.dumps({"run_id": "synthetic", "solver_status": "complete",
                                                              "continuation_policy": policy}))
            with self.subTest(policy=policy), \
                mock.patch("tools.arc_learning_agent_20261011.process_guard.verify_closed_proof"), \
                mock.patch.object(launch.os, "chmod"), \
                self.assertRaisesRegex(ValueError, "requires private candidate audit"):
                launch.seal_predictions(root, root / f"sealed-{index}", proof, "a" * 64)

    @requires_linux("seal integration imports the Linux-owned process closure verifier")
    def test_failed_solver_seals_partial_audit_without_enlarging_predictions(self):
        root = self.path.parent
        (root / "pools.json").write_text(json.dumps(self.pools))
        self.audit["records"] = []
        self.path.write_text(json.dumps(self.audit))
        proof = {"closed": True, "ownership_complete": True, "worker_returncode": 1}
        with mock.patch("tools.arc_learning_agent_20261011.process_guard.verify_closed_proof"), \
                mock.patch.object(launch.os, "chmod"):
            seal = launch.seal_predictions(root, root / "sealed", proof, "a" * 64)
        self.assertEqual(json.loads((root / "sealed/pools.json").read_text()), self.pools)
        self.assertEqual(seal["private_candidate_audit"]["missing_queries"], 1)
        self.assertFalse(seal["private_candidate_audit"]["complete_required"])
        self.assertFalse(seal["private_candidate_audit"]["used_for_scoring"])

    def test_oversized_file_rejected_before_read(self):
        with self.path.open("wb") as stream:
            stream.truncate(64 * 1024**2 + 1)
        with self.assertRaisesRegex(ValueError, "bounded candidate audit"):
            launch.candidate_audit(self.path, self.pools)


if __name__ == "__main__":
    unittest.main()
