"""Scripted engineering controls; no model, Lean, TPU or human-review evidence."""
from __future__ import annotations
import copy
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import digest, file_digest, Lock, atomic_json
from controller import RUNTIME_SOURCES, accepted, execute_arm, parse_candidate, solver_view
from lean_worker import statement_digest
from model_adapter import ContextBudgetError, GenerationTimeout
from analyze import analyze
from evaluator import evaluate_selected, rational
from kaggle_run import reserve, notebook_identity

HERE = Path(__file__).resolve().parent
MODEL_ID = digest({"scripted_model": "identity-fixture-v1"})
VERIFIER_ID = digest({"scripted_verifier": "identity-fixture-v1"})


class ScriptedModel:
    """Records stub calls without instantiating a model runtime."""
    def __init__(self, response=None, error=None):
        self.prompts, self.kwargs, self.error = [], [], error
        self.response = response if response is not None else {
            "text": json.dumps({"answer": None, "proof_body": "by\n  trivial"}),
            "stop_reason": "eos", "cost": {"prompt_tokens": 7, "output_tokens": 5, "wall_seconds": 0.125}}

    def identity(self):
        return MODEL_ID

    def generate(self, prompt, **kwargs):
        self.prompts.append(copy.deepcopy(prompt))
        self.kwargs.append(kwargs)
        if self.error is not None:
            raise self.error
        return copy.deepcopy(self.response)


