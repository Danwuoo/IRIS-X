"""Digest-bound local Editor replay; no source acquisition, scoring or model calls."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from irisx.arc_nvarc_combined import atomic, read, require, sha, verify_envelope
from irisx.arc_nvarc_combined_worker import verify_branch, partial_teacher_counts
from irisx.arc_nvarc_sdg import validate_teacher_response, render_source_teacher_prompt, run_teacher_pipeline
from irisx.arc_nvarc_teacher_spec import PROFILE, PROMPTS, paired_seed
from irisx.canonical import digest_value
from tests.test_nvarc_combined_repair import SUMMARY, MIX, INPUT_CODE, OUTPUT_CODE, SpecSavedTeacher, response
from tools.stage_nvarc_combined import TOKENIZER_ROOT, M3

EVIDENCE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-002-editor-observation-001"
ARCHIVE_SHA = "b07846c87c295962b2cdf9717b872ab4fbc52af17831f2c8586c2f7993670948"


def replay(output, *, tokenizer=False):
    require(not output.exists(), "new local replay directory required")
    original = read(EVIDENCE / "verification.json")
    require(sha(EVIDENCE / "diagnostics.zip") == ARCHIVE_SHA == original["archive_sha256"], "Editor archive differs")
    files = EVIDENCE / "files"
    require({p.relative_to(files).as_posix() for p in files.rglob("*") if p.is_file()} == set(original["files"]),
            "Editor extracted inventory differs")
    for name, digest in original["files"].items():
        require(sha(files / name) == digest, "Editor extracted file differs: " + name)
    plan = read(files / "plan.json")
    require(plan == read(EVIDENCE.parent / "combined-approved-002/plan.json"), "Editor retained approved plan differs")
    counts = verify_branch(plan, "m2", files / "workers/m2")
    terminal = verify_envelope(files / "workers/m2", run_id=plan["run_id"], plan_digest=digest_value(plan), branch="m2")
    require(terminal["actual_counters"] == counts, "legacy M2 terminal accounting changed")
    partial = partial_teacher_counts(plan, files / "workers/m3")
    rows = read(files / "workers/m2/work/source-result.json")["results"]
    observations = [o for row in rows for o in row["generation_observations"]]
    require(len(observations) == 4 and all(o["expansions"] == 1 and o["completed_candidates"] == 0 and
            o["stop_reason"] == "no_valid_candidate" and o["max_new_tokens"] == 64 for o in observations),
            "Editor root-exhaustion observations differ")
    raw_mix = next(iter(read(files / "workers/m3/work/stage-ledgers/mix.json")["records"].values()))["response"]
    rejection = {}
    for profile in ("qwen-direct-complete-v1", PROFILE):
        try:
            validate_teacher_response("mix", copy.deepcopy(raw_mix), profile=profile)
        except Exception as error:
            rejection[profile] = str(error)
        else:
            raise AssertionError("retained non-EOS mix was accepted")
    # Isolate arithmetic/schema defense independently of the real EOS failure.
    counterfactual = {**raw_mix, "finish_reason": "eos"}
    try:
        validate_teacher_response("mix", counterfactual, profile=PROFILE)
    except Exception as error:
        schema_rejection = str(error)
    else:
        raise AssertionError("old free-form self-corrections passed the JSON schema")
    seed = paired_seed(read(M3 / "seed.json"))["record"]
    record = seed["record_id"]
    saved = {"summary:" + record: response(json.dumps(SUMMARY)), "mix:" + record: response(json.dumps(MIX)),
             "input-logic:" + record: response(INPUT_CODE), "output-logic:" + record: response(OUTPUT_CODE)}
    provider = SpecSavedTeacher(saved)
    replayed = run_teacher_pipeline([seed], PROMPTS, provider, output / "authored-fixture-ledgers", seed=24, maximum_calls=0)
    token_counts = None
    if tokenizer:
        from transformers import AutoTokenizer
        cached = AutoTokenizer.from_pretrained(TOKENIZER_ROOT, local_files_only=True)
        token_counts = {}
        from irisx.arc_nvarc_teacher_profile import LIMITS
        for stage, prompt in provider.rendered:
            tokens = cached.apply_chat_template([{"role": "user", "content": prompt}], tokenize=True,
                add_generation_prompt=True, enable_thinking=False, return_tensors="pt", return_dict=False)
            require(tokens.ndim == 2 and tokens.shape[0] == 1, "cached tokenizer did not return one input tensor")
            token_counts[stage] = int(tokens.shape[-1])
            require(token_counts[stage] <= LIMITS[stage]["input"], "candidate fixture input exceeds unchanged stage cap")
    report = {"format": "irisx/nvarc-combined-repair-replay-v1", "archive_sha256": ARCHIVE_SHA,
        "external_calls": 0, "model_generations": 0, "m2_legacy_semantics_and_envelope": counts,
        "m3_legacy_partial_ledger": partial, "retained_mix_rejections": rejection,
        "counterfactual_eos_schema_rejection": schema_rejection,
        "m2_root_inference": "Given the bound submitted DFS, 64-token budget and one expansion, every legal root digit had probability <=0.2; exact logits and top masked symbol remain unobserved.",
        "authored_fixture_stages": len(replayed["stages"]), "authored_fixture_reserved_calls": replayed["reserved_calls"],
        "candidate_profile": PROFILE, "cached_tokenizer_fixture_input_tokens": token_counts,
        "contains_evaluator_truth": False,
        "claim": "local engineering replay; authored fixture responses are not teacher output or accepted SDG pairs"}
    atomic(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tokenizer", action="store_true", help="count fixture prompts with the retained local tokenizer")
    args = parser.parse_args()
    print(json.dumps(replay(args.output, tokenizer=args.tokenizer), indent=2))
