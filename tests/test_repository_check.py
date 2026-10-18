from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "irisx_repository_check", ROOT / "tools/repository_check.py"
)
assert SPEC is not None and SPEC.loader is not None
REPOSITORY_CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPOSITORY_CHECK)


class RepositoryCheckTests(unittest.TestCase):
    def test_active_repository_is_valid(self) -> None:
        self.assertEqual(REPOSITORY_CHECK.validate(ROOT, public=True), [])

    def test_retained_archive_objects_are_valid(self) -> None:
        issues = []
        REPOSITORY_CHECK.validate_archive(ROOT, issues)
        self.assertEqual(issues, [])

    def test_unavailable_archive_ref_does_not_hide_active_or_catalog_checks(self) -> None:
        original_git = REPOSITORY_CHECK.git

        def without_archive(root, *args):
            if any(REPOSITORY_CHECK.ARCHIVE_TAG in arg for arg in args):
                raise RuntimeError("retained archive ref unavailable in this checkout")
            return original_git(root, *args)

        with patch.object(REPOSITORY_CHECK, "git", side_effect=without_archive), \
                patch.object(REPOSITORY_CHECK, "validate_active_surface", wraps=REPOSITORY_CHECK.validate_active_surface) as active, \
                patch.object(REPOSITORY_CHECK, "validate_archive_catalog", wraps=REPOSITORY_CHECK.validate_archive_catalog) as catalog:
            self.assertEqual(REPOSITORY_CHECK.validate(ROOT, public=True), [])
            active.assert_called_once()
            catalog.assert_called_once()
            self.assertIn("retained archive ref unavailable in this checkout", REPOSITORY_CHECK.validate(ROOT))
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(REPOSITORY_CHECK.run_repository_check(ROOT, public=True), 0)
            self.assertIn("tag/tree/blob recovery: UNVERIFIED", output.getvalue())
            self.assertNotIn("representative recovery checks:", output.getvalue())

    def test_public_archive_catalog_missing_or_changed_bytes_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "archive").mkdir()
            for relative in REPOSITORY_CHECK.ARCHIVE_CATALOG_SHA256:
                shutil.copyfile(ROOT / relative, root / relative)
            issues = []
            REPOSITORY_CHECK.validate_archive_catalog(root, issues)
            self.assertEqual(issues, [])
            for relative in REPOSITORY_CHECK.ARCHIVE_CATALOG_SHA256:
                with self.subTest(path=relative):
                    path = root / relative
                    original = path.read_bytes()
                    path.write_bytes(original + b" ")
                    issues = []
                    REPOSITORY_CHECK.validate_archive_catalog(root, issues)
                    self.assertEqual(issues, [f"public archive catalog SHA-256 mismatch: {relative}"])
                    path.unlink()
                    issues = []
                    REPOSITORY_CHECK.validate_archive_catalog(root, issues)
                    self.assertEqual(len(issues), 1)
                    self.assertIn(f"cannot read public archive catalog {relative}", issues[0])
                    path.write_bytes(original)

    def test_all_checks_still_select_strict_repository_validation(self) -> None:
        with patch.object(REPOSITORY_CHECK, "run_self_tests", return_value=0), \
                patch.object(REPOSITORY_CHECK, "run_repository_check", return_value=1) as repository, \
                patch.object(REPOSITORY_CHECK.subprocess, "run") as external, \
                redirect_stdout(io.StringIO()):
            external.return_value.returncode = 0
            self.assertEqual(REPOSITORY_CHECK.run_all_checks(ROOT), 1)
            repository.assert_called_once_with(ROOT)
            self.assertEqual(external.call_args_list[0].args[0][1:],
                             ["-m", "unittest", "discover", "-s", "tests", "-v"])

    def test_policy_set_preserves_product_boundaries(self) -> None:
        paths = (
            "docs/product/product-scope.md",
            "docs/product/non-goals.md",
            "docs/development/operating-model.md",
            "docs/development/data-and-execution-policy.md",
        )
        combined = "\n".join(
            (ROOT / path).read_text(encoding="utf-8") for path in paths
        )
        for term in (
            "Domain Specification",
            "Domain Package",
            "Engineering Trial",
            "remain undecided",
            "owner authorization",
            "P1",
        ):
            self.assertIn(term, combined)

    def test_execution_policy_separates_offline_and_external_work(self) -> None:
        policy = (
            ROOT / "docs/development/data-and-execution-policy.md"
        ).read_text(encoding="utf-8")
        for term in (
            "Never commit API keys",
            "sensitive",
            ".irisx/",
            "provenance",
            "maximum budget",
            "P1 qualification fixture are deterministic and",
            "Any external or paid execution requires explicit owner authorization",
        ):
            self.assertIn(term, policy)

    def test_decision_0004_is_current_authority_without_run_authorization(self) -> None:
        decision = (
            ROOT / "docs/decisions/0004-admit-first-p2-arc-agi-2-engineering-trial.md"
        ).read_text(encoding="utf-8")
        for term in (
            "Status: Accepted",
            "ARC-AGI-2",
            "f3283f727488ad98fe575ea6a5ac981e4a188e49",
            "candidate ARC score - baseline ARC score >= 0.05",
            "separate explicit owner authorization",
        ):
            self.assertIn(term, decision)

    def test_decision_0005_narrowly_binds_kaggle_and_qwen_without_run_authorization(self) -> None:
        decision = (
            ROOT / "docs/decisions/0005-authorize-kaggle-offline-handoff-for-arc-agi-2-trial-001.md"
        ).read_text(encoding="utf-8")
        for term in (
            "Status: Accepted",
            "Qwen/Qwen3.8-27B",
            "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
            "NVIDIA RTX PRO 6000 96 GB",
            "trial-input.zip",
            "result-package.zip",
            "separate explicit owner authorization",
        ):
            self.assertIn(term, decision)

    def test_decision_0006_binds_the_direct_unpacked_model_without_run_authorization(self) -> None:
        decision = (
            ROOT / "docs/decisions/0006-use-unpacked-model-source-for-arc-agi-2-trial-001.md"
        ).read_text(encoding="utf-8")
        for term in (
            "Status: Accepted",
            "unpacked",
            "model_source_provenance_digest",
            "/kaggle/input/datasets/danielwuu/qwen38-27b",
            "does not authorize the real model/solver run",
        ):
            self.assertIn(term, decision)

    def test_decision_0007_binds_the_extracted_trial_tree_without_run_authorization(self) -> None:
        decision = (
            ROOT / "docs/decisions/0007-bind-kaggle-extracted-trial-dataset.md"
        ).read_text(encoding="utf-8")
        for term in (
            "Status: Accepted",
            "/kaggle/input/datasets/danielwuu/trial-input",
            "trial_manifest_digest",
            "version 1",
            "does not authorize the real model/solver run",
        ):
            self.assertIn(term, decision)

    def test_decision_0008_binds_the_offline_qwen35_runtime_without_run_authorization(self) -> None:
        decision = (
            ROOT / "docs/decisions/0008-bind-offline-qwen3-5-transformers-runtime.md"
        ).read_text(encoding="utf-8")
        for term in (
            "Status: Accepted",
            "qwen3_5",
            "Transformers 5.8.1",
            "offline",
            "does not authorize the real model/solver run",
        ):
            self.assertIn(term, decision)

    def test_decision_0009_freezes_run_identity_and_gates_layout_normalization(self) -> None:
        decision = (
            ROOT / "docs/decisions/0009-normalize-arc-agi-2-trial-001-layout.md"
        ).read_text(encoding="utf-8")
        for term in (
            "Status: Accepted",
            "run-001",
            "a179ee8b80b5b7886b756561f74be80d425312faf2d1ecea0b5d81262cef6b44",
            "normalization_ready: true",
            "runs/<run-id>/",
            "does not authorize or ratify",
        ):
            self.assertIn(term, decision)

    def test_decision_0010_uses_risk_based_workflow_without_weakening_run_gate(self) -> None:
        decision = (
            ROOT / "docs/decisions/0010-adopt-lightweight-risk-based-development.md"
        ).read_text(encoding="utf-8")
        for term in (
            "Status: Accepted",
            "Routine lane",
            "Gated lane",
            "One current status source",
            "python tools\\repository_check.py --all",
            "separate explicit owner authorization",
            "run-001",
        ):
            self.assertIn(term, decision)

    def test_decision_0011_creates_checkpointing_run_002_without_execution_authority(self) -> None:
        decision = (
            ROOT / "docs/decisions/0011-create-checkpointing-run-002.md"
        ).read_text(encoding="utf-8")
        for term in (
            "Status: Accepted",
            "run-002",
            "checkpoint-package.zip",
            "progress.jsonl",
            "cumulative wall-clock budget",
            "does not authorize a real",
        ):
            self.assertIn(term, decision)

    def test_decision_0012_closes_trial_without_promoting_missing_results(self) -> None:
        decision = (
            ROOT / "docs/decisions/0012-close-arc-agi-2-trial-001-inconclusive.md"
        ).read_text(encoding="utf-8")
        for term in (
            "Status: Accepted",
            "inconclusive-no-promotion",
            "owner-reported",
            "`run-003/result.zip` was returned to local quarantine",
            "promotion: false",
            "End all remaining Trial 001 model execution authority",
        ):
            self.assertIn(term, decision)

        closure = json.loads(
            (ROOT / "trials/first-real-domain/closure.json").read_text(encoding="utf-8")
        )
        self.assertEqual(closure["disposition"], "inconclusive-no-promotion")
        self.assertFalse(closure["measurement_complete"])
        self.assertFalse(closure["accuracy_computed"])
        self.assertFalse(closure["promotion"])
        self.assertFalse(closure["domain_package_created"])
        self.assertEqual(closure["result_digests"], [])

    def test_decision_0013_creates_exact_four_invocation_completion_benchmark(self) -> None:
        decision = (
            ROOT / "docs/decisions/0013-create-unbounded-four-invocation-run-003.md"
        ).read_text(encoding="utf-8")
        for term in (
            "Status: Accepted",
            "run-003",
            "exactly the first four",
            "max_time",
            "result.zip",
            "provider-controlled session lifetime",
            "does not authorize the remaining 664 invocations",
        ):
            self.assertIn(term, decision)

    def test_trial_001_readme_is_the_current_status_source(self) -> None:
        status = (
            ROOT / "trials/first-real-domain/README.md"
        ).read_text(encoding="utf-8")
        for term in (
            "single current status page",
            "## Goal",
            "## Current state",
            "## Next action",
            "## Fixed boundary",
            "closed-inconclusive",
            "inconclusive-no-promotion",
            "run-002",
            "checkpoint-package.zip",
            "run-003",
            "result.zip",
        ):
            self.assertIn(term, status)

    def test_p0_archive_identities_are_unchanged(self) -> None:
        self.assertEqual(REPOSITORY_CHECK.ARCHIVE_TAG, "archive/pre-product-transition-2026-09-17")
        self.assertEqual(REPOSITORY_CHECK.TAG_OBJECT, "658cdd6ccc33ffd32ced70e0834726c8e30d0a7d")
        self.assertEqual(REPOSITORY_CHECK.SOURCE_COMMIT, "83207e48cc44ce26d0bcb0c98006facfc4f01844")
        self.assertEqual(REPOSITORY_CHECK.ROOT_TREE, "623066ca75243af5e68f53d8674508d4470ce2cd")


if __name__ == "__main__":
    unittest.main()
