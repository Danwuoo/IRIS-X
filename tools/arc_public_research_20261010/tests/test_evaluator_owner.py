"""Actual isolated synthetic owner closure, incarnation and crash rejection."""
import copy
from pathlib import Path
import tempfile
import time
import unittest

from tools.arc_public_research_20261010 import public_data as data, public_evaluator as ev
from tools.arc_public_research_20261010 import remote_model_owner as remote
from tools.arc_public_research_20261010.tests.test_generation_owner import fixtures, PLAN_HASH
from tools.arc_public_research_20261010.tests.test_evaluator_boundary import bindings


class EvaluatorOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        bootstrap, source = fixtures(self.root)
        self.owner = remote.RemoteModelOwner._synthetic_for_tests(bootstrap,
            environment_plan_sha256=PLAN_HASH, source_identity=source, deadline_monotonic=time.monotonic() + 30)
        self.addCleanup(self.owner.close)
        self.owner.initialize_tokenizer()
        self.binding = bindings()
        self.binding['source_identity'].update(source)
        self.binding['actual_environment_lock_sha256'] = bootstrap['actual_environment_lock_sha256']
        self.request_path = self.owner._request_path
        self.start_path = self.request_path.parent / 'worker-start.json'

    def proof(self, closure):
        return {'mode': 'remote-owner', 'closure': closure,
                'request': {'path': str(self.request_path), 'sha256': data.sha256(self.request_path.read_bytes())},
                'start': {'path': str(self.start_path), 'sha256': data.sha256(self.start_path.read_bytes())},
                'pending_reservations': 0, 'physical_calls': 0}

    def test_graceful_actual_stop_receipt_verified(self):
        proof = self.proof(self.owner.close())
        ev.verify_owner_proof(proof, self.binding)
        self.assertIsNone(ev._process(proof['closure']['process_evidence']['worker_pid']))

    def test_live_process_cannot_use_forged_stopped_boolean(self):
        start = data.parse_json(self.start_path.read_bytes())
        fake = {'model_owner_stopped': True, 'model_released': True, 'owned_descendants_stopped': True,
                'owned_descendants': [], 'environment_plan_sha256': PLAN_HASH,
                'actual_environment_lock_sha256': self.binding['actual_environment_lock_sha256'],
                'process_evidence': {'process_stopped': True, 'worker_pid': start['worker_pid'], 'returncode': 0,
                    'owned_descendants': [], 'observed_process_identities': [start['worker_identity']], 'forced': False,
                    'owned_io_threads_stopped': True, 'scope': 'linux-owned-process-tree'},
                'child_acknowledgement': {'model_owner_stopped': True}}
        with self.assertRaisesRegex(ValueError, 'remains present'):
            ev.verify_owner_proof(self.proof(fake), self.binding)

    def test_crashed_forced_and_foreign_start_rejected(self):
        proof = self.proof(self.owner.close())
        for key, value in (('forced', True), ('returncode', 79), ('owned_io_threads_stopped', False)):
            altered = copy.deepcopy(proof); altered['closure']['process_evidence'][key] = value
            with self.assertRaises(ValueError):
                ev.verify_owner_proof(altered, self.binding)
        start = data.parse_json(self.start_path.read_bytes()); start['nonce'] = 'foreign'
        other = self.root / 'foreign-start.json'; other.write_bytes(data.canonical(start))
        proof['start'] = {'path': str(other), 'sha256': data.sha256(other.read_bytes())}
        with self.assertRaisesRegex(ValueError, 'foreign'):
            ev.verify_owner_proof(proof, self.binding)

    def test_synthetic_owner_cannot_claim_research_gpu(self):
        proof = self.proof(self.owner.close()); self.binding['prediction_origin'] = 'research_gpu'
        with self.assertRaisesRegex(ValueError, 'synthetic process'):
            ev.verify_owner_proof(proof, self.binding)


if __name__ == '__main__':
    unittest.main()
