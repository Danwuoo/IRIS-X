"""Structural ARC source navigation checks, never research-content acceptance."""

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import workstream_management as management

RESEARCH_PATH = "docs/workstreams/arc-agi-2/RESEARCH.md"


class ResearchNavigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="irisx-research-navigation-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repository"
        self.root.mkdir()
        canonical = (ROOT / RESEARCH_PATH).read_text(encoding="utf-8")
        self.source_url = re.search(
            r"https://github\.com/[^\s)]+/blob/[0-9a-f]{40}/research/[^\s)]+", canonical
        ).group(0)
        self.original_research = (canonical.splitlines()[0] + "\n\n"
                                  "Small structural clone; original research interpretation remains for human review.\n\n"
                                  f"[R1 original source]({self.source_url})\n")
        self.catalog = {
            "format": "irisx.documents.v1",
            "managed_scopes": ["docs/workstreams/**", "docs/plan/**"],
            "documents": [
                self.document("plan", "docs/plan/synthetic-research-navigation.md", "plan"),
                self.document("arc-status", "docs/workstreams/arc-agi-2/STATUS.md", "guide"),
                self.document("arc-research", RESEARCH_PATH, "reference"),
                {"id": "original-r1", "url": self.source_url, "kind": "reference",
                 "workstream": "arc-agi-2", "status": "active", "owner_role": "researcher",
                 "related_tasks": ["WSF-03"], "supersedes": []},
            ],
            "legacy_indexes": [],
        }
        self.task = {
            "format": "irisx.task.v1", "id": "WSF-03", "title": "Synthetic research navigation check",
            "workstream": "arc-agi-2", "state": "planned", "depends_on": [],
            "owner_role": "developer", "plan_ref": "plan",
            "scope_paths": ["docs/workstreams/arc-agi-2/STATUS.md"],
            "base_branch": "example/base", "head_branch": "example/navigation",
            "base_commit": None, "implementation_commit": None,
            "acceptance": ["A3-7"], "blockers": [], "handoff_ref": None,
            "verification_refs": [], "review_refs": [], "concurrency_group": None,
        }
        self.write_text("docs/plan/synthetic-research-navigation.md", "# Synthetic plan\n\n- A3-7: Structural research navigation.\n")
        self.write_text("docs/workstreams/arc-agi-2/STATUS.md", "# ARC STATUS\n\n[Research reading entry](RESEARCH.md)\n")
        self.write_text(RESEARCH_PATH, self.original_research)
        self.flush()

    @staticmethod
    def document(doc_id: str, path: str, kind: str) -> dict:
        return {"id": doc_id, "path": path, "kind": kind, "workstream": "arc-agi-2",
                "status": "active", "owner_role": "researcher",
                "related_tasks": ["WSF-03"], "supersedes": []}

    def write_text(self, path: str, text: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def flush(self) -> None:
        self.write_text("docs/management/documents.json", json.dumps(self.catalog, indent=2) + "\n")
        self.write_text("docs/management/tasks/WSF-03.json", json.dumps(self.task, indent=2) + "\n")
        self.write_text("docs/management/BOARD.md", management.render_board(self.root))

    def errors(self) -> str:
        self.flush()
        return "\n".join(management.validate(self.root)).lower()

    def test_small_canonical_navigation_clone_is_valid_and_read_only(self) -> None:
        before = {path.relative_to(self.root): path.read_bytes()
                  for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(management.validate(self.root), [])
        after = {path.relative_to(self.root): path.read_bytes()
                 for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_missing_research_catalog_entry_rejected(self) -> None:
        self.catalog["documents"] = [doc for doc in self.catalog["documents"] if doc["id"] != "arc-research"]
        errors = self.errors()
        self.assertIn("missing arc research entry", errors)

    def test_missing_research_file_rejected(self) -> None:
        (self.root / RESEARCH_PATH).unlink()
        errors = self.errors()
        self.assertIn("missing document", errors)
        self.assertIn("research.md", errors)

    def test_main_and_short_commit_research_sources_rejected(self) -> None:
        original_commit = self.source_url.split("/blob/", 1)[1].split("/", 1)[0]
        source = next(doc for doc in self.catalog["documents"] if doc["id"] == "original-r1")
        for pin in ("main", original_commit[:7], original_commit[:39]):
            with self.subTest(pin=pin):
                changed = self.source_url.replace("/blob/" + original_commit + "/", "/blob/" + pin + "/")
                source["url"] = changed
                self.write_text(RESEARCH_PATH, self.original_research.replace(self.source_url, changed))
                errors = self.errors()
                self.assertIn("unpinned", errors)
                self.assertIn("research source", errors)

    def test_pinned_research_source_must_be_individually_cataloged(self) -> None:
        self.catalog["documents"] = [doc for doc in self.catalog["documents"] if doc["id"] != "original-r1"]
        self.assertIn("dangling or unpinned research source", self.errors())

    def test_missing_pinned_local_git_source_is_reported_without_network(self) -> None:
        self.write_text(".git", "Synthetic marker; this is not original repository evidence.\n")
        unavailable = mock.Mock(returncode=1, stdout="")
        with mock.patch.object(management.subprocess, "run", return_value=unavailable) as local_git:
            self.assertIn("missing local pinned source object", self.errors())
        self.assertTrue(local_git.call_args_list)
        for call in local_git.call_args_list:
            self.assertEqual(call.args[0][:3], ["git", "cat-file", "-e"])
            self.assertNotIn("https://", " ".join(call.args[0]))

    def test_available_git_object_check_is_local_structure_not_remote_attestation(self) -> None:
        self.write_text(".git", "Synthetic marker; local Git operations are mocked.\n")
        available = mock.Mock(returncode=0, stdout="")
        with mock.patch.object(management.subprocess, "run", return_value=available) as local_git:
            self.assertEqual(self.errors(), "")
        commit, path = self.source_url.split("/blob/", 1)[1].split("/", 1)
        self.assertEqual(local_git.call_args.args[0], ["git", "cat-file", "-e", commit + ":" + path])

    def test_check_output_keeps_structural_and_independent_review_scope_explicit(self) -> None:
        spec = importlib.util.spec_from_file_location("irisx_dev_navigation_test", ROOT / "tools/dev.py")
        dev = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"workstream_management": management}):
            spec.loader.exec_module(dev)
        output = io.StringIO()
        with mock.patch.object(dev, "ROOT", self.root), redirect_stdout(output):
            self.assertEqual(dev.main(["check"]), 0)
        # This checks the scope of the tool's claim, not the research's meaning.
        self.assertIn("structure only", output.getvalue())
        self.assertIn("independent evidence review remains separate", output.getvalue())


if __name__ == "__main__":
    unittest.main()
