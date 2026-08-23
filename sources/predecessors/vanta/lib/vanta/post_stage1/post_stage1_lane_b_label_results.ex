defmodule Vanta.PostStage1LaneBLabelResults do
  @moduledoc """
  Validates packet-local Post-Stage-1 Lane B label result imports.

  This module is an evaluation tooling layer for `PS1-LB-LABEL-001`. It does
  not define runtime behavior, verifier output, approval flow, or a core schema
  contract.
  """

  alias Vanta.PostStage1LaneBLabelResults.{Parser, PathHelpers, Renderer, ReportWriter, Validator}

  @default_run_timestamp "20260601_113121"
  @result_format "PS1-LB-LABEL-RESULT-LOCAL-001"

  def result_format, do: @result_format

  def ps1_g7_context_metric_surface_paths(_run_timestamp \\ @default_run_timestamp) do
    [
      "docs/00_manifest/Project_Manifest.md",
      "docs/00_manifest/Traceability_Matrix.md",
      "docs/02_specs/Post_Stage_1_Context_OS_Planning_Draft_Spec.md",
      "docs/03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md",
      "docs/04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md"
    ]
  end

  def template(opts \\ []) do
    with {:ok, packet} <- Parser.load_packet(opts) do
      {:ok, Renderer.template_for_packet(packet)}
    end
  end

  def template_for_packet(packet), do: Renderer.template_for_packet(packet)

  def write_template(path, opts \\ []), do: ReportWriter.write_template(path, opts)

  def validate_file(path, opts \\ []) do
    cwd = Keyword.get(opts, :cwd, File.cwd!())
    path_abs = Path.expand(path, cwd)

    with {:ok, packet} <- Parser.load_packet(opts),
         {:ok, results} <- PathHelpers.load_json(path_abs) do
      Validator.validate_results(results, packet, PathHelpers.display_path(path_abs, cwd))
    end
  end

  def write_import_summary(results_path, out_path, opts \\ []),
    do: ReportWriter.write_import_summary(results_path, out_path, opts)

  def validate_report_parity(report_path, results_path, import_summary_path, opts \\ []) do
    cwd = Keyword.get(opts, :cwd, File.cwd!())
    report_abs = Path.expand(report_path, cwd)
    results_abs = Path.expand(results_path, cwd)
    import_summary_abs = Path.expand(import_summary_path, cwd)
    result_path = PathHelpers.display_path(results_abs, cwd)

    with {:ok, packet} <- Parser.load_packet(opts),
         {:ok, results} <- PathHelpers.load_json(results_abs),
         {:ok, generated_summary} <- Validator.validate_results(results, packet, result_path),
         {:ok, saved_summary} <- PathHelpers.load_json(import_summary_abs),
         {:ok, report_text} <- PathHelpers.load_text(report_abs) do
      metric_scores = Validator.reported_metric_scores(results, packet)

      errors =
        []
        |> Validator.validate_import_summary_parity(generated_summary, saved_summary)
        |> Validator.validate_report_text_parity(report_text, generated_summary, metric_scores)

      if errors == [] do
        {:ok,
         %{
           "status" => "ok",
           "packet_id" => packet.packet_manifest["packet_id"],
           "report_path" => PathHelpers.display_path(report_abs, cwd),
           "result_path" => result_path,
           "import_summary_path" => PathHelpers.display_path(import_summary_abs, cwd),
           "raw_label_counts" => generated_summary["raw_label_counts"],
           "review_coverage" => generated_summary["review_coverage"],
           "reported_metric_scores" => metric_scores,
           "claim_boundary" =>
             "Report parity check only. It locks packet-local reported Lane B numbers against JSON artifacts and does not create runtime approval, full Context OS validation, or an H1-H5 validation claim."
         }}
      else
        {:error, Enum.reverse(errors)}
      end
    end
  end

  def validate_ps1_g7_context_metric_parity(results_path, import_summary_path, opts \\ []) do
    cwd = Keyword.get(opts, :cwd, File.cwd!())
    run_timestamp = Keyword.get(opts, :run_timestamp, @default_run_timestamp)
    report_path = Keyword.get(opts, :report, Parser.default_label_report_path(run_timestamp))
    surface_paths = Keyword.get(opts, :surface_paths, ps1_g7_context_metric_surface_paths())

    report_abs = Path.expand(report_path, cwd)
    results_abs = Path.expand(results_path, cwd)
    import_summary_abs = Path.expand(import_summary_path, cwd)
    result_path = PathHelpers.display_path(results_abs, cwd)

    with {:ok, packet} <- Parser.load_packet(opts),
         {:ok, results} <- PathHelpers.load_json(results_abs),
         {:ok, generated_summary} <- Validator.validate_results(results, packet, result_path),
         {:ok, saved_summary} <- PathHelpers.load_json(import_summary_abs),
         {:ok, report_text} <- PathHelpers.load_text(report_abs),
         {:ok, surfaces} <- PathHelpers.load_surface_texts(surface_paths, cwd) do
      metric_scores = Validator.reported_metric_scores(results, packet)

      errors =
        []
        |> Validator.validate_import_summary_parity(generated_summary, saved_summary)
        |> Validator.validate_locked_context_metric_values(metric_scores)
        |> Validator.validate_report_text_parity(report_text, generated_summary, metric_scores)
        |> Validator.validate_context_metric_surfaces(surfaces)

      if errors == [] do
        {:ok,
         %{
           "status" => "ok",
           "packet_id" => packet.packet_manifest["packet_id"],
           "result_path" => result_path,
           "import_summary_path" => PathHelpers.display_path(import_summary_abs, cwd),
           "report_path" => PathHelpers.display_path(report_abs, cwd),
           "surface_paths" => Enum.map(surfaces, fn {path, _text} -> path end),
           "reported_metric_scores" => metric_scores,
           "locked_context_metrics" => Validator.locked_context_metric_summary(metric_scores),
           "claim_boundary" =>
             "PS1-G7 context metric parity check only. It locks packet-local Lane B omission and relevance numbers against JSON artifacts, the label report, and planning/traceability documentation; it does not create runtime approval, schema change, full Context OS validation, or an H1-H5 validation claim."
         }}
      else
        {:error, Enum.reverse(errors)}
      end
    end
  end
end
