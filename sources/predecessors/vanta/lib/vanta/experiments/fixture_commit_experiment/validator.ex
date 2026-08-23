defmodule Vanta.FixtureCommitExperiment.Validator do
  @moduledoc false

  alias Vanta.Schema

  @scenarios ~w(
    valid_approved_commit
    missing_approval
    denied_approval
    expired_approval
    wrong_scope_approval
    approval_target_mismatch
    approval_candidate_hash_mismatch
    verifier_reject
    verifier_request_evidence
    missing_evidence
    path_escape
    source_fixture_mutation
    duplicate_same_request
    conflict_same_key_different_request
    crash_before_durable_prepare
    crash_after_prepare_before_effect
    crash_after_effect_before_db_commit
    crash_after_db_commit_before_response
    restart_recovery
    rollback_success
    rollback_failure
    corrupted_approval_ref
    missing_approval_ref
    corrupted_evidence_ref
    missing_journal_refs
    irreversible_misclassification
    memory_write_smuggling
    strict_replay_mismatch
  )

  @outcomes ~w(
    committed
    rejected
    committed_idempotent
    conflict_rejected
    recovered_aborted
    recovered_rolled_back
    rolled_back
    recovery_required
    mismatch_detected
  )

  def load!(fixture_root) do
    cases =
      fixture_root
      |> Path.join("cases/*.json")
      |> Path.wildcard()
      |> Enum.sort()
      |> Enum.map(fn path ->
        fixture = Schema.load_json!(path)
        validate_fixture!(fixture, path)
        Map.put(fixture, "fixture_path", Path.relative_to(path, fixture_root))
      end)

    validate_inventory!(cases)
    validate_workspace!(fixture_root)
    cases
  end

  def scenarios, do: @scenarios

  defp validate_fixture!(fixture, path) do
    errors =
      []
      |> add_unless(present?(fixture["fixture_id"]), "fixture_id_missing")
      |> add_unless(present?(fixture["family"]), "family_missing")
      |> add_unless(fixture["scenario"] in @scenarios, "scenario_unknown")
      |> add_unless(fixture["expected_outcome"] in @outcomes, "expected_outcome_unknown")
      |> add_unless(
        Map.keys(fixture) |> Enum.sort() == ~w(expected_outcome family fixture_id scenario),
        "unexpected_fields"
      )

    if errors != [],
      do:
        raise(
          ArgumentError,
          "invalid G10 fixture #{path}: #{Enum.join(Enum.reverse(errors), ", ")}"
        )
  end

  defp validate_inventory!(cases) do
    ids = Enum.map(cases, & &1["fixture_id"])
    scenarios = Enum.map(cases, & &1["scenario"])

    cond do
      length(cases) != length(@scenarios) ->
        raise ArgumentError,
              "G10 fixture count must be #{length(@scenarios)}, got #{length(cases)}"

      length(Enum.uniq(ids)) != length(ids) ->
        raise ArgumentError, "G10 fixture IDs must be unique"

      Enum.sort(scenarios) != Enum.sort(@scenarios) ->
        raise ArgumentError, "G10 fixture scenarios must exactly match the frozen matrix"

      true ->
        :ok
    end
  end

  defp validate_workspace!(fixture_root) do
    workspace = Path.join(fixture_root, "workspace_template")
    marker = workspace |> Path.join(".vanta_fixture_workspace.json") |> Schema.load_json!()

    required = [
      Path.join(workspace, "inputs/source.md"),
      Path.join(workspace, "candidates/candidate.md"),
      Path.join(workspace, "committed/document.md")
    ]

    unless marker["scope"] == "fixture_local_committable_v0" and marker["ephemeral"] == true and
             Enum.all?(required, &File.regular?/1) do
      raise ArgumentError, "G10 workspace template is incomplete or not marked ephemeral"
    end
  end

  defp add_unless(errors, true, _error), do: errors
  defp add_unless(errors, false, error), do: [error | errors]
  defp present?(value), do: is_binary(value) and String.trim(value) != ""
end
