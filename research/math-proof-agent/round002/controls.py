"""Engineering controls with scripted outputs; never a model efficacy result."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import digest, Lock, atomic_json
from controller import accepted, execute_arm, parse_candidate, solver_view
from lean_worker import statement_digest
from analyze import analyze
from evaluator import evaluate_selected, rational
from kaggle_run import reserve, notebook_identity


class Controls(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads(Path(__file__).with_name("protocol.json").read_text())
        self.protocol["status"] = "frozen"
        s = {"id": "control", "imports": ["Init"], "declaration": ": True", "fidelity": "human_checked"}
        # Pure scripted interface fixture; this is not an actual human review.
        s["sha256"] = statement_digest(s)
        self.problem = {"id": "control", "statement": s, "statement_sha256": s["sha256"],
                        "natural_language": "interface fixture", "answer_mode": "proof_only",
                        "human_review": {"status": "approved", "source": "SCRIPTED_TEST_ONLY"},
                        "gold_answer": "DO_NOT_LEAK", "reference_proof": "DO_NOT_LEAK", "rubric": "DO_NOT_LEAK"}

    def test_gold_view_excluded(self):
        self.assertNotIn("DO_NOT_LEAK", json.dumps(solver_view(self.problem)))

    def test_candidate_schema_injection_rejected(self):
        with self.assertRaises(ValueError):
            parse_candidate('{"answer":null,"proof_body":"by rfl","statement":"False"}')

    def test_blank_proof_rejected(self):
        with self.assertRaises(ValueError):
            parse_candidate('{"answer":null,"proof_body":" "}')

    def test_exit_zero_does_not_accept(self):
        self.assertFalse(accepted({"exit_code": 0}, self.problem))

    def test_binding_is_required(self):
        self.assertFalse(accepted({"proof_status": "kernel_verified", "trust_policy_passed": True,
                                   "statement_sha256": "wrong"}, self.problem))

    def test_atomic_lock(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lock"
            with Lock(p):
                with self.assertRaises(FileExistsError):
                    with Lock(p):
                        pass
            self.assertFalse(p.exists())

    def test_atomic_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.json"
            atomic_json(p, {"phase": "generating"})
            atomic_json(p, {"phase": "unknown"})
            self.assertEqual(json.loads(p.read_text()), {"phase": "unknown"})

    def test_first_smoke_budget(self):
        with self.assertRaises(ValueError):
            reserve({"runs": []}, {"timeout_seconds": 1801, "kind": "smoke"})

    def test_unknown_submission_blocks(self):
        with self.assertRaises(ValueError):
            reserve({"runs": [{"state": "submission_unknown", "timeout_seconds": 1800}]},
                    {"timeout_seconds": 100, "kind": "smoke"})

    def test_budget_never_refunded(self):
        state = {"runs": [{"state": "error", "timeout_seconds": 10800, "run_id": "a"},
                          {"state": "error", "timeout_seconds": 10800, "run_id": "b"}]}
        with self.assertRaises(ValueError):
            reserve(state, {"timeout_seconds": 1, "kind": "smoke", "run_id": "c"})

    def test_two_root_causes_stop(self):
        state = {"runs": [{"state": "error", "timeout_seconds": 1800, "run_id": "a", "root_cause": "quota"},
                          {"state": "error", "timeout_seconds": 1800, "run_id": "b", "root_cause": "quota"}]}
        with self.assertRaises(ValueError):
            reserve(state, {"timeout_seconds": 1800, "kind": "smoke", "run_id": "c"})

    def test_unfinished_denominator(self):
        result = analyze([self.problem], [], [0])
        for row in result["arms"].values():
            self.assertEqual(row["planned"], 1)
            self.assertEqual(row["counts"]["not_completed"], 1)
            self.assertIsNone(row["joint_rate"])

    def test_answer_given_not_joint(self):
        p = dict(self.problem, answer_mode="answer_given")
        result = analyze([p], [{"problem_id": p["id"], "arm": "M-SAMPLE", "seed": 0,
                                "status": "proof_accepted", "answer_status": "correct", "identities": {}}], [0], {})
        self.assertIsNone(result["arms"]["M-SAMPLE"]["joint_rate"])

    def test_duplicate_outcomes_rejected(self):
        r = {"problem_id": "control", "seed": 0, "arm": "M-DIRECT", "identities": {}}
        with self.assertRaises(ValueError):
            analyze([self.problem], [r, r], [0], {})

    def test_result_identity_required(self):
        with self.assertRaises(ValueError):
            analyze([self.problem], [{"problem_id": "control", "seed": 0, "arm": "M-DIRECT"}], [0])

    def test_answer_evaluator_no_execution(self):
        with self.assertRaises(ValueError):
            rational("__import__('os').system('echo bad')")
        rows = [{"problem_id": "x", "answer_mode": "find_answer", "events": [
            {"status": "accepted", "candidate": {"answer": "2/4"}}]}]
        result = evaluate_selected(rows, {"x": "1/2"})
        self.assertEqual(result[0]["answer_status"], "correct")
        self.assertNotIn("answer_status", rows[0])

    def test_real_interface_and_stop_on_success(self):
        prompts = []
        class Model:
            def generate(inner, prompt, **kwargs):
                prompts.append(prompt)
                return {"text": '{"answer":null,"proof_body":"by trivial"}',
                        "cost": {"prompt_tokens": 7, "output_tokens": 5}}
        class Verifier:
            def preflight(inner):
                return {"status": "passed"}
            def verify(inner, statement, body, deadline=None):
                return {"proof_status": "kernel_verified", "trust_policy_passed": True,
                        "statement_sha256": statement_digest(statement)}
        with tempfile.TemporaryDirectory() as d:
            result = execute_arm(self.problem, "M-REPAIR", 0, Model(), Verifier(), self.protocol,
                                 Path(d)/"result", {"protocol_sha256": digest(self.protocol)})
        self.assertEqual(result["status"], "proof_accepted")
        self.assertEqual(len(prompts), 1)
        self.assertNotIn("DO_NOT_LEAK", json.dumps(prompts))
        self.assertEqual(result["answer_status"], "not_applicable")

    def test_feedback_only_for_repair(self):
        seen = {}
        class Model:
            def generate(inner, prompt, **kwargs):
                seen.setdefault(arm, []).append(prompt)
                return {"text": '{"answer":null,"proof_body":"by rfl"}'}
        class Verifier:
            def preflight(inner): return {"status": "passed"}
            def verify(inner, statement, body, deadline=None):
                return {"status": "rejected", "execution": {"output": "TEST_FEEDBACK"}}
        with tempfile.TemporaryDirectory() as d:
            for arm in ("M-SAMPLE", "M-REPAIR"):
                execute_arm(self.problem, arm, 0, Model(), Verifier(), self.protocol, Path(d)/arm,
                            {"protocol_sha256": digest(self.protocol)})
        self.assertEqual(len(seen["M-SAMPLE"]), 4)
        self.assertEqual(len(seen["M-REPAIR"]), 4)
        self.assertNotIn("TEST_FEEDBACK", json.dumps(seen["M-SAMPLE"]))
        self.assertIn("TEST_FEEDBACK", json.dumps(seen["M-REPAIR"][1]))

    def test_notebook_transport_normalization(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"n.json"
            atomic_json(p, {"cells": [{"cell_type": "code", "source": ["a\n", "b"], "outputs": []}]})
            before = notebook_identity(p)
            atomic_json(p, {"cells": [{"cell_type": "code", "source": "a\nb", "outputs": ["transport"]}]})
            self.assertEqual(before, notebook_identity(p))


if __name__ == "__main__":
    unittest.main(verbosity=2)
