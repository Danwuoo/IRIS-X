"""Offline bootstrap integrity checks; synthetic reviews grant no provider authority."""
import ast
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('rl_collect.py', 'operator_common.py', 'rl_transport.py')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def synthetic_bootstrap_arguments(root, source_root=ROOT):
    """Disposable source-binding fixture only, never independent action approval."""
    root.mkdir(parents=True, exist_ok=True)
    documents = {'manifest': {'synthetic_test_only': True, 'notebooks': []}}
    manifest_sha = sha(encoded(documents['manifest']))
    documents['local_config'] = {'synthetic_test_only': True,
                                 'publication_manifest_sha256': manifest_sha}
    documents['material'] = {'synthetic_test_only': True, 'status': 'APPROVED',
        'scope': {'publication_manifest': {'sha256': manifest_sha}}, 'approved_notebooks': []}
    documents['review'] = {'synthetic_test_only': True, 'status': 'PASS',
        'provider_execution_admitted': False, 'allowed_actions': [],
        'publication_manifest_sha256': manifest_sha,
        'local_config_sha256': sha(encoded(documents['local_config'])),
        'material_approval_sha256': sha(encoded(documents['material'])),
        'operator_files': {path.name: sha(path.read_bytes()) for path in source_root.iterdir()
                           if path.is_file() and path.suffix in ('.py', '.json')}}
    values = {'action': 'poll'}
    for name, document in documents.items():
        raw = encoded(document)
        path = root / ('synthetic-bootstrap-' + name + '.json')
        path.write_bytes(raw)
        values[name], values[name + '_sha'] = str(path), sha(raw)
    return SimpleNamespace(**values)


def load_collector(path):
    module = ModuleType('synthetic_bootstrap_collector')
    module.__file__, module.__package__ = str(path), ''
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True,
                 optimize=sys.flags.optimize), vars(module))
    return module


class CollectorBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='collector-bootstrap-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        for name in SOURCES:
            (self.source / name).write_bytes((ROOT / name).read_bytes())
        self.collector = load_collector(self.source / 'rl_collect.py')
        self.args = synthetic_bootstrap_arguments(self.root / 'documents', self.source)

    def document(self, name):
        return json.loads(Path(getattr(self.args, name)).read_bytes())

    def write_document(self, name, document):
        raw = encoded(document)
        Path(getattr(self.args, name)).write_bytes(raw)
        setattr(self.args, name + '_sha', sha(raw))

    def bind_review(self):
        review = self.document('review')
        for field, name in [('local_config_sha256', 'local_config'),
                            ('publication_manifest_sha256', 'manifest'),
                            ('material_approval_sha256', 'material')]:
            review[field] = getattr(self.args, name + '_sha')
        for name in SOURCES:
            review['operator_files'][name] = sha((self.source / name).read_bytes())
        self.write_document('review', review)

    def rejected_before_exec(self, message=None):
        with patch.object(self.collector, 'exec', create=True) as execute:
            with self.assertRaisesRegex((ValueError, OSError), message or '.'):
                self.collector.bootstrap(self.args)
            execute.assert_not_called()
        self.assertIsNone(self.collector.transport)
        self.assertIsNone(self.collector._common)

    def argv(self):
        result = ['poll']
        for name in self.collector._BOOTSTRAP_REQUIRED:
            result.extend(['--' + name, getattr(self.args, name.replace('-', '_'))])
        return result

    def test_import_and_help_are_inert_without_dependencies(self):
        (self.source / 'rl_transport.py').unlink()
        (self.source / 'operator_common.py').unlink()
        collector = load_collector(self.source / 'rl_collect.py')
        self.assertIsNone(collector.transport)
        with patch.object(collector, 'bootstrap') as bootstrap, \
                patch.object(sys, 'argv', ['rl_collect.py', '--help']), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                collector.main()
            self.assertEqual(caught.exception.code, 0)
            bootstrap.assert_not_called()

    def test_full_exact_cli_and_equals_syntax(self):
        args = self.collector.bootstrap_arguments(self.argv())
        self.assertEqual(vars(args) | vars(self.args), vars(args))
        argv = ['poll'] + ['--' + name + '=' + getattr(self.args, name.replace('-', '_'))
                          for name in self.collector._BOOTSTRAP_REQUIRED]
        self.assertEqual(vars(self.collector.bootstrap_arguments(argv)), vars(args))

    def test_duplicate_binding_and_optional_flags_block_before_bootstrap(self):
        for name in self.collector._BOOTSTRAP_REQUIRED + self.collector._BOOTSTRAP_OPTIONAL:
            with self.subTest(name=name):
                argv = self.argv() + ['--' + name + '=first', '--' + name, 'second']
                with patch.object(self.collector, 'bootstrap') as bootstrap, \
                        patch.object(sys, 'argv', ['rl_collect.py', *argv]), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as caught:
                        self.collector.main()
                    self.assertEqual(caught.exception.code, 2)
                    bootstrap.assert_not_called()

    def test_abbreviated_unknown_or_missing_flags_block_before_bootstrap(self):
        variants = [self.argv() + ['--rev', 'x'], self.argv() + ['--monitor-rev', 'x'],
                    self.argv() + ['--unknown', 'x'], self.argv()[:-2], ['validate', *self.argv()[1:]]]
        for argv in variants:
            with self.subTest(argv=argv), patch.object(self.collector, 'bootstrap') as bootstrap, \
                    patch.object(sys, 'argv', ['rl_collect.py', *argv]), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.collector.main()
                bootstrap.assert_not_called()

    def test_bounded_cli_rejects_terminator_nul_and_excess(self):
        for argv in (self.argv() + ['--'], self.argv() + ['x\x00'], ['x'] * 129, ['x' * 8193]):
            with self.subTest(argv=argv[:1]), self.assertRaisesRegex(ValueError, 'bounded_unambiguous'):
                self.collector.bootstrap_arguments(argv)

    def test_missing_explicit_binding_and_noncanonical_digests(self):
        for name in self.collector._BOOTSTRAP_REQUIRED:
            attribute = name.replace('-', '_')
            original = getattr(self.args, attribute)
            setattr(self.args, attribute, None)
            self.rejected_before_exec('bootstrap_explicit_binding_required')
            setattr(self.args, attribute, original)
        original = self.args.review_sha
        for digest in ('', 'A' * 64, '0' * 63, original + ' ', 5):
            self.args.review_sha = digest
            self.rejected_before_exec()
        self.args.review_sha = original

    def test_each_document_stale_hash_rejected_before_exec(self):
        for name in ('review', 'manifest', 'material', 'local_config'):
            path = Path(getattr(self.args, name)); original = path.read_bytes()
            with self.subTest(name=name):
                path.write_bytes(original + b' ')
                self.rejected_before_exec('bootstrap_file_hash')
            path.write_bytes(original)

    def test_each_source_stale_hash_rejected_before_exec(self):
        for name in SOURCES:
            path = self.source / name; original = path.read_bytes()
            with self.subTest(name=name):
                path.write_bytes(original + b'\nraise RuntimeError("unreviewed source executed")\n')
                self.rejected_before_exec('bootstrap_file_hash')
            path.write_bytes(original)

    def test_duplicate_nonfinite_and_nonobject_json_in_every_document(self):
        for name in ('review', 'manifest', 'material', 'local_config'):
            path = Path(getattr(self.args, name)); original = path.read_bytes()
            digest = getattr(self.args, name + '_sha')
            for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}',
                        b'{"x":1e999}', b'[]', b'{"nested":{"x":1,"x":2}}'):
                with self.subTest(name=name, raw=raw):
                    path.write_bytes(raw); setattr(self.args, name + '_sha', sha(raw))
                    self.rejected_before_exec('bootstrap_(duplicate_json_key|nonfinite_json|json_object_required)')
            path.write_bytes(original); setattr(self.args, name + '_sha', digest)

    def test_json_depth_is_bounded(self):
        raw = b'{"x":' * 66 + b'0' + b'}' * 66
        Path(self.args.review).write_bytes(raw); self.args.review_sha = sha(raw)
        self.rejected_before_exec('bootstrap_json_structure_bound')

    def test_document_and_source_size_are_bounded(self):
        for path, cap, attribute in ((Path(self.args.review), 4 * 1024**2, 'review_sha'),
                                     (Path(self.args.local_config), 1024**2, 'local_config_sha'),
                                     (self.source / 'rl_transport.py', 1024**2, None)):
            original = path.read_bytes()
            with self.subTest(path=path.name):
                path.write_bytes(b' ' * (cap + 1))
                if attribute:
                    old_sha = getattr(self.args, attribute)
                    setattr(self.args, attribute, sha(path.read_bytes()))
                self.rejected_before_exec('bootstrap_bounded_ordinary_file')
                if attribute:
                    setattr(self.args, attribute, old_sha)
            path.write_bytes(original)

    def test_review_status_and_all_crossbindings(self):
        original = self.document('review')
        for key in ('status', 'local_config_sha256', 'publication_manifest_sha256', 'material_approval_sha256'):
            with self.subTest(key=key):
                self.write_document('review', {**original, key: '0' * 64})
                self.rejected_before_exec('bootstrap_review_binding')
        self.write_document('review', original)

    def test_config_and_material_crossbindings_and_approval(self):
        original = self.document('local_config')
        self.write_document('local_config', {**original, 'publication_manifest_sha256': '0' * 64})
        self.bind_review()
        self.rejected_before_exec('bootstrap_config_manifest_binding')
        self.write_document('local_config', original)
        material = self.document('material')
        for value in ({**material, 'status': 'PASS'}, {**material, 'scope': {}},
                      {**material, 'scope': {'publication_manifest': {'sha256': '0' * 64}}}):
            self.write_document('material', value); self.bind_review()
            self.rejected_before_exec('bootstrap_material_manifest_binding')

    def test_review_requires_all_three_source_digests(self):
        original = self.document('review')
        for name in SOURCES:
            review = json.loads(encoded(original))
            del review['operator_files'][name]
            self.write_document('review', review)
            self.rejected_before_exec('bootstrap_reviewed_sources_required')
        self.write_document('review', {**original, 'operator_files': []})
        self.rejected_before_exec('bootstrap_reviewed_sources_required')

    def test_transport_static_common_pin_must_match_same_review(self):
        path = self.source / 'rl_transport.py'; raw = path.read_text()
        digest = sha((self.source / 'operator_common.py').read_bytes())
        for changed in (raw.replace("COMMON_SOURCE_SHA256 = '" + digest + "'",
                                    "COMMON_SOURCE_SHA256 = '" + '0' * 64 + "'"),
                        raw + '\nCOMMON_SOURCE_SHA256 = ' + repr(digest) + '\n',
                        raw.replace("COMMON_SOURCE_SHA256 = '" + digest + "'",
                                    'COMMON_SOURCE_SHA256 = str(' + repr(digest) + ')')):
            path.write_text(changed); self.bind_review()
            self.rejected_before_exec('bootstrap_transport_common_pin')
        path.write_text(raw)

    def test_symlink_hardlink_special_and_parent_paths_rejected(self):
        for path in (Path(self.args.review), Path(self.args.local_config),
                     Path(self.args.manifest), Path(self.args.material),
                     *(self.source / name for name in SOURCES)):
            raw = path.read_bytes(); target = path.with_name(path.name + '.target')
            path.rename(target)
            for kind in ('symlink', 'hardlink', 'directory', 'fifo'):
                with self.subTest(path=path.name, kind=kind):
                    if kind == 'symlink':path.symlink_to(target)
                    elif kind == 'hardlink':os.link(target, path)
                    elif kind == 'directory':path.mkdir()
                    else:os.mkfifo(path)
                    self.rejected_before_exec('bootstrap_bounded_ordinary_file')
                    if kind == 'directory':path.rmdir()
                    else:path.unlink()
            target.rename(path)
            self.assertEqual(path.read_bytes(), raw)
        alias = self.root / 'linked-documents'; alias.symlink_to(Path(self.args.review).parent)
        self.args.review = str(alias / Path(self.args.review).name)
        self.rejected_before_exec('bootstrap_linked_or_special_parent')
        self.args.review = str(self.root / 'documents' / '..' / 'documents' / Path(self.args.review).name)
        self.rejected_before_exec('bootstrap_parent_path_segment')

    def test_success_compiles_reviewed_bytes_without_external_access(self):
        class NoExternalImports:
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] in ('kaggle', 'kagglesdk', 'requests'):
                    raise AssertionError('bootstrap imported SDK or HTTP')
                return None
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, 'meta_path', [NoExternalImports(), *sys.meta_path]))
            for target, name in ((socket, 'socket'), (socket, 'create_connection'), (subprocess, 'Popen')):
                stack.enter_context(patch.object(target, name, side_effect=AssertionError('external access')))
            transport = self.collector.bootstrap(self.args)
        self.assertIs(transport, self.collector.transport)
        self.assertIs(self.collector._common, transport._common)
        self.assertIsNone(self.collector.CONFIG)
        self.assertIsNone(transport._common.ACTION_REVIEW)
        self.assertEqual(transport.COMMON_SOURCE_SHA256, sha((self.source / 'operator_common.py').read_bytes()))
        with self.assertRaisesRegex(ValueError, 'collector_already_bootstrapped'):
            self.collector.bootstrap(self.args)

    def test_self_computed_pass_review_does_not_admit_provider_execution(self):
        # Real production review/action gates remain necessary after bootstrap.
        collector = load_collector(ROOT / 'rl_collect.py')
        args = synthetic_bootstrap_arguments(self.root / 'execution-gate')
        path = Path(args.review)
        review = json.loads(path.read_bytes())
        review.update(provider_execution_admitted=True, allowed_actions=['poll'])
        path.write_bytes(encoded(review)); args.review_sha = sha(path.read_bytes())
        transport = collector.bootstrap(args)
        transport.CONFIG = SimpleNamespace(document_sha256=args.local_config_sha)
        with patch.object(transport, 'Provider') as provider:
            with self.assertRaisesRegex(ValueError, 'synthetic_review_cannot_admit_provider_execution'):
                transport.execution_gate(args, monitor=True)
            provider.assert_not_called()

    def test_retained_transport_bytes_are_executed(self):
        read = self.collector._bootstrap_read
        def read_then_change(path, digest, cap):
            raw = read(path, digest, cap)
            if Path(path).name == 'rl_transport.py':
                Path(path).write_bytes(b'raise AssertionError("unverified transport executed")\n')
            return raw
        with patch.object(self.collector, '_bootstrap_read', side_effect=read_then_change):
            transport = self.collector.bootstrap(self.args)
        self.assertTrue(callable(transport.load_contract))

    def test_reviewed_transport_update_does_not_change_collector(self):
        before = (self.source / 'rl_collect.py').read_bytes()
        path = self.source / 'rl_transport.py'
        path.write_bytes(path.read_bytes() + b'\n# Synthetic source-only transport successor.\n')
        self.bind_review()
        self.collector.bootstrap(self.args)
        self.assertEqual((self.source / 'rl_collect.py').read_bytes(), before)

    def test_original_execution_and_historical_review_binding_stay_present(self):
        tree = ast.parse((ROOT / 'rl_collect.py').read_bytes())
        bindings = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'bindings')
        text = ast.unparse(bindings)
        self.assertIn("j['transport_review_sha256'] == args.review_sha", text)
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        self.assertIn('transport.execution_gate(args, monitor=True)', ast.unparse(main))


if __name__ == '__main__':
    unittest.main()
