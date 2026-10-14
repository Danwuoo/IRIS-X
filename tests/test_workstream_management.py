"""Offline management contract checks using new synthetic repository roots only."""

from __future__ import annotations

import copy
from contextlib import redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import workstream_management as management


class ManagementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="irisx-management-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repository"
        self.root.mkdir()
        self.catalog = {
            "format": "irisx.documents.v1",
            "managed_scopes": ["docs/managed/**"],
            "documents": [self.document("plan", "docs/managed/PLAN.md", "plan")],
            "legacy_indexes": [],
        }
        self.tasks = {
            "TASK-A.json": {
                "format": "irisx.task.v1",
                "id": "TASK-A",
                "title": "Synthetic engineering task",
                "workstream": "core",
                "state": "planned",
                "depends_on": [],
                "owner_role": "developer",
                "plan_ref": "plan",
                "scope_paths": ["src/irisx/example.py", "tests/test_example.py"],
                "base_branch": "example/base",
                "head_branch": "example/task-a",
                "base_commit": None,
                "implementation_commit": None,
                "acceptance": ["A2-1"],
                "blockers": [],
                "handoff_ref": None,
                "verification_refs": [],
                "review_refs": [],
                "concurrency_group": None,
            }
        }
        self.write_text("docs/managed/PLAN.md", "# Synthetic plan\n\n- A2-1: Record one outcome.\n")
        self.write_json("docs/workstreams/registry.json", {
            "format": "irisx/workstream-navigation-v1",
            "workstreams": [
                {"id": name, "role": role, "status_path": f"docs/workstreams/{name}/STATUS.md"}
                for name, role in (("core", "shared"), ("arc-agi-2", "domain"), ("line-b", "unassigned"))
            ],
        })
        self.flush()

    @staticmethod
    def document(doc_id: str, path: str, kind: str = "guide") -> dict:
        return {"id": doc_id, "path": path, "kind": kind, "workstream": "core",
                "status": "active", "owner_role": "developer",
                "related_tasks": ["TASK-A"], "supersedes": []}

    def write_text(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_json(self, relative: str, data: object) -> None:
        self.write_text(relative, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def flush(self, *, board: bool = True) -> None:
        self.write_json("docs/management/documents.json", self.catalog)
        for filename, data in self.tasks.items():
            self.write_json("docs/management/tasks/" + filename, data)
        if board:
            # Invalid metadata may itself prevent rendering. Validation must
            # still identify the intended fault, not only a stale board.
            try:
                rendered = management.render_board(self.root)
            except (ValueError, OSError, KeyError, TypeError):
                return
            self.write_text("docs/management/BOARD.md", rendered)

    def issues(self) -> list[str]:
        self.flush()
        return management.validate(self.root)

    def assert_rejected(self, *fragments: str) -> list[str]:
        issues = self.issues()
        self.assertTrue(issues, "invalid synthetic metadata was accepted")
        combined = "\n".join(issues).lower()
        self.assertTrue(any(fragment.lower() in combined for fragment in fragments), combined)
        return issues

    def prepare_review_ready(self) -> None:
        task = self.tasks["TASK-A.json"]
        task.update(state="review_ready", implementation_commit="a" * 40, handoff_ref="handoff")
        self.catalog["documents"].append(self.document("handoff", "docs/managed/HANDOFF.md", "evidence"))
        self.write_text("docs/managed/HANDOFF.md", "# Developer handoff\n\nSelf-review only.\n")

    def prepare_verified(self) -> dict:
        # A synthetic positive is bound to an actual local Git commit that
        # contains the task controls and code. A 40-character string alone is
        # not review evidence.
        self.write_text("src/irisx/example.py", "VALUE = 'synthetic source'\n")
        self.write_text("tests/test_example.py", "# Synthetic source; never collected here.\n")
        self.flush()
        for arguments in (["init", "--quiet"], ["add", "."],
                          ["-c", "user.name=Synthetic Fixture", "-c", "user.email=fixture@example.invalid",
                           "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Synthetic code checkpoint"]):
            subprocess.run(["git", *arguments], cwd=self.root, check=True, capture_output=True)
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, check=True,
                                capture_output=True, text=True).stdout.strip()
        self.prepare_review_ready()
        task = self.tasks["TASK-A.json"]
        task.update(state="verified", implementation_commit=commit, review_refs=["review"])
        self.catalog["documents"].append(self.document("review", "docs/managed/REVIEW.json", "evidence"))
        review = {"format": "irisx.review.v1", "target_commit": commit,
                  "reviewer_role": "independent", "outcome": "verified", "limitations": [],
                  "source": "Synthetic independent review fixture; not actual acceptance",
                  "scope_paths": [*task["scope_paths"], "docs/managed/PLAN.md"]}
        self.write_json("docs/managed/REVIEW.json", review)
        return review

    def test_valid_synthetic_metadata(self) -> None:
        self.assertEqual(management.validate(self.root), [])

    def test_generated_board_is_deterministic_and_checks_are_read_only(self) -> None:
        before = {path.relative_to(self.root): path.read_bytes()
                  for path in self.root.rglob("*") if path.is_file()}
        first = management.render_board(self.root)
        self.assertEqual(first, management.render_board(self.root))
        self.assertIn("TASK-A", first)
        self.assertIn("planned", first)
        self.assertEqual(management.validate(self.root), [])
        after = {path.relative_to(self.root): path.read_bytes()
                 for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_duplicate_json_keys_rejected_at_any_depth(self) -> None:
        for content in ('{"id": 1, "id": 2}', '{"outer": {"id": 1, "id": 2}}'):
            with self.subTest(content=content):
                path = self.root / "duplicate.json"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    management.load_json(path)

    def test_validator_reports_duplicate_json_keys(self) -> None:
        self.write_text("docs/management/tasks/TASK-A.json", '{"format": "irisx.task.v1", "id": "A", "id": "B"}\n')
        combined = "\n".join(management.validate(self.root)).lower()
        self.assertIn("duplicate", combined)

    def test_duplicate_document_id_rejected(self) -> None:
        self.catalog["documents"].append(copy.deepcopy(self.catalog["documents"][0]))
        self.assert_rejected("duplicate")

    def test_duplicate_task_id_rejected(self) -> None:
        self.tasks["another.json"] = copy.deepcopy(self.tasks["TASK-A.json"])
        self.assert_rejected("duplicate")

    def test_duplicate_legacy_ids_rejected_across_indexes_and_documents(self) -> None:
        index = {"id": "legacy", "url": "https://github.com/example/repo/blob/" + "a" * 40 + "/README.md",
                 "scope": ["legacy/**"]}
        self.catalog["legacy_indexes"] = [index, copy.deepcopy(index)]
        self.assert_rejected("duplicate legacy")
        self.catalog["legacy_indexes"] = [dict(index, id="plan")]
        self.assert_rejected("duplicate legacy")

    def test_invalid_baseline_sha_cannot_disable_changed_document_checks(self) -> None:
        for value in ("not-a-sha", "a" * 39, 42, True):
            with self.subTest(value=value):
                self.catalog["baseline_commit"] = value
                self.assert_rejected("baseline", "sha")

    def test_required_task_strings_reject_empty_or_non_string_values(self) -> None:
        task = self.tasks["TASK-A.json"]
        for field in ("id", "title", "owner_role", "base_branch", "head_branch", "plan_ref"):
            original = task[field]
            for value in (None, "", "   ", [], {}, 42):
                with self.subTest(field=field, value=value):
                    task[field] = value
                    self.assert_rejected("string", "field", "unhashable")
            task[field] = original

    def test_task_filename_must_match_generated_task_link(self) -> None:
        self.tasks["different-name.json"] = self.tasks.pop("TASK-A.json")
        (self.root / "docs/management/tasks/TASK-A.json").unlink()
        self.assert_rejected("filename", "mismatch")

    def test_invalid_states_rejected(self) -> None:
        for state in ("done", "VERIFIED", "", 42):
            with self.subTest(state=state):
                self.tasks["TASK-A.json"]["state"] = state
                self.assert_rejected("state")

    def test_blocked_requires_a_concrete_blocker(self) -> None:
        self.tasks["TASK-A.json"]["state"] = "blocked"
        self.assert_rejected("blocker")
        self.tasks["TASK-A.json"]["blockers"] = ["Unavailable test interpreter"]
        self.assertEqual(self.issues(), [])

    def test_unknown_executable_fields_rejected_without_execution(self) -> None:
        target = self.root / "MUST-NOT-EXIST"
        self.tasks["TASK-A.json"]["command"] = "create MUST-NOT-EXIST"
        self.assert_rejected("unknown", "only", "field")
        self.assertFalse(target.exists())
        del self.tasks["TASK-A.json"]["command"]
        self.catalog["documents"][0]["execute"] = "create MUST-NOT-EXIST"
        self.assert_rejected("unknown", "only", "field")
        self.assertFalse(target.exists())

    def test_unknown_catalog_fields_rejected(self) -> None:
        self.catalog["run_authorized"] = True
        self.assert_rejected("unknown", "only", "field")

    def test_document_paths_cannot_escape_or_be_absolute(self) -> None:
        for path in ("../outside.md", "/tmp/outside.md", "C:\\outside.md", "docs/../outside.md"):
            with self.subTest(path=path):
                self.catalog["documents"][0]["path"] = path
                self.assert_rejected("path", "escape", "relative")

    def test_scope_paths_cannot_escape_or_grant_whole_repository(self) -> None:
        for path in ("../src/**", "/src/**", "C:\\src\\*", "**"):
            with self.subTest(path=path):
                self.tasks["TASK-A.json"]["scope_paths"] = [path]
                self.assert_rejected("scope", "path", "explicit")

    def test_missing_document_rejected(self) -> None:
        (self.root / "docs/managed/PLAN.md").unlink()
        self.assert_rejected("missing", "unreadable")

    def test_unregistered_active_document_rejected(self) -> None:
        self.write_text("docs/managed/NEW.md", "# New active guide\n")
        self.assert_rejected("unregistered", "not registered")

    def test_remote_sources_require_full_commit_pins_and_one_location(self) -> None:
        doc = self.catalog["documents"][0]
        del doc["path"]
        for pin in ("main", "cc14bd1", "a" * 39):
            with self.subTest(pin=pin):
                doc["url"] = f"https://github.com/example/repo/blob/{pin}/docs/PLAN.md"
                self.assert_rejected("pin", "url", "commit")
        doc["url"] = "https://github.com/example/repo/blob/" + "a" * 40 + "/docs/PLAN.md"
        doc["path"] = "docs/managed/PLAN.md"
        self.assert_rejected("one", "either", "path", "url")

    def test_dangling_document_and_task_references_rejected(self) -> None:
        task = self.tasks["TASK-A.json"]
        for field, value in (("plan_ref", "missing"), ("handoff_ref", "missing"),
                             ("verification_refs", ["missing"]), ("review_refs", ["missing"]),
                             ("depends_on", ["missing"])):
            with self.subTest(field=field):
                original = copy.deepcopy(task[field])
                task[field] = value
                self.assert_rejected("missing", "unknown", "dangling")
                task[field] = original
        doc = self.catalog["documents"][0]
        for field in ("related_tasks", "supersedes"):
            with self.subTest(field=field):
                original = doc[field]
                doc[field] = ["missing"]
                self.assert_rejected("missing", "unknown", "dangling")
                doc[field] = original

    def test_acceptance_check_must_exist_in_canonical_plan(self) -> None:
        self.tasks["TASK-A.json"]["acceptance"] = ["A2-999"]
        self.assert_rejected("acceptance", "check")

    def prepare_remote_plan(self) -> None:
        plan = self.catalog["documents"][0]
        del plan["path"]
        plan["url"] = "https://github.com/example/repo/blob/" + "a" * 40 + "/PLAN.md"
        (self.root / "docs/managed/PLAN.md").unlink()

    def test_unavailable_remote_plan_check_is_explicitly_unverified(self) -> None:
        self.prepare_remote_plan()
        self.tasks["TASK-A.json"]["acceptance"] = ["A2-999"]
        with mock.patch.object(management.subprocess, "run", return_value=mock.Mock(returncode=1, stdout="")):
            self.assert_rejected("cannot validate plan/check")

    def test_remote_plan_checks_use_available_pinned_git_content(self) -> None:
        self.prepare_remote_plan()
        available = mock.Mock(returncode=0, stdout="# Pinned plan\n\n- A2-1: A known check.\n")
        with mock.patch.object(management.subprocess, "run", return_value=available) as read:
            self.assertEqual(self.issues(), [])
            self.assertEqual(read.call_args.args[0], ["git", "show", "a" * 40 + ":PLAN.md"])
            self.tasks["TASK-A.json"]["acceptance"] = ["A2-999"]
            self.assert_rejected("check")

    def test_dependency_cycle_rejected(self) -> None:
        second = copy.deepcopy(self.tasks["TASK-A.json"])
        second.update(id="TASK-B", title="Second synthetic task", head_branch="example/task-b", depends_on=["TASK-A"])
        self.tasks["TASK-B.json"] = second
        self.tasks["TASK-A.json"]["depends_on"] = ["TASK-B"]
        self.assert_rejected("cycle", "cyclic")

    def test_stale_board_rejected(self) -> None:
        self.write_text("docs/management/BOARD.md", "# Manually edited stale board\n")
        issues = "\n".join(management.validate(self.root)).lower()
        self.assertTrue("board" in issues and ("stale" in issues or "generated" in issues), issues)

    def test_review_ready_requires_checkpoint_and_handoff(self) -> None:
        self.tasks["TASK-A.json"]["state"] = "review_ready"
        self.assert_rejected("implementation", "handoff")
        self.prepare_review_ready()
        self.assertEqual(self.issues(), [])

    def test_verified_requires_review_and_matching_independent_identity(self) -> None:
        self.prepare_review_ready()
        self.tasks["TASK-A.json"]["state"] = "verified"
        self.assert_rejected("review")
        self.tasks["TASK-A.json"]["state"] = "planned"
        # Prepare a fresh fixture here to avoid duplicate handoff registration.
        self.catalog["documents"] = [self.catalog["documents"][0]]
        (self.root / "docs/managed/HANDOFF.md").unlink()
        review = self.prepare_verified()
        self.assertEqual(self.issues(), [])
        for field, value in (("target_commit", "b" * 40), ("reviewer_role", "self-review"),
                             ("outcome", "changes_requested"), ("source", None)):
            with self.subTest(field=field):
                changed = copy.deepcopy(review)
                changed[field] = value
                self.write_json("docs/managed/REVIEW.json", changed)
                self.assert_rejected("review", "target", "independent")

    def test_limited_review_keeps_limitations_visible(self) -> None:
        review = self.prepare_verified()
        review.update(outcome="verified_with_limits", limitations=["Linux-only check remains unexecuted"])
        self.write_json("docs/managed/REVIEW.json", review)
        self.assertEqual(self.issues(), [])
        board = management.render_board(self.root)
        self.assertIn("Linux-only check remains unexecuted", board)

    def test_fake_sha_without_git_is_not_independent_acceptance(self) -> None:
        self.prepare_review_ready()
        task = self.tasks["TASK-A.json"]
        task.update(state="verified", review_refs=["review"])
        self.catalog["documents"].append(self.document("review", "docs/managed/REVIEW.json", "evidence"))
        self.write_json("docs/managed/REVIEW.json", {
            "format": "irisx.review.v1", "target_commit": "a" * 40,
            "reviewer_role": "independent", "outcome": "verified",
            "limitations": [], "source": "Synthetic fixture; no actual review",
            "scope_paths": [*task["scope_paths"], "docs/managed/PLAN.md"],
        })
        self.assert_rejected("review", "unbound")
        self.assertEqual(management.review_status(self.root)["TASK-A"]["historical_verified"], [])

    def test_review_provenance_and_limitations_require_concrete_types(self) -> None:
        review = self.prepare_verified()
        invalid = [
            {"source": True}, {"source": []}, {"source": "   "},
            {"limitations": "AB"}, {"limitations": {}}, {"limitations": [None]},
            {"outcome": []},
            {"outcome": "verified_with_limits", "limitations": []},
        ]
        for change in invalid:
            with self.subTest(change=change):
                self.write_json("docs/managed/REVIEW.json", dict(review, **change))
                self.assert_rejected("review", "provenance", "limitations")

    def test_explicit_render_uses_path_guard_before_reading_or_writing_board(self) -> None:
        """The dev writer must use the same guard as read-only validation."""
        spec = importlib.util.spec_from_file_location("irisx_dev_synthetic_test", ROOT / "tools/dev.py")
        dev = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"workstream_management": management}):
            spec.loader.exec_module(dev)
        board = self.root / "docs/management/BOARD.md"
        before = board.read_bytes()
        with mock.patch.object(dev, "ROOT", self.root), \
             mock.patch.object(dev, "safe_path", side_effect=ValueError("linked generated BOARD")) as guard, \
             mock.patch.object(dev, "render_board") as render, redirect_stderr(io.StringIO()):
            self.assertEqual(dev.main(["render"]), 1)
        guard.assert_called_once_with(self.root, "docs/management/BOARD.md")
        render.assert_not_called()
        self.assertEqual(board.read_bytes(), before)

    def test_invalid_sha_rejected(self) -> None:
        self.prepare_review_ready()
        self.tasks["TASK-A.json"]["implementation_commit"] = "abc123"
        self.assert_rejected("commit", "sha")

    def test_concurrent_writable_overlap_rejected_but_disjoint_scopes_allowed(self) -> None:
        first = self.tasks["TASK-A.json"]
        first.update(state="in_progress", concurrency_group="same-batch", scope_paths=["src/irisx/shared/**"])
        second = copy.deepcopy(first)
        second.update(id="TASK-B", head_branch="example/task-b", scope_paths=["src/irisx/shared/module.py"])
        self.tasks["TASK-B.json"] = second
        self.assert_rejected("overlap", "conflict")
        second["scope_paths"] = ["src/irisx/domains/line_b/**"]
        self.assertEqual(self.issues(), [])

    def test_linked_document_path_rejected(self) -> None:
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "NOTE.md").write_text("# Outside synthetic document\n", encoding="utf-8")
        linked = self.root / "docs/managed/linked"
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Platform does not permit test symlinks: {exc}")
        self.catalog["documents"].append(self.document("linked", "docs/managed/linked/NOTE.md"))
        self.assert_rejected("linked", "symlink", "escape")

    def test_link_detection_rejects_linked_components_without_os_privilege(self) -> None:
        """Exercise the link guard where Windows cannot create real symlinks."""
        component = self.root / "docs/managed"
        original = Path.is_symlink
        self.flush()
        with mock.patch.object(Path, "is_symlink", autospec=True,
                               side_effect=lambda path: path == component or original(path)):
            issues = "\n".join(management.validate(self.root)).lower()
        self.assertTrue("linked" in issues or "symlink" in issues, issues)


if __name__ == "__main__":
    unittest.main()
