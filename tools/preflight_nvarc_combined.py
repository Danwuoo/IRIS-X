"""Offline closed-inventory verification and execution-guard test of the draft."""

from __future__ import annotations

import argparse
import ast
import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools.stage_nvarc_combined import (DRAFT, metadata, render, verify_inputs, verify_references)
from irisx.arc_nvarc_combined import DRAFT_DIGEST, RUN, member, read, require, sha, validate_plan
from irisx.arc_nvarc_source_bundle import verify_bundle
from irisx.canonical import canonical_bytes, digest_value


def preflight(package: Path) -> dict:
    summary = read(package / "stage-summary.json")
    require(summary.get("format") == "irisx/nvarc-combined-stage-v1" and summary.get("run_id") == RUN and
            summary.get("approved") is False and summary.get("external_calls") == 0 and
            summary.get("plan_digest") == DRAFT_DIGEST, "combined package summary differs")
    inventory = summary["inventory"]
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    require(actual == set(inventory) | {"stage-summary.json"} and
            not any(p.is_symlink() for p in package.rglob("*")), "combined closed file inventory differs")
    for name, digest in inventory.items():
        require(sha(member(package, name)) == digest, "combined review file differs: " + name)
    plan = read(package / "plan.json")
    validate_plan(plan)
    require((package / "plan.json").read_bytes() == DRAFT.read_bytes(), "checked draft bytes differ")
    require(read(package / "kernel/kernel-metadata.json") == metadata(plan), "combined private draft metadata differs")
    notebook = read(package / "kernel/kaggle-notebook.ipynb")
    source = "".join(notebook["cells"][0]["source"])
    bindings = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in {"PAYLOADS", "HASHES", "FILES"}:
                bindings[node.targets[0].id] = ast.literal_eval(node.value)
    payloads = {k: base64.b64decode(v, validate=True) for k, v in bindings["PAYLOADS"].items()}
    require(set(payloads) == set(bindings["HASHES"]) == set(bindings["FILES"]), "combined embedded inventory differs")
    expected_payloads = {"plan", "source_config", "visible", "training_evidence", "seed", "prompts",
                         "model_manifest", "wheel_manifest", "runtime_wheel"}
    bundle_files = sorted(p for p in (package / "source-bundle").rglob("*") if p.is_file())
    expected_files = {key: key.replace("_", "-") + ".json" for key in expected_payloads}
    expected_files["runtime_wheel"] = "wheel/irisx-0.2.0-py3-none-any.whl"
    for index, path in enumerate(bundle_files, start=len(expected_payloads)):
        expected_files["bundle_" + str(index)] = path.relative_to(package).as_posix()
    require(bindings["FILES"] == expected_files and set(payloads) == set(expected_files),
            "combined expected payload members differ")
    require(set(inventory) == set(expected_files.values()) | {"material-references.json",
            "kernel/kaggle-notebook.ipynb", "kernel/kernel-metadata.json"},
            "combined expected review inventory differs")
    for key, value in payloads.items():
        import hashlib
        require(hashlib.sha256(value).hexdigest() == bindings["HASHES"][key] and
                member(package, bindings["FILES"][key]).read_bytes() == value,
                "combined embedded bytes differ: " + key)
    require(source == render(payloads, bindings["FILES"]), "combined executable differs from reviewed template")
    require(payloads["plan"] == (package / "plan.json").read_bytes(), "embedded plan differs")
    verify_inputs(plan, payloads)
    verify_bundle(package / "source-bundle", plan["branches"]["m2"]["source_bundle_digest"])
    verify_references(read(package / "material-references.json"), json.loads(payloads["model_manifest"]))
    # Execute the exact stdlib guard only; no dependency installs or model work.
    with tempfile.TemporaryDirectory(dir=ROOT / ".irisx", prefix="combined-guard-") as temp:
        probe = Path(temp) / "guard.py"
        probe.write_text(source, encoding="utf-8")
        guard = subprocess.run([sys.executable, "-I", str(probe)], cwd=temp,
                               capture_output=True, text=True, timeout=10)
        require(guard.returncode != 0 and "combined draft is inert" in guard.stderr,
                "combined notebook guard did not reject execution")
        terminal = read(Path(temp) / RUN / "aggregate-terminal.json")
        require(terminal.get("outcome") == "failed" and terminal.get("last_phase") == "execution-guard" and
                terminal.get("plan_digest") == DRAFT_DIGEST and
                all(b["launch_count"] == 0 for b in terminal["branches"].values()), "inert guard terminal differs")
    return {"run_id": RUN, "plan_digest": digest_value(plan), "approved": False,
            "external_calls": 0, "draft_guard_verified": True, "inventory_count": len(inventory),
            "export_verified_by_reference": True, "cached_tokenizer_verified": True,
            "gpu_acceptance": "pending"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    print(json.dumps(preflight(parser.parse_args().package), indent=2))
