defmodule Vanta.Hash do
  @moduledoc false

  def sha256(data) when is_binary(data) do
    "sha256:" <> Base.encode16(:crypto.hash(:sha256, data), case: :lower)
  end

  def file_hash(path) do
    path
    |> File.read!()
    |> sha256()
  end

  def term_hash(term) do
    term
    |> canonical_term()
    |> :erlang.term_to_binary()
    |> sha256()
  end

  def canonical_json_hash(term), do: term |> canonical_json() |> sha256()

  def canonical_json(map) when is_map(map) do
    map
    |> Enum.map(fn {key, value} -> {to_string(key), value} end)
    |> Enum.sort_by(&elem(&1, 0))
    |> Enum.map_join(",", fn {key, value} ->
      Jason.encode!(key) <> ":" <> canonical_json(value)
    end)
    |> then(&("{" <> &1 <> "}"))
  end

  def canonical_json(list) when is_list(list) do
    list
    |> Enum.map_join(",", &canonical_json/1)
    |> then(&("[" <> &1 <> "]"))
  end

  def canonical_json(value) when is_binary(value), do: Jason.encode!(value)
  def canonical_json(value) when is_integer(value), do: Integer.to_string(value)
  def canonical_json(value) when is_float(value), do: Jason.encode!(value)
  def canonical_json(true), do: "true"
  def canonical_json(false), do: "false"
  def canonical_json(nil), do: "null"
  def canonical_json(value) when is_atom(value), do: value |> Atom.to_string() |> Jason.encode!()

  def state_hash(state) when is_map(state) do
    state
    |> Map.delete("state_hash")
    |> canonical_json_hash()
  end

  defp canonical_term(map) when is_map(map) do
    map
    |> Enum.map(fn {key, value} -> {to_string(key), canonical_term(value)} end)
    |> Enum.sort_by(fn {key, _value} -> key end)
  end

  defp canonical_term(list) when is_list(list), do: Enum.map(list, &canonical_term/1)
  defp canonical_term(value), do: value
end
