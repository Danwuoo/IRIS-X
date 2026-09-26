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
args = parser.parse_args()
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
write("worker-state.json", {**common, "phase": "work", "reserved_counters": None, "actual_counters": None})
if args.mode == "work-fail":
    raise RuntimeError("fixture failed during work")
if args.mode == "work-hang":
    time.sleep(60)
if args.mode == "log-flood":
    sys.stdout.buffer.write(b"x" * (9 * 1024 * 1024))
    sys.stderr.buffer.write(b"y" * (9 * 1024 * 1024))
    sys.stdout.flush()
    sys.stderr.flush()
time.sleep(0.1)
counters = {"fixture_calls": 1}
write("fixture-result.json", {"kind": "synthetic-process-fixture", "counters": counters,
                              "visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES")})
artifacts = {"fixture-result.json": hashlib.sha256((root / "fixture-result.json").read_bytes()).hexdigest()}
if args.mode == "descendant":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    write("descendant.json", {"pid": child.pid})
    artifacts["descendant.json"] = hashlib.sha256((root / "descendant.json").read_bytes()).hexdigest()
write("worker-terminal.json", {**common, "phase": "verified", "status": "complete",
    "artifacts": artifacts, "actual_counters": {"fixture_calls": 999} if args.mode == "forged-counters" else counters})
if args.mode == "tampered":
    (root / "fixture-result.json").write_text("{}")
if args.mode == "no-result":
    (root / "fixture-result.json").unlink()
