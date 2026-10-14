"""Fixed CI matrix checks with synthetic reports; no GitHub or provider calls."""

from __future__ import annotations

import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import workstream_gate as gate

COMMIT = "a" * 40


class WorkstreamGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="irisx-gate-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "reports"
        self.root.mkdir()
        for operating_system in gate.OPERATING_SYSTEMS:
            for python in gate.PYTHONS:
                for suite in gate.SUITES:
                    self.write(self.public_path(suite, operating_system, python),
                               self.public_report(suite, operating_system, python))
                self.write(self.formal_path(operating_system, python),
                           self.formal_report(operating_system, python))

    def public_path(self, suite: str = "core", operating_system: str = "ubuntu-latest", python: str = "3.11") -> Path:
        return self.root / f"public-{suite}-{operating_system}-{python}/report.json"

    def formal_path(self, operating_system: str = "ubuntu-latest", python: str = "3.11") -> Path:
        return self.root / f"formal-{operating_system}-{python}/report.json"

    @staticmethod
    def public_report(suite: str, operating_system: str, python: str) -> dict:
        summary = {"format": "irisx.suite-report.v1", "suite": suite, "status": "passed",
                   "tests": 1, "failures": 0, "errors": 0, "skips": 0, "expected_skips": 0,
                   "unexpected_skips": 0, "blocked": 0, "exit_code": 0}
        child = dict(summary, path="tests/test_synthetic.py", collection_errors=0, collection_messages=[])
        return dict(summary, target_commit=COMMIT, python=python + ".99 synthetic fixture",
                    platform="Windows-11-fixture" if operating_system == "windows-latest" else "Linux-6-fixture",
                    selected_paths=[child["path"]], modules=[child])

    @staticmethod
    def formal_report(operating_system: str, python: str) -> dict:
        return {"schema": "irisx/distribution-self-check-v1", "status": "passed", "target_commit": COMMIT,
                "python": python + ".99 synthetic fixture",
                "platform": "Windows-11-fixture" if operating_system == "windows-latest" else "Linux-6-fixture",
                "wheels": [{"sha256": "b" * 64, "record_verified": True, "members": 42},
                           {"sha256": "b" * 64, "record_verified": True, "members": 42}],
                "synthetic_reference_flow": "passed", "line_b_synthetic_flow": "passed",
                "installation": {"non_editable": True, "editable_pth": [],
                                 "origin": "/synthetic/consumer/site-packages/irisx/__init__.py",
                                 "prefix": "/synthetic/consumer", "external_cwd": "/synthetic/external"},
                "commands": [{"argv": ["synthetic-python", "-I", "-B", "-m", "irisx", "--help"],
                              "cwd": "/synthetic/external", "log": "command-01.log", "exit_code": 0,
                              "expected_exit_code": 0},
                             {"argv": ["synthetic-python", "-I", "-B", "-m", "irisx", "package", "verify", "missing"],
                              "cwd": "/synthetic/external", "log": "command-02.log", "exit_code": 2,
                              "expected_exit_code": 2}]}

    @staticmethod
    def write(path: Path, data: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def assert_rejected(self, path: Path, mutate) -> None:
        original = self.read(path)
        changed = copy.deepcopy(original)
        mutate(changed)
        self.write(path, changed)
        self.assertTrue(gate.check_matrix(self.root, COMMIT))
        self.write(path, original)

    def test_complete_28_public_and_four_formal_reports_pass_read_only(self) -> None:
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*.json")}
        self.assertEqual(len(before), 32)
        self.assertEqual(gate.check_matrix(self.root, COMMIT), [])
        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*.json")})

    def test_missing_public_or_formal_report_is_rejected(self) -> None:
        for path in (self.public_path(), self.formal_path()):
            with self.subTest(path=path):
                original = path.read_bytes()
                path.unlink()
                self.assertTrue(gate.check_matrix(self.root, COMMIT))
                path.write_bytes(original)

    def test_target_commit_mismatch_is_rejected_for_public_and_formal(self) -> None:
        for path in (self.public_path(), self.formal_path()):
            with self.subTest(path=path):
                self.assert_rejected(path, lambda report: report.update(target_commit="c" * 40))

    def test_public_wrong_suite_schema_os_or_python_is_rejected(self) -> None:
        for change in ({"suite": "other"}, {"format": "unknown"}, {"python": "3.14.99"},
                       {"platform": "Windows-11-fixture"}, {"platform": "UnrelatedOS"}):
            with self.subTest(change=change):
                self.assert_rejected(self.public_path(), lambda report: report.update(change))

    def test_formal_wrong_schema_os_or_python_is_rejected(self) -> None:
        for change in ({"schema": "unknown"}, {"python": "3.14.99"}, {"platform": "Windows-11-fixture"}):
            with self.subTest(change=change):
                self.assert_rejected(self.formal_path(), lambda report: report.update(change))

    def test_cancelled_timed_out_blocked_and_empty_public_reports_are_rejected(self) -> None:
        for change in ({"status": "cancelled", "exit_code": -1}, {"status": "timeout", "exit_code": 1},
                       {"status": "blocked", "blocked": 1, "exit_code": 2}, {"tests": 0},
                       {"unexpected_skips": 1, "skips": 1}):
            with self.subTest(change=change):
                self.assert_rejected(self.public_path(), lambda report: report.update(change))

    def test_negative_or_non_integer_public_counts_are_rejected(self) -> None:
        for change in ({"tests": -1}, {"failures": False}, {"errors": 0.0},
                       {"skips": -1, "expected_skips": -1}):
            with self.subTest(change=change):
                self.assert_rejected(self.public_path(), lambda report: report.update(change))

    def test_failed_or_invalid_child_cannot_be_hidden_by_healthy_suite_summary(self) -> None:
        for change in ({"status": "failed", "exit_code": 1}, {"exit_code": 1}, {"tests": -1}, {"errors": 1},
                       {"suite": "other"}, {"format": "unknown"}, {"path": "tests/unselected.py"}):
            with self.subTest(change=change):
                self.assert_rejected(self.public_path(), lambda report: report["modules"][0].update(change))
        self.assert_rejected(self.public_path(), lambda report: report.update(modules=[]))
        self.assert_rejected(self.public_path(), lambda report: report.update(selected_paths=[]))

    def test_differing_wheel_hash_or_failed_record_is_rejected(self) -> None:
        self.assert_rejected(self.formal_path(), lambda report: report["wheels"][0].update(sha256="d" * 64))
        self.assert_rejected(self.formal_path(), lambda report: report["wheels"][0].update(record_verified=False))
        self.assert_rejected(self.formal_path(), lambda report: report["wheels"][0].update(members=0))

    def test_two_equal_invalid_hashes_or_boolean_member_counts_are_rejected(self) -> None:
        for value in (None, "", "not-a-hash", "b" * 63):
            with self.subTest(value=value):
                self.assert_rejected(self.formal_path(),
                                     lambda report: [wheel.update(sha256=value) for wheel in report["wheels"]])
        self.assert_rejected(self.formal_path(), lambda report: report["wheels"][0].update(members=True))

    def test_missing_line_b_reference_flow_or_non_editable_proof_is_rejected(self) -> None:
        for field in ("line_b_synthetic_flow", "synthetic_reference_flow"):
            with self.subTest(field=field):
                self.assert_rejected(self.formal_path(), lambda report: report.pop(field))
        self.assert_rejected(self.formal_path(), lambda report: report["installation"].update(non_editable=False))
        self.assert_rejected(self.formal_path(), lambda report: report["installation"].update(editable_pth=["injected.pth"]))

    def test_commands_need_actual_integer_results_matching_expected_results(self) -> None:
        self.assert_rejected(self.formal_path(), lambda report: report.update(commands=[]))
        self.assert_rejected(self.formal_path(), lambda report: report.update(commands=[{}]))
        self.assert_rejected(self.formal_path(), lambda report: report["commands"][0].update(exit_code=1))
        self.assert_rejected(self.formal_path(), lambda report: report["commands"][0].update(exit_code=False))

    def test_malformed_reports_return_errors_without_uncaught_exceptions(self) -> None:
        path = self.public_path()
        original = path.read_bytes()
        for invalid in (None, [], "invalid"):
            with self.subTest(invalid=invalid):
                self.write(path, invalid)
                self.assertTrue(gate.check_matrix(self.root, COMMIT))
        path.write_text('{"status":"passed", "status":"failed"}\n', encoding="utf-8")
        self.assertTrue(gate.check_matrix(self.root, COMMIT))
        path.write_bytes(original)

    def test_main_requires_successful_jobs_as_well_as_complete_reports(self) -> None:
        needs = {"public-suites": {"result": "success"}, "formal-distribution": {"result": "success"}}
        with mock.patch.dict(gate.os.environ, {"WORKSTREAM_NEEDS": json.dumps(needs)}), \
             mock.patch.object(gate.subprocess, "check_output", return_value=COMMIT + "\n"), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(gate.main(["--reports", str(self.root)]), 0)
        for result in ("cancelled", "failure", "skipped", None):
            with self.subTest(result=result):
                needs["public-suites"]["result"] = result
                with mock.patch.dict(gate.os.environ, {"WORKSTREAM_NEEDS": json.dumps(needs)}), \
                     mock.patch.object(gate.subprocess, "check_output", return_value=COMMIT + "\n"), \
                     redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(gate.main(["--reports", str(self.root)]), 1)


if __name__ == "__main__":
    unittest.main()
