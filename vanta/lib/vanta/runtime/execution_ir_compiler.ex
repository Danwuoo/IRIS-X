defmodule Vanta.ExecutionIRCompiler do
  @moduledoc """
  Compiles Stage 1 action proposals into ExecutionStep records.
  """

  @action_classes %{
    "read_file" => "READ_ONLY",
    "list_files" => "READ_ONLY",
    "compute_hash" => "READ_ONLY",
    "validate_artifact" => "READ_ONLY",
    "inspect_document_structure" => "READ_ONLY",
    "validate_document_contract" => "READ_ONLY",
    "simulate_structured_edit" => "SIMULATED",
    "apply_reversible_structured_edit" => "REVERSIBLE",
    "simulate_patch" => "SIMULATED",
    "compute_diff" => "SIMULATED",
    "apply_reversible_patch" => "REVERSIBLE",
    "record_compensable_action" => "COMPENSABLE",
    "commit_fixture_document_candidate" => "COMMITTABLE"
  }

  def compile(task, episode_id, action_type, payload \\ %{}, occurrence_index \\ nil) do
    with :ok <- allowed_action?(task, action_type),
         {:ok, side_effect_class} <- side_effect_class(task, action_type),
         :ok <- runtime_side_effect?(action_type, side_effect_class) do
      step = %{
        "schema_version" => Vanta.schema_version(),
        "step_id" => step_id(episode_id, action_type, occurrence_index),
        "episode_id" => episode_id,
        "parent_step_id" => nil,
        "action_type" => action_type,
        "action_payload" => payload,
        "expected_effect" => expected_effect(action_type),
        "preconditions" => preconditions(action_type),
        "postconditions" => postconditions(action_type),
        "dependency_edges" => [],
        "verifier_requirements" => verifier_requirements(action_type),
        "rollback_policy" => rollback_policy(side_effect_class),
        "side_effect_class" => side_effect_class,
        "status" => "ready"
      }

      {:ok, Vanta.Schema.validate!("execution_step", step)}
    end
  end

  def action_side_effect_class(action_type), do: Map.fetch(@action_classes, action_type)

  def rejected_step(_task, episode_id, action_type, payload, _reason, occurrence_index \\ nil) do
    side_effect_class =
      case Map.fetch(@action_classes, action_type) do
        {:ok, class} -> class
        :error -> "IRREVERSIBLE"
      end

    step = %{
      "schema_version" => Vanta.schema_version(),
      "step_id" => step_id(episode_id, action_type, occurrence_index),
      "episode_id" => episode_id,
      "parent_step_id" => nil,
      "action_type" => action_type,
      "action_payload" => payload,
      "expected_effect" => expected_effect(action_type),
      "preconditions" => preconditions(action_type),
      "postconditions" => postconditions(action_type),
      "dependency_edges" => [],
      "verifier_requirements" => [
        "schema_valid",
        "evidence_complete",
        "side_effect_allowed",
        "provenance_present"
      ],
      "rollback_policy" => rollback_policy(side_effect_class),
      "side_effect_class" => side_effect_class,
      "status" => "rejected"
    }

    Vanta.Schema.validate!("execution_step", step)
  end

  defp allowed_action?(task, action_type) do
    if action_type in Map.get(task, "allowed_actions", []) do
      :ok
    else
      {:error, {:action_not_allowed, action_type}}
    end
  end

  defp side_effect_class(task, action_type) do
    with {:ok, side_effect_class} <- Map.fetch(@action_classes, action_type) do
      if side_effect_class in Map.get(task, "side_effect_classes", []) do
        {:ok, side_effect_class}
      else
        {:error, {:side_effect_class_not_allowed_by_task, side_effect_class}}
      end
    end
  end

  defp runtime_side_effect?(action_type, side_effect_class) do
    if Vanta.side_effect_allowed?(action_type, side_effect_class) do
      :ok
    else
      {:error, {:side_effect_class_not_allowed_in_runtime, side_effect_class}}
    end
  end

  defp step_id(episode_id, action_type, nil), do: "step_#{episode_id}_#{action_type}"

  defp step_id(episode_id, action_type, occurrence_index)
       when is_integer(occurrence_index) and occurrence_index >= 0 do
    index =
      occurrence_index
      |> Integer.to_string()
      |> String.pad_leading(3, "0")

    "step_#{episode_id}_#{index}_#{action_type}"
  end

  defp step_id(episode_id, action_type, occurrence_index) do
    "step_#{episode_id}_#{occurrence_index}_#{action_type}"
  end

  defp expected_effect("read_file"), do: "Read fixture-local file content without mutation."
  defp expected_effect("list_files"), do: "List fixture-local files without mutation."
  defp expected_effect("compute_hash"), do: "Compute fixture-local file hash without mutation."
  defp expected_effect("validate_artifact"), do: "Validate an artifact without mutation."

  defp expected_effect("inspect_document_structure"),
    do: "Parse fixture-local document structure without mutation."

  defp expected_effect("validate_document_contract"),
    do:
      "Validate a fixture-local document against an inline or fixture-local contract without mutation."

  defp expected_effect("simulate_structured_edit"),
    do: "Compute a selector-based candidate structured edit without writing source files."

  defp expected_effect("apply_reversible_structured_edit"),
    do: "Apply a selector-based fixture-local edit with backup metadata."

  defp expected_effect("simulate_patch"), do: "Compute a candidate patch without writing it."
  defp expected_effect("compute_diff"), do: "Compute a diff without writing source files."

  defp expected_effect("apply_reversible_patch"),
    do: "Apply a fixture-local edit with backup metadata."

  defp expected_effect("record_compensable_action"),
    do: "Record a fixture-local compensable action receipt without executing an external effect."

  defp expected_effect("commit_fixture_document_candidate"),
    do: "Promote one verified candidate document into a marked copied fixture workspace."

  defp expected_effect(_action_type), do: "Reject unsupported action before execution."

  defp preconditions(_action_type), do: ["fixture_workspace_exists", "action_is_allowed"]

  defp postconditions("apply_reversible_patch"),
    do: ["backup_metadata_exists", "change_is_rollbackable"]

  defp postconditions("apply_reversible_structured_edit"),
    do: ["selector_resolved", "backup_metadata_exists", "change_is_rollbackable"]

  defp postconditions("simulate_structured_edit"),
    do: ["selector_resolved", "source_files_preserved_unless_explicitly_allowed"]

  defp postconditions("inspect_document_structure"),
    do: ["structure_summary_recorded", "source_files_preserved_unless_explicitly_allowed"]

  defp postconditions("validate_document_contract"),
    do: ["contract_result_recorded", "source_files_preserved_unless_explicitly_allowed"]

  defp postconditions("record_compensable_action"),
    do: ["compensation_record_required", "rollback_not_claimed"]

  defp postconditions("commit_fixture_document_candidate"),
    do: [
      "approval_scope_valid",
      "prepared_intent_precedes_effect",
      "candidate_hash_equals_committed_hash",
      "source_and_candidate_unchanged",
      "durable_commit_refs_complete"
    ]

  defp postconditions(_action_type), do: ["source_files_preserved_unless_explicitly_allowed"]

  defp rollback_policy("REVERSIBLE"), do: "fixture_backup_restore"
  defp rollback_policy("COMPENSABLE"), do: "compensation_record"
  defp rollback_policy("COMMITTABLE"), do: "fixture_commit_restore"
  defp rollback_policy(_side_effect_class), do: "not_applicable"

  defp verifier_requirements("commit_fixture_document_candidate") do
    [
      "schema_valid",
      "approval_record_valid_and_in_scope",
      "pre_effect_evidence_complete",
      "pre_effect_verifier_accept",
      "post_effect_evidence_complete",
      "post_effect_verifier_accept",
      "durable_prepared_intent",
      "idempotency_and_conflict_guard",
      "durable_audit_refs_complete"
    ]
  end

  defp verifier_requirements(_action_type) do
    ["schema_valid", "evidence_complete", "side_effect_allowed", "provenance_present"]
  end
end
