"""ARC task isolation, reversible augmentation, and offline SDG replay.

This module never opens answer files. Callers supply labelled examples only to
the training-data path; solver tasks contain demonstrations and test inputs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import sqlite3
from collections import Counter
from typing import Any, Iterable, Mapping

from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


def grid(value: Any) -> list[list[int]]:
    if (not isinstance(value, list) or not 1 <= len(value) <= 30 or
            any(not isinstance(row, list) or not 1 <= len(row) <= 30 for row in value)):
        raise ValidationError("grid dimensions must be 1..30")
    width = len(value[0])
    if any(len(row) != width for row in value):
        raise ValidationError("grid must be rectangular")
    if any(type(cell) is not int or not 0 <= cell <= 9 for row in value for cell in row):
        raise ValidationError("grid cells must be integer colors 0..9")
    return [row[:] for row in value]


def visible_task(task_id: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(task_id, str) or not task_id:
        raise ValidationError("task_id is required")
    train, tests = raw.get("train"), raw.get("test")
    if not isinstance(train, list) or not train or not isinstance(tests, list) or not tests:
        raise ValidationError("task needs demonstrations and test inputs")
    try:
        return {"task_id": task_id,
                "train": [{"input": grid(p["input"]), "output": grid(p["output"])} for p in train],
                "test": [{"input": grid(p["input"])} for p in tests]}
    except (KeyError, TypeError) as exc:
        raise ValidationError("task pair is missing an input or demonstration output") from exc


def selected_view(task: Mapping[str, Any], test_index: int) -> dict[str, Any]:
    if type(test_index) is not int or not 0 <= test_index < len(task["test"]):
        raise ValidationError("test_index outside full task")
    return {"task_id": task["task_id"], "train": task["train"],
            "test": [task["test"][test_index]], "source_test_index": test_index}


def source_sdg_messages(pairs: list[Mapping[str, Any]], *, seed: int,
                        augment: bool) -> dict[str, Any]:
    """Execute pinned NVARC SDG augmentation/formatter on labelled pairs.

    The original SDG function uses Python's global RNG. Save and restore it so
    this source-compatible data path cannot perturb another trial stage.
    """
    from .arc_nvarc_upstream import sdg_build_datasets

    source = sdg_build_datasets()
    cleaned = [{"input": grid(pair["input"]), "output": grid(pair["output"])}
               for pair in pairs]
    if not cleaned:
        raise ValidationError("source SDG message builder needs labelled pairs")
    state = random.getstate()
    try:
        random.seed(seed)
        rules = source.fix_settings(["dihedral", "color"]) if augment else []
        transformed = source.apply_augmentation(cleaned, rules)
        messages = source.get_messages(transformed, do_augmentation=False)
    finally:
        random.setstate(state)
    return {"messages": messages, "rules": rules,
            "source": "NVARC/SDG/scripts/build_datasets.py:get_messages"}


def compare_visible(full: Mapping[str, Any], mounted: Mapping[str, Any]) -> bool:
    """Compare full tasks; selected execution views are never accepted here."""
    return (full["task_id"] == mounted["task_id"] and
            full["train"] == mounted["train"] and full["test"] == mounted["test"])


def transform_grid(value: Any, spec: Mapping[str, Any], *, inverse: bool = False) -> list[list[int]]:
    rows = grid(value)
    rotation = spec.get("rotation", 0)
    transpose = spec.get("transpose", False)
    permutation = spec.get("colors", list(range(10)))
    if rotation not in (0, 1, 2, 3) or type(transpose) is not bool or sorted(permutation) != list(range(10)):
        raise ValidationError("invalid dihedral/color transform")

    def turn(a: list[list[int]]) -> list[list[int]]:
        return [list(row) for row in zip(*a)][::-1]

    if inverse:
        inverse_colors = [0] * 10
        for old, new in enumerate(permutation):
            inverse_colors[new] = old
        rows = [[inverse_colors[cell] for cell in row] for row in rows]
        for _ in range((-rotation) % 4):
            rows = turn(rows)
        if transpose:
            rows = [list(row) for row in zip(*rows)]
    else:
        if transpose:
            rows = [list(row) for row in zip(*rows)]
        for _ in range(rotation):
            rows = turn(rows)
        rows = [[permutation[cell] for cell in row] for row in rows]
    return grid(rows)


def transform_task(task: Mapping[str, Any], spec: Mapping[str, Any]) -> dict[str, Any]:
    train = [{key: transform_grid(pair[key], spec) for key in ("input", "output")}
             for pair in task["train"]]
    order = spec.get("demo_order", list(range(len(train))))
    if sorted(order) != list(range(len(train))):
        raise ValidationError("invalid demonstration order")
    return {"task_id": task["task_id"], "train": [train[i] for i in order],
            "test": [{"input": transform_grid(item["input"], spec)} for item in task["test"]],
            "transform": dict(spec)}


def source_qwen_transform_grid(value: Any, spec: Mapping[str, Any], *,
                               inverse: bool = False) -> list[list[int]]:
    """Use the pinned notebook's ArcDataset D4/color operations directly."""
    import numpy as np
    from .arc_nvarc_upstream import qwen_cell

    source_key = spec.get("source_key")
    if source_key is not None:
        if not isinstance(source_key, str) or not source_key.startswith("view."):
            raise ValidationError("invalid source Qwen view key")
        cls = qwen_cell("arc_loader.py").ArcDataset
        array = np.array(grid(value), dtype=np.uint8)
        result = (cls.invert_mod(array, source_key, inv_perm=True) if inverse else
                  cls.forward_mod(array, source_key, use_perm=True))
        return grid(result.tolist())
    rotation = spec.get("rotation", 0)
    transpose = spec.get("transpose", False)
    colors = spec.get("colors", list(range(10)))
    if rotation not in (0, 1, 2, 3) or type(transpose) is not bool or sorted(colors) != list(range(10)):
        raise ValidationError("invalid source Qwen transform")
    key = "view" + (".transpose" if transpose else "") + ".rot90" * rotation
    key += ".permute" + "".join(str(color) for color in colors)
    cls = qwen_cell("arc_loader.py").ArcDataset
    array = np.array(grid(value), dtype=np.uint8)
    result = cls.invert_mod(array, key, inv_perm=True) if inverse else cls.forward_mod(array, key, use_perm=True)
    return grid(result.tolist())


