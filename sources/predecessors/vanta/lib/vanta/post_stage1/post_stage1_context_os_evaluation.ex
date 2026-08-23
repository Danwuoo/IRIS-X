defmodule Vanta.PostStage1ContextOSEvaluation do
  @moduledoc """
  Deterministic, artifact-backed PS1-G7 Context OS evaluation pilot.

  The evaluator reads the accepted Lane A run, active frozen Lane B packet,
  coordinator-only post-freeze mapping memo, and fixed policy artifacts. It
  reconstructs only the existing bounded raw-trace and Working Set Compiler v0
  context artifacts for comparison. It never calls a model, reruns OpenClaw,
  dispatches a runtime action, changes selection behavior, or creates Context OS
  implementation authority.
  """

  alias Vanta.Hash
  alias Vanta.PostStage1ContextOSEvaluation.{PathHelpers, Validator}

  @artifact_files ~w(
    run.json
    summary.md
    fixture_inventory.md
    context_artifact_inventory.md
    label_packet_ref.md
  )

  @source_run_id "20260601_113121"
  @plan_id "PS1-LC-CTX-PLAN-001"
  @gate_policy "PS1-LC-CTX-GATE-001"
  @metric_policy "PS1-LA-METRIC-001"
  @label_policy "PS1-LB-LABEL-001"
  @evaluation_mode "artifact_backed_post_freeze_evaluation"

  def artifact_files, do: @artifact_files
  def plan_id, do: @plan_id

  def validate(opts \\ []) do
    config = normalize_opts(opts)

    with :ok <- ensure_active_packet(config),
         :ok <- ensure_sources(config),
         {:ok, sources} <- load_sources(config),
         {:ok, evidence} <- Validator.validate(config, sources) do
      {:ok, build_run(config, sources, evidence)}
    end
  end

  def run(opts \\ []) do
    with {:ok, run} <- validate(opts) do
      config = normalize_opts(opts)
      write_results!(config.out_dir, run)
      assert_artifacts_complete!(config.out_dir)
      {:ok, run}
    end
  end

  defp normalize_opts(opts) do
    cwd = Keyword.get_lazy(opts, :cwd, &File.cwd!/0)
    timestamp = Keyword.get_lazy(opts, :timestamp, &timestamp/0)

    source_run =
      expand(
        Keyword.get(
          opts,
          :source_run,
          "docs/04_experiments/results/post_stage_1_larger_sample/#{@source_run_id}/run.json"
        ),
        cwd
      )

    source_run_dir = Path.dirname(source_run)

    packet_dir =
      expand(
        Keyword.get(
          opts,
          :packet_dir,
          "docs/05_evaluation/label_packets/post_stage_1_lane_b_#{@source_run_id}"
        ),
        cwd
      )

    %{
      cwd: cwd,
      timestamp: timestamp,
      generated_at:
        Keyword.get_lazy(opts, :generated_at, fn ->
          DateTime.utc_now() |> DateTime.truncate(:second) |> DateTime.to_iso8601()
        end),
      out_dir:
        expand(
          Keyword.get(
            opts,
            :out_dir,
            "docs/04_experiments/results/context_os_planning/#{timestamp}"
          ),
          cwd
        ),
      source_run: source_run,
      source_summary:
        expand(Keyword.get(opts, :source_summary, Path.join(source_run_dir, "summary.md")), cwd),
      source_fixture_inventory:
        expand(
          Keyword.get(
            opts,
            :source_fixture_inventory,
            Path.join(source_run_dir, "fixture_inventory.md")
          ),
          cwd
        ),
      source_run_report:
        expand(
          Keyword.get(
            opts,
            :source_run_report,
            "docs/05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md"
          ),
          cwd
        ),
      source_closure:
        expand(
          Keyword.get(
            opts,
            :source_closure,
            "docs/00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md"
          ),
          cwd
        ),
      fixtures_root:
        expand(
          Keyword.get(opts, :fixtures_root, "docs/04_experiments/fixtures/document_ops"),
          cwd
        ),
      packet_dir: packet_dir,
      packet_manifest:
        expand(
          Keyword.get(opts, :packet_manifest, Path.join(packet_dir, "packet_manifest.json")),
          cwd
        ),
      packet_readme:
        expand(Keyword.get(opts, :packet_readme, Path.join(packet_dir, "README.md")), cwd),
      packet_freeze:
        expand(
          Keyword.get(
            opts,
            :packet_freeze,
            Path.join(packet_dir, "coordinator_primary_label_packet_freeze.json")
          ),
          cwd
        ),
      primary_label_results:
        expand(
          Keyword.get(
            opts,
            :primary_label_results,
            Path.join(packet_dir, "label_results_primary_filled.json")
          ),
          cwd
        ),
      import_summary:
        expand(
          Keyword.get(
            opts,
            :import_summary,
            Path.join(packet_dir, "label_results_import_summary.json")
          ),
          cwd
        ),
      evidence_items:
        expand(
          Keyword.get(
            opts,
            :evidence_items,
            Path.join(packet_dir, "evidence_sufficiency_items.jsonl")
          ),
          cwd
        ),
      working_set_items:
        expand(
          Keyword.get(
            opts,
            :working_set_items,
            Path.join(packet_dir, "working_set_context_items.jsonl")
          ),
          cwd
        ),
      redacted_task_packets:
        expand(
          Keyword.get(
            opts,
            :redacted_task_packets,
            Path.join(packet_dir, "redacted_task_packets")
          ),
          cwd
        ),
      label_results_template:
        expand(
          Keyword.get(
            opts,
            :label_results_template,
            Path.join(packet_dir, "label_results_template.json")
          ),
          cwd
        ),
      adjudication_placeholders:
        expand(
          Keyword.get(
            opts,
            :adjudication_placeholders,
            Path.join(packet_dir, "adjudication_placeholders.json")
          ),
          cwd
        ),
      memo:
        expand(
          Keyword.get(
            opts,
            :memo,
            Path.join(packet_dir, "coordinator_only_post_freeze_context_unblind_memo.md")
          ),
          cwd
        ),
      label_report:
        expand(
          Keyword.get(
            opts,
            :label_report,
            "docs/05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md"
          ),
          cwd
        ),
      attestation:
        expand(
          Keyword.get(
            opts,
            :attestation,
            "docs/04_experiments/context_os_planning_control_attestation.json"
          ),
          cwd
        ),
      adapter_source:
        expand(
          Keyword.get(
            opts,
            :adapter_source,
            "lib/vanta/adapters/open_claw_context_planner_adapter.ex"
          ),
          cwd
        ),
      evaluation_plan:
        expand(
          Keyword.get(
            opts,
            :evaluation_plan,
            "docs/04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md"
          ),
          cwd
        ),
      gate:
        expand(
          Keyword.get(opts, :gate, "docs/00_manifest/Context_OS_Expansion_Gate.md"),
          cwd
        ),
      metric_policy:
        expand(
          Keyword.get(opts, :metric_policy, "docs/05_evaluation/Post_Stage_1_Metric_Policy.md"),
          cwd
        ),
      label_policy:
        expand(
          Keyword.get(
            opts,
            :label_policy,
            "docs/05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md"
          ),
          cwd
        ),
      baseline_plan:
        expand(
          Keyword.get(opts, :baseline_plan, "docs/04_experiments/Baseline_Identity_Plan.md"),
          cwd
        ),
      working_set_schema:
        expand(
          Keyword.get(opts, :working_set_schema, "docs/03_schemas/working_set.schema.json"),
          cwd
        )
    }
  end

  defp ensure_active_packet(config) do
    if String.contains?(PathHelpers.normalize_separator(config.packet_dir), "20260530_141649") do
      {:error, ["superseded packet 20260530_141649 cannot be used as active Lane B source"]}
    else
      :ok
    end
  end

  defp ensure_sources(config) do
    files = source_file_paths(config)

    missing_files =
      files
      |> Enum.reject(&File.regular?/1)
      |> Enum.map(&"missing source artifact: #{PathHelpers.display_path(&1, config.cwd)}")

    missing_dirs =
      [config.packet_dir, config.fixtures_root, config.redacted_task_packets]
      |> Enum.reject(&File.dir?/1)
      |> Enum.map(&"missing source directory: #{PathHelpers.display_path(&1, config.cwd)}")

    fixture_files =
      Validator.expected_fixture_budgets()
      |> Map.keys()
      |> Enum.flat_map(fn fixture_id ->
        root = Path.join(config.fixtures_root, fixture_id)
        [Path.join(root, "task.json"), Path.join(root, "expected/working_set_acceptance.json")]
      end)
      |> Enum.reject(&File.regular?/1)
      |> Enum.map(
        &"missing long-context fixture artifact: #{PathHelpers.display_path(&1, config.cwd)}"
      )

    case missing_files ++ missing_dirs ++ fixture_files do
      [] -> :ok
      errors -> {:error, errors}
    end
  end

  defp load_sources(config) do
    with {:ok, run} <- PathHelpers.load_json(config.source_run),
         {:ok, attestation} <- PathHelpers.load_json(config.attestation),
         {:ok, packet_manifest} <- PathHelpers.load_json(config.packet_manifest),
         {:ok, packet_freeze} <- PathHelpers.load_json(config.packet_freeze),
         {:ok, primary_label_results} <- PathHelpers.load_json(config.primary_label_results),
         {:ok, import_summary} <- PathHelpers.load_json(config.import_summary),
         {:ok, label_results_template} <- PathHelpers.load_json(config.label_results_template),
         {:ok, evidence_items} <- PathHelpers.load_jsonl(config.evidence_items),
         {:ok, working_set_items} <- PathHelpers.load_jsonl(config.working_set_items),
         {:ok, redacted_task_packets} <-
           PathHelpers.load_json_directory(config.redacted_task_packets),
         {:ok, source_summary} <- File.read(config.source_summary),
         {:ok, source_fixture_inventory} <- File.read(config.source_fixture_inventory),
         {:ok, run_report} <- File.read(config.source_run_report),
         {:ok, closure} <- File.read(config.source_closure),
         {:ok, packet_readme} <- File.read(config.packet_readme),
         {:ok, memo} <- File.read(config.memo),
         {:ok, label_report} <- File.read(config.label_report),
         {:ok, adapter_source} <- File.read(config.adapter_source),
         {:ok, evaluation_plan} <- File.read(config.evaluation_plan),
         {:ok, gate} <- File.read(config.gate),
         {:ok, metric_policy} <- File.read(config.metric_policy),
         {:ok, label_policy} <- File.read(config.label_policy),
         {:ok, baseline_plan} <- File.read(config.baseline_plan),
         {:ok, working_set_schema_text} <- File.read(config.working_set_schema) do
      {:ok,
       %{
         cwd: config.cwd,
         run: run,
         attestation: attestation,
         packet_manifest: packet_manifest,
         packet_freeze: packet_freeze,
         primary_label_results: primary_label_results,
         import_summary: import_summary,
         label_results_template: label_results_template,
         evidence_items: evidence_items,
         working_set_items: working_set_items,
         redacted_task_packets: redacted_task_packets,
         evidence_items_path: config.evidence_items,
         working_set_items_path: config.working_set_items,
         source_summary: source_summary,
         source_fixture_inventory: source_fixture_inventory,
         run_report: run_report,
         closure: closure,
         packet_readme: packet_readme,
         memo: memo,
         label_report: label_report,
         adapter_source: adapter_source,
         evaluation_plan: evaluation_plan,
         gate: gate,
         metric_policy: metric_policy,
         label_policy: label_policy,
         baseline_plan: baseline_plan,
         working_set_schema_text: working_set_schema_text
       }}
    else
      {:error, errors} when is_list(errors) -> {:error, errors}
      {:error, reason} -> {:error, ["cannot load source artifact: #{inspect(reason)}"]}
    end
  end

  defp build_run(config, sources, evidence) do
    source_refs = source_artifact_refs(config)

    deterministic_core = %{
      "schema_version" => "PS1-G7-context-evaluation-pilot-v1",
      "experiment_id" => "context_os_planning_evaluation_pilot",
      "plan_id" => @plan_id,
      "gate_policy_version" => @gate_policy,
      "metric_policy_version" => @metric_policy,
      "label_policy_version" => @label_policy,
      "evaluation_mode" => @evaluation_mode,
      "report_label" => "context_evaluation_pilot",
      "source_run" => %{
        "run_id" => @source_run_id,
        "experiment_id" => sources.run["experiment_id"],
        "sample_frame" => sources.run["sample_frame_id"],
        "threshold_status" => sources.run["threshold_status"],
        "closure_status" => "accepted_by_closure",
        "run_ref" => PathHelpers.display_path(config.source_run, config.cwd),
        "closure_ref" => PathHelpers.display_path(config.source_closure, config.cwd),
        "original_model_run_reexecuted" => false
      },
      "controls" => evidence.controls,
      "source_artifact_refs" => source_refs,
      "lane_a_structural_fixture_oracle_evidence" => evidence.lane_a,
      "lane_b_human_label_evidence" => evidence.lane_b,
      "process_integrity_floors" => evidence.process_integrity_floors,
      "validation_errors" => [],
      "pilot_execution_counts" => %{
        "model_calls" => 0,
        "openclaw_measured_runs" => 0,
        "runtime_actions_dispatched" => 0,
        "memory_writes" => 0,
        "external_target_accesses" => 0,
        "irreversible_effects" => 0
      },
      "implementation_status" =>
        "evaluation tooling only; full Context OS implementation is not authorized",
      "full_context_os_experiment_status" => "Not yet run",
      "final_pilot_status" => "pass_artifact_backed_evaluation_pilot",
      "interpretation_boundaries" => evidence.interpretation_boundaries,
      "artifact_contract" => %{
        "required_files" => @artifact_files,
        "output_root_pattern" => "docs/04_experiments/results/context_os_planning/<timestamp>/"
      }
    }

    fingerprint = Hash.canonical_json_hash(deterministic_core)

    deterministic_core
    |> Map.put("evaluation_fingerprint", fingerprint)
    |> Map.put("generated_at", config.generated_at)
    |> Map.put("artifact_root", PathHelpers.display_path(config.out_dir, config.cwd))
    |> Map.put("completion_status", "complete")
  end

  defp source_artifact_refs(config) do
    file_refs =
      source_file_paths(config)
      |> Enum.map(&PathHelpers.source_ref(&1, config.cwd))

    tree_refs =
      [PathHelpers.tree_ref(config.redacted_task_packets, config.cwd)] ++
        (Validator.expected_fixture_budgets()
         |> Map.keys()
         |> Enum.sort()
         |> Enum.map(fn fixture_id ->
           config.fixtures_root
           |> Path.join(fixture_id)
           |> PathHelpers.tree_ref(config.cwd)
         end))

    (file_refs ++ tree_refs)
    |> Enum.sort_by(& &1["path"])
  end

  defp source_file_paths(config) do
    [
      config.source_run,
      config.source_summary,
      config.source_fixture_inventory,
      config.source_run_report,
      config.source_closure,
      config.packet_manifest,
      config.packet_readme,
      config.packet_freeze,
      config.primary_label_results,
      config.import_summary,
      config.evidence_items,
      config.working_set_items,
      config.label_results_template,
      config.adjudication_placeholders,
      config.memo,
      config.label_report,
      config.attestation,
      config.adapter_source,
      config.evaluation_plan,
      config.gate,
      config.metric_policy,
      config.label_policy,
      config.baseline_plan,
      config.working_set_schema
    ]
  end

  defp write_results!(out_dir, run) do
    File.mkdir_p!(out_dir)
    File.write!(Path.join(out_dir, "run.json"), Jason.encode!(run, pretty: true) <> "\n")
    File.write!(Path.join(out_dir, "summary.md"), summary_markdown(run))
    File.write!(Path.join(out_dir, "fixture_inventory.md"), fixture_inventory_markdown(run))

    File.write!(
      Path.join(out_dir, "context_artifact_inventory.md"),
      context_artifact_inventory_markdown(run)
    )

    File.write!(Path.join(out_dir, "label_packet_ref.md"), label_packet_ref_markdown(run))
  end

  defp assert_artifacts_complete!(out_dir) do
    missing = Enum.reject(@artifact_files, &File.regular?(Path.join(out_dir, &1)))
    if missing != [], do: raise("missing Context OS pilot artifacts: #{Enum.join(missing, ", ")}")
  end

  defp summary_markdown(run) do
    lane_a = run["lane_a_structural_fixture_oracle_evidence"]["metrics"]
    lane_b = run["lane_b_human_label_evidence"]

    """
    # PS1-G7 Artifact-Backed Context OS Evaluation Pilot

    Plan ID: `#{run["plan_id"]}`
    Gate policy: `#{run["gate_policy_version"]}`
    Evaluation mode: `#{run["evaluation_mode"]}`
    Final pilot status: `#{run["final_pilot_status"]}`
    Evaluation fingerprint: `#{run["evaluation_fingerprint"]}`
    Source Lane A run: `#{get_in(run, ["source_run", "run_id"])}` (`accepted_by_closure`)
    Model calls issued by this pilot: `0`
    OpenClaw measured runs issued by this pilot: `0`

    ## Fixed Controls

    - model: `#{get_in(run, ["controls", "model"])}`
    - harness: `#{get_in(run, ["controls", "harness"])}`
    - context planner adapter: `#{get_in(run, ["controls", "context_planner_adapter"])}`
    - OpenClaw agent: `#{get_in(run, ["controls", "openclaw_agent"])}` (post-hoc user-authorized coordinator attestation; not source-run-native metadata)
    - prompt / response budgets: `#{get_in(run, ["controls", "prompt_character_budget"])}` / `#{get_in(run, ["controls", "response_character_budget"])}` characters
    - response format: `#{get_in(run, ["controls", "response_format"])}`
    - action / recovery attempt limits: `#{get_in(run, ["controls", "action_attempt_limit"])}` / `#{get_in(run, ["controls", "recovery_attempt_limit"])}`
    - tool policy: `#{get_in(run, ["controls", "tool_policy"])}`
    - context budget: global `null` means `#{get_in(run, ["controls", "context_budget", "global_null_semantics"])}`; the complete map is in `run.json` and `fixture_inventory.md`

    ## Lane A Structural / Fixture-Oracle Evidence

    | Metric | Baseline | Treatment | Label source |
    | --- | ---: | ---: | --- |
    #{lane_a_metric_rows(lane_a, run["lane_a_structural_fixture_oracle_evidence"]["metric_label_sources"])}

    These Lane A values are automated structural or fixture-oracle evidence.
    They are not human-labeled evidence.

    ## Lane B Human-Label Evidence

    | Interpreted arm | Blinded arm | Omission | Relevance |
    | --- | --- | ---: | ---: |
    #{lane_b_rows(lane_b)}

    The packet is small, so raw counts are reported. Relevance must be read
    together with omission; empty or sparse context must not be treated as
    sufficient merely because selected-ref precision appears high.

    ## Claim Boundary

    This pilot validates the completeness and internal consistency of the named
    artifact-backed evaluation only. It is not a new model run, a full Context
    OS experiment, H3 validation, production readiness, runtime approval,
    runtime action authority, schema authority, memory authority, side-effect
    authority, or a new `accepted_by_closure` decision.
    """
  end

  defp fixture_inventory_markdown(run) do
    rows =
      run["lane_a_structural_fixture_oracle_evidence"]["fixture_records"]
      |> Enum.map_join("\n", fn fixture ->
        "| `#{fixture["fixture_id"]}` | #{fixture["context_budget_chars"]} | `#{fixture["fixture_hash"]}` | `#{fixture["baseline_context_artifact_id"]}` | `#{fixture["treatment_context_artifact_id"]}` | #{fixture["source_traceability_valid"]} |"
      end)

    """
    # Context Evaluation Fixture Inventory

    Source run: `#{get_in(run, ["source_run", "run_id"])}`
    Source fixture count: 48
    Long-context fixture count: 6
    Global context budget: `null`
    Global-null semantics: `uses_frozen_per_fixture_budgets`

    | Fixture | Frozen context budget (chars) | Fixture tree hash | Baseline artifact | Treatment artifact | Traceability valid |
    | --- | ---: | --- | --- | --- | --- |
    #{rows}
    """
  end

  defp context_artifact_inventory_markdown(run) do
    rows =
      run["lane_a_structural_fixture_oracle_evidence"]["context_artifact_records"]
      |> Enum.map_join("\n", fn artifact ->
        "| `#{artifact["fixture_id"]}` | #{artifact["arm"]} | `#{artifact["arm_label"]}` | `#{artifact["context_artifact_id"]}` | #{artifact["context_budget_chars"]} | #{artifact["selected_context_chars"]} | `#{artifact["context_artifact_hash"]}` | `#{artifact["source_fixture_hash"]}` |"
      end)

    """
    # Context Artifact Inventory

    Every context artifact below was reconstructed with the existing bounded
    raw-trace builder or unchanged `Working Set Compiler v0` selection behavior
    and compared exactly with the source run artifact. No model was called.

    | Fixture | Arm | Exact arm label | Context artifact | Budget | Selected chars | Artifact hash | Source fixture hash |
    | --- | --- | --- | --- | ---: | ---: | --- | --- |
    #{rows}
    """
  end

  defp label_packet_ref_markdown(run) do
    lane_b = run["lane_b_human_label_evidence"]
    refs = run["source_artifact_refs"]

    packet_refs =
      refs
      |> Enum.filter(&String.contains?(&1["path"], "post_stage_1_lane_b_20260601_113121"))
      |> Enum.map_join("\n", fn ref ->
        "| `#{ref["path"]}` | `#{ref["sha256"]}` |"
      end)

    """
    # Lane B Label Packet Reference

    Active packet: `#{lane_b["packet_id"]}`
    Label policy: `#{run["label_policy_version"]}`
    Primary label freeze: `#{lane_b["primary_label_freeze"]}`
    Reviewer-visible true arm identity backfilled: `false`

    The arm mapping is read only from the coordinator-only post-freeze memo for
    evaluation interpretation. Reviewer-visible blinded artifacts remain
    unchanged and use only `context_arm_A` and `context_arm_B`.

    | Source artifact | SHA-256 / tree hash |
    | --- | --- |
    #{packet_refs}

    Small-sample Lane B results:

    #{lane_b_bullets(lane_b)}

    Relevance must be interpreted with omission. These labels remain
    packet-level evaluation evidence and never become runtime approval.
    """
  end

  defp lane_a_metric_rows(metrics, sources) do
    ~w(
      working_set_budget_adherence
      working_set_provenance_completeness
      context_omission_error_rate
      working_set_relevance_score
      long_task_stability
    )
    |> Enum.map_join("\n", fn metric ->
      "| `#{metric}` | #{format4(metrics["baseline"][metric])} | #{format4(metrics["treatment"][metric])} | `#{sources[metric]}` |"
    end)
  end

  defp lane_b_rows(lane_b) do
    interpreted = lane_b["post_freeze_true_arm_interpretation"]

    [
      {"Baseline", interpreted["baseline"]},
      {"Treatment", interpreted["treatment"]}
    ]
    |> Enum.map_join("\n", fn {role, arm} ->
      omission = arm["metrics"]["context_omission_error_rate"]
      relevance = arm["metrics"]["working_set_relevance_score"]

      "| #{role} | `#{arm["blinded_arm"]}` | #{omission["rate_4dp"]} (#{omission["numerator"]}/#{omission["denominator"]}) | #{relevance["rate_4dp"]} (#{relevance["numerator"]}/#{relevance["denominator"]}) |"
    end)
  end

  defp lane_b_bullets(lane_b) do
    metrics = lane_b["blinded_arm_metrics"]

    ["context_arm_A", "context_arm_B", "Combined"]
    |> Enum.map_join("\n", fn arm ->
      omission = metrics[arm]["context_omission_error_rate"]
      relevance = metrics[arm]["working_set_relevance_score"]

      "- `#{arm}`: omission #{omission["rate_4dp"]} (#{omission["numerator"]}/#{omission["denominator"]}); relevance #{relevance["rate_4dp"]} (#{relevance["numerator"]}/#{relevance["denominator"]})"
    end)
  end

  defp format4(value) when is_number(value), do: :erlang.float_to_binary(value / 1, decimals: 4)
  defp format4(value), do: inspect(value)

  defp expand(path, cwd), do: Path.expand(path, cwd)

  defp timestamp do
    {{year, month, day}, {hour, minute, second}} = :calendar.local_time()

    :io_lib.format(
      "~4..0B~2..0B~2..0B_~2..0B~2..0B~2..0B",
      [year, month, day, hour, minute, second]
    )
    |> IO.iodata_to_binary()
  end
end
