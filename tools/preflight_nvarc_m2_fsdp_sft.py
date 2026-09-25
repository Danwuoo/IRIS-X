"""Offline hash and authorization preflight for an SFT/source-solve package."""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from irisx.arc_nvarc_data import visible_task
from irisx.arc_nvarc_representation import verify_model_material
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from tools.stage_nvarc_m2_fsdp_sft import MODEL


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def preflight(package: Path, *, model_root: Path = MODEL) -> dict:
    summary = json.loads((package / "stage-summary.json").read_bytes())
    notebook_path = package / "kernel/kaggle-notebook.ipynb"
    metadata_path = package / "kernel/kernel-metadata.json"
    notebook_bytes = notebook_path.read_bytes()
    metadata_bytes = metadata_path.read_bytes()
    if (summary.get("format") != "irisx/nvarc-m2-fsdp-sft-stage-v1" or
            _sha(notebook_bytes) != summary.get("notebook_sha256") or
            _sha(metadata_bytes) != summary.get("kernel_metadata_sha256")):
        raise ValidationError("SFT package notebook or metadata differs")
    notebook = json.loads(notebook_bytes)
    if len(notebook["cells"]) != 1:
        raise ValidationError("SFT package requires one bounded notebook cell")
    source = "".join(notebook["cells"][0]["source"])
    assignments = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in {"PAYLOADS", "HASHES"}:
                assignments[node.targets[0].id] = ast.literal_eval(node.value)
    if set(assignments) != {"PAYLOADS", "HASHES"}:
        raise ValidationError("SFT notebook embedded payloads are missing")
    payloads = {name: base64.b64decode(encoded, validate=True)
                for name, encoded in assignments["PAYLOADS"].items()}
    hashes = assignments["HASHES"]
    if set(payloads) != {"plan", "sequences", "visible", "source_config",
                         "wheel_manifest", "runtime_wheel"} or set(hashes) != set(payloads):
        raise ValidationError("SFT notebook payload set differs")
    if any(_sha(value) != hashes[name] for name, value in payloads.items()):
        raise ValidationError("SFT notebook embedded hash differs")
    review_names = {"plan": "plan.json", "sequences": "sequences.jsonl",
                    "visible": "visible.json", "source_config": "source-config.json",
                    "wheel_manifest": "wheel-manifest.json"}
    if any((package / filename).read_bytes() != payloads[name]
           for name, filename in review_names.items()):
        raise ValidationError("SFT inspectable review member differs from notebook")
    plan = json.loads(payloads["plan"])
    metadata = json.loads(metadata_bytes)
    run_id = plan.get("run_id")
    if run_id not in {"nvarc-m2-fsdp-sft-001", "nvarc-m2-fsdp-sft-002"}:
        raise ValidationError("unknown SFT run identity")
    storage_ok = (
        plan.get("maximum_retrieval_member_bytes") == 1_750_000_000
        if run_id.endswith("001") else
        plan.get("checkpoint_storage") == "ephemeral-scratch" and
        plan.get("discard_resumed_checkpoint_after_load") is True and
        plan.get("minimum_free_working_bytes") == 11_000_000_000 and
        plan.get("minimum_free_scratch_bytes") == 55_000_000_000 and
        plan.get("maximum_retained_output_bytes") == 12_000_000_000)
    if (plan.get("format") != "irisx/nvarc-m2-fsdp-sft-v1" or
            plan.get("run_id") != summary["run_id"] or
            plan.get("approved") != summary["approved"] or
            plan.get("kernel_id") != metadata["id"] or
            plan.get("maximum_paid_usd") != 0 or
            plan.get("maximum_optimizer_steps") != 8 or
            plan.get("scheduled_training_tokens") != 2578 or
            plan.get("maximum_source_generation_calls") != 4 or
            not storage_ok or
            metadata.get("is_private") is not True or
            metadata.get("enable_internet") is not False or
            metadata.get("machine_shape") != "NvidiaL4" or
            metadata.get("competition_sources") != ["arc-prize-2026-arc-agi-2"] or
            metadata.get("dataset_sources") != [plan["model_dataset_id"],
                                                   plan["wheel_dataset_id"]]):
        raise ValidationError("SFT plan or transport bounds differ")
    if plan["approved"] is False:
        if (not plan["kernel_id"].startswith("DRAFT-DO-NOT-PUSH/") or
                "exact owner-approved 4B SFT plan required" not in source):
            raise ValidationError("SFT review package is not safely inert")
        with tempfile.TemporaryDirectory(prefix="nvarc-sft-draft-guard-") as scratch:
            script = Path(scratch) / "guard.py"
            script.write_text(source, encoding="utf-8")
            checked = subprocess.run([sys.executable, str(script)], capture_output=True,
                                     text=True, timeout=10)
        if (checked.returncode == 0 or
                "exact owner-approved 4B SFT plan required" not in checked.stderr):
            raise ValidationError("SFT review notebook did not stop at its approval guard")
    elif (plan.get("owner_decision") is None or
          (run_id.endswith("002") and str(plan["owner_decision"]).startswith(
              ("Decision 0028", "Decision 0029", "Decision 0030", "Decision 0031"))) or
          plan["kernel_id"] != "danielwuu/" + plan["run_id"]):
        raise ValidationError("SFT package lacks exact approval binding")
    sequences = [json.loads(line) for line in payloads["sequences"].decode().splitlines()]
    if (len(sequences) != 128 or digest_value(sequences) != plan["sequences_digest"] or
            hashes["sequences"] != plan["sequences_sha256"] or
            summary["sequences_sha256"] != hashes["sequences"]):
        raise ValidationError("SFT package sequence identity differs")
    stride = plan["sample_stride"]
    scheduled = [sequences[(plan["seed"] + index * stride) % len(sequences)]
                 for index in range(plan["world_size"] * plan["maximum_optimizer_steps"])]
    if (sum(len(item["input_ids"]) for item in scheduled) != 2578 or
            sorted({item["source"].split(":")[0] for item in scheduled}) !=
            summary["selected_parent_ids"]):
        raise ValidationError("SFT scheduled tokens or parent coverage differ")
    visible = json.loads(payloads["visible"])
    if (list(visible) != plan["source_visible_task_ids"] or
            summary["source_visible_sha256"] != hashes["visible"]):
        raise ValidationError("SFT source-visible identity differs")
    for task_id, item in visible.items():
        visible_task(task_id, item)
    config = json.loads(payloads["source_config"])
    if (config["profiles"]["4b"]["material_digest"] != plan["compact_material_digest"] or
            config["candidate"]["maximum_calls_per_task"] != 4 or
            hashes["source_config"] != plan["source_config_sha256"]):
        raise ValidationError("SFT source profile differs")
    if (_sha(payloads["plan"]) != summary["plan_sha256"] or
            _sha(payloads["runtime_wheel"]) != summary["runtime_wheel_sha256"] or
            digest_value(plan) != summary["plan_digest"]):
        raise ValidationError("SFT package plan/wheel summary differs")
    wheel_path = next((package / "wheel").glob("irisx-*.whl"))
    if wheel_path.read_bytes() != payloads["runtime_wheel"]:
        raise ValidationError("SFT staged wheel differs from notebook payload")
    with zipfile.ZipFile(wheel_path) as archive:
        if not {"irisx/arc_nvarc_fsdp_sft.py", "irisx/arc_nvarc_source_runtime.py"}.issubset(
                archive.namelist()):
            raise ValidationError("SFT staged wheel lacks runtime")
    verify_model_material(model_root, plan["compact_material_digest"],
                          allowed_extra_files={"dataset-metadata.json"}
                          if (model_root / "dataset-metadata.json").exists() else None)
    report = {"format": "irisx/nvarc-m2-fsdp-sft-preflight-v1",
              "run_id": plan["run_id"], "approved": plan["approved"],
              "plan_sha256": hashes["plan"],
              "notebook_sha256": summary["notebook_sha256"],
              "runtime_wheel_sha256": hashes["runtime_wheel"],
              "compact_material_digest": plan["compact_material_digest"],
              "scheduled_training_tokens": 2578, "optimizer_steps": 8,
              "checkpoint_storage": plan.get("checkpoint_storage", "retained-working"),
              "source_visible_task_ids": plan["source_visible_task_ids"],
              "maximum_source_generation_calls": 4,
              "maximum_paid_usd": 0, "external_calls": 0}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--compact", type=Path, default=MODEL)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = preflight(args.package, model_root=args.compact)
    if args.report is not None:
        args.report.write_bytes(canonical_bytes(report, newline=True))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
