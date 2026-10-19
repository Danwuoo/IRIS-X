"""Task-local identities and crash-safe records; no provider imports."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


SCORING_HASH_KEYS = ("source_sha256", "protocol_semantic_sha256", "panel_semantic_sha256",
                     "model_spec_sha256", "verifier_spec_sha256")

MODEL_COST_COUNTS = frozenset({"prompt_tokens", "output_tokens", "consumed_prompt_tokens"})
MODEL_COST_TIMES = frozenset({"wall_seconds", "cold_compile_seconds", "cache_allocation_seconds",
                              "prefill_seconds", "decode_seconds"})
MODEL_COST_REQUIRED = frozenset({"prompt_tokens", "output_tokens", "wall_seconds"})


def nonnegative_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def nonnegative_seconds(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_model_cost(cost, *, force_partial=False):
    """Validate raw receipts independently at ingestion and analysis.

    Never coerce invalid values or replace missing fields with zero. The caller
    retains the original receipt; valid, recognized fields alone form a measured
    lower bound. Optional fields, when present, must satisfy the same schema.
    Unknown fields need an explicit schema update, not silent aggregation.
    """
    issues, observed = [], {}
    if not isinstance(cost, dict):
        issues.append({"field": "<receipt>", "reason": "not_an_object"})
        cost = {}
    for name in sorted(MODEL_COST_REQUIRED - cost.keys()):
        issues.append({"field": name, "reason": "missing"})
    for name, value in cost.items():
        if name in MODEL_COST_COUNTS:
            valid = nonnegative_count(value)
            reason = "requires_nonbool_nonnegative_integer"
        elif name in MODEL_COST_TIMES:
            valid = nonnegative_seconds(value)
            reason = "requires_finite_nonbool_nonnegative_number"
        elif name == "partial":
            if not isinstance(value, bool):
                issues.append({"field": name, "reason": "requires_boolean"})
            continue
        else:
            issues.append({"field": str(name), "reason": "unknown_field"})
            continue
        if valid:
            observed[name] = value
        else:
            issues.append({"field": name, "reason": reason})
    if ("consumed_prompt_tokens" in observed and "prompt_tokens" in observed
            and observed["consumed_prompt_tokens"] > observed["prompt_tokens"]):
        issues.append({"field": "consumed_prompt_tokens", "reason": "exceeds_prompt_tokens"})
        del observed["consumed_prompt_tokens"]
    partial = cost.get("partial") is True or force_partial
    return {"format": "irisx.math.model-cost-check.v1", "complete": not issues and not partial,
            "partial": partial, "issues": issues, "observed_lower_bound": observed}


def validate_scoring_identity(identity):
    """Scoring semantic hashes are distinct from the smoke's raw file manifest."""
    if not isinstance(identity, dict) or identity.get("format") != "irisx.math.scoring-identity.v1":
        raise ValueError("complete scoring identity required")
    for key, length in [("code_sha", 40), *((key, 64) for key in SCORING_HASH_KEYS)]:
        if not isinstance(identity.get(key), str) or not re.fullmatch("[0-9a-f]{%d}" % length, identity[key]):
            raise ValueError("missing or malformed scoring identity: " + key)
    return identity


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


class Lock:
    """Exclusive task lock. A stale lock is evidence, never silently removed."""
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(self.fd, json.dumps({"pid": os.getpid(), "created": time.time()}).encode())
        os.fsync(self.fd)
        return self

    def __exit__(self, *_):
        os.close(self.fd)
        self.path.unlink()


def python_environment(inherited=None):
    # Same controlled startup semantics as WSF-R5; no -I/-E.
    env = {k: v for k, v in (os.environ if inherited is None else inherited).items()
           if not k.upper().startswith("PYTHON")}
    env.update(PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    return env
