"""Controlled, offline development entry point, separate from the product CLI."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import time

from workstream_management import MARKER, _records, render_board, safe_path, validate

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("check")
    render = commands.add_parser("render")
    render.add_argument("--check", action="store_true")
    context = commands.add_parser("context")
    context.add_argument("--task", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--suite", required=True)
    verify.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            from suite_runner import run_suite
            output = args.output or ROOT / f".irisx/core/verification/{args.suite}/{time.time_ns()}"
            report = run_suite(ROOT, args.suite, output.absolute())
            print(f"{args.suite}: {report['status']}; tests={report['tests']} failures={report['failures']} errors={report['errors']} skips={report['skips']} blocked={report['blocked']}")
            print(output / "report.json")
            return report["exit_code"]
        if args.command == "status":
            print(render_board(ROOT), end="")
        elif args.command == "context":
            catalog, tasks = _records(ROOT)
            task = next((t for t in tasks if t["id"] == args.task), None)
            if task is None:
                raise ValueError(f"unknown task: {args.task}")
            docs = {d["id"]: d for d in catalog["documents"]}
            print(f"{task['id']}: {task['state']} (independent review pending unless sourced)")
            print("Read AGENTS.md and narrower rules for: " + ", ".join(task["scope_paths"]))
            for ref in [task["plan_ref"], task.get("handoff_ref"), *task["verification_refs"]]:
                if ref in docs:
                    print(docs[ref].get("path") or docs[ref].get("url"))
            print("docs/workstreams/" + task["workstream"] + "/STATUS.md")
        elif args.command == "render" and not args.check:
            board = safe_path(ROOT, "docs/management/BOARD.md")
            if board.exists() and not board.read_text(encoding="utf-8").startswith(MARKER):
                raise ValueError("refusing to overwrite unmarked BOARD")
            board.write_text(render_board(ROOT), encoding="utf-8", newline="\n")
        else:
            errors = validate(ROOT)
            if (ROOT / "tests/inventory.json").is_file():
                from suite_runner import validate_inventory
                errors.extend(validate_inventory(ROOT))
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
            print("management: PASS (structure only; independent evidence review remains separate)")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"dev: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
