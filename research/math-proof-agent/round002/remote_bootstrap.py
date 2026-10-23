"""Public dependency preparation in a task-owned /tmp venv, with total deadline.

This setup is not a sandbox. It never receives or executes model proof bodies.
Credential files and full environments are never copied into result artifacts.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import atomic_json, python_environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    manifest = json.loads(args.manifest.read_text())
    output = args.output_dir
    deadline_epoch = time.time() + manifest["timeout_seconds"] - 150
    report = {"status": "preparing", "commands": [], "run_id": manifest["run_id"], "network_purpose": "public dependencies and immutable weights only"}

    def run(command, name, cap):
        left = min(cap, deadline_epoch - time.time())
        if left <= 0:
            raise TimeoutError("setup deadline exhausted")
        start = time.monotonic()
        with (output / (name + ".log")).open("w") as log:
            r = subprocess.run(command, env=python_environment(), stdout=log, stderr=subprocess.STDOUT, timeout=left)
        report["commands"].append({"command": command, "exit_code": r.returncode, "wall_seconds": time.monotonic()-start})
        atomic_json(output / "setup-report.json", report)
        return r.returncode

    try:
        # Existing-backend observation is independent of selected runtime pins.
        probe = "import json,jax; d=jax.devices(); print(json.dumps({'backend':jax.default_backend(),'jax':jax.__version__,'devices':[{'platform':x.platform,'kind':x.device_kind,'id':x.id} for x in d]})); raise SystemExit(0 if len(d)==8 and all(x.platform=='tpu' and ('v5e' in x.device_kind.lower() or 'v5 lite' in x.device_kind.lower()) for x in d) else 7)"
        raw = run([sys.executable, "-P", "-s", "-B", "-c", probe], "platform-preflight", 120)
        if raw != 0:
            report.update(status="preflight_failed", blocker="platform_backend_not_qualified", weights_downloaded=False)
            atomic_json(output / "setup-report.json", report)
            return 7
        # This actual isolation result is retained even if model setup later fails.
        run([sys.executable, "-P", "-s", "-B", str(source / "lean_controls.py"), "--isolation-only", "--output", str(output / "remote-isolation.json")], "remote-isolation", 60)
        scratch = Path("/tmp") / manifest["run_id"]
        scratch.mkdir(exist_ok=False)
        venv = scratch / "venv"
        if run([sys.executable, "-P", "-s", "-B", "-m", "venv", str(venv)], "venv", 60):
            raise RuntimeError("venv creation failed")
        python = str(venv / "bin/python")
        spec = json.loads((source / "model-candidates.json").read_text())
        pins = spec["runtime"]["packages"]
        torch_pin = "torch==" + pins["torch"]
        if run([python, "-P", "-s", "-B", "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--no-deps", torch_pin,
                "--index-url", "https://download.pytorch.org/whl/cpu"], "torch-install", 480):
            raise RuntimeError("CPU reference dependency installation failed")
        requirements = [key + "==" + value for key, value in pins.items() if key != "torch"]
        if run([python, "-P", "-s", "-B", "-m", "pip", "install", "--disable-pip-version-check", "--no-input", *requirements], "runtime-install", 480):
            raise RuntimeError("fixed runtime installation failed")
        run([python, "-P", "-s", "-B", "-m", "pip", "freeze"], "runtime-freeze", 30)
        result = run([python, "-P", "-s", "-B", str(source / "remote_smoke.py"),
                      "--output-dir", str(output), "--manifest", str(args.manifest),
                      "--run-id", manifest["run_id"], "--candidates", str(source / "model-candidates.json"),
                      "--candidate", "all", "--deadline-epoch", str(deadline_epoch),
                      "--timeout-seconds", str(manifest["timeout_seconds"]), "--cache-dir", str(scratch / "hf-cache")],
                     "model-smoke", manifest["timeout_seconds"])
        report.update(status="model_smoke_finished", model_smoke_exit_code=result,
                      lean_full_controls="not_executed_no_remote_pinned_Lean_runtime", panel_scoring_allowed=False)
        atomic_json(output / "setup-report.json", report)
        return result
    except Exception as exc:
        report.update(status="preflight_failed", blocker=type(exc).__name__ + ": " + str(exc))
        atomic_json(output / "setup-report.json", report)
        return 8


if __name__ == "__main__":
    raise SystemExit(main())
