"""CPU process fixture: explicit synthetic evidence, no models or provider work."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--branch", required=True)
parser.add_argument("--mode", default="success")
parser.add_argument("--digest", default="fixture-plan")
parser.add_argument("--run", default="fixture-combined")
parser.add_argument("--device", default="null")
parser.add_argument("--startup-delay", type=float, default=0)
parser.add_argument("--work-delay", type=float, default=0.1)
args = parser.parse_args()
time.sleep(args.startup_delay)
root = args.output
common = {"branch": args.branch, "run_id": args.run + "-" + args.branch,
          "parent_run_id": args.run, "plan_digest": args.digest,
          "contains_evaluator_truth": False, "device": json.loads(args.device)}

def write(name, value):
    temporary = root / (name + ".tmp")
    temporary.write_text(json.dumps(value))
    os.replace(temporary, root / name)

write("worker-state.json", {**common, "phase": "loading", "reserved_counters": None, "actual_counters": None})
if args.mode == "pre-ready-fail":
    raise RuntimeError("fixture failed before readiness")
if args.mode == "pre-ready-hang":
    time.sleep(60)
write("model-ready.json", common)
if args.mode == "foreign-ready":
    write("model-ready.json", {**common, "run_id": "foreign-worker"})
if args.mode == "boolean-ready-device":
    write("model-ready.json", {**common, "device": {**common["device"], "index": False}})
if args.mode == "duplicate-ready":
    (root / "model-ready.json").write_text(json.dumps(common)[:-1] + ',"branch":"' + args.branch + '"}')
write("worker-state.json", {**common, "phase": "work", "reserved_counters": None, "actual_counters": None})
if args.mode == "work-fail":
    raise RuntimeError("fixture failed during work")
if args.mode == "work-hang-with-diagnostic-error":
    write("worker-state.json", {**common, "phase": "work", "reserved_counters": None,
                                "actual_counters": None,
                                "error": {"type": "FixtureDiagnostic", "message": "earlier worker note"}})
if args.mode in {"work-hang", "work-hang-with-diagnostic-error"}:
    time.sleep(60)
if args.mode == "log-flood":
    sys.stdout.buffer.write(b"x" * (9 * 1024 * 1024))
    sys.stderr.buffer.write(b"y" * (9 * 1024 * 1024))
    sys.stdout.flush()
    sys.stderr.flush()
time.sleep(args.work_delay)
counters = {"fixture_calls": 1}
write("fixture-result.json", {"kind": "synthetic-process-fixture", "counters": counters,
                              "visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES")})
artifacts = {"fixture-result.json": hashlib.sha256((root / "fixture-result.json").read_bytes()).hexdigest()}
if args.mode in {"descendant", "grandchild"}:
    if args.mode == "grandchild":
        # Both descendants ignore TERM and inherit pipes. Only owned-tree KILL
        # can release all resources after the primary has already exited.
        script = ("import json,os,signal,subprocess,sys,time; from pathlib import Path; "
                  "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                  "p=subprocess.Popen([sys.executable,'-c','import signal,time; "
                  "signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)']); "
                  "Path(sys.argv[1]).write_text(json.dumps({'pid':p.pid})); time.sleep(60)")
        child = subprocess.Popen([sys.executable, "-c", script, str(root / "grandchild.json")])
        until = time.monotonic() + 2
        while not (root / "grandchild.json").is_file():
            if time.monotonic() >= until:
                raise RuntimeError("fixture grandchild startup failed")
            time.sleep(.005)
        artifacts["grandchild.json"] = hashlib.sha256((root / "grandchild.json").read_bytes()).hexdigest()
    else:
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    write("descendant.json", {"pid": child.pid})
    artifacts["descendant.json"] = hashlib.sha256((root / "descendant.json").read_bytes()).hexdigest()
write("worker-terminal.json", {**common, "phase": "verified", "status": "complete",
    "artifacts": artifacts, "actual_counters": {"fixture_calls": 999} if args.mode == "forged-counters" else counters})
if args.mode == "nonfinite-diagnostics":
    write("worker-terminal.json", {**common, "phase": "verified", "status": "complete",
        "artifacts": artifacts, "actual_counters": {"fixture_calls": float("nan")}})
if args.mode in {"boolean-counters", "float-counters", "boolean-terminal-device"}:
    terminal = {**common, "phase": "verified", "status": "complete", "artifacts": artifacts,
                "actual_counters": counters}
    if args.mode == "boolean-counters":
        terminal["actual_counters"] = {"fixture_calls": True}
    elif args.mode == "float-counters":
        terminal["actual_counters"] = {"fixture_calls": 1.0}
    else:
        terminal["device"] = {**common["device"], "index": False}
    write("worker-terminal.json", terminal)
if args.mode == "tampered":
    (root / "fixture-result.json").write_text("{}")
if args.mode == "no-result":
    (root / "fixture-result.json").unlink()
