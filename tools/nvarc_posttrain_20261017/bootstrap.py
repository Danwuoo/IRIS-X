"""Offline dual-specialist preparation and owned-controller launch.

No evaluator dataset is admitted. Ordinary independent CUDA processes share
one actual device; no MIG, security settings, MPS daemon or driver changes.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
import time

SOURCE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(SOURCE), str(SOURCE / "src")]
from tools.arc2_goal_sprint_20261017 import bootstrap as offline
from tools.arc2_goal_sprint_20261017.launch import (
    TRAINING_MANIFEST_SHA256, check_dataset_separation, regular, require,
    relay_solver_log, sha, verify_inventory, write_new,
)
from tools.nvarc_posttrain_20261017.materials import model_pin, verify_model
from tools.nvarc_posttrain_20261017.score import seal
from tools.arc2_goal_sprint_20261017.data import digest

ENV_KEYS = {"PATH", "LD_LIBRARY_PATH", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE",
    "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK", "WANDB_DISABLED", "PYTHONDONTWRITEBYTECODE",
    "PIP_NO_INDEX", "PIP_DISABLE_PIP_VERSION_CHECK", "TOKENIZERS_PARALLELISM", "CUDA_VISIBLE_DEVICES",
    "LANG", "LC_ALL", "TZ", "NVIDIA_VISIBLE_DEVICES", "NVIDIA_DRIVER_CAPABILITIES"}


def resolve_model(input_root, variant):
    pin = model_pin(variant)
    owner, slug, framework, variation, version = pin["model_source"].split("/")
    roots = [Path(input_root) / slug, Path(input_root) / "models" / owner / slug]
    candidates = []
    visited = 0
    for root in roots:
        if not root.is_dir():
            continue
        for directory, subdirs, files in os.walk(root, followlinks=False):
            directory = Path(directory)
            visited += len(subdirs) + len(files)
            require(visited <= 1024 and len(directory.relative_to(root).parts) <= 6,
                    "bounded official model mount discovery required")
            require(not directory.is_symlink() and all(not (directory / name).is_symlink() for name in subdirs),
                    "model mount symlink forbidden")
            if "config.json" in files:
                require(not subdirs, "flat official model version required")
                candidates.append(directory)
    require(len(candidates) == 1, "one exact official model mount required: " + variant)
    identity = verify_model(candidates[0], variant)
    return candidates[0].absolute(), identity


def verify_source(request):
    path = regular(SOURCE / "source-manifest.json")
    require(sha(path) == request["source_manifest_sha256"], "source manifest pin differs")
    manifest = json.loads(path.read_bytes())
    require(manifest["format"] == "irisx/nvarc-source-manifest-v1"
        and manifest["run_id"] == request["run_id"] and manifest["contains_evaluator_data"] is False,
        "exact solver-only successor source identity required")
    for name, row in manifest["files"].items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "safe source paths required")
        item = regular(SOURCE / name)
        require(item.stat().st_size == row["bytes"] and sha(item) == row["sha256"], "source bytes differ: " + name)
    return manifest


def protected_launch(config, control, env):
    from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard, verify_closed_proof
    control = Path(control)
    control.mkdir(parents=True, exist_ok=False)
    config_path = control / "controller-config.json"
    write_new(config_path, config)
    deadline = config["deadline_epoch"] - 60
    require(time.time() < deadline, "original session closure reserve exhausted")
    guard = None
    try:
        with (control / "controller.log").open("xb") as log, (control / "controller.log").open("rb") as relay:
            guard = OwnedProcessGuard.spawn([config["python"], "-I", "-B", str(SOURCE / "tools/nvarc_posttrain_20261017/bootstrap.py"),
                "--controller", str(config_path)], evidence_dir=control / "owned-tree", cwd=SOURCE,
                env=env, stdin=None, stdout=log, stderr=log)
            while guard.poll() is None and time.time() < deadline:
                relay_solver_log(relay)
                time.sleep(min(2., max(.01, deadline - time.time())))
            proof = guard.stop(timeout=30) if guard.poll() is None else guard.closed_proof()
            verify_closed_proof(proof)
            write_new(control / "owner-closure.json", proof)
            for _ in range(16):
                if not relay_solver_log(relay):
                    break
    finally:
        if guard is not None and guard.poll() is None:
            guard.stop(timeout=30)
    if config.get("workflow") in {"paired-ttt-stability-v1", "compact-matched-controls-v1", "compact-convergence-screen-v1"}:
        if config["workflow"] == "compact-convergence-screen-v1":
            from tools.nvarc_posttrain_20261017.convergence_controller import close_diagnostic
        elif config["workflow"] == "compact-matched-controls-v1":
            from tools.nvarc_posttrain_20261017.matched_controller import close_diagnostic
        else:
            from tools.nvarc_posttrain_20261017.stability_controller import close_diagnostic
        terminal = close_diagnostic(config, control, proof)
        print(json.dumps({k: v for k, v in terminal.items() if k != "files"}, sort_keys=True), flush=True)
        return terminal
    preserve_failed_denominator(config, proof)
    receipt = seal(config["output_root"], control / "sealed", proof, config["source_identity"])
    terminal = {"status": "SEALED_AWAITING_EXTERNAL_EVALUATOR", "run_id": config["run_id"],
        "prediction_seal_sha256": sha(control / "sealed/prediction-seal.json"), "pools_sha256": receipt["pools_sha256"],
        "source_manifest_sha256": config["source_identity"], "provider_terminal_verified": False,
        "inherited_exposure_qualified": True, "clean_generalization_claimed": False,
        "public_score": None, "official_score": None, "generation_may_resume": False}
    write_new(control / "terminal.json", terminal)
    print(json.dumps(terminal, sort_keys=True), flush=True)
    return terminal


def preserve_failed_denominator(config, proof):
    """A closed failed controller still exports explicit misses, not fake work.

    Never fabricate candidates, choose a new checkpoint, or overwrite an
    existing pool. Reconstruct the already-declared ensemble from any closed
    specialist output; absent models contribute explicit misses.
    """
    from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof
    verify_closed_proof(proof)
    output = Path(config["output_root"])
    output.mkdir(parents=True, exist_ok=True)
    admission_path = output / "public-evidence-admission.json"
    if not admission_path.exists():
        from tools.nvarc_posttrain_20261017.controller import public_record_admitted
        admission = {"source_identity": config["source_identity"], "models": {
            variant: {"admitted": False, "status": "no_bound_public_evidence", "path": None} for variant in ("2b", "4b")}}
        topology_path = output / "topology.json"
        device = json.loads(regular(topology_path).read_bytes()).get("device_identity") if topology_path.exists() else None
        for wave_path in sorted(output.glob("public-*/wave.json")):
            wave = json.loads(regular(wave_path).read_bytes())
            for row in wave["jobs"]:
                job_id = row.get("job_id")
                if job_id not in {"2b-S", "4b-S"}:
                    continue
                worker_root = wave_path.parent / job_id
                config_path = worker_root / "config.json"
                if not config_path.is_file():
                    continue
                worker = json.loads(regular(config_path).read_bytes())
                bound = (worker.get("job_id") == job_id and worker.get("mode") == "public"
                    and worker.get("source_identity") == config["source_identity"]
                    and worker.get("device_identity") == device
                    and worker.get("workload_identity") == "compact-selected-full-public-v1"
                    and public_record_admitted(row, source_identity=config["source_identity"], device_identity=device))
                path = worker_root / "pools.json"
                variant = job_id.split("-")[0]
                if bound and path.is_file():
                    require(not admission["models"][variant]["admitted"], "duplicate admitted specialist output")
                    admission["models"][variant] = {"admitted": True, "status": row["status"],
                        "path": path.relative_to(output).as_posix()}
        write_new(admission_path, admission)
    admission = json.loads(regular(admission_path).read_bytes())
    require(admission.get("source_identity") == config["source_identity"] and set(admission["models"]) == {"2b", "4b"},
            "bound complete public evidence admission required")
    if not (output / "pools.json").exists():
        public = json.loads(regular(config["public_path"]).read_bytes())
        require(len(public) == 120 and sum(len(t["test"]) for t in public.values()) == 167, "full fallback denominator required")
        empty = {"format": "irisx/arc-offline-pools-v1", "run_id": config["run_id"],
            "method": "explicit missing specialist after closed controller failure", "challenges_digest": digest(public),
            "records": [{"task_id": key, "tests": [{"test_index": i, "input_digest": digest(q["input"]),
                "ranked_grids": [], "status": "controller_failed"} for i, q in enumerate(task["test"])]}
                for key, task in sorted(public.items())]}
        by_variant = {}
        for variant, row in admission["models"].items():
            if row["admitted"]:
                relative = Path(row["path"])
                require(not relative.is_absolute() and ".." not in relative.parts and len(relative.parts) == 3
                    and relative.parts[0].startswith("public-") and relative.parts[1] == variant + "-S"
                    and relative.parts[2] == "pools.json", "safe admitted specialist path required")
                by_variant[variant] = json.loads(regular(output / relative).read_bytes())
        for variant in ("2b", "4b"):
            by_variant.setdefault(variant, empty)
        from tools.nvarc_posttrain_20261017.controller import ensemble_pools
        pools = ensemble_pools(public, by_variant, run_id=config["run_id"])
        write_new(output / "pools.json", pools)
    if not (output / "run-summary.json").exists():
        write_new(output / "run-summary.json", {"run_id": config["run_id"], "source_identity": config["source_identity"],
            "solver_status": "failed", "inherited_exposure_qualified": True, "clean_generalization_claimed": False,
            "failure_denominator_preserved_after_closure": True, "model_success_claimed": False,
            "external_scoring_required": True, "public_tasks": 120, "public_queries": 167})
    if not (output / "selected-checkpoints.json").exists():
        write_new(output / "selected-checkpoints.json", {"selection_completed": False})
    if not (output / "isolation.json").exists():
        check_dataset_separation(config["input_root"], config["allowed_input_roots"])
        write_new(output / "isolation.json", {"mechanism": "dataset-separated-provider-execution",
            "evaluator_dataset_absent": True, "os_sandbox_claimed": False,
            "verified_by_parent_after_closed_failure": True})


def bootstrap(request):
    workflow = request.get("workflow", "dual-posttrain-v1")
    require(workflow in {"dual-posttrain-v1", "paired-ttt-stability-v1", "compact-matched-controls-v1", "compact-convergence-screen-v1"}, "known explicit workflow required")
    start = request["started_epoch"]
    require(type(start) in (int, float) and math.isfinite(start) and 0 < start <= time.time(), "actual pre-dispatch start required")
    require(request["session_deadline_epoch"] == start + 43200, "original 12-hour platform deadline required")
    require(request.get("evaluation_mode") == "external-cpu", "only evaluator-absent provider execution supported")
    offline.remaining(request)
    manifest = verify_source(request)
    variants = ("2b",) if workflow in {"compact-matched-controls-v1", "compact-convergence-screen-v1"} else ("2b", "4b")
    if workflow in {"compact-matched-controls-v1", "compact-convergence-screen-v1"}:
        require(manifest.get("workflow") == workflow
                and manifest.get("model_sources") == [model_pin("2b")["model_source"]],
                "matched source capsule must bind exact2B-only workflow")
    root = Path(request["working_root"])
    root.mkdir(parents=True, exist_ok=False)
    write_new(root / "request.json", request)
    references = {key: offline.REFERENCES[key] for key in ("wheels", "interpreter", "training")}
    references["public"] = request["solver_dataset"]
    require(references["public"] != offline.REFERENCES["public"], "distinct solver-only projection required")
    roots = {key: offline.resolve_dataset(request["input_root"], value) for key, value in references.items()}
    public = offline.solver_projection(roots["public"])
    verify_inventory(roots["training"], TRAINING_MANIFEST_SHA256)
    source_mount = offline.resolve_dataset(request["input_root"], request["source_dataset"])
    expected = {manifest["transport"]["filename"]} if "transport" in manifest else set(manifest["files"])
    offline.exact_files(source_mount, expected | {"source-manifest.json"}, optional=("dataset-metadata.json",))
    models, identities = {}, {}
    for variant in variants:
        models[variant], identities[variant] = resolve_model(request["input_root"], variant)
    allowed = [str(p) for p in roots.values()] + [str(source_mount)] + [str(p) for p in models.values()]
    check_dataset_separation(request["input_root"], allowed)
    runtime = Path(request.get("runtime_root", "/kaggle/temp/" + request["run_id"]))
    require(not runtime.is_relative_to(root), "ephemeral runtime must be outside retained outputs")
    runtime.mkdir(parents=True, exist_ok=False)
    python, environment, env = offline.install(request, roots, runtime)
    write_new(root / "model-receipt.json", identities)
    retained_env = {key: value for key, value in env.items() if key in ENV_KEYS}
    config = {"run_id": request["run_id"], "source_root": str(SOURCE), "output_root": str(root / "solver"),
        "started_epoch": start, "deadline_epoch": request["session_deadline_epoch"], "python": python,
        "runtime_env": retained_env, "model_roots": {key: str(value) for key, value in models.items()},
        "training_root": str(roots["training"] / "data/training"), "training_manifest_path": str(roots["training"] / "manifest.json"),
        "public_path": str(public / "public-challenges.json"), "input_root": request["input_root"],
        "allowed_input_roots": allowed, "source_identity": request["source_manifest_sha256"],
        "parameters": request.get("parameters", {}), "workflow": workflow}
    return protected_launch(config, root / "control", retained_env)


def require_completed_diagnostic(request, terminal):
    """Fail the notebook only AFTER owned closure and evidence preservation.

    A successful Python coordinator exit is not a successful scientific screen.
    Dual-specialist runs still use their separate sealed external-evaluation
    contract; this check concerns only the explicitly diagnostic workflows.
    """
    if request.get("workflow") in {"paired-ttt-stability-v1", "compact-matched-controls-v1", "compact-convergence-screen-v1"}:
        if not isinstance(terminal, dict) or terminal.get("completed") is not True:
            raise RuntimeError("scientific diagnostic incomplete; closed private evidence retained; no successful comparison")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request")
    parser.add_argument("--controller")
    args = parser.parse_args()
    if args.controller:
        config = json.loads(regular(args.controller).read_bytes())
        if config.get("workflow") == "compact-convergence-screen-v1":
            from tools.nvarc_posttrain_20261017.convergence_controller import run
        elif config.get("workflow") == "compact-matched-controls-v1":
            from tools.nvarc_posttrain_20261017.matched_controller import run
        elif config.get("workflow") == "paired-ttt-stability-v1":
            from tools.nvarc_posttrain_20261017.stability_controller import run
        else:
            require(config.get("workflow", "dual-posttrain-v1") == "dual-posttrain-v1", "unknown workflow")
            from tools.nvarc_posttrain_20261017.controller import run
        run(config)
        return
    request = json.loads(regular(args.request).read_bytes())
    try:
        terminal = bootstrap(request)
        require_completed_diagnostic(request, terminal)
    finally:
        offline.preserve_runtime_evidence(request)


if __name__ == "__main__":
    main()
