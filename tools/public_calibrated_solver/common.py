"""Gold-free source/plan admission and immutable, bounded evidence adapters."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import time

from tools.public_demo_calibration import core
from tools.public_sft141_diagnostic import contract, model_worker as base
from tools.public_sft141_submission.files import load_json, read_bytes, parent_directory

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_PLAN_SHA256 = "bafeabeae62625171147645d166b524e3f008fdbf5e44164c0ed8c41498e9c1c"
PUBLIC_PLAN_CANONICAL_SHA256 = "cc795e7475cb689714b34fb5f10802c23f51a2534dcf50121774a56750c31069"
PUBLIC_GOLD_FILE_SHA256 = "cab56c98868fdbf119646bb3ae2591f1588e9fc39800c7c1a08b368ec44e7471"
STRATEGIES = ("vote", "rescored", "demo_weighted")
PACKAGES = ("public_sft141_diagnostic", "public_demo_calibration",
            "public_sft141_submission", "public_calibrated_solver")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def new_artifacts(path):
    # Reject existing symlink ancestors before any integration output write.
    # The frozen base writer provides exclusive atomic publication; this is
    # not a hostile-concurrent-filesystem sandbox or a two-file transaction.
    with parent_directory(path):
        return base.Artifacts(path)


def frozen(path, expected):
    value, raw = load_json(path)
    if sha(raw) != expected:
        raise ValueError("frozen input bytes changed: " + str(path))
    return value


def sources():
    return {str(p.relative_to(ROOT)): sha(read_bytes(p))
            for package in PACKAGES for p in sorted((ROOT / "tools" / package).iterdir())
            if p.is_file() and p.suffix in (".py", ".json")}


def verify_base():
    pins, _ = load_json(Path(__file__).with_name("base_source_pins.json"))
    expected = {str(p.relative_to(ROOT)) for p in (ROOT / "tools/public_sft141_diagnostic").iterdir()
                if p.is_file() and p.suffix in (".py", ".json")}
    if set(pins) != expected or any(sha(read_bytes(ROOT / p)) != digest for p, digest in pins.items()):
        raise ValueError("frozen independent public base source bytes differ")


def verify_sources(expected):
    verify_base()
    if sources() != expected:
        raise ValueError("solver/dependency source identity changed")


def admit(plan, raw_hash, kind):
    core.validate_gold_free(plan)
    if sum(len(p["test"]) for p in plan["parents"]) != 15:
        raise ValueError("this experiment is fixed to twelve parents and fifteen true test queries")
    if kind not in ("public_model", "synthetic_cpu"):
        raise ValueError("explicit execution kind required")
    if kind == "public_model" and (raw_hash != PUBLIC_PLAN_SHA256 or
                                   core.digest(plan) != PUBLIC_PLAN_CANONICAL_SHA256):
        raise ValueError("real execution requires exact fixed public plan bytes and canonical identity")


def inherited(seconds, started, clock=time.monotonic):
    d = base.Deadline(seconds, clock)
    if not math.isfinite(started) or not 0 <= started <= clock():
        raise ValueError("original monotonic start is invalid")
    d.start, d.end = started, started + seconds
    d.work_end = d.end - d.reserve
    return d


def challenge_from_plan(plan):
    return {p["task_id"]: {"train": p["train"], "test": [{"input": q["input"]} for q in p["test"]]}
            for p in plan["parents"]}


def evidence_manifest(root):
    root = Path(root)
    found = {}
    for path in sorted(root.rglob("*.json")):
        if path.is_symlink():
            raise ValueError("linked evidence is not admitted")
        found[str(path.relative_to(root))] = sha(read_bytes(path))
    return found


def verify_evidence(root, inventory):
    if evidence_manifest(root) != inventory:
        raise ValueError("sealed worker evidence is missing, added, or changed")


def load_if(path):
    return load_json(path)[0] if Path(path).exists() else None


def assemble_pool(plan, calibration, worker):
    """Map unchanged atomic base view receipts to the public calibration API."""
    worker = Path(worker)
    specs = {(s["query_id"], s["view"]): s for s in core.generation_specs(plan)}
    rows = []
    for path in sorted((worker / "generation/receipts").glob("view-*.json")):
        row, raw = load_json(path)
        trace = load_if(worker / "receipts" / ("bound-" + path.name))
        if trace is None or trace["raw_sha256"] != sha(raw):
            raise ValueError("raw generation receipt lacks immutable calibration event binding")
        if trace["calibration_sha256"] != core.digest(calibration):
            raise ValueError("view receipt bound to different calibration")
        key = row["query_id"], row["view"]
        status = "deadline" if row.get("termination") == "deadline" or trace["late"] else row["status"]
        rows.append(core.pool_row(specs[key], row.get("token_ids") or [], row["seconds"], trace["event"], status))
    return core.pool_bundle(plan, calibration, rows)


def recover_base(plan, worker):
    """Retain partial raw evidence when the worker dies before its aggregate.

    Recovery is always partial, even if the final raw operation had completed.
    Candidate and score inventories use the original deterministic base order.
    """
    worker = Path(worker)
    queries = []
    for parent in plan["parents"]:
        for q in parent["test"]:
            qi = len(queries)
            views, candidates = [], {}
            for view in range(8):
                row = load_if(worker / f"generation/receipts/view-{qi:04d}-{view}.json")
                row = row or {"view": view, "status": "missing"}
                views.append(row)
                if row.get("status") == "complete" and row.get("valid"):
                    grid = contract.inverse(contract.parse_answer(row["token_ids"]), view)
                    key = base._key(grid)
                    item = candidates.setdefault(key, {"canonical_key": key, "grid": grid, "count": 0,
                        "view_nll": [], "mean_nll": None, "combined_score": None})
                    item["count"] += 1
            pool = sorted(candidates.values(), key=lambda c: c["canonical_key"])
            complete = len(views) == 8 and all(r["status"] == "complete" for r in views)
            for ci, candidate in enumerate(pool):
                for view in range(8):
                    nll = load_if(worker / f"generation/receipts/nll-{qi:04d}-{ci}-{view}.json")
                    candidate["view_nll"].append(nll or {"view": view, "status": "missing"})
                ready = all(r["status"] == "complete" for r in candidate["view_nll"])
                complete = complete and ready
                if ready:
                    mean = sum(r["nll"] for r in candidate["view_nll"]) / 8
                    candidate.update(mean_nll=mean, combined_score=candidate["count"] - mean)
            queries.append({"task_id": parent["task_id"], "test_index": q["test_index"],
                "query_id": q["query_id"], "views": views, "candidates": pool,
                "vote": [c["grid"] for c in sorted(pool, key=lambda c: (-c["count"], c["canonical_key"]))[:2]],
                "rescored": [c["grid"] for c in sorted(pool, key=lambda c: (-c["combined_score"], c["canonical_key"]))[:2]] if complete else [],
                "vote_complete": all(r["status"] == "complete" for r in views),
                "rescoring_complete": complete, "status": "recovered-partial"})
    return {"schema": base.SCHEMA, "status": "recovered-partial", "queries": queries,
            "full_panel_complete": False, "capability_claim": False}


def reconcile_base(plan, worker):
    raw = recover_base(plan, worker)
    declared = load_if(Path(worker) / "generation/result.json")
    if declared is None:
        return raw, False
    rows = declared.get("queries", [])
    if len(rows) != len(raw["queries"]):
        raise ValueError("base aggregate query inventory differs from raw receipts")
    for a, b in zip(rows, raw["queries"]):
        for field in ("query_id", "views", "candidates", "vote"):
            if a[field] != b[field]:
                # In interrupted base execution its aggregate can omit a mean
                # even though all eight raw scores exist. Never promote it.
                if field == "candidates":
                    ca = [{k: v for k, v in c.items() if k not in ("mean_nll", "combined_score")} for c in a[field]]
                    cb = [{k: v for k, v in c.items() if k not in ("mean_nll", "combined_score")} for c in b[field]]
                    if ca == cb:
                        continue
                raise ValueError("base aggregate differs from atomic " + field)
    return declared, True
