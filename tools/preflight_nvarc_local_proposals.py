"""Build two INERT review bundles. No provider or model execution entry exists."""

import argparse
import copy
import json
from pathlib import Path
import sys
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from irisx.arc_nvarc_combined import atomic, read, require, sha
from irisx.arc_nvarc_semantics import PROFILE, PROMPTS, NUMPY_WHEEL_SHA256, NUMPY_INVENTORY_DIGEST
from irisx.arc_nvarc_sdg import render_source_teacher_prompt
from irisx.canonical import digest_value
from tests.test_nvarc_semantics import item, SUMMARY, MIX, INPUT, OUTPUT, response
from tools.stage_nvarc_combined import TOKENIZER_ROOT, TOKENIZER_FILES
from tools import irisx_build_backend as build

CONFIGS = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs"


def stage(output, tokenizer=False):
    require(not output.exists(), "new local proposal directory required")
    output.mkdir(parents=True)
    reports = {}
    for name in ("m2-root-threshold-proposal-001", "m3-rule-contract-proposal-001"):
        plan = read(CONFIGS / (name + ".json"))
        require(plan["approved"] is False and plan["owner_decision"] is None and
                plan["status"] == "inert-owner-decision-required" and
                all(type(v) is int and v == 0 for v in plan["external_allowances"].values()),
                "proposal cannot grant external authority")
        limits = plan["proposed_limits"]
        if name.startswith("m2"):
            shared = plan["shared"]
            calls = len(plan["arms"]) * shared["calls_per_arm"]
            sequences = calls * shared["beams_per_call"]
            require(calls == limits["generation_calls"] and sequences == limits["returned_sequences"] and
                    calls * shared["dfs_max_expansions"] == limits["dfs_forwards"] and
                    sequences * 8 == limits["verification_forwards"], "proposal model-forward ceiling differs")
            require([a["cumulative_probability_threshold"] for a in plan["arms"]] == [0.2, 0.1, 0.02], "reviewed arms differ")
        else:
            require(plan["teacher_profile"] == PROFILE and
                    sum(sum(x.values()) for x in limits["stage_tokens"].values()) == limits["reserved_tokens"] == 28160,
                    "teacher reserved tokens differ")
            atomic(output / name / "prompts.json", PROMPTS)
            atomic(output / name / "seed.json", item())
        atomic(output / name / "proposal.json", plan)
        reports[name] = {"run_id": plan["run_id"], "proposal_digest": digest_value(plan),
                         "execution_authorized": False, "proposed_limits": limits}
    # Count every dependent prompt using authored controls and the CACHED pinned
    # tokenizer. These are input-token counts only; no model is loaded.
    token_counts = None
    if tokenizer:
        from transformers import AutoTokenizer
        manifest_path = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-003-editor-observation-001/files/model-manifest.json"
        require(sha(manifest_path) == "0079d074151065b317da97aab60cea166498d08a1c2883c005dd12a1a6017667", "retained teacher manifest differs")
        entries = {entry["path"]: entry for entry in read(manifest_path)["files"]}
        for name in TOKENIZER_FILES:
            path, entry = TOKENIZER_ROOT / name, entries[name]
            require(not path.is_symlink() and path.stat().st_size == entry["byte_size"] and
                    "sha256:" + sha(path) == entry["content_digest"], "cached tokenizer material differs: " + name)
        cached = AutoTokenizer.from_pretrained(TOKENIZER_ROOT, local_files_only=True)
        record = copy.deepcopy(item())
        replies = {"summary": json.dumps(SUMMARY), "mix": json.dumps(MIX), "input-logic": INPUT, "output-logic": OUTPUT}
        token_counts = {}
        for key in replies:
            prompt = render_source_teacher_prompt(key, record, PROMPTS[key], profile=PROFILE)
            tokens = cached.apply_chat_template([{"role": "user", "content": prompt}], tokenize=True,
                add_generation_prompt=True, enable_thinking=False, return_tensors="pt", return_dict=False)
            require(tokens.ndim == 2 and tokens.shape[0] == 1, "cached tokenizer did not return one input tensor")
            token_counts[key] = int(tokens.shape[-1])
            require(token_counts[key] <= limits["stage_tokens"][key]["input"], "authored prompt exceeds unchanged cap")
            record.setdefault("stage_responses", {})[key] = {"content": replies[key]}
    source_paths = ("src/irisx/arc_nvarc_semantics.py", "src/irisx/arc_nvarc_sdg.py",
                    "src/irisx/arc_nvarc_sdg_teacher.py",
                    "src/irisx/arc_nvarc_candidates.py", "src/irisx/arc_nvarc_source_runtime.py",
                    "src/irisx/arc_nvarc_threshold_trial.py", "tests/nvarc_threshold_strict.py",
                    "src/irisx/arc_nvarc_root_audit.py", "tools/nvarc_sdg_semantic_namespace.sh",
                    "tests/test_nvarc_semantics.py", "tests/nvarc_semantic_strict.py",
                    "tests/test_nvarc_root_audit.py", "tests/fixtures/nvarc_combined_003_semantic_negative.json")
    wheel = output / "wheel" / build.build_wheel(str(output / "wheel"))
    with zipfile.ZipFile(wheel) as archive:
        for name in source_paths:
            if name.startswith("src/"):
                require(archive.read(name[4:]) == (ROOT / name).read_bytes(), "proposal wheel source differs")
    probe = output / "wheel-guard-probe.py"
    probe.write_text('''import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from irisx.arc_nvarc_semantics import compose_order
from irisx.arc_nvarc_threshold_trial import compare_thresholds
from irisx.arc_nvarc_sdg_teacher import _run_bound
assert compose_order([2,3],[["rotate180"]])==[5,4,3,2,1,0]
try:
 _run_bound({"teacher_profile":"qwen-rule-contract-v3","approved":True,"owner_decision":"Decision 0037"},
            *([Path("ABSENT")]*5))
except Exception as e:
 assert "profile is inert" in str(e),str(e)
else: raise AssertionError("old envelope activated semantic teacher")
assert "torch" not in sys.modules
print("packaged semantic guard rejected before ML imports; zero model calls")
''', encoding="utf-8")
    completed = subprocess.run([sys.executable, "-I", str(probe), str(wheel)], capture_output=True, text=True, timeout=15)
    require(completed.returncode == 0, "packaged proposal guard failed: " + completed.stderr)
    report = {"format": "irisx/nvarc-local-proposal-preflight-v1", "proposals": reports,
              "wheel_matches_source": True, "packaged_guard": completed.stdout.strip(),
              "semantic_sandbox_numpy": {"wheel_sha256": NUMPY_WHEEL_SHA256,
                                         "inventory_digest": NUMPY_INVENTORY_DIGEST},
              "source_sha256": {name: sha(ROOT / name) for name in source_paths},
              "bundle_sha256": {p.relative_to(output).as_posix(): sha(p) for p in output.rglob("*") if p.is_file()},
              "cached_tokenizer_authored_prompt_tokens": token_counts,
              "external_requests": 0, "model_generations": 0,
              "claim": "inert review bundles; no executable Kaggle metadata or kernel"}
    atomic(output / "preflight.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tokenizer", action="store_true")
    args = parser.parse_args()
    print(json.dumps(stage(args.output, args.tokenizer), indent=2))
