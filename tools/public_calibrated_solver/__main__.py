"""Explicit offline paired solver. No automatic downloads, submission, or run."""
import argparse
import json
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="freeze gold-free plan and public source bytes; no model load")
    p.add_argument("--plan", required=True)
    p.add_argument("--plan-sha256", required=True)
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--output", required=True)
    r = sub.add_parser("run", help="explicit real run unless --synthetic is provided")
    r.add_argument("--source-lock", required=True)
    r.add_argument("--source-lock-sha256", required=True)
    r.add_argument("--model-dir")
    r.add_argument("--gold", required=True)
    r.add_argument("--gold-sha256", required=True)
    r.add_argument("--output", required=True)
    r.add_argument("--strategy", choices=("vote", "rescored", "demo_weighted"), required=True)
    r.add_argument("--fallback", choices=("fail", "copy-input"), required=True)
    r.add_argument("--budget-seconds", type=float, default=7200)
    r.add_argument("--synthetic", action="store_true")
    r.add_argument("--synthetic-age-seconds", type=float, default=0)
    r.add_argument("--synthetic-fault", choices=("none", "load-fail", "calibration-fail", "generation-fail", "generation-hang", "evaluator-hang", "invalid-pool"), default="none")
    for command in ("_coordinator", "_model", "_evaluate"):
        leaf = sub.add_parser(command, help=argparse.SUPPRESS)
        leaf.add_argument("--intent", required=True)
        leaf.add_argument("--intent-sha256", required=True)
        leaf.add_argument("--output", required=True)
        if command != "_model":
            leaf.add_argument("--gold", required=True)
            leaf.add_argument("--gold-sha256", required=True)
        if command == "_evaluate":
            leaf.add_argument("--evaluation-intent", required=True)
            leaf.add_argument("--evaluation-intent-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "_model":
            from .common import frozen
            from .worker import execute
            return execute(frozen(args.intent, args.intent_sha256), args.output)
        from . import controller
        if args.command == "prepare":
            print(json.dumps(controller.prepare(args.plan, args.plan_sha256, args.output,
                "synthetic_cpu" if args.synthetic else "public_model"), sort_keys=True))
            return 0
        if args.command == "run":
            return controller.run(args)
        if args.command == "_coordinator":
            return controller.coordinate(args)
        return controller.evaluate_leaf(args)
    except (ValueError, OSError, TypeError) as exc:
        print(f"public paired solver rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
