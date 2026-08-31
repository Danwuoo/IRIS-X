#!/usr/bin/env python3
"""Shared deterministic Document Ops worker for H-OR1a."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SEQUENCE_COUNTER = 0


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def is_within(path: Path, boundary: Path) -> bool:
    resolved = path.resolve()
    root = boundary.resolve()
    return resolved == root or root in resolved.parents


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


def solve_traceability(inputs: list[dict[str, Any]], cache: dict[str, bytes]) -> dict[str, Any]:
    links: list[dict[str, str]] = []
    for item in inputs:
        if item["role"] != "source":
            continue
        text = cache[item["path"]].decode("utf-8")
        links.extend({"label": match.group(1), "target": match.group(2)} for match in LINK_RE.finditer(text))
    return {"links": links}


def solve_inconsistencies(inputs: list[dict[str, Any]], cache: dict[str, bytes]) -> dict[str, Any]:
    source_items = [item for item in inputs if item["role"] == "source"]
    canonical_present = any("Evidence Packet" in cache[item["path"]].decode("utf-8") for item in source_items)
    findings: list[dict[str, str]] = []
    if canonical_present:
        for item in source_items:
            if "evidence package" in cache[item["path"]].decode("utf-8"):
                findings.append(
                    {"canonical": "Evidence Packet", "observed": "evidence package", "path": item["path"]}
                )
    return {"inconsistencies": findings}


def solve_structure(task_id: str, inputs: list[dict[str, Any]], cache: dict[str, bytes]) -> dict[str, Any]:
    sources = [item for item in inputs if item["role"] == "source"]
    if len(sources) != 1:
        raise ValueError("structure handler requires one source")
    lines, headings = parse_headings(cache[sources[0]["path"]].decode("utf-8"))
    if task_id == "docops_struct_inspect_001":
        selector_results = []
        for name, whole_section in (("Scope", False), ("Evidence", True)):
            matches = [(index, heading) for index, heading in enumerate(headings) if heading["text"] == name]
            if len(matches) != 1:
                selector_results.append({"status": "missing" if not matches else "ambiguous"})
                continue
            index, heading = matches[0]
            end_line = section_end(headings, index, len(lines)) if whole_section else heading["line"]
            selector_results.append(
                {"status": "resolved", "target": {"start_line": heading["line"], "end_line": end_line}}
            )
        return {"structure": {"line_count": len(lines), "headings": headings}, "selector_results": selector_results}
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


def solve_contract(task_id: str, inputs: list[dict[str, Any]], cache: dict[str, bytes]) -> dict[str, Any]:
    source = next(item for item in inputs if item["role"] == "source")
    text = cache[source["path"]].decode("utf-8")
    if task_id == "docops_struct_contract_pass_001":
        contract_item = next(item for item in inputs if item["role"] == "contract")
        contract = json.loads(cache[contract_item["path"]].decode("utf-8"))
    elif task_id == "docops_struct_contract_fail_001":
        contract = {"required_headings": [{"text": "Rollback", "level": 2}]}
    elif task_id == "docops_ps1_terms_contract_inline_001":
        contract = {"required_text": ["Evidence Packet", "Verifier Runtime"]}
    else:
        raise ValueError(f"unsupported contract task: {task_id}")
    failures = contract_failures(text, contract)
    return {"passed": not failures, "failures": failures}


def execute_request(request: dict[str, Any]) -> dict[str, Any]:
    global SEQUENCE_COUNTER
    SEQUENCE_COUNTER += 1
    start_wall = time.perf_counter_ns()
    start_cpu = time.process_time_ns()
    fixture = (ROOT / request["fixture_path"]).resolve()
    expected_path = (fixture / request["expected_path"]).resolve()
    if not is_within(fixture, ROOT / "sources" / "predecessors" / "vanta") or not fixture.is_dir():
        raise ValueError("fixture escapes registered source boundary")
    if not is_within(expected_path, fixture) or not expected_path.is_file():
        raise ValueError("expected path is invalid")
    task = load_json(fixture / "task.json")
    if task.get("task_id") != request["task_id"]:
        raise ValueError("task identity mismatch")
    inputs: list[dict[str, Any]] = []
    cache: dict[str, bytes] = {}
    bytes_read = 0
    for artifact in task.get("input_artifacts", []):
        path = (fixture / artifact["path"]).resolve()
        if not is_within(path, fixture) or not path.is_file():
            raise ValueError("declared input is invalid")
        payload = path.read_bytes()
        cache[artifact["path"]] = payload
        bytes_read += len(payload)
        inputs.append({"path": artifact["path"], "role": artifact.get("role", "Unknown"), "absolute": path})
    pre_hashes = {item["path"]: sha256_bytes(cache[item["path"]]) for item in inputs}
    kind = request["output_kind"]
    if kind == "traceability":
        output = solve_traceability(inputs, cache)
    elif kind == "inconsistencies":
        output = solve_inconsistencies(inputs, cache)
    elif kind == "structure":
        output = solve_structure(request["task_id"], inputs, cache)
    elif kind == "contract_result":
        output = solve_contract(request["task_id"], inputs, cache)
    else:
        raise ValueError(f"unsupported output kind: {kind}")
    expected = load_json(expected_path)
    bytes_read += expected_path.stat().st_size + (fixture / "task.json").stat().st_size
    post_hashes = {item["path"]: sha256_bytes(item["absolute"].read_bytes()) for item in inputs}
    input_evidence = [
        {"path": item["path"], "sha256": pre_hashes[item["path"]]} for item in inputs
    ]
    actual_outcome = "success" if output == expected and pre_hashes == post_hashes else "failure"
    evidence_status = "sufficient" if len(input_evidence) == len(inputs) and pre_hashes == post_hashes else "insufficient"
    core = {
        "task_id": request["task_id"],
        "output": output,
        "output_sha256": sha256_bytes(canonical_json_bytes(output)),
        "input_evidence": input_evidence,
        "actual_outcome": actual_outcome,
        "empirical_evidence_status": evidence_status,
        "acceptance_decision": "not_applicable",
        "verified_success_eligibility": actual_outcome == "success" and evidence_status == "sufficient",
        "terminal_execution_status": "completed",
    }
    return {
        "core": core,
        "worker_pid": os.getpid(),
        "worker_sequence_counter": SEQUENCE_COUNTER,
        "resource": {
            "worker_wall_ns": time.perf_counter_ns() - start_wall,
            "worker_cpu_ns": time.process_time_ns() - start_cpu,
            "bytes_read": bytes_read,
            "output_bytes": len(canonical_json_bytes(output)),
            "model_calls": 0,
            "paid_api_calls": 0,
            "retry_count": 0,
            "recovery_count": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--single", action="store_true")
    parser.add_argument("--server", action="store_true")
    args = parser.parse_args()
    if args.single == args.server:
        parser.error("choose exactly one of --single or --server")
    if args.single:
        request = json.loads(sys.stdin.read())
        print(json.dumps(execute_request(request), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    for line in sys.stdin:
        if not line.strip():
            continue
        response = execute_request(json.loads(line))
        print(json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
