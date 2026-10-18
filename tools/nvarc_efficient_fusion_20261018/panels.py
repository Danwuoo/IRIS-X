"""Torch-free, source-bound panels for the compact efficient-fusion experiment.

Only original training demonstrations enter these panels. PUBLIC projections
are answer-free exclusion inputs; original training-file test fields are never
used. The historical selectors below intentionally reproduce their frozen ID
ordering without importing their Torch-dependent experiment modules.

``validate_prepared`` treats source_binding as independently trusted evidence.
It detects re-sealed panel/protocol substitutions against that evidence; it is
not a signature on an arbitrary replacement source_binding. The controller must
independently call prepare_panels on pinned source bytes and compare its result
before model work. Known variants are syntactic, not semantic family proofs,
and none of these panels establishes cleanliness of inherited model weights.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re

from src.irisx.arc_nvarc_data import known_variant_group
from tools.arc2_goal_sprint_20261017.data import canonical, digest, valid_grid
from tools.arc2_goal_sprint_20261017.launch import TRAINING_MANIFEST_SHA256, regular, require


PROTOCOL = "compact-efficient-fusion-v1"
FORMAT = "irisx/compact-efficient-fusion-panel-v1"
ADMISSION_FORMAT = FORMAT
PROBABILITY_POLICY = "fp32-backbone-math-v1"
TRAIN_COUNT = 64
DEV_COUNT = 96
HISTORICAL_COUNT = 24
STABILITY_COUNT = 32
MATCHED_COUNT = 16


def sha(value):
    """SHA256 of canonical JSON, without the digest() 'sha256:' prefix."""
    return hashlib.sha256(canonical(value)).hexdigest()


def _is_sha(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _id(value):
    # Source IDs are also filenames. No separators, traversal or implicit paths.
    return (type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is not None)


def _schema(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), "strict " + label + " schema required")


def _ids(value, *, count=None, label="parent IDs"):
    require(type(value) is list and all(_id(p) for p in value) and len(value) == len(set(value))
            and (count is None or len(value) == count), "distinct bounded " + label + " required")


def validate_task(task, *, selected=True):
    """Validate a demonstration-only task; selected panels require held-demo independence."""
    _schema(task, ("train",), "train-only task")
    pairs = task["train"]
    require(type(pairs) is list and 1 <= len(pairs) <= 1000, "bounded original demonstrations required")
    for pair in pairs:
        _schema(pair, ("input", "output"), "demonstration")
        require(all(valid_grid(grid) for grid in pair.values()), "valid training grids required")
    if selected:
        require(2 <= len(pairs) <= 32, "two to32 training demonstrations required")
        require(_metadata(task)["independent_held_input"], "independent held-demo input required")
    return task


def _metadata(task):
    pairs = task["train"]
    return {"pair_count": len(pairs), "independent_held_input":
            all(pair["input"] != pairs[0]["input"] for pair in pairs[1:])}


def _groups(tasks):
    cache, result = {}, {}
    for parent, task in sorted(tasks.items()):
        key = sha({"train": task["train"]})
        if key not in cache:
            cache[key] = known_variant_group({"train": task["train"], "test": []})
        result[parent] = cache[key]
    return result


def _ordered(ids, salt):
    return sorted(ids, key=lambda parent: (hashlib.sha256((salt + parent).encode()).hexdigest(), parent))


def _eligible(metadata, *, upper=32):
    return metadata["pair_count"] >= 2 and (upper is None or metadata["pair_count"] <= upper) \
        and metadata["independent_held_input"]


def _pick(ids, groups, metadata, salt, count, excluded=(), *, upper=32):
    unavailable, chosen = set(excluded), []
    for parent in _ordered(ids, salt):
        if groups[parent] in unavailable or not _eligible(metadata[parent], upper=upper):
            continue
        chosen.append(parent)
        unavailable.add(groups[parent])
        if len(chosen) == count:
            return chosen
    raise ValueError("insufficient independent known-variant groups for fixed " + salt + " panel")


def _selection(binding, train_count, dev_count):
    """Reconstruct all exclusions and availability, never reading model results."""
    partitions = binding["split"]["partition_ids"]
    groups = binding["family_lineage"]["groups"]
    metadata = binding["source"]["demonstration_metadata"]
    previous = _ordered(partitions["dev"], "nvarc-dev-v1:")[:HISTORICAL_COUNT]
    unavailable = {groups["dev"][parent] for parent in previous}
    stability = _pick(partitions["dev"], groups["dev"], metadata,
                      "compact-paired-ttt-stability-v1:", STABILITY_COUNT, unavailable, upper=None)
    unavailable.update(groups["dev"][parent] for parent in stability)
    matched = _pick(partitions["dev"], groups["dev"], metadata,
                    "compact-matched-controls-v1:dev:", MATCHED_COUNT, unavailable)
    unavailable.update(groups["dev"][parent] for parent in matched)
    train_ids = _pick(partitions["train"], groups["train"], metadata,
                      PROTOCOL + ":train:", train_count)
    dev_ids = _pick(partitions["dev"], groups["dev"], metadata,
                    PROTOCOL + ":dev:", dev_count, unavailable)
    eligible = {name: [p for p in partitions[name] if _eligible(metadata[p])
                      and (name != "dev" or groups[name][p] not in unavailable)]
                for name in ("train", "dev")}
    return {"training_parent_ids": train_ids, "development_parent_ids": dev_ids,
            "excluded_previous_panel": previous, "excluded_stability_panel": stability,
            "excluded_matched_panel": matched,
            "excluded_development_variant_groups": sorted(unavailable),
            "exposed_development_parents": len(set(previous + stability + matched)),
            "exposed_development_variant_groups": len(unavailable),
            "available_training_parents": len(eligible["train"]),
            "available_training_variant_groups": len({groups["train"][p] for p in eligible["train"]}),
            "available_development_parents": len(eligible["dev"]),
            "available_development_variant_groups": len({groups["dev"][p] for p in eligible["dev"]})}


def _lineage(groups):
    return {"kind": "syntactic-known-D4-color-demo-shuffle-strata-v1",
            "true_generator_lineage_available": False, "semantic_family_independence_claimed": False,
            "groups": groups,
            "family_definition": "known-variant:<demonstration-only known_variant_group sha256>",
            "priority_interpretation": "one parent per selected syntactic group; no difficulty-based selection"}


def _admission(binding, selection):
    groups = binding["family_lineage"]["groups"]
    excluded_groups = sorted(set(groups["dev"].values()) | set(groups["public"].values()))
    return {"format": ADMISSION_FORMAT, "source_sha256": sha(binding["source"]),
            "split_sha256": sha(binding["split"]), "family_lineage_sha256": sha(binding["family_lineage"]),
            "parents": [{"parent_id": parent,
                         "task_sha256": binding["source"]["demonstration_sha256"][parent],
                         "variant_group": groups["train"][parent],
                         "family_id": "known-variant:" + groups["train"][parent], "held_index": 0}
                        for parent in selection["training_parent_ids"]],
            "excluded": {"parent_ids": sorted(set(binding["split"]["partition_ids"]["dev"])
                                               | set(binding["split"]["protected_ids"])
                                               | set(binding["split"]["partition_ids"]["public"])),
                         "variant_groups": excluded_groups,
                         "family_ids": ["known-variant:" + group for group in excluded_groups]}}


def _protocol(binding, selection, admission, development, train_count, dev_count):
    ids = selection["development_parent_ids"]
    return {"version": PROTOCOL, "probability_policy": PROBABILITY_POLICY,
            "train_count": train_count, "dev_count": dev_count, **selection,
            "development_task_sha256": {p: sha(development[p]) for p in ids},
            "development_target_digest": {p: digest(development[p]["train"][0]["output"]) for p in ids},
            "development_variant_groups": {p: binding["family_lineage"]["groups"]["dev"][p] for p in ids},
            "admission_sha256": sha(admission), "source_sha256": sha(binding["source"]),
            "split_sha256": sha(binding["split"]), "family_lineage_sha256": sha(binding["family_lineage"]),
            "held_demo_index": 0,
            "prior_panel_policy": "historical24+stability32+matched/convergence16",
            "panel_selection": "deterministic-id-hash-after-syntactic-exclusions-v1",
            "performance_or_difficulty_selection_used": False,
            "training_test_fields_used": False, "public_feedback_used": False,
            "initial_weight_cleanliness_claimed": False,
            "scientific_scope": "train-derived held-demo comparison; inherited exposure qualified; "
                                "known variants are syntactic only, not semantic independence"}


def _counts(train_count, dev_count, manifest_sha):
    require(type(train_count) is int and 1 <= train_count <= TRAIN_COUNT
            and type(dev_count) is int and 1 <= dev_count <= DEV_COUNT,
            "bounded prespecified64/96 panels required")
    if manifest_sha == TRAINING_MANIFEST_SHA256:
        require((train_count, dev_count) == (TRAIN_COUNT, DEV_COUNT),
                "official source requires fixed64 training and fixed96 development parents")


def prepare_panels(training, development, public, split, *, training_root, training_manifest_path,
                   expected_training_manifest_sha256=TRAINING_MANIFEST_SHA256,
                   train_count=TRAIN_COUNT, dev_count=DEV_COUNT):
    """Reread exact source bytes, freeze exclusion-only panels before model work.

    The injectable source pin and smaller counts support synthetic offline
    fixtures, never smaller production denominators. No original test field or
    protected answer is accessed, retained in the binding or used for selection.
    """
    require(_is_sha(expected_training_manifest_sha256), "independently pinned training source required")
    _counts(train_count, dev_count, expected_training_manifest_sha256)
    body = regular(training_manifest_path).read_bytes()
    require(hashlib.sha256(body).hexdigest() == expected_training_manifest_sha256
            == split.get("training_manifest_sha256"), "independently pinned training source required")
    manifest = json.loads(body)
    fixed = manifest["upstream"]["fixed_splits"]
    _schema(fixed, ("train", "dev"), "historical split")
    for name, data, count in (("train", training, 800), ("dev", development, 200), ("public", public, 120)):
        require(type(data) is dict and len(data) == count and all(_id(p) for p in data),
                "original admitted800/200 and solver120/167 partitions required")
        if name != "public":
            _ids(fixed[name], count=count, label="fixed " + name + " IDs")
            require(set(data) == set(fixed[name]), "unchanged historical800/200 train/dev partition required")
    require(set(training).isdisjoint(development) and set(training).isdisjoint(public)
            and set(development).isdisjoint(public), "train/dev/PUBLIC parent overlap forbidden")
    for task in public.values():
        _schema(task, ("train", "test"), "answer-free PUBLIC projection")
        validate_task({"train": task["train"]}, selected=False)
        require(type(task["test"]) is list and task["test"]
                and all(type(q) is dict and set(q) == {"input"} and valid_grid(q["input"])
                        for q in task["test"]), "PUBLIC projection must remain answer-free and exclusion-only")
    require(sum(len(t["test"]) for t in public.values()) == 167, "complete solver120/167 partition required")
    require(split.get("training_test_fields_used") is False and split.get("training_tasks") == 800
            and split.get("dev_tasks") == 200 and split.get("excluded_task_ids") == []
            and split.get("train_ids_digest") == digest(sorted(training))
            and split.get("dev_ids_digest") == digest(sorted(development))
            and split.get("public_digest") == digest(public), "admitted split receipt differs")
    protected = manifest.get("protected_ids", [])
    _ids(protected, label="protected IDs")
    tasks = {**training, **development}
    require(set(tasks).isdisjoint(protected), "protected parent leaked into training/development")
    root = Path(training_root)
    expected_names = {"data/training/" + p + ".json" for p in tasks}
    actual_names = {name for name in manifest["files"] if name.startswith("data/training/") and name.endswith(".json")}
    require(actual_names == expected_names and {p.stem for p in root.glob("*.json")} == set(tasks),
            "exact admitted1000 training file inventory required")
    files, demo_hashes, metadata = {}, {}, {}
    for parent, task in sorted(tasks.items()):
        validate_task(task, selected=False)
        name = "data/training/" + parent + ".json"
        row = manifest["files"][name]
        raw = regular(root / (parent + ".json")).read_bytes()
        require(type(row["bytes"]) is int and len(raw) == row["bytes"]
                and hashlib.sha256(raw).hexdigest() == row["sha256"], "source training bytes differ")
        require(json.loads(raw)["train"] == task["train"], "admitted demonstration mapping differs from source")
        files[name] = {"bytes": len(raw), "sha256": row["sha256"]}
        demo_hashes[parent], metadata[parent] = sha(task), _metadata(task)
    groups = {name: _groups(data) for name, data in (("train", training), ("dev", development), ("public", public))}
    source = {"training_manifest_sha256": expected_training_manifest_sha256, "files": files,
              "demonstration_sha256": demo_hashes, "demonstration_metadata": metadata}
    split_binding = {"receipt": copy.deepcopy(split), "fixed_splits": copy.deepcopy(fixed),
                     "partition_ids": {name: sorted(data) for name, data in
                                       (("train", training), ("dev", development), ("public", public))},
                     "protected_ids": sorted(protected), "known_variant_partition_sha256": sha(groups),
                     "public_use": "input/demonstration exclusion only"}
    binding = {"source": source, "split": split_binding, "family_lineage": _lineage(groups)}
    _validate_binding(binding)
    selection = _selection(binding, train_count, dev_count)
    admission = _admission(binding, selection)
    protocol = _protocol(binding, selection, admission, development, train_count, dev_count)
    prepared = {"training": {p: copy.deepcopy(training[p]) for p in selection["training_parent_ids"]},
                "development": {p: copy.deepcopy(development[p]) for p in selection["development_parent_ids"]},
                "admission": admission, "protocol": protocol, "source_binding": binding,
                "pins": {"admission_sha256": sha(admission), "protocol_sha256": sha(protocol),
                         "source_binding_sha256": sha(binding)}}
    validate_prepared(prepared)
    return prepared


def _validate_binding(binding):
    _schema(binding, ("source", "split", "family_lineage"), "source binding")
    source, split, lineage = (binding[k] for k in ("source", "split", "family_lineage"))
    _schema(source, ("training_manifest_sha256", "files", "demonstration_sha256", "demonstration_metadata"), "source")
    require(_is_sha(source["training_manifest_sha256"]), "source manifest SHA required")
    _schema(split, ("receipt", "fixed_splits", "partition_ids", "protected_ids",
                    "known_variant_partition_sha256", "public_use"), "split binding")
    _schema(split["partition_ids"], ("train", "dev", "public"), "partitions")
    _schema(split["fixed_splits"], ("train", "dev"), "historical split")
    partitions = split["partition_ids"]
    for name, count in (("train", 800), ("dev", 200), ("public", 120)):
        _ids(partitions[name], count=count, label=name + " partition IDs")
        require(partitions[name] == sorted(partitions[name]), "sorted source partition IDs required")
        if name != "public":
            _ids(split["fixed_splits"][name], count=count, label="historical " + name + " IDs")
            require(set(split["fixed_splits"][name]) == set(partitions[name]), "source partition membership differs")
    _ids(split["protected_ids"], label="protected IDs")
    train, dev, public = (set(partitions[n]) for n in ("train", "dev", "public"))
    require(train.isdisjoint(dev) and train.isdisjoint(public) and dev.isdisjoint(public)
            and (train | dev).isdisjoint(split["protected_ids"]), "protected/source partition overlap forbidden")
    receipt = split["receipt"]
    require(type(receipt) is dict and receipt.get("training_manifest_sha256") == source["training_manifest_sha256"]
            and receipt.get("training_tasks") == 800 and receipt.get("dev_tasks") == 200
            and receipt.get("excluded_task_ids") == [] and receipt.get("training_test_fields_used") is False
            and receipt.get("train_ids_digest") == digest(sorted(train))
            and receipt.get("dev_ids_digest") == digest(sorted(dev))
            and type(receipt.get("public_digest")) is str and receipt["public_digest"].startswith("sha256:")
            and _is_sha(receipt["public_digest"][7:])
            and split["public_use"] == "input/demonstration exclusion only", "bound source split receipt differs")
    tasks = train | dev
    require(type(source["files"]) is dict
            and set(source["files"]) == {"data/training/" + p + ".json" for p in tasks},
            "exact source file inventory required")
    for row in source["files"].values():
        _schema(row, ("bytes", "sha256"), "source file")
        require(type(row["bytes"]) is int and row["bytes"] > 0 and _is_sha(row["sha256"]), "valid source file pin required")
    require(type(source["demonstration_sha256"]) is dict and set(source["demonstration_sha256"]) == tasks
            and all(_is_sha(value) for value in source["demonstration_sha256"].values()),
            "complete source demonstration hash binding required")
    require(type(source["demonstration_metadata"]) is dict and set(source["demonstration_metadata"]) == tasks,
            "complete source demonstration metadata required")
    for row in source["demonstration_metadata"].values():
        _schema(row, ("pair_count", "independent_held_input"), "demonstration metadata")
        require(type(row["pair_count"]) is int and 1 <= row["pair_count"] <= 1000
                and type(row["independent_held_input"]) is bool, "bounded source demonstration metadata required")
    require(type(lineage) is dict and "groups" in lineage and lineage == _lineage(lineage["groups"]),
            "syntactic-only exposure-qualified family lineage required")
    groups = lineage["groups"]
    _schema(groups, ("train", "dev", "public"), "variant partitions")
    for name in partitions:
        require(type(groups[name]) is dict and set(groups[name]) == set(partitions[name])
                and all(_is_sha(value) for value in groups[name].values()), "complete source variant binding required")
    sets = {name: set(values.values()) for name, values in groups.items()}
    require(sets["train"].isdisjoint(sets["dev"]) and sets["train"].isdisjoint(sets["public"])
            and sets["dev"].isdisjoint(sets["public"]), "known-variant overlap across partitions forbidden")
    require(split["known_variant_partition_sha256"] == sha(groups), "source variant partition digest differs")


def validate_prepared(prepared):
    """Pure validation against the controller's independently trusted source_binding."""
    _schema(prepared, ("training", "development", "admission", "protocol", "source_binding", "pins"), "prepared panels")
    admission, protocol, binding, pins = (prepared[k] for k in ("admission", "protocol", "source_binding", "pins"))
    require(pins == {"admission_sha256": sha(admission), "protocol_sha256": sha(protocol),
                     "source_binding_sha256": sha(binding)}, "pinned panel payload changed before model work")
    _validate_binding(binding)
    require(type(protocol) is dict, "fixed panel protocol required")
    train_count, dev_count = protocol.get("train_count"), protocol.get("dev_count")
    _counts(train_count, dev_count, binding["source"]["training_manifest_sha256"])
    selection = _selection(binding, train_count, dev_count)
    for name, partition, count, key in (("training", "train", train_count, "training_parent_ids"),
                                        ("development", "dev", dev_count, "development_parent_ids")):
        tasks = prepared[name]
        require(type(tasks) is dict and len(tasks) == count and set(tasks) == set(selection[key]),
                "exact source-derived fixed " + name + " panel required")
        for parent, task in tasks.items():
            validate_task(task)
            require(sha(task) == binding["source"]["demonstration_sha256"][parent]
                    and _metadata(task) == binding["source"]["demonstration_metadata"][parent],
                    "selected task differs from trusted source demonstrations")
            variant = known_variant_group({"train": task["train"], "test": []})
            require(variant == binding["family_lineage"]["groups"][partition][parent],
                    "selected known-variant lineage differs from trusted source")
    expected_admission = _admission(binding, selection)
    require(admission == expected_admission, "source-derived training admission or exclusions differ")
    expected_protocol = _protocol(binding, selection, expected_admission, prepared["development"], train_count, dev_count)
    require(protocol == expected_protocol, "source-derived fixed panel protocol differs")
    return prepared
