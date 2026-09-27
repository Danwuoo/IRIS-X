"""Truth-free source-profile TTT, search and rank over a verified checkpoint."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import time

from .arc_nvarc_candidates import FixtureCandidateBackend, QwenCandidateBackend, solve_task, candidate_score_limit
from .arc_nvarc_data import visible_task
from .arc_nvarc_representation import verify_model_material, validate_profile_material
from .arc_nvarc_training import TaskLocalAdapter, load_compact_model
from .canonical import canonical_bytes
from .errors import ValidationError


def run_source_profile(config_path: Path, visible_path: Path, output: Path, *,
                       profile: str, fixture_path: Path | None = None,
                       checkpoint: Path | None = None,
                       material_digest: str | None = None,
                       bundle: Path | None = None, bundle_digest: str | None = None,
                       model_ready=None, call_observer=None) -> dict:
    from .arc_nvarc_upstream import source_bundle, qwen_cell

    if (bundle is None) != (bundle_digest is None):
        raise ValidationError("source bundle path and digest must be supplied together")
    with source_bundle(bundle, bundle_digest) if bundle is not None else nullcontext():
        # Exercise every runtime source entrance before any model load or update.
        for name in ("arc_loader.py", "arc_decoder.py", "arc_solver.py"):
            qwen_cell(name)
        return _run_source_profile(config_path, visible_path, output, profile=profile,
                                   fixture_path=fixture_path, checkpoint=checkpoint,
                                   material_digest=material_digest, bundle_digest=bundle_digest,
                                   model_ready=model_ready, call_observer=call_observer)


def _run_source_profile(config_path: Path, visible_path: Path, output: Path, *,
                        profile: str, fixture_path: Path | None,
                        checkpoint: Path | None, material_digest: str | None,
                        bundle_digest: str | None, model_ready=None, call_observer=None) -> dict:
    config = json.loads(config_path.read_bytes())
    if config.get("format") != "irisx/nvarc-source-stage-v1" or profile not in config.get("profiles", {}):
        raise ValidationError("unknown source integration stage/profile")
    candidate, adaptation = config["candidate"], config["adaptation"]
    max_score = candidate_score_limit(candidate)
    if (candidate.get("augmentation") != "source-qwen" or
            candidate.get("representation") != "source-qwen" or
            candidate.get("ranking") != "source-kgmon" or
            adaptation.get("source_qwen") is not True):
        raise ValidationError("source stage algorithm bindings differ")
    if output.exists():
        raise ValidationError("source stage output must be new")
    raw = json.loads(visible_path.read_bytes())
    if not isinstance(raw, dict) or not raw:
        raise ValidationError("source stage needs nonempty visible tasks")
    tasks = [visible_task(task_id, value) for task_id, value in sorted(raw.items())]
    material = None
    if profile == "fixture":
        if fixture_path is None or checkpoint is not None or material_digest is not None:
            raise ValidationError("fixture profile requires only synthetic predictions")
        backend = FixtureCandidateBackend(json.loads(fixture_path.read_bytes()))
    else:
        if fixture_path is not None or checkpoint is None or material_digest is None:
            raise ValidationError("model profile requires checkpoint and material digest")
        pinned = config["profiles"][profile].get("material_digest")
        material = verify_model_material(checkpoint, material_digest)
        validate_profile_material(profile, pinned, material_digest, material)
        model = load_compact_model(checkpoint, dtype="float32" if profile == "tiny" else "bfloat16")
        if profile == "4b":
            import torch
            if not torch.cuda.is_available():
                raise ValidationError("4B source stage requires CUDA")
            model.to(torch.device("cuda", 0))
        adapter = TaskLocalAdapter(model, adaptation)
        backend = QwenCandidateBackend(model, task_adapter=adapter,
                                       dfs_max_score=max_score,
                                       dfs_max_expansions=int(candidate["dfs_max_expansions"]))
    if model_ready is not None:
        model_ready()
    results = []
    measurements = []
    for task in tasks:
        if profile != "fixture":
            import torch
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        results.extend(solve_task(task, backend, candidate, call_observer=call_observer))
        if profile != "fixture":
            import torch
            try:
                import psutil
                memory = psutil.Process().memory_info()
                rss_mib = getattr(memory, "peak_wset", memory.rss) / 1048576
            except ImportError:
                rss_mib = None
            measurements.append({"task_id": task["task_id"],
                                 "wall_seconds": time.monotonic() - started,
                                 "ttt_seconds": backend.ttt_seconds,
                                 "generation_seconds": backend.generate_seconds,
                                 "ranking_seconds": backend.rank_seconds,
                                 "explicit_forward_calls": backend.forward_calls,
                                 "total_model_forward_calls": backend.forward_calls +
                                 (adapter.last_observation or {}).get("steps", 0),
                                 "verification_calls": backend.verification_calls,
                                 "ttt": adapter.last_observation,
                                 "process_peak_rss_mib": rss_mib,
                                 "peak_cuda_allocated_mib": (torch.cuda.max_memory_allocated() / 1048576
                                                             if torch.cuda.is_available() else None)})
    report = {"format": "irisx/nvarc-source-stage-result-v1", "profile": profile,
              "source_profile": config["source_profile"],
              "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
              "visible_sha256": hashlib.sha256(visible_path.read_bytes()).hexdigest(),
              "material_digest": material_digest,
              "source_bundle_digest": bundle_digest,
              "training_identity_digest": (material.get("training_identity_digest")
                                           if material is not None else None),
              "measurements": measurements,
              "task_count": len(tasks), "test_count": sum(len(task["test"]) for task in tasks),
              "results": results, "contains_evaluator_truth": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(report, newline=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--visible", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=("fixture", "tiny", "4b"), required=True)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--material-digest")
    parser.add_argument("--source-bundle", type=Path)
    parser.add_argument("--source-bundle-digest")
    args = parser.parse_args()
    run_source_profile(args.config, args.visible, args.output, profile=args.profile,
                       fixture_path=args.fixture, checkpoint=args.checkpoint,
                       material_digest=args.material_digest,
                       bundle=args.source_bundle, bundle_digest=args.source_bundle_digest)


if __name__ == "__main__":
    main()
