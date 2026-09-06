#!/usr/bin/env python3
"""One provider-specific Codex adapter shared by the three frozen Batch 6 tasks."""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping

import check_admission as admission_checker
import run_qualification as qualified
from task_family import FrozenTaskDefinition, PROFILE_ID, PROFILE_SHA256, sha256_bytes

from irisx.core.execution import ExecutorAdapterError
from irisx.core.records import (
    UNKNOWN,
    AdapterResourceReport,
    EvidenceRef,
    ExecutionContext,
    ExecutionRequest,
    RawResult,
)


Runner = Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extended_event_audit(events: list[Mapping[str, Any]]) -> dict[str, Any]:
    audit = qualified.audit_provider_events(events)
    escalation_hashes: list[str] = []
    recovery_hashes: list[str] = []
    for event in events:
        event_type = str(event.get("type", "")).lower()
        encoded = json.dumps(event, ensure_ascii=False, sort_keys=True).lower()
        event_hash = sha256_bytes(qualified.canonical_json_bytes(event))
        if "escalat" in event_type or '"escalation"' in encoded:
            escalation_hashes.append(event_hash)
        if "recovery" in event_type or '"recovery_action"' in encoded:
            recovery_hashes.append(event_hash)
    return {
        **audit,
        "escalation_event_count": len(escalation_hashes),
        "escalation_event_hashes": escalation_hashes,
        "recovery_event_count": len(recovery_hashes),
        "recovery_event_hashes": recovery_hashes,
    }


