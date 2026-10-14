"""Static dependency direction checks on fresh synthetic source packages."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import dependency_check as checker


class DomainDependencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="irisx-dependencies-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repository"
        self.root.mkdir()
        self.config = {
            "format": "irisx.dependencies.v1",
            "core_modules": ["irisx.core", "irisx.engine"],
            "router": {"irisx.cli": ["irisx.domains.arc_agi_2.cli"]},
            "facade_legacy": {"irisx.domains.arc_agi_2.cli": ["irisx.arc_legacy"]},
        }
        for module in ("irisx", "irisx.domains", "irisx.domains.arc_agi_2", "irisx.domains.line_b"):
            self.write_module(module, "", package=True)
        self.write_module("irisx.core", "import irisx.engine\n")
        self.write_module("irisx.engine", "VALUE = 'shared synthetic core'\n")
        self.write_module("irisx.cli", "import irisx.domains.arc_agi_2.cli\n")
        self.write_module("irisx.domains.arc_agi_2.cli", "import irisx.core\nimport irisx.arc_legacy\n")
        self.write_module("irisx.domains.line_b.flow", "import irisx.engine\n")
        self.write_module("irisx.arc_legacy", "VALUE = 'retained synthetic legacy'\n")
        self.flush()

    def write_module(self, module: str, source: str, *, package: bool = False) -> None:
        path = self.root / "src" / Path(*module.split("."))
        path = path / "__init__.py" if package else path.with_suffix(".py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    def flush(self) -> None:
        path = self.root / "docs/workstreams/dependencies.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.config, indent=2) + "\n", encoding="utf-8")

    def assert_rejected(self, *fragments: str) -> None:
        self.flush()
        errors = checker.check_dependencies(self.root)
        self.assertTrue(errors, "forbidden synthetic dependency was accepted")
        combined = "\n".join(errors).lower()
        self.assertTrue(any(part.lower() in combined for part in fragments), combined)

    def test_allowed_core_domain_and_explicit_facade_edges(self) -> None:
        self.assertEqual(checker.check_dependencies(self.root), [])

    def test_core_cannot_import_domain_implementation(self) -> None:
        self.write_module("irisx.core", "from irisx.domains.line_b import flow\n")
        self.assert_rejected("core", "domain", "forbidden")

    def test_neutral_domains_namespace_cannot_eagerly_import_a_domain(self) -> None:
        for domain in ("arc_agi_2.cli", "line_b.flow"):
            with self.subTest(domain=domain):
                self.write_module("irisx.domains", "import irisx.domains." + domain + "\n", package=True)
                self.assert_rejected("core", "domain", "forbidden")

    def test_core_cannot_import_flat_arc_legacy(self) -> None:
        self.write_module("irisx.engine", "import irisx.arc_legacy\n")
        self.assert_rejected("core", "legacy", "forbidden")

    def test_parent_core_namespace_is_not_blanket_permission_for_legacy(self) -> None:
        self.config["core_modules"].append("irisx")
        self.write_module("irisx.engine", "import irisx.arc_legacy\n")
        self.assert_rejected("core", "legacy", "forbidden")

    def test_line_b_cannot_import_arc_facade(self) -> None:
        self.write_module("irisx.domains.line_b.flow", "from irisx.domains.arc_agi_2 import cli\n")
        self.assert_rejected("cross", "line", "arc")

    def test_arc_cannot_import_line_b(self) -> None:
        self.write_module("irisx.domains.arc_agi_2.cli", "import irisx.domains.line_b.flow\n")
        self.assert_rejected("cross", "line")

    def test_relative_cross_line_imports_are_rejected(self) -> None:
        self.write_module("irisx.domains.line_b.flow", "from ..arc_agi_2 import cli\n")
        self.assert_rejected("cross", "line", "arc")
        self.write_module("irisx.domains.line_b.flow", "import irisx.engine\n")
        self.write_module("irisx.domains.arc_agi_2.cli", "from ..line_b import flow\n")
        self.assert_rejected("cross", "line")

    def test_facade_cannot_call_unregistered_legacy_module(self) -> None:
        self.write_module("irisx.arc_other", "VALUE = 'another synthetic legacy'\n")
        self.write_module("irisx.domains.arc_agi_2.cli", "import irisx.arc_other\n")
        self.assert_rejected("legacy", "unregistered", "forbidden")

    def test_legacy_exception_is_bound_to_the_named_facade(self) -> None:
        self.write_module("irisx.domains.arc_agi_2.helper", "import irisx.arc_legacy\n")
        self.assert_rejected("legacy", "unregistered", "forbidden")

    def test_core_literal_dunder_import_of_domain_is_rejected(self) -> None:
        self.write_module("irisx.core", "__import__('irisx.domains.arc_agi_2.cli')\n")
        self.assert_rejected("core", "domain", "forbidden")

    def test_line_b_literal_importlib_cross_line_is_rejected(self) -> None:
        self.write_module("irisx.domains.line_b.flow",
                          "import importlib\nimportlib.import_module('irisx.domains.arc_agi_2.cli')\n")
        self.assert_rejected("cross", "line", "arc")

    def test_literal_dynamic_import_alias_preserves_direction_checks(self) -> None:
        self.write_module("irisx.domains.line_b.flow",
                          "from importlib import import_module as load\nload('irisx.domains.arc_agi_2.cli')\n")
        self.assert_rejected("cross", "line", "arc")

    def test_unresolved_dynamic_import_is_rejected(self) -> None:
        for source in ("import importlib\nimportlib.import_module(target)\n", "__import__(target)\n"):
            with self.subTest(source=source):
                self.write_module("irisx.core", source)
                self.assert_rejected("dynamic", "unresolved")

    def test_router_literal_is_allowed_only_for_its_registered_destination(self) -> None:
        self.write_module("irisx.cli",
                          "import importlib\nimportlib.import_module('irisx.domains.arc_agi_2.cli')\n")
        self.assertEqual(checker.check_dependencies(self.root), [])
        self.write_module("irisx.cli",
                          "import importlib\nimportlib.import_module('irisx.domains.line_b.flow')\n")
        self.assert_rejected("router", "unregistered", "forbidden")

    def test_invalid_schema_and_missing_core_source_are_rejected(self) -> None:
        self.config["execute"] = "not an executable registry"
        self.assert_rejected("schema", "field", "format")
        del self.config["execute"]
        self.config["core_modules"].append("irisx.missing_core")
        self.assert_rejected("missing", "source", "module")

    def test_source_syntax_errors_are_visible(self) -> None:
        self.write_module("irisx.core", "def broken(\n")
        self.assert_rejected("syntax", "parse", "source")

    def test_check_is_read_only_and_never_imports_source(self) -> None:
        self.write_module("irisx.engine", "raise RuntimeError('STATIC_CHECK_MUST_NOT_IMPORT')\n")
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(checker.check_dependencies(self.root), [])
        after = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
