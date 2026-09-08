#!/usr/bin/env python3
"""TURN B only: validate and copy external staging into immutable run paths."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pressure_tasks as tasks  # noqa: E402


REQUIRED_TASK_ARTIFACTS = {
    "attempt-start.json", "provider-events.jsonl", "provider-stderr.txt",
    "raw-output.txt", "resource-record.json", "verification-record.json",
    "terminal-record.json", "predicate-source-map.json", "run-manifest.json",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch-manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = tasks.load_object(args.launch_manifest)
        staging = Path(manifest["external_staging"]["staging_root"])
        completion = staging / "batch-completion.json"
        if not completion.is_file():
            raise ValueError("batch completion artifact is absent")
        destination = EXPERIMENT_ROOT / "runs/batch-2"
        for task_key in tasks.TASK_KEYS:
            task_dir = staging / task_key
            if not task_dir.exists():
                continue
            names = {path.name for path in task_dir.iterdir() if path.is_file()}
            missing = REQUIRED_TASK_ARTIFACTS - names
            if missing:
                raise ValueError(f"staging task artifacts missing for {task_key}: {sorted(missing)}")
        if (destination / completion.name).exists():
            raise FileExistsError("immutable collected completion record already exists")
        shutil.copy2(completion, destination / completion.name)
        for task_key in tasks.TASK_KEYS:
            if (staging / task_key).is_dir():
                if (destination / task_key).exists():
                    raise FileExistsError(f"immutable collected task path already exists: {task_key}")
                shutil.copytree(staging / task_key, destination / task_key)
        print(destination)
        return 0
    except (OSError, ValueError) as exc:
        print(f"Phase 6 Batch 2 collection: FAIL ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
