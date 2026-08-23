defmodule Vanta.Persistence.SQLiteAdapter do
  @moduledoc """
  Direct Exqlite adapter for Fixture-Local SQLite Persistence v0.
  """

  @behaviour Vanta.Persistence

  alias Exqlite.Sqlite3
  alias Vanta.{Hash, Persistence, Schema}

  @recoverable ~w(running prepared rollback_pending recovery_required)

  @schema_sql """
  CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS episodes (
    episode_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    lifecycle TEXT NOT NULL,
    runtime_manifest_json TEXT NOT NULL,
    runtime_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    hash_policy_version TEXT NOT NULL,
    accepted_state_artifact_id TEXT,
    journal_artifact_id TEXT,
    rollback_status TEXT NOT NULL,
    recovery_status TEXT NOT NULL,
    idempotency_keys_json TEXT NOT NULL,
    created_sequence INTEGER NOT NULL,
    updated_sequence INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_sequence INTEGER NOT NULL UNIQUE,
    provenance_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(episode_id) REFERENCES episodes(episode_id)
  );

  CREATE TABLE IF NOT EXISTS recovery_records (
    recovery_id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    status TEXT NOT NULL,
    crash_window TEXT NOT NULL,
    target_identity_json TEXT NOT NULL,
    pre_state_hash TEXT NOT NULL,
    backup_metadata_json TEXT NOT NULL,
    effect_applied INTEGER NOT NULL,
    rollback_status TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_sequence INTEGER NOT NULL,
    updated_sequence INTEGER NOT NULL,
    FOREIGN KEY(episode_id) REFERENCES episodes(episode_id)
  );

  CREATE TABLE IF NOT EXISTS logical_commits (
    idempotency_key TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_sequence INTEGER NOT NULL,
    FOREIGN KEY(episode_id) REFERENCES episodes(episode_id)
  );
  """

  @impl true
  def open(opts) do
    path = Keyword.fetch!(opts, :path)
    busy_timeout = Keyword.get(opts, :busy_timeout, 250)

    with :ok <- ensure_parent(path), {:ok, conn} <- Sqlite3.open(path) do
      result =
        with :ok <- normalize(Sqlite3.set_busy_timeout(conn, busy_timeout)),
             :ok <- exec_script(conn, "PRAGMA foreign_keys = ON;"),
             :ok <- exec_script(conn, "PRAGMA journal_mode = WAL;"),
             :ok <- exec_script(conn, @schema_sql),
             :ok <- initialize_metadata(conn),
             :ok <- verify_metadata(conn) do
          {:ok, %{conn: conn, path: path, busy_timeout: busy_timeout}}
        end

      case result do
        {:ok, _handle} = ok ->
          ok

        {:error, _reason} = error ->
          _ = Sqlite3.close(conn)
          error
      end
    end
  end

  @impl true
  def close(%{conn: conn}), do: normalize(Sqlite3.close(conn))

  @impl true
  def create_episode(handle, manifest) do
    expected_task_id = manifest["task_id"]

    transaction(handle, fn conn ->
      case fetch_episode(conn, manifest["episode_id"]) do
        {:ok, %{"task_id" => ^expected_task_id} = existing} ->
          {:ok, existing}

        {:ok, _existing} ->
          {:error, :episode_identity_conflict}

        {:error, :episode_not_found} ->
          with {:ok, sequence} <- next_sequence(conn) do
            manifest =
              manifest
              |> Map.put("created_sequence", sequence)
              |> Map.put("updated_sequence", sequence)
              |> then(&Schema.validate!("persistence_manifest", &1))

            params = [
              manifest["episode_id"],
              manifest["task_id"],
              manifest["lifecycle"],
              encode(manifest["runtime_manifest"]),
              manifest["runtime_version"],
              manifest["schema_version"],
              manifest["hash_policy_version"],
              manifest["accepted_state_artifact_id"],
              manifest["journal_artifact_id"],
              manifest["rollback_status"],
              manifest["recovery_status"],
              encode(manifest["idempotency_keys"]),
              sequence,
              sequence
            ]

            with :ok <-
                   run(
                     conn,
                     """
                     INSERT INTO episodes (
                       episode_id, task_id, lifecycle, runtime_manifest_json,
                       runtime_version, schema_version, hash_policy_version,
                       accepted_state_artifact_id, journal_artifact_id,
                       rollback_status, recovery_status, idempotency_keys_json,
                       created_sequence, updated_sequence
                     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                     """,
                     params
                   ) do
              {:ok, manifest}
            end
          end
      end
    end)
  end

  @impl true
  def append_immutable_artifact(handle, type, payload, opts) do
    transaction(handle, fn conn -> insert_artifact(conn, type, payload, opts) end)
  end

  @impl true
  def record_prepared_effect(handle, attrs) do
    transaction(handle, fn conn ->
      with {:ok, sequence} <- next_sequence(conn) do
        record = Persistence.build_recovery_record(attrs, sequence)

        with :ok <- insert_recovery(conn, record),
             :ok <-
               update_episode_row(conn, record["episode_id"], "prepared", %{
                 "recovery_status" => "prepared",
                 "updated_sequence" => sequence
               }) do
          {:ok, record}
        end
      end
    end)
  end

  @impl true
  def record_recovery_status(handle, recovery_id, status, attrs) do
    transaction(handle, fn conn ->
      with {:ok, existing} <- fetch_recovery(conn, recovery_id),
           {:ok, sequence} <- next_sequence(conn) do
        record =
          existing
          |> Map.merge(stringify_keys(attrs))
          |> Map.put("status", status)
          |> Map.put("updated_sequence", sequence)
          |> rehash_recovery()

        with :ok <-
               run(
                 conn,
                 """
                 UPDATE recovery_records SET
                   status = ?, crash_window = ?, target_identity_json = ?,
                   pre_state_hash = ?, backup_metadata_json = ?, effect_applied = ?,
                   rollback_status = ?, content_hash = ?, updated_sequence = ?
                 WHERE recovery_id = ?
                 """,
                 [
                   record["status"],
                   record["crash_window"],
                   encode(record["target_identity"]),
                   record["pre_state_hash"],
                   encode(record["backup_metadata"]),
                   bool_int(record["effect_applied"]),
                   record["rollback_status"],
                   record["content_hash"],
                   record["updated_sequence"],
                   recovery_id
                 ]
               ),
             :ok <- maybe_update_episode_for_recovery(conn, record, sequence) do
          {:ok, record}
        end
      end
    end)
  end

  @impl true
  def set_episode_status(handle, episode_id, status, attrs) do
    transaction(handle, fn conn ->
      with {:ok, sequence} <- next_sequence(conn),
           :ok <-
             update_episode_row(
               conn,
               episode_id,
               status,
               attrs |> stringify_keys() |> Map.put("updated_sequence", sequence)
             ),
           {:ok, episode} <- fetch_episode(conn, episode_id) do
        {:ok, episode}
      end
    end)
  end

  @impl true
  def commit_logical(handle, request) do
    transaction(handle, fn conn ->
      key = request["idempotency_key"]
      request_hash = request["request_hash"]

      case fetch_commit(conn, key) do
        {:ok, %{"request_hash" => ^request_hash, "result" => result}} ->
          {:ok, Map.put(result, "idempotent_replay", true)}

        {:ok, _commit} ->
          {:error, :idempotency_conflict}

        {:error, :logical_commit_not_found} ->
          do_commit(conn, request)
      end
    end)
  end

  @impl true
  def lookup_logical_commit(%{conn: conn}, key, request_hash) do
    case fetch_commit(conn, key) do
      {:error, :logical_commit_not_found} -> :not_found
      {:ok, %{"request_hash" => ^request_hash, "result" => result}} -> {:ok, result}
      {:ok, _commit} -> {:error, :idempotency_conflict}
      {:error, _reason} = error -> error
    end
  end

  @impl true
  def load_episode(%{conn: conn}, episode_id), do: fetch_episode(conn, episode_id)

  @impl true
  def load_artifact(%{conn: conn}, artifact_id), do: fetch_artifact(conn, artifact_id)

  @impl true
  def load_artifacts(%{conn: conn}, episode_id) do
    with {:ok, rows} <-
           query_all(
             conn,
             """
             SELECT artifact_id, artifact_type, schema_version, episode_id,
                    content_hash, created_sequence, provenance_json, payload_json
             FROM artifacts WHERE episode_id = ? ORDER BY created_sequence ASC
             """,
             [episode_id]
           ) do
      {:ok, Enum.map(rows, &artifact_from_row/1)}
    end
  end

  @impl true
  def load_recovery_records(%{conn: conn}, episode_id) do
    with {:ok, rows} <-
           query_all(
             conn,
             """
             SELECT recovery_id, episode_id, step_id, status, crash_window,
                    target_identity_json, pre_state_hash, backup_metadata_json,
                    effect_applied, rollback_status, content_hash,
                    created_sequence, updated_sequence
             FROM recovery_records WHERE episode_id = ? ORDER BY created_sequence ASC
             """,
             [episode_id]
           ) do
      {:ok, Enum.map(rows, &recovery_from_row/1)}
    end
  end

  @impl true
  def list_recoverable_episodes(%{conn: conn}) do
    placeholders = Enum.map_join(@recoverable, ",", fn _ -> "?" end)

    with {:ok, rows} <-
           query_all(
             conn,
             """
             SELECT episode_id FROM episodes
             WHERE lifecycle IN (#{placeholders})
             ORDER BY created_sequence ASC
             """,
             @recoverable
           ) do
      rows
      |> Enum.map(&hd/1)
      |> Enum.reduce_while({:ok, []}, fn episode_id, {:ok, acc} ->
        case fetch_episode(conn, episode_id) do
          {:ok, episode} -> {:cont, {:ok, acc ++ [episode]}}
          {:error, reason} -> {:halt, {:error, reason}}
        end
      end)
    end
  end

  @impl true
  def verify_artifact_integrity(handle, artifact_id) do
    with {:ok, artifact} <- load_artifact(handle, artifact_id),
         :ok <- compatible_artifact_version(artifact),
         true <- artifact["content_hash"] == Hash.canonical_json_hash(artifact["payload"]),
         :ok <- Schema.validate("persisted_artifact", artifact),
         :ok <- Persistence.validate_typed_payload(artifact["artifact_type"], artifact["payload"]) do
      :ok
    else
      false -> {:error, :content_hash_mismatch}
      {:error, _reason} = error -> error
    end
  end

  defp do_commit(conn, request) do
    episode_id = request["episode_id"]

    with {:ok, step_artifacts} <-
           insert_many(conn, "execution_step", request["steps"], episode_id),
         {:ok, approval_artifacts} <-
           insert_many(conn, "approval_record", request["approval_records"], episode_id),
         {:ok, evidence_artifacts} <-
           insert_many(conn, "evidence_packet", request["evidence_packets"], episode_id),
         {:ok, verifier_artifacts} <-
           insert_many(conn, "verifier_output", request["verifier_outputs"], episode_id),
         {:ok, state_artifact} <-
           insert_artifact(conn, "canonical_state", request["state"], episode_id: episode_id),
         :ok <- maybe_inject_transaction_failure(request),
         {:ok, journal_artifact} <-
           insert_artifact(conn, "episode_journal", request["journal"], episode_id: episode_id),
         {:ok, sequence} <- next_sequence(conn),
         {:ok, episode} <- fetch_episode(conn, episode_id) do
      artifact_ids =
        Enum.map(
          step_artifacts ++
            approval_artifacts ++
            evidence_artifacts ++
            verifier_artifacts ++
            [state_artifact, journal_artifact],
          & &1["artifact_id"]
        )

      result = %{
        "episode_id" => episode_id,
        "idempotency_key" => request["idempotency_key"],
        "request_hash" => request["request_hash"],
        "state_artifact_id" => state_artifact["artifact_id"],
        "journal_artifact_id" => journal_artifact["artifact_id"],
        "artifact_ids" => artifact_ids,
        "committed_sequence" => sequence,
        "idempotent_replay" => false
      }

      keys = Enum.uniq(episode["idempotency_keys"] ++ [request["idempotency_key"]])

      with :ok <-
             run(
               conn,
               """
               UPDATE episodes SET lifecycle = 'committed',
                 accepted_state_artifact_id = ?, journal_artifact_id = ?,
                 rollback_status = ?, recovery_status = 'not_required',
                 idempotency_keys_json = ?, updated_sequence = ?
               WHERE episode_id = ?
               """,
               [
                 state_artifact["artifact_id"],
                 journal_artifact["artifact_id"],
                 request["journal"]["rollback_status"],
                 encode(keys),
                 sequence,
                 episode_id
               ]
             ),
           :ok <-
             run(
               conn,
               """
               INSERT INTO logical_commits
                 (idempotency_key, episode_id, request_hash, result_json, created_sequence)
               VALUES (?, ?, ?, ?, ?)
               """,
               [
                 request["idempotency_key"],
                 episode_id,
                 request["request_hash"],
                 encode(result),
                 sequence
               ]
             ) do
        {:ok, result}
      end
    end
  end

  defp insert_many(conn, type, values, episode_id) do
    Enum.reduce_while(values || [], {:ok, []}, fn payload, {:ok, acc} ->
      case insert_artifact(conn, type, payload, episode_id: episode_id) do
        {:ok, artifact} -> {:cont, {:ok, acc ++ [artifact]}}
        {:error, reason} -> {:halt, {:error, reason}}
      end
    end)
  end

  defp insert_artifact(conn, type, payload, opts) do
    with {:ok, sequence} <- next_sequence(conn) do
      episode_id = Keyword.fetch!(opts, :episode_id)
      artifact = Persistence.build_artifact(type, episode_id, payload, sequence, opts)

      with :ok <-
             run(
               conn,
               """
               INSERT INTO artifacts
                 (artifact_id, artifact_type, schema_version, episode_id,
                  content_hash, created_sequence, provenance_json, payload_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               """,
               [
                 artifact["artifact_id"],
                 artifact["artifact_type"],
                 artifact["schema_version"],
                 artifact["episode_id"],
                 artifact["content_hash"],
                 artifact["created_sequence"],
                 encode(artifact["provenance"]),
                 encode(artifact["payload"])
               ]
             ) do
        {:ok, artifact}
      end
    end
  end

  defp insert_recovery(conn, record) do
    run(
      conn,
      """
      INSERT INTO recovery_records
        (recovery_id, episode_id, step_id, status, crash_window,
         target_identity_json, pre_state_hash, backup_metadata_json,
         effect_applied, rollback_status, content_hash,
         created_sequence, updated_sequence)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      """,
      [
        record["recovery_id"],
        record["episode_id"],
        record["step_id"],
        record["status"],
        record["crash_window"],
        encode(record["target_identity"]),
        record["pre_state_hash"],
        encode(record["backup_metadata"]),
        bool_int(record["effect_applied"]),
        record["rollback_status"],
        record["content_hash"],
        record["created_sequence"],
        record["updated_sequence"]
      ]
    )
  end

  defp fetch_episode(conn, episode_id) do
    sql = """
    SELECT episode_id, task_id, lifecycle, runtime_manifest_json,
           runtime_version, schema_version, hash_policy_version,
           accepted_state_artifact_id, journal_artifact_id, rollback_status,
           recovery_status, idempotency_keys_json, created_sequence, updated_sequence
    FROM episodes WHERE episode_id = ?
    """

    case query_one(conn, sql, [episode_id]) do
      {:ok, nil} -> {:error, :episode_not_found}
      {:ok, row} -> {:ok, episode_from_row(row)}
      {:error, _reason} = error -> error
    end
  end

  defp fetch_artifact(conn, artifact_id) do
    sql = """
    SELECT artifact_id, artifact_type, schema_version, episode_id,
           content_hash, created_sequence, provenance_json, payload_json
    FROM artifacts WHERE artifact_id = ?
    """

    case query_one(conn, sql, [artifact_id]) do
      {:ok, nil} -> {:error, :artifact_not_found}
      {:ok, row} -> {:ok, artifact_from_row(row)}
      {:error, _reason} = error -> error
    end
  end

  defp fetch_recovery(conn, recovery_id) do
    sql = """
    SELECT recovery_id, episode_id, step_id, status, crash_window,
           target_identity_json, pre_state_hash, backup_metadata_json,
           effect_applied, rollback_status, content_hash,
           created_sequence, updated_sequence
    FROM recovery_records WHERE recovery_id = ?
    """

    case query_one(conn, sql, [recovery_id]) do
      {:ok, nil} -> {:error, :recovery_record_not_found}
      {:ok, row} -> {:ok, recovery_from_row(row)}
      {:error, _reason} = error -> error
    end
  end

  defp fetch_commit(conn, key) do
    case query_one(
           conn,
           "SELECT episode_id, request_hash, result_json, created_sequence FROM logical_commits WHERE idempotency_key = ?",
           [key]
         ) do
      {:ok, nil} ->
        {:error, :logical_commit_not_found}

      {:ok, [episode_id, request_hash, result_json, created_sequence]} ->
        {:ok,
         %{
           "episode_id" => episode_id,
           "request_hash" => request_hash,
           "result" => decode(result_json),
           "created_sequence" => created_sequence
         }}

      {:error, _reason} = error ->
        error
    end
  end

  defp update_episode_row(conn, episode_id, lifecycle, attrs) do
    with {:ok, episode} <- fetch_episode(conn, episode_id) do
      episode =
        episode
        |> Map.merge(stringify_keys(attrs))
        |> Map.put("lifecycle", lifecycle)
        |> then(&Schema.validate!("persistence_manifest", &1))

      run(
        conn,
        """
        UPDATE episodes SET lifecycle = ?, accepted_state_artifact_id = ?,
          journal_artifact_id = ?, rollback_status = ?, recovery_status = ?,
          idempotency_keys_json = ?, updated_sequence = ?
        WHERE episode_id = ?
        """,
        [
          episode["lifecycle"],
          episode["accepted_state_artifact_id"],
          episode["journal_artifact_id"],
          episode["rollback_status"],
          episode["recovery_status"],
          encode(episode["idempotency_keys"]),
          episode["updated_sequence"],
          episode_id
        ]
      )
    end
  end

  defp maybe_update_episode_for_recovery(conn, record, sequence) do
    case lifecycle_for_recovery(record["status"]) do
      nil ->
        :ok

      lifecycle ->
        update_episode_row(conn, record["episode_id"], lifecycle, %{
          "recovery_status" => record["status"],
          "rollback_status" => record["rollback_status"],
          "updated_sequence" => sequence
        })
    end
  end

  defp lifecycle_for_recovery("commit_completed"), do: "committed"
  defp lifecycle_for_recovery("abort_completed"), do: "aborted"
  defp lifecycle_for_recovery("rollback_pending"), do: "rollback_pending"
  defp lifecycle_for_recovery("rollback_in_progress"), do: "rollback_pending"
  defp lifecycle_for_recovery("rolled_back"), do: "rolled_back"
  defp lifecycle_for_recovery("recovery_required"), do: "recovery_required"
  defp lifecycle_for_recovery(_status), do: nil

  defp transaction(%{conn: conn}, fun) do
    case exec_script(conn, "BEGIN IMMEDIATE;") do
      :ok ->
        try do
          case fun.(conn) do
            {:ok, value} ->
              case exec_script(conn, "COMMIT;") do
                :ok ->
                  {:ok, value}

                {:error, reason} ->
                  _ = exec_script(conn, "ROLLBACK;")
                  {:error, {:commit_failed, reason}}
              end

            {:error, reason} ->
              _ = exec_script(conn, "ROLLBACK;")
              {:error, reason}
          end
        rescue
          error ->
            _ = exec_script(conn, "ROLLBACK;")
            {:error, {:transaction_rolled_back, Exception.message(error)}}
        catch
          kind, reason ->
            _ = exec_script(conn, "ROLLBACK;")
            {:error, {:transaction_rolled_back, {kind, reason}}}
        end

      {:error, reason} ->
        {:error, {:database_busy_or_locked, reason}}
    end
  end

  defp next_sequence(conn) do
    with :ok <-
           run(
             conn,
             "UPDATE metadata SET value = CAST(value AS INTEGER) + 1 WHERE key = 'sequence'",
             []
           ),
         {:ok, [value]} <-
           query_one(conn, "SELECT value FROM metadata WHERE key = 'sequence'", []) do
      {:ok, String.to_integer(to_string(value))}
    end
  end

  defp initialize_metadata(conn) do
    entries = [
      {"sequence", "0"},
      {"storage_schema_version", Vanta.persistence_schema_version()},
      {"hash_policy_version", Vanta.hash_policy_version()},
      {"runtime_schema_version", Vanta.schema_version()}
    ]

    Enum.reduce_while(entries, :ok, fn {key, value}, :ok ->
      case run(conn, "INSERT OR IGNORE INTO metadata (key, value) VALUES (?, ?)", [key, value]) do
        :ok -> {:cont, :ok}
        {:error, reason} -> {:halt, {:error, reason}}
      end
    end)
  end

  defp verify_metadata(conn) do
    required = %{
      "storage_schema_version" => Vanta.persistence_schema_version(),
      "hash_policy_version" => Vanta.hash_policy_version(),
      "runtime_schema_version" => Vanta.schema_version()
    }

    Enum.reduce_while(required, :ok, fn {key, expected}, :ok ->
      case query_one(conn, "SELECT value FROM metadata WHERE key = ?", [key]) do
        {:ok, [^expected]} ->
          {:cont, :ok}

        {:ok, [actual]} ->
          {:halt, {:error, {:incompatible_storage_metadata, key, actual, expected}}}

        {:ok, nil} ->
          {:halt, {:error, {:missing_storage_metadata, key}}}

        {:error, reason} ->
          {:halt, {:error, reason}}
      end
    end)
  end

  defp ensure_parent(":memory:"), do: :ok

  defp ensure_parent(path) do
    path |> Path.dirname() |> File.mkdir_p()
  end

  defp exec_script(conn, sql), do: conn |> Sqlite3.execute(sql) |> normalize()

  defp run(conn, sql, params) do
    with {:ok, stmt} <- Sqlite3.prepare(conn, sql) do
      try do
        with :ok <- normalize(Sqlite3.bind(stmt, params)) do
          case Sqlite3.step(conn, stmt) do
            :done -> :ok
            :busy -> {:error, :busy}
            {:error, reason} -> {:error, reason}
            {:row, _row} -> {:error, :unexpected_row}
          end
        end
      after
        _ = Sqlite3.release(conn, stmt)
      end
    end
  end

  defp query_one(conn, sql, params) do
    with {:ok, rows} <- query_all(conn, sql, params) do
      case rows do
        [] -> {:ok, nil}
        [row] -> {:ok, row}
        _rows -> {:error, :expected_one_row}
      end
    end
  end

  defp query_all(conn, sql, params) do
    with {:ok, stmt} <- Sqlite3.prepare(conn, sql) do
      try do
        with :ok <- normalize(Sqlite3.bind(stmt, params)) do
          collect_rows(conn, stmt, [])
        end
      after
        _ = Sqlite3.release(conn, stmt)
      end
    end
  end

  defp collect_rows(conn, stmt, acc) do
    case Sqlite3.step(conn, stmt) do
      {:row, row} -> collect_rows(conn, stmt, [row | acc])
      :done -> {:ok, Enum.reverse(acc)}
      :busy -> {:error, :busy}
      {:error, reason} -> {:error, reason}
    end
  end

  defp episode_from_row([
         episode_id,
         task_id,
         lifecycle,
         runtime_manifest_json,
         runtime_version,
         schema_version,
         hash_policy_version,
         accepted_state_artifact_id,
         journal_artifact_id,
         rollback_status,
         recovery_status,
         idempotency_keys_json,
         created_sequence,
         updated_sequence
       ]) do
    %{
      "storage_schema_version" => Vanta.persistence_schema_version(),
      "episode_id" => episode_id,
      "task_id" => task_id,
      "lifecycle" => lifecycle,
      "runtime_manifest" => decode(runtime_manifest_json),
      "runtime_version" => runtime_version,
      "schema_version" => schema_version,
      "hash_policy_version" => hash_policy_version,
      "accepted_state_artifact_id" => accepted_state_artifact_id,
      "journal_artifact_id" => journal_artifact_id,
      "rollback_status" => rollback_status,
      "recovery_status" => recovery_status,
      "idempotency_keys" => decode(idempotency_keys_json),
      "created_sequence" => created_sequence,
      "updated_sequence" => updated_sequence
    }
    |> then(&Schema.validate!("persistence_manifest", &1))
  end

  defp artifact_from_row([
         artifact_id,
         artifact_type,
         schema_version,
         episode_id,
         content_hash,
         created_sequence,
         provenance_json,
         payload_json
       ]) do
    %{
      "artifact_id" => artifact_id,
      "artifact_type" => artifact_type,
      "schema_version" => schema_version,
      "episode_id" => episode_id,
      "content_hash" => content_hash,
      "created_sequence" => created_sequence,
      "provenance" => decode(provenance_json),
      "payload" => decode(payload_json)
    }
  end

  defp recovery_from_row([
         recovery_id,
         episode_id,
         step_id,
         status,
         crash_window,
         target_identity_json,
         pre_state_hash,
         backup_metadata_json,
         effect_applied,
         rollback_status,
         content_hash,
         created_sequence,
         updated_sequence
       ]) do
    %{
      "recovery_id" => recovery_id,
      "episode_id" => episode_id,
      "step_id" => step_id,
      "status" => status,
      "crash_window" => crash_window,
      "target_identity" => decode(target_identity_json),
      "pre_state_hash" => pre_state_hash,
      "backup_metadata" => decode(backup_metadata_json),
      "effect_applied" => effect_applied == 1,
      "rollback_status" => rollback_status,
      "content_hash" => content_hash,
      "created_sequence" => created_sequence,
      "updated_sequence" => updated_sequence
    }
    |> then(&Schema.validate!("recovery_record", &1))
  end

  defp rehash_recovery(record) do
    hash = record |> Map.drop(["content_hash"]) |> Hash.canonical_json_hash()

    record
    |> Map.put("content_hash", hash)
    |> then(&Schema.validate!("recovery_record", &1))
  end

  defp compatible_artifact_version(%{"schema_version" => version}) do
    if version == Vanta.schema_version(),
      do: :ok,
      else: {:error, {:incompatible_artifact_schema_version, version}}
  end

  defp maybe_inject_transaction_failure(%{
         "failure_injection" => "transaction_rollback_after_state"
       }),
       do: {:error, :injected_transaction_rollback}

  defp maybe_inject_transaction_failure(_request), do: :ok

  defp normalize(:ok), do: :ok
  defp normalize(:done), do: :ok
  defp normalize(:busy), do: {:error, :busy}
  defp normalize({:error, reason}), do: {:error, reason}
  defp normalize(other), do: other

  defp encode(value), do: Jason.encode!(value)
  defp decode(value), do: Jason.decode!(value)
  defp bool_int(true), do: 1
  defp bool_int(false), do: 0

  defp stringify_keys(map) when is_map(map) do
    Map.new(map, fn {key, value} -> {to_string(key), stringify_keys(value)} end)
  end

  defp stringify_keys(list) when is_list(list), do: Enum.map(list, &stringify_keys/1)
  defp stringify_keys(value), do: value
end
