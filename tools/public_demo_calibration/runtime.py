"""Sequential, injectable calibration harness for the explicit owned-leaf CLI.

The CLI controller owns a killable calibration leaf and the original
whole-session deadline. Cooperative checks alone cannot interrupt a hung
accelerator forward. Later paired generation/evaluation needs its own shared
whole-session controller; this calibration-only command does not claim that.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.public_sft141_diagnostic.model_worker import Artifacts, full_answer_nll
from .core import (calibration_bundle, cases, complete_row, digest, prepare,
                   validate_calibration, MODEL_IDENTITY)


def masked_token_mean_nll(logits: Any, prompt_length: int, answer: list[int]) -> float:
    """Real tensor causal loss; prompt/padding excluded, full answer/EOS included."""
    return full_answer_nll(logits, prompt_length, answer) / len(answer)


def _versions(backend: Any) -> list[tuple] | None:
    model = getattr(backend, "model", None)
    if model is None:
        return None
    if model.training:
        raise ValueError("calibration requires an eval-mode immutable model")
    return [(kind, name, tuple(t.shape), str(t.dtype), str(t.device), t.data_ptr(), t._version)
            for kind, values in (("parameter", model.named_parameters()),
                                 ("buffer", model.named_buffers())) for name, t in values]


def collect(plan: dict, backend: Any, output: str | Path, deadline: Any, *,
            execution_kind: str = "synthetic_cpu", session_id: str = "synthetic",
            public_verification: dict | None = None, artifacts: Any = None) -> dict:
    """Use backend.score sequentially, save every attempted operation, never train.

    `deadline` is inherited from the controller BEFORE loading, not reset here.
    Failed forward costs remain unknown, rather than reporting free failures.
    No token cropping, support filtering, model loading or generation occurs.
    """
    if execution_kind not in ("synthetic_cpu", "public_model"):
        raise ValueError("unknown execution kind")
    if execution_kind == "public_model":
        if (not isinstance(public_verification, dict) or
                public_verification.get("handle") != MODEL_IDENTITY["handle"] or
                public_verification.get("files") != MODEL_IDENTITY["files"] or
                getattr(backend, "model", None) is None):
            raise ValueError("real calibration requires verified exact public model files and a loaded model")
    model = getattr(backend, "model", None)
    if model is not None:
        for parameter in model.parameters():
            parameter.requires_grad_(False)
    schedule = prepare(plan, backend.max_context, deadline.seconds)
    artifacts = artifacts or Artifacts(output)
    artifacts.write("plan.json", schedule)
    snapshot = _versions(backend)
    artifacts.write("start.json", {"execution_kind": execution_kind,
        "model_version_snapshot_sha256": digest(snapshot), "budget": deadline.receipt(),
        "sequential": True, "batch_size": 1, "use_cache": False, "optimizer": None,
        "version_guard_is_not_cryptographic_parameter_attestation": True})
    rows, event, status, error = [], 0, "complete", None
    if not schedule["context_admitted"]:
        status, error = "partial", "full-context admission failed; no forward started"
    else:
        for spec, prompt, answer in cases(plan):
            started = deadline.clock()
            try:
                deadline.check()
                if _versions(backend) != snapshot:
                    raise ValueError("model state changed before calibration")
                result = backend.score(prompt, answer, deadline)
                row = complete_row(spec, result["nll"], result["seconds"], event, result.get("memory"))
                # Require the actual backend to report what it processed.
                if result.get("input_tokens") != spec["input_tokens"] or result.get("answer_tokens") != spec["answer_tokens"]:
                    raise ValueError("backend full-answer token counts differ from plan")
                if result.get("batch_size") != 1 or result.get("use_cache") is not False:
                    raise ValueError("backend must report batch-one cache-free teacher forcing")
                check = calibration_bundle(plan, [row], session_id=session_id, kind=execution_kind,
                                           completed_event=event + 1, status="partial")
                validate_calibration(plan, check)
                if _versions(backend) != snapshot:
                    raise ValueError("model parameters or buffers mutated during calibration")
                rows.append(row)
                artifacts.write(f"receipts/loo-{event:05d}.json", row)
                event += 1
                deadline.check()  # A late completion cannot promote calibration.
            except Exception as exc:
                status, error = "partial", f"{type(exc).__name__}: {exc}"
                # If the successful row was already saved, preserve it unchanged.
                if not rows or rows[-1]["spec"]["case_id"] != spec["case_id"]:
                    row = {"spec": spec, "status": "failed", "nll_sum": None,
                        "seconds": max(0., deadline.clock() - started), "event": event,
                        "forward_calls": None, "actual_input_tokens": None,
                        "actual_answer_tokens": None, "memory": None}
                    rows.append(row)
                    artifacts.write(f"receipts/loo-{event:05d}.json", row)
                    event += 1
                break
    bundle = calibration_bundle(plan, rows, session_id=session_id, kind=execution_kind,
                                completed_event=event, status=status)
    validate_calibration(plan, bundle)
    artifacts.write("calibration.json", bundle)
    artifacts.write("closure.json", {"status": status, "error": error,
        "budget": deadline.receipt(), "context_admitted": schedule["context_admitted"],
        "calibration_sha256": digest(bundle), "real_model_executed": execution_kind == "public_model" and any(r["status"] == "complete" for r in rows),
        "model_version_snapshot_sha256": digest(_versions(backend)),
        "capability_evidence": False, "hard_watchdog_owned_by_caller": True})
    return bundle
