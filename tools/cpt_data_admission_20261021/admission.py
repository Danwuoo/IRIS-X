"""Bounded JSONL admission with audited lineage, disk staging and atomic seals.

No network, model, tokenizer, provider or generated-program execution. Registry
assertions are reviewed inputs, not independently established licensing facts.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from urllib.parse import urlparse

VERSION = "cpt-data-admission-20261021.v1"
SPLITS = {"train", "dev", "evaluation", "source_test"}
SHA = re.compile(r"[0-9a-f]{64}\Z")
LIMITS = {"max_total_bytes": 64 * 1024 * 1024, "max_record_bytes": 1024 * 1024,
          "max_records": 100_000, "max_registry_bytes": 4 * 1024 * 1024,
          "max_graph_nodes": 20_000, "max_ancestors": 4096, "max_depth": 128}


class AdmissionError(ValueError):
    """Fail-closed contract, pin, resource or restart error."""


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise AdmissionError("duplicate_json_key")
        out[key] = value
    return out


def decode(raw):
    try:
        return json.loads(raw, object_pairs_hook=_unique_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              AdmissionError("nonfinite_json")))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise AdmissionError("invalid_json: " + str(exc)) from exc


def _string(value, max_length=512):
    return isinstance(value, str) and 0 < len(value) <= max_length and not any(
        ord(c) < 32 for c in value)


def _sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _keys(obj, required, optional=()):
    return isinstance(obj, dict) and set(required) <= set(obj) <= set(required) | set(optional)


def file_pin(path, max_bytes):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise AdmissionError("artifact_missing_or_symlink: " + str(path))
    count = 0
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            count += len(chunk)
            if count > max_bytes:
                raise AdmissionError("artifact_byte_limit")
            h.update(chunk)
    return {"bytes": count, "sha256": h.hexdigest()}


def validate_task(task, require_answers=False):
    """All tests are validated; no projection to test[0], truncation or coercion."""
    if not _keys(task, {"train", "test"}):
        raise AdmissionError("task_schema")
    for role in ("train", "test"):
        pairs = task[role]
        if not isinstance(pairs, list) or not 1 <= len(pairs) <= 128:
            raise AdmissionError("pair_count")
        for pair in pairs:
            required = {"input", "output"} if role == "train" or require_answers else {"input"}
            if not _keys(pair, required, {"output"}):
                raise AdmissionError("pair_schema_or_missing_target")
            for grid in pair.values():
                if not isinstance(grid, list) or not 1 <= len(grid) <= 30:
                    raise AdmissionError("grid_height")
                width = len(grid[0]) if isinstance(grid[0], list) else 0
                if not 1 <= width <= 30 or any(not isinstance(row, list) or len(row) != width for row in grid):
                    raise AdmissionError("grid_width_or_ragged")
                if any(type(cell) is not int or not 0 <= cell <= 9 for row in grid for cell in row):
                    raise AdmissionError("grid_color_not_integer_0_9")
    coverage = ["output" in pair for pair in task["test"]]
    if any(coverage) and not all(coverage):
        raise AdmissionError("partial_test_gold")
    return task


def _rotate(grid):
    return [list(row) for row in zip(*grid[::-1])]


def _transform(grid, rotation, reflect):
    out = [row[::-1] if reflect else row[:] for row in grid]
    for _ in range(rotation):
        out = _rotate(out)
    return out


def prompt_task(task):
    return {"train": task["train"], "test": [{"input": pair["input"]} for pair in task["test"]]}


def canonical_task(task):
    """D4 + one joint bijective color relabel; pair order stays significant.

    This is finite transform equivalence, NOT semantic/rule/program deduplication.
    """
    candidates = []
    for reflect in (False, True):
        for rotation in range(4):
            colors = {}
            out = {}
            for role in ("train", "test"):
                out[role] = []
                for pair in task[role]:
                    row = {}
                    for key in ("input", "output"):
                        if key not in pair:
                            continue
                        grid = _transform(pair[key], rotation, reflect)
                        row[key] = [[colors.setdefault(cell, len(colors)) for cell in line] for line in grid]
                    out[role].append(row)
            candidates.append(encoded(out))
    return hashlib.sha256(min(candidates)).hexdigest()


class UnionFind:
    def __init__(self):
        self.parents = {}

    def find(self, item):
        self.parents.setdefault(item, item)
        root = item
        while self.parents[root] != root:
            root = self.parents[root]
        while self.parents[item] != item:
            item, self.parents[item] = self.parents[item], root
        return root

    def union(self, left, right):
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parents[max(a, b)] = min(a, b)


def _rearc(*values):
    return any("rearc" in re.sub(r"[^a-z0-9]", "", str(value).lower()) for value in values)


class Registry:
    def __init__(self, path, expected_sha256, limits):
        self.path, self.limits = Path(path), limits
        self.pin = file_pin(self.path, limits["max_registry_bytes"])
        if self.pin["sha256"] != expected_sha256:
            raise AdmissionError("registry_pin_mismatch")
        with self.path.open("rb") as stream:
            raw_registry = stream.read(limits["max_registry_bytes"] + 1)
        if len(raw_registry) > limits["max_registry_bytes"] or hashlib.sha256(raw_registry).hexdigest() != expected_sha256:
            raise AdmissionError("registry_changed_while_reading")
        self.data = decode(raw_registry)
        if not _keys(self.data, {"schema_version", "scope", "artifacts", "sources", "lineage", "shards"}):
            raise AdmissionError("registry_schema")
        if type(self.data["schema_version"]) is not int or self.data["schema_version"] != 1 or self.data["scope"] not in (
                "synthetic-fixtures", "local-public-sample", "bounded-corpus-window"):
            raise AdmissionError("registry_version_or_scope")
        for key in ("artifacts", "sources", "lineage"):
            if not isinstance(self.data[key], dict) or len(self.data[key]) > limits["max_graph_nodes"]:
                raise AdmissionError("registry_graph_bound")
            if any(not _string(k) for k in self.data[key]):
                raise AdmissionError("registry_id")
        self.artifacts = self.data["artifacts"]
        self.sources, self.nodes = self.data["sources"], self.data["lineage"]
        self.verified_artifacts = {}
        self._source_cache, self._lineage_cache = {}, {}
        total = 0
        for key, item in sorted(self.artifacts.items()):
            if not _keys(item, {"path", "bytes", "sha256"}) or not _string(item["path"], 4096) or not _sha(item["sha256"]):
                raise AdmissionError("artifact_schema")
            if type(item["bytes"]) is not int or item["bytes"] < 0:
                raise AdmissionError("artifact_size")
            total += item["bytes"]
            if total > limits["max_total_bytes"]:
                raise AdmissionError("total_byte_limit")
            relative = Path(item["path"])
            if relative.is_absolute() or ".." in relative.parts or "\\" in item["path"] or not relative.parts:
                raise AdmissionError("artifact_path_outside_registry_root")
            registry_root = self.path.parent.resolve()
            target = registry_root / relative
            current = registry_root
            for part in relative.parts:
                current = current / part
                if current.is_symlink():
                    raise AdmissionError("artifact_path_symlink")
            if not target.resolve().is_relative_to(registry_root):
                raise AdmissionError("artifact_path_outside_registry_root")
            pin = file_pin(target, limits["max_total_bytes"])
            if pin != {k: item[k] for k in ("bytes", "sha256")}:
                raise AdmissionError("artifact_pin_mismatch: " + key)
            self.verified_artifacts[key] = target
        shards = self.data["shards"]
        if not isinstance(shards, list) or not 1 <= len(shards) <= limits["max_graph_nodes"]:
            raise AdmissionError("shard_count")
        seen = set()
        for shard in shards:
            if not _keys(shard, {"artifact_id", "source_id"}):
                raise AdmissionError("shard_schema")
            if not _string(shard["artifact_id"]) or not _string(shard["source_id"]) or shard["artifact_id"] not in self.artifacts or shard["source_id"] not in self.sources:
                raise AdmissionError("shard_reference")
            if shard["artifact_id"] in seen:
                raise AdmissionError("duplicate_shard")
            seen.add(shard["artifact_id"])
        self.shards = sorted(shards, key=lambda row: (row["source_id"], row["artifact_id"]))
        self.family_groups = UnionFind()
        for node_id, node in self.nodes.items():
            if not isinstance(node, dict):
                continue
            self.family_groups.find("node:" + node_id)
            for parent in node.get("parents", []) if isinstance(node.get("parents"), list) else []:
                if _string(parent):
                    self.family_groups.union("node:" + node_id, "node:" + parent)
            for family in node.get("family_ids", []) if isinstance(node.get("family_ids"), list) else []:
                if _string(family):
                    self.family_groups.union("node:" + node_id, "family:" + family)

        # The registry, not the selected rows, defines family isolation. A
        # missing evaluation row or unresolved sibling cannot launder a family.
        self.component_reasons, component_splits = {}, {}
        for node_id in sorted(self.nodes):
            lineage = self.lineage(node_id)
            component = lineage["family_component"]
            self.component_reasons.setdefault(component, set()).update(lineage["reasons"])
            component_splits.setdefault(component, set()).add(lineage["split"])
        for component, splits in component_splits.items():
            if len(splits) > 1:
                self.component_reasons[component].add("registry_family_split_conflict")

    def reverify(self):
        if file_pin(self.path, self.limits["max_registry_bytes"]) != self.pin:
            raise AdmissionError("registry_changed_during_build")
        for key, path in self.verified_artifacts.items():
            if file_pin(path, self.limits["max_total_bytes"]) != {k: self.artifacts[key][k] for k in ("bytes", "sha256")}:
                raise AdmissionError("artifact_changed_during_build: " + key)

    def source_reasons(self, source_id):
        if not _string(source_id):
            return {"unresolved_source"}
        if source_id in self._source_cache:
            return set(self._source_cache[source_id])
        visited, active, reasons = set(), set(), set()
        stack = [(source_id, False, 0)]
        while stack:
            current, leaving, depth = stack.pop()
            if leaving:
                active.discard(current)
                continue
            if current in active:
                reasons.add("source_cycle_or_depth")
                continue
            if current in visited:
                continue
            if depth >= self.limits["max_depth"] or len(visited) >= self.limits["max_ancestors"]:
                reasons.add("source_cycle_or_depth")
                break
            visited.add(current)
            reasons.update(self._source_local_reasons(current))
            source = self.sources.get(current)
            if not isinstance(source, dict) or not isinstance(source.get("parents"), list):
                continue
            active.add(current)
            stack.append((current, True, depth))
            stack.extend((p, False, depth + 1) for p in reversed(source["parents"]) if _string(p))
        self._source_cache[source_id] = frozenset(reasons)
        return reasons

    def _source_local_reasons(self, source_id):
        source = self.sources.get(source_id)
        if not isinstance(source, dict):
            return {"unresolved_source"}
        required = {"url", "revision", "revision_kind", "parents", "origin_status", "rearc_status", "license", "evidence"}
        if not _keys(source, required):
            return {"source_schema"}
        reasons = set()
        if _rearc(source_id, source["url"]) or source["rearc_status"] == "derived":
            reasons.add("excluded_rearc")
        elif source["rearc_status"] != "clear":
            reasons.add("unresolved_rearc_ancestry")
        if source["origin_status"] != "resolved":
            reasons.add("unresolved_origin")
        if not _string(source["url"], 4096) or urlparse(source["url"]).scheme not in ("https", "fixture"):
            reasons.add("unresolved_source_url")
        kind, rev = source["revision_kind"], source["revision"]
        exact = isinstance(rev, str) and (
            (kind == "git_commit" and re.fullmatch(r"[0-9a-f]{40}", rev)) or
            (kind == "sha256" and _sha(rev)) or
            (kind == "dataset_version" and re.fullmatch(r"[A-Za-z0-9_./-]+:v[1-9][0-9]*", rev)))
        if not exact:
            reasons.add("mutable_or_missing_revision")
        if self.data["scope"] != "synthetic-fixtures" and str(source["url"]).startswith("fixture:"):
            reasons.add("fixture_in_real_scope")
        if not self._evidence(source["evidence"]):
            reasons.add("missing_origin_evidence")
        license_info = source["license"]
        if not _keys(license_info, {"status", "spdx", "evidence", "notices"}):
            reasons.add("unresolved_license")
        else:
            if license_info["status"] != "resolved" or not _string(license_info["spdx"]):
                reasons.add("unresolved_license")
            if not self._evidence(license_info["evidence"]):
                reasons.add("missing_license_evidence")
            if not isinstance(license_info["notices"], list) or any(not isinstance(x, str) or x not in self.artifacts for x in license_info["notices"]):
                reasons.add("unresolved_notices")
        if not isinstance(source["parents"], list) or any(not _string(p) for p in source["parents"]):
            reasons.add("source_parent_schema")
        return reasons

    def _evidence(self, items):
        return isinstance(items, list) and bool(items) and all(isinstance(x, str) and x in self.artifacts for x in items)

    def lineage(self, node_id):
        if node_id in self._lineage_cache:
            return self._lineage_cache[node_id]
        visited, active, reasons, families, splits, iris_splits = set(), set(), set(), set(), set(), set()
        stack = [(node_id, False, 0)]
        while stack:
            current, leaving, depth = stack.pop()
            if leaving:
                active.discard(current)
                continue
            if current in active:
                reasons.add("lineage_cycle")
                continue
            if current in visited:
                continue
            if depth >= self.limits["max_depth"] or len(visited) >= self.limits["max_ancestors"]:
                reasons.add("lineage_bound")
                break
            visited.add(current)
            node = self.nodes.get(current)
            if not _keys(node, {"source_id", "parents", "family_ids", "original_split", "iris_split", "evidence"}):
                reasons.add("unresolved_lineage_node")
                continue
            if _rearc(current):
                reasons.add("excluded_rearc")
            reasons.update(self.source_reasons(node["source_id"]))
            if not self._evidence(node["evidence"]):
                reasons.add("missing_lineage_evidence")
            if not _string(node["original_split"]) or node["original_split"] not in SPLITS or not _string(node["iris_split"]) or node["iris_split"] not in SPLITS:
                reasons.add("unresolved_split")
            splits.update(str(value) for value in (node["original_split"], node["iris_split"]))
            iris_splits.add(str(node["iris_split"]))
            if node["original_split"] in ("evaluation", "source_test") and node["iris_split"] != node["original_split"]:
                reasons.add("protected_split_relabel")
            if not isinstance(node["family_ids"], list) or not node["family_ids"] or any(not _string(f) for f in node["family_ids"]):
                reasons.add("unresolved_family")
            else:
                families.update(node["family_ids"])
            if not isinstance(node["parents"], list) or any(not _string(p) for p in node["parents"]):
                reasons.add("lineage_parent_schema")
                continue
            active.add(current)
            stack.append((current, True, depth))
            stack.extend((p, False, depth + 1) for p in reversed(node["parents"]))
        own = self.nodes.get(node_id, {})
        split = own.get("iris_split", "unknown") if isinstance(own, dict) else "unknown"
        if split == "train" and splits - {"train"}:
            reasons.add("nontraining_ancestry")
        if not _string(split) or split not in SPLITS:
            split = "unknown"
        if iris_splits - {split}:
            reasons.add("lineage_split_conflict")
        result = {"ancestors": sorted(visited), "families": sorted(families), "split": split,
                  "family_component": self.family_groups.find("node:" + node_id), "reasons": sorted(reasons)}
        # Cache only bounded metadata, not corpus/task bodies.
        if len(self._lineage_cache) >= 128:
            self._lineage_cache.pop(next(iter(self._lineage_cache)))
        self._lineage_cache[node_id] = result
        return result


def _tool_digest():
    return digest({p.name: file_pin(p, 1024 * 1024)["sha256"] for p in sorted(Path(__file__).parent.glob("*.py"))})


def _record(raw, registry, source_id):
    result = {"record_id": None, "lineage_id": None, "split": "unknown", "task": None,
              "exact": None, "canonical": None, "visible": None, "family": None,
              "lineage": None, "reasons": [], "provenance_reasons": [], "status": "quarantine"}
    try:
        row = decode(raw)
        if not _keys(row, {"record_id", "lineage_id", "source_locator", "task"}, {"transforms"}):
            raise AdmissionError("record_schema")
        if any(not _string(row[key]) for key in ("record_id", "lineage_id", "source_locator")):
            raise AdmissionError("record_identity")
        transforms = row.get("transforms", [])
        if not isinstance(transforms, list) or len(transforms) > 128 or any(not _string(t) for t in transforms):
            raise AdmissionError("transform_schema")
        result.update(record_id=row["record_id"], lineage_id=row["lineage_id"], source_locator=row["source_locator"], transforms=transforms)
        lineage = registry.lineage(row["lineage_id"])
        result.update(lineage=lineage, split=lineage["split"], family=lineage["family_component"])
        reasons = (set(lineage["reasons"]) | registry.source_reasons(source_id) |
                   registry.component_reasons.get(lineage["family_component"], set()))
        node = registry.nodes.get(row["lineage_id"], {})
        if not isinstance(node, dict) or node.get("source_id") != source_id:
            reasons.add("record_source_lineage_mismatch")
        if _rearc(row["record_id"], row["source_locator"]):
            reasons.add("excluded_rearc")
        result["reasons"] = sorted(reasons)
        result["provenance_reasons"] = sorted(reasons)
        task = validate_task(row["task"], require_answers=result["split"] == "train")
        result.update(task=task, exact=digest(task), canonical=canonical_task(task), visible=canonical_task(prompt_task(task)))
        result["status"] = "reject" if "excluded_rearc" in reasons else "quarantine" if reasons else "candidate"
    except AdmissionError as exc:
        result["status"] = "reject"
        result["reasons"] = sorted(set(result["reasons"]) | {str(exc)})
    return result


def _connect(path, binding):
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=DELETE")
    db.execute("PRAGMA synchronous=FULL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS rows(n INTEGER PRIMARY KEY, shard INTEGER, line INTEGER,
            offset INTEGER, length INTEGER, raw_sha TEXT, record_id TEXT, split TEXT,
            family TEXT, exact TEXT, canonical TEXT, visible TEXT, base_result TEXT, result TEXT);
        CREATE TABLE IF NOT EXISTS cursors(shard INTEGER PRIMARY KEY, offset INTEGER, line INTEGER);
    """)
    stored = db.execute("SELECT value FROM meta WHERE key='binding'").fetchone()
    text = encoded(binding).decode()
    if stored and stored[0] != text:
        db.close()
        raise AdmissionError("restart_binding_mismatch")
    with db:
        db.execute("INSERT OR IGNORE INTO meta VALUES ('binding', ?)", (text,))
    return db


