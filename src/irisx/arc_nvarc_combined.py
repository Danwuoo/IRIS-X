"""Exactly bound M2/M3 authorization and independently checked supervision."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import signal
import subprocess
import sys
import threading
import time

from .canonical import canonical_bytes, digest_value
from .errors import ValidationError

RUN = "nvarc-m2-m3-combined-001"
REPAIR_RUN = "nvarc-m2-m3-combined-002"
DRAFT_DIGEST = "sha256:2052311757ab3922473e0476801dde4df551e0a037795b64025fa5f17c54e0ef"
DRAFT_SHA256 = "7014795d4ea7f098a8f9680b32843039a2c76b946fd920789491743201ebcc22"
APPROVED_DIGEST = "sha256:efa10338690105c3236a8bb62d235568d2335b08a674475ba156e6b9a4abc912"
REPAIR_DIGEST = "sha256:48e9fa7c28e37fc585f87046957e723573697eb01016e1175fab50c9152364ef"
EDITOR_DIGEST = 'sha256:13790f5930800a9614555cae183eecfe12b0443d9a8f4ba83f9d3976039410cf'
PROFILE = "combined-two-distinct-l4-v1"
LOG_LIMIT = 8 * 1024 * 1024


def require(value, message):
    if not value:
        raise ValidationError(message)


def sha(path: Path, *, deadline=None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            require(deadline is None or time.monotonic() < deadline, "artifact hashing deadline expired")
            digest.update(block)
    return digest.hexdigest()


def read(path: Path):
    return json.loads(path.read_bytes())


def atomic(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(canonical_bytes(value, newline=True))
    for attempt in range(5):
        try:
            os.replace(temporary, path)
            return
        except PermissionError as error:
            # Windows readers can briefly hold a file without delete sharing.
            # Keep the old complete ledger until replacement succeeds; ordinary
            # permissions fail immediately; persistent locks get at most 150 ms
            # of backoff before the original error is raised.
            if getattr(error, "winerror", None) not in {5, 32, 33} or attempt == 4:
                raise
            time.sleep(0.01 * 2**attempt)


def member(root: Path, name: str) -> Path:
    relative = Path(name)
    require(isinstance(name, str) and not relative.is_absolute() and
            not PureWindowsPath(name).drive and not PureWindowsPath(name).root and
            ":" not in name and ".." not in relative.parts and
            "\\" not in name and name not in {"", "."}, "unsafe artifact member")
    path = root / relative
    require(not root.is_symlink() and not any(p.is_symlink() for p in
            [path, *path.parents] if p == root or root in p.parents), "artifact symlink ancestor")
    return path


def validate_plan(plan: dict, *, approved=False) -> None:
    # Whole-plan binding rejects unknown fields, changed inputs, identities,
    # allowances and budgets, including booleans substituted for integer limits.
    expected = REPAIR_DIGEST if plan.get("run_id") == REPAIR_RUN else APPROVED_DIGEST
    require(digest_value(plan) == (expected if approved else DRAFT_DIGEST),
            "combined approved identity, materials or bounds differ" if approved else
            "combined draft identity, materials or bounds differ")


def activate_plan(draft: dict, *, run_id=RUN) -> dict:
    """Exact historical 0035 or replacement 0036 authorization/transport envelope.

    Child scientific fields remain inert workload specifications; replacement
    children receive distinct identities, with no independent submission quota.
    """
    validate_plan(draft)
    plan = copy.deepcopy(draft)
    plan.update(format="irisx/nvarc-combined-approved-v1", approved=True,
                owner_decision="Decision 0035", kernel_id="danielwuu/" + RUN,
                original_draft_digest=DRAFT_DIGEST, original_draft_sha256=DRAFT_SHA256)
    plan["external_allowances"]["submissions"] = 1
    require(run_id in {RUN, REPAIR_RUN}, "known combined run identity required")
    if run_id == REPAIR_RUN:
        plan.update(run_id=run_id, owner_decision="Decision 0036", kernel_id="danielwuu/" + run_id)
        for branch, child in plan["branches"].items():
            child.update(run_id=run_id + "-" + branch, kernel_id="DRAFT-DO-NOT-PUSH/" + run_id + "-" + branch)
    validate_plan(plan, approved=True)
    return plan


def require_live_authorization(plan: dict) -> None:
    if digest_value(plan) == DRAFT_DIGEST:
        raise ValidationError("combined draft is inert; exact Decision 0036 package required")
    require(digest_value(plan) in {REPAIR_DIGEST, EDITOR_DIGEST},
            "exact Decision 0036 or owner-Editor Decision 0037 combined package required")


def select_devices(inventory: list[dict], indices=(0, 1)) -> dict:
    require(len(indices) == 2 and all(type(i) is int for i in indices) and
            len(set(indices)) == 2, "two distinct device indices required")
    require(all(type(g.get("index")) is int and isinstance(g.get("uuid"), str) and
                g["uuid"] for g in inventory) and
            len({g["index"] for g in inventory}) == len(inventory) and
            len({g["uuid"] for g in inventory}) == len(inventory), "hardware inventory identities differ")
    by_index = {g["index"]: g for g in inventory}
    require(set(indices) <= set(by_index), "assigned device missing")
    selected = [by_index[i] for i in indices]
    require(all(g.get("name") == "NVIDIA L4" and g.get("bf16") is True and
                g.get("memory_bytes", 0) >= 22 * 10**9 and
                g.get("memory_mib", 0) >= 22000 for g in selected),
            "two BF16 L4 devices with minimum memory required")
    return {"profile": PROFILE, "inventory": inventory,
            "assignments": {branch: selected[i] for i, branch in enumerate(("m2", "m3"))}}


def check_logical_device(branch, hardware, assigned_uuid, logical_inventory, visible_devices):
    require(hardware.get("profile") == PROFILE, "explicit combined hardware profile required")
    selected = select_devices(hardware["inventory"],
        [hardware["assignments"][b]["index"] for b in ("m2", "m3")])
    require(selected == hardware, "parent device record differs")
    assigned = selected["assignments"][branch]
    require(assigned_uuid == assigned["uuid"] and visible_devices == assigned_uuid and
            len(logical_inventory) == 1 and logical_inventory[0]["index"] == 0 and
            all(logical_inventory[0].get(k) == assigned.get(k) for k in
                ("uuid", "physical_index", "name", "memory_bytes", "memory_mib", "bf16")),
            "worker must see only assigned UUID as logical cuda:0")


def resolve_mount(dataset_id: str, marker: str, root=Path("/kaggle/input")) -> Path:
    owner, slug = dataset_id.split("/")
    candidates = [root / "datasets" / owner / slug, root / slug]
    matches = [path for path in candidates if (path / marker).is_file()]
    require(len(matches) == 1, "exact owner-qualified or legacy Dataset mount required: " + dataset_id)
    return matches[0]


def event(output, *, branch, phase, started, run_id, plan_digest, **details):
    record = {"branch": branch, "phase": phase, "elapsed_seconds": time.monotonic() - started,
              "run_id": run_id, "plan_digest": plan_digest, **details}
    with (output / "startup-events.jsonl").open("ab") as stream:
        stream.write(canonical_bytes(record, newline=True))


def _windows_job(process):
    """Kill descendants on job close, even if the primary worker exits first."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    limits = Extended()
    limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not handle or not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(process._handle)):
        if handle:
            kernel.CloseHandle(handle)
        process.kill()
        process.wait(timeout=5)
        raise OSError("cannot establish worker process job")
    return lambda: kernel.CloseHandle(handle)


