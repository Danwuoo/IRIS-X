"""Original-clock process watchdog, pre-gold selection, post-exit evaluation.

The supervisor and coordinator track exact owned process identities, including
observed descendants that change session. Only the evaluator opens gold; its pathname is never passed to the
model leaf. No stage gets a new
7200-second allowance. Evidence is never overwritten or resumed.
"""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from tools.public_demo_calibration import core
from tools.public_sft141_submission import contract as export_contract
from .common import (ROOT, STRATEGIES, PUBLIC_GOLD_FILE_SHA256, admit, assemble_pool, challenge_from_plan,
    evidence_manifest, frozen, inherited, load_if, read_bytes, reconcile_base,
    sha, sources, verify_evidence, verify_sources, new_artifacts)


def environment():
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_DATASETS_OFFLINE="1",
               TOKENIZERS_PARALLELISM="false", PYTHONDONTWRITEBYTECODE="1")
    return env


def require_linux():
    if (not sys.platform.startswith("linux") or not hasattr(os, "pidfd_open") or
            not hasattr(signal, "pidfd_send_signal") or not hasattr(os, "P_PIDFD")):
        raise ValueError("owned descendant orchestration requires Linux with pidfds; no unsafe platform fallback")
    # Probe the running kernel before any launch, not merely Python's API.
    fd = os.pidfd_open(os.getpid())
    try:
        signal.pidfd_send_signal(fd, 0)
    finally:
        os.close(fd)


def become_subreaper():
    """Adopt and reap our killed descendants even when the coordinator dies."""
    require_linux()
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # Linux PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "cannot establish owned descendant reaping")


class CleanupFailure(RuntimeError):
    """A failed ownership proof cannot be serialized as completed cleanup."""


def _process_snapshot():
    """Bounded kernel stat reads; never infer ownership from names or groups."""
    snapshot = {}
    for path in Path("/proc").iterdir():
        if not path.name.isdecimal():
            continue
        try:
            with (path / "stat").open() as stream:
                raw = stream.read(16385)
        except (FileNotFoundError, ProcessLookupError):
            continue
        if len(raw) > 16384 or ") " not in raw:
            raise CleanupFailure("cannot obtain bounded process identity")
        fields = raw.rsplit(") ", 1)[1].split()
        if len(fields) < 20:
            raise CleanupFailure("incomplete process identity")
        snapshot[int(path.name)] = (int(fields[1]), int(fields[19]))
    return snapshot


