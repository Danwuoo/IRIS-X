"""Stage the exact Decision 0037 notebook; offline probes never enter setup."""

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
from tools import stage_nvarc_combined_candidate as candidate
from tools.stage_nvarc_combined import metadata, verify_inputs, verify_references
from tools.preflight_nvarc_combined import probe_guard
from tools.nvarc_combined_hardware_probe import probe_hardware
from irisx.arc_nvarc_combined import (EDITOR_DIGEST, atomic, member, read, require,
                                     require_live_authorization, sha)
from irisx.arc_nvarc_source_bundle import verify_bundle
from irisx.canonical import canonical_bytes, digest_value

RUN = candidate.RUN
PLAN = candidate.PLAN.with_name("m2-m3-combined-editor-003.json")
TEMPLATE = ROOT / "tools/nvarc_combined_notebook_editor_003.py.tmpl"


def validate(plan):
    require(digest_value(plan) == EDITOR_DIGEST and
            canonical_bytes(plan, newline=True) == PLAN.read_bytes(), "exact Editor plan required")
    original = read(candidate.PLAN)
    require(plan["branches"] == original["branches"] and
            plan["candidate_plan_digest"] == digest_value(original), "reviewed scientific fields differ")
    expected = {**original, "format": "irisx/nvarc-combined-editor-v1", "approved": True,
        "owner_decision": "Decision 0037", "kernel_id": "danielwuu/" + RUN,
        "candidate_plan_digest": digest_value(original),
        "execution_control": {"agent_start": False, "owner_editor_start": True, "save_type": "QUICK_SAVE"},
        "external_allowances": {**original["external_allowances"], "submissions": 1}}
    require(plan == expected, "Editor authorization envelope differs")
    require_live_authorization(plan)


def bindings(source):
    values = {node.targets[0].id: ast.literal_eval(node.value) for node in ast.parse(source).body
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and
        isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"PAYLOADS", "FILES", "HASHES"}}
    return values, {key: base64.b64decode(value, validate=True) for key, value in values["PAYLOADS"].items()}


def render(payloads, files):
    source = TEMPLATE.read_text(encoding="utf-8").replace(
        "__HARDWARE_HELPER__", candidate.HARDWARE_HELPER.read_text(encoding="utf-8"))
    source = source.replace("__PLAN_DIGEST__", repr(EDITOR_DIGEST))
    for name, value in {"PAYLOADS": {k: base64.b64encode(v).decode() for k, v in payloads.items()},
        "HASHES": {k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()}, "FILES": files}.items():
        source = source.replace("__" + name + "__", repr(value))
    compile(source, "owner-editor-003", "exec")
    return source


def stage(output):
    validate(read(PLAN))
    summary = candidate.stage(output)  # New directory only; never alters a retained candidate.
    notebook = read(output / "kernel/kaggle-notebook.ipynb")
    values, payloads = bindings("".join(notebook["cells"][0]["source"]))
    payloads["plan"] = PLAN.read_bytes()
    (output / "plan.json").write_bytes(payloads["plan"])
    notebook["cells"][0]["source"] = render(payloads, values["FILES"]).splitlines(keepends=True)
    atomic(output / "kernel/kaggle-notebook.ipynb", notebook)
    atomic(output / "kernel/kernel-metadata.json", metadata(read(PLAN)))
    summary.update(format="irisx/nvarc-combined-editor-stage-v1", approved=True,
        plan_digest=EDITOR_DIGEST, claim="owner Editor execution only; saved with QUICK_SAVE")
    summary["inventory"] = {name: sha(output / name) for name in summary["inventory"]}
    atomic(output / "stage-summary.json", summary)
    return summary


