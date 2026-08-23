defmodule Vanta.Experiment002 do
  @moduledoc """
  Experiment 002 runner for Evidence Packet / Verifier LLM comparison.

  This experiment evaluates LLM verifier decisions across three input arms:
  final-answer summary, raw trace, and structured Evidence Packet. Fixture
  acceptance recipes provide oracle labels.
  """

  alias Vanta.{
    ActionExecutor,
    CommitController,
    EvidenceBuilder,
    ExecutionIRCompiler,
    FixtureAcceptance,
    OpenClawVerifierAdapter,
    Schema,
    StateManager,
    VerifierRuntime
  }

  @experiment_id "experiment_002_evidence_verifier"
  @arms ~w(final_answer raw_trace structured_evidence_packet)

  def run(fixture_root, opts \\ []) do
    out_dir = Keyword.get(opts, :out_dir)
    verifier = Keyword.get(opts, :verifier, OpenClawVerifierAdapter)
    verifier_opts = Keyword.get(opts, :verifier_opts, [])

    with :ok <- ensure_verifier_ready(verifier, verifier_opts) do
      review_items = build_review_items(fixture_root)

      arm_results =
        review_items
        |> Enum.flat_map(fn review_item ->
          Enum.map(@arms, fn arm ->
            review_item
            |> review_input(arm)
            |> verify_item(verifier, verifier_opts)
          end)
        end)

      run = %{
        "schema_version" => Vanta.schema_version(),
        "experiment_id" => @experiment_id,
        "status" => run_status(arm_results),
        "baseline" => verifier_id(verifier, verifier_opts) <> "_final_answer_and_raw_trace",
        "treatment" => verifier_id(verifier, verifier_opts) <> "_structured_evidence_packet",
        "fixture_count" => fixture_count(review_items),
        "tasks" => task_results(review_items, arm_results),
        "metrics" => arm_metrics(arm_results)
      }

      run = Schema.validate!("experiment_run", run)

      if out_dir do
        write_results!(out_dir, run)
      end

      {:ok, run}
    end
  end

  def build_review_items(fixture_root) do
    fixture_root
    |> Path.join("*/task.json")
    |> Path.wildcard()
    |> Enum.sort()
    |> Enum.flat_map(&build_fixture_review_items/1)
  end

  def review_input(review_item, arm) when arm in @arms do
    base = %{
      "schema_version" => Vanta.schema_version(),
      "experiment_id" => @experiment_id,
      "arm" => arm,
      "review_item_id" => "#{review_item["review_item_id"]}_#{arm}",
      "base_review_item_id" => review_item["review_item_id"],
      "task_id" => review_item["task_id"],
      "episode_id" => review_item["episode_id"],
      "step_id" => review_item["step_id"],
      "evidence_refs" => review_item["evidence_refs"],
      "oracle_label" => review_item["oracle_label"],
      "oracle_valid" => review_item["oracle_valid"],
      "evidence_sufficiency_label" => evidence_sufficiency_label(review_item, arm),
      "deterministic_verifier_output" => review_item["deterministic_verifier_output"],
      "deterministic_gate_applied" => arm == "structured_evidence_packet"
    }

    Map.put(base, "verifier_input", verifier_payload(review_item, arm))
  end

  defp ensure_verifier_ready(OpenClawVerifierAdapter, opts) do
    case OpenClawVerifierAdapter.env(opts) do
      {:ok, _env} -> :ok
      {:error, reason} -> {:error, {:llm_verifier_not_configured, reason}}
    end
  end

  defp ensure_verifier_ready(verifier, opts) do
    cond do
      function_exported?(verifier, :env, 1) ->
        case verifier.env(opts) do
          {:ok, _env} -> :ok
          {:error, reason} -> {:error, {:llm_verifier_not_configured, reason}}
          _other -> :ok
        end

      true ->
        :ok
    end
  end

  defp build_fixture_review_items(task_path) do
    source_workspace = Path.dirname(task_path)
    workspace = prepare_workspace(source_workspace)
    task = Schema.load_json!(Path.join(workspace, "task.json"))
    {:ok, action_sequence} = FixtureAcceptance.action_sequence(workspace)
    initial_state = StateManager.from_task(task)

    {_state, review_items} =
      action_sequence["actions"]
      |> Enum.with_index(1)
      |> Enum.reduce({initial_state, []}, fn {action, index}, {state, items} ->
        {next_state, review_item} =
          build_action_review_item(task, workspace, state, action, index)

        {next_state, items ++ [review_item]}
      end)

    review_items
  end

  defp build_action_review_item(task, workspace, state, action, index) do
    task_id = task["task_id"]
    episode_id = "episode_exp002_#{task_id}_#{index}"
    action_type = action["action_type"]
    payload = action["action_payload"] || %{}

    case ExecutionIRCompiler.compile(task, episode_id, action_type, payload) do
      {:ok, step} ->
        review_from_compiled_step(task, workspace, state, action, step, index)

      {:error, reason} ->
        step_id = "step_#{episode_id}_#{action_type}_compile_rejected"
        evidence = compile_error_evidence(task, state, action, episode_id, step_id, reason)

        review_item =
          base_review_item(task, workspace, index, episode_id, step_id, action)
          |> Map.merge(%{
            "compiled_step" => nil,
            "compile_error" => inspect(reason),
            "observation" => evidence["observation"],
            "evidence_packet" => evidence,
            "deterministic_verifier_output" =>
              oracle_reject_output(episode_id, step_id, evidence),
            "oracle_valid" => false,
            "oracle_label" => "invalid",
            "evidence_refs" => [evidence["evidence_id"]],
            "final_result" => %{
              "status" => "rejected",
              "summary" => "Execution IR compilation rejected the proposed action."
            }
          })

        {state, review_item}
    end
  end

  defp review_from_compiled_step(task, workspace, state, action, step, index) do
    episode_id = step["episode_id"]
    step_id = step["step_id"]

    {observation, evidence, deterministic_output} =
      case safe_execute(workspace, step) do
        {:ok, observation} ->
          evidence = EvidenceBuilder.build(state, step, observation)

          deterministic_output =
            VerifierRuntime.verify(step, evidence, %{task: task, workspace: workspace})

          {observation, evidence, deterministic_output}

        {:error, reason} ->
          observation = failure_observation(step, reason)
          evidence = EvidenceBuilder.build(state, step, observation)

          deterministic_output =
            VerifierRuntime.verify(step, evidence, %{task: task, workspace: workspace})

          {observation, evidence, deterministic_output}
      end

    oracle_valid? = deterministic_output["decision"] == "accept"
    next_state = commit_state_if_valid(state, step, evidence, deterministic_output)

    review_item =
      base_review_item(task, workspace, index, episode_id, step_id, action)
      |> Map.merge(%{
        "compiled_step" => step,
        "compile_error" => nil,
        "observation" => observation,
        "evidence_packet" => evidence,
        "deterministic_verifier_output" => deterministic_output,
        "oracle_valid" => oracle_valid?,
        "oracle_label" => if(oracle_valid?, do: "valid", else: "invalid"),
        "evidence_refs" => [evidence["evidence_id"]],
        "final_result" => final_result_summary(oracle_valid?, deterministic_output, observation)
      })

    {next_state, review_item}
  end

  defp base_review_item(task, workspace, index, episode_id, step_id, action) do
    %{
      "review_item_id" => "#{task["task_id"]}_step_#{index}",
      "schema_version" => Vanta.schema_version(),
      "task_id" => task["task_id"],
      "episode_id" => episode_id,
      "step_id" => step_id,
      "action_index" => index,
      "task" => public_task_fields(task),
      "expected_runtime_status" => FixtureAcceptance.expected_runtime_status(workspace),
      "action" => action
    }
  end

  defp verifier_payload(review_item, "final_answer") do
    %{
      "task" => review_item["task"],
      "expected_runtime_status" => review_item["expected_runtime_status"],
      "final_result" => review_item["final_result"]
    }
  end

  defp verifier_payload(review_item, "raw_trace") do
    %{
      "task" => review_item["task"],
      "expected_runtime_status" => review_item["expected_runtime_status"],
      "action_proposal" => review_item["action"],
      "compiled_step" => review_item["compiled_step"],
      "compile_error" => review_item["compile_error"],
      "raw_observation_trace" => review_item["observation"],
      "final_result" => review_item["final_result"]
    }
  end

  defp verifier_payload(review_item, "structured_evidence_packet") do
    %{
      "expected_runtime_status" => review_item["expected_runtime_status"],
      "task_constraints" => compact_task_constraints(review_item["task"]),
      "action_proposal" => compact_action(review_item["action"]),
      "normalized_step" => compact_step(review_item["compiled_step"]),
      "compile_error" => review_item["compile_error"],
      "evidence_packet" => compact_evidence_packet(review_item["evidence_packet"]),
      "deterministic_gate_reference" => %{
        "decision" => review_item["deterministic_verifier_output"]["decision"],
        "violated_constraints" =>
          review_item["deterministic_verifier_output"]["violated_constraints"],
        "required_extra_evidence" =>
          review_item["deterministic_verifier_output"]["required_extra_evidence"],
        "verification_scope" => review_item["deterministic_verifier_output"]["verification_scope"]
      }
    }
  end

  defp compact_task_constraints(task) do
    %{
      "prompt" => task["prompt"],
      "allowed_actions" => task["allowed_actions"],
      "side_effect_classes" => task["side_effect_classes"],
      "success_criteria" => task["success_criteria"],
      "failure_criteria" => task["failure_criteria"]
    }
  end

  defp compact_action(nil), do: nil

  defp compact_action(action) do
    %{
      "action_type" => action["action_type"],
      "action_payload" => compact_payload(action["action_payload"] || %{})
    }
  end

  defp compact_step(nil), do: nil

  defp compact_step(step) do
    Map.take(step, [
      "schema_version",
      "episode_id",
      "step_id",
      "action_type",
      "action_payload",
      "side_effect_class",
      "preconditions",
      "postconditions",
      "rollback_policy",
      "verifier_requirements",
      "status"
    ])
    |> Map.update("action_payload", %{}, &compact_payload/1)
  end

  defp compact_payload(payload) when is_map(payload) do
    Map.drop(payload, ["candidate_content"])
  end

  defp compact_payload(payload), do: payload

  defp compact_evidence_packet(evidence) do
    evidence
    |> Map.take([
      "schema_version",
      "evidence_id",
      "episode_id",
      "step_id",
      "pre_state_hash",
      "pre_state_summary",
      "action_ref",
      "post_state_summary",
      "post_state_hash",
      "confidence",
      "violated_constraints",
      "provenance",
      "runtime_context"
    ])
    |> Map.put("observation", compact_observation(evidence["observation"]))
    |> Map.put("verifier_result", Map.get(evidence, "verifier_result", %{}))
    |> Map.put("disagreement", Map.get(evidence, "disagreement", %{}))
    |> Map.put("failure_logits", Map.get(evidence, "failure_logits", %{}))
    |> Map.put("credit_hints", Map.get(evidence, "credit_hints", %{}))
  end

  defp compact_observation(observation) when is_map(observation) do
    Map.drop(observation, ["content", "candidate_content"])
  end

  defp compact_observation(observation), do: observation

  defp verify_item(
         %{"arm" => "structured_evidence_packet"} = review_input,
         verifier,
         verifier_opts
       ) do
    deterministic_output = review_input["deterministic_verifier_output"]

    if deterministic_hard_stop?(deterministic_output) do
      review_input
      |> Map.put("llm_invoked", false)
      |> item_result(deterministic_output)
    else
      review_input
      |> Map.put("llm_invoked", true)
      |> call_llm_verifier(verifier, verifier_opts)
    end
  end

  defp verify_item(review_input, verifier, verifier_opts) do
    review_input
    |> Map.put("llm_invoked", true)
    |> call_llm_verifier(verifier, verifier_opts)
  end

  defp call_llm_verifier(review_input, verifier, verifier_opts) do
    case verifier.verify(review_input, verifier_opts) do
      {:ok, verifier_output} ->
        item_result(review_input, verifier_output)

      {:error, reason} ->
        review_input
        |> Map.put("verifier_error", inspect(reason))
        |> item_result(error_output(review_input, reason))
        |> Map.put("verifier_error", inspect(reason))
    end
  end

  defp deterministic_hard_stop?(%{"decision" => decision})
       when decision in ["reject", "request_evidence"],
       do: true

  defp deterministic_hard_stop?(_deterministic_output), do: false

  defp item_result(review_input, verifier_output) do
    decision = verifier_output["decision"]
    oracle_valid? = review_input["oracle_valid"]
    correct? = strict_correct?(oracle_valid?, decision)
    deterministic_output = review_input["deterministic_verifier_output"] || %{}

    %{
      "review_item_id" => review_input["review_item_id"],
      "base_review_item_id" => review_input["base_review_item_id"],
      "task_id" => review_input["task_id"],
      "episode_id" => review_input["episode_id"],
      "step_id" => review_input["step_id"],
      "arm" => review_input["arm"],
      "oracle_label" => review_input["oracle_label"],
      "oracle_valid" => oracle_valid?,
      "decision" => decision,
      "confidence" => verifier_output["confidence"],
      "correct" => correct?,
      "llm_invoked" => Map.get(review_input, "llm_invoked", true),
      "deterministic_gate_applied" => review_input["deterministic_gate_applied"],
      "deterministic_gate_decision" => deterministic_output["decision"],
      "deterministic_gate_violations" => deterministic_output["violated_constraints"] || [],
      "deterministic_gate_required_extra_evidence" =>
        deterministic_output["required_extra_evidence"] || [],
      "false_accept" => oracle_valid? == false and decision == "accept",
      "false_reject" => oracle_valid? == true and decision != "accept",
      "evidence_sufficiency_label" => review_input["evidence_sufficiency_label"],
      "required_extra_evidence" => verifier_output["required_extra_evidence"],
      "violated_constraints" => verifier_output["violated_constraints"],
      "verifier_output" => verifier_output,
      "verifier_input" => review_input["verifier_input"]
    }
  end

  defp strict_correct?(true, "accept"), do: true
  defp strict_correct?(true, _decision), do: false
  defp strict_correct?(false, "accept"), do: false
  defp strict_correct?(false, _decision), do: true

  defp error_output(review_input, reason) do
    verifier_output = %{
      "schema_version" => Vanta.schema_version(),
      "verifier_output_id" => "llm_verifier_#{review_input["review_item_id"]}_error",
      "episode_id" => review_input["episode_id"],
      "step_id" => review_input["step_id"],
      "evidence_refs" => review_input["evidence_refs"] || [],
      "decision" => "abstain",
      "verification_scope" => [
        "preconditions",
        "postconditions",
        "evidence_sufficiency",
        "policy_constraints",
        "side_effect_safety",
        "state_consistency"
      ],
      "validity_score" => 0.0,
      "confidence" => 0.0,
      "calibration_state" => %{"method" => "experiment002_adapter_error"},
      "disagreement" => %{},
      "risk_score" => 1.0,
      "violated_constraints" => [],
      "required_extra_evidence" => ["llm_verifier_response"],
      "failure_logits" => %{},
      "credit_hints" => %{"adapter_error" => inspect(reason)}
    }

    Schema.validate!("verifier_output", verifier_output)
  end

  defp arm_metrics(results) do
    Map.new(@arms, fn arm ->
      arm_results = Enum.filter(results, &(&1["arm"] == arm))
      {arm, metrics(arm_results)}
    end)
  end

  defp metrics(results) do
    total = length(results)
    invalid = Enum.filter(results, &(&1["oracle_valid"] == false))
    valid = Enum.filter(results, &(&1["oracle_valid"] == true))
    false_accepts = Enum.count(results, & &1["false_accept"])
    false_rejects = Enum.count(results, & &1["false_reject"])
    requests = Enum.count(results, &(&1["decision"] == "request_evidence"))
    abstains = Enum.count(results, &(&1["decision"] == "abstain"))

    %{
      "review_item_count" => total,
      "valid_item_count" => length(valid),
      "invalid_item_count" => length(invalid),
      "verifier_false_accept_rate" => safe_div(false_accepts, length(invalid)),
      "verifier_false_reject_rate" => safe_div(false_rejects, length(valid)),
      "evidence_sufficiency_score" => mean(Enum.map(results, & &1["evidence_sufficiency_label"])),
      "verifier_brier_score" => verifier_brier_score(results),
      "request_evidence_rate" => safe_div(requests, total),
      "abstain_rate" => safe_div(abstains, total)
    }
  end

  defp verifier_brier_score(results) do
    results
    |> Enum.map(fn result ->
      correctness = if result["correct"], do: 1.0, else: 0.0
      confidence = result["confidence"] || 0.0
      :math.pow(confidence - correctness, 2)
    end)
    |> mean()
  end

  defp task_results(review_items, arm_results) do
    review_items
    |> Enum.group_by(& &1["task_id"])
    |> Enum.map(fn {task_id, items} ->
      %{
        "task_id" => task_id,
        "review_items" =>
          Enum.map(items, fn item ->
            %{
              "review_item_id" => item["review_item_id"],
              "step_id" => item["step_id"],
              "oracle_label" => item["oracle_label"],
              "evidence_refs" => item["evidence_refs"]
            }
          end),
        "arms" =>
          arm_results
          |> Enum.filter(&(&1["task_id"] == task_id))
          |> Enum.group_by(& &1["arm"])
      }
    end)
    |> Enum.sort_by(& &1["task_id"])
  end

  defp run_status(results) do
    if Enum.any?(results, &Map.has_key?(&1, "verifier_error")) do
      "partial"
    else
      "completed"
    end
  end

  defp fixture_count(review_items) do
    review_items
    |> Enum.map(& &1["task_id"])
    |> Enum.uniq()
    |> length()
  end

  defp verifier_id(verifier, opts) do
    if function_exported?(verifier, :verifier_id, 1) do
      verifier.verifier_id(opts)
    else
      "llm_verifier"
    end
  end

  defp evidence_sufficiency_label(review_item, "structured_evidence_packet") do
    if evidence_packet_sufficient?(review_item["evidence_packet"]) do
      1.0
    else
      0.0
    end
  end

  defp evidence_sufficiency_label(_review_item, _arm), do: 0.0

  defp evidence_packet_sufficient?(evidence) do
    Schema.validate("evidence_packet", evidence) == :ok and
      get_in(evidence, ["provenance", "source"]) in [
        "fixture_workspace",
        "fixture_acceptance_recipe"
      ] and
      is_map(evidence["runtime_context"])
  end

  defp compile_error_evidence(task, state, action, episode_id, step_id, reason) do
    evidence = %{
      "schema_version" => Vanta.schema_version(),
      "evidence_id" => "evidence_#{step_id}",
      "episode_id" => episode_id,
      "step_id" => step_id,
      "pre_state_hash" => state["state_hash"],
      "pre_state_summary" => state["task_intent"],
      "action_ref" => step_id,
      "observation" => %{
        "kind" => "precondition_error",
        "action_type" => action["action_type"],
        "action_payload" => action["action_payload"] || %{},
        "error" => inspect(reason),
        "mutated" => false
      },
      "post_state_summary" => state["task_intent"],
      "post_state_hash" => state["state_hash"],
      "verifier_result" => %{},
      "confidence" => 1.0,
      "disagreement" => %{},
      "violated_constraints" => ["execution_ir_compile_rejected"],
      "failure_logits" => %{},
      "credit_hints" => %{"failure_class" => "F_PROC"},
      "provenance" => %{
        "source" => "fixture_acceptance_recipe",
        "task_id" => task["task_id"],
        "paths" => []
      },
      "runtime_context" => %{
        "runtime" => "vanta_experiment002",
        "schema_version" => Vanta.schema_version(),
        "side_effect_class" => "precondition_rejected"
      }
    }

    Schema.validate!("evidence_packet", evidence)
  end

  defp oracle_reject_output(episode_id, step_id, evidence) do
    verifier_output = %{
      "schema_version" => Vanta.schema_version(),
      "verifier_output_id" => "oracle_verifier_#{step_id}",
      "episode_id" => episode_id,
      "step_id" => step_id,
      "evidence_refs" => [evidence["evidence_id"]],
      "decision" => "reject",
      "verification_scope" => ["preconditions", "policy_constraints", "evidence_sufficiency"],
      "validity_score" => 0.0,
      "confidence" => 1.0,
      "calibration_state" => %{"method" => "fixture_oracle"},
      "disagreement" => %{},
      "risk_score" => 1.0,
      "violated_constraints" => ["execution_ir_compile_rejected"],
      "required_extra_evidence" => [],
      "failure_logits" => %{},
      "credit_hints" => %{"failure_class" => "F_PROC"}
    }

    Schema.validate!("verifier_output", verifier_output)
  end

  defp final_result_summary(true, verifier_output, observation) do
    %{
      "status" => "accepted",
      "summary" => "Fixture oracle accepts the action.",
      "observation_kind" => observation["kind"],
      "deterministic_decision" => verifier_output["decision"]
    }
  end

  defp final_result_summary(false, verifier_output, observation) do
    %{
      "status" => "rejected",
      "summary" => "Fixture oracle rejects the action.",
      "observation_kind" => observation["kind"],
      "deterministic_decision" => verifier_output["decision"],
      "violated_constraints" => verifier_output["violated_constraints"]
    }
  end

  defp commit_state_if_valid(state, step, evidence, %{"decision" => "accept"} = verifier_output) do
    case CommitController.commit(state, step, evidence, verifier_output) do
      {:ok, next_state} -> next_state
      {:error, _reason} -> state
    end
  end

  defp commit_state_if_valid(state, _step, _evidence, _verifier_output), do: state

  defp safe_execute(workspace, step) do
    ActionExecutor.execute(workspace, step)
  rescue
    error -> {:error, {:execution_exception, Exception.message(error)}}
  end

  defp failure_observation(step, reason) do
    payload = step["action_payload"] || %{}

    %{
      "kind" => step["action_type"],
      "path" => payload["path"],
      "paths" => payload["paths"],
      "error" => inspect(reason),
      "mutated" => false
    }
    |> Enum.reject(fn {_key, value} -> is_nil(value) end)
    |> Map.new()
  end

  defp public_task_fields(task) do
    Map.take(task, [
      "schema_version",
      "task_id",
      "task_type",
      "prompt",
      "input_artifacts",
      "allowed_actions",
      "success_criteria",
      "failure_criteria",
      "side_effect_classes"
    ])
  end

  defp prepare_workspace(source_workspace) do
    target =
      Path.join(
        System.tmp_dir!(),
        "vanta_experiment002_#{Path.basename(source_workspace)}_#{System.unique_integer([:positive])}"
      )

    File.rm_rf!(target)
    File.cp_r!(source_workspace, target)
    target
  end

  defp write_results!(out_dir, run) do
    File.mkdir_p!(out_dir)
    File.write!(Path.join(out_dir, "run.json"), Jason.encode!(run, pretty: true))
    File.write!(Path.join(out_dir, "summary.md"), summary(run))
  end

  defp summary(run) do
    """
    # Experiment 002 Local Run

    Status: #{run["status"]}
    Fixture count: #{run["fixture_count"]}
    Baseline: #{run["baseline"]}
    Treatment: #{run["treatment"]}

    ## Final Answer

    #{metric_lines(run["metrics"]["final_answer"])}

    ## Raw Trace

    #{metric_lines(run["metrics"]["raw_trace"])}

    ## Structured Evidence Packet

    #{metric_lines(run["metrics"]["structured_evidence_packet"])}

    Interpretation: this is an OpenClaw local harness verifier run and must not
    be described as a pure model-only result or broad validation of H2.
    """
  end

  defp metric_lines(metrics) do
    """
    - verifier_false_accept_rate: #{metrics["verifier_false_accept_rate"]}
    - verifier_false_reject_rate: #{metrics["verifier_false_reject_rate"]}
    - evidence_sufficiency_score: #{metrics["evidence_sufficiency_score"]}
    - verifier_brier_score: #{metrics["verifier_brier_score"]}
    - request_evidence_rate: #{metrics["request_evidence_rate"]}
    - abstain_rate: #{metrics["abstain_rate"]}
    """
  end

  defp mean([]), do: 0.0
  defp mean(values), do: Enum.sum(values) / length(values)

  defp safe_div(_numerator, 0), do: 0.0
  defp safe_div(numerator, denominator), do: numerator / denominator
end
