"""Bounded, truth-free summaries of existing terminal consumer reports.

This module performs no I/O, imports no producer/consumer/provider, and confers
no authentication, admission, promotion, or execution authority. Its arithmetic
is conditional on the supplied JSON. Unknown values remain unknown.
"""
from __future__ import annotations

import math


FORMAT = "irisx/arc2-continuation-analysis-v1"
CONSUMER_FORMAT = "irisx/owned-rl-batched-offline-validation-v1"
ARMS = ("A", "B", "C")
AXES = (
    "evidence_valid", "diagnostic_evidence_valid", "authenticated_collection_verified",
    "external_owner_envelope_verified", "production_admitted", "operational_complete",
    "operational_success", "comparison_complete", "compute_matched", "comparison_eligible",
    "public_benchmark_evidence_eligible", "public_goal_met", "scientific_goal_met", "goal_met",
)
STATUSES = frozenset((
    "REVIEWED_PRODUCTION_CONTENT_COMPLETE", "STOPPED_INCOMPLETE", "EVIDENCE_REJECTED",
    "UNSEALED_SESSION_DIAGNOSTICS", "INCOMPLETE_DIAGNOSTIC_EVIDENCE",
    "OWNED_CONTENT_COMPLETE_UNADMITTED", "FIXTURE_OWNED_CONTENT_COMPLETE",
    "FIXTURE_CONTENT_COMPLETE_STRUCTURE_BRIDGE_UNAVAILABLE", "FIXTURE_MECHANICS_COMPLETE",
    "INNER_CONTENT_VALIDATED", "TERMINAL_EVIDENCE_VERIFIED", "GPU_UNAVAILABLE_STOP",
))
PUBLIC_STATUSES = frozenset(("SEALED_SCORER_ROWS_REPLAYED", "PREDICTIONS_SEALED_NOT_SCORED"))
SCORING_STATUSES = frozenset((
    "REVIEWED_PRODUCTION_CONTENT_COMPLETE", "OWNED_CONTENT_COMPLETE_UNADMITTED",
    "FIXTURE_OWNED_CONTENT_COMPLETE", "FIXTURE_CONTENT_COMPLETE_STRUCTURE_BRIDGE_UNAVAILABLE",
    "FIXTURE_MECHANICS_COMPLETE", "INNER_CONTENT_VALIDATED",
))
COLLECTOR_DIAGNOSTIC_STATUSES = frozenset((
    "UNSEALED_SESSION_DIAGNOSTICS", "INCOMPLETE_DIAGNOSTIC_EVIDENCE", "GPU_UNAVAILABLE_STOP",
))
PROVIDER_TERMINAL_STATUSES = frozenset(("COMPLETE", "ERROR", "CANCEL_ACKNOWLEDGED"))


def _integer(value, low=0, high=256):
    return type(value) is int and low <= value <= high


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _boolean(value):
    return value if type(value) is bool else None


def _object(value):
    return value if type(value) is dict else {}


def _section(report, key, issues):
    value = report.get(key)
    if value is not None and type(value) is not dict:
        issues.add(key.upper() + "_SECTION_INVALID", invalid=True)
    return _object(value)


class _Issues:
    def __init__(self):
        self.codes = set()
        self.invalid = False

    def add(self, code, *, invalid=False):
        self.codes.add(code)
        self.invalid |= invalid


def _scores(value, scope, denominator, issues):
    """Return only counts and internal hitsets; never expose identities."""
    code = scope.upper()
    if value is None:
        issues.add(code + "_SCORES_UNAVAILABLE")
        return None, None
    if type(value) is not dict or set(value) != set(ARMS):
        issues.add(code + "_ARM_INVENTORY_INVALID", invalid=True)
        return None, None
    counts, hitsets = {}, {}
    for arm in ARMS:
        row = value[arm]
        if type(row) is not dict or not _integer(row.get("exact"), 0, denominator) or \
                type(row.get("denominator")) is not int or row["denominator"] != denominator:
            issues.add(code + "_SCORE_COUNTS_INVALID", invalid=True)
            return None, None
        ids = row.get("exact_case_ids")
        if type(ids) is not list or len(ids) != row["exact"] or len(ids) > denominator or \
                any(type(x) is not str or not x.startswith(scope + ":") or
                    len(x) <= len(scope) + 1 or len(x) > 512 for x in ids):
            issues.add(code + "_HITSET_INVALID", invalid=True)
            return None, None
        if len(set(ids)) != len(ids):
            issues.add(code + "_HITSET_DUPLICATE", invalid=True)
            return None, None
        if row.get("prediction_file_bound") is not True:
            issues.add(code + "_PREDICTION_BINDING_NOT_DECLARED", invalid=True)
            return None, None
        counts[arm] = {"exact": row["exact"], "denominator": denominator,
                       "value": row["exact"] / denominator}
        hitsets[arm] = set(ids)
    if len(set().union(*hitsets.values())) > denominator:
        issues.add(code + "_HITSET_UNION_EXCEEDS_DENOMINATOR", invalid=True)
        return None, None
    return counts, hitsets


