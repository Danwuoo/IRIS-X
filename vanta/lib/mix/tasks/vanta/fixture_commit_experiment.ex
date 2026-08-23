defmodule Mix.Tasks.Vanta.FixtureCommitExperiment do
  use Mix.Task

  @shortdoc "Run PS1-G10 fixture-local COMMITTABLE Experiment 007"

  @impl Mix.Task
  def run(args) do
    Mix.Task.run("app.start")

    {opts, _rest, _invalid} =
      OptionParser.parse(args, strict: [out_dir: :string, fixture_root: :string])

    runner_opts =
      []
      |> maybe_put(:out_dir, opts[:out_dir])
      |> maybe_put(:fixture_root, opts[:fixture_root])

    {:ok, result} = Vanta.FixtureCommitExperiment.run(runner_opts)
    Mix.shell().info("#{result.run["threshold_status"]}: #{result.out_dir}")
  end

  defp maybe_put(opts, _key, nil), do: opts
  defp maybe_put(opts, key, value), do: Keyword.put(opts, key, value)
end
