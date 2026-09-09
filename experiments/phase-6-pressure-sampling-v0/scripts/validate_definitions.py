#!/usr/bin/env python3
"""Generate and validate the frozen Phase 6 Batch 2 definition surface."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import derive_direct_predicates as predicates  # noqa: E402
import pressure_tasks as tasks  # noqa: E402
import provider_schema  # noqa: E402


BASELINE_SHA = "07a71392a59f78e41ca32f1c9c377e2a43be41e6"
PROFILE_PATH = REPOSITORY_ROOT / "experiments/substrates/model-execution-qualification-v0/admission/codex-cli-0.147.0-run-03-profile.json"
PROFILE_SHA256 = "ab21119f80141456e7327e276fa3e470abf288cf6a3535ac5fceeace68302033"
MANIFEST_PATH = EXPERIMENT_ROOT / "definition/sample-manifest.json"
NEGATIVE_CORPUS_PATH = EXPERIMENT_ROOT / "fixtures/verifier-negative-outputs/negative-corpus.json"
PROTECTED_PATHS = (
    "irisx/core",
    "sources",
    "references/papers",
    "experiments/capability-pressure-attribution-v0",
    "experiments/substrates/model-execution-qualification-v0",
)


class DefinitionError(ValueError):
    """The frozen Batch 2 definition surface is invalid."""


def git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=REPOSITORY_ROOT, check=True, text=True,
        encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def definition_artifacts() -> dict[str, dict[str, Any]]:
    names = (
        "task-feature-schema.json", "direct-predicate-schema.json",
        "predicate-derivation-rules.json", "failure-attribution-rules.json",
        "negative-control-policy.json", "launch-policy.json",
        "provider-response-schema-policy.json",
    )
    result = {}
    for name in names:
        path = EXPERIMENT_ROOT / "definition" / name
        content = path.read_bytes()
        result[name] = {
            "path": path.relative_to(EXPERIMENT_ROOT).as_posix(),
            "bytes": len(content), "sha256": tasks.sha256_bytes(content),
        }
    return result


def generate_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "sample_id": "phase-6-pressure-sampling-v0",
        "required_baseline_sha": BASELINE_SHA,
        "allocation": {
            "profile_id": "codex-cli-0.147.0-run-03-admission-v0",
            "profile_path": PROFILE_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
            "profile_sha256": PROFILE_SHA256,
            "provider_slot": "irisx_openai_no_retry",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "medium",
        },
        "protected_tree_ids_at_baseline": {
            path: git("rev-parse", f"{BASELINE_SHA}:{path}") for path in PROTECTED_PATHS
        },
        "definition_artifacts": definition_artifacts(),
        "tasks": [tasks.task_manifest_record(tasks.load_task(key)) for key in tasks.TASK_KEYS],
    }


def _freeze_rule_hashes() -> None:
    payload = predicates.load_object(predicates.RULES_PATH)
    for rule in payload["rules"]:
        rule["derivation_rule_sha256"] = predicates.rule_sha256(rule)
    predicates.RULES_PATH.write_bytes(tasks.pretty_json_bytes(payload))


def write_derived() -> None:
    for key in tasks.TASK_KEYS:
        task = tasks.load_task(key, require_oracle=False)
        (task.root / "oracle.json").write_bytes(tasks.pretty_json_bytes(tasks.derive_oracle(key, task.task_input)))
    _freeze_rule_hashes()
    NEGATIVE_CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    NEGATIVE_CORPUS_PATH.write_bytes(tasks.pretty_json_bytes(tasks.negative_corpus()))
    MANIFEST_PATH.write_bytes(tasks.pretty_json_bytes(generate_manifest()))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DefinitionError(message)


def _count_p6_matches(record: dict[str, Any]) -> int:
    return sum((
        record["fraud_score"] >= 90,
        record["vip"] and record["amount_cents"] >= 50000,
        record["days_overdue"] >= 30,
        (not record["domestic"]) and record["amount_cents"] >= 30000,
        record["expedite"], True,
    ))


def validate_task_constraints(loaded: dict[str, tasks.FrozenPressureTask]) -> None:
    p1 = loaded["p1-selection"]
    _require(12 <= len(p1.task_input["records"]) <= 20, "P1 record count out of bounds")
    _require(p1.contract["features"]["rule_count"] >= 4, "P1 requires at least four constraints")
    _require("disqualifier" in p1.task_input["constraints"], "P1 disqualifier missing")
    p2 = loaded["p2-aggregation"]
    _require(12 <= len(p2.task_input["records"]) <= 20, "P2 record count out of bounds")
    _require(len(p2.task_input["group_order"]) >= 3, "P2 requires at least three groups")
    _require(len(p2.task_input["conditions"]) >= 2, "P2 requires multiple conditions")
    p3 = loaded["p3-ranking"]
    _require(10 <= len(p3.task_input["candidates"]) <= 18, "P3 candidate count out of bounds")
    _require(len(p3.task_input["rank_order"]) >= 3, "P3 requires primary plus two tie-breaks")
    p4 = loaded["p4-dependency"]
    _require(10 <= len(p4.task_input["nodes"]) <= 16, "P4 node count out of bounds")
    _require(p4.contract["features"]["precedence_depth"] >= 3, "P4 branch depth too shallow")
    prerequisite_uses = [parent for row in p4.task_input["nodes"] for parent in row["prerequisites"]]
    _require(len(prerequisite_uses) != len(set(prerequisite_uses)), "P4 shared prerequisite absent")
    p5 = loaded["p5-reconciliation"]
    _require(p5.task_input["left"] and p5.task_input["right"], "P5 requires two record sets")
    _require("sum_amount_cents" in p5.task_input["duplicate_rule"], "P5 duplicate rule missing")
    _require(any(
        len([row for row in p5.task_input[side] if row["id"] == record_id]) > 1
        for side in ("left", "right")
        for record_id in {row["id"] for row in p5.task_input[side]}
    ), "P5 duplicate rule is not exercised")
    p6 = loaded["p6-rule-precedence"]
    _require(8 <= len(p6.task_input["records"]) <= 14, "P6 record count out of bounds")
    _require(len(p6.task_input["rules_in_precedence_order"]) >= 5, "P6 requires at least five rules")
    _require(sum(_count_p6_matches(row) >= 3 for row in p6.task_input["records"]) >= 2, "P6 lacks multiple-match precedence cases")


def validate() -> dict[str, Any]:
    _require(tasks.sha256_bytes(PROFILE_PATH.read_bytes()) == PROFILE_SHA256, "admission profile hash drift")
    loaded = {key: tasks.load_task(key) for key in tasks.TASK_KEYS}
    _require(len({task.contract["task_id"] for task in loaded.values()}) == 6, "task IDs are not unique")
    _require(len({task.contract["semantic_family"] for task in loaded.values()}) == 6, "semantic families are not distinct")
    validate_task_constraints(loaded)
    provider_schema_policy = provider_schema.load_policy()
    for key, task in loaded.items():
        provider_schema.validate_provider_schema(task.schema, policy=provider_schema_policy)
        _require(task.oracle == tasks.derive_oracle(key, task.task_input), f"oracle mismatch: {key}")
        _require(json.dumps(task.oracle, sort_keys=True) not in task.program, f"oracle leaked into program: {key}")
        _require(tasks.verify_raw_output(task, json.dumps(task.oracle))["semantic_valid"], f"oracle rejected: {key}")
    corpus = tasks.load_object(NEGATIVE_CORPUS_PATH)
    _require(corpus == tasks.negative_corpus(), "negative corpus is not deterministic")
    for task_entry in corpus["tasks"]:
        task = loaded[task_entry["task_key"]]
        for case in task_entry["cases"]:
            result = tasks.verify_raw_output(task, case["raw_output"])
            _require(result["status"] == case["expected_status"], f"negative case mismatch: {task.key}/{case['case_id']}")
    rule_definitions = predicates.load_object(predicates.RULES_PATH)
    _require(len({rule["derivation_rule_id"] for rule in rule_definitions["rules"]}) == len(rule_definitions["rules"]), "derivation rule IDs are not unique")
    for rule in rule_definitions["rules"]:
        predicates.validate_rule_hash(rule)
    expected_gates = {"H-G1", "H-W1", "H-C1", "H-R1", "persistence", "nondeterministic-verifier", "external-action", "retry-recovery"}
    _require({gate["gate_id"] for gate in rule_definitions["gates"]} == expected_gates, "gate inventory mismatch")
    launch_policy = tasks.load_object(EXPERIMENT_ROOT / "definition/launch-policy.json")
    _require(launch_policy["policy_id"] == "phase-6-batch-3-launch-policy-v0", "launch policy identity drift")
    _require(launch_policy["profile_id"] == "codex-cli-0.147.0-run-03-admission-v0", "profile identity drift")
    _require(launch_policy["provider_schema_preflight_required"] is True, "provider schema preflight disabled")
    _require(
        launch_policy["provider_response_schema_policy_id"] == provider_schema_policy["policy_id"],
        "provider schema policy binding drift",
    )
    for field in ("retries", "routes", "fallbacks", "recovery_actions", "external_actions", "model_judges", "stronger_allocations"):
        _require(launch_policy[field] == 0, f"forbidden launch policy count: {field}")
    _require(launch_policy["batch_model_call_ceiling"] == 6, "batch call ceiling drift")
    _require(launch_policy["per_task_model_call_ceiling"] == 1, "task call ceiling drift")
    negative_policy = tasks.load_object(EXPERIMENT_ROOT / "definition/negative-control-policy.json")
    _require(negative_policy["negative_control_semantics"] == "insufficient_by_itself", "negative-control semantics drift")
    _require(negative_policy["separately_proven_positive_remains_positive"] is True, "negative control became a veto")
    manifest = tasks.load_object(MANIFEST_PATH)
    _require(manifest == generate_manifest(), "sample manifest is not deterministic or hashes drifted")
    feature_schema = tasks.load_object(EXPERIMENT_ROOT / "definition/task-feature-schema.json")
    required_features = set(feature_schema["required"])
    for record in manifest["tasks"]:
        _require(set(record["features"]) == required_features, f"task feature fields mismatch: {record['task_key']}")
    for path in PROTECTED_PATHS:
        _require(git("rev-parse", f"HEAD:{path}") == git("rev-parse", f"{BASELINE_SHA}:{path}"), f"protected tree changed: {path}")
    return {
        "status": "PASS", "task_count": len(loaded),
        "negative_case_count": sum(len(row["cases"]) for row in corpus["tasks"]),
        "derivation_rule_count": len(rule_definitions["rules"]),
        "provider_schema_policy_id": provider_schema_policy["policy_id"],
        "provider_schema_valid_count": len(loaded),
        "protected_tree_count": len(PROTECTED_PATHS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-derived", action="store_true")
    args = parser.parse_args()
    try:
        if args.write_derived:
            write_derived()
        print(json.dumps(validate(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (DefinitionError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"Phase 6 Batch 2 definition validation: FAIL ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
