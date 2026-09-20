"""Thin network-disabled Kaggle adapter for ARC-AGI-2 Trial 001.

This module is copied into the outbound package and run only after a separately
authorized real trial. Importing it performs no model, GPU, or network work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any


_NETWORK_ATTEMPTS = 0


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return "sha256:" + hasher.hexdigest()


def _validate_model_tree(model_root: Path, provenance: dict[str, Any]) -> None:
    if provenance.get("schema") != "irisx/model-source-provenance":
        raise RuntimeError("raw model provenance kind is invalid")
    unsigned = {key: provenance.get(key) for key in ("schema", "schema_version", "artifact_id", "version", "payload")}
    encoded = json.dumps(unsigned, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if provenance.get("content_digest") != _digest(encoded):
        raise RuntimeError("raw model provenance artifact digest is invalid")
    entries = provenance.get("payload", {}).get("files")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("raw model provenance file list is invalid")
    expected = {entry.get("path"): entry for entry in entries if isinstance(entry, dict)}
    if len(expected) != len(entries) or "config.json" not in expected:
        raise RuntimeError("raw model provenance paths are incomplete or duplicated")
    actual: dict[str, Path] = {}
    for path in model_root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"raw model Dataset contains a symbolic link: {path}")
        if path.is_file():
            actual[path.relative_to(model_root).as_posix()] = path
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))[:20]
        extra = sorted(set(actual) - set(expected))[:20]
        raise RuntimeError(f"raw model Dataset membership mismatch; missing={missing}, extra={extra}")
    for logical, path in actual.items():
        entry = expected[logical]
        if path.stat().st_size != entry.get("byte_size") or _file_digest(path) != entry.get("content_digest"):
            raise RuntimeError(f"raw model Dataset file binding mismatch: {logical}")


def _hardware() -> dict[str, Any]:
    completed = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        raise RuntimeError("nvidia-smi failed; the bound accelerator is unavailable")
    rows = [row.strip() for row in completed.stdout.splitlines() if row.strip()]
    if len(rows) != 1:
        raise RuntimeError("exactly one GPU is required")
    name, memory = [part.strip() for part in rows[0].rsplit(",", 1)]
    memory_mib = int(memory)
    if "NVIDIA RTX PRO 6000" not in name or memory_mib < 96000:
        raise RuntimeError(f"unexpected GPU identity: {name}, {memory_mib} MiB")
    return {"gpu_count": 1, "gpu_model": name, "gpu_memory_mib": memory_mib}


def _disable_network() -> None:
    global _NETWORK_ATTEMPTS

    _NETWORK_ATTEMPTS = 0
    import importlib

    socket = importlib.import_module("socket")
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "PIP_NO_INDEX": "1",
            "WANDB_DISABLED": "true",
            "HF_HOME": "/kaggle/working/hf-home",
            "TRANSFORMERS_CACHE": "/kaggle/working/hf-home/transformers",
            "TORCH_HOME": "/kaggle/working/torch-home",
            "XDG_CACHE_HOME": "/kaggle/working/cache",
            "TMPDIR": "/kaggle/working/tmp",
        }
    )
    for variable in ("HF_HOME", "TORCH_HOME", "XDG_CACHE_HOME", "TMPDIR"):
        Path(os.environ[variable]).mkdir(parents=True, exist_ok=True)

    def blocked(*_args: Any, **_kwargs: Any) -> Any:
        global _NETWORK_ATTEMPTS

        _NETWORK_ATTEMPTS += 1
        raise RuntimeError("network access is disabled by the IRIS-X trial runner")

    original_socket = socket.socket

    class BlockedSocket(original_socket):  # type: ignore[misc, valid-type]
        def connect(self, *_args: Any, **_kwargs: Any) -> Any:
            return blocked()

        def connect_ex(self, *_args: Any, **_kwargs: Any) -> Any:
            return blocked()

        def sendto(self, *_args: Any, **_kwargs: Any) -> Any:
            return blocked()

    # Keep ``socket.socket`` class-like so offline library imports that subclass
    # it continue to work; all connection paths still fail closed and count.
    socket.socket = BlockedSocket
    socket.create_connection = blocked  # type: ignore[assignment]
    socket.getaddrinfo = blocked  # type: ignore[assignment]


def _assert_no_credentials() -> None:
    exact = {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "KAGGLE_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "HF_TOKEN",
        "HUGGING_FACE_HUB_TOKEN",
    }
    present = sorted(
        key
        for key, value in os.environ.items()
        if value
        and (
            key in exact
            or key.endswith("_API_KEY")
            or key.endswith("_ACCESS_TOKEN")
            or key.endswith("_AUTH_TOKEN")
            or key.endswith("_SECRET")
        )
    )
    if present:
        raise RuntimeError(f"provider or service credentials are present: {present}")


def _seed(configuration_digest: str, case_id: str, test_index: int, attempt_index: int) -> int:
    source = f"{configuration_digest}:{case_id}:{test_index}:{attempt_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(source).digest()[:4], "big")


def _prompt(case: dict[str, Any], test_index: int, prompt_payload: dict[str, Any]) -> str:
    policy = prompt_payload.get("reasoning_policy", [])
    sections = [prompt_payload["instruction"]]
    if policy:
        sections.append("Reasoning policy:\n" + "\n".join(f"- {item}" for item in policy))
    sections.append("Demonstrations:\n" + json.dumps(case["train"], separators=(",", ":")))
    sections.append("Test input:\n" + json.dumps(case["test"][test_index]["input"], separators=(",", ":")))
    sections.append("Return only the JSON output grid.")
    return "\n\n".join(sections)


def _grid(text: str) -> list[list[int]] | None:
    candidates = re.findall(r"\[\s*\[.*?\]\s*\]", text, flags=re.DOTALL)
    for candidate in reversed(candidates):
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, list) or not value or len(value) > 30:
            continue
        width = None
        valid = True
        for row in value:
            if not isinstance(row, list) or not row or len(row) > 30:
                valid = False
                break
            width = len(row) if width is None else width
            if len(row) != width or any(isinstance(cell, bool) or not isinstance(cell, int) or not 0 <= cell <= 9 for cell in row):
                valid = False
                break
        if valid:
            return value
    return None


def _prediction_document(
    label: str,
    configuration: dict[str, Any],
    prompts: dict[str, Any],
    solver_cases: dict[str, Any],
    model: Any,
    tokenizer: Any,
    torch: Any,
    envelope: dict[str, Any],
    logs: list[dict[str, Any]],
    deadline: float,
) -> dict[str, Any]:
    configuration_ref = {
        "kind": configuration["schema"],
        "artifact_id": configuration["artifact_id"],
        "version": configuration["version"],
        "content_digest": configuration["content_digest"],
    }
    cases: list[dict[str, Any]] = []
    for case in solver_cases["payload"]["cases"]:
        tests = []
        for test_index in range(len(case["test"])):
            attempts = []
            for attempt_index in range(2):
                started = time.monotonic()
                raw = ""
                status = "error"
                grid = None
                try:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise RuntimeError("wall-clock timeout")
                    seed = _seed(configuration_ref["content_digest"], case["case_id"], test_index, attempt_index)
                    torch.manual_seed(seed)
                    torch.cuda.manual_seed_all(seed)
                    inputs = tokenizer(_prompt(case, test_index, prompts["payload"]), return_tensors="pt").to("cuda")
                    generated = model.generate(
                        **inputs,
                        do_sample=envelope["payload"]["decoding"]["do_sample"],
                        temperature=envelope["payload"]["decoding"]["temperature"],
                        top_p=envelope["payload"]["decoding"]["top_p"],
                        max_new_tokens=envelope["payload"]["output_limits"]["max_new_tokens"],
                        max_time=min(envelope["payload"]["timeout_seconds_per_invocation"], remaining),
                    )
                    completion = generated[0][inputs["input_ids"].shape[1] :]
                    raw = tokenizer.decode(completion, skip_special_tokens=True)
                    if len(raw.encode("utf-8")) > envelope["payload"]["output_limits"]["max_response_bytes"]:
                        raw = raw.encode("utf-8")[: envelope["payload"]["output_limits"]["max_response_bytes"]].decode("utf-8", "ignore")
                    grid = _grid(raw)
                    status = "ok" if grid is not None else "malformed"
                except RuntimeError as exc:
                    raw = str(exc)
                    status = "timeout" if "timeout" in raw.lower() else "error"
                elapsed = time.monotonic() - started
                if elapsed > envelope["payload"]["timeout_seconds_per_invocation"]:
                    status = "timeout"
                    grid = None
                attempts.append(
                    {
                        "attempt_index": attempt_index,
                        "status": status,
                        "grid": grid,
                        "raw_output_digest": _digest(raw.encode("utf-8")),
                    }
                )
                logs.append(
                    {
                        "event": "invocation_complete",
                        "configuration": label,
                        "case_id": case["case_id"],
                        "test_index": test_index,
                        "attempt_index": attempt_index,
                        "status": status,
                        "elapsed_seconds": elapsed,
                    }
                )
            tests.append({"test_index": test_index, "attempts": attempts})
        cases.append({"case_id": case["case_id"], "tests": tests})
    return {
        "format": "irisx/arc-agi-2-predictions",
        "format_version": "1.0",
        "configuration_ref": configuration_ref,
        "cases": cases,
    }


def execute(trial_root: Path, model_root: Path, output: Path, trial_manifest_digest: str) -> None:
    working = Path("/kaggle/working").resolve()
    kaggle_input = Path("/kaggle/input").resolve()
    if not trial_root.resolve().is_relative_to(working):
        raise RuntimeError("writable trial material must be beneath /kaggle/working")
    if not model_root.resolve().is_relative_to(kaggle_input):
        raise RuntimeError("raw model source must be mounted read-only beneath /kaggle/input")
    if not output.resolve().is_relative_to(working):
        raise RuntimeError("result output must be beneath /kaggle/working")
    hardware = _hardware()
    if os.environ.get("IRISX_KAGGLE_INTERNET_DISABLED") != "1":
        raise RuntimeError("notebook Internet-disabled state was not bound")
    _assert_no_credentials()
    _disable_network()
    import torch
    import transformers

    envelope = _read(trial_root / "bindings/execution-envelope.json")
    solver_cases = _read(trial_root / "cases/solver-cases.json")
    baseline = _read(trial_root / "configurations/baseline.json")
    candidate = _read(trial_root / "configurations/candidate.json")
    baseline_prompts = _read(trial_root / "components/baseline-prompts.json")
    candidate_prompts = _read(trial_root / "components/candidate-prompts.json")
    binding = _read(trial_root / "bindings/run.json")
    dependencies = _read(trial_root / "runtime/dependencies.json")
    observed_software = {
        "python": os.sys.version.split()[0],
        "torch": torch.__version__,
        "transformers": transformers.__version__,
    }
    if any(observed_software[field] != dependencies.get(field) for field in observed_software):
        raise RuntimeError(f"effective runtime does not match the bound dependency versions: {observed_software}")
    provenance = _read(trial_root / "bindings/model-source-provenance.json")
    if provenance.get("content_digest") != binding.get("model_source_provenance_digest"):
        raise RuntimeError("raw model provenance does not match the run binding")
    _validate_model_tree(model_root, provenance)
    expected_invocations = sum(len(case["test"]) for case in solver_cases["payload"]["cases"]) * 2
    if envelope["payload"]["invocation_limit_per_configuration"] != expected_invocations:
        raise RuntimeError("execution envelope invocation limit does not match the frozen solver workload")
    tokenizer = transformers.AutoTokenizer.from_pretrained(model_root, local_files_only=True, trust_remote_code=False)
    model = transformers.AutoModelForCausalLM.from_pretrained(
        model_root,
        local_files_only=True,
        trust_remote_code=False,
        torch_dtype=torch.bfloat16,
        device_map="cuda",
    )
    started = time.monotonic()
    deadline = started + envelope["payload"]["wall_clock_limit_seconds"]
    logs: list[dict[str, Any]] = []
    baseline_predictions = _prediction_document(
        "baseline", baseline, baseline_prompts, solver_cases, model, tokenizer, torch, envelope, logs, deadline
    )
    candidate_predictions = _prediction_document(
        "candidate", candidate, candidate_prompts, solver_cases, model, tokenizer, torch, envelope, logs, deadline
    )
    wall_clock = time.monotonic() - started
    stop_conditions = []
    if _NETWORK_ATTEMPTS:
        stop_conditions.append("network-attempt")
    if wall_clock > envelope["payload"]["wall_clock_limit_seconds"]:
        stop_conditions.append("wall-clock-limit")
    observations = {
        "format": "irisx/arc-agi-2-execution-observations",
        "format_version": "1.0",
        "hardware": hardware,
        "software": observed_software,
        "internet_disabled": True,
        "credentials_present": False,
        "network_calls": _NETWORK_ATTEMPTS,
        "provider_calls": 0,
        "external_paid_cost_usd": 0,
        "evaluation_leaks": 0,
        "identity_binding_failures": 0,
        "wall_clock_seconds": wall_clock,
        "gpu_seconds_state": "unknown",
        "gpu_seconds": None,
        "timeout_policy": envelope["payload"]["timeout_seconds_per_invocation"],
        "seed_policy": envelope["payload"]["seed_policy"],
        "attempts_per_test_input": 2,
        "stop_conditions_triggered": stop_conditions,
    }
    files = {
        "predictions/baseline.json": _canonical(baseline_predictions),
        "predictions/candidate.json": _canonical(candidate_predictions),
        "observations/execution.json": _canonical(observations),
        "logs/runner.json": _canonical({"events": logs}),
    }
    entries = [
        {"path": path, "byte_size": len(data), "content_digest": _digest(data)} for path, data in sorted(files.items())
    ]
    manifest = {
        "format": "irisx/closed-world-zip",
        "format_version": "1.0",
        "package_kind": "irisx/arc-agi-2-result-package",
        "package_id": binding["run_id"],
        "files": entries,
        "metadata": {
            "trial_manifest_digest": trial_manifest_digest,
            "model_source_provenance_digest": binding["model_source_provenance_digest"],
            "model_dataset": binding["model_dataset"],
            "bundle_id": binding["bundle_id"],
            "repository_revision": binding["repository_revision"],
            "notebook_digest": binding["notebook_digest"],
            "runner_digest": binding["runner_digest"],
            "baseline_configuration_ref": baseline_predictions["configuration_ref"],
            "candidate_configuration_ref": candidate_predictions["configuration_ref"],
            "execution_envelope_ref": binding["execution_envelope_ref"],
        },
    }
    import zipfile

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path, data in [("manifest.json", _canonical(manifest)), *sorted(files.items())]:
            info = zipfile.ZipInfo(path, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = (0o100644 << 16)
            archive.writestr(info, data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--trial-manifest-digest", required=True)
    args = parser.parse_args(argv)
    execute(args.trial_root, args.model_root, args.output, args.trial_manifest_digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
