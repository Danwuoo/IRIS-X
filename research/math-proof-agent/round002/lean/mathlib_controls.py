"""Public authored Mathlib engineering controls; no panel or model evaluation.

Runs the committed restricted worker unchanged against a separately fingerprinted
Mathlib project. Every statement has engineering-only fidelity and is bound
before preflight. This file never acquires dependencies or calls a provider.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lean_worker import LeanWorker, statement_digest, tree_sha256


MATHLIB_COMMIT = "c44e0c8ee63ca166450922a373c7409c5d26b00b"
IMPORTS = ["Mathlib.Tactic.Ring", "Mathlib.Tactic.NormNum"]
CASES = [
    ("mathlib_ring_identity", "(x y : Nat) : (x + y)^2 = x^2 + 2*x*y + y^2",
     "by\n  ring", "accepted"),
    ("mathlib_ring_false", "(x y : Nat) : (x + y)^2 = x^2 + y^2",
     "by\n  ring", "rejected"),
    ("mathlib_norm_num_true", ": (23 : Nat) * 19 = 437",
     "by\n  norm_num", "accepted"),
    ("mathlib_norm_num_false", ": (23 : Nat) * 19 = 438",
     "by\n  norm_num", "rejected"),
    ("mathlib_omega_true", "(n : Nat) (h : n > 7) : n >= 8",
     "by\n  omega", "accepted"),
    ("mathlib_omega_false", "(n : Nat) (h : n > 7) : n >= 9",
     "by\n  omega", "rejected"),
    ("mathlib_forbidden_native", ": (23 : Nat) * 19 = 437",
     "by\n  native_decide", "invalid_format"),
    ("mathlib_forbidden_command", ": True",
     "by\n  trivial\n#print axioms other_theorem", "invalid_format"),
]


def statement(identifier: str, declaration: str) -> dict:
    result = {"id": identifier, "imports": IMPORTS, "declaration": declaration,
              "fidelity": "authored_engineering_control"}
    result["sha256"] = statement_digest(result)
    return result


def synthetic_exit_controls(config: dict) -> dict:
    """Mock only the process receipt; no executable or sandbox is started here."""
    fixed = statement("synthetic_exit_fixture", ": True")
    options = dict(config, engineering_controls_only=True,
                   statement_sha256s={fixed["id"]: fixed["sha256"]})
    worker = LeanWorker(options)
    worker._preflight = {"runtime_qualified": True, "status": "passed"}
    checks = []
    for code, expected in [(128, "infrastructure_error"), (139, "infrastructure_error"),
                           (152, "infrastructure_error"), (-11, "infrastructure_error"),
                           (1, "rejected"), (0, "trust_rejected")]:
        def mocked_source(source, command=None, limits=None):
            return {"exit_code": code, "timed_out": False, "wall_seconds": 0,
                    "output": "", "output_truncated": False}
        worker._run_source = mocked_source
        result = worker.verify(fixed, "by\n  trivial")
        checks.append({"exit_code": code, "expected_status": expected,
                       "actual_status": result["status"],
                       "matched": result["status"] == expected and not result["accepted"]})
    return {"kind": "synthetic_process_receipt_branch_controls", "actual_Lean_executions": 0,
            "checks": checks, "test_count": len(checks),
            "passed_count": sum(item["matched"] for item in checks),
            "qualified": all(item["matched"] for item in checks)}


def run_controls(config: dict) -> dict:
    if (os.environ.get("PYTHONHASHSEED") != "0" or sys.flags.ignore_environment
            or sys.flags.hash_randomization != 0 or not sys.flags.safe_path
            or not sys.flags.no_user_site or not sys.dont_write_bytecode):
        raise ValueError("Requires effective PYTHONHASHSEED=0 with -P -s -B startup")
    source_files = [Path(__file__).resolve(), Path(__file__).resolve().parents[1] / "lean_worker.py"]
    source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files}
    config = dict(config)
    if config.get("mathlib_revision") != MATHLIB_COMMIT:
        raise ValueError("Controls require the exact Mathlib v4.19.0 source commit")
    config["engineering_controls_only"] = True
    config["statement_sha256s"] = {
        identifier: statement(identifier, declaration)["sha256"]
        for identifier, declaration, _, _ in CASES
    }
    config["statement_sha256s"]["mathlib_hidden_axiom"] = statement(
        "mathlib_hidden_axiom", ": False")["sha256"]
    worker = LeanWorker(config)
    started = time.monotonic()
    preflight = worker.preflight()
    report = {"kind": "authored_Mathlib_controls", "mathlib_revision": MATHLIB_COMMIT,
              "imports": IMPORTS, "preflight": preflight,
              "controls": [], "qualified": False,
              "scoring_model_calls": 0, "tpu_runs": 0,
              "source_files": source_hashes,
              "seed_startup": {"requested": "0", "ignore_environment": sys.flags.ignore_environment,
                               "hash_randomization": sys.flags.hash_randomization,
                               "safe_path": sys.flags.safe_path, "no_user_site": sys.flags.no_user_site,
                               "dont_write_bytecode": sys.dont_write_bytecode,
                               "probe_hash": hash("IRIS-X-MATH-002")},
              "human_review": "not_claimed_engineering_controls_only"}
    report["preflight_wall_seconds"] = time.monotonic() - started
    if preflight.get("status") != "passed":
        return report
    for identifier, declaration, proof, expected in CASES:
        result = worker.verify(statement(identifier, declaration), proof)
        matched = result["status"] == expected
        if expected == "rejected":
            # A crash, launcher error or missing import is not a negative proof control.
            execution = result.get("execution", {})
            matched = (matched and execution.get("exit_code") == 1
                       and "error:" in execution.get("output", "")
                       and "unknown module" not in execution.get("output", ""))
        report["controls"].append({"id": identifier, "expected_status": expected,
                                   "matched": matched, "result": result})
    # Trusted authored source injection is confined to this negative control.
    # The normal worker never exposes an untrusted command insertion route.
    original_run = worker._run_source
    def inject_dependency(source, command=None, limits=None):
        if source is not None:
            source = source.replace(
                "set_option maxHeartbeats 200000\n",
                "set_option maxHeartbeats 200000\n"
                "axiom irisx_mathlib_bad : False\n"
                "theorem irisx_mathlib_hidden : False := irisx_mathlib_bad\n")
        return original_run(source, command, limits)
    worker._run_source = inject_dependency
    result = worker.verify(statement("mathlib_hidden_axiom", ": False"),
                           "by\n  exact irisx_mathlib_hidden")
    report["controls"].append({
        "id": "mathlib_hidden_axiom", "expected_status": "trust_rejected",
        "matched": result["status"] == "trust_rejected"
                   and result.get("axioms") == ["irisx_mathlib_bad"],
        "result": result})
    worker._run_source = original_run
    # Recomputed hashes on changed statements cannot bypass the prebound map.
    changed = statement("mathlib_norm_num_true", ": (23 : Nat) * 19 = 438")
    result = worker.verify(changed, "by\n  norm_num")
    report["controls"].append({"id": "statement_binding_mutation",
                               "expected_status": "invalid_format",
                               "matched": result.get("reason") == "statement_binding_or_fidelity_failed",
                               "result": result})
    report["source_files_after"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files}
    report["synthetic_exit_controls"] = synthetic_exit_controls(config)
    report["source_unchanged_during_run"] = source_hashes == report["source_files_after"]
    report["qualified"] = (all(item["matched"] for item in report["controls"])
                           and report["source_unchanged_during_run"]
                           and report["synthetic_exit_controls"]["qualified"])
    report["wall_seconds"] = time.monotonic() - started
    report["test_count"] = len(report["controls"])
    report["passed_count"] = sum(item["matched"] for item in report["controls"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fingerprint-project", type=Path)
    args = parser.parse_args()
    if args.fingerprint_project:
        print(tree_sha256(args.fingerprint_project.resolve()))
        return 0
    if not args.config or not args.output:
        parser.error("--config and --output are required for controls")
    if args.output.exists():
        parser.error("fresh output path required; previous receipts are preserved")
    result = run_controls(json.loads(args.config.read_text()))
    result["config_sha256"] = hashlib.sha256(args.config.read_bytes()).hexdigest()
    result["source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(args.output)
    print(json.dumps({"qualified": result["qualified"],
                      "test_count": result.get("test_count", 0),
                      "passed_count": result.get("passed_count", 0),
                      "preflight_blocker": result["preflight"].get("blocker"),
                      "output": str(args.output)}, sort_keys=True))
    return 0 if result["qualified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
