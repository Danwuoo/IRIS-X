"""Onboarding safety and metadata tests using new synthetic sandbox roots."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import onboarding_check as onboarding

COMMIT = "a" * 40


class OnboardingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="irisx-onboarding-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repository"
        self.root.mkdir()
        self.task = onboarding.exercise_task(COMMIT, "example/base", "exercise/synthetic")
        self.finished = onboarding.finish_task(self.task, COMMIT, self.suite_report())
        self.catalog = {"format": "irisx.documents.v1", "documents": [], "legacy_indexes": []}
        onboarding.register_document(self.catalog, onboarding.PLAN_ID, onboarding.PLAN_PATH, "plan")
        onboarding.register_document(self.catalog, onboarding.HANDOFF_ID, onboarding.HANDOFF_PATH, "evidence")
        for doc_id, path in zip(onboarding.RESEARCH_IDS, (
                "research/native-continuation-20261013/primary-method-assessment.md",
                "docs/plan/2026-10-13-native-research-continuation.md")):
            self.catalog["documents"].append({
                "id": doc_id, "url": "https://github.com/Danwuoo/IRIS-X/blob/" + onboarding.RESEARCH_SHA + "/" + path,
                "kind": "reference", "workstream": "arc-agi-2", "status": "active",
                "owner_role": "researcher", "related_tasks": [], "supersedes": [],
            })
        self.write("docs/README.md", "# Synthetic docs\n\n[Board](management/BOARD.md)\n")
        self.write("docs/management/BOARD.md", f"# Synthetic board\n\n[{onboarding.TASK_ID}](tasks/{onboarding.TASK_ID}.json)\n")
        self.write(onboarding.PLAN_PATH, "# Synthetic plan\n\n- OB1-1: Navigation exercise.\n\n"
                   "[Program](../../src/irisx/domains/line_b/flow.py)\n")
        self.write(onboarding.HANDOFF_PATH, "# Synthetic developer handoff\n\n"
                   f"target_commit: {COMMIT}\n\nIndependent review pending.\n")
        self.write(f"docs/management/tasks/{onboarding.TASK_ID}.json", json.dumps(self.finished) + "\n")
        self.write("src/irisx/domains/line_b/flow.py", "raise RuntimeError('NAVIGATION_MUST_NOT_EXECUTE')\n")
        self.write("docs/workstreams/arc-agi-2/STATUS.md", "# Synthetic status\n\n[Research](RESEARCH.md)\n")
        self.write("docs/workstreams/arc-agi-2/RESEARCH.md", "# Synthetic source links\n\n" + "\n".join(
            "[Original](" + doc["url"] + ")" for doc in self.catalog["documents"] if "url" in doc) + "\n")

    def write(self, relative: str, value: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    @staticmethod
    def suite_report() -> dict:
        return {"format": "irisx.suite-report.v1", "suite": "line-b",
                "status": "passed", "tests": 2, "failures": 0, "errors": 0, "skips": 0,
                "expected_skips": 0, "unexpected_skips": 0, "blocked": 0, "exit_code": 0,
                "target_commit": COMMIT, "attestable": True, "evidence_kind": "commit"}

    def test_handoff_binds_committed_exercise_without_changing_source_base(self) -> None:
        exercise = "b" * 40
        report = dict(self.suite_report(), target_commit=exercise)
        task = onboarding.finish_task(self.task, exercise, report, base_commit=COMMIT)
        self.assertEqual(task["base_commit"], COMMIT)
        self.assertEqual(task["implementation_commit"], exercise)

    def test_development_pass_cannot_support_commit_handoff(self) -> None:
        for change in ({"attestable": False}, {"evidence_kind": "development"}, {"target_commit": None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                onboarding.finish_task(self.task, COMMIT, dict(self.suite_report(), **change))

    def test_task_is_synthetic_separate_and_has_no_review_claim(self) -> None:
        self.assertEqual(self.task["workstream"], "line-b")
        self.assertEqual(self.task["state"], "in_progress")
        self.assertEqual(self.task["review_refs"], [])
        self.assertEqual(self.task["base_commit"], COMMIT)
        self.assertIn("WSF-04", self.task["depends_on"])
        self.assertNotIn("command", self.task)

    def test_task_rejects_short_or_missing_source_commit(self) -> None:
        for commit in ("abc123", "", "a" * 39):
            with self.subTest(commit=commit), self.assertRaises(ValueError):
                onboarding.exercise_task(commit, "example/base", "exercise/synthetic")

    def test_finish_task_requires_passing_commit_bound_self_tests(self) -> None:
        result = onboarding.finish_task(self.task, COMMIT, self.suite_report())
        self.assertEqual(result["state"], "review_ready")
        self.assertEqual(result["implementation_commit"], COMMIT)
        self.assertEqual(result["handoff_ref"], onboarding.HANDOFF_ID)
        self.assertEqual(result["review_refs"], [])
        self.assertEqual(self.task["state"], "in_progress")
        for change in ({"status": "failed"}, {"target_commit": "b" * 40}, {"tests": 0},
                       {"errors": 1}, {"blocked": 1}, {"unexpected_skips": 1}, {"exit_code": 1},
                       {"suite": "core"}, {"format": "unknown"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                onboarding.finish_task(self.task, COMMIT, dict(self.suite_report(), **change))

    def test_finish_task_does_not_replace_an_original_or_verified_task(self) -> None:
        for change in ({"id": "WSF-04"}, {"state": "verified"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                onboarding.finish_task(dict(self.task, **change), COMMIT, self.suite_report())

    def test_new_files_never_overwrite_original_sandbox_files(self) -> None:
        path = "docs/original.md"
        self.write(path, "original synthetic fixture\n")
        with self.assertRaises(FileExistsError):
            onboarding.write_new(self.root, path, "replacement")
        self.assertEqual((self.root / path).read_text(encoding="utf-8"), "original synthetic fixture\n")

    def test_registration_rejects_existing_identity_or_path(self) -> None:
        before = copy.deepcopy(self.catalog)
        for doc_id, path in ((onboarding.PLAN_ID, "docs/new.md"), ("new-doc", onboarding.PLAN_PATH)):
            with self.subTest(doc_id=doc_id), self.assertRaises(ValueError):
                onboarding.register_document(self.catalog, doc_id, path, "guide")
        self.assertEqual(self.catalog, before)

    def test_output_must_be_new_ignored_directory_with_no_escape(self) -> None:
        accepted = self.root / ".irisx/core/onboarding/new"
        self.assertEqual(onboarding.output_path(self.root, accepted), accepted)
        accepted.mkdir(parents=True)
        for path in (accepted, self.root / "output", Path(self.tmp.name) / "outside",
                     self.root / ".irisx/../outside"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                onboarding.output_path(self.root, path)

    def test_output_rejects_linked_components_without_windows_privilege(self) -> None:
        component = self.root / ".irisx"
        original = Path.is_symlink
        with mock.patch.object(Path, "is_symlink", autospec=True,
                               side_effect=lambda path: path == component or original(path)):
            with self.assertRaises(ValueError):
                onboarding.output_path(self.root, component / "core/new")

    def test_complete_navigation_and_research_links_are_read_only(self) -> None:
        task = self.finished
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        chain = onboarding.navigation_chain(self.root, self.catalog, task)
        sources = onboarding.research_sources(self.root, self.catalog)
        self.assertEqual([step["role"] for step in chain], ["entry", "board", "task", "plan", "code", "handoff"])
        self.assertEqual(len(sources), 2)
        self.assertTrue(all(source["remote_availability"] == "unverified" for source in sources))
        self.assertTrue(all(source["research_content_review"] == "pending human review" for source in sources))
        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()})

    def test_navigation_catches_missing_entry_or_handoff(self) -> None:
        task = self.finished
        self.write("docs/README.md", "# Missing board entry\n")
        with self.assertRaises(ValueError):
            onboarding.navigation_chain(self.root, self.catalog, task)
        self.write("docs/README.md", "[Board](management/BOARD.md)\n")
        (self.root / onboarding.HANDOFF_PATH).unlink()
        with self.assertRaises(ValueError):
            onboarding.navigation_chain(self.root, self.catalog, task)

    def test_research_requires_fixed_r4_r5_catalog_and_reading_entry_binding(self) -> None:
        for changed in ("main", "b" * 40):
            with self.subTest(changed=changed):
                catalog = copy.deepcopy(self.catalog)
                catalog["documents"][-1]["url"] = catalog["documents"][-1]["url"].replace(onboarding.RESEARCH_SHA, changed)
                with self.assertRaises(ValueError):
                    onboarding.research_sources(self.root, catalog)
        self.write("docs/workstreams/arc-agi-2/STATUS.md", "# Missing research entry\n")
        with self.assertRaises(ValueError):
            onboarding.research_sources(self.root, self.catalog)

    def test_failed_source_identity_command_produces_failed_report_not_fake_pass(self) -> None:
        output = self.root / ".irisx/core/onboarding/failed-source"
        failed = mock.Mock(returncode=1, stdout="", stderr="synthetic source identity failure")
        with mock.patch.object(onboarding.subprocess, "run", return_value=failed):
            report = onboarding.run_onboarding(self.root, output)
        self.assertEqual(report["status"], "failed")
        self.assertIsNone(report["target_commit"])
        self.assertEqual(report["independent_review"], "pending")
        self.assertEqual(report["commands"][0]["exit_code"], 1)
        self.assertEqual(json.loads((output / "report.json").read_text(encoding="utf-8")), report)


if __name__ == "__main__":
    unittest.main()
