"""Audit the two consumed Decision 0031 Kaggle versions without scoring truth."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(sft_package: Path, sft_output: Path,
           teacher_package: Path, teacher_output: Path) -> dict:
    sft_plan = json.loads((sft_package / "plan.json").read_bytes())
    teacher_plan = json.loads((teacher_package / "plan.json").read_bytes())
    if (sft_plan.get("run_id") != "nvarc-m2-fsdp-sft-001" or
            sft_plan.get("approved") is not True or
            teacher_plan.get("run_id") != "nvarc-m3-teacher-small-002" or
            teacher_plan.get("approved") is not True or
            (teacher_output / "plan.json").read_bytes() !=
            (teacher_package / "plan.json").read_bytes()):
        raise ValidationError("Decision 0031 package or retrieved plan differs")
    hardware_path = sft_output / "m2-sft-hardware-preflight.json"
    hardware = json.loads(hardware_path.read_bytes())
    rows = hardware.get("nvidia_smi_rows", [])
    if (len(hardware.get("gpus", [])) != 4 or len(rows) != 4 or
            len({row[3] for row in rows if len(row) == 4}) != 4 or
            any("L4" not in item["name"] for item in hardware["gpus"]) or
            hardware.get("bf16") is not True or
            hardware["free_working_bytes"] >= sft_plan["minimum_free_working_bytes"]):
        raise ValidationError("M2 hardware/disk gate observation differs")
    sft_log_path = sft_output / "nvarc-m2-fsdp-sft-001.log"
    log_events = json.loads(sft_log_path.read_text(encoding="utf-8"))
    log_text = "".join(item.get("data", "") for item in log_events)
    if ("bounded checkpoint disk required" not in log_text or
            (sft_output / sft_plan["run_id"]).exists() or
            (sft_output / "m2-sft-mount-preflight.json").exists()):
        raise ValidationError("M2 did not stop at the working-disk gate")
    teacher_hardware_path = teacher_output / "m3-teacher-hardware-preflight.json"
    teacher_hardware = json.loads(teacher_hardware_path.read_bytes())
    if (len(teacher_hardware.get("gpus", [])) != 4 or
            any("L4" not in item["name"] for item in teacher_hardware["gpus"])):
        raise ValidationError("M3 four-L4 observation differs")
    result_path = teacher_output / "m3-teacher-small-002/result.json"
    summary_path = teacher_output / "m3-teacher-small-002/stage-ledgers/summary.json"
    terminal_path = teacher_output / "m3-teacher-terminal.json"
    result = json.loads(result_path.read_bytes())
    summary = json.loads(summary_path.read_bytes())
    terminal = json.loads(terminal_path.read_bytes())
    record = summary.get("records", {}).get("public-arc-train-pair-001", {})
    if (result.get("plan_digest") != digest_value(teacher_plan) or
            result.get("completed_calls") != 0 or result.get("reserved_calls") != 1 or
            result.get("reserved_tokens") != 0 or result.get("responses") != [] or
            result.get("contains_evaluator_truth") is not False or
            summary.get("reserved_calls") != 1 or summary.get("stage") != "summary" or
            record.get("status") != "failed" or record.get("error_type") != "AttributeError" or
            record.get("provider_calls") != 1 or
            terminal.get("return_code") != 0 or
            terminal.get("plan_sha256") != sha(teacher_package / "plan.json")):
        raise ValidationError("M3 failed-first-call ledger differs")
    return {
        "format": "irisx/nvarc-m2-m3-decision-0031-terminal-audit-v1",
        "sft": {"run_id": sft_plan["run_id"], "version": 1,
                "status": "ERROR", "completed_optimizer_steps": 0,
                "free_working_bytes": hardware["free_working_bytes"],
                "minimum_free_working_bytes": sft_plan["minimum_free_working_bytes"],
                "hardware_sha256": sha(hardware_path), "log_sha256": sha(sft_log_path),
                "plan_sha256": sha(sft_package / "plan.json")},
        "teacher": {"run_id": teacher_plan["run_id"], "version": 1,
                    "status": "COMPLETE-with-failed-first-stage",
                    "reserved_calls": 1, "completed_calls": 0,
                    "reserved_tokens": 0, "responses": 0,
                    "hardware_sha256": sha(teacher_hardware_path),
                    "result_sha256": sha(result_path),
                    "summary_sha256": sha(summary_path),
                    "terminal_sha256": sha(terminal_path),
                    "plan_sha256": sha(teacher_package / "plan.json")},
        "contains_evaluator_truth": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sft-package", type=Path, required=True)
    parser.add_argument("--sft-output", type=Path, required=True)
    parser.add_argument("--teacher-package", type=Path, required=True)
    parser.add_argument("--teacher-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.sft_package, args.sft_output,
                    args.teacher_package, args.teacher_output)
    if args.report.exists():
        raise ValidationError("new terminal audit report path required")
    args.report.write_bytes(canonical_bytes(report, newline=True))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
