"""Faithful synthetic contract tests. No real corpus, training or network claims."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tests.platform_requirements import requires_linux

from tools.cpt_data_admission_20261021.admission import (
    AdmissionError, LIMITS, admit, canonical_task, encoded, file_pin,
    prompt_task, validate_task, verify_bundle, _rotate, _transform,
)


def task(style=0, tests=1):
    # Different shapes/patterns are intentionally not D4/color equivalents.
    inp = [[0, 1, 0], [1, 0, 1]] if style == 0 else [[0, 1, 2, 0], [0, 0, 1, 2], [2, 1, 0, 0]]
    if style == 2:
        inp = [[0, 1, 0, 0, 1], [1, 1, 1, 0, 0], [0, 0, 0, 1, 0]]
    return {"train": [{"input": inp, "output": inp}],
            "test": [{"input": inp, "output": inp} for _ in range(tests)]}


def record(name, node="train", style=0, tests=1):
    return {"record_id": name, "lineage_id": node, "source_locator": "synthetic:" + name,
            "task": task(style, tests), "transforms": []}


class Fixture:
    def __init__(self, root, records=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "LICENSE.txt").write_text("Synthetic test fixture released under MIT for contract testing.\n")
        (self.root / "provenance.txt").write_text("Self-authored synthetic grids. No external corpus; no ReArc.\n")
        self.records = records if records is not None else [record("train-ok"), record("eval-ok", "eval", 1, tests=2)]
        self.registry = {
            "schema_version": 1, "scope": "synthetic-fixtures", "artifacts": {},
            "sources": {"fixture": self.source()},
            "lineage": {"train": self.node("train", "train-family"),
                        "eval": self.node("evaluation", "eval-family")},
            "shards": [{"source_id": "fixture", "artifact_id": "data"}],
        }

    @staticmethod
    def source():
        return {"url": "fixture://self-authored-grid-contract", "revision": "1" * 40, "revision_kind": "git_commit",
                "parents": [], "origin_status": "resolved", "rearc_status": "clear", "evidence": ["provenance"],
                "license": {"status": "resolved", "spdx": "MIT", "evidence": ["license"], "notices": []}}

    @staticmethod
    def node(split="train", family="train-family", parents=None, source="fixture"):
        return {"source_id": source, "parents": parents or [], "family_ids": [family],
                "original_split": split, "iris_split": split, "evidence": ["provenance"]}

    def write(self, raw=None):
        (self.root / "data.jsonl").write_bytes(raw if raw is not None else b"".join(encoded(r) + b"\n" for r in self.records))
        for key, filename in (("data", "data.jsonl"), ("license", "LICENSE.txt"), ("provenance", "provenance.txt")):
            self.registry["artifacts"][key] = {"path": filename, **file_pin(self.root / filename, 64 * 1024 * 1024)}
        self.path = self.root / "registry.json"
        self.path.write_bytes(encoded(self.registry) + b"\n")
        self.sha = file_pin(self.path, LIMITS["max_registry_bytes"])["sha256"]
        return self

    def run(self, name="out", **kwargs):
        return admit(self.path, self.sha, self.root / name, **kwargs)

    def rows(self, relative, name="out"):
        return [json.loads(line) for line in (self.root / name / "bundle" / relative).read_text().splitlines()]

    def decisions(self, name="out"):
        return {r["record_id"]: r for r in self.rows("audit/decisions.jsonl", name)}


@requires_linux("POSIX fcntl locks, atomic directory seals and filesystem permissions")
class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def fixture(self, records=None):
        return Fixture(self.root, records)

    def test_positive_multitest_answer_free_export_and_exact_provenance(self):
        f = self.fixture().write()
        manifest = f.run()
        self.assertEqual(manifest["counts"], {"accepted": 2, "quarantine": 0, "reject": 0, "deduplicated": 0})
        self.assertEqual(manifest["query_counts"], {"train": 1, "evaluation": 2})
        prompts = f.rows("evaluation-inputs/evaluation.jsonl")
        self.assertEqual(set(prompts[0]), {"record_id", "task"})
        self.assertEqual(prompts[0]["task"], prompt_task(f.records[1]["task"]))
        self.assertEqual(len(prompts[0]["task"]["test"]), 2)
        self.assertTrue(all(set(pair) == {"input"} for pair in prompts[0]["task"]["test"]))
        gold = f.rows("evaluator-only/gold.jsonl")
        self.assertEqual([r["test_index"] for r in gold], [0, 1])
        self.assertEqual(len(f.rows("training/train.jsonl")), 1)
        for row in f.rows("audit/provenance.jsonl"):
            data = (self.root / "data.jsonl").read_bytes()[row["byte_offset"]:row["byte_offset"] + row["raw_bytes"]]
            self.assertEqual(hashlib.sha256(data).hexdigest(), row["raw_sha256"])
        self.assertEqual(manifest, verify_bundle(self.root / "out/bundle"))
        self.assertIn("not_training_ready", manifest["status"])

    def test_unanswered_eval_keeps_all_queries_without_fake_gold(self):
        f = self.fixture([record("eval", "eval", 1, tests=3)])
        for pair in f.records[0]["task"]["test"]:
            pair.pop("output")
        m = f.write().run()
        self.assertEqual(m["query_counts"], {"evaluation": 3})
        self.assertEqual(m["evaluation_gold_query_counts"], {})
        self.assertEqual(f.rows("evaluator-only/gold.jsonl"), [])

    def test_missing_licenses_origin_and_mutable_revision_quarantined(self):
        mutations = [lambda s: s.update(origin_status="unresolved"), lambda s: s.update(rearc_status="unresolved"),
                     lambda s: s.update(revision="main"), lambda s: s["license"].update(status="conflict"),
                     lambda s: s["license"].update(evidence=[]), lambda s: s.update(evidence=[]),
                     lambda s: s.update(parents=["unresolved-source"])]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                f = Fixture(self.root / str(i), [record("x")])
                mutate(f.registry["sources"]["fixture"])
                m = f.write().run()
                self.assertEqual(m["counts"]["quarantine"], 1)
                self.assertEqual(f.rows("training/train.jsonl"), [])

    def test_rearc_and_derivatives_denied_even_with_clean_child_labels(self):
        for marker in ("source", "source-ancestor", "row", "node", "locator", "declared"):
            with self.subTest(marker=marker):
                f = Fixture(self.root / marker, [record("child")])
                if marker in ("source", "source-ancestor"):
                    source = f.registry["sources"]["fixture"]
                    if marker == "source-ancestor":
                        source["parents"] = ["upstream"]
                        source = f.registry["sources"]["upstream"] = f.source()
                    source["url"] = "https://github.com/michaelhodel/re-arc"
                elif marker == "row":
                    f.records[0]["record_id"] = "rearc-derived"
                elif marker == "node":
                    f.registry["lineage"]["rearc-parent"] = f.node()
                    f.registry["lineage"]["train"]["parents"] = ["rearc-parent"]
                elif marker == "locator":
                    f.records[0]["source_locator"] = "nvarc/re_arc/1"
                else:
                    f.registry["sources"]["fixture"]["rearc_status"] = "derived"
                m = f.write().run()
                self.assertEqual(m["counts"]["reject"], 1)
                self.assertIn("excluded_rearc", next(iter(f.decisions().values()))["reasons"])

    def test_all_ancestors_inspected_and_graph_cycles_fail_closed(self):
        for parents, reason in [(["safe", "eval"], "nontraining_ancestry"),
                                (["safe", "missing"], "unresolved_lineage_node"),
                                (["safe", "train"], "lineage_cycle")]:
            with self.subTest(parents=parents):
                f = Fixture(self.root / reason, [record("child")])
                f.registry["lineage"]["safe"] = f.node()
                f.registry["lineage"]["train"]["parents"] = parents
                f.write().run()
                self.assertIn(reason, f.decisions()["child"]["reasons"])
                self.assertEqual(f.decisions()["child"]["status"], "quarantine")

    def test_protected_eval_split_cannot_be_renamed_dev(self):
        f = self.fixture([record("x", "eval", 1)])
        f.registry["lineage"]["eval"]["iris_split"] = "dev"
        f.write().run()
        self.assertIn("protected_split_relabel", f.decisions()["x"]["reasons"])
        self.assertEqual(f.rows("evaluation-inputs/dev.jsonl"), [])

    def test_family_conflict_quarantines_every_row_order_independently(self):
        for reverse in (False, True):
            f = Fixture(self.root / str(reverse), [record("a"), record("b", "dev", 1), record("c", "sibling", 2)])
            f.registry["lineage"]["dev"] = f.node("dev", "shared")
            f.registry["lineage"]["train"]["family_ids"] = ["shared"]
            f.registry["lineage"]["sibling"] = f.node("train", "shared")
            if reverse:
                f.records.reverse()
            m = f.write().run()
            self.assertEqual(m["counts"]["quarantine"], 3)
            self.assertTrue(all("cross_split_family_or_content" in r["reasons"] for r in f.decisions().values()))

    def test_unmaterialized_registry_family_members_cannot_launder_window(self):
        for mode in ("evaluation-family", "evaluation-descendant", "unresolved-sibling", "unresolved-source", "rearc-sibling"):
            f = Fixture(self.root / mode, [record("train-only")])
            if mode == "evaluation-family":
                f.registry["lineage"]["eval"]["family_ids"] = ["train-family"]
            elif mode == "evaluation-descendant":
                f.registry["lineage"]["eval"]["parents"] = ["train"]
            elif mode == "unresolved-sibling":
                f.registry["lineage"]["sibling"] = f.node(parents=["unresolved"])
            elif mode == "unresolved-source":
                f.registry["lineage"]["sibling"] = f.node(source="unresolved")
            else:
                f.registry["lineage"]["rearc-sibling"] = f.node()
            m = f.write().run()
            self.assertEqual(m["counts"]["accepted"], 0)
            self.assertEqual(f.rows("training/train.jsonl"), [])
            self.assertTrue(f.decisions()["train-only"]["reasons"])

    def test_artifact_paths_must_remain_inside_registry_root_without_symlinks(self):
        for mode in ("absolute", "parent", "symlink-file", "symlink-parent"):
            f = Fixture(self.root / mode).write()
            original = f.root / "LICENSE.txt"
            if mode == "absolute":
                path = str(original)
            elif mode == "parent":
                path = "../" + mode + "/LICENSE.txt"
            elif mode == "symlink-file":
                (f.root / "linked").symlink_to(original)
                path = "linked"
            else:
                (f.root / "linked").symlink_to(f.root, target_is_directory=True)
                path = "linked/LICENSE.txt"
            f.registry["artifacts"]["license"]["path"] = path
            f.path.write_bytes(encoded(f.registry) + b"\n")
            f.sha = file_pin(f.path, LIMITS["max_registry_bytes"])["sha256"]
            with self.assertRaisesRegex(AdmissionError, "artifact_path"):
                f.run()
            self.assertFalse((f.root / "out/bundle").exists())

    def test_joint_transform_dedup_and_global_visible_overlap(self):
        base = record("a")
        transformed = copy.deepcopy(base)
        transformed["record_id"] = "z"
        for pairs in transformed["task"].values():
            for pair in pairs:
                for key, grid in pair.items():
                    pair[key] = [[(cell + 4) % 10 for cell in row] for row in _rotate(grid)]
        self.assertEqual(canonical_task(base["task"]), canonical_task(transformed["task"]))
        f = self.fixture([transformed, base]).write()
        self.assertEqual(f.run()["counts"]["deduplicated"], 1)
        self.assertEqual(f.decisions()["a"]["status"], "accepted")
        self.assertEqual(f.decisions()["z"]["status"], "deduplicated")
        # Eval input can lack gold; visible canonical identity still blocks train.
        f2 = Fixture(self.root / "overlap", [record("train"), record("eval", "eval")])
        for pair in f2.records[1]["task"]["test"]:
            pair.pop("output")
        self.assertEqual(f2.write().run()["counts"]["quarantine"], 2)

    def test_content_equivalence_propagates_unmaterialized_eval_family_taint(self):
        f = self.fixture([record("clean-label"), record("tainted", "tainted")])
        f.registry["lineage"]["tainted"] = f.node("train", "eval-family")
        m = f.write().run()
        self.assertEqual(m["counts"]["quarantine"], 2)
        self.assertIn("registry_family_split_conflict", f.decisions()["clean-label"]["reasons"])
        self.assertEqual(f.rows("training/train.jsonl"), [])

    def test_malformed_source_and_lineage_values_never_crash_or_admit(self):
        paths = [("sources", "fixture", key) for key in Fixture.source()]
        paths += [("lineage", "train", key) for key in Fixture.node()]
        for n, (path, value) in enumerate((path, value) for path in paths for value in (None, True, 1, [], {}, [{}])):
            with self.subTest(path=path, value=value):
                f = Fixture(self.root / str(n), [record("x")])
                f.registry[path[0]][path[1]][path[2]] = value
                try:
                    m = f.write().run()
                except AdmissionError:
                    continue
                # Empty parent arrays are a legitimate resolved root.
                if path[-1] == "parents" and value == []:
                    continue
                self.assertEqual(m["counts"]["accepted"], 0)

    def test_source_graph_cycle_quarantined(self):
        f = self.fixture([record("x")])
        f.registry["sources"]["fixture"]["parents"] = ["parent"]
        f.registry["sources"]["parent"] = f.source()
        f.registry["sources"]["parent"]["parents"] = ["fixture"]
        f.write().run()
        self.assertIn("source_cycle_or_depth", f.decisions()["x"]["reasons"])

    def test_duplicate_record_ids_all_quarantined_not_first_wins(self):
        f = self.fixture([record("same"), record("same", style=1)]).write()
        m = f.run()
        self.assertEqual(m["counts"]["quarantine"], 2)
        self.assertEqual(f.rows("training/train.jsonl"), [])

    def test_strict_schema_grids_and_later_tests(self):
        bad = []
        row = record("x", tests=2); row["task"]["test"][1]["input"] = [[True]]; bad.append(row)
        row = record("x"); row["task"]["train"][0]["output"] = [[1], [2, 3]]; bad.append(row)
        row = record("x"); row["task"]["test"][0]["output"] = [[10]]; bad.append(row)
        row = record("x"); row["task"]["test"][0].pop("output"); bad.append(row)
        row = record("x", "eval", tests=2); row["task"]["test"][0].pop("output"); bad.append(row)
        row = record("x"); row["task"]["test"] = []; bad.append(row)
        row = record("x"); row["task"]["extra"] = "gold"; bad.append(row)
        row = record("x"); row["task"]["train"][0]["input"] = [[1.0]]; bad.append(row)
        row = record("x"); row["task"]["train"][0]["input"] = [[1] * 31]; bad.append(row)
        for i, row in enumerate(bad):
            with self.subTest(i=i):
                f = Fixture(self.root / str(i), [row]).write()
                self.assertEqual(f.run()["counts"]["reject"], 1)

    def test_duplicate_json_keys_and_nonfinite_are_rejected_not_coerced(self):
        for i, raw in enumerate((b'{"record_id":"a","record_id":"b"}\n', b'{"x":NaN}\n', b'\xff\n', b'\n')):
            f = Fixture(self.root / str(i)).write(raw=raw)
            self.assertEqual(f.run()["counts"]["reject"], 1)

    def test_source_hash_license_hash_and_registry_hash_fail_before_seal(self):
        for target in ("data.jsonl", "LICENSE.txt", "registry.json"):
            f = Fixture(self.root / target).write()
            with (f.root / target).open("ab") as stream:
                stream.write(b"tamper")
            with self.assertRaises(AdmissionError):
                f.run()
            self.assertFalse((f.root / "out/bundle").exists())

    def test_restart_manifest_and_files_byte_identical_to_uninterrupted(self):
        f = self.fixture().write()
        first = f.run("resumed", stop_after_records=1)
        self.assertEqual(first["status"], "paused_not_sealed")
        self.assertFalse((self.root / "resumed/bundle").exists())
        resumed = f.run("resumed")
        direct = f.run("direct")
        self.assertEqual(resumed, direct)
        self.assertEqual(f.run("resumed"), direct)
        for relative in resumed["outputs"]:
            self.assertEqual((self.root / "resumed/bundle" / relative).read_bytes(), (self.root / "direct/bundle" / relative).read_bytes())

    def test_restart_after_failed_export_reclassifies_from_original_rows(self):
        f = self.fixture([record("a"), record("z")]).write()
        with patch("tools.cpt_data_admission_20261021.admission._export", side_effect=RuntimeError("crash")):
            with self.assertRaisesRegex(RuntimeError, "crash"):
                f.run("crashed")
        self.assertEqual(f.run("crashed"), f.run("direct"))

    def test_restart_rejects_changed_bindings_and_database_tamper(self):
        f = self.fixture().write()
        f.run(stop_after_records=1)
        with self.assertRaisesRegex(AdmissionError, "restart_binding"):
            f.run(limits={"max_records": 3})
        db = sqlite3.connect(self.root / "out/state.sqlite")
        with db:
            db.execute("UPDATE rows SET base_result='{}' WHERE n=0")
        db.close()
        with self.assertRaisesRegex(AdmissionError, "restart_staged_record"):
            f.run()
        self.assertFalse((self.root / "out/bundle").exists())

    def test_resource_bounds_never_silently_truncate_or_seal(self):
        for name, limits in (("bytes", {"max_total_bytes": 1}), ("record", {"max_record_bytes": 5}), ("count", {"max_records": 1})):
            f = Fixture(self.root / name).write()
            with self.assertRaises(AdmissionError):
                f.run(limits=limits)
            self.assertFalse((f.root / "out/bundle").exists())

    def test_tampered_sealed_output_does_not_silently_rebuild(self):
        f = self.fixture().write(); f.run()
        path = self.root / "out/bundle/evaluation-inputs/evaluation.jsonl"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaises(AdmissionError):
            f.run()

    def test_no_program_execution_and_no_arbitrary_fields(self):
        f = self.fixture([record("x")])
        f.records[0]["program"] = "raise RuntimeError('must never execute')"
        f.write()
        with patch("subprocess.run", side_effect=AssertionError("no child execution")), patch("builtins.exec", side_effect=AssertionError("no exec")):
            self.assertEqual(f.run()["counts"]["reject"], 1)

    def test_cli_runs_offline_and_verifies_seal(self):
        f = self.fixture().write()
        command = [sys.executable, "-m", "tools.cpt_data_admission_20261021", "admit", "--registry", str(f.path),
                   "--registry-sha256", f.sha, "--output", str(self.root / "cli")]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        m = json.loads(result.stdout)
        self.assertEqual(m["counts"]["accepted"], 2)
        result = subprocess.run([sys.executable, "-m", "tools.cpt_data_admission_20261021", "verify", str(self.root / "cli/bundle")],
                                check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout), m)


if __name__ == "__main__":
    unittest.main()
