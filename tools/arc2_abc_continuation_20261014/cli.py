"""Inspect one explicitly supplied training audit; never launch or admit a run."""
from __future__ import annotations

import json
from pathlib import Path
import signal
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).absolute().parents[2]))

from tools.arc2_sft_rl_continuation_20261014.io import (
    InputError, read_json, write_new_json,
)
from tools.arc2_sft_rl_continuation_20261014.cli import (
    _Parser, _Interrupted, _terminate,
)


def _parser():
    parser = _Parser(description=__doc__)
    for name in ("audit", "context"):
        parser.add_argument("--" + name, type=Path, required=True)
        parser.add_argument("--" + name + "-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv=None):
    previous_handler = None
    handler_installed = False
    try:
        args = _parser().parse_args(argv)
        if hasattr(signal, "SIGTERM"):
            previous_handler = signal.signal(signal.SIGTERM, _terminate)
            handler_installed = True
        # Reuse the reviewed descriptor-relative reader and its unchanged
        # 16 MiB bound. A larger native audit is an explicit unsupported input,
        # not a reason to silently increase the established boundary.
        audit, audit_descriptor = read_json(args.audit, args.audit_sha256)
        context_document, context_descriptor = read_json(args.context, args.context_sha256)
        # Optional dependencies are imported only after argument and file checks.
        # --help and package import remain usable without CPU tensor packages.
        from tools.arc2_abc_continuation_20261014.audit import (
            analyze_audit, context_from_document,
        )
        context = context_from_document(context_document, audit_sha256=audit_descriptor["sha256"])
        result = analyze_audit(audit, context)
        if type(result) is not dict or type(result.get("status")) is not str:
            raise InputError("audit_result_contract")
        result["input_binding"] = {
            "audit": audit_descriptor,
            "context": context_descriptor,
            "explicit_bytes_hashes_verified": True,
            "external_collection_authenticated": False,
        }
        descriptor = write_new_json(args.output, result)
        print(json.dumps({
            "status": "OFFLINE_AUDIT_OUTPUT_WRITTEN",
            "audit_status": result["status"],
            "output": descriptor,
            "dispatch_authorized": False,
        }, sort_keys=True))
        return 0
    except InputError as exc:
        print(json.dumps({"status": "INPUT_REJECTED", "code": str(exc),
                          "dispatch_authorized": False}), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, _Interrupted):
        print(json.dumps({"status": "INTERRUPTED", "code": "interrupted",
                          "dispatch_authorized": False}), file=sys.stderr)
        return 130
    except ImportError:
        print(json.dumps({"status": "DEPENDENCY_UNAVAILABLE", "code": "offline_cpu_dependencies",
                          "dispatch_authorized": False}), file=sys.stderr)
        return 3
    except (OSError, ValueError, TypeError, KeyError, IndexError, RecursionError, OverflowError, RuntimeError):
        # Never echo a caller's filename, context, source error, or token data.
        print(json.dumps({"status": "INPUT_REJECTED", "code": "local_audit_or_output_error",
                          "dispatch_authorized": False}), file=sys.stderr)
        return 2
    finally:
        if handler_installed:
            signal.signal(signal.SIGTERM, previous_handler)


if __name__ == "__main__":
    raise SystemExit(main())
