"""CPU-only contracts. These tests make no 2B/GPU effectiveness claim."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.public_sft141_diagnostic import contract
from tools.public_sft141_diagnostic import model_worker as worker


def plan_fixture():
    return {"schema": "iris-public-sft141-plan-v1", "provenance": {}, "protocol": {},
            "parents": [{"task_id": f"parent{i:02d}",
                         "train": [{"input": [[0, 1]], "output": [[1, 0]]}],
                         "test": [{"input": [[i % 10]], "test_index": 0,
                                   "query_id": f"parent{i:02d}:0"}], "selection": {}}
                        for i in range(12)]}


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeBackend:
    """Deterministic injected backend, never selected by the real CLI."""
    max_context = 8192
    metadata = {"backend": "simulated-cpu-test-only", "model_effectiveness_evidence": False}

    def __init__(self, clock, *, generation_seconds=0.001, scoring_seconds=0.0001):
        self.clock = clock
        self.generation_seconds = generation_seconds
        self.scoring_seconds = scoring_seconds
        self.generate_calls = []
        self.score_calls = []
        self.fail_generation_call = None
        self.fail_score_call = None
        self.invalid_admission = False
        self.deadline_generation_call = None

    def generate(self, prompt, max_new_tokens, deadline):
        self.generate_calls.append((list(prompt), max_new_tokens))
        number = len(self.generate_calls)
        self.clock.advance(self.generation_seconds)
        if number == self.fail_generation_call:
            raise RuntimeError("simulated generation failure")
        if number == self.deadline_generation_call:
            self.clock.value = deadline.work_end
            return {"token_ids": [1], "seconds": self.generation_seconds,
                    "memory": {"simulated": True}, "termination": "deadline"}
        if number <= 3 and self.invalid_admission:
            return {"token_ids": [11, 15], "seconds": self.generation_seconds,
                    "memory": {"simulated": True}, "termination": "eos"}
        # Two candidates in equal vote counts. B prefers color 2 by lower NLL.
        color = 1 if number <= 3 or (number - 4) % 8 < 4 else 2
        return {"token_ids": [color, 15], "seconds": self.generation_seconds,
                "memory": {"simulated": True}, "termination": "eos"}

    def score(self, prompt, answer, deadline):
        self.score_calls.append((list(prompt), list(answer)))
        self.clock.advance(self.scoring_seconds)
        if len(self.score_calls) == self.fail_score_call:
            raise RuntimeError("simulated NLL failure")
        return {"nll": 10.0 if answer[0] == 1 else 0.0,
                "seconds": self.scoring_seconds, "memory": {"simulated": True}}


class WorkerContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "fresh"
        self.clock = FakeClock()
        self.backend = FakeBackend(self.clock)

    def run_worker(self, **kwargs):
        return worker.run(kwargs.pop("plan", plan_fixture()), self.backend, self.output,
                          kwargs.pop("budget_seconds", 600), self.clock, **kwargs)

    def test_complete_same_pool_eight_conditions_and_deterministic_rankings(self):
        result = self.run_worker()
        self.assertEqual(result["status"], "complete")
        self.assertTrue(result["full_panel_complete"])
        self.assertFalse(result["capability_claim"])
        self.assertEqual(len(self.backend.generate_calls), 3 + 12 * 8)
        self.assertTrue(all(call[1] == 931 for call in self.backend.generate_calls))
        self.assertEqual(len(self.backend.score_calls), 3 + 12 * 2 * 8)
        self.assertEqual(result["counts"]["missing_views"], 0)
        for query in result["queries"]:
            self.assertEqual([row["count"] for row in query["candidates"]], [4, 4])
            self.assertEqual(query["vote"], [[[1]], [[2]]])
            self.assertEqual(query["rescored"], [[[2]], [[1]]])
            self.assertTrue(query["vote_complete"])
            self.assertTrue(query["rescoring_complete"])
            self.assertEqual(query["candidates"][0]["mean_nll"], 10)
            self.assertEqual(query["candidates"][0]["combined_score"], -6)
            for candidate in query["candidates"]:
                self.assertEqual([entry["view"] for entry in candidate["view_nll"]], list(range(8)))
                self.assertTrue(all(entry["includes_eos"] for entry in candidate["view_nll"]))

    def test_rectangular_d4_inverse_deduplicates_and_scoring_reapplies_every_view(self):
        grid = [[1, 2, 3], [4, 5, 6]]
        backend = self.backend
        original_generate = backend.generate

        def rectangular_generate(prompt, max_new_tokens, deadline):
            receipt = original_generate(prompt, max_new_tokens, deadline)
            number = len(backend.generate_calls)
            if number > 3:
                receipt["token_ids"] = contract.answer_ids(contract.transform(grid, (number - 4) % 8))
            return receipt

        backend.generate = rectangular_generate
        result = self.run_worker()
        for query in result["queries"]:
            self.assertEqual(len(query["candidates"]), 1)
            self.assertEqual(query["candidates"][0]["grid"], grid)
            self.assertEqual(query["candidates"][0]["count"], 8)
            self.assertEqual(query["vote"], [grid])
            self.assertEqual(query["rescored"], [grid])
        first_scoring_conditions = backend.score_calls[3:11]
        for view, (prompt, answer) in enumerate(first_scoring_conditions):
            self.assertEqual(answer, contract.answer_ids(contract.transform(grid, view)))
            self.assertEqual(prompt, contract.prompt_ids(plan_fixture()["parents"][0]["train"], [[0]], view))

    def test_every_test_input_is_retained_for_each_fixed_parent(self):
        plan = plan_fixture()
        plan["parents"][0]["test"].append({"input": [[9]], "test_index": 1, "query_id": "parent00:1"})
        result = self.run_worker(plan=plan)
        self.assertEqual(result["counts"]["queries"], 13)
        self.assertEqual(result["counts"]["expected_views"], 104)
        self.assertEqual([row["query_id"] for row in result["queries"][:2]], ["parent00:0", "parent00:1"])
        self.assertEqual(len(self.backend.generate_calls), 3 + 104)

    def test_raw_tokens_time_memory_and_unique_receipts(self):
        self.run_worker()
        receipt = json.loads((self.output / "receipts/view-0000-0.json").read_text())
        self.assertEqual(receipt["token_ids"], [1, 15])
        self.assertEqual(receipt["seconds"], 0.001)
        self.assertTrue(receipt["memory"]["simulated"])
        self.assertEqual(receipt["max_new_tokens"], 931)
        self.assertEqual(len(receipt["prompt_sha256"]), 64)
        self.assertEqual(len(list((self.output / "receipts").glob("view-*.json"))), 96)
        self.assertEqual(len(list((self.output / "receipts").glob("nll-*.json"))), 192)
        with self.assertRaises(FileExistsError):
            self.run_worker()

    def test_atomic_receipts_never_overwrite(self):
        artifacts = worker.Artifacts(self.output)
        artifacts.write("result.json", {"value": 1})
        with self.assertRaises(FileExistsError):
            artifacts.write("result.json", {"value": 2})
        self.assertEqual(json.loads((self.output / "result.json").read_text()), {"value": 1})
        self.assertFalse(list(self.output.glob(".pending-*")))

    def test_gold_bearing_query_or_metadata_rejected(self):
        for mutation in ("query", "metadata", "top"):
            plan = plan_fixture()
            if mutation == "query":
                plan["parents"][0]["test"][0]["output"] = [[9]]
            elif mutation == "metadata":
                plan["provenance"]["gold"] = [[[9]]]
            else:
                plan["answers"] = {"parent00": [[[9]]]}
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                worker.validate_plan(plan)

    def test_exact_twelve_parents_and_all_query_order(self):
        plan = plan_fixture()
        plan["parents"].pop()
        with self.assertRaises(ValueError):
            worker.validate_plan(plan)
        plan = plan_fixture()
        plan["parents"][0]["test"][0]["test_index"] = 2
        with self.assertRaises(ValueError):
            worker.validate_plan(plan)

    def test_context_limit_never_silently_truncates_supports(self):
        self.backend.max_context = 931
        result = self.run_worker()
        self.assertEqual(result["status"], "context_admission_failed")
        self.assertEqual(len(self.backend.generate_calls), 0)
        self.assertEqual(result["counts"]["missing_views"], 96)
        self.assertIn("full prompt", result["errors"][0])

    def test_three_unique_admission_queries_exact_longest_view(self):
        plan = plan_fixture()
        for i, parent in enumerate(plan["parents"]):
            parent["train"][0]["input"] = [[1] * (i + 1)]
        result = self.run_worker(plan=plan)
        admissions = result["context_admission"]
        self.assertEqual([row["length_class"] for row in admissions], ["short", "median", "longest"])
        self.assertEqual(len({row["query_id"] for row in admissions}), 3)
        self.assertEqual(admissions[-1]["query_id"], "parent11:0")
        for row in admissions:
            self.assertEqual(row["prompt_tokens"], max(row["prompt_tokens_by_view"]))
            self.assertEqual(row["max_new_tokens"], 931)

    def test_worst_case_envelope_does_not_force_false_early_exit(self):
        result = self.run_worker(budget_seconds=20)
        initial = result["projections"][0]
        self.assertTrue(initial["fits"])
        self.assertFalse(initial["worst_case_fits"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(initial["safety_factor"], 1.25)

    def test_measured_budget_decline_retains_admission_no_panel(self):
        self.backend.generation_seconds = 0.1
        result = self.run_worker(budget_seconds=20)
        self.assertEqual(result["status"], "budget_declined")
        self.assertEqual(len(self.backend.generate_calls), 3)
        self.assertEqual(len(result["context_admission"]), 3)
        self.assertEqual(result["counts"]["missing_views"], 96)
        self.assertFalse(result["full_panel_complete"])

    def test_rescoring_failure_retains_vote_but_not_partial_b_ranking(self):
        self.backend.fail_score_call = 4
        result = self.run_worker()
        self.assertEqual(result["status"], "partial_failure")
        self.assertEqual(result["phase"], "panel_rescoring")
        self.assertEqual(result["counts"]["vote_complete_queries"], 12)
        self.assertEqual(result["counts"]["rescoring_complete_queries"], 0)
        self.assertTrue(all(query["vote"] for query in result["queries"]))
        self.assertTrue(all(not query["rescored"] for query in result["queries"]))
        failure = json.loads((self.output / "receipts/nll-0000-0-0.json").read_text())
        self.assertEqual(failure["status"], "failed")
        self.assertIn("seconds", failure)

    def test_generation_failure_cannot_claim_view_quorum(self):
        self.backend.fail_generation_call = 11  # Last view of the first query.
        result = self.run_worker()
        self.assertEqual(result["status"], "partial_failure")
        self.assertFalse(result["queries"][0]["vote_complete"])
        self.assertEqual(result["counts"]["failed_views"], 1)
        self.assertEqual(result["counts"]["missing_views"], 88)
        self.assertFalse(result["full_panel_complete"])

    def test_cooperative_deadline_preserves_raw_truncated_answer(self):
        self.backend.deadline_generation_call = 4
        result = self.run_worker()
        self.assertEqual(result["status"], "partial_budget")
        self.assertEqual(result["counts"]["truncated_views"], 1)
        self.assertEqual(result["counts"]["invalid_views"], 1)
        self.assertEqual(result["queries"][0]["views"][0]["token_ids"], [1])
        self.assertEqual(result["queries"][0]["vote"], [])
        self.assertGreaterEqual(result["budget"]["remaining_seconds"], result["budget"]["closure_reserve_seconds"])

    def test_invalid_admission_is_format_not_context_failure(self):
        self.backend.invalid_admission = True
        result = self.run_worker()
        self.assertEqual(result["status"], "complete")
        self.assertTrue(all(not row["valid"] for row in result["context_admission"]))
        self.assertTrue(all(row["scoring_receipt"]["source"] == "synthetic-30x30-zero-grid-cost-only"
                            for row in result["context_admission"]))
        self.assertEqual(len(self.backend.score_calls[0][1]), 930)
        self.assertEqual(result["queries"][0]["candidates"][0]["count"], 4)

    def test_original_deadline_includes_prior_load_time(self):
        deadline = worker.Deadline(100, self.clock)
        self.clock.advance(85)
        result = self.run_worker(budget_seconds=100, deadline=deadline)
        self.assertEqual(len(self.backend.generate_calls), 0)
        self.assertEqual(result["budget"]["elapsed_seconds"], 85)
        self.assertEqual(result["status"], "context_admission_failed")

    def test_budget_is_finite_bounded_and_cannot_resume(self):
        for seconds in (0, -1, 7201, float("inf"), float("nan")):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                worker.Deadline(seconds)

    def test_tokenizer_real_contract_crosscheck(self):
        plan = plan_fixture()
        texts = {contract.prompt_text(parent["train"], query["input"], view):
                 contract.prompt_ids(parent["train"], query["input"], view)
                 for parent in plan["parents"] for query in parent["test"] for view in range(8)}

        class Tokenizer:
            eos_token_id = 15
            pad_token_id = 13
            def get_vocab(self):
                return {("Ċ" if token == "\n" else token): index for index, token in enumerate(contract.TOKEN_STRINGS)}
            def decode(self, ids, **kwargs):
                return "".join(contract.TOKEN_STRINGS[index] for index in ids)
            def encode(self, text, add_special_tokens):
                if add_special_tokens:
                    raise AssertionError("no generic BOS/chat wrapper")
                return texts[text]

        backend = worker.TransformersBackend.__new__(worker.TransformersBackend)
        backend.tokenizer = Tokenizer()
        backend._verify_tokenizer(plan)
        backend.tokenizer.eos_token_id = 13
        with self.assertRaises(worker.AdmissionFailure):
            backend._verify_tokenizer(plan)


@unittest.skipUnless(os.environ.get("PUBLIC_SFT141_TOKENIZER_DIR") and importlib.util.find_spec("transformers"),
                     "public local tokenizer path/transformers not supplied; no tokenizer-file claim")
class ActualPublicTokenizerTests(unittest.TestCase):
    def test_actual_public_local_tokenizer_bytelevel_vocab_and_prompts(self):
        tokenizer = worker.load_public_tokenizer(os.environ["PUBLIC_SFT141_TOKENIZER_DIR"])
        self.assertEqual(type(tokenizer.backend_tokenizer.model).__name__, "WordLevel")
        self.assertEqual(tokenizer.get_vocab()["Ċ"], 10)
        self.assertEqual(tokenizer.decode([10], skip_special_tokens=False), "\n")
        backend = worker.TransformersBackend.__new__(worker.TransformersBackend)
        backend.tokenizer = tokenizer
        backend._verify_tokenizer(plan_fixture())


@unittest.skipUnless(importlib.util.find_spec("torch"), "CPU torch is unavailable; no numerical/model claim")
class TorchNumericalTests(unittest.TestCase):
    def test_full_answer_shift_sum_eos_fp32_and_prompt_exclusion(self):
        import torch
        logits = torch.zeros((1, 4, 16), dtype=torch.bfloat16)
        logits[0, 0, 7] = 100  # Prompt-only prediction must be excluded.
        logits[0, 1, 2] = 3
        logits[0, 2, 15] = 4
        logits[0, 3, 5] = 100  # Position after the final answer target is excluded.
        actual = worker.full_answer_nll(logits, 2, [2, 15])
        oracle = -(torch.log_softmax(logits.float(), dim=-1)[0, 1, 2] +
                   torch.log_softmax(logits.float(), dim=-1)[0, 2, 15]).item()
        self.assertAlmostEqual(actual, oracle, places=6)
        self.assertGreater(actual, 0)
        with self.assertRaises(ValueError):
            worker.full_answer_nll(logits, 2, [2])

    @unittest.skipUnless(importlib.util.find_spec("transformers"), "CPU transformers unavailable; tiny public config not run")
    def test_tiny_public_model_full_answer_matches_manual_causal_loss(self):
        import torch
        from transformers import Qwen3Config, Qwen3ForCausalLM
        torch.manual_seed(0)
        config = Qwen3Config(vocab_size=16, hidden_size=16, intermediate_size=32,
                             num_hidden_layers=1, num_attention_heads=2,
                             num_key_value_heads=1, head_dim=8, max_position_embeddings=128,
                             eos_token_id=15, pad_token_id=13, attention_dropout=0.0)
        model = Qwen3ForCausalLM(config).eval()
        prompt = [14, 11, 10, 1, 15, 14, 12, 10]
        answer = [2, 10, 3, 15]
        ids = torch.tensor([prompt + answer[:-1]])
        with torch.inference_mode():
            logits = model(input_ids=ids, use_cache=False).logits
            actual = worker.full_answer_nll(logits, len(prompt), answer)
            selected = logits[0, len(prompt) - 1:len(prompt) - 1 + len(answer)].float()
            oracle = torch.nn.functional.cross_entropy(selected, torch.tensor(answer), reduction="sum").item()
        self.assertAlmostEqual(actual, oracle, places=5)


if __name__ == "__main__":
    unittest.main()
