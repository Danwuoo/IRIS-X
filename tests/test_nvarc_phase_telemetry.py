"""E00 CPU fakes: lifecycle clocks are observations, never model correctness."""
import copy
import hashlib
from contextlib import contextmanager, redirect_stdout
import io
import json
import time
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import nvarc_native_multitask as native
from tools import nvarc_native_solve_runtime as inference
from tools import nvarc_public_eval as public
from tools import nvarc_public_eval_runtime as runtime
from tools import nvarc_public_eval_parent as parent
from tools import arc_kaggle_submission as submission
from tools import arc_offline_evaluation as evaluation
from tests.test_nvarc_native_solve import FakeTensor, FakeTorch, FakeModel
from tests.test_nvarc_public_eval import fixture, record


class Clock:
    def __init__(self): self.value = 0.0; self.reads = 0
    def __call__(self): self.reads += 1; return self.value
    def advance(self, amount): self.value += amount


class Array:
    def __init__(self, value): self.value = copy.deepcopy(value)
    def tolist(self): return copy.deepcopy(self.value)
    def __eq__(self, other): return isinstance(other, Array) and self.value == other.value


class SolveFixture:
    def __init__(self, *, beams=None, partial=False):
        self.clock = Clock(); self.events = []; self.votes = None; self.calls = []
        self.adapter = inference.SourceModel(FakeModel(), FakeTorch,
            lambda event, **kw: self.events.append((event, kw)),
            forward_limits={'control': 7, 'generation': 4096, 'verification': 128},
            input_token_limit=5242880, generation_deadline=1000)
        self.adapter.verification_deadline = 1000
        self.beams = beams if beams is not None else [(0.1, [1, 15]), (0.2, [1, 15]),
                                                    (0.3, [10, 15]), (0.4, [2, 15])]
        self.partial = partial; self.verified = 0
        self.loader = SimpleNamespace(ArcDataset=SimpleNamespace(invert_mod=lambda arr, *_a, **_k: arr),
                                      np=SimpleNamespace(asarray=Array))
        self.views = SimpleNamespace(keys=['a_0.r'+str(i) for i in range(16)],
                                     get=lambda *_a: {'input': 'prefix'})
        self.formatter = SimpleNamespace(convert_tokens_to_array=self.parse)
        self.tokenizer = SimpleNamespace(encode=lambda _text: [14, 12, 10])
        self.solver = SimpleNamespace(inference_turbo_dfs=self.generate, turbo_dfs=None, calc_scores=self.verify)
        self.decoder = SimpleNamespace(score_kgmon=self.rank)

    def parse(self, tokens):
        self.clock.advance(.25)
        return None if tokens[0] == 10 else Array([[tokens[0]]])

    def generate(self, adapter, prefixes, max_tokens, floor, deadline):
        self.calls.append(('generation', prefixes, max_tokens, floor, deadline))
        adapter(input_ids=FakeTensor(prefixes), use_cache=True)
        self.clock.advance(2)
        return [(0, copy.deepcopy(self.beams))] if len(self.calls) == 1 else []

    def verify(self, queries, answers, tokenizer, adapter):
        self.verified += 1
        if self.partial and self.verified == 4:
            raise inference.InferenceLimitReached('inference_deadline')
        adapter(input_ids=FakeTensor([[10, 1, 15]]*4), use_cache=True)
        self.clock.advance(3)
        self.calls.append(('verification', list(queries), list(answers)))
        return [1.0]*4

    def rank(self, votes):
        self.votes = copy.deepcopy(votes)
        result = {}; self.clock.advance(.5)
        for v in votes.values(): result.setdefault(native.grid_key(v['solution'].tolist()), v['solution'])
        return list(result.values())

    def run(self, telemetry=False, detailed=False):
        if telemetry: self.adapter.telemetry = public.PhaseTelemetry(clock=self.clock, detailed=detailed)
        batches = [self.views.keys[i:i+4] for i in range(0, 16, 4)]
        verified = [{'input': 'query', 'reply': 'reply'} for _ in range(8)]
        bindings = [{'source_view': 'a_0.v'+str(i), 'query_ids': [10], 'answer_ids': [1, 15]} for i in range(8)]
        with patch.object(native, 'test_views', return_value=('a_0', SimpleNamespace(), self.views, self.formatter, batches)), \
             patch.object(native, 'verifier_rows', return_value=(verified, bindings)), \
             patch.object(inference.time, 'time', self.clock):
            return native.solve_test({}, 'a', 0, self.loader, self.solver, self.decoder, self.tokenizer,
                self.adapter, maximum_candidates=64, emit=lambda event, **kw: self.events.append((event, kw)))


