"""Local controller primitives for the bounded ARC prompt search.

DSPy/GEPA and Codex remain optional controller-side dependencies.  This module
does not import them at package import time, so the core IRIS-X runtime remains
dependency-free and Kaggle receives only a frozen instruction and workload.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from typing import Any, Callable, Mapping, Sequence

from .arc_prompt_pilot import (
    BASE_INSTRUCTION,
    BASELINE_JOB_COUNT,
    HOLDOUT_COUNT,
    MAX_GENERATION_INVOCATIONS,
    MAX_PROPOSAL_ATTEMPTS,
    RUN_ID,
    TRIAL_ID,
)
from .canonical import canonical_bytes, digest_value, read_json
from .errors import ValidationError
from .transport import digest_path


LEDGER_FORMAT = "irisx/arc-agi-2-prompt-pilot-search-ledger"
LEDGER_VERSION = "1.0"
DSPY_VERSION = "3.3.1"
GEPA_VERSION = "0.1.4"
CODEX_MODEL = "gpt-5.6-sol"
CODEX_REASONING_EFFORT = "xhigh"
MAX_PROPOSER_INPUT_BYTES = 32 * 1024
MAX_REFLECTIVE_EXAMPLES = 3
MAX_INSTRUCTION_BYTES = 16 * 1024


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    temporary.write_bytes(canonical_bytes(dict(value), newline=True))
    os.replace(temporary, path)


def initialize_ledger(path: Path, baseline_score_path: Path) -> dict[str, Any]:
    if path.exists():
        return load_ledger(path)
    score = read_json(baseline_score_path)
    if score.get("trial_id") != TRIAL_ID or score.get("run_id") != RUN_ID or score.get("holdout") != {"opened": False, "scored": False, "record_count": 0}:
        raise ValidationError("prompt-pilot baseline score is not an unopened bound baseline")
    ledger = {
        "format": LEDGER_FORMAT,
        "format_version": LEDGER_VERSION,
        "trial_id": TRIAL_ID,
        "decision": "0019",
        "created_at_utc": _utc(),
        "updated_at_utc": _utc(),
        "controller": {"state": "idle", "pid": None, "token": None, "started_at_utc": None},
        "dependencies": {
            "dspy": DSPY_VERSION,
            "gepa": GEPA_VERSION,
            "codex_cli_model": CODEX_MODEL,
            "codex_reasoning_effort": CODEX_REASONING_EFFORT,
        },
        "budget": {
            "proposal_attempts_used": 0,
            "proposal_attempts_max": MAX_PROPOSAL_ATTEMPTS,
            "generation_invocations_used": BASELINE_JOB_COUNT,
            "generation_invocations_max": MAX_GENERATION_INVOCATIONS,
        },
        "baseline": {
            "candidate": "B1",
            "instruction": BASE_INSTRUCTION,
            "instruction_digest": digest_value(BASE_INSTRUCTION),
            "run_id": RUN_ID,
            "run_identity_digest": score["bindings"]["run_identity_digest"],
            "outbound_digest": score["bindings"]["outbound_digest"],
            "result_digest": score["bindings"]["result_digest"],
            "score_path": str(baseline_score_path.resolve()),
            "score_digest": digest_path(baseline_score_path),
            "train": score["groups"]["optimization-train"],
            "dev": score["groups"]["selection-dev"],
        },
        "rounds": [],
        "frontier": [{"candidate": "B1", "instruction_digest": digest_value(BASE_INSTRUCTION), "dev_accuracy": score["groups"]["selection-dev"]["accuracy"]}],
        "holdout": {"opened": False, "frozen_candidate": None, "generation_invocations": 0, "result_digest": None},
        "next_action": "propose-round-01",
    }
    validate_ledger(ledger)
    _atomic_write(path, ledger)
    return ledger


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    if ledger.get("format") != LEDGER_FORMAT or ledger.get("format_version") != LEDGER_VERSION or ledger.get("trial_id") != TRIAL_ID or ledger.get("decision") != "0019":
        raise ValidationError("prompt-pilot search ledger identity is invalid")
    budget = ledger.get("budget", {})
    rounds = ledger.get("rounds")
    if not isinstance(rounds, list) or budget.get("proposal_attempts_used") != len(rounds) or budget.get("proposal_attempts_max") != MAX_PROPOSAL_ATTEMPTS:
        raise ValidationError("prompt-pilot proposal ledger count is invalid")
    if len(rounds) > MAX_PROPOSAL_ATTEMPTS:
        raise ValidationError("prompt-pilot proposal budget is exceeded")
    if budget.get("generation_invocations_max") != MAX_GENERATION_INVOCATIONS:
        raise ValidationError("prompt-pilot generation ceiling changed")
    used = budget.get("generation_invocations_used")
    if not isinstance(used, int) or not BASELINE_JOB_COUNT <= used <= MAX_GENERATION_INVOCATIONS:
        raise ValidationError("prompt-pilot generation use is invalid")
    seen_rounds: set[int] = set()
    seen_instructions = {ledger.get("baseline", {}).get("instruction_digest")}
    for index, item in enumerate(rounds, start=1):
        if item.get("round") != index or index in seen_rounds:
            raise ValidationError("prompt-pilot ledger rounds are not contiguous")
        seen_rounds.add(index)
        digest = item.get("candidate_instruction_digest")
        if digest is not None and item.get("duplicate") is False:
            if digest in seen_instructions:
                raise ValidationError("prompt-pilot ledger marks a duplicate instruction as new")
            seen_instructions.add(digest)
    holdout = ledger.get("holdout", {})
    if holdout.get("opened") is False and holdout.get("generation_invocations") != 0:
        raise ValidationError("prompt-pilot holdout accounting is inconsistent")


def load_ledger(path: Path) -> dict[str, Any]:
    ledger = read_json(path)
    if path.read_bytes() != canonical_bytes(ledger, newline=True):
        raise ValidationError("prompt-pilot search ledger is not canonical")
    validate_ledger(ledger)
    return ledger


def save_ledger(path: Path, ledger: Mapping[str, Any]) -> None:
    updated = dict(ledger)
    updated["updated_at_utc"] = _utc()
    validate_ledger(updated)
    _atomic_write(path, updated)


def begin_proposal_attempt(path: Path, *, parent_candidate: str, parent_instruction: str) -> dict[str, Any]:
    ledger = load_ledger(path)
    budget = ledger["budget"]
    if budget["proposal_attempts_used"] >= budget["proposal_attempts_max"]:
        raise ValidationError("prompt-pilot proposal budget is exhausted")
    round_index = budget["proposal_attempts_used"] + 1
    item = {
        "round": round_index,
        "parent_candidate": parent_candidate,
        "parent_instruction_digest": digest_value(parent_instruction),
        "proposal_status": "running",
        "proposal_started_at_utc": _utc(),
        "proposal_wall_seconds": None,
        "proposal_input_digest": None,
        "proposal_output_digest": None,
        "failure_hypothesis": None,
        "expected_improvement": None,
        "candidate": f"G{round_index}",
        "candidate_instruction": None,
        "candidate_instruction_digest": None,
        "duplicate": None,
        "gpu_status": "not-started",
        "run_id": None,
        "run_identity_digest": None,
        "configuration_digest": None,
        "kernel_ref": None,
        "kernel_version": None,
        "dataset_version": None,
        "incidents": [],
        "outbound_digest": None,
        "result_digest": None,
        "score_digest": None,
        "score_path": None,
        "train": None,
        "dev": None,
        "generation_invocations": 0,
        "retrieval_attempted": False,
        "kernel_submitted_at_utc": None,
        "kernel_terminal_at_utc": None,
        "timings": {"transport_seconds": 0.0, "queue_wait_seconds": 0.0, "gpu_runtime_seconds": 0.0, "retrieval_seconds": 0.0},
        "next_action": "finish-proposal",
    }
    ledger["rounds"].append(item)
    budget["proposal_attempts_used"] = round_index
    ledger["next_action"] = f"finish-proposal-round-{round_index:02d}"
    save_ledger(path, ledger)
    return item


def record_candidate_staged(
    path: Path,
    *,
    round_index: int,
    run_id: str,
    run_identity_digest: str,
    configuration_digest: str,
    outbound_digest: str,
    dataset_version: int,
) -> dict[str, Any]:
    ledger = load_ledger(path)
    item = ledger["rounds"][round_index - 1]
    if item["round"] != round_index or item["proposal_status"] != "valid" or item["duplicate"] is not False or item["gpu_status"] != "not-started":
        raise ValidationError("prompt-pilot candidate cannot be staged from its current state")
    item.update({
        "gpu_status": "staged",
        "run_id": run_id,
        "run_identity_digest": run_identity_digest,
        "configuration_digest": configuration_digest,
        "outbound_digest": outbound_digest,
        "dataset_version": dataset_version,
        "next_action": f"upload-dataset-round-{round_index:02d}",
    })
    ledger["next_action"] = item["next_action"]
    save_ledger(path, ledger)
    return item


def record_dataset_uploaded(path: Path, *, round_index: int, transport_seconds: float) -> dict[str, Any]:
    ledger = load_ledger(path)
    item = ledger["rounds"][round_index - 1]
    if item["gpu_status"] != "staged":
        raise ValidationError("prompt-pilot Dataset upload is out of order")
    item["gpu_status"] = "dataset-ready"
    item["timings"]["transport_seconds"] += transport_seconds
    item["next_action"] = f"submit-kernel-round-{round_index:02d}"
    ledger["next_action"] = item["next_action"]
    save_ledger(path, ledger)
    return item


def reconcile_duplicate_dataset_versions(
    path: Path,
    *,
    round_index: int,
    observed_version: int,
    duplicate_versions: Sequence[int],
    evidence_path: Path,
) -> dict[str, Any]:
    """Recover a staged candidate after identical Dataset versions were uploaded.

    This transition is deliberately narrow: it may only advance a staged item,
    every duplicate must be at or above the originally planned version, and the
    observed ready version must be the last duplicate.  The caller retains a
    canonical incident record binding the bytes and remote observations.
    """

    ledger = load_ledger(path)
    item = ledger["rounds"][round_index - 1]
    expected_version = item.get("dataset_version")
    versions = list(duplicate_versions)
    if (
        item.get("gpu_status") != "staged"
        or not isinstance(expected_version, int)
        or not versions
        or versions != sorted(set(versions))
        or versions[0] != expected_version
        or versions[-1] != observed_version
        or not evidence_path.is_file()
    ):
        raise ValidationError("prompt-pilot Dataset reconciliation evidence is invalid")
    incident = {
        "type": "duplicate-identical-dataset-versions",
        "recorded_at_utc": _utc(),
        "planned_version": expected_version,
        "duplicate_versions": versions,
        "recovered_version": observed_version,
        "evidence_path": str(evidence_path.resolve()),
        "evidence_digest": digest_path(evidence_path),
        "kernel_submitted": False,
        "generation_invocations": 0,
    }
    item.setdefault("incidents", []).append(incident)
    item["dataset_version"] = observed_version
    item["gpu_status"] = "dataset-ready"
    item["next_action"] = f"submit-kernel-round-{round_index:02d}"
    ledger["next_action"] = item["next_action"]
    save_ledger(path, ledger)
    return item


def record_kernel_submission_planned(
    path: Path,
    *,
    round_index: int,
    kernel_ref: str,
    kernel_version: int,
    transport_seconds: float,
) -> dict[str, Any]:
    ledger = load_ledger(path)
    item = ledger["rounds"][round_index - 1]
    if item["gpu_status"] != "dataset-ready" or item["generation_invocations"] != 0:
        raise ValidationError("prompt-pilot kernel submission is duplicated or out of order")
    if ledger["budget"]["generation_invocations_used"] + BASELINE_JOB_COUNT > MAX_GENERATION_INVOCATIONS:
        raise ValidationError("prompt-pilot generation ceiling would be exceeded")
    item.update({"gpu_status": "submitting", "kernel_ref": kernel_ref, "kernel_version": kernel_version, "generation_invocations": BASELINE_JOB_COUNT, "next_action": f"push-kernel-round-{round_index:02d}"})
    item["timings"]["transport_seconds"] += transport_seconds
    ledger["budget"]["generation_invocations_used"] += BASELINE_JOB_COUNT
    ledger["next_action"] = item["next_action"]
    save_ledger(path, ledger)
    return item


def record_kernel_submission_rejected(
    path: Path,
    *,
    round_index: int,
    evidence_path: Path,
) -> dict[str, Any]:
    """Release a pre-reserved generation budget after a definitive API reject."""

    ledger = load_ledger(path)
    item = ledger["rounds"][round_index - 1]
    if (
        item.get("gpu_status") != "submitting"
        or item.get("generation_invocations") != BASELINE_JOB_COUNT
        or not isinstance(item.get("kernel_version"), int)
        or not evidence_path.is_file()
    ):
        raise ValidationError("prompt-pilot kernel rejection evidence is invalid")
    incident = {
        "type": "kernel-api-rejected-before-creation",
        "recorded_at_utc": _utc(),
        "kernel_ref": item["kernel_ref"],
        "kernel_version": item["kernel_version"],
        "reserved_generation_invocations_released": BASELINE_JOB_COUNT,
        "evidence_path": str(evidence_path.resolve()),
        "evidence_digest": digest_path(evidence_path),
    }
    item.setdefault("incidents", []).append(incident)
    item.update({
        "gpu_status": "dataset-ready",
        "kernel_ref": None,
        "kernel_version": None,
        "generation_invocations": 0,
        "next_action": f"submit-kernel-round-{round_index:02d}",
    })
    ledger["budget"]["generation_invocations_used"] -= BASELINE_JOB_COUNT
    ledger["next_action"] = item["next_action"]
    save_ledger(path, ledger)
    return item


def record_kernel_accepted(path: Path, *, round_index: int, transport_seconds: float) -> dict[str, Any]:
    ledger = load_ledger(path)
    item = ledger["rounds"][round_index - 1]
    if item["gpu_status"] != "submitting":
        raise ValidationError("prompt-pilot kernel acceptance is out of order")
    item.update({"gpu_status": "running", "kernel_submitted_at_utc": _utc(), "next_action": f"wait-kernel-round-{round_index:02d}"})
    item["timings"]["transport_seconds"] += transport_seconds
    ledger["next_action"] = item["next_action"]
    save_ledger(path, ledger)
    return item


def record_kernel_terminal(path: Path, *, round_index: int, terminal_status: str) -> dict[str, Any]:
    ledger = load_ledger(path)
    item = ledger["rounds"][round_index - 1]
    if item["gpu_status"] != "running" or terminal_status not in {"complete", "error", "cancelled"}:
        raise ValidationError("prompt-pilot kernel terminal transition is invalid")
    item.update({"gpu_status": terminal_status, "kernel_terminal_at_utc": _utc(), "next_action": f"retrieve-kernel-round-{round_index:02d}"})
    ledger["next_action"] = item["next_action"]
    save_ledger(path, ledger)
    return item


def record_retrieval_planned(path: Path, *, round_index: int) -> dict[str, Any]:
    ledger = load_ledger(path)
    item = ledger["rounds"][round_index - 1]
    if item["gpu_status"] not in {"complete", "error"} or item["retrieval_attempted"]:
        raise ValidationError("prompt-pilot output retrieval is duplicated or out of order")
    item["retrieval_attempted"] = True
    item["next_action"] = f"retrieval-in-progress-round-{round_index:02d}"
    ledger["next_action"] = item["next_action"]
    save_ledger(path, ledger)
    return item


def record_retrieval_cli_recovery(path: Path, *, round_index: int, evidence_path: Path) -> dict[str, Any]:
    """Retain a CLI-print failure that did not prevent a valid local result."""

    ledger = load_ledger(path)
    item = ledger["rounds"][round_index - 1]
    if item.get("gpu_status") not in {"complete", "error", "scored"} or not item.get("retrieval_attempted") or not evidence_path.is_file():
        raise ValidationError("prompt-pilot retrieval recovery evidence is invalid")
    incidents = item.setdefault("incidents", [])
    if any(entry.get("type") == "retrieval-cli-encoding-after-download" for entry in incidents):
        return item
    incidents.append({
        "type": "retrieval-cli-encoding-after-download",
        "recorded_at_utc": _utc(),
        "evidence_path": str(evidence_path.resolve()),
        "evidence_digest": digest_path(evidence_path),
        "second_retrieval_attempted": False,
    })
    save_ledger(path, ledger)
    return item


def record_candidate_scored(
    path: Path,
    *,
    round_index: int,
    result_digest: str,
    score_path: Path,
    gpu_runtime_seconds: float,
    queue_wait_seconds: float,
    retrieval_seconds: float,
) -> dict[str, Any]:
    ledger = load_ledger(path)
    item = ledger["rounds"][round_index - 1]
    if item["gpu_status"] not in {"complete", "error"} or not item["retrieval_attempted"]:
        raise ValidationError("prompt-pilot candidate result is out of order")
    score = read_json(score_path)
    if score.get("run_id") != item["run_id"] or score.get("bindings", {}).get("instruction_digest") != item["candidate_instruction_digest"]:
        raise ValidationError("prompt-pilot candidate score differs from the ledger binding")
    item.update({
        "gpu_status": "scored",
        "result_digest": result_digest,
        "score_digest": digest_path(score_path),
        "score_path": str(score_path.resolve()),
        "train": score["groups"]["optimization-train"],
        "dev": score["groups"]["selection-dev"],
        "next_action": "continue-gepa",
    })
    item["timings"].update({"gpu_runtime_seconds": gpu_runtime_seconds, "queue_wait_seconds": queue_wait_seconds, "retrieval_seconds": retrieval_seconds})
    ledger["frontier"].append({"candidate": item["candidate"], "instruction_digest": item["candidate_instruction_digest"], "dev_accuracy": item["dev"]["accuracy"]})
    ledger["next_action"] = "continue-gepa"
    save_ledger(path, ledger)
    return item


def freeze_final_candidate(path: Path) -> dict[str, Any]:
    """Freeze G* by dev exact match with earliest-candidate tie breaking."""

    ledger = load_ledger(path)
    if ledger["budget"]["proposal_attempts_used"] != MAX_PROPOSAL_ATTEMPTS:
        raise ValidationError("prompt-pilot final candidate requires all proposal attempts")
    unresolved = [item["candidate"] for item in ledger["rounds"] if item["proposal_status"] == "running" or (item["proposal_status"] == "valid" and item["duplicate"] is False and item["gpu_status"] != "scored")]
    if unresolved:
        raise ValidationError(f"prompt-pilot candidates remain unresolved: {unresolved}")
    candidates = [("B1", ledger["baseline"]["instruction"], ledger["baseline"]["instruction_digest"], ledger["baseline"]["dev"]["accuracy"], 0)]
    candidates.extend(
        (item["candidate"], item["candidate_instruction"], item["candidate_instruction_digest"], item["dev"]["accuracy"], item["round"])
        for item in ledger["rounds"]
        if item.get("gpu_status") == "scored"
    )
    candidate, instruction, instruction_digest, dev_accuracy, order = max(candidates, key=lambda value: (value[3], -value[4]))
    ledger["holdout"].update({
        "status": "selected",
        "opened": False,
        "frozen_candidate": candidate,
        "instruction": instruction,
        "instruction_digest": instruction_digest,
        "selection_dev_accuracy": dev_accuracy,
        "selection_order": order,
        "generation_invocations": 0,
        "run_id": None,
        "run_identity_digest": None,
        "outbound_digest": None,
        "dataset_version": None,
        "kernel_ref": None,
        "kernel_version": None,
        "retrieval_attempted": False,
        "result_digest": None,
        "score_path": None,
        "score_digest": None,
        "locked_holdout": None,
        "next_action": "plan-final-holdout-opening",
    })
    ledger["next_action"] = "plan-final-holdout-opening"
    save_ledger(path, ledger)
    return ledger["holdout"]


def record_holdout_opening_planned(path: Path) -> dict[str, Any]:
    ledger = load_ledger(path)
    holdout = ledger["holdout"]
    if holdout.get("status") != "selected" or holdout.get("opened") or holdout.get("frozen_candidate") != "B1":
        raise ValidationError("prompt-pilot B1-only holdout cannot be opened")
    holdout.update({"status": "opening", "opened": True, "next_action": "build-final-holdout"})
    ledger["next_action"] = holdout["next_action"]
    save_ledger(path, ledger)
    return holdout


def record_holdout_staged(
    path: Path,
    *,
    run_id: str,
    run_identity_digest: str,
    outbound_digest: str,
    dataset_version: int,
) -> dict[str, Any]:
    ledger = load_ledger(path)
    holdout = ledger["holdout"]
    if holdout.get("status") != "opening" or not holdout.get("opened"):
        raise ValidationError("prompt-pilot holdout staging is out of order")
    holdout.update({
        "status": "staged",
        "run_id": run_id,
        "run_identity_digest": run_identity_digest,
        "outbound_digest": outbound_digest,
        "dataset_version": dataset_version,
        "next_action": "upload-final-holdout-dataset",
    })
    ledger["next_action"] = holdout["next_action"]
    save_ledger(path, ledger)
    return holdout


def record_holdout_dataset_uploaded(path: Path) -> dict[str, Any]:
    ledger = load_ledger(path)
    holdout = ledger["holdout"]
    if holdout.get("status") != "staged":
        raise ValidationError("prompt-pilot holdout Dataset upload is out of order")
    holdout.update({"status": "dataset-ready", "next_action": "submit-final-holdout-kernel"})
    ledger["next_action"] = holdout["next_action"]
    save_ledger(path, ledger)
    return holdout


def record_holdout_kernel_submission_planned(path: Path, *, kernel_ref: str, kernel_version: int) -> dict[str, Any]:
    ledger = load_ledger(path)
    holdout = ledger["holdout"]
    if holdout.get("status") != "dataset-ready" or holdout.get("generation_invocations") != 0:
        raise ValidationError("prompt-pilot holdout kernel submission is duplicated or out of order")
    if ledger["budget"]["generation_invocations_used"] + HOLDOUT_COUNT > MAX_GENERATION_INVOCATIONS:
        raise ValidationError("prompt-pilot final holdout would exceed the generation ceiling")
    holdout.update({"status": "submitting", "kernel_ref": kernel_ref, "kernel_version": kernel_version, "generation_invocations": HOLDOUT_COUNT, "next_action": "push-final-holdout-kernel"})
    ledger["budget"]["generation_invocations_used"] += HOLDOUT_COUNT
    ledger["next_action"] = holdout["next_action"]
    save_ledger(path, ledger)
    return holdout


def record_holdout_kernel_accepted(path: Path) -> dict[str, Any]:
    ledger = load_ledger(path)
    holdout = ledger["holdout"]
    if holdout.get("status") != "submitting":
        raise ValidationError("prompt-pilot holdout kernel acceptance is out of order")
    holdout.update({"status": "running", "next_action": "wait-final-holdout-kernel"})
    ledger["next_action"] = holdout["next_action"]
    save_ledger(path, ledger)
    return holdout


def record_holdout_kernel_terminal(path: Path, *, terminal_status: str) -> dict[str, Any]:
    ledger = load_ledger(path)
    holdout = ledger["holdout"]
    if holdout.get("status") != "running" or terminal_status not in {"complete", "error", "cancelled"}:
        raise ValidationError("prompt-pilot holdout terminal transition is invalid")
    holdout.update({"status": terminal_status, "next_action": "retrieve-final-holdout"})
    ledger["next_action"] = holdout["next_action"]
    save_ledger(path, ledger)
    return holdout


def record_holdout_retrieval_planned(path: Path) -> dict[str, Any]:
    ledger = load_ledger(path)
    holdout = ledger["holdout"]
    if holdout.get("status") not in {"complete", "error"} or holdout.get("retrieval_attempted"):
        raise ValidationError("prompt-pilot holdout retrieval is duplicated or out of order")
    holdout.update({"retrieval_attempted": True, "next_action": "final-holdout-retrieval-in-progress"})
    ledger["next_action"] = holdout["next_action"]
    save_ledger(path, ledger)
    return holdout


def record_holdout_scored(path: Path, *, result_digest: str, score_path: Path) -> dict[str, Any]:
    ledger = load_ledger(path)
    holdout = ledger["holdout"]
    if holdout.get("status") not in {"complete", "error"} or not holdout.get("retrieval_attempted"):
        raise ValidationError("prompt-pilot holdout score is out of order")
    score = read_json(score_path)
    summary = score.get("groups", {}).get("locked-holdout")
    if score.get("selected_candidate") != holdout.get("frozen_candidate") or not isinstance(summary, dict) or summary.get("denominator") != HOLDOUT_COUNT:
        raise ValidationError("prompt-pilot holdout score differs from the frozen selection")
    holdout.update({
        "status": "scored",
        "result_digest": result_digest,
        "score_path": str(score_path.resolve()),
        "score_digest": digest_path(score_path),
        "locked_holdout": summary,
        "next_action": "complete",
    })
    ledger["next_action"] = "complete"
    save_ledger(path, ledger)
    return holdout


def finish_proposal_attempt(
    path: Path,
    *,
    instruction: str | None,
    status: str,
    wall_seconds: float,
    input_digest: str,
    output_digest: str | None,
    failure_hypothesis: str | None = None,
    expected_improvement: str | None = None,
) -> dict[str, Any]:
    ledger = load_ledger(path)
    item = ledger["rounds"][-1]
    if item["proposal_status"] != "running":
        raise ValidationError("prompt-pilot proposal is not running")
    if status not in {"valid", "invalid", "failed"}:
        raise ValidationError("prompt-pilot proposal terminal status is invalid")
    duplicate = None
    instruction_digest = None
    if status == "valid":
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction.encode("utf-8")) > MAX_INSTRUCTION_BYTES:
            raise ValidationError("prompt-pilot proposed instruction is invalid")
        instruction = instruction.strip()
        instruction_digest = digest_value(instruction)
        existing = {ledger["baseline"]["instruction_digest"]}
        existing.update(entry["candidate_instruction_digest"] for entry in ledger["rounds"][:-1] if entry["candidate_instruction_digest"])
        duplicate = instruction_digest in existing
    item.update({
        "proposal_status": status,
        "proposal_wall_seconds": wall_seconds,
        "proposal_input_digest": input_digest,
        "proposal_output_digest": output_digest,
        "failure_hypothesis": failure_hypothesis,
        "expected_improvement": expected_improvement,
        "candidate_instruction": instruction,
        "candidate_instruction_digest": instruction_digest,
        "duplicate": duplicate,
    })
    if status != "valid" or duplicate:
        item["gpu_status"] = "skipped"
        item["next_action"] = "continue-gepa"
        ledger["next_action"] = "continue-gepa"
    else:
        item["next_action"] = f"stage-round-{item['round']:02d}"
        ledger["next_action"] = item["next_action"]
    save_ledger(path, ledger)
    return item


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_codex_proposal_request(
    candidate: Mapping[str, str],
    reflective_dataset: Mapping[str, Sequence[Mapping[str, Any]]],
    components_to_update: Sequence[str],
) -> tuple[str, dict[str, Any]]:
    if len(components_to_update) != 1:
        raise ValidationError("prompt-pilot GEPA bridge must update exactly one component")
    component = components_to_update[0]
    if component not in candidate or component not in reflective_dataset:
        raise ValidationError("prompt-pilot GEPA reflective component is missing")
    current = candidate[component]
    if not isinstance(current, str) or not current.strip():
        raise ValidationError("prompt-pilot GEPA parent instruction is invalid")

    examples = [dict(item) for item in reflective_dataset[component]]
    examples.sort(key=lambda item: (len(_json_bytes(item)), digest_value(item)))
    selected: list[dict[str, Any]] = []
    base = {
        "task": "Improve one ARC solver instruction using only the supplied optimization-train traces.",
        "current_instruction": current,
        "constraints": [
            "Return one instruction only through the required JSON field.",
            "Do not change the model, demonstrations, parser, output format, decoding, token limit, or retry policy.",
            "The solver must still return only the output grid as digit rows with no explanation.",
            "Generalize from the examples; do not mention task IDs, expected answers, scores, dev, or holdout.",
        ],
        "reflective_examples": selected,
    }
    for example in examples[:MAX_REFLECTIVE_EXAMPLES]:
        trial = {**base, "reflective_examples": [*selected, example]}
        if len(_json_bytes(trial)) <= MAX_PROPOSER_INPUT_BYTES:
            selected.append(example)
    payload = {**base, "reflective_examples": selected}
    prompt = (
        "Act as GEPA's instruction proposer. First reason privately with a concise plan, then return JSON matching the schema. "
        "Use only this payload; it contains optimization-train feedback and no dev or holdout data.\n"
        + _json_bytes(payload).decode("utf-8")
    )
    if len(prompt.encode("utf-8")) > MAX_PROPOSER_INPUT_BYTES:
        raise ValidationError("prompt-pilot Codex proposer input exceeds 32 KiB")
    evidence = {
        "component": component,
        "parent_instruction_digest": digest_value(current),
        "reflective_example_count": len(selected),
        "input_bytes": len(prompt.encode("utf-8")),
        "input_digest": digest_value(prompt),
    }
    return prompt, evidence


def invoke_codex_cli(prompt: str, workspace: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    codex = shutil.which("codex")
    if codex is None:
        raise ValidationError("Codex CLI is unavailable")
    workspace.mkdir(parents=True, exist_ok=True)
    schema_path = workspace / "proposal-schema.json"
    output_path = workspace / "proposal.json"
    events_path = workspace / "events.jsonl"
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["instruction", "failure_hypothesis", "expected_improvement"],
        "properties": {
            "instruction": {"type": "string", "minLength": 1, "maxLength": MAX_INSTRUCTION_BYTES},
            "failure_hypothesis": {"type": "string", "minLength": 1, "maxLength": 4096},
            "expected_improvement": {"type": "string", "minLength": 1, "maxLength": 4096},
        },
    }
    schema_path.write_bytes(canonical_bytes(schema, newline=True))
    started = time.monotonic()
    completed = subprocess.run(
        [
            codex,
            "exec",
            "-",
            "--model",
            CODEX_MODEL,
            "-c",
            f'model_reasoning_effort="{CODEX_REASONING_EFFORT}"',
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--cd",
            str(workspace),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--json",
        ],
        input=prompt,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    wall = time.monotonic() - started
    events_path.write_text(completed.stdout, encoding="utf-8")
    evidence = {
        "model": CODEX_MODEL,
        "reasoning_effort": CODEX_REASONING_EFFORT,
        "codex_path": codex,
        "exit_code": completed.returncode,
        "wall_seconds": wall,
        "events_digest": digest_path(events_path),
        "stderr": completed.stderr[-4096:],
    }
    if completed.returncode != 0 or not output_path.is_file():
        raise RuntimeError(f"Codex proposer failed with exit code {completed.returncode}: {completed.stderr[-1000:]}")
    try:
        proposal = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError("Codex proposer output is not JSON") from exc
    if set(proposal) != {"instruction", "failure_hypothesis", "expected_improvement"} or any(not isinstance(value, str) or not value.strip() for value in proposal.values()):
        raise ValidationError("Codex proposer output does not match the required fields")
    evidence["output_digest"] = digest_path(output_path)
    return proposal, evidence


def _candidate_label(ledger: Mapping[str, Any], instruction: str) -> str:
    digest = digest_value(instruction)
    if digest == ledger["baseline"]["instruction_digest"]:
        return "B1"
    for item in ledger["rounds"]:
        if item.get("candidate_instruction_digest") == digest:
            return item["candidate"]
    raise ValidationError("GEPA selected a parent that is absent from the durable ledger")


class LedgerCodexInstructionProposer:
    """GEPA ProposalFn implementation backed by one isolated Codex CLI call."""

    def __init__(self, ledger_path: Path, workspace_root: Path):
        self.ledger_path = ledger_path
        self.workspace_root = workspace_root

    def __call__(
        self,
        candidate: dict[str, str],
        reflective_dataset: Mapping[str, Sequence[Mapping[str, Any]]],
        components_to_update: list[str],
    ) -> dict[str, str]:
        if len(components_to_update) != 1:
            raise ValidationError("prompt-pilot proposer received multiple components")
        component = components_to_update[0]
        current = candidate[component]
        ledger = load_ledger(self.ledger_path)
        if ledger["rounds"] and ledger["rounds"][-1]["proposal_status"] == "running":
            finish_proposal_attempt(
                self.ledger_path,
                instruction=None,
                status="failed",
                wall_seconds=0.0,
                input_digest=digest_value("interrupted-before-terminal-proposal-evidence"),
                output_digest=None,
                failure_hypothesis="The prior controller stopped before retaining terminal proposer output.",
                expected_improvement=None,
            )
            ledger = load_ledger(self.ledger_path)
        if ledger["budget"]["proposal_attempts_used"] >= MAX_PROPOSAL_ATTEMPTS:
            return {component: current}

        parent = _candidate_label(ledger, current)
        item = begin_proposal_attempt(self.ledger_path, parent_candidate=parent, parent_instruction=current)
        started = time.monotonic()
        input_digest = digest_value({"candidate": candidate, "components": components_to_update})
        try:
            prompt, request_evidence = build_codex_proposal_request(candidate, reflective_dataset, components_to_update)
            input_digest = request_evidence["input_digest"]
            round_workspace = self.workspace_root / f"round-{item['round']:02d}"
            proposal, invocation = invoke_codex_cli(prompt, round_workspace)
            instruction = proposal["instruction"].strip()
            finished = finish_proposal_attempt(
                self.ledger_path,
                instruction=instruction,
                status="valid",
                wall_seconds=invocation["wall_seconds"],
                input_digest=input_digest,
                output_digest=invocation["output_digest"],
                failure_hypothesis=proposal["failure_hypothesis"].strip(),
                expected_improvement=proposal["expected_improvement"].strip(),
            )
            if finished["duplicate"]:
                return {component: current}
            return {component: instruction}
        except Exception as exc:
            finish_proposal_attempt(
                self.ledger_path,
                instruction=None,
                status="failed",
                wall_seconds=time.monotonic() - started,
                input_digest=input_digest,
                output_digest=None,
                failure_hypothesis=f"{type(exc).__name__}: {exc}",
                expected_improvement=None,
            )
            return {component: current}


class ReplayThenLedgerProposer:
    """Replay one retained instruction, then delegate new attempts to Codex."""

    def __init__(self, delegate: LedgerCodexInstructionProposer, replay_instruction: str):
        self.delegate = delegate
        self.replay_instruction = replay_instruction
        self.replayed = False

    def __call__(
        self,
        candidate: dict[str, str],
        reflective_dataset: Mapping[str, Sequence[Mapping[str, Any]]],
        components_to_update: list[str],
    ) -> dict[str, str]:
        if not self.replayed:
            if len(components_to_update) != 1:
                raise ValidationError("prompt-pilot replay received multiple components")
            self.replayed = True
            return {components_to_update[0]: self.replay_instruction}
        return self.delegate(candidate, reflective_dataset, components_to_update)

def _load_score_for_instruction(ledger: Mapping[str, Any], instruction_digest: str) -> Path | None:
    if instruction_digest == ledger["baseline"]["instruction_digest"]:
        return Path(ledger["baseline"]["score_path"])
    for item in ledger["rounds"]:
        if item.get("candidate_instruction_digest") == instruction_digest and item.get("score_path"):
            return Path(item["score_path"])
    return None


def deterministic_train_feedback(example: Any, prediction: Any, score_record: Mapping[str, Any]) -> str:
    if example.group != "optimization-train":
        return "Selection-dev contributes only an aggregate exact-match score; case-level answer feedback is withheld."
    if score_record["correct"]:
        return "Exact match. Preserve the general strategy while keeping output to digit rows only."
    if score_record["status"] != "valid":
        return "The completion was not a parseable valid ARC grid. Return exactly one rectangular digit grid with no prose."
    predicted = score_record["predicted_output"]
    expected = score_record["expected_output"]
    predicted_shape = [len(predicted), len(predicted[0])] if predicted else None
    expected_shape = [len(expected), len(expected[0])]
    if predicted_shape != expected_shape:
        reason = f"Wrong output shape: predicted {predicted_shape}, expected {expected_shape}."
    else:
        mismatches = sum(a != b for prow, erow in zip(predicted, expected) for a, b in zip(prow, erow))
        reason = f"Shape matched but {mismatches} cells differed."
    return reason + " Expected grid: " + json.dumps(expected, separators=(",", ":"))


def run_dspy_gepa_search(
    *,
    ledger_path: Path,
    baseline_trial_root: Path,
    proposer_workspace: Path,
    gepa_run_dir: Path,
    evaluate_candidate: Callable[[int, str], Path],
    replay_instruction: str | None = None,
) -> dict[str, Any]:
    """Run real dspy.GEPA while delegating each new candidate to private Kaggle.

    The task LM is a replay adapter over verified result packages.  On the
    first call for a new instruction it invokes ``evaluate_candidate`` once;
    all subsequent GEPA metric calls are served from the retained score report.
    """

    try:
        import importlib.metadata
        import dspy
        from gepa.utils import MaxCandidateProposalsStopper
    except ImportError as exc:
        raise ValidationError("DSPy/GEPA optimizer dependencies are unavailable") from exc
    if importlib.metadata.version("dspy") != DSPY_VERSION or importlib.metadata.version("gepa") != GEPA_VERSION:
        raise ValidationError("DSPy/GEPA versions differ from the Decision 0019 binding")

    solver = read_json(baseline_trial_root / "solver-cases.json")
    truth = read_json(baseline_trial_root / "evaluator-truth.json")
    cases = {item["task_id"]: item for item in solver["cases"]}
    truth_by_id = {item["task_id"]: item for item in truth["cases"] if item["group"] != "locked-holdout"}
    if set(cases) != set(truth_by_id):
        raise ValidationError("DSPy/GEPA train-dev workload differs from the frozen evaluator truth")

    score_cache: dict[str, dict[str, Mapping[str, Any]]] = {}
    candidate_evaluation_lock = threading.Lock()

    def ensure_score(instruction: str) -> tuple[str, dict[str, Mapping[str, Any]]]:
        instruction_digest = digest_value(instruction)
        if instruction_digest in score_cache:
            return instruction_digest, score_cache[instruction_digest]
        with candidate_evaluation_lock:
            if instruction_digest in score_cache:
                return instruction_digest, score_cache[instruction_digest]
            ledger = load_ledger(ledger_path)
            score_path = _load_score_for_instruction(ledger, instruction_digest)
            if score_path is None:
                matching = [item for item in ledger["rounds"] if item.get("candidate_instruction_digest") == instruction_digest]
                if len(matching) != 1 or matching[0].get("duplicate") is not False or matching[0].get("proposal_status") != "valid":
                    raise ValidationError("GEPA requested an unledgered or invalid instruction")
                score_path = evaluate_candidate(matching[0]["round"], instruction)
            score = read_json(score_path)
            if score.get("bindings", {}).get("instruction_digest", instruction_digest) != instruction_digest:
                raise ValidationError("candidate score instruction binding differs")
            records = score.get("records")
            if not isinstance(records, list) or len(records) != BASELINE_JOB_COUNT:
                raise ValidationError("candidate score does not preserve the 384-case denominator")
            by_id = {item["task_id"]: item for item in records}
            if set(by_id) != set(cases):
                raise ValidationError("candidate score task identities differ")
            score_cache[instruction_digest] = by_id
            return instruction_digest, by_id

    instruction_marker = "In adhering to this structure, your objective is: \n        "

    class VerifiedReplayLM(dspy.BaseLM):
        forward_contract = "typed_lm"

        def __init__(self):
            super().__init__("irisx/verified-qwen-result-replay", cache=False, num_retries=0)

        def forward(self, request):
            system = request.messages[0].parts[0].text
            if instruction_marker not in system:
                raise ValidationError("DSPy replay request lacks an instruction marker")
            instruction = system.split(instruction_marker, 1)[1]
            user = request.messages[-1].parts[0].text
            match = re.search(r"\[\[ ## task_id ## \]\]\n([^\n]+)", user)
            if match is None:
                raise ValidationError("DSPy replay request lacks a task ID")
            task_id = match.group(1).strip()
            instruction_digest, scored = ensure_score(instruction)
            record = scored[task_id]
            predicted = record["predicted_output"]
            text = json.dumps(predicted, separators=(",", ":")) if predicted is not None else "<invalid-grid>"
            response = {
                "predicted_grid": text,
                "instruction_digest": instruction_digest,
                "terminal_status": record["status"],
            }
            return dspy.LMResponse.from_text(json.dumps(response, separators=(",", ":")), model=request.model)

    signature = dspy.make_signature(
        "task_id, visible_case, group -> predicted_grid, instruction_digest, terminal_status",
        instructions=BASE_INSTRUCTION,
    )

    class ReplayProgram(dspy.Module):
        def __init__(self):
            super().__init__()
            self.solve = dspy.Predict(signature)

        def forward(self, task_id: str, visible_case: str, group: str):
            return self.solve(task_id=task_id, visible_case=visible_case, group=group)

    def metric(example, prediction, trace=None, pred_name=None, trace_for_pred=None):
        current_ledger = load_ledger(ledger_path)
        if _load_score_for_instruction(current_ledger, prediction.instruction_digest) is None:
            raise ValidationError("DSPy metric cannot locate the candidate score")
        _, records = ensure_score(
            next(
                item.get("instruction", item.get("candidate_instruction"))
                for item in ([current_ledger["baseline"]] + current_ledger["rounds"])
                if item.get("instruction_digest", item.get("candidate_instruction_digest")) == prediction.instruction_digest
            )
        )
        record = records[example.task_id]
        return dspy.Prediction(
            score=1.0 if record["correct"] else 0.0,
            feedback=deterministic_train_feedback(example, prediction, record),
        )

    def to_example(task_id: str):
        case = cases[task_id]
        expected = truth_by_id[task_id]["output"]
        visible = json.dumps({"train": case["train"], "test_input": case["test"][0]["input"]}, separators=(",", ":"))
        return dspy.Example(task_id=task_id, visible_case=visible, group=case["group"], expected_output=expected).with_inputs("task_id", "visible_case", "group")

    trainset = [to_example(item["task_id"]) for item in solver["cases"] if item["group"] == "optimization-train"]
    valset = [to_example(item["task_id"]) for item in solver["cases"] if item["group"] == "selection-dev"]
    ledger_before_run = load_ledger(ledger_path)
    remaining_attempts = MAX_PROPOSAL_ATTEMPTS - ledger_before_run["budget"]["proposal_attempts_used"]
    proposal_iterations = remaining_attempts
    proposer: Any = LedgerCodexInstructionProposer(ledger_path, proposer_workspace)
    if replay_instruction is not None:
        replay_digest = digest_value(replay_instruction)
        replay_score = _load_score_for_instruction(ledger_before_run, replay_digest)
        if replay_score is None:
            raise ValidationError("GEPA recovery replay must already have a verified score")
        proposer = ReplayThenLedgerProposer(proposer, replay_instruction)
        proposal_iterations += 1
    if proposal_iterations < 1:
        raise ValidationError("prompt-pilot proposal budget is exhausted")
    dspy.configure(lm=VerifiedReplayLM(), adapter=dspy.JSONAdapter())
    optimizer = dspy.GEPA(
        metric,
        max_metric_calls=100_000,
        reflection_minibatch_size=MAX_REFLECTIVE_EXAMPLES,
        candidate_selection_strategy="pareto",
        instruction_proposer=proposer,
        skip_perfect_score=False,
        use_merge=False,
        num_threads=1,
        track_stats=True,
        log_dir=str(gepa_run_dir),
        seed=20260922,
        gepa_kwargs={"stop_callbacks": MaxCandidateProposalsStopper(proposal_iterations)},
    )
    optimized = optimizer.compile(ReplayProgram(), trainset=trainset, valset=valset)
    best_instruction = optimized.solve.signature.instructions
    ledger = load_ledger(ledger_path)
    best_label = _candidate_label(ledger, best_instruction)
    return {
        "best_candidate": best_label,
        "best_instruction": best_instruction,
        "best_instruction_digest": digest_value(best_instruction),
        "proposal_attempts_used": ledger["budget"]["proposal_attempts_used"],
        "dspy_version": DSPY_VERSION,
        "gepa_version": GEPA_VERSION,
    }
