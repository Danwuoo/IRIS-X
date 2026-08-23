defmodule Vanta.PostStage1LaneBPacketTest do
  use ExUnit.Case

  alias Vanta.PostStage1LaneBPacket

  @opts [
    run_timestamp: "20260601_113121",
    run_json: "docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/run.json",
    run_report: "docs/05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md",
    closure: "docs/00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md",
    fixtures: "docs/04_experiments/fixtures/document_ops",
    out: "docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121"
  ]

  @tag :generated_artifact_tooling
  test "builds active Lane B packet item counts and source linkage" do
    assert {:ok, packet} = PostStage1LaneBPacket.build(@opts)

    assert packet.packet_manifest["packet_id"] == "PS1-LB-PACKET-20260601-113121-BATCH-001"
    assert packet.packet_manifest["packet_status"] == "active_packet_complete_reported"
    assert packet.packet_manifest["label_collection_status"] == "complete_reported"
    assert packet.packet_manifest["report_status"] == "reported_from_validated_primary_labels"
    assert get_in(packet.packet_manifest, ["label_import_summary", "status"]) == "reported"

    assert get_in(packet.packet_manifest, ["label_import_summary", "raw_label_counts"]) == %{
             "evidence_sufficiency_score" => 16,
             "working_set_context" => 24
           }

    assert get_in(packet.packet_manifest, ["artifact_paths", "label_report"]) ==
             "docs/05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md"

    assert Enum.all?(
             packet.packet_manifest["metric_scope"],
             fn {_metric, scope} -> scope["label_status"] == "complete_reported" end
           )

    assert get_in(packet.packet_manifest, ["source_run", "closure_status"]) ==
             "accepted_by_closure"

    assert get_in(packet.packet_manifest, ["source_run", "run_json_path"]) ==
             "docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/run.json"

    assert length(packet.evidence_sufficiency_items) == 8
    assert length(packet.working_set_context_items) == 12
    assert packet.label_results_template["result_format"] == "PS1-LB-LABEL-RESULT-LOCAL-001"
    assert packet.label_results_template["label_collection_status"] == "Not yet run"
  end

  @tag :generated_artifact_tooling
  test "redacts oracle-sensitive task fields for primary labeler packets" do
    assert {:ok, packet} = PostStage1LaneBPacket.build(@opts)

    Enum.each(packet.redacted_task_packets, fn {_task_id, task_packet} ->
      refute has_key_recursive?(task_packet, "required_refs")
      refute has_key_recursive?(task_packet, "relevant_refs")
      refute has_key_recursive?(task_packet, "irrelevant_refs")
      refute has_key_recursive?(task_packet, "omission_trap_refs")
      refute has_key_recursive?(task_packet, "expected_runtime_status")
      refute has_key_recursive?(task_packet, "expected_label_source")

      Enum.each(task_packet["input_artifacts"], fn input_artifact ->
        refute Map.has_key?(input_artifact, "role")
        refute Map.has_key?(input_artifact, "description")
      end)
    end)
  end

  @tag :generated_artifact_tooling
  test "keeps reviewer-visible item label fields as Not yet run scaffolds" do
    assert {:ok, packet} = PostStage1LaneBPacket.build(@opts)

    items = packet.evidence_sufficiency_items ++ packet.working_set_context_items

    Enum.each(items, fn item ->
      assert item["label_status"] == "Not yet run"
      assert item["adjudication_status"] == "Not yet run"
      assert Enum.all?(Map.values(item["primary_label_fields"]), &(&1 == "Not yet run"))
    end)
  end

  @tag :generated_artifact_tooling
  test "active reported packet generation paths do not regress to pre-label narrative" do
    assert {:ok, packet} = PostStage1LaneBPacket.build(@opts)

    assert String.contains?(packet.readme, "complete_reported")
    assert String.contains?(packet.readme, "label_results_import_summary.json")
    refute String.contains?(packet.readme, "It does not contain human labels")
    refute String.contains?(packet.readme, "All fields are currently `Not yet run`")

    assert String.contains?(packet.label_report_skeleton, "complete_reported")

    assert String.contains?(
             packet.label_report_skeleton,
             "reported_from_validated_primary_labels"
           )

    assert String.contains?(packet.label_report_skeleton, "label_results_import_summary.json")
    refute String.contains?(packet.label_report_skeleton, "Human labels have not been collected")
    refute String.contains?(packet.label_report_skeleton, "Claim level before labels")
  end

  @tag :generated_artifact_tooling
  test "working-set context items use blinded arms without arm identity mapping" do
    assert {:ok, packet} = PostStage1LaneBPacket.build(@opts)

    assert Enum.frequencies_by(packet.working_set_context_items, & &1["blinded_arm"]) == %{
             "context_arm_A" => 6,
             "context_arm_B" => 6
           }

    encoded = Jason.encode!(packet.working_set_context_items)
    refute String.contains?(encoded, "\"baseline\"")
    refute String.contains?(encoded, "\"treatment\"")
  end

  @tag :generated_artifact_tooling
  test "post-freeze unblind guard accepts packet artifacts without coordinator-only source labels" do
    assert {:ok, packet} = PostStage1LaneBPacket.build(@opts)

    artifacts = %{
      evidence_sufficiency_items: packet.evidence_sufficiency_items,
      working_set_context_items: packet.working_set_context_items,
      redacted_task_packets: packet.redacted_task_packets,
      label_results_template: packet.label_results_template
    }

    assert PostStage1LaneBPacket.post_freeze_unblind_boundary_errors(artifacts) == []
  end

  @tag :generated_artifact_tooling
  test "packet check rejects post-freeze unblind source labels in result scaffolds" do
    opts = temp_packet_opts("post_freeze_unblind_guard")
    assert {:ok, _result} = PostStage1LaneBPacket.generate(opts)

    opts
    |> Keyword.fetch!(:label_results)
    |> File.write!(
      Jason.encode!(
        %{
          "result_format" => "PS1-LB-LABEL-RESULT-LOCAL-001",
          "source_arm_label" => "raw_trace_*"
        },
        pretty: true
      )
    )

    assert {:error, errors} = PostStage1LaneBPacket.check(opts)

    assert Enum.any?(errors, fn error ->
             String.contains?(error, "post-freeze unblind guard") and
               String.contains?(error, "source arm label")
           end)
  end

  @tag :generated_artifact_tooling
  test "selector-missing evidence item comes from repaired rejection artifact" do
    assert {:ok, packet} = PostStage1LaneBPacket.build(@opts)

    item =
      Enum.find(packet.evidence_sufficiency_items, fn item ->
        item["task_id"] == "docops_struct_selector_missing_001"
      end)

    assert item["packet_id"] == "lb20260601-es-005"
    assert get_in(item, ["action_under_review", "status"]) == "rejected"
    assert get_in(item, ["verifier_output", "decision"]) == "reject"

    assert get_in(item, ["evidence_packet", "observation", "selector_resolution", "status"]) ==
             "missing"

    assert get_in(item, ["action_under_review", "action_payload", "selector", "type"]) ==
             "section"
  end

  defp has_key_recursive?(map, key) when is_map(map) do
    Map.has_key?(map, key) or Enum.any?(Map.values(map), &has_key_recursive?(&1, key))
  end

  defp has_key_recursive?(list, key) when is_list(list) do
    Enum.any?(list, &has_key_recursive?(&1, key))
  end

  defp has_key_recursive?(_value, _key), do: false

  defp temp_packet_opts(name) do
    base_dir =
      Path.join(
        System.tmp_dir!(),
        "vanta_lane_b_packet_#{name}_#{System.unique_integer([:positive])}"
      )

    on_exit(fn -> File.rm_rf!(base_dir) end)

    Keyword.merge(@opts,
      out: Path.join(base_dir, "packet"),
      label_report: Path.join(base_dir, "Post_Stage_1_Lane_B_20260601_113121_Label_Report.md"),
      label_results: Path.join([base_dir, "packet", "label_results_primary_filled.json"]),
      import_summary: Path.join([base_dir, "packet", "label_results_import_summary.json"]),
      coordinator_packet_freeze:
        Path.join([base_dir, "packet", "coordinator_primary_label_packet_freeze.json"])
    )
  end
end
