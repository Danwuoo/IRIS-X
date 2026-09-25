"""Verify a retrieved, truth-free four-L4 NVARC M2 feasibility observation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from irisx.canonical import canonical_bytes, digest_value, read_json
from irisx.errors import ValidationError
from tools.preflight_nvarc_m2_m3 import preflight


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_pair(value: object) -> bool:
    return (isinstance(value, list) and len(value) == 2 and
            all(type(part) in (int, float) and math.isfinite(part) for part in value))


def verify_observation(plan: dict, result: dict, terminal: dict,
                       hardware: dict, traces: dict[int, list[dict]]) -> dict:
    allowed_result_keys = {"claim", "compact_material_digest", "contains_evaluator_truth",
                           "format", "optimizer_steps", "plan_digest", "ranks",
                           "sequences_digest", "total_input_tokens", "wall_seconds"}
    allowed_rank_keys = {"device_uuid", "input_tokens", "local_rank", "loss", "name",
                         "nonzero_gradient_tensors", "peak_cuda_allocated_mib", "rank",
                         "step_wall_seconds", "total_memory_bytes",
                         "weight_fingerprint_after", "weight_fingerprint_before"}
    if (plan.get("run_id") != "nvarc-m2-fsdp-feasibility-003" or
            plan.get("approved") is not True or plan.get("maximum_optimizer_steps") != 1 or
            plan.get("maximum_total_input_tokens") != 512 or
            plan.get("maximum_paid_usd") != 0):
        raise ValidationError("approved 003 plan or ceilings differ")
    if (terminal.get("return_code") != 0 or
            terminal.get("wall_seconds", math.inf) > plan["maximum_kernel_wall_seconds"] or
            terminal.get("wall_seconds", 0) <= 0):
        raise ValidationError("FSDP terminal success or wall bound differs")
    rows = hardware.get("nvidia_smi_rows")
    gpus = hardware.get("gpus")
    if (hardware.get("bf16") is not True or not isinstance(rows, list) or
            not isinstance(gpus, list) or len(rows) != 4 or len(gpus) != 4 or
            len({row[3] for row in rows if len(row) == 4}) != 4):
        raise ValidationError("four distinct BF16 L4s not observed")
    for rank, (row, gpu) in enumerate(zip(rows, gpus)):
        if (len(row) != 4 or row[0] != str(rank) or "L4" not in row[1] or
                "L4" not in gpu.get("name", "") or gpu.get("index") != rank or
                gpu.get("memory_bytes", 0) < 22 * 10**9):
            raise ValidationError("FSDP L4 rank hardware differs")
    if (set(result) != allowed_result_keys or
            result.get("format") != "irisx/nvarc-m2-fsdp-feasibility-result-v1" or
            result.get("contains_evaluator_truth") is not False or
            result.get("optimizer_steps") != 1 or
            result.get("compact_material_digest") != plan["compact_material_digest"] or
            result.get("sequences_digest") != plan["sequences_digest"] or
            result.get("plan_digest") != digest_value(plan) or
            result.get("claim") !=
            "FSDP one-step compatibility only; no exported ARC-SFT checkpoint"):
        raise ValidationError("FSDP result identity or truth boundary differs")
    ranks = result.get("ranks")
    if not isinstance(ranks, list) or len(ranks) != 4:
        raise ValidationError("four result ranks required")
    before = ranks[0].get("weight_fingerprint_before")
    after = ranks[0].get("weight_fingerprint_after")
    if not _finite_pair(before) or not _finite_pair(after) or before == after:
        raise ValidationError("finite changed weight fingerprints required")
    tokens = 0
    required_phases = ["input_verified", "hardware_gate_complete", "compact_gate_complete",
                       "model_loaded", "fsdp_wrapped", "fingerprint_before_complete",
                       "forward_start", "forward_complete", "backward_start",
                       "backward_complete", "gradient_check_complete", "clip_complete",
                       "optimizer_complete", "weight_check_complete",
                       "fingerprint_after_complete", "result_gather_complete", "completed"]
    for rank, item in enumerate(ranks):
        if (set(item) != allowed_rank_keys or
                item.get("rank") != rank or item.get("local_rank") != rank or
                item.get("device_uuid") != rows[rank][3] or
                item.get("name") != gpus[rank]["name"] or
                item.get("total_memory_bytes") != gpus[rank]["memory_bytes"] or
                item.get("weight_fingerprint_before") != before or
                item.get("weight_fingerprint_after") != after or
                not isinstance(item.get("nonzero_gradient_tensors"), int) or
                item["nonzero_gradient_tensors"] <= 0):
            raise ValidationError(f"FSDP rank {rank} result identity or update differs")
        count = item.get("input_tokens")
        if not isinstance(count, int) or not 0 < count <= plan["maximum_tokens_per_rank"]:
            raise ValidationError(f"FSDP rank {rank} token ceiling differs")
        tokens += count
        for field in ("loss", "step_wall_seconds", "peak_cuda_allocated_mib"):
            value = item.get(field)
            if (type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
                raise ValidationError(f"FSDP rank {rank} {field} is invalid")
        if item["peak_cuda_allocated_mib"] * 1048576 > item["total_memory_bytes"]:
            raise ValidationError(f"FSDP rank {rank} peak memory exceeds GPU")
        events = traces.get(rank)
        phases = [event.get("phase") for event in events] if isinstance(events, list) else []
        positions = [phases.index(phase) if phase in phases else -1 for phase in required_phases]
        if (positions != sorted(positions) or -1 in positions or
                "exception" in phases or phases[-1] != "completed" or
                any(event.get("rank") != rank for event in events) or
                next(event for event in events if event["phase"] == "forward_start")
                .get("input_tokens") != count):
            raise ValidationError(f"FSDP rank {rank} trace is incomplete")
    if (tokens != result.get("total_input_tokens") or
            tokens > plan["maximum_total_input_tokens"] or
            result.get("wall_seconds", 0) <= 0 or
            result["wall_seconds"] > terminal["wall_seconds"]):
        raise ValidationError("FSDP aggregate tokens or wall differs")
    return {"optimizer_steps": 1, "total_input_tokens": tokens, "rank_count": 4,
            "distinct_l4_uuids": 4,
            "maximum_peak_cuda_allocated_mib": max(
                item["peak_cuda_allocated_mib"] for item in ranks),
            "kernel_wall_seconds": terminal["wall_seconds"],
            "step_wall_seconds": max(item["step_wall_seconds"] for item in ranks)}


def verify(package: Path, retrieved: Path) -> dict:
    preflight(package, approved=True)
    summary = read_json(package / "stage-summary.json")
    plan_path = retrieved / "plan.json"
    plan = read_json(plan_path)
    result_path = retrieved / plan["run_id"] / "result.json"
    result_bytes = result_path.read_bytes()
    result = read_json(result_path)
    terminal = read_json(retrieved / "m2-fsdp-terminal.json")
    hardware = read_json(retrieved / "m2-fsdp-hardware-preflight.json")
    mounts = read_json(retrieved / "m2-fsdp-mount-preflight.json")
    if (summary["run_id"] != plan["run_id"] or
            _sha(plan_path) != summary["plan_sha256"] or
            terminal.get("plan_sha256") != summary["plan_sha256"] or
            terminal.get("runtime_wheel_sha256") != summary["runtime_wheel_sha256"] or
            _sha(retrieved / "irisx-0.2.0-py3-none-any.whl") !=
            summary["runtime_wheel_sha256"] or
            _sha(retrieved / "sequences.json") != summary["sequences_sha256"] or
            result_bytes != canonical_bytes(result, newline=True)):
        raise ValidationError("retrieved FSDP package or canonical result differs")
    sequences = [json.loads(line) for line in
                 (retrieved / "sequences.json").read_text(encoding="utf-8").splitlines()]
    if len(sequences) != 128 or digest_value(sequences) != plan["sequences_digest"]:
        raise ValidationError("retrieved public ARC sequences differ")
    if (len(mounts.get("model_mounts", [])) != 1 or
            len(mounts.get("wheel_mounts", [])) != 1 or
            Path(mounts["model_mounts"][0]).name != "irisx-nvarc-m2-compact-4b-001" or
            Path(mounts["wheel_mounts"][0]).name !=
            "irisx-arc-agi-2-trial-002-smoke-001"):
        raise ValidationError("FSDP private model or wheel mount differs")
    traces = {}
    for rank in range(4):
        path = retrieved / (plan["run_id"] + "-diagnostics") / f"rank-{rank}.jsonl"
        traces[rank] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    observed = verify_observation(plan, result, terminal, hardware, traces)
    return {"format": "irisx/nvarc-m2-fsdp-verified-v1", "run_id": plan["run_id"],
            "plan_sha256": summary["plan_sha256"],
            "result_sha256": _sha(result_path),
            "terminal_sha256": _sha(retrieved / "m2-fsdp-terminal.json"),
            "log_sha256": _sha(retrieved / (plan["run_id"] + ".log")),
            "compact_material_digest": plan["compact_material_digest"],
            "sequences_digest": plan["sequences_digest"],
            "contains_evaluator_truth": False, **observed,
            "claim": "one full-parameter 4B optimizer step only; no exported SFT checkpoint"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("retrieved", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise ValidationError("new verification report path required")
    report = verify(args.package, args.retrieved)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_bytes(canonical_bytes(report, newline=True))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
