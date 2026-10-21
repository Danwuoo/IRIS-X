"""Explicit public-model calibration controller; never executed by imports/tests.

No generation, evaluator import, network call, optimizer, or checkpoint update.
Only this controller's own leaf PID may be terminated. Interrupted raw receipts
are preserved and collected as partial evidence, never silently made complete.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time

from tools.public_sft141_diagnostic.model_pins import verify_model
from tools.public_sft141_diagnostic.model_worker import Artifacts, Deadline, TransformersBackend
from .core import calibration_bundle, cases, digest, prepare, validate_calibration, validate_gold_free
from .runtime import collect


PUBLIC_PLAN_SHA256 = "cc795e7475cb689714b34fb5f10802c23f51a2534dcf50121774a56750c31069"


def admit_public_plan(plan):
    """The real runtime cannot replace the independently frozen public panel."""
    validate_gold_free(plan)
    if digest(plan) != PUBLIC_PLAN_SHA256:
        raise ValueError("real calibration requires the exact frozen public 12-parent/15-query plan")
    return PUBLIC_PLAN_SHA256


def inherited_deadline(seconds, started):
    deadline = Deadline(seconds)
    if not isinstance(started, (float, int)) or not 0 <= started <= deadline.start:
        raise ValueError("invalid original monotonic start")
    deadline.start = started
    deadline.end = started + seconds
    deadline.work_end = deadline.end - deadline.reserve
    return deadline


def source_identity():
    """Bind our source plus the unchanged public codec/backend/model pins."""
    import hashlib
    from tools.public_sft141_diagnostic import contract, model_worker, model_pins
    paths = list(Path(__file__).parent.glob("*.py")) + [Path(m.__file__) for m in (contract, model_worker, model_pins)]
    return {str(p.relative_to(Path(__file__).resolve().parents[2])):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def worker(plan, model_dir, output, seconds, started, session_id):
    deadline = inherited_deadline(seconds, started)
    admit_public_plan(plan)
    artifacts = Artifacts(output)
    rows = []
    try:
        schedule = prepare(plan, 8192, seconds)
        if not schedule["context_admitted"]:
            raise ValueError("full-context preflight failed before model loading")
        deadline.check()
        verification = verify_model(model_dir)
        artifacts.write("model_verification.json", verification)
        artifacts.write("source_identity.json", source_identity())
        deadline.check()
        if not cases(plan):
            bundle = calibration_bundle(plan, [], kind="public_model", session_id=session_id)
            artifacts.write("calibration.json", bundle)
            artifacts.write("closure.json", {"status": "complete", "reason": "single-demo-only panel; no calibration or model load",
                "real_model_executed": False, "budget": deadline.receipt()})
            return 0
        backend = TransformersBackend(model_dir, plan, deadline, artifacts)
        artifacts.write("backend.json", backend.metadata)
        # Validate the actual pinned tokenizer on every LOO prompt/answer too.
        from tools.public_sft141_diagnostic import contract
        parents = {p["task_id"]: p for p in plan["parents"]}
        for spec, prompt, answer in cases(plan):
            deadline.check()
            parent = parents[spec["task_id"]]
            train = parent["train"]
            held, view = spec["held_support_index"], spec["view"]
            text = contract.prompt_text([train[i] for i in spec["conditioned_support_indices"]], train[held]["input"], view)
            target = contract.grid_text(contract.transform(train[held]["output"], view)) + "<|im_end|>"
            if (backend.tokenizer.encode(text, add_special_tokens=False) != prompt or
                    backend.tokenizer.encode(target, add_special_tokens=False) != answer):
                raise ValueError("actual tokenizer does not match every LOO prompt and EOS target")
        result = collect(plan, backend, output, deadline, execution_kind="public_model", session_id=session_id,
                         public_verification=verification, artifacts=artifacts)
        return 0 if result["status"] == "complete" else 2
    except Exception as exc:
        # If collect already closed, do not replace any existing result.
        if not (Path(output) / "calibration.json").exists():
            bundle = calibration_bundle(plan, rows, kind="public_model", session_id=session_id, status="partial")
            artifacts.write("calibration.json", bundle)
        artifacts.write("worker_failure.json", {"type": type(exc).__name__, "message": str(exc), "budget": deadline.receipt()})
        return 2


def reconcile_receipts(plan, session_id, raw, bundle):
    """Atomic per-forward receipts are authoritative for interrupted accounting.

    Aggregate disagreement can never promote. Preserve the original aggregate
    on disk, return a new partial view of validated raw evidence, and disclose
    that any unsaved forward costs remain unknown.
    """
    recovered = calibration_bundle(plan, raw, kind="public_model", session_id=session_id,
        completed_event=max((r["event"] for r in raw), default=-1) + 1, status="partial")
    validate_calibration(plan, recovered)
    if bundle is None:
        return recovered, False
    validate_calibration(plan, bundle)
    if bundle["session_id"] != session_id or bundle["execution_kind"] != "public_model":
        raise ValueError("worker aggregate does not belong to the owned public-model session")
    consistent = digest(raw) == digest(bundle["rows"])
    return (bundle if consistent else recovered), consistent


def run(plan, plan_path, plan_file_sha256, model_dir, output, seconds=7200):
    """Explicit CLI action. Includes preparation/load/forwards in one wall clock."""
    started = time.monotonic()
    deadline = inherited_deadline(seconds, started)
    admit_public_plan(plan)
    schedule = prepare(plan, 8192, seconds)
    artifacts = Artifacts(output)
    artifacts.write("schedule.json", schedule)
    session_id = f"demo-calibration-{time.time_ns()}"
    sources = source_identity()
    artifacts.write("intent.json", {"session_id": session_id, "plan_sha256": digest(plan),
        "plan_file_sha256": plan_file_sha256, "started_monotonic": started,
        "budget_seconds": seconds, "source_identity": sources,
        "run_scope": "calibration-only; paired generation/evaluation not executed", "resume_supported": False})
    if not schedule["context_admitted"]:
        artifacts.write("closure.json", {"status": "context_admission_failed", "forward_calls": 0,
            "real_model_executed": False, "budget": deadline.receipt()})
        return 2
    command = [sys.executable, "-m", "tools.public_demo_calibration", "_calibration-worker",
               "--plan", str(Path(plan_path).resolve()), "--plan-sha256", plan_file_sha256,
               "--model-dir", str(Path(model_dir).resolve()), "--output", str(Path(output).resolve() / "worker"),
               "--budget-seconds", str(seconds), "--started-monotonic", str(started), "--session-id", session_id]
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_DATASETS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    timed_out, process = False, None
    with (Path(output) / "worker.log").open("xb") as log:
        try:
            deadline.check()
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env,
                                       cwd=Path(__file__).resolve().parents[2])
            try:
                rc = process.wait(timeout=deadline.work_remaining())
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                rc = process.wait(timeout=min(5, max(.1, deadline.remaining())))
        except BaseException:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            raise
    # The original deadline cannot be reset by CLI replay or leaf failure.
    from .__main__ import read_frozen
    import hashlib
    raw = []
    for path in sorted((Path(output) / "worker" / "receipts").glob("loo-*.json")):
        data = path.read_bytes()
        raw.append(read_frozen(path, hashlib.sha256(data).hexdigest()))
    result_path = Path(output) / "worker" / "calibration.json"
    if result_path.exists():
        data = result_path.read_bytes()
        bundle = read_frozen(result_path, hashlib.sha256(data).hexdigest())
    else:
        bundle = None
    bundle, receipts_consistent = reconcile_receipts(plan, session_id, raw, bundle)
    complete = rc == 0 and not timed_out and receipts_consistent and not deadline.expired() and bundle["status"] == "complete"
    if not complete:
        bundle = dict(bundle, status="partial")
    if source_identity() != sources:
        complete = False
        bundle = dict(bundle, status="partial")
    artifacts.write("calibration.json", bundle)  # Fresh controller-owned immutable copy.
    artifacts.write("closure.json", {"status": "complete" if complete else "partial",
        "worker_returncode": rc, "worker_timed_out": timed_out,
        "worker_exited": process.poll() is not None, "budget": deadline.receipt(),
        "aggregate_matches_atomic_receipts": receipts_consistent,
        "raw_receipt_count": len(raw), "unknown_unsaved_forward_cost_possible": not complete,
        "calibration_sha256": digest(bundle), "source_unchanged": source_identity() == sources,
        "real_model_success_requires_worker_receipts": True, "scientific_effectiveness_established": False,
        "paired_generation_or_evaluation_executed": False})
    return 0 if complete else 2
