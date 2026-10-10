"""Synthetic-only provider checks; no model mounts, torch, training or GPU use."""
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, patch

from tools.arc_consolidated_20261010 import assets, model_provider as mp
from tools.arc_consolidated_20261010.ledger import BindingMismatch, Ledger, digest as ledger_digest
from tools.arc_consolidated_20261010.tests.support import TemporaryDirectory

arc_typed_ir = assets.load_legacy("arc_typed_ir")


ENVIRONMENT = "e" * 64
GRAMMAR = {"version": "synthetic-test-only", "max_steps": 3,
           "operations": {"identity": {}, "flip_horizontal": {}, "flip_vertical": {}}}
PLAN_TEXT = '{"steps":[{"op":"identity"}]}'


def tasks():
    return [{"task_id": "synthetic_" + str(i),
             "demos": [{"input": [[i]], "output": [[i]]}]} for i in range(8)]


def plan(**kwargs):
    return mp.build_study_plan(tasks(), grammar=GRAMMAR,
                               environment_sha256=ENVIRONMENT, **kwargs)


def validate_compile(value):
    admitted = arc_typed_ir.validate_plan(value)
    arc_typed_ir.compile_plan(admitted)  # Bounded AST data only, never executed.
    return admitted


def roots_and_feedback(study):
    roots, feedback = {}, {}
    for spec in study.calls:
        if spec.stage != "root":
            continue
        request = mp.materialize_request(study, spec)
        root = mp.freeze_root(request, PLAN_TEXT, validate_compile)
        roots[spec.call_id] = root
        feedback[spec.call_id] = {"status": "verified", "demo_matches": [True],
                                  "response_sha256": root.response_sha256}
    return roots, feedback


def payload(request):
    return json.loads(json.loads(request.messages_json)[1]["content"])


class SyntheticBackend:
    def __init__(self, *, mutate=None, fail=False):
        self.calls = []
        self.mutate = mutate
        self.fail = fail
        self.closed = False
        self.model_loaded = False
        self.trace = ["tokenizer_initialized"]

    def encode(self, messages):
        self.trace.append("tokenized")
        return list(mp.canonical(messages).encode())

    def ensure_model_loaded(self):
        if not self.model_loaded:
            self.trace.append("model_loaded")
            self.model_loaded = True

    def generate(self, prepared, *, deadline_monotonic):
        if not self.model_loaded:
            raise AssertionError("model load acknowledgement missing")
        self.trace.append("generated")
        self.calls.append(prepared)
        if self.fail:
            raise RuntimeError("injected unknown response")
        result = {"request_sha256": prepared.sha256,
                  "model_sha256": prepared.request.model_sha256,
                  "environment_sha256": prepared.request.environment_sha256,
                  "text": PLAN_TEXT, "prompt_tokens": prepared.prompt_tokens,
                  "output_tokens": 1, "output_token_ids": [42], "finish_reason": "stop"}
        if self.mutate:
            self.mutate(result, prepared)
        return result

    def close(self):
        self.closed = True
        return {"model_released": True, "descendants_stopped": True, "owned_descendants": []}


