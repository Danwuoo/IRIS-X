"""Linux-only owned worker, original deadline, and exclusive source-bound receipts."""

from collections import Counter
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from tools.public_sft141_submission.contract import (FROZEN_SCHEMA, canonical, digest,
    exact_fields, read_frozen, validate_challenge)
from tools.public_sft141_submission.files import (load_json, parent_directory, read_bytes,
    safe_path, _atomic_file)

from . import METHOD_VERSION
from .search import RANKING, TEMPLATES, Work, solve_task

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATHS = (
    "tools/__init__.py",
    "tools/public_cpu_arc_search/__init__.py",
    "tools/public_cpu_arc_search/__main__.py",
    "tools/public_cpu_arc_search/search.py",
    "tools/public_cpu_arc_search/runtime.py",
    "tools/public_sft141_diagnostic/__init__.py",
    "tools/public_sft141_diagnostic/contract.py",
    "tools/public_sft141_submission/__init__.py",
    "tools/public_sft141_submission/contract.py",
    "tools/public_sft141_submission/files.py",
)
PLAN_SCHEMA = "iris-public-cpu-search-plan-v1"
PLAN_FIELDS = {"schema", "method", "challenge_path", "challenge_sha256", "inventory",
               "source_files", "source_sha256", "grammar_sha256", "seconds", "ranking"}


def source_manifest():
    files = {name: digest(read_bytes(ROOT / name)) for name in SOURCE_PATHS}
    return files, digest(canonical(files))


def new_directory(path):
    with parent_directory(path) as (directory, parent):
        os.mkdir(directory.name, 0o700, dir_fd=parent)
    return directory


def write_new(path, value):
    """Atomic hard-link publication, never replacement, including empty files."""
    with parent_directory(path) as (path, parent):
        _atomic_file(path.parent, parent, path.name, canonical(value))
        os.fsync(parent)


def inventory(challenge):
    return [{"task_id": task_id, "test_count": len(challenge[task_id]["test"])}
            for task_id in sorted(challenge)]


def make_plan(challenge_path, seconds):
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 600:
        raise ValueError("whole-process budget must be finite and in (0, 600] seconds")
    challenge, raw = load_json(challenge_path)
    validate_challenge(challenge)
    files, source_hash = source_manifest()
    return {"schema": PLAN_SCHEMA, "method": METHOD_VERSION,
            "challenge_path": str(safe_path(challenge_path)), "challenge_sha256": digest(raw),
            "inventory": inventory(challenge), "source_files": files, "source_sha256": source_hash,
            "grammar_sha256": digest(canonical(TEMPLATES)), "seconds": seconds, "ranking": RANKING}


def load_bound_plan(path):
    plan, raw = load_json(path)
    exact_fields(plan, PLAN_FIELDS, "search plan")
    if raw != canonical(plan):
        raise ValueError("search plan must use canonical JSON bytes")
    # Rebuild all declarations rather than trusting a task count or source flag.
    rebuilt = make_plan(plan["challenge_path"], plan["seconds"])
    if plan != rebuilt:
        raise ValueError("plan binding mismatch: source, challenge, grammar, inventory or method changed")
    return plan, raw


def check_bindings(plan):
    if source_manifest() != (plan["source_files"], plan["source_sha256"]):
        raise ValueError("source bytes changed")
    if digest(read_bytes(plan["challenge_path"])) != plan["challenge_sha256"]:
        raise ValueError("challenge bytes changed")


def worker(plan_path, output_dir, work_deadline_epoch):
    """Only source + gold-free challenge are opened; no scoring module exists here."""
    plan, plan_raw = load_bound_plan(plan_path)
    challenge, challenge_raw = load_json(plan["challenge_path"])
    if digest(challenge_raw) != plan["challenge_sha256"]:
        raise ValueError("worker loaded challenge bytes differ from plan")
    output = safe_path(output_dir)
    admission, _ = load_json(output / "admission.json")
    if (admission["plan_sha256"] != digest(plan_raw)
            or admission["work_deadline_epoch"] != work_deadline_epoch):
        raise ValueError("worker admission binding mismatch")
    work = Work(time.monotonic() + max(0, min(plan["seconds"], work_deadline_epoch - time.time())))
    started, cpu_started = time.monotonic(), time.process_time()
    completed = 0
    for index, item in enumerate(plan["inventory"]):
        if time.monotonic() >= work.deadline:
            break
        task_id = item["task_id"]
        receipt = solve_task(task_id, challenge[task_id], work)
        receipt.update(plan_sha256=digest(plan_raw), challenge_sha256=plan["challenge_sha256"],
                       source_sha256=plan["source_sha256"])
        write_new(output / f"task-{index:06d}.json", receipt)
        if receipt["status"] != "complete":
            break
        completed += 1
    check_bindings(plan)
    result = {"schema": "iris-public-cpu-worker-v1", "plan_sha256": digest(plan_raw),
              "source_sha256": plan["source_sha256"], "challenge_sha256": plan["challenge_sha256"],
              "completed_tasks": completed, "all_tasks_complete": completed == len(plan["inventory"]),
              "counts": dict(sorted(work.counters.items())),
              "wall_seconds": time.monotonic() - started,
              "cpu_seconds": time.process_time() - cpu_started, "pid": os.getpid()}
    write_new(output / "worker.json", result)
    return 0


