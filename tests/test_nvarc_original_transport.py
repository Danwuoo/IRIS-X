"""Provider receipt and zero-enum regressions; no network or ML imports."""
from types import SimpleNamespace
from pathlib import Path
import json
import subprocess
import unittest
from unittest.mock import patch

from tools.execute_nvarc_overnight_sft import session_state,preflight
from tools.nvarc_qwen3_material import dataset_receipt_accepted
from tools.inspect_nvarc_free_resource import duration_seconds


class OriginalTransportTests(unittest.TestCase):
    def test_long_epoch_sdk_preflight_uses_bounded_offline_ml_process(self):
        observed={'offline_package_verified':True,'external_calls':0,'source_views':128}
        with patch('tools.execute_nvarc_overnight_sft.read',return_value={
                'format':'irisx/nvarc-original-qwen3-long-ttt-v1'}),patch(
                'tools.execute_nvarc_overnight_sft.subprocess.check_output',return_value=json.dumps(observed)) as run:
            self.assertEqual(preflight(Path('frozen-package')),observed)
            args,kwargs=run.call_args
            self.assertTrue(args[0][0].replace('\\','/').endswith('.irisx/nvarc-ml-venv/Scripts/python.exe'))
            self.assertEqual(args[0][-3:],['preflight','--package','frozen-package'])
            self.assertEqual(kwargs['timeout'],300)
            run.side_effect=subprocess.TimeoutExpired(args[0],300)
            with self.assertRaises(subprocess.TimeoutExpired):preflight(Path('frozen-package'))

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
