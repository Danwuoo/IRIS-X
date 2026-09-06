from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock


SUBSTRATE = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = SUBSTRATE / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_admission as admission  # noqa: E402
import run_task_family_case as runner_module  # noqa: E402
import task_family  # noqa: E402
from model_adapter import TaskFamilyModelAdapter  # noqa: E402

from irisx.core.execution import bind_execution, execute, terminal_record_to_dict  # noqa: E402
from irisx.core.interfaces import ExecutorAdapter  # noqa: E402
from irisx.core.records import UNKNOWN, AdapterResourceReport  # noqa: E402


def event_stream(text: str) -> str:
    events = (
        {"type": "thread.started", "thread_id": "fixture-thread"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"id": "fixture-item", "type": "agent_message", "text": text},
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": 12,
                "reasoning_output_tokens": 4,
            },
        },
    )
    return "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in events)


class FrozenRunner:
    def __init__(self, output: str, *, returncode: int = 0) -> None:
        self.output = output
        self.returncode = returncode
        self.calls = 0
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        self.calls += 1
        self.commands.append(command)
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(self.output, encoding="utf-8")
        return subprocess.CompletedProcess(
            command,
            self.returncode,
            stdout=event_stream(self.output),
            stderr="" if self.returncode == 0 else "fixture provider failure",
        )


class DefinitionProxy:
    def __init__(self, base: task_family.FrozenTaskDefinition, run_dir: Path) -> None:
        self.base = base
        self.run_dir = run_dir

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base, name)


def admission_fixture() -> dict[str, Any]:
    return {
        "status": "admitted",
        "compatibility_profile_id": task_family.PROFILE_ID,
        "compatibility_profile_sha256": task_family.PROFILE_SHA256,
        "observed_cli_path": "C:/frozen/codex.cmd",
    }


