"""Gold-free owned model leaf: one load, calibration freeze, unchanged base run."""
from __future__ import annotations

from pathlib import Path
import sys
import time

from tools.public_demo_calibration import core, runtime
from tools.public_sft141_diagnostic import contract, model_worker as base
from tools.public_sft141_diagnostic.model_pins import verify_model
from .common import (admit, assemble_pool, frozen, inherited, load_if, read_bytes,
                     sha, verify_sources, new_artifacts)


class Trace:
    def __init__(self, artifacts, deadline, intent):
        self.artifacts, self.deadline, self.intent = artifacts, deadline, intent
        self.event, self.phase, self.calibration_hash = 0, "load", None

    def emit(self, kind, **values):
        self.event += 1
        row = {"event": self.event, "kind": kind, "phase": self.phase,
               "elapsed_seconds": self.deadline.clock() - self.deadline.start,
               "original_started_monotonic": self.deadline.start, **values}
        self.artifacts.write(f"receipts/trace-{self.event:05d}.json", row)
        return self.event


class GuardedBackend:
    """Same backend object and original clock at every stage; no second loader."""
    def __init__(self, backend, trace, worker):
        self.backend, self.trace, self.worker = backend, trace, Path(worker)
        self.metadata, self.max_context = backend.metadata, backend.max_context
        if hasattr(backend, "model"):
            self.model = backend.model

    def memory_snapshot(self):
        fn = getattr(self.backend, "memory_snapshot", None)
        return fn() if fn else None

    def _call(self, operation, prompt, answer_or_limit, deadline):
        if deadline is not self.trace.deadline:
            raise ValueError("stage replaced the inherited deadline")
        if operation == "generate":
            freeze = load_if(self.worker / "calibration_freeze.json")
            if (self.trace.phase != "task_test" or freeze is None or
                    sha(read_bytes(self.worker / "calibration/calibration.json")) != freeze["calibration_file_sha256"] or
                    freeze["calibration_sha256"] != self.trace.calibration_hash):
                raise ValueError("generation before immutable calibration freeze")
        event = self.trace.emit("operation_start", operation=operation,
            prompt_sha256=core.digest(prompt),
            answer_sha256=core.digest(answer_or_limit) if operation == "score" else None)
        try:
            result = getattr(self.backend, operation)(prompt, answer_or_limit, deadline)
        except BaseException as exc:
            self.trace.emit("operation_failed", operation=operation, start_event=event,
                            error=f"{type(exc).__name__}: {exc}", cost_unknown=True)
            raise
        self.trace.emit("operation_finished", operation=operation, start_event=event,
                        result_sha256=core.digest(result), result=result, late=deadline.expired())
        return result

    def score(self, prompt, answer, deadline):
        return self._call("score", prompt, answer, deadline)

    def generate(self, prompt, ceiling, deadline):
        return self._call("generate", prompt, ceiling, deadline)


class BoundArtifacts:
    """Keep base files byte-for-byte unchanged and append independent bindings."""
    def __init__(self, artifacts, trace):
        self.base, self.trace = artifacts, trace

    def write(self, relative, value):
        self.base.write(relative, value)
        if relative.startswith("receipts/view-"):
            event = self.trace.emit("raw_view_published", relative=relative,
                calibration_sha256=self.trace.calibration_hash)
            self.trace.artifacts.write("receipts/bound-" + Path(relative).name, {
                "event": event, "raw_sha256": sha(read_bytes(self.base.root / relative)),
                "calibration_sha256": self.trace.calibration_hash,
                "source_identity_sha256": core.digest(self.trace.intent["source_identity"]),
                "late": self.trace.deadline.expired()})


def verify_loo_tokenizer(plan, backend, deadline):
    parents = {p["task_id"]: p for p in plan["parents"]}
    for spec, prompt, answer in core.cases(plan):
        deadline.check()
        train = parents[spec["task_id"]]["train"]
        held, view = spec["held_support_index"], spec["view"]
        text = contract.prompt_text([train[i] for i in spec["conditioned_support_indices"]], train[held]["input"], view)
        target = contract.grid_text(contract.transform(train[held]["output"], view)) + "<|im_end|>"
        if backend.tokenizer.encode(text, add_special_tokens=False) != prompt or backend.tokenizer.encode(target, add_special_tokens=False) != answer:
            raise ValueError("exact real tokenizer does not match full LOO prompt/EOS target")


