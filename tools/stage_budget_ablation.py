"""Offline staging for the two bounded Decision 0020 Kaggle kernels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import zipfile

from irisx import arc_budget_ablation as budget
from irisx.canonical import digest_value
from irisx.transport import digest_path


OLD_ROOT = Path("C:/Users/wurre/.codex/worktrees/e34a/IRIS-X/.irisx/arc-agi-2/prompt-pilot")
DATASET_REF = "danielwuu/irisx-arc-agi-2-budget-ablation-001"
MODEL_DATASET_REF = "danielwuu/irisx-arc-agi-2-trial-002-smoke-001"


def _notebook_code(run_id: str, outbound_name: str, outbound_digest: str, wheel_digest: str) -> str:
    return f'''from pathlib import Path
import hashlib
import json
import os
import stat
import subprocess
import sys
import zipfile

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['WANDB_DISABLED'] = 'true'
os.environ['PYTHONUNBUFFERED'] = '1'

def one_dir(label, paths):
    hits = [p for p in paths if p.is_dir()]
    if len(hits) != 1:
        raise RuntimeError(f'{{label}} exact mount resolution failed: {{hits}}')
    return hits[0]

def one_file(label, paths):
    hits = [p for p in paths if p.is_file()]
    if len(hits) != 1:
        raise RuntimeError(f'{{label}} exact file resolution failed: {{hits}}')
    return hits[0]

base_root = one_dir('model Dataset', [
    Path('/kaggle/input/datasets/danielwuu/irisx-arc-agi-2-trial-002-smoke-001'),
    Path('/kaggle/input/irisx-arc-agi-2-trial-002-smoke-001')])
runtime_root = one_dir('runtime Dataset', [
    Path('/kaggle/input/datasets/danielwuu/irisx-arc-agi-2-budget-ablation-001'),
    Path('/kaggle/input/irisx-arc-agi-2-budget-ablation-001')])
competition = one_file('competition challenges', [
    Path('/kaggle/input/competitions/arc-prize-2026-arc-agi-2/arc-agi_training_challenges.json'),
    Path('/kaggle/input/arc-prize-2026-arc-agi-2/arc-agi_training_challenges.json')])
archive = runtime_root / '{outbound_name}'
extracted = runtime_root / '{Path(outbound_name).stem}'
if archive.is_file() == (extracted / 'manifest.json').is_file():
    raise RuntimeError('outbound must have exactly one archive or extracted representation')
if archive.is_file():
    outbound = archive
    outbound_form = 'archive'
else:
    outbound = Path('/kaggle/working/{outbound_name}')
    outbound_form = 'exact-extracted-members'
    members = ['manifest.json', 'bindings/run.json', 'cases/jobs.json',
               'runtime/dependencies.json', 'sources/base-wheel-manifest.json',
               'sources/model-manifest.json']
    with zipfile.ZipFile(outbound, 'w', allowZip64=True) as target:
        for member in members:
            source = extracted / member
            if not source.is_file():
                raise RuntimeError(f'extracted outbound missing {{member}}')
            info = zipfile.ZipInfo(member, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            target.writestr(info, source.read_bytes())
wheel = runtime_root / 'irisx-0.2.0-py3-none-any.whl'
if not wheel.is_file() or not (base_root / 'config.json').is_file() or not (base_root / 'transformers-5.8.1-py3-none-any.whl').is_file():
    raise RuntimeError('bound model, wheel or configuration missing')
if hashlib.sha256(outbound.read_bytes()).hexdigest() != '{outbound_digest.removeprefix("sha256:")}':
    raise RuntimeError('outbound SHA-256 differs from local stage')
if hashlib.sha256(wheel.read_bytes()).hexdigest() != '{wheel_digest.removeprefix("sha256:")}':
    raise RuntimeError('runtime wheel SHA-256 differs from local stage')
print(json.dumps({{'event': 'mount_paths_resolved', 'run_id': '{run_id}', 'outbound_form': outbound_form,
                  'base_root': str(base_root), 'runtime_root': str(runtime_root),
                  'competition_challenges': str(competition)}}, sort_keys=True), flush=True)

import torch
hardware = []
for index in range(torch.cuda.device_count()):
    props = torch.cuda.get_device_properties(index)
    hardware.append({{'index': index, 'name': props.name, 'memory_mib': int(props.total_memory // (1024 * 1024)),
                     'uuid': str(getattr(props, 'uuid', 'unknown'))}})
smi = subprocess.run(['nvidia-smi', '--query-gpu=index,name,memory.total,uuid,pci.bus_id', '--format=csv,noheader,nounits'],
                     capture_output=True, text=True, check=False, timeout=30)
preflight = {{'run_id': '{run_id}', 'torch_cuda_device_count': torch.cuda.device_count(),
             'gpus': hardware, 'nvidia_smi_exit_code': smi.returncode,
             'nvidia_smi_rows': [line.strip() for line in smi.stdout.splitlines() if line.strip()]}}
Path('/kaggle/working/notebook-preflight.json').write_text(json.dumps(preflight, sort_keys=True) + '\\n', encoding='utf-8')
print(json.dumps({{'event': 'notebook_hardware_preflight', **preflight}}, sort_keys=True), flush=True)
if torch.cuda.device_count() != 4 or len(hardware) != 4 or len({{item['uuid'] for item in hardware}}) != 4 or any('L4' not in item['name'] or item['memory_mib'] < 22000 for item in hardware) or smi.returncode != 0 or len(preflight['nvidia_smi_rows']) != 4:
    raise RuntimeError('four distinct L4 GPU preflight failed')
subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--find-links', str(base_root), '--upgrade', '--no-deps',
                'transformers==5.8.1', 'jinja2==3.1.6'], check=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--force-reinstall', '--no-deps', str(wheel)], check=True)
command = [sys.executable, '-u', '-m', 'irisx.kaggle_runner_budget_ablation',
           '--outbound', str(outbound), '--model-root', str(base_root), '--competition-challenges', str(competition),
           '--output', '/kaggle/working/result.zip', '--checkpoint-output', '/kaggle/working/checkpoint.json',
           '--progress-output', '/kaggle/working/progress.jsonl']
subprocess.run(command, check=True, env={{**os.environ, 'PYTHONUNBUFFERED': '1'}})
'''


def stage(root: Path, run_id: str, arm: str | None) -> dict:
    if run_id not in {budget.DIAGNOSTIC_RUN, budget.VALIDATION_RUN}:
        raise ValueError("unknown run")
    audit = json.loads((root / "source/visible-audit.json").read_bytes())
    cohort = json.loads((root / "cohort.json").read_bytes())
    if not audit["executable_parity"]:
        raise RuntimeError("384-case source parity gate failed")
    old_outbound = OLD_ROOT / "repair-002/outbound/prompt-pilot-baseline-002.zip"
    old_solver = OLD_ROOT / "repair-002/trial/solver-cases.json"
    with zipfile.ZipFile(old_outbound) as archive:
        old_run = json.loads(archive.read("bindings/run.json"))
        model_manifest = json.loads(archive.read("sources/model-manifest.json"))
        base_wheels = json.loads(archive.read("sources/base-wheel-manifest.json"))
    workload = budget.make_workload(old_solver, run_id=run_id,
                                    cohort=cohort if run_id == budget.DIAGNOSTIC_RUN else None,
                                    validation_arm=arm)
    run = budget.make_run_binding(workload, source_audit=audit,
                                  model_manifest_digest=model_manifest["manifest_digest"],
                                  base_wheel_manifest_digest=base_wheels["manifest_digest"],
                                  baseline_split_digest=old_run["split_digest"],
                                  cohort_digest=cohort["manifest_digest"])
    run_root = root / ("diagnostic" if run_id == budget.DIAGNOSTIC_RUN else "validation")
    if run_root.exists() and any(run_root.iterdir()):
        if not (run_root / "run-binding.json").is_file() or json.loads((run_root / "run-binding.json").read_bytes()) != run:
            raise RuntimeError(f"existing run stage has a different bound identity: {run_root}")
    outbound_dir = run_root / "outbound"
    outbound_dir.mkdir(parents=True, exist_ok=True)
    outbound = outbound_dir / f"{run_id}.zip"
    if outbound.exists():
        budget.verify_outbound(outbound)
        outbound_digest = digest_path(outbound)
        if json.loads(zipfile.ZipFile(outbound).read("bindings/run.json")) != run:
            raise RuntimeError("existing outbound differs from bound run")
    else:
        outbound_digest = budget.build_outbound(outbound, run, workload, old_outbound)
    budget.atomic_json(run_root / "run-binding.json", run)
    wheel = root / "runtime/irisx-0.2.0-py3-none-any.whl"
    if not wheel.is_file():
        raise RuntimeError("build the local IRIS-X wheel before staging")
    wheel_digest = digest_path(wheel)
    dataset = run_root / "dataset"
    dataset.mkdir(exist_ok=True)
    budget.atomic_json(dataset / "dataset-metadata.json", {
        "title": "IRIS-X ARC-AGI-2 Budget Ablation Transport", "id": DATASET_REF,
        "description": "Private truth-free Decision 0020 transport; model and offline dependencies remain in the existing bound Trial 002 Dataset.",
        "licenses": [{"name": "other"}]})
    shutil.copy2(outbound, dataset / outbound.name)
    shutil.copy2(wheel, dataset / wheel.name)
    kernel = run_root / "kernel"
    kernel.mkdir(exist_ok=True)
    metadata = {"id": f"danielwuu/iris-x-arc-agi-2-{run_id}", "title": f"IRIS-X ARC-AGI-2 {run_id}",
                "code_file": "kaggle-notebook.ipynb", "language": "python", "kernel_type": "notebook",
                "is_private": True, "enable_gpu": True, "enable_internet": False, "enable_tpu": False,
                "machine_shape": "NvidiaL4", "competition_sources": [budget.pilot.COMPETITION_SLUG],
                "dataset_sources": [MODEL_DATASET_REF, DATASET_REF], "kernel_sources": [], "model_sources": []}
    budget.atomic_json(kernel / "kernel-metadata.json", metadata)
    code = _notebook_code(run_id, outbound.name, outbound_digest, wheel_digest)
    notebook = {"cells": [{"cell_type": "markdown", "metadata": {}, "source": [f"# {run_id}\n", "Private Decision 0020 four-L4 execution.\n"]},
                          {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": code.splitlines(keepends=True)}],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 5}
    (kernel / "kaggle-notebook.ipynb").write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if any(path.name in {"evaluator-truth.json", "arc-agi_training_solutions.json"} for path in dataset.rglob("*")):
        raise RuntimeError("staged Dataset contains evaluator truth")
    if metadata["competition_sources"] != ["arc-prize-2026-arc-agi-2"] or metadata["machine_shape"] != "NvidiaL4" or metadata["is_private"] is not True or metadata["enable_internet"] is not False:
        raise RuntimeError("kernel execution boundary differs")
    compile(code, str(kernel / "kaggle-notebook.ipynb"), "exec")
    return {"run_id": run_id, "run_identity_digest": run["run_identity_digest"],
            "workload_digest": run["workload_digest"], "outbound_digest": outbound_digest,
            "runtime_wheel_digest": wheel_digest, "kernel_ref": metadata["id"], "dataset_ref": DATASET_REF,
            "kernel_metadata_digest": digest_path(kernel / "kernel-metadata.json"),
            "notebook_digest": digest_path(kernel / "kaggle-notebook.ipynb"), "dataset_path": str(dataset),
            "kernel_path": str(kernel)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", choices=["diagnostic", "validation"])
    parser.add_argument("--arm", choices=sorted(budget.ARMS))
    parser.add_argument("--root", type=Path, default=Path(".irisx/arc-agi-2/budget-ablation"))
    args = parser.parse_args()
    if args.run == "validation" and not args.arm:
        parser.error("validation requires --arm")
    if args.run == "diagnostic" and args.arm:
        parser.error("diagnostic has three fixed arms")
    result = stage(args.root, budget.DIAGNOSTIC_RUN if args.run == "diagnostic" else budget.VALIDATION_RUN, args.arm)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
