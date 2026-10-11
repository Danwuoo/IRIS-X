"""Synthetic archived recovery; no benchmark gold/model execution or provider calls."""
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
from unittest import mock

from tools.arc_learning_agent_20261011 import archived_recovery as recovery
from tools.arc_learning_agent_20261011.budget import WorkLedger, canonical, digest
from tools.arc_learning_agent_20261011.result_projection import TASK_COUNTERS
from tools.arc_public_research_20261010.public_data import load_solver_tasks
from tools.arc_public_research_20261010.tests.test_public_data import make_assets
from tools.arc_next_offline_environment import _LAUNCHER


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if type(value) is bytes else canonical(value))
    return recovery.descriptor(path, recovery.RAW_CAP)


def ident(pid, session=None):
    return {'pid': pid, 'birth': 100 + pid, 'session': pid if session is None else session, 'state': 'R'}


def proof(root, child, code=0, *, supervisor=False, parent=None):
    value = {'format': 'irisx/owned-supervisor-result-v1' if supervisor else 'irisx/owned-process-closure-v1',
             'scope': 'dedicated-subreaper-tree', 'closed': True, 'ownership_complete': True,
             'remaining': [], 'errors': [], 'forced': False, 'returncode': code,
             'worker_returncode': code, 'root_identity': root,
             'owned_identities': [root] if root == child else [root, child], 'reaped_identities': []}
    if supervisor: value['supervisor_identity'] = parent
    return value


