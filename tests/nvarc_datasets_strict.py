"""Real HF preparation checks: multi-parent filtering and retained loader parity."""

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from datasets import Dataset, load_from_disk
from irisx.arc_nvarc_datasets import (SOURCES, audit_synthetic, prepare_augmented, sha_file,
                                    message_accounting)
from irisx.arc_nvarc_training import iter_source_sft_sequences
from irisx.errors import ValidationError
from irisx.canonical import canonical_bytes
from tools.nvarc_datasets import verify_prepared


class DatasetPreparationStrictTests(unittest.TestCase):
    def test_real_hf_filter_preserves_order_and_both_parents_and_rejects_oversize(self):
        messages = [{"role": "user", "content": "12\n34"}, {"role": "assistant", "content": "43\n21"}]
        giant = [{"role": "user" if index % 2 == 0 else "assistant", "content": "1" * 30}
                 for index in range(500)]
        catalog = {"training_ids": ["11111111", "22222222", "44444444"], "arc2_training_ids": ["11111111", "22222222"],
                   "evaluation_ids": ["33333333"], "excluded_parent_ids": ["22222222"],
                   "rearc_generator_ids": ["11111111"], "mini_ids": ["mini-one"], "concept_ids": ["concept-one"]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "synthetic.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                for name in ("nvarc_training/11111111/11111111_11111111.json",
                             "nvarc_training/11111111/11111111_22222222.json",
                             "nvarc_full/33333333/33333333_11111111.json"):
                    stream.writestr(name, json.dumps([{"input": [[1]], "output": [[2]]}]))
            processed = root / "processed"
            _, synthetic = audit_synthetic(archive, catalog, processed / "synthetic")
            raw = root / "raw"
            names = {"arc2_evaluation6": "33333333", "arc2_training": "11111111",
                     "mini": "mini-one", "concept": "concept-one", "rearc": "11111111",
                     "nvarc_training": "11111111_11111111", "nvarc_full": "33333333_11111111"}
            for source, name in names.items():
                rows = [{"puzzle_name": name, "messages": messages}]
                if source == "nvarc_training":
                    rows += [{"puzzle_name": "11111111_22222222", "messages": messages},
                             {"puzzle_name": name, "messages": giant},
                             {"puzzle_name": name, "messages": messages}]
                Dataset.from_list(rows).save_to_disk(str(raw / source))
            inventory = {"members": [{"path": p.relative_to(raw).as_posix(), "sha256": sha_file(p)}
                                      for p in raw.rglob("*") if p.is_file()]}
            prepared = processed / "augmented"
            report = prepare_augmented(raw, inventory, catalog, synthetic, prepared)
            self.assertFalse(report["original_six_source_corpus_ready"])
            summary = report["sources"]["nvarc_training"]
            self.assertEqual({"oversize-episode": 1, "protected-parent": 1, "public-training-only": 2}, summary["counts"])
            lineage = [json.loads(row) for row in (prepared / "nvarc_training/lineage.jsonl").read_text().splitlines()]
            self.assertEqual([0, 3], [row["source_row"] for row in lineage])
            self.assertEqual([["11111111"], ["11111111"]], [row["parent_ids"] for row in lineage])
            filtered = prepared / "nvarc_training/hf"
            self.assertEqual(2, len(load_from_disk(str(filtered))))
            encoded = list(iter_source_sft_sequences(str(filtered)))
            count, supervised = message_accounting(messages)
            self.assertEqual(2 * count, summary["input_tokens"])
            self.assertEqual(2 * supervised, summary["supervised_tokens"])
            self.assertEqual(count, len(encoded[0]["input_ids"]))
            self.assertEqual(supervised, sum(x >= 0 for x in encoded[0]["labels"][1:]))
            self.assertFalse((prepared / "nvarc_full/hf").exists())
            self.assertFalse((prepared / "arc2_evaluation6/hf").exists())
            catalog_path = root / "catalog.json"
            catalog_path.write_bytes(canonical_bytes(catalog, newline=True))
            manifest = {"catalog_sha256": sha_file(catalog_path),
                        "augmented_audit_sha256": sha_file(prepared / "audit.json"),
                        "synthetic_audit_sha256": sha_file(processed / "synthetic/audit.json"),
                        "source_corpus_ready": False}
            (processed / "manifest.json").write_bytes(canonical_bytes(manifest, newline=True))
            self.assertEqual(2, verify_prepared(processed, catalog_path)["sources"]["nvarc_training"]["verified_rows"])
            # Rehashing every metadata envelope cannot substitute a clean but false ancestor.
            lineage[0]["parent_ids"] = ["44444444"]
            lineage_path = prepared / "nvarc_training/lineage.jsonl"
            lineage_path.write_bytes(b"".join(canonical_bytes(row, newline=True) for row in lineage))
            report["sources"]["nvarc_training"]["lineage_sha256"] = sha_file(lineage_path)
            (prepared / "audit.json").write_bytes(canonical_bytes(report, newline=True))
            manifest["augmented_audit_sha256"] = sha_file(prepared / "audit.json")
            (processed / "manifest.json").write_bytes(canonical_bytes(manifest, newline=True))
            with self.assertRaisesRegex(ValidationError, "ancestor exposure"):
                verify_prepared(processed, catalog_path)
            with self.assertRaises(ValidationError):
                prepare_augmented(raw, inventory, catalog, synthetic, prepared)
            (raw / "extra.json").write_text("{}")
            with self.assertRaises(ValidationError):
                prepare_augmented(raw, inventory, catalog, synthetic, root / "tampered")


if __name__ == "__main__":
    unittest.main()
