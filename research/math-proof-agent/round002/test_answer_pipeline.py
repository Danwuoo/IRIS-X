"""Scripted answer-pipeline controls; never model or mathematical efficacy evidence.

The numerical fixtures are authored interface cases, not benchmark problems.
No model runtime, Lean process, source data or external service is invoked.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import digest, file_digest
from controller import RUNTIME_SOURCES, execute_arm
from controls import ScriptedModel, ScriptedVerifier, MODEL_ID, VERIFIER_ID
from lean_worker import statement_digest, answer_binding_digest, answer_candidate_digest, normalized_answer_sha256
from analyze import analyze
from evaluator import evaluate_selected

HERE = Path(__file__).resolve().parent
BODY = "by\n  norm_num"


def response(answer):
    return {"text": json.dumps({"answer": answer, "proof_body": BODY}), "stop_reason": "eos",
            "cost": {"prompt_tokens": 11, "consumed_prompt_tokens": 11,
                     "output_tokens": 7, "wall_seconds": 0.125}}


def make_answer_receipt(statement, answer, proof_body, spec):
    """Construct the worker contract with fixed scripted outcomes, not a proof."""
    try:
        candidate_sha = answer_candidate_digest(answer, proof_body)
        spec_sha = answer_binding_digest(spec)
    except ValueError:
        return {"status": "invalid_format", "proof_status": "unsupported", "trust_policy_passed": False,
                "statement_sha256": statement_digest(statement)}
    result = {"status": "rejected", "accepted": False, "proof_status": "incomplete", "trust_policy_passed": False,
              "statement_sha256": statement_digest(statement), "candidate_sha256": candidate_sha}
    if answer == "2":
        result.update(status="accepted", accepted=True, proof_status="kernel_verified", trust_policy_passed=True,
                      answer_binding={"kind": "closed_exists_nat_v1", "status": "kernel_verified",
                                      "statement_sha256": statement_digest(statement), "spec_sha256": spec_sha,
                                      "candidate_sha256": candidate_sha,
                                      "normalized_answer_sha256": normalized_answer_sha256(answer)})
    return result


class SequenceModel(ScriptedModel):
    def __init__(self, answers):
        super().__init__()
        self.answers = list(answers)

    def generate(self, prompt, **kwargs):
        self.prompts.append(copy.deepcopy(prompt))
        self.kwargs.append(kwargs)
        if len(self.prompts) > len(self.answers):
            raise RuntimeError("controller exceeded the scripted proposal sequence")
        return response(self.answers[len(self.prompts) - 1])


class AnswerVerifier(ScriptedVerifier):
    def __init__(self, spec, transform=None):
        super().__init__()
        self.spec = copy.deepcopy(spec)
        self.transform = transform
        self.answer_calls = []

    def answer_binding_spec(self, identifier):
        return copy.deepcopy(self.spec)

    def verify_answer(self, statement, answer, proof_body, deadline=None):
        self.answer_calls.append((copy.deepcopy(statement), answer, proof_body, deadline))
        result = make_answer_receipt(statement, answer, proof_body, self.spec)
        return self.transform(result) if self.transform is not None else result


class AnswerPipelineControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip()

    def setUp(self):
        self.protocol = json.loads((HERE / "protocol.json").read_text())
        self.protocol["status"] = "frozen"
        statement = {"id": "answer_pipeline_fixture", "imports": ["Init"],
                     "declaration": ": ∃ n : Nat, n + 1 = 3", "fidelity": "human_checked"}
        # Test-only admission record. No actual human review or benchmark fidelity is claimed.
        statement["sha256"] = statement_digest(statement)
        self.spec = {"kind": "closed_exists_nat_v1", "statement_sha256": statement["sha256"],
                     "review_ref": "SCRIPTED_TEST_ONLY", "answer_mode": "find_answer"}
        self.problem = {"id": statement["id"], "statement": statement, "statement_sha256": statement["sha256"],
                        "natural_language": "Authored scripted answer-pipeline interface fixture only.",
                        "answer_mode": "find_answer", "answer_binding": copy.deepcopy(self.spec),
                        "human_review": {"status": "approved", "source": "SCRIPTED_TEST_ONLY"},
                        "gold_answer": "PRIVATE_GOLD_SENTINEL", "rubric": "PRIVATE_GOLD_SENTINEL",
                        "reference_proof": "PRIVATE_GOLD_SENTINEL"}
        self.source_files = {name: file_digest(HERE / name) for name in sorted(RUNTIME_SOURCES)}

    def bindings(self, problem):
        return {"format": "irisx.math.scoring-identity.v1", "code_sha": self.code_sha,
                "protocol_semantic_sha256": digest(self.protocol), "panel_semantic_sha256": digest([problem]),
                "model_spec_sha256": MODEL_ID, "verifier_spec_sha256": VERIFIER_ID,
                "source_sha256": digest(self.source_files)}

    def run_arm(self, *, problem=None, model=None, verifier=None, arm="M-DIRECT", seed=0):
        problem = self.problem if problem is None else problem
        model = SequenceModel(["2"]) if model is None else model
        verifier = AnswerVerifier(self.spec) if verifier is None else verifier
        identities = self.bindings(problem)
        manifest = {"scoring": True, "code_sha": self.code_sha, "source_sha256": digest(self.source_files),
                    "source_files": copy.deepcopy(self.source_files)}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "arm"
            row = execute_arm(problem, arm, seed, model, verifier, self.protocol, output, identities,
                              panel=[problem], source_files=self.source_files, execution_manifest=manifest)
            self.assertEqual(json.loads((output / "checkpoint.json").read_text()), row)
            for event in row["events"]:
                self.assertEqual(json.loads((output / f"candidate-{event['index']}.json").read_text()), event)
        return row, model, verifier

    def summarize(self, rows, *, problem=None, seeds=(0,)):
        problem = self.problem if problem is None else problem
        return analyze([problem], rows, list(seeds), self.bindings(problem))

    def test_correct_bound_candidate_joint_and_stop_at_first_success(self):
        row, model, verifier = self.run_arm(arm="M-REPAIR", model=SequenceModel(["2", "1", "1", "1"]))
        self.assertEqual(row["status"], "proof_accepted")
        self.assertEqual(row["joint_status"], "kernel_verified")
        self.assertEqual(row["answer_status"], "correct")
        self.assertEqual(len(model.prompts), 1)
        self.assertEqual(len(verifier.answer_calls), 1)
        self.assertEqual(verifier.calls, [])
        evaluated = evaluate_selected([row], panel=[self.problem])
        self.assertEqual(evaluated[0]["joint_status"], "kernel_verified")
        summary = self.summarize(evaluated)["arms"]["M-REPAIR"]
        self.assertEqual(summary["joint_rate"], 1.0)
        self.assertEqual(summary["proof_rate"], 1.0)

    def test_wrong_answer_rejected_and_not_joint(self):
        row, _, verifier = self.run_arm(model=SequenceModel(["1"]))
        self.assertNotEqual(row["status"], "proof_accepted")
        self.assertEqual(row["events"][0]["status"], "rejected")
        self.assertEqual(len(verifier.answer_calls), 1)
        evaluated = evaluate_selected([row], panel=[self.problem])
        self.assertNotEqual(evaluated[0]["joint_status"], "kernel_verified")
        self.assertEqual(self.summarize(evaluated)["arms"]["M-DIRECT"]["joint_rate"], 0.0)

    def test_unrelated_statement_receipt_not_accepted(self):
        def unrelated(receipt):
            receipt["statement_sha256"] = "f" * 64
            return receipt
        row, _, _ = self.run_arm(verifier=AnswerVerifier(self.spec, unrelated))
        self.assertNotEqual(row["status"], "proof_accepted")
        self.assertNotEqual(row["events"][0]["status"], "accepted")
        self.assertNotEqual(row["joint_status"], "kernel_verified")

    def test_altered_answer_invalidates_saved_joint_receipt(self):
        row, _, _ = self.run_arm()
        row["events"][0]["candidate"]["answer"] = "3"
        evaluated = evaluate_selected([row], panel=[self.problem])
        self.assertNotEqual(evaluated[0]["joint_status"], "kernel_verified")
        with self.assertRaises(ValueError):
            self.summarize([row])

    def test_altered_proof_invalidates_saved_joint_receipt(self):
        row, _, _ = self.run_arm()
        row["events"][0]["candidate"]["proof_body"] = BODY + "\n  trivial"
        evaluated = evaluate_selected([row], panel=[self.problem])
        self.assertNotEqual(evaluated[0]["joint_status"], "kernel_verified")
        with self.assertRaises(ValueError):
            self.summarize([row])

    def test_missing_or_mixed_answer_receipt_does_not_joint(self):
        for field in ("kind", "status", "statement_sha256", "spec_sha256", "candidate_sha256", "normalized_answer_sha256"):
            with self.subTest(field=field):
                def damaged(receipt):
                    receipt["answer_binding"][field] = "unrelated"
                    return receipt
                row, _, _ = self.run_arm(verifier=AnswerVerifier(self.spec, damaged))
                self.assertNotEqual(row["status"], "proof_accepted")
                self.assertNotEqual(row["joint_status"], "kernel_verified")

    def test_unsupported_binding_blocks_before_generation(self):
        cases = [None, dict(self.spec, kind="real_answer_v1"), dict(self.spec, review_ref=""),
                 dict(self.spec, review_ref="  "), dict(self.spec, review_ref="x" * 1025),
                 dict(self.spec, statement_sha256="f" * 64), dict(self.spec, unexpected="extra")]
        for spec in cases:
            with self.subTest(spec=spec):
                problem = copy.deepcopy(self.problem)
                problem["answer_binding"] = spec
                row, model, verifier = self.run_arm(problem=problem, verifier=AnswerVerifier(spec))
                self.assertEqual(row["status"], "infrastructure_blocked")
                self.assertEqual(model.prompts, [])
                self.assertEqual(verifier.answer_calls, [])

    def test_worker_and_panel_binding_must_match_before_generation(self):
        row, model, verifier = self.run_arm(verifier=AnswerVerifier(dict(self.spec, review_ref="OTHER_FIXTURE")))
        self.assertEqual(row["status"], "infrastructure_blocked")
        self.assertEqual(model.prompts, [])
        self.assertEqual(verifier.answer_calls, [])

    def test_unsupported_original_declaration_blocks_before_generation(self):
        declarations = [": ∃ n : Rat, n + 1 = 3", "(h : True) : ∃ n : Nat, n + 1 = 3",
                        ": ∃! n : Nat, n + 1 = 3", ": Exists (fun n : Nat => n + 1 = 3)",
                        ": ∃ n : Nat, ∃ m : Nat, n + m = 3"]
        for declaration in declarations:
            with self.subTest(declaration=declaration):
                problem = copy.deepcopy(self.problem)
                problem["statement"]["declaration"] = declaration
                statement_sha = statement_digest(problem["statement"])
                problem["statement"]["sha256"] = statement_sha
                problem["statement_sha256"] = statement_sha
                problem["answer_binding"]["statement_sha256"] = statement_sha
                row, model, verifier = self.run_arm(problem=problem, verifier=AnswerVerifier(problem["answer_binding"]))
                self.assertEqual(row["status"], "infrastructure_blocked")
                self.assertEqual(model.prompts, [])
                self.assertEqual(verifier.answer_calls, [])

    def test_answer_given_never_counts_joint(self):
        problem = dict(self.problem, answer_mode="answer_given")
        problem.pop("answer_binding")
        row, _, verifier = self.run_arm(problem=problem, verifier=ScriptedVerifier())
        self.assertEqual(row["status"], "proof_accepted")
        self.assertEqual(len(verifier.calls), 1)
        self.assertFalse(hasattr(verifier, "answer_calls"))
        evaluated = evaluate_selected([row], {problem["id"]: "2"}, panel=[problem])
        self.assertEqual(evaluated[0]["joint_status"], "not_applicable")
        self.assertIsNone(self.summarize(evaluated, problem=problem)["arms"]["M-DIRECT"]["joint_rate"])

    def test_pure_proof_path_unchanged(self):
        problem = dict(self.problem, answer_mode="proof_only")
        problem.pop("answer_binding")
        row, _, verifier = self.run_arm(problem=problem, model=SequenceModel([None]), verifier=ScriptedVerifier())
        self.assertEqual(row["status"], "proof_accepted")
        self.assertEqual(row["answer_status"], "not_applicable")
        self.assertEqual(len(verifier.calls), 1)
        self.assertFalse(hasattr(verifier, "answer_calls"))
        self.assertIsNone(self.summarize([row], problem=problem)["arms"]["M-DIRECT"]["joint_rate"])

    def test_nested_gold_and_binding_metadata_not_in_prompts(self):
        self.problem["statement"].update(gold_answer="NESTED_GOLD_SENTINEL", reference_proof="NESTED_GOLD_SENTINEL")
        self.problem["human_review"]["rubric"] = "NESTED_GOLD_SENTINEL"
        self.spec["review_ref"] = "PRIVATE_REVIEW_SENTINEL"
        self.problem["answer_binding"] = copy.deepcopy(self.spec)
        row, model, _ = self.run_arm()
        self.assertEqual(row["status"], "proof_accepted")
        for secret in ("PRIVATE_GOLD_SENTINEL", "NESTED_GOLD_SENTINEL", "PRIVATE_REVIEW_SENTINEL"):
            self.assertNotIn(secret, json.dumps(model.prompts))

    def test_failed_and_not_reached_items_stay_in_joint_denominator(self):
        row, _, _ = self.run_arm(model=SequenceModel(["1"]))
        summary = self.summarize([row], seeds=(0, 1))["arms"]["M-DIRECT"]
        self.assertEqual(summary["planned"], 2)
        self.assertEqual(summary["counts"]["joint_denominator"], 2)
        self.assertEqual(summary["counts"]["not_completed"], 1)
        self.assertEqual(summary["joint_rate"], 0.0)
        self.assertEqual(summary["proof_rate"], 0.0)

    def test_private_key_disagreement_blocks_joint(self):
        row, model, _ = self.run_arm()
        evaluated = evaluate_selected([row], {self.problem["id"]: "9"}, panel=[self.problem])
        self.assertEqual(evaluated[0]["answer_status"], "inconsistent_evaluator_key")
        self.assertEqual(evaluated[0]["joint_status"], "blocked_key_disagreement")
        self.assertEqual(len(model.prompts), 1)
        summary = self.summarize(evaluated)["arms"]["M-DIRECT"]
        self.assertIsNone(summary["joint_rate"])

    def test_proposal_ceiling_is_one_four_four(self):
        for arm, count in (("M-DIRECT", 1), ("M-SAMPLE", 4), ("M-REPAIR", 4)):
            with self.subTest(arm=arm):
                row, model, verifier = self.run_arm(arm=arm, model=SequenceModel(["1"] * count))
                self.assertEqual(row["status"], "budget_exhausted")
                self.assertEqual(len(model.prompts), count)
                self.assertEqual(len(verifier.answer_calls), count)
                self.assertEqual(len(row["events"]), count)

    def test_first_bound_success_after_failure_stops_without_key_selection(self):
        row, model, _ = self.run_arm(arm="M-SAMPLE", model=SequenceModel(["1", "2", "1", "1"]))
        self.assertEqual(row["status"], "proof_accepted")
        self.assertEqual(len(model.prompts), 2)
        self.assertEqual([event["status"] for event in row["events"]], ["rejected", "accepted"])
        self.assertEqual(evaluate_selected([row], panel=[self.problem])[0]["joint_status"], "kernel_verified")

    def test_status_accepted_cannot_bypass_false_trust_or_wrong_statement(self):
        for mode in ("proof_only", "find_answer"):
            for defect in ("trust_policy_passed", "statement_sha256"):
                with self.subTest(mode=mode, defect=defect):
                    def damaged(receipt):
                        receipt["status"] = "accepted"
                        receipt[defect] = False if defect == "trust_policy_passed" else "f" * 64
                        return receipt
                    problem = dict(self.problem, answer_mode=mode)
                    if mode == "find_answer":
                        verifier = AnswerVerifier(self.spec, damaged)
                    else:
                        receipt = {"status": "accepted", "proof_status": "kernel_verified", "trust_policy_passed": True,
                                   "statement_sha256": self.problem["statement_sha256"]}
                        verifier = ScriptedVerifier(result=damaged(receipt))
                    row, _, _ = self.run_arm(problem=problem, model=SequenceModel([None if mode == "proof_only" else "2"]),
                                             verifier=verifier)
                    self.assertNotEqual(row["status"], "proof_accepted")
                    self.assertNotEqual(row["events"][0]["status"], "accepted")

    def test_noncanonical_nat_answers_never_joint(self):
        for answer in ("02", "-1", "2/1", " 2", "0x2"):
            with self.subTest(answer=answer):
                row, _, _ = self.run_arm(model=SequenceModel([answer]))
                self.assertNotEqual(row["status"], "proof_accepted")
                self.assertNotEqual(row["joint_status"], "kernel_verified")

    def test_both_blocked_pairs_are_not_ties(self):
        for mode in ("proof_only", "find_answer"):
            with self.subTest(mode=mode):
                problem = dict(self.problem, answer_mode=mode)
                if mode == "proof_only":
                    problem.pop("answer_binding")
                rows = []
                for arm in ("M-SAMPLE", "M-REPAIR"):
                    row, model, _ = self.run_arm(problem=problem, arm=arm,
                        verifier=ScriptedVerifier(preflight={"status": "blocked"}))
                    self.assertEqual(model.prompts, [])
                    self.assertEqual(row["events"], [])
                    rows.append(row)
                result = self.summarize(rows, problem=problem)
                self.assertEqual(result["paired"], {"no_generation_pair": 1})
                self.assertEqual(result["paired_joint"], {"no_generation_pair": 1} if mode == "find_answer" else {})
                self.assertEqual(result["conclusion"], "not_estimable")
                for arm in ("M-SAMPLE", "M-REPAIR"):
                    summary = result["arms"][arm]
                    self.assertEqual(summary["planned"], 1)
                    self.assertEqual(summary["counts"]["infrastructure_blocked"], 1)
                    self.assertIsNone(summary["proof_rate"])
                    self.assertIsNone(summary["joint_rate"])
                    if mode == "find_answer":
                        self.assertEqual(summary["counts"]["joint_denominator"], 1)

    def test_accepted_versus_blocked_pair_is_not_gain_or_loss(self):
        for mode in ("proof_only", "find_answer"):
            for accepted_arm in ("M-SAMPLE", "M-REPAIR"):
                with self.subTest(mode=mode, accepted_arm=accepted_arm):
                    problem = dict(self.problem, answer_mode=mode)
                    if mode == "proof_only":
                        problem.pop("answer_binding")
                    verifier = AnswerVerifier(self.spec) if mode == "find_answer" else ScriptedVerifier()
                    accepted_row, _, _ = self.run_arm(problem=problem, arm=accepted_arm, verifier=verifier,
                        model=SequenceModel(["2" if mode == "find_answer" else None]))
                    self.assertEqual(accepted_row["status"], "proof_accepted")
                    blocked_arm = "M-REPAIR" if accepted_arm == "M-SAMPLE" else "M-SAMPLE"
                    blocked_row, model, _ = self.run_arm(problem=problem, arm=blocked_arm,
                        verifier=ScriptedVerifier(preflight={"status": "blocked"}))
                    self.assertEqual(model.prompts, [])
                    result = self.summarize([accepted_row, blocked_row], problem=problem)
                    self.assertEqual(result["paired"], {"no_generation_pair": 1})
                    self.assertEqual(result["paired_joint"], {"no_generation_pair": 1} if mode == "find_answer" else {})
                    self.assertEqual(result["arms"][accepted_arm]["proof_rate"], 1.0)
                    self.assertIsNone(result["arms"][blocked_arm]["proof_rate"])
                    for arm in ("M-SAMPLE", "M-REPAIR"):
                        self.assertEqual(result["arms"][arm]["planned"], 1)
                        if mode == "find_answer":
                            self.assertEqual(result["arms"][arm]["counts"]["joint_denominator"], 1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
