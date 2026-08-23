defmodule Vanta.ReplayRunner do
  @moduledoc """
  Replays Stage 1 episode journals against a clean fixture workspace.
  """

  alias Vanta.Runtime

  def replay(task, source_workspace, journal, artifacts \\ %{}, opts \\ []) do
    action_sequence = %{
      "actions" =>
        journal
        |> Map.get("steps", [])
        |> Enum.filter(&Map.has_key?(&1, "action_type"))
        |> Enum.map(fn step ->
          %{
            "action_type" => step["action_type"],
            "action_payload" => Map.get(step, "action_payload", %{})
          }
        end)
    }

    replay_episode_id = Keyword.get(opts, :episode_id, journal["episode_id"])

    case Runtime.run_task(task, source_workspace,
           action_sequence: action_sequence,
           episode_id: replay_episode_id
         ) do
      {:ok, result} ->
        expected_last_hash = journal |> Map.get("state_hashes", []) |> List.last()
        actual_last_hash = result.journal |> Map.get("state_hashes", []) |> List.last()
        expected_status = journal["commit_status"]
        actual_status = result.status
        expected_step_count = journal |> Map.get("steps", []) |> length()
        actual_step_count = result.journal |> Map.get("steps", []) |> length()
        expected_observation_signatures = observation_signatures(journal, artifacts)

        actual_observation_signatures =
          observation_signatures(result.journal, %{
            evidence_packets: result.evidence_packets
          })

        status_match? = actual_status == expected_status
        state_hash_match? = is_nil(expected_last_hash) or expected_last_hash == actual_last_hash
        step_count_match? = expected_step_count == actual_step_count

        observation_match? =
          expected_observation_signatures == [] or
            expected_observation_signatures == actual_observation_signatures

        strict_result =
          if Keyword.get(opts, :strict?, false) do
            strict_fidelity(journal, artifacts, result, opts)
          else
            %{consistent?: true, mismatches: []}
          end

        consistent? =
          status_match? and state_hash_match? and step_count_match? and observation_match? and
            strict_result.consistent?

        {:ok,
         %{
           consistent?: consistent?,
           replay_result: result,
           expected_commit_status: expected_status,
           actual_commit_status: actual_status,
           expected_state_hash: expected_last_hash,
           actual_state_hash: actual_last_hash,
           expected_step_count: expected_step_count,
           actual_step_count: actual_step_count,
           status_match?: status_match?,
           state_hash_match?: state_hash_match?,
           step_count_match?: step_count_match?,
           observation_match?: observation_match?,
           fidelity_mismatches: strict_result.mismatches
         }}

      {:error, reason} ->
        {:error, reason}
    end
  end

  def strict_fidelity(expected_journal, artifacts, actual_result, opts \\ []) do
    expected_evidence = artifact_list(artifacts, :evidence_packets)
    expected_verifiers = artifact_list(artifacts, :verifier_outputs)
    expected_steps = Map.get(expected_journal, "steps", [])
    actual_journal = actual_result.journal

    comparisons = [
      {"episode_identity", expected_journal["episode_id"], actual_journal["episode_id"]},
      {"task_identity", expected_journal["task_id"], actual_journal["task_id"]},
      {"runtime_version", get_in(expected_journal, ["runtime_manifest", "runtime_version"]),
       get_in(actual_journal, ["runtime_manifest", "runtime_version"])},
      {"schema_version", expected_journal["schema_version"], actual_journal["schema_version"]},
      {"step_sequence", step_signatures(expected_steps),
       step_signatures(actual_journal["steps"])},
      {"commit_status", expected_journal["commit_status"], actual_journal["commit_status"]},
      {"rollback_status", expected_journal["rollback_status"], actual_journal["rollback_status"]},
      {"recovery_status", Keyword.get(opts, :expected_recovery_status, "not_required"),
       Keyword.get(opts, :actual_recovery_status, "not_required")},
      {"state_hash_sequence", expected_journal["state_hashes"], actual_journal["state_hashes"]},
      {"evidence_refs", expected_journal["evidence_refs"], actual_journal["evidence_refs"]},
      {"verifier_output_refs", expected_journal["verifier_output_refs"],
       actual_journal["verifier_output_refs"]},
      {"observation_signatures", observation_signatures(expected_journal, artifacts),
       observation_signatures(actual_journal, %{evidence_packets: actual_result.evidence_packets})},
      {"final_accepted_state_hash", List.last(expected_journal["state_hashes"] || []),
       List.last(actual_journal["state_hashes"] || [])}
    ]

    missing =
      []
      |> require_nonempty("expected_steps", expected_steps)
      |> require_nonempty("expected_evidence_packets", expected_evidence)
      |> require_nonempty("expected_verifier_outputs", expected_verifiers)

    mismatches =
      comparisons
      |> Enum.flat_map(fn
        {name, nil, _actual} -> [name <> ":missing_expected"]
        {name, _expected, nil} -> [name <> ":missing_actual"]
        {_name, same, same} -> []
        {name, _expected, _actual} -> [name <> ":mismatch"]
      end)
      |> Kernel.++(missing)
      |> Enum.sort()

    %{consistent?: mismatches == [], mismatches: mismatches, comparisons: comparisons}
  end

  defp step_signatures(steps) do
    Enum.map(steps || [], fn step ->
      %{
        "step_id" => step["step_id"],
        "action_type" => step["action_type"],
        "side_effect_class" => step["side_effect_class"],
        "status" => step["status"]
      }
    end)
  end

  defp require_nonempty(missing, name, []), do: [name | missing]
  defp require_nonempty(missing, _name, _values), do: missing

  defp observation_signatures(journal, artifacts) do
    evidence_by_id =
      artifacts
      |> artifact_list(:evidence_packets)
      |> Map.new(&{&1["evidence_id"], &1})

    journal
    |> Map.get("evidence_refs", [])
    |> Enum.flat_map(fn ref ->
      case Map.fetch(evidence_by_id, ref) do
        {:ok, evidence} -> [observation_signature(evidence["observation"])]
        :error -> []
      end
    end)
  end

  defp observation_signature(observation) do
    %{
      "kind" => observation["kind"],
      "path" => observation["path"],
      "selector_status" => get_in(observation, ["selector_resolution", "status"]),
      "diff" => observation["diff"],
      "before_hash" => observation["before_hash"],
      "after_hash" => observation["after_hash"],
      "passed" => observation["passed"],
      "failures" => observation["failures"]
    }
  end

  defp artifact_list(artifacts, key) do
    Map.get(artifacts, key) || Map.get(artifacts, Atom.to_string(key)) || []
  end
end
