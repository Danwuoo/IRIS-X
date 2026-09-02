#!/usr/bin/env python3
"""Execute frozen H-P1a DEV optimization and one-shot validation."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from common import (
    EXPERIMENT,
    FROZEN_INPUTS_PATH,
    OPTIMIZER_SCHEMA_PATH,
    SEED_PROGRAM_PATH,
    append_jsonl,
    candidate_bundle,
    canonical_bytes,
    codex_environment,
    evaluate_invocation,
    instance_paths,
    invoke_codex,
    load_json,
    load_jsonl,
    provider_output_schema_path,
    require_schema_admission,
    selection_key,
    sha_bytes,
    sha_file,
    summarize_records,
    utc_now,
    validate_program,
    validate_terminal_semantics,
    write_bytes_new,
    write_json_new,
)


OPTIMIZER_PROGRAM_PATH = EXPERIMENT / "definition" / "optimizer-program.txt"


def require_chatgpt_auth() -> str:
    identity = load_json(EXPERIMENT / "definition" / "execution-identity.json")
    completed = subprocess.run(
        [identity["codex_cli_resolved_path"], "login", "status"],
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=codex_environment(),
    )
    status = completed.stdout.strip()
    if "Logged in using ChatGPT" not in status:
        raise RuntimeError(f"required ChatGPT authentication is not active: {status}")
    return status


def load_instances(split: str) -> list[dict[str, Any]]:
    root = FROZEN_INPUTS_PATH / split
    return [load_json(path) for path in instance_paths(root)]


def freeze_outputs(batch_id: str, invocation_rows: list[dict[str, Any]], destination: Path) -> None:
    write_json_new(
        destination,
        {
            "schema_version": 1,
            "batch_id": batch_id,
            "frozen_at_utc": utc_now(),
            "invocation_count": len(invocation_rows),
            "records": [
                {
                    "invocation_id": row["invocation_id"],
                    "raw_event_stream_sha256": row["raw_event_stream_sha256"],
                    "output_sha256": row["output_sha256"],
                    "terminal_execution_status": row["terminal_execution_status"],
                }
                for row in invocation_rows
            ],
        },
    )


def evaluate_candidate_batch(
    *,
    run_root: Path,
    stage: str,
    candidate_id: str,
    program_bytes: bytes,
    instances: list[dict[str, Any]],
    definition_commit: str,
    code_commit: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    invocations: list[dict[str, Any]] = []
    artifact_dirs: list[Path] = []
    for index, instance in enumerate(instances, start=1):
        invocation_id = f"{stage}-{candidate_id}-{index:03d}-{instance['manifest']['instance_id']}"
        artifact_dir = run_root / "raw" / stage / candidate_id / f"{index:03d}-{instance['manifest']['instance_id']}"
        row = invoke_codex(
            invocation_id=invocation_id,
            model_id="gpt-5.6-luna",
            model_role="cheaper",
            program_bytes=program_bytes,
            payload=candidate_bundle(instance),
            output_schema_path=provider_output_schema_path(instance["manifest"]["family_id"]),
            definition_commit=definition_commit,
            code_commit=code_commit,
            artifact_dir=artifact_dir,
            call_kind=f"{stage}-candidate-evaluation",
        )
        row["candidate_id"] = candidate_id
        invocations.append(row)
        artifact_dirs.append(artifact_dir)
    freeze_outputs(
        f"{stage}-{candidate_id}",
        invocations,
        run_root / "output-freezes" / f"{stage}-{candidate_id}.json",
    )
    records: list[dict[str, Any]] = []
    for instance, invocation, artifact_dir in zip(instances, invocations, artifact_dirs, strict=True):
        evaluated = evaluate_invocation(instance, invocation, artifact_dir)
        evaluated["candidate_id"] = candidate_id
        evaluated["candidate_sha256"] = sha_bytes(program_bytes)
        records.append(evaluated)
        append_jsonl(run_root / f"{stage}-terminal-records.jsonl", evaluated)
    summary = summarize_records(records)
    summary.update(
        {
            "candidate_id": candidate_id,
            "candidate_sha256": sha_bytes(program_bytes),
            "candidate_bytes": len(program_bytes),
        }
    )
    write_json_new(run_root / "summaries" / f"{stage}-{candidate_id}.json", summary)
    return records, summary


def optimizer_payload(
    replicate_id: str,
    round_number: int,
    current_candidate_id: str,
    current_program: bytes,
    dev_instances: list[dict[str, Any]],
    dev_records: list[dict[str, Any]],
) -> dict[str, Any]:
    feedback = []
    for instance, record in zip(dev_instances, dev_records, strict=True):
        feedback.append(
            {
                "instance_id": instance["manifest"]["instance_id"],
                "family_id": instance["manifest"]["family_id"],
                "public_task_bundle": candidate_bundle(instance),
                "candidate_output": record["candidate_answer"],
                "actual_outcome": record["actual_outcome"],
                "empirical_evidence_status": record["empirical_evidence_status"],
                "acceptance_decision": record["acceptance_decision"],
                "verified_success_eligibility": record["verified_success_eligibility"],
                "malformed_output": record["malformed_output"],
                "development_feedback": record["development_feedback"],
            }
        )
    return {
        "schema_version": 1,
        "optimizer_replicate_id": replicate_id,
        "revision_round": round_number,
        "current_candidate_id": current_candidate_id,
        "current_candidate_program": current_program.decode("utf-8"),
        "allowed_dev_information": feedback,
        "mutation_boundary": "program-prompt-layer-only",
        "candidate_size_ceiling_bytes": 12288,
        "validation_information_included": False,
        "blind_information_included": False,
        "other_replicate_information_included": False,
    }


def evaluate_optimizer_output(
    invocation: dict[str, Any], artifact_dir: Path, candidate_id: str
) -> tuple[dict[str, Any], bytes | None]:
    output_path = artifact_dir / "output.json"
    candidate_bytes: bytes | None = None
    findings: list[str] = []
    schema_valid = False
    if invocation["terminal_execution_status"] == "completed" and output_path.exists():
        try:
            parsed = json.loads(output_path.read_text(encoding="utf-8"))
            errors = list(Draft202012Validator(load_json(OPTIMIZER_SCHEMA_PATH)).iter_errors(parsed))
            schema_valid = not errors
            if errors:
                findings.extend(error.message for error in errors)
            else:
                candidate_bytes = parsed["candidate_program"].encode("utf-8")
                findings.extend(validate_program(candidate_bytes))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            findings.append(f"malformed-optimizer-output:{type(exc).__name__}")
    else:
        findings.append("optimizer-terminal-noncompletion")
    valid = candidate_bytes is not None and not findings
    if not valid:
        candidate_bytes = None
    terminal_status = invocation["terminal_execution_status"]
    if not valid and terminal_status != "invalid":
        terminal_status = "failed"
    record = {
        **invocation,
        "candidate_id": candidate_id,
        "optimizer_output_schema_valid": schema_valid,
        "candidate_program_valid": valid,
        "candidate_program_sha256": sha_bytes(candidate_bytes) if candidate_bytes is not None else None,
        "candidate_program_bytes": len(candidate_bytes) if candidate_bytes is not None else 0,
        "static_findings": findings,
        "actual_outcome": "success" if valid else "failure",
        "empirical_evidence_status": "sufficient",
        "acceptance_decision": "accept" if valid else ("not_applicable" if not invocation["output_present"] else "reject"),
        "verified_success_eligibility": valid,
        "joint_interpretation": "verified_success" if valid else "correctly_recognized_failure",
        "terminal_execution_status": terminal_status,
    }
    validate_terminal_semantics(record)
    return record, candidate_bytes


def display_selection_tuple(summary: dict[str, Any], program_bytes: bytes, candidate_sha: str) -> list[Any]:
    return [
        -summary["verified_success_count"],
        -summary["actual_success_count"],
        summary["false_success_count"],
        summary["malformed_output_count"],
        summary["invalid_terminal_count"],
        summary["model_calls"],
        summary["input_tokens"] if isinstance(summary["input_tokens"], int) else "infinity",
        summary["output_tokens"] if isinstance(summary["output_tokens"], int) else "infinity",
        summary["reasoning_tokens"] if isinstance(summary["reasoning_tokens"], int) else "infinity",
        summary["total_wall_time_ns"],
        {"candidate_bytes_utf8": program_bytes.decode("utf-8"), "candidate_bytes_hex": program_bytes.hex()},
        candidate_sha,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--definition-commit", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--schema-admission-record", type=Path, required=True)
    args = parser.parse_args()
    schema_admission_record = args.schema_admission_record.resolve()
    admission = require_schema_admission(
        schema_admission_record, args.run_id, args.definition_commit, args.code_commit
    )
    authorization_path = (
        EXPERIMENT / "definition" / "run-authorizations" / f"{args.run_id}.json"
    )
    authorization = load_json(authorization_path)
    ceiling = authorization["independent_resource_ceiling"]
    run_root = EXPERIMENT / "design" / args.run_id
    if run_root.exists():
        raise FileExistsError(f"design run already exists: {run_root}")
    run_root.mkdir(parents=True)
    auth_status = require_chatgpt_auth()
    seed = SEED_PROGRAM_PATH.read_bytes()
    seed_findings = validate_program(seed)
    if seed_findings:
        raise ValueError(f"invalid seed program: {seed_findings}")
    dev_instances = load_instances("dev")
    validation_instances = load_instances("validation")
    if len(dev_instances) != 24 or len(validation_instances) != 16:
        raise ValueError("frozen split size mismatch")
    write_json_new(
        run_root / "run-manifest.json",
        {
            "schema_version": 1,
            "run_id": args.run_id,
            "created_at_utc": utc_now(),
            "definition_commit": args.definition_commit,
            "code_commit": args.code_commit,
            "authentication_mode": "chatgpt",
            "authentication_status_observed": auth_status,
            "billing_mode": "chatgpt-subscription",
            "api_key_fallback": "prohibited",
            "provider_cost_usd": "Unknown",
            "schema_admission_record": schema_admission_record.relative_to(EXPERIMENT).as_posix(),
            "schema_admission_record_sha256": sha_file(schema_admission_record),
            "schema_preflight_status": admission["status"],
            "resource_authorization": authorization_path.relative_to(EXPERIMENT).as_posix(),
            "resource_authorization_sha256": sha_file(authorization_path),
            "independent_resource_ceiling": ceiling,
            "seed_program_sha256": sha_bytes(seed),
            "seed_program_bytes": len(seed),
            "dev_inventory_sha256": sha_bytes((FROZEN_INPUTS_PATH / "dev" / "inventory.json").read_bytes()),
            "validation_inventory_sha256": sha_bytes((FROZEN_INPUTS_PATH / "validation" / "inventory.json").read_bytes()),
        },
    )
    candidate_programs: dict[str, bytes] = {"seed": seed}
    candidate_provenance: dict[str, dict[str, Any]] = {
        "seed": {"candidate_id": "seed", "source": "frozen-seed", "optimizer_generated": False}
    }
    seed_dev_records, seed_dev_summary = evaluate_candidate_batch(
        run_root=run_root,
        stage="dev",
        candidate_id="seed",
        program_bytes=seed,
        instances=dev_instances,
        definition_commit=args.definition_commit,
        code_commit=args.code_commit,
    )
    optimizer_calls = 0
    for replicate_id in ("opt-01", "opt-02"):
        current_id = "seed"
        current_program = seed
        current_records = seed_dev_records
        for round_number in range(1, 4):
            candidate_id = f"{replicate_id}-r{round_number:02d}"
            payload = optimizer_payload(
                replicate_id,
                round_number,
                current_id,
                current_program,
                dev_instances,
                current_records,
            )
            artifact_dir = run_root / "raw" / "optimizer" / candidate_id
            invocation = invoke_codex(
                invocation_id=f"optimizer-{candidate_id}",
                model_id="gpt-5.6-terra",
                model_role="strong-design-time",
                program_bytes=OPTIMIZER_PROGRAM_PATH.read_bytes(),
                payload=payload,
                output_schema_path=OPTIMIZER_SCHEMA_PATH,
                definition_commit=args.definition_commit,
                code_commit=args.code_commit,
                artifact_dir=artifact_dir,
                call_kind="terra-design-time-optimizer",
            )
            optimizer_calls += 1
            optimizer_record, candidate_bytes = evaluate_optimizer_output(invocation, artifact_dir, candidate_id)
            optimizer_record["optimizer_replicate_id"] = replicate_id
            optimizer_record["revision_round"] = round_number
            append_jsonl(run_root / "optimizer-terminal-records.jsonl", optimizer_record)
            if candidate_bytes is None:
                break
            write_bytes_new(run_root / "candidates" / f"{candidate_id}.txt", candidate_bytes)
            candidate_programs[candidate_id] = candidate_bytes
            candidate_provenance[candidate_id] = {
                "candidate_id": candidate_id,
                "source": "terra-optimizer",
                "optimizer_generated": True,
                "replicate_id": replicate_id,
                "revision_round": round_number,
                "candidate_sha256": sha_bytes(candidate_bytes),
                "candidate_bytes": len(candidate_bytes),
                "optimizer_invocation_id": optimizer_record["invocation_id"],
            }
            current_records, _ = evaluate_candidate_batch(
                run_root=run_root,
                stage="dev",
                candidate_id=candidate_id,
                program_bytes=candidate_bytes,
                instances=dev_instances,
                definition_commit=args.definition_commit,
                code_commit=args.code_commit,
            )
            current_id = candidate_id
            current_program = candidate_bytes
    by_sha: dict[str, list[str]] = {}
    for candidate_id, program in candidate_programs.items():
        if candidate_id == "seed":
            continue
        by_sha.setdefault(sha_bytes(program), []).append(candidate_id)
    canonical_candidates: dict[str, bytes] = {}
    duplicate_provenance: dict[str, list[str]] = {}
    for candidate_sha, ids in sorted(by_sha.items()):
        canonical_id = min(ids)
        canonical_candidates[canonical_id] = candidate_programs[canonical_id]
        duplicate_provenance[candidate_sha] = sorted(ids)
    if not canonical_candidates:
        write_json_new(
            run_root / "blocker.json",
            {"blocker": "zero-eligible-optimizer-generated-candidates", "optimizer_calls": optimizer_calls},
        )
        print("BLOCKED: zero eligible optimizer-generated candidates")
        return 2
    validation_pool = {"seed": seed, **canonical_candidates}
    validation_invocations: dict[str, list[tuple[dict[str, Any], dict[str, Any], Path]]] = {}
    all_validation_rows: list[dict[str, Any]] = []
    for candidate_id, program in validation_pool.items():
        rows: list[tuple[dict[str, Any], dict[str, Any], Path]] = []
        for index, instance in enumerate(validation_instances, start=1):
            artifact_dir = run_root / "raw" / "validation" / candidate_id / f"{index:03d}-{instance['manifest']['instance_id']}"
            invocation = invoke_codex(
                invocation_id=f"validation-{candidate_id}-{index:03d}-{instance['manifest']['instance_id']}",
                model_id="gpt-5.6-luna",
                model_role="cheaper",
                program_bytes=program,
                payload=candidate_bundle(instance),
                output_schema_path=provider_output_schema_path(instance["manifest"]["family_id"]),
                definition_commit=args.definition_commit,
                code_commit=args.code_commit,
                artifact_dir=artifact_dir,
                call_kind="validation-candidate-evaluation",
            )
            invocation["candidate_id"] = candidate_id
            rows.append((instance, invocation, artifact_dir))
            all_validation_rows.append(invocation)
        validation_invocations[candidate_id] = rows
    freeze_outputs("validation-complete-pool", all_validation_rows, run_root / "validation-output-freeze.json")
    validation_summaries: dict[str, dict[str, Any]] = {}
    for candidate_id, rows in validation_invocations.items():
        records = []
        program = validation_pool[candidate_id]
        for instance, invocation, artifact_dir in rows:
            evaluated = evaluate_invocation(instance, invocation, artifact_dir)
            evaluated["candidate_id"] = candidate_id
            evaluated["candidate_sha256"] = sha_bytes(program)
            records.append(evaluated)
            append_jsonl(run_root / "validation-terminal-records.jsonl", evaluated)
        summary = summarize_records(records)
        summary.update(
            {
                "candidate_id": candidate_id,
                "candidate_sha256": sha_bytes(program),
                "candidate_bytes": len(program),
            }
        )
        validation_summaries[candidate_id] = summary
        write_json_new(run_root / "summaries" / f"validation-{candidate_id}.json", summary)
    eligible = []
    selection_records = []
    for candidate_id, program in canonical_candidates.items():
        summary = validation_summaries[candidate_id]
        candidate_sha = sha_bytes(program)
        key = selection_key(summary, program, candidate_sha)
        eligible.append((key, candidate_id, program, candidate_sha, summary))
        selection_records.append(
            {
                "candidate_id": candidate_id,
                "candidate_sha256": candidate_sha,
                "selection_tuple": display_selection_tuple(summary, program, candidate_sha),
                "optimizer_provenance_ids": duplicate_provenance[candidate_sha],
            }
        )
    eligible.sort(key=lambda row: row[0])
    _, selected_id, selected_program, selected_sha, selected_summary = eligible[0]
    write_bytes_new(run_root / "c1-freeze" / "c1-program.txt", selected_program)
    write_json_new(
        run_root / "c1-freeze" / "c1-freeze.json",
        {
            "schema_version": 1,
            "selected_candidate_id": selected_id,
            "candidate_sha256": selected_sha,
            "candidate_bytes": len(selected_program),
            "optimizer_generated": True,
            "definition_commit": args.definition_commit,
            "code_commit": args.code_commit,
            "selected_at_utc": utc_now(),
            "validation_summary": selected_summary,
            "selection_tuple": display_selection_tuple(selected_summary, selected_program, selected_sha),
            "program_file_sha256": sha_bytes(selected_program),
            "candidate_modification_after_freeze": "prohibited",
        },
    )
    write_json_new(
        run_root / "selection-reconstruction.json",
        {
            "schema_version": 1,
            "selection_rule": "definition/selection-rule.json",
            "validation_opened_after_all_outputs_frozen": True,
            "seed_ineligible_for_c1": True,
            "deduplication": duplicate_provenance,
            "eligible_records": selection_records,
            "selected_candidate_id": selected_id,
            "selected_candidate_sha256": selected_sha,
        },
    )
    dev_records = load_jsonl(run_root / "dev-terminal-records.jsonl")
    validation_records = load_jsonl(run_root / "validation-terminal-records.jsonl")
    optimizer_records = load_jsonl(run_root / "optimizer-terminal-records.jsonl")
    luna_calls = sum(row["model_calls"] for row in dev_records + validation_records)
    terra_calls = sum(row["model_calls"] for row in optimizer_records)
    design_luna_ceiling = (
        ceiling["allocation"]["seed_dev_luna"]
        + ceiling["allocation"]["candidate_dev_luna"]
        + ceiling["allocation"]["validation_luna"]
    )
    if (
        luna_calls > design_luna_ceiling
        or terra_calls > ceiling["maximum_terra_optimizer_calls"]
        or luna_calls + terra_calls > design_luna_ceiling + ceiling["maximum_terra_optimizer_calls"]
    ):
        raise RuntimeError("design-time call ceiling exceeded")
    write_json_new(
        run_root / "design-ledger.json",
        {
            "schema_version": 1,
            "status": "closed",
            "closed_at_utc": utc_now(),
            "definition_commit": args.definition_commit,
            "code_commit": args.code_commit,
            "provider_id": "openai",
            "execution_surface": "codex-cli",
            "authentication_mode": "chatgpt",
            "billing_mode": "chatgpt-subscription",
            "api_key_fallback": "prohibited",
            "provider_cost_usd": "Unknown",
            "price_basis": "no-run-attributable-chatgpt-subscription-price-basis-available",
            "luna_calls": luna_calls,
            "terra_optimizer_calls": terra_calls,
            "total_model_calls": luna_calls + terra_calls,
            "seed_dev_calls": seed_dev_summary["model_calls"],
            "optimizer_generated_candidate_count": len(candidate_programs) - 1,
            "unique_optimizer_candidate_count": len(canonical_candidates),
            "optimizer_failed_round_count": sum(not row["candidate_program_valid"] for row in optimizer_records),
            "validation_candidate_count": len(validation_pool),
            "validation_calls": sum(row["model_calls"] for row in validation_records),
            "candidate_evaluations": len(dev_records) + len(validation_records),
            "human_intervention": 0,
            "retry_count": 0,
            "recovery_count": 0,
            "routing": "none",
            "escalation": "none",
            "selected_c1_id": selected_id,
            "selected_c1_sha256": selected_sha,
            "selected_c1_bytes": len(selected_program),
            "design_time_not_amortized": True,
        },
    )
    print(
        f"design complete: optimizer_calls={terra_calls}; luna_calls={luna_calls}; "
        f"C1={selected_id} {selected_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