def source_qwen_views(task: Mapping[str, Any], test_index: int, *,
                      seed: int, color_repeats: int,
                      answer: Any | None = None) -> list[dict[str, Any]]:
    """Run pinned ArcDataset.augment and keep its exact transformed examples.

    One source dataset is constructed per test; this preserves a full multi-test
    task while never adding answers from other tests to the solver view.
    """
    import numpy as np
    from .arc_nvarc_upstream import qwen_cell

    if not 0 <= test_index < len(task["test"]) or color_repeats not in (1, 2):
        raise ValidationError("source Qwen view bounds differ")
    cls = qwen_cell("arc_loader.py").ArcDataset
    query = {"train": task["train"], "test": [task["test"][test_index]]}
    replies = {"view": [grid(answer)]} if answer is not None else {}
    source = cls(queries={"view": query}, replies=replies, keys=["view"])
    state = np.random.get_state()
    try:
        augmented = source.augment(n=color_repeats, seed=seed)
    finally:
        np.random.set_state(state)
    keys = sorted(augmented.keys)
    if color_repeats == 2:
        # Notebook cell4: four two-key DFS batches for each transpose half.
        indices = [0, 4, 2, 6, 8, 12, 10, 14]
        keys = [keys[i + j] for i in indices for j in range(2)]
    views = []
    for key in keys:
        item = augmented.queries[key]
        transformed = {"task_id": task["task_id"], "train": item["train"],
                       "test": item["test"], "transform": {"source_key": key}}
        views.append({"spec": {"source_key": key}, "task": transformed,
                      "answer": augmented.replies[key][0] if answer is not None else None})
    return views


def source_qwen_training_views(task: Mapping[str, Any], *, seed: int,
                               color_repeats: int) -> list[dict[str, Any]]:
    """Use notebook train_ds.augment(n, shfl_keys=True) without test labels."""
    import numpy as np
    from .arc_nvarc_upstream import qwen_cell

    if not 1 <= color_repeats <= 16 or not task["train"]:
        raise ValidationError("source Qwen adaptation view bound differs")
    cls = qwen_cell("arc_loader.py").ArcDataset
    source = cls(queries={"view": {"train": task["train"], "test": task["test"]}},
                 keys=["view"])
    state = np.random.get_state()
    try:
        augmented = source.augment(n=color_repeats, shfl_keys=True, seed=seed)
    finally:
        np.random.set_state(state)
    return [{"key": key, "train": augmented.queries[key]["train"]}
            for key in augmented.keys]