def _paired(hitsets):
    if hitsets is None:
        return None
    result = {}
    for label, arm, reference in (("B_minus_A", "B", "A"), ("C_minus_A", "C", "A"),
                                  ("B_minus_C", "B", "C")):
        gain = len(hitsets[arm] - hitsets[reference])
        loss = len(hitsets[reference] - hitsets[arm])
        result[label] = {"gained": gain, "lost": loss, "net": gain - loss,
                         "both_correct": len(hitsets[arm] & hitsets[reference]),
                         "conditional_on_same_case_universe": True}
    return result


def _comparison(report, issues, *, scoring_allowed=True):
    evaluation = _section(report, "evaluation", issues)
    dev, dev_hits = _scores(evaluation.get("dev_scores"), "dev", 16, issues)
    held, hits = _scores(evaluation.get("holdout_scores"), "holdout", 32, issues)
    selected = evaluation.get("selected_arm")
    if selected not in ARMS:
        if selected is not None:
            issues.add("DEV_SELECTED_ARM_INVALID", invalid=True)
        selected = None
    expected = max(ARMS, key=lambda arm: dev[arm]["exact"]) if dev is not None else None
    selection_consistent = None
    if expected is not None:
        selection_consistent = selected == expected
        if not selection_consistent:
            issues.add("DEV_SELECTION_OR_TIE_RULE_INCONSISTENT", invalid=True)
    paired = _paired(hits)
    declared_pairs = evaluation.get("paired_vs_A")
    if hits is not None:
        if type(declared_pairs) is not dict or set(declared_pairs) != {"B", "C"}:
            issues.add("PAIRED_VS_A_DECLARATION_INVALID", invalid=True)
            paired = None
        else:
            for arm in ("B", "C"):
                row = declared_pairs[arm]
                for field, wanted in (("gained_case_ids", hits[arm] - hits["A"]),
                                      ("lost_case_ids", hits["A"] - hits[arm])):
                    ids = row.get(field) if type(row) is dict else None
                    if type(ids) is not list or len(ids) > 32 or \
                            any(type(x) is not str or len(x) > 512 for x in ids) or \
                            len(ids) != len(set(ids)) or set(ids) != wanted:
                        issues.add("PAIRED_VS_A_COUNTS_INCONSISTENT", invalid=True)
                        paired = None
        issues.add("FULL_CASE_UNIVERSE_NOT_ESTABLISHED_BY_HITSETS")
    elif declared_pairs is not None:
        issues.add("PAIRED_COUNTS_WITHOUT_VALID_HELD_SCORES", invalid=True)
    complete = _boolean(evaluation.get("comparison_complete"))
    if evaluation and type(evaluation.get("comparison_complete")) is not bool:
        issues.add("COMPARISON_COMPLETENESS_TYPE_INVALID", invalid=True)
    top_complete = _boolean(report.get("comparison_complete"))
    if complete is not None and top_complete is not None and complete != top_complete:
        issues.add("COMPARISON_COMPLETENESS_DECLARATIONS_DIFFER", invalid=True)
    if (complete is True or top_complete is True) and (dev is None or held is None):
        issues.add("COMPLETE_COMPARISON_MISSING_VALID_SCORES", invalid=True)
    if (complete is False or top_complete is False) and held is not None:
        issues.add("INCOMPLETE_COMPARISON_HAS_HELD_SCORES", invalid=True)
        paired = None
    if not scoring_allowed:
        if dev is not None or held is not None:
            issues.add("TERMINAL_STATUS_WITH_SCORED_CONTENT", invalid=True)
        dev, held, dev_hits, paired, expected, selection_consistent = (None,) * 6
    if dev is not None:
        issues.add("SELECTION_PROVENANCE_NOT_PRESENT_IN_COMPACT_REPORT")
    return {"selected_arm": selected, "derived_dev_selected_arm": expected,
            "dev_selection_consistent": selection_consistent,
            "selection_provenance_verified": False,
            "declared_complete": complete, "dev": dev, "holdout": held,
            "dev_paired_deltas": _paired(dev_hits),
            "paired_deltas": paired, "case_universe_verified": False,
            "paired_comparison_qualified": False,
            "holdout_scope": "reused-experiment-heldout-not-pristine-confirmation"}


