"""Validate frozen Phase 6 Batch 1 definitions, fixtures, and optional run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import assess_pressure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-run", type=Path)
    args = parser.parse_args(argv)
    try:
        gate_map, vocabulary, _ = assess_pressure.load_definitions()
        cases = assess_pressure.load_cases(gate_map, vocabulary)
        assessments = assess_pressure.assess_all(cases, gate_map, vocabulary)
        if args.validate_run is not None:
            assess_pressure.validate_authoritative_run(args.validate_run)
    except (assess_pressure.DefinitionError, assess_pressure.AssessmentError, OSError) as exc:
        print(f"capability-pressure validation: FAIL ({exc})", file=sys.stderr)
        return 1
    pressure = sum(item["suite"] == "synthetic_pressure" for item in assessments)
    boundaries = sum(item["suite"] == "attribution_boundaries" for item in assessments)
    replays = sum(item["suite"] == "historical_replay" for item in assessments)
    suffix = " and authoritative run" if args.validate_run is not None else ""
    print(
        "capability-pressure validation: PASS "
        f"({len(gate_map)} gates, {pressure} pressure, {boundaries} attribution, "
        f"{replays} replay cases{suffix})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