class ScriptedVerifier:
    """Exercises controller contracts without starting Lean."""
    def __init__(self, preflight=None, result=None):
        self.preflight_result = preflight if preflight is not None else {"status": "passed"}
        self.result, self.preflight_calls, self.calls = result, 0, []

    def identity(self):
        return VERIFIER_ID

    def preflight(self):
        self.preflight_calls += 1
        if isinstance(self.preflight_result, Exception):
            raise self.preflight_result
        return copy.deepcopy(self.preflight_result)

    def verify(self, statement, body, deadline=None):
        self.calls.append((copy.deepcopy(statement), body, deadline))
        if isinstance(self.result, Exception):
            raise self.result
        if self.result is not None:
            return copy.deepcopy(self.result)
        return {"status": "accepted", "accepted": True,
                "proof_status": "kernel_verified", "trust_policy_passed": True,
                "candidate_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "statement_sha256": statement_digest(statement)}


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip()

    def setUp(self):
        self.protocol = json.loads((HERE / "protocol.json").read_text())
        self.protocol["status"] = "frozen"
        s = {"id": "control", "imports": ["Init"], "declaration": ": True", "fidelity": "human_checked"}
        # Synthetic admission fixture only; never an actual statement-review claim.
        s["sha256"] = statement_digest(s)
        self.problem = {"id": "control", "statement": s, "statement_sha256": s["sha256"],
                        "natural_language": "SCRIPTED INTERFACE FIXTURE ONLY", "answer_mode": "proof_only",
                        "human_review": {"status": "approved", "source": "SCRIPTED_TEST_ONLY"},
                        "gold_answer": "DO_NOT_LEAK", "reference_proof": "DO_NOT_LEAK", "rubric": "DO_NOT_LEAK"}
        self.panel = [self.problem]
        self.source_files = {name: file_digest(HERE / name) for name in sorted(RUNTIME_SOURCES)}
        self.identities = self.bindings()
        self.manifest = self.execution_manifest()

    def bindings(self, *, panel=None, source_files=None):
        return {"format": "irisx.math.scoring-identity.v1", "code_sha": self.code_sha,
                "protocol_semantic_sha256": digest(self.protocol),
                "panel_semantic_sha256": digest(self.panel if panel is None else panel),
                "model_spec_sha256": MODEL_ID, "verifier_spec_sha256": VERIFIER_ID,
                "source_sha256": digest(self.source_files if source_files is None else source_files)}

    def execution_manifest(self, source_files=None):
        files = self.source_files if source_files is None else source_files
        return {"scoring": True, "code_sha": self.code_sha, "source_sha256": digest(files),
                "source_files": copy.deepcopy(files)}

    def execute(self, *, problem=None, panel=None, arm="M-DIRECT", seed=0, model=None, verifier=None,
                identities=None, source_files=None, execution_manifest=None):
        model = model if model is not None else ScriptedModel()
        verifier = verifier if verifier is not None else ScriptedVerifier()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result"
            result = execute_arm(self.problem if problem is None else problem, arm, seed, model, verifier,
                self.protocol, output, self.identities if identities is None else identities,
                panel=self.panel if panel is None else panel,
                source_files=self.source_files if source_files is None else source_files,
                execution_manifest=self.manifest if execution_manifest is None else execution_manifest)
            self.assertEqual(json.loads((output / "checkpoint.json").read_text()), result)
            for event in result["events"]:
                self.assertEqual(json.loads((output / f"candidate-{event['index']}.json").read_text()), event)
        return result, model, verifier

    def rejects_before_generation(self, **kwargs):
        model = ScriptedModel()
        with self.assertRaises(ValueError):
            self.execute(model=model, **kwargs)
        self.assertEqual(model.prompts, [])

    def selected_event(self, **kwargs):
        candidate = kwargs.pop("candidate", {"answer": None, "proof_body": "by trivial"})
        return dict({"status": "accepted", "candidate": candidate, "model_text": json.dumps(candidate),
                     "tool": {"status": "accepted", "accepted": True,
                              "proof_status": "kernel_verified", "trust_policy_passed": True,
                              "candidate_sha256": hashlib.sha256(candidate["proof_body"].encode()).hexdigest(),
                              "statement_sha256": self.problem["statement_sha256"]}}, **kwargs)

    def row(self, **kwargs):
        return dict({"problem_id": self.problem["id"], "arm": "M-DIRECT", "seed": 0,
                     "identities": copy.deepcopy(self.identities), "status": "budget_exhausted",
                     "statement_sha256": self.problem["statement_sha256"],
                     "answer_mode": "proof_only", "answer_status": "not_applicable",
                     "verifier_setup_seconds": 0.25, "wall_seconds": 1.0, "events": []}, **kwargs)

    def test_gold_view_excluded(self):
        self.assertNotIn("DO_NOT_LEAK", json.dumps(solver_view(self.problem)))

    def test_nested_gold_view_excluded_from_generation(self):
        self.problem["statement"].update(gold_answer="NESTED_SECRET", reference_proof="NESTED_SECRET",
                                         rubric={"answer": "NESTED_SECRET"})
        self.problem["human_review"]["private_reference"] = "NESTED_SECRET"
        result, model, _ = self.execute(identities=self.bindings())
        self.assertEqual(result["status"], "proof_accepted")
        self.assertNotIn("NESTED_SECRET", json.dumps(model.prompts))
        self.assertEqual(set(solver_view(self.problem)["statement"]),
                         {"id", "imports", "declaration", "fidelity", "sha256"})

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

    def test_missing_identity_fields_prevent_generation(self):
        for key in self.identities:
            with self.subTest(key=key):
                identity = dict(self.identities)
                del identity[key]
                self.rejects_before_generation(identities=identity)

    def test_mismatched_identity_fields_prevent_generation(self):
        for key in self.identities:
            with self.subTest(key=key):
                identity = dict(self.identities)
                identity[key] = "unexpected-format" if key == "format" else "f" * len(identity[key])
                self.rejects_before_generation(identities=identity)

    def test_source_bytes_mismatch_prevents_generation(self):
        files = dict(self.source_files, **{"controller.py": "0" * 64})
        self.rejects_before_generation(source_files=files, identities=self.bindings(source_files=files),
                                       execution_manifest=self.execution_manifest(files))

    def test_missing_runtime_source_prevents_generation(self):
        files = dict(self.source_files)
        del files["evaluator.py"]
        self.rejects_before_generation(source_files=files, identities=self.bindings(source_files=files),
                                       execution_manifest=self.execution_manifest(files))

    def test_smoke_manifest_cannot_authorize_scoring(self):
        self.rejects_before_generation(execution_manifest=dict(self.manifest, scoring=False))

    def test_foreign_panel_member_prevents_generation(self):
        foreign = copy.deepcopy(self.problem)
        foreign["natural_language"] = "Different provenance for the same identifier"
        self.rejects_before_generation(problem=foreign)

    def test_duplicate_panel_member_prevents_generation(self):
        panel = [self.problem, copy.deepcopy(self.problem)]
        self.rejects_before_generation(panel=panel, identities=self.bindings(panel=panel))

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
        result = analyze(self.panel, [], [0])
        for row in result["arms"].values():
            self.assertEqual(row["planned"], 1)
            self.assertEqual(row["counts"]["not_completed"], 1)
            self.assertIsNone(row["joint_rate"])
            self.assertFalse(row["cost_complete"])

    def test_answer_given_not_joint(self):
        problem = dict(self.problem, answer_mode="answer_given")
        identity = self.bindings(panel=[problem])
        row = self.row(arm="M-SAMPLE", status="proof_accepted", answer_mode="answer_given",
                       answer_status="correct", identities=identity, events=[self.selected_event()])
        result = analyze([problem], [row], [0], identity)
        self.assertIsNone(result["arms"]["M-SAMPLE"]["joint_rate"])

    def test_duplicate_outcomes_rejected(self):
        row = self.row()
        with self.assertRaises(ValueError):
            analyze(self.panel, [row, row], [0], self.identities)

    def test_result_identity_required(self):
        with self.assertRaises(ValueError):
            analyze(self.panel, [{"problem_id": "control", "seed": 0, "arm": "M-DIRECT"}], [0])

    def test_empty_analysis_identity_rejected(self):
        for expected, observed in (({}, {}), (self.identities, {})):
            with self.subTest(expected_complete=bool(expected)):
                with self.assertRaises(ValueError):
                    analyze(self.panel, [self.row(identities=observed)], [0], expected)
        with self.assertRaises(ValueError):
            analyze(self.panel, [], [0], {})

    def test_duplicate_analysis_panel_rejected(self):
        with self.assertRaises(ValueError):
            analyze(self.panel * 2, [], [0])

    def test_duplicate_analysis_seed_rejected(self):
        with self.assertRaises(ValueError):
            analyze(self.panel, [], [0, 0])

    def test_answer_evaluator_no_execution(self):
        with self.assertRaises(ValueError):
            rational("__import__('os').system('echo bad')")
        rows = [{"problem_id": "x", "answer_mode": "find_answer", "events": [
            {"status": "accepted", "candidate": {"answer": "2/4"}}]}]
        result = evaluate_selected(rows, {"x": "1/2"})
        self.assertEqual(result[0]["answer_status"], "correct")
        self.assertNotIn("answer_status", rows[0])

    def test_real_interface_and_stop_on_success(self):
        result, model, verifier = self.execute(arm="M-REPAIR")
        self.assertEqual(result["status"], "proof_accepted")
        self.assertEqual(len(model.prompts), 1)
        self.assertEqual(len(verifier.calls), 1)
        self.assertNotIn("DO_NOT_LEAK", json.dumps(model.prompts))
        self.assertEqual(result["answer_status"], "not_applicable")
        self.assertEqual(verifier.calls[0][2], model.kwargs[0]["deadline"])

    def test_feedback_only_for_repair(self):
        seen = {}
        for arm in ("M-SAMPLE", "M-REPAIR"):
            result, model, verifier = self.execute(arm=arm, verifier=ScriptedVerifier(
                result={"status": "rejected", "execution": {"output": "TEST_FEEDBACK"}}))
            seen[arm] = model.prompts
            self.assertEqual(result["status"], "budget_exhausted")
            self.assertEqual(len(verifier.calls), 4)
        self.assertEqual(len(seen["M-SAMPLE"]), 4)
        self.assertEqual(len(seen["M-REPAIR"]), 4)
        self.assertNotIn("TEST_FEEDBACK", json.dumps(seen["M-SAMPLE"]))
        self.assertIn("TEST_FEEDBACK", json.dumps(seen["M-REPAIR"][1]))

    def test_preflight_blocked_persists_cost_and_checkpoint(self):
        for preflight in ({"status": "blocked", "reason": "CONTROL"}, RuntimeError("CONTROL")):
            with self.subTest(preflight_type=type(preflight).__name__):
                with mock.patch("controller.time.monotonic", side_effect=itertools.count(10, 0.25)):
                    result, model, verifier = self.execute(verifier=ScriptedVerifier(preflight=preflight))
                self.assertEqual(result["status"], "infrastructure_blocked")
                self.assertEqual(result["verifier_setup_seconds"], 0.25)
                self.assertEqual(result["wall_seconds"], 0.0)
                self.assertEqual(model.prompts, [])
                self.assertEqual(verifier.calls, [])
                costs = analyze(self.panel, [result], [0], self.identities)["arms"]["M-DIRECT"]["observed_execution_cost"]
                self.assertEqual(costs["verifier_setup_seconds"], 0.25)

    def test_deadline_stop_reason_precedes_malformed_json(self):
        model = ScriptedModel(response={"text": '{"answer":', "stop_reason": "deadline",
                                        "cost": {"prompt_tokens": 9, "output_tokens": 2, "wall_seconds": 1.5}})
        result, _, verifier = self.execute(model=model)
        self.assertEqual(result["events"][0]["status"], "timeout")
        self.assertEqual(result["events"][0]["stop_reason"], "deadline")
        self.assertEqual(result["events"][0]["model_cost"]["output_tokens"], 2)
        self.assertEqual(verifier.calls, [])

    def test_malformed_json_without_deadline_is_parse_failure(self):
        result, _, verifier = self.execute(model=ScriptedModel(response={"text": "{", "cost": {"output_tokens": 1}}))
        self.assertEqual(result["events"][0]["status"], "invalid_format")
        self.assertFalse(result["events"][0]["model_cost_complete"])
        self.assertEqual(verifier.calls, [])

    def test_context_budget_error_stops_without_futile_retry(self):
        result, model, verifier = self.execute(arm="M-REPAIR", model=ScriptedModel(error=ContextBudgetError("CONTROL")))
        self.assertEqual(result["status"], "context_budget_exceeded")
        self.assertEqual(result["events"][0]["status"], "context_budget_exceeded")
        self.assertEqual(len(model.prompts), 1)
        self.assertEqual(verifier.calls, [])

    def test_generation_value_error_is_infrastructure_not_parse(self):
        result, model, verifier = self.execute(arm="M-SAMPLE", model=ScriptedModel(error=ValueError("CONTROL")))
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertEqual(result["events"][0]["status"], "infrastructure_error")
        self.assertEqual(len(model.prompts), 1)
        self.assertEqual(verifier.calls, [])

    def test_partial_timeout_receipt_preserved(self):
        cost = {"prompt_tokens": 17, "output_tokens": 2, "wall_seconds": 0.75, "partial": True}
        error = GenerationTimeout("CONTROL", cost=cost, phase="decode")
        result, _, verifier = self.execute(model=ScriptedModel(error=error))
        event = result["events"][0]
        self.assertEqual(event["status"], "timeout")
        self.assertEqual(event["model_cost"], cost)
        self.assertFalse(event["model_cost_complete"])
        self.assertEqual(verifier.calls, [])
        summary = analyze(self.panel, [result], [0], self.identities)["arms"]["M-DIRECT"]
        self.assertEqual(summary["observed_model_cost_lower_bound"]["prompt_tokens"], 17)
        self.assertNotIn("partial", summary["observed_model_cost_lower_bound"])
        self.assertFalse(summary["cost_complete"])

    def test_model_tool_setup_arm_costs_and_missing_lower_bound(self):
        row = self.row(wall_seconds=2.5, events=[
            {"model_cost_complete": True, "model_cost": {"prompt_tokens": 7, "output_tokens": 5, "wall_seconds": 0.5},
             "tool_attempted": True, "tool_wall_seconds": 0.2},
            {"model_cost_complete": False, "model_cost": {"prompt_tokens": 3, "output_tokens": 2, "partial": True},
             "tool_attempted": True}])
        result = analyze(self.panel, [row], [0], self.identities)
        summary = result["arms"]["M-DIRECT"]
        self.assertEqual(summary["observed_model_cost_lower_bound"],
                         {"prompt_tokens": 10, "output_tokens": 7, "wall_seconds": 0.5})
        cost = summary["observed_execution_cost"]
        for name, value in {"verifier_setup_seconds": 0.25, "wall_seconds": 2.5, "generation_attempts": 2,
                            "incomplete_model_cost_receipts": 1, "tool_calls": 2,
                            "tool_wall_seconds": 0.2, "tool_wall_missing_calls": 1}.items():
            self.assertEqual(cost[name], value)
        self.assertFalse(summary["cost_complete"])
        missing = result["arms"]["M-SAMPLE"]["observed_execution_cost"]
        self.assertEqual(missing["wall_seconds_missing_rows"], 1)
        self.assertEqual(missing["verifier_setup_seconds_missing_rows"], 1)

    def test_complete_cost_receipt_is_distinct_from_missing(self):
        result, _, _ = self.execute()
        summary = analyze(self.panel, [result], [0], self.identities)["arms"]["M-DIRECT"]
        self.assertTrue(summary["cost_complete"])
        self.assertEqual(summary["observed_execution_cost"]["tool_calls"], 1)

    def test_correct_answer_and_unrelated_accepted_proof_never_joint(self):
        problem = dict(self.problem, answer_mode="find_answer")
        identity = self.bindings(panel=[problem])
        # The accepted proof certifies the fixed True proposition, unrelated to the separate answer.
        event = self.selected_event(candidate={"answer": "2/4", "proof_body": "by trivial"})
        row = self.row(status="proof_accepted", answer_mode="find_answer", answer_status="correct",
                       joint_status="success", identities=identity, events=[event])
        evaluated = evaluate_selected([row], {"control": "1/2"})
        self.assertEqual(evaluated[0]["answer_status"], "correct")
        self.assertEqual(evaluated[0]["joint_status"], "unqualified")
        # R1 strengthens analysis admission too: an unsupported find-answer
        # success cannot keep a pure-proof receipt and enter any success count.
        with self.assertRaises(ValueError):
            analyze([problem], evaluated, [0], identity)

    def test_unrelated_verifier_receipt_cannot_establish_proof_success(self):
        event = self.selected_event()
        event["tool"]["statement_sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            analyze(self.panel, [self.row(status="proof_accepted", events=[event])], [0], self.identities)

    def test_find_answer_blocks_before_generation(self):
        problem = dict(self.problem, answer_mode="find_answer")
        result, model, verifier = self.execute(problem=problem, panel=[problem],
                                               identities=self.bindings(panel=[problem]))
        self.assertEqual(result["status"], "infrastructure_blocked")
        self.assertEqual(result["reason"], "answer_proof_binding_unqualified")
        self.assertEqual(result["joint_status"], "unqualified")
        self.assertEqual(model.prompts, [])
        self.assertEqual(verifier.calls, [])

    def test_pure_proof_cannot_supply_an_answer(self):
        model = ScriptedModel(response={"text": json.dumps({"answer": "1", "proof_body": "by trivial"})})
        result, _, verifier = self.execute(model=model)
        self.assertEqual(result["events"][0]["status"], "invalid_format")
        self.assertEqual(verifier.calls, [])

    def test_preflight_block_without_generation_has_no_model_rate(self):
        row, model, _ = self.execute(verifier=ScriptedVerifier(preflight={"status": "blocked"}))
        self.assertEqual(row["events"], [])
        self.assertEqual(model.prompts, [])
        result = analyze(self.panel, [row], [0, 1], self.identities)
        summary = result["arms"]["M-DIRECT"]
        self.assertEqual(summary["planned"], 2)
        self.assertEqual(summary["counts"]["infrastructure_blocked"], 1)
        self.assertEqual(summary["counts"]["not_completed"], 1)
        self.assertEqual(summary["counts"]["generation_observed_rows"], 0)
        self.assertIsNone(summary["proof_rate"])
        self.assertEqual(result["conclusion"], "not_estimable")

    def test_context_event_without_generation_has_no_model_rate(self):
        row, _, _ = self.execute(model=ScriptedModel(error=ContextBudgetError("CONTROL")))
        self.assertEqual(len(row["events"]), 1)
        self.assertNotIn("model_text", row["events"][0])
        result = analyze(self.panel, [row], [0], self.identities)
        summary = result["arms"]["M-DIRECT"]
        self.assertEqual(summary["planned"], 1)
        self.assertEqual(summary["counts"]["context_budget_exceeded"], 1)
        self.assertEqual(summary["counts"]["generation_observed_rows"], 0)
        self.assertEqual(summary["observed_execution_cost"]["generation_attempts"], 1)
        self.assertIsNone(summary["proof_rate"])
        self.assertEqual(result["conclusion"], "not_estimable")

    def test_consumed_prompt_timeout_is_limited_generation_observation(self):
        receipt = {"prompt_tokens": 17, "consumed_prompt_tokens": 13,
                   "output_tokens": 0, "wall_seconds": 0.75, "partial": True}
        error = GenerationTimeout("CONTROL", cost=receipt, phase="prefill")
        row, _, _ = self.execute(model=ScriptedModel(error=error))
        self.assertNotIn("model_text", row["events"][0])
        self.assertEqual(row["events"][0]["status"], "timeout")
        result = analyze(self.panel, [row], [0, 1], self.identities)
        summary = result["arms"]["M-DIRECT"]
        self.assertEqual(summary["planned"], 2)
        self.assertEqual(summary["counts"]["generation_observed_rows"], 1)
        self.assertEqual(summary["counts"]["not_completed"], 1)
        self.assertEqual(summary["proof_rate"], 0.0)
        self.assertEqual(summary["observed_model_cost_lower_bound"]["consumed_prompt_tokens"], 13)
        self.assertFalse(summary["cost_complete"])
        self.assertIsNone(result["arms"]["M-SAMPLE"]["proof_rate"])
        self.assertEqual(result["conclusion"], "descriptive_pilot_only")

    def test_notebook_transport_normalization(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"n.json"
            atomic_json(p, {"cells": [{"cell_type": "code", "source": ["a\n", "b"], "outputs": []}]})
            before = notebook_identity(p)
            atomic_json(p, {"cells": [{"cell_type": "code", "source": "a\nb", "outputs": ["transport"]}]})
            self.assertEqual(before, notebook_identity(p))


if __name__ == "__main__":
    unittest.main(verbosity=2)
