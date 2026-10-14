"""Fixed CI matrix checks with synthetic reports; no GitHub or provider calls."""

from __future__ import annotations

import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import workstream_gate as gate

class WorkstreamGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="irisx-gate-synthetic-git-")
        self.addCleanup(self.tmp.cleanup)
        self.repository = Path(self.tmp.name) / "repository"
        self.repository.mkdir()
        self.root = Path(self.tmp.name) / "reports"
        self.root.mkdir()
        self.inventory = {"format": "irisx.tests.v1", "suites": {
            suite: {"public": True} for suite in gate.SUITES}, "entries": []}
        for suite in gate.SUITES:
            for suffix in (("a", "b") if suite == "core" else ("a",)):
                path = "tests/test_synthetic_" + suite.replace("-", "_") + "_" + suffix + ".py"
                target = self.repository / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("import unittest\nclass Fixture(unittest.TestCase):\n    def test_constant(self): self.assertEqual(2 + 2, 4)\n", encoding="utf-8")
                entry = {"path": path, "workstream": "core", "dependency_class": "stdlib", "suite": suite,
                         "role": "test", "dependencies": [], "collector": "unittest",
                         "reason": "Authored constant-only synthetic gate inventory; fixture reports are not OS execution evidence",
                         "expected_skips": []}
                if suite == "core" and suffix == "a":
                    self.skip_id = "test_synthetic_core_a.Fixture.test_link"
                    entry["expected_skips"] = [{"test_id": self.skip_id, "reason_contains": "WinError 1314",
                                                "platforms": ["win32"]}]
                    with target.open("a", encoding="utf-8") as stream:
                        stream.write("    def test_link(self): self.assertEqual(1, 1)\n")
                self.inventory["entries"].append(entry)
        helper = self.repository / "tests/core_support.py"
        helper.write_text("# Constant-only helper, never a passing module report.\n", encoding="utf-8")
        self.inventory["entries"].append({"path": "tests/core_support.py", "workstream": "core",
            "dependency_class": "stdlib", "suite": "core", "role": "helper", "dependencies": [],
            "collector": "helper", "reason": "Authored helper-only fixture", "expected_skips": []})
        self.write(self.repository / "tests/inventory.json", self.inventory)
        runner = self.repository / "tools/suite_runner.py"
        runner.parent.mkdir()
        runner.write_text("# Authored runner identity fixture; never executed.\n", encoding="utf-8")
        self.git("init", "--quiet")
        self.git("add", "--", "tests", "tools")
        self.git("-c", "user.name=IRIS-X synthetic fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "-m", "Synthetic gate source identity")
        self.commit = self.git("rev-parse", "HEAD").strip()
        self.evidence = self.evidence_for(self.commit)
        self.write_reports()

    def evidence_for(self, commit: str) -> dict:
        rows = []
        for record in self.git("ls-tree", "-r", "-z", "--full-tree", commit).split("\0"):
            if record:
                metadata, path = record.split("\t", 1)
                mode, kind, blob = metadata.split()
                self.assertEqual(kind, "blob")
                rows.append({"path": path, "mode": mode, "blob": blob})
        digest = hashlib.sha256(json.dumps(sorted(rows, key=lambda row: row["path"]), sort_keys=True,
            separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        return {"attestable": True, "evidence_kind": "commit", "target_commit": commit,
            "inventory_blob": self.git("rev-parse", commit + ":tests/inventory.json").strip(),
            "runner_blob": self.git("rev-parse", commit + ":tools/suite_runner.py").strip(),
            "source_identity": {"format": "irisx.source-identity.v1", "commit": commit,
                "tree": self.git("rev-parse", commit + "^{tree}").strip(), "manifest_sha256": digest}}

    def write_reports(self) -> None:
        for operating_system in gate.OPERATING_SYSTEMS:
            for python in gate.PYTHONS:
                for suite in gate.SUITES:
                    self.write(self.public_path(suite, operating_system, python),
                               self.public_report(suite, operating_system, python))
                self.write(self.formal_path(operating_system, python),
                           self.formal_report(operating_system, python))

    def git(self, *arguments, input_bytes=None) -> str:
        completed = subprocess.run(["git", *arguments], cwd=self.repository, check=True,
                                   capture_output=True, input=input_bytes)
        return completed.stdout.decode("utf-8")

    def commit_with_virtual_paths(self, paths: tuple[str, ...]) -> str:
        """Create raw Git tree entries without materializing unsafe Windows paths."""
        rows = []
        for record in self.git("ls-tree", "-r", "-z", "--full-tree", self.commit).split("\0"):
            if record:
                metadata, path = record.split("\t", 1)
                mode, kind, blob = metadata.split()
                self.assertEqual(kind, "blob")
                rows.append((path, mode, blob))
        blob = self.git("hash-object", "-w", "--stdin",
                        input_bytes=b"# Constant-only source metadata fixture; never executed.\n").strip()
        rows.extend((path, "100644", blob) for path in paths)
        tree = {}
        for path, mode, blob in rows:
            node = tree
            parts = path.split("/")
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = (mode, blob)

        def write_tree(node):
            records = []
            for name, entry in sorted(node.items()):
                if isinstance(entry, dict):
                    mode, kind, identity = "040000", "tree", write_tree(entry)
                else:
                    mode, identity = entry
                    kind = "blob"
                records.append(f"{mode} {kind} {identity}\t{name}\0".encode("utf-8"))
            return self.git("mktree", "-z", input_bytes=b"".join(records)).strip()

        return self.git("-c", "user.name=IRIS-X synthetic fixture", "-c", "user.email=fixture@example.invalid",
                        "commit-tree", write_tree(tree), "-p", self.commit,
                        "-m", "Virtual source manifest fixture without checkout").strip()

    def check(self, commit=None, repository=None):
        return gate.check_matrix(self.root, commit or self.commit,
                                 repository_root=repository or self.repository)

    def public_path(self, suite: str = "core", operating_system: str = "ubuntu-latest", python: str = "3.11") -> Path:
        return self.root / f"public-{suite}-{operating_system}-{python}/report.json"

    def formal_path(self, operating_system: str = "ubuntu-latest", python: str = "3.11") -> Path:
        return self.root / f"formal-{operating_system}-{python}/report.json"

    def public_report(self, suite: str, operating_system: str, python: str) -> dict:
        summary = {"format": "irisx.suite-report.v1", "suite": suite, "status": "passed",
                   "tests": 0, "failures": 0, "errors": 0, "skips": 0, "expected_skips": 0,
                   "unexpected_skips": 0, "blocked": 0, "exit_code": 0}
        summary.update(copy.deepcopy(self.evidence))
        modules = []
        for entry in self.inventory["entries"]:
            if entry["suite"] == suite and entry["role"] != "helper":
                child = copy.deepcopy(summary)
                child.update(path=entry["path"], tests=2 if entry["path"].endswith("core_a.py") else 1,
                             collection_errors=0, collection_messages=[], skip_records=[])
                modules.append(child)
        summary.update(tests=sum(module["tests"] for module in modules),
            python=python + ".99 synthetic fixture",
            platform="Windows-11-fixture" if operating_system == "windows-latest" else "Linux-6-fixture",
            selected_paths=[child["path"] for child in modules], modules=modules)
        return summary

    def formal_report(self, operating_system: str, python: str) -> dict:
        return {**copy.deepcopy(self.evidence), "schema": "irisx/distribution-self-check-v1", "status": "passed", "target_commit": self.commit,
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
        self.assertTrue(self.check())
        self.write(path, original)

    def test_complete_28_public_and_four_formal_reports_pass_read_only(self) -> None:
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*.json")}
        self.assertEqual(len(before), 32)
        self.assertEqual(self.check(), [])
        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*.json")})

    def test_missing_public_or_formal_report_is_rejected(self) -> None:
        for path in (self.public_path(), self.formal_path()):
            with self.subTest(path=path):
                original = path.read_bytes()
                path.unlink()
                self.assertTrue(self.check())
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
                self.assertTrue(self.check())
        path.write_text('{"status":"passed", "status":"failed"}\n', encoding="utf-8")
        self.assertTrue(self.check())
        path.write_bytes(original)

    def test_main_requires_successful_jobs_as_well_as_complete_reports(self) -> None:
        needs = {"public-suites": {"result": "success"}, "formal-distribution": {"result": "success"}}
        arguments = ["--reports", str(self.root), "--repository-root", str(self.repository)]
        with mock.patch.dict(gate.os.environ, {"WORKSTREAM_NEEDS": json.dumps(needs)}), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(gate.main(arguments), 0)
        for result in ("cancelled", "failure", "skipped", None):
            with self.subTest(result=result):
                needs["public-suites"]["result"] = result
                with mock.patch.dict(gate.os.environ, {"WORKSTREAM_NEEDS": json.dumps(needs)}), \
                     redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(gate.main(arguments), 1)

    @staticmethod
    def recalculate(report):
        for field in gate.COUNTS:
            report[field] = sum(module[field] for module in report["modules"])

    def test_consistent_omission_of_module_selection_and_counts_is_rejected(self):
        def omit(report):
            report["modules"].pop()
            report["selected_paths"].pop()
            self.recalculate(report)
        self.assert_rejected(self.public_path(), omit)

    def test_substituted_extra_duplicate_and_reordered_modules_are_rejected(self):
        def replace(report):
            report["modules"][1]["path"] = "tests/substituted.py"
            report["selected_paths"][1] = "tests/substituted.py"
        def extra(report):
            module = copy.deepcopy(report["modules"][0])
            module["path"] = "tests/extra.py"
            report["modules"].append(module)
            report["selected_paths"].append(module["path"])
            self.recalculate(report)
        def duplicate(report):
            report["modules"].append(copy.deepcopy(report["modules"][0]))
            report["selected_paths"].append(report["modules"][0]["path"])
            self.recalculate(report)
        def reorder(report):
            report["modules"].reverse()
            report["selected_paths"].reverse()
        for mutate in (replace, extra, duplicate, reorder):
            with self.subTest(mutate=mutate.__name__):
                self.assert_rejected(self.public_path(), mutate)

    def test_helper_module_cannot_replace_required_test(self):
        def substitute(report):
            report["modules"][1]["path"] = "tests/core_support.py"
            report["selected_paths"][1] = "tests/core_support.py"
        self.assert_rejected(self.public_path(), substitute)

    def test_report_binding_mismatch_or_development_evidence_is_rejected(self):
        changes = ({"attestable": False}, {"attestable": 1}, {"evidence_kind": "development"},
                   {"inventory_blob": "c" * 40}, {"runner_blob": "d" * 40})
        for change in changes:
            with self.subTest(change=change):
                self.assert_rejected(self.public_path(), lambda report: report.update(change))
                self.assert_rejected(self.public_path(), lambda report: report["modules"][0].update(change))
                self.assert_rejected(self.formal_path(), lambda report: report.update(change))
        for field in ("tree", "commit", "manifest_sha256"):
            with self.subTest(field=field):
                self.assert_rejected(self.public_path(), lambda report: report["source_identity"].update({field: "f" * 64}))
                self.assert_rejected(self.public_path(), lambda report: report["modules"][0]["source_identity"].update({field: "f" * 64}))
                self.assert_rejected(self.formal_path(), lambda report: report["source_identity"].update({field: "f" * 64}))

    def test_another_real_inventory_and_runner_blob_cannot_be_mixed(self):
        changed = copy.deepcopy(self.inventory)
        changed["entries"][0]["reason"] += " Different synthetic committed inventory."
        self.write(self.repository / "tests/inventory.json", changed)
        (self.repository / "tools/suite_runner.py").write_text("# Different fixture runner identity.\n", encoding="utf-8")
        self.git("add", "--", "tests/inventory.json", "tools/suite_runner.py")
        self.git("-c", "user.name=IRIS-X synthetic fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "-m", "Different synthetic authoritative inventory")
        other = self.git("rev-parse", "HEAD").strip()
        inventory_blob = self.git("rev-parse", other + ":tests/inventory.json").strip()
        runner_blob = self.git("rev-parse", other + ":tools/suite_runner.py").strip()
        self.assert_rejected(self.public_path(), lambda report: report.update(inventory_blob=inventory_blob))
        self.assert_rejected(self.public_path(), lambda report: report["modules"][0].update(inventory_blob=inventory_blob))
        self.assert_rejected(self.public_path(), lambda report: report["modules"][0].update(runner_blob=runner_blob))

    def test_target_git_objects_override_dirty_checkout_inventory_and_runner(self):
        self.write(self.repository / "tests/inventory.json", {"unrelated": "dirty bytes are not authoritative"})
        (self.repository / "tools/suite_runner.py").write_text("# Dirty fixture runner.\n", encoding="utf-8")
        self.assertEqual(self.check(), [])

    def test_missing_git_objects_or_non_git_source_fails_closed(self):
        self.assertTrue(self.check(commit="0" * 40))
        self.assertTrue(self.check(commit="not-a-commit"))
        self.assertTrue(self.check(repository=self.root))

    def add_allowed_skip(self, report):
        module = report["modules"][0]
        module.update(skips=1, expected_skips=1,
                      skip_records=[{"test_id": self.skip_id, "reason": "Synthetic Windows WinError 1314 privilege condition"}])
        self.recalculate(report)

    def test_actual_skip_records_are_allowed_only_by_target_inventory_os(self):
        windows = self.public_path(operating_system="windows-latest")
        report = self.read(windows)
        self.add_allowed_skip(report)
        self.write(windows, report)
        self.assertEqual(self.check(), [])
        self.assert_rejected(self.public_path(), self.add_allowed_skip)

    def test_skip_forgery_missing_duplicate_wrong_id_reason_or_counts_is_rejected(self):
        path = self.public_path(operating_system="windows-latest")
        original = self.read(path)
        def changes(report, kind):
            self.add_allowed_skip(report)
            module = report["modules"][0]
            if kind == "missing": module.pop("skip_records")
            elif kind == "id": module["skip_records"][0]["test_id"] = "fabricated.case"
            elif kind == "reason": module["skip_records"][0]["reason"] = "fabricated reason"
            elif kind == "claimed": module["skip_records"][0]["expected"] = True
            elif kind == "duplicate":
                module["skip_records"].append(copy.deepcopy(module["skip_records"][0]))
                module.update(skips=2, expected_skips=2)
                self.recalculate(report)
            elif kind == "count":
                module.update(skips=2, expected_skips=2)
                self.recalculate(report)
        for kind in ("missing", "id", "reason", "claimed", "duplicate", "count"):
            with self.subTest(kind=kind):
                self.assert_rejected(path, lambda report: changes(report, kind))
        self.assertEqual(self.read(path), original)

    def test_target_inventory_duplicates_invalid_json_and_missing_module_are_rejected(self):
        cases = ("duplicate", "json", "module")
        for kind in cases:
            with self.subTest(kind=kind):
                changed = copy.deepcopy(self.inventory)
                if kind == "duplicate": changed["entries"].append(copy.deepcopy(changed["entries"][0]))
                elif kind == "module": changed["entries"][0]["path"] = "tests/unavailable.py"
                if kind == "json":
                    (self.repository / "tests/inventory.json").write_text('{"format":"a","format":"b"}', encoding="utf-8")
                else: self.write(self.repository / "tests/inventory.json", changed)
                self.git("add", "--", "tests/inventory.json")
                self.git("-c", "user.name=IRIS-X synthetic fixture", "-c", "user.email=fixture@example.invalid",
                         "commit", "--quiet", "-m", "Invalid synthetic inventory " + kind)
                self.assertTrue(self.check(commit=self.git("rev-parse", "HEAD").strip()))

    def test_metadata_only_source_tree_with_consistent_parent_case_passes(self):
        checkout_commit = self.commit
        paths = ("src/Fixture/a.py", "src/Fixture/b.py")
        self.commit = self.commit_with_virtual_paths(paths)
        self.evidence = self.evidence_for(self.commit)
        self.write_reports()
        self.assertTrue(set(paths) <= set(self.git("ls-tree", "-r", "--name-only", self.commit).splitlines()))
        self.assertEqual(self.check(), [])
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), checkout_commit)
        self.assertFalse((self.repository / "src").exists())

    def test_metadata_only_parent_component_case_collisions_are_rejected(self):
        checkout_commit = self.commit
        cases = (("src/Foo/a.py", "src/foo/b.py"),
                 ("src/fixture/Parent/a.py", "src/fixture/parent/b.py"))
        for paths in cases:
            with self.subTest(paths=paths):
                self.commit = checkout_commit
                self.commit = self.commit_with_virtual_paths(paths)
                self.evidence = self.evidence_for(self.commit)
                self.write_reports()
                self.assertTrue(set(paths) <= set(self.git("ls-tree", "-r", "--name-only", self.commit).splitlines()))
                errors = self.check()
                self.assertEqual(len(errors), 1)
                self.assertIn("colliding target source parent path", errors[0])
                self.assertEqual(self.git("rev-parse", "HEAD").strip(), checkout_commit)
                self.assertFalse((self.repository / "src").exists())

    def test_metadata_only_tracked_git_and_output_paths_are_rejected(self):
        checkout_commit = self.commit
        checkout_config = (self.repository / ".git/config").read_bytes()
        for path in (".git/fixture.txt", ".irisx/fixture.txt", ".git", ".irisx",
                     ".GIT", ".IRISX", ".GIT/config", ".IRISX/fixture.txt",
                     ".GIT/nested/config", ".IRISX/cache/payload.txt"):
            with self.subTest(path=path):
                self.commit = checkout_commit
                self.commit = self.commit_with_virtual_paths((path,))
                self.evidence = self.evidence_for(self.commit)
                self.write_reports()
                self.assertIn(path, self.git("ls-tree", "-r", "--name-only", self.commit).splitlines())
                errors = self.check()
                self.assertEqual(len(errors), 1)
                self.assertIn("target source cannot include Git/output directories: " + path, errors[0])
                self.assertEqual(self.git("rev-parse", "HEAD").strip(), checkout_commit)
                self.assertTrue((self.repository / ".git").is_dir())
                self.assertEqual((self.repository / ".git/config").read_bytes(), checkout_config)
                self.assertFalse((self.repository / ".git/fixture.txt").exists())
                self.assertFalse((self.repository / ".irisx").exists())


if __name__ == "__main__":
    unittest.main()
