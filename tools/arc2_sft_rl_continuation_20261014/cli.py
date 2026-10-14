"""Prepare an inert research handoff or summarize explicitly supplied local reports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).absolute().parents[1]))
    from arc2_sft_rl_continuation_20261014.io import InputError, read_json, report_links, write_new_json
    from arc2_sft_rl_continuation_20261014.prepare import prepare_plan
    from arc2_sft_rl_continuation_20261014.analysis import analyze_report
else:
    from .io import InputError, read_json, report_links, write_new_json
    from .prepare import prepare_plan
    from .analysis import analyze_report


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        # argparse's default error includes unrecognized arguments. They may
        # contain private file names or values, so use one fixed diagnostic.
        raise InputError("arguments_invalid")


class _Interrupted(BaseException):
    pass


def _terminate(_signum, _frame):
    raise _Interrupted()


def _parser():
    parser = _Parser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Create a source-bound offline plan; no launch or training")
    prep.add_argument("--repository-root", type=Path, default=Path(__file__).absolute().parents[2])
    prep.add_argument("--output", type=Path, required=True)
    analysis = sub.add_parser("analyze", help="Interpret local collector JSON; never authenticate or score")
    for name in ("report", "checkpoint", "retrieval"):
        analysis.add_argument("--" + name, type=Path, required=name == "report")
        analysis.add_argument("--" + name + "-sha256", required=name == "report")
    analysis.add_argument("--output", type=Path, required=True)
    return parser


def main(argv=None):
    previous_handler = None
    handler_installed = False
    try:
        args = _parser().parse_args(argv)
        # CLI-only cooperative termination lets descriptor-owned staging clean
        # up. SIGKILL/power loss cannot run Python cleanup; see the handoff.
        if hasattr(signal, "SIGTERM"):
            previous_handler = signal.signal(signal.SIGTERM, _terminate)
            handler_installed = True
        if args.command == "prepare":
            result = prepare_plan(args.repository_root)
        else:
            documents, descriptors = {}, {}
            for name in ("report", "checkpoint", "retrieval"):
                path, expected = getattr(args, name), getattr(args, name + "_sha256")
                if (path is None) != (expected is None):
                    raise InputError("paired_file_hash_arguments")
                if path is not None:
                    documents[name], descriptors[name] = read_json(path, expected)
            binding = report_links(documents["report"], descriptors["report"],
                                   checkpoint=documents.get("checkpoint"), checkpoint_descriptor=descriptors.get("checkpoint"),
                                   retrieval=documents.get("retrieval"), retrieval_descriptor=descriptors.get("retrieval"))
            result = analyze_report(documents["report"])
            result["input_binding"] = binding
        descriptor = write_new_json(args.output, result)
        notice = {"status": "OFFLINE_OUTPUT_WRITTEN", "output": descriptor,
                  "dispatch_authorized": False}
        if args.command == "analyze":
            notice["analysis_structurally_consistent"] = result["structurally_consistent"]
        print(json.dumps(notice, sort_keys=True))
        return 0
    except InputError as exc:
        print(json.dumps({"status": "INPUT_REJECTED", "code": str(exc), "dispatch_authorized": False}), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, _Interrupted):
        print(json.dumps({"status": "INTERRUPTED", "code": "interrupted",
                          "dispatch_authorized": False}), file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
        # Private source paths, JSON values, raw provider errors and credentials
        # must never be copied into a portable analysis error or stdout.
        print(json.dumps({"status": "INPUT_REJECTED", "code": "local_input_or_output_error",
                          "dispatch_authorized": False}), file=sys.stderr)
        return 2
    finally:
        if handler_installed:
            signal.signal(signal.SIGTERM, previous_handler)


if __name__ == "__main__":
    raise SystemExit(main())
