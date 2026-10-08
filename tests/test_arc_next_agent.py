"""Independent synthetic and negative controls; no ARC evaluator data."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / "tools" / "arc_next_agent.py"
spec = importlib.util.spec_from_file_location("arc_next_agent_under_test", PATH)
agent = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = agent
spec.loader.exec_module(agent)


TASK = {"train": [{"input": [[1, 0], [0, 1]], "output": [[2, 0], [0, 2]]},
                  {"input": [[1, 1]], "output": [[2, 2]]}],
        "test": [{"input": [[0, 1], [1, 0]]}]}
IDENTITY = "def transform(grid):\n    return copy_grid(grid)"
RECOLOR = """def transform(grid):
    out = copy_grid(grid)
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] == 1:
                out[r][c] = 2
    return out
"""


class FakeModel:
    def __init__(self, values, generated=10, model_id="synthetic-mock"):
        self.values, self.generated, self.model_id = values, generated, model_id
        self.requests = []

    def __call__(self, request):
        self.requests.append(copy.deepcopy(request))
        value = self.values[min(len(self.requests) - 1, len(self.values) - 1)]
        if isinstance(value, Exception):
            raise value
        return {"text": value if type(value) is str else json.dumps(value),
                "prompt_tokens": count_tokens(request["messages"]),
                "generated_tokens": self.generated, "model_id": self.model_id,
                "finish_reason": "synthetic_mock_stop"}


def count_tokens(messages):
    # Deliberately synthetic exact callback contract, not a real tokenizer claim.
    return len(json.dumps(messages).encode())


def limits(**kwargs):
    return agent.Limits(**{"max_calls": 2, "max_prompt_tokens": 20000, **kwargs})


class InterpreterTests(unittest.TestCase):
    def test_generic_loop_recolor_and_caller_isolation(self):
        value = [[1, 0], [0, 1]]
        before = copy.deepcopy(value)
        result = agent.execute_program(RECOLOR, value)
        self.assertEqual(result["output"], [[2, 0], [0, 2]])
        self.assertEqual(value, before)
        self.assertGreater(result["steps"], 0)

    def test_generic_comprehension_and_helpers(self):
        source = """def replace(x):
    return 3 if x == 1 else x
def transform(grid):
    return [[replace(c) for c in row] for row in grid]
"""
        self.assertEqual(agent.execute_program(source, [[1, 0]])["output"], [[3, 0]])

    def test_geometry_and_composed_nonfixed_transformation(self):
        source = "def transform(grid):\n    return transpose(crop(grid,0,0,2,2))"
        self.assertEqual(agent.execute_program(source, [[1, 2, 0], [3, 4, 0]])["output"],
                         [[1, 3], [2, 4]])

    def test_object_components_and_relational_program(self):
        source = """def transform(grid):
    objects = components(grid, 0, 4)
    out = copy_grid(grid)
    for obj in objects:
        if len(obj) > 1:
            for r, c, color in obj:
                out[r][c] = 3
    return out
"""
        self.assertEqual(agent.execute_program(source, [[1, 1, 0, 2]])["output"],
                         [[3, 3, 0, 2]])

    def test_break_continue_and_augmentation(self):
        source = """def transform(grid):
    out = new_grid(1, 2, 0)
    n = 0
    for x in range(5):
        if x == 0:
            continue
        n += x
        if x == 2:
            break
    out[0][0] = n
    out[0][1] = sum(unique([1, 1, 2]))
    return out
