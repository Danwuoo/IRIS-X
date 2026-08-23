defmodule Vanta.PostStage1LaneBPacket.Validator do
  @moduledoc false

  @default_run_timestamp "20260601_113121"
  @not_yet_run "Not yet run"
  @complete_reported "complete_reported"
  @complete_reported_packet_status "active_packet_complete_reported"
  @reported_from_validated_primary_labels "reported_from_validated_primary_labels"

  @evidence_sample [
    {"docops_read_traceability_001", "traceability_extraction"},
    {"docops_struct_contract_fail_001", "terminology_consistency"},
    {"docops_simulate_patch_001", "simulated_patch_and_diff"},
    {"docops_struct_apply_reversible_001", "reversible_edit_and_commit"},
    {"docops_struct_selector_missing_001", "invalid_action_and_path_guard"},
    {"docops_wrong_diff_001", "evidence_and_verifier_challenge"},
    {"docops_rollback_failure_001", "journal_replay_and_recovery"},
    {"docops_ws_evidence_packet_001", "working_set_long_context"}
  ]

  @working_set_task_ids ~w(
    docops_ws_evidence_packet_001
    docops_ws_irrelevant_context_001
    docops_ws_omission_trap_001
    docops_ws_recovery_context_001
    docops_ws_traceability_long_001
    docops_ps1_ws_structured_edit_context_001
  )

  @redacted_task_oracle_fields ~w(
    required_refs
    relevant_refs
    irrelevant_refs
    omission_trap_refs
    expected_runtime_status
    expected_label_source
    expected_failure_labels
    expected_recovery_policy
    expected_failure_label
  )

  @forbidden_packet_keys @redacted_task_oracle_fields ++ ~w(role description required)

  @post_freeze_unblind_forbidden_patterns [
    {"raw-trace source arm label",
     ~r/raw_trace_bounded_openclaw_agent_local\/openai-codex\/[^\s"']+/},
    {"working-set source arm label",
     ~r/working_set_compiler_v0_reference_backed_openclaw_agent_local\/openai-codex\/[^\s"']+/},
    {"literal raw-trace wildcard marker", ~r/raw_trace_\*/},
    {"literal working-set wildcard marker", ~r/working_set_\*/},
    {"context arm mapping field", ~r/\bcontext_arm_mapping\b/},
    {"arm mapping field", ~r/\barm_mapping\b/},
    {"source arm label field", ~r/\bsource_arm_label\b/},
    {"true arm field", ~r/\btrue_arm(?:_role)?\b/},
    {"context artifact prefix field", ~r/\bcontext_artifact_prefix\b/},
    {"post-freeze coordinator memo marker", ~r/\bcoordinator_only_post_freeze\b/},
    {"context arm A true-role mapping",
     ~r/context_arm_A\s*(?:=>|->|=|:)\s*(?:baseline|raw_trace|context baseline)/i},
    {"context arm B true-role mapping",
     ~r/context_arm_B\s*(?:=>|->|=|:)\s*(?:treatment|working_set|working set compiler)/i},
    {"context baseline role phrase", ~r/\bcontext baseline\b/i},
    {"working-set treatment role phrase", ~r/\bworking set compiler v0 treatment\b/i},
    {"bounded raw-trace role phrase", ~r/\bbounded raw-trace context baseline\b/i}
  ]

  def validate_packet(expected, actual) do
    []
    |> require_equal("packet_manifest.json", actual.packet_manifest, expected.packet_manifest)
    |> require_equal(
      "evidence_sufficiency_items.jsonl",
      actual.evidence_sufficiency_items,
      expected.evidence_sufficiency_items
    )
    |> require_equal(
      "working_set_context_items.jsonl",
      actual.working_set_context_items,
      expected.working_set_context_items
    )
    |> require_equal(
      "adjudication_placeholders.json",
      actual.adjudication_placeholders,
      expected.adjudication_placeholders
    )
    |> require_equal(
      "label_results_template.json",
      actual.label_results_template,
      expected.label_results_template
    )
    |> require_equal(
      "redacted_task_packets",
      actual.redacted_task_packets,
      expected.redacted_task_packets
    )
    |> check_required_text("README.md", actual.readme, [
      expected.opts.run_json_path,
      expected.opts.run_report_path,
      expected.opts.closure_path
    ])
    |> check_required_text("label report skeleton", actual.label_report_skeleton, [
      expected.opts.run_json_path,
      expected.opts.run_report_path,
      expected.opts.closure_path
    ])
    |> check_packet_shape(actual)
    |> check_redaction(actual)
    |> check_post_freeze_unblind_boundary(actual)
    |> check_not_yet_run_labels(actual)
    |> check_reported_packet_state(actual)
    |> check_selector_repair_item(actual)
  end

  def post_freeze_unblind_boundary_errors(packet_artifacts) when is_map(packet_artifacts) do
    packet_artifacts
    |> post_freeze_unblind_scan_targets()
    |> Enum.flat_map(fn {artifact, value} ->
      value
      |> post_freeze_unblind_hits([])
      |> Enum.map(fn {path, label} ->
        "post-freeze unblind guard: #{artifact}#{format_scan_path(path)} contains #{label}"
      end)
    end)
    |> Enum.uniq()
    |> Enum.sort()
  end

  def check_packet_shape(errors, actual) do
    prefix = packet_prefix_from_manifest(actual.packet_manifest)

    errors
    |> require_count("evidence sufficiency item count", actual.evidence_sufficiency_items, 8)
    |> require_count("working-set context item count", actual.working_set_context_items, 12)
    |> require_values(
      "evidence sufficiency item IDs",
      Enum.map(actual.evidence_sufficiency_items, & &1["packet_id"]),
      expected_evidence_ids(prefix)
    )
    |> require_values(
      "evidence sufficiency task IDs",
      Enum.map(actual.evidence_sufficiency_items, & &1["task_id"]),
      Enum.map(@evidence_sample, fn {task_id, _stratum} -> task_id end)
    )
    |> require_values(
      "working-set item IDs",
      Enum.map(actual.working_set_context_items, & &1["packet_id"]),
      expected_working_set_ids(prefix)
    )
    |> require_values(
      "working-set task IDs",
      actual.working_set_context_items
      |> Enum.map(& &1["task_id"])
      |> Enum.chunk_every(2)
      |> Enum.map(&List.first/1),
      @working_set_task_ids
    )
  end

  def check_redaction(errors, actual) do
    redacted_errors =
      actual.redacted_task_packets
      |> Enum.flat_map(fn {task_id, task_packet} ->
        input_errors =
          Enum.flat_map(task_packet["input_artifacts"] || [], fn input_artifact ->
            ["role", "description"]
            |> Enum.filter(&Map.has_key?(input_artifact, &1))
            |> Enum.map(&"#{task_id} redacted input_artifacts still exposes #{&1}")
          end)

        task_errors =
          task_packet
          |> forbidden_keys(@redacted_task_oracle_fields)
          |> Enum.map(&"#{task_id} redacted task packet still exposes #{&1}")

        input_errors ++ task_errors
      end)

    context_errors =
      actual.working_set_context_items
      |> Enum.flat_map(fn item ->
        forbidden_keys(item, @forbidden_packet_keys)
        |> Enum.map(&"#{item["packet_id"]} working-set packet exposes forbidden key #{&1}")
      end)

    Enum.reduce(redacted_errors ++ context_errors, errors, &[&1 | &2])
  end

  def check_post_freeze_unblind_boundary(errors, actual) do
    actual
    |> post_freeze_unblind_boundary_errors()
    |> Enum.reduce(errors, &[&1 | &2])
  end

  defp post_freeze_unblind_scan_targets(artifacts) do
    [
      {"evidence_sufficiency_items.jsonl",
       artifact_value(artifacts, :evidence_sufficiency_items)},
      {"working_set_context_items.jsonl", artifact_value(artifacts, :working_set_context_items)},
      {"redacted_task_packets", artifact_value(artifacts, :redacted_task_packets)},
      {"label_results_template.json", artifact_value(artifacts, :label_results_template)},
      {"label_results_primary_filled.json",
       artifact_value(artifacts, :label_results_primary_filled)}
    ]
    |> Enum.reject(fn {_label, value} -> is_nil(value) end)
  end

  defp artifact_value(map, key) when is_map(map) do
    Map.get(map, key) || Map.get(map, Atom.to_string(key))
  end

  defp post_freeze_unblind_hits(value, path) when is_map(value) do
    Enum.flat_map(value, fn {key, nested_value} ->
      key_path = path ++ [key]

      post_freeze_unblind_string_hits(to_string(key), key_path) ++
        post_freeze_unblind_hits(nested_value, key_path)
    end)
  end

  defp post_freeze_unblind_hits(value, path) when is_list(value) do
    value
    |> Enum.with_index()
    |> Enum.flat_map(fn {item, index} -> post_freeze_unblind_hits(item, path ++ [index]) end)
  end

  defp post_freeze_unblind_hits(value, path) when is_binary(value) do
    post_freeze_unblind_string_hits(value, path)
  end

  defp post_freeze_unblind_hits(_value, _path), do: []

  defp post_freeze_unblind_string_hits(value, path) do
    @post_freeze_unblind_forbidden_patterns
    |> Enum.filter(fn {_label, pattern} -> Regex.match?(pattern, value) end)
    |> Enum.map(fn {label, _pattern} -> {path, label} end)
  end

  defp format_scan_path([]), do: ""

  defp format_scan_path(path) do
    Enum.map_join(path, "", fn
      index when is_integer(index) -> "[#{index}]"
      key -> ".#{key}"
    end)
  end

  def check_not_yet_run_labels(errors, actual) do
    label_errors =
      [
        actual.adjudication_placeholders["status"],
        actual.label_results_template["label_collection_status"],
        get_in(actual.label_results_template, ["primary_label_freeze", "status"]),
        get_in(actual.label_results_template, ["agreement_report", "status"])
      ]
      |> Enum.with_index()
      |> Enum.flat_map(fn {value, index} ->
        if value == @not_yet_run, do: [], else: ["label status #{index} is #{inspect(value)}"]
      end)

    item_errors =
      (actual.evidence_sufficiency_items ++ actual.working_set_context_items)
      |> Enum.flat_map(fn item ->
        fields = Map.values(item["primary_label_fields"] || %{})

        cond do
          item["label_status"] != @not_yet_run ->
            ["#{item["packet_id"]} label_status is #{inspect(item["label_status"])}"]

          item["adjudication_status"] != @not_yet_run ->
            [
              "#{item["packet_id"]} adjudication_status is #{inspect(item["adjudication_status"])}"
            ]

          Enum.any?(fields, &(&1 != @not_yet_run)) ->
            ["#{item["packet_id"]} has primary label fields not marked Not yet run"]

          true ->
            []
        end
      end)

    Enum.reduce(label_errors ++ item_errors, errors, &[&1 | &2])
  end

  def check_reported_packet_state(errors, actual) do
    case actual.packet_manifest["label_collection_status"] do
      @complete_reported ->
        errors
        |> require_equal(
          "packet_status",
          actual.packet_manifest["packet_status"],
          @complete_reported_packet_status
        )
        |> require_equal(
          "report_status",
          actual.packet_manifest["report_status"],
          @reported_from_validated_primary_labels
        )
        |> require_equal(
          "label_import_summary.status",
          get_in(actual.packet_manifest, ["label_import_summary", "status"]),
          "reported"
        )
        |> require_present_path(
          "label_results_import_summary path",
          get_in(actual.packet_manifest, ["artifact_paths", "label_results_import_summary"]),
          "label_results_import_summary.json"
        )
        |> check_metric_label_status(actual, @complete_reported)
        |> check_required_text(
          "README.md",
          actual.readme,
          [@complete_reported, "label_results_import_summary.json"]
        )
        |> check_required_text(
          "label report",
          actual.label_report_skeleton,
          [
            @complete_reported,
            @reported_from_validated_primary_labels,
            "label_results_import_summary.json"
          ]
        )
        |> reject_text(
          "README.md",
          actual.readme,
          [
            "It does not contain human labels",
            "Label collection status is\n`Not yet run`",
            "All fields are currently `Not yet run`"
          ]
        )
        |> reject_text(
          "label report",
          actual.label_report_skeleton,
          [
            "Human labels have not been collected",
            "Label collection remains `Not yet run`",
            "Claim level before labels"
          ]
        )

      @not_yet_run ->
        errors
        |> require_equal(
          "packet_status",
          actual.packet_manifest["packet_status"],
          "prepared_for_labeling"
        )
        |> require_equal(
          "packet adjudication status",
          get_in(actual.packet_manifest, ["adjudication", "status"]),
          @not_yet_run
        )
        |> check_metric_label_status(actual, @not_yet_run)

      other ->
        [
          "packet label_collection_status is #{inspect(other)}, expected a known packet state"
          | errors
        ]
    end
  end

  defp check_metric_label_status(errors, actual, expected_status) do
    metric_status_errors =
      actual.packet_manifest
      |> get_in(["metric_scope"])
      |> case do
        metric_scope when is_map(metric_scope) ->
          metric_scope
          |> Enum.flat_map(fn {metric, scope} ->
            if scope["label_status"] == expected_status do
              []
            else
              [
                "#{metric} label_status is #{inspect(scope["label_status"])}, expected #{inspect(expected_status)}"
              ]
            end
          end)

        _other ->
          ["packet manifest metric_scope must be an object"]
      end

    Enum.reduce(metric_status_errors, errors, &[&1 | &2])
  end

  def check_selector_repair_item(errors, actual) do
    item =
      Enum.find(actual.evidence_sufficiency_items, fn item ->
        item["task_id"] == "docops_struct_selector_missing_001"
      end)

    checks = [
      {"action status", get_in(item, ["action_under_review", "status"]), "rejected"},
      {"verifier decision", get_in(item, ["verifier_output", "decision"]), "reject"},
      {
        "selector status",
        get_in(item, ["evidence_packet", "observation", "selector_resolution", "status"]),
        "missing"
      },
      {
        "selector type",
        get_in(item, ["action_under_review", "action_payload", "selector", "type"]),
        "section"
      },
      {
        "selector heading",
        get_in(item, ["action_under_review", "action_payload", "selector", "heading"]),
        "Missing"
      }
    ]

    Enum.reduce(checks, errors, fn {label, actual_value, expected_value}, acc ->
      if actual_value == expected_value do
        acc
      else
        [
          "docops_struct_selector_missing_001 #{label} is #{inspect(actual_value)}, expected #{inspect(expected_value)}"
          | acc
        ]
      end
    end)
  end

  def require_equal(errors, label, actual, expected) do
    if actual == expected do
      errors
    else
      [
        "#{label} does not match regenerated source artifact#{diff_summary(actual, expected)}"
        | errors
      ]
    end
  end

  defp diff_summary(actual, expected) when is_list(actual) and is_list(expected) do
    cond do
      length(actual) != length(expected) ->
        " (actual count #{length(actual)}, expected #{length(expected)})"

      true ->
        index = Enum.find_index(Enum.zip(actual, expected), fn {left, right} -> left != right end)

        if is_integer(index) do
          {left, right} = Enum.at(Enum.zip(actual, expected), index)
          " (first mismatch at index #{index}: #{diff_summary(left, right)})"
        else
          ""
        end
    end
  end

  defp diff_summary(actual, expected) when is_map(actual) and is_map(expected) do
    actual_keys = actual |> Map.keys() |> MapSet.new()
    expected_keys = expected |> Map.keys() |> MapSet.new()
    only_actual = actual_keys |> MapSet.difference(expected_keys) |> MapSet.to_list()
    only_expected = expected_keys |> MapSet.difference(actual_keys) |> MapSet.to_list()

    common_mismatch =
      actual_keys
      |> MapSet.intersection(expected_keys)
      |> Enum.find(fn key -> actual[key] != expected[key] end)

    packet =
      case {actual["packet_id"], expected["packet_id"]} do
        {same, same} when is_binary(same) ->
          " packet_id=#{same},"

        {left, right} when is_binary(left) or is_binary(right) ->
          " packet_id #{inspect(left)} vs #{inspect(right)},"

        _other ->
          ""
      end

    nested =
      if is_nil(common_mismatch) do
        ""
      else
        ": #{diff_summary(actual[common_mismatch], expected[common_mismatch])}"
      end

    " (#{packet} only_actual=#{inspect(only_actual)}, only_expected=#{inspect(only_expected)}, first_value_mismatch=#{inspect(common_mismatch)}#{nested})"
  end

  defp diff_summary(actual, expected),
    do: " (actual=#{inspect(actual)}, expected=#{inspect(expected)})"

  def check_required_text(errors, label, text, required_strings) do
    required_strings
    |> Enum.reject(&String.contains?(text, &1))
    |> Enum.reduce(errors, fn missing, acc ->
      ["#{label} does not contain #{inspect(missing)}" | acc]
    end)
  end

  defp reject_text(errors, label, text, rejected_strings) do
    rejected_strings
    |> Enum.filter(&String.contains?(text, &1))
    |> Enum.reduce(errors, fn rejected, acc ->
      ["#{label} contains stale pre-label text #{inspect(rejected)}" | acc]
    end)
  end

  defp require_present_path(errors, label, value, expected_suffix) do
    cond do
      not is_binary(value) or String.trim(value) == "" ->
        ["#{label} must be a non-empty path" | errors]

      not String.ends_with?(value, expected_suffix) ->
        [
          "#{label} is #{inspect(value)}, expected to end with #{inspect(expected_suffix)}"
          | errors
        ]

      true ->
        errors
    end
  end

  defp require_count(errors, label, list, expected_count) do
    if length(list) == expected_count do
      errors
    else
      ["#{label} is #{length(list)}, expected #{expected_count}" | errors]
    end
  end

  defp require_values(errors, label, actual, expected) do
    if actual == expected do
      errors
    else
      ["#{label} is #{inspect(actual)}, expected #{inspect(expected)}" | errors]
    end
  end

  defp forbidden_keys(value, forbidden_keys), do: forbidden_keys(value, forbidden_keys, [])

  defp forbidden_keys(map, forbidden_keys, acc) when is_map(map) do
    map
    |> Enum.reduce(acc, fn {key, value}, acc ->
      acc =
        if key in forbidden_keys do
          [key | acc]
        else
          acc
        end

      forbidden_keys(value, forbidden_keys, acc)
    end)
  end

  defp forbidden_keys(list, forbidden_keys, acc) when is_list(list) do
    Enum.reduce(list, acc, &forbidden_keys(&1, forbidden_keys, &2))
  end

  defp forbidden_keys(_value, _forbidden_keys, acc), do: Enum.uniq(acc)

  defp expected_evidence_ids(prefix) do
    @evidence_sample
    |> Enum.with_index(1)
    |> Enum.map(fn {_sample, index} -> "#{prefix}-es-#{pad3(index)}" end)
  end

  defp expected_working_set_ids(prefix) do
    @working_set_task_ids
    |> Enum.with_index(1)
    |> Enum.flat_map(fn {_task_id, index} ->
      [
        "#{prefix}-ws-#{pad3(index)}-context_arm_A",
        "#{prefix}-ws-#{pad3(index)}-context_arm_B"
      ]
    end)
  end

  defp packet_prefix_from_manifest(manifest) do
    case get_in(manifest, ["source_run", "run_timestamp"]) do
      timestamp when is_binary(timestamp) -> "lb#{packet_date(timestamp)}"
      _other -> "lb#{packet_date(@default_run_timestamp)}"
    end
  end

  defp packet_date(run_timestamp), do: run_timestamp |> String.split("_") |> hd()

  defp pad3(number) do
    number
    |> Integer.to_string()
    |> String.pad_leading(3, "0")
  end
end
