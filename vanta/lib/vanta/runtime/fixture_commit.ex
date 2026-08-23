defmodule Vanta.FixtureCommit do
  @moduledoc """
  PS1-G10 fixture-local COMMITTABLE candidate promotion.
  """

  alias Vanta.{EpisodeJournal, Hash, PathGuard, Persistence, Schema, StateManager}
  alias Vanta.Persistence.{Context, Recovery, SQLiteAdapter}

  @action "commit_fixture_document_candidate"
  @marker_scope "fixture_local_committable_v0"

  def execute(
        task,
        workspace,
        %{"action_type" => @action} = step,
        state,
        journal,
        %Context{adapter: SQLiteAdapter} = persistence,
        opts
      ) do
    payload = step["action_payload"]
    request_identity = request_identity(task, step, state)
    request_hash = Persistence.logical_request_hash(%{"request_identity" => request_identity})
    key = payload["idempotency_key"]

    case Persistence.lookup_logical_commit(persistence, key, request_hash) do
      {:ok, result} ->
        restore_existing(persistence, result)

      {:error, :idempotency_conflict} ->
        reject_without_effect(step, state, journal, :idempotency_conflict)

      :not_found ->
        execute_new(task, workspace, step, state, journal, persistence, request_identity, opts)

      {:error, reason} ->
        reject_without_effect(step, state, journal, {:idempotency_lookup_failed, reason})
    end
  end

  def execute(_task, _workspace, step, state, journal, _persistence, _opts) do
    reject_without_effect(step, state, journal, :sqlite_persistence_required)
  end

  def recover(%Context{} = persistence, episode_id, workspace) do
    with {:ok, episode} <- Persistence.load_episode(persistence, episode_id),
         {:ok, records} <- Persistence.load_recovery_records(persistence, episode_id) do
      cond do
        episode["lifecycle"] == "committed" ->
          {:ok, %{episode_id: episode_id, status: "committed", rollback_status: "available"}}

        records == [] ->
          with {:ok, _episode} <-
                 Persistence.set_episode_status(persistence, episode_id, "aborted", %{
                   "recovery_status" => "abort_before_prepare"
                 }) do
            {:ok, %{episode_id: episode_id, status: "aborted", rollback_status: "not_started"}}
          end

        true ->
          with {:ok, summary} <- Recovery.recover_episode(persistence, episode_id, workspace) do
            statuses = Enum.map(summary.outcomes, & &1["status"])

            cond do
              "recovery_required" in statuses ->
                {:ok,
                 %{episode_id: episode_id, status: "recovery_required", rollback_status: "failed"}}

              "rolled_back" in statuses ->
                {:ok,
                 %{episode_id: episode_id, status: "rolled_back", rollback_status: "completed"}}

              "abort_completed" in statuses ->
                {:ok,
                 %{episode_id: episode_id, status: "aborted", rollback_status: "not_started"}}

              true ->
                {:ok,
                 %{
                   episode_id: episode_id,
                   status: episode["lifecycle"],
                   rollback_status: episode["rollback_status"]
                 }}
            end
          end
      end
    end
  end

  def strict_replay(%Context{} = persistence, episode_id, workspace, overrides \\ %{}) do
    with {:ok, audit} <- Persistence.verify_episode_audit(persistence, episode_id),
         {:ok, episode} <- Persistence.load_episode(persistence, episode_id),
         {:ok, artifacts} <- Persistence.load_artifacts(persistence, episode_id) do
      journal = last_payload(artifacts, "episode_journal")
      state = last_payload(artifacts, "canonical_state")
      step = last_payload(artifacts, "execution_step")
      approval = last_payload(artifacts, "approval_record")
      evidence = payloads(artifacts, "evidence_packet")
      verifiers = payloads(artifacts, "verifier_output")
      artifact_ref = journal |> Map.get("artifact_refs", []) |> List.first()
      target_hash = Map.get(overrides, :target_hash, step["action_payload"]["candidate_hash"])

      mismatches =
        []
        |> mismatch_unless(audit.complete?, "audit_incomplete")
        |> mismatch_unless(episode["lifecycle"] == "committed", "episode_not_committed")
        |> mismatch_unless(step["action_type"] == @action, "action_type")
        |> mismatch_unless(step["side_effect_class"] == "COMMITTABLE", "side_effect_class")
        |> mismatch_unless(step["status"] == "committed", "step_status")
        |> mismatch_unless(journal["commit_status"] == "committed", "commit_status")
        |> mismatch_unless(journal["memory_write_effects"] == [], "memory_write_effects")
        |> mismatch_unless(length(evidence) == 2, "evidence_count")
        |> mismatch_unless(
          MapSet.new(evidence, & &1["evidence_phase"]) ==
            MapSet.new(["pre_effect", "post_effect"]),
          "evidence_phases"
        )
        |> mismatch_unless(length(verifiers) == 2, "verifier_count")
        |> mismatch_unless(
          Enum.all?(verifiers, &(&1["decision"] == "accept")),
          "verifier_decision"
        )
        |> mismatch_unless(approval["decision"] == "approved", "approval_decision")
        |> mismatch_unless(
          approval["scope"]["target_identity"] == step["action_payload"]["target_identity"],
          "approval_target_scope"
        )
        |> mismatch_unless(
          approval["scope"]["candidate_hash"] == step["action_payload"]["candidate_hash"],
          "approval_candidate_hash"
        )
        |> mismatch_unless(not is_nil(artifact_ref), "artifact_ref")
        |> mismatch_unless(
          artifact_ref && artifact_ref["content_hash"] == target_hash,
          "target_hash"
        )
        |> mismatch_unless(final_state_hash(journal) == state["state_hash"], "final_state_hash")
        |> compare_workspace_hashes(workspace, step, target_hash)

      {:ok, %{consistent?: mismatches == [], mismatches: Enum.sort(mismatches), audit: audit}}
    end
  end

  defp execute_new(task, workspace, step, state, journal, persistence, request_identity, opts) do
    case validate_context(workspace, step) do
      {:error, reason} ->
        reject_with_evidence(step, state, journal, persistence, nil, reason, "reject")

      {:ok, context} ->
        case fetch_approval(step, opts) do
          {:error, reason, maybe_record} ->
            reject_with_evidence(
              step,
              state,
              journal,
              persistence,
              schema_valid_approval(maybe_record),
              reason,
              "reject",
              context
            )

          {:ok, approval} ->
            case validate_approval(approval, step, opts) do
              :ok ->
                continue_after_approval(
                  task,
                  workspace,
                  step,
                  state,
                  journal,
                  persistence,
                  context,
                  approval,
                  request_identity,
                  opts
                )

              {:error, reason} ->
                reject_with_evidence(
                  step,
                  state,
                  journal,
                  persistence,
                  approval,
                  reason,
                  "reject",
                  context
                )
            end
        end
    end
  end

  defp continue_after_approval(
         task,
         workspace,
         step,
         state,
         journal,
         persistence,
         context,
         approval,
         request_identity,
         opts
       ) do
    pre_evidence = build_pre_evidence(state, step, context, approval, request_identity)

    pre_evidence =
      if failure_point(opts) == :missing_evidence,
        do: Map.delete(pre_evidence, "target_identity"),
        else: pre_evidence

    pre_decision =
      case failure_point(opts) do
        :verifier_reject ->
          "reject"

        :verifier_request_evidence ->
          "request_evidence"

        _point ->
          if(complete_pre_evidence?(pre_evidence),
            do: "accept",
            else: "request_evidence"
          )
      end

    pre_verifier = verifier_output(step, pre_evidence, "pre", pre_decision)

    if pre_decision != "accept" do
      persist_rejection(persistence, step, pre_evidence, pre_verifier, approval)

      {:error,
       base_outcome(step, state, journal,
         evidence_packets: [pre_evidence],
         verifier_outputs: [pre_verifier],
         approval_records: [approval],
         reason: {:pre_effect_verifier, pre_decision}
       )}
    else
      prepare_and_effect(
        task,
        workspace,
        step,
        state,
        journal,
        persistence,
        context,
        approval,
        pre_evidence,
        pre_verifier,
        request_identity,
        opts
      )
    end
  end

  defp prepare_and_effect(
         task,
         workspace,
         step,
         state,
         journal,
         persistence,
         context,
         approval,
         pre_evidence,
         pre_verifier,
         request_identity,
         opts
       ) do
    if failure_point(opts) == :crash_before_durable_prepare do
      {:crash, :crash_before_durable_prepare,
       base_outcome(step, state, journal,
         status: "aborted",
         evidence_packets: [pre_evidence],
         verifier_outputs: [pre_verifier],
         approval_records: [approval],
         reason: :crash_before_durable_prepare
       )}
    else
      with {:ok, recovery_record} <-
             Recovery.prepare_committable(persistence, workspace, step, state["state_hash"]),
           :ok <- inject_after_prepare(opts),
           :ok <- promote_candidate(context),
           {:ok, recovery_record} <- Recovery.mark_effect_applied(persistence, recovery_record) do
        if failure_point(opts) in [:crash_after_effect_before_db_commit, :restart_recovery] do
          {:crash, :crash_after_effect_before_db_commit,
           base_outcome(step, state, journal,
             status: "aborted",
             evidence_packets: [pre_evidence],
             verifier_outputs: [pre_verifier],
             approval_records: [approval],
             effect_count: 1,
             reason: :crash_after_effect_before_db_commit
           )}
        else
          verify_post_and_commit(
            task,
            workspace,
            step,
            state,
            journal,
            persistence,
            context,
            approval,
            pre_evidence,
            pre_verifier,
            recovery_record,
            request_identity,
            opts
          )
        end
      else
        {:error, {:injected_crash, :crash_after_prepare_before_effect}} ->
          {:crash, :crash_after_prepare_before_effect,
           base_outcome(step, state, journal,
             status: "aborted",
             evidence_packets: [pre_evidence],
             verifier_outputs: [pre_verifier],
             approval_records: [approval],
             reason: :crash_after_prepare_before_effect
           )}

        {:error, reason} ->
          reject_with_evidence(
            step,
            state,
            journal,
            persistence,
            approval,
            reason,
            "reject",
            context
          )
      end
    end
  end

  defp verify_post_and_commit(
         _task,
         workspace,
         step,
         state,
         journal,
         persistence,
         context,
         approval,
         pre_evidence,
         pre_verifier,
         recovery_record,
         request_identity,
         opts
       ) do
    committed_state =
      StateManager.append_event(state, %{
        "step_id" => step["step_id"],
        "action_type" => @action,
        "observation_kind" => @action,
        "mutated" => true,
        "committed_path" => context.target_identity["committed_path"]
      })

    post_evidence =
      build_post_evidence(state, committed_state, step, context, approval, recovery_record)

    post_verifier =
      verifier_output(step, post_evidence, "post", post_decision(post_evidence, context))

    if post_verifier["decision"] != "accept" do
      rollback = rollback_effect(persistence, recovery_record, workspace)

      {:error,
       base_outcome(step, state, journal,
         rollback_status: rollback,
         evidence_packets: [pre_evidence, post_evidence],
         verifier_outputs: [pre_verifier, post_verifier],
         approval_records: [approval],
         effect_count: 1,
         reason: :post_effect_verifier_not_accept
       )}
    else
      committed_step = Map.put(step, "status", "committed")

      artifact_ref = %{
        "artifact_role" => "committed_document",
        "path" => context.target_identity["committed_path"],
        "content_hash" => context.candidate_hash,
        "target_identity" => context.target_identity
      }

      committed_journal =
        journal
        |> EpisodeJournal.record_step(committed_step)
        |> EpisodeJournal.record_evidence(pre_evidence)
        |> EpisodeJournal.record_evidence(post_evidence)
        |> EpisodeJournal.record_verifier_output(pre_verifier)
        |> EpisodeJournal.record_verifier_output(post_verifier)
        |> EpisodeJournal.record_approval(approval)
        |> EpisodeJournal.record_artifact(artifact_ref)
        |> EpisodeJournal.record_state(committed_state)
        |> EpisodeJournal.set_commit_status("committed")
        |> EpisodeJournal.set_rollback_status("available")

      committed_journal = inject_journal_ref_failure(committed_journal, opts)
      maybe_corrupt_backup(workspace, recovery_record, opts)

      request = %{
        "episode_id" => step["episode_id"],
        "idempotency_key" => step["action_payload"]["idempotency_key"],
        "request_identity" => request_identity,
        "state" => committed_state,
        "journal" => committed_journal,
        "steps" => [committed_step],
        "approval_records" => [approval],
        "evidence_packets" => [pre_evidence, post_evidence],
        "verifier_outputs" => [pre_verifier, post_verifier],
        "failure_injection" => transaction_failure(opts)
      }

      case Persistence.commit_episode(persistence, request) do
        {:ok, commit_result} ->
          {:ok, _record} =
            Persistence.record_recovery_status(
              persistence,
              recovery_record["recovery_id"],
              "commit_completed",
              %{"rollback_status" => "available"}
            )

          outcome =
            base_outcome(committed_step, committed_state, committed_journal,
              status: "committed",
              rollback_status: "available",
              evidence_packets: [pre_evidence, post_evidence],
              verifier_outputs: [pre_verifier, post_verifier],
              approval_records: [approval],
              observations: [post_evidence["observation"]],
              persistence_commit: commit_result,
              effect_count: 1
            )

          if failure_point(opts) == :crash_after_db_commit_before_response do
            {:crash, :crash_after_db_commit_before_response, outcome}
          else
            {:ok, outcome}
          end

        {:error, reason} ->
          rollback = rollback_effect(persistence, recovery_record, workspace)

          {:error,
           base_outcome(step, state, journal,
             rollback_status: rollback,
             evidence_packets: [pre_evidence, post_evidence],
             verifier_outputs: [pre_verifier, post_verifier],
             approval_records: [approval],
             effect_count: 1,
             reason: {:logical_commit_failed, reason}
           )}
      end
    end
  end

  defp validate_context(workspace, step) do
    payload = step["action_payload"]
    identity = payload["target_identity"]

    with :ok <- require_prefix(identity["source_path"], "inputs/", :source_path_out_of_scope),
         :ok <-
           require_prefix(identity["candidate_path"], "candidates/", :candidate_path_out_of_scope),
         :ok <-
           require_prefix(identity["committed_path"], "committed/", :committed_path_out_of_scope),
         :ok <- require_distinct_paths(identity),
         {:ok, marker_path} <-
           PathGuard.safe_resolve(workspace, identity["workspace_marker_path"]),
         {:ok, source_path} <- PathGuard.safe_resolve(workspace, identity["source_path"]),
         {:ok, candidate_path} <- PathGuard.safe_resolve(workspace, identity["candidate_path"]),
         {:ok, committed_path} <- PathGuard.safe_resolve(workspace, identity["committed_path"]),
         {:ok, marker} <- load_marker(marker_path),
         :ok <- validate_marker(marker, identity),
         :ok <- require_regular(source_path, :source_missing),
         :ok <- require_regular(candidate_path, :candidate_missing),
         source_hash <- Hash.file_hash(source_path),
         candidate_hash <- Hash.file_hash(candidate_path),
         :ok <- require_equal(source_hash, payload["source_hash"], :source_hash_mismatch),
         :ok <- require_equal(candidate_hash, payload["candidate_hash"], :candidate_hash_mismatch) do
      {:ok,
       %{
         workspace: workspace,
         target_identity: identity,
         marker: marker,
         source_path: source_path,
         candidate_path: candidate_path,
         committed_path: committed_path,
         source_hash: source_hash,
         candidate_hash: candidate_hash,
         target_preexisting: File.regular?(committed_path),
         target_pre_hash:
           if(File.regular?(committed_path), do: Hash.file_hash(committed_path), else: "missing")
       }}
    else
      {:error, reason} -> {:error, reason}
    end
  end

  defp fetch_approval(step, opts) do
    ref = step["action_payload"]["approval_record_ref"]
    records = Keyword.get(opts, :approval_records, %{})

    case Map.fetch(records, ref) do
      :error ->
        {:error, :approval_record_missing, nil}

      {:ok, record} ->
        case Schema.validate("approval_record", record) do
          :ok -> {:ok, record}
          {:error, _errors} -> {:error, :approval_record_schema_invalid, record}
        end
    end
  end

  defp validate_approval(approval, step, opts) do
    payload = step["action_payload"]
    scope = approval["scope"]
    now = Keyword.get(opts, :now, DateTime.utc_now())

    with :ok <- require_equal(approval["decision"], "approved", :approval_denied),
         :ok <- require_equal(approval["action_type"], @action, :approval_action_mismatch),
         :ok <- require_equal(scope["action_type"], @action, :approval_scope_action_mismatch),
         :ok <-
           require_equal(
             scope["target_identity"],
             payload["target_identity"],
             :approval_target_mismatch
           ),
         :ok <-
           require_equal(
             scope["candidate_hash"],
             payload["candidate_hash"],
             :approval_candidate_hash_mismatch
           ),
         :ok <-
           require_equal(
             scope["policy_version"],
             payload["approval_policy_version"],
             :approval_policy_mismatch
           ),
         {:ok, not_before} <- parse_time(approval["not_before"]),
         {:ok, expires_at} <- parse_time(approval["expires_at"]),
         :ok <-
           if(DateTime.compare(now, not_before) in [:eq, :gt],
             do: :ok,
             else: {:error, :approval_not_yet_valid}
           ),
         :ok <-
           if(DateTime.compare(now, expires_at) == :lt,
             do: :ok,
             else: {:error, :approval_expired}
           ) do
      :ok
    end
  end

  defp build_pre_evidence(state, step, context, approval, request_identity) do
    %{
      "schema_version" => Vanta.schema_version(),
      "evidence_id" => "evidence_#{step["step_id"]}_pre",
      "episode_id" => step["episode_id"],
      "step_id" => step["step_id"],
      "pre_state_hash" => state["state_hash"],
      "pre_state_summary" => state["task_intent"],
      "action_ref" => step["step_id"],
      "observation" => %{
        "kind" => @action,
        "phase" => "pre_effect",
        "mutated" => false,
        "workspace_scope" => context.marker["scope"],
        "ephemeral" => context.marker["ephemeral"],
        "source_hash" => context.source_hash,
        "candidate_hash" => context.candidate_hash,
        "target_preexisting" => context.target_preexisting,
        "target_pre_hash" => context.target_pre_hash,
        "approval_record_ref" => approval["approval_id"],
        "approval_policy_version" => approval["scope"]["policy_version"],
        "idempotency_key" => step["action_payload"]["idempotency_key"],
        "request_hash" =>
          Persistence.logical_request_hash(%{"request_identity" => request_identity}),
        "rollback_policy" => "fixture_commit_restore",
        "path" => context.target_identity["committed_path"]
      },
      "post_state_summary" => state["task_intent"],
      "post_state_hash" => state["state_hash"],
      "verifier_result" => %{},
      "confidence" => 1.0,
      "disagreement" => %{},
      "violated_constraints" => [],
      "failure_logits" => %{},
      "credit_hints" => %{},
      "provenance" => %{
        "source" => "ephemeral_copied_fixture_workspace",
        "paths" => [
          context.target_identity["workspace_marker_path"],
          context.target_identity["source_path"],
          context.target_identity["candidate_path"],
          context.target_identity["committed_path"]
        ]
      },
      "runtime_context" => %{
        "runtime" => "vanta_fixture_commit_v0",
        "schema_version" => Vanta.schema_version(),
        "side_effect_class" => "COMMITTABLE",
        "gate_policy_version" => "PS1-LC-FIXTURE-COMMIT-GATE-001"
      },
      "evidence_phase" => "pre_effect",
      "target_identity" => context.target_identity,
      "approval_record_refs" => [approval["approval_id"]],
      "artifact_refs" => [
        %{
          "artifact_role" => "candidate_document",
          "path" => context.target_identity["candidate_path"],
          "content_hash" => context.candidate_hash
        }
      ]
    }
    |> then(&Schema.validate!("evidence_packet", &1))
  end

  defp build_post_evidence(state, committed_state, step, context, approval, recovery_record) do
    committed_hash = Hash.file_hash(context.committed_path)
    source_hash_after = Hash.file_hash(context.source_path)
    candidate_hash_after = Hash.file_hash(context.candidate_path)

    %{
      "schema_version" => Vanta.schema_version(),
      "evidence_id" => "evidence_#{step["step_id"]}_post",
      "episode_id" => step["episode_id"],
      "step_id" => step["step_id"],
      "pre_state_hash" => state["state_hash"],
      "pre_state_summary" => state["task_intent"],
      "action_ref" => step["step_id"],
      "observation" => %{
        "kind" => @action,
        "phase" => "post_effect",
        "mutated" => true,
        "path" => context.target_identity["committed_path"],
        "committed_hash" => committed_hash,
        "candidate_hash" => context.candidate_hash,
        "candidate_hash_after" => candidate_hash_after,
        "source_hash" => context.source_hash,
        "source_hash_after" => source_hash_after,
        "effect_count" => 1,
        "recovery_id" => recovery_record["recovery_id"],
        "rollback_policy" => "fixture_commit_restore"
      },
      "post_state_summary" => committed_state["task_intent"],
      "post_state_hash" => committed_state["state_hash"],
      "verifier_result" => %{},
      "confidence" => 1.0,
      "disagreement" => %{},
      "violated_constraints" => [],
      "failure_logits" => %{},
      "credit_hints" => %{},
      "provenance" => %{
        "source" => "ephemeral_copied_fixture_workspace",
        "paths" => [
          context.target_identity["source_path"],
          context.target_identity["candidate_path"],
          context.target_identity["committed_path"]
        ]
      },
      "runtime_context" => %{
        "runtime" => "vanta_fixture_commit_v0",
        "schema_version" => Vanta.schema_version(),
        "side_effect_class" => "COMMITTABLE",
        "gate_policy_version" => "PS1-LC-FIXTURE-COMMIT-GATE-001"
      },
      "evidence_phase" => "post_effect",
      "target_identity" => context.target_identity,
      "approval_record_refs" => [approval["approval_id"]],
      "artifact_refs" => [
        %{
          "artifact_role" => "committed_document",
          "path" => context.target_identity["committed_path"],
          "content_hash" => committed_hash
        }
      ]
    }
    |> then(&Schema.validate!("evidence_packet", &1))
  end

  defp verifier_output(step, evidence, phase, decision) do
    violations =
      case decision do
        "accept" -> []
        "request_evidence" -> []
        _other -> ["fixture_commit_#{phase}_effect_rejected"]
      end

    required =
      if decision == "request_evidence", do: ["complete_#{phase}_effect_evidence"], else: []

    %{
      "schema_version" => Vanta.schema_version(),
      "verifier_output_id" => "verifier_#{step["step_id"]}_#{phase}",
      "episode_id" => step["episode_id"],
      "step_id" => step["step_id"],
      "evidence_refs" => [evidence["evidence_id"]],
      "decision" => decision,
      "verification_scope" => [
        "preconditions",
        "postconditions",
        "evidence_sufficiency",
        "policy_constraints",
        "side_effect_safety",
        "state_consistency"
      ],
      "validity_score" => if(decision == "accept", do: 1.0, else: 0.0),
      "confidence" => 1.0,
      "risk_score" => if(decision == "accept", do: 0.05, else: 1.0),
      "violated_constraints" => violations,
      "required_extra_evidence" => required,
      "calibration_state" => %{"policy" => "PS1-G10-deterministic-verifier-v0"},
      "disagreement" => %{},
      "failure_logits" => %{},
      "credit_hints" => %{}
    }
    |> then(&Schema.validate!("verifier_output", &1))
  end

  defp post_decision(post_evidence, context) do
    observation = post_evidence["observation"]

    if observation["committed_hash"] == context.candidate_hash and
         observation["source_hash_after"] == context.source_hash and
         observation["candidate_hash_after"] == context.candidate_hash and
         Schema.validate("evidence_packet", post_evidence) == :ok do
      "accept"
    else
      "reject"
    end
  end

  defp reject_with_evidence(
         step,
         state,
         journal,
         persistence,
         approval,
         reason,
         decision,
         context \\ nil
       ) do
    evidence = rejection_evidence(step, state, approval, reason, context)
    verifier = verifier_output(step, evidence, "pre", decision)
    persist_rejection(persistence, step, evidence, verifier, approval)

    {:error,
     base_outcome(step, state, journal,
       evidence_packets: [evidence],
       verifier_outputs: [verifier],
       approval_records: List.wrap(approval),
       reason: reason
     )}
  end

  defp rejection_evidence(step, state, approval, reason, context) do
    identity = step["action_payload"]["target_identity"]
    approval_refs = if approval, do: [approval["approval_id"]], else: []

    %{
      "schema_version" => Vanta.schema_version(),
      "evidence_id" => "evidence_#{step["step_id"]}_pre",
      "episode_id" => step["episode_id"],
      "step_id" => step["step_id"],
      "pre_state_hash" => state["state_hash"],
      "pre_state_summary" => state["task_intent"],
      "action_ref" => step["step_id"],
      "observation" => %{
        "kind" => @action,
        "phase" => "pre_effect",
        "mutated" => false,
        "error" => inspect(reason),
        "path" => identity["committed_path"]
      },
      "post_state_summary" => state["task_intent"],
      "post_state_hash" => state["state_hash"],
      "verifier_result" => %{},
      "confidence" => 1.0,
      "disagreement" => %{},
      "violated_constraints" => [inspect(reason)],
      "failure_logits" => %{},
      "credit_hints" => %{},
      "provenance" => %{
        "source" => "fixture_commit_precondition_validation",
        "paths" =>
          Enum.reject(
            [identity["source_path"], identity["candidate_path"], identity["committed_path"]],
            &is_nil/1
          )
      },
      "runtime_context" => %{
        "runtime" => "vanta_fixture_commit_v0",
        "schema_version" => Vanta.schema_version(),
        "side_effect_class" => "COMMITTABLE"
      },
      "evidence_phase" => "pre_effect",
      "target_identity" => identity,
      "approval_record_refs" => approval_refs,
      "artifact_refs" =>
        if(context, do: [%{"candidate_hash" => context.candidate_hash}], else: [])
    }
    |> then(&Schema.validate!("evidence_packet", &1))
  end

  defp persist_rejection(persistence, step, evidence, verifier, approval) do
    rejected_step = Map.put(step, "status", "rejected")

    with {:ok, _step} <-
           Persistence.append_immutable_artifact(
             persistence,
             "execution_step",
             step["episode_id"],
             rejected_step
           ),
         :ok <- maybe_persist_approval(persistence, step["episode_id"], approval),
         :ok <- maybe_persist_evidence(persistence, step["episode_id"], evidence),
         {:ok, _verifier} <-
           Persistence.record_verifier_result(persistence, step["episode_id"], verifier),
         {:ok, _episode} <-
           Persistence.set_episode_status(persistence, step["episode_id"], "rejected", %{
             "recovery_status" => "rejected_before_effect"
           }) do
      :ok
    else
      _error -> :error
    end
  end

  defp restore_existing(persistence, result) do
    with {:ok, artifacts} <- load_result_artifacts(persistence, result) do
      journal = last_payload(artifacts, "episode_journal")
      state = last_payload(artifacts, "canonical_state")
      step = last_payload(artifacts, "execution_step")
      evidence = payloads(artifacts, "evidence_packet")
      verifiers = payloads(artifacts, "verifier_output")
      approvals = payloads(artifacts, "approval_record")

      observation =
        evidence |> Enum.find(&(&1["evidence_phase"] == "post_effect")) |> Map.get("observation")

      {:ok,
       base_outcome(step, state, journal,
         status: "committed",
         rollback_status: journal["rollback_status"],
         evidence_packets: evidence,
         verifier_outputs: verifiers,
         approval_records: approvals,
         observations: [observation],
         persistence_commit: Map.put(result, "idempotent_replay", true),
         idempotent_replay: true,
         effect_count: 0
       )}
    else
      {:error, reason} -> {:error, %{reason: {:idempotent_restore_failed, reason}}}
    end
  end

  defp base_outcome(step, state, journal, opts) do
    %{
      status: Keyword.get(opts, :status, "rejected"),
      rollback_status: Keyword.get(opts, :rollback_status, "not_applicable"),
      step: step,
      state: state,
      journal: journal,
      evidence_packets: Keyword.get(opts, :evidence_packets, []),
      verifier_outputs: Keyword.get(opts, :verifier_outputs, []),
      approval_records: Keyword.get(opts, :approval_records, []),
      observations: Keyword.get(opts, :observations, []),
      persistence_commit: Keyword.get(opts, :persistence_commit),
      idempotent_replay: Keyword.get(opts, :idempotent_replay, false),
      effect_count: Keyword.get(opts, :effect_count, 0),
      reason: Keyword.get(opts, :reason)
    }
  end

  defp reject_without_effect(step, state, journal, reason) do
    {:error, base_outcome(step, state, journal, reason: reason)}
  end

  defp promote_candidate(context) do
    File.mkdir_p!(Path.dirname(context.committed_path))
    temporary = context.committed_path <> ".vanta-promoting"
    File.cp!(context.candidate_path, temporary)
    File.rename!(temporary, context.committed_path)
    :ok
  rescue
    error -> {:error, {:promotion_failed, Exception.message(error)}}
  end

  defp rollback_effect(persistence, recovery_record, workspace) do
    case Recovery.recover_episode(persistence, recovery_record["episode_id"], workspace) do
      {:ok, %{outcomes: outcomes}} ->
        cond do
          Enum.any?(outcomes, &(&1["status"] == "rolled_back")) -> "completed"
          Enum.any?(outcomes, &(&1["status"] == "recovery_required")) -> "failed"
          true -> "failed"
        end

      {:error, _reason} ->
        "failed"
    end
  end

  defp inject_after_prepare(opts) do
    if failure_point(opts) == :crash_after_prepare_before_effect,
      do: {:error, {:injected_crash, :crash_after_prepare_before_effect}},
      else: :ok
  end

  defp inject_journal_ref_failure(journal, opts) do
    case failure_point(opts) do
      :corrupted_evidence_ref ->
        Map.put(journal, "evidence_refs", ["corrupt_evidence_ref"])

      :missing_journal_refs ->
        journal |> Map.put("approval_record_refs", []) |> Map.put("artifact_refs", [])

      _point ->
        journal
    end
  end

  defp transaction_failure(opts) do
    if failure_point(opts) in [:transaction_rollback_after_state, :rollback_failure],
      do: "transaction_rollback_after_state",
      else: nil
  end

  defp maybe_corrupt_backup(workspace, recovery_record, opts) do
    if failure_point(opts) == :rollback_failure do
      backup_path = get_in(recovery_record, ["backup_metadata", "backup_path"])

      if is_binary(backup_path) do
        workspace |> PathGuard.resolve!(backup_path) |> File.write!("corrupted rollback backup")
      end
    end

    :ok
  end

  defp compare_workspace_hashes(mismatches, workspace, step, target_hash) do
    identity = step["action_payload"]["target_identity"]

    [
      {identity["source_path"], step["action_payload"]["source_hash"], "source_hash"},
      {identity["candidate_path"], step["action_payload"]["candidate_hash"], "candidate_hash"},
      {identity["committed_path"], target_hash, "committed_hash"}
    ]
    |> Enum.reduce(mismatches, fn {relative, expected, label}, acc ->
      case PathGuard.safe_resolve(workspace, relative) do
        {:ok, path} when is_binary(expected) ->
          mismatch_unless(acc, File.regular?(path) and Hash.file_hash(path) == expected, label)

        _other ->
          [label | acc]
      end
    end)
  end

  defp request_identity(task, step, state) do
    %{
      "episode_id" => step["episode_id"],
      "task_id" => task["task_id"],
      "step_id" => step["step_id"],
      "action_type" => step["action_type"],
      "action_payload" => step["action_payload"],
      "side_effect_class" => step["side_effect_class"],
      "pre_state_hash" => state["state_hash"],
      "runtime_schema_version" => Vanta.schema_version(),
      "hash_policy_version" => Vanta.hash_policy_version(),
      "gate_policy_version" => "PS1-LC-FIXTURE-COMMIT-GATE-001"
    }
  end

  defp load_marker(path) do
    if File.regular?(path) do
      case Jason.decode(File.read!(path)) do
        {:ok, marker} -> {:ok, marker}
        {:error, _reason} -> {:error, :workspace_marker_invalid_json}
      end
    else
      {:error, :workspace_marker_missing}
    end
  end

  defp validate_marker(marker, identity) do
    cond do
      marker["scope"] != @marker_scope ->
        {:error, :workspace_marker_scope_invalid}

      marker["ephemeral"] != true ->
        {:error, :workspace_not_ephemeral}

      marker["fixture_id"] != identity["fixture_id"] ->
        {:error, :workspace_fixture_identity_mismatch}

      marker["workspace_id"] != identity["workspace_id"] ->
        {:error, :workspace_identity_mismatch}

      true ->
        :ok
    end
  end

  defp require_prefix(path, prefix, error) when is_binary(path) do
    normalized = PathGuard.normalize_separator(path)
    if String.starts_with?(normalized, prefix), do: :ok, else: {:error, error}
  end

  defp require_prefix(_path, _prefix, error), do: {:error, error}

  defp require_distinct_paths(identity) do
    paths = [identity["source_path"], identity["candidate_path"], identity["committed_path"]]
    if length(Enum.uniq(paths)) == 3, do: :ok, else: {:error, :source_candidate_target_overlap}
  end

  defp require_regular(path, error), do: if(File.regular?(path), do: :ok, else: {:error, error})
  defp require_equal(left, right, _error) when left == right, do: :ok
  defp require_equal(_left, _right, error), do: {:error, error}

  defp parse_time(value) do
    case DateTime.from_iso8601(value) do
      {:ok, datetime, _offset} -> {:ok, datetime}
      _other -> {:error, :approval_time_invalid}
    end
  end

  defp complete_pre_evidence?(evidence) do
    observation = Map.get(evidence, "observation", %{})

    Schema.validate("evidence_packet", evidence) == :ok and
      evidence["evidence_phase"] == "pre_effect" and
      is_map(evidence["target_identity"]) and
      length(Map.get(evidence, "approval_record_refs", [])) == 1 and
      length(Map.get(evidence, "artifact_refs", [])) == 1 and
      Enum.all?(
        ~w(source_hash candidate_hash target_pre_hash approval_record_ref approval_policy_version idempotency_key request_hash rollback_policy),
        &Map.has_key?(observation, &1)
      )
  end

  defp schema_valid_approval(nil), do: nil

  defp schema_valid_approval(record),
    do: if(Schema.validate("approval_record", record) == :ok, do: record, else: nil)

  defp maybe_persist_approval(_persistence, _episode_id, nil), do: :ok

  defp maybe_persist_approval(persistence, episode_id, approval) do
    case Persistence.append_immutable_artifact(
           persistence,
           "approval_record",
           episode_id,
           approval
         ) do
      {:ok, _artifact} -> :ok
      {:error, _reason} = error -> error
    end
  end

  defp maybe_persist_evidence(persistence, episode_id, evidence) do
    if Schema.validate("evidence_packet", evidence) == :ok do
      case Persistence.append_immutable_artifact(
             persistence,
             "evidence_packet",
             episode_id,
             evidence
           ) do
        {:ok, _artifact} -> :ok
        {:error, _reason} = error -> error
      end
    else
      :ok
    end
  end

  defp load_result_artifacts(persistence, result) do
    result["artifact_ids"]
    |> Enum.reduce_while({:ok, []}, fn id, {:ok, acc} ->
      case Persistence.load_artifact(persistence, id) do
        {:ok, artifact} -> {:cont, {:ok, acc ++ [artifact]}}
        {:error, reason} -> {:halt, {:error, reason}}
      end
    end)
  end

  defp payloads(artifacts, type) do
    artifacts
    |> Enum.filter(&(&1["artifact_type"] == type))
    |> Enum.sort_by(& &1["created_sequence"])
    |> Enum.map(& &1["payload"])
  end

  defp last_payload(artifacts, type), do: artifacts |> payloads(type) |> List.last()
  defp final_state_hash(journal), do: journal |> Map.get("state_hashes", []) |> List.last()
  defp failure_point(opts), do: Keyword.get(opts, :failure_injection)
  defp mismatch_unless(mismatches, true, _label), do: mismatches
  defp mismatch_unless(mismatches, _false, label), do: [label | mismatches]
end
