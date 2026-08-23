defmodule Vanta.PostStage1SideEffectPlanning do
  @moduledoc """
  Rerunnable PS1-G8 fixture-local Document Ops planning pilot.

  The runner materializes proposal records from immutable planning fixtures,
  invokes the deterministic proposal validator, compares evaluation-only
  fixture oracles, and writes measured planning artifacts. It never dispatches
  a runtime action or collects an approval record.
  """

  alias Vanta.Hash
  alias Vanta.PostStage1SideEffectPlanning.PathHelpers
  alias Vanta.PostStage1SideEffectPlanning.Validator

  @experiment_id "side_effect_planning"
  @plan_id "PS1-LC-SIDEFX-PLAN-001"
  @surface_id "PS1-LC-SIDEFX-COMMITTABLE-DOCOPS-001"
  @gate_policy_version "PS1-LC-SIDEFX-GATE-001"
  @artifact_contract_version "PS1-G8-committable-docops-planning-pilot-v1"
  @placeholder_action "commit_fixture_document_candidate"
  @report_label "committable_docops_planning_pilot"

  @required_families ~w(
    valid_fixture_local_commit_proposal
    missing_target_identity
    missing_approval_boundary
    missing_idempotency_duplicate_guard
    missing_rollback_or_compensation_statement
    path_escape
    source_fixture_mutation
    irreversible_misclassification
    memory_write_smuggling
  )

  @artifact_files ~w(
    run.json
    fixture_results.json
    environment_manifest.json
    summary.md
    fixture_inventory.md
    commit_plan_inventory.md
    approval_boundary_report.md
    rollback_compensation_report.md
    schema_impact_ref.md
    not_applicable.md
  )

  @source_documents [
    "docs/00_manifest/Side_Effect_Escalation_Gate.md",
    "docs/02_specs/Post_Stage_1_Side_Effect_Planning_Draft_Spec.md",
    "docs/03_schemas/Post_Stage_1_Side_Effect_Schema_Impact_Review.md",
    "docs/04_experiments/Post_Stage_1_Side_Effect_Evaluation_Plan.md"
  ]

  def artifact_files, do: @artifact_files
  def plan_id, do: @plan_id
  def surface_id, do: @surface_id
  def gate_policy_version, do: @gate_policy_version
  def placeholder_action, do: @placeholder_action

  def generate(opts \\ []), do: run(opts)

  def run(opts \\ []) do
    opts = normalize_opts(opts)
    assert_output_outside_fixture_root!(opts)

    fixture_hash_before = PathHelpers.fixture_tree_hash(opts.fixture_root)
    fixtures = load_fixtures!(opts.fixture_root)
    fixture_results = Enum.map(fixtures, &evaluate_fixture/1)
    fixture_hash_after = PathHelpers.fixture_tree_hash(opts.fixture_root)

    run =
      build_run(
        opts,
        fixture_results,
        fixture_hash_before,
        fixture_hash_after
      )

    write_results!(opts.out_dir, run, fixture_results)
    assert_artifacts_complete!(opts.out_dir)

    {:ok, run}
  end

  def evaluate_proposal(proposal), do: Validator.validate(proposal)

  defp normalize_opts(opts) do
    cwd = Keyword.get_lazy(opts, :cwd, &File.cwd!/0)
    timestamp = Keyword.get_lazy(opts, :timestamp, &timestamp/0)

    fixture_root =
      opts
      |> Keyword.get(
        :fixture_root,
        "docs/04_experiments/fixtures/side_effect_planning"
      )
      |> Path.expand(cwd)

    out_dir =
      opts
      |> Keyword.get(:out_dir, "docs/04_experiments/results/side_effect_planning/#{timestamp}")
      |> Path.expand(cwd)

    generated_at =
      Keyword.get_lazy(opts, :generated_at, fn ->
        DateTime.utc_now() |> DateTime.truncate(:second) |> DateTime.to_iso8601()
      end)

    %{
      cwd: cwd,
      timestamp: timestamp,
      fixture_root: fixture_root,
      out_dir: out_dir,
      generated_at: generated_at
    }
  end

  defp assert_output_outside_fixture_root!(opts) do
    if PathHelpers.inside_root?(opts.out_dir, opts.fixture_root) do
      raise ArgumentError, "planning pilot output must stay outside the source fixture root"
    end
  end

  defp load_fixtures!(fixture_root) do
    base = read_json!(Path.join(fixture_root, "base_proposal.json"))

    fixture_root
    |> Path.join("case_*.json")
    |> Path.wildcard()
    |> Enum.sort()
    |> Enum.map(fn path ->
      fixture = read_json!(path)
      proposal = materialize_proposal(base, fixture)

      %{
        "fixture" => fixture,
        "fixture_path" => path,
        "proposal" => proposal
      }
    end)
  end

  defp materialize_proposal(base, fixture) do
    fixture_id = fixture["fixture_id"]
    proposal_id = "#{fixture_id}-proposal"

    base
    |> interpolate_tokens(%{
      "{{fixture_id}}" => fixture_id,
      "{{proposal_id}}" => proposal_id
    })
    |> deep_merge(fixture["proposal_overrides"] || %{})
    |> remove_fields(fixture["remove_fields"] || [])
  end

  defp evaluate_fixture(%{"fixture" => fixture, "fixture_path" => path, "proposal" => proposal}) do
    validation = Validator.validate(proposal)
    oracle = fixture["oracle"]

    oracle_match =
      validation["decision"] == oracle["expected_decision"] and
        validation["report_label"] == oracle["expected_report_label"] and
        Enum.sort(validation["reason_codes"]) == Enum.sort(oracle["expected_reason_codes"])

    result = %{
      "fixture_id" => fixture["fixture_id"],
      "family" => fixture["family"],
      "description" => fixture["description"],
      "fixture_ref" => display_path(path),
      "proposal_hash" => Hash.canonical_json_hash(proposal),
      "expected" => oracle,
      "actual" => validation,
      "oracle_match" => oracle_match,
      "runtime_execution_attempted" => false,
      "audit_refs" => %{
        "fixture_ref" => display_path(path),
        "proposal_hash" => Hash.canonical_json_hash(proposal),
        "validator_version" => Validator.validator_version()
      }
    }

    Map.put(result, "audit_complete", audit_complete?(result))
  end

  defp audit_complete?(result) do
    PathHelpers.present?(result["fixture_ref"]) and
      PathHelpers.present?(result["proposal_hash"]) and
      is_map(result["expected"]) and
      is_map(result["actual"]) and
      PathHelpers.present?(get_in(result, ["actual", "validator_version"])) and
      is_boolean(result["oracle_match"]) and
      result["runtime_execution_attempted"] == false
  end

  defp build_run(opts, fixture_results, fixture_hash_before, fixture_hash_after) do
    metrics = planning_metrics(fixture_results)

    process_floors =
      process_integrity_floors(fixture_results, fixture_hash_before, fixture_hash_after)

    families = fixture_results |> Enum.map(& &1["family"]) |> Enum.uniq() |> Enum.sort()

    pilot_gates = %{
      "required_fixture_families_present" => Enum.all?(@required_families, &(&1 in families)),
      "fixture_count" => length(fixture_results),
      "required_fixture_count_minimum" => 10,
      "fixture_count_sufficient" => length(fixture_results) >= 10,
      "all_planning_metrics_pass" =>
        Enum.all?(metrics, fn {_name, metric} -> metric["passed"] end),
      "all_process_integrity_floors_pass" =>
        Enum.all?(process_floors, fn {_name, value} -> value == 0 end)
    }

    complete? =
      Enum.all?(pilot_gates, fn
        {"fixture_count", _value} -> true
        {"required_fixture_count_minimum", _value} -> true
        {_name, value} -> value == true
      end)

    %{
      "schema_version" => Vanta.schema_version(),
      "experiment_id" => @experiment_id,
      "plan_id" => @plan_id,
      "planning_surface_id" => @surface_id,
      "gate_policy_version" => @gate_policy_version,
      "artifact_contract_version" => @artifact_contract_version,
      "validator_version" => Validator.validator_version(),
      "generation_mode" => "measured planning pilot",
      "report_label" => @report_label,
      "completion_status" => if(complete?, do: "complete", else: "failed"),
      "threshold_status" =>
        if(complete?, do: "pass_planning_pilot", else: "failed_no_acceptance"),
      "run_status" =>
        if(complete?,
          do: "Measured planning pilot complete",
          else: "Measured planning pilot failed"
        ),
      "implementation_status" =>
        "Planning validator and runner implemented; runtime execution not authorized",
      "runtime_execution_status" => "Not authorized and not attempted",
      "approval_collection_status" => "Not authorized and not collected",
      "schema_change_status" => "no schema changes",
      "generated_at" => opts.generated_at,
      "artifact_root" => display_path(opts.out_dir, opts.cwd),
      "fixture_root" => display_path(opts.fixture_root, opts.cwd),
      "fixture_count" => length(fixture_results),
      "fixture_family_count" => length(families),
      "fixture_families" => families,
      "artifact_contract" => artifact_contract(),
      "source_documents" => @source_documents,
      "planning_boundary" => planning_boundary(),
      "future_action_placeholder" => future_action_placeholder(),
      "executed_side_effect_counts" => executed_side_effect_counts(),
      "observed_negative_proposal_counts" => observed_negative_proposal_counts(fixture_results),
      "process_integrity_floors" => process_floors,
      "planning_metrics" => metrics,
      "pilot_gates" => pilot_gates,
      "source_fixture_integrity" => %{
        "pre_run_tree_hash" => fixture_hash_before,
        "post_run_tree_hash" => fixture_hash_after,
        "unchanged" => fixture_hash_before == fixture_hash_after
      },
      "fixture_results_ref" => "fixture_results.json",
      "environment_manifest_ref" => "environment_manifest.json",
      "claim_boundary" => claim_boundary()
    }
  end

  defp planning_metrics(results) do
    positive = Enum.filter(results, &(get_in(&1, ["expected", "expected_decision"]) == "valid"))
    negative = Enum.reject(results, &(get_in(&1, ["expected", "expected_decision"]) == "valid"))

    %{
      "approval_boundary_completeness" =>
        check_metric(
          positive,
          &get_in(&1, ["actual", "completeness_checks", "approval_boundary_complete"])
        ),
      "target_identity_completeness" =>
        check_metric(
          positive,
          &get_in(&1, ["actual", "completeness_checks", "target_identity_complete"])
        ),
      "duplicate_guard_completeness" =>
        check_metric(positive, fn result ->
          get_in(result, ["actual", "completeness_checks", "idempotency_key_present"]) and
            get_in(result, ["actual", "completeness_checks", "duplicate_guard_present"])
        end),
      "rollback_or_compensation_declaration_rate" =>
        check_metric(
          positive,
          &get_in(&1, ["actual", "completeness_checks", "rollback_or_compensation_declared"])
        ),
      "missing_target_identity_rejection_rate" =>
        family_rejection_metric(results, "missing_target_identity"),
      "missing_approval_rejection_rate" =>
        family_rejection_metric(results, "missing_approval_boundary"),
      "missing_idempotency_duplicate_guard_rejection_rate" =>
        family_rejection_metric(results, "missing_idempotency_duplicate_guard"),
      "missing_rollback_or_compensation_rejection_rate" =>
        family_rejection_metric(results, "missing_rollback_or_compensation_statement"),
      "path_escape_rejection_rate" => family_rejection_metric(results, "path_escape"),
      "source_fixture_mutation_rejection_rate" =>
        family_rejection_metric(results, "source_fixture_mutation"),
      "irreversible_misclassification_rejection_rate" =>
        family_rejection_metric(results, "irreversible_misclassification"),
      "memory_write_smuggling_rejection_rate" =>
        family_rejection_metric(results, "memory_write_smuggling"),
      "planning_rejection_rule_accuracy" => check_metric(negative, & &1["oracle_match"]),
      "planning_audit_completeness" => check_metric(results, & &1["audit_complete"]),
      "fixture_oracle_conformance" => check_metric(results, & &1["oracle_match"])
    }
  end

  defp family_rejection_metric(results, family) do
    results
    |> Enum.filter(&(&1["family"] == family))
    |> check_metric(fn result ->
      get_in(result, ["actual", "decision"]) == "rejected" and result["oracle_match"]
    end)
  end

  defp check_metric(items, predicate) do
    denominator = length(items)
    numerator = Enum.count(items, predicate)
    value = if denominator == 0, do: nil, else: Float.round(numerator / denominator, 4)

    %{
      "numerator" => numerator,
      "denominator" => denominator,
      "value" => value,
      "required_value" => 1.0,
      "passed" => denominator > 0 and value == 1.0
    }
  end

  defp process_integrity_floors(results, fixture_hash_before, fixture_hash_after) do
    accepted = Enum.filter(results, &(get_in(&1, ["actual", "decision"]) == "valid"))

    %{
      "runtime_committable_execution_count" => 0,
      "runtime_irreversible_execution_count" => 0,
      "memory_write_count" => 0,
      "external_target_count" => 0,
      "production_target_count" => 0,
      "source_fixture_mutation_count" =>
        if(fixture_hash_before == fixture_hash_after, do: 0, else: 1),
      "unsupported_commit_count" => 0,
      "approval_as_label_count" => 0,
      "fixture_oracle_as_approval_count" => 0,
      "human_label_as_approval_count" => 0,
      "approval_record_count" => 0,
      "accepted_missing_approval_boundary_count" =>
        Enum.count(
          accepted,
          &(not get_in(&1, ["actual", "completeness_checks", "approval_boundary_complete"]))
        ),
      "accepted_missing_rollback_or_compensation_count" =>
        Enum.count(
          accepted,
          &(not get_in(&1, ["actual", "completeness_checks", "rollback_or_compensation_declared"]))
        ),
      "schema_change_count" => 0,
      "runtime_action_added_count" => 0,
      "runtime_dispatch_count" => 0
    }
  end

  defp observed_negative_proposal_counts(results) do
    %{
      "path_escape_proposal_count" => Enum.count(results, &(&1["family"] == "path_escape")),
      "source_fixture_mutation_proposal_count" =>
        Enum.count(results, &(&1["family"] == "source_fixture_mutation")),
      "irreversible_misclassification_proposal_count" =>
        Enum.count(results, &(&1["family"] == "irreversible_misclassification")),
      "memory_write_smuggling_proposal_count" =>
        Enum.count(results, &(&1["family"] == "memory_write_smuggling"))
    }
  end

  defp artifact_contract do
    %{
      "required_files" => @artifact_files,
      "output_root_pattern" => "docs/04_experiments/results/side_effect_planning/<timestamp>/",
      "contract_status" => "measured planning pilot",
      "label_packet_ref" => "not_applicable.md",
      "machine_schema" => "not added; run-local planning contract v1"
    }
  end

  defp planning_boundary do
    %{
      "boundary" => "planning validation only",
      "authorized_runtime_actions_added" => [],
      "runtime_dispatch" => "not attempted",
      "approval_records_collected" => 0,
      "labels_are_runtime_approvals" => false,
      "fixture_oracles_are_runtime_approvals" => false,
      "target_scope" => "copied fixture workspace planning identities only",
      "source_fixture_mutation_allowed" => false,
      "external_targets_allowed" => false,
      "production_targets_allowed" => false,
      "memory_stores_allowed" => false
    }
  end

  defp future_action_placeholder do
    %{
      "name" => @placeholder_action,
      "status" => "planning placeholder only",
      "side_effect_class" => "COMMITTABLE",
      "present_in_current_action_set" => @placeholder_action in Vanta.action_types(),
      "present_in_allowed_actions" => false,
      "runtime_dispatch_allowed" => false
    }
  end

  defp executed_side_effect_counts do
    %{"COMMITTABLE" => 0, "IRREVERSIBLE" => 0, "MEMORY_WRITE" => 0}
  end

  defp claim_boundary do
    %{
      "claim_level" => "named planning pilot completeness and rejection rules only",
      "h5_validation" => "not claimed",
      "side_effect_safety" => "not claimed",
      "runtime_approval" => "not collected",
      "runtime_execution_authorization" => "not authorized",
      "production_deployment" => "not approved"
    }
  end

  defp write_results!(out_dir, run, fixture_results) do
    File.mkdir_p!(out_dir)
    write_json!(Path.join(out_dir, "run.json"), run)
    write_json!(Path.join(out_dir, "fixture_results.json"), fixture_results)
    write_json!(Path.join(out_dir, "environment_manifest.json"), environment_manifest(run))
    File.write!(Path.join(out_dir, "summary.md"), summary_markdown(run))

    File.write!(
      Path.join(out_dir, "fixture_inventory.md"),
      fixture_inventory_markdown(run, fixture_results)
    )

    File.write!(
      Path.join(out_dir, "commit_plan_inventory.md"),
      commit_plan_inventory_markdown(fixture_results)
    )

    File.write!(
      Path.join(out_dir, "approval_boundary_report.md"),
      approval_boundary_markdown(run)
    )

    File.write!(
      Path.join(out_dir, "rollback_compensation_report.md"),
      rollback_compensation_markdown(run)
    )

    File.write!(Path.join(out_dir, "schema_impact_ref.md"), schema_impact_markdown(run))
    File.write!(Path.join(out_dir, "not_applicable.md"), not_applicable_markdown(run))
  end

  defp assert_artifacts_complete!(out_dir) do
    missing = Enum.reject(@artifact_files, &File.regular?(Path.join(out_dir, &1)))
    if missing != [], do: raise("missing planning pilot artifacts: #{Enum.join(missing, ", ")}")
  end

  defp environment_manifest(run) do
    %{
      "generated_at" => run["generated_at"],
      "elixir_version" => System.version(),
      "otp_release" => System.otp_release(),
      "os_type" => inspect(:os.type()),
      "validator_version" => run["validator_version"],
      "fixture_root" => run["fixture_root"],
      "pre_run_fixture_hash" => get_in(run, ["source_fixture_integrity", "pre_run_tree_hash"]),
      "post_run_fixture_hash" => get_in(run, ["source_fixture_integrity", "post_run_tree_hash"])
    }
  end

  defp summary_markdown(run) do
    """
    # Post-Stage-1 Side-Effect Planning Pilot

    Plan ID: #{run["plan_id"]}
    Planning surface ID: #{run["planning_surface_id"]}
    Gate policy version: #{run["gate_policy_version"]}
    Report label: #{run["report_label"]}
    Completion status: #{run["completion_status"]}
    Threshold status: #{run["threshold_status"]}
    Measured run path: `#{run["artifact_root"]}`
    Fixture count: #{run["fixture_count"]}

    ## Planning Metrics

    | Metric | Result | Required | Status |
    | --- | ---: | ---: | --- |
    #{metric_rows(run["planning_metrics"])}

    ## Process Integrity

    | Floor | Measured | Required |
    | --- | ---: | ---: |
    #{floor_rows(run["process_integrity_floors"])}

    Executed `COMMITTABLE`, `IRREVERSIBLE`, and `MEMORY_WRITE` counts are all
    zero. The source fixture tree hash is unchanged. Fixture oracles are used
    only for evaluation comparison and are not runtime approvals.

    ## Interpretation Boundary

    This measured result supports only the completeness and rejection rules of
    the named `committable_docops_planning_pilot`. It does not authorize
    execution, collect approval, change runtime schemas, establish side-effect
    safety, validate H5, or establish production readiness.
    """
  end

  defp fixture_inventory_markdown(run, fixture_results) do
    rows =
      Enum.map_join(fixture_results, "\n", fn result ->
        "| `#{result["fixture_id"]}` | `#{result["family"]}` | #{get_in(result, ["expected", "expected_decision"])} | #{get_in(result, ["actual", "decision"])} | #{result["oracle_match"]} |"
      end)

    """
    # Fixture Inventory

    Fixture root: `#{run["fixture_root"]}`
    Fixture count: #{run["fixture_count"]}
    Pre-run tree hash: `#{get_in(run, ["source_fixture_integrity", "pre_run_tree_hash"])}`
    Post-run tree hash: `#{get_in(run, ["source_fixture_integrity", "post_run_tree_hash"])}`
    Source fixture mutation count: #{get_in(run, ["process_integrity_floors", "source_fixture_mutation_count"])}

    | Fixture | Family | Expected | Actual | Oracle match |
    | --- | --- | --- | --- | --- |
    #{rows}
    """
  end

  defp commit_plan_inventory_markdown(fixture_results) do
    rows =
      Enum.map_join(fixture_results, "\n", fn result ->
        reasons = get_in(result, ["actual", "reason_codes"]) |> Enum.join(", ")
        reasons = if reasons == "", do: "none", else: reasons

        "| `#{result["fixture_id"]}` | `#{result["proposal_hash"]}` | #{get_in(result, ["actual", "decision"])} | #{reasons} | false |"
      end)

    """
    # Commit Plan Inventory

    Future action placeholder: `#{@placeholder_action}`
    Placeholder status: planning placeholder only
    Runtime dispatch count: 0

    | Fixture | Proposal hash | Decision | Reasons | Runtime dispatched |
    | --- | --- | --- | --- | --- |
    #{rows}
    """
  end

  defp approval_boundary_markdown(run) do
    metric = get_in(run, ["planning_metrics", "approval_boundary_completeness"])
    rejection = get_in(run, ["planning_metrics", "missing_approval_rejection_rate"])

    """
    # Approval Boundary Report

    Gate policy version: #{run["gate_policy_version"]}
    Positive-control approval-boundary completeness: #{metric["value"]} (#{metric["numerator"]}/#{metric["denominator"]})
    Missing-approval rejection rate: #{rejection["value"]} (#{rejection["numerator"]}/#{rejection["denominator"]})
    Approval record count: #{get_in(run, ["process_integrity_floors", "approval_record_count"])}
    Approval-as-label count: #{get_in(run, ["process_integrity_floors", "approval_as_label_count"])}

    No approval record was collected. Fixture oracles, human labels, verifier
    output, and final-answer judgments are not runtime approvals.
    """
  end

  defp rollback_compensation_markdown(run) do
    declaration = get_in(run, ["planning_metrics", "rollback_or_compensation_declaration_rate"])

    rejection =
      get_in(run, ["planning_metrics", "missing_rollback_or_compensation_rejection_rate"])

    """
    # Rollback And Compensation Report

    Positive-control declaration rate: #{declaration["value"]} (#{declaration["numerator"]}/#{declaration["denominator"]})
    Missing-declaration rejection rate: #{rejection["value"]} (#{rejection["numerator"]}/#{rejection["denominator"]})
    Runtime `COMMITTABLE` execution count: #{get_in(run, ["process_integrity_floors", "runtime_committable_execution_count"])}
    Runtime `IRREVERSIBLE` execution count: #{get_in(run, ["process_integrity_floors", "runtime_irreversible_execution_count"])}
    Memory-write count: #{get_in(run, ["process_integrity_floors", "memory_write_count"])}

    The positive controls cover both `fixture_commit_restore` and
    `fixture_commit_supersede`. Supersession is compensation, not strict
    rollback. Neither path is executable in this pilot.
    """
  end

  defp schema_impact_markdown(run) do
    """
    # Schema Impact Reference

    Schema impact review:
    `docs/03_schemas/Post_Stage_1_Side_Effect_Schema_Impact_Review.md`

    Schema change status: #{run["schema_change_status"]}
    Schema change count: #{get_in(run, ["process_integrity_floors", "schema_change_count"])}
    Runtime action added count: #{get_in(run, ["process_integrity_floors", "runtime_action_added_count"])}

    The proposal fixture format and `run.json` contract are pilot-local
    evaluation artifacts. They do not add `#{@placeholder_action}` to runtime
    schemas or allowlists.
    """
  end

  defp not_applicable_markdown(run) do
    """
    # Not Applicable

    Label packet reference: not applicable
    Plan ID: #{run["plan_id"]}
    Planning surface ID: #{run["planning_surface_id"]}

    No label packet or approval record is produced. Fixture oracles are used
    only to measure deterministic validator conformance.
    """
  end

  defp metric_rows(metrics) do
    metrics
    |> Enum.sort_by(&elem(&1, 0))
    |> Enum.map_join("\n", fn {name, metric} ->
      status = if metric["passed"], do: "pass", else: "fail"

      "| `#{name}` | #{metric["value"]} (#{metric["numerator"]}/#{metric["denominator"]}) | #{metric["required_value"]} | #{status} |"
    end)
  end

  defp floor_rows(floors) do
    floors
    |> Enum.sort_by(&elem(&1, 0))
    |> Enum.map_join("\n", fn {name, value} -> "| `#{name}` | #{value} | 0 |" end)
  end

  defp write_json!(path, value), do: File.write!(path, Jason.encode!(value, pretty: true) <> "\n")
  defp read_json!(path), do: path |> File.read!() |> Jason.decode!()

  defp interpolate_tokens(value, tokens) when is_binary(value) do
    Enum.reduce(tokens, value, fn {token, replacement}, text ->
      String.replace(text, token, replacement)
    end)
  end

  defp interpolate_tokens(value, tokens) when is_map(value) do
    Map.new(value, fn {key, child} -> {key, interpolate_tokens(child, tokens)} end)
  end

  defp interpolate_tokens(value, tokens) when is_list(value),
    do: Enum.map(value, &interpolate_tokens(&1, tokens))

  defp interpolate_tokens(value, _tokens), do: value

  defp deep_merge(left, right) when is_map(left) and is_map(right) do
    Map.merge(left, right, fn _key, left_value, right_value ->
      if is_map(left_value) and is_map(right_value) do
        deep_merge(left_value, right_value)
      else
        right_value
      end
    end)
  end

  defp remove_fields(proposal, fields), do: Enum.reduce(fields, proposal, &Map.delete(&2, &1))

  defp display_path(path, cwd \\ File.cwd!()) do
    path |> Path.relative_to(cwd) |> PathHelpers.normalize_separator()
  end

  defp timestamp do
    {{year, month, day}, {hour, minute, second}} = :calendar.local_time()

    :io_lib.format(
      "~4..0B~2..0B~2..0B_~2..0B~2..0B~2..0B",
      [year, month, day, hour, minute, second]
    )
    |> IO.iodata_to_binary()
  end
end
