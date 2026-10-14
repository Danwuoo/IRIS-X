"""Select from a static inventory before importing tests; report every outcome."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest

try:
    from .workstream_management import load_json, safe_path
except ImportError:
    from workstream_management import load_json, safe_path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {"path", "workstream", "dependency_class", "suite", "role", "dependencies", "collector", "reason", "expected_skips"}
CLASSES = {"stdlib", "small-python", "historical", "operational", "native", "unclassified-public"}
PROTECTED = {"historical", "operational", "native"}


def validate_inventory(root: Path, data=None) -> list[str]:
    errors = []
    try:
        data = data if data is not None else load_json(safe_path(root, "tests/inventory.json"))
        if set(data) != {"format", "suites", "entries"} or data["format"] != "irisx.tests.v1":
            raise ValueError("unknown fields or invalid inventory format")
        if not isinstance(data["suites"], dict) or not data["suites"]:
            raise ValueError("empty suite catalog")
        for suite, options in data["suites"].items():
            if not isinstance(suite, str) or not suite or set(options) != {"public"} or type(options["public"]) is not bool:
                raise ValueError("invalid suite definition")
        paths = set()
        for entry in data["entries"]:
            if set(entry) != FIELDS:
                raise ValueError("unknown or missing inventory entry fields; commands forbidden")
            path = safe_path(root, entry["path"])
            if not entry["path"].startswith(("tests/", "tools/")):
                errors.append(f"path outside managed test roots: {entry['path']}")
            if path.suffix != ".py" or not path.is_file():
                errors.append(f"missing Python path: {entry['path']}")
            if entry["path"].casefold() in paths:
                errors.append(f"duplicate classification: {entry['path']}")
            paths.add(entry["path"].casefold())
            if entry["suite"] not in data["suites"]:
                errors.append(f"unknown suite: {entry['suite']}")
            if entry["dependency_class"] not in CLASSES:
                errors.append(f"invalid dependency class: {entry['path']}")
            if entry["workstream"] not in {"core", "arc-agi-2", "line-b"} or entry["role"] not in {"test", "helper", "script"}:
                errors.append(f"invalid role/workstream: {entry['path']}")
            if entry["collector"] not in {"unittest", "helper", "blocked-script"} or ((entry["role"] == "test") != (entry["collector"] == "unittest")):
                errors.append(f"invalid collector: {entry['path']}")
            if not isinstance(entry["reason"], str) or not entry["reason"].strip() or not isinstance(entry["dependencies"], list) or not all(isinstance(x, str) for x in entry["dependencies"]):
                errors.append(f"invalid dependency/reason metadata: {entry['path']}")
            if not isinstance(entry["expected_skips"], list):
                raise ValueError("invalid expected skip list")
            for skip in entry["expected_skips"]:
                if set(skip) != {"test_id", "reason_contains", "platforms"} or not isinstance(skip["test_id"], str) or not skip["test_id"].strip() or not isinstance(skip["reason_contains"], str) or not skip["reason_contains"].strip() or not isinstance(skip["platforms"], list) or not skip["platforms"] or any(p not in {"win32", "linux", "darwin"} for p in skip["platforms"]):
                    raise ValueError("expected skips require exact ID, reason and platform")
        # Inventory completeness is checked without importing any test modules.
        required = {p.relative_to(root).as_posix().casefold() for p in (root / "tests").rglob("*.py")}
        required.update(p.relative_to(root).as_posix().casefold() for p in (root / "tools").rglob("test_*.py"))
        for missing in sorted(required - paths):
            errors.append(f"unregistered inventory coverage: {missing}")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        errors.append(str(exc))
    return errors


def select_suite(root: Path, suite: str, data=None) -> list[dict]:
    data = data if data is not None else load_json(safe_path(root, "tests/inventory.json"))
    errors = validate_inventory(root, data)
    if errors:
        raise ValueError("; ".join(errors))
    if suite not in data["suites"]:
        raise ValueError(f"unknown suite: {suite}")
    selected = [entry for entry in data["entries"] if entry["suite"] == suite and entry["role"] != "helper"]
    if not selected:
        raise ValueError(f"empty suite: {suite}")
    return selected


def _empty(suite: str) -> dict:
    return {"format": "irisx.suite-report.v1", "suite": suite, "status": "failed", "tests": 0, "failures": 0, "errors": 0, "skips": 0, "expected_skips": 0, "unexpected_skips": 0, "blocked": 0, "exit_code": 1, "modules": []}


def _child(root: Path, suite: str, path: str, report_path: Path) -> int:
    selected = select_suite(root, suite)
    entry = next((e for e in selected if e["path"] == path), None)
    if entry is None or entry["dependency_class"] in PROTECTED or entry["collector"] != "unittest":
        raise ValueError("protected/unselected module cannot be imported")
    report = _empty(suite)
    report.update(path=path, collection_errors=0, collection_messages=[])
    file = safe_path(root, path)
    sys.path[:0] = [str(file.parent), str(root / "tests"), str(root / "src"), str(root)]
    try:
        spec = importlib.util.spec_from_file_location(file.stem, file)
        if spec is None or spec.loader is None:
            raise ValueError("missing module spec")
        module = importlib.util.module_from_spec(spec)
        sys.modules[file.stem] = module
        spec.loader.exec_module(module)
        loader = unittest.TestLoader()
        tests = loader.loadTestsFromModule(module)
        result = unittest.TextTestRunner(verbosity=2).run(tests)
        report.update(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), skips=len(result.skipped), collection_errors=len(loader.errors), collection_messages=loader.errors)
        skip_records = []
        for test, reason in result.skipped:
            allowed = any(s["test_id"] == test.id() and s["reason_contains"] in reason and sys.platform in s["platforms"] for s in entry["expected_skips"])
            report["expected_skips" if allowed else "unexpected_skips"] += 1
            skip_records.append({"test_id": test.id(), "reason": reason, "expected": allowed})
        report["skip_records"] = skip_records
        report["failure_ids"] = [t.id() for t, _ in result.failures]
        report["error_ids"] = [t.id() for t, _ in result.errors]
        passed = result.wasSuccessful() and result.testsRun > 0 and not loader.errors and not report["unexpected_skips"]
        report.update(status="passed" if passed else "failed", exit_code=0 if passed else 1)
    except Exception as exc:
        report.update(errors=1, collection_errors=1, collection_messages=[f"{type(exc).__name__}: {exc}"])
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report["exit_code"]


def run_suite(root: Path, suite: str, output: Path) -> dict:
    root = root.resolve()
    relative = output.absolute().relative_to(root).as_posix()
    output = safe_path(root, relative)
    if not relative.startswith(".irisx/") or output.exists():
        raise ValueError("report output must be a new ignored .irisx directory")
    output.mkdir(parents=True)
    report = _empty(suite)
    report.update(python=sys.version, platform=platform.platform(), cwd=str(root), commands=[], target_commit=None)
    if (root / ".git").exists():
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
        if not result.returncode:
            report["target_commit"] = result.stdout.strip()
    try:
        selected = select_suite(root, suite)
        report["selected_paths"] = [e["path"] for e in selected]
        if any(e["dependency_class"] in PROTECTED or e["collector"] != "unittest" for e in selected):
            report.update(status="blocked", blocked=len(selected), exit_code=2, reason="requires authentic inputs, native training scope, or reviewed standalone script; no module imported")
        else:
            env = os.environ.copy()
            env.update({"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TMPDIR": str(output), "TMP": str(output), "TEMP": str(output)})
            for number, entry in enumerate(selected):
                child_path = output / f"module-{number:03d}.json"
                command = [sys.executable, *( ["-O"] if sys.flags.optimize else []), "-B", str(Path(__file__).resolve()), "--root", str(root), "--suite", suite, "--child", entry["path"], "--child-report", str(child_path)]
                report["commands"].append(command)
                try:
                    completed = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
                    (output / f"module-{number:03d}.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
                    if child_path.is_file():
                        child = load_json(child_path)
                        if (child.get("format") != "irisx.suite-report.v1" or child.get("suite") != suite or child.get("path") != entry["path"] or any(type(child.get(k)) is not int or child[k] < 0 for k in ("tests", "failures", "errors", "skips", "expected_skips", "unexpected_skips", "blocked", "exit_code")) or child["skips"] != child["expected_skips"] + child["unexpected_skips"]):
                            child = _empty(suite)
                            child.update(path=entry["path"], errors=1, collection_errors=1, collection_messages=["invalid child report identity/counts"])
                    else:
                        child = _empty(suite)
                        child.update(path=entry["path"], errors=1, collection_errors=1, collection_messages=["missing child report"])
                    if completed.returncode != child["exit_code"]:
                        child.update(status="failed", errors=child["errors"] + 1, exit_code=1)
                except subprocess.TimeoutExpired:
                    child = _empty(suite)
                    child.update(path=entry["path"], status="timeout", errors=1, collection_errors=1, collection_messages=["controlled child timeout"])
                report["modules"].append(child)
                for field in ("tests", "failures", "errors", "skips", "expected_skips", "unexpected_skips", "blocked"):
                    report[field] += child[field]
            passed = report["tests"] > 0 and all(m["status"] == "passed" for m in report["modules"])
            report.update(status="passed" if passed else "failed", exit_code=0 if passed else 1)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        report.update(errors=1, reason=str(exc))
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def validate_gate(reports: dict, expected_suites: list[str]) -> list[str]:
    errors = []
    if not expected_suites:
        errors.append("empty gate selection")
    for suite in expected_suites:
        report = reports.get(suite)
        if not isinstance(report, dict):
            errors.append(f"missing report: {suite}")
            continue
        if report.get("status") != "passed" or report.get("exit_code") != 0 or type(report.get("tests")) is not int or report["tests"] <= 0:
            errors.append(f"non-success/empty/cancelled report: {suite}")
        for field in ("failures", "errors", "unexpected_skips", "blocked", "exit_code"):
            if type(report.get(field)) is not int or report[field] != 0:
                errors.append(f"invalid {field} count: {suite}")
        for field in ("skips", "expected_skips"):
            if type(report.get(field)) is not int or report[field] < 0:
                errors.append(f"invalid {field} count: {suite}")
        if report.get("skips") != report.get("expected_skips", 0):
            errors.append(f"unexpected skip count: {suite}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", help=argparse.SUPPRESS)
    parser.add_argument("--child-report", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child:
        report_path = safe_path(args.root, args.child_report.absolute().relative_to(args.root).as_posix())
        if not report_path.is_relative_to(args.root / ".irisx") or report_path.exists():
            raise ValueError("child report must be new and ignored")
        return _child(args.root, args.suite, args.child, report_path)
    if args.output is None:
        parser.error("--output required")
    report = run_suite(args.root, args.suite, args.output.absolute())
    print(json.dumps({k: v for k, v in report.items() if k not in {"commands", "modules"}}, indent=2))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
