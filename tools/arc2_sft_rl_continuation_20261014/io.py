"""Bounded local JSON and explicit report links. No ambient or provider access."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile

MAX_JSON_BYTES = 16 * 1024 * 1024


class InputError(ValueError):
    """A fixed diagnostic code, with no private input content attached."""


def require(condition, code):
    if not condition:
        raise InputError(code)


def safe_path(path):
    path = Path(path).absolute()
    require(".." not in path.parts, "path_traversal")
    require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink_path")
    return path


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_json(path, expected_sha256):
    """Expected hashes detect changed local bytes; they do not attest provenance."""
    require(type(expected_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", expected_sha256), "expected_sha256")
    path = safe_path(path)
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "regular_single_link_input")
    require(0 < before.st_size <= MAX_JSON_BYTES, "input_size")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        require(_identity(before) == _identity(os.fstat(stream.fileno())), "input_replaced")
        raw = stream.read(MAX_JSON_BYTES + 1)
        require(_identity(before) == _identity(os.fstat(stream.fileno())), "input_changed")
    require(_identity(before) == _identity(path.stat()), "input_changed")
    require(len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == expected_sha256, "input_hash")

    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def number(value):
        result = float(value)
        require(math.isfinite(result), "nonfinite_json")
        return result

    def constant(_value):
        raise InputError("nonfinite_json")

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_float=number, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise InputError("invalid_json") from None
    require(type(value) is dict, "json_object_required")
    return value, {"bytes": len(raw), "sha256": expected_sha256}


def _link(value, descriptor, code):
    # The recorded path is deliberately ignored: only explicitly supplied files
    # may be opened, even if a collector descriptor points somewhere else.
    require(type(value) is dict, code)
    require(type(value.get("bytes")) is int and value["bytes"] == descriptor["bytes"]
            and value.get("sha256") == descriptor["sha256"], code)


def report_links(report, report_descriptor, *, checkpoint=None, checkpoint_descriptor=None,
                 retrieval=None, retrieval_descriptor=None):
    """Check local collector serialization links, without recreating admission."""
    result = {
        "report": report_descriptor,
        "checkpoint": checkpoint_descriptor,
        "retrieval": retrieval_descriptor,
        "local_descriptor_links_consistent": None,
        "external_collection_authenticated": False,
        "recorded_numeric_output_version": None,
    }
    require((checkpoint is None) == (checkpoint_descriptor is None), "checkpoint_arguments")
    require((retrieval is None) == (retrieval_descriptor is None), "retrieval_arguments")
    require(retrieval is None or checkpoint is not None, "retrieval_requires_checkpoint")
    if checkpoint is None:
        return result
    require(checkpoint.get("status") == "TERMINAL_EVIDENCE_VERIFIED", "checkpoint_status")
    _link(checkpoint.get("validation"), report_descriptor, "checkpoint_validation_link")
    require(checkpoint.get("provider_status") == report.get("provider_status"), "checkpoint_provider_status")
    for key in ("operational_success", "comparison_complete", "compute_matched", "comparison_eligible",
                "public_benchmark_evidence_eligible", "goal_met", "public_goal_met"):
        require(type(checkpoint.get(key)) is bool and checkpoint[key] is report.get(key), "checkpoint_axes")
    require(checkpoint.get("automatic_retry") is False, "checkpoint_retry")
    if retrieval is not None:
        _link(checkpoint.get("retrieval"), retrieval_descriptor, "checkpoint_retrieval_link")
        require(retrieval.get("format") == "irisx/rlvr-selected-retrieval-v1", "retrieval_format")
        version = retrieval.get("numeric_output_version")
        require(type(version) is int and version > 0, "retrieval_version")
        before, after = retrieval.get("before"), retrieval.get("after")
        require(type(before) is dict and type(after) is dict, "retrieval_bracket")
        require(before.get("status") == after.get("status") == report.get("provider_status"), "retrieval_bracket")
        require(retrieval.get("inventory_scope") == "selected_outputs_only"
                and retrieval.get("whole_provider_inventory_verified") is False, "retrieval_scope")
        result["recorded_numeric_output_version"] = version
    result["local_descriptor_links_consistent"] = True
    return result


def write_new_json(path, value):
    """Publish one complete local report, refusing overwrite; clean failed temps."""
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    require(len(raw) <= MAX_JSON_BYTES, "output_size")
    path = safe_path(path)
    require(path.parent.is_dir(), "output_parent_missing")
    require(not path.exists(), "output_exists")
    descriptor = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    fd, temporary = tempfile.mkstemp(prefix=".arc2-report-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic exclusive publication: unlike replace(), a competing output is
        # preserved. No report can appear half-written at the requested path.
        os.link(temporary, path)
    finally:
        os.unlink(temporary)
    return descriptor
