#!/usr/bin/env python3
"""Read-only audit for the Decision-0009 Trial 001 layout transition."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile


RUN_ID = "run-001"
EXPECTED = {
    "trial_zip_digest": "sha256:a179ee8b80b5b7886b756561f74be80d425312faf2d1ecea0b5d81262cef6b44",
    "trial_manifest_digest": "sha256:1eede07b480301cebe66b56af76846178dda5ff4b5630b75d4304364bb04dfb0",
    "notebook_digest": "sha256:e12a187dd59ef0978930b2c78cded09f8187e39e08b079bab0a9f1f3547bb40a",
    "runner_digest": "sha256:ffde7dda2dd9b035ffa654b9e0914c7d2ce5f004d55467d86c2a44a7c43502a2",
    "repository_revision": "3191c3e9d126570567d09651b80d0dd778e2c6f3",
}


def _digest_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _digest_path(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"


def _manifest(path: Path) -> tuple[dict, str]:
    with zipfile.ZipFile(path, "r") as archive:
        raw = archive.read("manifest.json")
    return json.loads(raw.decode("utf-8")), _digest_bytes(raw)


def audit_layout(repository_root: Path, trial_root: Path) -> dict:
    """Return a deterministic report without changing any local bytes."""

    repository_root = repository_root.resolve()
    trial_root = trial_root.resolve()
    outbound = trial_root / "kaggle/outbound/run-001/trial-input.zip"
    notebook = repository_root / "trials/first-real-domain/kaggle-notebook.ipynb"
    result = trial_root / "kaggle/inbound/quarantine/run-001/result-package.zip"
    imported = trial_root / "runs/run-001/import-evidence.json"
    evaluation = trial_root / "runs/run-001/local-evaluation"

    identity_issues: list[str] = []
    observed: dict[str, object] = {}
    if not outbound.is_file():
        identity_issues.append("canonical outbound package is missing")
    else:
        observed["trial_zip_digest"] = _digest_path(outbound)
        try:
            manifest, manifest_digest = _manifest(outbound)
        except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
            identity_issues.append(f"canonical outbound manifest is unreadable: {exc}")
        else:
            observed["trial_manifest_digest"] = manifest_digest
            observed["package_id"] = manifest.get("package_id")
            metadata = manifest.get("metadata", {})
            repository = metadata.get("repository", {}) if isinstance(metadata, dict) else {}
            observed["repository_revision"] = repository.get("revision")
            observed["notebook_digest"] = metadata.get("notebook_digest") if isinstance(metadata, dict) else None
            observed["runner_digest"] = metadata.get("runner_digest") if isinstance(metadata, dict) else None
    if not notebook.is_file():
        identity_issues.append("tracked canonical notebook is missing")
    else:
        observed["tracked_notebook_digest"] = _digest_path(notebook)

    comparisons = {
        "trial_zip_digest": observed.get("trial_zip_digest"),
        "trial_manifest_digest": observed.get("trial_manifest_digest"),
        "repository_revision": observed.get("repository_revision"),
        "notebook_digest": observed.get("notebook_digest"),
        "runner_digest": observed.get("runner_digest"),
    }
    for field, value in comparisons.items():
        if value != EXPECTED[field]:
            identity_issues.append(f"{field} does not match Decision 0009")
    if observed.get("tracked_notebook_digest") != EXPECTED["notebook_digest"]:
        identity_issues.append("tracked notebook bytes do not match Decision 0009")
    if observed.get("package_id") != RUN_ID:
        identity_issues.append("canonical outbound package_id is not run-001")

    alias_candidates = (
        trial_root / "kaggle/outbound/run-001-v3/trial-input.zip",
        trial_root / "trial-input/trial-input-v3.zip",
    )
    exact_aliases = []
    for path in alias_candidates:
        if path.is_file():
            digest = _digest_path(path)
            exact_aliases.append(
                {
                    "path": path.relative_to(trial_root).as_posix(),
                    "digest": digest,
                    "matches_canonical": digest == EXPECTED["trial_zip_digest"],
                }
            )

    superseded = []
    for suffix in ("v1", "v2"):
        path = trial_root / f"kaggle/outbound/run-001-{suffix}/trial-input.zip"
        if not path.is_file():
            continue
        entry: dict[str, object] = {
            "path": path.relative_to(trial_root).as_posix(),
            "digest": _digest_path(path),
        }
        try:
            manifest, manifest_digest = _manifest(path)
        except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
            entry["error"] = str(exc)
        else:
            entry["package_id"] = manifest.get("package_id")
            entry["manifest_digest"] = manifest_digest
        superseded.append(entry)

    expected_evaluation = {
        "baseline-result.json",
        "candidate-result.json",
        "selection.json",
        "p2-acceptance.json",
    }
    observed_evaluation = (
        {path.name for path in evaluation.iterdir() if path.is_file()}
        if evaluation.is_dir()
        else set()
    )
    closure = {
        "result_present": result.is_file(),
        "import_evidence_present": imported.is_file(),
        "local_evaluation_complete": expected_evaluation <= observed_evaluation,
    }
    blockers = list(identity_issues)
    if not closure["result_present"]:
        blockers.append("returned result-package.zip is not present in quarantine")
    if not closure["import_evidence_present"]:
        blockers.append("run-001 has not been imported into runs/run-001")
    if not closure["local_evaluation_complete"]:
        blockers.append("run-001 local evaluation evidence is incomplete")

    normalization_ready = not blockers
    status = "ready-to-normalize" if normalization_ready else (
        "identity-invalid" if identity_issues else "frozen-awaiting-result-closure"
    )
    return {
        "format": "irisx/trial-001-layout-audit",
        "format_version": "1.0",
        "run_id": RUN_ID,
        "status": status,
        "normalization_ready": normalization_ready,
        "canonical_paths": {
            "outbound": outbound.relative_to(repository_root).as_posix(),
            "result": result.relative_to(repository_root).as_posix(),
            "normalized_run": (trial_root / "runs/run-001").relative_to(repository_root).as_posix(),
        },
        "expected_identity": EXPECTED,
        "observed_identity": observed,
        "result_closure": closure,
        "exact_aliases": exact_aliases,
        "superseded_packages": superseded,
        "blockers": blockers,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--trial-root",
        type=Path,
        default=Path(".irisx/arc-agi-2/trial-001"),
    )
    parser.add_argument(
        "--require-normalization-ready",
        action="store_true",
        help="exit non-zero until the Decision-0009 result closure gate passes",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository_root = args.repository_root.resolve()
    trial_root = args.trial_root
    if not trial_root.is_absolute():
        trial_root = repository_root / trial_root
    report = audit_layout(repository_root, trial_root)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    if report["status"] == "identity-invalid":
        return 1
    if args.require_normalization_ready and not report["normalization_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
