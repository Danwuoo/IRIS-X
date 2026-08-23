defmodule Mix.Tasks.Vanta.PostStage1LaneBPacket do
  @moduledoc """
  Generates or checks the Post-Stage-1 Lane B blinded label packet.
  """

  use Mix.Task

  @shortdoc "Generate or check the Post-Stage-1 Lane B packet"

  @impl Mix.Task
  def run(args) do
    Mix.Task.run("app.start")

    {opts, _argv, invalid} =
      OptionParser.parse(args,
        strict: [
          run_json: :string,
          run_timestamp: :string,
          run_report: :string,
          closure: :string,
          fixtures: :string,
          out: :string,
          label_results: :string,
          import_summary: :string,
          coordinator_packet_freeze: :string,
          mode: :string
        ]
      )

    if invalid != [] do
      Mix.raise("Invalid options: #{inspect(invalid)}")
    end

    mode = Keyword.get(opts, :mode, "check")
    packet_opts = compact_opts(opts)

    case mode do
      "generate" ->
        case Vanta.PostStage1LaneBPacket.generate(packet_opts) do
          {:ok, result} ->
            Mix.shell().info("Lane B packet generated: #{result.packet_id}")
            Mix.shell().info("Packet: #{result.packet_dir}")
            Mix.shell().info("Label report: #{result.label_report}")
            Mix.shell().info("Label result template: #{result.label_results_template}")
            Mix.shell().info("Evidence items: #{result.evidence_item_count}")
            Mix.shell().info("Working-set items: #{result.working_set_item_count}")

          {:error, errors} ->
            Mix.raise("Lane B packet generation failed:\n#{format_errors(errors)}")
        end

      "check" ->
        case Vanta.PostStage1LaneBPacket.check(packet_opts) do
          {:ok, result} ->
            Mix.shell().info("Lane B packet check passed: #{result.packet_id}")
            Mix.shell().info("Packet: #{result.packet_dir}")
            Mix.shell().info("Evidence items: #{result.evidence_item_count}")
            Mix.shell().info("Working-set items: #{result.working_set_item_count}")

          {:error, errors} ->
            Mix.raise("Lane B packet check failed:\n#{format_errors(errors)}")
        end

      other ->
        Mix.raise("Unsupported --mode #{inspect(other)}; expected generate or check")
    end
  end

  defp compact_opts(opts) do
    Enum.reject(opts, fn
      {:mode, _value} -> true
      {_key, nil} -> true
      _item -> false
    end)
  end

  defp format_errors(errors) do
    errors
    |> List.wrap()
    |> Enum.map_join("\n", &"- #{&1}")
  end
end
