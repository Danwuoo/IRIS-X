defmodule Vanta.RecoveryRunner do
  @moduledoc """
  Runs targeted Phase 4 recovery over a failed fixture-local episode.
  """

  alias Vanta.{FixtureAcceptance, OpenClawRecoveryAdapter, RecoveryPolicy, Runtime}

  @experiment_id "experiment_004_targeted_recovery"

  def run_task(task, source_workspace, opts \\ []) do
    recovery_adapter = Keyword.get(opts, :recovery_adapter, OpenClawRecoveryAdapter)
    recovery_opts = Keyword.get(opts, :recovery_opts, [])

    with {:ok, failed_result} <- Runtime.run_task(task, source_workspace),
         recovery_input <- recovery_input(task, failed_result, recovery_opts),
         {:ok, decision} <- recovery_adapter.recover(recovery_input, recovery_opts),
         {:ok, outcome} <-
           RecoveryPolicy.apply(decision["recovery_policy"], failed_result.workspace, %{
             failed_result: failed_result,
             recovery_input: recovery_input,
             decision: decision
           }) do
      expected_labels = FixtureAcceptance.expected_failure_labels(failed_result.workspace)
      expected_policy = FixtureAcceptance.expected_recovery_policy(failed_result.workspace)

      {:ok,
       %{
         arm: :targeted_recovery,
         task: task,
         workspace: failed_result.workspace,
         initial_result: failed_result,
         recovery_input: recovery_input,
         recovery_decision: decision,
         recovery_outcome: outcome,
         expected_failure_labels: expected_labels,
         expected_recovery_policy: expected_policy,
         expected_rollback_status:
           FixtureAcceptance.expected_rollback_status(failed_result.workspace),
         recovery_success?: recovery_success?(outcome, expected_policy, decision),
         targeted_recovery_success?:
           targeted_recovery_success?(outcome, expected_policy, decision),
         failure_label_accuracy?: failure_label_accuracy?(decision, expected_labels),
         repeated_failure?: not Map.get(outcome, "success", false),
         budget_usage: decision["budget_usage"]
       }}
    end
  end

  def recovery_input(task, failed_result, opts \\ []) do
    %{
      "schema_version" => Vanta.schema_version(),
      "experiment_id" => @experiment_id,
      "task_id" => task["task_id"],
      "episode_id" => failed_result.episode_id,
      "allowed_recovery_policies" => RecoveryPolicy.policies(),
      "budget_constraints" => %{
        "max_prompt_chars" => Keyword.get(opts, :max_prompt_chars, 20_000),
        "max_response_chars" => Keyword.get(opts, :max_response_chars, 12_000),
        "max_action_attempts" => Keyword.get(opts, :max_action_attempts, 1)
      },
      "failure_context" => %{
        "task" => public_task_fields(task),
        "runtime_status" => failed_result.status,
        "rollback_status" => failed_result.rollback_status,
        "invalid_actions" => failed_result.invalid_actions,
        "journal" => failed_result.journal,
        "evidence_packets" => compact_artifacts(failed_result.evidence_packets),
        "verifier_outputs" => compact_artifacts(failed_result.verifier_outputs),
        "observations" => compact_artifacts(failed_result.observations)
      }
    }
  end

  defp recovery_success?(outcome, expected_policy, decision) do
    Map.get(outcome, "success", false) and decision["recovery_policy"] == expected_policy
  end

  defp targeted_recovery_success?(outcome, expected_policy, decision) do
    recovery_success?(outcome, expected_policy, decision)
  end

  defp failure_label_accuracy?(decision, expected_labels) do
    expected_labels != [] and
      Enum.all?(expected_labels, &(&1 in decision["failure_labels"]))
  end

  defp public_task_fields(task) do
    Map.take(task, [
      "schema_version",
      "task_id",
      "task_type",
      "prompt",
      "input_artifacts",
      "allowed_actions",
      "success_criteria",
      "failure_criteria",
      "side_effect_classes"
    ])
  end

  defp compact_artifacts(artifacts) when is_list(artifacts) do
    Enum.map(artifacts, &compact_artifact/1)
  end

  defp compact_artifact(artifact) when is_map(artifact) do
    artifact
    |> Map.drop(["content", "candidate_content"])
    |> compact_nested()
  end

  defp compact_artifact(artifact), do: artifact

  defp compact_nested(map) do
    Map.new(map, fn
      {key, value} when is_map(value) -> {key, compact_artifact(value)}
      {key, value} when is_list(value) -> {key, compact_artifacts(value)}
      pair -> pair
    end)
  end
end
