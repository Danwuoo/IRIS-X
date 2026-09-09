from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import pressure_tasks as tasks  # noqa: E402
import provider_schema  # noqa: E402


class ProviderSchemaTests(unittest.TestCase):
    def test_all_six_repaired_schemas_are_policy_admissible(self) -> None:
        for key in tasks.TASK_KEYS:
            result = provider_schema.validate_provider_schema(tasks.load_task(key).schema)
            self.assertEqual(result["status"], "provider_schema_policy_admissible", key)

    def test_observed_unique_items_keyword_is_rejected_with_pointer(self) -> None:
        schema = json.loads(json.dumps(tasks.load_task("p4-dependency").schema))
        schema["properties"]["ordered_ids"]["uniqueItems"] = True
        with self.assertRaisesRegex(
            provider_schema.ProviderSchemaError,
            r"/properties/ordered_ids/uniqueItems: uniqueItems",
        ):
            provider_schema.validate_provider_schema(schema)

    def test_unknown_keyword_is_rejected_closed_world(self) -> None:
        schema = json.loads(json.dumps(tasks.load_task("p1-selection").schema))
        schema["properties"]["selected_ids"]["contains"] = {"type": "string"}
        with self.assertRaisesRegex(provider_schema.ProviderSchemaError, "outside closed-world"):
            provider_schema.validate_provider_schema(schema)

    def test_policy_is_bound_to_batch2_direct_rejection_evidence(self) -> None:
        policy = provider_schema.load_policy()
        binding = policy["evidence_bindings"][0]
        source = ROOT / binding["source_path"]
        self.assertEqual(tasks.sha256_bytes(source.read_bytes()), binding["source_sha256"])
        self.assertIn("uniqueItems", source.read_text(encoding="utf-8"))

    def test_p4_exact_verifier_rejects_duplicate_after_wire_repair(self) -> None:
        task = tasks.load_task("p4-dependency")
        duplicate = json.loads(json.dumps(task.oracle))
        duplicate["ordered_ids"][-1] = duplicate["ordered_ids"][0]
        result = tasks.verify_raw_output(task, json.dumps(duplicate))
        self.assertEqual(result["status"], "semantic_miss")
        self.assertFalse(result["semantic_valid"])


if __name__ == "__main__":
    unittest.main()
