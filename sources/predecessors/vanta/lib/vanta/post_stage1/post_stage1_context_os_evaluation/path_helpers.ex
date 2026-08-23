defmodule Vanta.PostStage1ContextOSEvaluation.PathHelpers do
  @moduledoc false

  alias Vanta.Hash

  def load_json(path) do
    with {:ok, text} <- File.read(path),
         text <- strip_utf8_bom(text),
         {:ok, value} <- Jason.decode(text) do
      {:ok, value}
    else
      {:error, %Jason.DecodeError{} = error} ->
        {:error, ["invalid JSON #{normalize_separator(path)}: #{Exception.message(error)}"]}

      {:error, reason} ->
        {:error, ["cannot read #{normalize_separator(path)}: #{inspect(reason)}"]}
    end
  end

  def load_jsonl(path) do
    with {:ok, text} <- File.read(path) do
      text
      |> strip_utf8_bom()
      |> String.split(~r/\R/, trim: true)
      |> Enum.with_index(1)
      |> Enum.reduce_while({:ok, []}, fn {line, line_number}, {:ok, values} ->
        case Jason.decode(line) do
          {:ok, value} ->
            {:cont, {:ok, values ++ [value]}}

          {:error, error} ->
            {:halt,
             {:error,
              [
                "invalid JSONL #{normalize_separator(path)} line #{line_number}: #{Exception.message(error)}"
              ]}}
        end
      end)
    else
      {:error, reason} ->
        {:error, ["cannot read #{normalize_separator(path)}: #{inspect(reason)}"]}
    end
  end

  def load_json_directory(path) do
    paths = path |> Path.join("*.json") |> Path.wildcard() |> Enum.sort()

    if paths == [] do
      {:error, ["JSON directory is empty: #{normalize_separator(path)}"]}
    else
      Enum.reduce_while(paths, {:ok, %{}}, fn file_path, {:ok, values} ->
        case load_json(file_path) do
          {:ok, value} ->
            {:cont, {:ok, Map.put(values, Path.basename(file_path), value)}}

          {:error, errors} ->
            {:halt, {:error, errors}}
        end
      end)
    end
  end

  def source_ref(path, cwd) do
    %{
      "path" => display_path(path, cwd),
      "sha256" => Hash.file_hash(path)
    }
  end

  def tree_ref(path, cwd) do
    %{
      "path" => display_path(path, cwd) <> "/",
      "sha256" => tree_hash(path),
      "file_count" => path |> Path.join("**/*") |> Path.wildcard() |> Enum.count(&File.regular?/1)
    }
  end

  def tree_hash(root) do
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

  def display_path(path, cwd \\ File.cwd!()) do
    path
    |> Path.expand(cwd)
    |> Path.relative_to(Path.expand(cwd))
    |> normalize_separator()
  end

  def present?(value), do: is_binary(value) and String.trim(value) != ""
  def normalize_separator(path), do: String.replace(path, "\\", "/")

  def same_number?(left, right) when is_number(left) and is_number(right),
    do: abs(left - right) <= 1.0e-12

  def same_number?(_left, _right), do: false

  defp strip_utf8_bom(<<0xEF, 0xBB, 0xBF, rest::binary>>), do: rest
  defp strip_utf8_bom(text), do: text
end
