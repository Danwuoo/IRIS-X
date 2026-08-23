defmodule Vanta.PostStage1LargerSample.Parser do
  @moduledoc false

  alias Vanta.Schema
  alias Vanta.PostStage1LargerSample.PathHelpers

  @strata [
    {"traceability_extraction", ~w(
       docops_read_traceability_001
       docops_struct_inspect_001
       docops_ps1_traceability_multisource_001
       docops_ps1_traceability_cross_doc_refs_001
       docops_ps1_traceability_missing_target_001
       docops_ps1_traceability_structured_outline_001
     )},
    {"terminology_consistency", ~w(
       docops_detect_terms_001
       docops_struct_contract_pass_001
       docops_struct_contract_fail_001
       docops_ps1_terms_alias_conflict_001
       docops_ps1_terms_clean_canonical_001
       docops_ps1_terms_contract_inline_001
     )},
    {"simulated_patch_and_diff", ~w(
       docops_simulate_patch_001
       docops_multistep_commit_001
       docops_struct_simulate_md_001
       docops_struct_simulate_json_001
       docops_struct_insert_before_001
       docops_struct_insert_after_001
     )},
    {"reversible_edit_and_commit", ~w(
       docops_reversible_edit_001
       docops_struct_apply_reversible_001
       docops_ps1_reversible_append_section_001
       docops_ps1_reversible_replace_heading_001
       docops_ps1_reversible_json_path_replace_001
       docops_ps1_reversible_patch_multiline_001
     )},
    {"invalid_action_and_path_guard", ~w(
       docops_action_not_allowed_001
       docops_path_escape_001
       docops_struct_path_escape_001
       docops_struct_selector_missing_001
       docops_struct_selector_ambiguous_001
       docops_ps1_invalid_reversible_in_readonly_001
     )},
    {"evidence_and_verifier_challenge", ~w(
       docops_wrong_diff_001
       docops_struct_wrong_diff_001
       docops_struct_simulation_mutation_001
       docops_struct_missing_backup_metadata_001
       docops_ps1_wrong_diff_multiline_001
       docops_ps1_struct_backup_files_dropped_001
     )},
    {"journal_replay_and_recovery", ~w(
       docops_rollback_failure_001
       docops_audit_gap_001
       docops_compensable_action_001
       docops_ps1_recovery_structured_rollback_001
       docops_ps1_recovery_audit_gap_complete_refs_001
       docops_ps1_replay_multistep_structured_commit_001
     )},
    {"working_set_long_context", ~w(
       docops_ws_evidence_packet_001
       docops_ws_irrelevant_context_001
       docops_ws_omission_trap_001
       docops_ws_recovery_context_001
       docops_ws_traceability_long_001
       docops_ps1_ws_structured_edit_context_001
     )}
  ]

  def build_inventory(fixture_root, frame, label_source_fun) do
    {items, errors} =
      Enum.reduce(frame, {[], []}, fn frame_item, {items, errors} ->
        fixture_id = frame_item["fixture_id"]
        workspace = Path.join(fixture_root, fixture_id)
        task_path = Path.join(workspace, "task.json")
        acceptance_path = Path.join(workspace, "expected/acceptance.json")

        cond do
          not File.exists?(task_path) ->
            {items, errors ++ ["#{fixture_id}: missing task.json"]}

          not File.exists?(acceptance_path) ->
            {items, errors ++ ["#{fixture_id}: missing expected/acceptance.json"]}

          true ->
            task = Schema.load_json!(task_path)
            acceptance = Schema.load_json!(acceptance_path)

            validation_errors =
              []
              |> validate_artifact("benchmark_task", task, "#{fixture_id}: task.json")
              |> validate_artifact(
                "fixture_acceptance",
                acceptance,
                "#{fixture_id}: expected/acceptance.json"
              )
              |> validate_action_sequence(acceptance, fixture_id)

            item =
              frame_item
              |> Map.merge(%{
                "action_types" =>
                  acceptance
                  |> get_in(["action_sequence", "actions"])
                  |> List.wrap()
                  |> Enum.map(& &1["action_type"])
                  |> Enum.uniq(),
                "side_effect_classes" => task["side_effect_classes"],
                "expected_runtime_status" => acceptance["expected_runtime_status"],
                "expected_label_source" => label_source_fun.(fixture_id, acceptance, workspace),
                "fixture_hash" => PathHelpers.fixture_hash(workspace),
                "workspace" => workspace
              })

            {items ++ [item], errors ++ validation_errors}
        end
      end)

    %{
      items: items,
      errors: errors ++ frame_errors(items)
    }
  end

  defp validate_artifact(errors, schema_name, artifact, label) do
    case Schema.validate(schema_name, artifact) do
      :ok -> errors
      {:error, schema_errors} -> errors ++ ["#{label}: #{inspect(schema_errors)}"]
    end
  end

  defp validate_action_sequence(errors, acceptance, fixture_id) do
    case Vanta.PlannerAdapter.validate_action_sequence(acceptance["action_sequence"]) do
      {:ok, _sequence} -> errors
      {:error, reason} -> errors ++ ["#{fixture_id}: invalid action_sequence #{inspect(reason)}"]
    end
  end

  defp frame_errors(items) do
    count_errors =
      if length(items) == 48 do
        []
      else
        ["sample frame has #{length(items)} fixtures, expected 48"]
      end

    strata_errors =
      @strata
      |> Enum.flat_map(fn {stratum, ids} ->
        actual = Enum.count(items, &(&1["stratum"] == stratum))

        cond do
          length(ids) != 6 -> ["#{stratum}: frame definition has #{length(ids)} ids"]
          actual != 6 -> ["#{stratum}: inventory has #{actual} fixtures, expected 6"]
          true -> []
        end
      end)

    count_errors ++ strata_errors
  end
end
