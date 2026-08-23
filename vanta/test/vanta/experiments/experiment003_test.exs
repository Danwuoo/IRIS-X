defmodule Vanta.Experiment003Test do
  use ExUnit.Case

  alias Vanta.{Experiment003, Schema}

  @fixture_root Path.expand("../../fixtures/document_ops", __DIR__)

  @tag :integration
  test "experiment003 runner writes journal audit and replay smoke results" do
    out_dir =
      Path.join(System.tmp_dir!(), "vanta_experiment003_#{System.unique_integer([:positive])}")

    File.rm_rf!(out_dir)

    assert {:ok, run} = Experiment003.run(@fixture_root, out_dir: out_dir)

    assert run["status"] == "completed"
    assert run["fixture_count"] == fixture_count()
    assert :ok = Schema.validate("experiment_run", run)
    assert File.exists?(Path.join(out_dir, "run.json"))
    assert File.exists?(Path.join(out_dir, "summary.md"))

    assert run["metrics"]["baseline"]["commit_integrity_score"] == 0.0
    assert run["metrics"]["baseline"]["replay_consistency"] == 0.0
    assert run["metrics"]["baseline"]["audit_completeness"] == 0.0

    assert run["metrics"]["treatment"]["commit_integrity_score"] == 1.0
    assert run["metrics"]["treatment"]["replay_consistency"] == 1.0
    assert run["metrics"]["treatment"]["audit_completeness"] == 1.0

    assert run["metrics"]["treatment"]["invalid_action_rate"] ==
             invalid_action_rate(run["tasks"], "treatment")

    assert Enum.all?(run["tasks"], &get_in(&1, ["replay", "consistent"]))
    assert Enum.all?(run["tasks"], &get_in(&1, ["treatment", "audit_complete"]))
  end

  defp fixture_count do
    @fixture_root
    |> Path.join("*/task.json")
    |> Path.wildcard()
    |> length()
  end

  defp invalid_action_rate(tasks, arm) do
    results = Enum.map(tasks, & &1[arm])
    total_actions = results |> Enum.map(& &1["total_actions"]) |> Enum.sum() |> max(1)
    invalid_actions = results |> Enum.map(& &1["invalid_actions"]) |> Enum.sum()

    invalid_actions / total_actions
  end
end