def _reap(process, close_job, term_seconds, kill_seconds):
    # Also clean descendants after a normal primary-process exit.
    if close_job is not None:
        close_job()
    elif os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=term_seconds)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=kill_seconds)
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _launch_worker(command, *, cwd, env):
    """Establish the Windows descendant job before allowing worker execution.

    Assigning a running short-lived worker races its exit. A pipe-gated Python
    parent stays alive until assignment and its worker inherits the same job.
    Closing the gate without authorization starts no worker.
    """
    gated = os.name == "nt"
    if gated:
        bootstrap = ("import json, subprocess, sys\n"
                     "if sys.stdin.buffer.read(1) != b'1':\n"
                     "    raise SystemExit(125)\n"
                     "raise SystemExit(subprocess.call(json.loads(sys.argv[1]), "
                     "stdin=subprocess.DEVNULL))\n")
        command = [sys.executable, "-c", bootstrap, json.dumps(command)]
    process = subprocess.Popen(command, cwd=cwd, env=env,
        stdin=subprocess.PIPE if gated else None,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=os.name == "posix",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if gated else 0)
    job = None
    try:
        job = _windows_job(process)
        if gated:
            process.stdin.write(b"1")
            process.stdin.flush()
            process.stdin.close()
        return process, job
    except BaseException:
        if gated and not process.stdin.closed:
            process.stdin.close()
        if job is not None:
            job()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        for pipe in (process.stdout, process.stderr):
            pipe.close()
        raise


