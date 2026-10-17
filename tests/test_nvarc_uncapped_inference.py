"""CPU-only uncapped adapter/stream/replay tests; no weights, GPU or provider IO.

The NumPy tensor/model below is explicitly synthetic. Exact-source tests need
IRIS_NATIVE_CODE_ONLY_DIR (or IRISX_E12_NATIVE_FIXTURE) pointing at retained pinned
source. They never replace missing historical experiment evidence with mocks.
"""
from tests.platform_requirements import requires_linux
import ast
from contextlib import nullcontext
import copy
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import numpy as np

from tools import nvarc_uncapped_inference as inference
from tools import nvarc_uncapped_source as source
from tools.nvarc_native_multitask import digest
from tools.nvarc_uncapped_artifacts import StreamEvents, atomic_json, read_json, iter_events


class Tensor:
    def __init__(self, data, dtype=None): self.data = np.asarray(data, dtype=dtype)
    @property
    def shape(self): return self.data.shape
    def size(self, axis): return self.shape[axis]
    def detach(self): return self
    def cpu(self): return self
    def contiguous(self): return self
    def float(self): return Tensor(self.data.astype(np.float32))
    def tolist(self): return self.data.tolist()
    def item(self): return self.data.item()
    def sum(self): return Tensor(self.data.sum())
    def all(self): return Tensor(self.data.all())
    def unsqueeze(self, axis): return Tensor(np.expand_dims(self.data, axis))
    def expand(self, n, width): return Tensor(np.broadcast_to(self.data, (n, self.shape[1] if width == -1 else width)))
    def view(self, *shape): return Tensor(self.data.reshape(*shape))
    def log_softmax(self, axis):
        shifted = self.data-self.data.max(axis=axis, keepdims=True)
        return Tensor(shifted-np.log(np.exp(shifted).sum(axis=axis, keepdims=True)))
    def __getitem__(self, key):
        if isinstance(key, tuple): key = tuple(k.data if isinstance(k, Tensor) else k for k in key)
        return Tensor(self.data[key])
    def __sub__(self, other): return Tensor(self.data-(other.data if isinstance(other, Tensor) else other))


class Torch:
    long = np.int64
    float32 = np.float32
    def tensor(self, values, dtype=None, **_kw): return Tensor(values, dtype)
    def arange(self, n, **_kw): return Tensor(np.arange(n, dtype=np.int64))
    def full(self, shape, value, **_kw): return Tensor(np.full(shape, value, dtype=np.int64))
    def isfinite(self, values): return Tensor(np.isfinite(values.data))
    def inference_mode(self): return nullcontext()
    def no_grad(self): return lambda function: function


class CompactTokens:
    """Labeled test tokenizer for the exact grid/chat text alphabet only."""
    words = {str(i): i for i in range(10)} | {'\n': 10, 'user': 11, 'assistant': 12,
        '<|endoftext|>': 13, '<|im_start|>': 14, '<|im_end|>': 15}
    pattern = re.compile('|'.join(re.escape(k) for k in sorted(words, key=len, reverse=True)))
    def encode(self, text):
        parts = self.pattern.findall(text)
        if ''.join(parts) != text: raise AssertionError('synthetic compact text outside exact alphabet')
        return [self.words[p] for p in parts]
    def decode(self, values, **_kw):
        inverse = {v: k for k, v in self.words.items()}
        return ''.join(inverse[v] for v in values)


class Model:
    device = 'explicit-numpy-cpu-fixture'
    def __init__(self, mode='uniform'):
        self.mode = mode; self.calls = 0; self.cache = object()
    def __call__(self, input_ids, **kwargs):
        self.calls += 1
        shape = [*input_ids.shape, 16]
        logits = np.zeros(shape, dtype=np.float32)
        if self.mode == 'branch':
            logits.fill(-30)
            if kwargs.get('past_key_values') is None:
                logits[:, :, 1] = logits[:, :, 2] = 0
            else: logits[:, :, 15] = 0
        elif self.mode == 'nonfinite': logits[0, 0, 0] = np.nan
        elif self.mode == 'wrong-vocab': logits = logits[:, :, :15]
        if self.mode == 'tuple': return Tensor(logits), self.cache
        return NS(logits=Tensor(logits), past_key_values=None if self.mode == 'no-cache' else self.cache)


