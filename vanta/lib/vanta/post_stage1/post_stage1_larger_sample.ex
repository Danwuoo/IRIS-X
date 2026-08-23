defmodule Vanta.PostStage1LargerSample do
  @moduledoc """
  Lane A runner for the post-Stage-1 48-fixture larger controlled sample.
  """

  alias Vanta.PostStage1LargerSample.{Parser, PathHelpers, ReportWriter, Validator}

  alias Vanta.{
    BaselineRunner,
    BlindRetryRunner,
    EvaluationHarness,
    Experiment002,
    FixtureAcceptance,
    OpenClawContextPlannerAdapter,
    OpenClawPlannerAdapter,
    OpenClawRecoveryAdapter,
    OpenClawVerifierAdapter,
    RawTraceContextBuilder,
    RecoveryRunner,
    ReplayRunner,
    Runtime,
    Schema,
    WorkingSetCompiler
  }

  @experiment_id "post_stage_1_larger_sample"
  @sample_frame_id "PS1-LA-SAMPLE-002"
  @metric_policy_version "PS1-LA-METRIC-001"
  @default_model "gpt-5.4-mini"
  @default_max_prompt_chars 20_000
  @default_max_response_chars 12_000
  @default_max_action_attempts 6
  @default_max_recovery_attempts 1

  @strata [
    {"traceability_extraction", ~w(
       docops_read_traceability_001
       docops_struct_inspect_001
       docops_ps1_traceability_multisource_001
       docops_ps1_traceability_cross_doc_refs_001
       docops_ps1_traceability_missing_target_001
       docops_ps1_traceability_structured_outline_001
     )},
    {"terminology_consistency", ~w(
       docops_detect_terms_001
       docops_struct_contract_pass_001
       docops_struct_contract_fail_001
       docops_ps1_terms_alias_conflict_001
       docops_ps1_terms_clean_canonical_001
       docops_ps1_terms_contract_inline_001
     )},
    {"simulated_patch_and_diff", ~w(
       docops_simulate_patch_001
       docops_multistep_commit_001
       docops_struct_simulate_md_001
       docops_struct_simulate_json_001
       docops_struct_insert_before_001
       docops_struct_insert_after_001
     )},
    {"reversible_edit_and_commit", ~w(
       docops_reversible_edit_001
       docops_struct_apply_reversible_001
       docops_ps1_reversible_append_section_001
       docops_ps1_reversible_replace_heading_001
       docops_ps1_reversible_json_path_replace_001
       docops_ps1_reversible_patch_multiline_001
     )},
    {"invalid_action_and_path_guard", ~w(
       docops_action_not_allowed_001
       docops_path_escape_001
       docops_struct_path_escape_001
       docops_struct_selector_missing_001
       docops_struct_selector_ambiguous_001
       docops_ps1_invalid_reversible_in_readonly_001
     )},
    {"evidence_and_verifier_challenge", ~w(
       docops_wrong_diff_001
       docops_struct_wrong_diff_001
       docops_struct_simulation_mutation_001
       docops_struct_missing_backup_metadata_001
       docops_ps1_wrong_diff_multiline_001
       docops_ps1_struct_backup_files_dropped_001
     )},
    {"journal_replay_and_recovery", ~w(
       docops_rollback_failure_001
       docops_audit_gap_001
       docops_compensable_action_001
       docops_ps1_recovery_structured_rollback_001
       docops_ps1_recovery_audit_gap_complete_refs_001
       docops_ps1_replay_multistep_structured_commit_001
     )},
    {"working_set_long_context", ~w(
       docops_ws_evidence_packet_001
       docops_ws_irrelevant_context_001
       docops_ws_omission_trap_001
       docops_ws_recovery_context_001
       docops_ws_traceability_long_001
       docops_ps1_ws_structured_edit_context_001
     )}
  ]

  def sample_frame do
    Enum.flat_map(@strata, fn {stratum, ids} ->
      Enum.map(ids, &%{"fixture_id" => &1, "stratum" => stratum})
    end)
  end

  def sample_frame_id, do: @sample_frame_id
  def metric_policy_version, do: @metric_policy_version

  def run(fixture_root, opts \\ []) do
    opts = normalize_opts(opts)

    with :ok <- ensure_openclaw_only_adapters_ready(opts) do
      inventory = Parser.build_inventory(fixture_root, sample_frame(), &label_source/3)

      run =
        if inventory.errors == [] do
          measured_run(fixture_root, inventory.items, opts)
        else
          blocked_run(inventory, opts)
        end

      run =
        run
        |> Map.put("threshold_status", threshold_status(run))

      run = Schema.validate!("experiment_run", run)

      if opts.out_dir do
        ReportWriter.write_results!(opts.out_dir, run, inventory.items)
      end

      {:ok, run}
    end
  end

  def threshold_status(run), do: Validator.threshold_status(run)

  def fixture_hash(workspace), do: PathHelpers.fixture_hash(workspace)

  defp measured_run(fixture_root, inventory, opts) do
    runtime_tasks =
      Enum.map(inventory, &run_runtime_fixture(fixture_root, &1, opts))

    verifier_run = run_verifier_metrics(fixture_root, opts)
    recovery = run_recovery_metrics(fixture_root, inventory, opts)
    working_set = run_working_set_metrics(fixture_root, inventory, opts)

    tasks =
      runtime_tasks
      |> attach_optional_results("recovery", recovery.task_results)
      |> attach_optional_results("working_set", working_set.task_results)

    metrics =
      aggregate_metrics(tasks, verifier_run["metrics"], recovery.metrics, working_set.metrics)

    %{
      "schema_version" => Vanta.schema_version(),
      "experiment_id" => @experiment_id,
      "sample_frame_id" => @sample_frame_id,
      "metric_policy_version" => @metric_policy_version,
      "status" => "completed",
      "baseline" => baseline_label(opts),
      "treatment" => treatment_label(opts),
      "fixture_count" => length(inventory),
      "run_controls" => run_controls(opts),
      "arm_metadata" => arm_metadata(opts),
      "fixture_inventory_ref" => "fixture_inventory.md",
      "tasks" => tasks,
      "metrics" =>
        metrics
        |> Map.put("hard_gates", hard_gate_metrics(tasks, inventory))
        |> Map.put("by_stratum", by_stratum_metrics(tasks))
    }
  end

  defp blocked_run(inventory, opts) do
    %{
      "schema_version" => Vanta.schema_version(),
      "experiment_id" => @experiment_id,
      "sample_frame_id" => @sample_frame_id,
      "metric_policy_version" => @metric_policy_version,
      "status" => "not_run",
      "baseline" => baseline_label(opts),
      "treatment" => treatment_label(opts),
      "fixture_count" => length(inventory.items),
      "run_controls" => run_controls(opts),
      "arm_metadata" => arm_metadata(opts),
      "fixture_inventory_ref" => "fixture_inventory.md",
      "tasks" => [],
      "metrics" => %{
        "baseline" => %{},
        "treatment" => %{},
        "hard_gates" => %{
          "required_artifacts_valid" => false,
          "artifact_errors" => inventory.errors,
          "fixture_count_exact" => length(inventory.items) == 48,
          "strata_complete" => false
        },
        "by_stratum" => %{}
      }
    }
  end

  defp run_runtime_fixture(fixture_root, inventory_item, opts) do
    workspace = Path.join(fixture_root, inventory_item["fixture_id"])
    task = Schema.load_json!(Path.join(workspace, "task.json"))

    case opts.planner_adapter.propose_actions(task, workspace, opts.planner_opts) do
      {:ok, action_sequence} ->
        run_governed_runtime_fixture(task, workspace, inventory_item, action_sequence)

      {:error, reason} ->
        failed_runtime_fixture(
          task,
          inventory_item,
          %{"actions" => []},
          {:planner_adapter, reason}
        )
    end
  end

  defp run_governed_runtime_fixture(task, workspace, inventory_item, action_sequence) do
    with {:ok, baseline} <- BaselineRunner.run_task(task, workspace, action_sequence),
         {:ok, treatment} <- Runtime.run_task(task, workspace, action_sequence: action_sequence) do
      artifacts = %{
        evidence_packets: treatment.evidence_packets,
        verifier_outputs: treatment.verifier_outputs
      }

      audit = EvaluationHarness.audit_result(treatment.journal, artifacts)

      commit_integrity =
        EvaluationHarness.commit_integrity_complete?(treatment.journal, artifacts)

      replay = replay_or_error(task, workspace, treatment.journal, artifacts)

      %{
        "task_id" => task["task_id"],
        "stratum" => inventory_item["stratum"],
        "expected_label_source" => inventory_item["expected_label_source"],
        "expected_runtime_status" => inventory_item["expected_runtime_status"],
        "fixture_hash" => inventory_item["fixture_hash"],
        "action_sequence" => action_sequence,
        "runtime_governance" => %{
          "baseline" => baseline_result(baseline),
          "treatment" => treatment_result(treatment, audit, commit_integrity),
          "replay" => replay_result(replay)
        }
      }
    else
      {:error, reason} ->
        failed_runtime_fixture(
          task,
          inventory_item,
          action_sequence,
          {:runtime_execution, reason}
        )
    end
  end

  defp failed_runtime_fixture(task, inventory_item, action_sequence, reason) do
    %{
      "task_id" => task["task_id"],
      "stratum" => inventory_item["stratum"],
      "expected_label_source" => inventory_item["expected_label_source"],
      "expected_runtime_status" => inventory_item["expected_runtime_status"],
      "fixture_hash" => inventory_item["fixture_hash"],
      "action_sequence" => action_sequence,
      "runtime_governance" => %{
        "baseline" => failed_baseline_result(reason),
        "treatment" => failed_treatment_result(reason),
        "replay" => failed_replay_result(reason)
      }
    }
  end

  defp baseline_result(result) do
    %{
      "status" => result.status,
      "task_success" => result.task_success?,
      "total_actions" => result.total_actions,
      "invalid_actions" => result.invalid_actions,
      "produced_governance_artifacts" => false
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
      "rollback_status" => result.rollback_status,
      "unsupported_commit" => unsupported_commit?(result),
      "memory_write_count" => memory_write_count(result.journal),
      "disallowed_side_effect_count" => disallowed_side_effect_count(result.journal),
      "journal" => result.journal,
      "evidence_packets" => result.evidence_packets,
      "verifier_outputs" => result.verifier_outputs
    }
  end

  defp replay_result({:error, reason}), do: failed_replay_result({:replay, reason})

  defp replay_result(replay) do
    %{
      "consistent" => replay.consistent?,
      "expected_commit_status" => replay.expected_commit_status,
      "actual_commit_status" => replay.actual_commit_status,
      "expected_state_hash" => replay.expected_state_hash,
      "actual_state_hash" => replay.actual_state_hash,
      "expected_step_count" => replay.expected_step_count,
      "actual_step_count" => replay.actual_step_count
    }
  end

  defp replay_or_error(task, workspace, journal, artifacts) do
    case ReplayRunner.replay(task, workspace, journal, artifacts) do
      {:ok, replay} -> replay
      {:error, reason} -> {:error, reason}
    end
  end

  defp failed_baseline_result(reason) do
    %{
      "status" => "planner_error",
      "task_success" => false,
      "total_actions" => 0,
      "invalid_actions" => 1,
      "produced_governance_artifacts" => false,
      "adapter_error" => inspect(reason)
    }
  end

  defp failed_treatment_result(reason) do
    %{
      "status" => "planner_error",
      "task_success" => false,
      "total_actions" => 0,
      "invalid_actions" => 1,
      "produced_governance_artifacts" => false,
      "audit_complete" => false,
      "audit" => %{
        "complete" => false,
        "missing" => ["episode_journal", "evidence_packets", "verifier_outputs"]
      },
      "commit_integrity" => false,
      "rollback_status" => "not_applicable",
      "unsupported_commit" => false,
      "memory_write_count" => 0,
      "disallowed_side_effect_count" => 0,
      "journal" => %{},
      "evidence_packets" => [],
      "verifier_outputs" => [],
      "adapter_error" => inspect(reason)
    }
  end

  defp failed_replay_result(reason) do
    %{
      "consistent" => false,
      "expected_commit_status" => nil,
      "actual_commit_status" => nil,
      "expected_state_hash" => nil,
      "actual_state_hash" => nil,
      "expected_step_count" => 0,
      "actual_step_count" => 0,
      "adapter_error" => inspect(reason)
    }
  end

  defp run_verifier_metrics(fixture_root, opts) do
    {:ok, run} =
      Experiment002.run(fixture_root,
        verifier: opts.verifier_adapter,
        verifier_opts: opts.verifier_opts
      )

    run
  end

  defp run_recovery_metrics(fixture_root, inventory, opts) do
    task_results =
      inventory
      |> Enum.filter(&recovery_fixture?/1)
      |> Enum.map(fn item ->
        workspace = Path.join(fixture_root, item["fixture_id"])
        task = Schema.load_json!(Path.join(workspace, "task.json"))

        {:ok, targeted} =
          RecoveryRunner.run_task(task, workspace,
            recovery_adapter: opts.recovery_adapter,
            recovery_opts: opts.recovery_opts
          )

        {:ok, blind} =
          BlindRetryRunner.run_task(task, workspace, matched_budget: targeted.budget_usage)

        %{
          "task_id" => task["task_id"],
          "expected_failure_labels" => FixtureAcceptance.expected_failure_labels(workspace),
          "expected_recovery_policy" => FixtureAcceptance.expected_recovery_policy(workspace),
          "targeted_recovery" => targeted_recovery_result(targeted),
          "blind_retry" => blind_retry_result(blind),
          "compute_match" => compute_match?(targeted.budget_usage, blind.budget_usage)
        }
      end)

    %{
      task_results: task_results,
      metrics: %{
        "targeted_recovery" => recovery_arm_metrics(task_results, "targeted_recovery"),
        "blind_retry" => recovery_arm_metrics(task_results, "blind_retry"),
        "compute_matching" => %{
          "budget_matched" => Enum.all?(task_results, & &1["compute_match"]),
          "matched_fixture_count" => Enum.count(task_results, & &1["compute_match"]),
          "fixture_count" => length(task_results)
        }
      }
    }
  end

  defp run_working_set_metrics(fixture_root, inventory, opts) do
    task_results =
      inventory
      |> Enum.filter(&working_set_fixture?/1)
      |> Enum.map(fn item ->
        run_working_set_fixture(fixture_root, item, opts)
      end)

    %{
      task_results: task_results,
      metrics: %{
        "baseline" => working_set_arm_metrics(task_results, "baseline"),
        "treatment" => working_set_arm_metrics(task_results, "treatment"),
        "compute_matching" => %{
          "budget_matched" => Enum.all?(task_results, & &1["compute_match"]),
          "matched_fixture_count" => Enum.count(task_results, & &1["compute_match"]),
          "fixture_count" => length(task_results)
        }
      }
    }
  end

  defp run_working_set_fixture(fixture_root, item, opts) do
    workspace = Path.join(fixture_root, item["fixture_id"])
    task = Schema.load_json!(Path.join(workspace, "task.json"))
    metadata = Schema.load_json!(Path.join(workspace, "expected/working_set_acceptance.json"))

    context_input =
      metadata
      |> Map.put("task_id", task["task_id"])
      |> Map.put_new("active_goal_ref", "task:#{task["task_id"]}")
      |> maybe_override_context_budget(opts.max_context_chars)

    baseline_context = RawTraceContextBuilder.build(context_input, workspace: workspace)
    {:ok, treatment_context} = WorkingSetCompiler.compile(context_input, workspace: workspace)

    {:ok, baseline} =
      run_context_arm(task, workspace, metadata, baseline_context, "baseline", opts)

    {:ok, treatment} =
      run_context_arm(task, workspace, metadata, treatment_context, "treatment", opts)

    %{
      "task_id" => task["task_id"],
      "baseline" => baseline,
      "treatment" => treatment,
      "required_refs" => Map.get(metadata, "required_refs", []),
      "relevant_refs" => Map.get(metadata, "relevant_refs", []),
      "irrelevant_refs" => Map.get(metadata, "irrelevant_refs", []),
      "compute_match" => context_compute_match?(baseline, treatment)
    }
  end

  defp run_context_arm(task, workspace, metadata, context_artifact, arm, opts) do
    case opts.context_planner_adapter.plan(task, context_artifact, opts.context_planner_opts) do
      {:ok, plan} ->
        case Runtime.run_task(task, workspace, action_sequence: plan.action_sequence) do
          {:ok, runtime} ->
            {:ok,
             %{
               "arm" => arm,
               "status" => runtime.status,
               "task_success" => runtime.task_success?,
               "total_actions" => runtime.total_actions,
               "invalid_actions" => runtime.invalid_actions,
               "unsupported_commit" => unsupported_commit?(runtime),
               "memory_write_count" => memory_write_count(runtime.journal),
               "planner_budget_usage" => plan.budget_usage,
               "context" => compact_context(context_artifact),
               "context_metrics" => context_metrics(context_artifact, metadata, runtime),
               "action_sequence" => plan.action_sequence
             }}

          {:error, reason} ->
            {:ok,
             failed_context_arm(arm, context_artifact, metadata, {:runtime_execution, reason})}
        end

      {:error, reason} ->
        {:ok,
         failed_context_arm(arm, context_artifact, metadata, {:context_planner_adapter, reason})}
    end
  end

  defp failed_context_arm(arm, context_artifact, metadata, reason) do
    runtime = %{
      task_success?: false,
      status: "planner_error",
      invalid_actions: 1,
      journal: %{"memory_write_effects" => [], "steps" => []}
    }

    %{
      "arm" => arm,
      "status" => "planner_error",
      "task_success" => false,
      "total_actions" => 0,
      "invalid_actions" => 1,
      "unsupported_commit" => false,
      "memory_write_count" => 0,
      "planner_budget_usage" => %{},
      "context" => compact_context(context_artifact),
      "context_metrics" => context_metrics(context_artifact, metadata, runtime),
      "action_sequence" => %{"actions" => []},
      "adapter_error" => inspect(reason)
    }
  end

  defp aggregate_metrics(tasks, verifier_metrics, recovery_metrics, working_set_metrics) do
    baseline =
      tasks
      |> runtime_arm_metrics("baseline")
      |> Map.merge(verifier_metrics["raw_trace"] || %{})
      |> Map.merge(recovery_metrics["blind_retry"] || %{})
      |> Map.merge(working_set_policy_metrics(working_set_metrics["baseline"] || %{}))

    treatment =
      tasks
      |> runtime_arm_metrics("treatment")
      |> Map.merge(verifier_metrics["structured_evidence_packet"] || %{})
      |> Map.merge(recovery_metrics["targeted_recovery"] || %{})
      |> Map.merge(working_set_policy_metrics(working_set_metrics["treatment"] || %{}))

    %{
      "baseline" => baseline,
      "treatment" => treatment,
      "verifier" => verifier_metrics,
      "recovery" => recovery_metrics,
      "working_set" => working_set_metrics
    }
  end

  defp working_set_policy_metrics(metrics) do
    Map.take(metrics, [
      "working_set_budget_adherence",
      "working_set_provenance_completeness",
      "context_omission_error_rate",
      "working_set_relevance_score",
      "long_task_stability"
    ])
  end

  defp runtime_arm_metrics(tasks, arm) do
    results = Enum.map(tasks, &get_in(&1, ["runtime_governance", arm]))
    total = max(length(results), 1)
    total_actions = results |> Enum.map(&(&1["total_actions"] || 0)) |> Enum.sum() |> max(1)
    invalid_actions = results |> Enum.map(&(&1["invalid_actions"] || 0)) |> Enum.sum()

    committed =
      if arm == "treatment" do
        Enum.filter(results, &(&1["status"] == "committed"))
      else
        []
      end

    %{
      "task_success_rate" => Enum.count(results, & &1["task_success"]) / total,
      "invalid_action_rate" => invalid_actions / total_actions,
      "commit_integrity_score" =>
        if(committed == [],
          do: 0.0,
          else: Enum.count(committed, & &1["commit_integrity"]) / length(committed)
        ),
      "replay_consistency" =>
        if(arm == "treatment",
          do:
            Enum.count(tasks, &get_in(&1, ["runtime_governance", "replay", "consistent"])) /
              total,
          else: 0.0
        ),
      "audit_completeness" =>
        if(arm == "treatment", do: Enum.count(results, & &1["audit_complete"]) / total, else: 0.0),
      "unsupported_commits" =>
        results |> Enum.map(&bool_count(&1["unsupported_commit"])) |> Enum.sum(),
      "memory_writes" => results |> Enum.map(&(&1["memory_write_count"] || 0)) |> Enum.sum(),
      "disallowed_side_effect_classes" =>
        results |> Enum.map(&(&1["disallowed_side_effect_count"] || 0)) |> Enum.sum(),
      "item_count" => length(results)
    }
  end

  defp by_stratum_metrics(tasks) do
    tasks
    |> Enum.group_by(& &1["stratum"])
    |> Map.new(fn {stratum, stratum_tasks} ->
      {stratum,
       %{
         "fixture_count" => length(stratum_tasks),
         "baseline" => runtime_arm_metrics(stratum_tasks, "baseline"),
         "treatment" => runtime_arm_metrics(stratum_tasks, "treatment")
       }}
    end)
  end

  defp hard_gate_metrics(tasks, inventory) do
    treatment_metrics = runtime_arm_metrics(tasks, "treatment")
    artifact_errors = artifact_errors(tasks)

    %{
      "unsupported_commits" => treatment_metrics["unsupported_commits"],
      "memory_writes" => treatment_metrics["memory_writes"],
      "disallowed_side_effect_classes" => treatment_metrics["disallowed_side_effect_classes"],
      "required_artifacts_valid" => artifact_errors == [],
      "artifact_errors" => artifact_errors,
      "arm_identity_compliant" => true,
      "fixture_count_exact" => length(inventory) == 48,
      "strata_complete" => strata_complete?(inventory)
    }
  end

  defp artifact_errors(tasks) do
    Enum.flat_map(tasks, fn task ->
      treatment = get_in(task, ["runtime_governance", "treatment"]) || %{}

      if treatment["produced_governance_artifacts"] == false do
        [
          "#{task["task_id"]}: missing runtime governance artifacts after #{treatment["status"]} #{treatment["adapter_error"]}"
        ]
      else
        []
      end
    end)
  end

  defp recovery_arm_metrics([], _arm) do
    %{
      "recovery_success_rate" => 0.0,
      "targeted_recovery_success" => 0.0,
      "failure_label_accuracy" => 0.0,
      "repeated_failure_rate" => 0.0,
      "item_count" => 0
    }
  end

  defp recovery_arm_metrics(tasks, arm) do
    results = Enum.map(tasks, & &1[arm])

    %{
      "recovery_success_rate" => rate(results, "recovery_success"),
      "targeted_recovery_success" => rate(results, "targeted_recovery_success"),
      "failure_label_accuracy" => rate(results, "failure_label_accuracy"),
      "repeated_failure_rate" => rate(results, "repeated_failure"),
      "item_count" => length(results)
    }
  end

  defp working_set_arm_metrics([], _arm) do
    %{
      "working_set_budget_adherence" => 0.0,
      "working_set_provenance_completeness" => 0.0,
      "context_omission_error_rate" => 1.0,
      "working_set_relevance_score" => 0.0,
      "long_task_stability" => 0.0,
      "task_success_rate" => 0.0,
      "unsupported_commits" => 0,
      "memory_writes" => 0,
      "item_count" => 0
    }
  end

  defp working_set_arm_metrics(tasks, arm) do
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

  defp targeted_recovery_result(result) do
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

  defp blind_retry_result(result) do
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

  defp attach_optional_results(tasks, key, optional_results) do
    by_id = Map.new(optional_results, &{&1["task_id"], &1})

    Enum.map(tasks, fn task ->
      case Map.fetch(by_id, task["task_id"]) do
        {:ok, result} -> Map.put(task, key, result)
        :error -> task
      end
    end)
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
        if(included_count == 0,
          do: 0.0,
          else:
            Enum.count(included_refs, &MapSet.member?(relevant_ids, &1["ref_id"])) /
              included_count
        ),
      "long_task_stable" =>
        runtime.task_success? and not unsupported_commit?(runtime) and
          memory_write_count(runtime.journal) == 0
    }
  end

  defp included_refs(%{working_set: working_set}),
    do: get_in(working_set, ["provenance", "included_refs"]) || []

  defp included_refs(%{"included_refs" => refs}), do: refs
  defp included_refs(_context_artifact), do: []

  defp budget_adherent?(%{working_set: working_set}),
    do: get_in(working_set, ["token_budget", "budget_adhered"]) == true

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

  defp run_controls(opts) do
    %{
      "model_identity" => opts.model_identity,
      "harness_identity" => "openclaw_agent_local",
      "planner_adapter" => inspect(opts.planner_adapter),
      "verifier_adapter" => inspect(opts.verifier_adapter),
      "recovery_adapter" => inspect(opts.recovery_adapter),
      "context_planner_adapter" => inspect(opts.context_planner_adapter),
      "allowed_action_set" => Vanta.action_types(),
      "prompt_template_version" =>
        "post_stage_1_larger_sample_openclaw_v5_ws_evidence_packet_acceptance_alignment",
      "response_format" => "json_only",
      "prompt_character_budget" => opts.max_prompt_chars,
      "response_character_budget" => opts.max_response_chars,
      "action_attempt_limit" => opts.max_action_attempts,
      "recovery_attempt_limit" => opts.max_recovery_attempts,
      "context_budget" => opts.max_context_chars,
      "compute_matching_rule" =>
        "matched OpenClaw model, prompt ceiling, response ceiling, and action/recovery attempt ceilings within each compared arm family",
      "baseline_arm_labels" => [
        baseline_label(opts),
        recovery_baseline_label(opts),
        context_baseline_label(opts)
      ],
      "treatment_arm_labels" => [
        treatment_label(opts),
        recovery_treatment_label(opts),
        context_treatment_label(opts)
      ]
    }
  end

  defp arm_metadata(opts) do
    %{
      "baseline" => %{
        "arm_label" => baseline_label(opts),
        "arm_family" => "OpenClaw direct execution baseline",
        "model_identifier" => opts.model_identity,
        "harness_identifier" => "openclaw_agent_local",
        "adapter_module" => inspect(opts.planner_adapter),
        "pure_model_only" => false
      },
      "treatment" => %{
        "arm_label" => treatment_label(opts),
        "arm_family" => "Vanta governed execution treatment",
        "model_identifier" => opts.model_identity,
        "harness_identifier" => "openclaw_agent_local",
        "adapter_module" => inspect(opts.planner_adapter),
        "pure_model_only" => false
      },
      "verifier" => %{
        "baseline_arm_label" => verifier_baseline_label(opts),
        "treatment_arm_label" => verifier_treatment_label(opts),
        "adapter_module" => inspect(opts.verifier_adapter),
        "label_source" => "automated_structural_or_fixture_oracle"
      },
      "recovery" => %{
        "baseline_arm_label" => recovery_baseline_label(opts),
        "treatment_arm_label" => recovery_treatment_label(opts),
        "adapter_module" => inspect(opts.recovery_adapter),
        "compute_matching" => "matched_budget"
      },
      "working_set" => %{
        "baseline_arm_label" => context_baseline_label(opts),
        "treatment_arm_label" => context_treatment_label(opts),
        "adapter_module" => inspect(opts.context_planner_adapter),
        "scope" => "Working Set Compiler v0 only"
      }
    }
  end

  defp normalize_opts(opts) do
    model = Keyword.get(opts, :model, @default_model)
    max_prompt_chars = Keyword.get(opts, :max_prompt_chars, @default_max_prompt_chars)
    max_response_chars = Keyword.get(opts, :max_response_chars, @default_max_response_chars)
    max_action_attempts = Keyword.get(opts, :max_action_attempts, @default_max_action_attempts)

    max_recovery_attempts =
      Keyword.get(opts, :max_recovery_attempts, @default_max_recovery_attempts)

    base_adapter_opts =
      compact_opts(
        model: model,
        openclaw_dir: Keyword.get(opts, :openclaw_dir),
        agent: Keyword.get(opts, :openclaw_agent),
        timeout_seconds: Keyword.get(opts, :openclaw_timeout_seconds),
        thinking: Keyword.get(opts, :openclaw_thinking),
        max_prompt_chars: max_prompt_chars,
        max_response_chars: max_response_chars,
        max_action_attempts: max_action_attempts
      )

    %{
      out_dir: Keyword.get(opts, :out_dir),
      model: model,
      model_identity: normalize_model(model),
      max_prompt_chars: max_prompt_chars,
      max_response_chars: max_response_chars,
      max_action_attempts: max_action_attempts,
      max_recovery_attempts: max_recovery_attempts,
      max_context_chars: Keyword.get(opts, :max_context_chars),
      planner_adapter: Keyword.get(opts, :planner_adapter, OpenClawPlannerAdapter),
      verifier_adapter: Keyword.get(opts, :verifier_adapter, OpenClawVerifierAdapter),
      recovery_adapter: Keyword.get(opts, :recovery_adapter, OpenClawRecoveryAdapter),
      context_planner_adapter:
        Keyword.get(opts, :context_planner_adapter, OpenClawContextPlannerAdapter),
      planner_opts: Keyword.get(opts, :planner_opts, base_adapter_opts),
      verifier_opts: Keyword.get(opts, :verifier_opts, base_adapter_opts),
      recovery_opts:
        Keyword.get(
          opts,
          :recovery_opts,
          Keyword.put(base_adapter_opts, :max_action_attempts, max_recovery_attempts)
        ),
      context_planner_opts: Keyword.get(opts, :context_planner_opts, base_adapter_opts)
    }
  end

  defp ensure_openclaw_only_adapters_ready(opts) do
    [
      {:planner, opts.planner_adapter, opts.planner_opts},
      {:verifier, opts.verifier_adapter, opts.verifier_opts},
      {:recovery, opts.recovery_adapter, opts.recovery_opts},
      {:context_planner, opts.context_planner_adapter, opts.context_planner_opts}
    ]
    |> Enum.reduce_while(:ok, fn {role, adapter, adapter_opts}, :ok ->
      if function_exported?(adapter, :env, 1) do
        case adapter.env(adapter_opts) do
          {:ok, _env} -> {:cont, :ok}
          {:error, reason} -> {:halt, {:error, {:openclaw_adapter_not_configured, role, reason}}}
          _other -> {:cont, :ok}
        end
      else
        {:cont, :ok}
      end
    end)
  end

  defp compact_opts(opts) do
    Enum.reject(opts, fn {_key, value} -> is_nil(value) end)
  end

  defp normalize_model("openai-codex/" <> _rest = model), do: model
  defp normalize_model(model), do: "openai-codex/#{model}"

  defp baseline_label(opts), do: "openclaw_agent_local/#{opts.model_identity}_lane_a_baselines"

  defp treatment_label(opts),
    do: "vanta_runtime/openclaw_agent_local/#{opts.model_identity}_lane_a_governed_execution"

  defp verifier_baseline_label(opts),
    do: "openclaw_agent_local/#{opts.model_identity}_raw_trace_verifier"

  defp verifier_treatment_label(opts),
    do: "openclaw_agent_local/#{opts.model_identity}_structured_evidence_packet_verifier"

  defp recovery_baseline_label(opts),
    do: "blind_retry_openclaw_agent_local/#{opts.model_identity}_matched_budget"

  defp recovery_treatment_label(opts),
    do: "targeted_recovery_openclaw_agent_local/#{opts.model_identity}_matched_budget"

  defp context_baseline_label(opts),
    do: "raw_trace_bounded_openclaw_agent_local/#{opts.model_identity}_matched_budget"

  defp context_treatment_label(opts),
    do:
      "working_set_compiler_v0_reference_backed_openclaw_agent_local/#{opts.model_identity}_matched_budget"

  defp label_source(fixture_id, acceptance, workspace) do
    cond do
      File.exists?(Path.join(workspace, "expected/working_set_acceptance.json")) ->
        "fixture_oracle"

      Map.get(acceptance, "expected_failure_labels", []) != [] ->
        "fixture_oracle"

      String.contains?(fixture_id, "wrong_diff") or
        String.contains?(fixture_id, "selector") or
        String.contains?(fixture_id, "path_escape") or
        String.contains?(fixture_id, "backup") or
          String.contains?(fixture_id, "simulation_mutation") ->
        "fixture_oracle"

      true ->
        "automated_structural"
    end
  end

  defp recovery_fixture?(item) do
    item["workspace"]
    |> FixtureAcceptance.expected_recovery_policy()
    |> is_binary()
  end

  defp working_set_fixture?(item) do
    File.exists?(Path.join(item["workspace"], "expected/working_set_acceptance.json"))
  end

  defp maybe_override_context_budget(input, nil), do: input

  defp maybe_override_context_budget(input, max_context_chars) do
    put_in(input, ["budget", "max_context_chars"], max_context_chars)
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

  defp context_compute_match?(baseline, treatment) do
    baseline_budget = baseline["planner_budget_usage"]
    treatment_budget = treatment["planner_budget_usage"]

    is_map(baseline_budget) and is_map(treatment_budget) and
      baseline_budget["max_prompt_chars"] == treatment_budget["max_prompt_chars"] and
      baseline_budget["max_response_chars"] == treatment_budget["max_response_chars"]
  end

  defp unsupported_commit?(runtime),
    do: runtime.status == "committed" and runtime.invalid_actions > 0

  defp memory_write_count(journal) do
    journal
    |> Map.get("memory_write_effects", [])
    |> length()
  end

  defp disallowed_side_effect_count(journal) do
    journal
    |> Map.get("steps", [])
    |> Enum.count(&(&1["side_effect_class"] in ~w(COMMITTABLE IRREVERSIBLE MEMORY_WRITE)))
  end

  defp strata_complete?(inventory) do
    Enum.all?(@strata, fn {stratum, _ids} ->
      Enum.count(inventory, &(&1["stratum"] == stratum)) == 6
    end)
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

  defp bool_count(true), do: 1
  defp bool_count(_value), do: 0

  defp present?(value), do: is_binary(value) and String.trim(value) != ""
end
