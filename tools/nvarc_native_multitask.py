"""Finite native multi-task producer. No provider, acquisition, or evaluator IO.

Every task is a fresh process/model/Trainer; every test shares that task's epoch.
The source DFS, formatter, augmentation, inverse and score_kgmon are unchanged.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

from tools.nvarc_native_solve_runtime import (SourceModel, InferenceLimitReached,
    require, grid_key, source_batches, source_result_rows)

FORMAT = 'irisx/nvarc-native-multitask-v1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return 'sha256:' + hashlib.sha256(canonical(value)).hexdigest()


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('wb') as stream:
        stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)


def validate_challenges(challenges):
    from tools.arc_kaggle_submission import challenge_counts
    counts = challenge_counts(challenges)
    require(all(re.fullmatch(r'[A-Za-z0-9-]+',key) for key in counts),
            'unambiguous original source task IDs required')
    return counts


def public_training_material(loader,tokenizer,task_id,task):
    """Derive exact source epoch texts and completion-mask references offline.

    Native preparation must still compare its actual collator to these masks.
    Query/reply metadata is omitted; only public-demo text reaches the Trainer.
    """
    formatter=loader.QwenFormatter(tokenizer);state=loader.np.random.get_state()
    try:
        ds=loader.ArcDataset(queries={task_id:task},keys=[task_id])
        ds=ds.augment(n=16,shfl_keys=True,seed=1)
        ds=ds.cut_to_len(formatter=formatter,name='text',max_len=8192)
        texts=[{'key':r['key'],'text':r['text']} for r in ds.as_list(formatter)]
    finally:loader.np.random.set_state(state)
    rows=[]
    for i,text in enumerate(texts):
        ids=tokenizer.encode(text['text']);labels=[-100]*len(ids)
        starts=sorted(n for n,t in enumerate(ids) if t in (11,12));ends=[n for n,t in enumerate(ids) if t==15]
        require(len(starts)==len(ends) and len(starts)%2==0,'complete original chat role sequence required')
        for j,(start,end) in enumerate(zip(starts,ends)):
            require(start<end,'source chat roles differ')
            if j%2:labels[start+2:end+1]=ids[start+2:end+1]
        rows.append({'row':i,'source_view':text['key'],'input_tokens':len(ids),
            'supervised_tokens':sum(t>=0 for t in labels[1:]),'input_ids_digest':digest(ids),
            'labels_digest':digest(labels),'original_text_sha256':hashlib.sha256(text['text'].encode()).hexdigest()})
    require(len(rows)==8*16 and all(1<=r['input_tokens']<=8192 for r in rows),
            'task-derived sixteen permutations times eight D4 source rows required')
    return {'texts':texts,'rows':rows}


class Events:
    """Append-only, fsynced reservation chain with a task/run/input identity."""
    def __init__(self, path, binding):
        self.path, self.binding = Path(path), dict(binding)
        require(not self.path.exists(), 'new task event ledger required')
        self.sequence, self.head = 0, digest(self.binding)

    def emit(self, event, **details):
        row = {**self.binding, 'sequence': self.sequence, 'previous': self.head,
               'event': event, **details}
        require(all(row[key] == value for key, value in self.binding.items()), 'event binding override')
        row['digest'] = digest(row)
        with self.path.open('ab') as stream:
            stream.write(canonical(row) + b'\n'); stream.flush(); os.fsync(stream.fileno())
        self.sequence += 1; self.head = row['digest']
        return row


class EvidenceModel(SourceModel):
    """Retain verifier token log probabilities from actual native model logits.

    Never clone, crop, rebuild, or deep-copy the native cache. Mutating cache
    implementations must fail the existing deep/sibling full-prefix controls.
    """
    def __init__(self, *args, **kwargs):
        self.per_test_limits = kwargs.pop('per_test_limits', None)
        self.test_start_counts = None
        super().__init__(*args, **kwargs)
        self.verification_rows = None

    def __call__(self, *, input_ids, **kwargs):
        if self.active != 'control' and self.test_start_counts is not None:
            counts, tokens = self.test_start_counts
            if self.reserved[self.active]-counts[self.active] >= self.per_test_limits[self.active]:
                raise InferenceLimitReached('forward_limit')
            if self.input_tokens-tokens+input_ids.numel() > self.per_test_limits['input_tokens']:
                raise InferenceLimitReached('input_token_limit')
        if self.active == 'verification':
            require(self.verification_rows is not None, 'verified source rows required before scoring')
            rows = self.verification_rows
            padded = [r['query_ids'] + r['answer_ids'] for r in rows]
            width = max(map(len, padded))
            require(input_ids.tolist() == [r + [13]*(width-len(r)) for r in padded],
                    'source verifier actual model input differs')
        original_emit = self.emit
        def bound(event, **details):
            if event == 'forward_reserved': details['input_ids_digest'] = digest(input_ids.tolist())
            original_emit(event, **details)
        self.emit = bound
        try:
            value = super().__call__(input_ids=input_ids, **kwargs)
        finally:
            self.emit = original_emit
        if self.active == 'generation':
            self.emit('generation_observed', call_id=sum(self.reserved.values()),
                      last_logits=value.logits[:, -1].float().cpu().tolist())
        if self.active == 'verification':
            logp = value.logits.float().cpu().log_softmax(-1)
            evidence = []
            for i, row in enumerate(self.verification_rows):
                start = len(row['query_ids']) - 1; answer = row['answer_ids']
                selected = logp[i, start:start+len(answer)][self.torch.arange(len(answer)), answer]
                evidence.append({**row, 'answer_log_probabilities': selected.tolist(),
                                 'score': -selected.sum().item()})
            self.emit('verification_observed', call_id=sum(self.reserved.values()), rows=evidence)
        return value


def test_views(challenges, task_id, test_index, loader, tokenizer):
    """Split the real full task first, then select its real test index."""
    counts = validate_challenges(challenges)
    require(task_id in counts and type(test_index) is int and 0 <= test_index < counts[task_id],
            'exact planned task/test identity required')
    formatter = loader.QwenFormatter(tokenizer)
    require(formatter.max_new_tokens() == 931, 'original answer-token limit required')
    puzzle = loader.ArcDataset(queries={task_id: challenges[task_id]}, keys=[task_id]).split_multi_replies()
    base = task_id + '_' + str(test_index)
    state = loader.np.random.get_state()
    try:
        # Match the original RNG stream over ALL real tests, before selecting
        # one test's four batches. Selecting before augmentation would silently
        # change later tests' color permutations and demonstration orders.
        views = puzzle.augment(n=2, seed=2)
        views = views.cut_to_len(formatter=formatter, name='input', max_len=8192-931)
        views = views.change_keys([k for k in views.keys if k.split('.')[0]==base])
    finally:
        loader.np.random.set_state(state)
    puzzle = puzzle.change_keys([base])
    return base, puzzle, views, formatter, source_batches(views.keys)


def verifier_rows(puzzle, base, solution, loader, formatter, tokenizer):
    state = loader.np.random.get_state()
    try:
        ds = loader.ArcDataset(queries={base: puzzle.queries[base]},
                              replies={base: [solution]}, keys=[base])
        ds = ds.augment(seed=hash(base) % 1024**2)
        ds = ds.cut_to_len(formatter=formatter, name='input', max_len=8192-931)
        rows = ds.as_list(formatter)
        require(len(rows) == 8, 'all eight original verifier views required')
        return rows, [{'source_view': r['key'], 'query_ids': tokenizer.encode(r['input']),
                       'answer_ids': tokenizer.encode(r['reply'])} for r in rows]
    finally:
        loader.np.random.set_state(state)


def solve_test(challenges, task_id, test_index, loader, solver, decoder, tokenizer,
               adapter, *, maximum_candidates, emit):
    base, puzzle, views, formatter, batches = test_views(challenges, task_id, test_index, loader, tokenizer)
    if getattr(adapter, 'per_test_limits', None) is not None:
        adapter.test_start_counts = (dict(adapter.reserved), adapter.input_tokens)
    known, votes = {}, {}
    completed = reserved = sequences = invalid = 0; stop = None; coverage = []
    emit('test_started', test_index=test_index, base_key=base,
         source_views=views.keys, source_input_digests={k: digest(tokenizer.encode(views.get(k, formatter)['input']))
                                                     for k in views.keys})
    for batch_index, batch in enumerate(batches):
        if time.time() >= adapter.generation_deadline:
            stop = 'inference_deadline'; break
        prefixes = [tokenizer.encode(views.get(key, formatter)['input']) for key in batch]
        require(len({len(r) for r in prefixes}) == 1, 'original unpadded batch lengths differ')
        emit('generation_reserved', test_index=test_index, batch_index=batch_index, source_views=batch,
             prefix_digests=[digest(r) for r in prefixes]); reserved += 1
        source_clock = solver.inference_turbo_dfs.__globals__.get('time') if hasattr(solver.inference_turbo_dfs,'__globals__') else None
        # torch.no_grad wraps the function. The recursive turbo_dfs globals are
        # the exact source namespace, shared with the unwrapped inference body.
        namespace = getattr(solver.turbo_dfs, '__globals__', None)
        clocks=[]
        if namespace is not None:
            source_clock=namespace['time']
            class Clock:
                @staticmethod
                def time():
                    value=source_clock.time();clocks.append(value);return value
            namespace['time']=Clock
        try:
            with adapter.scope('generation'):
                result = solver.inference_turbo_dfs(adapter, prefixes, 931, -math.log(.2), adapter.generation_deadline)
        except InferenceLimitReached as error:
            stop = error.reason; break
        finally:
            if namespace is not None:namespace['time']=source_clock
        rows = source_result_rows(result)
        record = {'batch_index': batch_index, 'returned_row_ids': sorted(rows),
                  'empty_rows': 4-sum(bool(r) for r in rows.values()),
                  'source_dfs_deadline_observed': bool(clocks and
                      (clocks[-1]>=adapter.generation_deadline or clocks[-1]-clocks[0]>=540))}
        coverage.append(record); completed += 1
        # All returned beams (including invalid parses) are retained before processing.
        emit('generation_completed', test_index=test_index, batch_index=batch_index,
             source_result=result, coverage=record, source_clock_reads=clocks,
             source_end_time=adapter.generation_deadline)
        for row_index, beams in rows.items():
            key = batch[row_index]
            for score, tokens in beams:
                if sequences >= maximum_candidates:
                    stop = 'candidate_limit'; break
                sequences += 1
                require(isinstance(tokens, list) and 1 <= len(tokens) <= 931 and tokens[-1] == 15 and
                        all(type(t) is int and t in list(range(11)) for t in tokens[:-1]) and
                        math.isfinite(float(score)) and 0 <= float(score) < -math.log(.2),
                        'original EOS/beam score contract differs')
                array = formatter.convert_tokens_to_array(tokens)
                if array is None:
                    invalid += 1
                    emit('candidate_invalid', test_index=test_index, source_view=key, source_tokens=tokens)
                    continue
                solution = loader.ArcDataset.invert_mod(array, key, inv_perm=True).tolist()
                identity = grid_key(solution)
                emit('candidate_parsed', test_index=test_index, source_view=key, source_tokens=tokens,
                     candidate_grid=solution, beam_score=float(score), already_verified=identity in known)
                if identity not in known:
                    verify, bindings = verifier_rows(puzzle, base, solution, loader, formatter, tokenizer)
                    scores = []; calls = []
                    try:
                        with adapter.scope('verification'):
                            for offset in (0, 4):
                                adapter.verification_rows = bindings[offset:offset+4]
                                scores += solver.calc_scores([r['input'] for r in verify[offset:offset+4]],
                                    [r['reply'] for r in verify[offset:offset+4]], tokenizer, adapter)
                                calls.append(sum(adapter.reserved.values()))
                    except InferenceLimitReached as error:
                        stop = error.reason; break
                    finally:
                        adapter.verification_rows = None
                    require(len(scores) == 8 and all(math.isfinite(float(s)) and s >= 0 for s in scores),
                            'finite eight-view verification required')
                    known[identity] = ([float(s) for s in scores], calls)
                scores, calls = known[identity]
                votes[str(len(votes))] = {'beam_score': float(score), 'score_aug': scores,
                                         'solution': loader.np.asarray(solution)}
                emit('candidate_ranked', test_index=test_index, source_view=key, source_tokens=tokens,
                     candidate_grid=solution, beam_score=float(score), score_aug=scores, verification_call_ids=calls)
            if stop: break
        if not stop and record['source_dfs_deadline_observed']:stop='source_dfs_deadline'
        if stop: break
    grids = [g.tolist() for g in decoder.score_kgmon(votes)]
    require(len(grids) == len({grid_key(g) for g in grids}) == len(known), 'original vote/ranking closure differs')
    result = {'test_index': test_index, 'base_key': base, 'ranked_grids': grids, 'attempts': grids[:2],
              'missing_attempts': max(0, 2-len(grids)), 'reserved_generation_batches': reserved,
              'completed_generation_batches': completed, 'source_view_denominator': 16,
              'unfinished_source_views': 4*(reserved-completed), 'undispatched_source_views': 16-4*reserved,
              'returned_sequences_processed': sequences, 'invalid_candidates': invalid, 'coverage': coverage,
              'termination_reason': stop or 'all_source_batches_completed',
              'status': ('complete' if len(grids) >= 2 else 'missing-candidate') if not stop else
                        ('partial-candidates' if grids else 'budget_stop'),
              'native_complete': completed == 4 and bool(grids) and stop is None,
              'search_exhaustiveness_claim': False,
              'correctness_scored': False}
    emit('test_terminal', result=result)
    return result


def failure_status(error):
    if isinstance(error, InferenceLimitReached): return 'budget_stop'
    if isinstance(error, TimeoutError): return 'timeout'
    if isinstance(error, (KeyboardInterrupt, SystemExit)): return 'interrupted_pending'
    if 'out of memory' in str(error).lower(): return 'oom'
    return 'failed'


def run_task_tests(challenges, task_id, solve, checkpoint):
    """Commit each independent completed test before dispatching the next.

    A failure can preserve earlier checkpointed tests, never the failed test's
    uncommitted votes. The full denominator is always explicit.
    """
    counts = validate_challenges(challenges)
    tests = [{'test_index': i, 'status': 'not_executed', 'attempts': [], 'missing_attempts': 2}
             for i in range(counts[task_id])]
    failure = None
    for i in range(len(tests)):
        try:
            tests[i] = solve(i); checkpoint(tests)
        except BaseException as error:
            tests[i] = {'test_index': i, 'status': failure_status(error), 'attempts': [], 'missing_attempts': 2}
            failure = {'error_type': type(error).__name__, 'error_message': str(error)[:1200]}
            checkpoint(tests); break
        if tests[i]['termination_reason'] != 'all_source_batches_completed': break
    return tests, failure


@contextmanager
def training_deadline(budget, deadline):
    """Stop before Trainer microstep reservation; existing EpochBudget reserves
    every training forward/optimizer call before entry and retains failures.
    """
    original = budget.trainer.training_step
    def guarded(*args, **kwargs):
        if time.time() >= deadline: raise InferenceLimitReached('training_deadline')
        return original(*args, **kwargs)
    budget.trainer.training_step = guarded
    try:
        with budget.installed(): yield budget
    finally:
        budget.trainer.training_step = original
