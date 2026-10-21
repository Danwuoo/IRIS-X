"""Post-exit raw reconstruction and original-clock Linux controller."""
from __future__ import annotations
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from tools.public_sft141_diagnostic import model_pins
from tools.public_sft141_submission import contract as wire, files
from tools.public_sft141_solver.controller import (mkdir_exclusive, process_table, Ownership, subreaper, safe_cleanup, WorkerLog)
from . import core

def _seal_files(root):
    names = ["challenge.json", "plan.json", "dispatch.json", "controller_exit.json"]
    allowed = {"inventory.json", "identity.json", "model_identity.json", "environment.json",
               "load_preflight.json", "backend.json", "context_admission.json", "model_state_before.json",
               "load_start.json", "load_end.json", "calibration_freeze.json",
               "model_state_after.json", "terminal.json"}
    if (root / "worker.log").exists():
        names.append("worker.log")
    worker = root / "worker"
    if worker.exists():
        if worker.is_symlink() or not worker.is_dir():
            raise ValueError("worker evidence must be a real directory")
        for entry in worker.iterdir():
            if entry.name == "receipts":
                if entry.is_symlink() or not entry.is_dir():
                    raise ValueError("receipts must be a real directory")
                names.extend(str(p.relative_to(root)) for p in entry.iterdir() if not p.name.startswith("."))
            elif not entry.name.startswith("."):
                if entry.name not in allowed:
                    raise ValueError("unexpected committed worker artifact")
                names.append(str(entry.relative_to(root)))
    return {name: wire.digest(files.read_bytes(root / name)) for name in sorted(names)}


def seal_exited(root):
    exit_row, _ = files.load_json(root / "controller_exit.json")
    if exit_row["worker_dispatched"] and (not exit_row["worker_exited"] or not exit_row["cleanup"]["complete"]):
        raise ValueError("cannot seal while the owned worker or descendants remain")
    seal = {"schema": core.SCHEMA, "worker_dispatched": exit_row["worker_dispatched"],
            "worker_exited": exit_row["worker_exited"], "files": _seal_files(root),
            "seal_is_authentication": False, "qualification": "Local byte-integrity binding, not a signature or independent attestation."}
    core.publish(root / "exited_seal.json", seal)
    return seal


def validate_budget(value, dispatch):
    wire.exact_fields(value, {"original_start_monotonic", "budget_seconds", "elapsed_seconds",
                             "remaining_seconds", "closure_reserve_seconds", "resume_supported"}, "budget receipt")
    original = core.SharedDeadline(dispatch["start_monotonic"], dispatch["budget_seconds"])
    for key in ("original_start_monotonic", "budget_seconds", "elapsed_seconds", "remaining_seconds", "closure_reserve_seconds"):
        if not core._finite(value[key]):
            raise ValueError("budget receipt contains invalid numerical fields")
    if (value["original_start_monotonic"] != original.start or value["budget_seconds"] != original.seconds
            or value["closure_reserve_seconds"] != original.reserve or value["resume_supported"] is not False
            or abs(value["remaining_seconds"] - max(0., original.seconds - value["elapsed_seconds"])) > .1):
        raise ValueError("budget receipt differs from original clock")

