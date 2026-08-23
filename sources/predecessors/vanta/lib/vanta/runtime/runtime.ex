defmodule Vanta.Runtime do
  @moduledoc """
  Stage 1 closed-loop runtime orchestration with optional Persistence v0.
  """

  alias Vanta.{
    ActionExecutor,
    CommitController,
    EpisodeJournal,
    EvidenceBuilder,
    ExecutionIRCompiler,
    FixtureAcceptance,
    FixtureCommit,
    Persistence,
    PlannerAdapter,
    StateManager,
    VerifierRuntime
  }

  alias Vanta.Persistence.Recovery

  def run_task(task, source_workspace, opts \\ []) do
    workspace = prepare_workspace(source_workspace, opts)
    episode_id = Keyword.get(opts, :episode_id, "episode_#{Map.fetch!(task, "task_id")}")

    with {:ok, action_sequence} <- action_sequence(task, workspace, opts),
         {:ok, persistence, owned?} <- acquire_persistence(opts) do
      initial_state = StateManager.from_task(task)

      initial_journal =
        task
        |> EpisodeJournal.new(episode_id)
        |> EpisodeJournal.record_state(initial_state)

      result =
        with :ok <- initialize_persistence(persistence, task, initial_state, initial_journal) do
          initial_acc = %{
            state: initial_state,
            journal: initial_journal,
            steps: [],
            evidence_packets: [],
            verifier_outputs: [],
            approval_records: [],
            observations: [],
            invalid_actions: 0,
            rollback_status: "not_applicable",
            status: "committed",
            stop?: false,
            crash: nil,
            persistence: persistence,
            persistence_commits: [],
            idempotent_replays: 0,
            committable_effect_count: 0
          }

          acc =
            action_sequence["actions"]
            |> Enum.with_index(1)
            |> Enum.reduce_while(initial_acc, fn {action, occurrence_index}, acc ->
              case run_action(task, workspace, episode_id, action, occurrence_index, acc, opts) do
                %{stop?: true} = next_acc -> {:halt, next_acc}
                next_acc -> {:cont, next_acc}
              end
            end)

          finalize_run(task, workspace, episode_id, action_sequence, acc)
        end

      if owned? and persistence, do: Persistence.close(persistence)
      result
    end
  end

  defp finalize_run(_task, workspace, episode_id, _action_sequence, %{crash: point} = acc)
       when not is_nil(point) do
    {:error,
     {:injected_crash, point,
      %{
        workspace: workspace,
        episode_id: episode_id,
        persistence: persistence_descriptor(acc.persistence),
        persistence_commits: acc.persistence_commits
      }}}
  end

  defp finalize_run(task, workspace, episode_id, action_sequence, acc) do
    journal =
      acc.journal
      |> EpisodeJournal.set_commit_status(acc.status)
      |> EpisodeJournal.set_rollback_status(acc.rollback_status)
      |> EpisodeJournal.validate!()

    task_success? =
      FixtureAcceptance.evaluate_task(
        workspace,
        acc.status,
        acc.invalid_actions,
        acc.observations
      )

    {:ok,
     %{
       arm: :treatment,
       task: task,
       workspace: workspace,
       episode_id: episode_id,
       action_sequence: action_sequence,
       state: acc.state,
       steps: acc.steps,
       evidence_packets: acc.evidence_packets,
       verifier_outputs: acc.verifier_outputs,
       approval_records: acc.approval_records,
       journal: journal,
       observations: acc.observations,
       total_actions: length(action_sequence["actions"]),
       invalid_actions: acc.invalid_actions,
       status: acc.status,
       rollback_status: acc.rollback_status,
       task_success?: task_success?,
       persistence: persistence_descriptor(acc.persistence),
       persistence_commits: acc.persistence_commits,
       idempotent_replays: acc.idempotent_replays,
       committable_effect_count: acc.committable_effect_count
     }}
  end

  defp action_sequence(task, workspace, opts) do
    cond do
      Keyword.has_key?(opts, :action_sequence) ->
        PlannerAdapter.propose_actions(task, workspace,
          action_sequence: Keyword.fetch!(opts, :action_sequence)
        )

      Keyword.has_key?(opts, :planner) ->
        planner = Keyword.fetch!(opts, :planner)
        planner.propose_actions(task, workspace, opts)

      true ->
        FixtureAcceptance.action_sequence(workspace)
    end
  end

  defp run_action(task, workspace, episode_id, action, occurrence_index, acc, opts) do
    action_type = action["action_type"]
    payload = action["action_payload"]

    case ExecutionIRCompiler.compile(task, episode_id, action_type, payload, occurrence_index) do
      {:ok, step} ->
        run_compiled_action(task, workspace, step, acc, opts)

      {:error, reason} ->
        rejected_step =
          ExecutionIRCompiler.rejected_step(
            task,
            episode_id,
            action_type,
            payload,
            reason,
            occurrence_index
          )

        failure_observation = %{
          "kind" => action_type,
          "error" => inspect(reason),
          "mutated" => false
        }

        evidence = EvidenceBuilder.build(acc.state, rejected_step, failure_observation)

        verifier_output =
          VerifierRuntime.verify(rejected_step, evidence, %{
            task: task,
            workspace: workspace,
            compile_error: reason
          })

        next_acc = %{
          acc
          | steps: acc.steps ++ [rejected_step],
            journal:
              acc.journal
              |> EpisodeJournal.record_step(rejected_step)
              |> EpisodeJournal.record_evidence(evidence)
              |> EpisodeJournal.record_verifier_output(verifier_output),
            evidence_packets: acc.evidence_packets ++ [evidence],
            verifier_outputs: acc.verifier_outputs ++ [verifier_output],
            observations: acc.observations ++ [failure_observation],
            invalid_actions: acc.invalid_actions + 1,
            status: "rejected",
            stop?: true
        }

        persist_rejected(next_acc, rejected_step, evidence, verifier_output)
    end
  end

  defp run_compiled_action(
         task,
         workspace,
         %{"action_type" => "commit_fixture_document_candidate"} = step,
         acc,
         opts
       ) do
    case FixtureCommit.execute(
           task,
           workspace,
           step,
           acc.state,
           acc.journal,
           acc.persistence,
           opts
         ) do
      {:ok, outcome} ->
        merge_fixture_commit_outcome(acc, outcome)

      {:error, outcome} ->
        acc
        |> merge_fixture_commit_outcome(outcome)
        |> Map.update!(:invalid_actions, &(&1 + 1))
        |> Map.put(:stop?, true)

      {:crash, point, outcome} ->
        acc
        |> merge_fixture_commit_outcome(outcome)
        |> Map.put(:crash, point)
        |> Map.put(:stop?, true)
    end
  end

  defp run_compiled_action(task, workspace, step, acc, opts) do
    identity = request_identity(task, step, acc.state)
    request_hash = Persistence.logical_request_hash(%{"request_identity" => identity})
    key = logical_key(step, opts)

    case lookup_existing(acc.persistence, key, request_hash) do
      {:ok, result} ->
        restore_existing_commit(acc, result)

      {:error, :idempotency_conflict} ->
        _ =
          maybe_set_status(acc.persistence, step["episode_id"], "rejected", %{
            "recovery_status" => "idempotency_conflict"
          })

        %{
          acc
          | invalid_actions: acc.invalid_actions + 1,
            status: "rejected",
            stop?: true
        }

      :not_found ->
        with {:ok, recovery_record} <- maybe_prepare(acc.persistence, workspace, step, acc.state),
             :ok <- maybe_inject_after_prepare(step, recovery_record, opts) do
          execute_and_verify(
            task,
            workspace,
            step,
            acc,
            recovery_record,
            key,
            identity,
            opts
          )
        else
          {:error, {:injected_crash, point}} ->
            %{acc | crash: point, stop?: true, status: "aborted"}

          {:error, reason} ->
            _ =
              maybe_set_status(acc.persistence, step["episode_id"], "recovery_required", %{
                "recovery_status" => inspect(reason)
              })

            %{acc | crash: {:persistence_prepare_failed, reason}, stop?: true, status: "aborted"}
        end
    end
  end

  defp merge_fixture_commit_outcome(acc, outcome) do
    step_status =
      case outcome.status do
        "committed" -> "committed"
        "aborted" -> "aborted"
        _status -> "rejected"
      end

    step = Map.put(outcome.step, "status", step_status)

    journal =
      outcome.journal
      |> ensure_journal_step(step)
      |> record_fixture_commit_refs(
        outcome.evidence_packets,
        outcome.verifier_outputs,
        outcome.approval_records
      )
      |> EpisodeJournal.record_state(outcome.state)
      |> EpisodeJournal.set_commit_status(outcome.status)
      |> EpisodeJournal.set_rollback_status(outcome.rollback_status)

    %{
      acc
      | state: outcome.state,
        journal: journal,
        steps: append_unique_by_id(acc.steps, step, "step_id"),
        evidence_packets:
          append_unique_many(acc.evidence_packets, outcome.evidence_packets, "evidence_id"),
        verifier_outputs:
          append_unique_many(
            acc.verifier_outputs,
            outcome.verifier_outputs,
            "verifier_output_id"
          ),
        approval_records:
          append_unique_many(acc.approval_records, outcome.approval_records, "approval_id"),
        observations: acc.observations ++ outcome.observations,
        rollback_status: outcome.rollback_status,
        status: outcome.status,
        persistence_commits: acc.persistence_commits ++ List.wrap(outcome.persistence_commit),
        idempotent_replays:
          acc.idempotent_replays + if(outcome.idempotent_replay, do: 1, else: 0),
        committable_effect_count: acc.committable_effect_count + outcome.effect_count
    }
  end

  defp ensure_journal_step(journal, step) do
    if Enum.any?(journal["steps"], &(&1["step_id"] == step["step_id"])) do
      journal
    else
      EpisodeJournal.record_step(journal, step)
    end
  end

  defp record_fixture_commit_refs(journal, evidence, verifiers, approvals) do
    journal = Enum.reduce(evidence, journal, &EpisodeJournal.record_evidence(&2, &1))
    journal = Enum.reduce(verifiers, journal, &EpisodeJournal.record_verifier_output(&2, &1))
    Enum.reduce(approvals, journal, &EpisodeJournal.record_approval(&2, &1))
  end

  defp append_unique_many(values, new_values, key) do
    Enum.reduce(new_values, values, &append_unique_by_id(&2, &1, key))
  end

  defp append_unique_by_id(values, value, key) do
    if Enum.any?(values, &(&1[key] == value[key])), do: values, else: values ++ [value]
  end

  defp execute_and_verify(task, workspace, step, acc, recovery_record, key, identity, opts) do
    case safe_execute(workspace, step) do
      {:ok, observation} ->
        with {:ok, recovery_record} <-
               maybe_mark_effect_applied(acc.persistence, recovery_record),
             :ok <- maybe_inject_before_evidence(opts) do
          evidence = EvidenceBuilder.build(acc.state, step, observation)

          verifier_output =
            VerifierRuntime.verify(step, evidence, %{
              task: task,
              workspace: workspace,
              observations: acc.observations ++ [observation]
            })

          recorded_step = step_with_status(step, verifier_output["decision"])

          next_journal =
            acc.journal
            |> EpisodeJournal.record_step(recorded_step)
            |> EpisodeJournal.record_evidence(evidence)
            |> EpisodeJournal.record_verifier_output(verifier_output)

          next_acc = %{
            acc
            | journal: next_journal,
              steps: acc.steps ++ [recorded_step],
              evidence_packets: acc.evidence_packets ++ [evidence],
              verifier_outputs: acc.verifier_outputs ++ [verifier_output],
              observations: acc.observations ++ [observation]
          }

          handle_verifier_decision(
            workspace,
            step,
            evidence,
            verifier_output,
            observation,
            next_acc,
            recovery_record,
            key,
            identity,
            opts
          )
        else
          {:error, {:injected_crash, point}} ->
            %{acc | crash: point, stop?: true, status: "aborted"}

          {:error, reason} ->
            %{acc | crash: {:effect_persistence_failed, reason}, stop?: true, status: "aborted"}
        end

      {:error, reason} ->
        failure_observation = %{
          "kind" => step["action_type"],
          "error" => inspect(reason),
          "mutated" => false
        }

        evidence = EvidenceBuilder.build(acc.state, step, failure_observation)

        verifier_output =
          VerifierRuntime.verify(step, evidence, %{task: task, workspace: workspace})

        failed_step = Map.put(step, "status", "failed")

        next_acc = %{
          acc
          | journal:
              acc.journal
              |> EpisodeJournal.record_step(failed_step)
              |> EpisodeJournal.record_evidence(evidence)
              |> EpisodeJournal.record_verifier_output(verifier_output),
            steps: acc.steps ++ [failed_step],
            evidence_packets: acc.evidence_packets ++ [evidence],
            verifier_outputs: acc.verifier_outputs ++ [verifier_output],
            observations: acc.observations ++ [failure_observation],
            invalid_actions: acc.invalid_actions + 1,
            status: "rejected",
            stop?: true
        }

        persist_rejected(next_acc, failed_step, evidence, verifier_output)
    end
  end

  defp handle_verifier_decision(
         workspace,
         step,
         evidence,
         verifier_output,
         observation,
         acc,
         recovery_record,
         key,
         identity,
         opts
       ) do
    if verifier_output["decision"] == "accept" do
      case CommitController.commit(acc.state, step, evidence, verifier_output) do
        {:ok, committed_state} ->
          rollback_status = rollback_status_after_commit(step, acc.rollback_status)

          committed_journal =
            acc.journal
            |> EpisodeJournal.record_state(committed_state)
            |> EpisodeJournal.set_commit_status("committed")
            |> EpisodeJournal.set_rollback_status(rollback_status)
            |> EpisodeJournal.validate!()

          request = %{
            "episode_id" => step["episode_id"],
            "idempotency_key" => key,
            "request_identity" => identity,
            "state" => committed_state,
            "journal" => committed_journal,
            "steps" => [List.last(acc.steps)],
            "evidence_packets" => [evidence],
            "verifier_outputs" => [verifier_output],
            "failure_injection" => transaction_injection(opts)
          }

          case persist_commit(acc.persistence, request) do
            {:ok, commit_result} ->
              _ = maybe_mark_commit_completed(acc.persistence, recovery_record)

              next_acc = %{
                acc
                | state: committed_state,
                  journal: committed_journal,
                  rollback_status: rollback_status,
                  persistence_commits: acc.persistence_commits ++ List.wrap(commit_result)
              }

              if failure_point(opts) == :after_db_commit_before_response do
                %{next_acc | crash: :after_db_commit_before_response, stop?: true}
              else
                next_acc
              end

            {:error, reason} ->
              rollback_status =
                rollback_after_commit_failure(
                  acc.persistence,
                  recovery_record,
                  workspace,
                  step,
                  observation
                )

              %{
                acc
                | invalid_actions: acc.invalid_actions + 1,
                  status: "rejected",
                  stop?: true,
                  rollback_status: rollback_status,
                  steps: mark_last_step(acc.steps, "rejected", inspect(reason))
              }
          end

        {:error, reason} ->
          next_acc = %{
            acc
            | invalid_actions: acc.invalid_actions + 1,
              status: "rejected",
              stop?: true,
              steps: mark_last_step(acc.steps, "rejected", inspect(reason))
          }

          persist_rejected(next_acc, List.last(next_acc.steps), evidence, verifier_output)
      end
    else
      rollback_status =
        rollback_rejected_effect(
          acc.persistence,
          recovery_record,
          workspace,
          step,
          observation
        )

      next_acc = %{
        acc
        | invalid_actions: acc.invalid_actions + 1,
          rollback_status: rollback_status,
          status: "rejected",
          stop?: true
      }

      persist_rejected(next_acc, List.last(next_acc.steps), evidence, verifier_output)
    end
  end

  defp persist_commit(nil, _request), do: {:ok, nil}
  defp persist_commit(context, request), do: Persistence.commit_episode(context, request)

  defp persist_rejected(%{persistence: nil} = acc, _step, _evidence, _verifier), do: acc

  defp persist_rejected(acc, step, evidence, verifier) do
    episode_id = step["episode_id"]

    result =
      with {:ok, _step_artifact} <-
             Persistence.append_immutable_artifact(
               acc.persistence,
               "execution_step",
               episode_id,
               step
             ),
           {:ok, _evidence_artifact} <-
             Persistence.append_immutable_artifact(
               acc.persistence,
               "evidence_packet",
               episode_id,
               evidence
             ),
           {:ok, _verifier_artifact} <-
             Persistence.record_verifier_result(acc.persistence, episode_id, verifier),
           {:ok, _episode} <-
             Persistence.set_episode_status(acc.persistence, episode_id, "rejected", %{
               "recovery_status" => "rejected_before_commit"
             }) do
        :ok
      end

    case result do
      :ok -> acc
      {:error, reason} -> %{acc | crash: {:rejected_artifact_persistence_failed, reason}}
    end
  end

  defp restore_existing_commit(acc, result) do
    with {:ok, artifacts} <- load_commit_artifacts(acc.persistence, result) do
      state = find_payload(artifacts, "canonical_state") || acc.state
      journal = find_payload(artifacts, "episode_journal") || acc.journal
      step = find_payload(artifacts, "execution_step")
      evidence = find_payload(artifacts, "evidence_packet")
      verifier = find_payload(artifacts, "verifier_output")
      observation = if evidence, do: evidence["observation"], else: nil

      %{
        acc
        | state: state,
          journal: journal,
          steps: append_if(acc.steps, step),
          evidence_packets: append_if(acc.evidence_packets, evidence),
          verifier_outputs: append_if(acc.verifier_outputs, verifier),
          observations: append_if(acc.observations, observation),
          rollback_status: journal["rollback_status"] || acc.rollback_status,
          status: journal["commit_status"] || "committed",
          persistence_commits:
            acc.persistence_commits ++ [Map.put(result, "idempotent_replay", true)],
          idempotent_replays: acc.idempotent_replays + 1
      }
    else
      {:error, reason} -> %{acc | crash: {:idempotent_restore_failed, reason}, stop?: true}
    end
  end

  defp load_commit_artifacts(nil, _result), do: {:error, :persistence_not_configured}

  defp load_commit_artifacts(context, result) do
    result["artifact_ids"]
    |> Enum.reduce_while({:ok, []}, fn id, {:ok, acc} ->
      case Persistence.load_artifact(context, id) do
        {:ok, artifact} -> {:cont, {:ok, acc ++ [artifact]}}
        {:error, reason} -> {:halt, {:error, reason}}
      end
    end)
  end

  defp find_payload(artifacts, type) do
    artifacts
    |> Enum.find(&(&1["artifact_type"] == type))
    |> case do
      nil -> nil
      artifact -> artifact["payload"]
    end
  end

  defp lookup_existing(nil, _key, _request_hash), do: :not_found

  defp lookup_existing(context, key, request_hash) do
    Persistence.lookup_logical_commit(context, key, request_hash)
  end

  defp maybe_prepare(nil, _workspace, _step, _state), do: {:ok, nil}

  defp maybe_prepare(context, workspace, %{"side_effect_class" => "REVERSIBLE"} = step, state) do
    Recovery.prepare(context, workspace, step, state["state_hash"])
  end

  defp maybe_prepare(_context, _workspace, _step, _state), do: {:ok, nil}

  defp maybe_mark_effect_applied(_context, nil), do: {:ok, nil}

  defp maybe_mark_effect_applied(context, record),
    do: Recovery.mark_effect_applied(context, record)

  defp maybe_mark_commit_completed(_context, nil), do: :ok

  defp maybe_mark_commit_completed(context, record) do
    Persistence.record_recovery_status(
      context,
      record["recovery_id"],
      "commit_completed",
      %{"rollback_status" => "available"}
    )
  end

  defp maybe_inject_after_prepare(_step, nil, _opts), do: :ok

  defp maybe_inject_after_prepare(_step, _record, opts) do
    if failure_point(opts) == :after_prepared_before_effect,
      do: {:error, {:injected_crash, :after_prepared_before_effect}},
      else: :ok
  end

  defp maybe_inject_before_evidence(opts) do
    if failure_point(opts) in [:after_effect_before_evidence, :before_evidence_persist],
      do: {:error, {:injected_crash, failure_point(opts)}},
      else: :ok
  end

  defp transaction_injection(opts) do
    if failure_point(opts) == :transaction_rollback_after_state,
      do: "transaction_rollback_after_state",
      else: nil
  end

  defp rollback_after_commit_failure(nil, _record, workspace, step, observation),
    do: rollback_if_needed(workspace, step, observation)

  defp rollback_after_commit_failure(_context, nil, workspace, step, observation),
    do: rollback_if_needed(workspace, step, observation)

  defp rollback_after_commit_failure(context, record, workspace, _step, _observation) do
    case Recovery.recover_episode(context, record["episode_id"], workspace) do
      {:ok, _summary} -> "completed"
      {:error, _reason} -> "failed"
    end
  end

  defp rollback_rejected_effect(nil, _record, workspace, step, observation),
    do: rollback_if_needed(workspace, step, observation)

  defp rollback_rejected_effect(_context, nil, workspace, step, observation),
    do: rollback_if_needed(workspace, step, observation)

  defp rollback_rejected_effect(context, record, workspace, _step, _observation) do
    case Recovery.recover_episode(context, record["episode_id"], workspace) do
      {:ok, _summary} -> "completed"
      {:error, _reason} -> "failed"
    end
  end

  defp safe_execute(workspace, step) do
    ActionExecutor.execute(workspace, step)
  rescue
    error -> {:error, {:execution_exception, Exception.message(error)}}
  end

  defp rollback_if_needed(workspace, %{"side_effect_class" => "REVERSIBLE"}, %{
         "backup_metadata" => metadata
       }) do
    case ActionExecutor.rollback(workspace, metadata) do
      :ok -> "completed"
      _other -> "failed"
    end
  rescue
    _error -> "failed"
  end

  defp rollback_if_needed(_workspace, %{"side_effect_class" => "REVERSIBLE"}, _observation),
    do: "unavailable"

  defp rollback_if_needed(_workspace, %{"side_effect_class" => "COMPENSABLE"}, _observation),
    do: "compensation_required"

  defp rollback_if_needed(_workspace, _step, _observation), do: "not_applicable"

  defp rollback_status_after_commit(%{"side_effect_class" => "REVERSIBLE"}, _status),
    do: "available"

  defp rollback_status_after_commit(%{"side_effect_class" => "COMPENSABLE"}, _status),
    do: "compensation_required"

  defp rollback_status_after_commit(_step, status), do: status

  defp step_with_status(step, "accept"), do: Map.put(step, "status", "committed")
  defp step_with_status(step, "request_evidence"), do: Map.put(step, "status", "aborted")
  defp step_with_status(step, _decision), do: Map.put(step, "status", "rejected")

  defp mark_last_step([], _status, _error), do: []

  defp mark_last_step(steps, status, error) do
    {prefix, [last]} = Enum.split(steps, -1)
    prefix ++ [last |> Map.put("status", status) |> Map.put("error", error)]
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
      "hash_policy_version" => Vanta.hash_policy_version()
    }
  end

  defp logical_key(step, opts) do
    root = Keyword.get(opts, :idempotency_key, step["episode_id"])
    "#{root}:#{step["step_id"]}"
  end

  defp acquire_persistence(opts) do
    cond do
      match?(%Persistence.Context{}, opts[:persistence]) ->
        {:ok, opts[:persistence], false}

      not is_nil(opts[:persistence_adapter]) and is_atom(opts[:persistence_adapter]) ->
        case Persistence.open(opts[:persistence_adapter], opts[:persistence_opts] || []) do
          {:ok, context} -> {:ok, context, true}
          {:error, _reason} = error -> error
        end

      true ->
        {:ok, nil, false}
    end
  end

  defp initialize_persistence(nil, _task, _state, _journal), do: :ok

  defp initialize_persistence(context, task, state, journal) do
    with {:ok, episode} <- Persistence.create_episode(context, task, journal),
         {:ok, artifacts} <- Persistence.load_artifacts(context, journal["episode_id"]),
         :ok <- maybe_write_initial_artifacts(context, task, state, journal, artifacts),
         :ok <- maybe_mark_running(context, episode) do
      :ok
    end
  end

  defp maybe_write_initial_artifacts(_context, _task, _state, _journal, [_ | _]), do: :ok

  defp maybe_write_initial_artifacts(context, task, state, journal, []) do
    episode_id = journal["episode_id"]

    with {:ok, _runtime_manifest} <-
           Persistence.append_immutable_artifact(
             context,
             "runtime_manifest",
             episode_id,
             journal["runtime_manifest"]
           ),
         {:ok, _episode_metadata} <-
           Persistence.append_immutable_artifact(
             context,
             "episode_metadata",
             episode_id,
             %{"episode_id" => episode_id, "task_id" => task["task_id"]}
           ),
         {:ok, _initial_state} <-
           Persistence.save_canonical_state_snapshot(context, episode_id, state) do
      :ok
    end
  end

  defp maybe_mark_running(_context, %{"lifecycle" => lifecycle}) when lifecycle != "created",
    do: :ok

  defp maybe_mark_running(context, episode) do
    case Persistence.set_episode_status(context, episode["episode_id"], "running") do
      {:ok, _episode} -> :ok
      {:error, _reason} = error -> error
    end
  end

  defp maybe_set_status(nil, _episode_id, _status, _attrs), do: :ok

  defp maybe_set_status(context, episode_id, status, attrs) do
    Persistence.set_episode_status(context, episode_id, status, attrs)
  end

  defp persistence_descriptor(nil), do: nil

  defp persistence_descriptor(%Persistence.Context{adapter: adapter, handle: handle, mode: mode}) do
    %{
      adapter: adapter,
      mode: mode,
      path: if(is_map(handle), do: handle[:path], else: nil),
      storage_schema_version: Vanta.persistence_schema_version(),
      hash_policy_version: Vanta.hash_policy_version()
    }
  end

  defp failure_point(opts), do: Keyword.get(opts, :failure_injection)

  defp append_if(values, nil), do: values
  defp append_if(values, value), do: values ++ [value]

  defp prepare_workspace(source_workspace, opts) do
    if Keyword.get(opts, :copy_workspace?, true) do
      target =
        Path.join(
          System.tmp_dir!(),
          "vanta_runtime_#{Path.basename(source_workspace)}_#{System.unique_integer([:positive])}"
        )

      File.rm_rf!(target)
      File.cp_r!(source_workspace, target)
      target
    else
      source_workspace
    end
  end
end
