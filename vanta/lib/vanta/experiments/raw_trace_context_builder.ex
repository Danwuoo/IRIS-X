defmodule Vanta.RawTraceContextBuilder do
  @moduledoc """
  Builds the bounded raw-trace baseline artifact for Experiment 005.
  """

  alias Vanta.WorkingSetCompiler

  def build(input, opts \\ []) do
    workspace = Keyword.get(opts, :workspace)

    max_context_chars =
      Keyword.get(opts, :max_context_chars) ||
        get_in(input, ["budget", "max_context_chars"]) ||
        Map.get(input, "max_context_chars") ||
        20_000

    refs =
      input
      |> Map.get("candidate_refs", [])
      |> Enum.map(&WorkingSetCompiler.normalize_ref(&1, workspace))

    {included, dropped} = bounded_trace(refs, max_context_chars)
    selected_chars = included |> Enum.map(& &1["content_chars"]) |> Enum.sum()

    %{
      "artifact_id" => "raw_trace_#{Map.fetch!(input, "task_id")}",
      "arm" => "raw_trace_bounded",
      "max_context_chars" => max_context_chars,
      "selected_context_chars" => selected_chars,
      "estimated_tokens" => WorkingSetCompiler.estimate_tokens(selected_chars),
      "estimation_method" => "ceil(chars / 4)",
      "budget_adhered" => selected_chars <= max_context_chars,
      "included_refs" => Enum.map(included, &provenance_ref/1),
      "dropped_refs" => Enum.map(dropped, &provenance_ref/1),
      "context_text" => WorkingSetCompiler.context_text(included)
    }
  end

  defp bounded_trace(refs, max_context_chars) do
    Enum.reduce_while(refs, {[], [], 0}, fn ref, {included, dropped, used_chars} ->
      next_chars = used_chars + ref["content_chars"]

      if next_chars <= max_context_chars do
        {:cont, {included ++ [ref], dropped, next_chars}}
      else
        remaining =
          refs
          |> Enum.drop(length(included))
          |> Enum.map(&Map.put(&1, "omit_reason", "budget_exceeded"))

        {:halt, {included, dropped ++ remaining, used_chars}}
      end
    end)
    |> then(fn {included, dropped, _used_chars} -> {included, dropped} end)
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
end
