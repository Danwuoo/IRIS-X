"""Synthetic producer-schema conformance; no genuine/model run is claimed."""
import ast
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.arc2_agent_factory3_bridge_20261014.bridge import compute_loss, digest, prepare_batch
from tools.arc2_abc_continuation_20261014 import audit as adapter
from tools.arc2_abc_continuation_20261014.audit import AuditError, analyze_audit, context_from_document
from tools.arc2_abc_continuation_20261014.fixtures import audit_bytes, bind_context_document, synthetic_audit


def context(audit, doc):
    bound = bind_context_document(audit, doc)
    return context_from_document(bound, audit_sha256=bound["audit_sha256"])


def analyze(audit, doc, **kwargs):
    return analyze_audit(audit, context(audit, doc), **kwargs)


def frozen_function(relative, name, namespace):
    """Execute an unchanged inspected pure function, never model/runtime imports."""
    adapter.verify_sources()
    source = adapter.ROOT / relative
    tree = ast.parse(source.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[name]


def require(value, _message):
    if not value:
        raise ValueError("frozen-control-rejected")


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.audit, self.doc = synthetic_audit()

    def rejected(self, mutation, code=None):
        audit, doc = deepcopy(self.audit), deepcopy(self.doc)
        mutation(audit, doc)
        # Non-JSON values exercise the in-memory API; the CLI safe reader rejects
        # them before this adapter and no new byte hash can be fabricated.
        try:
            checked_context = context(audit, doc)
        except ValueError:
            checked_context = context_from_document(doc, audit_sha256=doc["audit_sha256"])
        result = analyze_audit(audit, checked_context)
        self.assertEqual("REJECTED", result["status"], result)
        self.assertFalse(result["conformance_complete"])
        if code is not None:
            self.assertEqual([code], result["issues"])
        return result

    def test_full_producer_shaped_audit_invokes_actual_upstream(self):
        import torch
        from tools.arc2_agent_factory3_bridge_20261014.vendor.losses.ddis_loss import DDISLoss
        original = DDISLoss.compute_unpacked
        calls = []
        def tracked(instance, **kwargs):
            calls.append(len(kwargs["log_probs"]))
            return original(instance, **kwargs)
        with patch.object(DDISLoss, "compute_unpacked", tracked):
            result = analyze(self.audit, self.doc)
        self.assertEqual("CONFORMANT_SAVED_REPLAY", result["status"])
        self.assertTrue(result["conformance_complete"])
        self.assertEqual([1] * 64, calls)
        self.assertEqual(64, result["replay"]["checked"])
        self.assertLess(result["replay"]["maximum_absolute_loss_delta"], 1e-7)
        self.assertIsNone(result["replay"]["leaf_logp_derivative"])
        self.assertEqual(64, result["coverage"]["eligible_mean_denominator"])
        for key in ("provenance_authenticated", "model_replay_verified", "model_gradients_verified",
                    "physical_execution_verified", "production_update_authorized", "ABC_efficacy_established"):
            self.assertIs(result[key], False)
        self.assertTrue(torch.is_grad_enabled())

    def test_unchanged_native_and_consumer_summary_differential(self):
        producer = frozen_function("tools/arc_qwen_rlvr004_20261013/source/experiment_flow/audit.py",
                                   "summarize", {"Counter": Counter, "require": require})
        consumer = frozen_function("tools/arc_qwen_rlvr004_20261013/release/terminal-consumer/consumer/audit_checks.py",
                                   "summary", {"Counter": Counter, "need": require, "integer": adapter._integer})
        for successes in ((1, 2, 4, 6, 0, 8, 3, 5), (0,) * 8, (8,) * 8, (1, 0, 0, 0, 0, 0, 0, 0)):
            a, _ = synthetic_audit(successes)
            for partial in (False, True):
                if partial:
                    a["batch"]["rows"][-1].update(trajectory=None, eligible=False, reward=None, status="not-reached")
                expected = producer(a["batch"], a["parent_ids"], 8)
                self.assertEqual(expected, consumer(a["batch"], a["parent_ids"], 8))
                self.assertEqual(expected, adapter._summary(a["batch"], a["parent_ids"]))

    def test_actual_modern_consumer_accepts_complete_native_shaped_fixture(self):
        # Import only the pinned stdlib consumer, under a distinct test namespace.
        import types
        import importlib
        adapter.verify_sources()
        package = types.ModuleType("abc_audit_test_frozen_consumer")
        package.__path__ = [str(adapter.ROOT / "tools/arc_qwen_rlvr004_20261013/release/terminal-consumer/consumer")]
        sys.modules[package.__name__] = package
        original = importlib.import_module(package.__name__ + ".audit_checks")
        a, d = deepcopy(self.audit), deepcopy(self.doc)
        batch, update, events = a["batch"], a["update"], {}
        for index, row in enumerate(batch["rows"]):
            t = row["trajectory"]
            self.assertEqual([index], t["physical_event_ids"])
            self.assertTrue(all(type(s["actor_event_id"]) is int and s["actor_event_id"] == index for s in t["steps"]))
            events[index] = {"event_id": index, "phase": "rollout-generation", "dispatched": True,
                "status": "complete", "started": index * .1, "ended": index * .1 + .05, "seconds": .05,
                "forward_calls": len(t["steps"]), "forward_input_tokens": len(t["prompt_ids"]) + len(t["steps"]) - 1,
                "trajectory_id": t["trajectory_id"]}
        clock, identifier = 1000.1, 64
        for row, replay in zip(batch["rows"], update["replays"]):
            t = row["trajectory"]
            replay["replay_event_id"] = identifier
            events[identifier] = {"event_id": identifier, "phase": "causal-replay", "dispatched": True,
                "status": "complete", "started": clock, "ended": clock + .01, "seconds": .01,
                "input_tokens": len(t["original_ids"]) - 1, "checkpointing": True,
                "trajectory_id": t["trajectory_id"], "update_batch_id": batch["id"], "deadline": 1600.}
            identifier += 1; clock += .01
            if replay["group_advantage"]:
                replay["backward_event_id"] = identifier
                replay["backward_seconds"] = .01
                events[identifier] = {"event_id": identifier, "phase": "ddis-backward", "dispatched": True,
                    "status": "complete", "started": clock, "ended": clock + .01, "seconds": .01,
                    "trajectory_id": t["trajectory_id"], "update_batch_id": batch["id"], "deadline": 1600.}
                identifier += 1; clock += .01
            else:
                replay["backward_event_id"] = None
        update["whole_replay_backward_seconds"] = clock - 1000.1
        update["optimizer_event_id"] = identifier
        update["batch_finished_monotonic"] = clock + .01
        events[identifier] = {"event_id": identifier, "phase": "optimizer-commit", "dispatched": True,
            "status": "complete", "started": clock, "ended": clock + .01, "seconds": .01,
            "update_batch_id": batch["id"], "deadline": 1600.}
        self.assertEqual(a["summary"], original.summary(batch, batch["parent_ids"], 8))
        for row in batch["rows"]:
            original.trajectory(row["trajectory"], row, batch, expected_seed=row["trajectory"]["seed"], events=events)
        self.assertTrue(original.validate_update(update, batch, a["summary"], gate=update["numerical_gate"]["gate"],
                                                synthetic=False, events=events, require_modern=True))
        self.assertEqual("CONFORMANT_SAVED_REPLAY", analyze(a, d)["status"])
        self.rejected(lambda a, d: a["update"]["replays"][0].update(backward_event_id="uuid-is-not-ledger-id"))

    def test_frozen_consumer_group_weight_differential(self):
        fn = frozen_function("tools/arc_qwen_rlvr004_20261013/release/terminal-consumer/consumer/audit_checks.py",
                             "group_weight_evidence", {"need": require, "finite": adapter._finite, "math": math})
        for i, replay in enumerate(self.audit["update"]["replays"]):
            value = fn(replay, self.audit["batch"]["rows"][i], self.audit["summary"]["groups"][i // 8], 6)
            self.assertAlmostEqual(value["detached_DDIS_loss"], replay["detached_DDIS_loss"], places=7)

    def test_full_upstream_and_frozen_native_loss_differential(self):
        import torch
        from tools.arc2_agent_factory3_bridge_20261014.proof import baseline_math
        for successes in ((1, 2, 4, 6, 0, 8, 3, 5), (1, 0, 0, 0, 0, 0, 0, 0), (1,) * 8):
            for gap in (0., .001):
                a, d = synthetic_audit(successes, logp_gap=gap)
                c = context(a, d)
                prepared = prepare_batch(a["batch"], c.batch_context)
                pi = {r["trajectory_id"]: torch.tensor(r["log_pi"], requires_grad=True) for r in a["update"]["replays"]}
                full = compute_loss(prepared, pi)
                result = analyze(a, d)
                self.assertEqual("CONFORMANT_SAVED_REPLAY", result["status"], result)
                self.assertAlmostEqual(float(full.loss_unscaled.detach()), result["replay"]["loss_unscaled"], places=7)
                from torch.nn.utils.rnn import pad_sequence
                tensors = list(pi.values())
                native, diagnostics = baseline_math().ddis_loss(
                    pad_sequence(tensors, batch_first=True),
                    pad_sequence([torch.tensor(r["log_mu"]) for r in a["update"]["replays"]], batch_first=True),
                    pad_sequence([torch.ones(len(r["log_pi"]), dtype=torch.bool) for r in a["update"]["replays"]], batch_first=True),
                    torch.tensor([r["reward"] for r in a["batch"]["rows"]], dtype=torch.float32),
                    [r["parent_id"] for r in a["batch"]["rows"]], torch.ones(64, dtype=torch.bool),
                    [c.batch_context.policy_version] * 64)
                self.assertAlmostEqual(float(native.detach()), result["replay"]["loss_unscaled"], places=7)
                self.assertEqual(a["summary"]["mixed_groups"], diagnostics["mixed_groups"])

    def test_optional_leaf_gradient_is_not_model_gradient(self):
        result = analyze(self.audit, self.doc, leaf_logp_derivative=True)
        leaf = result["replay"]["leaf_logp_derivative"]
        self.assertEqual("fresh-CPU-selected-logp-leaf-derivative-only", leaf["kind"])
        self.assertGreater(leaf["nonzero_tokens"], 0)
        self.assertGreater(leaf["absolute_sum"], 0)
        self.assertFalse(leaf["original_logits_gradient"])
        self.assertFalse(leaf["model_or_LoRA_gradient"])

    def test_zero_signal_has_no_torch_loss_or_replay(self):
        for successes in ((0,) * 8, (8,) * 8, (0, 8) * 4):
            a, d = synthetic_audit(successes)
            with patch("tools.arc2_abc_continuation_20261014.streaming.StreamingLossSession", side_effect=AssertionError("unreachable")):
                result = analyze(a, d)
            self.assertEqual("CONFORMANT_ZERO_SIGNAL", result["status"], result)
            self.assertTrue(result["conformance_complete"])
            self.assertEqual(0, result["replay"]["required"])
            self.assertIsNone(result["replay"]["loss_unscaled"])

    def test_all_four_disjoint_batch_indices(self):
        for index in range(4):
            a, d = synthetic_audit(batch_index=index)
            self.assertEqual("CONFORMANT_SAVED_REPLAY", analyze(a, d)["status"])

    def test_missing_originals_are_unknown_not_zero(self):
        for mutation in (lambda a: a.pop("batch"), lambda a: a.update(update=None),
                         lambda a: a["batch"]["rows"][0].update(trajectory=None),
                         lambda a: a["update"]["replays"].pop(),
                         lambda a: a["update"]["replays"][0].pop("detached_DDIS_loss"),
                         lambda a: a["update"]["replays"][0].pop("log_pi"),
                         lambda a: a["batch"]["rows"][0]["trajectory"].pop("original_ids"),
                         lambda a: a["batch"]["rows"][0]["trajectory"]["steps"][0].pop("support")):
            a = deepcopy(self.audit); mutation(a)
            r = analyze(a, self.doc)
            self.assertEqual("MISSING_ORIGINAL_ARTIFACTS", r["status"], r)
            self.assertFalse(r["conformance_complete"])
            self.assertNotEqual("CONFORMANT_ZERO_SIGNAL", r["status"])

    def test_compact_terminal_report_not_reconstructible(self):
        r = analyze({"format": "irisx/owned-rl-batched-offline-validation-v1", "status": "COMPLETE"}, self.doc)
        self.assertEqual("MISSING_ORIGINAL_ARTIFACTS", r["status"])
        self.assertIsNone(r["coverage"])

    def incomplete(self):
        a = deepcopy(self.audit)
        a["batch"]["rows"][3].update(eligible=False, reward=None, status="infrastructure-excluded", reason="private detail")
        for row in a["batch"]["rows"][4:]:
            row.update(eligible=False, reward=None, status="not-reached", trajectory=None)
        a["batch"].update(all_slots_reached=False, stop_reason="incomplete-audit")
        a.update(status="incomplete-audit", update=None)
        a["summary"] = adapter._summary(a["batch"], a["parent_ids"])
        return a

    def test_incomplete_preserves_null_rewards(self):
        a = self.incomplete()
        result = analyze(a, self.doc)
        self.assertEqual("INCOMPLETE_AUDIT", result["status"])
        self.assertFalse(result["conformance_complete"])
        self.assertFalse(result["coverage"]["complete"])
        self.assertEqual(3, result["coverage"]["eligible_mean_denominator"])
        self.assertEqual(60, result["coverage"]["not_reached"])
        self.assertIsNone(result["groups"][0]["pass_at_8"])
        self.assertNotIn("private detail", json.dumps(result))
        a["status"] = "zero-signal"
        self.assertEqual("REJECTED", analyze(a, self.doc)["status"])

    def test_unattempted_sparse_original_batch(self):
        a = deepcopy(self.audit)
        a["batch"] = {"sweep": 0, "batch_index": 0, "parent_ids": a["parent_ids"], "policy_version": None,
                      "planned_attempts": 64, "rows": [{"parent_id": p, "slot": s, "trajectory": None,
                        "reward": None, "eligible": False, "status": "not-reached", "reason": "not-entered"}
                        for p in a["parent_ids"] for s in range(8)],
                      "closed": True, "all_slots_reached": False, "fatal_native_state": False}
        a.update(status="not-reached", update=None, policy_before=None, policy_after=None, admission=None)
        a["summary"] = adapter._summary(a["batch"], a["parent_ids"])
        result = analyze(a, self.doc)
        self.assertEqual("NOT_REACHED", result["status"], result)
        self.assertIsNone(result["coverage"]["eligible_mean_reward"])
        self.assertEqual(0, result["coverage"]["eligible_mean_denominator"])

    def test_fatal_is_distinct_and_error_is_redacted(self):
        a = deepcopy(self.audit)
        a["batch"]["fatal_native_state"] = "private device exception 987-secret"
        a["summary"]["fatal_native_state"] = a["batch"]["fatal_native_state"]
        a.update(status="failed-no-safe-continuation", policy_after=None, error="private traceback")
        result = analyze(a, self.doc)
        self.assertEqual("FATAL_NATIVE_STATE", result["status"])
        self.assertFalse(result["conformance_complete"])
        self.assertNotIn("private", json.dumps(result))

    def numeric_failure(self, *, gap=.1):
        a, d = synthetic_audit(logp_gap=gap)
        a.update(status="numeric-nonadmission-no-update", policy_after={**a["policy_before"], "generation_epoch": 2})
        u = a["update"]
        u.update(status=a["status"], optimizer_committed=False, optimizer_dispatched=False)
        u["numerical_gate"].update(admitted=False, failures=[r["parent_id"] + ":ratio-gap" for r in u["replays"]])
        return a, d

    def test_numeric_nonadmission_preserves_status_without_streaming(self):
        a, d = self.numeric_failure()
        with patch("tools.arc2_abc_continuation_20261014.streaming.StreamingLossSession", side_effect=AssertionError("unreachable")):
            r = analyze(a, d)
        self.assertEqual("NUMERIC_NONADMISSION", r["status"], r)
        self.assertFalse(r["conformance_complete"])
        self.assertFalse(r["replay"]["probability_values_passed"])
        self.assertIsNone(r["replay"]["loss_unscaled"])
        a["update"]["replays"][0]["detached_DDIS_loss"] += .01
        self.assertEqual("REJECTED", analyze(a, d)["status"])

    def test_failed_update_prefix_stays_unknown(self):
        a = deepcopy(self.audit)
        a.update(status="incomplete-audit", error="private recoverable failure")
        a["update"].update(status="update-failed", optimizer_committed=False,
                           replays=a["update"]["replays"][:3], error="private update error")
        r = analyze(a, self.doc)
        self.assertEqual("UPDATE_FAILED", r["status"], r)
        self.assertEqual(3, r["replay"]["present"])
        self.assertEqual(0, r["replay"]["checked"])
        self.assertIsNone(r["replay"]["recorded_loss_matches"])
        a["update"]["replays"].reverse()
        self.assertEqual("REJECTED", analyze(a, self.doc)["status"])

    def test_summary_and_status_adversaries(self):
        mutations = [lambda a, d: a["summary"].update(mixed_groups=1),
                     lambda a, d: a["summary"].update(eligible_mean_denominator=63),
                     lambda a, d: a.update(status="zero-signal"),
                     lambda a, d: a["batch"].update(planned_attempts=True),
                     lambda a, d: a["batch"].update(group_size=4),
                     lambda a, d: a["batch"].update(all_slots_reached=False),
                     lambda a, d: a["batch"].update(stop_reason="private-stop"),
                     lambda a, d: a["batch"].update(batch_index=1),
                     lambda a, d: a["batch"]["rows"].reverse(),
                     lambda a, d: a["batch"]["rows"].pop(),
                     lambda a, d: a["batch"]["rows"].append(deepcopy(a["batch"]["rows"][0])),
                     lambda a, d: a["batch"]["rows"][0].update(slot=False),
                     lambda a, d: a["batch"]["rows"][0].update(reward=True),
                     lambda a, d: a["batch"]["rows"][0].update(reward=None),
                     lambda a, d: a["batch"]["rows"][0].update(reward=.5),
                     lambda a, d: a["batch"]["rows"][0].update(status="model-invalid")]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                self.rejected(mutation)

    def test_trajectory_adversaries(self):
        mutations = [lambda t: t.update(identity="d" * 64), lambda t: t.update(policy_version="rl:stale"),
                     lambda t: t.update(generation_epoch=9), lambda t: t.update(record_id="wrong-record"),
                     lambda t: t.update(seed=7), lambda t: t.update(messages_sha256="e" * 64),
                     lambda t: t.update(infrastructure_excluded=True), lambda t: t.update(finish_reason="length"),
                     lambda t: t.update(fatal_native_state="private fatal"),
                     lambda t: t["sampling"].update(cache_mode="full_prefix"),
                     lambda t: t["sampling"].update(top_p=.95), lambda t: t["prompt_ids"].append(20),
                     lambda t: t["original_ids"].append(15), lambda t: t["attention_mask"].__setitem__(0, 0),
                     lambda t: t["origins"].__setitem__(0, "assistant_generated"),
                     lambda t: t["steps"][0].update(position=0),
                     lambda t: t["steps"][0].update(prefix_sha256="f" * 64),
                     lambda t: t["steps"][0].update(log_mu=float("nan")),
                     lambda t: t["steps"][0].update(log_mu=-.1),
                     lambda t: t["steps"][0]["support"].append(30),
                     lambda t: t["steps"][0].update(dfa_state=[3, 1, 0]),
                     lambda t: t.update(format_text="different"), lambda t: t.update(dispatched_forwards=1),
                     lambda t: t.update(cache_discarded=False),
                     lambda t: t["steps"][0].update(actor_forward_index=True),
                     lambda t: t["steps"][0].update(actor_event_id="uuid"),
                     lambda t: t.update(physical_event_ids=["uuid"])]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                self.rejected(lambda a, d: mutation(a["batch"]["rows"][0]["trajectory"]))

    def test_replay_adversaries_including_zero_advantage_groups(self):
        mutations = [lambda r: r.update(trajectory_id="wrong"), lambda r: r.update(parent_id="wrong"),
                     lambda r: r.update(update_batch_id="wrong"), lambda r: r["log_mu"].__setitem__(0, -.5),
                     lambda r: r["log_pi"].append(-1.), lambda r: r["log_pi"].__setitem__(0, float("inf")),
                     lambda r: r["log_pi"].__setitem__(0, -.1),
                     lambda r: r.update(original_token_replay=False), lambda r: r.update(prompt_and_tool_loss_masked=False),
                     lambda r: r.update(training_mode=False), lambda r: r.update(cache_mode="full_prefix"),
                     lambda r: r.update(group_advantage=0.), lambda r: r.update(eligible_group_size=7),
                     lambda r: r.update(mixed_group_count=7), lambda r: r.update(original_generated_length=1),
                     lambda r: r.update(gradient_weight=.2), lambda r: r.update(detached_DDIS_loss=.2),
                     lambda r: r["all_tokens"].update(tokens=True), lambda r: r["nonforced_tokens"].update(max_abs_gap=.1),
                     lambda r: r.update(forced_tokens=1), lambda r: r.update(seconds=-1),
                     lambda r: r.update(peak_memory_bytes=None), lambda r: r.update(backward_seconds=-1)]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                self.rejected(lambda a, d: mutation(a["update"]["replays"][0]))
        self.rejected(lambda a, d: a["update"]["replays"][32].update(original_token_replay=False))
        self.rejected(lambda a, d: a["update"]["replays"].reverse())
        self.rejected(lambda a, d: a["update"]["replays"].append(a["update"]["replays"][0]))

    def test_update_adversaries(self):
        mutations = [lambda a, d: a["update"].update(batch_id="wrong"),
                     lambda a, d: a["update"].update(eligible_attempts=63),
                     lambda a, d: a["update"]["groups"][0].update(successes=0),
                     lambda a, d: a["update"].update(optimizer_dispatched=False),
                     lambda a, d: a["update"].update(gradient_norm=0.),
                     lambda a, d: a["update"].update(backward_calls=64),
                     lambda a, d: a["update"].update(gradient_divisor="tokens"),
                     lambda a, d: a["update"]["numerical_gate"].update(admitted=False),
                     lambda a, d: a["update"]["numerical_gate"]["gate"].update(maximum_p95_gap=1.),
                     lambda a, d: a["update"]["numerical_gate"].update(per_trajectory=[]),
                     lambda a, d: a["update"].update(whole_replay_backward_seconds=700.),
                     lambda a, d: a["policy_after"].update(adapter_sha256=a["policy_before"]["adapter_sha256"]),
                     lambda a, d: a["policy_after"].update(source_sha256="d" * 64)]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                self.rejected(mutation)

    def test_context_closed_schema_and_source_binding(self):
        for mutation in (lambda d: d.update(extra=1), lambda d: d.update(audit_sha256="f" * 64),
                         lambda d: d["batch_context"].update(actor_identity="invalid"),
                         lambda d: d["batch_context"]["record_ids"].pop(),
                         lambda d: d["batch_context"]["forbidden_parent_ids"].pop(),
                         lambda d: d["batch_context"]["forbidden_parent_ids"].__setitem__(0, d["batch_context"]["train_parent_ids"][0]),
                         lambda d: d["training"]["record_declarations"][0].update(record_id="other"),
                         lambda d: d["training"].update(source_sha256="invalid"),
                         lambda d: d["policy_before"].update(generation_epoch=True)):
            d = deepcopy(self.doc); mutation(d)
            with self.assertRaises(AuditError):
                context_from_document(d, audit_sha256=self.doc["audit_sha256"])
        c = context(self.audit, self.doc)
        changed = replace(c, declaration_digest="0" * 64)
        self.assertEqual("REJECTED", analyze_audit(self.audit, changed)["status"])
        self.assertEqual("REJECTED", analyze_audit(self.audit, self.doc)["status"])

    def test_declared_training_is_still_unauthenticated(self):
        d = deepcopy(self.doc)
        d["batch_context"]["evidence_kind"] = "declared-training-only"
        r = analyze(self.audit, d)
        self.assertEqual("CONFORMANT_SAVED_REPLAY", r["status"])
        self.assertFalse(r["provenance_authenticated"])
        self.assertFalse(r["model_replay_verified"])
        a = deepcopy(self.audit); a["batch"]["rows"][0]["fixture_only"] = True
        self.assertEqual("REJECTED", analyze(a, d)["status"])

    def test_no_private_identifiers_tokens_grids_or_errors_in_output(self):
        result = analyze(self.audit, self.doc, leaf_logp_derivative=True)
        raw = json.dumps(result)
        for forbidden in ("fabricated-parent", "fabricated-record", "fabricated-trajectory", "fabricated-batch",
                          "generated_ids", "original_ids", "format_text", "log_mu", "log_pi", "dfa_state"):
            self.assertNotIn(forbidden, raw)
        self.assertLess(len(raw), 8000)
        a = deepcopy(self.audit); a["batch"]["rows"][0]["trajectory"]["private_error"] = "SECRET"
        self.assertNotIn("SECRET", json.dumps(analyze(a, self.doc)))

    def test_source_drift_is_fail_closed_without_changing_frozen_files(self):
        original = Path.read_bytes
        def changed(path):
            data = original(path)
            return data + b"# drift" if str(path).endswith("rl_session/actor.py") else data
        with patch.object(Path, "read_bytes", changed):
            r = analyze(self.audit, self.doc)
        self.assertEqual("REJECTED", r["status"])
        self.assertEqual(["FROZEN_SOURCE_DRIFT"], r["issues"])
        self.assertEqual(adapter.PIN_MANIFEST_SHA256, adapter.verify_sources())

    def test_no_model_runtime_imports_and_zero_signal_no_torch(self):
        code = '''import sys
from tools.arc2_abc_continuation_20261014.fixtures import synthetic_audit
from tools.arc2_abc_continuation_20261014.audit import context_from_document, analyze_audit
a,d=synthetic_audit((0,)*8)
r=analyze_audit(a,context_from_document(d,audit_sha256=d['audit_sha256']))
assert r['status']=='CONFORMANT_ZERO_SIGNAL'
assert 'torch' not in sys.modules
assert not any(k.startswith(('transformers','peft','safetensors','rl_session','owned_runtime')) for k in sys.modules)
'''
        outcome = subprocess.run([sys.executable, "-c", code], cwd=adapter.ROOT, text=True, capture_output=True)
        self.assertEqual(0, outcome.returncode, outcome.stderr)

    def test_caller_inputs_are_not_mutated(self):
        original = deepcopy((self.audit, self.doc))
        analyze(self.audit, self.doc, leaf_logp_derivative=True)
        self.assertEqual(original, (self.audit, self.doc))


if __name__ == "__main__":
    unittest.main()
