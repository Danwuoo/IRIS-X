"""Build and verify the inert combined 003 candidate using only retained inputs."""

from __future__ import annotations

import argparse
import ast
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools import irisx_build_backend as build
from tools.stage_nvarc_combined import (DRAFT, M2, M3, LOCAL, TRIAL, HARDWARE_HELPER,
    references, verify_references, verify_inputs, metadata)
from tools.preflight_nvarc_combined import probe_guard
from tools.nvarc_combined_hardware_probe import probe_hardware
from irisx.arc_nvarc_combined import (REPAIR_DIGEST, atomic, read, require, sha, member,
                                     require_live_authorization)
from irisx.arc_nvarc_source_bundle import build_bundle, verify_bundle
from irisx.arc_nvarc_teacher_spec import PROFILE, PROMPTS, paired_seed
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError

RUN = "nvarc-m2-m3-combined-003"
PLAN = TRIAL / "configs/m2-m3-combined-candidate-003.json"
TEMPLATE = ROOT / "tools/nvarc_combined_notebook_candidate_003.py.tmpl"


def make_plan():
    plan = copy.deepcopy(read(DRAFT))
    plan.update(format="irisx/nvarc-combined-candidate-v1", run_id=RUN,
                kernel_id="DRAFT-DO-NOT-PUSH/" + RUN, predecessor_plan_digest=REPAIR_DIGEST)
    for branch, child in plan["branches"].items():
        child.update(run_id=RUN + "-" + branch,
                     kernel_id="DRAFT-DO-NOT-PUSH/" + RUN + "-" + branch)
    plan["branches"]["m2"]["search_diagnostics_profile"] = "root-pruning-v1"
    child = plan["branches"]["m3"]
    child.update(teacher_profile=PROFILE, prompts_digest=digest_value(PROMPTS),
        original_seed_record_sha256=child["seed_record_sha256"],
        seed_record_sha256=hashlib.sha256(canonical_bytes(paired_seed(read(M3 / "seed.json")), newline=True)).hexdigest())
    return plan


def validate_candidate(plan):
    require(plan == make_plan() and canonical_bytes(plan, newline=True) == PLAN.read_bytes(),
            "exact inert combined 003 candidate plan required")
    require(plan["approved"] is False and plan["owner_decision"] is None and
            all(type(v) is int and v == 0 for v in plan["external_allowances"].values()),
            "candidate external allowances must remain zero")


def render(payloads, files):
    source = TEMPLATE.read_text(encoding="utf-8").replace(
        "__HARDWARE_HELPER__", HARDWARE_HELPER.read_text(encoding="utf-8"))
    source = source.replace("__PLAN_DIGEST__", repr(digest_value(read(PLAN))))
    for name, value in {"PAYLOADS": {k: base64.b64encode(v).decode() for k, v in payloads.items()},
                        "HASHES": {k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()},
                        "FILES": files}.items():
        source = source.replace("__" + name + "__", repr(value))
    compile(source, "inert-combined-003", "exec")
    return source


