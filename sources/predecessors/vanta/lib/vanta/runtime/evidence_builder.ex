defmodule Vanta.EvidenceBuilder do
  @moduledoc """
  Builds Evidence Packet records from state, ExecutionStep, and normalized observation.
  """

  alias Vanta.StateManager

  def build(pre_state, step, observation, opts \\ []) do
    post_state =
      Keyword.get(
        opts,
        :post_state,
        StateManager.append_event(pre_state, event_from(step, observation))
      )

    evidence = %{
      "schema_version" => Vanta.schema_version(),
      "evidence_id" => "evidence_#{step["step_id"]}",
      "episode_id" => step["episode_id"],
      "step_id" => step["step_id"],
      "pre_state_hash" => pre_state["state_hash"],
      "pre_state_summary" => pre_state["task_intent"],
      "action_ref" => step["step_id"],
      "observation" => observation,
      "post_state_summary" => post_state["task_intent"],
      "post_state_hash" => post_state["state_hash"],
      "verifier_result" => %{},
      "confidence" => 1.0,
      "disagreement" => %{},
      "violated_constraints" => [],
      "failure_logits" => %{},
      "credit_hints" => %{},
      "provenance" => provenance(step, observation),
      "runtime_context" => runtime_context(step)
    }

    Vanta.Schema.validate!("evidence_packet", evidence)
  end

  defp event_from(step, observation) do
    %{
      "step_id" => step["step_id"],
      "action_type" => step["action_type"],
      "observation_kind" => observation["kind"],
      "mutated" => Map.get(observation, "mutated", false)
    }
  end

  defp provenance(step, observation) do
    %{
      "source" => "fixture_workspace",
      "action_type" => step["action_type"],
      "paths" =>
        [
          observation["path"],
          observation["paths"],
          observation["contract_ref"],
          get_in(observation, ["backup_metadata", "backup_path"]),
          get_in(observation, ["backup_metadata", "metadata_path"])
        ]
        |> List.flatten()
        |> Enum.reject(&is_nil/1)
        |> Enum.uniq()
    }
  end

  defp runtime_context(step) do
    %{
      "runtime" => "vanta_phase1",
      "schema_version" => Vanta.schema_version(),
      "side_effect_class" => step["side_effect_class"]
    }
  end
end
