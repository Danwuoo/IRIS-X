"""Offline CPython/wheel/material preparation for the distinct goal-directed run.

No model is loaded here. Every installed distribution is pinned by wheel bytes;
host site-packages are excluded. Original datasets/notebook/evidence are never
modified. The notebook supplies an immutable pre-dispatch session clock.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

SOURCE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(SOURCE), str(SOURCE / "src")]
from tools.arc2_goal_sprint_20261017.launch import (require, regular, sha, write_new, verify_inventory,
    SOLVER_MANIFEST_SHA256, TRAINING_MANIFEST_SHA256)

from tools.arc2_goal_sprint_20261017 import materials

WHEEL_MANIFEST_SHA256 = "2b082a3c36534b5602b8a9f738beec2c01b3d2df11b5438f1c352a84c118b052"
INTERPRETER_MANIFEST_SHA256 = "20a52944f1ee2abf6f47a2e3beafce44951993439fede39335e660cea143495e"
MODEL_CONTRACT_SHA256 = "8d26b2f04a91147bbb5e11231f614552d36e2862af9b8d2d2b05b273805b69b0"
REFERENCES = {
    "wheels": "danielwuu/iris-arc-next-cu128-cp312-wheels/1",
    "interpreter": "danielwuu/iris-arc-next-cpython312-offline/2",
    "training": "danielwuu/iris-x-learning-training-20261011/1",
    "public": "danielwuu/iris-x-public120-data-20261010/1",
    "model": "qwen-lm/qwen-3/Transformers/14b/1",
}


def resolve_dataset(input_root, reference):
    owner, slug, version = reference.split("/")
    require(version.isdigit(), "explicit dataset version required")
    root = Path(input_root)
    paths = [root / slug, root / "datasets" / owner / slug]
    present = [p for p in paths if p.is_dir()]
    require(len(present) == 1, "one mounted dataset required: " + reference)
    require(not present[0].is_symlink(), "dataset mount cannot be a symlink")
    return present[0].absolute()


def remaining(request, reserve=300):
    left = request["session_deadline_epoch"] - time.time() - reserve
    require(left > 0, "absolute platform session deadline reached")
    return left


def exact_files(root, expected, *, optional=()):
    """Check all mounted filenames without opening unadmitted file bodies."""
    root = Path(root)
    actual = set()
    for path in root.rglob("*"):
        require(not path.is_symlink(), "mounted material symlink forbidden")
        require(path.is_dir() or path.is_file(), "special mounted material forbidden")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    require(set(expected) <= actual and actual <= set(expected) | set(optional), "unexpected/missing mounted inventory: " + str(root))
    return len(actual)


def solver_projection(root):
    """Accept either provider-observed flat transport or explicit solver prefix."""
    root = Path(root)
    candidates = [path for path in (root, root / "solver") if (path / "manifest.json").is_file()]
    require(len(candidates) == 1, "exactly one solver projection layout required")
    solver = candidates[0]
    expected = {"manifest.json", "public-challenges.json", "LICENSE", "NOTICE"}
    if solver == root:
        exact_files(root, expected, optional=("dataset-metadata.json",))
        # verify_inventory excludes metadata, which the provider normally omits.
        require(not (root / "dataset-metadata.json").exists(), "flat runtime projection must omit upload metadata")
    else:
        exact_files(root, {"solver/" + name for name in expected}, optional=("dataset-metadata.json",))
    verify_inventory(solver, SOLVER_MANIFEST_SHA256)
    return solver


def offline_env():
    # Retain normal host runtime/driver context, but never host Python/loader overrides.
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME", "LD_PRELOAD", "LD_LIBRARY_PATH"}}
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_DATASETS_OFFLINE="1",
               HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1", WANDB_DISABLED="true",
               PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1",
               TOKENIZERS_PARALLELISM="false", CUDA_VISIBLE_DEVICES="0")
    return env


def prepare_python(request, roots, work):
    if (sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 12)
            and platform.system() == "Linux" and platform.machine() == "x86_64"):
        python = sys.executable
        origin = {"kind": "ambient-compatible-cpython312", "executable": python, "version": sys.version}
    else:
        from tools.arc_next_offline_interpreter import prepare_interpreter
        prepared = prepare_interpreter(roots["interpreter"], INTERPRETER_MANIFEST_SHA256, work / "cpython312")
        python = prepared["python_executable"]
        origin = {"kind": "pinned-offline-cpython312", "receipt": prepared}
    environment = work / "venv"
    with (work / "install.log").open("xb") as log:
        subprocess.run([python, "-I", "-B", "-m", "venv", "--copies", str(environment)],
                       check=True, timeout=remaining(request), env=offline_env(), stdout=log, stderr=log)
    return environment / "bin/python", origin


def verified_wheels(wheel_root, extra_root):
    require(sha(regular(wheel_root / "wheel-lock.json")) == WHEEL_MANIFEST_SHA256, "original wheel manifest pin differs")
    original = json.loads((wheel_root / "wheel-lock.json").read_bytes())
    extra = json.loads(regular(extra_root / "extra-wheel-lock.json").read_bytes())
    rows = {}
    paths = []
    for root, inventory in ((wheel_root / "wheels", original["files"]), (extra_root, extra["files"])):
        exact_files(root, inventory, optional=("extra-wheel-lock.json",) if root == extra_root else ())
        for name, row in inventory.items():
            require(Path(name).name == name and name.endswith(".whl"), "wheel filename required")
            path = regular(root / name)
            # Some historical wheel Datasets use a wheelhouse subdirectory.
            require(path.stat().st_size == row["bytes"] and sha(path) == row["sha256"], "wheel bytes differ: " + name)
            key = row["name"].lower().replace("_", "-")
            require(key not in rows or rows[key] == row, "conflicting wheel distributions")
            rows[key] = row
            paths.append(path)
    require({"torch", "transformers", "peft", "pydantic", "pydantic-core", "annotated-types", "typing-inspection"} <= set(rows),
            "complete ML and AF3 dependencies required")
    return rows, paths


def install(request, roots, work):
    python, interpreter = prepare_python(request, roots, work)
    extra = SOURCE / "extra-wheels"
    rows, _ = verified_wheels(roots["wheels"], extra)
    requirements = work / "requirements.lock"
    requirements.write_text("\n".join(f"{name}=={row['version']} --hash=sha256:{row['sha256']}"
                                      for name, row in sorted(rows.items())) + "\n")
    environment = python.parent.parent
    env = offline_env()
    with (work / "install.log").open("ab") as log:
        subprocess.run([str(python), "-I", "-B", "-m", "pip", "install", "--isolated", "--no-index", "--no-cache-dir",
                        "--only-binary=:all:", "--require-hashes", "--find-links", str(roots["wheels"] / "wheels"),
                        "--find-links", str(extra), "--report", str(work / "pip-report.json"), "-r", str(requirements)],
                       check=True, timeout=remaining(request), env=env, stdout=log, stderr=log)
        subprocess.run([str(python), "-I", "-B", "-m", "pip", "check"],
                       check=True, timeout=remaining(request), env=env, stdout=log, stderr=log)
    sites = list((environment / "lib").glob("python3.12/site-packages"))
    require(len(sites) == 1, "one isolated CP312 site-packages required")
    site = sites[0]
    libraries = sorted((site / "nvidia").glob("*/lib")) + [site / "torch/lib"]
    # CUDA runtime/cuDNN come first from the pinned wheels, driver last from host.
    libraries += [Path(p) for p in ("/usr/local/nvidia/lib64", "/usr/local/nvidia/lib", "/usr/lib/x86_64-linux-gnu") if Path(p).is_dir()]
    env["LD_LIBRARY_PATH"] = ":".join(str(p) for p in libraries if p.is_dir())
    env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "/usr/bin:/bin")
    probe_code = "import sys; sys.path[:0]=" + repr([str(SOURCE), str(SOURCE / "src")]) + "\n" + '''
import importlib.metadata as m,json,time,torch,transformers,peft,pydantic
import tools.arc2_goal_sprint_20261017.run, tools.arc_offline_evaluation
from tools.arc2_agent_factory3_bridge_20261014.provenance import verify_vendor
from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard, verify_closed_proof
from tools.arc2_goal_sprint_20261017.launch import require
verify_vendor()
guard = OwnedProcessGuard.spawn([sys.executable, '-I', '-B', '-c', 'pass'], evidence_dir=sys.argv[1])
deadline = time.monotonic() + 15
while guard.poll() is None and time.monotonic() < deadline: time.sleep(.05)
proof = guard.stop(timeout=15) if guard.poll() is None else guard.closed_proof()
verify_closed_proof(proof)
require(proof['worker_returncode'] == 0, 'No-op owned guard failed')
print(json.dumps({'versions':{k:m.version(k) for k in ('torch','transformers','peft','pydantic')}, 'owned_noop_closure':proof}))
'''
    probe = subprocess.run([str(python), "-I", "-B", "-c", probe_code, str(work / "prepare-owned-tree")],
        check=True, capture_output=True, text=True, timeout=min(300, remaining(request)), env=env)
    admission = json.loads(probe.stdout.splitlines()[-1])
    receipt = {"format": "irisx/goal-offline-runtime-v1", "interpreter": interpreter,
               "python": str(python), "wheel_manifest_sha256": WHEEL_MANIFEST_SHA256,
               "extra_wheel_manifest_sha256": sha(extra / "extra-wheel-lock.json"),
               "pip_check_passed": True, "no_index": True, "solver_scorer_af3_imported": True,
               "model_loaded": False, **admission,
               "requirements_sha256": sha(requirements), "environment": str(environment)}
    write_new(work / "runtime-receipt.json", receipt)
    return str(python), str(environment), env


def prepare_model(input_root, work, *, request=None):
    contract_path = SOURCE / "materials/qwen14b/material-contract.json"
    require(sha(regular(contract_path)) == MODEL_CONTRACT_SHA256, "Qwen material contract differs")
    contract = json.loads(contract_path.read_bytes())
    bases = [Path(input_root) / "qwen-3", Path(input_root) / "models/qwen-lm/qwen-3"]
    candidates = []
    visited = 0
    for base in bases:
        if not base.is_dir():
            continue
        for directory, subdirs, filenames in os.walk(base, followlinks=False):
            directory = Path(directory)
            require(not directory.is_symlink(), "model mount symlink forbidden")
            visited += len(subdirs) + len(filenames)
            require(visited < 8192 and len(directory.relative_to(base).parts) <= 7, "bounded model mount discovery exceeded")
            subdirs[:] = [name for name in subdirs if not (directory / name).is_symlink()]
            if {"model.safetensors.index.json", "config.json"} <= set(filenames):
                require(not subdirs and set(filenames) == set(contract["provider_files"]), "exact provider model inventory required")
                candidates.append(directory)
    require(len(candidates) == 1, "one pinned qwen-lm/qwen-3 model mount required")
    mount = candidates[0]
    verified = {}
    for name, row in contract["provider_files"].items():
        if request is not None:
            remaining(request)
        path = regular(mount / name)
        require(path.stat().st_size == row["size_bytes"], "model provider size differs")
        if row.get("runtime_full_sha256_required"):
            actual = sha(path)
            require(actual == row["sha256"], "model provider hash differs: " + name)
            verified[name] = actual
    model = work / "model"
    model.mkdir()
    for name, row in contract["provider_files"].items():
        if row["role"] in {"base-weight", "weight-index"}:
            (model / name).symlink_to(mount / name)
    overlay = contract_path.parent / "hf-overlay"
    exact_files(overlay, contract["overlay_files"])
    for name, row in contract["overlay_files"].items():
        path = regular(overlay / name)
        require(path.stat().st_size == row["size_bytes"] and sha(path) == row["sha256"], "model overlay differs")
        shutil.copyfile(path, model / name)
    require({name for name, row in contract["provider_files"].items() if row["role"] in {"base-weight", "weight-index"}}
            <= verified.keys(), "full base weight/index hashes must be verified")
    require(REFERENCES["model"] == materials.MODEL_SOURCE and MODEL_CONTRACT_SHA256 == materials.MODEL_CONTRACT_SHA256,
            "protected production base identity differs")
    write_new(work / "model-receipt.json", {"reference": REFERENCES["model"], "provider_mount": str(mount),
        "contract_sha256": MODEL_CONTRACT_SHA256, "verified_sha256": verified,
        "loader": "pinned provider shards and index; pinned official HF config/tokenizer overlay",
        "model_base_identity": materials.base_identity(), "model_path": str(model), "model_loaded": False})
    return model, mount


def prepare_continuation(request, specs, parameters, python, env, runtime, training, public_solver):
    """Validate CPU material bytes/lineage with pinned installed dependencies."""
    if not specs and not parameters:
        return None
    inputs = {"specs": specs, "parameters": parameters, "training_root": str(training / "data/training"),
              "training_manifest_path": str(training / "manifest.json"),
              "public_path": str(public_solver / "public-challenges.json")}
    path = runtime / "continuation-check.json"
    write_new(path, inputs)
    code = "import sys; sys.path[:0]=" + repr([str(SOURCE), str(SOURCE / "src")]) + "\n" + '''
import json
from tools.arc2_goal_sprint_20261017.materials import validate_runtime_materials
with open(sys.argv[1]) as stream: inputs = json.load(stream)
print(json.dumps(validate_runtime_materials(**inputs), sort_keys=True))
'''
    result = subprocess.run([python, "-I", "-B", "-c", code, str(path)], check=True,
        capture_output=True, text=True, env=env, timeout=min(600, remaining(request)))
    receipt = json.loads(result.stdout.splitlines()[-1])
    require(receipt["model_loaded"] is False and receipt["adapter_loaded"] is False
            and receipt["training_executed"] is False, "CPU material validation must not claim model execution")
    write_new(runtime / "continuation-receipt.json", receipt)
    return receipt


def bootstrap(request):
    parameters = materials.validate_request_options(request)
    start = request["started_epoch"]
    require(type(start) in {int, float} and math.isfinite(start) and 0 < start <= time.time(), "actual pre-dispatch epoch required")
    require(request["session_deadline_epoch"] == start + 43200, "unchanged 12-hour platform deadline required")
    remaining(request)
    require(sha(regular(SOURCE / "source-manifest.json")) == request["source_manifest_sha256"], "source manifest pin differs")
    manifest = json.loads((SOURCE / "source-manifest.json").read_bytes())
    for name, row in manifest["files"].items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "unsafe source file path")
        path = regular(SOURCE / name)
        require(path.stat().st_size == row["bytes"] and sha(path) == row["sha256"], "source file identity differs: " + name)
    optional_materials = materials.resolve_materials(SOURCE, request.get("continuation_materials_sha256"),
                                                    source_files=manifest["files"])
    root = Path(request["working_root"]).absolute()
    root.mkdir(parents=True, exist_ok=False)
    write_new(root / "request.json", request)
    mode = request.get("evaluation_mode", "landlock-local")
    require(mode in {"landlock-local", "external-cpu"}, "unknown evaluation boundary")
    references = dict(REFERENCES)
    if mode == "external-cpu":
        require(request.get("solver_dataset") and request["solver_dataset"] != REFERENCES["public"], "distinct solver-only Dataset required")
        references["public"] = request["solver_dataset"]
    roots = {role: resolve_dataset(request["input_root"], references[role])
             for role in ("wheels", "interpreter", "training", "public")}
    if mode == "external-cpu":
        public_solver = solver_projection(roots["public"])
    else:
        public_solver = roots["public"] / "solver"
        verify_inventory(public_solver, SOLVER_MANIFEST_SHA256)
    training_manifest = verify_inventory(roots["training"], TRAINING_MANIFEST_SHA256)
    source_mount = resolve_dataset(request["input_root"], request["source_dataset"])
    expected_source = {manifest["transport"]["filename"]} if "transport" in manifest else set(manifest["files"])
    exact_files(source_mount, expected_source | {"source-manifest.json"}, optional=("dataset-metadata.json",))
    runtime = Path(request.get("runtime_root", "/kaggle/temp/" + request["run_id"])).absolute()
    require(not runtime.is_relative_to(root), "ephemeral runtime must be outside harvested working output")
    runtime.mkdir(parents=True, exist_ok=False)
    python, environment, env = install(request, roots, runtime)
    model, mount = prepare_model(request["input_root"], runtime, request=request)
    # These values originate only in successfully verified preparation, never
    # from a request, adapter metadata or a tunable config dictionary.
    verified_base_identity = materials.base_identity()
    continuation_receipt = prepare_continuation(request, optional_materials, parameters, python, env,
                                               runtime, roots["training"], public_solver)
    allowed_input_roots = [str(p) for p in roots.values()] + [str(mount),
        str(source_mount)]
    if mode == "external-cpu":
        from tools.arc2_goal_sprint_20261017.launch import check_dataset_separation
        check_dataset_separation(request["input_root"], allowed_input_roots)
    require(type(request.get("prepare_only", False)) is bool, "Boolean preparation-only flag required")
    remaining(request)
    if request.get("prepare_only", False):
        receipt = {"format": "irisx/goal-runtime-ready-v1", "status": "READY", "run_id": request["run_id"],
            "source_dataset": request["source_dataset"], "source_manifest_sha256": request["source_manifest_sha256"],
            "solver_dataset": references["public"], "solver_manifest_sha256": SOLVER_MANIFEST_SHA256,
            "solver_projection_root": str(public_solver),
            "wheel_manifest_sha256": WHEEL_MANIFEST_SHA256, "training_manifest_sha256": TRAINING_MANIFEST_SHA256,
            "evaluation_mode": mode, "python": python, "runtime_receipt_sha256": sha(runtime / "runtime-receipt.json"),
            "model_receipt_sha256": sha(runtime / "model-receipt.json"), "mounted_input_roots": allowed_input_roots,
            "training_inventory_verified_files": len(training_manifest["files"]),
            "source_inventory_verified_files": len(manifest["files"]), "solver_inventory_verified": True,
            "model_loaded": False, "training_executed": False, "inference_executed": False,
            "gpu_execution_performed": False, "evaluator_answer_bytes_read": False, "completed_epoch": time.time()}
        if continuation_receipt is not None:
            receipt["continuation_materials"] = continuation_receipt
        write_new(root / "prepare-ready.json", receipt)
        print(json.dumps(receipt, sort_keys=True), flush=True)
        return receipt
    config = {"run_id": request["run_id"], "model_path": str(model),
        "training_root": str(roots["training"] / "data/training"), "training_manifest_path": str(roots["training"] / "manifest.json"),
        "public_path": str(public_solver / "public-challenges.json"), "output_dir": str(root / "solver"),
        "seed": 20261017, "session_deadline_epoch": request["session_deadline_epoch"],
        "training_seconds": 24000, "sft_steps": 3072, "rl_batches": 12, "rl_group_size": 8,
        "rl_parents_per_batch": 8, "ttt_steps": 8, "context_tokens": 8192, "generation_tokens": 2048, "dev_tasks": 24}
    config.update(parameters)
    config.update(optional_materials)
    config["model_path"] = str(model)
    config["model_base_identity"] = verified_base_identity
    config["training_manifest_sha256"] = TRAINING_MANIFEST_SHA256
    launch_request = {"source_root": str(SOURCE), "source_manifest_sha256": request["source_manifest_sha256"],
        "control_root": str(root / "control"), "evaluator_root": str(roots["public"] / "evaluator"),
        "environment_root": str(runtime), "model_roots": [str(model), str(mount)],
        "python": python, "runtime_env": env, "solver_config": config,
        "evaluation_mode": mode, "input_root": request["input_root"],
        "allowed_input_roots": allowed_input_roots,
        "solver_dataset": references["public"]}
    path = root / "launch-request.json"
    # Do not serialize ambient secrets from runtime_env into retained receipts.
    child_request = {**launch_request, "runtime_env": {k: v for k, v in env.items() if k in {
        "PATH", "LD_LIBRARY_PATH", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK", "WANDB_DISABLED", "PYTHONDONTWRITEBYTECODE",
        "PIP_NO_INDEX", "PIP_DISABLE_PIP_VERSION_CHECK", "TOKENIZERS_PARALLELISM", "CUDA_VISIBLE_DEVICES",
        "LANG", "LC_ALL", "TZ", "NVIDIA_VISIBLE_DEVICES", "NVIDIA_DRIVER_CAPABILITIES"}}}
    write_new(path, child_request)
    completed = subprocess.run([python, "-I", "-B", str(SOURCE / "tools/arc2_goal_sprint_20261017/launch.py"), "--request", str(path)],
        env=env, timeout=remaining(request, reserve=30), check=False)
    require(completed.returncode == 0, "protected launcher failed; retain runtime/control evidence")


def preserve_runtime_evidence(request):
    """Retain small receipts, never the multi-GB venv, interpreter or model links."""
    root = Path(request["working_root"])
    runtime = Path(request.get("runtime_root", "/kaggle/temp/" + request["run_id"]))
    if not root.is_dir() or not runtime.is_dir():
        return
    destination = root / "runtime-evidence"
    destination.mkdir(exist_ok=True)
    for name in ("install.log", "runtime-receipt.json", "model-receipt.json", "requirements.lock", "pip-report.json", "continuation-receipt.json"):
        source = runtime / name
        if source.is_file():
            require(source.stat().st_size <= 16 * 1024**2, "bounded runtime receipt exceeded: " + name)
            shutil.copyfile(regular(source), destination / name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    args = parser.parse_args()
    request = json.loads(regular(args.request).read_bytes())
    try:
        bootstrap(request)
    except BaseException as exc:
        target = Path(request["working_root"])
        if target.is_dir() and not (target / "bootstrap-failure.json").exists():
            write_new(target / "bootstrap-failure.json", {"status": "ERROR", "error_type": type(exc).__name__,
                "message": str(exc), "started_epoch": request["started_epoch"],
                "session_deadline_epoch": request["session_deadline_epoch"], "epoch": time.time()})
        raise
    finally:
        preserve_runtime_evidence(request)


if __name__ == "__main__":
    main()
