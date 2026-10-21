"""Linux ownership/watchdog and post-exit replay/export for the public baseline."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time

from tools.public_sft141_diagnostic import model_pins
from tools.public_sft141_submission import contract as wire
from tools.public_sft141_submission import files
from . import core


def mkdir_exclusive(path):
    with files.parent_directory(path) as (path, fd):
        if fd is None:
            raise ValueError("solver process ownership requires Linux no-follow directory operations")
        os.mkdir(path.name, mode=0o700, dir_fd=fd)
    return path


def process_table():
    result = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(") ", 1)[1].split()
            result[int(entry.name)] = {"state": fields[0], "ppid": int(fields[1]),
                "pgid": int(fields[2]), "session": int(fields[3]), "start_ticks": int(fields[19])}
        except (OSError, ValueError, IndexError):
            continue
    return result


def group_members(pgid):
    return {pid: row for pid, row in process_table().items()
            if row["pgid"] == pgid and row["session"] == pgid}


class Ownership:
    """Observed lineage is bound to Linux start ticks, never a bare PID.

    A newly adopted child with unobserved provenance is not safe to signal. It
    blocks the seal instead. Existing unrelated children are never touched.
    """
    def __init__(self, root_pid, baseline):
        self.root_pid, self.baseline = root_pid, baseline
        self.owned, self.uncertain = {}, {}
        self.update()

    def update(self):
        table = process_table()
        root = table.get(self.root_pid)
        if root and root["pgid"] == self.root_pid and root["session"] == self.root_pid and self.root_pid not in self.owned:
            self.owned[self.root_pid] = root["start_ticks"]
        live = {pid for pid, tick in self.owned.items()
                if pid in table and table[pid]["start_ticks"] == tick}
        root_reused = root is not None and self.root_pid in self.owned and root["start_ticks"] != self.owned[self.root_pid]
        changed = True
        while changed:
            changed = False
            for pid, row in table.items():
                if pid in live:
                    continue
                if row["ppid"] in live or (not root_reused and row["pgid"] == self.root_pid and row["session"] == self.root_pid):
                    self.owned[pid] = row["start_ticks"]
                    live.add(pid)
                    changed = True
        for pid, row in table.items():
            identity = (pid, row["start_ticks"])
            if row["ppid"] == os.getpid() and identity not in self.baseline and pid not in live:
                self.uncertain[pid] = row["start_ticks"]
        self.uncertain = {pid: tick for pid, tick in self.uncertain.items()
                          if pid in table and table[pid]["start_ticks"] == tick and pid not in live}
        return {pid: table[pid] for pid in live}

    def signal_escaped(self, sig):
        for pid, row in self.update().items():
            if row["state"] == "Z" or (row["pgid"] == self.root_pid and row["session"] == self.root_pid):
                continue
            if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
                continue  # Remains live, so cleanup and sealing fail closed.
            try:
                fd = os.pidfd_open(pid)
                try:
                    now = process_table().get(pid)
                    if now is not None and now["start_ticks"] == self.owned[pid]:
                        signal.pidfd_send_signal(fd, sig)
                finally:
                    os.close(fd)
            except ProcessLookupError:
                pass

def subreaper(enable):
    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(previous), 0, 0, 0) != 0:  # PR_GET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "cannot inspect Linux child-subreaper state")
    if libc.prctl(36, int(enable), 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "cannot set Linux child-subreaper state")
    return previous.value


def cleanup_group(proc, deadline, ownership):
    begun = time.monotonic()
    signals = []
    for sig, grace in ((signal.SIGTERM, .15), (signal.SIGKILL, .35)):
        members = ownership.update()
        if any(v["state"] != "Z" and v["pgid"] == proc.pid and v["session"] == proc.pid
               for v in members.values()):
            try:
                os.killpg(proc.pid, sig)
                signals.append(sig.name)
            except ProcessLookupError:
                pass
        ownership.signal_escaped(sig)
        stop = time.monotonic() + min(grace, max(.02, deadline.remaining()))
        while time.monotonic() < stop:
            ownership.update()
            proc.poll()
            for pid in list(ownership.update()):
                if pid == proc.pid:
                    continue
                try:
                    os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    pass
            if not ownership.update():
                break
            time.sleep(.01)
    proc.poll()
    remaining = ownership.update()
    return {"owned_pgid": proc.pid, "owned_session": proc.pid,
            "observed_pids": sorted(ownership.owned), "owned_pid_start_ticks": ownership.owned,
            "signals": signals, "remaining_owned_members": {str(k): v for k, v in remaining.items()},
            "unattributed_adopted_children": {str(k): v for k, v in ownership.uncertain.items()},
            "complete": not remaining and not ownership.uncertain,
            "seconds": time.monotonic() - begun,
            "scope": "owned-new-session-group-and-start-time-bound-observed-descendants; unattributed-adoptions-block-seal"}

def safe_cleanup(proc, deadline, ownership, baseline):
    """Inspection failures still stop the direct owned child, never certify closure."""
    try:
        return cleanup_group(proc, deadline, ownership or Ownership(proc.pid, baseline))
    except Exception as exc:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=.1)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=.2)
                except subprocess.TimeoutExpired:
                    pass
        return {"owned_pgid": proc.pid, "owned_session": proc.pid,
                "observed_pids": sorted(ownership.owned) if ownership else [proc.pid],
                "complete": False, "remaining_owned_members": "unknown-inspection-failure",
                "unattributed_adopted_children": "unknown-inspection-failure",
                "error": f"{type(exc).__name__}: {exc}",
                "scope": "direct Popen child stopped; descendant closure is unproven"}

class WorkerLog:
    """Bounded prefix of combined worker stdout/stderr, never environment dumps."""
    LIMIT = 1024 * 1024

    def __init__(self, root):
        with files.parent_directory(root / "worker.log") as (path, parent):
            self.fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                              0o600, dir_fd=parent)
        self.seen = self.saved = 0

    def drain(self, stream):
        for _ in range(16):
            try:
                chunk = os.read(stream.fileno(), 65536)
            except BlockingIOError:
                break
            if not chunk:
                break
            self.seen += len(chunk)
            keep = chunk[:max(0, self.LIMIT - self.saved)]
            if keep:
                view = memoryview(keep)
                while view:
                    written = os.write(self.fd, view)
                    view = view[written:]
                self.saved += len(keep)

    def close(self):
        os.fsync(self.fd)
        os.close(self.fd)
        return {"bytes_seen": self.seen, "bytes_saved": self.saved, "truncated": self.seen > self.saved,
                "cap_bytes": self.LIMIT, "scientific_evidence": False,
                "streams": "combined stdout/stderr; inherited environment is never printed by controller"}

def _seal_files(root):
    names = ["challenge.json", "plan.json", "dispatch.json", "controller_exit.json"]
    allowed = {"inventory.json", "identity.json", "model_identity.json", "environment.json",
               "load_preflight.json", "backend.json", "admission.json", "model_state_before.json",
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
    cap, state_guard = core.CONTEXT_CAP, "unknown"
    if "worker/admission.json" in seal["files"]:
        admission, _ = files.load_json(root / "worker/admission.json")
        cap = admission["effective_context"]
    if "worker/model_state_after.json" in seal["files"]:
        state_after, _ = files.load_json(root / "worker/model_state_after.json")
        state_before, _ = files.load_json(root / "worker/model_state_before.json")
        state_guard = "unchanged" if state_after["snapshot"] == state_before else "changed"
        if state_after["status"] == "changed":
            state_guard = "changed"
        if state_after["status"] != state_guard:
            raise ValueError("model state guard evidence is inconsistent")
    if records:
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
    bounds = (dispatch["start_monotonic"], dispatch["work_end_monotonic"],
              dispatch["start_monotonic"] + exit_row["budget"]["elapsed_seconds"])
    analysis, selections = core.reconstruct(plan, records, effective_context=cap,
                                            state_guard=state_guard, timing_bounds=bounds)
    terminal = {"status": "missing-terminal-not-clean", "phase": "unknown", "error": "Worker did not publish a terminal receipt; see bounded worker.log."}
    if "worker/terminal.json" in seal["files"]:
        terminal, _ = files.load_json(root / "worker/terminal.json")
    generation_protocol_complete = (dispatch["execution_kind"] == "public-pinned-model"
        and analysis["counts"]["valid_views"] == analysis["counts"]["planned_views"]
        and state_guard == "unchanged" and exit_row["returncode"] == 0
        and exit_row["stop_reason"] == "worker-exited"
        and terminal["status"] == "all-admissible-views-returned"
        and exit_row["budget"]["elapsed_seconds"] < dispatch["budget_seconds"])
    analysis.update({"generation_protocol_complete": generation_protocol_complete,
                     "accuracy_established": False, "worker_terminal": terminal,
                     "execution_kind": dispatch["execution_kind"],
                     "worker_returncode": exit_row["returncode"], "controller_stop_reason": exit_row["stop_reason"],
                     "effective_context": cap})
    # A surviving immutable inventory must agree with independent prompt rebuild.
    if "worker/inventory.json" in seal["files"]:
        actual, _ = files.load_json(root / "worker/inventory.json")
        if wire.canonical(actual) != wire.canonical({"schema": core.SCHEMA, "queries": core.inventory(plan)}):
            raise ValueError("worker inventory disagrees with all-support prompt reconstruction")
    return challenge, dispatch, analysis, selections, wire.digest(seal_raw)


def prepare_bundle(root):
    challenge, dispatch, analysis, selections, seal_hash = read_replay(root)
    submission, counts, modes = wire.build_submission(challenge, selections, fallback=dispatch["fallback"])
    output = wire.canonical(submission)
    closure = {"schema": core.SCHEMA, "exited_seal_sha256": seal_hash,
               "analysis_sha256": wire.digest(wire.canonical(analysis)),
               "source_sha256": dispatch["source"]["sha256"], "challenge_sha256": dispatch["challenge_sha256"],
               "submission_sha256": wire.digest(output), "execution_kind": dispatch["execution_kind"],
               "scheduler": core.SCHEDULER, "fallback_policy": dispatch["fallback"],
               "counts": counts, "queries": modes,
               "format_complete": True, "candidate_coverage_complete": counts["fallback_queries"] == 0,
               "all_queries_eight_views_completed": analysis["all_queries_eight_views_completed"],
               "generation_protocol_complete": analysis["generation_protocol_complete"], "accuracy_established": False,
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
            "budget", "whole_budget_met_at_readback", "outer_closure_seconds", "no_new_generation_or_clock_on_closure"}, "completion")
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


def run(challenge_path, model_dir, run_dir, output_dir, *, budget_seconds=7200., fallback="fail",
        _test_worker_prefix=None, _original_clock=None):
    """Run once. Private injection is CPU-testing only and irreversibly labelled.

    CLI exposes no backend choice, token/context override, retry, or resume.
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
    plan = core.make_plan(challenge, wire.digest(challenge_raw))
    core.publish(root / "challenge.json", raw=challenge_raw)
    plan_hash = core.publish(root / "plan.json", plan)
    dispatch = {"schema": core.SCHEMA, "start_monotonic": start, "start_epoch": epoch,
                "budget_seconds": budget_seconds, "outer_supervised": _original_clock is not None, "work_end_monotonic": deadline.work_end,
                "end_monotonic": deadline.end, "scheduler": core.SCHEDULER,
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
        command = list(_test_worker_prefix or [sys.executable, "-m", "tools.public_sft141_solver.worker"])
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
        completion = {"schema": core.SCHEMA, "readback_verified": True,
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
                "operation_counts": analysis["counts"],
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
