"""Authored Nat answer-binding engineering controls, never model evaluation."""
from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lean_worker import (ANSWER_BINDING_KIND, LeanWorker, answer_binding_digest,
                         answer_candidate_digest, normalize_nat_answer,
                         normalized_answer_sha256, statement_digest)


def statement(identifier: str, declaration: str) -> dict:
    item = {"id": identifier, "imports": ["Init"], "declaration": declaration,
            "fidelity": "authored_engineering_control"}
    item["sha256"] = statement_digest(item)
    return item


def spec_for(item: dict) -> dict:
    return {"kind": ANSWER_BINDING_KIND, "statement_sha256": item["sha256"],
            "review_ref": "engineering:answer_controls:" + item["id"],
            "answer_mode": "find_answer"}


def run_controls(config: dict) -> dict:
    if (os.environ.get("PYTHONHASHSEED") != "0" or sys.flags.ignore_environment
            or sys.flags.hash_randomization != 0 or not sys.flags.safe_path
            or not sys.flags.no_user_site or not sys.dont_write_bytecode):
        raise ValueError("Requires effective PYTHONHASHSEED=0 with -P -s -B startup")
    paths = [Path(__file__).resolve(), Path(__file__).resolve().parents[1] / "lean_worker.py"]
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    seven = statement("answer_seven", ": ∃ n : Nat, n = 7")
    zero = statement("answer_zero", ": ∃ n : Nat, n = 0")
    reflexive = statement("answer_reflexive", ": ∃ n : Nat, n = n")
    config = copy.deepcopy(config)
    config.update(engineering_controls_only=True,
                  statement_sha256s={s["id"]: s["sha256"] for s in [seven, zero, reflexive]},
                  answer_bindings={s["id"]: spec_for(s) for s in [seven, zero, reflexive]})
    worker = LeanWorker(config)
    started = time.monotonic()
    preflight = worker.preflight()
    report = {"kind": "authored_Nat_answer_binding_controls", "qualified": False,
              "source_files": hashes, "preflight": preflight, "controls": [],
              "preflight_wall_seconds": time.monotonic() - started,
              "statement_sha256s": config["statement_sha256s"],
              "binding_spec_sha256s": {key: answer_binding_digest(value)
                                      for key, value in config["answer_bindings"].items()},
              "verifier_identity": worker.identity(), "scoring_model_calls": 0, "tpu_runs": 0,
              "human_review": "not_claimed_engineering_controls_only",
              "seed_startup": {"requested": "0", "ignore_environment": sys.flags.ignore_environment,
                               "hash_randomization": sys.flags.hash_randomization,
                               "safe_path": sys.flags.safe_path, "no_user_site": sys.flags.no_user_site,
                               "dont_write_bytecode": sys.dont_write_bytecode,
                               "probe_hash": hash("IRIS-X-MATH-002")}}
    if preflight.get("status") != "passed":
        return report

    def record(identifier, result, expected, *, semantic_error=False, check=True):
        matched = result["status"] == expected and check
        if semantic_error:
            execution = result.get("execution", {})
            matched = (matched and execution.get("exit_code") == 1
                       and "error:" in execution.get("output", "")
                       and "unknown module" not in execution.get("output", ""))
        if expected != "accepted":
            matched = matched and not result["accepted"] and "answer_binding" not in result
        report["controls"].append({"id": identifier, "expected_status": expected,
                                   "matched": bool(matched), "result": result})

    for identifier, item, answer, expected in [
        ("correct_witness", seven, "7", "accepted"),
        ("wrong_witness", seven, "8", "rejected"),
        ("zero_witness", zero, "0", "accepted"),
        ("sixty_digit_numeral", reflexive, "9" * 60, "accepted"),
    ]:
        body = "by\n  rfl"
        result = worker.verify_answer(item, answer, body)
        receipt = result.get("answer_binding", {})
        check = expected != "accepted" or receipt == {
            "kind": ANSWER_BINDING_KIND, "status": "kernel_verified",
            "statement_sha256": item["sha256"],
            "spec_sha256": answer_binding_digest(spec_for(item)),
            "normalized_answer_sha256": normalized_answer_sha256(answer),
            "candidate_sha256": answer_candidate_digest(answer, body)}
        record(identifier, result, expected, semantic_error=expected == "rejected", check=check)

    original_run = worker._run_source
    injected_sources = []
    def inject_alternate(source, command=None, limits=None):
        if source is not None:
            # This authored test helper proves the original existential using 7.
            # A candidate reporting 8 must not use that theorem as its residual proof.
            injected_sources.append(source)
            source = source.replace("set_option maxHeartbeats 200000\n",
                "set_option maxHeartbeats 200000\n"
                "theorem irisx_alternate : ∃ n : Nat, n = 7 := ⟨7, rfl⟩\n")
        return original_run(source, command, limits)
    worker._run_source = inject_alternate
    result = worker.verify_answer(seven, "8", "by\n  exact irisx_alternate")
    record("alternate_existential_cannot_replace_witness", result, "rejected", semantic_error=True,
           check=bool(injected_sources) and
           "theorem irisx_final " + seven["declaration"] + " :=" in injected_sources[-1]
           and "_root_.Exists.intro (8 : _root_.Nat) (by" in injected_sources[-1])

    def inject_axiom(source, command=None, limits=None):
        if source is not None:
            source = source.replace("set_option maxHeartbeats 200000\n",
                "set_option maxHeartbeats 200000\n"
                "axiom irisx_answer_bad : (8 : Nat) = 7\n"
                "theorem irisx_answer_hidden : (8 : Nat) = 7 := irisx_answer_bad\n")
        return original_run(source, command, limits)
    worker._run_source = inject_axiom
    result = worker.verify_answer(seven, "8", "by\n  exact irisx_answer_hidden")
    record("transitive_axiom_in_residual_proof", result, "trust_rejected",
           check=result.get("axioms") == ["irisx_answer_bad"]
                 and result.get("execution", {}).get("exit_code") == 0)
    worker._run_source = original_run

    # Every following verification control must reject before any Lean execution.
    invalid_answers = ["", " 7", "7 ", "+7", "-1", "07", "7/1", "7.0", "７",
                       "7\n", "7 : Nat", "7) (by rfl)", "9" * 61, 7, None]
    for index, answer in enumerate(invalid_answers):
        result = worker.verify_answer(seven, answer, "by\n  rfl")
        record("malformed_answer_" + str(index), result, "invalid_format",
               check="execution" not in result)
    for index, body in enumerate(["by\n  exact ⟨7, rfl⟩", "by\n  refine Exists.intro 7 ?_\n  rfl",
                                   "by\n  rfl\n)\n#print axioms irisx_final", "by\n  sorry"]):
        record("proof_escape_" + str(index), worker.verify_answer(seven, "8", body), "invalid_format")
    record("proof_only_bypass", worker.verify(seven, "by\n  rfl"), "invalid_format")
    malformed_registration = LeanWorker(dataclasses.replace(worker.config,
        answer_bindings={seven["id"]: None}))
    record("null_registration_proof_only_bypass",
           malformed_registration.verify(seven, "by\n  rfl"), "invalid_format")
    result = worker.verify_answer(seven, "7", "by\n  rfl", deadline=time.monotonic() - 1)
    record("expired_arm_deadline", result, "timeout", check="execution" not in result)

    def altered_worker(item, spec):
        options = copy.deepcopy(config)
        options["statement_sha256s"] = {item["id"]: item["sha256"]}
        options["answer_bindings"] = {} if spec is None else {item["id"]: spec}
        return LeanWorker(options)
    bad_specs = [None,
                 dict(spec_for(seven), statement_sha256="0" * 64),
                 dict(spec_for(seven), kind="closed_exists_rat_v1"),
                 dict(spec_for(seven), answer_mode="answer_given"),
                 dict(spec_for(seven), review_ref=""),
                 dict(spec_for(seven), review_ref="source:unreviewed"),
                 dict(spec_for(seven), extra="unregistered")]
    for index, spec in enumerate(bad_specs):
        result = altered_worker(seven, spec).verify_answer(seven, "7", "by\n  rfl")
        record("spec_admission_" + str(index), result, "invalid_format", check="execution" not in result)
    for index, declaration in enumerate([
        "(k : Nat) : ∃ n : Nat, n = k", ": ∃ n : Int, n = 7", ": ∃ n : Rat, n = 7",
        ": ∃! n : Nat, n = 7", ": ExistsUnique (fun n : Nat => n = 7)",
        ": ∃ n : Nat, ∃ m : Nat, n = m", ": True"]):
        item = statement("unsupported_declaration_" + str(index), declaration)
        result = altered_worker(item, spec_for(item)).verify_answer(item, "7", "by\n  rfl")
        record("declaration_admission_" + str(index), result, "invalid_format", check="execution" not in result)
    changed = statement(seven["id"], ": ∃ n : Nat, n = 8")
    record("statement_drift", worker.verify_answer(changed, "8", "by\n  rfl"), "invalid_format")
    production = LeanWorker(dataclasses.replace(worker.config, engineering_controls_only=False))
    record("engineering_fidelity_in_production", production.verify_answer(seven, "7", "by\n  rfl"),
           "invalid_format")

    original_identity = worker.identity()
    detached = worker.answer_binding_spec(seven["id"])
    detached["review_ref"] = "engineering:modified-copy"
    config["answer_bindings"][seven["id"]]["review_ref"] = "engineering:mutated-input"
    helper_checks = {
        "canonical_zero": normalize_nat_answer("0") == "0",
        "distinct_answer_digest": answer_candidate_digest("7", "by\n  rfl") != answer_candidate_digest("8", "by\n  rfl"),
        "distinct_proof_digest": answer_candidate_digest("7", "by\n  rfl") != answer_candidate_digest("7", "by\n  trivial"),
        "detached_spec_and_constructor_maps": worker.answer_binding_spec(seven["id"]) == spec_for(seven),
        "unchanged_identity_after_external_mutation": worker.identity() == original_identity,
        "unregistered_spec_is_none": worker.answer_binding_spec("unregistered") is None,
        "binding_in_identity": altered_worker(seven, dict(spec_for(seven), review_ref="engineering:other")).identity()
            != altered_worker(seven, spec_for(seven)).identity(),
    }
    report["helper_controls"] = {"kind": "pure_helper_controls", "checks": helper_checks,
                                 "test_count": len(helper_checks), "passed_count": sum(helper_checks.values())}
    def thread_failure_receipt(source, command=None, limits=None):
        return {"exit_code": 1, "timed_out": False, "wall_seconds": 0,
                "output": "failed to create thread\n", "output_truncated": False}
    worker._run_source = thread_failure_receipt
    synthetic_result = worker.verify_answer(seven, "7", "by\n  rfl")
    worker._run_source = original_run
    report["synthetic_runtime_controls"] = {
        "kind": "synthetic_process_receipt_branch_controls", "actual_Lean_executions": 0,
        "test_count": 1, "passed_count": int(synthetic_result["status"] == "infrastructure_error"
            and not synthetic_result["accepted"] and "answer_binding" not in synthetic_result),
        "result": synthetic_result}
    report["source_files_after"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    report["source_unchanged_during_run"] = hashes == report["source_files_after"]
    report["actual_Lean_executions"] = sum("execution" in item["result"] for item in report["controls"])
    report["test_count"] = len(report["controls"])
    report["passed_count"] = sum(item["matched"] for item in report["controls"])
    report["qualified"] = (all(item["matched"] for item in report["controls"])
                           and all(helper_checks.values()) and report["source_unchanged_during_run"]
                           and report["synthetic_runtime_controls"]["passed_count"] == 1)
    report["wall_seconds"] = time.monotonic() - started
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("fresh output path required; previous receipts are preserved")
    result = run_controls(json.loads(args.config.read_text(encoding="utf-8")))
    result["config_sha256"] = hashlib.sha256(args.config.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"qualified": result["qualified"], "test_count": result.get("test_count", 0),
                      "passed_count": result.get("passed_count", 0),
                      "actual_Lean_executions": result.get("actual_Lean_executions", 0),
                      "preflight_blocker": result["preflight"].get("blocker"), "output": str(args.output)}))
    return 0 if result["qualified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
