"""Build the inert export-only M2 continuation and verify retained training evidence."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
from tools import irisx_build_backend as build
from tools.stage_nvarc_m2_fsdp_sft import MODEL
from tools.verify_nvarc_m2_fsdp_sft import verify_training_export
from irisx.arc_nvarc_source_bundle import build_bundle
from irisx.arc_nvarc_source_continuation import RUN, EXPORT, TRAINING, validate_plan
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError

TRIAL = ROOT / "trials/arc-agi-2-qwen35-nvarc"
LOCAL = ROOT / ".irisx/arc-agi-2/qwen35-nvarc"
RETRIEVED = LOCAL / "m2-m3/fsdp-sft-retrieved-002"


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stage(output: Path) -> dict:
    if output.exists():
        raise ValidationError("new continuation package directory required")
    run = RETRIEVED / "nvarc-m2-fsdp-sft-002"
    checked = verify_training_export(RETRIEVED / "plan.json", MODEL,
                                     RETRIEVED / "sequences.jsonl", run)
    if checked["identity"] != TRAINING or checked["export_chain"]["export_material_digest"] != EXPORT:
        raise ValidationError("retained training identity differs")
    plan = json.loads((TRIAL / "configs/m2-source-cont-draft-001.json").read_bytes())
    validate_plan(plan, approved=False)
    binding = build_bundle(LOCAL / "source", TRIAL / "source-manifest.json", output / "source-bundle")
    plan["source_bundle_digest"] = binding["bundle_digest"]
    evidence = {"format": "irisx/nvarc-m2-retained-training-export-v1",
                "training_identity_digest": TRAINING, "export_material_digest": EXPORT,
                "optimizer_steps": checked["final"]["step"], "tokens_seen": checked["final"]["tokens_seen"],
                "model_forwards": checked["final"]["forwards"], "optimizer_checkpoint_retained": False,
                "checkpoint_manifest_digest": checked["final"]["checkpoint"]["manifest_digest"],
                "contains_evaluator_truth": False,
                "claim": "retained SFT/export only; source solve incomplete",
                "files": {name: sha((run / name).read_bytes()) for name in
                          ("pause-result.json", "final-result.json", "export-chain.json",
                           "first-checkpoint-manifest.json", "final-checkpoint-manifest.json",
                           "resume-evicted.json", *(f"rank-{rank}-trace.jsonl" for rank in range(4)))}}
    payloads = {"source_config": (RETRIEVED / "source-config.json").read_bytes(),
                "visible": (RETRIEVED / "visible.json").read_bytes(),
                "training_evidence": canonical_bytes(evidence, newline=True),
                "wheel_manifest": (TRIAL / "configs/base-wheel-manifest.json").read_bytes()}
    for name in ("source_config", "visible", "training_evidence"):
        plan[name + "_sha256"] = sha(payloads[name])
    payloads["plan"] = canonical_bytes(plan, newline=True)
    wheel = build.build_wheel(str(output / "wheel"))
    payloads["runtime_wheel"] = (output / "wheel" / wheel).read_bytes()
    files = {name: name.replace("_", "-") + ".json" for name in payloads}
    files["runtime_wheel"] = wheel
    for index, path in enumerate(sorted((output / "source-bundle").rglob("*"))):
        if path.is_file():
            key = "bundle_" + str(index)
            payloads[key] = path.read_bytes()
            files[key] = "source-bundle/" + path.relative_to(output / "source-bundle").as_posix()
    for name in ("plan", "visible", "source_config", "training_evidence", "wheel_manifest"):
        (output / files[name]).write_bytes(payloads[name])
    # A separate local copy is ready for a future private upload. No provider calls.
    dataset = output / "model-dataset"
    shutil.copytree(run / "export", dataset / "export")
    (dataset / "training-evidence.json").write_bytes(payloads["training_evidence"])
    (dataset / "dataset-metadata.json").write_bytes(canonical_bytes({
        "title": "IRIS-X NVARC M2 SFT export 002", "id": plan["model_dataset_id"],
        "licenses": [{"name": "other"}]}, newline=True))
    hashes = {name: sha(value) for name, value in payloads.items()}
    template = (ROOT / "tools/nvarc_source_continuation_notebook.py.tmpl").read_text()
    source = template.replace("__PAYLOADS__", repr({name: base64.b64encode(value).decode()
                                                   for name, value in payloads.items()}))
    source = source.replace("__HASHES__", repr(hashes)).replace("__FILES__", repr(files))
    compile(source, "continuation-notebook", "exec")
    kernel = output / "kernel"
    kernel.mkdir()
    notebook = {"cells": [{"cell_type": "code", "execution_count": None, "metadata": {},
                            "outputs": [], "source": source.splitlines(keepends=True)}],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 5}
    (kernel / "kaggle-notebook.ipynb").write_bytes(canonical_bytes(notebook, newline=True))
    metadata = {"id": plan["kernel_id"], "title": RUN, "code_file": "kaggle-notebook.ipynb",
                "language": "python", "kernel_type": "notebook", "is_private": True,
                "enable_gpu": True, "enable_tpu": False, "enable_internet": False,
                "machine_shape": "NvidiaL4", "competition_sources": ["arc-prize-2026-arc-agi-2"],
                "dataset_sources": [plan["model_dataset_id"], plan["wheel_dataset_id"]],
                "kernel_sources": [], "model_sources": []}
    (kernel / "kernel-metadata.json").write_bytes(canonical_bytes(metadata, newline=True))
    summary = {"format": "irisx/nvarc-m2-source-continuation-stage-v1", "approved": False,
               "run_id": RUN, "plan_digest": digest_value(plan), "payload_sha256": hashes,
               "source_bundle_digest": binding["bundle_digest"], "export_material_digest": EXPORT,
               "notebook_sha256": sha((kernel / "kaggle-notebook.ipynb").read_bytes()),
               "metadata_sha256": sha((kernel / "kernel-metadata.json").read_bytes()), "external_calls": 0}
    (output / "stage-summary.json").write_bytes(canonical_bytes(summary, newline=True))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(stage(parser.parse_args().output), indent=2))
