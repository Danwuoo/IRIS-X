"""Real Arrow/HF original material checks, deliberately separate from frozen ML proof."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pyarrow as pa
from datasets import Dataset, disable_progress_bars

from irisx.arc_nvarc_original_corpus import (SOURCES, VALIDATION, arrow_message_accounting,
    prepare_original, verify_original, OriginalCorpusStore)
from irisx.arc_nvarc_datasets import sha_file, message_accounting
from irisx.arc_nvarc_representation import GridTokenizer
from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/original-corpus-contract-20261001.json"
SOURCE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/source/NVARC"
TYPE = pa.list_(pa.struct([("content", pa.string()), ("role", pa.string())]))
SMALL = [{"role": "user", "content": "12\n34"}, {"role": "assistant", "content": "43\n21"}]
GIANT = [{"role": "user" if i % 2 == 0 else "assistant", "content": "1" * 30} for i in range(500)]


class OriginalCorpusStrictTests(unittest.TestCase):
    def test_arrow_accounting_matches_python_and_encoder_with_sliced_arrays(self):
        array = pa.array([SMALL, GIANT, SMALL + SMALL], type=TYPE)
        for values in (array, array.slice(1, 2)):
            total, supervised = arrow_message_accounting(values)
            for i, messages in enumerate(values.to_pylist()):
                self.assertEqual(message_accounting(messages), (total[i], supervised[i]))
        bad = copy.deepcopy(SMALL)
        bad[1]["content"] = "1\n23"
        invalid = [[], SMALL + SMALL[:1], bad, [{"content": "1", "role": "bad"}, SMALL[1]],
                   [SMALL[0], {"content": "0" * 31, "role": "assistant"}],
                   [SMALL[0], {"content": None, "role": "assistant"}],
                   [SMALL[0], {"content": "1\n", "role": "assistant"}],
                   [SMALL[0], {"content": "1\n" * 30 + "1", "role": "assistant"}]]
        for messages in invalid:
            with self.subTest(messages=messages), self.assertRaises(ValidationError):
                arrow_message_accounting(pa.array([messages], type=TYPE))
        tokens, labels = GridTokenizer(source_chat_newlines=True).encode_pair([[1, 2], [3, 4]], [[4, 3], [2, 1]])
        self.assertEqual((len(tokens), sum(x >= 0 for x in labels[1:])), message_accounting(SMALL))

    def _fixture(self, root):
        disable_progress_bars()
        raw = root / "raw"
        catalog = {"training_ids": ["11111111", "22222222", "44444444"],
            "arc2_training_ids": ["11111111", "22222222"], "evaluation_ids": ["33333333"],
            "excluded_parent_ids": ["22222222"], "rearc_generator_ids": ["11111111"],
            "mini_ids": ["mini-one"], "concept_ids": ["concept-one"],
            "protected_categories": {"locked_holdout": ["22222222"], "pilot": ["22222222"]}}
        names = {"arc2_training": "11111111", "mini": "mini-one", "concept": "concept-one",
                 "rearc": "11111111", "nvarc_training": "11111111_22222222",
                 "nvarc_full": "33333333_22222222", VALIDATION: "33333333"}
        for s, name in names.items():
            records = [{"puzzle_name": name, "messages": SMALL}]
            if s == "nvarc_training":
                records += [{"puzzle_name": name, "messages": GIANT}]
            Dataset.from_list(records).save_to_disk(str(raw / s))
        augmented = {"archive_sha256": "1" * 64, "members": [
            {"path": p.relative_to(raw).as_posix(), "sha256": sha_file(p)}
            for p in sorted(raw.rglob("*")) if p.is_file()]}
        synthetic = {"archive_sha256": "2" * 64, "members": [
            {"path": "nvarc_training/11111111/11111111_22222222.json"},
            {"path": "nvarc_full/33333333/33333333_22222222.json"}]}
        for name, value in (("augmented-inventory", augmented), ("synthetic-inventory", synthetic), ("catalog", catalog)):
            (root / (name + ".json")).write_bytes(canonical_bytes(value, newline=True))
        contract = json.loads(CONTRACT.read_bytes())
        contract["material_class"] = "synthetic-fixture"
        contract["expected_records"] = {s: 2 if s == "nvarc_training" else 1 for s in names}
        contract["catalog_sha256"] = sha_file(root / "catalog.json")
        for key, inventory in (("augmented", augmented), ("synthetic", synthetic)):
            contract["archives"][key]["sha256"] = inventory["archive_sha256"]
            contract["archives"][key]["inventory_sha256"] = sha_file(root / (key + "-inventory.json"))
        (root / "contract.json").write_bytes(canonical_bytes(contract, newline=True))
        output = root / "original"
        manifest = prepare_original(raw, root / "augmented-inventory.json", root / "synthetic-inventory.json",
                                    root / "catalog.json", root / "contract.json", SOURCE, output)
        return output, manifest

    def test_full_original_freeze_keeps_long_and_exposed_rows_and_separate_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output, manifest = self._fixture(root)
            self.assertEqual(7, manifest["training_records"])
            self.assertEqual(1, manifest["validation_records"])
            summary = manifest["sources"]["nvarc_training"]
            self.assertGreater(summary["maximum_compact_input_tokens"], 8192)
            self.assertEqual(0, summary["filtered_records"])
            self.assertEqual(2, summary["exposure_counts"]["locked_holdout-ancestor"])
            digest = sha_file(output / "manifest.json")
            proof = verify_original(output, expected_manifest_sha256=digest, source=SOURCE)
            self.assertTrue(proof["actual_upstream_loader_verified"])
            self.assertTrue(proof["full_seed24_shuffle_verified"])
            self.assertFalse(proof["material_preparation_ready"])
            self.assertFalse(proof["original_model_training_ready"])
            with self.assertRaises(ValidationError):
                OriginalCorpusStore(output, expected_manifest_sha256=digest, purpose="clean-research")
            with self.assertRaises(ValidationError):
                OriginalCorpusStore(output, expected_manifest_sha256="0" * 64, purpose="original-reproduction")
            # Even rehashed metadata cannot conceal a false second parent.
            path = output / "lineage/nvarc_full.arrow"
            with pa.memory_map(str(path), "r") as mapping:
                table = pa.ipc.open_file(mapping).read_all()
                schema = table.schema
                rows = table.to_pydict()
            del table
            rows["parent_ids"][0] = ["11111111", "33333333"]
            with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, schema) as writer:
                writer.write_table(pa.Table.from_pydict(rows, schema=schema))
            manifest["files"]["lineage/nvarc_full.arrow"] = sha_file(path)
            (output / "manifest.json").write_bytes(canonical_bytes(manifest, newline=True))
            with self.assertRaisesRegex(ValidationError, "lineage/token/order"):
                verify_original(output, expected_manifest_sha256=sha_file(output / "manifest.json"), source=SOURCE)
            (output / "hf/extra.json").write_text("{}")
            with self.assertRaisesRegex(ValidationError, "closed inventory"):
                OriginalCorpusStore(output, expected_manifest_sha256=sha_file(output / "manifest.json"), purpose="qwen35-port")


if __name__ == "__main__":
    unittest.main()