def fixture(root, *, large=False):
    root = Path(root)
    assets = make_assets(root)
    challenges = load_solver_tasks(assets['solver_root'], assets['solver_manifest_sha256'])['challenges']
    source = dict(recovery.SCORER_PINS)
    controller = 'tools/arc_learning_agent_20261011/controller.py'
    source[controller] = recovery.descriptor(recovery.ROOT / controller)['sha256']
    now = int(time.time())
    original = {**recovery.V4, 'reference': 'synthetic/test-only', 'kernel_id': 1,
                'started_epoch': now - 10, 'deadline_epoch': now - 10 + 43200,
                'source_identity_sha256': digest(source)}
    run_root = 'synthetic-original'
    evidence = root / 'evidence'; files = {}
    def save(name, value):
        files[name] = write(evidence / name, value)
    def inner(name, value): save(run_root + '/' + name, value)
    run_id = 'learning-' + '1' * 32
    clock = {'format': 'irisx/learning-clock-v1', 'session_id': run_id, 'origin': 'pre-dispatch',
             'started_epoch': original['started_epoch'], 'deadline_epoch': original['deadline_epoch'],
             'maximum_seconds': 43200}
    request = {'format': 'irisx/learning-owner-request-v1', 'run_id': run_id, 'source_identity': source,
               'solver_manifest_sha256': assets['solver_manifest_sha256'], 'clock': clock,
               'config': {'tiny_cpu': True, 'validation_mode': True, 'fixture_tasks': 120, 'seed': 0}}
    inner('worker/request.json', request)
    ledger_path = evidence / run_root / 'worker/physical-work.jsonl'
    ledger = WorkLedger(ledger_path)
    for name, amounts in [('sft', {'training_steps': 1, 'input_tokens': 2}), ('gen', {'generation_calls': 1})]:
        ledger.reserve(name, amounts); ledger.complete(name, amounts)
    files[run_root + '/worker/physical-work.jsonl'] = recovery.descriptor(ledger_path)
    rows = {}
    for key, challenge in challenges.items():
        # Rich repeated object structure, rather than one giant padding string.
        evidence_rows = [{'id': f'e{i:05}', 'kind': 'generation', 'parents': [],
            'payload': {'text': 'x' * 430, 'tokens': 3, 'valid': True, 'shape': [1, 1]}}
            for i in range(540 if large else 1)]
        rows[key] = {'task_id': key, 'status': 'complete', 'stop_reasons': [], 'evidence': evidence_rows,
             'physical_usage': {**dict.fromkeys(TASK_COUNTERS, 0), 'events': [],
                                'logical_policies_share_physical_work': True},
             'policies': {p: [{'candidates': [[[4]], [[5]]], 'status': 'complete', 'evidence_ids': ['e00000']}
                              for _ in challenge['test']] for p in recovery.POLICIES}}
    # Preserve empty/missing candidates within the complete denominator.
    rows['00000000']['policies']['global_grid'][0] = {'candidates': [], 'status': 'missing', 'evidence_ids': []}
    stage = {'steps': 1, 'optimizer_steps': 1, 'optimizer_state_consistent': True, 'usage_known': True,
             'status': 'complete', 'attempted_microbatches': 1, 'adapter_before_sha256': '1' * 64,
             'adapter_after_sha256': '2' * 64, 'input_tokens': 2, 'physical_event_id': 'sft', 'tiny_cpu': True,
             'updates': [{'finite_gradients': True, 'changed_adapter_tensors': 1, 'adam_step': 1,
                          'gradient_norm': 1.0, 'elapsed_seconds': 0.1, 'loss': 1.0,
                          'adapter_before_sha256': '1' * 64, 'adapter_after_sha256': '2' * 64}]}
    result = {'format': 'irisx/learning-owner-result-v1', 'run_id': run_id, 'status': 'complete',
              'source_identity_sha256': digest(source), 'request_sha256': digest(request),
              'solver_manifest_sha256': assets['solver_manifest_sha256'], 'prediction_origin': 'synthetic_cpu',
              'production_model': False, 'model_stopped': True, 'pending_work': {}, 'training_steps': 1,
              'charged_training_microbatches': 1, 'physical_usage': ledger.summary(), 'elapsed_seconds': 1.0,
              'results': rows, 'stages': {'global_sft': stage, 'model_load': {'identity': {'execution_mode': 'tiny_cpu'}}},
              'stage_clock': [{'stage': key, 'maximum_seconds': cap, 'status': 'complete', 'within_cap': True,
                               'started_epoch': now - 9 + i, 'elapsed_seconds': 0.1}
                              for i, (key, cap) in enumerate(recovery.historical.STAGE_CAPS.items())]}
    inner('worker/result.json', result)
    original['raw_result_sha256'] = files[run_root + '/worker/result.json']['sha256']
    outer_root, coordinator, owner_root, worker_id = ident(10), ident(11, 10), ident(20), ident(21, 20)
    owner_proof = proof(owner_root, worker_id)
    owner = {'format': 'irisx/learning-owner-closure-v1', 'worker_identity': owner_root,
             'parent_identity': coordinator, 'returncode': 0, 'graceful': True, 'session_members': [],
             'source_identity_sha256': digest(source), 'result_sha256': original['raw_result_sha256'],
             'request_sha256': digest(request), 'process_tree_proof': owner_proof}
    inner('owner-closure.json', owner)
    inner('owner-start.json', {'worker_identity': owner_root, 'parent_identity': coordinator, 'request_sha256': digest(request)})
    def guard(prefix, root_id, child_id, parent, code, request_sha):
        save(prefix + 'closure.json', proof(root_id, child_id, code))
        save(prefix + 'launch.json', {'format': 'irisx/owned-process-launch-v1', 'scope': 'dedicated-subreaper-tree',
                  'supervisor_identity': root_id, 'coordinator_identity': parent, 'worker_argv': ['synthetic', request_sha]})
        save(prefix + 'worker-launch.json', {'format': 'irisx/owned-worker-launch-v1', 'parent_death_signal': 9,
                  'supervisor_identity': root_id, 'worker_identity': child_id})
        save(prefix + 'supervisor-result.json', proof(child_id, child_id, code, supervisor=True, parent=root_id))
    guard(run_root + '/worker/process-guard/', owner_root, worker_id, coordinator, 0, digest(request))
    inner('session-clock.json', clock)
    inner('admission.json', {'run_id': run_id, 'source_identity': source, 'enable_model': True, 'clock': clock,
                            **{k: assets[k] for k in ('solver_manifest_sha256', 'evaluator_manifest_sha256')}})
    loader, guard_source, suffix = '# synthetic loader\n', '# synthetic guard\n', '# synthetic suffix\n'
    constants = {'MANUAL_START': True, 'ENABLE_MODEL': True, 'PROFILE': 'LEARNING_AGENT12H',
                 'OUTPUT_ROOT': run_root, 'SOURCE_PARENT': '/synthetic/source', 'INPUT_ROOT': '/synthetic/input',
                 'CODE_ROOT': '/synthetic/code', 'DATA_ROOT': '/synthetic/data', 'TRAINING_ROOT': '/synthetic/training',
                 'MODEL_CONFIG': {'synthetic': True}, 'SEED': 0, 'SESSION_SECONDS': 43200,
                 'PREDISPATCH_EPOCH': original['started_epoch'], 'LOADER_SOURCE': loader, 'GUARD_SOURCE': guard_source,
                 'LOADER_SHA256': recovery.historical.sha(loader.encode()),
                 'GUARD_SHA256': recovery.historical.sha(guard_source.encode()),
                 'LEARNING_PINS': {'data': {'role_manifests': {'solver': assets['solver_manifest_sha256'],
                                                           'evaluator': assets['evaluator_manifest_sha256']}}}}
    notebook = {'cells': [{'cell_type': 'code', 'source': '\n'.join(f'{k} = {v!r}' for k, v in constants.items()) +
                           '\ndriver = loader_source + ' + repr(suffix)}]}
    notebook_desc = write(root / 'notebook.ipynb', notebook)
    original['source_sha256'] = notebook_desc['sha256']
    prefix = run_root + '-launcher/'
    outer_request = {'started_epoch': original['started_epoch'], 'hard_deadline_epoch': original['deadline_epoch'],
                     'loader_sha256': constants['LOADER_SHA256'], 'guard_sha256': constants['GUARD_SHA256'],
                     'driver_sha256': recovery.historical.sha((loader + suffix).encode()),
                     'launcher_root': '/synthetic/' + run_root + '-launcher', 'pins': constants['LEARNING_PINS'],
                     'config': {k.lower(): constants[k] for k in ('MANUAL_START', 'ENABLE_MODEL', 'PROFILE',
                         'OUTPUT_ROOT', 'SOURCE_PARENT', 'INPUT_ROOT', 'CODE_ROOT', 'DATA_ROOT', 'TRAINING_ROOT',
                         'MODEL_CONFIG', 'SEED')}}
    outer_request['config'].update(session_seconds=43200, predispatch_epoch=original['started_epoch'])
    save(prefix + 'request.json', outer_request)
    save(prefix + 'bootstrap.py', (loader + suffix).encode())
    save(prefix + 'owned_process_guard.py', guard_source.encode())
    save(prefix + 'launcher-closure.json', {'format': 'irisx/learning-notebook-closure-v1', 'forced': False,
         'reason': None, 'within_absolute_deadline': True, 'started_epoch': original['started_epoch'],
         'hard_deadline_epoch': original['deadline_epoch'], 'completed_epoch': now,
         'process_tree_proof': proof(outer_root, coordinator, 1)})
    guard(prefix + 'owned-tree/', outer_root, coordinator, ident(9), 1, digest(outer_request))
    receipt = {**{k: original[k] for k in ('reference', 'kernel_id', 'version', 'source_sha256', 'provider_status')},
               'files': [{'provider_path': k, 'numeric_version': 4, **{x: v[x] for x in ('bytes', 'sha256')}}
                         for k, v in files.items()]}
    receipt_desc = write(root / 'retrieval.json', receipt)
    contract = {'format': recovery.FORMAT, 'recovery_id': 'synthetic-recovery', 'mode': 'synthetic-test-only',
                'original': original, 'source_root': str(recovery.ROOT), 'source_identity': source,
                'recovery_source_identity': recovery.source_identity(), 'output_root': run_root,
                'files': files, 'retrieval_receipts': [receipt_desc], 'notebook': notebook_desc,
                **{k: assets[k] for k in ('solver_root', 'evaluator_root', 'solver_manifest_sha256', 'evaluator_manifest_sha256')}}
    contract_path = root / 'contract.json'; write(contract_path, contract)
    return contract_path, contract, assets


class ArchivedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='archived-recovery-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path, self.contract, self.assets = fixture(self.root)

    def save_contract(self):
        return write(self.path, self.contract)['sha256']

    def prepare(self):
        return recovery.prepare_recovery(self.path, self.save_contract(), self.root / 'sealed')

    def test_truth_free_seal_and_isolated_synthetic_score(self):
        expected = {name: row['sha256'] for name, row in self.contract['files'].items()}
        seal = self.prepare()
        report = recovery.evaluate_recovery(self.root / 'sealed', seal['sha256'], self.root / 'score')
        self.assertEqual((report['tasks'], report['tests']), (120, 167))
        self.assertEqual(report['status'], 'SCORED')
        self.assertEqual(report['original_provider_status'], 'ERROR')
        self.assertFalse(report['competition_gpu_equivalent'])
        self.assertFalse(report['new_gpu_execution'])
        pool = json.loads((self.root / 'sealed/global_grid.json').read_bytes())
        self.assertEqual(pool['records'][0]['tests'][0]['ranked_grids'], [])
        self.assertEqual(len(pool['records']), 120)
        for name, row in self.contract['files'].items():
            self.assertEqual(recovery.descriptor(row['path'], recovery.RAW_CAP)['sha256'], expected[name])
        with self.assertRaisesRegex(ValueError, 'consumed'): self.prepare()

    def test_proof_only_with_evaluator_missing_and_no_live_pid_checks(self):
        self.contract['evaluator_root'] = str(self.root / 'nonexistent-evaluator')
        with mock.patch('tools.arc_learning_agent_20261011.evaluation.verify_closed', side_effect=AssertionError('live protocol forbidden')):
            seal = self.prepare()
        report = recovery.evaluate_recovery(self.root / 'sealed', seal['sha256'], self.root / 'proof', proof_only=True)
        self.assertFalse(report['public_answers_opened'])
        self.assertFalse((self.root / 'proof/public-summary.json').exists())

    def test_changed_raw_request_closure_source_ledger_and_receipt_rejected(self):
        names = ('worker/result.json', 'worker/request.json', 'owner-closure.json', 'worker/physical-work.jsonl')
        for name in names:
            row = self.contract['files'][self.contract['output_root'] + '/' + name]
            path = Path(row['path']); before = path.read_bytes(); path.write_bytes(before + b' ')
            try:
                with self.subTest(name=name), self.assertRaises(ValueError): self.prepare()
            finally: path.write_bytes(before)
        self.contract['source_identity'][next(iter(self.contract['source_identity']))] = '0' * 64
        with self.assertRaises(ValueError): self.prepare()

    def test_foreign_numeric_version_and_live_claims_rejected(self):
        for key, value in [('version', 5), ('provider_status', 'COMPLETE'), ('deadline_epoch', time.time() - 1)]:
            old = self.contract['original'][key]; self.contract['original'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.prepare()
            self.contract['original'][key] = old
        self.contract['claims_live_owner_closed'] = True
        with self.assertRaisesRegex(ValueError, 'schema'): self.prepare()

    def test_pool_order_grid_and_projection_changes_rejected_before_gold(self):
        seal = self.prepare()
        for name in ('full_agent.json', 'solver-result.json'):
            path = self.root / 'sealed' / name; raw = path.read_bytes(); value = json.loads(raw)
            if name == 'full_agent.json': value['records'].reverse()
            else: value['results']['00000000']['policies']['full_agent'][0]['candidates'].reverse()
            path.write_bytes(canonical(value))
            with self.subTest(name=name), self.assertRaises(ValueError):
                recovery.evaluate_recovery(self.root / 'sealed', seal['sha256'], self.root / 'blocked')
            self.assertFalse((self.root / 'blocked').exists())
            path.write_bytes(raw)

    def test_path_symlink_and_oversized_regular_files_rejected(self):
        target = self.root / 'plain'; target.write_bytes(b'x')
        link = self.root / 'linked'; link.symlink_to(target)
        with self.assertRaises(ValueError): recovery.descriptor(link)
        with self.assertRaises(ValueError): recovery.clean_path(str(self.root / '..' / 'escape'))
        giant = self.root / 'giant'
        with giant.open('wb') as handle: handle.truncate(recovery.RAW_CAP + 1)
        with self.assertRaises(ValueError): recovery.descriptor(giant, recovery.RAW_CAP)
        with self.assertRaises(ValueError): recovery.parse(b'{"x":1,"x":2}')
        with self.assertRaises(ValueError): recovery.parse(b'{"x":1e999}')
        self.contract['evaluator_root'] = str(link)
        with self.assertRaises(ValueError): self.prepare()

    def test_recorded_outer_failure_does_not_accept_success_forced_or_remaining(self):
        base = proof(ident(10), ident(11, 10), 1)
        self.assertEqual(recovery.failed_outer_proof(base), (10, 110, 10))
        for changes in ({'returncode': 0}, {'worker_returncode': 0}, {'forced': True},
                        {'ownership_complete': False}, {'remaining': [ident(12)]}, {'errors': ['unknown']}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                recovery.failed_outer_proof({**base, **changes})

    def test_pending_malformed_missing_task_and_changed_accounting_fail_even_rebound(self):
        c, e, constants, suffix = recovery.validate_contract(self.path, self.save_contract())
        raw = e.raw('worker/result.json'); result = json.loads(raw)
        mutations = [lambda r: r.update(pending_work={'unknown': 1}),
                     lambda r: r.update(model_stopped=False),
                     lambda r: r['physical_usage']['charged'].update(generation_calls=2),
                     lambda r: r['results'].pop('00000000'),
                     lambda r: r['results']['00000000']['physical_usage'].update(unknown_usage_events=1)]
        for mutate in mutations:
            bad = copy.deepcopy(result); mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                recovery.verify_history(c, e, constants, suffix, bad)


class ForwardProjectionAdapterTests(unittest.TestCase):
    def test_new_exact_source_identity_and_full_detail_validation(self):
        from tools.arc_learning_agent_20261011.deployment import validate_learning_outputs_projection as adapter
        from tools.arc_learning_agent_20261011.result_projection import project_owner_result
        from tools.arc_learning_agent_20261011.tests.test_result_projection import fixture_owner
        with tempfile.TemporaryDirectory(prefix='forward-adapter-') as directory:
            root = Path(directory); assets = make_assets(root)
            challenges = load_solver_tasks(assets['solver_root'], assets['solver_manifest_sha256'])['challenges']
            source = recovery.source_identity()
            request = {'format': 'irisx/learning-owner-request-v1', 'run_id': 'forward-adapter-test',
                       'source_identity': source, 'solver_manifest_sha256': assets['solver_manifest_sha256'],
                       'config': {'tiny_cpu': True, 'fixture_tasks': 120}}
            full = fixture_owner(request, challenges)
            raw = canonical(full); details = recovery.derived_details(full)
            projected = project_owner_result(raw, request=request, challenges=challenges, task_details=details)
            class View:
                def raw(self, name):
                    if name == 'worker/owner-evidence.json': return raw
                    return details[name.split('/')[2]]
                def json(self, name):
                    return request
            view = View()
            adapter.verify_compact_projection(view, projected, source, digest(source),
                                              assets['solver_root'], digest(source))
            with self.assertRaises(ValueError):
                adapter.verify_compact_projection(view, projected, source, digest(source),
                                                  assets['solver_root'], '0' * 64)
            for mutate in (lambda p: p.update(training_steps=1),
                           lambda p: p['results']['00000000']['physical_usage'].update(generation_calls=9),
                           lambda p: p['results']['00000000']['policies']['full_agent'][0]['candidates'].reverse(),
                           lambda p: p['results']['00000000']['policies']['full_agent'][0].update(candidates=[[[True]]])):
                changed = copy.deepcopy(projected); mutate(changed)
                with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                    adapter.verify_compact_projection(view, changed, source, digest(source),
                                                      assets['solver_root'], digest(source))
            old_raw = view.raw
            too_large = b' ' * (64 * recovery.MIB + 1)
            with mock.patch.object(view, 'raw', side_effect=lambda name: too_large if name == 'worker/owner-evidence.json' else old_raw(name)):
                with self.assertRaisesRegex(ValueError, 'full_owner_recovery_cap'):
                    adapter.verify_compact_projection(view, projected, source, digest(source),
                                                      assets['solver_root'], digest(source))
            del too_large
            key = next(iter(details)); old_detail = details[key]
            details[key] = b' ' * (16 * recovery.MIB + 1)
            with self.assertRaisesRegex(ValueError, 'bounded task detail'):
                adapter.verify_compact_projection(view, projected, source, digest(source),
                                                  assets['solver_root'], digest(source))
            details[key] = old_detail + b' '
            with self.assertRaises(ValueError):
                adapter.verify_compact_projection(view, projected, source, digest(source),
                                                  assets['solver_root'], digest(source))


class LargeOfflineRecoveryTests(unittest.TestCase):
    def test_rich_34mb_fixture_through_pinned_offline_launcher_and_limited_child(self):
        with tempfile.TemporaryDirectory(prefix='archived-large-') as directory:
            root = Path(directory)
            launcher = root / 'offline-run.py'; launcher.write_text(_LAUNCHER, encoding='utf-8')
            self.assertEqual(hashlib.sha256(launcher.read_bytes()).hexdigest(),
                             'cb171117dd3d59458b741f1732d8085b75a9bc277ab29c9f480fe372fb8817f4')
            driver = root / 'driver.py'
            driver.write_text('import sys\nfrom pathlib import Path\n' +
                f'sys.path[:0] = [{str(recovery.ROOT)!r}, {str(recovery.ROOT / "src")!r}]\n' +
                'from tools.arc_learning_agent_20261011.tests.test_archived_recovery import fixture\n' +
                'from tools.arc_learning_agent_20261011 import archived_recovery as r\n' +
                f'root=Path({str(root)!r})\n' +
                'path,c,assets=fixture(root,large=True)\n' +
                'assert c["files"][c["output_root"]+"/worker/result.json"]["bytes"] >= 34228110\n' +
                'seal=r.prepare_recovery(path,r.descriptor(path)["sha256"],root/"sealed")\n' +
                'result=r.evaluate_recovery(root/"sealed",seal["sha256"],root/"score")\n' +
                'assert result["status"]=="SCORED" and result["tests"]==167\n' +
                'assert result["maximum_resident_kib"] < 512*1024\n' +
                'print(result["maximum_resident_kib"])\n')
            completed = subprocess.run([sys.executable, '-I', '-B', '-S', str(launcher), str(driver)],
                                       capture_output=True, text=True, timeout=180)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            print('Rich archived synthetic CPU-child peak RSS KiB: ' + completed.stdout.strip())


if __name__ == '__main__':
    unittest.main()
