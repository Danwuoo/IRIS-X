defmodule Vanta.ActionExecutor do
  @moduledoc """
  Executes or simulates the fixture-local action set allowed in Stage 1.
  """

  alias Vanta.{EvaluationHarness, Hash, PathGuard, Schema, StructuredEdit}

  def execute(workspace, %{"action_type" => "read_file", "action_payload" => payload}) do
    path = Map.fetch!(payload, "path")
    abs_path = PathGuard.resolve!(workspace, path)
    content = File.read!(abs_path)

    {:ok,
     %{
       "kind" => "read_file",
       "path" => path,
       "content" => content,
       "links" => markdown_links(content),
       "file_hash" => Hash.sha256(content),
       "mutated" => false
     }}
  end

  def execute(workspace, %{"action_type" => "list_files", "action_payload" => payload}) do
    root = Map.get(payload, "path", ".")
    abs_root = PathGuard.resolve!(workspace, root)

    files =
      abs_root
      |> Path.join("**/*")
      |> Path.wildcard()
      |> Enum.filter(&File.regular?/1)
      |> Enum.map(&PathGuard.relative(workspace, &1))
      |> Enum.sort()

    {:ok, %{"kind" => "list_files", "path" => root, "files" => files, "mutated" => false}}
  end

  def execute(workspace, %{"action_type" => "compute_hash", "action_payload" => payload}) do
    path = Map.fetch!(payload, "path")
    abs_path = PathGuard.resolve!(workspace, path)

    {:ok,
     %{
       "kind" => "compute_hash",
       "path" => path,
       "file_hash" => Hash.file_hash(abs_path),
       "mutated" => false
     }}
  end

  def execute(workspace, %{
        "action_type" => "inspect_document_structure",
        "action_payload" => payload
      }) do
    StructuredEdit.inspect_document_structure(workspace, payload)
  end

  def execute(workspace, %{
        "action_type" => "validate_document_contract",
        "action_payload" => payload
      }) do
    StructuredEdit.validate_document_contract(workspace, payload)
  end

  def execute(workspace, %{
        "action_type" => "simulate_structured_edit",
        "action_payload" => payload
      }) do
    StructuredEdit.simulate_structured_edit(workspace, payload)
  end

  def execute(workspace, %{
        "action_type" => "apply_reversible_structured_edit",
        "action_payload" => payload
      }) do
    StructuredEdit.apply_reversible_structured_edit(workspace, payload)
  end

  def execute(workspace, %{"action_type" => "simulate_patch", "action_payload" => payload}) do
    patch_result(workspace, payload, false)
  end

  def execute(workspace, %{"action_type" => "compute_diff", "action_payload" => payload}) do
    path = Map.fetch!(payload, "path")
    candidate_content = Map.fetch!(payload, "candidate_content")
    abs_path = PathGuard.resolve!(workspace, path)
    original = File.read!(abs_path)

    {:ok,
     %{
       "kind" => "compute_diff",
       "path" => path,
       "diff" => simple_diff(original, candidate_content),
       "before_hash" => Hash.sha256(original),
       "after_hash" => Hash.sha256(candidate_content),
       "mutated" => false
     }}
  end

  def execute(workspace, %{"action_type" => "apply_reversible_patch", "action_payload" => payload}) do
    patch_result(workspace, payload, true)
  end

  def execute(_workspace, %{
        "action_type" => "record_compensable_action",
        "action_payload" => payload
      }) do
    {:ok,
     %{
       "kind" => "record_compensable_action",
       "receipt_id" => Map.fetch!(payload, "receipt_id"),
       "result_summary" =>
         Map.get(payload, "result_summary", "Fixture-local compensable action receipt."),
       "compensation_hint" => Map.get(payload, "compensation_hint"),
       "compensation_required" => true,
       "rollback_available" => false,
       "mutated" => false
     }}
  end

  def execute(workspace, %{"action_type" => "validate_artifact", "action_payload" => payload}) do
    case payload do
      %{"validation" => "traceability_links", "path" => path} ->
        validate_traceability_links(workspace, path)

      %{"validation" => "terminology_consistency", "paths" => paths} when is_list(paths) ->
        validate_terminology_consistency(workspace, paths)

      %{"validation" => "episode_audit_refs", "path" => path} ->
        validate_episode_audit_refs(workspace, path, Map.get(payload, "artifacts_path"))

      _ ->
        validate_exists(workspace, payload)
    end
  end

  def rollback(workspace, %{"backup_metadata" => metadata}), do: rollback(workspace, metadata)

  def rollback(workspace, metadata) do
    target = metadata |> Map.fetch!("path") |> then(&PathGuard.resolve!(workspace, &1))
    backup = metadata |> Map.fetch!("backup_path") |> then(&PathGuard.resolve!(workspace, &1))
    File.cp!(backup, target)
    :ok
  end

  defp validate_exists(workspace, payload) do
    path = Map.fetch!(payload, "path")
    abs_path = PathGuard.resolve!(workspace, path)

    {:ok,
     %{
       "kind" => "validate_artifact",
       "path" => path,
       "exists" => File.exists?(abs_path),
       "file_hash" => if(File.exists?(abs_path), do: Hash.file_hash(abs_path), else: nil),
       "mutated" => false
     }}
  end

  defp validate_traceability_links(workspace, path) do
    abs_path = PathGuard.resolve!(workspace, path)
    content = File.read!(abs_path)

    {:ok,
     %{
       "kind" => "validate_artifact",
       "validation" => "traceability_links",
       "path" => path,
       "links" => markdown_links(content),
       "file_hash" => Hash.sha256(content),
       "mutated" => false
     }}
  end

  defp validate_terminology_consistency(workspace, paths) do
    documents =
      Enum.map(paths, fn path ->
        abs_path = PathGuard.resolve!(workspace, path)
        content = File.read!(abs_path)

        %{
          "path" => path,
          "content" => content,
          "file_hash" => Hash.sha256(content)
        }
      end)

    {:ok,
     %{
       "kind" => "validate_artifact",
       "validation" => "terminology_consistency",
       "paths" => paths,
       "inconsistencies" => terminology_inconsistencies(documents),
       "file_hashes" => Map.new(documents, &{&1["path"], &1["file_hash"]}),
       "mutated" => false
     }}
  end

  defp patch_result(workspace, payload, write?) do
    path = Map.fetch!(payload, "path")
    find = Map.fetch!(payload, "find")
    replace = Map.fetch!(payload, "replace")
    abs_path = PathGuard.resolve!(workspace, path)
    original = File.read!(abs_path)

    if String.contains?(original, find) do
      candidate = String.replace(original, find, replace, global: false)
      diff = simple_diff(original, candidate)

      observation = %{
        "kind" => if(write?, do: "apply_reversible_patch", else: "simulate_patch"),
        "path" => path,
        "diff" => diff,
        "before_hash" => Hash.sha256(original),
        "after_hash" => Hash.sha256(candidate),
        "mutated" => write?
      }

      if write? do
        backup_metadata = write_backup!(workspace, path, original, candidate, diff)
        File.write!(abs_path, candidate)
        maybe_drop_backup!(workspace, backup_metadata, payload)

        {:ok,
         observation
         |> Map.put("backup_metadata", backup_metadata)
         |> Map.put("source_hash_after_write", Hash.file_hash(abs_path))}
      else
        {:ok, Map.put(observation, "candidate_content", candidate)}
      end
    else
      {:error, {:find_text_not_found, find}}
    end
  end

  defp validate_episode_audit_refs(workspace, path, artifacts_path) do
    journal =
      workspace
      |> PathGuard.resolve!(path)
      |> Schema.load_json!()

    artifacts =
      if is_binary(artifacts_path) do
        workspace
        |> PathGuard.resolve!(artifacts_path)
        |> Schema.load_json!()
      else
        %{}
      end

    audit = EvaluationHarness.audit_result(journal, artifacts)

    {:ok,
     %{
       "kind" => "validate_artifact",
       "validation" => "episode_audit_refs",
       "path" => path,
       "artifacts_path" => artifacts_path,
       "audit_complete" => audit["complete"],
       "missing" => audit["missing"],
       "checklist" => audit["checklist"],
       "mutated" => false
     }}
  end

  defp write_backup!(workspace, path, original, candidate, diff) do
    backup_dir = PathGuard.resolve!(workspace, ".vanta_backups")
    File.mkdir_p!(backup_dir)

    safe_name = path |> PathGuard.normalize_separator() |> String.replace("/", "__")
    backup_path = Path.join(backup_dir, safe_name <> ".bak")
    metadata_path = Path.join(backup_dir, safe_name <> ".metadata.json")

    metadata = %{
      "path" => path,
      "backup_path" => PathGuard.relative(workspace, backup_path),
      "metadata_path" => PathGuard.relative(workspace, metadata_path),
      "before_hash" => Hash.sha256(original),
      "after_hash" => Hash.sha256(candidate),
      "diff" => diff
    }

    File.write!(backup_path, original)
    File.write!(metadata_path, Jason.encode!(metadata, pretty: true))
    metadata
  end

  defp maybe_drop_backup!(workspace, metadata, %{"drop_backup_after_write" => true}) do
    metadata
    |> Map.take(["backup_path", "metadata_path"])
    |> Map.values()
    |> Enum.each(fn path ->
      workspace
      |> PathGuard.resolve!(path)
      |> File.rm()
    end)
  end

  defp maybe_drop_backup!(_workspace, _metadata, _payload), do: :ok

  defp simple_diff(original, candidate) do
    original_lines = original |> normalize_newlines() |> String.split("\n", trim: false)
    candidate_lines = candidate |> normalize_newlines() |> String.split("\n", trim: false)

    original_lines
    |> Enum.zip(candidate_lines)
    |> Enum.flat_map(fn
      {same, same} -> []
      {before, after_line} -> ["-" <> before, "+" <> after_line]
    end)
    |> Kernel.++(tail_diff(original_lines, candidate_lines))
    |> Enum.join("\n")
  end

  defp tail_diff(original_lines, candidate_lines) do
    original_count = length(original_lines)
    candidate_count = length(candidate_lines)

    cond do
      original_count > candidate_count ->
        original_lines |> Enum.drop(candidate_count) |> Enum.map(&("-" <> &1))

      candidate_count > original_count ->
        candidate_lines |> Enum.drop(original_count) |> Enum.map(&("+" <> &1))

      true ->
        []
    end
  end

  defp normalize_newlines(value) when is_binary(value) do
    value
    |> String.replace("\r\n", "\n")
    |> String.replace("\r", "\n")
  end

  defp markdown_links(content) do
    ~r/\[([^\]]+)\]\(([^)]+)\)/
    |> Regex.scan(content, capture: :all_but_first)
    |> Enum.map(fn [label, target] -> %{"label" => label, "target" => target} end)
  end

  defp terminology_inconsistencies(documents) do
    canonical_present? =
      Enum.any?(documents, fn document ->
        String.contains?(document["content"], "Evidence Packet")
      end)

    if canonical_present? do
      documents
      |> Enum.flat_map(fn document ->
        if String.contains?(document["content"], "evidence package") do
          [
            %{
              "canonical" => "Evidence Packet",
              "observed" => "evidence package",
              "path" => document["path"]
            }
          ]
        else
          []
        end
      end)
    else
      []
    end
  end
end
