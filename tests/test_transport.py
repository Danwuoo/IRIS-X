from __future__ import annotations

import io
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

import support  # noqa: F401

from irisx.canonical import canonical_bytes, digest_bytes
from irisx.errors import ValidationError
from irisx.transport import ArchiveLimits, TRIAL_LIMITS, build_zip_bytes, verify_zip_bytes


def raw_zip(entries: list[tuple[zipfile.ZipInfo, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for info, data in entries:
            archive.writestr(info, data)
    return buffer.getvalue()


def regular_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = zipfile.ZIP_STORED
    return info


class TransportTests(unittest.TestCase):
    def test_build_is_byte_reproducible_and_closed_world(self) -> None:
        files = {"b/data.bin": b"two", "a/data.bin": b"one"}
        first = build_zip_bytes("irisx/test", "test-package", files, {"binding": "fixed"}, limits=TRIAL_LIMITS)
        second = build_zip_bytes("irisx/test", "test-package", files, {"binding": "fixed"}, limits=TRIAL_LIMITS)
        self.assertEqual(first, second)
        manifest, contents = verify_zip_bytes(first, limits=TRIAL_LIMITS, package_kind="irisx/test")
        self.assertEqual(contents, files)
        self.assertEqual([entry["path"] for entry in manifest["files"]], sorted(files))

    def test_builder_rejects_traversal_absolute_backslash_and_reserved_paths(self) -> None:
        for path in ("../escape", "/absolute", "C:/absolute", "a\\b", "manifest.json"):
            with self.subTest(path=path), self.assertRaises(ValidationError):
                build_zip_bytes("irisx/test", "test-package", {path: b"x"}, {}, limits=TRIAL_LIMITS)

    def test_verifier_rejects_duplicate_entries(self) -> None:
        data = b"x"
        manifest = {
            "format": "irisx/closed-world-zip",
            "format_version": "1.0",
            "package_kind": "irisx/test",
            "package_id": "test-package",
            "files": [{"path": "a", "byte_size": 1, "content_digest": digest_bytes(data)}],
            "metadata": {},
        }
        archive = raw_zip(
            [
                (regular_info("manifest.json"), canonical_bytes(manifest, newline=True)),
                (regular_info("a"), data),
                (regular_info("a"), data),
            ]
        )
        with self.assertRaisesRegex(ValidationError, "duplicate ZIP entry"):
            verify_zip_bytes(archive, limits=TRIAL_LIMITS)

    def test_verifier_rejects_symbolic_links(self) -> None:
        data = b"target"
        manifest = {
            "format": "irisx/closed-world-zip",
            "format_version": "1.0",
            "package_kind": "irisx/test",
            "package_id": "test-package",
            "files": [{"path": "link", "byte_size": len(data), "content_digest": digest_bytes(data)}],
            "metadata": {},
        }
        link = zipfile.ZipInfo("link", (1980, 1, 1, 0, 0, 0))
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive = raw_zip([(regular_info("manifest.json"), canonical_bytes(manifest, newline=True)), (link, data)])
        with self.assertRaisesRegex(ValidationError, "unsafe non-regular"):
            verify_zip_bytes(archive, limits=TRIAL_LIMITS)

    def test_verifier_rejects_undeclared_missing_and_digest_mismatch(self) -> None:
        valid = build_zip_bytes("irisx/test", "test-package", {"a": b"x"}, {}, limits=TRIAL_LIMITS)
        with zipfile.ZipFile(io.BytesIO(valid)) as source:
            manifest = source.read("manifest.json")
        undeclared = raw_zip(
            [
                (regular_info("manifest.json"), manifest),
                (regular_info("a"), b"x"),
                (regular_info("extra"), b"x"),
            ]
        )
        with self.assertRaisesRegex(ValidationError, "closed-world mismatch"):
            verify_zip_bytes(undeclared, limits=TRIAL_LIMITS)
        missing = raw_zip([(regular_info("manifest.json"), manifest)])
        with self.assertRaisesRegex(ValidationError, "closed-world mismatch"):
            verify_zip_bytes(missing, limits=TRIAL_LIMITS)
        changed = raw_zip([(regular_info("manifest.json"), manifest), (regular_info("a"), b"y")])
        with self.assertRaisesRegex(ValidationError, "digest mismatch"):
            verify_zip_bytes(changed, limits=TRIAL_LIMITS)

    def test_expansion_size_and_count_limits_fail_before_reading_content(self) -> None:
        limits = ArchiveLimits(max_files=1, max_file_bytes=2, max_total_bytes=2, max_archive_bytes=4096)
        with self.assertRaisesRegex(ValidationError, "file-count"):
            build_zip_bytes("irisx/test", "test-package", {"a": b"x", "b": b"y"}, {}, limits=limits)
        with self.assertRaisesRegex(ValidationError, "byte limit"):
            build_zip_bytes("irisx/test", "test-package", {"a": b"xxx"}, {}, limits=limits)

    def test_verifier_rejects_trailing_bytes_and_noncanonical_metadata(self) -> None:
        valid = build_zip_bytes("irisx/test", "test-package", {"a": b"x"}, {}, limits=TRIAL_LIMITS)
        with self.assertRaisesRegex(ValidationError, "trailing bytes"):
            verify_zip_bytes(valid + b"trailing", limits=TRIAL_LIMITS)
        with zipfile.ZipFile(io.BytesIO(valid)) as source:
            manifest = source.read("manifest.json")
        changed = regular_info("a")
        changed.date_time = (2026, 1, 1, 0, 0, 0)
        archive = raw_zip([(regular_info("manifest.json"), manifest), (changed, b"x")])
        with self.assertRaisesRegex(ValidationError, "non-canonical ZIP metadata"):
            verify_zip_bytes(archive, limits=TRIAL_LIMITS)


if __name__ == "__main__":
    unittest.main()
