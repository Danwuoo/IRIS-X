#!/usr/bin/env python3
"""Zero-model-call admission checks for the exact Codex 0.147.0 Run 03 profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SUBSTRATE = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
TOOLS = REPOSITORY_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import model_baseline_check as baseline_check  # noqa: E402


PROFILE_PATH = SUBSTRATE / "admission" / "codex-cli-0.147.0-run-03-profile.json"
BASELINE_PATH = REPOSITORY_ROOT / "experiments" / "configurations" / "provider-model-baseline-v0.json"
RUNS = {
    "01": {
        "run_id": "qualification-20260905-01",
        "contract": "qualification-contract.json",
        "identity": "execution-identity.json",
        "preflight": "preflight-observation.json",
    },
    "02": {
        "run_id": "qualification-20260905-02",
        "contract": "qualification-repair-contract.json",
        "identity": "repair-execution-identity.json",
        "preflight": "repair-preflight-observation.json",
    },
    "03": {
        "run_id": "qualification-20260905-03",
        "contract": "qualification-run-03-contract.json",
        "identity": "run-03-execution-identity.json",
        "preflight": "run-03-preflight-observation.json",
    },
}


class AdmissionError(RuntimeError):
    """Admission input is malformed and cannot be evaluated safely."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise AdmissionError(f"JSON top level must be an object: {path}")
    return value


