"""Pinned TinyRecursiveModels data and launch adapter, separate from Qwen."""

from __future__ import annotations

import json
import hashlib
import math
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Mapping

from .arc_nvarc_data import grid
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError
from .arc_nvarc_candidates import rank_candidates


TRM_REVISION = "e7b68717f0a6c4cbb4ce6fbef787b14f42083bd9"
NVARC_REVISION = "846d0198efa752534594e321fc3289fc0a06c657"
TRM_SOURCE_HASHES = {
    "builder": "f6e452979cdaa438e46c82eaea1f2fe34cef828debd4b94e1b5139d13aca7c60",
    "train": "59dfb2523507046af3126790c473f371111f7b7ded77233266a71ea13d3104ac",
    "evaluate": "62ec1e2f179cd80c58a7f0067ab51c76e2e7eb213959566b015c107c5d98b36f",
}


def _pinned_file(path: Path, expected: str) -> None:
    if (not path.is_file() or path.is_symlink() or
            hashlib.sha256(path.read_bytes()).hexdigest() != expected):
        raise ValidationError(f"pinned TRM source differs: {path.name}")


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
            "cwd": str(upstream_root),
            "source_file": str(builder), "source_sha256": TRM_SOURCE_HASHES["builder"],
            "execution_state": "draft-not-authorized"}


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
    if mode == "evaluate" and (load_checkpoint is None or not load_checkpoint.is_file() or
                                not (data_root / "identifiers.json").is_file()):
        raise ValidationError("TRM evaluation requires an exact checkpoint file")
    argv = ["torchrun", "--standalone", "--nnodes=1", f"--nproc-per-node={world_size}"]
    if mode == "train":
        argv.extend([str(script_path), "--config-path", str(upstream_root / "config"),
                     "arch=trm", f"data_paths=[{data_root.as_posix()}]",
                     "arch.L_layers=2", "arch.H_cycles=3", "arch.L_cycles=4",
                     "ema=True", f"epochs={steps}",
                     f"+checkpoint_path={checkpoint_root.as_posix()}"])
        argv.extend(["evaluators=[]", "lr=0.0003", "global_batch_size=3072",
                     "eval_interval=1000"])
    else:
        from .arc_nvarc_trm_infer import _sha256
        argv.extend(["-m", "irisx.arc_nvarc_trm_infer",
                     "--source-script", str(script_path),
                     "--upstream-root", str(upstream_root), "--data-root", str(data_root),
                     "--checkpoint", str(load_checkpoint),
                     "--checkpoint-sha256", _sha256(load_checkpoint),
                     "--dataset-sha256", _sha256(data_root / "test" / "dataset.json"),
                     "--output", str(checkpoint_root), "--max-batches", str(steps)])
    return {"format": "irisx/nvarc-trm-launch-spec", "mode": mode,
            "upstream_revision": TRM_REVISION, "nvarc_revision": NVARC_REVISION,
            "argv": argv, "cwd": str(nvarc_trm_root),
            "env": {"PYTHONPATH": str(upstream_root) + os.pathsep +
                    str(Path(__file__).resolve().parents[1])}, "world_size": world_size,
            "maximum_wall_seconds": wall_seconds,
            "maximum_epochs": steps if mode == "train" else None,
            "maximum_batches": steps if mode == "evaluate" else None,
            "step_semantics": ("inference-only test batches; zero optimizer steps" if mode == "evaluate"
                               else "upstream derives optimizer steps from epochs and dataset size"),
            "output_root": str(checkpoint_root),
            "source_file": str(script_path), "source_sha256": TRM_SOURCE_HASHES[mode],
            "execution_state": "draft-not-authorized"}


