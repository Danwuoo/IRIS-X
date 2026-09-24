"""Shared offline regressions for interrupted retrieval and UTF-8 logs."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

from irisx.arc_nvarc_transport import resume_digest_member, run_utf8_logged_command
from irisx.errors import ValidationError


class NvarcTransportIOTests(unittest.TestCase):
    def test_interrupted_member_resumes_only_same_digest(self) -> None:
        payload = ("source-verified-格子".encode("utf-8") * 100)
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "artifact.bin"
            offsets = []

            def interrupted(offset):
                offsets.append(offset)
                yield payload[offset:200]
                raise ConnectionError("simulated interrupted transfer")

            with self.assertRaises(ConnectionError):
                resume_digest_member(target, expected_bytes=len(payload),
                                     expected_sha256=digest, chunks_from_offset=interrupted)
            self.assertFalse(target.exists())
            self.assertEqual(200, (Path(temp) / "artifact.bin.part").stat().st_size)

            def continuation(offset):
                offsets.append(offset)
                yield payload[offset:]

            self.assertEqual(target, resume_digest_member(target,
                expected_bytes=len(payload), expected_sha256=digest,
                chunks_from_offset=continuation))
            self.assertEqual([0, 200], offsets)
            self.assertEqual(payload, target.read_bytes())
            self.assertFalse((Path(temp) / "artifact.bin.part").exists())
            with self.assertRaises(ValidationError):
                resume_digest_member(target, expected_bytes=len(payload),
                                     expected_sha256="0" * 64,
                                     chunks_from_offset=lambda _: ())

    def test_utf8_log_retains_non_ascii_without_console_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "retrieval.log"
            code = run_utf8_logged_command([sys.executable, "-c",
                "print('繁體中文 🧪 model-ready')"], log)
            self.assertEqual(0, code)
            self.assertEqual("繁體中文 🧪 model-ready\n", log.read_text(encoding="utf-8"))
            with self.assertRaises(ValidationError):
                run_utf8_logged_command([sys.executable, "-c", "print(1)"], log)