"""
        self.assertEqual(agent.execute_program(source, [[0]])["output"], [[3, 3]])

    def test_host_capability_and_language_rejections(self):
        bad = [
            "import os\ndef transform(grid):\n return grid",
            "def transform(grid):\n return grid.__class__",
            "def transform(grid):\n return open(1)",
            "def transform(grid):\n return eval(1)",
            "def transform(grid):\n return exec(1)",
            "def transform(grid):\n while True:\n  pass\n return grid",
            "def transform(grid):\n return (lambda x: x)(grid)",
            "def transform(grid):\n return [[2 ** 1000000]]",
            "def transform(grid):\n return {1: 2}",
            "def transform(grid):\n return [[True]]",
            "def transform(grid):\n return [[-1]]",
            "def transform(grid):\n return [[10]]",
            "def transform(grid):\n return [[1], [1,2]]",
        ]
        for source in bad:
            with self.subTest(source=source), self.assertRaises(agent.ProgramError):
                agent.execute_program(source, [[0]])

    def test_recursion_and_instruction_budget(self):
        source = "def transform(grid):\n return transform(grid)"
        with self.assertRaisesRegex(agent.BudgetError, "call depth"):
            agent.execute_program(source, [[0]], limits(max_call_depth=3))
        source = "def transform(grid):\n for x in range(100):\n  for y in range(100):\n   x = y\n return grid"
        with self.assertRaises(agent.BudgetError):
            agent.execute_program(source, [[0]], limits(max_program_steps=100))

    def test_allocation_and_cycles(self):
        bad = ["def transform(grid):\n return [grid] * 1000000",
               "def transform(grid):\n xs = [0]\n xs[0] = xs\n return grid",
               "def transform(grid):\n xs = []\n append(xs, xs)\n return grid",
               "def transform(grid):\n return new_grid(31, 1, 0)"]
        for source in bad:
            with self.subTest(source=source), self.assertRaises(agent.ProgramError):
                agent.execute_program(source, [[0]])

    def test_source_ast_and_shape_limits(self):
        with self.assertRaises(agent.ProgramError):
            agent.execute_program(IDENTITY, [[0]], limits(max_source_bytes=10))
        with self.assertRaises(agent.ProgramError):
            agent.execute_program(IDENTITY, [[0]], limits(max_ast_nodes=2))
        for grid in ([], [[]], [[False]], [[1] * 31]):
            with self.assertRaises(agent.ProgramError):
                agent.execute_program(IDENTITY, grid)
        with self.assertRaisesRegex(agent.ProgramError, "UTF-8"):
            agent.execute_program("def transform(grid):\n return grid\n#\ud800", [[0]])
        with self.assertRaises(agent.ProgramError):
            agent.execute_program("def helper(a,b):\n return a\ndef transform(grid):\n return grid",
                                  [[0]], limits(max_locals=1))


class HarnessTests(unittest.TestCase):
    def run_arm(self, arm, responses, **kwargs):
        model = FakeModel(responses)
        result = agent.solve_task(TASK, arm, model, count_tokens, limits(**kwargs),
                                  expected_model_id="synthetic-mock")
        return result, model

    def test_grid_arm_and_distinct_slot_selection(self):
        a, b = [[2, 0], [0, 2]], [[0, 2], [2, 0]]
        result, model = self.run_arm("grid", [{"kind": "grid", "outputs": [a]},
                                               {"kind": "grid", "outputs": [b]}])
        self.assertEqual(result["selected"][0], {"test_index": 0, "attempts": [a, b]})
        self.assertFalse(result["correctness_scored"])
        self.assertEqual(result["lodo_status"], "not_run")
        self.assertEqual(result["usage"]["generated_tokens"], 20)
        self.assertEqual(result["usage"]["prompt_tokens"],
                         sum(count_tokens(r["messages"]) for r in model.requests))

    def test_program_demo_check_is_not_test_truth(self):
        result, _ = self.run_arm("program", [{"kind": "program", "source": RECOLOR}])
        self.assertEqual(result["selected"][0]["attempts"], [[[0, 2], [2, 0]]])
        self.assertEqual(result["ranked_candidates"][0]["votes"], 2)
        self.assertTrue(result["feedback"][0]["all_demonstrations_exact"])
        self.assertEqual(result["feedback"][0]["demonstrations"][0]["mismatch_count"], 0)

    def test_repair_receives_structured_feedback_only_after_failure(self):
        result, model = self.run_arm("repair", [{"kind": "program", "source": IDENTITY},
                                                {"kind": "program", "source": RECOLOR}])
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(len(model.requests[0]["messages"]), 2)
        self.assertEqual(len(model.requests[1]["messages"]), 4)
        self.assertIn("mismatch_count", model.requests[1]["messages"][-1]["content"])
        self.assertEqual(result["selected"][0]["attempts"][0], [[0, 2], [2, 0]])
        self.assertGreater(result["usage"]["program_steps"], 0)

    def test_open_loop_never_gets_feedback(self):
        result, model = self.run_arm("program", [{"kind": "program", "source": IDENTITY}])
        self.assertEqual(model.requests[0]["messages"], model.requests[1]["messages"])
        self.assertFalse(result["feedback"][0]["all_demonstrations_exact"])
        self.assertEqual(result["candidates"], [])

    def test_test_answers_rejected_before_model_call(self):
        task = copy.deepcopy(TASK)
        task["test"][0]["output"] = [[0]]
        model = FakeModel([{}])
        with self.assertRaises(ValueError):
            agent.solve_task(task, "grid", model, count_tokens)
        self.assertEqual(model.requests, [])

    def test_generation_budget_charged_and_no_hidden_calls(self):
        result, model = self.run_arm("grid", [{"kind": "grid", "outputs": [[[0]]]}],
                                    max_generated_tokens=10, max_calls=4)
        self.assertEqual(len(model.requests), 1)
        self.assertEqual(result["terminal_reason"], "token_budget")
        self.assertEqual(result["usage"]["generated_tokens"], 10)
        self.assertEqual(model.requests[0]["max_new_tokens"], 10)

    def test_prompt_budget_admission_is_zero_call(self):
        result, model = self.run_arm("grid", [{}], max_prompt_tokens=1)
        self.assertEqual(len(model.requests), 0)
        self.assertEqual(result["usage"]["generated_tokens"], 0)

    def test_context_limit_prevents_overlong_call(self):
        result, model = self.run_arm("grid", [{}], max_context_tokens=1)
        self.assertEqual(len(model.requests), 0)
        self.assertEqual(result["terminal_reason"], "token_budget")

    def test_callback_failure_is_unknown_usage_and_no_retry(self):
        result, model = self.run_arm("grid", [RuntimeError("mock transport")])
        self.assertFalse(result["usage_known"])
        self.assertEqual(len(model.requests), 1)
        self.assertEqual(result["calls"][0]["status"], "callback_error")
        self.assertEqual(result["terminal_reason"], "unknown_usage_callback_failure")

    def test_false_usage_model_switch_and_overspend_fail_closed(self):
        for change in ({"prompt_tokens": 1}, {"generated_tokens": 9000}, {"model_id": "other"}):
            model = FakeModel([{"kind": "grid", "outputs": [[[0]]]}])
            def callback(request):
                return {**model(request), **change}
            result = agent.solve_task(TASK, "grid", callback, count_tokens, limits(),
                                      expected_model_id="synthetic-mock")
            self.assertEqual(result["terminal_reason"], "model_contract_violation")
            self.assertEqual(result["candidates"], [])
            self.assertEqual(len(model.requests), 1)

    def test_malformed_candidate_and_parser_failure_can_repair(self):
        result, model = self.run_arm("repair", ["not JSON", {"kind": "program", "source": RECOLOR}])
        self.assertEqual(len(model.requests), 2)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertIn("error", result["feedback"][0])

    def test_malformed_unicode_and_huge_json_integer_are_charged(self):
        values = [{"kind": "program", "source": "def transform(grid):\n return grid\n#\ud800"},
                  '{"kind":"program","source":' + '9' * 4301 + '}']
        for value in values:
            with self.subTest(value=str(value)[:60]):
                result, model = self.run_arm("repair", [value], max_calls=1)
                self.assertEqual(len(model.requests), 1)
                self.assertEqual(result["usage"]["generated_tokens"], 10)
                self.assertEqual(result["candidates"], [])
                self.assertTrue(result["feedback"][0]["error"])

    def test_verification_late_candidate_is_rejected(self):
        original = agent._feedback
        def late(*args, **kwargs):
            result = original(*args, **kwargs)
            time.sleep(0.02)
            return result
        with patch.object(agent, "_feedback", side_effect=late):
            result, model = self.run_arm("repair", [{"kind": "program", "source": RECOLOR}],
                                         max_wall_seconds=0.01, max_calls=1)
        self.assertEqual(result["terminal_reason"], "wall_deadline")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["calls"][0]["candidate_rejected"], "verification_deadline")
        self.assertGreater(result["usage"]["program_steps"], 0)

    def test_slow_tokenizer_prevents_model_dispatch(self):
        def slow_count(messages):
            time.sleep(0.02)
            return count_tokens(messages)
        model = FakeModel([{"kind": "grid", "outputs": [[[0]]]}])
        result = agent.solve_task(TASK, "grid", model, slow_count,
                                  limits(max_wall_seconds=0.01))
        self.assertEqual(result["terminal_reason"], "wall_deadline")
        self.assertEqual(model.requests, [])
        self.assertEqual(result["calls"], [])
        self.assertEqual(result["usage"]["generated_tokens"], 0)

    def test_program_work_budget_is_recorded(self):
        result, _ = self.run_arm("program", [{"kind": "program", "source": RECOLOR}],
                                 max_total_program_steps=20)
        self.assertEqual(result["terminal_reason"], "program_work_budget")
        self.assertEqual(result["candidates"], [])
        self.assertLessEqual(result["usage"]["program_steps"], 20)

    def test_no_late_answer_admission_and_honest_deadline_status(self):
        model = FakeModel([{"kind": "grid", "outputs": [[[0]]]}])
        with patch.object(agent.time, "monotonic", side_effect=[0, 0, 0, 0, 301, 301, 301]):
            result = agent.solve_task(TASK, "grid", model, count_tokens, limits())
        self.assertEqual(result["terminal_reason"], "wall_deadline")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["usage"]["generated_tokens"], 10)
        self.assertFalse(result["hard_model_deadline_enforced"])


if __name__ == "__main__":
    unittest.main()
