defmodule Vanta.FixtureCommitMeasuredResultTest do
  use ExUnit.Case, async: true

  @moduletag :docs_consistency

  @docs_root Path.expand("../../../docs", __DIR__)
  @chatgpt_docs_root Path.expand("../../../chatgpt_docs/docs", __DIR__)
  @failed_root "04_experiments/results/fixture_local_committable_execution/20260716_015841"
  @run_root "04_experiments/results/fixture_local_committable_execution/20260716_020716"
  @closure "00_manifest/Post_Stage_1_Fixture_Local_Committable_v0_Closure.md"

  test "Experiment 007 measured run passes every G10 hard gate" do
    run = load_json(Path.join(@run_root, "run.json"))
    fixtures = load_json(Path.join(@run_root, "fixture_results.json"))

    assert run["threshold_status"] == "pass_acceptance_candidate"
    assert run["report_label"] == "pass_acceptance_candidate"
    assert run["fixture_count"] == 28
    assert run["case_pass_count"] == 28
    assert run["case_fail_count"] == 0
    assert length(fixtures) == 28
    assert Enum.all?(fixtures, & &1["passed"])
    assert Enum.all?(run["hard_metrics"], fn {_name, metric} -> metric["passed"] end)

    integrity = run["source_fixture_integrity"]
    assert integrity["unchanged"]
    assert integrity["pre_run_tree_hash"] == integrity["post_run_tree_hash"]

    assert run["claim_boundary"]["irreversible_effects"] == 0
    assert run["claim_boundary"]["memory_writes"] == 0
    assert run["claim_boundary"]["external_targets"] == 0
    refute run["claim_boundary"]["production_readiness"]
    refute run["claim_boundary"]["h1_h5_validation"]
  end

  test "failed G10 predecessor remains immutable failed_no_acceptance provenance" do
    run = load_json(Path.join(@failed_root, "run.json"))
    fixtures = load_json(Path.join(@failed_root, "fixture_results.json"))
    provenance = read_doc(Path.join(@failed_root, "provenance.md"))

    assert run["threshold_status"] == "failed_no_acceptance"
    assert run["report_label"] == "failed_no_acceptance"
    assert run["case_pass_count"] == 27
    assert run["case_fail_count"] == 1
    assert Enum.count(fixtures, & &1["passed"]) == 27
    assert run["hard_metrics"]["unauthorized_commit_count"]["value"] == 1
    assert run["hard_metrics"]["approval_verifier_substitution_count"]["value"] == 1
    assert run["hard_metrics"]["silent_partial_commits"]["value"] == 2
    refute run["hard_metrics"]["replay_consistency"]["passed"]
    assert provenance =~ "pre-measurement complete development diagnostic"
    assert provenance =~ "Acceptance use: none"
    assert provenance =~ "Superseded by repaired complete run: `20260716_020716`"

    summary = File.read!(Path.join(@docs_root, Path.join(@failed_root, "summary.md")))
    assert summary =~ "Threshold status: `failed_no_acceptance`"
    assert summary =~ "does not assign\n`accepted_by_closure`"
  end

  test "manifest closure accepts only the exact G10 copied-fixture scope" do
    closure = read_doc(@closure)
    manifest = read_doc("00_manifest/Project_Manifest.md")
    inventory = read_doc("00_manifest/Post_Stage_1_Gate_Inventory.md")
    traceability = read_doc("00_manifest/Traceability_Matrix.md")

    report =
      read_doc("05_evaluation/Experiment_007_Fixture_Local_Committable_Execution_Run_Report.md")

    assert closure =~ "accepted_by_closure"
    assert closure =~ "validated for Fixture-Local COMMITTABLE Document Promotion v0"
    assert closure =~ "28/28 cases"
    assert closure =~ "H5 or H1-H5 validation"
    assert closure =~ "broad side-effect safety"
    assert closure =~ "production readiness"
    assert closure =~ "repository source"
    assert closure =~ "external systems"
    assert closure =~ "`IRREVERSIBLE`"
    assert closure =~ "`MEMORY_WRITE`"
    assert closure =~ "durable memory"
    assert closure =~ "full Context OS"
    assert closure =~ "distributed transactions"
    assert closure =~ "multi-process authority"

    Enum.each([manifest, inventory, traceability, report], fn text ->
      assert text =~ "Post_Stage_1_Fixture_Local_Committable_v0_Closure.md"
    end)
  end

  test "G10 knowledge mirrors stay byte-identical and within the 25-file cap" do
    mirrored =
      @chatgpt_docs_root
      |> Path.join("**/*")
      |> Path.wildcard()
      |> Enum.filter(&File.regular?/1)

    assert length(mirrored) <= 25

    Enum.each(
      [
        "00_manifest/Fixture_Local_Committable_Execution_Gate.md",
        @closure,
        "02_specs/Fixture_Local_Committable_Document_Promotion_v0.md",
        "03_schemas/Fixture_Local_Committable_Schema_Impact_Review.md",
        "04_experiments/Experiment_007_Fixture_Local_Committable_Execution.md",
        "05_evaluation/Experiment_007_Fixture_Local_Committable_Execution_Run_Report.md"
      ],
      fn relative ->
        assert read_doc(relative) ==
                 File.read!(Path.join(@chatgpt_docs_root, relative))
      end
    )
  end

  defp read_doc(relative), do: File.read!(Path.join(@docs_root, relative))

  defp load_json(relative) do
    @docs_root
    |> Path.join(relative)
    |> File.read!()
    |> Jason.decode!()
  end
end
