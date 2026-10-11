import copy
import json
from pathlib import Path
import tempfile
import time
import unittest

from tools.arc_learning_agent_20261011 import data
from tools.arc_next_models import digest
from src.irisx.arc_nvarc_data import transform_grid


def fixture_tasks():
    return {
        "a": {"train": [{"input": [[1, 2]], "output": [[2, 1]]}, {"input": [[3, 4, 5]], "output": [[5, 4, 3]]}]},
        "b": {"train": [{"input": [[1], [2]], "output": [[1, 1], [2, 2]]}, {"input": [[3]], "output": [[3, 3]]}]},
        "c": {"train": [{"input": [[1, 2], [3, 4]], "output": [[1, 3], [2, 4]]}, {"input": [[0, 1, 2], [3, 4, 5]], "output": [[0, 3], [1, 4], [2, 5]]}]},
        "d": {"train": [{"input": [[1, 1, 1]], "output": [[1]]}, {"input": [[2, 2]], "output": [[2]]}]},
    }


class DataTests(unittest.TestCase):
    def test_split_is_deterministic_before_augmentation(self):
        tasks = fixture_tasks()
        a = data.create_split_manifest(tasks, seed=7)
        b = data.create_split_manifest(dict(reversed(list(tasks.items()))), seed=7)
        self.assertEqual(a, b)
        rows = data.build_records(tasks, a, augmentations=4)
        report = data.validate_records(rows, a, ())
        self.assertEqual(report["split_counts"], {"train": 24, "dev": 2})
        for row in rows:
            self.assertEqual(row["parent_ids"], [row["task_id"]])
            self.assertNotIn("[", row["completion"])
            self.assertNotIn(row["provenance"]["held_out_demo"], row["provenance"]["visible_demo_indices"])

    def test_fixed_historical_dev_never_promoted_to_train(self):
        tasks = fixture_tasks()
        fixed = {"train": ["a", "b", "c"], "dev": ["d"]}
        manifest = data.create_split_manifest(tasks, fixed_splits=fixed)
        self.assertEqual(manifest["tasks"]["d"]["split"], "dev")
        for key in fixed["train"]:
            self.assertEqual(manifest["tasks"][key]["split"], "train")
        linked = data.create_split_manifest(tasks, fixed_splits=fixed, family_ids={"a": "linked", "d": "linked"})
        self.assertEqual(linked["tasks"]["a"]["split"], "dev")
        self.assertEqual(linked["tasks"]["d"]["split"], "dev")
        self.assertEqual(linked["train_to_dev_component_demotions"], ["a"])
        implied = data.create_split_manifest(tasks, source_identity={"fixed_splits": fixed})
        self.assertEqual(implied["tasks"]["d"]["split"], "dev")

    def test_ancestry_and_family_union(self):
        tasks = fixture_tasks()
        m = data.create_split_manifest(tasks, ancestry={"a": ["root"], "b": ["root"], "root": []}, family_ids={"b": "family", "c": "family"})
        self.assertEqual({m["tasks"][k]["split"] for k in ("a", "b", "c")}, {m["tasks"]["a"]["split"]})
        self.assertEqual(m["tasks"]["a"]["ancestor_ids"], ["a", "root"])

    def test_unknown_cycle_protected_multi_parent_rejected(self):
        for graph, protected in (({"a": ["unknown"]}, ()), ({"a": ["b"], "b": ["a"]}, ()),
                                  ({"a": ["root", "gold"], "root": [], "gold": []}, ("gold",))):
            with self.assertRaises(ValueError):
                data.create_split_manifest(fixture_tasks(), ancestry=graph, protected_ids=protected)

    def test_known_reversible_variants_stay_together(self):
        tasks = fixture_tasks()
        spec = {"rotation": 1, "transpose": True, "colors": list(reversed(range(10)))}
        tasks["a-copy"] = {"train": [{k: transform_grid(p[k], spec) for k in ("input", "output")} for p in reversed(tasks["a"]["train"])]}
        m = data.create_split_manifest(tasks)
        self.assertEqual(m["tasks"]["a"]["split"], m["tasks"]["a-copy"]["split"])
        for pair in tasks["a"]["train"]:
            for value in pair.values():
                self.assertEqual(value, transform_grid(transform_grid(value, spec), spec, inverse=True))

    def test_record_and_manifest_tampering_rejected(self):
        tasks = fixture_tasks()
        m = data.create_split_manifest(tasks)
        rows = data.build_records(tasks, m)
        changed = copy.deepcopy(rows)
        changed[0]["parent_ids"] = ["unknown"]
        with self.assertRaises(ValueError):
            data.validate_records(changed, m, ())
        changed[0]["record_id"] = digest({k: v for k, v in changed[0].items() if k != "record_id"})
        with self.assertRaises(ValueError):
            data.validate_records(changed, m, ())
        forged = copy.deepcopy(m)
        forged["tasks"]["a"]["family_id"] = "bogus"
        with self.assertRaises(ValueError):
            data.validate_records(rows, forged, ())

    def test_rehashed_wrong_grid_target_still_fails_source_admission(self):
        tasks = fixture_tasks()
        manifest = data.create_split_manifest(tasks)
        rows = data.build_records(tasks, manifest, augmentations=1)
        row = copy.deepcopy(rows[0])
        row["completion"] = "999999"
        row["record_id"] = digest({k: v for k, v in row.items() if k != "record_id"})
        with self.assertRaisesRegex(ValueError, "source demonstrations"):
            data.validate_records([row], manifest, ())

    def test_protected_added_after_compilation_rejected(self):
        tasks = fixture_tasks()
        m = data.create_split_manifest(tasks)
        with self.assertRaises(ValueError):
            data.validate_records(data.build_records(tasks, m), m, ("b",))

    def test_query_labels_and_extra_keys_rejected(self):
        tasks = fixture_tasks()
        tasks["a"]["test"] = [{"input": [[1]], "output": [[9]]}]
        with self.assertRaises(ValueError):
            data.create_split_manifest(tasks)
        with self.assertRaises(ValueError):
            data.build_task_records("x", [{"input": [[True]], "output": [[1]]}])

    def test_single_demo_task_has_no_lodo(self):
        self.assertEqual(data.build_task_records("task", [{"input": [[1]], "output": [[9]]}]), [])

    def test_task_lodo_hides_held_output_from_messages(self):
        # Distinct sentinels make leakage detection unambiguous.
        demos = [{"input": [[1]], "output": [[8, 8, 8]]}, {"input": [[2]], "output": [[7, 7, 7]]}]
        rows = data.build_task_records("task", demos, augmentations=1)
        for row in rows:
            self.assertNotIn(row["completion"], json.dumps(row["messages"]))
        self.assertEqual(rows, data.build_task_records("task", demos, augmentations=1))

    def test_merge_preserves_sources_and_rejects_conflict(self):
        first = data.create_split_manifest(fixture_tasks())
        second_tasks = {"second:" + k: v for k, v in fixture_tasks().items()}
        second = data.create_split_manifest(second_tasks)
        # Identical variant groups assigned independently may differ; merging must reject.
        bad = copy.deepcopy(second)
        old = first["tasks"]["a"]["split"]
        bad["tasks"]["second:a"]["split"] = "dev" if old == "train" else "train"
        bad["parents"]["second:a"]["split"] = bad["tasks"]["second:a"]["split"]
        bad["manifest_sha256"] = digest({k: v for k, v in bad.items() if k != "manifest_sha256"})
        with self.assertRaises(ValueError):
            data.merge_manifests(first, bad)
        same = data.merge_manifests(first, first)
        self.assertEqual(same["tasks"], first["tasks"])
        self.assertEqual(len(same["source_identity"]["inputs"]), 2)

    def test_real_verified_train_trajectory_and_semantic_repair(self):
        from tools.arc_learning_agent_20261011.program_tools import verify_program
        tasks = fixture_tasks()
        manifest = data.create_split_manifest(tasks)
        # Use a genuinely trained-parent identity for a general identity program.
        train_id = next(k for k, v in manifest["tasks"].items() if v["split"] == "train")
        tasks[train_id] = {"train": [{"input": [[1, 2]], "output": [[1, 2]]}, {"input": [[3, 4, 5]], "output": [[3, 4, 5]]}]}
        manifest = data.create_split_manifest(tasks)
        # Fixture ID ranking is unchanged, so its parent remains in train.
        self.assertEqual(manifest["tasks"][train_id]["split"], "train")
        good = "def transform(grid):\n    return copy_grid(grid)\n"
        wrong = "def transform(grid):\n    return [[0]]\n"
        with tempfile.TemporaryDirectory() as tmp:
            proof = verify_program(good, tasks[train_id]["train"], tmp, "good")
            failed = verify_program(wrong, tasks[train_id]["train"], tmp, "failed")
            row = data.verified_program_record(train_id, tasks[train_id], good, proof, manifest)
            repaired = data.verified_program_record(train_id, tasks[train_id], good, proof, manifest, feedback=failed)
            self.assertEqual(row["kind"], "program")
            self.assertEqual(repaired["kind"], "repair")
            self.assertFalse(row["provenance"]["generalization_claim"])
            data.validate_records([row, repaired], manifest, ())
            visible_proof = verify_program(good, tasks[train_id]["train"][:1], tmp, "visible")
            context = {"visible_indices": [0], "held_out_demo_index": 1, "visible_verification_proof": visible_proof}
            held = data.verified_program_record(train_id, tasks[train_id], good, proof, manifest, generation_context=context)
            self.assertEqual(held["provenance"]["generalization_claim"], "training-heldout-demo-not-prompted")
            self.assertEqual(len(held["provenance"]["prompt_task"]["train"]), 1)
            self.assertEqual(held["provenance"]["prompt_task"]["test"], [{"input": tasks[train_id]["train"][1]["input"]}])
            changed = copy.deepcopy(context)
            changed["visible_indices"] = [0, 1]
            with self.assertRaises(ValueError):
                data.verified_program_record(train_id, tasks[train_id], good, proof, manifest, generation_context=changed)
            with self.assertRaises(ValueError):
                data.verified_program_record(train_id, tasks[train_id], wrong, proof, manifest)
            dev = next(k for k, v in manifest["tasks"].items() if v["split"] == "dev")
            with self.assertRaises(ValueError):
                data.verified_program_record(dev, tasks[dev], good, proof, manifest)
            Path(proof["proof_path"]).write_text("{}")
            with self.assertRaises(ValueError):
                data.validate_records([row], manifest, ())

    def test_authored_curriculum_actual_bounded_vm(self):
        with tempfile.TemporaryDirectory() as tmp:
            records, manifest, report = data.build_authored_curriculum(per_family=1, deadline=time.monotonic() + 90, output_dir=Path(tmp) / "corpus")
            self.assertEqual(report["verifier_calls"], 16)
            self.assertEqual(report["records"], 24)
            self.assertEqual(report["families"], 8)
            self.assertEqual(report["split_counts"], {"train": 18, "dev": 6})
            self.assertEqual(set(r["kind"] for r in records), {"grid", "program", "repair"})
            self.assertFalse(report["full_nvarc_corpus"])
            data.validate_records(records, manifest, ())


if __name__ == "__main__":
    unittest.main()
