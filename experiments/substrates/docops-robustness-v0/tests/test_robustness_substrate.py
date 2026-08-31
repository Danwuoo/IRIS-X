from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SUBSTRATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUBSTRATE / "scripts"))
import qualify  # noqa: E402


CASES = json.loads(
    (SUBSTRATE / "inputs" / "qualification-cases.json").read_text(encoding="utf-8")
)["cases"]


class RobustnessSubstrateTests(unittest.TestCase):
    def test_all_declared_positive_transformations_qualify(self) -> None:
        records = [
            qualify.qualify_case(case)
            for case in CASES
            if case["expected_effect"] == "same_oracle"
        ]
        self.assertEqual(len(records), 4)
        self.assertTrue(all(record["qualification_passed"] for record in records))
        self.assertTrue(
            all(
                record["validator"]["source_oracle_sha256"]
                == record["validator"]["transformed_oracle_sha256"]
                for record in records
            )
        )

    def test_semantics_changing_selector_case_is_rejected(self) -> None:
        case = next(case for case in CASES if case["expected_effect"] != "same_oracle")
        record = qualify.qualify_case(case)
        self.assertTrue(record["qualification_passed"])
        self.assertFalse(record["validator"]["accepted_as_semantics_preserving"])
        self.assertNotEqual(
            record["validator"]["source_oracle_sha256"],
            record["validator"]["transformed_oracle_sha256"],
        )

    def test_path_validator_rejects_escape(self) -> None:
        case = next(
            case
            for case in CASES
            if case["transformation_id"] == "equivalent-relative-path-presentation-v0"
        )
        changed = json.loads(json.dumps(case))
        changed["parameters"]["presentation"] = "../../report.md"
        record = qualify.qualify_case(changed)
        self.assertFalse(record["qualification_passed"])

    def test_builders_are_deterministic(self) -> None:
        for case in CASES:
            first, first_bytes = qualify.build(case)
            second, second_bytes = qualify.build(case)
            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)

    def test_records_make_no_candidate_or_model_claim(self) -> None:
        for case in CASES:
            record = qualify.qualify_case(case)
            self.assertFalse(record["candidate_executed"])
            self.assertEqual(record["model_calls"], 0)
            self.assertEqual(record["paid_api_calls"], 0)


if __name__ == "__main__":
    unittest.main()
