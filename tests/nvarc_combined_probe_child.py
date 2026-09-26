"""Installed-wheel CPU tiny Qwen worker / validated saved-response replay."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "site"))
if (root / "deps").is_dir():
    sys.path.insert(0, str(root / "deps"))

def offline(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.bind"}:
        raise RuntimeError("network forbidden in combined installed-wheel child")
sys.addaudithook(offline)

from irisx.arc_nvarc_combined import atomic, sha
from irisx.arc_nvarc_upstream import MANIFEST, SOURCE
from irisx.arc_nvarc_source_runtime import run_source_profile
from irisx.arc_nvarc_sdg import SavedTeacher, run_teacher_pipeline, validate_teacher_response
from irisx.arc_nvarc_sdg_teacher import stage_outcomes
from irisx.canonical import digest_value

assert not MANIFEST.exists() and not SOURCE.exists(), "checkout source accidentally available"
parser = argparse.ArgumentParser()
parser.add_argument("--branch", choices=("m2", "m3"), required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
common = {"branch": args.branch, "parent_run_id": "installed-tiny-and-replay",
          "run_id": "installed-tiny-and-replay-" + args.branch, "plan_digest": "offline-installed-probe",
          "device": None, "contains_evaluator_truth": False}
output = args.output
atomic(output / "worker-state.json", {**common, "phase": "loading"})

def ready(kind):
    atomic(output / "model-ready.json", {**common, "evidence_kind": kind})
    atomic(output / "worker-state.json", {**common, "phase": "work"})

if args.branch == "m2":
    import torch
    torch.set_num_threads(1)
    material = digest_value(json.loads((root / "tiny-export/material-manifest.json").read_bytes()))
    bundle = root / "source-bundle"
    bundle_digest = digest_value(json.loads((bundle / "bundle-manifest.json").read_bytes()))
    calls = []
    def observe(call):
        calls.append(call)
        atomic(output / "call-observations.json", {"kind": "tiny-real-source-call-observations", "events": calls})
    result = run_source_profile(root / "tiny-config.json", root / "visible.json", output / "source-result.json",
        profile="tiny", checkpoint=root / "tiny-export", material_digest=material,
        bundle=bundle, bundle_digest=bundle_digest, model_ready=lambda: ready("actual-tiny-Qwen-CPU"),
        call_observer=observe)
    counters = {"tiny_model_generation_calls": max(r["generation_calls_so_far"] for r in result["results"]),
                "ttt_steps": result["measurements"][0]["ttt"]["steps"]}
else:
    fixture = json.loads((root / "saved-replay.json").read_bytes())
    class ValidatedSavedTeacher(SavedTeacher):
        identity = "saved-response-complete-stage-replay"
        def complete(self, stage, item, prompt):
            return {"text": super().complete(stage, item, prompt), "finish_reason": "eos",
                    "provenance": "fixture finish annotation; no model-generated EOS or tokens"}
        def validate_response(self, stage, response):
            validate_teacher_response(stage, response)
    ready("saved-response-replay; no model load or teacher call")
    ledgers = run_teacher_pipeline([{"record_id": fixture["record_id"]}],
        {stage: stage for stage in ("summary", "mix", "input-logic", "output-logic")},
        ValidatedSavedTeacher(fixture["responses"]), output / "stage-ledgers", seed=24, maximum_calls=0)
    counters = {"teacher_calls": ledgers["reserved_calls"], "validated_saved_stages": len(ledgers["stages"])}
    atomic(output / "replay-result.json", {"kind": "saved-response-stage-replay", "counters": counters,
                                          "stage_outcomes": stage_outcomes(ledgers)})
artifacts = {p.relative_to(output).as_posix(): sha(p) for p in output.rglob("*")
             if p.is_file() and p.name not in {"worker-state.json", "model-ready.json", "stdout.log", "stderr.log"}}
atomic(output / "worker-terminal.json", {**common, "phase": "verified", "status": "complete",
                                         "artifacts": artifacts, "actual_counters": counters})
