defmodule Vanta.FixtureAcceptance do
  @moduledoc """
  Deterministic Stage 1 fixture-specific acceptance checks.
  """

  alias Vanta.Schema

  @expected_selector_failure_status %{
    "structured_selector_missing" => "missing",
    "structured_selector_ambiguous" => "ambiguous"
  }

  def load(workspace) do
    path = Path.join(workspace, "expected/acceptance.json")

    if File.exists?(path) do
      acceptance = Schema.load_json!(path)
      Schema.validate!("fixture_acceptance", acceptance)
    else
      %{}
    end
  end

  def action_sequence(workspace) do
    case load(workspace) do
      %{"action_sequence" => action_sequence} -> {:ok, action_sequence}
      _acceptance -> {:error, :missing_fixture_action_sequence}
    end
  end

  def expected_runtime_status(workspace) do
    workspace
    |> load()
    |> Map.get("expected_runtime_status")
  end

  def expected_task_success(workspace) do
    workspace
    |> load()
    |> Map.get("expected_task_success")
  end

  def expected_failure_labels(workspace) do
    workspace
    |> load()
    |> Map.get("expected_failure_labels", [])
  end

  def expected_recovery_policy(workspace) do
    workspace
    |> load()
    |> Map.get("expected_recovery_policy")
  end

  def expected_rollback_status(workspace) do
    workspace
    |> load()
    |> Map.get("expected_rollback_status")
  end

  def recovery_assertions(workspace) do
    workspace
    |> load()
    |> Map.get("recovery_assertions", [])
  end

  def evaluate_task(workspace, runtime_status, invalid_actions, observations) do
    acceptance = load(workspace)
    expected_status = Map.get(acceptance, "expected_runtime_status")

    observation_errors =
      observations
      |> Enum.map(&evaluate_observation(workspace, &1))
      |> Enum.filter(&match?({:error, _reason}, &1))

    status_ok? = is_nil(expected_status) or expected_status == runtime_status
    expected_success = Map.get(acceptance, "expected_task_success", status_ok?)

    cond do
      expected_success == false ->
        false

      not is_nil(expected_status) and expected_status != "committed" ->
        status_ok?

      observation_errors != [] ->
        false

      runtime_status == "committed" ->
        status_ok? and invalid_actions == 0

      true ->
        status_ok?
    end
  end

  def evaluate_observation(workspace, %{"kind" => "validate_artifact"} = observation) do
    case observation["validation"] do
      "traceability_links" ->
        expected_json(workspace, "traceability.json")
        |> compare_expected_key(observation, "links", "traceability_links_mismatch")

      "terminology_consistency" ->
        expected_json(workspace, "inconsistencies.json")
        |> compare_expected_key(
          observation,
          "inconsistencies",
          "terminology_inconsistencies_mismatch"
        )

      "episode_audit_refs" ->
        expected_json(workspace, "audit_result.json")
        |> compare_audit_result(observation)

      _other ->
        :not_applicable
    end
  end

  def evaluate_observation(workspace, %{"kind" => "inspect_document_structure"} = observation) do
    expected_json(workspace, "structure.json")
    |> compare_expected_subset(
      %{
        "structure" => observation["structure"],
        "selector_results" => observation["selector_results"]
      },
      "structure_mismatch"
    )
  end

  def evaluate_observation(workspace, %{"kind" => "validate_document_contract"} = observation) do
    expected_json(workspace, "contract_result.json")
    |> compare_expected_subset(
      %{"passed" => observation["passed"], "failures" => observation["failures"]},
      "contract_result_mismatch"
    )
  end

  def evaluate_observation(workspace, %{"kind" => kind} = observation)
      when kind in [
             "simulate_patch",
             "compute_diff",
             "apply_reversible_patch",
             "simulate_structured_edit",
             "apply_reversible_structured_edit"
           ] do
    with :ok <- compare_expected_failure_selector_status(workspace, observation),
         :ok <- compare_expected_diff(workspace, observation),
         :ok <- compare_expected_selector_resolution(workspace, observation) do
      :ok
    else
      :not_applicable -> :not_applicable
      {:error, reason} -> {:error, reason}
    end
  end

  def evaluate_observation(_workspace, _observation), do: :not_applicable

  defp expected_json(workspace, file_name) do
    path = Path.join(workspace, Path.join("expected", file_name))

    if File.exists?(path) do
      {:ok, Schema.load_json!(path)}
    else
      :missing
    end
  end

  defp compare_expected_key({:ok, expected}, observation, key, reason) do
    if Map.get(expected, key) == Map.get(observation, key) do
      :ok
    else
      {:error, reason}
    end
  end

  defp compare_expected_key(:missing, _observation, _key, _reason), do: :not_applicable

  defp compare_expected_subset({:ok, expected}, actual, reason) do
    if subset?(expected, actual), do: :ok, else: {:error, reason}
  end

  defp compare_expected_subset(:missing, _actual, _reason), do: :not_applicable

  defp compare_audit_result({:ok, expected}, observation) do
    expected_missing = Enum.sort(Map.get(expected, "missing", []))
    actual_missing = observation |> Map.get("missing", []) |> Enum.sort()

    if Map.get(expected, "complete") == Map.get(observation, "audit_complete") and
         expected_missing == actual_missing do
      :ok
    else
      {:error, "audit_result_mismatch"}
    end
  end

  defp compare_audit_result(:missing, _observation), do: :not_applicable

  defp normalize_diff_text(value) when is_binary(value) do
    value
    |> String.replace("\r\n", "\n")
    |> String.replace("\r", "\n")
    |> String.trim_trailing()
  end

  defp compare_expected_diff(workspace, observation) do
    diff_path = Path.join(workspace, "expected/diff.txt")

    if File.exists?(diff_path) do
      expected = diff_path |> File.read!() |> normalize_diff_text()
      actual = observation |> Map.get("diff", "") |> normalize_diff_text()

      if expected == actual do
        :ok
      else
        {:error, "diff_mismatch"}
      end
    else
      :ok
    end
  end

  defp compare_expected_selector_resolution(workspace, observation) do
    expected_json(workspace, "selector_resolution.json")
    |> compare_expected_subset(
      observation["selector_resolution"] || %{},
      "selector_resolution_mismatch"
    )
    |> case do
      :not_applicable -> :ok
      result -> result
    end
  end

  defp compare_expected_failure_selector_status(workspace, observation) do
    expected_labels = expected_failure_labels(workspace)

    @expected_selector_failure_status
    |> Enum.find(fn {label, _status} -> label in expected_labels end)
    |> case do
      nil ->
        :ok

      {label, expected_status} ->
        if get_in(observation, ["selector_resolution", "status"]) == expected_status do
          :ok
        else
          {:error, label}
        end
    end
  end

  defp subset?(expected, actual) when is_map(expected) and is_map(actual) do
    Enum.all?(expected, fn {key, expected_value} ->
      Map.has_key?(actual, key) and subset?(expected_value, actual[key])
    end)
  end

  defp subset?(expected, actual) when is_list(expected) and is_list(actual) do
    Enum.zip(expected, actual)
    |> Enum.all?(fn {expected_item, actual_item} -> subset?(expected_item, actual_item) end) and
      length(expected) <= length(actual)
  end

  defp subset?(expected, actual), do: expected == actual
end
