"""Hash-bound native Qwen3 solve integration; no data/weight/provider acquisition.

The three original code cells remain byte-frozen. Only reviewed definitions are
loaded, never their notebook runner, solution loader, pickle IO or score helper.
"""
from __future__ import annotations
import ast
from collections import defaultdict
from contextlib import contextmanager
import hashlib
import math
from pathlib import Path
import time
from types import SimpleNamespace

SOURCE_HASHES = {
    'solver.py': '1387c5b0b188dcc8570659dd5905ec2e824e5e0dfd7b20d8be9c2e13d0f12962',
    'arc_loader.py': 'd01cd56167e534ae156706ef62ab11662fc7b403964614a7a55131940bde970c',
    'arc_decoder.py': '965cfd910777d9bbec9681c6c15c5e2ea3924569734248046f5e58f16cb28222',
}
FAILURE_READ_METHODS = {'from_file', 'load_replies', 'get_submission',
                        'fill_submission', 'validate_submission'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


class InferenceLimitReached(RuntimeError):
    """A planned inference stop, distinct from a model/interface failure."""
    def __init__(self, reason):
        self.reason = reason
        super().__init__('native inference ceiling reached: ' + reason)


def discard_optimizer_state(model, trainer, budget):
    """Attempt every cleanup even when zero_grad or another cleanup fails."""
    errors = []
    optimizer = None if budget is None else budget.optimizer
    actions = [lambda: model.zero_grad(set_to_none=True)]
    if optimizer is not None:
        actions += [lambda: optimizer.zero_grad(set_to_none=True), optimizer.state.clear]
    actions += [trainer.accelerator._optimizers.clear, trainer.accelerator._schedulers.clear]
    for action in actions:
        try:
            action()
        except BaseException as error:
            errors.append(error)
    trainer.optimizer = None
    trainer.lr_scheduler = None
    if budget is not None:
        budget.optimizer = None
    if errors:
        raise errors[0]


def load_sources(directory, torch, np):
    definitions = {}
    for name, expected in SOURCE_HASHES.items():
        body = (Path(directory) / name).read_bytes()
        require(hashlib.sha256(body).hexdigest() == expected, 'exact original code cell differs: ' + name)
        tree = ast.parse(body)
        namespace = {'np': np, 'torch': torch, 'time': time, 'defaultdict': defaultdict,
                     'AutoTokenizer': object}
        if name == 'solver.py':
            wanted = {'turbo_dfs', 'inference_turbo_dfs', 'calc_scores'}
            constants = {'ARC_VOCAB', 'ARC_TOKENS', 'USER_TOKEN_ID',
                         'ASSISTANT_TOKEN_ID', 'PAD_ID', 'EOS_ID'}
            nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted
                     or isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and
                     t.id in constants for t in n.targets)]
            require({n.name for n in nodes if isinstance(n, ast.FunctionDef)} == wanted,
                    'native solver definitions missing')
        elif name == 'arc_decoder.py':
            wanted = {'hashable', 'score_sum', 'getter_kgmon', 'score_kgmon'}
            nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
            require({n.name for n in nodes} == wanted, 'native ranking definitions missing')
        else:
            nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
            for node in nodes:
                if isinstance(node, ast.ClassDef) and node.name == 'ArcDataset':
                    node.body = [n for n in node.body if not isinstance(n, ast.FunctionDef)
                                 or n.name not in FAILURE_READ_METHODS]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(Path(directory) / name), 'exec'), namespace)
        definitions[name] = SimpleNamespace(**namespace)
    return definitions['arc_loader.py'], definitions['solver.py'], definitions['arc_decoder.py']


def validate_visible(visible):
    require(isinstance(visible, dict) and len(visible) == 1, 'one fixed visible development task required')
    task_id, task = next(iter(visible.items()))
    require(isinstance(task_id, str) and task_id and '.' not in task_id and '_' not in task_id,
            'source-compatible task ID required')
    require(isinstance(task, dict) and set(task) == {'train', 'test'} and
            isinstance(task['train'], list) and task['train'] and
            isinstance(task['test'], list) and len(task['test']) == 1,
            'one-test fixed source task required')
    for pair in task['train']:
        require(isinstance(pair, dict) and set(pair) == {'input', 'output'}, 'visible demonstration differs')
        for value in pair.values():
            grid_key(value)
    require(isinstance(task['test'][0], dict) and set(task['test'][0]) == {'input'},
            'test answer or extra test metadata forbidden')
    grid_key(task['test'][0]['input'])
    return task_id


