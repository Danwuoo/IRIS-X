"""Offline full original corpus preparation, separate from clean material v1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from irisx.arc_nvarc_original_corpus import prepare_original, verify_original
from irisx.arc_nvarc_datasets import sha_file
from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError

CONTRACT = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/original-corpus-contract-20261001.json"
SOURCE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/source/NVARC"


def isolated(path: Path, category: str) -> Path:
    path = path.resolve()
    boundary = (ROOT / ".irisx/nvarc-original" / category).resolve()
    if path == boundary or not path.is_relative_to(boundary):
        raise ValidationError("new output must remain in its original reproduction namespace")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    for name in ("augmented", "augmented-archive", "augmented-inventory", "synthetic-archive",
                 "synthetic-inventory", "catalog", "output"):
        prepare.add_argument("--" + name, type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--corpus", type=Path, required=True)
    verify.add_argument("--manifest-sha256", required=True)
    verify.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            output = isolated(args.output, "materials")
            if output.exists():
                raise ValidationError("new original corpus output required")
            contract = json.loads(CONTRACT.read_bytes())
            for key in ("augmented", "synthetic"):
                if sha_file(getattr(args, key + "_archive")) != contract["archives"][key]["sha256"]:
                    raise ValidationError("retained raw archive digest differs")
            report = prepare_original(args.augmented, args.augmented_inventory, args.synthetic_inventory,
                                      args.catalog, CONTRACT, SOURCE, output)
            summary = {"manifest_sha256": sha_file(output / "manifest.json"),
                       "training_records": report["training_records"],
                       "validation_records": report["validation_records"],
                       "preparation_complete": report["preparation_complete"],
                       "original_model_training_ready": False}
        else:
            output = isolated(args.output, "manifests")
            if output.exists():
                raise ValidationError("new original verification output required")
            report = verify_original(isolated(args.corpus, "materials"),
                                     expected_manifest_sha256=args.manifest_sha256, source=SOURCE)
            if report["contract_sha256"] != sha_file(CONTRACT):
                raise ValidationError("verification is not bound to the published original contract")
            report["tool_sha256"] = sha_file(Path(__file__))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(canonical_bytes(report, newline=True))
            summary = {"verification_sha256": sha_file(output),
                       "verified_training_records": report["verified_training_records"],
                       "verified_validation_records": report["verified_validation_records"],
                       "material_preparation_ready": report["material_preparation_ready"],
                       "original_model_training_ready": False}
        print(json.dumps(summary, indent=2))
        return 0
    except (ValidationError, OSError, ValueError, KeyError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