def _audit(report, issues):
    audit = _section(report, "audit", issues)
    summary = audit.get("full_panel_summary")
    result = {"coverage_complete": None, "counts": None, "committed_updates": None,
              "group_counts": None, "signal_classification": "unknown"}
    if summary is None:
        issues.add("AUDIT_UNAVAILABLE")
        return result
    if type(summary) is not dict:
        issues.add("AUDIT_SUMMARY_INVALID", invalid=True)
        return result
    fields = ("planned_attempts", "actual_dispatched_attempts", "reward_eligible_attempts",
              "infrastructure_exclusions", "context_exclusions", "not_reached")
    counts = {key: summary.get(key) for key in fields}
    valid = all(_integer(v) for v in counts.values())
    valid &= counts["planned_attempts"] == 256
    if valid:
        valid = sum(counts[k] for k in ("reward_eligible_attempts", "infrastructure_exclusions",
                                       "context_exclusions", "not_reached")) == 256
        valid &= counts["reward_eligible_attempts"] <= counts["actual_dispatched_attempts"] <= \
            counts["reward_eligible_attempts"] + counts["infrastructure_exclusions"]
    if not valid:
        issues.add("AUDIT_COUNTS_INVALID", invalid=True)
        return result
    result["counts"] = counts
    complete = counts["reward_eligible_attempts"] == 256 and \
        all(counts[k] == 0 for k in ("infrastructure_exclusions", "context_exclusions", "not_reached"))
    if summary.get("complete") is not complete or \
            summary.get("all_slots_reached") is not (counts["not_reached"] == 0):
        issues.add("AUDIT_COMPLETENESS_INCONSISTENT", invalid=True)
        return result
    result["coverage_complete"] = complete
    if type(summary.get("fatal_native_state")) is not bool:
        issues.add("AUDIT_FATAL_NATIVE_STATE_TYPE_INVALID", invalid=True)
        return result
    if summary["fatal_native_state"]:
        issues.add("AUDIT_FATAL_NATIVE_STATE_DECLARED", invalid=True)
        return result
    groups = summary.get("groups")
    if type(groups) is not list or len(groups) != 32:
        issues.add("AUDIT_GROUP_INVENTORY_INVALID", invalid=True)
        return result
    parents, successes, eligible = set(), 0, 0
    totals = {"all_zero": 0, "all_one": 0, "mixed": 0, "incomplete": 0}
    for group in groups:
        if type(group) is not dict or type(group.get("parent_id")) is not str or \
                not group["parent_id"] or len(group["parent_id"]) > 512 or group["parent_id"] in parents or \
                type(group.get("planned")) is not int or group["planned"] != 8 or \
                not _integer(group.get("eligible"), 0, 8) or \
                not _integer(group.get("successes"), 0, group.get("eligible", 0)):
            issues.add("AUDIT_GROUP_INVALID_OR_DUPLICATE", invalid=True)
            return result
        parents.add(group["parent_id"])
        n, k = group["eligible"], group["successes"]
        flags = {"all_zero": n == 8 and k == 0, "all_one": n == 8 and k == 8,
                 "mixed": 0 < k < n}
        if any(group.get(key) is not value for key, value in flags.items()):
            issues.add("AUDIT_GROUP_FLAGS_INCONSISTENT", invalid=True)
            return result
        for key, value in flags.items():
            totals[key] += value
        totals["incomplete"] += n != 8
        successes += k
        eligible += n
    mean = successes / eligible if eligible else None
    reported_mean = summary.get("eligible_mean_reward")
    if eligible != counts["reward_eligible_attempts"] or \
            type(summary.get("mixed_groups")) is not int or summary["mixed_groups"] != totals["mixed"] or \
            type(summary.get("eligible_mean_denominator")) is not int or summary["eligible_mean_denominator"] != eligible or \
            (reported_mean is not None if mean is None else
             not _finite(reported_mean) or abs(reported_mean - mean) > 1e-12):
        issues.add("AUDIT_GROUP_AGGREGATE_INCONSISTENT", invalid=True)
        return result
    result["group_counts"] = totals
    for key, expected in (("planned_attempts", 256), ("planned_parents", 32), ("planned_batches", 4)):
        if type(audit.get(key)) is not int or audit[key] != expected:
            issues.add("AUDIT_FIXED_PANEL_DECLARATION_INVALID", invalid=True)
    updates, batches = audit.get("committed_updates"), audit.get("physical_attempted_batches")
    if not _integer(updates, 0, 4) or not _integer(batches, 0, 4) or updates > batches:
        issues.add("AUDIT_UPDATE_COUNTS_INVALID", invalid=True)
    else:
        result["committed_updates"] = updates
        if updates > totals["mixed"]:
            issues.add("AUDIT_UPDATES_EXCEED_MIXED_GROUPS", invalid=True)
    all_zero = complete and successes == 0
    if type(audit.get("all_zero_panel")) is not bool or audit["all_zero_panel"] is not all_zero:
        issues.add("AUDIT_ALL_ZERO_DECLARATION_INCONSISTENT", invalid=True)
    if not complete:
        result["signal_classification"] = "partial-audit-not-zero-signal"
        issues.add("PARTIAL_AUDIT_CANNOT_ESTABLISH_ZERO_SIGNAL")
    elif totals["mixed"]:
        result["signal_classification"] = "mixed-groups-observed"
    elif totals["all_zero"] == 32:
        result["signal_classification"] = "complete-all-zero-groups"
    elif totals["all_one"] == 32:
        result["signal_classification"] = "complete-all-one-groups"
    else:
        result["signal_classification"] = "complete-constant-groups-no-centered-signal"
    return result


