"""Public-only full-support calibrated solver. No implicit model/data download."""
import argparse
import json
import sys
from . import core
from .controller import verify
from .supervisor import supervised_run
from tools.public_sft141_submission import files, contract as wire


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="gold-free CPU inventory, not measured fit")
    execute = commands.add_parser("run", help="one clock/load, all-support LOO then eight-view generation/common8 NLL")
    for command in (plan, execute):
        command.add_argument("--challenge", required=True)
        command.add_argument("--context-cap", type=int, default=10240)
        command.add_argument("--budget-seconds", type=float, default=14400.)
        command.add_argument("--strategy", choices=core.STRATEGIES, default="vote")
    execute.add_argument("--model-dir", required=True)
    execute.add_argument("--run-dir", required=True)
    execute.add_argument("--output-dir", required=True)
    execute.add_argument("--evaluation-gold", help="optional evaluator-only path, never sent to model leaf")
    execute.add_argument("--original-start-monotonic", type=float)
    execute.add_argument("--original-start-epoch", type=float)
    execute.add_argument("--fallback", choices=("fail", "copy-input"), default="fail")
    check = commands.add_parser("verify", help="strict post-exit raw replay; no model or gold")
    check.add_argument("--run-dir", required=True)
    check.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            challenge, raw = files.load_json(args.challenge)
            result = core.prepare(core.make_plan(challenge, wire.digest(raw), context_cap=args.context_cap,
                budget_seconds=args.budget_seconds, strategy=args.strategy))
        elif args.command == "run":
            result = supervised_run(args.challenge, args.model_dir, args.run_dir, args.output_dir,
                context_cap=args.context_cap, budget_seconds=args.budget_seconds, strategy=args.strategy, fallback=args.fallback, evaluation_gold_path=args.evaluation_gold,
                original_start_monotonic=args.original_start_monotonic, original_start_epoch=args.original_start_epoch)
        else:
            analysis = verify(args.run_dir, args.output_dir)
            result = {"verified": True, "counts": analysis["counts"], "protocol_complete": analysis["protocol_complete"],
                      "execution_kind": analysis["execution_kind"], "scientific_complete": False}
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print(f"public full calibrated solver rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
