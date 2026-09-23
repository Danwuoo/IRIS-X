"""Private, Internet-disabled four-L4 NVARC inference runner.

Importing this module has no provider side effect. The deliberate run entry
requires a separate owner-approved manifest checked by the CLI.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
from pathlib import Path
import queue
import time
from typing import Any, Mapping

from .arc_nvarc_candidates import QwenCandidateBackend, solve_task
from .arc_nvarc_data import compare_visible, visible_task
from .arc_nvarc_representation import verify_model_material
from .arc_nvarc_runtime import (atomic_json, build_result, finalize_interrupted,
                                finish_task, new_checkpoint, reserve_task,
                                validate_checkpoint, verify_outbound)
from .arc_nvarc_training import TaskLocalAdapter, load_compact_model
from .errors import ValidationError
from .transport import digest_path


def validate_hardware() -> dict[str, Any]:
    from .kaggle_runner_budget_ablation import collect_runtime_hardware

    hardware = collect_runtime_hardware()
    gpus = hardware["gpus"]
    if (hardware["torch_cuda_device_count"] != 4 or len(gpus) != 4 or
            any("L4" not in gpu["name"] or gpu["memory_mib"] < 22000 for gpu in gpus) or
            len({gpu["uuid"] for gpu in gpus}) != 4 or
            hardware["nvidia_smi_exit_code"] != 0 or len(hardware["nvidia_smi_rows"]) != 4):
        raise ValidationError("NVARC runner requires four distinct L4 GPUs")
    return hardware


def validate_competition_mount(path: Path, binding: Mapping[str, Any],
                               workload: Mapping[str, Any]) -> None:
    if path.name != "arc-agi_training_challenges.json" or digest_path(path) != binding["source_digest"]:
        raise ValidationError("exact official ARC-AGI-2 challenge mount differs")
    mounted = json.loads(path.read_bytes())
    for case in workload["cases"]:
        task_id = case["task_id"]
        if task_id not in mounted or not compare_visible(case, visible_task(task_id, mounted[task_id])):
            raise ValidationError(f"full-task source differs: {task_id}")


def _worker(rank: int, command_queue: Any, output_queue: Any, model_root: str,
            config: Mapping[str, Any], gpu_uuid: str) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(rank)
    try:
        import torch

        load_started = time.monotonic()
        model = load_compact_model(Path(model_root))
        model.cuda().eval()
        adapter = TaskLocalAdapter(model, config["ttt"]) if config.get("ttt", {}).get("enabled") else None
        backend = QwenCandidateBackend(model, task_adapter=adapter)
        output_queue.put({"type": "ready", "rank": rank, "gpu_uuid": gpu_uuid,
                          "model_load_seconds": time.monotonic() - load_started})
        while True:
            command = command_queue.get()
            if command["type"] == "stop":
                return
            task = command["task"]
            started = time.monotonic()
            try:
                tests = solve_task(task, backend, config)
                output_queue.put({"type": "record", "rank": rank, "task_id": task["task_id"],
                                  "record": {"task_id": task["task_id"], "tests": tests,
                                             "status": "complete" if all(test["status"] == "complete" for test in tests) else "missing-candidate",
                                             "timing": {"load_seconds": None, "ttt_seconds": backend.ttt_seconds,
                                                        "generate_seconds": backend.generate_seconds,
                                                        "rank_seconds": backend.rank_seconds,
                                                        "task_wall_seconds": time.monotonic() - started},
                                             "adaptation": adapter.last_observation if adapter is not None else {},
                                             "peak_memory_mib": int(torch.cuda.max_memory_allocated() / 1024**2)}})
            except Exception as exc:
                status = "oom" if "out of memory" in str(exc).lower() else "worker_crash"
                output_queue.put({"type": "failure", "rank": rank, "task_id": task["task_id"],
                                  "status": status, "detail": f"{type(exc).__name__}: {exc}"})
                return
    except Exception as exc:
        output_queue.put({"type": "failure", "rank": rank, "task_id": None,
                          "status": "worker_crash", "detail": f"{type(exc).__name__}: {exc}"})


def _stop(processes: Mapping[int, Any], commands: Mapping[int, Any]) -> None:
    for rank, process in processes.items():
        if process.is_alive():
            commands[rank].put({"type": "stop"})
    for process in processes.values():
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)


def enforce_deadline(process: Any, deadline: float, now: float) -> bool:
    """Parent forcibly stops a worker; a late generate return is never required."""
    if now < deadline:
        return False
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
    return True


def run(outbound: Path, model_root: Path, competition_source: Path,
        output: Path, checkpoint_path: Path, *, resume: bool = False,
        worker_target: Any = None) -> str:
    binding, workload, _ = verify_outbound(outbound)
    config = binding["config"]
    start = time.monotonic()
    hardware = validate_hardware()
    validate_competition_mount(competition_source, binding, workload)
    if not (model_root / "grid-vocab.json").is_file():
        raise ValidationError("compact SFT checkpoint missing")
    verify_model_material(model_root, binding["model_digest"])
    if resume:
        checkpoint = json.loads(checkpoint_path.read_bytes())
        validate_checkpoint(checkpoint, binding, workload)
        if checkpoint["complete"]:
            raise ValidationError("complete checkpoint cannot be resumed")
        # A provider interruption consumes every pending task's full reserved
        # call quota. It is never silently retried after a task-boundary resume.
        by_id = {case["task_id"]: case for case in workload["cases"]}
        for task_id in list(checkpoint["reserved"]):
            tests = [{"test_index": index, "attempts": [], "missing_attempts": 2,
                      "status": "interrupted_pending"} for index in range(len(by_id[task_id]["test"]))]
            finish_task(checkpoint, task_id, {"task_id": task_id, "tests": tests,
                                              "status": "interrupted_pending",
                                              "timing": {"load_seconds": None, "ttt_seconds": None,
                                                         "generate_seconds": None, "rank_seconds": None},
                                              "peak_memory_mib": None})
    else:
        if checkpoint_path.exists():
            raise ValidationError("existing checkpoint requires resume")
        checkpoint = new_checkpoint(binding, workload)
    prior_wall = 0.0
    for session in checkpoint["sessions"]:
        if session.get("wall_seconds") is not None:
            prior_wall += float(session["wall_seconds"])
        elif session.get("started_unix") is not None:
            # Includes provider downtime: conservative accounting cannot
            # create a fresh budget by restarting the kernel.
            prior_wall += max(0.0, time.time() - float(session["started_unix"]))
        else:
            prior_wall += float(config["session_budget_seconds"])
    remaining_wall = max(0.0, config["session_budget_seconds"] - prior_wall)
    if remaining_wall <= config["finalization_reserve_seconds"] or set(checkpoint["completed"]) == set(checkpoint["expected_tasks"]):
        finalize_interrupted(checkpoint, workload, reason="session_limit")
        atomic_json(checkpoint_path, checkpoint)
        return build_result(output, binding, workload, checkpoint,
                            {"format": "irisx/nvarc-execution", "run_id": binding["run_id"],
                             "session_wall_seconds": 0.0, "prior_wall_seconds_charged": prior_wall,
                             "model_loads_this_session": 0, "gpu_busy_time_seconds": None,
                             "internet_enabled": False, "external_paid_cost_usd": 0})
    session_index = len(checkpoint["sessions"])
    checkpoint["sessions"].append({"index": session_index, "wall_seconds": None,
                                   "started_unix": time.time(),
                                   "gpu_uuids": [gpu["uuid"] for gpu in hardware["gpus"]]})
    atomic_json(checkpoint_path, checkpoint)
    context = multiprocessing.get_context("spawn")
    outputs = context.Queue()
    commands: dict[int, Any] = {}
    processes: dict[int, Any] = {}
    target = worker_target or _worker
    for rank in range(4):
        commands[rank] = context.Queue()
        processes[rank] = context.Process(target=target, args=(rank, commands[rank], outputs,
            str(model_root), config, hardware["gpus"][rank]["uuid"]))
        processes[rank].start()
    ready: set[int] = set()
    failure_info: dict[str, str] | None = None
    try:
        while len(ready) < 4:
            if time.monotonic() - start > min(600, remaining_wall - config["finalization_reserve_seconds"]):
                raise ValidationError("four workers did not become model-ready within startup bound")
            try:
                event = outputs.get(timeout=1)
            except queue.Empty:
                if any(not process.is_alive() for process in processes.values()):
                    raise ValidationError("worker exited before four-model readiness")
                continue
            if event["type"] != "ready" or event["rank"] in ready:
                raise ValidationError("worker failed or duplicated model readiness")
            rank = event["rank"]
            if event["gpu_uuid"] != hardware["gpus"][rank]["uuid"]:
                raise ValidationError("model-ready GPU UUID differs")
            ready.add(rank)
            checkpoint["model_ready"][str(rank)] = {"gpu_uuid": event["gpu_uuid"],
                                                     "model_load_seconds": event["model_load_seconds"]}
            atomic_json(checkpoint_path, checkpoint)
        cases = {case["task_id"]: case for case in workload["cases"]}
        pending = [task_id for task_id in checkpoint["expected_tasks"] if task_id not in checkpoint["completed"]]
        active: dict[int, tuple[str, float]] = {}
        disabled: set[int] = set()
        global_stop = start + remaining_wall - config["finalization_reserve_seconds"]

        def assign(rank: int) -> None:
            if not pending or rank in disabled or time.monotonic() >= global_stop:
                return
            task_id = pending.pop(0)
            reserve_task(checkpoint, binding, task_id, rank=rank,
                         at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            atomic_json(checkpoint_path, checkpoint)
            active[rank] = (task_id, min(global_stop, time.monotonic() + config["task_deadline_seconds"]))
            commands[rank].put({"type": "task", "task": cases[task_id]})

        for rank in range(4):
            assign(rank)
        while active:
            now = time.monotonic()
            for rank, (task_id, deadline) in list(active.items()):
                if enforce_deadline(processes[rank], deadline, now) or not processes[rank].is_alive():
                    status = "timeout" if now >= deadline else "worker_crash"
                    tests = [{"test_index": index, "attempts": [], "missing_attempts": 2,
                              "status": status} for index in range(len(cases[task_id]["test"]))]
                    finish_task(checkpoint, task_id, {"task_id": task_id, "tests": tests,
                                                      "status": status,
                                                      "timing": {"load_seconds": None, "ttt_seconds": None,
                                                                 "generate_seconds": None, "rank_seconds": None},
                                                      "peak_memory_mib": None})
                    active.pop(rank)
                    disabled.add(rank)
                    atomic_json(checkpoint_path, checkpoint)
            if not active or now >= global_stop:
                break
            try:
                event = outputs.get(timeout=1)
            except queue.Empty:
                continue
            rank = event["rank"]
            if rank not in active or event.get("task_id") != active[rank][0]:
                continue  # Late result from a killed/terminal worker is ignored.
            task_id = active.pop(rank)[0]
            if event["type"] == "record":
                finish_task(checkpoint, task_id, event["record"])
                atomic_json(checkpoint_path, checkpoint)
                assign(rank)
            else:
                tests = [{"test_index": index, "attempts": [], "missing_attempts": 2,
                          "status": event["status"]} for index in range(len(cases[task_id]["test"]))]
                finish_task(checkpoint, task_id, {"task_id": task_id, "tests": tests,
                                                  "status": event["status"],
                                                  "timing": {"load_seconds": None, "ttt_seconds": None,
                                                             "generate_seconds": None, "rank_seconds": None},
                                                  "peak_memory_mib": None})
                disabled.add(rank)
                atomic_json(checkpoint_path, checkpoint)
        reason = "session_limit" if time.monotonic() >= global_stop else "not_executed"
        finalize_interrupted(checkpoint, workload, reason=reason)
    except Exception as exc:
        failure_info = {"status": "startup_or_supervisor_failure",
                        "detail": f"{type(exc).__name__}: {exc}"}
        finalize_interrupted(checkpoint, workload, reason="worker_crash")
    finally:
        _stop(processes, commands)
    wall = time.monotonic() - start
    checkpoint["sessions"][session_index]["wall_seconds"] = wall
    atomic_json(checkpoint_path, checkpoint)
    observations = {"format": "irisx/nvarc-execution", "run_id": binding["run_id"],
                    "hardware": hardware["gpus"], "model_ready": checkpoint["model_ready"],
                    "session_wall_seconds": wall, "internet_enabled": False,
                    "competition_source": "arc-prize-2026-arc-agi-2",
                    "failure": failure_info,
                    "gpu_busy_time_seconds": None, "external_paid_cost_usd": 0}
    return build_result(output, binding, workload, checkpoint, observations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NVARC four-L4 private runner")
    parser.add_argument("--outbound", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--competition-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    authorization = json.loads(args.authorization.read_bytes())
    binding, _, _ = verify_outbound(args.outbound)
    if (authorization.get("approved") is not True or
            authorization.get("run_identity_digest") != binding["identity_digest"] or
            authorization.get("owner_decision") in (None, "") or
            authorization.get("provider") != "Kaggle" or
            not authorization.get("permitted_data") or
            not authorization.get("retention") or
            authorization.get("maximum_paid_usd") is None or
            authorization.get("maximum_session_seconds") != binding["config"]["session_budget_seconds"] or
            authorization.get("maximum_generation_calls") !=
            binding["config"]["maximum_calls_per_task"] * binding.get("task_count", 0)):
        raise ValidationError("new owner authorization with exact nonempty limits is required")
    print(run(args.outbound, args.model_root, args.competition_source,
              args.output, args.checkpoint, resume=args.resume))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
