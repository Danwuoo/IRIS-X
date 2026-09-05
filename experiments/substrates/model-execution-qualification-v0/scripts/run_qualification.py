#!/usr/bin/env python3
"""Preflight, run once, or validate the frozen Batch 4 repair qualification."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping, Sequence


SUBSTRATE = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from irisx.core.execution import (  # noqa: E402
    ExecutorAdapterError,
    evidence_binding,
    execute,
    state_sha256,
    terminal_record_to_dict,
)
from irisx.core.records import (  # noqa: E402
    UNKNOWN,
    AdapterResourceReport,
    EvidenceRef,
    EvidenceRequirement,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRequest,
    ProgramArtifact,
    RawResult,
    TaskContract,
    VerificationResult,
)


CONTRACT_PATH = SUBSTRATE / "definition" / "qualification-repair-contract.json"
IDENTITY_PATH = SUBSTRATE / "definition" / "repair-execution-identity.json"
OUTPUT_SCHEMA_PATH = SUBSTRATE / "definition" / "output-schema.json"
PREFLIGHT_OBSERVATION_PATH = SUBSTRATE / "definition" / "repair-preflight-observation.json"
MODEL_CATALOG_PATH = SUBSTRATE / "definition" / "tool-free-luna-model-catalog.json"
BASELINE_PATH = REPOSITORY_ROOT / "experiments" / "configurations" / "provider-model-baseline-v0.json"
ORIGINAL_RUN_ID = "qualification-20260905-01"
RUN_ID = "qualification-20260905-02"
RUN_DIR = SUBSTRATE / "runs" / RUN_ID
CODEX_PROVIDER_CONFIG_ID = "irisx_openai_no_retry"
CODEX_PROVIDER_NAME = "OpenAI"
API_ENVIRONMENT_NAMES = (
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "CODEX_API_KEY",
    "OPENAI_KEY",
    "OPENAI_ORGANIZATION",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT",
    "OPENAI_PROJECT_ID",
    "OPENAI_BASE_URL",
    "AZURE_OPENAI_ENDPOINT",
)
FULL_SHA = re.compile(r"[0-9a-f]{40}")
Runner = Callable[..., subprocess.CompletedProcess[str]]


class QualificationError(RuntimeError):
    """Frozen definition, preflight, or artifact validation failed closed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise QualificationError(f"JSON top level must be an object: {path}")
    return value


def write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)


def git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=check,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip() or completed.stderr.strip()


def require_clean_frozen_head(definition_commit: str, code_commit: str) -> str:
    for label, value in (
        ("definition_commit", definition_commit),
        ("code_commit", code_commit),
    ):
        if FULL_SHA.fullmatch(value) is None:
            raise QualificationError(f"{label} must be a full lowercase Git SHA")
        git("cat-file", "-e", f"{value}^{{commit}}")
    head = git("rev-parse", "HEAD")
    if definition_commit != head or code_commit != head:
        raise QualificationError("definition and code commits must both equal the clean invocation HEAD")
    if git("status", "--porcelain"):
        raise QualificationError("provider invocation requires a clean working tree")
    return head


def codex_environment() -> dict[str, str]:
    child = dict(os.environ)
    for name in API_ENVIRONMENT_NAMES:
        child.pop(name, None)
    return child


def codex_config_arguments(model_catalog_path: Path) -> list[str]:
    return [
        "--config",
        f"model_catalog_json={json.dumps(str(model_catalog_path))}",
        "--config",
        f'model_provider="{CODEX_PROVIDER_CONFIG_ID}"',
        "--config",
        f'model_providers.{CODEX_PROVIDER_CONFIG_ID}.name="{CODEX_PROVIDER_NAME}"',
        "--config",
        f"model_providers.{CODEX_PROVIDER_CONFIG_ID}.requires_openai_auth=true",
        "--config",
        f'model_providers.{CODEX_PROVIDER_CONFIG_ID}.wire_api="responses"',
        "--config",
        f"model_providers.{CODEX_PROVIDER_CONFIG_ID}.request_max_retries=0",
        "--config",
        f"model_providers.{CODEX_PROVIDER_CONFIG_ID}.stream_max_retries=0",
        "--config",
        f"model_providers.{CODEX_PROVIDER_CONFIG_ID}.supports_websockets=false",
        "--config",
        f"model_providers.{CODEX_PROVIDER_CONFIG_ID}.supports_standalone_web_search=false",
        "--config",
        'model_reasoning_effort="medium"',
        "--config",
        'approval_policy="never"',
        "--config",
        'web_search="disabled"',
        "--config",
        "tools.web_search=false",
        "--config",
        "tools.view_image=false",
        "--config",
        "apps._default.enabled=false",
        "--config",
        "agents.enabled=false",
        "--disable",
        "shell_tool",
        "--disable",
        "apply_patch_freeform",
        "--disable",
        "js_repl",
        "--disable",
        "multi_agent",
        "--disable",
        "multi_agent_v2",
        "--disable",
        "apps",
        "--disable",
        "plugins",
        "--disable",
        "plugin_hooks",
        "--disable",
        "tool_search",
        "--disable",
        "browser_use",
        "--disable",
        "in_app_browser",
        "--disable",
        "computer_use",
        "--disable",
        "image_generation",
        "--disable",
        "skill_search",
        "--disable",
        "goals",
        "--disable",
        "responses_websockets",
        "--disable",
        "responses_websockets_v2",
        "--disable",
        "remote_compaction_v2",
    ]


