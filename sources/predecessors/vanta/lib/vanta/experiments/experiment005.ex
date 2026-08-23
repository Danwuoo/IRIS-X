defmodule Vanta.Experiment005 do
  @moduledoc """
  Phase 5 local smoke runner for `Working Set Compiler v0`.
  """

  alias Vanta.{
    OpenClawContextPlannerAdapter,
    RawTraceContextBuilder,
    Runtime,
    Schema,
    WorkingSetCompiler
  }

  @experiment_id "experiment_005_working_set_compiler"

  def run(fixture_root, opts \\ []) do
    out_dir = Keyword.get(opts, :out_dir)
    planner_adapter = Keyword.get(opts, :planner_adapter, OpenClawContextPlannerAdapter)
    planner_opts = Keyword.get(opts, :planner_opts, [])

    with :ok <- ensure_planner_ready(planner_adapter, planner_opts),
         {:ok, tasks} <- run_tasks(fixture_root, planner_adapter, planner_opts, opts) do
      run = %{
        "schema_version" => Vanta.schema_version(),
        "experiment_id" => @experiment_id,
        "status" => "completed",
        "baseline" =>
          "raw_trace_bounded_#{planner_id(planner_adapter, planner_opts)}_matched_budget",
        "treatment" =>
          "working_set_compiler_v0_reference_backed_#{planner_id(planner_adapter, planner_opts)}_matched_budget",
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

  defp run_tasks(fixture_root, planner_adapter, planner_opts, opts) do
    fixture_root
    |> phase5_task_paths()
    |> Enum.reduce_while({:ok, []}, fn task_path, {:ok, tasks} ->
      case run_fixture(task_path, planner_adapter, planner_opts, opts) do
        {:ok, task_result} -> {:cont, {:ok, tasks ++ [task_result]}}
        {:error, reason} -> {:halt, {:error, reason}}
      end
    end)
  end

  defp run_fixture(task_path, planner_adapter, planner_opts, opts) do
    workspace = Path.dirname(task_path)
    task = Schema.load_json!(task_path)
    metadata = working_set_metadata(workspace)
    context_input = context_input(task, metadata, opts)

    baseline_context =
      RawTraceContextBuilder.build(context_input, workspace: workspace)

    with {:ok, treatment_context} <-
           WorkingSetCompiler.compile(context_input, workspace: workspace),
         {:ok, baseline} <-
           run_arm(
             task,
             workspace,
             metadata,
             "baseline",
             baseline_context,
             planner_adapter,
             planner_opts
           ),
         {:ok, treatment} <-
           run_arm(
             task,
             workspace,
             metadata,
             "treatment",
             treatment_context,
             planner_adapter,
             planner_opts
           ) do
      {:ok,
       %{
         "task_id" => task["task_id"],
         "required_refs" => Map.get(metadata, "required_refs", []),
         "relevant_refs" => Map.get(metadata, "relevant_refs", []),
         "irrelevant_refs" => Map.get(metadata, "irrelevant_refs", []),
         "omission_trap_refs" => Map.get(metadata, "omission_trap_refs", []),
         "baseline" => baseline,
         "treatment" => treatment,
         "compute_match" => compute_match?(baseline, treatment)
       }}
    else
      {:error, reason} -> {:error, {:experiment005_fixture_failed, task["task_id"], reason}}
    end
  end

  defp phase5_task_paths(fixture_root) do
    fixture_root
    |> Path.join("*/expected/working_set_acceptance.json")
    |> Path.wildcard()
    |> Enum.map(fn path -> path |> Path.dirname() |> Path.dirname() |> Path.join("task.json") end)
    |> Enum.filter(fn task_path ->
      task_path
      |> Path.dirname()
      |> Path.basename()
      |> String.starts_with?("docops_ws_")
    end)
    |> Enum.sort()
  end

  defp working_set_metadata(workspace) do
    workspace
    |> Path.join("expected/working_set_acceptance.json")
    |> Schema.load_json!()
  end

  defp context_input(task, metadata, opts) do
    metadata
    |> Map.put("task_id", task["task_id"])
    |> Map.put_new("active_goal_ref", "task:#{task["task_id"]}")
    |> maybe_override_context_budget(Keyword.get(opts, :max_context_chars))
  end

  defp maybe_override_context_budget(input, nil), do: input

  defp maybe_override_context_budget(input, max_context_chars) do
    put_in(input, ["budget", "max_context_chars"], max_context_chars)
  end

  defp run_arm(task, workspace, metadata, arm, context_artifact, planner_adapter, planner_opts) do
    with {:ok, plan} <- planner_adapter.plan(task, context_artifact, planner_opts),
         {:ok, runtime} <-
           Runtime.run_task(task, workspace, action_sequence: plan.action_sequence) do
      {:ok,
       %{
         "arm" => arm,
         "status" => runtime.status,
         "task_success" => runtime.task_success?,
         "total_actions" => runtime.total_actions,
         "invalid_actions" => runtime.invalid_actions,
         "unsupported_commit" => unsupported_commit?(runtime),
         "memory_write_count" => memory_write_count(runtime),
         "planner_budget_usage" => plan.budget_usage,
         "context" => compact_context(context_artifact),
         "context_metrics" => context_metrics(context_artifact, metadata, runtime),
         "action_sequence" => plan.action_sequence
       }}
    end
  end

  defp compact_context(%{working_set: working_set} = context) do
    %{
      "type" => "working_set",
      "working_set" => working_set,
      "selected_refs" =>
        context.selected_refs
        |> Enum.map(&Map.take(&1, ["ref_id", "kind", "path", "content_hash"])),
      "omitted_refs" =>
        context.omitted_refs |> Enum.map(&Map.take(&1, ["ref_id", "kind", "path", "omit_reason"]))
    }
  end

  defp compact_context(%{"arm" => "raw_trace_bounded"} = context) do
    Map.take(context, [
      "artifact_id",
      "arm",
      "max_context_chars",
      "selected_context_chars",
      "estimated_tokens",
      "estimation_method",
      "budget_adhered",
      "included_refs",
      "dropped_refs"
    ])
  end

  defp context_metrics(context_artifact, metadata, runtime) do
    included_refs = included_refs(context_artifact)
    included_ids = included_refs |> Enum.map(& &1["ref_id"]) |> MapSet.new()
    required_ids = metadata |> Map.get("required_refs", []) |> MapSet.new()

    relevant_ids =
      metadata
      |> Map.get("relevant_refs", [])
      |> Kernel.++(Map.get(metadata, "required_refs", []))
      |> MapSet.new()

    omitted_required = MapSet.difference(required_ids, included_ids)
    included_count = length(included_refs)

    %{
      "budget_adherent" => budget_adherent?(context_artifact),
      "provenance_completeness" => provenance_completeness(included_refs),
      "context_omission_error_rate" =>
        MapSet.size(omitted_required) / max(MapSet.size(required_ids), 1),
      "working_set_relevance_score" =>
        if included_count == 0 do
          0.0
        else
          Enum.count(included_refs, &MapSet.member?(relevant_ids, &1["ref_id"])) / included_count
        end,
      "long_task_stable" =>
        runtime.task_success? and not unsupported_commit?(runtime) and
          memory_write_count(runtime) == 0
    }
  end

  defp included_refs(%{working_set: working_set}) do
    get_in(working_set, ["provenance", "included_refs"]) || []
  end

  defp included_refs(%{"included_refs" => refs}), do: refs
  defp included_refs(_context_artifact), do: []

  defp budget_adherent?(%{working_set: working_set}) do
    get_in(working_set, ["token_budget", "budget_adhered"]) == true
  end

  defp budget_adherent?(%{"budget_adhered" => budget_adhered}), do: budget_adhered == true
  defp budget_adherent?(_context_artifact), do: false

  defp provenance_completeness([]), do: 0.0

  defp provenance_completeness(refs) do
    complete =
      Enum.count(refs, fn ref ->
        present?(ref["ref_id"]) and present?(ref["source"]) and present?(ref["path"]) and
          present?(ref["content_hash"])
      end)

    complete / length(refs)
  end

  defp metrics(tasks) do
    %{
      "baseline" => arm_metrics(tasks, "baseline"),
      "treatment" => arm_metrics(tasks, "treatment"),
      "compute_matching" => %{
        "budget_matched" => Enum.all?(tasks, & &1["compute_match"]),
        "matched_fixture_count" => Enum.count(tasks, & &1["compute_match"]),
        "fixture_count" => length(tasks)
      },
      "gate" => gate_metrics(tasks)
    }
  end

  defp arm_metrics(tasks, arm) do
    results = Enum.map(tasks, & &1[arm])
    context_metrics = Enum.map(results, & &1["context_metrics"])

    %{
      "working_set_budget_adherence" => rate(context_metrics, "budget_adherent"),
      "working_set_provenance_completeness" => mean(context_metrics, "provenance_completeness"),
      "context_omission_error_rate" => mean(context_metrics, "context_omission_error_rate"),
      "working_set_relevance_score" => mean(context_metrics, "working_set_relevance_score"),
      "long_task_stability" => rate(context_metrics, "long_task_stable"),
      "task_success_rate" => rate(results, "task_success"),
      "unsupported_commits" =>
        results |> Enum.map(&bool_count(&1["unsupported_commit"])) |> Enum.sum(),
      "memory_writes" => results |> Enum.map(& &1["memory_write_count"]) |> Enum.sum(),
      "item_count" => length(results)
    }
  end

  defp gate_metrics(tasks) do
    baseline = arm_metrics(tasks, "baseline")
    treatment = arm_metrics(tasks, "treatment")

    pass? =
      length(tasks) == 5 and
        treatment["working_set_budget_adherence"] == 1.0 and
        treatment["working_set_provenance_completeness"] == 1.0 and
        treatment["context_omission_error_rate"] < baseline["context_omission_error_rate"] and
        treatment["working_set_relevance_score"] > baseline["working_set_relevance_score"] and
        treatment["long_task_stability"] >= baseline["long_task_stability"] and
        treatment["unsupported_commits"] == 0 and
        treatment["memory_writes"] == 0

    %{"local_smoke_pass" => pass?}
  end

  defp rate([], _field), do: 0.0

  defp rate(results, field) do
    Enum.count(results, &(&1[field] == true)) / length(results)
  end

  defp mean([], _field), do: 0.0

  defp mean(results, field) do
    results
    |> Enum.map(&(Map.get(&1, field) || 0.0))
    |> Enum.sum()
    |> Kernel./(length(results))
  end

  defp compute_match?(baseline, treatment) do
    baseline_budget = baseline["planner_budget_usage"]
    treatment_budget = treatment["planner_budget_usage"]

    baseline_budget["max_prompt_chars"] == treatment_budget["max_prompt_chars"] and
      baseline_budget["max_response_chars"] == treatment_budget["max_response_chars"]
  end

  defp unsupported_commit?(runtime),
    do: runtime.status == "committed" and runtime.invalid_actions > 0

  defp memory_write_count(runtime) do
    runtime.journal
    |> Map.get("memory_write_effects", [])
    |> length()
  end

  defp bool_count(true), do: 1
  defp bool_count(_value), do: 0

  defp ensure_planner_ready(adapter, opts) do
    if function_exported?(adapter, :env, 1) do
      case adapter.env(opts) do
        {:ok, _env} -> :ok
        {:error, reason} -> {:error, {:openclaw_context_planner_not_configured, reason}}
        _other -> :ok
      end
    else
      :ok
    end
  end

  defp planner_id(adapter, opts) do
    if function_exported?(adapter, :planner_id, 1) do
      adapter.planner_id(opts)
    else
      "context_planner"
    end
  end

  defp write_results!(out_dir, run) do
    File.mkdir_p!(out_dir)
    File.write!(Path.join(out_dir, "run.json"), Jason.encode!(run, pretty: true))
    File.write!(Path.join(out_dir, "summary.md"), summary(run))
  end

  defp summary(run) do
    """
    # Experiment 005 Local Run

    Status: #{run["status"]}
    Fixture count: #{run["fixture_count"]}
    Baseline: #{run["baseline"]}
    Treatment: #{run["treatment"]}

    ## Baseline

    #{metric_lines(run["metrics"]["baseline"])}

    ## Treatment

    #{metric_lines(run["metrics"]["treatment"])}

    ## Compute Matching

    - budget_matched: #{run["metrics"]["compute_matching"]["budget_matched"]}
    - matched_fixture_count: #{run["metrics"]["compute_matching"]["matched_fixture_count"]}

    ## Gate

    - local_smoke_pass: #{run["metrics"]["gate"]["local_smoke_pass"]}

    Interpretation: this is a Phase 5 local smoke run for `Working Set Compiler
    v0`. It is not validation of full Context OS or H3.
    """
  end

  defp metric_lines(metrics) do
    """
    - working_set_budget_adherence: #{metrics["working_set_budget_adherence"]}
    - working_set_provenance_completeness: #{metrics["working_set_provenance_completeness"]}
    - context_omission_error_rate: #{metrics["context_omission_error_rate"]}
    - working_set_relevance_score: #{metrics["working_set_relevance_score"]}
    - long_task_stability: #{metrics["long_task_stability"]}
    - task_success_rate: #{metrics["task_success_rate"]}
    - unsupported_commits: #{metrics["unsupported_commits"]}
    - memory_writes: #{metrics["memory_writes"]}
    """
  end

  defp present?(value), do: is_binary(value) and String.trim(value) != ""
end
