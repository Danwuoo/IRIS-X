#!/usr/bin/env python3
"""Deterministic offline validation for the active IRIS-X repository."""

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
    ".github/workflows/ci.yml",
    "AGENTS.md",
    "PRODUCT_THESIS.md",
    "README.md",
    "pyproject.toml",
    "archive/AGENTS.md",
    "archive/README.md",
    "archive/manifest.json",
    "archive/path-index.tsv",
    "docs/README.md",
    "docs/decisions/0001-adopt-product-oriented-domain-ai-specialization.md",
    "docs/decisions/0002-adopt-p1-contract-and-serialization-foundation.md",
    "docs/decisions/0003-record-p2-admission-block.md",
    "docs/decisions/0004-admit-first-p2-arc-agi-2-engineering-trial.md",
    "docs/decisions/0005-authorize-kaggle-offline-handoff-for-arc-agi-2-trial-001.md",
    "docs/decisions/README.md",
    "docs/development/arc-agi-2-kaggle-handoff.md",
    "docs/development/data-and-execution-policy.md",
    "docs/development/operating-model.md",
    "docs/development/README.md",
    "docs/product/non-goals.md",
    "docs/product/p2-admission.md",
    "docs/product/contracts.md",
    "docs/product/domain-package.md",
    "docs/product/product-scope.md",
    "docs/product/README.md",
    "docs/repository-layout.md",
    "research/README.md",
    "src/irisx/__init__.py",
    "src/irisx/__main__.py",
    "src/irisx/admission.py",
    "src/irisx/arc_agi2.py",
    "src/irisx/arc_package.py",
    "src/irisx/artifacts.py",
    "src/irisx/bindings.py",
    "src/irisx/bundle.py",
    "src/irisx/canonical.py",
    "src/irisx/cli.py",
    "src/irisx/contracts.py",
    "src/irisx/engine.py",
    "src/irisx/errors.py",
    "src/irisx/fixture.py",
    "src/irisx/kaggle.py",
    "src/irisx/kaggle_runner.py",
    "src/irisx/package.py",
    "src/irisx/transport.py",
    "tests/README.md",
    "tests/arc_support.py",
    "tests/support.py",
    "tests/test_admission.py",
    "tests/test_arc_agi2.py",
    "tests/test_contracts.py",
    "tests/test_engine.py",
    "tests/test_reference_flow.py",
    "tests/test_repository_check.py",
    "tests/test_kaggle_handoff.py",
    "tests/test_transport.py",
    "tools/README.md",
    "tools/irisx_build_backend.py",
    "tools/repository_check.py",
    "trials/README.md",
    "trials/first-real-domain/README.md",
    "trials/first-real-domain/kaggle-notebook.ipynb",
    "trials/p2-admission/README.md",
    "trials/p2-admission/admission.json",
}