def resolve_codex_command() -> str:
    command_name = "codex.cmd" if os.name == "nt" else "codex"
    resolved = shutil.which(command_name)
    if resolved is None:
        raise QualificationError(f"cannot resolve {command_name} on PATH")
    return str(Path(resolved).resolve())


def run_checked(command: Sequence[str], *, env: Mapping[str, str] | None = None) -> str:
    completed = subprocess.run(
        list(command),
        cwd=REPOSITORY_ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(env) if env is not None else None,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise QualificationError(f"zero-call command failed ({completed.returncode}): {detail}")
    return completed.stdout.strip() or completed.stderr.strip()


def validate_frozen_definition() -> tuple[dict[str, Any], dict[str, Any]]:
    identity = load_json(IDENTITY_PATH)
    contract = load_json(CONTRACT_PATH)
    expected_files = (
        (CONTRACT_PATH, identity["contract_sha256"]),
        (SUBSTRATE / identity["program_path"], identity["program_sha256"]),
        (SUBSTRATE / identity["task_input_path"], identity["task_input_sha256"]),
        (SUBSTRATE / identity["output_schema_path"], identity["output_schema_sha256"]),
        (
            SUBSTRATE / identity["preflight_observation_path"],
            identity["preflight_observation_sha256"],
        ),
        (SUBSTRATE / identity["model_catalog_path"], identity["model_catalog_sha256"]),
        (BASELINE_PATH, identity["provider_baseline_sha256"]),
    )
    for path, expected in expected_files:
        actual = sha256_bytes(path.read_bytes())
        if actual != expected:
            raise QualificationError(f"frozen SHA mismatch: {path} expected {expected} observed {actual}")
    if contract["program"]["sha256"] != identity["program_sha256"]:
        raise QualificationError("contract and execution identity cross different programs")
    provider = contract["provider_configuration"]
    expected_provider = (
        "openai",
        "codex-cli",
        "cheaper",
        "gpt-5.6-luna",
        "medium",
    )
    observed_provider = (
        provider["provider_id"],
        provider["execution_surface"],
        provider["model_role"],
        provider["model_id"],
        provider["reasoning_effort"],
    )
    if observed_provider != expected_provider:
        raise QualificationError("provider/model configuration differs from the accepted cheaper role")
    if (
        provider["codex_model_provider_config_id"] != CODEX_PROVIDER_CONFIG_ID
        or provider["codex_model_provider_name"] != CODEX_PROVIDER_NAME
        or identity["codex_model_provider_config_id"] != CODEX_PROVIDER_CONFIG_ID
        or identity["codex_model_provider_name"] != CODEX_PROVIDER_NAME
        or identity["codex_model_provider_base_url"] is not None
    ):
        raise QualificationError("repair provider configuration differs from the frozen custom slot")
    if identity["retry_configuration"] != {
        "http_request_retries": 0,
        "stream_reconnect_retries": 0,
        "websocket_transport": False,
        "transport_fallback": False,
    }:
        raise QualificationError("repair retry/transport configuration drifted")
    catalog = load_json(SUBSTRATE / identity["model_catalog_path"])
    if len(catalog.get("models", [])) != 1:
        raise QualificationError("repair catalog must contain exactly one model")
    catalog_model = catalog["models"][0]
    if (
        catalog_model.get("slug") != identity["model_id"]
        or catalog_model.get("shell_type") != "disabled"
        or catalog_model.get("apply_patch_tool_type") is not None
        or catalog_model.get("supports_search_tool") is not False
        or catalog_model.get("experimental_supported_tools") != []
    ):
        raise QualificationError("repair model catalog does not enforce the zero-tool envelope")
    if identity["codex_cli_source_observation"] != {
        "repository": "openai/codex",
        "tag": "rust-v0.147.0",
        "commit": "be6e8eac029b183056b7e4402879f15d2c85f61b",
        "chatgpt_codex_base_url": "https://chatgpt.com/backend-api/codex",
        "request_retry_zero_semantics": "one-initial-request-attempt-no-retry",
        "stream_retry_zero_semantics": "no-stream-reconnect",
        "websocket_fallback_control": "provider-websocket-support-false",
    }:
        raise QualificationError("Codex CLI source observation drifted")
    if identity["official_codex_config_reference"] != (
        "https://learn.chatgpt.com/docs/config-file/config-reference"
    ):
        raise QualificationError("official Codex config reference drifted")
    ceiling = contract["call_ceiling"]
    if ceiling != {
        "provider_invocations": 1,
        "http_request_retries": 0,
        "stream_reconnect_retries": 0,
        "manual_retries": 0,
        "routes": 0,
        "escalations": 0,
        "recovery_actions": 0,
    }:
        raise QualificationError("call ceiling is not the frozen one-call/zero-retry boundary")
    return identity, contract


def preflight() -> dict[str, Any]:
    identity, _ = validate_frozen_definition()
    codex_path = resolve_codex_command()
    child_env = codex_environment()
    version = run_checked([codex_path, "--version"], env=child_env)
    auth_status = run_checked([codex_path, "login", "status"], env=child_env)
    if auth_status != "Logged in using ChatGPT":
        raise QualificationError(f"provider execution unavailable: auth status is {auth_status!r}")

    debug_command = [
        codex_path,
        "debug",
        *codex_config_arguments(MODEL_CATALOG_PATH),
        "models",
        "--bundled",
    ]
    catalog = json.loads(run_checked(debug_command, env=child_env))
    records = {
        row.get("slug"): row
        for row in catalog.get("models", [])
        if isinstance(row, dict)
    }
    model = records.get(identity["model_id"])
    if model is None:
        raise QualificationError("accepted cheaper model is absent from the bundled local catalog")
    efforts = {
        row.get("effort")
        for row in model.get("supported_reasoning_levels", [])
        if isinstance(row, dict)
    }
    if identity["reasoning_effort"] not in efforts:
        raise QualificationError("accepted medium reasoning effort is absent from the local catalog")

    doctor_command = [
        codex_path,
        "doctor",
        "--json",
        "--config",
        f'model="{identity["model_id"]}"',
        *codex_config_arguments(MODEL_CATALOG_PATH),
    ]
    doctor_completed = subprocess.run(
        doctor_command,
        cwd=REPOSITORY_ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=child_env,
    )
    doctor_output = doctor_completed.stdout.strip()
    if not doctor_output:
        raise QualificationError(
            "Codex doctor returned no JSON: " + doctor_completed.stderr.strip()
        )
    doctor = json.loads(doctor_output)
    checks = doctor.get("checks")
    if not isinstance(checks, Mapping):
        raise QualificationError("Codex doctor did not return a check map")
    config_check = checks.get("config.load", {})
    auth_check = checks.get("auth.credentials", {})
    reachability_check = checks.get("network.provider_reachability", {})
    websocket_check = checks.get("network.websocket_reachability", {})
    config_details = config_check.get("details", {})
    auth_details = auth_check.get("details", {})
    reachability_details = reachability_check.get("details", {})
    websocket_details = websocket_check.get("details", {})
    if (
        config_check.get("status") != "ok"
        or config_details.get("model provider") != CODEX_PROVIDER_CONFIG_ID
        or config_details.get("model") != identity["model_id"]
    ):
        raise QualificationError("Codex doctor did not load the frozen repair provider/model")
    if (
        auth_check.get("status") != "ok"
        or auth_details.get("stored auth mode") != "chatgpt"
        or auth_details.get("stored ChatGPT tokens") != "true"
    ):
        raise QualificationError("Codex doctor did not confirm ChatGPT authentication")
    if (
        reachability_check.get("status") != "ok"
        or reachability_details.get("reachability mode") != "ChatGPT auth"
    ):
        raise QualificationError("Codex doctor did not resolve the ChatGPT provider endpoint")
    if (
        websocket_check.get("status") != "ok"
        or websocket_details.get("model provider") != CODEX_PROVIDER_CONFIG_ID
        or websocket_details.get("provider name") != CODEX_PROVIDER_NAME
        or websocket_details.get("supports websockets") != "false"
        or websocket_details.get("wire API") != "responses"
    ):
        raise QualificationError("Codex doctor did not confirm the frozen non-WebSocket provider")
    return {
        "schema_version": 1,
        "checked_at": utc_now(),
        "provider_baseline_id": identity["provider_baseline_id"],
        "provider_baseline_sha256": identity["provider_baseline_sha256"],
        "provider_id": identity["provider_id"],
        "codex_model_provider_config_id": CODEX_PROVIDER_CONFIG_ID,
        "codex_model_provider_name": CODEX_PROVIDER_NAME,
        "codex_model_provider_base_url": None,
        "codex_chatgpt_endpoint_resolution": identity[
            "codex_chatgpt_endpoint_resolution"
        ],
        "doctor_provider_endpoint_observation": reachability_details.get(
            "ChatGPT base URL", UNKNOWN
        ),
        "doctor_websocket_support": False,
        "execution_surface": identity["execution_surface"],
        "codex_cli_resolved_path": codex_path,
        "codex_cli_version": version,
        "catalog_model_id": identity["model_id"],
        "catalog_medium_reasoning_supported": True,
        "authentication_mode": "chatgpt",
        "authentication_status": auth_status,
        "billing_mode": "chatgpt-subscription",
        "api_key_fallback": "prohibited",
        "api_key_environment_present_in_parent": any(
            name in os.environ for name in API_ENVIRONMENT_NAMES
        ),
        "api_key_environment_removed_from_child": all(
            name not in child_env for name in API_ENVIRONMENT_NAMES
        ),
        "http_request_retries": 0,
        "stream_reconnect_retries": 0,
        "doctor_reachability_probe_made": True,
        "provider_cost_usd": UNKNOWN,
        "zero_model_calls": True,
    }


def build_prompt() -> str:
    identity, _ = validate_frozen_definition()
    program = (SUBSTRATE / identity["program_path"]).read_text(encoding="utf-8")
    task = load_json(SUBSTRATE / identity["task_input_path"])
    return (
        program
        + "\nFrozen task input (canonical JSON):\n"
        + canonical_json_bytes(task).decode("utf-8")
        + "\n"
    )


def build_provider_command(
    codex_path: str,
    workspace: Path,
    output_schema_path: Path,
    model_catalog_path: Path,
    raw_output_path: Path,
) -> list[str]:
    return [
        codex_path,
        "exec",
        "--strict-config",
        "--ignore-user-config",
        "--ignore-rules",
        "--model",
        "gpt-5.6-luna",
        *codex_config_arguments(model_catalog_path),
        "--json",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--cd",
        str(workspace),
        "--output-schema",
        str(output_schema_path),
        "--output-last-message",
        str(raw_output_path),
        "-",
    ]


def parse_provider_events(content: bytes) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    errors = 0
    for line in content.decode("utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            errors += 1
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            errors += 1
    return events, errors


def audit_provider_events(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    event_types: list[str] = []
    tool_event_hashes: list[str] = []
    retry_event_hashes: list[str] = []
    route_event_hashes: list[str] = []
    fallback_event_hashes: list[str] = []
    allowed_item_types = {"agent_message", "reasoning"}
    for event in events:
        event_type = str(event.get("type", ""))
        event_types.append(event_type)
        item = event.get("item")
        item_type = str(item.get("type", "")) if isinstance(item, Mapping) else ""
        encoded = json.dumps(event, ensure_ascii=False, sort_keys=True).lower()
        toolish = (
            any(
                token in event_type.lower()
                for token in ("tool", "command", "file_change", "web_search", "computer", "browser", "mcp")
            )
            or (item_type and item_type not in allowed_item_types)
            or any(
                token in encoded
                for token in ('"type": "command_execution"', '"type": "file_change"', '"type": "tool_call"')
            )
        )
        if toolish:
            tool_event_hashes.append(sha256_bytes(canonical_json_bytes(event)))
        retryish = any(token in event_type.lower() for token in ("retry", "reconnect")) or any(
            token in encoded for token in ("reconnecting...", "stream disconnected - retrying")
        )
        routeish = any(token in event_type.lower() for token in ("reroute", "routing")) or any(
            token in encoded for token in ('"model_reroute"', '"model.reroute"')
        )
        fallbackish = "fallback" in event_type.lower() or "falling back" in encoded
        event_hash = sha256_bytes(canonical_json_bytes(event))
        if retryish:
            retry_event_hashes.append(event_hash)
        if routeish:
            route_event_hashes.append(event_hash)
        if fallbackish:
            fallback_event_hashes.append(event_hash)
    return {
        "event_types": event_types,
        "tool_attempt_count": len(tool_event_hashes),
        "tool_attempted": bool(tool_event_hashes),
        "tool_event_hashes": tool_event_hashes,
        "retry_event_count": len(retry_event_hashes),
        "retry_event_hashes": retry_event_hashes,
        "route_event_count": len(route_event_hashes),
        "route_event_hashes": route_event_hashes,
        "fallback_event_count": len(fallback_event_hashes),
        "fallback_event_hashes": fallback_event_hashes,
    }


def extract_usage(events: Sequence[Mapping[str, Any]]) -> dict[str, int | str]:
    result: dict[str, int | str] = {
        "input_tokens": UNKNOWN,
        "cached_input_tokens": UNKNOWN,
        "cache_write_input_tokens": UNKNOWN,
        "output_tokens": UNKNOWN,
        "reasoning_tokens": UNKNOWN,
    }
    aliases = {
        "input_tokens": "input_tokens",
        "cached_input_tokens": "cached_input_tokens",
        "cache_write_input_tokens": "cache_write_input_tokens",
        "output_tokens": "output_tokens",
        "reasoning_output_tokens": "reasoning_tokens",
        "reasoning_tokens": "reasoning_tokens",
    }
    for event in events:
        usage = event.get("usage")
        if not isinstance(usage, Mapping):
            continue
        for source, target in aliases.items():
            value = usage.get(source)
            if isinstance(value, int):
                result[target] = value
    return result


def final_agent_message(events: Sequence[Mapping[str, Any]]) -> str | None:
    messages: list[str] = []
    for event in events:
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, Mapping)
            and item.get("type") == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            messages.append(str(item["text"]))
    return messages[-1] if messages else None


class CodexModelExecutorAdapter:
    """One frozen Codex CLI model invocation; no adjudication authority."""

    def __init__(
        self,
        *,
        run_dir: Path,
        preflight_record: Mapping[str, Any],
        definition_commit: str,
        code_commit: str,
        runner: Runner = subprocess.run,
    ) -> None:
        self.run_dir = Path(run_dir)
        self.preflight_record = dict(preflight_record)
        self.definition_commit = definition_commit
        self.code_commit = code_commit
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
        if request.operation != "select_record" or request.requires_mutation_prevention:
            raise ValueError("model adapter accepts only the frozen read-only selection request")
        if self.invocation_attempts != 0:
            raise ValueError("the one-call ceiling has already been consumed")
        if self.run_dir.exists():
            raise FileExistsError(f"immutable run directory already exists: {self.run_dir}")
        self.run_dir.mkdir(parents=True)

        prompt = build_prompt()
        prompt_bytes = prompt.encode("utf-8")
        start_utc = utc_now()
        start_ns = time.perf_counter_ns()
        self.invocation_attempts = 1
        return_code: int | str = "not_started"
        timed_out = False
        stdout_text = ""
        stderr_text = ""
        output_bytes: bytes | None = None

        with tempfile.TemporaryDirectory(prefix="irisx-model-qualification-") as temporary:
            workspace = Path(temporary)
            schema_copy = workspace / "output-schema.json"
            schema_copy.write_bytes(OUTPUT_SCHEMA_PATH.read_bytes())
            model_catalog_copy = workspace / "model-catalog.json"
            model_catalog_copy.write_bytes(MODEL_CATALOG_PATH.read_bytes())
            raw_output_temp = workspace / "raw-output.txt"
            command = build_provider_command(
                str(self.preflight_record["codex_cli_resolved_path"]),
                workspace,
                schema_copy,
                model_catalog_copy,
                raw_output_temp,
            )
            attempt_start = {
                "schema_version": 1,
                "run_id": RUN_ID,
                "started_at": start_utc,
                "definition_commit": self.definition_commit,
                "code_commit": self.code_commit,
                "provider_attempt": 1,
                "model_calls_committed_ceiling": 1,
                "preserved_prior_logical_attempts": 1,
                "batch_4_lineage_logical_attempt_ceiling": 2,
                "retry_count": 0,
                "codex_model_provider_config_id": CODEX_PROVIDER_CONFIG_ID,
                "command": command,
                "api_key_environment_removed_from_child": True,
            }
            write_new(self.run_dir / "attempt-start.json", pretty_json_bytes(attempt_start))
            try:
                completed = self.runner(
                    command,
                    input=prompt,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=REPOSITORY_ROOT,
                    env=codex_environment(),
                    timeout=600,
                    check=False,
                )
                return_code = completed.returncode
                stdout_text = completed.stdout or ""
                stderr_text = completed.stderr or ""
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                return_code = "timeout"
                stdout_text = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode(
                    "utf-8", errors="replace"
                )
                stderr_text = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode(
                    "utf-8", errors="replace"
                )
            except Exception as exc:
                return_code = "process_start_failure"
                stderr_text = f"{type(exc).__name__}: {exc}\n"
            if raw_output_temp.exists():
                output_bytes = raw_output_temp.read_bytes()

        stdout_bytes = stdout_text.encode("utf-8")
        stderr_bytes = stderr_text.encode("utf-8")
        write_new(self.run_dir / "provider-events.jsonl", stdout_bytes)
        write_new(self.run_dir / "provider-stderr.txt", stderr_bytes)
        write_new(self.run_dir / "raw-output.txt", output_bytes or b"")

        wall_time_ns = time.perf_counter_ns() - start_ns
        events, parse_errors = parse_provider_events(stdout_bytes)
        event_audit = audit_provider_events(events)
        usage = extract_usage(events)
        event_message = final_agent_message(events)
        file_message = output_bytes.decode("utf-8", errors="replace") if output_bytes is not None else None
        resource_report = AdapterResourceReport(
            model_calls=1,
            network_calls=UNKNOWN,
            paid_api_calls=0,
            tool_calls=event_audit["tool_attempt_count"],
            retry_count=event_audit["retry_event_count"],
            route_count=event_audit["route_event_count"],
            escalation_count=0,
            recovery_count=event_audit["fallback_event_count"],
            wall_time_ns=wall_time_ns,
            provider_cost_usd=UNKNOWN,
        )
        self.capture = {
            "started_at": start_utc,
            "ended_at": utc_now(),
            "wall_time_ns": wall_time_ns,
            "command": command,
            "process_return_code": return_code,
            "timed_out": timed_out,
            "provider_event_parse_errors": parse_errors,
            "event_audit": event_audit,
            "event_final_message": event_message,
            "raw_output_present": output_bytes is not None,
            "raw_output_matches_event_message": (
                file_message.strip() == event_message.strip()
                if file_message is not None and event_message is not None
                else False
            ),
            "usage": usage,
            "prompt_sha256": sha256_bytes(prompt_bytes),
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
        if event_audit["tool_attempted"]:
            failure_reasons.append("prohibited_tool_attempt")
        if event_audit["retry_event_count"]:
            failure_reasons.append("prohibited_retry_observed")
        if event_audit["route_event_count"]:
            failure_reasons.append("prohibited_route_observed")
        if event_audit["fallback_event_count"]:
            failure_reasons.append("prohibited_transport_fallback_observed")
        if event_message is not None and file_message is not None and not self.capture[
            "raw_output_matches_event_message"
        ]:
            failure_reasons.append("raw_output_event_mismatch")
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


class RecordSelectionVerifier:
    """Fixture-local deterministic parser, oracle, evidence, and state check."""

    def __init__(self, expected_selected_id: str) -> None:
        self.expected_selected_id = expected_selected_id

    def verify(
        self,
        context: ExecutionContext,
        request: ExecutionRequest,
        raw_result: RawResult,
        before_state: Mapping[str, Any],
        after_state: Mapping[str, Any],
    ) -> VerificationResult:
        del request
        reasons: list[str] = []
        if before_state != after_state:
            reasons.append("read_only_state_changed")
        parsed: Any = None
        if not isinstance(raw_result.reported_value, str) or not raw_result.reported_value.strip():
            reasons.append("provider_output_not_captured")
        else:
            try:
                parsed = json.loads(raw_result.reported_value)
            except json.JSONDecodeError:
                reasons.append("provider_output_malformed_json")
        if parsed is not None:
            if not isinstance(parsed, dict) or set(parsed) != {"selected_id"}:
                reasons.append("provider_output_contract_mismatch")
            elif not isinstance(parsed["selected_id"], str):
                reasons.append("selected_id_not_string")
            elif parsed["selected_id"] != self.expected_selected_id:
                reasons.append("selected_id_oracle_mismatch")
        evidence_status, evidence_reasons = evidence_binding(
            context.evidence_requirements, raw_result.evidence
        )
        return VerificationResult(
            semantic_valid=not reasons,
            semantic_reasons=tuple(reasons or ("deterministic_record_selection_match",)),
            evidence_status=evidence_status,
            evidence_reasons=evidence_reasons,
            observed_post_state_sha256=state_sha256(after_state),
        )


def core_inputs() -> tuple[
    TaskContract,
    ProgramArtifact,
    ExecutionIdentity,
    ExecutionRequest,
    dict[str, Any],
    RecordSelectionVerifier,
]:
    identity, contract = validate_frozen_definition()
    contract_bytes = CONTRACT_PATH.read_bytes()
    program_bytes = (SUBSTRATE / identity["program_path"]).read_bytes()
    task_input = load_json(SUBSTRATE / identity["task_input_path"])
    core_contract = TaskContract(
        task_id=contract["task_id"],
        contract_id=contract["contract_id"],
        expected_program_id=contract["program"]["program_id"],
        expected_program_sha256=contract["program"]["sha256"],
        execution_id=contract["execution"]["execution_id"],
        configuration_id=contract["execution"]["configuration_id"],
        content=contract_bytes,
        evidence_requirements=tuple(
            EvidenceRequirement(**row) for row in contract["evidence_requirements"]
        ),
    )
    program = ProgramArtifact(
        identity["program_id"], identity["program_path"], program_bytes
    )
    execution_identity = ExecutionIdentity(
        identity["task_id"],
        identity["contract_id"],
        identity["program_id"],
        identity["execution_id"],
        identity["configuration_id"],
    )
    request = ExecutionRequest(
        **contract["request"], requires_mutation_prevention=False
    )
    state = {"task_input": copy.deepcopy(task_input)}
    verifier = RecordSelectionVerifier(contract["success_condition"]["selected_id"])
    return core_contract, program, execution_identity, request, state, verifier


def execute_with_adapter(adapter: CodexModelExecutorAdapter) -> dict[str, Any]:
    contract, program, identity, request, state, verifier = core_inputs()
    terminal = execute(
        contract=contract,
        program=program,
        supplied_identity=identity,
        request=request,
        state=state,
        executor=adapter,
        verifier=verifier,
        collect_observations=True,
    )
    return terminal_record_to_dict(terminal)


def artifact_hash_record(path: Path) -> dict[str, Any]:
    content = path.read_bytes()
    return {"path": path.relative_to(SUBSTRATE).as_posix(), "bytes": len(content), "sha256": sha256_bytes(content)}


def finalize_run(
    *,
    adapter: CodexModelExecutorAdapter,
    terminal: Mapping[str, Any],
    preflight_record: Mapping[str, Any],
    definition_commit: str,
    code_commit: str,
) -> dict[str, Any]:
    if adapter.capture is None or adapter.invocation_attempts != 1:
        raise QualificationError("one provider attempt was not captured")
    write_new(RUN_DIR / "terminal-record.json", pretty_json_bytes(terminal))
    ledger = dict(terminal["resource_ledger"])
    resource_record = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "preserved_prior_logical_attempts": 1,
        "batch_4_lineage_logical_attempts_after_run": 2,
        "provider_attempts": 1,
        "model_calls": ledger["model_calls"],
        "network_calls": ledger["network_calls"],
        "paid_api_calls": ledger["paid_api_calls"],
        "tool_calls": ledger["tool_calls"],
        "retry_count": ledger["retry_count"],
        "route_count": ledger["route_count"],
        "escalation_count": ledger["escalation_count"],
        "recovery_count": ledger["recovery_count"],
        "wall_time_ns": ledger["wall_time_ns"],
        "provider_cost_usd": ledger["provider_cost_usd"],
        "token_usage": adapter.capture["usage"],
        "transport_request_count": UNKNOWN,
        "price_basis": "no-run-attributable-chatgpt-subscription-price-basis-available",
    }
    write_new(RUN_DIR / "resource-record.json", pretty_json_bytes(resource_record))
    immutable = [
        artifact_hash_record(RUN_DIR / name)
        for name in (
            "attempt-start.json",
            "provider-events.jsonl",
            "provider-stderr.txt",
            "raw-output.txt",
            "terminal-record.json",
            "resource-record.json",
        )
    ]
    identity, contract = validate_frozen_definition()
    manifest = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "definition_commit": definition_commit,
        "code_commit": code_commit,
        "required_starting_sha": contract["freeze_requirements"]["required_starting_sha"],
        "provider_configuration": {
            "provider_baseline_id": identity["provider_baseline_id"],
            "provider_baseline_sha256": identity["provider_baseline_sha256"],
            "provider_id": identity["provider_id"],
            "execution_surface": identity["execution_surface"],
            "codex_model_provider_config_id": identity[
                "codex_model_provider_config_id"
            ],
            "codex_model_provider_name": identity["codex_model_provider_name"],
            "codex_model_provider_base_url": identity[
                "codex_model_provider_base_url"
            ],
            "codex_chatgpt_endpoint_resolution": identity[
                "codex_chatgpt_endpoint_resolution"
            ],
            "codex_cli_source_observation": identity[
                "codex_cli_source_observation"
            ],
            "model_role": identity["model_role"],
            "model_id": identity["model_id"],
            "reasoning_effort": identity["reasoning_effort"],
            "authentication_mode": "chatgpt",
            "billing_mode": "chatgpt-subscription",
            "api_key_fallback": "not-used-child-environment-sanitized",
            "codex_cli_resolved_path": preflight_record["codex_cli_resolved_path"],
            "codex_cli_version": preflight_record["codex_cli_version"],
            "catalog_checked_at": preflight_record["checked_at"],
            "doctor_provider_endpoint_observation": preflight_record[
                "doctor_provider_endpoint_observation"
            ],
            "http_request_retries": 0,
            "stream_reconnect_retries": 0,
            "websocket_transport": False,
        },
        "candidate_identity": {
            "task_id": identity["task_id"],
            "contract_id": identity["contract_id"],
            "contract_sha256": identity["contract_sha256"],
            "program_id": identity["program_id"],
            "program_sha256": identity["program_sha256"],
            "execution_id": identity["execution_id"],
            "configuration_id": identity["configuration_id"],
            "prompt_sha256": adapter.capture["prompt_sha256"],
        },
        "execution_envelope": contract["execution_envelope"],
        "call_ceiling": contract["call_ceiling"],
        "call_ledger": {
            "preserved_prior_logical_attempts": 1,
            "provider_attempts": 1,
            "model_calls": terminal["resource_ledger"]["model_calls"],
            "batch_4_lineage_logical_attempts": 2,
            "retries": terminal["resource_ledger"]["retry_count"],
            "routes": terminal["resource_ledger"]["route_count"],
            "escalations": terminal["resource_ledger"]["escalation_count"],
            "recovery_actions": terminal["resource_ledger"]["recovery_count"],
        },
        "provider_capture": {
            key: value
            for key, value in adapter.capture.items()
            if key not in {"resource_report"}
        },
        "terminal_semantics": {
            key: terminal[key]
            for key in (
                "actual_outcome",
                "producer_claim",
                "empirical_evidence_status",
                "acceptance_decision",
                "verified_success_eligibility",
                "joint_interpretation",
                "terminal_execution_status",
            )
        },
        "state_before_sha256": terminal["side_effects"]["state_before_sha256"],
        "state_after_sha256": terminal["side_effects"]["state_after_sha256"],
        "changed_paths": terminal["side_effects"]["changed_paths"],
        "immutable_artifacts": immutable,
    }
    write_new(RUN_DIR / "run-manifest.json", pretty_json_bytes(manifest))
    return manifest


def validate_run_artifacts(run_dir: Path = RUN_DIR) -> dict[str, Any]:
    required = {
        "attempt-start.json",
        "provider-events.jsonl",
        "provider-stderr.txt",
        "raw-output.txt",
        "terminal-record.json",
        "resource-record.json",
        "run-manifest.json",
    }
    if not run_dir.is_dir():
        raise QualificationError(f"run directory is absent: {run_dir}")
    names = {path.name for path in run_dir.iterdir() if path.is_file()}
    missing = required - names
    if missing:
        raise QualificationError(f"run artifacts missing: {sorted(missing)}")
    manifest = load_json(run_dir / "run-manifest.json")
    terminal = load_json(run_dir / "terminal-record.json")
    resources = load_json(run_dir / "resource-record.json")
    if manifest["run_id"] != run_dir.name or resources["run_id"] != run_dir.name:
        raise QualificationError("run identity does not match its immutable directory")
    for record in manifest["immutable_artifacts"]:
        path = SUBSTRATE / record["path"]
        content = path.read_bytes()
        if len(content) != record["bytes"] or sha256_bytes(content) != record["sha256"]:
            raise QualificationError(f"immutable artifact mismatch: {path}")
    ledger = terminal["resource_ledger"]
    if resources["model_calls"] != 1 or ledger["model_calls"] != 1:
        raise QualificationError("observed provider invocation must record one model call")
    excluded_counts = {
        field: resources[field]
        for field in ("retry_count", "route_count", "escalation_count", "recovery_count")
    }
    for field, count in excluded_counts.items():
        if ledger[field] != count:
            raise QualificationError(f"terminal/resource disagreement: {field}")
    if any(excluded_counts.values()) and (
        terminal["actual_outcome"] != "failure"
        or terminal["acceptance_decision"] != "reject"
        or terminal["verified_success_eligibility"] is not False
    ):
        raise QualificationError("excluded mechanism use did not fail closed")
    if resources["network_calls"] != UNKNOWN or ledger["network_calls"] != UNKNOWN:
        raise QualificationError("unexposed transport count must remain Unknown")
    if terminal["side_effects"]["state_before_sha256"] != terminal["side_effects"][
        "state_after_sha256"
    ]:
        raise QualificationError("read-only task state changed")
    if terminal["side_effects"]["changed_paths"]:
        raise QualificationError("read-only task reports changed paths")
    return {
        "run_id": manifest["run_id"],
        "artifact_count": len(required),
        "terminal_semantics": manifest["terminal_semantics"],
        "resource_record": resources,
        "excluded_mechanism_counts": excluded_counts,
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--validate-run", action="store_true")
    parser.add_argument("--write-preflight", type=Path)
    parser.add_argument("--definition-commit")
    parser.add_argument("--code-commit")
    parser.add_argument("--run-id", choices=(ORIGINAL_RUN_ID, RUN_ID), default=RUN_ID)
    args = parser.parse_args()

    try:
        if args.preflight:
            record = preflight()
            if args.write_preflight is not None:
                write_new(args.write_preflight, pretty_json_bytes(record))
            print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.validate_run:
            run_dir = SUBSTRATE / "runs" / args.run_id
            print(
                json.dumps(
                    validate_run_artifacts(run_dir),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if not args.definition_commit or not args.code_commit:
            raise QualificationError("live mode requires both full freeze commit identities")
        require_clean_frozen_head(args.definition_commit, args.code_commit)
        preflight_record = preflight()
        adapter = CodexModelExecutorAdapter(
            run_dir=RUN_DIR,
            preflight_record=preflight_record,
            definition_commit=args.definition_commit,
            code_commit=args.code_commit,
        )
        terminal = execute_with_adapter(adapter)
        manifest = finalize_run(
            adapter=adapter,
            terminal=terminal,
            preflight_record=preflight_record,
            definition_commit=args.definition_commit,
            code_commit=args.code_commit,
        )
        print(json.dumps(manifest["terminal_semantics"], ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, QualificationError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"model execution qualification: FAIL ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
