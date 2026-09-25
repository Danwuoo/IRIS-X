"""Stage the zero-paid small SDG teacher proposal offline, without provider use."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
import irisx_build_backend as build
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError

CONFIG = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs"
SOURCE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/source"
DEFAULT_OUT = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/teacher-small-draft"


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stage(output: Path = DEFAULT_OUT, authorization: Path | None = None,
          draft_path: Path = CONFIG / "m3-teacher-draft.json") -> dict:
    if output.exists():
        raise ValidationError("new teacher package directory required")
    if draft_path.resolve() not in {(CONFIG / name).resolve() for name in
                                    ("m3-teacher-draft.json", "m3-teacher-draft-002.json")}:
        raise ValidationError("unknown immutable teacher draft")
    draft_bytes = draft_path.read_bytes()
    plan = json.loads(draft_bytes)
    if (plan.get("approved") is not False or plan["maximum_teacher_calls"] != 4 or
            plan["maximum_total_reserved_tokens"] != 20480 or plan["maximum_paid_usd"] != 0 or
            plan.get("run_id") not in {"nvarc-m3-teacher-small-001",
                                       "nvarc-m3-teacher-small-002"} or
            plan.get("kernel_id") != "DRAFT-DO-NOT-PUSH/" + plan["run_id"]):
        raise ValidationError("small teacher draft differs")
    if authorization is not None:
        binding = json.loads(authorization.read_bytes())
        if (binding.get("approved") is not True or
                binding.get("draft_plan_sha256") != sha(draft_bytes) or
                binding.get("run_id") != plan["run_id"] or
                binding.get("kernel_id") != "danielwuu/" + plan["run_id"] or
                not isinstance(binding.get("owner_decision"), str) or
                not binding["owner_decision"].strip() or
                (plan["run_id"].endswith("002") and
                 binding["owner_decision"].startswith(("Decision 0028", "Decision 0029",
                                                       "Decision 0030")))):
            raise ValidationError("exact SDG teacher authorization is absent or differs")
        plan["approved"] = True
        plan["owner_decision"] = binding["owner_decision"]
        plan["kernel_id"] = binding["kernel_id"]
    small = json.loads((CONFIG / "m2-m3-small.json").read_bytes())
    records = []
    for selected in small["train"][:2]:
        path = SOURCE / "NVARC/external/ARC-AGI-2/data/training" / f"{selected['id']}.json"
        payload = path.read_bytes()
        if sha(payload) != selected["sha256"]:
            raise ValidationError("public SDG teacher train parent differs")
        records.append(json.loads(payload))
    if min(len(item["train"]) for item in records) < 2:
        raise ValidationError("SDG teacher seed needs two demonstrations per parent")
    parent_ids = [item["id"] for item in small["train"][:2]]
    seed = {"format": "irisx/nvarc-m3-teacher-seed-v1", "parent_ids": parent_ids,
            "parent_sha256": [item["sha256"] for item in small["train"][:2]],
            "record": {"record_id": "public-arc-train-pair-001",
                       "source_id": "official-ARC-AGI-2-public-training-only",
                       "train_demos": records[0]["train"][:2],
                       "second_description": "Second public ARC training puzzle demonstrations: " +
                       json.dumps(records[1]["train"][:2], sort_keys=True),
                       "source_comments": "No source comments supplied."}}
    seed_bytes = canonical_bytes(seed, newline=True)
    prompt_root = SOURCE / "NVARC/SDG/prompts"
    prompt_names = {"summary": "summary_v1.md", "mix": "mix_v1.md",
                    "input-logic": "generate_puzzle_input.md",
                    "output-logic": "generate_puzzle_output.md"}
    prompts = {stage: (prompt_root / name).read_text(encoding="utf-8")
               for stage, name in prompt_names.items()}
    plan["seed_record_sha256"] = sha(seed_bytes)
    plan["prompts_digest"] = digest_value(prompts)
    manifest = json.loads((CONFIG / "base-model-manifest.json").read_bytes())
    if (manifest["manifest_digest"] != plan["teacher_model_manifest_digest"] or
            manifest["revision"] != "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"):
        raise ValidationError("teacher model identity differs")
    wheel_manifest = json.loads((CONFIG / "base-wheel-manifest.json").read_bytes())
    wheel_dir = output / "wheel"
    wheel_name = build.build_wheel(str(wheel_dir))
    wheel_bytes = (wheel_dir / wheel_name).read_bytes()
    with zipfile.ZipFile(wheel_dir / wheel_name) as archive:
        if "irisx/arc_nvarc_sdg_teacher.py" not in archive.namelist():
            raise ValidationError("runtime wheel omitted teacher entry")
    payloads = {"plan": canonical_bytes(plan, newline=True), "seed": seed_bytes,
                "prompts": canonical_bytes(prompts, newline=True),
                "model_manifest": canonical_bytes(manifest, newline=True),
                "wheel_manifest": canonical_bytes(wheel_manifest, newline=True),
                "runtime_wheel": wheel_bytes}
    hashes = {name: sha(payload) for name, payload in payloads.items()}
    output.mkdir(parents=True, exist_ok=True)
    for name in ("plan", "seed", "prompts"):
        (output / f"{name}.json").write_bytes(payloads[name])
    encoded = {name: base64.b64encode(payload).decode() for name, payload in payloads.items()}
    template_name = ("nvarc_m3_teacher_notebook_002.py.tmpl" if plan["run_id"].endswith("002")
                     else "nvarc_m3_teacher_notebook.py.tmpl")
    template = (ROOT / "tools" / template_name).read_text(encoding="utf-8")
    source = template.replace("__PAYLOADS__", json.dumps(encoded, sort_keys=True)).replace(
        "__HASHES__", json.dumps(hashes, sort_keys=True))
    compile(source, "m3-teacher-notebook", "exec")
    kernel = output / "kernel"
    kernel.mkdir(parents=True)
    notebook = {"cells": [{"cell_type": "code", "execution_count": None, "metadata": {},
                            "outputs": [], "source": source.splitlines(keepends=True)}],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                             "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 5}
    notebook_path = kernel / "kaggle-notebook.ipynb"
    notebook_path.write_bytes(canonical_bytes(notebook, newline=True))
    metadata = {"id": plan["kernel_id"], "title": plan["run_id"],
                "code_file": notebook_path.name, "language": "python", "kernel_type": "notebook",
                "is_private": True, "enable_gpu": True, "enable_tpu": False,
                "enable_internet": False, "machine_shape": "NvidiaL4",
                "competition_sources": plan.get("competition_sources", []),
                "dataset_sources": [plan["source_dataset_id"]],
                "kernel_sources": [], "model_sources": []}
    (kernel / "kernel-metadata.json").write_bytes(canonical_bytes(metadata, newline=True))
    summary = {"format": "irisx/nvarc-m3-teacher-stage-v1", "approved": plan["approved"],
               "run_id": plan["run_id"], "draft_plan_sha256": sha(draft_bytes),
               "plan_digest": digest_value(plan), "plan_sha256": hashes["plan"],
               "seed_record_sha256": hashes["seed"], "prompts_digest": plan["prompts_digest"],
               "teacher_model_manifest_digest": manifest["manifest_digest"],
               "runtime_wheel_sha256": hashes["runtime_wheel"],
               "notebook_sha256": sha(notebook_path.read_bytes()),
               "metadata_sha256": sha((kernel / "kernel-metadata.json").read_bytes()),
               "maximum_teacher_calls": 4, "maximum_total_reserved_tokens": 20480,
               "output": str(output), "external_calls": 0,
               "claim": "offline teacher proposal only; model calls unexecuted"}
    (output / "stage-summary.json").write_bytes(canonical_bytes(summary, newline=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--draft-plan", type=Path, default=CONFIG / "m3-teacher-draft.json")
    args = parser.parse_args()
    print(json.dumps(stage(args.output, args.authorization, args.draft_plan), indent=2))


if __name__ == "__main__":
    main()
