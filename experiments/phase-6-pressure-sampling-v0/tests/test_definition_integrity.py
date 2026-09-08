from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import pressure_tasks as tasks  # noqa: E402
import validate_definitions as definitions  # noqa: E402


class DefinitionIntegrityTests(unittest.TestCase):
    def test_all_six_definitions_validate(self) -> None:
        result = definitions.validate()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["task_count"], 6)
        self.assertEqual(result["negative_case_count"], 48)

    def test_exact_oracles_are_derived_from_inputs(self) -> None:
        for key in tasks.TASK_KEYS:
            task = tasks.load_task(key)
            self.assertEqual(task.oracle, tasks.derive_oracle(key, task.task_input), key)
            self.assertTrue(tasks.verify_raw_output(task, json.dumps(task.oracle))["semantic_valid"], key)

    def test_verifier_negative_corpus_rejects_every_negative(self) -> None:
        corpus = tasks.load_object(definitions.NEGATIVE_CORPUS_PATH)
        for row in corpus["tasks"]:
            task = tasks.load_task(row["task_key"])
            for case in row["cases"]:
                result = tasks.verify_raw_output(task, case["raw_output"])
                self.assertEqual(result["status"], case["expected_status"], f"{task.key}/{case['case_id']}")
                self.assertEqual(result["semantic_valid"], case["case_id"] == "correct")

    def test_cross_task_outputs_never_gain_authority(self) -> None:
        loaded = {key: tasks.load_task(key) for key in tasks.TASK_KEYS}
        for source_key, source in loaded.items():
            raw = json.dumps(source.oracle)
            for target_key, target in loaded.items():
                if source_key != target_key:
                    self.assertFalse(tasks.verify_raw_output(target, raw)["semantic_valid"], f"{source_key}->{target_key}")

    def test_contract_program_and_oracle_identities_are_distinct(self) -> None:
        loaded = [tasks.load_task(key) for key in tasks.TASK_KEYS]
        for field in ("task_id", "contract_id", "program_id", "deterministic_oracle_id"):
            self.assertEqual(len({task.contract[field] for task in loaded}), 6, field)

    def test_deterministic_regeneration_changes_no_bytes(self) -> None:
        paths = [
            definitions.MANIFEST_PATH,
            definitions.NEGATIVE_CORPUS_PATH,
            ROOT / "definition/predicate-derivation-rules.json",
            *(ROOT / "tasks" / key / "oracle.json" for key in tasks.TASK_KEYS),
        ]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        definitions.write_derived()
        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

