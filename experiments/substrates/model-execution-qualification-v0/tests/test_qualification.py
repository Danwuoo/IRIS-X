from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SUBSTRATE = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = SUBSTRATE / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_qualification as qualification  # noqa: E402

from irisx.core.interfaces import ExecutorAdapter  # noqa: E402
from irisx.core.records import UNKNOWN  # noqa: E402


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

    def __call__(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls += 1
        self.commands.append(command)
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(self.output, encoding="utf-8")
        return subprocess.CompletedProcess(
            command,
            self.returncode,
            stdout=event_stream(self.output),
            stderr="" if self.returncode == 0 else "frozen provider failure",
        )


def preflight_fixture() -> dict[str, Any]:
    return {
        "codex_cli_resolved_path": "C:/frozen/codex.cmd",
        "codex_cli_version": "codex-cli 0.147.0",
        "checked_at": "2026-09-05T00:00:00+00:00",
    }


def run_fixture(output: str, *, returncode: int = 0) -> tuple[dict[str, Any], FrozenRunner]:
    runner = FrozenRunner(output, returncode=returncode)
    with tempfile.TemporaryDirectory() as temporary:
        adapter = qualification.CodexModelExecutorAdapter(
            run_dir=Path(temporary) / "run",
            preflight_record=preflight_fixture(),
            definition_commit="1" * 40,
            code_commit="1" * 40,
            runner=runner,
        )
        record = qualification.execute_with_adapter(adapter)
    return record, runner


class ModelExecutionQualificationTests(unittest.TestCase):
    def test_model_adapter_satisfies_executor_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            adapter = qualification.CodexModelExecutorAdapter(
                run_dir=Path(temporary) / "run",
                preflight_record=preflight_fixture(),
                definition_commit="1" * 40,
                code_commit="1" * 40,
                runner=FrozenRunner('{"selected_id":"alpha"}'),
            )
            self.assertIsInstance(adapter, ExecutorAdapter)

    def test_prompt_is_deterministic_from_frozen_inputs(self) -> None:
        first = qualification.build_prompt().encode("utf-8")
        second = qualification.build_prompt().encode("utf-8")
        self.assertEqual(first, second)
        self.assertEqual(
            hashlib.sha256(first).hexdigest(),
            "b3d7aa200d23c6791fbe453bd83e5b8b91700abae58b8bc67794150320a8a52b",
        )

    def test_provider_command_freezes_model_envelope_and_zero_retries(self) -> None:
        command = qualification.build_provider_command(
            "C:/frozen/codex.cmd",
            Path("C:/isolated"),
            Path("C:/isolated/schema.json"),
            Path("C:/isolated/model-catalog.json"),
            Path("C:/isolated/output.txt"),
        )
        self.assertEqual(command[0:2], ["C:/frozen/codex.cmd", "exec"])
        self.assertIn("gpt-5.6-luna", command)
        self.assertIn('model_reasoning_effort="medium"', command)
        self.assertIn(
            "model_catalog_json="
            + json.dumps(str(Path("C:/isolated/model-catalog.json"))),
            command,
        )
        self.assertIn('model_provider="irisx_openai_no_retry"', command)
        self.assertIn(
            'model_providers.irisx_openai_no_retry.name="OpenAI"', command
        )
        self.assertIn(
            "model_providers.irisx_openai_no_retry.requires_openai_auth=true",
            command,
        )
        self.assertIn(
            "model_providers.irisx_openai_no_retry.request_max_retries=0",
            command,
        )
        self.assertIn(
            "model_providers.irisx_openai_no_retry.stream_max_retries=0",
            command,
        )
        self.assertIn(
            "model_providers.irisx_openai_no_retry.supports_websockets=false",
            command,
        )
        self.assertNotIn("model_providers.openai.request_max_retries=0", command)
        self.assertIn('web_search="disabled"', command)
        self.assertIn("tools.web_search=false", command)
        self.assertNotIn("tools.view_image=false", command)
        self.assertIn("shell_tool", command)
        self.assertIn("apply_patch_freeform", command)
        self.assertIn("tool_search", command)
        self.assertIn("responses_websockets", command)
        self.assertIn("view_image", command)
        self.assertEqual(command[command.index("view_image") - 1], "--disable")
        self.assertIn("multi_agent", command)
        self.assertEqual(command.count("--sandbox"), 1)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")

    def test_strict_config_probe_matches_live_config_without_model_execution(self) -> None:
        catalog = Path("C:/isolated/model-catalog.json")
        arguments = qualification.codex_config_arguments(catalog)
        command = qualification.build_strict_config_probe_command(
            "C:/frozen/codex.cmd", catalog
        )
        self.assertEqual(command[0:2], ["C:/frozen/codex.cmd", "app-server"])
        self.assertIn("--strict-config", command)
        self.assertEqual(command[command.index("--listen") + 1], "off")
        self.assertNotIn("exec", command)
        self.assertEqual(command[-len(arguments) :], arguments)

    def test_strict_config_probe_accepts_only_post_load_sentinel(self) -> None:
        accepted = subprocess.CompletedProcess(
            ["codex", "app-server"],
            1,
            stdout="",
            stderr=(
                "WARNING: isolated CODEX_HOME has no path aliases\n"
                + qualification.STRICT_CONFIG_PROBE_SENTINEL
                + "\n"
            ),
        )
        qualification.validate_strict_config_probe_result(accepted)
        rejected = subprocess.CompletedProcess(
            ["codex", "app-server"],
            1,
            stdout="",
            stderr="Error: unknown configuration field `tools.view_image`\n",
        )
        with self.assertRaises(qualification.QualificationError):
            qualification.validate_strict_config_probe_result(rejected)

    def test_api_key_fallback_is_absent_from_child_environment(self) -> None:
        child = qualification.codex_environment()
        for name in qualification.API_ENVIRONMENT_NAMES:
            self.assertNotIn(name, child)

    def test_frozen_success_events_parse_to_raw_result_and_usage(self) -> None:
        content = (SUBSTRATE / "fixtures" / "provider-events-success.jsonl").read_bytes()
        events, errors = qualification.parse_provider_events(content)
        self.assertEqual(errors, 0)
        self.assertEqual(qualification.final_agent_message(events), '{"selected_id":"alpha"}')
        self.assertEqual(qualification.extract_usage(events)["input_tokens"], 100)
        audit = qualification.audit_provider_events(events)
        self.assertFalse(audit["tool_attempted"])
        self.assertEqual(audit["retry_event_count"], 0)
        self.assertEqual(audit["route_event_count"], 0)
        self.assertEqual(audit["fallback_event_count"], 0)

    def test_retry_route_and_fallback_events_are_detected(self) -> None:
        events = [
            {"type": "stream.retry", "message": "Reconnecting..."},
            {"type": "model_reroute", "from_model": "a", "to_model": "b"},
            {"type": "warning", "message": "Falling back from WebSockets"},
        ]
        audit = qualification.audit_provider_events(events)
        self.assertEqual(audit["retry_event_count"], 1)
        self.assertEqual(audit["route_event_count"], 1)
        self.assertEqual(audit["fallback_event_count"], 1)

    def test_repair_definition_uses_custom_provider_without_api_key_fields(self) -> None:
        identity, contract = qualification.validate_frozen_definition()
        provider = contract["provider_configuration"]
        self.assertEqual(provider["provider_id"], "openai")
        self.assertEqual(
            provider["codex_model_provider_config_id"], "irisx_openai_no_retry"
        )
        self.assertIsNone(identity["codex_model_provider_base_url"])
        arguments = qualification.codex_config_arguments(
            Path("C:/isolated/model-catalog.json")
        )
        rendered = "\n".join(arguments)
        self.assertNotIn("env_key", rendered)
        self.assertNotIn("experimental_bearer_token", rendered)
        self.assertNotIn("base_url", rendered)
        catalog = json.loads(qualification.MODEL_CATALOG_PATH.read_bytes())
        self.assertEqual(len(catalog["models"]), 1)
        model = catalog["models"][0]
        self.assertEqual(model["shell_type"], "disabled")
        self.assertIsNone(model["apply_patch_tool_type"])
        self.assertFalse(model["supports_search_tool"])
        self.assertEqual(model["experimental_supported_tools"], [])

    def test_original_failed_run_remains_valid_and_immutable(self) -> None:
        original = SUBSTRATE / "runs" / qualification.ORIGINAL_RUN_ID
        result = qualification.validate_run_artifacts(original)
        self.assertEqual(result["run_id"], qualification.ORIGINAL_RUN_ID)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(
            result["terminal_semantics"]["terminal_execution_status"], "failed"
        )

    def test_correct_output_becomes_verified_success(self) -> None:
        record, runner = run_fixture('{"selected_id":"alpha"}')
        self.assertEqual(runner.calls, 1)
        self.assertEqual(record["actual_outcome"], "success")
        self.assertEqual(record["producer_claim"], "success")
        self.assertEqual(record["empirical_evidence_status"], "sufficient")
        self.assertEqual(record["acceptance_decision"], "accept")
        self.assertTrue(record["verified_success_eligibility"])
        self.assertEqual(record["joint_interpretation"], "verified_success")
        self.assertEqual(record["terminal_execution_status"], "completed")

    def test_malformed_output_is_verifier_detected_failure(self) -> None:
        record, runner = run_fixture("not-json")
        self.assertEqual(runner.calls, 1)
        self.assertEqual(record["producer_claim"], "success")
        self.assertEqual(record["actual_outcome"], "failure")
        self.assertEqual(record["acceptance_decision"], "reject")
        self.assertFalse(record["verified_success_eligibility"])
        self.assertIn("provider_output_malformed_json", record["verification"]["semantic_reasons"])

    def test_wrong_structured_output_is_rejected(self) -> None:
        record, _ = run_fixture('{"selected_id":"beta"}')
        self.assertEqual(record["producer_claim"], "success")
        self.assertEqual(record["actual_outcome"], "failure")
        self.assertEqual(record["acceptance_decision"], "reject")
        self.assertFalse(record["verified_success_eligibility"])
        self.assertEqual(record["joint_interpretation"], "correctly_recognized_failure")

    def test_evidence_is_emitted_from_bound_execution_context(self) -> None:
        record, _ = run_fixture('{"selected_id":"alpha"}')
        expected = {
            "task_contract": hashlib.sha256(
                qualification.CONTRACT_PATH.read_bytes()
            ).hexdigest(),
            "program": hashlib.sha256(
                (SUBSTRATE / "inputs" / "model-program.txt").read_bytes()
            ).hexdigest(),
        }
        self.assertEqual(
            {item["role"]: item["sha256"] for item in record["evidence"]},
            expected,
        )

    def test_read_only_task_state_remains_unchanged(self) -> None:
        record, _ = run_fixture('{"selected_id":"alpha"}')
        effects = record["side_effects"]
        self.assertEqual(effects["state_before_sha256"], effects["state_after_sha256"])
        self.assertEqual(effects["changed_paths"], [])
        self.assertFalse(effects["mutation_primitive_executed"])

    def test_observed_model_invocation_cannot_report_zero_model_calls(self) -> None:
        record, _ = run_fixture('{"selected_id":"alpha"}')
        resources = record["resource_ledger"]
        self.assertEqual(resources["model_calls"], 1)
        self.assertEqual(resources["network_calls"], UNKNOWN)
        self.assertIsInstance(resources["wall_time_ns"], int)
        self.assertGreater(resources["wall_time_ns"], 0)
        self.assertEqual(resources["provider_cost_usd"], UNKNOWN)

    def test_retry_route_escalation_recovery_and_tools_remain_zero(self) -> None:
        record, _ = run_fixture('{"selected_id":"alpha"}')
        resources = record["resource_ledger"]
        for field in (
            "retry_count",
            "route_count",
            "escalation_count",
            "recovery_count",
            "tool_calls",
        ):
            self.assertEqual(resources[field], 0, field)
        self.assertFalse(record["recovery"]["silent_retry"])

    def test_provider_process_failure_preserves_model_usage_and_fails_closed(self) -> None:
        record, runner = run_fixture("", returncode=1)
        self.assertEqual(runner.calls, 1)
        self.assertEqual(record["actual_outcome"], "failure")
        self.assertEqual(record["terminal_execution_status"], "failed")
        self.assertEqual(record["resource_ledger"]["model_calls"], 1)
        self.assertEqual(record["resource_ledger"]["retry_count"], 0)

    def test_adapter_has_no_retry_loop_and_refuses_second_invocation(self) -> None:
        runner = FrozenRunner('{"selected_id":"alpha"}')
        with tempfile.TemporaryDirectory() as temporary:
            adapter = qualification.CodexModelExecutorAdapter(
                run_dir=Path(temporary) / "run",
                preflight_record=preflight_fixture(),
                definition_commit="1" * 40,
                code_commit="1" * 40,
                runner=runner,
            )
            qualification.execute_with_adapter(adapter)
            second = qualification.execute_with_adapter(adapter)
            self.assertEqual(second["actual_outcome"], "failure")
            self.assertEqual(second["terminal_execution_status"], "failed")
        self.assertEqual(runner.calls, 1)
        source = (SCRIPT_DIR / "run_qualification.py").read_text(encoding="utf-8")
        self.assertNotIn("for attempt", source)
        self.assertNotIn("while attempt", source)

    def test_core_contains_no_provider_specific_implementation(self) -> None:
        forbidden = ("openai", "codex", "gpt-5.6-luna")
        for path in sorted((REPOSITORY_ROOT / "irisx" / "core").glob("*.py")):
            source = path.read_text(encoding="utf-8").lower()
            for token in forbidden:
                self.assertNotIn(token, source, f"{token} leaked into {path}")


if __name__ == "__main__":
    unittest.main()
