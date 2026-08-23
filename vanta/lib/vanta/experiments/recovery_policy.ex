defmodule Vanta.RecoveryPolicy do
  @moduledoc """
  Deterministic fixture-local recovery policies for Phase 4.
  """

  alias Vanta.{EvaluationHarness, Hash, PathGuard, Schema}

  @policies ~w(
    reconstruct_rollback_from_diff
    repair_audit_refs
    produce_compensation_record
  )

  def policies, do: @policies

  def apply("reconstruct_rollback_from_diff", workspace, context) do
    with {:ok, step, observation} <- failed_action(context, "apply_reversible_patch"),
         {:ok, restored_path} <- restore_from_payload(workspace, step) do
      record =
        recovery_record("reconstruct_rollback_from_diff", true, %{
          "restored_path" => restored_path,
          "before_hash" => observation["before_hash"],
          "after_hash" => observation["after_hash"],
          "recovered_hash" => Hash.file_hash(PathGuard.resolve!(workspace, restored_path))
        })

      {:ok, write_recovery_artifact(workspace, "rollback_reconstruction.json", record)}
    else
      {:error, reason} ->
        {:ok,
         failed_record(
           workspace,
           "rollback_reconstruction.json",
           "reconstruct_rollback_from_diff",
           reason
         )}
    end
  end

  def apply("repair_audit_refs", workspace, context) do
    with {:ok, step, _observation} <- failed_action(context, "validate_artifact"),
         payload <- step["action_payload"] || %{},
         path when is_binary(path) <- payload["path"],
         artifacts_path when is_binary(artifacts_path) <- payload["artifacts_path"] do
      journal = workspace |> PathGuard.resolve!(path) |> Schema.load_json!()
      artifacts = workspace |> PathGuard.resolve!(artifacts_path) |> Schema.load_json!()
      repaired = repair_refs(journal, artifacts)
      audit = EvaluationHarness.audit_result(repaired, artifacts)

      record =
        recovery_record("repair_audit_refs", audit["complete"], %{
          "journal_path" => path,
          "artifacts_path" => artifacts_path,
          "repaired_journal" => repaired,
          "audit" => audit
        })

      {:ok, write_recovery_artifact(workspace, "repaired_audit.json", record)}
    else
      nil ->
        {:ok,
         failed_record(
           workspace,
           "repaired_audit.json",
           "repair_audit_refs",
           :missing_audit_payload
         )}

      {:error, reason} ->
        {:ok, failed_record(workspace, "repaired_audit.json", "repair_audit_refs", reason)}
    end
  end

  def apply("produce_compensation_record", workspace, context) do
    with {:ok, _step, observation} <- failed_action(context, "record_compensable_action") do
      record =
        recovery_record("produce_compensation_record", true, %{
          "receipt_id" => observation["receipt_id"],
          "compensation_status" => "compensation_completed",
          "compensation_hint" => observation["compensation_hint"],
          "external_action_executed" => false
        })

      {:ok, write_recovery_artifact(workspace, "compensation_record.json", record)}
    else
      {:error, reason} ->
        {:ok,
         failed_record(
           workspace,
           "compensation_record.json",
           "produce_compensation_record",
           reason
         )}
    end
  end

  def apply(policy, workspace, _context) do
    {:ok, failed_record(workspace, "no_recovery.json", policy, :policy_not_allowlisted)}
  end

  defp failed_action(context, action_type) do
    result = Map.fetch!(context, :failed_result)

    step =
      result.steps
      |> Enum.reverse()
      |> Enum.find(&(&1["action_type"] == action_type))

    observation =
      result.observations
      |> Enum.reverse()
      |> Enum.find(&(&1["kind"] == action_type or &1["validation"] == "episode_audit_refs"))

    cond do
      is_nil(step) -> {:error, :missing_failed_step}
      is_nil(observation) -> {:error, :missing_failed_observation}
      true -> {:ok, step, observation}
    end
  end

  defp restore_from_payload(workspace, step) do
    payload = step["action_payload"] || %{}

    with path when is_binary(path) <- payload["path"],
         find when is_binary(find) <- payload["find"],
         replace when is_binary(replace) <- payload["replace"] do
      abs_path = PathGuard.resolve!(workspace, path)
      content = File.read!(abs_path)

      restored =
        if String.contains?(content, replace) do
          String.replace(content, replace, find, global: false)
        else
          content
        end

      File.write!(abs_path, restored)
      {:ok, path}
    else
      _other -> {:error, :missing_reversible_patch_payload}
    end
  end

  defp repair_refs(journal, artifacts) do
    evidence_refs =
      artifacts
      |> Map.get("evidence_packets", [])
      |> Enum.map(& &1["evidence_id"])
      |> Enum.reject(&is_nil/1)

    verifier_refs =
      artifacts
      |> Map.get("verifier_outputs", [])
      |> Enum.map(& &1["verifier_output_id"])
      |> Enum.reject(&is_nil/1)

    journal
    |> Map.put("evidence_refs", evidence_refs)
    |> Map.put("verifier_output_refs", verifier_refs)
  end

  defp recovery_record(policy, success?, details) do
    %{
      "schema_version" => Vanta.schema_version(),
      "policy" => policy,
      "success" => success?,
      "details" => details
    }
  end

  defp failed_record(workspace, file_name, policy, reason) do
    write_recovery_artifact(
      workspace,
      file_name,
      recovery_record(policy, false, %{"error" => inspect(reason)})
    )
  end

  defp write_recovery_artifact(workspace, file_name, record) do
    recovery_dir = PathGuard.resolve!(workspace, ".vanta_recovery")
    File.mkdir_p!(recovery_dir)

    path = Path.join(recovery_dir, file_name)
    File.write!(path, Jason.encode!(record, pretty: true))

    record
    |> Map.put("artifact_path", PathGuard.relative(workspace, path))
  end
end
