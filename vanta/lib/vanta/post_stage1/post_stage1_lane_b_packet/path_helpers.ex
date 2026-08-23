defmodule Vanta.PostStage1LaneBPacket.PathHelpers do
  @moduledoc false

  def closure_status(path) do
    case File.read(path) do
      {:ok, content} ->
        case Regex.run(~r/Status:\s+`([^`]+)`/, content) do
          [_, status] -> status
          _other -> "unknown"
        end

      {:error, _reason} ->
        "unknown"
    end
  end

  def load_text(path) do
    case File.read(path) do
      {:ok, text} -> {:ok, strip_bom(text)}
      {:error, reason} -> {:error, ["failed to read #{path}: #{:file.format_error(reason)}"]}
    end
  end

  def existing_text_or(path, required_markers, fallback_fun) do
    case load_text(path) do
      {:ok, text} ->
        if Enum.all?(required_markers, &String.contains?(text, &1)) do
          text
        else
          fallback_fun.()
        end

      {:error, _errors} ->
        fallback_fun.()
    end
  end

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

  def load_optional_json(path) do
    if File.exists?(path) do
      load_json(path)
    else
      {:ok, nil}
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

  def write_json!(path, data), do: write_text!(path, Jason.encode!(data, pretty: true))

  def write_jsonl!(path, rows) do
    text =
      rows
      |> Enum.map(&Jason.encode!/1)
      |> Enum.join("\n")

    write_text!(path, text <> "\n")
  end

  def write_text!(path, text), do: File.write!(path, text)

  def strip_bom(<<0xEF, 0xBB, 0xBF, rest::binary>>), do: rest
  def strip_bom(text), do: text

  def display_path(path, cwd) do
    expanded = Path.expand(path, cwd)
    cwd = Path.expand(cwd)
    relative = Path.relative_to(expanded, cwd)

    relative
    |> slash_path()
  end

  def path_join(left, right), do: Path.join(left, right) |> slash_path()

  def slash_path(path), do: String.replace(path, "\\", "/")

  def ensure_trailing_slash(path) do
    if String.ends_with?(path, "/"), do: path, else: path <> "/"
  end

  def present?(value) when is_binary(value), do: String.trim(value) != ""
  def present?(nil), do: false
  def present?(_value), do: true
end
