from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "irisx_repository_check", ROOT / "tools/repository_check.py"
)
assert SPEC is not None and SPEC.loader is not None
REPOSITORY_CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPOSITORY_CHECK)


class RepositoryCheckTests(unittest.TestCase):
    def test_active_repository_is_valid(self) -> None:
        self.assertEqual(REPOSITORY_CHECK.validate(ROOT), [])

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

    def test_p0_archive_identities_are_unchanged(self) -> None:
        self.assertEqual(REPOSITORY_CHECK.ARCHIVE_TAG, "archive/pre-product-transition-2026-09-17")
        self.assertEqual(REPOSITORY_CHECK.TAG_OBJECT, "658cdd6ccc33ffd32ced70e0834726c8e30d0a7d")
        self.assertEqual(REPOSITORY_CHECK.SOURCE_COMMIT, "83207e48cc44ce26d0bcb0c98006facfc4f01844")
        self.assertEqual(REPOSITORY_CHECK.ROOT_TREE, "623066ca75243af5e68f53d8674508d4470ce2cd")


if __name__ == "__main__":
    unittest.main()
