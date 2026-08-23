defmodule Vanta.PostStage1LargerSample.ReportWriter do
  @moduledoc false

  alias Vanta.PostStage1LargerSample.Renderer

  def write_results!(out_dir, run, inventory) do
    File.mkdir_p!(out_dir)
    File.write!(Path.join(out_dir, "run.json"), Jason.encode!(run, pretty: true))
    File.write!(Path.join(out_dir, "summary.md"), Renderer.summary(run))

    File.write!(
      Path.join(out_dir, "fixture_inventory.md"),
      Renderer.fixture_inventory_markdown(inventory)
    )
  end
end