def collect(plan, output, plan_hash):
    """Every planned task and true task.test index remains in the final inventory."""
    tasks, hashes, counts, frozen = [], {}, Counter(), {}
    for index, expected in enumerate(plan["inventory"]):
        name = f"task-{index:06d}.json"
        path = output / name
        task_id = expected["task_id"]
        row = {"task_id": task_id, "status": "not_completed", "receipt_file": None,
               "queries": [{"test_index": i, "status": "not_completed", "candidate_count": 0}
                           for i in range(expected["test_count"])]}
        frozen[task_id] = {str(i): [] for i in range(expected["test_count"])}
        if path.exists():
            receipt, raw = load_json(path)
            hashes[name] = digest(raw)
            if (receipt.get("task_id") != task_id or receipt.get("plan_sha256") != plan_hash
                    or receipt.get("source_sha256") != plan["source_sha256"]
                    or receipt.get("challenge_sha256") != plan["challenge_sha256"]
                    or len(receipt.get("queries", [])) != expected["test_count"]):
                raise ValueError("task receipt binding or inventory mismatch")
            if receipt["status"] not in ("complete", "partial"):
                raise ValueError("invalid receipt completion state")
            if receipt["status"] == "complete" and (
                    len(receipt["attempts"]) != len(TEMPLATES)
                    or any(a["status"] == "interrupted" for a in receipt["attempts"])):
                raise ValueError("complete receipt lacks full template inventory")
            row.update(status=receipt["status"], receipt_file=name)
            counts.update(receipt["counts"])
            for i, query in enumerate(receipt["queries"]):
                if query["test_index"] != i:
                    raise ValueError("query ordering mismatch")
                candidates = [candidate["grid"] for candidate in query["candidates"]]
                if receipt["status"] != "complete" and candidates:
                    raise ValueError("partial search must not issue ranked predictions")
                frozen[task_id][str(i)] = candidates
                row["queries"][i].update(status=query["status"], candidate_count=len(candidates))
        tasks.append(row)
    return tasks, hashes, dict(sorted(counts.items())), frozen


