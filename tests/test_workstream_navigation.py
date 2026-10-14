"""Standalone navigation checks; no product imports, network or run fixtures."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = "docs/workstreams/registry.json"
SECTIONS = ("Scope", "Evidence", "Blockers", "Next", "Boundaries")


def validate_navigation(root: Path, data: object) -> list[str]:
    """Validate only navigation metadata and local status documents, never authority."""
    issues: list[str] = []
    if not isinstance(data, dict) or set(data) != {"format", "workstreams"}:
        return ["registry must contain only format and workstreams"]
    if data["format"] != "irisx/workstream-navigation-v1":
        issues.append("unsupported navigation format")
    rows = data["workstreams"]
    if not isinstance(rows, list) or not rows:
        return issues + ["workstreams must be a nonempty list"]
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "role", "status_path"}:
            issues.append("entry must contain only id, role and status_path")
            continue
        stream_id, role, relative = row["id"], row["role"], row["status_path"]
        if not isinstance(stream_id, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", stream_id):
            issues.append("invalid workstream id")
            continue
        if stream_id in seen_ids:
            issues.append("duplicate workstream id")
        seen_ids.add(stream_id)
        if not isinstance(role, str) or role not in {"shared", "domain", "unassigned"}:
            issues.append("invalid workstream role")
        expected = f"docs/workstreams/{stream_id}/STATUS.md"
        if not isinstance(relative, str) or relative != expected:
            issues.append("status_path must be the stream-local STATUS.md")
            continue
        if relative in seen_paths:
            issues.append("duplicate status path")
        seen_paths.add(relative)
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()):
            issues.append("status path escapes repository")
            continue
        # Reject links at every relative component, including directory links.
        parts = Path(relative).parts
        if any(root.joinpath(*parts[:index]).is_symlink() for index in range(1, len(parts) + 1)):
            issues.append("linked status path is not allowed")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            issues.append("status file missing or unreadable: " + relative)
            continue
        for section in SECTIONS:
            if not re.search(r"^## " + re.escape(section) + r"$", text, re.MULTILINE):
                issues.append("missing status section: " + section)
    return issues


class NavigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = {
            "format": "irisx/workstream-navigation-v1",
            "workstreams": [{"id": "example", "role": "unassigned",
                             "status_path": "docs/workstreams/example/STATUS.md"}],
        }
        self.status = self.root / self.data["workstreams"][0]["status_path"]
        self.status.parent.mkdir(parents=True)
        self.status.write_text("# Example\n\n" + "\n".join("## " + s for s in SECTIONS) + "\n", encoding="utf-8")

    def test_valid_synthetic_navigation(self) -> None:
        self.assertEqual(validate_navigation(self.root, self.data), [])

    def test_rejects_invalid_schema(self) -> None:
        for bad in (None, [], {}, {"format": "wrong", "workstreams": []}):
            with self.subTest(value=bad):
                self.assertTrue(validate_navigation(self.root, bad))

    def test_rejects_operational_fields(self) -> None:
        data = copy.deepcopy(self.data)
        data["workstreams"][0]["run_authorized"] = True
        self.assertTrue(validate_navigation(self.root, data))

    def test_rejects_duplicates(self) -> None:
        data = copy.deepcopy(self.data)
        data["workstreams"].append(copy.deepcopy(data["workstreams"][0]))
        self.assertIn("duplicate workstream id", validate_navigation(self.root, data))

    def test_rejects_nonlocal_or_cross_stream_paths(self) -> None:
        for path in ("../outside.md", "/tmp/STATUS.md", "C:\\STATUS.md",
                     "https://example.invalid/STATUS.md", "docs/workstreams/other/STATUS.md"):
            with self.subTest(path=path):
                data = copy.deepcopy(self.data)
                data["workstreams"][0]["status_path"] = path
                self.assertTrue(validate_navigation(self.root, data))

    def test_rejects_missing_status(self) -> None:
        self.status.unlink()
        self.assertTrue(validate_navigation(self.root, self.data))

    def test_rejects_incomplete_status(self) -> None:
        self.status.write_text("# No evidence or boundaries\n", encoding="utf-8")
        self.assertEqual(len(validate_navigation(self.root, self.data)), len(SECTIONS))

    def test_repository_navigation(self) -> None:
        data = json.loads((ROOT / REGISTRY).read_text(encoding="utf-8"))
        self.assertEqual(validate_navigation(ROOT, data), [])
        self.assertEqual({row["id"] for row in data["workstreams"]}, {"core", "arc-agi-2", "line-b"})

    def test_entrypoints_route_to_workstreams(self) -> None:
        for relative in ("README.md", "AGENTS.md", "docs/repository-layout.md",
                         "docs/development/operating-model.md", "tests/README.md"):
            with self.subTest(path=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("workstreams/", text)

    def test_cross_branch_blob_links_are_pinned(self) -> None:
        paths = [ROOT / "AGENTS.md", *sorted((ROOT / "docs/workstreams").rglob("*.md"))]
        count = 0
        pattern = r"https://github\.com/Danwuoo/IRIS-X/blob/([^/)]+)"
        for path in paths:
            for ref in re.findall(pattern, path.read_text(encoding="utf-8")):
                count += 1
                self.assertRegex(ref, r"^[0-9a-f]{40}$")
        self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
