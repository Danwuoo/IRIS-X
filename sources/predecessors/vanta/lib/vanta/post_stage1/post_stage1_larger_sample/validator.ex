defmodule Vanta.PostStage1LargerSample.Validator do
  @moduledoc false

  alias Vanta.PostStage1LargerSample.PathHelpers

  @sample_frame_id "PS1-LA-SAMPLE-002"
  @metric_policy_version "PS1-LA-METRIC-001"
  @required_metrics ~w(
    task_success_rate
    invalid_action_rate
    verifier_false_accept_rate
    verifier_false_reject_rate
    evidence_sufficiency_score
    commit_integrity_score
    replay_consistency
    audit_completeness
    recovery_success_rate
    targeted_recovery_success
    failure_label_accuracy
    repeated_failure_rate
    working_set_budget_adherence
    working_set_provenance_completeness
    context_omission_error_rate
    working_set_relevance_score
    long_task_stability
  )

  def threshold_status(run) do
    cond do
      missing_report_fields?(run) or missing_required_metrics?(run) ->
        "blocked_missing_metric"

      not hard_gates_pass?(run) or not thresholds_pass?(run) ->
        "failed_no_acceptance"

      true ->
        "pass_acceptance_candidate"
    end
  end

  defp missing_report_fields?(run) do
    run["fixture_count"] != 48 or
      run["sample_frame_id"] != @sample_frame_id or
      run["metric_policy_version"] != @metric_policy_version or
      not is_map(run["run_controls"]) or
      not is_map(run["arm_metadata"]) or
      not PathHelpers.present?(run["fixture_inventory_ref"])
  end

  defp missing_required_metrics?(run) do
    treatment = get_in(run, ["metrics", "treatment"]) || %{}

    Enum.any?(@required_metrics, fn metric ->
      not Map.has_key?(treatment, metric)
    end)
  end

  defp hard_gates_pass?(run) do
    gates = get_in(run, ["metrics", "hard_gates"]) || %{}

    gates["unsupported_commits"] == 0 and
      gates["memory_writes"] == 0 and
      gates["disallowed_side_effect_classes"] == 0 and
      gates["required_artifacts_valid"] == true and
      gates["arm_identity_compliant"] == true and
      gates["fixture_count_exact"] == true and
      gates["strata_complete"] == true
  end

  defp thresholds_pass?(run) do
    baseline = get_in(run, ["metrics", "baseline"]) || %{}
    treatment = get_in(run, ["metrics", "treatment"]) || %{}

    treatment["task_success_rate"] >= 0.90 and
      treatment["task_success_rate"] >= baseline["task_success_rate"] and
      treatment["verifier_false_accept_rate"] == 0.0 and
      treatment["verifier_false_reject_rate"] <= 0.05 and
      (treatment["verifier_false_reject_rate"] <= baseline["verifier_false_reject_rate"] or
         treatment["verifier_false_accept_rate"] == 0.0) and
      treatment["evidence_sufficiency_score"] >= 0.95 and
      treatment["commit_integrity_score"] == 1.0 and
      treatment["replay_consistency"] == 1.0 and
      treatment["audit_completeness"] == 1.0 and
      treatment["recovery_success_rate"] >= 0.80 and
      treatment["recovery_success_rate"] > baseline["recovery_success_rate"] and
      treatment["targeted_recovery_success"] >= 0.80 and
      treatment["targeted_recovery_success"] > baseline["targeted_recovery_success"] and
      treatment["failure_label_accuracy"] >= 0.80 and
      treatment["repeated_failure_rate"] <= 0.20 and
      treatment["repeated_failure_rate"] < baseline["repeated_failure_rate"] and
      treatment["working_set_budget_adherence"] == 1.0 and
      treatment["working_set_provenance_completeness"] == 1.0 and
      treatment["context_omission_error_rate"] <= 0.10 and
      treatment["context_omission_error_rate"] < baseline["context_omission_error_rate"] and
      treatment["working_set_relevance_score"] >= 0.80 and
      treatment["working_set_relevance_score"] >= baseline["working_set_relevance_score"] and
      treatment["long_task_stability"] >= 0.90 and
      treatment["long_task_stability"] >= baseline["long_task_stability"]
  rescue
    _error -> false
  end
end
