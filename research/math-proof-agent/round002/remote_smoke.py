"""Bounded non-scoring MATH-002 technical smoke, for a controlled subprocess.

The notebook bootstrap installs the exact runtime and starts this module with
PYTHONHASHSEED=0, no -I/-E, and a deadline covering bootstrap plus this worker.
This module never pushes notebooks or executes generated Lean. Lean qualification
is a separate mandatory gate; model success here never opens panel scoring.
"""
from __future__ import annotations

import argparse
import gc
import importlib.metadata
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_adapter import (JaxQwen3Adapter, PreflightError, canonical_hash,
                           sha256_file, tpu_preflight, transformers_reference)


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def download_candidate(candidate: dict, cache_dir: Path, deadline: float) -> tuple[Path, dict]:
    from huggingface_hub import hf_hub_download

    started = time.monotonic()
    files = []
    model_dir = None
    for item in candidate["files"]:
        if time.monotonic() >= deadline:
            raise TimeoutError("Deadline before source acquisition")
        # token=False disables both explicit and automatically saved HF credentials.
        path = Path(hf_hub_download(candidate["repo_id"], item["path"],
                                   revision=candidate["revision"], cache_dir=str(cache_dir),
                                   token=False, local_files_only=False))
        if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise PreflightError("Downloaded source fingerprint mismatch: " + item["path"])
        model_dir = path.parent
        files.append(item)
    return model_dir, {"seconds": time.monotonic() - started,
                       "bytes": sum(item["bytes"] for item in files),
                       "files_fingerprint": canonical_hash(files), "files": files}


def cpu_reference_subprocess(model_dir, token_ids, out_dir, deadline) -> dict:
    import numpy as np

    atomic_json(out_dir / "reference-input.json", {"token_ids": token_ids})
    command = [sys.executable, "-P", "-s", "-B", str(Path(__file__).resolve()), "--reference",
               "--model-dir", str(model_dir), "--output-dir", str(out_dir)]
    child_env = {key: value for key, value in os.environ.items() if not key.startswith("PYTHON")}
    child_env.update({"PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2",
                      "OPENBLAS_NUM_THREADS": "2", "HF_HUB_OFFLINE": "1",
                      "TRANSFORMERS_OFFLINE": "1", "JAX_PLATFORMS": "cpu"})
    remaining = min(300, deadline - time.monotonic() - 15)
    if remaining <= 0:
        raise TimeoutError("No time reserved for CPU reference")
    with (out_dir / "reference.log").open("w", encoding="utf-8") as log:
        completed = subprocess.run(command, env=child_env, stdout=log, stderr=subprocess.STDOUT,
                                   timeout=remaining, check=False)
    if completed.returncode:
        raise PreflightError(f"CPU reference exited {completed.returncode}; retained reference.log")
    metadata = json.loads((out_dir / "reference.json").read_text())
    metadata["_logits"] = np.load(out_dir / "reference-logits.npy", allow_pickle=False)
    metadata["exit_code"] = completed.returncode
    return metadata


def compare_parity(actual, reference, limits) -> dict:
    import numpy as np

    a = np.asarray(actual["_logits"], dtype=np.float32)
    b = np.asarray(reference["_logits"], dtype=np.float32)
    finite = bool(np.isfinite(a).all() and np.isfinite(b).all())
    equal_shape = a.shape == b.shape
    absolute, relative = None, None
    if equal_shape and finite:
        absolute = float(np.max(np.abs(a - b)))
        relative = float(np.linalg.norm(a - b) / max(float(np.linalg.norm(b)), 1e-12))
    same_tokens = actual["output_token_ids"] == reference["output_token_ids"]
    passed = (equal_shape and finite and same_tokens
              and absolute <= limits["max_absolute_logit_error"]
              and relative <= limits["relative_l2_logit_error"])
    return {"passed": bool(passed), "same_shape": equal_shape, "all_finite": finite,
            "greedy_tokens_equal": same_tokens, "max_absolute_logit_error": absolute,
            "relative_l2_logit_error": relative,
            "limits": {key: limits[key] for key in
                       ("max_absolute_logit_error", "relative_l2_logit_error")}}


