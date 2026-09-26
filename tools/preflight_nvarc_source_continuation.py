"""Offline review of the distinct, inert M2 export-only continuation."""

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


def preflight(package: Path) -> dict:
    summary = json.loads((package / "stage-summary.json").read_bytes())
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
    expected = (ROOT / "tools/nvarc_source_continuation_notebook.py.tmpl").read_text()
    for key in ("PAYLOADS", "HASHES", "FILES"):
        expected = expected.replace("__" + key + "__", repr(bindings[key]))
    if source != expected:
        raise ValidationError("continuation executable differs from reviewed template")
    plan = json.loads(payloads["plan"])
    validate_plan(plan, approved=False)
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
    if (set(path.name for path in dataset.iterdir()) !=
            {"export", "training-evidence.json", "dataset-metadata.json"} or
            any(path.is_symlink() for path in dataset.iterdir()) or
            json.loads((dataset / "dataset-metadata.json").read_bytes()).get("id") != plan["model_dataset_id"]):
        raise ValidationError("continuation Dataset root inventory or identity differs")
    verify_model_material(package / "model-dataset/export", EXPORT)
    if (package / "model-dataset/training-evidence.json").read_bytes() != payloads["training_evidence"]:
        raise ValidationError("continuation Dataset provenance differs")
    meta = json.loads(metadata.read_bytes())
    if (meta.get("is_private") is not True or meta.get("enable_internet") is not False or
            meta.get("id") != "DRAFT-DO-NOT-PUSH/" + RUN or meta.get("machine_shape") != "NvidiaL4" or
            meta.get("dataset_sources") != [plan["model_dataset_id"], plan["wheel_dataset_id"]] or
            meta.get("competition_sources") != ["arc-prize-2026-arc-agi-2"]):
        raise ValidationError("continuation provider boundaries differ")
    with tempfile.TemporaryDirectory() as temp:
        script = Path(temp) / "guard.py"
        script.write_text(source, encoding="utf-8")
        guard = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=10)
        if guard.returncode == 0 or "exact owner-approved source continuation required" not in guard.stderr:
            raise ValidationError("continuation draft did not stop before execution")
    return {"run_id": RUN, "approved": False, "external_calls": 0, "draft_guard_verified": True,
            "source_bundle_digest": plan["source_bundle_digest"], "export_material_digest": EXPORT}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    print(json.dumps(preflight(parser.parse_args().package), indent=2))
