"""Offline CPU contract tests. No model weights, HF imports, GPU, or paid work.

Literal fake backends test ordering/accounting and negative contracts. They do
not claim CUDA/BF16/PEFT numerical or architecture quality verification.
"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools import arc_next_models as models
from tools import arc_next_training as training


def demo_tasks():
    return {f"{i:08x}": {"train": [
        {"input": [[1, 0]], "output": [[0, 1]]},
        {"input": [[2, 0]], "output": [[0, 2]]},
        {"input": [[3, 0]], "output": [[0, 3]]},
    ]} for i in range(1, 6)}


class FakeTokenizer:
    def apply_chat_template(self, messages, *, add_generation_prompt=False, tokenize=False, **kwargs):
        text = "".join("<" + message["role"] + ">" + message["content"] + "</" + message["role"] + ">"
                       for message in messages)
        if add_generation_prompt:
            text += "<assistant>"
        return self.encode(text) if tokenize else text

    def encode(self, text, add_special_tokens=False):
        return [ord(c) for c in text]


class FakeBackend:
    def __init__(self, clock=None):
        self.calls, self.value, self.clock = [], 0, clock

    def step(self, row):
        self.calls.append(row["row_id"])
        self.value += 1
        if self.clock is not None:
            self.clock[0] += 1
        return {"loss": 1 / self.value, "seconds": 0.25, "finite_gradients": True,
                "optimizer_updates": 1, "changed_adapter_tensors": 1, "adam_step": self.value}


def token_row(i=0, input_tokens=8, supervised_tokens=3):
    return {"row_id": str(i), "task_id": "00000001", "partition": "train",
            "input_tokens": input_tokens, "supervised_tokens": supervised_tokens,
            "input_ids": list(range(input_tokens)), "labels": [-100] * (input_tokens - supervised_tokens) + [1] * supervised_tokens}


class TrainingMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data, self.manifest = self.root / "training-demonstrations.json", self.root / "training-manifest.json"
        self.tasks = demo_tasks()
        models.write_json(self.data, self.tasks)
        self.receipt = training.write_training_manifest(self.data, list(self.tasks), self.manifest)

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_source_and_grouped_split_roundtrip(self):
        tasks, manifest = training.load_training_material(self.data, self.manifest)
        self.assertEqual(tasks, self.tasks)
        split = manifest["task_partition"]
        self.assertFalse(set(split["train"]) & set(split["dev"]))
        self.assertEqual(set(split["train"]) | set(split["dev"]), set(tasks))
        self.assertEqual(split, training.task_group_split(list(reversed(tasks))))

    def test_explicit_parent_partitions_preserved(self):
        manifest = training.write_training_manifest(
            self.data, list(self.tasks), self.manifest,
            train_task_ids=list(self.tasks)[:3], dev_task_ids=list(self.tasks)[3:])
        self.assertEqual(manifest["task_partition"]["train"], list(self.tasks)[:3])
        self.assertEqual(manifest["task_partition"]["dev"], list(self.tasks)[3:])

    def test_raw_test_data_forbidden_not_silently_stripped(self):
        for key in ("test", "evaluation", "solutions"):
            bad = demo_tasks()
            bad["00000001"][key] = [{"input": [[9]], "output": [[8]]}]
            models.write_json(self.data, bad)
            with self.assertRaisesRegex(models.ContractError, "demonstrations only"):
                training.write_training_manifest(self.data, list(bad), self.manifest)

    def test_answer_paths_fail_before_file_read(self):
        with self.assertRaisesRegex(models.ContractError, "source paths"):
            training.load_training_material(self.root / "arc-agi_evaluation_solutions.json", self.manifest)

    def test_source_revision_and_allowlist_rejected(self):
        with self.assertRaises(models.ContractError):
            training.write_training_manifest(self.data, list(self.tasks), self.manifest, source_revision="main")
        with self.assertRaises(models.ContractError):
            training.write_training_manifest(self.data, list(self.tasks)[:-1], self.manifest)

    def test_changed_material_is_detected(self):
        self.tasks["00000001"]["train"][0]["input"][0][0] = 8
        models.write_json(self.data, self.tasks)
        with self.assertRaisesRegex(models.ContractError, "hash changed"):
            training.load_training_material(self.data, self.manifest)

    def test_grid_invalid_types_and_shapes_rejected(self):
        for grid in ([[True]], [[10]], [[1], [1, 2]], [], [[]], [[0]] * 31):
            with self.subTest(grid=grid), self.assertRaises(models.ContractError):
                training._grid(grid)

    def test_lodo_rows_exclude_target_demo_and_group_before_augmentation(self):
        rows = training.build_training_rows(self.tasks, self.receipt,
                                            train_augmentations=("identity", "rotate90"))
        self.assertEqual(len(rows["train"]), len(self.receipt["task_partition"]["train"]) * 6)
        self.assertEqual(len(rows["dev"]), len(self.receipt["task_partition"]["dev"]) * 3)
        for partition, values in rows.items():
            for row in values:
                self.assertIn(row["task_id"], self.receipt["task_partition"][partition])
                self.assertNotIn(row["held_out_demonstration"], row["visible_demonstration_indices"])
                self.assertEqual(len(row["visible_demonstration_indices"]), 2)
                self.assertEqual([m["role"] for m in row["messages"]], ["user"])
                self.assertEqual(row["partition"], partition)
        self.assertEqual(rows, training.build_training_rows(self.tasks, self.receipt,
                                                            train_augmentations=("identity", "rotate90")))

    def test_native_completion_mask_is_exact(self):
        rows = training.build_training_rows(self.tasks, self.receipt)["train"]
        tokens, excluded = training.tokenize_rows(rows, FakeTokenizer(), 4096)
        self.assertFalse(excluded)
        for row in tokens:
            boundary = row["prompt_tokens"]
            self.assertEqual(row["labels"][:boundary], [-100] * boundary)
            self.assertEqual(row["labels"][boundary:], row["input_ids"][boundary:])
            self.assertGreater(row["supervised_tokens"], 0)

    def test_oversized_whole_rows_are_excluded_never_truncated(self):
        rows = training.build_training_rows(self.tasks, self.receipt)["train"]
        accepted, excluded = training.tokenize_rows(rows, FakeTokenizer(), 8)
        self.assertFalse(accepted)
        self.assertEqual(len(excluded), len(rows))
        self.assertTrue(all(r["input_tokens"] > 8 for r in excluded))

    def test_granite_native_empty_thinking_prefix_is_masked(self):
        class GraniteBoundaryTokenizer(FakeTokenizer):
            def apply_chat_template(self, messages, *, add_generation_prompt=False, tokenize=False, **kwargs):
                messages = [dict(m, content="<think></think>" + m["content"])
                            if m["role"] == "assistant" and "<think>" not in m["content"] else m for m in messages]
                text = "".join("<|im_start|>" + m["role"] + "\n" + m["content"] + "<|im_end|>\n" for m in messages)
                if add_generation_prompt:
                    text += "<|im_start|>assistant\n<think></think>"
                return self.encode(text) if tokenize else text
        rows = training.build_training_rows(self.tasks, self.receipt)["train"][:1]
        tokenized, excluded = training.tokenize_rows(rows, GraniteBoundaryTokenizer(), 4096)
        self.assertFalse(excluded)
        row = tokenized[0]
        prompt = "".join(chr(token) for token in row["input_ids"][:row["prompt_tokens"]])
        completion = "".join(chr(token) for token in row["labels"] if token != -100)
        self.assertTrue(prompt.endswith("<think></think>"))
        self.assertTrue(completion.startswith(rows[0]["completion"]))
        self.assertNotIn("<think>", completion)
        self.assertEqual(row["completion_rendering_policy"], "native-template")

    def test_exact_native_templates_all_three_completion_boundaries(self):
        try:
            import jinja2
        except ImportError:
            self.skipTest("optional CPU Jinja2 unavailable; fake boundary tests still run")
        fixtures = json.loads((Path(__file__).parent / "fixtures/arc_next_native_templates.json").read_text())
        rows = training.build_training_rows(self.tasks, self.receipt)["train"][:1]
        for key, fixture in fixtures.items():
            with self.subTest(model_key=key):
                raw_config = fixture["tokenizer_config_source"]
                self.assertEqual(hashlib.sha256(raw_config.encode()).hexdigest(), models.PINNED_FILES[key]["tokenizer_config.json"])
                conf = json.loads(raw_config)
                if "chat_template.jinja" in models.PINNED_FILES[key]:
                    self.assertEqual(fixture["template_sha256"], models.PINNED_FILES[key]["chat_template.jinja"])
                else:
                    self.assertEqual(fixture["template"], conf["chat_template"])
                from jinja2.sandbox import ImmutableSandboxedEnvironment
                # Exact HF 5.8.1 compiler whitespace settings, verified against
                # the pinned released wheel; these templates have no generation blocks.
                env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True,
                                                    extensions=["jinja2.ext.loopcontrols"])
                env.globals["raise_exception"] = lambda message: (_ for _ in ()).throw(ValueError(message))
                template = env.from_string(fixture["template"])
                class NativeTemplateTokenizer(FakeTokenizer):
                    def apply_chat_template(self, messages, *, add_generation_prompt=False, tokenize=False, **kwargs):
                        text = template.render(messages=messages, add_generation_prompt=add_generation_prompt,
                                               enable_thinking=False, bos_token=conf.get("bos_token"),
                                               eos_token=conf.get("eos_token"))
                        return self.encode(text) if tokenize else text
                tokenizer = NativeTemplateTokenizer()
                if key == "granite-4.2-8b":
                    prompt = tokenizer.apply_chat_template(rows[0]["messages"], add_generation_prompt=True)
                    naive = tokenizer.apply_chat_template(rows[0]["messages"] + [{"role": "assistant", "content": rows[0]["completion"]}])
                    self.assertTrue(naive.startswith(prompt))
                tokens, excluded = training.tokenize_rows(rows, tokenizer, 4096, model_key=key)
                self.assertFalse(excluded)
                self.assertEqual(len(tokens), 1)
                row = tokens[0]
                supervised_text = "".join(chr(token) for token in row["labels"] if token != -100)
                self.assertTrue(supervised_text.startswith(rows[0]["completion"]))
                self.assertNotIn("<think>", supervised_text)
                if key == "granite-4.2-8b":
                    self.assertEqual(row["completion_rendering_policy"], "native-template")

    def test_template_boundary_merge_fails_closed(self):
        class MergingTokenizer(FakeTokenizer):
            def encode(self, text, add_special_tokens=False):
                values = super().encode(text)
                if text.endswith("</assistant>"):
                    values[0] += 1
                return values
        rows = training.build_training_rows(self.tasks, self.receipt)["train"]
        with self.assertRaisesRegex(models.ContractError, "boundary token merge"):
            training.tokenize_rows(rows, MergingTokenizer(), 4096)


class BudgetAndGuardTests(unittest.TestCase):
    def test_default_run_is_inert_and_does_not_write_or_import_models(self):
        with patch.object(training.multiprocessing, "get_context", side_effect=AssertionError("must not spawn")):
            result = training.run_calibration()
        self.assertEqual(result["status"], "inert")
        self.assertFalse(result["model_imported"])
        script = "import sys; from tools.arc_next_training import run_calibration; run_calibration(); assert 'torch' not in sys.modules; assert 'transformers' not in sys.modules; assert 'peft' not in sys.modules"
        subprocess.run([sys.executable, "-c", script], check=True)

    def test_pilots_need_separate_enable_and_exact_steps(self):
        with self.assertRaisesRegex(models.ContractError, "separate explicit"):
            training.preflight(training.CalibrationConfig(profile="pilot16", budget=training.RunBudget(max_optimizer_steps=16)))
        with self.assertRaisesRegex(models.ContractError, "profile must match"):
            training.preflight(training.CalibrationConfig(budget=training.RunBudget(max_optimizer_steps=128)))
        passed = training.preflight(training.CalibrationConfig(profile="pilot16", enable_pilot=True,
                                                               budget=training.RunBudget(max_optimizer_steps=16)))
        self.assertEqual(passed["budget"]["max_optimizer_steps"], 16)

    def test_execution_switches_reject_truthy_strings_and_integers(self):
        for name in ("enabled", "enable_pilot", "allow_experimental_qwen"):
            for value in ("False", "True", 1, 0, None):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(models.ContractError, "exact booleans"):
                    training.run_calibration(replace(training.CalibrationConfig(), **{name: value}))

    def test_supervisor_cancellation_cleans_worker_and_retains_receipt(self):
        class Process:
            exitcode = None
            def __init__(self):
                self.alive, self.cleaned = False, False
            def start(self):
                self.alive = True
            def join(self, timeout=None):
                if self.alive:
                    raise KeyboardInterrupt("owner cancellation")
            def is_alive(self):
                return self.alive
            def terminate(self):
                self.alive, self.cleaned = False, True
        process = Process()
        with tempfile.TemporaryDirectory() as temp:
            config = training.CalibrationConfig(enabled=True, model_path="/models", training_tasks_path="/data",
                                                training_manifest_path="/manifest", output_dir=temp + "/run",
                                                environment_lock_path="/lock", approved_max_cost_usd=5,
                                                estimated_hourly_cost_usd=10)
            with patch.object(training.multiprocessing, "get_context", return_value=NS(Process=lambda **kwargs: process)):
                with self.assertRaises(KeyboardInterrupt):
                    training.run_calibration(config)
            self.assertTrue(process.cleaned)
            receipt = json.loads((Path(temp) / "run/watchdog-result.json").read_text())
            self.assertEqual(receipt["status"], "cancelled")
            self.assertFalse(receipt["cleanup"]["worker_alive_after_cleanup"])

    def test_budgeted_dev_before_after_are_loss_only_and_never_updates(self):
        class DevBackend(FakeBackend):
            def evaluate(self, row):
                return {"loss": 2.0 if self.value == 0 else 1.0, "seconds": 0.1}
        backend, rows = DevBackend(), [dict(token_row(i), partition="dev") for i in range(10)]
        budget = training.RunBudget(max_eval_rows=4, max_eval_input_tokens=32)
        selected = training.select_evaluation_rows(rows, budget)
        self.assertEqual(len(selected), 2)
        before = training.evaluate_rows(backend, selected, budget, phase="before", start_time=0, clock=lambda: 1)
        self.assertEqual(backend.value, 0)
        backend.value = 2
        after = training.evaluate_rows(backend, selected, budget, phase="after", start_time=0, clock=lambda: 1,
                                       prior_input_tokens=before["cumulative_eval_input_tokens"])
        self.assertEqual(before["supervised_token_weighted_nll"], 2)
        self.assertEqual(after["supervised_token_weighted_nll"], 1)
        self.assertEqual(after["cumulative_eval_input_tokens"], 32)
        self.assertEqual(before["optimizer_updates"], 0)
        self.assertFalse(after["arc_accuracy_measured"])
        self.assertEqual([r["row_id"] for r in before["rows"]], [r["row_id"] for r in after["rows"]])
        with self.assertRaisesRegex(models.ContractError, "token budget"):
            training.evaluate_rows(backend, selected, budget, phase="after", start_time=0, clock=lambda: 1,
                                   prior_input_tokens=32)

    def test_nonfinite_or_boolean_budgets_rejected(self):
        for kwargs in ({"max_wall_seconds": float("inf")}, {"max_wall_seconds": float("nan")},
                       {"max_optimizer_steps": True}, {"max_input_tokens": 0},
                       {"max_sequence_tokens": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(models.ContractError):
                training.validate_budget(training.RunBudget(**kwargs))

    def test_manual_preflight_reports_optional_estimate_without_program_cost_cap(self):
        config = training.CalibrationConfig(enabled=True, model_path="/models", training_tasks_path="/data",
                                            training_manifest_path="/manifest", output_dir="/never-written-output",
                                            environment_lock_path="/lock")
        for ceiling in (None, 1, 5):
            with self.subTest(deprecated_ceiling=ceiling):
                passed = training.preflight(replace(config, approved_max_cost_usd=ceiling,
                                                     estimated_hourly_cost_usd=10))
                self.assertFalse(passed["program_cost_cap_enforced"])
                self.assertEqual(passed["maximum_calibration_compute_estimate_usd"], 5)
                self.assertIn("VM can keep billing", passed["billing_caveat"])
                for key in ("gpu_runtime_verified", "provisions_or_starts_compute",
                            "network_access", "automatic_uploads"):
                    self.assertFalse(passed[key])
        self.assertIsNone(training.preflight(config)["maximum_calibration_compute_estimate_usd"])
        for estimate in (True, 0, float("inf"), float("nan")):
            with self.subTest(estimate=estimate), self.assertRaises(models.ContractError):
                training.preflight(replace(config, estimated_hourly_cost_usd=estimate))

    def test_literal_updates_loss_and_accounting(self):
        backend, events = FakeBackend(), []
        result = training.execute_training_steps(backend, [token_row(0), token_row(1)],
                                                 training.RunBudget(), on_event=events.append)
        self.assertEqual(backend.value, 2)
        self.assertTrue(result["completed_profile"])
        self.assertEqual(result["budget"]["actual_optimizer_updates"], 2)
        self.assertEqual(result["budget"]["reserved_input_tokens"], 16)
        self.assertEqual(result["budget"]["reserved_supervised_tokens"], 6)
        self.assertEqual([e["event"] for e in events], ["step-reserved", "step-completed"] * 2)
        self.assertEqual([s["observation"]["loss"] for s in result["steps"]], [1, .5])

    def test_token_budget_reserves_before_call_not_after(self):
        backend = FakeBackend()
        budget = training.RunBudget(max_input_tokens=12, max_supervised_tokens=6, max_sequence_tokens=8)
        result = training.execute_training_steps(backend, [token_row()], budget)
        self.assertEqual(backend.value, 1)
        self.assertFalse(result["completed_profile"])
        self.assertEqual(result["stop_reason"], "input-token-budget")

    def test_wall_budget_includes_setup_time(self):
        clock, backend = [9], FakeBackend()
        budget = training.RunBudget(max_wall_seconds=10)
        backend.clock = clock
        result = training.execute_training_steps(backend, [token_row()], budget,
                                                 clock=lambda: clock[0], start_time=0)
        self.assertEqual(backend.value, 1)
        self.assertEqual(result["stop_reason"], "wall-clock-budget")

    def test_dev_never_enters_optimizer(self):
        row, backend = token_row(), FakeBackend()
        row["partition"] = "dev"
        with self.assertRaisesRegex(models.ContractError, "only training partition"):
            training.execute_training_steps(backend, [row], training.RunBudget())
        self.assertFalse(backend.calls)

    def test_fake_nonfinite_loss_or_missing_update_is_not_success(self):
        for invalid in ({"loss": float("nan")}, {"finite_gradients": False},
                        {"optimizer_updates": 0}, {"changed_adapter_tensors": 0}):
            class Broken(FakeBackend):
                def step(self, row):
                    return dict(super().step(row), **invalid)
            with self.subTest(invalid=invalid), self.assertRaises(models.ContractError):
                training.execute_training_steps(Broken(), [token_row()], training.RunBudget())

    def test_seeded_schedule_deterministic(self):
        first, second = FakeBackend(), FakeBackend()
        rows = [token_row(i) for i in range(20)]
        training.execute_training_steps(first, rows, training.RunBudget(), seed=18)
        training.execute_training_steps(second, rows, training.RunBudget(), seed=18)
        self.assertEqual(first.calls, second.calls)

    def test_qwen_opt_in_and_no_all_models_profile(self):
        with self.assertRaisesRegex(models.ContractError, "experimental"):
            training.preflight(training.CalibrationConfig(model_key="qwen3.5-9b"))
        with self.assertRaises(models.ContractError):
            training.preflight(training.CalibrationConfig(model_key="all"))

    def test_watchdog_terminates_stalled_worker_and_never_retries(self):
        class Process:
            exitcode = None
            def __init__(self):
                self.alive, self.starts, self.terminates = False, 0, 0
            def start(self):
                self.alive = True
                self.starts += 1
            def join(self, timeout=None):
                pass
            def is_alive(self):
                return self.alive
            def terminate(self):
                self.alive = False
                self.terminates += 1
            def kill(self):
                self.alive = False
        process = Process()
        context = NS(Process=lambda **kwargs: process)
        with tempfile.TemporaryDirectory() as temp:
            config = training.CalibrationConfig(enabled=True, model_path="/models", training_tasks_path="/data",
                                                training_manifest_path="/manifest", output_dir=temp + "/run",
                                                environment_lock_path="/lock", approved_max_cost_usd=5,
                                                estimated_hourly_cost_usd=10)
            with patch.object(training.multiprocessing, "get_context", return_value=context):
                result = training.run_calibration(config)
            self.assertEqual(result["status"], "watchdog-timeout")
            self.assertFalse(result["gpu_runtime_verified"])
            self.assertEqual((process.starts, process.terminates), (1, 1))
            with self.assertRaisesRegex(models.ContractError, "immutable"):
                training.run_calibration(config)


class ModelMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.key = "cpu-fixture"
        self.spec = models.ModelSpec(self.key, "test/fixture", "a" * 40, "Fixture", "fixture", 4, 8,
                                    {"BF16": 8}, {"hidden_size": 2})
        self.files = {
            "config.json": {"architectures": ["Fixture"], "model_type": "fixture", "vocab_size": 4, "hidden_size": 2},
            "tokenizer.json": {"model": {"vocab": {"zero": 0, "one": 1}}, "added_tokens": [{"id": 2, "content": "two"}]},
            "tokenizer_config.json": {"chat_template": "{{ messages }}"},
            "model.safetensors.index.json": {"weight_map": {"model.embed_tokens.weight": "model.safetensors"}},
        }
        for name, data in self.files.items():
            models.write_json(self.root / name, data)
        header = models.canonical({"model.embed_tokens.weight": {"dtype": "BF16", "shape": [4, 2], "data_offsets": [0, 16]}})
        (self.root / "model.safetensors").write_bytes(struct.pack("<Q", len(header)) + header + bytes(16))
        self.anchors = {p.name: models.file_sha256(p) for p in self.root.iterdir()}
        self.patch_models = patch.dict(models.MODELS, {self.key: self.spec})
        self.patch_files = patch.dict(models.PINNED_FILES, {self.key: self.anchors})
        self.patch_models.start()
        self.patch_files.start()
        models.write_material_manifest(self.root, self.key)

    def tearDown(self):
        self.patch_models.stop()
        self.patch_files.stop()
        self.temp.cleanup()

    def test_full_material_inventory_and_padded_vocabulary(self):
        result = models.validate_material(self.root, self.key)
        self.assertEqual(result["source_parameter_count"], 8)
        self.assertEqual(result["native_embedding_rows"], 4)
        self.assertEqual(result["tokenizer_max_id"], 2)
        self.assertTrue(result["full_native_vocabulary"])
        self.assertFalse(result["gpu_runtime_verified"])

    def test_changed_weights_and_self_declared_manifest_cannot_override_upstream(self):
        path = self.root / "model.safetensors"
        path.write_bytes(path.read_bytes()[:-1] + b"\x01")
        manifest = json.loads((self.root / "irisx-model-material.json").read_text())
        for entry in manifest["files"]:
            if entry["path"] == path.name:
                entry["sha256"] = models.file_sha256(path)
        models.write_json(self.root / "irisx-model-material.json", manifest)
        with self.assertRaisesRegex(models.ContractError, "bytes mismatch"):
            models.validate_material(self.root, self.key)

    def test_unlisted_binary_fallback_rejected(self):
        (self.root / "pytorch_model.bin").write_bytes(b"no pickle")
        with self.assertRaisesRegex(models.ContractError, "unlisted alternative"):
            models.validate_material(self.root, self.key)

    def test_wrong_revision_rejected(self):
        path = self.root / "irisx-model-material.json"
        manifest = json.loads(path.read_text())
        manifest["revision"] = "main"
        models.write_json(path, manifest)
        with self.assertRaisesRegex(models.ContractError, "identity mismatch"):
            models.validate_material(self.root, self.key)

    def test_supplemental_license_is_independently_bound(self):
        content = b"official fixture license"
        expected = {"LICENSE": {"sha256": hashlib.sha256(content).hexdigest(),
                                "size_bytes": len(content), "source_url": "https://example.com/pinned/LICENSE"}}
        with patch.dict(models.SUPPLEMENTAL_FILES, {self.key: expected}):
            with self.assertRaisesRegex(models.ContractError, "missing local"):
                models.write_material_manifest(self.root, self.key)
            (self.root / "LICENSE").write_bytes(content)
            models.write_material_manifest(self.root, self.key)
            result = models.validate_material(self.root, self.key)
            self.assertEqual(result["supplemental_files"][0]["sha256"], expected["LICENSE"]["sha256"])
            (self.root / "LICENSE").write_bytes(b"wrong")
            with self.assertRaisesRegex(models.ContractError, "license bytes mismatch"):
                models.validate_material(self.root, self.key)

    def test_missing_template_shard_or_inventory_member_rejected(self):
        (self.root / "tokenizer_config.json").unlink()
        with self.assertRaisesRegex(models.ContractError, "missing local"):
            models.validate_material(self.root, self.key)

    def test_header_overlaps_rejected(self):
        path = self.root / "overlap.safetensors"
        header = models.canonical({"a": {"dtype": "BF16", "shape": [1], "data_offsets": [0, 2]},
                                   "b": {"dtype": "BF16", "shape": [1], "data_offsets": [0, 2]}})
        path.write_bytes(struct.pack("<Q", len(header)) + header + bytes(2))
        with self.assertRaisesRegex(models.ContractError, "gaps or overlaps"):
            models._safetensor_inventory(path)

    def test_real_model_anchors_match_independent_source_lock(self):
        lock = json.loads((Path(__file__).resolve().parents[1] / "research/arc-next-line/model-source-lock.json").read_text())
        # Schema independent assertion: every pinned full shard SHA must occur in
        # the separately reviewed upstream lock, never an unanchored local hash.
        serialized = json.dumps(lock)
        for key, spec in models.MODELS.items():
            if key == self.key:
                continue
            self.assertIn(spec.repository, serialized)
            self.assertIn(spec.revision, serialized)
            shards = [sha for name, sha in models.PINNED_FILES[key].items() if name.endswith(".safetensors")]
            self.assertTrue(shards)
            self.assertTrue(all(sha in serialized for sha in shards))


class ExportRoundTripTests(unittest.TestCase):
    """Literal in-memory adapter/save/reload doubles, not actual HF/torch evidence."""
    def test_export_restores_and_reloads_exact_adapter_and_tokenizer(self):
        class Tensor:
            shape, dtype = (1,), "fake-float32"
            def __init__(self, value): self.value = value
            def detach(self): return self
            def cpu(self): return self
            def contiguous(self): return self
            def numel(self): return 1
            def view(self, dtype): return self
            def numpy(self): return NS(tobytes=lambda: struct.pack("<f", self.value))
        torch = NS(uint8="u8", isfinite=lambda value: NS(all=lambda: True))
        tokenizer = NS(get_vocab=lambda: {"x": 0}, apply_chat_template=lambda *a, **kw: [0])
        def save_tokenizer(path):
            models.write_json(Path(path) / "tokenizer.json", {"fake": "tokenizer"})
        tokenizer.save_pretrained = save_tokenizer
        state, restores = {"lora_A.weight": Tensor(2.0)}, []
        def save_model(path, safe_serialization):
            self.assertTrue(safe_serialization)
            models.write_json(Path(path) / "adapter_model.safetensors", {k: v.value for k, v in state.items()})
            models.write_json(Path(path) / "adapter_config.json", {"fake": "adapter"})
        def set_state(model, value):
            state.clear()
            state.update(value)
            restores.append(next(iter(value.values())).value)
        def load_file(path, device):
            return {key: Tensor(value) for key, value in json.loads(Path(path).read_text()).items()}
        backend = object.__new__(training.TorchLoRABackend)
        backend.torch, backend.model = torch, NS(save_pretrained=save_model)
        backend.get_state = lambda model: dict(state)
        backend.baseline = {"lora_A.weight": Tensor(0.0)}
        backend.initial_fingerprint = training._state_fingerprint(backend.baseline, torch)
        with tempfile.TemporaryDirectory() as temp:
            backend.session = NS(tokenizer=tokenizer, identity={"model_id": "fixture@abc", "native_embedding_rows": 4,
                                                               "material_manifest_sha256": "123", "local_material_path": temp})
            modules = {"peft": NS(set_peft_model_state_dict=set_state),
                       "safetensors.torch": NS(load_file=load_file),
                       "transformers": NS(AutoTokenizer=NS(from_pretrained=lambda *a, **kw: tokenizer))}
            with patch.dict(sys.modules, modules):
                result = backend.export_and_validate(Path(temp) / "adapter")
            self.assertTrue(result["baseline_restore_exact"])
            self.assertTrue(result["saved_state_exact"])
            self.assertTrue(result["reloaded_adapter_exact"])
            self.assertTrue(result["tokenizer_round_trip_exact"])
            self.assertFalse(result["fresh_base_process_reload_verified"])
            self.assertEqual(restores, [0.0, 2.0])
            binding = json.loads((Path(temp) / "adapter/adapter-binding.json").read_text())
            self.assertIn("adapter_model.safetensors", binding["files"])
            self.assertIn("source-model-identity.json", binding["files"])


class EnvironmentLockTests(unittest.TestCase):
    def test_wrong_platform_wheel_fails_closed(self):
        # This CPU test uses packaging's runtime tag set, without installing a wheel.
        from packaging.tags import Tag
        with patch("packaging.tags.sys_tags", return_value=iter([Tag("cp311", "cp311", "manylinux_2_28_x86_64")])):
            with self.assertRaisesRegex(models.ContractError, "ABI/platform"):
                models.validate_wheel_platform("torch-2.8.0+cu128-cp312-cp312-manylinux_2_28_x86_64.whl")
        with patch("packaging.tags.sys_tags", return_value=iter([Tag("cp311", "cp311", "manylinux_2_28_x86_64")])):
            models.validate_wheel_platform("torch-2.8.0+cu128-cp311-cp311-manylinux_2_28_x86_64.whl")

    def test_unlocked_or_partial_environment_rejected_before_package_read(self):
        versions = dict(models.GRANITE_BACKEND, torch="2.8.0+cu128")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = {"format": "irisx/arc-next-environment-lock-v1", "versions": versions}
            models.write_json(root / "environment-lock.json", lock)
            with patch.object(models.importlib.metadata, "version", side_effect=AssertionError("too early")):
                with self.assertRaisesRegex(models.ContractError, "complete transitive"):
                    models.validate_environment(root / "environment-lock.json", "granite-4.2-8b")
            lock["complete_transitive_lock"] = True
            lock["wheel_lock_sha256"] = "missing"
            models.write_json(root / "environment-lock.json", lock)
            with self.assertRaisesRegex(models.ContractError, "neighboring wheel lock"):
                models.validate_environment(root / "environment-lock.json", "granite-4.2-8b")


class LoaderAndHardwareTests(unittest.TestCase):
    def test_explicit_native_loader_offline_dtype_flags(self):
        for key, spec in models.MODELS.items():
            calls = []
            template = "fixture"
            tokenizer = NS(chat_template=template, get_chat_template=lambda: template,
                           get_vocab=lambda: {"x": 0, "y": spec.vocab_size - 2})
            model = type(spec.architecture, (), {
                "get_input_embeddings": lambda self: NS(weight=NS(shape=(spec.vocab_size, 4))),
                "get_output_embeddings": lambda self: NS(weight=NS(shape=(spec.vocab_size, 4))),
                "parameters": lambda self: [NS(numel=lambda: 12, dtype="BF16")],
                "state_dict": lambda self: {"weight": NS(shape=(3, 4))},
                "to": lambda self, device: calls.append(("to", device)),
            })()
            def from_pretrained(path, **kwargs):
                calls.append((path, kwargs))
                return model, {"missing_keys": [], "unexpected_keys": [], "mismatched_keys": [], "error_msgs": []}
            transformer = NS(AutoTokenizer=NS(from_pretrained=lambda *args, **kwargs: tokenizer))
            setattr(transformer, spec.loader_class, NS(from_pretrained=from_pretrained))
            identity = {"model_id": spec.repository + "@" + spec.revision,
                        "template_sha256": hashlib.sha256(template.encode()).hexdigest(),
                        "tokenizer_max_id": spec.vocab_size - 2, "tensor_inventory": {"weight": {"shape": [3, 4], "elements": 12}},
                        "vocabulary_mapping_sha256": models.digest(tokenizer.get_vocab()), "tokenizer_special_ids": {}}
            with tempfile.TemporaryDirectory() as temp, patch.dict(sys.modules, {"torch": NS(bfloat16="BF16", float32="F32"), "transformers": transformer}), \
                 patch.object(models, "validate_material", return_value=identity), \
                 patch.object(models, "validate_environment", return_value={}):
                session = models.load_candidate(temp, key, environment_lock_path="fake-lock", allow_experimental_qwen=True)
            kwargs = calls[0][1]
            self.assertIs(session.model, model)
            self.assertTrue(kwargs["local_files_only"])
            self.assertFalse(kwargs["trust_remote_code"])
            self.assertEqual(kwargs["torch_dtype"], "BF16")
            self.assertEqual(kwargs["attn_implementation"], "sdpa")
            self.assertTrue(kwargs["use_safetensors"])

    def test_qwen_never_silently_uses_generic_causal_loader(self):
        self.assertEqual(models.MODELS["qwen3.5-9b"].loader_class, "AutoModelForImageTextToText")
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(models.ContractError, "experimental"):
            models.load_candidate(temp, "qwen3.5-9b", environment_lock_path="unused")

    def test_qwen_lora_covers_delta_excludes_vision_and_mtp(self):
        class Linear:
            pass
        names = []
        for layer in range(32):
            stem = "model.language_model.layers." + str(layer) + "."
            names.extend(stem + "mlp." + suffix for suffix in ("gate_proj", "up_proj", "down_proj"))
            if (layer + 1) % 4:
                names.extend(stem + "linear_attn." + suffix for suffix in
                             ("in_proj_qkv", "in_proj_z", "in_proj_b", "in_proj_a", "out_proj"))
            else:
                names.extend(stem + "self_attn." + suffix for suffix in ("q_proj", "k_proj", "v_proj", "o_proj"))
        names += ["model.visual.q_proj", "mtp.0.q_proj", "lm_head"]
        model = NS(named_modules=lambda: [(name, Linear()) for name in names])
        targets = models.lora_target_modules(model, "qwen3.5-9b", NS(nn=NS(Linear=Linear)))
        self.assertEqual(len(targets), 248)
        self.assertTrue(all(name.startswith("model.language_model.layers.") for name in targets))
        bad = NS(named_modules=lambda: [(names[-4], Linear())])
        with self.assertRaisesRegex(models.ContractError, "DeltaNet"):
            models.lora_target_modules(bad, "qwen3.5-9b", NS(nn=NS(Linear=Linear)))

    def test_wrong_hardware_or_cuda_is_rejected(self):
        cuda = NS(is_available=lambda: True, device_count=lambda: 1,
                  get_device_properties=lambda n: NS(name="NVIDIA L4", total_memory=24_000_000_000))
        with self.assertRaisesRegex(models.ContractError, "96 GB"):
            models.observe_g4_hardware(NS(cuda=cuda))
        cuda.device_count = lambda: 4
        with self.assertRaisesRegex(models.ContractError, "exactly one"):
            models.observe_g4_hardware(NS(cuda=cuda))


if __name__ == "__main__":
    unittest.main()
