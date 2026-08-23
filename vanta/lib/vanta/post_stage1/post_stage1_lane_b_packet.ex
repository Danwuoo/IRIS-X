defmodule Vanta.PostStage1LaneBPacket do
  @moduledoc """
  Builds and checks the post-Stage-1 Lane B blinded label packet.
  """

  alias Vanta.PostStage1LaneBPacket.{Parser, ReportWriter, Validator}

  import Vanta.PostStage1LaneBPacket.PathHelpers

  @default_run_timestamp "20260601_113121"
  @label_policy_version "PS1-LB-LABEL-001"
  @metric_policy_version "PS1-LA-METRIC-001"
  @context_gate_policy_version "PS1-LC-CTX-GATE-001"
  @sample_frame "PS1-LA-SAMPLE-002"
  @experiment_id "post_stage_1_larger_sample"
  @not_yet_run "Not yet run"
  @complete_reported "complete_reported"
  @complete_reported_packet_status "active_packet_complete_reported"
  @reported_from_validated_primary_labels "reported_from_validated_primary_labels"
  @completed_no_adjudication_records "completed_no_records_required"

  @evidence_sample [
    {"docops_read_traceability_001", "traceability_extraction"},
    {"docops_struct_contract_fail_001", "terminology_consistency"},
    {"docops_simulate_patch_001", "simulated_patch_and_diff"},
    {"docops_struct_apply_reversible_001", "reversible_edit_and_commit"},
    {"docops_struct_selector_missing_001", "invalid_action_and_path_guard"},
    {"docops_wrong_diff_001", "evidence_and_verifier_challenge"},
    {"docops_rollback_failure_001", "journal_replay_and_recovery"},
    {"docops_ws_evidence_packet_001", "working_set_long_context"}
  ]

  @working_set_task_ids ~w(
    docops_ws_evidence_packet_001
    docops_ws_irrelevant_context_001
    docops_ws_omission_trap_001
    docops_ws_recovery_context_001
    docops_ws_traceability_long_001
    docops_ps1_ws_structured_edit_context_001
  )

  @redacted_task_oracle_fields ~w(
    required_refs
    relevant_refs
    irrelevant_refs
    omission_trap_refs
    expected_runtime_status
    expected_label_source
    expected_failure_labels
    expected_recovery_policy
    expected_failure_label
  )

  def default_run_timestamp, do: @default_run_timestamp

  def post_freeze_unblind_boundary_errors(packet_artifacts) when is_map(packet_artifacts),
    do: Validator.post_freeze_unblind_boundary_errors(packet_artifacts)

  def build(opts \\ []) do
    config = normalize_opts(opts)

    with :ok <- ensure_sources(config),
         {:ok, run} <- load_json(config.run_json_abs),
         :ok <- validate_run_source(run, config),
         {:ok, redacted_task_packets} <- build_redacted_task_packets(config),
         {:ok, evidence_items} <- build_evidence_items(run, config),
         {:ok, working_set_items} <- build_working_set_items(run, config),
         {:ok, label_state} <- label_state(config) do
      packet_manifest =
        packet_manifest(config, run, evidence_items, working_set_items, label_state)

      packet = %{
        opts: config,
        label_state: label_state,
        packet_manifest: packet_manifest,
        readme: packet_readme(config, label_state),
        redacted_task_packets: redacted_task_packets,
        evidence_sufficiency_items: evidence_items,
        working_set_context_items: working_set_items,
        adjudication_placeholders:
          adjudication_placeholders(config, evidence_items, working_set_items),
        label_results_template:
          Vanta.PostStage1LaneBLabelResults.template_for_packet(%{
            packet_manifest: packet_manifest,
            packet_dir: config.out_path
          }),
        label_report_skeleton: label_report_skeleton(config, label_state)
      }

      {:ok, packet}
    end
  end

  def generate(opts \\ []) do
    with {:ok, packet} <- build(opts) do
      {:ok, ReportWriter.write_packet!(packet)}
    end
  end

  def check(opts \\ []) do
    with {:ok, expected} <- build(opts),
         {:ok, actual} <- Parser.load_existing_packet(expected.opts, packet_task_ids()) do
      errors = Validator.validate_packet(expected, actual)

      if errors == [] do
        {:ok,
         %{
           packet_id: expected.packet_manifest["packet_id"],
           packet_dir: expected.opts.out_path,
           evidence_item_count: length(actual.evidence_sufficiency_items),
           working_set_item_count: length(actual.working_set_context_items),
           status: "ok"
         }}
      else
        {:error, Enum.reverse(errors)}
      end
    end
  end

  defp normalize_opts(opts) do
    cwd = Keyword.get(opts, :cwd, File.cwd!())
    run_timestamp = Keyword.get(opts, :run_timestamp, @default_run_timestamp)
    out = Keyword.get(opts, :out, default_packet_dir(run_timestamp))
    fixtures = Keyword.get(opts, :fixtures, "docs/04_experiments/fixtures/document_ops")
    run_json = Keyword.get(opts, :run_json, default_run_json(run_timestamp))

    run_report =
      Keyword.get(
        opts,
        :run_report,
        "docs/05_evaluation/Post_Stage_1_Lane_A_#{run_timestamp}_Run_Report.md"
      )

    closure =
      Keyword.get(
        opts,
        :closure,
        "docs/00_manifest/Post_Stage_1_Lane_A_#{run_timestamp}_Closure.md"
      )

    label_report =
      Keyword.get(
        opts,
        :label_report,
        "docs/05_evaluation/Post_Stage_1_Lane_B_#{run_timestamp}_Label_Report_Skeleton.md"
      )

    label_results =
      Keyword.get(
        opts,
        :label_results,
        Path.join(out, "label_results_primary_filled.json")
      )

    import_summary =
      Keyword.get(
        opts,
        :import_summary,
        Path.join(out, "label_results_import_summary.json")
      )

    coordinator_packet_freeze =
      Keyword.get(
        opts,
        :coordinator_packet_freeze,
        Path.join(out, "coordinator_primary_label_packet_freeze.json")
      )

    %{
      cwd: cwd,
      run_timestamp: run_timestamp,
      packet_date: packet_date(run_timestamp),
      packet_id: packet_id(run_timestamp),
      out_abs: Path.expand(out, cwd),
      out_path: display_path(out, cwd),
      fixtures_abs: Path.expand(fixtures, cwd),
      fixtures_path: display_path(fixtures, cwd),
      run_json_abs: Path.expand(run_json, cwd),
      run_json_path: display_path(run_json, cwd),
      summary_abs: Path.expand(Path.join(Path.dirname(run_json), "summary.md"), cwd),
      summary_path: display_path(Path.join(Path.dirname(run_json), "summary.md"), cwd),
      fixture_inventory_abs:
        Path.expand(Path.join(Path.dirname(run_json), "fixture_inventory.md"), cwd),
      fixture_inventory_path:
        display_path(Path.join(Path.dirname(run_json), "fixture_inventory.md"), cwd),
      run_report_abs: Path.expand(run_report, cwd),
      run_report_path: display_path(run_report, cwd),
      closure_abs: Path.expand(closure, cwd),
      closure_path: display_path(closure, cwd),
      label_report_abs: Path.expand(label_report, cwd),
      label_report_path: display_path(label_report, cwd),
      label_results_abs: Path.expand(label_results, cwd),
      label_results_path: display_path(label_results, cwd),
      import_summary_abs: Path.expand(import_summary, cwd),
      import_summary_path: display_path(import_summary, cwd),
      coordinator_packet_freeze_abs: Path.expand(coordinator_packet_freeze, cwd),
      coordinator_packet_freeze_path: display_path(coordinator_packet_freeze, cwd),
      closure_status: closure_status(Path.expand(closure, cwd))
    }
  end

  defp default_packet_dir(run_timestamp) do
    "docs/05_evaluation/label_packets/post_stage_1_lane_b_#{run_timestamp}"
  end

  defp default_run_json(run_timestamp) do
    "docs/04_experiments/results/post_stage_1_larger_sample/#{run_timestamp}/run.json"
  end

  defp ensure_sources(config) do
    [
      {config.run_json_abs, "run JSON"},
      {config.summary_abs, "run summary"},
      {config.fixture_inventory_abs, "fixture inventory"},
      {config.run_report_abs, "run report"},
      {config.closure_abs, "closure document"},
      {config.fixtures_abs, "fixture root"}
    ]
    |> Enum.reduce([], fn {path, label}, errors ->
      if File.exists?(path),
        do: errors,
        else: ["missing #{label}: #{display_path(path, config.cwd)}" | errors]
    end)
    |> case do
      [] -> :ok
      errors -> {:error, Enum.reverse(errors)}
    end
  end

  defp validate_run_source(run, config) do
    checks = [
      {"experiment_id", run["experiment_id"], @experiment_id},
      {"sample_frame_id", run["sample_frame_id"], @sample_frame},
      {"metric_policy_version", run["metric_policy_version"], @metric_policy_version},
      {"threshold_status", run["threshold_status"], "pass_acceptance_candidate"}
    ]

    errors =
      checks
      |> Enum.reduce([], fn {field, actual, expected}, errors ->
        if actual == expected do
          errors
        else
          ["source run #{field} is #{inspect(actual)}, expected #{inspect(expected)}" | errors]
        end
      end)
      |> then(fn errors ->
        if run["status"] == "completed" do
          errors
        else
          ["source run status is #{inspect(run["status"])}, expected \"completed\"" | errors]
        end
      end)
      |> then(fn errors ->
        if is_list(run["tasks"]) and length(run["tasks"]) == 48 do
          errors
        else
          ["source run task count is not 48" | errors]
        end
      end)
      |> then(fn errors ->
        if config.closure_status == "accepted_by_closure" do
          errors
        else
          [
            "closure status is #{inspect(config.closure_status)}, expected \"accepted_by_closure\""
            | errors
          ]
        end
      end)

    if errors == [], do: :ok, else: {:error, Enum.reverse(errors)}
  end

  defp build_redacted_task_packets(config) do
    packet_task_ids()
    |> Enum.reduce_while({:ok, %{}}, fn task_id, {:ok, packets} ->
      task_path = Path.join([config.fixtures_abs, task_id, "task.json"])

      case load_json(task_path) do
        {:ok, task} ->
          {:cont, {:ok, Map.put(packets, task_id, redact_task(task, task_path, config))}}

        {:error, errors} ->
          {:halt, {:error, errors}}
      end
    end)
  end

  defp redact_task(task, task_path, config) do
    input_artifacts =
      task
      |> Map.get("input_artifacts", [])
      |> Enum.map(&Map.drop(&1, ["role", "description"]))

    removed_oracle_fields =
      Enum.filter(@redacted_task_oracle_fields, &Map.has_key?(task, &1))

    task
    |> Map.drop(@redacted_task_oracle_fields)
    |> Map.put("input_artifacts", input_artifacts)
    |> Map.put("redaction", %{
      "removed_fields" =>
        ["input_artifacts.role", "input_artifacts.description"] ++ removed_oracle_fields,
      "reason" =>
        "Primary Lane B labelers must not see fixture oracle role fields before label freeze.",
      "source_task_path" => display_path(task_path, config.cwd)
    })
  end

  defp build_evidence_items(run, config) do
    @evidence_sample
    |> Enum.with_index(1)
    |> Enum.reduce_while({:ok, []}, fn {{task_id, stratum}, index}, {:ok, items} ->
      case evidence_item(run, config, task_id, stratum, index) do
        {:ok, item} -> {:cont, {:ok, items ++ [item]}}
        {:error, errors} -> {:halt, {:error, errors}}
      end
    end)
  end

  defp evidence_item(run, config, task_id, expected_stratum, index) do
    with {:ok, task} <- find_task(run, task_id),
         :ok <- ensure_stratum(task, task_id, expected_stratum),
         {:ok, treatment} <- required_map(task, ["runtime_governance", "treatment"], task_id),
         {:ok, evidence_packet} <-
           first_item(treatment["evidence_packets"], "#{task_id} evidence"),
         {:ok, verifier_output} <-
           first_item(treatment["verifier_outputs"], "#{task_id} verifier"),
         {:ok, step} <-
           first_item(get_in(treatment, ["journal", "steps"]), "#{task_id} journal step"),
         {:ok, journal} <- required_map(treatment, ["journal"], task_id) do
      {:ok,
       %{
         "packet_id" => "#{packet_prefix(config)}-es-#{pad3(index)}",
         "label_status" => @not_yet_run,
         "metric_targets" => ["evidence_sufficiency_score"],
         "review_mode" => "double_human_adjudicated",
         "task_id" => task_id,
         "stratum" => expected_stratum,
         "task_packet_path" => redacted_task_packet_path(config, task_id),
         "source_artifact_dir" => source_artifact_dir(config, task_id),
         "evidence_packet" => compact_evidence_packet(evidence_packet),
         "action_under_review" => compact_action_under_review(step),
         "verifier_output" => compact_verifier_output(verifier_output),
         "commit_or_reject_record" => compact_commit_record(journal),
         "primary_label_fields" => evidence_label_fields(),
         "adjudication_status" => @not_yet_run
       }}
    end
  end

  defp build_working_set_items(run, config) do
    @working_set_task_ids
    |> Enum.with_index(1)
    |> Enum.reduce_while({:ok, []}, fn {task_id, index}, {:ok, items} ->
      case working_set_task_items(run, config, task_id, index) do
        {:ok, task_items} -> {:cont, {:ok, items ++ task_items}}
        {:error, errors} -> {:halt, {:error, errors}}
      end
    end)
  end

  defp working_set_task_items(run, config, task_id, index) do
    with {:ok, task} <- find_task(run, task_id),
         :ok <- ensure_stratum(task, task_id, "working_set_long_context"),
         {:ok, working_set} <- required_map(task, ["working_set"], task_id),
         {:ok, baseline} <- required_map(working_set, ["baseline"], task_id),
         {:ok, treatment} <- required_map(working_set, ["treatment"], task_id) do
      inventory = candidate_ref_inventory(working_set)

      arms = [
        {"context_arm_A", baseline},
        {"context_arm_B", treatment}
      ]

      {:ok,
       Enum.map(arms, fn {blinded_arm, arm_result} ->
         context = arm_result["context"] || %{}
         selected_ids = selected_ref_ids(context)

         %{
           "packet_id" => "#{packet_prefix(config)}-ws-#{pad3(index)}-#{blinded_arm}",
           "label_status" => @not_yet_run,
           "metric_targets" => ["context_omission_error_rate", "working_set_relevance_score"],
           "review_mode" => "double_human_adjudicated",
           "task_id" => task_id,
           "blinded_arm" => blinded_arm,
           "context_artifact_id" => context_artifact_id(context),
           "task_packet_path" => redacted_task_packet_path(config, task_id),
           "source_artifact_dir" => source_artifact_dir(config, task_id),
           "candidate_ref_inventory" => inventory,
           "selected_ref_ids" => selected_ids,
           "omitted_ref_ids_visible_as_context_absent" =>
             omitted_visible_ref_ids(inventory, selected_ids),
           "token_budget" => token_budget(context),
           "primary_label_fields" => working_set_label_fields(),
           "adjudication_status" => @not_yet_run
         }
       end)}
    end
  end

  defp label_state(config) do
    if File.exists?(config.import_summary_abs) do
      with {:ok, summary} <- load_json(config.import_summary_abs),
           :ok <- validate_reported_import_summary(summary, config) do
        {:ok,
         %{
           kind: :complete_reported,
           packet_status: @complete_reported_packet_status,
           label_collection_status: @complete_reported,
           report_status: @reported_from_validated_primary_labels,
           metric_label_status: @complete_reported,
           adjudication_status: adjudication_status_from_summary(summary),
           import_summary: summary
         }}
      end
    else
      {:ok,
       %{
         kind: :not_yet_run,
         packet_status: "prepared_for_labeling",
         label_collection_status: @not_yet_run,
         report_status: @not_yet_run,
         metric_label_status: @not_yet_run,
         adjudication_status: @not_yet_run,
         import_summary: nil
       }}
    end
  end

  defp validate_reported_import_summary(summary, config) do
    checks = [
      {"import summary status", summary["status"], "ok"},
      {"import summary packet_id", summary["packet_id"], config.packet_id},
      {"import summary label_policy_version", summary["label_policy_version"],
       @label_policy_version},
      {"import summary label_collection_status", summary["label_collection_status"],
       @complete_reported}
    ]

    errors =
      checks
      |> Enum.reduce([], fn {label, actual, expected}, errors ->
        if actual == expected do
          errors
        else
          ["#{label} is #{inspect(actual)}, expected #{inspect(expected)}" | errors]
        end
      end)
      |> then(fn errors ->
        if File.exists?(config.label_results_abs) do
          errors
        else
          [
            "reported import summary exists but filled label results are missing: #{config.label_results_path}"
            | errors
          ]
        end
      end)

    if errors == [], do: :ok, else: {:error, Enum.reverse(errors)}
  end

  defp adjudication_status_from_summary(summary) do
    if summary["adjudication_required_count"] == 0 and
         summary["unhandled_adjudication_required_count"] == 0 and
         summary["adjudication_record_count"] == 0 do
      @completed_no_adjudication_records
    else
      "reported_from_import_summary"
    end
  end

  defp packet_manifest(config, run, evidence_items, working_set_items, label_state) do
    paths = artifact_paths(config, label_state)

    manifest = %{
      "packet_id" => config.packet_id,
      "packet_status" => label_state.packet_status,
      "label_collection_status" => label_state.label_collection_status,
      "label_policy_version" => @label_policy_version,
      "source_run" => %{
        "experiment_id" => run["experiment_id"],
        "sample_frame" => run["sample_frame_id"],
        "run_timestamp" => config.run_timestamp,
        "run_status" => run["status"],
        "threshold_status" => run["threshold_status"],
        "closure_status" => config.closure_status,
        "run_json_path" => config.run_json_path,
        "summary_path" => config.summary_path,
        "fixture_inventory_path" => config.fixture_inventory_path,
        "run_report_path" => config.run_report_path,
        "closure_path" => config.closure_path
      },
      "supersedes" => supersedes(config),
      "artifact_paths" => paths,
      "metric_scope" => %{
        "evidence_sufficiency_score" => %{
          "item_count" => length(evidence_items),
          "review_mode" => "double_human_adjudicated",
          "label_source" => "human",
          "label_status" => label_state.metric_label_status
        },
        "context_omission_error_rate" => %{
          "item_count" => length(working_set_items),
          "review_mode" => "double_human_adjudicated",
          "label_source" => "human",
          "label_status" => label_state.metric_label_status
        },
        "working_set_relevance_score" => %{
          "item_count" => length(working_set_items),
          "review_mode" => "double_human_adjudicated",
          "label_source" => "human",
          "label_status" => label_state.metric_label_status
        }
      },
      "candidate_sample_selection" => %{
        "evidence_sufficiency_score" =>
          "One treatment evidence unit from each major Lane A stratum, including the repaired selector-missing rejection artifact and one working-set long-context fixture.",
        "context_omission_error_rate" =>
          "All six working_set_long_context tasks from the accepted source run, with two blinded context arms per task.",
        "working_set_relevance_score" =>
          "Same twelve working-set/context items used for omission labeling."
      },
      "blinding_boundary" => blinding_boundary(),
      "adjudication" => %{
        "status" => label_state.adjudication_status,
        "record_path" => paths["adjudication_placeholders"],
        "required_triggers" => [
          "any reviewer marks needs_review",
          "ordinal labels differ by two or more levels",
          "evidence labels split across 0-2 versus 3-4",
          "reviewers disagree on task_critical, critical_omission, harmful, or metric denominator"
        ]
      },
      "claim_boundary" => claim_boundary(config, label_state)
    }

    if label_state.kind == :complete_reported do
      manifest
      |> Map.put("report_status", label_state.report_status)
      |> Map.put("label_import_summary", manifest_import_summary(config, label_state))
    else
      manifest
    end
  end

  defp artifact_paths(config, label_state) do
    base = %{
      "packet_readme" => path_join(config.out_path, "README.md"),
      "packet_manifest" => path_join(config.out_path, "packet_manifest.json"),
      "redacted_task_packets" =>
        ensure_trailing_slash(path_join(config.out_path, "redacted_task_packets")),
      "evidence_sufficiency_items" =>
        path_join(config.out_path, "evidence_sufficiency_items.jsonl"),
      "working_set_context_items" =>
        path_join(config.out_path, "working_set_context_items.jsonl"),
      "adjudication_placeholders" => path_join(config.out_path, "adjudication_placeholders.json"),
      "label_results_template" => path_join(config.out_path, "label_results_template.json"),
      "label_report" => config.label_report_path,
      "label_report_skeleton" => config.label_report_path
    }

    if label_state.kind == :complete_reported do
      base
      |> Map.put("label_results_primary_filled", config.label_results_path)
      |> Map.put("label_results_import_summary", config.import_summary_path)
      |> maybe_put_existing_path(
        "coordinator_primary_label_packet_freeze",
        config.coordinator_packet_freeze_abs,
        config.coordinator_packet_freeze_path
      )
    else
      base
    end
  end

  defp maybe_put_existing_path(map, key, abs_path, display_path) do
    if File.exists?(abs_path), do: Map.put(map, key, display_path), else: map
  end

  defp manifest_import_summary(config, %{import_summary: summary}) do
    %{
      "status" => "reported",
      "validation_status" => summary["status"],
      "summary_path" => config.import_summary_path,
      "result_path" => summary["result_path"] || config.label_results_path,
      "raw_label_counts" => summary["raw_label_counts"],
      "review_coverage" => summary["review_coverage"],
      "needs_review_count" => summary["needs_review_count"],
      "adjudication_required_count" => summary["adjudication_required_count"],
      "unhandled_adjudication_required_count" => summary["unhandled_adjudication_required_count"],
      "adjudication_record_count" => summary["adjudication_record_count"],
      "fixture_oracle_exposed_before_freeze" => summary["fixture_oracle_exposed_before_freeze"],
      "claim_boundary" => summary["claim_boundary"]
    }
  end

  defp claim_boundary(config, %{kind: :complete_reported}) do
    %{
      "allowed_after_report" =>
        "`#{config.run_timestamp}` active packet Lane B labeled evaluation evidence for the named packet and metrics only",
      "disallowed_after_report" => [
        "human-labeled broader evaluation evidence beyond this named packet",
        "new accepted_by_closure status beyond the Lane A source closure",
        "H1-H5 validation",
        "full Context OS validation",
        "production readiness",
        "runtime approval or human-in-the-loop verifier claim",
        "replacing the measured Lane A aggregate metrics with label results",
        "model-only baseline claims for OpenClaw local harness results"
      ]
    }
  end

  defp claim_boundary(_config, _label_state) do
    %{
      "allowed_before_labels" =>
        "prepared blinded Lane B label packet from the accepted Lane A closure run",
      "disallowed_before_labels" => [
        "human-labeled broader evaluation evidence",
        "new accepted_by_closure status beyond the Lane A source closure",
        "H1-H5 validation",
        "full Context OS validation",
        "production readiness",
        "runtime approval or human-in-the-loop verifier claim"
      ]
    }
  end

  defp supersedes(%{run_timestamp: @default_run_timestamp}) do
    %{
      "packet_id" => "PS1-LB-PACKET-20260530-141649-BATCH-001",
      "packet_path" => "docs/05_evaluation/label_packets/post_stage_1_lane_b_20260530_141649/",
      "reason" =>
        "The prior packet was prepared from a non-accepted Lane A run whose selector-missing item contained the pre-repair committed artifact. No labels had been collected, so the active packet is rebuilt from the accepted closure run."
    }
  end

  defp supersedes(_config), do: nil

  defp blinding_boundary do
    %{
      "visible_to_primary_labelers" => [
        "item JSONL records in this packet",
        "redacted task packet paths and fixture input artifact paths referenced by each item",
        "redacted candidate-ref inventories without fixture oracle role fields",
        "blinded context arm names context_arm_A and context_arm_B",
        "evidence packet, action, verifier output, and journal fields copied into evidence item records"
      ],
      "withheld_until_label_freeze" => [
        "fixture oracle role fields required_refs, relevant_refs, irrelevant_refs, and omission_trap_refs",
        "expected_runtime_status and expected_label_source",
        "expected failure labels",
        "original input_artifacts.role and input_artifacts.description fields from fixture task.json files",
        "task success flags from the source run",
        "aggregate Lane A metric values for the item under review",
        "context arm identity mapping from blinded arm name to baseline or treatment",
        "post-run focused repair notes when judging the measured artifact"
      ],
      "coordinator_only_before_label_freeze" => [
        "source run.json",
        "source summary.md",
        "source fixture_inventory.md",
        "original fixture task.json files",
        "Lane A run report",
        "Lane A closure"
      ],
      "fixture_oracle_exposure_for_adjudication" =>
        "Allowed only after primary labels are frozen and must be recorded per adjudication record."
    }
  end

  defp adjudication_placeholders(config, evidence_items, working_set_items) do
    evidence_ids = Enum.map(evidence_items, & &1["packet_id"])
    working_set_ids = Enum.map(working_set_items, & &1["packet_id"])

    %{
      "packet_id" => config.packet_id,
      "status" => @not_yet_run,
      "label_policy_version" => @label_policy_version,
      "review_mode" => "double_human_adjudicated",
      "evidence_sufficiency_score" => %{
        "item_ids" => evidence_ids,
        "adjudication_required_when" => [
          "any reviewer marks needs_review",
          "raw labels differ by two or more levels",
          "reviewers split across 0-2 versus 3-4 acceptability boundary"
        ],
        "records" => [],
        "unresolved_needs_review_count" => @not_yet_run
      },
      "context_omission_error_rate" => %{
        "item_ids" => working_set_ids,
        "adjudication_required_when" => [
          "reviewers disagree on task_critical",
          "reviewers disagree on critical_omission",
          "reviewers disagree on denominator",
          "any reviewer marks needs_review"
        ],
        "records" => [],
        "unresolved_needs_review_count" => @not_yet_run
      },
      "working_set_relevance_score" => %{
        "item_ids" => working_set_ids,
        "adjudication_required_when" => [
          "reviewers disagree on task_critical",
          "reviewers disagree on supporting versus irrelevant or harmful",
          "any reviewer marks harmful",
          "any reviewer marks needs_review"
        ],
        "records" => [],
        "unresolved_needs_review_count" => @not_yet_run
      },
      "fixture_oracle_exposure" => %{
        "primary_labelers" => "withheld until labels are frozen",
        "adjudicator" =>
          "allowed only after primary labels are frozen and must be recorded per adjudication record"
      }
    }
  end

  defp packet_readme(config, %{kind: :complete_reported} = label_state) do
    existing_text_or(
      Path.join(config.out_abs, "README.md"),
      [@complete_reported, "label_results_import_summary.json"],
      fn -> reported_packet_readme(config, label_state) end
    )
  end

  defp packet_readme(config, _label_state) do
    """
    # Post-Stage-1 Lane B #{config.run_timestamp} Blinded Label Packet

    ## Purpose

    This packet is the active blinded Lane B labeling batch prepared from the
    `#{config.run_timestamp}` Lane A rerun that is `accepted_by_closure` for the named
    threshold-governed Document Ops Lane A sample.

    It prepares artifact packets for:

    - `evidence_sufficiency_score`
    - `context_omission_error_rate`
    - `working_set_relevance_score`

    It does not contain human labels, secondary-review labels, adjudicated labels,
    or inter-annotator agreement results. Label collection status is
    `Not yet run`.

    ## Packet Contents

    | Artifact | Purpose |
    | --- | --- |
    | `packet_manifest.json` | Coordinator manifest, source run linkage, review mode, blinding boundary, supersession note, and artifact paths. |
    | `redacted_task_packets/` | Primary-labeler task packets with fixture oracle role and description fields removed from `input_artifacts`. |
    | `evidence_sufficiency_items.jsonl` | Eight blinded evidence sufficiency label items sampled from the accepted run artifact. |
    | `working_set_context_items.jsonl` | Twelve blinded working-set omission and relevance items: six long-context tasks by two blinded context arms. |
    | `adjudication_placeholders.json` | Empty adjudication record scaffold and trigger rules. |
    | `label_results_template.json` | Packet-local label result import template for `PS1-LB-LABEL-001`; not a core runtime schema. |
    | `../../Post_Stage_1_Lane_B_#{config.run_timestamp}_Label_Report_Skeleton.md` | Report skeleton for recording labels after collection. |

    ## Source Run

    - Source Lane A run:
      `#{config.run_json_path}`
    - Source run report:
      `#{config.run_report_path}`
    - Source closure:
      `#{config.closure_path}`
    - Label policy version: `#{@label_policy_version}`
    - Gate policy for context expansion planning: `#{@context_gate_policy_version}`
    - Source run threshold status: `pass_acceptance_candidate`
    - Source run closure status: `#{config.closure_status}`

    The source run remains a Lane A measured run. This Lane B packet is an
    evaluation-labeling artifact only and does not change the measured Lane A
    metrics or create any new closure status.

    ## Supersession Boundary

    This packet supersedes the prepared `20260530_141649` Lane B packet as the
    active labeling packet because the older packet was extracted from a Lane A run
    that was not `accepted_by_closure` and still contained the pre-repair
    `docops_struct_selector_missing_001` committed artifact. No human labels,
    secondary review, adjudication, or agreement reporting had been collected for
    that older packet.

    The older packet may remain in the repository only as a historical packet for
    that non-accepted source run. It must not be used as the current Lane B label
    source for accepted post-Stage-1 routing unless a future report explicitly
    chooses to label that historical run and states why.

    ## Review Modes

    | Metric | Review mode | Label collection status |
    | --- | --- | --- |
    | `evidence_sufficiency_score` | `double_human_adjudicated` | `Not yet run` |
    | `context_omission_error_rate` | `double_human_adjudicated` | `Not yet run` |
    | `working_set_relevance_score` | `double_human_adjudicated` | `Not yet run` |

    Double human annotation is the default for this first active packet. A
    documented secondary review may be used only if a later report records the
    substitution and still satisfies `#{@label_policy_version}`.

    ## Blinding Boundary

    Primary labelers may see:

    - the item JSONL records in this packet
    - redacted task packets and fixture input artifacts referenced by item paths
    - redacted candidate-ref inventories without fixture oracle role fields
    - anonymized context arm names, `context_arm_A` and `context_arm_B`
    - evidence packet, action, verifier output, and journal fields copied into the
      evidence item records

    Primary labelers must not see before labels are frozen:

    - fixture oracle fields such as `required_refs`, `relevant_refs`,
      `irrelevant_refs`, `omission_trap_refs`, `expected_runtime_status`,
      `expected_label_source`, expected failure labels, and original
      `input_artifacts.role` or `input_artifacts.description` fields
    - aggregate Lane A metric results for the item under review
    - context arm identity mapping from `context_arm_A` or `context_arm_B` to
      baseline or treatment
    - task success flags from the source run
    - post-run repair notes when labeling the measured artifact

    Coordinator-only source artifacts, including the original fixture `task.json`
    files, may be used after primary labels are frozen for scoring, secondary
    review, or adjudication. Any exposure during adjudication must be recorded in
    `adjudication_placeholders.json` or its filled successor.

    ## Post-Freeze Unblind Guard

    `mix vanta.post_stage_1_lane_b_packet --mode check` includes an executable
    post-freeze unblind guard over reviewer-visible JSONL, redacted task packets,
    `label_results_template.json`, and any packet-local result scaffold present.
    The guard rejects coordinator-only arm mapping fields, source arm labels, and
    post-freeze memo markers. It does not unblind, rewrite, or expand the frozen
    item files.

    ## Candidate Sample

    The evidence sufficiency batch uses one sampled treatment evidence unit from
    each major Lane A stratum:

    | Item | Task | Stratum |
    | --- | --- | --- |
    #{evidence_readme_rows(config)}

    The working-set batch covers all six `working_set_long_context` tasks from the
    accepted run, each under two blinded context arms.

    ## Label Output Fields

    Evidence sufficiency item labels must fill:

    - raw `0-4` label or `needs_review`
    - normalized score, after adjudication only
    - reviewer ID or anonymized reviewer ID
    - confidence
    - rationale
    - referenced artifact IDs

    Working-set item labels must fill:

    - omission severity
    - omitted task-critical ref IDs
    - task-critical candidate ref IDs
    - per-ref relevance labels
    - packet relevance quality
    - reviewer ID or anonymized reviewer ID
    - confidence
    - rationale

    All fields are currently `Not yet run`.

    ## Label Result Import Path

    The packet-local result format is `PS1-LB-LABEL-RESULT-LOCAL-001`, with
    `label_policy_version: #{@label_policy_version}`. It is a collection and
    validation aid for this Lane B packet only; it does not expand the core
    runtime schemas in `docs/03_schemas/`.

    Use `label_results_template.json` as the starting structure for imported
    raw labels. Before any report claim, validate a filled results file with:

    ```text
    mix vanta.post_stage_1_lane_b_label_results --mode validate --results <filled-results.json>
    ```

    To produce a machine-readable import summary for filling the report after
    real labels are collected, use:

    ```text
    mix vanta.post_stage_1_lane_b_label_results --mode import-summary --results <filled-results.json> --out <summary.json>
    ```

    These commands must not be used to treat templates, dry-run fixtures, or
    generated test data as real human labels.

    ## Interpretation Boundary

    This packet may support a future Lane B label report after labels are collected
    and adjudicated. Until then it may only be described as a prepared blinded label
    packet from the accepted Lane A source run. It must not be described as
    human-labeled evidence, H1-H5 validation, full Context OS validation,
    production readiness, a runtime approval path, or new closure acceptance beyond
    the Lane A `#{config.run_timestamp}` closure.
    """
  end

  defp reported_packet_readme(config, %{import_summary: summary}) do
    evidence_count = get_in(summary, ["raw_label_counts", "evidence_sufficiency_score"]) || 0
    working_count = get_in(summary, ["raw_label_counts", "working_set_context"]) || 0

    """
    # Post-Stage-1 Lane B #{config.run_timestamp} Blinded Label Packet

    ## Purpose

    This packet is the active blinded Lane B labeling batch prepared from the
    `#{config.run_timestamp}` Lane A rerun that is `accepted_by_closure` for the named
    threshold-governed Document Ops Lane A sample.

    The prepared item files remain the frozen primary-labeler-visible packet.
    The packet directory also contains the filled primary label result file and
    import summary for this active packet. Label collection status is
    `#{@complete_reported}`.

    For this packet, `#{@complete_reported}` means the primary labels were collected,
    frozen, validated, import-summarized, and reported in the companion Lane B
    label report. It is a packet-local evaluation status only and does not create a
    runtime approval or broader validation claim.

    ## Packet Contents

    | Artifact | Purpose |
    | --- | --- |
    | `packet_manifest.json` | Coordinator manifest, source run linkage, review mode, blinding boundary, supersession note, label status, and artifact paths. |
    | `redacted_task_packets/` | Primary-labeler task packets with fixture oracle role and description fields removed from `input_artifacts`. |
    | `evidence_sufficiency_items.jsonl` | Eight blinded evidence sufficiency label items sampled from the accepted run artifact. |
    | `working_set_context_items.jsonl` | Twelve blinded working-set omission and relevance items: six long-context tasks by two blinded context arms. |
    | `adjudication_placeholders.json` | Adjudication record scaffold and trigger rules; no records were required by the validator for the reported import summary. |
    | `label_results_template.json` | Packet-local label result import template for `#{@label_policy_version}`; not a core runtime schema. |
    | `label_results_primary_filled.json` | Filled packet-local primary label result file. |
    | `label_results_import_summary.json` | Machine-readable validation/import summary for the filled primary label result file. |
    | `../../Post_Stage_1_Lane_B_#{config.run_timestamp}_Label_Report_Skeleton.md` | Filled label report for this active packet. |

    ## Source Run

    - Source Lane A run:
      `#{config.run_json_path}`
    - Source run report:
      `#{config.run_report_path}`
    - Source closure:
      `#{config.closure_path}`
    - Label policy version: `#{@label_policy_version}`
    - Gate policy for context expansion planning: `#{@context_gate_policy_version}`
    - Source run threshold status: `pass_acceptance_candidate`
    - Source run closure status: `#{config.closure_status}`

    The source run remains a Lane A measured run. This Lane B packet is an
    evaluation-labeling artifact only and does not change the measured Lane A
    metrics or create any new closure status.

    ## Review Modes

    | Metric | Review mode | Label collection status |
    | --- | --- | --- |
    | `evidence_sufficiency_score` | `double_human_adjudicated` | `#{@complete_reported}` |
    | `context_omission_error_rate` | `double_human_adjudicated` | `#{@complete_reported}` |
    | `working_set_relevance_score` | `double_human_adjudicated` | `#{@complete_reported}` |

    ## Post-Freeze Unblind Guard

    `mix vanta.post_stage_1_lane_b_packet --mode check` includes an executable
    post-freeze unblind guard over reviewer-visible JSONL, redacted task packets,
    `label_results_template.json`, and any packet-local result scaffold present.
    The guard rejects coordinator-only arm mapping fields, source arm labels, and
    post-freeze memo markers. It does not unblind, rewrite, or expand the frozen
    item files.

    ## Label Result Import Path

    Validated import summary:

    - Summary path: `#{config.import_summary_path}`
    - Result path: `#{summary["result_path"] || config.label_results_path}`
    - Raw label counts:
      `evidence_sufficiency_score = #{evidence_count}`,
      `working_set_context = #{working_count}`
    - Needs review count: #{summary["needs_review_count"]}
    - Adjudication required count: #{summary["adjudication_required_count"]}
    - Unhandled adjudication required count:
      #{summary["unhandled_adjudication_required_count"]}
    - Fixture oracle exposed before freeze:
      `#{summary["fixture_oracle_exposed_before_freeze"]}`

    These commands must not be used to treat templates, dry-run fixtures, or
    generated test data as real human labels.

    ## Interpretation Boundary

    This packet supports the filled Lane B label report for the named
    `#{config.run_timestamp}` active packet. It may be described only as Lane B
    labeled evaluation evidence for the named packet and metrics. It must not be
    described as H1-H5 validation, full Context OS validation, production
    readiness, a runtime approval path, or new closure acceptance beyond the Lane A
    `#{config.run_timestamp}` closure.
    """
  end

  defp label_report_skeleton(config, %{kind: :complete_reported} = label_state) do
    existing_text_or(
      config.label_report_abs,
      [
        @complete_reported,
        @reported_from_validated_primary_labels,
        "label_results_import_summary.json"
      ],
      fn -> reported_label_report(config, label_state) end
    )
  end

  defp label_report_skeleton(config, _label_state) do
    """
    # Post-Stage-1 Lane B #{config.run_timestamp} Label Report Skeleton

    ## Experiment

    - Source experiment ID: `#{@experiment_id}`
    - Source sample frame: `#{@sample_frame}`
    - Source Lane A run timestamp: `#{config.run_timestamp}`
    - Source Lane A closure status: `#{config.closure_status}`
    - Lane B packet ID: `#{config.packet_id}`
    - Label policy version: `#{@label_policy_version}`
    - Metric policy version: `#{@metric_policy_version}`
    - Context gate policy version: `#{@context_gate_policy_version}`
    - Label collection status: `Not yet run`
    - Report status: `Not yet run`
    - Claim level before labels: prepared blinded label packet only

    ## Source Artifacts

    | Artifact | Path |
    | --- | --- |
    | Source run JSON | `#{config.run_json_path}` |
    | Source run summary | `#{config.summary_path}` |
    | Source fixture inventory | `#{config.fixture_inventory_path}` |
    | Lane A run report | `#{config.run_report_path}` |
    | Lane A closure | `#{config.closure_path}` |
    | Label packet manifest | `#{path_join(config.out_path, "packet_manifest.json")}` |
    | Redacted task packets | `#{ensure_trailing_slash(path_join(config.out_path, "redacted_task_packets"))}` |
    | Evidence sufficiency items | `#{path_join(config.out_path, "evidence_sufficiency_items.jsonl")}` |
    | Working-set context items | `#{path_join(config.out_path, "working_set_context_items.jsonl")}` |
    | Adjudication placeholders | `#{path_join(config.out_path, "adjudication_placeholders.json")}` |
    | Label result import template | `#{path_join(config.out_path, "label_results_template.json")}` |

    ## Supersession Boundary

    This report skeleton supersedes
    `Post_Stage_1_Lane_B_20260530_141649_Label_Report_Skeleton.md` as the active
    Lane B reporting shell. The older skeleton remains a historical shell for the
    non-accepted `20260530_141649` source run and its prepared packet only.

    The older packet must not be used as the current Lane B source for accepted
    post-Stage-1 routing because its source run was not `accepted_by_closure` and
    its `docops_struct_selector_missing_001` item records the pre-repair committed
    artifact. No labels had been collected for that older packet before this
    rebuild.

    ## Labeling Contract

    | Metric | Item count | Review mode | Label source | Status |
    | --- | ---: | --- | --- | --- |
    | `evidence_sufficiency_score` | 8 | `double_human_adjudicated` | `human` | `Not yet run` |
    | `context_omission_error_rate` | 12 | `double_human_adjudicated` | `human` | `Not yet run` |
    | `working_set_relevance_score` | 12 | `double_human_adjudicated` | `human` | `Not yet run` |

    Reviewer identity policy: anonymized reviewer IDs are allowed, but each raw
    label must preserve a stable reviewer ID.

    Fixture oracle metadata exposed before label freeze: `no`.

    Blinding policy: primary labelers see only the packet item records, referenced
    redacted task packets, fixture input artifacts, redacted candidate-ref
    inventories, and blinded context arm names. Fixture oracle role fields, original
    `input_artifacts.role` and `input_artifacts.description` fields, arm identity
    mapping, expected labels, task success flags, aggregate item metrics, and
    post-run repair notes remain withheld until labels are frozen.

    The packet-local label result format is
    `PS1-LB-LABEL-RESULT-LOCAL-001`. It is a local collection/import template
    for this Lane B packet and does not extend core runtime schemas.

    ## Collection, Import, Validation, And Reporting Flow

    Label collection remains `Not yet run` until real reviewer labels are
    imported from a filled result file and validated under `#{@label_policy_version}`.
    The template file is not label evidence.

    Reviewer fields for evidence sufficiency raw labels:

    - `metric: evidence_sufficiency_score`
    - `item_id`
    - `label_source: human`
    - `reviewer_id`
    - `raw_label_0_to_4_or_needs_review`
    - `confidence`
    - `rationale`
    - `referenced_artifact_ids`

    Reviewer fields for working-set raw labels:

    - `metric: working_set_context`
    - `item_id`
    - `label_source: human`
    - `reviewer_id`
    - `omission` fields for severity, omitted task-critical refs,
      task-critical candidate refs, `critical_omission`, and denominator refs
    - `per_ref_relevance_labels`
    - `packet_relevance_quality`
    - `confidence`
    - `rationale`
    - `referenced_artifact_ids`

    Required sequence:

    1. Freeze the blinded packet and distribute only primary-labeler-visible
       packet files.
    2. Collect raw primary labels with stable reviewer IDs and no fixture oracle
       exposure.
    3. Freeze primary labels before fixture oracle fields, arm identity mapping,
       source task oracle fields, or aggregate Lane A item results are exposed.
    4. Validate the filled result file with
       `mix vanta.post_stage_1_lane_b_label_results --mode validate --results <filled-results.json>`.
    5. Complete documented secondary review only if the report records the
       substitution allowed by `#{@label_policy_version}`.
    6. Complete adjudication records for all validator-triggered disagreements,
       `needs_review` labels, evidence `0-2` versus `3-4` splits, harmful
       relevance labels, task-critical disputes, critical-omission disputes, and
       denominator disputes.
    7. Produce an import summary with
       `mix vanta.post_stage_1_lane_b_label_results --mode import-summary --results <filled-results.json> --out <summary.json>`.
    8. Fill this report only from real labels, adjudicated labels, agreement
       counts, fixture-oracle exposure metadata, and the validated import
       summary.

    ## Candidate Sample

    Evidence sufficiency candidates:

    | Item | Task | Stratum | Source item file |
    | --- | --- | --- | --- |
    #{evidence_report_rows(config)}

    Working-set candidates:

    | Task | Blinded arms | Source item file |
    | --- | --- | --- |
    #{working_set_report_rows()}

    ## Label Results

    Human labels have not been collected.

    | Metric | Raw labels | Adjudicated labels | Score | `needs_review` count | Status |
    | --- | --- | --- | --- | --- | --- |
    | `evidence_sufficiency_score` | `Not yet run` | `Not yet run` | `Not yet run` | `Not yet run` | `Not yet run` |
    | `context_omission_error_rate` | `Not yet run` | `Not yet run` | `Not yet run` | `Not yet run` | `Not yet run` |
    | `working_set_relevance_score` | `Not yet run` | `Not yet run` | `Not yet run` | `Not yet run` | `Not yet run` |

    ## Adjudication

    Adjudication status: `Not yet run`.

    Required adjudication triggers:

    - any reviewer marks `needs_review`
    - evidence sufficiency labels differ by two or more levels
    - evidence sufficiency labels split across the `0-2` versus `3-4`
      acceptability boundary
    - reviewers disagree on `task_critical`, `critical_omission`, `harmful`, or
      denominator fields for working-set metrics

    Adjudication records must include original labels, adjudicated label,
    adjudicator ID, rationale, artifact refs inspected, and whether fixture oracle
    metadata was exposed.

    ## Agreement

    Inter-annotator agreement: `Not yet run`.

    If this first active batch remains too small for stable agreement statistics,
    report raw agreement counts and state that agreement statistics are not
    meaningful at the sample size.

    ## Interpretation Boundaries

    Allowed before labels are collected:

    - The `#{config.run_timestamp}` Lane A closure run has a prepared blinded Lane B label
      packet.
    - The packet includes candidate artifact paths, review modes, blinding
      boundary, supersession boundary, and adjudication placeholders for the three
      named metrics.

    Disallowed before labels are collected:

    - human-labeled broader evaluation evidence
    - new `accepted_by_closure` status beyond the Lane A source closure
    - H1-H5 validation
    - full Context OS validation
    - production readiness
    - human-in-the-loop verifier or runtime approval claims
    - replacing the measured Lane A aggregate metrics with label results

    ## Findings

    `Not yet run`.

    ## Failures And Risks

    `Not yet run`.

    ## Next Steps

    1. Freeze the primary labeling packet and distribute only the blinded item
       files and referenced source artifacts to reviewers.
    2. Collect two independent labels per item or record an allowed secondary
       review substitution.
    3. Freeze primary labels before exposing fixture oracle fields or arm identity
       mappings.
    4. Complete adjudication records for all required disagreements.
    5. Fill this report with raw labels, adjudicated labels, agreement counts, and
       interpretation boundaries.
    """
  end

  defp reported_label_report(config, %{import_summary: summary}) do
    evidence_count = get_in(summary, ["raw_label_counts", "evidence_sufficiency_score"]) || 0
    working_count = get_in(summary, ["raw_label_counts", "working_set_context"]) || 0

    """
    # Post-Stage-1 Lane B #{config.run_timestamp} Label Report

    ## Experiment

    - Source experiment ID: `#{@experiment_id}`
    - Source sample frame: `#{@sample_frame}`
    - Source Lane A run timestamp: `#{config.run_timestamp}`
    - Source Lane A closure status: `#{config.closure_status}`
    - Lane B packet ID: `#{config.packet_id}`
    - Label policy version: `#{@label_policy_version}`
    - Metric policy version: `#{@metric_policy_version}`
    - Context gate policy version: `#{@context_gate_policy_version}`
    - Label collection status: `#{@complete_reported}`
    - Report status: `#{@reported_from_validated_primary_labels}`
    - Claim level after labels: `#{config.run_timestamp}` active packet Lane B
      labeled evaluation evidence only

    For this packet, `#{@complete_reported}` means the primary labels were collected,
    frozen, validated, import-summarized, and reported in this Lane B label report.
    It is a packet-local evaluation status only and does not create a runtime
    approval or broader validation claim.

    ## Source Artifacts

    | Artifact | Path |
    | --- | --- |
    | Source run JSON | `#{config.run_json_path}` |
    | Source run summary | `#{config.summary_path}` |
    | Source fixture inventory | `#{config.fixture_inventory_path}` |
    | Lane A run report | `#{config.run_report_path}` |
    | Lane A closure | `#{config.closure_path}` |
    | Label packet manifest | `#{path_join(config.out_path, "packet_manifest.json")}` |
    | Filled primary label results | `#{summary["result_path"] || config.label_results_path}` |
    | Import summary | `#{config.import_summary_path}` |

    ## Label Results

    | Metric | Raw labels | Status |
    | --- | ---: | --- |
    | `evidence_sufficiency_score` | #{evidence_count} | `#{@complete_reported}` |
    | `context_omission_error_rate` | #{working_count} | `#{@complete_reported}` |
    | `working_set_relevance_score` | #{working_count} | `#{@complete_reported}` |

    ## Import Summary

    Validated import summary:

    - Summary path: `#{config.import_summary_path}`
    - Result path: `#{summary["result_path"] || config.label_results_path}`
    - Needs review count: #{summary["needs_review_count"]}
    - Adjudication required count: #{summary["adjudication_required_count"]}
    - Unhandled adjudication required count:
      #{summary["unhandled_adjudication_required_count"]}
    - Fixture oracle exposed before freeze:
      `#{summary["fixture_oracle_exposed_before_freeze"]}`

    ## Interpretation Boundaries

    Allowed after this report:

    - The `#{config.run_timestamp}` Lane A closure run has a completed active Lane B
      label packet with primary labels, primary label freeze, validation, raw
      agreement counts, and import summary under `#{@label_policy_version}`.
    - The labels are Lane B labeled evaluation evidence for the named active
      packet and the named metrics only.

    Disallowed:

    - new `accepted_by_closure` status beyond the Lane A source closure
    - H1-H5 validation
    - full Context OS validation
    - production readiness
    - human-in-the-loop verifier or runtime approval claims
    - replacing the measured Lane A aggregate metrics with label results
    - model-only baseline claims for OpenClaw local harness results
    """
  end

  defp evidence_readme_rows(config) do
    @evidence_sample
    |> Enum.with_index(1)
    |> Enum.map(fn {{task_id, stratum}, index} ->
      "| `#{packet_prefix(config)}-es-#{pad3(index)}` | `#{task_id}` | `#{stratum}` |"
    end)
    |> Enum.join("\n")
  end

  defp evidence_report_rows(config) do
    @evidence_sample
    |> Enum.with_index(1)
    |> Enum.map(fn {{task_id, stratum}, index} ->
      "| `#{packet_prefix(config)}-es-#{pad3(index)}` | `#{task_id}` | `#{stratum}` | `evidence_sufficiency_items.jsonl` |"
    end)
    |> Enum.join("\n")
  end

  defp working_set_report_rows do
    @working_set_task_ids
    |> Enum.map(fn task_id ->
      "| `#{task_id}` | `context_arm_A`, `context_arm_B` | `working_set_context_items.jsonl` |"
    end)
    |> Enum.join("\n")
  end

  defp compact_evidence_packet(packet) do
    packet
    |> Map.take(~w(
        evidence_id
        episode_id
        step_id
        action_ref
        pre_state_hash
        post_state_hash
        pre_state_summary
        post_state_summary
        observation
        provenance
        runtime_context
        violated_constraints
      ))
    |> update_in(["observation"], fn
      observation when is_map(observation) -> Map.drop(observation, ["content"])
      observation -> observation
    end)
  end

  defp compact_action_under_review(step) do
    Map.take(step, ~w(
      action_type
      action_payload
      side_effect_class
      status
      preconditions
      postconditions
      rollback_policy
      verifier_requirements
    ))
  end

  defp compact_verifier_output(output) do
    Map.take(output, ~w(
      verifier_output_id
      decision
      confidence
      risk_score
      validity_score
      verification_scope
      violated_constraints
      required_extra_evidence
    ))
  end

  defp compact_commit_record(journal) do
    Map.take(journal, ~w(
      episode_id
      commit_status
      rollback_status
      evidence_refs
      verifier_output_refs
      state_hashes
    ))
  end

  defp candidate_ref_inventory(working_set) do
    refs =
      [
        get_in(working_set, ["baseline", "context", "included_refs"]),
        get_in(working_set, ["baseline", "context", "dropped_refs"]),
        get_in(working_set, ["treatment", "context", "working_set", "provenance", "included_refs"]),
        get_in(working_set, ["treatment", "context", "selected_refs"]),
        get_in(working_set, ["treatment", "context", "omitted_refs"])
      ]
      |> Enum.flat_map(&List.wrap/1)

    refs
    |> Enum.reduce(%{}, fn ref, acc ->
      ref_id = ref["ref_id"]

      if present?(ref_id) do
        Map.update(acc, ref_id, ref, &merge_ref(&1, ref))
      else
        acc
      end
    end)
    |> Map.values()
    |> Enum.sort_by(& &1["ref_id"])
    |> Enum.map(&Map.take(&1, ~w(ref_id kind source path content_hash)))
  end

  defp merge_ref(left, right) do
    Map.merge(left, right, fn _key, old, new ->
      if present?(new), do: new, else: old
    end)
  end

  defp selected_ref_ids(%{"working_set" => %{"provenance" => %{"included_refs" => refs}}}),
    do: Enum.map(refs, & &1["ref_id"])

  defp selected_ref_ids(%{"selected_refs" => refs}) when is_list(refs),
    do: Enum.map(refs, & &1["ref_id"])

  defp selected_ref_ids(%{"included_refs" => refs}) when is_list(refs),
    do: Enum.map(refs, & &1["ref_id"])

  defp selected_ref_ids(_context), do: []

  defp omitted_visible_ref_ids(inventory, selected_ids) do
    selected = MapSet.new(selected_ids)

    inventory
    |> Enum.map(& &1["ref_id"])
    |> Enum.reject(&MapSet.member?(selected, &1))
  end

  defp context_artifact_id(%{"artifact_id" => artifact_id}), do: artifact_id

  defp context_artifact_id(%{"working_set" => %{"working_set_id" => working_set_id}}),
    do: working_set_id

  defp context_artifact_id(_context), do: nil

  defp token_budget(%{"working_set" => %{"token_budget" => token_budget}}), do: token_budget

  defp token_budget(context) do
    Map.take(context, ~w(
      max_context_chars
      selected_context_chars
      estimated_tokens
      estimation_method
      budget_adhered
    ))
  end

  defp evidence_label_fields do
    %{
      "raw_label_0_to_4_or_needs_review" => @not_yet_run,
      "normalized_score" => @not_yet_run,
      "reviewer_id" => @not_yet_run,
      "confidence" => @not_yet_run,
      "rationale" => @not_yet_run,
      "referenced_artifact_ids" => @not_yet_run
    }
  end

  defp working_set_label_fields do
    %{
      "omission_severity" => @not_yet_run,
      "omitted_task_critical_ref_ids" => @not_yet_run,
      "task_critical_candidate_ref_ids" => @not_yet_run,
      "per_ref_relevance_labels" => @not_yet_run,
      "packet_relevance_quality" => @not_yet_run,
      "reviewer_id" => @not_yet_run,
      "confidence" => @not_yet_run,
      "rationale" => @not_yet_run
    }
  end

  defp find_task(run, task_id) do
    case Enum.find(run["tasks"] || [], &(&1["task_id"] == task_id)) do
      nil -> {:error, ["source run is missing task #{task_id}"]}
      task -> {:ok, task}
    end
  end

  defp ensure_stratum(%{"stratum" => stratum}, _task_id, stratum), do: :ok

  defp ensure_stratum(task, task_id, expected_stratum) do
    {:error,
     [
       "#{task_id} stratum is #{inspect(task["stratum"])}, expected #{inspect(expected_stratum)}"
     ]}
  end

  defp required_map(map, keys, label) do
    case get_in(map, keys) do
      value when is_map(value) -> {:ok, value}
      _other -> {:error, ["#{label} is missing #{Enum.join(keys, ".")}"]}
    end
  end

  defp first_item(list, _label) when is_list(list) and list != [], do: {:ok, hd(list)}
  defp first_item(_list, label), do: {:error, ["missing #{label}"]}

  defp packet_task_ids do
    @evidence_sample
    |> Enum.map(fn {task_id, _stratum} -> task_id end)
    |> Kernel.++(@working_set_task_ids)
    |> Enum.uniq()
  end

  defp redacted_task_packet_path(config, task_id) do
    path_join(config.out_path, "redacted_task_packets/#{task_id}.json")
  end

  defp source_artifact_dir(config, task_id) do
    config.fixtures_path
    |> path_join("#{task_id}/inputs")
    |> ensure_trailing_slash()
  end

  defp packet_id(run_timestamp) do
    [date, time] = String.split(run_timestamp, "_", parts: 2)
    "PS1-LB-PACKET-#{date}-#{time}-BATCH-001"
  end

  defp packet_prefix(%{packet_date: packet_date}), do: "lb#{packet_date}"
  defp packet_date(run_timestamp), do: run_timestamp |> String.split("_") |> hd()

  defp pad3(number) do
    number
    |> Integer.to_string()
    |> String.pad_leading(3, "0")
  end
end
