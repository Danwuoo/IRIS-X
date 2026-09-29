"""Build and audit the distinct Decision 0047 owner-Editor QUICK_SAVE package."""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools import irisx_build_backend as build
from tools.stage_nvarc_combined import LOCAL, TRIAL, WHEEL_MANIFEST_SHA
from irisx.arc_nvarc_abc_004 import ARMS, BASE, SFT, TASKS, TRAINING, VOCAB, check_materials
from irisx.arc_nvarc_combined import atomic, read, require, sha
from irisx.arc_nvarc_data import visible_task
from irisx.arc_nvarc_source_bundle import build_bundle, verify_bundle
from irisx.canonical import canonical_bytes, digest_value

RUN = "nvarc-compact-abc-editor-004"
PLAN = TRIAL / "configs/compact-abc-editor-004.json"
TEMPLATE = ROOT / "tools/nvarc_abc_notebook_004.py.tmpl"
BASE_ROOT = LOCAL / "m2-m3/fsdp-approved-003/model-dataset"
SFT_ROOT = LOCAL / "m2-m3/source-cont-approved-002/model-dataset"
SOURCE = LOCAL / "source/NVARC/external/TinyRecursiveModels/kaggle/combined/arc-agi_training2_challenges.json"
EVIDENCE = LOCAL / "m2-m3/combined-editor-009-final/training-evidence.json"
SMALL = TRIAL / "configs/m2-m3-small.json"
SFT_PLAN = LOCAL / "m2-m3/fsdp-sft-retrieved-002/plan.json"
SFT_RESULT = LOCAL / "m2-m3/fsdp-sft-retrieved-002/nvarc-m2-fsdp-sft-002/final-result.json"
WHEEL_MANIFEST = TRIAL / "configs/base-wheel-manifest.json"


def visible_bytes():
    source = read(SOURCE)
    chosen = {key: visible_task(key, source[key]) for key in TASKS}
    return canonical_bytes({key: {"train": item["train"], "test": item["test"]}
                            for key, item in chosen.items()}, newline=True)


