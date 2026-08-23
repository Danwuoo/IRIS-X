defmodule Vanta.PostStage1LargerSample.PathHelpers do
  @moduledoc false

  alias Vanta.Hash

  def fixture_hash(workspace) do
    workspace
    |> Path.join("**/*")
    |> Path.wildcard()
    |> Enum.filter(&File.regular?/1)
    |> Enum.map(fn path ->
      relative =
        path
        |> Path.relative_to(workspace)
        |> String.replace("\\", "/")

      "#{relative}:#{Hash.file_hash(path)}"
    end)
    |> Enum.sort()
    |> Enum.join("\n")
    |> Hash.sha256()
  end

  def present?(value), do: is_binary(value) and String.trim(value) != ""
end
