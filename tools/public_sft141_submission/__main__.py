"""Offline format-only export/verification. Never submits, scores or runs a model."""

import argparse
import json
from pathlib import Path
import sys

from .contract import (CLOSURE_SCHEMA, STRATEGIES, build_submission, canonical,
                       digest, read_diagnostic, read_frozen, validate_challenge)
from .files import load_json, publish_bundle, read_bytes, safe_path


def prepare(args):
    if args.strategy_chosen_before_gold is not True:
        raise ValueError("explicit --strategy-chosen-before-gold declaration is required")
    challenge, challenge_raw = load_json(args.challenge)
    validate_challenge(challenge)
    candidates, candidate_raw = load_json(args.candidates)
    hashes = {"challenge_sha256": digest(challenge_raw),
              "candidate_source_sha256": digest(candidate_raw)}
    if args.source_format == "frozen":
        if args.plan is not None or args.seal is not None:
            raise ValueError("plan/seal are only supported with diagnostic source format")
        rows, verification = read_frozen(candidates, challenge, hashes["challenge_sha256"], args.strategy)
    else:
        if args.plan is None or args.seal is None:
            raise ValueError("diagnostic source requires --plan and --seal")
        plan, plan_raw = load_json(args.plan)
        seal, seal_raw = load_json(args.seal)
        hashes.update(plan_sha256=digest(plan_raw), seal_sha256=digest(seal_raw))
        rows, verification = read_diagnostic(candidates, challenge, plan, seal,
                                            hashes["candidate_source_sha256"], args.strategy)
    submission, counts, queries = build_submission(challenge, rows, fallback=args.fallback)
    output = canonical(submission)
    closure = {"schema": CLOSURE_SCHEMA, "source_format": args.source_format,
               "source_hashes": hashes, "submission_sha256": digest(output),
               "strategy": args.strategy, "strategy_chosen_before_gold": True,
               "strategy_timing_evidence": "operator-declaration-not-independent-attestation",
               "fallback_policy": args.fallback, "format_complete": True,
               "candidate_coverage_complete": counts["fallback_queries"] == 0,
               "source_verification": verification, "counts": counts, "queries": queries,
               "accuracy_evaluated": False, "scientific_complete": False,
               "official_submission_performed": False,
               "qualification": "Format and identity checks only. Duplicated attempts are not distinct evidence. Fallback counts are not accuracy. No gold is read; no model or API is invoked."}
    return output, canonical(closure), closure


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("export", "verify"))
    parser.add_argument("--challenge", required=True, help="gold-free official task-ID challenge JSON")
    parser.add_argument("--candidates", required=True, help="frozen candidates or diagnostic result JSON")
    parser.add_argument("--source-format", choices=("frozen", "diagnostic"), default="frozen")
    parser.add_argument("--strategy", choices=STRATEGIES, required=True)
    parser.add_argument("--strategy-chosen-before-gold", action="store_true", required=True,
                        help="attest strategy was fixed before inspecting evaluation gold; not independently provable here")
    parser.add_argument("--fallback", choices=("fail", "copy-input"), default="fail")
    parser.add_argument("--plan", help="gold-free diagnostic plan; must match whole challenge")
    parser.add_argument("--seal", help="exited-worker result seal; integrity is not scientific verification")
    parser.add_argument("--output-dir", required=True, help="new directory on export; existing bundle on verify")
    args = parser.parse_args(argv)
    try:
        directory = safe_path(args.output_dir)
        output, closure_raw, closure = prepare(args)
        if args.command == "export":
            publish_bundle(directory, output, closure_raw)
        else:
            if read_bytes(directory / "submission.json") != output:
                raise ValueError("submission bytes differ from recomputed canonical source-bound output")
            if read_bytes(directory / "closure.json") != closure_raw:
                raise ValueError("closure bytes differ from recomputed complete source/output binding")
        print(json.dumps({"command": args.command, "format_complete": True,
                          "candidate_coverage_complete": closure["candidate_coverage_complete"],
                          "counts": closure["counts"], "submission_sha256": closure["submission_sha256"],
                          "accuracy_evaluated": False, "official_submission_performed": False}, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        print(f"submission contract rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