def _drain(pipe, path):
    retained = 0
    with path.open("wb") as stream:
        while True:
            chunk = pipe.read(65536)
            if not chunk:
                break
            keep = min(len(chunk), max(0, LOG_LIMIT - retained))
            stream.write(chunk[:keep])
            retained += keep
    pipe.close()


def verify_envelope(output: Path, *, run_id: str, plan_digest: str, branch: str, deadline=None) -> dict:
    terminal = read(member(output, "worker-terminal.json"))
    require(terminal.get("run_id") == run_id + "-" + branch and
            terminal.get("parent_run_id") == run_id and terminal.get("plan_digest") == plan_digest and
            terminal.get("branch") == branch and terminal.get("status") == "complete" and
            terminal.get("contains_evaluator_truth") is False, "child terminal binding or status differs")
    artifacts = terminal.get("artifacts", {})
    require(isinstance(artifacts, dict) and artifacts, "child result artifacts absent")
    for name, digest in artifacts.items():
        require(sha(member(output, name), deadline=deadline) == digest, "child artifact differs: " + name)
    expected = set(artifacts) | {"worker-terminal.json", "worker-state.json", "model-ready.json",
                                 "stdout.log", "stderr.log"}
    actual = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    require(actual <= expected and not any(p.is_symlink() for p in output.rglob("*")),
            "child artifact inventory differs")
    return terminal