def make_plan():
    small = read(SMALL)
    train = [item["id"] for item in small["train"]]
    dev = [item["id"] for item in small["dev"]]
    require(not set(TASKS) & set(train) and set(TASKS) <= set(dev), "ABC public parent split differs")
    retained_sft = read(SFT_PLAN)
    retained_result = read(SFT_RESULT)
    require(retained_sft["run_id"] == "nvarc-m2-fsdp-sft-002" and
            retained_sft["compact_material_digest"] == BASE and
            retained_sft["scheduled_parent_ids"] == sorted(train) and
            retained_sft["maximum_optimizer_steps"] == 8 and
            retained_sft["scheduled_training_tokens"] == 2578 and
            retained_sft["sequences_digest"] == retained_result["sequences_digest"] and
            retained_result["identity_digest"] == TRAINING and
            retained_result["step"] == 8 and retained_result["tokens_seen"] == 2578,
            "ABC retained SFT training plan differs")
    return {"format": "irisx/nvarc-compact-abc-editor-v1", "approved": True,
        "owner_decision": "Decision 0047", "run_id": RUN, "kernel_id": "danielwuu/" + RUN,
        "execution_control": {"agent_start": False, "owner_editor_start": True, "save_type": "QUICK_SAVE"},
        "external_allowances": {"submissions": 1, "queries": 0, "retrievals": 0, "dataset_mutations": 0},
        "datasets": {"base": "danielwuu/irisx-nvarc-m2-compact-4b-001",
                     "sft": "danielwuu/irisx-nvarc-m2-sft-export-002",
                     "wheels": "danielwuu/irisx-arc-agi-2-trial-002-smoke-001"},
        "model": {"base_material_digest": BASE, "sft_export_material_digest": SFT,
                  "training_identity_digest": TRAINING, "vocabulary_identity_digest": VOCAB,
                  "sft_label": "8-step SFT pilot; 2578 observed training tokens",
                  "source_grammar": "source-qwen role/newline/EOS for all arms",
                  "precision": "bfloat16"},
        "arms": [{"id": "A", "checkpoint": "base", "ttt_steps_per_task": 0},
                 {"id": "B", "checkpoint": "sft", "ttt_steps_per_task": 0},
                 {"id": "C", "checkpoint": "sft", "ttt_steps_per_task": 1,
                  "adaptation_override": {"steps": 1, "learning_rate": 0.00005}}],
        "actual_execution_policy": "A then B then C sequentially on one selected L4; verify four distinct L4s; unload between arms",
        "hardware_profile": "four-distinct-bf16-l4-verified/one-active-worker-v1",
        "competition_mount": "/kaggle/input/competitions/arc-prize-2026-arc-agi-2",
        "predecessor_result_sha256": "195c7c4df43c53efb07d12af47d8f870f8723d968c61c5308e5fc5a2846fa68c",
        "tuning_policy": "vary only legal candidate search; fixed model, TTT, grammar, views, generation and ranking",
        "candidate_search": "model-log-probability legal beam width 2 at every output position; cumulative score without renormalization",
        "task_ids": list(TASKS), "sft_train_parent_ids": train,
        "sft_training_plan_sha256": sha(SFT_PLAN),
        "sft_sequences_digest": retained_sft["sequences_digest"],
        "sft_source_data_manifest_digest": retained_sft["source_data_manifest_digest"],
        "exploratory_previously_run_ids": ["00576224"],
        "parent_overlap": "exact IDs disjoint; semantic near duplicates unknown",
        "visible_sha256": sha_bytes(visible_bytes()), "source_file_sha256": sha(SOURCE),
        "training_evidence_sha256": sha(EVIDENCE),
        "source_bundle_digest": "sha256:625b010706dabfce5df58c036f5921af4e782da133bd27038bc442abdc79e1a4",
        "wheel_manifest_sha256": WHEEL_MANIFEST_SHA,
        "limits": {"model_seed": 42, "view_seed": 2, "views_per_task": 2,
                   "calls_per_task": 2, "returned_sequences_per_call": 2,
                   "new_tokens_per_sequence": 64, "expansions_per_call": 128,
                   "expansions_per_task": 256, "verifications_per_task": 4,
                   "verification_views_per_candidate": 8,
                   "maximum_total_generation_calls": 18,
                   "maximum_total_returned_sequences": 36,
                   "maximum_total_generation_forwards": 2304,
                   "maximum_total_verification_calls": 36,
                   "maximum_total_verification_forwards": 288,
                   "maximum_total_ttt_steps": 3,
                   "maximum_total_ttt_training_tokens": 768,
                   "maximum_sft_steps": 0, "maximum_teacher_calls": 0},
        "adaptation": {"seed": 42, "rank": 2, "alpha": 4, "learning_rate": 0.00005,
                       "steps": 1, "max_sequence_length": 256, "augmentation_count": 1,
                       "source_augmentation_seed": 1, "source_qwen": True},
        "maximum_setup_seconds": 300, "maximum_notebook_wall_seconds": 1800,
        "terminal_reserve_seconds": 60, "maximum_paid_usd": 0,
        "analysis_zip": "結果.zip", "analysis_zip_maximum_bytes": 64 * 1024 * 1024,
        "evaluator_truth": "excluded from notebook; exact correctness unknown until isolated local scoring"}


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def validate_plan(plan):
    require(plan == make_plan() and PLAN.read_bytes() == canonical_bytes(plan, newline=True),
            "exact Decision 0047 plan required")


def metadata(plan):
    return {"id": plan["kernel_id"], "title": plan["run_id"],
            "code_file": "kaggle-notebook.ipynb", "language": "python", "kernel_type": "notebook",
            "is_private": True, "enable_gpu": True, "enable_tpu": False, "enable_internet": False,
            "machine_shape": "NvidiaL4", "competition_sources": ["arc-prize-2026-arc-agi-2"],
            "dataset_sources": list(plan["datasets"].values()),
            "kernel_sources": [], "model_sources": []}


