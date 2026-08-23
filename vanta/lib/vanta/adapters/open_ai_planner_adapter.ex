defmodule Vanta.OpenAIPlannerAdapter do
  @moduledoc """
  OpenAI-compatible Stage 1 planner adapter.

  This adapter is env-gated and is used for the Experiment 001 LLM baseline. It
  returns a JSON action sequence and does not act as a verifier.
  """

  alias Vanta.PlannerAdapter

  @default_base_url "https://api.openai.com/v1"

  def propose_actions(task, workspace, opts \\ []) do
    with {:ok, env} <- env(opts),
         {:ok, request} <- request_body(task, workspace, env),
         {:ok, response} <- post_response(request, env, opts),
         {:ok, action_sequence} <- extract_action_sequence(response) do
      PlannerAdapter.validate_action_sequence(action_sequence)
    end
  end

  def env(opts \\ []) do
    api_key = Keyword.get(opts, :api_key) || System.get_env("OPENAI_API_KEY")
    model = Keyword.get(opts, :model) || System.get_env("OPENAI_MODEL")

    base_url =
      Keyword.get(opts, :base_url) || System.get_env("OPENAI_BASE_URL") || @default_base_url

    cond do
      blank?(api_key) ->
        {:error, :missing_openai_api_key}

      blank?(model) ->
        {:error, :missing_openai_model}

      true ->
        {:ok, %{api_key: api_key, model: model, base_url: String.trim_trailing(base_url, "/")}}
    end
  end

  def baseline_id(opts \\ []) do
    case env(opts) do
      {:ok, env} -> "responses_api/#{env.model}_direct_execution"
      {:error, _reason} -> "responses_api/direct_execution"
    end
  end

  defp request_body(task, workspace, env) do
    prompt = """
    Produce a JSON action sequence for this Stage 1 Document Ops fixture.

    You may only return actions from allowed_actions. Use fixture-local paths only.
    Return JSON only; no prose.

    Task:
    #{Jason.encode!(task, pretty: true)}

    Input artifact previews:
    #{Jason.encode!(artifact_previews(task, workspace), pretty: true)}
    """

    {:ok,
     %{
       "model" => env.model,
       "input" => prompt,
       "text" => %{
         "format" => %{
           "type" => "json_schema",
           "name" => "planner_action_sequence",
           "strict" => true,
           "schema" => action_sequence_output_schema()
         }
       }
     }}
  end

  defp post_response(request, env, opts) do
    client = Keyword.get(opts, :client, &http_post/2)
    client.(request, env)
  end

  defp http_post(request, env) do
    url = String.to_charlist(env.base_url <> "/responses")

    headers = [
      {~c"content-type", ~c"application/json"},
      {~c"authorization", String.to_charlist("Bearer " <> env.api_key)}
    ]

    body = Jason.encode!(request)

    case :httpc.request(:post, {url, headers, ~c"application/json", body}, [],
           body_format: :binary
         ) do
      {:ok, {{_version, status, _reason}, _headers, response_body}} when status in 200..299 ->
        {:ok, Jason.decode!(response_body)}

      {:ok, {{_version, status, reason}, _headers, response_body}} ->
        {:error, {:openai_http_error, status, to_string(reason), response_body}}

      {:error, reason} ->
        {:error, {:openai_request_failed, reason}}
    end
  end

  defp extract_action_sequence(%{"output_text" => output_text}) when is_binary(output_text) do
    decode_action_sequence(output_text)
  end

  defp extract_action_sequence(%{"output" => output}) when is_list(output) do
    output
    |> Enum.flat_map(&Map.get(&1, "content", []))
    |> Enum.find_value(fn
      %{"type" => "output_text", "text" => text} -> text
      %{"text" => text} -> text
      _other -> nil
    end)
    |> case do
      nil -> {:error, :missing_openai_output_text}
      text -> decode_action_sequence(text)
    end
  end

  defp extract_action_sequence(_response), do: {:error, :missing_openai_output_text}

  defp decode_action_sequence(output_text) do
    case Jason.decode(output_text) do
      {:ok, action_sequence} -> {:ok, action_sequence}
      {:error, error} -> {:error, {:invalid_openai_json, Exception.message(error)}}
    end
  end

  defp artifact_previews(task, workspace) do
    task
    |> Map.get("input_artifacts", [])
    |> Enum.map(fn artifact ->
      path = artifact["path"]
      abs_path = Path.join(workspace, path)

      %{
        "path" => path,
        "role" => artifact["role"],
        "content" => if(File.regular?(abs_path), do: File.read!(abs_path), else: nil)
      }
    end)
  end

  defp action_sequence_output_schema do
    %{
      "type" => "object",
      "additionalProperties" => false,
      "required" => ["actions"],
      "properties" => %{
        "actions" => %{
          "type" => "array",
          "items" => %{
            "type" => "object",
            "additionalProperties" => false,
            "required" => ["action_type", "action_payload"],
            "properties" => %{
              "action_type" => %{"type" => "string", "enum" => Vanta.action_types()},
              "action_payload" => %{"type" => "object", "additionalProperties" => true}
            }
          }
        }
      }
    }
  end

  defp blank?(value), do: is_nil(value) or String.trim(to_string(value)) == ""
end