class TaskFamilyModelAdapter:
    """Exactly one tool-free invocation for one already-bound frozen task."""

    def __init__(
        self,
        *,
        definition: FrozenTaskDefinition,
        admission_record: Mapping[str, Any],
        admission_record_path: Path,
        admission_record_sha256: str,
        definition_code_freeze_sha: str,
        launch_head: str,
        runner: Runner = subprocess.run,
    ) -> None:
        self.definition = definition
        self.admission_record = dict(admission_record)
        self.admission_record_path = Path(admission_record_path)
        self.admission_record_sha256 = admission_record_sha256
        self.definition_code_freeze_sha = definition_code_freeze_sha
        self.launch_head = launch_head
        self.runner = runner
        self.invocation_attempts = 0
        self.capture: dict[str, Any] | None = None

    def execute(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        state: MutableMapping[str, Any],
    ) -> RawResult:
        del state
        expected_identity = self.definition.execution_identity()
        if context.identity != expected_identity:
            raise ValueError("shared adapter received crossed task identity")
        if context.contract.content_sha256 != self.definition.contract_sha256:
            raise ValueError("shared adapter received crossed task contract")
        if context.program.content_sha256 != self.definition.program_sha256:
            raise ValueError("shared adapter received crossed task program")
        if request != self.definition.execution_request() or request.requires_mutation_prevention:
            raise ValueError("shared adapter received a non-frozen or mutating request")
        if self.admission_record.get("status") != "admitted":
            raise ValueError("live invocation requires admitted current environment")
        if self.admission_record.get("compatibility_profile_id") != PROFILE_ID:
            raise ValueError("admission profile identity mismatch")
        if self.admission_record.get("compatibility_profile_sha256") != PROFILE_SHA256:
            raise ValueError("admission profile hash mismatch")
        if self.invocation_attempts != 0:
            raise ValueError("the task-local one-call ceiling has already been consumed")
        if self.definition.run_dir.exists():
            raise FileExistsError(f"immutable run directory already exists: {self.definition.run_dir}")
        self.definition.run_dir.mkdir(parents=True)

        prompt = self.definition.prompt
        prompt_bytes = prompt.encode("utf-8")
        started_at = utc_now()
        start_ns = time.perf_counter_ns()
        self.invocation_attempts = 1
        return_code: int | str = "not_started"
        timed_out = False
        stdout_text = ""
        stderr_text = ""
        output_bytes: bytes | None = None

        with tempfile.TemporaryDirectory(prefix=f"irisx-task-family-{self.definition.task_key.lower()}-") as temporary:
            workspace = Path(temporary)
            schema_copy = workspace / "output-schema.json"
            schema_copy.write_bytes(self.definition.schema_path.read_bytes())
            model_catalog_copy = workspace / "model-catalog.json"
            model_catalog_copy.write_bytes(qualified.MODEL_CATALOG_PATH.read_bytes())
            raw_output_temp = workspace / "raw-output.txt"
            command = qualified.build_provider_command(
                str(self.admission_record["observed_cli_path"]),
                workspace,
                schema_copy,
                model_catalog_copy,
                raw_output_temp,
            )
            normalized = admission_checker.normalize_command(command)
            profile = admission_checker.load_object(admission_checker.PROFILE_PATH)
            if normalized != profile["canonical_argv"]:
                raise ValueError("provider command differs from admitted Run 03 profile")
            attempt_start = {
                "schema_version": 1,
                "run_id": self.definition.run_id,
                "task_key": self.definition.task_key,
                "task_id": self.definition.spec["task_id"],
                "contract_id": self.definition.spec["contract_id"],
                "contract_sha256": self.definition.contract_sha256,
                "program_id": self.definition.spec["program_id"],
                "program_sha256": self.definition.program_sha256,
                "prompt_sha256": self.definition.prompt_sha256,
                "definition_code_freeze_sha": self.definition_code_freeze_sha,
                "launch_head": self.launch_head,
                "admission_profile_id": PROFILE_ID,
                "admission_profile_sha256": PROFILE_SHA256,
                "admission_record_path": self.admission_record_path.as_posix(),
                "admission_record_sha256": self.admission_record_sha256,
                "admission_status": "admitted",
                "started_at": started_at,
                "provider_attempt": 1,
                "model_calls_committed_ceiling": 1,
                "batch_6_total_call_ceiling": 3,
                "retry_count": 0,
                "route_count": 0,
                "fallback_count": 0,
                "escalation_count": 0,
                "recovery_count": 0,
                "tool_call_count": 0,
                "codex_model_provider_config_id": qualified.CODEX_PROVIDER_CONFIG_ID,
                "command": command,
                "api_key_environment_removed_from_child": True,
            }
            qualified.write_new(
                self.definition.run_dir / "attempt-start.json",
                qualified.pretty_json_bytes(attempt_start),
            )
            try:
                completed = self.runner(
                    command,
                    input=prompt,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=qualified.REPOSITORY_ROOT,
                    env=qualified.codex_environment(),
                    timeout=600,
                    check=False,
                )
                return_code = completed.returncode
                stdout_text = completed.stdout or ""
                stderr_text = completed.stderr or ""
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                return_code = "timeout"
                stdout_text = (
                    exc.stdout
                    if isinstance(exc.stdout, str)
                    else (exc.stdout or b"").decode("utf-8", errors="replace")
                )
                stderr_text = (
                    exc.stderr
                    if isinstance(exc.stderr, str)
                    else (exc.stderr or b"").decode("utf-8", errors="replace")
                )
            except Exception as exc:
                return_code = "process_start_failure"
                stderr_text = f"{type(exc).__name__}: {exc}\n"
            if raw_output_temp.exists():
                output_bytes = raw_output_temp.read_bytes()

        stdout_bytes = stdout_text.encode("utf-8")
        stderr_bytes = stderr_text.encode("utf-8")
        qualified.write_new(self.definition.run_dir / "provider-events.jsonl", stdout_bytes)
        qualified.write_new(self.definition.run_dir / "provider-stderr.txt", stderr_bytes)
        qualified.write_new(self.definition.run_dir / "raw-output.txt", output_bytes or b"")

        wall_time_ns = time.perf_counter_ns() - start_ns
        events, parse_errors = qualified.parse_provider_events(stdout_bytes)
        event_audit = _extended_event_audit(events)
        usage = qualified.extract_usage(events)
        event_message = qualified.final_agent_message(events)
        file_message = (
            output_bytes.decode("utf-8", errors="replace") if output_bytes is not None else None
        )
        resource_report = AdapterResourceReport(
            model_calls=1,
            network_calls=UNKNOWN,
            paid_api_calls=0,
            tool_calls=event_audit["tool_attempt_count"],
            retry_count=event_audit["retry_event_count"],
            route_count=event_audit["route_event_count"],
            escalation_count=event_audit["escalation_event_count"],
            recovery_count=event_audit["recovery_event_count"],
            wall_time_ns=wall_time_ns,
            provider_cost_usd=UNKNOWN,
        )
        self.capture = {
            "started_at": started_at,
            "ended_at": utc_now(),
            "wall_time_ns": wall_time_ns,
            "command": command,
            "normalized_command_sha256": sha256_bytes(
                admission_checker.canonical_json_bytes(normalized)
            ),
            "process_return_code": return_code,
            "timed_out": timed_out,
            "provider_event_parse_errors": parse_errors,
            "provider_event_count": len(events),
            "event_audit": event_audit,
            "event_final_message": event_message,
            "raw_output_present": output_bytes is not None,
            "raw_output_matches_event_message": (
                file_message.strip() == event_message.strip()
                if file_message is not None and event_message is not None
                else False
            ),
            "usage": usage,
            "prompt_sha256": self.definition.prompt_sha256,
            "prompt_bytes": len(prompt_bytes),
            "resource_report": resource_report,
        }

        failure_reasons: list[str] = []
        if return_code != 0:
            failure_reasons.append("provider_process_failed")
        if timed_out:
            failure_reasons.append("provider_process_timed_out")
        if output_bytes is None:
            failure_reasons.append("provider_output_missing")
        if parse_errors:
            failure_reasons.append("provider_event_stream_malformed")
        if event_message is None:
            failure_reasons.append("provider_final_message_missing")
        forbidden_counts = {
            "prohibited_tool_attempt": event_audit["tool_attempt_count"],
            "prohibited_retry_observed": event_audit["retry_event_count"],
            "prohibited_route_observed": event_audit["route_event_count"],
            "prohibited_fallback_observed": event_audit["fallback_event_count"],
            "prohibited_escalation_observed": event_audit["escalation_event_count"],
            "prohibited_recovery_observed": event_audit["recovery_event_count"],
        }
        failure_reasons.extend(reason for reason, count in forbidden_counts.items() if count)
        if event_message is not None and file_message is not None and not self.capture[
            "raw_output_matches_event_message"
        ]:
            failure_reasons.append("raw_output_event_mismatch")
        self.capture["systemic_failure_reasons"] = failure_reasons
        if failure_reasons:
            raise ExecutorAdapterError(
                ";".join(failure_reasons),
                resource_report=resource_report,
            )

        evidence = tuple(
            EvidenceRef(item.role, item.artifact_id, item.path, item.sha256)
            for item in context.evidence_requirements
        )
        return RawResult(
            producer_claim="success",
            reported_value=file_message,
            evidence=evidence,
            executor_calls=1,
            mutation_primitive_calls=0,
            resource_report=resource_report,
        )
