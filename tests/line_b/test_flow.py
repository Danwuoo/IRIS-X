from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from irisx.artifacts import validate_artifact  # noqa: E402
from irisx.canonical import read_json  # noqa: E402
from irisx.contracts import DomainPackageManifest, EngineeringTrial, EvaluationResult, WorkloadDefinition, load_contract  # noqa: E402
from irisx.domains.line_b import flow  # noqa: E402
from irisx.errors import ValidationError  # noqa: E402
from irisx.fixture import prepare_fixture, run_trial  # noqa: E402
from irisx.package import build_package, verify_package  # noqa: E402


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


PROCESS = r'''
import importlib.abc, json, pathlib, sys, time
source, mode, output, barrier = sys.argv[1:]
sys.path.insert(0, source)
class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("irisx.arc") or fullname.startswith("irisx.kaggle") or fullname.startswith("irisx.domains.arc") or fullname == "tools" or fullname.startswith("tools.") or fullname.split(".")[0] in {"torch","transformers","numpy","peft","kaggle","huggingface_hub","tensorflow"}:
            raise AssertionError("domain boundary violated: " + fullname)
sys.meta_path.insert(0, Blocker())
output = pathlib.Path(output)
if barrier:
    barrier = pathlib.Path(barrier)
    (barrier / mode).write_text("ready")
    deadline = time.monotonic() + 15
    while not all((barrier / name).is_file() for name in ("core", "line-b")):
        if time.monotonic() >= deadline:
            raise AssertionError("concurrent fixture barrier timed out")
        time.sleep(0.01)
if mode == "line-b":
    from irisx.domains.line_b.flow import run
    report = run(output)
else:
    from irisx.fixture import prepare_fixture, run_trial
    from irisx.package import build_package, verify_package
    output.mkdir()
    prepare_fixture(output / "fixture")
    report = run_trial(output / "fixture/trial.json", output / "run")
    build_package(output / "run", output / "package")
    verify_package(output / "package")
print(json.dumps(report))
'''


