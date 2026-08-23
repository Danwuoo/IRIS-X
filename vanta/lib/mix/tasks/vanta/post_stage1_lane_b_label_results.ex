defmodule Mix.Tasks.Vanta.PostStage1LaneBLabelResults do
  @moduledoc """
  Generates or validates Post-Stage-1 Lane B label result imports.
  """

  use Mix.Task

  @shortdoc "Generate or validate Post-Stage-1 Lane B label results"

  @impl Mix.Task
  def run(args) do
    Mix.Task.run("app.start")

    {opts, _argv, invalid} =
      OptionParser.parse(args,
        strict: [
          mode: :string,
          run_timestamp: :string,
          packet_dir: :string,
          results: :string,
          report: :string,
          import_summary: :string,
          out: :string
        ]
      )

    if invalid != [] do
      Mix.raise("Invalid options: #{inspect(invalid)}")
    end

    mode = Keyword.get(opts, :mode, "validate")
    packet_opts = compact_opts(opts)

    case mode do
      "template" ->
        out = Keyword.get(opts, :out, default_template_path(opts))

        case Vanta.PostStage1LaneBLabelResults.write_template(out, packet_opts) do
          {:ok, result} ->
            Mix.shell().info(
              "Lane B label result template written: #{result["path"] || result.path}"
            )

            Mix.shell().info("Packet: #{result.packet_id}")
            Mix.shell().info("Result format: #{result.result_format}")
            Mix.shell().info("Label collection status: #{result.label_collection_status}")

          {:error, errors} ->
            Mix.raise("Lane B label result template generation failed:\n#{format_errors(errors)}")
        end

      "validate" ->
        results_path = required_results!(opts, mode)

        case Vanta.PostStage1LaneBLabelResults.validate_file(results_path, packet_opts) do
          {:ok, summary} ->
            print_summary("Lane B label result validation passed", summary)

          {:error, errors} ->
            Mix.raise("Lane B label result validation failed:\n#{format_errors(errors)}")
        end

      "import-summary" ->
        results_path = required_results!(opts, mode)

        case Keyword.get(opts, :out) do
          nil ->
            case Vanta.PostStage1LaneBLabelResults.validate_file(results_path, packet_opts) do
              {:ok, summary} ->
                print_summary("Lane B label result import summary", summary)

              {:error, errors} ->
                Mix.raise("Lane B label result import summary failed:\n#{format_errors(errors)}")
            end

          out ->
            case Vanta.PostStage1LaneBLabelResults.write_import_summary(
                   results_path,
                   out,
                   packet_opts
                 ) do
              {:ok, summary} ->
                print_summary("Lane B label result import summary written", summary)
                Mix.shell().info("Summary: #{summary["summary_path"]}")

              {:error, errors} ->
                Mix.raise("Lane B label result import summary failed:\n#{format_errors(errors)}")
            end
        end

      "report-parity" ->
        results_path = required_results!(opts, mode)
        report_path = Keyword.get(opts, :report, default_report_path(opts))

        import_summary_path =
          Keyword.get(opts, :import_summary, default_import_summary_path(opts))

        case Vanta.PostStage1LaneBLabelResults.validate_report_parity(
               report_path,
               results_path,
               import_summary_path,
               packet_opts
             ) do
          {:ok, summary} ->
            print_report_parity_summary(summary)

          {:error, errors} ->
            Mix.raise("Lane B label report parity failed:\n#{format_errors(errors)}")
        end

      "ps1-g7-parity" ->
        results_path = required_results!(opts, mode)
        report_path = Keyword.get(opts, :report, default_report_path(opts))

        import_summary_path =
          Keyword.get(opts, :import_summary, default_import_summary_path(opts))

        case Vanta.PostStage1LaneBLabelResults.validate_ps1_g7_context_metric_parity(
               results_path,
               import_summary_path,
               Keyword.put(packet_opts, :report, report_path)
             ) do
          {:ok, summary} ->
            print_ps1_g7_parity_summary(summary)

          {:error, errors} ->
            Mix.raise("PS1-G7 context metric parity failed:\n#{format_errors(errors)}")
        end

      other ->
        Mix.raise(
          "Unsupported --mode #{inspect(other)}; expected template, validate, import-summary, report-parity, or ps1-g7-parity"
        )
    end
  end

  defp compact_opts(opts) do
    opts
    |> Keyword.drop([:mode, :results, :report, :import_summary, :out])
    |> Enum.reject(fn {_key, value} -> is_nil(value) end)
  end

  defp required_results!(opts, mode) do
    case Keyword.get(opts, :results) do
      nil -> Mix.raise("--results is required for --mode #{mode}")
      value -> value
    end
  end

  defp default_template_path(opts) do
    default_packet_dir(opts)
    |> Path.join("label_results_template.json")
  end

  defp default_import_summary_path(opts) do
    default_packet_dir(opts)
    |> Path.join("label_results_import_summary.json")
  end

  defp default_report_path(opts) do
    run_timestamp =
      Keyword.get(opts, :run_timestamp, Vanta.PostStage1LaneBPacket.default_run_timestamp())

    "docs/05_evaluation/Post_Stage_1_Lane_B_#{run_timestamp}_Label_Report_Skeleton.md"
  end

  defp default_packet_dir(opts) do
    run_timestamp =
      Keyword.get(opts, :run_timestamp, Vanta.PostStage1LaneBPacket.default_run_timestamp())

    Keyword.get(
      opts,
      :packet_dir,
      "docs/05_evaluation/label_packets/post_stage_1_lane_b_#{run_timestamp}"
    )
  end

  defp print_summary(title, summary) do
    Mix.shell().info("#{title}: #{summary["packet_id"]}")
    Mix.shell().info("Results: #{summary["result_path"]}")
    Mix.shell().info("Label collection status: #{summary["label_collection_status"]}")

    Mix.shell().info(
      "Raw evidence labels: #{summary["raw_label_counts"]["evidence_sufficiency_score"]}"
    )

    Mix.shell().info(
      "Raw working-set labels: #{summary["raw_label_counts"]["working_set_context"]}"
    )

    Mix.shell().info("Needs review count: #{summary["needs_review_count"]}")
    Mix.shell().info("Adjudication required: #{summary["adjudication_required_count"]}")

    Mix.shell().info(
      "Unhandled adjudication required: #{summary["unhandled_adjudication_required_count"]}"
    )
  end

  defp print_report_parity_summary(summary) do
    metric_scores = summary["reported_metric_scores"]
    omission = metric_scores["context_omission_error_rate"]
    relevance = metric_scores["working_set_relevance_score"]

    Mix.shell().info("Lane B label report parity passed: #{summary["packet_id"]}")
    Mix.shell().info("Report: #{summary["report_path"]}")
    Mix.shell().info("Results: #{summary["result_path"]}")
    Mix.shell().info("Import summary: #{summary["import_summary_path"]}")

    Mix.shell().info(
      "Context omission: #{omission["score_4dp"]} (#{omission["omitted_task_critical_ref_count"]} / #{omission["task_critical_candidate_ref_count"]})"
    )

    Mix.shell().info(
      "Working-set relevance: #{relevance["score_4dp"]} (#{relevance["relevant_included_ref_count"]} / #{relevance["included_ref_denominator"]})"
    )
  end

  defp print_ps1_g7_parity_summary(summary) do
    print_report_parity_summary(summary)
    Mix.shell().info("PS1-G7 surface count: #{length(summary["surface_paths"])}")
    Mix.shell().info("Claim boundary: #{summary["claim_boundary"]}")
  end

  defp format_errors(errors) do
    errors
    |> List.wrap()
    |> Enum.map_join("\n", &"- #{&1}")
  end
end
