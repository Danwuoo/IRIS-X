"""Gold-free planning/replay, plus an explicit public-model calibration command. No evaluator."""
import argparse
import hashlib
import json
from pathlib import Path

from .core import prepare, rank

MAX_JSON_BYTES = 32 * 1024 * 1024


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read_frozen(path, expected_sha256):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_JSON_BYTES + 1)
    if len(data) > MAX_JSON_BYTES:
        raise ValueError("input JSON exceeds 32 MiB bound")
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("frozen input file SHA-256 mismatch")
    return json.loads(data, object_pairs_hook=_unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON number")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("plan")
    p.add_argument("--max-context", type=int, default=8192)
    p.add_argument("--budget-seconds", type=float, default=7200)
    r = subs.add_parser("rank")
    for name in ("calibration", "pool"):
        r.add_argument("--" + name, required=True)
        r.add_argument("--" + name + "-sha256", required=True)
    run = subs.add_parser("run-calibration", help="Explicit real public-model calibration; no generation/evaluation")
    worker = subs.add_parser("_calibration-worker", help=argparse.SUPPRESS)
    for sub in (run, worker):
        sub.add_argument("--model-dir", required=True)
        sub.add_argument("--budget-seconds", type=float, default=7200)
    worker.add_argument("--started-monotonic", type=float, required=True)
    worker.add_argument("--session-id", required=True)
    for sub in (p, r, run, worker):
        sub.add_argument("--plan", required=True)
        sub.add_argument("--plan-sha256", required=True)
        sub.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    plan = read_frozen(args.plan, args.plan_sha256)
    if args.command == "plan":
        result = prepare(plan, args.max_context, args.budget_seconds)
    elif args.command == "run-calibration":
        from .execution import run
        return run(plan, args.plan, args.plan_sha256, args.model_dir, args.output, args.budget_seconds)
    elif args.command == "_calibration-worker":
        from .execution import worker
        return worker(plan, args.model_dir, args.output, args.budget_seconds, args.started_monotonic, args.session_id)
    else:
        result = rank(plan, read_frozen(args.calibration, args.calibration_sha256),
                      read_frozen(args.pool, args.pool_sha256))
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
