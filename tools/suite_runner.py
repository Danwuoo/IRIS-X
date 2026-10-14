"""Select from a static inventory before importing tests; report every outcome."""
from __future__ import annotations
import argparse
import importlib
import importlib.util
import json
import keyword
import os
from pathlib import Path
import platform
import subprocess
import sys
import types
import unittest

# -P children omit the caller's script directory and inherit no Python settings.
# Bootstrap only this controlled tools directory, then declared per-file roots.
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from .workstream_management import load_json, safe_path
except ImportError:
    from workstream_management import load_json, safe_path

try:
    from .source_identity import create_snapshot, inspect_source, verify_binding
except ImportError:
    from source_identity import create_snapshot, inspect_source, verify_binding

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {"path", "workstream", "dependency_class", "suite", "role", "dependencies", "collector", "reason", "expected_skips"}
OPTIONAL_FIELDS = {"import_roots", "module_name"}
CLASSES = {"stdlib", "small-python", "historical", "operational", "native", "training", "unclassified-public"}
PROTECTED = {"historical", "operational", "native", "training"}
PYTHON_ENVIRONMENT = {"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}


def controlled_python_environment(inherited=None) -> dict:
    """Remove inherited Python configuration before interpreter initialization.

    -I/-E ignore PYTHONHASHSEED too, so callers use -P/-s/-B with this explicit
    allowlist. Non-Python settings, including offline restrictions, are retained.
    Reports record this allowlist only, never the rest of the inherited values.
    """
    inherited = os.environ if inherited is None else inherited
    environment = {name: value for name, value in inherited.items()
                   if not name.upper().startswith("PYTHON")}
    environment.update(PYTHON_ENVIRONMENT)
    return environment


def controlled_python_command(executable, *arguments, optimize=None) -> list[str]:
    """Launch a safe-path, no-user-site child whose fixed hash seed is honored."""
    optimize = sys.flags.optimize if optimize is None else optimize
    if type(optimize) is not int or optimize not in (0, 1, 2):
        raise ValueError("optimization must be 0, 1 or 2")
    if any(argument in {"-I", "-E"} for argument in arguments):
        raise ValueError("isolated/ignore-environment flags would disable the fixed seed")
    return [str(executable), "-P", "-s", "-B", *(["-" + "O" * optimize] if optimize else []),
            *(str(argument) for argument in arguments)]


def interpreter_startup() -> dict:
    """Expose actual startup controls and only the explicit Python allowlist."""
    return {"flags": {name: getattr(sys.flags, name) for name in
                      ("optimize", "safe_path", "no_user_site", "dont_write_bytecode",
                       "ignore_environment", "isolated", "hash_randomization")},
            "python_environment": {name: os.environ.get(name) for name in PYTHON_ENVIRONMENT}}


def validate_child_startup(startup, optimize=None) -> list[str]:
    """Fail closed when the seed or isolation was not effective at child startup."""
    optimize = sys.flags.optimize if optimize is None else optimize
    expected = {"flags": {"optimize": optimize, "safe_path": True, "no_user_site": 1,
                          "dont_write_bytecode": 1, "ignore_environment": 0, "isolated": 0,
                          "hash_randomization": 0},
                "python_environment": PYTHON_ENVIRONMENT}
    return [] if startup == expected else ["child interpreter startup controls do not match the fixed-seed isolation policy"]


def validate_entry_imports(root: Path, entry: dict) -> None:
    """Admit only roots owned by this single test snapshot, never a global pool."""
    roots = entry.get("import_roots", [])
    if not isinstance(roots, list) or ("import_roots" in entry and not roots) or any(not isinstance(name, str) for name in roots):
        raise ValueError("import_roots must be a nonempty repository-relative list")
    owner = entry["path"].split("/")[:2]
    seen = set()
    resolved = []
    for name in roots:
        path = safe_path(root, name)
        if name.split("/")[:2] != owner or len(name.split("/")) < 2 or not path.is_dir():
            raise ValueError("import root must belong to the selected snapshot")
        if name.casefold() in seen or any(path.is_relative_to(other) or other.is_relative_to(path) for other in resolved):
            raise ValueError("import root collision/overlap")
        seen.add(name.casefold())
        resolved.append(path)
    module = entry.get("module_name")
    if "module_name" in entry:
        if not isinstance(module, str) or not module or any(not part.isidentifier() or keyword.iskeyword(part) for part in module.split(".")):
            raise ValueError("module_name must be a valid dotted package name")
        file = safe_path(root, entry["path"])
        if not roots or not any(file.is_relative_to(path) and file.relative_to(path).with_suffix("").as_posix().replace("/", ".") == module for path in resolved):
            raise ValueError("module_name does not match its owning import root and source path")


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
            if not FIELDS <= set(entry) or set(entry) - FIELDS - OPTIONAL_FIELDS:
                raise ValueError("unknown or missing inventory entry fields; commands forbidden")
            path = safe_path(root, entry["path"])
            if not entry["path"].startswith(("tests/", "tools/")):
                errors.append(f"path outside managed test roots: {entry['path']}")
            if path.suffix != ".py" or not path.is_file():
                errors.append(f"missing Python path: {entry['path']}")
            validate_entry_imports(root, entry)
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
    return {"format": "irisx.suite-report.v1", "suite": suite, "status": "failed", "tests": 0, "failures": 0, "errors": 0, "skips": 0, "expected_skips": 0, "unexpected_skips": 0, "blocked": 0, "exit_code": 1, "modules": [], "attestable": False, "evidence_kind": "development", "target_commit": None, "head_commit": None, "inventory_blob": None, "runner_blob": None, "source_identity": None}


def _load_owned_parents(root: Path, file: Path, name: str, declared: list[Path]) -> None:
    owner = next(p for p in declared if file.is_relative_to(p) and file.relative_to(p).with_suffix("").as_posix().replace("/", ".") == name)
    parts = name.split(".")
    for count in range(1, len(parts)):
        parent_name = ".".join(parts[:count])
        directory = safe_path(root, owner.joinpath(*parts[:count]).relative_to(root).as_posix())
        if not directory.is_dir():
            raise ValueError("package parent directory is missing")
        if parent_name in sys.modules:
            origins = list(getattr(sys.modules[parent_name], "__path__", ()))
            if not origins or any(Path(p).resolve() != directory.resolve() for p in origins):
                raise ValueError("package collision outside owning snapshot")
            continue
        init = directory / "__init__.py"
        if init.is_file():
            spec = importlib.util.spec_from_file_location(parent_name, init, submodule_search_locations=[str(directory)])
            module = importlib.util.module_from_spec(spec)
            sys.modules[parent_name] = module
            spec.loader.exec_module(module)
            origins = list(getattr(module, "__path__", ()))
            if not origins or any(Path(p).resolve() != directory.resolve() for p in origins):
                raise ValueError("package namespace escapes owning snapshot")
        else:
            # Namespace parents are deliberately confined to the owning source.
            # import_module could execute an unrelated installed regular package
            # before an origin check, so no global package search is used here.
            module = types.ModuleType(parent_name)
            module.__path__ = [str(directory)]
            module.__package__ = parent_name
            module.__spec__ = importlib.machinery.ModuleSpec(parent_name, loader=None, is_package=True)
            module.__spec__.submodule_search_locations = module.__path__
            sys.modules[parent_name] = module


def _child(root: Path, suite: str, path: str, report_path: Path, binding: dict | None = None) -> int:
    selected = select_suite(root, suite)
    entry = next((e for e in selected if e["path"] == path), None)
    if entry is None or entry["dependency_class"] in PROTECTED or entry["collector"] != "unittest":
        raise ValueError("protected/unselected module cannot be imported")
    report = _empty(suite)
    if binding is not None:
        report.update(binding)
    report.update(path=path, collection_errors=0, collection_messages=[])
    report["interpreter_startup"] = interpreter_startup()
    file = safe_path(root, path)
    declared = [safe_path(root, name) for name in entry.get("import_roots", [])]
    sys.path[:0] = list(dict.fromkeys(str(p) for p in [*declared, file.parent, root / "tests", root / "src", root]))
    try:
        startup_errors = validate_child_startup(report["interpreter_startup"])
        if startup_errors:
            raise ValueError("; ".join(startup_errors))
        identity_errors = verify_binding(root, report)
        if identity_errors:
            raise ValueError("; ".join(identity_errors))
        name = entry.get("module_name", file.stem)
        if "." in name:
            _load_owned_parents(root, file, name, declared)
        spec = importlib.util.spec_from_file_location(name, file)
        if spec is None or spec.loader is None:
            raise ValueError("missing module spec")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        loader = unittest.TestLoader()
        tests = loader.loadTestsFromModule(module)
        result = unittest.TextTestRunner(verbosity=2).run(tests)
        report.update(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), skips=len(result.skipped), collection_errors=len(loader.errors), collection_messages=loader.errors)
        skip_records = []
        for test, reason in result.skipped:
            allowed = any(s["test_id"] == test.id() and s["reason_contains"] in reason and sys.platform in s["platforms"] for s in entry["expected_skips"])
            report["expected_skips" if allowed else "unexpected_skips"] += 1
            skip_records.append({"test_id": test.id(), "reason": reason})
        report["skip_records"] = skip_records
        report["failure_ids"] = [t.id() for t, _ in result.failures]
        report["error_ids"] = [t.id() for t, _ in result.errors]
        passed = result.wasSuccessful() and result.testsRun > 0 and not loader.errors and not report["unexpected_skips"]
        identity_errors = verify_binding(root, report)
        if identity_errors:
            raise ValueError("; ".join(identity_errors))
        report.update(status="passed" if passed else "failed", exit_code=0 if passed else 1)
    except Exception as exc:
        report.update(errors=report["errors"] + 1, collection_errors=report["collection_errors"] + 1,
                      collection_messages=[*report["collection_messages"], f"{type(exc).__name__}: {exc}"])
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report["exit_code"]


