"""Fixed CI gate bound to the target commit's inventory and source Git objects."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

try:
    from .workstream_management import load_json, safe_path
except ImportError:
    from workstream_management import load_json, safe_path

ROOT = Path(__file__).resolve().parents[1]
SUITES = ("core", "distribution", "management", "navigation", "integrity", "arc-unit", "line-b")
OPERATING_SYSTEMS = ("ubuntu-latest", "windows-latest")
PYTHONS = ("3.11", "3.14")
COUNTS = ("tests", "failures", "errors", "skips", "expected_skips", "unexpected_skips", "blocked")
ENTRY_FIELDS = {"path", "workstream", "dependency_class", "suite", "role", "dependencies", "collector", "reason", "expected_skips"}
OPTIONAL_ENTRY_FIELDS = {"import_roots", "module_name"}
DEPENDENCIES = {"stdlib", "small-python", "historical", "operational", "native", "training", "unclassified-public"}
PROTECTED = {"historical", "operational", "native", "training"}
MATH_TEST_ROOTS = ("research/math-proof-agent/round001", "research/math-proof-agent/round002")
MATH_NAMED_TESTS = {"research/math-proof-agent/round002/controls.py"}


def _git(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(["git", *arguments], cwd=root, capture_output=True, check=False)
    if result.returncode:
        raise ValueError("target Git object unavailable: " + " ".join(arguments))
    return result.stdout


def _relative_path(value: str) -> bool:
    return (isinstance(value, str) and bool(value) and not PurePosixPath(value).is_absolute()
            and "\\" not in value and ":" not in value
            and all(part not in {"", ".", ".."} for part in value.split("/")))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate inventory JSON key: " + key)
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("nonfinite inventory JSON number: " + value)


def _authoritative(root: Path, commit: str) -> dict:
    """Use target Git metadata and inventory bytes only, never the checkout copy."""
    if not isinstance(commit, str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit):
        raise ValueError("target_commit must be a complete Git object ID")
    if _git(root, "cat-file", "-t", commit).strip() != b"commit":
        raise ValueError("target object is not a Git commit")
    tree = _git(root, "rev-parse", commit + "^{tree}").decode("ascii").strip()
    files = {}
    folded = set()
    components = {}
    for raw in _git(root, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
        if not raw:
            continue
        metadata, name = raw.split(b"\t", 1)
        mode, kind, blob = metadata.decode("ascii").split()
        path = name.decode("utf-8")
        if (kind != "blob" or mode not in {"100644", "100755"}
                or not _relative_path(path) or path.casefold() in folded):
            raise ValueError("unsafe/colliding target source path: " + path)
        if path.split("/", 1)[0].casefold() in {".git", ".irisx"}:
            raise ValueError("target source cannot include Git/output directories: " + path)
        folded.add(path.casefold())
        parts = path.split("/")
        for count in range(1, len(parts) + 1):
            prefix = "/".join(parts[:count])
            previous = components.setdefault(prefix.casefold(), prefix)
            if previous != prefix:
                raise ValueError("colliding target source parent path: " + path)
        files[path] = {"path": path, "mode": mode, "blob": blob}
    inventory_row = files.get("tests/inventory.json")
    runner_row = files.get("tools/suite_runner.py")
    if inventory_row is None or runner_row is None:
        raise ValueError("target lacks authoritative inventory or runner Git blob")
    if int(_git(root, "cat-file", "-s", inventory_row["blob"]).strip()) > 16 * 1024**2:
        raise ValueError("authoritative inventory exceeds bounded metadata size")
    inventory = json.loads(_git(root, "cat-file", "blob", inventory_row["blob"]).decode("utf-8"),
                           object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    if (not isinstance(inventory, dict) or set(inventory) != {"format", "suites", "entries"}
            or inventory["format"] != "irisx.tests.v1" or not isinstance(inventory["suites"], dict)
            or not isinstance(inventory["entries"], list)):
        raise ValueError("invalid authoritative inventory schema")
    suite_catalog = inventory["suites"]
    for name, options in suite_catalog.items():
        if (not isinstance(name, str) or not name or not isinstance(options, dict)
                or set(options) != {"public"} or type(options["public"]) is not bool):
            raise ValueError("invalid authoritative suite catalog")
    if {name for name, options in suite_catalog.items() if options["public"]} != set(SUITES):
        raise ValueError("authoritative public suite catalog differs from fixed matrix")
    entries = {}
    expected = {name: [] for name in SUITES}
    for entry in inventory["entries"]:
        if (not isinstance(entry, dict) or not ENTRY_FIELDS <= set(entry)
                or set(entry) - ENTRY_FIELDS - OPTIONAL_ENTRY_FIELDS):
            raise ValueError("unknown/missing authoritative inventory entry fields")
        path = entry["path"]
        if (not _relative_path(path)
                or not (path.split("/")[0] in {"tests", "tools"}
                        or any(path.startswith(directory + "/") for directory in MATH_TEST_ROOTS))
                or not path.endswith(".py") or path not in files or path.casefold() in entries):
            raise ValueError("missing/duplicate/unsafe authoritative module path: " + str(path))
        dependency = entry["dependency_class"]
        suite = entry["suite"]
        if (not isinstance(dependency, str) or dependency not in DEPENDENCIES
                or not isinstance(suite, str) or suite not in suite_catalog
                or entry["workstream"] not in {"core", "arc-agi-2", "line-b"}
                or entry["role"] not in {"test", "helper", "script"}
                or entry["collector"] not in {"unittest", "helper", "blocked-script"}
                or ((entry["role"] == "test") != (entry["collector"] == "unittest"))
                or not isinstance(entry["dependencies"], list)
                or not all(isinstance(item, str) for item in entry["dependencies"])
                or not isinstance(entry["reason"], str) or not entry["reason"].strip()
                or not isinstance(entry["expected_skips"], list)):
            raise ValueError("invalid authoritative module classification: " + path)
        for skip in entry["expected_skips"]:
            if (not isinstance(skip, dict) or set(skip) != {"test_id", "reason_contains", "platforms"}
                    or not isinstance(skip["test_id"], str) or not skip["test_id"].strip()
                    or not isinstance(skip["reason_contains"], str) or not skip["reason_contains"].strip()
                    or not isinstance(skip["platforms"], list) or not skip["platforms"]
                    or any(not isinstance(item, str) or item not in {"linux", "win32", "darwin"}
                           for item in skip["platforms"])):
                raise ValueError("invalid authoritative skip allowlist: " + path)
        if "import_roots" in entry and (not isinstance(entry["import_roots"], list)
                or any(not _relative_path(item) for item in entry["import_roots"])):
            raise ValueError("invalid authoritative import roots: " + path)
        if "module_name" in entry and (not isinstance(entry["module_name"], str)
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", entry["module_name"])):
            raise ValueError("invalid authoritative module name: " + path)
        entries[path.casefold()] = entry
        if suite in expected and entry["role"] != "helper":
            if dependency in PROTECTED or entry["collector"] != "unittest":
                raise ValueError("protected module in authoritative public suite: " + path)
            expected[suite].append(path)
    required = {path.casefold() for path in files if path.startswith("tests/") and path.endswith(".py")}
    required.update(path.casefold() for path in files if path.startswith("tools/")
                    and PurePosixPath(path).name.startswith("test_") and path.endswith(".py"))
    required.update(path.casefold() for path in files
                    if any(path.startswith(directory + "/") for directory in MATH_TEST_ROOTS)
                    and PurePosixPath(path).name.startswith("test_") and path.endswith(".py"))
    required.update(path.casefold() for path in MATH_NAMED_TESTS if path in files)
    if required - entries.keys():
        raise ValueError("unclassified authoritative test paths")
    if any(not paths for paths in expected.values()):
        raise ValueError("empty authoritative public suite selection")
    manifest = [files[path] for path in sorted(files)]
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                                           ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"expected": expected, "entries": entries, "inventory_blob": inventory_row["blob"],
            "runner_blob": runner_row["blob"], "source_identity": {
                "format": "irisx.source-identity.v1", "commit": commit, "tree": tree,
                "manifest_sha256": fingerprint}}


def _bound(report: dict, commit: str, authority: dict) -> bool:
    return (report.get("attestable") is True and report.get("evidence_kind") == "commit"
            and report.get("target_commit") == commit
            and report.get("inventory_blob") == authority["inventory_blob"]
            and report.get("runner_blob") == authority["runner_blob"]
            and report.get("source_identity") == authority["source_identity"])


def _counts(report: dict) -> bool:
    return (all(type(report.get(field)) is int and report[field] >= 0 for field in COUNTS)
            and report["tests"] > 0 and report.get("status") == "passed"
            and type(report.get("exit_code")) is int and report["exit_code"] == 0
            and all(report[field] == 0 for field in ("failures", "errors", "unexpected_skips", "blocked")))


def _skip_errors(module: dict, entry: dict, operating_system: str) -> list[str]:
    records = module.get("skip_records")
    if not isinstance(records, list):
        return ["missing actual skip records"]
    errors = []
    ids = set()
    allowed = 0
    platform_name = "win32" if operating_system == "windows-latest" else "linux"
    for record in records:
        if (not isinstance(record, dict) or set(record) != {"test_id", "reason"}
                or not isinstance(record["test_id"], str) or not record["test_id"]
                or not isinstance(record["reason"], str) or not record["reason"]
                or record["test_id"] in ids):
            errors.append("invalid/duplicate actual skip record")
            continue
        ids.add(record["test_id"])
        if any(item["test_id"] == record["test_id"] and item["reason_contains"] in record["reason"]
               and platform_name in item["platforms"] for item in entry["expected_skips"]):
            allowed += 1
        else:
            errors.append("skip not allowed by target inventory and OS: " + record["test_id"])
    if (module.get("skips") != len(records) or module.get("expected_skips") != allowed
            or module.get("unexpected_skips") != len(records) - allowed
            or type(module.get("tests")) is not int or module["tests"] < len(records)):
        errors.append("actual skip record/count mismatch")
    return errors


def check_matrix(directory: Path, commit: str, repository_root: Path = ROOT) -> list[str]:
    errors = []
    try:
        authority = _authoritative(Path(repository_root).resolve(), commit)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        return ["authoritative target inventory/source unavailable: " + str(exc)]

    def read(relative):
        try:
            data = load_json(safe_path(directory, relative))
            if not isinstance(data, dict):
                raise ValueError("report must be an object")
            return data
        except (ValueError, OSError, TypeError) as exc:
            errors.append(f"missing or malformed report: {relative}: {exc}")
            return None

    def environment_matches(report, operating_system, python):
        platform_name = report.get("platform", "")
        return (isinstance(platform_name, str)
                and platform_name.startswith("Windows" if operating_system == "windows-latest" else "Linux")
                and isinstance(report.get("python"), str) and report["python"].startswith(python + "."))

    for operating_system in OPERATING_SYSTEMS:
        for python in PYTHONS:
            for suite in SUITES:
                label = f"{suite}/{operating_system}/{python}"
                report = read(f"public-{suite}-{operating_system}-{python}/report.json")
                if report is None:
                    continue
                if (report.get("format") != "irisx.suite-report.v1" or report.get("suite") != suite
                        or not _bound(report, commit, authority)
                        or not environment_matches(report, operating_system, python) or not _counts(report)):
                    errors.append("non-attestable/failed report identity or counts: " + label)
                expected = authority["expected"][suite]
                selected = report.get("selected_paths")
                modules = report.get("modules")
                if selected != expected:
                    errors.append("authoritative selection mismatch: " + label)
                if not isinstance(modules, list) or not modules:
                    errors.append("missing module reports: " + label)
                    continue
                paths = [module.get("path") if isinstance(module, dict) else None for module in modules]
                if paths != expected:
                    errors.append("missing/replacement/extra/duplicate authoritative modules: " + label)
                for module in modules:
                    if not isinstance(module, dict):
                        errors.append("malformed module: " + label)
                        continue
                    path = module.get("path")
                    if (module.get("format") != "irisx.suite-report.v1" or module.get("suite") != suite
                            or not _bound(module, commit, authority) or not _counts(module)
                            or type(module.get("collection_errors")) is not int or module["collection_errors"] != 0
                            or module.get("collection_messages") != []):
                        errors.append("failed/non-attestable module: " + label + "/" + str(path))
                    entry = authority["entries"].get(path.casefold()) if isinstance(path, str) else None
                    if entry is None or path not in expected:
                        errors.append("unselected module cannot supply evidence: " + label + "/" + str(path))
                    else:
                        errors.extend(label + "/" + path + ": " + issue
                                      for issue in _skip_errors(module, entry, operating_system))
                for field in COUNTS:
                    if (any(not isinstance(module, dict) or type(module.get(field)) is not int
                            or module[field] < 0 for module in modules)
                            or sum(module[field] for module in modules) != report.get(field)):
                        errors.append("module count mismatch: " + label + "/" + field)
            report = read(f"formal-{operating_system}-{python}/report.json")
            if report is None:
                continue
            wheels = report.get("wheels", [])
            commands = report.get("commands")
            if (report.get("schema") != "irisx/distribution-self-check-v1" or report.get("status") != "passed"
                    or not _bound(report, commit, authority) or not environment_matches(report, operating_system, python)
                    or not isinstance(wheels, list) or len(wheels) != 2
                    or not all(isinstance(wheel, dict) and isinstance(wheel.get("sha256"), str)
                               and re.fullmatch(r"[0-9a-f]{64}", wheel["sha256"])
                               and wheel.get("record_verified") is True and type(wheel.get("members")) is int
                               and wheel["members"] > 0 for wheel in wheels)
                    or wheels[0].get("sha256") != wheels[1].get("sha256")
                    or report.get("synthetic_reference_flow") != "passed" or report.get("line_b_synthetic_flow") != "passed"
                    or not isinstance(report.get("installation"), dict) or report["installation"].get("non_editable") is not True
                    or report["installation"].get("editable_pth") != [] or not isinstance(commands, list) or not commands
                    or any(not isinstance(command, dict) or type(command.get("exit_code")) is not int
                           or type(command.get("expected_exit_code")) is not int
                           or command["exit_code"] != command["expected_exit_code"]
                           or not isinstance(command.get("argv"), list) or not command["argv"]
                           or not all(isinstance(argument, str) for argument in command["argv"])
                           or not isinstance(command.get("cwd"), str) or not command["cwd"] for command in commands)):
                errors.append(f"failed formal distribution: {operating_system}/{python}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        needs = json.loads(os.environ.get("WORKSTREAM_NEEDS", "{}"))
        if not isinstance(needs, dict):
            raise ValueError("WORKSTREAM_NEEDS must be an object")
        errors = [f"missing/cancelled/non-success job: {job}" for job in ("public-suites", "formal-distribution")
                  if not isinstance(needs.get(job), dict) or needs[job].get("result") != "success"]
        commit = _git(args.repository_root, "rev-parse", "HEAD").decode("ascii").strip()
        errors.extend(check_matrix(args.reports, commit, repository_root=args.repository_root))
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print("workstream-gate: PASS (commit-bound public engineering scope; legacy/ARC audit remains separate)")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"gate: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
