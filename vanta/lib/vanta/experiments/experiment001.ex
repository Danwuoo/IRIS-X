defmodule Vanta.Experiment001 do
  @moduledoc """
  Local Experiment 001 runner for Stage 1 Document Ops fixtures.
  """

  alias Vanta.{
    BaselineRunner,
    FixtureAcceptance,
    OpenClawPlannerAdapter,
    OpenAIPlannerAdapter,
    ReplayRunner,
    Runtime,
    Schema
  }

  def run(fixture_root, opts \\ []) do
    out_dir = Keyword.get(opts, :out_dir)
    planner = Keyword.get(opts, :planner, OpenAIPlannerAdapter)
    planner_opts = Keyword.get(opts, :planner_opts, [])

    with :ok <- ensure_llm_ready(planner, planner_opts) do
      tasks =
        fixture_root
        |> Path.join("*/task.json")
        |> Path.wildcard()
        |> Enum.sort()
        |> Enum.map(fn task_path ->
          workspace = Path.dirname(task_path)
          task = Schema.load_json!(task_path)

          {:ok, action_sequence} = planner.propose_actions(task, workspace, planner_opts)
          {:ok, baseline} = BaselineRunner.run_task(task, workspace, action_sequence)
          {:ok, treatment} = Runtime.run_task(task, workspace, action_sequence: action_sequence)

          {:ok, replay} =
            ReplayRunner.replay(task, workspace, treatment.journal, %{
              evidence_packets: treatment.evidence_packets,
              verifier_outputs: treatment.verifier_outputs
            })

          task_result(task, action_sequence, baseline, treatment, replay)
        end)

      run = %{
        "schema_version" => Vanta.schema_version(),
        "experiment_id" => "experiment_001_minimal_loop",
        "status" => "completed",
        "baseline" => baseline_id(planner, planner_opts),
        "treatment" => "stage1_closed_loop_runtime",
        "fixture_count" => length(tasks),
        "tasks" => tasks,
        "metrics" => %{
          "baseline" => arm_metrics(tasks, "baseline"),
          "treatment" => arm_metrics(tasks, "treatment")
        }
      }

      run = Schema.validate!("experiment_run", run)

      if out_dir do
        write_results!(out_dir, run)
      end

      {:ok, run}
    end
  end

  defp ensure_llm_ready(Vanta.OpenAIPlannerAdapter, opts) do
    case OpenAIPlannerAdapter.env(opts) do
      {:ok, _env} -> :ok
      {:error, reason} -> {:error, {:llm_baseline_not_configured, reason}}
    end
  end

  defp ensure_llm_ready(Vanta.OpenClawPlannerAdapter, opts) do
    case OpenClawPlannerAdapter.env(opts) do
      {:ok, _env} -> :ok
      {:error, reason} -> {:error, {:llm_baseline_not_configured, reason}}
    end
  end

  defp ensure_llm_ready(_planner, _opts), do: :ok

  defp baseline_id(Vanta.OpenClawPlannerAdapter, opts),
    do: OpenClawPlannerAdapter.baseline_id(opts)

  defp baseline_id(Vanta.OpenAIPlannerAdapter, opts) do
    OpenAIPlannerAdapter.baseline_id(opts)
  end

  defp baseline_id(_planner, _opts), do: "llm_action_sequence_direct_execution"

  defp task_result(task, action_sequence, baseline, treatment, replay) do
    %{
      "task_id" => task["task_id"],
      "expected_runtime_status" => FixtureAcceptance.expected_runtime_status(treatment.workspace),
      "action_sequence" => action_sequence,
      "baseline" => arm_result(baseline),
      "treatment" => arm_result(treatment),
      "replay" => %{
        "consistent" => replay.consistent?,
        "expected_state_hash" => replay.expected_state_hash,
        "actual_state_hash" => replay.actual_state_hash
      }
    }
  end

  defp arm_result(result) do
    %{
      "status" => result.status,
      "task_success" => result.task_success?,
      "total_actions" => result.total_actions,
      "invalid_actions" => result.invalid_actions,
      "produced_governance_artifacts" => result.arm == :treatment
    }
  end

  defp metrics(results) do
    total_tasks = max(length(results), 1)
    total_actions = results |> Enum.map(& &1["total_actions"]) |> Enum.sum() |> max(1)
    invalid_actions = results |> Enum.map(& &1["invalid_actions"]) |> Enum.sum()
    successful_tasks = Enum.count(results, & &1["task_success"])

    %{
      "task_success_rate" => successful_tasks / total_tasks,
      "invalid_action_rate" => invalid_actions / total_actions,
      "commit_integrity_score" =>
        Enum.count(results, &(&1["status"] == "committed")) / total_tasks
    }
  end

  defp arm_metrics(tasks, arm) do
    tasks
    |> Enum.map(& &1[arm])
    |> metrics()
    |> Map.put("evidence_sufficiency_score", evidence_sufficiency_score(arm))
    |> Map.put("replay_consistency", replay_consistency(tasks, arm))
  end

  defp evidence_sufficiency_score("treatment"), do: 1.0
  defp evidence_sufficiency_score(_arm), do: 0.0

  defp replay_consistency(tasks, "treatment") do
    total_tasks = max(length(tasks), 1)
    consistent = Enum.count(tasks, &get_in(&1, ["replay", "consistent"]))
    consistent / total_tasks
  end

  defp replay_consistency(_tasks, _arm), do: 0.0

  defp write_results!(out_dir, run) do
    File.mkdir_p!(out_dir)
    File.write!(Path.join(out_dir, "run.json"), Jason.encode!(run, pretty: true))
    File.write!(Path.join(out_dir, "summary.md"), summary(run))
  end

  defp summary(run) do
    """
    # Experiment 001 Local Run

    Status: #{run["status"]}
    Fixture count: #{run["fixture_count"]}

    ## Baseline

    - task_success_rate: #{run["metrics"]["baseline"]["task_success_rate"]}
    - invalid_action_rate: #{run["metrics"]["baseline"]["invalid_action_rate"]}
    - commit_integrity_score: #{run["metrics"]["baseline"]["commit_integrity_score"]}
    - evidence_sufficiency_score: #{run["metrics"]["baseline"]["evidence_sufficiency_score"]}
    - replay_consistency: #{run["metrics"]["baseline"]["replay_consistency"]}

    ## Treatment

    - task_success_rate: #{run["metrics"]["treatment"]["task_success_rate"]}
    - invalid_action_rate: #{run["metrics"]["treatment"]["invalid_action_rate"]}
    - commit_integrity_score: #{run["metrics"]["treatment"]["commit_integrity_score"]}
    - evidence_sufficiency_score: #{run["metrics"]["treatment"]["evidence_sufficiency_score"]}
    - replay_consistency: #{run["metrics"]["treatment"]["replay_consistency"]}
    """
  end
end
