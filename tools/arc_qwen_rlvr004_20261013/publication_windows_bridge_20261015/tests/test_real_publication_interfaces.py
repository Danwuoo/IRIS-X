"""Synthetic offline interface closure, never candidate or runtime admission.

The real local candidate is deliberately not reconstructed here. The deployment
unit fixture supplies test-only JIT inputs; a temporary consumer changes only its
operator-pin literal to bind this current collector. Its helpers stay byte exact.
No provider, notebook execution, scorer, terminal receipt or archive is created.
Each case runs in a fresh interpreter, including under python -O.
"""
from contextlib import ExitStack, contextmanager
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT.parent / 'support'
CONSUMER = ROOT.parent / 'release/terminal-consumer'
OUTPUT_NAMES = {'active-finalized.ipynb', 'original-request.json', 'operator.json',
                'parent-private-scorer.json'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       allow_nan=False) + '\n').encode()


def load_source(name, path):
    """Keep the real collector's filename, code objects and optimization flags."""
    module = ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True,
                 optimize=sys.flags.optimize), vars(module))
    return module


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None
            for p in root.rglob('*')}


def relative_descriptor(path, root):
    raw = path.read_bytes()
    return {'path': path.relative_to(root).as_posix(), 'bytes': len(raw),
            'sha256': sha(raw)}


def synthetic_consumer(root, *, collector_sha256=None):
    """Temporary acyclic test pins, not an independent production review."""
    root.mkdir()
    inventory_raw = (CONSUMER / 'CONSUMER-INVENTORY.json').read_bytes()
    inventory = json.loads(inventory_raw)
    for name, digest in inventory['files'].items():
        raw = (CONSUMER / name).read_bytes()
        if sha(raw) != digest:
            raise AssertionError('tracked consumer helper inventory drift: ' + name)
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (root / 'CONSUMER-INVENTORY.json').write_bytes(inventory_raw)
    pins = {'format': 'owned-rl-batched-consumer-operator-v1',
            'source_sha256': '1' * 64, 'source_archive_sha256': '2' * 64,
            'policy_sha256': sha(b'synthetic-only-phase-policy'),
            'release_sha256': sha(b'synthetic-only-consumer-release'),
            'collector_entry_sha256': (collector_sha256 if collector_sha256 is not None
                                       else sha((ROOT / 'rl_collect.py').read_bytes())),
            'helper_inventory_sha256': sha(inventory_raw)}
    pin_raw = encoded(pins)
    (root / 'CONSUMER-OPERATOR.json').write_bytes(pin_raw)
    original = (CONSUMER / 'reviewed_entry.py').read_bytes()
    pattern = rb"(?m)^REVIEWED_OPERATOR_PINS_SHA256 = '[0-9a-f]{64}'$"
    replacement = ('REVIEWED_OPERATOR_PINS_SHA256 = ' + repr(sha(pin_raw))).encode()
    entry, count = re.subn(pattern, replacement, original)
    if count != 1:
        raise AssertionError('exactly one test-only reviewed entry pin required')
    (root / 'reviewed_entry.py').write_bytes(entry)
    return pins


def synthetic_review(transport, root, consumer, manifest):
    """Exercise the real monitor gate with a clearly synthetic review closure."""
    manifest_path = root / 'synthetic-publication-manifest.json'
    manifest_path.write_bytes(encoded(manifest))
    config_sha = sha(b'synthetic-only-local-configuration')
    material_sha = sha(b'synthetic-only-material-approval')
    # These are the instances used by this transport (and by this collector).
    transport.CONFIG = transport._common.CONFIG = SimpleNamespace(document_sha256=config_sha)
    review = {'status': 'PASS', 'synthetic_test_only': True,
              'local_config_sha256': config_sha,
              'publication_manifest_sha256': sha(manifest_path.read_bytes()),
              'material_approval_sha256': material_sha,
              'operator_files': {name: sha((ROOT / name).read_bytes())
                                 for name in transport.OPERATOR_SOURCE_NAMES},
              'consumer_files': {p.relative_to(consumer).as_posix(): sha(p.read_bytes())
                                 for p in consumer.rglob('*') if p.is_file()}}
    review_path = root / 'synthetic-monitor-review.json'
    review_path.write_bytes(encoded(review))
    return SimpleNamespace(manifest=str(manifest_path),
        manifest_sha=review['publication_manifest_sha256'], material_sha=material_sha,
        monitor_review=str(review_path), monitor_sha=sha(review_path.read_bytes()),
        consumer_root=str(consumer))


