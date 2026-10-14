"""Review lifecycle checks on new constant-only local Git repositories.

The reports in these fixtures simulate policy inputs; they are not reviews of
IRIS-X or independent acceptance of any delivered implementation.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import workstream_management as management


class ReviewLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="irisx-review-lifecycle-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = {"format": "irisx.documents.v1", "managed_scopes": ["docs/managed/**"],
                        "legacy_indexes": [], "documents": [
                            self.document("plan", "docs/managed/PLAN.md", "plan", ["TASK-A", "TASK-B", "TASK-C"])
                        ]}
        self.tasks = {
            key: self.task(key, scopes, depends) for key, scopes, depends in (
                ("TASK-A", ["src/irisx/core/**", "tests/test_core.py", "pyproject.toml",
                            ".github/workflows/core.yml"], []),
                ("TASK-B", ["src/irisx/line_b/**", "tests/test_line.py"], ["TASK-A"]),
                ("TASK-C", ["tools/third.py"], ["TASK-B"]),
            )
        }
        self.write("docs/managed/PLAN.md", "# Synthetic plan\n\n- CHECK-1: Inspect constants only.\n")
        # Import sentinels prove the metadata checker never imports source/tests.
        self.write("src/irisx/core/value.py", "raise RuntimeError('MUST NOT IMPORT REVIEWED SOURCE')\n")
        self.write("tests/test_core.py", "raise RuntimeError('MUST NOT COLLECT SYNTHETIC SOURCE')\n")
        self.write("src/irisx/line_b/value.py", "VALUE = 1\n")
        self.write("tests/test_line.py", "# constant-only fixture\n")
        self.write("tools/third.py", "VALUE = 3\n")
        self.write("pyproject.toml", "[project]\nname='synthetic-fixture'\nversion='0.0.0'\n")
        self.write(".github/workflows/core.yml", "# synthetic CI input; never executed\n")
        self.flush()
        self.git("init", "--quiet")
        self.target = self.commit("Synthetic source and task controls")
        self.approve("TASK-A")
        self.flush()

    @staticmethod
    def document(key, path, kind="evidence", related=None, supersedes=None):
        return {"id": key, "path": path, "kind": kind, "workstream": "core", "status": "active",
                "owner_role": "synthetic-fixture", "related_tasks": related or [],
                "supersedes": supersedes or []}

    @staticmethod
    def task(key, scopes, depends):
        return {"format": "irisx.task.v1", "id": key, "title": "Synthetic " + key,
                "workstream": "core", "state": "planned", "depends_on": depends,
                "owner_role": "synthetic-fixture", "plan_ref": "plan", "scope_paths": scopes,
                "base_branch": "synthetic/base", "head_branch": "synthetic/" + key,
                "base_commit": None, "implementation_commit": None, "acceptance": ["CHECK-1"],
                "blockers": [], "handoff_ref": None, "verification_refs": [], "review_refs": [],
                "concurrency_group": None}

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_json(self, relative, data):
        self.write(relative, json.dumps(data, indent=2) + "\n")

    def git(self, *args):
        result = subprocess.run(["git", *args], cwd=self.root, capture_output=True,
                                text=True, encoding="utf-8", check=True)
        return result.stdout.strip()

    def commit(self, message):
        self.git("add", ".")
        self.git("-c", "user.name=Synthetic Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", message)
        return self.git("rev-parse", "HEAD")

    def approve(self, key, review_id=None, *, supersedes=None):
        review_id = review_id or key + "-pass"
        task = self.tasks[key]
        task.update(state="verified", implementation_commit=self.target,
                    handoff_ref=key + "-handoff", review_refs=[review_id])
        handoff_path = "docs/managed/" + key + "-HANDOFF.md"
        if not any(doc["id"] == task["handoff_ref"] for doc in self.catalog["documents"]):
            self.catalog["documents"].append(self.document(task["handoff_ref"], handoff_path, related=[key]))
            self.write(handoff_path, "# Synthetic developer handoff; no actual review\n")
        report = {"format": "irisx.review.v1", "target_commit": self.target,
                  "reviewer_role": "independent", "outcome": "verified", "limitations": [],
                  "source": "Synthetic independent-review policy fixture; not actual acceptance",
                  "scope_paths": [*task["scope_paths"], "docs/managed/PLAN.md"]}
        self.add_review(review_id, report, related=[key], supersedes=supersedes)
        return report

    def add_review(self, key, report, *, related=None, supersedes=None):
        path = "docs/managed/" + key + ".json"
        self.catalog["documents"].append(self.document(key, path, related=related, supersedes=supersedes))
        self.write_json(path, report)

    def negative(self, key="TASK-A-changes", *, related=None, supersedes=None):
        self.add_review(key, {
            "format": "irisx.review.v1", "target_commit": self.target,
            "reviewer_role": "independent", "outcome": "changes_requested",
            "source": "Synthetic negative independent-review fixture; not actual acceptance",
            "limitations": ["A correction is required."],
            "findings": [{"id": "SYNTHETIC-1", "summary": "Policy negative control"}],
        }, related=related, supersedes=supersedes)

    def flush(self, *, board=True):
        self.write_json("docs/management/documents.json", self.catalog)
        for key, task in self.tasks.items():
            self.write_json("docs/management/tasks/" + key + ".json", task)
        if board:
            self.write("docs/management/BOARD.md", management.render_board(self.root))

    def status(self, key="TASK-A"):
        self.flush(board=False)
        states = management.review_status(self.root)
        self.write("docs/management/BOARD.md", management.render_board(self.root, review_states=states))
        return states[key]

    def assert_current(self, key="TASK-A"):
        self.assertTrue(self.status(key)["current_verified"])
        self.assertEqual(management.validate(self.root), [])

    def assert_stale(self, fragment, key="TASK-A"):
        status = self.status(key)
        self.assertFalse(status["current_verified"])
        self.assertIn(fragment.lower(), "; ".join(status["reasons"]).lower())
        issues = "; ".join(management.validate(self.root))
        self.assertIn("verified lacks current", issues)
        # Historical attribution is preserved even though current acceptance
        # cannot be inherited by changed source or a superseding review.
        self.assertTrue(status["historical_verified"])
        self.assertIn(self.target, [item["target_commit"] for item in status["historical_verified"]])
        return status

    def test_actual_git_bound_positive_never_imports_source(self):
        self.assert_current()
        self.assertIn("Historical verified-at", management.render_board(self.root))

    def test_metadata_only_delivery_commit_preserves_current_review(self):
        self.flush()
        delivery = self.commit("Synthetic report and handoff metadata only")
        self.assertNotEqual(delivery, self.target)
        self.assert_current()

    def test_unrelated_line_committed_and_working_changes_preserve_review(self):
        self.write("src/irisx/arc/unrelated.py", "VALUE = 'unrelated line'\n")
        self.commit("Synthetic unrelated-line source")
        self.write("src/irisx/arc/unrelated.py", "VALUE = 'unrelated working edit'\n")
        self.write("src/irisx/arc/new.py", "VALUE = 'unrelated untracked source'\n")
        self.assert_current()

    def test_committed_source_change_cannot_reuse_old_pass(self):
        self.write("src/irisx/core/value.py", "VALUE = 'changed committed source'\n")
        self.commit("Synthetic source mutation")
        self.assert_stale("coverage changed")

    def test_staged_source_change_cannot_reuse_old_pass(self):
        self.write("src/irisx/core/value.py", "VALUE = 'staged mutation'\n")
        self.git("add", "src/irisx/core/value.py")
        self.assert_stale("coverage changed")

    def test_unstaged_source_change_cannot_reuse_old_pass(self):
        self.write("src/irisx/core/value.py", "VALUE = 'unstaged mutation'\n")
        self.assert_stale("coverage changed")

    def test_untracked_source_in_reviewed_scope_cannot_reuse_old_pass(self):
        self.write("src/irisx/core/new.py", "VALUE = 'new untracked source'\n")
        self.assert_stale("coverage changed")

    def test_dependency_configuration_is_reviewed_input(self):
        self.write("pyproject.toml", "[project]\nname='changed-fixture'\nversion='0.0.0'\n")
        self.assert_stale("coverage changed")

    def test_ci_configuration_is_reviewed_input(self):
        self.write(".github/workflows/core.yml", "# changed synthetic CI policy\n")
        self.assert_stale("coverage changed")

    def test_canonical_plan_change_requires_new_review(self):
        self.write("docs/managed/PLAN.md", "# Revised synthetic plan\n\n- CHECK-1: Changed requirement.\n")
        self.assert_stale("coverage changed")

    def test_plan_catalog_rebinding_cannot_hide_changed_canonical_requirements(self):
        self.catalog["documents"][0]["path"] = "docs/managed/NEW-PLAN.md"
        self.write("docs/managed/NEW-PLAN.md", "# Changed plan binding\n\n- CHECK-1: A different requirement.\n")
        report = management.load_json(self.root / "docs/managed/TASK-A-pass.json")
        report["scope_paths"].append("docs/managed/NEW-PLAN.md")
        self.write_json("docs/managed/TASK-A-pass.json", report)
        # The new plan is also covered, but it is not the reviewed plan binding.
        self.assert_stale("plan catalog binding")

    def test_executable_glob_outside_src_requires_full_declared_scope(self):
        self.tasks["TASK-A"]["scope_paths"].append("scripts/**")
        self.write("scripts/check.py", "VALUE = 'synthetic executable'\n")
        self.tasks["TASK-A"].update(state="planned", implementation_commit=None, review_refs=[])
        self.flush()
        self.target = self.commit("Synthetic script coverage")
        report = self.approve("TASK-A", "TASK-A-script-pass", supersedes=["TASK-A-pass"])
        report["scope_paths"].remove("scripts/**")
        self.write_json("docs/managed/TASK-A-script-pass.json", report)
        self.assert_stale("does not cover")

    def test_ignored_outputs_do_not_invalidate_reviewed_source(self):
        self.write(".gitignore", ".irisx/\n")
        self.commit("Synthetic ignored output rule")
        self.write(".irisx/synthetic/report.json", '{"status": "synthetic output"}\n')
        self.assert_current()

    def test_ignore_rule_cannot_hide_untracked_source_in_reviewed_scope(self):
        self.write(".gitignore", ".irisx/\nsrc/irisx/core/ignored.py\n")
        self.commit("Synthetic ignore rule")
        self.write("src/irisx/core/ignored.py", "VALUE = 'untracked ignored source'\n")
        self.assert_stale("coverage changed")

    def test_semantic_task_controls_cannot_be_hidden_as_delivery_metadata(self):
        self.tasks["TASK-A"]["depends_on"] = ["TASK-B"]
        self.assert_stale("task controls changed")

    def test_narrowing_current_task_scope_requires_new_review(self):
        self.tasks["TASK-A"]["scope_paths"] = ["src/irisx/core/value.py"]
        self.assert_stale("task controls changed")

    def test_positive_review_cannot_narrow_explicit_source_coverage(self):
        path = "docs/managed/TASK-A-pass.json"
        report = management.load_json(self.root / path)
        report["scope_paths"] = ["src/irisx/core/value.py", "docs/managed/PLAN.md"]
        self.write_json(path, report)
        self.assert_stale("does not cover")

    def test_positive_review_without_scope_is_historical_only(self):
        path = "docs/managed/TASK-A-pass.json"
        report = management.load_json(self.root / path)
        del report["scope_paths"]
        self.write_json(path, report)
        self.assert_stale("scope_paths")

    def test_superseded_pass_and_negative_replacement_reject_current_acceptance(self):
        self.catalog["documents"][-1]["status"] = "superseded"
        self.negative(related=["TASK-A"], supersedes=["TASK-A-pass"])
        self.tasks["TASK-A"]["review_refs"].append("TASK-A-changes")
        self.assert_stale("requests changes")

    def test_omitting_replacement_ref_and_task_association_cannot_restore_old_pass(self):
        self.negative(supersedes=["TASK-A-pass"])
        self.assert_stale("requests changes")

    def test_orphan_negative_related_task_cannot_be_omitted_from_task_refs(self):
        self.negative(related=["TASK-A"])
        self.assert_stale("requests changes")

    def test_ambiguous_active_positive_target_cannot_fall_back_to_older_pass(self):
        delivery = self.commit("Synthetic metadata delivery")
        report = management.load_json(self.root / "docs/managed/TASK-A-pass.json")
        report["target_commit"] = delivery
        self.add_review("TASK-A-other-target", report, related=["TASK-A"])
        self.assert_stale("different implementation commit")

    def test_blocked_current_review_vetoes_positive(self):
        self.negative(related=["TASK-A"])
        path = "docs/managed/TASK-A-changes.json"
        report = management.load_json(self.root / path)
        report["outcome"] = "blocked"
        self.write_json(path, report)
        self.assert_stale("blocks acceptance")

    def test_explicit_new_positive_replacement_can_resolve_negative(self):
        self.negative(related=["TASK-A"], supersedes=["TASK-A-pass"])
        self.approve("TASK-A", "TASK-A-new-pass", supersedes=["TASK-A-changes"])
        self.assert_current()

    def test_downstream_verified_requires_upstream_recorded_verified(self):
        self.approve("TASK-B")
        self.tasks["TASK-A"]["state"] = "changes_requested"
        self.assert_stale("upstream task", "TASK-B")

    def test_downstream_verified_requires_upstream_effective_current_review(self):
        self.approve("TASK-B")
        self.negative(related=["TASK-A"], supersedes=["TASK-A-pass"])
        self.assert_stale("upstream task", "TASK-B")

    def test_stale_upstream_invalidates_transitive_downstream_acceptance(self):
        self.approve("TASK-B")
        self.approve("TASK-C")
        self.write("src/irisx/core/value.py", "VALUE = 'stale upstream source'\n")
        self.assert_stale("upstream task", "TASK-C")

    def test_all_verified_upstream_controls_allow_current_downstream_review(self):
        self.approve("TASK-B")
        self.approve("TASK-C")
        self.assert_current("TASK-C")

    def test_draft_positive_is_historical_and_does_not_authorize_current_acceptance(self):
        self.catalog["documents"][-1]["status"] = "draft"
        self.assert_stale("no effective")

    def test_review_data_never_executes_commands(self):
        path = "docs/managed/TASK-A-pass.json"
        report = management.load_json(self.root / path)
        report["command"] = "create MUST-NOT-EXIST"
        self.write_json(path, report)
        self.assert_current()
        self.assertFalse((self.root / "MUST-NOT-EXIST").exists())


if __name__ == "__main__":
    unittest.main()
