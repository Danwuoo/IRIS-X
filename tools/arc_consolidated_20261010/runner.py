"""One inert-by-default demos-only workflow, with durable physical accounting."""
from __future__ import annotations

from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import time
import threading
import uuid

from . import SUITE_ID
from . import arc_object_ir as ir
from . import assets, evidence, stages, verifier, offline_bootstrap
from .controls import synthetic_controls
from .path_guard import environment_path, guard_paths, normalized_path
from .ledger import Ledger, BudgetExceeded, digest as ledger_digest
from .model_provider import MODEL_MANIFEST_SHA256, Sampling, build_study_plan

PROFILES = {
    "SMOKE": {"candidates": 128, "coverage_checks": 1152, "coverage_wall_seconds": 300,
              "verifier_checks": 1152, "model_calls": 0, "session_seconds": 600},
    "FULL": {"candidates": 5965, "coverage_checks": 47848, "coverage_wall_seconds": 1800,
             "verifier_checks": 52536, "model_calls": 80, "session_seconds": 7200},
}
BASE_SHA256 = "f205b801bbb177cacd560582ddf994ad27c0f934cacd999b7983709d1c0a071e"
SMOKE_SHA256 = "1a697fb773219f4f091545528449fb43d53e517c634d59a2835ff2db006acf21"
CONTROLS_SHA256 = "4c1b631ee7090d24caf7b4da976cd6f81c4c273e8b59070802a8cbbacb479608"


def limits_for(profile):
    if profile not in PROFILES:
        raise ValueError("profile must be SMOKE or FULL")
    p = PROFILES[profile]
    return {"physical_calls": p["model_calls"], "cpu_checks": p["verifier_checks"],
            "unknown_verifications": p["verifier_checks"], "unknown_model_calls": p["model_calls"],
            "coverage_checks": p["coverage_checks"], "model_checks": p["model_calls"],
            "search_checks": 4608 if profile == "FULL" else 0,
            "gas": p["verifier_checks"] * 200000,
            "prompt_tokens": p["model_calls"] * 6144,
            "output_tokens": p["model_calls"] * 2048,
            "model_seconds": p["model_calls"] * 120,
            "verifier_seconds": p["verifier_checks"] * 3,
            "coverage_wall_seconds": p["coverage_wall_seconds"],
            "load_seconds": 14400, "archive_seconds": 600,
            "wall_seconds": 14400, "unknown_calls": p["verifier_checks"] + p["model_calls"] + 32}


def _compact_ledger(ledger):
    report = ledger.summary()
    report.pop("operations", None)
    report["directory_fsync_supported"] = __import__("os").name == "posix"
    return report


def _physical_complete(ledger):
    return all(op["status"] in {"complete", "fail"}
               for op in ledger.summary()["operations"].values()
               if op["kind"] in {"cpu", "model"})


def _prior_model_stopped(ledger):
    """CPU no-go paths still require retained model resource stop evidence.

    Current study provenance reserves owner/<session> before load/<session> or
    model dispatch. An unrelated old owner's stop cannot cover a later load.
    """
    operations = ledger.summary()["operations"]
    bootstraps = {op_id: op for op_id, op in operations.items() if op_id.startswith("bootstrap/")}
    if any(op["status"] not in {"complete", "fail"} or "response" not in op
           or ledger.get_response(op_id).get("bootstrap_stopped") is not True
           for op_id, op in bootstraps.items()):
        return False
    activities = {op_id: op for op_id, op in operations.items()
                  if op["kind"] == "model" or op_id.startswith(("load/", "owner/"))}
    if not activities:
        return True
    if any(op["status"] in {"reserved", "unknown"} for op in activities.values()):
        return False
    owners = {op_id: op for op_id, op in activities.items() if op_id.startswith("owner/")}
    if not owners:
        return False
    if any("owner/" + op_id[len("load/"):] not in owners
           for op_id in activities if op_id.startswith("load/")):
        return False
    return all("response" in op and ledger.get_response(op_id).get("model_owner_stopped") is True
               for op_id, op in owners.items())