class AdapterTests(unittest.TestCase):
    @requires_linux('Real streamed evidence writer requires O_DIRECTORY and directory fsync')
    def test_more_than_4096_forwards_all_counted_observed_and_streamed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'events.jsonl'; bound = {'fixture': 'synthetic-cpu-only'}
            with StreamEvents(path, bound) as events:
                observer = inference.StreamForwardObserver(events.emit)
                observer.begin_test(0)
                adapter = inference.UncappedModel(Model(), Torch(), events.emit, forward_observer=observer)
                with adapter.scope('generation'):
                    for _ in range(4101): adapter(input_ids=Tensor([[1]]*4), use_cache=True)
                self.assertEqual(adapter.reserved['generation'], 4101)
                self.assertEqual(adapter.completed['generation'], 4101)
                self.assertEqual(adapter.input_tokens, 16404)
                self.assertEqual(observer.snapshot()['observed_rows'], 4101)
                self.assertFalse(observer.snapshot()['truncated'])
                self.assertFalse(hasattr(observer, 'rows'))
                self.assertIsNone(adapter.forward_limits['generation'])
                self.assertIsNone(adapter.input_token_limit)
                self.assertIsNone(adapter.generation_deadline)
            count = sum(1 for _ in iter_events(path, bound))
            self.assertEqual(count, 4101*3)

    def test_input_tokens_have_no_former_total_ceiling(self):
        adapter = inference.UncappedModel(Model(), Torch(), lambda *_a, **_k: None)
        adapter.input_tokens = adapter.input_by_phase['generation'] = 5242880
        with adapter.scope('generation'):
            adapter(input_ids=Tensor([[1]]*4), use_cache=True)
        self.assertEqual(adapter.input_tokens, 5242884)

    def test_verification_over_128_calls_keeps_only_live_readback(self):
        adapter = inference.UncappedModel(Model(), Torch(), lambda *_a, **_k: None)
        adapter.verification_rows = [{'source_view': str(i), 'query_ids': [12], 'answer_ids': [1, 15]}
                                     for i in range(4)]
        with adapter.scope('verification'):
            for _ in range(130): adapter(input_ids=Tensor([[12, 1, 15]]*4), use_cache=True)
        self.assertEqual(adapter.completed['verification'], 130)
        self.assertEqual(adapter.last_verification['call_id'], 130)
        self.assertEqual(len(adapter.last_verification['rows']), 4)
        self.assertFalse(hasattr(adapter, 'observed'))
        self.assertIsNone(adapter.forward_limits['verification'])

    def test_model_failure_keeps_reservation_and_failed_observation(self):
        observed = []
        def emit(name, **details): observed.append((name, details))
        class Failure:
            device = 'synthetic-cpu'
            def __call__(self, **_kw): raise RuntimeError('synthetic native failure')
        observer = inference.StreamForwardObserver(emit)
        adapter = inference.UncappedModel(Failure(), Torch(), emit, forward_observer=observer)
        with adapter.scope('generation'), self.assertRaisesRegex(RuntimeError, 'synthetic native failure'):
            adapter(input_ids=Tensor([[1]]*4), use_cache=True)
        self.assertEqual(adapter.reserved['generation'], 1)
        self.assertEqual(adapter.completed['generation'], 0)
        self.assertEqual([name for name, _ in observed], ['forward_reserved', 'forward_observer'])
        self.assertEqual(observed[-1][1]['observation']['state'], 'failed')
        self.assertEqual(observer.snapshot()['failed_rows'], 1)

    def test_tuple_cache_is_preserved_without_copy(self):
        model = Model('tuple'); adapter = inference.UncappedModel(model, Torch(), lambda *_a, **_k: None)
        with adapter.scope('generation'):
            value = adapter(input_ids=Tensor([[1]]*4), use_cache=True)
            self.assertIs(value.past_key_values, model.cache)
            value = adapter(input_ids=Tensor([[2]]*4), position_ids=Tensor([[1]]*4),
                past_key_values=value.past_key_values, use_cache=True)
            self.assertIs(value.past_key_values, model.cache)

    def test_invalid_input_shape_ids_positions_and_logits_rejected(self):
        for rows in ([[1]]*3, [[1.0]]*4, [[16]]*4, [[True]]*4, [[]]*4, [[1]*8193]*4):
            adapter = inference.UncappedModel(Model(), Torch(), lambda *_a, **_k: None)
            with self.subTest(rows=str(rows)[:60]), adapter.scope('generation'), self.assertRaises(RuntimeError):
                adapter(input_ids=Tensor(rows), use_cache=True)
            self.assertEqual(adapter.reserved['generation'], 0)
        for mode in ('nonfinite', 'wrong-vocab', 'no-cache'):
            adapter = inference.UncappedModel(Model(mode), Torch(), lambda *_a, **_k: None)
            with self.subTest(mode=mode), adapter.scope('generation'), self.assertRaises(RuntimeError):
                adapter(input_ids=Tensor([[1]]*4), use_cache=True)
            self.assertEqual(adapter.reserved['generation'], 1)
            self.assertEqual(adapter.completed['generation'], 0)
        adapter = inference.UncappedModel(Model(), Torch(), lambda *_a, **_k: None)
        for kw in ({'past_key_values': object()}, {'position_ids': Tensor([[8192]]*4)},
                   {'position_ids': Tensor([[1]]*4)}, {'position_ids': Tensor([[0], [0], [1], [0]])}):
            with self.subTest(kw=kw), adapter.scope('generation'), self.assertRaises(RuntimeError):
                adapter(input_ids=Tensor([[1]]*4), use_cache=True, **kw)

    def test_invalid_grids_and_token_sequences_remain_invalid(self):
        from tools.nvarc_native_solve_runtime import grid_key
        for grid in ([], [[1]]*31, [[1]*31], [[True]], [[10]], [[1], [1, 2]]):
            with self.subTest(grid=grid), self.assertRaises(RuntimeError): grid_key(grid)
        for score, tokens in ((float('nan'), [1, 15]), (1.7, [1, 15]), (.1, [11, 15]),
                              (.1, [1]), (.1, [1]*931+[15]), (.1, [True, 15])):
            with self.subTest(tokens=tokens[:10]), self.assertRaises(RuntimeError):
                inference.validate_sequence(score, tokens)

    @requires_linux('Real streamed evidence writer requires O_DIRECTORY and directory fsync')
    def test_chain_over_8mib_and_single_event_over_1mib_without_truncation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'large.jsonl'; binding = {'fixture': 'large-complete-stream'}
            payload = 'x'*(2*1024**2)
            with StreamEvents(path, binding) as writer:
                for index in range(5): writer.emit('fixture_payload', index=index, payload=payload)
            self.assertGreater(path.stat().st_size, 8*1024**2)
            count = 0
            for event in iter_events(path, binding):
                self.assertEqual(len(event['payload']), len(payload)); self.assertEqual(event['index'], count)
                count += 1
            self.assertEqual(count, 5)


