"""Copied into an isolated install; imports no checkout modules."""

import hashlib
import json
import math
from pathlib import Path
import os
import sys
import time

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "site"))

# Block network even if a dependency accidentally ignores its offline flags.
def offline(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.bind"}:
        raise RuntimeError("network forbidden in installed-wheel probe")

sys.addaudithook(offline)
from irisx.arc_nvarc_upstream import MANIFEST, SOURCE
assert not MANIFEST.exists() and not SOURCE.exists(), "checkout source accidentally available"
from irisx.arc_nvarc_m2 import create_tiny_qwen_material
from irisx.arc_nvarc_source_runtime import run_source_profile
from irisx.arc_nvarc_training import train_torch_sft, load_compact_model
from irisx.arc_nvarc_representation import export_trained_model, GridTokenizer
from irisx.arc_nvarc_source_bundle import verify_bundle
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from irisx.arc_nvarc_combined import require, supervise, require_live_authorization
import torch

torch.set_num_threads(1)
bundle = root / "source-bundle"
digest = digest_value(json.loads((bundle / "bundle-manifest.json").read_bytes()))
verify_bundle(bundle, digest)
config = json.loads((root / "config.json").read_bytes())
config["profiles"] = {"tiny": {"backend": "qwen35-compact", "model_required": True}}
config["candidate"]["maximum_new_tokens"] = 8
config["candidate"]["dfs_max_expansions"] = 12
config_path = root / "tiny-config.json"
config_path.write_bytes(canonical_bytes(config, newline=True))
visible = root / "visible.json"
visible.write_bytes(canonical_bytes({"isolated": {"train": [
    {"input": [[1]], "output": [[2]]}, {"input": [[3]], "output": [[4]]}],
    "test": [{"input": [[5]]}]}}, newline=True))
# A missing bundle must fail before the model loader has a chance to run.
try:
    run_source_profile(config_path, visible, root / "missing-result.json", profile="tiny",
                       checkpoint=root / "absent-model", material_digest="sha256:" + "0" * 64,
                       bundle=root / "absent-bundle", bundle_digest=digest)
except ValidationError as error:
    assert "source bundle" in str(error)
else:
    raise AssertionError("missing source passed")

model, base_digest = create_tiny_qwen_material(root / "tiny-base")
ids, labels = GridTokenizer(source_chat_newlines=True).encode_pair([[1]], [[2]])
sequences = [{"input_ids": ids, "labels": labels}]
training = {"mode": "full-sft", "max_steps": 1, "learning_rate": 0.0001, "weight_decay": 0.0,
            "seed": 24, "max_sequence_length": 128, "maximum_training_tokens": 128,
            "gradient_accumulation": 1, "checkpoint_every": 1}
observed = train_torch_sft(model, sequences, root / "tiny-training", training,
                           model_identity_digest=base_digest)
identity = observed["identity_digest"]
export_digest = export_trained_model(model, root / "tiny-base", root / "tiny-export",
                                    training_identity_digest=identity)
result = run_source_profile(config_path, visible, root / "source-result.json", profile="tiny",
                            checkpoint=root / "tiny-export", material_digest=export_digest,
                            bundle=bundle, bundle_digest=digest)
assert observed["steps"] == 1 and result["training_identity_digest"] == identity
assert result["measurements"][0]["ttt"]["steps"] == 1
assert result["source_bundle_digest"] == digest
assert not MANIFEST.exists() and not SOURCE.exists()

def verify_tiny(output):
    value = json.loads((output / "source-result.json").read_bytes())
    observation = value["measurements"][0]["ttt"]
    require(value["profile"] == "tiny" and value["material_digest"] == export_digest and
            value["source_bundle_digest"] == digest and value["training_identity_digest"] == identity and
            observation["status"] == "complete" and observation["steps"] == 1 and
            math.isfinite(observation["last_loss"]), "independent tiny child verification failed")
    calls = max(r["generation_calls_so_far"] for r in value["results"])
    require(calls == 4, "tiny child call ceiling differs")
    events = json.loads((output / "call-observations.json").read_bytes())["events"]
    generation = [event for event in events if event["kind"] == "generation"]
    require([(event["index"], event["status"]) for event in generation] ==
            [(i, status) for i in range(1, 5) for status in ("reserved", "complete")],
            "tiny child did not persist each reservation before completion")
    return {"tiny_model_generation_calls": calls, "ttt_steps": 1}

def verify_saved(output):
    from irisx.arc_nvarc_sdg import validate_teacher_response
    value = json.loads((output / "replay-result.json").read_bytes())
    require(value["kind"] == "saved-response-stage-replay", "replay mislabeled")
    for stage in ("summary", "mix", "input-logic", "output-logic"):
        ledger = json.loads((output / "stage-ledgers" / (stage + ".json")).read_bytes())
        require(ledger["reserved_calls"] == ledger["maximum_calls"] == 0, "saved replay claimed real calls")
        for record in ledger["records"].values():
            require(record["status"] == "complete" and record["response_digest"] == digest_value(record["response"]),
                    "saved child record binding differs")
            validate_teacher_response(stage, dict(record["response"]))
    return {"teacher_calls": 0, "validated_saved_stages": 4}

children = {branch: {"command": [sys.executable, "-I", str(root / "combined-child.py"), "--branch", branch,
                                "--output", str(root / "combined-cpu" / branch)], "cwd": root}
            for branch in ("m2", "m3")}
combined = supervise(children, root / "combined-cpu", run_id="installed-tiny-and-replay",
    plan_digest="offline-installed-probe", deadline=time.monotonic() + 120,
    readiness_seconds=60, validators={"m2": verify_tiny, "m3": verify_saved})
assert combined["outcome"] == "complete", json.dumps(combined)
draft = json.loads((root / "combined-plan.json").read_bytes())
try:
    require_live_authorization(draft)
except ValidationError as error:
    assert "inert" in str(error)
else:
    raise AssertionError("installed combined draft activated")
summary = {"installed_wheel": True, "repository_source_available": False, "network_calls": 0,
           "tiny_sft_steps": observed["steps"], "source_bundle_digest": digest,
           "ttt_steps": result["measurements"][0]["ttt"]["steps"],
           "generation_calls": max(x["generation_calls_so_far"] for x in result["results"]),
           "verification_calls": max(x["verification_calls_so_far"] for x in result["results"]),
           "platform": sys.platform, "torch": torch.__version__,
           "combined_cpu_probe": {"outcome": combined["outcome"],
                                  "tiny_source_generation_calls": combined["branches"]["m2"]["actual_counters"]["tiny_model_generation_calls"],
                                  **combined["branches"]["m3"]["actual_counters"],
                                  "active_devices": "CPU only; no GPU evidence"}}
(root / "probe-result.json").write_bytes(canonical_bytes(summary, newline=True))
print(json.dumps(summary))
