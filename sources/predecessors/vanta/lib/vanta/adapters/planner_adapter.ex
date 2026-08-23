defmodule Vanta.PlannerAdapter do
  @moduledoc """
  Minimal planner adapter for Stage 1 action sequence proposals.
  """

  def propose(task, action_type, payload \\ %{}) do
    %{
      "task_id" => Map.fetch!(task, "task_id"),
      "action_type" => action_type,
      "action_payload" => payload
    }
  end

  def propose_actions(_task, _workspace, opts \\ []) do
    cond do
      Keyword.has_key?(opts, :action_sequence) ->
        validate_action_sequence(Keyword.fetch!(opts, :action_sequence))

      Keyword.has_key?(opts, :actions) ->
        validate_action_sequence(%{"actions" => Keyword.fetch!(opts, :actions)})

      true ->
        {:error, :missing_action_sequence}
    end
  end

  def validate_action_sequence(action_sequence) when is_map(action_sequence) do
    action_sequence =
      action_sequence
      |> stringify_keys()
      |> Map.update("actions", [], &Enum.map(&1, fn action -> stringify_keys(action) end))

    case Vanta.Schema.validate("planner_action_sequence", action_sequence) do
      :ok -> {:ok, action_sequence}
      {:error, errors} -> {:error, {:invalid_action_sequence, errors}}
    end
  end

  def validate_action_sequence(_action_sequence), do: {:error, :invalid_action_sequence}

  defp stringify_keys(map) when is_map(map) do
    Map.new(map, fn {key, value} -> {to_string(key), stringify_value(value)} end)
  end

  defp stringify_value(value) when is_map(value), do: stringify_keys(value)
  defp stringify_value(values) when is_list(values), do: Enum.map(values, &stringify_value/1)
  defp stringify_value(value), do: value
end
