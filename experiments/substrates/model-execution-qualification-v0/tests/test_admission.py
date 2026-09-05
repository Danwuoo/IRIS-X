from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SUBSTRATE = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = SUBSTRATE / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_admission as admission  # noqa: E402


class ModelExecutionAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = admission.load_object(admission.PROFILE_PATH)

    def candidate(self) -> dict[str, object]:
        return copy.deepcopy(admission.historical_candidate("03"))

    @staticmethod
    def replace_config(command: list[str], key: str, value: str) -> None:
        for index, item in enumerate(command):
            if index > 0 and command[index - 1] == "--config" and item.startswith(key + "="):
                command[index] = f"{key}={value}"
                return
        raise AssertionError(f"missing config key {key}")

    def test_profile_authorizes_no_model_calls(self) -> None:
        self.assertFalse(self.profile["authorization"]["model_calls_authorized"])
        self.assertTrue(self.profile["authorization"]["admission_only"])

    def test_exact_run_01_rejects_reserved_provider_configuration(self) -> None:
        record = admission.replay("01")
        self.assertEqual(record["status"], "rejected")
        self.assertEqual(record["reasons"], ["reserved_provider_configuration_incompatible"])
        self.assertEqual(record["live_model_calls"], 0)

    def test_exact_run_02_rejects_tools_view_image(self) -> None:
        record = admission.replay("02")
        self.assertEqual(record["status"], "rejected")
        self.assertEqual(record["reasons"], ["unsupported_config_field:tools.view_image"])
        self.assertEqual(record["live_model_calls"], 0)

    def test_exact_run_03_is_admitted(self) -> None:
        record = admission.replay("03")
        self.assertEqual(record["status"], "admitted")
        self.assertEqual(record["reasons"], [])
        self.assertEqual(record["live_model_calls"], 0)

    def test_run_03_command_identity_matches_profile(self) -> None:
        record = admission.replay("03")
        self.assertEqual(record["command_sha256"], record["expected_command_sha256"])
        self.assertEqual(record["canonical_command"], self.profile["canonical_argv"])

    def test_canonical_command_identity_is_deterministic(self) -> None:
        command = self.candidate()["command"]
        first = admission.normalize_command(command)
        second = admission.normalize_command(command)
        self.assertEqual(first, second)
        self.assertEqual(
            admission.sha256_bytes(admission.canonical_json_bytes(first)),
            admission.sha256_bytes(admission.canonical_json_bytes(second)),
        )

    def test_historical_replay_does_not_modify_artifacts(self) -> None:
        paths = sorted((SUBSTRATE / "runs").glob("qualification-20260905-0[123]/*"))
        before = {path: admission.sha256_bytes(path.read_bytes()) for path in paths if path.is_file()}
        admission.replay("01")
        admission.replay("02")
        admission.replay("03")
        after = {path: admission.sha256_bytes(path.read_bytes()) for path in paths if path.is_file()}
        self.assertEqual(before, after)

    def test_version_drift_is_unsupported(self) -> None:
        candidate = self.candidate()
        candidate["preflight"]["codex_cli_version"] = "codex-cli 0.148.0"
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "unsupported")
        self.assertEqual(record["reasons"], ["unsupported_version"])

    def test_executable_path_drift_is_unsupported(self) -> None:
        candidate = self.candidate()
        candidate["preflight"]["codex_cli_resolved_path"] = "C:/different/codex.cmd"
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "unsupported")
        self.assertIn("unsupported_executable_path", record["reasons"])

    def test_provider_baseline_identity_hash_drift_rejects(self) -> None:
        candidate = self.candidate()
        candidate["identity"]["provider_baseline_sha256"] = "0" * 64
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "rejected")
        self.assertIn("provider_baseline_identity_hash_mismatch", record["reasons"])

    def test_provider_baseline_file_hash_drift_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            drifted = Path(temporary) / "baseline.json"
            drifted.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(admission, "BASELINE_PATH", drifted):
                record = admission.evaluate(self.candidate(), self.profile)
        self.assertEqual(record["status"], "rejected")
        self.assertIn("provider_baseline_hash_mismatch", record["reasons"])

    def test_model_drift_rejects(self) -> None:
        candidate = self.candidate()
        candidate["identity"]["model_id"] = "gpt-5.6-terra"
        command = candidate["command"]
        command[command.index("--model") + 1] = "gpt-5.6-terra"
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "rejected")
        self.assertIn("model_mismatch", record["reasons"])

    def test_reasoning_effort_drift_rejects(self) -> None:
        candidate = self.candidate()
        candidate["identity"]["reasoning_effort"] = "high"
        self.replace_config(candidate["command"], "model_reasoning_effort", '"high"')
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "rejected")
        self.assertIn("reasoning_effort_mismatch", record["reasons"])

    def test_nonzero_retry_rejects(self) -> None:
        candidate = self.candidate()
        self.replace_config(
            candidate["command"],
            "model_providers.irisx_openai_no_retry.request_max_retries",
            "1",
        )
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "rejected")
        self.assertIn("retry_settings_nonzero_or_missing", record["reasons"])

    def test_websocket_enabled_rejects(self) -> None:
        candidate = self.candidate()
        self.replace_config(
            candidate["command"],
            "model_providers.irisx_openai_no_retry.supports_websockets",
            "true",
        )
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "rejected")
        self.assertIn("websocket_transport_enabled_or_unspecified", record["reasons"])

    def test_broader_sandbox_rejects(self) -> None:
        candidate = self.candidate()
        command = candidate["command"]
        command[command.index("--sandbox") + 1] = "workspace-write"
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "rejected")
        self.assertIn("sandbox_broader_than_read_only", record["reasons"])

    def test_tool_enabled_envelope_rejects(self) -> None:
        candidate = self.candidate()
        command = candidate["command"]
        index = command.index("view_image")
        del command[index - 1 : index + 1]
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "rejected")
        self.assertIn("tool_envelope_mismatch", record["reasons"])

    def test_api_key_fallback_configuration_rejects(self) -> None:
        candidate = self.candidate()
        candidate["identity"]["api_key_fallback"] = "allowed"
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "rejected")
        self.assertIn("api_key_fallback_configured", record["reasons"])
        self.assertTrue(record["api_key_fallback_present"])

    def test_provider_slot_mismatch_rejects(self) -> None:
        candidate = self.candidate()
        self.replace_config(candidate["command"], "model_provider", '"other_slot"')
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "rejected")
        self.assertIn("provider_slot_mismatch", record["reasons"])

    def test_unknown_material_configuration_rejects(self) -> None:
        candidate = self.candidate()
        index = candidate["command"].index("--json")
        candidate["command"][index:index] = ["--config", "future.material_flag=true"]
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "rejected")
        self.assertIn("unknown_material_configuration:future.material_flag", record["reasons"])

    def test_malformed_command_identity_fails_closed(self) -> None:
        with self.assertRaises(admission.AdmissionError):
            admission.normalize_command(["codex", "exec", "--config", "malformed"])

    def test_current_environment_uses_only_local_zero_call_checks(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="Logged in using ChatGPT\n", stderr="")

        with mock.patch.object(admission.baseline_check, "validate_baseline", return_value=[]), mock.patch.object(
            admission.baseline_check, "validate_local_catalog", return_value=([], "codex-cli 0.147.0")
        ), mock.patch.object(
            admission.baseline_check,
            "resolve_codex_command",
            return_value=self.profile["required_resolved_path"],
        ), mock.patch.object(admission.subprocess, "run", side_effect=fake_run):
            record = admission.current_environment()
        self.assertEqual(record["status"], "admitted")
        self.assertEqual(record["live_model_calls"], 0)
        self.assertEqual(calls, [[self.profile["required_resolved_path"], "login", "status"]])
        self.assertNotIn("exec", calls[0][1:])

    def test_current_record_never_contains_secret_values(self) -> None:
        secret = "not-for-artifact-super-secret"
        completed = subprocess.CompletedProcess(
            [self.profile["required_resolved_path"], "login", "status"],
            0,
            stdout="Logged in using ChatGPT\n",
            stderr="",
        )
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": secret}), mock.patch.object(
            admission.baseline_check, "validate_baseline", return_value=[]
        ), mock.patch.object(
            admission.baseline_check, "validate_local_catalog", return_value=([], "codex-cli 0.147.0")
        ), mock.patch.object(
            admission.baseline_check,
            "resolve_codex_command",
            return_value=self.profile["required_resolved_path"],
        ), mock.patch.object(admission.subprocess, "run", return_value=completed):
            record = admission.current_environment()
        rendered = json.dumps(record)
        self.assertNotIn(secret, rendered)
        self.assertIn("OPENAI_API_KEY", record["api_key_environment_names_present_in_parent"])
        self.assertFalse(record["api_key_fallback_present"])

    def test_missing_cli_is_unsupported_without_model_call(self) -> None:
        with mock.patch.object(admission.baseline_check, "validate_baseline", return_value=[]), mock.patch.object(
            admission.baseline_check, "resolve_codex_command", side_effect=OSError("missing")
        ), mock.patch.object(admission.subprocess, "run") as run:
            record = admission.current_environment()
        self.assertEqual(record["status"], "unsupported")
        self.assertIn("cli_executable_missing", record["reasons"])
        run.assert_not_called()

    def test_unknown_auth_state_is_unsupported(self) -> None:
        candidate = self.candidate()
        candidate["preflight"]["authentication_mode"] = "Unknown"
        record = admission.evaluate(candidate, self.profile)
        self.assertEqual(record["status"], "unsupported")
        self.assertIn("chatgpt_authentication_not_locally_established", record["reasons"])

    def test_admission_checker_does_not_create_run_directories(self) -> None:
        before = sorted(path.name for path in (SUBSTRATE / "runs").iterdir() if path.is_dir())
        admission.replay("01")
        admission.replay("02")
        admission.replay("03")
        after = sorted(path.name for path in (SUBSTRATE / "runs").iterdir() if path.is_dir())
        self.assertEqual(before, after)

    def test_provider_specific_admission_does_not_enter_core(self) -> None:
        changed_core = subprocess.run(
            ["git", "diff", "--name-only", "21f0150aed8b8555b69dc1094a1c3d7a6441732b", "--", "irisx/core"],
            cwd=REPOSITORY_ROOT,
            check=True,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
        ).stdout.strip()
        self.assertEqual(changed_core, "")


if __name__ == "__main__":
    unittest.main()
