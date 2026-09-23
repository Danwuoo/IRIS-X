from __future__ import annotations

import json
import multiprocessing
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock
import zipfile

from irisx.arc_nvarc_candidates import FixtureCandidateBackend, rank_candidates, solve_task
from irisx.arc_nvarc_cli import fixture_e2e
from irisx.arc_nvarc_data import (compare_visible, freeze_shards, freeze_streaming, grid, import_jsonl,
                                   known_variant_group, pair_saved_sdg_grids, replay_sdg_stage,
                                   require_isolated_executor, seeded_transform, selected_view,
                                   stream_import_jsonl, transform_grid, transform_task, visible_task)
from irisx.arc_nvarc_kaggle import enforce_deadline, run as run_kaggle
from irisx.arc_nvarc_representation import (GridTokenizer, MODEL_REVISION,
                                             PINNED_SOURCE_IDS, vocabulary_manifest)
from irisx.arc_nvarc_runtime import (build_outbound, make_binding, make_workload,
                                     new_checkpoint, reserve_task, score_sealed)
from irisx.arc_nvarc_training import (FrozenSequenceStore, collate, supervised_sequences,
                                       task_local_sequences, tiny_train)
from irisx.arc_nvarc_trm import (integrate_attempts, integrate_with_qwen_verifier,
                                 stage_trm_training, trm_grid)
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from irisx.transport import digest_path


def synthetic_worker(rank, commands, outputs, model_root, config, gpu_uuid):
    outputs.put({"type": "ready", "rank": rank, "gpu_uuid": gpu_uuid, "model_load_seconds": 0.0})
    while True:
        command = commands.get()
        if command["type"] == "stop":
            return
        task_id = command["task"]["task_id"]
        if rank == 0:
            time.sleep(30)
        elif rank == 1:
            outputs.put({"type": "failure", "rank": rank, "task_id": task_id,
                         "status": "worker_crash", "detail": "synthetic failure"})
            return
        else:
            outputs.put({"type": "record", "rank": rank, "task_id": task_id,
                         "record": {"task_id": task_id, "status": "missing-candidate",
                                    "tests": [{"test_index": 0, "attempts": [[[0]]],
                                               "missing_attempts": 1, "status": "missing-candidate",
                                               "generation_calls_so_far": 1,
                                               "returned_sequences": 1}],
                                    "timing": {"load_seconds": None, "ttt_seconds": 0.0,
                                               "generate_seconds": 0.0, "rank_seconds": 0.0},
                                    "peak_memory_mib": None}})


def synthetic_startup_failure_worker(rank, commands, outputs, model_root, config, gpu_uuid):
    if rank == 1:
        outputs.put({"type": "failure", "rank": rank, "task_id": None,
                     "status": "worker_crash", "detail": "synthetic load failure"})
        return
    outputs.put({"type": "ready", "rank": rank, "gpu_uuid": gpu_uuid, "model_load_seconds": 0.0})
    while commands.get()["type"] != "stop":
        pass


