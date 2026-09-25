"""Local source-profile stage; verifies pinned source before the shared runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from irisx.arc_nvarc_representation import validate_profile_material
from irisx.arc_nvarc_source_runtime import run_source_profile


def run(config_path: Path, visible_path: Path, output: Path, *, profile: str,
        fixture_path: Path | None = None, checkpoint: Path | None = None,
        material_digest: str | None = None) -> dict:
    subprocess.run([sys.executable, str(ROOT / "tools/nvarc_source.py"), "verify"],
                   check=True, stdout=subprocess.DEVNULL)
    return run_source_profile(config_path, visible_path, output, profile=profile,
                              fixture_path=fixture_path, checkpoint=checkpoint,
                              material_digest=material_digest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT /
                        "trials/arc-agi-2-qwen35-nvarc/configs/source-integration-stage.json")
    parser.add_argument("--visible", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=("fixture", "tiny", "4b"), required=True)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--material-digest")
    args = parser.parse_args()
    report = run(args.config, args.visible, args.output, profile=args.profile,
                 fixture_path=args.fixture, checkpoint=args.checkpoint,
                 material_digest=args.material_digest)
    print(json.dumps({"profile": report["profile"], "task_count": report["task_count"],
                      "test_count": report["test_count"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
