defmodule Vanta.DocumentationClosureConsistencyTest do
  use ExUnit.Case, async: true

  @moduletag :docs_consistency

  @docs_root Path.expand("../../../docs", __DIR__)
  @chatgpt_docs_root Path.expand("../../../chatgpt_docs/docs", __DIR__)
  @closure_doc Path.join(@docs_root, "00_manifest/Stage_1_Experiment_005_Closure.md")

  @phase5_status_docs [
    "04_experiments/Ablation_Plan.md",
    "06_engineering/Runtime_Module_Plan.md",
    "06_engineering/Implementation_Timeline.md",
    "00_manifest/Stage_1_Experiment_005_Closure.md",
    "05_evaluation/Experiment_005_Local_Run_Report.md"
  ]

  @phase5_runtime_modules [
    "Working Set Compiler",
    "Raw Trace Context Builder",
    "OpenClaw Context Planner Adapter"
  ]

  @lane_b_active_status_docs [
    "00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md",
    "02_specs/Context_OS_and_Working_Set_Compiler_Note.md"
  ]

  @active_lane_a_run "20260601_113121"
  @historical_lane_a_run "20260530_141649"
  @active_lane_b_packet_id "PS1-LB-PACKET-20260601-113121-BATCH-001"
  @historical_lane_b_packet_id "PS1-LB-PACKET-20260530-141649-BATCH-001"
  @active_lane_b_packet_dir "05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121"

  @ps1_g7_planning_bundle_docs [
    "02_specs/Post_Stage_1_Context_OS_Planning_Draft_Spec.md",
    "03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md",
    "04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md"
  ]

  @lane_b_ps1_g7_mirrored_docs [
    "00_manifest/Context_OS_Expansion_Gate.md",
    "00_manifest/Document_Map.md",
    "00_manifest/Post_Stage_1_Advancement_Gate.md",
    "00_manifest/Post_Stage_1_Gate_Inventory.md",
    "00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md",
    "00_manifest/Project_Manifest.md",
    "00_manifest/Traceability_Matrix.md",
    "02_specs/Context_OS_and_Working_Set_Compiler_Note.md"
  ]

  test "Phase 5 docs do not drift back to planned after Experiment 005 closure" do
    assert File.exists?(@closure_doc)

    closure_text = File.read!(@closure_doc)
    assert closure_text =~ "Status: `Closed: local smoke completed`"
    assert closure_text =~ "Closure date: 2026-05-07"

    docs = read_phase5_status_docs()
    ablation_plan = Map.fetch!(docs, "04_experiments/Ablation_Plan.md")
    runtime_plan = Map.fetch!(docs, "06_engineering/Runtime_Module_Plan.md")
    timeline = Map.fetch!(docs, "06_engineering/Implementation_Timeline.md")

    refute Regex.match?(~r/\|\s*E\s*\|\s*Planned\s*\|/, ablation_plan),
           "Ablation Plan Stage E still has Planned status"

    Enum.each(@phase5_runtime_modules, fn module_name ->
      refute Regex.match?(
               ~r/\|\s*#{Regex.escape(module_name)}\s*\|[^\n]*\|\s*Planned\b/,
               runtime_plan
             ),
             "Runtime Module Plan still marks #{module_name} as Planned"
    end)

    timeline
    |> markdown_section("## Phase 5: Context OS Candidate")
    |> then(fn phase5_section ->
      refute Regex.match?(~r/Status:\s*`?Planned`?/, phase5_section),
             "Implementation Timeline Phase 5 still has Planned status"
    end)
  end

  test "primary Phase 5 status surfaces point at the measured local smoke closure" do
    ablation_plan = File.read!(Path.join(@docs_root, "04_experiments/Ablation_Plan.md"))
    runtime_plan = File.read!(Path.join(@docs_root, "06_engineering/Runtime_Module_Plan.md"))
    timeline = File.read!(Path.join(@docs_root, "06_engineering/Implementation_Timeline.md"))
    report = File.read!(Path.join(@docs_root, "05_evaluation/Experiment_005_Local_Run_Report.md"))

    assert ablation_plan =~
             "| E | Local smoke evidence | Experiment 005 closed the five-fixture `Working Set Compiler v0` smoke against bounded raw trace; this is not broad validation of H3 or full Context OS. |"

    assert runtime_plan =~
             "| Working Set Compiler | Compile schema-valid, reference-backed `WorkingSet` artifacts from explicit candidate refs under a fixed budget. | Implemented and exercised by Experiment 005 local smoke |"

    assert runtime_plan =~
             "| Raw Trace Context Builder | Build bounded raw-trace baseline context under the same budget as treatment. | Implemented and exercised by Experiment 005 baseline local smoke |"

    assert runtime_plan =~
             "| OpenClaw Context Planner Adapter | Ask OpenClaw for JSON action sequences using embedded baseline or working-set context only. | Implemented and exercised by Experiment 005 local smoke |"

    assert timeline =~ "Status: `Closed: local smoke completed` on 2026-05-07."
    assert report =~ "Date: 2026-05-07"

    assert report =~
             "The run provides a measured local smoke result for `Working Set Compiler v0`."
  end

  test "20260601 closure follow-up does not publish stale active Lane B status" do
    label_report =
      File.read!(
        Path.join(
          @docs_root,
          "05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md"
        )
      )

    closure =
      File.read!(
        Path.join(@docs_root, "00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md")
      )

    context_note =
      File.read!(Path.join(@docs_root, "02_specs/Context_OS_and_Working_Set_Compiler_Note.md"))

    assert label_report =~ "- Label collection status: `complete_reported`"
    assert closure =~ "2026-06-01 closure-time status"
    assert closure =~ "first primary batch is `complete_reported`"
    assert context_note =~ "packet-level human-labeled context-quality evidence"

    refute closure =~ "Human or secondary labels remain `Not yet run`"
    refute context_note =~ "Lane B labels\nremain `Not yet run`"

    Enum.each(@lane_b_active_status_docs, fn relative_path ->
      assert File.read!(Path.join(@docs_root, relative_path)) ==
               File.read!(Path.join(@chatgpt_docs_root, relative_path))
    end)
  end

  test "active Lane B packet and PS1-G7 planning docs stay routed to 20260601 reported labels" do
    packet_manifest = read_json(Path.join(@active_lane_b_packet_dir, "packet_manifest.json"))

    label_report =
      read_doc("05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md")

    packet_readme = read_doc(Path.join(@active_lane_b_packet_dir, "README.md"))

    assert packet_manifest["packet_id"] == @active_lane_b_packet_id
    assert packet_manifest["packet_status"] == "active_packet_complete_reported"
    assert packet_manifest["label_collection_status"] == "complete_reported"
    assert packet_manifest["report_status"] == "reported_from_validated_primary_labels"
    assert packet_manifest["source_run"]["run_timestamp"] == @active_lane_a_run
    assert packet_manifest["source_run"]["closure_status"] == "accepted_by_closure"
    assert packet_manifest["supersedes"]["packet_id"] == @historical_lane_b_packet_id

    assert label_report =~ "- Source Lane A run timestamp: `#{@active_lane_a_run}`"
    assert label_report =~ "- Lane B packet ID: `#{@active_lane_b_packet_id}`"
    assert label_report =~ "- Label collection status: `complete_reported`"
    assert label_report =~ "- Report status: `reported_from_validated_primary_labels`"
    assert label_report =~ "supersedes\n`Post_Stage_1_Lane_B_20260530_141649"
    refute label_report =~ "Lane B packet ID: `#{@historical_lane_b_packet_id}`"
    refute label_report =~ "Label collection status: `Not yet run`"

    assert packet_readme =~
             "`#{@active_lane_a_run}` Lane A rerun that is `accepted_by_closure`"

    assert packet_readme =~ ~r/Label collection status is\s+`complete_reported`\./
    refute packet_readme =~ "Label collection status is\n`Not yet run`"

    Enum.each(@ps1_g7_planning_bundle_docs, fn relative_path ->
      text = read_doc(relative_path)

      assert text =~ "Source Lane A run: `#{@active_lane_a_run}`"
      assert text =~ "accepted_by_closure"

      assert text =~
               ~r/Lane B label status:\s+`complete_reported` for the first active\s+`#{@active_lane_a_run}` packet\./

      refute text =~ "Source Lane A run: `#{@historical_lane_a_run}`"
      refute text =~ "Lane B label status: `Not yet run`"
    end)

    Enum.each(@lane_b_ps1_g7_mirrored_docs, fn relative_path ->
      assert File.read!(Path.join(@docs_root, relative_path)) ==
               File.read!(Path.join(@chatgpt_docs_root, relative_path))
    end)
  end

  defp read_phase5_status_docs do
    Map.new(@phase5_status_docs, fn relative_path ->
      {relative_path, File.read!(Path.join(@docs_root, relative_path))}
    end)
  end

  defp read_doc(relative_path), do: File.read!(Path.join(@docs_root, relative_path))

  defp read_json(relative_path) do
    relative_path
    |> read_doc()
    |> Jason.decode!()
  end

  defp markdown_section(text, heading) do
    [_before, rest] = String.split(text, heading, parts: 2)

    rest
    |> String.split(~r/\n## /, parts: 2)
    |> hd()
  end
end
