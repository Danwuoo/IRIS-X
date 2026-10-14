from copy import deepcopy
from dataclasses import replace
import sys
import unittest
from unittest.mock import patch

from tools.arc2_agent_factory3_bridge_20261014.bridge import digest, prepare_batch
from tools.arc2_agent_factory3_bridge_20261014.fixtures import synthetic_batch
from tools.arc2_agent_factory3_bridge_20261014.provenance import verify_vendor
from tools.arc2_agent_factory3_bridge_20261014.vendor.types import TrainingSample


class ContractTests(unittest.TestCase):
    def test_exact_upstream_source_pins(self):
        self.assertEqual(len(verify_vendor()), 4)

    def test_source_pin_mismatch_fails_closed(self):
        from tools.arc2_agent_factory3_bridge_20261014 import provenance
        batch, context = synthetic_batch()
        with patch.dict(provenance.VENDOR_SHA256, {"vendor/types.py": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "vendored source drift"):
                prepare_batch(batch, context)
        with patch.dict(provenance.FROZEN_CONTRACT_SHA256, {provenance.BASELINE_MATH: "0" * 64}):
            with self.assertRaisesRegex(ValueError, "frozen contract source drift"):
                prepare_batch(batch, context)

    def test_single_token_and_exact_native_capacity_boundaries(self):
        for p, n in ((1, 1), (3072, 1024)):
            with self.subTest(prompt=p, generated=n):
                batch, context = synthetic_batch()
                for index, row in enumerate(batch["rows"][:8]):
                    t = row["trajectory"]
                    prompt = [20] * p
                    generated = [1] * n if index == 0 else t["generated_ids"]
                    length = len(generated)
                    t.update(prompt_ids=prompt, generated_ids=generated, original_ids=prompt + generated,
                             attention_mask=[1] * (p + length), origins=["prompt"] * p + ["assistant_generated"] * length,
                             steps=[{"token": token, "position": p + i - 1, "support": [token], "log_mu": 0.,
                                     "dfa_state": [0, 1, 0], "prefix_sha256": digest(prompt + generated[:i])}
                                    for i, token in enumerate(generated)])
                sample = prepare_batch(batch, context).samples[0]
                self.assertEqual(sample.seq_token_count, n)
                self.assertEqual(len(sample.input_ids), p + n)

    def test_coherent_prompt_rewrite_within_fixed_parent_rejected(self):
        batch, context = synthetic_batch()
        t = batch["rows"][1]["trajectory"]
        prompt, generated = t["prompt_ids"] + [23], t["generated_ids"]
        t.update(prompt_ids=prompt, original_ids=prompt + generated,
                 attention_mask=[1] * (len(prompt) + len(generated)),
                 origins=["prompt"] * len(prompt) + ["assistant_generated"] * len(generated))
        for index, step in enumerate(t["steps"]):
            step.update(position=len(prompt) + index - 1, prefix_sha256=digest(prompt + generated[:index]))
        with self.assertRaisesRegex(ValueError, "fixed parent prompt"):
            prepare_batch(batch, context)

    def test_actual_upstream_objects_and_all_slots(self):
        batch, context = synthetic_batch()
        result = prepare_batch(batch, context)
        self.assertEqual(len(result.samples), 64)
        self.assertEqual(result.mixed_groups, 6)
        self.assertTrue(all(type(s) is TrainingSample for s in result.samples))
        self.assertEqual(sum(g["eligible"] for g in result.group_reports), 64)
        for row, sample in zip(batch["rows"], result.samples):
            t = row["trajectory"]
            p, n = len(t["prompt_ids"]), len(t["generated_ids"])
            self.assertEqual(sample.input_ids, t["original_ids"])
            self.assertEqual(sample.completion_mask, [0] * p + [1] * n)
            self.assertEqual(sample.divisor, 6 * 8 * n)
            self.assertEqual(sample.gen_logprobs[:p], [0.] * p)
            self.assertEqual(sample.advantages[:p], [0.] * p)
            self.assertEqual(sample.weight_version_token_counts, {0: n})
        self.assertFalse(result.summary()["production_update_authorized"])
        self.assertFalse(result.summary()["provenance_authenticated"])

    def test_zero_groups_retained_with_zero_advantage(self):
        batch, context = synthetic_batch((0, 8, 0, 8, 0, 8, 0, 8))
        result = prepare_batch(batch, context)
        self.assertEqual(len(result.samples), 64)
        self.assertEqual(result.mixed_groups, 0)
        self.assertTrue(all(all(a == 0 for a in s.advantages) for s in result.samples))

    def test_all_four_fixed_disjoint_batches(self):
        seen = set()
        for index in range(4):
            batch, context = synthetic_batch(batch_index=index)
            result = prepare_batch(batch, context)
            parents = {s.prompt_id for s in result.samples}
            self.assertFalse(seen.intersection(parents))
            seen.update(parents)
            self.assertTrue(all(s.oldest_weight_version == 0 for s in result.samples))
            self.assertEqual(result.summary()["upstream_weight_version_mapping"], {"0": context.policy_version})
        self.assertEqual(len(seen), 32)

    def test_full_prefix_cache_and_model_length_failure_allowed(self):
        batch, context = synthetic_batch()
        row = batch["rows"][7]
        for item in batch["rows"]:
            item["trajectory"]["sampling"]["cache_mode"] = "full_prefix"
        row["trajectory"]["finish_reason"] = "length"
        self.assertEqual(row["reward"], 0)
        prepare_batch(batch, context)

    def test_upstream_lengths_validator_is_executed(self):
        batch, context = synthetic_batch()
        sample = prepare_batch(batch, context).samples[0]
        fields = sample.model_dump()
        fields["gen_logprobs"] = []
        with self.assertRaises(ValueError):
            TrainingSample(**fields)

    def test_bad_context_is_rejected(self):
        batch, context = synthetic_batch()
        for changed in (
            replace(context, forbidden_parent_ids=(context.train_parent_ids[0],)),
            replace(context, batch_index=4), replace(context, batch_index=True),
            replace(context, evidence_kind="public-evaluation"),
            replace(context, actor_identity="not-a-hash"),
            replace(context, record_ids=context.record_ids[:-1]),
            replace(context, train_parent_ids=([],) + context.train_parent_ids[1:]),
            replace(context, forbidden_parent_ids=([],) + context.forbidden_parent_ids[1:]),
        ):
            with self.subTest(context=changed), self.assertRaises(ValueError):
                prepare_batch(batch, changed)

    def test_batch_negative_contracts(self):
        batch, context = synthetic_batch()
        changes = {
            "incomplete": lambda b: b.update(all_slots_reached=False),
            "closed": lambda b: b.update(closed=False),
            "missing": lambda b: b["rows"].pop(),
            "budget": lambda b: b.update(session_planned_attempts=512),
            "duplicate-slot": lambda b: b["rows"][1].update(slot=0),
            "unknown-reward": lambda b: b["rows"][0].update(reward=None),
            "boolean-reward": lambda b: b["rows"][0].update(reward=True),
            "not-training": lambda b: b["rows"][0].update(reason="public-score"),
            "infra": lambda b: b["rows"][0].update(eligible=False),
            "reorder": lambda b: b["rows"].reverse(),
            "panel": lambda b: b.update(panel_sha256="f" * 64),
            "fatal": lambda b: b.update(fatal_native_state="failed"),
            "fake-false": lambda b: b.update(fatal_native_state=0),
            "stopped": lambda b: b.update(stop_reason="incomplete-audit"),
        }
        for name, change in changes.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                modified = deepcopy(batch); change(modified); prepare_batch(modified, context)

    def test_trajectory_negative_contracts(self):
        batch, context = synthetic_batch()
        changes = {
            "actor": lambda t: t.update(identity="d" * 64),
            "stale": lambda t: t.update(policy_version="old"),
            "epoch": lambda t: t.update(generation_epoch=1),
            "record": lambda t: t.update(record_id="other"),
            "retokenized": lambda t: t["original_ids"].append(9),
            "origins": lambda t: t["origins"].__setitem__(0, "assistant_generated"),
            "position": lambda t: t["steps"][0].update(position=99),
            "prefix": lambda t: t["steps"][0].update(prefix_sha256="e" * 64),
            "support": lambda t: t["steps"][0].update(support=[99]),
            "duplicate-support": lambda t: t["steps"][0].update(support=[1, 1]),
            "forced-mu": lambda t: t["steps"][0].update(log_mu=-1.),
            "nan-mu": lambda t: t["steps"][1].update(log_mu=float("nan")),
            "huge-mu": lambda t: t["steps"][1].update(log_mu=-(10**1000)),
            "infinite-mu": lambda t: t["steps"][1].update(log_mu=-float("inf")),
            "float32-overflow-mu": lambda t: t["steps"][1].update(log_mu=-1e300),
            "nested-token": lambda t: t["prompt_ids"].__setitem__(0, []),
            "nested-step": lambda t: t["steps"].__setitem__(0, []),
            "nested-sampling": lambda t: t.update(sampling=[]),
            "missing-dfa-state": lambda t: t["steps"][0].pop("dfa_state"),
            "nested-dfa-state": lambda t: t["steps"][0].update(dfa_state=[[], 1, 0]),
            "fatal": lambda t: t.update(fatal_native_state=True),
            "fatal-zero": lambda t: t.update(fatal_native_state=0),
            "explicit-error": lambda t: t.update(error="failed"),
            "boolean-mask": lambda t: t.update(attention_mask=[True] * len(t["original_ids"])),
            "vocab-overflow": lambda t: t["generated_ids"].__setitem__(0, 151936),
            "generated-overflow": lambda t: t.update(generated_ids=[1] * 1025),
            "prompt-overflow": lambda t: t.update(prompt_ids=[1] * 3073),
            "missing-mu": lambda t: t["steps"][1].pop("log_mu"),
            "missing-step": lambda t: t["steps"].pop(),
            "empty-generated": lambda t: t.update(generated_ids=[]),
            "temperature": lambda t: t["sampling"].update(temperature=.8),
            "mixed-cache": lambda t: t["sampling"].update(cache_mode="full_prefix"),
            "no-dfa": lambda t: t["sampling"].update(dfa=False),
            "positive-length": lambda t: t.update(finish_reason="length"),
            "bool-token": lambda t: t["prompt_ids"].__setitem__(0, True),
        }
        for name, change in changes.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                modified = deepcopy(batch); change(modified["rows"][0]["trajectory"])
                prepare_batch(modified, context)

    def test_duplicate_trajectory_rejected(self):
        batch, context = synthetic_batch()
        batch["rows"][1]["trajectory"]["trajectory_id"] = batch["rows"][0]["trajectory"]["trajectory_id"]
        with self.assertRaises(ValueError):
            prepare_batch(batch, context)

    def test_input_not_mutated(self):
        batch, context = synthetic_batch(); before = deepcopy(batch)
        prepare_batch(batch, context)
        self.assertEqual(batch, before)

    def test_support_and_dfa_declarations_are_bound_without_authentication_claim(self):
        batch, context = synthetic_batch()
        before = prepare_batch(batch, context)
        changed = deepcopy(batch)
        changed["rows"][0]["trajectory"]["steps"][1]["support"] = [2, 12]
        after = prepare_batch(changed, context)
        self.assertEqual(before.sample_digest, after.sample_digest)
        self.assertNotEqual(before.raw_receipt_digest, after.raw_receipt_digest)
        self.assertNotEqual(before.contract_digest, after.contract_digest)
        changed = deepcopy(batch)
        changed["rows"][0]["trajectory"]["steps"][1]["dfa_state"] = [0, 2, 1]
        self.assertNotEqual(before.contract_digest, prepare_batch(changed, context).contract_digest)
        self.assertFalse(after.summary()["provenance_authenticated"])


if __name__ == "__main__":
    unittest.main()
