"""Stage retained local inputs; default inert, exact Decision 0035 opt-in."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools import irisx_build_backend as build
from irisx.arc_nvarc_combined import RUN, activate_plan, atomic, read, require, sha, validate_plan
from irisx.arc_nvarc_source_bundle import build_bundle
from irisx.arc_nvarc_representation import verify_model_material
from irisx.arc_nvarc_source_continuation import EXPORT, TRAINING
from irisx.canonical import canonical_bytes, digest_value

TRIAL = ROOT / "trials/arc-agi-2-qwen35-nvarc"
LOCAL = ROOT / ".irisx/arc-agi-2/qwen35-nvarc"
DRAFT = TRIAL / "configs/m2-m3-combined-draft-001.json"
TEMPLATE = ROOT / "tools/nvarc_combined_notebook.py.tmpl"
APPROVED_TEMPLATE = ROOT / "tools/nvarc_combined_notebook_approved_001.py.tmpl"
M2 = LOCAL / "m2-m3/source-cont-approved-002"
M3 = LOCAL / "m2-m3/teacher-direct-approved-005"
EXPORT_ROOT = LOCAL / "m2-m3/fsdp-sft-retrieved-002/nvarc-m2-fsdp-sft-002/export"
TOKENIZER_ROOT = LOCAL / "teacher-tokenizer-851bf6e"
TOKENIZER_FILES = {"config.json", "tokenizer.json", "tokenizer_config.json",
                   "chat_template.jinja", "vocab.json", "merges.txt"}
WHEEL_MANIFEST_SHA = "f9106fe3d007d4b0963d12db6e7488a91b59e7824f8f0d192b4fcc45f8050887"


def references() -> dict:
    return {"format": "irisx/nvarc-combined-material-references-v1",
            "m2_export": {"path": EXPORT_ROOT.relative_to(ROOT).as_posix(), "material_digest": EXPORT,
                          "training_identity_digest": TRAINING},
            "m3_tokenizer": {"path": TOKENIZER_ROOT.relative_to(ROOT).as_posix(),
                             "model_manifest_digest": read(DRAFT)["branches"]["m3"]["teacher_model_manifest_digest"]},
            "m3_base_model": {"dataset_id": read(DRAFT)["branches"]["m3"]["source_dataset_id"],
                              "verification": "manifest-bound reference; full weights require future mount verification"}}


def verify_references(value: dict, model_manifest: dict) -> None:
    require(value == references(), "combined retained material references differ")
    material = verify_model_material(EXPORT_ROOT, EXPORT)
    require(material.get("training_identity_digest") == TRAINING, "retained export ancestry differs")
    entries = {entry["path"]: entry for entry in model_manifest["files"]}
    for name in TOKENIZER_FILES:
        path, entry = TOKENIZER_ROOT / name, entries[name]
        require(not path.is_symlink() and path.stat().st_size == entry["byte_size"] and
                "sha256:" + sha(path) == entry["content_digest"], "cached tokenizer binding differs: " + name)


def render(payloads: dict[str, bytes], files: dict[str, str], *, approved=False) -> str:
    import hashlib
    source = (APPROVED_TEMPLATE if approved else TEMPLATE).read_text(encoding="utf-8")
    bindings = {"PAYLOADS": {k: base64.b64encode(v).decode() for k, v in payloads.items()},
                "HASHES": {k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()}, "FILES": files}
    for name, value in bindings.items():
        source = source.replace("__" + name + "__", repr(value))
    compile(source, "combined-notebook", "exec")
    return source


def stage(output: Path, *, approved=False) -> dict:
    require(not output.exists(), "new combined review directory required")
    plan = read(DRAFT)
    validate_plan(plan)
    if approved:
        plan = activate_plan(plan)
    payloads = {"plan": canonical_bytes(plan, newline=True) if approved else DRAFT.read_bytes(),
                "source_config": (M2 / "source-config.json").read_bytes(),
                "visible": (M2 / "visible.json").read_bytes(),
                "training_evidence": (M2 / "training-evidence.json").read_bytes(),
                "seed": (M3 / "seed.json").read_bytes(), "prompts": (M3 / "prompts.json").read_bytes(),
                "model_manifest": (TRIAL / "configs/base-model-manifest.json").read_bytes(),
                "wheel_manifest": (TRIAL / "configs/base-wheel-manifest.json").read_bytes()}
    verify_inputs(plan, payloads)
    refs = references()
    verify_references(refs, json.loads(payloads["model_manifest"]))
    bundle = build_bundle(LOCAL / "source", TRIAL / "source-manifest.json", output / "source-bundle")
    require(bundle["bundle_digest"] == plan["branches"]["m2"]["source_bundle_digest"], "source bundle differs")
    wheel = build.build_wheel(str(output / "wheel"))
    payloads["runtime_wheel"] = (output / "wheel" / wheel).read_bytes()
    files = {name: name.replace("_", "-") + ".json" for name in payloads}
    files["runtime_wheel"] = "wheel/" + wheel
    for path in sorted((output / "source-bundle").rglob("*")):
        if path.is_file():
            key = "bundle_" + str(len(payloads))
            payloads[key] = path.read_bytes()
            files[key] = path.relative_to(output).as_posix()
    for key, payload in payloads.items():
        path = output / files[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    atomic(output / "material-references.json", refs)
    source = render(payloads, files, approved=approved)
    notebook = {"cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                            "source": source.splitlines(keepends=True)}],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 5}
    atomic(output / "kernel/kaggle-notebook.ipynb", notebook)
    atomic(output / "kernel/kernel-metadata.json", metadata(plan))
    summary = {"format": "irisx/nvarc-combined-stage-v1", "run_id": RUN, "approved": approved,
               "plan_digest": digest_value(plan), "external_calls": 0,
               "inventory": {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob("*")) if p.is_file()},
               "claim": ("Decision 0035 exact local submission package; two-device GPU acceptance pending"
                         if approved else "local inert proposal; two-device GPU acceptance pending")}
    atomic(output / "stage-summary.json", summary)
    return summary


def metadata(plan):
    return {"id": plan["kernel_id"], "title": RUN, "code_file": "kaggle-notebook.ipynb",
            "language": "python", "kernel_type": "notebook", "is_private": True,
            "enable_gpu": True, "enable_tpu": False, "enable_internet": False,
            "machine_shape": "NvidiaL4", "competition_sources": ["arc-prize-2026-arc-agi-2"],
            "dataset_sources": [plan["branches"]["m3"]["source_dataset_id"],
                                plan["branches"]["m2"]["model_dataset_id"]],
            "kernel_sources": [], "model_sources": []}


def verify_inputs(plan, payloads):
    import hashlib
    for key in ("source_config", "visible", "training_evidence"):
        require(hashlib.sha256(payloads[key]).hexdigest() == plan["branches"]["m2"][key + "_sha256"],
                "combined M2 input differs: " + key)
    teacher = plan["branches"]["m3"]
    model_manifest = json.loads(payloads["model_manifest"])
    require(digest_value(model_manifest.get("files")) == teacher["teacher_model_manifest_digest"] and
            model_manifest.get("format") == "irisx/model-material-manifest" and
            model_manifest.get("repository") == "Qwen/Qwen3.5-4B" and
            model_manifest.get("revision") == "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",
            "combined teacher manifest content differs")
    require(hashlib.sha256(payloads["seed"]).hexdigest() == teacher["seed_record_sha256"] and
            digest_value(json.loads(payloads["prompts"])) == teacher["prompts_digest"] and
            json.loads(payloads["model_manifest"])["manifest_digest"] == teacher["teacher_model_manifest_digest"] and
            hashlib.sha256(payloads["wheel_manifest"]).hexdigest() == WHEEL_MANIFEST_SHA,
            "combined teacher or dependency inputs differ")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approved", action="store_true", help="stage only the exact Decision 0035 envelope")
    args = parser.parse_args()
    print(json.dumps(stage(args.output, approved=args.approved), indent=2))
