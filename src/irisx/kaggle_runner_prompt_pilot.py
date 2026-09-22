"""Persistent four-GPU runner for the prompt-pilot baseline.

Each worker binds one physical GPU, loads the pinned model once, and receives
jobs dynamically from the parent.  There is no warm-up generation or retry.
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

from irisx import arc_prompt_pilot as core
from irisx.canonical import canonical_bytes, digest_value, read_json
from irisx.errors import ValidationError


RAW_COMPLETION_LIMIT_BYTES = 16_384


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def canonical_ready_evidence(ready: Mapping[int, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Convert internal integer worker ranks to canonical JSON object keys."""

    return {str(rank): dict(ready[rank]) for rank in sorted(ready)}


def _load_base_model(model_root: str) -> tuple[Any, Any, dict[str, Any]]:
    import torch
    from transformers import AutoModelForMultimodalLM, AutoTokenizer

    started = time.monotonic()
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
    return model, tokenizer, {"load_seconds": time.monotonic() - started}


def _cap(text: str) -> tuple[str, int, bool]:
    encoded = text.encode("utf-8")
    if len(encoded) <= RAW_COMPLETION_LIMIT_BYTES:
        return text, len(encoded), False
    return encoded[:RAW_COMPLETION_LIMIT_BYTES].decode("utf-8", errors="ignore"), len(encoded), True