def _time_matching(report, issues):
    value = _section(report, "metering", issues).get("time_matching")
    result = {"B_seconds": None, "C_seconds": None, "epsilon_seconds": None,
              "declared_matched": None, "derived_matched": None}
    if value is None:
        issues.add("WHOLE_WALL_MATCH_UNAVAILABLE")
        return result
    if type(value) is not dict or any(not _finite(value.get(k)) or not 0 <= value[k] <= 7200
                                    for k in ("B_seconds", "C_seconds")):
        issues.add("WHOLE_WALL_INTERVAL_INVALID", invalid=True)
        return result
    b, c = value["B_seconds"], value["C_seconds"]
    epsilon = min(120.0, max(5.0, 0.05 * b))
    if not _finite(value.get("epsilon_seconds")) or abs(value["epsilon_seconds"] - epsilon) > 1e-9 or \
            value.get("includes_failures_rollback_setup_save_reload_verification") is not True or \
            value.get("idle_padding") is not False or value.get("clock") != "whole-synchronized-model-phase-wall":
        issues.add("WHOLE_WALL_CONTRACT_INVALID", invalid=True)
        return result
    matched = abs(b - c) <= epsilon
    result.update(B_seconds=b, C_seconds=c, epsilon_seconds=epsilon,
                  declared_matched=_boolean(value.get("matched")), derived_matched=matched)
    if value.get("matched") is not matched:
        issues.add("WHOLE_WALL_MATCH_DECLARATION_INCONSISTENT", invalid=True)
    if type(report.get("compute_matched")) is bool and report["compute_matched"] is not matched:
        issues.add("COMPUTE_MATCH_AXIS_INCONSISTENT", invalid=True)
    return result


