#!/usr/bin/env python3
"""Deterministic offline validation for the IRIS-X P0 product transition."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest


ARCHIVE_TAG = "archive/pre-product-transition-2026-09-17"
TAG_OBJECT = "658cdd6ccc33ffd32ced70e0834726c8e30d0a7d"
SOURCE_COMMIT = "83207e48cc44ce26d0bcb0c98006facfc4f01844"
ROOT_TREE = "623066ca75243af5e68f53d8674508d4470ce2cd"
THESIS_SHA256 = "373105e33a500c821ea7ca1f5d45a077ec2d6f381250cf79859cbfa6a83d7a63"

ARCHIVED_ROOTS = (
    "corpus",
    "docs",
    "experiments",
    "irisx",
    "references",
    "research",
    "sources",
    "tools",
)

REQUIRED_PATHS = {
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "PRODUCT_THESIS.md",
    "README.md",
    "archive/AGENTS.md",
    "archive/README.md",
    "archive/manifest.json",
    "archive/path-index.tsv",
    "docs/README.md",
    "docs/decisions/0001-adopt-product-oriented-domain-ai-specialization.md",
    "docs/decisions/README.md",
    "docs/development/README.md",
    "docs/product/README.md",
    "docs/repository-layout.md",
    "research/README.md",
    "src/irisx/README.md",
    "tests/README.md",
    "tests/test_repository_check.py",
    "tools/README.md",
    "tools/repository_check.py",
    "trials/README.md",
}

ALLOWED_EXECUTABLES = {
    "tests/test_repository_check.py",
    "tools/repository_check.py",
}

REPRESENTATIVE_CATEGORIES = {
    "historical documentation",
    "historical research",
    "historical experiment result",
    "imported source snapshot",
    "corpus registry",
    "reference artifact",
    "historical prototype",
    "historical tool",
}

LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
EXECUTABLE_SUFFIXES = {".py", ".ps1", ".sh", ".bat", ".cmd", ".exe"}


def git(root: Path, *args: str) -> bytes:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout


def parse_ls_tree(raw: bytes) -> list[tuple[str, str, str, str]]:
    entries: list[tuple[str, str, str, str]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, path_bytes = record.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split(" ")
        entries.append(
            (mode, object_type, object_id, path_bytes.decode("utf-8"))
        )
    return entries


def render_path_index(entries: list[tuple[str, str, str, str]]) -> bytes:
    lines = ["mode\ttype\tobject_id\toriginal_path"]
    lines.extend("\t".join(entry) for entry in entries)
    return ("\n".join(lines) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tracked_paths(root: Path) -> set[str]:
    raw = git(root, "ls-files", "-z")
    return {
        item.decode("utf-8")
        for item in raw.split(b"\0")
        if item
    }


def add(condition: bool, message: str, issues: list[str]) -> None:
    if not condition:
        issues.append(message)


def validate_active_surface(root: Path, issues: list[str]) -> set[str]:
    tracked = tracked_paths(root)
    add(REQUIRED_PATHS <= tracked, f"missing tracked paths: {sorted(REQUIRED_PATHS - tracked)}", issues)
    add(tracked <= REQUIRED_PATHS, f"unexpected tracked active paths: {sorted(tracked - REQUIRED_PATHS)}", issues)

    for path in REQUIRED_PATHS:
        add((root / path).is_file(), f"required active file missing: {path}", issues)

    thesis = (root / "PRODUCT_THESIS.md").read_bytes()
    add(sha256(thesis) == THESIS_SHA256, "PRODUCT_THESIS.md SHA-256 mismatch", issues)
    staged_thesis = git(root, "show", ":PRODUCT_THESIS.md")
    add(sha256(staged_thesis) == THESIS_SHA256, "tracked PRODUCT_THESIS.md SHA-256 mismatch", issues)

    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    add(".irisx/" in gitignore, ".gitignore does not exclude .irisx outputs", issues)

    required_terms = {
        "README.md": (
            "PRODUCT_THESIS.md",
            "Domain Specification",
            "Build–Measure–Select",
            "Engineering Trials",
            "Domain Package",
        ),
        "docs/decisions/0001-adopt-product-oriented-domain-ai-specialization.md": (
            "Status: Accepted",
            "Domain Specification",
            "Build–Measure–Select",
            "Engineering Trial",
            "Domain Package",
            "first domain",
            "provider or model",
            "backend",
            "budget",
            "deployment form",
            "detailed product architecture",
        ),
    }
    for path, terms in required_terms.items():
        text = (root / path).read_text(encoding="utf-8")
        for term in terms:
            add(term in text, f"{path} is missing required term: {term}", issues)

    stale_claims = (
        "research-reset / direction-selection state",
        "direction-selection state",
        "no active thesis",
        "No replacement thesis",
        "product direction is open",
    )
    for path in ("README.md", "AGENTS.md", "docs/README.md", "docs/repository-layout.md"):
        text = (root / path).read_text(encoding="utf-8")
        for claim in stale_claims:
            add(claim not in text, f"stale authority claim in {path}: {claim}", issues)

    for path in sorted(tracked):
        if Path(path).suffix.lower() in EXECUTABLE_SUFFIXES:
            add(path in ALLOWED_EXECUTABLES, f"unexpected active executable: {path}", issues)

    legacy_import_roots = {"corpus", "experiments", "irisx", "references", "sources"}
    for path in sorted(ALLOWED_EXECUTABLES & tracked):
        source = (root / path).read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            issues.append(f"cannot parse active Python file {path}: {exc}")
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                add(
                    name.split(".", 1)[0] not in legacy_import_roots,
                    f"active Python imports archived module {name!r} in {path}",
                    issues,
                )

    return tracked


def validate_links(root: Path, tracked: set[str], issues: list[str]) -> None:
    for relative in sorted(path for path in tracked if path.endswith(".md")):
        text = (root / relative).read_text(encoding="utf-8")
        for raw_target in LINK_RE.findall(text):
            target = raw_target.strip().split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            target = target.strip("<>")
            resolved = ((root / relative).parent / target).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                issues.append(f"link escapes repository in {relative}: {raw_target}")
                continue
            add(resolved.exists(), f"broken link in {relative}: {raw_target}", issues)


def validate_archive(root: Path, issues: list[str]) -> None:
    try:
        add(git(root, "cat-file", "-t", ARCHIVE_TAG).decode().strip() == "tag", "archive tag is not annotated", issues)
        add(git(root, "rev-parse", ARCHIVE_TAG).decode().strip() == TAG_OBJECT, "archive tag object mismatch", issues)
        add(git(root, "rev-parse", f"{ARCHIVE_TAG}^{{}}").decode().strip() == SOURCE_COMMIT, "archive source commit mismatch", issues)
        add(git(root, "rev-parse", f"{ARCHIVE_TAG}^{{tree}}").decode().strip() == ROOT_TREE, "archive root tree mismatch", issues)
    except RuntimeError as exc:
        issues.append(str(exc))
        return

    manifest_path = root / "archive/manifest.json"
    index_path = root / "archive/path-index.tsv"
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(f"cannot read archive manifest: {exc}")
        return

    expected_json = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    add(manifest_bytes == expected_json, "archive manifest is not deterministic formatted JSON", issues)

    archive = manifest.get("archive", {})
    expected_archive = {
        "name": "pre-product-transition-2026-09-17",
        "tag": ARCHIVE_TAG,
        "tag_kind": "annotated",
        "tag_object": TAG_OBJECT,
        "source_commit": SOURCE_COMMIT,
        "root_tree": ROOT_TREE,
        "payload_location": "Git objects reachable from the annotated tag at original paths",
    }
    add(archive == expected_archive, "archive manifest identity block mismatch", issues)

    entries = parse_ls_tree(git(root, "ls-tree", "-r", "-z", ARCHIVE_TAG))
    expected_index = render_path_index(entries)
    actual_index = index_path.read_bytes()
    add(actual_index == expected_index, "archive path index does not match tagged tree", issues)

    index_record = manifest.get("path_index", {})
    add(index_record.get("path") == "archive/path-index.tsv", "manifest path-index path mismatch", issues)
    add(index_record.get("tracked_path_count") == len(entries), "manifest path count mismatch", issues)
    add(index_record.get("byte_count") == len(actual_index), "manifest path-index byte count mismatch", issues)
    add(index_record.get("sha256") == sha256(actual_index), "manifest path-index SHA-256 mismatch", issues)

    object_by_path = {path: (mode, object_type, object_id) for mode, object_type, object_id, path in entries}
    root_entries = {
        path: (mode, object_type, object_id)
        for mode, object_type, object_id, path in parse_ls_tree(git(root, "ls-tree", "-z", ARCHIVE_TAG))
    }

    roots = manifest.get("archived_roots", [])
    add([item.get("path") for item in roots] == [f"{name}/" for name in ARCHIVED_ROOTS], "archived root list mismatch", issues)
    for item in roots:
        path = item.get("path", "")
        name = path.rstrip("/")
        if name not in ARCHIVED_ROOTS or name not in root_entries:
            issues.append(f"invalid archived root entry: {path}")
            continue
        mode, object_type, object_id = root_entries[name]
        add(item.get("mode") == mode, f"archived root mode mismatch: {path}", issues)
        add(item.get("type") == object_type == "tree", f"archived root type mismatch: {path}", issues)
        add(item.get("object_id") == object_id, f"archived root object mismatch: {path}", issues)
        expected_count = sum(entry_path.startswith(path) for *_, entry_path in entries)
        add(item.get("tracked_path_count") == expected_count, f"archived root count mismatch: {path}", issues)

    for item in manifest.get("archived_root_files", []):
        path = item.get("path", "")
        if path not in object_by_path:
            issues.append(f"archived root file not found in tag: {path}")
            continue
        mode, object_type, object_id = object_by_path[path]
        add((item.get("mode"), item.get("type"), item.get("object_id")) == (mode, object_type, object_id), f"archived root file identity mismatch: {path}", issues)

    representatives = manifest.get("representative_recovery", [])
    add({item.get("category") for item in representatives} == REPRESENTATIVE_CATEGORIES, "representative recovery categories mismatch", issues)
    for item in representatives:
        path = item.get("path", "")
        if path not in object_by_path:
            issues.append(f"representative path not found in tag: {path}")
            continue
        mode, object_type, object_id = object_by_path[path]
        add((item.get("mode"), item.get("type"), item.get("object_id")) == (mode, object_type, object_id), f"representative Git identity mismatch: {path}", issues)
        blob = git(root, "cat-file", "blob", object_id)
        add(item.get("sha256") == sha256(blob), f"representative recovery SHA-256 mismatch: {path}", issues)

    add(len(manifest.get("recovery_commands", [])) == 4, "archive recovery command catalog mismatch", issues)


def validate(root: Path) -> list[str]:
    issues: list[str] = []
    tracked = validate_active_surface(root, issues)
    validate_links(root, tracked, issues)
    validate_archive(root, issues)
    return issues


class HelperTests(unittest.TestCase):
    def test_parse_and_render_path_index(self) -> None:
        raw = (
            b"100644 blob " + b"a" * 40 + b"\tREADME.md\0"
            b"100644 blob " + b"b" * 40 + b"\tdocs/a file.md\0"
        )
        entries = parse_ls_tree(raw)
        self.assertEqual(entries[1][3], "docs/a file.md")
        rendered = render_path_index(entries)
        self.assertTrue(rendered.startswith(b"mode\ttype\tobject_id\toriginal_path\n"))
        self.assertTrue(rendered.endswith(b"\n"))

    def test_sha256(self) -> None:
        self.assertEqual(
            sha256(b"IRIS-X"),
            "7533f77d709d8da95bad4e81ed5cd6133f6191b8b6e56c01104db9da335751db",
        )

    def test_required_roots_are_explicit(self) -> None:
        self.assertEqual(len(ARCHIVED_ROOTS), 8)
        self.assertEqual(len(REPRESENTATIVE_CATEGORIES), 8)


def run_self_tests() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HelperTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run validator helper tests")
    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_tests()

    root = Path(__file__).resolve().parents[1]
    issues = validate(root)
    if issues:
        print("IRIS-X repository check: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1

    manifest = json.loads((root / "archive/manifest.json").read_text(encoding="utf-8"))
    print("IRIS-X repository check: PASS")
    print(f"- thesis SHA-256: {THESIS_SHA256}")
    print(f"- archive tag: {ARCHIVE_TAG}")
    print(f"- source commit: {SOURCE_COMMIT}")
    print(f"- root tree: {ROOT_TREE}")
    print(f"- indexed historical paths: {manifest['path_index']['tracked_path_count']}")
    print(f"- representative recovery checks: {len(manifest['representative_recovery'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
