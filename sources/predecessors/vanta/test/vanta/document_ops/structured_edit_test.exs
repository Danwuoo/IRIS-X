defmodule Vanta.StructuredEditTest do
  use ExUnit.Case

  alias Vanta.{
    ActionExecutor,
    ExecutionIRCompiler,
    ReplayRunner,
    Runtime,
    Schema,
    StateManager,
    VerifierRuntime
  }

  @fixture_root Path.expand("../../fixtures/document_ops", __DIR__)

  @tag :fast_unit
  test "inspect_document_structure resolves heading and section selectors" do
    {task, workspace} = load_fixture("docops_struct_inspect_001")
    {:ok, sequence} = Vanta.FixtureAcceptance.action_sequence(workspace)
    [action] = sequence["actions"]

    {:ok, step} =
      ExecutionIRCompiler.compile(
        task,
        "episode_struct_inspect",
        action["action_type"],
        action["action_payload"]
      )

    {:ok, observation} = ActionExecutor.execute(workspace, step)

    assert observation["kind"] == "inspect_document_structure"
    assert observation["mutated"] == false
    assert Enum.map(observation["selector_results"], & &1["status"]) == ["resolved", "resolved"]
    assert get_in(observation, ["structure", "headings"]) |> length() == 3
  end

  @tag :fast_unit
  test "contract validation records pass and fail observations without mutation" do
    {pass_task, pass_workspace} = load_fixture("docops_struct_contract_pass_001")
    {:ok, pass_sequence} = Vanta.FixtureAcceptance.action_sequence(pass_workspace)
    [pass_action] = pass_sequence["actions"]

    {:ok, pass_step} =
      ExecutionIRCompiler.compile(
        pass_task,
        "episode_contract_pass",
        pass_action["action_type"],
        pass_action["action_payload"]
      )

    {:ok, pass_observation} = ActionExecutor.execute(pass_workspace, pass_step)
    assert pass_observation["passed"] == true
    assert pass_observation["failures"] == []

    {fail_task, fail_workspace} = load_fixture("docops_struct_contract_fail_001")
    {:ok, fail_sequence} = Vanta.FixtureAcceptance.action_sequence(fail_workspace)
    [fail_action] = fail_sequence["actions"]

    {:ok, fail_step} =
      ExecutionIRCompiler.compile(
        fail_task,
        "episode_contract_fail",
        fail_action["action_type"],
        fail_action["action_payload"]
      )

    {:ok, fail_observation} = ActionExecutor.execute(fail_workspace, fail_step)
    assert fail_observation["passed"] == false
    assert [%{"code" => "required_heading_missing"}] = fail_observation["failures"]
  end

  @tag :fast_unit
  test "structured edit simulation supports line ranges and JSON paths without source mutation" do
    workspace = fixture_path("docops_struct_simulate_md_001")
    source_path = Path.join(workspace, "inputs/notes.md")
    original = File.read!(source_path)
    task = Schema.load_json!(Path.join(workspace, "task.json"))
    {:ok, sequence} = Vanta.FixtureAcceptance.action_sequence(workspace)
    [action] = sequence["actions"]

    {:ok, step} =
      ExecutionIRCompiler.compile(
        task,
        "episode_struct_sim_md",
        action["action_type"],
        action["action_payload"]
      )

    {:ok, observation} = ActionExecutor.execute(workspace, step)
    assert observation["selector_resolution"]["status"] == "resolved"
    assert observation["source_hash_after_simulation"] == observation["before_hash"]
    assert File.read!(source_path) == original

    json_workspace = fixture_path("docops_struct_simulate_json_001")
    json_task = Schema.load_json!(Path.join(json_workspace, "task.json"))
    {:ok, json_sequence} = Vanta.FixtureAcceptance.action_sequence(json_workspace)
    [json_action] = json_sequence["actions"]

    {:ok, json_step} =
      ExecutionIRCompiler.compile(
        json_task,
        "episode_struct_sim_json",
        json_action["action_type"],
        json_action["action_payload"]
      )

    {:ok, json_observation} = ActionExecutor.execute(json_workspace, json_step)
    assert get_in(json_observation, ["selector_resolution", "target", "value"]) == "TBD"
    assert String.contains?(json_observation["candidate_content"], "Document Ops")
    assert json_observation["source_hash_after_simulation"] == json_observation["before_hash"]
  end

  @tag :integration
  test "insert_before and insert_after fixtures execute through the runtime" do
    Enum.each(~w(docops_struct_insert_before_001 docops_struct_insert_after_001), fn fixture_id ->
      {task, workspace} = load_fixture(fixture_id)

      assert {:ok, result} = Runtime.run_task(task, workspace)
      assert result.status == "committed"
      assert result.task_success?

      [observation] = Enum.map(result.evidence_packets, & &1["observation"])
      assert observation["selector_resolution"]["status"] == "resolved"
      assert observation["candidate_content"]
      assert observation["source_hash_after_simulation"] == observation["before_hash"]
    end)
  end

  @tag :fast_unit
  test "reversible structured edit writes backup metadata and rollback restores source" do
    workspace = copy_fixture("docops_struct_apply_reversible_001")
    task = Schema.load_json!(Path.join(workspace, "task.json"))
    source_path = Path.join(workspace, "inputs/glossary.md")
    original = File.read!(source_path)
    {:ok, sequence} = Vanta.FixtureAcceptance.action_sequence(workspace)
    [action] = sequence["actions"]

    {:ok, step} =
      ExecutionIRCompiler.compile(
        task,
        "episode_struct_apply",
        action["action_type"],
        action["action_payload"]
      )

    {:ok, observation} = ActionExecutor.execute(workspace, step)
    metadata = observation["backup_metadata"]

    assert observation["mutated"] == true
    assert metadata["backup_policy"] == "fixture_backup_restore"
    assert File.exists?(Path.join(workspace, metadata["backup_path"]))
    assert File.exists?(Path.join(workspace, metadata["metadata_path"]))
    assert File.read!(source_path) != original

    assert :ok = ActionExecutor.rollback(workspace, metadata)
    assert File.read!(source_path) == original
  end

  @tag :integration
  test "verifier rejects missing selectors, ambiguous selectors, simulation mutation, missing backup metadata, and wrong diffs" do
    expectations = %{
      "docops_struct_selector_missing_001" => "structured_selector_missing",
      "docops_struct_selector_ambiguous_001" => "structured_selector_ambiguous",
      "docops_struct_simulation_mutation_001" => "source_hash_after_simulation_mismatch",
      "docops_struct_missing_backup_metadata_001" => "backup_metadata_missing",
      "docops_struct_wrong_diff_001" => "diff_mismatch"
    }

    Enum.each(expectations, fn {fixture_id, violation} ->
      {task, workspace} = load_fixture(fixture_id)

      assert {:ok, result} = Runtime.run_task(task, workspace)
      assert result.status == "rejected"

      [verifier_output] = result.verifier_outputs
      assert verifier_output["decision"] == "reject"
      assert violation in verifier_output["violated_constraints"]
    end)
  end

  @tag :integration
  test "missing-selector fixture rejects substituted resolvable line ranges" do
    {task, workspace} = load_fixture("docops_struct_selector_missing_001")

    substituted_sequence = %{
      "actions" => [
        %{
          "action_type" => "simulate_structured_edit",
          "action_payload" => %{
            "path" => "inputs/source.md",
            "selector" => %{
              "type" => "line_range",
              "start_line" => 3,
              "end_line" => 3
            },
            "operation" => "replace",
            "replacement" => "Mutated line."
          }
        }
      ]
    }

    assert {:ok, result} =
             Runtime.run_task(task, workspace, action_sequence: substituted_sequence)

    assert result.status == "rejected"
    assert result.task_success?

    [verifier_output] = result.verifier_outputs
    assert verifier_output["decision"] == "reject"
    assert "structured_selector_missing" in verifier_output["violated_constraints"]
  end

  @tag :integration
  test "structured runtime episodes are audit-complete and replay-consistent with artifacts" do
    {task, workspace} = load_fixture("docops_struct_simulate_md_001")

    assert {:ok, result} = Runtime.run_task(task, workspace)

    assert Vanta.EvaluationHarness.audit_complete?(result.journal, %{
             evidence_packets: result.evidence_packets,
             verifier_outputs: result.verifier_outputs
           })

    assert {:ok, replay} =
             ReplayRunner.replay(task, workspace, result.journal, %{
               evidence_packets: result.evidence_packets,
               verifier_outputs: result.verifier_outputs
             })

    assert replay.consistent?
    assert replay.observation_match?
  end

  @tag :fast_unit
  test "structured verifier requests evidence when candidate content is missing" do
    {task, workspace} = load_fixture("docops_struct_simulate_md_001")
    state = StateManager.from_task(task)
    {:ok, sequence} = Vanta.FixtureAcceptance.action_sequence(workspace)
    [action] = sequence["actions"]

    {:ok, step} =
      ExecutionIRCompiler.compile(
        task,
        "episode_struct_missing_candidate",
        action["action_type"],
        action["action_payload"]
      )

    {:ok, observation} = ActionExecutor.execute(workspace, step)

    evidence =
      state
      |> Vanta.EvidenceBuilder.build(step, Map.delete(observation, "candidate_content"))

    verifier_output = VerifierRuntime.verify(step, evidence, %{task: task, workspace: workspace})

    assert verifier_output["decision"] == "reject"
    assert "candidate_content_missing" in verifier_output["violated_constraints"]
  end

  defp load_fixture(fixture_id) do
    workspace = fixture_path(fixture_id)
    {Schema.load_json!(Path.join(workspace, "task.json")), workspace}
  end

  defp fixture_path(fixture_id), do: Path.join(@fixture_root, fixture_id)

  defp copy_fixture(fixture_id) do
    source = fixture_path(fixture_id)

    target =
      Path.join(System.tmp_dir!(), "vanta_#{fixture_id}_#{System.unique_integer([:positive])}")

    File.rm_rf!(target)
    File.cp_r!(source, target)
    target
  end
end
