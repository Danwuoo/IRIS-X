defmodule Mix.Tasks.Vanta.PostStage1LargerSample do
  @moduledoc """
  Runs the Post-Stage-1 Lane A 48-fixture larger controlled sample.
  """

  use Mix.Task

  @shortdoc "Run Vanta Post-Stage-1 Lane A larger sample"

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
          max_action_attempts: :integer,
          max_recovery_attempts: :integer,
          max_context_chars: :integer
        ]
      )

    fixture_root =
      Keyword.get(
        opts,
        :fixtures,
        Path.expand("test/fixtures/document_ops", File.cwd!())
      )

    out_dir =
      Keyword.get_lazy(opts, :out, fn ->
        Path.expand(
          "docs/04_experiments/results/post_stage_1_larger_sample/#{timestamp()}",
          File.cwd!()
        )
      end)

    runner_opts =
      compact_opts(
        out_dir: out_dir,
        model: Keyword.get(opts, :model),
        openclaw_dir: Keyword.get(opts, :openclaw_dir),
        openclaw_agent: Keyword.get(opts, :openclaw_agent),
        openclaw_timeout_seconds: Keyword.get(opts, :openclaw_timeout_seconds),
        openclaw_thinking: Keyword.get(opts, :openclaw_thinking),
        max_prompt_chars: Keyword.get(opts, :max_prompt_chars),
        max_response_chars: Keyword.get(opts, :max_response_chars),
        max_action_attempts: Keyword.get(opts, :max_action_attempts),
        max_recovery_attempts: Keyword.get(opts, :max_recovery_attempts),
        max_context_chars: Keyword.get(opts, :max_context_chars)
      )

    case Vanta.PostStage1LargerSample.run(fixture_root, runner_opts) do
      {:ok, run} ->
        Mix.shell().info(
          "Post-Stage-1 Lane A #{run["threshold_status"]} for #{run["fixture_count"]} fixtures."
        )

        Mix.shell().info("Results: #{out_dir}")

      {:error, {:openclaw_adapter_not_configured, role, reason}} ->
        Mix.raise("OpenClaw #{role} adapter is not configured: #{inspect(reason)}")

      {:error, reason} ->
        Mix.raise("Post-Stage-1 Lane A run failed: #{inspect(reason)}")
    end
  end

  defp compact_opts(opts) do
    Enum.reject(opts, fn {_key, value} -> is_nil(value) end)
  end

  defp timestamp do
    {{year, month, day}, {hour, minute, second}} = :calendar.local_time()

    :io_lib.format(
      "~4..0B~2..0B~2..0B_~2..0B~2..0B~2..0B",
      [year, month, day, hour, minute, second]
    )
    |> IO.iodata_to_binary()
  end
end
