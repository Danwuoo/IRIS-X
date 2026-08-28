#!/usr/bin/env python3
"""Run the Phase 3 read-only Document Ops narrow-control baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = EXPERIMENT_ROOT / "runs"
SOURCE_PREFIX = ROOT / "sources" / "predecessors" / "vanta" / "docs" / "04_experiments" / "fixtures" / "document_ops"
LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class DefinitionError(ValueError):
    """Raised when an experiment definition violates the frozen contract."""


@dataclass
class ReadTracker:
    bytes_read: int = 0
    read_count: int = 0

    def read_bytes(self, path: Path) -> bytes:
        payload = path.read_bytes()
        self.bytes_read += len(payload)
        self.read_count += 1
        return payload

    def read_text(self, path: Path) -> str:
        return self.read_bytes(path).decode("utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def is_within(path: Path, boundary: Path) -> bool:
    resolved = path.resolve()
    root = boundary.resolve()
    return resolved == root or root in resolved.parents


def resolve_repo_path(value: str, label: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise DefinitionError(f"{label} must be a non-empty repository-relative path")
    candidate = (ROOT / value).resolve()
    if not is_within(candidate, ROOT):
        raise DefinitionError(f"{label} escapes the repository: {value}")
    return candidate


def relative_posix(path: Path, boundary: Path) -> str:
    return path.resolve().relative_to(boundary.resolve()).as_posix()


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def validate_definitions(manifest: Any, configurations: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise DefinitionError("task manifest schema_version must be 1")
    if manifest.get("distribution_id") != "taskdist-2026-08-28-vanta-docops-readonly-12":
        raise DefinitionError("unexpected distribution_id")
    if manifest.get("contract_id") != "contract-2026-08-28-docops-readonly-12":
        raise DefinitionError("unexpected contract_id")
    if manifest.get("source_id") != "src.vanta":
        raise DefinitionError("manifest source_id must be src.vanta")
    if manifest.get("sampling") != "enumerated-fixed":
        raise DefinitionError("manifest sampling must be enumerated-fixed")

    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 12:
        raise DefinitionError("task manifest must enumerate exactly 12 tasks")
    task_ids: set[str] = set()
    valid_kinds = {"traceability", "inconsistencies", "structure", "contract_result"}
    for index, row in enumerate(tasks):
        if not isinstance(row, dict):
            raise DefinitionError(f"tasks[{index}] must be an object")
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise DefinitionError(f"tasks[{index}].task_id is invalid")
        if task_id in task_ids:
            raise DefinitionError(f"duplicate task_id: {task_id}")
        task_ids.add(task_id)
        if row.get("output_kind") not in valid_kinds:
            raise DefinitionError(f"{task_id}: unsupported output_kind")
        fixture = resolve_repo_path(row.get("fixture_path"), f"{task_id}.fixture_path")
        if not is_within(fixture, SOURCE_PREFIX):
            raise DefinitionError(f"{task_id}: fixture_path is outside the selected VANTA boundary")
        if not fixture.is_dir():
            raise DefinitionError(f"{task_id}: fixture directory is missing")
        expected = (fixture / row.get("expected_path", "")).resolve()
        if not is_within(expected, fixture) or not expected.is_file():
            raise DefinitionError(f"{task_id}: expected_path is missing or escapes the fixture")
        task_path = fixture / "task.json"
        task = load_json(task_path)
        if task.get("task_id") != task_id:
            raise DefinitionError(f"{task_id}: task.json ID mismatch")
        if task.get("side_effect_classes") != ["READ_ONLY"]:
            raise DefinitionError(f"{task_id}: first-cycle tasks must be exactly READ_ONLY")
        expected_payload = load_json(expected)
        if not isinstance(expected_payload, dict):
            raise DefinitionError(f"{task_id}: expected output must be a JSON object")

    if not isinstance(configurations, dict) or configurations.get("schema_version") != 1:
        raise DefinitionError("configuration schema_version must be 1")
    if configurations.get("experiment_id") != "exp-2026-08-28-docops-readonly-baseline":
        raise DefinitionError("unexpected experiment_id in configurations")
    configs = configurations.get("configurations")
    if not isinstance(configs, list) or len(configs) != 2:
        raise DefinitionError("exactly two configurations are required")
    expected_impl = {
        "literal-readonly-v0": "builtin:literal",
        "structured-readonly-v0": "builtin:structured",
    }
    for config in configs:
        config_id = config.get("id") if isinstance(config, dict) else None
        if config_id not in expected_impl or config.get("implementation") != expected_impl[config_id]:
            raise DefinitionError(f"unsupported configuration: {config_id}")
        if config.get("network_access") is not False or config.get("external_tools") != []:
            raise DefinitionError(f"{config_id}: network and external tools must be disabled")
        for field in ("max_retries", "max_repairs", "max_escalations", "max_recoveries"):
            if config.get(field) != 0:
                raise DefinitionError(f"{config_id}: {field} must be zero")
    return tasks, configs


def declared_inputs(fixture: Path, task: dict[str, Any]) -> list[tuple[str, str, Path]]:
    inputs: list[tuple[str, str, Path]] = []
    for index, artifact in enumerate(task.get("input_artifacts", [])):
        rel = artifact.get("path")
        role = artifact.get("role", "unknown")
        if not isinstance(rel, str):
            raise DefinitionError(f"{task.get('task_id')}: input_artifacts[{index}].path is invalid")
        path = (fixture / rel).resolve()
        if not is_within(path, fixture) or not path.is_file():
            raise DefinitionError(f"{task.get('task_id')}: input path is missing or escapes fixture: {rel}")
        inputs.append((rel.replace("\\", "/"), str(role), path))
    if not inputs:
        raise DefinitionError(f"{task.get('task_id')}: no declared input artifacts")
    return inputs


def input_snapshot(inputs: list[tuple[str, str, Path]]) -> list[dict[str, Any]]:
    return [
        {"path": rel, "role": role, "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for rel, role, path in inputs
    ]


def evidence_and_cache(
    inputs: list[tuple[str, str, Path]], tracker: ReadTracker
) -> tuple[list[dict[str, str]], dict[str, bytes]]:
    evidence: list[dict[str, str]] = []
    cache: dict[str, bytes] = {}
    for rel, _role, path in inputs:
        payload = tracker.read_bytes(path)
        cache[rel] = payload
        evidence.append({"path": rel, "sha256": sha256_bytes(payload)})
    return evidence, cache


def source_texts(
    inputs: list[tuple[str, str, Path]], cache: dict[str, bytes], *, include_context: bool = False
) -> list[tuple[str, str]]:
    selected: list[tuple[str, str]] = []
    for rel, role, _path in inputs:
        if role == "source" or (include_context and role == "context"):
            selected.append((rel, cache[rel].decode("utf-8")))
    return selected


def solve_traceability(inputs: list[tuple[str, str, Path]], cache: dict[str, bytes]) -> dict[str, Any]:
    links: list[dict[str, str]] = []
    for _rel, text in source_texts(inputs, cache):
        links.extend({"label": match.group(1), "target": match.group(2)} for match in LINK_RE.finditer(text))
    return {"links": links}


def solve_inconsistencies(inputs: list[tuple[str, str, Path]], cache: dict[str, bytes]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    for rel, text in source_texts(inputs, cache):
        if "evidence package" in text:
            findings.append({"canonical": "Evidence Packet", "observed": "evidence package", "path": rel})
    return {"inconsistencies": findings}


def parse_headings(text: str) -> tuple[list[str], list[dict[str, Any]]]:
    lines = text.splitlines()
    headings: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match:
            headings.append({"level": len(match.group(1)), "text": match.group(2), "line": line_number})
    return lines, headings


def section_end(headings: list[dict[str, Any]], index: int, line_count: int) -> int:
    level = headings[index]["level"]
    for later in headings[index + 1 :]:
        if later["level"] <= level:
            return later["line"] - 1
    return line_count


def solve_structure(task_id: str, inputs: list[tuple[str, str, Path]], cache: dict[str, bytes]) -> dict[str, Any]:
    sources = source_texts(inputs, cache)
    if len(sources) != 1:
        raise ValueError("structure handler requires exactly one source input")
    _rel, text = sources[0]
    lines, headings = parse_headings(text)
    if task_id == "docops_struct_inspect_001":
        selectors: list[dict[str, Any]] = []
        for name, whole_section in (("Scope", False), ("Evidence", True)):
            matches = [(index, heading) for index, heading in enumerate(headings) if heading["text"] == name]
            if len(matches) != 1:
                selectors.append({"status": "missing" if not matches else "ambiguous"})
                continue
            index, heading = matches[0]
            end = section_end(headings, index, len(lines)) if whole_section else heading["line"]
            selectors.append(
                {"status": "resolved", "target": {"start_line": heading["line"], "end_line": end}}
            )
        return {"structure": {"line_count": len(lines), "headings": headings}, "selector_results": selectors}
    if task_id == "docops_ps1_traceability_structured_outline_001":
        matches = [heading for heading in headings if heading["text"] == "Specs" and heading["level"] == 2]
        status = "resolved" if len(matches) == 1 else ("missing" if not matches else "ambiguous")
        return {
            "structure": {"format": "markdown", "line_count": len(lines), "headings": headings},
            "selector_results": [{"status": status, "match_count": len(matches)}],
        }
    raise ValueError(f"unsupported structure task: {task_id}")


def contract_failures(text: str, contract: dict[str, Any]) -> list[dict[str, Any]]:
    _lines, headings = parse_headings(text)
    failures: list[dict[str, Any]] = []
    for required in contract.get("required_headings", []):
        if not any(
            heading["text"] == required.get("text") and heading["level"] == required.get("level")
            for heading in headings
        ):
            failures.append({"code": "required_heading_missing", "detail": required})
    for required_text in contract.get("required_text", []):
        if required_text not in text:
            failures.append({"code": "required_text_missing", "detail": {"text": required_text}})
    for forbidden in contract.get("forbidden_terms", []):
        if forbidden in text:
            failures.append({"code": "forbidden_term_present", "detail": {"text": forbidden}})
    return failures


def solve_contract(task_id: str, inputs: list[tuple[str, str, Path]], cache: dict[str, bytes]) -> dict[str, Any]:
    sources = source_texts(inputs, cache)
    if len(sources) != 1:
        raise ValueError("contract handler requires exactly one source input")
    _rel, text = sources[0]
    if task_id == "docops_struct_contract_pass_001":
        contract_rel = next((rel for rel, role, _path in inputs if role == "contract"), None)
        if contract_rel is None:
            raise ValueError("contract input is missing")
        contract = json.loads(cache[contract_rel].decode("utf-8"))
    elif task_id == "docops_struct_contract_fail_001":
        contract = {"required_headings": [{"text": "Rollback", "level": 2}]}
    elif task_id == "docops_ps1_terms_contract_inline_001":
        contract = {"required_text": ["Evidence Packet", "Verifier Runtime"]}
    else:
        raise ValueError(f"unsupported contract task: {task_id}")
    failures = contract_failures(text, contract)
    return {"passed": not failures, "failures": failures}


def invoke_control(
    config: dict[str, Any], row: dict[str, Any], task: dict[str, Any], fixture: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    tracker = ReadTracker()
    inputs = declared_inputs(fixture, task)
    evidence, cache = evidence_and_cache(inputs, tracker)
    output_kind = row["output_kind"]
    supported = output_kind in config["supported_output_kinds"]
    handler = "unsupported"
    observation: dict[str, Any] | None = None
    claimed_outcome = "failure"
    refusal_reason: str | None = f"output kind {output_kind} is outside this configuration's repertoire"
    if supported:
        if output_kind == "traceability":
            handler = "markdown-link-extractor"
            observation = solve_traceability(inputs, cache)
        elif output_kind == "inconsistencies":
            handler = "evidence-packet-alias-check"
            observation = solve_inconsistencies(inputs, cache)
        elif output_kind == "structure":
            handler = "markdown-structure-inspector"
            observation = solve_structure(task["task_id"], inputs, cache)
        elif output_kind == "contract_result":
            handler = "document-contract-validator"
            observation = solve_contract(task["task_id"], inputs, cache)
        claimed_outcome = "success"
        refusal_reason = None
    envelope = {
        "task_id": task["task_id"],
        "configuration_id": config["id"],
        "claimed_outcome": claimed_outcome,
        "observation": observation,
        "evidence": evidence,
        "handler": handler,
        "refusal_reason": refusal_reason,
        "execution_path": {"retry_count": 0, "repair_count": 0, "escalation_count": 0, "recovery_count": 0},
    }
    resources = {
        "bytes_read": tracker.bytes_read,
        "tool_read_count": tracker.read_count,
        "output_bytes": len(canonical_json_bytes(envelope)),
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "model_api_cost_usd": 0.0,
        "model_fields_applicability": "Not applicable",
    }
    return envelope, resources


def has_exact_overlap(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict) and isinstance(actual, dict):
        return any(key in actual and has_exact_overlap(value, actual[key]) for key, value in expected.items())
    if isinstance(expected, list) and isinstance(actual, list):
        return any(item in actual for item in expected)
    return expected == actual


def evidence_status(envelope: dict[str, Any], before: list[dict[str, Any]]) -> str:
    expected = {(item["path"], item["sha256"]) for item in before}
    observed_raw = envelope.get("evidence")
    if not isinstance(observed_raw, list):
        return "insufficient"
    observed = {
        (item.get("path"), item.get("sha256"))
        for item in observed_raw
        if isinstance(item, dict)
    }
    return "sufficient" if observed == expected and len(observed_raw) == len(expected) else "insufficient"


def joint_status(actual: str, claim: str, evidence: str) -> str:
    if actual == "success" and claim == "success":
        return "verified_success" if evidence == "sufficient" else "unverified_success"
    if actual == "success" and claim in {"partial", "failure"}:
        return "false_failure"
    if actual in {"partial", "failure"} and claim == "success":
        return "false_success"
    if actual == "failure" and claim == "failure" and evidence == "sufficient":
        return "correctly_recognized_failure"
    if actual == "partial" and claim == "partial" and evidence == "sufficient":
        return "correctly_recognized_partial"
    return "unresolved_joint_status"


def evaluate_episode(
    envelope: dict[str, Any], expected: dict[str, Any], before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> tuple[str, str, str, list[str]]:
    reasons: list[str] = []
    mutated = before != after
    if mutated:
        actual = "failure"
        reasons.append("input_mutation_detected")
    elif envelope.get("observation") == expected:
        actual = "success"
    elif isinstance(envelope.get("observation"), dict) and has_exact_overlap(expected, envelope["observation"]):
        actual = "partial"
        reasons.append("observation_incomplete_or_contains_incorrect_additions")
    else:
        actual = "failure"
        reasons.append(envelope.get("refusal_reason") or "no_correct_required_observation")
    evidence = evidence_status(envelope, before)
    if evidence != "sufficient":
        reasons.append("evidence_insufficient")
    joint = joint_status(actual, str(envelope.get("claimed_outcome")), evidence)
    return actual, evidence, joint, reasons


def aggregate(records: list[dict[str, Any]], configs: list[dict[str, Any]], repetitions: int) -> dict[str, Any]:
    by_config: dict[str, Any] = {}
    for config in configs:
        config_id = config["id"]
        subset = [record for record in records if record["configuration_id"] == config_id]
        valid = [record for record in subset if record["episode_status"] == "valid"]
        outcomes = {name: sum(record["actual_outcome"] == name for record in valid) for name in ("success", "partial", "failure")}
        joint_counts: dict[str, int] = defaultdict(int)
        for record in valid:
            joint_counts[record["joint_status"]] += 1
        repeat_disagreements: list[str] = []
        for task_id in sorted({record["task_id"] for record in valid}):
            task_records = [record for record in valid if record["task_id"] == task_id]
            signatures = {
                canonical_json_bytes({"outcome": record["actual_outcome"], "observation": record["produced"]["observation"]})
                for record in task_records
            }
            if len(task_records) != repetitions or len(signatures) != 1:
                repeat_disagreements.append(task_id)
        by_config[config_id] = {
            "attempted_episodes": len(subset),
            "valid_episodes": len(valid),
            "invalid_episodes": len(subset) - len(valid),
            "outcomes": outcomes,
            "task_success_rate": outcomes["success"] / len(valid) if valid else None,
            "joint_status_counts": dict(sorted(joint_counts.items())),
            "operational_repeatability": {
                "tasks_with_repeat_disagreement": repeat_disagreements,
                "repeat_agreement_task_count": 12 - len(repeat_disagreements),
            },
            "measured_cost_totals": {
                "generation_wall_ms": sum(record["resources"]["generation_wall_ms"] for record in valid),
                "generation_process_cpu_ms": sum(record["resources"]["generation_process_cpu_ms"] for record in valid),
                "evaluation_wall_ms": sum(record["resources"]["evaluation_wall_ms"] for record in valid),
                "bytes_read": sum(record["resources"]["bytes_read"] for record in valid),
                "output_bytes": sum(record["resources"]["output_bytes"] for record in valid),
                "tool_read_count": sum(record["resources"]["tool_read_count"] for record in valid),
                "model_calls": 0,
                "model_api_cost_usd": 0.0,
            },
        }
    return {
        "schema_version": 1,
        "experiment_id": "exp-2026-08-28-docops-readonly-baseline",
        "episode_count": len(records),
        "configurations": by_config,
        "reliability_dimensions": {
            "operational_reliability": "evaluated within the fixed same-environment repetition horizon",
            "robustness": "Not evaluated",
            "stateful_reliability": "Not evaluated",
            "change_reliability_maintainability": "Not evaluated",
            "recovery_reliability": "Not evaluated",
        },
        "lifecycle_cost_boundary": {
            "measured": [
                "generation wall time",
                "generation process CPU time",
                "evaluation wall time",
                "bytes read",
                "output bytes",
                "tool/read count",
                "execution-path counts",
                "harness failures",
            ],
            "unknown": [
                "electricity",
                "hardware depreciation",
                "development and specialization labor",
                "fixture-authoring labor",
                "maintenance and remediation labor",
                "external failure impact",
            ],
            "not_applicable_to_baseline_controls": ["model tokens", "model calls", "model/API charges"],
            "amortization": "No deployment-volume amortization; 72-episode pilot workload only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--configurations", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--run-id")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    manifest_path = resolve_repo_path(args.manifest, "--manifest")
    configurations_path = resolve_repo_path(args.configurations, "--configurations")
    manifest = load_json(manifest_path)
    configurations = load_json(configurations_path)
    tasks, configs = validate_definitions(manifest, configurations)
    if args.validate_only:
        print("definition validation: PASS (12 tasks, 2 configurations)")
        return 0
    if not args.output_dir or not args.run_id:
        parser.error("--output-dir and --run-id are required unless --validate-only is used")
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")

    output_dir = resolve_repo_path(args.output_dir, "--output-dir")
    if not is_within(output_dir, RUNS_ROOT):
        raise DefinitionError("--output-dir must be under this experiment's runs directory")
    if output_dir.exists():
        raise DefinitionError(f"output directory already exists: {relative_posix(output_dir, ROOT)}")

    started_at = utc_now()
    command = [sys.executable, *sys.argv]
    git_commit = git_output("rev-parse", "HEAD")
    git_status_before = git_output("status", "--short")
    source_tree = git_output("rev-parse", f"{git_commit}:sources/predecessors/vanta")
    source_status_before = git_output("status", "--short", "--", "sources", "references/papers")
    output_dir.mkdir(parents=True)
    raw_path = output_dir / "raw" / "episodes.jsonl"
    raw_path.parent.mkdir()

    records: list[dict[str, Any]] = []
    with raw_path.open("w", encoding="utf-8", newline="\n") as raw_stream:
        for config in configs:
            for repetition in range(1, args.repetitions + 1):
                for row in tasks:
                    fixture = resolve_repo_path(row["fixture_path"], f"{row['task_id']}.fixture_path")
                    task = load_json(fixture / "task.json")
                    expected = load_json((fixture / row["expected_path"]).resolve())
                    inputs = declared_inputs(fixture, task)
                    before = input_snapshot(inputs)
                    episode_started = utc_now()
                    wall_start = time.perf_counter_ns()
                    cpu_start = time.process_time_ns()
                    episode_status = "valid"
                    terminal_error: dict[str, str] | None = None
                    try:
                        produced, resources = invoke_control(config, row, task, fixture)
                    except Exception as exc:  # terminal failure evidence is retained
                        produced = {
                            "task_id": row["task_id"],
                            "configuration_id": config["id"],
                            "claimed_outcome": "failure",
                            "observation": None,
                            "evidence": [],
                            "handler": "harness-exception",
                            "refusal_reason": "harness exception",
                            "execution_path": {
                                "retry_count": 0,
                                "repair_count": 0,
                                "escalation_count": 0,
                                "recovery_count": 0,
                            },
                        }
                        resources = {
                            "bytes_read": 0,
                            "tool_read_count": 0,
                            "output_bytes": len(canonical_json_bytes(produced)),
                            "model_calls": 0,
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "model_api_cost_usd": 0.0,
                            "model_fields_applicability": "Not applicable",
                        }
                        episode_status = "invalid"
                        terminal_error = {"type": type(exc).__name__, "message": str(exc)}
                    generation_cpu_ms = (time.process_time_ns() - cpu_start) / 1_000_000
                    generation_wall_ms = (time.perf_counter_ns() - wall_start) / 1_000_000
                    evaluation_start = time.perf_counter_ns()
                    after = input_snapshot(inputs)
                    actual, evidence, joint, reasons = evaluate_episode(produced, expected, before, after)
                    evaluation_wall_ms = (time.perf_counter_ns() - evaluation_start) / 1_000_000
                    if before != after:
                        episode_status = "invalid"
                        terminal_error = {"type": "SourceMutation", "message": "selected fixture input changed"}
                    resources.update(
                        {
                            "generation_wall_ms": generation_wall_ms,
                            "generation_process_cpu_ms": generation_cpu_ms,
                            "evaluation_wall_ms": evaluation_wall_ms,
                        }
                    )
                    record = {
                        "schema_version": 1,
                        "run_id": args.run_id,
                        "episode_started_at": episode_started,
                        "task_id": row["task_id"],
                        "stratum": row["stratum"],
                        "output_kind": row["output_kind"],
                        "configuration_id": config["id"],
                        "repetition": repetition,
                        "episode_status": episode_status,
                        "actual_outcome": actual,
                        "claimed_outcome": produced["claimed_outcome"],
                        "evidence_status": evidence,
                        "joint_status": joint,
                        "outcome_reasons": reasons,
                        "produced": produced,
                        "expected": expected,
                        "input_snapshot_before": before,
                        "input_snapshot_after": after,
                        "resources": resources,
                        "terminal_error": terminal_error,
                    }
                    records.append(record)
                    raw_stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                    raw_stream.flush()
                    if episode_status == "invalid" and terminal_error and terminal_error["type"] == "SourceMutation":
                        raise RuntimeError("imported source mutation detected; run stopped")

    source_status_after = git_output("status", "--short", "--", "sources", "references/papers")
    expected_episode_count = len(tasks) * len(configs) * args.repetitions
    results = aggregate(records, configs, args.repetitions)
    results.update(
        {
            "run_id": args.run_id,
            "expected_episode_count": expected_episode_count,
            "complete_episode_count": len(records),
            "run_status": (
                "complete"
                if len(records) == expected_episode_count
                and not any(record["episode_status"] == "invalid" for record in records)
                and source_status_before == source_status_after == ""
                else "invalid"
            ),
        }
    )
    run_manifest = {
        "schema_version": 1,
        "run_id": args.run_id,
        "experiment_id": "exp-2026-08-28-docops-readonly-baseline",
        "status": results["run_status"],
        "started_at": started_at,
        "finished_at": utc_now(),
        "command": command,
        "working_directory": str(ROOT),
        "git_commit": git_commit,
        "git_status_before": git_status_before.splitlines(),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "os_name": os.name,
        "manifest_path": relative_posix(manifest_path, ROOT),
        "manifest_sha256": sha256_file(manifest_path),
        "configurations_path": relative_posix(configurations_path, ROOT),
        "configurations_sha256": sha256_file(configurations_path),
        "distribution_id": manifest["distribution_id"],
        "contract_id": manifest["contract_id"],
        "source_id": manifest["source_id"],
        "source_snapshot_id": manifest["source_snapshot_id"],
        "source_tree_oid_at_code_commit": source_tree,
        "source_status_before": source_status_before.splitlines(),
        "source_status_after": source_status_after.splitlines(),
        "repetitions": args.repetitions,
        "expected_episode_count": expected_episode_count,
        "network_access": False,
        "external_services": [],
        "paid_cost_usd": 0.0,
        "resource_envelope": {
            "model_calls_per_episode": 0,
            "configuration_invocations_per_episode": 1,
            "retries": 0,
            "repairs": 0,
            "escalations": 0,
            "recoveries": 0,
            "execution": "sequential local Python standard library",
        },
    }
    write_json(output_dir / "run-manifest.json", run_manifest)
    write_json(output_dir / "results.json", results)
    print(
        f"baseline run: {results['run_status'].upper()} "
        f"({len(records)}/{expected_episode_count} episodes, output={relative_posix(output_dir, ROOT)})"
    )
    return 0 if results["run_status"] == "complete" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DefinitionError, OSError, RuntimeError, json.JSONDecodeError, UnicodeError) as exc:
        print(f"baseline run: FAIL ({exc})", file=sys.stderr)
        raise SystemExit(1)
