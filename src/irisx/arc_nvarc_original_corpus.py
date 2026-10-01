"""Unfiltered, isolated published NVARC material, separate from clean corpus v1.

HF message bytes are copied intact. Arrow sidecars record every source row,
both parents, all known exposure categories and compact projection counts.
No tokenizer/model download, training, scoring or generated-program execution.
"""

from __future__ import annotations

import ast
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import shutil

from .arc_nvarc_datasets import SOURCES, sha_file, synthetic_parents, source_lineage
from .canonical import canonical_bytes
from .errors import ValidationError

VALIDATION = "arc2_evaluation6"


def validate_contract(contract: dict) -> None:
    if (contract.get("format") != "irisx/nvarc-original-corpus-contract-v1" or
            contract.get("policy") != "original-reproduction" or
            contract.get("namespace") != "nvarc-original" or
            contract.get("material_class") not in {"published-material", "synthetic-fixture"} or
            contract.get("training_sources") != list(SOURCES) or
            contract.get("validation_source") != VALIDATION or
            set(contract.get("expected_records", {})) != {*SOURCES, VALIDATION} or
            any(type(n) is not int or n < 1 for n in contract["expected_records"].values()) or
            contract.get("preparation", {}).get("filter_parents") is not False or
            contract["preparation"].get("maximum_sequence_length") is not None or
            contract["preparation"].get("truncate") is not False or
            contract.get("execution_authorized") is not False or
            contract.get("isolation", {}).get("unexposed_evaluation_claim_allowed") is not False):
        raise ValidationError("original isolated corpus contract differs")
    for key in ("materials", "manifests", "checkpoints", "runs", "results"):
        if contract["isolation"].get(key) != f"nvarc-original/{key}":
            raise ValidationError("original namespace differs")


def closed_files(root: Path) -> dict[str, str]:
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("corpus directory missing or linked")
    files = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValidationError("linked corpus member")
        if path.is_file():
            files[path.relative_to(root).as_posix()] = sha_file(path)
    return files


def member_hashes(inventory: dict) -> dict[str, str]:
    result = {}
    for item in inventory["members"]:
        name = item["path"]
        parts = PurePosixPath(name).parts
        if (not parts or "\\" in name or ":" in name or name.startswith("/") or
                any(x in {"", ".", ".."} for x in name.split("/")) or
                name.casefold() in {x.casefold() for x in result}):
            raise ValidationError("unsafe or duplicate inventory member")
        result[name] = item["sha256"]
    return result


def synthetic_index(inventory: dict) -> dict:
    """Use the closed ZIP inventory as the join key, without executing/reading programs."""
    index = {}
    for member in inventory["members"]:
        source, name, parents = synthetic_parents(member["path"])
        if (source, name) in index:
            raise ValidationError("duplicate synthetic puzzle identity")
        index[source, name] = {"parent_ids": list(parents), "status": "indexed"}
    return index


def parent_metadata(source: str, name: str, catalog: dict, index: dict) -> tuple[list[str], list[str]]:
    parents, status = source_lineage(source, name, catalog, index)
    if not parents or status == "unresolved-lineage":
        raise ValidationError("unresolved original source lineage")
    # Unlike the old clean audit, exposure categories are additive, never filters.
    values = set(parents)
    if source not in {"mini", "concept"} and not values <= set(catalog["training_ids"]) | set(catalog["evaluation_ids"]):
        raise ValidationError("unresolved original ancestor catalog")
    tags = []
    if values & set(catalog["evaluation_ids"]):
        tags.append("arc-evaluation-ancestor")
    if values & set(catalog["excluded_parent_ids"]):
        tags.append("protected-parent-or-visible-family")
    for category, ids in sorted(catalog.get("protected_categories", {}).items()):
        if values & set(ids):
            tags.append(category + "-ancestor")
    if not tags:
        tags.append("public-training-only")
    return list(parents), tags