def _validate_staged(db, registry):
    """Replay the committed prefix, checking cursor and serialized row integrity.

    SQLite is a restart cache, never independent evidence or a trusted source.
    No staged row becomes admissible solely because it exists in the database.
    """
    offsets, lines, hashes = {}, {}, {}
    last_shard = -1
    with contextlib.ExitStack() as stack:
        streams = {i: stack.enter_context(registry.verified_artifacts[s["artifact_id"]].open("rb"))
                   for i, s in enumerate(registry.shards)}
        for expected_n, saved in enumerate(db.execute("SELECT n,shard,line,offset,length,raw_sha,record_id,split,family,exact,canonical,visible,base_result FROM rows ORDER BY n")):
            n, shard, line, offset, length, raw_sha, *metadata, base_result = saved
            if (n != expected_n or n >= registry.limits["max_records"] or shard not in streams or
                    shard < last_shard or line != lines.get(shard, 0) + 1 or offset != offsets.get(shard, 0)):
                raise AdmissionError("restart_cursor_or_row_order_mismatch")
            if shard != last_shard:
                for previous in range(last_shard + 1, shard):
                    if registry.artifacts[registry.shards[previous]["artifact_id"]]["bytes"] != 0:
                        raise AdmissionError("restart_skipped_shard")
                if last_shard >= 0 and offsets[last_shard] != registry.artifacts[registry.shards[last_shard]["artifact_id"]]["bytes"]:
                    raise AdmissionError("restart_incomplete_prior_shard")
                last_shard = shard
            raw = streams[shard].readline(registry.limits["max_record_bytes"] + 1)
            if len(raw) != length or hashlib.sha256(raw).hexdigest() != raw_sha:
                raise AdmissionError("restart_raw_row_mismatch")
            record = _record(raw, registry, registry.shards[shard]["source_id"])
            expected = [record[key] for key in ("record_id", "split", "family", "exact", "canonical", "visible")]
            if metadata != expected or encoded(record).decode() != base_result:
                raise AdmissionError("restart_staged_record_mismatch")
            offsets[shard], lines[shard] = offset + length, line
            hashes.setdefault(shard, hashlib.sha256()).update(raw)
        cursors = {i: (offset, line) for i, offset, line in db.execute("SELECT shard,offset,line FROM cursors")}
        if cursors != {i: (offsets[i], lines[i]) for i in offsets}:
            raise AdmissionError("restart_cursor_mismatch")
    return {i: h.hexdigest() for i, h in hashes.items()}


