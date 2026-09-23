"""Stage a distinct 4B repair draft locally; no provider mutation."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

import irisx_build_backend as build


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/draft-4b-pilot-002.json"
MODEL = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/base-model-manifest.json"
WHEELS = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/base-wheel-manifest.json"
OUT = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/4b-pilot-002-draft"
FINAL_ID = "danielwuu/iris-x-qwen3-5-4b-bounded-lora-compatibility-pilot-002"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stage(out: Path = OUT, plan_path: Path = PLAN,
          authorization_path: Path | None = None) -> dict:
    if out.exists() and any(out.iterdir()):
        raise ValueError("4B pilot staging directory must be new or empty")
    draft_bytes = plan_path.read_bytes()
    plan = json.loads(draft_bytes)
    if (plan.get("approved") is not False or plan.get("owner_authorization") is not None or
            plan.get("kernel_id") != "DRAFT-DO-NOT-PUSH/nvarc-4b-compat-pilot-002" or
            plan.get("run_id") != "nvarc-4b-compat-pilot-002" or
            plan.get("competition_ref") != "arc-prize-2026-arc-agi-2" or
            plan.get("model_manifest_digest") !=
            "sha256:8f27407e1b0ee4dd7a5b4d62d39af9b356ba86b5701dd93eafba052febe9c72f"):
        raise ValueError("4B pilot draft is altered or already approved")
    model_bytes = MODEL.read_bytes()
    model = json.loads(model_bytes)
    if (model.get("manifest_digest") != plan["model_manifest_digest"] or
            model.get("revision") != plan["model_revision"]):
        raise ValueError("pinned base material manifest differs")
    wheels_bytes = WHEELS.read_bytes()
    wheels = json.loads(wheels_bytes)
    if wheels.get("manifest_digest") != plan.get("wheel_manifest_digest"):
        raise ValueError("pinned base wheel manifest differs")
    wheel_entries = {item["path"]: item for item in wheels["files"]}
    if any(name not in wheel_entries for name in plan["runtime_wheels"].values()):
        raise ValueError("required offline dependency wheel is absent")
    if authorization_path is not None:
        auth = json.loads(authorization_path.read_bytes())
        if (auth.get("approved") is not True or
                auth.get("draft_plan_sha256") != sha(draft_bytes) or
                auth.get("run_id") != plan["run_id"] or
                auth.get("kernel_id") != FINAL_ID or
                not isinstance(auth.get("owner_decision"), str) or
                not auth["owner_decision"].startswith("Decision 0022")):
            raise ValueError("exact owner authorization is absent or differs")
        plan.update(approved=True, owner_authorization=auth["owner_decision"],
                    kernel_id=FINAL_ID)
    plan_bytes = (json.dumps(plan, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")) + "\n").encode()
    wheel_dir = out / "wheel"
    wheel_name = build.build_wheel(str(wheel_dir))
    wheel_bytes = (wheel_dir / wheel_name).read_bytes()
    import zipfile
    with zipfile.ZipFile(wheel_dir / wheel_name) as archive:
        if "irisx/arc_nvarc_4b_pilot_002.py" not in archive.namelist():
            raise ValueError("wheel omitted 4B pilot runner")
    encoded = {"plan": base64.b64encode(plan_bytes).decode(),
               "model": base64.b64encode(model_bytes).decode(),
               "wheels": base64.b64encode(wheels_bytes).decode(),
               "wheel": base64.b64encode(wheel_bytes).decode()}
    hashes = {key: sha(base64.b64decode(value)) for key, value in encoded.items()}
    code = f'''import base64, hashlib, json, os, pathlib, subprocess, sys, time
START = time.monotonic()
PAYLOADS = {json.dumps(encoded, sort_keys=True)}
HASHES = {json.dumps(hashes, sort_keys=True)}
for name, value in PAYLOADS.items():
    if hashlib.sha256(base64.b64decode(value)).hexdigest() != HASHES[name]:
        raise RuntimeError("embedded 4B pilot payload differs")
plan = json.loads(base64.b64decode(PAYLOADS["plan"]))
if plan.get("approved") is not True or not str(plan.get("owner_authorization", "")).startswith("Decision 0022") or plan.get("kernel_id") != "{FINAL_ID}":
    raise RuntimeError("4B pilot has no exact owner launch authorization")
if plan["maximum_paid_usd"] != 0 or plan["maximum_training_steps"] != 2 or plan["maximum_generation_calls"] != 0:
    raise RuntimeError("4B pilot ceiling differs")
os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_DATASETS_OFFLINE="1",
                  TOKENIZERS_PARALLELISM="false", WANDB_DISABLED="true")
work = pathlib.Path("/kaggle/working")
work.mkdir(parents=True, exist_ok=True)
import torch
hardware = []
for index in range(min(torch.cuda.device_count(), 8)):
    try:
        props = torch.cuda.get_device_properties(index)
        hardware.append({{"index": index, "name": str(props.name),
                         "memory_mib": int(props.total_memory // (1024 * 1024)),
                         "uuid": str(getattr(props, "uuid", "unknown"))}})
    except Exception as exc:
        hardware.append({{"index": index, "property_error": type(exc).__name__}})
try:
    smi = subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total,uuid,pci.bus_id",
                          "--format=csv,noheader,nounits"], capture_output=True,
                         text=True, check=False, timeout=30)
    smi_code = smi.returncode
    smi_rows = [line.strip() for line in smi.stdout.splitlines() if line.strip()][:8]
except (OSError, subprocess.TimeoutExpired) as exc:
    smi_code, smi_rows = None, [type(exc).__name__]
hardware_preflight = {{"run_id": plan["run_id"], "cuda_available": bool(torch.cuda.is_available()),
                      "torch_cuda_device_count": int(torch.cuda.device_count()),
                      "gpus": hardware, "nvidia_smi_exit_code": smi_code,
                      "nvidia_smi_rows": smi_rows}}
(work / "nvarc-4b-pilot-hardware-preflight.json").write_text(
    json.dumps(hardware_preflight, sort_keys=True) + "\\n", encoding="utf-8")
print(json.dumps({{"event": "notebook_hardware_preflight", **hardware_preflight}}, sort_keys=True), flush=True)
competition_roots = [pathlib.Path("/kaggle/input/competitions/arc-prize-2026-arc-agi-2"),
                     pathlib.Path("/kaggle/input/arc-prize-2026-arc-agi-2")]
competition_matches = [path for path in competition_roots
                       if (path / "arc-agi_training_challenges.json").is_file()]
mount_preflight = {{"run_id": plan["run_id"], "competition_ref": plan["competition_ref"],
                   "challenge_mount_count": len(competition_matches),
                   "challenge_mount_path": str(competition_matches[0]) if len(competition_matches) == 1 else None}}
(work / "nvarc-4b-pilot-mount-preflight.json").write_text(
    json.dumps(mount_preflight, sort_keys=True) + "\\n", encoding="utf-8")
if len(competition_matches) != 1:
    raise RuntimeError("official ARC-AGI-2 challenge mount must resolve exactly once")
roots = [pathlib.Path("/kaggle/input/datasets/danielwuu/irisx-arc-agi-2-trial-002-smoke-001"),
         pathlib.Path("/kaggle/input/irisx-arc-agi-2-trial-002-smoke-001")]
found = [path for path in roots if path.is_dir()]
if len(found) != 1:
    raise RuntimeError("base Dataset mount must resolve exactly once")
base = found[0]
expected_names = list(plan["runtime_wheels"].values())
if len(set(expected_names)) != 5 or any(not (base / name).is_file() for name in expected_names):
    raise RuntimeError("pinned offline wheel material is missing")
wheel_manifest = json.loads(base64.b64decode(PAYLOADS["wheels"]))
if wheel_manifest.get("manifest_digest") != plan["wheel_manifest_digest"]:
    raise RuntimeError("offline wheel manifest identity differs")
wheel_entries = {{item["path"]: item for item in wheel_manifest["files"]}}
for name in expected_names:
    entry = wheel_entries[name]
    path = base / name
    if path.stat().st_size != entry["byte_size"] or "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_digest"]:
        raise RuntimeError("pinned offline wheel differs: " + name)
wheel = work / "{wheel_name}"
wheel.write_bytes(base64.b64decode(PAYLOADS["wheel"]))
plan_path = work / "nvarc-4b-pilot-plan.json"
plan_path.write_bytes(base64.b64decode(PAYLOADS["plan"]))
model_manifest = work / "nvarc-4b-base-manifest.json"
model_manifest.write_bytes(base64.b64decode(PAYLOADS["model"]))
subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--find-links", str(base),
                "transformers==5.8.1", "peft==0.21.0", "safetensors==0.8.0",
                "tokenizers==0.22.2", "accelerate==1.10.1", str(wheel)],
               check=True, timeout=180)
if time.monotonic() - START >= 300:
    raise RuntimeError("4B pilot setup consumed finalization reserve")
result = work / "nvarc-4b-pilot-result.json"
ledger = work / "nvarc-4b-pilot-ledger.json"
command = [sys.executable, "-m", "irisx.arc_nvarc_4b_pilot_002", "--plan", str(plan_path),
           "--model-root", str(base), "--model-manifest", str(model_manifest),
           "--output", str(result), "--ledger", str(ledger)]
try:
    subprocess.run(command, check=False, timeout=1500, env=os.environ.copy())
except subprocess.TimeoutExpired:
    if not result.exists():
        result.write_text(json.dumps({{"format": "irisx/nvarc-4b-pilot-result",
                                      "run_id": plan["run_id"], "status": "worker_timeout",
                                      "generation_calls": 0, "truth_free": True}}) + "\\n")
if time.monotonic() - START > 1800:
    raise RuntimeError("4B pilot session wall limit exhausted")
if not result.is_file():
    raise RuntimeError("4B pilot produced no terminal result")
print(result.read_text())
'''
    compile(code, "nvarc-4b-pilot-notebook", "exec")
    kernel = out / "kernel"
    kernel.mkdir(parents=True, exist_ok=True)
    notebook = {"cells": [{"cell_type": "code", "execution_count": None,
                            "metadata": {}, "outputs": [],
                            "source": code.splitlines(keepends=True)}],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                             "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 5}
    notebook_path = kernel / "kaggle-notebook.ipynb"
    notebook_path.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
    metadata = {"id": plan["kernel_id"],
                "title": "IRIS-X Qwen3.5-4B bounded LoRA compatibility pilot 002",
                "code_file": "kaggle-notebook.ipynb", "language": "python",
                "kernel_type": "notebook", "is_private": True, "enable_gpu": True,
                "enable_tpu": False, "enable_internet": False,
                "machine_shape": "NvidiaL4", "competition_sources": [plan["competition_ref"]],
                "dataset_sources": [plan["dataset_ref"]],
                "kernel_sources": [], "model_sources": []}
    metadata_path = kernel / "kernel-metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    summary = {"approved": plan["approved"], "run_id": plan["run_id"],
               "kernel_id": plan["kernel_id"], "draft_plan_sha256": sha(draft_bytes),
               "plan_sha256": hashes["plan"], "model_manifest_sha256": hashes["model"],
               "wheel_manifest_sha256": hashes["wheels"],
               "wheel_sha256": hashes["wheel"], "notebook_sha256": sha(notebook_path.read_bytes()),
               "metadata_sha256": sha(metadata_path.read_bytes()),
               "local_kernel_path": str(kernel)}
    (out / "stage-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args()
    print(json.dumps(stage(args.output, authorization_path=args.authorization), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