def render(payloads, files, plan_digest):
    source = TEMPLATE.read_text(encoding="utf-8")
    source = source.replace("__HARDWARE_HELPER__", (ROOT / "src/irisx/arc_nvarc_hardware.py").read_text(encoding="utf-8"))
    zip_source = (ROOT / "src/irisx/arc_nvarc_analysis_zip_abc.py").read_text(encoding="utf-8")
    source = source.replace("__ZIP_HELPER__", zip_source.replace("from __future__ import annotations\n", ""))
    source = source.replace("__PLAN_DIGEST__", repr(plan_digest))
    for key, value in {"PAYLOADS": {k: base64.b64encode(v).decode() for k, v in payloads.items()},
                       "HASHES": {k: sha_bytes(v) for k, v in payloads.items()}, "FILES": files}.items():
        source = source.replace("__" + key + "__", repr(value))
    compile(source, "owner-editor-abc", "exec")
    return source


def stage(output):
    require(not output.exists(), "new ABC package directory required")
    plan = read(PLAN)
    validate_plan(plan)
    check_materials(BASE_ROOT, SFT_ROOT)
    require(sha(EVIDENCE) == plan["training_evidence_sha256"] and
            read(EVIDENCE)["optimizer_steps"] == 8 and read(EVIDENCE)["tokens_seen"] == 2578,
            "retained eight-step SFT evidence differs")
    require(sha(WHEEL_MANIFEST) == WHEEL_MANIFEST_SHA, "offline wheel manifest differs")
    output.mkdir(parents=True)
    bundle = build_bundle(LOCAL / "source", TRIAL / "source-manifest.json", output / "source-bundle")
    require(bundle["bundle_digest"] == plan["source_bundle_digest"], "ABC source bundle differs")
    wheel_name = build.build_wheel(str(output / "wheel"))
    payloads = {"plan": PLAN.read_bytes(), "visible": visible_bytes(),
                "training_evidence": EVIDENCE.read_bytes(),
                "wheel_manifest": WHEEL_MANIFEST.read_bytes(),
                "runtime_wheel": (output / "wheel" / wheel_name).read_bytes()}
    files = {"plan": "plan.json", "visible": "visible.json",
             "training_evidence": "training-evidence.json", "wheel_manifest": "wheel-manifest.json",
             "runtime_wheel": "wheel/" + wheel_name}
    for path in sorted((output / "source-bundle").rglob("*")):
        if path.is_file():
            key = "bundle_" + str(len(payloads))
            payloads[key] = path.read_bytes()
            files[key] = path.relative_to(output).as_posix()
    for key, value in payloads.items():
        path = output / files[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    source = render(payloads, files, digest_value(plan))
    notebook = {"cells": [
        {"cell_type": "markdown", "metadata": {}, "source": [
            "# IRIS-X compact base / 8-step SFT / task TTT with two-path model beam\n",
            "Saved with QUICK_SAVE. Start manually in Kaggle Editor with L4 x4 and Internet off.\n",
            "Mount the competition at `/kaggle/input/competitions/arc-prize-2026-arc-agi-2`. A, B and C run in order on one GPU; all four GPUs are checked. Three public tuning parents are fixed; 00576224 was explored in combined 009.\n",
            "Download **結果.zip** from `/kaggle/working` and send it back for separate analysis. No hidden-answer scoring runs here.\n",
            "Partial failures are retained where Python finally can execute; a hard session kill may prevent packaging.\n"]},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
         "source": source.splitlines(keepends=True)}],
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
        "nbformat": 4, "nbformat_minor": 5}
    atomic(output / "kernel/kaggle-notebook.ipynb", notebook)
    atomic(output / "kernel/kernel-metadata.json", metadata(plan))
    atomic(output / "material-references.json", {"base_dataset": plan["datasets"]["base"],
        "sft_dataset": plan["datasets"]["sft"], "base_material_digest": BASE,
        "sft_material_digest": SFT, "vocabulary_identity_digest": VOCAB,
        "training_identity_digest": TRAINING, "source_file_sha256": plan["source_file_sha256"]})
    summary = {"format": "irisx/nvarc-abc-stage-v1", "run_id": RUN,
               "plan_digest": digest_value(plan), "external_calls": 0,
               "inventory": {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob("*"))
                             if p.is_file() and p.name != "stage-summary.json"}}
    atomic(output / "stage-summary.json", summary)
    return summary