class OwnedTree:
    """Exact lineage plus pidfds, including descendants that call setsid.

    Construct before spawning to preserve unrelated existing children. An
    adopted child whose lineage was never observed is not safe to signal: it
    makes cleanup fail closed. This is not a cgroup/hostile-process sandbox.
    """
    def __init__(self, *, before_spawn=True):
        become_subreaper()
        self.owner = os.getpid()
        snapshot = _process_snapshot()
        self.baseline = {(pid, row[1]) for pid, row in snapshot.items()
                         if before_spawn and row[0] == self.owner}
        self.pinned, self.unattributed = {}, set()
        self.process = None
        self.proven = False
        self.failed = False
        self.last = snapshot

    def _pin(self, pid, row):
        identity = (pid, row[1])
        if identity in self.pinned:
            return
        try:
            fd = os.pidfd_open(pid)
        except ProcessLookupError:
            return
        try:
            current = _process_snapshot().get(pid)
        except BaseException:
            os.close(fd)
            raise
        if current != row:
            os.close(fd)
            return
        self.pinned[identity] = fd

    def attach(self, process):
        self.process = process
        snapshot = _process_snapshot()
        row = snapshot.get(process.pid)
        if row is not None:
            if row[0] != self.owner:
                raise CleanupFailure("spawned PID is not our direct child")
            self._pin(process.pid, row)
        self.refresh()

    def refresh(self):
        snapshot = _process_snapshot()
        changed = True
        while changed:
            changed = False
            parents = {pid for pid, born in self.pinned
                       if pid in snapshot and snapshot[pid][1] == born}
            for pid, row in snapshot.items():
                identity = (pid, row[1])
                if row[0] in parents and identity not in self.pinned:
                    self._pin(pid, row)
                    changed = changed or identity in self.pinned
        self.unattributed.update((pid, row[1]) for pid, row in snapshot.items()
            if row[0] == self.owner and (pid, row[1]) not in self.baseline
            and (pid, row[1]) not in self.pinned)
        self.last = snapshot
        return {identity for identity in self.pinned
                if identity[0] in snapshot and snapshot[identity[0]][1] == identity[1]}

    def close(self):
        for fd in self.pinned.values():
            os.close(fd)
        self.pinned.clear()

    def abort_known(self):
        """Best-effort bounded cleanup if inspection fails; never prove success.

        A Popen child is owned even if failure interrupted its initial pin.
        Pidfds remain safe to signal without any new /proc inspection.
        """
        self.proven = False
        self.failed = True
        until = time.monotonic() + 2
        for fd in self.pinned.values():
            try:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if self.process is not None:
            self.process.kill()
            self.process.wait(timeout=max(.001, until - time.monotonic()))
        pending = dict(self.pinned)
        while pending and time.monotonic() < until:
            for identity, fd in tuple(pending.items()):
                try:
                    if os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOHANG) is not None:
                        pending.pop(identity)
                except ChildProcessError:
                    # Already reaped, or still owned by another dying parent.
                    # Retry, but do not turn uncertainty into a success seal.
                    pass
            if pending:
                time.sleep(.005)

    def terminate(self):
        until = time.monotonic() + 2
        try:
            while True:
                live = self.refresh()
                for identity, fd in reversed(tuple(self.pinned.items())):
                    if identity in live:
                        try:
                            signal.pidfd_send_signal(fd, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                self.process.poll()  # Popen, not a broad waitpid, owns its PID.
                for identity, fd in self.pinned.items():
                    if identity[0] == self.process.pid:
                        continue
                    try:
                        os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOHANG)
                    except ChildProcessError:
                        pass  # Its still-exiting tracked parent may own it.
                live = self.refresh()
                if not live and self.process.poll() is not None:
                    if self.unattributed:
                        raise CleanupFailure("unattributed adopted child; cleanup cannot be proven")
                    if self.failed:
                        raise CleanupFailure("prior ownership inspection failed; cleanup cannot be proven")
                    self.proven = True
                    return self.process.returncode
                if time.monotonic() >= until:
                    raise CleanupFailure("tracked owned descendants remain; cleanup cannot be proven")
                time.sleep(.005)
        except BaseException:
            self.abort_known()
            raise
        finally:
            self.close()


def terminate_owned(process, *, process_group=False, ownership=None):
    # process_group remains a compatibility keyword, not an ownership proof.
    tree = ownership or OwnedTree(before_spawn=False)
    if tree.process is None:
        try:
            tree.attach(process)
        except BaseException:
            try:
                tree.abort_known()
            finally:
                tree.close()
            raise
    return tree.terminate()


def command(name, **kwargs):
    cmd = [sys.executable, "-m", "tools.public_calibrated_solver", name]
    for key, value in kwargs.items():
        cmd.extend(["--" + key.replace("_", "-"), str(value)])
    return cmd


def wait_owned(process, seconds, *, process_group=False, ownership=None):
    """Track exact descendants while waiting, not only at the kill deadline."""
    tree = ownership or OwnedTree(before_spawn=False)
    try:
        tree.attach(process)
        end = time.monotonic() + max(.001, seconds)
        while True:
            live = tree.refresh()
            rc = process.poll()
            if rc is not None:
                live = tree.refresh()
                if live or tree.unattributed or tree.failed:
                    tree.terminate()
                    raise CleanupFailure("leader exited before its descendants; run is partial")
                tree.proven = True
                tree.close()
                return rc, False
            if time.monotonic() >= end:
                return tree.terminate(), True
            time.sleep(min(.05, max(.001, end - time.monotonic())))
    except BaseException:
        if not tree.proven:
            try:
                if tree.pinned:
                    tree.terminate()
                else:
                    tree.abort_known()
            finally:
                tree.close()
        raise


