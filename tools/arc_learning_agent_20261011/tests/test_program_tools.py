"""Real CPU AST/OS-verifier tests. No mocked program execution or neural claims."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from tools.arc_learning_agent_20261011 import program_tools as p

IDENTITY = "def transform(grid):\n    return copy_grid(grid)\n"
ROTATE_RECOLOR = """def recolor(g):
    out = copy_grid(g)
    for r in range(len(out)):
        for c in range(len(out[r])):
            if out[r][c] == 1:
                out[r][c] = 2
    return out
def transform(grid):
    return recolor(transpose(grid[::-1]))
"""
COMPONENTS = """def transform(grid):
    objects = components(grid, 0, 4)
    best = objects[0]
    for obj in objects:
        if len(obj) > len(best):
            best = obj
    out = copy_grid(grid)
    for pixel in best:
        out[pixel[0]][pixel[1]] = 9
    return out
"""


@unittest.skipUnless(p.legacy.capability()["available"], "Linux resource limits required")
class ActualCpuProgramToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def proof(self, source, demos, name="verify"):
        return p.verify_program(source, demos, self.root, name, deadline=time.monotonic() + 15)

    def test_real_rotate_recolor_helpers_and_query(self):
        demos = [{"input": [[1, 0, 3], [0, 1, 0]], "output": [[0, 2], [2, 0], [0, 3]]},
                 {"input": [[1, 4]], "output": [[2], [4]]}]
        proof = self.proof(ROTATE_RECOLOR, demos)
        self.assertTrue(proof["all_demos_fit"], proof)
        result = p.execute_queries(proof, [[[1, 5], [2, 0]]], self.root, "query", deadline=time.monotonic() + 15)
        self.assertEqual(result["results"][0]["output"], [[2, 2], [0, 5]])
        self.assertTrue(result["owned_descendants_stopped"])
        self.assertGreater(result["results"][0]["process_pid"], 0)
        self.assertGreater(result["gas_charged"], 0)
        self.assertTrue(result["demo_replay_in_each_query"])

    def test_real_components_algorithm_beyond_finite_plan_templates(self):
        inp = [[1, 1, 0, 2], [1, 0, 0, 0], [0, 3, 3, 0]]
        out = [[9, 9, 0, 2], [9, 0, 0, 0], [0, 3, 3, 0]]
        proof = self.proof(COMPONENTS, [{"input": inp, "output": out}])
        self.assertTrue(proof["all_demos_fit"], proof)
        result = p.execute_queries(proof, [[[0, 4], [4, 4]]], self.root, "query")
        self.assertEqual(result["results"][0]["output"], [[0, 9], [9, 9]])

    def test_partial_fit_feedback_cannot_execute_queries(self):
        proof = self.proof(IDENTITY, [{"input": [[1]], "output": [[1]]}, {"input": [[2]], "output": [[3]]}])
        self.assertFalse(proof["all_demos_fit"])
        self.assertEqual(proof["partial_score"]["exact_demos"], 1)
        self.assertEqual(proof["errors"][0]["mismatch_samples"][0]["expected"], 3)
        with mock.patch.object(p.subprocess, "Popen") as launch:
            result = p.execute_queries(proof, [[[2]]], self.root, "query")
        launch.assert_not_called()
        self.assertIn("all-demo-fit", result["error"])

    def test_malformed_import_and_host_access_are_rejected(self):
        for index, source in enumerate(("def transform(:", "import os\ndef transform(grid):\n return grid\n",
                                         "def transform(grid):\n return open(1)\n",
                                         "def transform(grid):\n return grid.__class__\n")):
            proof = self.proof(source, [{"input": [[1]], "output": [[1]]}], "bad-%d" % index)
            self.assertFalse(proof["all_demos_fit"], proof)
            self.assertTrue(proof["errors"])

    def test_infinite_loop_is_real_gas_bounded(self):
        proof = self.proof("def transform(grid):\n    while True:\n        pass\n", [{"input": [[1]], "output": [[1]]}])
        self.assertFalse(proof["all_demos_fit"])
        self.assertEqual(proof["gas_charged"], 200000)
        self.assertTrue(proof["receipt"]["owned_descendants_stopped"])

    def test_proof_tampering_does_not_dispatch(self):
        original = self.proof(IDENTITY, [{"input": [[1]], "output": [[1]]}])
        altered = copy.deepcopy(original)
        altered["source"] = ROTATE_RECOLOR
        with mock.patch.object(p.subprocess, "Popen") as launch:
            result = p.execute_queries(altered, [[[1]]], self.root, "query")
        launch.assert_not_called()
        self.assertIn("binding", result["error"])

    def test_expired_deadlines_never_dispatch(self):
        with mock.patch.object(p.legacy, "verify") as verify:
            proof = p.verify_program(
                IDENTITY, [{"input": [[1]], "output": [[1]]}], self.root, "expired", deadline=time.monotonic() - 1)
        verify.assert_not_called()
        self.assertFalse(proof["all_demos_fit"])
        self.assertEqual(proof["gas_charged"], 0)
        good = self.proof(IDENTITY, [{"input": [[1]], "output": [[1]]}])
        with mock.patch.object(p.subprocess, "Popen") as launch:
            result = p.execute_queries(good, [[[2]], [[3]]], self.root, "query", deadline=time.monotonic() - 1)
        launch.assert_not_called()
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(all(row["status"] == "missing" for row in result["results"]))

    def test_query_timeout_kills_reaps_and_charges_unknown(self):
        proof = self.proof(IDENTITY, [{"input": [[1]], "output": [[1]]}])
        # Tight real deadline exercises admission or parent timeout, never mocks VM.
        result = p.execute_queries(proof, [[[2]]], self.root, "query", deadline=time.monotonic() + .001)
        self.assertTrue(result["owned_descendants_stopped"])
        self.assertIn(result["results"][0]["status"], {"missing", "valid"})
        self.assertLessEqual(result["gas_charged"], 200000)

    def test_consumed_call_identity_and_json_safe_receipts(self):
        proof = self.proof(IDENTITY, [{"input": [[1]], "output": [[1]]}])
        json.dumps(proof, allow_nan=False)
        with self.assertRaises(FileExistsError):
            self.proof(IDENTITY, [{"input": [[1]], "output": [[1]]}])

    def test_pins_and_truth_free_input_schema(self):
        p._pins()
        with self.assertRaises(ValueError):
            self.proof(IDENTITY, [{"input": [[1]], "output": [[1]], "gold": [[1]]}])
