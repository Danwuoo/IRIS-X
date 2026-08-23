"""Regression tests for the Stage 3 provider-independent G0/S1 substrate."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from spex_arc.baselines.arc_a1 import (  # noqa: E402
    BaselineConfiguration,
    BaselineSolverFactory,
    BudgetTierMultipliers,
    derive_budget_proposal,
    load_calibration_observation,
    paired_precondition_failures,
    summarize_paired_task_comparison,
)
from spex_arc.domain.arc_a1 import parse_task_json  # noqa: E402
from spex_arc.evaluator.arc_a1 import LocalReferenceEvaluator, load_evaluator_identity  # noqa: E402
from spex_arc.runner.arc_a1 import ArcA1Runner, InferenceBudget, RunManifest  # noqa: E402
from spex_arc.solvers.arc_a1 import (  # noqa: E402
    G0MinimalPromptPolicy,
    G0Solver,
    ModelIdentity,
    ModelResponse,
    PreparedModelRequest,
    RequestReservation,
    S1Solver,
    StructuredPromptPolicy,
)


FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "arc_a1"
RULES_PATH = REPOSITORY_ROOT / "artifacts" / "arc-agi-1" / "rules.json"


class ReplayAdapter:
    """A no-network fixture adapter that nevertheless uses the real boundary."""

    requires_network = False
    required_tools: tuple[str, ...] = ()

    def __init__(self, identity: ModelIdentity) -> None:
        self.identity = identity
        self.requests = []

    def prepare(self, request, budget):
        self.requests.append(request)
        return PreparedModelRequest(
            request=request,
            reservation=RequestReservation(
                input_tokens=11,
                max_output_tokens=17,
                max_cost_usd=0.10,
            ),
        )

    def complete(self, prepared):
        structured = "fixed representation" in prepared.request.messages[1]["content"]
        output = [[2, 0], [0, 2]] if not structured else [[2, 0], [2, 0]]
        return ModelResponse(
            text=json.dumps(
                {
                    "task_id": prepared.request.task_id,
                    "attempts": [{"attempt": 1, "outputs": [output]}],
                }
            ),
            input_tokens=7,
            output_tokens=5,
            cost_usd=0.03,
        )


class ArcA1G0S1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        identity_result = load_evaluator_identity(RULES_PATH)
        assert identity_result.value is not None, identity_result.failures
        cls.evaluator_identity = identity_result.value
        evaluator_result = LocalReferenceEvaluator.from_rules_snapshot(RULES_PATH)
        assert evaluator_result.value is not None, evaluator_result.failures
        cls.evaluator = evaluator_result.value
        cls.model = ModelIdentity(
            provider="fixture-provider",
            model_id="fixture-model-v1",
            model_snapshot="fixture-snapshot-2026-08-06",
            weights_hash="fixture-weights-not-applicable",
            adapter_id="fixture-replay-adapter-v1",
            request_parameters={"temperature": 0, "top_p": 1},
        )

    def task(self):
        result = parse_task_json((FIXTURES / "task-single-test.json").read_text(encoding="utf-8"), "single")
        self.assertTrue(result.valid, result.failures)
        assert result.value is not None
        return result.value

    def configuration(self, label: str) -> BaselineConfiguration:
        policy = G0MinimalPromptPolicy() if label == "G0" else StructuredPromptPolicy()
        return BaselineConfiguration(
            configuration_id=f"fixture-{label.lower()}-v1",
            label=label,
            unit=policy.unit,
            model=self.model,
            prompt_policy=policy,
            retry_policy={"max_retries": 0},
            tools=(),
            network_access=False,
            context_policy="single-task; no persistent memory; no retrieved context",
            request_date="2026-08-06",
        )

    def manifest(self, configuration: BaselineConfiguration, run_id: str) -> RunManifest:
        return RunManifest(
            run_id=run_id,
            benchmark_snapshot="arc-agi-1-local-manifest:ee26dc8d3731cd670b3ed5e8712b675a6504ba741e428307200ab52e26a6f932",
            evaluator_version=self.evaluator_identity.evaluator_version,
            evaluation_date=configuration.request_date,
            unit=configuration.unit,
            model_provider=self.model.provider,
            model_id=self.model.model_id,
            model_snapshot=self.model.model_snapshot,
            weights_hash=self.model.weights_hash,
            configuration_id=configuration.configuration_id,
            configuration_sha256=configuration.sha256,
            provider_adapter_id=self.model.adapter_id,
            provider_request_parameters=dict(self.model.request_parameters),
            provider_request_parameters_sha256=self.model.request_parameters_sha256,
            prompt_policy=configuration.prompt_policy.to_json(),
            prompt_policy_hash=configuration.prompt_policy.sha256,
            retry_policy=dict(configuration.retry_policy),
            solver_commit="fixture-stage3",
            training_data_manifest="not-used-fixture",
            synthetic_data_manifest="not-used-fixture",
            tools=configuration.tools,
            verifier="none",
            memory_policy="none",
            search_policy="none",
            budget=InferenceBudget(
                num_attempts=1,
                max_input_tokens=20,
                max_output_tokens=20,
                max_model_calls_per_task=1,
                max_rollouts_per_task=1,
                wall_clock_limit_seconds=1.0,
            ),
            hardware="fixture-cpu",
            network_access=configuration.network_access,
            random_seed=17,
            estimated_cost_usd=1.0,
            contamination_status="fixture-only; no ARC public task query",
            result_status="exploratory",
            task_ids=("single",),
            rules_snapshot_id=self.evaluator_identity.rules_snapshot_id,
            rules_sha256=self.evaluator_identity.rules_sha256,
            scorer_status=self.evaluator_identity.scorer_status,
            official_status=self.evaluator_identity.official_status,
            parity_status=self.evaluator_identity.parity_status,
        )

    def test_g0_and_s1_are_bound_to_one_backbone_and_only_the_prompt_differs(self) -> None:
        g0 = self.configuration("G0")
        s1 = self.configuration("S1")
        g0_manifest = self.manifest(g0, "fixture-g0")
        s1_manifest = self.manifest(s1, "fixture-s1")

        self.assertEqual(g0.binding_failures(g0_manifest), ())
        self.assertEqual(s1.binding_failures(s1_manifest), ())
        self.assertEqual(paired_precondition_failures(g0, g0_manifest, s1, s1_manifest), ())

        asymmetric = replace(
            s1_manifest,
            budget=InferenceBudget(
                num_attempts=1,
                max_input_tokens=21,
                max_output_tokens=20,
                max_model_calls_per_task=1,
                max_rollouts_per_task=1,
                wall_clock_limit_seconds=1.0,
            ),
        )
        self.assertIn(
            "paired_manifest_asymmetry",
            {failure.code for failure in paired_precondition_failures(g0, g0_manifest, s1, asymmetric)},
        )

    def test_provider_reservations_settle_and_calibration_and_pairing_trace_to_task_records(self) -> None:
        task = self.task()
        g0 = self.configuration("G0")
        s1 = self.configuration("S1")
        g0_manifest = self.manifest(g0, "fixture-g0-run")
        s1_manifest = self.manifest(s1, "fixture-s1-run")
        adapter = ReplayAdapter(self.model)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            g0_result = ArcA1Runner(
                g0_manifest,
                self.evaluator,
                BaselineSolverFactory(g0, adapter),
                root,
            ).run((task,))
            s1_result = ArcA1Runner(
                s1_manifest,
                self.evaluator,
                BaselineSolverFactory(s1, adapter),
                root,
            ).run((task,))

            g0_costs = json.loads((g0_result.artifact_directory / "costs.json").read_text(encoding="utf-8"))
            usage = g0_costs["per_task"][0]["usage"]
            self.assertEqual(usage["input_tokens"], 7)
            self.assertEqual(usage["output_tokens"], 5)
            self.assertEqual(usage["estimated_cost_usd"], 0.03)
            self.assertEqual(g0_result.metrics["aggregate_metrics"]["exact_at_1"], 1.0)
            self.assertEqual(s1_result.metrics["aggregate_metrics"]["exact_at_1"], 0.0)

            comparison = summarize_paired_task_comparison(g0_result.artifact_directory, s1_result.artifact_directory).to_json()
            self.assertEqual(comparison["task_count"], 1)
            self.assertEqual(comparison["s1_minus_g0_exact_at_1"], -1.0)
            self.assertEqual(comparison["g0_only_solved"], 1)

            proposal = derive_budget_proposal(
                [load_calibration_observation(g0_result.artifact_directory)],
                BudgetTierMultipliers(low=1.0, matched=1.5, high=2.0),
                num_attempts=1,
            ).to_json()
            self.assertEqual([tier["label"] for tier in proposal["tiers"]], ["Low", "Matched", "High"])
            self.assertEqual(proposal["tiers"][0]["budget"]["max_input_tokens"], 7)
            self.assertEqual(proposal["tiers"][1]["budget"]["max_output_tokens"], 8)
            self.assertEqual(proposal["tiers"][2]["estimated_cost_usd"], 0.06)


if __name__ == "__main__":
    unittest.main()
