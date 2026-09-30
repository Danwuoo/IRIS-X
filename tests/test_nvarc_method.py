"""Dependency-light checks for source representation and SFT scheduling."""

import unittest
from pathlib import Path
import tempfile

from irisx.arc_nvarc_representation import GridTokenizer
from irisx.arc_nvarc_source_recipe import SourceTextTokenizer, source_sft_lr
from irisx.errors import ValidationError
from tools.nvarc_retained_abc import verify_retained_wheel


class MethodReferenceTests(unittest.TestCase):
    def test_retained_wheel_rejects_unknown_identity_and_changed_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'runtime.whl'
            path.write_bytes(b'rehashed unapproved wheel')
            for identity in ('nvarc-compact-abc-editor-005', 'unknown'):
                with self.assertRaises(ValidationError):
                    verify_retained_wheel(path,identity)

    def test_literal_source_text_matches_compact_pair_and_rejects_extra_text(self):
        text = '<|im_start|>user\n12\n34<|im_end|><|im_start|>assistant\n56<|im_end|>'
        self.assertEqual(SourceTextTokenizer().encode(text),
            GridTokenizer(source_chat_newlines=True).encode_pair([[1, 2], [3, 4]], [[5, 6]])[0])
        for invalid in (text + ' ', '```' + text, 'system\n' + text):
            with self.assertRaises(ValidationError):
                SourceTextTokenizer().encode(invalid)

    def test_source_learning_rate_has_warmup_peak_and_nonzero_floor(self):
        config = {"learning_rate": 1e-4, "warmup_initial_learning_rate": 1e-6,
                  "minimum_learning_rate": 1e-7, "warmup_steps": 200, "schedule_steps": 12716}
        self.assertAlmostEqual(source_sft_lr(config, 0), 1e-6)
        self.assertAlmostEqual(source_sft_lr(config, 100), (1e-6 + 1e-4) / 2)
        self.assertAlmostEqual(source_sft_lr(config, 200), 1e-4)
        self.assertAlmostEqual(source_sft_lr(config, 12716), 1e-7)
        self.assertAlmostEqual(source_sft_lr(config, 20000), 1e-7)
        with self.assertRaises(ValidationError):
            source_sft_lr({**config, "warmup_steps": 12716}, 0)


if __name__ == '__main__':
    unittest.main()
