defmodule Vanta.FixtureCommitExperimentTest do
  use ExUnit.Case, async: false

  alias Vanta.FixtureCommitExperiment
  alias Vanta.FixtureCommitExperiment.Validator

  @fixture_root "docs/04_experiments/fixtures/fixture_local_committable_execution"

  @tag :fast_unit
  test "G10 fixture validator locks all 28 scenarios and action-specific authorization" do
    fixtures = Validator.load!(@fixture_root)

    assert length(fixtures) == 28
    assert Enum.sort(Enum.map(fixtures, & &1["scenario"])) == Enum.sort(Validator.scenarios())
    assert "commit_fixture_document_candidate" in Vanta.fixture_commit_action_types()
    refute "commit_fixture_document_candidate" in Vanta.action_types()
    refute "COMMITTABLE" in Vanta.allowed_side_effect_classes()

    assert Vanta.side_effect_allowed?(
             "commit_fixture_document_candidate",
             "COMMITTABLE"
           )

    refute Vanta.side_effect_allowed?("apply_reversible_patch", "COMMITTABLE")
  end

  @tag :fast_unit
  test "standalone approval and dedicated action payload schemas validate independently" do
    source = Path.join(@fixture_root, "workspace_template/inputs/source.md")
    candidate = Path.join(@fixture_root, "workspace_template/candidates/candidate.md")

    identity = %{
      "fixture_id" => "g10_document_promotion",
      "workspace_id" => "ephemeral_workspace_v0",
      "workspace_marker_path" => ".vanta_fixture_workspace.json",
      "source_path" => "inputs/source.md",
      "candidate_path" => "candidates/candidate.md",
      "committed_path" => "committed/document.md"
    }

    approval = %{
      "schema_version" => Vanta.schema_version(),
      "approval_id" => "approval_schema_test",
      "decision" => "approved",
      "approver_type" => "test_authority",
      "approver_identity" => "schema-test",
      "action_type" => "commit_fixture_document_candidate",
      "scope" => %{
        "action_type" => "commit_fixture_document_candidate",
        "target_identity" => identity,
        "candidate_hash" => Vanta.Hash.file_hash(candidate),
        "policy_version" => "fixture-local-commit-approval-v0"
      },
      "issued_at" => "2026-07-15T00:00:00Z",
      "not_before" => "2026-07-15T00:00:00Z",
      "expires_at" => "2027-07-16T00:00:00Z"
    }

    assert :ok == Vanta.Schema.validate("approval_record", approval)

    action_sequence = %{
      "schema_version" => Vanta.schema_version(),
      "planner_id" => "schema-test",
      "actions" => [
        %{
          "action_type" => "commit_fixture_document_candidate",
          "action_payload" => %{
            "target_identity" => identity,
            "source_hash" => Vanta.Hash.file_hash(source),
            "candidate_hash" => Vanta.Hash.file_hash(candidate),
            "approval_record_ref" => approval["approval_id"],
            "approval_policy_version" => "fixture-local-commit-approval-v0",
            "idempotency_key" => "schema-test-key",
            "rollback_or_compensation_statement" => "fixture_commit_restore"
          }
        }
      ]
    }

    assert :ok == Vanta.Schema.validate("planner_action_sequence", action_sequence)

    assert {:error, _errors} =
             Vanta.Schema.validate(
               "planner_action_sequence",
               put_in(
                 action_sequence,
                 ["actions", Access.at(0), "action_payload", "memory_write"],
                 %{}
               )
             )
  end

  @tag :integration
  test "complete 28-case failure-injection matrix passes every G10 hard gate" do
    out_dir = temp_dir("g10_integration")

    assert {:ok, result} =
             FixtureCommitExperiment.run(fixture_root: @fixture_root, out_dir: out_dir)

    assert result.run["threshold_status"] == "pass_acceptance_candidate"
    assert result.run["fixture_count"] == 28
    assert result.run["case_pass_count"] == 28
    assert result.run["case_fail_count"] == 0
    assert Enum.all?(result.run["hard_metrics"], fn {_name, metric} -> metric["passed"] end)
    assert Enum.all?(result.fixture_results, & &1["passed"])
    assert result.run["source_fixture_integrity"]["unchanged"]
  end

  @tag :generated_artifact_tooling
  test "Mix task writes the complete Experiment 007 artifact contract" do
    out_dir = temp_dir("g10_mix_task")
    Mix.Task.reenable("vanta.fixture_commit_experiment")

    Mix.Tasks.Vanta.FixtureCommitExperiment.run([
      "--fixture-root",
      @fixture_root,
      "--out-dir",
      out_dir
    ])

    Enum.each(
      ~w(run.json fixture_results.json summary.md fixture_inventory.md failure_injection_matrix.md environment_manifest.json schema_policy_versions.json),
      &assert(File.regular?(Path.join(out_dir, &1)))
    )

    run = out_dir |> Path.join("run.json") |> Vanta.Schema.load_json!()
    assert run["threshold_status"] == "pass_acceptance_candidate"
    refute run["report_label"] == "accepted_by_closure"
  end

  defp temp_dir(prefix) do
    path = Path.join(System.tmp_dir!(), "#{prefix}_#{System.unique_integer([:positive])}")
    on_exit(fn -> File.rm_rf!(path) end)
    path
  end
end
