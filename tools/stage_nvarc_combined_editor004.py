"""Offline exact-package staging for the one Decision 0038 QUICK_SAVE."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT / "src")]
from tools import stage_nvarc_combined_candidate as candidate
from tools.stage_nvarc_combined_editor import bindings
from tools.stage_nvarc_combined import metadata, verify_inputs, verify_references
from tools.preflight_nvarc_combined import probe_guard
from tools.nvarc_combined_hardware_probe import probe_hardware
from irisx.arc_nvarc_combined import atomic, read, require, sha, member
from irisx.arc_nvarc_editor004 import RUN, PLAN_DIGEST, require_editor_authorization
from irisx.arc_nvarc_source_bundle import verify_bundle
from irisx.arc_nvarc_semantics import PROFILE, PROMPTS, NUMPY_WHEEL_SHA256
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError

CONFIGS = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs"
PLAN = CONFIGS / "m2-m3-combined-editor-004.json"
TEMPLATE = ROOT / "tools/nvarc_combined_notebook_editor_004.py.tmpl"
LAUNCHER = ROOT / "tools/nvarc_sdg_semantic_namespace_004.sh"
SDG_SOURCE = candidate.LOCAL / "source/NVARC/SDG/scripts/build_datasets.py"


def sdg_payloads():
    return {"sdg_manifest":(CONFIGS.parent / "source-manifest.json").read_bytes(),
            "sdg_source":SDG_SOURCE.read_bytes()}


def make_plan():
    plan = copy.deepcopy(read(CONFIGS / "m2-m3-combined-editor-003.json"))
    plan.pop("candidate_plan_digest")
    plan.update(run_id=RUN, kernel_id="danielwuu/"+RUN,owner_decision="Decision 0038",
        format="irisx/nvarc-combined-editor004-v1", predecessor_plan_digest=digest_value(read(CONFIGS / "m2-m3-combined-editor-003.json")),
        analysis_zip="結果.zip",analysis_zip_maximum_bytes=64*1024*1024)
    for branch, child in plan["branches"].items():
        child.update(run_id=RUN+"-"+branch,kernel_id="DRAFT-DO-NOT-PUSH/"+RUN+"-"+branch)
    m2 = read(CONFIGS / "m2-root-threshold-proposal-001.json")
    m3 = read(CONFIGS / "m3-rule-contract-proposal-001.json")
    plan["proposal_digests"] = {"m2":digest_value(m2),"m3":digest_value(m3)}
    plan["branches"]["m2"].update(format="irisx/nvarc-paired-threshold-workload-v1",
        arms=m2["arms"],maximum_source_generation_calls=12,maximum_training_tokens=512,
        maximum_verification_calls=24,maximum_dfs_forwards=1536,maximum_verification_forwards=192,
        adaptation_policy="one TTT shared then frozen across all three arms")
    seed = read(candidate.M3 / "seed.json")
    from irisx.arc_nvarc_teacher_spec import paired_seed
    seed = paired_seed(seed)
    seed["record"]["composition_shape"] = [3,3]
    sdg = sdg_payloads()
    plan["branches"]["m3"].update(teacher_profile=PROFILE,prompts_digest=digest_value(PROMPTS),
        seed_record_sha256=hashlib.sha256(canonical_bytes(seed,newline=True)).hexdigest(),
        sdg_source_digest=digest_value({"source-manifest.json":hashlib.sha256(sdg["sdg_manifest"]).hexdigest(),
            "NVARC/SDG/scripts/build_datasets.py":hashlib.sha256(sdg["sdg_source"]).hexdigest()}),
        sandbox_launcher_sha256=sha(LAUNCHER),sandbox_numpy_wheel_sha256=NUMPY_WHEEL_SHA256,
        maximum_program_invocations=44,maximum_accepted_pairs=5,
        semantic_profile="every-public-demo + ordered-composition + isolated finite program probes",
        retention="raw teacher replies, semantic rejection/accepted pairs and usage; truth-free")
    return plan


def validate(plan):
    require_editor_authorization(plan)
    require(plan == make_plan() and canonical_bytes(plan,newline=True) == PLAN.read_bytes(),
            "exact reviewed Editor004 package required")


def render(payloads, files):
    import base64
    source = TEMPLATE.read_text(encoding="utf-8")
    source = source.replace("__HARDWARE_HELPER__",candidate.HARDWARE_HELPER.read_text(encoding="utf-8"))
    source = source.replace("__ZIP_HELPER__",(ROOT / "src/irisx/arc_nvarc_analysis_zip.py").read_text(encoding="utf-8"))
    source = source.replace("__PLAN_DIGEST__",repr(PLAN_DIGEST))
    for name,value in {"PAYLOADS":{k:base64.b64encode(v).decode() for k,v in payloads.items()},
                       "HASHES":{k:hashlib.sha256(v).hexdigest() for k,v in payloads.items()},"FILES":files}.items():
        source = source.replace("__"+name+"__",repr(value))
    compile(source,"owner-editor004","exec")
    return source


def stage(output):
    validate(read(PLAN))
    candidate.stage(output)  # New output only; retained 003 packages stay untouched.
    notebook = read(output / "kernel/kaggle-notebook.ipynb")
    values,payloads = bindings("".join(notebook["cells"][0]["source"]))
    files = values["FILES"]
    payloads["plan"] = PLAN.read_bytes()
    seed = json.loads(payloads["seed"])
    seed["record"]["composition_shape"] = [3,3]
    payloads["seed"] = canonical_bytes(seed,newline=True)
    payloads["prompts"] = canonical_bytes(PROMPTS,newline=True)
    payloads.update(sdg_payloads(),sandbox_launcher=LAUNCHER.read_bytes())
    files.update(sdg_manifest="sdg-source/source-manifest.json",
                 sdg_source="sdg-source/NVARC/SDG/scripts/build_datasets.py",
                 sandbox_launcher="sandbox/nvarc_sdg_semantic_namespace_004.sh")
    for key,value in payloads.items():
        path = output / files[key]
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(value)
    notebook["cells"][0]["source"] = render(payloads,files).splitlines(keepends=True)
    # Owner sees workload, output and start instructions above the code cell.
    notebook["cells"].insert(0,{"cell_type":"markdown","metadata":{},"source":[
        "# IRIS-X M2 + M3 / combined 004\n",
        "Saved with QUICK_SAVE. Start this notebook manually in Editor with **two L4 GPUs**, Internet off.\n",
        "M2: one shared TTT, then 0.2 / 0.1 / 0.02 (12 calls total). M3: at most four dependent teacher calls with semantic gates.\n",
        "Download **結果.zip** from `/kaggle/working` after completion (also retained on ordinary Python errors).\n",
        "The ZIP includes raw replies, per-arm results, usage, hardware, lineage, digests and failures. Hard session termination may prevent finalization.\n"]})
    atomic(output / "kernel/kaggle-notebook.ipynb",notebook)
    atomic(output / "kernel/kernel-metadata.json",metadata(read(PLAN)))
    summary = {"format":"irisx/nvarc-editor004-stage-v1","run_id":RUN,"approved":True,
        "plan_digest":PLAN_DIGEST,"external_calls":0,
        "inventory":{p.relative_to(output).as_posix():sha(p) for p in sorted(output.rglob("*"))
                     if p.is_file() and p.name != "stage-summary.json"}}
    atomic(output / "stage-summary.json",summary)
    return summary


def preflight(package):
    plan,summary = read(package / "plan.json"),read(package / "stage-summary.json")
    validate(plan)
    inventory = summary["inventory"]
    require(summary["plan_digest"] == PLAN_DIGEST and summary["external_calls"] == 0 and
        {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()} == set(inventory)|{"stage-summary.json"}
        and not any(p.is_symlink() for p in package.rglob("*")),"Editor004 closed inventory differs")
    for name,digest in inventory.items():
        require(sha(member(package,name)) == digest,"Editor004 member differs: "+name)
    notebook = read(package / "kernel/kaggle-notebook.ipynb")
    source = "".join(notebook["cells"][1]["source"])
    values,payloads = bindings(source)
    require(set(payloads) == set(values["FILES"]) == set(values["HASHES"]),"embedded key coverage differs")
    for key,value in payloads.items():
        require(hashlib.sha256(value).hexdigest() == values["HASHES"][key] and
            member(package,values["FILES"][key]).read_bytes() == value,"Editor004 embedded bytes differ")
    require(source == render(payloads,values["FILES"]) and payloads["plan"] == PLAN.read_bytes() and
            read(package / "kernel/kernel-metadata.json") == metadata(plan),"Editor004 executable differs")
    verify_inputs(plan,payloads)
    verify_bundle(package / "source-bundle",plan["branches"]["m2"]["source_bundle_digest"])
    verify_references(read(package / "material-references.json"),json.loads(payloads["model_manifest"]))
    with zipfile.ZipFile(package / values["FILES"]["runtime_wheel"]) as wheel:
        for path in sorted((ROOT / "src/irisx").glob("*.py")):
            require(wheel.read("irisx/"+path.name) == path.read_bytes(),"Editor004 wheel source differs: "+path.name)
    probe_guard(source,PLAN_DIGEST,accepted=True,run_id=RUN)
    draft = {**plan,"approved":False}
    probe_guard(render({**payloads,"plan":canonical_bytes(draft,newline=True)},values["FILES"]),
                digest_value(draft),run_id=RUN)
    # Confirm all old execution gates still reject this new workload.
    from irisx.arc_nvarc_combined import require_live_authorization
    try:
        require_live_authorization(plan)
    except ValidationError:
        pass
    else:
        raise ValidationError("Editor004 piggybacked on an old execution envelope")
    return {"run_id":RUN,"plan_digest":PLAN_DIGEST,"external_calls":0,"owner_editor_only":True,
        "approved_guard_verified":True,"draft_guard_verified":True,"wheel_matches_source":True,
        "generated_hardware_fixture_probe":probe_hardware(source),"analysis_zip_on_pre_setup_failure":True,
        "sandbox_provider_capability":"unobserved; fail closed with diagnostic on unavailable namespace"}


def save_fields(package):
    validate(read(package / "plan.json"))
    meta = read(package / "kernel/kernel-metadata.json")
    require(meta == metadata(read(PLAN)),"save metadata differs")
    notebook = read(package / "kernel/kaggle-notebook.ipynb")
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            require(cell["outputs"] == [] and cell["execution_count"] is None,"notebook was executed")
        if isinstance(cell.get("source"),list):
            cell["source"] = "".join(cell["source"])
    return {"slug":meta["id"],"new_title":meta["title"],"text":json.dumps(notebook),
        "language":"python","kernel_type":"notebook","is_private":True,"enable_gpu":True,
        "enable_tpu":False,"enable_internet":False,"machine_shape":"NvidiaL4","session_timeout_seconds":1800,
        "dataset_data_sources":meta["dataset_sources"],"competition_data_sources":meta["competition_sources"],
        "kernel_data_sources":[],"model_data_sources":[],"kernel_execution_type":"QUICK_SAVE"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--preflight",type=Path)
    args = parser.parse_args()
    require((args.output is None) != (args.preflight is None),"choose stage or preflight")
    print(json.dumps(stage(args.output) if args.output else preflight(args.preflight),indent=2))
