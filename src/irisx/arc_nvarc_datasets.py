"""Offline inspection of fixed-version NVARC archives and multi-parent lineage.

Network acquisition is deliberately separate. No downloaded program is run.
"""

from __future__ import annotations

import hashlib
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import zipfile

from .canonical import canonical_bytes
from .errors import ValidationError

HEX_ID = re.compile(r"[0-9a-f]{8}")
SOURCES = ("arc2_training", "mini", "concept", "rearc", "nvarc_training", "nvarc_full")


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """Validate the entire archive before any extraction, including Windows paths."""
    found, members = set(), []
    for item in archive.infolist():
        name = item.orig_filename
        path = PurePosixPath(name)
        mode = item.external_attr >> 16
        parts = path.parts
        if (not name or name != item.filename or "\\" in name or ":" in name or path.is_absolute() or
                not parts or any(x in {"", ".", ".."} for x in name.rstrip("/").split("/")) or
                any(x.endswith((".", " ")) or re.fullmatch(
                    r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", x) for x in parts) or
                stat.S_ISLNK(mode) or item.flag_bits & 1):
            raise ValidationError("unsafe archive member")
        key = name.rstrip("/").casefold()
        if key in found:
            raise ValidationError("duplicate archive member")
        found.add(key)
        if not item.is_dir():
            members.append(item)
    files = {x.filename.casefold() for x in members}
    for name in files:
        if any(str(parent).casefold() in files for parent in PurePosixPath(name).parents
               if str(parent) != "."):
            raise ValidationError("archive file is also a directory")
    if not members:
        raise ValidationError("empty archive")
    return members


def inventory_archive(path: Path, output: Path, *, extract: Path | None = None) -> dict:
    """Read every member to verify CRC and SHA; optionally extract into a new tree."""
    if output.exists() or (extract is not None and extract.exists()):
        raise ValidationError("new archive inventory and extraction outputs required")
    with zipfile.ZipFile(path) as archive:
        members = archive_members(archive)
        size = sum(x.file_size for x in members)
        if extract is not None:
            extract.parent.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(extract.parent).free < size + 5 * 1024**3:
                raise ValidationError("archive extraction exceeds available disk reserve")
            extract.mkdir()
        rows = []
        for item in members:
            digest, length = hashlib.sha256(), 0
            target = None
            if extract is not None:
                destination = extract / item.filename
                destination.parent.mkdir(parents=True, exist_ok=True)
                target = destination.open("xb")
            try:
                with archive.open(item) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                        length += len(chunk)
                        if target is not None:
                            target.write(chunk)
            finally:
                if target is not None:
                    target.close()
            if length != item.file_size:
                raise ValidationError("archive member size differs")
            rows.append({"path": item.filename, "bytes": length, "sha256": digest.hexdigest()})
    report = {"format": "irisx/nvarc-archive-inventory-v1", "archive": path.name,
              "archive_bytes": path.stat().st_size, "archive_sha256": sha_file(path),
              "uncompressed_bytes": size, "member_count": len(rows), "members": rows,
              "extracted": extract is not None, "crc_verified": True}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(report, newline=True))
    return report


def synthetic_parents(member: str) -> tuple[str, str, tuple[str, ...]]:
    parts = member.split("/")
    if (len(parts) != 3 or parts[0] not in {"nvarc_training", "nvarc_full"} or
            not parts[-1].endswith(".json")):
        raise ValidationError("unrecognized synthetic member layout")
    name = parts[-1][:-5]
    parents = name.split("_")
    if (len(parents) != 2 or any(HEX_ID.fullmatch(x) is None for x in parents) or
            parts[1] != parents[0]):
        raise ValidationError("synthetic parent/batch naming differs")
    return parts[0], name, tuple(sorted(set(parents)))


def exposure(parents: tuple[str, ...], training: set[str], evaluation: set[str],
             excluded: set[str]) -> str:
    """Every ancestor is checked; a clean first parent cannot mask the second."""
    if not parents or any(x not in training | evaluation for x in parents):
        return "unresolved-lineage"
    if set(parents) & evaluation:
        return "evaluation-derived"
    if set(parents) & excluded:
        return "protected-parent"
    return "public-training-only"


def validate_pairs(value: object) -> int:
    if not isinstance(value, list) or not value:
        raise ValidationError("synthetic pairs must be a nonempty list")
    for pair in value:
        if not isinstance(pair, dict) or set(pair) != {"input", "output"}:
            raise ValidationError("synthetic pair fields differ")
        for grid in pair.values():
            if not isinstance(grid, list) or not 1 <= len(grid) <= 30:
                raise ValidationError("synthetic grid height differs")
            if not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30:
                raise ValidationError("synthetic grid width differs")
            width = len(grid[0])
            if any(not isinstance(row, list) or len(row) != width or
                   any(type(cell) is not int or not 0 <= cell <= 9 for cell in row) for row in grid):
                raise ValidationError("synthetic grid cells or rectangle differ")
    return len(value)


def message_accounting(messages: object) -> tuple[int, int]:
    """Exact compact chat token counts, with rectangle/role/EOS validation."""
    if not isinstance(messages, list) or not messages or len(messages) % 2:
        raise ValidationError("source SFT roles are incomplete")
    tokens, supervised = 0, 0
    for index, message in enumerate(messages):
        if (not isinstance(message, dict) or message.get("role") != ("user" if index % 2 == 0 else "assistant") or
                not isinstance(message.get("content"), str)):
            raise ValidationError("source SFT role or content differs")
        content = message["content"]
        rows = content.split("\n")
        if (not 1 <= len(rows) <= 30 or not 1 <= len(rows[0]) <= 30 or
                any(len(row) != len(rows[0]) for row in rows) or
                re.fullmatch(r"[0-9]+(?:\n[0-9]+)*", content) is None):
            raise ValidationError("source SFT content is not a rectangular grid")
        tokens += len(content) + 4  # begin, role, newline, end
        if index % 2:
            supervised += len(content) + 1  # assistant grid plus end
    return tokens, supervised


def audit_synthetic(archive_path: Path, catalog: dict, output: Path) -> tuple[dict, dict]:
    """Index all published parents; validate pair bytes only for eligible puzzles."""
    if output.exists():
        raise ValidationError("new synthetic audit output required")
    training, evaluation, excluded = (set(catalog[key]) for key in
                                     ("training_ids", "evaluation_ids", "excluded_parent_ids"))
    output.mkdir(parents=True)
    counts, pairs, index = Counter(), Counter(), {}
    with zipfile.ZipFile(archive_path) as archive, (output / "lineage.jsonl").open("wb") as stream:
        for member in archive_members(archive):
            source, name, parents = synthetic_parents(member.filename)
            key = (source, name)
            if key in index:
                raise ValidationError("duplicate synthetic puzzle name")
            status = exposure(parents, training, evaluation, excluded)
            count, problem = None, None
            if status == "public-training-only":
                try:
                    count = validate_pairs(json.loads(archive.read(member)))
                except (ValidationError, ValueError) as exc:
                    status, problem = "invalid-pairs", str(exc)
            row = {"source_id": source, "puzzle_name": name, "parent_ids": list(parents),
                   "member": member.filename, "status": status, "validated_pairs": count}
            if problem is not None:
                row["problem"] = problem
            index[key] = row
            counts[f"{source}/{status}"] += 1
            if count is not None:
                pairs[source] += count
            stream.write(canonical_bytes(row, newline=True))
    report = {"format": "irisx/nvarc-synthetic-lineage-audit-v1", "puzzle_count": len(index),
              "counts": dict(sorted(counts.items())), "eligible_pair_counts": dict(pairs),
              "archive_sha256": sha_file(archive_path),
              "lineage_sha256": sha_file(output / "lineage.jsonl"),
              "lineage_basis": "two ARC IDs in filename, first ID also matches batch; upstream preserves names",
              "semantic_parent_claim_independently_reconstructed": False,
              "programs_executed": 0, "evaluation_pair_contents_inspected": False}
    (output / "audit.json").write_bytes(canonical_bytes(report, newline=True))
    return report, index


def source_lineage(source: str, name: str, catalog: dict, synthetic: dict) -> tuple[tuple[str, ...], str]:
    if source in {"nvarc_training", "nvarc_full"}:
        row = synthetic.get((source, name))
        if row is None:
            return (), "unresolved-lineage"
        return tuple(row["parent_ids"]), row["status"]
    if source == "arc2_evaluation6":
        return (name,), "evaluation-derived" if name in catalog["evaluation_ids"] else "unresolved-lineage"
    if source in {"arc2_training", "rearc"}:
        if source == "rearc" and name not in catalog["rearc_generator_ids"]:
            return (), "unresolved-lineage"
        if source == "arc2_training" and name not in catalog["arc2_training_ids"]:
            return (), "unresolved-lineage"
        return (name,), exposure((name,), set(catalog["training_ids"]),
                                set(catalog["evaluation_ids"]), set(catalog["excluded_parent_ids"]))
    if source in {"mini", "concept"} and name in catalog[f"{source}_ids"]:
        return (f"{source}:{name}",), "public-training-only"
    return (), "unresolved-lineage"


def prepare_augmented(root: Path, inventory: dict, catalog: dict, synthetic: dict,
                      output: Path, *, maximum_length: int = 8192) -> dict:
    """Produce filtered HF sources and row-aligned multi-parent lineage, without training.

    Every eligible row is checked for exact compact grammar/role/token accounting.
    Evaluation and protected ancestors are rejected before message inspection.
    Oversize rows are quarantined intact rather than silently truncated.
    """
    import datasets
    from datasets import load_from_disk

    if output.exists() or type(maximum_length) is not int or maximum_length < 2:
        raise ValidationError("new augmented preparation output and length bound required")
    found = {p.relative_to(root).as_posix(): sha_file(p) for p in root.rglob("*") if p.is_file()}
    if any(p.is_symlink() for p in root.rglob("*")) or found != {
            row["path"]: row["sha256"] for row in inventory["members"]}:
        raise ValidationError("extracted augmented closed inventory differs")
    output.mkdir(parents=True)
    datasets.disable_progress_bars()
    summaries = {}
    for source in ("arc2_evaluation6", *SOURCES):
        dataset = load_from_disk(str(root / source))
        if set(dataset.column_names) != {"puzzle_name", "messages"}:
            raise ValidationError("unexpected augmented columns")
        source_output = output / source
        source_output.mkdir()
        indices, counts, lengths = [], Counter(), Counter()
        token_count, supervised_count, longest = 0, 0, 0
        puzzles, accepted_parents = set(), set()
        with (source_output / "lineage.jsonl").open("wb") as good, (
                source_output / "quarantine.jsonl").open("wb") as bad:
            # Batch conversion is much faster than millions of Dataset.__getitem__ calls.
            for batch_start in range(0, len(dataset), 1000):
                batch = dataset[batch_start:batch_start + 1000]
                for offset, name in enumerate(batch["puzzle_name"]):
                    row_index = batch_start + offset
                    puzzles.add(name)
                    parents, status = source_lineage(source, name, catalog, synthetic)
                    length, supervised, problem = None, None, None
                    if status == "public-training-only":
                        try:
                            length, supervised = message_accounting(batch["messages"][offset])
                            if length > maximum_length:
                                status = "oversize-episode"
                        except ValidationError as exc:
                            status, problem = "invalid-messages", str(exc)
                    record = {"source_row": row_index, "puzzle_name": name,
                              "parent_ids": list(parents), "status": status}
                    if length is not None:
                        record["input_tokens"], record["supervised_tokens"] = length, supervised
                    if problem is not None:
                        record["problem"] = problem
                    counts[status] += 1
                    if status == "public-training-only":
                        indices.append(row_index)
                        accepted_parents.update(parents)
                        token_count += length
                        supervised_count += supervised
                        longest = max(longest, length)
                        lengths[str((length // 1024) * 1024)] += 1
                        good.write(canonical_bytes(record, newline=True))
                    else:
                        bad.write(canonical_bytes(record, newline=True))
        if indices:
            destination = source_output / "hf"
            dataset.select(indices).save_to_disk(str(destination), max_shard_size="500MB")
            if len(load_from_disk(str(destination))) != len(indices):
                raise ValidationError("filtered HF count differs")
            members = [{"path": p.relative_to(destination).as_posix(), "bytes": p.stat().st_size,
                        "sha256": sha_file(p)} for p in sorted(destination.rglob("*")) if p.is_file()]
        else:
            members = []
        summary = {"raw_records": len(dataset), "unique_puzzles": len(puzzles),
                   "counts": dict(sorted(counts.items())), "accepted_records": len(indices),
                   "input_tokens": token_count, "supervised_tokens": supervised_count,
                   "maximum_input_tokens": longest, "input_length_bins": dict(sorted(lengths.items())),
                   "accepted_parent_ids": sorted(accepted_parents), "hf_members": members,
                   "lineage_sha256": sha_file(source_output / "lineage.jsonl"),
                   "quarantine_sha256": sha_file(source_output / "quarantine.jsonl")}
        (source_output / "audit.json").write_bytes(canonical_bytes(summary, newline=True))
        summaries[source] = summary
        print(f"{source}: {len(dataset)} raw, {len(indices)} accepted, {dict(counts)}", flush=True)
    complete = all(summaries[source]["accepted_records"] > 0 for source in SOURCES)
    report = {"format": "irisx/nvarc-augmented-preparation-v1", "policy": "clean-research",
              "maximum_sequence_length": maximum_length, "sources": summaries,
              "original_six_source_corpus_ready": complete,
              "excluded_parent_ids": catalog["excluded_parent_ids"],
              "semantic_overlap": "not-established", "execution_authorized": False,
              "method_contract_modified": False}
    (output / "audit.json").write_bytes(canonical_bytes(report, newline=True))
    return report