def _public(report, comparison, issues, *, scoring_allowed=True):
    public = _section(report, "public", issues)
    selected = comparison["selected_arm"]
    status = public.get("status")
    result = {"status": status if type(status) is str and status in PUBLIC_STATUSES else None,
              "expected_tasks": 120, "expected_queries": 167, "expected_views": 334,
              "reported_task_count": None, "task_count_verified": False,
              "coverage": None, "micro_pass_at_2": None, "derived_threshold_reached": None}
    selection_valid = type(public.get("selected_arm")) is str and \
        public["selected_arm"] in ARMS and public["selected_arm"] == selected and \
        comparison["dev_selection_consistent"] is True
    if public and not selection_valid:
        issues.add("PUBLIC_SELECTED_ARM_INCONSISTENT", invalid=True)
    if public and (type(status) is not str or status not in PUBLIC_STATUSES):
        issues.add("PUBLIC_STATUS_UNRECOGNIZED", invalid=True)
    coverage = public.get("coverage")
    coverage_valid = False
    if coverage is not None:
        keys = ("planned_queries", "observed_queries", "planned_views", "observed_views", "actual_generation_calls")
        if type(coverage) is not dict or any(not _integer(coverage.get(k), 0, 334) for k in keys) or \
                any(coverage[k] != n for k, n in (("planned_queries", 167), ("observed_queries", 167),
                                                 ("planned_views", 334), ("observed_views", 334))) or \
                type(coverage.get("complete_prediction_coverage")) is not bool or \
                type(coverage.get("deadline_exceeded")) is not bool or coverage.get("query_targets_used") is not False:
            issues.add("PUBLIC_COVERAGE_INVALID", invalid=True)
        else:
            if coverage["complete_prediction_coverage"] and coverage["actual_generation_calls"] != 334:
                issues.add("PUBLIC_COMPLETE_COVERAGE_CALL_COUNT_INCONSISTENT", invalid=True)
            else:
                coverage_valid = True
                result["coverage"] = {k: coverage[k] for k in keys}
                result["coverage"].update(complete_prediction_coverage=coverage["complete_prediction_coverage"],
                                          deadline_exceeded=coverage["deadline_exceeded"])
    elif public:
        issues.add("PUBLIC_COVERAGE_UNAVAILABLE", invalid=True)
    # The consumer's compact public object intentionally omits a task list/count.
    # A 167-query denominator cannot prove that those queries belong to 120 tasks.
    if public:
        issues.add("PUBLIC_120_TASK_UNIVERSE_NOT_PRESENT_IN_COMPACT_REPORT")
    metric = public.get("micro_pass_at_2")
    if metric is None:
        issues.add("PUBLIC_SCORE_UNAVAILABLE")
        if status == "SEALED_SCORER_ROWS_REPLAYED" or public.get("scorer_rows_complete") is True or \
                report.get("public_benchmark_evidence_eligible") is True:
            issues.add("PUBLIC_SCORE_CLAIM_WITHOUT_METRIC", invalid=True)
        return result
    if type(metric) is not dict or not _integer(metric.get("numerator"), 0, 167) or \
            type(metric.get("denominator")) is not int or metric["denominator"] != 167 or \
            metric.get("unit") != "test" or not _finite(metric.get("value")) or \
            abs(metric["value"] - metric["numerator"] / 167) > 1e-12:
        issues.add("PUBLIC_ORIGINAL_DENOMINATOR_METRIC_INVALID", invalid=True)
        return result
    if status != "SEALED_SCORER_ROWS_REPLAYED" or public.get("scorer_rows_complete") is not True:
        issues.add("PUBLIC_METRIC_WITHOUT_REPLAY_DECLARATION", invalid=True)
        return result
    if not scoring_allowed:
        issues.add("TERMINAL_STATUS_WITH_SCORED_CONTENT", invalid=True)
    if not (scoring_allowed and selection_valid and coverage_valid):
        issues.add("PUBLIC_METRIC_DEPENDENCIES_INVALID", invalid=True)
        return result
    result["micro_pass_at_2"] = {k: metric[k] for k in ("numerator", "denominator", "value", "unit")}
    threshold = metric["numerator"] >= 151
    result["derived_threshold_reached"] = threshold
    if public.get("metric_threshold_reached") is not threshold:
        issues.add("PUBLIC_THRESHOLD_DECLARATION_INCONSISTENT", invalid=True)
    if report.get("public_goal_met") is True and not threshold:
        issues.add("PUBLIC_GOAL_CLAIM_BELOW_THRESHOLD", invalid=True)
    return result


def _checkpoint_consistency(report, audit, comparison, issues):
    checkpoints = _section(report, "checkpoints", issues)
    b = _section(checkpoints, "B", issues)
    counts = _section(b, "counts", issues)
    if "rl_updates" not in counts:
        return
    n = counts["rl_updates"]
    if not _integer(n, 0, 4):
        issues.add("CHECKPOINT_RL_UPDATE_COUNT_INVALID", invalid=True)
        return
    if audit["committed_updates"] is not None and n != audit["committed_updates"]:
        issues.add("CHECKPOINT_AUDIT_UPDATE_COUNTS_DIFFER", invalid=True)
    if n == 0:
        a = _section(checkpoints, "A", issues)
        ah, bh = a.get("adapter_sha256"), b.get("adapter_sha256")
        if type(ah) is not str or len(ah) != 64 or any(c not in "0123456789abcdef" for c in ah) or bh != ah:
            issues.add("NO_UPDATE_B_ADAPTER_DIFFERS_FROM_A", invalid=True)
        for scope in ("dev", "holdout"):
            rows = comparison[scope]
            if rows is not None and rows["A"]["exact"] != rows["B"]["exact"]:
                issues.add("NO_UPDATE_B_DETERMINISTIC_SCORES_DIFFER", invalid=True)
        for field in ("dev_paired_deltas", "paired_deltas"):
            paired = comparison[field]
            if paired is not None and (paired["B_minus_A"]["gained"] or paired["B_minus_A"]["lost"]):
                issues.add("NO_UPDATE_B_DETERMINISTIC_HITSETS_DIFFER", invalid=True)


