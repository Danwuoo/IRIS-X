"""End-to-end regression tests for the Stage 2 ARC-AGI-1 run substrate."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from spex_arc.domain.arc_a1 import CandidateSet, Grid, Prediction, parse_task_json  # noqa: E402
from spex_arc.evaluator.arc_a1 import LocalReferenceEvaluator, load_evaluator_identity  # noqa: E402
from spex_arc.runner.arc_a1 import (  # noqa: E402
    ArcA1Runner,
    InferenceBudget,
    RunManifest,
    _ArtifactStore,
    record_usage,
    validate_run_manifest,
)


FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "arc_a1"
RULES_PATH = REPOSITORY_ROOT / "artifacts" / "arc-agi-1" / "rules.json"


class ExactDummySolver:
    """A deterministic fixture solver; it has no model, network, or tools."""

    requires_network = False
    required_tools: tuple[str, ...] = ()

    def __init__(self) -> None:
        self.calls: list[str] = []

    def solve(self, task, budget):
        self.calls.append(task.task_id)
        record_usage(input_tokens=3, output_tokens=2, model_calls=1, rollouts=1, estimated_cost_usd=0.02)
        return CandidateSet(
            task_id=task.task_id,
            candidates=(Prediction(attempt=1, outputs=(Grid(((2, 0), (0, 2))),)),),
        )


class OverBudgetDummySolver(ExactDummySolver):
    def solve(self, task, budget):
        record_usage(model_calls=2)
        return super().solve(task, budget)


class NetworkDummySolver(ExactDummySolver):
    requires_network = True


class FlakyDummySolver(ExactDummySolver):
    def solve(self, task, budget):
        self.calls.append(task.task_id)
        record_usage(model_calls=1)
        if len(self.calls) == 1:
            raise RuntimeError("transient fixture error")
        return CandidateSet(
            task_id=task.task_id,
            candidates=(Prediction(attempt=1, outputs=(Grid(((2, 0), (0, 2))),)),),
        )


class CancellableTimeoutDummySolver(ExactDummySolver):
    def __init__(self) -> None:
        super().__init__()
        self.cancelled = threading.Event()

    def solve(self, task, budget):
        self.calls.append(task.task_id)
        self.cancelled.wait(1.0)
        return CandidateSet(
            task_id=task.task_id,
            candidates=(Prediction(attempt=1, outputs=(Grid(((2, 0), (0, 2))),)),),
        )

    def cancel(self, task_id: str) -> None:
        self.cancelled.set()


class ArcA1RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        identity_result = load_evaluator_identity(RULES_PATH)
        assert identity_result.value is not None, identity_result.failures
        cls.identity = identity_result.value
        evaluator_result = LocalReferenceEvaluator.from_rules_snapshot(RULES_PATH)
        assert evaluator_result.value is not None, evaluator_result.failures
        cls.evaluator = evaluator_result.value

    def task(self, task_id: str = "single"):
        result = parse_task_json((FIXTURES / "task-single-test.json").read_text(encoding="utf-8"), task_id)
        self.assertTrue(result.valid, result.failures)
        assert result.value is not None
        return result.value

    def manifest(self, run_id: str, task_ids: tuple[str, ...]) -> RunManifest:
        return RunManifest(
            run_id=run_id,
            benchmark_snapshot="arc-agi-1-local-manifest:ee26dc8d3731cd670b3ed5e8712b675a6504ba741e428307200ab52e26a6f932",
            evaluator_version=self.identity.evaluator_version,
            evaluation_date="2026-08-06",
            unit="G",
            model_provider="test-dummy",
            model_id="exact-dummy-v1",
            model_snapshot="fixture-static",
            weights_hash="not-applicable-dummy",
            configuration_id="fixture-g0",
            configuration_sha256="0" * 64,
            provider_adapter_id="fixture-replay-v1",
            provider_request_parameters={"temperature": 0},
            provider_request_parameters_sha256="1" * 64,
            prompt_policy={"kind": "fixture-minimal"},
            prompt_policy_hash="2" * 64,
            retry_policy={"max_retries": 0},
            solver_commit="test-fixture",
            training_data_manifest="not-used",
            synthetic_data_manifest="not-used",
            tools=(),
            verifier="none",
            memory_policy="none",
            search_policy="none",
            budget=InferenceBudget(
                num_attempts=1,
                max_input_tokens=10,
                max_output_tokens=10,
                max_model_calls_per_task=1,
                max_rollouts_per_task=1,
                wall_clock_limit_seconds=1.0,
            ),
            hardware="test-cpu",
            network_access=False,
            random_seed=17,
            estimated_cost_usd=1.0,
            contamination_status="public-exposed",
            result_status="exploratory",
            task_ids=task_ids,
            rules_snapshot_id=self.identity.rules_snapshot_id,
            rules_sha256=self.identity.rules_sha256,
            scorer_status=self.identity.scorer_status,
            official_status=self.identity.official_status,
            parity_status=self.identity.parity_status,
        )

    def test_deterministic_dummy_run_writes_complete_traceable_bundle(self) -> None:
        task = self.task()
        manifest = self.manifest("dummy-deterministic", ("single",))
        validation = validate_run_manifest(manifest, self.identity)
        self.assertTrue(validation.valid, validation.failures)

        with tempfile.TemporaryDirectory() as temporary:
            solver = ExactDummySolver()
            runner = ArcA1Runner(manifest, self.evaluator, lambda _manifest, _budget: solver, Path(temporary))
            first = runner.run((task,))
            bundle = first.artifact_directory
            expected_files = {
                "manifest.json",
                "predictions.jsonl",
                "events.jsonl",
                "metrics.json",
                "costs.json",
                "failures.jsonl",
                "deviations.json",
            }
            self.assertEqual({path.name for path in bundle.iterdir()}, expected_files)
            first_predictions = (bundle / "predictions.jsonl").read_bytes()
            first_metrics = (bundle / "metrics.json").read_bytes()
            metrics = json.loads(first_metrics)
            costs = json.loads((bundle / "costs.json").read_text(encoding="utf-8"))

            self.assertEqual(first.completed_task_ids, ("single",))
            self.assertEqual(metrics["aggregate_metrics"]["exact_at_1"], 1.0)
            self.assertEqual(metrics["aggregate_metrics"]["task_count"], 1)
            self.assertEqual(costs["observed_run_cost_usd"], 0.02)
            self.assertEqual(costs["per_task"][0]["usage"]["wall_clock_seconds"] >= 0.0, True)

            second = runner.run((task,))
            self.assertEqual(second.executed_task_ids, ())
            self.assertEqual(first_predictions, (bundle / "predictions.jsonl").read_bytes())
            self.assertEqual(first_metrics, (bundle / "metrics.json").read_bytes())
            self.assertEqual(solver.calls, ["single"])

    def test_interrupted_task_is_terminally_recovered_without_rerun_or_double_counting(self) -> None:
        first_task = self.task("first")
        interrupted_task = self.task("second")
        manifest = self.manifest("resume-without-double-count", ("first", "second"))

        with tempfile.TemporaryDirectory() as temporary:
            bundle_root = Path(temporary) / manifest.run_id
            store = _ArtifactStore.open(bundle_root, manifest)
            store.append_event("task_attempt_started", attempt=1, task_id="second")
            solver = ExactDummySolver()
            result = ArcA1Runner(manifest, self.evaluator, lambda _manifest, _budget: solver, Path(temporary)).run(
                (first_task, interrupted_task)
            )

            predictions = [json.loads(line) for line in (bundle_root / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
            failures = [json.loads(line) for line in (bundle_root / "failures.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(result.completed_task_ids, ("first", "second"))
            self.assertEqual(result.resumed_task_ids, ("second",))
            self.assertEqual(solver.calls, ["first"])
            self.assertEqual([record["task_id"] for record in predictions], ["first", "second"])
            self.assertEqual(len({record["task_id"] for record in predictions}), 2)
            self.assertEqual(failures[0]["task_id"], "second")
            self.assertIn("interrupted_before_finalization", {failure["code"] for failure in failures[0]["score_failures"]})

    def test_budget_and_network_policy_failures_are_structured_terminal_records(self) -> None:
        task = self.task()
        cases = (
            ("budget", OverBudgetDummySolver(), "budget_exceeded"),
            ("network", NetworkDummySolver(), "policy_violation"),
        )
        for name, solver, expected_status in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                manifest = self.manifest(f"{name}-failure", ("single",))
                result = ArcA1Runner(manifest, self.evaluator, lambda _manifest, _budget: solver, Path(temporary)).run((task,))
                predictions = [
                    json.loads(line)
                    for line in (result.artifact_directory / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
                ]
                failures = [
                    json.loads(line)
                    for line in (result.artifact_directory / "failures.jsonl").read_text(encoding="utf-8").splitlines()
                ]
                self.assertEqual(predictions[0]["terminal_status"], expected_status)
                self.assertEqual(failures[0]["classification"], expected_status)
                self.assertTrue(predictions[0]["task_score"]["invalid_output"])

    def test_manifest_rejects_identity_and_concurrency_mismatches(self) -> None:
        manifest = self.manifest("invalid-manifest", ("single",))
        incompatible = replace(
            manifest,
            evaluator_version="different",
            budget=InferenceBudget(
                num_attempts=1,
                max_input_tokens=10,
                max_output_tokens=10,
                max_model_calls_per_task=1,
                max_rollouts_per_task=1,
                wall_clock_limit_seconds=1.0,
                concurrency_limit=2,
            ),
        )
        result = validate_run_manifest(incompatible, self.identity)
        self.assertFalse(result.valid)
        self.assertIn("evaluator_version_mismatch", {failure.code for failure in result.failures})
        self.assertIn("unsupported_concurrency_limit", {failure.code for failure in result.failures})

    def test_retry_and_cooperative_timeout_are_recorded_without_uncaught_exceptions(self) -> None:
        task = self.task()
        with tempfile.TemporaryDirectory() as temporary:
            flaky = FlakyDummySolver()
            manifest = replace(
                self.manifest("retry", ("single",)),
                retry_policy={"max_retries": 1},
                budget=InferenceBudget(
                    num_attempts=1,
                    max_input_tokens=10,
                    max_output_tokens=10,
                    max_model_calls_per_task=2,
                    max_rollouts_per_task=1,
                    wall_clock_limit_seconds=1.0,
                ),
            )
            result = ArcA1Runner(
                manifest,
                self.evaluator,
                lambda _manifest, _budget: flaky,
                Path(temporary),
                max_retries=1,
            ).run((task,))
            prediction = json.loads((result.artifact_directory / "predictions.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(flaky.calls, ["single", "single"])
            self.assertEqual(prediction["terminal_status"], "scored")
            self.assertEqual(prediction["task_score"]["exact_at_1"], True)

        with tempfile.TemporaryDirectory() as temporary:
            slow = CancellableTimeoutDummySolver()
            manifest = replace(
                self.manifest("cooperative-timeout", ("single",)),
                budget=InferenceBudget(
                    num_attempts=1,
                    max_input_tokens=10,
                    max_output_tokens=10,
                    max_model_calls_per_task=1,
                    max_rollouts_per_task=1,
                    wall_clock_limit_seconds=0.01,
                ),
            )
            result = ArcA1Runner(manifest, self.evaluator, lambda _manifest, _budget: slow, Path(temporary)).run((task,))
            prediction = json.loads((result.artifact_directory / "predictions.jsonl").read_text(encoding="utf-8"))
            self.assertTrue(slow.cancelled.is_set())
            self.assertEqual(prediction["terminal_status"], "timeout")
            self.assertTrue(prediction["task_score"]["invalid_output"])


if __name__ == "__main__":
    unittest.main()
