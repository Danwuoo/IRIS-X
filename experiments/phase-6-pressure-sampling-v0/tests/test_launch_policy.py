from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import pressure_tasks as tasks  # noqa: E402


class LaunchPolicyTests(unittest.TestCase):
    def test_exact_allocation_and_resource_ceiling(self) -> None:
        policy = tasks.load_object(ROOT / "definition/launch-policy.json")
        self.assertEqual(policy["profile_id"], "codex-cli-0.147.0-run-03-admission-v0")
        self.assertEqual(policy["provider_slot"], "irisx_openai_no_retry")
        self.assertEqual((policy["model"], policy["reasoning_effort"]), ("gpt-5.6-luna", "medium"))
        self.assertEqual(policy["task_count"], 6)
        self.assertEqual(policy["batch_model_call_ceiling"], 6)
        self.assertEqual(policy["per_task_model_call_ceiling"], 1)
        for field in ("retries", "routes", "fallbacks", "recovery_actions", "external_actions", "model_judges", "stronger_allocations"):
            self.assertEqual(policy[field], 0, field)
        self.assertEqual(policy["model_tools"], "disabled")
        self.assertFalse(policy["websocket_transport"])

    def test_runner_has_one_provider_subprocess_site_and_no_retry_loop(self) -> None:
        source = (SCRIPTS / "run_pressure_batch.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        provider_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.func.attr == "run"
        ]
        self.assertEqual(len(provider_calls), 2)  # git helper plus exactly one task invocation site
        self.assertNotIn("retry_task", source)
        self.assertNotIn("fallback_model", source)

    def test_runner_task_order_is_fixed(self) -> None:
        self.assertEqual(len(tasks.TASK_KEYS), 6)
        self.assertEqual(tasks.TASK_KEYS[0], "p1-selection")
        self.assertEqual(tasks.TASK_KEYS[-1], "p6-rule-precedence")


if __name__ == "__main__":
    unittest.main()
