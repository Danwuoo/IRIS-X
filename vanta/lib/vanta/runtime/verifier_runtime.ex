defmodule Vanta.VerifierRuntime do
  @moduledoc """
  Deterministic Stage 1 Verifier v0.
  """

  alias Vanta.{ExecutionIRCompiler, FixtureAcceptance, Hash, PathGuard}

  @required_evidence_fields ~w(
    schema_version
    evidence_id
    episode_id
    step_id
    pre_state_hash
    post_state_hash
    action_ref
    observation
    post_state_summary
    provenance
    runtime_context
  )

  def verify(step, evidence), do: verify(step, evidence, %{})

  def verify(step, evidence, context) do
    missing_fields = missing_evidence_fields(evidence)

    forbidden_side_effect? =
      not Vanta.side_effect_allowed?(step["action_type"], step["side_effect_class"])

    policy_violations = policy_violations(step, context)

    cond do
      forbidden_side_effect? ->
        output(step, evidence, "reject", 0.0, 1.0, 1.0, ["side_effect_class_not_allowed"], [])

      schema_invalid?(step, "execution_step") ->
        output(step, evidence, "reject", 0.0, 0.95, 0.7, ["execution_step_schema_invalid"], [])

      policy_violations != [] ->
        output(step, evidence, "reject", 0.0, 0.95, 0.8, Enum.sort(policy_violations), [])

      missing_fields != [] ->
        output(step, evidence, "request_evidence", 0.0, 0.95, 0.8, [], missing_fields)

      schema_invalid?(evidence, "evidence_packet") ->
        output(step, evidence, "request_evidence", 0.0, 0.95, 0.7, [], [
          "schema_valid_evidence_packet"
        ])

      true ->
        case evidence_violations(step, evidence, context) do
          [] ->
            output(step, evidence, "accept", 1.0, 0.9, 0.1, [], [])

          violations ->
            output(step, evidence, "reject", 0.0, 0.95, 0.8, Enum.sort(violations), [])
        end
    end
  end

  def missing_evidence_fields(evidence) when is_map(evidence) do
    Enum.reject(@required_evidence_fields, &Map.has_key?(evidence, &1))
  end

  defp schema_invalid?(artifact, schema_name) do
    case Vanta.Schema.validate(schema_name, artifact) do
      :ok -> false
      {:error, _errors} -> true
    end
  end

  defp policy_violations(step, context) do
    task = Map.get(context, :task) || Map.get(context, "task")

    []
    |> require_task_allowed_action(task, step)
    |> require_task_side_effect_class(task, step)
    |> require_action_side_effect_match(step)
    |> Enum.uniq()
  end

  defp evidence_violations(step, evidence, context) do
    observation = Map.get(evidence, "observation", %{})
    workspace = Map.get(context, :workspace) || Map.get(context, "workspace")

    []
    |> require_workspace_paths(workspace, step, evidence, observation)
    |> require_observation_kind(step, observation)
    |> require_read_only_semantics(step, observation)
    |> require_structured_read_semantics(step, observation)
    |> require_simulated_semantics(step, observation, workspace)
    |> require_structured_simulated_semantics(step, observation)
    |> require_reversible_semantics(step, observation, workspace)
    |> require_structured_reversible_semantics(step, observation, workspace)
    |> require_compensable_semantics(step, observation)
    |> require_audit_validation(observation)
    |> require_fixture_acceptance(observation, workspace)
    |> Enum.uniq()
  end

  defp require_task_allowed_action(violations, nil, _step), do: violations

  defp require_task_allowed_action(violations, task, step) do
    if step["action_type"] in Map.get(task, "allowed_actions", []) do
      violations
    else
      ["action_not_allowed_by_task" | violations]
    end
  end

  defp require_task_side_effect_class(violations, nil, _step), do: violations

  defp require_task_side_effect_class(violations, task, step) do
    if step["side_effect_class"] in Map.get(task, "side_effect_classes", []) do
      violations
    else
      ["side_effect_class_not_allowed_by_task" | violations]
    end
  end

  defp require_action_side_effect_match(violations, step) do
    actual_side_effect_class = step["side_effect_class"]

    case ExecutionIRCompiler.action_side_effect_class(step["action_type"]) do
      {:ok, ^actual_side_effect_class} ->
        violations

      {:ok, _side_effect_class} ->
        ["action_side_effect_class_mismatch" | violations]

      :error ->
        ["action_type_unknown" | violations]
    end
  end

  defp require_workspace_paths(violations, nil, _step, _evidence, _observation), do: violations

  defp require_workspace_paths(violations, workspace, step, evidence, observation) do
    [
      {"provenance_path_escapes_workspace", get_in(evidence, ["provenance", "paths"])},
      {"observation_path_escapes_workspace", observation_paths(observation)},
      {"action_path_escapes_workspace", action_paths(step)}
    ]
    |> Enum.reduce(violations, fn {violation, paths}, acc ->
      if paths |> path_list() |> Enum.any?(&path_escapes_workspace?(workspace, &1)) do
        [violation | acc]
      else
        acc
      end
    end)
  end

  defp observation_paths(observation) do
    [observation["path"], observation["paths"]]
    |> path_list()
  end

  defp action_paths(step) do
    payload = Map.get(step, "action_payload", %{})

    [payload["path"], payload["paths"], payload["contract_ref"]]
    |> path_list()
  end

  defp path_list(nil), do: []

  defp path_list(paths) do
    paths
    |> List.wrap()
    |> Enum.flat_map(&List.wrap/1)
    |> Enum.filter(&is_binary/1)
    |> Enum.uniq()
  end

  defp path_escapes_workspace?(workspace, path) do
    case PathGuard.safe_resolve(workspace, path) do
      {:ok, _path} -> false
      {:error, _reason} -> true
    end
  end

  defp require_observation_kind(violations, step, observation) do
    cond do
      Map.has_key?(observation, "error") ->
        ["action_execution_failed" | violations]

      observation["kind"] in [step["action_type"], "validate_artifact"] ->
        violations

      true ->
        ["observation_kind_mismatch" | violations]
    end
  end

  defp require_read_only_semantics(violations, %{"side_effect_class" => "READ_ONLY"}, observation) do
    if Map.get(observation, "mutated", false) do
      ["read_only_action_mutated" | violations]
    else
      violations
    end
  end

  defp require_read_only_semantics(violations, _step, _observation), do: violations

  defp require_structured_read_semantics(
         violations,
         %{"action_type" => "inspect_document_structure"},
         observation
       ) do
    violations
    |> require_present(observation, "file_hash", "file_hash_missing")
    |> require_map(observation, "structure", "structure_summary_missing")
    |> require_list(observation, "parse_diagnostics", "parse_diagnostics_missing")
  end

  defp require_structured_read_semantics(
         violations,
         %{"action_type" => "validate_document_contract"},
         observation
       ) do
    violations
    |> require_present(observation, "file_hash", "file_hash_missing")
    |> require_present(observation, "contract_hash", "contract_hash_missing")
    |> require_boolean(observation, "passed", "contract_result_missing")
    |> require_list(observation, "failures", "contract_failures_missing")
  end

  defp require_structured_read_semantics(violations, _step, _observation), do: violations

  defp require_simulated_semantics(
         violations,
         %{"side_effect_class" => "SIMULATED"},
         observation,
         workspace
       ) do
    violations
    |> require_mutated_false(observation, "simulated_action_mutated")
    |> require_diff_or_summary(observation)
    |> require_source_hash_unchanged(observation, workspace)
  end

  defp require_simulated_semantics(violations, _step, _observation, _workspace), do: violations

  defp require_structured_simulated_semantics(
         violations,
         %{"action_type" => "simulate_structured_edit"},
         observation
       ) do
    violations
    |> require_selector_resolved(observation)
    |> require_present(observation, "candidate_content", "candidate_content_missing")
    |> require_present(observation, "before_hash", "before_hash_missing")
    |> require_present(observation, "after_hash", "after_hash_missing")
    |> require_present(
      observation,
      "source_hash_after_simulation",
      "source_hash_after_simulation_missing"
    )
    |> require_source_hash_after_simulation(observation)
  end

  defp require_structured_simulated_semantics(violations, _step, _observation), do: violations

  defp require_reversible_semantics(
         violations,
         %{"side_effect_class" => "REVERSIBLE"},
         observation,
         workspace
       ) do
    violations
    |> require_diff_or_summary(observation)
    |> require_backup_metadata(observation, workspace)
  end

  defp require_reversible_semantics(violations, _step, _observation, _workspace), do: violations

  defp require_structured_reversible_semantics(
         violations,
         %{"action_type" => "apply_reversible_structured_edit"},
         observation,
         workspace
       ) do
    violations
    |> require_selector_resolved(observation)
    |> require_present(observation, "before_hash", "before_hash_missing")
    |> require_present(observation, "after_hash", "after_hash_missing")
    |> require_present(observation, "source_hash_after_write", "source_hash_after_write_missing")
    |> require_structured_backup_metadata(observation, workspace)
  end

  defp require_structured_reversible_semantics(violations, _step, _observation, _workspace),
    do: violations

  defp require_compensable_semantics(
         violations,
         %{"side_effect_class" => "COMPENSABLE"},
         observation
       ) do
    if Map.get(observation, "compensation_required", false) do
      ["compensation_required" | violations]
    else
      violations
    end
  end

  defp require_compensable_semantics(violations, _step, _observation), do: violations

  defp require_audit_validation(
         violations,
         %{
           "kind" => "validate_artifact",
           "validation" => "episode_audit_refs",
           "audit_complete" => false
         }
       ) do
    ["audit_gap_detected" | violations]
  end

  defp require_audit_validation(violations, _observation), do: violations

  defp require_mutated_false(violations, observation, violation) do
    if Map.get(observation, "mutated", false) do
      [violation | violations]
    else
      violations
    end
  end

  defp require_diff_or_summary(violations, observation) do
    if present?(observation["diff"]) or present?(observation["result_summary"]) do
      violations
    else
      ["diff_or_result_summary_missing" | violations]
    end
  end

  defp require_source_hash_unchanged(violations, _observation, nil), do: violations

  defp require_source_hash_unchanged(violations, observation, workspace) do
    with path when is_binary(path) <- observation["path"],
         before_hash when is_binary(before_hash) <- observation["before_hash"],
         {:ok, abs_path} <- PathGuard.safe_resolve(workspace, path),
         true <- File.exists?(abs_path),
         current_hash <- Hash.file_hash(abs_path),
         true <- current_hash == before_hash do
      violations
    else
      _other -> ["simulated_source_hash_changed" | violations]
    end
  end

  defp require_backup_metadata(violations, observation, workspace) do
    metadata = observation["backup_metadata"]

    cond do
      not is_map(metadata) ->
        ["backup_metadata_missing" | violations]

      is_nil(workspace) ->
        violations

      true ->
        violations
        |> require_metadata_path(metadata, workspace, "backup_path", "backup_file_missing")
        |> require_metadata_path(
          metadata,
          workspace,
          "metadata_path",
          "backup_metadata_file_missing"
        )
        |> require_hash_match(metadata, observation)
    end
  end

  defp require_structured_backup_metadata(violations, observation, workspace) do
    metadata = observation["backup_metadata"]

    cond do
      not is_map(metadata) ->
        violations

      metadata["backup_policy"] != "fixture_backup_restore" ->
        ["backup_policy_invalid" | violations]

      is_nil(workspace) ->
        violations

      true ->
        violations
        |> require_backup_hash(metadata, workspace)
        |> require_source_hash_after_write(observation, workspace)
        |> require_metadata_diff_hash(metadata, observation)
    end
  end

  defp require_backup_hash(violations, metadata, workspace) do
    with backup_path when is_binary(backup_path) <- metadata["backup_path"],
         {:ok, abs_path} <- PathGuard.safe_resolve(workspace, backup_path),
         true <- File.exists?(abs_path),
         backup_hash <- Hash.file_hash(abs_path),
         true <- backup_hash == metadata["backup_hash"],
         true <- backup_hash == metadata["before_hash"] do
      violations
    else
      _other -> ["backup_hash_mismatch" | violations]
    end
  end

  defp require_source_hash_after_write(violations, observation, workspace) do
    with path when is_binary(path) <- observation["path"],
         after_hash when is_binary(after_hash) <- observation["after_hash"],
         source_hash_after_write when is_binary(source_hash_after_write) <-
           observation["source_hash_after_write"],
         true <- source_hash_after_write == after_hash,
         {:ok, abs_path} <- PathGuard.safe_resolve(workspace, path),
         true <- File.exists?(abs_path),
         current_hash <- Hash.file_hash(abs_path),
         true <- current_hash == after_hash do
      violations
    else
      _other -> ["source_hash_after_write_mismatch" | violations]
    end
  end

  defp require_metadata_diff_hash(violations, metadata, observation) do
    with diff when is_binary(diff) <- observation["diff"],
         diff_hash when is_binary(diff_hash) <- metadata["diff_hash"],
         true <- Hash.sha256(diff) == diff_hash do
      violations
    else
      _other -> ["backup_diff_hash_mismatch" | violations]
    end
  end

  defp require_metadata_path(violations, metadata, workspace, key, violation) do
    with path when is_binary(path) <- metadata[key],
         {:ok, abs_path} <- PathGuard.safe_resolve(workspace, path),
         true <- File.exists?(abs_path) do
      violations
    else
      _other -> [violation | violations]
    end
  end

  defp require_hash_match(violations, metadata, observation) do
    cond do
      metadata["before_hash"] != observation["before_hash"] ->
        ["backup_before_hash_mismatch" | violations]

      metadata["after_hash"] != observation["after_hash"] ->
        ["backup_after_hash_mismatch" | violations]

      true ->
        violations
    end
  end

  defp require_selector_resolved(violations, observation) do
    case get_in(observation, ["selector_resolution", "status"]) do
      "resolved" -> violations
      "missing" -> ["structured_selector_missing" | violations]
      "ambiguous" -> ["structured_selector_ambiguous" | violations]
      _other -> ["structured_selector_resolution_missing" | violations]
    end
  end

  defp require_source_hash_after_simulation(violations, observation) do
    if observation["source_hash_after_simulation"] == observation["before_hash"] do
      violations
    else
      ["source_hash_after_simulation_mismatch" | violations]
    end
  end

  defp require_present(violations, observation, key, violation) do
    if present?(observation[key]), do: violations, else: [violation | violations]
  end

  defp require_map(violations, observation, key, violation) do
    if is_map(observation[key]), do: violations, else: [violation | violations]
  end

  defp require_list(violations, observation, key, violation) do
    if is_list(observation[key]), do: violations, else: [violation | violations]
  end

  defp require_boolean(violations, observation, key, violation) do
    if is_boolean(observation[key]), do: violations, else: [violation | violations]
  end

  defp require_fixture_acceptance(violations, _observation, nil), do: violations

  defp require_fixture_acceptance(violations, observation, workspace) do
    case FixtureAcceptance.evaluate_observation(workspace, observation) do
      {:error, reason} -> [reason | violations]
      _other -> violations
    end
  end

  defp present?(value), do: is_binary(value) and String.trim(value) != ""

  defp output(step, evidence, decision, validity, confidence, risk, violations, extra_evidence) do
    verifier_output = %{
      "schema_version" => Vanta.schema_version(),
      "verifier_output_id" => "verifier_#{step["step_id"]}",
      "episode_id" => step["episode_id"],
      "step_id" => step["step_id"],
      "evidence_refs" => evidence_refs(evidence),
      "decision" => decision,
      "verification_scope" => [
        "preconditions",
        "postconditions",
        "evidence_sufficiency",
        "policy_constraints",
        "side_effect_safety",
        "state_consistency"
      ],
      "validity_score" => validity,
      "confidence" => confidence,
      "calibration_state" => %{"method" => "deterministic_rules_v0"},
      "disagreement" => %{},
      "risk_score" => risk,
      "violated_constraints" => violations,
      "required_extra_evidence" => extra_evidence,
      "failure_logits" => %{},
      "credit_hints" => %{}
    }

    Vanta.Schema.validate!("verifier_output", verifier_output)
  end

  defp evidence_refs(%{"evidence_id" => evidence_id}), do: [evidence_id]
  defp evidence_refs(_evidence), do: []
end
