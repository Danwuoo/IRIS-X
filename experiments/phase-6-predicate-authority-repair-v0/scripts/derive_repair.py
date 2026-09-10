#!/usr/bin/env python3
"""Derive the post-Batch-3 predicate authority from preserved evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPAIR_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = REPOSITORY_ROOT / "experiments/phase-6-pressure-sampling-v0"
ENGINE_DIR = SOURCE_ROOT / "scripts"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

import derive_direct_predicates as engine  # noqa: E402


RULES_PATH = REPAIR_ROOT / "definition/predicate-derivation-rules.json"
EXPECTED_GATE_RESULTS = {
    "H-G1": "not_triggered",
    "H-W1": "not_triggered",
    "H-C1": "insufficient_or_ambiguous",
    "H-R1": "not_triggered",
    "persistence": "not_triggered",
    "nondeterministic-verifier": "not_triggered",
    "external-action": "not_triggered",
    "retry-recovery": "insufficient_or_ambiguous",
}


def load_definition() -> dict[str, Any]:
    return engine.load_object(RULES_PATH)


def derive_all() -> dict[str, Any]:
    definition = load_definition()
    records = [engine.derive_rule(rule, source_root=SOURCE_ROOT) for rule in definition["rules"]]
    gate_results = {
        gate["gate_id"]: engine.evaluate_gate(gate, records)
        for gate in definition["gates"]
    }
    return {
        "authority_id": definition["authority_id"],
        "gate_results": gate_results,
        "predicate_records": records,
        "schema_version": 1,
    }


def build_gate_adjudication(derived: dict[str, Any]) -> dict[str, Any]:
    definition = load_definition()
    records = {
        (record["gate_id"], record["predicate_id"]): record
        for record in derived["predicate_records"]
    }
    gates = []
    for gate in definition["gates"]:
        predicates = []
        for predicate_id in gate["required_predicates"]:
            record = records[(gate["gate_id"], predicate_id)]
            predicates.append(
                {
                    "derivation_status": record["derivation_status"],
                    "predicate_id": predicate_id,
                    "predicate_value": record["predicate_value"],
                    "source_ref_count": len(record["source_refs"]),
                }
            )
        missing = [
            row["predicate_id"]
            for row in predicates
            if row["predicate_value"] in {"unknown", "conflicting"}
        ]
        gates.append(
            {
                "architecture_experiment_triggered": False,
                "gate_id": gate["gate_id"],
                "gate_status": derived["gate_results"][gate["gate_id"]],
                "missing_or_conflicting_evidence": missing,
                "required_predicates": predicates,
            }
        )
    return {
        "authority_id": definition["authority_id"],
        "direct_evidence_trigger_count": sum(
            value == "triggered_by_direct_evidence"
            for value in derived["gate_results"].values()
        ),
        "gates": gates,
        "historical_batch3_classification": definition["historical_batch3_classification"],
        "model_provider_calls": 0,
        "phase_6_batch_4_status": "NOT started / NOT authorized",
        "schema_version": 1,
    }


def build_manifest(definition_freeze_sha: str, derived: dict[str, Any]) -> dict[str, Any]:
    definition = load_definition()
    any_miss = next(
        record
        for record in derived["predicate_records"]
        if record["predicate_id"] == "cheaper_admitted_configuration_misses_requirement"
    )
    return {
        "authority_definition_path": RULES_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        "authority_definition_sha256": engine.sha256_bytes(RULES_PATH.read_bytes()),
        "authority_id": definition["authority_id"],
        "definition_test_freeze_sha": definition_freeze_sha,
        "evaluator_path": definition["evaluator_path"],
        "evaluator_sha256": definition["evaluator_sha256"],
        "historical_batch3_classification": definition["historical_batch3_classification"],
        "model_provider_calls": 0,
        "preserved_batch3_terminal_sources": any_miss["source_refs"],
        "required_baseline_sha": definition["required_baseline_sha"],
        "schema_version": 1,
    }


def write_artifacts(output_dir: Path, definition_freeze_sha: str) -> None:
    if not (len(definition_freeze_sha) == 40 and all(c in "0123456789abcdef" for c in definition_freeze_sha)):
        raise ValueError("definition freeze SHA must be 40 lowercase hexadecimal characters")
    derived = derive_all()
    if derived["gate_results"] != EXPECTED_GATE_RESULTS:
        raise engine.PredicateDerivationError("gate results differ from bounded repair expectation")
    output_dir.mkdir(parents=True, exist_ok=False)
    artifacts = {
        "direct-predicates.json": derived,
        "gate-adjudication.json": build_gate_adjudication(derived),
        "manifest.json": build_manifest(definition_freeze_sha, derived),
    }
    for name, payload in artifacts.items():
        (output_dir / name).write_bytes(engine.pretty_json_bytes(payload))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--definition-freeze-sha", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        write_artifacts(args.output_dir, args.definition_freeze_sha)
        print(json.dumps({"status": "PASS", "output_dir": args.output_dir.as_posix()}, sort_keys=True))
        return 0
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"predicate authority repair derivation: FAIL ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