class LineBFlowTests(unittest.TestCase):
    def test_complete_graph_uses_independent_ids_and_fixed_profile_exceptions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "line-b"
            report = flow.run(root)
            self.assertEqual(report["outcome"], "promote")
            self.assertTrue(report["package_created"])
            self.assertEqual(report["real_domain"], "unassigned")
            self.assertEqual(report["independent_review"], "pending")
            for path in sorted((root / "fixture").glob("*.json")):
                self.assertTrue(read_json(path)["artifact_id"].startswith("line-b-synthetic-"), path)
            workload = load_contract(root / "run/workload.json", WorkloadDefinition)
            self.assertEqual(len(workload.payload["cases"]), 6)
            self.assertTrue(all(case["case_id"].startswith("line-b-synthetic-") for case in workload.payload["cases"]))
            baseline = load_contract(root / "run/results/line-b-synthetic-baseline-result.json", EvaluationResult)
            candidate = load_contract(root / "run/results/line-b-synthetic-candidate-result.json", EvaluationResult)
            self.assertEqual(baseline.payload["metrics"]["accuracy"]["value"], 2 / 6)
            self.assertEqual(baseline.payload["metrics"]["critical_failures"]["value"], 1)
            self.assertEqual(candidate.payload["metrics"]["accuracy"]["value"], 1)
            for name in ("network_calls", "provider_calls", "monetary_cost"):
                self.assertEqual(candidate.payload["resource_use"][name]["value"], 0)
            self.assertEqual(candidate.payload["resource_use"]["gpu_seconds"]["state"], "unknown")
            manifest = verify_package(root / "package")
            self.assertEqual(manifest.artifact_id, "line-b-synthetic-domain-package")
            deployment = validate_artifact(read_json(root / "package/deployment/metadata.json"))
            self.assertEqual(deployment["artifact_id"], "qualification-deployment-placeholder")
            self.assertFalse(deployment["payload"]["deployable"])
            self.assertEqual(read_json(root / "package/known-limitations.json")["artifact_id"], "qualification-known-limitations")

    def test_two_complete_runs_have_identical_canonical_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            one, two = Path(temporary) / "one", Path(temporary) / "two"
            self.assertEqual(flow.run(one), flow.run(two))
            self.assertEqual(tree_bytes(one), tree_bytes(two))

    def test_rebound_summary_and_decision_are_consistent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "line-b"
            report = flow.run(root)
            summary = validate_artifact(read_json(root / "run/run-summary.json"))
            decision = read_json(root / "run/decision.json")
            self.assertEqual(summary["artifact_id"], "line-b-synthetic-run-summary")
            self.assertEqual(summary["payload"]["decision_digest"], decision["content_digest"])
            self.assertEqual(report["decision_digest"], decision["content_digest"])
            self.assertEqual(read_json(root / "run/verdicts.json")["artifact_id"], "line-b-synthetic-verdicts")

    def test_unmet_requirements_remain_infeasible_and_package_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "unmet"
            report = flow.run(root, "unmet")
            self.assertEqual(report["outcome"], "infeasible")
            self.assertFalse(report["package_created"])
            self.assertIsNone(report["package_digest"])
            self.assertFalse((root / "package").exists())
            with self.assertRaisesRegex(ValidationError, "requires a promote decision"):
                build_package(root / "run", root / "refused-package")

    def test_missing_generated_component_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "missing"
            with self.assertRaisesRegex(ValidationError, "referenced evidence is missing"):
                flow.run(root, "missing")
            self.assertFalse((root / "fixture/candidate-component.json").exists())
            self.assertFalse((root / "package").exists())

    def test_missing_generated_result_prevents_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "line-b"
            flow.run(root)
            (root / "run/results/line-b-synthetic-candidate-result.json").unlink()
            with self.assertRaisesRegex(ValidationError, "referenced evidence is missing"):
                build_package(root / "run", root / "missing-result-package")

    def test_package_tampering_and_extra_payload_are_rejected(self):
        for variant in ("tamper", "extra"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "line-b"
                flow.run(root)
                if variant == "tamper":
                    target = root / "package/evaluation/results/line-b-synthetic-candidate-result.json"
                    target.write_bytes(target.read_bytes() + b" ")
                    message = "digest mismatch"
                else:
                    (root / "package/undeclared.txt").write_bytes(b"not admitted")
                    message = "unexpected files"
                with self.assertRaisesRegex(ValidationError, message):
                    verify_package(root / "package")

    def test_existing_output_and_invalid_variant_preserve_owned_sentinel(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sentinel = root / "sentinel"
            sentinel.write_bytes(b"preserve")
            for function in (flow.prepare, flow.run):
                with self.assertRaisesRegex(ValidationError, "already exists"):
                    function(root)
                with self.assertRaisesRegex(ValidationError, "unknown"):
                    function(root / "new", "not-a-variant")
            self.assertEqual(sentinel.read_bytes(), b"preserve")
            self.assertFalse((root / "new").exists())

    def test_shared_evaluator_selection_and_package_are_called_without_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(flow, "run_trial", wraps=run_trial) as evaluation, \
                 mock.patch.object(flow, "select_configuration", wraps=flow.select_configuration) as selection, \
                 mock.patch.object(flow, "build_package", wraps=build_package) as build, \
                 mock.patch.object(flow, "verify_package", wraps=verify_package) as verify, \
                 mock.patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), \
                 mock.patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
                flow.run(Path(temporary) / "line-b")
            self.assertEqual(evaluation.call_count, 1)
            self.assertEqual(selection.call_count, 1)
            self.assertEqual(build.call_count, 1)
            self.assertEqual(verify.call_count, 1)

    def test_fresh_process_runs_without_arc_tools_or_ml(self):
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        for optimized in (False, True):
            with self.subTest(optimized=optimized), tempfile.TemporaryDirectory() as temporary:
                command = [sys.executable, *( ["-O"] if optimized else []), "-I", "-B", "-c", PROCESS,
                           str(ROOT / "src"), "line-b", str(Path(temporary) / "line-b"), ""]
                result = subprocess.run(command, cwd=temporary, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["outcome"], "promote")

    def test_concurrent_core_and_line_b_have_distinct_ids_and_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            barrier = root / "barrier"
            barrier.mkdir()
            processes = []
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            try:
                for mode in ("core", "line-b"):
                    processes.append(subprocess.Popen([sys.executable, "-I", "-B", "-c", PROCESS, str(ROOT / "src"), mode,
                                                      str(root / mode), str(barrier)], cwd=root, env=environment,
                                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8"))
                for process in processes:
                    stdout, stderr = process.communicate(timeout=30)
                    self.assertEqual(process.returncode, 0, stderr)
                    self.assertEqual(json.loads(stdout)["outcome"], "promote")
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()
            trials = [load_contract(root / mode / "run/trial.json", EngineeringTrial) for mode in ("core", "line-b")]
            workloads = [load_contract(root / mode / "run/workload.json", WorkloadDefinition) for mode in ("core", "line-b")]
            self.assertNotEqual(trials[0].artifact_id, trials[1].artifact_id)
            self.assertNotEqual(workloads[0].artifact_id, workloads[1].artifact_id)
            self.assertTrue(set(case["case_id"] for case in workloads[0].payload["cases"]).isdisjoint(case["case_id"] for case in workloads[1].payload["cases"]))
            self.assertEqual(len(workloads[0].payload["cases"]), 4)
            self.assertEqual(len(workloads[1].payload["cases"]), 6)
            self.assertNotEqual(verify_package(root / "core/package").content_digest, verify_package(root / "line-b/package").content_digest)

    def test_cli_reports_unmet_and_missing_without_success_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(flow.main(["--output", str(root / "unmet"), "--variant", "unmet"]), 0)
            self.assertFalse(json.loads(stdout.getvalue())["package_created"])
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(flow.main(["--output", str(root / "missing"), "--variant", "missing"]), 2)
            self.assertEqual(json.loads(stderr.getvalue())["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
