defmodule Vanta.Persistence do
  @moduledoc """
  Adapter boundary for Fixture-Local Persistence v0.
  """

  alias Vanta.{Hash, Schema}

  defmodule Context do
    @moduledoc false
    @enforce_keys [:adapter, :handle]
    defstruct [:adapter, :handle, :mode]
  end

  @type context :: %Context{}

  @callback open(keyword()) :: {:ok, term()} | {:error, term()}
  @callback close(term()) :: :ok | {:error, term()}
  @callback create_episode(term(), map()) :: {:ok, map()} | {:error, term()}
  @callback append_immutable_artifact(term(), String.t(), term(), keyword()) ::
              {:ok, map()} | {:error, term()}
  @callback record_prepared_effect(term(), map()) :: {:ok, map()} | {:error, term()}
  @callback record_recovery_status(term(), String.t(), String.t(), map()) ::
              {:ok, map()} | {:error, term()}
  @callback set_episode_status(term(), String.t(), String.t(), map()) ::
              {:ok, map()} | {:error, term()}
  @callback commit_logical(term(), map()) :: {:ok, map()} | {:error, term()}
  @callback lookup_logical_commit(term(), String.t(), String.t()) ::
              :not_found | {:ok, map()} | {:error, term()}
  @callback load_episode(term(), String.t()) :: {:ok, map()} | {:error, term()}
  @callback load_artifact(term(), String.t()) :: {:ok, map()} | {:error, term()}
  @callback load_artifacts(term(), String.t()) :: {:ok, [map()]} | {:error, term()}
  @callback load_recovery_records(term(), String.t()) :: {:ok, [map()]} | {:error, term()}
  @callback list_recoverable_episodes(term()) :: {:ok, [map()]} | {:error, term()}
  @callback verify_artifact_integrity(term(), String.t()) :: :ok | {:error, term()}

  @artifact_schemas %{
    "approval_record" => "approval_record",
    "canonical_state" => "canonical_state",
    "execution_step" => "execution_step",
    "evidence_packet" => "evidence_packet",
    "verifier_output" => "verifier_output",
    "episode_journal" => "episode_journal"
  }

  def open(adapter, opts \\ []) when is_atom(adapter) do
    case adapter.open(opts) do
      {:ok, handle} -> {:ok, %Context{adapter: adapter, handle: handle, mode: opts[:mode]}}
      {:error, _reason} = error -> error
    end
  end

  def close(%Context{adapter: adapter, handle: handle}), do: adapter.close(handle)

  def create_episode(%Context{} = context, task, journal) do
    manifest = %{
      "storage_schema_version" => Vanta.persistence_schema_version(),
      "episode_id" => journal["episode_id"],
      "task_id" => task["task_id"],
      "lifecycle" => "created",
      "runtime_manifest" => journal["runtime_manifest"],
      "runtime_version" => get_in(journal, ["runtime_manifest", "runtime_version"]) || "0.1.0",
      "schema_version" => Vanta.schema_version(),
      "hash_policy_version" => Vanta.hash_policy_version(),
      "accepted_state_artifact_id" => nil,
      "journal_artifact_id" => nil,
      "rollback_status" => "not_applicable",
      "recovery_status" => "not_required",
      "idempotency_keys" => [],
      "created_sequence" => 1,
      "updated_sequence" => 1
    }

    Schema.validate!("persistence_manifest", manifest)
    context.adapter.create_episode(context.handle, manifest)
  end

  def append_immutable_artifact(%Context{} = context, type, episode_id, payload, opts \\ []) do
    with :ok <- validate_typed_payload(type, payload) do
      context.adapter.append_immutable_artifact(
        context.handle,
        type,
        payload,
        Keyword.put(opts, :episode_id, episode_id)
      )
    end
  end

  def save_canonical_state_snapshot(context, episode_id, state, opts \\ []) do
    append_immutable_artifact(context, "canonical_state", episode_id, state, opts)
  end

  def record_verifier_result(context, episode_id, verifier_output, opts \\ []) do
    append_immutable_artifact(context, "verifier_output", episode_id, verifier_output, opts)
  end

  def record_prepared_effect(%Context{} = context, record) do
    context.adapter.record_prepared_effect(context.handle, record)
  end

  def record_recovery_status(%Context{} = context, recovery_id, status, attrs \\ %{}) do
    context.adapter.record_recovery_status(context.handle, recovery_id, status, attrs)
  end

  def set_episode_status(%Context{} = context, episode_id, status, attrs \\ %{}) do
    context.adapter.set_episode_status(context.handle, episode_id, status, attrs)
  end

  def commit_episode(%Context{} = context, request) do
    request = stringify_keys(request)

    with :ok <- validate_commit_request(request) do
      request_hash = logical_request_hash(request)

      request =
        request
        |> Map.put("request_hash", request_hash)
        |> Map.put_new("schema_version", Vanta.schema_version())
        |> Map.put_new("hash_policy_version", Vanta.hash_policy_version())

      context.adapter.commit_logical(context.handle, request)
    end
  end

  def logical_request_hash(request) do
    request
    |> stringify_keys()
    |> then(fn normalized -> Map.get(normalized, "request_identity", normalized) end)
    |> Map.drop(["failure_injection", "request_hash"])
    |> Hash.canonical_json_hash()
  end

  def lookup_logical_commit(%Context{} = context, key, request_hash) do
    context.adapter.lookup_logical_commit(context.handle, key, request_hash)
  end

  def load_episode(%Context{} = context, episode_id) do
    context.adapter.load_episode(context.handle, episode_id)
  end

  def load_artifact(%Context{} = context, artifact_id) do
    context.adapter.load_artifact(context.handle, artifact_id)
  end

  def load_artifacts(%Context{} = context, episode_id) do
    context.adapter.load_artifacts(context.handle, episode_id)
  end

  def load_recovery_records(%Context{} = context, episode_id) do
    context.adapter.load_recovery_records(context.handle, episode_id)
  end

  def list_recoverable_episodes(%Context{} = context) do
    context.adapter.list_recoverable_episodes(context.handle)
  end

  def verify_artifact_integrity(%Context{} = context, artifact_id) do
    context.adapter.verify_artifact_integrity(context.handle, artifact_id)
  end

  def verify_episode_audit(%Context{} = context, episode_id) do
    with {:ok, episode} <- load_episode(context, episode_id),
         {:ok, artifacts} <- load_artifacts(context, episode_id) do
      by_id = Map.new(artifacts, &{&1["artifact_id"], &1})
      state_id = episode["accepted_state_artifact_id"]
      journal_id = episode["journal_artifact_id"]
      state = by_id[state_id]
      journal = by_id[journal_id]

      evidence_ids =
        artifacts
        |> Enum.filter(&(&1["artifact_type"] == "evidence_packet"))
        |> MapSet.new(&get_in(&1, ["payload", "evidence_id"]))

      verifier_ids =
        artifacts
        |> Enum.filter(&(&1["artifact_type"] == "verifier_output"))
        |> MapSet.new(&get_in(&1, ["payload", "verifier_output_id"]))

      approval_ids =
        artifacts
        |> Enum.filter(&(&1["artifact_type"] == "approval_record"))
        |> MapSet.new(&get_in(&1, ["payload", "approval_id"]))

      missing =
        []
        |> require_pointer("accepted_state_artifact", state_id, state)
        |> require_pointer("episode_journal_artifact", journal_id, journal)
        |> require_journal_refs(journal, evidence_ids, verifier_ids)
        |> require_approval_refs(journal, approval_ids)
        |> require_committed_artifact_refs(journal)
        |> require_final_hash(journal, state)
        |> Enum.sort()

      {:ok, %{complete?: missing == [], missing: missing}}
    end
  end

  def validate_typed_payload(type, payload) do
    case Map.fetch(@artifact_schemas, type) do
      {:ok, schema} -> Schema.validate(schema, payload)
      :error -> :ok
    end
  end

  def build_artifact(type, episode_id, payload, sequence, opts \\ []) do
    artifact = %{
      "artifact_id" =>
        Keyword.get(opts, :artifact_id, "artifact_#{episode_id}_#{type}_#{sequence}"),
      "artifact_type" => type,
      "schema_version" => Keyword.get(opts, :schema_version, Vanta.schema_version()),
      "episode_id" => episode_id,
      "content_hash" => Hash.canonical_json_hash(payload),
      "created_sequence" => sequence,
      "provenance" => Keyword.get(opts, :provenance, %{"source" => "vanta_runtime"}),
      "payload" => payload
    }

    Schema.validate!("persisted_artifact", artifact)
  end

  def build_recovery_record(attrs, sequence) do
    base =
      attrs
      |> stringify_keys()
      |> Map.merge(%{
        "created_sequence" => sequence,
        "updated_sequence" => sequence
      })
      |> Map.put_new("status", "prepared")
      |> Map.put_new("crash_window", "none")
      |> Map.put_new("effect_applied", false)
      |> Map.put_new("rollback_status", "not_started")

    content_hash = base |> Map.drop(["content_hash"]) |> Hash.canonical_json_hash()
    record = Map.put(base, "content_hash", content_hash)
    Schema.validate!("recovery_record", record)
  end

  defp validate_commit_request(request) do
    steps = Map.get(request, "steps", [])
    verifier_outputs = Map.get(request, "verifier_outputs", [])
    approval_records = Map.get(request, "approval_records", [])

    cond do
      not is_binary(request["episode_id"]) or not is_binary(request["idempotency_key"]) ->
        {:error, :invalid_commit_identity}

      not is_map(request["state"]) or not is_map(request["journal"]) ->
        {:error, :missing_state_or_journal}

      Enum.any?(verifier_outputs, &(&1["decision"] != "accept")) ->
        {:error, :verifier_not_accept}

      Enum.any?(
        steps,
        &(not Vanta.side_effect_allowed?(&1["action_type"], &1["side_effect_class"]))
      ) ->
        {:error, :unsupported_side_effect}

      Enum.any?(steps, &(&1["side_effect_class"] in ["IRREVERSIBLE", "MEMORY_WRITE"])) ->
        {:error, :unsupported_side_effect}

      request["journal"]["memory_write_effects"] != [] ->
        {:error, :memory_write_not_allowed}

      true ->
        with :ok <- Schema.validate("canonical_state", request["state"]),
             :ok <- Schema.validate("episode_journal", request["journal"]),
             :ok <- validate_many("execution_step", steps),
             :ok <- validate_many("approval_record", approval_records),
             :ok <- validate_many("evidence_packet", Map.get(request, "evidence_packets", [])),
             :ok <- validate_many("verifier_output", verifier_outputs),
             :ok <- validate_commit_refs(request) do
          :ok
        end
    end
  end

  defp validate_many(schema, values) do
    Enum.reduce_while(values, :ok, fn value, :ok ->
      case Schema.validate(schema, value) do
        :ok -> {:cont, :ok}
        {:error, reason} -> {:halt, {:error, {schema, reason}}}
      end
    end)
  end

  defp require_pointer(missing, _name, id, artifact) when is_binary(id) and is_map(artifact),
    do: missing

  defp require_pointer(missing, name, _id, _artifact), do: [name | missing]

  defp require_journal_refs(missing, nil, _evidence_ids, _verifier_ids), do: missing

  defp require_journal_refs(missing, journal, evidence_ids, verifier_ids) do
    payload = journal["payload"]

    evidence_missing =
      payload
      |> Map.get("evidence_refs", [])
      |> Enum.reject(&MapSet.member?(evidence_ids, &1))
      |> Enum.map(&("evidence_ref:" <> &1))

    verifier_missing =
      payload
      |> Map.get("verifier_output_refs", [])
      |> Enum.reject(&MapSet.member?(verifier_ids, &1))
      |> Enum.map(&("verifier_ref:" <> &1))

    missing ++ evidence_missing ++ verifier_missing
  end

  defp require_approval_refs(missing, nil, _approval_ids), do: missing

  defp require_approval_refs(missing, journal, approval_ids) do
    journal
    |> get_in(["payload", "approval_record_refs"])
    |> List.wrap()
    |> Enum.reject(&MapSet.member?(approval_ids, &1))
    |> Enum.map(&("approval_ref:" <> &1))
    |> then(&(missing ++ &1))
  end

  defp require_committed_artifact_refs(missing, nil), do: missing

  defp require_committed_artifact_refs(missing, journal) do
    payload = journal["payload"]

    committable? =
      payload
      |> Map.get("steps", [])
      |> Enum.any?(&(&1["action_type"] == "commit_fixture_document_candidate"))

    if committable? and Map.get(payload, "artifact_refs", []) == [] do
      ["committed_artifact_refs" | missing]
    else
      missing
    end
  end

  defp require_final_hash(missing, nil, _state), do: missing
  defp require_final_hash(missing, _journal, nil), do: missing

  defp require_final_hash(missing, journal, state) do
    final_hash = journal |> get_in(["payload", "state_hashes"]) |> List.wrap() |> List.last()

    if final_hash == get_in(state, ["payload", "state_hash"]),
      do: missing,
      else: ["final_state_hash" | missing]
  end

  defp validate_commit_refs(request) do
    steps = Map.get(request, "steps", [])

    if Enum.any?(steps, &(&1["action_type"] == "commit_fixture_document_candidate")) do
      journal = request["journal"]
      evidence = Map.get(request, "evidence_packets", [])
      verifiers = Map.get(request, "verifier_outputs", [])
      approvals = Map.get(request, "approval_records", [])
      evidence_ids = MapSet.new(evidence, & &1["evidence_id"])
      verifier_ids = MapSet.new(verifiers, & &1["verifier_output_id"])
      approval_ids = MapSet.new(approvals, & &1["approval_id"])
      journal_evidence = MapSet.new(Map.get(journal, "evidence_refs", []))
      journal_verifiers = MapSet.new(Map.get(journal, "verifier_output_refs", []))
      journal_approvals = MapSet.new(Map.get(journal, "approval_record_refs", []))
      phases = MapSet.new(evidence, & &1["evidence_phase"])

      cond do
        MapSet.size(approval_ids) != 1 ->
          {:error, :approval_record_count_invalid}

        Enum.any?(approvals, &(&1["decision"] != "approved")) ->
          {:error, :approval_not_approved}

        phases != MapSet.new(["pre_effect", "post_effect"]) ->
          {:error, :evidence_phases_incomplete}

        MapSet.size(verifier_ids) != 2 ->
          {:error, :verifier_output_count_invalid}

        MapSet.size(evidence_ids) != 2 ->
          {:error, :evidence_packet_count_invalid}

        journal_evidence != evidence_ids ->
          {:error, :journal_evidence_refs_mismatch}

        journal_verifiers != verifier_ids ->
          {:error, :journal_verifier_refs_mismatch}

        journal_approvals != approval_ids ->
          {:error, :journal_approval_refs_mismatch}

        Map.get(journal, "artifact_refs", []) == [] ->
          {:error, :journal_artifact_refs_missing}

        true ->
          :ok
      end
    else
      :ok
    end
  end

  defp stringify_keys(map) when is_map(map) do
    Map.new(map, fn {key, value} -> {to_string(key), stringify_keys(value)} end)
  end

  defp stringify_keys(list) when is_list(list), do: Enum.map(list, &stringify_keys/1)
  defp stringify_keys(value), do: value
end
