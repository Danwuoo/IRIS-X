defmodule Mix.Tasks.Vanta.Experiment002 do
  @moduledoc """
  Runs Experiment 002 against local Document Ops fixtures.
  """

  use Mix.Task

  @shortdoc "Run Vanta Experiment 002"

  @impl Mix.Task
  def run(args) do
    Mix.Task.run("app.start")

    {opts, _argv, _invalid} =
      OptionParser.parse(args,
        strict: [
          verifier: :string,
          out: :string,
          fixtures: :string,
          model: :string,
          openclaw_dir: :string,
          openclaw_agent: :string,
          openclaw_timeout_seconds: :integer,
          openclaw_thinking: :string
        ]
      )

    fixture_root =
      Keyword.get(
        opts,
        :fixtures,
        Path.expand("test/fixtures/document_ops", File.cwd!())
      )

    out_dir = Keyword.get(opts, :out)
    {verifier, verifier_opts} = verifier_config(opts)

    case Vanta.Experiment002.run(fixture_root,
           out_dir: out_dir,
           verifier: verifier,
           verifier_opts: verifier_opts
         ) do
      {:ok, run} ->
        Mix.shell().info("Experiment 002 #{run["status"]} for #{run["fixture_count"]} fixtures.")

      {:error, {:llm_verifier_not_configured, reason}} ->
        Mix.raise("LLM verifier is not configured: #{inspect(reason)}")

      {:error, reason} ->
        Mix.raise("Experiment 002 failed: #{inspect(reason)}")
    end
  end

  defp verifier_config(opts) do
    verifier_name =
      opts
      |> Keyword.get(:verifier)
      |> Kernel.||(System.get_env("VANTA_EXPERIMENT002_VERIFIER"))
      |> Kernel.||("openclaw")

    case verifier_name do
      "openclaw" ->
        {Vanta.OpenClawVerifierAdapter,
         compact_opts(
           model: Keyword.get(opts, :model),
           openclaw_dir: Keyword.get(opts, :openclaw_dir),
           agent: Keyword.get(opts, :openclaw_agent),
           timeout_seconds: Keyword.get(opts, :openclaw_timeout_seconds),
           thinking: Keyword.get(opts, :openclaw_thinking)
         )}

      other ->
        Mix.raise("unsupported --verifier #{inspect(other)}; expected openclaw")
    end
  end

  defp compact_opts(opts) do
    Enum.reject(opts, fn {_key, value} -> is_nil(value) end)
  end
end
