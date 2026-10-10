"""Bounded notebook display only; full scientific evidence stays on disk.

Only exact built-in scalar/dict fields are inspected. Large result collections
are never traversed, stringified or copied. This formatter performs no I/O and
does not change RESULT, evidence, gates, accounting or resume behavior.
"""
from __future__ import annotations

import json

MAX_SUMMARY_BYTES = 8192


def _mapping(value):
    return value if type(value) is dict else {}


def _text(value, limit=256):
    """Bound the JSON-encoded scalar, including escapes, without large reprs."""
    if type(value) is not str:
        return None
    prefix = value[:limit]
    if len(value) <= limit and len(json.dumps(prefix, ensure_ascii=True)) <= limit:
        return prefix
    marker = "...[truncated]"
    low, high = 0, len(prefix)
    while low < high:
        middle = (low + high + 1) // 2
        if len(json.dumps(prefix[:middle] + marker, ensure_ascii=True)) <= limit:
            low = middle
        else:
            high = middle - 1
    return prefix[:low] + marker


def _count(value):
    return value if type(value) is int and 0 <= value <= 2**63 - 1 else None


def _flag(value):
    return value if type(value) is bool else None


def _sha(value):
    return (value if type(value) is str and len(value) == 64
            and all(c in "0123456789abcdef" for c in value) else None)


def _error(value):
    error = _mapping(value)
    return {"type": _text(error.get("type"), 128),
            "message": _text(error.get("message"), 512)}


def render(result):
    """Return at most 8 KiB of ASCII JSON, selecting only bounded fields.

    A completed resume is a no-op and returns a compact ledger as its report;
    unavailable prior session/gate/archive facts remain null, not inferred.
    """
    result = _mapping(result)
    report = _mapping(result.get("report"))
    model = _mapping(report.get("model"))
    ledger = _mapping(report.get("final_accounting"))
    if not ledger:
        ledger = _mapping(report.get("ledger"))
    if not ledger and result.get("resumed_noop") is True:
        ledger = report
    charged = _mapping(ledger.get("charged"))
    processes = _mapping(report.get("processes"))
    archive = _mapping(result.get("archive"))
    root, session = result.get("output_root"), result.get("session_id")
    report_path = None
    if (type(root) is str and len(root) <= 4096 and type(session) is str
            and 1 <= len(session) <= 64 and session.isascii()
            and session.replace("-", "").isalnum()):
        report_path = root.rstrip("/") + "/stages/summary-" + session + ".json"
    summary = {
        "format": "irisx/consolidated-terminal-summary-v1",
        "status": _text(result.get("status"), 128),
        "profile": _text(report.get("profile"), 64),
        "resumed_noop": result.get("resumed_noop") is True,
        "gate_passed": _flag(_mapping(report.get("gate")).get("passed")),
        "coverage_complete": _flag(_mapping(report.get("coverage")).get("complete")),
        "controls_all_expected": _flag(_mapping(report.get("controls")).get("all_expected")),
        "cpu_checks_charged": _count(charged.get("cpu_checks")),
        "coverage_checks_charged": _count(charged.get("coverage_checks")),
        "model_calls_charged": _count(charged.get("physical_calls")),
        "model_status": _text(model.get("status"), 128),
        "workflow_error": _error(report.get("error")),
        "model_error": _error(model.get("error")),
        "model_owner_stopped": _flag(processes.get("model_owner_stopped")),
        "verifier_descendants_stopped": _flag(processes.get("verifier_descendants_stopped")),
        "global_seal": _text(report.get("global_seal")),
        "output_root": _text(root, 768),
        "report_path": _text(report_path, 1024),
        "archive_path": _text(archive.get("archive"), 1024),
        "archive_sha256": _sha(archive.get("sha256")),
        "source_sha256": _sha(report.get("source_sha256")),
        "details": "Full details remain in output-root stage, journal, response and archive files. Display text may be truncated.",
        "billing": "Program return and archive completion do not stop VM billing. Stop the owner-managed VM separately.",
    }
    rendered = json.dumps(summary, sort_keys=True, ensure_ascii=True, indent=2)
    # The allowlist and scalar bounds above stay below this independent ceiling.
    # Fail to a fixed tiny message if later schema edits accidentally exceed it.
    if len(rendered) + 1 > MAX_SUMMARY_BYTES:
        return '{"status":"summary_limit_exceeded","details":"Inspect the retained on-disk evidence; VM billing is not stopped."}'
    return rendered