def source_qwen_transform_task(task: Mapping[str, Any], spec: Mapping[str, Any]) -> dict[str, Any]:
    train = [{key: source_qwen_transform_grid(pair[key], spec) for key in ("input", "output")}
             for pair in task["train"]]
    order = spec.get("demo_order", list(range(len(train))))
    if sorted(order) != list(range(len(train))):
        raise ValidationError("invalid source Qwen demonstration order")
    return {"task_id": task["task_id"], "train": [train[i] for i in order],
            "test": [{"input": source_qwen_transform_grid(item["input"], spec)}
                     for item in task["test"]], "transform": dict(spec)}


def seeded_transform(task: Mapping[str, Any], seed: int, index: int) -> dict[str, Any]:
    rng = random.Random(f"{seed}:{task['task_id']}:{index}")
    colors = list(range(10))
    rng.shuffle(colors)
    order = list(range(len(task["train"])))
    rng.shuffle(order)
    return {"rotation": rng.randrange(4), "transpose": bool(rng.randrange(2)),
            "colors": colors, "demo_order": order}


def known_variant_group(task: Mapping[str, Any]) -> str:
    """Known D4/color-renaming/demo-shuffle signature of visible grids.

    This detects a useful overlap class. It is not a proof of semantic
    independence between data sources.
    """
    signatures = []
    for transpose in (False, True):
        for rotation in range(4):
            spec = {"transpose": transpose, "rotation": rotation, "colors": list(range(10))}
            pairs = [{key: transform_grid(item[key], spec) for key in ("input", "output")}
                     for item in task["train"]]

            def local_pattern(pair: Mapping[str, Any]) -> str:
                colors: dict[int, int] = {}
                return "".join(str(colors.setdefault(cell, len(colors))) for key in ("input", "output")
                               for row in pair[key] for cell in row)

            pairs.sort(key=lambda pair: (len(pair["input"]), len(pair["input"][0]),
                                         len(pair["output"]), len(pair["output"][0]), local_pattern(pair)))
            tests = [transform_grid(item["input"], spec) for item in task["test"]]
            colors: dict[int, int] = {}

            def normalize(value: list[list[int]]) -> list[list[int]]:
                return [[colors.setdefault(cell, len(colors)) for cell in row] for row in value]

            normalized = {"train": [{"input": normalize(pair["input"]),
                                      "output": normalize(pair["output"])} for pair in pairs],
                          "test": [normalize(value) for value in tests]}
            signatures.append(canonical_bytes(normalized))
    return hashlib.sha256(min(signatures)).hexdigest()


def stream_import_jsonl(path: Path, *, split: str,
                        forbidden_parent_ids: Iterable[str] = ()) -> Iterable[dict[str, Any]]:
    """Validate one source record at a time; no source corpus is loaded whole."""
    forbidden = set(forbidden_parent_ids)
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            try:
                task_id, parent, source_id = raw["task_id"], raw["parent_id"], raw["source_id"]
            except (KeyError, TypeError) as exc:
                raise ValidationError(f"source identity missing at line {line_number}") from exc
            if any(not isinstance(value, str) or not value for value in (task_id, parent, source_id)):
                raise ValidationError(f"source identity invalid at line {line_number}")
            if parent in forbidden:
                raise ValidationError(f"forbidden lineage at line {line_number}")
            visible = visible_task(task_id, raw)
            record = {**visible, "parent_id": parent, "source_id": source_id,
                      "split": split, "visible_digest": digest_value(visible)}
            if split.startswith("sft-") and all("output" in item for item in raw["test"]):
                # Training-data artifacts may carry labels; solver-visible
                # workload construction always strips them via visible_task.
                record["labelled_test"] = [{"input": grid(item["input"]), "output": grid(item["output"])}
                                           for item in raw["test"]]
            yield record


