from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
ROOT = EXPERIMENT_ROOT.parents[1]
DEFINITION = json.loads(
    (EXPERIMENT_ROOT / "inputs" / "experiment-definition.json").read_text(encoding="utf-8")
)
MANIFEST = json.loads((ROOT / DEFINITION["task_manifest_path"]).read_text(encoding="utf-8"))
WORKER = EXPERIMENT_ROOT / "scripts" / "worker.py"
RUNNER = EXPERIMENT_ROOT / "scripts" / "run_experiment.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProcessLifetimeDefinitionTests(unittest.TestCase):
    def test_frozen_horizon_and_task_order(self) -> None:
        self.assertEqual(DEFINITION["sequence_passes"], 20)
        self.assertEqual(DEFINITION["expected_total_episodes"], 480)
        self.assertEqual(DEFINITION["task_order"], [task["task_id"] for task in MANIFEST["tasks"]])
        self.assertEqual(len(DEFINITION["task_order"]), 12)

    def test_manifest_hash_is_frozen(self) -> None:
        payload = (ROOT / DEFINITION["task_manifest_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), DEFINITION["task_manifest_sha256"])

    def test_request_bytes_do_not_contain_arm_or_sequence(self) -> None:
        runner = load_module("hor1a_runner", RUNNER)
        request = runner.task_request(MANIFEST["tasks"][0])
        serialized = runner.canonical_json_bytes(request)
        self.assertNotIn(b"fresh-process", serialized)
        self.assertNotIn(b"long-lived-process", serialized)
        self.assertNotIn(b"pass", serialized)
        self.assertNotIn(b"position", serialized)

    def test_worker_modes_have_identical_response_core(self) -> None:
        runner = load_module("hor1a_runner_worker_test", RUNNER)
        request_bytes = runner.canonical_json_bytes(runner.task_request(MANIFEST["tasks"][0]))
        first = subprocess.run(
            [sys.executable, str(WORKER), "--single"],
            input=request_bytes,
            check=True,
            stdout=subprocess.PIPE,
        )
        server = subprocess.Popen(
            [sys.executable, str(WORKER), "--server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        assert server.stdin is not None and server.stdout is not None
        server.stdin.write(request_bytes.decode("utf-8") + "\n")
        server.stdin.close()
        second_line = server.stdout.readline()
        server.wait(timeout=10)
        server.stdout.close()
        first_response = json.loads(first.stdout.decode("utf-8"))
        second_response = json.loads(second_line)
        self.assertEqual(first_response["core"], second_response["core"])
        self.assertEqual(first_response["worker_sequence_counter"], 1)
        self.assertEqual(second_response["worker_sequence_counter"], 1)

    def test_aggregate_reconstructs_stable_synthetic_records(self) -> None:
        runner = load_module("hor1a_runner_aggregate_test", RUNNER)
        records = []
        for pass_index in range(1, 21):
            for position, task_id in enumerate(DEFINITION["task_order"], start=1):
                for arm in DEFINITION["arms"]:
                    counter = 1 if arm == "fresh-process-v0" else (pass_index - 1) * 12 + position
                    records.append(
                        {
                            "configuration_id": arm,
                            "task_or_action_id": task_id,
                            "cycle_or_sequence_index": {"pass": pass_index, "position": position},
                            "request_sha256": "a" * 64,
                            "response_core_sha256": task_id,
                            "actual_outcome": "success",
                            "empirical_evidence_status": "sufficient",
                            "terminal_execution_status": "completed",
                            "verified_success_eligibility": True,
                            "invalid_reason": None,
                            "worker_pid": 1 if arm == "long-lived-process-v0" else counter + 1000,
                            "worker_sequence_counter": counter,
                            "resource": {
                                "worker_wall_ns": 1,
                                "worker_cpu_ns": 1,
                                "orchestration_wall_ns": 1,
                                "bytes_read": 1,
                                "output_bytes": 1,
                            },
                        }
                    )
        results = runner.derive_results(records, DEFINITION)
        self.assertTrue(results["valid"])
        self.assertEqual(results["result_status"], "Stable under declared horizon")
        self.assertEqual(results["sequence_drift_records"], [])
        self.assertEqual(results["cross_arm_mismatches"], [])


if __name__ == "__main__":
    unittest.main()