def supervise(children: dict, output: Path, *, run_id: str, plan_digest: str,
              deadline: float, readiness_seconds: float, validators: dict,
              started: float | None = None, setup=None, term_seconds=5, kill_seconds=5,
              terminal_deadline: float | None = None) -> dict:
    """Start each child once; stagger on readiness or bounded pre-ready failure.

    Validators must independently check workload semantics after the envelope.
    Pipe-draining threads keep the first 8 MiB per stream and discard excess.
    All cleanup and packaging fit within the caller's terminal reserve.
    """
    require(set(children) == {"m2", "m3"} == set(validators), "two independent children and validators required")
    require(not output.exists(), "new combined output required")
    output.mkdir(parents=True)
    started = time.monotonic() if started is None else started
    terminal_deadline = deadline + 30 if terminal_deadline is None else terminal_deadline
    results = {branch: {"run_id": run_id + "-" + branch, "parent_run_id": run_id,
                       "child_plan_digest": spec.get("child_plan_digest"),
                       "material_bindings": spec.get("materials"),
                       "outcome": "not-started", "last_phase": "pending", "error": None,
                       "assigned_device": spec.get("device"), "return_code": None,
                       "reserved_counters": None, "actual_counters": None,
                       "artifacts": {}, "launch_count": 0} for branch, spec in children.items()}
    active = {}
    next_branch = 0
    shared_error = None

    def emit(branch, phase, **details):
        event(output, branch=branch, phase=phase, started=started,
              run_id=run_id, plan_digest=plan_digest, **details)

    def finish(branch, outcome, error=None):
        worker = active.pop(branch)
        cleanup_errors = []
        try:
            remaining = max(0, terminal_deadline - time.monotonic())
            _reap(worker["process"], worker["job"], min(term_seconds, remaining / 3),
                  min(kill_seconds, remaining / 3))
        except Exception as exception:
            cleanup_errors.append(str(exception)[:2000])
            try:
                if worker["process"].poll() is None:
                    worker["process"].kill()
                worker["process"].wait(timeout=min(kill_seconds, max(0, terminal_deadline - time.monotonic())))
            except Exception as fallback:
                cleanup_errors.append(str(fallback)[:2000])
        for thread in worker["threads"]:
            thread.join(timeout=min(kill_seconds, max(0, terminal_deadline - time.monotonic())))
            if thread.is_alive():
                cleanup_errors.append("worker log drain did not terminate")
        root = output / branch
        result = results[branch]
        result.update(outcome=outcome, return_code=worker["process"].returncode,
                      error=error, wall_seconds=time.monotonic() - worker["started"])
        for name in ("worker-state.json", "worker-terminal.json"):
            if (root / name).is_file():
                try:
                    value = read(member(root, name))
                    require(value.get("branch") == branch and value.get("parent_run_id") == run_id and
                            value.get("plan_digest") == plan_digest, "child diagnostic binding differs")
                    result["last_phase"] = value.get("phase", result["last_phase"])
                    result["reserved_counters"] = value.get("reserved_counters")
                    result["actual_counters"] = value.get("actual_counters")
                    if value.get("error"):
                        result["error"] = value["error"]
                except Exception as exception:
                    result["diagnostic_error"] = str(exception)[:2000]
        if outcome != "complete" and children[branch].get("diagnostics") is not None:
            try:
                partial = children[branch]["diagnostics"](root)
                result.update(partial)
            except Exception as exception:
                result["partial_counter_error"] = str(exception)[:2000]
        if outcome == "complete":
            # Preserve independently reconciled counts, regardless of diagnostics.
            result["actual_counters"] = result["verification"]
        try:
            result["artifacts"] = {p.relative_to(root).as_posix(): sha(member(root, p.relative_to(root).as_posix()),
                                                                         deadline=terminal_deadline)
                                   for p in root.rglob("*") if p.is_file()}
        except Exception as exception:
            result["artifact_error"] = str(exception)[:2000]
        if cleanup_errors:
            result.update(outcome="failed", cleanup_errors=cleanup_errors)
        try:
            emit(branch, "terminal", outcome=result["outcome"], return_code=result["return_code"], error=result["error"])
        except Exception as exception:
            result["event_error"] = str(exception)[:2000]

    try:
        emit("shared", "setup-start")
        if setup is not None:
            setup()
        require(time.monotonic() < deadline, "global deadline expired during shared setup")
        emit("shared", "setup-complete")
        while active or next_branch < 2:
            now = time.monotonic()
            if now >= deadline:
                for branch in list(active):
                    finish(branch, "timed-out", "global monotonic work deadline exceeded")
                for branch in ("m2", "m3")[next_branch:]:
                    results[branch].update(outcome="timed-out", error="global deadline before launch")
                break
            for branch in list(active):
                worker = active[branch]
                root = output / branch
                if not worker["ready"] and (root / "model-ready.json").is_file():
                    try:
                        ready = read(member(root, "model-ready.json"))
                        require(ready.get("branch") == branch and ready.get("parent_run_id") == run_id and
                                ready.get("plan_digest") == plan_digest and
                                ready.get("device") == children[branch].get("device"),
                                "model-ready binding differs")
                        worker["ready"] = True
                        results[branch]["last_phase"] = "work"
                        emit(branch, "model-ready", device=ready.get("device"))
                    except Exception as exception:
                        finish(branch, "failed", str(exception)[:2000])
                        continue
                code = worker["process"].poll()
                if code is not None:
                    outcome, error = "failed", "worker returned nonzero"
                    if code == 0:
                        try:
                            require(worker["ready"], "worker exited without model-ready")
                            terminal = verify_envelope(root, run_id=run_id, plan_digest=plan_digest,
                                                       branch=branch, deadline=deadline)
                            verified = validators[branch](root)
                            require(terminal.get("actual_counters") == verified,
                                    "child counters differ from independent verification")
                            require(terminal.get("device") == children[branch].get("device") and
                                    (children[branch].get("child_plan_digest") is None or
                                     terminal.get("child_plan_digest") == children[branch]["child_plan_digest"]),
                                    "child terminal device or plan binding differs")
                            results[branch]["verification"] = verified
                            results[branch]["actual_counters"] = terminal.get("actual_counters")
                            outcome, error = "complete", None
                        except Exception as exception:
                            error = str(exception)[:2000]
                    finish(branch, outcome, error)
                elif not worker["ready"] and now - worker["started"] >= readiness_seconds:
                    finish(branch, "timed-out", "bounded model-ready wait expired")
            can_launch = (next_branch == 0 or "m2" not in active or active["m2"]["ready"])
            if next_branch < 2 and can_launch:
                branch = ("m2", "m3")[next_branch]
                next_branch += 1
                spec = children[branch]
                root = output / branch
                root.mkdir()
                env = {**os.environ, **spec.get("env", {}), "PYTHONIOENCODING": "utf-8"}
                if spec.get("device") is not None:
                    env["CUDA_VISIBLE_DEVICES"] = spec["device"]["uuid"]
                try:
                    process, job = _launch_worker(spec["command"], cwd=spec.get("cwd"), env=env)
                    threads = [threading.Thread(target=_drain, args=(pipe, root / name), daemon=True)
                               for pipe, name in ((process.stdout, "stdout.log"), (process.stderr, "stderr.log"))]
                    for thread in threads:
                        thread.start()
                    active[branch] = {"process": process, "job": job, "threads": threads,
                                      "started": time.monotonic(), "ready": False}
                    results[branch].update(launch_count=1, last_phase="loading")
                    emit(branch, "launch", pid=process.pid, device=spec.get("device"))
                except Exception as exception:
                    results[branch].update(outcome="failed", error=str(exception)[:2000])
                    emit(branch, "launch-failed", error=results[branch]["error"])
            time.sleep(min(0.02, max(0, deadline - time.monotonic())))
    except Exception as exception:
        shared_error = {"type": type(exception).__name__, "message": str(exception)[:2000]}
        emit("shared", "failed", error=shared_error)
    finally:
        for branch in list(active):
            finish(branch, "failed", "shared supervisor failure")
        if shared_error:
            for result in results.values():
                if result["outcome"] == "not-started":
                    result.update(outcome="failed", last_phase="shared-setup", error=shared_error["message"])
        completed = sum(item["outcome"] == "complete" for item in results.values())
        outcome = ("complete" if completed == 2 else "partial" if completed else
                   "timed-out" if any(r["outcome"] == "timed-out" for r in results.values()) else "failed")
        manifest = {"format": "irisx/nvarc-combined-terminal-v1", "run_id": run_id,
                    "plan_digest": plan_digest, "outcome": outcome, "branches": results,
                    "shared_error": shared_error, "wall_seconds": time.monotonic() - started,
                    "contains_evaluator_truth": False, "retries": 0}
        atomic(output / "aggregate-terminal.json", manifest)
    return manifest