def import_jsonl(path: Path, *, split: str, forbidden_parent_ids: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Small-dataset convenience wrapper; full datasets use the stream path."""
    records = list(stream_import_jsonl(path, split=split,
                                       forbidden_parent_ids=forbidden_parent_ids))
    if len({record["task_id"] for record in records}) != len(records):
        raise ValidationError("source JSONL contains duplicate task IDs")
    return records


def freeze_streaming(records: Iterable[Mapping[str, Any]], output: Path, *,
                     policy: str, forbidden_parent_ids: Iterable[str] = (),
                     shard_size: int = 8192) -> dict[str, Any]:
    """Disk-backed deterministic freeze for multi-million-sample corpora."""
    if policy not in {"clean-research", "competition-reproduction"} or shard_size < 1:
        raise ValidationError("invalid data policy or shard size")
    if output.exists() and any(output.iterdir()):
        raise ValidationError("frozen stream output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    excluded = set(forbidden_parent_ids)
    known_evaluation_sources = {"arc2_evaluation6"}
    database = output / ".freeze-index.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE records (task_id TEXT PRIMARY KEY, source_id TEXT, parent_id TEXT, split TEXT, payload BLOB)")
        connection.execute("CREATE TABLE parents (parent_id TEXT PRIMARY KEY, split TEXT)")
        connection.execute("CREATE TABLE variants (variant_id TEXT PRIMARY KEY, split TEXT)")
        count = 0
        for record in records:
            parent, split = record["parent_id"], record["split"]
            if policy == "clean-research" and parent in excluded:
                raise ValidationError("clean stream contains a known excluded parent")
            if policy == "clean-research" and record["source_id"] in known_evaluation_sources:
                raise ValidationError("clean stream contains a known evaluation source")
            variant = known_variant_group(record)
            for table, key_name, key in (("parents", "parent_id", parent),
                                         ("variants", "variant_id", variant)):
                prior = connection.execute(f"SELECT split FROM {table} WHERE {key_name}=?", (key,)).fetchone()
                if prior and prior[0] != split:
                    raise ValidationError("known parent or transformed puzzle crosses splits")
                connection.execute(f"INSERT OR IGNORE INTO {table} VALUES (?, ?)", (key, split))
            try:
                connection.execute("INSERT INTO records VALUES (?, ?, ?, ?, ?)",
                                   (record["task_id"], record["source_id"], parent, split,
                                    canonical_bytes(dict(record), newline=True)))
            except sqlite3.IntegrityError as exc:
                raise ValidationError("frozen stream has duplicate task ID") from exc
            count += 1
        connection.commit()
        if count == 0:
            raise ValidationError("cannot freeze an empty source stream")
        shards = []
        cursor = connection.execute("SELECT payload FROM records ORDER BY source_id, parent_id, task_id")
        index = 0
        while True:
            batch = cursor.fetchmany(shard_size)
            if not batch:
                break
            name = f"shard-{index:05d}.jsonl"
            payload = b"".join(row[0] for row in batch)
            (output / name).write_bytes(payload)
            shards.append({"path": name, "sha256": hashlib.sha256(payload).hexdigest(),
                           "records": len(batch)})
            index += 1
        groups = connection.execute("SELECT COUNT(*) FROM variants").fetchone()[0]
        source_counts = {source: amount for source, amount in
                         connection.execute("SELECT source_id, COUNT(*) FROM records GROUP BY source_id ORDER BY source_id")}
    finally:
        connection.close()
        database.unlink(missing_ok=True)
    manifest = {"format": "irisx/nvarc-data-freeze", "policy": policy,
                "record_count": count, "shards": shards,
                "known_excluded_parent_count": len(excluded),
                "known_variant_group_count": groups,
                "source_counts": source_counts,
                "exposure": "unproven" if policy == "clean-research" else "competition-reproduction-contamination-possible"}
    (output / "manifest.json").write_bytes(canonical_bytes(manifest, newline=True))
    return manifest


def freeze_shards(records: Iterable[Mapping[str, Any]], output: Path, *,
                  policy: str, forbidden_parent_ids: Iterable[str] = (), shard_size: int = 128) -> dict[str, Any]:
    if policy not in {"clean-research", "competition-reproduction"} or shard_size < 1:
        raise ValidationError("invalid data policy or shard size")
    forbidden = set(forbidden_parent_ids)
    ordered = sorted(records, key=lambda r: (r["source_id"], r["parent_id"], r["task_id"]))
    if policy == "clean-research" and any(r["parent_id"] in forbidden for r in ordered):
        raise ValidationError("clean split contains a known excluded parent")
    if policy == "clean-research" and any(r["source_id"] == "arc2_evaluation6" for r in ordered):
        raise ValidationError("clean split contains a known evaluation source")
    groups: dict[str, str] = {}
    variants: dict[str, str] = {}
    for record in ordered:
        parent, split = record["parent_id"], record["split"]
        if parent in groups and groups[parent] != split:
            raise ValidationError("parent lineage crosses splits")
        groups[parent] = split
        variant = known_variant_group(record)
        if variant in variants and variants[variant] != split:
            raise ValidationError("known transformed visible puzzle crosses splits")
        variants[variant] = split
    if output.exists() and any(output.iterdir()):
        raise ValidationError("frozen data output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    shards = []
    for start in range(0, len(ordered), shard_size):
        name = f"shard-{start // shard_size:05d}.jsonl"
        payload = b"".join(canonical_bytes(item, newline=True) for item in ordered[start:start + shard_size])
        (output / name).write_bytes(payload)
        shards.append({"path": name, "sha256": hashlib.sha256(payload).hexdigest(),
                       "records": min(shard_size, len(ordered) - start)})
    manifest = {"format": "irisx/nvarc-data-freeze", "policy": policy,
                "record_count": len(ordered), "shards": shards,
                "known_excluded_parent_count": len(forbidden),
                "known_variant_group_count": len(variants),
                "source_counts": dict(sorted(Counter(r["source_id"] for r in ordered).items())),
                "exposure": "unproven" if policy == "clean-research" else "competition-reproduction-contamination-possible"}
    (output / "manifest.json").write_bytes(canonical_bytes(manifest, newline=True))
    return manifest


def replay_sdg_stage(stage: str, inputs: Iterable[Mapping[str, Any]], responses: Mapping[str, Any],
                     *, prompt_digest: str, seed: int) -> list[dict[str, Any]]:
    """Saved-response backend: no provider call, code execution, or implicit generation."""
    allowed = {"summary", "mix", "input-logic", "output-logic", "pair", "filter"}
    if stage not in allowed or not prompt_digest.startswith("sha256:"):
        raise ValidationError("invalid SDG stage or prompt binding")
    output = []
    for item in inputs:
        key = item["record_id"]
        if key not in responses:
            raise ValidationError(f"missing saved SDG response: {key}")
        value = responses[key]
        output.append({"stage": stage, "record_id": key, "parent_id": item["parent_id"],
                       "source_id": item["source_id"], "prompt_digest": prompt_digest,
                       "input_digest": digest_value(item), "response_digest": digest_value(value),
                       "response": value, "seed": seed, "provider_calls": 0, "tokens": 0,
                       "filter_reason": None})
    return output


def pair_saved_sdg_grids(input_records: Iterable[Mapping[str, Any]],
                         output_records: Iterable[Mapping[str, Any]], *,
                         minimum_pairs: int = 2) -> list[dict[str, Any]]:
    """Pair precomputed grids by lineage and record filter decisions.

    This accepts saved grid arrays only. It never evaluates generated Python.
    """
    inputs = {item["record_id"]: item for item in input_records}
    outputs = {item["record_id"]: item for item in output_records}
    if set(inputs) != set(outputs) or minimum_pairs < 1:
        raise ValidationError("SDG input/output record pairing differs")
    paired = []
    for record_id in sorted(inputs):
        left, right = inputs[record_id], outputs[record_id]
        if (left["parent_id"], left["source_id"]) != (right["parent_id"], right["source_id"]):
            raise ValidationError("SDG parent/source lineage differs")
        left_grids, right_grids = left["response"], right["response"]
        if not isinstance(left_grids, list) or not isinstance(right_grids, list):
            raise ValidationError("saved SDG grids must be arrays")
        if len(left_grids) != len(right_grids):
            raise ValidationError("saved SDG input/output grid counts differ")
        pairs = [{"input": grid(in_grid), "output": grid(out_grid)}
                 for in_grid, out_grid in zip(left_grids, right_grids)]
        input_keys = [digest_value(item["input"]) for item in pairs]
        output_keys = [digest_value(item["output"]) for item in pairs]
        reason = None
        if len(pairs) < minimum_pairs:
            reason = "too_few_pairs"
        elif len(set(input_keys)) != len(input_keys):
            reason = "duplicate_inputs"
        elif len(set(output_keys)) == 1:
            reason = "constant_output"
        paired.append({"record_id": record_id, "parent_id": left["parent_id"],
                       "source_id": left["source_id"], "input_digest": left["response_digest"],
                       "output_digest": right["response_digest"], "pairs": pairs if reason is None else [],
                       "filter_reason": reason, "accepted": reason is None,
                       "provider_calls": 0, "tokens": 0})
    return paired


def require_isolated_executor(config: Mapping[str, Any]) -> None:
    """Legacy config claims cannot authorize execution of generated Python."""
    raise ValidationError("caller-supplied sandbox claims do not establish isolation")
