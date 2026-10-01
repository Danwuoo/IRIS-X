"""Offline archive integrity, split contamination and compact accounting checks."""

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from irisx.arc_nvarc_datasets import (inventory_archive, synthetic_parents, exposure,
    message_accounting, validate_pairs, audit_synthetic, source_lineage)
from irisx.arc_nvarc_representation import GridTokenizer
from irisx.errors import ValidationError


class DatasetAuditTests(unittest.TestCase):
    def test_zip_rejects_windows_traversal_and_collision_before_extraction(self):
        for names in (("safe/data.json", "../outside.json"), ("C:/secret",),
                      ("folder\\outside",), ("x.json", "X.JSON"), ("NUL.json",),
                      ("folder./x",), ("data", "data/child"), ("a//b",)):
            with self.subTest(names=names), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                archive = root / "input.zip"
                with zipfile.ZipFile(archive, "w") as stream:
                    for name in names:
                        info = zipfile.ZipInfo("placeholder")
                        info.filename = name  # bypass ZipInfo's platform-specific path normalization
                        stream.writestr(info, b"{}")
                with self.assertRaises(ValidationError):
                    inventory_archive(archive, root / "inventory.json", extract=root / "extracted")
                self.assertFalse((root / "extracted").exists())

    def test_inventory_preserves_original_zip_and_checks_member_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "input.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("source/data.json", b'{"value":3}')
            original = archive.read_bytes()
            report = inventory_archive(archive, root / "inventory.json", extract=root / "extracted")
            self.assertEqual(original, archive.read_bytes())
            self.assertEqual(b'{"value":3}', (root / "extracted/source/data.json").read_bytes())
            self.assertTrue(report["crc_verified"])
            self.assertEqual(1, report["member_count"])
            with self.assertRaises(ValidationError):
                inventory_archive(archive, root / "inventory.json")

    def test_multi_parent_exclusion_checks_second_ancestor_and_unknown(self):
        train, evaluation, excluded = {"11111111", "22222222"}, {"33333333"}, {"22222222"}
        self.assertEqual("protected-parent", exposure(("11111111", "22222222"), train, evaluation, excluded))
        self.assertEqual("evaluation-derived", exposure(("33333333", "11111111"), train, evaluation, excluded))
        self.assertEqual("unresolved-lineage", exposure(("11111111", "44444444"), train, evaluation, excluded))
        self.assertEqual("public-training-only", exposure(("11111111",), train, evaluation, excluded))
        self.assertEqual(("nvarc_training", "22222222_11111111", ("11111111", "22222222")),
            synthetic_parents("nvarc_training/22222222/22222222_11111111.json"))
        for member in ("nvarc_training/11111111/22222222_11111111.json",
                       "nvarc_training/11111111/unknown.json"):
            with self.assertRaises(ValidationError):
                synthetic_parents(member)

    def test_token_accounting_matches_independent_compact_encoder(self):
        messages = [{"role": "user", "content": "12\n34"},
                    {"role": "assistant", "content": "56\n78"}]
        tokens, labels = GridTokenizer(source_chat_newlines=True).encode_pair([[1, 2], [3, 4]], [[5, 6], [7, 8]])
        self.assertEqual((len(tokens), sum(x >= 0 for x in labels[1:])), message_accounting(messages))
        for invalid in ([*messages, messages[0]], [{"role": "assistant", "content": "1"}, messages[1]],
                        [messages[0], {"role": "assistant", "content": "12\n3"}],
                        [messages[0], {"role": "assistant", "content": "```12```"}]):
            with self.assertRaises(ValidationError):
                message_accounting(invalid)

    def test_pair_validation_rejects_boolean_float_ragged_and_text(self):
        for invalid in ([[True]], [[1.0]], [[10]], [[1, 2], [3]], "python code"):
            with self.assertRaises(ValidationError):
                validate_pairs([{"input": [[1]], "output": invalid}])

    def test_synthetic_audit_does_not_parse_quarantined_content_or_lose_parents(self):
        catalog = {"training_ids": ["11111111", "22222222"], "evaluation_ids": ["33333333"],
                   "excluded_parent_ids": ["22222222"]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "input.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("nvarc_training/11111111/11111111_11111111.json",
                    json.dumps([{"input": [[1]], "output": [[2]]}]))
                stream.writestr("nvarc_training/11111111/11111111_22222222.json", "untrusted code")
                stream.writestr("nvarc_full/33333333/33333333_11111111.json", "not parsed")
            report, index = audit_synthetic(archive, catalog, root / "audit")
            self.assertEqual(3, report["puzzle_count"])
            self.assertEqual(1, report["eligible_pair_counts"]["nvarc_training"])
            self.assertEqual(0, report["programs_executed"])
            parents, status = source_lineage("nvarc_training", "11111111_22222222", catalog, index)
            self.assertEqual(("11111111", "22222222"), parents)
            self.assertEqual("protected-parent", status)
            self.assertEqual(((), "unresolved-lineage"), source_lineage("nvarc_training", "missing", catalog, index))


if __name__ == "__main__":
    unittest.main()
