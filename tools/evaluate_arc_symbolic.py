#!/usr/bin/env python3
"""EVALUATOR ONLY: frozen public development comparisons; never solver import.

Solutions and correctness rows are local evaluator artifacts. A final public
confirmation requires a caller-owned single-use lock, created BEFORE truth is
opened. This is not official scoring or evidence of unseen exposure.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from irisx.arc_candidates_neutral import combine_pools, validate_challenges
from irisx.canonical import canonical_bytes, digest_value
from tools.arc_kaggle_submission import parse_json, require, write_new
from tools.arc_offline_evaluation import evaluate, metric, paired, validate_pools


def exact_union_metrics(baseline: dict, symbolic: dict) -> dict:
    """Full-pool oracle from paired evaluator rows, without 64-grid merge loss."""
    left = {(r["task_id"], r["test_index"]): r for r in baseline["rows"]}
    right = {(r["task_id"], r["test_index"]): r for r in symbolic["rows"]}
    require(set(left) == set(right), "exact evaluator test identities required")
    tasks, baseline_tasks, symbolic_tasks = {}, {}, {}
    gain_tests, gain_tasks, union = 0, set(), 0
    for identity, a in left.items():
        b = right[identity]
        require(a["task_digest"] == b["task_digest"] and a["input_digest"] == b["input_digest"],
                "full task/test identity differs")
        correct = a["oracle"] or b["oracle"]
        union += bool(correct)
        tasks.setdefault(identity[0], []).append(bool(correct))
        baseline_tasks.setdefault(identity[0], []).append(bool(a["oracle"]))
        symbolic_tasks.setdefault(identity[0], []).append(bool(b["oracle"]))
        if b["oracle"] and not a["oracle"]:
            gain_tests += 1
            gain_tasks.add(identity[0])
    return {"candidate_union_oracle": metric(union, len(left)),
            "tasks_all_tests_union_oracle": metric(sum(all(v) for v in tasks.values()), len(tasks), "task"),
            "symbolic_new_correct_tests": gain_tests, "tasks_with_new_correct_tests": len(gain_tasks),
            "symbolic_newly_all_tests_correct_tasks": sum(all(symbolic_tasks[k]) and not all(baseline_tasks[k]) for k in tasks),
            "newly_all_tests_correct_union_tasks": sum(all(tasks[k]) and not all(baseline_tasks[k]) for k in tasks),
            "qualification": "full retained-pool oracle; not fixed-two-slot or submitted score"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--challenges", type=Path, required=True)
    parser.add_argument("--expected-challenges-digest", required=True)
    parser.add_argument("--solutions", type=Path, required=True)
    parser.add_argument("--expected-solutions-sha256", required=True)
    parser.add_argument("--symbolic-pools", type=Path, required=True)
    parser.add_argument("--expected-symbolic-sha256", required=True)
    parser.add_argument("--baseline-pools", type=Path)
    parser.add_argument("--expected-baseline-sha256")
    parser.add_argument("--policy", choices=("baseline-first", "one-each"), default="baseline-first")
    parser.add_argument("--purpose", choices=("development", "final-public-confirmation"), default="development")
    parser.add_argument("--confirmation-lock", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy_version = 2 if args.policy == "one-each" else 1
    challenges = validate_challenges(parse_json(args.challenges.read_bytes()))
    require(digest_value(challenges) == args.expected_challenges_digest, "frozen challenge digest differs")
    def load_bound(path, sha):
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == sha, "frozen artifact byte hash differs: " + str(path))
        return parse_json(raw)
    symbolic = load_bound(args.symbolic_pools, args.expected_symbolic_sha256)
    validate_pools(challenges, symbolic)
    baseline = None
    if args.baseline_pools:
        require(args.expected_baseline_sha256 is not None, "baseline byte hash required")
        baseline = load_bound(args.baseline_pools, args.expected_baseline_sha256)
        validate_pools(challenges, baseline)
    else:
        require(args.expected_baseline_sha256 is None, "baseline hash without baseline")
    require(not args.output.exists(), "new evaluator output directory required")
    if args.purpose == "final-public-confirmation":
        require(args.confirmation_lock is not None and not args.confirmation_lock.exists(),
                "fresh single-use final confirmation lock required")
        write_new(args.confirmation_lock, canonical_bytes({"purpose": args.purpose,
            "challenges_digest": digest_value(challenges), "symbolic_pool_digest": digest_value(symbolic),
            "baseline_pool_digest": None if baseline is None else digest_value(baseline),
            "policy": args.policy, "policy_version": policy_version}))
    else:
        require(args.confirmation_lock is None, "development must not consume a confirmation lock")
    # First opening of evaluator truth happens only after all source/candidate
    # and single-final-lock gates above. Nothing is fed back into solver records.
    solutions = load_bound(args.solutions, args.expected_solutions_sha256)
    symbolic_eval = evaluate(challenges, solutions, symbolic)
    report = {"format": "irisx/arc-symbolic-comparison-v1", "purpose": args.purpose,
              "qualification": "known-exposed public development; no official score or unseen-generalization claim",
              "symbolic": symbolic_eval, "baseline": None, "fixed_slots": None, "union": None, "paired": None,
              "policy": args.policy, "policy_version": policy_version}
    if baseline is not None:
        base_eval = evaluate(challenges, solutions, baseline)
        combined, _ = combine_pools(challenges, baseline, symbolic, policy=args.policy,
                                     run_id=symbolic["run_id"] + "-fixed")
        fixed_eval = evaluate(challenges, solutions, combined)
        report.update(baseline=base_eval, fixed_slots=fixed_eval,
                      union=exact_union_metrics(base_eval, symbolic_eval), paired=paired(base_eval, fixed_eval))
    args.output.mkdir(parents=True)
    write_new(args.output / "evaluation-local-only.json", canonical_bytes(report))
    aggregates = {key: None if report[key] is None else report[key]["development_metrics"]
                  for key in ("symbolic", "baseline", "fixed_slots")}
    brief = {"format": report["format"], "purpose": report["purpose"], "qualification": report["qualification"],
             "challenges_digest": digest_value(challenges), "metrics": aggregates, "union": report["union"],
             "policy": args.policy, "policy_version": policy_version, "symbolic_pool_digest": digest_value(symbolic),
             "baseline_pool_digest": None if baseline is None else digest_value(baseline)}
    write_new(args.output / "aggregate-brief.json", canonical_bytes(brief))
    print(canonical_bytes(brief).decode())


if __name__ == "__main__":
    main()
