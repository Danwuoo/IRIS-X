"""Exactly-four-invocation L4 x4 runner for ARC-AGI-2 Trial 002 smoke 002.

Torch and Transformers are imported only inside explicit Kaggle runtime paths.
Importing this module locally cannot load a model, touch a GPU, or use a network.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import multiprocessing
import os
from pathlib import Path
import queue
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping

from irisx import arc_trial_002 as core
from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError


RAW_COMPLETION_LIMIT_BYTES = 16_384


def _rotate(grid: list[list[int]], quarter_turns: int) -> list[list[int]]:
    value = [row[:] for row in grid]
    for _ in range(quarter_turns % 4):
        value = [list(row) for row in zip(*value[::-1], strict=True)]
    return value


def _transpose(grid: list[list[int]]) -> list[list[int]]:
    return [list(row) for row in zip(*grid, strict=True)]


def _map_colors(grid: list[list[int]], permutation: list[int]) -> list[list[int]]:
    return [[permutation[cell] for cell in row] for row in grid]


def transform_grid(grid: list[list[int]], view: str, permutation: list[int]) -> list[list[int]]:
    """Retained NVARC-compatible transform helper; smoke 002 uses identity only."""
    value = _map_colors(grid, permutation)
    if view == "identity":
        return value
    if view == "rot90":
        return _rotate(value, 1)
    if view == "rot180":
        return _rotate(value, 2)
    if view == "rot270":
        return _rotate(value, 3)
    if view == "transpose":
        return _transpose(value)
    raise ValidationError(f"unsupported NVARC augmentation view: {view}")


def invert_grid(grid: list[list[int]], view: str, permutation: list[int]) -> list[list[int]]:
    if view == "identity":
        value = grid
    elif view == "rot90":
        value = _rotate(grid, 3)
    elif view == "rot180":
        value = _rotate(grid, 2)
    elif view == "rot270":
        value = _rotate(grid, 1)
    elif view == "transpose":
        value = _transpose(grid)
    else:
        raise ValidationError(f"unsupported NVARC augmentation view: {view}")
    inverse = [0] * 10
    for original, mapped in enumerate(permutation):
        inverse[mapped] = original
    return _map_colors(value, inverse)


def _messages(train: list[dict[str, Any]], test_input: list[list[int]]) -> list[dict[str, str]]:
    demonstrations = "\n\n".join(
        f"Example {index + 1} input:\n{core.grid_to_text(pair['input'])}\n"
        f"Example {index + 1} output:\n{core.grid_to_text(pair['output'])}"
        for index, pair in enumerate(train)
    )
    prompt = (
        "Infer the transformation from the examples. Return only the output grid as digit rows, "
        "with no explanation.\n\n"
        f"{demonstrations}\n\nTest input:\n{core.grid_to_text(test_input)}"
    )
    return [{"role": "user", "content": prompt}]


def _load_base_model(model_root: str) -> tuple[Any, Any, dict[str, Any]]:
    import torch
    from transformers import AutoModelForMultimodalLM, AutoTokenizer

    load_started = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(model_root, local_files_only=True, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    model = AutoModelForMultimodalLM.from_pretrained(
        model_root,
        local_files_only=True,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    ).cuda()
    model.eval()
    return model, tokenizer, {"load_seconds": time.monotonic() - load_started}


def _cap_completion(text: str) -> tuple[str, int, bool]:
    encoded = text.encode("utf-8")
    if len(encoded) <= RAW_COMPLETION_LIMIT_BYTES:
        return text, len(encoded), False
    return encoded[:RAW_COMPLETION_LIMIT_BYTES].decode("utf-8", errors="ignore"), len(encoded), True


def _generate_once(
    model: Any,
    tokenizer: Any,
    task: Mapping[str, Any],
    configuration: Mapping[str, Any],
    deadline: float,
) -> tuple[list[list[list[int]]], dict[str, Any]]:
    """Perform exactly one model.generate call returning exactly one sequence."""
    import torch

    settings = configuration["generation"]
    if (
        settings["num_return_sequences"] != 1
        or settings["num_beams"] != 1
        or settings["do_sample"] is not False
        or settings["augmentation_views"] != ["identity"]
        or len(task["test"]) != 1
    ):
        raise RuntimeError("repair smoke generation configuration is not exactly one deterministic sequence")
    prompt = tokenizer.apply_chat_template(
        _messages(task["train"], task["test"][0]["input"]),
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    encoded = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
    input_tokens = int(encoded["attention_mask"].sum().item())
    if time.monotonic() >= deadline:
        raise TimeoutError("job budget expired before its single generation invocation")
    generation_started = time.monotonic()
    with torch.inference_mode():
        generated = model.generate(
            **encoded,
            max_new_tokens=settings["maximum_new_tokens"],
            num_beams=1,
            num_return_sequences=1,
            do_sample=False,
            return_dict_in_generate=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    generation_seconds = time.monotonic() - generation_started
    prompt_width = int(encoded["input_ids"].shape[1])
    suffix = generated.sequences[0][prompt_width:]
    generated_tokens = int(suffix.numel())
    raw = tokenizer.decode(suffix, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    completion, raw_bytes, truncated = _cap_completion(raw)
    parsed = core.parse_grid_text(raw)
    attempts: list[list[list[int]]] = []
    if parsed is not None:
        try:
            attempts = [core.validate_grid(parsed, "single completion grid")]
        except ValidationError:
            attempts = []
    last_token = int(suffix[-1].item()) if generated_tokens else None
    if last_token is not None and tokenizer.eos_token_id is not None and last_token == int(tokenizer.eos_token_id):
        stop_reason = "eos_token"
    elif generated_tokens >= settings["maximum_new_tokens"]:
        stop_reason = "maximum_new_tokens"
    else:
        stop_reason = "unknown"
    return attempts, {
        "input_tokens": input_tokens,
        "generated_tokens": generated_tokens,
        "generation_seconds": generation_seconds,
        "tokens_per_second": generated_tokens / generation_seconds if generation_seconds > 0 else None,
        "raw_completion": completion,
        "raw_completion_bytes": raw_bytes,
        "raw_completion_truncated": truncated,
        "parse_state": "valid_grid" if attempts else "invalid_grid",
        "stop_reason": stop_reason,
    }


def _generation_record(
    invocation_ordinal: int | None,
    *,
    metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = dict(metrics or {})
    return {
        "invocation_ordinal": invocation_ordinal,
        "raw_completion": metrics.get("raw_completion"),
        "raw_completion_bytes": metrics.get("raw_completion_bytes"),
        "raw_completion_truncated": metrics.get("raw_completion_truncated", False),
        "parse_state": metrics.get("parse_state", "not_available"),
        "stop_reason": metrics.get("stop_reason", "not_available"),
    }


def _record(
    task_id: str,
    status: str,
    *,
    invocation_ordinal: int | None = None,
    attempts: list[list[list[int]]] | None = None,
    failure: str | None = None,
    timing: Mapping[str, Any] | None = None,
    tokens: Mapping[str, Any] | None = None,
    generation: Mapping[str, Any] | None = None,
    peak_mib: int | None = None,
) -> dict[str, Any]:
    attempts = attempts or []
    return {
        "job_key": f"{task_id}:0",
        "task_id": task_id,
        "test_index": 0,
        "status": status,
        "attempts": attempts,
        "valid_model_output": bool(attempts),
        "generated_candidate_count": len(attempts),
        "failure": failure,
        "timing": dict(timing or {}),
        "tokens": dict(tokens or {}),
        "generation": _generation_record(invocation_ordinal, metrics=generation),
        "gpu_peak_memory_mib": peak_mib,
    }


def _worker(
    rank: int,
    model_root: str,
    task: Mapping[str, Any],
    configuration: Mapping[str, Any],
    command_queue: Any,
    output_queue: Any,
) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(rank)
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    task_id = task["task_id"]
    job_key = f"{task_id}:0"
    invocation_ordinal: int | None = None
    try:
        import torch

        torch.cuda.set_device(0)
        torch.manual_seed(configuration["generation"]["seed"] + rank)
        torch.cuda.reset_peak_memory_stats()
        output_queue.put({"type": "stage", "rank": rank, "task_id": task_id, "stage": "model_load"})
        model, tokenizer, load_timing = _load_base_model(model_root)
        output_queue.put({"type": "ready", "rank": rank, "task_id": task_id, "job_key": job_key, "load": load_timing})
        command = command_queue.get()
        deadline = float(command["deadline"])
        invocation_ordinal = int(command["invocation_ordinal"])
        output_queue.put({"type": "stage", "rank": rank, "task_id": task_id, "stage": "single_generate"})
        attempts, metrics = _generate_once(model, tokenizer, task, configuration, deadline)
        peak = int(torch.cuda.max_memory_allocated() // (1024 * 1024))
        status = "valid" if attempts else "invalid"
        output_queue.put(
            {
                "type": "record",
                "rank": rank,
                "record": _record(
                    task_id,
                    status,
                    invocation_ordinal=invocation_ordinal,
                    attempts=attempts,
                    failure=None if attempts else "single model completion was not a parseable valid grid",
                    timing={"load_seconds": load_timing["load_seconds"], "generation_seconds": metrics["generation_seconds"], "ttft_seconds": "unknown", "prefill_seconds": "unknown"},
                    tokens={"input": metrics["input_tokens"], "generated": metrics["generated_tokens"], "tokens_per_second": metrics["tokens_per_second"]},
                    generation=metrics,
                    peak_mib=peak,
                ),
            }
        )
    except Exception as exc:
        status = "timeout" if isinstance(exc, TimeoutError) else ("oom" if "out of memory" in str(exc).lower() else "worker_crash")
        output_queue.put(
            {
                "type": "failure",
                "rank": rank,
                "task_id": task_id,
                "job_key": job_key,
                "invocation_ordinal": invocation_ordinal,
                "status": status,
                "detail": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=20),
            }
        )


def collect_runtime_hardware() -> dict[str, Any]:
    import torch

    count = torch.cuda.device_count()
    gpus: list[dict[str, Any]] = []
    for index in range(count):
        properties = torch.cuda.get_device_properties(index)
        gpus.append(
            {
                "index": index,
                "name": properties.name,
                "memory_mib": int(properties.total_memory // (1024 * 1024)),
                "capability": f"{properties.major}.{properties.minor}",
                "uuid": str(getattr(properties, "uuid", "unknown")),
            }
        )
    completed = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,name,memory.total,uuid,pci.bus_id", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    return {
        "torch_cuda_device_count": count,
        "gpus": gpus,
        "nvidia_smi_exit_code": completed.returncode,
        "nvidia_smi_rows": [line.strip() for line in completed.stdout.splitlines() if line.strip()],
        "cuda": torch.version.cuda,
        "cudnn": str(torch.backends.cudnn.version()),
        "torch": torch.__version__,
        "python": sys.version.split()[0],
    }


def validate_runtime_hardware(hardware: Mapping[str, Any]) -> None:
    gpus = hardware.get("gpus")
    if hardware.get("torch_cuda_device_count") != core.WORKER_COUNT or not isinstance(gpus, list) or len(gpus) != core.WORKER_COUNT:
        raise RuntimeError(f"Trial 002 requires exactly four GPUs; observed {hardware.get('torch_cuda_device_count')}")
    if any("L4" not in item["name"] or item["memory_mib"] < 22000 for item in gpus):
        raise RuntimeError(f"Trial 002 requires four L4 GPUs with at least 22000 MiB each; observed {gpus}")
    if hardware.get("nvidia_smi_exit_code") != 0 or len(hardware.get("nvidia_smi_rows", [])) != core.WORKER_COUNT:
        raise RuntimeError("nvidia-smi did not independently report exactly four devices")


def runtime_preflight() -> dict[str, Any]:
    hardware = collect_runtime_hardware()
    validate_runtime_hardware(hardware)
    return hardware


def _progress_event(path: Path, event: Mapping[str, Any]) -> bytes:
    payload = canonical_bytes(dict(event), newline=True)
    with path.open("ab") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    print(payload.decode("utf-8").rstrip(), flush=True)
    return payload


def run(
    outbound: Path,
    model_root: Path,
    competition_challenges: Path,
    output: Path,
    checkpoint_output: Path,
    progress_output: Path,
    resume_checkpoint: Path | None = None,
) -> str:
    session_started = time.monotonic()
    manifest, contents, _ = core.verify_outbound_package(outbound)
    run_binding = json.loads(contents["bindings/run.json"])
    solver = json.loads(contents["cases/solver-cases.json"])
    progress_output.parent.mkdir(parents=True, exist_ok=True)
    progress_output.write_bytes(b"")
    _progress_event(progress_output, {"event": "runtime_preflight_started", "run_id": core.RUN_ID, "elapsed_seconds": 0.0})
    hardware = collect_runtime_hardware()
    _progress_event(progress_output, {"event": "runtime_hardware_observed", "elapsed_seconds": time.monotonic() - session_started, "hardware": hardware})
    validate_runtime_hardware(hardware)
    competition_evidence = core.validate_competition_mount(competition_challenges, run_binding, solver)
    _progress_event(progress_output, {"event": "competition_mount_validated", "elapsed_seconds": time.monotonic() - session_started, **competition_evidence})
    model_manifest = json.loads(contents["sources/model-manifest.json"])
    core.validate_material_manifest(model_root, model_manifest)

    if resume_checkpoint is None:
        checkpoint = core.new_checkpoint(run_binding, solver)
    else:
        checkpoint = core.load_checkpoint(resume_checkpoint, run_binding, solver)
        if checkpoint["complete"]:
            raise ValidationError("refusing to resume an already-complete Trial 002 checkpoint")
    prior_charged_seconds = float(checkpoint["cumulative_charged_seconds"])
    session_index = len(checkpoint["sessions"])
    checkpoint["sessions"].append(
        {
            "session_index": session_index,
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hardware": hardware,
            "charged_seconds": 0.0,
        }
    )
    core.atomically_write_json(checkpoint_output, checkpoint)
    _progress_event(
        progress_output,
        {
            "event": "session_start",
            "run_id": core.RUN_ID,
            "elapsed_seconds": time.monotonic() - session_started,
            "outbound_manifest_digest": core.digest_value(manifest),
            "resume": resume_checkpoint is not None,
            "prior_charged_seconds": prior_charged_seconds,
        },
    )

    tasks = solver["cases"]
    expected_by_task = {
        task["task_id"]: [f"{task['task_id']}:0"]
        for task in tasks
        if f"{task['task_id']}:0" not in checkpoint["completed"]
    }
    state = core.SupervisorState(expected_by_task)
    context = multiprocessing.get_context("spawn")
    output_queue = context.Queue()
    processes: dict[str, Any] = {}
    command_queues: dict[str, Any] = {}
    compute_seconds_remaining = max(0.0, core.SESSION_BUDGET_SECONDS - core.FINALIZATION_RESERVE_SECONDS - prior_charged_seconds)
    global_stop = session_started + compute_seconds_remaining
    prior_started = set(checkpoint["generation_invocations"])
    tasks_to_run = [task for task in tasks if task["task_id"] in expected_by_task and f"{task['task_id']}:0" not in prior_started]
    failures: dict[str, tuple[str, str]] = {
        task["task_id"]: ("worker_crash", "prior checkpoint consumed this generation invocation; resume will not generate again")
        for task in tasks
        if f"{task['task_id']}:0" in prior_started and f"{task['task_id']}:0" not in checkpoint["completed"]
    }
    for rank, task in enumerate(tasks):
        if task not in tasks_to_run:
            continue
        task_id = task["task_id"]
        command_queue = context.Queue()
        process = context.Process(
            target=_worker,
            args=(rank, str(model_root), task, run_binding["configuration"], command_queue, output_queue),
            name=f"trial002-{task_id}",
        )
        process.start()
        processes[task_id] = process
        command_queues[task_id] = command_queue
        _progress_event(progress_output, {"event": "worker_started", "task_id": task_id, "rank": rank, "elapsed_seconds": time.monotonic() - session_started})

    model_loads: dict[str, Any] = {}
    last_heartbeat = 0.0

    def charged_seconds() -> float:
        return min(core.SESSION_BUDGET_SECONDS, prior_charged_seconds + time.monotonic() - session_started)

    def finish_invocation_if_started(job_key: str, status: str) -> int | None:
        invocation = checkpoint["generation_invocations"].get(job_key)
        if not isinstance(invocation, dict):
            return None
        if invocation["status"] == "started":
            core.finish_generation_invocation(checkpoint, job_key, status, run_binding, solver)
            core.atomically_write_json(checkpoint_output, checkpoint)
        return int(invocation["ordinal"])

    def accept_message(message: Mapping[str, Any]) -> None:
        event_type = message.get("type")
        if event_type == "ready":
            task_id = message["task_id"]
            job_key = message["job_key"]
            model_loads[task_id] = message["load"]
            dispatched = time.monotonic()
            deadline = min(dispatched + core.TASK_DEADLINE_SECONDS, global_stop)
            state.dispatch(task_id, dispatched)
            ordinal = core.start_generation_invocation(checkpoint, job_key, message["rank"], run_binding, solver)
            checkpoint["cumulative_charged_seconds"] = charged_seconds()
            checkpoint["sessions"][session_index]["charged_seconds"] = time.monotonic() - session_started
            core.atomically_write_json(checkpoint_output, checkpoint)
            _progress_event(progress_output, {"event": "generation_invocation_started", "job_key": job_key, "ordinal": ordinal, "rank": message["rank"], "elapsed_seconds": dispatched - session_started})
            command_queues[task_id].put({"deadline": deadline, "invocation_ordinal": ordinal})
        elif event_type == "stage":
            _progress_event(progress_output, {**message, "elapsed_seconds": time.monotonic() - session_started})
        elif event_type == "record":
            record = message["record"]
            finish_invocation_if_started(record["job_key"], "completed")
            state.accept(record)
            core.record_terminal(checkpoint, record, run_binding, solver)
            checkpoint["cumulative_charged_seconds"] = charged_seconds()
            checkpoint["sessions"][session_index]["charged_seconds"] = time.monotonic() - session_started
            core.atomically_write_json(checkpoint_output, checkpoint)
            _progress_event(progress_output, {"event": "job_terminal", "job_key": record["job_key"], "status": record["status"], "elapsed_seconds": time.monotonic() - session_started})
        elif event_type == "failure":
            finish_invocation_if_started(message["job_key"], "failed")
            failures.setdefault(message["task_id"], (message["status"], message["detail"]))
            safe = {key: value for key, value in message.items() if key != "traceback"}
            _progress_event(progress_output, {**safe, "elapsed_seconds": time.monotonic() - session_started})
        else:
            task_id = message.get("task_id")
            if isinstance(task_id, str):
                failures.setdefault(task_id, ("worker_crash", f"unknown worker event: {event_type!r}"))

    while any(process.is_alive() for process in processes.values()):
        now = time.monotonic()
        elapsed = now - session_started
        if elapsed - last_heartbeat >= 15:
            _progress_event(progress_output, {"event": "heartbeat", "elapsed_seconds": elapsed, "remaining_session_seconds": max(0.0, global_stop - now), "completed_jobs": len(checkpoint["completed"]), "total_jobs": core.GENERATION_INVOCATION_QUOTA})
            last_heartbeat = elapsed
        if now >= global_stop:
            for task_id, process in processes.items():
                if process.is_alive():
                    process.terminate()
                    finish_invocation_if_started(f"{task_id}:0", "failed")
                    failures.setdefault(task_id, ("not_executed", "session compute stop reached before terminal result"))
            break
        for task_id in state.expired_tasks(now):
            process = processes[task_id]
            if process.is_alive():
                process.terminate()
            finish_invocation_if_started(f"{task_id}:0", "failed")
            failures.setdefault(task_id, ("timeout", "independent 300-second job deadline reached"))
        try:
            accept_message(output_queue.get(timeout=1.0))
        except queue.Empty:
            continue

    for process in processes.values():
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
    while True:
        try:
            accept_message(output_queue.get(timeout=0.25))
        except queue.Empty:
            break

    for task_id, keys in expected_by_task.items():
        key = keys[0]
        if key in checkpoint["completed"]:
            continue
        ordinal = finish_invocation_if_started(key, "failed")
        status, detail = failures.get(task_id, ("worker_crash", "worker exited without a terminal record"))
        record = _record(task_id, status, invocation_ordinal=ordinal, failure=detail)
        state.accept(record)
        core.record_terminal(checkpoint, record, run_binding, solver)
        _progress_event(progress_output, {"event": "job_terminal", "job_key": key, "status": status, "elapsed_seconds": time.monotonic() - session_started})

    wall_seconds = time.monotonic() - session_started
    checkpoint["cumulative_charged_seconds"] = min(core.SESSION_BUDGET_SECONDS, prior_charged_seconds + wall_seconds)
    checkpoint["sessions"][session_index]["charged_seconds"] = wall_seconds
    checkpoint["complete"] = True
    core.validate_checkpoint(checkpoint, run_binding, solver)
    core.atomically_write_json(checkpoint_output, checkpoint)
    statuses = Counter(record["status"] for record in checkpoint["completed"].values())
    invocation_statuses = Counter(item["status"] for item in checkpoint["generation_invocations"].values())
    import transformers

    observations = {
        "format": "irisx/arc-agi-2-trial-002-execution",
        "format_version": "2.0",
        "trial_id": core.TRIAL_ID,
        "run_id": core.RUN_ID,
        "session_wall_seconds": wall_seconds,
        "hardware": hardware["gpus"],
        "nvidia_smi_rows": hardware["nvidia_smi_rows"],
        "software": {"python": hardware["python"], "torch": hardware["torch"], "transformers": transformers.__version__, "cuda": hardware["cuda"], "cudnn": hardware["cudnn"]},
        "competition_input": competition_evidence,
        "internet_enabled": False,
        "external_paid_cost_usd": 0,
        "model_loads": model_loads,
        "generation_invocation_quota": core.GENERATION_INVOCATION_QUOTA,
        "generation_invocation_status_counts": dict(sorted(invocation_statuses.items())),
        "valid_generation_jobs": statuses.get("valid", 0),
        "terminal_status_counts": dict(sorted(statuses.items())),
        "ttft_state": "unknown",
        "gpu_busy_time_state": "unknown",
    }
    _progress_event(progress_output, {"event": "session_complete", "elapsed_seconds": wall_seconds, "generation_invocation_status_counts": dict(sorted(invocation_statuses.items())), "valid_generation_jobs": statuses.get("valid", 0), "terminal_status_counts": dict(sorted(statuses.items()))})
    return core.build_result_package(output, run_binding, solver, checkpoint, observations, progress_output.read_bytes())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run exactly four Qwen3.5 generation invocations on Kaggle L4 x4")
    parser.add_argument("--outbound", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--competition-challenges", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--checkpoint-output", required=True, type=Path)
    parser.add_argument("--progress-output", required=True, type=Path)
    parser.add_argument("--resume-checkpoint", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        digest = run(args.outbound, args.model_root, args.competition_challenges, args.output, args.checkpoint_output, args.progress_output, args.resume_checkpoint)
    except Exception as exc:
        failure_path = args.progress_output.with_name("runtime-failure.json")
        failure_path.write_bytes(
            canonical_bytes(
                {
                    "format": "irisx/arc-agi-2-trial-002-runtime-failure",
                    "format_version": "1.0",
                    "run_id": core.RUN_ID,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(limit=30),
                },
                newline=True,
            )
        )
        print(f"trial-002 runner failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 2
    print(f"trial-002 result: {args.output} {digest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
