defmodule Vanta.Schema do
  @moduledoc """
  JSON Schema validation against the Stage 1 contracts in docs/03_schemas.
  """

  @schema_dir Path.expand("../../../docs/03_schemas", __DIR__)

  @schemas %{
    "approval_record" => "approval_record.schema.json",
    "benchmark_task" => "benchmark_task.schema.json",
    "canonical_state" => "canonical_state.schema.json",
    "episode_journal" => "episode_journal.schema.json",
    "evidence_packet" => "evidence_packet.schema.json",
    "execution_step" => "execution_step.schema.json",
    "experiment_run" => "experiment_run.schema.json",
    "fixture_acceptance" => "fixture_acceptance.schema.json",
    "planner_action_sequence" => "planner_action_sequence.schema.json",
    "persistence_manifest" => "persistence_manifest.schema.json",
    "persisted_artifact" => "persisted_artifact.schema.json",
    "recovery_decision" => "recovery_decision.schema.json",
    "recovery_record" => "recovery_record.schema.json",
    "verifier_output" => "verifier_output.schema.json",
    "working_set" => "working_set.schema.json",
    "eval_result" => "eval_result.schema.json"
  }

  def load_json!(path) do
    path
    |> File.read!()
    |> Jason.decode!()
  end

  def validate(schema_name, data) do
    schema_name
    |> load_schema!()
    |> ExJsonSchema.Validator.validate(data)
    |> case do
      :ok -> :ok
      {:error, errors} -> {:error, errors}
    end
  end

  def validate!(schema_name, data) do
    case validate(schema_name, data) do
      :ok -> data
      {:error, errors} -> raise ArgumentError, "schema #{schema_name} failed: #{inspect(errors)}"
    end
  end

  defp load_schema!(schema_name) do
    schema_file = Map.fetch!(@schemas, schema_name)

    @schema_dir
    |> Path.join(schema_file)
    |> load_json!()
    |> ExJsonSchema.Schema.resolve()
  end
end
