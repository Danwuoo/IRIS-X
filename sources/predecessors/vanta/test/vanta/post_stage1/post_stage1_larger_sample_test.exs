defmodule Vanta.PostStage1LargerSampleTest do
  use ExUnit.Case

  alias Vanta.{PostStage1LargerSample, Schema}

  @fixture_root Path.expand("../../fixtures/document_ops", __DIR__)

  @tag :fast_unit
  test "sample frame fixes 48 fixtures across 8 strata" do
    frame = PostStage1LargerSample.sample_frame()

    assert length(frame) == 48

    strata = Enum.group_by(frame, & &1["stratum"])
    assert map_size(strata) == 8
    assert Enum.all?(strata, fn {_stratum, items} -> length(items) == 6 end)
  end

  @tag :docs_consistency
  test "sample frame fixtures exist and validate with expected artifacts" do
    Enum.each(PostStage1LargerSample.sample_frame(), fn %{"fixture_id" => fixture_id} ->
      workspace = Path.join(@fixture_root, fixture_id)
      task = Schema.load_json!(Path.join(workspace, "task.json"))
      acceptance = Schema.load_json!(Path.join(workspace, "expected/acceptance.json"))

      assert :ok = Schema.validate("benchmark_task", task)
      assert :ok = Schema.validate("fixture_acceptance", acceptance)
      assert File.exists?(Path.join(workspace, "expected/acceptance.json"))
    end)
  end

  @tag :fast_unit
  test "reversible append section fixture exposes exact insertion contract" do
    exact_line = "Add audit trail before commit."

    Enum.each(
      [@fixture_root, Path.expand("../../../docs/04_experiments/fixtures/document_ops", __DIR__)],
      fn
        root ->
          workspace = Path.join(root, "docops_ps1_reversible_append_section_001")
          task = Schema.load_json!(Path.join(workspace, "task.json"))
          acceptance = Schema.load_json!(Path.join(workspace, "expected/acceptance.json"))

          assert task["prompt"] =~ exact_line
          assert Enum.any?(task["success_criteria"], &String.contains?(&1, exact_line))

          action_sequence = get_in(acceptance, ["action_sequence"])

          assert {:ok, action_sequence} =
                   Vanta.PlannerAdapter.validate_action_sequence(action_sequence)

          assert get_in(action_sequence, [
                   "actions",
                   Access.at(0),
                   "action_payload",
                   "replacement"
                 ]) ==
                   exact_line
      end
    )
  end

  @tag :fast_unit
  test "fixture hash inventory is deterministic" do
    workspace = Path.join(@fixture_root, "docops_ps1_traceability_multisource_001")

    assert PostStage1LargerSample.fixture_hash(workspace) ==
             PostStage1LargerSample.fixture_hash(workspace)
  end

  @tag :integration
  test "mock run emits Lane A artifacts and pass_acceptance_candidate" do
    out_dir =
      Path.join(System.tmp_dir!(), "vanta_lane_a_#{System.unique_integer([:positive])}")

    File.rm_rf!(out_dir)

    assert {:ok, run} =
             PostStage1LargerSample.run(@fixture_root,
               out_dir: out_dir,
               planner_adapter: __MODULE__.MockPlanner,
               verifier_adapter: __MODULE__.MockVerifier,
               recovery_adapter: __MODULE__.MockRecovery,
               context_planner_adapter: __MODULE__.MockContextPlanner,
               model: "test-model"
             )

    assert run["sample_frame_id"] == "PS1-LA-SAMPLE-002"
    assert run["metric_policy_version"] == "PS1-LA-METRIC-001"
    assert run["threshold_status"] == "pass_acceptance_candidate"
    assert run["fixture_count"] == 48

    assert get_in(run, ["run_controls", "prompt_template_version"]) ==
             "post_stage_1_larger_sample_openclaw_v5_ws_evidence_packet_acceptance_alignment"

    assert :ok = Schema.validate("experiment_run", run)

    assert File.exists?(Path.join(out_dir, "run.json"))
    assert File.exists?(Path.join(out_dir, "summary.md"))
    assert File.exists?(Path.join(out_dir, "fixture_inventory.md"))

    summary = File.read!(Path.join(out_dir, "summary.md"))
    assert String.contains?(summary, "Threshold status: pass_acceptance_candidate")
    assert String.contains?(summary, "must not be described as H1-H5 validation")
  end

  @tag :integration
  test "runner records planner adapter errors instead of aborting measured artifacts" do
    out_dir =
      Path.join(System.tmp_dir!(), "vanta_lane_a_failed_#{System.unique_integer([:positive])}")

    File.rm_rf!(out_dir)

    assert {:ok, run} =
             PostStage1LargerSample.run(@fixture_root,
               out_dir: out_dir,
               planner_adapter: __MODULE__.OneBadPlanner,
               verifier_adapter: __MODULE__.MockVerifier,
               recovery_adapter: __MODULE__.MockRecovery,
               context_planner_adapter: __MODULE__.MockContextPlanner,
               model: "test-model"
             )

    failed_task =
      Enum.find(run["tasks"], &(&1["task_id"] == "docops_struct_inspect_001"))

    assert run["threshold_status"] == "failed_no_acceptance"
    assert get_in(failed_task, ["runtime_governance", "treatment", "status"]) == "planner_error"
    assert get_in(run, ["metrics", "hard_gates", "required_artifacts_valid"]) == false
    assert get_in(run, ["metrics", "treatment", "task_success_rate"]) < 1.0
    assert [_error] = get_in(run, ["metrics", "hard_gates", "artifact_errors"])

    assert :ok = Schema.validate("experiment_run", run)
    assert File.exists?(Path.join(out_dir, "run.json"))
    assert File.exists?(Path.join(out_dir, "summary.md"))
    assert File.exists?(Path.join(out_dir, "fixture_inventory.md"))

    summary = File.read!(Path.join(out_dir, "summary.md"))
    assert String.contains?(summary, "Threshold status: failed_no_acceptance")
    assert String.contains?(summary, "## Blocking Details")
  end

  @tag :fast_unit
  test "threshold decision distinguishes blocked and failed runs" do
    blocked = %{
      "sample_frame_id" => "PS1-LA-SAMPLE-002",
      "metric_policy_version" => "PS1-LA-METRIC-001",
      "fixture_count" => 47,
      "run_controls" => %{},
      "arm_metadata" => %{},
      "fixture_inventory_ref" => "fixture_inventory.md",
      "metrics" => %{"treatment" => %{}}
    }

    failed =
      put_in(blocked, ["fixture_count"], 48)
      |> Map.put("run_controls", %{"model_identity" => "openai-codex/test"})
      |> Map.put("arm_metadata", %{"baseline" => %{}})
      |> Map.put("metrics", %{
        "hard_gates" => %{
          "unsupported_commits" => 1,
          "memory_writes" => 0,
          "disallowed_side_effect_classes" => 0,
          "required_artifacts_valid" => true,
          "arm_identity_compliant" => true,
          "fixture_count_exact" => true,
          "strata_complete" => true
        },
        "baseline" => required_metrics(0.0),
        "treatment" => required_metrics(1.0)
      })

    assert PostStage1LargerSample.threshold_status(blocked) == "blocked_missing_metric"
    assert PostStage1LargerSample.threshold_status(failed) == "failed_no_acceptance"
  end

  defp required_metrics(value) do
    %{
      "task_success_rate" => value,
      "invalid_action_rate" => 0.0,
      "verifier_false_accept_rate" => 0.0,
      "verifier_false_reject_rate" => 0.0,
      "evidence_sufficiency_score" => value,
      "commit_integrity_score" => value,
      "replay_consistency" => value,
      "audit_completeness" => value,
      "recovery_success_rate" => value,
      "targeted_recovery_success" => value,
      "failure_label_accuracy" => value,
      "repeated_failure_rate" => 0.0,
      "working_set_budget_adherence" => value,
      "working_set_provenance_completeness" => value,
      "context_omission_error_rate" => 0.0,
      "working_set_relevance_score" => value,
      "long_task_stability" => value
    }
  end

  defmodule MockPlanner do
    def env(_opts), do: {:ok, %{model: "openai-codex/test-model"}}

    def propose_actions(_task, workspace, _opts) do
      Vanta.FixtureAcceptance.action_sequence(workspace)
    end
  end

  defmodule OneBadPlanner do
    def env(_opts), do: {:ok, %{model: "openai-codex/test-model"}}

    def propose_actions(%{"task_id" => "docops_struct_inspect_001"}, _workspace, _opts) do
      {:error, {:invalid_action_sequence, [{"schema mismatch", "#/actions/0"}]}}
    end

    def propose_actions(_task, workspace, _opts) do
      Vanta.FixtureAcceptance.action_sequence(workspace)
    end
  end

  defmodule MockVerifier do
    def env(_opts), do: {:ok, %{model: "openai-codex/test-model"}}
    def verifier_id(_opts), do: "openclaw_agent_local/openai-codex/test-model_verifier"

    def verify(review_input, _opts) do
      decision = if review_input["oracle_valid"], do: "accept", else: "reject"

      output = %{
        "schema_version" => Vanta.schema_version(),
        "verifier_output_id" => "mock_verifier_#{review_input["review_item_id"]}",
        "episode_id" => review_input["episode_id"],
        "step_id" => review_input["step_id"],
        "evidence_refs" => review_input["evidence_refs"] || [],
        "decision" => decision,
        "verification_scope" => [
          "preconditions",
          "postconditions",
          "evidence_sufficiency",
          "policy_constraints",
          "side_effect_safety",
          "state_consistency"
        ],
        "validity_score" => if(decision == "accept", do: 1.0, else: 0.0),
        "confidence" => 1.0,
        "calibration_state" => %{"method" => "mock"},
        "disagreement" => %{},
        "risk_score" => if(decision == "accept", do: 0.0, else: 1.0),
        "violated_constraints" => [],
        "required_extra_evidence" => [],
        "failure_logits" => %{},
        "credit_hints" => %{}
      }

      {:ok, Schema.validate!("verifier_output", output)}
    end
  end

  defmodule MockRecovery do
    def env(_opts), do: {:ok, %{model: "openai-codex/test-model"}}
    def recovery_id(_opts), do: "openclaw_agent_local/openai-codex/test-model"

    def recover(recovery_input, opts) do
      {policy, labels} = expected(recovery_input["task_id"])

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
          "prompt_chars" => 100,
          "response_chars" => 50,
          "estimated_input_tokens" => 25,
          "estimated_output_tokens" => 13,
          "max_prompt_chars" => Keyword.get(opts, :max_prompt_chars, 20_000),
          "max_response_chars" => Keyword.get(opts, :max_response_chars, 12_000),
          "max_action_attempts" => Keyword.get(opts, :max_action_attempts, 1)
        }
      }

      {:ok, Schema.validate!("recovery_decision", decision)}
    end

    defp expected(task_id)
         when task_id in ~w(docops_rollback_failure_001 docops_ps1_recovery_structured_rollback_001),
         do: {"reconstruct_rollback_from_diff", ["F_EXEC", "F_EXEC_ROLLBACK_FAILURE"]}

    defp expected(task_id)
         when task_id in ~w(docops_audit_gap_001 docops_ps1_recovery_audit_gap_complete_refs_001),
         do: {"repair_audit_refs", ["F_EXEC", "F_EXEC_AUDIT_GAP"]}

    defp expected("docops_compensable_action_001"),
      do: {"produce_compensation_record", ["F_EXEC", "F_EXEC_COMPENSATION_REQUIRED"]}
  end

  defmodule MockContextPlanner do
    def env(_opts), do: {:ok, %{model: "openai-codex/test-model"}}
    def planner_id(_opts), do: "openclaw_agent_local/openai-codex/test-model"

    def plan(task, _context_artifact, opts) do
      action_sequence =
        case task["task_id"] do
          "docops_ws_traceability_long_001" ->
            validate("inputs/source.md", "traceability_links")

          "docops_ws_evidence_packet_001" ->
            validate("inputs/evidence_packet.json")

          "docops_ws_irrelevant_context_001" ->
            validate("inputs/source.md")

          "docops_ws_omission_trap_001" ->
            validate("inputs/late_source.md")

          "docops_ws_recovery_context_001" ->
            validate("inputs/recovery_context.md")

          "docops_ps1_ws_structured_edit_context_001" ->
            validate("inputs/source.md")
        end

      {:ok,
       %{
         action_sequence: action_sequence,
         budget_usage: %{
           "model_call_count" => 1,
           "prompt_chars" => 500,
           "response_chars" => 100,
           "estimated_input_tokens" => 125,
           "estimated_output_tokens" => 25,
           "max_prompt_chars" => Keyword.get(opts, :max_prompt_chars, 20_000),
           "max_response_chars" => Keyword.get(opts, :max_response_chars, 12_000)
         }
       }}
    end

    defp validate(path) do
      %{
        "actions" => [
          %{"action_type" => "validate_artifact", "action_payload" => %{"path" => path}}
        ]
      }
    end

    defp validate(path, validation) do
      %{
        "actions" => [
          %{
            "action_type" => "validate_artifact",
            "action_payload" => %{"path" => path, "validation" => validation}
          }
        ]
      }
    end
  end
end
