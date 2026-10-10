"""Coordinator CPU acceptance uses synthetic inputs, never public answer bytes."""
import contextlib
import copy
import io
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from tools.arc_consolidated_20261010 import verifier, arc_object_ir as ir
from tools.arc_consolidated_20261010.controls import synthetic_controls
from tools.arc_consolidated_20261010.ledger import Ledger, digest, BindingMismatch
from tools.arc_public_research_20261010 import runner, public_data as data, query_executor as query
from tools.arc_public_research_20261010.tests.test_public_data import make_assets

IDENTITY = {'steps': [{'op': 'identity'}]}
TASK = {'task_id': 'synthetic', 'demos': [{'input': [[1]], 'output': [[1]]}]}


def make_ledger(root):
    limits = runner.limits_for()
    bindings = {k: 'f' * 64 for k in ('source', 'task', 'model', 'prompt', 'sampling', 'mode')}
    bindings['budget'] = digest(limits)
    return Ledger(root, bindings, limits)


def synthetic_receipt(source, task, *, fit=False, timeout=3.0, max_steps=200000):
    """Test-only schema-valid receipt; never represented as real VM acceptance."""
    request = verifier._validate_request(source, task, timeout, max_steps)
    receipt = verifier._result('fit' if fit else 'mismatch', 'SYNTHETIC TEST RECEIPT', request)
    receipt.update(worker_wall_seconds=.001, worker_cpu_seconds=.001)
    for index, pair in enumerate(task['demos']):
        row = verifier._empty_demo(index, pair)
        row.update(status='match' if fit else 'mismatch', match=fit,
                   actual_shape=row['expected_shape'], mismatch_count=0 if fit else 1,
                   mismatch_samples=[] if fit else [{'row': 0, 'column': 0,
                       'expected': pair['output'][0][0], 'actual': (pair['output'][0][0] + 1) % 10}],
                   gas=0, reason='synthetic receipt')
        receipt['demos'].append(row)
    receipt.update(dispatched=True, gas_reserved=200000, gas_charged=0,
                   owned_descendants_stopped=True, wall_reserved_seconds=3.0, wall_seconds=.001)
    return receipt


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_caps_and_cli_are_inert(self):
        cap = runner.limits_for()
        self.assertEqual(cap['cpu_checks'], 128 + 15360 + 240 + 1336)
        self.assertEqual(cap['physical_calls'], 240)
        self.assertEqual(cap['wall_seconds'], 7200)
        with patch.object(runner, 'run', side_effect=AssertionError('must be inert')), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(runner.main([]), 0)
            self.assertEqual(runner.main(['--enable-model']), 0)
        self.assertIn('manual-start-disabled', out.getvalue())

    def test_main_source_contains_scorer_and_model_subset(self):
        identity = runner.source_identity()
        self.assertIn('src/irisx/arc_agi2.py', identity)
        self.assertIn('tools/arc_public_research_20261010/runner.py', identity)
        self.assertIn('tools/arc_public_research_20261010/remote_model_owner.py', identity)
        self.assertTrue(set(runner.evaluator.source_identity()) <= set(identity))
        model = {k: v for k, v in identity.items() if k.startswith('tools/')}
        self.assertLess(len(model), len(identity))

    def test_identical_policy_plans_are_distinct_fresh_physical_calls(self):
        ledger = make_ledger(self.root / 'ledger')
        calls = []
        def check(source, task, **kwargs):
            calls.append(task['task_id'])
            return synthetic_receipt(source, task, **kwargs)
        with ledger.session(180):
            checked = runner.FreshVerifier(ledger, check)
            rows = checked.batch([{'call_id': 'uniform-0', 'task': TASK, 'plan': IDENTITY},
                                  {'call_id': 'shape-0', 'task': TASK, 'plan': IDENTITY}])
            self.assertEqual(len(calls), 2)
            self.assertEqual(ledger.summary()['charged']['cpu_checks'], 2)
            self.assertEqual([r['call_id'] for r in rows], ['uniform-0', 'shape-0'])
            self.assertLessEqual(checked.workers_used, 4)
            checked.batch([{'call_id': 'uniform-0', 'task': TASK, 'plan': IDENTITY}])
            self.assertEqual(len(calls), 2)

    def test_unknown_is_not_retried_and_all_rows_remain(self):
        ledger = make_ledger(self.root / 'ledger')
        with ledger.session(180):
            checked = runner.FreshVerifier(ledger, lambda *a, **k: (_ for _ in ()).throw(RuntimeError('unknown')))
            jobs = [{'call_id': 'check-%d' % i, 'task': TASK, 'plan': IDENTITY} for i in range(10)]
            rows = checked.batch(jobs)
            self.assertEqual(len(rows), 10)
            self.assertFalse(checked.all_stopped)
            self.assertEqual(ledger.summary()['charged']['cpu_checks'], 4)
            self.assertEqual(sum(r['verification']['status'] == 'unknown' for r in rows), 4)
            self.assertEqual(sum(r['verification']['status'] == 'missing' for r in rows), 6)
            self.assertEqual(runner._pending(ledger), 4)

    def test_cleanup_reserve_prevents_dispatch(self):
        ledger = make_ledger(self.root / 'ledger')
        with ledger.session(120):
            check = runner.FreshVerifier(ledger, lambda *a, **k: self.fail('reserve lost'))
            rows = check.batch([{'call_id': 'never', 'task': TASK, 'plan': IDENTITY}])
            self.assertEqual(rows[0]['verification']['status'], 'missing')
            self.assertEqual(ledger.summary()['charged']['cpu_checks'], 0)

    def test_original_fit_order_distinct_top_two(self):
        other = {'steps': [{'op': 'transpose'}]}
        pool = {ir.digest(p): {'plan': p} for p in (IDENTITY, other)}
        def row(plan, ident, fit):
            return {'candidate_id': ir.digest(plan), 'call_id': ident,
                    'verification': synthetic_receipt(ir.compile_plan(plan), TASK, fit=fit)}
        rows = [row(IDENTITY, 'wrong', False), row(other, 'first', True),
                row(other, 'duplicate', True), row(IDENTITY, 'second', True)]
        chosen = runner._fresh_candidates(rows, pool, 'synthetic-run', 2)
        self.assertEqual([v['fit_call_id'] for v in chosen], ['first', 'second'])
        self.assertEqual(len(runner._fresh_candidates(rows, pool, 'synthetic-run', 1)), 1)

    def test_controls_are_first_and_failure_never_opens_solver_or_evaluator(self):
        assets = make_assets(self.root)
        with patch.object(runner.data, 'load_solver_tasks', side_effect=AssertionError('data before controls')) as loader, \
             patch.object(runner.evaluator, 'evaluate_sealed', side_effect=AssertionError('score before controls')) as score:
            result = runner._run_synthetic_for_tests(self.root / 'out', assets['solver_root'], assets['evaluator_root'],
                assets['solver_manifest_sha256'], assets['evaluator_manifest_sha256'],
                verify_fn=lambda s, t, **k: synthetic_receipt(s, t, **k), session_seconds=180)
        self.assertEqual(result['report']['scoring']['status'], 'SCORING_BLOCKED')
        self.assertIsNone(result['report']['official_score'])
        self.assertEqual(result['report']['test_denominator'], 167)
        self.assertEqual(result['report']['accounting']['charged']['cpu_checks'], 128)
        loader.assert_not_called(); score.assert_not_called()
        self.assertTrue((self.root / 'out' / 'post-seal-closure.json').is_file())
        self.assertEqual(parse(self.root / 'out' / 'entry-provenance.json')['source_transport_mode'], 'direct-source')
        with zipfile.ZipFile(result['archive']['archive']) as z:
            self.assertIn('summary.json', z.namelist())
            self.assertNotIn('post-seal-closure.json', z.namelist())
        with self.assertRaisesRegex(ValueError, 'partial resume is fail-closed'):
            runner._run_synthetic_for_tests(self.root / 'out', assets['solver_root'], assets['evaluator_root'],
                assets['solver_manifest_sha256'], assets['evaluator_manifest_sha256'], resume=True)

    def test_synthetic_override_cannot_claim_production_or_enable_model(self):
        with self.assertRaisesRegex(ValueError, 'production test hooks'):
            runner._run('unused', 'unused2', 'unused3', 'a' * 64, 'b' * 64,
                        _verify_fn=lambda *a: None)
        with self.assertRaisesRegex(ValueError, 'cannot enable'):
            runner._run_synthetic_for_tests(enable_model=True)
        with self.assertRaisesRegex(ValueError, 'entry bootstrap'):
            runner.run('unused', 'unused2', 'unused3', 'a' * 64, 'b' * 64, entry_wall_seconds=float('nan'))

    def test_closed_synthetic_queries_one_input_per_cpu_reservation(self):
        assets = make_assets(self.root)
        solver = data.load_solver_tasks(assets['solver_root'], assets['solver_manifest_sha256'])
        key = next(iter(solver['demos_tasks']))
        task = solver['demos_tasks'][key]
        # This fit receipt and these two queries are real bounded CPU checks on synthetic data.
        verified = verifier.verify(ir.compile_plan(IDENTITY), task)
        self.assertTrue(verified['all_demos_fit'])
        selected = {p: {} for p in data.POLICIES}
        selected['raw'][key] = [{'candidate_id': ir.digest(IDENTITY), 'run_id': 'synthetic-run',
                                'plan': IDENTITY, 'verification': verified}]
        ledger = make_ledger(self.root / 'ledger')
        with ledger.session(180):
            checked = runner.FreshVerifier(ledger)
            path = runner._query_policies(solver, selected, ledger, self.root / 'out', 'synthetic-run', checked)
            self.assertEqual(ledger.summary()['charged']['search_checks'], 2)
            self.assertEqual(ledger.summary()['charged']['cpu_checks'], 2)
            proof = parse(path / 'prediction-proof-raw.json')
            self.assertEqual(len(proof['query_receipts'][key]), 2)
            self.assertTrue(all(v['receipt']['query_count'] == 1 for v in proof['query_receipts'][key]))
            raw = parse(path / 'pools-raw.json')
            self.assertEqual(sum(len(r['tests']) for r in raw['records']), 167)
            self.assertEqual(raw['records'][0]['tests'][0]['ranked_grids'], [[[2]]])
            # All four selections predate every query reservation/result.
            earliest = min(v['receipt']['started_at_ns'] for v in proof['query_receipts'][key])
            self.assertTrue(all(parse(path / ('selection-' + p + '.json'))['sealed_at_ns'] <= earliest for p in data.POLICIES))

    def test_actual_synthetic_owner_runner_proof_seals_and_scores(self):
        from tools.arc_public_research_20261010 import remote_model_owner as remote
        from tools.arc_public_research_20261010.tests.test_generation_owner import fixtures, PLAN_HASH
        from tools.arc_public_research_20261010.tests.test_evaluator_boundary import predictions, bindings
        assets = make_assets(self.root)
        bootstrap, source = fixtures(self.root)
        owner = remote.RemoteModelOwner._synthetic_for_tests(bootstrap,
            environment_plan_sha256=PLAN_HASH, source_identity=source,
            deadline_monotonic=time.monotonic() + 30)
        self.addCleanup(owner.close)
        owner.initialize_tokenizer()
        closure = owner.close()
        ledger = make_ledger(self.root / 'ledger')
        with ledger.session(180):
            proof = runner._owner_proof(owner, closure, ledger, self.root / 'out')
        self.assertEqual(Path(proof['request']['path']).name, 'request.json')
        self.assertEqual(Path(proof['start']['path']).name, 'worker-start.json')
        self.assertEqual(data.read_regular(proof['request']['path']), data.read_regular(owner._request_path))
        bind = bindings(); bind['source_identity'] = runner.source_identity()
        bind['actual_environment_lock_sha256'] = bootstrap['actual_environment_lock_sha256']
        pred = predictions(self.root / 'predictions', assets)
        seal = runner.evaluator.seal_predictions(pred, solver_root=assets['solver_root'],
            solver_manifest_sha256=assets['solver_manifest_sha256'],
            evaluator_manifest_sha256=assets['evaluator_manifest_sha256'], owner_proof=proof, bindings=bind)
        result = runner.evaluator.evaluate_sealed(pred, seal['seal_sha256'], solver_root=assets['solver_root'],
            evaluator_root=assets['evaluator_root'], output_root=self.root / 'score')
        self.assertEqual(result['status'], 'SCORED')
        self.assertEqual(result['evidence_mode'], 'synthetic-test-only')
        self.assertEqual(result['policies']['raw']['metrics']['pass_at_2']['denominator'], 167)

    def test_synthetic_end_to_end_partial_rank_work_keeps167_and_resume_noop(self):
        assets = make_assets(self.root)
        controls = {digest({'source': ir.compile_plan(c['plan']), 'task': c['task']}): c['expected_status']
                    for c in synthetic_controls()}
        def check(source, task, **kwargs):
            status = controls.get(digest({'source': source, 'task': task}), 'mismatch')
            return synthetic_receipt(source, task, fit=status == 'fit', **kwargs)
        def limited_rank(tasks, pool, root, ledger, rank_fn=None):
            # Explicitly synthetic partial work, never a completed PUBLIC120 claim.
            first = next(iter(tasks)); selected = [r['candidate_id'] for r in pool[:64]]
            binding = data.write_new(root / 'synthetic-partial-rank-seal.json',
                                     {'evidence_mode': 'synthetic-test-only', 'physical_checks': 0})
            return {p: {first: selected} for p in ('uniform', 'shape')}, binding['sha256']
        with patch.object(runner, '_seal_rankings', side_effect=limited_rank):
            result = runner._run_synthetic_for_tests(self.root / 'out', assets['solver_root'], assets['evaluator_root'],
                assets['solver_manifest_sha256'], assets['evaluator_manifest_sha256'], verify_fn=check,
                session_seconds=180, entry_wall_seconds=1.25)
        self.assertEqual(result['status'], 'partial-scored', result['report'].get('error'))
        self.assertEqual(result['report']['scoring']['status'], 'SCORED')
        self.assertEqual(result['report']['ranking']['completed_checks'], 128)
        self.assertEqual(result['report']['accounting']['charged']['cpu_checks'], 256)
        self.assertGreaterEqual(result['report']['elapsed_seconds'], 1.25)
        for policy in data.POLICIES:
            self.assertEqual(result['report']['scoring']['policies'][policy]['metrics']['pass_at_2']['denominator'], 167)
        closure = parse(self.root / 'out' / 'post-seal-closure.json')
        self.assertTrue(closure['session_deadline_met'])
        self.assertEqual(closure['accounting']['operation_states']['reserved'], 0)
        before = len(list((self.root / 'out' / 'ledger' / 'responses').iterdir()))
        resumed = runner._run_synthetic_for_tests(self.root / 'out', assets['solver_root'], assets['evaluator_root'],
            assets['solver_manifest_sha256'], assets['evaluator_manifest_sha256'], resume=True)
        self.assertTrue(resumed['resumed_noop'])
        self.assertEqual(len(list((self.root / 'out' / 'ledger' / 'responses').iterdir())), before)
        with patch.object(runner, '_cpu_environment', return_value={'changed': True}), self.assertRaises(BindingMismatch):
            runner._run_synthetic_for_tests(self.root / 'out', assets['solver_root'], assets['evaluator_root'],
                assets['solver_manifest_sha256'], assets['evaluator_manifest_sha256'], resume=True)

    def test_all_rankings_sealed_before_any_physical_check(self):
        pool = runner._base_pool()
        ids = [r['candidate_id'] for r in pool]
        tasks = {str(i): {**TASK, 'task_id': str(i)} for i in range(120)}
        writes = []
        def rank(task, candidates, seed, method, budget):
            self.assertEqual(seed, 0); self.assertEqual(budget, 64)
            return {'method': method, 'task_id': task['task_id'], 'budget': 64,
                    'full_order': ids, 'selected_candidate_ids': ids[:64], 'excluded_candidate_ids': []}
        def write(path, value):
            writes.append((path.name, value)); return {'sha256': 'a' * 64, 'bytes': 1}
        ledger = make_ledger(self.root / 'ledger')
        with ledger.session(180), patch.object(data, 'write_new', side_effect=write), \
             patch.object(verifier, 'verify', side_effect=AssertionError('verification before seal')):
            orders, seal = runner._seal_rankings(tasks, pool, self.root, ledger, rank)
            self.assertEqual(ledger.summary()['charged']['cpu_checks'], 0)
        self.assertEqual(len(writes), 241)
        self.assertEqual(writes[-1][0], 'rankings-seal.json')
        self.assertEqual(writes[-1][1]['physical_checks'], 0)
        self.assertEqual(sum(len(v) for p in orders.values() for v in p.values()), 15360)

    def test_actual128_independent_controls_use_fresh_bounded_children(self):
        ledger = make_ledger(self.root / 'ledger')
        with ledger.session(180):
            checked = runner.FreshVerifier(ledger)
            result = runner._controls(checked, self.root / 'out')
            self.assertTrue(result['passed'])
            self.assertEqual(result['total'], 128)
            self.assertEqual(ledger.summary()['charged']['cpu_checks'], 128)
            self.assertEqual(sum(v['verification']['status'] == 'fit' for v in result['rows']), 64)
            self.assertTrue(checked.all_stopped)

    def test_model_stage_actual_synthetic_pair_and_crash_cleanup(self):
        from tools.arc_public_research_20261010 import remote_model_owner as remote
        from tools.arc_public_research_20261010.tests.test_generation_owner import fixtures, PLAN_HASH
        from tools.arc_public_research_20261010.tests.test_generation_trie import requests
        real_owner = remote.RemoteModelOwner
        for crash in (False, True):
            with self.subTest(crash=crash):
                root = self.root / str(crash); root.mkdir()
                bootstrap, source = fixtures(root)
                ledger = make_ledger(root / 'ledger')
                created = []
                def factory(ready, **kwargs):
                    self.assertTrue(all(kwargs['source_identity'][k] == v for k, v in source.items()))
                    owner = real_owner._synthetic_for_tests(ready, environment_plan_sha256=PLAN_HASH,
                        source_identity=source, deadline_monotonic=kwargs['deadline_monotonic'],
                        faults={'crash_generate': True} if crash else {})
                    created.append(owner); self.addCleanup(owner.close)
                    return owner
                with ledger.session(180), patch.object(runner, '_bootstrap', return_value=bootstrap), \
                     patch.object(remote, 'RemoteModelOwner', side_effect=factory), \
                     contextlib.redirect_stdout(io.StringIO()) as printed:
                    result = runner._model_stage({}, requests()[:2], {'plan_sha256': PLAN_HASH}, {}, ledger,
                                                 root, runner.source_identity(), {})
                    self.assertTrue(result['stop_confirmed'], result)
                    self.assertEqual(result['owner_accounting']['load_count'], 1)
                    self.assertEqual(result['owner_accounting']['tokenizer_load_count'], 1)
                    self.assertEqual(ledger.summary()['charged']['physical_calls'], 1 if crash else 2)
                    self.assertEqual(runner._pending(ledger), 0)
                    self.assertEqual(result['native_prompt_audit']['admitted_pairs'], 1)
                    self.assertTrue((root / 'native-prompt-audit.json').is_file())
                    self.assertIn('at most 2 model calls', printed.getvalue())
                    self.assertEqual(result['status'], 'partial' if crash else 'complete')
                    self.assertEqual(result['proof']['physical_calls'], 1 if crash else 2)
                    self.assertEqual(result['owner_accounting']['hardware_receipt']['status'], 'not_run')
                    self.assertIsNotNone(created[0]._process.returncode)

    def test_streaming_archive_retains_exact_snapshot_and_deadline_fails_closed(self):
        root = self.root / 'evidence'; root.mkdir()
        raw = b'bounded streaming evidence' * 100000
        (root / 'large.bin').write_bytes(raw)
        closed = {'model_owner_stopped': True, 'verifier_descendants_stopped': True}
        result = runner._stream_archive(root, stopped=closed, summary={'status': 'synthetic-test-only'},
            session_id='synthetic', deadline_monotonic=time.monotonic() + 20)
        self.assertEqual(result['streaming_buffer_bytes'], 1024 * 1024)
        with zipfile.ZipFile(result['archive']) as archive:
            seal = data.parse_json(archive.read('global-seal.json'))
            self.assertEqual(seal['files']['large.bin']['sha256'], data.sha256(raw))
            self.assertEqual(archive.read('large.bin'), raw)
        with self.assertRaisesRegex(ValueError, 'deadline'):
            runner._stream_archive(root, stopped=closed, summary={}, session_id='expired',
                                   deadline_monotonic=time.monotonic() - 1)
        self.assertFalse((root / 'archives' / 'evidence-expired.zip').exists())
        with self.assertRaisesRegex(ValueError, 'closure'):
            runner._stream_archive(root, stopped={**closed, 'model_owner_stopped': False}, summary={},
                session_id='live', deadline_monotonic=time.monotonic() + 20)

    def test_query_accounting_overrun_blocks_seal_and_score(self):
        assets = make_assets(self.root)
        solver = data.load_solver_tasks(assets['solver_root'], assets['solver_manifest_sha256'])
        key = next(iter(solver['demos_tasks']))
        receipt = verifier.verify(ir.compile_plan(IDENTITY), solver['demos_tasks'][key])
        selected = {p: {} for p in data.POLICIES}
        selected['raw'][key] = [{'candidate_id': ir.digest(IDENTITY), 'run_id': 'synthetic-run',
                                'plan': IDENTITY, 'verification': receipt}]
        def slow_receipt(*args, **kwargs):
            result = query.query_execute(*args, **kwargs)
            result['results'][0]['wall_seconds'] = 3.1  # explicit synthetic accounting fault
            return result
        ledger = make_ledger(self.root / 'ledger')
        with ledger.session(180):
            checked = runner.FreshVerifier(ledger)
            runner._query_policies(solver, selected, ledger, self.root / 'out', 'synthetic-run', checked,
                                   query_fn=slow_receipt)
            self.assertTrue(checked.all_stopped)
            self.assertEqual(runner._pending(ledger), 0)
            self.assertTrue(ledger.summary()['reservation_overrun'])
            self.assertEqual(ledger.summary()['state'], 'fail')
            with patch.object(runner.evaluator, 'seal_predictions', side_effect=AssertionError('must not seal')) as seal, \
                 patch.object(runner.evaluator, 'evaluate_sealed', side_effect=AssertionError('must not score')) as score:
                with self.assertRaisesRegex(ValueError, 'overrun'):
                    runner._scoring_admission(ledger)
                seal.assert_not_called(); score.assert_not_called()
            self.assertEqual(ledger.summary()['charged']['search_checks'], 1)

    def test_entry_provenance_exact_schema_hashes_and_transport_mode(self):
        source = {'tools/example.py': '1' * 64}
        valid = notebook_entry(source, '2' * 64, '3' * 64)
        for mode in ('verified-archive', 'verified-extracted-source-root', 'verified-extracted-source-directory'):
            item = {**valid, 'source_transport_mode': mode, 'source_archive_bytes_verified': mode == 'verified-archive'}
            accepted = runner._entry_provenance(item, source, '2' * 64, '3' * 64)
            self.assertEqual(accepted, item)
            self.assertIsNot(accepted, item)
        direct = runner._entry_provenance(None, source, '2' * 64, '3' * 64)
        self.assertEqual(direct['source_transport_mode'], 'direct-source')
        self.assertEqual(direct['source_identity_sha256'], digest(source))
        mutations = [
            {'unexpected': True}, {'format': 'foreign'}, {'code_reference': 'danielwuu/iris-x-public120-code-20261010/2'},
            {'data_reference': 'foreign/data/1'}, {'code_manifest_sha256': 'bad'},
            {'source_archive_sha256': 'F' * 64}, {'source_identity_sha256': '9' * 64},
            {'data_material_manifest_sha256': False}, {'solver_manifest_sha256': '9' * 64},
            {'evaluator_manifest_sha256': '9' * 64}, {'source_transport_mode': 'unverified'},
            {'source_archive_bytes_verified': False}, {'source_archive_bytes_verified': 1}]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                runner._entry_provenance({**valid, **mutation}, source, '2' * 64, '3' * 64)
        for name in valid:
            missing = dict(valid); missing.pop(name)
            with self.subTest(missing=name), self.assertRaises(ValueError):
                runner._entry_provenance(missing, source, '2' * 64, '3' * 64)

    def test_entry_provenance_is_bound_retained_before_controls_and_archived(self):
        assets = make_assets(self.root)
        entry = notebook_entry(runner.source_identity(), assets['solver_manifest_sha256'], assets['evaluator_manifest_sha256'])
        output = self.root / 'out'
        observed = []
        def controls(checked, root):
            retained = parse(root / 'entry-provenance.json')
            self.assertEqual(retained, entry)
            self.assertEqual(checked.ledger.bindings['entry_provenance'], digest(entry))
            observed.append(retained)
            return {'passed': False, 'total': 128, 'expected': 128, 'rows': []}
        with patch.object(runner, '_controls', side_effect=controls):
            result = runner._run_synthetic_for_tests(output, assets['solver_root'], assets['evaluator_root'],
                assets['solver_manifest_sha256'], assets['evaluator_manifest_sha256'], entry_provenance=entry)
        self.assertEqual(len(observed), 1)
        self.assertEqual(result['report']['scoring']['status'], 'SCORING_BLOCKED')
        with zipfile.ZipFile(result['archive']['archive']) as archive:
            self.assertEqual(data.parse_json(archive.read('entry-provenance.json')), entry)
            seal = data.parse_json(archive.read('global-seal.json'))
            self.assertEqual(seal['files']['entry-provenance.json']['sha256'],
                             data.sha256(data.canonical(entry) + b'\n'))
        changed = {**entry, 'code_manifest_sha256': '0' * 64}
        with self.assertRaises(BindingMismatch):
            runner._run_synthetic_for_tests(output, assets['solver_root'], assets['evaluator_root'],
                assets['solver_manifest_sha256'], assets['evaluator_manifest_sha256'], entry_provenance=changed, resume=True)


def notebook_entry(source, solver_sha, evaluator_sha):
    return {'format': 'irisx/public120-notebook-source-admission-v1',
            'code_reference': 'danielwuu/iris-x-public120-code-20261010/1',
            'code_manifest_sha256': 'a' * 64, 'source_archive_sha256': 'b' * 64,
            'source_identity_sha256': digest(source), 'source_transport_mode': 'verified-archive',
            'source_archive_bytes_verified': True,
            'data_reference': 'danielwuu/iris-x-public120-data-20261010/1',
            'data_material_manifest_sha256': 'c' * 64,
            'solver_manifest_sha256': solver_sha, 'evaluator_manifest_sha256': evaluator_sha}


def parse(path):
    return data.parse_json(data.read_regular(path))


if __name__ == '__main__':
    unittest.main()
