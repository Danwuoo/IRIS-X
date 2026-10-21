"""One Linux model leaf: public pinned backend only; no evaluator imports."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import time

from tools.public_sft141_diagnostic import contract as codec
from tools.public_sft141_diagnostic import model_pins
from tools.public_sft141_diagnostic.model_worker import TransformersBackend
from tools.public_sft141_submission import contract as wire
from tools.public_sft141_submission import files
from . import core


class WorkerArtifacts:
    def __init__(self, root):
        self.root = Path(root)

    def write(self, relative, value):
        if Path(relative).name != relative or not relative.endswith(".json"):
            raise ValueError("backend artifact must be one immediate JSON file")
        core.publish(self.root / relative, value)


def model_file_state(directory):
    root = files.safe_path(directory)
    # The source pin verifier follows paths; prohibit links before calling it.
    with files.parent_directory(root / "config.json"):
        pass
    result = {}
    for name in model_pins.MODEL_FILES:
        info = (root / name).lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("public model files must be regular, non-symlink files")
        result[name] = [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
    return result


def state_snapshot(backend):
    model = getattr(backend, "model", None)
    if model is None:
        return {"kind": "synthetic-no-model", "value": getattr(backend, "state", None)}
    # Version/pointer/structure guard, NOT a cryptographic hash of GPU tensors.
    return {"kind": "pytorch-inference-version-pointer-structure-guard",
            "training_modules": [name for name, module in model.named_modules() if module.training],
            "parameters": [[name, list(p.shape), str(p.dtype), str(p.device),
                            p.data_ptr(), p._version, p.requires_grad]
                           for name, p in model.named_parameters()],
            "buffers": [[name, list(b.shape), str(b.dtype), str(b.device), b.data_ptr(), b._version]
                        for name, b in model.named_buffers()]}


def clean_raw(value):
    if not isinstance(value, dict):
        raise ValueError("backend generation must return a record")
    tokens = value.get("token_ids")
    if not isinstance(tokens, list) or any(type(t) is not int for t in tokens) or len(tokens) > 931:
        raise ValueError("backend violated fixed 931 integer-token generation ceiling")
    if not core._finite(value.get("seconds")):
        raise ValueError("backend returned invalid generation duration")
    termination = value.get("termination")
    if termination not in ("eos", "max_tokens", "deadline"):
        raise ValueError("backend returned unknown termination")
    if (termination == "eos") != bool(tokens and tokens[-1] == codec.EOS_ID):
        raise ValueError("backend termination disagrees with raw answer")
    return {"token_ids": tokens, "generated_tokens": len(tokens), "seconds": value["seconds"],
            "memory": value.get("memory"), "termination": termination}


def run_worker(run_dir, *, factory=None):
    root = files.safe_path(run_dir)
    dispatch, _ = files.load_json(root / "dispatch.json")
    challenge, raw = files.load_json(root / "challenge.json")
    plan, plan_raw = files.load_json(root / "plan.json")
    core.validate_plan(plan, challenge, wire.digest(raw))
    if dispatch["plan_sha256"] != wire.digest(plan_raw) or dispatch["source"] != core.source_identity():
        raise ValueError("worker source/plan does not match original dispatch")
    if factory is not None and dispatch["execution_kind"] != "synthetic-injected-no-model-evidence":
        raise ValueError("injected test backend cannot impersonate the public model")
    if factory is None and dispatch["execution_kind"] != "public-pinned-model":
        raise ValueError("public backend requires public execution identity")
    deadline = core.SharedDeadline(dispatch["start_monotonic"], dispatch["budget_seconds"])
    worker = root / "worker"
    worker.mkdir(mode=0o700)
    (worker / "receipts").mkdir(mode=0o700)
    artifacts = WorkerArtifacts(worker)
    rows = core.inventory(plan)
    artifacts.write("inventory.json", {"schema": core.SCHEMA, "queries": rows})
    artifacts.write("identity.json", {"source": dispatch["source"], "plan_sha256": wire.digest(plan_raw),
                                    "pid": os.getpid(), "pgid": os.getpgrp(),
                                    "session": os.getsid(0), "execution_kind": dispatch["execution_kind"]})
    backend, initial_state, pins_state = None, None, None
    state_status = "unknown"
    status, error = "failed", None
    phase = "admission"
    try:
        deadline.check()
        if not core.schedule(rows):
            artifacts.write("admission.json", {"effective_context": core.CONTEXT_CAP,
                                               "model_loads": 0, "reason": "all-queries-context-overflow"})
            status = "no-admissible-queries"
        else:
            phase = "model-pin-verification"
            if factory is None:
                pins_state = model_file_state(dispatch["model_dir"])
                pins = model_pins.verify_model(dispatch["model_dir"])
                if model_file_state(dispatch["model_dir"]) != pins_state:
                    raise ValueError("public model files changed during SHA verification")
                artifacts.write("model_identity.json", pins)
                deadline.check()
                phase = "model-load"
                backend = TransformersBackend(dispatch["model_dir"], plan, deadline, artifacts)
                if model_file_state(dispatch["model_dir"]) != pins_state:
                    raise ValueError("public model files changed during load")
                for parameter in backend.model.parameters():
                    parameter.requires_grad_(False)
            else:
                phase = "synthetic-load"
                backend = factory(plan, deadline)
            deadline.check()
            if type(backend.max_context) is not int or not 1 <= backend.max_context <= core.CONTEXT_CAP:
                raise ValueError("backend context exceeds fixed public cap")
            artifacts.write("backend.json", backend.metadata)
            artifacts.write("admission.json", {"effective_context": backend.max_context,
                                               "model_loads": 1, "reason": "full-support-all-eight-view-admission"})
            initial_state = state_snapshot(backend)
            if initial_state.get("training_modules"):
                raise ValueError("model is not entirely in inference/eval mode")
            artifacts.write("model_state_before.json", initial_state)
            phase = "generation"
            # Full view-major sequence is independent of answers, costs, and correctness.
            queries = [(parent, query) for parent in plan["parents"] for query in parent["test"]]
            for ordinal, i, view in core.schedule(rows, backend.max_context):
                deadline.check()
                parent, query = queries[i]
                prompt = codec.prompt_ids(parent["train"], query["input"], view)
                operation = core.operation_identity(rows, ordinal, i, view)
                if wire.digest(wire.canonical(prompt)) != operation["prompt_sha256"]:
                    raise ValueError("full-support prompt changed after admission")
                begin = time.monotonic()
                core.publish(worker / "receipts" / f"{ordinal:08d}-start.json",
                             {"operation": operation, "started_monotonic": begin})
                try:
                    generated = clean_raw(backend.generate(prompt, codec.MAX_NEW_TOKENS, deadline))
                    after = state_snapshot(backend)
                    if after != initial_state:
                        state_status = "changed"
                        raise ValueError("model state guard changed during inference")
                    core.publish(worker / "receipts" / f"{ordinal:08d}-end.json",
                                 {"operation": operation, "outcome": "returned",
                                  "elapsed_seconds": time.monotonic() - begin,
                                  "raw": generated, "error": None})
                except Exception as exc:
                    core.publish(worker / "receipts" / f"{ordinal:08d}-end.json",
                                 {"operation": operation, "outcome": "failed",
                                  "elapsed_seconds": time.monotonic() - begin,
                                  "raw": None, "error": f"{type(exc).__name__}: {exc}"})
                    raise
            status = "all-admissible-views-returned"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        status = "deadline" if isinstance(exc, TimeoutError) else "failed"
    finally:
        if initial_state is not None:
            try:
                after = state_snapshot(backend)
                if after != initial_state:
                    state_status = "changed"
                elif state_status != "changed":
                    state_status = "unchanged"
                if pins_state is not None and model_file_state(dispatch["model_dir"]) != pins_state:
                    state_status = "changed"
                    status, error = "failed", "public model file metadata changed after verification"
                artifacts.write("model_state_after.json", {"status": state_status, "snapshot": after,
                    "qualification": "Version/pointer/structure and file-metadata guard, not a cryptographic GPU-state proof."})
            except Exception as exc:
                status, error = "failed", f"state closure failed: {type(exc).__name__}: {exc}"
        artifacts.write("terminal.json", {"status": status, "phase": phase, "error": error,
                                           "model_state_guard": state_status, "budget": deadline.receipt()})
    return 0 if status in ("all-admissible-views-returned", "no-admissible-queries") else 3


def main(argv=None, *, factory=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)
    return run_worker(args.run_dir, factory=factory)


if __name__ == "__main__":
    raise SystemExit(main())