class DictDefaultTokenizerFixture:
    """Synthetic API-shape regression, not an actual tokenizer acceptance."""
    def __init__(self, ids):
        self.ids, self.calls = ids, []

    def apply_chat_template(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if kwargs.get("return_dict", True):
            return {"input_ids": self.ids, "attention_mask": [1] * len(self.ids)}
        return self.ids


class ModelProviderTests(unittest.TestCase):
    def owner(self, backend=None, **kwargs):
        return mp.SingleModelOwner(lambda: backend or SyntheticBackend(), enabled=True,
                                   environment_sha256=ENVIRONMENT,
                                   execution_mode="synthetic-test", **kwargs)

    def test_exact_frozen_80_call_structure_and_pairing(self):
        study = plan()
        self.assertEqual(len(study.calls), 80)
        self.assertEqual(len({c.call_id for c in study.calls}), 80)
        self.assertEqual([sum(c.stage == s for c in study.calls)
                          for s in ("root", "feedback", "memory")], [16, 32, 32])
        self.assertEqual(study.sha256, plan().sha256)
        self.assertNotEqual(study.sha256, plan(seed=1).sha256)
        for stage in ("feedback", "memory"):
            for root in study.calls[:16]:
                pair = [c for c in study.calls if c.root_id == root.call_id and c.stage == stage]
                self.assertEqual(len(pair), 2)
                self.assertEqual(pair[0].seed, pair[1].seed)
        with self.assertRaises(FrozenInstanceError):
            study.calls[0].arm = "changed"
        snapshot = study.tasks_json
        original = tasks()
        separate = mp.build_study_plan(original, grammar=GRAMMAR, environment_sha256=ENVIRONMENT)
        original[0]["demos"][0]["input"][0][0] = 9
        self.assertEqual(separate.tasks_json, snapshot)

    def test_task_rejection_at_every_depth_and_grid_types(self):
        for prohibited in ("test", "QUERY", " gold ", "solutions"):
            for sample in ({"task_id": "t", "demos": [], prohibited: []},
                           {"task_id": "t", "demos": [{"input": [[0]], "output": [[0]],
                                                        "metadata": {prohibited: []}}]}):
                with self.subTest(prohibited=prohibited), self.assertRaises(mp.ModelContractError):
                    mp.validate_demos_task(sample)
        for invalid in ([[True]], [[-1]], [[10]], [[0], [0, 1]], [[0.0]], []):
            with self.subTest(invalid=invalid), self.assertRaises(mp.ModelContractError):
                mp.validate_demos_task({"task_id": "t", "demos": [{"input": invalid, "output": [[0]]}]})

    def test_profile_rejects_missing_duplicate_and_ninth_task(self):
        for invalid in (tasks()[:7], tasks() + [tasks()[0]], tasks()[:7] + [tasks()[0]]):
            with self.assertRaises(mp.ModelContractError):
                mp.build_study_plan(invalid, grammar=GRAMMAR, environment_sha256=ENVIRONMENT)

    def test_matched_feedback_changes_only_feedback(self):
        study = plan()
        roots, feedback = roots_and_feedback(study)
        true, redacted = study.calls[16:18]
        left = payload(mp.materialize_request(study, true, frozen_roots=roots, feedback_by_root=feedback))
        right = payload(mp.materialize_request(study, redacted, frozen_roots=roots, feedback_by_root=feedback))
        self.assertNotEqual(left.pop("feedback"), right.pop("feedback"))
        self.assertEqual(left, right)
        self.assertEqual(left["parent"], left["history"][0])

    def test_matched_memory_changes_only_memory_and_freezes_parents(self):
        study = plan()
        roots, feedback = roots_and_feedback(study)
        off, on = study.calls[48:50]
        left = payload(mp.materialize_request(study, off, frozen_roots=roots, feedback_by_root=feedback))
        right = payload(mp.materialize_request(study, on, frozen_roots=roots, feedback_by_root=feedback))
        self.assertEqual(left.pop("memory"), [])
        self.assertEqual(len(right.pop("memory")), 2)
        self.assertEqual(left, right)
        self.assertTrue(all(c.root_id in {r.call_id for r in study.calls[:16]}
                            for c in study.calls[16:]))
        roots.pop(study.calls[1].call_id)
        with self.assertRaises(mp.ModelContractError):
            mp.materialize_request(study, on, frozen_roots=roots, feedback_by_root=feedback)

    def test_feedback_and_frozen_roots_bind_original_request_response(self):
        study = plan()
        roots, feedback = roots_and_feedback(study)
        repair = study.calls[16]
        feedback[repair.root_id]["response_sha256"] = "a" * 64
        with self.assertRaises(mp.ModelContractError):
            mp.materialize_request(study, repair, frozen_roots=roots, feedback_by_root=feedback)
        roots, feedback = roots_and_feedback(study)
        changed = plan(seed=9)
        roots[repair.root_id] = mp.freeze_root(mp.materialize_request(changed, changed.calls[0]),
                                              PLAN_TEXT, validate_compile)
        with self.assertRaises(mp.ModelContractError):
            mp.materialize_request(study, repair, frozen_roots=roots, feedback_by_root=feedback)

    def test_legal_three_step_root_is_retained(self):
        study = plan()
        text = '{"steps":[{"op":"flip_horizontal"},{"op":"flip_vertical"},{"op":"identity"}]}'
        root = mp.freeze_root(mp.materialize_request(study, study.calls[0]), text, validate_compile)
        self.assertEqual(root.status, "valid")
        self.assertEqual(len(json.loads(root.plan_json)["steps"]), 3)

    def test_invalid_response_is_digest_only_in_repair_prompt(self):
        study = plan()
        roots, feedback = roots_and_feedback(study)
        bad = "__import__('os').system('untrusted marker')"
        root = mp.freeze_root(mp.materialize_request(study, study.calls[0]), bad, validate_compile)
        roots[root.call_id] = root
        feedback[root.call_id] = {"status": "invalid_plan", "demo_matches": [None],
                                  "response_sha256": root.response_sha256}
        request = mp.materialize_request(study, study.calls[16], frozen_roots=roots, feedback_by_root=feedback)
        self.assertEqual(root.status, "invalid")
        self.assertNotIn("untrusted marker", request.messages_json)
        self.assertIn(root.response_sha256, request.messages_json)
        for invalid in ('{"steps":[],"steps":[]}', '{"steps":[{"op":"identity","gold":0}]}'):
            self.assertEqual(mp.freeze_root(mp.materialize_request(study, study.calls[0]),
                                            invalid, validate_compile).status, "invalid")

    def test_disabled_path_does_not_touch_factory_or_model_paths(self):
        study = plan()
        request = mp.materialize_request(study, study.calls[0])
        factory = Mock(side_effect=AssertionError("factory must remain inert"))
        owner = mp.SingleModelOwner(factory, environment_sha256=ENVIRONMENT)
        with patch.object(Path, "read_bytes", side_effect=AssertionError("no files")), \
             patch.object(Path, "iterdir", side_effect=AssertionError("no model scan")):
            with self.assertRaises(mp.ModelContractError):
                owner.prepare(request)
            with self.assertRaises(mp.ModelContractError):
                mp.G4Backend(model_path="not-scanned", manifest_path="not-read",
                             environment_lock_path="not-read", environment_sha256=ENVIRONMENT)
        factory.assert_not_called()
        self.assertEqual(owner.accounting()["load_count"], 0)
        self.assertTrue(owner.close()["model_owner_stopped"])

    def test_backend_loaded_once_for_preparation_and_dispatch(self):
        backend = SyntheticBackend()
        factory = Mock(return_value=backend)
        owner = mp.SingleModelOwner(factory, enabled=True, environment_sha256=ENVIRONMENT,
                                    execution_mode="synthetic-test")
        study = plan()
        for spec in study.calls[:2]:
            prepared = owner.prepare(mp.materialize_request(study, spec))
            result = owner.dispatch(prepared, deadline_monotonic=time.monotonic() + 10)
            self.assertEqual(result["prompt_tokens"], prepared.prompt_tokens)
            self.assertFalse(result["truncated"])
        factory.assert_called_once()
        self.assertEqual(owner.accounting()["load_count"], 1)
        self.assertEqual(owner.accounting()["physical_calls_attempted"], 2)
        self.assertFalse(owner.accounting()["vm_billing_stopped"])
        self.assertTrue(owner.close()["model_owner_stopped"])
        self.assertTrue(backend.closed)
        with self.assertRaises(mp.ModelContractError):
            owner.prepare(mp.materialize_request(study, study.calls[2]))

    def test_generic_backend_cannot_claim_production_g4(self):
        owner = mp.SingleModelOwner(SyntheticBackend, enabled=True, environment_sha256=ENVIRONMENT)
        study = plan()
        for _ in range(2):
            with self.assertRaises(mp.ModelContractError):
                owner.prepare(mp.materialize_request(study, study.calls[0]))
        self.assertEqual(owner.accounting()["load_count"], 0)
        self.assertEqual(owner.accounting()["tokenizer_load_count"], 1)

    def test_all_root_tokenization_and_template_audit_precede_model_load(self):
        backend, study = SyntheticBackend(), plan()
        owner = self.owner(backend)
        self.assertFalse(owner.initialize_tokenizer()["model_loaded"])
        requests = [mp.materialize_request(study, spec) for spec in study.calls[:16]]
        prepared, receipt = owner.prepare_group(requests)
        self.assertEqual(receipt["status"], "admitted")
        self.assertEqual(receipt["denominator"], 16)
        roots, feedback = roots_and_feedback(study)
        # A predictable skeleton audit is not admission of the actual repair.
        template = mp.materialize_request(study, study.calls[16], frozen_roots=roots,
                                           feedback_by_root=feedback)
        audited = owner.prepare(template, register=False)
        self.assertEqual(owner.accounting()["load_count"], 0)
        self.assertFalse(backend.model_loaded)
        with self.assertRaises(mp.ModelContractError):
            owner.dispatch(audited, deadline_monotonic=time.monotonic() + 10)
        owner.ensure_model_loaded()
        self.assertEqual(backend.trace[:18], ["tokenizer_initialized"] + ["tokenized"] * 17)
        self.assertEqual(backend.trace[18], "model_loaded")
        owner.dispatch(prepared[0], deadline_monotonic=time.monotonic() + 10)
        self.assertEqual(owner.accounting()["load_count"], 1)

    def test_overflow_excludes_both_matched_arms_without_loading_or_truncating(self):
        backend, study = SyntheticBackend(), plan()
        original_encode = backend.encode
        backend.encode = lambda messages: ([1] * 6145 if json.loads(messages[1]["content"])["memory"]
                                           else original_encode(messages))
        owner = self.owner(backend)
        roots, feedback = roots_and_feedback(study)
        requests = [mp.materialize_request(study, spec, frozen_roots=roots, feedback_by_root=feedback)
                    for spec in study.calls[48:50]]
        prepared, receipt = owner.prepare_group(requests)
        self.assertEqual(prepared, ())
        self.assertEqual(receipt["status"], "excluded_token_budget")
        self.assertEqual((receipt["denominator"], receipt["admitted"]), (2, 0))
        self.assertEqual(receipt["requests"][1]["prompt_tokens"], 6145)
        self.assertFalse(receipt["truncated"])
        fitting_partner = owner.prepare(requests[0])
        with self.assertRaises(mp.ModelContractError):
            owner.dispatch(fitting_partner, deadline_monotonic=time.monotonic() + 10)
        self.assertEqual(owner.accounting()["load_count"], 0)
        self.assertEqual(backend.calls, [])

    def test_failed_tokenizer_or_model_load_cannot_claim_stop_or_retry(self):
        study = plan()
        factory = Mock(side_effect=RuntimeError("injected tokenizer allocation failure"))
        owner = mp.SingleModelOwner(factory, enabled=True, environment_sha256=ENVIRONMENT,
                                    execution_mode="synthetic-test")
        with self.assertRaises(RuntimeError):
            owner.initialize_tokenizer()
        with self.assertRaises(mp.ModelContractError):
            owner.close()
        with self.assertRaises(mp.ModelContractError):
            owner.initialize_tokenizer()
        factory.assert_called_once()
        backend = SyntheticBackend()
        backend.ensure_model_loaded = Mock(side_effect=RuntimeError("unknown partial model allocation"))
        owner = self.owner(backend)
        owner.prepare(mp.materialize_request(study, study.calls[0]))
        with self.assertRaises(RuntimeError):
            owner.ensure_model_loaded()
        with self.assertRaises(mp.ModelContractError):
            owner.ensure_model_loaded()
        with self.assertRaises(mp.ModelContractError):
            owner.close()
        backend.ensure_model_loaded.assert_called_once()
        self.assertFalse(owner.accounting()["model_owner_stopped"])

    def test_failed_call_is_never_reissued_by_owner(self):
        backend = SyntheticBackend(fail=True)
        owner, study = self.owner(backend), plan()
        prepared = owner.prepare(mp.materialize_request(study, study.calls[0]))
        with self.assertRaises(RuntimeError):
            owner.dispatch(prepared, deadline_monotonic=time.monotonic() + 10)
        with self.assertRaises(mp.ModelContractError):
            owner.dispatch(prepared, deadline_monotonic=time.monotonic() + 10)
        self.assertEqual(len(backend.calls), 1)

    def test_cache_identity_binds_native_tokens_sampling_seed_and_environment(self):
        study, owner = plan(), self.owner()
        request = mp.materialize_request(study, study.calls[0])
        prepared = owner.prepare(request)
        for changed in (replace(prepared, input_token_ids=(1, 2)),
                        replace(prepared, request=replace(request, environment_sha256="a" * 64)),
                        replace(prepared, request=replace(request, spec=replace(request.spec, seed=123))),
                        replace(prepared, request=replace(request, sampling=mp.Sampling(max_output_tokens=1)))):
            self.assertNotEqual(prepared.cache_sha256, changed.cache_sha256)
            with self.assertRaises(mp.ModelContractError):
                owner.dispatch(changed, deadline_monotonic=time.monotonic() + 10)

    def test_usage_and_identity_fail_closed(self):
        corruptions = [("prompt_tokens", True), ("output_tokens", float("nan")),
                       ("output_tokens", float("inf")), ("output_tokens", 2049),
                       ("request_sha256", "a" * 64), ("model_sha256", "b" * 64),
                       ("environment_sha256", "c" * 64), ("output_token_ids", [True]),
                       ("finish_reason", "length")]
        study = plan()
        for field, value in corruptions:
            with self.subTest(field=field, value=value):
                owner = self.owner(SyntheticBackend(mutate=lambda r, p: r.update({field: value})))
                prepared = owner.prepare(mp.materialize_request(study, study.calls[0]))
                with self.assertRaises(mp.ModelContractError):
                    owner.dispatch(prepared, deadline_monotonic=time.monotonic() + 10)
                self.assertEqual(owner.accounting()["physical_calls_attempted"], 1)

    def test_invalid_deadline_and_prompt_tokens_prevent_generation(self):
        backend, study = SyntheticBackend(), plan()
        owner = self.owner(backend)
        prepared = owner.prepare(mp.materialize_request(study, study.calls[0]))
        for invalid in (True, float("nan"), float("inf"), time.monotonic() - 1,
                        time.monotonic() + 500):
            with self.assertRaises(mp.ModelContractError):
                owner.dispatch(prepared, deadline_monotonic=invalid)
        self.assertEqual(backend.calls, [])
        for ids in ([True], [100352], [], list(range(6145))):
            backend.encode = lambda messages, ids=ids: ids
            with self.assertRaises(mp.ModelContractError):
                self.owner(backend).prepare(mp.materialize_request(study, study.calls[0]))

    def test_g4_encode_explicit_flat_native_ids_without_tokenizer_or_weights_load(self):
        # Bypass all material/loading setup: this tests only encode's API call.
        native = object.__new__(mp.G4Backend)
        native.tokenizer = DictDefaultTokenizerFixture([0, 17, 100351])
        messages = [{"role": "user", "content": "synthetic only"}]
        self.assertIsInstance(native.tokenizer.apply_chat_template(messages), dict)
        self.assertIs(native.encode(messages), native.tokenizer.ids)
        self.assertEqual(native.tokenizer.calls[-1], (messages, {
            "tokenize": True, "add_generation_prompt": True, "enable_thinking": False,
            "return_dict": False, "return_tensors": None, "truncation": False, "padding": False}))
        backend, study = SyntheticBackend(), plan()
        backend.encode = native.encode
        owner = self.owner(backend)
        prepared = owner.prepare(mp.materialize_request(study, study.calls[0]))
        self.assertEqual(prepared.input_token_ids, (0, 17, 100351))
        self.assertEqual(owner.accounting()["physical_calls_attempted"], 0)
        self.assertEqual(owner.accounting()["load_count"], 0)
        self.assertFalse(backend.model_loaded)

    def test_native_id_contract_stays_strict_without_mapping_flatten_or_coercion(self):
        class IntSubclass(int):
            pass
        study = plan()
        for ids in ({"input_ids": [1]}, [[1, 2]], [True], [1.0], ["1"],
                    [-1], [100352], [IntSubclass(1)], [], (), None):
            with self.subTest(ids=ids):
                backend = SyntheticBackend()
                native = object.__new__(mp.G4Backend)
                native.tokenizer = Mock()
                native.tokenizer.apply_chat_template.return_value = ids
                backend.encode = native.encode
                owner = self.owner(backend)
                with self.assertRaises(mp.ModelContractError):
                    owner.prepare(mp.materialize_request(study, study.calls[0]))
                self.assertEqual(owner.accounting()["physical_calls_attempted"], 0)
                self.assertEqual(owner.accounting()["load_count"], 0)

    def test_native_encoding_never_truncates_over_budget_prompt(self):
        study = plan()
        for count in (6144, 6145):
            native = object.__new__(mp.G4Backend)
            native.tokenizer = DictDefaultTokenizerFixture([42] * count)
            backend = SyntheticBackend()
            backend.encode = native.encode
            owner = self.owner(backend)
            request = mp.materialize_request(study, study.calls[0])
            if count == 6144:
                self.assertEqual(owner.prepare(request).prompt_tokens, count)
            else:
                with self.assertRaises(mp.TokenAdmissionError) as caught:
                    owner.prepare(request)
                self.assertEqual((caught.exception.observed, caught.exception.limit), (6145, 6144))
            self.assertEqual(len(native.tokenizer.ids), count)
            self.assertEqual(owner.accounting()["load_count"], 0)
            self.assertEqual(owner.accounting()["physical_calls_attempted"], 0)

    def test_stop_acknowledgement_requires_model_and_descendant_release(self):
        backend, study = SyntheticBackend(), plan()
        owner = self.owner(backend)
        owner.prepare(mp.materialize_request(study, study.calls[0]))
        backend.close = lambda: {"model_released": True, "descendants_stopped": False,
                                 "owned_descendants": [123]}
        with self.assertRaises(mp.ModelContractError):
            owner.close()
        self.assertFalse(owner.accounting()["model_owner_stopped"])

    def test_all_80_calls_have_durable_synthetic_only_reservations(self):
        study, backend = plan(), SyntheticBackend()
        owner = self.owner(backend)
        roots, feedback = {}, {}
        bounds = {"physical_calls": 80, "cpu_checks": 1, "unknown_calls": 1,
                  "prompt_tokens": 80 * 6144, "output_tokens": 80 * 2048,
                  "model_seconds": 80 * 120, "wall_seconds": 1200}
        bindings = {"source": mp.digest("synthetic-test-source"),
                    "task": mp.digest(json.loads(study.tasks_json)), "model": study.model_sha256,
                    "prompt": study.prompt_template_sha256, "sampling": mp.digest({"plan": study.sha256}),
                    "budget": ledger_digest(bounds), "mode": mp.digest("synthetic-test")}
        with TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "synthetic-only", bindings, bounds)
            with ledger.session(session_seconds=120):
                root_group, admission = owner.prepare_group([
                    mp.materialize_request(study, spec) for spec in study.calls[:16]])
                self.assertEqual(admission["admitted"], 16)
                prepared_by_id = {item.request.spec.call_id: item for item in root_group}
                self.assertEqual(owner.accounting()["load_count"], 0)
                for index, spec in enumerate(study.calls):
                    request = mp.materialize_request(study, spec, frozen_roots=roots, feedback_by_root=feedback)
                    if spec.stage != "root" and spec.arm in ("true", "off"):
                        pair, admission = owner.prepare_group([
                            mp.materialize_request(study, member, frozen_roots=roots, feedback_by_root=feedback)
                            for member in study.calls[index:index + 2]])
                        self.assertEqual(admission["admitted"], 2)
                        prepared_by_id.update({item.request.spec.call_id: item for item in pair})
                    prepared = prepared_by_id[spec.call_id]
                    ledger.reserve("model", spec.call_id,
                                   {"prompt_tokens": prepared.prompt_tokens,
                                    "output_tokens": request.sampling.max_output_tokens,
                                    "model_seconds": 120}, metadata=prepared.reservation())
                    # Evidence that dispatch occurs only after a durable reservation.
                    self.assertEqual(ledger.operation(spec.call_id)["status"], "reserved")
                    result = owner.dispatch(prepared, deadline_monotonic=time.monotonic() + 10)
                    ledger.record_response(spec.call_id, result)
                    ledger.finish(spec.call_id, {key: result[key] for key in
                                                ("prompt_tokens", "output_tokens", "model_seconds")})
                    if spec.stage == "root":
                        root = mp.freeze_root(request, result["text"], validate_compile)
                        roots[spec.call_id] = root
                        feedback[spec.call_id] = {"status": "verified", "demo_matches": [True],
                                                 "response_sha256": root.response_sha256}
                summary = ledger.summary()
                self.assertEqual(summary["charged"]["physical_calls"], 80)
                self.assertEqual(summary["operation_states"]["complete"], 80)
                self.assertEqual(len(backend.calls), 80)
                self.assertEqual(sum(len(c.request.spec.attribution_arms) for c in backend.calls), 160)
                self.assertTrue(owner.close()["model_owner_stopped"])
            with self.assertRaises(BindingMismatch):
                with Ledger(Path(directory) / "synthetic-only",
                            {**bindings, "mode": mp.digest("g4")}, bounds).session(session_seconds=10):
                    pass


if __name__ == "__main__":
    unittest.main()
