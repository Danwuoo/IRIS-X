#!/usr/bin/env python3
"""Validate the accepted IRIS-X provider/model baseline without model calls."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "experiments" / "configurations" / "provider-model-baseline-v0.json"
EXPECTED_MODELS = {
    "strong": "gpt-5.6-terra",
    "cheaper": "gpt-5.6-luna",
}


def load_baseline() -> dict[str, Any]:
    with BASELINE.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("baseline top level must be an object")
    return value


def validate_baseline(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(value.get("schema_version") == 1, "schema_version must be 1")
    require(value.get("status") == "accepted", "status must be accepted")

    provider = value.get("provider")
    require(isinstance(provider, dict), "provider must be an object")
    if isinstance(provider, dict):
        require(provider.get("id") == "openai", "the sole provider must be openai")
        require(
            provider.get("codex_model_provider_id") == "openai",
            "Codex provider id must be openai",
        )

    surface = value.get("execution_surface")
    require(isinstance(surface, dict), "execution_surface must be an object")
    if isinstance(surface, dict):
        require(surface.get("id") == "codex-cli", "execution surface must be codex-cli")
        require(surface.get("command") == "codex", "execution command must be codex")
        require(
            "not-model-provider" in str(surface.get("classification", "")),
            "execution surface must be distinguished from the model provider",
        )

    defaults = value.get("shared_request_defaults")
    require(isinstance(defaults, dict), "shared_request_defaults must be an object")
    if isinstance(defaults, dict):
        require(
            defaults.get("reasoning_effort") == "medium",
            "comparison reasoning effort must be medium",
        )
        require(
            defaults.get("model_role_selection") == "explicit-per-run",
            "model role selection must remain explicit per run",
        )

    models = value.get("models")
    require(isinstance(models, dict), "models must be an object")
    if isinstance(models, dict):
        require(set(models) == set(EXPECTED_MODELS), "models must contain exactly strong and cheaper")
        for role, model_id in EXPECTED_MODELS.items():
            record = models.get(role)
            require(isinstance(record, dict), f"models.{role} must be an object")
            if not isinstance(record, dict):
                continue
            require(record.get("role") == role, f"models.{role}.role mismatch")
            require(record.get("model_id") == model_id, f"models.{role}.model_id mismatch")
            require(record.get("provider_id") == "openai", f"models.{role} provider mismatch")
            require(
                record.get("reference_kind") == "provider-alias",
                f"models.{role} must disclose alias status",
            )
            require(
                record.get("versioned_snapshot_id") is None,
                f"models.{role} must not claim an unavailable versioned snapshot",
            )

    templates = value.get("codex_exec_templates")
    require(isinstance(templates, dict), "codex_exec_templates must be an object")
    if isinstance(templates, dict):
        require(set(templates) == set(EXPECTED_MODELS), "templates must contain exactly two roles")
        for role, model_id in EXPECTED_MODELS.items():
            arguments = templates.get(role)
            require(isinstance(arguments, list), f"template {role} must be an argument list")
            if isinstance(arguments, list):
                require(arguments[:2] == ["codex", "exec"], f"template {role} must use codex exec")
                require(model_id in arguments, f"template {role} must select {model_id}")
                require(
                    'model_reasoning_effort="medium"' in arguments,
                    f"template {role} must freeze medium reasoning",
                )

    authorization = value.get("authorization")
    require(isinstance(authorization, dict), "authorization must be an object")
    if isinstance(authorization, dict):
        require(
            authorization.get("model_calls_authorized_by_this_file") is False,
            "shared baseline must not authorize model calls",
        )
        required = authorization.get("required_before_model_run")
        require(isinstance(required, list), "model-run prerequisites must be a list")
        if isinstance(required, list):
            require(
                "experiment-local-call-resource-ceiling" in required,
                "model runs must require an experiment-local call/resource ceiling",
            )
            require(
                all("spend-ceiling" not in str(item) for item in required),
                "baseline must not reinstate an API-dollar spend ceiling",
            )

    accounting = value.get("subscription_accounting")
    require(isinstance(accounting, dict), "subscription_accounting must be an object")
    if isinstance(accounting, dict):
        require(
            accounting.get("chatgpt_subscription_token_usage_is_provider_bill") is False,
            "subscription token observations must not be treated as provider bill",
        )
        require(
            accounting.get("api_price_table_is_actual_subscription_bill") is False,
            "API price tables must not be treated as the subscription bill",
        )
        require(
            accounting.get("unknown_provider_cost_value") == "Unknown",
            "unknown provider cost must remain Unknown",
        )
    return errors


def resolve_codex_command(explicit: str | None) -> str:
    if explicit:
        return explicit
    command_name = "codex.cmd" if os.name == "nt" else "codex"
    resolved = shutil.which(command_name)
    if resolved is None:
        raise OSError(f"cannot resolve {command_name} on PATH")
    return resolved


def validate_local_catalog(codex_command: str) -> tuple[list[str], str]:
    errors: list[str] = []
    version = subprocess.run(
        [codex_command, "--version"],
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
    ).stdout.strip()
    catalog_text = subprocess.run(
        [codex_command, "debug", "models", "--bundled"],
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
    ).stdout
    catalog = json.loads(catalog_text)
    records = {
        record.get("slug"): record
        for record in catalog.get("models", [])
        if isinstance(record, dict)
    }
    for role, model_id in EXPECTED_MODELS.items():
        record = records.get(model_id)
        if record is None:
            errors.append(f"local bundled catalog does not list {role} model {model_id}")
            continue
        efforts = {
            level.get("effort")
            for level in record.get("supported_reasoning_levels", [])
            if isinstance(level, dict)
        }
        if "medium" not in efforts:
            errors.append(f"local bundled catalog does not support medium effort for {model_id}")
    return errors, version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-local-catalog",
        action="store_true",
        help="also inspect the model catalog bundled with the installed Codex CLI",
    )
    parser.add_argument(
        "--codex-command",
        help="exact Codex executable or command shim to inspect (defaults to PATH resolution)",
    )
    args = parser.parse_args()

    try:
        errors = validate_baseline(load_baseline())
        version = None
        codex_command = None
        if args.check_local_catalog:
            codex_command = resolve_codex_command(args.codex_command)
            local_errors, version = validate_local_catalog(codex_command)
            errors.extend(local_errors)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"model baseline validation: FAIL ({exc})")
        return 1

    if errors:
        print(f"model baseline validation: FAIL ({len(errors)} error(s))")
        for error in errors:
            print(f"- {error}")
        return 1
    catalog_note = (
        f", bundled catalog checked with {version} at {codex_command}"
        if version and codex_command
        else ""
    )
    print(f"model baseline validation: PASS (1 provider, 1 strong, 1 cheaper{catalog_note})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
