defmodule Vanta.OpenClawVerifierAdapter do
  @moduledoc """
  OpenClaw-backed LLM verifier adapter for Experiment 002.

  The adapter calls the OpenClaw local agent harness through WSL and normalizes
  the assistant response into the Verifier Output schema. It is evaluation-only
  and is not used by the Stage 1 commit gate.
  """

  @default_model "openai-codex/gpt-5.4-mini"
  @default_openclaw_dir "~/openclaw"
  @default_agent "main"
  @default_timeout_seconds 600
  @default_thinking "off"

  @verification_scope ~w(
    preconditions
    postconditions
    evidence_sufficiency
    policy_constraints
    side_effect_safety
    state_consistency
    final_answer_correctness
  )

  def verify(review_item, opts \\ []) do
    with {:ok, env} <- env(opts, review_item),
         {:ok, response} <- call_openclaw(prompt(review_item), env, opts) do
      response
      |> extract_assistant_text()
      |> case do
        {:ok, text} ->
          case decode_verifier_output(text, review_item) do
            {:ok, verifier_output} -> {:ok, verifier_output}
            {:error, reason} -> {:ok, abstain_output(review_item, reason)}
          end

        {:error, reason} ->
          {:ok, abstain_output(review_item, reason)}
      end
    end
  end

  def env(opts \\ [], review_item \\ nil) do
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
           session_id: session_id(opts, review_item)
         }}
    end
  end

  def verifier_id(opts \\ []) do
    case env(opts) do
      {:ok, env} -> "openclaw_agent_local/#{env.model}_verifier"
      {:error, _reason} -> "openclaw_agent_local/verifier"
    end
  end

  defp prompt(review_item) do
    sanitized = prompt_review_item(review_item)

    """
    You are a non-interactive Vanta Experiment 002 verifier. Return JSON only.
    Do not use tools or read/write files. Judge only the embedded input.

    Required JSON keys: schema_version, verifier_output_id, episode_id, step_id,
    evidence_refs, decision, verification_scope, validity_score, confidence,
    risk_score, violated_constraints, required_extra_evidence.

    decision must be one of accept, reject, abstain, request_evidence.
    accept only when the input supports validity. reject constraint, side-effect,
    path, postcondition, or evidence violations. request_evidence for missing
    critical evidence. abstain only when still ambiguous.

    Scores are numbers from 0 to 1. No prose, markdown fences, comments, or
    extra keys.

    Input JSON:
    #{Jason.encode!(sanitized)}
    """
  end

  defp prompt_review_item(review_item) do
    Map.take(review_item, [
      "schema_version",
      "experiment_id",
      "arm",
      "review_item_id",
      "task_id",
      "episode_id",
      "step_id",
      "evidence_refs",
      "verifier_input"
    ])
  end

  defp call_openclaw(prompt, env, opts) do
    runner = Keyword.get(opts, :runner, &run_openclaw/2)
    runner.(prompt, env)
  end

  defp run_openclaw(prompt, env) do
    Vanta.OpenClawHarness.run_agent(prompt, env,
      temp_prefix: "vanta_openclaw",
      decoder: &decode_cli_json/1
    )
  end

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

  defp decode_verifier_output(text, review_item) do
    with {:ok, decoded} <- decode_json_or_embedded_json(strip_code_fence(text)) do
      {:ok, normalize_output(decoded, review_item)}
    end
  rescue
    error -> {:error, {:invalid_verifier_output, Exception.message(error)}}
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
          nil -> {:error, {:invalid_openclaw_verifier_json, Exception.message(first_error), text}}
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

  defp normalize_output(decoded, review_item) when is_map(decoded) do
    verifier_output = %{
      "schema_version" => Vanta.schema_version(),
      "verifier_output_id" =>
        string_or(decoded["verifier_output_id"], "llm_verifier_#{review_item["review_item_id"]}"),
      "episode_id" => string_or(decoded["episode_id"], review_item["episode_id"]),
      "step_id" => string_or(decoded["step_id"], review_item["step_id"]),
      "evidence_refs" =>
        string_list_or(decoded["evidence_refs"], review_item["evidence_refs"] || []),
      "decision" => normalize_decision(decoded["decision"]),
      "verification_scope" => normalize_scope(decoded["verification_scope"]),
      "validity_score" => clamp(decoded["validity_score"], 0.0),
      "confidence" => clamp(decoded["confidence"], 0.0),
      "calibration_state" =>
        map_or(decoded["calibration_state"], %{"method" => "openclaw_llm_verifier_v0"}),
      "disagreement" => map_or(decoded["disagreement"], %{}),
      "risk_score" => clamp(decoded["risk_score"], 0.5),
      "violated_constraints" => string_list_or(decoded["violated_constraints"], []),
      "required_extra_evidence" => string_list_or(decoded["required_extra_evidence"], []),
      "failure_logits" => map_or(decoded["failure_logits"], %{}),
      "credit_hints" => map_or(decoded["credit_hints"], %{})
    }

    Vanta.Schema.validate!("verifier_output", verifier_output)
  end

  defp normalize_output(_decoded, review_item),
    do: abstain_output(review_item, :non_object_output)

  defp abstain_output(review_item, reason) do
    verifier_output = %{
      "schema_version" => Vanta.schema_version(),
      "verifier_output_id" => "llm_verifier_#{review_item["review_item_id"]}",
      "episode_id" => review_item["episode_id"],
      "step_id" => review_item["step_id"],
      "evidence_refs" => review_item["evidence_refs"] || [],
      "decision" => "abstain",
      "verification_scope" => @verification_scope,
      "validity_score" => 0.0,
      "confidence" => 0.0,
      "calibration_state" => %{
        "method" => "openclaw_llm_verifier_v0",
        "normalization" => "parse_failure_to_abstain"
      },
      "disagreement" => %{},
      "risk_score" => 1.0,
      "violated_constraints" => [],
      "required_extra_evidence" => ["schema_valid_verifier_output"],
      "failure_logits" => %{},
      "credit_hints" => %{"adapter_error" => inspect(reason)}
    }

    Vanta.Schema.validate!("verifier_output", verifier_output)
  end

  defp candidate_json_suffixes(output) do
    output
    |> String.graphemes()
    |> Enum.with_index()
    |> Enum.filter(fn {char, _index} -> char == "{" end)
    |> Enum.map(fn {_char, index} -> String.slice(output, index..-1//1) end)
  end

  defp normalize_decision("needs_more_evidence"), do: "request_evidence"

  defp normalize_decision(decision) when decision in ~w(accept reject abstain request_evidence),
    do: decision

  defp normalize_decision(_decision), do: "abstain"

  defp normalize_scope(scope) when is_list(scope) do
    scope
    |> Enum.filter(&(&1 in @verification_scope))
    |> case do
      [] -> @verification_scope
      values -> values
    end
  end

  defp normalize_scope(_scope), do: @verification_scope

  defp string_or(value, _fallback) when is_binary(value) and value != "", do: value
  defp string_or(_value, fallback), do: fallback

  defp string_list_or(values, _fallback) when is_list(values) do
    values
    |> Enum.filter(&is_binary/1)
    |> Enum.map(&String.trim/1)
    |> Enum.reject(&(&1 == ""))
  end

  defp string_list_or(_values, fallback), do: fallback

  defp map_or(value, _fallback) when is_map(value), do: value
  defp map_or(_value, fallback), do: fallback

  defp clamp(value, _fallback) when is_number(value), do: value |> max(0.0) |> min(1.0)
  defp clamp(_value, fallback), do: fallback

  defp session_id(opts, review_item) do
    case Keyword.get(opts, :session_id) do
      value when not is_nil(value) ->
        to_string(value)

      nil ->
        item_id =
          case review_item do
            %{"review_item_id" => id} -> id
            _other -> "preflight"
          end

        unique = System.unique_integer([:positive])

        hash =
          :crypto.hash(:sha256, "#{item_id}:#{unique}")
          |> Base.encode16(case: :lower)
          |> binary_part(0, 12)

        slug =
          item_id
          |> String.replace(~r/[^a-zA-Z0-9]+/, "-")
          |> String.trim("-")
          |> String.slice(0, 28)
          |> case do
            "" -> "item"
            value -> value
          end

        "vexp002-#{slug}-#{hash}"
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