@contextmanager
def offline_only(*modules):
    """Fail rather than reaching an external, model or state-writing boundary."""
    class NoExternalImports:
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split('.')[0] in {'kaggle', 'kagglesdk', 'requests', 'torch',
                                          'transformers', 'tensorflow'}:
                raise AssertionError('synthetic test forbids external/model import')
            return None

    guard = NoExternalImports()
    sys.meta_path.insert(0, guard)
    try:
        with ExitStack() as stack:
            for module in modules:
                for name in ('Provider', 'write_new'):
                    stack.enter_context(patch.object(module, name,
                        side_effect=AssertionError('synthetic test forbids ' + name)))
            for target, name in ((socket, 'socket'), (socket, 'create_connection'),
                                 (subprocess, 'Popen')):
                stack.enter_context(patch.object(target, name,
                    side_effect=AssertionError('synthetic test forbids external execution')))
            yield
    finally:
        sys.meta_path.remove(guard)


@contextmanager
def trace_calls(*, forbidden=()):
    """Observe unchanged code; never wrap the authenticated caller or helpers."""
    calls, returned = [], {}

    def profile(frame, event, value):
        key = (frame.f_code.co_filename, frame.f_code.co_name)
        if event == 'call':
            if key in forbidden:
                raise AssertionError('synthetic test forbids scorer/content validation: ' + key[1])
            calls.append((key, frame.f_locals.get('epoch'), frame.f_locals.get('operation')))
        elif event == 'return' and frame.f_code.co_name in {
                'finalized_documents', 'receive_authenticated_collection', '_load_helpers'}:
            returned[key] = value
        elif event == 'return' and frame.f_code.co_name == 'kernel_wire':
            returned[(*key, frame.f_locals['n']['role'])] = value

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        yield calls, returned
    finally:
        sys.setprofile(previous)


def exercise_preflight(test, root):
    transport = load_source('real_interface_transport', ROOT / 'rl_transport.py')
    # Reuse the existing no-model fixture, not the ignored admission candidate.
    fixture = load_source('real_interface_deployment_fixture', SUPPORT / 'tests/test_deployment.py')
    factory = fixture.DeploymentTests('test_jit_determinism_and_chain')
    factory.root = root
    candidate, release = factory.candidate()
    finalizer = candidate / 'synthetic-finalize.py'
    finalizer.write_bytes((SUPPORT / 'assembly/finalize.py').read_bytes())
    builder_path = candidate / 'code-payload/deployment/notebook_builder.py'
    loader_path = candidate / 'code-payload/deployment/source_loader.py'
    builder = load_source('real_interface_fixture_builder', builder_path)
    notebooks = []
    for role, kind, active in (('inactive', 'inactive', False),
                                ('rlvr004', 'active-template', True)):
        path = candidate / (kind + '.ipynb')
        path.write_bytes(encoded(builder.build(release, loader_path.read_text(), kind=kind)))
        notebooks.append({**relative_descriptor(path, candidate), 'role': role,
            'title': 'Synthetic offline interface fixture', 'enable_gpu': active,
            'save_version_value': 1 if active else 3,
            'session_timeout_seconds': 42300 if active else None,
            'machine_shape': 'NvidiaRtxPro6000' if active else None})
    consumer = root / 'synthetic-consumer'
    pins = synthetic_consumer(consumer)
    manifest = {'synthetic_test_only': True, 'runtime_source_sha256': release['source_sha256'],
        'consumer_contract': {'source_sha256': pins['source_sha256'],
            'source_archive': {'sha256': pins['source_archive_sha256']},
            'material_review': {'sha256': release['material_review_sha256']},
            'phase_policy': {'sha256': pins['policy_sha256']},
            'release': {'sha256': pins['release_sha256']}},
        'jit': {'entry': relative_descriptor(finalizer, candidate),
            'dependencies': [relative_descriptor(p, candidate) for p in
                (candidate / 'notebook-release.json', builder_path, loader_path)],
            'output_documents': sorted(OUTPUT_NAMES)}, 'notebooks': notebooks,
        'datasets': [{'transport_archive': {'path': 'synthetic-code-upload.zip',
            'bytes': 100, 'sha256': sha(b'synthetic-upload-descriptor-only')}}]}
    args = synthetic_review(transport, candidate, consumer, manifest)
    transport.PINS = ['synthetic-owner/synthetic-code/1']
    before = snapshot(root)
    with offline_only(transport, transport._common), trace_calls() as (calls, returned):
        result = transport.publication_preflight(manifest, args)
    test.assertEqual(result['status'], 'OFFLINE_PUBLICATION_CLOSURE_PASS')
    test.assertEqual(result['synthetic_epoch'], 1)
    test.assertEqual((result['provider_calls'], result['state_writes']), (0, 0))
    test.assertIs(result['production_dispatch_admitted'], False)
    test.assertIs(result['actual_epoch_reserved'], False)
    test.assertIs(result['genuine_numeric_mount_inactive_audit_active_wire_still_required'], True)
    documents = returned[(str(ROOT / 'rl_transport.py'), 'finalized_documents')]
    test.assertEqual(set(documents), OUTPUT_NAMES)
    test.assertEqual(result['synthetic_finalizer_documents'],
        {name: {'bytes': len(raw), 'sha256': sha(raw)} for name, raw in documents.items()})
    test.assertEqual(transport.config(documents['active-finalized.ipynb'])['PREDISPATCH_EPOCH'], 1)
    test.assertEqual(json.loads(documents['original-request.json'])['original_epoch'], 1)
    test.assertEqual(snapshot(root), before)
    for name in OUTPUT_NAMES:
        test.assertFalse(any(p.name == name for p in root.rglob('*')))
    test.assertIn(((str(finalizer), 'finalize'), 1, None), calls)
    test.assertIn((str(builder_path), 'build'), [row[0] for row in calls])
    test.assertEqual([row[2] for row in calls if row[0] ==
        (str(ROOT / 'protocol.py'), 'validate_request')], ['start_upload', 'save', 'save'])
    test.assertEqual(sum(row[0] == (str(ROOT / 'rl_transport.py'), 'kernel_wire')
                         for row in calls), 2)
    test.assertEqual(set(result['static_wire_sha256']), {'inactive', 'rlvr004'})
    test.assertNotEqual(*result['static_wire_sha256'].values())
    for role, execution_type in (('inactive', 3), ('rlvr004', 1)):
        wire = returned[(str(ROOT / 'rl_transport.py'), 'kernel_wire', role)]
        test.assertEqual(wire['kernel_execution_type'], execution_type)
        test.assertIs(wire['enable_gpu'], role == 'rlvr004')
        test.assertEqual(result['static_wire_sha256'][role], sha(transport.canonical(wire)))
        if role == 'rlvr004':
            test.assertEqual(wire['text'].encode(), documents['active-finalized.ipynb'])
        else:
            test.assertEqual(wire['text'].encode(), (candidate / 'inactive.ipynb').read_bytes())
    return {'status': 'PASS', 'case': 'real-preflight', 'synthetic_epoch': 1,
            'persisted_finalizer_outputs': False, 'provider_calls': 0}


