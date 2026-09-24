"""Bounded synthetic compact-4B pilot; no provider calls at import time."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping

from .arc_nvarc_kaggle import run as run_kaggle, validate_hardware
from .arc_nvarc_representation import (MODEL_REVISION, convert_qwen35_checkpoint,
                                        verify_model_material, verify_source_model_material)
from .arc_nvarc_runtime import (atomic_json, build_outbound, build_result,
                                finalize_interrupted, make_binding, make_workload,
                                new_checkpoint, verify_outbound, verify_result)
from .canonical import digest_value
from .errors import ValidationError


RUN_ID_PREFIX = "nvarc-4b-compact-complete-"
KERNEL_ID_PREFIX = "danielwuu/iris-x-4b-compact-complete-"
LEGACY_DATASET_DIR = "trial-002-smoke-002"
LEGACY_DATASET_FILES = frozenset({
    "bindings/run.json", "cases/solver-cases.json", "manifest.json",
    "runtime/core.py", "runtime/dependencies.json", "runtime/runner.py",
    "sources/model-manifest.json", "sources/nvarc-manifest.json",
    "sources/wheel-manifest.json",
})
MODEL_DIGEST = "sha256:8f27407e1b0ee4dd7a5b4d62d39af9b356ba86b5701dd93eafba052febe9c72f"
WHEEL_DIGEST = "sha256:d24d85f791788621166fa05d7db51c03f7c72c046af4923096b12863f7e7dfa1"
VISIBLE_DIGEST = "sha256:0140be6128bd1eb653681c684c63439ed775dc1c4dc25668249dfc03546cea22"
PLAN_FIELDS = {"format", "approved", "owner_authorization", "run_id",
               "visible_source_digest", "task_count", "test_output_count", "kernel_id",
               "provider", "dataset_ref", "dataset_version", "competition_ref",
               "model_revision", "model_manifest_digest", "wheel_manifest_digest",
               "runtime_wheels", "maximum_paid_usd", "maximum_kernel_pushes",
               "maximum_output_retrievals", "maximum_preversion_transport_retries",
               "maximum_teacher_calls", "maximum_training_steps",
               "maximum_training_tokens", "maximum_generation_calls",
               "maximum_dfs_forwards", "maximum_verification_forwards",
               "worker_timeout_seconds", "retention", "config"}


def final_kernel_id(run_id: str) -> str:
    if (not isinstance(run_id, str) or not run_id.startswith(RUN_ID_PREFIX) or
            len(run_id) != len(RUN_ID_PREFIX) + 3 or
            not run_id[-3:].isascii() or not run_id[-3:].isdigit()):
        raise ValidationError("compact pilot run identity differs")
    return KERNEL_ID_PREFIX + run_id[-3:]


def validate_plan(plan: Mapping[str, Any], *, approved: bool) -> None:
    if not isinstance(plan, dict) or set(plan) != PLAN_FIELDS:
        raise ValidationError("compact pilot plan schema differs")
    config = plan.get("config")
    ttt = config.get("ttt") if isinstance(config, dict) else None
    if (plan.get("format") != "irisx/nvarc-compact-complete-plan" or
            plan.get("model_revision") != MODEL_REVISION or
            plan.get("visible_source_digest") != VISIBLE_DIGEST or
            plan.get("task_count") != 2 or plan.get("test_output_count") != 4 or
            plan.get("model_manifest_digest") != MODEL_DIGEST or
            plan.get("wheel_manifest_digest") != WHEEL_DIGEST or
            not isinstance(plan.get("runtime_wheels"), dict) or
            set(plan["runtime_wheels"]) != {"transformers", "peft", "safetensors", "tokenizers", "accelerate"} or
            any(not isinstance(value, str) or not value.endswith(".whl")
                for value in plan["runtime_wheels"].values()) or
            plan.get("dataset_ref") != "danielwuu/irisx-arc-agi-2-trial-002-smoke-001" or
            plan.get("dataset_version") != 2 or
            plan.get("competition_ref") != "arc-prize-2026-arc-agi-2" or
            plan.get("provider") != "Kaggle" or plan.get("maximum_paid_usd") != 0 or
            plan.get("maximum_kernel_pushes") != 1 or
            plan.get("maximum_output_retrievals") != 1 or
            plan.get("maximum_preversion_transport_retries") != 1 or
            plan.get("maximum_teacher_calls") != 0 or
            not isinstance(config, dict) or not isinstance(ttt, dict) or
            config.get("worker_count") != 1 or config.get("decoding") != "bounded-dfs" or
            config.get("ttt", {}).get("enabled") is not True or
            plan.get("maximum_training_steps") != 2 * ttt.get("steps", -1) or
            plan.get("maximum_training_tokens") != 2 * ttt.get("steps", -1) * ttt.get("max_sequence_length", -1) or
            plan.get("maximum_generation_calls") != 2 * config.get("maximum_calls_per_task", -1) or
            plan.get("maximum_dfs_forwards") != plan.get("maximum_generation_calls", -1) * config.get("dfs_max_expansions", -1) or
            plan.get("maximum_verification_forwards") != plan.get("maximum_generation_calls", -1) * config.get("beams_per_call", -1) * 8 or
            plan.get("worker_timeout_seconds", 0) > config.get("session_budget_seconds", -1) - config.get("finalization_reserve_seconds", -1) or
            not isinstance(plan.get("retention"), str) or not plan["retention"]):
        raise ValidationError("compact pilot plan identity or ceilings differ")
    expected_kernel_id = final_kernel_id(plan.get("run_id"))
    if approved:
        if (plan.get("approved") is not True or plan.get("kernel_id") != expected_kernel_id or
                not isinstance(plan.get("owner_authorization"), str) or
                not plan["owner_authorization"].strip()):
            raise ValidationError("compact pilot has no exact owner authorization")
    elif (plan.get("approved") is not False or plan.get("owner_authorization") is not None or
          plan.get("kernel_id") != "DRAFT-DO-NOT-PUSH/" + plan["run_id"]):
        raise ValidationError("compact pilot draft must be unapproved")
    if "UNBOUND" in json.dumps(plan) or "PLACEHOLDER" in json.dumps(plan):
        raise ValidationError("compact pilot contains an unbound value")


def visible_workload(source: Mapping[str, Any]) -> dict[str, Any]:
    # The source is visibly synthetic and contains no labelled test outputs.
    if (not isinstance(source, dict) or not source or
            any(not isinstance(task, dict) or set(task) != {"train", "test"} or
                not isinstance(task["test"], list) or
                any(not isinstance(item, dict) or set(item) != {"input"}
                    for item in task["test"])
                for task in source.values())):
        raise ValidationError("pilot visible source contains test truth or extra metadata")
    return make_workload(source, source_digest=digest_value(source))


def prepare(plan_path: Path, visible_path: Path, model_manifest_path: Path,
            wheel_manifest_path: Path) -> dict[str, Any]:
    plan = json.loads(plan_path.read_bytes())
    validate_plan(plan, approved=False)
    source = json.loads(visible_path.read_bytes())
    workload = visible_workload(source)
    if (workload["source_digest"] != plan["visible_source_digest"] or
            workload["task_count"] != plan["task_count"] or
            workload["test_output_count"] != plan["test_output_count"]):
        raise ValidationError("visible pilot workload differs from plan")
    model = json.loads(model_manifest_path.read_bytes())
    wheels = json.loads(wheel_manifest_path.read_bytes())
    if (model.get("manifest_digest") != MODEL_DIGEST or
            digest_value(model.get("files")) != MODEL_DIGEST or
            model.get("revision") != MODEL_REVISION or
            wheels.get("manifest_digest") != WHEEL_DIGEST or
            digest_value(wheels.get("files")) != WHEEL_DIGEST):
        raise ValidationError("pinned model or wheel manifest differs")
    if not set(plan["runtime_wheels"].values()).issubset({item["path"] for item in wheels["files"]}):
        raise ValidationError("required offline wheels are absent from manifest")
    # Use the actual checked-in candidate schema before any conversion.
    make_binding(workload, run_id=plan["run_id"], model_digest=MODEL_DIGEST,
                 data_digest=digest_value(workload), tokenizer_digest=MODEL_DIGEST,
                 runtime_digest=WHEEL_DIGEST, config=plan["config"])
    return {"run_id": plan["run_id"], "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
            "source_digest": workload["source_digest"],
            "tasks": workload["task_count"], "tests": workload["test_output_count"],
            "model_files": len(model["files"]), "wheel_files": len(wheels["files"]),
            "approved": False}


def _source_inventory(model_manifest: Mapping[str, Any], wheel_manifest: Mapping[str, Any],
                      base: Path, output: Path) -> tuple[str, set[str], dict[str, set[str]]]:
    """Translate the already pinned Dataset v2 manifest to compact converter format."""
    if (model_manifest.get("manifest_digest") != MODEL_DIGEST or
            digest_value(model_manifest.get("files")) != MODEL_DIGEST or
            wheel_manifest.get("manifest_digest") != WHEEL_DIGEST or
            digest_value(wheel_manifest.get("files")) != WHEEL_DIGEST):
        raise ValidationError("Dataset v2 material manifest differs")
    model_names = {item["path"] for item in model_manifest["files"]}
    wheel_names = {item["path"] for item in wheel_manifest["files"]}
    legacy = base / LEGACY_DATASET_DIR
    legacy_nodes = {path.relative_to(legacy).as_posix() for path in legacy.rglob("*")}
    expected_nodes = set(LEGACY_DATASET_FILES)
    for name in LEGACY_DATASET_FILES:
        expected_nodes.update(path.as_posix() for path in Path(name).parents if path != Path("."))
    if (len(model_names) != len(model_manifest["files"]) or
            len(wheel_names) != len(wheel_manifest["files"]) or
            model_names & wheel_names or
            {path.name for path in base.iterdir()} != model_names | wheel_names | {LEGACY_DATASET_DIR} or
            legacy.is_symlink() or not legacy.is_dir() or legacy_nodes != expected_nodes or
            any(path.is_symlink() or not (path.is_file() or path.is_dir())
                for path in legacy.rglob("*"))):
        raise ValidationError("Dataset v2 material inventory is not closed")
    for item in wheel_manifest["files"]:
        path = base / item["path"]
        if (path.is_symlink() or not path.is_file() or path.stat().st_size != item["byte_size"] or
                "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() != item["content_digest"]):
            raise ValidationError("offline wheel member differs")
    translated = {"format": "irisx/nvarc-base-model-material", "revision": MODEL_REVISION,
                  "files": [{"path": item["path"], "sha256": item["content_digest"][7:],
                             "bytes": item["byte_size"]} for item in model_manifest["files"]]}
    atomic_json(output, translated)
    return digest_value(translated), wheel_names, {LEGACY_DATASET_DIR: set(LEGACY_DATASET_FILES)}


def preflight(base: Path, competition_source: Path) -> dict[str, Any]:
    if (os.environ.get("HF_HUB_OFFLINE") != "1" or
            os.environ.get("TRANSFORMERS_OFFLINE") != "1" or
            importlib.util.find_spec("torchao") is not None or
            not competition_source.is_file() or
            competition_source.name != "arc-agi_training_challenges.json"):
        raise ValidationError("offline dependency or official mount preflight failed")
    versions = {name: importlib.metadata.version(name) for name in
                ("torch", "transformers", "peft", "safetensors", "tokenizers", "accelerate")}
    if (f"{sys.version_info.major}.{sys.version_info.minor}" != "3.12" or
            any(versions[name] != expected for name, expected in
                {"transformers": "5.8.1", "peft": "0.21.0", "safetensors": "0.8.0",
                 "tokenizers": "0.22.2", "accelerate": "1.10.1"}.items())):
        raise ValidationError("installed dependency versions differ")
    hardware = validate_hardware(1)
    return {"dependencies": versions, "hardware": hardware,
            "competition_mount_present": True, "competition_challenges_read": False,
            "base_root": str(base)}


def preflight_package(plan_path: Path, visible_path: Path, model_manifest_path: Path,
                      wheel_manifest_path: Path, base: Path, competition_source: Path,
                      output: Path) -> dict[str, Any]:
    """Separate no-model-load gate for an approved private environment."""
    plan = json.loads(plan_path.read_bytes())
    validate_plan(plan, approved=True)
    workload = visible_workload(json.loads(visible_path.read_bytes()))
    if workload["source_digest"] != plan["visible_source_digest"]:
        raise ValidationError("visible pilot source differs from plan")
    observation = preflight(base, competition_source)
    translation = output.with_name(output.stem + "-source-model-manifest.json")
    source_digest, extras, extra_dirs = _source_inventory(json.loads(model_manifest_path.read_bytes()),
                                               json.loads(wheel_manifest_path.read_bytes()),
                                               base, translation)
    verify_source_model_material(base, source_digest, MODEL_REVISION,
                                 manifest_path=translation, allowed_extra_files=extras,
                                 allowed_extra_directories=extra_dirs)
    observation["source_model_manifest_digest"] = source_digest
    observation["run_id"] = plan["run_id"]
    atomic_json(output, observation)
    return observation


def run(plan_path: Path, visible_path: Path, model_manifest_path: Path,
        wheel_manifest_path: Path, base: Path, competition_source: Path,
        output: Path, runtime_digest: str) -> dict[str, Any]:
    plan = json.loads(plan_path.read_bytes())
    validate_plan(plan, approved=True)
    workload = visible_workload(json.loads(visible_path.read_bytes()))
    if (workload["source_digest"] != plan["visible_source_digest"] or
            workload["task_count"] != plan["task_count"] or
            workload["test_output_count"] != plan["test_output_count"]):
        raise ValidationError("visible pilot workload differs from plan")
    make_binding(workload, run_id=plan["run_id"], model_digest=MODEL_DIGEST,
                 data_digest=digest_value(workload), tokenizer_digest=MODEL_DIGEST,
                 runtime_digest=WHEEL_DIGEST, config=plan["config"])
    if output.exists() and any(output.iterdir()):
        raise ValidationError("compact pilot output identity already exists; no model retry")
    if not runtime_digest.startswith("sha256:") or len(runtime_digest) != 71:
        raise ValidationError("current runtime wheel digest required")
    output.mkdir(parents=True, exist_ok=True)
    phase_path = output / "phase.json"
    phases: list[dict[str, Any]] = []
    started = time.monotonic()

    def phase(name: str, **fields: Any) -> None:
        try:
            import psutil
            rss_mib = int(psutil.Process().memory_info().rss / 1024**2)
        except ImportError:
            rss_mib = None
        try:
            import resource
            # Kaggle Linux reports ru_maxrss in KiB. It is cumulative, so
            # adjacent phase records reveal the peak reached by each phase.
            process_peak_rss_mib = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
        except ImportError:
            process_peak_rss_mib = None
        phases.append({"name": name, "elapsed_seconds": time.monotonic() - started,
                       "rss_mib": rss_mib, "process_peak_rss_mib": process_peak_rss_mib,
                       **fields})
        atomic_json(phase_path, {"run_id": plan["run_id"], "phases": phases})

    try:
        observation = preflight(base, competition_source)
        phase("preflight", **observation)
        model_manifest = json.loads(model_manifest_path.read_bytes())
        wheel_manifest = json.loads(wheel_manifest_path.read_bytes())
        source_digest, extras, extra_dirs = _source_inventory(model_manifest, wheel_manifest, base,
                                                   output / "source-model-manifest.json")
        phase("source-inventory", source_manifest_digest=source_digest)
        import torch
        torch.cuda.reset_peak_memory_stats()
        compact = output / "compact-model"
        converted = convert_qwen35_checkpoint(base, compact, model_revision=MODEL_REVISION,
                    model_manifest_digest=source_digest,
                    base_manifest_path=output / "source-model-manifest.json",
                    allowed_extra_source_files=extras,
                    allowed_extra_source_directories=extra_dirs)
        phase("compact-reload", compact_material_digest=converted["material_digest"],
              tied_embeddings=converted["tied_embeddings"],
              peak_memory_mib=int(torch.cuda.max_memory_allocated() / 1024**2))
        binding = make_binding(workload, run_id=plan["run_id"],
                               model_digest=converted["material_digest"],
                               data_digest=digest_value(workload),
                               tokenizer_digest=converted["vocabulary_manifest"]["identity_digest"],
                               runtime_digest=runtime_digest, config=plan["config"])
        outbound = output / "outbound.zip"
        build_outbound(outbound, binding, workload)
        phase("outbound", identity_digest=binding["identity_digest"])
        result_path = output / "result.zip"
        result_digest = run_kaggle(outbound, compact, competition_source, result_path,
                                   output / "checkpoint.json", source_policy="mount-presence-only")
        verify_result(result_path, binding, workload)
        phase("terminal", result_digest=result_digest)
        return {"status": "terminal", "result_digest": result_digest,
                "identity_digest": binding["identity_digest"], "phases": phases}
    except BaseException as exc:
        phase("failed", failure_type=type(exc).__name__, failure_detail=str(exc)[:300])
        raise


def finalize_after_timeout(output: Path, *, reason: str = "session_limit") -> str:
    """Package charged pending tasks once; never restart inference."""
    if reason not in {"session_limit", "worker_crash"}:
        raise ValidationError("unsupported interruption finalization reason")
    outbound = output / "outbound.zip"
    checkpoint_path = output / "checkpoint.json"
    result_path = output / "result.zip"
    if result_path.exists() or not outbound.is_file() or not checkpoint_path.is_file():
        raise ValidationError("timeout finalization needs unfinished outbound/checkpoint")
    binding, workload, _ = verify_outbound(outbound)
    checkpoint = json.loads(checkpoint_path.read_bytes())
    finalize_interrupted(checkpoint, workload, reason=reason)
    atomic_json(checkpoint_path, checkpoint)
    return build_result(result_path, binding, workload, checkpoint,
                        {"format": "irisx/nvarc-execution", "run_id": binding["run_id"],
                         "failure": reason, "internet_enabled": False,
                         "external_paid_cost_usd": 0})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One compact 4B synthetic full-flow pilot")
    parser.add_argument("command", choices=("prepare", "preflight", "run", "verify", "finalize-timeout"))
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--visible", type=Path)
    parser.add_argument("--model-manifest", type=Path)
    parser.add_argument("--wheel-manifest", type=Path)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--competition-source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runtime-digest")
    parser.add_argument("--reason", choices=("session_limit", "worker_crash"),
                        default="session_limit")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(args.plan, args.visible, args.model_manifest, args.wheel_manifest)
    elif args.command == "preflight":
        result = preflight_package(args.plan, args.visible, args.model_manifest,
                                   args.wheel_manifest, args.base,
                                   args.competition_source, args.output)
    elif args.command == "run":
        result = run(args.plan, args.visible, args.model_manifest, args.wheel_manifest,
                     args.base, args.competition_source, args.output, args.runtime_digest)
    elif args.command == "finalize-timeout":
        result = {"result_digest": finalize_after_timeout(args.output, reason=args.reason)}
    else:
        binding, workload, _ = verify_outbound(args.output / "outbound.zip")
        material = verify_model_material(args.output / "compact-model", binding["model_digest"])
        result = {"result_digest": verify_result(args.output / "result.zip", binding, workload),
                  "compact_material_digest": digest_value(material)}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