class PhaseTelemetryTests(unittest.TestCase):
    def test_nested_exclusive_scopes_partition_and_missing_is_null(self):
        clock = Clock(); t = public.PhaseTelemetry(clock=clock)
        with t.scope('parse_dedup'):
            clock.advance(2)
            with t.scope('generation'): clock.advance(3)
            clock.advance(1)
        clock.advance(4); data = t.snapshot()
        self.assertEqual(data['inclusive_host_seconds']['parse_dedup'], 6)
        self.assertEqual(data['exclusive_host_seconds']['parse_dedup'], 3)
        self.assertEqual(data['exclusive_host_seconds']['generation'], 3)
        self.assertEqual(data['unscoped_host_seconds'], 4)
        self.assertIsNone(data['exclusive_host_seconds']['training'])
        self.assertIsNone(data['gpu_kernel_seconds'])
        reads = clock.reads
        for _ in range(20):
            with t.detail('hot-path'): pass
        self.assertEqual(clock.reads, reads)
        self.assertIsNone(t.snapshot()['detail_inclusive_host_seconds'])

    def test_lifecycle_counts_votes_provenance_and_default_behavior_parity(self):
        plain, coarse, detailed = SolveFixture(), SolveFixture(), SolveFixture()
        original = plain.run(); observed = coarse.run(True); profiled = detailed.run(True, True)
        for f, result in ((coarse, observed), (detailed, profiled)):
            self.assertEqual({k: v for k, v in result.items() if k != 'telemetry'}, original)
            self.assertEqual(f.calls, plain.calls)
            self.assertEqual(f.votes, plain.votes)
        c = observed['telemetry']['counters']
        self.assertEqual(c, {'raw_returned': 4, 'processed': 4, 'invalid': 1, 'duplicate': 1,
            'parsed_unique': 2, 'verification_started': 2, 'partial_verified': 0,
            'full_verified': 2, 'ranked': 2, 'votes_ranked': 3})
        sources = observed['telemetry']['sequences']
        self.assertEqual([r['source_view'] for r in sources], ['a_0.r0']*4)
        self.assertEqual([r['voted'] for r in sources], [True, True, False, True])
        self.assertEqual(observed['telemetry']['forward_completions']['verification'], 4)
        self.assertEqual(observed['telemetry']['reserved_physical_input_tokens']['verification'], 48)
        clocks = coarse.adapter.telemetry.snapshot()
        self.assertEqual(clocks['exclusive_host_seconds']['verification'], 12)
        self.assertEqual(clocks['exclusive_host_seconds']['generation'], 8)
        self.assertEqual(clocks['exclusive_host_seconds']['ranking'], .5)
        self.assertIn('finite_logits_guard', detailed.adapter.telemetry.snapshot()['detail_inclusive_host_seconds'])

    def test_64_cap_is_processed_not_unique_or_raw_returned(self):
        f = SolveFixture(beams=[(.1, [1, 15])]*70); result = f.run(True)
        c = result['telemetry']['counters']
        self.assertEqual((c['raw_returned'], c['processed'], c['parsed_unique']), (70, 64, 1))
        self.assertEqual((c['duplicate'], c['votes_ranked'], c['ranked']), (63, 64, 1))
        self.assertEqual(result['termination_reason'], 'candidate_limit')

    def test_telemetry_does_not_mask_original_bad_source_token_gate(self):
        for enabled in (False, True):
            f = SolveFixture(beams=[(.1, [float('nan'), 15])])
            with self.subTest(enabled=enabled), self.assertRaisesRegex(RuntimeError, 'EOS/beam'):
                f.run(enabled)
            if enabled:
                self.assertEqual(f.adapter.telemetry.tests['0']['counters']['processed'], 1)
                self.assertEqual(f.adapter.telemetry.tests['0']['termination_reason'], 'exception:RuntimeError')

    def test_partial_four_of_eight_never_ranked_prior_full_candidate_survives(self):
        f = SolveFixture(partial=True); result = f.run(True)
        self.assertEqual(result['ranked_grids'], [[[1]]])
        c = result['telemetry']['counters']
        self.assertEqual((c['verification_started'], c['full_verified'], c['partial_verified']), (2, 1, 1))
        v = result['telemetry']['verifications'][-1]
        self.assertEqual((v['state'], v['completed_views'], v['required_views']), ('partial', 4, 8))

    def test_deadline_before_reservation_and_inflight_overrun_do_not_add_calls(self):
        clock = Clock(); events = []
        class Slow(FakeModel):
            def __call__(self, **kwargs):
                value = super().__call__(**kwargs); clock.advance(3); return value
        adapter = inference.SourceModel(Slow(), FakeTorch, lambda e, **kw: events.append((e, kw)),
            forward_limits={'control': 7, 'generation': 4, 'verification': 2},
            input_token_limit=1000, generation_deadline=1)
        with patch.object(inference.time, 'time', clock), adapter.scope('generation'):
            value = adapter(input_ids=FakeTensor([[10]]*4), use_cache=True)
            self.assertIsNotNone(value); self.assertGreater(clock(), adapter.generation_deadline)
            with self.assertRaisesRegex(inference.InferenceLimitReached, 'deadline'):
                adapter(input_ids=FakeTensor([[10]]*4), use_cache=True)
        self.assertEqual(adapter.reserved['generation'], adapter.completed['generation'])
        self.assertEqual(len(adapter.model.calls), 1)
        self.assertEqual([e for e, _ in events], ['forward_reserved', 'forward_completed'])
        adapter.generation_deadline = clock()
        adapter.reserved['generation'] = adapter.completed['generation'] = 0
        with patch.object(inference.time, 'time', clock), adapter.scope('generation'), \
             self.assertRaises(inference.InferenceLimitReached):
            adapter(input_ids=FakeTensor([[10]]*4), use_cache=True)
        self.assertEqual(adapter.reserved['generation'], 0)
        self.assertEqual(len(adapter.model.calls), 1)

    def test_deadline_crossed_after_reservation_is_cooperative_and_not_second_gate(self):
        clock = Clock()
        def emit(event, **details):
            if event == 'forward_reserved': clock.advance(2)
        adapter = inference.SourceModel(FakeModel(), FakeTorch, emit,
            forward_limits={'control': 7, 'generation': 4, 'verification': 2},
            input_token_limit=1000, generation_deadline=1)
        with patch.object(inference.time, 'time', clock), adapter.scope('generation'):
            adapter(input_ids=FakeTensor([[10]]*4), use_cache=True)
        self.assertEqual((adapter.reserved['generation'], adapter.completed['generation']), (1, 1))
        self.assertGreater(clock(), adapter.generation_deadline)

    def test_exception_after_reservation_is_unfinished_and_detail_preserves_exception(self):
        clock = Clock(); f = SolveFixture(); f.adapter.telemetry = public.PhaseTelemetry(clock=clock, detailed=True)
        def broken(**kwargs): clock.advance(1); raise RuntimeError('synthetic OOM-like fault')
        f.adapter.model = broken
        with self.assertRaisesRegex(RuntimeError, 'OOM-like'), patch.object(inference.time, 'time', clock), \
             f.adapter.telemetry.scope('generation'), f.adapter.scope('generation'):
            f.adapter(input_ids=FakeTensor([[10]]*4), use_cache=True)
        self.assertEqual((f.adapter.reserved['generation'], f.adapter.completed['generation']), (1, 0))
        self.assertEqual((f.adapter.input_by_phase['generation'], f.adapter.completed_input_by_phase['generation']), (4, 0))
        t = f.adapter.telemetry.snapshot()
        self.assertEqual(t['events'][0]['type'], 'RuntimeError')
        self.assertEqual(t['detail_inclusive_host_seconds']['model_entry_host_wall'], 1)

    def test_per_test_deadline_after_timeout_next_test_and_unlaunched_denominator(self):
        plan, data = fixture(); clock = Clock(); checkpoints = []; calls = []
        rec = record(plan, data, 'a')
        def solve(index, deadline):
            calls.append((index, deadline)); clock.advance(31)
            if index == 0: raise inference.InferenceLimitReached('inference_deadline')
            result = public.empty_tests(2)[index]; result.update(status='missing-candidate', termination_reason='all_source_batches_completed')
            return result
        runtime.solve_all_tests(plan, data, 'a', solve, lambda r: checkpoints.append(copy.deepcopy(r)), rec,
                                now=clock, deadline=100)
        self.assertEqual(calls, [(0, 30), (1, 61)])
        self.assertEqual(rec['tests'][0]['status'], 'budget_stop')
        self.assertEqual(rec['tests'][1]['termination_reason'], 'all_source_batches_completed')
        clock.advance(100); untouched = record(plan, data, 'a')
        runtime.solve_all_tests(plan, data, 'a', solve, lambda _: None, untouched, now=clock, deadline=100)
        self.assertEqual(len(calls), 2)
        with tempfile.TemporaryDirectory() as tmp:
            store = public.ResultStore(Path(tmp), plan, data, allow_fixture=True); store.commit(untouched)
            coverage = json.loads((Path(tmp)/'coverage.json').read_bytes())
            self.assertEqual((coverage['tests'], coverage['tests_not_executed']), (3, 3))

    def test_nested_evaluator_injection_and_bool_index_fail_closed(self):
        plan, data = fixture(); rec = record(plan, data, 'a')
        for field in ('solutions', 'candidate_oracle', 'diagnostic_label', 'route_label', 'pass_at_2'):
            leaked = copy.deepcopy(rec); leaked['telemetry'] = {'nested': [{'payload': {field: 'answer-derived'}}]}
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, 'evaluator'):
                public.validate_record(plan, data, leaked)
        rec['tests'][0]['test_index'] = False
        with self.assertRaisesRegex(RuntimeError, 'ordered'): public.validate_record(plan, data, rec)
        for body in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.assertRaises(submission.SubmissionError): submission.parse_json(body)

    def test_evaluator_bootstrap_recomputes_weighted_test_ratio(self):
        from tests.test_arc_offline_evaluation import fixture as scoring_fixture
        data, truth, pools = scoring_fixture(); left = evaluation.evaluate(data, truth, pools)
        other = copy.deepcopy(pools); other['run_id'] = 'right'
        other['records'][0]['tests'][0]['ranked_grids'] = [[[0]]]
        other['records'][1]['tests'][0]['ranked_grids'] = []
        right = evaluation.evaluate(data, truth, other)
        result = evaluation.paired_task_cluster_bootstrap(left, right, repeats=50, seed=19)
        self.assertEqual(result, evaluation.paired_task_cluster_bootstrap(left, right, repeats=50, seed=19))
        mixed = [r for r in result['samples'] if r['test_denominator'] == 5]
        self.assertTrue(mixed)
        self.assertTrue(all(r['test_micro_delta'] == 0 and r['task_macro_delta'] == -.375 for r in mixed))

    def test_checkpoint_replace_failure_keeps_last_file_but_sidecars_are_not_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'checkpoint.json'; native.write(path, {'generation': 1})
            before = path.read_bytes()
            with patch.object(Path, 'replace', side_effect=PermissionError('synthetic replace denied')):
                with self.assertRaises(PermissionError): native.write(path, {'generation': 2})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(submission.parse_json(path.read_bytes()), {'generation': 1})
            self.assertTrue(path.with_suffix('.json.tmp').exists())

    def test_parent_watchdog_kills_finite_cpu_children_and_exception_receipt_is_distinct(self):
        plan, data = fixture(); plan['fixture_repository'] = str(Path(__file__).resolve().parents[1])
        body = '''import argparse,json,sys,time
from pathlib import Path
p=argparse.ArgumentParser()
for k in ('root','model','dependency','rank','deadline','parent-pid'):p.add_argument('--'+k)
a=p.parse_args();root=Path(a.root);rank=int(a.rank);d=root/'workers'/str(rank)
plan=json.loads((root/'plan.json').read_bytes());data=json.loads((root/'challenges.json').read_bytes())
sys.path.insert(0,plan['fixture_repository'])
from tools.nvarc_native_multitask import write
from tools.nvarc_public_eval import task_binding,empty_tests,MailboxReader
from tools.arc_kaggle_submission import parse_json
reader=MailboxReader()
write(d/'ready.json',{'rank':rank,'uuid':'fake-'+str(rank),'model_material_digest':plan['model_material_digest']})
until=time.monotonic()+15
while time.monotonic()<until:
 job=d/'job.json'
 if job.is_file():
  body=reader.read(job)
  if body is None:time.sleep(.01);continue
  value=parse_json(body)
  if value.get('stop'):sys.exit(0)
  key=value['task_id'];out=root/'tasks'/key;out.mkdir(exist_ok=True)
  tests=empty_tests(len(data[key]['test']))
  if key=='a':
   from tools.nvarc_native_multitask import digest
   tests[0].update(attempts=[[[2]]],ranked_grids=[[[2]]],missing_attempts=1,status='missing-candidate',
    termination_reason='all_source_batches_completed',candidate_evidence={digest([[2]]):{'scores':[1.]*8,
     'rows':[{'source_view':'a_0.v'+str(i),'query_digest':digest([1]),'answer_digest':digest([2]),'score':1.} for i in range(8)]}})
  write(out/'checkpoint.json',{'binding':task_binding(plan,data,key),'baseline_verified':True,
   'training_complete':False,'training_steps':0,'tests':tests,'outcome':'partial','reset_verified':None,'timings':{}})
  if rank==1:sys.exit(17)
  time.sleep(15);sys.exit(0)
 time.sleep(.01)
sys.exit(19)
'''
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            root = Path(tmp); native.write(root/'plan.json', plan); native.write(root/'challenges.json', data)
            stub = root/'bounded_cpu_child.py'; stub.write_text(body, encoding='utf-8')
            store = public.ResultStore(root, plan, data, allow_fixture=True); processes = []
            clock = Clock()
            def launch(*a, **kw):
                process = subprocess.Popen(*a, **kw); processes.append(process); return process
            def pause(_seconds): time.sleep(.02); clock.advance(5)
            summary = parent.run_workers(root, plan, data, root, root,
                [{'uuid': 'fake-'+str(i)} for i in range(4)], store, 0,
                launch=launch, worker_command=[sys.executable, str(stub)], now=clock, pause=pause)
            self.assertTrue(all(p.poll() is not None for p in processes))
            timed = [r for r in summary['worker_failures'] if r['parent_hard_watchdog']]
            failed = [r for r in summary['worker_failures'] if r['returncode'] == 17]
            self.assertEqual(len(timed), 1); self.assertEqual(len(failed), 1)
            self.assertFalse(failed[0]['parent_hard_watchdog'])
            self.assertEqual(timed[0]['reason'], 'task-watchdog-timeout')
            self.assertTrue(timed[0]['returncode'] is not None)
            self.assertEqual(store.records['a']['tests'][0]['ranked_grids'], [[[2]]])
            self.assertEqual(json.loads((root/'coverage.json').read_bytes())['tests'], 3)
            events = [json.loads(line) for line in (root/'progress.jsonl').read_bytes().splitlines()]
            self.assertEqual(len([r for r in events if r['event'] == 'worker-retired']), 2)

    def test_inert_plan_has_one_factor_finite_screen_and_no_fresh_holdout_claim(self):
        root = Path(__file__).resolve().parents[1]
        plan = submission.parse_json((root/'research/stage4-e00/controlled-experiment-plan.json').read_bytes())
        self.assertEqual(plan['status'], 'inert_not_dispatched')
        self.assertTrue(plan['requires_owner_authorization'])
        self.assertEqual(plan['owner_authorized_executions'], 0)
        self.assertEqual(plan['screen']['task_runs_maximum'], 24*2*2)
        self.assertEqual(plan['screen']['generation_batches_upper_bound'], plan['screen']['test_runs_upper_bound']*4)
        self.assertEqual(plan['controls']['ttt_steps'], 128)
        self.assertEqual(plan['controls']['dfs_sequence_probability_floor'], .2)
        self.assertEqual(plan['controls']['native_checkpoint_true_count'], 37)
        self.assertTrue(plan['controls']['cap_includes_duplicate_and_invalid'])
        self.assertEqual(plan['calibration_gate_before_E10']['additional_calibration_runs'], 0)
        self.assertEqual(plan['confirmation']['maximum_comparisons_across_stage4'], 1)
        self.assertIn('never fresh holdout', plan['partition']['qualification'])
        self.assertIsNone(plan['bindings']['future_runtime_package'])
        self.assertIsNone(plan['official']['public_score'])
        self.assertFalse(plan['promotion'])
        manifest = submission.parse_json((root/'research/stage4-e00/original-specs/MANIFEST.json').read_bytes())
        for name in ('FIRST_LOCAL_TASK_PROMPT.md', 'RELIABILITY_ACCEPTANCE.md'):
            expected = next(r for r in manifest['files'] if r['path'] == name)
            body = (root/'research/stage4-e00/original-specs'/name).read_bytes()
            self.assertEqual(hashlib.sha256(body).hexdigest(), expected['sha256'])
            self.assertEqual(len(body), expected['bytes'])


if __name__ == '__main__': unittest.main()
