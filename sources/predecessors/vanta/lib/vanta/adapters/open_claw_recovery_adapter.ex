defmodule Vanta.OpenClawRecoveryAdapter do
  @moduledoc """
  OpenClaw-backed failure classifier and targeted recovery proposal adapter for
  Experiment 004.

  The adapter is evaluation-only. It returns a Recovery Decision and records a
  local character-budget ledger because the OpenClaw harness does not expose
  exact token usage in the current contract.
  """

  @default_model "openai-codex/gpt-5.4-mini"
  @default_openclaw_dir "~/openclaw"
  @default_agent "main"
  @default_timeout_seconds 600
  @default_thinking "off"
  @default_max_prompt_chars 20_000
  @default_max_response_chars 12_000
  @default_max_action_attempts 1

  @allowed_policies ~w(
    reconstruct_rollback_from_diff
    repair_audit_refs
    produce_compensation_record
    no_recovery
  )

  def recover(recovery_input, opts \\ []) do
    with {:ok, env} <- env(opts, recovery_input) do
      max_prompt_chars = Keyword.get(opts, :max_prompt_chars, @default_max_prompt_chars)
      max_response_chars = Keyword.get(opts, :max_response_chars, @default_max_response_chars)
      prompt = recovery_input |> prompt() |> bound_text(max_prompt_chars)

      case call_openclaw(prompt, env, opts) do
        {:ok, response} ->
          response
          |> extract_assistant_text()
          |> case do
            {:ok, text} ->
              response_text = bound_text(text, max_response_chars)
              budget = budget_usage(prompt, response_text, opts)

              case decode_recovery_decision(response_text, recovery_input, budget) do
                {:ok, decision} -> {:ok, decision}
                {:error, reason} -> {:ok, no_recovery_decision(recovery_input, budget, reason)}
              end

            {:error, reason} ->
              budget = budget_usage(prompt, "", opts)
              {:ok, no_recovery_decision(recovery_input, budget, reason)}
          end

        {:error, reason} ->
          budget = budget_usage(prompt, "", opts)
          {:ok, no_recovery_decision(recovery_input, budget, reason)}
      end
    end
  end

  def env(opts \\ [], recovery_input \\ nil) do
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
           session_id: session_id(opts, recovery_input)
         }}
    end
  end

  def recovery_id(opts \\ []) do
    case env(opts) do
      {:ok, env} -> "openclaw_agent_local/#{env.model}"
      {:error, _reason} -> "openclaw_agent_local/recovery"
    end
  end

  defp prompt(recovery_input) do
    sanitized =
      Map.take(recovery_input, [
        "schema_version",
        "experiment_id",
        "task_id",
        "episode_id",
        "allowed_recovery_policies",
        "budget_constraints",
        "failure_context"
      ])

    """
    You are a non-interactive Vanta Experiment 004 failure classifier and
    targeted recovery proposer. Return JSON only. Do not use tools or read/write
    files through the OpenClaw harness. Judge only the embedded input.

    Required JSON keys: failure_labels, primary_failure_label, recovery_policy,
    confidence, required_evidence_refs.

    Allowed recovery_policy values:
    #{Jason.encode!(@allowed_policies)}

    Use one or more failure labels. Prefer these Phase 4 labels when supported:
    F_EXEC_ROLLBACK_FAILURE, F_EXEC_AUDIT_GAP,
    F_EXEC_COMPENSATION_REQUIRED. Include F_EXEC when execution governance is
    the top-level class.

    Select no_recovery if the evidence is insufficient or the policy is not
    allowlisted. No prose, markdown fences, comments, or extra keys.

    Input JSON:
    #{Jason.encode!(sanitized)}
    """
  end

  defp call_openclaw(prompt, env, opts) do
    runner = Keyword.get(opts, :runner, &run_openclaw/2)
    runner.(prompt, env)
  end

  defp run_openclaw(prompt, env) do
    Vanta.OpenClawHarness.run_agent(prompt, env,
      temp_prefix: "vanta_openclaw_recovery",
      decoder: &decode_cli_json/1
    )
  end

  defp decode_recovery_decision(text, recovery_input, budget) do
    with {:ok, decoded} <- decode_json_or_embedded_json(strip_code_fence(text)) do
      {:ok, normalize_decision(decoded, recovery_input, budget)}
    end
  rescue
    error -> {:error, {:invalid_recovery_decision, Exception.message(error)}}
  end

  defp normalize_decision(decoded, recovery_input, budget) when is_map(decoded) do
    labels = string_list_or(decoded["failure_labels"], [])
    primary = string_or(decoded["primary_failure_label"], List.first(labels) || "unknown")
    policy = normalize_policy(decoded["recovery_policy"])

    decision = %{
      "schema_version" => Vanta.schema_version(),
      "decision_id" => "recovery_#{recovery_input["task_id"]}_#{recovery_input["episode_id"]}",
      "task_id" => recovery_input["task_id"],
      "episode_id" => recovery_input["episode_id"],
      "failure_labels" => labels,
      "primary_failure_label" => primary,
      "recovery_policy" => policy,
      "confidence" => clamp(decoded["confidence"], 0.0),
      "required_evidence_refs" => string_list_or(decoded["required_evidence_refs"], []),
      "budget_usage" => budget
    }

    Vanta.Schema.validate!("recovery_decision", decision)
  end

  defp normalize_decision(_decoded, recovery_input, budget),
    do: no_recovery_decision(recovery_input, budget, :non_object_output)

  defp no_recovery_decision(recovery_input, budget, reason) do
    decision = %{
      "schema_version" => Vanta.schema_version(),
      "decision_id" => "recovery_#{recovery_input["task_id"]}_#{recovery_input["episode_id"]}",
      "task_id" => recovery_input["task_id"],
      "episode_id" => recovery_input["episode_id"],
      "failure_labels" => [],
      "primary_failure_label" => "unknown",
      "recovery_policy" => "no_recovery",
      "confidence" => 0.0,
      "required_evidence_refs" => [],
      "budget_usage" => budget,
      "adapter_error" => inspect(reason)
    }

    Vanta.Schema.validate!("recovery_decision", decision)
  end

  defp budget_usage(prompt, response, opts) do
    prompt_chars = String.length(prompt)
    response_chars = String.length(response)

    %{
      "model_call_count" => 1,
      "prompt_chars" => prompt_chars,
      "response_chars" => response_chars,
      "estimated_input_tokens" => estimate_tokens(prompt_chars),
      "estimated_output_tokens" => estimate_tokens(response_chars),
      "max_prompt_chars" => Keyword.get(opts, :max_prompt_chars, @default_max_prompt_chars),
      "max_response_chars" => Keyword.get(opts, :max_response_chars, @default_max_response_chars),
      "max_action_attempts" =>
        Keyword.get(opts, :max_action_attempts, @default_max_action_attempts)
    }
  end

  defp estimate_tokens(chars), do: div(chars + 3, 4)

  defp decode_cli_json(output) do
    output
    |> candidate_json_suffixes()
    |> Enum.find_value(fn candidate ->
      case Jason.decode(candidate) do
        {:ok, decoded} -> {:ok, decoded}
        {:error, _error} -> nil
      end
    end)
    |> case do
      nil -> {:error, {:invalid_openclaw_json, output}}
      result -> result
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
          nil -> {:error, {:invalid_openclaw_recovery_json, Exception.message(first_error), text}}
          result -> {:ok, result}
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

  defp normalize_policy(policy) when policy in @allowed_policies, do: policy
  defp normalize_policy(_policy), do: "no_recovery"

  defp string_or(value, _fallback) when is_binary(value) and value != "", do: value
  defp string_or(_value, fallback), do: fallback

  defp string_list_or(values, _fallback) when is_list(values) do
    values
    |> Enum.filter(&is_binary/1)
    |> Enum.map(&String.trim/1)
    |> Enum.reject(&(&1 == ""))
  end

  defp string_list_or(_values, fallback), do: fallback

  defp clamp(value, _fallback) when is_number(value), do: value |> max(0.0) |> min(1.0)
  defp clamp(_value, fallback), do: fallback

  defp session_id(opts, recovery_input) do
    case Keyword.get(opts, :session_id) do
      value when not is_nil(value) ->
        to_string(value)

      nil ->
        task_id =
          case recovery_input do
            %{"task_id" => id} -> id
            _other -> "preflight"
          end

        unique = System.unique_integer([:positive])

        hash =
          :crypto.hash(:sha256, "#{task_id}:#{unique}")
          |> Base.encode16(case: :lower)
          |> binary_part(0, 12)

        slug =
          task_id
          |> String.replace(~r/[^a-zA-Z0-9]+/, "-")
          |> String.trim("-")
          |> String.slice(0, 28)
          |> case do
            "" -> "task"
            value -> value
          end

        "vexp004-#{slug}-#{hash}"
    end
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

  defp fallback(value, fallback_value) do
    if blank?(value), do: fallback_value, else: value
  end

  defp blank?(value), do: is_nil(value) or String.trim(to_string(value)) == ""
end