def arrow_message_accounting(messages):
    """Vectorized full grammar/role validation and exact compact projection counts.

    These counts are not evidence of original Qwen3/NeMo tokenizer parity.
    """
    import numpy as np
    import pyarrow as pa
    import pyarrow.compute as pc

    if (not pa.types.is_list(messages.type) or messages.null_count or
            not pa.types.is_struct(messages.type.value_type) or
            set(messages.type.value_type.names) != {"role", "content"}):
        raise ValidationError("original messages schema differs")
    offsets = messages.offsets.to_numpy(zero_copy_only=False).astype(np.int64)
    offsets -= offsets[0]
    counts = np.diff(offsets)
    if len(counts) == 0 or np.any(counts == 0) or np.any(counts % 2):
        raise ValidationError("original message roles are incomplete")
    values = messages.flatten()
    content, roles = values.field("content"), values.field("role")
    if (values.null_count or content.null_count or roles.null_count or
            content.type != pa.string() or roles.type != pa.string()):
        raise ValidationError("original message content/role schema differs")
    assistant = (np.arange(len(values)) - np.repeat(offsets[:-1], counts)) % 2 == 1
    is_assistant = pc.equal(roles, "assistant").to_numpy(zero_copy_only=False)
    is_user = pc.equal(roles, "user").to_numpy(zero_copy_only=False)
    if not np.all(np.where(assistant, is_assistant, is_user)):
        raise ValidationError("original message roles differ")
    if not pc.all(pc.match_substring_regex(content, r"^[0-9]{1,30}(\n[0-9]{1,30}){0,29}$")).as_py():
        raise ValidationError("original message contains non-grid text or invalid dimensions")
    lines = pc.split_pattern(content, pattern="\n")
    widths = pc.utf8_length(lines.flatten()).to_numpy(zero_copy_only=False)
    line_offsets = lines.offsets.to_numpy(zero_copy_only=False)
    if not np.all(widths == np.repeat(widths[line_offsets[:-1]], np.diff(line_offsets))):
        raise ValidationError("original message grid is not rectangular")
    lengths = pc.utf8_length(content).to_numpy(zero_copy_only=False).astype(np.int64)
    total = np.add.reduceat(lengths + 4, offsets[:-1])
    supervised = np.add.reduceat(np.where(assistant, lengths + 1, 0), offsets[:-1])
    return total, supervised


def source_behavior(source: Path, contract: dict) -> dict:
    """Hash-gated AST/config audit; it does not import NeMo or invent packing behavior."""
    import yaml

    if any(sha_file(source / name) != expected for name, expected in contract["source_files"].items()):
        raise ValidationError("pinned original recipe source differs")
    tree = ast.parse((source / "ARChitects/run_sft.py").read_text(encoding="utf-8"))
    preprocessor = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "sft_preprocessor")
    used = any(isinstance(n, ast.Name) and n.id == "max_seq_length" for n in ast.walk(preprocessor))
    config = yaml.safe_load((source / "ARChitects/sft_mg.yaml").read_bytes())
    if ([Path(p).name for p in config["data"]["train_dataset_path"]] != list(SOURCES) or
            Path(config["data"]["val_dataset_path"]).name != VALIDATION or used):
        raise ValidationError("source loader paths or preprocessor length use differs")
    packing = config["policy"]["sequence_packing"]
    expected = contract["source_recipe"]["packing"]
    if any(packing[k] != expected[k] for k in ("enabled", "algorithm", "sequence_length_round")):
        raise ValidationError("source packing settings differ")
    return {"source_files": contract["source_files"], "recipe": contract["source_recipe"],
            "preprocessor_uses_length_argument": used,
            "nemo_packing_implementation_verified": False,
            "original_tokenizer_parity_verified": False,
            "interpretation": "recipe configured; source NeMo implementation and tokenizer unavailable locally"}


def _schema():
    import pyarrow as pa
    return pa.schema([("source_row", pa.int64()), ("puzzle_name", pa.string()),
                      ("parent_ids", pa.list_(pa.string())), ("exposure_tags", pa.list_(pa.string())),
                      ("compact_input_tokens", pa.int64()), ("compact_supervised_tokens", pa.int64())])


def _batches(dataset):
    if set(dataset.column_names) != {"puzzle_name", "messages"} or len(dataset) < 1:
        raise ValidationError("original HF schema/count differs")
    yield from dataset.data.table.select(["puzzle_name", "messages"]).to_batches(max_chunksize=4096)


def _rows(source, batch, start, catalog, index, cache):
    import numpy as np
    names = batch.column("puzzle_name").to_pylist()
    if any(not isinstance(n, str) or not n for n in names):
        raise ValidationError("original puzzle name differs")
    inputs, supervised = arrow_message_accounting(batch.column("messages"))
    parents, tags = [], []
    for name in names:
        if name not in cache:
            cache[name] = parent_metadata(source, name, catalog, index)
        p, t = cache[name]
        parents.append(p)
        tags.append(t)
    return {"source_row": np.arange(start, start + len(names)), "puzzle_name": names,
            "parent_ids": parents, "exposure_tags": tags,
            "compact_input_tokens": inputs, "compact_supervised_tokens": supervised}


