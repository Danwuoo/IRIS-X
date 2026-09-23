"""Resume the exact Decision 0020 workflow from its atomic local ledger.

This command never repeats an attempted upload, kernel push or terminal output
retrieval when their outcome is ambiguous. It makes no proposer/model API calls.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

from irisx import arc_budget_ablation as budget
from irisx.transport import digest_path
from stage_budget_ablation import stage


ROOT = Path(".irisx/arc-agi-2/budget-ablation")
LEDGER = ROOT / "ledger.json"
OLD = Path("C:/Users/wurre/.codex/worktrees/e34a/IRIS-X/.irisx/arc-agi-2/prompt-pilot")
BASELINE_SCORE = OLD / "search/baseline-score.json"
BASELINE_RESULT = OLD / "repair-002/recovered-v1/result.zip"
TERMINAL = {"complete", "error", "cancelled"}


def _load() -> dict:
    value = json.loads(LEDGER.read_bytes())
    budget.validate_ledger(value)
    return value


def _run(*arguments: str) -> str:
    process = subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8", errors="replace",
                             env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    if process.returncode:
        raise RuntimeError(f"{' '.join(arguments)} failed ({process.returncode}): {process.stderr[-2000:]} {process.stdout[-1000:]}")
    return process.stdout


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _status(ref: str, version: int) -> str:
    output = _run("kaggle", "kernels", "status", f"{ref}/{version}")
    for candidate in ("COMPLETE", "ERROR", "CANCELLED", "RUNNING", "QUEUED"):
        if f"KernelWorkerStatus.{candidate}" in output:
            return candidate.lower()
    raise RuntimeError(f"unknown kernel status: {output.strip()}")


def _wait_terminal(section: str) -> str:
    prior = None
    consecutive_status_errors = 0
    while True:
        entry = _load()[section]
        if entry["state"] not in {"running", "launching"}:
            return entry.get("terminal_status", "")
        try:
            status = _status(entry["kernel_ref"], entry["kernel_version"])
        except RuntimeError as error:
            consecutive_status_errors += 1
            budget.atomic_json(ROOT / f"{section}/status-error-{consecutive_status_errors}.json",
                               {"at_utc": _utc(), "error": str(error), "consecutive_failures": consecutive_status_errors})
            if consecutive_status_errors >= 3:
                raise RuntimeError("three consecutive low-frequency status requests failed; run identity remains unchanged") from error
            time.sleep(180)
            continue
        consecutive_status_errors = 0
        if status != prior:
            print(json.dumps({"event": "kernel_status", "run": section, "status": status, "at_utc": _utc()}), flush=True)
        prior = status
        if status in TERMINAL:
            budget.update_ledger(LEDGER, section, state="terminal", terminal_status=status, terminal_at_utc=_utc())
            return status
        time.sleep(180)


def _verify_startup(contents: dict[str, bytes]) -> dict:
    checkpoint = json.loads(contents["checkpoint/checkpoint.json"])
    observations = json.loads(contents["observations/execution.json"])
    ready = observations.get("model_ready", {})
    hardware = observations.get("hardware", [])
    events = [json.loads(line) for line in contents["logs/progress.jsonl"].splitlines() if line]
    dispatched = {event["rank"] for event in events if event.get("event") == "generation_invocation_dispatched"}
    if set(ready) != {"0", "1", "2", "3"} or len({event["gpu_uuid"] for event in ready.values()}) != 4:
        raise RuntimeError("four distinct exact-model-ready workers were not verified")
    if any(event["model_revision"] != budget.MODEL_REVISION for event in ready.values()):
        raise RuntimeError("model-ready revision differs")
    if len(hardware) != 4 or len({gpu["uuid"] for gpu in hardware}) != 4 or any("L4" not in gpu["name"] for gpu in hardware):
        raise RuntimeError("four distinct L4 hardware identities were not verified")
    if dispatched != {0, 1, 2, 3}:
        raise RuntimeError("initial four-card dispatch was not verified")
    return {"model_ready_ranks": sorted(ready), "distinct_gpu_uuids": len({event["gpu_uuid"] for event in ready.values()}),
            "dispatched_ranks": sorted(dispatched), "generation_invocations": len(checkpoint["generation_invocations"]),
            "session_wall_seconds": observations.get("session_wall_seconds")}


def _retrieve_score(section: str, cohort: dict | None) -> dict:
    ledger = _load()
    entry = ledger[section]
    run_id = budget.DIAGNOSTIC_RUN if section == "diagnostic" else budget.VALIDATION_RUN
    run_root = ROOT / section
    retrieved = run_root / "retrieved"
    if not entry.get("retrieval_attempted"):
        if entry.get("state") != "terminal":
            raise RuntimeError("kernel must be terminal before its one output retrieval")
        budget.update_ledger(LEDGER, section, retrieval_attempted=True, state="retrieving", retrieval_started_utc=_utc())
        retrieved.mkdir(exist_ok=False)
        try:
            output = _run("kaggle", "kernels", "output", f"{entry['kernel_ref']}/{entry['kernel_version']}",
                          "--path", str(retrieved.resolve()), "--force")
            (run_root / "retrieval-cli-output.txt").write_text(output, encoding="utf-8")
        except RuntimeError as error:
            budget.atomic_json(run_root / "retrieval-cli-error.json", {"error": str(error), "at_utc": _utc(),
                                                                       "second_retrieval_attempted": False})
            if len(list(retrieved.rglob("result.zip"))) != 1:
                raise
    else:
        if not retrieved.is_dir():
            raise RuntimeError("retrieval was attempted but no local output directory exists")
    results = list(retrieved.rglob("result.zip"))
    if len(results) != 1:
        raise RuntimeError(f"terminal output lacks exactly one result.zip: {results}")
    result = results[0]
    outbound = run_root / "outbound" / f"{run_id}.zip"
    _, contents, digest = budget.verify_result_package(result, outbound)
    startup = _verify_startup(contents)
    if startup["generation_invocations"] > entry["reserved_generations"]:
        raise RuntimeError("kernel exceeded its reserved generation count")
    report = budget.score_ablation_result(result, outbound, BASELINE_SCORE, BASELINE_RESULT, cohort)
    budget.atomic_json(run_root / "score.json", report)
    budget.update_ledger(LEDGER, section, state="scored", result_digest=digest,
                         score_digest=digest_path(run_root / "score.json"), startup_evidence=startup,
                         consumed_generations=startup["generation_invocations"], scored_at_utc=_utc())
    print(json.dumps({"event": "run_scored", "run": section, "result_digest": digest,
                      "startup": startup, "arms": {arm: {"correct": x["correct"], "net": x["net_additional_correct"]}
                                               for arm, x in report["arms"].items()}}, sort_keys=True), flush=True)
    return report


def _prepare_validation(arm: str) -> None:
    ledger = _load()
    entry = ledger["validation"]
    if entry["state"] != "conditional":
        return
    if digest_path(ROOT / "runtime/irisx-0.2.0-py3-none-any.whl") != ledger["diagnostic"]["runtime_wheel_digest"]:
        raise RuntimeError("validation runtime wheel differs from diagnostic")
    built = stage(ROOT, budget.VALIDATION_RUN, arm)
    budget.update_ledger(LEDGER, "validation", state="staged", selected_arm=arm, **{
        key: built[key] for key in ("run_identity_digest", "workload_digest", "outbound_digest",
                               "runtime_wheel_digest", "kernel_metadata_digest", "notebook_digest", "dataset_ref")})
    print(json.dumps({"event": "validation_staged", "arm": arm, "outbound_digest": built["outbound_digest"]}), flush=True)


def _upload_validation() -> None:
    entry = _load()["validation"]
    if entry["state"] == "dataset-uploading":
        status = json.loads(_run("kaggle", "datasets", "status", entry["dataset_ref"], "--format", "json"))
        if status.get("status") == "ready" and status.get("current_version_number") == 2:
            budget.update_ledger(LEDGER, "validation", state="dataset-ready", dataset_ready_utc=_utc())
            return
        if status.get("current_version_number") == 2 and status.get("status") in {"pending", "running", "updating"}:
            for _ in range(40):
                time.sleep(15)
                status = json.loads(_run("kaggle", "datasets", "status", entry["dataset_ref"], "--format", "json"))
                if status.get("status") == "ready" and status.get("current_version_number") == 2:
                    budget.update_ledger(LEDGER, "validation", state="dataset-ready", dataset_ready_utc=_utc())
                    return
            raise TimeoutError("attempted validation Dataset version 2 remains pending")
        raise RuntimeError(f"attempted validation Dataset upload is ambiguous; no duplicate mutation: {status}")
    if entry["state"] != "staged":
        return
    status = json.loads(_run("kaggle", "datasets", "status", entry["dataset_ref"], "--format", "json"))
    if status.get("status") != "ready" or status.get("current_version_number") != 1:
        raise RuntimeError(f"validation Dataset must begin at ready version 1: {status}")
    budget.update_ledger(LEDGER, "validation", state="dataset-uploading", dataset_version=2,
                         dataset_upload_attempted=True, dataset_upload_started_utc=_utc())
    _run("kaggle", "datasets", "version", "--path", str((ROOT / "validation/dataset").resolve()),
         "--message", f"Decision 0020 validation {_load()['validation']['selected_arm']}", "--dir-mode", "zip")
    for _ in range(40):
        status = json.loads(_run("kaggle", "datasets", "status", entry["dataset_ref"], "--format", "json"))
        if status.get("status") == "ready" and status.get("current_version_number") == 2:
            budget.update_ledger(LEDGER, "validation", state="dataset-ready", dataset_ready_utc=_utc())
            return
        if status.get("current_version_number", 0) > 2 or status.get("status") not in {"pending", "running", "updating", "ready"}:
            raise RuntimeError(f"validation Dataset update failed: {status}")
        time.sleep(15)
    raise TimeoutError("validation Dataset version 2 was not ready within ten minutes")


def _launch_validation() -> None:
    entry = _load()["validation"]
    if entry["state"] != "dataset-ready":
        return
    if entry.get("launch_attempted"):
        raise RuntimeError("validation launch was already attempted")
    budget.update_ledger(LEDGER, "validation", state="launching", launch_attempted=True,
                         kernel_version=1, generation_budget_committed=384, launch_started_utc=_utc())
    _run("kaggle", "kernels", "push", "--path", str((ROOT / "validation/kernel").resolve()),
         "--accelerator", "NvidiaL4")
    budget.update_ledger(LEDGER, "validation", state="running", kernel_push_accepted_utc=_utc())
    print(json.dumps({"event": "validation_kernel_accepted", "ref": entry["kernel_ref"], "version": 1}), flush=True)


def main() -> int:
    diagnostic = _load()["diagnostic"]
    if diagnostic["state"] in {"running", "launching"}:
        _wait_terminal("diagnostic")
    if _load()["diagnostic"]["state"] in {"terminal", "retrieving"}:
        cohort = json.loads((ROOT / "cohort.json").read_bytes())
        report = _retrieve_score("diagnostic", cohort)
    elif _load()["diagnostic"]["state"] == "scored":
        report = json.loads((ROOT / "diagnostic/score.json").read_bytes())
    else:
        raise RuntimeError(f"diagnostic is not resumable from state {_load()['diagnostic']['state']}")
    gate = budget.choose_validation_arm(report)
    budget.atomic_json(ROOT / "diagnostic/qualification.json", gate)
    if gate["selected_arm"] is None:
        budget.update_ledger(LEDGER, "validation", state="not-qualified", selected_arm=None)
        print(json.dumps({"event": "ablation_complete_no_validation", "gate": gate}), flush=True)
        return 0
    arm = gate["selected_arm"]
    entry = _load()["validation"]
    if entry["state"] == "conditional":
        _prepare_validation(arm)
    elif entry.get("selected_arm") != arm:
        raise RuntimeError("frozen validation arm differs from scored gate")
    _upload_validation()
    _launch_validation()
    if _load()["validation"]["state"] in {"running", "launching"}:
        _wait_terminal("validation")
    if _load()["validation"]["state"] in {"terminal", "retrieving"}:
        _retrieve_score("validation", None)
    if _load()["validation"]["state"] != "scored":
        raise RuntimeError(f"validation is not scored: {_load()['validation']['state']}")
    print(json.dumps({"event": "ablation_complete_with_validation", "arm": arm}), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        budget.atomic_json(ROOT / "controller-failure.json", {"at_utc": _utc(), "type": type(error).__name__,
                                                              "detail": str(error), "ledger_state": _load()})
        raise