def strip_toml_string(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def parse_command(command: Sequence[str]) -> dict[str, Any]:
    if len(command) < 2 or not all(isinstance(item, str) for item in command):
        raise AdmissionError("command must be a string argument sequence")
    configs: dict[str, str] = {}
    duplicates: list[str] = []
    disabled: list[str] = []
    values: dict[str, str] = {}
    index = 2
    while index < len(command):
        argument = command[index]
        if argument == "--config":
            if index + 1 >= len(command) or "=" not in command[index + 1]:
                raise AdmissionError("malformed --config argument")
            key, value = command[index + 1].split("=", 1)
            if key in configs:
                duplicates.append(key)
            configs[key] = strip_toml_string(value)
            index += 2
            continue
        if argument == "--disable":
            if index + 1 >= len(command):
                raise AdmissionError("malformed --disable argument")
            disabled.append(command[index + 1])
            index += 2
            continue
        if argument in {"--model", "--sandbox", "--cd", "--output-schema", "--output-last-message"}:
            if index + 1 >= len(command):
                raise AdmissionError(f"malformed {argument} argument")
            values[argument] = command[index + 1]
            index += 2
            continue
        index += 1
    return {
        "configs": configs,
        "duplicate_configs": duplicates,
        "disabled_features": disabled,
        "values": values,
    }


def normalize_command(command: Sequence[str]) -> list[str]:
    parse_command(command)
    normalized = list(command)
    normalized[0] = "<resolved-codex-command>"
    index = 2
    while index < len(normalized):
        argument = normalized[index]
        if argument == "--config":
            value = normalized[index + 1]
            if value.startswith("model_catalog_json="):
                normalized[index + 1] = 'model_catalog_json="<isolated-model-catalog-path>"'
            index += 2
            continue
        replacements = {
            "--cd": "<isolated-temporary-directory>",
            "--output-schema": "<isolated-output-schema-path>",
            "--output-last-message": "<isolated-raw-output-path>",
        }
        if argument in replacements:
            normalized[index + 1] = replacements[argument]
            index += 2
            continue
        if argument in {"--disable", "--model", "--sandbox"}:
            index += 2
            continue
        index += 1
    return normalized


def profile_identity(profile: Mapping[str, Any]) -> tuple[str, str]:
    return str(profile["profile_id"]), sha256_bytes(PROFILE_PATH.read_bytes())


def historical_candidate(run_number: str) -> dict[str, Any]:
    definition = SUBSTRATE / "definition"
    descriptor = RUNS[run_number]
    run_dir = SUBSTRATE / "runs" / descriptor["run_id"]
    contract_path = definition / descriptor["contract"]
    identity_path = definition / descriptor["identity"]
    preflight_path = definition / descriptor["preflight"]
    attempt_path = run_dir / "attempt-start.json"
    contract = load_object(contract_path)
    identity = load_object(identity_path)
    preflight = load_object(preflight_path)
    attempt = load_object(attempt_path)
    command = attempt.get("command")
    if not isinstance(command, list):
        raise AdmissionError(f"historical command missing: {attempt_path}")
    return {
        "source_kind": "historical-replay",
        "source_id": descriptor["run_id"],
        "contract": contract,
        "identity": identity,
        "preflight": preflight,
        "command": command,
        "source_artifacts": {
            str(contract_path.relative_to(SUBSTRATE)).replace("\\", "/"): sha256_bytes(contract_path.read_bytes()),
            str(identity_path.relative_to(SUBSTRATE)).replace("\\", "/"): sha256_bytes(identity_path.read_bytes()),
            str(preflight_path.relative_to(SUBSTRATE)).replace("\\", "/"): sha256_bytes(preflight_path.read_bytes()),
            str(attempt_path.relative_to(SUBSTRATE)).replace("\\", "/"): sha256_bytes(attempt_path.read_bytes()),
        },
        "local_check_errors": [],
        "provider_baseline_check": "frozen-observation",
        "local_catalog_check": "frozen-observation",
        "api_environment_names_present": [],
        "api_key_environment_removed_from_child": True,
    }


def current_candidate(profile: Mapping[str, Any]) -> dict[str, Any]:
    candidate = historical_candidate("03")
    candidate["source_kind"] = "current-environment-static-run-03-profile"
    candidate["source_id"] = "current-environment"
    errors: list[dict[str, str]] = []
    candidate["provider_baseline_check"] = "PASS"
    candidate["local_catalog_check"] = "PASS"
    try:
        baseline_errors = baseline_check.validate_baseline(baseline_check.load_baseline())
        errors.extend({"status": "rejected", "reason": f"provider_baseline_invalid:{item}"} for item in baseline_errors)
        if baseline_errors:
            candidate["provider_baseline_check"] = "FAIL"
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        candidate["provider_baseline_check"] = "FAIL"
        errors.append({"status": "rejected", "reason": f"provider_baseline_unavailable:{type(exc).__name__}"})

    try:
        codex_path = str(Path(baseline_check.resolve_codex_command(None)).resolve())
    except OSError:
        candidate["preflight"] = {
            "codex_cli_resolved_path": None,
            "codex_cli_version": None,
            "authentication_mode": "Unknown",
            "authentication_status": "Unknown",
        }
        candidate["local_check_errors"] = [
            *errors,
            {"status": "unsupported", "reason": "cli_executable_missing"},
        ]
        return candidate

    version: str | None = None
    try:
        catalog_errors, version = baseline_check.validate_local_catalog(codex_path)
        errors.extend({"status": "rejected", "reason": f"local_catalog_invalid:{item}"} for item in catalog_errors)
        if catalog_errors:
            candidate["local_catalog_check"] = "FAIL"
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
        candidate["local_catalog_check"] = "UNAVAILABLE"
        errors.append({"status": "unsupported", "reason": "local_catalog_unavailable"})

    auth_mode = "Unknown"
    auth_status = "Unknown"
    try:
        completed = subprocess.run(
            [codex_path, "login", "status"],
            cwd=REPOSITORY_ROOT,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=sanitized_environment(profile),
        )
        auth_status = (completed.stdout or completed.stderr).strip()
        if completed.returncode == 0 and auth_status == "Logged in using ChatGPT":
            auth_mode = "chatgpt"
        else:
            errors.append(
                {"status": "unsupported", "reason": "chatgpt_authentication_not_locally_established"}
            )
    except OSError:
        errors.append(
            {"status": "unsupported", "reason": "chatgpt_authentication_not_locally_established"}
        )

    command = list(candidate["command"])
    command[0] = codex_path
    candidate["command"] = command
    candidate["preflight"] = {
        "codex_cli_resolved_path": codex_path,
        "codex_cli_version": version,
        "authentication_mode": auth_mode,
        "authentication_status": auth_status,
    }
    names = profile["provider"]["api_environment_names"]
    candidate["api_environment_names_present"] = sorted(name for name in names if name in os.environ)
    child = sanitized_environment(profile)
    candidate["api_key_environment_removed_from_child"] = all(name not in child for name in names)
    candidate["local_check_errors"] = errors
    return candidate


def sanitized_environment(profile: Mapping[str, Any]) -> dict[str, str]:
    child = dict(os.environ)
    for name in profile["provider"]["api_environment_names"]:
        child.pop(name, None)
    return child


def append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def evaluate(candidate: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, Any]:
    identity = candidate["identity"]
    contract = candidate["contract"]
    preflight = candidate["preflight"]
    command = candidate["command"]
    normalized = normalize_command(command)
    parsed = parse_command(command)
    configs = parsed["configs"]
    disabled = parsed["disabled_features"]
    values = parsed["values"]
    profile_id, profile_sha = profile_identity(profile)
    command_sha = sha256_bytes(canonical_json_bytes(normalized))
    expected_command_sha = sha256_bytes(canonical_json_bytes(profile["canonical_argv"]))
    reasons: list[str] = []
    unsupported: list[str] = []

    if candidate["source_kind"] == "historical-replay":
        expected_sources = profile["historical_replay_inputs"].get(candidate["source_id"], {})
        for path, expected_hash in expected_sources.items():
            if candidate["source_artifacts"].get(path) != expected_hash:
                reasons.append(f"historical_source_hash_mismatch:{path}")
        if reasons:
            return admission_record(
                candidate, profile, normalized, command_sha, expected_command_sha, "rejected", reasons
            )

    reserved = profile["provider"]["reserved_builtin_id"]
    if any(key.startswith(f"model_providers.{reserved}.") for key in configs):
        reasons.append("reserved_provider_configuration_incompatible")
        return admission_record(
            candidate, profile, normalized, command_sha, expected_command_sha, "rejected", reasons
        )
    for field in profile["execution_envelope"]["known_unsupported_config_fields"]:
        if field in configs:
            reasons.append(f"unsupported_config_field:{field}")
    if reasons:
        return admission_record(
            candidate, profile, normalized, command_sha, expected_command_sha, "rejected", reasons
        )

    for finding in candidate.get("local_check_errors", []):
        target = unsupported if finding["status"] == "unsupported" else reasons
        append_once(target, finding["reason"])
    if sha256_bytes(BASELINE_PATH.read_bytes()) != profile["provider_baseline"]["sha256"]:
        append_once(reasons, "provider_baseline_hash_mismatch")
    if identity.get("provider_baseline_id") != profile["provider_baseline"]["id"]:
        append_once(reasons, "provider_baseline_id_mismatch")
    if identity.get("provider_baseline_sha256") != profile["provider_baseline"]["sha256"]:
        append_once(reasons, "provider_baseline_identity_hash_mismatch")
    if identity.get("execution_surface") != profile["execution_surface"]:
        append_once(reasons, "execution_surface_mismatch")
    observed_version = preflight.get("codex_cli_version")
    if observed_version != profile["required_cli_version"]:
        append_once(unsupported, "unsupported_version")
    observed_path = preflight.get("codex_cli_resolved_path")
    if not observed_path:
        append_once(unsupported, "cli_executable_missing")
    elif str(Path(observed_path)).lower() != str(Path(profile["required_resolved_path"])).lower():
        append_once(unsupported, "unsupported_executable_path")
    if identity.get("model_role") != profile["model"]["role"]:
        append_once(reasons, "model_role_mismatch")
    if identity.get("model_id") != profile["model"]["id"] or values.get("--model") != profile["model"]["id"]:
        append_once(reasons, "model_mismatch")
    if identity.get("reasoning_effort") != profile["model"]["reasoning_effort"] or configs.get(
        "model_reasoning_effort"
    ) != profile["model"]["reasoning_effort"]:
        append_once(reasons, "reasoning_effort_mismatch")
    auth_mode = preflight.get("authentication_mode", identity.get("authentication_mode"))
    if auth_mode != profile["provider"]["authentication_mode"]:
        append_once(unsupported, "chatgpt_authentication_not_locally_established")
    if "prohibited" not in str(identity.get("api_key_fallback", "")):
        append_once(reasons, "api_key_fallback_configured")
    if not candidate.get("api_key_environment_removed_from_child"):
        append_once(reasons, "api_key_fallback_sanitation_missing")

    slot = configs.get("model_provider")
    required_slot = profile["provider"]["required_custom_slot"]
    if slot != required_slot:
        append_once(reasons, "provider_slot_mismatch")
    expected_configs = {
        f"model_providers.{required_slot}.name": profile["provider"]["required_name"],
        f"model_providers.{required_slot}.requires_openai_auth": "true",
        f"model_providers.{required_slot}.wire_api": profile["provider"]["required_wire_api"],
        f"model_providers.{required_slot}.request_max_retries": "0",
        f"model_providers.{required_slot}.stream_max_retries": "0",
        f"model_providers.{required_slot}.supports_websockets": "false",
        f"model_providers.{required_slot}.supports_standalone_web_search": "false",
        "approval_policy": profile["execution_envelope"]["approval_policy"],
        "web_search": "disabled",
        "tools.web_search": "false",
        "apps._default.enabled": "false",
        "agents.enabled": "false",
    }
    for key, expected in expected_configs.items():
        if configs.get(key) != expected:
            reason = "retry_settings_nonzero_or_missing" if key.endswith(("request_max_retries", "stream_max_retries")) else f"configuration_mismatch:{key}"
            append_once(reasons, reason)
    if configs.get(f"model_providers.{required_slot}.supports_websockets") != "false":
        append_once(reasons, "websocket_transport_enabled_or_unspecified")
    if values.get("--sandbox") != profile["execution_envelope"]["sandbox"]:
        append_once(reasons, "sandbox_broader_than_read_only")
    if parsed["duplicate_configs"]:
        append_once(reasons, "duplicate_configuration_fields")
    expected_config_keys = {
        item.split("=", 1)[0]
        for index, item in enumerate(profile["canonical_argv"])
        if index > 0 and profile["canonical_argv"][index - 1] == "--config"
    }
    for key in sorted(set(configs) - expected_config_keys):
        append_once(reasons, f"unknown_material_configuration:{key}")
    if disabled != profile["execution_envelope"]["required_disabled_features"]:
        append_once(reasons, "tool_envelope_mismatch")
    if command_sha != expected_command_sha:
        append_once(reasons, "command_identity_mismatch")
    definition = profile["qualified_definition"]
    if identity.get("configuration_id") != definition["configuration_id"]:
        append_once(reasons, "configuration_identity_mismatch")
    if candidate["source_kind"] != "historical-replay" or candidate["source_id"] == RUNS["03"]["run_id"]:
        if candidate["source_artifacts"].get(definition["contract_path"]) != definition["contract_sha256"]:
            append_once(reasons, "qualified_contract_hash_mismatch")
        if candidate["source_artifacts"].get(definition["identity_path"]) != definition["identity_sha256"]:
            append_once(reasons, "qualified_identity_hash_mismatch")
    contract_provider = contract.get("provider_configuration", {})
    if contract_provider.get("model_id") != profile["model"]["id"]:
        append_once(reasons, "contract_model_mismatch")

    status = "rejected" if reasons else "unsupported" if unsupported else "admitted"
    findings = reasons if reasons else unsupported
    return admission_record(
        candidate, profile, normalized, command_sha, expected_command_sha, status, findings
    )


def admission_record(
    candidate: Mapping[str, Any],
    profile: Mapping[str, Any],
    normalized: Sequence[str],
    command_sha: str,
    expected_command_sha: str,
    status: str,
    reasons: Sequence[str],
) -> dict[str, Any]:
    identity = candidate["identity"]
    preflight = candidate["preflight"]
    parsed = parse_command(candidate["command"])
    profile_id, profile_sha = profile_identity(profile)
    slot = parsed["configs"].get("model_provider")
    configuration_input = {
        "profile_id": profile_id,
        "configuration_id": identity.get("configuration_id"),
        "command_sha256": command_sha,
        "environment_policy": "remove-declared-api-key-and-endpoint-variables-from-future-child",
        "authentication_mode": preflight.get("authentication_mode", identity.get("authentication_mode")),
    }
    api_key_fallback_present = not (
        "prohibited" in str(identity.get("api_key_fallback", ""))
        and bool(candidate.get("api_key_environment_removed_from_child"))
    )

    def parsed_integer(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    websocket_value = parsed["configs"].get(
        f"model_providers.{slot}.supports_websockets" if slot else ""
    )
    return {
        "schema_version": 1,
        "status": status,
        "reasons": list(reasons),
        "source_kind": candidate["source_kind"],
        "source_id": candidate["source_id"],
        "execution_surface": identity.get("execution_surface"),
        "observed_cli_version": preflight.get("codex_cli_version"),
        "observed_cli_path": preflight.get("codex_cli_resolved_path"),
        "provider_baseline_id": identity.get("provider_baseline_id"),
        "provider_baseline_sha256": sha256_bytes(BASELINE_PATH.read_bytes()),
        "provider_baseline_check": candidate.get("provider_baseline_check"),
        "local_catalog_check": candidate.get("local_catalog_check"),
        "local_catalog_required_model": profile["model"]["id"],
        "local_catalog_required_reasoning_effort": profile["model"]["reasoning_effort"],
        "configuration_identity": identity.get("configuration_id"),
        "configuration_input_sha256": sha256_bytes(canonical_json_bytes(configuration_input)),
        "canonical_command": list(normalized),
        "command_sha256": command_sha,
        "expected_command_sha256": expected_command_sha,
        "compatibility_profile_id": profile_id,
        "compatibility_profile_sha256": profile_sha,
        "authentication_mode": preflight.get("authentication_mode", identity.get("authentication_mode")),
        "billing_mode": identity.get("billing_mode"),
        "api_key_environment_names_present_in_parent": list(candidate.get("api_environment_names_present", [])),
        "api_key_fallback_present": api_key_fallback_present,
        "api_key_fallback_sanitation_policy": "remove-declared-api-key-and-endpoint-variables-from-future-child",
        "provider_slot": slot,
        "model_role": identity.get("model_role"),
        "model_id": identity.get("model_id"),
        "reasoning_effort": identity.get("reasoning_effort"),
        "http_request_retries": parsed_integer(parsed["configs"].get(
            f"model_providers.{slot}.request_max_retries" if slot else ""
        )),
        "stream_reconnect_retries": parsed_integer(parsed["configs"].get(
            f"model_providers.{slot}.stream_max_retries" if slot else ""
        )),
        "websocket_transport": (
            False if websocket_value == "false" else True if websocket_value == "true" else None
        ),
        "sandbox": parsed["values"].get("--sandbox"),
        "disabled_features": parsed["disabled_features"],
        "source_artifacts": candidate["source_artifacts"],
        "provider_attempts": 0,
        "live_model_calls": 0,
        "future_model_execution_authorized": False,
    }


def replay(run_number: str) -> dict[str, Any]:
    profile = load_object(PROFILE_PATH)
    return evaluate(historical_candidate(run_number), profile)


def current_environment() -> dict[str, Any]:
    profile = load_object(PROFILE_PATH)
    return evaluate(current_candidate(profile), profile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--replay-run-01", action="store_true")
    mode.add_argument("--replay-run-02", action="store_true")
    mode.add_argument("--replay-run-03", action="store_true")
    mode.add_argument("--current", action="store_true")
    args = parser.parse_args()
    try:
        if args.replay_run_01:
            record = replay("01")
        elif args.replay_run_02:
            record = replay("02")
        elif args.replay_run_03:
            record = replay("03")
        else:
            record = current_environment()
        print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if record["status"] == "admitted" else 2
    except (AdmissionError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"model execution admission: FAIL ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
