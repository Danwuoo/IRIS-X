defmodule Vanta.Experiment002Test do
  use ExUnit.Case

  alias Vanta.{Experiment002, FixtureAcceptance, OpenClawVerifierAdapter, Schema}

  @fixture_root Path.expand("../../fixtures/document_ops", __DIR__)

  @tag :fast_unit
  test "openclaw verifier adapter parses schema-valid payload text" do
    review_item = review_item("adapter_valid")

    runner = fn prompt, env ->
      assert String.contains?(prompt, "Experiment 002 verifier")
      assert env.model == "openai-codex/test-model"

      {:ok,
       %{
         "payloads" => [
           %{
             "text" =>
               Jason.encode!(%{
                 "decision" => "accept",
                 "confidence" => 0.8,
                 "validity_score" => 0.9,
                 "risk_score" => 0.1,
                 "violated_constraints" => [],
                 "required_extra_evidence" => []
               })
           }
         ]
       }}
    end

    assert {:ok, verifier_output} =
             OpenClawVerifierAdapter.verify(review_item,
               wsl_executable: "mock-wsl",
               openclaw_dir: "~/openclaw",
               model: "test-model",
               runner: runner
             )

    assert verifier_output["decision"] == "accept"
    assert verifier_output["confidence"] == 0.8
    assert :ok = Schema.validate("verifier_output", verifier_output)
  end

  @tag :fast_unit
  test "openclaw verifier adapter parses JSON fences and normalizes needs_more_evidence" do
    review_item = review_item("adapter_fence")

    runner = fn _prompt, _env ->
      {:ok,
       %{
         "payloads" => [
           %{
             "text" => """
             ```json
             {
               "decision": "needs_more_evidence",
               "confidence": 0.4,
               "validity_score": 0.2,
               "risk_score": 0.7,
               "violated_constraints": [],
               "required_extra_evidence": ["provenance"]
             }
             ```
             """
           }
         ]
       }}
    end

    assert {:ok, verifier_output} =
             OpenClawVerifierAdapter.verify(review_item,
               wsl_executable: "mock-wsl",
               openclaw_dir: "~/openclaw",
               model: "test-model",
               runner: runner
             )

    assert verifier_output["decision"] == "request_evidence"
    assert verifier_output["required_extra_evidence"] == ["provenance"]
    assert :ok = Schema.validate("verifier_output", verifier_output)
  end

  @tag :fast_unit
  test "openclaw verifier adapter normalizes parse failure to abstain" do
    review_item = review_item("adapter_parse_failure")

    runner = fn _prompt, _env ->
      {:ok, %{"payloads" => [%{"text" => "not json"}]}}
    end

    assert {:ok, verifier_output} =
             OpenClawVerifierAdapter.verify(review_item,
               wsl_executable: "mock-wsl",
               openclaw_dir: "~/openclaw",
               model: "test-model",
               runner: runner
             )

    assert verifier_output["decision"] == "abstain"
    assert "schema_valid_verifier_output" in verifier_output["required_extra_evidence"]
    assert :ok = Schema.validate("verifier_output", verifier_output)
  end

  @tag :fast_unit
  test "openclaw verifier adapter generates short automatic session ids" do
    long_review_item =
      review_item(
        "docops_action_not_allowed_001_step_1_structured_evidence_packet_with_long_suffix"
      )

    assert {:ok, env} =
             OpenClawVerifierAdapter.env(
               [wsl_executable: "mock-wsl", openclaw_dir: "~/openclaw", model: "test-model"],
               long_review_item
             )

    assert String.length(env.session_id) <= 64
    assert String.starts_with?(env.session_id, "vexp002-docops-action-not-allowed-")
  end

  @tag :integration
  test "experiment002 runner computes three-arm strict verifier metrics" do
    out_dir =
      Path.join(System.tmp_dir!(), "vanta_experiment002_#{System.unique_integer([:positive])}")

    File.rm_rf!(out_dir)

    assert {:ok, run} =
             Experiment002.run(@fixture_root,
               verifier: __MODULE__.MockVerifier,
               out_dir: out_dir
             )

    assert run["status"] == "completed"
    assert run["fixture_count"] == fixture_count()
    assert :ok = Schema.validate("experiment_run", run)
    assert File.exists?(Path.join(out_dir, "run.json"))
    assert File.exists?(Path.join(out_dir, "summary.md"))

    assert run["metrics"]["final_answer"]["verifier_false_accept_rate"] == 0.0
    assert run["metrics"]["final_answer"]["verifier_false_reject_rate"] == 1.0
    assert run["metrics"]["final_answer"]["abstain_rate"] == 1.0

    assert run["metrics"]["raw_trace"]["verifier_false_accept_rate"] == 1.0
    assert run["metrics"]["raw_trace"]["verifier_false_reject_rate"] == 0.0

    assert run["metrics"]["structured_evidence_packet"]["verifier_false_accept_rate"] == 0.0
    assert run["metrics"]["structured_evidence_packet"]["verifier_false_reject_rate"] == 0.0
    assert run["metrics"]["structured_evidence_packet"]["evidence_sufficiency_score"] == 1.0
  end

  @tag :integration
  test "structured evidence gate rejects invalid fixtures before LLM verifier" do
    assert {:ok, run} =
             Experiment002.run(@fixture_root,
               verifier: __MODULE__.AcceptAllProbeVerifier,
               verifier_opts: [test_pid: self()]
             )

    calls = collect_llm_calls()
    structured_items = arm_results(run, "structured_evidence_packet")
    invalid_structured = Enum.filter(structured_items, &(&1["oracle_valid"] == false))
    valid_structured = Enum.filter(structured_items, &(&1["oracle_valid"] == true))

    assert run["metrics"]["structured_evidence_packet"]["verifier_false_accept_rate"] == 0.0
    assert run["metrics"]["structured_evidence_packet"]["verifier_false_reject_rate"] == 0.0

    assert Enum.all?(invalid_structured, &(&1["llm_invoked"] == false))
    assert Enum.all?(invalid_structured, &(&1["decision"] in ["reject", "request_evidence"]))
    assert Enum.all?(valid_structured, &(&1["llm_invoked"] == true))

    refute {:llm_invoked, "structured_evidence_packet", "docops_action_not_allowed_001"} in calls
    refute {:llm_invoked, "structured_evidence_packet", "docops_path_escape_001"} in calls
    refute {:llm_invoked, "structured_evidence_packet", "docops_wrong_diff_001"} in calls

    assert {:llm_invoked, "structured_evidence_packet", "docops_simulate_patch_001"} in calls

    assert calls
           |> Enum.filter(&match?({:llm_invoked, "structured_evidence_packet", _task_id}, &1))
           |> length() == length(valid_structured)
  end

  @tag :integration
  test "experiment002 review items cover compile rejects, execution rejects, wrong diffs, and reversible evidence" do
    review_items = Experiment002.build_review_items(@fixture_root)

    assert length(review_items) == review_item_count()

    action_not_allowed =
      Enum.find(review_items, &(&1["task_id"] == "docops_action_not_allowed_001"))

    assert action_not_allowed["compile_error"] =~ "action_not_allowed"
    assert action_not_allowed["oracle_label"] == "invalid"
    assert :ok = Schema.validate("evidence_packet", action_not_allowed["evidence_packet"])

    path_escape = Enum.find(review_items, &(&1["task_id"] == "docops_path_escape_001"))
    assert path_escape["observation"]["error"] =~ "path escapes fixture workspace"
    assert path_escape["oracle_label"] == "invalid"

    assert "action_execution_failed" in path_escape["deterministic_verifier_output"][
             "violated_constraints"
           ]

    assert "action_path_escapes_workspace" in path_escape["deterministic_verifier_output"][
             "violated_constraints"
           ]

    wrong_diff = Enum.find(review_items, &(&1["task_id"] == "docops_wrong_diff_001"))
    assert wrong_diff["oracle_label"] == "invalid"
    assert "diff_mismatch" in wrong_diff["deterministic_verifier_output"]["violated_constraints"]

    reversible =
      Enum.find(review_items, fn item ->
        item["task_id"] == "docops_reversible_edit_001" and
          item["action"]["action_type"] == "apply_reversible_patch"
      end)

    assert reversible["oracle_label"] == "valid"
    assert is_map(get_in(reversible, ["evidence_packet", "observation", "backup_metadata"]))

    structured_input = Experiment002.review_input(reversible, "structured_evidence_packet")
    assert structured_input["evidence_sufficiency_label"] == 1.0
    assert is_map(get_in(structured_input, ["verifier_input", "evidence_packet"]))

    assert :ok =
             Schema.validate(
               "evidence_packet",
               get_in(structured_input, ["verifier_input", "evidence_packet"])
             )

    wrong_diff_structured =
      wrong_diff
      |> Experiment002.review_input("structured_evidence_packet")
      |> get_in(["verifier_input", "evidence_packet", "observation"])

    refute Map.has_key?(wrong_diff_structured, "candidate_content")
    refute Map.has_key?(wrong_diff_structured, "content")
  end

  defp arm_results(run, arm) do
    run["tasks"]
    |> Enum.flat_map(fn task -> task["arms"][arm] end)
  end

  defp collect_llm_calls(acc \\ []) do
    receive do
      {:llm_invoked, _arm, _task_id} = call -> collect_llm_calls([call | acc])
    after
      0 -> Enum.reverse(acc)
    end
  end

  defp review_item(id) do
    %{
      "review_item_id" => id,
      "episode_id" => "episode_#{id}",
      "step_id" => "step_#{id}",
      "evidence_refs" => [],
      "oracle_label" => "valid",
      "oracle_valid" => true,
      "evidence_sufficiency_label" => 0.0,
      "verifier_input" => %{"summary" => "mock"}
    }
  end

  defp fixture_count do
    fixture_workspaces()
    |> length()
  end

  defp review_item_count do
    fixture_workspaces()
    |> Enum.map(fn workspace ->
      {:ok, action_sequence} = FixtureAcceptance.action_sequence(workspace)
      length(action_sequence["actions"])
    end)
    |> Enum.sum()
  end

  defp fixture_workspaces do
    @fixture_root
    |> Path.join("*/task.json")
    |> Path.wildcard()
    |> Enum.sort()
    |> Enum.map(&Path.dirname/1)
  end

  defmodule AcceptAllProbeVerifier do
    def env(_opts), do: {:ok, %{model: "mock"}}
    def verifier_id(_opts), do: "accept_all_probe_verifier"

    def verify(review_input, opts) do
      send(Keyword.fetch!(opts, :test_pid), {
        :llm_invoked,
        review_input["arm"],
        review_input["task_id"]
      })

      {:ok, output(review_input)}
    end

    defp output(review_input) do
      %{
        "schema_version" => Vanta.schema_version(),
        "verifier_output_id" => "accept_all_#{review_input["review_item_id"]}",
        "episode_id" => review_input["episode_id"],
        "step_id" => review_input["step_id"],
        "evidence_refs" => review_input["evidence_refs"],
        "decision" => "accept",
        "verification_scope" => [
          "preconditions",
          "postconditions",
          "evidence_sufficiency",
          "policy_constraints",
          "side_effect_safety",
          "state_consistency"
        ],
        "validity_score" => 1.0,
        "confidence" => 1.0,
        "calibration_state" => %{"method" => "accept_all_probe"},
        "disagreement" => %{},
        "risk_score" => 0.1,
        "violated_constraints" => [],
        "required_extra_evidence" => [],
        "failure_logits" => %{},
        "credit_hints" => %{}
      }
    end
  end

  defmodule MockVerifier do
    def env(_opts), do: {:ok, %{model: "mock"}}
    def verifier_id(_opts), do: "mock_llm_verifier"

    def verify(%{"arm" => "final_answer"} = review_input, _opts) do
      {:ok, output(review_input, "abstain", 0.0)}
    end

    def verify(%{"arm" => "raw_trace"} = review_input, _opts) do
      {:ok, output(review_input, "accept", 1.0)}
    end

    def verify(
          %{"arm" => "structured_evidence_packet", "oracle_valid" => true} = review_input,
          _opts
        ) do
      {:ok, output(review_input, "accept", 1.0)}
    end

    def verify(%{"arm" => "structured_evidence_packet"} = review_input, _opts) do
      {:ok, output(review_input, "reject", 1.0)}
    end

    defp output(review_input, decision, confidence) do
      %{
        "schema_version" => Vanta.schema_version(),
        "verifier_output_id" => "mock_#{review_input["review_item_id"]}",
        "episode_id" => review_input["episode_id"],
        "step_id" => review_input["step_id"],
        "evidence_refs" => review_input["evidence_refs"],
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
        "confidence" => confidence,
        "calibration_state" => %{"method" => "mock"},
        "disagreement" => %{},
        "risk_score" => if(decision == "accept", do: 0.1, else: 0.9),
        "violated_constraints" => [],
        "required_extra_evidence" => [],
        "failure_logits" => %{},
        "credit_hints" => %{}
      }
    end
  end
end