class NvarcTests(unittest.TestCase):
    def test_rectangular_transform_and_color_zero_roundtrip(self) -> None:
        task = {"task_id": "x", "train": [{"input": [[0, 1]], "output": [[1, 0]]}],
                "test": [{"input": [[0, 2, 3]]}]}
        for index in range(32):
            spec = seeded_transform(task, 71, index)
            source = [[0, 1, 2], [3, 4, 5]]
            self.assertEqual(source, transform_grid(transform_grid(source, spec), spec, inverse=True))
        with self.assertRaises(ValidationError):
            grid([[0], [1, 2]])

    def test_full_task_view_does_not_collapse_multi_test(self) -> None:
        task = visible_task("x", {"train": [{"input": [[1]], "output": [[2]]}],
                                  "test": [{"input": [[3]]}, {"input": [[4]], "output": [[9]]}]})
        self.assertEqual(2, len(task["test"]))
        self.assertFalse(compare_visible(task, selected_view(task, 0)))
        self.assertTrue(compare_visible(task, task))

    def test_split_parent_overlap_and_training_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records_path = root / "records.jsonl"
            item = {"task_id": "x", "parent_id": "p", "source_id": "synthetic",
                    "train": [{"input": [[1]], "output": [[2]]}],
                    "test": [{"input": [[3]], "output": [[4]]}]}
            records_path.write_bytes(canonical_bytes(item, newline=True))
            records = import_jsonl(records_path, split="sft-train")
            self.assertEqual(1, len(supervised_sequences(records)))
            manifest = freeze_shards(records, root / "frozen", policy="clean-research")
            self.assertEqual("unproven", manifest["exposure"])
            streamed = freeze_streaming(stream_import_jsonl(records_path, split="sft-train"),
                                        root / "streamed", policy="clean-research", shard_size=2)
            self.assertEqual(manifest, streamed)
            self.assertEqual(supervised_sequences(records)[0], FrozenSequenceStore(root / "streamed")[0])
            with self.assertRaises(ValidationError):
                freeze_shards(records + [{**records[0], "split": "selection-dev", "task_id": "y"}],
                              root / "crossed", policy="clean-research")
            with self.assertRaises(ValidationError):
                import_jsonl(records_path, split="sft-train", forbidden_parent_ids={"p"})
            transformed = transform_task(records[0], {"rotation": 1, "transpose": True,
                "colors": [1, 2, 3, 4, 5, 6, 7, 8, 9, 0], "demo_order": [0]})
            self.assertEqual(known_variant_group(records[0]), known_variant_group(transformed))
            with self.assertRaises(ValidationError):
                freeze_shards(records + [{**transformed, "task_id": "y", "parent_id": "other",
                                          "source_id": "synthetic", "split": "selection-dev"}],
                              root / "variant-crossed", policy="clean-research")

    def test_tokenizer_mask_padding_and_incomplete_grid(self) -> None:
        tokenizer = GridTokenizer()
        tokens, labels = tokenizer.encode_pair([[0, 1], [2, 3]], [[4, 5], [6, 7]])
        batch = collate([{"input_ids": tokens, "labels": labels},
                         {"input_ids": tokens[:-2] + [15], "labels": labels[:-2] + [15]}], 50)
        self.assertEqual(-100, batch["labels"][1][-1])
        self.assertEqual(0, batch["attention_mask"][1][-1])
        self.assertEqual([[4, 5], [6, 7]], tokenizer.parse_completion(tokenizer.encode_grid([[4, 5], [6, 7]]) + [15], stopped_on_eos=True))
        self.assertIsNone(tokenizer.parse_completion([4, 5], stopped_on_eos=False))
        class Native:
            values = dict(zip([str(i) for i in range(10)] + ["\n", "user", "assistant",
                               "<|endoftext|>", "<|im_start|>", "<|im_end|>"],
                              PINNED_SOURCE_IDS))
            def encode(self, text, add_special_tokens=False):
                return [self.values[text]]
        manifest = vocabulary_manifest(Native(), model_revision=MODEL_REVISION,
                                       model_manifest_digest=digest_value("base"))
        self.assertEqual(16, manifest["vocab_size"])
        Native.values["0"] = 999
        with self.assertRaises(ValidationError):
            vocabulary_manifest(Native(), model_revision=MODEL_REVISION,
                                model_manifest_digest=digest_value("base"))

    def test_tiny_resume_replays_same_gradient_path(self) -> None:
        task = visible_task("x", {"train": [{"input": [[1]], "output": [[2]]}],
                                  "test": [{"input": [[3]]}]})
        sequences = supervised_sequences([task])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = tiny_train(sequences, root / "resume", seed=19, steps=2)
            second = tiny_train(sequences, root / "resume", seed=19, steps=2, resume=True)
            whole = tiny_train(sequences, root / "whole", seed=19, steps=4)
            self.assertEqual(whole["rows"], second["rows"])
            self.assertEqual((4, 4), (second["cursor"], second["steps"]))
            with self.assertRaises(ValidationError):
                tiny_train(sequences, root / "resume", seed=20, steps=1, resume=True)

    def test_task_local_targets_never_include_test_truth(self) -> None:
        task = {"task_id": "x", "train": [
            {"input": [[1]], "output": [[2]]}, {"input": [[3]], "output": [[4]]}],
            "test": [{"input": [[5]], "output": [[9]]}]}
        before = task_local_sequences(task, seed=5, augmentation_count=2)
        changed = {**task, "test": [{"input": [[5]], "output": [[0]]}]}
        self.assertEqual(before, task_local_sequences(changed, seed=5, augmentation_count=2))
        self.assertEqual(4, len(before))
        self.assertTrue(all(example["labels"].count(-100) > 0 for example in before))

    def test_sdg_saved_replay_pairs_and_rejects_unsafe_execution(self) -> None:
        seed = [{"record_id": "a", "parent_id": "p", "source_id": "synthetic"}]
        inputs = replay_sdg_stage("input-logic", seed,
                                  {"a": [[[0]], [[1]]]}, prompt_digest=digest_value("in"), seed=7)
        outputs = replay_sdg_stage("output-logic", seed,
                                   {"a": [[[2]], [[3]]]}, prompt_digest=digest_value("out"), seed=7)
        paired = pair_saved_sdg_grids(inputs, outputs)
        self.assertTrue(paired[0]["accepted"])
        self.assertEqual(0, paired[0]["provider_calls"])
        with self.assertRaises(ValidationError):
            require_isolated_executor({"network": "none", "attested": False})
        with self.assertRaises(ValidationError):
            pair_saved_sdg_grids(inputs, [{**outputs[0], "parent_id": "other"}])

    def test_ranking_inverse_and_no_duplicate_attempts(self) -> None:
        task = visible_task("x", {"train": [{"input": [[1]], "output": [[2]]}],
                                  "test": [{"input": [[0, 3]]}]})
        backend = FixtureCandidateBackend({"x:0": [[[0, 4]], [[5, 0]]]})
        config = {"seed": 6, "color_repeats": 2, "maximum_calls_per_task": 16,
                  "beams_per_call": 1, "maximum_new_tokens": 16}
        output = solve_task(task, backend, config)
        self.assertEqual(2, len(output[0]["attempts"]))
        self.assertEqual(16, output[0]["generation_calls_so_far"])
        self.assertEqual({((0, 4),), ((5, 0),)}, {tuple(map(tuple, value)) for value in output[0]["attempts"]})
        self.assertEqual([], rank_candidates([{"grid": [[1]], "complete": False,
                                               "source": "cap", "beam_nll": 0,
                                               "verification_nll": 0}]))

    def test_truth_boundary_and_multi_test_scoring(self) -> None:
        truth = {"x": {"train": [{"input": [[1]], "output": [[2]]}],
                       "test": [{"input": [[3]], "output": [[4]]},
                                {"input": [[5]], "output": [[6]]}]},
                 "y": {"train": [{"input": [[0]], "output": [[9]]}],
                       "test": [{"input": [[7]], "output": [[8]]}]}}
        records = [{"task_id": "x", "tests": [
            {"test_index": 0, "attempts": [[[0]], [[4]]], "status": "complete"},
            {"test_index": 1, "attempts": [[[0]]], "status": "missing-candidate"}]},
                   {"task_id": "y", "tests": [
                       {"test_index": 0, "attempts": [[[8]]], "status": "complete"}]}]
        score = score_sealed(truth, records)
        self.assertEqual((1, 2, 3), (score["passed_at_1"], score["passed_at_2"], score["test_outputs"]))
        self.assertEqual(1, score["task_all_correct"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = make_workload(truth, source_digest=digest_value(truth))
            binding = make_binding(work, run_id="nvarc-test", model_digest=digest_value("m"),
                                   data_digest=digest_value("d"), tokenizer_digest=digest_value("t"),
                                   runtime_digest=digest_value("r"), config={
                                       "worker_count": 4, "task_deadline_seconds": 1,
                                       "session_budget_seconds": 100, "finalization_reserve_seconds": 1,
                                       "maximum_calls_per_task": 2, "beams_per_call": 1,
                                       "maximum_new_tokens": 10})
            build_outbound(root / "safe.zip", binding, work)
            with zipfile.ZipFile(root / "safe.zip") as archive:
                payload = archive.read("cases/visible-tasks.json")
                self.assertNotIn(b'"output":[[4]]', payload)
            unsafe = json.loads(json.dumps(work))
            unsafe["cases"][0]["test"][0]["expected_output"] = [[4]]
            with self.assertRaises(ValidationError):
                build_outbound(root / "unsafe.zip", {**binding, "workload_digest": digest_value(unsafe)}, unsafe)
            checkpoint = new_checkpoint(binding, work)
            reserve_task(checkpoint, binding, "x", rank=0, at_utc="now")
            with self.assertRaises(ValidationError):
                reserve_task(checkpoint, binding, "x", rank=0, at_utc="now")

    def test_worker_is_killed_at_deadline(self) -> None:
        context = multiprocessing.get_context("spawn")
        process = context.Process(target=time.sleep, args=(30,))
        process.start()
        try:
            self.assertFalse(enforce_deadline(process, 10.0, 9.0))
            self.assertTrue(process.is_alive())
            self.assertTrue(enforce_deadline(process, 10.0, 10.0))
            self.assertFalse(process.is_alive())
        finally:
            if process.is_alive():
                process.kill()
                process.join()

    def test_four_worker_parent_terminalizes_crash_timeout_and_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "arc-agi_training_challenges.json"
            tasks = {f"t{i}": {"train": [{"input": [[1]], "output": [[2]]}],
                               "test": [{"input": [[3]]}]} for i in range(4)}
            source.write_bytes(canonical_bytes(tasks, newline=True))
            work = make_workload(tasks, source_digest=digest_path(source))
            config = {"worker_count": 4, "task_deadline_seconds": 1,
                      "session_budget_seconds": 20, "finalization_reserve_seconds": 2,
                      "maximum_calls_per_task": 1, "beams_per_call": 1,
                      "maximum_new_tokens": 10}
            binding = make_binding(work, run_id="nvarc-synthetic-supervisor",
                                   model_digest=digest_value("m"), data_digest=digest_value("d"),
                                   tokenizer_digest=digest_value("t"), runtime_digest=digest_value("r"),
                                   config=config)
            outbound = root / "outbound.zip"
            build_outbound(outbound, binding, work)
            model = root / "model"; model.mkdir()
            (model / "grid-vocab.json").write_text("{}")
            hardware = {"gpus": [{"uuid": f"gpu-{i}"} for i in range(4)]}
            with mock.patch("irisx.arc_nvarc_kaggle.validate_hardware", return_value=hardware), \
                 mock.patch("irisx.arc_nvarc_kaggle.verify_model_material", return_value={}):
                run_kaggle(outbound, model, source, root / "result.zip",
                           root / "checkpoint.json", worker_target=synthetic_worker)
            checkpoint = json.loads((root / "checkpoint.json").read_bytes())
            statuses = [record["status"] for record in checkpoint["completed"].values()]
            self.assertEqual(1, statuses.count("timeout"))
            self.assertEqual(1, statuses.count("worker_crash"))
            self.assertEqual(2, statuses.count("missing-candidate"))
            self.assertEqual(4, checkpoint["counters"]["generation_calls_reserved"])
            self.assertEqual(2, checkpoint["counters"]["generation_calls_observed"])
            interrupted = new_checkpoint(binding, work)
            reserve_task(interrupted, binding, "t0", rank=0, at_utc="past")
            interrupted["sessions"] = [{"index": 0, "wall_seconds": 19.0,
                                         "gpu_uuids": [f"gpu-{i}" for i in range(4)]}]
            resume_path = root / "resume-checkpoint.json"
            resume_path.write_bytes(canonical_bytes(interrupted, newline=True))
            with mock.patch("irisx.arc_nvarc_kaggle.validate_hardware", return_value=hardware), \
                 mock.patch("irisx.arc_nvarc_kaggle.verify_model_material", return_value={}):
                run_kaggle(outbound, model, source, root / "resume-result.zip",
                           resume_path, resume=True, worker_target=synthetic_worker)
            resumed = json.loads(resume_path.read_bytes())
            self.assertEqual("interrupted_pending", resumed["completed"]["t0"]["status"])
            self.assertEqual(1, resumed["counters"]["generation_calls_reserved"])
            self.assertEqual(0, resumed["counters"]["generation_calls_observed"])
            self.assertEqual(1, len(resumed["sessions"]))
            with mock.patch("irisx.arc_nvarc_kaggle.validate_hardware", return_value=hardware), \
                 mock.patch("irisx.arc_nvarc_kaggle.verify_model_material", return_value={}):
                run_kaggle(outbound, model, source, root / "startup-result.zip",
                           root / "startup-checkpoint.json",
                           worker_target=synthetic_startup_failure_worker)
            startup = json.loads((root / "startup-checkpoint.json").read_bytes())
            self.assertEqual(4, len(startup["completed"]))
            self.assertTrue(all(record["status"] == "not_executed" for record in startup["completed"].values()))

    def test_trm_encoding_and_branch_priority(self) -> None:
        encoded = trm_grid([[0, 9], [1, 2]])
        self.assertEqual([2, 11, 1], encoded[:3])
        self.assertEqual(900, len(encoded))
        qwen = [{"grid": [[1]]}]
        trm = [{"grid": [[2]]}, {"grid": [[1]]}]
        self.assertEqual([[[1]], [[2]]], integrate_attempts(qwen, trm, mode="combined"))
        class Verifier:
            def verify(self, task, index, value):
                return 0.0 if value == [[2]] else 10.0
        result = integrate_with_qwen_verifier({"task_id": "x"}, 0, qwen, trm[:1], Verifier())
        self.assertEqual([[2]], result["attempts"][0])
        self.assertEqual(2, result["verification_calls"])
        with tempfile.TemporaryDirectory() as temp:
            task = {"train": [{"input": [[0]], "output": [[1]]}],
                    "labelled_test": [{"input": [[2]], "output": [[3]]}]}
            manifest = stage_trm_training({"x": task}, Path(temp) / "trm",
                                          source_digest=digest_value("fixture"),
                                          augmentation_count=2)
            self.assertTrue(manifest["contains_labels"])
            staged = json.loads((Path(temp) / "trm" / "arc-agi_sft_challenges.json").read_bytes())
            self.assertNotIn("output", staged["x"]["test"][0])

    def test_offline_e2e_artifacts_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = fixture_e2e(root / "one")
            second = fixture_e2e(root / "two")
            self.assertEqual(first["result_digest"], second["result_digest"])
            self.assertEqual((1, 2, 3), (first["score"]["passed_at_1"],
                                         first["score"]["passed_at_2"], first["score"]["test_outputs"]))
            self.assertEqual("fixture-predictions", first["backend"])


if __name__ == "__main__":
    unittest.main()