def execute_trm_spec(spec: Mapping[str, Any], output: Path, *,
                     authorization: Mapping[str, Any] | None = None,
                     fixture_command: list[str] | None = None) -> dict[str, Any]:
    """Execute a bounded subprocess; fixture launch never has model provenance."""
    if spec.get("format") not in {"irisx/nvarc-trm-preprocess-spec", "irisx/nvarc-trm-launch-spec"}:
        raise ValidationError("TRM invocation spec differs")
    if (spec.get("mode") == "evaluate" and
            output.resolve() != Path(spec.get("output_root", "")).resolve()):
        raise ValidationError("TRM inference output root differs from bound spec")
    if output.exists() and any(output.iterdir()):
        raise ValidationError("TRM invocation output must be empty")
    identity = digest_value(spec)
    if fixture_command is None:
        if (authorization is None or authorization.get("approved") is not True or
                authorization.get("operation") != "execute-trm" or
                authorization.get("identity_digest") != identity or
                not authorization.get("owner_decision")):
            raise ValidationError("real TRM invocation has no matching owner authorization")
        _pinned_file(Path(spec["source_file"]), spec["source_sha256"])
        argv = list(spec["argv"])
        kind = "upstream"
    else:
        argv = fixture_command
        kind = "launch-fixture"
    wall = int(spec.get("maximum_wall_seconds", 60))
    if wall < 1:
        raise ValidationError("TRM wall limit invalid")
    output.mkdir(parents=True, exist_ok=True)
    report = {"format": "irisx/nvarc-trm-invocation", "identity_digest": identity,
              "source_kind": kind, "status": "pending", "maximum_wall_seconds": wall}
    (output / "invocation.json").write_bytes(canonical_bytes(report, newline=True))
    log = output / "invocation.log"
    started = time.monotonic()
    with log.open("wb") as stream:
        process = subprocess.Popen(argv, cwd=spec["cwd"], stdout=stream,
                                   stderr=subprocess.STDOUT, env={**os.environ, **spec.get("env", {})},
                                   creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                                   start_new_session=os.name != "nt")
        try:
            code = process.wait(timeout=wall)
            status = "complete" if code == 0 else "failed"
        except subprocess.TimeoutExpired:
            code, status = None, "timeout"
            if os.name == "nt":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                               capture_output=True, check=False)
            else:
                import signal
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
    report.update({"status": status, "exit_code": code,
                   "elapsed_seconds": time.monotonic() - started})
    (output / "invocation.json").write_bytes(canonical_bytes(report, newline=True))
    return report


def read_trm_submission(path: Path, expected_tests: Mapping[str, int], *,
                        invocation: Mapping[str, Any]) -> dict[tuple[str, int], list[dict[str, Any]]]:
    """Parse upstream attempt grids; launch fixtures cannot claim model output."""
    kind = invocation.get("source_kind")
    if (kind not in {"upstream", "parser-fixture"} or
            invocation.get("status") != "complete"):
        raise ValidationError("TRM output needs a successful upstream invocation or explicit parser fixture")
    submission = json.loads(path.read_bytes())
    if set(submission) != set(expected_tests):
        raise ValidationError("TRM submission task denominator differs")
    result = {}
    for task_id, count in expected_tests.items():
        tests = submission[task_id]
        if type(count) is not int or count < 1 or not isinstance(tests, list) or len(tests) != count:
            raise ValidationError("TRM submission test denominator differs")
        for test_index, attempts in enumerate(tests):
            if not isinstance(attempts, dict) or set(attempts) != {f"attempt_{i}" for i in range(1, 11)}:
                raise ValidationError("TRM upstream ten-attempt schema differs")
            result[(task_id, test_index)] = [
                {"grid": grid(attempts[f"attempt_{i}"]),
                 "branch": "trm" if kind == "upstream" else "trm-fixture",
                 "source": f"{kind}:attempt_{i}", "rank": i}
                for i in range(1, 11)]
    return result


def _decode_trm_tensor(value: Any) -> list[list[int]]:
    """Mirror the pinned evaluator's largest EOS-free top-left crop."""
    cells = value.tolist() if hasattr(value, "tolist") else value
    if not isinstance(cells, list) or len(cells) != 900:
        raise ValidationError("TRM grid tensor is not 30x30")
    rows = [cells[start:start + 30] for start in range(0, 900, 30)]
    best_area = 0
    best_shape = (0, 0)
    columns = 30
    for height in range(1, 31):
        for col in range(1, columns + 1):
            value = rows[height - 1][col - 1]
            if type(value) is not int or value < 2 or value > 11:
                columns = col - 1
                break
        if height * columns > best_area:
            best_area, best_shape = height * columns, (height, columns)
    height, width = best_shape
    if not height or not width:
        raise ValidationError("TRM grid tensor has no complete grid")
    return grid([[rows[row][col] - 2 for col in range(width)] for row in range(height)])


def _inverse_trm_augmentation(name: str, value: list[list[int]]) -> tuple[str, list[list[int]]]:
    if "|||" not in name:
        return name, value
    import numpy as np

    parts = name.split("|||")
    if (len(parts) != 3 or not parts[0] or not parts[1].startswith("t") or
            parts[1] not in {f"t{i}" for i in range(8)} or
            len(parts[2]) != 10 or set(parts[2]) != set("0123456789")):
        raise ValidationError("TRM augmentation identifier differs")
    tid = int(parts[1][1:])
    inverse = (0, 3, 2, 1, 4, 5, 6, 7)[tid]
    array = np.array(value, dtype=np.uint8)
    if inverse == 1:
        array = np.rot90(array, 1)
    elif inverse == 2:
        array = np.rot90(array, 2)
    elif inverse == 3:
        array = np.rot90(array, 3)
    elif inverse == 4:
        array = np.fliplr(array)
    elif inverse == 5:
        array = np.flipud(array)
    elif inverse == 6:
        array = array.T
    elif inverse == 7:
        array = np.fliplr(np.rot90(array, 1))
    permutation = [int(char) for char in parts[2]]
    return parts[0], grid(np.argsort(permutation).astype(np.uint8)[array].tolist())


