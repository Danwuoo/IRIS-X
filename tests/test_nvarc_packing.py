import copy
import random
import unittest

from irisx.arc_nvarc_packing import modified_first_fit_decreasing, pack_sequences, validate_pack
from irisx.errors import ValidationError


def rows():
    return [{"input_ids": [14, 11, 1, 12, 2, 15], "labels": [-100] * 4 + [2, 15],
             "source_id": "synthetic", "source_row": i, "parent_ids": ["a", "b"],
             "exposure_tags": ["synthetic-fixture"]} for i in range(5)]


class PackingTests(unittest.TestCase):
    def test_whole_sequences_rounding_and_dual_lineage_survive_binning(self):
        packs = pack_sequences(rows(), capacity=24, length_multiple=4)
        self.assertEqual(2, len(packs))
        self.assertEqual(set(range(5)), {s["row_index"] for p in packs for s in p["segments"]})
        self.assertEqual(30, sum(p["input_tokens"] for p in packs))
        self.assertEqual(10, sum(p["supervised_tokens"] for p in packs))
        for pack in packs:
            validate_pack(pack)
            for segment in pack["segments"]:
                self.assertEqual(["a", "b"], segment["lineage"]["parent_ids"])
                self.assertEqual(-100, pack["labels"][segment["start"]])
        with self.assertRaises(ValidationError):
            pack_sequences(rows(), capacity=7, length_multiple=4)

    def test_tampered_positions_padding_or_supervision_cannot_cross_boundaries(self):
        pack = pack_sequences(rows(), capacity=48, length_multiple=4)[0]
        for key, index, value in (("position_ids", 8, 8), ("labels", 8, 14),
                                  ("attention_mask", 6, 1), ("input_ids", 7, 0)):
            altered = copy.deepcopy(pack)
            altered[key][index] = value
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_pack(altered)

    def test_mffd_never_loses_duplicates_or_overfills(self):
        generator = random.Random(24)
        for count in (0, 1, 2, 20, 256):
            lengths = [generator.randint(1, 100) for _ in range(count)]
            bins = modified_first_fit_decreasing(lengths, 100)
            self.assertEqual(list(range(count)), sorted(i for b in bins for i in b))
            self.assertTrue(all(sum(lengths[i] for i in b) <= 100 for b in bins))


if __name__ == "__main__":
    unittest.main()
