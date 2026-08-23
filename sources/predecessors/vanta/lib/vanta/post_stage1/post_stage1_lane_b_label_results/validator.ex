defmodule Vanta.PostStage1LaneBLabelResults.Validator do
  @moduledoc false

  import Vanta.PostStage1LaneBLabelResults.PathHelpers, only: [present?: 1]

  @result_format "PS1-LB-LABEL-RESULT-LOCAL-001"
  @label_policy_version "PS1-LB-LABEL-001"
  @not_yet_run "Not yet run"
  @review_mode "double_human_adjudicated"
  @human_label_source "human"
  @complete_pending_report "complete_pending_report"
  @complete_reported "complete_reported"
  @complete_reported_packet_status "active_packet_complete_reported"
  @reported_from_validated_primary_labels "reported_from_validated_primary_labels"

  @collection_statuses [
    @not_yet_run,
    "in_progress",
    "collected_pending_adjudication",
    @complete_pending_report,
    @complete_reported
  ]

  @packet_manifest_statuses ["prepared_for_labeling", @complete_reported_packet_status]
  @packet_manifest_collection_statuses [@not_yet_run, @complete_reported]

  @freeze_statuses [@not_yet_run, "open", "frozen"]
  @agreement_statuses [@not_yet_run, "small_sample_raw_counts", "reported"]
  @evidence_metric "evidence_sufficiency_score"
  @working_context_metric "working_set_context"
  @context_omission_metric "context_omission_error_rate"
  @working_set_relevance_metric "working_set_relevance_score"
  @relevant_relevance_labels ["task_critical", "supporting"]

  @ps1_g7_context_metric_expectations [
    %{
      metric: @context_omission_metric,
      score: "0.3684",
      numerator_key: "omitted_task_critical_ref_count",
      numerator: 14,
      denominator_key: "task_critical_candidate_ref_count",
      denominator: 38
    },
    %{
      metric: @working_set_relevance_metric,
      score: "0.7742",
      numerator_key: "relevant_included_ref_count",
      numerator: 24,
      denominator_key: "included_ref_denominator",
      denominator: 31
    }
  ]

  @policy_metrics [
    @evidence_metric,
    @context_omission_metric,
    @working_set_relevance_metric
  ]

  @review_results ["confirm", "revise", "needs_adjudication"]
  @omission_severities ["none", "minor", "material", "critical", "needs_review"]
  @critical_omission_values [true, false, "needs_review"]
  @relevance_labels ["task_critical", "supporting", "irrelevant", "harmful", "needs_review"]

  @packet_quality_labels [
    "sufficient",
    "mostly_sufficient",
    "partial",
    "minimal",
    "absent_or_misleading",
    "needs_review"
  ]

  @exposure_timings ["not_exposed", "after_primary_label_freeze"]

  def validate_packet_inputs(manifest, evidence_items, working_set_items, adjudication) do
    errors =
      []
      |> require_equal(
        "packet label_policy_version",
        manifest["label_policy_version"],
        @label_policy_version
      )
      |> require_in("packet_status", manifest["packet_status"], @packet_manifest_statuses)
      |> require_in(
        "packet label_collection_status",
        manifest["label_collection_status"],
        @packet_manifest_collection_statuses
      )
      |> validate_manifest_lifecycle(manifest)
      |> require_equal(
        "source closure status",
        get_in(manifest, ["source_run", "closure_status"]),
        "accepted_by_closure"
      )
      |> require_equal("adjudication placeholder status", adjudication["status"], @not_yet_run)
      |> require_count("evidence sufficiency packet items", evidence_items, 8)
      |> require_count("working-set context packet items", working_set_items, 12)
      |> require_equal(
        "manifest evidence item count",
        get_in(manifest, ["metric_scope", @evidence_metric, "item_count"]),
        length(evidence_items)
      )
      |> require_equal(
        "manifest context omission item count",
        get_in(manifest, ["metric_scope", @context_omission_metric, "item_count"]),
        length(working_set_items)
      )
      |> require_equal(
        "manifest working-set relevance item count",
        get_in(manifest, ["metric_scope", @working_set_relevance_metric, "item_count"]),
        length(working_set_items)
      )

    if errors == [], do: :ok, else: {:error, Enum.reverse(errors)}
  end

  defp validate_manifest_lifecycle(
         errors,
         %{"label_collection_status" => @complete_reported} = manifest
       ) do
    errors
    |> require_equal("packet_status", manifest["packet_status"], @complete_reported_packet_status)
    |> require_equal(
      "report_status",
      manifest["report_status"],
      @reported_from_validated_primary_labels
    )
    |> require_equal(
      "label_import_summary.status",
      get_in(manifest, ["label_import_summary", "status"]),
      "reported"
    )
  end

  defp validate_manifest_lifecycle(errors, manifest) do
    errors
    |> require_equal("packet_status", manifest["packet_status"], "prepared_for_labeling")
    |> require_equal(
      "packet label_collection_status",
      manifest["label_collection_status"],
      @not_yet_run
    )
  end

  def validate_results(results, packet, result_path) when is_map(results) do
    raw_labels = map_field(results, "raw_labels")
    evidence_labels = list_field(raw_labels, @evidence_metric)
    working_labels = list_field(raw_labels, @working_context_metric)
    secondary_reviews = list_field(results, "secondary_reviews")
    adjudication_records = list_field(results, "adjudication_records")
    agreement_report = map_field(results, "agreement_report")
    freeze = map_field(results, "primary_label_freeze")
    collection_status = results["label_collection_status"]

    coverage = coverage_summary(evidence_labels, working_labels, secondary_reviews, packet)
    triggers = adjudication_triggers(evidence_labels, working_labels, secondary_reviews, packet)
    unhandled_triggers = unhandled_triggers(triggers, adjudication_records)
    needs_review_count = needs_review_count(evidence_labels, working_labels)

    errors =
      []
      |> validate_top_level(results, packet)
      |> validate_raw_label_container(raw_labels)
      |> validate_freeze(freeze)
      |> validate_evidence_labels(evidence_labels, packet)
      |> validate_working_set_labels(working_labels, packet)
      |> validate_no_duplicate_reviewers(@evidence_metric, evidence_labels)
      |> validate_no_duplicate_reviewers(@working_context_metric, working_labels)
      |> validate_secondary_reviews(secondary_reviews, packet, freeze)
      |> validate_adjudication_records(adjudication_records, packet, freeze)
      |> validate_agreement_report(agreement_report)
      |> validate_collection_state(
        collection_status,
        evidence_labels,
        working_labels,
        secondary_reviews,
        adjudication_records,
        agreement_report,
        freeze,
        coverage,
        unhandled_triggers
      )

    if errors == [] do
      {:ok,
       %{
         "status" => "ok",
         "result_path" => result_path,
         "result_format" => @result_format,
         "label_policy_version" => @label_policy_version,
         "packet_id" => packet.packet_manifest["packet_id"],
         "label_collection_status" => collection_status,
         "raw_label_counts" => %{
           @evidence_metric => length(evidence_labels),
           @working_context_metric => length(working_labels)
         },
         "secondary_review_count" => length(secondary_reviews),
         "adjudication_record_count" => length(adjudication_records),
         "needs_review_count" => needs_review_count,
         "adjudication_required_count" => length(triggers),
         "unhandled_adjudication_required_count" => length(unhandled_triggers),
         "adjudication_required" => triggers,
         "review_coverage" => coverage,
         "fixture_oracle_exposed_before_freeze" => freeze["fixture_oracle_exposed_before_freeze"],
         "reported_metric_scores" =>
           reported_metric_scores(evidence_labels, working_labels, packet),
         "claim_boundary" =>
           "Import validation summary only. It supports the packet-local Lane B label report under PS1-LB-LABEL-001; it is not broad validation, runtime approval, full Context OS validation, or an H1-H5 validation claim."
       }}
    else
      {:error, Enum.reverse(errors)}
    end
  end

  def validate_results(_results, _packet, result_path) do
    {:error, ["#{result_path} must contain a JSON object"]}
  end

  def reported_metric_scores(results, packet) when is_map(results) do
    raw_labels = map_field(results, "raw_labels")

    reported_metric_scores(
      list_field(raw_labels, @evidence_metric),
      list_field(raw_labels, @working_context_metric),
      packet
    )
  end

  def reported_metric_scores(evidence_labels, working_labels, packet) do
    working_item_by_id =
      packet.working_set_context_items
      |> Map.new(fn item -> {item["packet_id"], item} end)

    working_item_labels = primary_item_labels(working_labels)
    omission_counts = count_by_arm(working_item_labels, working_item_by_id, &omission_counts/2)
    relevance_counts = count_by_arm(working_item_labels, working_item_by_id, &relevance_counts/2)

    %{
      @evidence_metric => evidence_score(evidence_labels),
      @context_omission_metric =>
        score_with_arms(omission_counts, "omitted_task_critical_ref_count",
          denominator_key: "task_critical_candidate_ref_count"
        ),
      @working_set_relevance_metric =>
        score_with_arms(relevance_counts, "relevant_included_ref_count",
          denominator_key: "included_ref_denominator"
        )
    }
  end

  defp evidence_score(labels) do
    numeric_labels =
      labels
      |> Enum.map(& &1["raw_label_0_to_4_or_needs_review"])
      |> Enum.filter(&is_integer/1)

    numerator = Enum.sum(numeric_labels)
    denominator = length(numeric_labels) * 4

    %{
      "raw_label_count" => length(labels),
      "scored_raw_label_count" => length(numeric_labels),
      "normalized_score_numerator" => numerator,
      "normalized_score_denominator" => denominator,
      "score_4dp" => score_4dp(numerator, denominator)
    }
  end

  defp primary_item_labels(labels) do
    labels
    |> Enum.group_by(& &1["item_id"])
    |> Enum.map(fn {item_id, item_labels} ->
      label =
        item_labels
        |> Enum.sort_by(&to_string(&1["reviewer_id"]))
        |> List.first()

      {item_id, label}
    end)
    |> Enum.sort_by(fn {item_id, _label} -> item_id end)
  end

  defp count_by_arm(item_labels, item_by_id, count_fun) do
    by_arm =
      item_labels
      |> Enum.map(fn {item_id, label} ->
        item = Map.get(item_by_id, item_id, %{})
        arm = item["blinded_arm"] || "unknown"
        {arm, count_fun.(label, item)}
      end)
      |> Enum.group_by(fn {arm, _counts} -> arm end, fn {_arm, counts} -> counts end)
      |> Map.new(fn {arm, counts} -> {arm, sum_counts(counts)} end)

    Map.put(by_arm, "Combined", by_arm |> Map.values() |> sum_counts())
  end

  defp omission_counts(label, _item) do
    omission = map_field(label, "omission")

    %{
      numerator: length(list_field(omission, "omitted_task_critical_ref_ids")),
      denominator: length(list_field(omission, "task_critical_candidate_ref_ids"))
    }
  end

  defp relevance_counts(label, item) do
    selected_ref_ids = list_field(item, "selected_ref_ids")

    relevance_by_ref =
      label
      |> list_field("per_ref_relevance_labels")
      |> Map.new(fn ref_label -> {ref_label["ref_id"], ref_label["relevance_label"]} end)

    numerator =
      Enum.count(selected_ref_ids, fn ref_id ->
        Map.get(relevance_by_ref, ref_id) in @relevant_relevance_labels
      end)

    %{
      numerator: numerator,
      denominator: max(length(selected_ref_ids), 1)
    }
  end

  defp sum_counts(counts) do
    Enum.reduce(counts, %{numerator: 0, denominator: 0}, fn counts, acc ->
      %{
        numerator: acc.numerator + counts.numerator,
        denominator: acc.denominator + counts.denominator
      }
    end)
  end

  defp score_with_arms(counts_by_arm, numerator_key, opts) do
    denominator_key = Keyword.fetch!(opts, :denominator_key)
    combined = Map.fetch!(counts_by_arm, "Combined")

    %{
      numerator_key => combined.numerator,
      denominator_key => combined.denominator,
      "score_4dp" => score_4dp(combined.numerator, combined.denominator),
      "by_blinded_arm" =>
        counts_by_arm
        |> Map.drop(["Combined"])
        |> Map.new(fn {arm, counts} ->
          {arm, ratio_counts(counts, numerator_key, denominator_key)}
        end)
        |> Map.put("Combined", ratio_counts(combined, numerator_key, denominator_key))
    }
  end

  defp ratio_counts(counts, numerator_key, denominator_key) do
    %{
      numerator_key => counts.numerator,
      denominator_key => counts.denominator,
      "score_4dp" => score_4dp(counts.numerator, counts.denominator)
    }
  end

  def validate_import_summary_parity(errors, generated_summary, saved_summary) do
    ~w(
      status
      result_path
      result_format
      label_policy_version
      packet_id
      label_collection_status
      raw_label_counts
      secondary_review_count
      adjudication_record_count
      needs_review_count
      adjudication_required_count
      unhandled_adjudication_required_count
      adjudication_required
      review_coverage
      fixture_oracle_exposed_before_freeze
      reported_metric_scores
    )
    |> Enum.reduce(errors, fn key, errors ->
      require_equal(
        errors,
        "import summary #{key}",
        saved_summary[key],
        generated_summary[key]
      )
    end)
  end

  def validate_locked_context_metric_values(errors, metric_scores) do
    Enum.reduce(@ps1_g7_context_metric_expectations, errors, fn expected, errors ->
      metric_score = Map.get(metric_scores, expected.metric, %{})

      errors
      |> require_equal(
        "PS1-G7 #{expected.metric} score",
        metric_score["score_4dp"],
        expected.score
      )
      |> require_equal(
        "PS1-G7 #{expected.metric} numerator",
        metric_score[expected.numerator_key],
        expected.numerator
      )
      |> require_equal(
        "PS1-G7 #{expected.metric} denominator",
        metric_score[expected.denominator_key],
        expected.denominator
      )
    end)
  end

  def locked_context_metric_summary(metric_scores) do
    Map.new(@ps1_g7_context_metric_expectations, fn expected ->
      metric_score = Map.fetch!(metric_scores, expected.metric)

      {expected.metric,
       %{
         "score_4dp" => metric_score["score_4dp"],
         expected.numerator_key => metric_score[expected.numerator_key],
         expected.denominator_key => metric_score[expected.denominator_key]
       }}
    end)
  end

  def validate_report_text_parity(errors, report_text, generated_summary, metric_scores) do
    metric_rows = report_metric_rows(report_text)
    arm_rows = report_working_set_arm_rows(report_text)

    evidence_score = metric_scores[@evidence_metric]
    omission_score = metric_scores[@context_omission_metric]
    relevance_score = metric_scores[@working_set_relevance_metric]

    errors
    |> require_report_metric_row(
      metric_rows,
      @evidence_metric,
      generated_summary["raw_label_counts"][@evidence_metric],
      evidence_score["score_4dp"],
      nil,
      nil
    )
    |> require_report_metric_row(
      metric_rows,
      @context_omission_metric,
      generated_summary["raw_label_counts"][@working_context_metric],
      omission_score["score_4dp"],
      omission_score["omitted_task_critical_ref_count"],
      omission_score["task_critical_candidate_ref_count"]
    )
    |> require_report_metric_row(
      metric_rows,
      @working_set_relevance_metric,
      generated_summary["raw_label_counts"][@working_context_metric],
      relevance_score["score_4dp"],
      relevance_score["relevant_included_ref_count"],
      relevance_score["included_ref_denominator"]
    )
    |> require_report_working_set_arm_rows(
      arm_rows,
      omission_score["by_blinded_arm"],
      relevance_score["by_blinded_arm"]
    )
    |> require_import_summary_snippets(report_text, generated_summary)
  end

  defp require_report_metric_row(errors, rows, metric, raw_count, score, numerator, denominator) do
    case Map.get(rows, metric) do
      nil ->
        ["label report is missing Label Results row for #{metric}" | errors]

      row ->
        errors
        |> require_equal(
          "label report #{metric} raw labels",
          parse_int(row["raw_label_count"]),
          raw_count
        )
        |> require_equal("label report #{metric} score", row["score"], score)
        |> require_equal(
          "label report #{metric} needs_review count",
          parse_int(row["needs_review_count"]),
          0
        )
        |> require_equal("label report #{metric} status", row["status"], @complete_reported)
        |> maybe_require_fraction(metric, row, numerator, denominator)
    end
  end

  defp maybe_require_fraction(errors, _metric, _row, nil, nil), do: errors

  defp maybe_require_fraction(errors, metric, row, numerator, denominator) do
    errors
    |> require_equal("label report #{metric} numerator", parse_int(row["numerator"]), numerator)
    |> require_equal(
      "label report #{metric} denominator",
      parse_int(row["denominator"]),
      denominator
    )
  end

  defp require_report_working_set_arm_rows(errors, rows, omission_by_arm, relevance_by_arm) do
    ["context_arm_A", "context_arm_B", "Combined"]
    |> Enum.reduce(errors, fn arm, errors ->
      case Map.get(rows, arm) do
        nil ->
          ["label report is missing working-set arm row for #{arm}" | errors]

        row ->
          omission = Map.fetch!(omission_by_arm, arm)
          relevance = Map.fetch!(relevance_by_arm, arm)

          errors
          |> require_equal(
            "label report #{arm} omission score",
            row["omission_score"],
            omission["score_4dp"]
          )
          |> require_equal(
            "label report #{arm} omission numerator",
            parse_int(row["omission_numerator"]),
            omission["omitted_task_critical_ref_count"]
          )
          |> require_equal(
            "label report #{arm} omission denominator",
            parse_int(row["omission_denominator"]),
            omission["task_critical_candidate_ref_count"]
          )
          |> require_equal(
            "label report #{arm} relevance score",
            row["relevance_score"],
            relevance["score_4dp"]
          )
          |> require_equal(
            "label report #{arm} relevance numerator",
            parse_int(row["relevance_numerator"]),
            relevance["relevant_included_ref_count"]
          )
          |> require_equal(
            "label report #{arm} relevance denominator",
            parse_int(row["relevance_denominator"]),
            relevance["included_ref_denominator"]
          )
      end
    end)
  end

  defp require_import_summary_snippets(errors, report_text, summary) do
    coverage = summary["review_coverage"]

    expected_snippets = [
      "`#{@evidence_metric} = #{summary["raw_label_counts"][@evidence_metric]}`",
      "`#{@working_context_metric} = #{summary["raw_label_counts"][@working_context_metric]}`"
    ]

    expected_snippets =
      expected_snippets ++
        Enum.map(@policy_metrics, fn metric ->
          metric_coverage = coverage[metric]

          "`#{metric} = #{metric_coverage["fully_reviewed_item_count"]} / #{metric_coverage["expected_item_count"]}`"
        end)

    Enum.reduce(expected_snippets, errors, fn snippet, errors ->
      if String.contains?(report_text, snippet) do
        errors
      else
        ["label report Import Summary is missing #{snippet}" | errors]
      end
    end)
  end

  def validate_context_metric_surfaces(errors, surfaces) do
    Enum.reduce(surfaces, errors, fn {path, text}, errors ->
      Enum.reduce(@ps1_g7_context_metric_expectations, errors, fn expected, errors ->
        pattern = context_metric_surface_pattern(expected)

        if Regex.match?(pattern, text) do
          errors
        else
          [
            "#{path} is missing locked #{expected.metric} = #{expected.score} (#{expected.numerator} / #{expected.denominator})"
            | errors
          ]
        end
      end)
    end)
  end

  defp context_metric_surface_pattern(expected) do
    Regex.compile!(
      "#{Regex.escape(expected.metric)}\\s*=\\s*`?#{Regex.escape(expected.score)}`?[\\s`\\(]*#{expected.numerator}\\s*/\\s*#{expected.denominator}"
    )
  end

  defp report_metric_rows(report_text) do
    row_pattern =
      ~r/^\|\s*`(?<metric>[^`]+)`\s*\|\s*(?<raw_label_count>\d+)\s*\|[^|]*\|\s*`(?<score>[^`]+)`(?:\s*\(`(?<numerator>\d+)\s*\/\s*(?<denominator>\d+)`\))?\s*\|\s*(?<needs_review_count>\d+)\s*\|\s*`(?<status>[^`]+)`\s*\|$/

    report_text
    |> String.split(~r/\R/)
    |> Enum.reduce(%{}, fn line, rows ->
      case Regex.named_captures(row_pattern, line) do
        nil -> rows
        row -> Map.put(rows, row["metric"], row)
      end
    end)
  end

  defp report_working_set_arm_rows(report_text) do
    row_pattern =
      ~r/^\|\s*(?:`(?<arm>context_arm_[AB])`|(?<plain_arm>Combined))\s*\|\s*`(?<omission_score>[^`]+)`\s*\(`(?<omission_numerator>\d+)\s*\/\s*(?<omission_denominator>\d+)`\)\s*\|\s*`(?<relevance_score>[^`]+)`\s*\(`(?<relevance_numerator>\d+)\s*\/\s*(?<relevance_denominator>\d+)`\)\s*\|$/

    report_text
    |> String.split(~r/\R/)
    |> Enum.reduce(%{}, fn line, rows ->
      case Regex.named_captures(row_pattern, line) do
        nil ->
          rows

        row ->
          arm = if row["arm"] == "", do: row["plain_arm"], else: row["arm"]
          Map.put(rows, arm, row)
      end
    end)
  end

  defp validate_top_level(errors, results, packet) do
    allowed_keys =
      MapSet.new(~w(
        result_format
        label_policy_version
        packet_id
        packet_manifest_path
        label_collection_status
        review_mode
        primary_label_freeze
        raw_labels
        secondary_reviews
        adjudication_records
        agreement_report
        reporting_boundary
      ))

    unknown_keys = Map.keys(results) |> Enum.reject(&MapSet.member?(allowed_keys, &1))

    errors
    |> add_unknown_key_errors("result", unknown_keys)
    |> require_equal("result_format", results["result_format"], @result_format)
    |> require_equal(
      "label_policy_version",
      results["label_policy_version"],
      @label_policy_version
    )
    |> require_equal("packet_id", results["packet_id"], packet.packet_manifest["packet_id"])
    |> require_equal("review_mode", results["review_mode"], @review_mode)
    |> require_in(
      "label_collection_status",
      results["label_collection_status"],
      @collection_statuses
    )
    |> require_string("packet_manifest_path", results["packet_manifest_path"])
  end

  defp validate_raw_label_container(errors, raw_labels) do
    errors
    |> require_map("raw_labels", raw_labels)
    |> require_list("raw_labels.#{@evidence_metric}", raw_labels[@evidence_metric])
    |> require_list("raw_labels.#{@working_context_metric}", raw_labels[@working_context_metric])
  end

  defp validate_freeze(errors, freeze) do
    errors
    |> require_map("primary_label_freeze", freeze)
    |> require_in("primary_label_freeze.status", freeze["status"], @freeze_statuses)
    |> require_boolean(
      "primary_label_freeze.fixture_oracle_exposed_before_freeze",
      freeze["fixture_oracle_exposed_before_freeze"]
    )
    |> then(fn errors ->
      if freeze["fixture_oracle_exposed_before_freeze"] == false do
        errors
      else
        [
          "primary_label_freeze.fixture_oracle_exposed_before_freeze must remain false under PS1-LB-LABEL-001"
          | errors
        ]
      end
    end)
    |> then(fn errors ->
      if freeze["status"] == "frozen" do
        require_string(errors, "primary_label_freeze.frozen_at", freeze["frozen_at"])
      else
        errors
      end
    end)
  end

  defp validate_evidence_labels(errors, labels, packet) do
    labels
    |> Enum.with_index(1)
    |> Enum.reduce(errors, fn {label, index}, errors ->
      context = "raw_labels.#{@evidence_metric}[#{index}]"
      item_id = label["item_id"]
      known_refs = Map.get(packet.item_refs, item_id, MapSet.new())

      errors
      |> require_map(context, label)
      |> require_allowed_keys(
        context,
        label,
        ~w(metric item_id label_source reviewer_id raw_label_0_to_4_or_needs_review confidence rationale referenced_artifact_ids labeled_at)
      )
      |> require_equal("#{context}.metric", label["metric"], @evidence_metric)
      |> require_equal("#{context}.label_source", label["label_source"], @human_label_source)
      |> require_known_id("#{context}.item_id", item_id, packet.evidence_ids)
      |> require_reviewer_id("#{context}.reviewer_id", label["reviewer_id"])
      |> require_evidence_raw_label(
        "#{context}.raw_label_0_to_4_or_needs_review",
        label["raw_label_0_to_4_or_needs_review"]
      )
      |> require_confidence("#{context}.confidence", label["confidence"])
      |> require_string("#{context}.rationale", label["rationale"])
      |> require_referenced_artifacts(
        "#{context}.referenced_artifact_ids",
        label["referenced_artifact_ids"],
        known_refs
      )
    end)
  end

  defp validate_working_set_labels(errors, labels, packet) do
    labels
    |> Enum.with_index(1)
    |> Enum.reduce(errors, fn {label, index}, errors ->
      context = "raw_labels.#{@working_context_metric}[#{index}]"
      item_id = label["item_id"]
      known_refs = Map.get(packet.item_refs, item_id, MapSet.new())
      candidate_refs = Map.get(packet.candidate_refs, item_id, MapSet.new())

      errors
      |> require_map(context, label)
      |> require_allowed_keys(
        context,
        label,
        ~w(metric item_id label_source reviewer_id omission per_ref_relevance_labels packet_relevance_quality confidence rationale referenced_artifact_ids labeled_at)
      )
      |> require_equal("#{context}.metric", label["metric"], @working_context_metric)
      |> require_equal("#{context}.label_source", label["label_source"], @human_label_source)
      |> require_known_id("#{context}.item_id", item_id, packet.working_set_ids)
      |> require_reviewer_id("#{context}.reviewer_id", label["reviewer_id"])
      |> validate_omission("#{context}.omission", label["omission"], candidate_refs)
      |> validate_per_ref_relevance(
        "#{context}.per_ref_relevance_labels",
        label["per_ref_relevance_labels"],
        candidate_refs
      )
      |> require_in(
        "#{context}.packet_relevance_quality",
        label["packet_relevance_quality"],
        @packet_quality_labels
      )
      |> require_confidence("#{context}.confidence", label["confidence"])
      |> require_string("#{context}.rationale", label["rationale"])
      |> require_referenced_artifacts(
        "#{context}.referenced_artifact_ids",
        label["referenced_artifact_ids"],
        known_refs
      )
    end)
  end

  defp validate_secondary_reviews(errors, reviews, packet, freeze) do
    reviews
    |> Enum.with_index(1)
    |> Enum.reduce(errors, fn {review, index}, errors ->
      context = "secondary_reviews[#{index}]"
      metric = review["metric"]
      item_ids = item_ids_for_secondary_metric(metric, packet)
      known_refs = Map.get(packet.item_refs, review["item_id"], MapSet.new())

      errors
      |> require_map(context, review)
      |> require_allowed_keys(
        context,
        review,
        ~w(metric item_id primary_reviewer_id secondary_reviewer_id review_result confidence rationale referenced_artifact_ids fixture_oracle_exposed fixture_oracle_exposure_timing reviewed_at)
      )
      |> require_in("#{context}.metric", metric, [@evidence_metric, @working_context_metric])
      |> require_known_id("#{context}.item_id", review["item_id"], item_ids)
      |> require_reviewer_id("#{context}.primary_reviewer_id", review["primary_reviewer_id"])
      |> require_reviewer_id("#{context}.secondary_reviewer_id", review["secondary_reviewer_id"])
      |> require_distinct_reviewers(
        context,
        review["primary_reviewer_id"],
        review["secondary_reviewer_id"]
      )
      |> require_in("#{context}.review_result", review["review_result"], @review_results)
      |> require_confidence("#{context}.confidence", review["confidence"])
      |> require_string("#{context}.rationale", review["rationale"])
      |> require_referenced_artifacts(
        "#{context}.referenced_artifact_ids",
        review["referenced_artifact_ids"],
        known_refs
      )
      |> validate_oracle_exposure(context, review, freeze)
    end)
  end

  defp validate_adjudication_records(errors, records, packet, freeze) do
    records
    |> Enum.with_index(1)
    |> Enum.reduce(errors, fn {record, index}, errors ->
      context = "adjudication_records[#{index}]"
      metric = record["metric"]
      item_ids = item_ids_for_policy_metric(metric, packet)
      known_refs = Map.get(packet.item_refs, record["item_id"], MapSet.new())

      errors
      |> require_map(context, record)
      |> require_allowed_keys(
        context,
        record,
        ~w(metric item_id trigger_reasons original_labels adjudicated_label adjudicator_id rationale artifact_refs_inspected fixture_oracle_exposed fixture_oracle_exposure_timing adjudicated_at)
      )
      |> require_in("#{context}.metric", metric, @policy_metrics)
      |> require_known_id("#{context}.item_id", record["item_id"], item_ids)
      |> require_non_empty_string_list("#{context}.trigger_reasons", record["trigger_reasons"])
      |> validate_original_labels("#{context}.original_labels", record["original_labels"])
      |> validate_adjudicated_label(
        "#{context}.adjudicated_label",
        metric,
        record["adjudicated_label"],
        packet,
        record["item_id"]
      )
      |> require_reviewer_id("#{context}.adjudicator_id", record["adjudicator_id"])
      |> require_string("#{context}.rationale", record["rationale"])
      |> require_referenced_artifacts(
        "#{context}.artifact_refs_inspected",
        record["artifact_refs_inspected"],
        known_refs
      )
      |> validate_oracle_exposure(context, record, freeze)
    end)
  end

  defp validate_agreement_report(errors, agreement_report) do
    errors
    |> require_map("agreement_report", agreement_report)
    |> require_in("agreement_report.status", agreement_report["status"], @agreement_statuses)
    |> then(fn errors ->
      if agreement_report["status"] == @not_yet_run do
        errors
      else
        errors
        |> require_string("agreement_report.method", agreement_report["method"])
        |> require_map(
          "agreement_report.raw_agreement_counts",
          agreement_report["raw_agreement_counts"]
        )
        |> require_string("agreement_report.notes", agreement_report["notes"])
      end
    end)
  end

  defp validate_collection_state(
         errors,
         @not_yet_run,
         evidence_labels,
         working_labels,
         secondary_reviews,
         adjudication_records,
         agreement_report,
         freeze,
         _coverage,
         _unhandled_triggers
       ) do
    errors
    |> require_empty("raw evidence labels", evidence_labels)
    |> require_empty("raw working-set labels", working_labels)
    |> require_empty("secondary_reviews", secondary_reviews)
    |> require_empty("adjudication_records", adjudication_records)
    |> require_equal("primary_label_freeze.status", freeze["status"], @not_yet_run)
    |> require_equal("agreement_report.status", agreement_report["status"], @not_yet_run)
  end

  defp validate_collection_state(
         errors,
         "collected_pending_adjudication",
         _evidence_labels,
         _working_labels,
         _secondary_reviews,
         _adjudication_records,
         _agreement_report,
         freeze,
         coverage,
         _unhandled_triggers
       ) do
    errors
    |> require_equal("primary_label_freeze.status", freeze["status"], "frozen")
    |> require_full_coverage("collected_pending_adjudication", coverage)
  end

  defp validate_collection_state(
         errors,
         status,
         _evidence_labels,
         _working_labels,
         _secondary_reviews,
         _adjudication_records,
         agreement_report,
         freeze,
         coverage,
         unhandled_triggers
       )
       when status in [@complete_pending_report, @complete_reported] do
    errors
    |> require_equal("primary_label_freeze.status", freeze["status"], "frozen")
    |> require_full_coverage(status, coverage)
    |> require_empty_unhandled_triggers(status, unhandled_triggers)
    |> then(fn errors ->
      if agreement_report["status"] == @not_yet_run do
        ["#{status} requires agreement_report.status to be reported" | errors]
      else
        errors
      end
    end)
  end

  defp validate_collection_state(
         errors,
         "in_progress",
         _evidence_labels,
         _working_labels,
         _secondary_reviews,
         _adjudication_records,
         _agreement_report,
         _freeze,
         _coverage,
         _unhandled_triggers
       ) do
    errors
  end

  defp validate_collection_state(errors, _other, _e, _w, _s, _a, _g, _f, _c, _u), do: errors

  defp validate_no_duplicate_reviewers(errors, metric, labels) do
    labels
    |> Enum.group_by(fn label -> {label["item_id"], label["reviewer_id"]} end)
    |> Enum.filter(fn {{item_id, reviewer_id}, grouped} ->
      present?(item_id) and present?(reviewer_id) and length(grouped) > 1
    end)
    |> Enum.reduce(errors, fn {{item_id, reviewer_id}, _grouped}, errors ->
      [
        "#{metric} has duplicate raw labels for item #{item_id} by reviewer #{reviewer_id}"
        | errors
      ]
    end)
  end

  defp validate_omission(errors, context, omission, candidate_refs) do
    errors
    |> require_map(context, omission)
    |> require_allowed_keys(
      context,
      omission,
      ~w(omission_severity omitted_task_critical_ref_ids task_critical_candidate_ref_ids critical_omission denominator_ref_ids)
    )
    |> require_in(
      "#{context}.omission_severity",
      omission["omission_severity"],
      @omission_severities
    )
    |> require_ref_id_list(
      "#{context}.omitted_task_critical_ref_ids",
      omission["omitted_task_critical_ref_ids"],
      candidate_refs
    )
    |> require_ref_id_list(
      "#{context}.task_critical_candidate_ref_ids",
      omission["task_critical_candidate_ref_ids"],
      candidate_refs
    )
    |> require_in(
      "#{context}.critical_omission",
      omission["critical_omission"],
      @critical_omission_values
    )
    |> require_ref_id_list(
      "#{context}.denominator_ref_ids",
      omission["denominator_ref_ids"],
      candidate_refs
    )
  end

  defp validate_per_ref_relevance(errors, context, labels, candidate_refs) do
    errors = require_list(errors, context, labels)
    labels = if is_list(labels), do: labels, else: []

    labeled_ids =
      labels
      |> Enum.map(& &1["ref_id"])
      |> Enum.filter(&present?/1)

    duplicate_ids =
      labeled_ids
      |> Enum.frequencies()
      |> Enum.filter(fn {_ref_id, count} -> count > 1 end)
      |> Enum.map(fn {ref_id, _count} -> ref_id end)

    missing_ids =
      candidate_refs
      |> MapSet.difference(MapSet.new(labeled_ids))
      |> MapSet.to_list()
      |> Enum.sort()

    extra_ids =
      labeled_ids
      |> MapSet.new()
      |> MapSet.difference(candidate_refs)
      |> MapSet.to_list()
      |> Enum.sort()

    labels
    |> Enum.with_index(1)
    |> Enum.reduce(errors, fn {label, index}, errors ->
      entry_context = "#{context}[#{index}]"

      errors
      |> require_map(entry_context, label)
      |> require_allowed_keys(entry_context, label, ~w(ref_id relevance_label))
      |> require_known_id("#{entry_context}.ref_id", label["ref_id"], candidate_refs)
      |> require_in(
        "#{entry_context}.relevance_label",
        label["relevance_label"],
        @relevance_labels
      )
    end)
    |> then(fn errors ->
      errors
      |> add_list_error("#{context} has duplicate ref_id values", duplicate_ids)
      |> add_list_error("#{context} is missing candidate ref_ids", missing_ids)
      |> add_list_error("#{context} has unknown candidate ref_ids", extra_ids)
    end)
  end

  defp validate_original_labels(errors, context, labels) do
    errors = require_list(errors, context, labels)
    labels = if is_list(labels), do: labels, else: []

    errors =
      if labels == [] do
        ["#{context} must include the original labels inspected for adjudication" | errors]
      else
        errors
      end

    labels
    |> Enum.with_index(1)
    |> Enum.reduce(errors, fn {label, index}, errors ->
      label_context = "#{context}[#{index}]"

      errors
      |> require_map(label_context, label)
      |> require_reviewer_id("#{label_context}.reviewer_id", label["reviewer_id"])
    end)
  end

  defp validate_adjudicated_label(errors, context, @evidence_metric, label, _packet, _item_id) do
    require_evidence_raw_label(errors, context, label)
  end

  defp validate_adjudicated_label(
         errors,
         context,
         @context_omission_metric,
         label,
         packet,
         item_id
       ) do
    candidate_refs = Map.get(packet.candidate_refs, item_id, MapSet.new())
    validate_omission(errors, context, label, candidate_refs)
  end

  defp validate_adjudicated_label(
         errors,
         context,
         @working_set_relevance_metric,
         label,
         packet,
         item_id
       ) do
    candidate_refs = Map.get(packet.candidate_refs, item_id, MapSet.new())

    errors
    |> require_map(context, label)
    |> require_allowed_keys(context, label, ~w(per_ref_relevance_labels packet_relevance_quality))
    |> validate_per_ref_relevance(
      "#{context}.per_ref_relevance_labels",
      label["per_ref_relevance_labels"],
      candidate_refs
    )
    |> require_in(
      "#{context}.packet_relevance_quality",
      label["packet_relevance_quality"],
      @packet_quality_labels
    )
  end

  defp validate_adjudicated_label(errors, context, _metric, _label, _packet, _item_id) do
    ["#{context} cannot be validated because metric is not a PS1-LB-LABEL-001 metric" | errors]
  end

  defp validate_oracle_exposure(errors, context, record, freeze) do
    errors =
      errors
      |> require_boolean("#{context}.fixture_oracle_exposed", record["fixture_oracle_exposed"])
      |> require_in(
        "#{context}.fixture_oracle_exposure_timing",
        record["fixture_oracle_exposure_timing"],
        @exposure_timings
      )

    cond do
      record["fixture_oracle_exposed"] == true and
          record["fixture_oracle_exposure_timing"] != "after_primary_label_freeze" ->
        [
          "#{context}.fixture_oracle_exposure_timing must be after_primary_label_freeze when fixture_oracle_exposed is true"
          | errors
        ]

      record["fixture_oracle_exposed"] == true and freeze["status"] != "frozen" ->
        ["#{context} exposes fixture oracle metadata before primary labels are frozen" | errors]

      record["fixture_oracle_exposed"] == false and
          record["fixture_oracle_exposure_timing"] != "not_exposed" ->
        [
          "#{context}.fixture_oracle_exposure_timing must be not_exposed when fixture_oracle_exposed is false"
          | errors
        ]

      true ->
        errors
    end
  end

  defp coverage_summary(evidence_labels, working_labels, secondary_reviews, packet) do
    %{
      @evidence_metric =>
        metric_coverage(@evidence_metric, packet.evidence_ids, evidence_labels, secondary_reviews),
      @context_omission_metric =>
        metric_coverage(
          @working_context_metric,
          packet.working_set_ids,
          working_labels,
          secondary_reviews
        ),
      @working_set_relevance_metric =>
        metric_coverage(
          @working_context_metric,
          packet.working_set_ids,
          working_labels,
          secondary_reviews
        )
    }
  end

  defp metric_coverage(raw_metric, expected_ids, labels, secondary_reviews) do
    covered_ids =
      expected_ids
      |> Enum.filter(fn item_id ->
        raw_reviewers =
          labels
          |> Enum.filter(&(&1["item_id"] == item_id))
          |> Enum.map(& &1["reviewer_id"])
          |> Enum.filter(&present?/1)
          |> MapSet.new()

        secondary_substitution =
          Enum.any?(secondary_reviews, fn review ->
            review["metric"] == raw_metric and review["item_id"] == item_id and
              present?(review["primary_reviewer_id"]) and
              present?(review["secondary_reviewer_id"]) and
              review["primary_reviewer_id"] != review["secondary_reviewer_id"] and
              review["review_result"] in ["confirm", "revise"]
          end)

        MapSet.size(raw_reviewers) >= 2 or secondary_substitution
      end)
      |> Enum.sort()

    missing_ids =
      expected_ids
      |> MapSet.difference(MapSet.new(covered_ids))
      |> MapSet.to_list()
      |> Enum.sort()

    %{
      "expected_item_count" => MapSet.size(expected_ids),
      "fully_reviewed_item_count" => length(covered_ids),
      "missing_item_ids" => missing_ids
    }
  end

  defp adjudication_triggers(evidence_labels, working_labels, secondary_reviews, packet) do
    evidence_triggers(evidence_labels, secondary_reviews)
    |> Kernel.++(context_omission_triggers(working_labels, secondary_reviews, packet))
    |> Kernel.++(working_set_relevance_triggers(working_labels, secondary_reviews, packet))
    |> Enum.map(fn trigger ->
      Map.update!(trigger, "trigger_reasons", fn reasons ->
        reasons |> Enum.uniq() |> Enum.sort()
      end)
    end)
    |> Enum.sort_by(&{&1["metric"], &1["item_id"]})
  end

  defp evidence_triggers(labels, secondary_reviews) do
    labels
    |> Enum.group_by(& &1["item_id"])
    |> Enum.flat_map(fn {item_id, item_labels} ->
      raw_values = Enum.map(item_labels, & &1["raw_label_0_to_4_or_needs_review"])
      numeric = Enum.filter(raw_values, &is_integer/1)

      reasons =
        []
        |> maybe_add(Enum.any?(raw_values, &(&1 == "needs_review")), "needs_review")
        |> maybe_add(pairwise_difference_at_least?(numeric, 2), "ordinal_difference_ge_2")
        |> maybe_add(acceptability_boundary_split?(numeric), "acceptability_boundary_split")
        |> maybe_add(
          secondary_needs_adjudication?(@evidence_metric, item_id, secondary_reviews),
          "secondary_review_needs_adjudication"
        )

      trigger_or_empty(@evidence_metric, item_id, reasons)
    end)
  end

  defp context_omission_triggers(labels, secondary_reviews, _packet) do
    labels
    |> Enum.group_by(& &1["item_id"])
    |> Enum.flat_map(fn {item_id, item_labels} ->
      omissions = Enum.map(item_labels, &map_field(&1, "omission"))

      reasons =
        []
        |> maybe_add(Enum.any?(omissions, &omission_needs_review?/1), "needs_review")
        |> maybe_add(
          set_field_disagrees?(omissions, "omitted_task_critical_ref_ids"),
          "omitted_task_critical_ref_ids_disagreement"
        )
        |> maybe_add(
          set_field_disagrees?(omissions, "task_critical_candidate_ref_ids"),
          "task_critical_candidate_ref_ids_disagreement"
        )
        |> maybe_add(
          set_field_disagrees?(omissions, "denominator_ref_ids"),
          "denominator_disagreement"
        )
        |> maybe_add(
          scalar_field_disagrees?(omissions, "critical_omission"),
          "critical_omission_disagreement"
        )
        |> maybe_add(
          secondary_needs_adjudication?(@working_context_metric, item_id, secondary_reviews),
          "secondary_review_needs_adjudication"
        )

      trigger_or_empty(@context_omission_metric, item_id, reasons)
    end)
  end

  defp working_set_relevance_triggers(labels, secondary_reviews, _packet) do
    labels
    |> Enum.group_by(& &1["item_id"])
    |> Enum.flat_map(fn {item_id, item_labels} ->
      per_ref_labels = Enum.map(item_labels, &list_field(&1, "per_ref_relevance_labels"))
      qualities = Enum.map(item_labels, & &1["packet_relevance_quality"])

      reasons =
        []
        |> maybe_add(
          per_ref_needs_review?(per_ref_labels) or Enum.any?(qualities, &(&1 == "needs_review")),
          "needs_review"
        )
        |> maybe_add(per_ref_harmful?(per_ref_labels), "harmful_marked")
        |> maybe_add(per_ref_disagrees?(per_ref_labels), "per_ref_relevance_disagreement")
        |> maybe_add(length(Enum.uniq(qualities)) > 1, "packet_relevance_quality_disagreement")
        |> maybe_add(
          secondary_needs_adjudication?(@working_context_metric, item_id, secondary_reviews),
          "secondary_review_needs_adjudication"
        )

      trigger_or_empty(@working_set_relevance_metric, item_id, reasons)
    end)
  end

  defp trigger_or_empty(_metric, _item_id, []), do: []

  defp trigger_or_empty(metric, item_id, reasons) do
    [%{"metric" => metric, "item_id" => item_id, "trigger_reasons" => reasons}]
  end

  defp unhandled_triggers(triggers, adjudication_records) do
    adjudicated_keys =
      adjudication_records
      |> Enum.map(&{&1["metric"], &1["item_id"]})
      |> MapSet.new()

    Enum.reject(triggers, fn trigger ->
      MapSet.member?(adjudicated_keys, {trigger["metric"], trigger["item_id"]})
    end)
  end

  defp needs_review_count(evidence_labels, working_labels) do
    evidence_count =
      Enum.count(evidence_labels, &(&1["raw_label_0_to_4_or_needs_review"] == "needs_review"))

    working_count =
      Enum.count(working_labels, fn label ->
        omission = map_field(label, "omission")
        per_ref = list_field(label, "per_ref_relevance_labels")

        omission_needs_review?(omission) or per_ref_needs_review?([per_ref]) or
          label["packet_relevance_quality"] == "needs_review"
      end)

    evidence_count + working_count
  end

  defp maybe_add(reasons, true, reason), do: [reason | reasons]
  defp maybe_add(reasons, _condition, _reason), do: reasons

  defp pairwise_difference_at_least?(values, threshold) do
    values != [] and Enum.max(values) - Enum.min(values) >= threshold
  end

  defp acceptability_boundary_split?(values) do
    Enum.any?(values, &(&1 <= 2)) and Enum.any?(values, &(&1 >= 3))
  end

  defp omission_needs_review?(omission) do
    omission["omission_severity"] == "needs_review" or
      omission["critical_omission"] == "needs_review"
  end

  defp set_field_disagrees?(maps, field) do
    maps
    |> Enum.map(fn map -> map |> list_field(field) |> Enum.sort() end)
    |> Enum.uniq()
    |> length()
    |> Kernel.>(1)
  end

  defp scalar_field_disagrees?(maps, field) do
    maps
    |> Enum.map(& &1[field])
    |> Enum.uniq()
    |> length()
    |> Kernel.>(1)
  end

  defp per_ref_needs_review?(per_ref_label_sets) do
    Enum.any?(per_ref_label_sets, fn labels ->
      Enum.any?(labels, &(&1["relevance_label"] == "needs_review"))
    end)
  end

  defp per_ref_harmful?(per_ref_label_sets) do
    Enum.any?(per_ref_label_sets, fn labels ->
      Enum.any?(labels, &(&1["relevance_label"] == "harmful"))
    end)
  end

  defp per_ref_disagrees?(per_ref_label_sets) do
    per_ref_label_sets
    |> Enum.map(fn labels ->
      labels
      |> Enum.map(&{&1["ref_id"], &1["relevance_label"]})
      |> Enum.sort()
    end)
    |> Enum.uniq()
    |> length()
    |> Kernel.>(1)
  end

  defp secondary_needs_adjudication?(metric, item_id, secondary_reviews) do
    Enum.any?(secondary_reviews, fn review ->
      review["metric"] == metric and review["item_id"] == item_id and
        review["review_result"] == "needs_adjudication"
    end)
  end

  def item_reference_index(evidence_items, working_set_items) do
    evidence_refs =
      evidence_items
      |> Map.new(fn item -> {item["packet_id"], evidence_reference_ids(item)} end)

    working_refs =
      working_set_items
      |> Map.new(fn item -> {item["packet_id"], working_set_reference_ids(item)} end)

    Map.merge(evidence_refs, working_refs)
  end

  def candidate_ref_index(working_set_items) do
    working_set_items
    |> Map.new(fn item ->
      refs =
        item
        |> Map.get("candidate_ref_inventory", [])
        |> Enum.map(& &1["ref_id"])
        |> Enum.filter(&present?/1)
        |> MapSet.new()

      {item["packet_id"], refs}
    end)
  end

  defp evidence_reference_ids(item) do
    [
      item["packet_id"],
      item["task_id"],
      item["task_packet_path"],
      item["source_artifact_dir"],
      get_in(item, ["evidence_packet", "evidence_id"]),
      get_in(item, ["evidence_packet", "episode_id"]),
      get_in(item, ["evidence_packet", "step_id"]),
      get_in(item, ["evidence_packet", "action_ref"]),
      get_in(item, ["verifier_output", "verifier_output_id"]),
      get_in(item, ["commit_or_reject_record", "episode_id"])
    ]
    |> Kernel.++(List.wrap(get_in(item, ["commit_or_reject_record", "evidence_refs"])))
    |> Kernel.++(List.wrap(get_in(item, ["commit_or_reject_record", "verifier_output_refs"])))
    |> Kernel.++(List.wrap(get_in(item, ["commit_or_reject_record", "state_hashes"])))
    |> known_ref_set()
  end

  defp working_set_reference_ids(item) do
    item
    |> Map.get("candidate_ref_inventory", [])
    |> Enum.map(& &1["ref_id"])
    |> Kernel.++(List.wrap(item["selected_ref_ids"]))
    |> Kernel.++([
      item["packet_id"],
      item["task_id"],
      item["context_artifact_id"],
      item["task_packet_path"],
      item["source_artifact_dir"]
    ])
    |> known_ref_set()
  end

  defp known_ref_set(values) do
    values
    |> Enum.filter(&present?/1)
    |> MapSet.new()
  end

  defp item_ids_for_secondary_metric(@evidence_metric, packet), do: packet.evidence_ids
  defp item_ids_for_secondary_metric(@working_context_metric, packet), do: packet.working_set_ids
  defp item_ids_for_secondary_metric(_metric, _packet), do: MapSet.new()

  defp item_ids_for_policy_metric(@evidence_metric, packet), do: packet.evidence_ids
  defp item_ids_for_policy_metric(@context_omission_metric, packet), do: packet.working_set_ids

  defp item_ids_for_policy_metric(@working_set_relevance_metric, packet),
    do: packet.working_set_ids

  defp item_ids_for_policy_metric(_metric, _packet), do: MapSet.new()

  defp map_field(map, field) when is_map(map) do
    case map[field] do
      value when is_map(value) -> value
      _other -> %{}
    end
  end

  defp map_field(_value, _field), do: %{}

  defp list_field(map, field) when is_map(map) do
    case map[field] do
      value when is_list(value) -> value
      _other -> []
    end
  end

  defp list_field(_value, _field), do: []

  defp require_map(errors, label, value) do
    if is_map(value), do: errors, else: ["#{label} must be an object" | errors]
  end

  defp require_list(errors, label, value) do
    if is_list(value), do: errors, else: ["#{label} must be a list" | errors]
  end

  defp require_empty(errors, label, value) do
    if value == [],
      do: errors,
      else: ["#{label} must be empty while status is Not yet run" | errors]
  end

  defp require_equal(errors, label, actual, expected) do
    if actual == expected do
      errors
    else
      ["#{label} is #{inspect(actual)}, expected #{inspect(expected)}" | errors]
    end
  end

  defp require_in(errors, label, actual, allowed) do
    if actual in allowed do
      errors
    else
      ["#{label} is #{inspect(actual)}, expected one of #{inspect(allowed)}" | errors]
    end
  end

  defp require_count(errors, label, value, expected_count) when is_list(value) do
    if length(value) == expected_count do
      errors
    else
      ["#{label} count is #{length(value)}, expected #{expected_count}" | errors]
    end
  end

  defp require_known_id(errors, label, value, allowed_ids) do
    if present?(value) and MapSet.member?(allowed_ids, value) do
      errors
    else
      ["#{label} is #{inspect(value)}, expected a referenced packet item ID" | errors]
    end
  end

  defp require_reviewer_id(errors, label, value) do
    cond do
      not is_binary(value) ->
        ["#{label} must be a stable reviewer ID string" | errors]

      value == @not_yet_run or String.trim(value) == "" ->
        ["#{label} must not be #{inspect(@not_yet_run)} or blank" | errors]

      not Regex.match?(~r/^[A-Za-z0-9_.:-]+$/, value) ->
        [
          "#{label} must use a stable anonymized ID with letters, digits, dot, underscore, colon, or dash"
          | errors
        ]

      true ->
        errors
    end
  end

  defp require_distinct_reviewers(errors, context, primary, secondary) do
    if is_binary(primary) and is_binary(secondary) and primary == secondary do
      ["#{context} primary and secondary reviewer IDs must differ" | errors]
    else
      errors
    end
  end

  defp require_evidence_raw_label(errors, label, value) do
    if value == "needs_review" or (is_integer(value) and value >= 0 and value <= 4) do
      errors
    else
      ["#{label} must be an integer 0-4 or needs_review" | errors]
    end
  end

  defp require_confidence(errors, label, value) do
    if is_number(value) and value >= 0.0 and value <= 1.0 do
      errors
    else
      ["#{label} must be a number between 0.0 and 1.0" | errors]
    end
  end

  defp require_string(errors, label, value) do
    cond do
      not is_binary(value) ->
        ["#{label} must be a non-empty string" | errors]

      value == @not_yet_run or String.trim(value) == "" ->
        ["#{label} must not be #{inspect(@not_yet_run)} or blank" | errors]

      true ->
        errors
    end
  end

  defp require_boolean(errors, label, value) do
    if is_boolean(value), do: errors, else: ["#{label} must be true or false" | errors]
  end

  defp require_ref_id_list(errors, label, value, known_refs) do
    errors = require_list(errors, label, value)
    refs = if is_list(value), do: value, else: []

    unknown =
      refs
      |> Enum.reject(&MapSet.member?(known_refs, &1))
      |> Enum.sort()

    cond do
      Enum.any?(refs, &(not is_binary(&1))) ->
        ["#{label} must contain only string ref IDs" | errors]

      unknown != [] ->
        ["#{label} contains unknown ref IDs #{inspect(unknown)}" | errors]

      true ->
        errors
    end
  end

  defp require_non_empty_string_list(errors, label, value) do
    errors = require_list(errors, label, value)
    values = if is_list(value), do: value, else: []

    cond do
      values == [] ->
        ["#{label} must not be empty" | errors]

      Enum.any?(values, &(not is_binary(&1) or String.trim(&1) == "")) ->
        ["#{label} must contain only non-empty strings" | errors]

      true ->
        errors
    end
  end

  defp require_referenced_artifacts(errors, label, value, known_refs) do
    errors = require_non_empty_string_list(errors, label, value)
    refs = if is_list(value), do: value, else: []

    unknown =
      refs
      |> Enum.reject(&MapSet.member?(known_refs, &1))
      |> Enum.sort()

    if unknown == [] do
      errors
    else
      ["#{label} contains unknown artifact IDs #{inspect(unknown)}" | errors]
    end
  end

  defp require_allowed_keys(errors, context, value, allowed_keys) when is_map(value) do
    allowed = MapSet.new(allowed_keys)
    unknown = Map.keys(value) |> Enum.reject(&MapSet.member?(allowed, &1))
    add_unknown_key_errors(errors, context, unknown)
  end

  defp require_allowed_keys(errors, _context, _value, _allowed_keys), do: errors

  defp add_unknown_key_errors(errors, _context, []), do: errors

  defp add_unknown_key_errors(errors, context, unknown_keys) do
    ["#{context} has unsupported keys #{inspect(Enum.sort(unknown_keys))}" | errors]
  end

  defp add_list_error(errors, _message, []), do: errors
  defp add_list_error(errors, message, values), do: ["#{message}: #{inspect(values)}" | errors]

  defp require_full_coverage(errors, status, coverage) do
    coverage
    |> Enum.reduce(errors, fn {metric, metric_coverage}, errors ->
      if metric_coverage["missing_item_ids"] == [] do
        errors
      else
        [
          "#{status} requires full review coverage for #{metric}; missing #{inspect(metric_coverage["missing_item_ids"])}"
          | errors
        ]
      end
    end)
  end

  defp require_empty_unhandled_triggers(errors, _status, []), do: errors

  defp require_empty_unhandled_triggers(errors, status, unhandled_triggers) do
    [
      "#{status} requires adjudication records for triggered items: #{inspect(unhandled_triggers)}"
      | errors
    ]
  end

  defp score_4dp(_numerator, 0), do: @not_yet_run

  defp score_4dp(numerator, denominator) do
    :erlang.float_to_binary(numerator / denominator, decimals: 4)
  end

  defp parse_int(value) when is_integer(value), do: value

  defp parse_int(value) do
    case Integer.parse(to_string(value)) do
      {integer, ""} -> integer
      _other -> value
    end
  end
end
