defmodule Mix.Tasks.Vanta.PersistenceExperiment do
  use Mix.Task

  @shortdoc "Runs Experiment 006 persistence and recovery failure injection"

  @impl true
  def run(args) do
    Mix.Task.run("app.start")

    {opts, _argv, _invalid} =
      OptionParser.parse(args, strict: [timestamp: :string, result_dir: :string])

    run_opts =
      []
      |> maybe_put(:timestamp, opts[:timestamp])
      |> maybe_put(:result_dir, opts[:result_dir])

    {:ok, %{result_dir: result_dir, run: run}} = Vanta.PersistenceExperiment.run(run_opts)
    Mix.shell().info("Experiment 006: #{run["threshold_status"]}")
    Mix.shell().info("Results: #{result_dir}")
  end

  defp maybe_put(opts, _key, nil), do: opts
  defp maybe_put(opts, key, value), do: Keyword.put(opts, key, value)
end
