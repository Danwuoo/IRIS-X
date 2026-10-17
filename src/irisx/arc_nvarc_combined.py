"""Exactly bound M2/M3 authorization and independently checked supervision."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import queue
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


def _same_json(left, right):
    """Exact JSON binding: Python equality aliases bool/int and int/float."""
    return canonical_bytes(left) == canonical_bytes(right)


def sha(path: Path, *, deadline=None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            require(deadline is None or time.monotonic() < deadline, "artifact hashing deadline expired")
            digest.update(block)
    return digest.hexdigest()


def read(path: Path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "duplicate child/plan JSON field: " + key)
            value[key] = item
        return value

    def nonfinite(value):
        raise ValidationError("non-finite child/plan JSON value: " + value)

    def finite_float(value):
        number = float(value)
        require(math.isfinite(number), "non-finite child/plan JSON number")
        return number

    return json.loads(path.read_bytes(), object_pairs_hook=unique,
                      parse_constant=nonfinite, parse_float=finite_float)


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
    require(_same_json(selected, hardware), "parent device record differs")
    assigned = selected["assignments"][branch]
    require(assigned_uuid == assigned["uuid"] and visible_devices == assigned_uuid and
            len(logical_inventory) == 1 and type(logical_inventory[0]["index"]) is int and
            logical_inventory[0]["index"] == 0 and
            all(_same_json(logical_inventory[0].get(k), assigned.get(k)) for k in
                ("uuid", "physical_index", "name", "memory_bytes", "memory_mib", "bf16")),
            "worker must see only assigned UUID as logical cuda:0")


def resolve_mount(dataset_id: str, marker: str, root=Path("/kaggle/input")) -> Path:
    owner, slug = dataset_id.split("/")
    candidates = [root / "datasets" / owner / slug, root / slug]
    matches = [path for path in candidates if (path / marker).is_file()]
    require(len(matches) == 1, "exact owner-qualified or legacy Dataset mount required: " + dataset_id)
    return matches[0]


def event(output, *, branch, phase, started, run_id, plan_digest, deadline=None, **details):
    require(deadline is None or time.monotonic() < deadline, "combined event write deadline expired")
    record = {"branch": branch, "phase": phase, "elapsed_seconds": time.monotonic() - started,
              "run_id": run_id, "plan_digest": plan_digest, **details}
    data = canonical_bytes(record, newline=True)
    with (output / "startup-events.jsonl").open("ab", buffering=0) as stream:
        require(deadline is None or time.monotonic() < deadline, "combined event write deadline expired")
        require(stream.write(data) == len(data), "combined event append was incomplete")


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
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                wintypes.DWORD, ctypes.c_void_p]
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
    class Accounting(ctypes.Structure):
        _fields_ = [(name, ctypes.c_int64) for name in
                    ("TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")]
        _fields_ += [(name, wintypes.DWORD) for name in
                     ("TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")]

    class Processes(ctypes.Structure):
        _fields_ = [("assigned", wintypes.DWORD), ("listed", wintypes.DWORD),
                    ("pids", ctypes.c_size_t * 64)]

    closed = False
    termination_observation = None

    def close():
        nonlocal closed
        if not closed:
            if not kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
            closed = True

    def request_termination():
        # Stop owned work promptly, but retain the handle for deferred measured
        # cleanup when starting a retirement thread is impossible. Closing here
        # would destroy the only authoritative descendant accounting handle.
        nonlocal termination_observation
        require(not closed, "owned worker job already closed before cleanup observation")
        if termination_observation is None:
            members = Processes()
            if not kernel.QueryInformationJobObject(handle, 3, ctypes.byref(members), ctypes.sizeof(members), None):
                raise ctypes.WinError(ctypes.get_last_error())
            termination_observation = {
                "kind": "owned-windows-job", "initial_process_ids": list(members.pids)[:members.listed],
                "active_processes_after_termination": None}
        if not kernel.TerminateJobObject(handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def terminate(timeout):
        # Closing a job starts asynchronous teardown. A bootstrap's successful
        # exit does not establish that descendants released inherited log pipes.
        # Keep the owned job queryable until every associated process is gone.
        deadline = time.monotonic() + max(0, timeout)
        try:
            request_termination()
            observation = copy.deepcopy(termination_observation)
            while True:
                accounting = Accounting()
                if not kernel.QueryInformationJobObject(handle, 1, ctypes.byref(accounting),
                                                        ctypes.sizeof(accounting), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                if accounting.ActiveProcesses == 0:
                    observation["active_processes_after_termination"] = 0
                    return observation
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("owned worker job descendants did not terminate")
                time.sleep(min(0.005, remaining))
        finally:
            primary = sys.exception()
            try:
                close()
            except Exception as secondary:
                if primary is None:
                    raise
                primary.add_note("owned worker job close failed: " + str(secondary)[:2000])

    close.terminate = terminate
    close.request_termination = request_termination
    return close


def _posix_group_members(group_id):
    """Linux observations exclude zombies, which cannot keep work/pipes alive.

    Other POSIX systems lack this procfs interface: signal delivery plus leader
    and pipe exit are retained there, without claiming a measured group count.
    """
    if not sys.platform.startswith("linux"):
        return None
    members = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == group_id:
                members.append({"pid": int(entry.name), "state": fields[0]})
        except (ProcessLookupError, FileNotFoundError):
            # A process can disappear between the directory and stat reads.
            continue
    return members


def _reap(process, close_job, term_seconds, kill_seconds):
    # Also clean descendants after a normal primary-process exit.
    tree_cleanup = None
    if close_job is not None:
        terminate = getattr(close_job, "terminate", None)
        if terminate is None:
            close_job()
        else:
            tree_cleanup = terminate(kill_seconds)
    elif os.name == "posix":
        initial = _posix_group_members(process.pid)
        tree_cleanup = {"kind": "owned-posix-session", "group_id": process.pid,
                        "initial_process_ids": None if initial is None else [p["pid"] for p in initial],
                        "active_processes_after_termination": None}
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
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait(timeout=kill_seconds)
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        end = time.monotonic() + max(0, kill_seconds)
        while True:
            members = _posix_group_members(process.pid)
            if members is None:
                break
            if not any(p["state"] not in {"Z", "X", "x"} for p in members):
                tree_cleanup.update(active_processes_after_termination=0,
                                    terminated_zombie_process_ids=[p["pid"] for p in members])
                break
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("owned worker process group descendants did not terminate")
            time.sleep(min(0.005, remaining))
    return tree_cleanup


def _force_reap(process, close_job, timeout, *, defer_job_close=False):
    """Attempt every owned resource after a normal cleanup operation fails."""
    errors = []
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception as error:
            errors.append(str(error)[:2000])
    if close_job is not None:
        try:
            request = getattr(close_job, "request_termination", None)
            if defer_job_close and request is not None:
                request()
            else:
                close_job()
        except Exception as error:
            errors.append(str(error)[:2000])
            # A failed stop request cannot leave the job running. Kill-on-close
            # remains the fail-closed fallback, without claiming measured proof.
            try:
                close_job()
            except Exception as secondary:
                errors.append(str(secondary)[:2000])
    try:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=timeout)
    except Exception as error:
        errors.append(str(error)[:2000])
    return errors


def _resume_windows_worker(process):
    """Resume only the initial thread of our still-suspended owned launcher.

    Popen closes CreateProcess's initial thread handle. Enumerate the owned
    process's thread to reopen it; no unrelated process/thread is modified.
    """
    import ctypes
    from ctypes import wintypes

    class ThreadEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
                    ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG), ("dwFlags", wintypes.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ("Thread32First", "Thread32Next"):
        getattr(kernel, name).argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenThread.restype = wintypes.HANDLE
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    thread = None
    try:
        entry = ThreadEntry(); entry.dwSize = ctypes.sizeof(entry)
        found = []
        more = kernel.Thread32First(snapshot, ctypes.byref(entry))
        while more:
            if entry.th32OwnerProcessID == process.pid:
                found.append(entry.th32ThreadID)
            more = kernel.Thread32Next(snapshot, ctypes.byref(entry))
        require(len(found) == 1, "owned suspended launcher must have one initial thread")
        thread = kernel.OpenThread(2, False, found[0])  # THREAD_SUSPEND_RESUME
        if not thread or kernel.ResumeThread(thread) != 1:
            raise OSError("cannot resume owned suspended worker launcher")
    finally:
        if thread:
            kernel.CloseHandle(thread)
        kernel.CloseHandle(snapshot)


def _launch_worker(command, *, cwd, env):
    """Assign the suspended Windows launcher before any interpreter can spawn.

    Assigning a running short-lived worker races its exit. A pipe-gated Python
    The pipe gate alone cannot stop a venv redirector creating its interpreter
    before assignment. CREATE_SUSPENDED covers that launcher race as well.
    The Python gate stays closed until the owned job and resume both succeed.
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
        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP | 0x4) if gated else 0)  # CREATE_SUSPENDED
    job = None
    try:
        job = _windows_job(process)
        if gated:
            _resume_windows_worker(process)
            process.stdin.write(b"1")
            process.stdin.flush()
            process.stdin.close()
        return process, job
    except BaseException as primary:
        if gated and not process.stdin.closed:
            try:
                process.stdin.close()
            except Exception as cleanup:
                primary.add_note("worker launch gate cleanup failed: " + str(cleanup)[:2000])
        try:
            _reap(process, job, 0.2, 5)
        except Exception as cleanup:
            primary.add_note("worker launch cleanup failed: " + str(cleanup)[:2000])
            for secondary in _force_reap(process, job, 5):
                primary.add_note("worker launch fallback cleanup failed: " + secondary)
        for pipe in (process.stdout, process.stderr):
            try:
                pipe.close()
            except Exception as cleanup:
                primary.add_note("worker launch pipe cleanup failed: " + str(cleanup)[:2000])
        raise