def _kill_owned(process):
    # Popen is created here with start_new_session=True; no external PID accepted.
    # No shell, process lookup, global pkill, parent-group or Windows fallback.
    if process is not None and process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run(plan_path, output_dir, started_epoch):
    if not sys.platform.startswith("linux"):
        raise ValueError("Linux session/process-group admission is required; no unsafe fallback")
    started_wall = time.time()
    if (type(started_epoch) not in (int, float) or not math.isfinite(started_epoch)
            or started_epoch > started_wall):
        raise ValueError("finite original pre-dispatch --started-epoch, not future time, is required")
    plan, plan_raw = load_bound_plan(plan_path)
    deadline_epoch = started_epoch + plan["seconds"]
    remaining = min(plan["seconds"], deadline_epoch - time.time())
    if remaining <= 0:
        raise ValueError("original deadline expired before admission; do not reset it")
    process = None
    old_handler = signal.getsignal(signal.SIGALRM)

    def hard_deadline(_signum, _frame):
        _kill_owned(process)
        # Fail closed if reserve is exhausted. A missing closure is not a result.
        os._exit(124)

    signal.signal(signal.SIGALRM, hard_deadline)
    signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        output = new_directory(output_dir)
        reserve = min(2.0, remaining * 0.25)
        work_deadline = deadline_epoch - reserve
        plan_hash = digest(plan_raw)
        write_new(output / "plan.json", plan)
        admission = {"schema": "iris-public-cpu-admission-v1", "plan_sha256": plan_hash,
                     "source_sha256": plan["source_sha256"], "challenge_sha256": plan["challenge_sha256"],
                     "started_epoch": started_epoch, "deadline_epoch": deadline_epoch,
                     "work_deadline_epoch": work_deadline, "inventory": plan["inventory"],
                     "linux_owned_session": True, "supervisor_pid": os.getpid(),
                     "claim": "planned CPU search, not execution or accuracy success"}
        write_new(output / "admission.json", admission)
        timed_out = False
        command = [sys.executable, "-B", "-X", f"pycache_prefix={output / 'unused-pycache'}", "-m",
                   "tools.public_cpu_arc_search", "_worker", "--plan", str(output / "plan.json"),
                   "--output-dir", str(output), "--work-deadline-epoch", repr(work_deadline)]
        # Original absolute deadline includes validation and process startup.
        with open(output / "worker.log", "xb") as log:
            process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                process.wait(timeout=max(0, work_deadline - time.time()))
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_owned(process)
        # All result collection and sealing is strictly after worker exit.
        integrity_error = None
        try:
            check_bindings(plan)
        except (OSError, ValueError) as exc:
            integrity_error = str(exc)
        tasks, receipt_hashes, counts, queries = collect(plan, output, plan_hash)
        worker_result = None
        if (output / "worker.json").exists():
            worker_result, raw = load_json(output / "worker.json")
            receipt_hashes["worker.json"] = digest(raw)
            if (worker_result["plan_sha256"] != plan_hash
                    or worker_result["source_sha256"] != plan["source_sha256"]
                    or worker_result["challenge_sha256"] != plan["challenge_sha256"]
                    or worker_result["pid"] != process.pid):
                raise ValueError("worker summary binding mismatch")
        complete = (process.returncode == 0 and not timed_out and not integrity_error
                    and worker_result is not None and worker_result["all_tasks_complete"]
                    and all(row["status"] == "complete" for row in tasks))
        if integrity_error:
            # Never expose contaminated predictions as an admissible candidate artifact.
            queries = {task: {index: [] for index in indexed} for task, indexed in queries.items()}
        frozen = {"schema": FROZEN_SCHEMA, "challenge_sha256": plan["challenge_sha256"],
                  "strategy": "frozen", "strategy_chosen_before_gold": True, "queries": queries}
        if not integrity_error:
            challenge, _ = load_json(plan["challenge_path"])
            read_frozen(frozen, challenge, plan["challenge_sha256"], "frozen")
        write_new(output / "frozen_candidates.json", frozen)
        receipt_hashes["frozen_candidates.json"] = digest(canonical(frozen))
        receipt_hashes["worker.log"] = digest(read_bytes(output / "worker.log"))
        receipt_hashes["admission.json"] = digest(canonical(admission))
        receipt_hashes["plan.json"] = digest(plan_raw)
        predicted = sum(bool(grids) for indexed in queries.values() for grids in indexed.values())
        closure = {"schema": "iris-public-cpu-closure-v1", "method": METHOD_VERSION,
                   "plan_sha256": plan_hash, "source_sha256": plan["source_sha256"],
                   "challenge_sha256": plan["challenge_sha256"], "worker_pid": process.pid,
                   "worker_exited": True, "worker_returncode": process.returncode,
                   "timed_out": timed_out, "integrity_error": integrity_error,
                   "status": "complete" if complete else "partial", "search_complete": complete,
                   "sealed_for_scoring": complete, "tasks": tasks,
                   "task_count": len(tasks), "query_count": sum(x["test_count"] for x in plan["inventory"]),
                   "predicted_query_count": predicted, "counts": counts,
                   "worker_cpu_seconds": None if worker_result is None else worker_result["cpu_seconds"],
                   "whole_run_wall_seconds": time.time() - started_epoch,
                   "started_epoch": started_epoch, "deadline_epoch": deadline_epoch,
                   "source_and_challenge_unchanged": not integrity_error,
                   "files": receipt_hashes, "accuracy_evaluated": False,
                   "qualification": "Independent fixed-program CPU candidates. Exact demonstration replay and LOO are not test accuracy; no learned-model or author-method claim."}
        write_new(output / "closure.json", closure)
        return closure
    finally:
        _kill_owned(process)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


