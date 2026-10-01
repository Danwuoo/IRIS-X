"""Independent fixture oracle for published-response I/O and no-exec recovery.

The executor is deliberately a test oracle; real NumPy/namespace execution is
covered separately by nvarc_m2_m3_strict. These fixtures are not teacher data.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

from irisx.arc_nvarc_datasets import sha_file
from irisx.arc_nvarc_sdg_artifacts import replay
from irisx.arc_nvarc_upstream import SOURCE
from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError


class GridOracle:
    def __init__(self):
        self.calls = 0

    def execute_entry(self, code, entry, **kwargs):
        self.calls += 1
        if entry == "generate_puzzle_input":
            value = kwargs["seed"]
            return [[value // 10, value % 10]]
        return [[(color + 1) % 10 for color in row] for row in kwargs["input_grid"]]


class NeverExecute:
    def execute_entry(self, *args, **kwargs):
        raise AssertionError("local packaging recovery must not execute a program")


class PublishedSDGArtifactTests(unittest.TestCase):
    def test_unicode_source_io_exact_pair_oracle_and_verified_zero_call_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            material = root / "material"
            material.mkdir()
            key = {"mix_name": "mix1", "summary_name1": "summary1", "summary_name2": "summary1",
                   "puzzle_name1": "00576224", "puzzle_name2": "84db8fc4"}
            input_code = ("```python\n# 中文 π: fixture only\nimport numpy as np\n"
                          "def generate_puzzle_input(seed): return np.array([[seed // 10, seed % 10]])\n"
                          "def test_input(grid): assert grid.shape == (1, 2)\n```")
            output_code = ("```python\n# 中文 π: fixture only\nimport numpy as np\n"
                           "def generate_puzzle_output(input_grid): return (input_grid + 1) % 10\n```")
            base = {"model_name": "fixture-oracle", "reasoning_level": "none", "prompt": "fixture only"}
            rows = {"summaries": [{**base, "summary_name": "summary1", "puzzle_name": parent,
                                   "completion": "fixture description"}
                                  for parent in (key["puzzle_name1"], key["puzzle_name2"])],
                    "mixtures": [{**base, **key, "completion": "fixture mix"}],
                    "inputs": [{**base, **key, "completion": input_code}],
                    "outputs": [{**base, **key, "sid": sid, "completion": output_code} for sid in range(20)]}
            members = []
            for group, values in rows.items():
                path = material / group / "data-00000.parquet"
                path.parent.mkdir()
                pq.write_table(pa.Table.from_pylist(values), path)
                members.append({"path": path.relative_to(material).as_posix(),
                                "bytes": path.stat().st_size, "sha256": sha_file(path)})
            (material / "acquisition.json").write_bytes(canonical_bytes({
                "state": "verified-partial-published-artifacts", "fixture_only": True,
                "dataset": "sorokin/nvarc-artifacts-puzzles/1", "members": members}, newline=True))
            catalog = root / "catalog.json"
            catalog.write_bytes(canonical_bytes({"training_ids": [key["puzzle_name1"], key["puzzle_name2"]],
                "evaluation_ids": [], "excluded_parent_ids": [key["puzzle_name1"]],
                "protected_categories": {"pilot": [key["puzzle_name1"]]}}, newline=True))
            original, recovered = root / "original", root / "recovered"
            executor = GridOracle()
            observation = replay(material, SOURCE, catalog, original, executor)
            self.assertEqual(630, executor.calls)
            self.assertEqual(30, observation["accepted_pairs"])
            expected_pairs = [{"input": [[i // 10, i % 10]],
                               "output": [[(i // 10 + 1) % 10, (i % 10 + 1) % 10]]} for i in range(30)]
            relative = Path("mix1/00576224/00576224_84db8fc4.json")
            self.assertEqual(expected_pairs, json.loads((original / "accepted-pairs" / relative).read_bytes()))
            frozen = {p.relative_to(original).as_posix(): sha_file(p) for p in original.rglob("*") if p.is_file()}
            resumed = replay(material, SOURCE, catalog, recovered, NeverExecute(), reuse=original)
            self.assertEqual((0, 630, 30), (resumed["new_program_invocations"],
                                          resumed["reused_program_invocations"], resumed["accepted_pairs"]))
            self.assertEqual(expected_pairs, json.loads((recovered / "accepted-pairs" / relative).read_bytes()))
            self.assertEqual(frozen, {p.relative_to(original).as_posix(): sha_file(p)
                                      for p in original.rglob("*") if p.is_file()})
            results = original / "program-results.jsonl"
            values = [json.loads(line) for line in results.read_bytes().splitlines()]
            values[-1]["result_digest"] = "sha256:" + "0" * 64
            results.write_bytes(b"".join(canonical_bytes(value, newline=True) for value in values))
            with self.assertRaisesRegex(ValidationError, "retained execution result"):
                replay(material, SOURCE, catalog, root / "tampered-results", NeverExecute(), reuse=original)
            shard = material / "outputs/data-00000.parquet"
            with shard.open("ab") as stream:
                stream.write(b"tampered")
            with self.assertRaisesRegex(ValidationError, "member bytes"):
                replay(material, SOURCE, catalog, root / "tampered-shard", NeverExecute())


if __name__ == "__main__":
    unittest.main()
