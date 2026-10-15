"""Fail closed if portability changes unrelated frozen transport behavior."""
import ast
import hashlib
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
FROZEN = HERE.with_name('publication_run008')


def tree(path):
    value = ast.parse(path.read_bytes())
    if value.body and isinstance(value.body[0], ast.Expr) and isinstance(value.body[0].value, ast.Constant):
        value.body.pop(0)
    return value


def erase_pin_values(value, names):
    for node in value.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
            node.value = ast.Constant(value='REVIEWED-SUCCESSOR-PIN')
    return value


class FrozenEquivalenceTests(unittest.TestCase):
    def test_frozen_provenance_still_matches_every_original_byte(self):
        provenance = json.loads((HERE / 'FROZEN-SOURCE-PROVENANCE.json').read_bytes())
        self.assertEqual(provenance['source_commit'], 'cc14bd1a79aac1fe6135017c9e09d4834300675d')
        self.assertEqual(set(provenance['files']), {'config.py', 'native_auth.py', 'sdk-lock.json', 'operator_common.py', 'rl_transport.py', 'rl_collect.py', 'launch.py'})
        for name, row in provenance['files'].items():
            raw = (FROZEN / name).read_bytes()
            self.assertEqual(len(raw), row['bytes'], name)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'], name)

    def test_transport_primitives_change_only_upstream_source_pins(self):
        pins = {'CONFIG_SOURCE_SHA256', 'NATIVE_AUTH_SHA256'}
        self.assertEqual(ast.dump(erase_pin_values(tree(FROZEN / 'operator_common.py'), pins)),
                         ast.dump(erase_pin_values(tree(HERE / 'operator_common.py'), pins)))

    def test_transport_changes_only_pins_and_replacement_runtime_boundary(self):
        original, successor = tree(FROZEN / 'rl_transport.py'), tree(HERE / 'rl_transport.py')
        pins = {'COMMON_SOURCE_SHA256'}
        for value in (original, successor):
            erase_pin_values(value, pins)
            configure = next(node for node in value.body if isinstance(node, ast.FunctionDef) and node.name == 'configure_local')
            checks = [node for node in configure.body if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                      and isinstance(node.value.func, ast.Name) and node.value.func.id == 'need'
                      and len(node.value.args) == 2 and isinstance(node.value.args[1], ast.Constant)
                      and node.value.args[1].value in {'official_native_wrapper_required', 'reviewed_posix_runtime_required'}]
            self.assertEqual(len(checks), 1)
            configure.body.remove(checks[0])
        self.assertEqual(ast.dump(original), ast.dump(successor))

    def test_collector_changes_only_upstream_source_pins(self):
        pins = {'COMMON_SOURCE_SHA256', 'TRANSPORT_SOURCE_SHA256'}
        self.assertEqual(ast.dump(erase_pin_values(tree(FROZEN / 'rl_collect.py'), pins)),
                         ast.dump(erase_pin_values(tree(HERE / 'rl_collect.py'), pins)))

    def test_official_session_and_source_only_importer_are_unchanged(self):
        for name in ('OfficialSession', 'ReviewedSdkFinder'):
            values = [next(node for node in tree(root / 'native_auth.py').body if isinstance(node, ast.ClassDef) and node.name == name)
                      for root in (FROZEN, HERE)]
            self.assertEqual(ast.dump(values[0]), ast.dump(values[1]), name)

    def test_exact_official_sdk_lock_is_not_rebased_to_installed_versions(self):
        self.assertEqual((HERE / 'sdk-lock.json').read_bytes(), (FROZEN / 'sdk-lock.json').read_bytes())
        lock = json.loads((HERE / 'sdk-lock.json').read_bytes())
        self.assertEqual(lock['distributions'], {'kaggle': '2.2.4', 'kagglesdk': '0.1.37'})
        self.assertEqual(len(lock['sources']), 170)


if __name__ == '__main__':
    unittest.main(verbosity=2)
