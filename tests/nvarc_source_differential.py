"""Strict source differential suite: run only in the pinned ML environment.

Every source comparison loads the hash-checked upstream file or notebook cell.
Missing material/dependencies are failures, never skips.
"""

from __future__ import annotations

import math
import json
import hashlib
from pathlib import Path
import random
import tempfile
import types
import unittest

import numpy as np
import torch

from irisx.arc_nvarc_candidates import (FixtureCandidateBackend, PrefixLogitCache,
                                         bounded_dfs_search, rank_candidates,
                                         solve_task)
from irisx.arc_nvarc_data import (source_qwen_training_views, source_qwen_transform_grid,
                                  source_qwen_transform_task, source_qwen_views,
                                  source_sdg_messages, transform_grid, transform_task)
from irisx.arc_nvarc_qwen35_adapter import answer_nll, full_prefix_log_probs
from irisx.arc_nvarc_representation import (BEGIN, END, PAD, SYMBOLS, GridTokenizer,
                                             PINNED_SOURCE_IDS)
from irisx.arc_nvarc_training import (source_sft_sequences, task_local_sequences,
                                      train_torch_sft)
from irisx.arc_nvarc_trm import (preprocess_source_training_fixture,
                                  stage_trm_training, trm_grid)
from irisx.arc_nvarc_upstream import (qwen_cell, sdg_build_datasets,
                                      trm_dataset_entry)
from irisx.canonical import digest_value
from irisx.errors import ValidationError


TASK = {"task_id": "rect", "train": [
    {"input": [[1, 2, 3], [4, 5, 6]], "output": [[6, 5], [4, 3], [2, 1]]},
    {"input": [[7, 8]], "output": [[8, 7]]}],
    "test": [{"input": [[1, 2]]}, {"input": [[3], [4]]}]}


def source_text_ids(text: str) -> list[int]:
    """Explicit source Qwen3 compact mapping; native Qwen3.5 IDs are separate."""
    literals = (("<|im_start|>", BEGIN), ("<|im_end|>", END),
                ("assistant", 12), ("user", 11), ("\n", 10))
    result = []
    while text:
        match = next(((literal, value) for literal, value in literals if text.startswith(literal)), None)
        if match:
            literal, value = match
            result.append(value)
            text = text[len(literal):]
        elif text[0] in "0123456789":
            result.append(int(text[0]))
            text = text[1:]
        else:
            raise AssertionError(f"unmapped Qwen source character: {text[:20]!r}")
    return result


class TreeModel:
    """Deterministic logits only; traversal itself is the real source DFS."""

    device = torch.device("cpu")

    def __init__(self, *, prune_second: bool = False, immediate_eos: bool = False) -> None:
        self.prune_second = prune_second
        self.immediate_eos = immediate_eos
        self.visited: list[tuple[int, ...]] = []

    def __call__(self, input_ids, past_key_values=None, **_kwargs):
        prefixes = []
        for index, row in enumerate(input_ids.tolist()):
            prefix = tuple(row) if past_key_values is None else tuple(past_key_values[index]) + tuple(row)
            prefixes.append(prefix)
            self.visited.append(prefix)
        logits = torch.full((len(prefixes), input_ids.shape[1], 16), -30.0)
        for index, prefix in enumerate(prefixes):
            if len(prefix) == 1:
                if self.immediate_eos:
                    logits[index, -1, END] = 10.0
                else:
                    logits[index, -1, 1] = 10.0
                    logits[index, -1, 2] = 6.0 if self.prune_second else 10.0
            else:
                logits[index, -1, END] = 10.0
        return types.SimpleNamespace(logits=logits, past_key_values=prefixes)


class PositionModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(()), requires_grad=False)

    @property
    def device(self):
        return self.anchor.device

    def forward(self, input_ids, **_kwargs):
        vocab = torch.arange(16, device=input_ids.device)
        target = (input_ids + 1) % 16
        logits = -(vocab[None, None, :] - target[:, :, None]).abs().float()
        return types.SimpleNamespace(logits=logits + self.anchor * 0)


