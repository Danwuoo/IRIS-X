"""Provisional local, pinned training-parent diagnostics, not a benchmark scorer.

Only this module's panel contains held-out training-pair targets. Adaptation is
passed a separate demos-only value, never the panel, query or held-out target.
The CLI is validation-only. The execution hook requires the admitted bootstrap
to verify the actual base materials and inject their identity before loading one
model. It does not extend an original session clock or dispatch any provider.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import time

from tools.arc2_goal_sprint_20261017.data import (
    IDENTITY, SECOND_VIEW, answer_text, canonical, encode_example, loo_example, parse_grid, transform, valid_grid,
)

PANEL_FORMAT = "irisx/train-only-diagnostic-panel-v1"
PROFILE_FORMAT = "irisx/train-only-diagnostic-profile-v1"
ARMS = {"A0": ("A", 0, "final"), "A8final": ("A", 8, "final"), "C0": ("C", 0, "final"),
        "C8final": ("C", 8, "final"), "C32final": ("C", 32, "final"),
        "C32causal_outputs": ("C", 32, "causal_outputs")}
DEFAULT_ARMS = ["A0", "A8final", "C0", "C8final"]
SHA = re.compile(r"[a-f0-9]{64}\Z")
COUNTERS = ("forward_calls", "sampled_tokens", "optimizer_steps", "optimizer_attempts")


class DiagnosticDeadline(RuntimeError):
    pass


class FatalDiagnostic(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_keys(value, keys, description):
    require(type(value) is dict and set(value) == set(keys), description + " key inventory differs")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def valid_sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def strict_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def validate_panel(panel):
    """Pure structural/lineage gate; the externally pinned bytes remain required.

    It cannot prove an arbitrary caller's claimed split. The panel producer must
    independently reconstruct the recorded original split and seal these bytes.
    A digest alone is not a substitute for that producer's provenance audit.
    """
    strict_keys(panel, ("format", "provenance", "selection", "parents"), "panel")
    require(panel["format"] == PANEL_FORMAT, "unknown panel format")
    provenance = panel["provenance"]
    strict_keys(provenance, ("training_manifest_sha256", "train_ids_digest", "dev_ids_digest",
                "source_run_id", "source_seal_sha256", "public_benchmark_data_included",
                "original_test_fields_used"), "panel provenance")
    for key in ("training_manifest_sha256", "source_seal_sha256"):
        require(valid_sha(provenance[key]), "invalid provenance SHA")
    for key in ("train_ids_digest", "dev_ids_digest"):
        require(isinstance(provenance[key], str) and provenance[key].startswith("sha256:")
                and valid_sha(provenance[key][7:]), "invalid split digest")
    require(provenance["train_ids_digest"] != provenance["dev_ids_digest"], "split identities collide")
    require(isinstance(provenance["source_run_id"], str) and 1 <= len(provenance["source_run_id"]) <= 160,
            "source run identity required")
    require(provenance["public_benchmark_data_included"] is False
            and provenance["original_test_fields_used"] is False, "original training pairs only")
    selection = panel["selection"]
    strict_keys(selection, ("dev_count", "train_count", "heldout_pair_index", "dev_order",
                           "train_order", "seed"), "panel selection")
    require(type(selection["dev_count"]) is int and 1 <= selection["dev_count"] <= 200,
            "bounded nonempty development panel required")
    require(type(selection["train_count"]) is int and 0 <= selection["train_count"] <= 800,
            "bounded control panel required")
    require(type(selection["heldout_pair_index"]) is int and selection["heldout_pair_index"] == 0,
            "held-out original pair zero required")
    require(type(selection["seed"]) is int and 0 <= selection["seed"] < 2**31, "bounded panel seed required")
    require(selection["dev_order"] == "sha256:dev-panel:"
            and selection["train_order"] == "sha256:train-diagnostic:", "frozen selection order required")
    parents = panel["parents"]
    require(type(parents) is list and len(parents) == selection["dev_count"] + selection["train_count"],
            "complete panel denominator required")
    ids, by_partition = set(), {"dev": [], "train": []}
    for parent in parents:
        strict_keys(parent, ("parent_id", "partition", "sft_exposure", "solver", "held_out"), "parent")
        name, partition = parent["parent_id"], parent["partition"]
        require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", name) is not None
                and name not in ids, "unique safe parent ID required")
        require(partition in ("dev", "train"), "explicit parent partition required")
        require(type(parent["sft_exposure"]) is bool and parent["sft_exposure"] == (partition == "train"),
                "training controls may have been seen in SFT; development parents were excluded")
        ids.add(name)
        by_partition[partition].append(name)
        solver, held = parent["solver"], parent["held_out"]
        strict_keys(solver, ("demos", "query"), "solver projection")
        strict_keys(held, ("pair_index", "target"), "held-out target")
        require(type(held["pair_index"]) is int and held["pair_index"] == 0, "held-out index differs")
        require(valid_grid(solver["query"]) and valid_grid(held["target"]), "invalid held-out pair")
        demos = solver["demos"]
        require(type(demos) is list and 1 <= len(demos) <= 100, "remaining solver demos required")
        indices = []
        for demo in demos:
            strict_keys(demo, ("pair_index", "input", "output"), "solver demo")
            require(type(demo["pair_index"]) is int and demo["pair_index"] > 0, "held-out pair leaked into demos")
            require(valid_grid(demo["input"]) and valid_grid(demo["output"]), "invalid remaining demo")
            indices.append(demo["pair_index"])
        require(indices == list(range(1, len(demos) + 1)), "complete ordered remaining original pair indices required")
    expected_ids = []
    for partition in ("dev", "train"):
        require(len(by_partition[partition]) == selection[partition + "_count"], "partition count differs")
        prefix = selection[partition + "_order"][7:]
        ordered = sorted(by_partition[partition], key=lambda key: (hashlib.sha256((prefix + key).encode()).hexdigest(), key))
        require(by_partition[partition] == ordered, "deterministic parent selection order differs")
        expected_ids.extend(ordered)
    require([p["parent_id"] for p in parents] == expected_ids, "development parents must precede training controls")
    return panel


def load_panel(path, expected_sha256):
    require(valid_sha(expected_sha256), "independently pinned panel SHA required")
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 32 * 1024**2,
            "regular bounded panel file required")
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == expected_sha256, "panel byte SHA differs")
    panel = strict_json(body)
    require(body == canonical(panel) + b"\n", "canonical newline-terminated panel required")
    return validate_panel(panel)


def default_profile(*, session_epoch, session_deadline, seed=20261017):
    return {"format": PROFILE_FORMAT, "seed": seed, "context_tokens": 8192,
            "generation_tokens": 2048, "inference_views": "original_two", "arms": list(DEFAULT_ARMS), "ttt_lr": 5e-5,
            "session_epoch": session_epoch, "session_deadline": session_deadline,
            "closure_reserve_seconds": 60, "arm_seconds": 600}


def validate_profile(profile, panel):
    strict_keys(profile, ("format", "seed", "context_tokens", "generation_tokens", "inference_views", "arms", "ttt_lr",
                          "session_epoch", "session_deadline", "closure_reserve_seconds", "arm_seconds"), "profile")
    require(profile["format"] == PROFILE_FORMAT, "unknown profile format")
    require(type(profile["seed"]) is int and profile["seed"] == panel["selection"]["seed"], "paired seed differs")
    require(type(profile["context_tokens"]) is int and profile["context_tokens"] == 8192,
            "identity-view v1 context is frozen at 8192; ablations need a separate profile")
    require(type(profile["generation_tokens"]) is int and profile["generation_tokens"] == 2048,
            "v1 generation cap is frozen at 2048")
    require(profile["arms"] in (DEFAULT_ARMS, DEFAULT_ARMS + ["C32final"],
                DEFAULT_ARMS + ["C32final", "C32causal_outputs"]), "fixed paired arm inventory required")
    require(profile["inference_views"] in ("original_two", "identity_only"), "explicit fixed inference views required")
    require(type(profile["ttt_lr"]) in (int, float) and profile["ttt_lr"] == 5e-5, "frozen TTT learning rate required")
    for key in ("session_epoch", "session_deadline", "closure_reserve_seconds", "arm_seconds"):
        require(type(profile[key]) in (int, float) and math.isfinite(profile[key]) and profile[key] > 0,
                "finite positive original clock/budget required")
    require(0 < profile["session_deadline"] - profile["session_epoch"] <= 43200,
            "original session must be bounded to twelve hours")
    require(60 <= profile["closure_reserve_seconds"] < profile["session_deadline"] - profile["session_epoch"],
            "at least sixty seconds of owned cleanup reserve must fit original session")
    require(profile["arm_seconds"] <= 43200, "bounded per-arm execution required")
    if "C32causal_outputs" in profile["arms"]:
        require(all(len(p["solver"]["demos"]) >= 2 for p in panel["parents"] if p["partition"] == "dev"),
                "causal_outputs requires two remaining demos for every development parent; no subset fallback")
    return profile


def solver_demos(parent):
    """Drop provenance fields and detach every nested grid from the panel."""
    return copy.deepcopy([{key: p[key] for key in ("input", "output")} for p in parent["solver"]["demos"]])


def adaptation_example(tokenizer, demos, *, parent_id, seed, step, context, generation, loss_mode):
    """The only adaptation data argument is the remaining demos, not a parent."""
    rng = random.Random(hashlib.sha256(canonical([seed, parent_id, step, "train-diagnostic-ttt-v1"])).digest())
    examples, query, target = loo_example({"train": demos}, rng, augment=True)
    return encode_example(tokenizer, examples, query, target, context=context, generation=generation, loss_mode=loss_mode)


def counters(engine):
    return {key: int(getattr(engine, key)) for key in COUNTERS}


def delta(after, before):
    return {key: after[key] - before[key] for key in COUNTERS}


def deadline_check(deadline, now=time.time):
    if now() >= deadline:
        raise DiagnosticDeadline("original diagnostic deadline reached")


class TorchBackend:
    """Lazy ML boundary permits genuine standard-library-only contract tests."""
    def __init__(self):
        import torch
        from tools.arc2_goal_sprint_20261017 import model
        self.torch, self.model = torch, model
        self.recoverable = (DiagnosticDeadline, model.PhaseDeadline, torch.cuda.OutOfMemoryError,
                            FloatingPointError, ValueError)

    def state(self, engine):
        return self.model.adapter_state(engine.model)

    def state_digest(self, state):
        return self.model.state_digest(state)

    def restore(self, engine, state):
        self.model.restore_state(engine.model, state)
        engine.model.zero_grad(set_to_none=True)

    def verify(self, engine, expected):
        actual = self.state(engine)
        if (any(not bool(self.torch.isfinite(v).all()) for v in actual.values())
                or self.state_digest(actual) != self.state_digest(expected)):
            raise FatalDiagnostic("adapter reset or rollback verification failed")

    def optimizer(self, engine, lr):
        return self.model.make_optimizer(engine.model, lr)

    def load(self, engine, spec, base_identity):
        return self.model.load_adapter_resume(engine, spec, base_identity=base_identity)

    def cleanup(self):
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()

    def token_nll(self, engine, example):
        with self.torch.no_grad():
            ids = example["prompt_ids"] + example["completion_ids"]
            values = -engine.completion_logps(ids, len(example["prompt_ids"]))[len(example["prompt_ids"]):]
            return values.detach().cpu().tolist()


def reset_verified(engine, state, backend):
    try:
        backend.restore(engine, state)
        backend.verify(engine, state)
    except BaseException as error:
        raise FatalDiagnostic("adapter reset or rollback failed closed") from error


def adapt_demos(engine, demos, *, parent_id, profile, arm, deadline, backend, now=time.time):
    """Step transactions retain previous commits and never retry a failed step."""
    _, steps, loss_mode = ARMS[arm]
    before, attempts, accepted, reports = counters(engine), 0, 0, []
    stop_reason, optimizer = "step_limit", None
    if steps:
        optimizer = backend.optimizer(engine, profile["ttt_lr"])
    try:
        for step in range(steps):
            if now() >= deadline:
                stop_reason = "deadline_before_step"
                break
            attempts += 1
            snapshot, failure, fatal, report = None, None, None, None
            try:
                example = adaptation_example(engine.tokenizer, demos, parent_id=parent_id,
                    seed=profile["seed"], step=step, context=profile["context_tokens"],
                    generation=profile["generation_tokens"], loss_mode=loss_mode)
                snapshot = backend.state(engine)
                report = engine.sft_step(example, optimizer, deadline=deadline)
                engine.sync()
                deadline_check(deadline, now)
            except BaseException as error:
                failure = type(error).__name__
                if not isinstance(error, backend.recoverable):
                    fatal = failure  # no retained traceback/tensor ownership
            if failure is not None:
                if snapshot is not None:
                    reset_verified(engine, snapshot, backend)
                optimizer.zero_grad(set_to_none=True)
                backend.cleanup()
                reports.append({"step": step, "status": "rolled_back", "failure": failure,
                                "snapshot_restored": snapshot is not None, "retried": False})
                stop_reason = failure
                if fatal is not None:
                    raise FatalDiagnostic("unrecognized adaptation failure: " + fatal)
                break
            accepted += int(report["updated"])
            reports.append({"step": step, "status": "accepted", **report})
    finally:
        if optimizer is not None:
            optimizer.zero_grad(set_to_none=True)
        optimizer = None
    return {"requested_steps": steps, "attempts": attempts, "actual_ttt_steps": accepted,
            "complete": attempts == steps and stop_reason == "step_limit", "stop_reason": stop_reason,
            "physical": delta(counters(engine), before), "state_sha256": backend.state_digest(backend.state(engine)),
            "steps": reports, "rollback_scope": "failed_step_only", "optimizer_fresh": True}


def grid_metrics(prediction, target, query):
    valid = valid_grid(prediction)
    shape = valid and len(prediction) == len(target) and len(prediction[0]) == len(target[0])
    pixel = (sum(a == b for x, y in zip(prediction, target) for a, b in zip(x, y)) / sum(map(len, target))) if shape else 0.0
    return {"exact": bool(valid and prediction == target), "valid": valid, "shape": bool(shape),
            "pixel": pixel, "copies_query": bool(valid and prediction == query)}


def loss_categories(tokenizer, completion_ids, target):
    """Exact fast-token offsets or unavailable; never guessed token classes."""
    if not getattr(tokenizer, "is_fast", False):
        return None
    text = answer_text(target)
    try:
        encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    except (TypeError, ValueError, NotImplementedError):
        return None
    expected = list(encoded["input_ids"])
    eos = tokenizer.eos_token_id
    if eos is not None:
        expected.append(eos)
    if expected != completion_ids or len(encoded["offset_mapping"]) != len(encoded["input_ids"]):
        return None
    result = []
    for start, end in encoded["offset_mapping"]:
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
            return None
        part = text[start:end]
        if all(c.isdigit() or c.isspace() for c in part) and any(c.isdigit() for c in part):
            result.append("digit_content")
        elif part.isspace():
            result.append("whitespace")
        elif not any(c.isdigit() for c in part):
            result.append("structure")
        else:
            result.append("mixed_boundary")
    if eos is not None:
        result.append("structure")
    return result


def target_nll(engine, solver, target, profile, backend, deadline, now):
    deadline_check(deadline, now)
    demos = [{k: p[k] for k in ("input", "output")} for p in solver["demos"]]
    example = encode_example(engine.tokenizer, demos, solver["query"], target,
                             context=profile["context_tokens"], generation=profile["generation_tokens"])
    values = backend.token_nll(engine, example)
    engine.sync()
    deadline_check(deadline, now)
    require(len(values) == len(example["completion_ids"]) and values
            and all(math.isfinite(v) for v in values), "complete finite teacher-forced losses required")
    categories = loss_categories(engine.tokenizer, example["completion_ids"], target)
    grouped = None
    if categories is not None:
        grouped = {}
        for name in ("digit_content", "whitespace", "structure", "mixed_boundary"):
            selected = [v for v, category in zip(values, categories) if category == name]
            grouped[name] = {"tokens": len(selected), "mean_nll": sum(selected) / len(selected) if selected else None}
    return {"mean_nll": sum(values) / len(values), "tokens": len(values), "categories": grouped,
            "categories_status": "exact_token_offsets" if categories is not None else "unavailable_token_offsets",
            "demos_dropped": example["demos_dropped"]}


def arm_order(parent_id, arms, seed):
    # Counterbalance execution order independently of labels or previous results.
    result = list(arms)
    random.Random(hashlib.sha256(canonical([seed, parent_id, "arm-order-v1"])).digest()).shuffle(result)
    return result


def expected_arms(parent, profile):
    return profile["arms"] if parent["partition"] == "dev" else ["A0", "C0"]


def summarize(panel, profile, rows, status, physical):
    """Aggregates contain no grids, IDs, target-derived strata or winner choice."""
    lookup = {(r["parent_id"], r["arm"]): r for r in rows}
    require(len(lookup) == len(rows), "duplicate diagnostic result")
    result = {"format": "irisx/train-only-diagnostic-summary-v1", "status": status,
              "qualification": "training-derived diagnostic only; training controls may have been seen during SFT",
              "benchmark_score": None, "winner_selected": None, "selection_permitted": False,
              "inference_views": profile["inference_views"], "context_tokens": profile["context_tokens"],
              "generation_tokens": profile["generation_tokens"], "physical": physical, "partitions": {}}
    for partition in ("dev", "train"):
        parents = [p for p in panel["parents"] if p["partition"] == partition]
        names = profile["arms"] if partition == "dev" else ["A0", "C0"]
        complete_parents = [p for p in parents if all(lookup.get((p["parent_id"], name), {}).get("status") == "complete" for name in names)]
        group = {"expected_parents": len(parents), "fully_paired_complete_parents": len(complete_parents),
                 "incomplete_parents": len(parents) - len(complete_parents), "arms": {}}
        for name in names:
            observed = [lookup[(p["parent_id"], name)] for p in parents if (p["parent_id"], name) in lookup]
            complete = [r for r in observed if r["status"] == "complete"]
            paired = [lookup[(p["parent_id"], name)] for p in complete_parents]
            def metrics(entries):
                return {"denominator": len(entries), **{key: (sum(r["metrics"][key] for r in entries) / len(entries)
                                  if entries else None) for key in ("exact", "pass_at_1", "pass_at_2", "valid", "shape", "pixel", "copies_query")}}
            missing_ttt = sum("ttt" not in r for r in observed) if ARMS[name][1] else 0
            reported_steps = sum(r.get("ttt", {}).get("actual_ttt_steps", 0) for r in observed)
            group["arms"][name] = {"expected": len(parents), "attempted": len(observed), "complete": len(complete),
                                  "incomplete": len(parents) - len(complete), "descriptive_observed": metrics(complete),
                                  "paired_complete_only": metrics(paired),
                                  "requested_ttt_steps": ARMS[name][1],
                                  "actual_ttt_steps": None if missing_ttt else reported_steps,
                                  "reported_accepted_ttt_steps": reported_steps,
                                  "ttt_reports_missing": missing_ttt}
            details = group["arms"][name]
            for label, subset in (("descriptive_observed_nll", complete), ("paired_complete_only_nll", paired)):
                nll = {}
                for phase in ("before", "after"):
                    entries = [r["nll_" + phase] for r in subset if "nll_" + phase in r]
                    tokens = sum(r["tokens"] for r in entries)
                    nll[phase] = {"parents": len(entries), "tokens": tokens,
                        "parent_mean": sum(r["mean_nll"] for r in entries) / len(entries) if entries else None,
                        "token_weighted_mean": sum(r["mean_nll"] * r["tokens"] for r in entries) / tokens if tokens else None}
                    categories = {}
                    for category in ("digit_content", "whitespace", "structure", "mixed_boundary"):
                        values = [r["categories"][category] for r in entries if r.get("categories") is not None]
                        count = sum(v["tokens"] for v in values)
                        categories[category] = {"tokens": count, "parents_with_offsets": len(values),
                            "token_weighted_mean": sum(v["mean_nll"] * v["tokens"] for v in values if v["tokens"]) / count if count else None}
                    nll[phase]["categories"] = categories
                nll_pairs = [r for r in subset if "nll_after" in r and "nll_before" in r]
                nll["change"] = {"parents": len(nll_pairs), "parent_mean": (sum(
                    r["nll_after"]["mean_nll"] - r["nll_before"]["mean_nll"] for r in nll_pairs)
                    / len(nll_pairs)) if nll_pairs else None}
                details[label] = nll
            views = [v for r in observed for v in r.get("views", [])]
            details["generation"] = {"complete_views": len(views),
                "tokens": sum(v["completion_tokens"] for v in views),
                "demos_dropped": sum(v["demos_dropped"] for v in views),
                "stop_counts": {stop: sum(v["stop"] == stop for v in views) for stop in ("completed", "length")}}
        baseline = [grid_metrics(p["solver"]["query"], p["held_out"]["target"], p["solver"]["query"]) for p in parents]
        group["query_copy_baseline"] = {"denominator": len(baseline),
            **{k: sum(r[k] for r in baseline) / len(baseline) if baseline else None for k in ("exact", "shape", "pixel")}}
        group["last_demo_copy_baseline"] = {"denominator": len(parents), **{k: sum(grid_metrics(
            p["solver"]["demos"][-1]["output"], p["held_out"]["target"], p["solver"]["query"])[k]
            for p in parents) / len(parents) if parents else None for k in ("exact", "shape", "pixel")}}
        result["partitions"][partition] = group
    # Even a full panel is diagnostic evidence, never an automatic model choice.
    result["full_panel_complete"] = all(v["incomplete_parents"] == 0 for v in result["partitions"].values())
    return result


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def run_diagnostic(engine, panel, profile, checkpoints, *, verified_base_identity, output,
                   backend=None, now=time.time):
    """One loaded engine; exact adapter resumes, parent-paired arms, no dispatch.

    verified_base_identity is a trusted bootstrap injection, not a profile or
    adapter-manifest field. The production entry below additionally checks the
    fixed material contract. Fake engines/backends are supported solely for tests.
    Output must be a fresh private local directory. Results are checkpointed after
    each arm and before failure escapes; incomplete panels never choose a winner.
    """
    validate_panel(panel)
    validate_profile(profile, panel)
    require(type(checkpoints) is dict and set(checkpoints) == {"A", "C"}, "exact A/C checkpoints required")
    for spec in checkpoints.values():
        strict_keys(spec, ("root", "manifest_sha256"), "adapter spec")
        require(isinstance(spec["root"], str) and valid_sha(spec["manifest_sha256"]), "pinned adapter spec required")
    require(checkpoints["A"]["manifest_sha256"] != checkpoints["C"]["manifest_sha256"], "distinct A/C manifests required")
    require(type(verified_base_identity) is dict and verified_base_identity, "bootstrap-injected base identity required")
    backend = backend or TorchBackend()
    output = Path(output)
    require(not output.exists(), "fresh diagnostic output directory required; no resume or overwrite")
    output.mkdir(parents=True, mode=0o700)
    before = counters(engine)
    rows, receipts, states = [], {}, {}
    status, failure = "running", None
    initial = backend.state(engine)
    effective_deadline = profile["session_deadline"] - profile["closure_reserve_seconds"]
    def save():
        summary = summarize(panel, profile, rows, status, delta(counters(engine), before))
        atomic_json(output / "diagnostic.private.json", {"format": "irisx/train-only-diagnostic-results-v1",
            "status": status, "failure": failure, "panel_sha256": hashlib.sha256(canonical(panel) + b"\n").hexdigest(), "profile": profile,
            "checkpoint_receipts": receipts, "rows": rows, "summary": summary})
        atomic_json(output / "aggregate.safe.json", summary)
        return summary
    save()
    try:
        require(now() >= profile["session_epoch"], "original session has not started")
        deadline_check(effective_deadline, now)
        for name in ("A", "C"):
            receipts[name] = backend.load(engine, checkpoints[name], verified_base_identity)
            states[name] = backend.state(engine)
            require(backend.state_digest(states[name]) == receipts[name]["state_sha256"], "resumed state receipt differs")
            deadline_check(effective_deadline, now)
        reset_verified(engine, initial, backend)
        for parent in panel["parents"]:
            for arm in arm_order(parent["parent_id"], expected_arms(parent, profile), profile["seed"]):
                deadline_check(effective_deadline, now)
                checkpoint = ARMS[arm][0]
                started, physical_before = now(), counters(engine)
                arm_deadline = min(effective_deadline, started + profile["arm_seconds"])
                row = {"parent_id": parent["parent_id"], "partition": parent["partition"],
                       "sft_exposure": parent["sft_exposure"], "arm": arm, "checkpoint": checkpoint,
                       "status": "incomplete", "reset_verified": False}
                try:
                    reset_verified(engine, states[checkpoint], backend)
                    row["reset_verified"] = True
                    row["initial_state_sha256"] = backend.state_digest(states[checkpoint])
                    # Teacher forcing never steps an optimizer and is outside the demos-only adaptation API.
                    row["nll_before"] = target_nll(engine, parent["solver"], parent["held_out"]["target"],
                                                   profile, backend, arm_deadline, now)
                    row["ttt"] = adapt_demos(engine, solver_demos(parent), parent_id=parent["parent_id"],
                        profile=profile, arm=arm, deadline=started + (arm_deadline - started) / 3, backend=backend, now=now)
                    deadline_check(arm_deadline, now)
                    row["views"], ranked = [], []
                    view_specs = [IDENTITY, SECOND_VIEW] if profile["inference_views"] == "original_two" else [IDENTITY]
                    for view_index, view in enumerate(view_specs):
                        transformed_demos = [{k: transform(p[k], **view) for k in ("input", "output")}
                                             for p in solver_demos(parent)]
                        query = transform(parent["solver"]["query"], **view)
                        inference = encode_example(engine.tokenizer, transformed_demos, query,
                            context=profile["context_tokens"], generation=profile["generation_tokens"])
                        generated = engine.generate(inference["prompt_ids"], count=1,
                            max_new_tokens=profile["generation_tokens"], sample=False, deadline=arm_deadline)[0]
                        engine.sync()
                        deadline_check(arm_deadline, now)
                        parsed = parse_grid(generated["text"])
                        prediction = transform(parsed, **view, inverse=True) if parsed is not None else None
                        # First-seen valid deduplication only. No target enters ranking.
                        if prediction is not None and prediction not in ranked:
                            ranked.append(prediction)
                        row["views"].append({"view_index": view_index,
                            "completion_tokens": generated["completion_tokens"], "stop": generated["stop"],
                            "demos_dropped": inference["demos_dropped"], "prompt_tokens": len(inference["prompt_ids"]),
                            "prediction": prediction, "text_sha256": sha(generated["text"]),
                            "metrics": grid_metrics(prediction, parent["held_out"]["target"], parent["solver"]["query"])})
                    row["ranked_predictions"] = ranked[:2]
                    row["ranking"] = "fixed_view_order_valid_dedup_no_target_access"
                    row["metrics"] = grid_metrics(ranked[0] if ranked else None,
                        parent["held_out"]["target"], parent["solver"]["query"])
                    row["metrics"].update(pass_at_1=row["metrics"]["exact"],
                        pass_at_2=any(prediction == parent["held_out"]["target"] for prediction in ranked[:2]))
                    row["nll_after"] = target_nll(engine, parent["solver"], parent["held_out"]["target"],
                                                  profile, backend, arm_deadline, now)
                    row["status"] = "complete" if row["ttt"]["complete"] else "incomplete_adaptation"
                except backend.recoverable as error:
                    row["failure"] = type(error).__name__
                finally:
                    row["wall_seconds"] = now() - started
                    row["physical"] = delta(counters(engine), physical_before)
                    rows.append(row)
                    # A bad restore is fatal: no subsequent inference is allowed.
                    reset_verified(engine, states[checkpoint], backend)
                    save()
        status = "complete" if all(r["status"] == "complete" for r in rows) else "incomplete"
    except DiagnosticDeadline:
        status, failure = "incomplete_deadline", "DiagnosticDeadline"
    except BaseException as error:
        status, failure = "failed_closed", type(error).__name__
        raise
    finally:
        try:
            reset_verified(engine, initial, backend)
        except BaseException:
            status, failure = "failed_closed", "RestoreFailure"
            save()
            raise
        save()
    return save()


def execute_from_bootstrap(*, model_path, verified_base_identity, panel_path, panel_sha256,
                           profile, checkpoints, output, device="cuda"):
    """Call only AFTER production bootstrap verified the actual model material.

    This hook does not import bootstrap.run (which is a different workflow),
    consume a runtime config with unrelated input paths, or accept arbitrary base
    identity from a manifest. The caller remains responsible for real shard and
    tokenizer verification and injecting the original admitted session clock.
    """
    from tools.arc2_goal_sprint_20261017.materials import base_identity
    from tools.arc2_goal_sprint_20261017.model import Engine
    require(verified_base_identity == base_identity(), "production base material identity differs")
    panel = load_panel(panel_path, panel_sha256)
    validate_profile(profile, panel)
    deadline_check(profile["session_deadline"] - profile["closure_reserve_seconds"])
    engine = Engine.load(model_path, device=device)
    return run_diagnostic(engine, panel, profile, checkpoints, verified_base_identity=verified_base_identity, output=output)


def main():
    parser = argparse.ArgumentParser(description="Validate pinned training-only diagnostics; does not execute a model")
    parser.add_argument("--panel", required=True)
    parser.add_argument("--panel-sha256", required=True)
    args = parser.parse_args()
    panel = load_panel(args.panel, args.panel_sha256)
    print(json.dumps({"valid": True, "dev_parents": panel["selection"]["dev_count"],
                      "train_controls": panel["selection"]["train_count"], "model_loaded": False}, sort_keys=True))


if __name__ == "__main__":
    main()
