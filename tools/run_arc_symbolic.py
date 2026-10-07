#!/usr/bin/env python3
"""Truth-free bounded CPU DSL execution. No solutions or scoring arguments."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from irisx.arc_candidates_neutral import from_dsl_worker, to_offline_pools, submission_records, validate_challenges
from irisx.arc_symbolic_dsl import GRAMMAR_SPEC, Limits
from irisx.arc_symbolic_runner import solve_isolated
from irisx.canonical import canonical_bytes, digest_value
from tools.arc_kaggle_submission import build_submission, parse_json, require, write_new


def source_identity() -> dict:
    paths = ["src/irisx/arc_symbolic_dsl.py", "src/irisx/arc_symbolic_runner.py",
             "src/irisx/arc_candidates_neutral.py", "tools/run_arc_symbolic.py"]
    return {name: "sha256:" + hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--challenges", type=Path, required=True)
    parser.add_argument("--expected-challenges-digest", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limits", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", args.run_id) is not None, "bounded run ID required")
    start = time.monotonic()
    body = args.challenges.read_bytes()
    challenges = validate_challenges(parse_json(body))
    require(digest_value(challenges) == args.expected_challenges_digest, "challenge digest differs from frozen input")
    limits = Limits(**parse_json(args.limits.read_bytes())) if args.limits else Limits()
    limits.validate()
    code = source_identity()
    source_digest = digest_value(code)
    require(not args.output.exists(), "new output directory required")
    args.output.mkdir(parents=True)
    plan = {"format": "irisx/arc-dsl-run-plan-v1", "run_id": args.run_id,
            "challenge_file_sha256": hashlib.sha256(body).hexdigest(),
            "challenges_digest": digest_value(challenges), "task_ids": list(challenges),
            "task_count": len(challenges), "test_count": sum(len(t["test"]) for t in challenges.values()),
            "limits": asdict(limits), "config_digest": digest_value(asdict(limits)),
            "grammar_digest": digest_value(GRAMMAR_SPEC), "source_code_digest": source_digest,
            "source_files": code, "correctness_scored": False, "test_outputs_received": False}
    write_new(args.output / "plan.json", canonical_bytes(plan))
    records = []
    # Stable original order; each task has one shared cap over all its tests.
    for index, (key, task) in enumerate(challenges.items()):
        write_new(args.output / (f"task-{index:03d}-reserved.json"), canonical_bytes({
            "run_id": args.run_id, "task_id": key, "task_digest": digest_value(task),
            "config_digest": plan["config_digest"], "source_code_digest": source_digest}))
        worker = solve_isolated(task, limits)
        record = from_dsl_worker(key, task, worker, source_digest)
        write_new(args.output / (f"task-{index:03d}.json"), canonical_bytes(record))
        records.append(record)
        print(f"{key}: {worker['status']}, {len(record['candidates'])} candidate vectors", flush=True)
    pools = to_offline_pools(challenges, records, args.run_id, time.monotonic() - start)
    submission, audit = build_submission(challenges, submission_records(challenges, pools))
    write_new(args.output / "pools.json", canonical_bytes(pools))
    write_new(args.output / "selection-records.json", canonical_bytes(records))
    write_new(args.output / "submission-audit.json", canonical_bytes(audit))
    write_new(args.output / "submission.json", canonical_bytes(submission))
    members = {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
               for p in sorted(args.output.iterdir()) if p.is_file()}
    write_new(args.output / "manifest.json", canonical_bytes({"format": "irisx/arc-dsl-run-manifest-v1",
        "run_id": args.run_id, "files": members, "correctness_scored": False}))


if __name__ == "__main__":
    main()