def verify(output_dir):
    """Integrity and semantic closure checks, not cryptographic authentication."""
    output = safe_path(output_dir)
    plan, plan_raw = load_bound_plan(output / "plan.json")
    closure, _ = load_json(output / "closure.json")
    if (closure.get("schema") != "iris-public-cpu-closure-v1"
            or closure.get("plan_sha256") != digest(plan_raw)
            or closure.get("source_sha256") != plan["source_sha256"]
            or closure.get("challenge_sha256") != plan["challenge_sha256"]):
        raise ValueError("closure bindings differ")
    tasks, hashes, counts, queries = collect(plan, output, digest(plan_raw))
    if (closure["tasks"] != tasks or closure["counts"] != counts
            or closure["task_count"] != len(plan["inventory"])
            or closure["query_count"] != sum(x["test_count"] for x in plan["inventory"])):
        raise ValueError("closure inventory differs")
    allowed_files = {"plan.json", "admission.json", "worker.log", "worker.json", "frozen_candidates.json", *hashes}
    required_files = {"plan.json", "admission.json", "worker.log", "frozen_candidates.json", *hashes}
    if (output / "worker.json").exists() or closure["search_complete"] or closure["sealed_for_scoring"]:
        required_files.add("worker.json")
    if not required_files <= set(closure["files"]) <= allowed_files:
        raise ValueError("closure is missing required artifact hashes or includes unexpected files")
    for name, expected_hash in closure["files"].items():
        if digest(read_bytes(output / name)) != expected_hash:
            raise ValueError("sealed file bytes changed: " + name)
    admission, _ = load_json(output / "admission.json")
    exact_fields(admission, {"schema", "plan_sha256", "source_sha256", "challenge_sha256",
        "started_epoch", "deadline_epoch", "work_deadline_epoch", "inventory",
        "linux_owned_session", "supervisor_pid", "claim"}, "admission")
    if (admission["schema"] != "iris-public-cpu-admission-v1"
            or admission["plan_sha256"] != digest(plan_raw)
            or admission["source_sha256"] != plan["source_sha256"]
            or admission["challenge_sha256"] != plan["challenge_sha256"]
            or admission["inventory"] != plan["inventory"]
            or admission["linux_owned_session"] is not True
            or type(admission["supervisor_pid"]) is not int or admission["supervisor_pid"] <= 0):
        raise ValueError("admission binding mismatch")
    for field in ("started_epoch", "deadline_epoch", "work_deadline_epoch"):
        if type(admission[field]) not in (float, int) or not math.isfinite(admission[field]):
            raise ValueError("invalid admission clock")
    if (admission["deadline_epoch"] != admission["started_epoch"] + plan["seconds"]
            or not admission["started_epoch"] < admission["work_deadline_epoch"] < admission["deadline_epoch"]
            or closure["started_epoch"] != admission["started_epoch"]
            or closure["deadline_epoch"] != admission["deadline_epoch"]):
        raise ValueError("original deadline binding differs")
    worker_result = None
    if "worker.json" in closure["files"]:
        worker_result, _ = load_json(output / "worker.json")
        exact_fields(worker_result, {"schema", "plan_sha256", "source_sha256", "challenge_sha256",
            "completed_tasks", "all_tasks_complete", "counts", "wall_seconds", "cpu_seconds", "pid"}, "worker summary")
        if (worker_result["schema"] != "iris-public-cpu-worker-v1"
                or worker_result["plan_sha256"] != digest(plan_raw)
                or worker_result["source_sha256"] != plan["source_sha256"]
                or worker_result["challenge_sha256"] != plan["challenge_sha256"]
                or worker_result["pid"] != closure["worker_pid"]
                or worker_result["completed_tasks"] != sum(t["status"] == "complete" for t in tasks)
                or worker_result["all_tasks_complete"] != all(t["status"] == "complete" for t in tasks)
                or worker_result["counts"] != counts
                or worker_result["cpu_seconds"] != closure["worker_cpu_seconds"]):
            raise ValueError("worker summary binding or counters differ")
        for field in ("wall_seconds", "cpu_seconds"):
            if type(worker_result[field]) not in (int, float) or not math.isfinite(worker_result[field]) or worker_result[field] < 0:
                raise ValueError("worker timings are invalid")
    frozen, _ = load_json(output / "frozen_candidates.json")
    challenge, _ = load_json(plan["challenge_path"])
    read_frozen(frozen, challenge, plan["challenge_sha256"], "frozen")
    if closure["integrity_error"] is None and frozen["queries"] != queries:
        raise ValueError("frozen candidates differ from task receipts")
    expected_complete = (closure["worker_exited"] is True and closure["worker_returncode"] == 0
                         and closure["timed_out"] is False and closure["integrity_error"] is None
                         and closure["source_and_challenge_unchanged"] is True
                         and worker_result is not None and worker_result["all_tasks_complete"] is True
                         and all(t["status"] == "complete" for t in tasks))
    if (closure["search_complete"] is not expected_complete
            or closure["sealed_for_scoring"] is not expected_complete
            or closure["status"] != ("complete" if expected_complete else "partial")
            or closure["accuracy_evaluated"] is not False
            or closure["predicted_query_count"] != sum(bool(v) for rows in frozen["queries"].values() for v in rows.values())):
        raise ValueError("inconsistent complete-run seal")
    if (type(closure["whole_run_wall_seconds"]) not in (int, float)
            or not math.isfinite(closure["whole_run_wall_seconds"])
            or not 0 <= closure["whole_run_wall_seconds"] <= plan["seconds"]):
        raise ValueError("whole-process budget receipt is invalid")
    return closure
