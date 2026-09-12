#!/usr/bin/env python3
"""Validate IRIS-X pre-synthesis readiness structure and references.

This validator deliberately checks machine-readable shape, repository paths,
registry coverage, baseline identity, and protected-tree preservation. It does
not assess scientific truth, evidence quality, or the merits of a formulation.
The readiness ``.yaml`` files use the repository's JSON-compatible YAML style,
so the standard library is sufficient.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "research" / "pre-synthesis-readiness"

REQUIRED_PACKAGE_FILES = {
    "README.md",
    "baseline-manifest.json",
    "source-interface.yaml",
    "phase-evidence-ledger.yaml",
    "construct-map.yaml",
    "assumption-tension-matrix.md",
    "claim-evidence-index.jsonl",
    "candidate-formulation-template.md",
    "ultra-session-contract.md",
    "ultra-session-prompt.md",
    "readiness-report.md",
}

SOURCE_EVIDENCE_CLASSES = {
    "source_stated",
    "directly_observed",
    "readiness_inference",
    "unknown",
}
LEDGER_EVIDENCE_CLASSES = SOURCE_EVIDENCE_CLASSES | {
    "inferred",
    "governance_decision",
}
UNCERTAINTY_LABELS = {
    "Unknown",
    "Unclear",
    "Not established",
    "Not evaluated",
    "Conflicting evidence",
}
CLAIM_STATUSES = {
    "supported_bounded",
    "inferred",
    "contested",
    "unknown",
    "not_evaluated",
    "governance_decision",
}
PROHIBITED_STRUCTURED_KEYS = {
    "winner",
    "winner_score",
    "winning_formulation",
    "final_thesis",
    "final_research_thesis",
    "final_research_problem",
    "final_rqs",
    "final_hypotheses",
    "selected_architecture",
    "selected_framework",
}

REQUIRED_CONSTRUCT_LABELS = {
    "capability",
    "sufficient capability",
    "task success",
    "reliability",
    "evidence",
    "verification",
    "provenance",
    "authority",
    "failure",
    "attribution",
    "state",
    "recovery",
    "specialization",
    "routing and allocation",
    "workflow",
    "optimization",
    "cost",
    "lifecycle cost",
    "intervention point",
}

REQUIRED_LEDGER_IDS = {
    "phase3.corrected-pilot",
    "phase4.hm1a-snapshot-assertion",
    "phase4.hv1a-independent-verification",
    "phase4.hv1b-evidence-binding",
    "phase4.hi1a-preexecution-interception",
    "phase4.ho1a-instrumentation",
    "phase4.hrcv1a-targeted-recovery",
    "phase4.hp1a-specialization",
    "phase5.provisional-operationalization",
    "phase5.qualification-lineage",
    "phase5.multitask-family",
    "phase5.closure-zero-triggers",
    "phase6.batch1-instrument",
    "phase6.batch2-result-c",
    "phase6.batch3-direct-observation",
    "phase6.batch3-result-d",
    "phase6.post-batch3-repair",
    "phase6.intervention-predicates-unknown",
    "phase6.formal-closure",
}

REQUIRED_TENSION_TERMS = {
    "Unit of analysis",
    "One-shot versus repeated/lifecycle horizon",
    "Deterministic oracle versus learned/model/human judgment",
    "Model capability versus system/configuration capability",
    "Design-time optimization versus runtime adaptation/escalation",
    "Task-specific specialization versus general capability",
    "Inference cost versus lifecycle cost",
    "Stateful versus stateless execution",
    "Successful execution versus justified belief in success",
    "Reward/benchmark performance versus reliability",
    "Prevention versus detection/recovery",
    "Local immutable evidence versus remote/mutable provenance",
}
ALLOWED_TENSION_CLASSES = {
    "true contradiction",
    "scope difference",
    "terminology collision",
    "Unclear",
}


class Check:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


def load_json(path: Path, check: Check) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        check.errors.append(f"cannot parse JSON-compatible data {path.relative_to(ROOT)}: {exc}")
        return {}


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def repo_path_exists(value: str) -> bool:
    if not value or value.startswith(("http://", "https://")):
        return False
    candidate = (ROOT / Path(value)).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return False
    return candidate.exists()


def check_paths(paths: Iterable[Any], context: str, check: Check) -> None:
    for value in paths:
        check.require(isinstance(value, str), f"{context}: repository path must be a string")
        if isinstance(value, str):
            check.require(repo_path_exists(value), f"{context}: missing repository path {value!r}")


def duplicate_values(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def scan_prohibited_keys(value: Any, location: str, check: Check) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in PROHIBITED_STRUCTURED_KEYS:
                check.errors.append(f"{location}: prohibited interpretation-selecting key {key!r}")
            scan_prohibited_keys(child, f"{location}.{key}", check)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_prohibited_keys(child, f"{location}[{index}]", check)


def validate_baseline(data: Any, sources: Any, artifacts: Any, check: Check) -> None:
    check.require(isinstance(data, dict), "baseline manifest must be an object")
    if not isinstance(data, dict):
        return
    commit = data.get("execution_start_commit")
    check.require(isinstance(commit, str) and bool(re.fullmatch(r"[0-9a-f]{40}", commit or "")), "baseline execution_start_commit must be a full SHA")
    check.require(data.get("execution_start_clean") is True, "baseline must record a clean execution start")
    check.require(data.get("model_provider_calls_authorized") == 0, "baseline must record zero authorized model/provider calls")
    check.require(data.get("model_provider_calls_performed") == 0, "baseline must record zero performed model/provider calls")
    check.require(data.get("foundational_synthesis_started") is False, "baseline must state that foundational synthesis did not start")
    check.require(data.get("foundational_synthesis_authorized") is False, "baseline must state that foundational synthesis is unauthorized")

    source_records = sources.get("records", []) if isinstance(sources, dict) else []
    artifact_records = artifacts.get("records", []) if isinstance(artifacts, dict) else []
    counts = data.get("registered_counts", {})
    check.require(counts.get("sources") == len(source_records), "baseline source count differs from corpus/sources.yaml")
    check.require(counts.get("artifacts") == len(artifact_records), "baseline artifact count differs from corpus/artifacts.yaml")

    for item in data.get("critical_files", []):
        if not isinstance(item, dict):
            check.errors.append("baseline critical_files entries must be objects")
            continue
        rel = item.get("path")
        if not isinstance(rel, str) or not repo_path_exists(rel):
            check.errors.append(f"baseline critical file path is missing: {rel!r}")
            continue
        path = ROOT / rel
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        check.require(digest == item.get("sha256"), f"baseline SHA-256 drift for {rel}")
        blob = run_git("hash-object", "--", rel)
        check.require(blob.returncode == 0, f"git hash-object failed for {rel}: {blob.stderr.strip()}")
        if blob.returncode == 0:
            check.require(blob.stdout.strip() == item.get("git_blob_oid"), f"baseline git blob drift for {rel}")

    if isinstance(commit, str):
        exists = run_git("cat-file", "-e", f"{commit}^{{commit}}")
        check.require(exists.returncode == 0, f"execution-start commit is unavailable: {commit}")
        for tree_path, expected_oid in data.get("protected_tree_identities", {}).items():
            resolved = run_git("rev-parse", f"{commit}:{tree_path}")
            check.require(resolved.returncode == 0, f"cannot resolve protected tree {tree_path} at baseline")
            if resolved.returncode == 0:
                check.require(resolved.stdout.strip() == expected_oid, f"recorded baseline tree identity differs for {tree_path}")


def validate_source_interface(data: Any, sources: Any, artifacts: Any, check: Check) -> None:
    entries = data.get("entries", []) if isinstance(data, dict) else []
    check.require(isinstance(entries, list), "source-interface entries must be a list")
    source_ids = {record.get("id") for record in sources.get("records", [])}
    artifact_ids = {record.get("id") for record in artifacts.get("records", [])}
    ids = [entry.get("stable_id") for entry in entries if isinstance(entry, dict)]
    check.require(not duplicate_values(ids), "source-interface stable IDs must be unique")
    interface_source_ids = {entry.get("stable_id") for entry in entries if entry.get("registry") == "sources"}
    interface_artifact_ids = {entry.get("stable_id") for entry in entries if entry.get("registry") == "artifacts"}
    check.require(interface_source_ids == source_ids, f"source-interface source coverage mismatch: expected {sorted(source_ids)}, got {sorted(interface_source_ids)}")
    check.require(interface_artifact_ids == artifact_ids, f"source-interface artifact coverage mismatch: expected {sorted(artifact_ids)}, got {sorted(interface_artifact_ids)}")

    required_keys = {
        "stable_id", "registry", "source_class", "retrieval_tier",
        "primary_retrieval_paths", "research_role", "plausible_units_of_analysis",
        "objective_or_optimization_target", "mechanism_family_tags",
        "evaluation_ground_truth_style", "time_horizon", "cost_boundary",
        "high_value_assumptions", "known_relations", "independence_caveat",
        "non_authority_warning", "access_coverage",
    }
    for entry in entries:
        if not isinstance(entry, dict):
            check.errors.append("source-interface entry must be an object")
            continue
        sid = entry.get("stable_id", "<missing>")
        check.require(required_keys <= set(entry), f"source-interface {sid} lacks required fields: {sorted(required_keys - set(entry))}")
        check.require(isinstance(entry.get("retrieval_tier"), int) and 1 <= entry.get("retrieval_tier", 0) <= 5, f"source-interface {sid} retrieval_tier must be 1..5")
        check_paths(entry.get("primary_retrieval_paths", []), f"source-interface {sid}", check)
        role = entry.get("research_role", {})
        objective = entry.get("objective_or_optimization_target", {})
        coverage = entry.get("access_coverage", {})
        for field_name, field in (("research_role", role), ("objective", objective), ("access_coverage", coverage)):
            if isinstance(field, dict) and "evidence_class" in field:
                check.require(field["evidence_class"] in SOURCE_EVIDENCE_CLASSES, f"source-interface {sid} invalid {field_name} evidence class")
        if isinstance(coverage, dict):
            check_paths(coverage.get("inspected_paths", []), f"source-interface {sid} inspected_paths", check)
        for relation in entry.get("known_relations", []):
            check.require(relation in source_ids | artifact_ids, f"source-interface {sid} has unknown relation {relation!r}")


def validate_ledger(data: Any, check: Check) -> None:
    entries = data.get("entries", []) if isinstance(data, dict) else []
    check.require(isinstance(entries, list), "phase ledger entries must be a list")
    ids = [entry.get("claim_id") for entry in entries if isinstance(entry, dict)]
    check.require(not duplicate_values(ids), "phase ledger claim IDs must be unique")
    check.require(REQUIRED_LEDGER_IDS <= set(ids), f"phase ledger lacks required entries: {sorted(REQUIRED_LEDGER_IDS - set(ids))}")
    required_keys = {
        "claim_id", "phase", "batch", "evidence_class", "bounded_claim",
        "direct_primary_authority_paths", "later_synthesis_paths",
        "tested_task_configuration_horizon", "supported_scope",
        "explicit_non_conclusions", "counterevidence_or_invalid_attempts",
        "uncertainty_labels", "established_falsifier_or_next_discriminating_evidence",
        "architecture_or_gate_relation", "independence_notes",
    }
    for entry in entries:
        if not isinstance(entry, dict):
            check.errors.append("phase ledger entry must be an object")
            continue
        cid = entry.get("claim_id", "<missing>")
        check.require(required_keys <= set(entry), f"phase ledger {cid} lacks required fields: {sorted(required_keys - set(entry))}")
        check.require(entry.get("evidence_class") in LEDGER_EVIDENCE_CLASSES, f"phase ledger {cid} has invalid evidence class")
        check_paths(entry.get("direct_primary_authority_paths", []), f"phase ledger {cid} direct authority", check)
        check_paths(entry.get("later_synthesis_paths", []), f"phase ledger {cid} later synthesis", check)
        check.require(bool(entry.get("explicit_non_conclusions")), f"phase ledger {cid} must preserve at least one explicit non-conclusion")
        labels = entry.get("uncertainty_labels", [])
        check.require(isinstance(labels, list) and bool(labels), f"phase ledger {cid} must include uncertainty labels")
        for label in labels if isinstance(labels, list) else []:
            check.require(isinstance(label, dict) and label.get("label") in UNCERTAINTY_LABELS, f"phase ledger {cid} has invalid uncertainty label {label!r}")


def validate_constructs(data: Any, check: Check) -> None:
    constructs = data.get("constructs", []) if isinstance(data, dict) else []
    labels = [entry.get("label") for entry in constructs if isinstance(entry, dict)]
    ids = [entry.get("construct_id") for entry in constructs if isinstance(entry, dict)]
    check.require(not duplicate_values(ids), "construct IDs must be unique")
    check.require(REQUIRED_CONSTRUCT_LABELS <= set(labels), f"construct map lacks required labels: {sorted(REQUIRED_CONSTRUCT_LABELS - set(labels))}")
    for entry in constructs:
        if not isinstance(entry, dict):
            check.errors.append("construct entry must be an object")
            continue
        cid = entry.get("construct_id", "<missing>")
        required = {
            "construct_id", "label", "source_specific_meanings",
            "measurement_or_operationalization", "related_non_equivalent_terms",
            "collision_or_overload", "unresolved_normalization_question",
        }
        check.require(required <= set(entry), f"construct {cid} lacks required fields: {sorted(required - set(entry))}")
        meanings = entry.get("source_specific_meanings", [])
        check.require(isinstance(meanings, list) and bool(meanings), f"construct {cid} must have source-specific meanings")
        for meaning in meanings if isinstance(meanings, list) else []:
            check.require(meaning.get("evidence_class") in SOURCE_EVIDENCE_CLASSES, f"construct {cid} has invalid evidence class")
            check.require(bool(meaning.get("unit_of_analysis")), f"construct {cid} meaning lacks unit_of_analysis")
            check_paths(meaning.get("primary_references", []), f"construct {cid} primary references", check)


def validate_tensions(path: Path, check: Check) -> int:
    text = path.read_text(encoding="utf-8")
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        if line.startswith("|") and not line.startswith(("|---", "| Tension")):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) >= 2:
                rows.append((cells[0], cells[1]))
    row_names = {row[0] for row in rows}
    check.require(REQUIRED_TENSION_TERMS <= row_names, f"tension matrix lacks rows: {sorted(REQUIRED_TENSION_TERMS - row_names)}")
    for name, classification in rows:
        check.require(classification in ALLOWED_TENSION_CLASSES, f"tension {name!r} has invalid classification {classification!r}")
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "#")):
            continue
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
            inside = True
        except ValueError:
            inside = False
        check.require(inside and resolved.exists(), f"tension matrix link does not resolve: {target}")
    return len(rows)


def validate_claim_index(path: Path, ledger: Any, check: Check) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            check.errors.append(f"claim index line {line_number} is invalid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            check.errors.append(f"claim index line {line_number} must be an object")
            continue
        claims.append(value)
    ids = [claim.get("claim_id") for claim in claims]
    check.require(not duplicate_values(ids), "claim index IDs must be unique")
    required_keys = {
        "claim_id", "normalized_short_proposition", "claim_status",
        "supporting_authority_paths", "challenging_counterevidence_paths",
        "dependent_claims", "scope_boundary_tags", "source_independence_notes",
        "retrieval_priority",
    }
    for claim in claims:
        cid = claim.get("claim_id", "<missing>")
        check.require(required_keys <= set(claim), f"claim index {cid} lacks fields: {sorted(required_keys - set(claim))}")
        check.require(claim.get("claim_status") in CLAIM_STATUSES, f"claim index {cid} has invalid status")
        check.require(isinstance(claim.get("retrieval_priority"), int) and 1 <= claim.get("retrieval_priority", 0) <= 5, f"claim index {cid} retrieval priority must be 1..5")
        check_paths(claim.get("supporting_authority_paths", []), f"claim index {cid} support", check)
        check_paths(claim.get("challenging_counterevidence_paths", []), f"claim index {cid} counterevidence", check)
        check.require(bool(claim.get("scope_boundary_tags")), f"claim index {cid} needs scope boundary tags")
    ledger_ids = {entry.get("claim_id") for entry in ledger.get("entries", [])}
    check.require(ledger_ids <= set(ids), f"claim index does not cover all ledger claims: {sorted(ledger_ids - set(ids))}")
    for claim in claims:
        for dependency in claim.get("dependent_claims", []):
            check.require(dependency in set(ids), f"claim index {claim.get('claim_id')} has unknown dependency {dependency!r}")
    return claims


def validate_session_design(check: Check) -> None:
    prompt = (PACKAGE / "ultra-session-prompt.md").read_text(encoding="utf-8")
    contract = (PACKAGE / "ultra-session-contract.md").read_text(encoding="utf-8")
    template = (PACKAGE / "candidate-formulation-template.md").read_text(encoding="utf-8")
    prompt_requirements = {
        "DO NOT EXECUTE": "prompt must be visibly unexecuted",
        "one continuous": "prompt must require one continuous session",
        "at least three": "prompt must require at least three competing formulations",
        "research/problem-definition.md": "prompt must treat the provisional problem prior explicitly",
        "primary": "prompt must require primary-source checking",
        "counterevidence": "prompt must require counterevidence",
        "no single unified thesis": "prompt must permit no single unified thesis",
        "discriminating hypotheses": "prompt must derive experiments from discriminating hypotheses",
        "anti-literature-review": "prompt must require the anti-literature-review audit",
    }
    lowered = prompt.lower()
    for needle, message in prompt_requirements.items():
        check.require(needle.lower() in lowered, message)
    for required_path in (
        "source-interface.yaml", "phase-evidence-ledger.yaml", "construct-map.yaml",
        "assumption-tension-matrix.md", "claim-evidence-index.jsonl",
        "candidate-formulation-template.md", "ultra-session-contract.md",
    ):
        check.require(required_path in prompt, f"prompt does not reference {required_path}")
    for needle in ("single continuous", "competing", "adversarial", "plural", "primary", "unknown", "unexecuted"):
        check.require(needle.lower() in contract.lower(), f"session contract lacks required concept {needle!r}")
    for needle in ("explanandum", "unit of analysis", "causal", "falsif", "counterevidence", "scope"):
        check.require(needle.lower() in template.lower(), f"candidate template lacks required concept {needle!r}")


def validate_protected_trees(baseline: Any, check: Check) -> None:
    for tree_path, expected_oid in baseline.get("protected_tree_identities", {}).items():
        resolved = run_git("rev-parse", f"HEAD:{tree_path}")
        check.require(resolved.returncode == 0, f"cannot resolve current protected tree {tree_path}")
        if resolved.returncode == 0:
            check.require(resolved.stdout.strip() == expected_oid, f"protected tree changed since execution start: {tree_path}")
    status = run_git("status", "--porcelain", "--untracked-files=all", "--", "sources", "references/papers", "experiments")
    check.require(status.returncode == 0, f"cannot inspect protected-tree working state: {status.stderr.strip()}")
    if status.returncode == 0:
        check.require(not status.stdout.strip(), f"protected trees contain working changes:\n{status.stdout.rstrip()}")


def main() -> int:
    check = Check()
    missing = sorted(name for name in REQUIRED_PACKAGE_FILES if not (PACKAGE / name).is_file())
    check.require(not missing, f"readiness package is missing required files: {missing}")
    if missing:
        for error in check.errors:
            print(f"ERROR: {error}")
        return 1

    baseline = load_json(PACKAGE / "baseline-manifest.json", check)
    source_interface = load_json(PACKAGE / "source-interface.yaml", check)
    ledger = load_json(PACKAGE / "phase-evidence-ledger.yaml", check)
    constructs = load_json(PACKAGE / "construct-map.yaml", check)
    sources = load_json(ROOT / "corpus" / "sources.yaml", check)
    artifacts = load_json(ROOT / "corpus" / "artifacts.yaml", check)

    validate_baseline(baseline, sources, artifacts, check)
    validate_source_interface(source_interface, sources, artifacts, check)
    validate_ledger(ledger, check)
    validate_constructs(constructs, check)
    tension_count = validate_tensions(PACKAGE / "assumption-tension-matrix.md", check)
    claims = validate_claim_index(PACKAGE / "claim-evidence-index.jsonl", ledger, check)
    validate_session_design(check)
    validate_protected_trees(baseline, check)

    for name, data in (
        ("baseline-manifest", baseline),
        ("source-interface", source_interface),
        ("phase-evidence-ledger", ledger),
        ("construct-map", constructs),
        ("claim-evidence-index", claims),
    ):
        scan_prohibited_keys(data, name, check)

    if check.errors:
        print("PRE-SYNTHESIS READINESS VALIDATION: FAIL")
        for error in check.errors:
            print(f"ERROR: {error}")
        print("Scientific truth and formulation merit were not evaluated.")
        return 1

    print("PRE-SYNTHESIS READINESS VALIDATION: PASS")
    print(f"Execution baseline: {baseline.get('execution_start_commit')}")
    print(f"Registered interface coverage: {len(sources.get('records', []))} sources, {len(artifacts.get('records', []))} artifacts")
    print(f"Phase evidence ledger: {len(ledger.get('entries', []))} entries")
    print(f"Construct map: {len(constructs.get('constructs', []))} constructs")
    print(f"Assumption/tension matrix: {tension_count} classified tensions")
    print(f"Claim/evidence index: {len(claims)} claims")
    print("Protected trees: sources/, references/papers/, and experiments/ unchanged")
    print("Scope: structural and referential integrity only; scientific truth was not evaluated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