def read_replay(root):
    seal, seal_raw = files.load_json(root / "exited_seal.json")
    wire.exact_fields(seal, {"schema", "worker_dispatched", "worker_exited", "files",
                             "seal_is_authentication", "qualification"}, "exited seal")
    if seal["schema"] != core.SCHEMA or seal["seal_is_authentication"] is not False or seal["files"] != _seal_files(root):
        raise ValueError("exited seal differs from current raw evidence")
    challenge, challenge_raw = files.load_json(root / "challenge.json")
    plan, plan_raw = files.load_json(root / "plan.json")
    dispatch, _ = files.load_json(root / "dispatch.json")
    exit_row, _ = files.load_json(root / "controller_exit.json")
    core.validate_plan(plan, challenge, wire.digest(challenge_raw))
    validate_budget(exit_row["budget"], dispatch)
    expected_model = {"handle": model_pins.MODEL_HANDLE, "url": model_pins.MODEL_URL,
                      "files": {k: {"bytes": v[0], "sha256": v[1]} for k, v in model_pins.MODEL_FILES.items()}}
    if (dispatch["schema"] != core.SCHEMA or wire.canonical(dispatch["expected_public_model"]) != wire.canonical(expected_model)
            or dispatch["execution_kind"] not in ("public-pinned-model", "synthetic-injected-no-model-evidence")
            or dispatch["fallback"] not in ("fail", "copy-input")
            or type(dispatch["outer_supervised"]) is not bool
            or (dispatch["execution_kind"] == "public-pinned-model" and dispatch["outer_supervised"] is not True)):
        raise ValueError("dispatch does not match pinned public execution contract")
    if dispatch["challenge_sha256"] != wire.digest(challenge_raw):
        raise ValueError("dispatch challenge hash differs from actual original bytes")
    if dispatch["configuration"] != plan["configuration"] or dispatch["budget_seconds"] != plan["configuration"]["budget_seconds"]:
        raise ValueError("dispatch configuration differs from immutable plan")
    original_deadline = core.SharedDeadline(dispatch["start_monotonic"], dispatch["budget_seconds"])
    if dispatch["end_monotonic"] != original_deadline.end or dispatch["work_end_monotonic"] != original_deadline.work_end:
        raise ValueError("dispatch clock does not preserve original whole budget")
    if dispatch["plan_sha256"] != wire.digest(plan_raw) or dispatch["source"] != core.source_identity():
        raise ValueError("current source/plan no longer matches original dispatch")
    if wire.canonical(dispatch["scheduler"]) != wire.canonical(core.SCHEDULER):
        raise ValueError("dispatch scheduler is not the fixed public scheduler")
    if (seal["worker_dispatched"] != exit_row["worker_dispatched"] or
            seal["worker_exited"] != exit_row["worker_exited"] or
            (exit_row["worker_dispatched"] and (not exit_row["worker_exited"] or not exit_row["cleanup"]["complete"]))):
        raise ValueError("worker closure is incomplete")
    records = {Path(name).name: files.load_json(root / name)[0]
               for name in seal["files"] if name.startswith("worker/receipts/")}
    state_guard = "unknown"
    if "worker/model_state_after.json" in seal["files"]:
        state_after, _ = files.load_json(root / "worker/model_state_after.json")
        state_before, _ = files.load_json(root / "worker/model_state_before.json")
        state_guard = "unchanged" if state_after["snapshot"] == state_before else "changed"
        if state_after["status"] == "changed":
            state_guard = "changed"
        if state_after["status"] != state_guard:
            raise ValueError("model state guard evidence is inconsistent")
    if records:
        loaded, _ = files.load_json(root / "worker/load_end.json")
        loading, _ = files.load_json(root / "worker/load_start.json")
        if (type(loaded["model_loads"]) is not int or loaded["model_loads"] != 1
                or type(loading["model_load_attempts"]) is not int or loading["model_load_attempts"] != 1
                or loaded["same_backend_all_stages"] is not True
                or not all(core._finite(loaded[k]) for k in ("started_monotonic", "finished_monotonic", "elapsed_seconds"))
                or loaded["started_monotonic"] != loading["started_monotonic"]
                or not dispatch["start_monotonic"] <= loaded["started_monotonic"] <= loaded["finished_monotonic"] < dispatch["work_end_monotonic"]
                or abs(loaded["elapsed_seconds"] - (loaded["finished_monotonic"] - loaded["started_monotonic"])) > .000001
                or min(r["started_monotonic"] for name, r in records.items() if name.endswith("-start.json")) < loaded["finished_monotonic"]):
            raise ValueError("model load receipt differs from original clock or operation order")
        identity, _ = files.load_json(root / "worker/identity.json")
        if (identity["source"] != dispatch["source"] or identity["plan_sha256"] != dispatch["plan_sha256"]
                or identity["execution_kind"] != dispatch["execution_kind"]
                or identity["pid"] != exit_row["cleanup"]["owned_pgid"]
                or identity["pgid"] != identity["pid"] or identity["session"] != identity["pid"]):
            raise ValueError("worker identity differs from dispatched source/session")
        if dispatch["execution_kind"] == "public-pinned-model":
            model_identity, _ = files.load_json(root / "worker/model_identity.json")
            if model_identity != dispatch["expected_public_model"]:
                raise ValueError("public model receipts do not match exact eight SHA pins")
            native, _ = files.load_json(root / "worker/context_admission.json")
            backend, _ = files.load_json(root / "worker/backend.json")
            configured = dispatch["configuration"]["context_cap"]
            if (native["configured"] != configured or native["native_config_unchanged"] is not True
                    or type(native["verified_native"]) is not int or configured > native["verified_native"]
                    or native["legacy_loader_software_cap"] != 8192
                    or backend["effective_context_cap"] != configured or backend["integration_context"] != native
                    or backend["model_config"]["max_position_embeddings"] != native["verified_native"]
                    or backend["model_class"] != "Qwen3ForCausalLM"):
                raise ValueError("public configured context lacks explicit verified native admission")
    bounds = (dispatch["start_monotonic"], dispatch["work_end_monotonic"],
              dispatch["start_monotonic"] + exit_row["budget"]["elapsed_seconds"])
    freeze = files.load_json(root / "worker/calibration_freeze.json")[0] if "worker/calibration_freeze.json" in seal["files"] else None
    analysis, selections = core.reconstruct(plan, records, freeze=freeze,
                                            state_guard=state_guard, timing_bounds=bounds)
    terminal = {"status": "missing-terminal-not-clean", "model_load_cost_unknown": True}
    if "worker/terminal.json" in seal["files"]:
        terminal, _ = files.load_json(root / "worker/terminal.json")
        validate_budget(terminal["budget"], dispatch)
    complete = (analysis["calibration_complete"] and analysis["generation_complete"] and analysis["nll_complete"]
        and state_guard == "unchanged" and exit_row["returncode"] == 0
        and exit_row["stop_reason"] == "worker-exited" and terminal["status"] == "all-phases-returned"
        and exit_row["budget"]["elapsed_seconds"] < dispatch["budget_seconds"])
    analysis.update({"protocol_complete": complete,
        "generation_protocol_complete": complete and dispatch["execution_kind"] == "public-pinned-model",
        "accuracy_established": False, "worker_terminal": terminal, "execution_kind": dispatch["execution_kind"],
        "worker_returncode": exit_row["returncode"], "controller_stop_reason": exit_row["stop_reason"],
        "configuration": plan["configuration"]})
    if "worker/inventory.json" in seal["files"]:
        actual, _ = files.load_json(root / "worker/inventory.json")
        if actual != core.prepare(plan):
            raise ValueError("worker inventory differs from independently rebuilt complete challenge")
    return challenge, dispatch, analysis, selections, wire.digest(seal_raw)


