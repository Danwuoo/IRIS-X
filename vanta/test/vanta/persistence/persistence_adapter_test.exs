defmodule Vanta.PersistenceAdapterTest do
  use ExUnit.Case, async: false

  @moduletag :fast_unit

  alias Vanta.{EpisodeJournal, Persistence, Schema, StateManager}
  alias Vanta.Persistence.{MemoryAdapter, SQLiteAdapter}

  @fixture Path.expand("../../fixtures/document_ops/docops_read_traceability_001", __DIR__)

  for adapter <- [MemoryAdapter, SQLiteAdapter] do
    @adapter adapter

    test "#{inspect(adapter)} satisfies artifact, commit, idempotency, and audit contract" do
      {context, cleanup} = open_context(@adapter)
      on_exit(cleanup)
      {task, state, journal} = episode_fixture("#{inspect(@adapter)}")

      assert {:ok, _manifest} = Persistence.create_episode(context, task, journal)

      assert {:ok, runtime_artifact} =
               Persistence.append_immutable_artifact(
                 context,
                 "runtime_manifest",
                 journal["episode_id"],
                 journal["runtime_manifest"]
               )

      request = commit_request(task, state, journal, "key-contract")

      assert {:ok, first} = Persistence.commit_episode(context, request)
      refute first["idempotent_replay"]

      assert {:ok, second} = Persistence.commit_episode(context, request)
      assert second["idempotent_replay"]
      assert first["state_artifact_id"] == second["state_artifact_id"]

      conflict = put_in(request, ["request_identity", "action_payload"], %{"changed" => true})
      assert {:error, :idempotency_conflict} = Persistence.commit_episode(context, conflict)

      assert {:ok, episode} = Persistence.load_episode(context, journal["episode_id"])
      assert episode["lifecycle"] == "committed"
      assert episode["accepted_state_artifact_id"] == first["state_artifact_id"]
      assert episode["journal_artifact_id"] == first["journal_artifact_id"]

      assert {:ok, artifacts} = Persistence.load_artifacts(context, journal["episode_id"])

      assert Enum.map(artifacts, & &1["created_sequence"]) ==
               artifacts |> Enum.map(& &1["created_sequence"]) |> Enum.sort()

      assert Enum.count(artifacts, &(&1["artifact_type"] == "canonical_state")) == 1
      assert Enum.count(artifacts, &(&1["artifact_type"] == "episode_journal")) == 1
      assert :ok = Persistence.verify_artifact_integrity(context, runtime_artifact["artifact_id"])

      assert {:ok, %{complete?: true, missing: []}} =
               Persistence.verify_episode_audit(context, journal["episode_id"])
    end
  end

  test "canonical state hash is deterministic canonical JSON and excludes state_hash" do
    left = %{"b" => 2, "a" => %{"y" => 2, "x" => 1}, "state_hash" => "old"}
    right = %{"state_hash" => "different", "a" => %{"x" => 1, "y" => 2}, "b" => 2}

    assert Vanta.Hash.state_hash(left) == Vanta.Hash.state_hash(right)

    assert Vanta.Hash.canonical_json(Map.delete(left, "state_hash")) ==
             ~s({"a":{"x":1,"y":2},"b":2})
  end

  test "SQLite detects content corruption and incompatible storage metadata" do
    {context, cleanup} = open_context(SQLiteAdapter)
    path = context.handle.path
    on_exit(cleanup)
    {task, state, journal} = episode_fixture("corruption")

    assert {:ok, _manifest} = Persistence.create_episode(context, task, journal)

    assert {:ok, result} =
             Persistence.commit_episode(
               context,
               commit_request(task, state, journal, "key-corrupt")
             )

    sql =
      "UPDATE artifacts SET payload_json = '{}' WHERE artifact_id = '#{result["state_artifact_id"]}'"

    assert :ok = Exqlite.Sqlite3.execute(context.handle.conn, sql)

    assert {:error, :content_hash_mismatch} =
             Persistence.verify_artifact_integrity(context, result["state_artifact_id"])

    assert :ok =
             Exqlite.Sqlite3.execute(
               context.handle.conn,
               "UPDATE metadata SET value = 'unsupported-v9' WHERE key = 'storage_schema_version'"
             )

    assert :ok = Persistence.close(context)

    assert {:error,
            {:incompatible_storage_metadata, "storage_schema_version", "unsupported-v9",
             "persistence-v0"}} = Persistence.open(SQLiteAdapter, path: path)
  end

  test "SQLite transaction rollback leaves accepted state and journal pointers unchanged" do
    {context, cleanup} = open_context(SQLiteAdapter)
    on_exit(cleanup)
    {task, state, journal} = episode_fixture("rollback")
    assert {:ok, _manifest} = Persistence.create_episode(context, task, journal)

    request =
      task
      |> commit_request(state, journal, "key-rollback")
      |> Map.put("failure_injection", "transaction_rollback_after_state")

    assert {:error, :injected_transaction_rollback} = Persistence.commit_episode(context, request)
    assert {:ok, episode} = Persistence.load_episode(context, journal["episode_id"])
    assert is_nil(episode["accepted_state_artifact_id"])
    assert is_nil(episode["journal_artifact_id"])
    assert {:ok, []} = Persistence.load_artifacts(context, journal["episode_id"])
  end

  test "SQLite reports an explicit busy/locked failure without a partial write" do
    path = temp_db_path("busy")
    {:ok, first} = Persistence.open(SQLiteAdapter, path: path, busy_timeout: 0)
    {:ok, second} = Persistence.open(SQLiteAdapter, path: path, busy_timeout: 0)

    on_exit(fn ->
      _ = Persistence.close(first)
      _ = Persistence.close(second)
      File.rm(path)
    end)

    assert :ok = Exqlite.Sqlite3.execute(first.handle.conn, "BEGIN IMMEDIATE;")
    {task, _state, journal} = episode_fixture("busy")

    assert {:error, {:database_busy_or_locked, _reason}} =
             Persistence.create_episode(second, task, journal)

    assert :ok = Exqlite.Sqlite3.execute(first.handle.conn, "ROLLBACK;")
    assert {:ok, []} = Persistence.list_recoverable_episodes(second)
  end

  test "MemoryAdapter and SQLiteAdapter preserve artifact and pointer parity" do
    {memory, memory_cleanup} = open_context(MemoryAdapter)
    {sqlite, sqlite_cleanup} = open_context(SQLiteAdapter)
    on_exit(memory_cleanup)
    on_exit(sqlite_cleanup)
    {task, state, journal} = episode_fixture("parity")

    for context <- [memory, sqlite] do
      assert {:ok, _manifest} = Persistence.create_episode(context, task, journal)

      assert {:ok, _result} =
               Persistence.commit_episode(
                 context,
                 commit_request(task, state, journal, "key-parity")
               )
    end

    assert {:ok, memory_episode} = Persistence.load_episode(memory, journal["episode_id"])
    assert {:ok, sqlite_episode} = Persistence.load_episode(sqlite, journal["episode_id"])
    assert {:ok, memory_artifacts} = Persistence.load_artifacts(memory, journal["episode_id"])
    assert {:ok, sqlite_artifacts} = Persistence.load_artifacts(sqlite, journal["episode_id"])

    assert Map.take(memory_episode, [
             "lifecycle",
             "accepted_state_artifact_id",
             "journal_artifact_id",
             "rollback_status",
             "idempotency_keys"
           ]) ==
             Map.take(sqlite_episode, [
               "lifecycle",
               "accepted_state_artifact_id",
               "journal_artifact_id",
               "rollback_status",
               "idempotency_keys"
             ])

    assert Enum.map(
             memory_artifacts,
             &Map.take(&1, [
               "artifact_id",
               "artifact_type",
               "content_hash",
               "created_sequence"
             ])
           ) ==
             Enum.map(
               sqlite_artifacts,
               &Map.take(&1, [
                 "artifact_id",
                 "artifact_type",
                 "content_hash",
                 "created_sequence"
               ])
             )
  end

  test "missing journal reference and non-accept verifier fail closed" do
    {context, cleanup} = open_context(SQLiteAdapter)
    on_exit(cleanup)
    {task, state, journal} = episode_fixture("fail_closed")
    assert {:ok, _manifest} = Persistence.create_episode(context, task, journal)

    reject_output = %{
      "schema_version" => Vanta.schema_version(),
      "verifier_output_id" => "verifier_reject",
      "episode_id" => journal["episode_id"],
      "step_id" => "step_reject",
      "evidence_refs" => [],
      "decision" => "reject",
      "verification_scope" => ["state_consistency"],
      "validity_score" => 0.0,
      "confidence" => 1.0,
      "risk_score" => 1.0,
      "violated_constraints" => ["test_reject"],
      "required_extra_evidence" => []
    }

    rejected_request =
      commit_request(task, state, journal, "key-non-accept")
      |> Map.put("verifier_outputs", [reject_output])

    assert {:error, :verifier_not_accept} = Persistence.commit_episode(context, rejected_request)

    journal_with_missing_ref = Map.put(journal, "evidence_refs", ["missing_evidence"])

    accepted_request =
      commit_request(task, state, journal_with_missing_ref, "key-missing-ref")

    assert {:ok, _result} = Persistence.commit_episode(context, accepted_request)

    assert {:ok, %{complete?: false, missing: missing}} =
             Persistence.verify_episode_audit(context, journal["episode_id"])

    assert "evidence_ref:missing_evidence" in missing
  end

  defp open_context(MemoryAdapter) do
    {:ok, context} = Persistence.open(MemoryAdapter)
    {context, fn -> Persistence.close(context) end}
  end

  defp open_context(SQLiteAdapter) do
    path = temp_db_path("adapter")
    {:ok, context} = Persistence.open(SQLiteAdapter, path: path, busy_timeout: 0)

    {context,
     fn ->
       _ = Persistence.close(context)
       File.rm(path)
       File.rm(path <> "-wal")
       File.rm(path <> "-shm")
     end}
  end

  defp episode_fixture(suffix) do
    task = Schema.load_json!(Path.join(@fixture, "task.json"))
    state = StateManager.from_task(task)
    episode_id = "episode_persistence_#{suffix |> to_string() |> String.replace(~r/\W+/, "_")}"

    journal =
      task
      |> EpisodeJournal.new(episode_id)
      |> EpisodeJournal.record_state(state)
      |> EpisodeJournal.set_commit_status("committed")
      |> EpisodeJournal.set_rollback_status("not_applicable")

    {task, state, journal}
  end

  defp commit_request(task, state, journal, key) do
    %{
      "episode_id" => journal["episode_id"],
      "idempotency_key" => key,
      "request_identity" => %{
        "episode_id" => journal["episode_id"],
        "task_id" => task["task_id"],
        "action_payload" => %{"kind" => "contract_test"},
        "pre_state_hash" => state["state_hash"]
      },
      "state" => state,
      "journal" => journal,
      "steps" => [],
      "evidence_packets" => [],
      "verifier_outputs" => []
    }
  end

  defp temp_db_path(label) do
    Path.join(
      System.tmp_dir!(),
      "vanta_#{label}_#{System.unique_integer([:positive])}.sqlite3"
    )
  end
end
