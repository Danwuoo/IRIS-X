#!/usr/bin/env python3
"""Admit one H-P1a run only after all frozen provider schemas pass locally."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from common import (
    DEFINITION,
    EXPERIMENT,
    ROOT,
    frozen_provider_schema_paths,
    load_json,
    provider_schema_findings,
    require_commit,
    sha_bytes,
    sha_file,
    utc_now,
    write_json_new,
)


def committed_bytes(commit: str, path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def committed_tree(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "rev-parse", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def validate_artifact_identities() -> dict[str, dict[str, object]]:
    manifest = load_json(DEFINITION / "artifact-identities.json")
    observed: dict[str, dict[str, object]] = {}
    for artifact_id, record in manifest["artifacts"].items():
        path = Path(record["path"])
        if not path.is_absolute():
            path = ROOT / path if path.parts[0] in {"experiments", "research", "docs", "tools"} else EXPERIMENT / path
        actual = {"path": path.relative_to(ROOT).as_posix(), "sha256": sha_file(path), "bytes": path.stat().st_size}
        if actual["sha256"] != record["sha256"] or actual["bytes"] != record["bytes"]:
            raise ValueError(f"frozen artifact identity drift: {artifact_id}")
        observed[artifact_id] = actual
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--definition-commit", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require_commit(args.definition_commit, "definition_commit")
    require_commit(args.code_commit, "code_commit")
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    authorization_path = DEFINITION / "run-authorizations" / f"{args.run_id}.json"
    authorization = load_json(authorization_path)
    if authorization["run_id"] != args.run_id:
        raise ValueError("run authorization identity mismatch")
    if (EXPERIMENT / "design" / args.run_id).exists():
        raise FileExistsError("formal design run identity already exists")
    prior = authorization["prior_attempt"]
    prior_path = EXPERIMENT / "design" / prior["run_id"]
    if committed_tree(prior_path) != prior["immutable_tree_sha"]:
        raise ValueError("prior attempt immutable tree drift")
    schema_rows: dict[str, dict[str, object]] = {}
    all_findings: list[str] = []
    for schema_id, path in sorted(frozen_provider_schema_paths().items()):
        if path.read_bytes() != committed_bytes(args.definition_commit, path):
            raise ValueError(f"schema bytes are not bound to definition commit: {schema_id}")
        findings = provider_schema_findings(load_json(path))
        schema_rows[schema_id] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha_file(path),
            "bytes": path.stat().st_size,
            "findings": findings,
        }
        all_findings.extend(f"{schema_id}:{finding}" for finding in findings)
    artifacts = validate_artifact_identities()
    if all_findings:
        raise ValueError("provider schema preflight failed: " + "; ".join(all_findings))
    write_json_new(
        args.output,
        {
            "schema_version": 1,
            "preflight_id": f"provider-schema-preflight-{args.run_id}",
            "run_id": args.run_id,
            "status": "pass",
            "admitted": True,
            "observed_at_utc": utc_now(),
            "definition_commit": args.definition_commit,
            "code_commit": args.code_commit,
            "provider_id": "openai",
            "execution_surface": "codex-cli",
            "policy_path": "experiments/exp-2026-09-01-luna-structured-program-specialization/definition/provider-structured-output-policy.json",
            "policy_sha256": sha_file(DEFINITION / "provider-structured-output-policy.json"),
            "official_source": "https://developers.openai.com/api/docs/guides/structured-outputs",
            "schemas": schema_rows,
            "artifact_identity_count": len(artifacts),
            "artifact_identities_sha256": sha_bytes((DEFINITION / "artifact-identities.json").read_bytes()),
            "authorization_path": authorization_path.relative_to(ROOT).as_posix(),
            "authorization_sha256": sha_file(authorization_path),
            "prior_attempt_immutable_tree_sha": prior["immutable_tree_sha"],
            "model_calls": 0,
            "network_calls": 0,
            "api_calls": 0,
            "provider_temporal_drift_eliminated": False,
            "provider_temporal_drift_limitation": "static preflight cannot make provider aliases or server validation immutable",
        },
    )
    print(f"provider schema preflight: PASS ({len(schema_rows)} frozen schemas; zero model/network/API calls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
