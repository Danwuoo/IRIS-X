"""Offline provenance, preservation and exact-repair regressions for run007."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid

from . import local_assemble_run007 as a
from . import local_accept_numeric_mount_run007 as mount

REPO = Path(__file__).absolute().parents[3]
ROOT = REPO / '.irisx/run007-local'


class ContractRejections(unittest.TestCase):
    def test_duplicate_json_key_rejects(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            a.obj(b'{"version":19,"version":20}')

    def test_nonfinite_json_rejects(self):
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            a.obj(b'{"epoch":NaN}')

    def test_unsafe_relative_path_rejects(self):
        for name in ('../state', '/state', 'state\\receipt', 'state:receipt'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                a.p.relative(name)

    def test_bool_version_rejects(self):
        doc = {'format': 'irisx/preparation-successor-proposed-identity-v1',
            'status': 'PROPOSED_NOT_PROVIDER_RESERVED', 'run_id': 'irisx-qwen14b-rlvr-20261013-run007',
            'versions': {'code_predecessor': 19, 'code': True, 'notebook_predecessor': 37, 'inactive': 38, 'active': 39}}
        with self.assertRaisesRegex(ValueError, 'integer'):
            a.p.identity(a.encoded(doc))

    def test_nonconsecutive_allocation_rejects(self):
        doc = {'format': 'irisx/preparation-successor-proposed-identity-v1',
            'status': 'PROPOSED_NOT_PROVIDER_RESERVED', 'run_id': 'irisx-qwen14b-rlvr-20261013-run007',
            'versions': {'code_predecessor': 19, 'code': 20, 'notebook_predecessor': 37, 'inactive': 39, 'active': 40}}
        with self.assertRaisesRegex(ValueError, 'consecutive'):
            a.p.identity(a.encoded(doc))

    def test_source_read_symlink_rejects_before_body(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'actual').write_bytes(b'not a receipt')
            (root / 'alias').symlink_to(root / 'actual')
            with self.assertRaisesRegex(ValueError, 'linked'):
                a.read(root / 'alias')

    def test_source_read_hardlink_rejects(self):
        import os
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'actual').write_bytes(b'not a receipt')
            os.link(root / 'actual', root / 'alias')
            with self.assertRaisesRegex(ValueError, 'regular'):
                a.read(root / 'alias')

    def test_invented_successful_owned_closure_rejects(self):
        class Guard:
            @staticmethod
            def verify_closed_proof(proof):
                pass
        for record in ({'returncode': True, 'worker_returncode': 0, 'forced': False},
                       {'returncode': 0, 'worker_returncode': 0, 'forced': True},
                       {'returncode': 0, 'worker_returncode': 1, 'forced': False}):
            with self.subTest(record=record), self.assertRaises(ValueError):
                mount.check_closure(Guard, record)


@unittest.skipUnless((ROOT / 'v37-lineage-proof/LAUNCH-LINEAGE.json').is_file(),
                     'authentic original v37 supplement not present in clean source-only checkout')
class ActualV37Provenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helper = a.p.load_module(a.pinned(a.HERE / 'run006_lineage.py', a.RUN006_LINEAGE_SHA),
            'run007_test_actual_lineage', a.HERE / 'run006_lineage.py')
        cls.bundle = ROOT / 'v37-lineage-proof'
        cls.proof_raw = a.read(cls.bundle / 'LAUNCH-LINEAGE.json')
        cls.proof = cls.helper.verify(cls.bundle, a.sha(cls.proof_raw))

    def test_actual_four_document_wire_chain_and_clock_replay(self):
        self.assertEqual(self.proof['original_epoch'], 1791901490)
        self.assertEqual(self.proof['original_deadline'], 1791944690)
        self.assertEqual(self.proof['notebook_version'], 37)
        self.assertEqual(self.proof['code_version'], 19)
        self.assertTrue(self.proof['v37_original_dispatch_chain_verified'])
        for key in ('runtime_or_model_closure_verified', 'physical_costs_known', 'scientific_result_verified'):
            self.assertIs(self.proof[key], False)
        self.assertEqual(self.proof['provider_calls'], 0)
        self.assertEqual(self.proof['model_or_GPU_calls'], 0)

    def test_current_packet_binds_actual_terminal_source(self):
        raw = a.read(ROOT / 'sealed-inputs/observation/OBSERVATION.json')
        checked = a.observation_inputs(ROOT / 'sealed-inputs/observation', a.sha(raw))
        packet = a.obj(checked['current-predecessor-v37/OBSERVATION.json'])
        self.assertEqual(packet['provider_status'], 'ERROR')
        self.assertEqual(packet['saved_source_sha256'], self.proof['saved_source_sha256'])

    def test_original_clock_reset_rejects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'bundle'
            shutil.copytree(self.bundle, root)
            proof = copy.deepcopy(self.proof)
            proof['original_epoch'] += 1
            body = a.encoded(proof)
            (root / 'LAUNCH-LINEAGE.json').write_bytes(body)
            with self.assertRaisesRegex(ValueError, 'alter original identity'):
                self.helper.verify(root, a.sha(body))

    def test_launch_proof_cannot_promote_scientific_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'bundle'
            shutil.copytree(self.bundle, root)
            proof = copy.deepcopy(self.proof)
            proof['scientific_result_verified'] = True
            body = a.encoded(proof)
            (root / 'LAUNCH-LINEAGE.json').write_bytes(body)
            with self.assertRaisesRegex(ValueError, 'promote closure'):
                self.helper.verify(root, a.sha(body))

    def test_unknown_supplement_file_rejects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'bundle'
            shutil.copytree(self.bundle, root)
            (root / 'new-receipt.json').write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError, 'unknown'):
                self.helper.verify(root, a.sha(self.proof_raw))

    def test_output_inside_original_state_or_candidate_rejects(self):
        old = REPO / '.irisx/run006-local'
        inputs = dict(repository_root=REPO, base_root=old / 'inputs/candidate-run005',
            source_proposal_root=ROOT / 'source-proposal', observation_root=ROOT / 'sealed-inputs/observation',
            observation_sha='0' * 64, stop_attestation_path=ROOT / 'OWNER-REQUEST.json', stop_attestation_sha='0' * 64,
            solver_path=old / 'inputs/target-free-dataset-namespace-inputs/derived-code18-target-free-solver.json',
            new_solver_path=ROOT / 'source-proposal/review-only/solver-descriptor.json',
            solver_review_path=ROOT / 'reviews/solver-namespace-review.json', solver_review_sha='0' * 64,
            collector_path=REPO / 'tools/arc_qwen_rlvr004_20261013/publication_run007/rl_collect.py',
            collector_sha='0' * 64, mode='proposal', source_proposal_inventory_sha='0' * 64,
            run006_candidate_root=old / 'candidate-run006', run006_state_root=old / 'ops/state-run006',
            run006_state_inventory_path=ROOT / 'sealed-inputs/RUN006-STATE-INVENTORY.json',
            run006_state_inventory_sha='0' * 64)
        for source in (inputs['run006_candidate_root'], inputs['run006_state_root']):
            output = source / ('negative-overlap-' + uuid.uuid4().hex)
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'overlap'):
                a.assemble(output_root=output, **inputs)
            self.assertFalse(output.exists())


@unittest.skipUnless((ROOT / 'candidate-run007/publication-manifest.json').is_file(),
                     'independently reviewed final run007 candidate not retained in source-only checkout')
class ActualRun007Finalizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = ROOT / 'candidate-run007'
        cls.manifest = a.obj(a.read(cls.candidate / 'publication-manifest.json'))
        entry = cls.manifest['jit']['entry']
        cls.helper = a.p.load_module(a.pinned(cls.candidate / entry['path'], entry['sha256']),
            'test_actual_run007_pure_finalizer', cls.candidate / entry['path'])
        cls.epoch = int(a.obj(a.read(ROOT / 'sealed-inputs/observation/OBSERVATION.json'))['observed_epoch'])
        cls.documents = cls.helper.finalize(cls.candidate, cls.epoch)

    def test_real_four_documents_bind_new_source_and_owner(self):
        self.assertEqual(set(self.documents), {'active-finalized.ipynb', 'original-request.json',
            'operator.json', 'parent-private-scorer.json'})
        owner = a.obj(self.documents['original-request.json'])
        operator = a.obj(self.documents['operator.json'])
        parent = a.obj(self.documents['parent-private-scorer.json'])
        self.assertEqual(owner['original_epoch'], self.epoch)
        self.assertEqual(operator['original_epoch'], self.epoch)
        self.assertEqual(operator['raw_source_sha256'], self.manifest['runtime_source_sha256'])
        self.assertEqual(operator['original_request_sha256'], a.sha(self.documents['original-request.json']))
        self.assertEqual(operator['parent_scorer_sha256'], a.sha(self.documents['parent-private-scorer.json']))
        self.assertEqual(parent['raw_source_sha256'], self.manifest['runtime_source_sha256'])
        self.assertEqual(parent['original_request_sha256'], a.sha(self.documents['original-request.json']))
        notebook = a.obj(self.documents['active-finalized.ipynb'])
        self.assertEqual(notebook['metadata']['owned_rl_release']['operator_sha256'],
                         a.sha(self.documents['operator.json']))

    def test_active_wire_preserves_limits_paths_and_full_inputs(self):
        from tools.arc_qwen_rlvr004_20261013.publication_run007 import rl_transport as transport
        notebook = self.documents['active-finalized.ipynb']
        config = transport.config(notebook)
        self.assertIs(config['MANUAL_START'], True)
        self.assertIs(config['ENABLE_MODEL'], True)
        self.assertEqual(config['PREDISPATCH_EPOCH'], self.epoch)
        self.assertEqual(config['OUTPUT_ROOT'], '/kaggle/working/irisx-qwen14b-rlvr-20261013-run007')
        self.assertEqual(config['SOURCE_PARENT'], '/kaggle/working/irisx-qwen14b-rlvr-20261013-source007')
        self.assertEqual(config['SESSION_SECONDS'], 43200)
        self.assertEqual(config['EXECUTION_CUTOFF_SECONDS'], 42000)
        self.assertEqual(config['OUTER_CUTOFF_SECONDS'], 42180)
        self.assertEqual(config['PROVIDER_RUNTIME_SECONDS'], 42300)
        row = next(n for n in self.manifest['notebooks'] if n['role'] == 'rlvr004')
        transport.PINS = row['dataset_sources']
        wire = transport.kernel_wire(row, notebook)
        self.assertEqual(wire['dataset_data_sources'], row['dataset_sources'])
        self.assertEqual(wire['dataset_data_sources'][1:], transport.NON_CODE_PINS)
        self.assertEqual(wire['machine_shape'], 'NvidiaRtxPro6000')
        self.assertIs(wire['is_private'], True)
        self.assertIs(wire['enable_internet'], False)
        self.assertIs(wire['enable_tpu'], False)
        self.assertIs(wire['enable_gpu'], True)
        self.assertEqual(wire['kernel_execution_type'], 1)
        self.assertEqual(wire['session_timeout_seconds'], 42300)


if __name__ == '__main__':
    unittest.main()