def prepare_original(augmented: Path, augmented_inventory: Path, synthetic_inventory: Path,
                     catalog_path: Path, contract_path: Path, source: Path, output: Path) -> dict:
    """New immutable material tree. Fails closed on unknown ancestry or malformed bytes."""
    import pyarrow as pa
    from datasets import load_from_disk

    contract = json.loads(contract_path.read_bytes())
    validate_contract(contract)
    if output.exists():
        raise ValidationError("new original corpus output required")
    inventories = {"augmented": augmented_inventory, "synthetic": synthetic_inventory}
    for key, path in inventories.items():
        inv = json.loads(path.read_bytes())
        expected = contract["archives"][key]
        if sha_file(path) != expected["inventory_sha256"] or inv["archive_sha256"] != expected["sha256"]:
            raise ValidationError("original archive/inventory binding differs")
    if sha_file(catalog_path) != contract["catalog_sha256"]:
        raise ValidationError("original parent catalog binding differs")
    catalog = json.loads(catalog_path.read_bytes())
    inventory = json.loads(augmented_inventory.read_bytes())
    index = synthetic_index(json.loads(synthetic_inventory.read_bytes()))
    members = member_hashes(inventory)
    if closed_files(augmented) != members:
        raise ValidationError("original augmented closed inventory differs")
    behavior = source_behavior(source, contract)
    output.parent.mkdir(parents=True, exist_ok=True)
    needed = sum((augmented / p).stat().st_size for p in members) + 2 * 1024**3
    if shutil.disk_usage(output.parent).free < needed + 5 * 1024**3:
        raise ValidationError("original corpus exceeds available disk reserve")
    output.mkdir()
    for name, path in {"contract.json": contract_path, "catalog.json": catalog_path,
                       "augmented-inventory.json": augmented_inventory,
                       "synthetic-inventory.json": synthetic_inventory}.items():
        shutil.copyfile(path, output / name)
    for name, expected in members.items():
        target = output / "hf" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(augmented / name, target)
        if sha_file(target) != expected:
            raise ValidationError("copied original HF bytes differ")
    summaries = {}
    (output / "lineage").mkdir()
    for source_id in (*SOURCES, VALIDATION):
        dataset = load_from_disk(str(output / "hf" / source_id))
        if len(dataset) != contract["expected_records"][source_id]:
            raise ValidationError("original source count differs")
        start, total, supervised, maximum = 0, 0, 0, 0
        longest_row, tags, cache = 0, Counter(), {}
        path = output / "lineage" / (source_id + ".arrow")
        with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, _schema()) as writer:
            for batch in _batches(dataset):
                rows = _rows(source_id, batch, start, catalog, index, cache)
                writer.write_table(pa.Table.from_pydict(rows, schema=_schema()))
                lengths = rows["compact_input_tokens"]
                total += int(lengths.sum())
                supervised += int(rows["compact_supervised_tokens"].sum())
                if int(lengths.max()) > maximum:
                    maximum = int(lengths.max())
                    longest_row = start + int(lengths.argmax())
                for exposure in rows["exposure_tags"]:
                    tags.update(exposure)
                start += batch.num_rows
        summaries[source_id] = {"records": start, "unique_puzzles": len(cache),
            "compact_input_tokens": total, "compact_supervised_tokens": supervised,
            "maximum_compact_input_tokens": maximum, "longest_source_row": longest_row,
            "exposure_counts": dict(sorted(tags.items())),
            "parent_ids": sorted({p for parents, _ in cache.values() for p in parents}),
            "filtered_records": 0, "truncated_records": 0}
        print(f"{source_id}: {start} retained, compact tokens {total}, max {maximum}", flush=True)
    manifest = {"format": "irisx/nvarc-original-corpus-v1", "namespace": "nvarc-original",
        "policy": "original-reproduction", "material_class": contract["material_class"],
        "contract_sha256": sha_file(output / "contract.json"), "sources": summaries,
        "training_sources": list(SOURCES), "validation_source": VALIDATION,
        "training_records": sum(summaries[s]["records"] for s in SOURCES),
        "validation_records": summaries[VALIDATION]["records"], "source_behavior": behavior,
        "files": closed_files(output), "preparation_complete": True,
        "original_model_training_ready": False, "full_method_ready": False,
        "execution_authorized": False, "model_calls": 0, "programs_executed": 0,
        "evaluator_files_opened": 0, "unexposed_evaluation_claim_allowed": False}
    (output / "manifest.json").write_bytes(canonical_bytes(manifest, newline=True))
    return manifest