def prepare(plan_path, plan_hash, output, kind):
    plan = frozen(plan_path, plan_hash)
    admit(plan, plan_hash, kind)
    from .common import verify_base
    verify_base()
    art = new_artifacts(output)
    schedule = core.prepare(plan)
    lock = {"schema": "public-calibrated-solver-source-lock-v1",
            "plan_path": str(Path(plan_path).resolve()), "plan_file_sha256": plan_hash,
            "plan_sha256": core.digest(plan), "execution_kind": kind,
            "source_identity": sources(), "context_admitted": schedule["context_admitted"],
            "task_count": 12, "query_count": 15, "scientific_panel_views": 120,
            "additional_base_admission_generations": 3, "additional_base_admission_scores": 3,
            "model_executed": False, "scientific_effectiveness_established": False}
    art.write("source_lock.json", lock)
    art.write("schedule.json", schedule)
    return {"source_lock_path": str(art.root / "source_lock.json"),
            "source_lock_sha256": sha(read_bytes(art.root / "source_lock.json")),
            "context_admitted": schedule["context_admitted"]}


def run(args):
    started = time.monotonic()
    require_linux()
    become_subreaper()
    lock = frozen(args.source_lock, args.source_lock_sha256)
    if lock.get("schema") != "public-calibrated-solver-source-lock-v1":
        raise ValueError("unsupported source lock")
    kind = lock["execution_kind"]
    if args.synthetic != (kind == "synthetic_cpu"):
        raise ValueError("synthetic execution requires its explicit flag and synthetic source lock")
    if not 60 <= args.budget_seconds <= 7200:
        raise ValueError("whole-run budget must be 60..7200 seconds")
    if kind != "synthetic_cpu" and (args.synthetic_age_seconds or args.synthetic_fault != "none"):
        raise ValueError("synthetic test controls are forbidden for real execution")
    if args.synthetic_age_seconds < 0 or args.synthetic_age_seconds >= args.budget_seconds:
        raise ValueError("synthetic elapsed time must be within the original clock budget")
    started -= args.synthetic_age_seconds
    deadline = inherited(args.budget_seconds, started)
    verify_sources(lock["source_identity"])
    plan = frozen(lock["plan_path"], lock["plan_file_sha256"])
    admit(plan, lock["plan_file_sha256"], kind)
    if core.digest(plan) != lock["plan_sha256"]:
        raise ValueError("source lock plan binding differs")
    if args.strategy not in STRATEGIES or args.fallback not in ("fail", "copy-input"):
        raise ValueError("strategy and no-candidate policy must be fixed initially")
    if kind == "public_model" and not args.model_dir:
        raise ValueError("verified local public model directory is required")
    if kind == "public_model" and args.gold_sha256 != PUBLIC_GOLD_FILE_SHA256:
        raise ValueError("real evaluation requires frozen public gold byte identity")
    artifacts = new_artifacts(args.output)
    intent = {"schema": "public-calibrated-solver-intent-v1", **{k: lock[k] for k in
        ("plan_path", "plan_file_sha256", "plan_sha256", "execution_kind", "source_identity")},
        "source_lock_sha256": args.source_lock_sha256,
        "session_id": f"public-paired-{time.time_ns()}", "started_monotonic": started,
        "budget_seconds": args.budget_seconds, "selected_strategy": args.strategy,
        "fallback_policy": args.fallback, "selection_fixed_before_worker": True,
        "export_adapter": "public frozen candidate serializer; not a score-selected winner",
        "model_dir": str(Path(args.model_dir).resolve()) if args.model_dir else None,
        "synthetic_fault": args.synthetic_fault, "synthetic_age_seconds": args.synthetic_age_seconds,
        "resume_supported": False, "scientific_effectiveness_established": False}
    artifacts.write("intent.json", intent)
    path = artifacts.root / "intent.json"
    digest = sha(read_bytes(path))
    started_child = time.monotonic()
    with (artifacts.root / "coordinator.log").open("xb") as log:
        ownership = OwnedTree()
        process = None
        previous = signal.getsignal(signal.SIGTERM)
        def cancel(signum, frame):
            raise KeyboardInterrupt("supervisor interrupted")
        signal.signal(signal.SIGTERM, cancel)
        try:
            process = subprocess.Popen(command("_coordinator", intent=path, intent_sha256=digest,
                gold=Path(args.gold).resolve(), gold_sha256=args.gold_sha256, output=artifacts.root / "paired"),
                cwd=ROOT, env=environment(), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            rc, timeout = wait_owned(process, deadline.remaining(), process_group=True, ownership=ownership)
        except BaseException as exc:
            cleanup_error = None
            if process is not None and not ownership.proven:
                try:
                    terminate_owned(process, ownership=ownership)
                except BaseException as failure:
                    cleanup_error = f"{type(failure).__name__}: {failure}"
            artifacts.write("watchdog.json", {"status": "interrupted" if ownership.proven else "cleanup_failed",
                "error": f"{type(exc).__name__}: {exc}", "coordinator_exited": process is None or process.poll() is not None,
                "cleanup_error": cleanup_error,
                "owned_process_group_reaped": ownership.proven,
                "owned_descendants_reaped": ownership.proven, "budget": deadline.receipt(),
                "scientific_effectiveness_established": False})
            return 2
        finally:
            signal.signal(signal.SIGTERM, previous)
    closure = load_if(artifacts.root / "paired/closure.json")
    complete = (rc == 0 and not timeout and ownership.proven and closure is not None and closure.get("status") == "complete"
                and deadline.remaining() > 0)
    artifacts.write("watchdog.json", {"status": "complete" if complete else "partial",
        "coordinator_returncode": rc, "whole_process_watchdog_fired": timeout,
        "coordinator_exited": process.poll() is not None,
        "owned_descendants_reaped": ownership.proven,
        "owned_process_group": process.pid, "child_seconds": time.monotonic() - started_child,
        "budget": deadline.receipt(), "serialization_after_deadline": deadline.remaining() == 0,
        "execution_kind": kind, "scientific_effectiveness_established": False})
    return 0 if complete else 2


def recovered_calibration(plan, intent, worker):
    """Atomic successful/failed rows survive missing or inconsistent aggregate."""
    raw = [load_if(p) for p in sorted((worker / "calibration/receipts").glob("loo-*.json"))]
    aggregate = load_if(worker / "calibration/calibration.json")
    recovered = core.calibration_bundle(plan, raw, kind=intent["execution_kind"],
        session_id=intent["session_id"], completed_event=max((r["event"] for r in raw), default=-1) + 1,
        status="partial")
    core.validate_calibration(plan, recovered)
    if aggregate is None:
        return recovered, False
    core.validate_calibration(plan, aggregate)
    if aggregate["session_id"] != intent["session_id"] or aggregate["execution_kind"] != intent["execution_kind"]:
        raise ValueError("calibration aggregate belongs to a different session")
    if core.digest(raw) != core.digest(aggregate["rows"]):
        raise ValueError("calibration aggregate differs from atomic raw receipts")
    return aggregate, True


def bind_trace_intent(intent, worker, ledger, session_complete):
    """Bind self-consistent leaf clocks/provenance to the initial outer intent."""
    original = ledger.get("original_started_monotonic")
    if original is not None and original != intent["started_monotonic"]:
        raise ValueError("operation trace reset or replaced the original outer clock")
    freeze = load_if(Path(worker) / "calibration_freeze.json")
    if freeze is not None and (freeze["session_id"] != intent["session_id"] or
            freeze["source_identity_sha256"] != core.digest(intent["source_identity"]) or
            freeze["budget"]["budget_seconds"] != intent["budget_seconds"]):
        raise ValueError("calibration freeze is not bound to initial session/source/budget")
    if session_complete:
        last = ledger.get("last_trace_elapsed_seconds")
        reserve = min(120., max(15., intent["budget_seconds"] * .02))
        if (original is None or type(last) not in (int, float) or
                not 0 <= last < intent["budget_seconds"] - reserve or freeze is None):
            raise ValueError("claimed complete trace reaches original work deadline or lacks freeze")


def select_candidates(intent, plan, base_result, ranking):
    """Pure selection shared with independent pre-gold provenance checking."""
    strategy = intent["selected_strategy"]
    base_rows = {r["query_id"]: r for r in base_result["queries"]}
    calibrated = {r["query_id"]: r for r in ranking["queries"]}
    selected, eligibility = {}, []
    for p in plan["parents"]:
        selected[p["task_id"]] = {}
        for q in p["test"]:
            row = calibrated[q["query_id"]]
            if strategy == "demo_weighted":
                ready = row["adaptation_applied"]
                candidates = row["weighted_top2"] if ready else []
            else:
                b = base_rows[q["query_id"]]
                ready = row["pool_complete"] and (b["vote_complete"] if strategy == "vote" else b["rescoring_complete"])
                candidates = b[strategy] if ready else []
            selected[p["task_id"]][str(q["test_index"])] = candidates
            eligibility.append({"query_id": q["query_id"], "strategy_eligible": ready,
                                "selected_candidates": len(candidates)})
    return selected, eligibility


def selection_values(intent, plan, base_result, ranking, challenge_hash):
    selected, eligibility = select_candidates(intent, plan, base_result, ranking)
    candidates = {"schema": export_contract.FROZEN_SCHEMA, "challenge_sha256": challenge_hash,
        "strategy": "frozen", "strategy_chosen_before_gold": True, "queries": selected}
    selection = {"selected_strategy": intent["selected_strategy"],
        "intent_sha256": core.digest(intent), "candidate_sha256": core.digest(candidates),
        "pool_sha256": ranking["pool_sha256"], "calibration_sha256": ranking["calibration_sha256"],
        "queries": eligibility, "evaluation_started": False, "score_based_selection": False}
    return candidates, selection


def exporter_args(intent, root):
    root = Path(root)
    return ["--challenge", str(root / "challenge.json"),
              "--candidates", str(root / "selected_candidates.json"),
              "--source-format", "frozen", "--strategy", "frozen", "--strategy-chosen-before-gold",
              "--fallback", intent["fallback_policy"], "--output-dir", str(root / "export")]


def export_selected(intent, plan, base_result, ranking, artifacts):
    """Select before evaluator starts, using the strategy already in intent."""
    from tools.public_sft141_submission.__main__ import main as export_main
    challenge = challenge_from_plan(plan)
    artifacts.write("challenge.json", challenge)
    candidates, selection = selection_values(intent, plan, base_result, ranking,
                                             sha(read_bytes(artifacts.root / "challenge.json")))
    artifacts.write("selected_candidates.json", candidates)
    artifacts.write("selection.json", selection)
    common = exporter_args(intent, artifacts.root)
    exported = export_main(["export", *common]) == 0
    verified = exported and export_main(["verify", *common]) == 0
    return {"exported": exported, "verified": verified, "strategy": intent["selected_strategy"],
            "no_candidate_policy": intent["fallback_policy"],
            "format_success_is_not_model_success": True}


def coordinate(args):
    require_linux()
    intent = frozen(args.intent, args.intent_sha256)
    deadline = inherited(intent["budget_seconds"], intent["started_monotonic"])
    artifacts = new_artifacts(args.output)
    worker = artifacts.root / "model"
    process = evaluator = None
    model_ownership = evaluator_ownership = None
    try:
        verify_sources(intent["source_identity"])
        plan = frozen(intent["plan_path"], intent["plan_file_sha256"])
        deadline.check()
        with (artifacts.root / "model.log").open("xb") as log:
            model_ownership = OwnedTree()
            process = subprocess.Popen(command("_model", intent=args.intent,
                intent_sha256=args.intent_sha256, output=worker), cwd=ROOT, env=environment(),
                stdout=log, stderr=subprocess.STDOUT)
            rc, timeout = wait_owned(process, deadline.work_remaining(), ownership=model_ownership)
        # The owned model PID has exited. Only now collect/seal/evaluate evidence.
        seal = {"schema": "public-paired-worker-seal-v1", "worker_exited": process.poll() is not None,
            "returncode": rc, "timed_out": timeout, "worker_pid": process.pid,
            "owned_descendants_reaped": model_ownership.proven,
            "intent_sha256": args.intent_sha256, "files": evidence_manifest(worker),
            "source_identity_sha256": core.digest(intent["source_identity"]),
            "integrity_only_not_execution_attestation": True, "budget": deadline.receipt()}
        artifacts.write("worker_seal.json", seal)
        calibration, consistent = recovered_calibration(plan, intent, worker)
        base_result, aggregate_exists = reconcile_base(plan, worker)
        pool = assemble_pool(plan, calibration, worker)
        ranking = core.rank(plan, calibration, pool)
        for filename, value in (("calibration.json", calibration), ("base_result.json", base_result),
                                ("pool.json", pool), ("ranking.json", ranking)):
            artifacts.write(filename, value)
        for filename, value in (("pool.json", pool), ("ranking.json", ranking)):
            declared = load_if(worker / filename)
            if declared is not None and declared != value:
                raise ValueError("worker declared " + filename + " differs from atomic reconstruction")
        closure = load_if(worker / "closure.json") or {}
        complete = (rc == 0 and not timeout and consistent and aggregate_exists and
            closure.get("status") == "complete" and closure.get("evaluator_imported") is False and
            closure.get("completed_within_work_deadline") is True and deadline.remaining() > 0)
        from .trace_audit import audit
        protocol_audit = audit(plan, calibration, base_result, worker, complete)
        artifacts.write("trace_audit.json", protocol_audit)
        bind_trace_intent(intent, worker, protocol_audit, complete)
        if not protocol_audit["audit_passed"]:
            raise ValueError("operation trace/cost audit failed; corrupt evidence cannot reach gold")
        complete = complete and protocol_audit["strict_complete"]
        export = export_selected(intent, plan, base_result, ranking, artifacts)
        artifacts.write("export_status.json", export)
        verify_sources(intent["source_identity"])
        verify_evidence(worker, seal["files"])
        analysis_inputs = {name: sha(read_bytes(artifacts.root / name)) for name in
            ("calibration.json", "base_result.json", "pool.json", "ranking.json", "selection.json",
             "selected_candidates.json", "worker_seal.json", "trace_audit.json", "challenge.json", "export_status.json")}
        artifacts.write("evaluation_intent.json", {"session_complete": complete,
            "input_files": analysis_inputs, "intent_sha256": args.intent_sha256,
            "model_worker_exited": True, "original_started_monotonic": deadline.start,
            "selected_strategy": intent["selected_strategy"]})
        if deadline.remaining() <= 1:
            raise TimeoutError("no original closure budget remains for independent evaluator")
        eval_intent = artifacts.root / "evaluation_intent.json"
        with (artifacts.root / "evaluator.log").open("xb") as log:
            evaluator_ownership = OwnedTree()
            evaluator = subprocess.Popen(command("_evaluate", intent=args.intent,
                intent_sha256=args.intent_sha256, evaluation_intent=eval_intent,
                evaluation_intent_sha256=sha(read_bytes(eval_intent)), gold=args.gold,
                gold_sha256=args.gold_sha256, output=artifacts.root / "evaluation"),
                cwd=ROOT, env=environment(), stdout=log, stderr=subprocess.STDOUT)
            erc, etimeout = wait_owned(evaluator, max(.001, deadline.remaining() - 1), ownership=evaluator_ownership)
        evaluation = load_if(artifacts.root / "evaluation/result.json")
        verify_sources(intent["source_identity"])
        verify_evidence(worker, seal["files"])
        if export["verified"]:
            from tools.public_sft141_submission.__main__ import main as export_main
            if export_main(["verify", *exporter_args(intent, artifacts.root)]) != 0:
                raise ValueError("pre-gold selected export changed during evaluation")
        successful = (complete and erc == 0 and not etimeout and evaluation is not None and
                      evaluation.get("scientific_audit_complete") is True and export["verified"] and deadline.remaining() > 0)
        artifacts.write("closure.json", {"status": "complete" if successful else "partial",
            "session_complete": complete, "worker_exited_before_evaluation": True,
            "evaluator_returncode": erc, "evaluator_timed_out": etimeout,
            "evaluator_exited": evaluator.poll() is not None, "export": export,
            "owned_descendants_reaped": model_ownership.proven and evaluator_ownership.proven,
            "budget": deadline.receipt(), "execution_kind": intent["execution_kind"],
            "scientific_audit_complete": bool(evaluation and evaluation.get("scientific_audit_complete")),
            "scientific_effectiveness_established": False,
            "qualification": "Fixed public 12-parent/15-query mechanics experiment, not arbitrary hidden-task coverage or a proven model improvement."})
        return 0 if successful else 2
    except BaseException as exc:
        cleanup_errors = []
        for child, ownership in ((process, model_ownership), (evaluator, evaluator_ownership)):
            if child is not None and child.poll() is None:
                try:
                    terminate_owned(child, ownership=ownership if ownership and ownership.pinned else None)
                except BaseException as failure:
                    cleanup_errors.append(f"{type(failure).__name__}: {failure}")
        artifacts.write("failure.json", {"type": type(exc).__name__, "message": str(exc),
            "budget": deadline.receipt(), "worker_exited": process is None or process.poll() is not None,
            "owned_descendants_reaped": all(o is None or o.proven for o in (model_ownership, evaluator_ownership)),
            "cleanup_errors": cleanup_errors,
            "scientific_effectiveness_established": False})
        return 2


def evaluate_leaf(args):
    """Only this process reads gold, after checking worker exit and pre-gold seal."""
    intent = frozen(args.intent, args.intent_sha256)
    deadline = inherited(intent["budget_seconds"], intent["started_monotonic"])
    art = new_artifacts(args.output)
    try:
        evaluation_intent = frozen(args.evaluation_intent, args.evaluation_intent_sha256)
        root = Path(args.evaluation_intent).parent
        if (evaluation_intent["intent_sha256"] != args.intent_sha256 or
                evaluation_intent["model_worker_exited"] is not True or
                evaluation_intent["selected_strategy"] != intent["selected_strategy"] or
                evaluation_intent["original_started_monotonic"] != deadline.start):
            raise ValueError("post-exit evaluation intent mismatch")
        verify_sources(intent["source_identity"])
        values = {name: frozen(root / name, digest) for name, digest in evaluation_intent["input_files"].items()}
        seal = values["worker_seal.json"]
        if (seal["worker_exited"] is not True or seal.get("owned_descendants_reaped") is not True
                or seal["intent_sha256"] != args.intent_sha256):
            raise ValueError("model worker not sealed as exited")
        verify_evidence(root / "model", seal["files"])
        plan = frozen(intent["plan_path"], intent["plan_file_sha256"])
        if values["challenge.json"] != challenge_from_plan(plan):
            raise ValueError("export challenge differs from exact admitted plan")
        from .trace_audit import audit
        protocol_audit = audit(plan, values["calibration.json"], values["base_result.json"],
            root / "model", evaluation_intent["session_complete"])
        bind_trace_intent(intent, root / "model", protocol_audit, evaluation_intent["session_complete"])
        if protocol_audit != values["trace_audit.json"] or not protocol_audit["audit_passed"]:
            raise ValueError("independent operation trace/cost reconstruction differs")
        from .evaluation import audit_predictions
        audit_predictions(plan, values["base_result.json"], values["calibration.json"],
            values["pool.json"], values["ranking.json"], evaluation_intent["session_complete"])
        selection = values["selection.json"]
        if selection["selected_strategy"] != intent["selected_strategy"] or selection["score_based_selection"] is not False:
            raise ValueError("selected strategy changed before evaluation")
        expected_candidates, expected_selection = selection_values(intent, plan,
            values["base_result.json"], values["ranking.json"], sha(read_bytes(root / "challenge.json")))
        if values["selected_candidates.json"] != expected_candidates or selection != expected_selection:
            raise ValueError("selected candidates or full pre-gold strategy lineage differ")
        if get_export := values["export_status.json"]:
            if get_export["verified"]:
                from tools.public_sft141_submission.__main__ import main as export_main
                if export_main(["verify", *exporter_args(intent, root)]) != 0:
                    raise ValueError("selected export no longer verifies")
        if intent.get("synthetic_fault") == "evaluator-hang":
            time.sleep(120)
        if deadline.remaining() <= 0:
            raise TimeoutError("original whole-run deadline reached before gold read")
        # This is the first access to evaluator labels in the entire pipeline.
        gold = frozen(args.gold, args.gold_sha256)
        art.write("boundary.json", {"gold_file_sha256": args.gold_sha256,
            "model_worker_exited": True, "selected_candidates_sha256": evaluation_intent["input_files"]["selected_candidates.json"],
            "budget": deadline.receipt(), "selection_precedes_gold_read": True})
        from .evaluation import evaluate
        result = evaluate(plan, gold, values["base_result.json"], values["calibration.json"],
            values["pool.json"], values["ranking.json"], intent["execution_kind"], evaluation_intent["session_complete"],
            protocol_audit=protocol_audit)
        if deadline.remaining() <= 0:
            raise TimeoutError("post-exit evaluator exceeded original whole-run deadline")
        art.write("result.json", result)
        return 0
    except Exception as exc:
        art.write("failure.json", {"type": type(exc).__name__, "message": str(exc),
                                  "budget": deadline.receipt(), "scientific_effectiveness_established": False})
        return 2
