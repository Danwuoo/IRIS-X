"""Exercise the exact staged notebook's interrupt diagnostic without Kaggle calls."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-editor-008-final"


class Editor008StrictTests(unittest.TestCase):
    def test_interrupt_during_torch_import_retains_terminal_zip(self):
        notebook = json.loads((PACKAGE / "kernel/kaggle-notebook.ipynb").read_text(encoding="utf-8"))
        source = "".join(notebook["cells"][1]["source"])
        platform_guard = '    if os.name != "posix":\n'
        torch_import = '    import torch\n    phase = "smi-query"'
        self.assertEqual(1, source.count(platform_guard))
        self.assertEqual(1, source.count(torch_import))
        # A controlled Windows replay changes only the platform guard and
        # injects the interruption at the observed startup boundary.
        source = source.replace(platform_guard, '    if False:\n')
        source = source.replace(torch_import,
            '    raise KeyboardInterrupt("controlled interruption")\n    phase = "smi-query"')
        source = source.replace("signal.SIGALRM", "signal.SIGINT")
        source = source.replace("signal.ITIMER_REAL", "0")
        source = source.replace("import signal\n", "import signal\nsignal.setitimer = lambda *_args: None\n")
        with tempfile.TemporaryDirectory(dir=ROOT / ".irisx", prefix="editor008-interrupt-") as temp:
            script = Path(temp) / "replay.py"
            script.write_text(source, encoding="utf-8")
            process = subprocess.run([sys.executable, str(script)], cwd=temp,
                                     capture_output=True, text=True, timeout=30)
            self.assertNotEqual(0, process.returncode)
            self.assertIn("KeyboardInterrupt", process.stderr)
            with zipfile.ZipFile(Path(temp) / "結果.zip") as archive:
                self.assertIsNone(archive.testzip())
                terminal = json.loads(archive.read("aggregate-terminal.json"))
                events = [json.loads(row) for row in archive.read("startup-events.jsonl").splitlines()]
            self.assertEqual("failed", terminal["outcome"])
            self.assertEqual("torch-import", terminal["last_phase"])
            self.assertEqual("KeyboardInterrupt", terminal["error"]["type"])
            self.assertEqual("terminal-failure", events[-1]["phase"])
            self.assertEqual("KeyboardInterrupt", events[-1]["error"]["type"])
            self.assertEqual(0, terminal["branches"]["m2"]["launch_count"])
            self.assertEqual(0, terminal["branches"]["m3"]["launch_count"])


if __name__ == "__main__":
    unittest.main()
