import os
from pathlib import Path
import subprocess
import sys
import unittest


class ImportTests(unittest.TestCase):
    def test_imports_are_inert_without_neural_dependencies(self):
        root = Path(__file__).resolve().parents[3]
        script = '''import sys
from tools.arc_learning_agent_20261011 import data, training
assert 'torch' not in sys.modules
assert 'transformers' not in sys.modules
assert 'peft' not in sys.modules
assert not hasattr(training, 'model')
'''
        result = subprocess.run([sys.executable, "-c", script], cwd=root, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_compact_head_or_dynamic_candidate_execution(self):
        source = Path(__file__).resolve().parents[1] / "training.py"
        text = source.read_text()
        self.assertNotIn("[:16]", text)
        self.assertNotIn("GridTokenizer", text)
        self.assertIn("weights_only=True", text)
        self.assertIn("lora_target_modules", text)


if __name__ == "__main__":
    unittest.main()
