from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import collect_pressure_batch as collector  # noqa: E402
import pressure_tasks as tasks  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.write_bytes(tasks.pretty_json_bytes(value))


def make_task_dir(root: Path, *, systemic_missing: bool, raw: bytes | None = None) -> Path:
    key = "p1-selection"
    task = tasks.load_task(key)
    task_dir = root / key
    task_dir.mkdir()
    raw_path = task_dir / "raw-output.txt"
    if raw is not None:
        raw_path.write_bytes(raw)
    reasons = ["provider_process_failed", "provider_output_missing"] if systemic_missing else []
    terminal = {
        "schema_version": 2,
        "task_key": key,
        "task_id": task.contract["task_id"],
        "terminal_status": "systemic_failure" if systemic_missing else "verified_success",
        "systemic_failure_reasons": reasons,
        "usable_model_result": not systemic_missing,
        "usable_result_observed": not systemic_missing,
    }
    fixtures = {
        "attempt-start.json": {"task_key": key},
        "provider-events.jsonl": None,
        "provider-stderr.txt": None,
        "resource-record.json": {"model_call_boundaries": 1},
        "verification-record.json": {"semantic_valid": not systemic_missing},
        "terminal-record.json": terminal,
        "predicate-source-map.json": {"authoritative_source": "terminal-record.json"},
    }
    for name, value in fixtures.items():
        path = task_dir / name
        if value is None:
            path.write_bytes((name + "\n").encode("utf-8"))
        else:
            write_json(path, value)
    artifacts = []
    for path in sorted(task_dir.iterdir()):
        if path.is_file():
            content = path.read_bytes()
            artifacts.append({"path": path.name, "bytes": len(content), "sha256": tasks.sha256_bytes(content)})
    write_json(task_dir / "run-manifest.json", {
        "task_id": task.contract["task_id"],
        "definition_code_freeze_sha": "f" * 40,
        "launch_ready_sha": "a" * 40,
        "admission_record_sha256": "b" * 64,
        "artifacts": artifacts,
    })
    return task_dir


def make_launch(root: Path, *, stopped: bool = True) -> Path:
    attempted = [{"task_key": "p1-selection", "terminal_status": "systemic_failure" if stopped else "verified_success"}]
    completion = {
        "batch_id": collector.EXPECTED_BATCH_ID,
        "definition_code_freeze_sha": "f" * 40,
        "launch_ready_sha": "a" * 40,
        "attempted": attempted,
        "stopped_on_systemic_or_safety_failure": stopped,
    }
    write_json(root / "batch-completion.json", completion)
    launch = {
        "batch_id": collector.EXPECTED_BATCH_ID,
        "definition_code_freeze_sha": "f" * 40,
        "launch_ready_sha": "a" * 40,
        "external_staging": {"staging_root": str(root)},
        "admission": {"record_sha256": "b" * 64},
        "repository_run_path": "experiments/phase-6-pressure-sampling-v0/runs/batch-3",
    }
    launch_path = root / "launch-manifest.json"
    write_json(launch_path, launch)
    return launch_path


class CollectionContractTests(unittest.TestCase):
    def test_systemic_no_output_is_collected_without_fabrication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = make_task_dir(root, systemic_missing=True)
            launch = make_launch(root)
            destination = root / "collected"
            result = collector.collect(launch, destination=destination)
            self.assertTrue(result["task_validation"][0]["systemic_output_absence_valid"])
            self.assertFalse((destination / "p1-selection/raw-output.txt").exists())
            for path in source.iterdir():
                if path.is_file():
                    self.assertEqual(path.read_bytes(), (destination / "p1-selection" / path.name).read_bytes())

    def test_declared_missing_output_with_raw_file_is_contradictory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = make_task_dir(root, systemic_missing=True)
            (task_dir / "raw-output.txt").write_bytes(b"{}\n")
            with self.assertRaisesRegex(collector.CollectionError, "raw output exists but is declared missing"):
                collector.validate_task_artifacts("p1-selection", task_dir)

    def test_absent_output_without_missing_reason_is_contradictory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = make_task_dir(root, systemic_missing=True)
            terminal_path = task_dir / "terminal-record.json"
            terminal = tasks.load_object(terminal_path)
            terminal["systemic_failure_reasons"] = ["provider_process_failed"]
            write_json(terminal_path, terminal)
            with self.assertRaisesRegex(collector.CollectionError, "absent without missing-output reason"):
                collector.validate_task_artifacts("p1-selection", task_dir)

    def test_non_systemic_result_requires_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = make_task_dir(root, systemic_missing=False, raw=None)
            with self.assertRaisesRegex(collector.CollectionError, "non-systemic task raw output missing"):
                collector.validate_task_artifacts("p1-selection", task_dir)


if __name__ == "__main__":
    unittest.main()
