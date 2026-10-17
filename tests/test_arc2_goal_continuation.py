"""Optional continuation contracts; synthetic CPU checks, never ARC2 evidence."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import tempfile
import time
import unittest
from unittest.mock import patch

from tools.arc2_goal_sprint_20261017 import data
from tests.test_arc2_goal_model import CharacterTokenizer, TinyTokenizer

_MISSING = [name for name in ("torch", "transformers", "peft", "pydantic", "tokenizers", "safetensors")
            if importlib.util.find_spec(name) is None]
if not _MISSING:
    import torch
    from peft import LoraConfig, get_peft_model
    from safetensors.torch import load_file, save_file
    from tokenizers import Tokenizer
    from tokenizers.models import BPE
    from transformers import PreTrainedTokenizerFast, Qwen3Config, Qwen3ForCausalLM
    from tools.arc2_goal_sprint_20261017 import model, run
    from tests.test_arc2_goal_model import tiny_engine


def demos():
    return [{"input": [[i]], "output": [[i + 1]]} for i in (1, 3, 5)]


def fast_tokenizer():
    # A real tokenizer whose newline/< merge intentionally crosses answer spans.
    alphabet = sorted(set(data.render_prompt(demos(), [[7]]) + "USER\nASSISTANT\n0123456789"))
    vocabulary = {"<eos>": 0, "<unk>": 1, **{char: i + 2 for i, char in enumerate(alphabet)}}
    vocabulary["\n<"] = len(vocabulary)
    vocabulary["\n<g"] = len(vocabulary)
    backend = Tokenizer(BPE(vocabulary, [("\n", "<"), ("\n<", "g")], unk_token="<unk>"))
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=backend, eos_token="<eos>", unk_token="<unk>")
    tokenizer.chat_template = "{{ 'USER\\n' + messages[0]['content'] + '\\nASSISTANT\\n' }}"
    return tokenizer


def fast_engine():
    tokenizer = fast_tokenizer()
    torch.manual_seed(81)
    config = Qwen3Config(vocab_size=len(tokenizer), hidden_size=16, intermediate_size=32,
                        num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1,
                        head_dim=8, attention_dropout=0.0)
    config._attn_implementation = "sdpa"
    network = get_peft_model(Qwen3ForCausalLM(config), LoraConfig(
        r=2, lora_alpha=4, lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
    return model.Engine(network, tokenizer, device="cpu")


class PureContinuationTests(unittest.TestCase):
    def test_old_encoding_default_is_byte_and_key_identical(self):
        tok = CharacterTokenizer()
        example = data.encode_example(tok, demos(), [[7]], [[8]])
        text = tok.apply_chat_template([{"role": "user", "content": data.render_prompt(demos(), [[7]])}])
        self.assertEqual(example, {"prompt_ids": tok.encode(text), "completion_ids": tok.encode(data.answer_text([[8]])) + [0],
                                   "demos_used": 3, "demos_dropped": 0})

    def test_frozen_views_cover_d4_deterministically_and_inverse(self):
        grid = [[0, 1, 2], [3, 4, 5]]
        for count in (8, 16):
            views = data.inference_views(count, seed=3, task_id="synthetic", demo_count=5)
            random.seed(9999)
            self.assertEqual(views, data.inference_views(count, seed=3, task_id="synthetic", demo_count=5))
            self.assertNotEqual(views, data.inference_views(count, seed=4, task_id="synthetic", demo_count=5))
            self.assertEqual(len({(v["transform"]["rotation"], v["transform"]["transpose"]) for v in views}), 8)
            for view in views:
                self.assertEqual(sorted(view["demo_order"]), list(range(5)))
                spec = view["transform"]
                self.assertEqual(data.transform(data.transform(grid, **spec), **spec, inverse=True), grid)
        legacy = data.inference_views(2, seed=3, task_id="anything", demo_count=2)
        self.assertEqual([v["transform"] for v in legacy], [data.IDENTITY, data.SECOND_VIEW])
        self.assertEqual([v["demo_order"] for v in legacy], [[0, 1], [0, 1]])

    def test_parent_balancing_and_no_corpus_rng_change(self):
        tasks = {"a": {"train": demos()}, "b": {"train": demos()}}
        bundles = {"a": [{"task_id": f"bundle{i}", "train": demos()} for i in range(20)]}
        rng, original_rng = random.Random(44), random.Random(44)
        for _ in range(20):
            key, task, source = data.sample_sft_parent(tasks, rng)
            self.assertEqual(key, original_rng.choice(sorted(tasks)))
            self.assertIs(task, tasks[key])
            self.assertEqual(source["source"], "original")
        counts = {"a": 0, "b": 0, "generated": 0}
        rng = random.Random(20)
        for _ in range(20000):
            key, task, source = data.sample_sft_parent(tasks, rng, bundles)
            counts[key] += 1
            counts["generated"] += source["source"] == "curriculum"
            if key == "b":
                self.assertEqual(source["source"], "original")
        self.assertTrue(9700 < counts["a"] < 10300, counts)
        self.assertTrue(4700 < counts["generated"] < 5300, counts)


@unittest.skipIf(bool(_MISSING), "Optional ML dependencies missing: " + ", ".join(_MISSING))
class ContinuationModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    @unittest.skipUnless(os.environ.get("IRISX_GOAL_TOKENIZER_ROOT"), "Pinned private tokenizer overlay not supplied")
    def test_actual_hash_pinned_qwen_tokenizer_offsets(self):
        from transformers import AutoTokenizer
        root = Path(os.environ["IRISX_GOAL_TOKENIZER_ROOT"])
        contract_path = Path(__file__).resolve().parents[1] / "research/qwen14b-materials/material-contract.json"
        contract = json.loads(contract_path.read_bytes())
        for name, row in contract["overlay_files"].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), row["sha256"])
        tokenizer = AutoTokenizer.from_pretrained(root, local_files_only=True, trust_remote_code=False)
        self.assertTrue(tokenizer.is_fast)
        for side in (1, 3, 8, 20, 30):
            pairs = [{"input": [[(i + j + k) % 10 for j in range(side)] for i in range(side)],
                      "output": [[(i + j + k + 1) % 10 for j in range(side)] for i in range(side)]}
                     for k in range(3)]
            example = data.encode_example(tokenizer, pairs, [[7]], [[8]], context=8192, loss_mode="causal_outputs")
            # Equal-size fixtures drop earliest examples, exactly as legacy code.
            kept = pairs[len(pairs) - example["demos_used"]:]
            content, spans = data.render_prompt_spans(kept, [[7]])
            text = tokenizer.apply_chat_template([{"role": "user", "content": content}], tokenize=False,
                                                 add_generation_prompt=True, enable_thinking=False)
            offset = text.index(content)
            ranges = [(a + offset, b + offset) for a, b in spans[1:]]
            positions = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)["offset_mapping"]
            expected = [int(any(a <= x < y <= b for a, b in ranges)) for x, y in positions]
            self.assertEqual(example["loss_mask"][:len(example["prompt_ids"])], expected)
            self.assertEqual(example["loss_mask"][len(example["prompt_ids"]):], [1] * len(example["completion_ids"]))
            if side == 30:
                self.assertGreater(example["demos_dropped"], 0)

    def test_fast_offsets_exclude_first_output_inputs_and_cross_boundary_tokens(self):
        tokenizer = fast_tokenizer()
        example = data.encode_example(tokenizer, demos(), [[7]], [[8]], loss_mode="causal_outputs")
        content, spans = data.render_prompt_spans(demos(), [[7]])
        text = tokenizer.apply_chat_template([{"role": "user", "content": content}], tokenize=False)
        shift = text.index(content)
        ranges = [(a + shift, b + shift) for a, b in spans]
        offsets = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)["offset_mapping"]
        crossings = 0
        for index, (a, b) in enumerate(offsets):
            expected = int(any(left <= a < b <= right for left, right in ranges[1:]))
            self.assertEqual(example["loss_mask"][index], expected)
            if any(a < left < b for left, _ in ranges[1:]):
                crossings += 1
                self.assertEqual(example["loss_mask"][index], 0)
            if any(left <= a < b <= right for left, right in ranges[:1]):
                self.assertEqual(example["loss_mask"][index], 0)
        self.assertGreater(crossings, 0)
        self.assertEqual(example["loss_mask"][len(example["prompt_ids"]):], [1] * len(example["completion_ids"]))
        self.assertGreater(sum(example["loss_mask"]), len(example["completion_ids"]))

    def test_optional_mask_fails_closed_on_slow_changed_template_or_offsets(self):
        with self.assertRaisesRegex(ValueError, "Fast tokenizer"):
            data.encode_example(CharacterTokenizer(), demos(), [[1]], [[2]], loss_mode="causal_outputs")
        tokenizer = fast_tokenizer()
        tokenizer.chat_template = "{{ messages[0]['content'] + messages[0]['content'] }}"
        with self.assertRaisesRegex(ValueError, "exact prompt"):
            data.encode_example(tokenizer, demos(), [[1]], [[2]], loss_mode="causal_outputs")
        tokenizer = fast_tokenizer()
        with self.assertRaisesRegex(ValueError, "retained causal"):
            data.encode_example(tokenizer, [], [[1]], [[2]], loss_mode="causal_outputs")
        text, spans = data.render_prompt_spans(demos(), [[1]])
        with self.assertRaisesRegex(ValueError, "offset IDs"):
            data.causal_output_mask(tokenizer, text, text, spans, [1], [2])

    def test_context_drop_recomputes_first_retained_output(self):
        tokenizer = fast_tokenizer()
        pairs = demos()
        pairs[0] = {"input": [[1] * 20 for _ in range(20)], "output": [[2] * 20 for _ in range(20)]}
        example = data.encode_example(tokenizer, pairs, [[7]], [[8]], context=600, loss_mode="causal_outputs")
        reference = data.encode_example(tokenizer, pairs[1:], [[7]], [[8]], context=600, loss_mode="causal_outputs")
        self.assertEqual(example["demos_dropped"], 1)
        self.assertEqual(example["loss_mask"], reference["loss_mask"])
        self.assertEqual(example["prompt_ids"], reference["prompt_ids"])

    def test_actual_qwen_masked_gradients_equal_full_causal_cross_entropy(self):
        engine = fast_engine()
        example = data.encode_example(engine.tokenizer, demos(), [[7]], [[8]], loss_mode="causal_outputs")
        ids = example["prompt_ids"] + example["completion_ids"]
        mask = example["loss_mask"]
        tokens = torch.tensor([ids])
        positions = torch.tensor([i for i, value in enumerate(mask) if value])
        logits = engine.model(input_ids=tokens, use_cache=False).logits[0].float()
        reference = torch.nn.functional.cross_entropy(logits[positions - 1], tokens[0, positions])
        reference.backward()
        expected = {n: p.grad.detach().clone() for n, p in engine.model.named_parameters() if p.requires_grad}
        engine.model.zero_grad(set_to_none=True)
        masked = -engine.masked_logps(ids, mask).mean()
        masked.backward()
        self.assertAlmostEqual(reference.item(), masked.item(), places=5)
        for name, parameter in engine.model.named_parameters():
            if parameter.requires_grad:
                torch.testing.assert_close(parameter.grad, expected[name], atol=2e-6, rtol=2e-5)
        final_only = {k: v for k, v in example.items() if k not in {"loss_mask", "loss_mode"}}
        self.assertEqual(engine.nll(example), engine.nll(final_only))
        before = model.state_digest(model.adapter_state(engine.model))
        report = engine.sft_step(example, model.make_optimizer(engine.model, 1e-3))
        self.assertTrue(report["updated"])
        self.assertNotEqual(before, model.state_digest(model.adapter_state(engine.model)))
        self.assertEqual(report["supervised_tokens"], sum(mask))

    def test_mask_validation_and_precommit_deadline_cannot_update(self):
        engine = tiny_engine()
        for mask in ([1, 0, 1], [0, 0, 0], [0, .5, 1], [0, 1]):
            with self.assertRaises(ValueError):
                engine.masked_logps([1, 2, 3], mask)
        before = model.state_digest(model.adapter_state(engine.model))
        with patch.object(model, "check_deadline", side_effect=[None, model.PhaseDeadline("synthetic")]):
            with self.assertRaises(model.PhaseDeadline):
                engine.sft_step({"prompt_ids": [1, 2], "completion_ids": [3], "demos_dropped": 0},
                                model.make_optimizer(engine.model, 1e-3), deadline=1)
        self.assertEqual(before, model.state_digest(model.adapter_state(engine.model)))
        self.assertEqual(engine.optimizer_steps, 0)

    def make_resume(self, root, engine):
        engine.model.save_pretrained(root, safe_serialization=True)
        for path in root.iterdir():
            if path.name not in {"adapter_model.safetensors", "adapter_config.json"}:
                path.unlink()
        expected = model.state_digest(model.adapter_state(engine.model))
        base = {"model_source": "synthetic-tiny-qwen", "material_contract_sha256": "a" * 64}
        origin = {"run_id": "synthetic-pre-public", "source_sha256": "b" * 64, "phase": "pre_public",
                  "public_ttt_applied": False, "public_labels_used": False,
                  "run_summary_sha256": "c" * 64, "provider_record_sha256": "d" * 64}
        manifest = model.build_resume_manifest(root, expected_state_sha256=expected, base_identity=base, origin=origin)
        spec = self.seal(root, manifest)
        return base, manifest, spec

    def seal(self, root, manifest):
        body = data.canonical(manifest) + b"\n"
        (root / "manifest.json").write_bytes(body)
        return {"root": str(root), "manifest_sha256": hashlib.sha256(body).hexdigest()}

    def test_exact_cpu_resume_and_next_task_reset(self):
        source, destination = tiny_engine(), tiny_engine()
        source.sft_step({"prompt_ids": [1, 2], "completion_ids": [3, 4], "demos_dropped": 0},
                        model.make_optimizer(source.model, 1e-3))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base, manifest, spec = self.make_resume(root, source)
            report = model.load_adapter_resume(destination, spec, base_identity=base)
            self.assertEqual(report["state_sha256"], manifest["state_sha256"])
            self.assertFalse(report["optimizer_resumed"])
            self.assertEqual(model.tensor_inventory(model.adapter_state(source.model)),
                             model.tensor_inventory(model.adapter_state(destination.model)))
            selected = model.adapter_state(destination.model)
            destination.sft_step({"prompt_ids": [1, 2], "completion_ids": [3, 4], "demos_dropped": 0},
                                 model.make_optimizer(destination.model, 1e-3))
            model.restore_state(destination.model, selected)
            self.assertEqual(model.state_digest(model.adapter_state(destination.model)), manifest["state_sha256"])

    def test_resume_corruption_base_origin_inventory_and_digest_are_rejected(self):
        for change in ("file", "base", "origin", "export_keys", "shape", "dtype", "state", "trainable_hash", "extra_file", "manifest_sha"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                source, destination = tiny_engine(), tiny_engine(seed=432)
                root = Path(directory)
                base, manifest, spec = self.make_resume(root, source)
                before = model.state_digest(model.adapter_state(destination.model))
                key = next(iter(manifest["exported_tensors"]))
                if change == "file":
                    with (root / "adapter_model.safetensors").open("ab") as stream:
                        stream.write(b"bad")
                elif change == "base":
                    base = {**base, "model_source": "different-base"}
                elif change == "origin":
                    manifest["origin"]["public_ttt_applied"] = True
                elif change == "export_keys":
                    manifest["exported_tensors"].pop(key)
                elif change in {"shape", "dtype"}:
                    manifest["exported_tensors"][key][change] = [1] if change == "shape" else "torch.float16"
                elif change == "state":
                    manifest["state_sha256"] = "0" * 64
                elif change == "trainable_hash":
                    manifest["trainable_tensors"][next(iter(manifest["trainable_tensors"]))]["sha256"] = "0" * 64
                elif change == "extra_file":
                    (root / "unapproved.txt").write_text("extra")
                spec = self.seal(root, manifest)
                if change == "manifest_sha":
                    spec["manifest_sha256"] = "0" * 64
                with self.assertRaises(ValueError):
                    model.load_adapter_resume(destination, spec, base_identity=base)
                self.assertEqual(before, model.state_digest(model.adapter_state(destination.model)))

    def test_builder_rejects_unbound_selected_state_and_unknown_keys(self):
        engine = tiny_engine()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base, manifest, spec = self.make_resume(root, engine)
            with self.assertRaisesRegex(ValueError, "sealed selected state"):
                model.build_resume_manifest(root, expected_state_sha256="0" * 64, base_identity=base, origin=manifest["origin"])
            tensors = load_file(str(root / "adapter_model.safetensors"))
            tensors["arbitrary.weight"] = torch.ones(1)
            save_file(tensors, str(root / "adapter_model.safetensors"))
            with self.assertRaisesRegex(ValueError, "explicit default LoRA"):
                model.build_resume_manifest(root, expected_state_sha256=manifest["state_sha256"], base_identity=base, origin=manifest["origin"])

    def test_likelihood_sum_and_token_mean_are_actual_final_only_qwen_values(self):
        engine = tiny_engine()
        example = {"prompt_ids": [1, 2], "completion_ids": [3, 4, 5], "loss_mask": [0, 1, 1, 1, 1]}
        expected = engine.completion_logps([1, 2, 3, 4, 5], 2)[2:].detach()
        self.assertAlmostEqual(engine.candidate_log_likelihood(example, normalization="sum"), expected.sum().item())
        self.assertAlmostEqual(engine.candidate_log_likelihood(example, normalization="token_mean"), expected.mean().item())

    def test_complete_panel_likelihood_ranks_and_partial_panel_falls_back(self):
        engine = tiny_engine()
        task = {"train": demos()}
        views = data.inference_views(8, seed=1, task_id="synthetic", demo_count=3)
        candidates = [{"grid": [[1]], "votes": 5}, {"grid": [[2]], "votes": 2}, {"grid": [[3]], "votes": 1}]
        cfg = {"candidate_views": 8, "candidate_ranker": "cross_view_likelihood", "context_tokens": 128}
        observed = []
        def likelihood(example, **kwargs):
            observed.append(example["prompt_ids"])
            return [-3., -1., -2.][(len(observed) - 1) % 3]
        with patch.object(engine, "candidate_log_likelihood", side_effect=likelihood):
            order, receipt = run.rank_candidate_pool(engine, candidates, task, [[7]], views, cfg, deadline=math.inf)
        self.assertEqual(order, [1, 2, 0])
        self.assertEqual(receipt["complete_views"], 8)
        for i in range(8):
            self.assertEqual(observed[i * 3:i * 3 + 3], [observed[i * 3]] * 3)
        with patch.object(engine, "candidate_log_likelihood", side_effect=[-3., -1., -2., -9., model.PhaseDeadline("synthetic")]):
            order, receipt = run.rank_candidate_pool(engine, candidates, task, [[7]], views, cfg, deadline=math.inf)
        self.assertEqual(order, [0, 1, 2])
        self.assertEqual(receipt["used_ranker"], "vote")
        self.assertEqual(receipt["complete_views"], 1)
        self.assertEqual(len(receipt["partial_scores"]), 1)
        self.assertNotIn("aggregate_log_likelihood", receipt)

    def test_expanded_generation_inverse_dedup_votes_top_two_and_private_full_pool(self):
        engine = tiny_engine()
        task = {"train": demos(), "test": [{"input": [[7]]}]}
        views = data.inference_views(8, seed=1, task_id="synthetic", demo_count=3)
        grids = [[[1, 2]], [[2, 3]], [[3, 4]]]
        choices = [0, 1, 1, 2, 2, 2, 2, 0]
        outputs = [[{"text": data.answer_text(data.transform(grids[i], **view["transform"])),
                     "completion_tokens": 9, "stop": "completed"}] for i, view in zip(choices, views)]
        cfg = {"run_id": "synthetic", "seed": 1, "ttt_steps": 0, "context_tokens": 128, "generation_tokens": 32,
               "candidate_views": 8, "candidate_ranker": "vote"}
        with tempfile.TemporaryDirectory() as directory, patch.object(engine, "generate", side_effect=outputs):
            pools = run.solve_public(engine, {"synthetic": task}, model.adapter_state(engine.model), cfg,
                                     lambda *a, **k: None, Path(directory), deadline=math.inf)
            full = json.loads((Path(directory) / "full-candidate-pools.json").read_text())
        self.assertEqual(pools["records"][0]["tests"][0]["ranked_grids"], [grids[2], grids[0]])
        self.assertEqual([v["votes"] for v in full["records"][0]["candidates"]], [2, 2, 4])
        self.assertEqual(len(full["records"][0]["views"]), 8)

    def test_expired_expanded_run_preserves_complete_120_167_inventory(self):
        engine = tiny_engine()
        public = {f"synthetic-{i:03}": {"train": demos(), "test": [{"input": [[7]]}] * (2 if i < 47 else 1)}
                  for i in range(120)}
        cfg = {"run_id": "synthetic", "seed": 1, "ttt_steps": 8, "context_tokens": 128, "generation_tokens": 3,
               "candidate_views": 16, "candidate_ranker": "cross_view_likelihood"}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(engine, "generate", side_effect=AssertionError("expired generation")), \
             patch.object(engine, "candidate_log_likelihood", side_effect=AssertionError("expired rerank")):
            pools = run.solve_public(engine, public, model.adapter_state(engine.model), cfg,
                                     lambda *a, **k: None, Path(directory), deadline=time.time() - 1)
        self.assertEqual(len(pools["records"]), 120)
        self.assertEqual(sum(len(r["tests"]) for r in pools["records"]), 167)
        self.assertTrue(all(t["ranked_grids"] == [] for r in pools["records"] for t in r["tests"]))
        self.assertEqual(engine.forward_calls, 0)

    def test_generation_has_separate_frozen_rerank_reserve(self):
        engine = tiny_engine()
        cfg = {"seed": 1, "candidate_views": 8, "candidate_ranker": "cross_view_likelihood",
               "rerank_fraction": .25, "context_tokens": 128, "generation_tokens": 3}
        deadlines = []
        def generate(*args, **kwargs):
            deadlines.append(kwargs["deadline"])
            return [{"text": "invalid", "completion_tokens": 1, "stop": "length"}]
        with patch.object(run.time, "time", return_value=100.), patch.object(model.time, "time", return_value=100.), \
             patch.object(engine, "generate", side_effect=generate):
            result, full = run.solve_query_views(engine, {"train": demos()}, [[7]], cfg, lambda *a, **k: None,
                                                 task_id="synthetic", query_index=0, deadline=200.)
        self.assertEqual(len(deadlines), 8)
        self.assertTrue(all(d <= 175. for d in deadlines))
        self.assertEqual(full["rerank_budget_fraction"], .25)

    def test_optional_config_validation_old_defaults_and_corpus_scope(self):
        values = run.continuation_options({})
        self.assertEqual(values["candidate_views"], 2)
        self.assertEqual(values["candidate_ranker"], "first")
        self.assertEqual(values["sft_loss_mode"], "final")
        self.assertEqual(values["ttt_loss_mode"], "final")
        for values in ({"candidate_views": 4}, {"candidate_views": 16, "candidate_pool_limit": 8},
                       {"candidate_ranker": "PUBLIC_score"}, {"rerank_fraction": 0}, {"rerank_fraction": float("nan")},
                       {"likelihood_normalization": "adaptive"}, {"sft_loss_mode": "all_tokens"}):
            with self.assertRaises(ValueError):
                run.continuation_options(values)
        engine = tiny_engine()
        with self.assertRaisesRegex(ValueError, "restricted"):
            run.sft_phase(engine, {"train": {"train": demos()}}, {}, lambda *a, **k: None,
                          phase="TTT", rng=random.Random(1), deadline=math.inf, bundles_by_parent={"dev": []})

    def test_config_tensor_key_dtype_and_noncanonical_resume_tampering(self):
        for change in ("rank", "unknown_config", "missing_config", "tensor_key", "tensor_dtype", "tensor_nonfinite", "noncanonical", "symlink"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                source, destination = tiny_engine(), tiny_engine(seed=456)
                root = Path(directory)
                base, manifest, spec = self.make_resume(root, source)
                before = model.state_digest(model.adapter_state(destination.model))
                if change in {"rank", "unknown_config", "missing_config"}:
                    path = root / "adapter_config.json"
                    cfg = json.loads(path.read_bytes())
                    if change == "missing_config":
                        cfg.pop("inference_mode")
                    else:
                        cfg["r" if change == "rank" else "unknown"] = 3
                    body = data.canonical(cfg)
                    path.write_bytes(body)
                    manifest["files"][path.name] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
                elif change in {"tensor_key", "tensor_dtype", "tensor_nonfinite"}:
                    path = root / "adapter_model.safetensors"
                    tensors = load_file(str(path))
                    key = next(iter(tensors))
                    if change == "tensor_key":
                        tensors[key + ".extra"] = tensors.pop(key)
                    elif change == "tensor_dtype":
                        tensors[key] = tensors[key].half()
                    else:
                        tensors[key].fill_(float("nan"))
                    save_file(tensors, str(path))
                    body = path.read_bytes()
                    manifest["files"][path.name] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
                    manifest["exported_tensors"] = model.tensor_inventory(tensors)
                elif change == "symlink":
                    path = root / "adapter_config.json"
                    target = root.parent / (root.name + "-config.json")
                    target.write_bytes(path.read_bytes())
                    try:
                        path.unlink()
                        path.symlink_to(target)
                    except (OSError, NotImplementedError):
                        target.unlink()
                        self.skipTest("symlink creation unavailable on this platform")
                spec = self.seal(root, manifest)
                if change == "noncanonical":
                    body = json.dumps(manifest, indent=2).encode()
                    (root / "manifest.json").write_bytes(body)
                    spec["manifest_sha256"] = hashlib.sha256(body).hexdigest()
                try:
                    with self.assertRaises(ValueError):
                        model.load_adapter_resume(destination, spec, base_identity=base)
                    self.assertEqual(before, model.state_digest(model.adapter_state(destination.model)))
                finally:
                    if change == "symlink":
                        target.unlink()

    def test_resume_partial_setter_failure_rolls_back_all_adapter_bytes(self):
        engine = tiny_engine()
        with tempfile.TemporaryDirectory() as directory:
            base, manifest, spec = self.make_resume(Path(directory), engine)
            before = model.state_digest(model.adapter_state(engine.model))
            def partial(network, values):
                with torch.no_grad():
                    engine.parameters[0].add_(7)
                raise RuntimeError("synthetic partial PEFT setter failure")
            with patch("peft.set_peft_model_state_dict", side_effect=partial):
                with self.assertRaisesRegex(RuntimeError, "partial PEFT"):
                    model.load_adapter_resume(engine, spec, base_identity=base)
            self.assertEqual(before, model.state_digest(model.adapter_state(engine.model)))

    def test_physical_optimizer_attempt_survives_failed_partial_commit(self):
        engine = tiny_engine()
        before = model.adapter_state(engine.model)
        original = torch.optim.AdamW.step
        def mutate_then_fail(optimizer, *args, **kwargs):
            original(optimizer, *args, **kwargs)
            raise torch.cuda.OutOfMemoryError("synthetic partial step")
        with patch("torch.optim.AdamW.step", new=mutate_then_fail):
            with self.assertRaises(torch.cuda.OutOfMemoryError):
                engine.sft_step({"prompt_ids": [1, 2], "completion_ids": [3, 4], "demos_dropped": 0},
                                model.make_optimizer(engine.model, 1e-3))
        self.assertEqual(engine.optimizer_attempts, 1)
        self.assertEqual(engine.optimizer_steps, 0)
        model.restore_state(engine.model, before)
        self.assertEqual(model.state_digest(model.adapter_state(engine.model)), model.state_digest(before))

    def test_sft_curriculum_only_uses_uniform_parent_then_real_masked_updates(self):
        engine = fast_engine()
        tasks = {"train": {"train": demos()}}
        bundle = {"task_id": "synthetic-bundle", "train": list(reversed(demos()))}
        events = []
        cfg = {"context_tokens": 1024, "generation_tokens": 3, "sft_loss_mode": "causal_outputs"}
        report = run.sft_phase(engine, tasks, cfg, lambda event, **fields: events.append((event, fields)),
                              phase="A", rng=random.Random(0), deadline=math.inf, steps=8,
                              bundles_by_parent={"train": [bundle]})
        self.assertEqual(report["steps"], 8)
        sources = [r["source"] for e, r in events if e == "sft_step"]
        self.assertEqual(set(sources), {"original", "curriculum"})
        self.assertTrue(all(r["loss_mode"] == "causal_outputs" for e, r in events if e == "sft_step"))
        self.assertEqual(engine.optimizer_attempts, 8)
        self.assertEqual(engine.optimizer_steps, 8)

    def test_optional_execute_resumes_before_sft_and_admits_corpus_once(self):
        from tools.arc2_goal_sprint_20261017 import curriculum
        source, engine = fast_engine(), fast_engine()
        example = data.encode_example(source.tokenizer, demos(), [[7]], [[8]])
        source.sft_step(example, model.make_optimizer(source.model, 1e-3))
        training = {"train": {"train": demos()}}
        dev = {"dev": {"train": demos()}}
        public = {"public": {"train": demos(), "test": [{"input": [[7]]}]}}
        bundles = {"train": [{"task_id": "synthetic-bundle", "train": list(reversed(demos()))}]}
        reward_calls = []
        def reward(prediction, target):
            reward_calls.append(1)
            value = float(len(reward_calls) % 2)
            return {"reward": value, "exact": value, "pixel": value}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = root / "adapter"
            adapter.mkdir()
            base, manifest, spec = self.make_resume(adapter, source)
            cfg = {"output_dir": str(root / "output"), "run_id": "synthetic-optional-execute",
                   "session_deadline_epoch": time.time() + 40000, "training_root": "synthetic-unused",
                   "training_manifest_path": "synthetic-unused", "public_path": "synthetic-unused",
                   "model_path": "synthetic-unused", "sft_steps": 2, "rl_batches": 1,
                   "rl_parents_per_batch": 1, "rl_group_size": 2, "ttt_steps": 1,
                   "context_tokens": 1024, "generation_tokens": 3, "dev_tasks": 1,
                   "sft_loss_mode": "causal_outputs", "ttt_loss_mode": "causal_outputs",
                   "candidate_views": 8, "candidate_ranker": "vote", "model_base_identity": base,
                   "adapter_resume": spec, "curriculum": {"root": "synthetic-corpus", "manifest_sha256": "e" * 64}}
            admitted = object()
            with patch.object(run, "load_data", return_value=(training, dev, public, {"fixture_only": True})), \
                 patch.object(curriculum.Admission, "from_load_data", return_value=admitted) as admission, \
                 patch.object(curriculum, "load_curriculum", return_value=(bundles, {"manifest_sha256": "e" * 64})) as load, \
                 patch.object(run.Engine, "load", return_value=engine), \
                 patch.object(run, "admit_resource", return_value={"gpu": "SYNTHETIC-CPU", "gpu_bytes": 0}), \
                 patch.object(run, "reward_components", side_effect=reward), \
                 patch("torch.cuda.get_device_name", return_value="SYNTHETIC-CPU"), \
                 patch("torch.cuda.get_device_properties", return_value=type("DeviceFixture", (), {"total_memory": 0})()), \
                 patch("builtins.print"):
                run.execute(cfg)
            admission.assert_called_once_with(training, dev, public, {"fixture_only": True})
            load.assert_called_once_with("synthetic-corpus", admission=admitted,
                                         expected_manifest_sha256="e" * 64, expected_producer_hashes=None)
            summary = json.loads((root / "output/run-summary.json").read_bytes())
            events = [json.loads(line) for line in (root / "output/audit.jsonl").read_text().splitlines()]
            names = [r["event"] for r in events]
            self.assertLess(names.index("adapter_resume_verified"), names.index("sft_step"))
            self.assertEqual(summary["adapter_resume"]["state_sha256"], manifest["state_sha256"])
            self.assertEqual(summary["A"]["steps"], 2)
            self.assertEqual(summary["B"]["commits"], 1)
            self.assertEqual(summary["public_queries"], 1)
            self.assertEqual(summary["physical_optimizer_attempts"], engine.optimizer_attempts)
            self.assertTrue(any(r["event"] == "ttt_step" and r["loss_mode"] == "causal_outputs" for r in events))
            self.assertTrue(all(r["phase"] in {"A", "C"} for r in events if r["event"] == "sft_step"))
            self.assertFalse(summary["public_labels_used"])
            self.assertIsNone(summary["score"])


if __name__ == "__main__":
    unittest.main()
