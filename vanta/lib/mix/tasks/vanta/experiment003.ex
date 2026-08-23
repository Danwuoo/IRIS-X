defmodule Mix.Tasks.Vanta.Experiment003 do
  @moduledoc """
  Runs Experiment 003 against local Document Ops fixtures.
  """

  use Mix.Task

  @shortdoc "Run Vanta Experiment 003"

  @impl Mix.Task
  def run(args) do
    Mix.Task.run("app.start")

    {opts, _argv, _invalid} =
      OptionParser.parse(args,
        strict: [
          out: :string,
          fixtures: :string
        ]
      )

    fixture_root =
      Keyword.get(
        opts,
        :fixtures,
        Path.expand("test/fixtures/document_ops", File.cwd!())
      )

    out_dir = Keyword.get(opts, :out)

    {:ok, run} = Vanta.Experiment003.run(fixture_root, out_dir: out_dir)
    Mix.shell().info("Experiment 003 #{run["status"]} for #{run["fixture_count"]} fixtures.")
  end
end
