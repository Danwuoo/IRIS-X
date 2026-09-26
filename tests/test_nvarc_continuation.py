"""Deployment and teacher stage regressions, with no external calls."""

import json
from pathlib import Path
import tempfile
import unittest
import hashlib
import sys

from irisx.arc_nvarc_sdg import (extract_teacher_program, validate_teacher_response,
                                run_teacher_pipeline)
from irisx.arc_nvarc_source_continuation import validate_plan
from irisx.errors import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from nvarc_continuation_authorization import authorize


class ContinuationTests(unittest.TestCase):
    def test_authorization_binds_exact_draft_and_new_decision(self):
        for filename, decision in (("m2-source-cont-draft-001.json", "Decision 0033"),
                                   ("m3-teacher-draft-004.json", "Decision 0033"),
                                   ("m2-source-cont-draft-002.json", "Decision 0034"),
                                   ("m3-teacher-draft-005.json", "Decision 0034")):
            raw = (ROOT / "trials/arc-agi-2-qwen35-nvarc/configs" / filename).read_bytes()
            plan = json.loads(raw)
            binding = {"approved": True, "owner_decision": decision,
                       "run_id": plan["run_id"], "kernel_id": "danielwuu/" + plan["run_id"],
                       "draft_plan_sha256": hashlib.sha256(raw).hexdigest()}
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "auth.json"
                path.write_text(json.dumps(binding))
                self.assertTrue(authorize(plan, raw, path)["approved"])
                for key, value in (("owner_decision", "Decision 0033" if decision == "Decision 0034" else "Decision 0034"),
                                   ("draft_plan_sha256", "0" * 64), ("run_id", "old-run")):
                    path.write_text(json.dumps({**binding, key: value}))
                    with self.subTest(key=key), self.assertRaises(ValidationError):
                        authorize(plan, raw, path)

    def test_restart_preserves_workload_and_does_not_reauthorize_retrieval(self):
        config = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs"
        for old, new in (("m2-source-cont-draft-001.json", "m2-source-cont-draft-002.json"),
                         ("m3-teacher-draft-004.json", "m3-teacher-draft-005.json")):
            before = json.loads((config / old).read_bytes())
            after = json.loads((config / new).read_bytes())
            self.assertNotEqual(before["run_id"], after["run_id"])
            self.assertEqual(0, after["maximum_output_retrievals"])
            keys = {"run_id", "kernel_id", "maximum_output_retrievals", "maximum_model_dataset_versions"}
            self.assertEqual({k: v for k, v in before.items() if k not in keys},
                             {k: v for k, v in after.items() if k not in keys})
        plan = json.loads((config / "m2-source-cont-draft-002.json").read_bytes())
        validate_plan(plan, approved=False)
        approved = {**plan, "approved": True, "owner_decision": "Decision 0034",
                    "kernel_id": "danielwuu/" + plan["run_id"]}
        validate_plan(approved, approved=True)
        for key, value in (("maximum_output_retrievals", 1), ("maximum_model_dataset_versions", 1),
                           ("owner_decision", "Decision 0033")):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_plan({**approved, key: value}, approved=True)
        for old, new, before, after in (
                ("nvarc_source_continuation_notebook.py.tmpl", "nvarc_source_continuation_notebook_002.py.tmpl",
                 "source-cont-001", "source-cont-002"),
                ("nvarc_m3_teacher_notebook_004.py.tmpl", "nvarc_m3_teacher_notebook_005.py.tmpl",
                 "teacher-small-004", "teacher-small-005")):
            self.assertEqual((ROOT / "tools" / old).read_text().replace("Decision 0033", "Decision 0034").replace(before, after),
                             (ROOT / "tools" / new).read_text())

    def test_rejected_reply_is_retained_and_stops_dependent_calls(self):
        class TruncatedTeacher:
            identity = "fixture-truncated-direct-v1"
            billed_calls = 1
            calls = 0

            def complete(self, *args):
                self.calls += 1
                return {"text": "unfinished rule", "finish_reason": "length", "output_tokens": 512}

            validate_response = staticmethod(validate_teacher_response)

        provider = TruncatedTeacher()
        with tempfile.TemporaryDirectory() as temp:
            prompts = {stage: "prompt" for stage in ("summary", "mix", "input-logic", "output-logic")}
            for _ in range(2):
                result = run_teacher_pipeline([{"record_id": "a"}], prompts, provider, Path(temp),
                                              seed=24, maximum_calls=4)
            record = result["stages"]["summary"]["records"]["a"]
            self.assertEqual("rejected", record["status"])
            self.assertEqual("unfinished rule", record["response"]["text"])
            self.assertEqual((1, 1), (provider.calls, result["reserved_calls"]))
            self.assertEqual({"summary"}, set(result["stages"]))

    def test_program_parser_rejects_truncation_missing_ambiguous_and_wrong_signature(self):
        for raw in ("```python\ndef generate_puzzle_input(seed): return [[1]]",
                    "def helper(seed): return [[1]]", "def generate_puzzle_input(): return [[1]]",
                    "def generate_puzzle_input(seed):\n", "```python\ndef generate_puzzle_input(seed): return [[1]]\n```\n" * 2):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                extract_teacher_program(raw, "generate_puzzle_input")
        raw = "Explanation\n```python\ndef generate_puzzle_input(seed): return [[seed % 10]]\n```"
        response = {"text": raw, "finish_reason": "eos"}
        validate_teacher_response("input-logic", response)
        self.assertEqual(raw, response["text"])
        self.assertEqual("def generate_puzzle_input(seed): return [[seed % 10]]", response["content"])

    def test_current_truncated_teacher_responses_are_not_accepted(self):
        # Portable failure shapes from the retained batch, never execute source.
        for stage, raw in (("summary", "Thinking Process: unfinished"),
                           ("mix", "unfinished description"),
                           ("input-logic", "```python\ndef generate_puzzle_input(seed):\n    pass"),
                           ("output-logic", "```python\ndef helper(input_grid):\n    pass")):
            with self.subTest(stage=stage), self.assertRaises(ValidationError):
                validate_teacher_response(stage, {"text": raw, "finish_reason": "length"})

    def test_continuation_does_not_reauthorize_sft_or_legacy_identity(self):
        plan = json.loads((ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/m2-source-cont-draft-001.json").read_bytes())
        validate_plan(plan, approved=False)
        for key, value in (("maximum_sft_steps", 8), ("run_id", "nvarc-m2-fsdp-sft-002"),
                           ("retry", True), ("maximum_source_generation_calls", 5), ("approved", True)):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_plan({**plan, key: value}, approved=False)


if __name__ == "__main__":
    unittest.main()
