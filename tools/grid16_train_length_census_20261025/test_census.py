import unittest
from census import pair_lengths, episode_metadata

TEXT = "ARC demonstration episode\nExample 0\nInput 1 2\n01\nOutput 2 1\n0\n1\nExample 1\nInput 1 1\n2\nOutput 1 2\n03\n"


class Tests(unittest.TestCase):
    def test_exact_lengths(self):
        self.assertEqual(pair_lengths(TEXT), [(2, 3), (1, 2)])
        row = episode_metadata("synthetic", TEXT)
        self.assertEqual(row["full_episode_ids"], 24)
        self.assertEqual(row["views"], [
            {"query_demo_ordinal": 0, "prompt_ids": 20, "target_ids_including_eos": 4},
            {"query_demo_ordinal": 1, "prompt_ids": 21, "target_ids_including_eos": 3}])

    def test_train_only_parser(self):
        for bad in [TEXT.replace("Example 1", "Query"), TEXT.replace("01", "0x"),
                    TEXT.replace("Input 1 2", "Input 1 3"), TEXT[:-1],
                    TEXT.replace("Example 1", "Example 0"), TEXT.replace("0\n1", "13\n1")]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    pair_lengths(bad)

    def test_labels_only_change_hash_not_length(self):
        other = TEXT.replace("03", "99")
        a, b = episode_metadata("synthetic", TEXT), episode_metadata("synthetic", other)
        self.assertEqual(a["views"], b["views"])
        self.assertNotEqual(a["source_text_sha256"], b["source_text_sha256"])


if __name__ == "__main__":
    unittest.main()
