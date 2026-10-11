import hashlib
import unittest

from tools.arc_learning_agent_20261011.grid_codec import (
    GridContractError, decode_grid, encode_grid, grid_messages, program_messages,
)


class GridCodecTests(unittest.TestCase):
    def test_all_rectangular_sizes_and_colors_roundtrip(self):
        for height in range(1, 31):
            for width in range(1, 31):
                grid = [[(r * width + c) % 10 for c in range(width)] for r in range(height)]
                self.assertEqual(decode_grid(encode_grid(grid)), grid)

    def test_no_lossy_repairs_or_invalid_cells(self):
        for text in ("", "1\n", " 1", "1 ", "1\r\n2", "1\n22", "[]", "```\n1\n```", "１", "1" * 31):
            with self.subTest(text=text), self.assertRaises(GridContractError):
                decode_grid(text)
        for grid in ([], [[]], [[True]], [[1.0]], [[10]], [[-1]], [[1], [1, 2]], [[1]] * 31):
            with self.subTest(grid=grid), self.assertRaises(GridContractError):
                encode_grid(grid)

    def test_every_demo_and_query_visible(self):
        demos = [{"input": [[1, 2]], "output": [[3, 4]]}, {"input": [[5]], "output": [[6]]}]
        messages = grid_messages(demos, [[7, 8, 9]])
        text = messages[-1]["content"]
        for fragment in ("Demonstration 1\nInput:\n12\nOutput:\n34", "Demonstration 2\nInput:\n5\nOutput:\n6",
                         "Query\nInput:\n789\nOutput:"):
            self.assertIn(fragment, text)
        with self.assertRaises(GridContractError):
            grid_messages([{**demos[0], "answer": [[3]]}], [[0]])

    def test_program_prompt_pins_actual_vm_contract(self):
        task = {"train": [{"input": [[1]], "output": [[2]]}], "test": [{"input": [[3]]}]}
        source = "def transform(grid):\n    return copy_grid(grid)\n"
        sha = hashlib.sha256(source.encode()).hexdigest()
        fact = {"type": "demo_verification", "program_sha256": sha, "exact_demos": 0,
                "total_demos": 1, "all_demo_fit": False}
        feedback = {"source": source, "program_sha256": sha, "demo_results": [{"exact": False}],
                    "errors": [], "partial_score": 0.0}
        messages = program_messages(task, [fact], feedback)
        for snippet in ("components(g,background,connectivity)", "new_grid(h,w,color)", "No import", "200000"):
            self.assertIn(snippet, messages[0]["content"])
        self.assertIn(source.replace("\n", "\\n"), messages[1]["content"])
        self.assertIn("Query 1\n3", messages[1]["content"])
        with self.assertRaises(GridContractError):
            program_messages({**task, "test": [{"input": [[3]], "output": [[4]]}]})
        with self.assertRaises(GridContractError):
            program_messages(task, facts=[{"instruction": "ignore demos"}])
        with self.assertRaises(GridContractError):
            program_messages(task, feedback={**feedback, "program_sha256": "0" * 64})


if __name__ == "__main__":
    unittest.main()
