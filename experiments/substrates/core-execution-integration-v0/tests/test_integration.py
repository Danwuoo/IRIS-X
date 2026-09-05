from __future__ import annotations

import ast
import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path


SUBSTRATE = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = SUBSTRATE / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_lookup  # noqa: E402

from irisx.core.interfaces import ExecutorAdapter  # noqa: E402


def load_mutation_slice():
    path = (
        REPOSITORY_ROOT
        / "experiments"
        / "substrates"
        / "minimal-reliable-execution-v0"
        / "scripts"
        / "run_slice.py"
    )
    spec = importlib.util.spec_from_file_location("phase5_mutation_slice", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load mutation slice")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CountingPolicyGate:
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, context, request):
        del context, request
        self.calls += 1
        raise AssertionError("a read-only request must not invoke mutation policy")


class CoreExecutionReadOnlyIntegrationTests(unittest.TestCase):
    def test_read_only_path_yields_verified_success(self) -> None:
        adapter = run_lookup.ReadOnlyLookupAdapter()
        record = run_lookup.execute_lookup(adapter=adapter)
        self.assertEqual(record["actual_outcome"], "success")
        self.assertEqual(record["producer_claim"], "success")
        self.assertEqual(record["empirical_evidence_status"], "sufficient")
        self.assertEqual(record["acceptance_decision"], "accept")
        self.assertTrue(record["verified_success_eligibility"])
        self.assertEqual(record["joint_interpretation"], "verified_success")
        self.assertEqual(record["terminal_execution_status"], "completed")
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(adapter.lookup_calls, 1)

    def test_read_only_path_preserves_state_identity(self) -> None:
        adapter = run_lookup.ReadOnlyLookupAdapter()
        record = run_lookup.execute_lookup(adapter=adapter)
        effects = record["side_effects"]
        self.assertEqual(effects["state_before_sha256"], effects["state_after_sha256"])
        self.assertEqual(effects["changed_paths"], [])
        self.assertFalse(effects["mutation_primitive_executed"])
        self.assertEqual(adapter.mutation_primitive_calls, 0)

    def test_read_only_classification_does_not_invoke_policy_gate(self) -> None:
        gate = CountingPolicyGate()
        record = run_lookup.execute_lookup(policy_gate=gate)
        self.assertEqual(gate.calls, 0)
        self.assertEqual(record["policy_decision"]["decision"], "not_required")
        self.assertEqual(record["policy_decision"]["timing"], "not_applicable")

    def test_two_concrete_adapters_share_core_without_substrate_branching(self) -> None:
        mutation = load_mutation_slice()
        set_adapter = mutation.LocalSetAdapter()
        lookup_adapter = run_lookup.ReadOnlyLookupAdapter()
        self.assertNotEqual(type(set_adapter), type(lookup_adapter))
        self.assertIsInstance(set_adapter, ExecutorAdapter)
        self.assertIsInstance(lookup_adapter, ExecutorAdapter)
        self.assertTrue(mutation.execute_slice(adapter=set_adapter)["verified_success_eligibility"])
        self.assertTrue(run_lookup.execute_lookup(adapter=lookup_adapter)["verified_success_eligibility"])
        core_source = (REPOSITORY_ROOT / "irisx" / "core" / "execution.py").read_text(encoding="utf-8")
        self.assertNotIn("minimal-reliable-execution-v0", core_source)
        self.assertNotIn("core-execution-integration-v0", core_source)

    def test_core_imports_no_experiment_or_preserved_source_tree(self) -> None:
        forbidden = {"experiments", "sources", "references"}
        for path in sorted((REPOSITORY_ROOT / "irisx").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".", 1)[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    roots = {node.module.split(".", 1)[0]}
                else:
                    continue
                self.assertFalse(roots & forbidden, f"forbidden dependency in {path}")

    def test_observations_do_not_determine_adjudication(self) -> None:
        observed = run_lookup.execute_lookup(collect_observations=True)
        unobserved = run_lookup.execute_lookup(collect_observations=False)
        fields = (
            "actual_outcome",
            "producer_claim",
            "empirical_evidence_status",
            "acceptance_decision",
            "verified_success_eligibility",
            "joint_interpretation",
            "terminal_execution_status",
            "policy_decision",
            "side_effects",
            "verification",
            "evidence",
            "resource_ledger",
        )
        self.assertTrue(observed["observations"])
        self.assertEqual(unobserved["observations"], [])
        for field in fields:
            self.assertEqual(observed[field], unobserved[field])

    def test_excluded_runtime_counts_are_explicitly_zero(self) -> None:
        record = run_lookup.execute_lookup()
        resources = record["resource_ledger"]
        for field in (
            "model_calls",
            "network_calls",
            "paid_api_calls",
            "tool_calls",
            "retry_count",
            "route_count",
            "escalation_count",
            "recovery_count",
        ):
            self.assertEqual(resources[field], 0, field)
        self.assertFalse(record["recovery"]["attempted"])
        self.assertFalse(record["recovery"]["silent_retry"])

    def test_stale_evidence_denies_eligibility_without_rewriting_outcome(self) -> None:
        adapter = run_lookup.ReadOnlyLookupAdapter(evidence_hash_overrides={"program": "0" * 64})
        record = run_lookup.execute_lookup(adapter=adapter)
        self.assertEqual(record["actual_outcome"], "success")
        self.assertEqual(record["empirical_evidence_status"], "invalid_binding")
        self.assertEqual(record["acceptance_decision"], "reject")
        self.assertFalse(record["verified_success_eligibility"])
        self.assertEqual(record["joint_interpretation"], "unverified_success")

    def test_original_frozen_fixture_and_program_bytes_reconstruct_exactly(self) -> None:
        inputs = (
            REPOSITORY_ROOT
            / "experiments"
            / "substrates"
            / "minimal-reliable-execution-v0"
            / "inputs"
        )
        expected = {
            "task-contract.json": (
                1283,
                "d99571c5ed28b79ef5bb9880a078b02545f7e1d51df811934a95e385785266f2",
            ),
            "specialization-program.txt": (
                257,
                "30b56206f628174443bd2f7ae27e29530ac60c09ecf6d31b29c553ba5f99f242",
            ),
        }
        for name, (size, digest) in expected.items():
            content = (inputs / name).read_bytes()
            self.assertEqual(len(content), size, name)
            self.assertEqual(hashlib.sha256(content).hexdigest(), digest, name)


if __name__ == "__main__":
    unittest.main()
