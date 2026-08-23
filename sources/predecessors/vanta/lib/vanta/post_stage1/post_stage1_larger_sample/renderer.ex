defmodule Vanta.PostStage1LargerSample.Renderer do
  @moduledoc false

  @sample_frame_id "PS1-LA-SAMPLE-002"
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
  def summary(run) do
    baseline = run["metrics"]["baseline"] || %{}
    treatment = run["metrics"]["treatment"] || %{}
    gates = get_in(run, ["metrics", "hard_gates"]) || %{}

    """
    # Post-Stage-1 Lane A Larger Controlled Sample

    Lane: Lane A larger controlled sample
    Sample frame: #{run["sample_frame_id"]}
    Metric policy version: #{run["metric_policy_version"]}
    Threshold status: #{run["threshold_status"]}
    Status: #{run["status"]}
    Fixture count: #{run["fixture_count"]}
    Baseline: #{run["baseline"]}
    Treatment: #{run["treatment"]}

    ## Fixed Controls

    - model identity: #{get_in(run, ["run_controls", "model_identity"])}
    - harness identity: #{get_in(run, ["run_controls", "harness_identity"])}
    - planner adapter: #{get_in(run, ["run_controls", "planner_adapter"])}
    - allowed action set: #{Enum.join(get_in(run, ["run_controls", "allowed_action_set"]) || [], ", ")}
    - prompt character budget: #{get_in(run, ["run_controls", "prompt_character_budget"])}
    - response character budget: #{get_in(run, ["run_controls", "response_character_budget"])}
    - action-attempt limit: #{get_in(run, ["run_controls", "action_attempt_limit"])}
    - recovery-attempt limit: #{get_in(run, ["run_controls", "recovery_attempt_limit"])}
    - context budget: #{inspect(get_in(run, ["run_controls", "context_budget"]))}
    - compute matching rule: #{get_in(run, ["run_controls", "compute_matching_rule"])}

    ## Metrics

    | Metric | Baseline | Treatment |
    | --- | ---: | ---: |
    #{metric_table_rows(baseline, treatment)}

    ## Hard Gates

    - unsupported_commits: #{gates["unsupported_commits"]}
    - memory_writes: #{gates["memory_writes"]}
    - disallowed_side_effect_classes: #{gates["disallowed_side_effect_classes"]}
    - required_artifacts_valid: #{gates["required_artifacts_valid"]}
    - arm_identity_compliant: #{gates["arm_identity_compliant"]}
    - fixture_count_exact: #{gates["fixture_count_exact"]}
    - strata_complete: #{gates["strata_complete"]}
    #{blocking_details(gates)}

    ## Interpretation Boundaries

    #{interpretation(run["threshold_status"])}

    This report must not be described as H1-H5 validation, production readiness,
    full Context OS validation, memory-write approval, irreversible-effect
    approval, or a pure model-only OpenClaw baseline result.
    """
  end

  defp metric_table_rows(baseline, treatment) do
    @required_metrics
    |> Enum.map(fn metric ->
      "| `#{metric}` | #{format_metric(baseline[metric])} | #{format_metric(treatment[metric])} |"
    end)
    |> Enum.join("\n")
  end

  defp blocking_details(%{"artifact_errors" => errors}) when is_list(errors) and errors != [] do
    rows =
      errors
      |> Enum.map(&"- #{&1}")
      |> Enum.join("\n")

    """

    ## Blocking Details

    #{rows}
    """
  end

  defp blocking_details(_gates), do: ""

  defp interpretation("blocked_missing_metric") do
    "The run is data collection only because a required metric, artifact, control, or fixture-frame field is missing."
  end

  defp interpretation("failed_no_acceptance") do
    "The run has measured metrics but fails at least one PS1-G2 hard gate, threshold, or no-regression rule."
  end

  defp interpretation("pass_acceptance_candidate") do
    "The run passes PS1-G2 as a pass_acceptance_candidate only. It still requires future manifest closure before accepted_by_closure may be used."
  end

  defp interpretation(status), do: "Unhandled threshold status: #{status}."

  def fixture_inventory_markdown(inventory) do
    rows =
      inventory
      |> Enum.map(fn item ->
        "| `#{item["fixture_id"]}` | #{item["stratum"]} | #{Enum.join(item["action_types"], ", ")} | #{Enum.join(item["side_effect_classes"], ", ")} | #{item["expected_runtime_status"]} | #{item["expected_label_source"]} | `#{item["fixture_hash"]}` |"
      end)
      |> Enum.join("\n")

    """
    # Fixture Inventory

    Sample frame: #{@sample_frame_id}
    Fixture count: #{length(inventory)}

    | Fixture ID | Stratum | Action types | Side-effect classes | Expected runtime status | Expected label source | Fixture hash |
    | --- | --- | --- | --- | --- | --- | --- |
    #{rows}
    """
  end

  defp format_metric(value) when is_float(value), do: :erlang.float_to_binary(value, decimals: 4)
  defp format_metric(value) when is_integer(value), do: Integer.to_string(value)
  defp format_metric(value) when is_boolean(value), do: to_string(value)
  defp format_metric(nil), do: "missing"
  defp format_metric(value), do: to_string(value)
end
