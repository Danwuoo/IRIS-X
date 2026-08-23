defmodule Vanta.OpenClawContextPlannerAdapter do
  @moduledoc """
  OpenClaw-backed context planner for Experiment 005.

  The adapter receives an already-built context artifact and asks for a JSON
  action sequence. It is evaluation-only and must not use OpenClaw tools.
  """

  alias Vanta.{PlannerAdapter, WorkingSetCompiler}

  @default_model "openai-codex/gpt-5.4-mini"
  @default_openclaw_dir "~/openclaw"
  @default_agent "main"
  @default_timeout_seconds 600
  @default_thinking "off"
  @default_max_prompt_chars 20_000
  @default_max_response_chars 12_000

  def plan(task, context_artifact, opts \\ []) do
    with {:ok, env} <- env(opts, task) do
      max_prompt_chars = Keyword.get(opts, :max_prompt_chars, @default_max_prompt_chars)
      max_response_chars = Keyword.get(opts, :max_response_chars, @default_max_response_chars)
      prompt = task |> prompt(context_artifact) |> bound_text(max_prompt_chars)

      case call_openclaw(prompt, env, opts) do
        {:ok, response} ->
          with {:ok, text} <- extract_assistant_text(response),
               response_text <- bound_text(text, max_response_chars),
               {:ok, action_sequence} <- decode_action_sequence(response_text),
               {:ok, action_sequence} <- PlannerAdapter.validate_action_sequence(action_sequence) do
            {:ok,
             %{
               action_sequence: action_sequence,
               budget_usage: budget_usage(prompt, response_text, opts)
             }}
          end

        {:error, reason} ->
          {:error, reason}
      end
    end
  end

  def env(opts \\ [], task \\ nil) do
    model =
      opts
      |> Keyword.get(:model)
      |> fallback(System.get_env("OPENCLAW_MODEL"))
      |> fallback(openai_model_from_env())
      |> fallback(@default_model)
      |> normalize_model()

    wsl_executable =
      opts
      |> Keyword.get(:wsl_executable)
      |> fallback(System.get_env("WSL_EXE"))
      |> fallback(System.find_executable("wsl.exe"))

    openclaw_dir =
      opts
      |> Keyword.get(:openclaw_dir)
      |> fallback(System.get_env("OPENCLAW_DIR"))
      |> fallback(@default_openclaw_dir)

    agent =
      opts
      |> Keyword.get(:agent)
      |> fallback(System.get_env("OPENCLAW_AGENT"))
      |> fallback(@default_agent)

    timeout_seconds =
      opts
      |> Keyword.get(:timeout_seconds)
      |> fallback(System.get_env("OPENCLAW_TIMEOUT_SECONDS"))
      |> parse_positive_integer(@default_timeout_seconds)

    thinking =
      opts
      |> Keyword.get(:thinking)
      |> fallback(System.get_env("OPENCLAW_THINKING"))
      |> fallback(@default_thinking)

    cond do
      blank?(wsl_executable) ->
        {:error, :missing_wsl_executable}

      blank?(openclaw_dir) ->
        {:error, :missing_openclaw_dir}

      blank?(model) ->
        {:error, :missing_openclaw_model}

      true ->
        {:ok,
         %{
           wsl_executable: wsl_executable,
           openclaw_dir: openclaw_dir,
           agent: agent,
           model: model,
           timeout_seconds: timeout_seconds,
           thinking: thinking,
           session_id: session_id(opts, task)
         }}
    end
  end

  def planner_id(opts \\ []) do
    case env(opts) do
      {:ok, env} -> "openclaw_agent_local/#{env.model}"
      {:error, _reason} -> "openclaw_agent_local/context_planner"
    end
  end

  defp prompt(task, context_artifact) do
    """
    You are a non-interactive Vanta Experiment 005 context planner.

    Return JSON only. Do not use OpenClaw tools. Do not read or write files
    through the OpenClaw harness. Use only the task JSON and embedded context
    artifact below.

    Produce one JSON object matching this shape:
    {"actions":[{"action_type":"validate_artifact","action_payload":{"path":"inputs/source.md"}}]}

    Allowed action_type values:
    #{Jason.encode!(Vanta.action_types())}

    Prefer validate_artifact for Phase 5 read-only validation tasks. Use only
    paths supported by the embedded context or task input_artifacts. Do not
    include prose, markdown fences, comments, or extra keys.

    Task:
    #{Jason.encode!(task, pretty: true)}

    Context artifact:
    #{Jason.encode!(prompt_context(context_artifact), pretty: true)}
    """
  end

  defp prompt_context(%{working_set: working_set, selected_refs: selected_refs} = result) do
    %{
      "arm" => "working_set_compiler_v0",
      "working_set" => working_set,
      "selected_reference_previews" => prompt_refs(selected_refs),
      "context_text" =>
        Map.get(result, :context_text, WorkingSetCompiler.context_text(selected_refs))
    }
  end

  defp prompt_context(%{"arm" => "raw_trace_bounded"} = artifact), do: artifact
  defp prompt_context(artifact), do: artifact

  defp prompt_refs(refs) do
    Enum.map(refs, fn ref ->
      %{
        "ref_id" => ref["ref_id"],
        "kind" => ref["kind"],
        "path" => ref["path"],
        "content" => ref["content"]
      }
    end)
  end

  defp call_openclaw(prompt, env, opts) do
    runner = Keyword.get(opts, :runner, &run_openclaw/2)
    runner.(prompt, env)
  end

  defp run_openclaw(prompt, env) do
    Vanta.OpenClawHarness.run_agent(prompt, env,
      temp_prefix: "vanta_openclaw_context",
      decoder: &decode_cli_json/1
    )
  end

  defp decode_cli_json(output) do
    output
    |> candidate_json_suffixes()
    |> Enum.map(fn candidate ->
      case Jason.decode(candidate) do
        {:ok, decoded} -> decoded
        {:error, _error} -> nil
      end
    end)
    |> Enum.reject(&is_nil/1)
    |> Enum.find_value(fn
      %{"payloads" => payloads} = decoded when is_list(payloads) -> decoded
      _decoded -> nil
    end)
    |> case do
      nil -> {:error, {:invalid_openclaw_json, output}}
      result -> {:ok, result}
    end
  end

  defp extract_assistant_text(%{"payloads" => payloads}) when is_list(payloads) do
    payloads
    |> Enum.find_value(fn
      %{"text" => text} when is_binary(text) -> text
      _other -> nil
    end)
    |> case do
      nil -> {:error, :missing_openclaw_payload_text}
      text -> {:ok, text}
    end
  end

  defp extract_assistant_text(_response), do: {:error, :missing_openclaw_payload_text}

  defp decode_action_sequence(text) do
    text
    |> strip_code_fence()
    |> decode_json_or_embedded_json()
  end

  defp decode_json_or_embedded_json(text) do
    case Jason.decode(text) do
      {:ok, decoded} ->
        {:ok, decoded}

      {:error, first_error} ->
        text
        |> candidate_json_suffixes()
        |> Enum.find_value(fn candidate ->
          case Jason.decode(candidate) do
            {:ok, decoded} -> {:ok, decoded}
            {:error, _error} -> nil
          end
        end)
        |> case do
          nil ->
            {:error,
             {:invalid_openclaw_context_action_json, Exception.message(first_error), text}}

          result ->
            {:ok, result}
        end
    end
  end

  defp strip_code_fence(text) do
    trimmed = String.trim(text)

    case Regex.run(~r/\A```(?:json)?\s*(.*?)\s*```\z/s, trimmed, capture: :all_but_first) do
      [json] -> String.trim(json)
      _other -> trimmed
    end
  end

  defp budget_usage(prompt, response, opts) do
    prompt_chars = String.length(prompt)
    response_chars = String.length(response)

    %{
      "model_call_count" => 1,
      "prompt_chars" => prompt_chars,
      "response_chars" => response_chars,
      "estimated_input_tokens" => WorkingSetCompiler.estimate_tokens(prompt_chars),
      "estimated_output_tokens" => WorkingSetCompiler.estimate_tokens(response_chars),
      "max_prompt_chars" => Keyword.get(opts, :max_prompt_chars, @default_max_prompt_chars),
      "max_response_chars" => Keyword.get(opts, :max_response_chars, @default_max_response_chars)
    }
  end

  defp bound_text(text, max_chars) when is_integer(max_chars) and max_chars > 0 do
    String.slice(text, 0, max_chars)
  end

  defp bound_text(text, _max_chars), do: text

  defp candidate_json_suffixes(output) do
    output
    |> String.graphemes()
    |> Enum.with_index()
    |> Enum.filter(fn {char, _index} -> char == "{" end)
    |> Enum.map(fn {_char, index} -> String.slice(output, index..-1//1) end)
  end

  defp openai_model_from_env do
    case System.get_env("OPENAI_MODEL") do
      nil -> nil
      "" -> nil
      model -> model
    end
  end

  defp normalize_model("openai-codex/" <> _rest = model), do: model
  defp normalize_model(model), do: "openai-codex/#{model}"

  defp parse_positive_integer(value, _default) when is_integer(value) and value > 0, do: value

  defp parse_positive_integer(value, default) do
    case Integer.parse(to_string(value || "")) do
      {integer, ""} when integer > 0 -> integer
      _other -> default
    end
  end

  defp session_id(opts, task) do
    case Keyword.get(opts, :session_id) do
      value when not is_nil(value) ->
        to_string(value)

      nil ->
        task_id =
          case task do
            %{"task_id" => id} -> id
            _other -> "preflight"
          end

        unique = System.unique_integer([:positive])
        "vexp005-#{task_id}-#{unique}"
    end
  end

  defp fallback(value, fallback_value) do
    if blank?(value), do: fallback_value, else: value
  end

  defp blank?(value), do: is_nil(value) or String.trim(to_string(value)) == ""
end
