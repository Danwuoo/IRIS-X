defmodule Vanta.MixProject do
  use Mix.Project

  def project do
    [
      app: :vanta,
      version: "0.1.0",
      elixir: "~> 1.19",
      start_permanent: Mix.env() == :prod,
      aliases: aliases(),
      deps: deps()
    ]
  end

  def cli do
    [
      preferred_envs: [
        "test.fast": :test,
        "test.docs": :test,
        "test.tooling": :test,
        "test.integration": :test,
        "test.smoke": :test,
        "test.full": :test
      ]
    ]
  end

  def application do
    [
      extra_applications: [:logger, :crypto, :inets, :ssl]
    ]
  end

  defp deps do
    [
      {:jason, "~> 1.4"},
      {:ex_json_schema, "~> 0.10"},
      {:exqlite, "~> 0.38"}
    ]
  end

  defp aliases do
    [
      "test.fast": ["test --exclude test --include fast_unit"],
      "test.docs": ["test --exclude test --include docs_consistency"],
      "test.tooling": ["test --exclude test --include generated_artifact_tooling"],
      "test.integration": ["test --exclude test --include integration"],
      "test.smoke": ["test --exclude test --include fast_unit --include docs_consistency"],
      "test.full": ["test"],
      "vanta.post_stage_1_larger_sample": ["vanta.post_stage1_larger_sample"],
      "vanta.post_stage_1_lane_b_packet": ["vanta.post_stage1_lane_b_packet"],
      "vanta.post_stage_1_lane_b_label_results": ["vanta.post_stage1_lane_b_label_results"],
      "vanta.post_stage_1_context_os_evaluation": [
        "vanta.post_stage1_context_os_evaluation"
      ],
      "vanta.post_stage_1_side_effect_planning": [
        "vanta.post_stage1_side_effect_planning"
      ],
      "vanta.persistence_and_recovery": ["vanta.persistence_experiment"],
      "vanta.fixture_local_committable_execution": ["vanta.fixture_commit_experiment"]
    ]
  end
end
