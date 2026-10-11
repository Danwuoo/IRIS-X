"""Bounded, source-capable program tools; no candidate is host-executed.

The existing demos verifier and source-capable query verifier are byte-pinned.
Query execution deliberately replays demos in the unchanged query verifier,
sharing its 200,000-gas ceiling across demos and the query. This stricter replay
can exclude a previously fitted program; it never bypasses a demo-fit gate.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from tools.arc_consolidated_20261010 import verifier as legacy
from tools.arc_next_suite_20261009.src import arc_program_v2 as source_verifier

VERIFIER_SHA256 = "072c4133b63e05c09509fa9f5734a4dae4f7065f8bdb2cc5483b6468e189368b"
QUERY_VERIFIER_SHA256 = "52bc22ffdf32198ceee209b68f68840869086af7d4372e54ec7d7b0297fe760d"
TRANSPORT_KEYS = {"dispatched", "gas_reserved", "owned_descendants_stopped", "gas_charged", "wall_reserved_seconds", "wall_seconds"}
FORMAT = "irisx/learning-program-proof-v1"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _source_hash(text):
    return hashlib.sha256(text.encode("utf-8", "strict")).hexdigest()


def _write(path, value):
    with Path(path).open("xb") as handle:
        handle.write(_canonical(value) + b"\n")


def _root(output_dir, call_id):
    if type(call_id) is not str or re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", call_id) is None or call_id in {".", ".."}:
        raise ValueError("safe unique call_id required")
    root = Path(output_dir) / call_id
    root.mkdir(parents=True, exist_ok=False)
    return root


def _pins():
    for module, pin in ((legacy, VERIFIER_SHA256), (source_verifier, QUERY_VERIFIER_SHA256)):
        if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != pin:
            raise ValueError("unchanged verifier hash mismatch")
    legacy._check_assets()


def _remaining(deadline):
    if deadline is None:
        return legacy.MAX_WALL_SECONDS
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ValueError("finite monotonic deadline required")
    return min(legacy.MAX_WALL_SECONDS, max(0.0, deadline - time.monotonic()))


def _partial(receipt, demos):
    rows = receipt.get("demos", [])
    matches = sum(row.get("status") == "match" for row in rows)
    errors = []
    for row in rows:
        if row.get("status") != "match":
            errors.append({key: row.get(key) for key in ("index", "status", "reason", "expected_shape", "actual_shape", "mismatch_count", "mismatch_samples")})
    cells = sum(len(pair["output"]) * len(pair["output"][0]) for pair in demos)
    mismatches = sum(row.get("mismatch_count") if type(row.get("mismatch_count")) is int else
                     len(demos[index]["output"]) * len(demos[index]["output"][0])
                     for index, row in enumerate(rows))
    # Admission failures contain no reliable positive cell evidence.
    cell_agreement = max(0, cells - mismatches) / cells if len(rows) == len(demos) and cells else 0.0
    return {"exact_demos": matches, "demo_count": len(demos), "exact_fraction": matches / len(demos),
            "cell_agreement": cell_agreement}, errors


def verify_program(text, demos, output_dir, call_id, *, deadline=None):
    """Persist reservation and a byte-bound demos-only proof; tool errors are data."""
    started = time.monotonic()
    root = _root(output_dir, call_id)
    task = legacy.validate_task({"task_id": call_id, "demos": demos})
    timeout = _remaining(deadline)
    _write(root / "reservation.json", {"call_id": call_id, "operation": "demo_verify", "timeout": timeout,
                                      "source_sha256": _source_hash(text) if type(text) is str else None})
    try:
        _pins()
        if timeout <= 0:
            receipt = legacy._result("unavailable", "task deadline exhausted")
            receipt.update(dispatched=False, gas_reserved=0, gas_charged=0, owned_descendants_stopped=True,
                           wall_reserved_seconds=0.0, wall_seconds=0.0)
        else:
            receipt = legacy.verify(text, task, timeout=timeout)
    except (ValueError, OSError, UnicodeError) as exc:
        receipt = legacy._result("unavailable", str(exc))
        receipt.update(dispatched=False, gas_reserved=0, gas_charged=0, owned_descendants_stopped=True,
                       wall_reserved_seconds=0.0, wall_seconds=0.0)
    score, errors = _partial(receipt, task["demos"])
    if receipt["status"] != "fit" and not errors:
        errors = [{"status": receipt["status"], "reason": receipt["reason"]}]
    proof = {"format": FORMAT, "call_id": call_id, "source": text if type(text) is str else "",
             "source_sha256": _source_hash(text) if type(text) is str else None,
             "demos": task["demos"], "demo_task": task, "receipt": receipt,
             "all_demos_fit": receipt["all_demos_fit"] is True and receipt["known"] is True,
             "partial_score": score, "errors": errors, "gas_charged": receipt["gas_charged"],
             "elapsed_seconds": time.monotonic() - started}
    _write(root / "proof.json", proof)
    return {**proof, "proof_path": str((root / "proof.json").resolve()), "proof_sha256": _hash(proof)}


def _checked_proof(candidate):
    if type(candidate) is not dict:
        raise ValueError("verified candidate required")
    proof = {key: value for key, value in candidate.items() if key not in {"proof_path", "proof_sha256"}}
    if candidate.get("proof_sha256") != _hash(proof):
        raise ValueError("demo proof binding differs")
    data = Path(candidate["proof_path"]).read_bytes()
    if len(data) > 256 * 1024 or data != _canonical(proof) + b"\n":
        raise ValueError("persisted demo proof differs")
    if proof.get("format") != FORMAT or proof.get("all_demos_fit") is not True:
        raise ValueError("all-demo-fit proof required before query execution")
    if proof.get("source_sha256") != _source_hash(proof["source"]):
        raise ValueError("source proof binding differs")
    receipt = proof["receipt"]
    request = legacy._validate_request(proof["source"], proof["demo_task"], legacy.MAX_WALL_SECONDS, legacy.MAX_STEPS)
    legacy._validate_receipt({k: v for k, v in receipt.items() if k not in TRANSPORT_KEYS}, request)
    if (proof["demos"] != proof["demo_task"]["demos"] or receipt["status"] != "fit" or
            receipt["dispatched"] is not True or receipt["owned_descendants_stopped"] is not True or
            receipt["gas_reserved"] != legacy.MAX_STEPS or receipt["gas_charged"] != receipt["gas"]):
        raise ValueError("fresh closed all-demo-fit verification required")
    return proof


def _query_one(source, demos, query, root, deadline):
    root.mkdir()
    task = {"train": demos, "test": [{"input": query}]}
    request = {"source": source, "task": task}
    payload = _canonical(request)
    if len(payload) > source_verifier.MAX_INPUT_BYTES:
        raise ValueError("query request byte limit")
    _write(root / "request.json", request)
    timeout = _remaining(deadline)
    _write(root / "reservation.json", {"request_sha256": _hash(request), "timeout": timeout,
                                      "gas": legacy.MAX_STEPS if timeout else 0})
    began = time.monotonic()
    row = {"request_sha256": _hash(request), "input_sha256": _hash(query), "status": "missing", "output": None,
           "gas": None, "gas_charged": 0, "dispatched": False, "owned_descendants_stopped": True,
           "process_pid": None, "process_returncode": None, "reason": "deadline exhausted", "verifier": None}
    process = None
    if timeout > 0:
        try:
            with (root / "request.json").open("rb") as incoming, (root / "response.json").open("xb") as outgoing, \
                    (root / "stderr.txt").open("xb") as errors:
                process = subprocess.Popen([sys.executable, "-I", "-B", "-S", str(Path(source_verifier.__file__).resolve()),
                                            "--worker", str(legacy.ASSET_DIRECTORY / "arc_bounded_v2.py")],
                                           stdin=incoming, stdout=outgoing, stderr=errors, cwd=root,
                                           close_fds=True, start_new_session=True,
                                           env={**os.environ, "CUDA_VISIBLE_DEVICES": "", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
                row.update(dispatched=True, process_pid=process.pid, gas_charged=legacy.MAX_STEPS,
                           owned_descendants_stopped=False, reason="worker receipt unavailable")
                try:
                    process.wait(timeout=max(.001, timeout - (time.monotonic() - began)))
                except subprocess.TimeoutExpired:
                    legacy._terminate(process)
                    row["reason"] = "query wall deadline; killed and reaped"
                finally:
                    if process.poll() is None:
                        legacy._terminate(process)
                    else:
                        process.wait()
                    row.update(owned_descendants_stopped=True, process_returncode=process.returncode)
            if process.returncode == 0:
                with (root / "response.json").open("rb") as response_file:
                    raw = response_file.read(source_verifier.MAX_OUTPUT_BYTES + 1)
                progress, final = source_verifier._decode_records(raw)
                if final is None or not source_verifier._result_binds_task(final, task):
                    raise ValueError("unbound or incomplete query receipt")
                row.update(verifier=final, gas=final["program_steps"], gas_charged=final["program_steps"],
                           status="valid" if final["query_execution_success"] else "invalid",
                           output=final["candidate"] if final["query_execution_success"] else None,
                           reason=final["error_category"] or "valid grid")
        except (ValueError, OSError, UnicodeError, RecursionError) as exc:
            row["reason"] = ("query transport: " + str(exc))[:160]
    row["elapsed_seconds"] = time.monotonic() - began
    _write(root / "receipt.json", row)
    return row


def execute_queries(verified_candidate, query_inputs, output_dir, call_id, *, deadline=None):
    """Only byte-bound fitted source enters the unchanged query verifier process."""
    root = _root(output_dir, call_id)
    started = time.monotonic()
    results, error = [], None
    try:
        _pins()
        if not legacy.capability()["available"]:
            raise ValueError("Linux resource controls required; no fallback")
        proof = _checked_proof(verified_candidate)
        if type(query_inputs) is not list or not 1 <= len(query_inputs) <= 10:
            raise ValueError("expected 1..10 query inputs")
        inputs = [legacy._grid(value) for value in query_inputs]
        for index, query in enumerate(inputs):
            results.append(_query_one(proof["source"], proof["demos"], query, root / ("query-%03d" % index), deadline))
    except (ValueError, OSError, KeyError, UnicodeError, RecursionError) as exc:
        error = str(exc)[:160]
    result = {"call_id": call_id, "results": results, "error": error,
              "query_count": len(results), "dispatched": sum(row["dispatched"] for row in results),
              "gas_charged": sum(row["gas_charged"] for row in results),
              "owned_descendants_stopped": all(row["owned_descendants_stopped"] for row in results),
              "elapsed_seconds": time.monotonic() - started,
              "limits": legacy.known_limits(), "demo_replay_in_each_query": True}
    _write(root / "receipt.json", result)
    return result