ALLOWED_TOP_LEVEL_FILES = {
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "PRODUCT_THESIS.md",
    "README.md",
    "pyproject.toml",
}
ALLOWED_TOP_LEVEL_DIRECTORIES = {
    ".github",
    "archive",
    "docs",
    "research",
    "src",
    "tests",
    "tools",
    "trials",
}
LEGACY_ROOTS = {"corpus", "experiments", "irisx", "references", "sources"}
FORBIDDEN_RUNTIME_IMPORTS = {
    "aiohttp",
    "anthropic",
    "boto3",
    "google.generativeai",
    "httpx",
    "openai",
    "requests",
    "socket",
    "urllib",
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


def active_paths(root: Path) -> set[str]:
    """Return non-ignored files in the working surface, including new P1 files."""

    raw = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    return {
        item.decode("utf-8")
        for item in raw.split(b"\0")
        if item and (root / item.decode("utf-8")).is_file()
    }


def add(condition: bool, message: str, issues: list[str]) -> None:
    if not condition:
        issues.append(message)


def validate_active_surface(root: Path, issues: list[str]) -> set[str]:
    tracked = active_paths(root)
    add(REQUIRED_PATHS <= tracked, f"missing active paths: {sorted(REQUIRED_PATHS - tracked)}", issues)

    for path in REQUIRED_PATHS:
        add((root / path).is_file(), f"required active file missing: {path}", issues)

    for path in sorted(tracked):
        parts = Path(path).parts
        top = parts[0]
        allowed = path in ALLOWED_TOP_LEVEL_FILES or top in ALLOWED_TOP_LEVEL_DIRECTORIES
        add(allowed, f"unexpected top-level active path: {path}", issues)
        add(top not in LEGACY_ROOTS, f"legacy root returned to active surface: {path}", issues)
        add(top != ".irisx", f"generated local output is active: {path}", issues)
        add("__pycache__" not in parts and not path.endswith((".pyc", ".pyo")), f"generated Python cache is active: {path}", issues)

    thesis = (root / "PRODUCT_THESIS.md").read_bytes()
    add(sha256(thesis) == THESIS_SHA256, "PRODUCT_THESIS.md SHA-256 mismatch", issues)
    staged_thesis = git(root, "show", ":PRODUCT_THESIS.md")
    add(sha256(staged_thesis) == THESIS_SHA256, "tracked PRODUCT_THESIS.md SHA-256 mismatch", issues)

    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    add(".irisx/" in gitignore, ".gitignore does not exclude .irisx outputs", issues)
    add(".env" in gitignore, ".gitignore does not exclude local environment files", issues)

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
        "docs/product/product-scope.md": (
            "Domain Specification",
            "Domain Package",
            "Build–Measure–Select",
            "Engineering Trial",
            "P1",
        ),
        "docs/product/non-goals.md": (
            "general-purpose agent framework",
            "fine-tuning",
            "benchmark leaderboard",
            "framework aggregation",
            "P1 does not select a real domain",
        ),
        "docs/development/operating-model.md": (
            "Product engineering is the default",
            "Build–Measure–Select",
            "Engineering Trial",
            "owner-authorized scope",
            "Research is conditional",
            "P1",
        ),
        "docs/development/data-and-execution-policy.md": (
            "Secrets and credentials",
            "sensitive data",
            ".irisx/",
            "retention",
            "provenance",
            "provider/model",
            "maximum budget",
            "offline",
            "external or paid execution",
        ),
        "docs/product/contracts.md": (
            "Measurement units",
            "critical_failure",
            "segment accuracy",
            "relative POSIX logical paths",
            "cases.json/<case-id>/<input|expected>",
            "accuracy.<segment>",
        ),
        "docs/product/domain-package.md": (
            "baseline_result_ref",
            "considered_result_refs",
            "eligible_result_refs",
            "recomputes",
            "symbolic links",
            "matching a value digest alone is insufficient",
        ),
        "docs/decisions/0003-record-p2-admission-block.md": (
            "admission-blocked",
            "mutually exclusive",
            "admitted or executed",
            "No network/provider/paid/sensitive-data execution",
        ),
        "docs/decisions/0004-admit-first-p2-arc-agi-2-engineering-trial.md": (
            "Status: Accepted",
            "ARC-AGI-2",
            "arcprize/ARC-AGI-2",
            "f3283f727488ad98fe575ea6a5ac981e4a188e49",
            "official public training split",
            "official public evaluation split",
            "third-party ARC data",
            "USD 0",
            "candidate ARC score - baseline ARC score >= 0.05",
            "separate explicit owner authorization",
        ),
        "docs/decisions/0005-authorize-kaggle-offline-handoff-for-arc-agi-2-trial-001.md": (
            "Status: Accepted",
            "Qwen/Qwen3.8-27B",
            "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
            "NVIDIA RTX PRO 6000 96 GB",
            "trial-input.zip",
            "result-package.zip",
            "network-disabled",
            "separate explicit owner authorization",
        ),
        "docs/development/arc-agi-2-kaggle-handoff.md": (
            "manual",
            "private",
            "Evaluator truth",
            "quarantine",
            "run_authorized: false",
            "local scoring",
        ),
        "docs/product/p2-admission.md": (
            "admission_blocked",
            "Unknown",
            "Synthetic fixtures",
            "promotion",
        ),
        "trials/p2-admission/README.md": (
            "admission-blocked",
            "One owner choice",
            "Acceptance and falsification",
            "synthetic evidence presented as real",
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

    current_authority_terms = {
        "AGENTS.md": (
            "Decision 0004",
            "Decision 0005",
            "ARC-AGI-2",
            "Qwen/Qwen3.8-27B",
            "separate explicit owner authorization",
            "historical blocked-state evidence",
        ),
        "README.md": (
            "Decision 0004",
            "Decision 0005",
            "ARC-AGI-2",
            "separate explicit owner authorization",
        ),
        "docs/repository-layout.md": (
            "Decision 0004",
            "Decision 0005",
            "ARC-AGI-2",
            "real run requires a separate explicit owner authorization",
        ),
    }
    for path, terms in current_authority_terms.items():
        text = (root / path).read_text(encoding="utf-8")
        for term in terms:
            add(term in text, f"{path} is missing current authority term: {term}", issues)

    for path in sorted(tracked):
        if Path(path).suffix.lower() in EXECUTABLE_SUFFIXES:
            allowed_prefix = path.startswith(("src/irisx/", "tests/", "tools/"))
            add(allowed_prefix, f"unexpected active executable: {path}", issues)

    python_paths = {path for path in tracked if path.endswith(".py")}
    for path in sorted(python_paths):
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
                    name.split(".", 1)[0] not in {"corpus", "experiments", "references", "sources"},
                    f"active Python imports archived module {name!r} in {path}",
                    issues,
                )
                if path.startswith("src/irisx/"):
                    add(
                        not any(name == forbidden or name.startswith(forbidden + ".") for forbidden in FORBIDDEN_RUNTIME_IMPORTS),
                        f"P1 runtime imports provider/network integration {name!r} in {path}",
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
    try:
        sys.path.insert(0, str(root / "src"))
        from irisx.admission import validate_admission_file

        validate_admission_file(root / "trials/p2-admission/admission.json", root)
    except Exception as exc:  # validator must report rather than crash on admission corruption
        issues.append(f"P2 admission package validation failed: {exc}")
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
