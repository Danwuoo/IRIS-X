defmodule Vanta.EvaluationHarness do
  @moduledoc """
  Computes minimal process-integrity checks from Stage 1 episode journals.
  """

  @audit_fields ~w(
    schema_version
    episode_id
    task_id
    runtime_manifest
    steps
    state_hashes
    evidence_refs
    verifier_output_refs
    commit_status
    rollback_status
    memory_write_effects
  )

  @rollback_statuses ~w(
    not_applicable
    available
    completed
    failed
    unavailable
    compensation_required
    compensation_completed
    irreversible_escalation
  )

  def audit_complete?(journal, artifacts \\ %{}) do
    journal
    |> audit_result(artifacts)
    |> Map.fetch!("complete")
  end

  def audit_result(journal, artifacts \\ %{}) do
    checklist = %{
      "episode_metadata" => episode_metadata?(journal),
      "replay_metadata" => replay_metadata?(journal),
      "step_audit" => step_audit?(journal),
      "state_audit" => state_audit?(journal),
      "evidence_audit" => evidence_audit?(journal, artifacts),
      "verifier_audit" => verifier_audit?(journal, artifacts),
      "commit_audit" => commit_audit?(journal, artifacts),
      "rollback_memory_boundary" => rollback_memory_boundary?(journal)
    }

    missing =
      checklist
      |> Enum.reject(fn {_check, passed?} -> passed? end)
      |> Enum.map(fn {check, _passed?} -> check end)
      |> Enum.sort()

    %{
      "complete" => missing == [],
      "checklist" => checklist,
      "missing" => missing
    }
  end

  def metrics(journals) do
    entries = Enum.map(journals, &journal_artifacts/1)
    total = max(length(entries), 1)

    complete =
      Enum.count(entries, fn {journal, artifacts} -> audit_complete?(journal, artifacts) end)

    %{
      "audit_completeness" => complete / total,
      "commit_integrity_score" => commit_integrity_score(entries)
    }
  end

  def commit_integrity_complete?(journal, artifacts \\ %{}) do
    commit_audit?(journal, artifacts)
  end

  defp episode_metadata?(journal) do
    Enum.all?(@audit_fields, &Map.has_key?(journal, &1)) and
      is_binary(journal["schema_version"]) and
      is_binary(journal["episode_id"]) and
      is_binary(journal["task_id"]) and
      is_map(journal["runtime_manifest"])
  end

  defp replay_metadata?(journal) do
    manifest = journal["runtime_manifest"]

    is_map(manifest) and
      present?(manifest["runtime"]) and
      present?(manifest["runtime_version"]) and
      present?(manifest["language"]) and
      present?(manifest["language_version"]) and
      present?(manifest["otp_version"]) and
      present?(manifest["schema_version"]) and
      non_empty_list?(manifest["schema_contracts"]) and
      is_map(manifest["tool_environment"]) and
      non_empty_list?(manifest["side_effect_classes_allowed"])
  end

  defp step_audit?(journal) do
    steps = Map.get(journal, "steps", [])

    steps != [] and
      Enum.all?(steps, fn step ->
        Vanta.Schema.validate("execution_step", step) == :ok and
          present?(step["step_id"]) and
          present?(step["action_type"]) and
          is_map(step["action_payload"]) and
          present?(step["status"]) and
          present?(step["side_effect_class"]) and
          present?(step["rollback_policy"])
      end)
  end

  defp state_audit?(journal) do
    state_hashes = Map.get(journal, "state_hashes", [])

    non_empty_list?(state_hashes) and
      Enum.all?(state_hashes, &present?/1) and
      (journal["commit_status"] != "committed" or length(state_hashes) >= 2)
  end

  defp evidence_audit?(journal, artifacts) do
    evidence_by_id = artifact_index(artifacts, :evidence_packets, "evidence_id")
    evidence_refs = Map.get(journal, "evidence_refs", [])
    step_ids = journal |> Map.get("steps", []) |> MapSet.new(& &1["step_id"])

    non_empty_list?(evidence_refs) and
      length(evidence_refs) >= length(Map.get(journal, "steps", [])) and
      Enum.all?(evidence_refs, fn ref ->
        case Map.fetch(evidence_by_id, ref) do
          {:ok, evidence} ->
            Vanta.Schema.validate("evidence_packet", evidence) == :ok and
              evidence["episode_id"] == journal["episode_id"] and
              MapSet.member?(step_ids, evidence["step_id"]) and
              evidence["action_ref"] == evidence["step_id"]

          :error ->
            false
        end
      end)
  end

  defp verifier_audit?(journal, artifacts) do
    verifier_by_id = artifact_index(artifacts, :verifier_outputs, "verifier_output_id")
    evidence_refs = MapSet.new(Map.get(journal, "evidence_refs", []))
    verifier_refs = Map.get(journal, "verifier_output_refs", [])
    step_ids = journal |> Map.get("steps", []) |> MapSet.new(& &1["step_id"])

    non_empty_list?(verifier_refs) and
      length(verifier_refs) >= length(Map.get(journal, "steps", [])) and
      Enum.all?(verifier_refs, fn ref ->
        case Map.fetch(verifier_by_id, ref) do
          {:ok, verifier_output} ->
            Vanta.Schema.validate("verifier_output", verifier_output) == :ok and
              verifier_output["episode_id"] == journal["episode_id"] and
              MapSet.member?(step_ids, verifier_output["step_id"]) and
              Enum.all?(verifier_output["evidence_refs"], &MapSet.member?(evidence_refs, &1))

          :error ->
            false
        end
      end)
  end

  defp commit_audit?(journal, artifacts) do
    steps = Map.get(journal, "steps", [])
    committed_steps = Enum.filter(steps, &(&1["status"] == "committed"))
    evidence_by_step = artifact_index(artifacts, :evidence_packets, "step_id")
    verifier_by_step = artifact_index(artifacts, :verifier_outputs, "step_id")

    cond do
      journal["commit_status"] == "committed" and committed_steps == [] ->
        false

      journal["commit_status"] != "committed" ->
        true

      true ->
        Enum.all?(committed_steps, fn step ->
          evidence = Map.get(evidence_by_step, step["step_id"])
          verifier_output = Map.get(verifier_by_step, step["step_id"])

          not is_nil(evidence) and
            not is_nil(verifier_output) and
            verifier_output["decision"] == "accept" and
            step["side_effect_class"] in Vanta.allowed_side_effect_classes() and
            Vanta.VerifierRuntime.missing_evidence_fields(evidence) == [] and
            reversible_commit_auditable?(step, evidence)
        end)
    end
  end

  defp rollback_memory_boundary?(journal) do
    journal["rollback_status"] in @rollback_statuses and
      Map.get(journal, "memory_write_effects") == []
  end

  defp reversible_commit_auditable?(
         %{
           "action_type" => "apply_reversible_structured_edit",
           "side_effect_class" => "REVERSIBLE"
         },
         evidence
       ) do
    metadata = get_in(evidence, ["observation", "backup_metadata"])

    is_map(metadata) and
      metadata["backup_policy"] == "fixture_backup_restore" and
      present?(metadata["path"]) and
      present?(metadata["backup_path"]) and
      present?(metadata["metadata_path"]) and
      present?(metadata["before_hash"]) and
      present?(metadata["after_hash"]) and
      present?(metadata["backup_hash"]) and
      present?(metadata["diff_hash"])
  end

  defp reversible_commit_auditable?(%{"side_effect_class" => "REVERSIBLE"}, evidence) do
    evidence
    |> get_in(["observation", "backup_metadata"])
    |> is_map()
  end

  defp reversible_commit_auditable?(_step, _evidence), do: true

  defp artifact_index(artifacts, key, id_field) do
    artifacts
    |> artifact_list(key)
    |> Map.new(&{&1[id_field], &1})
  end

  defp artifact_list(artifacts, key) do
    Map.get(artifacts, key) || Map.get(artifacts, Atom.to_string(key)) || []
  end

  defp journal_artifacts({journal, artifacts}), do: {journal, artifacts}

  defp journal_artifacts(%{"journal" => journal, "artifacts" => artifacts}),
    do: {journal, artifacts}

  defp journal_artifacts(%{journal: journal, artifacts: artifacts}), do: {journal, artifacts}
  defp journal_artifacts(journal), do: {journal, %{}}

  defp commit_integrity_score(entries) do
    committed =
      Enum.filter(entries, fn {journal, _artifacts} -> journal["commit_status"] == "committed" end)

    if committed == [] do
      0.0
    else
      Enum.count(committed, fn {journal, artifacts} ->
        commit_integrity_complete?(journal, artifacts)
      end) / length(committed)
    end
  end

  defp non_empty_list?(value), do: is_list(value) and value != []
  defp present?(value), do: is_binary(value) and String.trim(value) != ""
end
