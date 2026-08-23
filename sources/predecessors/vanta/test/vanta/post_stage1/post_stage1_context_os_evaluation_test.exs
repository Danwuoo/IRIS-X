defmodule Vanta.PostStage1ContextOSEvaluationTest do
  use ExUnit.Case

  alias Vanta.PostStage1ContextOSEvaluation, as: Evaluation

  @source_run "docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/run.json"
  @source_summary "docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/summary.md"
  @source_fixture_inventory "docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/fixture_inventory.md"
  @active_packet "docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121"
  @superseded_packet "docs/05_evaluation/label_packets/post_stage_1_lane_b_20260530_141649"

  @baseline_arm "raw_trace_bounded_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget"

  setup do
    root =
      Path.join(
        System.tmp_dir!(),
        "vanta_context_os_evaluation_#{System.unique_integer([:positive, :monotonic])}"
      )

    File.mkdir_p!(root)
    on_exit(fn -> File.rm_rf!(root) end)
    %{root: root}
  end

  @tag :generated_artifact_tooling
  test "happy path validates the active frozen artifact set" do
    assert {:ok, run} = Evaluation.validate(generated_at: "2026-07-19T00:00:00Z")

    assert run["final_pilot_status"] == "pass_artifact_backed_evaluation_pilot"
    assert run["evaluation_mode"] == "artifact_backed_post_freeze_evaluation"
    assert get_in(run, ["source_run", "run_id"]) == "20260601_113121"
    assert get_in(run, ["source_run", "original_model_run_reexecuted"]) == false
    assert get_in(run, ["controls", "openclaw_agent"]) == "vanta-verifier"
    assert get_in(run, ["controls", "tool_policy"]) == "embedded_context_only"
    assert run["validation_errors"] == []
  end

  @tag :generated_artifact_tooling
  test "fails closed on source run ID mismatch", %{root: root} do
    opts = mutated_run_opts(root, "20260530_141649", & &1)
    assert_error(Evaluation.validate(opts), "source run directory ID")
  end

  @tag :generated_artifact_tooling
  test "fails closed on arm identity mismatch", %{root: root} do
    opts =
      mutated_run_opts(root, "20260601_113121", fn run ->
        put_in(
          run,
          ["arm_metadata", "working_set", "baseline_arm_label"],
          @baseline_arm <> "_mutated"
        )
      end)

    assert_error(Evaluation.validate(opts), "working-set baseline arm")
  end

  @tag :generated_artifact_tooling
  test "fails closed on model or harness mismatch", %{root: root} do
    model_opts =
      mutated_run_opts(Path.join(root, "model"), "20260601_113121", fn run ->
        put_in(run, ["run_controls", "model_identity"], "unexpected-model")
      end)

    harness_opts =
      mutated_run_opts(Path.join(root, "harness"), "20260601_113121", fn run ->
        put_in(run, ["run_controls", "harness_identity"], "unexpected-harness")
      end)

    assert_error(Evaluation.validate(model_opts), "model identity")
    assert_error(Evaluation.validate(harness_opts), "harness identity")
  end

  @tag :generated_artifact_tooling
  test "fails closed on prompt or response budget mismatch", %{root: root} do
    prompt_opts =
      mutated_run_opts(Path.join(root, "prompt"), "20260601_113121", fn run ->
        put_in(run, ["run_controls", "prompt_character_budget"], 19_999)
      end)

    response_opts =
      mutated_run_opts(Path.join(root, "response"), "20260601_113121", fn run ->
        put_in(run, ["run_controls", "response_character_budget"], 11_999)
      end)

    assert_error(Evaluation.validate(prompt_opts), "prompt character budget")
    assert_error(Evaluation.validate(response_opts), "response character budget")
  end

  @tag :generated_artifact_tooling
  test "fails closed on a per-fixture context budget mismatch", %{root: root} do
    opts =
      mutated_run_opts(root, "20260601_113121", fn run ->
        update_task(run, "docops_ws_evidence_packet_001", fn task ->
          put_in(task, ["working_set", "baseline", "context", "max_context_chars"], 259)
        end)
      end)

    assert_error(Evaluation.validate(opts), "baseline context budget")
  end

  @tag :generated_artifact_tooling
  test "fails closed when a long-context fixture is missing", %{root: root} do
    opts =
      mutated_run_opts(root, "20260601_113121", fn run ->
        Map.update!(run, "tasks", fn tasks ->
          Enum.reject(tasks, &(&1["task_id"] == "docops_ws_recovery_context_001"))
        end)
      end)

    assert_error(Evaluation.validate(opts), "missing long-context fixture")
  end

  @tag :generated_artifact_tooling
  test "fails closed when a source context artifact is missing", %{root: root} do
    opts =
      mutated_run_opts(root, "20260601_113121", fn run ->
        update_task(run, "docops_ws_omission_trap_001", fn task ->
          put_in(task, ["working_set", "treatment", "context"], nil)
        end)
      end)

    assert_error(Evaluation.validate(opts), "treatment context artifact")
  end

  @tag :generated_artifact_tooling
  test "fails closed on a Lane A metric mismatch", %{root: root} do
    opts =
      mutated_run_opts(root, "20260601_113121", fn run ->
        put_in(
          run,
          ["metrics", "working_set", "baseline", "working_set_relevance_score"],
          0.5
        )
      end)

    assert_error(Evaluation.validate(opts), "source working-set metric")
  end

  @tag :generated_artifact_tooling
  test "fails closed on Lane B raw-count or rate mismatch", %{root: root} do
    import_path = Path.join(@active_packet, "label_results_import_summary.json")

    count_path =
      write_mutated_json(Path.join(root, "count.json"), import_path, fn summary ->
        put_in(summary, ["raw_label_counts", "working_set_context"], 23)
      end)

    rate_path =
      write_mutated_json(Path.join(root, "rate.json"), import_path, fn summary ->
        put_in(
          summary,
          [
            "reported_metric_scores",
            "working_set_relevance_score",
            "by_blinded_arm",
            "context_arm_B",
            "score_4dp"
          ],
          "0.9499"
        )
      end)

    assert_error(
      Evaluation.validate(import_summary: count_path),
      "Lane B report/import parity"
    )

    assert_error(Evaluation.validate(import_summary: rate_path), "Lane B report/import parity")
  end

  @tag :generated_artifact_tooling
  test "rejects the superseded historical packet before source loading" do
    assert_error(
      Evaluation.validate(packet_dir: @superseded_packet),
      "superseded packet 20260530_141649"
    )
  end

  @tag :generated_artifact_tooling
  test "fails closed when the primary-label freeze is missing", %{root: root} do
    source = Path.join(@active_packet, "label_results_primary_filled.json")

    path =
      write_mutated_json(Path.join(root, "labels.json"), source, fn result ->
        Map.delete(result, "primary_label_freeze")
      end)

    assert_error(Evaluation.validate(primary_label_results: path), "primary label freeze")
  end

  @tag :generated_artifact_tooling
  test "fails closed when the import summary artifact is missing", %{root: root} do
    assert_error(
      Evaluation.validate(import_summary: Path.join(root, "missing_import_summary.json")),
      "missing source artifact"
    )
  end

  @tag :generated_artifact_tooling
  test "fails closed on a process-integrity floor violation", %{root: root} do
    opts =
      mutated_run_opts(root, "20260601_113121", fn run ->
        put_in(run, ["metrics", "hard_gates", "unsupported_commits"], 1)
      end)

    assert_error(
      Evaluation.validate(opts),
      "process-integrity metrics.hard_gates.unsupported_commits"
    )
  end

  @tag :generated_artifact_tooling
  test "fails closed if reviewer-visible artifacts contain true arm identity", %{root: root} do
    source = Path.join(@active_packet, "working_set_context_items.jsonl")
    [first | rest] = source |> File.read!() |> String.split(~r/\R/, trim: true)

    polluted =
      first
      |> Jason.decode!()
      |> Map.put("source_arm_label", @baseline_arm)
      |> Jason.encode!()

    path = Path.join(root, "polluted_working_set_context_items.jsonl")
    File.write!(path, Enum.join([polluted | rest], "\n") <> "\n")

    assert_error(
      Evaluation.validate(working_set_items: path),
      "reviewer-visible packet contamination"
    )
  end

  @tag :generated_artifact_tooling
  test "writes the complete required output artifact set", %{root: root} do
    out = Path.join(root, "complete")
    assert {:ok, run} = Evaluation.run(out_dir: out, generated_at: "2026-07-19T00:00:00Z")

    assert Enum.all?(Evaluation.artifact_files(), &File.regular?(Path.join(out, &1)))

    assert Jason.decode!(File.read!(Path.join(out, "run.json")))["evaluation_fingerprint"] ==
             run["evaluation_fingerprint"]
  end

  @tag :generated_artifact_tooling
  test "deterministic reruns retain a stable evaluation fingerprint", %{root: root} do
    assert {:ok, first} =
             Evaluation.run(
               out_dir: Path.join(root, "first"),
               generated_at: "2026-07-19T00:00:00Z"
             )

    assert {:ok, second} =
             Evaluation.run(
               out_dir: Path.join(root, "second"),
               generated_at: "2026-07-19T00:00:01Z"
             )

    assert first["evaluation_fingerprint"] == second["evaluation_fingerprint"]
    refute first["generated_at"] == second["generated_at"]
    refute first["artifact_root"] == second["artifact_root"]
  end

  defp mutated_run_opts(root, run_id, mutator) do
    run_path =
      root
      |> Path.join(run_id)
      |> Path.join("run.json")

    write_mutated_json(run_path, @source_run, mutator)

    [
      source_run: run_path,
      source_summary: @source_summary,
      source_fixture_inventory: @source_fixture_inventory
    ]
  end

  defp write_mutated_json(path, source, mutator) do
    value = source |> File.read!() |> strip_bom() |> Jason.decode!() |> mutator.()
    File.mkdir_p!(Path.dirname(path))
    File.write!(path, Jason.encode!(value, pretty: true) <> "\n")
    path
  end

  defp update_task(run, task_id, fun) do
    Map.update!(run, "tasks", fn tasks ->
      Enum.map(tasks, fn task -> if task["task_id"] == task_id, do: fun.(task), else: task end)
    end)
  end

  defp assert_error({:error, errors}, fragment) do
    assert Enum.any?(errors, &String.contains?(&1, fragment)),
           "expected error containing #{inspect(fragment)}, got:\n#{Enum.join(errors, "\n")}"
  end

  defp assert_error(other, fragment),
    do: flunk("expected error containing #{inspect(fragment)}, got: #{inspect(other)}")

  defp strip_bom(<<0xEF, 0xBB, 0xBF, rest::binary>>), do: rest
  defp strip_bom(text), do: text
end