def prepare_bundle(root):
    challenge, dispatch, analysis, selections, seal_hash = read_replay(root)
    submission, counts, modes = wire.build_submission(challenge, selections[dispatch["configuration"]["strategy"]], fallback=dispatch["fallback"])
    output = wire.canonical(submission)
    closure = {"schema": core.SCHEMA, "exited_seal_sha256": seal_hash,
               "analysis_sha256": wire.digest(wire.canonical(analysis)),
               "source_sha256": dispatch["source"]["sha256"], "challenge_sha256": dispatch["challenge_sha256"],
               "submission_sha256": wire.digest(output), "execution_kind": dispatch["execution_kind"],
               "scheduler": core.SCHEDULER, "configuration": dispatch["configuration"], "strategy_chosen_before_gold": True,
               "fallback_policy": dispatch["fallback"],
               "counts": counts, "queries": modes,
               "format_complete": True, "candidate_coverage_complete": counts["fallback_queries"] == 0,
               "all_queries_eight_views_completed": analysis["all_queries_eight_views_completed"],
               "generation_protocol_complete": analysis["generation_protocol_complete"], "protocol_complete": analysis["protocol_complete"],
               "all_planned_calls_returned": analysis["all_planned_calls_returned"],
               "all_generated_answers_valid": analysis["all_generated_answers_valid"], "accuracy_established": False,
               "scientific_complete": False, "accuracy_evaluated": False, "official_submission_performed": False,
               "completion_receipt_required": True,
               "qualification": "Public baseline deployment source only; no competition-hardware/eligibility or accuracy claim. Partial views, singleton padding, and copy-input fallback are not accuracy evidence. Seal is integrity, not authentication."}
    return output, wire.canonical(closure), analysis


