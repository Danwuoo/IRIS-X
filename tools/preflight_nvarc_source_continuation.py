"""Offline review of the distinct M2 export-only continuation."""

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
from irisx.arc_nvarc_source_bundle import verify_bundle
from irisx.arc_nvarc_source_continuation import validate_plan, EXPORT, RUN
from irisx.arc_nvarc_representation import verify_model_material
from irisx.canonical import digest_value
from irisx.errors import ValidationError


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def preflight(package: Path, *, approved: bool = False) -> dict:
    summary = json.loads((package / "stage-summary.json").read_bytes())
    if summary.get("approved") is not approved:
        raise ValidationError("continuation approval state differs")
    notebook = package / "kernel/kaggle-notebook.ipynb"
    metadata = package / "kernel/kernel-metadata.json"
    if (sha(notebook.read_bytes()) != summary["notebook_sha256"] or
            sha(metadata.read_bytes()) != summary["metadata_sha256"]):
        raise ValidationError("continuation notebook/metadata differs")
    source = "".join(json.loads(notebook.read_bytes())["cells"][0]["source"])
    bindings = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in {"PAYLOADS", "HASHES", "FILES"}:
                bindings[node.targets[0].id] = ast.literal_eval(node.value)
    payloads = {key: base64.b64decode(value, validate=True) for key, value in bindings["PAYLOADS"].items()}
    if (set(payloads) != set(bindings["FILES"]) or
            {key: sha(value) for key, value in payloads.items()} != summary["payload_sha256"] or
            bindings["HASHES"] != summary["payload_sha256"]):
        raise ValidationError("continuation embedded payloads differ")
    # Compare the entire executable body to the current reviewed template.
    plan = json.loads(payloads["plan"])
    validate_plan(plan, approved=approved)
    template_name = ("nvarc_source_continuation_notebook.py.tmpl" if plan["run_id"] == RUN else
                     "nvarc_source_continuation_notebook_002.py.tmpl")
    expected = (ROOT / "tools" / template_name).read_text()
    for key in ("PAYLOADS", "HASHES", "FILES"):
        expected = expected.replace("__" + key + "__", repr(bindings[key]))
    if source != expected:
        raise ValidationError("continuation executable differs from reviewed template")
    if digest_value(plan) != summary["plan_digest"] or summary.get("external_calls") != 0:
        raise ValidationError("continuation stage identity differs")
    for key, value in payloads.items():
        relative = Path(bindings["FILES"][key])
        if relative.is_absolute() or ".." in relative.parts or "\\" in bindings["FILES"][key]:
            raise ValidationError("continuation review member path differs")
        if key == "runtime_wheel":
            path = package / "wheel" / bindings["FILES"][key]
        else:
            path = package / bindings["FILES"][key]
        if path.read_bytes() != value:
            raise ValidationError("continuation review member differs: " + key)
    for name in ("source_config", "visible", "training_evidence"):
        if sha(payloads[name]) != plan[name + "_sha256"]:
            raise ValidationError("continuation plan input digest differs")
    verify_bundle(package / "source-bundle", plan["source_bundle_digest"])
    dataset = package / "model-dataset"
    material = json.loads((dataset / "material-manifest.json").read_bytes())
    expected_files = {entry["path"] for entry in material["files"]} | {
        "material-manifest.json", "dataset-metadata.json"}
    if (set(path.name for path in dataset.iterdir()) !=
            expected_files or
            any(path.is_symlink() for path in dataset.iterdir()) or
            json.loads((dataset / "dataset-metadata.json").read_bytes()).get("id") != plan["model_dataset_id"]):
        raise ValidationError("continuation Dataset root inventory or identity differs")
    verify_model_material(dataset, EXPORT, allowed_extra_files={"dataset-metadata.json"})
    meta = json.loads(metadata.read_bytes())
    if (meta.get("is_private") is not True or meta.get("enable_internet") is not False or
            meta.get("id") != plan["kernel_id"] or meta.get("machine_shape") != "NvidiaL4" or
            meta.get("dataset_sources") != [plan["model_dataset_id"], plan["wheel_dataset_id"]] or
            meta.get("competition_sources") != ["arc-prize-2026-arc-agi-2"]):
        raise ValidationError("continuation provider boundaries differ")
    # Exercise an inert copy of the exact notebook guard, never its approved body.
    inert_payloads = dict(bindings["PAYLOADS"])
    inert_plan = {**plan, "approved": False}
    inert_bytes = json.dumps(inert_plan).encode()
    inert_payloads["plan"] = base64.b64encode(inert_bytes).decode()
    inert_hashes = {**bindings["HASHES"], "plan": sha(inert_bytes)}
    guard_source = (ROOT / "tools" / template_name).read_text()
    for key, value in (("PAYLOADS", inert_payloads), ("HASHES", inert_hashes), ("FILES", bindings["FILES"])):
        guard_source = guard_source.replace("__" + key + "__", repr(value))
    with tempfile.TemporaryDirectory() as temp:
        script = Path(temp) / "guard.py"
        script.write_text(guard_source, encoding="utf-8")
        guard = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=10)
        if guard.returncode == 0 or "exact owner-approved source continuation required" not in guard.stderr:
            raise ValidationError("continuation draft did not stop before execution")
    return {"run_id": plan["run_id"], "approved": approved, "external_calls": 0, "draft_guard_verified": True,
            "source_bundle_digest": plan["source_bundle_digest"], "export_material_digest": EXPORT}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    print(json.dumps(preflight(args.package, approved=args.approved), indent=2))
