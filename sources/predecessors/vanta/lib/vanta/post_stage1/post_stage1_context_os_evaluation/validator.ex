defmodule Vanta.PostStage1ContextOSEvaluation.Validator do
  @moduledoc false

  alias Vanta.PostStage1ContextOSEvaluation.PathHelpers
  alias Vanta.{Hash, PostStage1LaneBLabelResults, PostStage1LaneBPacket}

  @source_run_id "20260601_113121"
  @plan_id "PS1-LC-CTX-PLAN-001"
  @gate_policy "PS1-LC-CTX-GATE-001"
  @metric_policy "PS1-LA-METRIC-001"
  @label_policy "PS1-LB-LABEL-001"
  @sample_frame "PS1-LA-SAMPLE-002"
  @packet_id "PS1-LB-PACKET-20260601-113121-BATCH-001"
  @attestation_id "PS1-LC-CTX-CONTROL-ATTEST-001"

  @model "openai-codex/gpt-5.4-mini"
  @harness "openclaw_agent_local"
  @context_adapter "Vanta.OpenClawContextPlannerAdapter"
  @openclaw_agent "vanta-verifier"
  @baseline_arm "raw_trace_bounded_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget"
  @treatment_arm "working_set_compiler_v0_reference_backed_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget"

  @fixture_budgets %{
    "docops_ws_evidence_packet_001" => 260,
    "docops_ws_irrelevant_context_001" => 240,
    "docops_ws_omission_trap_001" => 250,
    "docops_ws_recovery_context_001" => 270,
    "docops_ws_traceability_long_001" => 280,
    "docops_ps1_ws_structured_edit_context_001" => 320
  }

  @lane_a_expected %{
    "baseline" => %{
      "working_set_budget_adherence" => 1.0,
      "working_set_provenance_completeness" => 2 / 3,
      "context_omission_error_rate" => 7 / 9,
      "working_set_relevance_score" => 13 / 60,
      "long_task_stability" => 1.0
    },
    "treatment" => %{
      "working_set_budget_adherence" => 1.0,
      "working_set_provenance_completeness" => 1.0,
      "context_omission_error_rate" => 0.0,
      "working_set_relevance_score" => 29 / 30,
      "long_task_stability" => 1.0
    }
  }

  @lane_b_expected %{
    "context_arm_A" => %{
      "context_omission_error_rate" => {14, 19, "0.7368"},
      "working_set_relevance_score" => {5, 11, "0.4545"}
    },
    "context_arm_B" => %{
      "context_omission_error_rate" => {0, 19, "0.0000"},
      "working_set_relevance_score" => {19, 20, "0.9500"}
    },
    "Combined" => %{
      "context_omission_error_rate" => {14, 38, "0.3684"},
      "working_set_relevance_score" => {24, 31, "0.7742"}
    }
  }

  def expected_fixture_budgets, do: @fixture_budgets
  def expected_baseline_arm, do: @baseline_arm
  def expected_treatment_arm, do: @treatment_arm
  def source_run_id, do: @source_run_id

  def validate(config, sources) do
    {lane_a_errors, lane_a} = validate_lane_a(config, sources)
    {lane_b_errors, lane_b} = validate_lane_b(config, sources)

    errors =
      []
      |> validate_policy_sources(sources)
      |> validate_control_attestation(config, sources)
      |> validate_run_controls(config, sources)
      |> validate_source_identity(config, sources)
      |> Kernel.++(lane_a_errors)
      |> Kernel.++(lane_b_errors)
      |> Enum.uniq()

    if errors == [] do
      {:ok,
       %{
         lane_a: lane_a,
         lane_b: lane_b,
         controls: control_summary(sources),
         process_integrity_floors: process_integrity_floors(sources.run),
         interpretation_boundaries: interpretation_boundaries()
       }}
    else
      {:error, errors}
    end
  end

  defp validate_policy_sources(errors, sources) do
    errors
    |> require_text("evaluation plan ID", sources.evaluation_plan, "Plan ID: `#{@plan_id}`")
    |> require_text(
      "evaluation plan gate policy",
      sources.evaluation_plan,
      "Gate policy version: `#{@gate_policy}`"
    )
    |> require_text("context gate policy", sources.gate, "Gate policy ID: `#{@gate_policy}`")
    |> require_text("metric policy", sources.metric_policy, "Policy ID: `#{@metric_policy}`")
    |> require_text("label policy", sources.label_policy, "Policy ID: `#{@label_policy}`")
    |> require_text(
      "baseline identity plan",
      sources.baseline_plan,
      "Plan ID: `PS1-LA-BASELINE-001`"
    )
    |> require_text(
      "baseline arm policy",
      sources.baseline_plan,
      "raw_trace_bounded_openclaw_agent_local/<model>_matched_budget"
    )
    |> require_text(
      "treatment arm policy",
      sources.baseline_plan,
      "working_set_compiler_v0_reference_backed_openclaw_agent_local/<model>_matched_budget"
    )
    |> require_text(
      "working-set schema title",
      sources.working_set_schema_text,
      "\"title\": \"Working Set\""
    )
  end

  defp validate_control_attestation(errors, config, sources) do
    attestation = sources.attestation
    adapter = sources.adapter_source

    errors
    |> require_equal("attestation ID", attestation["attestation_id"], @attestation_id)
    |> require_equal(
      "attestation type",
      attestation["attestation_type"],
      "coordinator_control_attestation"
    )
    |> require_equal("attestation source run", attestation["source_run"], @source_run_id)
    |> require_equal(
      "attestation source_run_native_metadata",
      attestation["source_run_native_metadata"],
      false
    )
    |> require_equal(
      "attestation scope",
      attestation["scope"],
      "artifact_backed_post_freeze_evaluation_only"
    )
    |> require_equal(
      "attested OpenClaw agent",
      get_in(attestation, ["controls", "openclaw_agent"]),
      @openclaw_agent
    )
    |> require_equal(
      "attested tool policy",
      get_in(attestation, ["controls", "tool_policy"]),
      "embedded_context_only"
    )
    |> require_equal(
      "attested adapter source path",
      get_in(attestation, ["adapter_policy_source", "path"]),
      PathHelpers.display_path(config.adapter_source, config.cwd)
    )
    |> require_equal(
      "attested adapter source hash",
      get_in(attestation, ["adapter_policy_source", "sha256"]),
      Hash.file_hash(config.adapter_source)
    )
    |> validate_adapter_policy_fragments(
      adapter,
      get_in(attestation, ["adapter_policy_source", "required_policy_fragments"])
    )
  end

  defp validate_adapter_policy_fragments(errors, _adapter, fragments) when not is_list(fragments),
    do: ["attestation adapter policy fragments must be a list" | errors]

  defp validate_adapter_policy_fragments(errors, adapter, fragments) do
    Enum.reduce(fragments, errors, fn fragment, acc ->
      require_text(acc, "adapter embedded-context-only policy", adapter, fragment)
    end)
  end

  defp validate_source_identity(errors, config, sources) do
    run = sources.run
    manifest = sources.packet_manifest

    errors
    |> require_equal(
      "source run directory ID",
      config.source_run |> Path.dirname() |> Path.basename(),
      @source_run_id
    )
    |> require_equal("source experiment ID", run["experiment_id"], "post_stage_1_larger_sample")
    |> require_equal("source sample frame", run["sample_frame_id"], @sample_frame)
    |> require_equal("source metric policy", run["metric_policy_version"], @metric_policy)
    |> require_equal("source run status", run["status"], "completed")
    |> require_equal(
      "source threshold status",
      run["threshold_status"],
      "pass_acceptance_candidate"
    )
    |> require_equal("source fixture_count", run["fixture_count"], 48)
    |> require_equal("source task count", length(run["tasks"] || []), 48)
    |> require_unique_task_ids(run["tasks"] || [])
    |> require_text("closure status", sources.closure, "Status: `accepted_by_closure`")
    |> require_text("closure source run", sources.closure, "Run timestamp: `#{@source_run_id}`")
    |> require_text(
      "closure result path",
      sources.closure,
      "post_stage_1_larger_sample/#{@source_run_id}/"
    )
    |> require_text(
      "run report source ID",
      sources.run_report,
      "Run timestamp: `#{@source_run_id}`"
    )
    |> require_equal("active Lane B packet ID", manifest["packet_id"], @packet_id)
    |> require_equal(
      "active Lane B source run",
      get_in(manifest, ["source_run", "run_timestamp"]),
      @source_run_id
    )
    |> require_equal(
      "active Lane B closure status",
      get_in(manifest, ["source_run", "closure_status"]),
      "accepted_by_closure"
    )
    |> reject_superseded_packet(config)
  end

  defp reject_superseded_packet(errors, config) do
    packet_path = PathHelpers.display_path(config.packet_dir, config.cwd)

    cond do
      String.contains?(packet_path, "20260530_141649") ->
        ["superseded packet 20260530_141649 cannot be used as active Lane B source" | errors]

      not String.contains?(packet_path, "20260601_113121") ->
        ["active Lane B packet path does not identify 20260601_113121: #{packet_path}" | errors]

      true ->
        errors
    end
  end

  defp validate_run_controls(errors, _config, sources) do
    controls = sources.run["run_controls"] || %{}
    working_set = get_in(sources.run, ["arm_metadata", "working_set"]) || %{}

    errors
    |> require_equal("model identity", controls["model_identity"], @model)
    |> require_equal("harness identity", controls["harness_identity"], @harness)
    |> require_equal(
      "context planner adapter",
      controls["context_planner_adapter"],
      @context_adapter
    )
    |> require_equal("working-set adapter", working_set["adapter_module"], @context_adapter)
    |> require_equal("prompt character budget", controls["prompt_character_budget"], 20_000)
    |> require_equal("response character budget", controls["response_character_budget"], 12_000)
    |> require_equal("response format", controls["response_format"], "json_only")
    |> require_equal("action-attempt limit", controls["action_attempt_limit"], 6)
    |> require_equal("recovery-attempt limit", controls["recovery_attempt_limit"], 1)
    |> require_equal("global context budget", controls["context_budget"], nil)
    |> require_member("baseline arm labels", controls["baseline_arm_labels"], @baseline_arm)
    |> require_member("treatment arm labels", controls["treatment_arm_labels"], @treatment_arm)
    |> require_equal("working-set baseline arm", working_set["baseline_arm_label"], @baseline_arm)
    |> require_equal(
      "working-set treatment arm",
      working_set["treatment_arm_label"],
      @treatment_arm
    )
    |> require_equal("working-set scope", working_set["scope"], "Working Set Compiler v0 only")
  end

  defp validate_lane_a(config, sources) do
    run = sources.run
    tasks = run["tasks"] || []

    {fixture_errors, fixture_records, context_records, per_fixture_metrics} =
      @fixture_budgets
      |> Enum.sort_by(&elem(&1, 0))
      |> Enum.reduce({[], [], [], %{"baseline" => [], "treatment" => []}}, fn
        {fixture_id, budget}, {errors, fixtures, contexts, metrics} ->
          case Enum.find(tasks, &(&1["task_id"] == fixture_id)) do
            nil ->
              {["missing long-context fixture #{fixture_id}" | errors], fixtures, contexts,
               metrics}

            task ->
              {item_errors, fixture_record, item_contexts, item_metrics} =
                validate_long_context_fixture(config, task, fixture_id, budget)

              {
                errors ++ item_errors,
                fixtures ++ [fixture_record],
                contexts ++ item_contexts,
                %{
                  "baseline" => metrics["baseline"] ++ [item_metrics["baseline"]],
                  "treatment" => metrics["treatment"] ++ [item_metrics["treatment"]]
                }
              }
          end
      end)

    aggregate = %{
      "baseline" => aggregate_context_metrics(per_fixture_metrics["baseline"]),
      "treatment" => aggregate_context_metrics(per_fixture_metrics["treatment"])
    }

    errors =
      fixture_errors
      |> validate_lane_a_aggregate(run, aggregate)
      |> validate_process_integrity(run)
      |> validate_lane_a_report(sources.run_report)

    lane_a = %{
      "label_source" => "automated_structural_and_fixture_oracle",
      "fixture_count" => length(fixture_records),
      "fixture_records" => fixture_records,
      "context_artifact_records" => context_records,
      "metrics" => aggregate,
      "metric_label_sources" => %{
        "working_set_budget_adherence" => "automated_structural",
        "working_set_provenance_completeness" => "automated_structural",
        "context_omission_error_rate" => "fixture_oracle",
        "working_set_relevance_score" => "fixture_oracle",
        "long_task_stability" => "automated_structural_and_task_outcome"
      }
    }

    {errors, lane_a}
  end

  defp validate_long_context_fixture(config, task, fixture_id, budget) do
    workspace = Path.join(config.fixtures_root, fixture_id)
    task_path = Path.join(workspace, "task.json")
    metadata_path = Path.join(workspace, "expected/working_set_acceptance.json")
    task_source = task_path |> File.read!() |> Jason.decode!()
    metadata = metadata_path |> File.read!() |> Jason.decode!()
    fixture_hash = Vanta.PostStage1LargerSample.fixture_hash(workspace)
    working_set = task["working_set"] || %{}
    baseline = working_set["baseline"] || %{}
    treatment = working_set["treatment"] || %{}
    baseline_context = baseline["context"]
    treatment_context = treatment["context"]

    context_input =
      metadata
      |> Map.put("task_id", task_source["task_id"])
      |> Map.put_new("active_goal_ref", "task:#{task_source["task_id"]}")

    expected_baseline = Vanta.RawTraceContextBuilder.build(context_input, workspace: workspace)

    expected_treatment =
      case Vanta.WorkingSetCompiler.compile(context_input, workspace: workspace) do
        {:ok, compiled} ->
          compiled

        {:error, reason} ->
          raise "cannot reconstruct #{fixture_id} working set: #{inspect(reason)}"
      end

    compact_baseline = compact_baseline_context(expected_baseline)

    compact_treatment =
      expected_treatment
      |> compact_treatment_context()
      |> align_historical_schema_version(treatment_context)

    baseline_metrics = recompute_context_metrics(expected_baseline, metadata, baseline)
    treatment_metrics = recompute_context_metrics(expected_treatment, metadata, treatment)

    errors =
      []
      |> require_equal("#{fixture_id} stratum", task["stratum"], "working_set_long_context")
      |> require_equal("#{fixture_id} fixture hash", task["fixture_hash"], fixture_hash)
      |> require_equal(
        "#{fixture_id} required refs",
        working_set["required_refs"],
        metadata["required_refs"]
      )
      |> require_equal(
        "#{fixture_id} relevant refs",
        working_set["relevant_refs"],
        metadata["relevant_refs"]
      )
      |> require_equal(
        "#{fixture_id} irrelevant refs",
        working_set["irrelevant_refs"],
        metadata["irrelevant_refs"]
      )
      |> require_equal("#{fixture_id} compute match", working_set["compute_match"], true)
      |> require_equal(
        "#{fixture_id} frozen metadata budget",
        get_in(metadata, ["budget", "max_context_chars"]),
        budget
      )
      |> require_equal(
        "#{fixture_id} baseline context budget",
        context_budget(baseline_context),
        budget
      )
      |> require_equal(
        "#{fixture_id} treatment context budget",
        context_budget(treatment_context),
        budget
      )
      |> require_equal(
        "#{fixture_id} baseline context artifact",
        baseline_context,
        compact_baseline
      )
      |> require_equal(
        "#{fixture_id} treatment context artifact",
        treatment_context,
        compact_treatment
      )
      |> require_equal(
        "#{fixture_id} baseline context metrics",
        baseline["context_metrics"],
        baseline_metrics
      )
      |> require_equal(
        "#{fixture_id} treatment context metrics",
        treatment["context_metrics"],
        treatment_metrics
      )
      |> validate_arm_budget_controls(fixture_id, "baseline", baseline)
      |> validate_arm_budget_controls(fixture_id, "treatment", treatment)
      |> validate_working_set_schema(fixture_id, treatment_context)

    fixture_record = %{
      "fixture_id" => fixture_id,
      "fixture_hash" => fixture_hash,
      "source_fixture_ref" => PathHelpers.display_path(workspace, config.cwd) <> "/",
      "context_budget_chars" => budget,
      "baseline_context_artifact_id" => context_artifact_id(baseline_context),
      "treatment_context_artifact_id" => context_artifact_id(treatment_context),
      "source_traceability_valid" => errors == []
    }

    context_records = [
      context_record(fixture_id, "baseline", baseline_context, budget, fixture_hash),
      context_record(fixture_id, "treatment", treatment_context, budget, fixture_hash)
    ]

    {errors, fixture_record, context_records,
     %{"baseline" => baseline_metrics, "treatment" => treatment_metrics}}
  end

  defp compact_baseline_context(context) do
    Map.take(context, ~w(
      artifact_id
      arm
      max_context_chars
      selected_context_chars
      estimated_tokens
      estimation_method
      budget_adhered
      included_refs
      dropped_refs
    ))
  end

  defp compact_treatment_context(context) do
    %{
      "type" => "working_set",
      "working_set" => context.working_set,
      "selected_refs" =>
        Enum.map(context.selected_refs, &Map.take(&1, ["ref_id", "kind", "path", "content_hash"])),
      "omitted_refs" =>
        Enum.map(context.omitted_refs, &Map.take(&1, ["ref_id", "kind", "path", "omit_reason"]))
    }
  end

  # The accepted source run predates the schema-version marker update. Selection,
  # ordering, budgets, provenance, and content hashes must still match exactly;
  # only the historical marker is retained for the artifact equivalence check.
  defp align_historical_schema_version(rebuilt, source) do
    case get_in(source || %{}, ["working_set", "schema_version"]) do
      version when is_binary(version) ->
        put_in(rebuilt, ["working_set", "schema_version"], version)

      _ ->
        rebuilt
    end
  end

  defp recompute_context_metrics(context, metadata, arm) do
    included_refs = included_refs(context)
    included_ids = included_refs |> Enum.map(& &1["ref_id"]) |> MapSet.new()
    required_ids = metadata |> Map.get("required_refs", []) |> MapSet.new()

    relevant_ids =
      metadata
      |> Map.get("relevant_refs", [])
      |> Kernel.++(Map.get(metadata, "required_refs", []))
      |> MapSet.new()

    provenance_complete =
      if included_refs == [] do
        0.0
      else
        Enum.count(included_refs, fn ref ->
          Enum.all?(~w(ref_id source path content_hash), &PathHelpers.present?(ref[&1]))
        end) / length(included_refs)
      end

    relevance =
      if included_refs == [] do
        0.0
      else
        Enum.count(included_refs, &MapSet.member?(relevant_ids, &1["ref_id"])) /
          length(included_refs)
      end

    %{
      "budget_adherent" => budget_adherent?(context),
      "provenance_completeness" => provenance_complete,
      "context_omission_error_rate" =>
        MapSet.size(MapSet.difference(required_ids, included_ids)) /
          max(MapSet.size(required_ids), 1),
      "working_set_relevance_score" => relevance,
      "long_task_stable" =>
        arm["task_success"] == true and arm["unsupported_commit"] == false and
          arm["memory_write_count"] == 0
    }
  end

  defp included_refs(%{working_set: working_set}),
    do: get_in(working_set, ["provenance", "included_refs"]) || []

  defp included_refs(%{"included_refs" => refs}) when is_list(refs), do: refs
  defp included_refs(_context), do: []

  defp budget_adherent?(%{working_set: working_set}),
    do: get_in(working_set, ["token_budget", "budget_adhered"]) == true

  defp budget_adherent?(%{"budget_adhered" => value}), do: value == true
  defp budget_adherent?(_context), do: false

  defp context_budget(%{"max_context_chars" => budget}), do: budget

  defp context_budget(%{"working_set" => working_set}),
    do: get_in(working_set, ["token_budget", "max_context_chars"])

  defp context_budget(_context), do: nil

  defp context_artifact_id(%{"artifact_id" => id}), do: id
  defp context_artifact_id(%{"working_set" => %{"working_set_id" => id}}), do: id
  defp context_artifact_id(_context), do: nil

  defp context_record(fixture_id, arm, context, budget, fixture_hash) do
    %{
      "fixture_id" => fixture_id,
      "arm" => arm,
      "arm_label" => if(arm == "baseline", do: @baseline_arm, else: @treatment_arm),
      "context_artifact_id" => context_artifact_id(context),
      "context_artifact_hash" => Hash.canonical_json_hash(context),
      "context_budget_chars" => budget,
      "selected_context_chars" => selected_context_chars(context),
      "source_fixture_hash" => fixture_hash,
      "source_traceability_valid" => true
    }
  end

  defp selected_context_chars(%{"selected_context_chars" => value}), do: value

  defp selected_context_chars(%{"working_set" => working_set}),
    do: get_in(working_set, ["token_budget", "selected_context_chars"])

  defp selected_context_chars(_context), do: nil

  defp validate_arm_budget_controls(errors, fixture_id, arm_name, arm) do
    usage = arm["planner_budget_usage"] || %{}

    errors
    |> require_equal("#{fixture_id} #{arm_name} prompt budget", usage["max_prompt_chars"], 20_000)
    |> require_equal(
      "#{fixture_id} #{arm_name} response budget",
      usage["max_response_chars"],
      12_000
    )
    |> require_equal("#{fixture_id} #{arm_name} model call count", usage["model_call_count"], 1)
  end

  defp validate_working_set_schema(errors, fixture_id, treatment_context) do
    case get_in(treatment_context || %{}, ["working_set"]) do
      working_set when is_map(working_set) ->
        case Vanta.Schema.validate("working_set", working_set) do
          :ok ->
            errors

          {:error, schema_errors} ->
            ["#{fixture_id} working-set schema mismatch: #{inspect(schema_errors)}" | errors]
        end

      _other ->
        ["#{fixture_id} missing treatment working-set artifact" | errors]
    end
  end

  defp aggregate_context_metrics([]), do: %{}

  defp aggregate_context_metrics(metrics) do
    %{
      "working_set_budget_adherence" => rate(metrics, "budget_adherent"),
      "working_set_provenance_completeness" => mean(metrics, "provenance_completeness"),
      "context_omission_error_rate" => mean(metrics, "context_omission_error_rate"),
      "working_set_relevance_score" => mean(metrics, "working_set_relevance_score"),
      "long_task_stability" => rate(metrics, "long_task_stable")
    }
  end

  defp rate(items, field), do: Enum.count(items, &(&1[field] == true)) / length(items)
  defp mean(items, field), do: Enum.sum(Enum.map(items, & &1[field])) / length(items)

  defp validate_lane_a_aggregate(errors, run, aggregate) do
    Enum.reduce(~w(baseline treatment), errors, fn arm, acc ->
      Enum.reduce(@lane_a_expected[arm], acc, fn {metric, expected}, arm_errors ->
        arm_errors
        |> require_number("recomputed Lane A #{arm} #{metric}", aggregate[arm][metric], expected)
        |> require_number(
          "source working-set metric #{arm} #{metric}",
          get_in(run, ["metrics", "working_set", arm, metric]),
          expected
        )
        |> require_number(
          "source aggregate metric #{arm} #{metric}",
          get_in(run, ["metrics", arm, metric]),
          expected
        )
      end)
    end)
  end

  defp validate_lane_a_report(errors, report) do
    expected_fragments = [
      "| `working_set_budget_adherence` | `1.0000` | `1.0000` |",
      "| `working_set_provenance_completeness` | `0.6667` | `1.0000` |",
      "| `context_omission_error_rate` | `0.7778` | `0.0000` |",
      "| `working_set_relevance_score` | `0.2167` | `0.9667` |",
      "| `long_task_stability` | `1.0000` | `1.0000` |"
    ]

    Enum.reduce(expected_fragments, errors, fn fragment, acc ->
      require_text(acc, "Lane A run report metric", report, fragment)
    end)
  end

  defp validate_process_integrity(errors, run) do
    floor_paths = [
      ["metrics", "hard_gates", "unsupported_commits"],
      ["metrics", "hard_gates", "memory_writes"],
      ["metrics", "hard_gates", "disallowed_side_effect_classes"],
      ["metrics", "baseline", "unsupported_commits"],
      ["metrics", "baseline", "memory_writes"],
      ["metrics", "baseline", "disallowed_side_effect_classes"],
      ["metrics", "treatment", "unsupported_commits"],
      ["metrics", "treatment", "memory_writes"],
      ["metrics", "treatment", "disallowed_side_effect_classes"]
    ]

    errors =
      Enum.reduce(floor_paths, errors, fn path, acc ->
        require_equal(acc, "process-integrity #{Enum.join(path, ".")}", get_in(run, path), 0)
      end)

    Enum.reduce(run["tasks"] || [], errors, fn task, acc ->
      treatment = get_in(task, ["runtime_governance", "treatment"]) || %{}

      acc
      |> require_equal(
        "#{task["task_id"]} unsupported commit",
        treatment["unsupported_commit"],
        false
      )
      |> require_equal("#{task["task_id"]} memory writes", treatment["memory_write_count"], 0)
      |> require_equal(
        "#{task["task_id"]} disallowed side-effect count",
        treatment["disallowed_side_effect_count"],
        0
      )
    end)
  end

  defp validate_lane_b(config, sources) do
    label_opts = [packet_dir: config.packet_dir, cwd: config.cwd, run_timestamp: @source_run_id]

    {label_validation_errors, generated_summary} =
      case PostStage1LaneBLabelResults.validate_file(config.primary_label_results, label_opts) do
        {:ok, summary} -> {[], summary}
        {:error, errors} -> {Enum.map(errors, &"Lane B primary labels: #{&1}"), %{}}
      end

    parity_errors =
      case PostStage1LaneBLabelResults.validate_report_parity(
             config.label_report,
             config.primary_label_results,
             config.import_summary,
             label_opts
           ) do
        {:ok, _summary} -> []
        {:error, errors} -> Enum.map(errors, &"Lane B report/import parity: #{&1}")
      end

    boundary_errors = reviewer_visible_boundary_errors(config, sources)

    errors =
      []
      |> validate_lane_b_lifecycle(sources)
      |> validate_lane_b_expected_metrics(generated_summary)
      |> validate_lane_b_memo(sources.memo)
      |> Kernel.++(label_validation_errors)
      |> Kernel.++(parity_errors)
      |> Kernel.++(boundary_errors)

    lane_b = lane_b_summary(generated_summary)
    {errors, lane_b}
  end

  defp validate_lane_b_lifecycle(errors, sources) do
    results = sources.primary_label_results
    import_summary = sources.import_summary
    freeze = sources.packet_freeze
    agreement = results["agreement_report"] || %{}

    errors
    |> require_equal("Lane B label policy", results["label_policy_version"], @label_policy)
    |> require_equal("Lane B packet ID", results["packet_id"], @packet_id)
    |> require_equal(
      "Lane B collection status",
      results["label_collection_status"],
      "complete_reported"
    )
    |> require_equal(
      "primary label freeze status",
      get_in(results, ["primary_label_freeze", "status"]),
      "frozen"
    )
    |> require_equal(
      "primary label freeze timestamp",
      get_in(results, ["primary_label_freeze", "frozen_at"]),
      "2026-06-05T21:40:44+08:00"
    )
    |> require_equal(
      "fixture oracle exposure before primary freeze",
      get_in(results, ["primary_label_freeze", "fixture_oracle_exposed_before_freeze"]),
      false
    )
    |> require_equal("import summary status", import_summary["status"], "ok")
    |> require_equal("import summary packet ID", import_summary["packet_id"], @packet_id)
    |> require_equal(
      "import summary label policy",
      import_summary["label_policy_version"],
      @label_policy
    )
    |> require_equal("needs_review count", import_summary["needs_review_count"], 0)
    |> require_equal(
      "adjudication required count",
      import_summary["adjudication_required_count"],
      0
    )
    |> require_equal(
      "unhandled adjudication required count",
      import_summary["unhandled_adjudication_required_count"],
      0
    )
    |> require_equal(
      "packet allowlist freeze status",
      freeze["freeze_status"],
      "frozen_for_primary_review_distribution"
    )
    |> require_equal("packet allowlist policy", freeze["label_policy_version"], @label_policy)
    |> require_equal("agreement status", agreement["status"], "small_sample_raw_counts")
    |> require_equal(
      "evidence raw exact agreement",
      get_in(agreement, [
        "raw_agreement_counts",
        "evidence_sufficiency_score",
        "exact_raw_label_agreement"
      ]),
      8
    )
    |> require_equal(
      "working-set omission exact agreement",
      get_in(agreement, [
        "raw_agreement_counts",
        "working_set_context",
        "omission_exact_agreement"
      ]),
      12
    )
    |> validate_frozen_packet_hashes(sources)
  end

  defp validate_frozen_packet_hashes(errors, sources) do
    hashes = sources.packet_freeze["content_hashes"] || %{}

    [sources.evidence_items_path, sources.working_set_items_path]
    |> Enum.reduce(errors, fn path, acc ->
      relative = PathHelpers.display_path(path, sources.cwd)

      require_equal(
        acc,
        "frozen reviewer-visible hash #{relative}",
        hashes[relative],
        Hash.file_hash(path)
      )
    end)
  end

  defp validate_lane_b_expected_metrics(errors, generated_summary) do
    raw_counts = generated_summary["raw_label_counts"] || %{}
    scores = generated_summary["reported_metric_scores"] || %{}

    errors =
      errors
      |> require_equal(
        "Lane B evidence raw label count",
        raw_counts["evidence_sufficiency_score"],
        16
      )
      |> require_equal("Lane B context raw label count", raw_counts["working_set_context"], 24)

    Enum.reduce(@lane_b_expected, errors, fn {arm, metric_expectations}, acc ->
      Enum.reduce(metric_expectations, acc, fn {metric, {numerator, denominator, score}},
                                               arm_errors ->
        numerator_key =
          if metric == "context_omission_error_rate",
            do: "omitted_task_critical_ref_count",
            else: "relevant_included_ref_count"

        denominator_key =
          if metric == "context_omission_error_rate",
            do: "task_critical_candidate_ref_count",
            else: "included_ref_denominator"

        values = get_in(scores, [metric, "by_blinded_arm", arm]) || %{}

        arm_errors
        |> require_equal("Lane B #{arm} #{metric} numerator", values[numerator_key], numerator)
        |> require_equal(
          "Lane B #{arm} #{metric} denominator",
          values[denominator_key],
          denominator
        )
        |> require_equal("Lane B #{arm} #{metric} rate", values["score_4dp"], score)
      end)
    end)
  end

  defp validate_lane_b_memo(errors, memo) do
    errors
    |> require_text(
      "coordinator memo status",
      memo,
      "Memo status: `coordinator_only_post_freeze`"
    )
    |> require_text("coordinator memo packet", memo, "Packet ID: `#{@packet_id}`")
    |> require_text(
      "coordinator memo primary freeze",
      memo,
      "Primary label freeze: `2026-06-05T21:40:44+08:00`"
    )
    |> require_text(
      "coordinator memo baseline mapping",
      memo,
      "| `context_arm_A` | Context baseline | `#{@baseline_arm}`"
    )
    |> require_text(
      "coordinator memo treatment mapping",
      memo,
      "| `context_arm_B` | Working Set Compiler v0 treatment | `#{@treatment_arm}`"
    )
    |> require_text(
      "coordinator memo boundary",
      memo,
      "must not be backfilled into reviewer-visible packet records"
    )
  end

  defp reviewer_visible_boundary_errors(config, sources) do
    artifacts = %{
      evidence_sufficiency_items: sources.evidence_items,
      working_set_context_items: sources.working_set_items,
      redacted_task_packets: sources.redacted_task_packets,
      label_results_template: sources.label_results_template,
      label_results_primary_filled: sources.primary_label_results
    }

    PostStage1LaneBPacket.post_freeze_unblind_boundary_errors(artifacts)
    |> Enum.map(&"reviewer-visible packet contamination: #{&1}")
    |> Kernel.++(validate_blinded_arm_shape(config, sources.working_set_items))
  end

  defp validate_blinded_arm_shape(_config, items) do
    frequencies = Enum.frequencies_by(items, & &1["blinded_arm"])

    errors =
      if frequencies == %{"context_arm_A" => 6, "context_arm_B" => 6} do
        []
      else
        [
          "reviewer-visible blinded arm coverage is #{inspect(frequencies)}, expected six items per blinded arm"
        ]
      end

    Enum.reduce(items, errors, fn item, acc ->
      artifact_id = item["context_artifact_id"] || ""

      expected_prefix =
        case item["blinded_arm"] do
          "context_arm_A" -> "raw_trace_"
          "context_arm_B" -> "working_set_"
          _other -> "__invalid_arm__"
        end

      if String.starts_with?(artifact_id, expected_prefix) do
        acc
      else
        [
          "#{item["packet_id"]} context artifact #{inspect(artifact_id)} does not match blinded arm prefix"
          | acc
        ]
      end
    end)
  end

  defp lane_b_summary(generated_summary) do
    scores = generated_summary["reported_metric_scores"] || %{}

    %{
      "label_source" => "human",
      "packet_id" => @packet_id,
      "primary_label_freeze" => "2026-06-05T21:40:44+08:00",
      "raw_label_counts" => generated_summary["raw_label_counts"],
      "small_sample_reporting" => "raw_counts_only",
      "blinded_arm_metrics" => %{
        "context_arm_A" => lane_b_arm_metrics(scores, "context_arm_A"),
        "context_arm_B" => lane_b_arm_metrics(scores, "context_arm_B"),
        "Combined" => lane_b_arm_metrics(scores, "Combined")
      },
      "post_freeze_true_arm_interpretation" => %{
        "baseline" => %{
          "blinded_arm" => "context_arm_A",
          "arm_label" => @baseline_arm,
          "metrics" => lane_b_arm_metrics(scores, "context_arm_A")
        },
        "treatment" => %{
          "blinded_arm" => "context_arm_B",
          "arm_label" => @treatment_arm,
          "metrics" => lane_b_arm_metrics(scores, "context_arm_B")
        }
      },
      "reviewer_visible_true_arm_identity_backfilled" => false,
      "relevance_interpretation" =>
        "must be read with omission; sparse or empty context can mislead"
    }
  end

  defp lane_b_arm_metrics(scores, arm) do
    omission = get_in(scores, ["context_omission_error_rate", "by_blinded_arm", arm]) || %{}
    relevance = get_in(scores, ["working_set_relevance_score", "by_blinded_arm", arm]) || %{}

    %{
      "context_omission_error_rate" => %{
        "numerator" => omission["omitted_task_critical_ref_count"],
        "denominator" => omission["task_critical_candidate_ref_count"],
        "rate_4dp" => omission["score_4dp"]
      },
      "working_set_relevance_score" => %{
        "numerator" => relevance["relevant_included_ref_count"],
        "denominator" => relevance["included_ref_denominator"],
        "rate_4dp" => relevance["score_4dp"]
      }
    }
  end

  defp control_summary(sources) do
    controls = sources.run["run_controls"]

    %{
      "model" => @model,
      "harness" => @harness,
      "context_planner_adapter" => @context_adapter,
      "openclaw_agent" => @openclaw_agent,
      "openclaw_agent_provenance" => "post_hoc_user_authorized_coordinator_control_attestation",
      "prompt_character_budget" => controls["prompt_character_budget"],
      "response_character_budget" => controls["response_character_budget"],
      "response_format" => controls["response_format"],
      "action_attempt_limit" => controls["action_attempt_limit"],
      "recovery_attempt_limit" => controls["recovery_attempt_limit"],
      "tool_policy" => "embedded_context_only",
      "tool_policy_provenance" =>
        "coordinator attestation plus adapter source hash and policy fragments",
      "baseline_arm_label" => @baseline_arm,
      "treatment_arm_label" => @treatment_arm,
      "context_budget" => %{
        "global" => nil,
        "global_null_semantics" => "uses_frozen_per_fixture_budgets",
        "per_fixture_chars" => @fixture_budgets
      }
    }
  end

  defp process_integrity_floors(_run) do
    %{
      "unsupported_commits" => 0,
      "memory_writes" => 0,
      "disallowed_side_effect_classes" => 0
    }
  end

  defp interpretation_boundaries do
    [
      "This is an artifact-backed post-freeze evaluation of the existing 20260601_113121 Lane A run and active Lane B packet; it is not a new model run.",
      "Lane A values are automated structural or fixture-oracle evidence, not human labels.",
      "Lane B values are human-label evidence for the named active packet only; arm interpretation uses the coordinator-only memo after primary label freeze.",
      "The OpenClaw arms include the local harness and must not be described as pure model-only.",
      "The pilot does not implement or validate full Context OS, learned retrieval, ranking, compression, memory governance, or H3.",
      "The pilot creates no runtime approval, runtime action, schema enum, side-effect, memory-write, production-readiness, or closure authority."
    ]
  end

  defp require_unique_task_ids(errors, tasks) do
    ids = Enum.map(tasks, & &1["task_id"])

    if length(ids) == length(Enum.uniq(ids)) do
      errors
    else
      ["source task IDs are not unique" | errors]
    end
  end

  defp require_equal(errors, _label, actual, expected) when actual == expected, do: errors

  defp require_equal(errors, label, actual, expected),
    do: ["#{label} is #{inspect(actual)}, expected #{inspect(expected)}" | errors]

  defp require_number(errors, label, actual, expected) do
    if PathHelpers.same_number?(actual, expected) do
      errors
    else
      ["#{label} is #{inspect(actual)}, expected #{inspect(expected)}" | errors]
    end
  end

  defp require_text(errors, label, text, fragment) when is_binary(text) do
    normalized_text = String.replace(text, ~r/\s+/, " ")
    normalized_fragment = String.replace(fragment, ~r/\s+/, " ")

    if String.contains?(normalized_text, normalized_fragment) do
      errors
    else
      ["#{label} is missing required fragment #{inspect(fragment)}" | errors]
    end
  end

  defp require_text(errors, label, _text, fragment),
    do: ["#{label} is not readable while checking #{inspect(fragment)}" | errors]

  defp require_member(errors, label, list, member) when is_list(list) do
    if member in list do
      errors
    else
      ["#{label} does not include #{inspect(member)}" | errors]
    end
  end

  defp require_member(errors, label, value, member),
    do: ["#{label} is #{inspect(value)}, expected a list containing #{inspect(member)}" | errors]
end
