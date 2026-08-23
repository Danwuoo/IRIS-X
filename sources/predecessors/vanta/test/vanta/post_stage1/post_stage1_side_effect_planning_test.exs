defmodule Vanta.PostStage1SideEffectPlanningTest do
  use ExUnit.Case

  alias Vanta.PostStage1SideEffectPlanning
  alias Vanta.PostStage1SideEffectPlanning.PathHelpers

  @fixture_root Path.expand(
                  "../../../docs/04_experiments/fixtures/side_effect_planning",
                  __DIR__
                )

  @required_files ~w(
    run.json
    fixture_results.json
    environment_manifest.json
    summary.md
    fixture_inventory.md
    commit_plan_inventory.md
    approval_boundary_report.md
    rollback_compensation_report.md
    schema_impact_ref.md
    not_applicable.md
  )

  @placeholder_action "commit_fixture_document_candidate"

  @tag :generated_artifact_tooling
  test "runner writes the complete measured PS1-G8 planning pilot artifact contract" do
    out_dir = tmp_dir("sidefx_contract")

    assert {:ok, run} =
             PostStage1SideEffectPlanning.run(
               out_dir: out_dir,
               generated_at: "2026-07-15T00:00:00Z"
             )

    assert run["plan_id"] == "PS1-LC-SIDEFX-PLAN-001"
    assert run["planning_surface_id"] == "PS1-LC-SIDEFX-COMMITTABLE-DOCOPS-001"
    assert run["gate_policy_version"] == "PS1-LC-SIDEFX-GATE-001"
    assert run["generation_mode"] == "measured planning pilot"
    assert run["report_label"] == "committable_docops_planning_pilot"
    assert run["completion_status"] == "complete"
    assert run["threshold_status"] == "pass_planning_pilot"
    assert run["fixture_count"] == 10
    assert get_in(run, ["artifact_contract", "required_files"]) == @required_files

    Enum.each(@required_files, fn file_name ->
      assert File.regular?(Path.join(out_dir, file_name)), "#{file_name} was not generated"
    end)

    assert Jason.decode!(File.read!(Path.join(out_dir, "run.json"))) == run

    fixture_results = Jason.decode!(File.read!(Path.join(out_dir, "fixture_results.json")))
    assert length(fixture_results) == 10
    assert Enum.all?(fixture_results, & &1["oracle_match"])
    assert Enum.all?(fixture_results, & &1["audit_complete"])
  end

  @tag :fast_unit
  test "validator accepts positive controls and applies every required rejection rule" do
    out_dir = tmp_dir("sidefx_rules")
    assert {:ok, _run} = PostStage1SideEffectPlanning.run(out_dir: out_dir)

    results = Jason.decode!(File.read!(Path.join(out_dir, "fixture_results.json")))

    assert Enum.count(results, &(get_in(&1, ["actual", "decision"]) == "valid")) == 2
    assert Enum.count(results, &(get_in(&1, ["actual", "decision"]) == "rejected")) == 8

    assert_reason(results, "missing_target_identity", "missing_target_identity")
    assert_reason(results, "missing_approval_boundary", "missing_approval_boundary")

    assert_reason(
      results,
      "missing_idempotency_duplicate_guard",
      "missing_idempotency_key"
    )

    assert_reason(
      results,
      "missing_idempotency_duplicate_guard",
      "missing_duplicate_guard"
    )

    assert_reason(
      results,
      "missing_rollback_or_compensation_statement",
      "missing_rollback_or_compensation_statement"
    )

    assert_reason(results, "path_escape", "path_escape")
    assert_reason(results, "source_fixture_mutation", "source_fixture_mutation_target")

    assert_reason(
      results,
      "irreversible_misclassification",
      "irreversible_misclassification"
    )

    assert_reason(results, "memory_write_smuggling", "memory_write_smuggling")
  end

  @tag :generated_artifact_tooling
  test "all planning metrics pass and every execution/process floor stays at zero" do
    out_dir = tmp_dir("sidefx_metrics")
    assert {:ok, run} = PostStage1SideEffectPlanning.run(out_dir: out_dir)

    assert Enum.all?(run["planning_metrics"], fn {_name, metric} ->
             metric["value"] == 1.0 and metric["passed"]
           end)

    assert Enum.all?(run["process_integrity_floors"], fn {_name, value} -> value == 0 end)

    assert run["executed_side_effect_counts"] == %{
             "COMMITTABLE" => 0,
             "IRREVERSIBLE" => 0,
             "MEMORY_WRITE" => 0
           }

    assert get_in(run, ["source_fixture_integrity", "unchanged"])
    assert get_in(run, ["planning_boundary", "labels_are_runtime_approvals"]) == false
    assert get_in(run, ["planning_boundary", "fixture_oracles_are_runtime_approvals"]) == false
  end

  @tag :generated_artifact_tooling
  test "a failed hard metric run is retained and is not marked complete" do
    fixture_root = tmp_dir("sidefx_failed_fixtures")
    File.cp_r!(@fixture_root, fixture_root)

    case_path = Path.join(fixture_root, "case_missing_target_identity.json")
    fixture = case_path |> File.read!() |> Jason.decode!()
    fixture = put_in(fixture, ["oracle", "expected_reason_codes"], ["wrong_reason"])
    File.write!(case_path, Jason.encode!(fixture, pretty: true) <> "\n")

    out_dir = tmp_dir("sidefx_failed_run")

    assert {:ok, run} =
             PostStage1SideEffectPlanning.run(
               fixture_root: fixture_root,
               out_dir: out_dir
             )

    assert run["completion_status"] == "failed"
    assert run["threshold_status"] == "failed_no_acceptance"
    refute get_in(run, ["pilot_gates", "all_planning_metrics_pass"])
    assert File.regular?(Path.join(out_dir, "run.json"))
    assert File.regular?(Path.join(out_dir, "fixture_results.json"))
  end

  @tag :fast_unit
  test "runner refuses output inside source fixtures and preserves the source tree" do
    before_hash = PathHelpers.fixture_tree_hash(@fixture_root)

    assert_raise ArgumentError, ~r/output must stay outside/, fn ->
      PostStage1SideEffectPlanning.run(
        fixture_root: @fixture_root,
        out_dir: Path.join(@fixture_root, "forbidden-output")
      )
    end

    assert PathHelpers.fixture_tree_hash(@fixture_root) == before_hash
  end

  @tag :fast_unit
  test "G8 planning runner remains non-dispatching after the separately governed G10 successor" do
    assert @placeholder_action not in Vanta.action_types()
    assert @placeholder_action in Vanta.fixture_commit_action_types()

    Enum.each(
      [
        "docs/03_schemas/execution_step.schema.json",
        "docs/03_schemas/planner_action_sequence.schema.json",
        "docs/03_schemas/benchmark_task.schema.json"
      ],
      fn schema_path ->
        assert File.read!(schema_path) =~ @placeholder_action,
               "#{schema_path} must expose the separately accepted G10 action"
      end
    )

    source = File.read!("lib/vanta/post_stage1/post_stage1_side_effect_planning.ex")
    refute source =~ "Runtime.run_task("
    refute source =~ "ExecutionIRCompiler"
    refute source =~ "ActionExecutor"
    refute source =~ "CommitController"
  end

  @tag :generated_artifact_tooling
  test "generated reports keep the claim boundary explicit" do
    out_dir = tmp_dir("sidefx_claims")
    assert {:ok, _run} = PostStage1SideEffectPlanning.run(out_dir: out_dir)

    generated_text =
      @required_files
      |> Enum.map(&File.read!(Path.join(out_dir, &1)))
      |> Enum.join("\n")

    assert generated_text =~ "committable_docops_planning_pilot"
    assert generated_text =~ "runtime execution not authorized"
    assert generated_text =~ "not runtime approvals"

    Enum.each(
      [
        "accepted_by_closure",
        "H5 validated",
        "side-effect safety validated",
        "runtime approval collected",
        "COMMITTABLE execution authorized",
        "IRREVERSIBLE execution authorized",
        "MEMORY_WRITE authorized",
        "production ready"
      ],
      fn disallowed_claim -> refute generated_text =~ disallowed_claim end
    )
  end

  @tag :generated_artifact_tooling
  test "Mix task reruns the formal planning pilot" do
    aliases = Mix.Project.config()[:aliases]

    assert aliases[:"vanta.post_stage_1_side_effect_planning"] == [
             "vanta.post_stage1_side_effect_planning"
           ]

    out_dir = tmp_dir("sidefx_mix_task")

    Mix.Task.reenable("vanta.post_stage1_side_effect_planning")
    Mix.Task.run("vanta.post_stage1_side_effect_planning", ["--out", out_dir])

    run = Jason.decode!(File.read!(Path.join(out_dir, "run.json")))
    assert run["report_label"] == "committable_docops_planning_pilot"
    assert run["completion_status"] == "complete"
    assert get_in(run, ["executed_side_effect_counts", "COMMITTABLE"]) == 0
  end

  defp assert_reason(results, family, reason) do
    result = Enum.find(results, &(&1["family"] == family))
    assert result
    assert reason in get_in(result, ["actual", "reason_codes"])
    assert get_in(result, ["actual", "decision"]) == "rejected"
  end

  defp tmp_dir(label) do
    out_dir =
      Path.join(System.tmp_dir!(), "vanta_#{label}_#{System.unique_integer([:positive])}")

    File.rm_rf!(out_dir)
    out_dir
  end
end
