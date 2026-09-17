from __future__ import annotations

import contextlib
import io
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

import support  # noqa: F401

from irisx import cli
from irisx.errors import ValidationError
from irisx.fixture import prepare_fixture, run_trial, validate_trial
from irisx.package import build_package, verify_package


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ReferenceFlowTests(unittest.TestCase):
    def test_repeated_execution_and_packages_are_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture_a, fixture_b = root / "fixture-a", root / "fixture-b"
            run_a, run_b = root / "run-a", root / "run-b"
            package_a, package_b = root / "package-a", root / "package-b"
            prepare_fixture(fixture_a)
            prepare_fixture(fixture_b)
            run_trial(fixture_a / "trial.json", run_a)
            run_trial(fixture_b / "trial.json", run_b)
            build_package(run_a, package_a)
            build_package(run_b, package_b)
            self.assertEqual(tree_bytes(fixture_a), tree_bytes(fixture_b))
            self.assertEqual(tree_bytes(run_a), tree_bytes(run_b))
            self.assertEqual(tree_bytes(package_a), tree_bytes(package_b))

    def test_fixture_makes_no_network_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), mock.patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
                prepare_fixture(root / "fixture")
                run_trial(root / "fixture/trial.json", root / "run")
                build_package(root / "run", root / "package")
                verify_package(root / "package")

    def test_package_rejects_corruption_missing_and_unexpected_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_fixture(root / "fixture")
            run_trial(root / "fixture/trial.json", root / "run")
            build_package(root / "run", root / "package")
            target = root / "package/evaluation/result.json"
            target.write_bytes(target.read_bytes() + b" ")
            with self.assertRaisesRegex(ValidationError, "digest mismatch"):
                verify_package(root / "package")

    def test_trial_validation_rejects_substituted_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_fixture(root / "fixture")
            candidate = root / "fixture/candidate.json"
            candidate.write_bytes(candidate.read_bytes().replace(b"Deterministic candidate intervention", b"Substituted candidate intervention"))
            with self.assertRaisesRegex(ValidationError, "digest mismatch"):
                validate_trial(root / "fixture/trial.json")

    def test_cli_success_and_failure_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cli.main(["fixture", "prepare", "--output", str(root / "fixture")]), 0)
                self.assertEqual(cli.main(["spec", "validate", str(root / "fixture/specification.json")]), 0)
                self.assertEqual(cli.main(["trial", "validate", str(root / "fixture/trial.json")]), 0)
                self.assertEqual(cli.main(["trial", "run", "--trial", str(root / "fixture/trial.json"), "--output", str(root / "run")]), 0)
                self.assertEqual(cli.main(["package", "build", "--run", str(root / "run"), "--output", str(root / "package")]), 0)
                self.assertEqual(cli.main(["package", "verify", str(root / "package")]), 0)
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(cli.main(["package", "verify", str(root / "missing")]), 2)
            self.assertIn("error", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
