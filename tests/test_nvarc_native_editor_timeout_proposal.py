"""Offline parent-deadline replay and fail-closed proposal tests; no model work."""
import ast
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from irisx.canonical import canonical_bytes
from tools import stage_nvarc_native_editor_timeout_proposal as proposal


class NativeEditorTimeoutProposalTests(unittest.TestCase):
    def fixture(self):
        plan = {'run_id': proposal.RUN, 'approved': False,
            'maximum_notebook_wall_seconds': 3600, 'maximum_child_wall_seconds': 3000}
        raw = {'plan': canonical_bytes(plan), 'source_inventory': b'{}', 'model_inventory': b'{}',
            'editor_archive': proposal.predecessor.ARCHIVE.read_bytes()}
        return plan, raw

    def test_unapproved_emitted_parent_stops_before_dependency_or_gpu_access(self):
        plan, raw = self.fixture()
        source = ''.join(proposal.notebook(plan, raw)['cells'][0]['source'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = source.replace("Path('/kaggle/working')", 'Path(' + repr(str(root)) + ')')
            with patch('sys.stdout', new_callable=io.StringIO), patch('sys.version_info', (3, 11, 13)), \
                    self.assertRaisesRegex(RuntimeError, 'new owner approval required'):
                exec(compile(source, 'inert-proposal', 'exec'), {})
            with zipfile.ZipFile(root / '結果.zip') as stream:
                terminal = json.loads(stream.read('terminal.json'))
                self.assertEqual(terminal['phase'], 'payload-verification')
                self.assertEqual(terminal['model_forwards_reserved'], 0)
                self.assertEqual(terminal['optimizer_steps_reserved'], 0)
                self.assertNotIn('hardware.json', stream.namelist())
                self.assertNotIn('worker-stdout.log', stream.namelist())
                self.assertFalse(json.loads(stream.read('plan.json'))['approved'])

    def test_actual_parent_timeout_expression_replays_007_and_retains_terminal_reserve(self):
        plan, raw = self.fixture()
        tree = ast.parse(''.join(proposal.notebook(plan, raw)['cells'][0]['source']))
        expressions = [node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
            and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == 'remaining']
        self.assertEqual(len(expressions), 1)
        expression = compile(ast.Expression(expressions[0]), 'actual-parent-budget', 'eval')
        class Clock:
            @staticmethod
            def monotonic(): return 400.9820315730001
        historical = {'maximum_notebook_wall_seconds': 1500, 'maximum_child_wall_seconds': 1200}
        namespace = {'START': 0, 'time': Clock, 'plan': historical}
        self.assertAlmostEqual(eval(expression, namespace), 979.0179684269999)
        namespace['plan'] = plan
        self.assertEqual(eval(expression, namespace), 3000)
        # Late setup still shortens the child, preserving the unchanged 120s reserve.
        namespace['START'] = -2000
        self.assertAlmostEqual(eval(expression, namespace), 1079.0179684269999)


if __name__ == '__main__':
    unittest.main()
