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
    def test_p0_repository_is_valid(self) -> None:
        self.assertEqual(REPOSITORY_CHECK.validate(ROOT), [])

    def test_policy_set_preserves_p0_boundaries(self) -> None:
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
            "Ordinary P0 validation is deterministic and offline",
            "Any external or paid execution requires explicit owner authorization",
        ):
            self.assertIn(term, policy)


if __name__ == "__main__":
    unittest.main()