def analyze_report(report: dict) -> dict:
    """Summarize declared/derived facts without accepting their authenticity.

    Invalid/missing structures yield stable issue codes and null dependent
    metrics. Arbitrary input errors, paths, case IDs and answer bodies are never
    copied. File, hash and linkage handling belongs to the calling offline CLI.
    """
    issues = _Issues()
    if type(report) is not dict:
        issues.add("REPORT_NOT_OBJECT", invalid=True)
        report = {}
    status = report.get("status")
    status = status if type(status) is str and status in STATUSES else None
    if status is None:
        issues.add("REPORT_STATUS_UNRECOGNIZED", invalid=True)
    reported_format = report.get("format")
    compatible = reported_format == CONSUMER_FORMAT or \
        (reported_format is None and status in COLLECTOR_DIAGNOSTIC_STATUSES)
    if not compatible:
        issues.add("REPORT_FORMAT_UNSUPPORTED" if reported_format is not None else "REPORT_FORMAT_UNAVAILABLE",
                   invalid=True)
    declared = {key: _boolean(report.get(key)) for key in AXES}
    for key in AXES:
        if key in report and type(report[key]) is not bool:
            issues.add("DECLARED_AXIS_TYPE_INVALID", invalid=True)
    provider = report.get("provider_status")
    provider = provider if type(provider) is str and provider in PROVIDER_TERMINAL_STATUSES else None
    if "provider_status" in report and provider is None:
        issues.add("PROVIDER_STATUS_UNRECOGNIZED", invalid=True)
    data = report if compatible else {}
    scoring_allowed = status in SCORING_STATUSES
    if scoring_allowed and declared["evidence_valid"] is not True:
        issues.add("SCORING_STATUS_WITHOUT_VALID_CONTENT_DECLARATION", invalid=True)
        scoring_allowed = False
    comparison = _comparison(data, issues, scoring_allowed=scoring_allowed)
    audit = _audit(data, issues)
    timing = _time_matching(data, issues)
    public = _public(data, comparison, issues, scoring_allowed=scoring_allowed)
    _checkpoint_consistency(data, audit, comparison, issues)
    phase_status = _section(data, "phase_status", issues)
    if "owner_process_closed" in phase_status and type(phase_status["owner_process_closed"]) is not bool:
        issues.add("OWNER_PROCESS_CLOSED_TYPE_INVALID", invalid=True)
    if declared["comparison_eligible"] is True and \
            (declared["comparison_complete"] is not True or timing["derived_matched"] is not True):
        issues.add("COMPARISON_ELIGIBILITY_DECLARATION_INCONSISTENT", invalid=True)
    return {"format": FORMAT, "analysis_authenticated": False, "dispatch_authorized": False,
            "method_efficacy_established": False, "input_status": status,
            "input_format": CONSUMER_FORMAT if reported_format == CONSUMER_FORMAT else None,
            "report_contract_compatible": compatible,
            "structurally_consistent": not issues.invalid,
            "issues": sorted(issues.codes), "declared_axes": declared,
            "declared_provider_status": provider,
            "declared_owner_process_closed": _boolean(phase_status.get("owner_process_closed")),
            "audit": audit, "comparison": comparison, "time_matching": timing, "public": public,
            "qualifications": [
                "All declarations and arithmetic are conditional on unauthenticated supplied JSON; this is not a replacement terminal consumer.",
                "Hitsets do not establish the full same-case universe. Set differences are conditional counts, not qualified paired-effect evidence.",
                "Dev counts and the fixed A/B/C tie rule do not verify the selection seal, source/dataset identity, chronology, or absence of prior held-target access.",
                "The compact report does not expose the full 120-task PUBLIC universe; 167 queries alone do not establish task coverage.",
                "Held32 is reused experiment-held-out evidence; different B/C learning rates define an intervention-package comparison.",
                "Whole synchronized extra-phase wall includes failed work and persistence; it is neither kernel time nor billed time.",
                "No score, authentication, method promotion, or next-run authorization is created by this analysis.",
            ]}
