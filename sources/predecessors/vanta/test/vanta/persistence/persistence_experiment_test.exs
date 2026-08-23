defmodule Vanta.PersistenceExperimentTest do
  use ExUnit.Case, async: false

  @moduletag :generated_artifact_tooling

  alias Vanta.{PersistenceExperiment, Schema}

  @required_files ~w(
    run.json
    summary.md
    fixture_inventory.md
    failure_injection_results.json
    failure_injection_matrix.md
    environment_manifest.json
    schema_hash_policy_versions.json
  )

  test "Mix task produces a complete validating 20-case candidate run" do
    result_dir =
      Path.join(
        System.tmp_dir!(),
        "vanta_persistence_runner_test_#{System.unique_integer([:positive])}"
      )

    on_exit(fn -> File.rm_rf(result_dir) end)
    Mix.Task.reenable("vanta.persistence_experiment")

    Mix.Tasks.Vanta.PersistenceExperiment.run([
      "--timestamp",
      "test_run",
      "--result-dir",
      result_dir
    ])

    Enum.each(@required_files, fn filename ->
      assert File.regular?(Path.join(result_dir, filename)), "missing #{filename}"
    end)

    run = load_json(Path.join(result_dir, "run.json"))
    results = load_json(Path.join(result_dir, "failure_injection_results.json"))

    assert :ok = Schema.validate("experiment_run", run)
    assert run["threshold_status"] == "pass_acceptance_candidate"
    assert run["fixture_count"] == 20
    assert run["metrics"]["case_pass_rate"] == 1.0

    assert Enum.all?(PersistenceExperiment.hard_requirements(), fn {metric, required} ->
             run["metrics"][metric] == required
           end)

    assert length(results["cases"]) == 20
    assert Enum.all?(results["cases"], & &1["passed"])
    refute File.read!(Path.join(result_dir, "summary.md")) =~ "accepted_by_closure"
    assert File.read!(Path.join(result_dir, "summary.md")) =~ "no OS-level kill claim"
  end

  defp load_json(path), do: path |> File.read!() |> Jason.decode!()
end
