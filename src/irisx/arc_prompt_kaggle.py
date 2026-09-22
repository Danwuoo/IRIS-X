"""Private Kaggle evaluator used by the Decision 0019 GEPA controller."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from . import arc_prompt_pilot as pilot
from .arc_prompt_optimizer import (
    load_ledger,
    record_candidate_scored,
    record_candidate_staged,
    record_dataset_uploaded,
    record_kernel_accepted,
    record_kernel_submission_planned,
    record_kernel_terminal,
    record_retrieval_planned,
    record_retrieval_cli_recovery,
)
from .canonical import write_json
from .errors import ValidationError


class KaggleCandidateEvaluator:
    """Stage, execute, retrieve, verify, and score one instruction at a time."""

    def __init__(
        self,
        *,
        repository_root: Path,
        ledger_path: Path,
        baseline_trial_root: Path,
        baseline_outbound: Path,
        runtime_wheel: Path,
        search_root: Path,
        notebook_template_root: Path,
        status_query_interval_seconds: int = 180,
    ):
        self.repository_root = repository_root.resolve()
        self.ledger_path = ledger_path.resolve()
        self.baseline_trial_root = baseline_trial_root.resolve()
        self.baseline_outbound = baseline_outbound.resolve()
        self.runtime_wheel = runtime_wheel.resolve()
        self.search_root = search_root.resolve()
        self.notebook_template_root = notebook_template_root.resolve()
        self.status_query_interval_seconds = max(120, status_query_interval_seconds)

    def _run(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
        completed = subprocess.run(arguments, cwd=self.repository_root, env=environment, text=True, encoding="utf-8", capture_output=True, check=False)
        if completed.stdout:
            print(completed.stdout.rstrip(), flush=True)
        if completed.returncode != 0:
            raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(arguments)}\n{completed.stderr[-2000:]}")
        return completed

    def _dataset_status(self) -> dict[str, Any]:
        completed = self._run(["kaggle", "datasets", "status", pilot.RUNTIME_DATASET_REF, "--format", "json"])
        try:
            status = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValidationError("Kaggle Dataset status is not JSON") from exc
        if not isinstance(status.get("current_version_number"), int):
            raise ValidationError("Kaggle Dataset status lacks a version")
        return status

    def _kernel_status(self, kernel_ref: str, version: int) -> str:
        completed = self._run(["kaggle", "kernels", "status", f"{kernel_ref}/{version}"])
        text = completed.stdout
        for status in ("COMPLETE", "ERROR", "CANCELLED", "RUNNING", "QUEUED"):
            if f"KernelWorkerStatus.{status}" in text:
                return status.lower()
        raise ValidationError(f"unrecognized Kaggle kernel status: {text.strip()}")

    def _stage(self, round_index: int, instruction: str) -> dict[str, Any]:
        ledger = load_ledger(self.ledger_path)
        item = ledger["rounds"][round_index - 1]
        if item["gpu_status"] != "not-started":
            return item
        dataset_status = self._dataset_status()
        if dataset_status.get("status") != "ready":
            raise RuntimeError(f"runtime Dataset is not ready: {dataset_status}")
        expected_dataset_version = dataset_status["current_version_number"] + 1
        round_root = self.search_root / f"round-{round_index:02d}"
        outbound_dir = round_root / "outbound"
        outbound_dir.mkdir(parents=True, exist_ok=True)
        outbound = outbound_dir / f"prompt-pilot-search-g{round_index:02d}.zip"
        if outbound.exists():
            raise ValidationError("unledgered prompt-pilot candidate outbound already exists")
        built = pilot.build_search_outbound_package(
            self.baseline_trial_root,
            self.baseline_outbound,
            self.runtime_wheel,
            outbound,
            instruction=instruction,
            round_index=round_index,
            parent_instruction_digest=item["parent_instruction_digest"],
            repository_root=self.repository_root,
        )
        pilot.stage_search_dataset(outbound, self.runtime_wheel, round_root / "dataset", expected_version=expected_dataset_version)
        pilot.stage_search_kernel(
            self.notebook_template_root,
            round_root / "kernel",
            run_id=built["run"]["run_id"],
            outbound_digest=built["outbound_digest"],
            runtime_wheel_digest=pilot.digest_path(self.runtime_wheel),
        )
        return record_candidate_staged(
            self.ledger_path,
            round_index=round_index,
            run_id=built["run"]["run_id"],
            run_identity_digest=built["run"]["run_identity_digest"],
            configuration_digest=built["run"]["configuration_digest"],
            outbound_digest=built["outbound_digest"],
            dataset_version=expected_dataset_version,
        )

    def _upload_dataset(self, round_index: int, item: dict[str, Any]) -> dict[str, Any]:
        if item["gpu_status"] != "staged":
            return item
        dataset_dir = self.search_root / f"round-{round_index:02d}" / "dataset"
        started = time.monotonic()
        target_version = item["dataset_version"]
        status = self._dataset_status()
        current_version = status["current_version_number"]
        if current_version > target_version:
            raise RuntimeError(f"runtime Dataset advanced beyond the planned version: {status}")
        if not (status.get("status") == "ready" and current_version == target_version):
            if status.get("status") == "ready" and current_version < target_version:
                self._run(["kaggle", "datasets", "version", "--path", str(dataset_dir), "--message", f"Decision 0019 candidate G{round_index}", "--dir-mode", "zip"])
            elif status.get("status") not in {"pending", "running", "updating"}:
                raise RuntimeError(f"runtime Dataset is not ready for its planned update: {status}")
        while True:
            status = self._dataset_status()
            current_version = status["current_version_number"]
            if status.get("status") == "ready" and current_version == target_version:
                break
            if current_version > target_version:
                raise RuntimeError(f"runtime Dataset advanced beyond the planned version: {status}")
            if status.get("status") not in {"pending", "running", "updating", "ready"}:
                raise RuntimeError(f"runtime Dataset update failed: {status}")
            time.sleep(15)
        return record_dataset_uploaded(self.ledger_path, round_index=round_index, transport_seconds=time.monotonic() - started)

    def _submit_kernel(self, round_index: int, item: dict[str, Any]) -> dict[str, Any]:
        if item["gpu_status"] == "submitting":
            try:
                self._kernel_status(item["kernel_ref"], item["kernel_version"])
            except Exception as exc:
                raise RuntimeError("kernel submission state is ambiguous; refusing a duplicate push") from exc
            return record_kernel_accepted(self.ledger_path, round_index=round_index, transport_seconds=0.0)
        if item["gpu_status"] != "dataset-ready":
            return item
        ledger = load_ledger(self.ledger_path)
        prior_versions = [entry["kernel_version"] for entry in ledger["rounds"] if isinstance(entry.get("kernel_version"), int)]
        kernel_version = max(prior_versions, default=0) + 1
        record_kernel_submission_planned(
            self.ledger_path,
            round_index=round_index,
            kernel_ref=pilot.KAGGLE_SEARCH_KERNEL_REF,
            kernel_version=kernel_version,
            transport_seconds=0.0,
        )
        kernel_dir = self.search_root / f"round-{round_index:02d}" / "kernel"
        started = time.monotonic()
        self._run(["kaggle", "kernels", "push", "--path", str(kernel_dir), "--accelerator", pilot.KAGGLE_MACHINE_SHAPE])
        return record_kernel_accepted(self.ledger_path, round_index=round_index, transport_seconds=time.monotonic() - started)

    def _wait_terminal(self, round_index: int, item: dict[str, Any]) -> tuple[dict[str, Any], float]:
        if item["gpu_status"] != "running":
            return item, 0.0
        started = time.monotonic()
        next_query = 0.0
        while True:
            elapsed = time.monotonic() - started
            if elapsed >= next_query:
                status = self._kernel_status(item["kernel_ref"], item["kernel_version"])
                print(json.dumps({"event": "low_frequency_kernel_status", "round": round_index, "status": status, "elapsed_seconds": elapsed}, sort_keys=True), flush=True)
                if status in {"complete", "error", "cancelled"}:
                    return record_kernel_terminal(self.ledger_path, round_index=round_index, terminal_status=status), elapsed
                next_query = elapsed + self.status_query_interval_seconds
            time.sleep(60)

    def _retrieve_and_score(self, round_index: int, item: dict[str, Any], status_wait_seconds: float) -> Path:
        round_root = self.search_root / f"round-{round_index:02d}"
        retrieved = round_root / "retrieved"
        if not item["retrieval_attempted"]:
            record_retrieval_planned(self.ledger_path, round_index=round_index)
            retrieved.mkdir(parents=True, exist_ok=False)
            started = time.monotonic()
            try:
                self._run(["kaggle", "kernels", "output", f"{item['kernel_ref']}/{item['kernel_version']}", "--path", str(retrieved), "--force"])
            except RuntimeError as exc:
                if len(list(retrieved.rglob("result.zip"))) != 1:
                    raise
                evidence_path = round_root / "retrieval-cli-recovery.json"
                write_json(evidence_path, {
                    "format": "irisx/prompt-pilot-retrieval-cli-recovery",
                    "format_version": "1.0",
                    "round": round_index,
                    "kernel_ref": item["kernel_ref"],
                    "kernel_version": item["kernel_version"],
                    "error": str(exc),
                    "result_zip_present": True,
                    "second_retrieval_attempted": False,
                })
                record_retrieval_cli_recovery(self.ledger_path, round_index=round_index, evidence_path=evidence_path)
            retrieval_seconds = time.monotonic() - started
        else:
            if not retrieved.is_dir():
                raise RuntimeError("retrieval was attempted but no local quarantine directory exists")
            retrieval_seconds = 0.0
        results = list(retrieved.rglob("result.zip"))
        if len(results) != 1:
            raise RuntimeError(f"candidate output does not contain exactly one result.zip: {results}")
        result = results[0]
        outbound = round_root / "outbound" / f"prompt-pilot-search-g{round_index:02d}.zip"
        _, contents, result_digest = pilot.verify_runtime_result_package(result, outbound)
        report = pilot.score_search_result_package(self.baseline_trial_root, result, outbound)
        score_path = round_root / "score.json"
        write_json(score_path, report)
        observations = json.loads(contents["observations/execution.json"])
        gpu_seconds = float(observations.get("session_wall_seconds", 0.0))
        queue_seconds = max(0.0, status_wait_seconds - gpu_seconds)
        record_candidate_scored(
            self.ledger_path,
            round_index=round_index,
            result_digest=result_digest,
            score_path=score_path,
            gpu_runtime_seconds=gpu_seconds,
            queue_wait_seconds=queue_seconds,
            retrieval_seconds=retrieval_seconds,
        )
        return score_path

    def __call__(self, round_index: int, instruction: str) -> Path:
        item = self._stage(round_index, instruction)
        item = self._upload_dataset(round_index, item)
        item = self._submit_kernel(round_index, item)
        item, wait_seconds = self._wait_terminal(round_index, item)
        if item["gpu_status"] == "cancelled":
            raise RuntimeError("candidate kernel was cancelled")
        return self._retrieve_and_score(round_index, item, wait_seconds)
