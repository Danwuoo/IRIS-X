"""Repackage a complete Decision 0020 checkpoint after finalization failure.

No generation or network call occurs. The only input is the single retained
terminal retrieval for an already launched kernel.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from irisx import arc_budget_ablation as budget
from irisx.canonical import canonical_bytes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", choices=["diagnostic", "validation"])
    args = parser.parse_args()
    root = Path(".irisx/arc-agi-2/budget-ablation") / args.run
    run_id = budget.DIAGNOSTIC_RUN if args.run == "diagnostic" else budget.VALIDATION_RUN
    retrieved = root / "retrieved"
    checkpoints = list(retrieved.rglob("checkpoint.json"))
    progresses = list(retrieved.rglob("progress.jsonl"))
    if len(checkpoints) != 1 or len(progresses) != 1 or list(retrieved.rglob("result.zip")):
        raise RuntimeError("recovery requires one checkpoint and progress stream and no existing result.zip")
    outbound = root / "outbound" / f"{run_id}.zip"
    _, contents, _ = budget.verify_outbound(outbound)
    run = json.loads(contents["bindings/run.json"])
    workload = json.loads(contents["cases/jobs.json"])
    checkpoint_path, progress_path = checkpoints[0], progresses[0]
    checkpoint = json.loads(checkpoint_path.read_bytes())
    if checkpoint_path.read_bytes() != canonical_bytes(checkpoint, newline=True):
        raise RuntimeError("checkpoint is not canonical")
    budget.validate_checkpoint(checkpoint, run, workload)
    if not checkpoint.get("complete") or len(checkpoint["completed"]) != len(checkpoint["expected_jobs"]):
        raise RuntimeError("checkpoint is incomplete; no regeneration authorized")
    ready = checkpoint["model_ready"]
    if set(ready) != {"0", "1", "2", "3"} or len({item["gpu_uuid"] for item in ready.values()}) != 4:
        raise RuntimeError("checkpoint lacks four distinct model-ready workers")
    progress = progress_path.read_bytes()
    events = [json.loads(line) for line in progress.splitlines() if line]
    if progress != b"".join(canonical_bytes(event, newline=True) for event in events):
        raise RuntimeError("progress stream is not canonical")
    if {event.get("rank") for event in events if event.get("event") == "generation_invocation_dispatched"} != {0, 1, 2, 3}:
        raise RuntimeError("progress lacks initial four-rank dispatch")
    competition = next((event for event in events if event.get("event") == "competition_mount_validated"), None)
    if competition is None or competition.get("challenge_digest") != run["source"]["competition_challenge_digest"]:
        raise RuntimeError("progress lacks bound competition validation")
    session = checkpoint["sessions"][-1]
    hardware = session["hardware"]
    status = Counter(record["status"] for record in checkpoint["completed"].values())
    jobs_by_worker = Counter(str(record["worker_rank"]) for record in checkpoint["completed"].values() if record["worker_rank"] >= 0)
    active_seconds = Counter()
    for record in checkpoint["completed"].values():
        seconds = record.get("timing", {}).get("generation_seconds")
        if record["worker_rank"] >= 0 and isinstance(seconds, (int, float)):
            active_seconds[str(record["worker_rank"])] += seconds
    observations = {"format": "irisx/arc-budget-execution", "format_version": "1.0", "trial_id": budget.TRIAL_ID,
                    "run_id": run_id, "session_wall_seconds": session["wall_seconds"], "hardware": hardware["gpus"],
                    "nvidia_smi_rows": hardware["nvidia_smi_rows"],
                    "software": {"python": hardware["python"], "torch": hardware["torch"],
                                 "transformers": None, "cuda": hardware["cuda"], "cudnn": hardware["cudnn"]},
                    "competition_input": {key: competition[key] for key in ("challenge_digest", "available_task_count", "selected_job_count", "selected_test_index", "solutions_opened")},
                    "internet_enabled": False, "external_paid_cost_usd": 0, "model_ready": ready,
                    "model_load_count_by_worker": {key: 1 for key in ready},
                    "jobs_by_worker": dict(jobs_by_worker), "job_active_seconds_by_worker": dict(active_seconds),
                    "terminal_status_counts": dict(status), "generation_invocation_count": len(checkpoint["generation_invocations"]),
                    "gpu_utilization_state": "not_sampled", "recovered_from_complete_checkpoint": True}
    output = retrieved / "recovered" / "result.zip"
    output.parent.mkdir(exist_ok=False)
    digest = budget.build_result_package(output, run, workload, checkpoint, observations, progress)
    budget.verify_result_package(output, outbound)
    print(json.dumps({"event": "complete_checkpoint_repackaged", "result_digest": digest,
                      "new_generations": 0, "result_path": str(output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
