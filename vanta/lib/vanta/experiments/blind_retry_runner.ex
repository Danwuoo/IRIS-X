defmodule Vanta.BlindRetryRunner do
  @moduledoc """
  Compute-matched blind retry baseline for Experiment 004.

  The baseline repeats the original action sequence without failure labels,
  credit vectors, or recovery-policy hints. Its budget ledger is matched to the
  targeted arm for the same fixture.
  """

  alias Vanta.Runtime

  def run_task(task, source_workspace, opts \\ []) do
    matched_budget = Keyword.fetch!(opts, :matched_budget)
    max_attempts = Map.get(matched_budget, "max_action_attempts", 1)

    attempts =
      1..max(max_attempts, 1)
      |> Enum.map(fn _index ->
        {:ok, result} = Runtime.run_task(task, source_workspace)
        result
      end)

    {:ok,
     %{
       arm: :blind_retry,
       task: task,
       attempts: attempts,
       status: attempts |> List.last() |> Map.fetch!(:status),
       recovery_success?: false,
       targeted_recovery_success?: false,
       failure_label_accuracy?: false,
       repeated_failure?: true,
       budget_usage: matched_budget
     }}
  end
end