def exercise_collector(test, root):
    collector = load_source('real_interface_current_collector', ROOT / 'rl_collect.py')
    fixture = load_source('real_interface_bootstrap_fixture', ROOT / 'tests/test_collector_bootstrap.py')
    collector.bootstrap(fixture.synthetic_bootstrap_arguments(root / 'bootstrap'))
    consumer = root / 'synthetic-consumer'
    pins = synthetic_consumer(consumer)
    manifest = {'synthetic_test_only': True,
                'consumer_contract': {'source_root': 'synthetic-absent-source'}}
    args = synthetic_review(collector.transport, root, consumer, manifest)
    body = {key: pins[key] for key in
            ('source_sha256', 'source_archive_sha256', 'policy_sha256', 'release_sha256')}
    body.update({key: sha(('synthetic-only-' + key).encode()) for key in
        ('launch_sha256', 'artifact_inventory_sha256', 'dataset_sha256', 'archive_sha256',
         'terminal_sha256', 'owner_request_sha256', 'outer_closure_sha256')})
    body.update(format='owned-rl-batched-authenticated-collection-v1',
                checkpoint_archive_observation=None)
    envelope = root / 'synthetic-collection.json'
    envelope.write_bytes(encoded(body))
    archive = root / 'synthetic-absent-archive.zip'
    terminal = root / 'synthetic-absent-terminal.json'
    collector.OUT = root / 'synthetic-output-not-created'
    prefix = '_owned_batched_consumer_' + pins['helper_inventory_sha256']
    test.assertFalse(any(name == prefix or name.startswith(prefix + '.') for name in sys.modules))
    # A structurally valid envelope is insufficient from an arbitrary caller.
    direct_entry = load_source('real_interface_arbitrary_caller_probe', consumer / 'reviewed_entry.py')
    with offline_only(collector, collector.transport, collector._common):
        with test.assertRaisesRegex(ValueError,
                r'^authenticated expectation requires reviewed collector callsite$'):
            direct_entry.receive_authenticated_collection(envelope, sha(envelope.read_bytes()),
                operator_pins_path=consumer / 'CONSUMER-OPERATOR.json')
    test.assertFalse(direct_entry._CONTEXTS)
    # A consistently rebound entry/operator with an obsolete collector pin must
    # still fail the actual monitor gate, before any helper import or capability.
    stale_root = root / 'synthetic-stale-collector-case'
    stale_root.mkdir()
    stale_consumer = stale_root / 'consumer'
    synthetic_consumer(stale_consumer, collector_sha256='0' * 64)
    stale_args = synthetic_review(collector.transport, stale_root, stale_consumer, manifest)
    with offline_only(collector, collector.transport, collector._common):
        with test.assertRaisesRegex(collector.transport.GuardError,
                                   r'^consumer_collector_closure_link$'):
            collector.validate_received(manifest, stale_args, envelope,
                root / 'synthetic-absent-release', archive, terminal)
    test.assertNotIn('reviewed_rl_terminal_entry', sys.modules)
    test.assertFalse(any(name == prefix or name.startswith(prefix + '.') for name in sys.modules))
    forbidden = {(str(consumer / 'consumer/validate_owned_outputs.py'), 'validate_owned_outputs'),
                 (str(consumer / 'consumer/public_checks.py'), 'validate_public'),
                 (str(consumer / 'consumer/public_checks.py'), 'scorer_rows')}
    before = snapshot(root)
    with offline_only(collector, collector.transport, collector._common), \
            trace_calls(forbidden=forbidden) as (calls, returned):
        with test.assertRaisesRegex(ValueError,
                r'^missing regular artifact: synthetic-absent-terminal\.json$') as raised:
            collector.validate_received(manifest, args, envelope,
                root / 'synthetic-absent-release', archive, terminal)
    safe_io = sys.modules[prefix + '.consumer.safe_io']
    test.assertIs(type(raised.exception), safe_io.EvidenceError)
    entry = sys.modules['reviewed_rl_terminal_entry']
    context = returned[(str(consumer / 'reviewed_entry.py'), 'receive_authenticated_collection')]
    test.assertIs(type(context), entry.CollectionContext)
    validator = returned[(str(consumer / 'reviewed_entry.py'), '_load_helpers')]
    test.assertIs(validator, sys.modules[prefix + '.production'].validate_received_collection)
    required_calls = [(ROOT / 'rl_collect.py', 'validate_received'),
        (consumer / 'reviewed_entry.py', 'receive_authenticated_collection'),
        (consumer / 'reviewed_entry.py', 'validate_reviewed'),
        (consumer / 'reviewed_entry.py', '_load_helpers'),
        (consumer / 'production.py', 'validate_received_collection'),
        (consumer / 'production.py', '_transport'), (consumer / 'terminal.py', 'verify_terminal')]
    positions = [[row[0] for row in calls].index((str(path), name)) for path, name in required_calls]
    test.assertEqual(positions, sorted(positions))
    test.assertNotIn((str(consumer / 'consumer/validate_owned_outputs.py'), 'validate_owned_outputs'),
                     [row[0] for row in calls])
    test.assertEqual(snapshot(root), before)
    test.assertFalse(archive.exists())
    test.assertFalse(terminal.exists())
    test.assertFalse(collector.OUT.exists())
    return {'status': 'PASS', 'case': 'real-current-collector',
            'exact_failure': str(raised.exception), 'actual_caller_authenticated': True,
            'real_helpers_imported': True, 'terminal_or_scientific_admission': False,
            'arbitrary_caller_rejected': True, 'stale_collector_pin_rejected': True,
            'provider_or_scorer_called': False}


