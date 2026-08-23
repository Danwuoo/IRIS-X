defmodule Vanta.Experiment003 do
  @moduledoc """
  Local Experiment 003 runner for Episode Journal audit and replay checks.
  """

  alias Vanta.{
    BaselineRunner,
    EvaluationHarness,
    FixtureAcceptance,
    ReplayRunner,
    Runtime,
    Schema
  }

  def run(fixture_root, opts \\ []) do
    out_dir = Keyword.get(opts, :out_dir)

    tasks =
      fixture_root
      |> Path.join("*/task.json")
      |> Path.wildcard()
      |> Enum.sort()
      |> Enum.map(fn task_path ->
        workspace = Path.dirname(task_path)
        task = Schema.load_json!(task_path)

        {:ok, action_sequence} = FixtureAcceptance.action_sequence(workspace)
        {:ok, baseline} = BaselineRunner.run_task(task, workspace, action_sequence)
        {:ok, treatment} = Runtime.run_task(task, workspace, action_sequence: action_sequence)

        artifacts = %{
          evidence_packets: treatment.evidence_packets,
          verifier_outputs: treatment.verifier_outputs
        }

        audit = EvaluationHarness.audit_result(treatment.journal, artifacts)

        commit_integrity =
          EvaluationHarness.commit_integrity_complete?(treatment.journal, artifacts)

        {:ok, replay} = ReplayRunner.replay(task, workspace, treatment.journal, artifacts)

        task_result(
          task,
          workspace,
          action_sequence,
          baseline,
          treatment,
          audit,
          commit_integrity,
          replay
        )
      end)

    run = %{
      "schema_version" => Vanta.schema_version(),
      "experiment_id" => "experiment_003_commit_journal",
      "status" => "completed",
      "baseline" => "tool_trace_only_direct_execution",
      "treatment" => "stage1_episode_journal_replay_runtime",
      "fixture_count" => length(tasks),
      "tasks" => tasks,
      "metrics" => %{
        "baseline" => baseline_metrics(tasks),
        "treatment" => treatment_metrics(tasks)
      }
    }

    run = Schema.validate!("experiment_run", run)

    if out_dir do
      write_results!(out_dir, run)
    end

    {:ok, run}
  end

  defp task_result(
         task,
         workspace,
         action_sequence,
         baseline,
         treatment,
         audit,
         commit_integrity,
         replay
       ) do
    %{
      "task_id" => task["task_id"],
      "expected_runtime_status" => FixtureAcceptance.expected_runtime_status(workspace),
      "action_sequence" => action_sequence,
      "baseline" => baseline_result(baseline),
      "treatment" => treatment_result(treatment, audit, commit_integrity),
      "replay" => replay_result(replay)
    }
  end

  defp baseline_result(result) do
    %{
      "status" => result.status,
      "task_success" => result.task_success?,
      "total_actions" => result.total_actions,
      "invalid_actions" => result.invalid_actions,
      "produced_governance_artifacts" => false,
      "audit_complete" => false,
      "replay_consistent" => false,
      "commit_integrity" => false
    }
  end

  defp treatment_result(result, audit, commit_integrity) do
    %{
      "status" => result.status,
      "task_success" => result.task_success?,
      "total_actions" => result.total_actions,
      "invalid_actions" => result.invalid_actions,
      "produced_governance_artifacts" => true,
      "audit_complete" => audit["complete"],
      "audit" => audit,
      "commit_integrity" => commit_integrity,
      "journal" => result.journal,
      "evidence_packets" => result.evidence_packets,
      "verifier_outputs" => result.verifier_outputs
    }
  end

  defp replay_result(replay) do
    %{
      "consistent" => replay.consistent?,
      "expected_commit_status" => replay.expected_commit_status,
      "actual_commit_status" => replay.actual_commit_status,
      "expected_state_hash" => replay.expected_state_hash,
      "actual_state_hash" => replay.actual_state_hash,
      "expected_step_count" => replay.expected_step_count,
      "actual_step_count" => replay.actual_step_count,
      "status_match" => replay.status_match?,
      "state_hash_match" => replay.state_hash_match?,
      "step_count_match" => replay.step_count_match?
    }
  end

  defp baseline_metrics(tasks) do
    results = Enum.map(tasks, & &1["baseline"])

    %{
      "commit_integrity_score" => 0.0,
      "replay_consistency" => 0.0,
      "audit_completeness" => 0.0,
      "invalid_action_rate" => invalid_action_rate(results)
    }
  end

  defp treatment_metrics(tasks) do
    results = Enum.map(tasks, & &1["treatment"])
    committed = Enum.filter(results, &(&1["status"] == "committed"))
    committed_total = length(committed)

    commit_integrity_score =
      if committed_total == 0 do
        0.0
      else
        Enum.count(committed, & &1["commit_integrity"]) / committed_total
      end

    %{
      "commit_integrity_score" => commit_integrity_score,
      "replay_consistency" =>
        Enum.count(tasks, &get_in(&1, ["replay", "consistent"])) / max(length(tasks), 1),
      "audit_completeness" =>
        Enum.count(results, & &1["audit_complete"]) / max(length(results), 1),
      "invalid_action_rate" => invalid_action_rate(results)
    }
  end

  defp invalid_action_rate(results) do
    total_actions = results |> Enum.map(& &1["total_actions"]) |> Enum.sum() |> max(1)
    invalid_actions = results |> Enum.map(& &1["invalid_actions"]) |> Enum.sum()
    invalid_actions / total_actions
  end

  defp write_results!(out_dir, run) do
    File.mkdir_p!(out_dir)
    File.write!(Path.join(out_dir, "run.json"), Jason.encode!(run, pretty: true))
    File.write!(Path.join(out_dir, "summary.md"), summary(run))
  end

  defp summary(run) do
    """
    # Experiment 003 Local Run

    Status: #{run["status"]}
    Fixture count: #{run["fixture_count"]}
    Baseline: #{run["baseline"]}
    Treatment: #{run["treatment"]}

    ## Baseline

    - commit_integrity_score: #{run["metrics"]["baseline"]["commit_integrity_score"]}
    - replay_consistency: #{run["metrics"]["baseline"]["replay_consistency"]}
    - audit_completeness: #{run["metrics"]["baseline"]["audit_completeness"]}
    - invalid_action_rate: #{run["metrics"]["baseline"]["invalid_action_rate"]}

    ## Treatment

    - commit_integrity_score: #{run["metrics"]["treatment"]["commit_integrity_score"]}
    - replay_consistency: #{run["metrics"]["treatment"]["replay_consistency"]}
    - audit_completeness: #{run["metrics"]["treatment"]["audit_completeness"]}
    - invalid_action_rate: #{run["metrics"]["treatment"]["invalid_action_rate"]}

    Interpretation: this is a local smoke run for journal audit and replay
    pipeline stability over the current fixture set. It must not be described as
    validation of H5.
    """
  end
end