def run_suite(root: Path, suite: str, output: Path, *, require_committed: bool = False) -> dict:
    root = root.resolve()
    relative = output.absolute().relative_to(root).as_posix()
    output = safe_path(root, relative)
    if not relative.startswith(".irisx/") or output.exists():
        raise ValueError("report output must be a new ignored .irisx directory")
    output.mkdir(parents=True)
    report = _empty(suite)
    report.update(python=sys.version, platform=platform.platform(), cwd=str(root), commands=[], source_changes=[])
    try:
        report["head_commit"] = inspect_source(root)["head_commit"]
        select_suite(root, suite)  # Static validation before copying/importing.
        snapshot = create_snapshot(root, output / "source", require_committed=require_committed, runner_path=Path(__file__).resolve())
        report.update(snapshot.binding)
        report["execution_root"] = str(snapshot.root)
        selected = select_suite(snapshot.root, suite)
        report["selected_paths"] = [e["path"] for e in selected]
        if any(e["dependency_class"] in PROTECTED or e["collector"] != "unittest" for e in selected):
            report.update(status="blocked", blocked=len(selected), exit_code=2, reason="requires authentic inputs, native training scope, or reviewed standalone script; no module imported")
        else:
            env = controlled_python_environment()
            env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TMPDIR": str(output), "TMP": str(output), "TEMP": str(output)})
            report["child_python_environment"] = dict(PYTHON_ENVIRONMENT)
            child_output = snapshot.root / ".irisx/suite-reports"
            child_output.mkdir(parents=True)
            binding_path = child_output / "source-binding.json"
            binding_path.write_text(json.dumps(snapshot.binding), encoding="utf-8")
            for number, entry in enumerate(selected):
                changes = snapshot.changes()
                if changes:
                    raise ValueError("; ".join(changes))
                child_path = child_output / f"module-{number:03d}.json"
                command = controlled_python_command(sys.executable, str(snapshot.root / "tools/suite_runner.py"), "--root", str(snapshot.root), "--suite", suite, "--child", entry["path"], "--child-report", str(child_path), "--binding", str(binding_path))
                report["commands"].append(command)
                try:
                    completed = subprocess.run(command, cwd=snapshot.root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
                    (output / f"module-{number:03d}.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
                    if child_path.is_file():
                        child = load_json(child_path)
                        if (child.get("format") != "irisx.suite-report.v1" or child.get("suite") != suite or child.get("path") != entry["path"] or any(child.get(k) != snapshot.binding[k] for k in snapshot.binding) or any(type(child.get(k)) is not int or child[k] < 0 for k in ("tests", "failures", "errors", "skips", "expected_skips", "unexpected_skips", "blocked", "exit_code")) or child["skips"] != child["expected_skips"] + child["unexpected_skips"] or validate_child_startup(child.get("interpreter_startup"))):
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
                (output / f"module-{number:03d}.json").write_text(json.dumps(child, indent=2) + "\n", encoding="utf-8")
                for field in ("tests", "failures", "errors", "skips", "expected_skips", "unexpected_skips", "blocked"):
                    report[field] += child[field]
            passed = report["tests"] > 0 and all(m["status"] == "passed" for m in report["modules"])
            report.update(status="passed" if passed else "failed", exit_code=0 if passed else 1)
        changes = snapshot.changes()
        if changes:
            report.update(status="failed", exit_code=1, source_changes=changes, errors=report["errors"] + 1)
            report.update(attestable=False, evidence_kind="development", target_commit=None)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        report.update(status="failed", exit_code=1, errors=report["errors"] + 1, reason=str(exc), attestable=False, evidence_kind="development", target_commit=None)
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
    parser.add_argument("--require-committed", action="store_true", help="reject dirty/unbound evidence before importing tests")
    parser.add_argument("--child", help=argparse.SUPPRESS)
    parser.add_argument("--child-report", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--binding", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child:
        report_path = safe_path(args.root, args.child_report.absolute().relative_to(args.root).as_posix())
        if not report_path.is_relative_to(args.root / ".irisx") or report_path.exists():
            raise ValueError("child report must be new and ignored")
        binding = None
        if args.binding is not None:
            binding_path = safe_path(args.root, args.binding.absolute().relative_to(args.root).as_posix())
            if not binding_path.is_relative_to(args.root / ".irisx"):
                raise ValueError("child binding must be snapshot-local")
            binding = load_json(binding_path)
        return _child(args.root, args.suite, args.child, report_path, binding)
    if args.output is None:
        parser.error("--output required")
    report = run_suite(args.root, args.suite, args.output.absolute(), require_committed=args.require_committed)
    print(json.dumps({k: v for k, v in report.items() if k not in {"commands", "modules"}}, indent=2))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
