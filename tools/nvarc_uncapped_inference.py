# Original portions/source flow: sorokin's Kaggle notebook Version10,
# arc2-qwen3-unsloth-flash-lora-batch4-queue, Apache-2.0.
# https://www.kaggle.com/code/sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue
# IRIS-X adaptations: uncapped resource policy, streamed evidence and strict replay.
# See notices/NOTICE-native.txt and notices/LICENSE-Apache-2.0.txt.
"""One uncapped native search per real test, with interleaved eight-view scoring.

No time, forward, input-token, candidate, event-byte or observer-row budget drives
this path. None is the no-cap policy. The original scientific p=.2 DFS, sixteen
views/four batches, 8192-token model context, 931-token answer grammar, inverse
transforms, score_kgmon and two displayed guesses remain. This is not infinite
compute: finite physical RAM/VRAM/disk, recursion stack, provider session limits
and the original DFS's in-memory suffixes/votes remain actual constraints.

Evidence streams incrementally; only live call/readback state is retained by the
adapter/observer. Scientific deduplication/voting retains candidates as required
by the original ranker. CPU verification checks structure, source transforms,
input bindings, retained score readbacks and accounting. It does NOT recreate
native logits, prove exhaustive search, score correctness or confer authority.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
import math
from pathlib import Path
import time
from types import SimpleNamespace

from tools.nvarc_native_multitask import digest, require, test_views, verifier_rows, validate_challenges
from tools.nvarc_native_solve_runtime import grid_key, source_result_rows
from tools.nvarc_native_submission import reject_truth
from tools.nvarc_uncapped_source import prepare_solver, adapted_tree, load_uncapped_sources
from tools.nvarc_uncapped_artifacts import StreamEvents, atomic_json, read_json, iter_events, full_diagnostic

PHASES = ('generation', 'verification')
MAX_SCORE = -math.log(.2)
POLICY = {'generation_forwards': None, 'verification_forwards': None, 'input_tokens': None,
    'processed_candidates': None, 'generation_seconds': None, 'verification_seconds': None,
    'source_dfs_seconds': None, 'observer_rows': None, 'event_bytes': None, 'ledger_bytes': None}
SCIENCE = {'dfs_probability_floor': .2, 'verification_schedule': 'interleaved',
    'source_views': 16, 'source_batches': 4, 'views_per_batch': 4,
    'verifier_views': 8, 'context_tokens': 8192, 'answer_tokens': 931, 'displayed_guesses': 2,
    'ranking_policy': 'unchanged_source_score_kgmon'}

EVENT_FIELDS = {
    'test_started': {'base_key', 'source_views', 'source_input_digests', 'started_epoch',
                     'resource_policy', 'scientific_contract'},
    'generation_reserved': {'batch_index', 'source_views', 'prefix_digests'},
    'generation_completed': {'batch_index', 'raw_returned', 'returned_rows', 'coverage',
                             'elapsed_host_seconds', 'source_end_time'},
    'source_sequence': {'batch_index', 'row_index', 'beam_index', 'source_view', 'beam_score',
                        'source_tokens', 'sequence_index'},
    'forward_reserved': {'call_id', 'phase', 'batch_shape', 'physical_input_tokens', 'cached',
                         'position_start', 'position_end', 'input_ids_digest'},
    'forward_completed': {'call_id', 'phase', 'output_contract'},
    'forward_observer': {'observation'},
    'verification_observed': {'call_id', 'rows'},
    'candidate_invalid': {'source_view', 'source_tokens'},
    'candidate_parsed': {'source_view', 'source_tokens', 'candidate_grid', 'beam_score', 'already_verified'},
    'candidate_ranked': {'source_view', 'source_tokens', 'candidate_grid', 'beam_score', 'score_aug',
                         'verification_call_ids'},
    'test_terminal': {'result'}, 'test_committed': {'result'}}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def task_binding(plan, challenges, rank):
    require(type(plan) is dict and plan.get('format') == 'irisx/stage4-uncapped-owner-editor-v1',
            'distinct uncapped plan required')
    require(plan.get('verification_schedule') == 'interleaved', 'interleaved verification required')
    require(type(plan.get('task_order')) is list and len(set(plan['task_order'])) == len(plan['task_order']) and
        all(type(key) is str for key in plan['task_order']), 'distinct planned task order required')
    require(type(rank) is int and 0 <= rank < len(plan['task_order']), 'exact task rank required')
    counts = validate_challenges(challenges)
    key = plan['task_order'][rank]
    require(digest(challenges) == plan['challenges_digest'] and digest(counts) == digest(plan['test_counts']) and
        set(plan['task_order']) == set(counts),
            'exact visible public task/test binding required')
    return {'run_id': plan['run_id'], 'plan_digest': digest(plan), 'rank': rank, 'task_id': key,
        'task_digest': digest(challenges[key]), 'challenges_digest': digest(challenges),
        'model_material_digest': plan['model_material_digest'], 'resource_policy_digest': digest(POLICY),
        'scientific_contract_digest': digest(SCIENCE)}


class StreamForwardObserver:
    """One live host-only observation; completed rows go directly to the ledger."""
    def __init__(self, emit, *, clock=time.monotonic):
        self.emit, self.clock = emit, clock
        self.test_index = None
        self.observed_rows = self.failed_rows = 0
        self.prefix_lengths, self.last_depths = {}, {}

    def begin_test(self, index):
        require(type(index) is int and index >= 0, 'observer test index required')
        self.test_index = index
        self.prefix_lengths.clear(); self.last_depths.clear()

    def reserve(self, call_id, phase, shape, cached, start, end, entered):
        depth = backtrack = None
        if phase == 'generation':
            if not cached:
                self.prefix_lengths[phase] = shape[1]
                self.last_depths.pop(phase, None)
                depth, backtrack = 0, False
            elif phase in self.prefix_lengths:
                depth = start - self.prefix_lengths[phase] + 1
                previous = self.last_depths.get(phase)
                backtrack = previous is not None and depth <= previous
                self.last_depths[phase] = depth
        return {'call_id': call_id, 'phase': phase, 'batch_shape': list(shape), 'cached': cached,
            'position_start': start, 'position_end': end, 'batched_source_depth': depth,
            'position_backtrack': backtrack, 'state': 'reserved', 'error_type': None,
            'host_monotonic': {'call_entered': entered, 'reservation': self.clock(),
                'model_entered': None, 'model_returned': None, 'guard_completed': None,
                'call_finished': None}}

    def mark(self, row, stage):
        require(stage in ('model_entered', 'model_returned', 'guard_completed'), 'known host stage required')
        row['host_monotonic'][stage] = self.clock()

    def finish(self, row, error=None):
        row['host_monotonic']['call_finished'] = self.clock()
        row['state'] = 'complete' if error is None else 'failed'
        row['error_type'] = None if error is None else type(error).__name__
        self.emit('forward_observer', observation=row)
        self.observed_rows += 1
        self.failed_rows += int(error is not None)

    def snapshot(self):
        return {'format': 'irisx/uncapped-streaming-forward-observer-v1',
            'clock': 'time.monotonic host wall seconds', 'maximum_rows': None,
            'observed_rows': self.observed_rows, 'failed_rows': self.failed_rows,
            'truncated': False, 'dropped_rows': 0, 'added_device_synchronizations': 0,
            'added_tensor_readbacks': 0, 'per_forward_file_writes': True,
            'row_storage': 'inference-events.jsonl forward_observer events',
            'timing_boundary': 'model adapter only; excludes later verifier NLL readback',
            'gpu_kernel_timing_attestation': False, 'native_numerical_replay': False}


class UncappedModel:
    """Original checked model interface with resource stops absent, counts intact."""
    def __init__(self, model, torch, emit, *, forward_observer=None):
        self.model, self.torch, self.emit = model, torch, emit
        self.device = model.device
        self.forward_limits = {phase: None for phase in PHASES}
        self.input_token_limit = self.generation_deadline = self.verification_deadline = None
        self.context_tokens = 8192
        self.reserved = {phase: 0 for phase in PHASES}
        self.completed = dict(self.reserved)
        self.input_by_phase = dict(self.reserved)
        self.completed_input_by_phase = dict(self.reserved)
        self.input_tokens = 0
        self.telemetry = self.active = self.verification_rows = self.last_verification = None
        self.forward_observer = forward_observer

    def profile(self, name):
        return nullcontext() if self.telemetry is None else self.telemetry.detail(name)

    @contextmanager
    def scope(self, phase):
        require(phase in PHASES and self.active is None, 'one known inference phase required')
        self.active = phase
        try:
            yield self
        finally:
            self.active = None

    def __call__(self, *, input_ids, **kwargs):
        observer = self.forward_observer
        entered = None if observer is None else observer.clock()
        phase = self.active
        require(phase in PHASES, 'unreserved native model entry')
        shape = list(input_ids.shape)
        require(len(shape) == 2 and shape[0] == 4 and 1 <= shape[1] <= 8192,
                'fixed four-view batch and model context required')
        ids = input_ids.tolist()
        require(type(ids) is list and len(ids) == 4 and all(type(row) is list and len(row) == shape[1]
            and all(type(v) is int and 0 <= v < 16 for v in row) for row in ids),
            'exact native vocabulary integer input tensor required')
        rows = self.verification_rows
        if phase == 'verification':
            require(type(rows) is list and len(rows) == 4, 'four actual verifier rows required')
            padded = [r['query_ids'] + r['answer_ids'] for r in rows]
            width = max(map(len, padded))
            require(ids == [r + [13]*(width-len(r)) for r in padded], 'actual verifier input differs')
        cached = kwargs.get('past_key_values') is not None
        positions = kwargs.get('position_ids')
        if positions is None:
            require(not cached, 'cached native call needs explicit source positions')
            positions = self.torch.arange(shape[1], device=self.device).unsqueeze(0).expand(4, -1).contiguous()
            kwargs['position_ids'] = positions
        with self.profile('positions_cpu_copy'):
            values = positions.detach().cpu().tolist()
        require(len(values) == 4 and all(len(row) == shape[1] and
            all(type(v) is int and 0 <= v < 8192 for v in row) for row in values),
            'explicit model-context position IDs required')
        require(all(row == list(range(values[0][0], values[0][0]+shape[1])) for row in values),
            'one contiguous position range across all four views required')
        require(cached or all(row == list(range(shape[1])) for row in values),
                'prefill positions must start at zero')
        require(type(kwargs.get('use_cache')) is bool and kwargs.get('return_dict', True) is True,
                'explicit native cache/output policy required')
        kwargs['return_dict'] = True
        tokens = shape[0] * shape[1]
        self.reserved[phase] += 1; self.input_tokens += tokens; self.input_by_phase[phase] += tokens
        call = sum(self.reserved.values())
        observation = None if observer is None else observer.reserve(
            call, phase, shape, cached, values[0][0], values[0][-1], entered)
        try:
            self.emit('forward_reserved', call_id=call, phase=phase, batch_shape=shape,
                physical_input_tokens=tokens, cached=cached, position_start=values[0][0],
                position_end=values[0][-1], input_ids_digest=digest(ids))
            if observer is not None: observer.mark(observation, 'model_entered')
            with self.profile('model_entry_host_wall'):
                output = self.model(input_ids=input_ids, **kwargs)
            if observer is not None: observer.mark(observation, 'model_returned')
            if isinstance(output, tuple):
                require(len(output) >= (2 if kwargs['use_cache'] else 1), 'native tuple requested outputs missing')
                logits, cache = output[0], output[1] if len(output) >= 2 else None
                contract = 'tuple-logits-cache'
            else:
                logits, cache = output.logits, getattr(output, 'past_key_values', None)
                contract = 'model-output-logits-cache'
            with self.profile('finite_logits_guard'):
                require(list(logits.shape) == [4, shape[1], 16] and
                    bool(self.torch.isfinite(logits).all().item()), 'finite exact sixteen-row native logits required')
            if observer is not None: observer.mark(observation, 'guard_completed')
            require(kwargs['use_cache'] is False or cache is not None, 'native cache result missing')
            self.completed[phase] += 1; self.completed_input_by_phase[phase] += tokens
            self.emit('forward_completed', call_id=call, phase=phase, output_contract=contract)
        except BaseException as error:
            if observer is not None: observer.finish(observation, error)
            raise
        if observer is not None: observer.finish(observation)
        value = SimpleNamespace(logits=logits, past_key_values=cache)
        if phase == 'verification':
            with self.profile('verifier_readback'):
                logp = logits.float().cpu().log_softmax(-1)
                observed = []
                for n, row in enumerate(rows):
                    answer = row['answer_ids']; start = len(row['query_ids'])-1
                    score = -logp[n, start:start+len(answer)][self.torch.arange(len(answer)), answer].sum().item()
                    require(finite(score) and score >= 0, 'finite nonnegative actual verifier NLL required')
                    observed.append(dict(row, query_digest=digest(row['query_ids']),
                                         answer_digest=digest(answer), score=score))
            self.last_verification = {'call_id': call, 'rows': observed}
            self.emit('verification_observed', **self.last_verification)
        return value


def adapter_counts(adapter):
    return {phase: {'reserved': adapter.reserved[phase], 'completed': adapter.completed[phase],
        'input_tokens_reserved': adapter.input_by_phase[phase],
        'input_tokens_completed': adapter.completed_input_by_phase[phase]} for phase in PHASES}


def validate_sequence(score, tokens):
    require(type(tokens) is list and 1 <= len(tokens) <= 931 and tokens[-1] == 15 and
        all(type(t) is int and 0 <= t <= 10 for t in tokens[:-1]) and
        finite(score) and 0 <= score < MAX_SCORE, 'original EOS/beam score contract differs')


def solve_test(challenges, task_id, test_index, loader, solver, decoder, tokenizer, adapter, *, emit):
    """Process every returned sequence; verify its first unique grid immediately."""
    base, puzzle, views, formatter, batches = test_views(challenges, task_id, test_index, loader, tokenizer)
    telemetry = adapter.telemetry
    def phase(name):
        return nullcontext() if telemetry is None else telemetry.scope(name)
    known, votes, coverage = {}, {}, []
    sequences = invalid = raw = 0
    start = time.time(); monotonic = time.monotonic()
    emit('test_started', base_key=base, source_views=views.keys,
        source_input_digests={k: digest(tokenizer.encode(views.get(k, formatter)['input'])) for k in views.keys},
        started_epoch=start, resource_policy=POLICY, scientific_contract=SCIENCE)
    for batch_index, batch in enumerate(batches):
        prefixes = [tokenizer.encode(views.get(key, formatter)['input']) for key in batch]
        require(len({len(row) for row in prefixes}) == 1, 'original unpadded batch lengths differ')
        emit('generation_reserved', batch_index=batch_index, source_views=batch,
             prefix_digests=[digest(row) for row in prefixes])
        started = time.monotonic()
        with phase('generation'), adapter.scope('generation'):
            result = solver.inference_turbo_dfs(adapter, prefixes, 931, MAX_SCORE, None)
        rows = source_result_rows(result)
        count = sum(len(beams) for beams in rows.values()); raw += count
        item = {'batch_index': batch_index, 'returned_row_ids': sorted(rows),
                'empty_rows': 4-sum(bool(beams) for beams in rows.values())}
        coverage.append(item)
        emit('generation_completed', batch_index=batch_index, raw_returned=count,
            returned_rows=[{'row_index': n, 'sequences': len(beams)} for n, beams in rows.items()],
            coverage=item, elapsed_host_seconds=time.monotonic()-started, source_end_time=None)
        for row_index, beams in rows.items():
            key = batch[row_index]
            for beam_index, (score, tokens) in enumerate(beams):
                require(finite(score), 'finite native beam score required')
                score = float(score)
                emit('source_sequence', batch_index=batch_index, row_index=row_index,
                    beam_index=beam_index, source_view=key, beam_score=score, source_tokens=tokens,
                    sequence_index=sequences)
                validate_sequence(score, tokens); sequences += 1
                with phase('parse_dedup'):
                    array = formatter.convert_tokens_to_array(tokens)
                    if array is None:
                        invalid += 1
                        emit('candidate_invalid', source_view=key, source_tokens=tokens)
                        continue
                    solution = loader.ArcDataset.invert_mod(array, key, inv_perm=True).tolist()
                    identity = grid_key(solution)
                    emit('candidate_parsed', source_view=key, source_tokens=tokens, candidate_grid=solution,
                        beam_score=score, already_verified=identity in known)
                if identity not in known:
                    verify, bindings = verifier_rows(puzzle, base, solution, loader, formatter, tokenizer)
                    scores, calls = [], []
                    try:
                        with phase('verification'), adapter.scope('verification'):
                            for offset in (0, 4):
                                adapter.verification_rows = bindings[offset:offset+4]
                                part = solver.calc_scores([r['input'] for r in verify[offset:offset+4]],
                                    [r['reply'] for r in verify[offset:offset+4]], tokenizer, adapter)
                                readback = adapter.last_verification
                                require(readback is not None and len(part) == 4 and
                                    [float(s) for s in part] == [r['score'] for r in readback['rows']],
                                    'source scores differ from actual verifier readback')
                                scores.extend(float(s) for s in part); calls.append(readback['call_id'])
                    finally:
                        adapter.verification_rows = adapter.last_verification = None
                    require(len(scores) == 8 and all(finite(s) and s >= 0 for s in scores),
                            'finite eight-view verification required')
                    known[identity] = (scores, calls)
                scores, calls = known[identity]
                votes[str(len(votes))] = {'beam_score': score, 'score_aug': scores,
                                         'solution': loader.np.asarray(solution)}
                emit('candidate_ranked', source_view=key, source_tokens=tokens, candidate_grid=solution,
                    beam_score=score, score_aug=scores, verification_call_ids=calls)
    with phase('ranking'):
        grids = [g.tolist() for g in decoder.score_kgmon(votes)]
    require(len(grids) == len({grid_key(g) for g in grids}) == len(known),
            'original inverse/deduplication/ranking closure differs')
    require(sequences == raw, 'every native returned sequence must be processed')
    result = {'test_index': test_index, 'base_key': base, 'ranked_grids': grids, 'attempts': grids[:2],
        'missing_attempts': max(0, 2-len(grids)), 'reserved_generation_batches': 4,
        'completed_generation_batches': 4, 'source_view_denominator': 16, 'unfinished_source_views': 0,
        'undispatched_source_views': 0, 'returned_sequences_processed': sequences, 'raw_returned': raw,
        'raw_unprocessed': 0, 'invalid_candidates': invalid, 'unique_candidates': len(known),
        'coverage': coverage, 'termination_reason': 'all_source_batches_completed',
        'status': 'complete' if len(grids) >= 2 else 'missing-candidate',
        'native_complete': bool(grids), 'output_qualified': bool(grids),
        'candidate_path_exercised': bool(grids), 'search_exhaustiveness_claim': False,
        'correctness_scored': False, 'native_logit_replay': False, 'started_epoch': start,
        'finished_epoch': time.time(), 'elapsed_host_seconds': time.monotonic()-monotonic,
        'deadline_epoch': None, 'resource_policy': dict(POLICY)}
    emit('test_terminal', result=result)
    return result


def solve_task(engine, root, plan, rank, telemetry, directory=None):
    """Durably commit each test; errors preserve earlier results and reservations."""
    root = Path(root); output = Path(directory) if directory is not None else root/'workers'/str(rank)
    output.mkdir(parents=True, exist_ok=True)
    challenges = read_json(root/'challenges.json')
    bound = task_binding(plan, challenges, rank)
    receipt = prepare_solver(engine, root)
    atomic_json(output/'uncapped-source-adaptation.json', receipt)
    current = None
    events = StreamEvents(output/'inference-events.jsonl', bound)
    def emit(event, **details):
        events.emit(event, test_index=current, **details)
    observer = StreamForwardObserver(emit)
    adapter = UncappedModel(engine.model, engine.torch, emit, forward_observer=observer)
    adapter.telemetry = telemetry
    record = {'binding': bound, 'tests': [{'test_index': n, 'status': 'not_executed',
        'attempts': [], 'missing_attempts': 2} for n in range(plan['test_counts'][bound['task_id']])],
        'accounting': None, 'errors': [], 'output_qualified': False, 'correctness_scored': False,
        'promotion': False, 'source_adaptation_digest': digest(receipt), 'resource_policy': dict(POLICY),
        'scientific_contract': dict(SCIENCE), 'evidence_kind': 'structural-events-and-verifier-readback',
        'native_logit_replay': False, 'event_chain': None}
    def checkpoint():
        events.flush()
        record['accounting'] = adapter_counts(adapter)
        record['event_chain'] = {'rows': events.sequence, 'head': events.head}
        atomic_json(output/'inference-forward-diagnostics.json', dict(observer.snapshot(), binding=bound))
        atomic_json(output/'answer-checkpoint.json', record)
    checkpoint()
    try:
        for current in range(len(record['tests'])):
            observer.begin_test(current)
            with engine.torch.inference_mode():
                result = solve_test(challenges, bound['task_id'], current, engine.loader, engine.solver,
                    engine.decoder, engine.tokenizer, adapter, emit=emit)
            record['tests'][current] = result
            emit('test_committed', result=result)
            checkpoint()
        record['output_qualified'] = all(test['output_qualified'] for test in record['tests'])
    except BaseException as error:
        record['errors'].append(full_diagnostic(error, 'uncapped-inference'))
        raise
    finally:
        try: checkpoint()
        finally: events.close()
    return record


def cpu_components(root):
    """Original pinned source plus shipped tokenizer; no Torch import or model call."""
    import numpy as np
    from tokenizers import Tokenizer
    loader, _solver, decoder, _receipt = load_uncapped_sources(
        root, SimpleNamespace(no_grad=lambda: lambda function: function), np)
    native = Tokenizer.from_file(str(Path(root)/'verified-tokenizer.json'))
    class Tokens:
        def encode(self, text): return native.encode(text).ids
        def decode(self, values): return native.decode(values, skip_special_tokens=False)
    return loader, decoder, Tokens()


def _same(value, expected, message):
    require(type(value) is type(expected) and digest(value) == digest(expected), message)


def verify_task(root, plan, rank, directory=None):
    """Streaming CPU structural/source/readback verification, never logit replay.

    The event chain detects mutation/truncation relative to its retained seal; it
    is not a hardware attestation. Only successfully committed complete tasks
    qualify. Interrupted evidence remains available but cannot pass this check.
    """
    root = Path(root); output = Path(directory) if directory is not None else root/'workers'/str(rank)
    challenges = read_json(root/'challenges.json'); bound = task_binding(plan, challenges, rank)
    record = read_json(output/'answer-checkpoint.json'); reject_truth(record)
    require(type(record) is dict and set(record) == {'binding', 'tests', 'accounting', 'errors',
        'output_qualified', 'correctness_scored', 'promotion', 'source_adaptation_digest', 'resource_policy',
        'scientific_contract', 'evidence_kind', 'native_logit_replay', 'event_chain'},
        'closed uncapped answer checkpoint required')
    _same(record['binding'], bound, 'exact uncapped task/run binding required')
    require(record['errors'] == [] and record['correctness_scored'] is record['promotion'] is False and
        record['native_logit_replay'] is False and
        record['evidence_kind'] == 'structural-events-and-verifier-readback',
        'successful structural-only inference evidence required')
    _same(record['resource_policy'], POLICY, 'uncapped resource policy differs')
    _same(record['scientific_contract'], SCIENCE, 'original scientific contract differs')
    _tree, receipt = adapted_tree(root)
    _same(read_json(output/'uncapped-source-adaptation.json'), receipt, 'exact source adaptation receipt required')
    require(record['source_adaptation_digest'] == digest(receipt), 'source adaptation digest differs')
    loader, decoder, tokenizer = cpu_components(root)
    total = {phase: {'reserved': 0, 'completed': 0, 'input_tokens_reserved': 0,
                     'input_tokens_completed': 0} for phase in PHASES}
    count = plan['test_counts'][bound['task_id']]
    require(type(record['tests']) is list and len(record['tests']) == count, 'all real tests required')
    index = 0; local = None; call = None; source = None; candidate = None; terminal = None
    observer_count = event_count = 0; head = digest(bound)
    names = set(EVENT_FIELDS)
    shared_fields = set(bound) | {'sequence', 'previous', 'digest', 'event', 'test_index'}
    for event in iter_events(output/'inference-events.jsonl', bound):
        event_count += 1; head = event['digest']; name = event['event']
        require(name in names and type(event.get('test_index')) is int and event['test_index'] == index,
                'known ordered real-test event required')
        require(set(event) == shared_fields | EVENT_FIELDS[name], 'closed inference event schema required')
        for field in ('call_id', 'batch_index', 'row_index', 'beam_index', 'sequence_index',
                      'raw_returned', 'physical_input_tokens', 'position_start', 'position_end'):
            if field in event: require(type(event[field]) is int, 'exact integer '+field+' required')
        if 'beam_score' in event: require(type(event['beam_score']) is float, 'native float beam score required')
        if name == 'test_started':
            require(local is None and index < count, 'one search per real test required')
            base, puzzle, views, formatter, batches = test_views(challenges, bound['task_id'], index, loader, tokenizer)
            require(event['base_key'] == base and event['source_views'] == views.keys and
                event['source_input_digests'] == {k: digest(tokenizer.encode(views.get(k, formatter)['input']))
                                                for k in views.keys}, 'source views/prefixes differ')
            _same(event['resource_policy'], POLICY, 'event resource policy differs')
            _same(event['scientific_contract'], SCIENCE, 'event scientific contract differs')
            require(finite(event['started_epoch']), 'finite honest start observation required')
            local = {'base': base, 'puzzle': puzzle, 'views': views, 'formatter': formatter,
                'batches': batches, 'batch': -1, 'generation_open': False, 'coverage': [],
                'known': {}, 'votes': {}, 'processed': 0, 'invalid': 0, 'raw': 0,
                'remaining_rows': [], 'row_offset': 0, 'row_used': 0, 'generation_calls': 0,
                'started_epoch': event['started_epoch'], 'prefix_length': None, 'last_depth': None}
            continue
        require(local is not None, 'test must start before its evidence')
        if terminal is not None:
            require(name == 'test_committed', 'terminal result must be committed next')
        if name == 'generation_reserved':
            require(call is None and source is None and candidate is None and
                not local['generation_open'] and local['processed'] == local['raw'] and
                event['batch_index'] == local['batch']+1 and event['batch_index'] < 4,
                'all previous returned candidates must finish before next source batch')
            local['batch'] += 1; batch = local['batches'][local['batch']]
            prefixes = [tokenizer.encode(local['views'].get(k, local['formatter'])['input']) for k in batch]
            require(event['source_views'] == batch and event['prefix_digests'] == [digest(r) for r in prefixes],
                    'ordered original generation batch differs')
            local.update(generation_open=True, generation_calls=0, prefixes=prefixes)
        elif name == 'forward_reserved':
            phase = event['phase']; shape = event['batch_shape']
            require(call is None and phase in PHASES and type(event['call_id']) is int and
                event['call_id'] == sum(v['reserved'] for v in total.values())+1 and
                type(shape) is list and len(shape) == 2 and type(shape[0]) is type(shape[1]) is int and
                shape[0] == 4 and 1 <= shape[1] <= 8192 and type(event['physical_input_tokens']) is int and
                event['physical_input_tokens'] == 4*shape[1] and type(event['cached']) is bool and
                type(event['position_start']) is type(event['position_end']) is int and
                0 <= event['position_start'] <= event['position_end'] < 8192 and
                event['position_end']-event['position_start']+1 == shape[1],
                'one exact valid counted native forward required')
            if not event['cached']: require(event['position_start'] == 0, 'prefill starts at zero')
            if phase == 'generation':
                require(local['generation_open'] and candidate is None and source is None,
                        'generation must run inside its source batch')
                if local['generation_calls'] == 0:
                    require(event['cached'] is False and event['input_ids_digest'] == digest(local['prefixes']) and
                        shape == [4, len(local['prefixes'][0])], 'first generation prefill source differs')
                    local['prefix_length'] = shape[1]; local['last_depth'] = None
                else:
                    require(event['cached'] is True and shape[1] == 1,
                            'original DFS uses cached one-token descendants')
                local['generation_calls'] += 1
            else:
                require(not local['generation_open'] and candidate is not None and not candidate['duplicate'] and
                    candidate['verified_views'] in (0, 4) and event['cached'] is False,
                    'interleaved fresh candidate verification required')
                offset = candidate['verified_views']; rows = candidate['bindings'][offset:offset+4]
                tokens = [r['query_ids']+r['answer_ids'] for r in rows]; width = max(map(len, tokens))
                expected = [r+[13]*(width-len(r)) for r in tokens]
                require(event['input_ids_digest'] == digest(expected) and shape == [4, width],
                        'actual padded verifier input binding differs')
            total[phase]['reserved'] += 1; total[phase]['input_tokens_reserved'] += event['physical_input_tokens']
            call = dict(event, state='reserved')
        elif name == 'forward_completed':
            require(call is not None and call['state'] == 'reserved' and
                event['call_id'] == call['call_id'] and event['phase'] == call['phase'] and
                event['output_contract'] in ('tuple-logits-cache', 'model-output-logits-cache'),
                'native forward completion without exact reservation')
            total[call['phase']]['completed'] += 1
            total[call['phase']]['input_tokens_completed'] += call['physical_input_tokens']
            call['state'] = 'completed'
        elif name == 'forward_observer':
            observation = event['observation']
            require(call is not None and call['state'] == 'completed' and
                set(observation) == {'call_id', 'phase', 'batch_shape', 'cached', 'position_start', 'position_end',
                    'batched_source_depth', 'position_backtrack', 'state', 'error_type', 'host_monotonic'} and
                all(digest(observation.get(k)) == digest(call[k]) for k in ('call_id', 'phase', 'batch_shape', 'cached',
                    'position_start', 'position_end')) and observation['state'] == 'complete' and
                observation['error_type'] is None, 'one completed untruncated forward observation required')
            stamps = observation['host_monotonic']
            order = ('call_entered', 'reservation', 'model_entered', 'model_returned', 'guard_completed', 'call_finished')
            require(set(stamps) == set(order) and all(finite(stamps[k]) for k in order) and
                [stamps[k] for k in order] == sorted(stamps[k] for k in order),
                'finite ordered host observation boundaries required')
            depth = backtrack = None
            if call['phase'] == 'generation':
                if not call['cached']: depth, backtrack = 0, False
                else:
                    depth = call['position_start']-local['prefix_length']+1
                    previous = local['last_depth']; backtrack = previous is not None and depth <= previous
                    local['last_depth'] = depth
            require(observation['batched_source_depth'] == depth and observation['position_backtrack'] is backtrack,
                    'source-depth host observation differs')
            observer_count += 1
            if call['phase'] == 'generation': call = None
            else: call['state'] = 'observed'
        elif name == 'verification_observed':
            require(call is not None and call['state'] == 'observed' and call['phase'] == 'verification' and
                event['call_id'] == call['call_id'], 'readback requires its actual completed verifier call')
            offset = candidate['verified_views']; expected = candidate['bindings'][offset:offset+4]
            rows = event['rows']
            require(type(rows) is list and len(rows) == 4, 'four verifier row readbacks required')
            for row, original in zip(rows, expected):
                require(set(row) == {'source_view', 'query_ids', 'answer_ids', 'query_digest', 'answer_digest', 'score'} and
                    digest({k: row[k] for k in ('source_view', 'query_ids', 'answer_ids')}) == digest(original) and
                    row['query_digest'] == digest(original['query_ids']) and
                    row['answer_digest'] == digest(original['answer_ids']) and
                    type(row['score']) is float and finite(row['score']) and row['score'] >= 0,
                    'source-derived finite verifier readback differs')
            candidate['scores'].extend(row['score'] for row in rows)
            candidate['calls'].append(call['call_id']); candidate['verified_views'] += 4; call = None
        elif name == 'generation_completed':
            require(call is None and local['generation_open'] and local['generation_calls'] > 0 and
                event['batch_index'] == local['batch'] and event['source_end_time'] is None and
                finite(event['elapsed_host_seconds']) and event['elapsed_host_seconds'] >= 0,
                'native source batch completion and no-deadline receipt required')
            rows = event['returned_rows']
            require(type(rows) is list and len(rows) <= 4 and all(type(r) is dict and
                set(r) == {'row_index', 'sequences'} and type(r['row_index']) is type(r['sequences']) is int and
                0 <= r['row_index'] < 4 and r['sequences'] >= 0 for r in rows) and
                len({r['row_index'] for r in rows}) == len(rows) and type(event['raw_returned']) is int and
                event['raw_returned'] == sum(r['sequences'] for r in rows),
                'all source returned row counts required')
            coverage = {'batch_index': local['batch'], 'returned_row_ids': sorted(r['row_index'] for r in rows),
                        'empty_rows': 4-sum(r['sequences'] > 0 for r in rows)}
            _same(event['coverage'], coverage, 'source row coverage differs')
            local['coverage'].append(coverage); local['raw'] += event['raw_returned']
            local.update(generation_open=False, remaining_rows=rows, row_offset=0, row_used=0)
        elif name == 'source_sequence':
            require(call is None and source is None and candidate is None and not local['generation_open'],
                    'interleaved source sequence processing required')
            while local['row_offset'] < len(local['remaining_rows']) and local['row_used'] == \
                    local['remaining_rows'][local['row_offset']]['sequences']:
                local['row_offset'] += 1; local['row_used'] = 0
            require(local['row_offset'] < len(local['remaining_rows']), 'unexpected extra source sequence')
            row = local['remaining_rows'][local['row_offset']]
            require(event['batch_index'] == local['batch'] and event['row_index'] == row['row_index'] and
                event['beam_index'] == local['row_used'] and event['sequence_index'] == local['processed'] and
                event['source_view'] == local['batches'][local['batch']][row['row_index']],
                'every raw sequence must be consumed in native returned order')
            validate_sequence(event['beam_score'], event['source_tokens'])
            source = event; local['processed'] += 1; local['row_used'] += 1
        elif name in ('candidate_invalid', 'candidate_parsed'):
            require(source is not None and candidate is None and call is None and
                event['source_view'] == source['source_view'] and event['source_tokens'] == source['source_tokens'],
                'candidate requires its exact source sequence')
            array = local['formatter'].convert_tokens_to_array(source['source_tokens'])
            if name == 'candidate_invalid':
                require(array is None, 'invalid parse differs from original formatter')
                local['invalid'] += 1; source = None
            else:
                require(array is not None, 'claimed grid cannot parse')
                solution = loader.ArcDataset.invert_mod(array, source['source_view'], inv_perm=True).tolist()
                identity = grid_key(solution)
                require(event['candidate_grid'] == solution and event['beam_score'] == source['beam_score'] and
                    event['already_verified'] is (identity in local['known']), 'original inverse/duplicate differs')
                duplicate = identity in local['known']
                _rows, bindings = verifier_rows(local['puzzle'], local['base'], solution, loader,
                                                 local['formatter'], tokenizer)
                candidate = {'identity': identity, 'solution': solution, 'duplicate': duplicate,
                    'bindings': bindings, 'scores': [], 'calls': [], 'verified_views': 0}
        elif name == 'candidate_ranked':
            require(source is not None and candidate is not None and call is None and
                event['source_view'] == source['source_view'] and event['source_tokens'] == source['source_tokens'] and
                event['beam_score'] == source['beam_score'] and event['candidate_grid'] == candidate['solution'],
                'ranked occurrence provenance differs')
            identity = candidate['identity']
            if candidate['duplicate']:
                scores, calls = local['known'][identity]
            else:
                require(candidate['verified_views'] == 8 and len(candidate['calls']) == 2,
                        'eight interleaved verifier views must finish before voting')
                scores, calls = candidate['scores'], candidate['calls']
                local['known'][identity] = (scores, calls)
            _same(event['score_aug'], scores, 'ranked scores must equal actual complete verifier readbacks')
            _same(event['verification_call_ids'], calls, 'ranked calls must match original completed verification')
            local['votes'][str(len(local['votes']))] = {'solution': loader.np.asarray(candidate['solution']),
                'beam_score': source['beam_score'], 'score_aug': scores}
            source = candidate = None
        elif name == 'test_terminal':
            require(call is None and source is None and candidate is None and not local['generation_open'] and
                local['batch'] == 3 and len(local['coverage']) == 4 and local['processed'] == local['raw'],
                'all four source batches and every candidate must finish')
            terminal = event['result']
            grids = [g.tolist() for g in decoder.score_kgmon(local['votes'])]
            require(len(grids) == len({grid_key(g) for g in grids}) == len(local['known']),
                    'original ranking closure differs')
            expected = {'test_index': index, 'base_key': local['base'], 'ranked_grids': grids,
                'attempts': grids[:2], 'missing_attempts': max(0, 2-len(grids)),
                'reserved_generation_batches': 4, 'completed_generation_batches': 4,
                'source_view_denominator': 16, 'unfinished_source_views': 0, 'undispatched_source_views': 0,
                'returned_sequences_processed': local['processed'], 'raw_returned': local['raw'],
                'raw_unprocessed': 0, 'invalid_candidates': local['invalid'], 'unique_candidates': len(local['known']),
                'coverage': local['coverage'], 'termination_reason': 'all_source_batches_completed',
                'status': 'complete' if len(grids) >= 2 else 'missing-candidate',
                'native_complete': bool(grids), 'output_qualified': bool(grids),
                'candidate_path_exercised': bool(grids), 'search_exhaustiveness_claim': False,
                'correctness_scored': False, 'native_logit_replay': False,
                'started_epoch': local['started_epoch'], 'deadline_epoch': None, 'resource_policy': POLICY}
            require(set(terminal) == set(expected) | {'finished_epoch', 'elapsed_host_seconds'},
                    'closed uncapped terminal result required')
            for field, value in expected.items(): _same(terminal[field], value, 'terminal '+field+' differs')
            require(finite(terminal['finished_epoch']) and finite(terminal['elapsed_host_seconds']) and
                terminal['elapsed_host_seconds'] >= 0, 'finite actual elapsed observations required')
        elif name == 'test_committed':
            require(terminal is not None, 'terminal event must precede commitment')
            _same(event['result'], terminal, 'committed result differs')
            _same(record['tests'][index], terminal, 'durable checkpoint result differs')
            index += 1; local = terminal = None
    require(index == count and local is call is source is candidate is terminal is None,
            'all real tests must have an exact completed commit')
    _same(record['accounting'], total, 'forward/token accounting differs')
    _same(record['event_chain'], {'rows': event_count, 'head': head}, 'event seal/truncation differs')
    require(record['output_qualified'] is all(t['output_qualified'] for t in record['tests']),
            'task output qualification differs')
    observer = read_json(output/'inference-forward-diagnostics.json')
    _same(observer['binding'], bound, 'observer task binding differs')
    require(observer['observed_rows'] == observer_count == sum(v['completed'] for v in total.values()) and
        observer['maximum_rows'] is None and observer['truncated'] is False and observer['dropped_rows'] == 0 and
        observer['failed_rows'] == 0 and observer['native_numerical_replay'] is False,
        'all forward observations must survive without truncation')
    return record