def _generate_once(model: Any, tokenizer: Any, case: Mapping[str, Any], settings: Mapping[str, Any]) -> tuple[list[list[list[int]]], dict[str, Any]]:
    import torch

    if settings != core._configuration()["generation"]:
        raise RuntimeError("generation settings differ from the frozen prompt-pilot baseline")
    messages = core.render_b1(case)
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    encoded = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
    input_tokens = int(encoded["attention_mask"].sum().item())
    started = time.monotonic()
    with torch.inference_mode():
        generated = model.generate(
            **encoded,
            max_new_tokens=512,
            num_beams=1,
            num_return_sequences=1,
            do_sample=False,
            return_dict_in_generate=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    seconds = time.monotonic() - started
    suffix = generated.sequences[0][int(encoded["input_ids"].shape[1]):]
    raw = tokenizer.decode(suffix, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    completion, raw_bytes, capped = _cap(raw)
    parsed = core.parse_grid_text(raw)
    attempts: list[list[list[int]]] = []
    if parsed is not None:
        try:
            attempts = [core.validate_grid(parsed, "single completion grid")]
        except ValidationError:
            attempts = []
    generated_tokens = int(suffix.numel())
    last = int(suffix[-1].item()) if generated_tokens else None
    if last is not None and tokenizer.eos_token_id is not None and last == int(tokenizer.eos_token_id):
        stop = "eos_token"
    elif generated_tokens >= 512:
        stop = "maximum_new_tokens"
    else:
        stop = "unknown"
    return attempts, {
        "input_tokens": input_tokens,
        "generated_tokens": generated_tokens,
        "generation_seconds": seconds,
        "tokens_per_second": generated_tokens / seconds if seconds else None,
        "raw_completion": completion,
        "raw_completion_bytes": raw_bytes,
        "raw_completion_truncated": capped,
        "parse_state": "valid_grid" if attempts else "invalid_grid",
        "stop_reason": stop,
    }


def _record(case: Mapping[str, Any], rank: int, gpu_uuid: str, ordinal: int | None, status: str, *, attempts: list[list[list[int]]] | None = None, metrics: Mapping[str, Any] | None = None, failure: str | None = None, started_utc: str | None = None, ended_utc: str | None = None, peak_mib: int | None = None) -> dict[str, Any]:
    metrics = dict(metrics or {})
    attempts = attempts or []
    return {
        "job_key": f"{case['task_id']}:0", "task_id": case["task_id"], "group": case["group"], "test_index": 0,
        "worker_rank": rank, "gpu_uuid": gpu_uuid, "invocation_ordinal": ordinal,
        "started_utc": started_utc, "ended_utc": ended_utc, "status": status,
        "attempts": attempts, "valid_model_output": bool(attempts), "failure": failure,
        "timing": {"generation_seconds": metrics.get("generation_seconds")},
        "tokens": {"input": metrics.get("input_tokens"), "generated": metrics.get("generated_tokens"), "tokens_per_second": metrics.get("tokens_per_second")},
        "generation": {"raw_completion": metrics.get("raw_completion"), "raw_completion_bytes": metrics.get("raw_completion_bytes"), "raw_completion_truncated": metrics.get("raw_completion_truncated", False), "parse_state": metrics.get("parse_state", "not_available"), "stop_reason": metrics.get("stop_reason", "not_available")},
        "gpu_peak_memory_mib": peak_mib,
    }


def _worker(rank: int, model_root: str, configuration: Mapping[str, Any], command_queue: Any, output_queue: Any, model_manifest_digest: str) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(rank)
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    try:
        import torch

        torch.cuda.set_device(0)
        torch.manual_seed(int(configuration["generation"]["seed"]) + rank)
        props = torch.cuda.get_device_properties(0)
        gpu_uuid = str(getattr(props, "uuid", "unknown"))
        output_queue.put({"type": "stage", "event": "model_load_started", "rank": rank, "gpu_uuid": gpu_uuid, "at_utc": _utc()})
        model, tokenizer, load = _load_base_model(model_root)
        output_queue.put({
            "type": "ready", "event": "model_ready", "rank": rank, "gpu_uuid": gpu_uuid,
            "gpu_name": props.name, "model_repository": core.MODEL_REPOSITORY,
            "model_revision": core.MODEL_REVISION, "model_manifest_digest": model_manifest_digest,
            "load_seconds": load["load_seconds"], "at_utc": _utc(),
        })
        while True:
            command = command_queue.get()
            if command.get("type") == "stop":
                break
            case = command["case"]
            ordinal = int(command["ordinal"])
            job_key = f"{case['task_id']}:0"
            started_utc = _utc()
            output_queue.put({"type": "stage", "event": "job_started", "rank": rank, "gpu_uuid": gpu_uuid, "job_key": job_key, "invocation_ordinal": ordinal, "at_utc": started_utc})
            try:
                torch.cuda.reset_peak_memory_stats()
                attempts, metrics = _generate_once(model, tokenizer, case, configuration["generation"])
                peak = int(torch.cuda.max_memory_allocated() // (1024 * 1024))
                status = "valid" if attempts else "invalid"
                output_queue.put({"type": "record", "rank": rank, "record": _record(case, rank, gpu_uuid, ordinal, status, attempts=attempts, metrics=metrics, failure=None if attempts else "single completion was not a parseable valid grid", started_utc=started_utc, ended_utc=_utc(), peak_mib=peak)})
            except Exception as exc:
                status = "oom" if "out of memory" in str(exc).lower() else "worker_crash"
                output_queue.put({"type": "failure", "rank": rank, "job_key": job_key, "invocation_ordinal": ordinal, "status": status, "detail": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(limit=20), "at_utc": _utc()})
                break
    except Exception as exc:
        output_queue.put({"type": "failure", "rank": rank, "job_key": None, "invocation_ordinal": None, "status": "worker_crash", "detail": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(limit=20), "at_utc": _utc()})


def collect_runtime_hardware() -> dict[str, Any]:
    import torch

    gpus = []
    for index in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(index)
        gpus.append({"index": index, "name": props.name, "memory_mib": int(props.total_memory // (1024 * 1024)), "uuid": str(getattr(props, "uuid", "unknown")), "capability": f"{props.major}.{props.minor}"})
    completed = subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total,uuid,pci.bus_id", "--format=csv,noheader,nounits"], capture_output=True, text=True, check=False, timeout=30)
    return {"torch_cuda_device_count": torch.cuda.device_count(), "gpus": gpus, "nvidia_smi_exit_code": completed.returncode, "nvidia_smi_rows": [line.strip() for line in completed.stdout.splitlines() if line.strip()], "python": sys.version.split()[0], "torch": torch.__version__, "cuda": torch.version.cuda, "cudnn": str(torch.backends.cudnn.version())}


def validate_runtime_hardware(hardware: Mapping[str, Any]) -> None:
    gpus = hardware.get("gpus")
    if hardware.get("torch_cuda_device_count") != 4 or not isinstance(gpus, list) or len(gpus) != 4:
        raise RuntimeError(f"prompt pilot requires exactly four GPUs; observed {hardware.get('torch_cuda_device_count')}")
    if any("L4" not in gpu["name"] or gpu["memory_mib"] < 22000 for gpu in gpus):
        raise RuntimeError(f"prompt pilot requires four L4 GPUs with at least 22000 MiB each; observed {gpus}")
    if len({gpu["uuid"] for gpu in gpus}) != 4:
        raise RuntimeError("PyTorch did not expose four distinct GPU UUIDs")
    if hardware.get("nvidia_smi_exit_code") != 0 or len(hardware.get("nvidia_smi_rows", [])) != 4:
        raise RuntimeError("nvidia-smi did not independently report exactly four GPUs")


def _progress(path: Path, event: Mapping[str, Any]) -> None:
    payload = canonical_bytes(dict(event), newline=True)
    with path.open("ab") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    print(payload.decode().rstrip(), flush=True)


def _stop_processes(processes: Mapping[int, Any], queues: Mapping[int, Any]) -> None:
    for rank, command_queue in queues.items():
        if processes[rank].is_alive():
            command_queue.put({"type": "stop"})
    for process in processes.values():
        process.join(timeout=10)
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)


def run(outbound: Path, model_root: Path, competition_challenges: Path, output: Path, checkpoint_output: Path, progress_output: Path, resume_checkpoint: Path | None = None) -> str:
    session_started = time.monotonic()
    manifest, contents, _ = core.verify_outbound_package(outbound)
    run_binding = json.loads(contents["bindings/run.json"])
    solver = json.loads(contents["cases/solver-cases.json"])
    model_manifest = json.loads(contents["sources/model-manifest.json"])
    progress_output.parent.mkdir(parents=True, exist_ok=True)
    progress_output.write_bytes(b"")
    _progress(progress_output, {"event": "runtime_preflight_started", "run_id": core.RUN_ID, "at_utc": _utc(), "elapsed_seconds": 0.0})
    hardware = collect_runtime_hardware()
    _progress(progress_output, {"event": "runtime_hardware_observed", "run_id": core.RUN_ID, "at_utc": _utc(), "elapsed_seconds": time.monotonic() - session_started, "hardware": hardware})
    validate_runtime_hardware(hardware)
    competition = core.validate_competition_mount(competition_challenges, run_binding, solver)
    _progress(progress_output, {"event": "competition_mount_validated", "run_id": core.RUN_ID, "at_utc": _utc(), "elapsed_seconds": time.monotonic() - session_started, **competition})
    core.validate_material_manifest(model_root, model_manifest)

    if resume_checkpoint is None:
        checkpoint = core.new_checkpoint(run_binding, solver)
    else:
        checkpoint = read_json(resume_checkpoint)
        core.validate_checkpoint(checkpoint, run_binding, solver)
        if checkpoint["complete"]:
            raise ValidationError("refusing to resume a complete prompt-pilot checkpoint")
    session_index = len(checkpoint["sessions"])
    checkpoint["sessions"].append({"session_index": session_index, "started_utc": _utc(), "hardware": hardware, "ended_utc": None, "wall_seconds": None})
    core.atomically_write_json(checkpoint_output, checkpoint)

    context = multiprocessing.get_context("spawn")
    output_queue = context.Queue()
    command_queues: dict[int, Any] = {}
    processes: dict[int, Any] = {}
    for rank in range(core.WORKER_COUNT):
        command_queues[rank] = context.Queue()
        processes[rank] = context.Process(target=_worker, args=(rank, str(model_root), run_binding["configuration"], command_queues[rank], output_queue, model_manifest["manifest_digest"]), name=f"prompt-pilot-worker-{rank}")
        processes[rank].start()
        _progress(progress_output, {"event": "worker_process_started", "rank": rank, "pid": processes[rank].pid, "at_utc": _utc(), "elapsed_seconds": time.monotonic() - session_started})

    ready: dict[int, dict[str, Any]] = {}
    ready_deadline = time.monotonic() + 1800
    while len(ready) < core.WORKER_COUNT:
        if time.monotonic() >= ready_deadline:
            _stop_processes(processes, command_queues)
            raise TimeoutError("not all four workers reported model_ready within 1800 seconds")
        try:
            message = output_queue.get(timeout=5)
        except queue.Empty:
            continue
        safe = {key: value for key, value in message.items() if key not in {"type", "traceback"}}
        _progress(progress_output, {**safe, "elapsed_seconds": time.monotonic() - session_started})
        if message["type"] == "ready":
            rank = int(message["rank"])
            if rank in ready or message["model_revision"] != core.MODEL_REVISION or message["model_manifest_digest"] != model_manifest["manifest_digest"]:
                _stop_processes(processes, command_queues)
                raise RuntimeError("duplicate or incorrectly bound model_ready event")
            ready[rank] = safe
            checkpoint["model_ready"][str(rank)] = safe
            core.atomically_write_json(checkpoint_output, checkpoint)
        elif message["type"] == "failure":
            _stop_processes(processes, command_queues)
            raise RuntimeError(f"worker {message['rank']} failed before four-worker readiness: {message['detail']}")
    if len({event["gpu_uuid"] for event in ready.values()}) != 4:
        _stop_processes(processes, command_queues)
        raise RuntimeError("four model_ready events do not name four distinct GPU UUIDs")
    _progress(progress_output, {"event": "all_workers_ready", "run_id": core.RUN_ID, "ready_ranks": sorted(ready), "model_revision": core.MODEL_REVISION, "at_utc": _utc(), "elapsed_seconds": time.monotonic() - session_started})

    cases = {f"{case['task_id']}:0": case for case in solver["cases"]}
    consumed = set(checkpoint["generation_invocations"])
    pending = [job for job in checkpoint["expected_jobs"] if job not in checkpoint["completed"] and job not in consumed]
    dispatch = core.DispatchState.from_jobs(pending)
    global_stop = session_started + core.SESSION_BUDGET_SECONDS - core.FINALIZATION_RESERVE_SECONDS
    next_ordinal = len(checkpoint["generation_invocations"]) + 1

    def assign(rank: int) -> None:
        nonlocal next_ordinal
        now = time.monotonic()
        if now >= global_stop:
            return
        job = dispatch.dispatch(rank, min(global_stop, now + core.TASK_DEADLINE_SECONDS))
        if job is None:
            return
        ordinal = next_ordinal
        next_ordinal += 1
        checkpoint["generation_invocations"][job] = {"ordinal": ordinal, "worker_rank": rank, "status": "started", "started_utc": _utc(), "ended_utc": None}
        core.atomically_write_json(checkpoint_output, checkpoint)
        command_queues[rank].put({"type": "job", "case": cases[job], "ordinal": ordinal})
        _progress(progress_output, {"event": "generation_invocation_dispatched", "rank": rank, "gpu_uuid": ready[rank]["gpu_uuid"], "job_key": job, "invocation_ordinal": ordinal, "at_utc": _utc(), "elapsed_seconds": now - session_started})

    for rank in range(core.WORKER_COUNT):
        assign(rank)

    abort: tuple[str, str] | None = None
    last_heartbeat = 0.0
    while dispatch.active:
        now = time.monotonic()
        expired = dispatch.expired(now)
        if expired:
            for rank, job in expired:
                checkpoint["generation_invocations"][job].update({"status": "timeout", "ended_utc": _utc()})
                checkpoint["completed"][job] = _record(cases[job], rank, ready[rank]["gpu_uuid"], checkpoint["generation_invocations"][job]["ordinal"], "timeout", failure="300-second parent-enforced job deadline reached", started_utc=checkpoint["generation_invocations"][job]["started_utc"], ended_utc=_utc())
                dispatch.finish(rank, job, "timeout")
            abort = ("timeout", "a persistent worker exceeded the 300-second per-job deadline")
            break
        if now >= global_stop:
            abort = ("not_executed", "session finalization boundary reached")
            break
        if now - session_started - last_heartbeat >= 60:
            _progress(progress_output, {"event": "heartbeat", "completed_jobs": len(checkpoint["completed"]), "active_jobs": len(dispatch.active), "pending_jobs": len(dispatch.pending), "at_utc": _utc(), "elapsed_seconds": now - session_started})
            last_heartbeat = now - session_started
        timeout = min(5.0, max(0.1, min(deadline for _, deadline in dispatch.active.values()) - now))
        try:
            message = output_queue.get(timeout=timeout)
        except queue.Empty:
            continue
        safe = {key: value for key, value in message.items() if key not in {"type", "traceback"}}
        if message["type"] == "stage":
            _progress(progress_output, {**safe, "elapsed_seconds": time.monotonic() - session_started})
            continue
        rank = int(message["rank"])
        if message["type"] == "record":
            record = message["record"]
            job = record["job_key"]
            dispatch.finish(rank, job, record["status"])
            checkpoint["generation_invocations"][job].update({"status": "completed", "ended_utc": record["ended_utc"]})
            checkpoint["completed"][job] = record
            core.atomically_write_json(checkpoint_output, checkpoint)
            _progress(progress_output, {"event": "job_terminal", "rank": rank, "gpu_uuid": record["gpu_uuid"], "job_key": job, "invocation_ordinal": record["invocation_ordinal"], "status": record["status"], "at_utc": record["ended_utc"], "elapsed_seconds": time.monotonic() - session_started})
            assign(rank)
        elif message["type"] == "failure":
            job = message.get("job_key")
            if isinstance(job, str) and rank in dispatch.active:
                dispatch.finish(rank, job, message["status"])
                checkpoint["generation_invocations"][job].update({"status": "failed", "ended_utc": message["at_utc"]})
                checkpoint["completed"][job] = _record(cases[job], rank, ready[rank]["gpu_uuid"], message["invocation_ordinal"], message["status"], failure=message["detail"], started_utc=checkpoint["generation_invocations"][job]["started_utc"], ended_utc=message["at_utc"])
            _progress(progress_output, {**safe, "elapsed_seconds": time.monotonic() - session_started})
            abort = ("worker_crash", f"worker {rank} failed; no replacement model load is permitted")
            break

    _stop_processes(processes, command_queues)
    if abort is not None:
        status, detail = abort
        for rank, (job, _) in list(dispatch.active.items()):
            if job not in checkpoint["completed"]:
                checkpoint["generation_invocations"][job].update({"status": "failed", "ended_utc": _utc()})
                checkpoint["completed"][job] = _record(cases[job], rank, ready[rank]["gpu_uuid"], checkpoint["generation_invocations"][job]["ordinal"], status, failure=detail, started_utc=checkpoint["generation_invocations"][job]["started_utc"], ended_utc=_utc())
        for job in list(dispatch.pending):
            checkpoint["completed"][job] = _record(cases[job], -1, "not_assigned", None, "not_executed", failure=detail)
    checkpoint["complete"] = len(checkpoint["completed"]) == len(checkpoint["expected_jobs"])
    wall = time.monotonic() - session_started
    checkpoint["sessions"][session_index].update({"ended_utc": _utc(), "wall_seconds": wall})
    core.validate_checkpoint(checkpoint, run_binding, solver)
    core.atomically_write_json(checkpoint_output, checkpoint)
    import transformers
    statuses = Counter(record["status"] for record in checkpoint["completed"].values())
    worker_counts = Counter(str(record["worker_rank"]) for record in checkpoint["completed"].values() if record["worker_rank"] >= 0)
    active_seconds = Counter()
    for record in checkpoint["completed"].values():
        value = record.get("timing", {}).get("generation_seconds")
        if isinstance(value, (int, float)) and record["worker_rank"] >= 0:
            active_seconds[str(record["worker_rank"])] += value
    observations = {"format": "irisx/arc-agi-2-prompt-pilot-execution", "format_version": "1.0", "trial_id": core.TRIAL_ID, "run_id": core.RUN_ID, "session_wall_seconds": wall, "hardware": hardware["gpus"], "nvidia_smi_rows": hardware["nvidia_smi_rows"], "software": {"python": hardware["python"], "torch": hardware["torch"], "transformers": transformers.__version__, "cuda": hardware["cuda"], "cudnn": hardware["cudnn"]}, "competition_input": competition, "internet_enabled": False, "external_paid_cost_usd": 0, "model_ready": canonical_ready_evidence(ready), "model_load_count_by_worker": {str(rank): 1 for rank in ready}, "jobs_by_worker": dict(sorted(worker_counts.items())), "job_active_seconds_by_worker": dict(sorted(active_seconds.items())), "terminal_status_counts": dict(sorted(statuses.items())), "generation_invocation_count": len(checkpoint["generation_invocations"]), "gpu_utilization_state": "not_sampled"}
    _progress(progress_output, {"event": "session_complete", "completed_jobs": len(checkpoint["completed"]), "terminal_status_counts": dict(sorted(statuses.items())), "at_utc": _utc(), "elapsed_seconds": wall})
    return core.build_result_package(output, run_binding, solver, checkpoint, observations, progress_output.read_bytes())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the 384-job IRIS-X ARC prompt-pilot baseline")
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
        failure = args.progress_output.with_name("runtime-failure.json")
        failure.write_bytes(canonical_bytes({"run_id": core.RUN_ID, "status": "failed", "at_utc": _utc(), "detail": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(limit=40)}, newline=True))
        print(failure.read_text(), flush=True)
        return 1
    print(json.dumps({"event": "result_written", "run_id": core.RUN_ID, "result_digest": digest}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
