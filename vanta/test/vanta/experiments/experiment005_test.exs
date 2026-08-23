defmodule Vanta.Experiment005Test do
  use ExUnit.Case

  alias Vanta.{
    Experiment005,
    OpenClawContextPlannerAdapter,
    RawTraceContextBuilder,
    Schema,
    WorkingSetCompiler
  }

  @fixture_root Path.expand("../../fixtures/document_ops", __DIR__)
  @phase5_fixtures ~w(
    docops_ws_evidence_packet_001
    docops_ws_irrelevant_context_001
    docops_ws_omission_trap_001
    docops_ws_recovery_context_001
    docops_ws_traceability_long_001
  )

  @tag :fast_unit
  test "working set compiler emits schema-valid required-first artifacts" do
    {input, workspace} = context_input("docops_ws_traceability_long_001")

    assert {:ok, result} = WorkingSetCompiler.compile(input, workspace: workspace)

    working_set = result.working_set
    assert :ok = Schema.validate("working_set", working_set)
    assert working_set["active_goal_ref"] == "task:docops_ws_traceability_long_001"
    assert working_set["canonical_state_ref"] == "state:traceability_long"
    assert working_set["constraint_refs"] == ["constraint:read_only"]
    assert working_set["token_budget"]["budget_adhered"] == true
    assert working_set["provenance"]["included_refs"] != []
    assert Enum.all?(working_set["provenance"]["included_refs"], &present_provenance?/1)

    assert Enum.any?(
             working_set["omitted_context_notes"],
             &String.contains?(&1, "artifact:noise")
           )
  end

  @tag :fast_unit
  test "working set compiler records budget overflow as omitted context" do
    {input, workspace} = context_input("docops_ws_evidence_packet_001")
    input = put_in(input, ["budget", "max_context_chars"], 20)

    assert {:ok, result} = WorkingSetCompiler.compile(input, workspace: workspace)
    assert result.working_set["token_budget"]["budget_adhered"] == true
    assert result.working_set["omitted_context_notes"] != []
  end

  @tag :fast_unit
  test "working set compiler rejects raw logs, full memory dumps, and memory writes" do
    input = %{
      "task_id" => "bad_refs",
      "active_goal_ref" => "task:bad_refs",
      "budget" => %{"max_context_chars" => 1000},
      "required_refs" => [],
      "candidate_refs" => [
        %{
          "ref_id" => "raw:tool_log",
          "kind" => "raw_tool_log",
          "role" => "forbidden",
          "required" => false,
          "source" => "fixture",
          "path" => "logs/raw.txt",
          "content" => "raw log dump"
        },
        %{
          "ref_id" => "memory:dump",
          "kind" => "full_memory_dump",
          "role" => "forbidden",
          "required" => false,
          "source" => "fixture",
          "path" => "memory/full.json",
          "content" => "full memory dump"
        },
        %{
          "ref_id" => "memory:write",
          "kind" => "memory_write",
          "role" => "forbidden",
          "required" => false,
          "source" => "fixture",
          "path" => "memory/write.json",
          "content" => "memory write"
        }
      ]
    }

    assert {:error, {:disallowed_refs, refs}} = WorkingSetCompiler.compile(input)
    assert refs == ["memory:dump", "memory:write", "raw:tool_log"]
  end

  @tag :fast_unit
  test "raw trace baseline truncates before late required refs" do
    {input, workspace} = context_input("docops_ws_omission_trap_001")
    artifact = RawTraceContextBuilder.build(input, workspace: workspace)

    included_ids = Enum.map(artifact["included_refs"], & &1["ref_id"])
    dropped_ids = Enum.map(artifact["dropped_refs"], & &1["ref_id"])

    refute "artifact:late_source" in included_ids
    assert "artifact:late_source" in dropped_ids
    assert artifact["budget_adhered"] == true
  end

  @tag :fast_unit
  test "openclaw context planner parses JSON fences and rejects malformed output" do
    task = task("docops_ws_irrelevant_context_001")
    context_artifact = %{"arm" => "raw_trace_bounded", "context_text" => "path: inputs/source.md"}

    fenced_runner = fn prompt, env ->
      assert String.contains?(prompt, "Experiment 005 context planner")
      assert env.model == "openai-codex/test-model"

      {:ok,
       %{
         "payloads" => [
           %{
             "text" => """
             ```json
             {"actions":[{"action_type":"validate_artifact","action_payload":{"path":"inputs/source.md"}}]}
             ```
             """
           }
         ]
       }}
    end

    assert {:ok, result} =
             OpenClawContextPlannerAdapter.plan(task, context_artifact,
               wsl_executable: "mock-wsl",
               openclaw_dir: "~/openclaw",
               model: "test-model",
               runner: fenced_runner
             )

    assert [%{"action_type" => "validate_artifact"}] = result.action_sequence["actions"]
    assert result.budget_usage["model_call_count"] == 1

    malformed_runner = fn _prompt, _env ->
      {:ok, %{"payloads" => [%{"text" => "not json"}]}}
    end

    assert {:error, {:invalid_openclaw_context_action_json, _message, _text}} =
             OpenClawContextPlannerAdapter.plan(task, context_artifact,
               wsl_executable: "mock-wsl",
               openclaw_dir: "~/openclaw",
               model: "test-model",
               runner: malformed_runner
             )
  end

  @tag :integration
  test "experiment005 mock run emits working-set metrics and gate result" do
    out_dir =
      Path.join(System.tmp_dir!(), "vanta_experiment005_#{System.unique_integer([:positive])}")

    File.rm_rf!(out_dir)

    assert {:ok, run} =
             Experiment005.run(@fixture_root,
               planner_adapter: __MODULE__.MockContextPlanner,
               out_dir: out_dir
             )

    assert run["status"] == "completed"
    assert run["fixture_count"] == length(@phase5_fixtures)
    assert :ok = Schema.validate("experiment_run", run)
    assert File.exists?(Path.join(out_dir, "run.json"))
    assert File.exists?(Path.join(out_dir, "summary.md"))

    baseline = run["metrics"]["baseline"]
    treatment = run["metrics"]["treatment"]

    assert treatment["working_set_budget_adherence"] == 1.0
    assert treatment["working_set_provenance_completeness"] == 1.0
    assert treatment["context_omission_error_rate"] < baseline["context_omission_error_rate"]
    assert treatment["working_set_relevance_score"] > baseline["working_set_relevance_score"]
    assert treatment["long_task_stability"] >= baseline["long_task_stability"]
    assert treatment["unsupported_commits"] == 0
    assert treatment["memory_writes"] == 0
    assert run["metrics"]["compute_matching"]["budget_matched"] == true
    assert run["metrics"]["gate"]["local_smoke_pass"] == true

    assert Enum.all?(run["tasks"], fn task ->
             Schema.validate("working_set", task["treatment"]["context"]["working_set"]) == :ok
           end)
  end

  defp context_input(fixture_id) do
    workspace = Path.join(@fixture_root, fixture_id)
    metadata = Schema.load_json!(Path.join(workspace, "expected/working_set_acceptance.json"))
    task = Schema.load_json!(Path.join(workspace, "task.json"))

    {
      metadata
      |> Map.put("task_id", task["task_id"])
      |> Map.put_new("active_goal_ref", "task:#{task["task_id"]}"),
      workspace
    }
  end

  defp task(fixture_id) do
    @fixture_root
    |> Path.join(fixture_id)
    |> Path.join("task.json")
    |> Schema.load_json!()
  end

  defp present_provenance?(ref) do
    is_binary(ref["ref_id"]) and is_binary(ref["source"]) and is_binary(ref["path"]) and
      is_binary(ref["content_hash"])
  end

  defmodule MockContextPlanner do
    def env(_opts), do: {:ok, %{model: "mock"}}
    def planner_id(_opts), do: "openclaw_agent_local/mock"

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
          %{
            "action_type" => "validate_artifact",
            "action_payload" => %{"path" => path}
          }
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
