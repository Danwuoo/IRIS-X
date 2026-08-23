defmodule Vanta.Experiment004Test do
  use ExUnit.Case

  alias Vanta.{
    Experiment004,
    FixtureAcceptance,
    OpenClawRecoveryAdapter,
    RecoveryRunner,
    Schema
  }

  @fixture_root Path.expand("../../fixtures/document_ops", __DIR__)
  @phase4_fixtures ~w(
    docops_audit_gap_001
    docops_compensable_action_001
    docops_rollback_failure_001
  )

  @tag :fast_unit
  test "openclaw recovery adapter parses schema-valid payload text and records budget" do
    input = recovery_input("docops_rollback_failure_001")

    runner = fn prompt, env ->
      assert String.contains?(prompt, "Experiment 004")
      assert env.model == "openai-codex/test-model"

      {:ok,
       %{
         "payloads" => [
           %{
             "text" =>
               Jason.encode!(%{
                 "failure_labels" => ["F_EXEC", "F_EXEC_ROLLBACK_FAILURE"],
                 "primary_failure_label" => "F_EXEC_ROLLBACK_FAILURE",
                 "recovery_policy" => "reconstruct_rollback_from_diff",
                 "confidence" => 0.75,
                 "required_evidence_refs" => ["evidence_1"]
               })
           }
         ]
       }}
    end

    assert {:ok, decision} =
             OpenClawRecoveryAdapter.recover(input,
               wsl_executable: "mock-wsl",
               openclaw_dir: "~/openclaw",
               model: "test-model",
               runner: runner,
               max_action_attempts: 2
             )

    assert decision["recovery_policy"] == "reconstruct_rollback_from_diff"
    assert "F_EXEC_ROLLBACK_FAILURE" in decision["failure_labels"]
    assert decision["budget_usage"]["model_call_count"] == 1
    assert decision["budget_usage"]["prompt_chars"] > 0
    assert decision["budget_usage"]["response_chars"] > 0
    assert decision["budget_usage"]["max_action_attempts"] == 2
    assert :ok = Schema.validate("recovery_decision", decision)
  end

  @tag :fast_unit
  test "openclaw recovery adapter parses JSON fences and normalizes malformed output to no recovery" do
    fenced_runner = fn _prompt, _env ->
      {:ok,
       %{
         "payloads" => [
           %{
             "text" => """
             ```json
             {
               "failure_labels": ["F_EXEC", "F_EXEC_AUDIT_GAP"],
               "primary_failure_label": "F_EXEC_AUDIT_GAP",
               "recovery_policy": "repair_audit_refs",
               "confidence": 0.6,
               "required_evidence_refs": []
             }
             ```
             """
           }
         ]
       }}
    end

    assert {:ok, fenced} =
             OpenClawRecoveryAdapter.recover(recovery_input("docops_audit_gap_001"),
               wsl_executable: "mock-wsl",
               openclaw_dir: "~/openclaw",
               model: "test-model",
               runner: fenced_runner
             )

    assert fenced["recovery_policy"] == "repair_audit_refs"
    assert :ok = Schema.validate("recovery_decision", fenced)

    malformed_runner = fn _prompt, _env ->
      {:ok, %{"payloads" => [%{"text" => "not json"}]}}
    end

    assert {:ok, malformed} =
             OpenClawRecoveryAdapter.recover(recovery_input("docops_audit_gap_001"),
               wsl_executable: "mock-wsl",
               openclaw_dir: "~/openclaw",
               model: "test-model",
               runner: malformed_runner
             )

    assert malformed["recovery_policy"] == "no_recovery"
    assert malformed["primary_failure_label"] == "unknown"
    assert is_binary(malformed["adapter_error"])
    assert :ok = Schema.validate("recovery_decision", malformed)
  end

  @tag :integration
  test "targeted recovery policies repair the three Phase 4 fixtures" do
    Enum.each(@phase4_fixtures, fn fixture_id ->
      {task, workspace} = load_fixture(fixture_id)

      assert {:ok, result} =
               RecoveryRunner.run_task(task, workspace, recovery_adapter: __MODULE__.MockRecovery)

      assert result.initial_result.status == "rejected"

      assert result.initial_result.rollback_status ==
               FixtureAcceptance.expected_rollback_status(workspace)

      assert result.failure_label_accuracy?
      assert result.targeted_recovery_success?
      assert result.recovery_success?
      assert result.recovery_outcome["success"] == true

      assert File.exists?(Path.join(result.workspace, result.recovery_outcome["artifact_path"]))
    end)
  end

  @tag :integration
  test "experiment004 mock run emits matched-budget blind retry and targeted metrics" do
    out_dir =
      Path.join(System.tmp_dir!(), "vanta_experiment004_#{System.unique_integer([:positive])}")

    File.rm_rf!(out_dir)

    assert {:ok, run} =
             Experiment004.run(@fixture_root,
               recovery_adapter: __MODULE__.MockRecovery,
               out_dir: out_dir
             )

    assert run["status"] == "completed"
    assert run["fixture_count"] == length(@phase4_fixtures)
    assert :ok = Schema.validate("experiment_run", run)
    assert File.exists?(Path.join(out_dir, "run.json"))
    assert File.exists?(Path.join(out_dir, "summary.md"))

    assert run["metrics"]["compute_matching"]["budget_matched"] == true
    assert run["metrics"]["targeted_recovery"]["recovery_success_rate"] == 1.0
    assert run["metrics"]["targeted_recovery"]["targeted_recovery_success"] == 1.0
    assert run["metrics"]["targeted_recovery"]["failure_label_accuracy"] == 1.0
    assert run["metrics"]["targeted_recovery"]["repeated_failure_rate"] == 0.0
    assert run["metrics"]["targeted_recovery"]["rollback_recovery_success"] == 1.0
    assert run["metrics"]["targeted_recovery"]["audit_gap_closure_rate"] == 1.0
    assert run["metrics"]["targeted_recovery"]["compensation_policy_accuracy"] == 1.0

    assert run["metrics"]["blind_retry"]["recovery_success_rate"] == 0.0
    assert run["metrics"]["blind_retry"]["repeated_failure_rate"] == 1.0

    assert Enum.all?(run["tasks"], fn task ->
             targeted = task["targeted_recovery"]["budget_usage"]
             blind = task["blind_retry"]["budget_usage"]

             targeted["model_call_count"] == blind["model_call_count"] and
               targeted["max_action_attempts"] == blind["max_action_attempts"]
           end)
  end

  defp recovery_input(task_id) do
    %{
      "schema_version" => Vanta.schema_version(),
      "experiment_id" => "experiment_004_targeted_recovery",
      "task_id" => task_id,
      "episode_id" => "episode_#{task_id}",
      "allowed_recovery_policies" => [
        "reconstruct_rollback_from_diff",
        "repair_audit_refs",
        "produce_compensation_record"
      ],
      "budget_constraints" => %{
        "max_prompt_chars" => 20_000,
        "max_response_chars" => 12_000,
        "max_action_attempts" => 1
      },
      "failure_context" => %{"summary" => "mock"}
    }
  end

  defp load_fixture(fixture_id) do
    workspace = Path.join(@fixture_root, fixture_id)
    {Schema.load_json!(Path.join(workspace, "task.json")), workspace}
  end

  defmodule MockRecovery do
    def env(_opts), do: {:ok, %{model: "mock"}}
    def recovery_id(_opts), do: "openclaw_agent_local/mock"

    def recover(recovery_input, _opts) do
      {labels, policy} = expected(recovery_input["task_id"])

      decision = %{
        "schema_version" => Vanta.schema_version(),
        "decision_id" => "mock_recovery_#{recovery_input["task_id"]}",
        "task_id" => recovery_input["task_id"],
        "episode_id" => recovery_input["episode_id"],
        "failure_labels" => labels,
        "primary_failure_label" => List.last(labels),
        "recovery_policy" => policy,
        "confidence" => 1.0,
        "required_evidence_refs" => [],
        "budget_usage" => %{
          "model_call_count" => 1,
          "prompt_chars" => 100 + String.length(recovery_input["task_id"]),
          "response_chars" => 80,
          "estimated_input_tokens" => 25,
          "estimated_output_tokens" => 20,
          "max_prompt_chars" =>
            get_in(recovery_input, ["budget_constraints", "max_prompt_chars"]),
          "max_response_chars" =>
            get_in(recovery_input, ["budget_constraints", "max_response_chars"]),
          "max_action_attempts" =>
            get_in(recovery_input, ["budget_constraints", "max_action_attempts"])
        }
      }

      {:ok, Vanta.Schema.validate!("recovery_decision", decision)}
    end

    defp expected("docops_rollback_failure_001"),
      do: {["F_EXEC", "F_EXEC_ROLLBACK_FAILURE"], "reconstruct_rollback_from_diff"}

    defp expected("docops_audit_gap_001"),
      do: {["F_EXEC", "F_EXEC_AUDIT_GAP"], "repair_audit_refs"}

    defp expected("docops_compensable_action_001"),
      do: {["F_EXEC", "F_EXEC_COMPENSATION_REQUIRED"], "produce_compensation_record"}
  end
end
