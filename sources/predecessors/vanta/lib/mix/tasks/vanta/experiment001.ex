defmodule Mix.Tasks.Vanta.Experiment001 do
  @moduledoc """
  Runs Experiment 001 against local Document Ops fixtures.
  """

  use Mix.Task

  @shortdoc "Run Vanta Experiment 001"

  @impl Mix.Task
  def run(args) do
    Mix.Task.run("app.start")

    {opts, _argv, _invalid} =
      OptionParser.parse(args,
        strict: [
          baseline: :string,
          out: :string,
          fixtures: :string,
          planner: :string,
          model: :string,
          openclaw_dir: :string,
          openclaw_agent: :string,
          openclaw_timeout_seconds: :integer,
          openclaw_thinking: :string
        ]
      )

    baseline = Keyword.get(opts, :baseline, "llm")

    if baseline != "llm" do
      Mix.raise("only --baseline llm is supported for Experiment 001")
    end

    fixture_root =
      Keyword.get(
        opts,
        :fixtures,
        Path.expand("test/fixtures/document_ops", File.cwd!())
      )

    out_dir = Keyword.get(opts, :out)
    {planner, planner_opts} = planner_config(opts)

    case Vanta.Experiment001.run(fixture_root,
           out_dir: out_dir,
           planner: planner,
           planner_opts: planner_opts
         ) do
      {:ok, run} ->
        Mix.shell().info("Experiment 001 completed for #{run["fixture_count"]} fixtures.")

      {:error, {:llm_baseline_not_configured, reason}} ->
        Mix.raise("LLM baseline is not configured: #{inspect(reason)}")

      {:error, reason} ->
        Mix.raise("Experiment 001 failed: #{inspect(reason)}")
    end
  end

  defp planner_config(opts) do
    planner_name =
      opts
      |> Keyword.get(:planner)
      |> Kernel.||(System.get_env("VANTA_EXPERIMENT001_PLANNER"))
      |> Kernel.||("openai")

    case planner_name do
      "openai" ->
        {Vanta.OpenAIPlannerAdapter, compact_opts(model: Keyword.get(opts, :model))}

      "openclaw" ->
        {Vanta.OpenClawPlannerAdapter,
         compact_opts(
           model: Keyword.get(opts, :model),
           openclaw_dir: Keyword.get(opts, :openclaw_dir),
           agent: Keyword.get(opts, :openclaw_agent),
           timeout_seconds: Keyword.get(opts, :openclaw_timeout_seconds),
           thinking: Keyword.get(opts, :openclaw_thinking)
         )}

      other ->
        Mix.raise("unsupported --planner #{inspect(other)}; expected openai or openclaw")
    end
  end

  defp compact_opts(opts) do
    Enum.reject(opts, fn {_key, value} -> is_nil(value) end)
  end
end
