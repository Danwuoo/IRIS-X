"""Local, truth-free source-integration profile over the existing solver core.

No Kaggle, teacher, scoring or Dataset mutation path exists in this command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from irisx.arc_nvarc_candidates import (FixtureCandidateBackend,
                                         QwenCandidateBackend, solve_task)
from irisx.arc_nvarc_data import visible_task
from irisx.arc_nvarc_representation import verify_model_material
from irisx.arc_nvarc_training import TaskLocalAdapter, load_compact_model
from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError


def run(config_path: Path, visible_path: Path, output: Path, *, profile: str,
        fixture_path: Path | None = None, checkpoint: Path | None = None,
        material_digest: str | None = None) -> dict:
    config = json.loads(config_path.read_bytes())
    if config.get("format") != "irisx/nvarc-source-stage-v1" or profile not in config.get("profiles", {}):
        raise ValidationError("unknown source integration stage/profile")
    candidate, adaptation = config["candidate"], config["adaptation"]
    if (candidate.get("augmentation") != "source-qwen" or
            candidate.get("representation") != "source-qwen" or
            candidate.get("ranking") != "source-kgmon" or
            adaptation.get("source_qwen") is not True):
        raise ValidationError("source stage algorithm bindings differ")
    if output.exists():
        raise ValidationError("source stage output must be new")
    subprocess.run([sys.executable, str(ROOT / "tools/nvarc_source.py"), "verify"],
                   check=True, stdout=subprocess.DEVNULL)
    raw = json.loads(visible_path.read_bytes())
    if not isinstance(raw, dict) or not raw:
        raise ValidationError("source stage needs nonempty visible tasks")
    tasks = [visible_task(task_id, value) for task_id, value in sorted(raw.items())]
    if profile == "fixture":
        if fixture_path is None or checkpoint is not None or material_digest is not None:
            raise ValidationError("fixture profile requires only synthetic predictions")
        predictions = json.loads(fixture_path.read_bytes())
        backend = FixtureCandidateBackend(predictions)
    else:
        if fixture_path is not None or checkpoint is None or material_digest is None:
            raise ValidationError("model profile requires checkpoint and material digest")
        pinned = config["profiles"][profile].get("material_digest")
        if pinned is not None and material_digest != pinned:
            raise ValidationError("4B compact material identity differs")
        verify_model_material(checkpoint, material_digest)
        model = load_compact_model(checkpoint, dtype="float32" if profile == "tiny" else "bfloat16")
        adapter = TaskLocalAdapter(model, adaptation)
        backend = QwenCandidateBackend(model, task_adapter=adapter,
                                       dfs_max_expansions=int(candidate["dfs_max_expansions"]))
    results = [item for task in tasks for item in solve_task(task, backend, candidate)]
    report = {"format": "irisx/nvarc-source-stage-result-v1", "profile": profile,
              "source_profile": config["source_profile"],
              "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
              "visible_sha256": hashlib.sha256(visible_path.read_bytes()).hexdigest(),
              "material_digest": material_digest,
              "task_count": len(tasks), "test_count": sum(len(task["test"]) for task in tasks),
              "results": results, "contains_evaluator_truth": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(report, newline=True))
    return report


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
