"""Local installed-wheel Linux regression using cached dependencies, no download."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tests.nvarc_deployment_strict import prepare_probe


def linux_path(path: Path) -> str:
    absolute = path.resolve().as_posix()
    if not absolute.startswith("C:/"):
        raise ValueError("deployment probe needs a C: workspace path")
    return "/mnt/c" + absolute[2:]


def run(output: Path, runtime: str) -> dict:
    if output.exists():
        raise ValueError("new deployment probe directory required")
    prepare_probe(output)
    deps = output / "deps"
    # These previously acquired Linux wheels are installed only into this probe.
    wheels = ROOT / ".irisx/arc-agi-2/trial-001/runtime/linux-cp312"
    for wheel in sorted(wheels.glob("*.whl")):
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(deps)
    # PEFT is pure Python; copy the existing pinned local install unchanged.
    installed = ROOT / ".irisx/nvarc-ml-venv/Lib/site-packages"
    for name in ("peft", "peft-0.21.0.dist-info"):
        shutil.copytree(installed / name, deps / name)
    probe = output / "probe.py"
    probe.write_text(probe.read_text().replace('sys.path.insert(0, str(root / "site"))',
        'sys.path.insert(0, str(root / "site"))\nsys.path.insert(0, str(root / "deps"))'), encoding="utf-8")
    command = ["wsl", "-d", "Ubuntu-24.04", "--", "unshare", "--user", "--map-root-user",
               "--mount", "--net", "sh", linux_path(ROOT / "tools/nvarc_deployment_namespace.sh"),
               linux_path(output), runtime, linux_path(ROOT)]
    completed = subprocess.run(command, capture_output=True, timeout=600)
    (output / "stdout.txt").write_bytes(completed.stdout)
    (output / "stderr.txt").write_bytes(completed.stderr)
    if completed.returncode:
        raise RuntimeError("Linux deployment probe failed; inspect its retained stderr.txt")
    report = json.loads((output / "probe-result.json").read_bytes())
    report.update(checkout_hidden_by_mount=True, isolated_network_namespace=True)
    (output / "deployment-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--linux-python", default="/home/wurre/envs/ai/bin/python")
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.linux_python), indent=2))
