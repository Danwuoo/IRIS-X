"""CPU CLI integration with synthetic reports; never authentic experiment evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from test_analysis import report


PACKAGE = Path(__file__).absolute().parents[1]
ROOT = PACKAGE.parents[1]
CLI = PACKAGE / "cli.py"
POSIX_SAFE = (os.name == "posix" and hasattr(os, "O_NOFOLLOW")
              and hasattr(os, "O_DIRECTORY") and os.open in os.supports_dir_fd)


@unittest.skipUnless(POSIX_SAFE, "CLI file operations require no-follow POSIX descriptors")
class CLIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "summary.json"

    def command(self, *arguments):
        flags = ["-B"] + (["-O"] if sys.flags.optimize else [])
        return [sys.executable, *flags, str(CLI), *map(str, arguments)]

    def run_cli(self, *arguments):
        return subprocess.run(self.command(*arguments), cwd=ROOT, text=True,
                              capture_output=True, timeout=15, check=False)

    def save(self, name, value):
        raw = (json.dumps(value, allow_nan=False, sort_keys=True) + "\n").encode()
        path = self.root / name
        path.write_bytes(raw)
        return path, {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

    def assert_written(self, process):
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, "")
        notice = json.loads(process.stdout)
        self.assertEqual(notice["status"], "OFFLINE_OUTPUT_WRITTEN")
        self.assertIs(notice["dispatch_authorized"], False)
        raw = self.output.read_bytes()
        self.assertEqual(notice["output"], {
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        return json.loads(raw), notice

    def assert_rejected(self, process, code=None):
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertEqual(process.stdout, "")
        error = json.loads(process.stderr)
        self.assertEqual(error["status"], "INPUT_REJECTED")
        self.assertIs(error["dispatch_authorized"], False)
        if code:
            self.assertEqual(error["code"], code)
        self.assertNotIn(str(self.root), process.stderr)
        self.assertNotIn("Traceback", process.stderr)
        self.assertFalse(self.output.exists())

    def test_prepare_real_public_source_bytes_without_execution(self):
        process = self.run_cli("prepare", "--repository-root", ROOT, "--output", self.output)
        value, _ = self.assert_written(process)
        self.assertEqual(value["status"], "OFFLINE_PREPARATION_ONLY")
        self.assertEqual(value["baseline_commit"], "cc14bd1a79aac1fe6135017c9e09d4834300675d")
        self.assertIs(value["model_execution_performed"], False)
        self.assertIs(value["source_identity"]["selected_bytes_verified"], True)
        self.assertIs(value["source_identity"]["repository_head_verified"], False)
        self.assertEqual(value["scientific_plan"]["evaluation"]["public_denominator"],
                         {"tasks": 120, "queries": 167})
        self.assertNotIn(str(ROOT), json.dumps(value))

    def test_analyze_full_synthetic_report(self):
        value = report()
        value["error"] = "PRIVATE_ERROR_SENTINEL"
        source, descriptor = self.save("report.json", value)
        before = source.read_bytes()
        process = self.run_cli("analyze", "--report", source, "--report-sha256",
                               descriptor["sha256"], "--output", self.output)
        summary, notice = self.assert_written(process)
        self.assertIs(notice["analysis_structurally_consistent"], True)
        self.assertIs(summary["analysis_authenticated"], False)
        self.assertIs(summary["method_efficacy_established"], False)
        self.assertEqual(summary["public"]["micro_pass_at_2"]["denominator"], 167)
        self.assertIs(summary["public"]["task_count_verified"], False)
        self.assertIs(summary["comparison"]["case_universe_verified"], False)
        self.assertEqual(source.read_bytes(), before)
        serialized = self.output.read_text()
        for private in ("PRIVATE_ERROR_SENTINEL", "synthetic-parent", "holdout:synthetic", str(source)):
            self.assertNotIn(private, serialized)

    def test_missing_scoring_is_unknown(self):
        value = report()
        value.update(status="STOPPED_INCOMPLETE", provider_status="ERROR",
                     comparison_complete=False, comparison_eligible=False,
                     public_benchmark_evidence_eligible=False)
        value["evaluation"].update(comparison_complete=False, holdout_scores=None, paired_vs_A=None)
        value["public"] = {"status": "PREDICTIONS_SEALED_NOT_SCORED", "selected_arm": "B",
                           "scorer_rows_complete": False, "micro_pass_at_2": None}
        source, descriptor = self.save("report.json", value)
        process = self.run_cli("analyze", "--report", source, "--report-sha256",
                               descriptor["sha256"], "--output", self.output)
        summary, _ = self.assert_written(process)
        self.assertIsNone(summary["public"]["micro_pass_at_2"])
        self.assertIsNone(summary["comparison"]["holdout"])
        self.assertIsNone(summary["comparison"]["paired_deltas"])

    def test_explicit_collector_links_never_follow_recorded_paths(self):
        value = report()
        source, descriptor = self.save("report.json", value)
        retrieval = {"format": "irisx/rlvr-selected-retrieval-v1", "numeric_output_version": 999,
                     "before": {"status": "COMPLETE"}, "after": {"status": "COMPLETE"},
                     "inventory_scope": "selected_outputs_only",
                     "whole_provider_inventory_verified": False}
        retrieval_path, retrieval_descriptor = self.save("retrieval.json", retrieval)
        keys = ("operational_success", "comparison_complete", "compute_matched", "comparison_eligible",
                "public_benchmark_evidence_eligible", "goal_met", "public_goal_met")
        checkpoint = {key: value[key] for key in keys}
        checkpoint.update(status="TERMINAL_EVIDENCE_VERIFIED", automatic_retry=False,
                          provider_status="COMPLETE", validation={**descriptor, "path": "DO_NOT_OPEN"},
                          retrieval={**retrieval_descriptor, "path": "DO_NOT_OPEN"})
        checkpoint_path, checkpoint_descriptor = self.save("checkpoint.json", checkpoint)
        process = self.run_cli("analyze", "--report", source, "--report-sha256", descriptor["sha256"],
                               "--checkpoint", checkpoint_path, "--checkpoint-sha256", checkpoint_descriptor["sha256"],
                               "--retrieval", retrieval_path, "--retrieval-sha256", retrieval_descriptor["sha256"],
                               "--output", self.output)
        summary, _ = self.assert_written(process)
        binding = summary["input_binding"]
        self.assertIs(binding["local_descriptor_links_consistent"], True)
        self.assertIs(binding["external_collection_authenticated"], False)
        self.assertEqual(binding["recorded_numeric_output_version"], 999)
        self.assertNotIn("DO_NOT_OPEN", self.output.read_text())

    def test_bad_input_hash_produces_no_output(self):
        source, _ = self.save("report.json", report())
        self.assert_rejected(self.run_cli("analyze", "--report", source, "--report-sha256", "0" * 64,
                                          "--output", self.output), "input_hash")

    def test_paired_arguments_and_missing_file_are_sanitized(self):
        source, descriptor = self.save("report.json", report())
        self.assert_rejected(self.run_cli("analyze", "--report", source, "--report-sha256", descriptor["sha256"],
                                          "--checkpoint", self.root / "PRIVATE_PATH", "--output", self.output),
                             "paired_file_hash_arguments")
        self.assert_rejected(self.run_cli("analyze", "--report", self.root / "PRIVATE_PATH",
                                          "--report-sha256", descriptor["sha256"], "--output", self.output))

    def test_argument_errors_do_not_echo_values(self):
        process = self.run_cli("prepare", "--output", self.output, "--unexpected=PRIVATE_VALUE")
        self.assert_rejected(process, "arguments_invalid")
        self.assertNotIn("PRIVATE_VALUE", process.stderr)

    def test_malformed_json_is_sanitized(self):
        source = self.root / "report.json"
        for raw in (b'{"a":1,"a":2}', b'{"a":1e999}', b'{"a":NaN}', b'[]', b'\xff'):
            with self.subTest(raw=raw):
                source.write_bytes(raw)
                self.assert_rejected(self.run_cli("analyze", "--report", source, "--report-sha256",
                                                  hashlib.sha256(raw).hexdigest(), "--output", self.output))

    def test_huge_integer_does_not_escape_as_traceback(self):
        value = report()
        value["metering"]["time_matching"]["B_seconds"] = 10 ** 1000
        source, descriptor = self.save("report.json", value)
        summary, notice = self.assert_written(self.run_cli(
            "analyze", "--report", source, "--report-sha256", descriptor["sha256"], "--output", self.output))
        self.assertIs(notice["analysis_structurally_consistent"], False)
        self.assertIsNone(summary["time_matching"]["derived_matched"])

    def test_existing_output_is_not_overwritten(self):
        original = b"existing output must survive"
        self.output.write_bytes(original)
        process = self.run_cli("prepare", "--repository-root", ROOT, "--output", self.output)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(self.output.read_bytes(), original)

    def test_prepare_missing_source_is_rejected_without_path(self):
        self.assert_rejected(self.run_cli("prepare", "--repository-root", self.root / "PRIVATE_MISSING_ROOT",
                                          "--output", self.output))

    def test_cli_does_not_import_model_or_provider_or_open_network(self):
        wrapper = '''import importlib.abc, runpy, sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'torch','transformers','peft','kaggle','kagglesdk','requests','urllib3','vllm'}:
   raise RuntimeError('forbidden dependency')
sys.meta_path.insert(0, Block())
def audit(event, args):
 if event.startswith(('socket.', 'subprocess.')) or event in {'os.system','os.posix_spawn'}:
  raise RuntimeError('forbidden external operation')
sys.addaudithook(audit)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
'''
        command = self.command("prepare", "--repository-root", ROOT, "--output", self.output)
        command[command.index(str(CLI)):command.index(str(CLI))] = ["-c", wrapper]
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=15, check=False)
        self.assert_written(process)

    @unittest.skipUnless(hasattr(os, "kill"), "requires process termination")
    def test_sigterm_during_prepublication_write_cleans_staging(self):
        output_dir = self.root / "output"
        output_dir.mkdir()
        output = output_dir / "summary.json"
        marker = self.root / "entered-fsync"
        wrapper = '''import os, pathlib, sys, time
sys.path.insert(0, sys.argv[1])
from arc2_sft_rl_continuation_20261014 import cli, io
def slow_fsync(fd):
 pathlib.Path(sys.argv[2]).write_text('ready')
 time.sleep(60)
io.os.fsync = slow_fsync
raise SystemExit(cli.main(['prepare','--repository-root',sys.argv[3],'--output',sys.argv[4]]))
'''
        flags = ["-B"] + (["-O"] if sys.flags.optimize else [])
        process = subprocess.Popen([sys.executable, *flags, "-c", wrapper, str(ROOT / "tools"),
                                    str(marker), str(ROOT), str(output)], cwd=ROOT,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            end = time.monotonic() + 10
            while not marker.exists() and process.poll() is None and time.monotonic() < end:
                time.sleep(0.01)
            self.assertTrue(marker.exists(), "child never reached prepublication fsync")
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 130, stderr)
            self.assertEqual(stdout, "")
            self.assertEqual(json.loads(stderr)["status"], "INTERRUPTED")
            self.assertEqual(list(output_dir.iterdir()), [])
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
