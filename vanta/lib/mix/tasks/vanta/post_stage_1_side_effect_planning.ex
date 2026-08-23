defmodule Mix.Tasks.Vanta.PostStage1SideEffectPlanning do
  @moduledoc """
  Runs the PS1-G8 fixture-local Document Ops planning pilot.
  """

  use Mix.Task

  @shortdoc "Run the PS1-G8 side-effect planning pilot"

  @impl Mix.Task
  def run(args) do
    Mix.Task.run("app.start")

    {opts, _argv, _invalid} =
      OptionParser.parse(args,
        strict: [
          out: :string,
          timestamp: :string,
          fixtures: :string
        ]
      )

    runner_opts =
      compact_opts(
        out_dir: Keyword.get(opts, :out),
        timestamp: Keyword.get(opts, :timestamp),
        fixture_root: Keyword.get(opts, :fixtures)
      )

    {:ok, run} = Vanta.PostStage1SideEffectPlanning.run(runner_opts)

    Mix.shell().info(
      "PS1-G8 #{run["report_label"]} #{run["completion_status"]}; threshold #{run["threshold_status"]}; runtime execution #{run["runtime_execution_status"]}."
    )

    Mix.shell().info("Results: #{run["artifact_root"]}")
  end

  defp compact_opts(opts) do
    Enum.reject(opts, fn {_key, value} -> is_nil(value) end)
  end
end
