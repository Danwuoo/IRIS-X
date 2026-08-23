defmodule Vanta.Persistence.MemoryAdapter do
  @moduledoc """
  In-memory Persistence v0 adapter used for fast tests and compatibility.
  """

  @behaviour Vanta.Persistence
  alias Vanta.{Hash, Persistence, Schema}

  @recoverable ~w(running prepared rollback_pending recovery_required)

  @impl true
  def open(_opts) do
    Agent.start_link(fn ->
      %{sequence: 0, episodes: %{}, artifacts: %{}, order: [], recoveries: %{}, commits: %{}}
    end)
  end

  @impl true
  def close(pid) do
    if Process.alive?(pid), do: Agent.stop(pid)
    :ok
  end

  @impl true
  def create_episode(pid, manifest) do
    expected_task_id = manifest["task_id"]

    Agent.get_and_update(pid, fn state ->
      case state.episodes[manifest["episode_id"]] do
        nil ->
          {sequence, state} = next_sequence(state)
          manifest = %{manifest | "created_sequence" => sequence, "updated_sequence" => sequence}
          manifest = Schema.validate!("persistence_manifest", manifest)
          {{:ok, manifest}, put_in(state, [:episodes, manifest["episode_id"]], manifest)}

        %{"task_id" => ^expected_task_id} = existing ->
          {{:ok, existing}, state}

        _existing ->
          {{:error, :episode_identity_conflict}, state}
      end
    end)
  end

  @impl true
  def append_immutable_artifact(pid, type, payload, opts) do
    Agent.get_and_update(pid, fn state ->
      {artifact, state} = append_artifact(state, type, payload, opts)
      {{:ok, artifact}, state}
    end)
  rescue
    error -> {:error, {:artifact_write_failed, Exception.message(error)}}
  end

  @impl true
  def record_prepared_effect(pid, attrs) do
    Agent.get_and_update(pid, fn state ->
      {sequence, state} = next_sequence(state)
      record = Persistence.build_recovery_record(attrs, sequence)
      episode_id = record["episode_id"]

      state =
        state
        |> put_in([:recoveries, record["recovery_id"]], record)
        |> update_episode(episode_id, "prepared", %{
          "recovery_status" => "prepared",
          "updated_sequence" => sequence
        })

      {{:ok, record}, state}
    end)
  rescue
    error -> {:error, {:prepare_failed, Exception.message(error)}}
  end

  @impl true
  def record_recovery_status(pid, recovery_id, status, attrs) do
    Agent.get_and_update(pid, fn state ->
      case state.recoveries[recovery_id] do
        nil ->
          {{:error, :recovery_record_not_found}, state}

        record ->
          {sequence, state} = next_sequence(state)

          record =
            record
            |> Map.merge(stringify_keys(attrs))
            |> Map.put("status", status)
            |> Map.put("updated_sequence", sequence)
            |> rehash_recovery()

          episode_status = lifecycle_for_recovery(status)

          state =
            state
            |> put_in([:recoveries, recovery_id], record)
            |> maybe_update_episode(record["episode_id"], episode_status, %{
              "recovery_status" => status,
              "rollback_status" => record["rollback_status"],
              "updated_sequence" => sequence
            })

          {{:ok, record}, state}
      end
    end)
  end

  @impl true
  def set_episode_status(pid, episode_id, status, attrs) do
    Agent.get_and_update(pid, fn state ->
      if state.episodes[episode_id] do
        {sequence, state} = next_sequence(state)
        attrs = attrs |> stringify_keys() |> Map.put("updated_sequence", sequence)
        state = update_episode(state, episode_id, status, attrs)
        {{:ok, state.episodes[episode_id]}, state}
      else
        {{:error, :episode_not_found}, state}
      end
    end)
  end

  @impl true
  def commit_logical(pid, request) do
    Agent.get_and_update(pid, fn state ->
      key = request["idempotency_key"]
      request_hash = request["request_hash"]

      case state.commits[key] do
        %{"request_hash" => ^request_hash, "result" => result} ->
          {{:ok, Map.put(result, "idempotent_replay", true)}, state}

        %{} ->
          {{:error, :idempotency_conflict}, state}

        nil ->
          try do
            {result, state} = do_commit(state, request)
            {{:ok, result}, state}
          rescue
            error -> {{:error, {:transaction_rolled_back, Exception.message(error)}}, state}
          end
      end
    end)
  end

  @impl true
  def lookup_logical_commit(pid, key, request_hash) do
    Agent.get(pid, fn state ->
      case state.commits[key] do
        nil -> :not_found
        %{"request_hash" => ^request_hash, "result" => result} -> {:ok, result}
        _commit -> {:error, :idempotency_conflict}
      end
    end)
  end

  @impl true
  def load_episode(pid, episode_id) do
    Agent.get(pid, fn state ->
      case state.episodes[episode_id] do
        nil -> {:error, :episode_not_found}
        episode -> {:ok, episode}
      end
    end)
  end

  @impl true
  def load_artifact(pid, artifact_id) do
    Agent.get(pid, fn state ->
      case state.artifacts[artifact_id] do
        nil -> {:error, :artifact_not_found}
        artifact -> {:ok, artifact}
      end
    end)
  end

  @impl true
  def load_artifacts(pid, episode_id) do
    Agent.get(pid, fn state ->
      artifacts =
        state.order
        |> Enum.map(&state.artifacts[&1])
        |> Enum.filter(&(&1["episode_id"] == episode_id))

      {:ok, artifacts}
    end)
  end

  @impl true
  def load_recovery_records(pid, episode_id) do
    Agent.get(pid, fn state ->
      records =
        state.recoveries
        |> Map.values()
        |> Enum.filter(&(&1["episode_id"] == episode_id))
        |> Enum.sort_by(& &1["created_sequence"])

      {:ok, records}
    end)
  end

  @impl true
  def list_recoverable_episodes(pid) do
    Agent.get(pid, fn state ->
      {:ok,
       state.episodes
       |> Map.values()
       |> Enum.filter(&(&1["lifecycle"] in @recoverable))
       |> Enum.sort_by(& &1["created_sequence"])}
    end)
  end

  @impl true
  def verify_artifact_integrity(pid, artifact_id) do
    with {:ok, artifact} <- load_artifact(pid, artifact_id),
         true <- artifact["content_hash"] == Hash.canonical_json_hash(artifact["payload"]),
         :ok <- Schema.validate("persisted_artifact", artifact),
         :ok <- Persistence.validate_typed_payload(artifact["artifact_type"], artifact["payload"]) do
      :ok
    else
      false -> {:error, :content_hash_mismatch}
      {:error, reason} -> {:error, reason}
    end
  end

  defp do_commit(state, request) do
    episode_id = request["episode_id"]

    {step_artifacts, state} = append_many(state, "execution_step", request["steps"], episode_id)

    {approval_artifacts, state} =
      append_many(state, "approval_record", request["approval_records"], episode_id)

    {evidence_artifacts, state} =
      append_many(state, "evidence_packet", request["evidence_packets"], episode_id)

    {verifier_artifacts, state} =
      append_many(state, "verifier_output", request["verifier_outputs"], episode_id)

    {state_artifact, state} =
      append_artifact(state, "canonical_state", request["state"], episode_id: episode_id)

    if request["failure_injection"] == "transaction_rollback_after_state" do
      raise "injected transaction rollback"
    end

    {journal_artifact, state} =
      append_artifact(state, "episode_journal", request["journal"], episode_id: episode_id)

    {sequence, state} = next_sequence(state)

    result = %{
      "episode_id" => episode_id,
      "idempotency_key" => request["idempotency_key"],
      "request_hash" => request["request_hash"],
      "state_artifact_id" => state_artifact["artifact_id"],
      "journal_artifact_id" => journal_artifact["artifact_id"],
      "artifact_ids" =>
        Enum.map(
          step_artifacts ++
            approval_artifacts ++
            evidence_artifacts ++
            verifier_artifacts ++
            [state_artifact, journal_artifact],
          & &1["artifact_id"]
        ),
      "committed_sequence" => sequence,
      "idempotent_replay" => false
    }

    commit = %{
      "episode_id" => episode_id,
      "request_hash" => request["request_hash"],
      "result" => result,
      "created_sequence" => sequence
    }

    episode = state.episodes[episode_id]

    episode =
      episode
      |> Map.put("lifecycle", "committed")
      |> Map.put("accepted_state_artifact_id", state_artifact["artifact_id"])
      |> Map.put("journal_artifact_id", journal_artifact["artifact_id"])
      |> Map.put("rollback_status", request["journal"]["rollback_status"])
      |> Map.put("recovery_status", "not_required")
      |> Map.put(
        "idempotency_keys",
        Enum.uniq(episode["idempotency_keys"] ++ [request["idempotency_key"]])
      )
      |> Map.put("updated_sequence", sequence)
      |> then(&Schema.validate!("persistence_manifest", &1))

    state =
      state
      |> put_in([:episodes, episode_id], episode)
      |> put_in([:commits, request["idempotency_key"]], commit)

    {result, state}
  end

  defp append_many(state, type, values, episode_id) do
    Enum.map_reduce(values || [], state, fn payload, acc ->
      append_artifact(acc, type, payload, episode_id: episode_id)
    end)
  end

  defp append_artifact(state, type, payload, opts) do
    {sequence, state} = next_sequence(state)
    episode_id = Keyword.fetch!(opts, :episode_id)
    artifact = Persistence.build_artifact(type, episode_id, payload, sequence, opts)
    id = artifact["artifact_id"]

    {artifact,
     state
     |> put_in([:artifacts, id], artifact)
     |> Map.update!(:order, &(&1 ++ [id]))}
  end

  defp next_sequence(state) do
    sequence = state.sequence + 1
    {sequence, %{state | sequence: sequence}}
  end

  defp update_episode(state, episode_id, status, attrs) do
    update_in(state, [:episodes, episode_id], fn episode ->
      episode
      |> Map.merge(stringify_keys(attrs))
      |> Map.put("lifecycle", status)
      |> then(&Schema.validate!("persistence_manifest", &1))
    end)
  end

  defp maybe_update_episode(state, _episode_id, nil, _attrs), do: state

  defp maybe_update_episode(state, episode_id, status, attrs),
    do: update_episode(state, episode_id, status, attrs)

  defp lifecycle_for_recovery("commit_completed"), do: "committed"
  defp lifecycle_for_recovery("abort_completed"), do: "aborted"
  defp lifecycle_for_recovery("rollback_pending"), do: "rollback_pending"
  defp lifecycle_for_recovery("rollback_in_progress"), do: "rollback_pending"
  defp lifecycle_for_recovery("rolled_back"), do: "rolled_back"
  defp lifecycle_for_recovery("recovery_required"), do: "recovery_required"
  defp lifecycle_for_recovery(_status), do: nil

  defp rehash_recovery(record) do
    hash = record |> Map.drop(["content_hash"]) |> Hash.canonical_json_hash()

    record
    |> Map.put("content_hash", hash)
    |> then(&Schema.validate!("recovery_record", &1))
  end

  defp stringify_keys(map) when is_map(map) do
    Map.new(map, fn {key, value} -> {to_string(key), stringify_keys(value)} end)
  end

  defp stringify_keys(list) when is_list(list), do: Enum.map(list, &stringify_keys/1)
  defp stringify_keys(value), do: value
end
