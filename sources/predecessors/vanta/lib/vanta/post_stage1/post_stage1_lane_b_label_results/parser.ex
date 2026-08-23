defmodule Vanta.PostStage1LaneBLabelResults.Parser do
  @moduledoc false

  alias Vanta.PostStage1LaneBLabelResults.Validator

  import Vanta.PostStage1LaneBLabelResults.PathHelpers,
    only: [display_path: 2, load_json: 1, load_jsonl: 1]

  @default_run_timestamp "20260601_113121"

  def load_packet(opts) do
    config = normalize_opts(opts)

    paths = %{
      manifest: Path.join(config.packet_dir_abs, "packet_manifest.json"),
      evidence: Path.join(config.packet_dir_abs, "evidence_sufficiency_items.jsonl"),
      working_set: Path.join(config.packet_dir_abs, "working_set_context_items.jsonl"),
      adjudication: Path.join(config.packet_dir_abs, "adjudication_placeholders.json")
    }

    with {:ok, manifest} <- load_json(paths.manifest),
         {:ok, evidence_items} <- load_jsonl(paths.evidence),
         {:ok, working_set_items} <- load_jsonl(paths.working_set),
         {:ok, adjudication_placeholders} <- load_json(paths.adjudication),
         :ok <-
           Validator.validate_packet_inputs(
             manifest,
             evidence_items,
             working_set_items,
             adjudication_placeholders
           ) do
      {:ok,
       %{
         cwd: config.cwd,
         packet_dir: config.packet_dir,
         packet_manifest: manifest,
         evidence_sufficiency_items: evidence_items,
         working_set_context_items: working_set_items,
         adjudication_placeholders: adjudication_placeholders,
         evidence_ids: MapSet.new(Enum.map(evidence_items, & &1["packet_id"])),
         working_set_ids: MapSet.new(Enum.map(working_set_items, & &1["packet_id"])),
         item_refs: Validator.item_reference_index(evidence_items, working_set_items),
         candidate_refs: Validator.candidate_ref_index(working_set_items)
       }}
    end
  end

  defp normalize_opts(opts) do
    cwd = Keyword.get(opts, :cwd, File.cwd!())
    run_timestamp = Keyword.get(opts, :run_timestamp, @default_run_timestamp)
    packet_dir = Keyword.get(opts, :packet_dir, default_packet_dir(run_timestamp))

    %{
      cwd: cwd,
      packet_dir: display_path(packet_dir, cwd),
      packet_dir_abs: Path.expand(packet_dir, cwd)
    }
  end

  defp default_packet_dir(run_timestamp) do
    "docs/05_evaluation/label_packets/post_stage_1_lane_b_#{run_timestamp}"
  end

  def default_label_report_path(run_timestamp) do
    "docs/05_evaluation/Post_Stage_1_Lane_B_#{run_timestamp}_Label_Report_Skeleton.md"
  end
end
