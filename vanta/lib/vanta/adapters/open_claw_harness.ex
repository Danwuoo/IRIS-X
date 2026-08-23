defmodule Vanta.OpenClawHarness do
  @moduledoc """
  Shared OpenClaw local harness runner.

  The OpenClaw CLI accepts its own `--timeout`, but Lane A runs also need an OS
  process-level deadline so a stuck CLI call cannot block the whole batch.
  """

  @outer_timeout_grace_seconds 30

  def run_agent(prompt, env, opts) do
    temp_prefix = Keyword.fetch!(opts, :temp_prefix)
    decoder = Keyword.fetch!(opts, :decoder)
    command_runner = Keyword.get(opts, :command_runner, &System.cmd/3)
    prompt_path = temp_file_path(temp_prefix, "prompt", ".txt")
    script_path = temp_file_path(temp_prefix, "script", ".sh")

    File.write!(prompt_path, prompt)
    File.write!(script_path, agent_script(env, prompt_path))

    try do
      script = ["bash ", shell_quote(wsl_path(script_path))] |> IO.iodata_to_binary()

      case command_runner.(env.wsl_executable, ["--", "bash", "-lic", script],
             stderr_to_stdout: true
           ) do
        {output, 0} -> decoder.(output)
        {output, status} -> {:error, {:openclaw_cli_failed, status, output}}
      end
    after
      File.rm(prompt_path)
      File.rm(script_path)
    end
  end

  def agent_script(env, prompt_path) do
    [
      "#!/usr/bin/env bash\n",
      "set -euo pipefail\n",
      "cd ",
      shell_path(env.openclaw_dir),
      "\n",
      "timeout --kill-after=5s ",
      Integer.to_string(outer_timeout_seconds(env)),
      "s ",
      "pnpm openclaw --no-color agent --local --json",
      maybe_arg("--agent", env.agent),
      " --session-id ",
      shell_quote(env.session_id),
      " --model ",
      shell_quote(env.model),
      maybe_arg("--thinking", env.thinking),
      " --message \"$(cat ",
      shell_quote(wsl_path(prompt_path)),
      ")\"",
      " --timeout ",
      Integer.to_string(env.timeout_seconds),
      "\n"
    ]
    |> IO.iodata_to_binary()
  end

  defp outer_timeout_seconds(env) do
    env.timeout_seconds + @outer_timeout_grace_seconds
  end

  defp temp_file_path(prefix, kind, extension) do
    Path.join(
      System.tmp_dir!(),
      "#{prefix}_#{kind}_#{System.unique_integer([:positive])}#{extension}"
    )
  end

  defp wsl_path(path) do
    path = Path.expand(path)

    case Regex.run(~r/\A([a-zA-Z]):[\\\/](.*)\z/, path) do
      [_, drive, rest] ->
        "/mnt/#{String.downcase(drive)}/" <> String.replace(rest, "\\", "/")

      _other ->
        String.replace(path, "\\", "/")
    end
  end

  defp maybe_arg(_name, value) when is_nil(value), do: ""

  defp maybe_arg(name, value) do
    value = to_string(value)

    if blank?(value) do
      ""
    else
      [" ", name, " ", shell_quote(value)]
    end
  end

  defp shell_path("~/"), do: "~"

  defp shell_path("~/" <> rest) do
    if String.match?(rest, ~r/\A[-_a-zA-Z0-9.\/]+\z/) do
      "~/" <> rest
    else
      shell_quote("~/" <> rest)
    end
  end

  defp shell_path(path), do: shell_quote(path)

  defp shell_quote(value) do
    "'" <> String.replace(to_string(value), "'", "'\\''") <> "'"
  end

  defp blank?(value), do: is_nil(value) or String.trim(to_string(value)) == ""
end