def _ingest(db, registry, stop_after_records, prefix_hashes):
    newly_read = 0
    count = db.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
    for shard_index, shard in enumerate(registry.shards):
        cursor = db.execute("SELECT offset,line FROM cursors WHERE shard=?", (shard_index,)).fetchone() or (0, 0)
        offset, line = cursor
        with registry.verified_artifacts[shard["artifact_id"]].open("rb") as stream:
            consumed = 0
            h = hashlib.sha256()
            while consumed < offset:
                chunk = stream.read(min(1024 * 1024, offset - consumed))
                if not chunk:
                    raise AdmissionError("source_prefix_truncated")
                h.update(chunk)
                consumed += len(chunk)
            if offset and h.hexdigest() != prefix_hashes[shard_index]:
                raise AdmissionError("source_prefix_changed_during_resume")
            while True:
                raw = stream.readline(registry.limits["max_record_bytes"] + 1)
                if not raw:
                    pin = registry.artifacts[shard["artifact_id"]]
                    if consumed != pin["bytes"] or h.hexdigest() != pin["sha256"]:
                        raise AdmissionError("source_stream_pin_mismatch")
                    break
                h.update(raw)
                consumed += len(raw)
                if len(raw) > registry.limits["max_record_bytes"]:
                    raise AdmissionError("record_byte_limit")
                if count >= registry.limits["max_records"]:
                    raise AdmissionError("record_count_limit")
                record = _record(raw, registry, shard["source_id"])
                line += 1
                with db:
                    db.execute("INSERT INTO rows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                        count, shard_index, line, offset, len(raw), hashlib.sha256(raw).hexdigest(),
                        record["record_id"], record["split"], record["family"], record["exact"],
                        record["canonical"], record["visible"], encoded(record).decode(), encoded(record).decode()))
                    offset += len(raw)
                    db.execute("INSERT OR REPLACE INTO cursors VALUES (?,?,?)", (shard_index, offset, line))
                count += 1
                newly_read += 1
                if stop_after_records is not None and newly_read >= stop_after_records:
                    return False
    return True


