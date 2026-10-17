import random
import unittest

from tools.nvarc_posttrain_20261017 import codec
from tools.nvarc_posttrain_20261017.curriculum import ExactCurriculum, PositiveReplay, exact_reward


class CompactCodecTests(unittest.TestCase):
    def test_literal_role_tokens_and_masks(self):
        pair = {"input": [[1, 2]], "output": [[3, 4]]}
        result = codec.encode_example([pair], [[5]], [[6]])
        self.assertEqual(result["prompt_ids"], codec.PROBE_IDS + [14, 11, 10, 5, 15, 14, 12, 10])
        self.assertEqual(result["completion_ids"], [6, 15])
        self.assertEqual(result["loss_mask"], [0] * len(result["prompt_ids"]) + [1, 1])

    def test_every_grid_dimension_roundtrips_without_crop(self):
        rng = random.Random(3)
        for height in range(1, 31):
            for width in range(1, 31):
                grid = [[rng.randrange(10) for _ in range(width)] for _ in range(height)]
                self.assertEqual(codec.parse_completion(codec.grid_tokens(grid) + [15]), grid)
        self.assertEqual(codec.MAX_GRID_TOKENS, 930)

    def test_invalid_completion_is_not_repaired(self):
        for tokens in ([], [15], [1], [1, 15, 2], [1, 10, 15], [10, 1, 15], [1, 10, 2, 3, 15],
                       [True, 15], [1, 13, 15], [1, 14, 15], [1] * 31 + [15]):
            with self.subTest(tokens=tokens):
                self.assertIsNone(codec.parse_completion(tokens))

    def test_whole_demo_context_cut(self):
        small = {"input": [[1]], "output": [[2]]}
        large = {"input": [[1] * 30 for _ in range(30)], "output": [[2] * 30 for _ in range(30)]}
        result = codec.encode_example([small, large], [[3]], [[4]], context=30)
        self.assertEqual(result["retained_demo_indices"], [0])
        self.assertEqual(result["completion_ids"], [4, 15])
        with self.assertRaisesRegex(ValueError, "truncation forbidden"):
            codec.encode_example([], [[1] * 30 for _ in range(30)], [[2]], context=20)

    def test_causal_demo_masks_never_include_role_or_input(self):
        pair = {"input": [[1]], "output": [[2]]}
        result = codec.encode_example([pair, pair], [[3]], [[4]], loss_mode="causal_outputs")
        ids = result["prompt_ids"] + result["completion_ids"]
        self.assertEqual([token for token, mask in zip(ids, result["loss_mask"]) if mask], [2, 15, 4, 15])

    def test_invalid_values_rejected(self):
        for grid in ([[True]], [[-1]], [[10]], [[]], [[1], [2, 3]]):
            with self.assertRaises(ValueError):
                codec.grid_tokens(grid)


class ExactCurriculumTests(unittest.TestCase):
    def test_wrong_pixels_never_positive(self):
        self.assertEqual(exact_reward([[1, 1]], [[1, 2]]), 0)
        self.assertEqual(exact_reward([[1, 2]], [[1, 2]]), 1)
        self.assertEqual(exact_reward(None, [[1, 2]]), 0)

    def test_reproducibility_and_physical_groups(self):
        a, b = (ExactCurriculum(["a", "b"], seed=17) for _ in range(2))
        for c in (a, b):
            c.observe("a", [0] * 8)
            c.observe("b", [1] * 8)
        self.assertEqual([a.choose() for _ in range(100)], [b.choose() for _ in range(100)])
        report = a.report()
        self.assertEqual((report["samples"], report["exact"], report["groups"]), (16, 8, 2))
        self.assertFalse(report["public_or_dev_feedback"])
        with self.assertRaises(ValueError):
            a.observe("public", [1])
        with self.assertRaises(ValueError):
            a.observe("a", [.2])

    def test_positive_replay_verifies_tokens_not_claimed_reward(self):
        pool = PositiveReplay(["a"], per_parent=1)
        wrong = {"input_ids": [14, 11, 10, 1, 15], "prompt_length": 3, "reward": 1}
        self.assertFalse(pool.add("a", wrong, target=[[2]], policy_digest="p", model_identity={"id": "m"}))
        correct = {**wrong, "input_ids": [14, 11, 10, 2, 15]}
        self.assertTrue(pool.add("a", correct, target=[[2]], policy_digest="p", model_identity={"id": "m"}))
        self.assertFalse(pool.add("a", correct, target=[[2]], policy_digest="q", model_identity={"id": "m"}))
        sample = pool.sample()
        self.assertEqual(sample["completion_ids"], [2, 15])
        self.assertEqual(sample["use"], "separate-off-policy-supervised-replay")
        sample["completion_ids"][0] = 9
        self.assertEqual(pool.sample()["completion_ids"], [2, 15])
        with self.assertRaises(ValueError):
            pool.add("dev", correct, target=[[2]], policy_digest="p", model_identity={"id": "m"})


if __name__ == "__main__":
    unittest.main()
