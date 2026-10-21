"""One owned public model leaf, complete calibration before full query generation."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import time

from tools.public_sft141_diagnostic import contract as codec, model_pins
from tools.public_sft141_diagnostic.model_worker import TransformersBackend
from tools.public_sft141_solver.worker import WorkerArtifacts, model_file_state, state_snapshot, clean_raw
from tools.public_sft141_submission import contract as wire, files
from . import core


class NativeContextBackend(TransformersBackend):
    """Retain all native loader gates; explicitly admit configured native context.

    The original backend temporarily applies its unchanged 8192 software cap.
    Only after its native configuration/load verification succeeds do we adopt
    the caller's frozen cap, bounded by the verified unchanged native config.
    No config/RoPE/model mutation, reload, or monkeypatch is performed.
    """
    def __init__(self, model_dir, plan, deadline, artifacts):
        super().__init__(model_dir, plan, deadline, artifacts)
        configured = plan["configuration"]["context_cap"]
        native = self.metadata["model_declared_context"]
        if (type(native) is not int or self.model.config.max_position_embeddings != native or
                configured > native or self.metadata["model_config"]["max_position_embeddings"] != native):
            raise ValueError("configured context is not admitted by unchanged verified native configuration")
        if self.metadata["model_class"] != "Qwen3ForCausalLM":
            raise ValueError("exact native public Qwen3ForCausalLM required")
        self.max_context = configured
        self.metadata = {**self.metadata, "effective_context_cap": configured,
            "integration_context": {"configured": configured, "verified_native": native,
                "legacy_loader_software_cap": 8192, "native_config_unchanged": True,
                "measured_memory_or_runtime_fit": False}}
        artifacts.write("context_admission.json", self.metadata["integration_context"])


def verify_loo_tokenizer(plan, backend, deadline):
    parents = {p["task_id"]: p for p in plan["parents"]}
    for spec, prompt, answer in core.loo_cases(plan):
        deadline.check()
        train = parents[spec["task_id"]]["train"]
        held, view = spec["held_support_index"], spec["view"]
        text = codec.prompt_text([train[i] for i in spec["conditioned_support_indices"]], train[held]["input"], view)
        target = codec.grid_text(codec.transform(train[held]["output"], view)) + "<|im_end|>"
        if (backend.tokenizer.encode(text, add_special_tokens=False) != prompt or
                backend.tokenizer.encode(target, add_special_tokens=False) != answer):
            raise ValueError("real tokenizer differs from complete LOO prompt and EOS target")


def run_worker(run_dir, *, factory=None):
    root = files.safe_path(run_dir)
    dispatch, _ = files.load_json(root / "dispatch.json")
    challenge, raw = files.load_json(root / "challenge.json")
    plan, plan_raw = files.load_json(root / "plan.json")
    core.validate_plan(plan, challenge, wire.digest(raw))
    if dispatch["plan_sha256"] != wire.digest(plan_raw) or dispatch["source"] != core.source_identity():
        raise ValueError("worker source/plan differs from frozen dispatch")
    if (factory is None) != (dispatch["execution_kind"] == "public-pinned-model"):
        raise ValueError("injected CPU fixture cannot impersonate the pinned public model")
    deadline = core.SharedDeadline(dispatch["start_monotonic"], dispatch["budget_seconds"])
    if plan["configuration"] != dispatch["configuration"] or deadline.seconds != plan["configuration"]["budget_seconds"]:
        raise ValueError("worker configuration differs from original frozen plan")
    worker = root / "worker"
    worker.mkdir(mode=0o700)
    (worker / "receipts").mkdir(mode=0o700)
    artifacts = WorkerArtifacts(worker)
    schedule = core.prepare(plan)
    artifacts.write("inventory.json", schedule)
    artifacts.write("identity.json", {"source": dispatch["source"], "plan_sha256": wire.digest(plan_raw),
        "pid": os.getpid(), "pgid": os.getpgrp(), "session": os.getsid(0), "execution_kind": dispatch["execution_kind"]})
    backend = before = pins_state = None
    state_status, status, error, phase = "unknown", "failed", None, "admission"
    ordinal, load_started, load_finished = 0, None, None
    try:
        deadline.check()
        if not schedule["context_admitted"]:
            raise ValueError("whole-panel full-support context admission failed; no model load or query drop")
        phase = "model-load"
        load_started = time.monotonic()
        artifacts.write("load_start.json", {"started_monotonic": load_started, "model_load_attempts": 1})
        if factory is None:
            pins_state = model_file_state(dispatch["model_dir"])
            pins = model_pins.verify_model(dispatch["model_dir"])
            if model_file_state(dispatch["model_dir"]) != pins_state:
                raise ValueError("pinned public model files changed during verification")
            artifacts.write("model_identity.json", pins)
            deadline.check()
            backend = NativeContextBackend(dispatch["model_dir"], plan, deadline, artifacts)
            if model_file_state(dispatch["model_dir"]) != pins_state:
                raise ValueError("public files changed during model load")
            verify_loo_tokenizer(plan, backend, deadline)
        else:
            backend = factory(plan, deadline)
        if type(backend.max_context) is not int or backend.max_context != plan["configuration"]["context_cap"]:
            raise ValueError("backend must explicitly retain exactly the configured admitted context")
        model = getattr(backend, "model", None)
        if model is not None:
            for parameter in model.parameters():
                parameter.requires_grad_(False)
        before = state_snapshot(backend)
        if before.get("training_modules"):
            raise ValueError("all model modules must remain inference/eval-only")
        artifacts.write("model_state_before.json", before)
        artifacts.write("backend.json", backend.metadata)
        load_finished = time.monotonic()
        artifacts.write("load_end.json", {"started_monotonic": load_started, "finished_monotonic": load_finished,
            "elapsed_seconds": load_finished - load_started, "model_loads": 1, "same_backend_all_stages": True})
        deadline.check()

        def call(phase, spec, prompt, answer_or_limit, freeze_hash=None):
            nonlocal ordinal, state_status
            deadline.check()
            if state_snapshot(backend) != before:
                state_status = "changed"
                raise ValueError("model state guard changed before operation")
            op = core.operation(ordinal, phase, spec, freeze_hash)
            name = f"{ordinal:08d}"
            begin = time.monotonic()
            core.publish(worker / "receipts" / (name + "-start.json"), {"operation": op, "started_monotonic": begin})
            ordinal += 1
            try:
                if phase == "generation":
                    result = clean_raw(backend.generate(prompt, answer_or_limit, deadline))
                    if any(not 0 <= t < 16 for t in result["token_ids"]):
                        raise ValueError("generation contains non-native tokens")
                    core.validate_memory(result["memory"])
                else:
                    result = dict(backend.score(prompt, answer_or_limit, deadline))
                    result.setdefault("memory", None)
                    core.clean_score(result, spec)
                if state_snapshot(backend) != before:
                    state_status = "changed"
                    raise ValueError("model state changed during operation")
            except Exception as exc:
                core.publish(worker / "receipts" / (name + "-end.json"), {"operation": op, "outcome": "failed",
                    "elapsed_seconds": time.monotonic() - begin, "raw": None, "error": f"{type(exc).__name__}: {exc}"})
                raise
            core.publish(worker / "receipts" / (name + "-end.json"), {"operation": op, "outcome": "returned",
                "elapsed_seconds": time.monotonic() - begin, "raw": result, "error": None})
            deadline.check()
            if phase == "generation" and result["termination"] == "deadline":
                raise TimeoutError("backend returned interrupted generation")
            return result

        phase = "loo"
        successful = []
        for spec, prompt, answer in core.loo_cases(plan):
            successful.append((spec, call("loo", spec, prompt, answer)))
        deadline.check()
        freeze = core.freeze_value(plan, successful, time.monotonic())
        freeze_hash = core.publish(worker / "calibration_freeze.json", freeze)
        if files.read_bytes(worker / "calibration_freeze.json") != wire.canonical(freeze):
            raise ValueError("calibration freeze readback failed")
        phase = "generation"
        pools = [{} for _ in core.query_cases(plan)]
        for spec, prompt in core.generation_cases(plan):
            result = call("generation", spec, prompt, 931, freeze_hash)
            try:
                grid = codec.inverse(codec.parse_answer(result["token_ids"]), spec["view"])
                pools[spec["query_index"]][wire.grid_key(grid)] = grid
            except ValueError:
                pass  # Invalid output retained verbatim, never repaired.
        phase = "nll"
        for i, ((parent, query), pool) in enumerate(zip(core.query_cases(plan), pools)):
            for key in sorted(pool):
                for view in codec.VIEWS:
                    prompt = codec.prompt_ids(parent["train"], query["input"], view)
                    answer = codec.answer_ids(codec.transform(pool[key], view))
                    spec = core.score_spec("nll", i, pool[key], view, prompt, answer)
                    call("nll", spec, prompt, answer, freeze_hash)
        deadline.check()
        if dispatch["source"] != core.source_identity():
            raise ValueError("public source changed during execution")
        status = "all-phases-returned"
    except Exception as exc:
        status = "deadline" if isinstance(exc, TimeoutError) else "failed"
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if before is not None:
            after = state_snapshot(backend)
            state_status = "unchanged" if after == before and state_status != "changed" else "changed"
            if pins_state is not None and model_file_state(dispatch["model_dir"]) != pins_state:
                state_status, status, error = "changed", "failed", "public model file state changed after load"
            artifacts.write("model_state_after.json", {"status": state_status, "snapshot": after,
                "qualification": "Version/pointer/structure and file metadata guard, not cryptographic GPU tensor attestation."})
        artifacts.write("terminal.json", {"status": status, "phase": phase, "error": error,
            "model_state_guard": state_status, "budget": deadline.receipt(),
            "load_started": load_started, "load_finished": load_finished,
            "model_load_cost_unknown": load_started is not None and load_finished is None,
            "calibration_probe_calls": 0, "model_loads": int(load_finished is not None)})
    return 0 if status == "all-phases-returned" else 3


def main(argv=None, *, factory=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)
    return run_worker(args.run_dir, factory=factory)


if __name__ == "__main__":
    raise SystemExit(main())