def _classify(db):
    groups, first = UnionFind(), {}
    for n, family, exact, canonical, visible in db.execute("SELECT n,family,exact,canonical,visible FROM rows ORDER BY n"):
        groups.find(n)
        for tag, value in zip(("family", "exact", "canonical", "visible"), (family, exact, canonical, visible)):
            if value is not None:
                key = (tag, value)
                if key in first:
                    groups.union(n, first[key])
                else:
                    first[key] = n
    splits, provenance_reasons = {}, {}
    for n, split, base_result in db.execute("SELECT n,split,base_result FROM rows ORDER BY n"):
        root = groups.find(n)
        splits.setdefault(root, set()).add(split)
        provenance_reasons.setdefault(root, set()).update(decode(base_result)["provenance_reasons"])
    conflict_roots = {root for root, values in splits.items() if len(values) > 1}
    duplicate_ids = {row[0] for row in db.execute("SELECT record_id FROM rows WHERE record_id IS NOT NULL GROUP BY record_id HAVING COUNT(*)>1")}
    # Canonical task duplicates within an isolated split retain lexicographically
    # smallest record ID. Visible-only equality is isolation, not same-answer dedup.
    kept = {}
    for n, text in db.execute("SELECT n,base_result FROM rows ORDER BY record_id,n"):
        row = decode(text)
        reasons = set(row["reasons"]) | provenance_reasons[groups.find(n)]
        if groups.find(n) in conflict_roots:
            reasons.add("cross_split_family_or_content")
        if row["record_id"] in duplicate_ids:
            reasons.add("duplicate_record_id")
        status = "reject" if "excluded_rearc" in reasons else row["status"]
        if status != "reject" and reasons:
            status = "quarantine"
        if status == "candidate":
            key = (row["split"], row["canonical"])
            if key in kept:
                status = "deduplicated"
                reasons.add("transform_canonical_duplicate")
            else:
                kept[key] = row["record_id"]
                status = "accepted"
        row.update(status=status, reasons=sorted(reasons), component=groups.find(n))
        with db:
            db.execute("UPDATE rows SET result=? WHERE n=?", (encoded(row).decode(), n))
    return len(conflict_roots)


