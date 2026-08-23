defmodule Vanta.PostStage1LaneBLabelResults.Renderer do
  @moduledoc false

  import Vanta.PostStage1LaneBLabelResults.PathHelpers, only: [path_join: 2]

  @result_format "PS1-LB-LABEL-RESULT-LOCAL-001"
  @label_policy_version "PS1-LB-LABEL-001"
  @not_yet_run "Not yet run"
  @review_mode "double_human_adjudicated"
  @evidence_metric "evidence_sufficiency_score"
  @working_context_metric "working_set_context"

  def template_for_packet(packet) do
    %{
      "result_format" => @result_format,
      "label_policy_version" => @label_policy_version,
      "packet_id" => packet.packet_manifest["packet_id"],
      "packet_manifest_path" =>
        get_in(packet.packet_manifest, ["artifact_paths", "packet_manifest"]) ||
          path_join(packet.packet_dir, "packet_manifest.json"),
      "label_collection_status" => @not_yet_run,
      "review_mode" => @review_mode,
      "primary_label_freeze" => %{
        "status" => @not_yet_run,
        "frozen_at" => @not_yet_run,
        "fixture_oracle_exposed_before_freeze" => false,
        "oracle_exposure_notes" => @not_yet_run
      },
      "raw_labels" => %{
        @evidence_metric => [],
        @working_context_metric => []
      },
      "secondary_reviews" => [],
      "adjudication_records" => [],
      "agreement_report" => %{
        "status" => @not_yet_run,
        "method" => @not_yet_run,
        "raw_agreement_counts" => @not_yet_run,
        "notes" => @not_yet_run
      },
      "reporting_boundary" => %{
        "claim_level" => "template only; no labels imported",
        "disallowed_claims" => [
          "human-labeled broader evaluation evidence",
          "secondary review completed",
          "adjudication completed",
          "inter-annotator agreement reported",
          "H1-H5 validation",
          "full Context OS validation",
          "production readiness",
          "runtime approval or human-in-the-loop verifier claim"
        ]
      }
    }
  end
end