def grid_key(value):
    require(isinstance(value, list) and 1 <= len(value) <= 30 and
            isinstance(value[0], list) and 1 <= len(value[0]) <= 30, 'legal grid dimensions required')
    width = len(value[0])
    require(all(isinstance(row, list) and len(row) == width and
                all(type(cell) is int and 0 <= cell <= 9 for cell in row)
                for row in value), 'legal rectangular grid colors required')
    return tuple(map(tuple, value))


def source_batches(keys):
    groups = defaultdict(list)
    for key in sorted(keys):
        groups[key.split('.')[0]].append(key)
    require(len(groups) == 1 and all(len(rows) == 16 for rows in groups.values()),
            'all sixteen original generation views required')
    result = []
    for offsets in ((0, 4), (2, 6), (8, 12), (10, 14)):
        for rows in groups.values():
            result.append([key for offset in offsets for key in rows[offset:offset + 2]])
    require(len(result) == 4 and len({k for rows in result for k in rows}) == 16,
            'four distinct original four-view batches required')
    return result


class SourceModel:
    """Count actual callable entries; normalize source-compatible outputs/positions.

    Native cached outputs can be tuples despite return_dict=True. This wrapper
    changes the interface only, retaining the exact logits and cache objects.
    """
    def __init__(self, model, torch, emit, *, forward_limits, input_token_limit,
                 generation_deadline, context_tokens=8192):
        self.model, self.torch, self.emit = model, torch, emit
        self.device = model.device
        self.forward_limits = dict(forward_limits)
        require(set(self.forward_limits) == {'control', 'generation', 'verification'} and
                all(type(v) is int and v > 0 for v in self.forward_limits.values()) and
                type(input_token_limit) is int and input_token_limit > 0,
                'finite actual inference limits required')
        self.reserved = {key: 0 for key in self.forward_limits}
        self.completed = dict(self.reserved)
        self.input_token_limit = input_token_limit
        self.input_tokens = 0
        self.input_by_phase = dict(self.reserved)
        self.context_tokens = context_tokens
        require(type(context_tokens) is int and context_tokens > 0 and
                type(generation_deadline) in (int, float) and math.isfinite(generation_deadline),
                'finite context/deadline required')
        self.generation_deadline = generation_deadline
        self.active = None

    @contextmanager
    def scope(self, phase):
        require(phase in self.reserved and self.active is None, 'one known inference phase required')
        self.active = phase
        try:
            yield self
        finally:
            self.active = None

    def __call__(self, *, input_ids, **kwargs):
        phase = self.active
        require(phase in self.reserved, 'unreserved native model entry')
        shape = list(input_ids.shape)
        require(len(shape) == 2 and shape[0] == 4 and 1 <= shape[1] <= self.context_tokens,
                'fixed four-view batch and finite context required')
        if self.reserved[phase] >= self.forward_limits[phase]:
            raise InferenceLimitReached('forward_limit')
        if phase != 'control' and time.time() >= self.generation_deadline:
            raise InferenceLimitReached('inference_deadline')
        tokens = shape[0] * shape[1]
        if phase == 'control':
            require(self.input_by_phase['control'] + tokens <= 168, 'fixed synthetic control-token ceiling reached')
        else:
            if sum(v for k, v in self.input_by_phase.items() if k != 'control') + tokens > self.input_token_limit:
                raise InferenceLimitReached('input_token_limit')
        cached = kwargs.get('past_key_values') is not None
        positions = kwargs.get('position_ids')
        if positions is None:
            require(not cached, 'cached native call needs explicit source positions')
            positions = self.torch.arange(shape[1], device=self.device).unsqueeze(0).expand(shape[0], -1).contiguous()
            kwargs['position_ids'] = positions
        values = positions.detach().cpu().tolist()
        require(len(values) == shape[0] and all(len(row) == shape[1] and
                all(type(v) is int and 0 <= v < self.context_tokens for v in row)
                for row in values), 'bounded explicit position IDs required')
        require(all(row == list(range(values[0][0], values[0][0]+shape[1])) for row in values),
                'one contiguous source position range across all four views required')
        if not cached:
            require(all(row == list(range(shape[1])) for row in values), 'prefill positions must start at zero')
        require(type(kwargs.get('use_cache')) is bool and kwargs.get('return_dict', True) is True,
                'explicit native cache/output policy required')
        kwargs['return_dict'] = True
        self.reserved[phase] += 1
        self.input_tokens += tokens
        self.input_by_phase[phase] += tokens
        call_id = sum(self.reserved.values())
        self.emit('forward_reserved', call_id=call_id, phase=phase, batch_shape=shape,
                  physical_input_tokens=tokens, cached=cached,
                  position_start=values[0][0], position_end=values[0][-1])
        output = self.model(input_ids=input_ids, **kwargs)
        if isinstance(output, tuple):
            require(len(output) >= (2 if kwargs['use_cache'] else 1), 'native tuple must contain requested outputs')
            logits, cache = output[0], output[1] if len(output) >= 2 else None
            contract = 'tuple-logits-cache'
        else:
            logits, cache = output.logits, getattr(output, 'past_key_values', None)
            contract = 'model-output-logits-cache'
        require(list(logits.shape) == [shape[0], shape[1], 16] and
                bool(self.torch.isfinite(logits).all().item()), 'finite exact sixteen-row native logits required')
        require(kwargs['use_cache'] is False or cache is not None, 'native cache result missing')
        self.completed[phase] += 1
        self.emit('forward_completed', call_id=call_id, phase=phase, output_contract=contract)
        return SimpleNamespace(logits=logits, past_key_values=cache)


