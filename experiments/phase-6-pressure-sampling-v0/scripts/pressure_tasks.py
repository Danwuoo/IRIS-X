#!/usr/bin/env python3
"""Deterministic task definitions, oracles, prompts, and exact verifiers."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TASKS_ROOT = EXPERIMENT_ROOT / "tasks"
TASK_KEYS = (
    "p1-selection",
    "p2-aggregation",
    "p3-ranking",
    "p4-dependency",
    "p5-reconciliation",
    "p6-rule-precedence",
)
REQUIRED_TASK_FILES = (
    "contract.json",
    "input.json",
    "output-schema.json",
    "program.txt",
    "oracle.json",
)


class PressureTaskError(ValueError):
    """A frozen task or result is malformed or inconsistent."""


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise PressureTaskError(f"JSON top level must be an object: {path}")
    return value


def _derive_p1(task_input: Mapping[str, Any]) -> dict[str, Any]:
    constraints = task_input["constraints"]
    selected = []
    for record in task_input["records"]:
        if not record["active"]:
            continue
        if record["region"] not in constraints["allowed_regions"]:
            continue
        if record["score"] < constraints["minimum_score"]:
            continue
        if record["category"] in constraints["excluded_categories"]:
            continue
        if record["balance_cents"] > constraints["maximum_balance_cents"]:
            continue
        if record["sanctions_hold"] is constraints["disqualifier"]["sanctions_hold"]:
            continue
        selected.append(record)
    selected.sort(key=lambda row: (-row["score"], row["balance_cents"], row["id"]))
    return {"selected_ids": [row["id"] for row in selected]}


def _derive_p2(task_input: Mapping[str, Any]) -> dict[str, Any]:
    conditions = task_input["conditions"]
    grouped: dict[str, list[int]] = defaultdict(list)
    for record in task_input["records"]:
        if all(record[field] == expected for field, expected in conditions.items()):
            grouped[record["group"]].append(record["amount_cents"])
    groups = []
    for group in task_input["group_order"]:
        amounts = grouped[group]
        if not amounts:
            raise PressureTaskError(f"frozen aggregation group has no qualifying rows: {group}")
        groups.append(
            {
                "group": group,
                "count": len(amounts),
                "total_cents": sum(amounts),
                "min_cents": min(amounts),
                "max_cents": max(amounts),
            }
        )
    return {"groups": groups}


def _derive_p3(task_input: Mapping[str, Any]) -> dict[str, Any]:
    eligibility = task_input["eligibility"]
    candidates = [
        row
        for row in task_input["candidates"]
        if row["active"] is eligibility["active"]
        and row["compliance"] is eligibility["compliance"]
        and row["years"] >= eligibility["minimum_years"]
    ]
    candidates.sort(
        key=lambda row: (-row["score"], row["latency_ms"], -row["completed_jobs"], row["id"])
    )
    return {
        "ranked": [
            {"id": row["id"], "rank": index}
            for index, row in enumerate(candidates[: task_input["top_n"]], start=1)
        ]
    }


def _derive_p4(task_input: Mapping[str, Any]) -> dict[str, Any]:
    prerequisites = {row["id"]: tuple(row["prerequisites"]) for row in task_input["nodes"]}
    if len(prerequisites) != len(task_input["nodes"]):
        raise PressureTaskError("dependency node IDs must be unique")
    included: set[str] = set()

    def include(node_id: str) -> None:
        if node_id not in prerequisites:
            raise PressureTaskError(f"unknown dependency node: {node_id}")
        if node_id in included:
            return
        included.add(node_id)
        for parent in prerequisites[node_id]:
            include(parent)

    for target in task_input["target_ids"]:
        include(target)
    remaining = set(included)
    ordered: list[str] = []
    while remaining:
        available = sorted(
            node for node in remaining if set(prerequisites[node]).issubset(ordered)
        )
        if not available:
            raise PressureTaskError("dependency graph is cyclic or has unresolved prerequisites")
        selected = available[0]
        ordered.append(selected)
        remaining.remove(selected)
    return {"ordered_ids": ordered}


def _aggregate_records(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for row in records:
        totals[row["id"]] += row["amount_cents"]
    return dict(totals)


def _derive_p5(task_input: Mapping[str, Any]) -> dict[str, Any]:
    left = _aggregate_records(task_input["left"])
    right = _aggregate_records(task_input["right"])
    matched: list[str] = []
    mismatched: list[dict[str, Any]] = []
    unmatched_left: list[dict[str, Any]] = []
    unmatched_right: list[dict[str, Any]] = []
    for record_id in sorted(set(left) | set(right)):
        if record_id in left and record_id in right:
            if left[record_id] == right[record_id]:
                matched.append(record_id)
            else:
                mismatched.append(
                    {
                        "id": record_id,
                        "left_cents": left[record_id],
                        "right_cents": right[record_id],
                        "delta_cents": left[record_id] - right[record_id],
                    }
                )
        elif record_id in left:
            unmatched_left.append({"id": record_id, "amount_cents": left[record_id]})
        else:
            unmatched_right.append({"id": record_id, "amount_cents": right[record_id]})
    return {
        "matched": matched,
        "mismatched": mismatched,
        "unmatched_left": unmatched_left,
        "unmatched_right": unmatched_right,
    }


def _winning_rule(record: Mapping[str, Any]) -> tuple[str, str, str]:
    if record["fraud_score"] >= 90:
        return "blocked", "R1", "fraud-threshold"
    if record["vip"] and record["amount_cents"] >= 50000:
        return "priority", "R2", "vip-high-value"
    if record["days_overdue"] >= 30:
        return "collections", "R3", "overdue-30"
    if not record["domestic"] and record["amount_cents"] >= 30000:
        return "review", "R4", "foreign-high-value"
    if record["expedite"]:
        return "express", "R5", "expedite-requested"
    return "standard", "R6", "default"


def _derive_p6(task_input: Mapping[str, Any]) -> dict[str, Any]:
    results = []
    for record in task_input["records"]:
        classification, rule_id, reason_id = _winning_rule(record)
        results.append(
            {
                "id": record["id"],
                "class": classification,
                "rule_id": rule_id,
                "reason_id": reason_id,
            }
        )
    return {"classifications": results}


ORACLE_DERIVERS: dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
    "p1-selection": _derive_p1,
    "p2-aggregation": _derive_p2,
    "p3-ranking": _derive_p3,
    "p4-dependency": _derive_p4,
    "p5-reconciliation": _derive_p5,
    "p6-rule-precedence": _derive_p6,
}


@dataclass(frozen=True)
class FrozenPressureTask:
    key: str
    root: Path
    contract: dict[str, Any]
    task_input: dict[str, Any]
    schema: dict[str, Any]
    program: str
    oracle: dict[str, Any]

    @property
    def prompt(self) -> str:
        return (
            self.program.rstrip()
            + "\n\nTASK INPUT (authoritative local data):\n"
            + json.dumps(self.task_input, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        )

    def file_identity(self, name: str) -> dict[str, Any]:
        path = self.root / name
        content = path.read_bytes()
        return {
            "path": path.relative_to(EXPERIMENT_ROOT).as_posix(),
            "bytes": len(content),
            "sha256": sha256_bytes(content),
        }


def derive_oracle(task_key: str, task_input: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return ORACLE_DERIVERS[task_key](task_input)
    except KeyError as exc:
        raise PressureTaskError(f"unknown task key: {task_key}") from exc


def load_task(task_key: str, *, require_oracle: bool = True) -> FrozenPressureTask:
    if task_key not in TASK_KEYS:
        raise PressureTaskError(f"unknown task key: {task_key}")
    root = TASKS_ROOT / task_key
    oracle_path = root / "oracle.json"
    oracle = load_object(oracle_path) if require_oracle else {}
    task = FrozenPressureTask(
        key=task_key,
        root=root,
        contract=load_object(root / "contract.json"),
        task_input=load_object(root / "input.json"),
        schema=load_object(root / "output-schema.json"),
        program=(root / "program.txt").read_text(encoding="utf-8"),
        oracle=oracle,
    )
    derived = derive_oracle(task_key, task.task_input)
    if require_oracle and derived != task.oracle:
        raise PressureTaskError(f"frozen oracle mismatch: {task_key}")
    return task


def _exact_keys(value: Any, expected: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == expected


def output_shape_valid(task_key: str, value: Any) -> bool:
    if task_key == "p1-selection":
        return _exact_keys(value, {"selected_ids"}) and isinstance(value["selected_ids"], list) and all(
            isinstance(item, str) for item in value["selected_ids"]
        )
    if task_key == "p2-aggregation":
        return _exact_keys(value, {"groups"}) and isinstance(value["groups"], list) and all(
            _exact_keys(item, {"group", "count", "total_cents", "min_cents", "max_cents"})
            and isinstance(item["group"], str)
            and all(isinstance(item[field], int) and not isinstance(item[field], bool) for field in ("count", "total_cents", "min_cents", "max_cents"))
            for item in value["groups"]
        )
    if task_key == "p3-ranking":
        return _exact_keys(value, {"ranked"}) and isinstance(value["ranked"], list) and all(
            _exact_keys(item, {"id", "rank"})
            and isinstance(item["id"], str)
            and isinstance(item["rank"], int)
            and not isinstance(item["rank"], bool)
            for item in value["ranked"]
        )
    if task_key == "p4-dependency":
        return _exact_keys(value, {"ordered_ids"}) and isinstance(value["ordered_ids"], list) and all(
            isinstance(item, str) for item in value["ordered_ids"]
        )
    if task_key == "p5-reconciliation":
        if not _exact_keys(value, {"matched", "mismatched", "unmatched_left", "unmatched_right"}):
            return False
        if not isinstance(value["matched"], list) or not all(isinstance(item, str) for item in value["matched"]):
            return False
        if not isinstance(value["mismatched"], list) or not all(
            _exact_keys(item, {"id", "left_cents", "right_cents", "delta_cents"})
            and isinstance(item["id"], str)
            and all(isinstance(item[field], int) and not isinstance(item[field], bool) for field in ("left_cents", "right_cents", "delta_cents"))
            for item in value["mismatched"]
        ):
            return False
        return all(
            isinstance(value[field], list)
            and all(
                _exact_keys(item, {"id", "amount_cents"})
                and isinstance(item["id"], str)
                and isinstance(item["amount_cents"], int)
                and not isinstance(item["amount_cents"], bool)
                for item in value[field]
            )
            for field in ("unmatched_left", "unmatched_right")
        )
    if task_key == "p6-rule-precedence":
        return _exact_keys(value, {"classifications"}) and isinstance(value["classifications"], list) and all(
            _exact_keys(item, {"id", "class", "rule_id", "reason_id"})
            and all(isinstance(item[field], str) for field in ("id", "class", "rule_id", "reason_id"))
            for item in value["classifications"]
        )
    raise PressureTaskError(f"unknown task key: {task_key}")


def verify_raw_output(task: FrozenPressureTask, raw_text: str | bytes | None) -> dict[str, Any]:
    if isinstance(raw_text, bytes):
        raw_text = raw_text.decode("utf-8", errors="replace")
    if not isinstance(raw_text, str) or not raw_text.strip():
        return {"semantic_valid": False, "status": "missing_result", "reasons": ["missing_result"]}
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {"semantic_valid": False, "status": "malformed_json", "reasons": ["malformed_json"]}
    if not output_shape_valid(task.key, parsed):
        return {"semantic_valid": False, "status": "schema_invalid", "reasons": ["schema_invalid"]}
    if parsed != task.oracle:
        return {
            "semantic_valid": False,
            "status": "semantic_miss",
            "reasons": ["deterministic_oracle_mismatch"],
        }
    return {
        "semantic_valid": True,
        "status": "verified_success",
        "reasons": ["exact_deterministic_oracle_match"],
    }


def _mutated_semantic_value(task: FrozenPressureTask) -> dict[str, Any]:
    value = json.loads(json.dumps(task.oracle))
    if task.key == "p1-selection":
        value["selected_ids"][0] = "wrong-id"
    elif task.key == "p2-aggregation":
        value["groups"][0]["total_cents"] += 1
    elif task.key == "p3-ranking":
        value["ranked"][0]["id"] = "wrong-id"
    elif task.key == "p4-dependency":
        value["ordered_ids"][-1] = "wrong-id"
    elif task.key == "p5-reconciliation":
        value["mismatched"][0]["delta_cents"] += 1
    elif task.key == "p6-rule-precedence":
        value["classifications"][0]["rule_id"] = "R6"
    return value


def _wrong_order_value(task: FrozenPressureTask) -> dict[str, Any]:
    value = json.loads(json.dumps(task.oracle))
    array_field = {
        "p1-selection": "selected_ids",
        "p2-aggregation": "groups",
        "p3-ranking": "ranked",
        "p4-dependency": "ordered_ids",
        "p6-rule-precedence": "classifications",
    }.get(task.key)
    if array_field and len(value[array_field]) > 1:
        value[array_field][0], value[array_field][1] = value[array_field][1], value[array_field][0]
    elif task.key == "p5-reconciliation":
        value["matched"].reverse()
    return value


def negative_cases(task: FrozenPressureTask) -> list[dict[str, Any]]:
    correct = json.dumps(task.oracle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    extra = json.loads(json.dumps(task.oracle))
    extra["unexpected"] = True
    schema_invalid = {next(iter(task.oracle)): "wrong-type"}
    return [
        {"case_id": "correct", "raw_output": correct, "expected_status": "verified_success"},
        {"case_id": "malformed-json", "raw_output": "{not-json", "expected_status": "malformed_json"},
        {"case_id": "schema-invalid", "raw_output": json.dumps(schema_invalid), "expected_status": "schema_invalid"},
        {"case_id": "semantic-error", "raw_output": json.dumps(_mutated_semantic_value(task)), "expected_status": "semantic_miss"},
        {"case_id": "missing-result", "raw_output": "", "expected_status": "missing_result"},
        {"case_id": "extra-result", "raw_output": json.dumps(extra), "expected_status": "schema_invalid"},
        {"case_id": "wrong-order", "raw_output": json.dumps(_wrong_order_value(task)), "expected_status": "semantic_miss"},
        {"case_id": "cross-task-shape", "raw_output": "{\"foreign_result\":[]}", "expected_status": "schema_invalid"},
    ]


def task_manifest_record(task: FrozenPressureTask) -> dict[str, Any]:
    features = dict(task.contract["features"])
    feature_record = {
        "task_id": task.contract["task_id"],
        "semantic_family": task.contract["semantic_family"],
        "input_bytes": len((task.root / "input.json").read_bytes()),
        **features,
        "expected_output_cardinality": task.contract["expected_output_cardinality"],
        "deterministic_oracle_id": task.contract["deterministic_oracle_id"],
    }
    return {
        "task_key": task.key,
        "contract_id": task.contract["contract_id"],
        "program_id": task.contract["program_id"],
        "features": feature_record,
        "artifacts": {name: task.file_identity(name) for name in REQUIRED_TASK_FILES},
        "prompt_sha256": sha256_bytes(task.prompt.encode("utf-8")),
        "prompt_bytes": len(task.prompt.encode("utf-8")),
    }


def sample_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "sample_id": "phase-6-pressure-sampling-v0",
        "required_baseline": "a0ca60de39cc291fb9ad185d7de40cd6b4b5909d",
        "profile_id": "codex-cli-0.147.0-run-03-admission-v0",
        "task_count": len(TASK_KEYS),
        "tasks": [task_manifest_record(load_task(key)) for key in TASK_KEYS],
    }


def negative_corpus() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "corpus_id": "phase-6-batch-2-verifier-negative-corpus-v0",
        "tasks": [
            {"task_key": key, "cases": negative_cases(load_task(key))} for key in TASK_KEYS
        ],
    }
