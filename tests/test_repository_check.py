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


if __name__ == "__main__":
    unittest.main()
