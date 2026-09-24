"""Recheck a staged M2/M3 draft without provider calls or notebook execution."""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from irisx.arc_nvarc_representation import verify_model_material
from irisx.canonical import digest_value
from irisx.errors import ValidationError


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def preflight(package: Path) -> dict:
    summary = json.loads((package / "stage-summary.json").read_bytes())
    kind = summary.get("format")
    if kind not in {"irisx/nvarc-m2-fsdp-stage-v1", "irisx/nvarc-m3-teacher-stage-v1"}:
        raise ValidationError("unknown M2/M3 package kind")
    if summary.get("approved") is not False or summary.get("external_calls") != 0:
        raise ValidationError("preflight expects a zero-call unapproved draft")
    kernel = package / "kernel"
    notebook_path = kernel / "kaggle-notebook.ipynb"
    metadata_path = kernel / "kernel-metadata.json"
    notebook = json.loads(notebook_path.read_bytes())
    metadata = json.loads(metadata_path.read_bytes())
    if (len(notebook.get("cells", [])) != 1 or
            not metadata.get("is_private") or metadata.get("enable_internet") is not False or
            metadata.get("machine_shape") != "NvidiaL4" or
            sha(notebook_path.read_bytes()) != summary["notebook_sha256"] or
            sha(metadata_path.read_bytes()) != summary[
                "kernel_metadata_sha256" if "kernel_metadata_sha256" in summary else "metadata_sha256"]):
        raise ValidationError("notebook or private-offline metadata differs")
    source = "".join(notebook["cells"][0]["source"])
    tree = ast.parse(source)
    bindings = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in {"PAYLOADS", "HASHES"}:
                bindings[node.targets[0].id] = ast.literal_eval(node.value)
    payloads, hashes = bindings["PAYLOADS"], bindings["HASHES"]
    if payloads.keys() != hashes.keys():
        raise ValidationError("embedded M2/M3 payload inventory differs")
    decoded = {name: base64.b64decode(value, validate=True) for name, value in payloads.items()}
    if any(sha(payload) != hashes[name] for name, payload in decoded.items()):
        raise ValidationError("embedded M2/M3 payload digest differs")
    if (sha(decoded["runtime_wheel"]) != summary["runtime_wheel_sha256"] or
            json.loads(decoded["wheel_manifest"]).get("manifest_digest") !=
            "sha256:d24d85f791788621166fa05d7db51c03f7c72c046af4923096b12863f7e7dfa1"):
        raise ValidationError("M2/M3 runtime or offline wheel inventory differs")
    plan = json.loads(decoded["plan"])
    if (plan.get("approved") is not False or sha(decoded["plan"]) != summary["plan_sha256"] or
            digest_value(plan) != summary["plan_digest"]):
        raise ValidationError("M2/M3 draft plan binding differs")
    marker = ("exact owner-approved feasibility plan required" if "fsdp" in kind else
              "exact owner-approved teacher plan required")
    with tempfile.TemporaryDirectory() as scratch:
        draft_script = Path(scratch) / "guard.py"
        draft_script.write_text(source, encoding="utf-8")
        guard = subprocess.run([sys.executable, str(draft_script)], capture_output=True,
                               text=True, timeout=10)
    if guard.returncode == 0 or marker not in guard.stderr:
        raise ValidationError("M2/M3 draft notebook execution guard failed")
    if "fsdp" in kind:
        if (metadata.get("dataset_sources") != [plan["model_dataset_id"],
                                               "danielwuu/irisx-arc-agi-2-trial-002-smoke-001"] or
                sha(decoded["sequences"]) != plan["sequences_sha256"] or
                plan["sequences_digest"] != summary["sequences_digest"] or
                plan["source_data_manifest_digest"] != summary["source_data_manifest_digest"]):
            raise ValidationError("M2 FSDP dataset or sequences differ")
        verify_model_material(package / "model-dataset",
                              plan["compact_material_digest"],
                              allowed_extra_files={"dataset-metadata.json"})
        if sha((package / "model-dataset/dataset-metadata.json").read_bytes()) != summary["dataset_metadata_sha256"]:
            raise ValidationError("M2 private Dataset metadata differs")
    else:
        if (metadata.get("dataset_sources") != [plan["source_dataset_id"]] or
                sha(decoded["seed"]) != plan["seed_record_sha256"] or
                digest_value(json.loads(decoded["prompts"])) != plan["prompts_digest"] or
                sha((package / "seed.json").read_bytes()) != plan["seed_record_sha256"] or
                json.loads(decoded["model_manifest"])["manifest_digest"] !=
                plan["teacher_model_manifest_digest"]):
            raise ValidationError("M3 teacher source or model binding differs")
    return {"format": "irisx/nvarc-m2-m3-local-preflight-v1",
            "kind": kind, "run_id": plan["run_id"], "approved": False,
            "notebook_sha256": summary["notebook_sha256"],
            "payload_count": len(decoded), "draft_guard_verified": True,
            "external_calls": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    print(json.dumps(preflight(args.package), indent=2))


if __name__ == "__main__":
    main()
