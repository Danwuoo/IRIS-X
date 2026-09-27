"""Offline closed-inventory and guard verification, stopping before shared setup."""

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
from irisx.arc_nvarc_combined import (APPROVED_DIGEST, REPAIR_DIGEST, DRAFT_DIGEST, RUN, REPAIR_RUN, activate_plan,
                                    member, read, require, sha, validate_plan)
from irisx.arc_nvarc_source_bundle import verify_bundle
from irisx.canonical import canonical_bytes, digest_value


OFFLINE_STOP = "offline approved guard accepted; stopped before shared setup"


def guard_prefix(source: str) -> str:
    """Extract only stdlib payload/authorization checks, never live setup.

    The first environment mutation begins the live path. Replace everything
    from there in the try body with a deliberate exception, preserving terminal
    diagnostics. No approved notebook is ever executed by preflight.
    """
    tree = ast.parse(source)
    block = next(node for node in tree.body if isinstance(node, ast.Try))
    boundary = next(i for i, node in enumerate(block.body) if isinstance(node, ast.Expr) and
                    isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "os.environ.update")
    block.body = block.body[:boundary] + [ast.Raise(exc=ast.Call(
        func=ast.Name(id="RuntimeError", ctx=ast.Load()), args=[ast.Constant(OFFLINE_STOP)], keywords=[]))]
    return ast.unparse(ast.fix_missing_locations(tree))


def probe_guard(source: str, plan_digest: str, *, accepted=False, run_id=RUN) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT / ".irisx", prefix="combined-guard-") as temp:
        probe = Path(temp) / "guard.py"
        probe.write_text(guard_prefix(source), encoding="utf-8")
        guard = subprocess.run([sys.executable, "-I", str(probe)], cwd=temp,
                               capture_output=True, text=True, timeout=10)
        expected = OFFLINE_STOP if accepted else "combined draft is inert"
        require(guard.returncode != 0 and expected in guard.stderr,
                "combined notebook offline authorization probe differs")
        terminal = read(Path(temp) / run_id / "aggregate-terminal.json")
        require(terminal.get("outcome") == "failed" and terminal.get("last_phase") == "execution-guard" and
                terminal.get("plan_digest") == plan_digest and
                all(b["launch_count"] == 0 for b in terminal["branches"].values()), "offline guard terminal differs")


def preflight(package: Path, *, approved=False) -> dict:
    summary = read(package / "stage-summary.json")
    run_id = summary.get("run_id")
    expected_digest = REPAIR_DIGEST if run_id == REPAIR_RUN else APPROVED_DIGEST
    require(summary.get("format") == "irisx/nvarc-combined-stage-v1" and run_id in {RUN, REPAIR_RUN} and
            (approved or run_id == RUN) and
            summary.get("approved") is approved and summary.get("external_calls") == 0 and
            summary.get("plan_digest") == (expected_digest if approved else DRAFT_DIGEST),
            "combined package summary differs")
    inventory = summary["inventory"]
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    require(actual == set(inventory) | {"stage-summary.json"} and
            not any(p.is_symlink() for p in package.rglob("*")), "combined closed file inventory differs")
    for name, digest in inventory.items():
        require(sha(member(package, name)) == digest, "combined review file differs: " + name)
    plan = read(package / "plan.json")
    validate_plan(plan, approved=approved)
    expected_plan = canonical_bytes(activate_plan(read(DRAFT), run_id=run_id), newline=True) if approved else DRAFT.read_bytes()
    require((package / "plan.json").read_bytes() == expected_plan, "checked plan bytes differ")
    require(read(package / "kernel/kernel-metadata.json") == metadata(plan), "combined private metadata differs")
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
    require(source == render(payloads, bindings["FILES"], approved=approved, run_id=run_id),
            "combined executable differs from reviewed template")
    require(payloads["plan"] == (package / "plan.json").read_bytes(), "embedded plan differs")
    verify_inputs(plan, payloads)
    verify_bundle(package / "source-bundle", plan["branches"]["m2"]["source_bundle_digest"])
    verify_references(read(package / "material-references.json"), json.loads(payloads["model_manifest"]))
    # Deliberately truncate before setup even when checking an approved package.
    probe_guard(source, digest_value(plan), accepted=approved, run_id=run_id)
    draft_payloads = {**payloads, "plan": DRAFT.read_bytes()}
    probe_guard(render(draft_payloads, bindings["FILES"], approved=approved, run_id=run_id), DRAFT_DIGEST, run_id=run_id)
    hardware_probe = None
    if approved and run_id == REPAIR_RUN:
        from tools.nvarc_combined_hardware_probe import probe_hardware
        hardware_probe = probe_hardware(source)
    return {"run_id": run_id, "plan_digest": digest_value(plan), "approved": approved,
            "external_calls": 0, "draft_guard_verified": True, "inventory_count": len(inventory),
            "approved_guard_verified": approved, "offline_probe_stops_before_shared_setup": True,
            "generated_hardware_fixture_probe": hardware_probe,
            "export_verified_by_reference": True, "cached_tokenizer_verified": True,
            "gpu_acceptance": "pending"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--approved", action="store_true", help="verify exact historical/replacement approved package")
    args = parser.parse_args()
    print(json.dumps(preflight(args.package, approved=args.approved), indent=2))