def preflight(package):
    plan, summary = read(package / "plan.json"), read(package / "stage-summary.json")
    validate(plan)
    require(summary["format"] == "irisx/nvarc-combined-editor-stage-v1" and
        summary["run_id"] == RUN and summary["approved"] is True and
        summary["plan_digest"] == EDITOR_DIGEST and summary["external_calls"] == 0, "Editor summary differs")
    inventory = summary["inventory"]
    require({p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()} ==
        set(inventory) | {"stage-summary.json"} and not any(p.is_symlink() for p in package.rglob("*")),
        "Editor closed inventory differs")
    for name, digest in inventory.items():
        require(sha(member(package, name)) == digest, "Editor member differs: " + name)
    source = "".join(read(package / "kernel/kaggle-notebook.ipynb")["cells"][0]["source"])
    values, payloads = bindings(source)
    keys = {"plan", "source_config", "visible", "training_evidence", "seed", "prompts",
            "model_manifest", "wheel_manifest", "runtime_wheel"}
    files = {key: key.replace("_", "-") + ".json" for key in keys}
    files["runtime_wheel"] = "wheel/" + candidate.build.WHEEL_NAME
    for index, path in enumerate(sorted(p for p in (package / "source-bundle").rglob("*") if p.is_file()), start=len(keys)):
        files["bundle_" + str(index)] = path.relative_to(package).as_posix()
    require(values["FILES"] == files and set(payloads) == set(files) == set(values["HASHES"]) and
        set(inventory) == set(files.values()) | {"material-references.json", "kernel/kaggle-notebook.ipynb",
                                               "kernel/kernel-metadata.json"}, "Editor expected inventory differs")
    for key, value in payloads.items():
        require(hashlib.sha256(value).hexdigest() == values["HASHES"][key] and
            member(package, files[key]).read_bytes() == value, "Editor embedded payload differs: " + key)
    require(source == render(payloads, values["FILES"]), "Editor executable template differs")
    require(payloads["plan"] == PLAN.read_bytes() and
        read(package / "kernel/kernel-metadata.json") == metadata(plan), "Editor plan or metadata differs")
    verify_inputs(plan, payloads)
    verify_bundle(package / "source-bundle", plan["branches"]["m2"]["source_bundle_digest"])
    verify_references(read(package / "material-references.json"), json.loads(payloads["model_manifest"]))
    with zipfile.ZipFile(package / files["runtime_wheel"]) as wheel:
        for path in sorted((ROOT / "src/irisx").glob("*.py")):
            require(wheel.read("irisx/" + path.name) == path.read_bytes(), "Editor wheel source differs: " + path.name)
    probe_guard(source, EDITOR_DIGEST, accepted=True, run_id=RUN)
    probe_guard(render({**payloads, "plan": candidate.PLAN.read_bytes()}, values["FILES"]),
                digest_value(read(candidate.PLAN)), run_id=RUN)
    return {"run_id": RUN, "plan_digest": EDITOR_DIGEST, "approved": True, "external_calls": 0,
        "owner_editor_only": True, "approved_guard_verified": True, "draft_guard_verified": True,
        "offline_probe_stops_before_shared_setup": True, "wheel_matches_source": True,
        "inventory_count": len(inventory), "generated_hardware_fixture_probe": probe_hardware(source)}


def save_fields(package):
    """Pure request projection. Credential/API imports occur only in the deliberate save command."""
    plan = read(package / "plan.json")
    validate(plan)
    meta = read(package / "kernel/kernel-metadata.json")
    require(meta == metadata(plan), "save metadata differs")
    notebook = read(package / "kernel/kaggle-notebook.ipynb")
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            require(cell["outputs"] == [] and cell["execution_count"] is None, "notebook was executed")
        if isinstance(cell.get("source"), list):
            cell["source"] = "".join(cell["source"])
    return {"slug": meta["id"], "new_title": meta["title"], "text": json.dumps(notebook),
        "language": "python", "kernel_type": "notebook", "is_private": True,
        "enable_gpu": True, "enable_tpu": False, "enable_internet": False,
        "machine_shape": "NvidiaL4", "session_timeout_seconds": 1800,
        "dataset_data_sources": meta["dataset_sources"], "competition_data_sources": meta["competition_sources"],
        "kernel_data_sources": [], "model_data_sources": [], "kernel_execution_type": "QUICK_SAVE"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight", type=Path)
    args = parser.parse_args()
    require((args.output is None) != (args.preflight is None), "choose stage or preflight")
    print(json.dumps(stage(args.output) if args.output else preflight(args.preflight), indent=2))
