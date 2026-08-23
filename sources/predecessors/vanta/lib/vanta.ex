defmodule Vanta do
  @moduledoc """
  Stage 1 MVP runtime skeleton for fixture-local Document Ops tasks.
  """

  @schema_version "stage1-mvp-v1"
  @persistence_schema_version "persistence-v0"
  @hash_policy_version "canonical-json-sha256-v1"
  @allowed_side_effect_classes ~w(READ_ONLY SIMULATED REVERSIBLE COMPENSABLE)
  @fixture_commit_action_types ~w(commit_fixture_document_candidate)
  @action_types ~w(
    read_file
    list_files
    compute_hash
    inspect_document_structure
    validate_document_contract
    simulate_structured_edit
    apply_reversible_structured_edit
    simulate_patch
    compute_diff
    apply_reversible_patch
    record_compensable_action
    validate_artifact
  )

  def schema_version, do: @schema_version

  def persistence_schema_version, do: @persistence_schema_version

  def hash_policy_version, do: @hash_policy_version

  def allowed_side_effect_classes, do: @allowed_side_effect_classes

  def action_types, do: @action_types

  def fixture_commit_action_types, do: @fixture_commit_action_types

  def side_effect_allowed?("commit_fixture_document_candidate", "COMMITTABLE"), do: true

  def side_effect_allowed?(_action_type, side_effect_class),
    do: side_effect_class in @allowed_side_effect_classes

  def authorized_side_effect_classes(task) when is_map(task) do
    if Enum.any?(@fixture_commit_action_types, &(&1 in Map.get(task, "allowed_actions", []))) do
      @allowed_side_effect_classes ++ ["COMMITTABLE"]
    else
      @allowed_side_effect_classes
    end
  end
end
