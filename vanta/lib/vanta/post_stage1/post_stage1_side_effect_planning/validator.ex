defmodule Vanta.PostStage1SideEffectPlanning.Validator do
  @moduledoc """
  Deterministic validator for PS1-G8 planning proposals.

  It validates planning records only. It does not compile Execution IR, collect
  approvals, or dispatch any runtime action.
  """

  alias Vanta.PostStage1SideEffectPlanning.PathHelpers

  @validator_version "PS1-G8-committable-docops-proposal-validator-v1"
  @surface_id "PS1-LC-SIDEFX-COMMITTABLE-DOCOPS-001"
  @gate_policy_version "PS1-LC-SIDEFX-GATE-001"

  @approval_fields ~w(
    approver_type
    approver_identity
    scope
    timestamp
    target_identity
    policy_version
    approval_result
  )

  @other_required_fields ~w(
    proposal_id
    surface_id
    gate_policy_version
    side_effect_class
    fixture_id
    source_artifact_ref
    candidate_artifact_ref
    proposed_commit_target
    expected_effect
    preconditions
    postconditions
    pre_effect_evidence_requirements
    post_effect_evidence_requirements
    verifier_policy_ref
    journal_requirements
    rejection_conditions
  )

  def validator_version, do: @validator_version

  def validate(proposal) when is_map(proposal) do
    checks = completeness_checks(proposal)

    reason_codes =
      []
      |> add_unless(checks["target_identity_complete"], "missing_target_identity")
      |> add_unless(checks["approval_boundary_complete"], "missing_approval_boundary")
      |> add_unless(checks["idempotency_key_present"], "missing_idempotency_key")
      |> add_unless(checks["duplicate_guard_present"], "missing_duplicate_guard")
      |> add_unless(
        checks["rollback_or_compensation_declared"],
        "missing_rollback_or_compensation_statement"
      )
      |> add_if(path_escape?(proposal), "path_escape")
      |> add_if(source_fixture_target?(proposal), "source_fixture_mutation_target")
      |> add_if(irreversible_misclassification?(proposal), "irreversible_misclassification")
      |> add_if(memory_write_smuggling?(proposal), "memory_write_smuggling")
      |> add_if(approval_as_label?(proposal), "approval_as_label")
      |> add_if(Map.has_key?(proposal, "approval_record"), "runtime_approval_record_smuggling")
      |> add_unless(proposal["surface_id"] == @surface_id, "invalid_surface_id")
      |> add_unless(
        proposal["gate_policy_version"] == @gate_policy_version,
        "invalid_gate_policy_version"
      )
      |> add_unless(proposal["side_effect_class"] == "COMMITTABLE", "invalid_side_effect_class")
      |> add_missing_required_fields(proposal)
      |> Enum.uniq()
      |> Enum.sort()

    decision = if reason_codes == [], do: "valid", else: "rejected"

    %{
      "validator_version" => @validator_version,
      "decision" => decision,
      "report_label" => report_label(decision, reason_codes),
      "reason_codes" => reason_codes,
      "completeness_checks" => checks,
      "runtime_execution_attempted" => false,
      "approval_record_collected" => false
    }
  end

  defp completeness_checks(proposal) do
    %{
      "target_identity_complete" => target_identity_complete?(proposal),
      "approval_boundary_complete" => approval_boundary_complete?(proposal),
      "idempotency_key_present" => PathHelpers.present?(proposal["idempotency_key"]),
      "duplicate_guard_present" => duplicate_guard_present?(proposal),
      "rollback_or_compensation_declared" => rollback_or_compensation_declared?(proposal)
    }
  end

  defp target_identity_complete?(proposal) do
    identity = proposal["target_identity"]

    is_map(identity) and
      Enum.all?(
        ~w(
          workspace_id
          workspace_root
          source_artifact_path
          source_artifact_hash
          candidate_artifact_path
          candidate_artifact_hash
          proposed_commit_target
          target_kind
        ),
        &PathHelpers.present?(identity[&1])
      ) and hash_ref?(identity["source_artifact_hash"]) and
      hash_ref?(identity["candidate_artifact_hash"])
  end

  defp approval_boundary_complete?(proposal) do
    requirement = proposal["approval_record_requirement"]

    PathHelpers.present?(proposal["approval_policy_ref"]) and is_list(requirement) and
      Enum.all?(@approval_fields, &(&1 in requirement))
  end

  defp duplicate_guard_present?(proposal) do
    guard = proposal["duplicate_guard"]

    is_map(guard) and guard["strategy"] == "reject_existing_or_conflicting_key" and
      PathHelpers.present?(guard["target_scope"])
  end

  defp rollback_or_compensation_declared?(proposal) do
    proposal["rollback_or_compensation_statement"] in [
      "fixture_commit_restore",
      "fixture_commit_supersede"
    ]
  end

  defp path_escape?(proposal) do
    identity = proposal["target_identity"] || %{}
    workspace_root = identity["workspace_root"]

    paths = [
      identity["source_artifact_path"],
      identity["candidate_artifact_path"],
      identity["proposed_commit_target"],
      proposal["proposed_commit_target"]
    ]

    PathHelpers.present?(workspace_root) and
      Enum.any?(paths, fn path ->
        PathHelpers.present?(path) and not PathHelpers.inside_workspace?(path, workspace_root)
      end)
  end

  defp source_fixture_target?(proposal) do
    identity = proposal["target_identity"] || %{}

    identity["source_fixture_mutation"] == true or
      Enum.any?(
        [identity["proposed_commit_target"], proposal["proposed_commit_target"]],
        fn path ->
          PathHelpers.present?(path) and
            String.starts_with?(
              PathHelpers.normalize_separator(path),
              "docs/04_experiments/fixtures/"
            )
        end
      )
  end

  defp irreversible_misclassification?(proposal) do
    effect = proposal["expected_effect"] || %{}
    identity = proposal["target_identity"] || %{}

    effect["irreversible"] == true or identity["target_kind"] == "irreversible_target"
  end

  defp memory_write_smuggling?(proposal) do
    effect = proposal["expected_effect"] || %{}
    identity = proposal["target_identity"] || %{}

    effect["memory_write"] == true or identity["target_kind"] == "memory_store"
  end

  defp approval_as_label?(proposal) do
    proposal["approval_source"] in ["fixture_oracle", "human_label"]
  end

  defp add_missing_required_fields(reason_codes, proposal) do
    Enum.reduce(@other_required_fields, reason_codes, fn field, reasons ->
      if present_required?(proposal[field]) do
        reasons
      else
        ["missing_required_field:#{field}" | reasons]
      end
    end)
  end

  defp present_required?(value) when is_binary(value), do: PathHelpers.present?(value)
  defp present_required?(value) when is_map(value), do: map_size(value) > 0
  defp present_required?(value) when is_list(value), do: value != []
  defp present_required?(_value), do: false

  defp hash_ref?("sha256:" <> digest), do: String.match?(digest, ~r/^[0-9a-f]{64}$/)
  defp hash_ref?(_value), do: false

  defp report_label("valid", _reason_codes), do: "committable_docops_planning_pilot"

  defp report_label("rejected", reason_codes) do
    cond do
      "memory_write_smuggling" in reason_codes ->
        "blocked_memory_write"

      "irreversible_misclassification" in reason_codes ->
        "blocked_irreversible_misclassification"

      Enum.any?(reason_codes, &(&1 in ["path_escape", "source_fixture_mutation_target"])) ->
        "blocked_path_escape"

      "missing_approval_boundary" in reason_codes ->
        "blocked_missing_approval"

      "missing_rollback_or_compensation_statement" in reason_codes ->
        "blocked_missing_compensation_policy"

      true ->
        "blocked_incomplete_proposal"
    end
  end

  defp add_if(reasons, true, reason), do: [reason | reasons]
  defp add_if(reasons, false, _reason), do: reasons
  defp add_unless(reasons, true, _reason), do: reasons
  defp add_unless(reasons, false, reason), do: [reason | reasons]
end