def completion_failure(manifest: dict) -> str | None:
    """Describe branch/phase/reason while preserving the terminal disposition."""
    if manifest.get("outcome") == "complete":
        return None
    details = []
    for branch in ("m2", "m3"):
        item = manifest.get("branches", {}).get(branch, {})
        error = item.get("error")
        if isinstance(error, dict):
            error = error.get("message") or error.get("type")
        counts = item.get("actual_counters") or {}
        detail = f"{branch} {item.get('outcome', 'unknown')} at {item.get('last_phase', 'unknown')}"
        if branch == "m2" and "ranked_candidates" in counts:
            detail += f" (ranked_candidates={counts['ranked_candidates']}"
            if counts["ranked_candidates"] == 0:
                detail += "; missing-candidate"
            detail += ")"
        failures = [s for s in item.get("stage_outcomes", []) if s.get("status") != "complete"]
        if failures:
            stage = failures[0]
            detail += f"; {stage['stage']} {stage['status']}: {stage.get('reason') or 'response incomplete'}"
        elif error:
            detail += ": " + str(error)[:600]
        details.append(detail)
    return (f"combined {manifest.get('outcome', 'unknown')}; " + " | ".join(details) +
            "; no retry; evidence: aggregate-terminal.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    # Gate before importing ML packages, changing dependencies or launching work.
    require_live_authorization(read(args.plan))


if __name__ == "__main__":
    main()
