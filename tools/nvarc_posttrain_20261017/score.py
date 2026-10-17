"""Closed-generation scoring of exposure-qualified specialist predictions.

This wrapper does not change the pinned scorer. Initial weights have inherited
benchmark exposure, so even a high numeric result cannot establish the clean
PUBLIC120 goal. Evaluator material is opened only after provider/seal binding.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
import time

from tools.arc2_goal_sprint_20261017.launch import (
    EVALUATOR_MANIFEST_SHA256, SCORER_SHA256, SOLVER_MANIFEST_SHA256,
    regular, require, sha, verify_inventory, write_new,
)


def validate_pool_inventory(pools):
    require(pools.get("format") == "irisx/arc-offline-pools-v1"
        and isinstance(pools.get("run_id"), str) and bool(pools["run_id"]), "explicit prediction format/run required")
    records = pools.get("records")
    require(isinstance(records, list) and len(records) == 120, "complete 120-task prediction inventory required")
    task_ids, count = set(), 0
    for record in records:
        key, tests = record.get("task_id"), record.get("tests")
        require(isinstance(key, str) and bool(key) and key not in task_ids
            and isinstance(tests, list) and bool(tests), "unique task/query inventory required")
        task_ids.add(key)
        for index, test in enumerate(tests):
            require(type(test.get("test_index")) is int and test["test_index"] == index
                and re.fullmatch(r"sha256:[a-f0-9]{64}", test.get("input_digest", "")), "exact indexed input digest required")
            grids = test.get("ranked_grids")
            require(isinstance(grids, list) and len(grids) <= 2, "at most two guesses required")
            for grid in grids:
                require(isinstance(grid, list) and 1 <= len(grid) <= 30
                    and all(isinstance(line, list) and 1 <= len(line) <= 30 for line in grid)
                    and len({len(line) for line in grid}) == 1
                    and all(type(v) is int and 0 <= v <= 9 for line in grid for v in line), "strict output grid required")
            count += 1
    require(count == 167, "complete 167-query prediction inventory required")


def closure_structure(proof):
    require(proof.get("format") == "irisx/owned-process-closure-v1"
        and proof.get("scope") == "dedicated-subreaper-tree" and proof.get("closed") is True
        and proof.get("ownership_complete") is True and proof.get("remaining") == []
        and proof.get("errors") == [] and type(proof.get("returncode")) is int
        and type(proof.get("worker_returncode")) is int, "complete source-side process closure required")
    identities = proof.get("owned_identities")
    require(isinstance(identities, list) and len(identities) >= 2 and proof.get("root_identity") in identities,
            "complete source-side process identity inventory required")
    for identity in identities:
        require(set(identity) == {"pid", "birth", "session", "state"}
            and all(type(identity[k]) is int and identity[k] >= 0 for k in ("pid", "birth", "session"))
            and type(identity["state"]) is str, "source-side process identity malformed")
    require(len({(i["pid"], i["birth"]) for i in identities}) == len(identities), "duplicate process identities")


def admission_paths(admission, source_identity):
    require(admission.get("source_identity") == source_identity
        and set(admission.get("models", {})) == {"2b", "4b"}, "bound public evidence admission required")
    paths = {}
    for variant, row in admission["models"].items():
        require(type(row.get("admitted")) is bool, "explicit specialist admission required")
        if not row["admitted"]:
            require(row.get("path") is None, "rejected specialist cannot have an admitted path")
            continue
        require(isinstance(row.get("path"), str), "admitted specialist path required")
        relative = Path(row["path"])
        require(not relative.is_absolute() and ".." not in relative.parts and len(relative.parts) == 3
            and relative.parts[0].startswith("public-") and relative.parts[1] == variant + "-S"
            and relative.parts[2] == "pools.json", "safe admitted specialist path required")
        paths[variant] = relative.as_posix()
    return paths


def seal(output, destination, closure, source_identity):
    from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof
    verify_closed_proof(closure)
    closure_structure(closure)
    output, destination = Path(output), Path(destination)
    summary = json.loads(regular(output / "run-summary.json").read_bytes())
    pools = json.loads(regular(output / "pools.json").read_bytes())
    validate_pool_inventory(pools)
    require(summary["run_id"] == pools["run_id"] and summary["source_identity"] == source_identity,
            "source/run identity differs before sealing")
    require(summary.get("inherited_exposure_qualified") is True
            and summary.get("clean_generalization_claimed") is False,
            "inherited checkpoint exposure must be explicit")
    destination.mkdir(parents=True, exist_ok=False)
    files = {}
    # Private per-view candidate and adaptation evidence travels with the seal,
    # never with the public source package. No answer material exists here.
    paths = [output / name for name in ("pools.json", "run-summary.json", "selected-checkpoints.json", "isolation.json",
                                       "public-evidence-admission.json")]
    admission = json.loads(regular(output / "public-evidence-admission.json").read_bytes())
    for name in admission_paths(admission, source_identity).values():
        relative = Path(name)
        directory = output / relative.parent
        for name in ("pools.json", "full-candidate-pools.json", "task-adaptations.json", "result.json", "failure.json"):
            if (directory / name).exists():
                paths.append(directory / name)
    for path in paths:
        path = regular(path)
        require(path.stat().st_size <= 64 * 1024**2, "bounded sealed evidence file required")
        relative = path.relative_to(output).as_posix()
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with path.open("rb") as source, target.open("xb") as stream:
            shutil.copyfileobj(source, stream)
            stream.flush()
            os.fsync(stream.fileno())
        require(sha(path) == sha(target), "evidence changed while sealing")
        files[relative] = {"bytes": target.stat().st_size, "sha256": sha(target)}
    result = {"format": "irisx/nvarc-exposure-qualified-seal-v1", "run_id": pools["run_id"],
        "source_manifest_sha256": source_identity, "files": files, "pools_sha256": files["pools.json"]["sha256"],
        "closure": closure, "sealed_epoch": time.time(), "generation_may_resume": False,
        "tasks": 120, "queries": 167, "scorer_sha256": SCORER_SHA256,
        "solver_manifest_sha256": SOLVER_MANIFEST_SHA256, "evaluator_manifest_sha256": EVALUATOR_MANIFEST_SHA256,
        "inherited_exposure_qualified": True, "clean_generalization_claimed": False,
        "isolation": json.loads((destination / "isolation.json").read_bytes())}
    write_new(destination / "prediction-seal.json", result)
    return result


def verify_terminal(sealed, evidence, *, notebook_id, version):
    """Bind independent exact provider readback; never claim a provider signature."""
    require(type(notebook_id) is int and notebook_id > 0 and type(version) is int and version > 0,
            "independently reconciled exact notebook ID/version required")
    require(set(evidence) == {"terminal_path", "terminal_sha256", "seal_sha256", "source_manifest_sha256"},
            "exact external terminal and seal pins required")
    sealed = Path(sealed)
    require(sha(regular(evidence["terminal_path"])) == evidence["terminal_sha256"], "terminal evidence changed")
    require(sha(regular(sealed / "prediction-seal.json")) == evidence["seal_sha256"], "downloaded seal changed")
    receipt = json.loads((sealed / "prediction-seal.json").read_bytes())
    terminal = json.loads(Path(evidence["terminal_path"]).read_bytes())
    require(terminal.get("format") == "irisx/nvarc-provider-terminal-v1"
        and type(terminal.get("notebook_id")) is int and type(terminal.get("version")) is int
        and terminal.get("notebook_id") == notebook_id and terminal.get("version") == version
        and terminal.get("status") in {"COMPLETE", "ERROR", "CANCELLED", "CANCEL_ACKNOWLEDGED"}
        and terminal.get("source_verified") is True and terminal.get("outputs_verified") is True,
        "exact terminal/source/output verification required")
    require(terminal.get("source_manifest_sha256") == receipt["source_manifest_sha256"] == evidence["source_manifest_sha256"]
        and terminal.get("prediction_seal_sha256") == evidence["seal_sha256"]
        and terminal.get("pools_sha256") == receipt["pools_sha256"], "provider/source/prediction identity differs")
    stamp = terminal.get("verified_terminal_epoch")
    require(type(stamp) in (int, float) and math.isfinite(stamp)
        and receipt["sealed_epoch"] <= stamp <= time.time(), "terminal must follow sealing")
    closure_structure(receipt["closure"])
    require(receipt["format"] == "irisx/nvarc-exposure-qualified-seal-v1"
        and receipt["generation_may_resume"] is False and receipt["tasks"] == 120 and receipt["queries"] == 167
        and receipt["inherited_exposure_qualified"] is True and receipt["clean_generalization_claimed"] is False,
        "exposure-qualified closed full-denominator seal required")
    isolation = receipt["isolation"]
    require(isolation.get("mechanism") == "dataset-separated-provider-execution"
        and isolation.get("evaluator_dataset_absent") is True and isolation.get("os_sandbox_claimed") is False,
        "honest evaluator-absent dataset boundary required")
    for name, row in receipt["files"].items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "safe sealed file path required")
        path = regular(sealed / name)
        require(path.stat().st_size == row["bytes"] and sha(path) == row["sha256"], "sealed evidence changed")
    require(receipt["files"]["pools.json"]["sha256"] == receipt["pools_sha256"], "pool seal binding differs")
    require({"pools.json", "run-summary.json", "selected-checkpoints.json", "isolation.json", "public-evidence-admission.json"} <= set(receipt["files"]),
            "complete sealed evidence inventory required")
    pools = json.loads((sealed / "pools.json").read_bytes())
    validate_pool_inventory(pools)
    run = json.loads((sealed / "run-summary.json").read_bytes())
    admission = json.loads((sealed / "public-evidence-admission.json").read_bytes())
    admitted_paths = set(admission_paths(admission, receipt["source_manifest_sha256"]).values())
    sealed_paths = {name for name in receipt["files"] if len(Path(name).parts) == 3
        and Path(name).parts[0].startswith("public-") and Path(name).name == "pools.json"}
    require(admitted_paths == sealed_paths, "sealed specialist inventory differs from admission")
    require(pools["run_id"] == receipt["run_id"] == run["run_id"]
        and run["source_identity"] == receipt["source_manifest_sha256"]
        and run.get("inherited_exposure_qualified") is True and run.get("clean_generalization_claimed") is False,
        "sealed run/model exposure identity differs")
    return receipt, terminal


def score(sealed, evaluator_root, public_path, source_root, evidence, *, notebook_id, version):
    receipt, terminal = verify_terminal(sealed, evidence, notebook_id=notebook_id, version=version)
    require(receipt["solver_manifest_sha256"] == SOLVER_MANIFEST_SHA256
        and receipt["evaluator_manifest_sha256"] == EVALUATOR_MANIFEST_SHA256
        and receipt["scorer_sha256"] == SCORER_SHA256
        and sha(regular(Path(source_root) / "tools/arc_offline_evaluation.py")) == SCORER_SHA256,
        "unchanged original scorer and data pins required")
    verify_inventory(Path(public_path).parent, SOLVER_MANIFEST_SHA256)
    public = json.loads(regular(public_path).read_bytes())
    verify_ensemble(sealed, receipt, public)
    # First evaluator access is deliberately after all external closure checks.
    evaluator_root = Path(evaluator_root)
    verify_inventory(evaluator_root, EVALUATOR_MANIFEST_SHA256)
    from tools import arc_offline_evaluation as scorer
    require(sha(regular(scorer.__file__)) == SCORER_SHA256, "imported scorer differs")
    challenges, solutions, reference = scorer.load_pinned_reference(evaluator_root / "upstream", evaluator_root / "provenance.json")
    require(challenges == public, "solver challenge projection differs")
    sealed = Path(sealed)
    pools = json.loads((sealed / "pools.json").read_bytes())
    report = scorer.evaluate(challenges, solutions, pools)
    del solutions
    metrics = report["development_metrics"]
    require(metrics["tasks"] == 120 and metrics["tests"] == 167, "full denominator required")
    pass2 = metrics["metrics"]["pass_at_2"]
    run = json.loads((sealed / "run-summary.json").read_bytes())
    admission = json.loads((sealed / "public-evidence-admission.json").read_bytes())
    summary = {"format": "irisx/nvarc-exposure-qualified-summary-v1", "run_id": pools["run_id"],
        "measurement": "inherited-exposure-qualified PUBLIC development", "tasks": 120, "queries": 167,
        "pass_at_2": pass2, "numeric_threshold_met": pass2["numerator"] >= 156,
        "clean_goal_met": False, "clean_generalization_claimed": False, "inherited_exposure_qualified": True,
        "official_score": None, "hidden_score": None,
        "operational_success": terminal["status"] == "COMPLETE" and receipt["closure"]["worker_returncode"] == 0
            and run["solver_status"] == "complete" and set(admission["models"]) == {"2b", "4b"}
            and all(row["admitted"] is True for row in admission["models"].values()),
        "prediction_seal_sha256": evidence["seal_sha256"], "source_manifest_sha256": receipt["source_manifest_sha256"],
        "provider_terminal_sha256": evidence["terminal_sha256"], "reference": reference,
        "scorer_sha256": SCORER_SHA256, "generation_may_resume": False}
    require(sha(sealed / "pools.json") == receipt["pools_sha256"], "predictions changed during scoring")
    write_new(sealed / "evaluation-detail.json", report)
    write_new(sealed / "public-summary.json", summary)
    return summary


def verify_ensemble(sealed, receipt, public):
    """Reconstruct the fixed two-specialist rule using solver-only material."""
    from .controller import ensemble_pools
    from tools.arc2_goal_sprint_20261017.data import digest
    sealed = Path(sealed)
    combined = json.loads((sealed / "pools.json").read_bytes())
    require(combined.get("challenges_digest") == digest(public), "sealed solver challenge digest differs")
    by_variant = {}
    for name in receipt["files"]:
        parts = Path(name).parts
        if len(parts) == 3 and parts[0].startswith("public-") and parts[2] == "pools.json":
            variant = parts[1].split("-")[0]
            require(variant in {"2b", "4b"} and variant not in by_variant, "one sealed prediction pool per specialist required")
            by_variant[variant] = json.loads((sealed / name).read_bytes())
    empty = {"challenges_digest": digest(public), "records": [{"task_id": key, "tests": [
        {"test_index": i, "input_digest": digest(query["input"]), "ranked_grids": [], "status": "not_attempted"}
        for i, query in enumerate(task["test"])]} for key, task in sorted(public.items())]}
    for variant in ("2b", "4b"):
        by_variant.setdefault(variant, empty)
    reconstructed = ensemble_pools(public, by_variant, run_id=combined["run_id"])
    original_rows = {(r["task_id"], t["test_index"]): t for r in combined["records"] for t in r["tests"]}
    for row in reconstructed["records"]:
        for test in row["tests"]:
            original = original_rows.get((row["task_id"], test["test_index"]))
            require(original is not None and original["input_digest"] == test["input_digest"]
                and original["ranked_grids"] == test["ranked_grids"], "sealed ensemble differs from fixed specialist rule")