def execute(intent, output):
    """No gold pathname or evaluator is accepted or imported in this process."""
    deadline = inherited(intent["budget_seconds"], intent["started_monotonic"])
    artifacts = new_artifacts(output)
    trace = Trace(artifacts, deadline, intent)
    try:
        verify_sources(intent["source_identity"])
        plan = frozen(intent["plan_path"], intent["plan_file_sha256"])
        admit(plan, intent["plan_file_sha256"], intent["execution_kind"])
        schedule = core.prepare(plan, 8192, deadline.seconds)
        artifacts.write("schedule.json", schedule)
        if not schedule["context_admitted"]:
            raise ValueError("full-context admission failed before loading; truncation forbidden")
        deadline.check()
        trace.emit("model_load_start")
        verification = None
        if intent["execution_kind"] == "public_model":
            verification = verify_model(intent["model_dir"])
            artifacts.write("model_verification.json", verification)
            deadline.check()
            backend = base.TransformersBackend(intent["model_dir"], plan, deadline, artifacts)
            if backend.metadata["model_class"] != "Qwen3ForCausalLM":
                raise ValueError("exact native Qwen3ForCausalLM backend required")
            verify_loo_tokenizer(plan, backend, deadline)
        else:
            from .synthetic import SyntheticBackend
            backend = SyntheticBackend(plan, deadline, intent.get("synthetic_fault", "none"))
        deadline.check()
        trace.emit("model_load_finished", backend=backend.metadata, model_load_count=1)
        guarded = GuardedBackend(backend, trace, output)
        trace.phase = "calibration"
        calibration_artifacts = new_artifacts(Path(output) / "calibration")
        calibration = runtime.collect(plan, guarded, Path(output) / "calibration", deadline,
            execution_kind=intent["execution_kind"], session_id=intent["session_id"],
            public_verification=verification, artifacts=calibration_artifacts)
        model_snapshot = runtime._versions(guarded)
        trace.calibration_hash = core.digest(calibration)
        event = trace.emit("calibration_frozen", calibration_sha256=trace.calibration_hash)
        artifacts.write("calibration_freeze.json", {"event": event,
            "calibration_sha256": trace.calibration_hash,
            "calibration_file_sha256": sha(read_bytes(Path(output) / "calibration/calibration.json")),
            "source_identity_sha256": core.digest(intent["source_identity"]),
            "session_id": intent["session_id"], "budget": deadline.receipt()})
        if calibration["status"] != "complete":
            raise ValueError("incomplete calibration: task.test generation is forbidden")
        trace.phase = "task_test"
        deadline.check()
        generated = new_artifacts(Path(output) / "generation")
        result = base.run(plan, guarded, generated.root, deadline.seconds,
                          deadline=deadline, artifacts=BoundArtifacts(generated, trace))
        if runtime._versions(guarded) != model_snapshot:
            raise ValueError("model state changed between calibration and base generation/rescoring")
        pool = assemble_pool(plan, calibration, output)
        ranking = core.rank(plan, calibration, pool)
        artifacts.write("pool.json", pool)
        artifacts.write("ranking.json", ranking)
        verify_sources(intent["source_identity"])
        no_late = not deadline.expired()
        complete = (no_late and calibration["status"] == "complete" and result["full_panel_complete"]
                    and ranking["all_pools_complete"] and ranking["all_eligible_calibrations_complete"])
        artifacts.write("closure.json", {"status": "complete" if complete else "partial",
            "model_load_count": 1, "same_backend_all_stages": True, "original_clock_all_stages": True,
            "model_version_snapshot_sha256": core.digest(model_snapshot),
            "state_version_guard_not_cryptographic_parameter_attestation": True,
            "calibration_sha256": core.digest(calibration), "pool_sha256": core.digest(pool),
            "budget": deadline.receipt(), "completed_within_work_deadline": no_late,
            "evaluator_imported": any(n in sys.modules for n in (
                "tools.public_sft141_diagnostic.evaluate", "tools.public_calibrated_solver.evaluation")),
            "model_execution_kind": intent["execution_kind"], "scientific_effectiveness_established": False})
        return 0 if complete else 2
    except Exception as exc:
        artifacts.write("failure.json", {"type": type(exc).__name__, "message": str(exc),
            "phase": trace.phase, "budget": deadline.receipt(), "costs_may_be_unsaved": True,
            "scientific_effectiveness_established": False})
        return 2
