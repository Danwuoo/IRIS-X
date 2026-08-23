defmodule Vanta.Experiment004 do
  @moduledoc """
  Compute-matched Phase 4 targeted recovery ablation.

  This experiment compares blind retry against OpenClaw-backed failure
  classification plus allowlisted targeted recovery policies. It records local
  protocol output only; it must not be described as validation of H4 until a
  measured run with configured OpenClaw execution exists.
  """

  alias Vanta.{
    BlindRetryRunner,
    FixtureAcceptance,
    OpenClawRecoveryAdapter,
    RecoveryRunner,
    Schema
  }

  @experiment_id "experiment_004_targeted_recovery"

  def run(fixture_root, opts \\ []) do
    out_dir = Keyword.get(opts, :out_dir)
    recovery_adapter = Keyword.get(opts, :recovery_adapter, OpenClawRecoveryAdapter)
    recovery_opts = Keyword.get(opts, :recovery_opts, [])

    with :ok <- ensure_recovery_ready(recovery_adapter, recovery_opts) do
      tasks =
        fixture_root
        |> phase4_task_paths()
        |> Enum.map(fn task_path ->
          workspace = Path.dirname(task_path)
          task = Schema.load_json!(task_path)

          {:ok, targeted} =
            RecoveryRunner.run_task(task, workspace,
              recovery_adapter: recovery_adapter,
              recovery_opts: recovery_opts
            )

          {:ok, blind} =
            BlindRetryRunner.run_task(task, workspace, matched_budget: targeted.budget_usage)

          task_result(task, workspace, targeted, blind)
        end)

      run = %{
        "schema_version" => Vanta.schema_version(),
        "experiment_id" => @experiment_id,
        "status" => run_status(tasks),
        "baseline" =>
          "blind_retry_#{recovery_id(recovery_adapter, recovery_opts)}_matched_budget",
        "treatment" =>
          "targeted_recovery_#{recovery_id(recovery_adapter, recovery_opts)}_matched_budget",
        "fixture_count" => length(tasks),
        "tasks" => tasks,
        "metrics" => metrics(tasks)
      }

      run = Schema.validate!("experiment_run", run)

      if out_dir do
        write_results!(out_dir, run)
      end

      {:ok, run}
    end
  end

  defp phase4_task_paths(fixture_root) do
    fixture_root
    |> Path.join("*/task.json")
    |> Path.wildcard()
    |> Enum.sort()
    |> Enum.filter(fn task_path ->
      task_path
      |> Path.dirname()
      |> FixtureAcceptance.expected_recovery_policy()
      |> is_binary() and
        task_path
        |> Path.dirname()
        |> Path.basename()
        |> String.starts_with?("docops_ps1_")
        |> Kernel.not()
    end)
  end

  defp ensure_recovery_ready(OpenClawRecoveryAdapter, opts) do
    case OpenClawRecoveryAdapter.env(opts) do
      {:ok, _env} -> :ok
      {:error, reason} -> {:error, {:llm_recovery_not_configured, reason}}
    end
  end

  defp ensure_recovery_ready(adapter, opts) do
    cond do
      function_exported?(adapter, :env, 1) ->
        case adapter.env(opts) do
          {:ok, _env} -> :ok
          {:error, reason} -> {:error, {:llm_recovery_not_configured, reason}}
          _other -> :ok
        end

      true ->
        :ok
    end
  end

  defp task_result(task, workspace, targeted, blind) do
    %{
      "task_id" => task["task_id"],
      "expected_failure_labels" => FixtureAcceptance.expected_failure_labels(workspace),
      "expected_recovery_policy" => FixtureAcceptance.expected_recovery_policy(workspace),
      "expected_rollback_status" => FixtureAcceptance.expected_rollback_status(workspace),
      "targeted_recovery" => targeted_result(targeted),
      "blind_retry" => blind_result(blind),
      "compute_match" => compute_match?(targeted.budget_usage, blind.budget_usage)
    }
  end

  defp targeted_result(result) do
    %{
      "initial_status" => result.initial_result.status,
      "initial_rollback_status" => result.initial_result.rollback_status,
      "recovery_policy" => result.recovery_decision["recovery_policy"],
      "failure_labels" => result.recovery_decision["failure_labels"],
      "primary_failure_label" => result.recovery_decision["primary_failure_label"],
      "confidence" => result.recovery_decision["confidence"],
      "adapter_error" => result.recovery_decision["adapter_error"],
      "recovery_success" => result.recovery_success?,
      "targeted_recovery_success" => result.targeted_recovery_success?,
      "failure_label_accuracy" => result.failure_label_accuracy?,
      "repeated_failure" => result.repeated_failure?,
      "budget_usage" => result.budget_usage,
      "recovery_outcome" => result.recovery_outcome
    }
  end

  defp blind_result(result) do
    %{
      "status" => result.status,
      "attempt_count" => length(result.attempts),
      "recovery_success" => result.recovery_success?,
      "targeted_recovery_success" => result.targeted_recovery_success?,
      "failure_label_accuracy" => result.failure_label_accuracy?,
      "repeated_failure" => result.repeated_failure?,
      "budget_usage" => result.budget_usage
    }
  end

  defp metrics(tasks) do
    %{
      "targeted_recovery" => arm_metrics(tasks, "targeted_recovery"),
      "blind_retry" => arm_metrics(tasks, "blind_retry"),
      "compute_matching" => %{
        "budget_matched" => Enum.all?(tasks, & &1["compute_match"]),
        "matched_fixture_count" => Enum.count(tasks, & &1["compute_match"]),
        "fixture_count" => length(tasks)
      }
    }
  end

  defp arm_metrics(tasks, arm) do
    results = Enum.map(tasks, & &1[arm])
    total = length(results)

    %{
      "recovery_success_rate" => rate(results, "recovery_success"),
      "targeted_recovery_success" => rate(results, "targeted_recovery_success"),
      "failure_label_accuracy" => rate(results, "failure_label_accuracy"),
      "repeated_failure_rate" => rate(results, "repeated_failure"),
      "recovery_compute_cost" => compute_cost(results),
      "rollback_recovery_success" =>
        policy_rate(tasks, arm, "reconstruct_rollback_from_diff", "recovery_success"),
      "audit_gap_closure_rate" =>
        policy_rate(tasks, arm, "repair_audit_refs", "recovery_success"),
      "compensation_policy_accuracy" =>
        policy_rate(tasks, arm, "produce_compensation_record", "targeted_recovery_success"),
      "item_count" => total
    }
  end

  defp policy_rate(tasks, arm, policy, field) do
    scoped = Enum.filter(tasks, &(&1["expected_recovery_policy"] == policy))

    scoped
    |> Enum.map(& &1[arm])
    |> rate(field)
  end

  defp rate([], _field), do: 0.0

  defp rate(results, field) do
    Enum.count(results, &(&1[field] == true)) / length(results)
  end

  defp compute_cost(results) do
    budgets = Enum.map(results, & &1["budget_usage"])

    %{
      "mean_model_call_count" => mean_budget(budgets, "model_call_count"),
      "mean_prompt_chars" => mean_budget(budgets, "prompt_chars"),
      "mean_response_chars" => mean_budget(budgets, "response_chars"),
      "mean_estimated_input_tokens" => mean_budget(budgets, "estimated_input_tokens"),
      "mean_estimated_output_tokens" => mean_budget(budgets, "estimated_output_tokens"),
      "mean_action_attempts" => mean_budget(budgets, "max_action_attempts")
    }
  end

  defp mean_budget([], _field), do: 0.0

  defp mean_budget(budgets, field) do
    budgets
    |> Enum.map(&(Map.get(&1, field) || 0))
    |> Enum.sum()
    |> Kernel./(length(budgets))
  end

  defp compute_match?(left, right) do
    fields = ~w(
      model_call_count
      max_prompt_chars
      max_response_chars
      max_action_attempts
    )

    Enum.all?(fields, &(Map.get(left, &1) == Map.get(right, &1)))
  end

  defp run_status([]), do: "not_run"

  defp run_status(tasks) do
    if Enum.any?(tasks, &get_in(&1, ["targeted_recovery", "adapter_error"])) do
      "partial"
    else
      "completed"
    end
  end

  defp recovery_id(adapter, opts) do
    if function_exported?(adapter, :recovery_id, 1) do
      adapter.recovery_id(opts)
    else
      "llm_recovery"
    end
  end

  defp write_results!(out_dir, run) do
    File.mkdir_p!(out_dir)
    File.write!(Path.join(out_dir, "run.json"), Jason.encode!(run, pretty: true))
    File.write!(Path.join(out_dir, "summary.md"), summary(run))
  end

  defp summary(run) do
    """
    # Experiment 004 Local Run

    Status: #{run["status"]}
    Fixture count: #{run["fixture_count"]}
    Baseline: #{run["baseline"]}
    Treatment: #{run["treatment"]}

    ## Blind Retry

    #{metric_lines(run["metrics"]["blind_retry"])}

    ## Targeted Recovery

    #{metric_lines(run["metrics"]["targeted_recovery"])}

    ## Compute Matching

    - budget_matched: #{run["metrics"]["compute_matching"]["budget_matched"]}
    - matched_fixture_count: #{run["metrics"]["compute_matching"]["matched_fixture_count"]}

    Interpretation: this is the Phase 4 targeted-recovery ablation protocol
    output. It must not be described as validation of H4 unless produced by a
    measured OpenClaw run with the matched-budget controls preserved.
    """
  end

  defp metric_lines(metrics) do
    """
    - recovery_success_rate: #{metrics["recovery_success_rate"]}
    - targeted_recovery_success: #{metrics["targeted_recovery_success"]}
    - failure_label_accuracy: #{metrics["failure_label_accuracy"]}
    - repeated_failure_rate: #{metrics["repeated_failure_rate"]}
    - rollback_recovery_success: #{metrics["rollback_recovery_success"]}
    - audit_gap_closure_rate: #{metrics["audit_gap_closure_rate"]}
    - compensation_policy_accuracy: #{metrics["compensation_policy_accuracy"]}
    """
  end
end
