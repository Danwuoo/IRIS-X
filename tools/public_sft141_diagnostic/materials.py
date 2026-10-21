"""Explicit public data acquisition and gold-blind diagnostic panel freezing.

No network access or task loading happens on import. The source pins contain
public paths and Git blob hashes only. No private implementation, private
material bundle, old panel, or historical diagnostic artifact is an input.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.request
from collections.abc import Mapping
from pathlib import Path

from .contract import MAX_NEW_TOKENS, VIEWS, prompt_ids, validate_grid

PUBLIC_REPOSITORY = "https://github.com/arcprize/ARC-AGI-2"
PUBLIC_COMMIT = "f3283f727488ad98fe575ea6a5ac981e4a188e49"
SELECTION_SALT = "iris-public-diagnostic-20261021:"
PUBLIC_PARENT_COUNT = 120
PUBLIC_QUERY_COUNT = 167
PANEL_PARENT_COUNT = 12
MAX_SOURCE_BYTES = 1024 * 1024
FETCH_TIMEOUT_SECONDS = 20
FETCH_TOTAL_SECONDS = 600
PLAN_FILENAME = "plan.json"
GOLD_FILENAME = "gold.json"
MANIFEST_FILENAME = "material_manifest.json"


def _protocol() -> dict:
    return {"max_new_tokens": MAX_NEW_TOKENS, "views": list(VIEWS),
            "view_order": "view = 4 * transpose_flag + CCW quarter turns; transpose first",
            "support_policy": "all demonstrations, in original order; no truncation",
            "query_policy": "all test inputs, independently, in original order",
            "selection_salt": SELECTION_SALT,
            "selection_policy": "four equal length quartiles; three lowest hashes each",
            "selection_uses_query_outputs": False}


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True,
                       allow_nan=False) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    """Compute Git's blob identity, not a plain file SHA-1."""
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(data: bytes) -> object:
    return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_keys)


def load_public_pins() -> dict:
    """Read the checked-in, answer-free inventory of all 120 public parents."""
    pins = _load_json(Path(__file__).with_name("public_pins.json").read_bytes())
    if not isinstance(pins, dict) or pins.get("schema_version") != 1:
        raise ValueError("unsupported public pins schema")
    if pins.get("commit") != PUBLIC_COMMIT or pins.get("repository") != PUBLIC_REPOSITORY:
        raise ValueError("public source revision mismatch")
    files = pins.get("files")
    if not isinstance(files, list) or len(files) != PUBLIC_PARENT_COUNT:
        raise ValueError("public pins must contain exactly 120 files")
    paths = []
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "git_blob_sha1"}:
            raise ValueError("public pin entries must contain path and Git blob identity only")
        if not isinstance(entry["path"], str) or not re.fullmatch(
                r"data/evaluation/[0-9a-f]{8}\.json", entry["path"]):
            raise ValueError("unsafe or unexpected public task path")
        if not isinstance(entry["git_blob_sha1"], str) or not re.fullmatch(
                r"[0-9a-f]{40}", entry["git_blob_sha1"]):
            raise ValueError("invalid Git blob identity")
        paths.append(entry["path"])
    if paths != sorted(set(paths)):
        raise ValueError("public pins must have unique sorted paths")
    return pins


def _verify_blob(data: bytes, entry: dict) -> None:
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError(f"public task exceeds size bound: {entry['path']}")
    if git_blob_sha1(data) != entry["git_blob_sha1"]:
        raise ValueError(f"public Git blob pin mismatch: {entry['path']}")


