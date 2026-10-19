"""Authored engineering controls, never benchmark/model efficacy evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lean_worker import (LeanWorker, parse_proof_body, probe_isolation,
                         statement_digest, tree_sha256)


def parser_controls() -> dict:
    positive = ["by\n  rfl", "by\n  intro h\n  exact h", "by\n  omega",
                "by\n  simp only [Nat.add_comm]"]
    negative = ["by\n  sorry", "by\n  native_decide", "by\n  run_tac pure ()",
                "by\n  exact (by sorry)", "by\n  rfl\n#print axioms fake",
                "by\n  exact h; run_tac pure ()", "by\n  simp [show False from sorry]",
                "by\n  rfl /-", "by\n  rfl\naxiom unsafe : False", "by\n  exact Lean.ofReduceBool"]
    checks = {}
    for index, body in enumerate(positive):
        try:
            parse_proof_body(body)
            checks[f"positive_{index}"] = True
        except ValueError:
            checks[f"positive_{index}"] = False
    # A constant named Lean.ofReduceBool is syntactically an allowed identifier;
    # it must be rejected by final theorem axiom audit, not a string blacklist.
    for index, body in enumerate(negative[:-1]):
        try:
            parse_proof_body(body)
            checks[f"negative_{index}"] = False
        except ValueError:
            checks[f"negative_{index}"] = True
    return {"kind": "authored_parser_controls", "checks": checks,
            "passed": sum(checks.values()), "total": len(checks), "ok": all(checks.values())}


def lean_controls(config: dict) -> dict:
    cases = [
        ("true_rfl", ": (2 : Nat) = 2", "by\n  rfl", True),
        ("false_rfl", ": (2 : Nat) = 3", "by\n  rfl", False),
        ("incomplete", ": True ∧ True", "by\n  constructor", False),
        ("sorry_injection", ": False", "by\n  sorry", False),
        ("command_injection", ": False", "by\n  rfl\naxiom fake : False", False),
        ("implication", "(P : Prop) (h : P) : P", "by\n  exact h", True),
    ]
    config = dict(config, engineering_controls_only=True, statement_sha256s={})
    for identifier, declaration, _, _ in cases + [("transitive_axiom", ": False", "", False)]:
        statement = {"id": identifier, "imports": ["Init"], "declaration": declaration,
                     "fidelity": "authored_engineering_control"}
        config["statement_sha256s"][identifier] = statement_digest(statement)
    worker = LeanWorker(config)
    preflight = worker.preflight()
    report = {"kind": "authored_Lean_controls", "preflight": preflight,
              "controls": [], "qualified": False}
    if not preflight.get("runtime_qualified"):
        return report
    for identifier, declaration, proof, expected in cases:
        statement = {"id": identifier, "imports": ["Init"], "declaration": declaration,
                     "fidelity": "authored_engineering_control"}
        statement["sha256"] = statement_digest(statement)
        result = worker.verify(statement, proof)
        report["controls"].append({"id": identifier, "expected_accept": expected,
                                   "matched": result["accepted"] is expected, "result": result})
    # This controls-only trusted declaration introduces an axiom dependency. It
    # cannot enter an actual panel: panel bytes and fidelity are separately bound.
    statement = {"id": "transitive_axiom", "imports": ["Init"],
                 "declaration": ": False", "fidelity": "authored_engineering_control"}
    statement["sha256"] = statement_digest(statement)
    original = worker._run_source
    def inject_dependency(source, command=None, limits=None):
        if source is not None:
            source = source.replace("set_option maxHeartbeats 200000\n", "set_option maxHeartbeats 200000\naxiom irisx_bad : False\ntheorem irisx_hidden : False := irisx_bad\n")
        return original(source, command, limits)
    worker._run_source = inject_dependency
    result = worker.verify(statement, "by\n  exact irisx_hidden")
    report["controls"].append({"id": "transitive_axiom", "expected_accept": False,
                               "matched": result["status"] == "trust_rejected" and result.get("axioms") == ["irisx_bad"],
                               "result": result})
    report["qualified"] = all(item["matched"] for item in report["controls"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--isolation-only", action="store_true")
    parser.add_argument("--parser-only", action="store_true")
    parser.add_argument("--bwrap")
    parser.add_argument("--work-root")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--fingerprint-runtime", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.fingerprint_runtime:
        print(tree_sha256(args.fingerprint_runtime.resolve()))
        return 0
    if args.parser_only:
        result = parser_controls()
        passed = result["ok"]
    elif args.isolation_only:
        result = probe_isolation(args.bwrap, args.work_root)
        passed = result["qualified"]
    elif args.config:
        result = lean_controls(json.loads(args.config.read_text(encoding="utf-8")))
        passed = result["qualified"]
    else:
        parser.error("choose --parser-only, --isolation-only, --config or --fingerprint-runtime")
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(encoded, encoding="utf-8")
        temporary.replace(args.output)
    print(encoded)
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