def compare_vectors(reference, actual):
    require(len(reference) == len(actual) == 4 and all(len(r) == len(a) == 16
        and all(math.isfinite(x) for x in r + a) for r, a in zip(reference, actual)),
        'four finite native vocabulary vectors required')
    def eligible(row):
        top = max(row); denominator = sum(math.exp(v - top) for v in row)
        return [i for i in list(range(11)) + [15] if math.exp(row[i] - top) / denominator > .2]
    rows = [{'maximum_absolute_logit_difference': max(abs(x-y) for x,y in zip(r,a)),
             'bitwise_equal': r == a,
             'argmax_equal': max(range(16), key=r.__getitem__) == max(range(16), key=a.__getitem__),
             'root_probability_eligible_set_equal': eligible(r) == eligible(a)}
            for r, a in zip(reference, actual)]
    return {'comparisons': rows, 'gate_passed': all(row['argmax_equal'] and
            row['root_probability_eligible_set_equal'] for row in rows),
            'full_numerical_parity_claim': False}


CONTROL_PREFIXES = [[14, 11, 10, a, b, 15, 14, 12, 10]
                    for a, b in ((0, 1), (1, 0), (2, 3), (3, 2))]


def cache_controls(adapter):
    torch = adapter.torch
    def ids(rows):
        return torch.tensor(rows, device=adapter.device, dtype=torch.long)
    with torch.inference_mode(), adapter.scope('control'):
        first = adapter(input_ids=ids(CONTROL_PREFIXES), use_cache=True)
        initial = first.logits[:, -1].float().cpu().tolist()
        child = adapter(input_ids=ids([[0]] * 4), position_ids=ids([[9]] * 4),
                        past_key_values=first.past_key_values, use_cache=True)
        deep = adapter(input_ids=ids([[1]] * 4), position_ids=ids([[10]] * 4),
                       past_key_values=child.past_key_values, use_cache=True)
        deep_values = deep.logits[:, -1].float().cpu().tolist()
        sibling = adapter(input_ids=ids([[2]] * 4), position_ids=ids([[9]] * 4),
                          past_key_values=first.past_key_values, use_cache=True)
        sibling_values = sibling.logits[:, -1].float().cpu().tolist()
        reference_deep = adapter(input_ids=ids([row + [0, 1] for row in CONTROL_PREFIXES]), use_cache=False)
        reference_sibling = adapter(input_ids=ids([row + [2] for row in CONTROL_PREFIXES]), use_cache=False)
    comparisons = {'deep': compare_vectors(reference_deep.logits[:, -1].float().cpu().tolist(), deep_values),
                   'sibling_after_deep': compare_vectors(reference_sibling.logits[:, -1].float().cpu().tolist(), sibling_values)}
    adapter.emit('cache_control_result', comparisons=comparisons, baseline_prefill=initial,
                 deep_cached=deep_values, sibling_cached=sibling_values,
                 deep_reference=reference_deep.logits[:, -1].float().cpu().tolist(),
                 sibling_reference=reference_sibling.logits[:, -1].float().cpu().tolist())
    require(all(value['gate_passed'] for value in comparisons.values()),
            'native cache branch control failed before training')
    return {'comparisons': comparisons, 'baseline_prefill': initial, 'model_calls': 6,
            'synthetic_tokens_only': True, 'full_numerical_parity_claim': False}