def _bootstrap_environment(plan, gate, ledger, root, session_id):
    """Parent-owned durable accounting around the post-gate installer children."""
    available = ledger.limits["load_seconds"] - ledger.summary()["charged"]["load_seconds"]
    allowance = min(available, ledger.remaining_wall_seconds - 65)
    if allowance <= 0:
        raise BudgetExceeded("no offline environment preparation allowance")
    operation_id = "bootstrap/" + session_id
    ledger.reserve("overhead", operation_id, {"load_seconds": allowance}, metadata={
        "phase": "post_gate_offline_environment", "environment_plan_sha256": plan["plan_sha256"]})
    started = time.monotonic()
    proof, stopped = {}, False
    try:
        prepared = offline_bootstrap.prepare_model_environment(plan, enable_model=True,
            gate_receipt=gate, deadline_seconds=allowance)
        proof = prepared.get("child_stop_proof", {})
        stopped = (set(proof) == {"material", "install"} and
                   all(row.get("owned_group_stopped") is True and
                       row.get("leader_reaped") is True and row.get("live_group_members") == 0
                       for row in proof.values()))
        if prepared.get("status") != "prepared" or not stopped:
            raise ValueError("offline environment preparation lacks complete child stop evidence")
        source_identity = assets.executable_identity()
        package_prefix = "tools/arc_consolidated_20261010/"
        package_identity = {key[len(package_prefix):]: value for key, value in source_identity.items()
                            if key.startswith(package_prefix)}
        if assets.digest(package_identity) != ledger.bindings["source"]:
            raise ValueError("prepared executable source differs from the frozen CPU-gate source")
        fields = ("python_command", "source_root", "model_path", "manifest_path",
                  "environment_lock_path", "actual_environment_lock_sha256")
        ready = {key: prepared[key] for key in fields}
        if prepared["environment_plan_sha256"] != plan["plan_sha256"]:
            raise ValueError("prepared environment plan changed")
        admission = {"format": "irisx/consolidated-runtime-admission-v2",
            "environment_plan_sha256": plan["plan_sha256"],
            "source_identity_sha256": assets.digest(source_identity),
            "prepared": ready, "asset_receipts_sha256": assets.digest(prepared["asset_receipts"])}
        # Model caches must never cross actual installed environment bytes on
        # resume, even though the original ledger binds the pre-install plan.
        evidence.write_new(Path(root) / "runtime" / "environment-binding.json", admission)
        path = evidence.write_new(Path(root) / "runtime" / ("admission-" + session_id + ".json"), admission)
        ready.update(admission_path=str(path.absolute()),
                     admission_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        receipt = {"bootstrap_stopped": True, "child_stop_proof": proof,
                   "environment_plan_sha256": plan["plan_sha256"],
                   "actual_environment_lock_sha256": prepared["actual_environment_lock_sha256"],
                   "asset_receipts": prepared["asset_receipts"],
                   "admission_sha256": ready["admission_sha256"],
                   "elapsed_seconds": time.monotonic() - started}
    except Exception as exc:
        # An absent structured stop receipt is deliberately not inferred from
        # an exception or a child's exit code. Resume must retain that unknown.
        proof = getattr(exc, "child_stop_proof", proof)
        stopped = getattr(exc, "owned_descendants_stopped", stopped) is True
        receipt = {"bootstrap_stopped": stopped, "child_stop_proof": proof,
                   "environment_plan_sha256": plan["plan_sha256"],
                   "elapsed_seconds": time.monotonic() - started,
                   "error": {"type": type(exc).__name__, "message": str(exc)[:1000]}}
        ledger.record_response(operation_id, receipt)
        ledger.finish(operation_id, {"load_seconds": max(allowance, receipt["elapsed_seconds"])}, outcome="fail")
        raise
    ledger.record_response(operation_id, receipt)
    ledger.finish(operation_id, {"load_seconds": receipt["elapsed_seconds"]})
    return {"environment_sha256": plan["plan_sha256"], "prepared_bootstrap": ready,
            "source_identity": source_identity}, receipt


def _unknown(reason):
    return {"status": "unknown", "known": False, "all_demos_fit": False,
            "gas": None, "wall_seconds": 0.0, "reason": reason}


class AccountedVerifier:
    """Controller-owned accounting with at most four isolated CPU verifiers.

    A completed CPU receipt is reusable. An uncertain physical check is never
    retried under its old ID. A model response may get a new, counted CPU check
    on an explicitly resumed session while the fixed stage cap still permits it.
    Only ``verify_fn`` runs in worker threads. The controller alone compiles,
    reserves, reads caches and persists receipts, in fixed input order.
    """
    workers_cap = 4

    def __init__(self, ledger, *, cpu_deadline, capability, resume, verify_fn=verifier.verify):
        self.ledger, self.cpu_deadline = ledger, cpu_deadline
        self.capability, self.resume, self.verify_fn = capability, resume, verify_fn
        self.sources = {}
        self._controller = threading.get_ident()
        self._stop_confirmed, self._pending = True, set()
        self.workers_used = 0
        self._coverage_stop = None
        initial_operations = ledger.summary()["operations"]
        self.initial_cpu_ids = {op_id for op_id, op in initial_operations.items() if op["kind"] == "cpu"}
        for op_id, op in initial_operations.items():
            if op["kind"] != "cpu":
                continue
            if "response" not in op:
                self._stop_confirmed = False
            else:
                self._stop_confirmed &= ledger.get_response(op_id).get("owned_descendants_stopped") is True
        self.physical_this_session = 0

    @property
    def all_stopped(self):
        return self._stop_confirmed and not self._pending

    def _assert_controller(self):
        if threading.get_ident() != self._controller:
            raise RuntimeError("CPU accounting must remain on the owning controller thread")

    def _finish_receipt(self, ident, value):
        usage = {"verifier_seconds": value["wall_seconds"]}
        if value["known"]:
            usage.update(gas=value["gas"], unknown_verifications=0)
        self.ledger.finish(ident, usage, outcome="complete" if value["known"] else "fail")

    def _model_response_binding(self, call_id, plan):
        if not call_id:
            return None
        operation_id = "model/" + call_id
        operation = self.ledger.operation(operation_id)
        if operation is None or operation["kind"] != "model" or "response" not in operation:
            return None
        response = self.ledger.get_response(operation_id)
        if response.get("unknown_physical_call") or response.get("truncated") or response.get("late"):
            return None
        if ir.parse_plan(response.get("text")) != ir.validate_plan(plan):
            raise ValueError("CPU plan differs from its durable model response")
        return {"model_operation_id": operation_id,
                "model_response_sha256": operation["response"]["sha256"]}

    def _prepare(self, task, plan, scope="coverage", call_id=None):
        """Return (cached receipt, None) or (None, durably reserved work)."""
        self._assert_controller()
        if scope not in {"coverage", "model", "search"}:
            raise ValueError("unknown verification scope")
        ident = "cpu/" + scope + "/" + (call_id or assets.digest({"task": task, "plan": plan}))
        # User call IDs cannot smuggle different work into an existing cache.
        binding = assets.digest({"task": task, "plan": plan, "scope": scope})
        base_ident, attempt = ident, 1
        model_binding = None
        while (old := self.ledger.operation(ident)) is not None:
            if old["metadata"]["work_sha256"] != binding:
                raise ValueError("CPU request identity changed")
            if old["status"] in {"complete", "fail", "responded"} and "response" in old:
                value = self.ledger.get_response(ident)
                self._stop_confirmed &= value.get("owned_descendants_stopped") is True
                if old["status"] == "responded":
                    self._finish_receipt(ident, value)
                # A fresh verification is a separate physical operation, only
                # after explicit resume of a stopped-but-unknown old check.
                # A new unknown receipt is cached for this whole session.
                if (scope != "model" or not self.resume or ident not in self.initial_cpu_ids
                        or value["known"] or value.get("owned_descendants_stopped") is not True):
                    return value, None
                model_binding = self._model_response_binding(call_id, plan)
                if model_binding is None:
                    return value, None
                for key, expected in model_binding.items():
                    if key in old["metadata"] and old["metadata"][key] != expected:
                        raise ValueError("CPU verification durable model binding changed")
                attempt += 1
                ident = base_ident + "/verification-" + str(attempt)
            else:
                self._stop_confirmed = False
                return _unknown("reserved physical CPU work is uncertain; no redispatch"), None
        if scope == "model":
            model_binding = model_binding or self._model_response_binding(call_id, plan)
            if model_binding is None:
                return _unknown("model CPU verification requires a durable model response"), None
        if not self.capability["available"]:
            raise stages.StopCoverage(self.capability["reason"])
        if not self._stop_confirmed:
            raise stages.StopCoverage("an earlier owned CPU worker has no verified stop acknowledgement")
        if scope == "coverage" and self._coverage_stop is not None:
            raise stages.StopCoverage(self._coverage_stop)
        if scope == "coverage" and time.monotonic() >= self.cpu_deadline:
            raise stages.StopCoverage("cumulative CPU coverage wall cap exhausted")
        if self.ledger.remaining_wall_seconds <= 65:
            raise stages.StopCoverage("session admission stopped to retain cleanup/archive time")
        key = assets.digest(plan)
        if key not in self.sources:
            self.sources[key] = ir.compile_plan(plan)
        timeout = min(3.0, self.ledger.remaining_wall_seconds - 60)
        if scope == "coverage":
            timeout = min(timeout, self.cpu_deadline - time.monotonic())
        if timeout <= 0:
            raise stages.StopCoverage("CPU admission deadline reached")
        budget = {"cpu_checks": 1, scope + "_checks": 1, "gas": 200000, "unknown_verifications": 1,
                  "verifier_seconds": timeout}
        self.ledger.reserve("cpu", ident, budget,
                            metadata={"work_sha256": binding, "scope": scope, **(model_binding or {})})
        self._pending.add(ident)
        return None, {"ident": ident, "source": self.sources[key], "task": task, "timeout": timeout,
                      "deadline": time.monotonic() + timeout if scope != "coverage" else
                      min(time.monotonic() + timeout, self.cpu_deadline)}

    def _dispatch(self, work):
        # This is the sole worker-thread operation: no ledger/cache mutation.
        remaining = min(work["timeout"], work["deadline"] - time.monotonic())
        if remaining <= 0:
            return {**_unknown("reserved CPU dispatch deadline elapsed"),
                    "dispatched": False, "owned_descendants_stopped": True}
        return self.verify_fn(work["source"], work["task"], timeout=remaining, max_steps=200000)

    def _finalize(self, work, result):
        self._assert_controller()
        ident = work["ident"]
        result = stages._receipt(result)
        self.physical_this_session += int(result.get("dispatched") is True)
        self._stop_confirmed &= result.get("owned_descendants_stopped") is True
        self._pending.discard(ident)
        self.ledger.record_response(ident, result)
        # Unknown execution keeps full gas and unknown reservations charged.
        self._finish_receipt(ident, result)
        return result

    def _unconfirmed(self, work):
        self._stop_confirmed = False
        self._pending.discard(work["ident"])

    def __call__(self, task, plan, scope="coverage", call_id=None):
        cached, work = self._prepare(task, plan, scope, call_id)
        if work is None:
            return cached
        self.workers_used = max(self.workers_used, 1)
        try:
            result = self._dispatch(work)
        except BaseException:
            self._unconfirmed(work)
            raise
        return self._finalize(work, result)

    def batch(self, jobs):
        """Run ordered ``(task, plan)`` coverage jobs, with complete denominator.

        Each four-item window is reserved and dispatched by the controller.
        A stop drains the already submitted bounded verifiers before returning;
        no later jobs are reserved. Completed receipts retain input order even
        when subprocesses finish in a different order. An interrupt is retained
        as a stage stop, allowing the caller to export a partial diagnostic.
        """
        self._assert_controller()
        rows, stopped, invocations = [], self._coverage_stop, 0
        iterator = iter(jobs)
        exhausted = False
        with ThreadPoolExecutor(max_workers=self.workers_cap, thread_name_prefix="irisx-cpu") as executor:
            while not exhausted:
                window = []
                for _ in range(self.workers_cap):
                    try:
                        task, plan = next(iterator)
                    except StopIteration:
                        exhausted = True
                        break
                    if stopped is not None:
                        window.append((stages._unvisited(stopped), None, None))
                        continue
                    invocations += 1
                    work = None
                    try:
                        cached, work = self._prepare(task, plan)
                        future = executor.submit(self._dispatch, work) if work is not None else None
                        window.append((cached, work, future))
                    except BaseException as exc:
                        stopped = type(exc).__name__ + ": " + str(exc)[:400]
                        status = exc.current_status if isinstance(exc, stages.StopCoverage) else "missing"
                        if work is not None:
                            # Submit failure is conservatively unresolved.
                            self._unconfirmed(work)
                            status = "unknown"
                        window.append((stages._unvisited(stopped, status), None, None))
                self.workers_used = max(self.workers_used, sum(item[2] is not None for item in window))
                for cached, work, future in window:
                    if future is None:
                        rows.append(cached)
                        continue
                    result, failed = None, False
                    while True:
                        try:
                            result = future.result()
                            break
                        except (KeyboardInterrupt, SystemExit) as exc:
                            stopped = "controller interrupted; draining bounded CPU workers"
                            # A worker can also raise BaseException. It supplied
                            # no stop receipt, so retain its full reservation.
                            if future.done() and future.exception() is not None:
                                self._unconfirmed(work)
                                failed = True
                                break
                            continue
                        except Exception as exc:
                            stopped = "CPU verifier failed without stop acknowledgement: " + type(exc).__name__
                            self._unconfirmed(work)
                            failed = True
                            break
                    if failed:
                        rows.append(_unknown(stopped))
                        continue
                    try:
                        rows.append(self._finalize(work, result))
                    except BaseException as exc:
                        stopped = "CPU receipt accounting stopped: " + type(exc).__name__
                        # Preserve the validated observed result, including stop
                        # evidence, even when charging an overrun blocks dispatch.
                        if work["ident"] in self._pending:
                            self._unconfirmed(work)
                        try:
                            rows.append(stages._receipt(result))
                        except Exception:
                            rows.append(_unknown(stopped))
                if not self._stop_confirmed and stopped is None:
                    stopped = "owned CPU worker stop is unconfirmed"
        self._coverage_stop = stopped
        return {"results": rows, "stop_reason": stopped, "callback_invocations": invocations,
                "workers_used": self.workers_used, "workers_cap": self.workers_cap}


def run(output_root, *, manual_start=False, enable_model=False, profile="SMOKE",
        model_config=None, resume=False, session_seconds=None, bootstrap_seconds=0):
    """Production entry point. No test provider or fixture gate is exposed."""
    if type(manual_start) is not bool or type(enable_model) is not bool or type(resume) is not bool:
        raise ValueError("manual flags must be exact booleans")
    if not manual_start:
        return {"status": "INACTIVE", "suite_id": SUITE_ID,
                "model_calls": 0, "training_performed": False}
    return _run(output_root, enable_model=enable_model, profile=profile,
                model_config=model_config, resume=resume, session_seconds=session_seconds,
                bootstrap_seconds=bootstrap_seconds)


def _run(output_root, *, enable_model=False, profile="SMOKE", model_config=None,
         resume=False, session_seconds=None, bootstrap_seconds=0,
         evidence_mode="production", _test_verify=None, _test_backend=None):
    """Internal test hooks are always separately bound synthetic-only evidence."""
    started = time.monotonic()
    if type(bootstrap_seconds) not in (int, float) or not math.isfinite(bootstrap_seconds) or bootstrap_seconds < 0:
        raise ValueError("invalid bootstrap timing")
    if evidence_mode not in {"production", "synthetic-test-only"}:
        raise ValueError("unknown evidence mode")
    if evidence_mode == "production" and (_test_verify is not None or _test_backend is not None):
        raise ValueError("test providers cannot enter a production ledger")
    limits = limits_for(profile)
    if enable_model and profile != "FULL":
        raise ValueError("SMOKE is CPU-only and never enables model work")
    root = normalized_path(output_root)
    config = dict(model_config or {})
    guard_paths(config, {"source": Path(__file__).absolute().parents[2],
                         "output": root, "environment": environment_path(root)})
    tasks = assets.load_demos()
    bootstrap_plan = None
    if enable_model and evidence_mode == "production":
        # Pure path/pin planning is permitted here. All mount access, integrity
        # scans and installation occur after the FULL gate below. Environment
        # bytes live outside the recursive evidence archive.
        bootstrap_plan = offline_bootstrap.plan_config(config,
            work_root=str(environment_path(root)))
        environment_sha = bootstrap_plan["plan_sha256"]
    else:
        environment_sha = config.get("environment_sha256") or assets.digest("CPU-only: environment not scanned")
    grammar = {"version": ir.IR_VERSION, "contract": ir.plan_contract()}
    study = build_study_plan(tasks, grammar=grammar, environment_sha256=environment_sha)
    bindings = {"source": assets.digest(assets.source_identity()), "task": assets.digest(tasks),
                "model": MODEL_MANIFEST_SHA256, "prompt": study.prompt_template_sha256,
                "sampling": assets.digest(asdict(Sampling())), "budget": ledger_digest(limits),
                "mode": ledger_digest(evidence_mode), "environment": environment_sha,
                "configuration": assets.digest({"suite": SUITE_ID, "profile": profile,
                                                  "enable_model": enable_model, "model_config": config})}
    if root.exists() and not resume:
        raise ValueError("output identity exists; use explicit RESUME with unchanged bindings")
    if resume and not (root / "ledger" / "journal.jsonl").is_file():
        raise ValueError("resume requires an existing bound ledger")
    evidence.safe_root(root)
    ledger = Ledger(root / "ledger", bindings, limits)
    session_id = uuid.uuid4().hex
    allowance = PROFILES[profile]["session_seconds"] if session_seconds is None else session_seconds
    if type(allowance) not in (int, float) or not math.isfinite(allowance) or allowance <= 65:
        raise ValueError("session allowance must exceed 65 seconds for cleanup and export")
    report = {"suite_id": SUITE_ID, "profile": profile, "evidence_mode": evidence_mode,
              "source_sha256": bindings["source"], "task_denominator": 8,
              "training_performed": False, "query_scoring_implemented": False,
              "gpu_execution_validated": False, "four_l4_validated": False,
              "workers_used": 0, "workers_cap": 4, "vm_billing_stopped": False}
    cap = verifier.capability() if _test_verify is None else {
        "available": True, "reason": "explicit synthetic-test-only callback; no real verifier acceptance"}
    archive = None
    with ledger.session(session_seconds=allowance,
                        prior_elapsed_seconds=bootstrap_seconds + time.monotonic() - started):
        if ledger.summary()["state"] == "complete":
            return {"status": "complete", "output_root": str(root), "resumed_noop": True,
                    "archive": None, "report": _compact_ledger(ledger)}
        evidence.write_new(root / "run-binding.json", {"suite_id": SUITE_ID, "bindings": bindings,
                                                       "limits": limits, "evidence_mode": evidence_mode})
        report["verifier_capability"] = cap
        archive_id = "archive/" + session_id
        ledger.reserve("overhead", archive_id, {"archive_seconds": 60}, metadata={"phase": "export"})
        charged = ledger.summary()["charged"]
        remaining_cpu = max(0.0, limits["coverage_wall_seconds"] - charged["coverage_wall_seconds"])
        cpu_started = time.monotonic()
        cpu_id = "cpu-phase/" + session_id
        ledger.reserve("overhead", cpu_id, {"coverage_wall_seconds": remaining_cpu}, metadata={"phase": "CPU"})
        checked = AccountedVerifier(ledger, cpu_deadline=cpu_started + remaining_cpu,
                                    capability=cap, resume=resume,
                                    verify_fn=_test_verify or verifier.verify)
        prior_model_stopped = _prior_model_stopped(ledger)
        model_stopped = prior_model_stopped
        report["prior_model_owner_stopped"] = prior_model_stopped
        try:
            plans = ir.smoke_inventory() if profile == "SMOKE" else ir.base_inventory()
            expected = SMOKE_SHA256 if profile == "SMOKE" else BASE_SHA256
            if len(plans) != PROFILES[profile]["candidates"] or ir.digest(plans) != expected:
                raise ValueError("frozen inventory changed")
            pool = stages.freeze_base_inventory(plans, ir.compile_plan)
            controls = synthetic_controls()
            if assets.digest(controls) != CONTROLS_SHA256:
                raise ValueError("independent control definitions changed")
            report["inventory"] = {"candidate_count": len(plans), "sha256": expected,
                                   "manifest": ir.inventory_manifest()}
            report["controls"] = stages.run_controls(controls, checked)
            evidence.stage_snapshot(root, "controls", report["controls"], session_id=session_id)
            report["coverage"] = stages.run_coverage(tasks, pool, checked, profile=profile)
            evidence.stage_snapshot(root, "coverage", report["coverage"], session_id=session_id)
            elapsed = time.monotonic() - cpu_started
            ledger.finish(cpu_id, {"coverage_wall_seconds": elapsed})
            report["cpu_phase_seconds"] = elapsed
            report["checks_per_second"] = checked.physical_this_session / elapsed if elapsed else 0
            gate = stages.testability_gate(report["controls"], report["coverage"],
                                           _physical_complete(ledger), profile=profile,
                                           expected_base_inventory_sha256=BASE_SHA256,
                                           expected_candidate_count=5965)
            report["gate"] = gate
            # Pure ordering diagnostics always accompany coverage, even a no-go.
            diagnostics = {}
            for task_result in report["coverage"]["tasks"]:
                diagnostics[task_result["task_id"]] = stages.order_diagnostics(
                    pool, task_result["results"], {}, seed=0, budget=64,
                    production_ids_callback=ir.production_ids, task_id=task_result["task_id"])
            evidence.stage_snapshot(root, "ordering-diagnostics", diagnostics, session_id=session_id)
            report["ordering_diagnostics"] = stages.summarize_ordering(diagnostics)
            report["model"] = {"status": "not_enabled" if not enable_model else "gate_no_go",
                               "physical_calls": 0, "planned_denominator": 80 if profile == "FULL" else 0}
            if enable_model and not prior_model_stopped:
                report["model"]["status"] = "prior_stop_unconfirmed"
            if enable_model and gate["passed"] and prior_model_stopped:
                from .study_runner import run_model_studies
                model_stopped = False
                model_ready_config = config
                if evidence_mode == "production":
                    model_ready_config, bootstrap_receipt = _bootstrap_environment(
                        bootstrap_plan, gate, ledger, root, session_id)
                    report["offline_bootstrap"] = bootstrap_receipt
                    evidence.stage_snapshot(root, "offline-bootstrap", bootstrap_receipt, session_id=session_id)
                report["model"] = run_model_studies(
                    tasks, pool, report["coverage"], ledger, session_id=session_id,
                    model_config=model_ready_config, evidence_mode=evidence_mode,
                    backend_factory=_test_backend, verify_callback=checked)
                model_stopped = prior_model_stopped and report["model"]["stop_ack"]["model_owner_stopped"] is True
                evidence.stage_snapshot(root, "model-studies", report["model"], session_id=session_id)
            complete = report["controls"]["complete"] and report["coverage"]["complete"] and prior_model_stopped
            if enable_model and gate["passed"]:
                complete = complete and report["model"].get("status") == "complete"
            report["status"] = "complete" if complete else "partial-inconclusive"
            if complete and not gate["passed"]:
                report["research_outcome"] = "no-go" if profile == "FULL" else "smoke-only"
            else:
                report["research_outcome"] = "testability-only" if gate["passed"] else "inconclusive"
        except Exception as exc:
            report["status"] = "partial-inconclusive"
            model_stopped = _prior_model_stopped(ledger)
            report["error"] = {"type": type(exc).__name__, "message": str(exc)[:1200]}
            report.setdefault("gate", {"passed": False, "reasons": ["workflow incomplete"]})
            ledger.set_state("partial", "retained diagnostic failure: " + type(exc).__name__)
        finally:
            report["workers_used"] = checked.workers_used
            report["ledger"] = _compact_ledger(ledger)
            report["processes"] = {"model_owner_stopped": model_stopped,
                                   "verifier_descendants_stopped": checked.all_stopped}
            evidence.stage_snapshot(root, "summary", report, session_id=session_id)
            if model_stopped and checked.all_stopped:
                archive = evidence.seal_and_archive(root, stopped=report["processes"],
                                                    summary={k: v for k, v in report.items()
                                                             if k not in {"controls", "coverage"}},
                                                    session_id=session_id)
                ledger.finish(archive_id, {"archive_seconds": archive["seconds"]})
                evidence.write_new(root / "archives" / ("completion-" + session_id + ".json"), archive)
            else:
                report["global_seal"] = "withheld: owned resource stop is unconfirmed"
            state = "complete" if report["status"] == "complete" and _physical_complete(ledger) and archive else "partial"
            # A failed CPU phase can retain an unresolved overhead reservation;
            # session exit will charge it conservatively, never erase it.
            unresolved = ledger.summary()["operation_states"]
            if unresolved["reserved"] or unresolved["responded"] or unresolved["unknown"]:
                state = "partial"
            ledger.set_state(state, report["research_outcome"] if "research_outcome" in report else "inconclusive")
            report["final_accounting"] = _compact_ledger(ledger)
    return {"status": report["status"], "output_root": str(root), "archive": archive,
            "session_id": session_id, "report": report}
