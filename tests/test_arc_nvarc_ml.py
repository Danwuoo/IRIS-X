"""Actual tiny Qwen3.5/PEFT tests, run by the strict optional ML profile."""

from __future__ import annotations

import copy
import importlib.util
import tempfile
from pathlib import Path
import unittest

from irisx.arc_nvarc_representation import (BEGIN, END, PAD, GridTokenizer,
                                             select_rows, validate_compact_model)
from irisx.arc_nvarc_training import TaskLocalAdapter, collate, inspect_lora_targets


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
        adapter.reset()
        for name, value in get_peft_model_state_dict(adapter.model).items():
            self.assertTrue(torch.equal(value.cpu(), adapter.initial[name]), name)
        bad = {**task, "train": [{"input": [[1]], "output": []}]}
        with self.assertRaises(Exception):
            adapter.adapt(bad)
        for name, value in get_peft_model_state_dict(adapter.model).items():
            self.assertTrue(torch.equal(value.cpu(), adapter.initial[name]), name)


if __name__ == "__main__":
    unittest.main()
