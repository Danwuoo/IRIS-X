"""Retained combined-003 negative replay + authored isolated controls, offline."""

import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from irisx.arc_nvarc_combined import atomic, read, require, sha
from irisx.arc_nvarc_root_audit import audit_root
from irisx.arc_nvarc_semantics import (prepare_numpy, SemanticProgramExecutor, legacy_rotation_claim,
    validate_summary, validate_mix, accept_semantic_record, _typed_grid)
from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tests.test_nvarc_semantics import retained, item, SUMMARY, MIX, INPUT, OUTPUT, response
from tests.nvarc_semantic_strict import WHEEL

EVIDENCE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-003-editor-observation-001"


def rejection(callback):
    try:
        callback()
    except ValidationError as error:
        return str(error)
    raise AssertionError("retained semantic negative was accepted")


def replay(output, sandbox=False):
    require(not output.exists(), "new replay directory required")
    fixture = retained(); original = copy.deepcopy(fixture)
    verification = read(EVIDENCE / "verification.json")
    require(sha(EVIDENCE / "diagnostics.zip") == fixture["archive_sha256"] == verification["archive_sha256"], "retained archive differs")
    files = EVIDENCE / "files"
    for name, digest in verification["files"].items():
        require(sha(files / name) == digest, "retained member differs: " + name)
    for stage, value in fixture["responses"].items():
        ledger = read(files / ("workers/m3/work/stage-ledgers/" + stage + ".json"))
        record = ledger["records"][item()["record_id"]]
        require(record["response"] == value and record["response_digest"] == digest_value(value), "negative fixture reply differs")
    require(read(files / "workers/m3/seed.json") == fixture["seed"], "negative fixture seed differs")
    groups = {"puzzle1": item()["train_demos"], "puzzle2": item()["second_train_demos"]}
    negatives = {
        "summary": rejection(lambda: validate_summary(legacy_rotation_claim(json.loads(fixture["responses"]["summary"]["content"])), groups)),
        "mix": rejection(lambda: validate_mix(json.loads(fixture["responses"]["mix"]["content"]), [3,3],
                         [SUMMARY[key]["operations"] for key in SUMMARY]))}
    rows = read(files / "workers/m2/work/source-result.json")["results"]
    roots = [audit_root(o) for row in rows for o in row["generation_observations"]]
    require(len(roots) == 4 and all(not r["thresholds"][0]["root_survivors"] for r in roots), "retained root-pruning evidence differs")
    control = None; observations = None
    output.mkdir(parents=True)
    if sandbox:
        from irisx.arc_nvarc_upstream import sdg_build_datasets
        sdg_build_datasets()  # Missing host source-filter deps fail before probes.
        prepare_numpy(WHEEL, output / "numpy")
        executor = SemanticProgramExecutor(output / "numpy")
        observations = [executor.probe(fixture["responses"]["input-logic"]["content"], "generate_puzzle_input", seed=s) for s in range(5)]
        negatives["input-logic"] = [rejection(lambda o=o: _typed_grid(o, [3,3], "input")) for o in observations]
        probe = executor.probe(fixture["responses"]["output-logic"]["content"], "generate_puzzle_output", input_grid=[[1,2,3],[4,5,6],[7,8,9]])
        negatives["output-logic"] = rejection(lambda: _typed_grid(probe, [3,3], "output"))
        replies = {stage: response(text) for stage, text in {
            "summary": json.dumps(SUMMARY), "mix": json.dumps(MIX), "input-logic": INPUT, "output-logic": OUTPUT}.items()}
        control = accept_semantic_record(item(), replies, executor)
        atomic(output / "authored-control.json", control)
    else:
        negatives["programs"] = "refused: no verified isolated executor supplied"
    require(fixture == original, "retained raw replies changed")
    report = {"format": "irisx/nvarc-semantic-replay-v1", "archive_sha256": fixture["archive_sha256"],
              "raw_response_digests": {stage: digest_value(v) for stage,v in fixture["responses"].items()},
              "semantic_rejections": negatives, "retained_input_observations": observations,
              "retained_teacher_accepted_pairs": 0, "m2_root_arithmetic": roots,
              "authored_control_accepted_pairs": len(control["pairs"]) if control else 0,
              "generated_program_invocations": 6 + control["program_invocations"] if control else 0,
              "teacher_calls": 0, "model_generations": 0, "external_requests": 0,
              "claim": "local contract engineering; authored pairs do not establish teacher yield or ARC quality"}
    atomic(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sandbox", action="store_true", help="use existing digest-bound Linux NumPy wheel and verified namespace")
    args = parser.parse_args()
    print(json.dumps(replay(args.output, args.sandbox), indent=2))
