"""Offline adapter for the existing A/B/C producer's original sweep audit.

No model, runtime owner, evaluator, optimizer or network is imported. Original
JSON and external context remain untrusted declarations. A matching source/file
hash is byte consistency, never provenance authentication. Only complete native
64-slot batches can enter the unchanged AF3 bridge and streaming upstream loss.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, fields
import hashlib
import json
import math
import struct
from pathlib import Path

from tools.arc2_agent_factory3_bridge_20261014.bridge import BatchContext, digest, prepare_batch

FORMAT = "irisx/abc-audit-conformance-v1"
CONTEXT_FORMAT = "irisx/abc-audit-context-v1"
ROOT = Path(__file__).resolve().parents[2]
PIN_MANIFEST_SHA256 = "015e2549da2ab445b30273fa62e106d98510b26c2f130866eae393418531b8cd"
POLICY_SHA256 = "3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda"
STATUSES = frozenset(("updated", "zero-signal", "incomplete-audit", "not-reached",
                      "numeric-nonadmission-no-update", "update-failed", "failed-no-safe-continuation"))
ROW_STATUSES = frozenset(("eligible", "context-excluded", "infrastructure-excluded", "not-reached"))


class AuditError(ValueError):
    """Only fixed public codes are exposed, never private source/error content."""
    def __init__(self, code, *, status="REJECTED"):
        super().__init__(code)
        self.code, self.status = code, status


def _need(ok, code, *, status="REJECTED"):
    if not ok:
        raise AuditError(code, status=status)


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _original_float32(value):
    if not _finite(value):
        return False
    try:
        return struct.unpack("f", struct.pack("f", value))[0] == value
    except (OverflowError, struct.error):
        return False


def _integer(value, low=0, high=2**63-1):
    return type(value) is int and low <= value <= high


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _same(a, b):
    # Unlike Python equality, JSON's bool and integer declarations stay distinct.
    return digest(a) == digest(b)


def _object_keys(value, keys, code):
    _need(type(value) is dict and set(value) == set(keys), code)


def verify_sources():
    """Verify fixed inspected sources without importing the original runtime."""
    manifest = ROOT / "tools/arc2_abc_continuation_20261014/audit-source-pins.json"
    try:
        raw = manifest.read_bytes()
        _need(not manifest.is_symlink() and hashlib.sha256(raw).hexdigest() == PIN_MANIFEST_SHA256,
              "SOURCE_PINS_DRIFT")
        pins = json.loads(raw)
        for relative, expected in pins["files"].items():
            path = ROOT / relative
            _need(not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                  "FROZEN_SOURCE_DRIFT")
    except OSError:
        raise AuditError("FROZEN_SOURCE_UNAVAILABLE") from None
    return PIN_MANIFEST_SHA256


@dataclass(frozen=True)
class AuditContext:
    batch_context: BatchContext
    audit_sha256: str
    training_json: str
    policy_before_json: str
    declaration_digest: str

    def document(self):
        return {"format": CONTEXT_FORMAT, "audit_sha256": self.audit_sha256,
                "batch_context": json.loads(json.dumps(asdict(self.batch_context))),
                "training": json.loads(self.training_json),
                "policy_before": json.loads(self.policy_before_json)}


def context_from_document(doc, *, audit_sha256):
    """Bind closed external declarations to the independently read audit hash.

    The caller must use the existing safe reader to check original file bytes.
    This pure parser cannot authenticate the declaring party, training records,
    exclusions, model, reward or the source of that expected hash.
    """
    _object_keys(doc, ("format", "audit_sha256", "batch_context", "training", "policy_before"),
                 "CONTEXT_SCHEMA")
    _need(doc["format"] == CONTEXT_FORMAT and _sha(audit_sha256) and
          doc["audit_sha256"] == audit_sha256, "AUDIT_SOURCE_BINDING")
    batch = doc["batch_context"]
    _object_keys(batch, (f.name for f in fields(BatchContext)), "BATCH_CONTEXT_SCHEMA")
    raw = dict(batch)
    for key in ("train_parent_ids", "record_ids", "forbidden_parent_ids"):
        _need(type(raw[key]) is list, "BATCH_CONTEXT_SCHEMA")
        raw[key] = tuple(raw[key])
    try:
        declared = BatchContext(**raw)
        declared.validate()
    except (ValueError, TypeError):
        raise AuditError("BATCH_CONTEXT_INVALID") from None
    _need(declared.sampling_policy_sha256 == POLICY_SHA256, "SAMPLING_POLICY_SOURCE")
    _need(declared.policy_version.startswith("rl:"), "ORIGINAL_RL_POLICY_VERSION")
    training = doc["training"]
    _object_keys(training, ("source_sha256", "manifest_sha256", "plan_sha256", "exclusions_sha256",
                            "record_declarations"), "TRAINING_CONTEXT_SCHEMA")
    _need(all(_sha(training[k]) for k in ("source_sha256", "manifest_sha256", "plan_sha256",
                                        "exclusions_sha256")), "TRAINING_SOURCE_DECLARATIONS")
    records = training["record_declarations"]
    _need(type(records) is list and len(records) == 32, "TRAINING_RECORD_DECLARATIONS")
    for index, record in enumerate(records):
        _object_keys(record, ("parent_id", "record_id", "messages_sha256", "target_sha256", "exclusion"),
                     "TRAINING_RECORD_SCHEMA")
        _need(record["parent_id"] == declared.train_parent_ids[index] and
              record["record_id"] == declared.record_ids[index], "TRAINING_RECORD_ORDER")
        _need(_sha(record["messages_sha256"]) and _sha(record["target_sha256"]),
              "TRAINING_RECORD_SOURCE_DECLARATIONS")
        _need(record["exclusion"] is None or type(record["exclusion"]) is str and
              bool(record["exclusion"]), "TRAINING_RECORD_EXCLUSION")
    before = doc["policy_before"]
    _object_keys(before, ("policy_version", "adapter_sha256", "source_sha256", "generation_epoch"),
                 "POLICY_CONTEXT_SCHEMA")
    _need(before["policy_version"] == declared.policy_version and
          type(before["generation_epoch"]) is int and before["generation_epoch"] == declared.generation_epoch
          and _sha(before["adapter_sha256"]) and _sha(before["source_sha256"]), "POLICY_CONTEXT_IDENTITY")
    return AuditContext(declared, audit_sha256, json.dumps(training, sort_keys=True, allow_nan=False),
                        json.dumps(before, sort_keys=True, allow_nan=False), digest(doc))


def _summary(batch, parents):
    """Independently project the pinned producer/consumer summary, without truth."""
    _need(type(batch) is dict and type(batch.get("rows")) is list, "ORIGINAL_BATCH_MISSING",
          status="MISSING_ORIGINAL_ARTIFACTS")
    rows = batch["rows"]
    _need(len(rows) == 64 and all(type(r) is dict for r in rows), "FIXED_64_SLOTS")
    _need([(r.get("parent_id"), r.get("slot")) for r in rows] ==
          [(p, s) for p in parents for s in range(8)] and
          all(type(r.get("slot")) is int for r in rows), "FIXED_SLOT_ORDER")
    _need(type(batch.get("planned_attempts")) is int and batch["planned_attempts"] == 64,
          "FIXED_BATCH_DENOMINATOR")
    for row in rows:
        _need(type(row.get("eligible")) is bool and row.get("status") in ROW_STATUSES,
              "NATIVE_ROW_STATUS")
        _need((_integer(row.get("reward"), 0, 1) if row["eligible"] else row.get("reward") is None),
              "REWARD_UNKNOWN_OR_INVALID")
        _need(row["eligible"] is (row["status"] == "eligible"), "ROW_ELIGIBILITY_STATUS")
        if row["status"] == "not-reached":
            _need(row.get("trajectory") is None, "NOT_REACHED_HAS_TRAJECTORY")
        if row["eligible"]:
            _need(type(row.get("trajectory")) is dict, "ORIGINAL_TRAJECTORY_MISSING",
                  status="MISSING_ORIGINAL_ARTIFACTS")
    groups = []
    for index, parent in enumerate(parents):
        group = rows[index * 8:index * 8 + 8]
        eligible = [r for r in group if r["eligible"]]
        successes = sum(r["reward"] for r in eligible)
        groups.append({"parent_id": parent, "planned": 8, "eligible": len(eligible), "successes": successes,
                       "mixed": 0 < successes < len(eligible),
                       "all_zero": len(eligible) == 8 and successes == 0,
                       "all_one": len(eligible) == 8 and successes == 8,
                       "pass_at_8": int(successes > 0) if len(eligible) == 8 else None,
                       "fixture_full_group_success": int(successes > 0) if len(eligible) == 8 else None})
    counts = Counter(r["status"] for r in rows)
    eligible = sum(r["eligible"] for r in rows)
    context = sum(r["status"] == "context-excluded" or
                  bool((r.get("trajectory") or {}).get("context_excluded")) for r in rows)
    excluded = sum(not r["eligible"] and r["status"] != "not-reached" for r in rows) - context
    _need(excluded >= 0, "CONTEXT_EXCLUSION_INCONSISTENT")
    return {"planned_attempts": 64,
            "actual_dispatched_attempts": sum(bool(r.get("trajectory") and
                (r["trajectory"].get("dispatched") or r["trajectory"].get("steps"))) for r in rows),
            "reward_eligible_attempts": eligible, "infrastructure_exclusions": excluded,
            "context_exclusions": context, "not_reached": counts["not-reached"],
            "eligible_mean_reward": sum(r["reward"] for r in rows if r["eligible"]) / eligible if eligible else None,
            "eligible_mean_denominator": eligible,
            "complete": counts["not-reached"] == 0 and excluded == 0 and context == 0,
            "all_slots_reached": counts["not-reached"] == 0,
            "mixed_groups": sum(g["mixed"] for g in groups), "groups": groups,
            "pass_at_8_coverage": sum(g["pass_at_8"] is not None for g in groups),
            "status_counts": dict(counts), "fatal_native_state": batch.get("fatal_native_state", False)}


def _native_trajectories(batch, context):
    """Check saved native DFA/seed/prompt declarations; never recompute rewards."""
    records = json.loads(context.training_json)["record_declarations"]
    bc = context.batch_context
    plan_sha = json.loads(context.training_json)["plan_sha256"]
    seen_events = set()
    for index, row in enumerate(batch["rows"]):
        t = row["trajectory"]
        record = records[bc.batch_index * 8 + index // 8]
        _need(record["exclusion"] is None and t.get("messages_sha256") == record["messages_sha256"]
              and row.get("target_sha256") == record["target_sha256"] and type(row.get("fixture_only")) is bool,
              "TRAINING_RECORD_PROJECTION")
        if bc.evidence_kind == "declared-training-only":
            _need(row["fixture_only"] is False, "FIXTURE_CANNOT_CLAIM_TRAINING_EVIDENCE")
        seed = int(digest(["rl-fixed-batch-sampling-v1", POLICY_SHA256, plan_sha,
                           bc.batch_index, row["parent_id"], row["slot"]])[:15], 16)
        _need(type(t.get("seed")) is int and t["seed"] == seed, "ORIGINAL_SAMPLING_SEED")
        state, text, ended = (0, 1, 0), "", False
        for token, step in zip(t["generated_ids"], t["steps"]):
            _need(_original_float32(step["log_mu"]), "ORIGINAL_LOG_MU_FLOAT32")
            _need(not ended, "TOKENS_AFTER_EOS")
            width, nrows, column = state
            support = list(range(15, 25)) if column < (width or 30) else []
            if column > 0 and nrows < 30 and (not width or column == width):
                support.append(198)
            if column > 0 and (not width or column == width):
                support += [151643, 151645]
            _need(step.get("support") == sorted(support) and step.get("dfa_state") == list(state),
                  "ORIGINAL_NATIVE_DFA")
            if token in (151643, 151645):
                ended = True
            elif token == 198:
                state = (width or column, nrows + 1, 0)
                text += "\n"
            elif _integer(token, 15, 24):
                state = (width, nrows, column + 1)
                text += str(token - 15)
            else:
                raise AuditError("ORIGINAL_NATIVE_TOKEN")
        _need((ended and t.get("format_text") == text) if t["finish_reason"] == "eos" else not ended,
              "ORIGINAL_FINISH_REASON")
        _need(type(t.get("dispatched_forwards")) is int and t["dispatched_forwards"] == len(t["steps"]),
              "ORIGINAL_FORWARD_DENOMINATOR")
        _need(t.get("cache_discarded") is True, "ORIGINAL_CACHE_DISCARD_DECLARATION")
        event_ids = t.get("physical_event_ids")
        _need(type(event_ids) is list and bool(event_ids) and all(_integer(v) for v in event_ids)
              and len(set(event_ids)) == len(event_ids) and not seen_events.intersection(event_ids),
              "ORIGINAL_ACTOR_EVENT_DECLARATIONS")
        seen_events.update(event_ids)
        step_events = [s.get("actor_event_id") for s in t["steps"]]
        _need(all(_integer(v) for v in step_events), "ORIGINAL_ACTOR_EVENT_DECLARATIONS")
        if t.get("physical_accounting") == "one-durable-generation-with-dense-original-forward-indices":
            _need(len(event_ids) == 1 and set(step_events) == set(event_ids) and all(
                  type(s.get("actor_forward_index")) is int and s["actor_forward_index"] == i
                  for i, s in enumerate(t["steps"])), "ORIGINAL_FORWARD_INDEX_DECLARATIONS")
        else:
            _need(t.get("physical_accounting") == "per-forward-events" and step_events == event_ids,
                  "ORIGINAL_PER_FORWARD_EVENT_DECLARATIONS")


def _stats(gaps):
    if not gaps:
        return {"tokens": 0, "max_abs_gap": 0., "p95_abs_gap": 0.,
                "clipped_tokens": 0, "unclipped_fraction": 1.}
    values = sorted(abs(x) for x in gaps)
    pos = .95 * (len(values) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(values) - 1)
    clipped = sum(not (.8 < math.exp(max(-20., min(20., x))) < 1.28) for x in gaps)
    return {"tokens": len(gaps), "max_abs_gap": values[-1],
            "p95_abs_gap": values[lo] + (values[hi] - values[lo]) * (pos - lo),
            "clipped_tokens": clipped, "unclipped_fraction": 1 - clipped / len(gaps)}


def _check_stats(got, wanted):
    _need(type(got) is dict and set(got) == set(wanted), "REPLAY_STATISTICS_SCHEMA")
    for name, expected in wanted.items():
        _need(_finite(got[name]) and abs(got[name] - expected) <= 1e-6 and
              (type(got[name]) is int if name in ("tokens", "clipped_tokens") else True),
              "REPLAY_STATISTICS_MISMATCH")


def _update_header(update, batch, derived):
    _need(type(update) is dict, "ORIGINAL_UPDATE_MISSING", status="MISSING_ORIGINAL_ARTIFACTS")
    _need(type(update.get("optimizer_committed")) is bool and
          type(update.get("optimizer_dispatched")) is bool, "UPDATE_OPTIMIZER_DECLARATION")
    expected = {"planned_attempts": 64, "eligible_attempts": derived["reward_eligible_attempts"],
                "not_reached": derived["not_reached"],
                "infrastructure_excluded": derived["infrastructure_exclusions"] + derived["context_exclusions"],
                "actually_dispatched": derived["actual_dispatched_attempts"],
                "batch_index": batch["batch_index"], "session_planned_attempts": 256}
    _need(all(type(update.get(k)) is int and update[k] == v for k, v in expected.items()),
          "UPDATE_DENOMINATOR_MISMATCH")
    _need(update.get("parent_ids") == batch["parent_ids"] and
          update.get("update_batch_id") == update.get("batch_id") == batch["id"], "UPDATE_BATCH_IDENTITY")
    groups = [{"group": g["parent_id"], "total": 8, "eligible": g["eligible"],
               "infrastructure_excluded": 8 - g["eligible"], "successes": g["successes"],
               "mean_reward": g["successes"] / g["eligible"] if g["eligible"] else None,
               "mixed": g["mixed"], "all_zero": bool(g["eligible"] and g["successes"] == 0),
               "all_one": bool(g["eligible"] and g["successes"] == g["eligible"]),
               "pass_at_8": g["pass_at_8"]} for g in derived["groups"]]
    _need(_same(update.get("groups"), groups), "UPDATE_GROUP_SUMMARY")


def _replay_checks(update, batch, derived):
    replays = update.get("replays")
    _need(type(replays) is list, "ORIGINAL_REPLAYS_MISSING", status="MISSING_ORIGINAL_ARTIFACTS")
    _need(len(replays) <= 64, "REPLAY_EXTRA_OR_DUPLICATE")
    if len(replays) < 64:
        raise AuditError("COMPLETE_REPLAYS_MISSING", status="MISSING_ORIGINAL_ARTIFACTS")
    probability_passed = True
    for index, (row, replay) in enumerate(zip(batch["rows"], replays)):
        _need(type(replay) is dict, "REPLAY_SCHEMA")
        _need(_integer(replay.get("replay_event_id")), "REPLAY_EVENT_ID_DECLARATION")
        t = row["trajectory"]
        _need("log_pi" in replay and "log_mu" in replay, "ORIGINAL_REPLAY_ARRAYS_MISSING",
              status="MISSING_ORIGINAL_ARTIFACTS")
        _need(replay.get("parent_id") == row["parent_id"] and
              replay.get("trajectory_id") == t["trajectory_id"] and
              replay.get("update_batch_id") == batch["id"], "REPLAY_IDENTITY_ORDER")
        mu, pi = [s["log_mu"] for s in t["steps"]], replay.get("log_pi")
        _need(_same(replay.get("log_mu"), mu), "ORIGINAL_LOG_MU_MISMATCH")
        _need(type(pi) is list and len(pi) == len(mu) and
              all(_original_float32(v) and -3.4028234663852886e38 <= v <= 1e-6 for v in pi),
              "REPLAY_LOG_PI_COVERAGE")
        _need(all(len(s["support"]) != 1 or p == 0. for s, p in zip(t["steps"], pi)),
              "FORCED_REPLAY_PROBABILITY")
        group = derived["groups"][index // 8]
        advantage = row["reward"] - group["successes"] / 8
        mixed, length = derived["mixed_groups"], len(pi)
        weight = 1. / (mixed * 8 * length) if advantage else 0.
        _need(_finite(replay.get("group_advantage")) and replay["group_advantage"] == advantage and
              type(replay.get("eligible_group_size")) is int and replay["eligible_group_size"] == 8 and
              type(replay.get("mixed_group_count")) is int and replay["mixed_group_count"] == mixed and
              type(replay.get("original_generated_length")) is int and replay["original_generated_length"] == length,
              "REPLAY_GROUP_TOKEN_DENOMINATOR")
        _need(_finite(replay.get("gradient_weight")) and abs(replay["gradient_weight"] - weight) <= 1e-12,
              "REPLAY_GRADIENT_WEIGHT")
        _need(_finite(replay.get("detached_DDIS_loss")), "RECORDED_LOSS_MISSING",
              status="MISSING_ORIGINAL_ARTIFACTS")
        ratios = [math.exp(max(-20., min(20., p - m))) for p, m in zip(pi, mu)]
        scalar = -math.fsum(r * advantage * p for r, p in zip(ratios, pi) if .8 < r < 1.28) * weight
        _need(abs(replay["detached_DDIS_loss"] - scalar) <= max(1e-6, abs(scalar) * 1e-5),
              "RECORDED_DDIS_LOSS_MISMATCH")
        gaps = [p - m for p, m in zip(pi, mu)]
        nonforced = [g for g, s in zip(gaps, t["steps"]) if len(s["support"]) > 1]
        _check_stats(replay.get("all_tokens"), _stats(gaps))
        stats = _stats(nonforced)
        _check_stats(replay.get("nonforced_tokens"), stats)
        _need(type(replay.get("forced_tokens")) is int and replay["forced_tokens"] == len(gaps) - len(nonforced),
              "REPLAY_FORCED_DENOMINATOR")
        _need(all(replay.get(k) is True for k in ("original_token_replay", "prompt_and_tool_loss_masked",
                                                 "training_mode", "checkpointing_active")) and
              replay.get("cache_mode") == t["sampling"]["cache_mode"], "REPLAY_RECIPE_DECLARATIONS")
        probability_passed &= stats["max_abs_gap"] <= .20 and stats["p95_abs_gap"] <= .05
        probability_passed &= stats["unclipped_fraction"] == 1.
    return replays, probability_passed


def _numeric_gate_state(update, batch, replays, probability_passed):
    """Saved numerical/timing/memory declarations only, without owner proof."""
    gate = update.get("numerical_gate")
    expected = {"maximum_absolute_gap": .2, "minimum_unclipped_fraction": 1.,
                "maximum_replay_seconds": 30., "maximum_peak_bytes": 72 * 1024**3,
                "fixture_only": False, "maximum_p95_gap": .05,
                "maximum_reserved_bytes": 80 * 1024**3, "maximum_batch_replay_backward_seconds": 600.}
    _need(type(gate) is dict and type(gate.get("admitted")) is bool and
          _same(gate.get("gate"), expected) and _same(gate.get("per_trajectory"), replays) and
          gate.get("per_parent_ids") == batch["parent_ids"], "NUMERICAL_GATE_REPLAY_PROJECTION")
    failures = []
    for replay in replays:
        stats = replay["nonforced_tokens"]
        if stats["max_abs_gap"] > .2 or stats["p95_abs_gap"] > .05 or stats["unclipped_fraction"] < 1.:
            failures.append(replay["parent_id"] + ":ratio-gap")
        _need(_finite(replay.get("seconds")) and replay["seconds"] >= 0., "REPLAY_DURATION_DECLARATION")
        if replay["seconds"] > 30.:
            failures.append(replay["parent_id"] + ":runtime")
        for key in ("peak_memory_bytes", "peak_reserved_bytes"):
            _need(_integer(replay.get(key), 0, 2**50), "REPLAY_MEMORY_DECLARATION")
        if replay["peak_memory_bytes"] > 72 * 1024**3 or replay["peak_reserved_bytes"] > 80 * 1024**3:
            failures.append(replay["parent_id"] + ":memory")
        if replay["group_advantage"]:
            _need(_finite(replay.get("backward_seconds")) and 0 <= replay["backward_seconds"] <= replay["seconds"]
                  and _integer(replay.get("backward_event_id")),
                  "BACKWARD_DECLARATION")
        else:
            _need(replay.get("backward_event_id") is None and replay.get("backward_seconds") is None,
                  "ZERO_ADVANTAGE_BACKWARD_DECLARATION")
    _need(_finite(update.get("whole_replay_backward_seconds")) and update["whole_replay_backward_seconds"] >= 0 and
          _same(update.get("maximum_batch_replay_backward_seconds"), 600.), "CUMULATIVE_REPLAY_DECLARATION")
    if update["whole_replay_backward_seconds"] > 600.:
        failures.append("whole-replay-backward:runtime")
    start, replay_start, end, deadline = (update.get(k) for k in
        ("batch_started_monotonic", "batch_replay_started", "batch_finished_monotonic", "batch_deadline"))
    _need(all(_finite(v) for v in (start, replay_start, end, deadline)) and
          start <= replay_start <= end and start < deadline <= start + 600.001 and
          update["whole_replay_backward_seconds"] <= end - replay_start + .001,
          "CUMULATIVE_REPLAY_INTERVAL")
    if update["optimizer_committed"]:
        _need(end <= deadline + .001, "COMMITTED_BATCH_DEADLINE")
    _need(gate.get("failures") == failures and gate["admitted"] is (not failures),
          "NUMERICAL_ADMISSION_NOT_DERIVED")
    _need(probability_passed or bool(failures), "NUMERICAL_ADMISSION_NOT_DERIVED")
    return gate


def _base_result():
    return {"format": FORMAT, "status": "REJECTED", "conformance_complete": False,
            "scope": "offline-saved-original-audit-per-batch-only", "batch_index": None,
            "declared_original_status": None, "evidence_kind": None,
            "audit_source_sha256": None, "source_pins_sha256": PIN_MANIFEST_SHA256,
            "coverage": None, "groups": [], "replay": None, "issues": [],
            "provenance_authenticated": False, "model_replay_verified": False,
            "model_gradients_verified": False, "physical_execution_verified": False,
            "production_update_authorized": False, "ABC_efficacy_established": False,
            "unknowns": ["training_reward_provenance", "model_replay", "model_or_LoRA_gradients",
                         "physical_work_and_rollback", "optimizer_commit", "whole_ABC_efficacy"]}


def analyze_audit(audit, context, *, leaf_logp_derivative=False):
    """Return sanitized per-batch conformance conditional on saved declarations.

    Saved logp arrays can establish scalar consistency and optional derivatives
    of fresh CPU logp leaves only. They cannot reconstruct the original model
    graph, LoRA gradients, owner admission, physical costs or A/B/C efficacy.
    """
    result = _base_result()
    try:
        _need(type(leaf_logp_derivative) is bool, "DERIVATIVE_OPTION")
        verify_sources()
        _need(type(context) is AuditContext, "EXPLICIT_AUDIT_CONTEXT_REQUIRED")
        # Immutable context payloads and the original external-file binding.
        validated = context_from_document(context.document(), audit_sha256=context.audit_sha256)
        _need(validated.declaration_digest == context.declaration_digest, "MUTATED_CONTEXT")
        result.update(evidence_kind=context.batch_context.evidence_kind,
                      batch_index=context.batch_context.batch_index,
                      audit_source_sha256=context.audit_sha256)
        _need(type(audit) is dict and type(audit.get("batch")) is dict, "ORIGINAL_AUDIT_MISSING",
              status="MISSING_ORIGINAL_ARTIFACTS")
        _need(audit.get("status") in STATUSES, "ORIGINAL_AUDIT_STATUS")
        result["declared_original_status"] = audit["status"]
        bc, batch = context.batch_context, audit["batch"]
        parents = list(bc.train_parent_ids[bc.batch_index * 8:bc.batch_index * 8 + 8])
        _need(type(audit.get("batch_index")) is int and audit["batch_index"] == bc.batch_index and
              audit.get("parent_ids") == parents and batch.get("parent_ids") == parents and
              type(batch.get("batch_index")) is int and batch["batch_index"] == bc.batch_index and
              type(batch.get("sweep")) is int and batch["sweep"] == bc.batch_index, "AUDIT_BATCH_ORDER")
        derived = _summary(batch, parents)
        _need(_same(audit.get("summary"), derived), "RECORDED_SUMMARY_MISMATCH")
        _need(batch.get("closed") is True and batch.get("all_slots_reached") is derived["all_slots_reached"],
              "BATCH_CLOSURE_MISMATCH")
        result["coverage"] = {k: v for k, v in derived.items() if k not in ("groups", "fatal_native_state")}
        result["groups"] = [{"group_index": i, **{k: v for k, v in g.items() if k != "parent_id"}}
                            for i, g in enumerate(derived["groups"])]
        update, status = audit.get("update"), audit["status"]
        fatal = batch.get("fatal_native_state")
        if fatal is not None and fatal is not False:
            _need(status == "failed-no-safe-continuation", "FATAL_STATUS_INCONSISTENT")
            raise AuditError("ORIGINAL_FATAL_NATIVE_STATE", status="FATAL_NATIVE_STATE")
        if status == "not-reached":
            _need(derived["not_reached"] == 64 and update is None and audit.get("policy_before") is None and
                  audit.get("policy_after") is None and audit.get("admission") is None and
                  batch.get("policy_version") is None, "NOT_REACHED_INCONSISTENT")
            raise AuditError("ORIGINAL_BATCH_NOT_REACHED", status="NOT_REACHED")
        _need(_same(audit.get("policy_before"), json.loads(context.policy_before_json)), "POLICY_BEFORE_MISMATCH")
        _need(type(batch.get("attempted_batches")) is int and batch["attempted_batches"] == bc.batch_index + 1,
              "PHYSICAL_BATCH_ORDINAL_DECLARATION")
        if not derived["complete"]:
            _need(status in ("incomplete-audit", "failed-no-safe-continuation") and
                  not (type(update) is dict and update.get("optimizer_committed")), "INCOMPLETE_STATUS_INCONSISTENT")
            raise AuditError("ORIGINAL_BATCH_INCOMPLETE", status="INCOMPLETE_AUDIT")
        _need(batch.get("error") is None and batch.get("stop_reason") is None, "BATCH_STOP_OR_ERROR")
        for row in batch["rows"]:
            t = row["trajectory"]
            _need(all(k in t for k in ("prompt_ids", "generated_ids", "original_ids", "attention_mask", "origins", "steps")),
                  "ORIGINAL_TOKEN_ARTIFACTS_MISSING", status="MISSING_ORIGINAL_ARTIFACTS")
            if type(t["steps"]) is list:
                _need(all(type(step) is dict and all(k in step for k in
                          ("token", "position", "support", "dfa_state", "prefix_sha256", "log_mu")) for step in t["steps"]),
                      "ORIGINAL_STEP_ARTIFACTS_MISSING", status="MISSING_ORIGINAL_ARTIFACTS")
        try:
            prepared = prepare_batch(batch, bc)
        except (ValueError, TypeError, KeyError):
            raise AuditError("ORIGINAL_BATCH_BRIDGE_CONTRACT") from None
        _native_trajectories(batch, context)
        after = audit.get("policy_after")
        if status != "failed-no-safe-continuation":
            _need(type(after) is dict and _sha(after.get("source_sha256")) and
                  after["source_sha256"] == audit["policy_before"]["source_sha256"] and
                  _sha(after.get("adapter_sha256")) and _integer(after.get("generation_epoch")) and
                  after["generation_epoch"] > bc.generation_epoch, "POLICY_AFTER_DECLARATION")
        if not derived["mixed_groups"]:
            _need(status == "zero-signal" and update is None, "ZERO_SIGNAL_STATUS_INCONSISTENT")
            _need(after["policy_version"] == bc.policy_version and
                  after["adapter_sha256"] == audit["policy_before"]["adapter_sha256"], "ZERO_SIGNAL_POLICY_CHANGED")
            result.update(status="CONFORMANT_ZERO_SIGNAL", conformance_complete=True,
                          replay={"required": 0, "present": 0, "checked": 0, "loss_unscaled": None,
                                  "recorded_loss_matches": None, "leaf_logp_derivative": None})
            return result
        if status == "zero-signal":
            raise AuditError("MIXED_BATCH_RELABELLED_ZERO_SIGNAL")
        if status in ("update-failed", "failed-no-safe-continuation", "incomplete-audit"):
            if update is not None:
                _update_header(update, batch, derived)
                _need(update.get("status") == "update-failed" and update.get("optimizer_committed") is False,
                      "FAILED_UPDATE_STATUS_INCONSISTENT")
                prefix = update.get("replays")
                _need(type(prefix) is list and len(prefix) <= 64 and all(type(r) is dict and
                      r.get("trajectory_id") == row["trajectory"]["trajectory_id"] and
                      r.get("update_batch_id") == batch["id"] for r, row in zip(prefix, batch["rows"])),
                      "FAILED_REPLAY_PREFIX_ORDER")
                result["replay"] = {"required": 64, "present": len(prefix), "checked": 0,
                                    "loss_unscaled": None, "recorded_loss_matches": None,
                                    "leaf_logp_derivative": None}
            raise AuditError("ORIGINAL_UPDATE_FAILED", status="UPDATE_FAILED")
        _update_header(update, batch, derived)
        numeric_failed = status == "numeric-nonadmission-no-update"
        if numeric_failed:
            _need(update.get("status") == status and update["optimizer_committed"] is False and
                  update["optimizer_dispatched"] is False and after.get("policy_version") == bc.policy_version and
                  after["adapter_sha256"] == audit["policy_before"]["adapter_sha256"],
                  "NUMERIC_STATUS_INCONSISTENT")
        else:
            _need(status == "updated" and update.get("status") == "committed" and
                  update["optimizer_committed"] is True and update["optimizer_dispatched"] is True,
                  "UPDATE_STATUS_INCONSISTENT")
            _need(after.get("policy_version") == update.get("policy_version") and
                  after["policy_version"] != bc.policy_version and
                  after["adapter_sha256"] != audit["policy_before"]["adapter_sha256"], "UPDATED_POLICY_UNCHANGED")
            _need(_finite(update.get("gradient_norm")) and update["gradient_norm"] > 0 and
                  update.get("gradient_divisor") == "mixed-groups * eligible-group-size * original-generated-length" and
                  type(update.get("backward_calls")) is int and update["backward_calls"] == 8 * derived["mixed_groups"],
                  "ORIGINAL_UPDATE_GRADIENT_DECLARATIONS")
        replays, probability_passed = _replay_checks(update, batch, derived)
        gate = _numeric_gate_state(update, batch, replays, probability_passed)
        _need(gate["admitted"] is (not numeric_failed), "NUMERIC_STATUS_INCONSISTENT")
        result["replay"] = {"required": 64, "present": 64, "checked": 0,
                            "probability_values_passed": probability_passed,
                            "loss_unscaled": None, "recorded_loss_matches": None,
                            "leaf_logp_derivative": None}
        if numeric_failed or not probability_passed:
            if not numeric_failed:
                raise AuditError("COMMITTED_REPLAY_NUMERIC_FAILURE")
            raise AuditError("ORIGINAL_NUMERIC_NONADMISSION", status="NUMERIC_NONADMISSION")
        import torch
        from .streaming import StreamingLossSession
        deltas, derivative_l1, derivative_nonzero, derivative_tokens = [], 0., 0, 0
        with StreamingLossSession(prepared) as session:
            for row, replay in zip(batch["rows"], replays):
                pi = torch.tensor(replay["log_pi"], dtype=torch.float32, requires_grad=True)
                contribution = session.contribute(row["trajectory"]["trajectory_id"], pi)
                value = float(contribution.loss_unscaled.detach())
                recorded = replay["detached_DDIS_loss"]
                delta = abs(value - recorded)
                _need(delta <= max(1e-6, abs(recorded) * 1e-5), "RECORDED_DDIS_LOSS_MISMATCH")
                deltas.append(delta)
                if leaf_logp_derivative:
                    gradient, = torch.autograd.grad(contribution.loss_unscaled, pi)
                    _need(bool(torch.isfinite(gradient).all()), "LEAF_LOGP_DERIVATIVE_NONFINITE")
                    derivative_l1 += float(gradient.abs().sum())
                    derivative_nonzero += int((gradient != 0).sum())
                    derivative_tokens += gradient.numel()
                    del gradient
                del contribution, pi
            streamed = session.finalize()
        result["replay"].update(checked=64, loss_unscaled=streamed.loss_unscaled,
                                recorded_loss_matches=True, maximum_absolute_loss_delta=max(deltas))
        if leaf_logp_derivative:
            result["replay"]["leaf_logp_derivative"] = {
                "kind": "fresh-CPU-selected-logp-leaf-derivative-only", "tokens": derivative_tokens,
                "nonzero_tokens": derivative_nonzero, "absolute_sum": derivative_l1,
                "original_logits_gradient": False, "model_or_LoRA_gradient": False}
        result.update(status="CONFORMANT_SAVED_REPLAY", conformance_complete=True)
        return result
    except AuditError as exc:
        result.update(status=exc.status, conformance_complete=False, issues=[exc.code])
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RuntimeError, RecursionError):
        # No arbitrary exception strings, trajectory IDs, tokens or private errors.
        result.update(status="REJECTED", conformance_complete=False, issues=["AUDIT_CONTRACT_INVALID"])
    return result
