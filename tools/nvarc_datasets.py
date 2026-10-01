"""Deliberate offline NVARC dataset inventory/extraction (no network or execution)."""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from irisx.arc_nvarc_datasets import (inventory_archive, audit_synthetic, prepare_augmented, sha_file)
from irisx.arc_prompt_pilot import BASELINE_SPLIT_DIGEST, near_duplicate_fingerprint
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError


def verify_prepared(root: Path, catalog_path: Path) -> dict:
    """Independently check output digests, both ancestors and real-loader samples."""
    from datasets import load_from_disk
    from irisx.arc_nvarc_datasets import SOURCES, source_lineage
    from irisx.arc_nvarc_training import iter_source_sft_sequences
    manifest = json.loads((root / "manifest.json").read_bytes())
    catalog = json.loads(catalog_path.read_bytes())
    if (manifest["catalog_sha256"] != sha_file(catalog_path) or
            manifest["augmented_audit_sha256"] != sha_file(root / "augmented/audit.json") or
            manifest["synthetic_audit_sha256"] != sha_file(root / "synthetic/audit.json")):
        raise ValidationError("processing manifest binding differs")
    report = json.loads((root / "augmented/audit.json").read_bytes())
    synthetic_report = json.loads((root / "synthetic/audit.json").read_bytes())
    if sha_file(root / "synthetic/lineage.jsonl") != synthetic_report["lineage_sha256"]:
        raise ValidationError("synthetic parent index digest differs")
    synthetic = {}
    with (root / "synthetic/lineage.jsonl").open(encoding="utf-8") as stream:
        for raw in stream:
            row = json.loads(raw)
            synthetic[(row["source_id"], row["puzzle_name"])] = row
    protected = set(catalog["excluded_parent_ids"])
    checks = {}
    for source, summary in report["sources"].items():
        location = root / "augmented" / source
        for name in ("lineage", "quarantine"):
            if sha_file(location / (name + ".jsonl")) != summary[name + "_sha256"]:
                raise ValidationError("prepared lineage/quarantine digest differs")
        if not summary["accepted_records"]:
            if (location / "hf").exists():
                raise ValidationError("quarantined source has an HF training export")
            continue
        destination = location / "hf"
        found = {p.relative_to(destination).as_posix(): sha_file(p)
                 for p in destination.rglob("*") if p.is_file()}
        if found != {row["path"]: row["sha256"] for row in summary["hf_members"]}:
            raise ValidationError("prepared HF closed inventory differs")
        dataset = load_from_disk(str(destination))
        names = iter(dataset.data.column("puzzle_name").to_pylist())
        count, tokens, supervised, previous = 0, 0, 0, -1
        with (location / "lineage.jsonl").open(encoding="utf-8") as stream:
            for raw in stream:
                row = json.loads(raw)
                parents = row["parent_ids"]
                if (next(names, None) != row["puzzle_name"] or row["source_row"] <= previous or
                        not parents or set(parents) & protected or
                        row["status"] != "public-training-only" or
                        not 0 < row["input_tokens"] <= report["maximum_sequence_length"] or
                        not 0 < row["supervised_tokens"] < row["input_tokens"]):
                    raise ValidationError("prepared row/split/order differs")
                expected_parents, expected_status = source_lineage(source, row["puzzle_name"], catalog, synthetic)
                if list(expected_parents) != parents or expected_status != "public-training-only":
                    raise ValidationError("prepared ancestor exposure differs")
                previous = row["source_row"]
                count += 1
                tokens += row["input_tokens"]
                supervised += row["supervised_tokens"]
        if (next(names, None) is not None or count != len(dataset) or count != summary["accepted_records"] or
                tokens != summary["input_tokens"] or supervised != summary["supervised_tokens"]):
            raise ValidationError("prepared row/token counts differ")
        sample_count = 0
        for encoded in iter_source_sft_sequences(str(destination), maximum_records=32):
            if len(encoded["input_ids"]) > report["maximum_sequence_length"]:
                raise ValidationError("real upstream loader sample exceeds context")
            sample_count += 1
        checks[source] = {"verified_rows": count, "real_loader_samples": sample_count}
    if manifest["source_corpus_ready"] != all(source in checks for source in SOURCES):
        raise ValidationError("complete six-source readiness claim differs")
    return {"format": "irisx/nvarc-dataset-verification-v1", "processing_manifest_sha256": sha_file(root / "manifest.json"),
            "catalog_sha256": sha_file(catalog_path), "sources": checks,
            "code_sha256": {"tool": sha_file(Path(__file__)),
                            "module": sha_file(ROOT / "src/irisx/arc_nvarc_datasets.py")},
            "source_corpus_ready": manifest["source_corpus_ready"], "execution_authorized": False}


