"""Real-process safe-file integration with synthetic, non-ARC audit records."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).absolute().parents[3]
CLI = ROOT / "tools/arc2_abc_continuation_20261014/cli.py"
POSIX_SAFE = os.name == "posix" and hasattr(os, "O_NOFOLLOW") and os.open in os.supports_dir_fd


@unittest.skipUnless(POSIX_SAFE, "reviewed file operations require no-follow POSIX descriptors")
class AuditCLIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "result.json"

    def command(self, *args):
        return [sys.executable, "-B", *(["-O"] if sys.flags.optimize else []), str(CLI), *map(str, args)]

    def run_cli(self, *args):
        return subprocess.run(self.command(*args), cwd=ROOT, text=True, capture_output=True,
                              timeout=30, check=False)

    def save(self, name, raw):
        if not isinstance(raw, bytes):
            raw = (json.dumps(raw, sort_keys=True, allow_nan=False) + "\n").encode()
        path = self.root / name
        path.write_bytes(raw)
        return path, hashlib.sha256(raw).hexdigest()

    def arguments(self, audit, audit_hash, context, context_hash):
        return ["--audit", audit, "--audit-sha256", audit_hash,
                "--context", context, "--context-sha256", context_hash,
                "--output", self.output]

    def fixture_arguments(self, **kwargs):
        from tools.arc2_abc_continuation_20261014.fixtures import synthetic_audit, audit_bytes
        audit, context = synthetic_audit(**kwargs)
        path, digest = self.save("audit.json", audit_bytes(audit))
        context["audit_sha256"] = digest
        declaration, declaration_hash = self.save("context.json", context)
        return self.arguments(path, digest, declaration, declaration_hash)

    def assert_rejected(self, result, code=None):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        error = json.loads(result.stderr)
        self.assertEqual(error["status"], "INPUT_REJECTED")
        self.assertIs(error["dispatch_authorized"], False)
        if code is not None:
            self.assertEqual(error["code"], code)
        self.assertNotIn(str(self.root), result.stderr)
        self.assertNotIn("PRIVATE_SENTINEL", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def assert_written(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        notice = json.loads(result.stdout)
        self.assertEqual(notice["status"], "OFFLINE_AUDIT_OUTPUT_WRITTEN")
        self.assertIs(notice["dispatch_authorized"], False)
        raw = self.output.read_bytes()
        self.assertEqual(notice["output"], {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        report = json.loads(raw)
        self.assertEqual(notice["audit_status"], report["status"])
        self.assertIs(report["input_binding"]["external_collection_authenticated"], False)
        self.assertIs(report["input_binding"]["explicit_bytes_hashes_verified"], True)
        for private in (str(self.root), "PRIVATE_SENTINEL", '"prompt_ids":', '"generated_ids":', '"log_pi":', '"log_mu":'):
            self.assertNotIn(private, raw.decode())
        return report

    def test_help_does_not_load_tensor_dependencies(self):
        result = subprocess.run([sys.executable, "-B", "-S", str(CLI), "--help"],
                                cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--audit-sha256", result.stdout)
        self.assertFalse(self.output.exists())

    def test_unknown_argument_is_not_echoed(self):
        self.assert_rejected(self.run_cli("--PRIVATE_SENTINEL"), "arguments_invalid")

    def test_input_hash_mismatch_before_optional_imports(self):
        path, _ = self.save("PRIVATE_SENTINEL.json", {})
        context, context_hash = self.save("context.json", {})
        self.assert_rejected(self.run_cli(*self.arguments(path, "0" * 64, context, context_hash)), "input_hash")
        self.assertFalse(self.output.exists())

    def test_unchanged_reader_cap_is_explicit(self):
        from tools.arc2_sft_rl_continuation_20261014.io import MAX_JSON_BYTES
        self.assertEqual(MAX_JSON_BYTES, 16 * 1024 * 1024)
        large = self.root / "audit.json"
        with large.open("wb") as output:
            output.truncate(MAX_JSON_BYTES + 1)
        context, context_hash = self.save("context.json", {})
        self.assert_rejected(self.run_cli(*self.arguments(large, "0" * 64, context, context_hash)), "input_size")
        self.assertFalse(self.output.exists())

    def test_duplicate_nonfinite_and_nonobject_json_rejected(self):
        context, context_hash = self.save("context.json", {})
        for raw, code in ((b'{"x":1,"x":2}', "duplicate_json_key"),
                          (b'{"x":NaN}', "nonfinite_json"),
                          (b'[]', "json_object_required")):
            with self.subTest(code=code):
                audit, audit_hash = self.save("audit.json", raw)
                self.assert_rejected(self.run_cli(*self.arguments(audit, audit_hash, context, context_hash)), code)

    def test_symlink_and_hardlink_inputs_rejected(self):
        original, digest = self.save("original.json", {})
        context, context_hash = self.save("context.json", {})
        link = self.root / "audit-link.json"
        link.symlink_to(original)
        self.assert_rejected(self.run_cli(*self.arguments(link, digest, context, context_hash)), "symlink_path")
        link.unlink()
        os.link(original, link)
        self.assert_rejected(self.run_cli(*self.arguments(link, digest, context, context_hash)), "regular_single_link_input")

    def test_dependency_absence_has_a_fixed_diagnostic(self):
        path, digest = self.save("audit.json", {})
        context, context_hash = self.save("context.json", {})
        result = subprocess.run([sys.executable, "-B", "-S", str(CLI), *map(str, self.arguments(path, digest, context, context_hash))],
                                cwd=ROOT, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stderr)["code"], "offline_cpu_dependencies")
        self.assertNotIn(str(self.root), result.stderr)
        self.assertFalse(self.output.exists())

    def test_actual_upstream_audit_output_and_byte_binding(self):
        args = self.fixture_arguments()
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        report = self.assert_written(self.run_cli(*args))
        self.assertEqual(report["status"], "CONFORMANT_SAVED_REPLAY")
        self.assertIs(report["conformance_complete"], True)
        self.assertEqual(report["replay"]["checked"], 64)
        self.assertIs(report["replay"]["recorded_loss_matches"], True)
        self.assertIs(report["provenance_authenticated"], False)
        self.assertIs(report["model_replay_verified"], False)
        self.assertIs(report["production_update_authorized"], False)
        for name, raw in before.items():
            self.assertEqual((self.root / name).read_bytes(), raw)

    def test_zero_signal_remains_a_distinct_no_replay_result(self):
        report = self.assert_written(self.run_cli(*self.fixture_arguments(successes=(0,) * 8)))
        self.assertEqual(report["status"], "CONFORMANT_ZERO_SIGNAL")
        self.assertIs(report["conformance_complete"], True)
        self.assertEqual(report["replay"]["checked"], 0)
        self.assertIsNone(report["replay"]["loss_unscaled"])

    def test_written_semantic_rejection_is_not_conformance(self):
        from tools.arc2_abc_continuation_20261014.fixtures import synthetic_audit, audit_bytes
        audit, context = synthetic_audit()
        audit["update"]["replays"][0]["detached_DDIS_loss"] += .5
        path, audit_hash = self.save("audit.json", audit_bytes(audit))
        context["audit_sha256"] = audit_hash
        declaration, context_hash = self.save("context.json", context)
        report = self.assert_written(self.run_cli(*self.arguments(path, audit_hash, declaration, context_hash)))
        self.assertEqual(report["status"], "REJECTED")
        self.assertIs(report["conformance_complete"], False)
        self.assertIs(report["ABC_efficacy_established"], False)
        self.assertTrue(report["issues"])

    def test_missing_original_audit_is_unknown_not_reward_zero(self):
        from tools.arc2_abc_continuation_20261014.fixtures import synthetic_audit
        _, context = synthetic_audit()
        path, audit_hash = self.save("audit.json", {})
        context["audit_sha256"] = audit_hash
        declaration, context_hash = self.save("context.json", context)
        report = self.assert_written(self.run_cli(*self.arguments(path, audit_hash, declaration, context_hash)))
        self.assertEqual(report["status"], "MISSING_ORIGINAL_ARTIFACTS")
        self.assertIs(report["conformance_complete"], False)
        self.assertIsNone(report["coverage"])
        self.assertIsNone(report["replay"])

    def test_existing_output_is_never_overwritten(self):
        args = self.fixture_arguments()
        original = b'PRIVATE_SENTINEL_EXISTING_OUTPUT\n'
        self.output.write_bytes(original)
        result = self.run_cli(*args)
        self.assert_rejected(result)
        self.assertEqual(self.output.read_bytes(), original)

    def test_context_binds_the_exact_original_audit(self):
        args = self.fixture_arguments()
        context_path = Path(args[5])
        context = json.loads(context_path.read_text())
        context["audit_sha256"] = "0" * 64
        _, context_hash = self.save(context_path.name, context)
        args[7] = context_hash
        self.assert_rejected(self.run_cli(*args), "local_audit_or_output_error")
        self.assertFalse(self.output.exists())

    def test_timeout_then_sigterm_cleans_owned_unpublished_staging(self):
        args = self.fixture_arguments()
        marker = self.root / "writer-ready"
        script = (
            "import sys,time\nfrom pathlib import Path\nfrom unittest.mock import patch\n"
            "from tools.arc2_abc_continuation_20261014 import cli\n"
            "from tools.arc2_sft_rl_continuation_20261014 import io\n"
            "def pause(fd):\n Path(sys.argv[1]).write_text('ready')\n time.sleep(60)\n"
            "with patch.object(io.os,'fsync',pause):\n raise SystemExit(cli.main(sys.argv[2:]))\n"
        )
        process = subprocess.Popen([sys.executable, "-B", *(["-O"] if sys.flags.optimize else []),
                                    "-c", script, str(marker), *map(str, args)],
                                   cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 25
            while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(marker.exists(), "child never reached real unpublished staging")
            with self.assertRaises(subprocess.TimeoutExpired):
                process.communicate(timeout=.05)
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 130, stderr)
            self.assertEqual(stdout, "")
            self.assertEqual(json.loads(stderr)["status"], "INTERRUPTED")
            self.assertFalse(self.output.exists())
            self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["audit.json", "context.json", "writer-ready"])
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main()
