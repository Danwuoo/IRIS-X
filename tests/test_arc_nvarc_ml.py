"""Actual tiny Qwen3.5/PEFT tests, run by the strict optional ML profile."""

from __future__ import annotations

import copy
import importlib.util
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from irisx.arc_nvarc_candidates import QwenCandidateBackend
from irisx.arc_nvarc_compact_pilot import visible_workload
from irisx.arc_nvarc_kaggle import execute_model_task
from irisx.arc_nvarc_representation import (BEGIN, END, PAD, GridTokenizer,
                                             compact_loaded_model, select_rows,
                                             validate_compact_model)
from irisx.arc_nvarc_runtime import (build_outbound, build_result, finish_task,
                                     make_binding, new_checkpoint, reserve_task,
                                     score_sealed, verify_outbound, verify_result)
from irisx.arc_nvarc_training import (TaskLocalAdapter, collate, inspect_lora_targets,
                                       load_compact_model)
from irisx.canonical import digest_value
from irisx.errors import ValidationError


class NvarcMLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        missing = [name for name in ("torch", "transformers", "peft", "safetensors")
                   if importlib.util.find_spec(name) is None]
        if missing:
            raise unittest.SkipTest("optional ML dependencies missing: " + ", ".join(missing))

    def _tiny_qwen(self):
        import torch
        from transformers import Qwen3_5Config, Qwen3_5ForConditionalGeneration

        config = Qwen3_5Config()
        text = config.text_config
        # The pinned Qwen3.5-4B config ties both rows; constructor defaults do not.
        config.tie_word_embeddings = True
        text.tie_word_embeddings = True
        text.vocab_size = 32
        text.hidden_size = 64
        text.intermediate_size = 128
        text.num_hidden_layers = 2
        text.layer_types = ["linear_attention", "full_attention"]
        text.num_attention_heads = 4
        text.num_key_value_heads = 2
        text.head_dim = 16
        text.linear_num_key_heads = 4
        text.linear_num_value_heads = 4
        text.linear_key_head_dim = 16
        text.linear_value_head_dim = 16
        text.max_position_embeddings = 128
        text.rope_parameters = {"rope_type": "default", "rope_theta": 10000.0,
                                "mrope_section": [1, 1, 0], "mrope_interleaved": True}
        config.vision_config.depth = 1
        config.vision_config.hidden_size = 64
        config.vision_config.intermediate_size = 128
        config.vision_config.num_heads = 4
        config.vision_config.out_hidden_size = 64
        config.vision_config.num_position_embeddings = 16
        config.vocab_size = 32
        model = Qwen3_5ForConditionalGeneration(config)
        model.generation_config = copy.deepcopy(model.generation_config)
        return model

    def test_tiny_conversion_reload_and_masked_gradient(self) -> None:
        import torch
        from transformers import Qwen3_5ForConditionalGeneration

        model = self._tiny_qwen()
        source = model.get_input_embeddings().weight.detach().clone()
        manifest = {"symbols": [{"source_token_ids": [index]} for index in range(16)]}
        selected = select_rows(source, manifest)
        model.resize_token_embeddings(16)
        with torch.no_grad():
            model.get_input_embeddings().weight.copy_(selected)
        for config in (model.config, model.config.text_config, model.generation_config):
            config.pad_token_id, config.eos_token_id, config.bos_token_id = PAD, END, BEGIN
        model.config.vocab_size = model.config.text_config.vocab_size = 16
        validate_compact_model(model, tied=True)
        with tempfile.TemporaryDirectory() as temp:
            model.save_pretrained(temp, safe_serialization=True)
            reloaded = Qwen3_5ForConditionalGeneration.from_pretrained(temp, local_files_only=True)
            validate_compact_model(reloaded, tied=True)
            self.assertTrue(torch.equal(selected, reloaded.get_input_embeddings().weight))
            tokens, labels = GridTokenizer().encode_pair([[1]], [[2]])
            batch = {key: torch.tensor(value) for key, value in
                     collate([{"input_ids": tokens, "labels": labels}], 128).items()}
            self.assertEqual([-100] * (len(tokens) - 2), labels[:-2])
            loss = reloaded(**batch).loss
            self.assertTrue(torch.isfinite(loss))
            loss.backward()
            self.assertTrue(any(parameter.grad is not None and torch.isfinite(parameter.grad).all()
                                and parameter.grad.abs().sum() > 0
                                for parameter in reloaded.parameters() if parameter.requires_grad))

    def test_peft_attachment_and_task_reset_after_success_and_failure(self) -> None:
        import torch
        from peft import get_peft_model_state_dict

        model = self._tiny_qwen()
        model.resize_token_embeddings(16)
        targets = inspect_lora_targets(model)
        self.assertTrue(any("linear_attn" in name for name in targets))
        adapter = TaskLocalAdapter(model, {"seed": 3, "rank": 2, "alpha": 4,
                                           "learning_rate": 0.001, "steps": 1,
                                           "max_sequence_length": 128,
                                           "augmentation_count": 1})
        task = {"task_id": "tiny", "train": [{"input": [[1]], "output": [[2]]}],
                "test": [{"input": [[3]]}]}
        adapter.adapt(task)
        groups = {"attention": False, "delta": False, "embedding": False, "head": False}
        for name, parameter in adapter.model.named_parameters():
            if parameter.grad is None or not bool(torch.any(parameter.grad != 0)):
                continue
            if ".self_attn." in name:
                groups["attention"] = True
            if ".linear_attn." in name:
                groups["delta"] = True
            if "embed_tokens" in name:
                groups["embedding"] = True
            if "lm_head" in name:
                groups["head"] = True
        self.assertTrue(all(groups.values()), groups)
        adapter.reset()
        for name, value in get_peft_model_state_dict(adapter.model).items():
            self.assertTrue(torch.equal(value.cpu(), adapter.initial[name]), name)
        bad = {**task, "train": [{"input": [[1]], "output": []}]}
        with self.assertRaises(Exception):
            adapter.adapt(bad)
        for name, value in get_peft_model_state_dict(adapter.model).items():
            self.assertTrue(torch.equal(value.cpu(), adapter.initial[name]), name)

    def test_nonfinite_gradient_and_updated_adapter_reset(self) -> None:
        import torch
        from peft import get_peft_model_state_dict

        adapter = TaskLocalAdapter(self._tiny_qwen(), {"seed": 3, "rank": 2, "alpha": 4,
                                                      "learning_rate": 0.001, "steps": 1,
                                                      "max_sequence_length": 128,
                                                      "augmentation_count": 1})
        task = {"task_id": "finite-check", "train": [{"input": [[1]], "output": [[2]]}],
                "test": [{"input": [[3]]}]}
        parameter = next(value for value in adapter.model.parameters() if value.requires_grad)
        hook = parameter.register_hook(lambda grad: torch.full_like(grad, float("nan")))
        with self.assertRaisesRegex(ValidationError, "non-finite task adaptation gradient"):
            adapter.adapt(task)
        hook.remove()
        self.assertEqual("failed", adapter.last_observation["status"])
        self.assertEqual(0, adapter.last_observation["steps"])
        for name, value in get_peft_model_state_dict(adapter.model).items():
            self.assertTrue(torch.equal(value.cpu(), adapter.initial[name]), name)

        original_step = torch.optim.AdamW.step
        def corrupt_step(optimizer, *args, **kwargs):
            result = original_step(optimizer, *args, **kwargs)
            with torch.no_grad():
                parameter.fill_(float("inf"))
            return result
        with mock.patch.object(torch.optim.AdamW, "step", corrupt_step):
            with self.assertRaisesRegex(ValidationError, "non-finite task adapter"):
                adapter.adapt(task)
        self.assertEqual("failed", adapter.last_observation["status"])
        for name, value in get_peft_model_state_dict(adapter.model).items():
            self.assertTrue(torch.equal(value.cpu(), adapter.initial[name]), name)

    def test_tiny_real_model_two_task_four_test_result_roundtrip(self) -> None:
        import json
        import torch
        from peft import get_peft_model_state_dict

        root = Path(__file__).resolve().parents[1]
        visible = json.loads((root / "trials/arc-agi-2-qwen35-nvarc/configs/compact-complete-visible.json").read_bytes())
        config = json.loads((root / "trials/arc-agi-2-qwen35-nvarc/configs/compact-complete-001.json").read_bytes())["config"]
        config = {**config, "dfs_max_expansions": 16, "maximum_new_tokens": 4,
                  "dfs_max_score": 100.0}
        model = self._tiny_qwen()
        manifest = {"symbols": [{"source_token_ids": [index]} for index in range(16)]}
        tied, selected, _ = compact_loaded_model(model, manifest)
        self.assertTrue(tied)
        workload = visible_workload(visible)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            compact = out / "compact"
            compact.mkdir()
            model.save_pretrained(compact, safe_serialization=True)
            (compact / "grid-vocab.json").write_text("{}")
            (compact / "material-manifest.json").write_text('{"tied_embeddings":true}')
            del model
            reloaded = load_compact_model(compact, dtype="float32")
            self.assertTrue(torch.equal(selected, reloaded.get_input_embeddings().weight))
            adapter = TaskLocalAdapter(reloaded, config["ttt"])
            backend = QwenCandidateBackend(reloaded, task_adapter=adapter,
                                           decoding="bounded-dfs", dfs_max_score=100.0,
                                           dfs_max_expansions=16)
            binding = make_binding(workload, run_id="tiny-compact-real-e2e",
                                   model_digest=digest_value("tiny-compact"),
                                   data_digest=digest_value(workload),
                                   tokenizer_digest=digest_value("tiny-grid-vocab"),
                                   runtime_digest=digest_value("tiny-wheel"), config=config)
            outbound = out / "outbound.zip"
            build_outbound(outbound, binding, workload)
            verify_outbound(outbound)
            checkpoint = new_checkpoint(binding, workload)
            records = []
            for case in workload["cases"]:
                reserve_task(checkpoint, binding, case["task_id"], rank=0, at_utc="synthetic")
                record = execute_model_task(case, backend, adapter, config, torch)
                self.assertEqual(2, len(record["tests"]))
                self.assertEqual(2, record["tests"][-1]["generation_calls_so_far"])
                self.assertEqual(1, record["adaptation"]["steps"])
                self.assertTrue(record["adaptation"]["gradient_groups_by_step"])
                self.assertGreater(record["explicit_forward_calls"], 0)
                self.assertGreater(record["verification_calls"], 0)
                self.assertTrue(all(test["attempts"] for test in record["tests"]))
                self.assertTrue(all(torch.equal(value.cpu(), adapter.initial[name])
                                    for name, value in get_peft_model_state_dict(adapter.model).items()))
                finish_task(checkpoint, case["task_id"], record)
                records.append(record)
            checkpoint["complete"] = True
            result = out / "result.zip"
            build_result(result, binding, workload, checkpoint,
                         {"format": "irisx/nvarc-execution", "run_id": binding["run_id"],
                          "internet_enabled": False, "external_paid_cost_usd": 0})
            verify_result(result, binding, workload)
            sealed = {"synthetic-rect-a": {"test": [{"output": [[4, 3]]}, {"output": [[6, 5]]}]},
                      "synthetic-rect-b": {"test": [{"output": [[4], [3]]}, {"output": [[6], [5]]}]}}
            self.assertEqual(4, score_sealed(sealed, records)["test_outputs"])
            self.assertNotIn(b'"expected_output"', result.read_bytes())

if __name__ == "__main__":
    unittest.main()
