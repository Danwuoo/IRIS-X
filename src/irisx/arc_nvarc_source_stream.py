"""Lazy, lineage-preserving compact sequences in the complete source shuffle.

Only the index permutation is resident. Messages and sidecars are memory mapped;
validation stays in a distinct split. No parent filtering or length truncation.
"""
from __future__ import annotations

from bisect import bisect_right
from pathlib import Path

from .arc_nvarc_original_corpus import OriginalCorpusStore, SOURCES, VALIDATION, _schema
from .arc_nvarc_representation import GridTokenizer
from .canonical import digest_value
from .errors import ValidationError


class OriginalSequenceStream:
    def __init__(self, root: Path, manifest_sha256: str, *, split: str = "train", representation="qwen35"):
        import numpy as np
        import pyarrow as pa
        if split not in {"train", "validation"}:
            raise ValidationError("explicit original corpus split required")
        if representation not in {"qwen35", "original-qwen3"}:
            raise ValidationError("explicit source representation required")
        self.representation = representation
        self.store = OriginalCorpusStore(root, expected_manifest_sha256=manifest_sha256,
                                         purpose="original-reproduction" if representation == "original-qwen3" else "qwen35-port")
        self.split, self.manifest_sha256 = split, manifest_sha256
        self.sources = list(SOURCES) if split == "train" else [VALIDATION]
        self.ends, self._lineage, count = [], {}, 0
        self.tokenizer = GridTokenizer(source_chat_newlines=True)
        try:
            for source in self.sources:
                mapping = pa.memory_map(str(root / "lineage" / (source + ".arrow")), "r")
                reader = pa.ipc.open_file(mapping)
                if reader.schema != _schema():
                    mapping.close()
                    raise ValidationError("source sequence lineage schema differs")
                ends, rows = [], 0
                for index in range(reader.num_record_batches):
                    rows += reader.get_batch(index).num_rows
                    ends.append(rows)
                if rows != self.store.contract["expected_records"][source]:
                    mapping.close()
                    raise ValidationError("source sequence lineage count differs")
                self._lineage[source] = (mapping, reader, ends)
                count += rows
                self.ends.append(count)
            self.order = (np.random.default_rng(self.store.contract["source_recipe"]["shuffle_seed"])
                          .permutation(count) if split == "train" else np.arange(count))
            self.identity_digest = digest_value({"corpus_manifest_sha256": manifest_sha256,
                "split": split, "source_order": self.sources, "records": count,
                "shuffle_seed": self.store.contract["source_recipe"]["shuffle_seed"] if split == "train" else None,
                "order_sha256": __import__('hashlib').sha256(self.order.astype('<i8').tobytes()).hexdigest(),
                "representation": "original-qwen3-source-16-wordlevel" if representation == "original-qwen3"
                                  else "qwen35-compact-source-chat-newlines"})
        except BaseException:
            self.close()
            raise

    def __len__(self):
        return len(self.order)

    def __getitem__(self, position: int) -> dict:
        if type(position) is not int or not 0 <= position < len(self):
            raise ValidationError("source shuffle position outside the single epoch")
        raw_index = int(self.order[position])
        source_index = bisect_right(self.ends, raw_index)
        source = self.sources[source_index]
        source_row = raw_index - (self.ends[source_index - 1] if source_index else 0)
        _, reader, ends = self._lineage[source]
        batch_index = bisect_right(ends, source_row)
        offset = source_row - (ends[batch_index - 1] if batch_index else 0)
        lineage = reader.get_batch(batch_index).slice(offset, 1).to_pylist()[0]
        row = self.store.source(source)[source_row]
        if lineage["source_row"] != source_row or lineage["puzzle_name"] != row["puzzle_name"]:
            raise ValidationError("source message and lineage row differ")
        tokens, labels = [], []
        for index in range(0, len(row["messages"]), 2):
            pair = row["messages"][index:index + 2]
            if [value["role"] for value in pair] != ["user", "assistant"]:
                raise ValidationError("source message role order differs")
            if self.representation == "original-qwen3":
                from .arc_nvarc_qwen3_sft import encode_source_pair
                ids, targets = encode_source_pair(pair)
            else:
                grids = [[[int(c) for c in line] for line in value["content"].split("\n")] for value in pair]
                ids, targets = self.tokenizer.encode_pair(*grids)
            tokens.extend(ids)
            labels.extend(targets)
        if (len(tokens) != lineage["compact_input_tokens"] or
                sum(value >= 0 for value in labels[1:]) != lineage["compact_supervised_tokens"]):
            raise ValidationError("whole source sequence counts differ")
        return {"source_id": source, "source_row": source_row, "puzzle_name": row["puzzle_name"],
            "parent_ids": lineage["parent_ids"], "exposure_tags": lineage["exposure_tags"],
            "shuffle_position": position, "input_ids": tokens, "labels": labels}

    def batch(self, cursor: int, size: int, *, rank: int = 0, world: int = 1) -> list[dict]:
        if (self.split != "train" or type(cursor) is not int or cursor < 0 or
                type(size) is not int or size < 1 or cursor + size > len(self) or
                type(world) is not int or world < 1 or type(rank) is not int or not 0 <= rank < world):
            raise ValidationError("source batch cannot wrap, filter or cross validation")
        return [self[index] for index in range(cursor + rank, cursor + size, world)]

    def close(self):
        for mapping, _, _ in getattr(self, "_lineage", {}).values():
            mapping.close()
        self._lineage = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
