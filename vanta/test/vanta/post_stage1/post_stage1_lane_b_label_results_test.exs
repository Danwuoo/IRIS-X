defmodule Vanta.PostStage1LaneBLabelResultsTest do
  use ExUnit.Case

  alias Vanta.PostStage1LaneBLabelResults
  alias Vanta.PostStage1LaneBPacket

  @packet_opts [
    run_timestamp: "20260601_113121",
    run_json: "docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/run.json",
    run_report: "docs/05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md",
    closure: "docs/00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md",
    fixtures: "docs/04_experiments/fixtures/document_ops",
    out: "docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121"
  ]

  @label_opts [
    packet_dir: "docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121"
  ]

  @filled_results_path "docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_primary_filled.json"
  @import_summary_path "docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_import_summary.json"
  @label_report_path "docs/05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md"
  @context_os_eval_plan_path "docs/04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md"

  @tag :generated_artifact_tooling
  test "template is a Not yet run packet-local result scaffold" do
    assert {:ok, template} = PostStage1LaneBLabelResults.template(@label_opts)

    assert template["result_format"] == "PS1-LB-LABEL-RESULT-LOCAL-001"
    assert template["label_policy_version"] == "PS1-LB-LABEL-001"
    assert template["label_collection_status"] == "Not yet run"
    assert template["raw_labels"]["evidence_sufficiency_score"] == []
    assert template["raw_labels"]["working_set_context"] == []
    assert template["adjudication_records"] == []
    assert get_in(template, ["agreement_report", "status"]) == "Not yet run"
  end

  @tag :generated_artifact_tooling
  test "validates template file without treating it as collected labels" do
    assert {:ok, template} = PostStage1LaneBLabelResults.template(@label_opts)
    path = write_temp_json(template)

    assert {:ok, summary} = PostStage1LaneBLabelResults.validate_file(path, @label_opts)
    assert summary["label_collection_status"] == "Not yet run"
    assert summary["raw_label_counts"]["evidence_sufficiency_score"] == 0
    assert summary["raw_label_counts"]["working_set_context"] == 0
    assert summary["adjudication_required_count"] == 0
    assert String.contains?(summary["claim_boundary"], "packet-local Lane B label report")
    refute String.contains?(summary["claim_boundary"], "until real labels")
  end

  @tag :generated_artifact_tooling
  test "validates in-progress dry-run raw labels and reports pending triggers" do
    assert {:ok, packet} = PostStage1LaneBPacket.build(@packet_opts)
    assert {:ok, result} = in_progress_result(packet)

    [evidence_label] = result["raw_labels"]["evidence_sufficiency_score"]

    needs_review_result =
      put_in(result, ["raw_labels", "evidence_sufficiency_score"], [
        %{evidence_label | "raw_label_0_to_4_or_needs_review" => "needs_review"}
      ])

    path = write_temp_json(needs_review_result)

    assert {:ok, summary} = PostStage1LaneBLabelResults.validate_file(path, @label_opts)
    assert summary["label_collection_status"] == "in_progress"
    assert summary["raw_label_counts"]["evidence_sufficiency_score"] == 1
    assert summary["raw_label_counts"]["working_set_context"] == 1
    assert summary["needs_review_count"] == 1
    assert summary["adjudication_required_count"] == 1
    assert summary["unhandled_adjudication_required_count"] == 1
    assert String.contains?(summary["claim_boundary"], "not broad validation")
  end

  @tag :generated_artifact_tooling
  test "validates reported primary labels without requiring the old pending-report status" do
    assert {:ok, summary} =
             PostStage1LaneBLabelResults.validate_file(@filled_results_path, @label_opts)

    assert summary["label_collection_status"] == "complete_reported"
    assert summary["raw_label_counts"]["evidence_sufficiency_score"] == 16
    assert summary["raw_label_counts"]["working_set_context"] == 24
    assert summary["needs_review_count"] == 0
    assert summary["adjudication_required_count"] == 0
    assert summary["unhandled_adjudication_required_count"] == 0

    assert get_in(summary, [
             "reported_metric_scores",
             "context_omission_error_rate",
             "score_4dp"
           ]) == "0.3684"

    assert get_in(summary, [
             "reported_metric_scores",
             "working_set_relevance_score",
             "score_4dp"
           ]) == "0.7742"
  end

  @tag :generated_artifact_tooling
  test "validates active label report parity against filled labels and import summary" do
    assert {:ok, summary} =
             PostStage1LaneBLabelResults.validate_report_parity(
               @label_report_path,
               @filled_results_path,
               @import_summary_path,
               @label_opts
             )

    assert summary["status"] == "ok"

    assert summary["raw_label_counts"] == %{
             "evidence_sufficiency_score" => 16,
             "working_set_context" => 24
           }

    assert get_in(summary, [
             "reported_metric_scores",
             "context_omission_error_rate",
             "omitted_task_critical_ref_count"
           ]) == 14

    assert get_in(summary, [
             "reported_metric_scores",
             "context_omission_error_rate",
             "task_critical_candidate_ref_count"
           ]) == 38

    assert get_in(summary, [
             "reported_metric_scores",
             "working_set_relevance_score",
             "relevant_included_ref_count"
           ]) == 24

    assert get_in(summary, [
             "reported_metric_scores",
             "working_set_relevance_score",
             "included_ref_denominator"
           ]) == 31
  end

  @tag :generated_artifact_tooling
  test "report parity rejects drifted markdown omission metrics" do
    report_text =
      @label_report_path
      |> File.read!()
      |> String.replace(
        "| `context_omission_error_rate` | 24 | No adjudication required; exact matching primary labels retained | `0.3684` (`14 / 38`) | 0 | `complete_reported` |",
        "| `context_omission_error_rate` | 24 | No adjudication required; exact matching primary labels retained | `0.9999` (`99 / 99`) | 0 | `complete_reported` |",
        global: false
      )

    path = write_temp_text(report_text)

    assert {:error, errors} =
             PostStage1LaneBLabelResults.validate_report_parity(
               path,
               @filled_results_path,
               @import_summary_path,
               @label_opts
             )

    assert Enum.any?(errors, &String.contains?(&1, "context_omission_error_rate"))
  end

  @tag :docs_consistency
  test "validates PS1-G7 planning and traceability parity for locked context metrics" do
    assert {:ok, summary} =
             PostStage1LaneBLabelResults.validate_ps1_g7_context_metric_parity(
               @filled_results_path,
               @import_summary_path,
               Keyword.put(@label_opts, :report, @label_report_path)
             )

    assert summary["status"] == "ok"

    assert get_in(summary, [
             "locked_context_metrics",
             "context_omission_error_rate",
             "score_4dp"
           ]) == "0.3684"

    assert get_in(summary, [
             "locked_context_metrics",
             "context_omission_error_rate",
             "omitted_task_critical_ref_count"
           ]) == 14

    assert get_in(summary, [
             "locked_context_metrics",
             "context_omission_error_rate",
             "task_critical_candidate_ref_count"
           ]) == 38

    assert get_in(summary, [
             "locked_context_metrics",
             "working_set_relevance_score",
             "score_4dp"
           ]) == "0.7742"

    assert get_in(summary, [
             "locked_context_metrics",
             "working_set_relevance_score",
             "relevant_included_ref_count"
           ]) == 24

    assert get_in(summary, [
             "locked_context_metrics",
             "working_set_relevance_score",
             "included_ref_denominator"
           ]) == 31

    assert "docs/00_manifest/Traceability_Matrix.md" in summary["surface_paths"]

    assert "docs/02_specs/Post_Stage_1_Context_OS_Planning_Draft_Spec.md" in summary[
             "surface_paths"
           ]
  end

  @tag :docs_consistency
  test "PS1-G7 parity rejects drifted planning surface fractions" do
    drifted_plan =
      @context_os_eval_plan_path
      |> File.read!()
      |> String.replace(
        "`working_set_relevance_score = 0.7742` (`24 / 31`)",
        "`working_set_relevance_score = 0.7742` (`23 / 31`)",
        global: false
      )

    path = write_temp_text(drifted_plan)

    assert {:error, errors} =
             PostStage1LaneBLabelResults.validate_ps1_g7_context_metric_parity(
               @filled_results_path,
               @import_summary_path,
               @label_opts
               |> Keyword.put(:report, @label_report_path)
               |> Keyword.put(:surface_paths, [path])
             )

    assert Enum.any?(errors, &String.contains?(&1, "working_set_relevance_score"))
  end

  @tag :generated_artifact_tooling
  test "rejects labels outside the PS1-LB-LABEL-001 evidence scale" do
    assert {:ok, packet} = PostStage1LaneBPacket.build(@packet_opts)
    assert {:ok, result} = in_progress_result(packet)

    [evidence_label] = result["raw_labels"]["evidence_sufficiency_score"]

    invalid_result =
      put_in(result, ["raw_labels", "evidence_sufficiency_score"], [
        %{evidence_label | "raw_label_0_to_4_or_needs_review" => 5}
      ])

    path = write_temp_json(invalid_result)

    assert {:error, errors} = PostStage1LaneBLabelResults.validate_file(path, @label_opts)
    assert Enum.any?(errors, &String.contains?(&1, "integer 0-4 or needs_review"))
  end

  @tag :generated_artifact_tooling
  test "rejects unknown referenced artifact IDs" do
    assert {:ok, packet} = PostStage1LaneBPacket.build(@packet_opts)
    assert {:ok, result} = in_progress_result(packet)

    [evidence_label] = result["raw_labels"]["evidence_sufficiency_score"]

    invalid_result =
      put_in(result, ["raw_labels", "evidence_sufficiency_score"], [
        %{evidence_label | "referenced_artifact_ids" => ["not_in_packet"]}
      ])

    path = write_temp_json(invalid_result)

    assert {:error, errors} = PostStage1LaneBLabelResults.validate_file(path, @label_opts)
    assert Enum.any?(errors, &String.contains?(&1, "unknown artifact IDs"))
  end

  defp in_progress_result(packet) do
    with {:ok, template} <- PostStage1LaneBLabelResults.template(@label_opts) do
      evidence_item = hd(packet.evidence_sufficiency_items)
      working_set_item = hd(packet.working_set_context_items)

      {:ok,
       template
       |> Map.put("label_collection_status", "in_progress")
       |> put_in(["primary_label_freeze", "status"], "open")
       |> put_in(["raw_labels", "evidence_sufficiency_score"], [
         evidence_label(evidence_item)
       ])
       |> put_in(["raw_labels", "working_set_context"], [
         working_set_label(working_set_item)
       ])}
    end
  end

  defp evidence_label(item) do
    %{
      "metric" => "evidence_sufficiency_score",
      "item_id" => item["packet_id"],
      "label_source" => "human",
      "reviewer_id" => "dry_run_reviewer_a",
      "raw_label_0_to_4_or_needs_review" => 4,
      "confidence" => 0.9,
      "rationale" => "Dry-run validator fixture only; not a collected human label.",
      "referenced_artifact_ids" => [item["packet_id"]]
    }
  end

  defp working_set_label(item) do
    ref_ids = Enum.map(item["candidate_ref_inventory"], & &1["ref_id"])

    %{
      "metric" => "working_set_context",
      "item_id" => item["packet_id"],
      "label_source" => "human",
      "reviewer_id" => "dry_run_reviewer_a",
      "omission" => %{
        "omission_severity" => "none",
        "omitted_task_critical_ref_ids" => [],
        "task_critical_candidate_ref_ids" => [],
        "critical_omission" => false,
        "denominator_ref_ids" => ref_ids
      },
      "per_ref_relevance_labels" =>
        Enum.map(ref_ids, fn ref_id ->
          %{"ref_id" => ref_id, "relevance_label" => "supporting"}
        end),
      "packet_relevance_quality" => "sufficient",
      "confidence" => 0.85,
      "rationale" => "Dry-run validator fixture only; not a collected human label.",
      "referenced_artifact_ids" => [item["packet_id"]]
    }
  end

  defp write_temp_json(data) do
    path =
      Path.join(
        System.tmp_dir!(),
        "vanta_lane_b_label_results_#{System.unique_integer([:positive])}.json"
      )

    File.write!(path, Jason.encode!(data, pretty: true))
    on_exit(fn -> File.rm(path) end)
    path
  end

  defp write_temp_text(text) do
    path =
      Path.join(
        System.tmp_dir!(),
        "vanta_lane_b_label_report_#{System.unique_integer([:positive])}.md"
      )

    File.write!(path, text)
    on_exit(fn -> File.rm(path) end)
    path
  end
end