def verify(run_dir, output_dir, *, require_completion=True):
    root, output_dir = files.safe_path(run_dir), files.safe_path(output_dir)
    output, closure, analysis = prepare_bundle(root)
    if files.read_bytes(root / "analysis.json") != wire.canonical(analysis):
        raise ValueError("saved analysis differs from strict raw-token replay")
    if files.read_bytes(output_dir / "submission.json") != output or files.read_bytes(output_dir / "closure.json") != closure:
        raise ValueError("published bundle differs from independent raw-token replay")
    if require_completion:
        completion, _ = files.load_json(root / "completion.json")
        wire.exact_fields(completion, {"schema", "readback_verified", "submission_sha256", "closure_sha256",
            "budget", "whole_budget_met_at_readback", "outer_closure_seconds", "evaluation_sha256", "whole_comparison_complete", "no_new_generation_or_clock_on_closure"}, "completion")
        if (completion["schema"] != core.SCHEMA or completion["no_new_generation_or_clock_on_closure"] is not True
                or not core._finite(completion["outer_closure_seconds"])):
            raise ValueError("completion schema/closure facts are invalid")
        dispatch, _ = files.load_json(root / "dispatch.json")
        exit_row, _ = files.load_json(root / "controller_exit.json")
        budget = completion["budget"]
        validate_budget(budget, dispatch)
        if (type(budget["elapsed_seconds"]) not in (int, float) or not core._finite(budget["elapsed_seconds"])
                or type(budget["budget_seconds"]) not in (int, float)
                or budget["original_start_monotonic"] != dispatch["start_monotonic"]
                or budget["budget_seconds"] != dispatch["budget_seconds"]
                or budget["elapsed_seconds"] < exit_row["budget"]["elapsed_seconds"]):
            raise ValueError("completion clock differs from original dispatch/observed closure")
        if (completion["submission_sha256"] != wire.digest(output)
                or completion["closure_sha256"] != wire.digest(closure)
                or completion["readback_verified"] is not True
                or completion["whole_budget_met_at_readback"] is not True
                or completion["budget"]["elapsed_seconds"] >= completion["budget"]["budget_seconds"]
                or (root / "deadline_failure.json").exists()):
            raise ValueError("final completion receipt does not bind verified bundle")
        expected_comparison = analysis["protocol_complete"] and analysis["candidate_coverage_complete"] and dispatch.get("evaluation_requested") is True
        if completion["whole_comparison_complete"] is not expected_comparison:
            raise ValueError("whole comparison status differs from complete calls, candidate coverage, and evaluator requirement")
        if dispatch.get("evaluation_requested"):
            evaluation, evaluation_raw = files.load_json(root / "evaluation.json")
            evaluation_start, _ = files.load_json(root / "evaluation_start.json")
            if (completion["evaluation_sha256"] != wire.digest(evaluation_raw)
                    or (root / "evaluation_failure.json").exists()
                    or evaluation_start["started_monotonic"] != evaluation["started_monotonic"]
                    or evaluation_start["original_start_monotonic"] != dispatch["start_monotonic"]
                    or not (dispatch["start_monotonic"] + exit_row["budget"]["elapsed_seconds"] <= evaluation["started_monotonic"] <= evaluation["completed_monotonic"]
                            <= dispatch["start_monotonic"] + budget["elapsed_seconds"])
                    or evaluation["cleanup"]["complete"] is not True
                    or evaluation["returncode"] != 0
                    or evaluation["original_start_monotonic"] != dispatch["start_monotonic"]
                    or evaluation["completed_monotonic"] > dispatch["end_monotonic"]
                    or evaluation["report"]["exited_seal_sha256"] != wire.digest(files.read_bytes(root / "exited_seal.json"))
                    or evaluation["report"]["frozen_export_strategy"] != dispatch["configuration"]["strategy"]):
                raise ValueError("evaluator receipt does not bind original clock and sealed selection")
        elif completion["evaluation_sha256"] is not None:
            raise ValueError("unexpected evaluator result")
        if dispatch["outer_supervised"]:
            outer, _ = files.load_json(root / "outer_completion.json")
            precommit, precommit_raw = files.load_json(root / "outer_precommit.json")
            outer_fields = {"schema", "original_start_monotonic", "budget_seconds", "elapsed_seconds", "cleanup",
                            "submission_sha256", "closure_sha256", "source_sha256", "original_whole_clock_met",
                            "hard_watchdog", "readback_verified"}
            wire.exact_fields(precommit, outer_fields, "outer precommit")
            wire.exact_fields(outer, outer_fields | {"precommit_sha256"}, "outer completion")
            if (outer["precommit_sha256"] != wire.digest(precommit_raw)
                    or precommit["readback_verified"] is not False
                    or (root / "outer_failure.json").exists()
                    or wire.canonical({k: v for k, v in outer.items()
                                      if k not in ("elapsed_seconds", "readback_verified", "precommit_sha256")}) !=
                       wire.canonical({k: v for k, v in precommit.items()
                                      if k not in ("elapsed_seconds", "readback_verified")})):
                raise ValueError("outer completion precommit/readback failed")
            if (outer["schema"] != core.SCHEMA or outer["original_start_monotonic"] != dispatch["start_monotonic"]
                    or type(outer["budget_seconds"]) not in (int, float) or outer["budget_seconds"] != dispatch["budget_seconds"]
                    or not core._finite(outer["elapsed_seconds"]) or outer["elapsed_seconds"] >= dispatch["budget_seconds"]
                    or outer["elapsed_seconds"] < budget["elapsed_seconds"]
                    or outer["original_whole_clock_met"] is not True or outer["readback_verified"] is not True
                    or outer["cleanup"]["complete"] is not True
                    or outer["submission_sha256"] != wire.digest(output) or outer["closure_sha256"] != wire.digest(closure)
                    or outer["source_sha256"] != dispatch["source"]["sha256"]):
                raise ValueError("outer hard-watchdog completion is missing or inconsistent")
    return analysis


