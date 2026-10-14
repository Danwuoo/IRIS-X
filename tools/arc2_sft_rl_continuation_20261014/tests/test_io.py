"""Synthetic local I/O and collector-link tests; no evaluator/provider fixtures."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).absolute().parents[2]))
from arc2_sft_rl_continuation_20261014.io import (
    InputError, MAX_JSON_BYTES, read_json, report_links, write_new_json,
)


class LocalIOTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def save(self, raw):
        path = self.root / "report.json"
        path.write_bytes(raw)
        return path, hashlib.sha256(raw).hexdigest()

    def test_read_round_trip(self):
        path, sha = self.save(b'{"status":"STOPPED_INCOMPLETE"}')
        value, descriptor = read_json(path, sha)
        self.assertEqual(value, {"status": "STOPPED_INCOMPLETE"})
        self.assertEqual(descriptor, {"bytes": path.stat().st_size, "sha256": sha})

    def test_changed_hash(self):
        path, sha = self.save(b"{}")
        path.write_bytes(b'{"changed":true}')
        with self.assertRaisesRegex(InputError, "input_hash"):
            read_json(path, sha)

    def test_strict_json(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}', b'[]', b'\xff', b'{'):
            with self.subTest(raw=raw):
                path, sha = self.save(raw)
                with self.assertRaises(InputError):
                    read_json(path, sha)

    def test_bad_hash(self):
        path, _ = self.save(b"{}")
        for sha in (None, True, "A" * 64, "short"):
            with self.assertRaises(InputError):
                read_json(path, sha)

    def test_symlink_and_parent_symlink(self):
        path, sha = self.save(b"{}")
        alias = self.root / "alias.json"
        alias.symlink_to(path)
        with self.assertRaisesRegex(InputError, "symlink_path"):
            read_json(alias, sha)
        linked = self.root / "linked"
        linked.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(InputError, "symlink_path"):
            read_json(linked / path.name, sha)

    def test_hardlink_and_fifo_rejected(self):
        path, sha = self.save(b"{}")
        os.link(path, self.root / "hardlink.json")
        with self.assertRaisesRegex(InputError, "regular_single_link_input"):
            read_json(path, sha)
        if hasattr(os, "mkfifo"):
            fifo = self.root / "fifo"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(InputError, "regular_single_link_input"):
                read_json(fifo, sha)

    def test_oversized_input_rejected_before_read(self):
        path = self.root / "oversized.json"
        with path.open("wb") as stream:
            stream.truncate(MAX_JSON_BYTES + 1)
        with self.assertRaisesRegex(InputError, "input_size"):
            read_json(path, "0" * 64)

    def test_no_traversal(self):
        path, sha = self.save(b"{}")
        with self.assertRaisesRegex(InputError, "path_traversal"):
            read_json(self.root / ".." / self.root.name / path.name, sha)

    def test_atomic_write_refuses_overwrite(self):
        path = self.root / "output.json"
        descriptor = write_new_json(path, {"offline": True})
        before = path.read_bytes()
        self.assertEqual(hashlib.sha256(before).hexdigest(), descriptor["sha256"])
        with self.assertRaisesRegex(InputError, "output_exists"):
            write_new_json(path, {"replacement": True})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.root.glob(".arc2-report-*")), [])

    def test_publication_failure_cleans_temporary(self):
        with mock.patch("arc2_sft_rl_continuation_20261014.io.os.link", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                write_new_json(self.root / "output.json", {"offline": True})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_output_parent_must_exist_and_be_regular_path(self):
        with self.assertRaisesRegex(InputError, "output_parent_missing"):
            write_new_json(self.root / "absent" / "output.json", {})
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(InputError, "symlink_path"):
            write_new_json(alias / "output.json", {})


class LinkTests(unittest.TestCase):
    def setUp(self):
        self.descriptor = {"bytes": 200, "sha256": "a" * 64}
        self.retrieval_descriptor = {"bytes": 300, "sha256": "b" * 64}
        self.checkpoint_descriptor = {"bytes": 400, "sha256": "c" * 64}
        self.report = {"provider_status": "ERROR"}
        for key in ("operational_success", "comparison_complete", "compute_matched", "comparison_eligible",
                    "public_benchmark_evidence_eligible", "goal_met", "public_goal_met"):
            self.report[key] = False
        self.checkpoint = {
            **self.report, "status": "TERMINAL_EVIDENCE_VERIFIED", "automatic_retry": False,
            "validation": {**self.descriptor, "path": "/never-open-this-private-reference"},
            "retrieval": self.retrieval_descriptor,
        }
        self.retrieval = {"format": "irisx/rlvr-selected-retrieval-v1", "numeric_output_version": 999,
                          "before": {"status": "ERROR"}, "after": {"status": "ERROR"},
                          "inventory_scope": "selected_outputs_only", "whole_provider_inventory_verified": False}

    def linked(self):
        return report_links(self.report, self.descriptor, checkpoint=self.checkpoint,
                            checkpoint_descriptor=self.checkpoint_descriptor, retrieval=self.retrieval,
                            retrieval_descriptor=self.retrieval_descriptor)

    def test_explicit_links_are_not_authentication(self):
        with mock.patch("builtins.open", side_effect=AssertionError("must not follow descriptor")):
            result = self.linked()
        self.assertIs(result["local_descriptor_links_consistent"], True)
        self.assertIs(result["external_collection_authenticated"], False)
        self.assertEqual(result["recorded_numeric_output_version"], 999)
        self.assertNotIn("private-reference", json.dumps(result))

    def test_report_alone_does_not_invent_collection(self):
        result = report_links(self.report, self.descriptor)
        self.assertIsNone(result["local_descriptor_links_consistent"])
        self.assertIsNone(result["recorded_numeric_output_version"])

    def test_changed_validation_binding(self):
        self.checkpoint["validation"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(InputError, "checkpoint_validation_link"):
            self.linked()

    def test_inconsistent_boolean_and_status(self):
        for key, value in (("comparison_complete", 0), ("provider_status", "COMPLETE")):
            original = self.checkpoint[key]
            self.checkpoint[key] = value
            with self.assertRaises(InputError):
                self.linked()
            self.checkpoint[key] = original

    def test_partial_retrieval_or_different_bracket_rejected(self):
        with self.assertRaisesRegex(InputError, "retrieval_requires_checkpoint"):
            report_links(self.report, self.descriptor, retrieval=self.retrieval, retrieval_descriptor=self.retrieval_descriptor)
        self.retrieval["after"]["status"] = "RUNNING"
        with self.assertRaisesRegex(InputError, "retrieval_bracket"):
            self.linked()

    def test_numeric_version_bool_rejected(self):
        self.retrieval["numeric_output_version"] = True
        with self.assertRaisesRegex(InputError, "retrieval_version"):
            self.linked()


if __name__ == "__main__":
    unittest.main()
