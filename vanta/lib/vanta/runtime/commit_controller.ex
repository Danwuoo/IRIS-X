defmodule Vanta.CommitController do
  @moduledoc """
  Applies the Stage 1 commit rule for fixture-local actions.
  """

  alias Vanta.{StateManager, VerifierRuntime}

  def commit(state, step, evidence, verifier_output) do
    cond do
      verifier_output["decision"] != "accept" ->
        {:error, :verifier_not_accept}

      not Vanta.side_effect_allowed?(step["action_type"], step["side_effect_class"]) ->
        {:error, :side_effect_class_not_allowed}

      VerifierRuntime.missing_evidence_fields(evidence) != [] ->
        {:error, :missing_evidence}

      step["side_effect_class"] == "REVERSIBLE" and
          not Map.has_key?(evidence["observation"], "backup_metadata") ->
        {:error, :missing_rollback_metadata}

      step["action_type"] == "apply_reversible_structured_edit" and
          get_in(evidence, ["observation", "backup_metadata", "backup_policy"]) !=
            "fixture_backup_restore" ->
        {:error, :invalid_rollback_policy}

      step["side_effect_class"] == "COMPENSABLE" ->
        {:error, :compensation_required}

      true ->
        committed_state =
          StateManager.append_event(state, event_from(step, evidence["observation"]))

        if committed_state["state_hash"] == evidence["post_state_hash"] do
          {:ok, committed_state}
        else
          {:error, :post_state_hash_mismatch}
        end
    end
  end

  defp event_from(step, observation) do
    %{
      "step_id" => step["step_id"],
      "action_type" => step["action_type"],
      "observation_kind" => observation["kind"],
      "mutated" => Map.get(observation, "mutated", false)
    }
  end
end
