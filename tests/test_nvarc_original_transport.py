"""Provider receipt and zero-enum regressions; no network or ML imports."""
from types import SimpleNamespace
import unittest

from tools.execute_nvarc_overnight_sft import session_state
from tools.nvarc_qwen3_material import dataset_receipt_accepted
from tools.inspect_nvarc_free_resource import duration_seconds


class OriginalTransportTests(unittest.TestCase):
    def test_fractional_sdk_duration_and_unknown_encodings(self):
        from irisx.errors import ValidationError
        self.assertEqual(duration_seconds('7904.971004.0s'),7904.971004)
        self.assertEqual(duration_seconds('21600s'),21600)
        for invalid in ('NaNs','-1s','used=7904','7904.971.5s'):
            with self.assertRaises(ValidationError):duration_seconds(invalid)

    def test_zero_queued_enum_survives_empty_wire_dictionary(self):
        response=SimpleNamespace(status=SimpleNamespace(name='QUEUED'),to_dict=lambda:{})
        self.assertEqual(response.to_dict(),{})
        self.assertEqual(session_state(response),'QUEUED')

    def test_terminal_and_running_typed_enum(self):
        for state in ('RUNNING','COMPLETE','ERROR','CANCEL_ACKNOWLEDGED'):
            self.assertEqual(session_state(SimpleNamespace(status=SimpleNamespace(name=state))),state)

    def test_exact_capitalized_ok_dataset_receipt(self):
        receipt={'ref':'/datasets/danielwuu/irisx-nvarc-original-qwen3-001','status':'Ok',
            'url':'https://www.kaggle.com/datasets/danielwuu/irisx-nvarc-original-qwen3-001'}
        self.assertTrue(dataset_receipt_accepted(receipt))
        for key,value in [('status','error'),('error','rejected'),('ref','/datasets/other/model'),
                          ('url','https://www.kaggle.com/datasets/other/model')]:
            self.assertFalse(dataset_receipt_accepted({**receipt,key:value}))


if __name__=='__main__':unittest.main()
