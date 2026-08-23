defmodule Vanta.PathGuard do
  @moduledoc false

  def resolve!(workspace, relative_path) when is_binary(relative_path) do
    workspace_root = workspace |> Path.expand() |> normalize()
    target = relative_path |> Path.expand(workspace_root) |> normalize()

    if inside?(target, workspace_root) do
      target
    else
      raise ArgumentError, "path escapes fixture workspace: #{relative_path}"
    end
  end

  def safe_resolve(workspace, relative_path) when is_binary(relative_path) do
    {:ok, resolve!(workspace, relative_path)}
  rescue
    error in ArgumentError -> {:error, Exception.message(error)}
  end

  def relative(workspace, path) do
    path
    |> Path.relative_to(Path.expand(workspace))
    |> normalize_separator()
  end

  def normalize_separator(path), do: String.replace(path, "\\", "/")

  defp inside?(target, root) do
    target == root or String.starts_with?(target, root <> "/")
  end

  defp normalize(path) do
    path
    |> String.replace("\\", "/")
    |> String.trim_trailing("/")
  end
end