def read_trm_prediction_tensors(files: list[Path], identifiers_path: Path,
                                visible_cases: Mapping[str, Mapping[str, Any]], *,
                                invocation: Mapping[str, Any],
                                expected_ranks: int) -> dict[str, Any]:
    """Normalize saved upstream tensors using visible inputs, never evaluator labels."""
    import torch

    kind = invocation.get("source_kind")
    if kind not in {"upstream", "parser-fixture"} or invocation.get("status") != "complete":
        raise ValidationError("TRM tensor reader needs successful provenance")
    if (expected_ranks < 1 or len(files) != expected_ranks or
            len({path.name for path in files}) != expected_ranks):
        raise ValidationError("TRM saved rank set differs")
    patterns = [re.fullmatch(r"step_(\d+)_all_preds\.(\d+)", path.name)
                for path in files]
    if (any(match is None for match in patterns) or
            len({match.group(1) for match in patterns if match}) != 1 or
            {int(match.group(2)) for match in patterns if match} != set(range(expected_ranks))):
        raise ValidationError("TRM saved rank/step identity differs")
    identifiers = json.loads(identifiers_path.read_bytes())
    if not isinstance(identifiers, list) or len(set(identifiers)) != len(identifiers):
        raise ValidationError("TRM identifier mapping differs")
    by_input: dict[tuple[str, tuple[tuple[int, ...], ...]], list[int]] = {}
    result: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for task_id, task in visible_cases.items():
        for test_index, item in enumerate(task["test"]):
            key = (task_id, tuple(tuple(row) for row in grid(item["input"])))
            by_input.setdefault(key, []).append(test_index)
            result[(task_id, test_index)] = []
    invalid = 0
    for path in files:
        payload = torch.load(path, map_location="cpu", weights_only=True)
        required = {"inputs", "puzzle_identifiers", "q_halt_logits", "preds"}
        if not isinstance(payload, dict) or set(payload) != required:
            raise ValidationError("TRM raw prediction schema differs")
        size = len(payload["puzzle_identifiers"])
        if any(len(payload[key]) != size for key in required):
            raise ValidationError("TRM raw prediction lengths differ")
        for index in range(size):
            identifier = int(payload["puzzle_identifiers"][index])
            if identifier == 0:
                continue
            if identifier < 0 or identifier >= len(identifiers):
                raise ValidationError("TRM prediction identifier outside mapping")
            try:
                raw_input = _decode_trm_tensor(payload["inputs"][index])
                raw_pred = _decode_trm_tensor(payload["preds"][index])
                task_id, input_grid = _inverse_trm_augmentation(identifiers[identifier], raw_input)
                pred_task, output_grid = _inverse_trm_augmentation(identifiers[identifier], raw_pred)
                if pred_task != task_id:
                    raise ValidationError("TRM inverse task identity differs")
                matches = by_input.get((task_id, tuple(tuple(row) for row in input_grid)), [])
                if not matches:
                    invalid += 1
                    continue
                logit = float(payload["q_halt_logits"][index])
                if not math.isfinite(logit):
                    raise ValidationError("TRM halt logit is nonfinite")
                probability = 1 / (1 + math.exp(-logit)) if logit >= 0 else (
                    math.exp(logit) / (1 + math.exp(logit)))
                for test_index in matches:
                    result[(task_id, test_index)].append({"grid": output_grid,
                        "branch": "trm" if kind == "upstream" else "trm-fixture",
                        "source": f"{kind}:{path.name}:{index}",
                        "halt_probability": probability})
            except ValidationError:
                invalid += 1
    for key, candidates in result.items():
        votes: dict[tuple[tuple[int, ...], ...], dict[str, Any]] = {}
        for candidate in candidates:
            identity = tuple(tuple(row) for row in candidate["grid"])
            record = votes.setdefault(identity, {**candidate, "votes": 0,
                                                  "halt_sum": 0.0})
            record["votes"] += 1
            record["halt_sum"] += candidate["halt_probability"]
        ordered = list(votes.values())
        for candidate in ordered:
            candidate["halt_probability"] = candidate.pop("halt_sum") / candidate["votes"]
        ordered.sort(key=lambda item: (-item["votes"], -item["halt_probability"], item["grid"]))
        result[key] = ordered
    return {"candidates": result, "invalid_predictions": invalid,
            "source_kind": kind, "test_outputs": len(result)}


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
    if any(item.get("branch") == "trm-fixture" for item in trm):
        raise ValidationError("TRM parser fixture cannot enter model attempts")
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
    if any(item.get("branch") == "trm-fixture" for item in trm):
        raise ValidationError("TRM parser fixture cannot enter joint verification")
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
