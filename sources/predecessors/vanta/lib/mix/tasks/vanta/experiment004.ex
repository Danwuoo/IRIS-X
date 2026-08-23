defmodule Mix.Tasks.Vanta.Experiment004 do
  @moduledoc """
  Runs Experiment 004 against Phase 4 Document Ops recovery fixtures.
  """

  use Mix.Task

  @shortdoc "Run Vanta Experiment 004"

  @impl Mix.Task
  def run(args) do
    Mix.Task.run("app.start")

    {opts, _argv, _invalid} =
      OptionParser.parse(args,
        strict: [
          recovery: :string,
          out: :string,
          fixtures: :string,
          model: :string,
          openclaw_dir: :string,
          openclaw_agent: :string,
          openclaw_timeout_seconds: :integer,
          openclaw_thinking: :string,
          max_prompt_chars: :integer,
          max_response_chars: :integer,
          max_action_attempts: :integer
        ]
      )

    fixture_root =
      Keyword.get(
        opts,
        :fixtures,
        Path.expand("test/fixtures/document_ops", File.cwd!())
      )

    out_dir = Keyword.get(opts, :out)
    {recovery_adapter, recovery_opts} = recovery_config(opts)

    case Vanta.Experiment004.run(fixture_root,
           out_dir: out_dir,
           recovery_adapter: recovery_adapter,
           recovery_opts: recovery_opts
         ) do
      {:ok, run} ->
        Mix.shell().info("Experiment 004 #{run["status"]} for #{run["fixture_count"]} fixtures.")

      {:error, {:llm_recovery_not_configured, reason}} ->
        Mix.raise("LLM recovery adapter is not configured: #{inspect(reason)}")

      {:error, reason} ->
        Mix.raise("Experiment 004 failed: #{inspect(reason)}")
    end
  end

  defp recovery_config(opts) do
    recovery_name =
      opts
      |> Keyword.get(:recovery)
      |> Kernel.||(System.get_env("VANTA_EXPERIMENT004_RECOVERY"))
      |> Kernel.||("openclaw")

    case recovery_name do
      "openclaw" ->
        {Vanta.OpenClawRecoveryAdapter,
         compact_opts(
           model: Keyword.get(opts, :model),
           openclaw_dir: Keyword.get(opts, :openclaw_dir),
           agent: Keyword.get(opts, :openclaw_agent),
           timeout_seconds: Keyword.get(opts, :openclaw_timeout_seconds),
           thinking: Keyword.get(opts, :openclaw_thinking),
           max_prompt_chars: Keyword.get(opts, :max_prompt_chars),
           max_response_chars: Keyword.get(opts, :max_response_chars),
           max_action_attempts: Keyword.get(opts, :max_action_attempts)
         )}

      other ->
        Mix.raise("unsupported --recovery #{inspect(other)}; expected openclaw")
    end
  end

  defp compact_opts(opts) do
    Enum.reject(opts, fn {_key, value} -> is_nil(value) end)
  end
end