class OriginalCorpusStore:
    """Explicit original/port-only reader. Validation is never concatenated into train."""

    def __init__(self, root: Path, *, expected_manifest_sha256: str, purpose: str):
        if purpose not in {"original-reproduction", "qwen35-port"}:
            raise ValidationError("exposed original corpus cannot enter clean evaluation")
        if sha_file(root / "manifest.json") != expected_manifest_sha256:
            raise ValidationError("original corpus manifest binding differs")
        self.root = root
        self.manifest = json.loads((root / "manifest.json").read_bytes())
        self.contract = json.loads((root / "contract.json").read_bytes())
        validate_contract(self.contract)
        if (self.manifest.get("format") != "irisx/nvarc-original-corpus-v1" or
                self.manifest.get("policy") != "original-reproduction" or
                self.manifest.get("namespace") != "nvarc-original" or
                self.manifest.get("material_class") != self.contract["material_class"] or
                self.manifest.get("training_sources") != list(SOURCES) or
                self.manifest.get("validation_source") != VALIDATION or
                self.manifest.get("contract_sha256") != sha_file(root / "contract.json")):
            raise ValidationError("original corpus identity differs")
        if (self.manifest.get("training_records") != sum(self.contract["expected_records"][s] for s in SOURCES) or
                self.manifest.get("validation_records") != self.contract["expected_records"][VALIDATION] or
                self.manifest.get("preparation_complete") is not True or
                any(self.manifest.get(key) is not False for key in (
                    "original_model_training_ready", "full_method_ready", "execution_authorized",
                    "unexposed_evaluation_claim_allowed"))):
            raise ValidationError("original corpus readiness/count claim differs")
        found = closed_files(root)
        del found["manifest.json"]
        if found != self.manifest["files"]:
            raise ValidationError("original corpus closed inventory differs")
        if (sha_file(root / "catalog.json") != self.contract["catalog_sha256"] or
                closed_files(root / "hf") != member_hashes(json.loads((root / "augmented-inventory.json").read_bytes()))):
            raise ValidationError("original input binding differs")
        for key in ("augmented", "synthetic"):
            path = root / (key + "-inventory.json")
            if sha_file(path) != self.contract["archives"][key]["inventory_sha256"]:
                raise ValidationError("original inventory contract differs")
        self._datasets = {}

    def source(self, source: str):
        from datasets import load_from_disk
        if source not in (*SOURCES, VALIDATION):
            raise ValidationError("unknown original source")
        if source not in self._datasets:
            self._datasets[source] = load_from_disk(str(self.root / "hf" / source))
        if len(self._datasets[source]) != self.contract["expected_records"][source]:
            raise ValidationError("original source count differs")
        return self._datasets[source]

    def load_split(self, split: str):
        from .arc_nvarc_upstream import sft_data_entry
        if split == "train":
            paths = [str(self.root / "hf" / s) for s in SOURCES]
        elif split == "validation":
            paths = str(self.root / "hf" / VALIDATION)
        else:
            raise ValidationError("explicit original train/validation split required")
        return sft_data_entry().load_datasets(paths)


