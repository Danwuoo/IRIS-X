"""Deterministic derived summary for Phase 6 Batch 1 assessments."""

from __future__ import annotations

from typing import Any, Iterable


def summarize_assessments(
    assessments: Iterable[dict[str, Any]], gate_ids: Iterable[str]
) -> dict[str, Any]:
    records = sorted(assessments, key=lambda item: item["case_id"])
    gates = list(gate_ids)
    direct = {gate_id: [] for gate_id in gates}
    synthetic = {gate_id: [] for gate_id in gates}
    unknowns: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for record in records:
        for gate_id, result in record["trigger_results"].items():
            if result == "triggered_by_direct_evidence":
                direct[gate_id].append(record["case_id"])
            elif result == "triggered_by_fixture":
                synthetic[gate_id].append(record["case_id"])
        if record["unknowns"]:
            unknowns.append({"case_id": record["case_id"], "items": record["unknowns"]})
        if record["conflicts"]:
            conflicts.append({"case_id": record["case_id"], "items": record["conflicts"]})

    pressure = [item for item in records if item["suite"] == "synthetic_pressure"]
    boundaries = [item for item in records if item["suite"] == "attribution_boundaries"]
    replays = [item for item in records if item["suite"] == "historical_replay"]
    valid = [item for item in records if item["assessment_valid"]]
    expected = [item for item in records if item["expected_result_match"]]

    negative_passed = sum(
        item["expected_result_match"]
        for item in pressure
        if item["fixture_role"] == "negative_control"
    )
    near_passed = sum(
        item["expected_result_match"]
        for item in pressure
        if item["fixture_role"] == "near_trigger"
    )
    positive_passed = sum(
        item["expected_result_match"]
        for item in pressure
        if item["fixture_role"] == "synthetic_positive"
    )
    ambiguous_preserved = sum(
        item["expected_result_match"] and item["attribution_status"] == "ambiguous"
        for item in boundaries
    )
    replay_matches = sum(item["expected_result_match"] for item in replays)
    replay_conflicts = sum(bool(item["conflicts"]) for item in replays)

    foundation_established = (
        len(records) == 34
        and len(pressure) == 24
        and len(boundaries) == 8
        and len(replays) == 2
        and len(valid) == len(records)
        and len(expected) == len(records)
        and negative_passed == 8
        and near_passed == 8
        and positive_passed == 8
        and ambiguous_preserved >= 2
        and replay_matches == 2
        and replay_conflicts == 0
        and not conflicts
    )

    if replay_conflicts or conflicts:
        result_category = "Result C — Conflicting evidence"
    elif len(valid) != len(records):
        result_category = "Result D — Invalid batch execution"
    elif foundation_established:
        result_category = "Result A — Foundation established"
    else:
        result_category = "Result B — Instrument incomplete"

    return {
        "schema_version": 1,
        "authority": "derived_data_only_per_case_and_historical_sources_remain_authoritative",
        "result_category": result_category,
        "case_count": len(records),
        "synthetic_pressure_case_count": len(pressure),
        "attribution_boundary_case_count": len(boundaries),
        "historical_replay_case_count": len(replays),
        "valid_assessments": len(valid),
        "invalid_assessments": len(records) - len(valid),
        "expectations_matched": len(expected),
        "negative_controls_passed": negative_passed,
        "near_trigger_cases_passed": near_passed,
        "synthetic_positive_triggers_passed": positive_passed,
        "ambiguous_cases_preserved": ambiguous_preserved,
        "historical_replays_matched": replay_matches,
        "historical_replay_conflicts": replay_conflicts,
        "direct_evidence_triggers_by_gate": direct,
        "synthetic_triggers_by_gate": synthetic,
        "unknowns": unknowns,
        "conflicts": conflicts,
        "model_calls": 0,
        "provider_calls": 0,
        "paid_api_calls": 0,
        "model_subprocesses": 0,
    }
