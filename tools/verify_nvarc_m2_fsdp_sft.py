"""Verify a local FSDP SFT checkpoint, export and truth-free source result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from irisx.arc_nvarc_fsdp_sft import (verify_checkpoint,
                                      restore_checkpoint_transport)
from irisx.arc_nvarc_representation import verify_model_material
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_ephemeral_checkpoint_evidence(run_root: Path, identity: str,
                                         pause: dict | None, final: dict,
                                         export_chain: dict, world: int) -> dict:
    """Bind scratch checkpoint manifests without claiming retained DCP bytes."""
    if pause is None or pause.get("checkpoint", {}).get("step") != 1:
        raise ValidationError("scratch SFT first interruption is missing")
    first = json.loads((run_root / "first-checkpoint-manifest.json").read_bytes())
    last = json.loads((run_root / "final-checkpoint-manifest.json").read_bytes())
    evicted = json.loads((run_root / "resume-evicted.json").read_bytes())
    if (digest_value(first) != pause["checkpoint"]["manifest_digest"] or
            digest_value(last) != final["checkpoint"]["manifest_digest"] or
            evicted.get("format") != "irisx/nvarc-m2-fsdp-resume-evicted-v1" or
            evicted.get("identity_digest") != identity or
            evicted.get("checkpoint_manifest_digest") !=
            pause["checkpoint"]["manifest_digest"] or
            evicted.get("step") != 1 or
            evicted.get("contains_evaluator_truth") is not False or
            export_chain.get("checkpoint_manifest_digest") !=
            final["checkpoint"]["manifest_digest"]):
        raise ValidationError("scratch SFT checkpoint digest chain differs")
    for manifest, step, tokens in ((first, 1, pause["tokens_seen"]),
                                   (last, final["step"], final["tokens_seen"])):
        state = manifest.get("state", {})
        if (manifest.get("format") != "irisx/nvarc-m2-fsdp-checkpoint-v1" or
                state.get("identity_digest") != identity or
                state.get("world_size") != world or
                state.get("step") != step or state.get("tokens_seen") != tokens or
                state.get("contains_evaluator_truth") is not False or
                not manifest.get("files")):
            raise ValidationError("scratch SFT checkpoint manifest state differs")
    if any((run_root / reference["path"]).exists()
           for reference in (pause["checkpoint"], final["checkpoint"])):
        raise ValidationError("scratch SFT claims unretained DCP members")
    required = {"resume_dcp_load_complete", "resume_set_state_complete",
                "resume_load_complete", "resumed_checkpoint_evicted",
                "checkpoint_save_complete"}
    for rank in range(world):
        trace = [json.loads(line) for line in (run_root / f"rank-{rank}-trace.jsonl")
                 .read_text(encoding="utf-8").splitlines()]
        phases = {item["phase"] for item in trace if item.get("rank") == rank}
        if not required.issubset(phases):
            raise ValidationError("scratch SFT resume trace is incomplete")
    return last


def verify(plan_path: Path, compact: Path, sequences_path: Path, run_root: Path,
           source_result_path: Path, source_config_path: Path, visible_path: Path,
           *, reconstructed_checkpoint: Path | None = None) -> dict:
    plan = json.loads(plan_path.read_bytes())
    sequences = [json.loads(line) for line in sequences_path.read_text(encoding="utf-8").splitlines()]
    if (_sha(sequences_path) != plan["sequences_sha256"] or
            digest_value(sequences) != plan["sequences_digest"] or
            len(sequences) != plan["sequence_count"]):
        raise ValidationError("SFT verifier sequence binding differs")
    verify_model_material(compact, plan["compact_material_digest"],
                          allowed_extra_files={"dataset-metadata.json"}
                          if (compact / "dataset-metadata.json").exists() else None)
    identity = digest_value({"plan": plan,
                             "model_material_digest": plan["compact_material_digest"],
                             "sequences_digest": plan["sequences_digest"]})
    pause = json.loads((run_root / "pause-result.json").read_bytes()) if (
        run_root / "pause-result.json").is_file() else None
    final = json.loads((run_root / "final-result.json").read_bytes())
    export_chain = json.loads((run_root / "export-chain.json").read_bytes())
    if (final.get("format") != "irisx/nvarc-m2-fsdp-sft-result-v1" or
            final.get("identity_digest") != identity or
            final.get("step") != plan["maximum_optimizer_steps"] or
            final.get("stop_reason") != "maximum_steps" or
            final.get("contains_evaluator_truth") is not False or
            export_chain.get("format") != "irisx/nvarc-m2-fsdp-export-chain-v1" or
            export_chain.get("identity_digest") != identity or
            export_chain.get("checkpoint_manifest_digest") !=
            final["checkpoint"]["manifest_digest"] or
            export_chain.get("plan_sha256") != _sha(plan_path) or
            export_chain.get("sequences_sha256") != _sha(sequences_path) or
            export_chain.get("contains_evaluator_truth") is not False):
        raise ValidationError("SFT verifier training/export chain differs")
    if pause is not None and (pause.get("step") != 1 or
                              pause.get("identity_digest") != identity or
                              pause.get("stop_reason") != "controlled_interruption"):
        raise ValidationError("SFT verifier interruption chain differs")
    transport = run_root / "checkpoint-transport/manifest.json"
    ephemeral = plan.get("checkpoint_storage") == "ephemeral-scratch"
    if ephemeral:
        if transport.exists() or reconstructed_checkpoint is not None:
            raise ValidationError("scratch SFT cannot claim checkpoint transport")
        checkpoint_manifest = verify_ephemeral_checkpoint_evidence(
            run_root, identity, pause, final, export_chain, plan["world_size"])
        transport_digest = None
    elif transport.exists():
        if reconstructed_checkpoint is None:
            raise ValidationError("split checkpoint needs an explicit new reconstruction directory")
        checkpoint_manifest = restore_checkpoint_transport(run_root, reconstructed_checkpoint)
        transport_manifest = json.loads(transport.read_bytes())
        if (transport_manifest["checkpoint_manifest_digest"] !=
                export_chain["checkpoint_manifest_digest"] or
                transport_manifest["identity_digest"] != identity):
            raise ValidationError("SFT verifier checkpoint transport differs")
        transport_digest = digest_value(transport_manifest)
    else:
        checkpoint_manifest = verify_checkpoint(
            run_root / final["checkpoint"]["path"], identity, plan["world_size"])
        transport_digest = None
    if (digest_value(checkpoint_manifest) != final["checkpoint"]["manifest_digest"] or
            checkpoint_manifest["state"]["step"] != final["step"] or
            checkpoint_manifest["state"]["tokens_seen"] != final["tokens_seen"]):
        raise ValidationError("SFT verifier checkpoint state differs")
    export_material = verify_model_material(run_root / "export",
                                            export_chain["export_material_digest"])
    if (export_material.get("kind") != "sft-inference-export" or
            export_material.get("training_identity_digest") != identity or
            export_material.get("base_material_digest") != plan["compact_material_digest"]):
        raise ValidationError("SFT verifier export lineage differs")
    source = json.loads(source_result_path.read_bytes())
    if (source.get("format") != "irisx/nvarc-source-stage-result-v1" or
            source.get("material_digest") != export_chain["export_material_digest"] or
            source.get("training_identity_digest") != identity or
            source.get("config_sha256") != _sha(source_config_path) or
            source.get("visible_sha256") != _sha(visible_path) or
            source.get("contains_evaluator_truth") is not False or
            source.get("task_count") != 1 or source.get("test_count") < 1 or
            len(source.get("results", [])) != source["test_count"]):
        raise ValidationError("SFT verifier source-stage lineage differs")
    if (plan.get("source_config_sha256") is not None and
            plan["source_config_sha256"] != source["config_sha256"]) or (
            plan.get("source_visible_sha256") is not None and
            plan["source_visible_sha256"] != source["visible_sha256"]):
        raise ValidationError("SFT plan source config/visible binding differs")
    calls = max(item["generation_calls_so_far"] for item in source["results"])
    if plan.get("maximum_source_generation_calls") is not None and calls > plan[
            "maximum_source_generation_calls"]:
        raise ValidationError("SFT source generation ceiling exceeded")
    run_chain_path = run_root / "run-chain.json"
    if ephemeral and not run_chain_path.is_file():
        raise ValidationError("scratch SFT terminal run chain is missing")
    if run_chain_path.exists():
        run_chain = json.loads(run_chain_path.read_bytes())
        if (run_chain.get("training_identity_digest") != identity or
                run_chain.get("export_material_digest") != export_chain["export_material_digest"] or
                run_chain.get("source_result_sha256") != _sha(source_result_path) or
                run_chain.get("checkpoint_transport_manifest_digest") != transport_digest or
                run_chain.get("optimizer_checkpoint_retained", True) != (not ephemeral) or
                run_chain.get("contains_evaluator_truth") is not False):
            raise ValidationError("SFT terminal run chain differs")
    return {"format": "irisx/nvarc-m2-fsdp-sft-verification-v1",
            "training_identity_digest": identity,
            "optimizer_steps": final["step"], "training_tokens": final["tokens_seen"],
            "model_forwards": final["forwards"],
            "checkpoint_manifest_digest": final["checkpoint"]["manifest_digest"],
            "checkpoint_transport_manifest_digest": transport_digest,
            "optimizer_checkpoint_retained": not ephemeral,
            "export_material_digest": export_chain["export_material_digest"],
            "source_result_sha256": _sha(source_result_path),
            "source_generation_calls": calls,
            "source_returned_sequences": sum(item["returned_sequences"]
                                             for item in source["results"]),
            "source_verification_calls": max(item["verification_calls_so_far"]
                                             for item in source["results"]),
            "contains_evaluator_truth": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--compact", type=Path, required=True)
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--source-result", type=Path, required=True)
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--visible", type=Path, required=True)
    parser.add_argument("--reconstructed-checkpoint", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = verify(args.plan, args.compact, args.sequences, args.run,
                    args.source_result, args.source_config, args.visible,
                    reconstructed_checkpoint=args.reconstructed_checkpoint)
    if args.report is not None:
        args.report.write_bytes(canonical_bytes(report, newline=True))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
