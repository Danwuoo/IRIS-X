defmodule Vanta.RuntimePersistenceIntegrationTest do
  use ExUnit.Case, async: false

  @moduletag :integration

  alias Vanta.{Hash, Persistence, ReplayRunner, Runtime, Schema}
  alias Vanta.Persistence.{Recovery, SQLiteAdapter}

  @fixture_root Path.expand("../../fixtures/document_ops", __DIR__)
  @reversible_fixture "docops_ps1_reversible_replace_heading_001"

  test "normal SQLite commit survives restart, audits complete, and strictly replays" do
    {db_path, workspace, task, source_fixture} = setup_case("normal")
    {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)

    assert {:ok, result} =
             Runtime.run_task(task, workspace,
               persistence: context,
               copy_workspace?: false,
               episode_id: "episode_persist_normal",
               idempotency_key: "normal"
             )

    assert result.status == "committed"
    assert result.rollback_status == "available"
    assert length(result.persistence_commits) == 1
    assert :ok = Persistence.close(context)

    {:ok, restarted} = Persistence.open(SQLiteAdapter, path: db_path)
    assert {:ok, episode} = Persistence.load_episode(restarted, result.episode_id)
    assert episode["lifecycle"] == "committed"
    assert is_binary(episode["accepted_state_artifact_id"])
    assert is_binary(episode["journal_artifact_id"])

    assert {:ok, %{complete?: true}} =
             Persistence.verify_episode_audit(restarted, result.episode_id)

    assert {:ok, artifacts} = Persistence.load_artifacts(restarted, result.episode_id)

    Enum.each(artifacts, fn artifact ->
      assert :ok = Persistence.verify_artifact_integrity(restarted, artifact["artifact_id"])
    end)

    expected = persistence_payloads(artifacts)

    assert {:ok, replay} =
             ReplayRunner.replay(task, source_fixture, result.journal, expected,
               strict?: true,
               episode_id: result.episode_id
             )

    assert replay.consistent?
    assert replay.fidelity_mismatches == []
    assert :ok = Persistence.close(restarted)
  end

  test "prepared-before-effect crash is discovered and safely aborted after restart" do
    {db_path, workspace, task, _source_fixture} = setup_case("prepared")
    target = Path.join(workspace, "inputs/terms.md")
    before_hash = Hash.file_hash(target)

    assert {:error, {:injected_crash, :after_prepared_before_effect, crash}} =
             Runtime.run_task(task, workspace,
               persistence_adapter: SQLiteAdapter,
               persistence_opts: [path: db_path],
               copy_workspace?: false,
               episode_id: "episode_prepared_crash",
               idempotency_key: "prepared",
               failure_injection: :after_prepared_before_effect
             )

    assert crash.episode_id == "episode_prepared_crash"
    assert Hash.file_hash(target) == before_hash

    {:ok, restarted} = Persistence.open(SQLiteAdapter, path: db_path)
    assert {:ok, recoverable} = Persistence.list_recoverable_episodes(restarted)
    assert Enum.map(recoverable, & &1["episode_id"]) == ["episode_prepared_crash"]

    assert {:ok, %{outcomes: [%{"status" => "abort_completed"}]}} =
             Recovery.recover_episode(restarted, "episode_prepared_crash", workspace)

    assert {:ok, episode} = Persistence.load_episode(restarted, "episode_prepared_crash")
    assert episode["lifecycle"] == "aborted"
    assert is_nil(episode["accepted_state_artifact_id"])
    assert Hash.file_hash(target) == before_hash
    Persistence.close(restarted)
  end

  test "effect-before-DB-commit crash rolls back from durable backup after restart" do
    {db_path, workspace, task, _source_fixture} = setup_case("effect")
    target = Path.join(workspace, "inputs/terms.md")
    before_hash = Hash.file_hash(target)

    assert {:error, {:injected_crash, :before_evidence_persist, _crash}} =
             Runtime.run_task(task, workspace,
               persistence_adapter: SQLiteAdapter,
               persistence_opts: [path: db_path],
               copy_workspace?: false,
               episode_id: "episode_effect_crash",
               idempotency_key: "effect",
               failure_injection: :before_evidence_persist
             )

    refute Hash.file_hash(target) == before_hash

    {:ok, restarted} = Persistence.open(SQLiteAdapter, path: db_path)

    assert {:ok, %{outcomes: [%{"status" => "rolled_back"}]}} =
             Recovery.recover_episode(restarted, "episode_effect_crash", workspace)

    assert Hash.file_hash(target) == before_hash
    assert {:ok, episode} = Persistence.load_episode(restarted, "episode_effect_crash")
    assert episode["lifecycle"] == "rolled_back"
    assert is_nil(episode["accepted_state_artifact_id"])
    Persistence.close(restarted)
  end

  test "DB-commit-before-response crash is idempotently returned without a duplicate effect" do
    {db_path, workspace, task, _source_fixture} = setup_case("response")
    target = Path.join(workspace, "inputs/terms.md")

    assert {:error, {:injected_crash, :after_db_commit_before_response, _crash}} =
             Runtime.run_task(task, workspace,
               persistence_adapter: SQLiteAdapter,
               persistence_opts: [path: db_path],
               copy_workspace?: false,
               episode_id: "episode_response_crash",
               idempotency_key: "response",
               failure_injection: :after_db_commit_before_response
             )

    content_after_commit = File.read!(target)
    assert content_after_commit =~ "# Canonical Terms"

    assert {:ok, retry} =
             Runtime.run_task(task, workspace,
               persistence_adapter: SQLiteAdapter,
               persistence_opts: [path: db_path],
               copy_workspace?: false,
               episode_id: "episode_response_crash",
               idempotency_key: "response"
             )

    assert retry.status == "committed"
    assert retry.idempotent_replays == 1
    assert File.read!(target) == content_after_commit

    {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)
    assert {:ok, artifacts} = Persistence.load_artifacts(context, retry.episode_id)
    assert Enum.count(artifacts, &(&1["artifact_type"] == "execution_step")) == 1
    assert Enum.count(artifacts, &(&1["artifact_type"] == "episode_journal")) == 1
    Persistence.close(context)
  end

  test "rollback pending and in-progress crash windows finish deterministically" do
    for injection <- [:before_rollback, :during_rollback] do
      {db_path, workspace, task, _source_fixture} = setup_case("rollback_#{injection}")
      target = Path.join(workspace, "inputs/terms.md")
      before_hash = Hash.file_hash(target)

      assert {:error, {:injected_crash, :before_evidence_persist, _}} =
               Runtime.run_task(task, workspace,
                 persistence_adapter: SQLiteAdapter,
                 persistence_opts: [path: db_path],
                 copy_workspace?: false,
                 episode_id: "episode_rollback_#{injection}",
                 idempotency_key: "rollback_#{injection}",
                 failure_injection: :before_evidence_persist
               )

      {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)

      assert {:error, {:injected_crash, ^injection}} =
               Recovery.recover_episode(
                 context,
                 "episode_rollback_#{injection}",
                 workspace,
                 failure_injection: injection
               )

      Persistence.close(context)
      {:ok, restarted} = Persistence.open(SQLiteAdapter, path: db_path)

      assert {:ok, %{outcomes: [%{"status" => "rolled_back"}]}} =
               Recovery.recover_episode(
                 restarted,
                 "episode_rollback_#{injection}",
                 workspace
               )

      assert Hash.file_hash(target) == before_hash

      assert {:ok, episode} =
               Persistence.load_episode(restarted, "episode_rollback_#{injection}")

      assert episode["lifecycle"] == "rolled_back"
      Persistence.close(restarted)
    end
  end

  test "rejected runtime action never creates accepted state or journal pointers" do
    fixture = Path.join(@fixture_root, "docops_action_not_allowed_001")
    workspace = copy_workspace(fixture, "rejected")
    task = Schema.load_json!(Path.join(workspace, "task.json"))
    db_path = temp_db_path("rejected")

    assert {:ok, result} =
             Runtime.run_task(task, workspace,
               persistence_adapter: SQLiteAdapter,
               persistence_opts: [path: db_path],
               copy_workspace?: false,
               episode_id: "episode_rejected",
               idempotency_key: "rejected"
             )

    assert result.status == "rejected"
    {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)
    assert {:ok, episode} = Persistence.load_episode(context, result.episode_id)
    assert episode["lifecycle"] == "rejected"
    assert is_nil(episode["accepted_state_artifact_id"])
    assert is_nil(episode["journal_artifact_id"])
    Persistence.close(context)
  end

  defp setup_case(label) do
    fixture = Path.join(@fixture_root, @reversible_fixture)
    workspace = copy_workspace(fixture, label)
    task = Schema.load_json!(Path.join(workspace, "task.json"))
    {temp_db_path(label), workspace, task, fixture}
  end

  defp persistence_payloads(artifacts) do
    %{
      evidence_packets:
        artifacts
        |> Enum.filter(&(&1["artifact_type"] == "evidence_packet"))
        |> Enum.map(& &1["payload"]),
      verifier_outputs:
        artifacts
        |> Enum.filter(&(&1["artifact_type"] == "verifier_output"))
        |> Enum.map(& &1["payload"])
    }
  end

  defp copy_workspace(source, label) do
    target =
      Path.join(
        System.tmp_dir!(),
        "vanta_persistence_integration_#{label}_#{System.unique_integer([:positive])}"
      )

    File.rm_rf!(target)
    File.cp_r!(source, target)
    target
  end

  defp temp_db_path(label) do
    nonce = :crypto.strong_rand_bytes(8) |> Base.encode16(case: :lower)

    path =
      Path.join(
        System.tmp_dir!(),
        "vanta_persistence_integration_#{label}_#{nonce}.sqlite3"
      )

    on_exit(fn ->
      Enum.each([path, path <> "-shm", path <> "-wal"], &File.rm/1)
    end)

    path
  end
end
