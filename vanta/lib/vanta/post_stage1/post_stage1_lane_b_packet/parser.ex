defmodule Vanta.PostStage1LaneBPacket.Parser do
  @moduledoc false

  import Vanta.PostStage1LaneBPacket.PathHelpers,
    only: [display_path: 2, load_json: 1, load_jsonl: 1, load_optional_json: 1, load_text: 1]

  def load_existing_packet(config, task_ids) do
    paths = %{
      readme: Path.join(config.out_abs, "README.md"),
      packet_manifest: Path.join(config.out_abs, "packet_manifest.json"),
      evidence_sufficiency_items: Path.join(config.out_abs, "evidence_sufficiency_items.jsonl"),
      working_set_context_items: Path.join(config.out_abs, "working_set_context_items.jsonl"),
      adjudication_placeholders: Path.join(config.out_abs, "adjudication_placeholders.json"),
      label_results_template: Path.join(config.out_abs, "label_results_template.json"),
      label_results_primary_filled:
        Path.join(config.out_abs, "label_results_primary_filled.json"),
      label_report_skeleton: config.label_report_abs
    }

    missing =
      paths
      |> Enum.reduce([], fn {_key, path}, errors ->
        if File.exists?(path),
          do: errors,
          else: ["missing packet artifact: #{display_path(path, config.cwd)}" | errors]
      end)

    missing_redacted =
      task_ids
      |> Enum.reduce([], fn task_id, errors ->
        path = Path.join([config.out_abs, "redacted_task_packets", "#{task_id}.json"])

        if File.exists?(path),
          do: errors,
          else: ["missing redacted task packet: #{display_path(path, config.cwd)}" | errors]
      end)

    if missing ++ missing_redacted != [] do
      {:error, Enum.reverse(missing ++ missing_redacted)}
    else
      with {:ok, readme} <- load_text(paths.readme),
           {:ok, manifest} <- load_json(paths.packet_manifest),
           {:ok, evidence} <- load_jsonl(paths.evidence_sufficiency_items),
           {:ok, working_set} <- load_jsonl(paths.working_set_context_items),
           {:ok, adjudication} <- load_json(paths.adjudication_placeholders),
           {:ok, label_results_template} <- load_json(paths.label_results_template),
           {:ok, label_results_primary_filled} <-
             load_optional_json(paths.label_results_primary_filled),
           {:ok, report} <- load_text(paths.label_report_skeleton),
           {:ok, redacted} <- load_redacted_packets(config, task_ids) do
        {:ok,
         %{
           readme: readme,
           packet_manifest: manifest,
           evidence_sufficiency_items: evidence,
           working_set_context_items: working_set,
           adjudication_placeholders: adjudication,
           label_results_template: label_results_template,
           label_results_primary_filled: label_results_primary_filled,
           label_report_skeleton: report,
           redacted_task_packets: redacted
         }}
      end
    end
  end

  defp load_redacted_packets(config, task_ids) do
    task_ids
    |> Enum.reduce_while({:ok, %{}}, fn task_id, {:ok, packets} ->
      path = Path.join([config.out_abs, "redacted_task_packets", "#{task_id}.json"])

      case load_json(path) do
        {:ok, task_packet} -> {:cont, {:ok, Map.put(packets, task_id, task_packet)}}
        {:error, errors} -> {:halt, {:error, errors}}
      end
    end)
  end
end
