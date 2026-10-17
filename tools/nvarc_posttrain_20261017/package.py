"""Local-only exact source capsule and private notebook draft construction.

Does not upload, publish, run, authenticate or modify any remote object. The
checkpoint files remain official model mounts, not duplicated in this payload.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import time

from tools.arc2_goal_sprint_20261017 import package as predecessor
from tools.arc2_goal_sprint_20261017.bootstrap import REFERENCES
from tools.arc2_goal_sprint_20261017.launch import SCORER_SHA256, regular, require, sha, write_new
from .materials import model_pin

ROOT = Path(__file__).resolve().parents[2]
ENTRIES = ("tools.nvarc_posttrain_20261017.bootstrap", "tools.nvarc_posttrain_20261017.controller",
    "tools.nvarc_posttrain_20261017.worker", "tools.nvarc_posttrain_20261017.score",
    "tools.nvarc_posttrain_20261017.package", "tools.arc_offline_evaluation",
    "tools.arc_learning_agent_20261011.process_guard", "irisx.artifacts", "irisx.arc_agi2")


def build_source(root, destination, extra_wheelhouse, run_id):
    from tools.arc2_agent_factory3_bridge_20261014.provenance import verify_vendor
    verify_vendor()
    root, destination = Path(root), Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    paths = predecessor.source_paths(root, entry_modules=ENTRIES)
    paths.append(regular(root / "tools/nvarc_posttrain_20261017/model-pins.json"))
    for path in paths:
        target = destination / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(regular(path), target)
    extra = destination / "extra-wheels"
    extra.mkdir()
    lock = predecessor.wheel_lock(extra_wheelhouse)
    for name in lock["files"]:
        shutil.copyfile(regular(Path(extra_wheelhouse) / name), extra / name)
    write_new(extra / "extra-wheel-lock.json", lock)
    for name in ("tools/__init__.py", "src/__init__.py", "tools/nvarc_posttrain_20261017/__init__.py"):
        target = destination / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('"""Packaged IRIS-X runtime namespace."""\n', encoding="utf-8")
    files = {path.relative_to(destination).as_posix(): {"bytes": path.stat().st_size, "sha256": sha(regular(path))}
             for path in sorted(destination.rglob("*")) if path.is_file()}
    require(files["tools/arc_offline_evaluation.py"]["sha256"] == SCORER_SHA256, "original scorer changed")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    changed = subprocess.run(["git", "status", "--porcelain", "--", *[str(p.relative_to(root)) for p in paths]],
                             cwd=root, check=True, capture_output=True, text=True).stdout
    manifest = {"format": "irisx/nvarc-source-manifest-v1", "run_id": run_id, "files": files,
        "source_git_commit": revision, "source_git_worktree_clean_for_packaged_files": not bool(changed.strip()),
        "contains_evaluator_data": False, "contains_model_weights": False, "official_submission": False,
        "model_sources": [model_pin(v)["model_source"] for v in ("2b", "4b")],
        "measurement": "inherited-exposure-qualified PUBLIC development", "clean_generalization_claimed": False}
    return write_new(destination / "source-manifest.json", manifest)


def loader(request):
    text = predecessor.notebook_source(request)
    old = "tools/arc2_goal_sprint_20261017/bootstrap.py"
    require(text.count(old) == 1, "reviewed loader entrypoint changed")
    return text.replace(old, "tools/nvarc_posttrain_20261017/bootstrap.py")


def build_notebook(destination, *, run_id, source_dataset, solver_dataset, source_manifest_sha256,
                   source_payload_sha256, started_epoch, parameters=None):
    require(re.fullmatch(r"[a-z0-9][a-z0-9-]{3,95}", run_id), "fresh portable run identity required")
    require(re.fullmatch(r"danielwuu/[a-z0-9][a-z0-9-]+/[1-9][0-9]*", source_dataset or ""), "pinned private source Dataset required")
    require(re.fullmatch(r"danielwuu/[a-z0-9][a-z0-9-]+/[1-9][0-9]*", solver_dataset or "")
        and solver_dataset != REFERENCES["public"], "pinned distinct solver-only Dataset required")
    require(all(re.fullmatch(r"[a-f0-9]{64}", value or "") for value in (source_manifest_sha256, source_payload_sha256)),
        "exact immutable source/payload pins required")
    require(type(started_epoch) in (int, float) and math.isfinite(started_epoch) and 0 < started_epoch <= time.time(),
        "actual fresh pre-dispatch clock required")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    request = {"run_id": run_id, "source_dataset": source_dataset, "solver_dataset": solver_dataset,
        "source_manifest_sha256": source_manifest_sha256, "source_payload_sha256": source_payload_sha256,
        "evaluation_mode": "external-cpu", "input_root": "/kaggle/input", "working_root": "/kaggle/working/" + run_id,
        "runtime_root": "/kaggle/temp/" + run_id, "started_epoch": started_epoch,
        "session_deadline_epoch": started_epoch + 43200, "parameters": parameters or {}}
    filename = "iris-x-nvarc-dual-posttrain.ipynb"
    write_new(destination / filename, predecessor.notebook([loader(request)], run_id))
    metadata = {"id": "danielwuu/iris-x-nvarc-dual-posttrain-20261017", "title": "IRIS-X NVARC dual posttraining 20261017",
        "code_file": filename, "language": "python", "kernel_type": "notebook", "is_private": True,
        "enable_gpu": True, "enable_tpu": False, "enable_internet": False, "machine_shape": "NvidiaRtxPro6000",
        "dataset_sources": [REFERENCES[k] for k in ("wheels", "interpreter", "training")] + [solver_dataset, source_dataset],
        "model_sources": [model_pin(v)["model_source"] for v in ("2b", "4b")], "competition_sources": [], "kernel_sources": []}
    write_new(destination / "kernel-metadata.json", metadata)
    write_new(destination / "dispatch-request.json", request)
    return {"published": False, "run_launched": False, "notebook_id": metadata["id"],
        "source_manifest_sha256": source_manifest_sha256, "source_payload_sha256": source_payload_sha256}


def build_capsule(destination, *, run_id, source_dataset, extra_wheelhouse, root=ROOT):
    require(re.fullmatch(r"danielwuu/[a-z0-9][a-z0-9-]+/1", source_dataset), "fresh private source version 1 required")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    review, transport = destination / "source-review", destination / "source-dataset"
    build_source(root, review, extra_wheelhouse, run_id)
    manifest_sha = predecessor.source_transport(review, transport)
    manifest = json.loads((transport / "source-manifest.json").read_bytes())
    write_new(transport / "dataset-metadata.json", {"id": source_dataset.rsplit("/", 1)[0],
        "title": run_id, "licenses": [{"name": "Apache 2.0"}], "isPrivate": True})
    result = {"format": "irisx/nvarc-local-capsule-v1", "run_id": run_id, "source_dataset": source_dataset,
        "source_manifest_sha256": manifest_sha, "source_payload_sha256": manifest["transport"]["sha256"],
        "source_files": len(manifest["files"]), "published": False, "run_launched": False}
    write_new(destination / "local-capsule.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-dataset", required=True)
    parser.add_argument("--extra-wheelhouse", required=True)
    args = parser.parse_args()
    print(json.dumps(build_capsule(args.output, run_id=args.run_id, source_dataset=args.source_dataset,
                                 extra_wheelhouse=args.extra_wheelhouse), sort_keys=True))


if __name__ == "__main__": main()
