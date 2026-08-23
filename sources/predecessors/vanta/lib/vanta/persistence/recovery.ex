defmodule Vanta.Persistence.Recovery do
  @moduledoc """
  Fixture-local prepare and restart recovery protocol.
  """

  alias Vanta.{Hash, PathGuard, Persistence}

  def prepare(context, workspace, step, pre_state_hash, opts \\ []) do
    path = get_in(step, ["action_payload", "path"])

    with :ok <- require_reversible(step),
         :ok <- require_path(path),
         {:ok, abs_path} <- PathGuard.safe_resolve(workspace, path),
         :ok <- require_file(abs_path) do
      backup_dir = PathGuard.resolve!(workspace, ".vanta_persistence_backups")
      File.mkdir_p!(backup_dir)
      safe_step = String.replace(step["step_id"], ~r/[^A-Za-z0-9_.-]/, "_")
      backup_path = Path.join(backup_dir, safe_step <> ".bak")
      metadata_path = Path.join(backup_dir, safe_step <> ".metadata.json")
      pre_effect_hash = Hash.file_hash(abs_path)
      File.cp!(abs_path, backup_path)

      backup_metadata = %{
        "backup_policy" => "fixture_backup_restore",
        "path" => path,
        "backup_path" => PathGuard.relative(workspace, backup_path),
        "metadata_path" => PathGuard.relative(workspace, metadata_path),
        "backup_hash" => Hash.file_hash(backup_path),
        "pre_effect_hash" => pre_effect_hash
      }

      File.write!(metadata_path, Jason.encode!(backup_metadata, pretty: true))

      record = %{
        "recovery_id" => "recovery_#{step["step_id"]}",
        "episode_id" => step["episode_id"],
        "step_id" => step["step_id"],
        "status" => "prepared",
        "crash_window" => Keyword.get(opts, :crash_window, "none") |> to_string(),
        "target_identity" => %{
          "workspace_scope" => "fixture_local",
          "path" => path,
          "pre_effect_hash" => pre_effect_hash
        },
        "pre_state_hash" => pre_state_hash,
        "backup_metadata" => backup_metadata,
        "effect_applied" => false,
        "rollback_status" => "not_started"
      }

      Persistence.record_prepared_effect(context, record)
    end
  end

  def prepare_committable(context, workspace, step, pre_state_hash, opts \\ []) do
    identity = get_in(step, ["action_payload", "target_identity"])
    target_path = identity && identity["committed_path"]

    with :ok <- require_committable(step),
         :ok <- require_path(target_path),
         {:ok, target_abs} <- PathGuard.safe_resolve(workspace, target_path) do
      backup_dir = PathGuard.resolve!(workspace, ".vanta_persistence_backups")
      File.mkdir_p!(backup_dir)
      safe_step = String.replace(step["step_id"], ~r/[^A-Za-z0-9_.-]/, "_")
      backup_path = Path.join(backup_dir, safe_step <> ".bak")
      metadata_path = Path.join(backup_dir, safe_step <> ".metadata.json")
      target_preexisting = File.regular?(target_abs)
      pre_effect_hash = if target_preexisting, do: Hash.file_hash(target_abs), else: "missing"

      backup_hash =
        if target_preexisting do
          File.cp!(target_abs, backup_path)
          Hash.file_hash(backup_path)
        else
          nil
        end

      backup_metadata = %{
        "backup_policy" => "fixture_commit_restore",
        "path" => target_path,
        "backup_path" =>
          if(target_preexisting, do: PathGuard.relative(workspace, backup_path), else: nil),
        "metadata_path" => PathGuard.relative(workspace, metadata_path),
        "backup_hash" => backup_hash,
        "pre_effect_hash" => pre_effect_hash,
        "target_preexisting" => target_preexisting
      }

      File.write!(metadata_path, Jason.encode!(backup_metadata, pretty: true))

      record = %{
        "recovery_id" => "recovery_#{step["step_id"]}",
        "episode_id" => step["episode_id"],
        "step_id" => step["step_id"],
        "status" => "prepared",
        "crash_window" => Keyword.get(opts, :crash_window, "none") |> to_string(),
        "target_identity" =>
          identity
          |> Map.put("pre_effect_hash", pre_effect_hash)
          |> Map.put("candidate_hash", get_in(step, ["action_payload", "candidate_hash"]))
          |> Map.put(
            "approval_record_ref",
            get_in(step, ["action_payload", "approval_record_ref"])
          ),
        "pre_state_hash" => pre_state_hash,
        "backup_metadata" => backup_metadata,
        "effect_applied" => false,
        "rollback_status" => "not_started"
      }

      Persistence.record_prepared_effect(context, record)
    end
  end

  def mark_effect_applied(
        context,
        recovery_record,
        crash_window \\ "after_effect_before_db_commit"
      ) do
    Persistence.record_recovery_status(
      context,
      recovery_record["recovery_id"],
      "effect_applied",
      %{
        "effect_applied" => true,
        "crash_window" => crash_window,
        "rollback_status" => "available"
      }
    )
  end

  def recover_episode(context, episode_id, workspace, opts \\ []) do
    injection = Keyword.get(opts, :failure_injection)

    with {:ok, episode} <- Persistence.load_episode(context, episode_id),
         {:ok, records} <- Persistence.load_recovery_records(context, episode_id) do
      records
      |> Enum.reject(&(&1["status"] in ~w(commit_completed abort_completed rolled_back)))
      |> Enum.reduce_while({:ok, []}, fn record, {:ok, outcomes} ->
        case recover_record(context, episode, record, workspace, injection) do
          {:ok, outcome} -> {:cont, {:ok, outcomes ++ [outcome]}}
          {:error, {:injected_crash, _point} = reason} -> {:halt, {:error, reason}}
          {:error, reason} -> {:halt, {:error, reason}}
        end
      end)
      |> case do
        {:ok, outcomes} -> {:ok, %{episode_id: episode_id, outcomes: outcomes}}
        {:error, _reason} = error -> error
      end
    end
  end

  defp recover_record(context, %{"lifecycle" => "committed"}, record, _workspace, _injection) do
    Persistence.record_recovery_status(
      context,
      record["recovery_id"],
      "commit_completed",
      %{"rollback_status" => "available"}
    )
  end

  defp recover_record(
         context,
         _episode,
         %{"effect_applied" => false} = record,
         workspace,
         _injection
       ) do
    if target_matches_pre_effect?(workspace, record) do
      Persistence.record_recovery_status(
        context,
        record["recovery_id"],
        "abort_completed",
        %{"rollback_status" => "not_started"}
      )
    else
      require_manual_recovery(context, record, "prepared_target_changed")
    end
  end

  defp recover_record(context, _episode, record, workspace, injection) do
    cond do
      target_matches_pre_effect?(workspace, record) ->
        Persistence.record_recovery_status(
          context,
          record["recovery_id"],
          "rolled_back",
          %{"rollback_status" => "completed"}
        )

      injection == :before_rollback ->
        with {:ok, _record} <-
               Persistence.record_recovery_status(
                 context,
                 record["recovery_id"],
                 "rollback_pending",
                 %{"rollback_status" => "pending", "crash_window" => "before_rollback"}
               ) do
          {:error, {:injected_crash, :before_rollback}}
        end

      backup_valid?(workspace, record) ->
        with {:ok, in_progress} <-
               Persistence.record_recovery_status(
                 context,
                 record["recovery_id"],
                 "rollback_in_progress",
                 %{"rollback_status" => "in_progress", "crash_window" => "during_rollback"}
               ),
             :ok <- restore_backup(workspace, in_progress) do
          if injection == :during_rollback do
            {:error, {:injected_crash, :during_rollback}}
          else
            Persistence.record_recovery_status(
              context,
              record["recovery_id"],
              "rolled_back",
              %{"rollback_status" => "completed"}
            )
          end
        end

      true ->
        require_manual_recovery(context, record, "backup_missing_or_corrupt")
    end
  end

  defp restore_backup(workspace, record) do
    metadata = record["backup_metadata"]
    target = PathGuard.resolve!(workspace, metadata["path"])

    if metadata["target_preexisting"] == false do
      File.rm(target)

      if File.exists?(target), do: {:error, :rollback_target_still_exists}, else: :ok
    else
      backup = PathGuard.resolve!(workspace, metadata["backup_path"])
      File.cp!(backup, target)

      if Hash.file_hash(target) == metadata["pre_effect_hash"] do
        :ok
      else
        {:error, :rollback_hash_mismatch}
      end
    end
  end

  defp target_matches_pre_effect?(workspace, record) do
    metadata = record["backup_metadata"]

    if metadata["target_preexisting"] == false do
      with path when is_binary(path) <- metadata["path"],
           {:ok, abs_path} <- PathGuard.safe_resolve(workspace, path) do
        not File.exists?(abs_path)
      else
        _other -> false
      end
    else
      with path when is_binary(path) <- metadata["path"],
           {:ok, abs_path} <- PathGuard.safe_resolve(workspace, path),
           true <- File.regular?(abs_path) do
        Hash.file_hash(abs_path) == metadata["pre_effect_hash"]
      else
        _other -> false
      end
    end
  end

  defp backup_valid?(workspace, record) do
    metadata = record["backup_metadata"]

    if metadata["target_preexisting"] == false do
      true
    else
      with path when is_binary(path) <- metadata["backup_path"],
           {:ok, abs_path} <- PathGuard.safe_resolve(workspace, path),
           true <- File.regular?(abs_path) do
        Hash.file_hash(abs_path) == metadata["backup_hash"] and
          metadata["backup_hash"] == metadata["pre_effect_hash"]
      else
        _other -> false
      end
    end
  end

  defp require_manual_recovery(context, record, reason) do
    Persistence.record_recovery_status(
      context,
      record["recovery_id"],
      "recovery_required",
      %{"rollback_status" => "failed", "crash_window" => reason}
    )
  end

  defp require_reversible(%{"side_effect_class" => "REVERSIBLE"}), do: :ok
  defp require_reversible(_step), do: {:error, :not_reversible}

  defp require_committable(%{
         "action_type" => "commit_fixture_document_candidate",
         "side_effect_class" => "COMMITTABLE",
         "rollback_policy" => "fixture_commit_restore"
       }),
       do: :ok

  defp require_committable(_step), do: {:error, :not_fixture_local_committable}

  defp require_path(path) when is_binary(path), do: :ok
  defp require_path(_path), do: {:error, :missing_target_path}

  defp require_file(path) do
    if File.regular?(path), do: :ok, else: {:error, :target_not_found}
  end
end
