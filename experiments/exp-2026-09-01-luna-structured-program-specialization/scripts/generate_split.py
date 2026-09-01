#!/usr/bin/env python3
"""Generate one frozen H-P1a split from an explicit master seed."""

from __future__ import annotations

import argparse
from pathlib import Path

from common import EXPERIMENT, generate_split


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=("dev", "validation", "blind"))
    parser.add_argument("--master-seed", required=True)
    parser.add_argument("--per-family", required=True, type=int)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--definition-commit", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--candidate-freeze-commit")
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    destination = Path(args.destination)
    if not destination.is_absolute():
        destination = EXPERIMENT / destination
    inventory = generate_split(
        args.split,
        args.master_seed,
        args.per_family,
        destination,
        args.candidate_sha,
        args.definition_commit,
        args.code_commit,
        args.candidate_freeze_commit,
    )
    print(f"generated {inventory['split']}: {inventory['total_instances']} valid instances")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
