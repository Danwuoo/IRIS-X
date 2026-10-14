"""CPU-only admission tests. In-memory synthetic reviews are never launch receipts."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile
sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from tools.arc_qwen_rlvr004_20261013.admission_run008 import assemble as a
from tools.arc_qwen_rlvr004_20261013.admission_run008 import seal_inputs
from tools.arc_qwen_rlvr004_20261013.admission_run008 import accept_numeric_mount as mount
SCRATCH = Path(os.environ.get('IRISX_RUN008_TEST_SCRATCH', REPO / '.irisx/run008-admission/tests'))
SCRATCH.mkdir(parents=True, exist_ok=True)
REBUILD = REPO / '.irisx/transfer-verification-20261013/rebuild-offline-2'
PROPOSAL = REPO / '.irisx/run008-packaging/independent-reviewed-proposal'
BRACKET = REPO / '.irisx/run008-live-20261014/bracket-0001'
OWNER = REPO / '.irisx/run008-live-20261014/OWNER-DIRECTION.json'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_output(repository, output):
    """Test-only relocation; production CLI always uses its strict ignored root."""
    out = a.p.ordinary(output)
    a.need(out.is_relative_to(SCRATCH) and out != SCRATCH and not out.exists(), 'fresh test-local output')
    return out


class AdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='admission-', dir=SCRATCH)
        cls.root = Path(cls.tmp.name)
        cls.relocate = patch.object(a, 'output_path', side_effect=test_output)
        cls.relocate.start()
        seal = seal_inputs.seal(repository_root=REPO, observation_root=BRACKET,
            observation_sha=a.sha((BRACKET / 'OBSERVATION.json').read_bytes()), output_root=cls.root / 'observation')
        collector = HERE.parent / 'publication_run008/rl_collect.py'
        cls.args = dict(repository_root=REPO, source_proposal_root=PROPOSAL, base_root=REBUILD / 'candidate-rebuild',
            observation_root=cls.root / 'observation', observation_sha=seal['observation_sha256'],
            owner_direction_path=OWNER, owner_direction_sha=a.sha(OWNER.read_bytes()),
            collector_path=collector, collector_sha=a.sha(collector.read_bytes()))
        cls.candidate = cls.root / 'draft'
        cls.result = a.assemble(**cls.args, output_root=cls.candidate)
        cls.proposal_raw = (cls.candidate / 'ADMISSION-PROPOSAL.json').read_bytes()
        cls.proposal = a.obj(cls.proposal_raw)
        cls.release = a.obj((cls.candidate / 'notebook-release.json').read_bytes())
        cls.finalizer = load('admission_test_finalizer', cls.candidate / 'assembly/finalize.py')
        cls.loader = load('admission_test_loader', cls.candidate / 'code-payload/deployment/source_loader.py')
        cls.launch = load('admission_test_launch', cls.candidate / 'code-payload/deployment/launch_notebook.py')
        cls.guard = load('admission_test_guard', cls.candidate / 'producer-source/baseline/tools/arc_learning_agent_20261011/process_guard.py')

    @classmethod
    def tearDownClass(cls):
        cls.relocate.stop()
        cls.tmp.cleanup()

    def test_01_deterministic_numeric_draft(self):
        other = self.root / 'repeat'
        result = a.assemble(**self.args, output_root=other)
        self.assertEqual(self.result['assembly_inventory_sha256'], result['assembly_inventory_sha256'])
        self.assertEqual(result['versions'], {'code_predecessor': 20, 'code': 21, 'notebook_predecessor': 39, 'inactive': 40, 'active': 41})
        self.assertIsNone(result['successor_epoch'])
        self.assertFalse(self.release['production_admitted'])

    def test_02_reviewed_runtime_and_helpers_unchanged(self):
        self.assertEqual(self.result['source_sha256'], a.SOURCE_SHA)
        self.assertEqual(self.result['source_archive_sha256'], a.ARCHIVE_SHA)
        self.assertEqual((self.candidate / 'code-payload/source.zip').read_bytes(), (PROPOSAL / 'code-payload/source.zip').read_bytes())
        inventory = a.obj((self.candidate / 'terminal-consumer/CONSUMER-INVENTORY.json').read_bytes())
        self.assertEqual(len(inventory['files']), 21)
        for name, digest in inventory['files'].items():
            self.assertEqual(a.sha((self.candidate / 'terminal-consumer' / name).read_bytes()), digest)
        self.assertEqual(self.release['phase_policy_sha256'], self.proposal['phase_policy_sha256'])

    def test_03_draft_finalizer_refuses(self):
        with self.assertRaisesRegex(ValueError, 'independently admitted'):
            self.finalizer.finalize(self.candidate, 1792000000)
        for epoch in (None, True, 0, -1, 1.5):
            with self.assertRaises(ValueError): self.finalizer.finalize(self.candidate, epoch)

    def test_04_both_templates_inert(self):
        for kind in ('inactive', 'active-template'):
            notebook = a.obj((self.candidate / ('run008-' + kind + '.ipynb')).read_bytes())
            code = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')
            with patch('sys.stdout', new=io.StringIO()):
                ns = {}; exec(compile(code, '<test-inert-numeric>', 'exec'), ns)
            self.assertEqual(ns['RESULT'], {'status': 'INACTIVE_NO_EXECUTION', 'model_loaded': False, 'filesystem_accessed': False})
            self.assertEqual(ns['SESSION_SECONDS'], 43200)
            self.assertIsNone(ns['PREDISPATCH_EPOCH'])

    def test_05_source_only_upload(self):
        with zipfile.ZipFile(self.candidate / 'code-upload.zip') as archive:
            actual = set(archive.namelist())
        self.assertEqual(actual, {p.relative_to(self.candidate / 'code-payload').as_posix() for p in (self.candidate / 'code-payload').rglob('*') if p.is_file()})
        self.assertFalse(any('solver-descriptor' in n or n.startswith(('review/', 'historical', 'current-predecessor', 'evaluator')) for n in actual))

    def test_06_solver_two_paths(self):
        old = (REBUILD / 'source-rebuild/review-only/solver-descriptor.json').read_bytes()
        new = (self.candidate / 'review-only/solver-descriptor.json').read_bytes()
        self.assertEqual(new.replace(a.RUN.encode(), a.s.OLD_RUN.encode()), old)
        self.assertEqual(new.count(a.RUN.encode()), 2)

    def test_07_actual_bracket_and_owner_preserved(self):
        root = self.candidate / 'current-predecessor'
        for name in ('saved_source.ipynb', 'metadata-before.json', 'metadata-after.json', 'dataset.json', 'dataset-after.json', 'status.json'):
            self.assertEqual((root / name).read_bytes(), (BRACKET / name).read_bytes())
        self.assertEqual((root / 'publisher-observation.json').read_bytes(), (BRACKET / 'OBSERVATION.json').read_bytes())
        self.assertEqual((self.candidate / 'OWNER-DIRECTION.json').read_bytes(), OWNER.read_bytes())

    def test_08_all_review_receipts_required(self):
        for path, sha_ in ((None, None), (REBUILD / 'candidate-rebuild/SUCCESSOR-PROPOSAL.json', 'a' * 64)):
            with self.assertRaises((TypeError, ValueError)):
                a.assemble(**self.args, output_root=self.root / 'no-final', mode='final', proposal_path=path, proposal_sha=sha_)
        self.assertFalse((self.root / 'no-final').exists())

    def test_09_changed_proposal_rejected_before_approvals(self):
        modified = self.root / 'modified-proposal.json'
        modified.write_bytes(self.proposal_raw + b' ')
        with self.assertRaisesRegex(ValueError, 'differs from independently reviewed proposal'):
            a.assemble(**self.args, output_root=self.root / 'no-change', mode='final', proposal_path=modified, proposal_sha=a.sha(modified.read_bytes()))
        self.assertFalse((self.root / 'no-change').exists())

    def test_10_historical_approval_not_reused(self):
        historical = REBUILD / 'candidate-rebuild/code-payload/release/RUNTIME-REVIEW.json'
        kwargs = dict(proposal_path=self.candidate / 'ADMISSION-PROPOSAL.json', proposal_sha=a.sha(self.proposal_raw),
            solver_review_path=historical, solver_review_sha=a.sha(historical.read_bytes()), runtime_review_path=None,
            runtime_review_sha=None, material_review_path=None, material_review_sha=None,
            original_solver=(REBUILD / 'source-rebuild/review-only/solver-descriptor.json').read_bytes(),
            new_solver=(self.candidate / 'review-only/solver-descriptor.json').read_bytes())
        with self.assertRaisesRegex(ValueError, 'independent exact two-path'):
            a.review_inputs(self.proposal, **kwargs)

    def test_11_owner_scope_cannot_weaken(self):
        document = a.obj(OWNER.read_bytes()); document['public_query_denominator'] = 166
        path = self.root / 'bad-owner.json'; path.write_bytes(a.encoded(document))
        with self.assertRaisesRegex(ValueError, 'full clock/scorer'): a.owner_inputs(path, a.sha(path.read_bytes()))
        document['public_query_denominator'] = 167; document['new_resource_or_paid_provisioning_authorized'] = True
        path.write_bytes(a.encoded(document))
        with self.assertRaisesRegex(ValueError, 'bounded continuation'): a.owner_inputs(path, a.sha(path.read_bytes()))

    def test_12_live_bracket_closed_and_terminal(self):
        root = self.root / 'bad-observation'; shutil.copytree(self.args['observation_root'], root)
        (root / 'unknown').write_bytes(b'fixture')
        with self.assertRaisesRegex(ValueError, 'closed observation'): a.observation_inputs(root, self.args['observation_sha'])
        (root / 'unknown').unlink(); path = root / 'OBSERVATION.json'; document = a.obj(path.read_bytes())
        document['provider_status'] = 'RUNNING'; path.write_bytes(a.encoded(document))
        with self.assertRaisesRegex(ValueError, 'terminal actual'): a.observation_inputs(root, a.sha(path.read_bytes()))

    def test_13_output_failure_cleans_only_new_output(self):
        output = self.root / 'partial'
        with patch.object(a.s, 'read', side_effect=OSError('synthetic output roundtrip failure')):
            with self.assertRaisesRegex(OSError, 'synthetic output'):
                a.s.write_output(output, {'file': b'fixture'})
        self.assertFalse(output.exists())
        self.assertTrue(self.candidate.exists())

    def test_14_no_model_mount_acceptance(self):
        output = self.root / 'no-model'
        proc = subprocess.run([sys.executable, '-I', '-B', *(['-O'] if sys.flags.optimize else []),
            str(self.candidate / 'assembly/accept_downloaded_mount.py'), '--candidate-root', str(self.candidate),
            '--code-root', str(self.candidate / 'code-payload'), '--output-root', str(output)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
            env={'PATH': os.defpath, 'LANG': 'C.UTF-8'})
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        result = json.loads(proc.stdout)
        self.assertFalse(result['isolated_import']['model_libraries_imported'])
        self.assertFalse(result['provider_provenance_verified_by_this_helper'])
        self.assertEqual(result['expected_code_reference'], a.DREF + '/21')

    def test_15_corrupt_code_mount_rejected(self):
        root = self.root / 'bad-code'; shutil.copytree(self.candidate / 'code-payload', root)
        (root / 'source.zip').write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            self.loader.inspect_release(str(root), manifest_sha256=self.release['code_manifest_sha256'], archive_sha256=a.ARCHIVE_SHA)

    def test_16_both_extracted_layouts(self):
        for prefix, name in (('', 'root'), ('source/', 'source')):
            root = self.root / ('layout-' + name); shutil.copytree(self.candidate / 'code-payload', root)
            (root / 'source.zip').unlink()
            for path in (self.candidate / 'producer-source').rglob('*'):
                if path.is_file():
                    target = root / (prefix + path.relative_to(self.candidate / 'producer-source').as_posix())
                    target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target)
            result = self.loader.inspect_release(str(root), manifest_sha256=self.release['code_manifest_sha256'], archive_sha256=a.ARCHIVE_SHA)
            self.assertIn('verified-extracted', result[-1])

    def owned(self, name, code, deadline):
        stage = self.root / name
        result = self.launch.run_bounded([sys.executable, '-I', '-B', *(['-O'] if sys.flags.optimize else []), '-c', code],
            guard_module=self.guard, directory=stage, deadline_epoch=deadline,
            env={'PATH': os.defpath, 'LANG': 'C.UTF-8'}, scope='entire-owned-preparation-and-runtime',
            failure_context={'source_sha256': a.SOURCE_SHA, 'request_sha256': 'a' * 64, 'original_epoch': 1234567890})
        return stage, result

    def proof(self, name):
        value = a.obj((self.root / name / 'owned-tree/closure.json').read_bytes())
        self.guard.verify_closed_proof(value)
        self.assertTrue(value['closed']); self.assertFalse(value['remaining'])
        return value

    @unittest.skipUnless(sys.platform == 'linux', 'Linux owned supervisor')
    def test_17_owned_nonzero_closure(self):
        with self.assertRaises(RuntimeError): self.owned('nonzero', 'raise SystemExit(7)', time.time() + 40)
        self.assertEqual(self.proof('nonzero')['worker_returncode'], 7)

    @unittest.skipUnless(sys.platform == 'linux', 'Linux owned supervisor')
    def test_18_owned_timeout_cleanup(self):
        deadline = time.time() + 16
        with self.assertRaises(RuntimeError): self.owned('timeout', 'import time; time.sleep(40)', deadline)
        self.assertTrue(self.proof('timeout')['forced'])
        receipt = a.obj((self.root / 'timeout/closure.json').read_bytes())
        self.assertEqual(receipt['deadline_epoch'], deadline)
        self.assertEqual(receipt['reason'], 'original-outer-deadline')

    @unittest.skipUnless(sys.platform == 'linux', 'Linux owned supervisor')
    def test_19_expired_clock_never_dispatches(self):
        with self.assertRaisesRegex(ValueError, 'reserve exhausted'):
            self.owned('expired', 'raise AssertionError()', time.time() - 1)
        self.assertFalse((self.root / 'expired/owned-tree').exists())

    @unittest.skipUnless(sys.platform == 'linux', 'Linux owned supervisor')
    def test_21_postspawn_parent_failure_cleanup(self):
        with patch.object(self.launch.selectors, 'DefaultSelector', side_effect=OSError('synthetic selector failure')):
            with self.assertRaisesRegex(OSError, 'synthetic selector failure'):
                self.owned('parent-failure', 'import time; time.sleep(30)', time.time() + 40)
        self.proof('parent-failure')

    def test_20_numeric_wrapper_rejects_proposal(self):
        mount.MANIFEST_SHA = self.result['publication_manifest_sha256']
        mount.INVENTORY_SHA = self.result['assembly_inventory_sha256']
        with self.assertRaisesRegex(ValueError, 'exact reviewed candidate'):
            mount.candidate_inputs(self.candidate)


if __name__ == '__main__': unittest.main()
