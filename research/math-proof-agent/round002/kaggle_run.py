"""One task-owned, bounded publisher/reader. Default observe never submits.

CLI 2.2.4 ignores /version for status/logs/output. Every latest read is enclosed
by source readback checks against the pinned version and unique run manifest.
Raw receipts stay in the ignored task root; only sanitized summaries leave it.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Lock, atomic_json, digest, file_digest
from sdk_readback import notebook_source_identity

ROOT = Path(__file__).resolve().parents[3]
STATE_ROOT = ROOT / ".irisx/line-b/MATH-002"
TERMINAL = {"complete", "error", "cancelacknowledged", "canceled"}


def read_state(root):
    p = root / "state.json"
    return json.loads(p.read_text()) if p.exists() else {
        "task": "MATH-002", "limit_seconds": 21600, "limit_submissions": 4,
        "runs": [], "writer": "current-research-task-only", "monitor": "stopped"}


def receipt(root, command, timeout=120):
    stamp = f"{time.time_ns()}-{uuid.uuid4().hex[:6]}"
    start = time.monotonic()
    try:
        r = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        result = {"command": command, "exit_code": r.returncode, "stdout": r.stdout,
                  "stderr": r.stderr, "seconds": time.monotonic() - start}
    except subprocess.TimeoutExpired as exc:
        result = {"command": command, "exit_code": None, "stdout": str(exc.stdout or ""),
                  "stderr": "local command timeout", "seconds": time.monotonic() - start}
    atomic_json(root / "receipts" / (stamp + ".json"), result)
    return result


def notebook_identity(path):
    return notebook_source_identity(Path(path).read_text(encoding="utf-8"))


def source_readback(root, run, versioned):
    ref = run["notebook_id"] + ("/" + str(run["version"]) if versioned else "")
    destination = root / "readbacks" / f"{run['run_id']}-{time.time_ns()}"
    result = receipt(root, ["kaggle", "kernels", "pull", ref, "-p", str(destination), "-m"])
    if result["exit_code"] != 0:
        raise RuntimeError("source readback failed")
    meta = json.loads((destination / "kernel-metadata.json").read_text())
    code = Path(meta["code_file"])
    if code.is_absolute() or ".." in code.parts or len(code.parts) != 1:
        raise RuntimeError("unexpected remote code path")
    if meta["id"] != run["notebook_id"] or meta.get("is_private") not in (True, "true"):
        raise RuntimeError("notebook ownership/privacy mismatch")
    if notebook_identity(destination / code) != run["notebook_sha256"]:
        raise RuntimeError("remote source identity mismatch")
    # CLI metadata omits current_version_number; a read-only SDK probe retains it.
    probe = receipt(root, [sys.executable, "-P", "-s", "-B", str(Path(__file__).with_name("sdk_readback.py")), ref])
    if probe["exit_code"] != 0:
        raise RuntimeError("SDK version readback failed")
    identity = json.loads(probe["stdout"])
    if (identity["current_version_number"] != run["version"] or
            identity["notebook_sha256"] != run["notebook_sha256"] or
            identity["ref"] != run["notebook_id"] or identity["is_private"] is not True):
        raise RuntimeError("remote exact version/source/privacy mismatch")
    return {"ref": ref, "notebook_sha256": run["notebook_sha256"], "private": True,
            "current_version_number": identity["current_version_number"],
            "checked_at": time.time(), "readback_dir": str(destination)}


def reserve(state, manifest):
    runs = state["runs"]
    timeout = manifest["timeout_seconds"]
    if type(timeout) is not int or timeout <= 0 or timeout > 10800:
        raise ValueError("invalid timeout reservation")
    if not runs and (manifest["kind"] != "smoke" or timeout > 1800):
        raise ValueError("first run must be smoke <=1800 seconds")
    if len(runs) >= 4 or sum(r["timeout_seconds"] for r in runs) + timeout > 21600:
        raise ValueError("submission budget exhausted")
    if any(r["state"] not in TERMINAL | {"confirmed_not_started"} for r in runs):
        raise ValueError("previous submission unresolved or active")
    if any(r["state"] == "complete" and not r.get("retrieval", {}).get("verified") for r in runs):
        raise ValueError("completed status requires retrieved run-bound artifacts before another dispatch")
    if manifest.get("notebook_id") and any(r.get("notebook_id") == manifest["notebook_id"] for r in runs):
        raise ValueError("each attempt requires a fresh task slug; stale latest-session state must not be reused")
    if any(r["state"] in {"error", "canceled", "cancelacknowledged", "confirmed_not_started"}
           and not r.get("root_cause") for r in runs):
        raise ValueError("current research task must diagnose terminal failure before another dispatch")
    if len(runs) >= 2 and runs[-1].get("root_cause") and runs[-1].get("root_cause") == runs[-2].get("root_cause"):
        raise ValueError("same root cause twice; offline diagnosis required")
    if any(r["run_id"] == manifest["run_id"] for r in runs):
        raise ValueError("run identity reused")
    runs.append({**manifest, "state": "submission_unknown", "version": None,
                 "reserved_at": time.time(), "last_event": "reserved before push"})
    return runs[-1]


def submit(root, staging):
    staging = staging.resolve()
    manifest = json.loads((staging / "run-manifest.json").read_text())
    metadata = json.loads((staging / "kernel-metadata.json").read_text())
    if manifest["task"] != "MATH-002" or metadata["id"] != manifest["notebook_id"]:
        raise ValueError("wrong task or notebook")
    if metadata.get("is_private") not in (True, "true") or metadata.get("machine_shape") != "TpuV5E8":
        raise ValueError("privacy/accelerator mismatch")
    notebook = staging / metadata["code_file"]
    if notebook_identity(notebook) != manifest["notebook_sha256"]:
        raise ValueError("staging drift")
    with Lock(root / "task.lock"):
        state = read_state(root)
        # Exact new slug or previously bound task slug only. No metadata inference.
        if not any(r["notebook_id"] == manifest["notebook_id"] for r in state["runs"]):
            check = receipt(root, ["kaggle", "kernels", "list", "--mine", "--search",
                                   manifest["notebook_id"].split("/")[1], "--format", "json"])
            empty = check["stdout"].strip() == "Not found"
            if not empty:
                try:
                    empty = json.loads(check["stdout"]) == []
                except ValueError:
                    empty = False
            if check["exit_code"] != 0 or not empty:
                raise ValueError("new slug absence not established")
        run = reserve(state, manifest)
        atomic_json(root / "state.json", state)
        response = receipt(root, ["kaggle", "kernels", "push", "-p", str(staging),
                                  "--accelerator", "TpuV5E8", "--timeout", str(manifest["timeout_seconds"])], 180)
        run["push_exit_code"] = response["exit_code"]
        run["last_event"] = "push response saved; pending version reconciliation"
        match = re.search(r"Kernel version (\d+)", response["stdout"])
        if match and response["exit_code"] == 0:
            run["version"] = int(match.group(1))
            try:
                run["pinned_readback"] = source_readback(root, run, True)
                run["latest_readback"] = source_readback(root, run, False)
                run["state"] = "submitted"
                run["last_event"] = "version and latest source verified"
            except Exception as exc:
                run["last_event"] = "submission_unknown: " + str(exc)
        atomic_json(root / "state.json", state)
        return {k: run.get(k) for k in ("run_id", "notebook_id", "version", "state", "push_exit_code", "last_event")}


def observe_once(root, collect_logs=False):
    with Lock(root / "task.lock"):
        state = read_state(root)
        if not state["runs"]:
            return {"state": "no_submissions"}
        run = state["runs"][-1]
        if run["version"] is None:
            return {"state": "submission_unknown", "reason": "read-only manual reconciliation required; no retry"}
        try:
            run["latest_readback"] = source_readback(root, run, False)
            result = receipt(root, ["kaggle", "kernels", "status", run["notebook_id"] + "/" + str(run["version"])])
            if result["exit_code"] != 0:
                raise RuntimeError("status unavailable")
            match = re.search(r'has status "(?:KernelWorkerStatus\.)?([^".]+)"', result["stdout"])
            if not match:
                raise RuntimeError("unrecognized status")
            observed = match.group(1).lower()
            if collect_logs:
                receipt(root, ["kaggle", "kernels", "logs", run["notebook_id"]])
                run["monitor_mode"] = "snapshot_logs"
            else:
                run["monitor_mode"] = "status-only"
            run["latest_readback"] = source_readback(root, run, False)
            run["state"] = observed
            run["last_event"] = "latest status enclosed by matching source readbacks"
            run["observed_at"] = time.time()
        except Exception as exc:
            run["last_event"] = "observation_error: " + str(exc)
            state["monitor_errors"] = state.get("monitor_errors", 0) + 1
        atomic_json(root / "state.json", state)
        return {k: run.get(k) for k in ("run_id", "notebook_id", "version", "state", "last_event", "monitor_mode")}


def reconcile(root):
    """Resolve an uncertain push by reading the unique submitted source only."""
    with Lock(root / "task.lock"):
        state = read_state(root)
        run = state["runs"][-1]
        if run["state"] != "submission_unknown":
            raise ValueError("reconciliation is only for an uncertain submission")
        probe = receipt(root, [sys.executable, "-P", "-s", "-B", str(Path(__file__).with_name("sdk_readback.py")), run["notebook_id"]])
        if probe["exit_code"] == 0:
            identity = json.loads(probe["stdout"])
            if (identity.get("ref") == run["notebook_id"] and identity.get("is_private") is True
                    and identity.get("notebook_sha256") == run["notebook_sha256"]):
                run["version"] = identity["current_version_number"]
                run["pinned_readback"] = source_readback(root, run, True)
                run["latest_readback"] = source_readback(root, run, False)
                run.update(state="submitted", last_event="uncertain push reconciled by unique source and version readback")
        atomic_json(root / "state.json", state)
        return {k: run.get(k) for k in ("run_id", "notebook_id", "version", "state", "last_event")}


def retrieve(root):
    with Lock(root / "task.lock"):
        state = read_state(root)
        run = state["runs"][-1]
        if run["state"] not in TERMINAL or not run.get("version"):
            raise ValueError("not a bound terminal run")
        source_readback(root, run, True)
        source_readback(root, run, False)
        destination = root / "outputs" / f"{run['run_id']}-v{run['version']}-{time.time_ns()}"
        ref = run["notebook_id"] + "/" + str(run["version"])
        result = receipt(root, ["kaggle", "kernels", "output", ref, "-p", str(destination)])
        source_readback(root, run, False)
        run["retrieval"] = {"path": str(destination), "exit_code": result["exit_code"],
                            "api_limitation": "CLI output uses latest, enclosed by source identity checks",
                            "verified": False}
        if result["exit_code"] == 0:
            manifests = list(destination.rglob("artifact-manifest.json"))
            if len(manifests) == 1:
                artifact = json.loads(manifests[0].read_text())
                if (artifact.get("run_id") == run["run_id"] and artifact.get("code_sha") == run["code_sha"]
                        and artifact.get("source_sha256") == run["source_sha256"]):
                    base = manifests[0].parent
                    saved_manifest = base / "run-manifest.json"
                    returned = json.loads(saved_manifest.read_text()) if saved_manifest.is_file() else {}
                    keys = ("run_id", "code_sha", "source_sha256", "protocol_sha256", "panel_sha256", "model_sha256", "timeout_seconds", "source_files")
                    ok = all(returned.get(k) == run.get(k) for k in keys)
                    for name, expected_hash in artifact.get("files", {}).items():
                        p = Path(name)
                        if p.is_absolute() or ".." in p.parts or not (base / p).is_file() or file_digest(base / p) != expected_hash:
                            ok = False
                    run["retrieval"]["verified"] = ok and bool(artifact.get("files"))
        atomic_json(root / "state.json", state)
        return run["retrieval"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("observe", "submit", "retrieve", "reconcile"), nargs="?", default="observe")
    parser.add_argument("--staging", type=Path)
    parser.add_argument("--root", type=Path, default=STATE_ROOT)
    parser.add_argument("--logs", action="store_true")
    parser.add_argument("--watch-seconds", type=int, default=0)
    args = parser.parse_args()
    if args.command == "submit":
        print(json.dumps(submit(args.root, args.staging), ensure_ascii=False))
    elif args.command == "retrieve":
        print(json.dumps(retrieve(args.root), ensure_ascii=False))
    elif args.command == "reconcile":
        print(json.dumps(reconcile(args.root), ensure_ascii=False))
    else:
        if not 0 <= args.watch_seconds <= 21600:
            raise ValueError("bounded watch required")
        deadline = time.monotonic() + args.watch_seconds
        errors = 0
        with Lock(args.root / "monitor.lock"):
            while True:
                result = observe_once(args.root, args.logs)
                atomic_json(args.root / "heartbeat.json", {"pid": os.getpid(), "time": time.time(), "deadline_remaining": max(0, deadline-time.monotonic()), "result": result})
                print(json.dumps(result), flush=True)
                if result["state"] in TERMINAL | {"submission_unknown", "no_submissions"} or time.monotonic() >= deadline:
                    break
                errors = errors + 1 if result["last_event"].startswith("observation_error") else 0
                if errors >= 5:
                    break
                time.sleep(min(300, 60 * 2 ** errors, max(0, deadline - time.monotonic())))
            atomic_json(args.root / "monitor-stopped.json", {"pid": os.getpid(), "time": time.time(), "result": result})


if __name__ == "__main__":
    main()