class TaskFamilyQualificationTests(unittest.TestCase):
    def test_three_definitions_are_distinct_and_frozen(self) -> None:
        records = runner_module.validate_definitions()
        self.assertEqual(records["status"], "PASS")
        self.assertEqual(records["task_count"], 3)
        for field in ("task_id", "contract_id", "program_id", "schema_id", "verifier_id", "oracle_id"):
            self.assertEqual(len({item[field] for item in records["tasks"]}), 3, field)
        self.assertEqual(
            {item["configuration_id"] for item in records["tasks"]},
            {task_family.CONFIGURATION_ID},
        )

    def test_deterministic_oracles_derive_from_inputs(self) -> None:
        self.assertEqual(task_family.load_task("A").oracle, {"selected_ids": ["b", "d"]})
        self.assertEqual(task_family.load_task("B").oracle, {"total": 43})
        self.assertEqual(
            task_family.load_task("C").oracle,
            {"ranked": [{"id": "b", "rank": 1}, {"id": "c", "rank": 2}]},
        )

    def test_all_negative_output_fixtures_use_canonical_pipeline(self) -> None:
        case_count = 0
        for task_key, spec in task_family.TASK_SPECS.items():
            fixture = task_family.load_object(SUBSTRATE / spec["fixture_path"])
            self.assertEqual(fixture["task_key"], task_key)
            for case in fixture["cases"]:
                case_count += 1
                with self.subTest(task=task_key, case=case["name"]):
                    terminal, adapter = task_family.execute_offline(
                        task_key,
                        case["output"],
                        producer_claim=case["producer_claim"],
                    )
                    self.assertEqual(adapter.calls, 1)
                    self.assertEqual(terminal.verification.semantic_valid, case["expected_success"])
                    self.assertIn(case["expected_reason"], terminal.verification.semantic_reasons)
                    self.assertEqual(
                        terminal.joint_interpretation,
                        "verified_success" if case["expected_success"] else "correctly_recognized_failure",
                    )
        self.assertEqual(case_count, 27)

    def test_producer_success_claim_cannot_override_semantic_failure(self) -> None:
        terminal, _ = task_family.execute_offline("B", '{"total":44}', producer_claim="success")
        self.assertEqual(terminal.producer_claim, "success")
        self.assertEqual(terminal.actual_outcome, "failure")
        self.assertEqual(terminal.acceptance_decision, "reject")
        self.assertFalse(terminal.verified_success_eligibility)

    def test_schema_valid_wrong_answer_is_rejected(self) -> None:
        terminal, _ = task_family.execute_offline("A", '{"selected_ids":["a","d"]}')
        self.assertFalse(terminal.verification.semantic_valid)
        self.assertEqual(terminal.empirical_evidence_status, "sufficient")
        self.assertEqual(terminal.joint_interpretation, "correctly_recognized_failure")

    def test_resource_telemetry_does_not_affect_adjudication(self) -> None:
        first, _ = task_family.execute_offline("B", '{"total":43}')
        second, _ = task_family.execute_offline(
            "B",
            '{"total":43}',
            resource_report=AdapterResourceReport(
                model_calls=7,
                network_calls=9,
                paid_api_calls=5,
                tool_calls=3,
                route_count=2,
                wall_time_ns=123,
                provider_cost_usd=4.5,
            ),
        )
        adjudicated = (
            "actual_outcome",
            "acceptance_decision",
            "verified_success_eligibility",
            "joint_interpretation",
        )
        self.assertEqual(
            tuple(getattr(first, field) for field in adjudicated),
            tuple(getattr(second, field) for field in adjudicated),
        )

    def test_batch_5_run_03_replay_remains_admitted(self) -> None:
        record = admission.replay("03")
        self.assertEqual(record["status"], "admitted")
        self.assertEqual(record["live_model_calls"], 0)

    def test_rejected_admission_snapshot_prevents_runner_authorization(self) -> None:
        admission_root = task_family.TASK_FAMILY_ROOT / "admission"
        admission_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=admission_root) as temporary:
            path = Path(temporary) / "rejected.json"
            path.write_text(json.dumps({"status": "rejected", "reasons": ["fixture"]}), encoding="utf-8")
            with mock.patch.object(runner_module, "git", return_value="tracked"):
                with self.assertRaises(runner_module.TaskFamilyRunError):
                    runner_module.validate_admission_snapshot(path, refresh_current=False)

    def test_shared_adapter_uses_exact_admitted_command_and_one_call(self) -> None:
        base = task_family.load_task("A")
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            proxy = DefinitionProxy(base, Path(temporary) / "run")
            frozen_runner = FrozenRunner('{"selected_ids":["b","d"]}')
            adapter = TaskFamilyModelAdapter(
                definition=proxy,
                admission_record=admission_fixture(),
                admission_record_path=Path("task-family/admission/fixture.json"),
                admission_record_sha256="1" * 64,
                definition_code_freeze_sha="1" * 40,
                launch_head="2" * 40,
                runner=frozen_runner,
            )
            context = bind_execution(
                base.core_contract(), base.program_artifact(), base.execution_identity()
            )
            result = adapter.execute(context, base.execution_request(), base.initial_state())
            self.assertEqual(result.resource_report.model_calls, 1)
            self.assertEqual(result.resource_report.retry_count, 0)
            self.assertEqual(frozen_runner.calls, 1)
            normalized = admission.normalize_command(frozen_runner.commands[0])
            self.assertEqual(normalized, admission.load_object(admission.PROFILE_PATH)["canonical_argv"])
            with self.assertRaises(ValueError):
                adapter.execute(context, base.execution_request(), base.initial_state())
            self.assertEqual(frozen_runner.calls, 1)

    def test_adapter_is_one_executor_protocol_for_all_tasks(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            for key in task_family.TASK_SPECS:
                base = task_family.load_task(key)
                adapter = TaskFamilyModelAdapter(
                    definition=DefinitionProxy(base, Path(temporary) / key),
                    admission_record=admission_fixture(),
                    admission_record_path=Path("task-family/admission/fixture.json"),
                    admission_record_sha256="1" * 64,
                    definition_code_freeze_sha="1" * 40,
                    launch_head="2" * 40,
                    runner=FrozenRunner(json.dumps(base.oracle)),
                )
                self.assertIsInstance(adapter, ExecutorAdapter)

    def test_synthetic_finalize_binds_admission_freeze_and_launch(self) -> None:
        base = task_family.load_task("B")
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            temp_root = Path(temporary)
            proxy = DefinitionProxy(base, temp_root / "run")
            admission_path = temp_root / "admission.json"
            admission_path.write_text(json.dumps(admission_fixture()), encoding="utf-8")
            frozen_runner = FrozenRunner('{"total":43}')
            adapter = TaskFamilyModelAdapter(
                definition=proxy,
                admission_record=admission_fixture(),
                admission_record_path=Path(runner_module.repository_relative(admission_path)),
                admission_record_sha256=task_family.sha256_bytes(admission_path.read_bytes()),
                definition_code_freeze_sha="1" * 40,
                launch_head="2" * 40,
                runner=frozen_runner,
            )
            terminal = execute(
                contract=base.core_contract(),
                program=base.program_artifact(),
                supplied_identity=base.execution_identity(),
                request=base.execution_request(),
                state=base.initial_state(),
                executor=adapter,
                verifier=task_family.verifier_for(base),
            )
            runner_module.finalize_run(
                definition=proxy,
                adapter=adapter,
                terminal=terminal_record_to_dict(terminal),
                admission_record=admission_fixture(),
                admission_record_path=admission_path,
                admission_record_sha256=task_family.sha256_bytes(admission_path.read_bytes()),
                definition_code_freeze_sha="1" * 40,
                launch_head="2" * 40,
            )
            manifest = task_family.load_object(proxy.run_dir / "run-manifest.json")
            binding = manifest["admission_binding"]
            self.assertEqual(binding["admission_profile_sha256"], task_family.PROFILE_SHA256)
            self.assertEqual(
                binding["admission_record_sha256"],
                task_family.sha256_bytes(admission_path.read_bytes()),
            )
            self.assertEqual(manifest["definition_code_freeze_sha"], "1" * 40)
            self.assertEqual(manifest["launch_head"], "2" * 40)
            with mock.patch.object(runner_module, "load_task", return_value=proxy), mock.patch.object(
                runner_module, "require_full_commit"
            ):
                validated = runner_module.validate_run("B")
            self.assertEqual(validated["status"], "PASS")
            self.assertEqual(validated["classification"], "verified_success")

    def test_batch_summary_aggregates_only_observed_values(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            roots: dict[str, SimpleNamespace] = {}
            results: dict[str, dict[str, Any]] = {}
            for index, key in enumerate(task_family.TASK_SPECS, start=1):
                run_dir = Path(temporary) / key
                run_dir.mkdir()
                (run_dir / "terminal-record.json").write_text(f"terminal-{key}", encoding="utf-8")
                roots[key] = SimpleNamespace(run_dir=run_dir)
                tokens: dict[str, int | str] = {
                    "input_tokens": 100 * index,
                    "cached_input_tokens": 0,
                    "cache_write_input_tokens": 0,
                    "output_tokens": 10 * index,
                    "reasoning_tokens": 0,
                }
                if key == "C":
                    tokens["output_tokens"] = UNKNOWN
                resource = {
                    "model_calls": 1,
                    "provider_attempts": 1,
                    "token_usage": tokens,
                    "wall_time_ns": index,
                    "retry_count": 0,
                    "route_count": 0,
                    "fallback_count": 0,
                    "escalation_count": 0,
                    "recovery_count": 0,
                    "tool_calls": 0,
                    "provider_cost_usd": UNKNOWN,
                }
                results[key] = {
                    "status": "PASS",
                    "task_key": key,
                    "run_id": task_family.TASK_SPECS[key]["run_id"],
                    "classification": "verified_success",
                    "terminal_semantics": {"terminal_execution_status": "completed"},
                    "resource_record": resource,
                }
            with mock.patch.object(
                runner_module, "load_task", side_effect=lambda key: roots[key]
            ), mock.patch.object(
                runner_module, "validate_run", side_effect=lambda key: results[key]
            ):
                summary = runner_module.build_summary()
            self.assertEqual(summary["total_model_calls"], 3)
            self.assertEqual(summary["total_token_usage"]["input_tokens"], 600)
            self.assertEqual(summary["total_token_usage"]["output_tokens"], UNKNOWN)
            self.assertEqual(summary["total_wall_time_ns"], 6)
            self.assertEqual(summary["provider_cost_usd"], UNKNOWN)
            self.assertTrue(summary["architecture_exercise_accepted"])
            self.assertTrue(summary["full_task_family_qualification"])
            for field in (
                "total_retries",
                "total_routes",
                "total_fallbacks",
                "total_escalations",
                "total_recovery_actions",
                "total_tool_calls",
            ):
                self.assertEqual(summary[field], 0, field)

    def test_missing_token_values_remain_unknown(self) -> None:
        self.assertEqual(runner_module._observed_sum([1, UNKNOWN, 2]), UNKNOWN)
        self.assertEqual(runner_module._observed_sum([1, 2, 3]), 6)

    def test_core_remains_free_of_provider_specific_implementation(self) -> None:
        for path in sorted((REPOSITORY_ROOT / "irisx" / "core").glob("*.py")):
            source = path.read_text(encoding="utf-8").lower()
            for token in ("openai", "codex", "gpt-5.6-luna", "admissiongate"):
                self.assertNotIn(token, source, f"{token} leaked into {path}")


if __name__ == "__main__":
    unittest.main()
