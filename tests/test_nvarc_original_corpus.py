"""Offline policy and lineage checks; default suite needs no Arrow dependency."""

import copy
import json
from pathlib import Path
import unittest

from irisx.arc_nvarc_original_corpus import validate_contract, parent_metadata, synthetic_index, member_hashes
from irisx.errors import ValidationError

ROOT = Path(__file__).resolve().parents[1]


class OriginalCorpusPolicyTests(unittest.TestCase):
    def test_original_contract_has_full_sources_validation_and_separate_namespaces(self):
        contract = json.loads((ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/original-corpus-contract-20261001.json").read_bytes())
        validate_contract(contract)
        self.assertEqual(3255481, sum(contract["expected_records"][s] for s in contract["training_sources"]))
        self.assertEqual(720, contract["expected_records"][contract["validation_source"]])
        for field, value in (("filter_parents", True), ("maximum_sequence_length", 8192), ("truncate", True)):
            bad = copy.deepcopy(contract)
            bad["preparation"][field] = value
            with self.assertRaises(ValidationError):
                validate_contract(bad)
        bad = copy.deepcopy(contract)
        bad["isolation"]["checkpoints"] = "clean/checkpoints"
        with self.assertRaises(ValidationError):
            validate_contract(bad)

    def test_both_parents_keep_simultaneous_evaluation_and_protected_exposure(self):
        inventory = {"members": [{"path": "nvarc_full/33333333/33333333_22222222.json"}]}
        index = synthetic_index(inventory)
        catalog = {"training_ids": ["11111111", "22222222"], "evaluation_ids": ["33333333"],
                   "excluded_parent_ids": ["22222222"],
                   "protected_categories": {"locked_holdout": ["22222222"], "pilot": ["22222222"]}}
        parents, tags = parent_metadata("nvarc_full", "33333333_22222222", catalog, index)
        self.assertEqual(["22222222", "33333333"], parents)
        self.assertEqual(["arc-evaluation-ancestor", "protected-parent-or-visible-family",
                          "locked_holdout-ancestor", "pilot-ancestor"], tags)
        with self.assertRaises(ValidationError):
            parent_metadata("nvarc_training", "unknown", catalog, index)
        # Hash-bound filename metadata is lineage evidence, not independently reconstructed semantics.
        with self.assertRaises(ValidationError):
            synthetic_index({"members": inventory["members"] * 2})

    def test_inventory_traversal_and_collision_are_rejected(self):
        for paths in (("../outside",), ("a\\b",), ("C:/outside",), ("/outside",), ("a", "A")):
            with self.subTest(paths=paths), self.assertRaises(ValidationError):
                member_hashes({"members": [{"path": p, "sha256": "0" * 64} for p in paths]})


if __name__ == "__main__":
    unittest.main()
