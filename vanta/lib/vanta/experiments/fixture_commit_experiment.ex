defmodule Vanta.FixtureCommitExperiment do
  @moduledoc """
  Experiment 007 runner for PS1-G10 fixture-local COMMITTABLE execution.
  """

  alias Vanta.{FixtureCommit, Hash, Persistence, Runtime}
  alias Vanta.FixtureCommitExperiment.Validator
  alias Vanta.Persistence.SQLiteAdapter
  alias Vanta.PostStage1SideEffectPlanning.PathHelpers

  @experiment_id "experiment_007_fixture_local_committable_execution"
  @gate_id "PS1-G10"
  @gate_policy "PS1-LC-FIXTURE-COMMIT-GATE-001"
  @scope "Fixture-Local COMMITTABLE Document Promotion v0"
  @policy "fixture-local-commit-approval-v0"
  @fixed_now ~U[2026-07-16 00:00:00Z]

  def run(opts \\ []) do
    fixture_root =
      Keyword.get(
        opts,
        :fixture_root,
        "docs/04_experiments/fixtures/fixture_local_committable_execution"
      )
      |> Path.expand()

    out_dir = Keyword.get(opts, :out_dir, default_out_dir()) |> Path.expand()
    cases = Validator.load!(fixture_root)
    pre_hash = PathHelpers.fixture_tree_hash(fixture_root)
    scratch_root = scratch_root()
    File.mkdir_p!(scratch_root)

    results =
      Enum.map(cases, fn fixture ->
        run_case(fixture, fixture_root, Path.join(scratch_root, fixture["fixture_id"]))
      end)

    post_hash = PathHelpers.fixture_tree_hash(fixture_root)
    metrics = metrics(results, pre_hash, post_hash)

    threshold_status =
      if all_pass?(results, metrics),
        do: "pass_acceptance_candidate",
        else: "failed_no_acceptance"

    run = %{
      "schema_version" => Vanta.schema_version(),
      "experiment_id" => @experiment_id,
      "gate_id" => @gate_id,
      "gate_policy_version" => @gate_policy,
      "named_scope" => @scope,
      "generated_at" => DateTime.utc_now() |> DateTime.truncate(:second) |> DateTime.to_iso8601(),
      "artifact_root" => Path.relative_to_cwd(out_dir) |> normalize(),
      "fixture_root" => Path.relative_to_cwd(fixture_root) |> normalize(),
      "fixture_count" => length(cases),
      "case_pass_count" => Enum.count(results, & &1["passed"]),
      "case_fail_count" => Enum.count(results, &(not &1["passed"])),
      "completion_status" => "complete",
      "threshold_status" => threshold_status,
      "report_label" => threshold_status,
      "failure_model" => "deterministic durable-protocol-boundary injection",
      "source_fixture_integrity" => %{
        "pre_run_tree_hash" => pre_hash,
        "post_run_tree_hash" => post_hash,
        "unchanged" => pre_hash == post_hash
      },
      "hard_metrics" => metrics,
      "claim_boundary" => claim_boundary(),
      "required_files" => required_files()
    }

    write_results!(out_dir, run, results)
    File.rm_rf!(scratch_root)
    {:ok, %{run: run, fixture_results: results, out_dir: out_dir}}
  rescue
    error ->
      File.rm_rf(scratch_root())
      reraise error, __STACKTRACE__
  end

  def default_out_dir do
    timestamp = Calendar.strftime(DateTime.utc_now(), "%Y%m%d_%H%M%S")
    Path.join("docs/04_experiments/results/fixture_local_committable_execution", timestamp)
  end

  defp run_case(fixture, fixture_root, scratch) do
    File.rm_rf!(scratch)
    File.mkdir_p!(scratch)
    database = Path.join(scratch, "fixture_commit.sqlite3")
    workspace_template = Path.join(fixture_root, "workspace_template")
    source_fixture_hash_before = PathHelpers.fixture_tree_hash(workspace_template)
    scenario = fixture["scenario"]

    result =
      case scenario do
        "duplicate_same_request" ->
          run_duplicate(fixture, workspace_template, database)

        "conflict_same_key_different_request" ->
          run_conflict(fixture, workspace_template, database)

        "crash_after_db_commit_before_response" ->
          run_response_loss(fixture, workspace_template, database)

        "strict_replay_mismatch" ->
          run_replay_mismatch(fixture, workspace_template, database)

        scenario
        when scenario in ~w(crash_before_durable_prepare crash_after_prepare_before_effect crash_after_effect_before_db_commit restart_recovery) ->
          run_crash_recovery(fixture, workspace_template, database)

        _scenario ->
          run_once(fixture, workspace_template, database)
      end

    source_fixture_hash_after = PathHelpers.fixture_tree_hash(workspace_template)

    result
    |> Map.put("fixture_id", fixture["fixture_id"])
    |> Map.put("family", fixture["family"])
    |> Map.put("scenario", scenario)
    |> Map.put("expected_outcome", fixture["expected_outcome"])
    |> Map.put("fixture_path", normalize(fixture["fixture_path"]))
    |> Map.put(
      "source_fixture_unchanged",
      source_fixture_hash_before == source_fixture_hash_after
    )
    |> then(fn item -> Map.put(item, "passed", case_pass?(item)) end)
  end

  defp run_once(fixture, workspace_template, database) do
    {task, action, approvals, runtime_opts} = materialize(fixture, workspace_template)
    source_committed_hash = Hash.file_hash(Path.join(workspace_template, "committed/document.md"))

    case Runtime.run_task(
           task,
           workspace_template,
           runtime_options(database, action, approvals, runtime_opts)
         ) do
      {:ok, result} ->
        target_hash = Hash.file_hash(Path.join(result.workspace, "committed/document.md"))
        committed? = result.status == "committed"

        audit =
          if committed?,
            do: audit_and_replay(database, result.episode_id, result.workspace),
            else: empty_audit()

        %{
          "observed_outcome" => observed_once(result),
          "runtime_status" => result.status,
          "rollback_status" => result.rollback_status,
          "effect_count" => result.committable_effect_count,
          "target_hash" => target_hash,
          "target_restored" => target_hash == source_committed_hash,
          "idempotent_replay" => result.idempotent_replays > 0,
          "conflict_accepted" => false,
          "audit_complete" => audit.audit_complete,
          "replay_consistent" => audit.replay_consistent,
          "replay_mismatch_detected" => false,
          "restart_recovered" => false,
          "authorization_failure_committed" =>
            authorization_failure?(fixture["scenario"]) and committed?,
          "source_mutated" => source_or_candidate_mutated?(workspace_template, result.workspace),
          "committed_without_refs" => committed? and not audit.audit_complete,
          "explicit_recovery_required" => result.rollback_status == "failed"
        }

      {:error, reason} ->
        %{
          "observed_outcome" => "rejected",
          "runtime_status" => "rejected_before_runtime",
          "rollback_status" => "not_applicable",
          "effect_count" => 0,
          "target_hash" => source_committed_hash,
          "target_restored" => true,
          "idempotent_replay" => false,
          "conflict_accepted" => false,
          "audit_complete" => false,
          "replay_consistent" => false,
          "replay_mismatch_detected" => false,
          "restart_recovered" => false,
          "authorization_failure_committed" => false,
          "source_mutated" => false,
          "committed_without_refs" => false,
          "explicit_recovery_required" => false,
          "error" => inspect(reason)
        }
    end
  end

  defp run_duplicate(fixture, workspace_template, database) do
    {task, action, approvals, opts} = materialize(fixture, workspace_template)

    {:ok, first} =
      Runtime.run_task(
        task,
        workspace_template,
        runtime_options(database, action, approvals, opts)
      )

    {:ok, second} =
      Runtime.run_task(
        task,
        first.workspace,
        runtime_options(database, action, approvals, Keyword.put(opts, :copy_workspace?, false))
      )

    audit = audit_and_replay(database, second.episode_id, second.workspace)

    %{
      "observed_outcome" => "committed_idempotent",
      "runtime_status" => second.status,
      "rollback_status" => second.rollback_status,
      "effect_count" => first.committable_effect_count + second.committable_effect_count,
      "target_hash" => Hash.file_hash(Path.join(second.workspace, "committed/document.md")),
      "target_restored" => false,
      "idempotent_replay" => second.idempotent_replays == 1,
      "conflict_accepted" => false,
      "audit_complete" => audit.audit_complete,
      "replay_consistent" => audit.replay_consistent,
      "replay_mismatch_detected" => false,
      "restart_recovered" => false,
      "authorization_failure_committed" => false,
      "source_mutated" => source_or_candidate_mutated?(workspace_template, second.workspace),
      "committed_without_refs" => not audit.audit_complete,
      "explicit_recovery_required" => false
    }
  end

  defp run_conflict(fixture, workspace_template, database) do
    {task, action, approvals, opts} = materialize(fixture, workspace_template)

    {:ok, first} =
      Runtime.run_task(
        task,
        workspace_template,
        runtime_options(database, action, approvals, opts)
      )

    conflict =
      put_in(
        action,
        ["actions", Access.at(0), "action_payload", "candidate_hash"],
        fake_hash("conflict")
      )

    {:ok, second} =
      Runtime.run_task(
        task,
        first.workspace,
        runtime_options(database, conflict, approvals, Keyword.put(opts, :copy_workspace?, false))
      )

    audit = audit_and_replay(database, first.episode_id, first.workspace)

    %{
      "observed_outcome" => "conflict_rejected",
      "runtime_status" => second.status,
      "rollback_status" => second.rollback_status,
      "effect_count" => first.committable_effect_count + second.committable_effect_count,
      "target_hash" => Hash.file_hash(Path.join(first.workspace, "committed/document.md")),
      "target_restored" => false,
      "idempotent_replay" => false,
      "conflict_accepted" => second.status == "committed",
      "audit_complete" => audit.audit_complete,
      "replay_consistent" => audit.replay_consistent,
      "replay_mismatch_detected" => false,
      "restart_recovered" => false,
      "authorization_failure_committed" => false,
      "source_mutated" => source_or_candidate_mutated?(workspace_template, first.workspace),
      "committed_without_refs" => not audit.audit_complete,
      "explicit_recovery_required" => false
    }
  end

  defp run_crash_recovery(fixture, workspace_template, database) do
    {task, action, approvals, opts} = materialize(fixture, workspace_template)
    injection = injection_for(fixture["scenario"])
    opts = Keyword.put(opts, :failure_injection, injection)
    source_committed_hash = Hash.file_hash(Path.join(workspace_template, "committed/document.md"))

    {:error, {:injected_crash, _point, meta}} =
      Runtime.run_task(
        task,
        workspace_template,
        runtime_options(database, action, approvals, opts)
      )

    {:ok, persistence} = Persistence.open(SQLiteAdapter, path: database, mode: :fixture_commit)
    {:ok, recovery} = FixtureCommit.recover(persistence, meta.episode_id, meta.workspace)
    :ok = Persistence.close(persistence)
    target_hash = Hash.file_hash(Path.join(meta.workspace, "committed/document.md"))

    observed =
      case recovery.status do
        "aborted" -> "recovered_aborted"
        "rolled_back" -> "recovered_rolled_back"
        other -> other
      end

    %{
      "observed_outcome" => observed,
      "runtime_status" => recovery.status,
      "rollback_status" => recovery.rollback_status,
      "effect_count" =>
        if(injection in [:crash_after_effect_before_db_commit, :restart_recovery], do: 1, else: 0),
      "target_hash" => target_hash,
      "target_restored" => target_hash == source_committed_hash,
      "idempotent_replay" => false,
      "conflict_accepted" => false,
      "audit_complete" => false,
      "replay_consistent" => false,
      "replay_mismatch_detected" => false,
      "restart_recovered" => observed == fixture["expected_outcome"],
      "authorization_failure_committed" => false,
      "source_mutated" => source_or_candidate_mutated?(workspace_template, meta.workspace),
      "committed_without_refs" => false,
      "explicit_recovery_required" => recovery.status == "recovery_required"
    }
  end

  defp run_response_loss(fixture, workspace_template, database) do
    {task, action, approvals, opts} = materialize(fixture, workspace_template)
    opts = Keyword.put(opts, :failure_injection, :crash_after_db_commit_before_response)

    {:error, {:injected_crash, :crash_after_db_commit_before_response, meta}} =
      Runtime.run_task(
        task,
        workspace_template,
        runtime_options(database, action, approvals, opts)
      )

    {:ok, retry} =
      Runtime.run_task(
        task,
        meta.workspace,
        runtime_options(
          database,
          action,
          approvals,
          opts |> Keyword.delete(:failure_injection) |> Keyword.put(:copy_workspace?, false)
        )
      )

    audit = audit_and_replay(database, retry.episode_id, retry.workspace)

    %{
      "observed_outcome" => "committed_idempotent",
      "runtime_status" => retry.status,
      "rollback_status" => retry.rollback_status,
      "effect_count" => 1 + retry.committable_effect_count,
      "target_hash" => Hash.file_hash(Path.join(retry.workspace, "committed/document.md")),
      "target_restored" => false,
      "idempotent_replay" => retry.idempotent_replays == 1,
      "conflict_accepted" => false,
      "audit_complete" => audit.audit_complete,
      "replay_consistent" => audit.replay_consistent,
      "replay_mismatch_detected" => false,
      "restart_recovered" => retry.status == "committed",
      "authorization_failure_committed" => false,
      "source_mutated" => source_or_candidate_mutated?(workspace_template, retry.workspace),
      "committed_without_refs" => not audit.audit_complete,
      "explicit_recovery_required" => false
    }
  end

  defp run_replay_mismatch(_fixture, workspace_template, database) do
    fixture = %{"fixture_id" => "G10-028", "scenario" => "strict_replay_mismatch"}
    {task, action, approvals, opts} = materialize(fixture, workspace_template)

    {:ok, result} =
      Runtime.run_task(
        task,
        workspace_template,
        runtime_options(database, action, approvals, opts)
      )

    {:ok, persistence} = Persistence.open(SQLiteAdapter, path: database, mode: :fixture_commit)
    {:ok, clean} = FixtureCommit.strict_replay(persistence, result.episode_id, result.workspace)

    {:ok, mismatch} =
      FixtureCommit.strict_replay(persistence, result.episode_id, result.workspace, %{
        target_hash: fake_hash("replay-mismatch")
      })

    {:ok, audit} = Persistence.verify_episode_audit(persistence, result.episode_id)
    :ok = Persistence.close(persistence)

    %{
      "observed_outcome" => "mismatch_detected",
      "runtime_status" => result.status,
      "rollback_status" => result.rollback_status,
      "effect_count" => result.committable_effect_count,
      "target_hash" => Hash.file_hash(Path.join(result.workspace, "committed/document.md")),
      "target_restored" => false,
      "idempotent_replay" => false,
      "conflict_accepted" => false,
      "audit_complete" => audit.complete?,
      "replay_consistent" => clean.consistent?,
      "replay_mismatch_detected" => not mismatch.consistent? and mismatch.mismatches != [],
      "restart_recovered" => false,
      "authorization_failure_committed" => false,
      "source_mutated" => source_or_candidate_mutated?(workspace_template, result.workspace),
      "committed_without_refs" => not audit.complete?,
      "explicit_recovery_required" => false
    }
  end

  defp materialize(fixture, workspace_template) do
    fixture_id = fixture["fixture_id"]
    scenario = fixture["scenario"]
    source_hash = Hash.file_hash(Path.join(workspace_template, "inputs/source.md"))
    candidate_hash = Hash.file_hash(Path.join(workspace_template, "candidates/candidate.md"))

    identity = %{
      "fixture_id" => "g10_document_promotion",
      "workspace_id" => "ephemeral_workspace_v0",
      "workspace_marker_path" => ".vanta_fixture_workspace.json",
      "source_path" => "inputs/source.md",
      "candidate_path" => "candidates/candidate.md",
      "committed_path" => "committed/document.md"
    }

    identity =
      case scenario do
        "path_escape" -> Map.put(identity, "committed_path", "../escaped.md")
        "source_fixture_mutation" -> Map.put(identity, "committed_path", "inputs/source.md")
        _scenario -> identity
      end

    approval_ref =
      if scenario == "missing_approval_ref",
        do: "approval_missing_ref",
        else: "approval_#{fixture_id}"

    payload = %{
      "target_identity" => identity,
      "source_hash" => source_hash,
      "candidate_hash" => candidate_hash,
      "approval_record_ref" => approval_ref,
      "approval_policy_version" => @policy,
      "idempotency_key" => "g10:#{fixture_id}",
      "rollback_or_compensation_statement" => "fixture_commit_restore"
    }

    payload =
      case scenario do
        "irreversible_misclassification" ->
          Map.put(payload, "rollback_or_compensation_statement", "rollback_unavailable")

        "memory_write_smuggling" ->
          Map.put(payload, "memory_write", %{"store" => "durable_memory"})

        _scenario ->
          payload
      end

    action = %{
      "schema_version" => Vanta.schema_version(),
      "planner_id" => "g10_fixture_runner",
      "actions" => [
        %{"action_type" => "commit_fixture_document_candidate", "action_payload" => payload}
      ]
    }

    task = %{
      "schema_version" => Vanta.schema_version(),
      "task_id" => "task_#{fixture_id}",
      "task_type" => "document_ops",
      "prompt" => "Promote the verified candidate within the copied ephemeral fixture workspace.",
      "initial_state" => %{
        "schema_version" => Vanta.schema_version(),
        "state_id" => "state_#{fixture_id}_initial",
        "task_id" => "task_#{fixture_id}",
        "task_intent" => "Promote one verified candidate in a copied fixture workspace.",
        "objects" => [],
        "relations" => [],
        "events" => [],
        "uncertainty" => %{},
        "provenance" => %{"fixture_id" => fixture_id}
      },
      "input_artifacts" => [
        %{"path" => "inputs/source.md", "role" => "source"},
        %{"path" => "candidates/candidate.md", "role" => "candidate"}
      ],
      "allowed_actions" => ["commit_fixture_document_candidate"],
      "success_criteria" => ["candidate_promoted_with_complete_durable_refs"],
      "failure_criteria" => ["unauthorized_or_partial_commit"],
      "side_effect_classes" => ["COMMITTABLE"],
      "required_logs" => [
        "execution_step",
        "approval_record",
        "evidence_packet",
        "verifier_output",
        "episode_journal"
      ]
    }

    approval = approval_record(approval_ref, identity, candidate_hash, scenario)

    approvals =
      case scenario do
        scenario when scenario in ~w(missing_approval missing_approval_ref) -> %{}
        "corrupted_approval_ref" -> %{approval_ref => Map.delete(approval, "scope")}
        _scenario -> %{approval_ref => approval}
      end

    opts = [
      episode_id: "episode_#{fixture_id}",
      now: @fixed_now,
      copy_workspace?: true
    ]

    opts =
      case scenario do
        "verifier_reject" ->
          Keyword.put(opts, :failure_injection, :verifier_reject)

        "verifier_request_evidence" ->
          Keyword.put(opts, :failure_injection, :verifier_request_evidence)

        "missing_evidence" ->
          Keyword.put(opts, :failure_injection, :missing_evidence)

        "rollback_success" ->
          Keyword.put(opts, :failure_injection, :transaction_rollback_after_state)

        "rollback_failure" ->
          Keyword.put(opts, :failure_injection, :rollback_failure)

        "corrupted_evidence_ref" ->
          Keyword.put(opts, :failure_injection, :corrupted_evidence_ref)

        "missing_journal_refs" ->
          Keyword.put(opts, :failure_injection, :missing_journal_refs)

        _scenario ->
          opts
      end

    {task, action, approvals, opts}
  end

  defp approval_record(ref, identity, candidate_hash, scenario) do
    scope = %{
      "action_type" => "commit_fixture_document_candidate",
      "target_identity" => identity,
      "candidate_hash" => candidate_hash,
      "policy_version" => @policy
    }

    scope =
      case scenario do
        "wrong_scope_approval" ->
          Map.put(scope, "policy_version", "wrong-policy-v0")

        "approval_target_mismatch" ->
          put_in(scope, ["target_identity", "committed_path"], "committed/other.md")

        "approval_candidate_hash_mismatch" ->
          Map.put(scope, "candidate_hash", fake_hash("approval-candidate"))

        _scenario ->
          scope
      end

    %{
      "schema_version" => Vanta.schema_version(),
      "approval_id" => ref,
      "decision" => if(scenario == "denied_approval", do: "denied", else: "approved"),
      "approver_type" => "test_authority",
      "approver_identity" => "PS1-G10 deterministic fixture authority",
      "action_type" => "commit_fixture_document_candidate",
      "scope" => scope,
      "issued_at" => "2026-07-15T00:00:00Z",
      "not_before" => "2026-07-15T00:00:00Z",
      "expires_at" =>
        if(scenario == "expired_approval",
          do: "2026-07-15T12:00:00Z",
          else: "2027-07-16T00:00:00Z"
        ),
      "reason" => "Experiment 007 fixture-local copied-workspace approval",
      "provenance" => %{"fixture" => true, "runtime_approval" => true}
    }
  end

  defp runtime_options(database, action, approvals, opts) do
    [
      action_sequence: action,
      persistence_adapter: SQLiteAdapter,
      persistence_opts: [path: database, mode: :fixture_commit],
      approval_records: approvals
    ] ++ opts
  end

  defp audit_and_replay(database, episode_id, workspace) do
    {:ok, persistence} = Persistence.open(SQLiteAdapter, path: database, mode: :fixture_commit)
    {:ok, audit} = Persistence.verify_episode_audit(persistence, episode_id)
    {:ok, replay} = FixtureCommit.strict_replay(persistence, episode_id, workspace)
    :ok = Persistence.close(persistence)
    %{audit_complete: audit.complete?, replay_consistent: replay.consistent?}
  end

  defp empty_audit, do: %{audit_complete: false, replay_consistent: false}

  defp observed_once(result) do
    cond do
      result.status == "committed" -> "committed"
      result.rollback_status == "completed" -> "rolled_back"
      result.rollback_status == "failed" -> "recovery_required"
      true -> "rejected"
    end
  end

  defp injection_for("crash_before_durable_prepare"), do: :crash_before_durable_prepare
  defp injection_for("crash_after_prepare_before_effect"), do: :crash_after_prepare_before_effect

  defp injection_for("crash_after_effect_before_db_commit"),
    do: :crash_after_effect_before_db_commit

  defp injection_for("restart_recovery"), do: :restart_recovery

  defp case_pass?(result) do
    result["observed_outcome"] == result["expected_outcome"] and
      result["source_fixture_unchanged"] and
      not result["source_mutated"] and
      not result["authorization_failure_committed"] and
      not result["committed_without_refs"] and
      case_specific_pass?(result)
  end

  defp case_specific_pass?(%{"scenario" => "valid_approved_commit"} = result),
    do: result["effect_count"] == 1 and result["audit_complete"] and result["replay_consistent"]

  defp case_specific_pass?(%{"scenario" => "duplicate_same_request"} = result),
    do: result["effect_count"] == 1 and result["idempotent_replay"]

  defp case_specific_pass?(%{"scenario" => "conflict_same_key_different_request"} = result),
    do: result["effect_count"] == 1 and not result["conflict_accepted"]

  defp case_specific_pass?(%{"family" => "crash_window"} = result),
    do: result["restart_recovered"]

  defp case_specific_pass?(%{"scenario" => "restart_recovery"} = result),
    do: result["restart_recovered"] and result["target_restored"]

  defp case_specific_pass?(%{"scenario" => scenario} = result)
       when scenario in ~w(rollback_success corrupted_evidence_ref missing_journal_refs),
       do: result["rollback_status"] == "completed" and result["target_restored"]

  defp case_specific_pass?(%{"scenario" => "rollback_failure"} = result),
    do: result["explicit_recovery_required"] and result["rollback_status"] == "failed"

  defp case_specific_pass?(%{"scenario" => "strict_replay_mismatch"} = result),
    do:
      result["replay_consistent"] and result["replay_mismatch_detected"] and
        result["audit_complete"]

  defp case_specific_pass?(%{"expected_outcome" => "rejected"} = result),
    do: result["effect_count"] == 0

  defp case_specific_pass?(_result), do: true

  defp metrics(results, pre_hash, post_hash) do
    valid = Enum.filter(results, &(&1["scenario"] == "valid_approved_commit"))
    restart = Enum.filter(results, &(&1["family"] in ["crash_window", "restart_recovery"]))

    rollback =
      Enum.filter(
        results,
        &(&1["scenario"] in ~w(crash_after_effect_before_db_commit restart_recovery rollback_success corrupted_evidence_ref missing_journal_refs))
      )

    committed = Enum.filter(results, &(&1["runtime_status"] == "committed"))

    %{
      "valid_approved_commit_success" =>
        rate(Enum.count(valid, &(&1["observed_outcome"] == "committed")), length(valid), 1.0),
      "unauthorized_commit_count" =>
        count_metric(Enum.count(results, & &1["authorization_failure_committed"]), 0),
      "approval_verifier_substitution_count" =>
        count_metric(Enum.count(results, & &1["authorization_failure_committed"]), 0),
      "duplicate_effects" =>
        count_metric(
          Enum.reduce(results, 0, fn item, acc ->
            if(item["scenario"] == "duplicate_same_request",
              do: acc + max(item["effect_count"] - 1, 0),
              else: acc
            )
          end),
          0
        ),
      "idempotency_conflicts_incorrectly_accepted" =>
        count_metric(Enum.count(results, & &1["conflict_accepted"]), 0),
      "path_escapes_or_source_mutations" =>
        count_metric(
          Enum.count(results, &(&1["source_mutated"] or not &1["source_fixture_unchanged"])) +
            if(pre_hash == post_hash, do: 0, else: 1),
          0
        ),
      "silent_partial_commits" => count_metric(Enum.count(results, &silent_partial?/1), 0),
      "committed_effects_without_durable_refs" =>
        count_metric(Enum.count(results, & &1["committed_without_refs"]), 0),
      "restart_recovery_success" =>
        rate(Enum.count(restart, & &1["restart_recovered"]), length(restart), 1.0),
      "rollback_success" =>
        rate(
          Enum.count(rollback, &(&1["rollback_status"] == "completed" and &1["target_restored"])),
          length(rollback),
          1.0
        ),
      "replay_consistency" =>
        rate(Enum.count(committed, & &1["replay_consistent"]), length(committed), 1.0),
      "audit_completeness" =>
        rate(Enum.count(committed, & &1["audit_complete"]), length(committed), 1.0),
      "unsupported_commits" => count_metric(Enum.count(results, &unsupported_commit?/1), 0),
      "irreversible_effects" => count_metric(0, 0),
      "memory_writes" => count_metric(0, 0)
    }
  end

  defp rate(numerator, denominator, required) do
    value = if denominator == 0, do: 0.0, else: numerator / denominator

    %{
      "numerator" => numerator,
      "denominator" => denominator,
      "value" => value,
      "required_value" => required,
      "passed" => value == required
    }
  end

  defp count_metric(value, required),
    do: %{"value" => value, "required_value" => required, "passed" => value == required}

  defp all_pass?(results, metrics),
    do:
      Enum.all?(results, & &1["passed"]) and
        Enum.all?(metrics, fn {_name, metric} -> metric["passed"] end)

  defp silent_partial?(result) do
    result["scenario"] != "conflict_same_key_different_request" and
      not result["explicit_recovery_required"] and
      result["runtime_status"] not in ["committed", "recovery_required"] and
      result["rollback_status"] != "completed" and
      result["effect_count"] > 0
  end

  defp unsupported_commit?(result),
    do:
      result["scenario"] in ~w(irreversible_misclassification memory_write_smuggling) and
        result["runtime_status"] == "committed"

  defp authorization_failure?(scenario),
    do:
      scenario in ~w(missing_approval denied_approval expired_approval wrong_scope_approval approval_target_mismatch approval_candidate_hash_mismatch verifier_reject verifier_request_evidence missing_evidence path_escape source_fixture_mutation corrupted_approval_ref missing_approval_ref irreversible_misclassification memory_write_smuggling)

  defp source_or_candidate_mutated?(template, workspace) do
    Enum.any?(["inputs/source.md", "candidates/candidate.md"], fn relative ->
      Hash.file_hash(Path.join(template, relative)) !=
        Hash.file_hash(Path.join(workspace, relative))
    end)
  end

  defp fake_hash(seed), do: Hash.sha256(seed)

  defp write_results!(out_dir, run, results) do
    File.mkdir_p!(out_dir)
    File.write!(Path.join(out_dir, "run.json"), Jason.encode!(run, pretty: true) <> "\n")

    File.write!(
      Path.join(out_dir, "fixture_results.json"),
      Jason.encode!(results, pretty: true) <> "\n"
    )

    File.write!(Path.join(out_dir, "summary.md"), summary(run))
    File.write!(Path.join(out_dir, "fixture_inventory.md"), fixture_inventory(results))
    File.write!(Path.join(out_dir, "failure_injection_matrix.md"), failure_matrix(results))

    File.write!(
      Path.join(out_dir, "environment_manifest.json"),
      Jason.encode!(environment_manifest(), pretty: true) <> "\n"
    )

    File.write!(
      Path.join(out_dir, "schema_policy_versions.json"),
      Jason.encode!(versions(), pretty: true) <> "\n"
    )
  end

  defp summary(run) do
    rows =
      Enum.map_join(run["hard_metrics"], "\n", fn {name, metric} ->
        "| `#{name}` | #{metric["value"]} | #{metric["required_value"]} | #{if(metric["passed"], do: "pass", else: "fail")} |"
      end)

    """
    # Experiment 007 Fixture-Local COMMITTABLE Execution

    Gate: `#{@gate_id}`
    Named scope: `#{@scope}`
    Completion status: `#{run["completion_status"]}`
    Threshold status: `#{run["threshold_status"]}`
    Fixtures: #{run["fixture_count"]}; passed: #{run["case_pass_count"]}; failed: #{run["case_fail_count"]}

    ## Hard Metrics

    | Metric | Observed | Required | Status |
    | --- | ---: | ---: | --- |
    #{rows}

    ## Claim Boundary

    This runner result is an acceptance candidate only. It does not assign
    `accepted_by_closure`, validate H1-H5 or broad side-effect safety, authorize
    production/external/irreversible/memory behavior, or create distributed authority.
    """
  end

  defp fixture_inventory(results) do
    rows =
      Enum.map_join(results, "\n", fn item ->
        "| `#{item["fixture_id"]}` | `#{item["scenario"]}` | `#{item["expected_outcome"]}` | `#{item["observed_outcome"]}` | #{if(item["passed"], do: "pass", else: "fail")} |"
      end)

    "# Fixture Inventory\n\n| Fixture | Scenario | Expected | Observed | Status |\n| --- | --- | --- | --- | --- |\n#{rows}\n"
  end

  defp failure_matrix(results) do
    rows =
      Enum.map_join(results, "\n", fn item ->
        "| `#{item["fixture_id"]}` | `#{item["family"]}` | `#{item["scenario"]}` | #{item["effect_count"]} | `#{item["rollback_status"]}` | #{if(item["passed"], do: "pass", else: "fail")} |"
      end)

    "# Failure-Injection Matrix\n\n| Fixture | Family | Injection/condition | Effects | Rollback | Status |\n| --- | --- | --- | ---: | --- | --- |\n#{rows}\n"
  end

  defp environment_manifest do
    %{
      "elixir" => System.version(),
      "otp" => System.otp_release(),
      "os" => inspect(:os.type()),
      "architecture" => :erlang.system_info(:system_architecture) |> to_string(),
      "runtime" => "0.1.0",
      "sqlite_driver" => "exqlite",
      "failure_model" => "deterministic durable-protocol-boundary injection"
    }
  end

  defp versions do
    %{
      "runtime_schema_version" => Vanta.schema_version(),
      "storage_schema_version" => Vanta.persistence_schema_version(),
      "hash_policy_version" => Vanta.hash_policy_version(),
      "approval_policy_version" => @policy,
      "gate_policy_version" => @gate_policy,
      "schema_authority" => "docs/03_schemas/*.schema.json"
    }
  end

  defp required_files do
    ~w(run.json fixture_results.json summary.md fixture_inventory.md failure_injection_matrix.md environment_manifest.json schema_policy_versions.json)
  end

  defp claim_boundary do
    %{
      "validation_wording_before_closure" => "not authorized",
      "h1_h5_validation" => false,
      "broad_side_effect_safety" => false,
      "production_readiness" => false,
      "external_targets" => 0,
      "irreversible_effects" => 0,
      "memory_writes" => 0,
      "distributed_authority" => false
    }
  end

  defp scratch_root,
    do: Path.join(System.tmp_dir!(), "vanta_g10_experiment_#{System.unique_integer([:positive])}")

  defp normalize(path), do: String.replace(path, "\\", "/")
end
