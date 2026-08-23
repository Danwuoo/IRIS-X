defmodule Vanta.PostStage1LaneBPacket.ReportWriter do
  @moduledoc false

  import Vanta.PostStage1LaneBPacket.PathHelpers,
    only: [path_join: 2, write_json!: 2, write_jsonl!: 2, write_text!: 2]

  def write_packet!(packet) do
    config = packet.opts
    File.mkdir_p!(config.out_abs)
    File.mkdir_p!(Path.join(config.out_abs, "redacted_task_packets"))

    write_text!(Path.join(config.out_abs, "README.md"), packet.readme)
    write_json!(Path.join(config.out_abs, "packet_manifest.json"), packet.packet_manifest)

    Enum.each(packet.redacted_task_packets, fn {task_id, task_packet} ->
      write_json!(
        Path.join([config.out_abs, "redacted_task_packets", "#{task_id}.json"]),
        task_packet
      )
    end)

    write_jsonl!(
      Path.join(config.out_abs, "evidence_sufficiency_items.jsonl"),
      packet.evidence_sufficiency_items
    )

    write_jsonl!(
      Path.join(config.out_abs, "working_set_context_items.jsonl"),
      packet.working_set_context_items
    )

    write_json!(
      Path.join(config.out_abs, "adjudication_placeholders.json"),
      packet.adjudication_placeholders
    )

    write_json!(
      Path.join(config.out_abs, "label_results_template.json"),
      packet.label_results_template
    )

    File.mkdir_p!(Path.dirname(config.label_report_abs))
    write_text!(config.label_report_abs, packet.label_report_skeleton)

    %{
      packet_id: packet.packet_manifest["packet_id"],
      packet_dir: config.out_path,
      label_report: config.label_report_path,
      label_report_skeleton: config.label_report_path,
      label_results_template: path_join(config.out_path, "label_results_template.json"),
      evidence_item_count: length(packet.evidence_sufficiency_items),
      working_set_item_count: length(packet.working_set_context_items)
    }
  end
end