def verify_original(root: Path, *, expected_manifest_sha256: str, source: Path) -> dict:
    """Recheck every row's counts/ancestry and independent compact encoder samples."""
    import numpy as np
    import pyarrow as pa
    from .arc_nvarc_representation import GridTokenizer

    store = OriginalCorpusStore(root, expected_manifest_sha256=expected_manifest_sha256,
                                purpose="original-reproduction")
    catalog = json.loads((root / "catalog.json").read_bytes())
    index = synthetic_index(json.loads((root / "synthetic-inventory.json").read_bytes()))
    if source_behavior(source, store.contract) != store.manifest["source_behavior"]:
        raise ValidationError("original source behavior binding differs")
    summaries, sample_counts = {}, {}
    tokenizer = GridTokenizer(source_chat_newlines=True)
    for source_id in (*SOURCES, VALIDATION):
        dataset, start, total, supervised, maximum = store.source(source_id), 0, 0, 0, 0
        tags, cache, longest = Counter(), {}, 0
        with pa.memory_map(str(root / "lineage" / (source_id + ".arrow")), "r") as mapping:
            reader = pa.ipc.open_file(mapping)
            if reader.schema != _schema():
                raise ValidationError("original lineage schema differs")
            batches = _batches(dataset)
            for i in range(reader.num_record_batches):
                actual = reader.get_batch(i)
                batch = next(batches, None)
                if batch is None:
                    raise ValidationError("original lineage row count differs")
                expected = _rows(source_id, batch, start, catalog, index, cache)
                if not actual.equals(pa.RecordBatch.from_pydict(expected, schema=_schema())):
                    raise ValidationError("original lineage/token/order differs")
                lengths = expected["compact_input_tokens"]
                total += int(lengths.sum())
                supervised += int(expected["compact_supervised_tokens"].sum())
                if int(lengths.max()) > maximum:
                    maximum, longest = int(lengths.max()), start + int(lengths.argmax())
                for exposure in expected["exposure_tags"]:
                    tags.update(exposure)
                start += batch.num_rows
            if next(batches, None) is not None:
                raise ValidationError("original lineage missing rows")
        summary = {"records": start, "unique_puzzles": len(cache), "compact_input_tokens": total,
            "compact_supervised_tokens": supervised, "maximum_compact_input_tokens": maximum,
            "longest_source_row": longest, "exposure_counts": dict(sorted(tags.items())),
            "parent_ids": sorted({p for parents, _ in cache.values() for p in parents}),
            "filtered_records": 0, "truncated_records": 0}
        if summary != store.manifest["sources"][source_id]:
            raise ValidationError("original source summary differs")
        samples = sorted({0, start // 2, start - 1, longest,
                          *[int(x) for x in np.linspace(0, start - 1, min(32, start))]})
        for row_index in samples:
            row = dataset[row_index]
            tokens, labels = [], []
            for i in range(0, len(row["messages"]), 2):
                grids = [[[int(c) for c in line] for line in m["content"].split("\n")]
                         for m in row["messages"][i:i + 2]]
                t, l = tokenizer.encode_pair(*grids)
                tokens.extend(t)
                labels.extend(l)
            counts = arrow_message_accounting(pa.array([row["messages"]], type=dataset.data.column("messages").type))
            if len(tokens) != counts[0][0] or sum(x >= 0 for x in labels[1:]) != counts[1][0]:
                raise ValidationError("independent compact encoder counts differ")
        summaries[source_id], sample_counts[source_id] = summary, len(samples)
    train, validation = store.load_split("train"), store.load_split("validation")
    offset = 0
    for source_id in SOURCES:
        local = store.source(source_id)
        for idx in (0, len(local) - 1):
            if train[offset + idx] != local[idx]:
                raise ValidationError("actual upstream concatenation order differs")
        offset += len(local)
    if len(train) != offset or len(validation) != len(store.source(VALIDATION)):
        raise ValidationError("actual upstream train/validation counts differ")
    # Exercise the actual HF shuffle used in source main, on the complete index.
    shuffled = train.shuffle(seed=store.contract["source_recipe"]["shuffle_seed"], keep_in_memory=True)
    positions = shuffled._indices.column(0).to_numpy()
    expected_positions = np.random.default_rng(store.contract["source_recipe"]["shuffle_seed"]).permutation(len(train))
    if not np.array_equal(positions, expected_positions):
        raise ValidationError("source shuffle index differs")
    return {"format": "irisx/nvarc-original-corpus-verification-v1",
        "manifest_sha256": expected_manifest_sha256, "contract_sha256": store.manifest["contract_sha256"],
        "verified_training_records": len(train), "verified_validation_records": len(validation),
        "sources": summaries, "independent_compact_encoder_samples": sample_counts,
        "actual_upstream_loader_verified": True, "full_seed24_shuffle_verified": True,
        "material_preparation_ready": store.contract["material_class"] == "published-material",
        "packing_backend_verified": False, "original_tokenizer_parity_verified": False,
        "original_model_training_ready": False, "full_method_ready": False,
        "execution_authorized": False, "model_calls": 0, "evaluator_files_opened": 0,
        "code_sha256": sha_file(Path(__file__))}
