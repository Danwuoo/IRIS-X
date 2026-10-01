"""Replay one fixed published SDG response group in real WSL isolation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools.nvarc_source import verify
from irisx.arc_nvarc_sdg import WSLNamespaceProgramExecutor
from irisx.arc_nvarc_sdg_artifacts import replay
from irisx.arc_nvarc_upstream import SOURCE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--reuse-run")
    args = parser.parse_args()
    if not re.fullmatch(r"nvarc-overnight-sdg-replay-\d{3}", args.run):
        raise ValueError("new isolated SDG replay identity required")
    if args.reuse_run and (not re.fullmatch(r"nvarc-overnight-sdg-replay-\d{3}", args.reuse_run) or
                          args.reuse_run == args.run):
        raise ValueError("distinct retained SDG execution identity required")
    verify(SOURCE, json.loads((ROOT / "trials/arc-agi-2-qwen35-nvarc/source-manifest.json").read_bytes()))
    executor = WSLNamespaceProgramExecutor()
    subprocess.run(["wsl", "-d", executor.distribution, "--", "true"],
                   check=True, capture_output=True, timeout=90)
    result = replay(ROOT / ".irisx/nvarc-original/materials/sdg-first-shards-20261002-001", SOURCE,
                    ROOT / ".irisx/nvarc-original/materials/corpus-20261001-001/catalog.json",
                    ROOT / ".irisx/nvarc-original/runs" / args.run, executor,
                    reuse=ROOT / ".irisx/nvarc-original/runs" / args.reuse_run if args.reuse_run else None)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
