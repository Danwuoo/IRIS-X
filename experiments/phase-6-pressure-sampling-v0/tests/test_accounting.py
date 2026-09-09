from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_pressure_batch as runner  # noqa: E402


class AccountingTests(unittest.TestCase):
    def test_final_message_directly_establishes_provider_acceptance(self) -> None:
        self.assertIs(runner.observed_provider_acceptance([], final_message='{"ok":true}'), True)

    def test_invalid_schema_event_directly_establishes_rejection(self) -> None:
        events = [{"type": "error", "message": "invalid_request_error invalid_json_schema"}]
        self.assertIs(runner.observed_provider_acceptance(events, final_message=None), False)

    def test_uninstrumented_process_failure_preserves_unknown(self) -> None:
        events = [{"type": "turn.failed", "error": {"message": "connection closed"}}]
        self.assertEqual(runner.observed_provider_acceptance(events, final_message=None), "Unknown")


if __name__ == "__main__":
    unittest.main()
