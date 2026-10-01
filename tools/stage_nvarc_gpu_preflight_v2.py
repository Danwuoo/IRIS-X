"""Prepare and audit the distinct owner-approved Kaggle resource probe offline."""

from __future__ import annotations

import argparse
import ast
import base64
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools import irisx_build_backend as build
from irisx.arc_nvarc_original_corpus import OriginalCorpusStore, parent_metadata, synthetic_index
from irisx.arc_nvarc_datasets import SOURCES, sha_file
from irisx.arc_nvarc_gpu_preflight_v2 import RUN, BASE, CORPUS_SHA, RECIPE, MEMORY_POLICY, check_plan
from irisx.arc_nvarc_representation import GridTokenizer
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError

CORPUS = ROOT / ".irisx/nvarc-original/materials/corpus-20261001-001"
TRIAL = ROOT / "trials/arc-agi-2-qwen35-nvarc"


def select_samples(corpus: Path = CORPUS) -> list[dict]:
    store = OriginalCorpusStore(corpus, expected_manifest_sha256=CORPUS_SHA, purpose="qwen35-port")
    catalog = json.loads((corpus / "catalog.json").read_bytes())
    index = synthetic_index(json.loads((corpus / "synthetic-inventory.json").read_bytes()))
    schedule = [(s, 0) for s in SOURCES[:4]] + [
        (s, store.manifest["sources"][s]["longest_source_row"])
        for s in ("arc2_training", "rearc", "nvarc_training", "nvarc_full")]
    tokenizer, result = GridTokenizer(source_chat_newlines=True), []
    for source, row_index in schedule:
        row = store.source(source)[row_index]
        ids, labels = [], []
        for i in range(0, len(row["messages"]), 2):
            grids = [[[int(c) for c in line] for line in item["content"].split("\n")]
                     for item in row["messages"][i:i + 2]]
            t, l = tokenizer.encode_pair(*grids)
            ids.extend(t)
            labels.extend(l)
        parents, tags = parent_metadata(source, row["puzzle_name"], catalog, index)
        result.append({"source_id": source, "source_row": row_index, "puzzle_name": row["puzzle_name"],
            "parent_ids": parents, "exposure_tags": tags, "input_ids": ids, "labels": labels})
    return result