class DifferentialTests(unittest.TestCase):
    def test_source_sdg_rectangular_augmentation_messages_and_seed(self):
        source = sdg_build_datasets()
        pairs = TASK["train"]
        prior = random.getstate()
        integrated = source_sdg_messages(pairs, seed=31, augment=True)
        self.assertEqual(prior, random.getstate())
        random.seed(31)
        rules = source.fix_settings(["dihedral", "color"])
        expected = source.get_messages(source.apply_augmentation(pairs, rules))
        random.setstate(prior)
        self.assertEqual(rules, integrated["rules"])
        self.assertEqual(expected, integrated["messages"])
        self.assertEqual(["user", "assistant", "user", "assistant"],
                         [m["role"] for m in integrated["messages"]])
        # The older IRIS-X one-pass color map differs from source's in-place
        # mapping for cycles; the new source path retains the original behavior.
        swap = [{"type": "color", "settings": {"mapping": [0, 2, 1, 3, 4, 5, 6, 7, 8, 9]}}]
        upstream = source.apply_augmentation([{"input": [[1, 2]], "output": [[2, 1]]}], swap)
        local = transform_grid([[1, 2]], {"rotation": 0, "transpose": False,
                                          "colors": swap[0]["settings"]["mapping"]})
        self.assertNotEqual(upstream[0]["input"], local)

    def test_qwen_source_views_inverse_demo_order_and_multitest(self):
        loader = qwen_cell("arc_loader.py")
        colors = [2, 0, 1, 3, 4, 5, 6, 7, 8, 9]
        for transpose in (False, True):
            for rotation in range(4):
                spec = {"transpose": transpose, "rotation": rotation,
                        "colors": colors, "demo_order": [1, 0]}
                rendered = source_qwen_transform_task(TASK, spec)
                self.assertEqual(TASK["train"][1]["output"], source_qwen_transform_grid(
                    rendered["train"][0]["output"], spec, inverse=True))
                self.assertEqual(transform_task(TASK, spec)["test"], rendered["test"])
                original = source_qwen_transform_grid(rendered["test"][1]["input"], spec,
                                                      inverse=True)
                self.assertEqual(TASK["test"][1]["input"], original)
        views = source_qwen_views(TASK, 1, seed=2, color_repeats=2)
        self.assertEqual(16, len(views))
        self.assertTrue(all(len(view["task"]["test"]) == 1 for view in views))
        self.assertTrue(all("source_key" in view["spec"] for view in views))
        source = loader.ArcDataset({"view": {"train": TASK["train"],
                                            "test": [TASK["test"][1]]}}, keys=["view"])
        state = np.random.get_state()
        try:
            original = source.augment(n=2, seed=2)
        finally:
            np.random.set_state(state)
        self.assertEqual(set(original.keys), {view["spec"]["source_key"] for view in views})
        for view in views:
            key = view["spec"]["source_key"]
            self.assertEqual(original.queries[key], {"train": view["task"]["train"],
                                                     "test": view["task"]["test"]})

    def test_role_eos_mask_and_explicit_native_id_map(self):
        loader = qwen_cell("arc_loader.py")
        formatter = loader.QwenFormatter(None)
        tokenizer = GridTokenizer(source_chat_newlines=True)
        query = formatter.fmt_train(TASK["train"]) + formatter.fmt_query([TASK["test"][0]])
        self.assertEqual(source_text_ids(query), tokenizer.encode_query(TASK, 0))
        reply = formatter.fmt_reply([[[8, 9], [0, 1]]])
        self.assertEqual(source_text_ids(reply), tokenizer.encode_grid([[8, 9], [0, 1]]) + [END])
        pair_tokens, labels = tokenizer.encode_pair([[1, 2]], [[3, 4]])
        self.assertEqual([-100] * (len(pair_tokens) - 3) + [3, 4, END], labels)
        source_collator = qwen_cell("arc_solver.py").QwenDataCollatorForCompletionOnlyLM()
        self.assertEqual(labels, source_collator.torch_call([pair_tokens])["labels"][0].tolist())
        self.assertEqual(tuple(range(15, 25)) + (198, 846, 74455, 248044, 248045, 248046),
                         PINNED_SOURCE_IDS)

    def test_upstream_task_adaptation_views_and_masks(self):
        loader = qwen_cell("arc_loader.py")
        source_collator = qwen_cell("arc_solver.py").QwenDataCollatorForCompletionOnlyLM()
        views = source_qwen_training_views(TASK, seed=1, color_repeats=1)
        adapted = task_local_sequences(TASK, seed=42, augmentation_count=1,
                                       source_qwen=True, source_augmentation_seed=1)
        self.assertEqual(8, len(views))
        self.assertEqual(len(views), len(adapted))
        formatter = loader.QwenFormatter(None)
        for view, sequence in zip(views, adapted):
            source_text = formatter.fmt_train(view["train"], last_is_challenge=True)
            self.assertEqual(source_text_ids(source_text), sequence["input_ids"])
            upstream_labels = source_collator.torch_call([sequence["input_ids"]])["labels"][0].tolist()
            self.assertEqual(upstream_labels, sequence["labels"])

    def test_actual_source_sft_loader_to_compact_sequences(self):
        from datasets import Dataset

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            messages = source_sdg_messages(TASK["train"], seed=0, augment=False)["messages"]
            paths = []
            for index in range(2):
                path = root / f"source-{index}"
                Dataset.from_list([{"puzzle_name": f"fixture-{index}",
                                    "messages": messages}]).save_to_disk(path)
                paths.append(str(path))
            sequences = source_sft_sequences(paths, maximum_records=2)
        self.assertEqual(2, len(sequences))
        self.assertEqual(["fixture-0", "fixture-1"], [x["source"] for x in sequences])
        expected = []
        for pair in TASK["train"]:
            expected.extend(GridTokenizer(source_chat_newlines=True).encode_pair(
                pair["input"], pair["output"])[0])
        self.assertEqual(expected, sequences[0]["input_ids"])
        self.assertEqual(len(expected), len(sequences[0]["labels"]))
        self.assertEqual(2, sequences[0]["labels"].count(END))
        from tests.test_arc_nvarc_ml import NvarcMLTests

        model = NvarcMLTests()._tiny_qwen()
        model.resize_token_embeddings(16)
        before = model.get_input_embeddings().weight.detach().clone()
        with tempfile.TemporaryDirectory() as temp:
            trained = train_torch_sft(model, sequences, Path(temp) / "sft",
                {"mode": "full-sft", "device": "cpu", "seed": 3,
                 "learning_rate": 0.001, "max_steps": 1,
                 "maximum_training_tokens": 1000, "max_sequence_length": 128,
                 "gradient_accumulation": 1, "checkpoint_every": 1},
                model_identity_digest=digest_value("source-fixture-tiny-qwen"))
            self.assertTrue((Path(temp) / "sft/training-state.pt").is_file())
        self.assertEqual(1, trained["steps"])
        self.assertTrue(math.isfinite(trained["last_loss"]))
        self.assertFalse(torch.equal(before, model.get_input_embeddings().weight))

    def test_actual_trm_builder_rectangular_eos(self):
        source = trm_dataset_entry()
        sample = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.uint8)
        encoded = source.np_grid_to_seq_translational_augment(sample, sample, False)[0]
        self.assertEqual(trm_grid(sample.tolist()), encoded.tolist())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage = root / "stage"
            output = root / "processed"
            labelled = {"fixture": {"train": [TASK["train"][0]],
                                    "labelled_test": [{"input": [[1, 2]],
                                                       "output": [[2, 1]]}]}}
            stage_trm_training(labelled, stage, source_digest="sha256:" + "a" * 64,
                               augmentation_count=0)
            report = preprocess_source_training_fixture(stage, output, seed=5)
            values = np.load(output / "train/all__inputs.npy")
            self.assertEqual((2, 900), values.shape)
            expected_untranslated = (trm_grid(TASK["train"][0]["input"]), trm_grid([[1, 2]]))
            self.assertTrue(any(row.tolist() == expected for row in values
                                for expected in expected_untranslated))
            self.assertEqual(900, report["dataset_metadata"]["seq_len"])
            self.assertTrue(report["contains_labels"])

    def test_upstream_dfs_traversal_pruning_and_completion(self):
        source = qwen_cell("arc_solver.py")
        for prune in (False, True):
            model = TreeModel(prune_second=prune)
            upstream = source.inference_turbo_dfs(model, [[BEGIN]], 2, 1.0, float("inf"))
            local_calls = []

            def next_probs(prefix):
                local_calls.append(tuple(prefix))
                output = TreeModel(prune_second=prune)(torch.tensor([prefix]))
                return torch.log_softmax(output.logits[0, -1], dim=-1).tolist()

            local = bounded_dfs_search([BEGIN], next_probs, max_new_tokens=2,
                                       max_score=1.0, max_expansions=8, max_sequences=3)
            got = [(round(x["beam_nll"], 5), x["tokens"]) for x in local["sequences"]]
            expected = [(round(score, 5), tokens) for score, tokens in upstream[0][1]]
            self.assertEqual(expected, got)
            self.assertEqual(model.visited, local_calls)
            self.assertEqual(1 if prune else 2, len(got))
            self.assertEqual("exhausted", local["stop_reason"])
        empty_raw = source.inference_turbo_dfs(TreeModel(immediate_eos=True),
                                                [[BEGIN]], 2, 1.0, float("inf"))
        self.assertEqual([END], empty_raw[0][1][0][1])
        self.assertIsNone(qwen_cell("arc_loader.py").QwenFormatter(None).convert_tokens_to_array([END]))
        empty_filtered = bounded_dfs_search([BEGIN], lambda _: [-50.0] * 15 + [0.0],
                                            max_new_tokens=2, max_score=1.0,
                                            max_expansions=3, max_sequences=1)
        self.assertEqual("no_valid_candidate", empty_filtered["stop_reason"])

    def test_source_nll_duplicate_votes_top_two_and_missing(self):
        source = qwen_cell("arc_solver.py")
        decoder = qwen_cell("arc_decoder.py")
        model = PositionModel()

        class Tokens:
            def encode(self, text):
                return {"q": [BEGIN, 11], "a": [1, END]}[text]

        reference = source.calc_scores(["q"], ["a"], Tokens(), model)[0]
        local = answer_nll(model, [BEGIN, 11], [1, END], normalize=False)
        self.assertAlmostEqual(reference, local, places=5)
        views = source_qwen_views(TASK, 0, seed=17, color_repeats=1, answer=[[1, 2]])
        self.assertEqual(8, len(views))
        self.assertEqual(8, len({view["spec"]["source_key"] for view in views}))
        compact = GridTokenizer(source_chat_newlines=True)
        encoded = {}
        queries, answers, local_view_nll = [], [], []
        for index, view in enumerate(views):
            query, answer = f"q{index}", f"a{index}"
            encoded[query] = compact.encode_query(view["task"], 0)
            encoded[answer] = compact.encode_grid(view["answer"]) + [END]
            queries.append(query)
            answers.append(answer)
            local_view_nll.append(answer_nll(model, encoded[query], encoded[answer],
                                             normalize=False))

        class ViewTokens:
            def encode(self, text):
                return encoded[text]

        upstream_view_nll = source.calc_scores(queries, answers, ViewTokens(), model)
        for expected, actual in zip(upstream_view_nll, local_view_nll):
            self.assertAlmostEqual(expected, actual, places=4)
        scores = [float(i + 1) for i in range(8)]
        raw = [{"grid": [[1, 2]], "complete": True, "source": f"v{i}",
                "beam_nll": float(i), "verification_nll": sum(scores) / 8}
               for i in range(2)]
        raw.append({"grid": [[2, 1]], "complete": True, "source": "v2",
                    "beam_nll": 0.1, "verification_nll": 0.5})
        ranked = rank_candidates(raw, policy="source-kgmon")
        source_ranked = decoder.score_kgmon({str(i): {"solution": np.array(item["grid"]),
                                                     "score_aug": [item["verification_nll"]] * 8}
                                             for i, item in enumerate(raw)})
        self.assertEqual([item.tolist() for item in source_ranked[:2]],
                         [item["grid"] for item in ranked[:2]])
        self.assertEqual(2, ranked[0]["votes"] if ranked[0]["grid"] == [[1, 2]] else ranked[1]["votes"])
        self.assertEqual([], rank_candidates([], policy="source-kgmon"))

    def test_integrated_source_profile_multitest_shared_verification(self):
        backend = FixtureCandidateBackend({"rect:0": [[[1, 2]]],
                                           "rect:1": [[[3], [4]]]})
        result = solve_task(TASK, backend, {"seed": 2, "color_repeats": 2,
            "maximum_calls_per_task": 4, "beams_per_call": 1,
            "maximum_new_tokens": 8, "augmentation": "source-qwen",
            "representation": "source-qwen", "ranking": "source-kgmon"})
        self.assertEqual(2, len(result))
        self.assertEqual([1, 2], [item["verification_calls_so_far"] for item in result])
        self.assertEqual([2, 2], [item["ranked"][0]["votes"] for item in result])
        self.assertEqual([1, 1], [item["missing_attempts"] for item in result])
        self.assertEqual([[[1, 2]], [[3], [4]]],
                         [item["attempts"][0] for item in result])

    def test_one_stage_config_fixture_uses_shared_result_schema(self):
        from tools.nvarc_source_stage import run

        root = Path(__file__).resolve().parents[1]
        config = root / "trials/arc-agi-2-qwen35-nvarc/configs/source-integration-stage.json"
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            visible, predictions, output = (work / name for name in
                                            ("visible.json", "fixture.json", "result.json"))
            visible.write_text(json.dumps({"rect": TASK}), encoding="utf-8")
            predictions.write_text(json.dumps({"rect:0": [[[1, 2]]],
                                               "rect:1": [[[3], [4]]]}), encoding="utf-8")
            report = run(config, visible, output, profile="fixture", fixture_path=predictions)
            self.assertEqual("irisx/nvarc-source-stage-result-v1", report["format"])
            self.assertEqual(2, report["test_count"])
            self.assertEqual(report, json.loads(output.read_bytes()))
            self.assertFalse(report["contains_evaluator_truth"])

    def test_one_stage_config_tiny_real_model_same_result_schema(self):
        from tests.test_arc_nvarc_ml import NvarcMLTests
        from tools.nvarc_source_stage import run

        root = Path(__file__).resolve().parents[1]
        config = root / "trials/arc-agi-2-qwen35-nvarc/configs/source-integration-stage.json"
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            model_dir = work / "compact"
            model_dir.mkdir()
            model = NvarcMLTests()._tiny_qwen()
            model.resize_token_embeddings(16)
            for obj in (model.config, model.config.text_config, model.generation_config):
                obj.pad_token_id, obj.eos_token_id, obj.bos_token_id = PAD, END, BEGIN
            model.config.vocab_size = model.config.text_config.vocab_size = 16
            model.save_pretrained(model_dir, safe_serialization=True)
            vocab = {"format": "irisx/nvarc-compact-vocab", "vocab_size": 16,
                     "symbols": [{"compact_id": i, "symbol": value,
                                  "source_token_ids": [i]} for i, value in enumerate(SYMBOLS)]}
            vocab["identity_digest"] = digest_value(vocab)
            (model_dir / "grid-vocab.json").write_text(json.dumps(vocab), encoding="utf-8")
            (model_dir / "grid-tokenizer.json").write_text(json.dumps({
                "format": "irisx/nvarc-grid-tokenizer", "symbols": list(SYMBOLS),
                "pad_token_id": PAD, "eos_token_id": END}), encoding="utf-8")
            files = [{"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "bytes": path.stat().st_size} for path in sorted(model_dir.iterdir()) if path.is_file()]
            material = {"format": "irisx/nvarc-compact-model-material", "tied_embeddings": True,
                        "base_model_revision": "tiny-fixture", "source_model_manifest_digest":
                        digest_value("tiny-fixture-base"), "vocabulary_identity_digest":
                        vocab["identity_digest"], "vision_modules_retained": True, "files": files}
            material_digest = digest_value(material)
            (model_dir / "material-manifest.json").write_text(json.dumps(material), encoding="utf-8")
            visible = work / "visible.json"
            visible.write_text(json.dumps({"tiny": {"train": [{"input": [[1]], "output": [[2]]}],
                                                    "test": [{"input": [[3]]}]}}), encoding="utf-8")
            result = run(config, visible, work / "tiny-result.json", profile="tiny",
                         checkpoint=model_dir, material_digest=material_digest)
            self.assertEqual("irisx/nvarc-source-stage-result-v1", result["format"])
            self.assertEqual(1, result["test_count"])
            self.assertEqual(1, len(result["results"]))
            self.assertFalse(result["contains_evaluator_truth"])

            # The future threshold proposal is an explicit separate tiny-only
            # configuration. Same loaded checkpoint, adaptation seed and query:
            # compare the actual forwarded roots, not a mocked constructor.
            proposal_config = json.loads(config.read_bytes())
            proposal_config["candidate"]["cumulative_probability_threshold"] = 0.02
            proposal_path = work / "root-threshold-tiny-proposal.json"
            proposal_path.write_text(json.dumps(proposal_config))
            proposed = run(proposal_path, visible, work / "root-threshold-tiny-result.json", profile="tiny",
                           checkpoint=model_dir, material_digest=material_digest)
            control = result["results"][0]["generation_observations"][0]
            candidate = proposed["results"][0]["generation_observations"][0]
            self.assertEqual(control["query_role_tail"], candidate["query_role_tail"])
            self.assertEqual(control["diagnostics"]["root"]["log_probs"], candidate["diagnostics"]["root"]["log_probs"])
            self.assertAlmostEqual(-math.log(.2), control["diagnostics"]["max_score"])
            self.assertAlmostEqual(-math.log(.02), candidate["diagnostics"]["max_score"])
            self.assertEqual(1, control["expansions"])
            self.assertGreater(candidate["expansions"], 1)

    def test_long_path_and_explicit_stop_reasons(self):
        def path(prefix):
            logits = [-50.0] * 16
            logits[END if len(prefix) >= 1101 else 1] = 0.0
            return logits

        long = bounded_dfs_search([BEGIN], path, max_new_tokens=1102,
                                  max_score=1.0, max_expansions=1200, max_sequences=1)
        self.assertEqual(1101, long["expansions"])
        self.assertEqual("sequence_limit", long["stop_reason"])
        self.assertEqual(1101, len(long["sequences"][0]["tokens"]))
        limited = bounded_dfs_search([BEGIN], path, max_new_tokens=1102,
                                     max_score=1.0, max_expansions=2, max_sequences=1)
        self.assertEqual("expansion_limit", limited["stop_reason"])
        token_limited = bounded_dfs_search([BEGIN], path, max_new_tokens=3,
                                           max_score=1.0, max_expansions=8, max_sequences=1)
        self.assertEqual("token_limit", token_limited["stop_reason"])
        timed = bounded_dfs_search([BEGIN], path, max_new_tokens=3,
                                   max_score=1.0, max_expansions=3, max_sequences=1,
                                   deadline=0, now=lambda: 0)
        self.assertEqual("deadline", timed["stop_reason"])
        missing = bounded_dfs_search([BEGIN], lambda _: [-50.0] * 16,
                                     max_new_tokens=3, max_score=1.0,
                                     max_expansions=3, max_sequences=1)
        self.assertEqual("no_valid_candidate", missing["stop_reason"])

    def test_tiny_real_qwen_full_prefix_branch_isolation(self):
        from tests.test_arc_nvarc_ml import NvarcMLTests

        torch.manual_seed(9)
        model = NvarcMLTests()._tiny_qwen()
        model.resize_token_embeddings(16)
        model.eval()
        prefixes = [[BEGIN, 11, 10, 1], [BEGIN, 11, 10, 2],
                    [BEGIN, 11, 10, 1]]
        reference = [full_prefix_log_probs(model, prefix) for prefix in prefixes]
        cache = PrefixLogitCache(lambda prefix: full_prefix_log_probs(model, prefix), 4)
        cached = [cache(prefix) for prefix in prefixes]
        self.assertEqual(1, cache.hits)
        for lhs, rhs in zip(reference, cached):
            self.assertLess(max(abs(a - b) for a, b in zip(lhs, rhs)), 1e-6)
        self.assertNotEqual(reference[0], reference[1])


if __name__ == "__main__":
    unittest.main()
