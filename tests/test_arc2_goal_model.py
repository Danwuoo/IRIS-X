"""Synthetic CPU integration checks, not ARC scores or full-model GPU evidence.

The real Qwen3, PEFT LoRA, autograd, cached sampling and upstream DDIS run here.
Optional ML dependencies are deliberately absent from the baseline repository CI.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import tempfile
import time
import unittest
from unittest.mock import patch

from tools.arc2_goal_sprint_20261017 import data

_OPTIONAL = ("torch", "transformers", "peft", "pydantic")
_MISSING = [name for name in _OPTIONAL if importlib.util.find_spec(name) is None]
if not _MISSING:
    import torch
    from transformers import Qwen3Config, Qwen3ForCausalLM
    from peft import LoraConfig, get_peft_model
    from tools.arc2_goal_sprint_20261017.af3 import AF3Trajectory, compute_group_loss
    from tools.arc2_goal_sprint_20261017.model import (
        Engine, PhaseDeadline, adapter_state, make_optimizer, restore_state, state_digest,
    )
    from tools.arc2_goal_sprint_20261017 import run


class CharacterTokenizer:
    """Deterministic local fixture for context accounting, not a model tokenizer."""
    eos_token_id = 0

    def encode(self, text, **kwargs):
        return [ord(char) for char in text]

    def decode(self, ids, **kwargs):
        return "".join(chr(value) for value in ids)

    def apply_chat_template(self, messages, **kwargs):
        return "USER\n" + messages[0]["content"] + "\nASSISTANT\n"


class TinyTokenizer:
    """No retokenization equivalence: raw model IDs remain authoritative."""
    eos_token_id = None

    def encode(self, text, **kwargs):
        return [] if text == "</grid>" else [2, 3, 4]

    def decode(self, ids, **kwargs):
        return "decoded-not-round-trippable"

    def apply_chat_template(self, messages, **kwargs):
        return messages[0]["content"]


def tiny_engine(seed=123):
    torch.manual_seed(seed)
    config = Qwen3Config(vocab_size=32, hidden_size=32, intermediate_size=64,
                        num_hidden_layers=2, num_attention_heads=2,
                        num_key_value_heads=1, head_dim=16, attention_dropout=0.0)
    config._attn_implementation = "sdpa"
    model = get_peft_model(Qwen3ForCausalLM(config), LoraConfig(
        r=2, lora_alpha=4, lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    ))
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    return Engine(model, TinyTokenizer(), device="cpu")


class DataContractTests(unittest.TestCase):
    def test_all_dihedral_color_inverses_on_rectangular_grid(self):
        grid = [[0, 1, 2], [3, 4, 5]]
        original = copy.deepcopy(grid)
        colors = [9, 4, 7, 0, 8, 2, 1, 5, 3, 6]
        variants = set()
        for rotation in range(4):
            for transpose in (False, True):
                spec = dict(rotation=rotation, transpose=transpose, colors=colors)
                result = data.transform(grid, **spec)
                variants.add(data.canonical(result))
                self.assertEqual(data.transform(result, **spec, inverse=True), original)
        self.assertEqual(len(variants), 8)
        self.assertEqual(grid, original)
        with self.assertRaises(ValueError):
            data.transform(grid, colors=[0] * 10)

    def test_parser_requires_bounded_complete_rectangular_digits(self):
        for text in ("<grid>\n1 2\n3 4\n</grid>", "[[1,2],[3,4]]", "12\n34"):
            self.assertEqual(data.parse_grid(text), [[1, 2], [3, 4]])
        for text in ("", "<grid>1 2", "1,2", "1\n2 3", "-1", "1.0", "[[true]]",
                     "<grid>" + "1 " * 31 + "</grid>", "\n".join(["1"] * 31)):
            with self.subTest(text=text):
                self.assertIsNone(data.parse_grid(text))
        self.assertFalse(data.valid_grid([[True]]))
        self.assertEqual(data.parse_grid("explanation <grid>1</grid> then <grid>2</grid>"), [[2]])

    def test_context_drops_whole_largest_demo_not_query_target(self):
        tokenizer = CharacterTokenizer()
        small = {"input": [[1]], "output": [[2]]}
        large = {"input": [[1] * 8] * 5, "output": [[2] * 8] * 5}
        query, target = [[8, 9]], [[9, 8]]
        one = data.encode_example(tokenizer, [small], query, target, context=10000)
        budget = len(one["prompt_ids"]) + len(one["completion_ids"])
        result = data.encode_example(tokenizer, [large, small], query, target, context=budget)
        self.assertEqual(result["demos_used"], 1)
        self.assertEqual(result["demos_dropped"], 1)
        self.assertEqual(result["prompt_ids"], one["prompt_ids"])
        self.assertEqual(result["completion_ids"], tokenizer.encode(data.answer_text(target)) + [0])
        inference = data.encode_example(tokenizer, [small], query, context=10000, generation=17)
        exact = len(inference["prompt_ids"]) + 17
        self.assertEqual(data.encode_example(tokenizer, [small], query, context=exact,
                                            generation=17)["demos_used"], 1)
        with self.assertRaisesRegex(ValueError, "truncation forbidden"):
            data.encode_example(tokenizer, [], query, target, context=1)

    def test_loo_never_accesses_original_test_fields(self):
        pairs = [{"input": [[i]], "output": [[i + 1]]} for i in range(3)]
        task = {"train": pairs, "test": object()}
        demos, query, target = data.loo_example(task, random.Random(0), augment=False, held_index=1)
        self.assertEqual(demos, [pairs[0], pairs[2]])
        self.assertEqual(query, pairs[1]["input"])
        self.assertEqual(target, pairs[1]["output"])

    def test_training_inventory_is_pinned_and_known_overlap_is_excluded(self):
        # All values are artificial. Exactly 1,000 files exercise admission, not research claims.
        def pair(seed):
            rng = random.Random(seed)
            return {"input": [[rng.randrange(10) for _ in range(4)] for _ in range(3)],
                    "output": [[rng.randrange(10) for _ in range(4)] for _ in range(3)]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            training_root = root / "training"
            training_root.mkdir()
            public = {f"p{i:03}": {"train": [pair(10000 + i)],
                      "test": [{"input": [[0, 1]]} for _ in range(2 if i < 47 else 1)]} for i in range(120)}
            pairs = [pair(i) for i in range(1000)]
            pairs[0] = public["p000"]["train"][0]
            pairs[1] = {k: data.transform(v, **data.SECOND_VIEW) for k, v in pairs[2].items()}
            manifest = {"protected_ids": ["t0003"], "files": {},
                        "upstream": {"fixed_splits": {"train": [], "dev": ["t0002"]}}}
            for i, item in enumerate(pairs):
                name = f"t{i:04}.json"
                raw = data.canonical({"train": [item], "test": "FORBIDDEN-TRAINING-TEST-SENTINEL"})
                (training_root / name).write_bytes(raw)
                manifest["files"]["data/training/" + name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                if i != 2:
                    manifest["upstream"]["fixed_splits"]["train"].append(name[:-5])
            manifest_path, public_path = root / "manifest.json", root / "public.json"
            manifest_path.write_bytes(data.canonical(manifest))
            public_path.write_bytes(data.canonical(public))
            train, dev, admitted, receipt = data.load_data(training_root, manifest_path, public_path)
            self.assertEqual(set(dev), {"t0001", "t0002"})
            self.assertEqual(len(train), 996)
            self.assertEqual(set(receipt["excluded_task_ids"]), {"t0000", "t0003"})
            self.assertFalse(receipt["training_test_fields_used"])
            self.assertTrue(all(set(task) == {"train"} for task in list(train.values()) + list(dev.values())))
            self.assertEqual(len(admitted), 120)
            self.assertEqual(sum(len(t["test"]) for t in admitted.values()), 167)
            public["p000"]["test"][0]["output"] = [[1]]
            public_path.write_bytes(data.canonical(public))
            with self.assertRaisesRegex(ValueError, "answers forbidden"):
                data.load_data(training_root, manifest_path, public_path)
            public["p000"]["test"][0].pop("output")
            public_path.write_bytes(data.canonical(public))
            with (training_root / "t0004.json").open("ab") as stream:
                stream.write(b" ")
            with self.assertRaisesRegex(ValueError, "source digest differs"):
                data.load_data(training_root, manifest_path, public_path)


@unittest.skipIf(bool(_MISSING), "Optional model integration dependencies missing: " + ", ".join(_MISSING))
class TinyModelIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def setUp(self):
        self.engine = tiny_engine()

    def rows(self, *, count=6):
        rows = self.engine.generate([1, 2, 3], count=count, max_new_tokens=5, sample=True)
        for index, row in enumerate(rows):
            row.update(sample_id=f"s{index}", group_id=f"g{index // 2}",
                       reward=(1.0 if index < 4 and index % 2 == 0 else 0.0))
        return rows

    def test_engine_load_local_bfloat16_base_and_float32_lora(self):
        from transformers import PreTrainedTokenizerFast
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        config = Qwen3Config(vocab_size=32, hidden_size=32, intermediate_size=64,
                            num_hidden_layers=1, num_attention_heads=2,
                            num_key_value_heads=1, head_dim=16, attention_dropout=0.0)
        with tempfile.TemporaryDirectory() as directory:
            Qwen3ForCausalLM(config).save_pretrained(directory)
            vocabulary = {"[UNK]": 0, **{f"t{i}": i for i in range(1, 32)}}
            backend = Tokenizer(WordLevel(vocabulary, unk_token="[UNK]"))
            backend.pre_tokenizer = Whitespace()
            tokenizer = PreTrainedTokenizerFast(tokenizer_object=backend, unk_token="[UNK]")
            tokenizer.save_pretrained(directory)
            engine = Engine.load(directory, rank=2, alpha=4, device="cpu")
            self.assertTrue(all(p.dtype == torch.float32 for p in engine.parameters))
            self.assertTrue(all(p.dtype == torch.bfloat16 for p in engine.model.parameters() if not p.requires_grad))
            self.assertTrue(engine.model.is_gradient_checkpointing)
            rows = engine.generate([1, 2, 3], count=2, max_new_tokens=4, sample=True)
            for row in rows:
                replay = engine.completion_logps(row["input_ids"], 3)
                self.assertTrue(torch.isfinite(replay).all())
                # CPU BF16 cached/full-kernel differences need not be FP32-exact.
                self.assertLess((replay.detach() - torch.tensor(row["behavior_log_probs"])).abs().max().item(), 0.05)
            report = engine.sft_step({"prompt_ids": [1, 2, 3], "completion_ids": [4, 5],
                                      "demos_dropped": 0}, make_optimizer(engine.model, 1e-3))
            self.assertTrue(report["updated"])

    def test_cached_sampling_replay_raw_ids_full_vocabulary(self):
        original = torch.multinomial
        captured = []
        def draw(probs, count):
            captured.append(probs.detach().clone())
            return original(probs, count)
        with patch("torch.multinomial", side_effect=draw):
            rows = self.rows(count=4)
        self.assertEqual(len(captured), 5)
        for probabilities in captured:
            self.assertEqual(tuple(probabilities.shape), (4, 32))
            self.assertTrue((probabilities > 0).all())
            torch.testing.assert_close(probabilities.sum(-1), torch.ones(4))
        for row in rows:
            replay = self.engine.completion_logps(row["input_ids"], row["prompt_length"])
            torch.testing.assert_close(replay.detach(), torch.tensor(row["behavior_log_probs"]), atol=1e-6, rtol=1e-6)
            self.assertNotEqual(self.engine.tokenizer.encode(row["text"]), row["input_ids"][3:])
            ids = torch.tensor([row["input_ids"]])
            with torch.no_grad():
                raw_logits = self.engine.model(input_ids=ids, use_cache=False).logits[0].float()
            expected = raw_logits[2:-1].log_softmax(-1).gather(1, ids[0, 3:, None]).squeeze(1)
            torch.testing.assert_close(replay[3:].detach(), expected, atol=1e-6, rtol=1e-6)

    def test_batched_eos_and_close_tag_keep_no_filler_tokens(self):
        self.engine.tokenizer.eos_token_id = 0
        self.engine.tokenizer.encode = lambda text, **kwargs: [30, 31]
        self.engine.model.generation_config.eos_token_id = [0, 29]
        draws = [torch.tensor([[0], [30], [4]]), torch.tensor([[6], [31], [5]]),
                 torch.tensor([[6], [7], [29]])]
        with patch("torch.multinomial", side_effect=draws):
            rows = self.engine.generate([1, 2, 3], count=3, max_new_tokens=8, sample=True)
        self.assertEqual([r["completion_tokens"] for r in rows], [1, 2, 3])
        self.assertEqual([r["input_ids"][3:] for r in rows], [[0], [30, 31], [4, 5, 29]])
        self.assertTrue(all(r["stop"] == "completed" for r in rows))
        self.assertEqual(self.engine.sampled_tokens, 6)
        for row in rows:
            replay = self.engine.completion_logps(row["input_ids"], 3)
            torch.testing.assert_close(replay.detach(), torch.tensor(row["behavior_log_probs"]), atol=1e-6, rtol=1e-6)

    def test_streamed_gradients_equal_actual_group_adapter_with_unequal_lengths(self):
        rows = self.rows()
        rows[0]["input_ids"] = rows[0]["input_ids"][:4]
        rows[0]["behavior_log_probs"] = rows[0]["behavior_log_probs"][:4]
        rows[0]["completion_tokens"] = 1
        trajectories = []
        for row in rows:
            trajectories.append(AF3Trajectory(row["sample_id"], row["group_id"], row["input_ids"],
                self.engine.completion_logps(row["input_ids"], 3), torch.tensor(row["behavior_log_probs"]),
                torch.tensor([0] * 3 + [1] * row["completion_tokens"]), row["reward"]))
        result = compute_group_loss(trajectories)
        result.loss.backward()
        expected = {n: p.grad.detach().clone() for n, p in self.engine.model.named_parameters() if p.requires_grad}
        reference_loss = result.loss.item()
        captured = {}
        def capture(optimizer):
            captured.update({n: p.grad.detach().clone() for n, p in self.engine.model.named_parameters() if p.requires_grad})
            optimizer.zero_grad(set_to_none=True)
            return {"updated": False, "gradient_norm": 0.0}
        before = state_digest(adapter_state(self.engine.model))
        with patch.object(self.engine, "commit", side_effect=capture):
            report = self.engine.af3_update(rows, make_optimizer(self.engine.model, 1e-3),
                        expected_groups=["g0", "g1", "g2"], group_size=2)
        self.assertEqual(report["replayed"], 4)
        self.assertEqual(report["mixed_groups"], 2)
        self.assertEqual(report["physical_trajectories"], 6)
        self.assertAlmostEqual(report["loss"], reference_loss, places=6)
        self.assertGreater(sum(p.square().sum().item() for p in expected.values()), 0)
        self.assertEqual(set(expected), set(captured))
        for name in expected:
            torch.testing.assert_close(captured[name], expected[name], atol=2e-7, rtol=2e-5)
        self.assertEqual(before, state_digest(adapter_state(self.engine.model)))

    def test_real_af3_updates_and_zero_signal_preserves_state(self):
        rows = self.rows(count=4)
        optimizer = make_optimizer(self.engine.model, 1e-3)
        before = state_digest(adapter_state(self.engine.model))
        report = self.engine.af3_update(rows, optimizer, expected_groups=["g0", "g1"], group_size=2)
        self.assertTrue(report["updated"])
        self.assertEqual(report["probability_measure"], "full-vocabulary-temperature-one")
        self.assertLess(report["max_replay_logp_gap"], 1e-5)
        self.assertNotEqual(before, state_digest(adapter_state(self.engine.model)))
        after = state_digest(adapter_state(self.engine.model))
        for row in rows:
            row["reward"] = 1.0
        report = self.engine.af3_update(rows, optimizer, expected_groups=["g0", "g1"], group_size=2)
        self.assertFalse(report["updated"])
        self.assertEqual(report["reason"], "zero_reward_signal")
        self.assertEqual(after, state_digest(adapter_state(self.engine.model)))

    def test_complete_groups_and_duplicate_trajectories_rejected(self):
        rows = self.rows(count=4)
        optimizer = make_optimizer(self.engine.model, 1e-3)
        before = state_digest(adapter_state(self.engine.model))
        for broken in (rows[:-1], [rows[0], rows[0], *rows[2:]]):
            with self.assertRaises(ValueError):
                self.engine.af3_update(broken, optimizer, expected_groups=["g0", "g1"], group_size=2)
        self.assertEqual(before, state_digest(adapter_state(self.engine.model)))

    def test_sft_updates_only_adapter_reduces_nll_and_restores_exactly(self):
        example = {"prompt_ids": [1, 2, 3], "completion_ids": [4, 5, 6], "demos_dropped": 0}
        before = adapter_state(self.engine.model)
        frozen = {n: p.detach().clone() for n, p in self.engine.model.named_parameters() if not p.requires_grad}
        loss_before = self.engine.nll(example)
        optimizer = make_optimizer(self.engine.model, 1e-2)
        for _ in range(6):
            self.assertTrue(self.engine.sft_step(example, optimizer)["updated"])
        self.assertLess(self.engine.nll(example), loss_before)
        self.assertNotEqual(state_digest(before), state_digest(adapter_state(self.engine.model)))
        for name, parameter in self.engine.model.named_parameters():
            if name in frozen:
                torch.testing.assert_close(parameter.detach(), frozen[name], atol=0, rtol=0)
        restore_state(self.engine.model, before)
        self.assertEqual(state_digest(before), state_digest(adapter_state(self.engine.model)))
        with self.assertRaises(ValueError):
            restore_state(self.engine.model, {})

    def test_sft_partial_optimizer_oom_and_nonfinite_are_rolled_back_before_retry(self):
        for failure in ("oom", "nonfinite"):
            with self.subTest(failure=failure):
                engine = tiny_engine()
                initial = state_digest(adapter_state(engine.model))
                observations, events = [], []
                original_step = torch.optim.AdamW.step
                def inject(optimizer, *args, **kwargs):
                    observations.append((state_digest(adapter_state(engine.model)), len(optimizer.state)))
                    result = original_step(optimizer, *args, **kwargs)
                    if len(observations) == 1:
                        if failure == "oom":
                            raise torch.cuda.OutOfMemoryError("synthetic partial optimizer mutation")
                        with torch.no_grad():
                            engine.parameters[0].fill_(float("nan"))
                    return result
                cfg = {"context_tokens": 8192, "generation_tokens": 3}
                tasks = {"synthetic": {"train": [{"input": [[1]], "output": [[2]]}]}}
                with patch("torch.optim.AdamW.step", new=inject):
                    report = run.sft_phase(engine, tasks, cfg,
                        lambda event, **fields: events.append((event, fields)),
                        phase="A", rng=random.Random(0), deadline=math.inf, steps=1)
                self.assertEqual(report["attempts"], 2)
                self.assertEqual(report["steps"], 1)
                self.assertEqual(report["failures"], 1)
                self.assertEqual(observations, [(initial, 0), (initial, 0)])
                self.assertEqual(engine.optimizer_steps, 1)
                self.assertNotEqual(initial, state_digest(adapter_state(engine.model)))
                self.assertEqual(cfg["context_tokens"], 7168 if failure == "oom" else 8192)
                aborts = [fields for event, fields in events if event == "sft_step_aborted"]
                self.assertEqual(len(aborts), 1)
                self.assertFalse(aborts[0]["committed"])
                self.assertTrue(aborts[0]["adapter_restored"])
                self.assertTrue(aborts[0]["optimizer_reset"])

    def test_missing_nonfinite_and_zero_gradients_never_step(self):
        optimizer = make_optimizer(self.engine.model, 1e-3)
        initial = state_digest(adapter_state(self.engine.model))
        with self.assertRaises(FloatingPointError):
            self.engine.commit(optimizer)
        for parameter in self.engine.parameters:
            parameter.grad = torch.zeros_like(parameter)
        self.assertFalse(self.engine.commit(optimizer)["updated"])
        self.engine.parameters[0].grad = torch.full_like(self.engine.parameters[0], float("nan"))
        with self.assertRaises(FloatingPointError):
            self.engine.commit(optimizer)
        self.assertEqual(initial, state_digest(adapter_state(self.engine.model)))
        self.assertEqual(self.engine.optimizer_steps, 0)
        self.assertTrue(all(p.grad is None for p in self.engine.parameters))

    def test_deadline_before_generation_and_mid_replay_never_commits(self):
        with self.assertRaises(PhaseDeadline):
            self.engine.generate([1], deadline=time.time() - 1)
        self.assertEqual(self.engine.forward_calls, 0)
        rows = self.rows(count=4)
        optimizer = make_optimizer(self.engine.model, 1e-3)
        before = state_digest(adapter_state(self.engine.model))
        with patch("tools.arc2_goal_sprint_20261017.model.check_deadline",
                   side_effect=[None, PhaseDeadline("synthetic deadline")]):
            with self.assertRaises(PhaseDeadline):
                self.engine.af3_update(rows, optimizer, expected_groups=["g0", "g1"], group_size=2)
        self.assertEqual(before, state_digest(adapter_state(self.engine.model)))
        self.assertEqual(self.engine.optimizer_steps, 0)
        self.assertTrue(all(p.grad is None for p in self.engine.parameters))

    def test_rl_phase_restores_nonfinite_after_optimizer_step(self):
        before = adapter_state(self.engine.model)
        tasks = {"synthetic": {"train": [{"input": [[1]], "output": [[2]]},
                                          {"input": [[2]], "output": [[3]]}]}}
        rows = self.engine.generate([1, 2, 3], count=2, max_new_tokens=3, sample=True)
        rows[0]["text"], rows[1]["text"] = "<grid>1</grid>", "invalid"
        audit_rows = []
        original_step = torch.optim.AdamW.step
        def poison(optimizer, *args, **kwargs):
            original_step(optimizer, *args, **kwargs)
            with torch.no_grad():
                self.engine.parameters[0].fill_(float("nan"))
        cfg = {"rl_batches": 1, "rl_parents_per_batch": 1, "rl_group_size": 2,
               "context_tokens": 128, "generation_tokens": 3}
        with patch.object(self.engine, "generate", return_value=rows), \
             patch.object(run, "loo_example", return_value=([], [[1]], [[1]])), \
             patch("torch.optim.AdamW.step", new=poison):
            report = run.rl_phase(self.engine, tasks, cfg,
                lambda event, **fields: audit_rows.append((event, fields)), rng=random.Random(0), deadline=math.inf)
        self.assertEqual(report["commits"], 0)
        self.assertEqual(report["complete_batches"], 0)
        self.assertEqual(state_digest(before), state_digest(adapter_state(self.engine.model)))
        self.assertTrue(any(event == "af3_batch_aborted" and fields["failure"] == "FloatingPointError"
                            for event, fields in audit_rows))

    def test_select_arm_uses_fixed_dev_only_panel_and_restores_winner(self):
        state = adapter_state(self.engine.model)
        names = list(state)
        states = {}
        for arm, value in (("A", 1.0), ("B", 2.0), ("C", 3.0)):
            states[arm] = {name: tensor.clone() for name, tensor in state.items()}
            states[arm][names[0]].fill_(value)
        seen = []
        def nll(example):
            value = float(adapter_state(self.engine.model)[names[0]].flatten()[0])
            seen.append((value, copy.deepcopy(example)))
            return {1.0: 2.0, 2.0: 1.0, 3.0: 3.0}[value]
        dev = {f"dev{i}": {"train": [{"input": [[1]], "output": [[2]]},
                                      {"input": [[2]], "output": [[3]]}]} for i in range(5)}
        cfg = {"seed": 1, "dev_tasks": 3, "context_tokens": 128, "generation_tokens": 3}
        with patch.object(self.engine, "nll", side_effect=nll):
            winner, scores = run.select_arm(self.engine, states, dev, cfg, lambda *a, **k: None, math.inf)
        self.assertEqual(winner, "B")
        self.assertEqual(scores, {"A": 2.0, "B": 1.0, "C": 3.0})
        self.assertEqual(len(seen), 9)
        self.assertEqual([x[1] for x in seen[:3]], [x[1] for x in seen[3:6]])
        self.assertEqual(state_digest(adapter_state(self.engine.model)), state_digest(states["B"]))

    def test_dev_deadline_falls_back_to_predeclared_a_not_partial_winner(self):
        state = adapter_state(self.engine.model)
        name = next(iter(state))
        states = {arm: {key: value.clone() for key, value in state.items()} for arm in ("A", "B", "C")}
        for index, arm in enumerate(states):
            states[arm][name].fill_(index + 1)
        dev = {"synthetic-dev": {"train": [{"input": [[1]], "output": [[2]]}]}}
        cfg = {"seed": 1, "dev_tasks": 1, "context_tokens": 128, "generation_tokens": 3}
        events = []
        with patch.object(self.engine, "nll", side_effect=[3.0, 1.0]), \
             patch.object(run, "check_deadline", side_effect=[None, None, PhaseDeadline("synthetic")]):
            selected, scores = run.select_arm(self.engine, states, dev, cfg,
                lambda event, **fields: events.append((event, fields)), math.inf)
        self.assertEqual(selected, "A")
        self.assertEqual(scores, {"A": 3.0, "B": 1.0})
        self.assertEqual(state_digest(adapter_state(self.engine.model)), state_digest(states["A"]))
        self.assertTrue(any(event == "dev_incomplete_fallback" for event, _ in events))

    def test_ttt_failure_rolls_back_and_later_task_starts_from_selected(self):
        selected = adapter_state(self.engine.model)
        public = {f"synthetic-{i}": {"train": [{"input": [[1]], "output": [[2]]}],
                                   "test": [{"input": [[3]]}]} for i in range(2)}
        cfg = {"run_id": "synthetic-rollback", "seed": 1, "ttt_steps": 1,
               "context_tokens": 128, "generation_tokens": 3}
        events, observed_states = [], []
        original_step = torch.optim.AdamW.step
        def poison(optimizer, *args, **kwargs):
            original_step(optimizer, *args, **kwargs)
            with torch.no_grad():
                self.engine.parameters[0].fill_(float("nan"))
        def generate(*args, **kwargs):
            observed_states.append(state_digest(adapter_state(self.engine.model)))
            return [{"text": "invalid", "completion_tokens": 1, "stop": "length"}]
        with tempfile.TemporaryDirectory() as directory, \
             patch("torch.optim.AdamW.step", new=poison), \
             patch.object(self.engine, "generate", side_effect=generate):
            pools = run.solve_public(self.engine, public, selected, cfg,
                lambda event, **fields: events.append((event, fields)), Path(directory), deadline=math.inf)
        self.assertEqual(observed_states, [state_digest(selected)] * 4)
        self.assertEqual(sum(event == "ttt_rollback" for event, _ in events), 2)
        self.assertEqual(len(pools["records"]), 2)
        self.assertEqual(state_digest(adapter_state(self.engine.model)), state_digest(selected))

    def test_expired_public_deadline_preserves_every_query_with_no_generation(self):
        from tools.arc_offline_evaluation import validate_pools
        public = {"synthetic": {"train": [{"input": [[1]], "output": [[2]]}],
                                "test": [{"input": [[3]]}, {"input": [[4]]}]}}
        cfg = {"run_id": "synthetic-deadline", "seed": 1, "ttt_steps": 1,
               "context_tokens": 128, "generation_tokens": 3}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(self.engine, "generate", side_effect=AssertionError("must not generate")):
            pools = run.solve_public(self.engine, public, adapter_state(self.engine.model), cfg,
                                    lambda *a, **k: None, Path(directory), deadline=time.time() - 1)
        records = validate_pools(public, pools)
        self.assertEqual(len(records["synthetic"]["tests"]), 2)
        for query in records["synthetic"]["tests"]:
            self.assertEqual(query["ranked_grids"], [])
            self.assertEqual(query["status"], "failed")
        self.assertEqual(self.engine.forward_calls, 0)

    def test_resource_admission_checks_actual_device_before_model_load(self):
        with patch("torch.cuda.is_available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "allocation missing"):
                run.admit_resource()
        for memory, accepted in ((16 * 1024**3, False), (96 * 1024**3, True)):
            with patch("torch.cuda.is_available", return_value=True), \
                 patch("torch.cuda.get_device_name", return_value="synthetic-allocation"), \
                 patch("torch.cuda.get_device_properties", return_value=type("DeviceFixture", (), {"total_memory": memory})()):
                if accepted:
                    self.assertEqual(run.admit_resource()["gpu_bytes"], memory)
                else:
                    with self.assertRaisesRegex(RuntimeError, "allocation mismatch"):
                        run.admit_resource()

    def test_execute_all_phases_real_model_and_exact_export_reload(self):
        # A fully synthetic lifecycle. Fake device metadata is explicit; all actual
        # model forwards/backwards, adapter serialization and reload are on CPU.
        training = {"synthetic-train": {"train": [{"input": [[1]], "output": [[2]]},
                                                  {"input": [[2]], "output": [[3]]}]}}
        dev = {"synthetic-dev": copy.deepcopy(training["synthetic-train"])}
        public = {"synthetic-public": {**copy.deepcopy(training["synthetic-train"]),
                                      "test": [{"input": [[4]]}, {"input": [[5]]}]}}
        counter = []
        def synthetic_reward(prediction, target):
            counter.append(1)
            value = float(len(counter) % 2)
            return {"reward": value, "exact": value, "pixel": value}
        self.engine.tokenizer.save_pretrained = lambda path: (Path(path) / "synthetic-tokenizer.txt").write_text("synthetic")
        with tempfile.TemporaryDirectory() as directory:
            cfg = {"output_dir": directory, "run_id": "synthetic-execute-only",
                   "session_deadline_epoch": time.time() + 40000, "training_root": "unused-fixture",
                   "training_manifest_path": "unused-fixture", "public_path": "unused-fixture",
                   "model_path": "unused-tiny-model", "sft_steps": 2, "rl_batches": 1,
                   "rl_parents_per_batch": 1, "rl_group_size": 2, "ttt_steps": 1,
                   "context_tokens": 128, "generation_tokens": 3, "dev_tasks": 1}
            with patch.object(run, "load_data", return_value=(training, dev, public, {"fixture_only": True})), \
                 patch.object(run.Engine, "load", return_value=self.engine), \
                 patch.object(run, "admit_resource", return_value={"gpu": "CPU-SYNTHETIC-NOT-GPU", "gpu_bytes": 0}), \
                 patch.object(run, "reward_components", side_effect=synthetic_reward), \
                 patch("torch.cuda.get_device_name", return_value="CPU-SYNTHETIC-METADATA-NOT-GPU"), \
                 patch("torch.cuda.get_device_properties", return_value=type("DeviceFixture", (), {"total_memory": 0})()), \
                 patch("builtins.print"):
                run.execute(cfg)
            root = Path(directory)
            summary = json.loads((root / "run-summary.json").read_text())
            selection = json.loads((root / "selection.json").read_text())
            audit = [json.loads(line) for line in (root / "audit.jsonl").read_text().splitlines()]
            self.assertEqual(summary["solver_status"], "complete")
            self.assertEqual(summary["public_tasks"], 1)
            self.assertEqual(summary["public_queries"], 2)
            self.assertEqual(summary["A"]["steps"], 2)
            self.assertEqual(summary["B"]["commits"], 1)
            self.assertIsNone(summary["score"])
            self.assertFalse(selection["public_labels_used"])
            self.assertTrue((root / "selected-adapter/adapter_model.safetensors").is_file())
            self.assertTrue(any(row["event"] == "checkpoint_reload_verified" for row in audit))
            self.assertGreater(summary["optimizer_steps"], 3)

    def test_public_multitest_inverse_candidates_and_original_scorer_schema(self):
        # Interface-only fixture: no evaluator answers are loaded or evaluated.
        from tools.arc_offline_evaluation import validate_pools
        public = {"synthetic-a": {"train": [{"input": [[1]], "output": [[2]]}],
                                  "test": [{"input": [[3]]}, {"input": [[4, 5]]}]},
                  "synthetic-b": {"train": [{"input": [[5]], "output": [[6]]}],
                                  "test": [{"input": [[7]]}]}}
        selected = adapter_state(self.engine.model)
        output_grid = [[1, 2], [3, 4], [5, 6]]
        observed_states = []
        generated = []
        for _ in range(3):
            for spec in (data.IDENTITY, data.SECOND_VIEW):
                generated.append([{"text": data.answer_text(data.transform(output_grid, **spec)),
                                   "completion_tokens": 20, "stop": "completed"}])
        def generate(*args, **kwargs):
            observed_states.append(state_digest(adapter_state(self.engine.model)))
            return generated.pop(0)
        cfg = {"run_id": "synthetic-interface-only", "seed": 1, "ttt_steps": 0,
               "context_tokens": 128, "generation_tokens": 32}
        with tempfile.TemporaryDirectory() as directory, patch.object(self.engine, "generate", side_effect=generate):
            pools = run.solve_public(self.engine, public, selected, cfg, lambda *a, **k: None,
                                     Path(directory), deadline=math.inf)
            records = validate_pools(public, pools)
            self.assertEqual(json.loads((Path(directory) / "pools.json").read_text()), pools)
        self.assertEqual(set(records), set(public))
        self.assertEqual(sum(len(row["tests"]) for row in records.values()), 3)
        self.assertEqual(observed_states, [state_digest(selected)] * 6)
        for record in records.values():
            for test in record["tests"]:
                self.assertEqual(test["ranked_grids"], [output_grid])
                self.assertEqual(test["status"], "complete")


if __name__ == "__main__":
    unittest.main()
