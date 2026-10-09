"""Tiny synthetic archive tests; never execute or attest the real interpreter."""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

from tools import arc_next_offline_interpreter as portable


def digest(data):
    return hashlib.sha256(data).hexdigest()


@unittest.skipUnless(platform.system() == "Linux", "Private POSIX permissions require Linux")
class PortableInterpreterTests(unittest.TestCase):
    def setUp(self):
        # A native filesystem is necessary to exercise private modes/hardlinks.
        # No existing accepted interpreter or venv is touched.
        temporary = tempfile.TemporaryDirectory(prefix="irisx-portable-cpu-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.asset = self.base / "asset"
        self.asset.mkdir()
        self.destination = self.base / "prepared"
        elf = bytearray(64)
        elf[:6] = b"\x7fELF\x02\x01"
        elf[18:20] = (62).to_bytes(2, "little")
        # An ELF header fixture, deliberately not a runnable Python executable.
        self.files = {
            portable.EXECUTABLE: (bytes(elf), 0o755),
            portable.SYSCONFIG: (b"build_time_vars = {'prefix': '/install', 'LIBDIR': '/install/lib', "
                                 b"'AR': '/tools/llvm/bin/llvm-ar', 'CC': 'clang -pthread', 'CXX': 'clang++'}\n", 0o644),
            portable.MAKEFILE: (b"prefix= /install\nCC= clang -pthread\nCXX= clang++\nAR= /tools/llvm/bin/llvm-ar\n", 0o644),
            "python/include/python3.12/Python.h": (b"/* synthetic header */\n", 0o644),
            "python/lib/libpython3.12.so.1.0": (bytes(elf), 0o644),
            "python/lib/python3.12/LICENSE.txt": (b"Synthetic fixture only\n", 0o644),
        }
        self.links = {"python/bin/python": "python3.12"}
        self.write_archive()
        for name, content in {"source-receipt.json": b'{"synthetic_fixture":true}\n',
                              "licenses/fixture.txt": b"Synthetic archive, no upstream attestation\n"}.items():
            path = self.asset / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(content)
        self.manifest = {
            "format": portable.FORMAT, "target": portable.TARGET,
            "archive": {"filename": portable.STORED_ARCHIVE_NAME,
                        "upstream_filename": portable.ARCHIVE_NAME, "bytes": self.archive_size,
                        "sha256": self.archive_sha, "source_url": portable.SOURCE_URL},
            "members": {name: {"kind": "file", "bytes": len(body), "sha256": digest(body), "mode": mode}
                        for name, (body, mode) in self.files.items()},
            "companions": {name: {"bytes": len((self.asset / name).read_bytes()),
                                  "sha256": digest((self.asset / name).read_bytes())}
                           for name in ("source-receipt.json", "licenses/fixture.txt")},
        }
        self.manifest["members"].update({name: {"kind": "symlink", "target": target}
                                          for name, target in self.links.items()})
        self.refresh_manifest()
        # Only the synthetic archive hash/size are substituted, never host,
        # path, member, source identity, relocation or prepared-tree checks.
        self.enterContext(mock.patch.object(portable, "ARCHIVE_BYTES", self.archive_size))
        self.enterContext(mock.patch.object(portable, "ARCHIVE_SHA256", self.archive_sha))
        self.enterContext(mock.patch.object(subprocess, "run", side_effect=AssertionError("execution forbidden")))
        self.enterContext(mock.patch.object(subprocess, "Popen", side_effect=AssertionError("execution forbidden")))
        self.enterContext(mock.patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")))

    def write_archive(self):
        path = self.asset / portable.STORED_ARCHIVE_NAME
        with tarfile.open(path, "w:gz", format=tarfile.USTAR_FORMAT) as archive:
            for name, (body, mode) in self.files.items():
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(body), mode
                archive.addfile(member, io.BytesIO(body))
            for name, target in self.links.items():
                member = tarfile.TarInfo(name)
                member.type, member.linkname, member.mode = tarfile.SYMTYPE, target, 0o777
                archive.addfile(member)
        self.archive_sha = digest(path.read_bytes())
        self.archive_size = path.stat().st_size

    def refresh_manifest(self):
        body = (json.dumps(self.manifest, indent=2, sort_keys=True) + "\n").encode()
        (self.asset / portable.MANIFEST_NAME).write_bytes(body)
        self.manifest_sha = digest(body)

    def prepare(self):
        return portable.prepare_interpreter(self.asset, self.manifest_sha, self.destination)

    def assert_rejected_without_destination(self, message):
        with self.assertRaisesRegex(portable.OfflineInterpreterError, message):
            self.prepare()
        self.assertFalse(self.destination.exists())

    def test_preparation_relocation_and_cached_revalidation_run_nothing(self):
        receipt = self.prepare()
        self.assertEqual(receipt["interpreter_executions"], 0)
        self.assertEqual(receipt["network_calls"], 0)
        self.assertEqual(receipt["verified_member_count"], 7)
        self.assertEqual(self.prepare(), receipt)
        config = ast.literal_eval(ast.parse((self.destination / portable.SYSCONFIG).read_text()).body[0].value)
        self.assertEqual(config["prefix"], str(self.destination / "python"))
        self.assertEqual(config["LIBDIR"], str(self.destination / "python/lib"))
        self.assertEqual((config["AR"], config["CC"], config["CXX"]), ("ar", "cc -pthread", "c++"))
        self.assertEqual(os.readlink(self.destination / "python/bin/python"), "python3.12")
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o700)
        self.assertFalse((self.destination / portable.INCOMPLETE_NAME).exists())

    def test_wrong_host_stops_before_reading_assets(self):
        for name, value in (("system", "Windows"), ("machine", "aarch64"), ("libc_ver", ("glibc", "2.27"))):
            with self.subTest(host=name), mock.patch.object(portable.platform, name, return_value=value), \
                 mock.patch.object(portable, "_asset", side_effect=AssertionError("asset access forbidden")):
                with self.assertRaises(portable.OfflineInterpreterError):
                    self.prepare()
                self.assertFalse(self.destination.exists())

    def test_manifest_pin_and_duplicate_json_rejected(self):
        with self.assertRaisesRegex(portable.OfflineInterpreterError, "manifest hash"):
            portable.prepare_interpreter(self.asset, "0" * 64, self.destination)
        body = b'{"format":1,"format":2}'
        (self.asset / portable.MANIFEST_NAME).write_bytes(body)
        self.manifest_sha = digest(body)
        self.assert_rejected_without_destination("Duplicate JSON key")

    def test_source_identity_and_target_remain_locked(self):
        self.manifest["archive"]["source_url"] = "https://example.invalid/substitute"
        self.refresh_manifest()
        self.assert_rejected_without_destination("Unapproved interpreter archive")
        self.manifest["archive"]["source_url"] = portable.SOURCE_URL
        self.manifest["target"] = dict(portable.TARGET, python="3.13.0")
        self.refresh_manifest()
        self.assert_rejected_without_destination("Unsupported interpreter manifest")

    def test_archive_bytes_and_companion_hashes_rejected(self):
        archive = self.asset / portable.STORED_ARCHIVE_NAME
        original = archive.read_bytes()
        archive.write_bytes(original + b"changed")
        self.assert_rejected_without_destination("archive hash/size")
        archive.write_bytes(original)
        (self.asset / "source-receipt.json").write_bytes(b"changed")
        self.assert_rejected_without_destination("Companion hash mismatch")

    def test_unexpected_asset_and_symlink_are_rejected(self):
        extra = self.asset / "unexpected"
        extra.write_bytes(b"x")
        self.assert_rejected_without_destination("Unexpected/missing")
        extra.unlink()
        extra.symlink_to("source-receipt.json")
        self.assert_rejected_without_destination("Symlink in interpreter asset")

    def test_member_inventory_disagreement_stops_before_extraction(self):
        self.manifest["members"]["python/include/python3.12/Python.h"]["sha256"] = "0" * 64
        self.refresh_manifest()
        self.assert_rejected_without_destination("Archive member manifest mismatch")

    def test_unsafe_archive_records_rejected(self):
        for label in ("traversal", "escape link", "non-x86 ELF", "special permissions"):
            with self.subTest(archive=label):
                files, links = dict(self.files), dict(self.links)
                if label == "traversal":
                    self.files["python/../outside"] = (b"x", 0o644)
                elif label == "escape link":
                    self.links["python/bin/python"] = "../../outside"
                elif label == "non-x86 ELF":
                    self.files[portable.EXECUTABLE] = (b"not an ELF executable", 0o755)
                else:
                    self.files[portable.EXECUTABLE] = (self.files[portable.EXECUTABLE][0], 0o4755)
                self.write_archive()
                with self.assertRaises(portable.OfflineInterpreterError):
                    portable._archive_records(self.asset / portable.STORED_ARCHIVE_NAME)
                self.assertFalse(self.destination.exists())
                self.files, self.links = files, links

    def test_build_config_code_is_never_evaluated(self):
        payload = b"build_time_vars = __import__('os').system('must-never-execute')\n"
        with mock.patch.object(os, "system", side_effect=AssertionError("execution forbidden")):
            with self.assertRaises(ValueError):
                portable._relocated(payload, portable.SYSCONFIG, self.destination)

    def test_unsafe_and_input_overlapping_destinations_rejected(self):
        for target in (self.asset / "prepared", self.base / "unsafe space"):
            with self.subTest(destination=str(target)), self.assertRaises(portable.OfflineInterpreterError):
                portable.prepare_interpreter(self.asset, self.manifest_sha, target)
            self.assertFalse(target.exists())

    def test_changed_cached_tree_and_receipt_fail_closed_without_repair(self):
        self.prepare()
        executable = self.destination / portable.EXECUTABLE
        original = executable.read_bytes()
        executable.write_bytes(original + b"changed")
        with self.assertRaisesRegex(portable.OfflineInterpreterError, "file mismatch"):
            self.prepare()
        self.assertEqual(executable.read_bytes(), original + b"changed")
        executable.write_bytes(original)
        receipt = self.destination / portable.RECEIPT_NAME
        receipt.write_bytes(receipt.read_bytes() + b" ")
        with self.assertRaisesRegex(portable.OfflineInterpreterError, "receipt mismatch"):
            self.prepare()

    def test_interrupted_tree_permissions_and_hardlinks_fail_closed(self):
        self.prepare()
        marker = self.destination / portable.INCOMPLETE_NAME
        marker.write_bytes(b"interrupted")
        with self.assertRaisesRegex(portable.OfflineInterpreterError, "Interrupted"):
            self.prepare()
        marker.unlink()
        self.destination.chmod(0o755)
        with self.assertRaisesRegex(portable.OfflineInterpreterError, "private/owned"):
            self.prepare()
        self.destination.chmod(0o700)
        os.link(self.destination / portable.EXECUTABLE, self.base / "linked-executable")
        with self.assertRaisesRegex(portable.OfflineInterpreterError, "file mismatch"):
            self.prepare()


if __name__ == "__main__":
    unittest.main()
