"""Synthetic-only, stdlib tests for the independent public diagnostic.

No fixture contains actual ARC evaluation tasks or answers. Network calls are
always mocked; no private IRIS implementation or materials are imported.
"""

import copy
import hashlib
import io
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from tools.public_sft141_diagnostic import contract as codec
from tools.public_sft141_diagnostic import materials


def synthetic_tasks(multi=True):
    tasks = {}
    for index in range(120):
        tests = [{"input": [[2]], "output": [[9, 8], [7, 6]]}]
        if multi and index < 47:
            tests.append({"input": [[3], [4]], "output": [[5, 6, 7]]})
        tasks[f"{index:08x}"] = {
            "train": [{"input": [[0]], "output": [[1]]}], "test": tests,
        }
    return tasks


def write_synthetic_source(root, tasks):
    root.mkdir()
    entries = []
    for task_id, task in sorted(tasks.items()):
        data = (json.dumps(task) + "\n").encode()
        (root / (task_id + ".json")).write_bytes(data)
        entries.append({"path": f"data/evaluation/{task_id}.json",
                        "git_blob_sha1": materials.git_blob_sha1(data)})
    return {"schema_version": 1, "commit": materials.PUBLIC_COMMIT,
            "repository": materials.PUBLIC_REPOSITORY, "files": entries}


class CodecTests(unittest.TestCase):
    def test_exact_public_prompt_and_all_support(self):
        train = [{"input": [[1, 2], [3, 4]], "output": [[5]]},
                 {"input": [[6]], "output": [[7, 8]]}]
        query = [[9, 0]]
        expected_text = ("<|im_start|>user\n12\n34<|im_end|><|im_start|>assistant\n5<|im_end|>"
                         "<|im_start|>user\n6<|im_end|><|im_start|>assistant\n78<|im_end|>"
                         "<|im_start|>user\n90<|im_end|><|im_start|>assistant\n")
        expected_ids = [14, 11, 10, 1, 2, 10, 3, 4, 15, 14, 12, 10, 5, 15,
                        14, 11, 10, 6, 15, 14, 12, 10, 7, 8, 15,
                        14, 11, 10, 9, 0, 15, 14, 12, 10]
        self.assertEqual(codec.prompt_text(train, query), expected_text)
        self.assertEqual(codec.prompt_ids(train, query), expected_ids)
        self.assertEqual("".join(codec.TOKEN_STRINGS[token] for token in expected_ids), expected_text)

    def test_exact_grid_and_answer(self):
        self.assertEqual(codec.grid_text([[0, 9], [8, 1]]), "09\n81")
        self.assertEqual(codec.answer_ids([[0, 9], [8, 1]]), [0, 9, 10, 8, 1, 15])
        self.assertEqual(codec.parse_answer([0, 9, 10, 8, 1, 15]), [[0, 9], [8, 1]])

    def test_maximum_grid_token_allowance(self):
        grid = [[9] * 30 for _ in range(30)]
        self.assertEqual(len(codec.answer_ids(grid)), 930)
        self.assertEqual(codec.MAX_NEW_TOKENS, 931)
        self.assertEqual(codec.parse_answer(codec.answer_ids(grid)), grid)

    def test_all_rectangular_d4_roundtrips(self):
        for height in range(1, 31):
            for width in range(1, 31):
                grid = [[(row * width + col) % 10 for col in range(width)] for row in range(height)]
                for view in codec.VIEWS:
                    with self.subTest(height=height, width=width, view=view):
                        transformed = codec.transform(grid, view)
                        self.assertEqual(codec.inverse(transformed, view), grid)
                        self.assertEqual(codec.transform(codec.inverse(grid, view), view), grid)

    def test_stable_view_order_on_non_square(self):
        grid = [[1, 2, 3], [4, 5, 6]]
        self.assertEqual(codec.transform(grid, 0), grid)
        self.assertEqual(codec.transform(grid, 1), [[3, 6], [2, 5], [1, 4]])
        self.assertEqual(codec.transform(grid, 4), [[1, 4], [2, 5], [3, 6]])
        self.assertEqual(codec.transform(grid, 5), [[4, 5, 6], [1, 2, 3]])
        self.assertEqual(len({codec.grid_text(codec.transform(grid, view)) for view in codec.VIEWS}), 8)

    def test_transform_applies_to_support_and_query(self):
        train = [{"input": [[1, 2, 3]], "output": [[4, 5]]},
                 {"input": [[6], [7]], "output": [[8, 9], [0, 1]]}]
        query = [[2, 3], [4, 5], [6, 7]]
        for view in codec.VIEWS:
            changed = [{key: codec.transform(value, view) for key, value in pair.items()}
                       for pair in train]
            self.assertEqual(codec.prompt_ids(train, query, view),
                             codec.prompt_ids(changed, codec.transform(query, view)))

    def test_strict_parse_rejects_malformed_without_repair(self):
        invalid = [[], [15], [1], [1, 15, 13], [1, 15, 2, 15], [1, 13, 15],
                   [1, 11, 15], [1, 14, 15], [10, 1, 15], [1, 10, 15],
                   [1, 10, 10, 2, 15], [1, 2, 10, 3, 15], [True, 15],
                   [1.0, 15], ["1", 15], [-1, 15], [16, 15], [1] * 31 + [15],
                   [item for _ in range(30) for item in [1, 10]] + [1, 15],
                   [1] * 931 + [15]]
        for ids in invalid:
            with self.subTest(ids=ids[:20]), self.assertRaises(ValueError):
                codec.parse_answer(ids)

    def test_grid_and_view_validation(self):
        for grid in [[], [[]], [[True]], [[-1]], [[10]], [[1.0]], [["1"]],
                     [[1], [1, 2]], [[1] * 31], [[1]] * 31, "12"]:
            with self.subTest(grid=grid), self.assertRaises(ValueError):
                codec.validate_grid(grid)
        for view in [-1, 8, True, 1.0, "0"]:
            with self.assertRaises(ValueError):
                codec.transform([[1]], view)
        with self.assertRaises(ValueError):
            codec.prompt_ids([], [[1]])
        with self.assertRaises(ValueError):
            codec.prompt_ids([{"input": [[1]]}], [[1]])


