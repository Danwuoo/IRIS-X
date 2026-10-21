"""Gold-free official ARC challenge -> submission.json using the public SFT141 baseline."""
import argparse
import json
import sys

from .controller import verify
from .supervisor import supervised_run as run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    execute = commands.add_parser("run", help="one original clock, one model load, no retries or resume")
    execute.add_argument("--challenge", required=True)
    execute.add_argument("--model-dir", required=True, help="existing exact public 8-file model; never downloaded")
    execute.add_argument("--run-dir", required=True, help="new immutable evidence directory")
    execute.add_argument("--output-dir", required=True, help="new exclusive bundle directory")
    execute.add_argument("--budget-seconds", type=float, default=7200.)
    execute.add_argument("--fallback", choices=("fail", "copy-input"), default="fail")
    check = commands.add_parser("verify", help="no model: replay sealed raw answers and verify export")
    check.add_argument("--run-dir", required=True)
    check.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            result = run(args.challenge, args.model_dir, args.run_dir, args.output_dir,
                         budget_seconds=args.budget_seconds, fallback=args.fallback)
        else:
            analysis = verify(args.run_dir, args.output_dir)
            result = {"verified": True, "counts": analysis["counts"],
                      "execution_kind": analysis["execution_kind"], "scientific_complete": False}
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        if args.command == "run" and result["stop_reason"] == "controller-interrupted":
            return 130
        return 0 if args.command == "verify" or result["whole_budget_met"] else 4
    except (OSError, ValueError, TypeError, RuntimeError, RecursionError) as exc:
        print(f"public solver rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
