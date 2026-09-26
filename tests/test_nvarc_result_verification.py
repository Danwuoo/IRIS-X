"""Adversarial retrieved-teacher checks; fixtures never invoke a model."""

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify_nvarc_continuation import verify_m3
from irisx.arc_nvarc_sdg import BoundedLocalHFTeacher, run_teacher_pipeline
from irisx.arc_nvarc_teacher_profile import LIMITS, TOTAL_TOKENS, PROMPTS
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value, newline=True))


class RetrievedTeacherTests(unittest.TestCase):
    def test_dependency_tampering_and_unaccounted_tokens_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            package, output = Path(temp) / "package", Path(temp) / "output"
            plan = json.loads((ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/m3-teacher-draft-004.json").read_bytes())
            seed = {"record": {"record_id": "fixture", "train_demos": [], "second_description": "fixture"}}
            plan.update(approved=True, owner_decision="Decision 0033", kernel_id="danielwuu/" + plan["run_id"],
                        seed_record_sha256=hashlib.sha256(canonical_bytes(seed, newline=True)).hexdigest())
            for directory in (package, output):
                for name, value in (("plan", plan), ("seed", seed), ("prompts", PROMPTS)):
                    save(directory / (name + ".json"), value)
            (package / "wheel").mkdir()
            (package / "wheel/fixture.whl").write_bytes(b"fixture-only-not-a-wheel")
            (output / "fixture.whl").write_bytes(b"fixture-only-not-a-wheel")
            save(output / "hardware-uuid-preflight.json", {"bf16": True,
                 "rows": [[str(i), "NVIDIA L4", "23034", "fixture-uuid-" + str(i)] for i in range(4)]})
            save(output / "m3-teacher-terminal.json", {"return_code": 0, "wall_seconds": 10,
                 "plan_sha256": hashlib.sha256((package / "plan.json").read_bytes()).hexdigest()})

            class FixtureTeacher(BoundedLocalHFTeacher):
                def complete(self, stage, item, prompt):
                    texts = {"summary": "fixture rule", "mix": "fixture specification",
                             "input-logic": "def generate_puzzle_input(seed): return [[1]]",
                             "output-logic": "def generate_puzzle_output(input_grid): return input_grid"}
                    return {"text": texts[stage], "finish_reason": "eos", "input_tokens": 1,
                            "output_tokens": 2, "output_token_ids": [1, 2], "enable_thinking": False,
                            "model_material_digest": self.model_material_digest}

            provider = FixtureTeacher(None, None, model_material_digest=plan["teacher_model_manifest_digest"],
                 maximum_input_tokens=8192, maximum_output_tokens=3072, maximum_total_tokens=TOTAL_TOKENS,
                 stage_limits=LIMITS, enable_thinking=False, require_complete=True)
            run = output / "m3-teacher-small-004"
            pipeline = run_teacher_pipeline([seed["record"]], PROMPTS, provider, run / "stage-ledgers",
                                             seed=24, maximum_calls=4)
            responses = []
            for stage, ledger in pipeline["stages"].items():
                record = ledger["records"]["fixture"]
                responses.append({"stage": stage, "accepted": True, "rejection_reason": None,
                    "usage": {"input_tokens": 1, "output_tokens": 2}, "response_digest": record["response_digest"]})
            result = {"format": "irisx/nvarc-m3-teacher-small-result-v1",
                      "teacher_profile": "qwen-direct-complete-v1",
                      "run_id": plan["run_id"], "plan_digest": digest_value(plan),
                      "completed_calls": 4, "accepted_stages": 4, "reserved_calls": 4,
                      "reserved_tokens": TOTAL_TOKENS, "seed_record_sha256": plan["seed_record_sha256"],
                      "teacher_model_manifest_digest": plan["teacher_model_manifest_digest"],
                      "contains_evaluator_truth": False, "responses": responses}
            save(run / "result.json", result)
            checked = verify_m3(package, output)
            self.assertEqual((4, 8), (checked["input_tokens"], checked["output_tokens"]))
            path = run / "stage-ledgers/summary.json"
            original = json.loads(path.read_bytes())
            for change in ("dependency", "tokens", "content", "rejected"):
                ledger = copy.deepcopy(original)
                record = ledger["records"]["fixture"]
                if change == "dependency":
                    record["response"]["text"] = "changed rule"
                    provider.validate_response("summary", record["response"])
                elif change == "tokens":
                    record["response"]["output_token_ids"].append(3)
                elif change == "content":
                    record["response"]["content"] = "forged accepted content"
                else:
                    record["status"] = "rejected"
                record["response_digest"] = digest_value(record["response"])
                save(path, ledger)
                with self.subTest(change=change), self.assertRaises(ValidationError):
                    verify_m3(package, output)
            save(path, original)


if __name__ == "__main__":
    unittest.main()
