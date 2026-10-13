"""Offline AST and pure-function collection tests; no provider/authentication calls."""
from pathlib import Path
import ast
import copy
import math
import types
import unittest

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent / 'publication_run005/rl_collect.py'
OPTIONAL = {'preparation/preparation-failure.json': 64 * 1024,
            'preparation/preparation-stages.jsonl': 16 * 1024,
            'preparation/installation-log-excerpt.bin': 128 * 1024}


def function_module(path):
    """Compile only pure source-owned functions, excluding all operator imports."""
    tree = ast.parse(path.read_text())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in ('output_paths', 'validation_gate')]
    def need(ok, message):
        if not ok:
            raise ValueError(message)
    module = types.ModuleType('synthetic_collector_functions')
    vars(module).update(Path=Path, math=math, need=need, TERMINAL={'COMPLETE', 'ERROR', 'CANCEL_ACKNOWLEDGED'},
                        transport=types.SimpleNamespace(row=lambda m, role: m['notebooks'][0]))
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), vars(module))
    return module


class CollectorDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.old = function_module(FROZEN)
        self.new = function_module(HERE / 'rl_collect.py')
        self.manifest = {'terminal_contract': {'terminal_path': 'run005.evidence.zip.terminal.json',
            'evidence_path': 'run005.evidence.zip', 'archive_caps': {'evidence_archive_bytes': 5 * 1024**3}},
            'notebooks': [{'output_root': '/kaggle/working/run005'}]}

    def test_exactly_three_optional_caps_added_and_required_set_unchanged(self):
        old_prefix, old_outer, old_caps, old_required = self.old.output_paths(self.manifest)
        prefix, outer, caps, required = self.new.output_paths(self.manifest)
        self.assertEqual((prefix, outer, required), (old_prefix, old_outer, old_required))
        added = {outer + '/' + name: value for name, value in OPTIONAL.items()}
        self.assertEqual(caps, {**old_caps, **added})
        self.assertTrue(set(added).isdisjoint(required))
        self.assertEqual(sum(added.values()), 208 * 1024)

    def test_absence_of_all_optional_files_never_creates_missing_required_evidence(self):
        _, outer, caps, required = self.new.output_paths(self.manifest)
        available = set(caps) - {outer + '/' + name for name in OPTIONAL}
        self.assertEqual(required - available, set())

    def test_only_diagnostics_never_satisfy_any_required_evidence(self):
        _, outer, caps, required = self.new.output_paths(self.manifest)
        diagnostics_only = {outer + '/' + name for name in OPTIONAL}
        self.assertEqual(required - diagnostics_only, required)
        self.assertTrue(required)

    def test_all_other_collector_ast_including_pins_and_classification_identical(self):
        before = ast.parse(FROZEN.read_text())
        after = ast.parse((HERE / 'rl_collect.py').read_text())
        old = next(node for node in before.body if isinstance(node, ast.FunctionDef) and node.name == 'output_paths')
        new = next(node for node in after.body if isinstance(node, ast.FunctionDef) and node.name == 'output_paths')
        def optional_assignment(node):
            return (isinstance(node, ast.Assign) and len(node.targets) == 1 and
                    isinstance(node.targets[0], ast.Subscript) and
                    isinstance(node.targets[0].value, ast.Name) and node.targets[0].value.id == 'caps' and
                    any(isinstance(value, ast.Constant) and isinstance(value.value, str) and
                        value.value in {'/' + name for name in OPTIONAL} for value in ast.walk(node.targets[0])))
        removed = [node for node in new.body if optional_assignment(node)]
        self.assertEqual(len(removed), 3)
        new.body = [node for node in new.body if not optional_assignment(node)]
        self.assertEqual(ast.dump(before, include_attributes=False), ast.dump(after, include_attributes=False))

    def test_diagnostic_payload_cannot_pass_production_validation(self):
        diagnostic = {'format': 'irisx/rlvr-preparation-failure-v1', 'status': 'FAILED',
                      'stage': 'offline-installation', 'operational_success': False}
        for module in (self.old, self.new):
            with self.assertRaisesRegex(ValueError, 'unverified_production_content'):
                module.validation_gate(diagnostic, 'COMPLETE', True)

    def test_existing_stopped_incomplete_never_promoted_even_provider_complete(self):
        diagnostic = {'status': 'STOPPED_INCOMPLETE', 'diagnostic_evidence_valid': True,
            'authenticated_collection_verified': True, 'release_content_binding_valid': True,
            'external_owner_envelope_verified': True, 'production_admitted': False,
            'public_goal_met': False, 'scientific_goal_met': False}
        old = self.old.validation_gate(copy.deepcopy(diagnostic), 'COMPLETE', True)
        new = self.new.validation_gate(copy.deepcopy(diagnostic), 'COMPLETE', True)
        self.assertEqual(new, old)
        for field in ('operational_complete', 'operational_success', 'comparison_complete', 'compute_matched',
                      'comparison_eligible', 'public_benchmark_evidence_eligible', 'verified_public_threshold_reached',
                      'public_goal_met', 'goal_met', 'automatic_retry'):
            self.assertIs(new[field], False)

    def test_invalid_closure_remains_blocking(self):
        for module in (self.old, self.new):
            with self.assertRaisesRegex(ValueError, 'invalid_raw_wrapper_blocks_all_admission'):
                module.validation_gate({'status': 'STOPPED_INCOMPLETE'}, 'COMPLETE', False)


if __name__ == '__main__':
    unittest.main()
