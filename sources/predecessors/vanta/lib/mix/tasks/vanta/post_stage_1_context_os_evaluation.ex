defmodule Mix.Tasks.Vanta.PostStage1ContextOsEvaluation do
  @moduledoc """
  Runs the deterministic PS1-G7 artifact-backed Context OS evaluation pilot.
  """

  use Mix.Task

  @shortdoc "Run the PS1-G7 artifact-backed context evaluation pilot"

  @impl Mix.Task
  def run(args) do
    Mix.Task.run("app.start")

    {opts, _argv, _invalid} =
      OptionParser.parse(args,
        strict: [
          out: :string,
          timestamp: :string,
          source_run: :string,
          packet_dir: :string,
          attestation: :string
        ]
      )

    runner_opts =
      [
        out_dir: Keyword.get(opts, :out),
        timestamp: Keyword.get(opts, :timestamp),
        source_run: Keyword.get(opts, :source_run),
        packet_dir: Keyword.get(opts, :packet_dir),
        attestation: Keyword.get(opts, :attestation)
      ]
      |> Enum.reject(fn {_key, value} -> is_nil(value) end)

    case Vanta.PostStage1ContextOSEvaluation.run(runner_opts) do
      {:ok, run} ->
        Mix.shell().info(
          "PS1-G7 #{run["final_pilot_status"]}; fingerprint #{run["evaluation_fingerprint"]}."
        )

        Mix.shell().info("Results: #{run["artifact_root"]}")

      {:error, errors} ->
        Mix.raise(
          "PS1-G7 artifact-backed evaluation failed closed:\n- #{Enum.join(errors, "\n- ")}"
        )
    end
  end
end
