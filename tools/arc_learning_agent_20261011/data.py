"""Lineage-closed clean data and native compact-grid training records.

Only explicit calls read data. Original challenge test fields are never retained.
This is a fresh official-training/authored corpus, not the contaminated NVARC corpus.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time

from tools.arc_next_models import canonical, digest, require
from tools.arc_next_training import task_group_split
from src.irisx.arc_nvarc_data import grid as _native_grid, known_variant_group, seeded_transform, transform_grid
from src.irisx.errors import ValidationError


def grid(value):
    try:
        return _native_grid(value)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

FORMAT = "irisx/learning-agent-split-v1"
IDENTITY = {"rotation": 0, "transpose": False, "colors": list(range(10))}


def _demos(task):
    require(type(task) is dict and set(task) == {"train"}, "demonstration-only task required; test fields forbidden")
    require(type(task["train"]) is list and bool(task["train"]), "nonempty demonstrations required")
    result = []
    for pair in task["train"]:
        require(type(pair) is dict and set(pair) == {"input", "output"}, "exact demo pair required")
        result.append({"input": grid(pair["input"]), "output": grid(pair["output"])})
    return result


def load_official_training(source_dir, inventory_path, *, protected_ids=()):
    """Use pinned upstream byte/blob checks before stripping every original test."""
    from tools.arc_next_materials import groups, sanitize_source
    inventory = json.loads(Path(inventory_path).read_text())
    # Reuses exact 1000-task path/revision validation before reading task bytes.
    fixed = groups(inventory, training_count=800, development_count=200)
    protected = set(protected_ids)
    tasks, receipts = {}, {}
    root = Path(source_dir).resolve()
    for entry in inventory["files"]:
        task_id = Path(entry["path"]).stem
        require(task_id not in protected, "protected source task: " + task_id)
        path = root / (task_id + ".json")
        require(path.resolve().parent == root and not path.is_symlink(), "source escape/symlink forbidden")
        tasks[task_id], receipts[task_id] = sanitize_source(path.read_bytes(), entry)
    return tasks, {"repository": inventory["repository"], "revision": inventory["commit"],
                   "inventory_sha256": digest(inventory), "files": receipts,
                   "task_count": len(tasks), "scope": "official-training-demonstrations-only",
                   "fixed_splits": {"train": fixed["training_ids"], "dev": fixed["development_ids"]}}


def create_split_manifest(tasks_by_id, *, protected_ids=(), ancestry=None, family_ids=None,
                          seed=0, dev_fraction=0.2, source_identity=None, fixed_splits=None):
    """Split complete ancestry/family/known-variant components before augmentation.

    ancestry maps known node IDs to immediate parents, with [] for roots. A missing
    task node defaults to a root; references to any other unknown node fail closed.
    This catches a useful exact symmetry class, not general semantic duplicates.
    """
    require(type(tasks_by_id) is dict and len(tasks_by_id) >= 2, "at least two task groups required")
    require(all(type(k) is str and k for k in tasks_by_id), "nonempty task IDs required")
    cleaned = {key: {"train": _demos(value)} for key, value in tasks_by_id.items()}
    families = dict(family_ids or {})
    require(set(families) <= set(cleaned), "unknown family task")
    graph = deepcopy(ancestry or {})
    for key in cleaned:
        graph.setdefault(key, [])
    require(all(type(k) is str and k and type(v) is list and len(v) == len(set(v)) and
                all(type(x) is str and x for x in v) for k, v in graph.items()), "invalid ancestry graph")
    require(all(p in graph for parents in graph.values() for p in parents), "unknown ancestor")
    protected = set(protected_ids)
    require(all(type(x) is str and x for x in protected), "invalid protected IDs")
    closure, visiting = {}, set()
    def visit(key):
        require(key not in visiting, "ancestry cycle")
        if key not in closure:
            visiting.add(key)
            ancestors = {key}
            for parent in graph[key]:
                ancestors.update(visit(parent))
            visiting.remove(key)
            require(not ancestors & protected, "protected ancestor: " + key)
            closure[key] = ancestors
        return closure[key]
    for key in graph:
        visit(key)
    links = {key: key for key in cleaned}
    def find(key):
        while links[key] != key:
            links[key] = links[links[key]]
            key = links[key]
        return key
    def union(a, b):
        a, b = find(a), find(b)
        links[max(a, b)] = min(a, b)
    seen = {}
    variants = {}
    for key in sorted(cleaned):
        variants[key] = known_variant_group({**cleaned[key], "test": []})
        family = families.get(key, "official-task:" + key)
        require(type(family) is str and family, "nonempty family ID required")
        families[key] = family
        tags = [("ancestor", a) for a in closure[key]] + [("family", family), ("variant", variants[key])]
        for tag in tags:
            if tag in seen:
                union(key, seen[tag])
            else:
                seen[tag] = key
    components = {}
    for key in sorted(cleaned):
        components.setdefault(find(key), []).append(key)
    require(len(components) >= 2, "independent train/dev components unavailable")
    fixed = deepcopy(fixed_splits if fixed_splits is not None else (source_identity or {}).get("fixed_splits"))
    demoted = []
    historical = (source_identity or {}).get("fixed_splits")
    if historical is not None:
        require(fixed is not None and all(set(fixed.get(part, [])) == set(historical[part]) for part in ("train", "dev")), "cannot override historical source partition")
    if fixed is None:
        split = task_group_split(list(components), seed=seed, dev_fraction=dev_fraction)
        partition = {key: part for part, groups_ in split.items() for group in groups_ for key in components[group]}
    else:
        require(type(fixed) is dict and set(fixed) == {"train", "dev"} and
                all(type(v) is list and len(v) == len(set(v)) for v in fixed.values()) and
                not set(fixed["train"]) & set(fixed["dev"]) and
                set(fixed["train"]) | set(fixed["dev"]) == set(cleaned), "exhaustive fixed source partitions required")
        original = {key: part for part, keys in fixed.items() for key in keys}
        partition = {}
        for component in components.values():
            # A known linkage can move old training material to dev, never the reverse.
            part = "dev" if any(original[key] == "dev" for key in component) else "train"
            for key in component:
                partition[key] = part
                if original[key] == "train" and part == "dev":
                    demoted.append(key)
        require("train" in partition.values() and "dev" in partition.values(), "fixed split leaves no independent training/development")
    parent_parts = {}
    for key in cleaned:
        for parent in closure[key]:
            require(parent not in parent_parts or parent_parts[parent] == partition[key], "cross-split ancestor")
            parent_parts[parent] = partition[key]
    # Unused graph nodes cannot supply an unpartitioned parent later.
    result = {"format": FORMAT, "split_seed": seed, "dev_fraction": dev_fraction,
              "source_identity": deepcopy(source_identity or {}), "protected_ids": sorted(protected),
              "fixed_splits": fixed, "train_to_dev_component_demotions": sorted(demoted),
              "parents": {key: {"parents": graph[key], "split": parent_parts[key]}
                          for key in sorted(parent_parts)},
              "tasks": {key: {"split": partition[key], "family_id": families[key],
                                "parent_ids": [key], "ancestor_ids": sorted(closure[key]),
                                "task_sha256": digest(cleaned[key]), "demonstrations": deepcopy(cleaned[key]["train"]), "variant_group": variants[key]}
                        for key in sorted(cleaned)},
              "components": [components[k] for k in sorted(components)],
              "independence_limit": "known D4/color/demo-order variants, declared families and ancestry; not semantic independence proof"}
    result["manifest_sha256"] = digest(result)
    return result


def _validate_manifest(manifest, protected_ids):
    require(type(manifest) is dict and manifest.get("format") == FORMAT, "lineage-closed split manifest required")
    payload = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    require(digest(payload) == manifest.get("manifest_sha256"), "split manifest digest changed")
    protected = set(protected_ids) | set(manifest["protected_ids"])
    parents, tasks = manifest["parents"], manifest["tasks"]
    require(type(parents) is dict and type(tasks) is dict and tasks, "manifest ancestry/tasks missing")
    ancestors, visiting = {}, set()
    def visit(key):
        require(key in parents, "unknown parent")
        require(key not in visiting, "ancestry cycle")
        if key not in ancestors:
            visiting.add(key)
            item = parents[key]
            require(item["split"] in ("train", "dev"), "invalid parent split")
            values = {key}
            for parent in item["parents"]:
                require(parent in parents and parents[parent]["split"] == item["split"], "cross-split/unknown ancestor")
                values.update(visit(parent))
            visiting.remove(key)
            require(not values & protected, "protected ancestor")
            ancestors[key] = values
        return ancestors[key]
    for key in parents:
        visit(key)
    if manifest.get("fixed_splits"):
        require(all(key in tasks and tasks[key]["split"] == "dev" for key in manifest["fixed_splits"]["dev"]), "historical development parent promoted to train")
    require(all(key in tasks and tasks[key]["split"] == "dev" for key in manifest.get("historical_dev_ids", [])), "historical development parent promoted to train")
    def source_historical_dev(node):
        if type(node) is not dict:
            return set()
        result = set((node.get("fixed_splits") or {}).get("dev", []))
        for item in node.get("inputs", []):
            result.update(source_historical_dev(item.get("source_identity", {})))
        return result
    require(all(key in tasks and tasks[key]["split"] == "dev" for key in source_historical_dev(manifest.get("source_identity", {}))), "source historical development partition changed")
    family_parts, variant_parts = {}, {}
    for key, task in tasks.items():
        require(digest({"train": _demos({"train": task.get("demonstrations")})}) == task["task_sha256"], "manifest demonstrations changed")
        require(task["split"] in ("train", "dev") and task["parent_ids"], "invalid task partition")
        values = set()
        for parent in task["parent_ids"]:
            values.update(visit(parent))
            require(parents[parent]["split"] == task["split"], "cross-split task")
        require(values == set(task["ancestor_ids"]), "ancestor closure changed")
        for store, tag in ((family_parts, task["family_id"]), (variant_parts, task["variant_group"])):
            require(tag not in store or store[tag] == task["split"], "cross-split family/variant overlap")
            store[tag] = task["split"]
    return ancestors


def semantic_sample_id(record):
    """Identity of the learning example, never its measured execution receipt.

    record_id continues to bind the complete original evidence and is validated
    unchanged. This deliberately narrow semantic projection is only a sampling
    key, NOT an admission proof or an exact-restart identity. Identical examples
    retain their input-order occurrence order; runtime hashes never break ties.
    """
    provenance = record.get("provenance", {})
    source = {key: provenance[key] for key in (
        "source_task_sha256", "objective", "held_out_demo", "visible_demo_indices",
        "augmentation", "augmentation_index", "generator_family", "authored_reference",
        "generalization_claim", "prompt_task") if key in provenance}
    context = provenance.get("generation_context")
    if context is not None:
        source["generation_context"] = {key: context[key] for key in (
            "visible_indices", "held_out_demo_index") if key in context}
    return digest({"format": "irisx/semantic-training-sample-v1",
                   "sample": {key: record[key] for key in (
                       "split", "task_id", "parent_ids", "family_id", "kind", "messages", "completion")},
                   "source": source})


def _seal_record(record):
    record["record_id"] = digest(record)
    return record


def build_records(tasks_by_id, split_manifest, *, protected_ids=(), augmentations=8, seed=0):
    """Compact-grid LODO; all augmentation descendants retain full lineage."""
    from .grid_codec import encode_grid, grid_messages
    _validate_manifest(split_manifest, protected_ids)
    require(type(augmentations) is int and 1 <= augmentations <= 128, "augmentation count must be 1..128")
    require(set(tasks_by_id) == set(split_manifest["tasks"]), "exact manifest task coverage required")
    records = []
    for task_id in sorted(tasks_by_id):
        demos = _demos(tasks_by_id[task_id])
        entry = split_manifest["tasks"][task_id]
        require(digest({"train": demos}) == entry["task_sha256"], "source task changed")
        require(len(demos) >= 2, "LODO requires two demos")
        views = augmentations if entry["split"] == "train" else 1
        for index in range(views):
            spec = deepcopy(IDENTITY) if index == 0 else seeded_transform({"task_id": task_id, "train": demos}, seed, index)
            for held_out, target in enumerate(demos):
                visible_indices = [i for i in spec.get("demo_order", list(range(len(demos)))) if i != held_out]
                visible = [{k: transform_grid(demos[i][k], spec) for k in ("input", "output")} for i in visible_indices]
                record = {"split": entry["split"], "task_id": task_id,
                          "parent_ids": entry["parent_ids"][:], "family_id": entry["family_id"], "kind": "grid",
                          "messages": grid_messages(visible, transform_grid(target["input"], spec)),
                          "completion": encode_grid(transform_grid(target["output"], spec)),
                          "provenance": {"source_task_sha256": entry["task_sha256"], "held_out_demo": held_out,
                                         "visible_demo_indices": visible_indices, "augmentation": spec,
                                         "augmentation_index": index, "objective": "demo-only-lodo"}}
                records.append(_seal_record(record))
    validate_records(records, split_manifest, protected_ids)
    return records


def build_task_records(task_id, demos, *, augmentations=8, seed=0):
    """Task-local schema uses no query inputs or query answers, including in lineage."""
    from .grid_codec import encode_grid, grid_messages
    cleaned = _demos({"train": demos})
    if len(cleaned) < 2:
        return []
    require(type(augmentations) is int and 1 <= augmentations <= 128, "invalid TTT augmentation count")
    records = []
    for view in range(augmentations):
        spec = deepcopy(IDENTITY) if view == 0 else seeded_transform({"task_id": task_id, "train": cleaned}, seed, view)
        for held_out, target in enumerate(cleaned):
            indices = [i for i in spec.get("demo_order", list(range(len(cleaned)))) if i != held_out]
            visible = [{k: transform_grid(cleaned[i][k], spec) for k in ("input", "output")} for i in indices]
            records.append(_seal_record({"task_id": task_id, "split": "train", "parent_ids": [task_id],
                "family_id": "task-local:" + task_id, "kind": "grid", "messages": grid_messages(visible, transform_grid(target["input"], spec)),
                "completion": encode_grid(transform_grid(target["output"], spec)),
                "provenance": {"objective": "demo-only-lodo", "held_out_demo": held_out,
                               "visible_demo_indices": indices, "augmentation": spec, "augmentation_index": view,
                               "source_task_sha256": digest({"train": cleaned})}}))
    return records


def validate_records(records, split_manifest, protected_ids):
    """Reject changed/unknown/protected ancestry and cross-split families before use."""
    from .grid_codec import decode_grid
    ancestors = _validate_manifest(split_manifest, protected_ids)
    require(type(records) is list, "records list required")
    seen = set()
    for record in records:
        require(type(record) is dict, "record dictionary required")
        require(record.get("record_id") == digest({k: v for k, v in record.items() if k != "record_id"}), "record digest changed")
        require(record["record_id"] not in seen, "duplicate record identity")
        seen.add(record["record_id"])
        require(record.get("kind") in ("grid", "program", "repair"), "invalid objective")
        task = split_manifest["tasks"].get(record.get("task_id"))
        require(task is not None, "unknown task parent")
        require(record.get("split") == task["split"] and record.get("family_id") == task["family_id"], "task family/split changed")
        require(record.get("parent_ids") == task["parent_ids"], "unknown or changed parents")
        for parent in record["parent_ids"]:
            require(parent in ancestors, "unknown parent")
        messages = record.get("messages")
        require(type(messages) is list and bool(messages), "nonempty messages required")
        require(all(type(m) is dict and set(m) == {"role", "content"} and m["role"] in ("system", "user", "assistant", "tool") and
                    type(m["content"]) is str and bool(m["content"]) for m in messages), "invalid chat messages")
        require(messages[-1]["role"] in ("user", "tool"), "completion must follow user or tool context")
        require(type(record.get("completion")) is str and bool(record["completion"]), "empty completion")
        provenance = record.get("provenance", {})
        require(provenance.get("source_task_sha256") == task["task_sha256"], "record source task hash differs")
        if record["kind"] == "grid":
            decode_grid(record["completion"])
            _validate_grid_target(record, task)
        elif provenance.get("objective") == "execution-verified-train-trajectory":
            require(record["split"] == "train", "trajectory refinement accepts training parents only")
            _validate_trajectory(record, task)
        else:
            proof = provenance.get("verification", {})
            episode = _authored_reference(provenance, task)
            require(record["completion"] == episode["witness_program"], "authored program differs from independent reference")
            require(provenance.get("generator_family") == task["family_id"] and
                    proof.get("witness_all_demo_fit") is True and proof.get("independent_query_exact") is True and
                    proof.get("program_sha256") == hashlib.sha256(record["completion"].encode()).hexdigest() and
                    proof.get("verifier_sha256") and proof.get("interpreter_sha256"), "independently verified authored program required")
            if record["kind"] == "repair":
                require(proof.get("mutation_semantic_failure") is True, "verified semantic repair required")
    return {"records": len(records), "split_counts": dict(Counter(r["split"] for r in records)),
            "kind_counts": dict(Counter(r["kind"] for r in records)), "records_sha256": digest(records),
            "manifest_sha256": split_manifest["manifest_sha256"], "protected_ancestors": "excluded"}


def build_authored_curriculum(*, per_family=8, seed=1015, deadline, output_dir):
    """Reuse eight authored formulas and independently verify every witness/mutation.

    Returns records, lineage manifest and actual bounded-VM receipts. The fixed
    first six families train, last two validate. No F/copy objective is admitted.
    A restricted count is a new export, never a claim of old 512-episode completion.
    """
    from .grid_codec import grid_messages, program_messages, encode_grid
    require(type(per_family) is int and 1 <= per_family <= 64, "per_family must be 1..64")
    root = Path(__file__).resolve().parents[1] / "arc_next_suite_20261009" / "src"
    # Legacy source imports its sibling modules by bare names; scoped path only.
    curriculum = _curriculum_module()
    agent = root / "arc_agent.py"
    if not agent.exists():
        # Actual pinned interpreter lives in the suite source directory.
        agent = root / "arc_program.py"
    # Identify the exact pinned dependency by hash, never an invented substitute.
    candidates = list(root.glob("*.py")) + list(root.parent.parent.glob("*.py"))
    agent = next((p for p in candidates if hashlib.sha256(p.read_bytes()).hexdigest() == curriculum.PINNED_INTERPRETER_SHA256), None)
    require(agent is not None, "pinned curriculum interpreter unavailable")
    verifier = next((p for p in candidates if hashlib.sha256(p.read_bytes()).hexdigest() == curriculum.PINNED_VERIFIER_SHA256), None)
    require(verifier is not None, "pinned curriculum verifier unavailable")
    verify = curriculum.fresh_verifier(agent, verifier)
    episodes, receipts, tasks, families, ancestry = [], [], {}, {}, {}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    for family_index, family in enumerate(curriculum.FAMILIES):
        for index in range(per_family):
            require(time.monotonic() < deadline, "curriculum deadline exhausted")
            episode = curriculum.build_episode(family_index * 64 + index, seed=seed)
            results = []
            for mutation in (False, True):
                remaining = deadline - time.monotonic()
                require(remaining > 0, "curriculum deadline exhausted")
                result = verify(episode["mutation_program" if mutation else "witness_program"], episode["task"], timeout_seconds=min(3.0, remaining))
                curriculum._check_receipt(result, episode, mutation=mutation)
                results.append(result)
            task_id = "authored:" + episode["episode_id"]
            family_id = "authored:" + family
            tasks[task_id] = {"train": episode["task"]["train"]}
            families[task_id] = family_id
            ancestry[task_id] = [family_id]
            ancestry[family_id] = []
            episodes.append((task_id, episode, results))
            receipts.append({"task_id": task_id, "witness": results[0], "mutation": results[1]})
    manifest = create_split_manifest(tasks, ancestry=ancestry, family_ids=families,
                                     source_identity={"kind": "authored-independent-formulas", "generator_sha256": hashlib.sha256(Path(curriculum.__file__).read_bytes()).hexdigest(),
                                                      "seed": seed, "source_arc_tasks": False})
    # Preserve the existing fixed generator-family split, without crossing components.
    for task_id, episode, _ in episodes:
        part = "train" if curriculum.FAMILY_SPLIT[episode["family"]] == "train" else "dev"
        manifest["tasks"][task_id]["split"] = part
        for ancestor in manifest["tasks"][task_id]["ancestor_ids"]:
            manifest["parents"][ancestor]["split"] = part
    manifest["manifest_sha256"] = digest({k: v for k, v in manifest.items() if k != "manifest_sha256"})
    records = []
    for task_id, episode, results in episodes:
        entry = manifest["tasks"][task_id]
        proof = {"witness_all_demo_fit": True, "independent_query_exact": True, "mutation_semantic_failure": True,
                 "program_sha256": hashlib.sha256(episode["witness_program"].encode()).hexdigest(),
                 "verifier_sha256": curriculum.PINNED_VERIFIER_SHA256, "interpreter_sha256": curriculum.PINNED_INTERPRETER_SHA256,
                 "receipt_sha256": digest(results)}
        base = {"task_id": task_id, "split": entry["split"], "parent_ids": entry["parent_ids"], "family_id": entry["family_id"],
                "provenance": {"source_task_sha256": entry["task_sha256"], "generator_family": entry["family_id"], "verification": proof, "authored_reference": {"episode_index": curriculum.FAMILIES.index(episode["family"]) * 64 + episode["augmentation_index"], "seed": seed, "generator_sha256": hashlib.sha256(Path(curriculum.__file__).read_bytes()).hexdigest()}}}
        task = episode["task"]
        records.append(_seal_record({**deepcopy(base), "kind": "grid", "messages": grid_messages(task["train"], task["test"][0]["input"]), "completion": encode_grid(episode["query_target"])}))
        records.append(_seal_record({**deepcopy(base), "kind": "program", "messages": program_messages(task), "completion": episode["witness_program"]}))
        feedback = {"source": episode["mutation_program"], "program_sha256": hashlib.sha256(episode["mutation_program"].encode()).hexdigest(), "demo_results": results[1]["feedback"]["demonstrations"], "errors": [], "partial_score": 0.0}
        records.append(_seal_record({**deepcopy(base), "kind": "repair", "messages": program_messages(task, feedback=feedback), "completion": episode["witness_program"]}))
    report = validate_records(records, manifest, ())
    report.update(receipts_path=str((out / "receipts.json").resolve()), receipts_sha256=hashlib.sha256(canonical(receipts) + b"\n").hexdigest(), episodes=len(episodes), families=len(curriculum.FAMILIES), unique_programs=len({r["completion"] for r in records if r["kind"] == "program"}),
                  unique_train_programs=len({r["completion"] for r in records if r["kind"] == "program" and r["split"] == "train"}),
                  unique_dev_programs=len({r["completion"] for r in records if r["kind"] == "program" and r["split"] == "dev"}),
                  verifier_calls=len(episodes) * 2, full_nvarc_corpus=False)
    for name, value in (("records.json", records), ("manifest.json", manifest), ("receipts.json", receipts), ("report.json", report)):
        (out / name).write_bytes(canonical(value) + b"\n")
    return records, manifest, report


def merge_manifests(*manifests, protected_ids=()):
    """Union independently fixed splits; never reshuffle or weaken cross-source guards."""
    require(bool(manifests), "one or more manifests required")
    merged = {"format": FORMAT, "split_seed": "preserved-per-source", "dev_fraction": None,
              "source_identity": {"inputs": []}, "protected_ids": sorted(set(protected_ids)),
              "tasks": {}, "parents": {}, "components": [], "historical_dev_ids": [],
              "independence_limit": "declared ancestry/families/known variants only; no semantic independence proof"}
    for manifest in manifests:
        _validate_manifest(manifest, protected_ids)
        merged["protected_ids"] = sorted(set(merged["protected_ids"]) | set(manifest["protected_ids"]))
        merged["historical_dev_ids"] = sorted(set(merged["historical_dev_ids"]) | set((manifest.get("fixed_splits") or {}).get("dev", [])) | set(manifest.get("historical_dev_ids", [])))
        merged["source_identity"]["inputs"].append({"manifest_sha256": manifest["manifest_sha256"], "source_identity": manifest["source_identity"]})
        for field in ("tasks", "parents"):
            for key, value in manifest[field].items():
                require(key not in merged[field] or merged[field][key] == value, "inconsistent overlapping " + field)
                merged[field][key] = deepcopy(value)
        for component in manifest["components"]:
            if component not in merged["components"]:
                merged["components"].append(component[:])
    merged["manifest_sha256"] = digest(merged)
    _validate_manifest(merged, protected_ids)
    return merged


def _checked_failure(proof, *, demos):
    """Bind a semantic failure to the same real persisted verifier, without fitting it."""
    from . import program_tools
    require(type(proof) is dict and "proof_path" in proof, "persisted failed verification proof required")
    body = {k: v for k, v in proof.items() if k not in {"proof_path", "proof_sha256"}}
    require(proof.get("proof_sha256") == program_tools._hash(body) and
            Path(proof["proof_path"]).read_bytes() == program_tools._canonical(body) + b"\n", "failure proof binding differs")
    require(body.get("format") == program_tools.FORMAT and body.get("source_sha256") == hashlib.sha256(body["source"].encode()).hexdigest(), "failure source proof differs")
    require(body.get("demos") == demos and body["demo_task"]["demos"] == demos, "failure demos differ")
    receipt = body["receipt"]
    request = program_tools.legacy._validate_request(body["source"], body["demo_task"], program_tools.legacy.MAX_WALL_SECONDS, program_tools.legacy.MAX_STEPS)
    program_tools.legacy._validate_receipt({k: v for k, v in receipt.items() if k not in program_tools.TRANSPORT_KEYS}, request)
    require(receipt.get("known") is True and receipt.get("dispatched") is True and receipt.get("owned_descendants_stopped") is True and
            body["all_demos_fit"] is False and any(r.get("status") == "mismatch" for r in receipt.get("demos", [])), "actual closed semantic failure required")
    return body


def _validate_trajectory(record, entry):
    from .program_tools import _checked_proof
    provenance = record["provenance"]
    proof = _checked_proof(provenance["verification_proof"])
    require(proof["source"] == record["completion"] and
            digest({"train": proof["demos"]}) == entry["task_sha256"], "trajectory target/parent demos differ")
    context = provenance.get("generation_context")
    expected_demos = proof["demos"]
    if context is not None:
        visible, visible_proof = _generation_context(context, proof["demos"], record["completion"])
        expected_demos = visible["train"]
        require(provenance.get("generalization_claim") == "training-heldout-demo-not-prompted", "heldout claim differs")
    else:
        visible = provenance["prompt_task"]
        require(provenance.get("generalization_claim") is False and visible["train"] == expected_demos, "demo fit is not independent generalization")
    typed = None
    if record["kind"] == "repair":
        failure = _checked_failure(provenance.get("failure_proof"), demos=expected_demos)
        typed = _failure_feedback(failure)
    from .grid_codec import program_messages
    require(record["messages"] == program_messages(visible, feedback=typed), "trajectory prompt exposes or changes generation context")


def verified_program_record(task_id, task, source, proof, manifest, feedback=None, generation_context=None):
    """Compile a real train-parent all-demo-fit trajectory; never accept prose claims.

    proof is the full persisted return of program_tools.verify_program. Optional
    feedback is a persisted failed verify_program return with a semantic mismatch.
    Global/query evaluation parents are rejected, and query labels are forbidden.
    """
    from .grid_codec import program_messages, validate_task
    from .program_tools import _checked_proof
    _validate_manifest(manifest, ())
    entry = manifest["tasks"].get(task_id)
    require(entry is not None and entry["split"] == "train", "verified refinement requires original train parent")
    require(type(task) is dict and set(task) in ({"train"}, {"train", "test"}), "only solver-visible task allowed")
    demos = _demos({"train": task["train"]})
    require(digest({"train": demos}) == entry["task_sha256"], "trajectory training demonstrations changed")
    visible = deepcopy(task) if "test" in task else {"train": demos, "test": [{"input": demos[0]["input"]}]}
    validate_task(visible)
    verified = _checked_proof(proof)
    require(verified["source"] == source and verified["demos"] == demos, "verified source/demos differ")
    provenance = {"source_task_sha256": entry["task_sha256"], "objective": "execution-verified-train-trajectory",
                  "verification_proof": deepcopy(proof), "generalization_claim": False, "prompt_task": deepcopy(visible)}
    if generation_context is not None:
        visible, _ = _generation_context(generation_context, demos, source)
        provenance.update(generation_context=deepcopy(generation_context), prompt_task=deepcopy(visible),
                          generalization_claim="training-heldout-demo-not-prompted")
    typed = None
    if feedback is not None:
        failure = _checked_failure(feedback, demos=visible["train"])
        provenance["failure_proof"] = deepcopy(feedback)
        typed = _failure_feedback(failure)
    record = _seal_record({"task_id": task_id, "split": "train", "parent_ids": entry["parent_ids"][:],
        "family_id": entry["family_id"], "kind": "repair" if feedback is not None else "program",
        "messages": program_messages(visible, feedback=typed), "completion": source, "provenance": provenance})
    validate_records([record], manifest, ())
    return record


def _curriculum_module():
    root = Path(__file__).resolve().parents[1] / "arc_next_suite_20261009" / "src"
    sys.path.insert(0, str(root))
    try:
        import arc_curriculum
        require(Path(arc_curriculum.__file__).resolve() == root / "arc_curriculum.py", "unexpected authored generator module")
        return arc_curriculum
    finally:
        sys.path.remove(str(root))


def _authored_reference(provenance, entry):
    reference = provenance.get("authored_reference")
    require(type(reference) is dict and set(reference) == {"episode_index", "seed", "generator_sha256"}, "independent authored reference required")
    curriculum = _curriculum_module()
    require(hashlib.sha256(Path(curriculum.__file__).read_bytes()).hexdigest() == reference["generator_sha256"], "authored generator source changed")
    episode = curriculum.build_episode(reference["episode_index"], seed=reference["seed"])
    require("authored:" + episode["family"] == entry["family_id"] and episode["task"]["train"] == entry["demonstrations"], "authored reference family/demos differ")
    return episode


def _validate_grid_target(record, entry):
    from .grid_codec import grid_messages, encode_grid
    provenance = record["provenance"]
    if provenance.get("objective") == "demo-only-lodo":
        demos = entry["demonstrations"]
        held = provenance.get("held_out_demo")
        require(type(held) is int and 0 <= held < len(demos), "invalid LODO held-out index")
        spec = provenance.get("augmentation")
        require(type(spec) is dict and set(spec) <= {"rotation", "transpose", "colors", "demo_order"}, "invalid augmentation spec")
        order = spec.get("demo_order", list(range(len(demos))))
        require(sorted(order) == list(range(len(demos))), "invalid demonstration order")
        visible_indices = [i for i in order if i != held]
        require(provenance.get("visible_demo_indices") == visible_indices, "LODO target appears in visible demonstrations")
        visible = [{k: transform_grid(demos[i][k], spec) for k in ("input", "output")} for i in visible_indices]
        require(record["messages"] == grid_messages(visible, transform_grid(demos[held]["input"], spec)) and
                record["completion"] == encode_grid(transform_grid(demos[held]["output"], spec)), "LODO prompt/target does not match source demonstrations")
    else:
        episode = _authored_reference(provenance, entry)
        proof = provenance.get("verification", {})
        require(proof.get("witness_all_demo_fit") is True and proof.get("independent_query_exact") is True,
                "independently verified authored grid required")
        require(record["messages"] == grid_messages(episode["task"]["train"], episode["task"]["test"][0]["input"]) and
                record["completion"] == encode_grid(episode["query_target"]), "authored grid differs from independent formula")


def _failure_feedback(failure):
    return {"source": failure["source"], "program_sha256": failure["source_sha256"],
            "demo_results": failure["receipt"]["demos"], "errors": failure["errors"],
            "partial_score": failure["partial_score"]["exact_fraction"]}


def _generation_context(context, demos, source):
    from .program_tools import _checked_proof
    require(type(context) is dict and set(context) == {"visible_indices", "held_out_demo_index", "visible_verification_proof"}, "exact withheld-demo generation context required")
    held = context["held_out_demo_index"]
    require(type(held) is int and 0 <= held < len(demos) and len(demos) >= 2, "invalid held-out training demonstration")
    visible_indices = [i for i in range(len(demos)) if i != held]
    require(context["visible_indices"] == visible_indices, "held-out output must never be visible for generation")
    visible = {"train": [deepcopy(demos[i]) for i in visible_indices], "test": [{"input": deepcopy(demos[held]["input"])}]}
    proof = _checked_proof(context["visible_verification_proof"])
    require(proof["source"] == source and proof["demos"] == visible["train"], "visible proof must bind same source and reduced demos")
    return visible, proof
