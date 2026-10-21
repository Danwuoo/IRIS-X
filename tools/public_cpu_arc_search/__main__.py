"""Public-only CPU program search. Planning is separate from scientific execution."""

import argparse
import json
import sys

from .runtime import make_plan, run, verify, worker, write_new


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="freeze source/challenge/method/budget; no inference")
    plan.add_argument("--challenge", required=True)
    plan.add_argument("--seconds", required=True, type=float)
    plan.add_argument("--output-plan", required=True)
    execution = sub.add_parser("run", help="Linux only; original pre-dispatch clock required")
    execution.add_argument("--plan", required=True)
    execution.add_argument("--output-dir", required=True)
    execution.add_argument("--started-epoch", required=True, type=float)
    check = sub.add_parser("verify", help="verify an exited-worker artifact; does not score")
    check.add_argument("--output-dir", required=True)
    internal = sub.add_parser("_worker", help=argparse.SUPPRESS)
    internal.add_argument("--plan", required=True)
    internal.add_argument("--output-dir", required=True)
    internal.add_argument("--work-deadline-epoch", required=True, type=float)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            result = make_plan(args.challenge, args.seconds)
            write_new(args.output_plan, result)
            print(json.dumps({"planned": True, "challenge_sha256": result["challenge_sha256"],
                              "source_sha256": result["source_sha256"],
                              "tasks": len(result["inventory"]), "seconds": result["seconds"]}, sort_keys=True))
            return 0
        if args.command == "_worker":
            return worker(args.plan, args.output_dir, args.work_deadline_epoch)
        result = (run(args.plan, args.output_dir, args.started_epoch) if args.command == "run"
                  else verify(args.output_dir))
        print(json.dumps({key: result[key] for key in (
            "status", "search_complete", "sealed_for_scoring", "task_count", "query_count",
            "predicted_query_count", "whole_run_wall_seconds", "accuracy_evaluated")}, sort_keys=True))
        return 0 if result["search_complete"] else 3
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print(f"CPU search rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
