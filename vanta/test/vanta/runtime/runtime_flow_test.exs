defmodule Vanta.RuntimeFlowTest do
  use ExUnit.Case

  alias Vanta.{
    ActionExecutor,
    BaselineRunner,
    CommitController,
    EpisodeJournal,
    EvaluationHarness,
    EvidenceBuilder,
    ExecutionIRCompiler,
    Experiment001,
    FixtureAcceptance,
    OpenClawPlannerAdapter,
    OpenAIPlannerAdapter,
    ReplayRunner,
    Runtime,
    Schema,
    StateManager,
    VerifierRuntime
  }

  @fixture_root Path.expand("../../fixtures/document_ops", __DIR__)
  @ps1_fix_007_expected_rejected_fixtures ~w(
    docops_ps1_invalid_reversible_in_readonly_001
    docops_struct_simulation_mutation_001
    docops_ps1_struct_backup_files_dropped_001
    docops_rollback_failure_001
    docops_ps1_recovery_structured_rollback_001
  )
  @ps1_fix_008_expected_rejected_fixtures ~w(
    docops_struct_wrong_diff_001
    docops_struct_missing_backup_metadata_001
  )
  @ps1_fix_006_positive_fixtures ~w(
    docops_struct_inspect_001
    docops_struct_contract_fail_001
    docops_struct_insert_after_001
    docops_reversible_edit_001
    docops_ps1_reversible_append_section_001
    docops_ps1_reversible_replace_heading_001
    docops_ps1_reversible_patch_multiline_001
    docops_ws_evidence_packet_001
    docops_ws_omission_trap_001
    docops_ws_recovery_context_001
  )

  @tag :fast_unit
  test "verifier requests extra evidence when required evidence is missing" do
    {task, workspace} = load_fixture("docops_simulate_patch_001")
    state = StateManager.from_task(task)

    {:ok, step} =
      ExecutionIRCompiler.compile(task, "episode_missing_evidence", "simulate_patch", %{
        "path" => "inputs/spec.md",
        "find" => "First controlled environment: TBD.",
        "replace" => "First controlled environment: Document Ops."
      })

    {:ok, observation} = ActionExecutor.execute(workspace, step)

    evidence =
      state
      |> EvidenceBuilder.build(step, observation)
      |> Map.delete("observation")

    verifier_output = VerifierRuntime.verify(step, evidence)

    assert verifier_output["decision"] == "request_evidence"
    assert "observation" in verifier_output["required_extra_evidence"]
  end

  @tag :fast_unit
  test "forbidden side-effect classes cannot enter the commit path" do
    {task, workspace} = load_fixture("docops_simulate_patch_001")
    state = StateManager.from_task(task)

    {:ok, step} =
      ExecutionIRCompiler.compile(task, "episode_forbidden", "simulate_patch", %{
        "path" => "inputs/spec.md",
        "find" => "First controlled environment: TBD.",
        "replace" => "First controlled environment: Document Ops."
      })

    {:ok, observation} = ActionExecutor.execute(workspace, step)
    forbidden_step = Map.put(step, "side_effect_class", "IRREVERSIBLE")
    evidence = EvidenceBuilder.build(state, forbidden_step, observation)
    verifier_output = VerifierRuntime.verify(forbidden_step, evidence)

    assert verifier_output["decision"] == "reject"

    assert {:error, :verifier_not_accept} =
             CommitController.commit(state, forbidden_step, evidence, verifier_output)
  end

  @tag :fast_unit
  test "commit controller only commits verifier accept decisions" do
    {task, workspace} = load_fixture("docops_simulate_patch_001")
    state = StateManager.from_task(task)

    {:ok, step} =
      ExecutionIRCompiler.compile(task, "episode_commit_gate", "simulate_patch", %{
        "path" => "inputs/spec.md",
        "find" => "First controlled environment: TBD.",
        "replace" => "First controlled environment: Document Ops."
      })

    {:ok, observation} = ActionExecutor.execute(workspace, step)
    evidence = EvidenceBuilder.build(state, step, observation)
    verifier_output = VerifierRuntime.verify(step, evidence)

    assert verifier_output["decision"] == "accept"

    assert {:ok, committed_state} =
             CommitController.commit(state, step, evidence, verifier_output)

    assert committed_state["state_hash"] == evidence["post_state_hash"]

    rejected_output = Map.put(verifier_output, "decision", "reject")

    assert {:error, :verifier_not_accept} =
             CommitController.commit(state, step, evidence, rejected_output)
  end

  @tag :fast_unit
  test "reversible edit writes backup metadata and can rollback in a fixture workspace" do
    workspace = copy_fixture("docops_reversible_edit_001")
    task = Schema.load_json!(Path.join(workspace, "task.json"))
    target = Path.join(workspace, "inputs/glossary.md")
    original = File.read!(target)

    {:ok, step} =
      ExecutionIRCompiler.compile(task, "episode_reversible", "apply_reversible_patch", %{
        "path" => "inputs/glossary.md",
        "find" => "Verifier Runtime: final-answer checker for a completed task.",
        "replace" =>
          "Verifier Runtime: runtime verifier for action feasibility, evidence sufficiency, and final correctness where applicable."
      })

    {:ok, observation} = ActionExecutor.execute(workspace, step)

    assert observation["mutated"] == true
    assert File.read!(target) != original
    assert File.exists?(Path.join(workspace, observation["backup_metadata"]["backup_path"]))
    assert File.exists?(Path.join(workspace, observation["backup_metadata"]["metadata_path"]))

    assert :ok = ActionExecutor.rollback(workspace, observation["backup_metadata"])
    assert File.read!(target) == original
  end

  @tag :fast_unit
  test "episode journal records state, evidence, verifier, commit, and rollback status" do
    {task, workspace} = load_fixture("docops_simulate_patch_001")
    state = StateManager.from_task(task)
    episode_id = "episode_journal_records"

    {:ok, step} =
      ExecutionIRCompiler.compile(task, episode_id, "simulate_patch", %{
        "path" => "inputs/spec.md",
        "find" => "First controlled environment: TBD.",
        "replace" => "First controlled environment: Document Ops."
      })

    {:ok, observation} = ActionExecutor.execute(workspace, step)
    evidence = EvidenceBuilder.build(state, step, observation)
    verifier_output = VerifierRuntime.verify(step, evidence)

    journal =
      task
      |> EpisodeJournal.new(episode_id)
      |> EpisodeJournal.record_state(state)
      |> EpisodeJournal.record_step(step)
      |> EpisodeJournal.record_evidence(evidence)
      |> EpisodeJournal.record_verifier_output(verifier_output)
      |> EpisodeJournal.set_commit_status("committed")
      |> EpisodeJournal.set_rollback_status("not_applicable")
      |> EpisodeJournal.validate!()

    assert journal["state_hashes"] == [state["state_hash"]]
    assert journal["evidence_refs"] == [evidence["evidence_id"]]
    assert journal["verifier_output_refs"] == [verifier_output["verifier_output_id"]]
    assert journal["commit_status"] == "committed"
    assert journal["rollback_status"] == "not_applicable"

    refute EvaluationHarness.audit_complete?(journal)

    assert EvaluationHarness.audit_complete?(journal, %{
             evidence_packets: [evidence],
             verifier_outputs: [verifier_output]
           }) == false
  end

  @tag :integration
  test "runtime runs positive fixtures end-to-end and replay is consistent" do
    Enum.each(
      ~w(
        docops_read_traceability_001
        docops_detect_terms_001
        docops_simulate_patch_001
        docops_reversible_edit_001
        docops_multistep_commit_001
        docops_struct_inspect_001
        docops_struct_contract_pass_001
        docops_struct_contract_fail_001
        docops_struct_simulate_md_001
        docops_struct_simulate_json_001
        docops_struct_apply_reversible_001
        docops_struct_insert_before_001
        docops_struct_insert_after_001
      ),
      fn fixture_id ->
        {task, workspace} = load_fixture(fixture_id)

        assert {:ok, result} = Runtime.run_task(task, workspace)
        assert result.status == "committed"
        assert result.task_success?
        assert result.journal["commit_status"] == "committed"
        assert result.journal["rollback_status"] in ["not_applicable", "available"]

        Enum.each(result.evidence_packets, fn evidence ->
          assert :ok = Schema.validate("evidence_packet", evidence)
        end)

        Enum.each(result.verifier_outputs, fn verifier_output ->
          assert verifier_output["decision"] == "accept"
          assert :ok = Schema.validate("verifier_output", verifier_output)
        end)

        assert {:ok, replay} =
                 ReplayRunner.replay(task, workspace, result.journal, %{
                   evidence_packets: result.evidence_packets,
                   verifier_outputs: result.verifier_outputs
                 })

        assert replay.consistent?
      end
    )
  end

  @tag :integration
  test "runtime records every step in the expanded multi-step commit fixture" do
    {task, workspace} = load_fixture("docops_multistep_commit_001")

    assert {:ok, result} = Runtime.run_task(task, workspace)
    assert result.status == "committed"
    assert result.task_success?
    assert result.total_actions == 3
    assert result.invalid_actions == 0

    assert Enum.map(result.steps, & &1["action_type"]) == [
             "list_files",
             "simulate_patch",
             "compute_diff"
           ]

    assert length(result.journal["steps"]) == 3
    assert length(result.journal["evidence_refs"]) == 3
    assert length(result.journal["verifier_output_refs"]) == 3
    assert length(result.journal["state_hashes"]) == 4
    assert length(result.evidence_packets) == 3
    assert length(result.verifier_outputs) == 3

    assert Enum.all?(result.journal["steps"], &(&1["status"] == "committed"))
    assert Enum.all?(result.verifier_outputs, &(&1["decision"] == "accept"))

    assert EvaluationHarness.audit_complete?(result.journal, %{
             evidence_packets: result.evidence_packets,
             verifier_outputs: result.verifier_outputs
           })

    assert {:ok, replay} =
             ReplayRunner.replay(task, workspace, result.journal, %{
               evidence_packets: result.evidence_packets,
               verifier_outputs: result.verifier_outputs
             })

    assert replay.consistent?
  end

  @tag :integration
  test "runtime preserves audit refs for repeated action types in one episode" do
    {task, workspace} = load_fixture("docops_detect_terms_001")

    action_sequence = %{
      "actions" => [
        %{"action_type" => "read_file", "action_payload" => %{"path" => "inputs/term_a.md"}},
        %{"action_type" => "read_file", "action_payload" => %{"path" => "inputs/term_b.md"}},
        %{
          "action_type" => "validate_artifact",
          "action_payload" => %{
            "paths" => ["inputs/term_a.md", "inputs/term_b.md"],
            "validation" => "terminology_consistency"
          }
        }
      ]
    }

    assert {:ok, result} = Runtime.run_task(task, workspace, action_sequence: action_sequence)

    step_ids = Enum.map(result.steps, & &1["step_id"])

    assert result.status == "committed"
    assert length(step_ids) == 3
    assert length(Enum.uniq(step_ids)) == 3
    assert length(result.journal["steps"]) == 3
    assert length(result.journal["evidence_refs"]) == 3
    assert length(result.journal["verifier_output_refs"]) == 3
    assert length(Enum.uniq(result.journal["evidence_refs"])) == 3
    assert length(Enum.uniq(result.journal["verifier_output_refs"])) == 3

    assert EvaluationHarness.audit_complete?(result.journal, %{
             evidence_packets: result.evidence_packets,
             verifier_outputs: result.verifier_outputs
           })
  end

  @tag :integration
  test "multistep compute_diff accepts LF candidate content against CRLF source files" do
    workspace = copy_fixture("docops_multistep_commit_001")
    target = Path.join(workspace, "inputs/workflow.md")

    target
    |> File.read!()
    |> String.replace("\r\n", "\n")
    |> String.replace("\n", "\r\n")
    |> then(&File.write!(target, &1))

    task = Schema.load_json!(Path.join(workspace, "task.json"))

    assert {:ok, result} = Runtime.run_task(task, workspace)
    assert result.status == "committed"
    assert result.task_success?

    observation =
      result.evidence_packets
      |> Enum.map(& &1["observation"])
      |> Enum.find(&(&1["kind"] == "compute_diff"))

    assert observation["diff"] ==
             "-Verifier gate: TODO.\n+Verifier gate: Evidence Packet reviewed before commit."
  end

  @tag :integration
  test "runtime rejects negative fixtures and records invalid action paths" do
    Enum.each(
      ~w(
        docops_action_not_allowed_001
        docops_path_escape_001
        docops_wrong_diff_001
        docops_struct_selector_missing_001
        docops_struct_selector_ambiguous_001
        docops_struct_path_escape_001
        docops_struct_simulation_mutation_001
        docops_struct_missing_backup_metadata_001
        docops_struct_wrong_diff_001
      ),
      fn fixture_id ->
        {task, workspace} = load_fixture(fixture_id)

        assert {:ok, result} = Runtime.run_task(task, workspace)
        assert result.status == "rejected"
        assert result.task_success?
        assert result.invalid_actions >= 1
        assert result.journal["commit_status"] == "rejected"
        assert length(result.journal["steps"]) == 1
        assert length(result.evidence_packets) == 1
        assert length(result.verifier_outputs) == 1

        assert EvaluationHarness.audit_complete?(result.journal, %{
                 evidence_packets: result.evidence_packets,
                 verifier_outputs: result.verifier_outputs
               })

        assert {:ok, replay} = ReplayRunner.replay(task, workspace, result.journal, %{})
        assert replay.consistent?
      end
    )
  end

  @tag :fast_unit
  test "compile reject path records auditable evidence without accepted state update" do
    {task, workspace} = load_fixture("docops_action_not_allowed_001")
    initial_state = StateManager.from_task(task)

    assert {:ok, result} = Runtime.run_task(task, workspace)

    assert result.status == "rejected"
    assert result.journal["state_hashes"] == [initial_state["state_hash"]]

    [step] = result.journal["steps"]
    [evidence] = result.evidence_packets
    [verifier_output] = result.verifier_outputs

    assert step["status"] == "rejected"
    assert step["action_type"] == "simulate_patch"
    assert :ok = Schema.validate("execution_step", step)

    assert evidence["step_id"] == step["step_id"]
    assert evidence["observation"]["error"] =~ "action_not_allowed"
    assert :ok = Schema.validate("evidence_packet", evidence)

    assert verifier_output["decision"] == "reject"
    assert "action_not_allowed_by_task" in verifier_output["violated_constraints"]
    assert :ok = Schema.validate("verifier_output", verifier_output)

    assert EvaluationHarness.audit_complete?(result.journal, %{
             evidence_packets: result.evidence_packets,
             verifier_outputs: result.verifier_outputs
           })
  end

  @tag :fast_unit
  test "audit checklist detects missing refs and reversible rollback metadata gaps" do
    {task, workspace} = load_fixture("docops_reversible_edit_001")

    assert {:ok, result} = Runtime.run_task(task, workspace)

    artifacts = %{
      evidence_packets: result.evidence_packets,
      verifier_outputs: result.verifier_outputs
    }

    assert EvaluationHarness.audit_complete?(result.journal, artifacts)

    missing_manifest =
      result.journal
      |> put_in(["runtime_manifest"], %{})
      |> EvaluationHarness.audit_result(artifacts)

    refute missing_manifest["complete"]
    assert "replay_metadata" in missing_manifest["missing"]

    missing_evidence_ref =
      result.journal
      |> Map.put("evidence_refs", [])
      |> EvaluationHarness.audit_result(artifacts)

    refute missing_evidence_ref["complete"]
    assert "evidence_audit" in missing_evidence_ref["missing"]

    missing_verifier_ref =
      result.journal
      |> Map.put("verifier_output_refs", [])
      |> EvaluationHarness.audit_result(artifacts)

    refute missing_verifier_ref["complete"]
    assert "verifier_audit" in missing_verifier_ref["missing"]

    evidence_without_backup =
      result.evidence_packets
      |> List.first()
      |> update_in(["observation"], &Map.delete(&1, "backup_metadata"))

    missing_rollback_metadata =
      EvaluationHarness.audit_result(result.journal, %{
        evidence_packets: [evidence_without_backup],
        verifier_outputs: result.verifier_outputs
      })

    refute missing_rollback_metadata["complete"]
    assert "commit_audit" in missing_rollback_metadata["missing"]
  end

  @tag :fast_unit
  test "verifier rejects simulated observations that mutate source state" do
    {task, workspace} = load_fixture("docops_simulate_patch_001")
    state = StateManager.from_task(task)

    {:ok, step} =
      ExecutionIRCompiler.compile(task, "episode_mutation_violation", "simulate_patch", %{
        "path" => "inputs/spec.md",
        "find" => "First controlled environment: TBD.",
        "replace" => "First controlled environment: Document Ops."
      })

    {:ok, observation} = ActionExecutor.execute(workspace, step)
    mutated_observation = Map.put(observation, "mutated", true)
    evidence = EvidenceBuilder.build(state, step, mutated_observation)
    verifier_output = VerifierRuntime.verify(step, evidence, %{workspace: workspace, task: task})

    assert verifier_output["decision"] == "reject"
    assert "simulated_action_mutated" in verifier_output["violated_constraints"]
  end

  @tag :fast_unit
  test "verifier enforces task action and side-effect allowlists" do
    {task, workspace} = load_fixture("docops_action_not_allowed_001")
    state = StateManager.from_task(task)

    step = %{
      "schema_version" => Vanta.schema_version(),
      "step_id" => "step_episode_allowlist_gate_simulate_patch",
      "episode_id" => "episode_allowlist_gate",
      "parent_step_id" => nil,
      "action_type" => "simulate_patch",
      "action_payload" => %{
        "path" => "inputs/source.md",
        "find" => "First controlled environment: TBD.",
        "replace" => "First controlled environment: Document Ops."
      },
      "expected_effect" => "Simulate a candidate patch.",
      "preconditions" => ["fixture_workspace_exists"],
      "postconditions" => ["source_files_preserved_unless_explicitly_allowed"],
      "dependency_edges" => [],
      "verifier_requirements" => ["side_effect_allowed"],
      "rollback_policy" => "not_applicable",
      "side_effect_class" => "SIMULATED",
      "status" => "ready"
    }

    observation = %{
      "kind" => "simulate_patch",
      "path" => "inputs/source.md",
      "diff" =>
        "-First controlled environment: TBD.\n+First controlled environment: Document Ops.",
      "mutated" => false
    }

    evidence = EvidenceBuilder.build(state, step, observation)
    verifier_output = VerifierRuntime.verify(step, evidence, %{task: task, workspace: workspace})

    assert verifier_output["decision"] == "reject"
    assert "action_not_allowed_by_task" in verifier_output["violated_constraints"]
    assert "side_effect_class_not_allowed_by_task" in verifier_output["violated_constraints"]
  end

  @tag :fast_unit
  test "verifier rejects action side-effect class mismatches" do
    {task, workspace} = load_fixture("docops_simulate_patch_001")
    state = StateManager.from_task(task)
    task = Map.put(task, "side_effect_classes", ["READ_ONLY", "SIMULATED"])

    {:ok, step} =
      ExecutionIRCompiler.compile(task, "episode_side_effect_mismatch", "simulate_patch", %{
        "path" => "inputs/spec.md",
        "find" => "First controlled environment: TBD.",
        "replace" => "First controlled environment: Document Ops."
      })

    {:ok, observation} = ActionExecutor.execute(workspace, step)
    mismatched_step = Map.put(step, "side_effect_class", "READ_ONLY")
    evidence = EvidenceBuilder.build(state, mismatched_step, observation)

    verifier_output =
      VerifierRuntime.verify(mismatched_step, evidence, %{task: task, workspace: workspace})

    assert verifier_output["decision"] == "reject"
    assert "action_side_effect_class_mismatch" in verifier_output["violated_constraints"]
  end

  @tag :fast_unit
  test "verifier rejects workspace path escapes before LLM review" do
    {task, workspace} = load_fixture("docops_path_escape_001")
    state = StateManager.from_task(task)

    {:ok, step} =
      ExecutionIRCompiler.compile(task, "episode_path_escape_gate", "read_file", %{
        "path" => "../outside.md"
      })

    observation = %{
      "kind" => "read_file",
      "path" => "../outside.md",
      "error" => "path escapes fixture workspace: ../outside.md",
      "mutated" => false
    }

    evidence = EvidenceBuilder.build(state, step, observation)
    verifier_output = VerifierRuntime.verify(step, evidence, %{task: task, workspace: workspace})

    assert verifier_output["decision"] == "reject"
    assert "action_execution_failed" in verifier_output["violated_constraints"]
    assert "action_path_escapes_workspace" in verifier_output["violated_constraints"]
    assert "observation_path_escapes_workspace" in verifier_output["violated_constraints"]
    assert "provenance_path_escapes_workspace" in verifier_output["violated_constraints"]
  end

  @tag :fast_unit
  test "baseline direct execution records invalid actions without governance artifacts" do
    {task, workspace} = load_fixture("docops_wrong_diff_001")
    {:ok, action_sequence} = FixtureAcceptance.action_sequence(workspace)

    assert {:ok, result} = BaselineRunner.run_task(task, workspace, action_sequence)
    assert result.arm == :baseline
    assert result.status == "invalid_actions"
    assert result.invalid_actions == 1
    assert result.task_success? == false
    refute Map.has_key?(result, :journal)
    refute Map.has_key?(result, :evidence_packets)
  end

  @tag :fast_unit
  test "openai planner adapter parses mock structured output" do
    {task, workspace} = load_fixture("docops_read_traceability_001")

    client = fn request, env ->
      assert request["text"]["format"]["type"] == "json_schema"
      assert env.model == "test-model"

      {:ok,
       %{
         "output_text" =>
           Jason.encode!(%{
             "actions" => [
               %{
                 "action_type" => "validate_artifact",
                 "action_payload" => %{
                   "path" => "inputs/source.md",
                   "validation" => "traceability_links"
                 }
               }
             ]
           })
       }}
    end

    assert {:ok, action_sequence} =
             OpenAIPlannerAdapter.propose_actions(task, workspace,
               api_key: "test-key",
               model: "test-model",
               client: client
             )

    assert [%{"action_type" => "validate_artifact"}] = action_sequence["actions"]
  end

  @tag :fast_unit
  test "openclaw planner adapter parses mock agent payload text" do
    {task, workspace} = load_fixture("docops_read_traceability_001")

    runner = fn prompt, env ->
      assert String.contains?(prompt, "non-interactive Vanta Experiment 001 planner")
      assert env.model == "openai-codex/gpt-5.4-mini"
      assert String.starts_with?(env.session_id, "vanta-exp001-docops_read_traceability_001-")
      assert String.length(env.session_id) <= 64

      {:ok,
       %{
         "payloads" => [
           %{
             "text" =>
               Jason.encode!(%{
                 "actions" => [
                   %{
                     "action_type" => "validate_artifact",
                     "action_payload" => %{
                       "path" => "inputs/source.md",
                       "validation" => "traceability_links"
                     }
                   }
                 ]
               })
           }
         ]
       }}
    end

    assert {:ok, action_sequence} =
             OpenClawPlannerAdapter.propose_actions(task, workspace,
               wsl_executable: "wsl.exe",
               model: "gpt-5.4-mini",
               runner: runner
             )

    assert [%{"action_type" => "validate_artifact"}] = action_sequence["actions"]
  end

  @tag :fast_unit
  test "openclaw planner adapter uses compact prompts for Lane A overflow fixtures" do
    Enum.each(
      ~w(
        docops_ps1_recovery_audit_gap_complete_refs_001
        docops_ps1_replay_multistep_structured_commit_001
      ),
      fn fixture_id ->
        {task, workspace} = load_fixture(fixture_id)
        {:ok, expected_sequence} = FixtureAcceptance.action_sequence(workspace)

        runner = fn prompt, env ->
          assert env.model == "openai-codex/gpt-5.4-mini"
          assert String.length(env.session_id) <= 64
          assert String.contains?(prompt, "Vanta Lane A compact planner")
          assert String.contains?(prompt, fixture_id)
          assert String.contains?(prompt, "action_hint")
          assert String.contains?(prompt, "recommended_actions")
          assert String.length(prompt) < 5_000
          refute String.contains?(prompt, "Input artifact previews:")
          refute String.contains?(prompt, "\"runtime_manifest\"")

          Enum.each(task["allowed_actions"], fn action_type ->
            assert String.contains?(prompt, action_type)
          end)

          {:ok, %{"payloads" => [%{"text" => Jason.encode!(expected_sequence)}]}}
        end

        assert {:ok, action_sequence} =
                 OpenClawPlannerAdapter.propose_actions(task, workspace,
                   wsl_executable: "wsl.exe",
                   model: "gpt-5.4-mini",
                   runner: runner
                 )

        assert action_sequence == expected_sequence
      end
    )
  end

  @tag :integration
  test "Lane A overflow fixture action sequences produce governance artifacts" do
    Enum.each(
      ~w(
        docops_ps1_recovery_audit_gap_complete_refs_001
        docops_ps1_replay_multistep_structured_commit_001
      ),
      fn fixture_id ->
        {task, workspace} = load_fixture(fixture_id)
        {:ok, action_sequence} = FixtureAcceptance.action_sequence(workspace)

        assert {:ok, result} =
                 Runtime.run_task(task, workspace, action_sequence: action_sequence)

        artifacts = %{
          evidence_packets: result.evidence_packets,
          verifier_outputs: result.verifier_outputs
        }

        audit = EvaluationHarness.audit_result(result.journal, artifacts)

        assert result.task_success?,
               "#{fixture_id}: status=#{result.status}, invalid_actions=#{result.invalid_actions}, observations=#{inspect(result.observations)}"

        assert result.evidence_packets != []
        assert result.verifier_outputs != []
        assert audit["complete"]

        assert {:ok, replay} =
                 ReplayRunner.replay(task, workspace, result.journal, artifacts)

        assert replay.consistent?
      end
    )
  end

  @tag :fast_unit
  test "openclaw planner adapter uses compact rejection prompts for PS1-LA-FIX-007 fixtures" do
    Enum.each(@ps1_fix_007_expected_rejected_fixtures, fn fixture_id ->
      {task, workspace} = load_fixture(fixture_id)
      {:ok, expected_sequence} = FixtureAcceptance.action_sequence(workspace)
      expected_action = expected_sequence["actions"] |> List.first()

      runner = fn prompt, env ->
        assert env.model == "openai-codex/gpt-5.4-mini"
        assert String.length(env.session_id) <= 64
        assert String.contains?(prompt, "Vanta Lane A compact planner")
        assert String.contains?(prompt, fixture_id)
        assert String.contains?(prompt, "rejection_expected")
        assert String.contains?(prompt, "Return action_hint.recommended_actions exactly")
        assert String.contains?(prompt, "do not substitute read_file")
        assert String.contains?(prompt, expected_action["action_type"])

        unless expected_action["action_type"] in task["allowed_actions"] do
          assert String.contains?(prompt, "action type is absent")
          assert String.contains?(prompt, "task_summary.allowed_actions")
        end

        assert String.length(prompt) < 5_000
        refute String.contains?(prompt, "Input artifact previews:")

        {:ok, %{"payloads" => [%{"text" => Jason.encode!(expected_sequence)}]}}
      end

      assert {:ok, action_sequence} =
               OpenClawPlannerAdapter.propose_actions(task, workspace,
                 wsl_executable: "wsl.exe",
                 model: "gpt-5.4-mini",
                 runner: runner
               )

      assert action_sequence == expected_sequence
    end)
  end

  @tag :integration
  test "PS1-LA-FIX-007 expected-rejected fixtures produce complete governance artifacts" do
    Enum.each(@ps1_fix_007_expected_rejected_fixtures, fn fixture_id ->
      {task, workspace} = load_fixture(fixture_id)
      {:ok, action_sequence} = FixtureAcceptance.action_sequence(workspace)

      assert {:ok, action_sequence} =
               Vanta.PlannerAdapter.validate_action_sequence(action_sequence)

      assert {:ok, result} =
               Runtime.run_task(task, workspace, action_sequence: action_sequence)

      artifacts = %{
        evidence_packets: result.evidence_packets,
        verifier_outputs: result.verifier_outputs
      }

      expected_rollback_status = FixtureAcceptance.expected_rollback_status(workspace)

      assert result.status == "rejected"
      assert result.task_success?
      assert result.invalid_actions >= 1
      assert result.journal["commit_status"] == "rejected"

      if expected_rollback_status do
        assert result.rollback_status == expected_rollback_status
        assert result.journal["rollback_status"] == expected_rollback_status
      end

      assert length(result.steps) == length(action_sequence["actions"])
      assert length(result.evidence_packets) == length(result.steps)
      assert length(result.verifier_outputs) == length(result.steps)

      Enum.each(result.steps, fn step ->
        assert step["status"] == "rejected"
        assert :ok = Schema.validate("execution_step", step)
      end)

      Enum.each(result.evidence_packets, fn evidence ->
        assert :ok = Schema.validate("evidence_packet", evidence)
      end)

      Enum.each(result.verifier_outputs, fn verifier_output ->
        assert verifier_output["decision"] == "reject"
        assert verifier_output["violated_constraints"] != []
        assert :ok = Schema.validate("verifier_output", verifier_output)
      end)

      assert :ok = Schema.validate("episode_journal", result.journal)

      assert EvaluationHarness.audit_complete?(result.journal, artifacts),
             "#{fixture_id}: audit=#{inspect(EvaluationHarness.audit_result(result.journal, artifacts))}"

      assert {:ok, replay} = ReplayRunner.replay(task, workspace, result.journal, artifacts)
      assert replay.consistent?
    end)
  end

  @tag :fast_unit
  test "openclaw planner adapter uses compact rejection prompts for PS1-LA-FIX-008 structured fixtures" do
    Enum.each(@ps1_fix_008_expected_rejected_fixtures, fn fixture_id ->
      {task, workspace} = load_fixture(fixture_id)
      {:ok, expected_sequence} = FixtureAcceptance.action_sequence(workspace)
      expected_action = expected_sequence["actions"] |> List.first()
      expected_payload = expected_action["action_payload"]

      runner = fn prompt, env ->
        assert env.model == "openai-codex/gpt-5.4-mini"
        assert String.length(env.session_id) <= 64
        assert String.contains?(prompt, "Vanta Lane A compact planner")
        assert String.contains?(prompt, fixture_id)
        assert String.contains?(prompt, "rejection_expected")
        assert String.contains?(prompt, "Return action_hint.recommended_actions exactly")
        assert String.contains?(prompt, "preserve every action_type and")
        assert String.contains?(prompt, expected_action["action_type"])
        assert String.contains?(prompt, expected_payload["replacement"])

        if Map.has_key?(expected_payload, "fault_injection") do
          assert String.contains?(prompt, expected_payload["fault_injection"])
        end

        assert String.length(prompt) < 5_000
        refute String.contains?(prompt, "Input artifact previews:")

        {:ok, %{"payloads" => [%{"text" => Jason.encode!(expected_sequence)}]}}
      end

      assert {:ok, action_sequence} =
               OpenClawPlannerAdapter.propose_actions(task, workspace,
                 wsl_executable: "wsl.exe",
                 model: "gpt-5.4-mini",
                 runner: runner
               )

      assert action_sequence == expected_sequence
    end)
  end

  @tag :fast_unit
  test "openclaw planner adapter preserves missing-selector rejection fixture action" do
    {task, workspace} = load_fixture("docops_struct_selector_missing_001")
    {:ok, expected_sequence} = FixtureAcceptance.action_sequence(workspace)

    runner = fn prompt, env ->
      assert env.model == "openai-codex/gpt-5.4-mini"
      assert String.length(env.session_id) <= 64
      assert String.contains?(prompt, "Vanta Lane A compact planner")
      assert String.contains?(prompt, "docops_struct_selector_missing_001")
      assert String.contains?(prompt, "rejection_expected")
      assert String.contains?(prompt, "Return action_hint.recommended_actions exactly")
      assert String.contains?(prompt, "\"type\": \"section\"")
      assert String.contains?(prompt, "\"heading\": \"Missing\"")
      refute String.contains?(prompt, "Input artifact previews:")

      {:ok, %{"payloads" => [%{"text" => Jason.encode!(expected_sequence)}]}}
    end

    assert {:ok, action_sequence} =
             OpenClawPlannerAdapter.propose_actions(task, workspace,
               wsl_executable: "wsl.exe",
               model: "gpt-5.4-mini",
               runner: runner
             )

    assert action_sequence == expected_sequence
  end

  @tag :integration
  test "PS1-LA-FIX-008 structured expected-rejected fixtures produce complete governance artifacts" do
    Enum.each(@ps1_fix_008_expected_rejected_fixtures, fn fixture_id ->
      {task, workspace} = load_fixture(fixture_id)
      {:ok, action_sequence} = FixtureAcceptance.action_sequence(workspace)

      assert {:ok, action_sequence} =
               Vanta.PlannerAdapter.validate_action_sequence(action_sequence)

      assert {:ok, result} =
               Runtime.run_task(task, workspace, action_sequence: action_sequence)

      artifacts = %{
        evidence_packets: result.evidence_packets,
        verifier_outputs: result.verifier_outputs
      }

      expected_rollback_status = FixtureAcceptance.expected_rollback_status(workspace)
      expected_labels = FixtureAcceptance.expected_failure_labels(workspace)

      assert result.status == "rejected"
      assert result.task_success?
      assert result.invalid_actions >= 1
      assert result.journal["commit_status"] == "rejected"

      if expected_rollback_status do
        assert result.rollback_status == expected_rollback_status
        assert result.journal["rollback_status"] == expected_rollback_status
      end

      assert length(result.steps) == length(action_sequence["actions"])
      assert length(result.evidence_packets) == length(result.steps)
      assert length(result.verifier_outputs) == length(result.steps)

      Enum.each(result.steps, fn step ->
        assert step["status"] == "rejected"
        assert :ok = Schema.validate("execution_step", step)
      end)

      Enum.each(result.evidence_packets, fn evidence ->
        assert :ok = Schema.validate("evidence_packet", evidence)
      end)

      Enum.each(result.verifier_outputs, fn verifier_output ->
        assert verifier_output["decision"] == "reject"
        assert Enum.all?(expected_labels, &(&1 in verifier_output["violated_constraints"]))
        assert :ok = Schema.validate("verifier_output", verifier_output)
      end)

      assert :ok = Schema.validate("episode_journal", result.journal)

      assert EvaluationHarness.audit_complete?(result.journal, artifacts),
             "#{fixture_id}: audit=#{inspect(EvaluationHarness.audit_result(result.journal, artifacts))}"

      assert {:ok, replay} = ReplayRunner.replay(task, workspace, result.journal, artifacts)
      assert replay.consistent?
    end)
  end

  @tag :fast_unit
  test "openclaw planner adapter uses compact acceptance prompts for PS1-LA-FIX-006 fixtures" do
    Enum.each(@ps1_fix_006_positive_fixtures, fn fixture_id ->
      {task, workspace} = load_fixture(fixture_id)
      {:ok, expected_sequence} = FixtureAcceptance.action_sequence(workspace)
      expected_action = expected_sequence["actions"] |> List.first()

      runner = fn prompt, env ->
        assert env.model == "openai-codex/gpt-5.4-mini"
        assert String.length(env.session_id) <= 64
        assert String.contains?(prompt, "Vanta Lane A compact planner")
        assert String.contains?(prompt, fixture_id)
        assert String.contains?(prompt, "fixture_acceptance_expected")
        assert String.contains?(prompt, "Return action_hint.recommended_actions exactly")
        assert String.contains?(prompt, "Do not add read_file")
        assert String.contains?(prompt, expected_action["action_type"])
        assert String.length(prompt) < 5_000
        refute String.contains?(prompt, "Input artifact previews:")

        {:ok, %{"payloads" => [%{"text" => Jason.encode!(expected_sequence)}]}}
      end

      assert {:ok, action_sequence} =
               OpenClawPlannerAdapter.propose_actions(task, workspace,
                 wsl_executable: "wsl.exe",
                 model: "gpt-5.4-mini",
                 runner: runner
               )

      assert action_sequence == expected_sequence
    end)
  end

  @tag :integration
  test "PS1-LA-FIX-006 positive fixtures produce complete governance artifacts" do
    Enum.each(@ps1_fix_006_positive_fixtures, fn fixture_id ->
      {task, workspace} = load_fixture(fixture_id)
      {:ok, action_sequence} = FixtureAcceptance.action_sequence(workspace)

      assert {:ok, action_sequence} =
               Vanta.PlannerAdapter.validate_action_sequence(action_sequence)

      assert {:ok, result} =
               Runtime.run_task(task, workspace, action_sequence: action_sequence)

      artifacts = %{
        evidence_packets: result.evidence_packets,
        verifier_outputs: result.verifier_outputs
      }

      audit = EvaluationHarness.audit_result(result.journal, artifacts)

      assert result.status == "committed",
             "#{fixture_id}: status=#{result.status}, observations=#{inspect(result.observations)}"

      assert result.task_success?,
             "#{fixture_id}: verifier_outputs=#{inspect(result.verifier_outputs)}"

      assert result.invalid_actions == 0
      assert result.evidence_packets != []
      assert result.verifier_outputs != []
      assert audit["complete"]

      assert {:ok, replay} =
               ReplayRunner.replay(task, workspace, result.journal, artifacts)

      assert replay.consistent?
    end)
  end

  @tag :fast_unit
  test "openclaw planner adapter rejects prompt budget overflow before runner call" do
    {task, workspace} = load_fixture("docops_read_traceability_001")

    runner = fn _prompt, _env -> flunk("runner should not be called after prompt overflow") end

    assert {:error, {:planner_prompt_budget_exceeded, prompt_chars, 10}} =
             OpenClawPlannerAdapter.propose_actions(task, workspace,
               wsl_executable: "wsl.exe",
               model: "gpt-5.4-mini",
               max_prompt_chars: 10,
               runner: runner
             )

    assert prompt_chars > 10
  end

  @tag :fast_unit
  test "openclaw planner adapter rejects response budget overflow before JSON decode" do
    {task, workspace} = load_fixture("docops_read_traceability_001")

    runner = fn _prompt, _env ->
      {:ok, %{"payloads" => [%{"text" => String.duplicate("x", 50)}]}}
    end

    assert {:error, {:planner_response_budget_exceeded, 50, 20}} =
             OpenClawPlannerAdapter.propose_actions(task, workspace,
               wsl_executable: "wsl.exe",
               model: "gpt-5.4-mini",
               max_response_chars: 20,
               runner: runner
             )
  end

  @tag :fast_unit
  test "openclaw planner adapter classifies context overflow text explicitly" do
    {task, workspace} = load_fixture("docops_read_traceability_001")

    runner = fn _prompt, _env ->
      {:ok,
       %{
         "payloads" => [
           %{"text" => "OpenClaw error: maximum context length exceeded for this request."}
         ]
       }}
    end

    assert {:error, {:openclaw_context_overflow, message}} =
             OpenClawPlannerAdapter.propose_actions(task, workspace,
               wsl_executable: "wsl.exe",
               model: "gpt-5.4-mini",
               runner: runner
             )

    assert message =~ "maximum context length exceeded"
  end

  @tag :fast_unit
  test "malformed action sequence is rejected before execution" do
    assert {:error, {:invalid_action_sequence, _errors}} =
             Vanta.PlannerAdapter.validate_action_sequence(%{
               "actions" => [%{"action_type" => "unknown", "action_payload" => %{}}]
             })
  end

  @tag :integration
  test "experiment runner writes compact mock run results" do
    out_dir =
      Path.join(System.tmp_dir!(), "vanta_experiment001_#{System.unique_integer([:positive])}")

    File.rm_rf!(out_dir)

    assert {:ok, run} =
             Experiment001.run(@fixture_root,
               planner: __MODULE__.AcceptancePlanner,
               out_dir: out_dir
             )

    assert run["status"] == "completed"
    assert run["fixture_count"] == fixture_count()
    assert :ok = Schema.validate("experiment_run", run)
    assert File.exists?(Path.join(out_dir, "run.json"))
    assert File.exists?(Path.join(out_dir, "summary.md"))
  end

  defp load_fixture(fixture_id) do
    workspace = Path.join(@fixture_root, fixture_id)
    {Schema.load_json!(Path.join(workspace, "task.json")), workspace}
  end

  defp copy_fixture(fixture_id) do
    source = Path.join(@fixture_root, fixture_id)

    target =
      Path.join(System.tmp_dir!(), "vanta_#{fixture_id}_#{System.unique_integer([:positive])}")

    File.rm_rf!(target)
    File.cp_r!(source, target)
    target
  end

  defp fixture_count do
    @fixture_root
    |> Path.join("*/task.json")
    |> Path.wildcard()
    |> length()
  end

  defmodule AcceptancePlanner do
    def propose_actions(_task, workspace, _opts),
      do: Vanta.FixtureAcceptance.action_sequence(workspace)
  end
end
