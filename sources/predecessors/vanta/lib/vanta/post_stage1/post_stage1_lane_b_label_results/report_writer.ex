defmodule Vanta.PostStage1LaneBLabelResults.ReportWriter do
  @moduledoc false

  alias Vanta.PostStage1LaneBLabelResults.{Parser, PathHelpers, Renderer}

  def write_template(path, opts \\ []) do
    cwd = Keyword.get(opts, :cwd, File.cwd!())
    path_abs = Path.expand(path, cwd)

    with {:ok, packet} <- Parser.load_packet(opts) do
      template = Renderer.template_for_packet(packet)
      File.mkdir_p!(Path.dirname(path_abs))
      PathHelpers.write_json!(path_abs, template)

      {:ok,
       %{
         path: PathHelpers.display_path(path_abs, cwd),
         packet_id: template["packet_id"],
         result_format: Vanta.PostStage1LaneBLabelResults.result_format(),
         label_collection_status: "Not yet run"
       }}
    end
  end

  def write_import_summary(results_path, out_path, opts \\ []) do
    cwd = Keyword.get(opts, :cwd, File.cwd!())
    out_abs = Path.expand(out_path, cwd)

    with {:ok, summary} <- Vanta.PostStage1LaneBLabelResults.validate_file(results_path, opts) do
      File.mkdir_p!(Path.dirname(out_abs))
      PathHelpers.write_json!(out_abs, summary)
      {:ok, Map.put(summary, "summary_path", PathHelpers.display_path(out_abs, cwd))}
    end
  end
end