class SelectionTests(unittest.TestCase):
    def test_panel_balanced_deterministic_and_order_independent(self):
        tasks = synthetic_tasks()
        first = materials.select_panel(tasks)
        self.assertEqual(first, materials.select_panel(dict(reversed(list(tasks.items())))))
        self.assertEqual(len(first["selected"]), 12)
        self.assertEqual(Counter(row["quartile"] for row in first["inventory"]), {0: 30, 1: 30, 2: 30, 3: 30})
        self.assertEqual(Counter(row["quartile"] for row in first["selected"]), {0: 3, 1: 3, 2: 3, 3: 3})
        self.assertTrue(any(row["test_count"] > 1 for row in first["selected"]))

    def test_selection_never_reads_query_output(self):
        class InputOnly(dict):
            def __getitem__(self, key):
                if key != "input":
                    raise AssertionError("query answer was accessed")
                return super().__getitem__(key)

        original = synthetic_tasks()
        poisoned = copy.deepcopy(original)
        for task in poisoned.values():
            task["test"] = [InputOnly(input=query["input"]) for query in task["test"]]
        self.assertEqual(materials.select_panel(original), materials.select_panel(poisoned))
        for task in original.values():
            for query in task["test"]:
                query["output"] = {"invalid": "deliberately not a grid"}
        self.assertEqual(materials.select_panel(original), materials.select_panel(poisoned))

    def test_cost_includes_every_query_support_and_view(self):
        tasks = synthetic_tasks()
        task = tasks["00000000"]
        task["train"].append({"input": [[5] * 20], "output": [[6] * 30]})
        task["test"].append({"input": [[7] * 30], "output": [[1]]})
        selection = materials.select_panel(tasks)
        row = next(row for row in selection["inventory"] if row["task_id"] == "00000000")
        expected = max(len(codec.prompt_ids(task["train"], query["input"], view))
                       for query in task["test"] for view in codec.VIEWS)
        self.assertEqual(row["max_prompt_tokens"], expected)
        self.assertEqual(row["test_count"], 3)
        self.assertGreater(expected, len(codec.prompt_ids(task["train"], task["test"][0]["input"])))

    def test_multiquery_repair_first_eligible_quartile_hash_order(self):
        tasks = synthetic_tasks(multi=False)
        eligible = {}
        for quartile in (1, 3):
            ids = [f"{index:08x}" for index in range(quartile * 30, (quartile + 1) * 30)]
            ranked = sorted(ids, key=materials.selection_hash)
            eligible[quartile] = ranked
            for task_id in ranked[3:5]:
                tasks[task_id]["test"].append({"input": [[2]], "output": [[0]]})
        result = materials.select_panel(tasks)
        self.assertEqual(result["multi_query_repair"], {
            "quartile": 1, "removed_task_id": eligible[1][2], "added_task_id": eligible[1][3],
        })
        chosen = {row["task_id"] for row in result["selected"]}
        self.assertIn(eligible[1][3], chosen)
        self.assertNotIn(eligible[1][2], chosen)
        self.assertNotIn(eligible[3][3], chosen)

    def test_requires_complete_inventory_and_multiquery_parent(self):
        with self.assertRaises(ValueError):
            materials.select_panel({})
        with self.assertRaises(ValueError):
            materials.select_panel(synthetic_tasks(multi=False))


