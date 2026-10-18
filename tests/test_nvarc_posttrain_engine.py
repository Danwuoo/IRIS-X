"""Synthetic CPU numerical/admission tests. Not official weight/GPU validation."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_OPTIONAL = ("torch", "transformers", "peft", "pydantic", "tokenizers", "safetensors")
_MISSING = [name for name in _OPTIONAL if importlib.util.find_spec(name) is None]
if not _MISSING:
    import torch
    from tokenizers import AddedToken, Regex, Tokenizer, decoders, pre_tokenizers
    from tokenizers.models import WordLevel
    from transformers import PreTrainedTokenizerFast, Qwen3Config, Qwen3ForCausalLM
    from tools.nvarc_posttrain_20261017.engine import (
        CompactEngine, FatalUpdateError, VOCAB, OFFICIAL_SHAPES, adapter_state,
        load_compact_tokenizer, make_optimizer, model_contract, state_digest,
        tensor_inventory, validate_tokenizer, validate_trainables,
    )


def tokenizer_fixture():
    backend = Tokenizer(WordLevel({key: value for key, value in VOCAB.items() if value < 13},
                                  unk_token="<|endoftext|>"))
    backend.pre_tokenizer = pre_tokenizers.Sequence([
        pre_tokenizers.Split(Regex("user|assistant|[0-9]|\\n"), behavior="isolated"),
        pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False),
    ])
    backend.decoder = decoders.ByteLevel()
    backend.add_special_tokens([AddedToken(token, special=True, normalized=False)
                                for token in ("<|endoftext|>", "<|im_start|>", "<|im_end|>")])
    return PreTrainedTokenizerFast(tokenizer_object=backend,
                                  eos_token="<|im_end|>", pad_token="<|endoftext|>")


def tiny_engine(*, model_seed=123, sample_seed=7, adapter_seed=7, dtype=None, rank=4, identity=None,
                probability_policy="outer-autocast-compact-head-v1"):
    with torch.random.fork_rng():
        torch.manual_seed(model_seed)
        config = Qwen3Config(vocab_size=16, hidden_size=32, intermediate_size=64,
                            num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1,
                            head_dim=16, attention_dropout=0.0, tie_word_embeddings=False,
                            bos_token_id=13, eos_token_id=15)
        config._attn_implementation = "sdpa"
        return CompactEngine.from_base(Qwen3ForCausalLM(config), tokenizer_fixture(),
            base_identity=identity or {"fixture": "tiny-123", "weight_sha256": "a" * 64},
            device="cpu", test_fixture=True, rank=rank, alpha=16,
            seed=sample_seed, adapter_seed=adapter_seed, base_dtype=dtype or torch.float32,
            probability_policy=probability_policy)


def example():
    return {"prompt_ids": [14, 11, 10, 1, 2, 15, 10, 14, 12, 10],
            "completion_ids": [3, 4, 10, 5, 6, 15], "demos_dropped": 0}


def origin():
    return {"phase": "pre_public", "public_ttt_applied": False, "public_labels_used": False,
            "run_id": "synthetic-cpu", "source_sha256": "b" * 64}


def pin(saved):
    return {"root": saved["root"], "manifest_sha256": saved["manifest_sha256"]}


def rewrite_manifest(root, mutate):
    path = root / "manifest.json"
    data = json.loads(path.read_bytes())
    mutate(data)
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                     allow_nan=False).encode() + b"\n"
    path.write_bytes(raw)
    return {"root": str(root), "manifest_sha256": hashlib.sha256(raw).hexdigest()}


@unittest.skipIf(bool(_MISSING), "Optional compact model dependencies missing: " + ", ".join(_MISSING))
class CompactEngineCPU(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def setUp(self):
        self.engine = tiny_engine()

    def test_adapter_initialization_seed_separate_from_rollout_and_process_rng(self):
        global_before = torch.random.get_rng_state().clone()
        paired = tiny_engine(sample_seed=123456, adapter_seed=7)
        self.assertEqual(state_digest(adapter_state(self.engine.model)), state_digest(adapter_state(paired.model)))
        different = tiny_engine(sample_seed=7, adapter_seed=8)
        self.assertNotEqual(state_digest(adapter_state(self.engine.model)), state_digest(adapter_state(different.model)))
        self.assertTrue(torch.equal(global_before, torch.random.get_rng_state()))
        self.assertEqual(paired.adapter_seed, 7)
        self.assertNotEqual(self.engine.generator.initial_seed(), paired.generator.initial_seed())

    def test_exact_tokenizer_roundtrip_and_serialized_backend(self):
        self.assertEqual(validate_tokenizer(self.engine.tokenizer)["vocab_size"], 16)
        with tempfile.TemporaryDirectory() as directory:
            self.engine.tokenizer.save_pretrained(directory)
            reloaded = load_compact_tokenizer(directory)
            self.assertEqual(reloaded.encode("user", add_special_tokens=False), [11])
            self.assertEqual(reloaded.encode("assistant", add_special_tokens=False), [12])
            self.assertEqual(validate_tokenizer(reloaded), self.engine.tokenizer_admission)
        with patch.object(self.engine.tokenizer, "encode", return_value=[]):
            with self.assertRaisesRegex(ValueError, "exact encode/decode probe"):
                validate_tokenizer(self.engine.tokenizer)

    def test_actual_trainable_inventory_untied_rs_scaling_and_checkpointing(self):
        report = self.engine.trainable_inventory
        self.assertEqual(report["tensor_count"], 2 * 7 * 2 + 2)
        self.assertEqual(report["parameter_count"], 5120)
        self.assertTrue(all(p.dtype == torch.float32 for p in self.engine.parameters))
        self.assertTrue(self.engine.model.is_gradient_checkpointing)
        for module in self.engine.model.modules():
            if hasattr(module, "_gradient_checkpointing_func"):
                self.assertFalse(module._gradient_checkpointing_func.keywords["use_reentrant"])
        embeddings = self.engine.model.get_input_embeddings().modules_to_save["default"].weight
        head = self.engine.model.get_output_embeddings().modules_to_save["default"].weight
        self.assertNotEqual(embeddings.data_ptr(), head.data_ptr())
        self.assertEqual(tuple(embeddings.shape), (16, 32))
        self.assertEqual(tuple(head.shape), (16, 32))
        for module in self.engine.model.modules():
            if hasattr(module, "lora_A") and "default" in module.lora_A:
                self.assertEqual(module.scaling["default"], 8)
        frozen = next(p for p in self.engine.model.parameters() if not p.requires_grad)
        frozen.requires_grad_(True)
        with self.assertRaisesRegex(ValueError, "trainable tensor inventory"):
            validate_trainables(self.engine.model, rank=4, alpha=16, base_dtype=torch.float32)

    def test_asymmetric_query_width_and_production_rank64_alpha16(self):
        # Like official 4B: attention_heads * head_dim is NOT hidden_size.
        config = Qwen3Config(vocab_size=16, hidden_size=32, intermediate_size=80,
                            num_hidden_layers=1, num_attention_heads=4, num_key_value_heads=1,
                            head_dim=16, bos_token_id=13, eos_token_id=15, tie_word_embeddings=False)
        config._attn_implementation = "sdpa"
        engine = CompactEngine.from_base(Qwen3ForCausalLM(config), tokenizer_fixture(),
                    base_identity={"fixture": "asymmetric"}, device="cpu", test_fixture=True)
        inventory = engine.trainable_inventory["tensors"]
        prefix = "base_model.model.model.layers.0.self_attn."
        self.assertEqual(inventory[prefix + "q_proj.lora_B.default.weight"]["shape"], [64, 64])
        self.assertEqual(inventory[prefix + "o_proj.lora_A.default.weight"]["shape"], [64, 64])
        self.assertEqual(inventory[prefix + "o_proj.lora_B.default.weight"]["shape"], [32, 64])
        self.assertEqual(engine.trainable_inventory["rank"], 64)
        self.assertEqual(engine.trainable_inventory["alpha"], 16)
        for module in engine.model.modules():
            if hasattr(module, "lora_A") and "default" in module.lora_A:
                self.assertEqual(module.scaling["default"], 2)
        self.assertTrue(engine.sft_step(example(), make_optimizer(engine.model, 1e-3))["updated"])

    def test_full_head_and_embedding_receive_gradients_base_preserved(self):
        before = {n: p.detach().clone() for n, p in self.engine.model.named_parameters() if not p.requires_grad}
        item = example()
        logps = self.engine.completion_logps(item["prompt_ids"] + item["completion_ids"], len(item["prompt_ids"]))
        loss = -logps[len(item["prompt_ids"]):].mean()
        loss.backward()
        for name in ("base_model.model.model.embed_tokens.modules_to_save.default.weight",
                     "base_model.model.lm_head.modules_to_save.default.weight"):
            gradient = dict(self.engine.model.named_parameters())[name].grad
            self.assertIsNotNone(gradient)
            self.assertTrue(torch.isfinite(gradient).all())
            self.assertGreater(gradient.abs().sum().item(), 0)
        optimizer = make_optimizer(self.engine.model, 1e-3)
        self.assertTrue(self.engine.commit(optimizer)["updated"])
        for name, previous in before.items():
            self.assertTrue(torch.equal(dict(self.engine.model.named_parameters())[name], previous), name)

    def test_bfloat16_base_fp32_trainables_sft_and_mask(self):
        engine = tiny_engine(dtype=torch.bfloat16)
        self.assertTrue(all(p.dtype == torch.bfloat16 for p in engine.model.parameters() if not p.requires_grad))
        self.assertTrue(all(p.dtype == torch.float32 for p in engine.parameters))
        item = example()
        item["loss_mask"] = [0] * len(item["prompt_ids"]) + [1] * len(item["completion_ids"])
        report = engine.sft_step(item, make_optimizer(engine.model, 1e-3))
        self.assertTrue(report["updated"])
        self.assertEqual(report["supervised_tokens"], 6)
        self.assertTrue(math.isfinite(report["loss"]))
        for row in engine.generate(item["prompt_ids"], count=2, max_new_tokens=5, sample=True):
            current = engine.completion_logps(row["input_ids"], row["prompt_length"])
            self.assertLess((current.detach() - torch.tensor(row["behavior_log_probs"])).abs().max().item(), 0.05)

    def test_full16_behavior_replay_and_global_rng_independence(self):
        original = torch.multinomial
        distributions = []
        def capture(probabilities, count, **kwargs):
            distributions.append(probabilities.detach().clone())
            self.assertIs(kwargs["generator"], self.engine.generator)
            return original(probabilities, count, **kwargs)
        state = torch.random.get_rng_state().clone()
        with patch("torch.multinomial", side_effect=capture):
            rows = self.engine.generate(example()["prompt_ids"], count=4, max_new_tokens=7, sample=True)
        self.assertTrue(torch.equal(state, torch.random.get_rng_state()))
        for values in distributions:
            self.assertEqual(tuple(values.shape), (4, 16))
            self.assertTrue((values > 0).all())
            torch.testing.assert_close(values.sum(-1), torch.ones(4))
        for row in rows:
            current = self.engine.completion_logps(row["input_ids"], row["prompt_length"])
            torch.testing.assert_close(current.detach(), torch.tensor(row["behavior_log_probs"]), atol=1e-6, rtol=1e-6)
            self.assertEqual(row["completion_ids"], row["input_ids"][row["prompt_length"]:])
        other = tiny_engine()
        torch.rand(1000)  # Sampling is not affected by unrelated process RNG use.
        self.assertEqual(rows, other.generate(example()["prompt_ids"], count=4, max_new_tokens=7, sample=True))

    def test_eos15_only_not_generation_config_endoftext_or_roles(self):
        self.engine.model.generation_config.eos_token_id = [0, 13, 14, 15]
        self.engine.tokenizer.eos_token_id = 13  # Generation must use admitted constant, never this mutable field.
        choices = iter([13, 14, 12, 10, 15])
        def scripted(probabilities, count, **kwargs):
            return torch.full((probabilities.shape[0], 1), next(choices), dtype=torch.long)
        with patch("torch.multinomial", side_effect=scripted):
            rows = self.engine.generate([14, 11, 10, 0, 15, 14, 12, 10], count=2, max_new_tokens=8, sample=True)
        self.assertEqual(self.engine.forward_calls, 5)
        self.assertEqual(self.engine.sampled_tokens, 10)
        for row in rows:
            self.assertEqual(row["completion_ids"], [13, 14, 12, 10, 15])
            self.assertEqual(row["stop"], "completed")
            self.assertEqual(row["completion_tokens"], 5)
        # Restore tokenizer before a fresh fixture admission elsewhere.
        self.engine.tokenizer.eos_token_id = 15

    def test_finished_rows_do_not_retain_filler_or_extra_logps(self):
        choices = iter([[15, 13], [1, 14], [2, 15]])
        with patch("torch.multinomial", side_effect=lambda *args, **kwargs: torch.tensor(next(choices))[:, None]):
            rows = self.engine.generate([14, 12, 10], count=2, max_new_tokens=5, sample=True)
        self.assertEqual(rows[0]["completion_ids"], [15])
        self.assertEqual(rows[1]["completion_ids"], [13, 14, 15])
        self.assertEqual(self.engine.sampled_tokens, 4)
        self.assertEqual(len(rows[0]["behavior_log_probs"]), 4)

    def test_heterogeneous_greedy_batch_matches_single_prompts(self):
        prompts = [[14, 12, 10], example()["prompt_ids"], [14, 11, 10, 2, 3, 4, 15, 14, 12, 10]]
        batched = self.engine.generate_prompts(prompts, max_new_tokens=7)
        for prompt, row in zip(prompts, batched):
            single = self.engine.generate(prompt, max_new_tokens=7)[0]
            self.assertEqual(row["input_ids"], single["input_ids"])
            torch.testing.assert_close(torch.tensor(row["behavior_log_probs"]),
                                       torch.tensor(single["behavior_log_probs"]), atol=1e-6, rtol=1e-6)

    def test_generation_bounds_and_raw_id_validation(self):
        for kwargs in ({"max_new_tokens": 932}, {"max_new_tokens": 0}, {"count": True}, {"count": 65}, {"sample": 1}):
            with self.assertRaises(ValueError):
                self.engine.generate([14, 12, 10], **kwargs)
        for prompt in ([], [16], [-1], [True], [0] * 8192):
            with self.assertRaises(ValueError):
                self.engine.generate(prompt, max_new_tokens=1)
        with self.assertRaises(ValueError):
            self.engine.completion_logps([0, 16], 1)
        with self.assertRaises(ValueError):
            self.engine.generate_prompts([[0]] * 9, max_new_tokens=1)

    def test_actual_af3_update_inherits_ddis_and_complete_group(self):
        rows = self.engine.generate(example()["prompt_ids"], count=4, max_new_tokens=4, sample=True)
        for i, row in enumerate(rows):
            row.update(sample_id=f"s{i}", group_id=f"g{i // 2}", reward=float(i % 2))
        before = state_digest(adapter_state(self.engine.model))
        report = self.engine.af3_update(rows, make_optimizer(self.engine.model, 1e-3), expected_groups=["g0", "g1"], group_size=2)
        self.assertTrue(report["updated"])
        self.assertEqual(report["mixed_groups"], 2)
        self.assertEqual(report["replayed"], 4)
        self.assertLess(report["max_replay_logp_gap"], 1e-6)
        self.assertEqual(report["probability_measure"], "full-vocabulary-temperature-one")
        self.assertNotEqual(state_digest(adapter_state(self.engine.model)), before)

    def test_zero_signal_af3_preserves_all_parameters(self):
        rows = self.engine.generate([14, 12, 10], count=2, max_new_tokens=3, sample=True)
        for i, row in enumerate(rows):
            row.update(sample_id=str(i), group_id="g", reward=0.0)
        before = state_digest(adapter_state(self.engine.model))
        report = self.engine.af3_update(rows, make_optimizer(self.engine.model, 1e-3), expected_groups=["g"], group_size=2)
        self.assertFalse(report["updated"])
        self.assertEqual(report["reason"], "zero_reward_signal")
        self.assertEqual(state_digest(adapter_state(self.engine.model)), before)
        self.assertEqual(self.engine.optimizer_attempts, 0)

    def test_official_config_dimensions_and_rotary_metadata(self):
        for variant, shape in OFFICIAL_SHAPES.items():
            raw = {**shape, "architectures": ["Qwen3ForCausalLM"], "model_type": "qwen3",
                   "vocab_size": 16, "tie_word_embeddings": False, "attention_dropout": 0.0,
                   "attention_bias": False, "bos_token_id": 13, "eos_token_id": 15,
                   "hidden_act": "silu", "rms_norm_eps": 1e-6, "max_position_embeddings": 262144,
                   "layer_types": ["full_attention"] * shape["num_hidden_layers"],
                   "use_sliding_window": False, "sliding_window": None, "rope_theta": 5000000,
                   "rope_scaling": {"rope_type": "default", "mrope_interleaved": True,
                                    "mrope_section": [24, 20, 20]} if variant == "2b" else None}
            admitted = model_contract(raw, variant=variant)
            translated = copy.deepcopy(raw)
            translated["rope_parameters"] = admitted["rope_parameters"]
            translated.pop("rope_scaling")
            translated.pop("rope_theta")
            self.assertEqual(model_contract(translated), admitted)
            for field, wrong in (("vocab_size", 151936), ("tie_word_embeddings", True), ("hidden_size", 2049)):
                with self.assertRaises(ValueError):
                    model_contract({**raw, field: wrong})
            if variant == "2b":
                with self.assertRaisesRegex(ValueError, "rotary metadata"):
                    model_contract({**raw, "rope_scaling": None})

    def test_checkpoint_roundtrip_full_modules_preserves_base_and_rng(self):
        self.engine.sft_step(example(), make_optimizer(self.engine.model, 1e-3))
        with tempfile.TemporaryDirectory() as directory:
            saved = self.engine.save_checkpoint(Path(directory) / "selected", origin=origin())
            fresh = tiny_engine(sample_seed=99)
            rng_before = fresh.generator.get_state().clone()
            frozen_before = {n: p.detach().clone() for n, p in fresh.model.named_parameters() if not p.requires_grad}
            report = fresh.load_checkpoint(pin(saved))
            self.assertFalse(report["optimizer_resumed"])
            self.assertFalse(report["rng_resumed"])
            self.assertTrue(report["fresh_optimizer_required"])
            self.assertEqual(report["tensor_count"], 30)
            self.assertEqual(state_digest(adapter_state(fresh.model)), saved["state_sha256"])
            self.assertTrue(torch.equal(rng_before, fresh.generator.get_state()))
            for name, value in frozen_before.items():
                self.assertTrue(torch.equal(value, dict(fresh.model.named_parameters())[name]))
            manifest = json.loads((Path(saved["root"]) / "manifest.json").read_bytes())
            self.assertTrue(any("embed_tokens.modules_to_save.default.weight" in n for n in manifest["trainable_tensors"]))
            self.assertTrue(any("lm_head.modules_to_save.default.weight" in n for n in manifest["trainable_tensors"]))
            opt = make_optimizer(fresh.model, 1e-3)
            self.assertEqual(len(opt.state), 0)
            self.assertTrue(fresh.sft_step(example(), opt)["updated"])
            with self.assertRaises(ValueError):
                fresh.load_checkpoint(pin(saved))

    def test_checkpoint_rejects_identity_pin_shape_remapping_and_nonfinite_without_mutation(self):
        from safetensors.torch import load, save
        for corruption in ("identity", "pin", "rename", "shape", "nonfinite", "dtype", "extra"):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "checkpoint"
                saved = self.engine.save_checkpoint(root, origin=origin())
                fresh = tiny_engine()
                before = state_digest(adapter_state(fresh.model))
                spec = pin(saved)
                if corruption == "identity":
                    fresh.base_identity = {"different": "base"}
                elif corruption == "pin":
                    spec["manifest_sha256"] = "0" * 64
                elif corruption == "extra":
                    (root / "optimizer.pt").write_bytes(b"forbidden")
                else:
                    state = load((root / "trainable_state.safetensors").read_bytes())
                    key = next(iter(state))
                    if corruption == "rename":
                        state[key.replace(".default.", ".")] = state.pop(key)
                    elif corruption == "shape":
                        state[key] = state[key][:-1].clone()
                    elif corruption == "nonfinite":
                        state[key].view(-1)[0] = float("nan")
                    elif corruption == "dtype":
                        state[key] = state[key].to(torch.bfloat16)
                    body = save(state)
                    (root / "trainable_state.safetensors").write_bytes(body)
                    def mutate(manifest):
                        manifest["file"].update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
                        manifest["trainable_tensors"] = tensor_inventory(state)
                        manifest["state_sha256"] = state_digest(state)
                    spec = rewrite_manifest(root, mutate)
                with self.assertRaises(ValueError):
                    fresh.load_checkpoint(spec)
                self.assertEqual(state_digest(adapter_state(fresh.model)), before)

    def test_checkpoint_refuses_public_origin_symlink_and_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "original"
            saved = self.engine.save_checkpoint(root, origin=origin())
            original_bytes = {p.name: p.read_bytes() for p in root.iterdir()}
            with self.assertRaises(FileExistsError):
                self.engine.save_checkpoint(root, origin=origin())
            self.assertEqual(original_bytes, {p.name: p.read_bytes() for p in root.iterdir()})
            for field, value in (("phase", "post_public"), ("public_labels_used", True), ("public_ttt_applied", True)):
                with self.assertRaises(ValueError):
                    self.engine.save_checkpoint(Path(directory) / "bad", origin={**origin(), field: value})
            link = Path(directory) / "link"
            link.symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "regular checkpoint"):
                tiny_engine().load_checkpoint({**pin(saved), "root": str(link)})

    def test_checkpoint_rechecks_actual_config_and_rejects_post_admission_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "checkpoint"
            self.engine.model.config.tie_word_embeddings = True
            with self.assertRaises(ValueError):
                self.engine.save_checkpoint(root, origin=origin())
            self.assertFalse(root.exists())
            self.engine.model.config.tie_word_embeddings = False
            saved = self.engine.save_checkpoint(root, origin=origin())
            fresh = tiny_engine()
            layer = fresh.model.base_model.model.model.layers[0].self_attn.q_proj
            layer.scaling["default"] = 1.0
            before = state_digest(adapter_state(fresh.model))
            with self.assertRaisesRegex(ValueError, "scaling differs"):
                fresh.load_checkpoint(pin(saved))
            self.assertEqual(state_digest(adapter_state(fresh.model)), before)

    def test_checkpoint_partial_copy_failure_restores_initial_trainables(self):
        self.engine.sft_step(example(), make_optimizer(self.engine.model, 1e-3))
        with tempfile.TemporaryDirectory() as directory:
            saved = self.engine.save_checkpoint(Path(directory) / "checkpoint", origin=origin())
            fresh = tiny_engine()
            before = state_digest(adapter_state(fresh.model))
            from tools.nvarc_posttrain_20261017 import engine as module
            real_restore = module.restore_state
            calls = []
            def fail_once(model, state):
                calls.append(1)
                if len(calls) == 1:
                    with torch.no_grad():
                        next(p for p in model.parameters() if p.requires_grad).add_(9)
                    raise RuntimeError("synthetic copy failure")
                return real_restore(model, state)
            with patch.object(module, "restore_state", side_effect=fail_once):
                with self.assertRaisesRegex(RuntimeError, "synthetic copy failure"):
                    fresh.load_checkpoint(pin(saved))
            self.assertEqual(state_digest(adapter_state(fresh.model)), before)
            self.assertFalse(fresh._checkpoint_loaded)
            fresh.load_checkpoint(pin(saved))

    def test_nonfinite_commit_rolls_back_parameters_poisons_engine_no_optimizer_reset(self):
        optimizer = make_optimizer(self.engine.model, 1e-3)
        self.engine.sft_step(example(), optimizer)
        optimizer_state_count = len(optimizer.state)
        before = state_digest(adapter_state(self.engine.model))
        for p in self.engine.parameters:
            p.grad = torch.ones_like(p)
        def corrupt_step():
            with torch.no_grad():
                self.engine.parameters[0].fill_(float("nan"))
        with patch.object(optimizer, "step", side_effect=corrupt_step):
            with self.assertRaisesRegex(FatalUpdateError, "abort worker"):
                self.engine.commit(optimizer)
        self.assertEqual(state_digest(adapter_state(self.engine.model)), before)
        self.assertEqual(len(optimizer.state), optimizer_state_count)
        self.assertEqual(self.engine.optimizer_attempts, 2)
        self.assertEqual(self.engine.optimizer_steps, 1)
        with self.assertRaises(FatalUpdateError):
            self.engine.generate([14, 12, 10], max_new_tokens=1)
        with self.assertRaises(FatalUpdateError):
            self.engine.completion_logps([14, 12, 10, 15], 3)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FatalUpdateError):
                self.engine.save_checkpoint(Path(directory) / "forbidden", origin=origin())

    def test_partial_exception_and_nonfinite_optimizer_state_are_fatal(self):
        for mode in ("exception", "state"):
            with self.subTest(mode=mode):
                engine = tiny_engine()
                optimizer = make_optimizer(engine.model, 1e-3)
                before = state_digest(adapter_state(engine.model))
                for p in engine.parameters:
                    p.grad = torch.ones_like(p)
                def broken():
                    with torch.no_grad():
                        engine.parameters[0].add_(1)
                    if mode == "exception":
                        raise RuntimeError("synthetic partial optimizer failure")
                    optimizer.state[engine.parameters[0]]["exp_avg"] = torch.tensor(float("inf"))
                with patch.object(optimizer, "step", side_effect=broken):
                    with self.assertRaises(FatalUpdateError):
                        engine.commit(optimizer)
                self.assertEqual(state_digest(adapter_state(engine.model)), before)
                self.assertEqual(engine.optimizer_steps, 0)


if __name__ == "__main__":
    unittest.main()
