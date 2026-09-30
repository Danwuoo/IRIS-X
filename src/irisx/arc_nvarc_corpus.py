"""Offline, lineage-bound import of the source SFT mixture into sequence shards."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .arc_nvarc_training import FrozenSequenceStore, iter_source_sft_sequences
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError

SOURCES = ("arc2_training", "mini", "concept", "rearc", "nvarc_training", "nvarc_full")


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_inventory(root: Path, members: list[dict]) -> None:
    if not root.is_dir() or root.is_symlink() or not members:
        raise ValidationError("source corpus inventory is missing")
    expected = {}
    for item in members:
        name = item["path"]
        path = Path(name)
        if (not isinstance(name, str) or path.is_absolute() or ".." in path.parts or
                "\\" in name or ":" in name or name in expected):
            raise ValidationError("unsafe or duplicate corpus inventory member")
        expected[name] = item["sha256"]
    found = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValidationError("source corpus contains a symlink")
        if path.is_file():
            found[path.relative_to(root).as_posix()] = sha_file(path)
    if found != expected:
        raise ValidationError("source corpus closed inventory differs")


def freeze_source_corpus(spec_path: Path, output: Path, *, shard_records: int = 8192) -> dict:
    """Stream all six HF sources, rejecting missing lineage and excluded parents.

    Each source has a digest-bound JSONL lineage row in the same order as its
    dataset. No parent ID is guessed from an augmented puzzle name. Declared
    lineage does not establish absence of unknown semantic overlap.
    """
    spec = json.loads(spec_path.read_bytes())
    if (spec.get("format") != "irisx/nvarc-source-corpus-spec-v1" or
            spec.get("policy") != "clean-research" or output.exists() or
            spec.get("material_class") not in {"synthetic-fixture", "source-material"} or
            type(shard_records) is not int or shard_records < 1):
        raise ValidationError("new output and clean source corpus spec required")
    sources = spec.get("sources", [])
    if [item.get("source_id") for item in sources] != list(SOURCES):
        raise ValidationError("complete ordered six-source SFT mixture required")
    excluded = spec.get("excluded_parent_ids")
    if (not isinstance(excluded, list) or not excluded or
            any(not isinstance(x, str) or not x for x in excluded)):
        raise ValidationError("explicit development and locked parent exclusions required")
    excluded = set(excluded)
    max_length = spec.get("max_sequence_length")
    if type(max_length) is not int or max_length < 2:
        raise ValidationError("corpus sequence bound required")
    resolved = []
    for item in sources:
        if (item.get("exposure") != "public-training-only" or
                type(item.get("records")) is not int or item["records"] < 1):
            raise ValidationError("unknown training exposure or source count")
        if spec["material_class"] == "source-material":
            provenance = item.get("provenance", {})
            if any(not isinstance(provenance.get(k), str) or not provenance[k]
                   for k in ("origin", "revision", "lineage_basis")):
                raise ValidationError("actual source provenance and lineage basis required")
        dataset = spec_path.parent / item["dataset_path"]
        lineage = spec_path.parent / item["lineage_path"]
        verify_inventory(dataset, item["members"])
        if lineage.is_symlink() or sha_file(lineage) != item["lineage_sha256"]:
            raise ValidationError("source lineage digest differs")
        resolved.append((item, dataset, lineage))
    output.mkdir(parents=True)
    (output / "source-spec.json").write_bytes(canonical_bytes(spec, newline=True))
    shards, counts, total, tokens, supervised, longest = [], {}, 0, 0, 0, 0
    stream = None
    local_count = 0
    try:
        for item, dataset, lineage in resolved:
            count = 0
            with lineage.open("r", encoding="utf-8") as parents:
                for sequence in iter_source_sft_sequences(str(dataset)):
                    row = parents.readline()
                    if not row:
                        raise ValidationError("source lineage ends before dataset")
                    parent = json.loads(row)
                    if (parent.get("puzzle_name") != sequence["source"] or
                            not isinstance(parent.get("parent_id"), str) or not parent["parent_id"] or
                            parent["parent_id"] in excluded):
                        raise ValidationError("source row lineage or split exclusion differs")
                    length = len(sequence["input_ids"])
                    if length > max_length:
                        raise ValidationError("SFT episode exceeds sequence bound; no silent truncation")
                    if stream is None:
                        shard = output / f"sequences-{len(shards):05d}.jsonl"
                        stream = shard.open("wb")
                        local_count = 0
                    record = {**sequence, "source_id": item["source_id"], "parent_id": parent["parent_id"]}
                    stream.write(canonical_bytes(record, newline=True))
                    count += 1
                    total += 1
                    local_count += 1
                    tokens += length
                    longest = max(longest, length)
                    supervised += sum(label >= 0 for label in sequence["labels"][1:])
                    if local_count == shard_records:
                        stream.close()
                        stream = None
                        shards.append({"path": shard.name, "sha256": sha_file(shard), "records": local_count})
                if parents.readline():
                    raise ValidationError("source lineage has extra rows")
            if count != item["records"]:
                raise ValidationError("source mixture count differs")
            counts[item["source_id"]] = count
        if stream is not None:
            stream.close()
            stream = None
            shards.append({"path": shard.name, "sha256": sha_file(shard), "records": local_count})
    finally:
        if stream is not None:
            stream.close()
    manifest = {"format": "irisx/nvarc-source-sequences-v1", "spec_digest": digest_value(spec),
        "material_class": spec["material_class"],
        "source_counts": counts, "record_count": total, "input_tokens": tokens,
        "supervised_tokens": supervised, "maximum_sequence_tokens": longest,
        "excluded_parent_ids": sorted(excluded), "policy": "clean-research",
        "semantic_overlap": "not-established", "shards": shards}
    (output / "manifest.json").write_bytes(canonical_bytes(manifest, newline=True))
    return manifest


class FrozenSourceSequenceStore(FrozenSequenceStore):
    """Verified indexed source sequences consumed by the existing full-SFT entry."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.manifest = json.loads((root / "manifest.json").read_bytes())
        manifest = self.manifest
        spec = json.loads((root / "source-spec.json").read_bytes())
        if (manifest.get("format") != "irisx/nvarc-source-sequences-v1" or
                set(manifest.get("source_counts", {})) != set(SOURCES) or
                manifest.get("policy") != "clean-research" or
                manifest.get("material_class") not in {"synthetic-fixture", "source-material"} or
                spec.get("material_class") != manifest["material_class"] or
                digest_value(spec) != manifest["spec_digest"] or
                spec.get("excluded_parent_ids") is None or
                sorted(set(spec["excluded_parent_ids"])) != manifest["excluded_parent_ids"] or
                [s.get("source_id") for s in spec.get("sources", [])] != list(SOURCES)):
            raise ValidationError("complete frozen source sequence mixture required")
        self.index = []
        self.parent_ids = set()
        from .arc_nvarc_representation import GridTokenizer
        tokenizer = GridTokenizer(source_chat_newlines=True)
        counts = {key: 0 for key in SOURCES}
        tokens = supervised = longest = 0
        names = set()
        for shard in manifest["shards"]:
            path = root / shard["path"]
            if path.parent != root or path.is_symlink() or shard["path"] in names:
                raise ValidationError("unsafe or repeated sequence shard")
            names.add(shard["path"])
            if sha_file(path) != shard["sha256"]:
                raise ValidationError("frozen source sequence digest differs")
            offset, count = 0, 0
            with path.open("rb") as stream:
                for line in stream:
                    row = json.loads(line)
                    if (row["source_id"] not in counts or
                            not isinstance(row["parent_id"], str) or not row["parent_id"] or
                            row["parent_id"] in manifest["excluded_parent_ids"] or
                            not isinstance(row["source"], str) or not row["source"] or
                            len(row["input_ids"]) != len(row["labels"]) or
                            len(row["input_ids"]) > spec["max_sequence_length"] or
                            not any(x >= 0 for x in row["labels"][1:]) or
                            any(type(x) is not int or not 0 <= x < 16 for x in row["input_ids"]) or
                            any(type(x) is not int or x != -100 and x != token
                                for x, token in zip(row["labels"], row["input_ids"]))):
                        raise ValidationError("frozen source row semantics differ")
                    cursor, expected_labels = 0, []
                    ids = row["input_ids"]
                    try:
                        while cursor < len(ids):
                            if ids[cursor:cursor+3] != [14, 11, 10]:
                                raise ValidationError("source user header differs")
                            user_end = ids.index(15, cursor+3)
                            tokenizer.decode_grid(ids[cursor+3:user_end])
                            if ids[user_end+1:user_end+4] != [14, 12, 10]:
                                raise ValidationError("source assistant header differs")
                            answer_end = ids.index(15, user_end+4)
                            tokenizer.decode_grid(ids[user_end+4:answer_end])
                            expected_labels.extend([-100] * (user_end+4-cursor))
                            expected_labels.extend(ids[user_end+4:answer_end+1])
                            cursor = answer_end+1
                    except ValueError as exc:
                        raise ValidationError("source message has no EOS") from exc
                    if expected_labels != row["labels"]:
                        raise ValidationError("source assistant-only loss mask differs")
                    tokens += len(ids)
                    supervised += sum(x >= 0 for x in row["labels"][1:])
                    longest = max(longest, len(ids))
                    self.index.append((path, offset))
                    self.parent_ids.add(row["parent_id"])
                    offset += len(line)
                    count += 1
                    counts[row["source_id"]] += 1
            if count != shard["records"]:
                raise ValidationError("source shard count differs")
        if counts != manifest["source_counts"] or len(self.index) != manifest["record_count"] or not self.index:
            raise ValidationError("source mixture counts differ")
        if (any(count < 1 for count in counts.values()) or
                tokens != manifest["input_tokens"] or supervised != manifest["supervised_tokens"] or
                longest != manifest["maximum_sequence_tokens"] or
                {p.name for p in root.iterdir()} != names | {"manifest.json", "source-spec.json"}):
            raise ValidationError("source token accounting or closed output inventory differs")
        self.data_digest = digest_value(manifest)

    def __getitem__(self, index: int) -> dict:
        path, offset = self.index[index]
        with path.open("rb") as stream:
            stream.seek(offset)
            return json.loads(stream.readline())