def reset_control(adapter, before):
    torch = adapter.torch
    with torch.inference_mode(), adapter.scope('control'):
        result = adapter(input_ids=torch.tensor(CONTROL_PREFIXES, device=adapter.device, dtype=torch.long), use_cache=True)
        after = result.logits[:, -1].float().cpu().tolist()
    require(after == before['baseline_prefill'], 'post-reset inference differs from its exact same-run baseline')
    return {'prefill_bitwise_equal': True, 'prefill': after,
            'synthetic_tokens_only': True, 'additional_model_calls': 1}



def source_result_rows(result):
    """The pinned DFS returns only rows with EOS suffixes; absent rows are empty."""
    require(isinstance(result, list), 'source batch result must be a list')
    rows = {}
    for row in result:
        require(isinstance(row, (list, tuple)) and len(row) == 2 and
                type(row[0]) is int and 0 <= row[0] < 4 and row[0] not in rows and
                isinstance(row[1], list), 'unique bounded source result row required')
        rows[row[0]] = row[1]
    return rows


def solve_visible(visible, loader, solver, decoder, tokenizer, adapter, *, task_started,
                  task_seconds=1200, maximum_candidates=64, emit=lambda *_args, **_kwargs: None):
    task_id = validate_visible(visible)
    np = loader.np
    formatter = loader.QwenFormatter(tokenizer)
    require(formatter.max_new_tokens() == 931, 'exact original maximum answer-token limit required')
    puzzle = loader.ArcDataset(queries=visible, keys=[task_id]).split_multi_replies()
    state = np.random.get_state()
    try:
        views = puzzle.augment(n=2, seed=2)
        views = views.cut_to_len(formatter=formatter, name='input', max_len=8192-931)
        batches = source_batches(views.keys)
        known_scores, candidates = {}, {}
        completed_batches = 0
        reserved_batches = 0
        stop_reason = None
        raw_candidates = invalid_candidates = sequences = 0
        batch_coverage = []
        for batch in batches:
            if time.time() - task_started >= task_seconds:
                stop_reason = 'task_deadline'
                break
            if time.time() >= adapter.generation_deadline:
                stop_reason = 'inference_deadline'
                break
            prefixes = [tokenizer.encode(views.get(key, formatter)['input']) for key in batch]
            require(len({len(row) for row in prefixes}) == 1, 'original unpadded batch lengths differ')
            emit('generation_reserved', batch_index=completed_batches, view_count=4)
            reserved_batches += 1
            try:
                with adapter.scope('generation'):
                    result = solver.inference_turbo_dfs(adapter, prefixes, 931, -math.log(.2), adapter.generation_deadline)
            except InferenceLimitReached as error:
                stop_reason = error.reason
                break
            rows = source_result_rows(result)
            coverage = {'batch_index': completed_batches, 'attempted_views': 4,
                'returned_row_ids': sorted(rows),
                'rows_with_sequences': sum(bool(beams) for beams in rows.values()),
                'absent_rows': 4-len(rows),
                'explicit_empty_rows': sum(not beams for beams in rows.values())}
            coverage['empty_rows'] = coverage['absent_rows'] + coverage['explicit_empty_rows']
            batch_coverage.append(coverage)
            completed_batches += 1
            emit('generation_completed', batch_index=completed_batches-1,
                 source_result_coverage=coverage)
            for batch_index, beams in rows.items():
                key = batch[batch_index]; base_key = key.split('.')[0]
                for score, tokens in beams:
                    sequences += 1
                    require(sequences <= maximum_candidates, 'native returned sequence ceiling reached')
                    require(tokens and tokens[-1] == 15 and math.isfinite(float(score)) and
                            0 <= float(score) < -math.log(.2), 'source EOS/score contract differs')
                    array = formatter.convert_tokens_to_array(tokens)
                    if array is None:
                        invalid_candidates += 1
                        continue
                    solution = puzzle.invert_mod(array, key, inv_perm=True)
                    canonical_grid = grid_key(solution.tolist())
                    raw_candidates += 1
                    require(raw_candidates <= maximum_candidates, 'native candidate ceiling reached')
                    identity = (base_key, canonical_grid)
                    emit('candidate_parsed', source_view=key, candidate_grid=solution.tolist(),
                         beam_score=float(score), already_verified=identity in known_scores)
                    if identity not in known_scores:
                        dataset = loader.ArcDataset(queries={base_key: puzzle.queries[base_key]},
                                                   replies={base_key: [solution.tolist()]}, keys=[base_key])
                        dataset = dataset.augment(seed=hash(base_key) % 1024**2)
                        dataset = dataset.cut_to_len(formatter=formatter, name='input', max_len=8192-931)
                        rows = dataset.as_list(formatter)
                        require(len(rows) == 8, 'eight original verification views required')
                        queries, answers = [r['input'] for r in rows], [r['reply'] for r in rows]
                        try:
                            with adapter.scope('verification'):
                                scores = solver.calc_scores(queries[:4], answers[:4], tokenizer, adapter)
                                scores += solver.calc_scores(queries[4:], answers[4:], tokenizer, adapter)
                        except InferenceLimitReached as error:
                            stop_reason = error.reason
                            break
                        require(len(scores) == 8 and all(math.isfinite(float(s)) for s in scores), 'finite eight-view scores required')
                        known_scores[identity] = scores
                    candidates[str(len(candidates))] = {'beam_score': float(score),
                        'score_aug': known_scores[identity], 'solution': solution}
                    emit('candidate_ranked', source_view=key, candidate_grid=solution.tolist(),
                         source_tokens=tokens, beam_score=float(score),
                         score_aug=[float(s) for s in known_scores[identity]])
                if stop_reason is not None:
                    break
            if stop_reason is not None:
                break
        ranked = decoder.score_kgmon(candidates)
        grids = [value.tolist() for value in ranked]
        for value in grids:
            grid_key(value)
        require(len(grids) == len({grid_key(value) for value in grids}) == len(known_scores),
                'source inverse/deduplication/ranking closure differs')
        return {'task_id': task_id, 'completed_generation_batches': completed_batches,
                'reserved_generation_batches': reserved_batches,
                'termination_reason': stop_reason or 'all_source_batches_completed',
                'attempted_source_views': reserved_batches * 4,
                'completed_source_views': completed_batches * 4,
                'unfinished_source_views': (reserved_batches-completed_batches) * 4,
                'raw_candidates': raw_candidates,
                'returned_sequences': sequences, 'generation_batch_coverage': batch_coverage,
                'source_views_without_sequences': sum(row['empty_rows'] for row in batch_coverage)
                    + (reserved_batches-completed_batches) * 4,
                'unique_candidates': len(known_scores), 'invalid_parsed_candidates': invalid_candidates,
                'ranked_grids': grids, 'attempts': grids[:2], 'missing_attempts': max(0, 2-len(grids)),
                'nonempty_ranking': bool(grids), 'all_source_batches_completed': completed_batches == 4,
                'outcome': 'complete' if completed_batches == 4 and grids and stop_reason is None else 'inconclusive',
                'correctness_scored': False, 'original_convenience_scorer_called': False,
                'search_exhaustiveness_claim': False,
                'ranking_policy': 'unchanged_source_score_kgmon', 'verification_seed_policy': 'hash(base_key), PYTHONHASHSEED=0'}
    finally:
        np.random.set_state(state)
