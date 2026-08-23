defmodule Vanta.PostStage1SideEffectPlanning.PathHelpers do
  @moduledoc false

  alias Vanta.Hash

  def fixture_tree_hash(root) do
    root
    |> Path.join("**/*")
    |> Path.wildcard()
    |> Enum.filter(&File.regular?/1)
    |> Enum.map(fn path ->
      relative = path |> Path.relative_to(root) |> normalize_separator()
      "#{relative}:#{Hash.file_hash(path)}"
    end)
    |> Enum.sort()
    |> Enum.join("\n")
    |> Hash.sha256()
  end

  def present?(value), do: is_binary(value) and String.trim(value) != ""

  def safe_relative_path?(path) when is_binary(path) do
    Path.type(path) == :relative and
      path
      |> normalize_separator()
      |> String.split("/", trim: true)
      |> Enum.all?(&(&1 not in [".", ".."]))
  end

  def safe_relative_path?(_path), do: false

  def inside_workspace?(path, workspace_root)
      when is_binary(path) and is_binary(workspace_root) do
    normalized_path = normalize_separator(path)
    normalized_root = workspace_root |> normalize_separator() |> String.trim_trailing("/")

    safe_relative_path?(normalized_path) and
      safe_relative_path?(normalized_root) and
      (normalized_path == normalized_root or
         String.starts_with?(normalized_path, normalized_root <> "/"))
  end

  def inside_workspace?(_path, _workspace_root), do: false

  def inside_root?(path, root) do
    expanded_path = path |> Path.expand() |> normalize_separator() |> String.trim_trailing("/")
    expanded_root = root |> Path.expand() |> normalize_separator() |> String.trim_trailing("/")

    expanded_path == expanded_root or String.starts_with?(expanded_path, expanded_root <> "/")
  end

  def normalize_separator(path), do: String.replace(path, "\\", "/")
end
