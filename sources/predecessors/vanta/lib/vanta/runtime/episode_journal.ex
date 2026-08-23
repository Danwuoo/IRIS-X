defmodule Vanta.EpisodeJournal do
  @moduledoc """
  Persists audit and replay metadata for a Stage 1 fixture episode.
  """

  def new(task, episode_id \\ nil) do
    episode_id = episode_id || "episode_#{Map.fetch!(task, "task_id")}"

    %{
      "schema_version" => Vanta.schema_version(),
      "episode_id" => episode_id,
      "task_id" => Map.fetch!(task, "task_id"),
      "runtime_manifest" => %{
        "runtime" => "vanta_phase1",
        "runtime_version" => "0.1.0",
        "language" => "elixir",
        "language_version" => System.version(),
        "otp_version" => System.otp_release(),
        "schema_version" => Vanta.schema_version(),
        "schema_contracts" => [
          "execution_step",
          "evidence_packet",
          "verifier_output",
          "episode_journal"
        ],
        "tool_environment" => %{
          "action_executor" => "fixture_local_document_ops_v0",
          "commit_controller" => "stage1_commit_controller_v0",
          "replay_runner" => "journal_action_sequence_replay_v0",
          "verifier_runtime" => "deterministic_rules_v0"
        },
        "side_effect_classes_allowed" => Vanta.authorized_side_effect_classes(task)
      },
      "steps" => [],
      "state_hashes" => [],
      "evidence_refs" => [],
      "verifier_output_refs" => [],
      "approval_record_refs" => [],
      "artifact_refs" => [],
      "commit_status" => "not_started",
      "rollback_status" => "not_applicable",
      "memory_write_effects" => []
    }
  end

  def record_state(journal, state) do
    update_in(journal, ["state_hashes"], &append_unique(&1, state["state_hash"]))
  end

  def record_step(journal, step) do
    update_in(journal, ["steps"], &(&1 ++ [step]))
  end

  def record_evidence(journal, evidence) do
    update_in(journal, ["evidence_refs"], &append_unique(&1, evidence["evidence_id"]))
  end

  def record_verifier_output(journal, verifier_output) do
    update_in(
      journal,
      ["verifier_output_refs"],
      &append_unique(&1, verifier_output["verifier_output_id"])
    )
  end

  def record_approval(journal, approval_record) do
    update_in(
      journal,
      ["approval_record_refs"],
      &append_unique(&1, approval_record["approval_id"])
    )
  end

  def record_artifact(journal, artifact_ref) do
    update_in(journal, ["artifact_refs"], fn refs -> refs ++ [artifact_ref] end)
  end

  def set_commit_status(journal, status), do: Map.put(journal, "commit_status", status)
  def set_rollback_status(journal, status), do: Map.put(journal, "rollback_status", status)

  def validate!(journal), do: Vanta.Schema.validate!("episode_journal", journal)

  defp append_unique(values, value), do: Enum.uniq(values ++ [value])
end
