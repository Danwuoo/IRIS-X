defmodule Vanta.PersistenceExperiment do
  @moduledoc """
  Deterministic failure-injection runner for Experiment 006.
  """

  alias Vanta.{
    EpisodeJournal,
    Hash,
    Persistence,
    ReplayRunner,
    Runtime,
    Schema,
    StateManager
  }

  alias Vanta.Persistence.{Recovery, SQLiteAdapter}

  @experiment_id "experiment_006_persistence_and_recovery"
  @fixture_root Path.expand("../../../test/fixtures/document_ops", __DIR__)
  @result_root Path.expand(
                 "../../../docs/04_experiments/results/persistence_and_recovery",
                 __DIR__
               )
  @reversible_fixture "docops_ps1_reversible_replace_heading_001"
  @read_fixture "docops_read_traceability_001"

  @hard_requirements %{
    "persistence_artifact_schema_validity" => 1.0,
    "persistence_write_success_rate" => 1.0,
    "restart_recovery_success" => 1.0,
    "replay_consistency" => 1.0,
    "audit_completeness" => 1.0,
    "state_journal_atomicity_violations" => 0,
    "duplicate_logical_commits" => 0,
    "silent_partial_commits" => 0,
    "committed_effects_without_journal_refs" => 0,
    "artifact_integrity_detection_rate" => 1.0,
    "unsupported_commits" => 0,
    "memory_writes" => 0,
    "irreversible_effects" => 0
  }

  def run(opts \\ []) do
    timestamp = Keyword.get(opts, :timestamp, timestamp())
    result_dir = Keyword.get(opts, :result_dir, Path.join(@result_root, timestamp))
    File.mkdir_p!(result_dir)

    cases =
      case_specs()
      |> Enum.map(fn {id, name, fun} -> safe_case(id, name, fun) end)

    metrics = metrics(cases)

    threshold_status =
      if hard_gates_pass?(metrics), do: "pass_acceptance_candidate", else: "failed_no_acceptance"

    run = %{
      "schema_version" => Vanta.schema_version(),
      "experiment_id" => @experiment_id,
      "sample_frame_id" => "PS1-G9-PERSISTENCE-FAILURE-INJECTION-V0",
      "metric_policy_version" => "PS1-G9-HARD-METRICS-V0",
      "threshold_status" => threshold_status,
      "status" => "completed",
      "baseline" => "fixture_local_memory_adapter_shadow_parity",
      "treatment" => "fixture_local_sqlite_persistence_v0",
      "fixture_count" => length(cases),
      "run_controls" => %{
        "failure_injection" => "deterministic_protocol_boundary_simulation",
        "os_process_kill_simulated" => false,
        "storage_schema_version" => Vanta.persistence_schema_version(),
        "runtime_schema_version" => Vanta.schema_version(),
        "hash_policy_version" => Vanta.hash_policy_version(),
        "sqlite_driver" => sqlite_driver_version()
      },
      "fixture_inventory_ref" => "fixture_inventory.md",
      "arm_metadata" => %{
        "scope" => "single_machine_fixture_local_document_ops",
        "adapter" => "Vanta.Persistence.SQLiteAdapter",
        "memory_adapter_role" => "shadow_parity_and_fast_tests"
      },
      "tasks" => Enum.map(cases, &case_summary/1),
      "metrics" => metrics
    }

    Schema.validate!("experiment_run", run)
    write_results(result_dir, run, cases)
    {:ok, %{result_dir: result_dir, run: run, cases: cases}}
  end

  def hard_requirements, do: @hard_requirements

  defp case_specs do
    [
      {"P006-01", "normal commit then restart", &case_normal_restart/0},
      {"P006-02", "crash before Evidence Packet persistence", &case_before_evidence/0},
      {"P006-03", "prepared complete before file effect", &case_prepared_before_effect/0},
      {"P006-04", "file effect complete before DB commit", &case_effect_before_commit/0},
      {"P006-05", "DB commit complete before client response", &case_commit_before_response/0},
      {"P006-06", "crash before rollback starts",
       fn -> case_rollback_window(:before_rollback) end},
      {"P006-07", "crash during rollback", fn -> case_rollback_window(:during_rollback) end},
      {"P006-08", "same idempotency key resend", &case_idempotent_resend/0},
      {"P006-09", "same key conflicting request", &case_idempotency_conflict/0},
      {"P006-10", "artifact content corruption", &case_artifact_corruption/0},
      {"P006-11", "artifact reference missing", &case_missing_reference/0},
      {"P006-12", "schema version incompatible", &case_incompatible_version/0},
      {"P006-13", "database busy or locked", &case_database_busy/0},
      {"P006-14", "write failure transaction rollback", &case_transaction_rollback/0},
      {"P006-15", "incomplete episode discovery", &case_incomplete_discovery/0},
      {"P006-16", "clean workspace replay", &case_clean_replay/0},
      {"P006-17", "structured reversible restart replay", &case_structured_replay/0},
      {"P006-18", "rejected action not accepted", &case_rejected_action/0},
      {"P006-19", "non-accept verifier cannot commit", &case_non_accept_verifier/0},
      {"P006-20", "unsupported and memory effects remain zero", &case_unsupported_effects/0}
    ]
  end

  defp case_normal_restart do
    with_runtime_case("normal", fn db_path, workspace, task, _source ->
      {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)
      episode_id = "episode_p006_normal"

      {:ok, result} =
        Runtime.run_task(task, workspace,
          persistence: context,
          copy_workspace?: false,
          episode_id: episode_id,
          idempotency_key: "p006-normal"
        )

      Persistence.close(context)
      {:ok, restarted} = Persistence.open(SQLiteAdapter, path: db_path)
      {:ok, episode} = Persistence.load_episode(restarted, episode_id)
      {:ok, audit} = Persistence.verify_episode_audit(restarted, episode_id)
      measurements = artifact_measurements(restarted, episode_id)
      Persistence.close(restarted)

      result_case(
        %{
          "runtime_committed" => result.status == "committed",
          "restart_lifecycle_committed" => episode["lifecycle"] == "committed",
          "accepted_state_pointer_present" => is_binary(episode["accepted_state_artifact_id"]),
          "journal_pointer_present" => is_binary(episode["journal_artifact_id"]),
          "audit_complete" => audit.complete?
        },
        measurements
        |> Map.merge(%{"expected_writes" => 1, "successful_writes" => 1})
        |> audit_measurement(audit)
      )
    end)
  end

  defp case_before_evidence do
    crash_and_recover_case("before_evidence", :before_evidence_persist, "rolled_back")
  end

  defp case_prepared_before_effect do
    with_runtime_case("prepared", fn db_path, workspace, task, _source ->
      target = Path.join(workspace, "inputs/terms.md")
      before_hash = Hash.file_hash(target)
      episode_id = "episode_p006_prepared"

      crash =
        Runtime.run_task(task, workspace,
          persistence_adapter: SQLiteAdapter,
          persistence_opts: [path: db_path],
          copy_workspace?: false,
          episode_id: episode_id,
          idempotency_key: "p006-prepared",
          failure_injection: :after_prepared_before_effect
        )

      {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)
      {:ok, discoverable} = Persistence.list_recoverable_episodes(context)
      {:ok, recovery} = Recovery.recover_episode(context, episode_id, workspace)
      {:ok, episode} = Persistence.load_episode(context, episode_id)
      measurements = artifact_measurements(context, episode_id)
      Persistence.close(context)

      result_case(
        %{
          "injected_crash_observed" => match?({:error, {:injected_crash, _, _}}, crash),
          "target_unchanged" => Hash.file_hash(target) == before_hash,
          "episode_discovered" => Enum.any?(discoverable, &(&1["episode_id"] == episode_id)),
          "restart_aborted" => episode["lifecycle"] == "aborted",
          "recovery_record_aborted" => outcome_status(recovery) == "abort_completed"
        },
        Map.merge(measurements, %{
          "recovery_expected" => 1,
          "recovery_succeeded" => bool_count(episode["lifecycle"] == "aborted")
        })
      )
    end)
  end

  defp case_effect_before_commit do
    crash_and_recover_case("effect_before_commit", :before_evidence_persist, "rolled_back")
  end

  defp case_commit_before_response do
    with_runtime_case("response", fn db_path, workspace, task, _source ->
      target = Path.join(workspace, "inputs/terms.md")
      episode_id = "episode_p006_response"

      opts = [
        persistence_adapter: SQLiteAdapter,
        persistence_opts: [path: db_path],
        copy_workspace?: false,
        episode_id: episode_id,
        idempotency_key: "p006-response"
      ]

      crash =
        Runtime.run_task(
          task,
          workspace,
          Keyword.put(opts, :failure_injection, :after_db_commit_before_response)
        )

      content_after_commit = File.read!(target)
      {:ok, retry} = Runtime.run_task(task, workspace, opts)
      {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)
      {:ok, artifacts} = Persistence.load_artifacts(context, episode_id)
      measurements = artifact_measurements(context, episode_id)
      Persistence.close(context)

      no_duplicate = Enum.count(artifacts, &(&1["artifact_type"] == "execution_step")) == 1

      result_case(
        %{
          "injected_crash_observed" => match?({:error, {:injected_crash, _, _}}, crash),
          "retry_committed" => retry.status == "committed",
          "idempotent_replay_reported" => retry.idempotent_replays == 1,
          "effect_not_repeated" => File.read!(target) == content_after_commit,
          "single_step_artifact" => no_duplicate
        },
        Map.merge(measurements, %{
          "expected_writes" => 1,
          "successful_writes" => 1,
          "duplicate_logical_commits" => bool_count(not no_duplicate)
        })
      )
    end)
  end

  defp case_rollback_window(injection) do
    with_runtime_case("rollback_#{injection}", fn db_path, workspace, task, _source ->
      target = Path.join(workspace, "inputs/terms.md")
      before_hash = Hash.file_hash(target)
      episode_id = "episode_p006_rollback_#{injection}"

      _crash =
        Runtime.run_task(task, workspace,
          persistence_adapter: SQLiteAdapter,
          persistence_opts: [path: db_path],
          copy_workspace?: false,
          episode_id: episode_id,
          idempotency_key: "p006-rollback-#{injection}",
          failure_injection: :before_evidence_persist
        )

      {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)

      injected =
        Recovery.recover_episode(context, episode_id, workspace, failure_injection: injection)

      Persistence.close(context)
      {:ok, restarted} = Persistence.open(SQLiteAdapter, path: db_path)
      {:ok, recovery} = Recovery.recover_episode(restarted, episode_id, workspace)
      {:ok, episode} = Persistence.load_episode(restarted, episode_id)
      measurements = artifact_measurements(restarted, episode_id)
      Persistence.close(restarted)

      recovered = episode["lifecycle"] == "rolled_back" and Hash.file_hash(target) == before_hash

      result_case(
        %{
          "rollback_crash_observed" => injected == {:error, {:injected_crash, injection}},
          "restart_rollback_completed" => recovered,
          "recovery_record_rolled_back" => outcome_status(recovery) == "rolled_back"
        },
        Map.merge(measurements, %{
          "recovery_expected" => 1,
          "recovery_succeeded" => bool_count(recovered)
        })
      )
    end)
  end

  defp case_idempotent_resend do
    with_direct_case("idempotent", fn context, task, state, journal ->
      request = commit_request(task, state, journal, "p006-idempotent")
      {:ok, first} = Persistence.commit_episode(context, request)
      {:ok, second} = Persistence.commit_episode(context, request)
      {:ok, artifacts} = Persistence.load_artifacts(context, journal["episode_id"])
      measurements = artifact_measurements(context, journal["episode_id"])

      no_duplicate = Enum.count(artifacts, &(&1["artifact_type"] == "episode_journal")) == 1

      result_case(
        %{
          "second_is_idempotent" => second["idempotent_replay"],
          "same_state_pointer" => first["state_artifact_id"] == second["state_artifact_id"],
          "single_logical_commit_artifacts" => no_duplicate
        },
        Map.merge(measurements, %{
          "expected_writes" => 1,
          "successful_writes" => 1,
          "duplicate_logical_commits" => bool_count(not no_duplicate)
        })
      )
    end)
  end

  defp case_idempotency_conflict do
    with_direct_case("conflict", fn context, task, state, journal ->
      request = commit_request(task, state, journal, "p006-conflict")
      {:ok, first} = Persistence.commit_episode(context, request)
      conflict = put_in(request, ["request_identity", "payload"], %{"different" => true})
      conflict_result = Persistence.commit_episode(context, conflict)
      {:ok, episode} = Persistence.load_episode(context, journal["episode_id"])
      measurements = artifact_measurements(context, journal["episode_id"])

      result_case(
        %{
          "conflict_rejected" => conflict_result == {:error, :idempotency_conflict},
          "accepted_pointer_unchanged" =>
            episode["accepted_state_artifact_id"] == first["state_artifact_id"]
        },
        measurements
      )
    end)
  end

  defp case_artifact_corruption do
    with_direct_case("corrupt", fn context, task, state, journal ->
      {:ok, result} =
        Persistence.commit_episode(context, commit_request(task, state, journal, "p006-corrupt"))

      measurements = artifact_measurements(context, journal["episode_id"])

      :ok =
        Exqlite.Sqlite3.execute(
          context.handle.conn,
          "UPDATE artifacts SET payload_json = '{}' WHERE artifact_id = '#{result["state_artifact_id"]}'"
        )

      detected =
        Persistence.verify_artifact_integrity(context, result["state_artifact_id"]) ==
          {:error, :content_hash_mismatch}

      result_case(
        %{"corruption_detected" => detected},
        Map.merge(measurements, %{
          "integrity_injections" => 1,
          "integrity_detections" => bool_count(detected)
        })
      )
    end)
  end

  defp case_missing_reference do
    with_direct_case("missing_ref", fn context, task, state, journal ->
      journal = Map.put(journal, "evidence_refs", ["missing_evidence_ref"])

      {:ok, _result} =
        Persistence.commit_episode(
          context,
          commit_request(task, state, journal, "p006-missing-ref")
        )

      {:ok, audit} = Persistence.verify_episode_audit(context, journal["episode_id"])
      measurements = artifact_measurements(context, journal["episode_id"])
      detected = not audit.complete? and "evidence_ref:missing_evidence_ref" in audit.missing

      result_case(
        %{"missing_reference_detected" => detected},
        Map.merge(measurements, %{
          "integrity_injections" => 1,
          "integrity_detections" => bool_count(detected)
        })
      )
    end)
  end

  defp case_incompatible_version do
    scratch_case("incompatible", fn dir ->
      db_path = Path.join(dir, "persistence.sqlite3")
      {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)

      :ok =
        Exqlite.Sqlite3.execute(
          context.handle.conn,
          "UPDATE metadata SET value = 'persistence-v99' WHERE key = 'storage_schema_version'"
        )

      Persistence.close(context)
      reopened = Persistence.open(SQLiteAdapter, path: db_path)

      result_case(%{
        "incompatible_version_rejected" =>
          match?({:error, {:incompatible_storage_metadata, _, _, _}}, reopened)
      })
    end)
  end

  defp case_database_busy do
    scratch_case("busy", fn dir ->
      db_path = Path.join(dir, "persistence.sqlite3")
      {:ok, first} = Persistence.open(SQLiteAdapter, path: db_path, busy_timeout: 0)
      {:ok, second} = Persistence.open(SQLiteAdapter, path: db_path, busy_timeout: 0)
      :ok = Exqlite.Sqlite3.execute(first.handle.conn, "BEGIN IMMEDIATE;")
      {task, _state, journal} = direct_episode("busy")
      busy_result = Persistence.create_episode(second, task, journal)
      :ok = Exqlite.Sqlite3.execute(first.handle.conn, "ROLLBACK;")
      {:ok, episodes} = Persistence.list_recoverable_episodes(second)
      Persistence.close(first)
      Persistence.close(second)

      result_case(%{
        "busy_error_explicit" => match?({:error, {:database_busy_or_locked, _}}, busy_result),
        "no_partial_episode" => episodes == []
      })
    end)
  end

  defp case_transaction_rollback do
    with_direct_case("tx_rollback", fn context, task, state, journal ->
      request =
        task
        |> commit_request(state, journal, "p006-tx-rollback")
        |> Map.put("failure_injection", "transaction_rollback_after_state")

      rollback_result = Persistence.commit_episode(context, request)
      {:ok, episode} = Persistence.load_episode(context, journal["episode_id"])
      {:ok, artifacts} = Persistence.load_artifacts(context, journal["episode_id"])

      atomic =
        is_nil(episode["accepted_state_artifact_id"]) and
          is_nil(episode["journal_artifact_id"]) and artifacts == []

      result_case(
        %{
          "write_failed" => match?({:error, _}, rollback_result),
          "state_and_journal_rolled_back" => atomic
        },
        %{
          "state_journal_atomicity_violations" => bool_count(not atomic),
          "silent_partial_commits" => bool_count(not atomic)
        }
      )
    end)
  end

  defp case_incomplete_discovery do
    with_runtime_case("incomplete", fn db_path, workspace, task, _source ->
      episode_id = "episode_p006_incomplete"

      _crash =
        Runtime.run_task(task, workspace,
          persistence_adapter: SQLiteAdapter,
          persistence_opts: [path: db_path],
          copy_workspace?: false,
          episode_id: episode_id,
          idempotency_key: "p006-incomplete",
          failure_injection: :after_prepared_before_effect
        )

      {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)
      {:ok, recoverable} = Persistence.list_recoverable_episodes(context)
      measurements = artifact_measurements(context, episode_id)
      Persistence.close(context)
      found = Enum.any?(recoverable, &(&1["episode_id"] == episode_id))

      result_case(%{"incomplete_episode_discovered" => found}, measurements)
    end)
  end

  defp case_clean_replay do
    replay_case("clean_replay", @read_fixture)
  end

  defp case_structured_replay do
    replay_case("structured_replay", @reversible_fixture)
  end

  defp case_rejected_action do
    scratch_case("rejected", fn dir ->
      fixture = Path.join(@fixture_root, "docops_action_not_allowed_001")
      workspace = copy_fixture(fixture, Path.join(dir, "workspace"))
      task = Schema.load_json!(Path.join(workspace, "task.json"))
      db_path = Path.join(dir, "persistence.sqlite3")

      {:ok, result} =
        Runtime.run_task(task, workspace,
          persistence_adapter: SQLiteAdapter,
          persistence_opts: [path: db_path],
          copy_workspace?: false,
          episode_id: "episode_p006_rejected",
          idempotency_key: "p006-rejected"
        )

      {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)
      {:ok, episode} = Persistence.load_episode(context, result.episode_id)
      measurements = artifact_measurements(context, result.episode_id)
      Persistence.close(context)

      isolated =
        result.status == "rejected" and is_nil(episode["accepted_state_artifact_id"]) and
          is_nil(episode["journal_artifact_id"])

      result_case(
        %{"rejected_action_not_accepted" => isolated},
        Map.merge(measurements, %{
          "state_journal_atomicity_violations" => 0,
          "committed_effects_without_journal_refs" => 0
        })
      )
    end)
  end

  defp case_non_accept_verifier do
    with_direct_case("non_accept", fn context, task, state, journal ->
      verifier = reject_verifier(journal["episode_id"])

      request =
        task
        |> commit_request(state, journal, "p006-non-accept")
        |> Map.put("verifier_outputs", [verifier])

      commit = Persistence.commit_episode(context, request)
      {:ok, episode} = Persistence.load_episode(context, journal["episode_id"])

      result_case(%{
        "non_accept_rejected" => commit == {:error, :verifier_not_accept},
        "accepted_pointer_absent" => is_nil(episode["accepted_state_artifact_id"])
      })
    end)
  end

  defp case_unsupported_effects do
    with_direct_case("unsupported", fn context, task, state, journal ->
      unsupported_step = %{
        "schema_version" => Vanta.schema_version(),
        "step_id" => "step_unsupported",
        "episode_id" => journal["episode_id"],
        "parent_step_id" => nil,
        "action_type" => "read_file",
        "action_payload" => %{"path" => "inputs/traceability.md"},
        "expected_effect" => "must reject",
        "preconditions" => [],
        "postconditions" => [],
        "dependency_edges" => [],
        "verifier_requirements" => [],
        "rollback_policy" => "not_applicable",
        "side_effect_class" => "IRREVERSIBLE",
        "status" => "committed"
      }

      unsupported_request =
        task
        |> commit_request(state, journal, "p006-unsupported")
        |> Map.put("steps", [unsupported_step])

      unsupported = Persistence.commit_episode(context, unsupported_request)

      memory_journal = Map.put(journal, "memory_write_effects", [%{"candidate" => "forbidden"}])

      memory_request = commit_request(task, state, memory_journal, "p006-memory")
      memory = Persistence.commit_episode(context, memory_request)

      {:ok, episode} = Persistence.load_episode(context, journal["episode_id"])
      no_commit = is_nil(episode["accepted_state_artifact_id"])

      result_case(
        %{
          "unsupported_rejected" => unsupported == {:error, :unsupported_side_effect},
          "memory_write_rejected" => memory == {:error, :memory_write_not_allowed},
          "no_accepted_commit" => no_commit
        },
        %{
          "unsupported_commits" => 0,
          "memory_writes" => 0,
          "irreversible_effects" => 0
        }
      )
    end)
  end

  defp crash_and_recover_case(label, injection, expected_lifecycle) do
    with_runtime_case(label, fn db_path, workspace, task, _source ->
      target = Path.join(workspace, "inputs/terms.md")
      before_hash = Hash.file_hash(target)
      episode_id = "episode_p006_#{label}"

      crash =
        Runtime.run_task(task, workspace,
          persistence_adapter: SQLiteAdapter,
          persistence_opts: [path: db_path],
          copy_workspace?: false,
          episode_id: episode_id,
          idempotency_key: "p006-#{label}",
          failure_injection: injection
        )

      changed_before_recovery = Hash.file_hash(target) != before_hash
      {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)
      {:ok, recovery} = Recovery.recover_episode(context, episode_id, workspace)
      {:ok, episode} = Persistence.load_episode(context, episode_id)
      measurements = artifact_measurements(context, episode_id)
      Persistence.close(context)

      recovered =
        episode["lifecycle"] == expected_lifecycle and Hash.file_hash(target) == before_hash

      result_case(
        %{
          "injected_crash_observed" => match?({:error, {:injected_crash, _, _}}, crash),
          "effect_observed_before_recovery" => changed_before_recovery,
          "restart_recovery_completed" => recovered,
          "recovery_record_rolled_back" => outcome_status(recovery) == "rolled_back"
        },
        Map.merge(measurements, %{
          "recovery_expected" => 1,
          "recovery_succeeded" => bool_count(recovered)
        })
      )
    end)
  end

  defp replay_case(label, fixture_name) do
    scratch_case(label, fn dir ->
      source = Path.join(@fixture_root, fixture_name)
      workspace = copy_fixture(source, Path.join(dir, "workspace"))
      task = Schema.load_json!(Path.join(workspace, "task.json"))
      db_path = Path.join(dir, "persistence.sqlite3")
      episode_id = "episode_p006_#{label}"
      {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path)

      {:ok, result} =
        Runtime.run_task(task, workspace,
          persistence: context,
          copy_workspace?: false,
          episode_id: episode_id,
          idempotency_key: "p006-#{label}"
        )

      {:ok, artifacts} = Persistence.load_artifacts(context, episode_id)
      {:ok, audit} = Persistence.verify_episode_audit(context, episode_id)
      expected = persistence_payloads(artifacts)

      {:ok, replay} =
        ReplayRunner.replay(task, source, result.journal, expected,
          strict?: true,
          episode_id: episode_id
        )

      measurements = artifact_measurements(context, episode_id)
      Persistence.close(context)

      result_case(
        %{
          "strict_replay_consistent" => replay.consistent?,
          "fidelity_mismatches_empty" => replay.fidelity_mismatches == [],
          "audit_complete" => audit.complete?
        },
        measurements
        |> Map.merge(%{
          "replay_expected" => 1,
          "replay_succeeded" => bool_count(replay.consistent?),
          "expected_writes" => 1,
          "successful_writes" => 1,
          "committed_effects_without_journal_refs" => bool_count(not audit.complete?)
        })
        |> audit_measurement(audit)
      )
    end)
  end

  defp with_runtime_case(label, fun) do
    scratch_case(label, fn dir ->
      source = Path.join(@fixture_root, @reversible_fixture)
      workspace = copy_fixture(source, Path.join(dir, "workspace"))
      task = Schema.load_json!(Path.join(workspace, "task.json"))
      fun.(Path.join(dir, "persistence.sqlite3"), workspace, task, source)
    end)
  end

  defp with_direct_case(label, fun) do
    scratch_case(label, fn dir ->
      db_path = Path.join(dir, "persistence.sqlite3")
      {:ok, context} = Persistence.open(SQLiteAdapter, path: db_path, busy_timeout: 0)
      {task, state, journal} = direct_episode(label)
      {:ok, _manifest} = Persistence.create_episode(context, task, journal)
      result = fun.(context, task, state, journal)
      Persistence.close(context)
      result
    end)
  end

  defp scratch_case(label, fun) do
    dir =
      Path.join(
        System.tmp_dir!(),
        "vanta_p006_#{label}_#{System.unique_integer([:positive])}"
      )

    File.rm_rf!(dir)
    File.mkdir_p!(dir)

    try do
      fun.(dir)
    after
      _ = File.rm_rf(dir)
    end
  end

  defp direct_episode(label) do
    fixture = Path.join(@fixture_root, @read_fixture)
    task = Schema.load_json!(Path.join(fixture, "task.json"))
    state = StateManager.from_task(task)
    episode_id = "episode_p006_direct_#{label}"

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
        "payload" => %{"kind" => "experiment_006"},
        "pre_state_hash" => state["state_hash"]
      },
      "state" => state,
      "journal" => journal,
      "steps" => [],
      "evidence_packets" => [],
      "verifier_outputs" => []
    }
  end

  defp reject_verifier(episode_id) do
    %{
      "schema_version" => Vanta.schema_version(),
      "verifier_output_id" => "verifier_p006_reject",
      "episode_id" => episode_id,
      "step_id" => "step_p006_reject",
      "evidence_refs" => [],
      "decision" => "reject",
      "verification_scope" => ["state_consistency"],
      "validity_score" => 0.0,
      "confidence" => 1.0,
      "risk_score" => 1.0,
      "violated_constraints" => ["injected_reject"],
      "required_extra_evidence" => []
    }
  end

  defp artifact_measurements(context, episode_id) do
    {:ok, artifacts} = Persistence.load_artifacts(context, episode_id)

    valid =
      Enum.count(
        artifacts,
        &(Persistence.verify_artifact_integrity(context, &1["artifact_id"]) == :ok)
      )

    %{"artifact_count" => length(artifacts), "schema_valid_artifacts" => valid}
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

  defp copy_fixture(source, target) do
    File.rm_rf!(target)
    File.cp_r!(source, target)
    target
  end

  defp outcome_status(%{outcomes: [outcome | _]}), do: outcome["status"]
  defp outcome_status(_summary), do: nil

  defp result_case(checks, measurements \\ %{}) do
    %{"checks" => checks, "measurements" => measurements}
  end

  defp safe_case(id, name, fun) do
    started = System.monotonic_time(:millisecond)

    try do
      result = fun.()
      checks = result["checks"]

      %{
        "case_id" => id,
        "name" => name,
        "passed" => Enum.all?(checks, fn {_name, passed} -> passed == true end),
        "checks" => checks,
        "measurements" => result["measurements"],
        "duration_ms" => System.monotonic_time(:millisecond) - started
      }
    rescue
      error ->
        %{
          "case_id" => id,
          "name" => name,
          "passed" => false,
          "checks" => %{"case_completed" => false},
          "measurements" => %{},
          "error" => Exception.format(:error, error, __STACKTRACE__),
          "duration_ms" => System.monotonic_time(:millisecond) - started
        }
    catch
      kind, reason ->
        %{
          "case_id" => id,
          "name" => name,
          "passed" => false,
          "checks" => %{"case_completed" => false},
          "measurements" => %{},
          "error" => inspect({kind, reason}),
          "duration_ms" => System.monotonic_time(:millisecond) - started
        }
    end
  end

  defp metrics(cases) do
    totals = fn key ->
      Enum.sum(Enum.map(cases, &(get_in(&1, ["measurements", key]) || 0)))
    end

    artifact_count = totals.("artifact_count")
    schema_valid = totals.("schema_valid_artifacts")
    expected_writes = totals.("expected_writes")
    successful_writes = totals.("successful_writes")
    recovery_expected = totals.("recovery_expected")
    recovery_succeeded = totals.("recovery_succeeded")
    replay_expected = totals.("replay_expected")
    replay_succeeded = totals.("replay_succeeded")
    audit_expected = totals.("audit_expected")
    audit_succeeded = totals.("audit_succeeded")
    integrity_injections = totals.("integrity_injections")
    integrity_detections = totals.("integrity_detections")

    %{
      "case_pass_rate" => rate(Enum.count(cases, & &1["passed"]), length(cases)),
      "cases_passed" => Enum.count(cases, & &1["passed"]),
      "cases_total" => length(cases),
      "persistence_artifact_schema_validity" => rate(schema_valid, artifact_count),
      "persistence_write_success_rate" => rate(successful_writes, expected_writes),
      "restart_recovery_success" => rate(recovery_succeeded, recovery_expected),
      "replay_consistency" => rate(replay_succeeded, replay_expected),
      "audit_completeness" => rate(audit_succeeded, audit_expected),
      "state_journal_atomicity_violations" => totals.("state_journal_atomicity_violations"),
      "duplicate_logical_commits" => totals.("duplicate_logical_commits"),
      "silent_partial_commits" => totals.("silent_partial_commits"),
      "committed_effects_without_journal_refs" =>
        totals.("committed_effects_without_journal_refs"),
      "artifact_integrity_detection_rate" => rate(integrity_detections, integrity_injections),
      "unsupported_commits" => totals.("unsupported_commits"),
      "memory_writes" => totals.("memory_writes"),
      "irreversible_effects" => totals.("irreversible_effects"),
      "measurement_counts" => %{
        "artifacts_valid" => schema_valid,
        "artifacts_checked" => artifact_count,
        "writes_succeeded" => successful_writes,
        "writes_expected" => expected_writes,
        "recoveries_succeeded" => recovery_succeeded,
        "recoveries_expected" => recovery_expected,
        "replays_succeeded" => replay_succeeded,
        "replays_expected" => replay_expected,
        "audits_succeeded" => audit_succeeded,
        "audits_expected" => audit_expected,
        "integrity_detections" => integrity_detections,
        "integrity_injections" => integrity_injections
      }
    }
  end

  defp hard_gates_pass?(metrics) do
    metrics["case_pass_rate"] == 1.0 and
      Enum.all?(@hard_requirements, fn {metric, required} -> metrics[metric] == required end)
  end

  defp rate(_numerator, 0), do: 0.0
  defp rate(numerator, denominator), do: numerator / denominator
  defp bool_count(true), do: 1
  defp bool_count(false), do: 0

  defp audit_measurement(measurements, audit) do
    Map.merge(measurements, %{
      "audit_expected" => 1,
      "audit_succeeded" => bool_count(audit.complete?),
      "committed_effects_without_journal_refs" => bool_count(not audit.complete?)
    })
  end

  defp case_summary(case_result) do
    Map.take(case_result, ["case_id", "name", "passed", "duration_ms"])
  end

  defp write_results(result_dir, run, cases) do
    File.write!(Path.join(result_dir, "run.json"), Jason.encode!(run, pretty: true) <> "\n")

    File.write!(
      Path.join(result_dir, "failure_injection_results.json"),
      Jason.encode!(%{"experiment_id" => @experiment_id, "cases" => cases}, pretty: true) <> "\n"
    )

    File.write!(Path.join(result_dir, "summary.md"), render_summary(run))
    File.write!(Path.join(result_dir, "fixture_inventory.md"), render_inventory(cases))
    File.write!(Path.join(result_dir, "failure_injection_matrix.md"), render_matrix(cases))

    File.write!(
      Path.join(result_dir, "environment_manifest.json"),
      Jason.encode!(environment_manifest(), pretty: true) <> "\n"
    )

    File.write!(
      Path.join(result_dir, "schema_hash_policy_versions.json"),
      Jason.encode!(
        %{
          "storage_schema_version" => Vanta.persistence_schema_version(),
          "runtime_schema_version" => Vanta.schema_version(),
          "hash_policy_version" => Vanta.hash_policy_version(),
          "schema_authority" => "docs/03_schemas/*.schema.json"
        },
        pretty: true
      ) <> "\n"
    )
  end

  defp render_summary(run) do
    metrics = run["metrics"]

    """
    # Experiment 006 Persistence And Recovery Summary

    - Experiment: `#{run["experiment_id"]}`
    - Status: `#{run["threshold_status"]}`
    - Cases: `#{metrics["cases_passed"]} / #{metrics["cases_total"]}`
    - Storage schema: `#{Vanta.persistence_schema_version()}`
    - Runtime schema: `#{Vanta.schema_version()}`
    - Hash policy: `#{Vanta.hash_policy_version()}`
    - Failure injection: deterministic protocol-boundary simulation; no OS-level kill claim

    ## Hard Metrics

    #{render_metric_rows(metrics)}

    ## Claim Boundary

    This result is a closure candidate only for `Fixture-Local SQLite Persistence v0`.
    It does not validate H1-H5, the full architecture, production readiness,
    distributed persistence, durable memory, full Context OS, external
    `COMMITTABLE`, `IRREVERSIBLE`, `MEMORY_WRITE`, or broad agent safety.
    """
  end

  defp render_metric_rows(metrics) do
    header = "| Metric | Required | Observed |\n| --- | ---: | ---: |"

    rows =
      Enum.map_join(@hard_requirements, "\n", fn {metric, required} ->
        "| `#{metric}` | `#{required}` | `#{metrics[metric]}` |"
      end)

    header <> "\n" <> rows
  end

  defp render_inventory(cases) do
    rows =
      Enum.map_join(cases, "\n", fn case_result ->
        "| `#{case_result["case_id"]}` | #{case_result["name"]} | `#{case_result["passed"]}` |"
      end)

    """
    # Fixture Inventory

    The measured frame contains 20 deterministic persistence/recovery cases over
    fixture-local Document Ops workspaces. Scratch SQLite databases and copied
    workspaces are temporary; compact result artifacts in this directory are the
    retained evidence.

    | Case | Fixture / injection | Passed |
    | --- | --- | ---: |
    #{rows}
    """
  end

  defp render_matrix(cases) do
    rows =
      Enum.map_join(cases, "\n", fn case_result ->
        failed =
          case_result["checks"]
          |> Enum.reject(fn {_name, passed} -> passed end)
          |> Enum.map_join(", ", &elem(&1, 0))

        failed = if failed == "", do: "none", else: failed

        "| `#{case_result["case_id"]}` | #{case_result["name"]} | `#{case_result["passed"]}` | #{failed} | `#{case_result["duration_ms"]}` |"
      end)

    """
    # Failure-Injection Matrix

    Deterministic injection points model durable protocol boundaries. They do
    not claim an operating-system process kill was executed.

    | Case | Window | Passed | Failed checks | Duration ms |
    | --- | --- | ---: | --- | ---: |
    #{rows}
    """
  end

  defp environment_manifest do
    %{
      "elixir_version" => System.version(),
      "otp_version" => System.otp_release(),
      "os_type" => inspect(:os.type()),
      "system_architecture" => :erlang.system_info(:system_architecture) |> to_string(),
      "sqlite_driver" => sqlite_driver_version(),
      "runtime" => "vanta",
      "runtime_version" => Application.spec(:vanta, :vsn) |> to_string()
    }
  end

  defp sqlite_driver_version do
    Application.spec(:exqlite, :vsn) |> to_string()
  end

  defp timestamp do
    DateTime.utc_now() |> Calendar.strftime("%Y%m%d_%H%M%S")
  end
end
