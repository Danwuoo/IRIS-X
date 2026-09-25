"""Recheck a staged M2/M3 package without provider calls or model execution."""

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
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def preflight(package: Path, *, approved: bool = False) -> dict:
    summary = json.loads((package / "stage-summary.json").read_bytes())
    kind = summary.get("format")
    if kind not in {"irisx/nvarc-m2-fsdp-stage-v1", "irisx/nvarc-m3-teacher-stage-v1"}:
        raise ValidationError("unknown M2/M3 package kind")
    if summary.get("approved") is not approved or summary.get("external_calls") != 0:
        raise ValidationError("package approval or call state differs")
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
    if (plan.get("approved") is not approved or sha(decoded["plan"]) != summary["plan_sha256"] or
            digest_value(plan) != summary["plan_digest"]):
        raise ValidationError("M2/M3 plan binding differs")
    marker = ("exact owner-approved feasibility plan required" if "fsdp" in kind else
              "exact owner-approved teacher plan required")
    if approved:
        expected_decision = ("Decision 0029" if plan.get("run_id") ==
                             "nvarc-m2-fsdp-feasibility-002" else "Decision 0028")
        if (not str(plan.get("owner_decision", "")).startswith(expected_decision) or
                plan.get("kernel_id") != metadata.get("id") or
                plan.get("maximum_kernel_wall_seconds") != 1800 or
                plan.get("maximum_accepted_kernel_versions") != 1 or
                plan.get("maximum_output_retrievals") != 1 or
                plan.get("maximum_paid_usd") != 0):
            raise ValidationError("approved M2/M3 decision boundary differs")
    else:
        with tempfile.TemporaryDirectory() as scratch:
            draft_script = Path(scratch) / "guard.py"
            draft_script.write_text(source, encoding="utf-8")
            guard = subprocess.run([sys.executable, str(draft_script)], capture_output=True,
                                   text=True, timeout=10)
        if guard.returncode == 0 or marker not in guard.stderr:
            raise ValidationError("M2/M3 draft notebook execution guard failed")
    if "fsdp" in kind:
        if metadata.get("competition_sources") != ["arc-prize-2026-arc-agi-2"]:
            raise ValidationError("FSDP L4 transport source mount differs")
        if approved and (plan.get("maximum_optimizer_steps") != 1 or
                         plan.get("maximum_total_input_tokens") != 512 or
                         plan.get("maximum_generations") != 0 or
                         plan.get("model_dataset_id") != "danielwuu/irisx-nvarc-m2-compact-4b-001"):
            raise ValidationError("approved FSDP ceilings differ")
        if plan.get("run_id") == "nvarc-m2-fsdp-feasibility-002" and (
                plan.get("collective_timeout_seconds") != 480 or
                plan.get("maximum_model_dataset_versions") != 0):
            raise ValidationError("FSDP replacement diagnostic or Dataset bound differs")
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
        if approved and (plan.get("maximum_teacher_calls") != 4 or
                         plan.get("maximum_total_reserved_tokens") != 20480 or
                         plan.get("seed_train_parent_ids") != ["833966f4", "6150a2bd"]):
            raise ValidationError("approved teacher ceilings differ")
        if (metadata.get("dataset_sources") != [plan["source_dataset_id"]] or
                sha(decoded["seed"]) != plan["seed_record_sha256"] or
                digest_value(json.loads(decoded["prompts"])) != plan["prompts_digest"] or
                sha((package / "seed.json").read_bytes()) != plan["seed_record_sha256"] or
                json.loads(decoded["model_manifest"])["manifest_digest"] !=
                plan["teacher_model_manifest_digest"]):
            raise ValidationError("M3 teacher source or model binding differs")
    return {"format": "irisx/nvarc-m2-m3-local-preflight-v1",
            "kind": kind, "run_id": plan["run_id"], "approved": approved,
            "notebook_sha256": summary["notebook_sha256"],
            "payload_count": len(decoded), "draft_guard_verified": not approved,
            "external_calls": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    report = preflight(args.package, approved=args.approved)
    if args.report is not None:
        if args.report.exists():
            raise ValidationError("new local preflight report path required")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_bytes(canonical_bytes(report, newline=True))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
