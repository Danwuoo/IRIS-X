"""Exercise repository onboarding in a new ignored local Git clone only."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

try:
    from .suite_runner import validate_gate
    from .workstream_management import load_json, safe_path
except ImportError:
    from suite_runner import validate_gate
    from workstream_management import load_json, safe_path

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "ONBOARD-LB-01"
PLAN_ID = "onboarding-line-b-plan"
GUIDE_ID = "onboarding-line-b-guide"
HANDOFF_ID = "onboarding-line-b-handoff"
PLAN_PATH = "docs/plan/synthetic-line-b-onboarding.md"
GUIDE_PATH = "docs/development/synthetic-line-b-onboarding.md"
HANDOFF_PATH = f"docs/verification/{TASK_ID}/HANDOFF.md"
RESEARCH_SHA = "cc14bd1a79aac1fe6135017c9e09d4834300675d"
RESEARCH_IDS = ("arc-r4-primary-method-assessment", "arc-r5-native-research-continuation")


def output_path(root: Path, output: Path) -> Path:
    relative = output.absolute().relative_to(root.absolute()).as_posix()
    path = safe_path(root.absolute(), relative)
    if not relative.startswith(".irisx/") or path.exists():
        raise ValueError("onboarding output must be a new ignored .irisx directory")
    return path


def exercise_task(commit: str, base_branch: str, head_branch: str) -> dict:
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("onboarding requires an actual full source commit SHA")
    return {
        "format": "irisx.task.v1", "id": TASK_ID,
        "title": "Synthetic line-b management onboarding exercise",
        "workstream": "line-b", "state": "in_progress", "depends_on": ["WSF-04"],
        "owner_role": "onboarding-self-check", "plan_ref": PLAN_ID,
        "scope_paths": [PLAN_PATH, GUIDE_PATH, HANDOFF_PATH, f"docs/management/tasks/{TASK_ID}.json"],
        "base_branch": base_branch, "head_branch": head_branch, "base_commit": commit,
        "implementation_commit": None, "acceptance": ["OB1-1"], "blockers": [],
        "handoff_ref": None, "verification_refs": [], "review_refs": [], "concurrency_group": None,
    }


def finish_task(task: dict, commit: str, report: dict) -> dict:
    errors = validate_gate({"line-b": report}, ["line-b"])
    if (not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit) or task.get("base_commit") != commit or
            task.get("id") != TASK_ID or task.get("state") != "in_progress" or errors or
            report.get("target_commit") != commit or report.get("format") != "irisx.suite-report.v1" or
            report.get("suite") != "line-b"):
        raise ValueError("onboarding task needs passing commit-bound self-tests before review_ready")
    return dict(task, state="review_ready", implementation_commit=commit,
                handoff_ref=HANDOFF_ID, verification_refs=[HANDOFF_ID], review_refs=[])


def register_document(catalog: dict, doc_id: str, path: str, kind: str) -> None:
    if any(doc.get("id") == doc_id or doc.get("path") == path for doc in catalog["documents"]):
        raise ValueError("onboarding cannot replace an original catalog document")
    catalog["documents"].append({
        "id": doc_id, "path": path, "kind": kind, "workstream": "line-b",
        "status": "active", "owner_role": "onboarding-self-check",
        "related_tasks": [TASK_ID], "supersedes": [],
    })


def write_new(root: Path, relative: str, text: str) -> None:
    path = safe_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_json(root: Path, relative: str, data: dict) -> None:
    safe_path(root, relative).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8", newline="\n")


def navigation_chain(root: Path, catalog: dict, task: dict) -> list[dict]:
    docs = {doc["id"]: doc for doc in catalog["documents"]}
    readme = safe_path(root, "docs/README.md").read_text(encoding="utf-8")
    board = safe_path(root, "docs/management/BOARD.md").read_text(encoding="utf-8")
    if "(management/BOARD.md)" not in readme or f"(tasks/{task['id']}.json)" not in board:
        raise ValueError("onboarding README/BOARD/task chain is missing")
    task_path = f"docs/management/tasks/{task['id']}.json"
    if load_json(safe_path(root, task_path)) != task:
        raise ValueError("onboarding task identity differs from its record")
    plan = docs.get(task["plan_ref"], {})
    handoff = docs.get(task.get("handoff_ref"), {})
    code = "src/irisx/domains/line_b/flow.py"
    for relative in (plan.get("path", ""), code, handoff.get("path", "")):
        if not safe_path(root, relative).is_file():
            raise ValueError("onboarding plan/code/handoff chain is incomplete")
    if "(../../" + code + ")" not in safe_path(root, plan["path"]).read_text(encoding="utf-8"):
        raise ValueError("onboarding plan does not lead to its program")
    if "\ntarget_commit: " + task["implementation_commit"] + "\n" not in safe_path(root, handoff["path"]).read_text(encoding="utf-8"):
        raise ValueError("onboarding handoff lacks its program commit binding")
    return [
        {"role": "entry", "path": "docs/README.md"},
        {"role": "board", "path": "docs/management/BOARD.md"},
        {"role": "task", "path": task_path},
        {"role": "plan", "path": plan["path"]},
        {"role": "code", "path": code},
        {"role": "handoff", "path": handoff["path"]},
    ]


def research_sources(root: Path, catalog: dict) -> list[dict]:
    status = safe_path(root, "docs/workstreams/arc-agi-2/STATUS.md").read_text(encoding="utf-8")
    research = safe_path(root, "docs/workstreams/arc-agi-2/RESEARCH.md").read_text(encoding="utf-8")
    if "(RESEARCH.md)" not in status:
        raise ValueError("ARC STATUS does not lead to the research entry")
    docs = {doc["id"]: doc for doc in catalog["documents"]}
    results = []
    for doc_id in RESEARCH_IDS:
        url = docs.get(doc_id, {}).get("url", "")
        match = re.fullmatch(r"https://github\.com/Danwuoo/IRIS-X/blob/([0-9a-f]{40})/(.+)", url)
        if not match or match[1] != RESEARCH_SHA or url not in research:
            raise ValueError("research source lacks its fixed catalog/entry binding")
        results.append({"id": doc_id, "url": url, "commit": match[1], "path": match[2],
                        "remote_availability": "unverified", "research_content_review": "pending human review"})
    return results


def run_onboarding(root: Path, output: Path) -> dict:
    root = root.absolute()
    output = output_path(root, output)
    output.mkdir(parents=True)
    report = {"format": "irisx.onboarding-report.v1", "status": "failed",
              "scope": "synthetic engineering-only non-deployable; developer self-check",
              "independent_review": "pending", "commands": [], "target_commit": None}
    environment = os.environ.copy()
    environment.update(PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1",
                       TRANSFORMERS_OFFLINE="1", HF_DATASETS_OFFLINE="1")

    def run(argv: list[str], cwd: Path) -> str:
        result = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=180)
        log = f"command-{len(report['commands']) + 1:02d}.log"
        (output / log).write_text(result.stdout + result.stderr, encoding="utf-8")
        report["commands"].append({"argv": argv, "cwd": str(cwd), "exit_code": result.returncode, "log": log})
        if result.returncode:
            raise ValueError(f"onboarding command failed ({result.returncode}); see {log}")
        return result.stdout.strip()

    try:
        commit = run(["git", "rev-parse", "HEAD"], root)
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("source HEAD is not a full Git commit identity")
        report["target_commit"] = commit
        source_branch = run(["git", "branch", "--show-current"], root) or "detached-source"
        hooks = output / "empty-hooks"
        hooks.mkdir()
        checkout = output / "checkout"
        # A local filesystem source and shared object store cause no Git network
        # retrieval. Hooks are disabled per command, not through global settings.
        run(["git", "-c", f"core.hooksPath={hooks}", "clone", "--quiet", "--shared", "--no-checkout",
             str(root), str(checkout)], root)
        run(["git", "-c", f"core.hooksPath={hooks}", "switch", "--detach", commit], checkout)
        branch = f"codex/onboarding-line-b-{time.time_ns()}"
        run(["git", "-c", f"core.hooksPath={hooks}", "switch", "-c", branch], checkout)
        if run(["git", "status", "--porcelain"], checkout):
            raise ValueError("local source clone is not initially clean")
        report["initial_checkout_clean"] = True
        catalog = load_json(safe_path(checkout, "docs/management/documents.json"))
        original_task_bytes = {
            path.name: path.read_bytes() for path in safe_path(checkout, "docs/management/tasks").glob("*.json")
        }
        task = exercise_task(commit, source_branch, branch)
        plan = ("# Synthetic line-b onboarding\n\n"
                "This temporary checkout exercise is engineering-only and non-deployable.\n\n"
                "- OB1-1: Register a task/document, execute the existing scoped line-b suite,\n"
                "  produce a commit-bound developer handoff and return to the core task.\n\n"
                "Program: [shared line-b flow](../../src/irisx/domains/line_b/flow.py).\n"
                "No new domain, solver, training, provider or independent acceptance is claimed.\n")
        guide = ("# Temporary onboarding guide\n\n"
                 "[Task board](../management/BOARD.md) → [exercise plan](../plan/synthetic-line-b-onboarding.md).\n"
                 "Use the existing synthetic line-b program; return to WSF-04 after self-tests.\n")
        write_new(checkout, PLAN_PATH, plan)
        write_new(checkout, GUIDE_PATH, guide)
        write_new(checkout, f"docs/management/tasks/{TASK_ID}.json", json.dumps(task, indent=2) + "\n")
        register_document(catalog, PLAN_ID, PLAN_PATH, "plan")
        register_document(catalog, GUIDE_ID, GUIDE_PATH, "guide")
        write_json(checkout, "docs/management/documents.json", catalog)
        python = sys.executable
        run([python, "-B", "tools/dev.py", "render"], checkout)
        run([python, "-B", "tools/dev.py", "context", "--task", TASK_ID], checkout)
        run([python, "-B", "tools/dev.py", "check"], checkout)
        suite_output = checkout / ".irisx/line-b/onboarding-suite"
        run([python, "-B", "tools/dev.py", "verify", "--suite", "line-b", "--output", str(suite_output)], checkout)
        suite_report = load_json(safe_path(checkout, ".irisx/line-b/onboarding-suite/report.json"))
        task = finish_task(task, commit, suite_report)
        handoff = ("# Synthetic onboarding developer handoff\n\n"
                   f"Task: {TASK_ID}; state: review_ready.\n\ntarget_commit: {commit}\n\n"
                   "The committed program was reused unchanged. Temporary task/document metadata\n"
                   "was added only in this self-owned checkout. The line-b controlled suite passed;\n"
                   f"tests={suite_report['tests']}, failures={suite_report['failures']}, errors={suite_report['errors']}, "
                   f"skips={suite_report['skips']}, blocked={suite_report['blocked']}.\n\n"
                   "This is developer self-validation. Independent review remains pending;\n"
                   "no scientific capability, GPU result or deployment is established.\n")
        write_new(checkout, HANDOFF_PATH, handoff)
        register_document(catalog, HANDOFF_ID, HANDOFF_PATH, "evidence")
        write_json(checkout, "docs/management/documents.json", catalog)
        write_json(checkout, f"docs/management/tasks/{TASK_ID}.json", task)
        run([python, "-B", "tools/dev.py", "render"], checkout)
        run([python, "-B", "tools/dev.py", "render", "--check"], checkout)
        report["navigation_chain"] = navigation_chain(checkout, catalog, task)
        report["research_sources"] = research_sources(checkout, catalog)
        for source in report["research_sources"]:
            run(["git", "cat-file", "-e", source["commit"] + ":" + source["path"]], checkout)
            source["git_blob"] = run(["git", "rev-parse", source["commit"] + ":" + source["path"]], checkout)
            source["local_git_object"] = "present"
        run([python, "-B", "tools/dev.py", "context", "--task", "WSF-04"], checkout)
        run(["git", "diff", "--exit-code", "HEAD", "--", "src", "tools", "tests", ".github", "pyproject.toml"], checkout)
        if any((checkout / "docs/management/tasks" / name).read_bytes() != data
               for name, data in original_task_bytes.items()):
            raise ValueError("onboarding changed an original task record")
        report.update(status="passed", task_id=TASK_ID, task_state=task["state"],
                      program_and_original_tasks_unchanged=True, returned_to_task="WSF-04",
                      line_b_suite={key: suite_report[key] for key in
                                    ("status", "tests", "failures", "errors", "skips", "blocked", "target_commit")},
                      checkout=str(checkout), sandbox_head_branch=branch)
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_onboarding(args.root, args.output)
        print(json.dumps({key: value for key, value in report.items() if key != "commands"}, indent=2))
        return 0 if report["status"] == "passed" else 1
    except (ValueError, OSError) as exc:
        print(f"onboarding: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