def _write_json(path, data):
    with path.open("xb") as stream:
        stream.write(encoded(data) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def verify_bundle(path, expected_binding=None):
    path = Path(path)
    manifest = decode((path / "manifest.json").read_bytes())
    seal = manifest.pop("manifest_sha256", None)
    if digest(manifest) != seal:
        raise AdmissionError("manifest_seal_mismatch")
    if expected_binding is not None and manifest["binding"] != expected_binding:
        raise AdmissionError("sealed_binding_mismatch")
    expected = {"manifest.json"} | set(manifest["outputs"])
    actual = {str(p.relative_to(path)) for p in path.rglob("*") if p.is_file()}
    if actual != expected:
        raise AdmissionError("sealed_file_set_mismatch")
    for name, pin in manifest["outputs"].items():
        if file_pin(path / name, pin["bytes"]) != pin:
            raise AdmissionError("sealed_output_pin_mismatch")
    manifest["manifest_sha256"] = seal
    return manifest


def _export(db, registry, root, binding, conflict_count):
    staging = Path(tempfile.mkdtemp(prefix=".export-", dir=root))
    os.chmod(staging, 0o700)
    for part in ("training", "evaluation-inputs", "evaluator-only", "audit"):
        (staging / part).mkdir(mode=0o700)
    names = ["training/train.jsonl", "evaluator-only/gold.jsonl", "audit/decisions.jsonl", "audit/provenance.jsonl"]
    names += [f"evaluation-inputs/{split}.jsonl" for split in sorted(SPLITS - {"train"})]
    counts = {"accepted": 0, "quarantine": 0, "reject": 0, "deduplicated": 0}
    split_counts, queries, gold_queries = {}, {}, {}
    reasons_count = {}
    with contextlib.ExitStack() as stack:
        files = {name: stack.enter_context((staging / name).open("xb")) for name in names}
        def write(name, value):
            files[name].write(encoded(value) + b"\n")
        for n, shard_index, line, offset, length, raw_sha, text in db.execute("SELECT n,shard,line,offset,length,raw_sha,result FROM rows ORDER BY record_id,n"):
            row = decode(text)
            counts[row["status"]] += 1
            for reason in row["reasons"]:
                reasons_count[reason] = reasons_count.get(reason, 0) + 1
            write("audit/decisions.jsonl", {"row": n, "record_id": row["record_id"], "status": row["status"], "reasons": row["reasons"]})
            if row["status"] != "accepted":
                continue
            split, task = row["split"], row["task"]
            split_counts[split] = split_counts.get(split, 0) + 1
            queries[split] = queries.get(split, 0) + len(task["test"])
            if split == "train":
                write("training/train.jsonl", {"record_id": row["record_id"], "task": task})
            else:
                write(f"evaluation-inputs/{split}.jsonl", {"record_id": row["record_id"], "task": prompt_task(task)})
                for index, pair in enumerate(task["test"]):
                    if "output" in pair:
                        write("evaluator-only/gold.jsonl", {"record_id": row["record_id"], "split": split, "test_index": index, "output": pair["output"]})
                        gold_queries[split] = gold_queries.get(split, 0) + 1
            shard = registry.shards[shard_index]
            write("audit/provenance.jsonl", {"record_id": row["record_id"], "source_id": shard["source_id"],
                  "artifact_id": shard["artifact_id"], "artifact_sha256": registry.artifacts[shard["artifact_id"]]["sha256"],
                  "line": line, "byte_offset": offset, "raw_bytes": length, "raw_sha256": raw_sha,
                  "source_locator": row["source_locator"], "lineage_id": row["lineage_id"],
                  "lineage": row["lineage"], "transforms": row["transforms"],
                  "exact_task_sha256": row["exact"], "transform_canonical_sha256": row["canonical"]})
        for stream in files.values():
            stream.flush()
            os.fsync(stream.fileno())
    os.chmod(staging / "evaluator-only/gold.jsonl", 0o600)
    _write_json(staging / "audit/registry.json", registry.data)
    outputs = {str(path.relative_to(staging)): file_pin(path, 1 << 40) for path in sorted(staging.rglob("*")) if path.is_file()}
    manifest = {"schema_version": 1, "tool_version": VERSION, "binding": binding,
                "scope": registry.data["scope"], "status": "prerequisite_window_sealed_not_training_ready",
                "counts": counts, "accepted_by_split": split_counts, "query_counts": queries,
                "evaluation_gold_query_counts": gold_queries, "reason_counts": reasons_count,
                "cross_split_conflict_components": conflict_count, "outputs": outputs,
                "dedup_contract": "exact JSON and joint D4/color-bijection; ordered pairs; no semantic dedup",
                "limits": registry.limits, "limitations": [
                    "Registry provenance/license decisions are supplied reviewed evidence, not independently authenticated facts.",
                    "Only the pinned input window was processed; full upstream corpus counts/bytes remain unverified.",
                    "No program correctness, solver verification, tokenizer, training, model or GPU readiness established.",
                    "Evaluation gold and scratch database require a separate evaluator identity/mount; directory names alone are not access isolation.",
                    "Source exposure is preserved by lineage/splits; no clean hidden generalization claim."]}
    manifest["manifest_sha256"] = digest(manifest)
    _write_json(staging / "manifest.json", manifest)
    verify_bundle(staging, binding)
    os.rename(staging, root / "bundle")
    return manifest


def admit(registry_path, expected_registry_sha256, output_dir, *, limits=None, stop_after_records=None):
    selected = dict(LIMITS)
    if limits:
        if set(limits) - set(selected) or any(type(x) is not int or x < 1 for x in limits.values()):
            raise AdmissionError("invalid_limits")
        selected.update(limits)
    if stop_after_records is not None and (type(stop_after_records) is not int or stop_after_records < 1):
        raise AdmissionError("invalid_stop_after_records")
    registry = Registry(registry_path, expected_registry_sha256, selected)
    binding = {"registry": registry.pin, "tool_sha256": _tool_digest(), "limits": selected}
    root = Path(output_dir)
    if root.is_symlink():
        raise AdmissionError("output_symlink")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if any(p.is_symlink() for p in root.iterdir()):
        raise AdmissionError("output_member_symlink")
    import fcntl  # POSIX build capability; pure schema helpers stay importable.
    with (root / ".lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AdmissionError("build_already_running") from exc
        if (root / "bundle").exists():
            return verify_bundle(root / "bundle", binding)
        if any(p.name not in {".lock", "state.sqlite"} and not p.name.startswith(".export-") for p in root.iterdir()):
            raise AdmissionError("output_not_owned_build")
        db = _connect(root / "state.sqlite", binding)
        os.chmod(root / "state.sqlite", 0o600)
        try:
            prefix_hashes = _validate_staged(db, registry)
            if not _ingest(db, registry, stop_after_records, prefix_hashes):
                return {"status": "paused_not_sealed", "binding": binding,
                        "records_staged": db.execute("SELECT COUNT(*) FROM rows").fetchone()[0]}
            conflicts = _classify(db)
            registry.reverify()
            return _export(db, registry, root, binding, conflicts)
        finally:
            db.close()
