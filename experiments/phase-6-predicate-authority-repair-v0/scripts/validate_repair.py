#!/usr/bin/env python3
"""Validate the bounded post-Batch-3 predicate authority repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPAIR_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPAIR_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import derive_repair as repair  # noqa: E402


RUN_PATH = REPAIR_ROOT / "runs/authority-repair-20260910"
BASELINE_SHA = "fc42646466b697e5723d6ae2db58fafcb8e13448"
PROTECTED_PATHS = (
    "experiments/phase-6-pressure-sampling-v0/runs/batch-2",
    "experiments/phase-6-pressure-sampling-v0/runs/batch-3",
    "experiments/phase-6-pressure-sampling-v0/definition/predicate-derivation-rules.json",
    "research/phase-6-sampling-path-repair-and-requalification.md",
    "docs/phase-6-sampling-path-repair-and-requalification-handoff.md",
    "docs/plans/TEMP_PHASE_6_SAMPLING_PATH_REPAIR_AND_REQUALIFICATION.md",
    "irisx/core",
    "sources",
    "references/papers",
)


class RepairValidationError(ValueError):
    """The repaired authority is incomplete or conflicting."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RepairValidationError(message)


def git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=REPOSITORY_ROOT, check=True, text=True,
        encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(*, require_run: bool = True) -> dict[str, object]:
    definition = repair.load_definition()
    require(definition["required_baseline_sha"] == BASELINE_SHA, "baseline identity drift")
    engine_path = REPOSITORY_ROOT / definition["evaluator_path"]
    require(sha256(engine_path) == definition["evaluator_sha256"], "evaluator identity drift")
    for rule in definition["rules"]:
        repair.engine.validate_rule_hash(rule)

    any_miss_rule = next(
        rule for rule in definition["rules"]
        if rule["predicate_id"] == "cheaper_admitted_configuration_misses_requirement"
    )
    expected_paths = [
        f"runs/batch-3/{key}/terminal-record.json"
        for key in (
            "p1-selection", "p2-aggregation", "p3-ranking", "p4-dependency",
            "p5-reconciliation", "p6-rule-precedence",
        )
    ]
    require(any_miss_rule["operator"] == "any_equals", "any-miss operator is not any_equals")
    require([source["path"] for source in any_miss_rule["sources"]] == expected_paths, "Batch 3 terminal source inventory drift")
    require(all(source["pointer"] == "/attribution/task_level_pressure_observed" for source in any_miss_rule["sources"]), "task pressure pointer drift")

    derived = repair.derive_all()
    require(derived["gate_results"] == repair.EXPECTED_GATE_RESULTS, "gate adjudication drift")
    any_miss = next(
        record for record in derived["predicate_records"]
        if record["predicate_id"] == "cheaper_admitted_configuration_misses_requirement"
    )
    require(any_miss["predicate_value"] == "true", "Batch 3 any-miss predicate is not true")
    require([source["observed_value"] for source in any_miss["source_refs"]] == [False, False, False, True, False, False], "Batch 3 task pressure observations drift")
    require(len(any_miss["source_refs"]) == 6, "not all Batch 3 terminal sources are bound")
    for record in derived["predicate_records"]:
        repair.engine.validate_source_refs(record, source_root=repair.SOURCE_ROOT)
    require(not any(value == "triggered_by_direct_evidence" for value in derived["gate_results"].values()), "architecture gate unexpectedly triggered")

    baseline_commit = git("cat-file", "-t", BASELINE_SHA)
    require(baseline_commit == "commit", "required baseline commit unavailable")
    for path in PROTECTED_PATHS:
        require(git("diff", "--name-only", BASELINE_SHA, "--", path) == "", f"protected path changed: {path}")

    if require_run:
        require(RUN_PATH.is_dir(), "authoritative repair run is absent")
        direct_path = RUN_PATH / "direct-predicates.json"
        gate_path = RUN_PATH / "gate-adjudication.json"
        manifest_path = RUN_PATH / "manifest.json"
        require(direct_path.read_bytes() == repair.engine.pretty_json_bytes(derived), "direct predicates do not regenerate byte-identically")
        require(gate_path.read_bytes() == repair.engine.pretty_json_bytes(repair.build_gate_adjudication(derived)), "gate adjudication does not regenerate byte-identically")
        manifest = repair.engine.load_object(manifest_path)
        require(manifest_path.read_bytes() == repair.engine.pretty_json_bytes(repair.build_manifest(manifest["definition_test_freeze_sha"], derived)), "manifest does not regenerate byte-identically")
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            repair.write_artifacts(first, manifest["definition_test_freeze_sha"])
            repair.write_artifacts(second, manifest["definition_test_freeze_sha"])
            for name in ("direct-predicates.json", "gate-adjudication.json", "manifest.json"):
                require((first / name).read_bytes() == (second / name).read_bytes(), f"double regeneration differs: {name}")

    return {
        "authority_id": definition["authority_id"],
        "batch3_terminal_source_count": 6,
        "direct_evidence_trigger_count": 0,
        "gate_count": 8,
        "historical_batch3_classification": definition["historical_batch3_classification"],
        "model_provider_calls": 0,
        "preserved_path_count": len(PROTECTED_PATHS),
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--definition-only", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(validate(require_run=not args.definition_only), indent=2, sort_keys=True))
        return 0
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"predicate authority repair validation: FAIL ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

