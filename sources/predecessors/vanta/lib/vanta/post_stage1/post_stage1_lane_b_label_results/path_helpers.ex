defmodule Vanta.PostStage1LaneBLabelResults.PathHelpers do
  @moduledoc false

  def load_json(path) do
    with {:ok, text} <- load_text(path),
         {:ok, json} <- Jason.decode(text) do
      {:ok, json}
    else
      {:error, errors} when is_list(errors) ->
        {:error, errors}

      {:error, %Jason.DecodeError{} = error} ->
        {:error, ["failed to decode JSON #{path}: #{Exception.message(error)}"]}
    end
  end

  def load_jsonl(path) do
    with {:ok, text} <- load_text(path) do
      text
      |> String.split(~r/\R/, trim: true)
      |> Enum.reduce_while({:ok, []}, fn line, {:ok, rows} ->
        case Jason.decode(line) do
          {:ok, row} ->
            {:cont, {:ok, rows ++ [row]}}

          {:error, error} ->
            {:halt, {:error, ["failed to decode JSONL #{path}: #{Exception.message(error)}"]}}
        end
      end)
    end
  end

  def load_text(path) do
    case File.read(path) do
      {:ok, text} -> {:ok, strip_bom(text)}
      {:error, reason} -> {:error, ["failed to read #{path}: #{:file.format_error(reason)}"]}
    end
  end

  def load_surface_texts(surface_paths, cwd) do
    surface_paths
    |> List.wrap()
    |> Enum.reduce_while({:ok, []}, fn path, {:ok, surfaces} ->
      path_abs = Path.expand(path, cwd)

      case load_text(path_abs) do
        {:ok, text} ->
          {:cont, {:ok, surfaces ++ [{display_path(path_abs, cwd), text}]}}

        {:error, errors} ->
          {:halt, {:error, errors}}
      end
    end)
  end

  def write_json!(path, data), do: File.write!(path, Jason.encode!(data, pretty: true))

  def strip_bom(<<0xEF, 0xBB, 0xBF, rest::binary>>), do: rest
  def strip_bom(text), do: text

  def path_join(left, right), do: Path.join(left, right) |> slash_path()

  def display_path(path, cwd) do
    expanded = Path.expand(path, cwd)
    cwd = Path.expand(cwd)

    expanded
    |> Path.relative_to(cwd)
    |> slash_path()
  end

  def slash_path(path), do: String.replace(path, "\\", "/")

  def present?(value) when is_binary(value), do: String.trim(value) != ""
  def present?(nil), do: false
  def present?(_value), do: true
end