def preflight(package):
    plan = read(package / "plan.json")
    validate_plan(plan)
    summary = read(package / "stage-summary.json")
    require(summary["plan_digest"] == digest_value(plan) and summary["external_calls"] == 0 and
            {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()} ==
            set(summary["inventory"]) | {"stage-summary.json"}, "ABC closed inventory differs")
    for name, digest in summary["inventory"].items():
        require(sha(package / name) == digest, "ABC package member differs: " + name)
    verify_bundle(package / "source-bundle", plan["source_bundle_digest"])
    check_materials(BASE_ROOT, SFT_ROOT)
    notebook = read(package / "kernel/kaggle-notebook.ipynb")
    source = "".join(notebook["cells"][1]["source"])
    tree = ast.parse(source)
    values = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign) and len(node.targets) == 1 and
              isinstance(node.targets[0], ast.Name) and node.targets[0].id in
              {"PAYLOADS", "HASHES", "FILES", "PLAN_DIGEST"}}
    payloads = {k: base64.b64decode(v, validate=True) for k, v in values["PAYLOADS"].items()}
    require(set(payloads) == set(values["HASHES"]) == set(values["FILES"]) and
            values["PLAN_DIGEST"] == digest_value(plan), "ABC notebook binding differs")
    for key, value in payloads.items():
        require(sha_bytes(value) == values["HASHES"][key] and
                (package / values["FILES"][key]).read_bytes() == value,
                "ABC embedded package bytes differ")
    require(source == render(payloads, values["FILES"], digest_value(plan)) and
            payloads["visible"] == visible_bytes() and
            read(package / "kernel/kernel-metadata.json") == metadata(plan),
            "ABC rendered notebook or metadata differs")
    with zipfile.ZipFile(package / values["FILES"]["runtime_wheel"]) as wheel:
        for path in (ROOT / "src/irisx").glob("*.py"):
            if path.name == "arc_nvarc_abc_005.py":
                continue  # Distinct 005 module was not part of frozen 004 wheel.
            require(wheel.read("irisx/" + path.name) == path.read_bytes(),
                    "ABC installed wheel source differs: " + path.name)
    require(not any(x in source for x in ("SAVE_AND_RUN_ALL", "GetKernel", "GetOutput", "solutions.json")),
            "ABC notebook contains forbidden transport or truth access")
    return {"run_id": RUN, "plan_digest": digest_value(plan), "external_calls": 0,
            "wheel_matches_source": True, "embedded_payloads": len(payloads),
            "exact_materials_verified": True, "quick_save_only": True}


def save_fields(package):
    preflight(package)
    meta = read(package / "kernel/kernel-metadata.json")
    notebook = read(package / "kernel/kaggle-notebook.ipynb")
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            require(cell["outputs"] == [] and cell["execution_count"] is None,
                    "ABC notebook was executed")
        if isinstance(cell.get("source"), list):
            cell["source"] = "".join(cell["source"])
    return {"slug": meta["id"], "new_title": meta["title"], "text": json.dumps(notebook),
            "language": "python", "kernel_type": "notebook", "is_private": True,
            "enable_gpu": True, "enable_tpu": False, "enable_internet": False,
            "machine_shape": "NvidiaL4", "session_timeout_seconds": 1800,
            "dataset_data_sources": meta["dataset_sources"],
            "competition_data_sources": meta["competition_sources"],
            "kernel_data_sources": [], "model_data_sources": [],
            "kernel_execution_type": "QUICK_SAVE"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-plan", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight", type=Path)
    args = parser.parse_args()
    if args.write_plan:
        require(not PLAN.exists(), "ABC plan already exists")
        PLAN.write_bytes(canonical_bytes(make_plan(), newline=True))
        print(digest_value(read(PLAN)))
    elif args.output:
        print(json.dumps(stage(args.output), indent=2))
    elif args.preflight:
        print(json.dumps(preflight(args.preflight), indent=2))
    else:
        parser.error("choose one action")

