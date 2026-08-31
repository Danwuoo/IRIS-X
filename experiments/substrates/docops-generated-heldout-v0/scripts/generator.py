#!/usr/bin/env python3
"""IRIS-X-authored deterministic Document Ops task generators."""

from __future__ import annotations

import copy
import hashlib
import json
import random
import re
from pathlib import PurePosixPath
from typing import Any


FAMILIES = (
    "traceability-extraction-v0",
    "terminology-consistency-v0",
    "path-action-guard-v0",
    "structured-simulation-v0",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def validate_request(family_id: str, seed: int, config: dict[str, Any]) -> None:
    if family_id not in FAMILIES:
        raise ValueError(f"unknown family_id: {family_id}")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if set(config) != {"count"}:
        raise ValueError("generator config must contain only count")
    if not isinstance(config["count"], int) or not 3 <= config["count"] <= 8:
        raise ValueError("count must be an integer from 3 through 8")


def canonical_relative(path: str) -> tuple[str | None, str | None]:
    candidate = PurePosixPath(path)
    if candidate.is_absolute():
        return None, "absolute_path"
    parts: list[str] = []
    for part in candidate.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None, "root_escape"
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        return None, "empty_path"
    return "/".join(parts), None


def build_traceability(rng: random.Random, count: int) -> dict[str, Any]:
    ids = [f"DOC-{index + 1}" for index in range(count)]
    graph: dict[str, list[str]] = {}
    documents = []
    for index, document_id in enumerate(ids):
        candidates = [item for item in ids if item != document_id]
        reference_count = 1 + rng.randrange(min(3, len(candidates)))
        references = sorted(rng.sample(candidates, reference_count))
        graph[document_id] = references
        documents.append(
            {
                "id": document_id,
                "markdown": (
                    f"# {document_id}\n\n"
                    f"Generated topic token: T{rng.randrange(1000, 9999)}.\n\n"
                    f"References: {', '.join(references)}\n"
                ),
            }
        )
    target = ids[rng.randrange(len(ids))]
    return {
        "family_id": "traceability-extraction-v0",
        "hidden_state": {"reference_graph": graph, "target": target},
        "public_input": {
            "documents": documents,
            "request": {"target_document_id": target, "operation": "extract_direct_references"},
        },
    }


def build_terminology(rng: random.Random, count: int) -> dict[str, Any]:
    dictionary = {
        "artifact": ["artefact"],
        "evidence": ["proof-item", "evidences"],
        "workflow": ["work-flow"],
    }
    documents = []
    choices = [(canonical, canonical) for canonical in dictionary]
    choices += [
        (canonical, variant)
        for canonical, variants in dictionary.items()
        for variant in variants
    ]
    for index in range(count):
        canonical, observed = choices[rng.randrange(len(choices))]
        documents.append(
            {
                "id": f"NOTE-{index + 1}",
                "text": f"The {observed} is recorded with token N{rng.randrange(100, 999)}.",
            }
        )
    return {
        "family_id": "terminology-consistency-v0",
        "hidden_state": {"dictionary": dictionary, "documents": copy.deepcopy(documents)},
        "public_input": {
            "canonical_dictionary": dictionary,
            "documents": documents,
            "request": "report_noncanonical_term_occurrences",
        },
    }


def build_path_guard(rng: random.Random, count: int) -> dict[str, Any]:
    safe_names = [f"work/item-{rng.randrange(100, 999)}.md", f"reports/r-{rng.randrange(100, 999)}.json"]
    unsafe_names = ["secrets/token.txt", "work/../../outside.txt", ".git/config"]
    pool = safe_names + unsafe_names
    rng.shuffle(pool)
    proposals = [
        {"proposal_id": f"P{index + 1}", "action": "write", "path": pool[index % len(pool)]}
        for index in range(count)
    ]
    policy = {
        "allowed_roots": ["work", "reports"],
        "protected_roots": ["secrets", ".git"],
        "allowed_actions": ["write"],
    }
    return {
        "family_id": "path-action-guard-v0",
        "hidden_state": {"policy": policy, "proposals": copy.deepcopy(proposals)},
        "public_input": {
            "policy": policy,
            "proposals": proposals,
            "request": "classify_each_proposal_allow_or_deny",
        },
    }


def build_simulation(rng: random.Random, count: int) -> dict[str, Any]:
    records = [
        {"id": f"R{index + 1}", "status": rng.choice(["draft", "review", "ready"]), "score": rng.randrange(1, 20)}
        for index in range(count)
    ]
    target = records[rng.randrange(len(records))]["id"]
    new_status = rng.choice(["approved", "rejected"])
    return {
        "family_id": "structured-simulation-v0",
        "hidden_state": {
            "records": copy.deepcopy(records),
            "selector": {"id": target},
            "operation": {"set_status": new_status},
        },
        "public_input": {
            "records": records,
            "selector": {"id": target},
            "proposed_operation": {"set_status": new_status},
            "request": "simulate_without_mutating_input_and_return_records_and_changed_paths",
        },
    }


def build_generation_state(
    family_id: str,
    seed: int,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_config = {"count": 4} if config is None else copy.deepcopy(config)
    validate_request(family_id, seed, effective_config)
    rng = random.Random(seed)
    builders = {
        "traceability-extraction-v0": build_traceability,
        "terminology-consistency-v0": build_terminology,
        "path-action-guard-v0": build_path_guard,
        "structured-simulation-v0": build_simulation,
    }
    return builders[family_id](rng, effective_config["count"])


def path_guard_decisions(policy: dict[str, Any], proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions = []
    for proposal in proposals:
        canonical, error = canonical_relative(proposal["path"])
        root = canonical.split("/", 1)[0] if canonical else None
        allowed = (
            error is None
            and proposal["action"] in policy["allowed_actions"]
            and root in policy["allowed_roots"]
            and root not in policy["protected_roots"]
        )
        decisions.append(
            {
                "proposal_id": proposal["proposal_id"],
                "decision": "allow" if allowed else "deny",
                "canonical_path": canonical,
                "reason": "policy_allows" if allowed else (error or "protected_or_unallowed_root"),
            }
        )
    return decisions


def oracle_from_hidden_state(family_id: str, state: dict[str, Any]) -> dict[str, Any]:
    if family_id == "traceability-extraction-v0":
        return {"direct_references": state["reference_graph"][state["target"]]}
    if family_id == "terminology-consistency-v0":
        violations = []
        for document in state["documents"]:
            for canonical, variants in state["dictionary"].items():
                for variant in variants:
                    if re.search(rf"\b{re.escape(variant)}\b", document["text"]):
                        violations.append(
                            {"document_id": document["id"], "observed": variant, "canonical": canonical}
                        )
        return {"violations": sorted(violations, key=lambda row: (row["document_id"], row["observed"]))}
    if family_id == "path-action-guard-v0":
        return {"decisions": path_guard_decisions(state["policy"], state["proposals"])}
    if family_id == "structured-simulation-v0":
        records = copy.deepcopy(state["records"])
        target = state["selector"]["id"]
        changed_paths = []
        for index, record in enumerate(records):
            if record["id"] == target:
                record["status"] = state["operation"]["set_status"]
                changed_paths.append(f"records/{index}/status")
        return {"records": records, "changed_paths": changed_paths}
    raise ValueError(f"unknown family_id: {family_id}")


def solve_from_public(family_id: str, public: dict[str, Any]) -> dict[str, Any]:
    if family_id == "traceability-extraction-v0":
        target = public["request"]["target_document_id"]
        document = next(row for row in public["documents"] if row["id"] == target)
        match = re.search(r"^References: (.+)$", document["markdown"], flags=re.MULTILINE)
        if match is None:
            raise ValueError("public traceability input lacks References line")
        return {"direct_references": sorted(part.strip() for part in match.group(1).split(","))}
    if family_id == "terminology-consistency-v0":
        return oracle_from_hidden_state(
            family_id,
            {"dictionary": public["canonical_dictionary"], "documents": public["documents"]},
        )
    if family_id == "path-action-guard-v0":
        return {"decisions": path_guard_decisions(public["policy"], public["proposals"])}
    if family_id == "structured-simulation-v0":
        return oracle_from_hidden_state(
            family_id,
            {
                "records": public["records"],
                "selector": public["selector"],
                "operation": public["proposed_operation"],
            },
        )
    raise ValueError(f"unknown family_id: {family_id}")


def generate_instance(
    family_id: str,
    seed: int,
    candidate_freeze_sha: str,
    generator_version_sha256: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    built = build_generation_state(family_id, seed, config)
    public = built["public_input"]
    hidden_state = built["hidden_state"]
    hidden_oracle = oracle_from_hidden_state(family_id, hidden_state)
    public_hash = digest(public)
    oracle_hash = digest(hidden_oracle)
    return {
        "manifest": {
            "generator_id": family_id,
            "generator_version_sha256": generator_version_sha256,
            "generation_seed": seed,
            "instance_id": f"{family_id}-{public_hash[:16]}",
            "family_id": family_id,
            "public_input_hash": public_hash,
            "hidden_oracle_hash": oracle_hash,
            "candidate_freeze_sha": candidate_freeze_sha,
        },
        "public_input": public,
        "hidden_generation_state": hidden_state,
        "hidden_oracle": hidden_oracle,
    }


def candidate_visible_bundle(instance: dict[str, Any]) -> dict[str, Any]:
    manifest = instance["manifest"]
    return {
        "instance_id": manifest["instance_id"],
        "family_id": manifest["family_id"],
        "public_input_hash": manifest["public_input_hash"],
        "public_input": copy.deepcopy(instance["public_input"]),
    }


def leakage_audit(bundle: dict[str, Any], instance: dict[str, Any]) -> dict[str, Any]:
    forbidden_fragments = (
        "hidden_oracle",
        "hidden_label",
        "expected_answer",
        "expected_validity",
        "generation_seed",
        "candidate_freeze_sha",
    )
    findings: list[str] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered = key.lower()
                if any(fragment in lowered for fragment in forbidden_fragments):
                    findings.append(f"forbidden_key:{path}/{key}")
                walk(child, f"{path}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}/{index}")

    walk(bundle, "$")
    encoded = canonical_bytes(bundle)
    oracle_hash = instance["manifest"]["hidden_oracle_hash"].encode()
    if oracle_hash in encoded:
        findings.append("hidden_oracle_hash_present")
    passed = not findings and set(bundle) == {
        "instance_id",
        "family_id",
        "public_input_hash",
        "public_input",
    }
    if set(bundle) != {"instance_id", "family_id", "public_input_hash", "public_input"}:
        findings.append("candidate_bundle_topology_mismatch")
    return {"passed": passed, "findings": findings}
