"""M002-R1 scripted receipt-integrity controls; no model, provider or Lean calls.

These authored constants exercise serialization and trust-receipt contracts.
They are neither an admitted panel nor mathematical/model efficacy evidence.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluator import (bound_answer_matches, verified_event_matches,
                       verified_receipt_matches)
from analyze import analyze
from common import digest
from controller import accepted
from lean_worker import (answer_binding_digest, answer_candidate_digest,
                         normalized_answer_sha256, statement_digest)


MODES = ("proof_only", "answer_given", "find_answer")
BODY = "by\n  rfl"


def fixture(mode):
    statement = {"id": "receipt_fixture", "imports": ["Init"],
                 "declaration": ": ∃ n : Nat, n = 2" if mode == "find_answer" else ": (2 : Nat) = 2",
                 "fidelity": "authored_engineering_control"}
    statement["sha256"] = statement_digest(statement)
    problem = {"id": statement["id"], "answer_mode": mode,
               "statement": statement, "statement_sha256": statement["sha256"]}
    candidate = {"answer": None if mode == "proof_only" else "2", "proof_body": BODY}
    result = {"status": "accepted", "accepted": True,
              "proof_status": "kernel_verified", "trust_policy_passed": True,
              "statement_sha256": statement["sha256"],
              "candidate_sha256": hashlib.sha256(BODY.encode("utf-8")).hexdigest()}
    if mode == "find_answer":
        spec = {"kind": "closed_exists_nat_v1", "answer_mode": "find_answer",
                "statement_sha256": statement["sha256"],
                "review_ref": "engineering:receipt_integrity_scripted_fixture"}
        problem["answer_binding"] = spec
        digest = answer_candidate_digest(candidate["answer"], candidate["proof_body"])
        result.update(candidate_sha256=digest, answer_binding={
            "kind": "closed_exists_nat_v1", "status": "kernel_verified",
            "statement_sha256": statement["sha256"], "spec_sha256": answer_binding_digest(spec),
            "candidate_sha256": digest,
            "normalized_answer_sha256": normalized_answer_sha256(candidate["answer"])})
    return problem, {"status": "accepted", "candidate": candidate,
                     "model_text": json.dumps(candidate), "tool": result}


class ReceiptBindingControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (os.environ.get("PYTHONHASHSEED") != "0" or sys.flags.ignore_environment
                or sys.flags.hash_randomization != 0 or not sys.flags.safe_path
                or not sys.flags.no_user_site or not sys.dont_write_bytecode):
            raise RuntimeError("Requires effective PYTHONHASHSEED=0 with -P -s -B startup")

    def summarize(self, problem, event):
        # Syntactic identity fixtures only, never a claimed executed manifest.
        identity = {"format": "irisx.math.scoring-identity.v1", "code_sha": "0" * 40,
                    "source_sha256": "1" * 64, "protocol_semantic_sha256": "2" * 64,
                    "panel_semantic_sha256": digest([problem]),
                    "model_spec_sha256": "3" * 64, "verifier_spec_sha256": "4" * 64}
        row = {"problem_id": problem["id"], "seed": 0, "arm": "M-DIRECT", "identities": identity,
               "statement_sha256": problem["statement_sha256"], "answer_mode": problem["answer_mode"],
               "status": "proof_accepted", "events": [copy.deepcopy(event)],
               "answer_status": "correct" if problem["answer_mode"] == "find_answer" else "not_applicable",
               "joint_status": "kernel_verified" if problem["answer_mode"] == "find_answer" else "not_applicable",
               "wall_seconds": 0.5, "verifier_setup_seconds": 0.1}
        row["events"][0].update(model_cost={"prompt_tokens": 10, "output_tokens": 5, "wall_seconds": 0.2},
                                  model_cost_complete=True, tool_attempted=True, tool_wall_seconds=0.1)
        return analyze([problem], [row], [0], identity)

    def check(self, problem, event, expected):
        self.assertIs(verified_receipt_matches(event.get("tool"), problem, event.get("candidate"),
                                              model_text=event.get("model_text")), expected)
        self.assertIs(accepted(event.get("tool"), problem, event.get("candidate"),
                               model_text=event.get("model_text")), expected)
        self.assertIs(verified_event_matches(event, problem), expected)
        if problem.get("answer_mode") == "find_answer":
            self.assertIs(bound_answer_matches(event, problem), expected)
        if expected:
            summary = self.summarize(problem, event)["arms"]["M-DIRECT"]
            self.assertEqual(summary["proof_rate"], 1.0)
            if problem["answer_mode"] == "find_answer":
                self.assertEqual(summary["joint_rate"], 1.0)
        else:
            with self.assertRaises(ValueError):
                self.summarize(problem, event)

    def test_correct_receipts_all_modes(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.check(*fixture(mode), True)

    def test_fenced_JSON_preserves_raw_candidate(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                problem, event = fixture(mode)
                event["model_text"] = "```json\n" + event["model_text"] + "\n```"
                self.check(problem, event, True)

    def test_JSON_envelope_whitespace_is_not_proof_normalization(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                problem, event = fixture(mode)
                event["model_text"] = json.dumps(event["candidate"], indent=2)
                self.check(problem, event, True)

    def test_changed_proof_and_model_text_cannot_reuse_receipt(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                problem, event = fixture(mode)
                event["candidate"]["proof_body"] = "by\n  trivial"
                event["model_text"] = json.dumps(event["candidate"])
                self.check(problem, event, False)

    def test_changed_candidate_only_cannot_reuse_receipt(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                problem, event = fixture(mode)
                event["candidate"]["proof_body"] = "by\n  trivial"
                self.check(problem, event, False)

    def test_changed_model_text_only_cannot_reuse_receipt(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                problem, event = fixture(mode)
                event["model_text"] = json.dumps(dict(event["candidate"], proof_body="by\n  trivial"))
                self.check(problem, event, False)

    def test_proof_whitespace_bytes_not_normalized(self):
        for mode in MODES:
            for body in (BODY + "\n", BODY.replace("\n", "\r\n"), "by\n    rfl", " " + BODY):
                with self.subTest(mode=mode, body=repr(body)):
                    problem, event = fixture(mode)
                    event["candidate"]["proof_body"] = body
                    event["model_text"] = json.dumps(event["candidate"])
                    self.check(problem, event, False)

    def test_missing_or_changed_candidate_hash_rejected(self):
        for mode in MODES:
            for value in (None, "0" * 64, "", 1):
                with self.subTest(mode=mode, value=value):
                    problem, event = fixture(mode)
                    if value is None:
                        event["tool"].pop("candidate_sha256")
                    else:
                        event["tool"]["candidate_sha256"] = value
                    self.check(problem, event, False)

    def test_receipt_statement_hash_rejected(self):
        for mode in MODES:
            for value in (None, "0" * 64):
                with self.subTest(mode=mode, value=value):
                    problem, event = fixture(mode)
                    if value is None:
                        event["tool"].pop("statement_sha256")
                    else:
                        event["tool"]["statement_sha256"] = value
                    self.check(problem, event, False)

    def test_changed_statement_bytes_with_stale_hash_rejected(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                problem, event = fixture(mode)
                problem["statement"]["declaration"] += " ∧ True"
                self.check(problem, event, False)

    def test_disagreeing_problem_and_statement_hash_rejected(self):
        for mode in MODES:
            for location in ("problem", "statement"):
                with self.subTest(mode=mode, location=location):
                    problem, event = fixture(mode)
                    if location == "problem":
                        problem["statement_sha256"] = "0" * 64
                    else:
                        problem["statement"]["sha256"] = "0" * 64
                    self.check(problem, event, False)

    def test_each_success_field_is_required_and_coherent(self):
        values = {"status": (None, "rejected", "timeout", "infrastructure_error"),
                  "accepted": (None, False, 1, "true"),
                  "proof_status": (None, "incomplete", "unsupported"),
                  "trust_policy_passed": (None, False, 1, "true")}
        for mode in MODES:
            for key, invalids in values.items():
                for value in invalids:
                    with self.subTest(mode=mode, key=key, value=value):
                        problem, event = fixture(mode)
                        if value is None:
                            event["tool"].pop(key)
                        else:
                            event["tool"][key] = value
                        self.check(problem, event, False)

    def test_event_status_must_also_be_accepted(self):
        for mode in MODES:
            for status in (None, "generated", "rejected", "timeout"):
                with self.subTest(mode=mode, status=status):
                    problem, event = fixture(mode)
                    event["status"] = status
                    self.assertFalse(verified_event_matches(event, problem))
                    with self.assertRaises(ValueError):
                        self.summarize(problem, event)
                    if mode == "find_answer":
                        self.assertFalse(bound_answer_matches(event, problem))

    def test_missing_or_malformed_model_text_rejected(self):
        for mode in MODES:
            for text in (None, "", "not JSON", "[]", "null", "x" * 65537,
                         '{"answer":null,"proof_body":"by\\n  rfl","extra":1}'):
                with self.subTest(mode=mode, text_kind=type(text).__name__):
                    problem, event = fixture(mode)
                    event["model_text"] = text
                    self.check(problem, event, False)

    def test_candidate_shape_type_and_mode_rejected(self):
        for mode in MODES:
            for candidate in (None, {}, {"answer": "2", "proof_body": 1},
                              {"answer": 2, "proof_body": BODY},
                              {"answer": "2", "proof_body": ""},
                              {"answer": "2", "proof_body": BODY, "extra": 1}):
                with self.subTest(mode=mode, candidate=candidate):
                    problem, event = fixture(mode)
                    event["candidate"] = candidate
                    event["model_text"] = json.dumps(candidate)
                    self.check(problem, event, False)
        problem, event = fixture("proof_only")
        event["candidate"]["answer"] = "2"
        event["model_text"] = json.dumps(event["candidate"])
        self.check(problem, event, False)
        problem, event = fixture("answer_given")
        problem["answer_mode"] = "unsupported_mode"
        self.check(problem, event, False)

    def test_find_answer_preserves_all_witness_binding_fields(self):
        for field in ("kind", "status", "statement_sha256", "spec_sha256",
                      "candidate_sha256", "normalized_answer_sha256"):
            with self.subTest(field=field):
                problem, event = fixture("find_answer")
                event["tool"]["answer_binding"][field] = "different"
                self.check(problem, event, False)

    def test_find_answer_changed_answer_spec_or_missing_witness_rejected(self):
        for change in ("answer", "spec", "missing"):
            with self.subTest(change=change):
                problem, event = fixture("find_answer")
                if change == "answer":
                    event["candidate"]["answer"] = "3"
                    event["model_text"] = json.dumps(event["candidate"])
                elif change == "spec":
                    problem["answer_binding"]["review_ref"] += "-different"
                else:
                    event["tool"].pop("answer_binding")
                self.check(problem, event, False)

    def test_proof_modes_are_not_joint_discovery(self):
        for mode in ("proof_only", "answer_given"):
            problem, event = fixture(mode)
            self.assertTrue(verified_event_matches(event, problem))
            self.assertFalse(bound_answer_matches(event, problem))

    def test_validator_does_not_mutate_candidate_or_receipt(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                problem, event = fixture(mode)
                original = copy.deepcopy((problem, event))
                self.check(problem, event, True)
                self.assertEqual((problem, event), original)

    def test_actual_UTF8_body_hash_accepted_without_normalization(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                problem, event = fixture(mode)
                body = "by\n  constructor\n  · rfl\n  · rfl\n"
                # This is a scripted receipt contract only, not a claim that the
                # body proves the fixture. No Lean process executes this text.
                event["candidate"]["proof_body"] = body
                event["model_text"] = json.dumps(event["candidate"], ensure_ascii=False)
                if mode == "find_answer":
                    digest = answer_candidate_digest("2", body)
                    event["tool"]["answer_binding"]["candidate_sha256"] = digest
                else:
                    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
                event["tool"]["candidate_sha256"] = digest
                self.check(problem, event, True)


if __name__ == "__main__":
    print(json.dumps({"controlled_startup": {"PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
        "ignore_environment": sys.flags.ignore_environment, "hash_randomization": sys.flags.hash_randomization,
        "safe_path": sys.flags.safe_path, "no_user_site": sys.flags.no_user_site,
        "dont_write_bytecode": sys.dont_write_bytecode, "optimize": sys.flags.optimize,
        "effective_hash_probe": hash("IRIS-X-MATH-002")}}), flush=True)
    unittest.main()
