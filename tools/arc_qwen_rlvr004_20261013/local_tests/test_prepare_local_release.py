"""Local restoration rejection tests; never synthesize the missing private ZIP."""
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.arc_qwen_rlvr004_20261013.publication_local import prepare_local_release as prepare


REPO = Path(__file__).resolve().parents[3]
DELIVERY = REPO / ".irisx/imports/rlvr004-code17-20261013/release"


class PathAndArchiveGuards(unittest.TestCase):
    def test_relative_names_reject_windows_and_zip_traversal(self):
        for name in ("", "../file", "/absolute", "a/../b", "a//b", "a\\b", "C:/file", "a/./b"):
            with self.subTest(name=name), self.assertRaises(prepare.PreparationError):
                prepare.relative_name(name)
        self.assertEqual(prepare.relative_name("producer-source/owned_runtime/release.py"),
                         "producer-source/owned_runtime/release.py")

    def test_duplicate_and_nonfinite_json_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'[]'):
            with self.subTest(raw=raw), self.assertRaises(prepare.PreparationError):
                prepare.strict_json(raw)

    def test_reparse_directory_rejected_before_tree_traversal(self):
        information = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_file_attributes=0x400)
        with patch.object(Path, "lstat", return_value=information):
            with self.assertRaisesRegex(prepare.PreparationError, "reparse"):
                prepare.ordinary_path(Path("linked-directory"))

    def test_small_fake_archive_cannot_satisfy_original_predecessor(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fake.evidence.zip"
            path.write_bytes(b"PK\x03\x04source-complete is not operational evidence")
            with self.assertRaisesRegex(prepare.PreparationError, "exact original predecessor"):
                prepare.verify_predecessor(path)

    def test_missing_predecessor_is_not_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "missing.evidence.zip"
            with self.assertRaises(FileNotFoundError):
                prepare.verify_predecessor(path)
            self.assertFalse(path.exists())

    def test_hash_checks_reject_same_size_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.py"
            path.write_bytes(b"one")
            expected = prepare.file_descriptor(path)
            path.write_bytes(b"two")
            with self.assertRaisesRegex(prepare.PreparationError, "descriptor mismatch"):
                prepare.checked_bytes(path, expected)

    def test_source_read_cap_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "large"
            path.write_bytes(b"12345")
            with self.assertRaises(prepare.PreparationError):
                prepare.file_descriptor(path, cap=4)

    def test_existing_output_rejected_before_assembly(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            output = repo / ".irisx/existing"
            output.mkdir(parents=True)
            with patch.object(prepare.subprocess, "run", side_effect=AssertionError("must not execute")):
                with self.assertRaisesRegex(prepare.PreparationError, "fresh output"):
                    prepare.prepare_local_release(repository_root=repo, delivery_root=repo / "delivery",
                                                  predecessor_evidence=repo / "evidence", output_root=output)

    def test_output_outside_owner_scratch_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            with self.assertRaisesRegex(prepare.PreparationError, "inside repository .irisx"):
                prepare.prepare_local_release(repository_root=repo, delivery_root=repo / "delivery",
                                              predecessor_evidence=repo / "evidence", output_root=repo / "output")

    def test_input_output_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            delivery = repo / ".irisx/delivery"
            delivery.mkdir(parents=True)
            with self.assertRaisesRegex(prepare.PreparationError, "overlap"):
                prepare.prepare_local_release(repository_root=repo, delivery_root=delivery,
                                              predecessor_evidence=repo / "evidence", output_root=delivery / "output")

    def test_actual_code17_input_pins_are_consistent(self):
        for name in ("runtime_assembly.py", "runtime-path-map.json"):
            raw = (REPO / prepare.DEPLOYMENT / name).read_bytes()
            self.assertEqual(prepare.sha(raw), prepare.PINS[name])
        for name in ("publication-manifest.json", "ASSEMBLY-INVENTORY.json"):
            raw = (REPO / prepare.DEPLOYMENT / "release" / name).read_bytes()
            self.assertEqual(prepare.sha(raw), prepare.PINS[name])

    @unittest.skipUnless(DELIVERY.is_dir(), "authorized source delivery is not installed")
    def test_actual_source_complete_delivery_still_requires_private_original(self):
        scratch = REPO / ".irisx"
        with tempfile.TemporaryDirectory(prefix="code17-restoration-rejection-", dir=scratch) as temporary:
            base = Path(temporary)
            fake = base / "not-the-original.evidence.zip"
            fake.write_bytes(b"not the original private archive")
            output = base / "candidate"
            with patch.object(prepare.subprocess, "run", side_effect=AssertionError("must not execute")):
                with self.assertRaisesRegex(prepare.PreparationError, "exact original predecessor"):
                    prepare.prepare_local_release(repository_root=REPO, delivery_root=DELIVERY,
                                                  predecessor_evidence=fake, output_root=output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