class MaterialsTests(unittest.TestCase):
    def test_checked_in_public_pins_are_answer_free(self):
        pins = materials.load_public_pins()
        self.assertEqual(len(pins["files"]), 120)
        self.assertTrue(all(set(entry) == {"path", "git_blob_sha1"} for entry in pins["files"]))
        self.assertEqual(pins["commit"], materials.PUBLIC_COMMIT)

    def test_git_blob_hash_is_not_plain_sha1(self):
        data = b"synthetic fixture\n"
        self.assertEqual(materials.git_blob_sha1(data), hashlib.sha1(b"blob 18\0" + data).hexdigest())
        self.assertNotEqual(materials.git_blob_sha1(data), hashlib.sha1(data).hexdigest())

    def test_prepare_preserves_all_queries_and_separates_gold(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = synthetic_tasks()
            pins = write_synthetic_source(root / "source", tasks)
            with patch.object(materials, "load_public_pins", return_value=pins), \
                    patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
                manifest = materials.prepare_materials(root / "source", root / "out")
                verified, plan = materials.verify_materials(root / "out")
                self.assertEqual(verified, manifest)
                gold = json.loads((root / "out" / "gold.json").read_bytes())
                self.assertEqual(len(plan["parents"]), 12)
                self.assertEqual(sum(len(task["test"]) for task in tasks.values()), 167)
                for parent in plan["parents"]:
                    task = tasks[parent["task_id"]]
                    self.assertEqual(parent["train"], task["train"])
                    self.assertEqual(len(parent["test"]), len(task["test"]))
                    for index, query in enumerate(parent["test"]):
                        self.assertEqual(set(query), {"input", "query_id", "test_index"})
                        self.assertEqual(query["input"], task["test"][index]["input"])
                        self.assertEqual(query["test_index"], index)
                        self.assertEqual(query["query_id"], f"{parent['task_id']}:{index}")
                    self.assertEqual(gold["answers"][parent["task_id"]],
                                     [query["output"] for query in task["test"]])
                for name in ("plan.json", "gold.json"):
                    data = (root / "out" / name).read_bytes()
                    self.assertEqual(manifest["files"][name]["sha256"], hashlib.sha256(data).hexdigest())
                before = {path.name: path.read_bytes() for path in (root / "out").iterdir()}
                with self.assertRaises(FileExistsError):
                    materials.prepare_materials(root / "source", root / "out")
                self.assertEqual(before, {path.name: path.read_bytes() for path in (root / "out").iterdir()})

    def test_prepare_deterministic_plan_even_when_gold_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = synthetic_tasks()
            pins = write_synthetic_source(root / "first", tasks)
            with patch.object(materials, "load_public_pins", return_value=pins):
                materials.prepare_materials(root / "first", root / "out1")
            for task in tasks.values():
                for query in task["test"]:
                    query["output"] = [[0] * 30 for _ in range(30)]
            pins = write_synthetic_source(root / "second", tasks)
            with patch.object(materials, "load_public_pins", return_value=pins):
                materials.prepare_materials(root / "second", root / "out2")
            self.assertEqual((root / "out1" / "plan.json").read_bytes(),
                             (root / "out2" / "plan.json").read_bytes())
            self.assertNotEqual((root / "out1" / "gold.json").read_bytes(),
                                (root / "out2" / "gold.json").read_bytes())

    def test_pin_mismatch_fails_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pins = write_synthetic_source(root / "source", synthetic_tasks())
            (root / "source" / "00000000.json").write_bytes(b"{}")
            with patch.object(materials, "load_public_pins", return_value=pins):
                with self.assertRaisesRegex(ValueError, "pin mismatch"):
                    materials.prepare_materials(root / "source", root / "out")
            self.assertFalse((root / "out").exists())

    def test_missing_and_extra_public_source_files_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pins = write_synthetic_source(root / "source", synthetic_tasks())
            with patch.object(materials, "load_public_pins", return_value=pins):
                extra = root / "source" / "unexpected.json"
                extra.write_bytes(b"{}")
                with self.assertRaises(ValueError):
                    materials.load_public_data(root / "source")
                extra.unlink()
                (root / "source" / "00000000.json").unlink()
                with self.assertRaises(ValueError):
                    materials.load_public_data(root / "source")

    def test_verify_detects_material_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pins = write_synthetic_source(root / "source", synthetic_tasks())
            with patch.object(materials, "load_public_pins", return_value=pins):
                materials.prepare_materials(root / "source", root / "out")
                gold = root / "out" / "gold.json"
                gold.write_bytes(gold.read_bytes() + b" ")
                with self.assertRaisesRegex(ValueError, "hash or size mismatch"):
                    materials.verify_materials(root / "out")

    def test_verify_does_not_parse_gold(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pins = write_synthetic_source(root / "source", synthetic_tasks())
            with patch.object(materials, "load_public_pins", return_value=pins):
                manifest = materials.prepare_materials(root / "source", root / "out")
                # Deliberately non-JSON bytes demonstrate separation at verification.
                data = b"gold bytes are hashed, never decoded here"
                (root / "out" / "gold.json").write_bytes(data)
                manifest["files"]["gold.json"] = {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
                (root / "out" / "material_manifest.json").write_text(json.dumps(manifest))
                materials.verify_materials(root / "out")

    def test_explicit_fetch_has_fixed_url_timeout_and_size_bound(self):
        data = b"synthetic download"
        pin = {"path": "data/evaluation/00000000.json", "git_blob_sha1": materials.git_blob_sha1(data)}
        expected_url = ("https://raw.githubusercontent.com/arcprize/ARC-AGI-2/"
                        + materials.PUBLIC_COMMIT + "/" + pin["path"])
        class Response(io.BytesIO):
            def geturl(self):
                return expected_url
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "source"
            with patch.object(materials, "load_public_pins", return_value={"files": [pin]}), \
                    patch("urllib.request.urlopen", return_value=Response(data)) as fetch:
                result = materials.fetch_public_data(target)
                self.assertEqual(result["parent_count"], 1)
                self.assertEqual((target / "00000000.json").read_bytes(), data)
                self.assertEqual(fetch.call_args.args[0].full_url, expected_url)
                self.assertGreater(fetch.call_args.kwargs["timeout"], 0)
                self.assertLessEqual(fetch.call_args.kwargs["timeout"], materials.FETCH_TIMEOUT_SECONDS)
                with self.assertRaises(FileExistsError):
                    materials.fetch_public_data(target)
                self.assertEqual(fetch.call_count, 1)
            with patch.object(materials, "load_public_pins", return_value={"files": [pin]}), \
                    patch("urllib.request.urlopen", return_value=Response(b"x" * (materials.MAX_SOURCE_BYTES + 1))):
                with self.assertRaisesRegex(ValueError, "size bound"):
                    materials.fetch_public_data(Path(directory) / "too_large")


if __name__ == "__main__":
    unittest.main()