def stage(output):
    require(not output.exists(), "new candidate review directory required")
    plan = read(PLAN)
    validate_candidate(plan)
    payloads = {"plan": PLAN.read_bytes(),
        **{key: (M2 / name).read_bytes() for key, name in
           (("source_config", "source-config.json"), ("visible", "visible.json"),
            ("training_evidence", "training-evidence.json"))},
        "seed": canonical_bytes(paired_seed(read(M3 / "seed.json")), newline=True),
        "prompts": canonical_bytes(PROMPTS, newline=True),
        "model_manifest": (TRIAL / "configs/base-model-manifest.json").read_bytes(),
        "wheel_manifest": (TRIAL / "configs/base-wheel-manifest.json").read_bytes()}
    verify_inputs(plan, payloads)
    refs = references()
    verify_references(refs, json.loads(payloads["model_manifest"]))
    bundle = build_bundle(LOCAL / "source", TRIAL / "source-manifest.json", output / "source-bundle")
    require(bundle["bundle_digest"] == plan["branches"]["m2"]["source_bundle_digest"], "candidate source bundle differs")
    wheel = build.build_wheel(str(output / "wheel"))
    payloads["runtime_wheel"] = (output / "wheel" / wheel).read_bytes()
    files = {key: key.replace("_", "-") + ".json" for key in payloads}
    files["runtime_wheel"] = "wheel/" + wheel
    for path in sorted((output / "source-bundle").rglob("*")):
        if path.is_file():
            key = "bundle_" + str(len(payloads))
            payloads[key], files[key] = path.read_bytes(), path.relative_to(output).as_posix()
    for key, value in payloads.items():
        path = output / files[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    atomic(output / "material-references.json", refs)
    source = render(payloads, files)
    notebook = {"cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                           "source": source.splitlines(keepends=True)}],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 5}
    atomic(output / "kernel/kaggle-notebook.ipynb", notebook)
    atomic(output / "kernel/kernel-metadata.json", metadata(plan))
    summary = {"format": "irisx/nvarc-combined-candidate-stage-v1", "run_id": RUN,
        "approved": False, "plan_digest": digest_value(plan), "external_calls": 0,
        "inventory": {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob("*")) if p.is_file()},
        "claim": "local inert candidate; model quality and GPU acceptance unverified"}
    atomic(output / "stage-summary.json", summary)
    return summary


def preflight(package):
    summary, plan = read(package / "stage-summary.json"), read(package / "plan.json")
    validate_candidate(plan)
    require(summary.get("format") == "irisx/nvarc-combined-candidate-stage-v1" and
            summary.get("approved") is False and summary.get("run_id") == RUN and
            summary.get("plan_digest") == digest_value(plan) and summary.get("external_calls") == 0,
            "candidate summary differs")
    inventory = summary["inventory"]
    require({p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()} ==
            set(inventory) | {"stage-summary.json"} and not any(p.is_symlink() for p in package.rglob("*")),
            "candidate closed inventory differs")
    for name, digest in inventory.items():
        require(sha(member(package, name)) == digest, "candidate member differs: " + name)
    source = "".join(read(package / "kernel/kaggle-notebook.ipynb")["cells"][0]["source"])
    bindings = {node.targets[0].id: ast.literal_eval(node.value) for node in ast.parse(source).body
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and
                isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"PAYLOADS", "FILES", "HASHES"}}
    payloads = {k: base64.b64decode(v, validate=True) for k, v in bindings["PAYLOADS"].items()}
    keys = {"plan", "source_config", "visible", "training_evidence", "seed", "prompts",
            "model_manifest", "wheel_manifest", "runtime_wheel"}
    files = {key: key.replace("_", "-") + ".json" for key in keys}
    files["runtime_wheel"] = "wheel/" + build.WHEEL_NAME
    for index, path in enumerate(sorted(p for p in (package / "source-bundle").rglob("*") if p.is_file()), start=len(keys)):
        files["bundle_" + str(index)] = path.relative_to(package).as_posix()
    require(bindings["FILES"] == files and set(payloads) == set(files) == set(bindings["HASHES"]) and
            set(inventory) == set(files.values()) | {"material-references.json", "kernel/kaggle-notebook.ipynb",
                                                  "kernel/kernel-metadata.json"}, "candidate expected inventory differs")
    for key, value in payloads.items():
        require(hashlib.sha256(value).hexdigest() == bindings["HASHES"][key] and
                member(package, files[key]).read_bytes() == value, "candidate embedded payload differs: " + key)
    require(source == render(payloads, bindings["FILES"]), "candidate executable template differs")
    require(payloads["plan"] == PLAN.read_bytes() and
            read(package / "kernel/kernel-metadata.json") == metadata(plan), "candidate plan or metadata differs")
    verify_inputs(plan, payloads)
    require(json.loads(payloads["prompts"]) == PROMPTS and
            json.loads(payloads["seed"]) == paired_seed(read(M3 / "seed.json")), "candidate paired profile differs")
    verify_bundle(package / "source-bundle", plan["branches"]["m2"]["source_bundle_digest"])
    verify_references(read(package / "material-references.json"), json.loads(payloads["model_manifest"]))
    with zipfile.ZipFile(package / files["runtime_wheel"]) as wheel:
        for path in sorted((ROOT / "src/irisx").glob("*.py")):
            require(wheel.read("irisx/" + path.name) == path.read_bytes(), "candidate wheel source differs: " + path.name)
    probe_guard(source, digest_value(plan), run_id=RUN)
    try:
        require_live_authorization(plan)
    except ValidationError:
        pass
    else:
        raise ValidationError("candidate reached live parent authorization")
    return {"run_id": RUN, "plan_digest": digest_value(plan), "external_calls": 0,
            "execution_guard_rejected": True, "offline_probe_stops_before_shared_setup": True,
            "inventory_count": len(inventory), "wheel_matches_source": True,
            "generated_hardware_fixture_probe": probe_hardware(source),
            "cached_export_and_tokenizer_verified": True, "gpu_acceptance": "pending"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight", type=Path)
    args = parser.parse_args()
    require((args.output is None) != (args.preflight is None), "choose stage or preflight")
    print(json.dumps(stage(args.output) if args.output else preflight(args.preflight), indent=2))
