from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.docs.system import DocumentSystemError, load_yaml, validate_repository, write_index


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class DocumentationSystemTests(unittest.TestCase):
    def _copy_system(self, destination: Path) -> None:
        shutil.copy2(REPOSITORY_ROOT / "eidos.yaml", destination / "eidos.yaml")
        shutil.copytree(REPOSITORY_ROOT / "docs" / "schema", destination / "docs" / "schema")
        (destination / "docs" / "records").mkdir(parents=True)
        shutil.copy2(REPOSITORY_ROOT / "docs" / "index.json", destination / "docs" / "index.json")

    def test_repository_is_valid(self) -> None:
        self.assertEqual([], validate_repository(REPOSITORY_ROOT))

    def test_duplicate_yaml_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.yaml"
            path.write_text("value: 1\nvalue: 2\n", encoding="utf-8")
            with self.assertRaisesRegex(DocumentSystemError, "duplicate YAML key"):
                load_yaml(path)

    def test_generated_index_supports_a_governed_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_system(root)
            record = root / "docs" / "records" / "PRJ-0001.yaml"
            record.write_text(
                """schema_version: 1
id: PRJ-0001
kind: project
status: draft
title: Temporary test record
language: en
authority: non_normative
summary: Used only inside the validator test fixture.
relations:
  depends_on: []
  supersedes: []
  informed_by: []
content:
  purpose: Exercise index generation.
provenance:
  created_on: '2026-08-14'
  sources: []
""",
                encoding="utf-8",
            )
            write_index(root)
            self.assertEqual([], validate_repository(root))
            index = json.loads((root / "docs" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual("PRJ-0001", index["documents"][0]["id"])

    def test_stale_index_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_system(root)
            index_path = root / "docs" / "index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["documents"] = [
                {
                    "id": "NOTE-0001",
                    "kind": "note",
                    "status": "archived",
                    "title": "Stale entry",
                    "language": "en",
                    "authority": "non_normative",
                    "summary": "This record does not exist.",
                    "path": "docs/records/NOTE-0001.yaml",
                    "relations": {"depends_on": [], "supersedes": [], "informed_by": []},
                }
            ]
            index_path.write_text(json.dumps(index), encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("is stale" in error for error in errors), errors)

    def test_invalid_document_schema_is_rejected_without_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_system(root)
            schema_path = root / "docs" / "schema" / "document.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["type"] = "not-a-json-schema-type"
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            errors = validate_repository(root)
            self.assertTrue(any("invalid JSON Schema" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
