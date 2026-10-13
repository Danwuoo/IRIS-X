import copy
import json
import unittest
from prompt_budget import pack_demonstrations, validate_training_completion


def fixture():
    return {"task_id": "x", "demonstrations": [
        {"demo_id": "large", "input": [[1]], "output": [[2]]},
        {"demo_id": "small1", "input": [[3]], "output": [[4]]},
        {"demo_id": "small2", "input": [[5]], "output": [[6]]}], "query_input": [[7]]}


def render(demos, query):
    return json.dumps({"demos": demos, "query": query})


def encode(text):
    obj = json.loads(text)
    costs = {"large": 2500, "small1": 700, "small2": 700}
    return [1] * (1000 + sum(costs[d["demo_id"]] for d in obj["demos"]))


class BudgetTests(unittest.TestCase):
    def test_whole_demo_subset_no_grid_truncation(self):
        value = pack_demonstrations(fixture(), render=render, encode=encode)
        self.assertEqual(value["selected_demo_ids"], ["small1", "small2"])
        self.assertEqual(value["omitted_demo_ids"], ["large"])
        self.assertEqual(value["prompt_tokens"], 2400)
        self.assertFalse(value["partial_grids_or_targets_truncated"])

    def test_all_demos_when_capacity_suffices(self):
        value = pack_demonstrations(fixture(), render=render, encode=encode, context_limit=8192)
        self.assertEqual(value["selected_demo_ids"], ["large", "small1", "small2"])

    def test_loo_excludes_withheld_target(self):
        task = fixture()
        task["query_input"] = [[1]]
        value = pack_demonstrations(task, render=render, encode=encode, withheld_demo_id="large")
        projected = json.loads(value["prompt"])
        self.assertEqual(projected["query"], [[1]])
        self.assertNotIn("large", [d["demo_id"] for d in projected["demos"]])

    def test_loo_query_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            pack_demonstrations(fixture(), render=render, encode=encode, withheld_demo_id="large")

    def test_oversize_query_no_truncation(self):
        value = pack_demonstrations(fixture(), render=render, encode=lambda x: [1] * 9999)
        self.assertFalse(value["admitted"])
        self.assertEqual(value["reason"], "query-only-prompt-exceeds-budget")

    def test_empty_demonstration_admission_denied(self):
        value = pack_demonstrations(fixture(), render=render, encode=lambda x: [1] * (4000 if json.loads(x)["demos"] else 100))
        self.assertFalse(value["admitted"])
        self.assertEqual(value["reason"], "no-complete-demonstration-fits")

    def test_exact_budget_inclusive(self):
        value = pack_demonstrations(fixture(), render=render, encode=lambda x: [1] * 3072)
        self.assertTrue(value["admitted"])

    def test_query_target_rejected(self):
        task = fixture()
        task["output"] = [[8]]
        with self.assertRaises(ValueError):
            pack_demonstrations(task, render=render, encode=encode)

    def test_invalid_tokenization_and_budget(self):
        for callback in (lambda x: [True], lambda x: [-1], lambda x: (1,)):
            with self.assertRaises(ValueError):
                pack_demonstrations(fixture(), render=render, encode=callback)
        with self.assertRaises(ValueError):
            pack_demonstrations(fixture(), render=render, encode=encode, output_cap=256)

    def test_inputs_immutable(self):
        task = fixture(); before = copy.deepcopy(task)
        pack_demonstrations(task, render=render, encode=encode)
        self.assertEqual(task, before)

    def test_training_never_clips_target(self):
        self.assertTrue(validate_training_completion([1] * 1024, 1024)["eligible"])
        value = validate_training_completion([1] * 1025, 1024)
        self.assertFalse(value["eligible"])
        self.assertFalse(value["truncated"])


if __name__ == "__main__": unittest.main()