FIXTURE = os.environ.get('IRIS_NATIVE_CODE_ONLY_DIR') or os.environ.get('IRISX_E12_NATIVE_FIXTURE')


@unittest.skipUnless(FIXTURE, 'explicit retained hash-bound native source fixture not configured')
class ExactSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in source.SOURCE_HASHES:
            shutil.copyfile(Path(FIXTURE)/name, self.root/name)
        self.original = {name: (self.root/name).read_bytes() for name in source.SOURCE_HASHES}
        self.torch = Torch()
        self.loader, self.solver, self.decoder, self.receipt = source.load_uncapped_sources(self.root, self.torch, np)

    def test_exact_original_bytes_and_only_dual_time_guard_ast_change(self):
        tree, receipt = source.adapted_tree(self.root)
        self.assertEqual(len(receipt['changes']), 1)
        self.assertEqual(receipt['changes'][0]['removed_resource_guards'],
                         ['elapsed_seconds_less_than_540', 'epoch_before_end_time'])
        self.assertEqual(receipt['changes'][0]['after_ast'], 'Constant(value=True)')
        self.assertNotEqual(receipt['original_inference_ast_digest'], receipt['adapted_inference_ast_digest'])
        self.assertEqual(self.original, {name: (self.root/name).read_bytes() for name in self.original})
        self.assertFalse(hasattr(self.solver, 'worker'))
        self.assertFalse(hasattr(self.loader.ArcDataset, 'load_replies'))
        self.assertFalse(hasattr(self.decoder, 'ArcDecoder'))
        self.assertEqual({n.name for n in tree.body if isinstance(n, ast.FunctionDef)}, source.FUNCTIONS)
        with (self.root/'solver.py').open('ab') as stream: stream.write(b'\n')
        with self.assertRaisesRegex(RuntimeError, 'original code cell differs'): source.adapted_tree(self.root)

    def test_native_dfs_ignores_old_540_seconds_and_expired_end_time(self):
        # Original timestamp jumps by >540s after prefill. Neither recursive loop
        # nor expired/None end_time may inspect it as a stop policy.
        for end_time in (None, -1000.):
            model = Model('branch'); adapter = inference.UncappedModel(model, self.torch, lambda *_a, **_k: None)
            reads = []
            def jumped_clock():
                reads.append(len(reads)*1000000.)
                return reads[-1]
            source_clock = NS(time=jumped_clock)
            with patch.dict(self.solver.turbo_dfs.__globals__, time=source_clock), adapter.scope('generation'):
                rows = self.solver.inference_turbo_dfs(adapter, [[14, 12, 10]]*4, 931,
                                                     -math.log(.2), end_time)
            self.assertEqual(len(rows), 4)
            self.assertTrue(all([tokens for _score, tokens in beams] == [[1, 15], [2, 15]]
                                for _row, beams in rows))
            self.assertEqual(adapter.completed['generation'], 3)
            self.assertEqual(reads, [0.])  # Initial metadata read only, no clock-driven DFS decisions.
        # Execute the unmodified pinned source with the same huge clock jump.
        # It demonstrates the old 540-second guard really would stop this fixture.
        from tools.nvarc_native_solve_runtime import load_sources
        _loader, original_solver, _decoder = load_sources(self.root, self.torch, np)
        reads = []
        def jumped_clock():
            reads.append(len(reads)*1000000.); return reads[-1]
        adapter = inference.UncappedModel(Model('branch'), self.torch, lambda *_a, **_k: None)
        with patch.dict(original_solver.turbo_dfs.__globals__, time=NS(time=jumped_clock)), adapter.scope('generation'):
            self.assertEqual(original_solver.inference_turbo_dfs(adapter, [[14, 12, 10]]*4, 931,
                -math.log(.2), 2000000.), [])
        self.assertEqual(adapter.completed['generation'], 1)
        self.assertEqual(self.original, {name: (self.root/name).read_bytes() for name in self.original})

    def fixture(self, *, repeats=20, fail_after=None, fail_test=None):
        challenges = {'ab12': {'train': [{'input': [[1]], 'output': [[2]]}],
                               'test': [{'input': [[3]]}, {'input': [[4]]}]}}
        atomic_json(self.root/'challenges.json', challenges)
        plan = {'format': 'irisx/stage4-uncapped-owner-editor-v1', 'run_id': 'literal-uncapped-cpu',
            'task_order': ['ab12'], 'test_counts': {'ab12': 2}, 'challenges_digest': digest(challenges),
            'model_material_digest': digest('synthetic model, no weights'), 'verification_schedule': 'interleaved'}
        engine = NS(torch=self.torch, np=np, model=Model(), tokenizer=CompactTokens())
        real_prepare = source.prepare_solver
        generations = []
        def prepare(engine, root):
            receipt = real_prepare(engine, root)
            def generate(adapter, prefixes, maximum, max_score, deadline):
                self.assertEqual(maximum, 931); self.assertEqual(max_score, -math.log(.2)); self.assertIsNone(deadline)
                if (fail_after is not None and engine.model.calls >= fail_after) or \
                        (fail_test is not None and len(generations) >= 4*fail_test):
                    raise RuntimeError('literal fixture failure')
                generations.append(len(generations))
                adapter(input_ids=Tensor(prefixes), use_cache=True)
                # Deliberate >64 synthetic-return test, not a probability-valid
                # claim about how many beams the exact native p=.2 DFS produces.
                return [(row, [(.1, [1, 15]) for _ in range(repeats)]) for row in range(4)]
            engine.solver.inference_turbo_dfs = generate
            return receipt
        components = lambda _root: (self.loader, self.decoder, CompactTokens())
        return plan, engine, prepare, components

    def solve(self, **kwargs):
        plan, engine, prepare, components = self.fixture(**kwargs)
        with patch.object(inference, 'prepare_solver', side_effect=prepare):
            record = inference.solve_task(engine, self.root, plan, 0, None)
        return plan, engine, record, components

    def test_every_sequence_above_64_consumed_with_original_transforms_and_ranker(self):
        plan, engine, record, components = self.solve(repeats=20)
        self.assertEqual(len(record['tests']), 2)
        for test in record['tests']:
            self.assertEqual(test['returned_sequences_processed'], 320)
            self.assertEqual(test['raw_unprocessed'], 0)
            self.assertEqual(test['completed_generation_batches'], 4)
            self.assertEqual(len(test['attempts']), 2)
            self.assertIsNone(test['deadline_epoch'])
            self.assertEqual(test['termination_reason'], 'all_source_batches_completed')
        with patch.object(inference, 'cpu_components', side_effect=components):
            verified = inference.verify_task(self.root, plan, 0)
        self.assertEqual(verified, record)
        self.assertTrue(record['output_qualified']); self.assertFalse(record['native_logit_replay'])
        self.assertEqual(record['accounting']['generation']['completed'], 8)
        self.assertEqual(self.original, {name: (self.root/name).read_bytes() for name in self.original})

    def test_failure_retains_earlier_commit_and_exact_failed_reservation(self):
        plan, engine, prepare, _components = self.fixture(repeats=1, fail_after=1)
        with patch.object(inference, 'prepare_solver', side_effect=prepare), self.assertRaisesRegex(RuntimeError, 'fixture failure'):
            inference.solve_task(engine, self.root, plan, 0, None)
        path = self.root/'workers/0/answer-checkpoint.json'; record = read_json(path)
        self.assertTrue(record['errors']); self.assertFalse(record['output_qualified'])
        self.assertEqual(record['tests'][0]['status'], 'not_executed')
        self.assertGreater(record['accounting']['generation']['completed'], 0)
        self.assertEqual(record['event_chain']['rows'], sum(1 for _ in iter_events(
            self.root/'workers/0/inference-events.jsonl', record['binding'])))

    def test_later_test_failure_preserves_previously_committed_answer(self):
        plan, engine, prepare, _components = self.fixture(repeats=1, fail_test=1)
        with patch.object(inference, 'prepare_solver', side_effect=prepare), self.assertRaisesRegex(RuntimeError, 'fixture failure'):
            inference.solve_task(engine, self.root, plan, 0, None)
        directory = self.root/'workers/0'; record = read_json(directory/'answer-checkpoint.json')
        self.assertEqual(record['tests'][0]['status'], 'complete')
        self.assertEqual(len(record['tests'][0]['attempts']), 2)
        self.assertEqual(record['tests'][1]['status'], 'not_executed')
        self.assertTrue(record['errors']); self.assertFalse(record['output_qualified'])
        commits = [event for event in iter_events(directory/'inference-events.jsonl', record['binding'])
                   if event['event'] == 'test_committed']
        self.assertEqual(len(commits), 1); self.assertEqual(commits[0]['result'], record['tests'][0])

    def test_exact_adapted_dfs_and_actual_verifier_run_on_cpu_tensors(self):
        plan, engine, _prepare, components = self.fixture()
        engine.model = Model('branch')
        # No replacement solver: execute the pinned adapted DFS and calc_scores.
        record = inference.solve_task(engine, self.root, plan, 0, None)
        self.assertEqual([t['returned_sequences_processed'] for t in record['tests']], [32, 32])
        self.assertEqual(record['accounting']['generation']['completed'], 24)
        with patch.object(inference, 'cpu_components', side_effect=components):
            self.assertEqual(inference.verify_task(self.root, plan, 0), record)

    def test_rehashed_wrong_candidate_readback_and_lost_observer_rejected(self):
        plan, _engine, record, components = self.solve(repeats=1)
        directory = self.root/'workers/0'; path = directory/'inference-events.jsonl'
        original = list(iter_events(path, record['binding']))
        binding_keys = set(record['binding']) | {'sequence', 'previous', 'digest', 'event'}
        mutations = (
            ('candidate_ranked', lambda e: e['score_aug'].__setitem__(0, e['score_aug'][0]+1)),
            ('verification_observed', lambda e: e['rows'][0]['query_ids'].__setitem__(0, 3)),
            ('source_sequence', lambda e: e.update(beam_index=999)),
            ('forward_observer', lambda e: e['observation'].update(batched_source_depth=999)))
        for target, mutate in mutations:
            rows = copy.deepcopy(original); mutate(next(r for r in rows if r['event'] == target))
            path.unlink()
            with StreamEvents(path, record['binding']) as writer:
                for row in rows: writer.emit(row['event'], **{k: v for k, v in row.items() if k not in binding_keys})
                changed = copy.deepcopy(record); changed['event_chain'] = {'rows': writer.sequence, 'head': writer.head}
            atomic_json(directory/'answer-checkpoint.json', changed)
            with self.subTest(target=target), patch.object(inference, 'cpu_components', side_effect=components), \
                    self.assertRaises(RuntimeError): inference.verify_task(self.root, plan, 0)

    def test_empty_source_search_is_complete_but_not_output_qualified(self):
        plan, _engine, record, components = self.solve(repeats=0)
        self.assertFalse(record['output_qualified'])
        self.assertTrue(all(t['completed_generation_batches'] == 4 and t['missing_attempts'] == 2
                            for t in record['tests']))
        with patch.object(inference, 'cpu_components', side_effect=components):
            self.assertEqual(inference.verify_task(self.root, plan, 0), record)


if __name__ == '__main__': unittest.main()
