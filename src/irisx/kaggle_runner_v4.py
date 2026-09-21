"""Checkpointing network-disabled Kaggle adapter for ARC-AGI-2 Trial 001.

The outbound builder installs this file as ``runtime/runner.py`` and the frozen
v3 runner as ``runtime/runner_core.py``. Importing this module performs no model,
GPU, filesystem, or network work.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import time
from typing import Any
import zipfile

try:  # standalone inside the outbound runtime directory
    import runner_core as core
except ModuleNotFoundError:  # repository tests and local inspection
    from irisx import kaggle_runner as core


CHECKPOINT_KIND = "irisx/arc-agi-2-checkpoint-package"
CHECKPOINT_FORMAT = "irisx/arc-agi-2-checkpoint"
CHECKPOINT_VERSION = "1.0"
FINALIZATION_RESERVE_SECONDS = 1800
MAX_CHECKPOINT_MEMBER_BYTES = 16 * 1024 * 1024
CHECKPOINT_POLICY = {
    "format": CHECKPOINT_FORMAT,
    "format_version": CHECKPOINT_VERSION,
    "interval": "after-every-attempt",
    "pending_attempt_recovery": "record-timeout-and-continue",
    "finalization_reserve_seconds": FINALIZATION_RESERVE_SECONDS,
    "resume_budget": "cumulative-across-sessions",
}


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _append_progress(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = core._canonical(event)
    with path.open("ab") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    print(encoded.decode("utf-8").rstrip(), flush=True)


def _write_zip_atomic(
    output: Path,
    package_kind: str,
    package_id: str,
    files: dict[str, bytes],
    metadata: dict[str, Any],
) -> None:
    entries = [
        {"path": path, "byte_size": len(data), "content_digest": core._digest(data)}
        for path, data in sorted(files.items())
    ]
    manifest = {
        "format": "irisx/closed-world-zip",
        "format_version": "1.0",
        "package_kind": package_kind,
        "package_id": package_id,
        "files": entries,
        "metadata": metadata,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for logical, data in [("manifest.json", core._canonical(manifest)), *sorted(files.items())]:
            info = zipfile.ZipInfo(logical, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    os.replace(temporary, output)


def _configuration_ref(configuration: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": configuration["schema"],
        "artifact_id": configuration["artifact_id"],
        "version": configuration["version"],
        "content_digest": configuration["content_digest"],
    }


def _identity(binding: dict[str, Any], trial_manifest_digest: str) -> dict[str, Any]:
    return {
        "bundle_id": binding["bundle_id"],
        "trial_manifest_digest": trial_manifest_digest,
        "model_source_provenance_digest": binding["model_source_provenance_digest"],
        "repository_revision": binding["repository_revision"],
        "notebook_digest": binding["notebook_digest"],
        "runner_digest": binding["runner_digest"],
        "runner_core_digest": binding["runner_core_digest"],
        "baseline_configuration_ref": binding["baseline_configuration_ref"],
        "candidate_configuration_ref": binding["candidate_configuration_ref"],
        "execution_envelope_ref": binding["execution_envelope_ref"],
        "checkpoint_policy": binding["checkpoint_policy"],
    }


def _key(label: str, case_id: str, test_index: int, attempt_index: int) -> dict[str, Any]:
    return {
        "configuration": label,
        "case_id": case_id,
        "test_index": test_index,
        "attempt_index": attempt_index,
    }


def _tasks(
    solver_cases: dict[str, Any],
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    baseline_prompts: dict[str, Any],
    candidate_prompts: dict[str, Any],
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for label, configuration, prompts in (
        ("baseline", baseline, baseline_prompts),
        ("candidate", candidate, candidate_prompts),
    ):
        for case in solver_cases["payload"]["cases"]:
            for test_index in range(len(case["test"])):
                for attempt_index in range(2):
                    tasks.append(
                        {
                            "key": _key(label, case["case_id"], test_index, attempt_index),
                            "configuration": configuration,
                            "prompts": prompts,
                            "case": case,
                        }
                    )
    return tasks


def _new_state(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": CHECKPOINT_FORMAT,
        "format_version": CHECKPOINT_VERSION,
        "identity": identity,
        "completed": [],
        "pending": None,
        "consumed_wall_clock_seconds": 0.0,
        "session_count": 0,
        "resume_count": 0,
        "interrupted_attempts": 0,
        "sessions": [],
    }


def _valid_grid(value: Any) -> bool:
    if not isinstance(value, list) or not value or len(value) > 30:
        return False
    width = None
    for row in value:
        if not isinstance(row, list) or not row or len(row) > 30:
            return False
        width = len(row) if width is None else width
        if len(row) != width:
            return False
        if any(isinstance(cell, bool) or not isinstance(cell, int) or not 0 <= cell <= 9 for cell in row):
            return False
    return True


def _validate_attempt(value: Any, key: dict[str, Any]) -> None:
    required = {"attempt_index", "status", "grid", "raw_output_digest"}
    if not isinstance(value, dict) or set(value) != required:
        raise RuntimeError("checkpoint attempt fields are incomplete or unexpected")
    if value["attempt_index"] != key["attempt_index"]:
        raise RuntimeError("checkpoint attempt index is stale")
    if value["status"] not in {"ok", "malformed", "timeout", "error"}:
        raise RuntimeError("checkpoint attempt status is invalid")
    if value["status"] == "ok":
        if not _valid_grid(value["grid"]):
            raise RuntimeError("checkpoint successful attempt grid is invalid")
    elif value["grid"] is not None:
        raise RuntimeError("checkpoint unsuccessful attempt must not contain a grid")
    digest = value["raw_output_digest"]
    if not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) != 71:
        raise RuntimeError("checkpoint raw-output digest is invalid")


def _validate_state(
    value: Any,
    identity: dict[str, Any],
    expected_keys: list[dict[str, Any]],
    wall_clock_limit: float,
) -> dict[str, Any]:
    required = {
        "format",
        "format_version",
        "identity",
        "completed",
        "pending",
        "consumed_wall_clock_seconds",
        "session_count",
        "resume_count",
        "interrupted_attempts",
        "sessions",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise RuntimeError("checkpoint fields are incomplete or unexpected")
    if value["format"] != CHECKPOINT_FORMAT or value["format_version"] != CHECKPOINT_VERSION:
        raise RuntimeError("checkpoint format is unsupported")
    if value["identity"] != identity:
        raise RuntimeError("checkpoint identity does not match this outbound run")
    completed = value["completed"]
    if not isinstance(completed, list) or len(completed) > len(expected_keys):
        raise RuntimeError("checkpoint completed invocation list is invalid")
    for index, record in enumerate(completed):
        if not isinstance(record, dict) or set(record) != {"key", "attempt", "elapsed_seconds"}:
            raise RuntimeError("checkpoint completed record is malformed")
        if record["key"] != expected_keys[index]:
            raise RuntimeError("checkpoint is not a contiguous invocation prefix")
        _validate_attempt(record["attempt"], record["key"])
        elapsed = record["elapsed_seconds"]
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or elapsed < 0:
            raise RuntimeError("checkpoint elapsed time is invalid")
    pending = value["pending"]
    if pending is not None:
        if not isinstance(pending, dict) or set(pending) != {"key", "reserved_seconds"}:
            raise RuntimeError("checkpoint pending record is malformed")
        if len(completed) >= len(expected_keys) or pending["key"] != expected_keys[len(completed)]:
            raise RuntimeError("checkpoint pending invocation is not the next invocation")
        reserved = pending["reserved_seconds"]
        if isinstance(reserved, bool) or not isinstance(reserved, (int, float)) or reserved <= 0:
            raise RuntimeError("checkpoint pending reservation is invalid")
    consumed = value["consumed_wall_clock_seconds"]
    if isinstance(consumed, bool) or not isinstance(consumed, (int, float)) or not 0 <= consumed <= wall_clock_limit:
        raise RuntimeError("checkpoint cumulative wall-clock value is invalid")
    elapsed_total = sum(record["elapsed_seconds"] for record in completed)
    if elapsed_total > consumed:
        raise RuntimeError("checkpoint elapsed invocation time exceeds cumulative wall-clock time")
    for field in ("session_count", "resume_count", "interrupted_attempts"):
        if isinstance(value[field], bool) or not isinstance(value[field], int) or value[field] < 0:
            raise RuntimeError(f"checkpoint {field} is invalid")
    if value["resume_count"] > value["session_count"] or value["interrupted_attempts"] > len(completed):
        raise RuntimeError("checkpoint session counters are inconsistent")
    if not isinstance(value["sessions"], list) or len(value["sessions"]) != value["session_count"]:
        raise RuntimeError("checkpoint session evidence is incomplete")
    if (completed or pending is not None) and value["session_count"] == 0:
        raise RuntimeError("checkpoint work exists without a recorded session")
    if value["session_count"] and value["session_count"] != value["resume_count"] + 1:
        raise RuntimeError("checkpoint session and resume counters are inconsistent")
    first_hardware = None
    first_software = None
    for index, session in enumerate(value["sessions"]):
        if not isinstance(session, dict) or set(session) != {"session_index", "hardware", "software"}:
            raise RuntimeError("checkpoint session record is malformed")
        if session["session_index"] != index:
            raise RuntimeError("checkpoint session indexes are not contiguous")
        if index == 0:
            first_hardware = session["hardware"]
            first_software = session["software"]
        elif session["hardware"] != first_hardware or session["software"] != first_software:
            raise RuntimeError("checkpoint session runtime identity changed")
    timeout_count = sum(record["attempt"]["status"] == "timeout" for record in completed)
    if value["interrupted_attempts"] > timeout_count:
        raise RuntimeError("checkpoint interrupted-attempt count exceeds timeout evidence")
    return value


def _progress_events(data: bytes) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in data.splitlines(keepends=True):
        try:
            value = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"checkpoint progress JSONL is invalid: {exc}") from exc
        if core._canonical(value) != line:
            raise RuntimeError("checkpoint progress JSONL is not canonical")
        if not isinstance(value, dict) or value.get("event") not in {
            "session_started",
            "invocation_started",
            "invocation_complete",
            "wall_clock_exhausted",
        }:
            raise RuntimeError("checkpoint progress event is unsupported")
        events.append(value)
    return events


def _persist_checkpoint(output: Path, progress: Path, state: dict[str, Any]) -> None:
    progress_bytes = progress.read_bytes() if progress.exists() else b""
    _progress_events(progress_bytes)
    files = {
        "checkpoint.json": core._canonical(state),
        "progress.jsonl": progress_bytes,
    }
    _write_zip_atomic(output, CHECKPOINT_KIND, state["identity"]["bundle_id"], files, {"identity": state["identity"]})


def _load_checkpoint(
    path: Path,
    identity: dict[str, Any],
    expected_keys: list[dict[str, Any]],
    wall_clock_limit: float,
    progress: Path,
) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)) or set(names) != {"manifest.json", "checkpoint.json", "progress.jsonl"}:
            raise RuntimeError("checkpoint package membership is invalid")
        for info in infos:
            if (
                info.is_dir()
                or stat.S_ISLNK(info.external_attr >> 16)
                or info.compress_type != zipfile.ZIP_STORED
                or info.file_size > MAX_CHECKPOINT_MEMBER_BYTES
                or info.compress_size != info.file_size
            ):
                raise RuntimeError("checkpoint package contains an unsafe member")
        contents = {name: archive.read(name) for name in names}
    manifest = json.loads(contents["manifest.json"])
    if core._canonical(manifest) != contents["manifest.json"]:
        raise RuntimeError("checkpoint manifest is not canonical")
    entries = manifest.get("files")
    declared = (
        {entry.get("path"): entry for entry in entries if isinstance(entry, dict)}
        if isinstance(entries, list)
        else {}
    )
    expected_files = {"checkpoint.json", "progress.jsonl"}
    if (
        manifest.get("format") != "irisx/closed-world-zip"
        or manifest.get("format_version") != "1.0"
        or manifest.get("package_kind") != CHECKPOINT_KIND
        or manifest.get("package_id") != identity["bundle_id"]
        or manifest.get("metadata") != {"identity": identity}
        or not isinstance(entries, list)
        or len(declared) != len(entries)
        or set(declared) != expected_files
    ):
        raise RuntimeError("checkpoint manifest identity is stale or malformed")
    for logical in expected_files:
        data = contents[logical]
        if declared[logical] != {
            "path": logical,
            "byte_size": len(data),
            "content_digest": core._digest(data),
        }:
            raise RuntimeError(f"checkpoint member binding is stale: {logical}")
    state = json.loads(contents["checkpoint.json"])
    if core._canonical(state) != contents["checkpoint.json"]:
        raise RuntimeError("checkpoint state is not canonical")
    _progress_events(contents["progress.jsonl"])
    _atomic_write(progress, contents["progress.jsonl"])
    return _validate_state(state, identity, expected_keys, wall_clock_limit)


def _timeout_attempt(attempt_index: int, reason: str) -> dict[str, Any]:
    return {
        "attempt_index": attempt_index,
        "status": "timeout",
        "grid": None,
        "raw_output_digest": core._digest(reason.encode("utf-8")),
    }


def _complete_record(
    state: dict[str, Any],
    progress: Path,
    key: dict[str, Any],
    attempt: dict[str, Any],
    elapsed_seconds: float,
) -> None:
    state["completed"].append(
        {"key": key, "attempt": attempt, "elapsed_seconds": elapsed_seconds}
    )
    state["pending"] = None
    _append_progress(
        progress,
        {
            "event": "invocation_complete",
            "sequence": len(state["completed"]) - 1,
            "key": key,
            "status": attempt["status"],
            "elapsed_seconds": elapsed_seconds,
            "consumed_wall_clock_seconds": state["consumed_wall_clock_seconds"],
        },
    )


def _recover_pending(
    state: dict[str, Any],
    progress: Path,
    checkpoint_output: Path,
) -> bool:
    """Close an interrupted invocation exactly once without granting a rerun."""

    if state["pending"] is None:
        return False
    pending = state["pending"]
    state["consumed_wall_clock_seconds"] += pending["reserved_seconds"]
    state["interrupted_attempts"] += 1
    attempt = _timeout_attempt(
        pending["key"]["attempt_index"],
        "interrupted attempt recovered as timeout",
    )
    _complete_record(state, progress, pending["key"], attempt, pending["reserved_seconds"])
    _persist_checkpoint(checkpoint_output, progress, state)
    return True


def _documents(
    state: dict[str, Any],
    solver_cases: dict[str, Any],
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    by_key = {
        (
            record["key"]["configuration"],
            record["key"]["case_id"],
            record["key"]["test_index"],
            record["key"]["attempt_index"],
        ): record
        for record in state["completed"]
    }
    documents: dict[str, dict[str, Any]] = {}
    for label, configuration in (("baseline", baseline), ("candidate", candidate)):
        cases = []
        for case in solver_cases["payload"]["cases"]:
            tests = []
            for test_index in range(len(case["test"])):
                attempts = [
                    by_key[(label, case["case_id"], test_index, attempt_index)]["attempt"]
                    for attempt_index in range(2)
                ]
                tests.append({"test_index": test_index, "attempts": attempts})
            cases.append({"case_id": case["case_id"], "tests": tests})
        documents[label] = {
            "format": "irisx/arc-agi-2-predictions",
            "format_version": "1.0",
            "configuration_ref": _configuration_ref(configuration),
            "cases": cases,
        }
    logs = {
        "events": [
            {
                "event": "invocation_complete",
                **record["key"],
                "status": record["attempt"]["status"],
                "elapsed_seconds": record["elapsed_seconds"],
            }
            for record in state["completed"]
        ]
    }
    return documents["baseline"], documents["candidate"], logs


def _write_result(
    output: Path,
    binding: dict[str, Any],
    identity: dict[str, Any],
    baseline_predictions: dict[str, Any],
    candidate_predictions: dict[str, Any],
    observations: dict[str, Any],
    logs: dict[str, Any],
) -> None:
    files = {
        "predictions/baseline.json": core._canonical(baseline_predictions),
        "predictions/candidate.json": core._canonical(candidate_predictions),
        "observations/execution.json": core._canonical(observations),
        "logs/runner.json": core._canonical(logs),
    }
    metadata = {
        "trial_manifest_digest": identity["trial_manifest_digest"],
        "model_source_provenance_digest": identity["model_source_provenance_digest"],
        "model_dataset": binding["model_dataset"],
        "bundle_id": identity["bundle_id"],
        "repository_revision": identity["repository_revision"],
        "notebook_digest": identity["notebook_digest"],
        "runner_digest": identity["runner_digest"],
        "runner_core_digest": identity["runner_core_digest"],
        "checkpoint_policy": identity["checkpoint_policy"],
        "baseline_configuration_ref": identity["baseline_configuration_ref"],
        "candidate_configuration_ref": identity["candidate_configuration_ref"],
        "execution_envelope_ref": identity["execution_envelope_ref"],
    }
    _write_zip_atomic(output, "irisx/arc-agi-2-result-package", identity["bundle_id"], files, metadata)


def execute(
    trial_root: Path,
    model_root: Path,
    output: Path,
    checkpoint_output: Path,
    trial_manifest_digest: str,
    resume_checkpoint: Path | None = None,
) -> None:
    working = Path("/kaggle/working").resolve()
    kaggle_input = Path("/kaggle/input").resolve()
    for path, boundary, label in (
        (trial_root, working, "trial material"),
        (output, working, "result output"),
        (checkpoint_output, working, "checkpoint output"),
    ):
        if not path.resolve().is_relative_to(boundary):
            raise RuntimeError(f"{label} must be beneath {boundary}")
    if not model_root.resolve().is_relative_to(kaggle_input):
        raise RuntimeError("raw model source must be mounted read-only beneath /kaggle/input")

    hardware = core._hardware()
    if os.environ.get("IRISX_KAGGLE_INTERNET_DISABLED") != "1":
        raise RuntimeError("notebook Internet-disabled state was not bound")
    core._assert_no_credentials()
    core._disable_network()
    import torch
    import transformers

    envelope = core._read(trial_root / "bindings/execution-envelope.json")
    solver_cases = core._read(trial_root / "cases/solver-cases.json")
    baseline = core._read(trial_root / "configurations/baseline.json")
    candidate = core._read(trial_root / "configurations/candidate.json")
    baseline_prompts = core._read(trial_root / "components/baseline-prompts.json")
    candidate_prompts = core._read(trial_root / "components/candidate-prompts.json")
    binding = core._read(trial_root / "bindings/run.json")
    dependencies = core._read(trial_root / "runtime/dependencies.json")
    observed_software = {
        "python": os.sys.version.split()[0],
        "torch": torch.__version__,
        "transformers": transformers.__version__,
    }
    if any(observed_software[field] != dependencies.get(field) for field in observed_software):
        raise RuntimeError(f"effective runtime does not match the bound dependency versions: {observed_software}")
    if binding.get("checkpoint_policy") != CHECKPOINT_POLICY:
        raise RuntimeError("outbound checkpoint policy does not match runner v4")
    provenance = core._read(trial_root / "bindings/model-source-provenance.json")
    if provenance.get("content_digest") != binding.get("model_source_provenance_digest"):
        raise RuntimeError("raw model provenance does not match the run binding")
    core._validate_model_tree(model_root, provenance)

    expected_invocations = sum(len(case["test"]) for case in solver_cases["payload"]["cases"]) * 2
    if envelope["payload"]["invocation_limit_per_configuration"] != expected_invocations:
        raise RuntimeError("execution envelope invocation limit does not match the frozen solver workload")
    tasks = _tasks(solver_cases, baseline, candidate, baseline_prompts, candidate_prompts)
    expected_keys = [task["key"] for task in tasks]
    identity = _identity(binding, trial_manifest_digest)
    wall_limit = float(envelope["payload"]["wall_clock_limit_seconds"])
    progress = checkpoint_output.with_name("progress.jsonl")
    if resume_checkpoint is None:
        state = _new_state(identity)
        _atomic_write(progress, b"")
    else:
        state = _load_checkpoint(resume_checkpoint, identity, expected_keys, wall_limit, progress)
        state["resume_count"] += 1

    state["session_count"] += 1
    state["sessions"].append(
        {
            "session_index": state["session_count"] - 1,
            "hardware": hardware,
            "software": observed_software,
        }
    )
    _append_progress(
        progress,
        {
            "event": "session_started",
            "session_index": state["session_count"] - 1,
            "resume": resume_checkpoint is not None,
            "completed_invocations": len(state["completed"]),
            "consumed_wall_clock_seconds": state["consumed_wall_clock_seconds"],
        },
    )
    _persist_checkpoint(checkpoint_output, progress, state)

    _recover_pending(state, progress, checkpoint_output)

    tokenizer = None
    model = None
    if (
        len(state["completed"]) < len(tasks)
        and state["consumed_wall_clock_seconds"] < wall_limit - FINALIZATION_RESERVE_SECONDS
    ):
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            model_root,
            local_files_only=True,
            trust_remote_code=False,
        )
        model = transformers.AutoModelForCausalLM.from_pretrained(
            model_root,
            local_files_only=True,
            trust_remote_code=False,
            torch_dtype=torch.bfloat16,
            device_map="cuda",
        )

    accounted = time.monotonic()

    def account_time() -> None:
        nonlocal accounted
        now = time.monotonic()
        state["consumed_wall_clock_seconds"] += max(0.0, now - accounted)
        accounted = now

    while len(state["completed"]) < len(tasks):
        account_time()
        remaining_compute = (
            wall_limit
            - FINALIZATION_RESERVE_SECONDS
            - state["consumed_wall_clock_seconds"]
        )
        if remaining_compute <= 0:
            _append_progress(
                progress,
                {
                    "event": "wall_clock_exhausted",
                    "completed_invocations": len(state["completed"]),
                    "total_invocations": len(tasks),
                    "consumed_wall_clock_seconds": state["consumed_wall_clock_seconds"],
                },
            )
            for task in tasks[len(state["completed"]):]:
                attempt = _timeout_attempt(task["key"]["attempt_index"], "wall-clock timeout before invocation")
                _complete_record(state, progress, task["key"], attempt, 0.0)
            _persist_checkpoint(checkpoint_output, progress, state)
            break

        task = tasks[len(state["completed"])]
        if tokenizer is None or model is None:
            raise RuntimeError("model runtime is unavailable while compute budget remains")
        reserved = min(
            float(envelope["payload"]["timeout_seconds_per_invocation"]),
            remaining_compute,
        )
        state["pending"] = {"key": task["key"], "reserved_seconds": reserved}
        _append_progress(
            progress,
            {
                "event": "invocation_started",
                "sequence": len(state["completed"]),
                "key": task["key"],
                "reserved_seconds": reserved,
            },
        )
        _persist_checkpoint(checkpoint_output, progress, state)

        started = time.monotonic()
        raw = ""
        status = "error"
        grid = None
        try:
            configuration_ref = _configuration_ref(task["configuration"])
            seed = core._seed(
                configuration_ref["content_digest"],
                task["case"]["case_id"],
                task["key"]["test_index"],
                task["key"]["attempt_index"],
            )
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            inputs = tokenizer(
                core._prompt(task["case"], task["key"]["test_index"], task["prompts"]["payload"]),
                return_tensors="pt",
            ).to("cuda")
            generated = model.generate(
                **inputs,
                do_sample=envelope["payload"]["decoding"]["do_sample"],
                temperature=envelope["payload"]["decoding"]["temperature"],
                top_p=envelope["payload"]["decoding"]["top_p"],
                max_new_tokens=envelope["payload"]["output_limits"]["max_new_tokens"],
                max_time=reserved,
            )
            completion = generated[0][inputs["input_ids"].shape[1]:]
            raw = tokenizer.decode(completion, skip_special_tokens=True)
            maximum = envelope["payload"]["output_limits"]["max_response_bytes"]
            if len(raw.encode("utf-8")) > maximum:
                raw = raw.encode("utf-8")[:maximum].decode("utf-8", "ignore")
            grid = core._grid(raw)
            status = "ok" if grid is not None else "malformed"
        except RuntimeError as exc:
            raw = str(exc)
            status = "timeout" if "timeout" in raw.lower() else "error"
        elapsed = time.monotonic() - started
        if elapsed > reserved or elapsed > envelope["payload"]["timeout_seconds_per_invocation"]:
            status = "timeout"
            grid = None
        attempt = {
            "attempt_index": task["key"]["attempt_index"],
            "status": status,
            "grid": grid,
            "raw_output_digest": core._digest(raw.encode("utf-8")),
        }
        account_time()
        _complete_record(state, progress, task["key"], attempt, elapsed)
        _persist_checkpoint(checkpoint_output, progress, state)

    account_time()
    _persist_checkpoint(checkpoint_output, progress, state)
    baseline_predictions, candidate_predictions, logs = _documents(
        state, solver_cases, baseline, candidate
    )
    stop_conditions = []
    if core._NETWORK_ATTEMPTS:
        stop_conditions.append("network-attempt")
    if state["consumed_wall_clock_seconds"] > wall_limit:
        stop_conditions.append("wall-clock-limit")
    observations = {
        "format": "irisx/arc-agi-2-execution-observations",
        "format_version": "2.0",
        "hardware": hardware,
        "software": observed_software,
        "internet_disabled": True,
        "credentials_present": False,
        "network_calls": core._NETWORK_ATTEMPTS,
        "provider_calls": 0,
        "external_paid_cost_usd": 0,
        "evaluation_leaks": 0,
        "identity_binding_failures": 0,
        "wall_clock_seconds": state["consumed_wall_clock_seconds"],
        "gpu_seconds_state": "unknown",
        "gpu_seconds": None,
        "timeout_policy": envelope["payload"]["timeout_seconds_per_invocation"],
        "seed_policy": envelope["payload"]["seed_policy"],
        "attempts_per_test_input": 2,
        "stop_conditions_triggered": stop_conditions,
        "checkpoint": {
            "format": CHECKPOINT_FORMAT,
            "format_version": CHECKPOINT_VERSION,
            "resume_count": state["resume_count"],
            "session_count": state["session_count"],
            "interrupted_attempts": state["interrupted_attempts"],
            "completed_invocations": len(state["completed"]),
            "total_invocations": len(tasks),
            "cumulative_wall_clock_seconds": state["consumed_wall_clock_seconds"],
            "sessions": state["sessions"],
        },
    }
    _write_result(
        output,
        binding,
        identity,
        baseline_predictions,
        candidate_predictions,
        observations,
        logs,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--checkpoint-output", required=True, type=Path)
    parser.add_argument("--resume-checkpoint", type=Path)
    parser.add_argument("--trial-manifest-digest", required=True)
    args = parser.parse_args(argv)
    execute(
        args.trial_root,
        args.model_root,
        args.output,
        args.checkpoint_output,
        args.trial_manifest_digest,
        args.resume_checkpoint,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
