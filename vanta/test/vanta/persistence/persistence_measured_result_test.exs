defmodule Vanta.PersistenceMeasuredResultTest do
  use ExUnit.Case, async: true

  @moduletag :docs_consistency

  alias Vanta.{PersistenceExperiment, Schema}

  @docs_root Path.expand("../../../docs", __DIR__)
  @accepted_candidate "04_experiments/results/persistence_and_recovery/20260715_114209"
  @failed_provenance "04_experiments/results/persistence_and_recovery/20260715_114052"

  test "measured candidate artifacts pass every PS1-G9 hard metric" do
    run = load_json(Path.join(@accepted_candidate, "run.json"))
    cases = load_json(Path.join(@accepted_candidate, "failure_injection_results.json"))

    assert :ok = Schema.validate("experiment_run", run)
    assert run["threshold_status"] == "pass_acceptance_candidate"
    assert run["metrics"]["cases_passed"] == 20
    assert run["metrics"]["cases_total"] == 20
    assert Enum.all?(cases["cases"], & &1["passed"])

    Enum.each(PersistenceExperiment.hard_requirements(), fn {metric, required} ->
      assert run["metrics"][metric] == required, "#{metric} missed hard gate"
    end)
  end

  test "failed predecessor remains failed provenance and is not rewritten as accepted" do
    run = load_json(Path.join(@failed_provenance, "run.json"))
    assert run["threshold_status"] == "failed_no_acceptance"
    assert run["metrics"]["cases_passed"] == 19

    refute File.read!(Path.join(@docs_root, @failed_provenance <> "/summary.md")) =~
             "accepted_by_closure"
  end

  test "manifest closure accepts only the named PS1-G9 scope" do
    closure =
      File.read!(Path.join(@docs_root, "00_manifest/Post_Stage_1_Persistence_v0_Closure.md"))

    report =
      File.read!(
        Path.join(
          @docs_root,
          "05_evaluation/Experiment_006_Persistence_and_Recovery_Run_Report.md"
        )
      )

    manifest = File.read!(Path.join(@docs_root, "00_manifest/Project_Manifest.md"))
    inventory = File.read!(Path.join(@docs_root, "00_manifest/Post_Stage_1_Gate_Inventory.md"))
    traceability = File.read!(Path.join(@docs_root, "00_manifest/Traceability_Matrix.md"))

    assert closure =~ "accepted_by_closure"
    assert closure =~ "validated for Fixture-Local SQLite Persistence v0"
    assert closure =~ "H1-H5 validation"
    assert closure =~ "full architecture validation"
    assert closure =~ "production readiness"
    assert closure =~ "distributed storage or distributed persistence validation"
    assert closure =~ "durable memory"
    assert closure =~ "external executable `COMMITTABLE` actions"
    assert closure =~ "`IRREVERSIBLE` actions"
    assert closure =~ "`MEMORY_WRITE` actions"
    assert report =~ "- Cases: `20`"
    assert report =~ "- Passed: `20`"
    assert report =~ "OS-level process kill: not executed and not claimed"
    assert manifest =~ "Post_Stage_1_Persistence_v0_Closure.md"
    assert inventory =~ "Storage and Persistence Gate"
    assert traceability =~ "accepted_by_closure"
  end

  defp load_json(relative_path) do
    @docs_root
    |> Path.join(relative_path)
    |> File.read!()
    |> Jason.decode!()
  end
end
