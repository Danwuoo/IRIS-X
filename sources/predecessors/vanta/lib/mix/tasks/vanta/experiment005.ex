defmodule Mix.Tasks.Vanta.Experiment005 do
  @moduledoc """
  Runs Experiment 005 against Phase 5 Document Ops working-set fixtures.
  """

  use Mix.Task

  @shortdoc "Run Vanta Experiment 005"

  @impl Mix.Task
  def run(args) do
    Mix.Task.run("app.start")

    {opts, _argv, _invalid} =
      OptionParser.parse(args,
        strict: [
          out: :string,
          fixtures: :string,
          model: :string,
          openclaw_dir: :string,
          openclaw_agent: :string,
          openclaw_timeout_seconds: :integer,
          openclaw_thinking: :string,
          max_prompt_chars: :integer,
          max_response_chars: :integer,
          max_context_chars: :integer
        ]
      )

    fixture_root =
      Keyword.get(
        opts,
        :fixtures,
        Path.expand("test/fixtures/document_ops", File.cwd!())
      )

    planner_opts =
      compact_opts(
        model: Keyword.get(opts, :model),
        openclaw_dir: Keyword.get(opts, :openclaw_dir),
        agent: Keyword.get(opts, :openclaw_agent),
        timeout_seconds: Keyword.get(opts, :openclaw_timeout_seconds),
        thinking: Keyword.get(opts, :openclaw_thinking),
        max_prompt_chars: Keyword.get(opts, :max_prompt_chars),
        max_response_chars: Keyword.get(opts, :max_response_chars)
      )

    case Vanta.Experiment005.run(fixture_root,
           out_dir: Keyword.get(opts, :out),
           planner_opts: planner_opts,
           max_context_chars: Keyword.get(opts, :max_context_chars)
         ) do
      {:ok, run} ->
        Mix.shell().info("Experiment 005 #{run["status"]} for #{run["fixture_count"]} fixtures.")

      {:error, {:openclaw_context_planner_not_configured, reason}} ->
        Mix.raise("OpenClaw context planner is not configured: #{inspect(reason)}")

      {:error, reason} ->
        Mix.raise("Experiment 005 failed: #{inspect(reason)}")
    end
  end

  defp compact_opts(opts) do
    Enum.reject(opts, fn {_key, value} -> is_nil(value) end)
  end
end
