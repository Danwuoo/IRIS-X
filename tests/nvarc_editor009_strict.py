"""Offline checks for the distinct public witness and no-exec AST contract."""

import copy
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

from irisx.arc_nvarc_combined import read
from irisx.arc_nvarc_data import visible_task
from irisx.arc_nvarc_editor009 import run_m2, run_m3, verify_branch
from irisx.arc_nvarc_public_witness import public_index_witness
from irisx.arc_nvarc_safe_ast import SafeASTProgramExecutor
from irisx.arc_nvarc_sdg import BoundedLocalHFTeacher
from irisx.arc_nvarc_semantics_v6 import accept_semantic_record
from irisx.arc_nvarc_source_continuation import TRAINING
from irisx.arc_nvarc_representation import compact_loaded_model
from irisx.arc_nvarc_upstream import sdg_source_bundle
from irisx.errors import ValidationError
from tools.stage_nvarc_combined import M2

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3"
PACKAGE = LOCAL / "combined-editor-009-final"
OBSERVATION = LOCAL / "combined-008-editor-observation-001"
STAGES = ("summary", "mix", "input-logic", "output-logic")


def saved_responses():
    return {stage: next(iter(read(OBSERVATION / "workers/m3/work/stage-ledgers" /
                                   (stage + ".json"))["records"].values()))["response"]
            for stage in STAGES}


class Editor009StrictTests(unittest.TestCase):
    def test_tiny_m2_keeps_model_and_public_witness_separate(self):
        import torch
        from tests.test_arc_nvarc_ml import NvarcMLTests
        torch.set_num_threads(2)
        torch.manual_seed(19)
        model = NvarcMLTests()._tiny_qwen().eval()
        compact_loaded_model(model, {"symbols": [{"source_token_ids": [i]} for i in range(16)]})
        original_to = model.to
        model.to = lambda target: original_to("cpu" if target == "cuda:0" else target)
        plan = read(PACKAGE / "plan.json")
        paths = {key: str(M2 / name) for key, name in
                 (("source_config", "source-config.json"), ("visible", "visible.json"),
                  ("training_evidence", "training-evidence.json"))}
        paths.update(m2_model="fixture", bundle=str(LOCAL / "combined-editor-003/source-bundle"))
        material = {"kind": "sft-inference-export",
                    "base_material_digest": read(Path(paths["source_config"]))["profiles"]["4b"]["material_digest"],
                    "training_identity_digest": TRAINING}
        with tempfile.TemporaryDirectory() as temp, patch(
                "irisx.arc_nvarc_training.load_compact_model", return_value=model), patch(
                "irisx.arc_nvarc_representation.verify_model_material", return_value=material):
            output = Path(temp)
            run_m2(plan, paths, output, lambda: None)
            result = read(output / "work/result.json")
            counts = verify_branch(plan, "m2", output)
        self.assertEqual(4, counts["generation_calls"])
        self.assertEqual(8, counts["ranked_candidates"])
        self.assertEqual(36, len(result["public_index_witness"]["source_index_order"]))
        self.assertFalse(result["public_witness_counts_as_model_candidate"])

    def test_public_index_witness_requires_all_demos_and_remains_separate(self):
        task = visible_task("00576224", read(PACKAGE / "visible.json")["00576224"])
        witness = public_index_witness(task)
        self.assertEqual(36, len(witness["source_index_order"]))
        self.assertEqual([3,2,3,2,3,2], witness["grid"][0])
        self.assertEqual([7,8,7,8,7,8], witness["grid"][1])
        damaged = copy.deepcopy(task)
        damaged["train"][1]["output"][0][0] = 9
        with self.assertRaises(ValidationError):
            public_index_witness(damaged)

    def test_safe_ast_rejects_extra_teacher_code_before_execution(self):
        code = saved_responses()["input-logic"]["content"]
        executor = SafeASTProgramExecutor()
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "must-not-exist"
            attack = code + f"\nopen({str(marker)!r}, 'w').write('bad')\n"
            with self.assertRaisesRegex(ValidationError, "safe AST input template differs"):
                executor.probe(attack, "generate_puzzle_input", seed=11)
            self.assertFalse(marker.exists())

    def test_safe_ast_wrong_permutation_fails_semantic_challenges(self):
        replies = copy.deepcopy(saved_responses())
        output = replies["output-logic"]
        self.assertIn("[7,8,6,5,4,3,2,0,1]", output["text"])
        output["text"] = output["text"].replace("[7,8,6,5,4,3,2,0,1]",
                                                  "[8,7,6,5,4,3,2,0,1]")
        seed = read(PACKAGE / "seed.json")["record"]
        with sdg_source_bundle(PACKAGE / "sdg-source",
                               read(PACKAGE / "plan.json")["branches"]["m3"]["sdg_source_digest"]):
            with self.assertRaisesRegex(ValidationError, "output_permutation_mismatch"):
                accept_semantic_record(seed, replies, SafeASTProgramExecutor())

    def test_saved_teacher_replies_pass_trusted_ast_worker_and_44_challenges(self):
        import transformers
        class Model:
            def eval(self):
                return self
        replies = saved_responses()
        class SavedBoundTeacher(BoundedLocalHFTeacher):
            def complete(self, stage, item, prompt):
                self.reserved_tokens += sum(self.stage_limits[stage].values())
                return copy.deepcopy(replies[stage])
        plan = read(PACKAGE / "plan.json")
        paths = {key: str(PACKAGE / name) for key, name in
                 (("seed", "seed.json"), ("prompts", "prompts.json"),
                  ("model_manifest", "model-manifest.json"), ("sdg_bundle", "sdg-source"))}
        paths["m3_model"] = "fixture"
        with tempfile.TemporaryDirectory() as temp, patch(
                "irisx.arc_nvarc_4b_pilot.verify_model_material"), patch.object(
                transformers.AutoTokenizer, "from_pretrained", return_value=None), patch.object(
                transformers.AutoModelForMultimodalLM, "from_pretrained", return_value=Model()), patch(
                "irisx.arc_nvarc_sdg.BoundedLocalHFTeacher", SavedBoundTeacher):
            output = Path(temp)
            run_m3(plan, paths, output, lambda: None)
            result = read(output / "work/result.json")
            accepted = read(output / "work/accepted-pairs.json")
            counts = verify_branch(plan, "m3", output)
        self.assertEqual(5, result["accepted_pairs"])
        self.assertEqual(5, counts["accepted_pairs"])
        self.assertEqual(44, accepted["program_invocations"])
        self.assertEqual("trusted-ast-interpretation", accepted["program_validation_mode"])
        self.assertFalse(accepted["teacher_programs_executed"])


if __name__ == "__main__":
    unittest.main()
