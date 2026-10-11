"""Synthetic-only oversized owner recovery; no public answer payloads or model."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

from tools.arc_learning_agent_20261011 import evaluation, result_projection as projection
from tools.arc_learning_agent_20261011.budget import DEFAULT_CAPS, SessionClock, atomic_json, canonical, digest
from tools.arc_learning_agent_20261011.export import export_evidence
from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard, verify_closed_proof
from tools.arc_next_offline_environment import _LAUNCHER
from tools.arc_public_research_20261010.public_data import MAX_FILE_BYTES, load_solver_tasks, read_regular
from tools.arc_public_research_20261010.tests.test_public_data import make_assets


def fixture_owner(request, challenges, *, large=False):
    """Declared scripted output, never represented as completed neural training."""
    rows = {}
    for task_id, task in challenges.items():
        evidence = [{'id': 'e00000', 'task_id': task_id, 'kind': 'generation', 'parents': [],
                     'payload': {'synthetic_test_only': True, 'text': 'x' * (230000 if large else 10)}}]
        events = [{'event': 'synthetic-physical-receipt', 'evidence_id': 'e00000',
                   'diagnostic': 'y' * (30000 if large else 10)}]
        rows[task_id] = {'task_id': task_id, 'status': 'complete', 'stop_reasons': [],
            'evidence': evidence, 'physical_usage': {**dict.fromkeys(projection.TASK_COUNTERS, 0),
                'events': events, 'logical_policies_share_physical_work': True},
            'policies': {p: [{'candidates': [[[4]], [[5]]], 'status': 'complete',
                              'evidence_ids': ['e00000']} for _ in task['test']]
                         for p in evaluation.POLICIES}}
    return {'format': 'irisx/learning-owner-result-v1', 'run_id': request['run_id'], 'status': 'complete',
        'source_identity_sha256': digest(request['source_identity']), 'request_sha256': digest(request),
        'solver_manifest_sha256': request['solver_manifest_sha256'], 'prediction_origin': 'synthetic_cpu',
        'production_model': False, 'model_stopped': True, 'results': rows,
        'stages': {'synthetic_test_only': True, 'retained_diagnostic': 'z' * (3 * 1024**2 if large else 10)},
        'stage_clock': [], 'training_steps': 0, 'charged_training_microbatches': 0,
        'physical_usage': {'caps': dict(DEFAULT_CAPS), 'charged': dict.fromkeys(DEFAULT_CAPS, 0),
                           'pending': {}, 'events': 0, 'last_sha256': '0' * 64},
        'pending_work': {}, 'elapsed_seconds': 1.25}


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='owner-projection-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = make_assets(self.root)
        self.challenges = load_solver_tasks(self.assets['solver_root'], self.assets['solver_manifest_sha256'])['challenges']
        self.worker = self.root / 'worker'; self.worker.mkdir()
        self.request = {'format': 'irisx/learning-owner-request-v1', 'run_id': 'synthetic-projection',
            'source_identity': {'synthetic-source.py': '1' * 64},
            'solver_manifest_sha256': self.assets['solver_manifest_sha256'], 'output_root': str(self.worker),
            'config': {'tiny_cpu': True, 'fixture_tasks': 120}}
        self.owner = fixture_owner(self.request, self.challenges)

    def details(self, owner=None):
        owner = self.owner if owner is None else owner
        return {key: canonical(row) for key, row in owner['results'].items()}

    def project(self, owner=None, **kwargs):
        owner = self.owner if owner is None else owner
        args = {'request': self.request, 'challenges': self.challenges, 'task_details': self.details(owner), **kwargs}
        return projection.project_owner_result(canonical(owner), **args)

    def write_details(self, owner=None):
        for key, raw in self.details(owner).items():
            path = self.worker / 'tasks' / key / 'result.json'; path.parent.mkdir(parents=True)
            path.write_bytes(raw)

    def test_exact_projection_retains_every_other_field_and_policy_digest(self):
        before = canonical(self.owner)
        actual = self.project()
        expected = copy.deepcopy(self.owner)
        for row in expected['results'].values(): del row['evidence']
        self.assertEqual(canonical({k: v for k, v in actual.items() if k != 'result_projection'}), canonical(expected))
        self.assertEqual(canonical(self.owner), before)
        meta = actual['result_projection']
        self.assertEqual(meta['policies_sha256'], digest({k: v['policies'] for k, v in self.owner['results'].items()}))
        self.assertEqual(meta['full_owner'], {'path': 'owner-evidence.json', 'bytes': len(before),
                                             'sha256': hashlib.sha256(before).hexdigest()})
        for key, raw in self.details().items():
            self.assertEqual(meta['task_details'][key], {'path': 'tasks/' + key + '/result.json',
                'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        original_pools = evaluation.make_pools(self.challenges, self.owner['results'],
            run_id=self.owner['run_id'], elapsed_seconds=self.owner['elapsed_seconds'])
        compact_pools = evaluation.make_pools(self.challenges, actual['results'],
            run_id=actual['run_id'], elapsed_seconds=actual['elapsed_seconds'])
        self.assertEqual(digest(original_pools), digest(compact_pools))
        self.assertTrue(projection.verify_owner_projection(actual, full_raw=before, request=self.request,
            challenges=self.challenges, task_details=self.details()))

    def test_raw_and_task_noncanonical_bytes_are_bound_exactly(self):
        raw = json.dumps(self.owner, indent=1).encode()
        details = {key: value + b' ' for key, value in self.details().items()}
        actual = projection.project_owner_result(raw, request=self.request, challenges=self.challenges, task_details=details)
        self.assertEqual(actual['result_projection']['full_owner']['sha256'], hashlib.sha256(raw).hexdigest())
        for kwargs in ({'full_raw': raw + b' '}, {'task_details': self.details()}):
            args = {'full_raw': raw, 'request': self.request, 'challenges': self.challenges, 'task_details': details, **kwargs}
            with self.assertRaisesRegex(ValueError, 'binding differs'):
                projection.verify_owner_projection(actual, **args)

    def test_projection_metadata_and_preserved_predictions_cannot_be_tampered(self):
        projected = self.project(); key = next(iter(self.owner['results']))
        mutations = [
            lambda p: p['result_projection']['full_owner'].update(sha256='0' * 64),
            lambda p: p['result_projection']['full_owner'].update(bytes=1),
            lambda p: p['result_projection']['full_owner'].update(path='../foreign'),
            lambda p: p['result_projection']['task_details'][key].update(sha256='0' * 64),
            lambda p: p['result_projection']['task_details'][key].update(bytes=1),
            lambda p: p['result_projection']['task_details'][key].update(path='foreign'),
            lambda p: p['result_projection'].update(policies_sha256='0' * 64),
            lambda p: p['result_projection'].update(omitted_task_fields=['evidence', 'physical_usage']),
            lambda p: p['results'][key]['policies']['full_agent'][0].update(candidates=[[[7]], [[8]]]),
            lambda p: p['results'][key]['physical_usage'].update(events=[]),
            lambda p: p.update(training_steps=1),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(projected); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaisesRegex(ValueError, 'binding differs'):
                projection.verify_owner_projection(changed, full_raw=canonical(self.owner), request=self.request,
                    challenges=self.challenges, task_details=self.details())

    def test_missing_extra_inconsistent_task_detail_and_duplicate_json_fail(self):
        details = self.details(); key = next(iter(details))
        for changed in ({k: v for k, v in details.items() if k != key},
                        {**details, 'foreign': b'{}'}, {**details, key: b'{}'},
                        {**details, key: b'{"task_id":"x","task_id":"x"}'}):
            with self.subTest(keys=len(changed)), self.assertRaises(ValueError): self.project(task_details=changed)
        with self.assertRaises(ValueError):
            projection.project_owner_result(b'{"format":0,"format":0}', request=self.request,
                                            challenges=self.challenges, task_details={})

    def test_owner_bindings_status_pending_attribution_and_cost_fail_closed(self):
        for key, value in [('source_identity_sha256', '0' * 64), ('request_sha256', '0' * 64),
            ('run_id', 'foreign'), ('solver_manifest_sha256', '0' * 64), ('status', 'running'),
            ('model_stopped', False), ('pending_work', {'unknown': {}}), ('pending_work', None),
            ('pending_work', []), ('prediction_origin', 'trained_model_research'), ('production_model', True),
            ('training_steps', True), ('training_steps', 1), ('charged_training_microbatches', 1),
            ('elapsed_seconds', -1)]:
            with self.subTest(key=key, value=value):
                owner = copy.deepcopy(self.owner); owner[key] = value
                with self.assertRaises(ValueError): self.project(owner)
        owner = copy.deepcopy(self.owner); owner['physical_usage']['pending'] = {'unknown': {}}
        with self.assertRaises(ValueError): self.project(owner)
        owner = copy.deepcopy(self.owner); owner['physical_usage']['caps']['gas'] += 1
        with self.assertRaises(ValueError): self.project(owner)

    def test_exact_task_policy_cardinality_and_candidate_grid_shapes(self):
        key = next(iter(self.owner['results']))
        mutations = [lambda r: r['results'].pop(key),
            lambda r: r['results'].update({'../escape': r['results'][key]}),
            lambda r: r['results'][key].update(task_id='foreign'),
            lambda r: r['results'][key].update(status='reset_failed'),
            lambda r: r['results'][key]['policies'].pop('task_ttt'),
            lambda r: r['results'][key]['policies'].update(extra=[]),
            lambda r: r['results'][key]['policies']['full_agent'].pop(),
            lambda r: r['results'][key]['policies']['full_agent'][0].update(status='missing')]
        for mutate in mutations:
            owner = copy.deepcopy(self.owner); mutate(owner)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): self.project(owner)
        for invalid in ([], [[True]], [[10]], [[-1]], [[1.0]], [[1], [1, 2]], [[1] * 31], [[1]] * 31):
            owner = copy.deepcopy(self.owner)
            owner['results'][key]['policies']['full_agent'][0]['candidates'][0] = invalid
            with self.subTest(grid=invalid), self.assertRaises(ValueError): self.project(owner)
        for candidates in ([[[1]], [[1]]], [[[1]], [[2]], [[3]]]):
            owner = copy.deepcopy(self.owner)
            owner['results'][key]['policies']['full_agent'][0]['candidates'] = candidates
            with self.assertRaises(ValueError): self.project(owner)
        challenges = copy.deepcopy(self.challenges); challenges.pop(key)
        with self.assertRaises(ValueError): self.project(challenges=challenges)

    def test_partial_keeps_missing_tasks_in_frozen_denominator(self):
        owner = copy.deepcopy(self.owner); owner['status'] = 'partial'; owner['results'].pop(next(iter(owner['results'])))
        actual = self.project(owner)
        pools = evaluation.make_pools(self.challenges, actual['results'], run_id=actual['run_id'], elapsed_seconds=1)
        for pool in pools.values():
            self.assertEqual(len(pool['records']), 120)
            self.assertEqual(sum(len(row['tests']) for row in pool['records']), 167)

    def test_hard_raw_detail_and_projection_byte_limits(self):
        with self.assertRaisesRegex(ValueError, 'bounded full owner'):
            projection.project_owner_result(b' ' * (projection.FULL_OWNER_MAX_BYTES + 1),
                request=self.request, challenges=self.challenges, task_details={})
        details = self.details(); details[next(iter(details))] = b' ' * (MAX_FILE_BYTES + 1)
        with self.assertRaisesRegex(ValueError, 'bounded task detail'): self.project(task_details=details)
        owner = copy.deepcopy(self.owner); owner['stages']['oversize'] = 'x' * MAX_FILE_BYTES
        with self.assertRaisesRegex(ValueError, 'projected owner exceeds16MiB'): self.project(owner)

    def test_fresh_writer_retains_full_diagnostics_and_detects_file_tampering(self):
        self.write_details()
        actual = projection.write_owner_result(self.owner, request=self.request, challenges=self.challenges)
        raw = (self.worker / 'owner-evidence.json').read_bytes()
        self.assertEqual(raw, canonical(self.owner))
        self.assertEqual((self.worker / 'owner-evidence.json').stat().st_mode & 0o222, 0)
        self.assertEqual(projection.verify_written_owner_result(self.worker, request=self.request,
                                                              challenges=self.challenges), actual)
        with self.assertRaises(ValueError):
            projection.write_owner_result(self.owner, request=self.request, challenges=self.challenges)
        key = next(iter(self.owner['results'])); detail = self.worker / 'tasks' / key / 'result.json'
        for path in (detail, self.worker / 'owner-evidence.json', self.worker / 'result.json'):
            before = path.read_bytes(); path.chmod(0o644)
            path.write_bytes(before + b' ')
            # Compact whitespace is not itself part of this helper's hash; live
            # closure/seal hashes it. Full/raw task whitespace is explicitly bound.
            if path.name != 'result.json' or path == detail:
                with self.assertRaises(ValueError):
                    projection.verify_written_owner_result(self.worker, request=self.request, challenges=self.challenges)
            path.write_bytes(before)
        detail.unlink()
        with self.assertRaises(ValueError):
            projection.verify_written_owner_result(self.worker, request=self.request, challenges=self.challenges)
        detail.symlink_to(self.worker / 'owner-evidence.json')
        with self.assertRaises(ValueError):
            projection.verify_written_owner_result(self.worker, request=self.request, challenges=self.challenges)

    def test_missing_raw_evidence_blocks_written_verification(self):
        self.write_details()
        projection.write_owner_result(self.owner, request=self.request, challenges=self.challenges)
        (self.worker / 'owner-evidence.json').unlink()
        with self.assertRaises(ValueError):
            projection.verify_written_owner_result(self.worker, request=self.request, challenges=self.challenges)

    def test_oversized_projection_writer_fails_without_discarding_diagnostics(self):
        self.owner['stages']['oversize'] = 'x' * MAX_FILE_BYTES
        self.write_details()
        with self.assertRaisesRegex(ValueError, 'projected owner exceeds16MiB'):
            projection.write_owner_result(self.owner, request=self.request, challenges=self.challenges)
        self.assertEqual((self.worker / 'owner-evidence.json').read_bytes(), canonical(self.owner))
        self.assertFalse((self.worker / 'result.json').exists())

    def test_failed_write_retains_raw_diagnostics_without_sealable_result(self):
        with self.assertRaises(ValueError):
            projection.write_owner_result(self.owner, request=self.request, challenges=self.challenges)
        self.assertEqual((self.worker / 'owner-evidence.json').read_bytes(), canonical(self.owner))
        self.assertFalse((self.worker / 'result.json').exists())


_SYNTHETIC_OWNER = '''
import json
from pathlib import Path
import socket
import sys
sys.path[:0] = [REPOSITORY, REPOSITORY + '/src']
from tools.arc_learning_agent_20261011.tests.test_result_projection import fixture_owner
from tools.arc_learning_agent_20261011.result_projection import write_owner_result
from tools.arc_learning_agent_20261011.budget import atomic_json
from tools.arc_public_research_20261010.public_data import read_regular, load_solver_tasks
assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
assert getattr(socket, '_irisx_offline_guard', False)
try:
    socket.socket(socket.AF_INET)
except RuntimeError:
    pass
else:
    raise AssertionError('network guard missing')
request = json.loads(read_regular(sys.argv[1], sys.argv[2]))
challenges = load_solver_tasks(request['solver_root'], request['solver_manifest_sha256'])['challenges']
owner = fixture_owner(request, challenges, large=True)
for task_id, row in owner['results'].items():
    atomic_json(Path(request['output_root']) / 'tasks' / task_id / 'result.json', row, exclusive=True)
write_owner_result(owner, request=request, challenges=challenges)
'''


@unittest.skipUnless(sys.platform == 'linux', 'Linux owned process proof required')
class OversizedLauncherIntegrationTests(unittest.TestCase):
    def test_oversized_real_launcher_owner_seal_fresh_evaluator_and_archive(self):
        with tempfile.TemporaryDirectory(prefix='oversized-owner-') as tmp:
            root = Path(tmp); assets = make_assets(root)
            output = root / 'output'; output.mkdir(); worker = output / 'worker'; worker.mkdir()
            source = evaluation.source_identity()
            clock = SessionClock.create(output / 'session-clock.json', 'synthetic-oversized',
                started_epoch=time.time() - 2400, origin='pre-dispatch')
            clock_bytes = (output / 'session-clock.json').read_bytes()
            request = {'format': 'irisx/learning-owner-request-v1', 'run_id': 'synthetic-oversized',
                'source_identity': source, 'solver_root': assets['solver_root'],
                'solver_manifest_sha256': assets['solver_manifest_sha256'], 'output_root': str(worker),
                'config': {'tiny_cpu': True, 'fixture_tasks': 120}, 'clock': clock.record}
            atomic_json(worker / 'request.json', request, exclusive=True)
            launcher = root / 'offline-run.py'; launcher.write_bytes(_LAUNCHER.encode())
            script = root / 'synthetic-owner.py'
            script.write_text(_SYNTHETIC_OWNER.replace('REPOSITORY', repr(str(evaluation.ROOT))))
            with (worker / 'stderr.txt').open('wb') as err:
                guard = OwnedProcessGuard.spawn([sys.executable, '-I', '-B', '-S', str(launcher), str(script),
                    str(worker / 'request.json'), digest(request)], evidence_dir=worker / 'process-guard',
                    cwd=worker, stdout=subprocess.DEVNULL, stderr=err,
                    env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'PYTHONDONTWRITEBYTECODE': '1',
                         'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'})
                self.addCleanup(lambda: guard.stop(timeout=5) if guard.poll() is None else None)
                until = time.monotonic() + 90
                while guard.poll() is None and time.monotonic() < until: time.sleep(0.05)
                if guard.poll() is None: guard.stop(timeout=5)
            self.assertEqual(guard.child.returncode, 0, (worker / 'stderr.txt').read_text())
            proof = guard.closed_proof(); self.assertTrue(verify_closed_proof(proof))
            self.assertFalse(proof['forced']); self.assertEqual(proof['worker_returncode'], 0)
            full_path, result_path = worker / 'owner-evidence.json', worker / 'result.json'
            self.assertGreater(full_path.stat().st_size, MAX_FILE_BYTES)
            self.assertLess(result_path.stat().st_size, MAX_FILE_BYTES)
            with self.assertRaisesRegex(ValueError, 'bounded regular file'): read_regular(full_path)
            compact = json.loads(read_regular(result_path)); original = json.loads(full_path.read_bytes())
            challenges = load_solver_tasks(assets['solver_root'], assets['solver_manifest_sha256'])['challenges']
            self.assertEqual(projection.verify_written_owner_result(worker, request=request, challenges=challenges), compact)
            closure = {'format': 'irisx/learning-owner-closure-v1', 'worker_identity': guard.identity,
                'returncode': guard.child.returncode, 'graceful': True, 'source_identity_sha256': digest(source),
                'request_sha256': digest(request), 'result_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest(),
                'session_members': [], 'parent_identity': evaluation.process_identity(os.getpid()),
                'process_tree_proof': proof}
            atomic_json(output / 'owner-closure.json', closure, exclusive=True)
            seal = evaluation.seal_predictions(output / 'predictions', solver_root=assets['solver_root'],
                solver_manifest_sha256=assets['solver_manifest_sha256'], evaluator_manifest_sha256=assets['evaluator_manifest_sha256'],
                result_path=result_path, closure=closure, bindings={'run_id': request['run_id'], 'prediction_origin': 'synthetic_cpu'})
            expected = evaluation.make_pools(challenges, original['results'], run_id=request['run_id'], elapsed_seconds=original['elapsed_seconds'])
            for name, pool in expected.items():
                self.assertEqual((output / 'predictions' / (name + '.json')).read_bytes(), canonical(pool))
            evaluated = evaluation.evaluate_sealed(output / 'predictions', seal['sha256'],
                solver_root=assets['solver_root'], evaluator_root=assets['evaluator_root'],
                output_root=output / 'evaluation', deadline=time.monotonic() + 60)
            self.assertEqual(evaluated['status'], 'SCORED', (output / 'evaluation' / 'stderr.txt').read_text())
            self.assertEqual((evaluated['tasks'], evaluated['tests']), (120, 167))
            self.assertEqual(evaluated['prediction_origin'], 'synthetic_cpu')
            self.assertFalse(evaluated['training_used'])
            exported = export_evidence(output, run_id=request['run_id'], deadline=time.monotonic() + 60)
            with zipfile.ZipFile(exported['archive']['path']) as archive:
                self.assertEqual(archive.read('worker/owner-evidence.json'), full_path.read_bytes())
                self.assertEqual(archive.read('worker/result.json'), result_path.read_bytes())
                for key in original['results']:
                    name = 'worker/tasks/' + key + '/result.json'
                    self.assertEqual(archive.read(name), (output / name).read_bytes())
            self.assertEqual((output / 'session-clock.json').read_bytes(), clock_bytes)
            self.assertEqual(clock.record['deadline_epoch'], clock.record['started_epoch'] + 43200)
            # A changed compact result is rejected by the unchanged live closure.
            result_path.write_bytes(result_path.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'source/result binding'):
                evaluation.seal_predictions(output / 'tampered-predictions', solver_root=assets['solver_root'],
                    solver_manifest_sha256=assets['solver_manifest_sha256'], evaluator_manifest_sha256=assets['evaluator_manifest_sha256'],
                    result_path=result_path, closure=closure, bindings={'run_id': request['run_id'], 'prediction_origin': 'synthetic_cpu'})


if __name__ == '__main__': unittest.main()
