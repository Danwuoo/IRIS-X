import unittest

from tools.cpt_token_contract_20261021 import build_row, token_ledger
from tools.cpt_token_contract_20261021.probe import encode_without_silent_normalization, encode_with_policy


class TokenContractTests(unittest.TestCase):
    def row(self, ids=(1, 2, 9), mask=(True, True, True), **kwargs):
        args = dict(length=5, eos_id=9, vocab_size=10, objective="cpt")
        args.update(kwargs)
        return build_row(list(ids), list(mask), **args)

    def test_eos_pad_collision_is_not_loss_mask(self):
        r = self.row()
        self.assertEqual(r["targets"], [2, 9, 9, 9, 9])
        self.assertEqual(r["targets_segmentation"], [1, 1, 0, 0, 0])
        self.assertNotEqual([int(x != 9) for x in r["targets"]], r["targets_segmentation"])

    def test_position_padding_is_zero_not_eos(self):
        r = self.row()
        self.assertEqual(r["inputs_position"], [0, 1, 0, 0, 0])
        self.assertEqual(r["inputs_segmentation"], [1, 1, 0, 0, 0])

    def test_sft_keeps_prompt_as_context(self):
        r = self.row((1, 2, 3, 9), (False, False, True, True), objective="sft")
        self.assertEqual(r["inputs_segmentation"], [1, 1, 1, 0, 0])
        self.assertEqual(r["targets_segmentation"], [0, 1, 1, 0, 0])
        self.assertEqual(r["loss_positions"], 2)

    def test_exact_context_boundary(self):
        r = self.row(length=2)
        self.assertEqual(r["padded_positions"], 0)

    def test_no_truncation(self):
        with self.assertRaisesRegex(ValueError, "truncation"):
            self.row(length=1)

    def test_reject_multiple_documents_or_eos(self):
        for ids in ((1, 9, 2, 9), (1, 2, 3), (9, 9)):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.row(ids, [True] * len(ids))

    def test_invalid_ids(self):
        for ids in ((True, 2, 9), (1, -1, 9), (1, 10, 9), (1, 2.0, 9)):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.row(ids)

    def test_invalid_mask(self):
        for mask in ((1, 1, 1), (True,), (True, True, False)):
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                self.row(mask=mask)

    def test_no_silent_masked_cpt(self):
        with self.assertRaisesRegex(ValueError, "masked CPT"):
            self.row(mask=(False, True, True))

    def test_invalid_sft(self):
        for mask in ((True, True, True, True), (False, True, False, True),
                     (False, False, False, True)):
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                self.row((1, 2, 3, 9), mask, objective="sft")

    def test_does_not_mutate_input(self):
        ids, masks = [1, 2, 9], [True] * 3
        r = build_row(ids, masks, length=3, eos_id=9, vocab_size=10, objective="cpt")
        r["inputs"][0] = 4
        self.assertEqual(ids, [1, 2, 9])
        self.assertEqual(masks, [True] * 3)

    def test_measured_ledger(self):
        a, b = self.row(), self.row(length=2)
        total = token_ledger([a, b])
        self.assertEqual((total["stored_tokens"], total["real_positions"],
                          total["loss_positions"], total["processed_positions"]), (6, 4, 4, 7))

    def test_non_nfc_rejected_before_tokenizer(self):
        with self.assertRaisesRegex(ValueError, "Non-NFC"):
            encode_without_silent_normalization(None, "e\u0301")

    def test_explicit_policy_does_not_normalize_code_or_exact_targets(self):
        for kind in ("code", "exact_target"):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "semantic"):
                encode_with_policy(None, "e\u0301", policy="native_nfc_with_receipt", content_kind=kind)

    def test_unknown_normalization_policy_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown"):
            encode_with_policy(None, "text", policy="discard_unicode")


if __name__ == "__main__":
    unittest.main()