def _drain(pipe, path):
    retained = 0
    try:
        with path.open("wb") as stream:
            while True:
                chunk = pipe.read(65536)
                if not chunk:
                    break
                keep = min(len(chunk), max(0, LOG_LIMIT - retained))
                stream.write(chunk[:keep])
                retained += keep
    finally:
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
    children = copy.deepcopy(children)
    validators = dict(validators)
    terminal_deadline = deadline + 30 if terminal_deadline is None else terminal_deadline
    require(all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                for value in (deadline, terminal_deadline, readiness_seconds, term_seconds, kill_seconds)) and
            terminal_deadline >= deadline and readiness_seconds > 0 and term_seconds >= 0 and kill_seconds >= 0,
            "finite ordered work/terminal deadlines and cleanup/readiness bounds required")
    require(not output.exists(), "new combined output required")
    output.mkdir(parents=True)
    started = time.monotonic() if started is None else started
    results = {branch: {"run_id": run_id + "-" + branch, "parent_run_id": run_id,
                       "child_plan_digest": spec.get("child_plan_digest"),
                       "material_bindings": spec.get("materials"),
                       "outcome": "not-started", "last_phase": "pending", "error": None,
                       "assigned_device": spec.get("device"), "return_code": None,
                       "reserved_counters": None, "actual_counters": None,
                       "artifacts": {}, "launch_count": 0} for branch, spec in children.items()}
    active = {}
    retiring = {}
    deferred_retirement = {}
    retirement_expired = set()
    result_lock = threading.Lock()
    event_lock = threading.Lock()
    event_condition = threading.Condition(event_lock)
    event_queue = queue.Queue()
    pending_events = {}
    event_errors = []
    accepting_events = True
    event_thread = None
    event_thread_started = False
    next_branch = 0
    shared_error = None

    def emit(branch, phase, **details):
        with event_lock:
            require(accepting_events, "combined event submission closed at terminal deadline")
            pending_events[branch] = pending_events.get(branch, 0) + 1
            event_queue.put((branch, phase, copy.deepcopy({
                "observed_elapsed_seconds": time.monotonic() - started, **details})))

    def drain_events():
        while True:
            item = event_queue.get()
            if item is None:
                return
            branch, phase, details = item
            error = None
            try:
                event(output, branch=branch, phase=phase, started=started,
                      run_id=run_id, plan_digest=plan_digest, deadline=terminal_deadline, **details)
            except BaseException as exception:
                error = {"branch": branch, "phase": phase, "message": str(exception)[:2000]}
            finally:
                # Only queue bookkeeping is locked. Event disk IO cannot hold
                # the scheduler's readiness/admission/exit observation gate.
                with event_lock:
                    if error is not None:
                        event_errors.append(error)
                    pending_events[branch] -= 1
                    event_condition.notify_all()

    def reconcile_events(errors, pending):
        for observation in errors:
            targets = ("m2", "m3") if observation["branch"] == "shared" else (observation["branch"],)
            for branch in targets:
                result = results[branch]
                result["event_error"] = observation["message"]
                if result["outcome"] == "complete":
                    result.update(outcome="failed", error="worker terminal event failed: " + observation["message"])
        for branch in pending:
            targets = ("m2", "m3") if branch == "shared" else (branch,)
            for target in targets:
                result = results[target]
                result["event_error"] = "combined event drain did not terminate"
                if result["outcome"] == "complete":
                    result.update(outcome="failed", error=result["event_error"])

    def finalize(branch, worker, outcome, error, *, run_callbacks=True):
        result = copy.deepcopy(results[branch])
        cleanup_errors = list(worker.get("retirement_start_errors", []))
        try:
            remaining = max(0, terminal_deadline - time.monotonic())
            tree_cleanup = _reap(worker["process"], worker["job"], min(term_seconds, remaining / 3),
                                 min(kill_seconds, remaining / 3))
            if tree_cleanup is not None:
                result["process_tree_cleanup"] = tree_cleanup
        except Exception as exception:
            cleanup_errors.append(str(exception)[:2000])
            cleanup_errors.extend(getattr(exception, "__notes__", []))
            # Retry only owned-tree termination, even when the primary already
            # exited. Killing just Popen would leave its grandchildren alive.
            cleanup_errors.extend(_force_reap(worker["process"], worker["job"],
                min(kill_seconds, max(0, terminal_deadline - time.monotonic()))))
        for thread in worker["threads"]:
            # Drain completion is bounded by the common terminal reserve. The
            # process kill grace is not a deadline for Python reader scheduling.
            thread.join(timeout=max(0, terminal_deadline - time.monotonic()))
            if thread.is_alive():
                cleanup_errors.append("worker log drain did not terminate")
        for pipe in worker["undrained_pipes"]:
            try:
                pipe.close()
            except Exception as exception:
                cleanup_errors.append(str(exception)[:2000])
        cleanup_errors.extend(worker["drain_errors"])
        root = output / branch
        if outcome == "verify":
            # The scheduler observed leader exit inside the work budget. Stop
            # descendants and release pipes before reading candidate artifacts;
            # verification consumes the terminal reserve, not new model work.
            outcome, error = "failed", "worker cleanup prevented independent verification"
            if not cleanup_errors:
                try:
                    require(worker["ready"], "worker exited without model-ready")
                    terminal = verify_envelope(root, run_id=run_id, plan_digest=plan_digest,
                                               branch=branch, deadline=terminal_deadline)
                    verified = copy.deepcopy(validators[branch](root))
                    canonical_bytes(verified)
                    require(_same_json(terminal.get("actual_counters"), verified),
                            "child counters differ from independent verification")
                    require(_same_json(terminal.get("device"), children[branch].get("device")) and
                            (children[branch].get("child_plan_digest") is None or
                             terminal.get("child_plan_digest") == children[branch]["child_plan_digest"]),
                            "child terminal device or plan binding differs")
                    require(time.monotonic() < terminal_deadline, "terminal verification deadline expired")
                    result["verification"] = verified
                    outcome, error = "complete", None
                except BaseException as exception:
                    error = type(exception).__name__ + ": " + str(exception)[:2000]
        result.update(outcome=outcome, return_code=worker["process"].returncode,
                      error=error, supervisor_error=error, ready_observed=worker["ready"],
                      process_exit_confirmed=worker["process"].returncode is not None,
                      log_drain_confirmed=not any(t.is_alive() for t in worker["threads"]),
                      wall_seconds=time.monotonic() - worker["started"])
        for name in ("worker-state.json", "worker-terminal.json"):
            if (root / name).is_file():
                try:
                    value = read(member(root, name))
                    require(value.get("branch") == branch and value.get("run_id") == run_id + "-" + branch and
                            value.get("parent_run_id") == run_id and
                            value.get("plan_digest") == plan_digest, "child diagnostic binding differs")
                    result["last_phase"] = value.get("phase", result["last_phase"])
                    result["reserved_counters"] = value.get("reserved_counters")
                    result["actual_counters"] = value.get("actual_counters")
                    if value.get("error"):
                        result["worker_error"] = value["error"]
                        if error in (None, "worker returned nonzero"):
                            result["error"] = value["error"]
                except Exception as exception:
                    result["diagnostic_error"] = str(exception)[:2000]
        if outcome != "complete" and children[branch].get("diagnostics") is not None:
            if not run_callbacks:
                result.update(partial_diagnostics_skipped=True, actual_counters=None,
                              counter_evidence="partial diagnostics skipped: retirement thread unavailable; "
                                               "unreconciled actual work remains unknown")
            else:
                try:
                    partial = copy.deepcopy(children[branch]["diagnostics"](root))
                    require(isinstance(partial, dict) and set(partial) <= {
                        "reserved_counters", "actual_counters", "stage_outcomes", "counter_evidence"},
                        "partial diagnostics cannot change supervisor disposition or identity")
                    canonical_bytes(partial)  # Reject values that would poison the aggregate.
                    result.update(partial)
                except BaseException as exception:
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
            if result["outcome"] == "complete":
                result.update(outcome="failed", error="worker artifact retention failed: " + str(exception)[:2000])
        if cleanup_errors:
            result.update(outcome="failed", cleanup_errors=cleanup_errors)
        try:
            emit(branch, "retirement-observed", observed_outcome=result["outcome"],
                 authoritative_terminal=False, authoritative_source="aggregate-terminal.json",
                 return_code=result["return_code"], error=result["error"])
        except Exception as exception:
            result["event_error"] = str(exception)[:2000]
            if result["outcome"] == "complete":
                result.update(outcome="failed", error="worker terminal event failed: " + str(exception)[:2000])
        with result_lock:
            if branch not in retirement_expired:
                results[branch] = result

    def finish(branch, outcome, error=None):
        worker = active[branch]
        result = results[branch]
        try:
            exit_code = worker["process"].poll()
        except Exception as exception:
            result["poll_error"] = str(exception)[:2000]
            exit_code = worker["process"].returncode
            outcome, error = "failed", error or "worker process poll failed: " + str(exception)[:2000]
        active.pop(branch)  # Poll failure must not discard cleanup ownership.
        result.update(exit_code_before_stop=exit_code,
                      stop_reason=outcome, disposition_observed_seconds=time.monotonic() - started)

        def complete_retirement(*, run_callbacks=True):
            try:
                finalize(branch, worker, outcome, error, run_callbacks=run_callbacks)
            except BaseException as exception:
                emergency_errors = _force_reap(worker["process"], worker["job"],
                    min(kill_seconds, max(0, terminal_deadline - time.monotonic())))
                with result_lock:
                    if branch not in retirement_expired:
                        results[branch].update(outcome="failed", return_code=worker["process"].returncode,
                                              error=error or type(exception).__name__ + ": " + str(exception)[:2000],
                                              finalization_error=str(exception)[:2000],
                                              cleanup_errors=emergency_errors)

        # A branch's cleanup/log scheduling must not suspend its sibling's work
        # watchdog or admission. All trees start retiring before we join any.
        try:
            thread = threading.Thread(target=complete_retirement, daemon=True)
            retiring[branch] = thread
            thread.start()
        except Exception as exception:
            retiring.pop(branch, None)
            worker["retirement_start_errors"] = ["worker retirement thread startup failed: " + str(exception)[:2000]]
            worker["retirement_start_errors"].extend(_force_reap(worker["process"], worker["job"], 0,
                                                                  defer_job_close=True))
            # Stop owned work now, but defer log joins/hashing until no active
            # sibling needs admission or watchdog observation. No new thread
            # is needed to recover from a thread-creation refusal.
            deferred_retirement[branch] = complete_retirement

    try:
        event_thread = threading.Thread(target=drain_events, daemon=True)
        event_thread.start()
        event_thread_started = True
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
                if not worker["ready"] and time.monotonic() - worker["started"] >= readiness_seconds:
                    finish(branch, "timed-out", "bounded model-ready wait expired")
                    continue
                if not worker["ready"] and (root / "model-ready.json").is_file():
                    try:
                        ready = read(member(root, "model-ready.json"))
                        require(ready.get("branch") == branch and ready.get("run_id") == run_id + "-" + branch and
                                ready.get("parent_run_id") == run_id and
                                ready.get("plan_digest") == plan_digest and
                                _same_json(ready.get("device"), children[branch].get("device")),
                                "model-ready binding differs")
                        if time.monotonic() - worker["started"] >= readiness_seconds:
                            finish(branch, "timed-out", "bounded model-ready wait expired")
                            continue
                        worker["ready"] = True
                        results[branch]["last_phase"] = "work"
                        emit(branch, "model-ready", device=ready.get("device"))
                    except Exception as exception:
                        finish(branch, "failed", str(exception)[:2000])
                        continue
                try:
                    code = worker["process"].poll()
                except Exception as exception:
                    results[branch]["poll_error"] = str(exception)[:2000]
                    finish(branch, "failed", "worker process poll failed: " + str(exception)[:2000])
                    continue
                observed = time.monotonic()
                if observed >= deadline:
                    finish(branch, "timed-out", "global monotonic work deadline exceeded")
                elif not worker["ready"] and observed - worker["started"] >= readiness_seconds:
                    finish(branch, "timed-out", "bounded model-ready wait expired")
                elif code is not None:
                    finish(branch, "verify" if code == 0 else "failed",
                           None if code == 0 else "worker returned nonzero")
            can_launch = (next_branch == 0 or "m2" not in active or active["m2"]["ready"])
            if next_branch < 2 and can_launch and time.monotonic() < deadline:
                branch = ("m2", "m3")[next_branch]
                next_branch += 1
                spec = children[branch]
                root = output / branch
                try:
                    results[branch]["last_phase"] = "preparing"
                    root.mkdir()
                    env = {**os.environ, **spec.get("env", {}), "PYTHONIOENCODING": "utf-8"}
                    if spec.get("device") is not None:
                        env["CUDA_VISIBLE_DEVICES"] = spec["device"]["uuid"]
                    if time.monotonic() >= deadline:
                        results[branch].update(outcome="timed-out", error="global deadline before launch")
                        continue
                    results[branch].update(launch_attempt_count=1, last_phase="launching")
                    process, job = _launch_worker(spec["command"], cwd=spec.get("cwd"), env=env)
                    results[branch]["launch_count"] = 1
                    worker = {"process": process, "job": job, "threads": [], "drain_errors": [],
                              "undrained_pipes": [process.stdout, process.stderr],
                              "started": time.monotonic(), "ready": False}
                    active[branch] = worker  # Own the tree before acquiring log resources.

                    def drain(pipe, path, worker=worker):
                        try:
                            _drain(pipe, path)
                        except BaseException as exception:
                            worker["drain_errors"].append("worker log drain failed: " + str(exception)[:2000])

                    for pipe, name in ((process.stdout, "stdout.log"), (process.stderr, "stderr.log")):
                        thread = threading.Thread(target=drain, args=(pipe, root / name), daemon=True)
                        thread.start()
                        worker["threads"].append(thread)
                        worker["undrained_pipes"].remove(pipe)
                    results[branch].update(last_phase="loading")
                    emit(branch, "launch", pid=process.pid, device=spec.get("device"))
                except Exception as exception:
                    error = str(exception)[:2000]
                    if getattr(exception, "__notes__", None):
                        results[branch]["launch_cleanup_errors"] = list(exception.__notes__)
                    if branch in active:
                        finish(branch, "failed", error)
                    else:
                        results[branch].update(outcome="failed", error=error)
                    emit(branch, "launch-failed", error=error)
            time.sleep(min(0.02, max(0, deadline - time.monotonic())))
    except Exception as exception:
        shared_error = {"type": type(exception).__name__, "message": str(exception)[:2000]}
        try:
            emit("shared", "failed", error=shared_error)
        except Exception as secondary:
            shared_error["event_error"] = str(secondary)[:2000]
    finally:
        for branch in list(active):
            finish(branch, "failed", "shared supervisor failure")
        for branch, complete_retirement in deferred_retirement.items():
            complete_retirement(run_callbacks=False)
            results[branch]["retirement_completed"] = True
        for branch, thread in retiring.items():
            thread.join(timeout=max(0, terminal_deadline - time.monotonic()))
            with result_lock:
                if thread.is_alive():
                    retirement_expired.add(branch)
                    results[branch].update(outcome="failed", finalization_error="worker retirement did not terminate",
                                           retirement_completed=False)
                else:
                    results[branch]["retirement_completed"] = True
        if shared_error:
            for result in results.values():
                if result["outcome"] == "not-started":
                    result.update(outcome="failed", last_phase="shared-setup", error=shared_error["message"])
        with event_condition:
            accepting_events = False
            while event_thread_started and any(pending_events.values()) and time.monotonic() < terminal_deadline:
                event_condition.wait(timeout=max(0, terminal_deadline - time.monotonic()))
            initial_event_errors = copy.deepcopy(event_errors)
            initial_pending_events = {b: count for b, count in pending_events.items() if count}
        # Semantic retirement is provisional. Reconcile all preceding event IO
        # before publishing a final branch terminal disposition.
        reconcile_events(initial_event_errors, initial_pending_events)
        with event_lock:
            if event_thread_started and not initial_pending_events and time.monotonic() < terminal_deadline:
                for branch, result in results.items():
                    pending_events[branch] = pending_events.get(branch, 0) + 1
                    event_queue.put((branch, "terminal", copy.deepcopy({
                        "observed_elapsed_seconds": time.monotonic() - started,
                        "outcome": result["outcome"], "return_code": result["return_code"],
                        "error": result["error"], "authoritative_terminal": False,
                        "authoritative_source": "aggregate-terminal.json"})))
            event_queue.put(None)
        if event_thread_started:
            event_thread.join(timeout=max(0, terminal_deadline - time.monotonic()))
        with event_lock:
            observed_event_errors = copy.deepcopy(event_errors)
            observed_pending_events = {b: count for b, count in pending_events.items() if count}
        reconcile_events(observed_event_errors, observed_pending_events)
        completed = sum(item["outcome"] == "complete" for item in results.values())
        outcome = ("complete" if completed == 2 else "partial" if completed else
                   "timed-out" if any(r["outcome"] == "timed-out" for r in results.values()) else "failed")
        manifest = {"format": "irisx/nvarc-combined-terminal-v1", "run_id": run_id,
                    "plan_digest": plan_digest, "outcome": outcome, "branches": copy.deepcopy(results),
                    "shared_error": shared_error, "wall_seconds": time.monotonic() - started,
                    "event_errors": observed_event_errors, "pending_events": observed_pending_events,
                    "event_drain_confirmed": not observed_pending_events,
                    "event_thread_exit_confirmed": event_thread_started and not event_thread.is_alive(),
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