def run(challenge_path, model_dir, run_dir, output_dir, *, budget_seconds=14400., context_cap=10240, strategy="vote", fallback="fail",
        _test_worker_prefix=None, _original_clock=None, evaluation_gold_path=None):
    """Run once. Private injection is CPU-testing only and irreversibly labelled.

    CLI freezes explicit context and strategy; no backend choice, retries, or resume.
    The original clock starts before input/source verification or subprocess setup.
    """
    start, epoch = (time.monotonic(), time.time()) if _original_clock is None else _original_clock
    if _original_clock is None and _test_worker_prefix is None:
        raise ValueError("public execution requires the independent outer supervisor")
    if start > time.monotonic():
        raise ValueError("original clock cannot start in the future")
    if sys.platform != "linux":
        raise ValueError("this controller requires Linux process groups and child subreaping")
    deadline = core.SharedDeadline(start, budget_seconds)
    if fallback not in ("fail", "copy-input"):
        raise ValueError("fallback must be fail or explicit copy-input")
    challenge, challenge_raw = files.load_json(challenge_path)
    wire.validate_challenge(challenge)
    root = mkdir_exclusive(run_dir)
    output_dir = files.safe_path(output_dir)
    if output_dir.exists():
        raise FileExistsError("output directory already exists; overwrite/resume forbidden")
    plan = core.make_plan(challenge, wire.digest(challenge_raw), context_cap=context_cap, budget_seconds=budget_seconds, strategy=strategy)
    core.publish(root / "challenge.json", raw=challenge_raw)
    plan_hash = core.publish(root / "plan.json", plan)
    dispatch = {"schema": core.SCHEMA, "start_monotonic": start, "start_epoch": epoch,
                "budget_seconds": budget_seconds, "evaluation_requested": evaluation_gold_path is not None, "outer_supervised": _original_clock is not None, "work_end_monotonic": deadline.work_end,
                "end_monotonic": deadline.end, "scheduler": core.SCHEDULER, "configuration": plan["configuration"],
                "source": core.source_identity(), "challenge_sha256": wire.digest(challenge_raw),
                "plan_sha256": plan_hash, "model_dir": str(files.safe_path(model_dir)),
                "expected_public_model": {"handle": model_pins.MODEL_HANDLE, "url": model_pins.MODEL_URL,
                                          "files": {k: {"bytes": v[0], "sha256": v[1]} for k, v in model_pins.MODEL_FILES.items()}},
                "fallback": fallback, "execution_kind": "public-pinned-model" if _test_worker_prefix is None
                else "synthetic-injected-no-model-evidence"}
    core.publish(root / "dispatch.json", dispatch)
    proc, cleanup, returncode, ownership = None, None, None, None
    worker_log, log_receipt = None, None
    reason, error = "not-started", None
    interrupted = []
    old_handlers, previous_subreaper = {}, None
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, lambda signum, frame: interrupted.append(signum))
        previous_subreaper = subreaper(True)
        deadline.check()
        command = list(_test_worker_prefix or [sys.executable, "-m", "tools.public_full_calibrated_solver.worker"])
        command.extend(["--run-dir", str(root)])
        environment = os.environ.copy()
        environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
                           TOKENIZERS_PARALLELISM="false", WANDB_DISABLED="true")
        worker_log = WorkerLog(root)
        baseline = {(pid, row["start_ticks"]) for pid, row in process_table().items() if row["ppid"] == os.getpid()}
        proc = subprocess.Popen(command, cwd=core.ROOT, env=environment, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        os.set_blocking(proc.stdout.fileno(), False)
        ownership = Ownership(proc.pid, baseline)
        reason = "worker-exited"
        while proc.poll() is None:
            ownership.update()
            worker_log.drain(proc.stdout)
            if interrupted:
                reason = "controller-interrupted"
                break
            if deadline.expired():
                reason = "global-work-deadline"
                break
            time.sleep(min(.05, deadline.work_remaining()))
    except Exception as exc:
        reason, error = "controller-failure", f"{type(exc).__name__}: {exc}"
    finally:
        if proc is not None:
            cleanup = safe_cleanup(proc, deadline, ownership, baseline)
            returncode = proc.poll()
            worker_log.drain(proc.stdout)
            proc.stdout.close()
        if worker_log is not None:
            log_receipt = worker_log.close()
        if previous_subreaper is not None:
            subreaper(previous_subreaper)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
    exit_row = {"schema": core.SCHEMA, "worker_dispatched": proc is not None,
                "worker_exited": proc is not None and returncode is not None,
                "returncode": returncode, "stop_reason": reason, "error": error,
                "interrupted_signals": interrupted, "cleanup": cleanup, "worker_log": log_receipt, "budget": deadline.receipt()}
    core.publish(root / "controller_exit.json", exit_row)
    def closure_check():
        if deadline.remaining() <= 0:
            if not (root / "deadline_failure.json").exists():
                core.publish(root / "deadline_failure.json", {"budget": deadline.receipt(),
                    "reason": "original whole clock expired; retained raw evidence is not a completed run"})
            raise TimeoutError("original whole clock expired during closure; no completed-run claim")
    closure_check()
    seal_exited(root)
    closure_check()
    _, _, analysis, _, _ = read_replay(root)
    core.publish(root / "analysis.json", analysis)
    closure_check()
    try:
        output, closure, _ = prepare_bundle(root)
        closure_check()
        files.publish_bundle(output_dir, output, closure)
        closure_check()
        verify(root, output_dir, require_completion=False)
        closure_check()
        evaluation_hash = None
        if evaluation_gold_path is not None:
            evaluation_hash = run_evaluator(root, output_dir, evaluation_gold_path, deadline)
            closure_check()
        completion = {"schema": core.SCHEMA, "evaluation_sha256": evaluation_hash, "readback_verified": True,
                      "whole_comparison_complete": analysis["protocol_complete"] and analysis["candidate_coverage_complete"] and evaluation_hash is not None,
                      "submission_sha256": wire.digest(output), "closure_sha256": wire.digest(closure),
                      "budget": deadline.receipt(), "whole_budget_met_at_readback": deadline.remaining() > 0,
                      "outer_closure_seconds": time.monotonic() - start - exit_row["budget"]["elapsed_seconds"],
                      "no_new_generation_or_clock_on_closure": True}
        core.publish(root / "completion.json", completion)
        if files.read_bytes(root / "completion.json") != wire.canonical(completion):
            raise ValueError("final completion receipt readback mismatch")
        closure_check()
        format_counts = files.decode_json(closure)["counts"]
        status = ("format-only-fallback" if format_counts["fallback_queries"] else
                  "partial-view-submission" if not analysis["all_queries_eight_views_completed"] else
                  "all-view-format-complete-not-accuracy-evidence")
        return {"format_complete": True, "status": status, "counts": format_counts,
                "operation_counts": analysis["counts"], "protocol_complete": analysis["protocol_complete"],
                "all_planned_calls_returned": analysis["all_planned_calls_returned"],
                "all_generated_answers_valid": analysis["all_generated_answers_valid"],
                "candidate_coverage_complete": analysis["candidate_coverage_complete"],
                "whole_comparison_complete": completion["whole_comparison_complete"],
                "execution_kind": dispatch["execution_kind"], "stop_reason": reason,
                "worker_returncode": returncode, "whole_budget_met": deadline.remaining() > 0,
                "elapsed_seconds": time.monotonic() - start,
                "scientific_complete": False, "official_submission_performed": False,
                "submission_path": str(output_dir / "submission.json"),
                "submission_sha256": wire.digest(output), "closure_sha256": wire.digest(closure),
                "source_sha256": dispatch["source"]["sha256"]}
    except (OSError, ValueError, TypeError) as exc:
        core.publish(root / "export_failure.json", {"error": f"{type(exc).__name__}: {exc}",
                                                    "budget": deadline.receipt()})
        raise


def run_evaluator(root, output_dir, gold_path, deadline):
    """Owned evaluator leaf uses only remaining original closure/evaluation time."""
    from tools.public_sft141_solver.supervisor import _drain
    command = [sys.executable, "-m", "tools.public_full_calibrated_solver.evaluation",
               "--run-dir", str(root), "--output-dir", str(output_dir), "--gold", os.fspath(gold_path),
               "--before-completion"]
    proc = ownership = cleanup = None
    previous = subreaper(True)
    baseline = {(pid, row["start_ticks"]) for pid, row in process_table().items() if row["ppid"] == os.getpid()}
    buffer = bytearray()
    begun = time.monotonic()
    core.publish(root / "evaluation_start.json", {"started_monotonic": begun, "original_start_monotonic": deadline.start,
        "remaining_seconds": deadline.remaining(), "gold_read_by_separate_owned_leaf_only": True})
    failure = None
    try:
        if deadline.remaining() <= 0:
            raise TimeoutError("no original-clock time remains for evaluator")
        proc = subprocess.Popen(command, cwd=core.ROOT, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        os.set_blocking(proc.stdout.fileno(), False)
        ownership = Ownership(proc.pid, baseline)
        while proc.poll() is None:
            ownership.update()
            _drain(proc.stdout, buffer)
            if deadline.remaining() <= 0:
                raise TimeoutError("evaluator reached original whole deadline")
            time.sleep(min(.02, deadline.remaining()))
    except BaseException as exc:
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        if proc is not None:
            cleanup = safe_cleanup(proc, deadline, ownership, baseline)
            _drain(proc.stdout, buffer)
            proc.stdout.close()
        subreaper(previous)
    if failure is not None or proc is None or proc.returncode != 0 or not cleanup["complete"] or deadline.remaining() <= 0:
        core.publish(root / "evaluation_failure.json", {"returncode": proc.returncode if proc else None, "cleanup": cleanup,
            "original_start_monotonic": deadline.start, "budget": deadline.receipt(),
            "error": failure or buffer.decode("utf-8", errors="replace")[-2000:]})
        raise RuntimeError("separate evaluator did not finish and close within original whole clock")
    report = files.decode_json(bytes(buffer).strip().splitlines()[-1])
    receipt = {"report": report, "returncode": proc.returncode, "cleanup": cleanup,
               "original_start_monotonic": deadline.start, "started_monotonic": begun,
               "completed_monotonic": time.monotonic(), "elapsed_seconds": time.monotonic() - begun}
    digest = core.publish(root / "evaluation.json", receipt)
    if files.read_bytes(root / "evaluation.json") != wire.canonical(receipt):
        raise ValueError("evaluator receipt readback mismatch")
    return digest


def main(argv=None):
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Private supervised-controller entrypoint")
    parser.add_argument("--request-json", required=True)
    args = parser.parse_args(argv)
    try:
        request = files.decode_json(args.request_json.encode())
        result = run(**request)
        print(json.dumps(result, sort_keys=True, allow_nan=False), flush=True)
        return 0
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print(f"supervised controller failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