def fetch_public_data(destination: str | Path) -> dict:
    """Deliberately download the pinned public evaluation set into a NEW folder.

    This function is never called by preparation, inference or imports.
    Default tests never perform network requests.
    Every read has a timeout and a 1 MiB bound; the fetch checks a 10-minute
    deadline between bounded reads. A failure may leave a partial new directory, never overwrite an
    existing directory or silently accept unverified bytes.
    """
    pins = load_public_pins()
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + FETCH_TOTAL_SECONDS
    files = []
    for entry in pins["files"]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("public source fetch deadline exceeded")
        url = ("https://raw.githubusercontent.com/arcprize/ARC-AGI-2/"
               + PUBLIC_COMMIT + "/" + entry["path"])
        request = urllib.request.Request(url, headers={"User-Agent": "public-sft141-diagnostic/1"})
        with urllib.request.urlopen(request, timeout=min(FETCH_TIMEOUT_SECONDS, remaining)) as response:
            if response.geturl() != url:
                raise ValueError("unexpected redirect while fetching fixed public source")
            chunks = []
            size = 0
            while size <= MAX_SOURCE_BYTES:
                if time.monotonic() > deadline:
                    raise TimeoutError("public source fetch deadline exceeded")
                chunk = response.read1(min(65536, MAX_SOURCE_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
            data = b"".join(chunks)
        if time.monotonic() > deadline:
            raise TimeoutError("public source fetch deadline exceeded")
        _verify_blob(data, entry)
        target = destination / Path(entry["path"]).name
        with target.open("xb") as stream:
            stream.write(data)
        files.append({**entry, "sha256": _sha256(data), "size_bytes": len(data)})
    return {"repository": PUBLIC_REPOSITORY, "commit": PUBLIC_COMMIT,
            "parent_count": len(files), "files": files}


def _public_projection(task: Mapping) -> dict:
    """Read support and test inputs only. Do NOT inspect test output keys."""
    if not isinstance(task, Mapping):
        raise ValueError("task must be a mapping")
    train = task["train"]
    tests = task["test"]
    if not isinstance(train, list) or not train:
        raise ValueError("task must have support demonstrations")
    if not isinstance(tests, list) or not tests:
        raise ValueError("task must have test inputs")
    return {
        "train": [{"input": validate_grid(pair["input"]),
                   "output": validate_grid(pair["output"])} for pair in train],
        "test": [{"input": validate_grid(query["input"])} for query in tests],
    }


def selection_hash(task_id: str) -> str:
    return _sha256((SELECTION_SALT + task_id).encode("ascii"))


def select_panel(tasks: Mapping[str, Mapping]) -> dict:
    """Select 12 parents from 120, without looking at any query answer.

    Length = maximum full all-support prompt length over EVERY true test input
    and all eight D4 views. Sort by (length, task ID), make four groups of 30,
    and take each group's three lowest salted SHA-256 ranks. If no multi-query
    parent was chosen, replace the hash-last chosen single-query parent in the
    first quartile with a multi-query parent by its hash-first multi-query
    parent. No output lengths, labels, outcomes or difficulty judgments enter.
    """
    if not isinstance(tasks, Mapping) or len(tasks) != PUBLIC_PARENT_COUNT:
        raise ValueError("panel selection requires exactly 120 public parents")
    inventory = []
    for task_id, task in tasks.items():
        if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-f]{8}", task_id):
            raise ValueError("task ID must be eight lowercase hex characters")
        visible = _public_projection(task)
        cost = max(len(prompt_ids(visible["train"], query["input"], view))
                   for query in visible["test"] for view in VIEWS)
        inventory.append({"task_id": task_id, "max_prompt_tokens": cost,
                          "test_count": len(visible["test"]),
                          "selection_hash": selection_hash(task_id)})
    inventory.sort(key=lambda row: (row["max_prompt_tokens"], row["task_id"]))
    quartiles = []
    selected = []
    for quartile in range(4):
        group = inventory[quartile * 30:(quartile + 1) * 30]
        for row in group:
            row["quartile"] = quartile
        quartiles.append(group)
        selected.extend(sorted(group, key=lambda row: (row["selection_hash"], row["task_id"]))[:3])
    repair = None
    if not any(row["test_count"] > 1 for row in selected):
        for quartile, group in enumerate(quartiles):
            multi = [row for row in group if row["test_count"] > 1]
            if not multi:
                continue
            incoming = min(multi, key=lambda row: (row["selection_hash"], row["task_id"]))
            outgoing = max((row for row in selected if row["quartile"] == quartile),
                           key=lambda row: (row["selection_hash"], row["task_id"]))
            selected.remove(outgoing)
            selected.append(incoming)
            repair = {"quartile": quartile, "removed_task_id": outgoing["task_id"],
                      "added_task_id": incoming["task_id"]}
            break
        if repair is None:
            raise ValueError("public inventory has no multi-query parent")
    selected.sort(key=lambda row: (row["quartile"], row["selection_hash"], row["task_id"]))
    return {"selected": selected, "inventory": inventory, "multi_query_repair": repair}


def load_public_data(data_dir: str | Path) -> tuple[dict, list[dict]]:
    """Verify local upstream bytes against every checked-in public blob pin.

    Accept either an upstream repository root or a flat evaluation directory.
    No fallback source, download, private material or unpinned file is used.
    """
    pins = load_public_pins()
    data_dir = Path(data_dir)
    nested = data_dir / "data" / "evaluation"
    source_dir = nested if nested.is_dir() else data_dir
    expected_names = {Path(entry["path"]).name for entry in pins["files"]}
    actual_names = {path.name for path in source_dir.glob("*.json")}
    if actual_names != expected_names:
        raise ValueError("source directory must contain exactly the 120 pinned task JSON files")
    tasks = {}
    source_files = []
    for entry in pins["files"]:
        path = source_dir / Path(entry["path"]).name
        with path.open("rb") as stream:
            data = stream.read(MAX_SOURCE_BYTES + 1)
        _verify_blob(data, entry)
        task_id = path.stem
        tasks[task_id] = _load_json(data)
        source_files.append({**entry, "sha256": _sha256(data), "size_bytes": len(data)})
    return tasks, source_files


def prepare_materials(data_dir: str | Path, out_dir: str | Path) -> dict:
    """Freeze a NEW public-only plan, separate evaluator gold, and manifests.

    The plan includes every selected parent's demonstrations and all original
    test inputs. Selection finishes BEFORE any test output is accessed. Gold
    is read only into the separate evaluator object after that boundary.
    """
    out_dir = Path(out_dir)
    if out_dir.exists() or out_dir.is_symlink():
        raise FileExistsError(f"refusing to overwrite material directory: {out_dir}")
    tasks, source_files = load_public_data(data_dir)
    selection = select_panel(tasks)
    query_count = sum(row["test_count"] for row in selection["inventory"])
    if query_count != PUBLIC_QUERY_COUNT:
        raise ValueError("pinned public inventory must contain all 167 test inputs")
    provenance = {"repository": PUBLIC_REPOSITORY, "commit": PUBLIC_COMMIT,
                  "license": "Apache-2.0", "public_parent_count": PUBLIC_PARENT_COUNT,
                  "public_query_count": query_count,
                  "qualification": "Independent public-development diagnostic; not a held-out benchmark."}
    parents = []
    for selected in selection["selected"]:
        task_id = selected["task_id"]
        visible = _public_projection(tasks[task_id])
        parents.append({"task_id": task_id, "train": visible["train"],
                        "test": [{"input": query["input"], "test_index": index,
                                  "query_id": f"{task_id}:{index}"}
                                 for index, query in enumerate(visible["test"])],
                        "selection": {key: value for key, value in selected.items()
                                      if key != "task_id"}})
    plan = {"schema": "iris-public-sft141-plan-v1", "parents": parents,
            "provenance": provenance,
            "protocol": _protocol()}
    # Evaluator-only boundary: the inference plan and selection are already final.
    gold = {"schema": "iris-public-sft141-gold-v1", "provenance": provenance,
            "answers": {parent["task_id"]: [validate_grid(query["output"])
                         for query in tasks[parent["task_id"]]["test"]]
                        for parent in parents}}
    plan_bytes, gold_bytes = _json_bytes(plan), _json_bytes(gold)
    manifest = {
        "schema": "iris-public-sft141-materials-v1",
        "provenance": provenance,
        "source_files": source_files,
        "panel": selection,
        "panel_parent_count": len(parents),
        "panel_query_count": sum(len(parent["test"]) for parent in parents),
        "files": {PLAN_FILENAME: {"sha256": _sha256(plan_bytes), "size_bytes": len(plan_bytes)},
                  GOLD_FILENAME: {"sha256": _sha256(gold_bytes), "size_bytes": len(gold_bytes)}},
    }
    out_dir.mkdir(parents=True, exist_ok=False)
    for name, data in ((PLAN_FILENAME, plan_bytes), (GOLD_FILENAME, gold_bytes),
                       (MANIFEST_FILENAME, _json_bytes(manifest))):
        with (out_dir / name).open("xb") as stream:
            stream.write(data)
    return manifest


def verify_materials(material_dir: str | Path) -> tuple[dict, dict]:
    """Verify hashes and inference schema, without parsing evaluator gold.

    The manifest is a local integrity receipt, not a signature. The caller must
    additionally freeze its own manifest hash before execution. Both files'
    byte hashes are checked here; only plan.json is decoded as JSON.
    """
    material_dir = Path(material_dir)
    manifest = _load_json((material_dir / MANIFEST_FILENAME).read_bytes())
    if not isinstance(manifest, dict) or manifest.get("schema") != "iris-public-sft141-materials-v1":
        raise ValueError("unsupported materials manifest schema")
    records = manifest.get("files")
    if not isinstance(records, dict) or set(records) != {PLAN_FILENAME, GOLD_FILENAME}:
        raise ValueError("manifest must hash exactly plan.json and gold.json")
    plan_data = None
    for name in (PLAN_FILENAME, GOLD_FILENAME):
        data = (material_dir / name).read_bytes()
        record = records[name]
        if not isinstance(record, dict) or record.get("sha256") != _sha256(data) or record.get("size_bytes") != len(data):
            raise ValueError(f"material hash or size mismatch: {name}")
        if name == PLAN_FILENAME:
            plan_data = data
    pins = load_public_pins()
    source_files = manifest.get("source_files")
    if not isinstance(source_files, list) or len(source_files) != PUBLIC_PARENT_COUNT:
        raise ValueError("manifest must bind all 120 public source files")
    if any(not isinstance(entry, dict) or set(entry) != {"path", "git_blob_sha1", "sha256", "size_bytes"}
           for entry in source_files):
        raise ValueError("invalid source-file identity record")
    source_identities = [{"path": entry.get("path"), "git_blob_sha1": entry.get("git_blob_sha1")}
                         for entry in source_files]
    if source_identities != pins["files"]:
        raise ValueError("manifest public source identities differ from checked-in pins")
    plan = _load_json(plan_data)
    if not isinstance(plan, dict) or plan.get("schema") != "iris-public-sft141-plan-v1":
        raise ValueError("unsupported inference plan schema")
    if set(plan) != {"schema", "parents", "provenance", "protocol"}:
        raise ValueError("unexpected inference-plan field")
    if plan["protocol"] != _protocol():
        raise ValueError("inference protocol differs from the frozen public diagnostic")
    if (not isinstance(plan["provenance"], dict)
            or plan["provenance"] != manifest.get("provenance")
            or plan["provenance"].get("commit") != PUBLIC_COMMIT
            or plan["provenance"].get("repository") != PUBLIC_REPOSITORY
            or plan["provenance"].get("public_parent_count") != PUBLIC_PARENT_COUNT
            or plan["provenance"].get("public_query_count") != PUBLIC_QUERY_COUNT):
        raise ValueError("plan provenance mismatch")
    parents = plan.get("parents")
    if not isinstance(parents, list) or len(parents) != PANEL_PARENT_COUNT:
        raise ValueError("inference plan requires twelve parents")
    if any(not isinstance(row, dict) or set(row) != {"task_id", "train", "test", "selection"}
           for row in parents):
        raise ValueError("unexpected parent-plan fields")
    panel = manifest.get("panel")
    if not isinstance(panel, dict):
        raise ValueError("missing panel selection metadata")
    selected = panel.get("selected")
    if not isinstance(selected, list) or len(selected) != PANEL_PARENT_COUNT:
        raise ValueError("missing selected-parent metadata")
    selection_fields = {"task_id", "max_prompt_tokens", "test_count", "selection_hash", "quartile"}
    if any(not isinstance(row, dict) or set(row) != selection_fields for row in selected):
        raise ValueError("invalid selected-parent metadata")
    if [row["task_id"] for row in parents] != [row["task_id"] for row in selected]:
        raise ValueError("inference plan does not match selected parent order")
    if len({row["task_id"] for row in parents}) != PANEL_PARENT_COUNT:
        raise ValueError("duplicate inference parent")
    count = 0
    for parent, selected_row in zip(parents, selected):
        if not isinstance(parent["train"], list) or not isinstance(parent["test"], list):
            raise ValueError("support and query inventories must be lists")
        if any(not isinstance(pair, dict) or set(pair) != {"input", "output"} for pair in parent["train"]):
            raise ValueError("unexpected support field")
        for index, query in enumerate(parent["test"]):
            if not isinstance(query, dict) or set(query) != {"input", "test_index", "query_id"}:
                raise ValueError("query answer or unexpected field in inference plan")
            if query["test_index"] != index or query["query_id"] != f"{parent['task_id']}:{index}":
                raise ValueError("query inventory or order mismatch")
        visible = _public_projection(parent)
        cost = max(len(prompt_ids(visible["train"], query["input"], view))
                   for query in visible["test"] for view in VIEWS)
        expected_selection = {key: value for key, value in selected_row.items() if key != "task_id"}
        if (parent["selection"] != expected_selection
                or cost != selected_row["max_prompt_tokens"]
                or len(parent["test"]) != selected_row["test_count"]
                or selection_hash(parent["task_id"]) != selected_row["selection_hash"]):
            raise ValueError("inference selection metadata mismatch")
        count += len(parent["test"])
    if manifest.get("panel_parent_count") != len(parents) or manifest.get("panel_query_count") != count:
        raise ValueError("panel denominator mismatch")
    if not any(len(parent["test"]) > 1 for parent in parents):
        raise ValueError("panel must include a multi-query parent")
    return manifest, plan
