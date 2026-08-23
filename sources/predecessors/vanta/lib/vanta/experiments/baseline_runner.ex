defmodule Vanta.BaselineRunner do
  @moduledoc """
  Direct action execution baseline for Experiment 001.

  The baseline receives the same action sequence as treatment, executes directly
  through the ActionExecutor, and records evaluation labels without producing
  Execution IR, Evidence Packets, Verifier Outputs, commits, or journals.
  """

  alias Vanta.{ActionExecutor, FixtureAcceptance, PlannerAdapter}

  def run_task(task, source_workspace, action_sequence, opts \\ []) do
    workspace = prepare_workspace(source_workspace, opts)

    with {:ok, action_sequence} <- PlannerAdapter.validate_action_sequence(action_sequence) do
      {observations, invalid_actions, errors} =
        Enum.reduce(action_sequence["actions"], {[], 0, []}, fn action,
                                                                {observations, invalid, errors} ->
          action_invalid? = action["action_type"] not in Map.get(task, "allowed_actions", [])

          case safe_execute(workspace, action) do
            {:ok, observation} ->
              acceptance_invalid? =
                match?(
                  {:error, _reason},
                  FixtureAcceptance.evaluate_observation(workspace, observation)
                )

              invalid_count = invalid + if(action_invalid? or acceptance_invalid?, do: 1, else: 0)
              {observations ++ [observation], invalid_count, errors}

            {:error, reason} ->
              error_observation = %{
                "kind" => action["action_type"],
                "error" => inspect(reason),
                "mutated" => false
              }

              {observations ++ [error_observation], invalid + 1, errors ++ [reason]}
          end
        end)

      status = if invalid_actions == 0 and errors == [], do: "committed", else: "invalid_actions"

      task_success? =
        FixtureAcceptance.evaluate_task(workspace, status, invalid_actions, observations)

      {:ok,
       %{
         arm: :baseline,
         workspace: workspace,
         action_sequence: action_sequence,
         observations: observations,
         total_actions: length(action_sequence["actions"]),
         invalid_actions: invalid_actions,
         errors: errors,
         status: status,
         task_success?: task_success?
       }}
    end
  end

  defp safe_execute(workspace, action) do
    ActionExecutor.execute(workspace, %{
      "action_type" => action["action_type"],
      "action_payload" => action["action_payload"]
    })
  rescue
    error -> {:error, {:execution_exception, Exception.message(error)}}
  end

  defp prepare_workspace(source_workspace, opts) do
    if Keyword.get(opts, :copy_workspace?, true) do
      target =
        Path.join(
          System.tmp_dir!(),
          "vanta_baseline_#{Path.basename(source_workspace)}_#{System.unique_integer([:positive])}"
        )

      File.rm_rf!(target)
      File.cp_r!(source_workspace, target)
      target
    else
      source_workspace
    end
  end
end
