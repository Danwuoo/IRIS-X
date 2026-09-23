"""Pinned TinyRecursiveModels data and launch adapter, separate from Qwen."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .arc_nvarc_data import grid
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError
from .arc_nvarc_candidates import rank_candidates


TRM_REVISION = "e7b68717f0a6c4cbb4ce6fbef787b14f42083bd9"
NVARC_REVISION = "846d0198efa752534594e321fc3289fc0a06c657"


def trm_grid(value: Any) -> list[int]:
    """Pinned TRM 30x30 encoding: PAD 0, EOS 1, colors 2..11."""
    source = grid(value)
    canvas = [[0] * 30 for _ in range(30)]
    for row_index, row in enumerate(source):
        for col_index, color in enumerate(row):
            canvas[row_index][col_index] = color + 2
    if len(source) < 30:
        for col_index in range(len(source[0])):
            canvas[len(source)][col_index] = 1
    if len(source[0]) < 30:
        for row_index in range(len(source)):
            canvas[row_index][len(source[0])] = 1
    return [cell for row in canvas for cell in row]


def stage_trm_training(tasks: Mapping[str, Mapping[str, Any]], output: Path, *,
                       source_digest: str, augmentation_count: int) -> dict[str, Any]:
    """Write a labelled *training* artifact for the pinned upstream builder.

    This is never included in a solver outbound or inference result.
    """
    if not source_digest.startswith("sha256:") or augmentation_count < 0:
        raise ValidationError("invalid TRM training source or augmentation")
    if output.exists() and any(output.iterdir()):
        raise ValidationError("TRM staging directory must be empty")
    challenges = {}
    solutions = {}
    for task_id, task in sorted(tasks.items()):
        demos = [{"input": grid(pair["input"]), "output": grid(pair["output"])} for pair in task["train"]]
        tests = task.get("labelled_test", [])
        if not tests:
            raise ValidationError("TRM train adapter requires explicit labelled_test")
        challenges[task_id] = {"train": demos, "test": [{"input": grid(item["input"])} for item in tests]}
        solutions[task_id] = [grid(item["output"]) for item in tests]
    output.mkdir(parents=True, exist_ok=True)
    challenge_path = output / "arc-agi_sft_challenges.json"
    solution_path = output / "arc-agi_sft_solutions.json"
    challenge_path.write_bytes(canonical_bytes(challenges, newline=True))
    solution_path.write_bytes(canonical_bytes(solutions, newline=True))
    manifest = {"format": "irisx/nvarc-trm-training-stage", "artifact_kind": "training-data",
                "trm_revision": TRM_REVISION, "nvarc_revision": NVARC_REVISION,
                "source_digest": source_digest, "augmentation_count": augmentation_count,
                "challenge_digest": digest_value(challenges), "solution_digest": digest_value(solutions),
                "task_count": len(challenges), "contains_labels": True}
    (output / "manifest.json").write_bytes(canonical_bytes(manifest, newline=True))
    return manifest


def trm_preprocess_spec(upstream_root: Path, staged_root: Path, output_root: Path,
                        *, augmentation_count: int, seed: int = 42) -> dict[str, Any]:
    """Build the upstream NumPy dataset from the separately staged labels."""
    builder = upstream_root / "dataset" / "build_arc_dataset.py"
    if not builder.is_file() or augmentation_count < 0 or output_root.exists():
        raise ValidationError("TRM dataset builder or empty output directory required")
    manifest = staged_root / "manifest.json"
    if not manifest.is_file():
        raise ValidationError("TRM labelled stage manifest is missing")
    stage = json.loads(manifest.read_bytes())
    if (stage.get("format") != "irisx/nvarc-trm-training-stage" or
            stage.get("augmentation_count") != augmentation_count):
        raise ValidationError("TRM staged data and augmentation binding differ")
    prefix = staged_root / "arc-agi"
    challenge = staged_root / "arc-agi_sft_challenges.json"
    solution = staged_root / "arc-agi_sft_solutions.json"
    if not challenge.is_file() or not solution.is_file():
        raise ValidationError("TRM staged challenge/solution pair is incomplete")
    if (digest_value(json.loads(challenge.read_bytes())) != stage["challenge_digest"] or
            digest_value(json.loads(solution.read_bytes())) != stage["solution_digest"]):
        raise ValidationError("TRM staged challenge/solution digest differs")
    return {"format": "irisx/nvarc-trm-preprocess-spec",
            "upstream_revision": TRM_REVISION, "stage_digest": digest_value(stage),
            "argv": ["python", str(builder), "--input-file-prefix", str(prefix),
                     "--output-dir", str(output_root), "--subsets", "sft",
                     "--test-set-name", "evaluation", "--num-aug", str(augmentation_count),
                     "--seed", str(seed)],
            "cwd": str(upstream_root), "execution_state": "draft-not-authorized"}


def trm_launch_spec(nvarc_trm_root: Path, upstream_root: Path, data_root: Path,
                    checkpoint_root: Path, *, mode: str, world_size: int,
                    steps: int, wall_seconds: int,
                    load_checkpoint: Path | None = None) -> dict[str, Any]:
    if mode not in {"train", "evaluate"} or world_size < 1 or steps < 1 or wall_seconds < 1:
        raise ValidationError("invalid TRM launch bounds")
    if not (upstream_root / "models" / "recursive_reasoning" / "trm.py").is_file():
        raise ValidationError("pinned TRM source is unavailable")
    script = "pretrain-no-eval.py" if mode == "train" else "eval-arc-k-10.py"
    script_path = nvarc_trm_root / script
    if (not script_path.is_file() or
            not (upstream_root / "config" / "cfg_pretrain.yaml").is_file() or
            not (data_root / ("train" if mode == "train" else "test") / "dataset.json").is_file()):
        raise ValidationError("TRM script, Hydra config or processed dataset is unavailable")
    if mode == "evaluate" and (load_checkpoint is None or not load_checkpoint.is_file()):
        raise ValidationError("TRM evaluation requires an exact checkpoint file")
    argv = ["torchrun", "--standalone", "--nnodes=1", f"--nproc-per-node={world_size}",
            str(script_path), "--config-path", str(upstream_root / "config"),
            "arch=trm", f"data_paths=[{data_root.as_posix()}]",
            "arch.L_layers=2", "arch.H_cycles=3" if mode == "train" else "arch.H_cycles=4",
            "arch.L_cycles=4", "ema=True", f"epochs={steps}",
            f"+checkpoint_path={checkpoint_root.as_posix()}"]
    if mode == "train":
        argv.extend(["evaluators=[]", "lr=0.0003", "global_batch_size=3072",
                     "eval_interval=1000"])
    else:
        argv.extend(["arch.halt_max_steps=10", f"+load_checkpoint={load_checkpoint.as_posix()}",
                     "global_batch_size=128", "eval_interval=2000", "lr_warmup_steps=200",
                     "lr=0.0001"])
    return {"format": "irisx/nvarc-trm-launch-spec", "mode": mode,
            "upstream_revision": TRM_REVISION, "nvarc_revision": NVARC_REVISION,
            "argv": argv, "cwd": str(nvarc_trm_root),
            "env": {"PYTHONPATH": str(upstream_root)}, "world_size": world_size,
            "maximum_wall_seconds": wall_seconds, "maximum_steps": steps,
            "execution_state": "draft-not-authorized"}


def trm_candidates(records: list[Mapping[str, Any]]) -> dict[tuple[str, int], list[dict[str, Any]]]:
    """Normalize scored, inverse-mapped TRM outputs into branch candidates."""
    result: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for record in records:
        key = (record["task_id"], record["test_index"])
        value = grid(record["grid"])
        q = float(record["halt_probability"])
        if not 0 <= q <= 1:
            raise ValidationError("TRM halt probability outside [0,1]")
        result.setdefault(key, []).append({"grid": value, "branch": "trm",
                                            "votes": int(record["votes"]),
                                            "halt_probability": q,
                                            "source": str(record["source"])})
    for key in result:
        result[key].sort(key=lambda item: (-item["votes"], -item["halt_probability"], item["grid"]))
    return result


def integrate_attempts(qwen: list[Mapping[str, Any]], trm: list[Mapping[str, Any]], *,
                       mode: str) -> list[list[list[int]]]:
    """Fixed branch priority avoids adding uncalibrated Qwen/TRM scores."""
    if mode not in {"qwen-only", "trm-only", "combined"}:
        raise ValidationError("invalid branch mode")
    ordered = (list(qwen) if mode != "trm-only" else []) + (list(trm) if mode != "qwen-only" else [])
    attempts = []
    for candidate in ordered:
        value = grid(candidate["grid"])
        if value not in attempts:
            attempts.append(value)
        if len(attempts) == 2:
            break
    return attempts


def integrate_with_qwen_verifier(task: Mapping[str, Any], test_index: int,
                                 qwen: list[Mapping[str, Any]], trm: list[Mapping[str, Any]],
                                 verifier: Any) -> dict[str, Any]:
    """Source-style joint pool: Qwen likelihood verifies every TRM attempt.

    The caller must include these extra forward passes in the run budget.
    """
    candidates = []
    for branch, items in (("qwen", qwen), ("trm", trm)):
        for index, item in enumerate(items):
            value = grid(item["grid"])
            nll = float(verifier.verify(task, test_index, value))
            candidates.append({"grid": value, "complete": True,
                               "source": f"{branch}:{item.get('source', index)}",
                               "beam_nll": 0.0, "verification_nll": nll})
    ranked = rank_candidates(candidates, policy="votes-minus-mean-nll")
    return {"attempts": [item["grid"] for item in ranked[:2]],
            "ranked": ranked, "verification_calls": len(candidates),
            "branches": ["qwen", "trm"]}
