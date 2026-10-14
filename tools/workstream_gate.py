"""Fixed CI gate for complete public suite and formal distribution reports."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from suite_runner import validate_gate
from workstream_management import load_json, safe_path

SUITES = ("core", "distribution", "management", "navigation", "integrity", "arc-unit", "line-b")
OPERATING_SYSTEMS = ("ubuntu-latest", "windows-latest")
PYTHONS = ("3.11", "3.14")


def check_matrix(directory: Path, commit: str) -> list[str]:
    errors = []
    def read(relative):
        try:
            path = safe_path(directory, relative)
            data = load_json(path)
            if not isinstance(data, dict):
                raise ValueError("report must be an object")
            return data
        except (ValueError, OSError, TypeError) as exc:
            errors.append(f"missing or malformed report: {relative}: {exc}")
            return None
    def environment_matches(report, operating_system, python):
        platform_name = report.get("platform", "")
        return isinstance(platform_name, str) and platform_name.startswith("Windows" if operating_system == "windows-latest" else "Linux") and isinstance(report.get("python"), str) and report["python"].startswith(python + ".")
    for operating_system in OPERATING_SYSTEMS:
        for python in PYTHONS:
            reports = {}
            for suite in SUITES:
                report = read(f"public-{suite}-{operating_system}-{python}/report.json")
                if report is None:
                    continue
                if report.get("format") != "irisx.suite-report.v1" or report.get("suite") != suite or report.get("target_commit") != commit or not environment_matches(report, operating_system, python):
                    errors.append(f"report identity mismatch: {suite}/{operating_system}/{python}")
                modules = report.get("modules")
                if not isinstance(modules, list) or not modules or any(not isinstance(m, dict) or m.get("format") != "irisx.suite-report.v1" or m.get("status") != "passed" or m.get("suite") != suite or type(m.get("exit_code")) is not int or m["exit_code"] != 0 or not isinstance(m.get("path"), str) or not m["path"] or type(m.get("collection_errors")) is not int or m["collection_errors"] != 0 for m in modules):
                    errors.append(f"missing or failed module reports: {suite}/{operating_system}/{python}")
                else:
                    selected_paths = report.get("selected_paths")
                    module_paths = [m["path"] for m in modules]
                    if not isinstance(selected_paths, list) or len(set(module_paths)) != len(module_paths) or sorted(module_paths) != sorted(selected_paths):
                        errors.append(f"selection/module identity mismatch: {suite}/{operating_system}/{python}")
                    for field in ("tests", "failures", "errors", "skips", "expected_skips", "unexpected_skips", "blocked"):
                        if any(type(m.get(field)) is not int or m[field] < 0 for m in modules) or sum(m[field] for m in modules) != report.get(field):
                            errors.append(f"module count mismatch: {suite}/{field}")
                reports[suite] = report
            errors.extend(validate_gate(reports, list(SUITES)))
            report = read(f"formal-{operating_system}-{python}/report.json")
            if report is None:
                continue
            wheels = report.get("wheels", [])
            commands = report.get("commands")
            if (report.get("schema") != "irisx/distribution-self-check-v1" or report.get("status") != "passed" or report.get("target_commit") != commit or not environment_matches(report, operating_system, python) or not isinstance(wheels, list) or len(wheels) != 2 or not all(isinstance(w, dict) and isinstance(w.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", w["sha256"]) and w.get("record_verified") is True and type(w.get("members")) is int and w["members"] > 0 for w in wheels) or wheels[0].get("sha256") != wheels[1].get("sha256") or report.get("synthetic_reference_flow") != "passed" or report.get("line_b_synthetic_flow") != "passed" or not isinstance(report.get("installation"), dict) or report["installation"].get("non_editable") is not True or report["installation"].get("editable_pth") != [] or not isinstance(commands, list) or not commands or any(not isinstance(c, dict) or type(c.get("exit_code")) is not int or type(c.get("expected_exit_code")) is not int or c["exit_code"] != c["expected_exit_code"] or not isinstance(c.get("argv"), list) or not c["argv"] or not all(isinstance(a, str) for a in c["argv"]) or not isinstance(c.get("cwd"), str) or not c["cwd"] for c in commands)):
                errors.append(f"failed formal distribution: {operating_system}/{python}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        needs = json.loads(os.environ.get("WORKSTREAM_NEEDS", "{}"))
        errors = [f"missing/cancelled/non-success job: {job}" for job in ("public-suites", "formal-distribution") if needs.get(job, {}).get("result") != "success"]
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        errors.extend(check_matrix(args.reports, commit))
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print("workstream-gate: PASS (public engineering scope; legacy/ARC audit remains separate)")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"gate: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