def build_catalog(source: Path, split_path: Path, comparison_path: Path, output: Path) -> dict:
    if output.exists():
        raise ValidationError("new catalog required")
    split, comparison = (json.loads(p.read_bytes()) for p in (split_path, comparison_path))
    if digest_value(split) != BASELINE_SPLIT_DIGEST:
        raise ValidationError("frozen locked split differs")
    if (comparison.get("format") != "irisx/nvarc-method-comparison-proposal-v1" or
            len(comparison.get("dev_parent_ids", [])) != 8):
        raise ValidationError("bound provisional comparison required")
    pilot = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/m2-m3-small.json"
    old = json.loads(pilot.read_bytes())
    categories = {"pilot": sorted(x["id"] for x in old["train"] + old["dev"]),
                  "provisional_dev": comparison["dev_parent_ids"],
                  "locked_holdout": sorted(x["task_id"] for x in split["records"]
                                           if x["group"] == "locked-holdout"),
                  "prior_smoke": split["excluded_smoke_task_ids"]}
    excluded = {x for group in categories.values() for x in group}
    arc = source / "NVARC/external/ARC-AGI-2/data"
    training = sorted(p.stem for p in (arc / "training").glob("*.json"))
    evaluation = sorted(p.stem for p in (arc / "evaluation").glob("*.json"))
    if len(training) != 1000 or len(evaluation) != 120 or not excluded <= set(training):
        raise ValidationError("source ARC catalogs or protected parents differ")
    # Close known visible color-renamed duplicate families without scoring test outputs.
    families = defaultdict(set)
    for path in sorted((arc / "training").glob("*.json")):
        task = json.loads(path.read_bytes())
        visible = {"train": task["train"], "test": [{"input": x["input"]} for x in task["test"]]}
        families[near_duplicate_fingerprint(visible)].add(path.stem)
    for ids in families.values():
        if ids & excluded:
            excluded.update(ids)
    generators = source / "NVARC/external/re-arc/generators.py"
    tree = ast.parse(generators.read_text(encoding="utf-8"))
    generator_ids = sorted(node.name[len("generate_"):] for node in tree.body
                           if isinstance(node, ast.FunctionDef) and node.name.startswith("generate_"))
    original_archive = source / "NVARC/external/re-arc/arc_original.zip"
    with zipfile.ZipFile(original_archive) as archive:
        original_training = sorted(Path(name).stem for name in archive.namelist()
            if name.startswith("arc_original/training/") and name.endswith(".json"))
    if len(generator_ids) != 400 or generator_ids != original_training:
        raise ValidationError("re-ARC generator catalog differs")
    contract = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/method-contract-20260930.json"
    catalog = {"format": "irisx/nvarc-dataset-parent-catalog-v1",
               "training_ids": sorted(set(training) | set(original_training)),
               "arc2_training_ids": training, "arc1_training_ids": original_training,
               "evaluation_ids": evaluation, "rearc_generator_ids": generator_ids,
               "mini_ids": sorted(p.stem for p in (source / "NVARC/external/MINI-ARC/data/MiniARC").glob("*.json")),
               "concept_ids": sorted(p.stem for p in (source / "NVARC/external/ConceptARC/corpus").rglob("*.json")),
               "excluded_parent_ids": sorted(excluded), "protected_categories": categories,
               "split_digest": digest_value(split), "comparison_sha256": sha_file(comparison_path),
               "pilot_sha256": sha_file(pilot), "method_contract_sha256": sha_file(contract),
               "rearc_generator_source_sha256": sha_file(generators),
               "arc1_original_archive_sha256": sha_file(original_archive),
               "nvarc_source_commit": json.loads(contract.read_bytes())["source"]["nvarc_commit"],
               "cross_source_semantic_overlap": "not-established"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(catalog, newline=True))
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("inventory-archive")
    item.add_argument("--archive", type=Path, required=True)
    item.add_argument("--output", type=Path, required=True)
    item.add_argument("--extract", type=Path)
    item = sub.add_parser("verify-prepared")
    item.add_argument("--prepared", type=Path, required=True)
    item.add_argument("--catalog", type=Path, required=True)
    item.add_argument("--output", type=Path, required=True)
    item = sub.add_parser("build-catalog")
    item.add_argument("--source", type=Path, required=True)
    item.add_argument("--protected-split", type=Path, required=True)
    item.add_argument("--comparison", type=Path, required=True)
    item.add_argument("--output", type=Path, required=True)
    item = sub.add_parser("prepare")
    item.add_argument("--augmented", type=Path, required=True)
    item.add_argument("--augmented-inventory", type=Path, required=True)
    item.add_argument("--synthetic-archive", type=Path, required=True)
    item.add_argument("--synthetic-inventory", type=Path, required=True)
    item.add_argument("--catalog", type=Path, required=True)
    item.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "inventory-archive":
        result = inventory_archive(args.archive, args.output, extract=args.extract)
        print({key: value for key, value in result.items() if key != "members"})
    elif args.command == "build-catalog":
        result = build_catalog(args.source, args.protected_split, args.comparison, args.output)
        print({key: len(value) for key, value in result.items() if key.endswith("_ids")})
    elif args.command == "verify-prepared":
        if args.output.exists():
            raise ValidationError("new verification output required")
        result = verify_prepared(args.prepared, args.catalog)
        args.output.write_bytes(canonical_bytes(result, newline=True))
        print(result)
    else:
        if args.output.exists():
            raise ValidationError("new processing identity required")
        synthetic_inventory = json.loads(args.synthetic_inventory.read_bytes())
        if sha_file(args.synthetic_archive) != synthetic_inventory["archive_sha256"]:
            raise ValidationError("synthetic ZIP binding differs")
        catalog = json.loads(args.catalog.read_bytes())
        args.output.mkdir(parents=True)
        synthetic_report, index = audit_synthetic(args.synthetic_archive, catalog, args.output / "synthetic")
        print("synthetic:", synthetic_report["counts"], flush=True)
        augmented_report = prepare_augmented(args.augmented,
            json.loads(args.augmented_inventory.read_bytes()), catalog, index, args.output / "augmented")
        result = {"format": "irisx/nvarc-dataset-processing-v1", "decision": "0049",
                  "catalog_sha256": sha_file(args.catalog),
                  "synthetic_inventory_sha256": sha_file(args.synthetic_inventory),
                  "augmented_inventory_sha256": sha_file(args.augmented_inventory),
                  "synthetic_audit_sha256": sha_file(args.output / "synthetic/audit.json"),
                  "augmented_audit_sha256": sha_file(args.output / "augmented/audit.json"),
                  "source_corpus_ready": augmented_report["original_six_source_corpus_ready"],
                  "accepted_sources": [s for s, r in augmented_report["sources"].items() if r["accepted_records"]],
                  "model_calls": 0, "program_executions": 0, "paid_cost_usd": 0,
                  "execution_authorized": False}
        (args.output / "manifest.json").write_bytes(canonical_bytes(result, newline=True))
        print(result)


if __name__ == "__main__":
    main()
