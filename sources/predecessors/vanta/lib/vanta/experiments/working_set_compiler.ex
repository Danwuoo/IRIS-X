defmodule Vanta.WorkingSetCompiler do
  @moduledoc """
  Phase 5 `Working Set Compiler v0`.

  The compiler is deterministic and reference-backed. It does not read memory
  stores, write memory, or accept raw tool log / full memory dump refs.
  """

  alias Vanta.{Hash, PathGuard, Schema}

  @disallowed_kinds ~w(raw_tool_log full_memory_dump memory_write)

  @kind_priority %{
    "canonical_state" => 0,
    "constraint" => 1,
    "evidence" => 2,
    "recovery_context" => 3,
    "memory" => 4,
    "artifact" => 5
  }

  def compile(input, opts \\ []) do
    workspace = Keyword.get(opts, :workspace)
    max_context_chars = max_context_chars(input, opts)
    required_refs = MapSet.new(Map.get(input, "required_refs", []))

    candidates =
      input
      |> Map.get("candidate_refs", [])
      |> Enum.map(&normalize_ref(&1, workspace))

    disallowed =
      candidates
      |> Enum.filter(&(&1["kind"] in @disallowed_kinds))
      |> Enum.map(& &1["ref_id"])

    if disallowed != [] do
      {:error, {:disallowed_refs, Enum.sort(disallowed)}}
    else
      {selected, omitted} = select_refs(candidates, required_refs, max_context_chars)
      selected_chars = total_chars(selected)

      working_set = %{
        "schema_version" => Vanta.schema_version(),
        "working_set_id" => "working_set_#{Map.fetch!(input, "task_id")}",
        "active_goal_ref" => Map.fetch!(input, "active_goal_ref"),
        "canonical_state_ref" => first_ref(selected, "canonical_state"),
        "memory_refs" => refs_by_kind(selected, "memory"),
        "evidence_refs" => refs_by_kind(selected, "evidence"),
        "constraint_refs" => refs_by_kind(selected, "constraint"),
        "recovery_context_refs" => refs_by_kind(selected, "recovery_context"),
        "selection_policy" => "working_set_compiler_v0/reference_backed_required_first",
        "selection_rationale" =>
          "Required refs selected before optional refs; optional refs sorted by stable kind priority and ref_id.",
        "token_budget" => %{
          "max_context_chars" => max_context_chars,
          "selected_context_chars" => selected_chars,
          "estimated_tokens" => estimate_tokens(selected_chars),
          "estimation_method" => "ceil(chars / 4)",
          "budget_adhered" => selected_chars <= max_context_chars
        },
        "provenance" => %{
          "included_refs" => Enum.map(selected, &provenance_ref/1)
        },
        "omitted_context_notes" => omitted_notes(omitted)
      }

      {:ok,
       %{
         working_set: Schema.validate!("working_set", working_set),
         selected_refs: selected,
         omitted_refs: omitted,
         context_text: context_text(selected)
       }}
    end
  end

  def normalize_ref(ref, workspace \\ nil) do
    content = Map.get(ref, "content") || load_content(ref, workspace)

    ref
    |> Map.put_new("required", false)
    |> Map.put_new("role", "optional")
    |> Map.put_new("source", "fixture")
    |> Map.put("content", content)
    |> Map.put("content_hash", Map.get(ref, "content_hash") || Hash.sha256(content))
    |> Map.put("content_chars", String.length(content))
  end

  def estimate_tokens(chars) when is_integer(chars) and chars >= 0, do: div(chars + 3, 4)

  def context_text(refs) do
    refs
    |> Enum.map(fn ref ->
      """
      REF #{ref["ref_id"]}
      kind: #{ref["kind"]}
      path: #{ref["path"]}
      content:
      #{ref["content"]}
      """
      |> String.trim()
    end)
    |> Enum.join("\n\n")
  end

  defp max_context_chars(input, opts) do
    Keyword.get(opts, :max_context_chars) ||
      get_in(input, ["budget", "max_context_chars"]) ||
      Map.get(input, "max_context_chars") ||
      20_000
  end

  defp select_refs(candidates, required_refs, max_context_chars) do
    {required, optional} =
      Enum.split_with(candidates, fn ref ->
        ref["required"] == true or MapSet.member?(required_refs, ref["ref_id"])
      end)

    ordered =
      Enum.sort_by(required, &sort_key/1) ++ Enum.sort_by(optional, &sort_key/1)

    Enum.reduce(ordered, {[], [], 0}, fn ref, {selected, omitted, used_chars} ->
      next_chars = used_chars + ref["content_chars"]

      if next_chars <= max_context_chars do
        {selected ++ [ref], omitted, next_chars}
      else
        {selected, omitted ++ [Map.put(ref, "omit_reason", "budget_exceeded")], used_chars}
      end
    end)
    |> then(fn {selected, omitted, _used_chars} -> {selected, omitted} end)
  end

  defp sort_key(ref), do: {Map.get(@kind_priority, ref["kind"], 99), ref["ref_id"]}

  defp total_chars(refs), do: refs |> Enum.map(& &1["content_chars"]) |> Enum.sum()

  defp first_ref(refs, kind) do
    refs
    |> refs_by_kind(kind)
    |> List.first()
    |> Kernel.||("")
  end

  defp refs_by_kind(refs, kind) do
    refs
    |> Enum.filter(&(&1["kind"] == kind))
    |> Enum.map(& &1["ref_id"])
  end

  defp provenance_ref(ref) do
    %{
      "ref_id" => ref["ref_id"],
      "kind" => ref["kind"],
      "source" => ref["source"],
      "path" => ref["path"],
      "content_hash" => ref["content_hash"],
      "role" => ref["role"],
      "required" => ref["required"] == true
    }
  end

  defp omitted_notes(omitted) do
    Enum.map(omitted, fn ref ->
      "omitted #{ref["ref_id"]} (#{ref["kind"]}): #{ref["omit_reason"]}"
    end)
  end

  defp load_content(%{"path" => path}, workspace) when is_binary(path) and is_binary(workspace) do
    cond do
      String.contains?(path, "#") ->
        path

      true ->
        workspace
        |> PathGuard.resolve!(path)
        |> File.read!()
    end
  rescue
    _error -> path
  end

  defp load_content(ref, _workspace), do: Map.get(ref, "path", "")
end