def stage(output: Path) -> dict:
    if output.exists():
        raise ValidationError("new GPU preflight package required")
    samples = select_samples()
    plan = {"format": "irisx/nvarc-q35-gpu-preflight-v2", "approved": True, "owner_decision": "Decision 0052",
        "run_id": RUN, "kernel_id": "danielwuu/" + RUN, "backend": "cuda-l4", "world_size": 4,
        "packing": False, "packing_gap": "NeMo source packing and Qwen3.5 DeltaNet state isolation not verified",
        "source_recipe": RECIPE, "memory_policy": MEMORY_POLICY,
        "base_material_digest": BASE, "corpus_manifest_sha256": CORPUS_SHA,
        "sample_digest": digest_value(samples), "maximum_optimizer_steps": 2, "checkpoint_steps": [1, 2],
        "scheduled_input_tokens": sum(len(r["input_ids"]) for r in samples), "maximum_training_tokens": 89568,
        "maximum_sequence_length": 11196, "seed": 24, "maximum_generations": 0, "maximum_teacher_calls": 0,
        "maximum_paid_usd": 0, "maximum_notebook_wall_seconds": 2700, "terminal_reserve_seconds": 120,
        "minimum_free_scratch_bytes": 55000000000, "minimum_host_available_bytes": 80000000000,
        "datasets": {"base": "danielwuu/irisx-nvarc-m2-compact-4b-001",
                     "wheels": "danielwuu/irisx-arc-agi-2-trial-002-smoke-001"},
        "competition_sources": ["arc-prize-2026-arc-agi-2"],
        "competition_mount_policy": "mount for prior four-L4 transport; never open competition files",
        "model_identity": "verified Qwen3.5 compact port; original Qwen3/NeMo parity unclaimed",
        "material_policy": "original-reproduction with all exposure retained",
        "full_sft_completed": False, "execution_control": "SAVE_AND_RUN_ALL; agent monitor and one retrieval"}
    check_plan(plan, samples, 4)
    wheel_dir = output / "wheel"
    wheel_dir.mkdir(parents=True)
    wheel = wheel_dir / build.build_wheel(str(wheel_dir))
    payloads = {"plan": canonical_bytes(plan, newline=True), "samples": canonical_bytes(samples, newline=True),
        "wheel_manifest": (TRIAL / "configs/base-wheel-manifest.json").read_bytes(), "runtime_wheel": wheel.read_bytes()}
    import hashlib
    hashes = {k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()}
    for name in ("plan", "samples"):
        (output / (name + ".json")).write_bytes(payloads[name])
    source = (ROOT / "tools/nvarc_gpu_preflight_v2_notebook.py.tmpl").read_text(encoding="utf-8")
    source = source.replace("__PAYLOADS__", json.dumps({k: base64.b64encode(v).decode() for k,v in payloads.items()}))
    source = source.replace("__HASHES__", json.dumps(hashes, sort_keys=True))
    source = source.replace("__HARDWARE_HELPER__", (ROOT / "src/irisx/arc_nvarc_hardware.py").read_text(encoding="utf-8"))
    compile(source, "gpu-preflight-notebook", "exec")
    notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": {"kernelspec": {
        "display_name": "Python 3", "language": "python", "name": "python3"}}, "cells": [{
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": source.splitlines(keepends=True)}]}
    kernel = output / "kernel"
    kernel.mkdir()
    (kernel / "notebook.ipynb").write_bytes(canonical_bytes(notebook, newline=True))
    meta = {"id": plan["kernel_id"], "title": RUN, "code_file": "notebook.ipynb", "language": "python",
        "kernel_type": "notebook", "is_private": True, "enable_gpu": True, "enable_tpu": False,
        "enable_internet": False, "machine_shape": "NvidiaL4", "dataset_sources": list(plan["datasets"].values()),
        "competition_sources": plan["competition_sources"], "kernel_sources": [], "model_sources": []}
    (kernel / "kernel-metadata.json").write_bytes(canonical_bytes(meta, newline=True))
    summary = {"format": "irisx/nvarc-gpu-preflight-stage-v1", "run_id": RUN, "plan_digest": digest_value(plan),
        "payload_sha256": hashes, "inventory": {p.relative_to(output).as_posix(): sha_file(p)
                for p in sorted(output.rglob("*")) if p.is_file()}, "external_calls": 0}
    (output / "stage-summary.json").write_bytes(canonical_bytes(summary, newline=True))
    return summary


def preflight(output: Path) -> dict:
    import hashlib
    summary = json.loads((output / "stage-summary.json").read_bytes())
    actual = {p.relative_to(output).as_posix(): sha_file(p) for p in output.rglob("*") if p.is_file() and p.name != "stage-summary.json"}
    if actual != summary["inventory"]:
        raise ValidationError("GPU package closed inventory differs")
    notebook = json.loads((output / "kernel/notebook.ipynb").read_bytes())
    source = "".join(notebook["cells"][0]["source"])
    values = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"PAYLOADS", "HASHES"}:
            values[node.targets[0].id] = ast.literal_eval(node.value)
    decoded = {k: base64.b64decode(v, validate=True) for k,v in values["PAYLOADS"].items()}
    expected = (ROOT / "tools/nvarc_gpu_preflight_v2_notebook.py.tmpl").read_text(encoding="utf-8")
    expected = expected.replace("__PAYLOADS__", json.dumps(values["PAYLOADS"]))
    expected = expected.replace("__HASHES__", json.dumps(values["HASHES"], sort_keys=True))
    expected = expected.replace("__HARDWARE_HELPER__", (ROOT / "src/irisx/arc_nvarc_hardware.py").read_text(encoding="utf-8"))
    if source != expected:
        raise ValidationError("second GPU notebook differs from reviewed repair template")
    if {k:hashlib.sha256(v).hexdigest() for k,v in decoded.items()} != values["HASHES"] or values["HASHES"] != summary["payload_sha256"]:
        raise ValidationError("GPU notebook payload differs")
    plan, rows = json.loads(decoded["plan"]), json.loads(decoded["samples"])
    identity = check_plan(plan, rows, 4)
    if decoded["plan"] != (output / "plan.json").read_bytes() or decoded["samples"] != (output / "samples.json").read_bytes():
        raise ValidationError("GPU reviewed plan/samples differ")
    if set(r["source_id"] for r in rows) != set(SOURCES) or max(len(r["input_ids"]) for r in rows) != 11196:
        raise ValidationError("GPU original source/longest coverage differs")
    for row, expected in zip(rows[4:], (9330, 11170, 11196, 11196)):
        if len(row["input_ids"]) != expected:
            raise ValidationError("GPU heavy source whole maximum differs")
    wheel = next((output / "wheel").glob("*.whl"))
    if wheel.read_bytes() != decoded["runtime_wheel"]:
        raise ValidationError("GPU runtime wheel differs")
    with zipfile.ZipFile(wheel) as archive:
        if archive.read("irisx/arc_nvarc_gpu_preflight_v2.py") != (ROOT / "src/irisx/arc_nvarc_gpu_preflight_v2.py").read_bytes():
            raise ValidationError("GPU wheel runtime source differs")
    from irisx.arc_nvarc_fsdp_sft import _verify_compact_base
    _verify_compact_base(ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/fsdp-approved-003/model-dataset", BASE)
    meta = json.loads((output / "kernel/kernel-metadata.json").read_bytes())
    if (meta["id"] != plan["kernel_id"] or meta["is_private"] is not True or meta["enable_internet"] is not False or
            meta["machine_shape"] != "NvidiaL4" or meta["dataset_sources"] != list(plan["datasets"].values()) or
            meta["competition_sources"] != ["arc-prize-2026-arc-agi-2"]):
        raise ValidationError("GPU Kaggle request metadata differs")
    return {"run_id": RUN, "plan_digest": digest_value(plan), "identity_digest": identity,
        "scheduled_input_tokens": plan["scheduled_input_tokens"], "maximum_sequence_length": 11196,
        "sources": sorted(set(r["source_id"] for r in rows)), "offline_package_verified": True,
        "runtime_verified": False,
        "maximum_optimizer_steps": 2, "maximum_paid_usd": 0, "external_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("stage", "preflight"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.output) if args.action == "stage" else preflight(args.output), indent=2))
