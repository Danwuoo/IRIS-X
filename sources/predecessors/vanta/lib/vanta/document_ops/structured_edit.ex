defmodule Vanta.StructuredEdit do
  @moduledoc false

  alias Vanta.{Hash, PathGuard, Schema}

  def inspect_document_structure(workspace, payload) do
    path = Map.fetch!(payload, "path")
    abs_path = PathGuard.resolve!(workspace, path)
    content = File.read!(abs_path)
    document = parse_document(path, content, Map.get(payload, "format"))

    selector_results =
      payload
      |> Map.get("selectors", [])
      |> Enum.map(&resolve_selector(document, &1))

    {:ok,
     %{
       "kind" => "inspect_document_structure",
       "path" => path,
       "file_hash" => Hash.sha256(content),
       "format" => document.format,
       "structure" => document.structure,
       "parse_diagnostics" => document.diagnostics,
       "selector_results" => selector_results,
       "mutated" => false
     }}
  end

  def validate_document_contract(workspace, payload) do
    path = Map.fetch!(payload, "path")
    abs_path = PathGuard.resolve!(workspace, path)
    content = File.read!(abs_path)
    document = parse_document(path, content, Map.get(payload, "format"))
    {contract, contract_source} = load_contract(workspace, payload)
    failures = contract_failures(document, content, contract)

    observation =
      %{
        "kind" => "validate_document_contract",
        "path" => path,
        "file_hash" => Hash.sha256(content),
        "format" => document.format,
        "contract_hash" => contract_hash(contract, contract_source),
        "contract_source" => contract_source,
        "passed" => failures == [],
        "failures" => failures,
        "parse_diagnostics" => document.diagnostics,
        "mutated" => false
      }
      |> maybe_put_contract_ref(payload)

    {:ok, observation}
  end

  def simulate_structured_edit(workspace, payload) do
    structured_edit(workspace, payload, false)
  end

  def apply_reversible_structured_edit(workspace, payload) do
    structured_edit(workspace, payload, true)
  end

  def simple_diff(original, candidate) do
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

  defp structured_edit(workspace, payload, write?) do
    path = Map.fetch!(payload, "path")
    operation = Map.fetch!(payload, "operation")
    replacement = Map.fetch!(payload, "replacement")
    selector = Map.fetch!(payload, "selector")
    abs_path = PathGuard.resolve!(workspace, path)
    original = File.read!(abs_path)
    document = parse_document(path, original, Map.get(payload, "format"))
    selector_resolution = resolve_selector(document, selector)
    kind = if(write?, do: "apply_reversible_structured_edit", else: "simulate_structured_edit")

    base_observation = %{
      "kind" => kind,
      "path" => path,
      "operation" => operation,
      "operation_summary" => operation_summary(operation, selector_resolution),
      "selector_resolution" => selector_resolution,
      "before_hash" => Hash.sha256(original),
      "format" => document.format,
      "mutated" => false
    }

    if selector_resolution["status"] == "resolved" do
      case apply_operation(document, selector_resolution, operation, replacement) do
        {:ok, candidate} ->
          diff = simple_diff(original, candidate)

          if write? do
            write_structured_edit(
              workspace,
              payload,
              abs_path,
              original,
              candidate,
              diff,
              base_observation
            )
          else
            maybe_mutate_after_simulation(abs_path, payload, candidate)

            {:ok,
             base_observation
             |> Map.merge(%{
               "candidate_content" => candidate,
               "diff" => diff,
               "after_hash" => Hash.sha256(candidate),
               "source_hash_after_simulation" => Hash.file_hash(abs_path),
               "mutated" =>
                 Map.get(payload, "fault_injection") == "mutate_source_after_simulation"
             })}
          end

        {:error, reason} ->
          {:ok, Map.put(base_observation, "error", inspect(reason))}
      end
    else
      source_hash_key =
        if(write?, do: "source_hash_after_write", else: "source_hash_after_simulation")

      {:ok, Map.put(base_observation, source_hash_key, Hash.file_hash(abs_path))}
    end
  end

  defp write_structured_edit(workspace, payload, abs_path, original, candidate, diff, observation) do
    metadata =
      write_backup!(
        workspace,
        payload,
        original,
        candidate,
        diff,
        observation["selector_resolution"]
      )

    File.write!(abs_path, candidate)
    maybe_drop_backup_files!(workspace, metadata, payload)

    observation =
      observation
      |> Map.merge(%{
        "diff" => diff,
        "after_hash" => Hash.sha256(candidate),
        "source_hash_after_write" => Hash.file_hash(abs_path),
        "mutated" => true
      })

    if Map.get(payload, "fault_injection") == "omit_backup_metadata" do
      {:ok, observation}
    else
      {:ok, Map.put(observation, "backup_metadata", metadata)}
    end
  end

  defp maybe_mutate_after_simulation(
         abs_path,
         %{"fault_injection" => "mutate_source_after_simulation"},
         candidate
       ) do
    File.write!(abs_path, candidate)
  end

  defp maybe_mutate_after_simulation(_abs_path, _payload, _candidate), do: :ok

  defp write_backup!(workspace, payload, original, candidate, diff, selector_resolution) do
    path = Map.fetch!(payload, "path")
    backup_dir = PathGuard.resolve!(workspace, ".vanta_backups")
    File.mkdir_p!(backup_dir)

    safe_name = path |> PathGuard.normalize_separator() |> String.replace("/", "__")
    backup_path = Path.join(backup_dir, safe_name <> ".structured.bak")
    metadata_path = Path.join(backup_dir, safe_name <> ".structured.metadata.json")

    metadata = %{
      "backup_policy" => Map.get(payload, "backup_policy", "fixture_backup_restore"),
      "path" => path,
      "backup_path" => PathGuard.relative(workspace, backup_path),
      "metadata_path" => PathGuard.relative(workspace, metadata_path),
      "before_hash" => Hash.sha256(original),
      "after_hash" => Hash.sha256(candidate),
      "backup_hash" => Hash.sha256(original),
      "diff_hash" => Hash.sha256(diff),
      "operation" => Map.fetch!(payload, "operation"),
      "selector_resolution" => selector_resolution
    }

    File.write!(backup_path, original)
    File.write!(metadata_path, Jason.encode!(metadata, pretty: true))
    metadata
  end

  defp maybe_drop_backup_files!(workspace, metadata, %{"fault_injection" => "drop_backup_files"}) do
    metadata
    |> Map.take(["backup_path", "metadata_path"])
    |> Map.values()
    |> Enum.each(fn path ->
      workspace
      |> PathGuard.resolve!(path)
      |> File.rm()
    end)
  end

  defp maybe_drop_backup_files!(_workspace, _metadata, _payload), do: :ok

  defp parse_document(path, content, requested_format) do
    format = requested_format || inferred_format(path)
    normalized = normalize_newlines(content)

    case format do
      "json" ->
        parse_json_document(normalized)

      _other ->
        parse_markdown_document(normalized)
    end
  end

  defp parse_markdown_document(content) do
    lines = logical_lines(content)
    headings = markdown_headings(lines)
    sections = markdown_sections(headings, length(lines))

    %{
      format: "markdown",
      content: content,
      lines: lines,
      trailing_newline?: String.ends_with?(content, "\n"),
      json: nil,
      diagnostics: [],
      structure: %{
        "format" => "markdown",
        "line_count" => length(lines),
        "headings" => headings,
        "sections" => sections
      }
    }
  end

  defp parse_json_document(content) do
    case Jason.decode(content) do
      {:ok, json} ->
        %{
          format: "json",
          content: content,
          lines: logical_lines(content),
          trailing_newline?: String.ends_with?(content, "\n"),
          json: json,
          diagnostics: [],
          structure: %{
            "format" => "json",
            "top_level_keys" => top_level_keys(json),
            "json_paths" => json_paths(json)
          }
        }

      {:error, error} ->
        %{
          format: "json",
          content: content,
          lines: logical_lines(content),
          trailing_newline?: String.ends_with?(content, "\n"),
          json: nil,
          diagnostics: [%{"severity" => "error", "message" => Exception.message(error)}],
          structure: %{"format" => "json", "top_level_keys" => [], "json_paths" => []}
        }
    end
  end

  defp inferred_format(path) do
    if path |> Path.extname() |> String.downcase() == ".json", do: "json", else: "markdown"
  end

  defp markdown_headings(lines) do
    lines
    |> Enum.with_index(1)
    |> Enum.flat_map(fn {line, line_no} ->
      case Regex.run(~r/^(#+)\s+(.+?)\s*#*\s*$/, line, capture: :all_but_first) do
        [markers, text] ->
          [
            %{
              "level" => String.length(markers),
              "text" => String.trim(text),
              "line" => line_no
            }
          ]

        _other ->
          []
      end
    end)
  end

  defp markdown_sections(headings, line_count) do
    headings
    |> Enum.with_index()
    |> Enum.map(fn {heading, index} ->
      next_boundary =
        headings
        |> Enum.drop(index + 1)
        |> Enum.find(fn candidate -> candidate["level"] <= heading["level"] end)

      end_line =
        case next_boundary do
          nil -> line_count
          %{"line" => line} -> line - 1
        end

      %{
        "heading" => heading["text"],
        "level" => heading["level"],
        "start_line" => heading["line"],
        "end_line" => end_line
      }
    end)
  end

  defp resolve_selector(%{format: "markdown"} = document, %{"type" => "heading"} = selector) do
    matches =
      document.structure["headings"]
      |> Enum.filter(&selector_heading_match?(&1, selector))
      |> Enum.map(fn heading ->
        %{
          "kind" => "heading",
          "format" => "markdown",
          "start_line" => heading["line"],
          "end_line" => heading["line"],
          "text" => heading["text"],
          "level" => heading["level"]
        }
      end)

    choose_match(selector, matches)
  end

  defp resolve_selector(%{format: "markdown"} = document, %{"type" => "section"} = selector) do
    matches =
      document.structure["sections"]
      |> Enum.filter(&selector_section_match?(&1, selector))
      |> Enum.map(fn section ->
        %{
          "kind" => "section",
          "format" => "markdown",
          "start_line" => section["start_line"],
          "end_line" => section["end_line"],
          "heading" => section["heading"],
          "level" => section["level"]
        }
      end)

    choose_match(selector, matches)
  end

  defp resolve_selector(document, %{"type" => "line_range"} = selector) do
    start_line = selector["start_line"]
    end_line = selector["end_line"]

    if is_integer(start_line) and is_integer(end_line) and start_line >= 1 and
         end_line >= start_line and end_line <= length(document.lines) do
      choose_match(selector, [
        %{
          "kind" => "line_range",
          "format" => document.format,
          "start_line" => start_line,
          "end_line" => end_line
        }
      ])
    else
      missing_resolution(selector, 0)
    end
  end

  defp resolve_selector(
         %{format: "json", json: json} = document,
         %{"type" => "json_path"} = selector
       )
       when not is_nil(json) do
    with {:ok, tokens} <- json_path_tokens(selector["path"]),
         {:ok, value} <- fetch_json_path(json, tokens) do
      choose_match(selector, [
        %{
          "kind" => "json_path",
          "format" => document.format,
          "json_path" => selector["path"],
          "tokens" => serialize_json_tokens(tokens),
          "value" => value
        }
      ])
    else
      _other -> missing_resolution(selector, 0)
    end
  end

  defp resolve_selector(_document, selector), do: missing_resolution(selector, 0)

  defp selector_heading_match?(heading, selector) do
    heading["text"] == selector["text"] and optional_match?(heading["level"], selector["level"])
  end

  defp selector_section_match?(section, selector) do
    section["heading"] == selector["heading"] and
      optional_match?(section["level"], selector["level"])
  end

  defp optional_match?(_actual, nil), do: true
  defp optional_match?(actual, expected), do: actual == expected

  defp choose_match(selector, matches) do
    occurrence = selector["occurrence"]

    cond do
      matches == [] ->
        missing_resolution(selector, 0)

      is_integer(occurrence) and occurrence >= 1 and length(matches) >= occurrence ->
        resolved_resolution(selector, Enum.at(matches, occurrence - 1), length(matches))

      is_integer(occurrence) ->
        missing_resolution(selector, length(matches))

      length(matches) == 1 ->
        resolved_resolution(selector, hd(matches), 1)

      true ->
        %{
          "selector" => selector,
          "status" => "ambiguous",
          "match_count" => length(matches),
          "matches" =>
            Enum.map(
              matches,
              &Map.take(&1, ["kind", "start_line", "end_line", "text", "heading", "json_path"])
            )
        }
    end
  end

  defp resolved_resolution(selector, target, match_count) do
    %{
      "selector" => selector,
      "status" => "resolved",
      "match_count" => match_count,
      "target" => target
    }
  end

  defp missing_resolution(selector, match_count) do
    %{
      "selector" => selector,
      "status" => "missing",
      "match_count" => match_count
    }
  end

  defp apply_operation(%{format: "json", json: json}, resolution, "replace", replacement) do
    tokens = resolution["target"]["tokens"] |> deserialize_json_tokens()

    with {:ok, updated} <- replace_json_path(json, tokens, replacement),
         {:ok, encoded} <- encode_json(updated) do
      {:ok, encoded}
    end
  end

  defp apply_operation(%{format: "json", json: json}, resolution, operation, replacement)
       when operation in ["insert_before", "insert_after"] do
    tokens = resolution["target"]["tokens"] |> deserialize_json_tokens()

    with {:ok, updated} <- insert_json_path(json, tokens, operation, replacement),
         {:ok, encoded} <- encode_json(updated) do
      {:ok, encoded}
    end
  end

  defp apply_operation(document, resolution, operation, replacement)
       when operation in ["replace", "insert_before", "insert_after"] do
    target = resolution["target"]
    replacement_lines = replacement |> normalize_newlines() |> logical_lines()
    lines = document.lines
    start_index = target["start_line"] - 1
    end_index = target["end_line"] - 1

    updated_lines =
      case operation do
        "replace" ->
          Enum.take(lines, start_index) ++ replacement_lines ++ Enum.drop(lines, end_index + 1)

        "insert_before" ->
          Enum.take(lines, start_index) ++ replacement_lines ++ Enum.drop(lines, start_index)

        "insert_after" ->
          Enum.take(lines, end_index + 1) ++ replacement_lines ++ Enum.drop(lines, end_index + 1)
      end

    {:ok, join_lines(updated_lines, document.trailing_newline?)}
  end

  defp apply_operation(_document, _resolution, operation, _replacement),
    do: {:error, {:unsupported_operation, operation}}

  defp operation_summary(operation, %{"status" => "resolved", "target" => target}) do
    %{
      "operation" => operation,
      "target_kind" => target["kind"],
      "target_start_line" => target["start_line"],
      "target_end_line" => target["end_line"],
      "json_path" => target["json_path"]
    }
  end

  defp operation_summary(operation, resolution) do
    %{"operation" => operation, "selector_status" => resolution["status"]}
  end

  defp load_contract(workspace, %{"contract_ref" => contract_ref}) do
    abs_path = PathGuard.resolve!(workspace, contract_ref)

    {Schema.load_json!(abs_path),
     %{"kind" => "fixture_ref", "path" => contract_ref, "hash" => Hash.file_hash(abs_path)}}
  end

  defp load_contract(_workspace, %{"inline_contract" => contract}) do
    {contract, %{"kind" => "inline"}}
  end

  defp contract_hash(_contract, %{"hash" => hash}), do: hash
  defp contract_hash(contract, _source), do: Hash.sha256(Jason.encode!(contract))

  defp maybe_put_contract_ref(observation, %{"contract_ref" => contract_ref}),
    do: Map.put(observation, "contract_ref", contract_ref)

  defp maybe_put_contract_ref(observation, _payload), do: observation

  defp contract_failures(document, content, contract) do
    []
    |> required_headings_failures(document, Map.get(contract, "required_headings", []))
    |> required_json_paths_failures(document, Map.get(contract, "required_json_paths", []))
    |> required_text_failures(content, Map.get(contract, "required_text", []))
    |> forbidden_terms_failures(content, Map.get(contract, "forbidden_terms", []))
    |> Enum.reverse()
  end

  defp required_headings_failures(failures, %{format: "markdown"} = document, required_headings) do
    Enum.reduce(required_headings, failures, fn required, acc ->
      found? =
        document.structure["headings"]
        |> Enum.any?(fn heading ->
          heading["text"] == required["text"] and
            optional_match?(heading["level"], required["level"])
        end)

      if found?, do: acc, else: [contract_failure("required_heading_missing", required) | acc]
    end)
  end

  defp required_headings_failures(failures, _document, []), do: failures

  defp required_headings_failures(failures, _document, required_headings) do
    Enum.reduce(required_headings, failures, fn required, acc ->
      [contract_failure("required_heading_missing", required) | acc]
    end)
  end

  defp required_json_paths_failures(failures, %{format: "json", json: json}, required_paths)
       when not is_nil(json) do
    Enum.reduce(required_paths, failures, fn path, acc ->
      with {:ok, tokens} <- json_path_tokens(path),
           {:ok, _value} <- fetch_json_path(json, tokens) do
        acc
      else
        _other -> [contract_failure("required_json_path_missing", %{"path" => path}) | acc]
      end
    end)
  end

  defp required_json_paths_failures(failures, _document, required_paths) do
    Enum.reduce(required_paths, failures, fn path, acc ->
      [contract_failure("required_json_path_missing", %{"path" => path}) | acc]
    end)
  end

  defp required_text_failures(failures, content, required_text) do
    Enum.reduce(required_text, failures, fn text, acc ->
      if String.contains?(content, text),
        do: acc,
        else: [contract_failure("required_text_missing", %{"text" => text}) | acc]
    end)
  end

  defp forbidden_terms_failures(failures, content, forbidden_terms) do
    Enum.reduce(forbidden_terms, failures, fn term, acc ->
      if String.contains?(content, term),
        do: [contract_failure("forbidden_term_present", %{"term" => term}) | acc],
        else: acc
    end)
  end

  defp contract_failure(code, detail), do: %{"code" => code, "detail" => detail}

  defp json_path_tokens(path) when is_binary(path) do
    if String.starts_with?(path, "$") do
      tokens =
        ~r/\.([A-Za-z_][A-Za-z0-9_-]*)|\[(\d+)\]/
        |> Regex.scan(String.trim_leading(path, "$"), capture: :all)
        |> Enum.map(fn
          ["." <> _match, key | _rest] -> {:key, key}
          ["[" <> _match | captures] -> {:index, captures |> List.last() |> String.to_integer()}
        end)

      {:ok, tokens}
    else
      {:error, :invalid_json_path}
    end
  end

  defp json_path_tokens(_path), do: {:error, :invalid_json_path}

  defp fetch_json_path(value, []), do: {:ok, value}

  defp fetch_json_path(%{} = map, [{:key, key} | rest]) do
    if Map.has_key?(map, key), do: fetch_json_path(map[key], rest), else: {:error, :missing_path}
  end

  defp fetch_json_path(list, [{:index, index} | rest]) when is_list(list) do
    if index >= 0 and index < length(list),
      do: list |> Enum.at(index) |> fetch_json_path(rest),
      else: {:error, :missing_path}
  end

  defp fetch_json_path(_value, _tokens), do: {:error, :missing_path}

  defp replace_json_path(_json, [], replacement), do: {:ok, replacement}

  defp replace_json_path(%{} = map, [{:key, key}], replacement) do
    if Map.has_key?(map, key),
      do: {:ok, Map.put(map, key, replacement)},
      else: {:error, :missing_path}
  end

  defp replace_json_path(%{} = map, [{:key, key} | rest], replacement) do
    with true <- Map.has_key?(map, key),
         {:ok, updated} <- replace_json_path(map[key], rest, replacement) do
      {:ok, Map.put(map, key, updated)}
    else
      _other -> {:error, :missing_path}
    end
  end

  defp replace_json_path(list, [{:index, index}], replacement) when is_list(list) do
    if index >= 0 and index < length(list),
      do: {:ok, List.replace_at(list, index, replacement)},
      else: {:error, :missing_path}
  end

  defp replace_json_path(list, [{:index, index} | rest], replacement) when is_list(list) do
    with true <- index >= 0 and index < length(list),
         {:ok, updated} <- list |> Enum.at(index) |> replace_json_path(rest, replacement) do
      {:ok, List.replace_at(list, index, updated)}
    else
      _other -> {:error, :missing_path}
    end
  end

  defp replace_json_path(_value, _tokens, _replacement), do: {:error, :missing_path}

  defp insert_json_path(json, tokens, operation, replacement) do
    case Enum.split(tokens, -1) do
      {parent_tokens, [{:index, index}]} ->
        with {:ok, parent} <- fetch_json_path(json, parent_tokens),
             true <- is_list(parent),
             true <- index >= 0 and index < length(parent),
             insert_at <- if(operation == "insert_before", do: index, else: index + 1),
             updated_parent <- List.insert_at(parent, insert_at, replacement),
             {:ok, updated_json} <- replace_json_path(json, parent_tokens, updated_parent) do
          {:ok, updated_json}
        else
          _other -> {:error, :json_insert_requires_array_index}
        end

      _other ->
        {:error, :json_insert_requires_array_index}
    end
  end

  defp encode_json(json), do: {:ok, Jason.encode!(json, pretty: true) <> "\n"}

  defp serialize_json_tokens(tokens) do
    Enum.map(tokens, fn
      {:key, key} -> %{"type" => "key", "value" => key}
      {:index, index} -> %{"type" => "index", "value" => index}
    end)
  end

  defp deserialize_json_tokens(tokens) do
    Enum.map(tokens, fn
      %{"type" => "key", "value" => key} -> {:key, key}
      %{"type" => "index", "value" => index} -> {:index, index}
    end)
  end

  defp json_paths(json), do: json_paths(json, "$")

  defp json_paths(%{} = map, prefix) do
    map
    |> Enum.sort_by(fn {key, _value} -> key end)
    |> Enum.flat_map(fn {key, value} -> json_paths(value, prefix <> "." <> key) end)
  end

  defp json_paths(list, prefix) when is_list(list) do
    list
    |> Enum.with_index()
    |> Enum.flat_map(fn {value, index} -> json_paths(value, "#{prefix}[#{index}]") end)
  end

  defp json_paths(_value, prefix), do: [prefix]

  defp top_level_keys(%{} = map), do: map |> Map.keys() |> Enum.sort()
  defp top_level_keys(_json), do: []

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

  defp logical_lines(content) do
    lines = String.split(content, "\n", trim: false)

    if List.last(lines) == "" do
      Enum.drop(lines, -1)
    else
      lines
    end
  end

  defp join_lines(lines, trailing_newline?) do
    Enum.join(lines, "\n") <> if(trailing_newline?, do: "\n", else: "")
  end

  defp normalize_newlines(value) when is_binary(value) do
    value
    |> String.replace("\r\n", "\n")
    |> String.replace("\r", "\n")
  end
end