def run_smoke(args) -> int:
    start = time.monotonic()
    wall_deadline = args.deadline_epoch or (time.time() + args.timeout_seconds)
    # Absolute deadline lets the bootstrap charge installation time to the same run.
    deadline = start + min(args.timeout_seconds, wall_deadline - time.time())
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    spec_path = Path(args.candidates).resolve()
    spec = json.loads(spec_path.read_text())
    result = {"format": "irisx.math.technical-smoke.v1", "task": "MATH-002",
              "run_id": args.run_id, "status": "running", "scoring_generations": 0,
              "model_candidates_sha256": sha256_file(spec_path), "candidates": [],
              "started_utc_epoch": time.time(), "deadline_utc_epoch": wall_deadline,
              "source_sha256": {name: sha256_file(Path(__file__).with_name(name))
                                for name in ("remote_smoke.py", "model_adapter.py")},
              "lean_qualification": "separate_gate_required", "panel_scoring_allowed": False}

    def save():
        result["worker_elapsed_seconds"] = time.monotonic() - start
        atomic_json(out / "smoke-report.json", result)

    def alarm_handler(_signal, _frame):
        raise TimeoutError("Whole-run reserved deadline reached")

    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, max(1, deadline - time.monotonic() - 10))
    try:
        if not 1 <= args.timeout_seconds <= 1800 or deadline <= start:
            raise PreflightError("Smoke deadline must fit first-run reservation <=1800 seconds")
        if args.manifest:
            manifest_path = Path(args.manifest).resolve()
            manifest = json.loads(manifest_path.read_text())
            result["run_manifest_sha256"] = sha256_file(manifest_path)
            if manifest.get("run_id") != args.run_id:
                raise PreflightError("Run manifest identity does not match --run-id")
        if (os.environ.get("PYTHONHASHSEED") != "0" or sys.flags.ignore_environment
                or sys.flags.hash_randomization != 0 or not sys.flags.no_user_site
                or not sys.flags.safe_path or not sys.dont_write_bytecode):
            raise PreflightError("Requires controlled subprocess startup with effective PYTHONHASHSEED=0")
        result["seed_startup"] = {"requested": "0", "ignore_environment": sys.flags.ignore_environment,
                                  "hash_randomization": sys.flags.hash_randomization,
                                  "no_user_site": sys.flags.no_user_site,
                                  "safe_path": sys.flags.safe_path,
                                  "dont_write_bytecode": sys.dont_write_bytecode,
                                  "probe_hash": hash("IRIS-X-MATH-002")}
        result["hardware"] = tpu_preflight()
        result["packages"] = {package: importlib.metadata.version(package)
                              for package in spec["runtime"]["packages"]}
        for package, required in spec["runtime"]["packages"].items():
            if result["packages"][package] != required:
                raise PreflightError(f"Package pin mismatch: {package}")
        save()
        selected = [c for c in spec["candidates"] if args.candidate == "all" or c["key"] == args.candidate]
        if not selected:
            raise PreflightError("No selected candidate")
        for candidate in selected:
            record = {"key": candidate["key"], "repo_id": candidate["repo_id"],
                      "revision": candidate["revision"], "status": "started"}
            result["candidates"].append(record)
            save()
            if deadline - time.monotonic() < 300:
                record["status"] = "not_started_insufficient_reserved_time"
                save()
                continue
            candidate_start = time.monotonic()
            candidate_out = out / candidate["key"]
            candidate_out.mkdir(exist_ok=True)
            try:
                record["stage"] = "download_pinned_source"
                save()
                model_dir, acquisition = download_candidate(candidate, Path(args.cache_dir), deadline)
                record["acquisition"] = acquisition
                record["stage"] = "adapter_load"
                save()
                load_start = time.monotonic()
                adapter = JaxQwen3Adapter(model_dir, candidate, context_length=args.context_tokens)
                record["load_seconds"] = time.monotonic() - load_start
                record["context_tokens"] = args.context_tokens
                record["sharding"] = {"mesh": {"mp": 8}, "weights": spec["runtime"]["parameter_layout"],
                                      "kv": spec["runtime"]["kv_layout"]}
                record["stage"] = "cold_compile"
                save()
                record["cold_compile_seconds"] = adapter.compile()
                record["stage"] = "warm_short_generation"
                save()
                options = {"seed": 0, "max_new_tokens": spec["qualification"]["short_output_tokens"],
                           "temperature": 0, "top_p": 1, "deadline": deadline,
                           "qualification_mode": True}
                first = adapter.generate(spec["qualification"]["technical_messages"], **options)
                repeat = adapter.generate(spec["qualification"]["technical_messages"], **options)
                record["first_generation"] = {key: value for key, value in first.items() if key != "_logits"}
                record["warm_generation"] = {key: value for key, value in repeat.items() if key != "_logits"}
                record["warm_repeat_tokens_equal"] = first["output_token_ids"] == repeat["output_token_ids"]
                record["stage"] = "cpu_reference"
                save()
                reference = cpu_reference_subprocess(model_dir, first["prompt_token_ids"], candidate_out, deadline)
                record["reference"] = {key: value for key, value in reference.items() if key != "_logits"}
                record["parity"] = compare_parity(first, reference, spec["qualification"])
                record["device_memory_after"] = []
                for device in adapter.jax.devices():
                    stats = device.memory_stats() or {}
                    record["device_memory_after"].append({"id": device.id, **{
                        key: int(stats[key]) for key in ("bytes_limit", "bytes_in_use", "peak_bytes_in_use")
                        if key in stats}})
                passed = (record["parity"]["passed"] and record["warm_repeat_tokens_equal"]
                          and first["stop_reason"] != "deadline" and repeat["stop_reason"] != "deadline")
                record["status"] = "model_technical_passed" if passed else "model_technical_failed"
                adapter.qualification = "passed" if passed else "failed"
                del adapter, first, repeat, reference
                gc.collect()
                import jax
                jax.clear_caches()
            except Exception as exc:
                record["status"] = "model_technical_failed"
                # No tracebacks or environment dumps; raw trusted-reference output is separate.
                record["error_type"] = type(exc).__name__
                record["error"] = str(exc)[:2000]
            record["elapsed_seconds"] = time.monotonic() - candidate_start
            save()
        result["status"] = ("technical_smoke_complete" if all(
            item["status"] == "model_technical_passed" for item in result["candidates"])
            else "technical_smoke_incomplete_or_failed")
    except Exception as exc:
        result["status"] = "preflight_failed" if not result["candidates"] else "technical_smoke_failed"
        result["error_type"], result["error"] = type(exc).__name__, str(exc)[:2000]
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.setitimer(signal.ITIMER_REAL, 0)
        save()
        receipt = {"run_id": args.run_id, "files": []}
        for path in sorted(out.rglob("*")):
            if path.is_file() and path.name != "smoke-files.json":
                receipt["files"].append({"path": path.relative_to(out).as_posix(),
                                          "bytes": path.stat().st_size, "sha256": sha256_file(path)})
        atomic_json(out / "smoke-files.json", receipt)
    print(json.dumps({"run_id": args.run_id, "status": result["status"],
                      "report": str(out / "smoke-report.json")}, sort_keys=True), flush=True)
    return 0 if result["status"] == "technical_smoke_complete" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--model-dir")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", default="technical-unregistered")
    parser.add_argument("--manifest", help="Parent-owned run manifest; run_id must match")
    parser.add_argument("--candidate", choices=("all", "qwen3-4b", "goedel-v2-8b"), default="all")
    parser.add_argument("--candidates", default=str(Path(__file__).with_name("model-candidates.json")))
    parser.add_argument("--cache-dir", default="/tmp/math002-model-cache")
    parser.add_argument("--context-tokens", type=int, default=8192)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--deadline-epoch", type=float)
    args = parser.parse_args()
    if args.reference:
        import numpy as np
        out = Path(args.output_dir)
        token_ids = json.loads((out / "reference-input.json").read_text())["token_ids"]
        result = transformers_reference(args.model_dir, token_ids, new_tokens=8, threads=2)
        np.save(out / "reference-logits.npy", np.asarray(result.pop("_logits")), allow_pickle=False)
        atomic_json(out / "reference.json", result)
        return 0
    return run_smoke(args)


if __name__ == "__main__":
    raise SystemExit(main())
