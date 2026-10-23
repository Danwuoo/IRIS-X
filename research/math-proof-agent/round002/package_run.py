"""Package exact committed task sources into one self-contained private notebook."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import atomic_json, digest
from kaggle_run import notebook_identity

ROOT = Path(__file__).resolve().parents[3]
PREFIX = "research/math-proof-agent/round002/"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def package(staging, run_id, notebook_id, timeout):
    # A package is always a Git snapshot, never an untracked adjacent module.
    sha = git("rev-parse", "HEAD").decode().strip()
    if git("status", "--porcelain", "--", PREFIX).strip():
        raise ValueError("commit task runtime before packaging")
    tracked = git("ls-tree", "-r", "--name-only", sha, "--", PREFIX).decode().splitlines()
    payload, hashes = {}, {}
    for name in tracked:
        relative = name[len(PREFIX):]
        if Path(relative).suffix not in {".py", ".json", ".lean", ".toml"}:
            continue
        blob = git("show", f"{sha}:{name}")
        payload[relative] = base64.b64encode(blob).decode()
        hashes[relative] = hashlib.sha256(blob).hexdigest()
    for required in ("remote_bootstrap.py", "remote_smoke.py", "model_adapter.py", "lean_worker.py", "lean_controls.py", "protocol.json", "model-candidates.json", "panel-proposal.json"):
        if required not in payload:
            raise ValueError("missing committed source: " + required)
    manifest = {"task": "MATH-002", "run_id": run_id, "kind": "smoke", "code_sha": sha,
                "notebook_id": notebook_id, "timeout_seconds": timeout,
                "accelerator": "TpuV5E8", "source_files": hashes,
                "source_sha256": digest(hashes), "protocol_sha256": hashes["protocol.json"],
                "panel_sha256": hashes["panel-proposal.json"], "model_sha256": hashes["model-candidates.json"],
                "scoring": False, "unique_writer": "MATH-002-current-research-task"}
    bootstrap = '''import base64, hashlib, json, os, pathlib, subprocess, sys, time
PAYLOAD = __PAYLOAD__
MANIFEST = __MANIFEST__
root = pathlib.Path('/kaggle/working/m002')
root.mkdir(exist_ok=False)
source = root / 'source'
source.mkdir()
output = root / 'results'
output.mkdir()
def atomic(path, value):
    temp = path.with_suffix('.tmp')
    with temp.open('w') as f:
        json.dump(value, f, sort_keys=True, indent=2)
        f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)
for name, encoded in PAYLOAD.items():
    p = source / name
    if pathlib.Path(name).is_absolute() or '..' in pathlib.Path(name).parts:
        raise ValueError('unsafe embedded source')
    p.parent.mkdir(parents=True, exist_ok=True)
    content = base64.b64decode(encoded)
    if hashlib.sha256(content).hexdigest() != MANIFEST['source_files'][name]:
        raise ValueError('embedded source mismatch')
    p.write_bytes(content)
atomic(output / 'run-manifest.json', MANIFEST)
env = {k:v for k,v in os.environ.items() if not k.upper().startswith('PYTHON')}
env.update(PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1')
start = time.monotonic()
exit_code = None
try:
    command = [sys.executable, '-P', '-s', '-B', str(source / 'remote_bootstrap.py'), '--output-dir', str(output), '--manifest', str(output / 'run-manifest.json')]
    with (output / 'child.log').open('w') as log:
        child = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=max(1, MANIFEST['timeout_seconds']-120))
    exit_code = child.returncode
except subprocess.TimeoutExpired:
    atomic(output / 'parent-timeout.json', {'status':'timeout', 'phase':'technical_smoke'})
finally:
    atomic(output / 'execution.json', {'run_id':MANIFEST['run_id'], 'code_sha':MANIFEST['code_sha'], 'exit_code':exit_code, 'wall_seconds':time.monotonic()-start, 'scored_questions':0})
    files = {p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file() and p.name != 'artifact-manifest.json'}
    atomic(output / 'artifact-manifest.json', {'run_id':MANIFEST['run_id'], 'code_sha':MANIFEST['code_sha'], 'source_sha256':MANIFEST['source_sha256'], 'files':files})
print(json.dumps({'run_id':MANIFEST['run_id'], 'exit_code':exit_code, 'output_saved':True}))
if exit_code != 0:
    raise RuntimeError('MATH-002 technical smoke did not qualify; see retained results')
'''.replace("__PAYLOAD__", repr(payload)).replace("__MANIFEST__", repr(manifest))
    nb = {"nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}},
          "cells": [{"cell_type": "code", "execution_count": None, "metadata": {},
                     "outputs": [], "source": bootstrap}]}
    staging.mkdir(parents=True, exist_ok=True)
    # Must derive metadata from actual kaggle kernels init output.
    metadata_path = staging / "kernel-metadata.json"
    meta = json.loads(metadata_path.read_text())
    if meta["id"].split("/")[0] != notebook_id.split("/")[0]:
        raise ValueError("owner differs from authenticated init")
    meta.update(id=notebook_id, title=notebook_id.split("/")[1], code_file="math002.ipynb",
                language="python", kernel_type="notebook", is_private=True, enable_gpu=False,
                enable_tpu=True, enable_internet=True, machine_shape="TpuV5E8",
                dataset_sources=[], competition_sources=[], kernel_sources=[], model_sources=[])
    atomic_json(staging / "math002.ipynb", nb)
    manifest["notebook_sha256"] = notebook_identity(staging / "math002.ipynb")
    atomic_json(metadata_path, meta)
    atomic_json(staging / "run-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--notebook-id", required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    print(json.dumps(package(args.staging, args.run_id, args.notebook_id, args.timeout), indent=2))