class RealPublicationInterfaceTests(unittest.TestCase):
    def run_fresh(self, case):
        flags = ['-B'] + ['-O'] * sys.flags.optimize
        result = subprocess.run([sys.executable, *flags, str(Path(__file__).resolve()),
            '--synthetic-worker', case], stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=45, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['optimization'], sys.flags.optimize)
        return report

    def test_real_preflight_finalizer_builder_and_wire_protocol(self):
        report = self.run_fresh('preflight')
        self.assertEqual(report['case'], 'real-preflight')
        self.assertEqual(report['synthetic_epoch'], 1)
        self.assertIs(report['persisted_finalizer_outputs'], False)

    def test_current_collector_authenticates_then_rejects_absent_evidence(self):
        report = self.run_fresh('collector')
        self.assertEqual(report['exact_failure'],
                         'missing regular artifact: synthetic-absent-terminal.json')
        self.assertIs(report['actual_caller_authenticated'], True)
        self.assertIs(report['real_helpers_imported'], True)
        self.assertIs(report['terminal_or_scientific_admission'], False)
        self.assertIs(report['arbitrary_caller_rejected'], True)
        self.assertIs(report['stale_collector_pin_rejected'], True)
        self.assertIs(report['provider_or_scorer_called'], False)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--synthetic-worker':
        operation = {'preflight': exercise_preflight, 'collector': exercise_collector}[sys.argv[2]]
        with tempfile.TemporaryDirectory(prefix='irisx-synthetic-interface-') as temporary:
            report = operation(unittest.TestCase(), Path(temporary))
        report['optimization'] = sys.flags.optimize
        print(json.dumps(report, sort_keys=True))
    else:
        unittest.main()
