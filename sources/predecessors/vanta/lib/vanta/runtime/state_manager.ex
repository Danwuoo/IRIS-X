defmodule Vanta.StateManager do
  @moduledoc """
  Maintains canonical state and state hashes for Stage 1 fixture episodes.
  """

  alias Vanta.Hash

  def from_task(task) do
    task
    |> Map.fetch!("initial_state")
    |> ensure_hash()
  end

  def append_event(state, event) when is_map(event) do
    events = Map.get(state, "events", [])

    state
    |> Map.put("events", events ++ [event])
    |> ensure_hash()
  end

  def ensure_hash(state) do
    Map.put(state, "state_hash", Hash.state_hash(state))
  end
end
