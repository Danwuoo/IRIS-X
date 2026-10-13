"""Explicit RL A/B/C PUBLIC successor; source-review-only and unpublishable.

Generation consumes only authenticated challenge projections and an actually
frozen dev decision.  This is deliberately NOT the old SFT checkpoint schema.
The only label-opening API is ``score_closed_public`` in the parent AFTER its
owned supervisor has minted and reverified a nonserializable ClosedCapability.
The original, byte-pinned offline scorer owns all task-answer reads/scoring.
Trust is fixed source and owned process/dataflow, not same-UID secrecy.
"""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
import math
from pathlib import Path
import sys
import time

from experiment_flow.contracts import SourceFreeze, canonical, digest, file_sha, require, write_json
from experiment_flow.evaluation import PredictionAuthority, read_predictions, validate_generation

ROOT = Path(__file__).resolve().parents[1]
SOLVER_MANIFEST_SHA256 = '549019b4b5cb47176f3abd3fcd9ca516e91b7d6e581dfc414a5a6452ff7b1f7f'
EVALUATOR_MANIFEST_SHA256 = 'c7e8ad35770a66a71a22cccbbd0455c1c3bcc1a505dfb2e4c29819eec6209e33'
SCORER_PINS_SHA256 = '58216d4cf1ced5740b7f66b7be845d38ce327f5fb84048876aa54d3ca29f9f72'
REQUEST_FORMAT = 'irisx/rl-public-successor-request-v1'
ARTIFACT_FORMAT = 'irisx/rl-public-successor-predictions-v1'
SEAL_FORMAT = 'irisx/rl-public-successor-seal-v1'
REPORT_FORMAT = 'irisx/rl-public-successor-evaluation-v1'
METHOD = 'rl-abc/dev-selected-frozen-primaryTTT0-transform01-top2'
SCOPE = 'source-review-only-unpublishable'
_SYNTHETIC_FORMAT = 'irisx/rl-public-successor-synthetic-challenges-v1'
_SYNTHETIC_GOLD_FORMAT = 'irisx/rl-public-successor-synthetic-gold-v1'


def _exact(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), label + ' schema differs')


def _sha(value):
    require(type(value) is str and len(value) == 64 and set(value) <= set('0123456789abcdef'), 'SHA256 required')
    return value


def _regular(path):
    path = Path(path).absolute()
    require(not path.is_symlink() and all(not p.is_symlink() for p in path.parents), 'symlink evidence forbidden')
    require(path.is_file() and path.stat().st_size <= 2 * 1024**3, 'bounded regular evidence required')
    return path


def _read_ref(ref, *, owner=None):
    _exact(ref, ('path', 'file_sha256'), 'immutable file reference')
    path = _regular(ref['path'])
    if owner is not None:
        require(path.is_relative_to(Path(owner).resolve()), 'evidence escapes owner output')
    require(file_sha(path) == _sha(ref['file_sha256']), 'sealed file bytes changed')
    return json.loads(path.read_text())


def _ref(path):
    path = _regular(path)
    return {'path': str(path), 'file_sha256': file_sha(path)}


def _source_check(sources):
    require(type(sources) is SourceFreeze and Path(sources.root).resolve() == ROOT, 'exact owned successor source root required')
    sources.verify()
    inventory = dict(sources.files)
    own = str(Path(__file__).resolve().relative_to(ROOT))
    require(inventory.get(own) == file_sha(__file__), 'PUBLIC bridge absent from owned source registry')
    from tools.arc_public_research_20261010.public_evaluator import SCORER_PINS
    require(digest(SCORER_PINS) == SCORER_PINS_SHA256, 'historical scorer pin registry changed')
    for name, pin in SCORER_PINS.items():
        require(inventory.get('baseline/' + name) == pin and file_sha(ROOT / 'baseline' / name) == pin,
                'unchanged original scorer import closure required: ' + name)
    # No accidentally inherited module from another checkout can substitute for
    # a same-named import even when the on-disk successor inventory is correct.
    for name, module in tuple(sys.modules.items()):
        if name.startswith(('tools.', 'irisx.', 'experiment_flow.', 'owned_runtime.')):
            filename = getattr(module, '__file__', None)
            if filename and Path(filename).suffix == '.py':
                path = Path(filename).resolve()
                require(path.is_relative_to(ROOT), 'foreign checkout module: ' + name)
                relative = str(path.relative_to(ROOT))
                require(inventory.get(relative) == file_sha(path), 'unregistered imported source: ' + name)
    return dict(SCORER_PINS)


def _inference(plan):
    require(plan.transforms == (0, 1) and all(type(t) is int for t in plan.transforms) and
            type(plan.seed) is int and plan.seed == 1917, 'fixed primary views/seed required')
    require(plan.inference['TTT'] is False and plan.inference['maximum_answers'] == 2, 'primaryTTT0 required')
    return {**deepcopy(plan.inference), 'do_sample': False, 'temperature': 1.0, 'top_p': 1.0}


def _cases(challenges):
    from tools.arc_kaggle_submission import challenge_counts
    challenge_counts(challenges)  # Rejects query outputs and all extra fields.
    return [{'case_id': 'public:' + key + ':' + str(index), 'parent_id': key, 'scope': 'public',
             'demos': deepcopy(task['train']), 'query_input': deepcopy(test['input']),
             'source': {'task_id': key, 'test_index': index, 'input_sha256': digest(test['input'])}}
            for key, task in sorted(challenges.items()) for index, test in enumerate(task['test'])]


def _selection(selection, authority, arms, plan):
    require(type(authority) is PredictionAuthority and authority.selection == canonical(selection),
            'actual owned dev-only frozen selection required')
    require(authority.closure is None, 'PUBLIC generations must precede final model closure')
    require(getattr(authority.dataset, '_authority', None) is authority, 'unregistered dev evaluator authority')
    require('dev' in authority.issued, 'dev predictions were never issued')
    dev_seal = json.loads(authority.issued['dev'])
    payload = authority.admit('dev', dev_seal)
    require(payload['experiment_plan_sha256'] == plan.sha256, 'foreign dev experiment plan')
    frozen = _read_ref({k: selection[k] for k in ('path', 'file_sha256')})
    require(frozen == {k: v for k, v in selection.items() if k not in ('path', 'file_sha256')}, 'dev decision changed')
    require(frozen['rule'] == 'dev-exact-fixed-tie-A-B-C' and frozen['holdout_labels_opened'] is False,
            'dev-only fixed selection rule required')
    require(frozen['dev_prediction_file_sha256'] == dev_seal['file_sha256'], 'selection belongs to different dev predictions')
    scores = frozen['scores']
    require(set(scores) == {'A', 'B', 'C'}, 'all three dev scores required')
    chosen = max(('A', 'B', 'C'), key=lambda a: scores[a]['exact'])
    require(frozen['selected_arm'] == chosen, 'fixed dev tie-break winner differs')
    require(authority.expected['adapter_identities'] == {a: arms[a]['adapter_sha256'] for a in ('A', 'B', 'C')},
            'selected snapshot inventory differs from evaluated arms')
    return chosen, dev_seal


def _is_native(backend):
    from experiment_flow.native import NativeSessionAdapter
    from owned_runtime.backend import NativeOwnedAdapter
    return type(backend) in (NativeSessionAdapter, NativeOwnedAdapter)


def predict_public_native(backend, case, *, transform, seed, max_new_tokens, deadline):
    """Original target-free packing/decoder, with an explicit PUBLIC case schema."""
    from experiment_flow.native import NativeSessionAdapter
    from tools.arc_qwen_transfer_20261012.data import pack_prompt
    from tools.arc_qwen_transfer_20261012.arc_adaptation import Transform
    from tools.arc_learning_agent_20261011.grid_codec import decode_grid
    require(_is_native(backend), 'exact owned native adapter required')
    config = backend.session.native.config
    require(config.get('do_sample') is False and config.get('temperature') == 1.0 and config.get('top_p') == 1.0,
            'PUBLIC inference must remain greedy')
    operation = Transform(transform)
    lists = lambda grid: [list(row) for row in grid]
    demos = [{k: lists(operation.apply(d[k])) for k in ('input', 'output')} for d in case['demos']]
    query = lists(operation.apply(case['query_input']))
    backend.assert_settled()
    messages, packing = pack_prompt(backend.session.native, demos, query, task_id=case['case_id'])
    if messages is None:
        generation = {'dispatched': False, 'valid': False, 'finish_reason': 'context_excluded'}
        status = 'context-excluded'
        identity = backend.identity()
    else:
        generation = backend.session.evaluate(messages, seed=seed, max_new_tokens=max_new_tokens, deadline=deadline)
        require(not generation.get('fatal_error') and not generation.get('fatal_native_state'), 'fatal native PUBLIC state')
        identity = generation['rl_policy_identity']
        status = 'complete' if generation.get('valid') else 'invalid'
        if generation.get('finish_reason') in ('deadline', 'error', 'rejected'):
            status = 'infrastructure-excluded'
    prediction = lists(operation.inverse().apply(decode_grid(generation['text']))) if generation.get('valid') else None
    backend.assert_settled()
    return {'case_id': case['case_id'], 'transform': transform, 'prediction': prediction,
            'status': status, 'dispatched': generation['dispatched'], 'packing': packing,
            'generation': generation, 'adapter_sha256': identity['adapter_sha256'], 'query_targets_used': False}


class PublicSuccessorBridge:
    """One-use generation owner. Constructor receives no evaluator/gold path."""
    def __init__(self, sources, *, solver_root, output_root, solver_manifest_sha256=SOLVER_MANIFEST_SHA256):
        _source_check(sources)
        require(solver_manifest_sha256 == SOLVER_MANIFEST_SHA256, 'original solver manifest pin required')
        from tools.arc_public_research_20261010.public_data import load_solver_tasks
        solver = load_solver_tasks(solver_root, solver_manifest_sha256)
        require(solver['manifest']['evidence_mode'] == 'public-development', 'original PUBLIC120 solver required')
        self._initialize(sources, solver['challenges'], output_root, mode='public-development',
                         solver={'root': str(Path(solver_root).resolve()), 'manifest_sha256': solver_manifest_sha256})

    @classmethod
    def synthetic(cls, challenges, sources, output_root):
        """Small CPU mechanics fixture, never a replacement PUBLIC denominator."""
        _source_check(sources)
        require(1 <= len(_cases(challenges)) <= 4, 'bounded explicit synthetic fixture required')
        obj = cls.__new__(cls)
        obj._initialize(sources, challenges, output_root, mode='synthetic-test-only', solver=None)
        return obj

    def _initialize(self, sources, challenges, output_root, *, mode, solver):
        self.sources = sources
        self.challenges = deepcopy(challenges)
        self.challenge_sha256 = digest(challenges)
        self.output = Path(output_root).resolve()
        self.mode, self.solver = mode, solver
        self._issued = None
        require(not self.output.exists(), 'PUBLIC output identity consumed')
        require(not self.output.is_relative_to(ROOT / 'baseline'), 'output cannot mutate baseline')

    def generate(self, backend, *, selection, selection_authority, arms, plan, deadline, clock=time.monotonic):
        require(self._issued is None and not self.output.exists(), 'PUBLIC bridge is one-use')
        _source_check(self.sources)
        require(plan.sources == self.sources and digest(self.challenges) == self.challenge_sha256, 'PUBLIC source/solver changed')
        require(type(deadline) in (int, float) and math.isfinite(deadline) and deadline <= plan.deadline,
                'PUBLIC deadline must retain original inner deadline')
        arm, dev_seal = _selection(selection, selection_authority, arms, plan)
        inference = _inference(plan)
        cases = _cases(self.challenges)
        if self.mode == 'public-development':
            require(len(self.challenges) == 120 and len(cases) == 167, 'original120/167 coverage required')
        # Fixture backends remain explicitly fixtures, including when exercising
        # the complete original target-free query projection.
        scope = backend.scope
        require(scope in ('controlled-adapter-fixture', 'native-tiny-CPU-fixture', 'owned-native-production'), 'source-owned backend scope required')
        native = _is_native(backend)
        if scope == 'owned-native-production':
            from owned_runtime.backend import NativeOwnedAdapter
            require(type(backend) is NativeOwnedAdapter and self.mode == 'public-development' and plan.output_cap == 1024,
                    'factory-owned production backend and original full PUBLIC contract required')
        if not native:
            require(scope == 'controlled-adapter-fixture' and callable(getattr(backend, 'predict_public', None)),
                    'explicit source-owned controlled PUBLIC adapter required')
            path = Path(inspect.getsourcefile(type(backend))).resolve()
            require(path.is_relative_to(ROOT) and dict(self.sources.files).get(str(path.relative_to(ROOT))) == file_sha(path),
                    'controlled PUBLIC adapter absent from source registry')
        selected = arms[arm]
        manifest = _ref(Path(selected['checkpoint_path']) / 'manifest.json')
        require(manifest['file_sha256'] == selected['manifest_file_sha256'], 'selected snapshot manifest changed')
        if clock()<deadline:
            loaded = backend.reload(selected['checkpoint_path'], deadline=deadline)
            backend.assert_safe()
            require(loaded.get('reload_verified') is True and loaded.get('same_source') is True,
                    'selected snapshot must actually reload from the owned source')
            require(backend.identity()['adapter_sha256'] == selected['adapter_sha256'], 'selected adapter restore differs')
            require(loaded.get('state_sha256') == selected['save']['state_sha256'], 'selected full-state reload differs')
        else:
            loaded={**deepcopy(selected['reload']),'PUBLIC_reload_not_reached':True,
                    'prior_durable_checkpoint_proof':deepcopy(selected['reload'])}
        self.output.mkdir(parents=True, exist_ok=False)
        challenge_ref = write_json(self.output / 'target-free-challenges.json',
                                   {'format': _SYNTHETIC_FORMAT if self.mode == 'synthetic-test-only' else 'original-public-challenges-copy-v1',
                                    'challenges': self.challenges})
        request = {'format': REQUEST_FORMAT, 'scope': SCOPE, 'evidence_mode': self.mode, 'backend_scope': scope,
                   'experiment_plan_sha256': plan.sha256, 'source_root': self.sources.root,
                   'source_files': dict(self.sources.files), 'source_sha256': self.sources.sha256,
                   'solver': self.solver, 'challenge_ref': challenge_ref, 'challenge_sha256': self.challenge_sha256,
                   'selected_arm': arm, 'adapter_sha256': selected['adapter_sha256'],
                   'selected_checkpoint_manifest': manifest, 'selected_state_sha256': selected['save']['state_sha256'],
                   'selected_reload': loaded, 'dev_selection': {k: selection[k] for k in ('path', 'file_sha256')},
                   'dev_predictions': dev_seal, 'inference_contract': inference,
                   'planned_queries': len(cases), 'planned_views': len(cases) * 2,
                   'deadline': deadline, 'generation_started': clock(), 'query_targets_used': False,
                   'production_admitted': False, 'publishable': False}
        request_ref = write_json(self.output / 'request.json', request)
        rows = []
        for index, case in enumerate(cases):
            row = {'case_id': case['case_id'], 'parent_id': case['parent_id'],
                   'test_index': case['source']['test_index'], 'input_sha256': digest(case['query_input']),
                   'generations': [], 'answers': []}
            for transform in (0, 1):
                before = deepcopy(backend.physical_events())
                fn = predict_public_native if native else lambda owner, target, **kw: owner.predict_public(target, **kw)
                if clock()<deadline:
                    generation = fn(backend, deepcopy(case), transform=transform, seed=1917,
                                    max_new_tokens=plan.output_cap, deadline=deadline)
                    backend.assert_settled()
                    require(backend.identity()['adapter_sha256'] == selected['adapter_sha256'], 'PUBLIC inference changed selected adapter')
                else:
                    generation={'case_id':case['case_id'],'transform':transform,'prediction':None,
                        'status':'not-reached','dispatched':False,'adapter_sha256':selected['adapter_sha256'],
                        'query_targets_used':False,'generation':{'dispatched':False,'finish_reason':'not-reached'},
                        'packing':None,'reason':'protected-PUBLIC-deadline'}
                validate_generation(generation, case_id=case['case_id'], transform=transform,
                                    adapter_sha256=selected['adapter_sha256'])
                after = deepcopy(backend.physical_events())
                require(after[:len(before)] == before, 'earlier physical events changed')
                events = after[len(before):]
                require(all(e.get('status') in ('complete', 'failed', 'excluded') for e in events), 'unsettled PUBLIC physical work')
                require(not generation['dispatched'] or events, 'dispatched view lacks observed physical work')
                envelope = {'format': 'irisx/rl-public-successor-view-v1', 'case_id': case['case_id'],
                            'transform': transform, 'input_sha256': digest(case['query_input']),
                            'selected_arm': arm, 'adapter_sha256': selected['adapter_sha256'],
                            'seed': 1917, 'max_new_tokens': plan.output_cap, 'do_sample': False, 'TTT': False,
                            'native_receipt': native, 'receipt': generation, 'physical_events': events}
                ref = write_json(self.output / 'views' / f'{index:03d}-{transform}.json', envelope)
                row['generations'].append({'transform': transform, 'receipt': ref})
                if generation['prediction'] is not None and generation['prediction'] not in row['answers']:
                    row['answers'].append(generation['prediction'])
            rows.append(row)
        artifact = {'format': ARTIFACT_FORMAT, 'request': request_ref, 'selected_arm': arm,
                    'adapter_sha256': selected['adapter_sha256'], 'rows': rows,
                    'query_count': len(rows), 'view_count': sum(len(r['generations']) for r in rows),
                    'generation_ended': clock(), 'deadline_exceeded':clock()>deadline, 'query_targets_used': False,
                    'model_must_close_before_scoring': True, 'production_admitted': False, 'publishable': False}
        artifact_ref = write_json(self.output / 'predictions.json', artifact)
        pool, coverage = _make_pool(request, artifact, self.challenges)
        pool_ref = write_json(self.output / 'pool.json', pool)
        seal = {'format': SEAL_FORMAT, 'scope': SCOPE, 'request': request_ref, 'artifact': artifact_ref,
                'pool': pool_ref, 'coverage': coverage, 'selected_arm': arm,
                'source_sha256': self.sources.sha256, 'generation_closed': True,
                'model_closure_authority': 'parent-owned-ClosedCapability-required',
                'production_admitted': False, 'publishable': False}
        seal_ref = write_json(self.output / 'prediction-seal.json', seal)
        result = {'format': SEAL_FORMAT, **seal_ref, 'selected_arm': arm, 'coverage': coverage,
                  'status': 'PUBLIC_SUCCESSOR_PREDICTIONS_SEALED', 'production_admitted': False, 'publishable': False}
        self._issued = canonical(result)
        self.verify_issued(result)
        return result

    def verify_issued(self, seal):
        require(self._issued is not None and canonical(seal) == self._issued, 'unknown or changed owned PUBLIC seal')
        return verify_public_seal(seal, sources=self.sources)


def _make_pool(request, artifact, challenges):
    from tools.arc_offline_evaluation import POOL_FORMAT, validate_pools
    from tools.nvarc_native_multitask import digest as scorer_digest
    require(artifact['query_targets_used'] is False and artifact['production_admitted'] is False and
            artifact['publishable'] is False, 'closed target-free artifact required')
    expected = _cases(challenges)
    rows = artifact['rows']
    require(len(rows) == len(expected) == request['planned_queries'] and
            artifact['query_count'] == len(rows) and artifact['view_count'] == request['planned_views'] == 2 * len(rows),
            'complete original-query/view inventory required')
    require(artifact['selected_arm'] == request['selected_arm'] and artifact['adapter_sha256'] == request['adapter_sha256'],
            'PUBLIC artifact selected method differs')
    records = {key: {'task_id': key, 'task_digest': scorer_digest(task), 'tests': [], 'timings': {}}
               for key, task in sorted(challenges.items())}
    calls = 0; used_events = set(); completed = 0
    for row, case in zip(rows, expected):
        _exact(row, ('case_id', 'parent_id', 'test_index', 'input_sha256', 'generations', 'answers'), 'PUBLIC query')
        require(row['case_id'] == case['case_id'] and row['parent_id'] == case['parent_id'] and
                row['test_index'] == case['source']['test_index'] and row['input_sha256'] == digest(case['query_input']),
                'PUBLIC original query identity/order differs')
        require(len(row['generations']) == 2, 'exactly two PUBLIC transform slots required')
        answers = []; complete = True
        for transform, compact in enumerate(row['generations']):
            _exact(compact, ('transform', 'receipt'), 'PUBLIC view reference')
            require(type(compact['transform']) is int and compact['transform'] == transform, 'fixed PUBLIC transform order differs')
            view = _read_ref(compact['receipt'], owner=Path(artifact['request']['path']).parent)
            _exact(view, ('format', 'case_id', 'transform', 'input_sha256', 'selected_arm', 'adapter_sha256',
                          'seed', 'max_new_tokens', 'do_sample', 'TTT', 'native_receipt', 'receipt', 'physical_events'), 'PUBLIC view')
            require(view['format'] == 'irisx/rl-public-successor-view-v1' and view['case_id'] == case['case_id'] and
                    type(view['transform']) is int and view['transform'] == transform and view['input_sha256'] == row['input_sha256'] and
                    view['selected_arm'] == request['selected_arm'] and view['adapter_sha256'] == request['adapter_sha256'] and
                    view['seed'] == 1917 and view['max_new_tokens'] == request['inference_contract']['max_new_tokens'] and
                    view['do_sample'] is False and view['TTT'] is False, 'PUBLIC generation binding differs')
            receipt = view['receipt']
            validate_generation(receipt, case_id=case['case_id'], transform=transform, adapter_sha256=request['adapter_sha256'])
            events = view['physical_events']
            require(type(events) is list and (not receipt['dispatched'] or events), 'PUBLIC physical dispatch evidence missing')
            for event in events:
                event_id = event.get('event_id')
                require(type(event_id) is int and event_id not in used_events and event.get('status') in ('complete', 'failed', 'excluded'),
                        'reused or unsettled PUBLIC physical event')
                used_events.add(event_id)
            if view['native_receipt']:
                _verify_native_receipt(receipt, case, transform, events, request)
            else:
                require(request['backend_scope'] == 'controlled-adapter-fixture', 'non-native receipt outside explicit fixture')
            prediction = receipt['prediction']
            if prediction is not None and prediction not in answers: answers.append(prediction)
            calls += int(receipt['dispatched'])
            complete = complete and receipt['dispatched'] and receipt['status'] not in ('infrastructure-excluded','not-reached')
        require(row['answers'] == answers, 'PUBLIC top-two answers not derived from ordered unique views')
        completed += int(complete)
        records[case['parent_id']]['tests'].append({'test_index': row['test_index'],
                    'input_digest': scorer_digest(case['query_input']), 'ranked_grids': answers,
                    'status': 'complete' if complete else 'partial' if answers else 'failed'})
    elapsed = artifact['generation_ended'] - request['generation_started']
    require(math.isfinite(elapsed) and elapsed >= 0 and type(artifact['deadline_exceeded']) is bool and
            artifact['deadline_exceeded']==(artifact['generation_ended']>request['deadline']), 'PUBLIC clock binding differs')
    pool = {'format': POOL_FORMAT, 'run_id': 'rl-public-' + artifact['request']['file_sha256'][:24],
            'method': METHOD, 'challenges_digest': scorer_digest(challenges), 'records': list(records.values()),
            'parent_wall_seconds': elapsed}
    validate_pools(challenges, pool)
    return pool, {'planned_queries': len(expected), 'observed_queries': len(rows), 'planned_views': 2 * len(expected),
                  'observed_views': 2 * len(rows), 'actual_generation_calls': calls,
                  'complete_prediction_coverage': completed == len(expected),
                  'deadline_exceeded':artifact['deadline_exceeded'], 'query_targets_used': False}


def _verify_native_receipt(receipt, case, transform, events, request):
    from tools.arc_qwen_transfer_20261012.arc_adaptation import Transform
    from tools.arc_learning_agent_20261011.grid_codec import decode_grid, grid_messages
    if receipt['status']=='not-reached':
        require(receipt['dispatched'] is False and receipt['prediction'] is None and not events and
                receipt.get('reason')=='protected-PUBLIC-deadline','unreached PUBLIC slot invented work')
        return
    packing, native = receipt['packing'], receipt['generation']
    require(packing.get('format') == 'irisx/whole-demonstration-packing-v1' and
            packing.get('context_limit') == 4096 and packing.get('output_cap') == 1024 and
            packing.get('task_id') == case['case_id'] and packing.get('query_targets_used') is False and
            packing.get('partial_grids_or_targets_truncated') is False and packing.get('withheld_demo_id') is None,
            'native whole-demo target-free packing required')
    require(type(packing.get('admitted')) is bool, 'native packing admission required')
    if not packing['admitted']:
        require(receipt['status'] == 'context-excluded' and not receipt['dispatched'] and not events, 'context exclusion dispatch differs')
        return
    selected = packing.get('selected_demo_ids')
    require(type(selected) is list and selected and all(type(i) is str and i.isdigit() for i in selected), 'whole-demo packing IDs required')
    indices = [int(i) for i in selected]
    require(indices == sorted(set(indices)) and all(0 <= i < len(case['demos']) for i in indices) and
            packing['omitted_demo_ids'] == [str(i) for i in range(len(case['demos'])) if i not in indices], 'packing demo selection differs')
    operation = Transform(transform); lists = lambda g: [list(r) for r in g]
    demos = [{k: lists(operation.apply(case['demos'][i][k])) for k in ('input', 'output')} for i in indices]
    query = lists(operation.apply(case['query_input']))
    # Full transformed grid_messages is retained by the native packing receipt;
    # fixed Qwen template expansion is independently reconstructed without a model.
    messages = grid_messages(demos, query)
    prompt = ''.join('<|im_start|>' + m['role'] + '\n' + m['content'] + '<|im_end|>\n' for m in messages)
    prompt += '<|im_start|>assistant\n<think>\n\n</think>\n\n'
    import hashlib
    from tools.arc_qwen_transfer_20261012.demo_selector import digest as packing_digest
    require(packing.get('prompt') == prompt and packing.get('prompt_sha256') == packing_digest(prompt) and
            native.get('rendered_prompt_sha256') == hashlib.sha256(prompt.encode()).hexdigest() and
            type(packing.get('prompt_tokens')) is int and 0 < packing['prompt_tokens'] <= 3072 and
            native.get('input_tokens') == packing['prompt_tokens'],
            'native prompt differs from original query and selected whole demos')
    require(native.get('rl_policy_identity', {}).get('adapter_sha256') == request['adapter_sha256'] and
            native.get('adapter_state_sha256') == request['adapter_sha256'] and
            native.get('adapter_execution_mode') == 'trained', 'native selected adapter differs')
    require(native.get('sampling') == {'do_sample': False, 'temperature': 1.0, 'top_p': 1.0} and
            native.get('seed') == 1917 and native.get('decoding_mode') == 'native-rectangular-grid-DFA',
            'actual native PUBLIC greedy decoder/seed differs')
    require(native.get('physical_event_id') in [e['event_id'] for e in events], 'native dispatch physical event unbound')
    if native.get('valid'):
        import hashlib
        ids, eos = native.get('output_token_ids'), native.get('native_eos_ids')
        require(type(ids) is list and ids and all(type(t) is int and t >= 0 for t in ids) and
                type(eos) is list and ids[-1] in eos and not any(t in eos for t in ids[:-1]) and
                native.get('output_tokens') == len(ids) and
                native.get('output_sha256') == hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest(),
                'native output token/EOS evidence differs')
        require(native.get('finish_reason') == 'eos' and native.get('dispatched') is True, 'valid native decode requires EOS')
        expected = lists(operation.inverse().apply(decode_grid(native['text'])))
        require(receipt['prediction'] == expected, 'native PUBLIC inverse/parser differs')


def verify_public_seal(seal, *, sources):
    """Truth-free verifier; this function never confers permission to read gold."""
    _source_check(sources)
    _exact(seal, ('format', 'path', 'file_sha256', 'selected_arm', 'coverage', 'status', 'production_admitted', 'publishable'), 'successor seal handle')
    require(seal['format'] == SEAL_FORMAT and seal['status'] == 'PUBLIC_SUCCESSOR_PREDICTIONS_SEALED' and
            seal['production_admitted'] is False and seal['publishable'] is False, 'explicit RL successor seal required')
    envelope = _read_ref({k: seal[k] for k in ('path', 'file_sha256')})
    _exact(envelope, ('format', 'scope', 'request', 'artifact', 'pool', 'coverage', 'selected_arm', 'source_sha256',
                      'generation_closed', 'model_closure_authority', 'production_admitted', 'publishable'), 'successor seal')
    require(envelope['format'] == SEAL_FORMAT and envelope['scope'] == SCOPE and envelope['generation_closed'] is True and
            envelope['model_closure_authority'] == 'parent-owned-ClosedCapability-required' and
            envelope['source_sha256'] == sources.sha256 and envelope['production_admitted'] is False and envelope['publishable'] is False,
            'successor seal binding differs')
    owner = Path(seal['path']).parent
    request = _read_ref(envelope['request'], owner=owner)
    _exact(request, ('format', 'scope', 'evidence_mode', 'backend_scope', 'experiment_plan_sha256',
                     'source_root', 'source_files', 'source_sha256', 'solver', 'challenge_ref', 'challenge_sha256',
                     'selected_arm', 'adapter_sha256', 'selected_checkpoint_manifest', 'selected_state_sha256',
                     'selected_reload', 'dev_selection', 'dev_predictions', 'inference_contract', 'planned_queries',
                     'planned_views', 'deadline', 'generation_started', 'query_targets_used', 'production_admitted',
                     'publishable'), 'successor request')
    require(request['format'] == REQUEST_FORMAT and request['scope'] == SCOPE and request['production_admitted'] is False and
            request['publishable'] is False and request['query_targets_used'] is False and
            request['source_root'] == sources.root and request['source_files'] == dict(sources.files) and
            request['source_sha256'] == sources.sha256, 'successor request/source binding differs')
    require(request['inference_contract']['transforms'] == [0, 1] and
            all(type(t) is int for t in request['inference_contract']['transforms']) and
            type(request['inference_contract']['seed']) is int and request['inference_contract']['seed'] == 1917 and
            request['inference_contract']['TTT'] is False and request['inference_contract']['do_sample'] is False and
            request['inference_contract']['maximum_answers'] == 2 and
            request['inference_contract']['temperature'] == 1.0 and request['inference_contract']['top_p'] == 1.0,
            'successor fixed inference differs')
    frozen = _read_ref(request['dev_selection'])
    dev = read_predictions(request['dev_predictions'])
    require(dev['scope'] == 'dev' and dev['experiment_plan_sha256'] == request['experiment_plan_sha256'] and
            frozen['dev_prediction_file_sha256'] == request['dev_predictions']['file_sha256'] and
            frozen['selected_arm'] == request['selected_arm'] in ('A', 'B', 'C') and frozen['holdout_labels_opened'] is False and
            frozen['rule'] == 'dev-exact-fixed-tie-A-B-C' and
            max(('A', 'B', 'C'), key=lambda a: frozen['scores'][a]['exact']) == request['selected_arm'] and
            dev['adapter_identities'][request['selected_arm']] == request['adapter_sha256'], 'dev-only selected adapter binding differs')
    _read_ref(request['selected_checkpoint_manifest'])
    require(request['selected_reload']['reload_verified'] is True and request['selected_reload']['same_source'] is True and
            request['selected_reload']['state_sha256'] == request['selected_state_sha256'], 'selected snapshot restore not verified')
    challenges = _read_ref(request['challenge_ref'], owner=owner)['challenges']
    require(digest(challenges) == request['challenge_sha256'], 'target-free challenge projection changed')
    if request['evidence_mode'] == 'public-development':
        require(request['solver']['manifest_sha256'] == SOLVER_MANIFEST_SHA256, 'original solver manifest differs')
        from tools.arc_public_research_20261010.public_data import load_solver_tasks
        solver = load_solver_tasks(request['solver']['root'], SOLVER_MANIFEST_SHA256)
        require(solver['challenges'] == challenges and len(_cases(challenges)) == 167 and request['planned_views'] == 334,
                'original167/334 projection differs')
    else:
        require(request['evidence_mode'] == 'synthetic-test-only' and request['solver'] is None and
                1 <= len(_cases(challenges)) <= 4, 'explicit bounded synthetic origin required')
    artifact = _read_ref(envelope['artifact'], owner=owner)
    _exact(artifact, ('format', 'request', 'selected_arm', 'adapter_sha256', 'rows', 'query_count', 'view_count',
                      'generation_ended', 'deadline_exceeded', 'query_targets_used', 'model_must_close_before_scoring',
                      'production_admitted', 'publishable'), 'successor artifact')
    require(artifact['model_must_close_before_scoring'] is True, 'PUBLIC model closure boundary required')
    require(artifact['format'] == ARTIFACT_FORMAT and artifact['request'] == envelope['request'], 'artifact/request binding differs')
    pool, coverage = _make_pool(request, artifact, challenges)
    require(_read_ref(envelope['pool'], owner=owner) == pool and coverage == envelope['coverage'] == seal['coverage'] and
            envelope['selected_arm'] == seal['selected_arm'] == request['selected_arm'], 'derived PUBLIC pool/seal differs')
    return {'seal': envelope, 'request': request, 'artifact': artifact, 'pool': pool, 'challenges': challenges}


def score_closed_public(capability, seal, *, sources, evaluator_root, output_root,
                        evaluator_manifest_sha256=EVALUATOR_MANIFEST_SHA256):
    """Parent-only CPU scorer; no caller Boolean or JSON authorizes label access.

    The supervisor capability must additionally bind the finished child's actual
    result file containing this exact issued seal. Unrelated closed children do
    not authorize a score. The durable journal is revalidated by the supervisor.
    """
    from owned_runtime.supervisor import verify_closed_capability
    closed = verify_closed_capability(capability)  # FIRST, before evaluator I/O.
    scoring_started=time.monotonic()
    require(closed['exit_observed_monotonic']<=scoring_started<closed['original_deadlines']['absolute'],'score requires verified exit and unexpired original absolute clock')
    outer_path=Path(closed['output_root'])/'outer-closure.json'
    require(outer_path.is_file() and json.loads(outer_path.read_text())==closed,'persisted actual outer closure required before scoring')
    outer_ref=_ref(outer_path)
    bundle = verify_public_seal(seal, sources=sources)
    _bind_closed_result(closed, seal, bundle)
    output = Path(output_root).resolve()
    evaluator = Path(evaluator_root).resolve()
    require(not output.exists(), 'PUBLIC scoring output identity consumed')
    require(output != evaluator and not output.is_relative_to(evaluator) and not evaluator.is_relative_to(output),
            'evaluator and score output must be separate')
    request, challenges = bundle['request'], bundle['challenges']
    from tools.arc_offline_evaluation import evaluate, load_pinned_reference
    require(time.monotonic()<closed['original_deadlines']['absolute'],'original absolute clock expired before evaluator I/O')
    if request['evidence_mode'] == 'synthetic-test-only':
        # Only explicitly controlled, tiny gold created for these CPU tests.
        # This is not the real evaluator path and never opens any real asset.
        require(evaluator_manifest_sha256 != EVALUATOR_MANIFEST_SHA256, 'synthetic gold cannot use real evaluator pin')
        gold = _read_ref({'path': str(evaluator / 'synthetic-gold.json'), 'file_sha256': evaluator_manifest_sha256})
        _exact(gold, ('format', 'challenges_sha256', 'solutions'), 'synthetic scorer gold')
        require(gold['format'] == _SYNTHETIC_GOLD_FORMAT and gold['challenges_sha256'] == digest(challenges), 'synthetic gold origin differs')
        solutions = gold['solutions']
    else:
        require(evaluator_manifest_sha256 == EVALUATOR_MANIFEST_SHA256, 'original evaluator manifest pin required')
        from tools.arc_public_research_20261010.public_data import validate_manifest
        # FIRST REAL EVALUATOR READ: owned inner+outer closure, journal, original
        # solver, selected checkpoint, complete view receipts and pool checked.
        manifest = validate_manifest(_read_ref({'path': str(evaluator / 'manifest.json'),
                                               'file_sha256': evaluator_manifest_sha256}), role='evaluator')
        from tools.arc_public_research_20261010.public_data import load_solver_tasks
        solver = load_solver_tasks(request['solver']['root'], SOLVER_MANIFEST_SHA256)
        require(manifest['identity'] == solver['identity'] and manifest['source'] == solver['manifest']['source'] and
                manifest['evidence_mode'] == 'public-development', 'original evaluator/solver identity differs')
        require(set(manifest['files']) == {'LICENSE', 'NOTICE', 'provenance.json', 'upstream-inventory.json'} |
                {'upstream/data/evaluation/' + key + '.json' for key in challenges}, 'original evaluator file roles differ')
        # Only the unchanged pinned loader below opens task files containing
        # gold. Authenticate its non-gold provenance input first.
        provenance = _regular(evaluator / 'provenance.json')
        require(file_sha(provenance) == manifest['source']['provenance_sha256'] and
                file_sha(provenance) == manifest['files']['provenance.json']['sha256'], 'original provenance bytes differ')
        original, solutions, reference = load_pinned_reference(evaluator / 'upstream', evaluator / 'provenance.json')
        require(original == challenges and reference['provenance_sha256'] == manifest['source']['provenance_sha256'],
                'original evaluator challenge/provenance differs')
    report = evaluate(challenges, solutions, bundle['pool'])  # unchanged pinned original scorer
    del solutions
    metrics = report['development_metrics']
    require(metrics['tasks'] == len(challenges) and metrics['tests'] == len(_cases(challenges)) and
            metrics['metrics']['pass_at_2']['denominator'] == len(_cases(challenges)), 'original scorer denominator changed')
    verify_closed_capability(capability)
    verify_public_seal(seal, sources=sources)
    pins = _source_check(sources)
    summary = {'format': REPORT_FORMAT, 'scope': SCOPE, 'status': ('PUBLIC_SUCCESSOR_EVALUATION_COMPLETE' if seal['coverage']['complete_prediction_coverage'] else
                                                                'PUBLIC_SUCCESSOR_EVALUATION_PARTIAL'),
               'evidence_mode': request['evidence_mode'], 'backend_scope': request['backend_scope'],
               'selected_arm': request['selected_arm'], 'prediction_seal': deepcopy(seal),
               'development_metrics': report['development_metrics'], 'scorer_sha256': pins['tools/arc_offline_evaluation.py'],
               'scorer_pins': pins, 'source_sha256': sources.sha256, 'official_score': None,
               'goal_met': False, 'production_admitted': False, 'publishable': False,
               'qualification': 'sealed runtime/scorer content; production and benchmark-goal eligibility require independent external validation'}
    scoring_finished=time.monotonic()
    require(scoring_finished<closed['original_deadlines']['absolute'],'original absolute clock expired during scorer')
    summary.update(scoring_started_monotonic=scoring_started,scoring_finished_monotonic=scoring_finished,
                   owner_outer_closure=outer_ref,owner_request_sha256=closed['request_sha256'],
                   owner_inner_closure_sha256=closed['inner_closure_sha256'])
    detail = write_json(output / 'evaluator-detail.json', {**summary, 'report': report})
    require(time.monotonic()<closed['original_deadlines']['absolute'],'original absolute clock expired before score completion')
    summary['detail'] = detail
    summary_ref = write_json(output / 'public-summary.json', summary)
    return {**summary, **summary_ref}


def _bind_closed_result(closed, seal, bundle):
    """Match supervisor-authenticated result evidence, never a caller result."""
    inner = _read_ref({'path': closed['inner_closure_path'], 'file_sha256': closed['inner_closure_sha256']},
                      owner=closed['output_root'])
    require(inner.get('request_sha256') == closed['request_sha256'], 'inner closure/request binding differs')
    result_ref = inner.get('result_ref')
    require(type(result_ref) is dict, 'closed capability lacks authenticated child result reference')
    result = _read_ref(result_ref, owner=closed['output_root'])
    flow = result.get('experiment', result)
    require(flow.get('public') == seal, 'PUBLIC seal not issued by this closed child')
    require(flow.get('status') in ('owned-comparison-complete-PUBLIC-sealed','owned-partial-comparison-PUBLIC-sealed'), 'unclosed selected PUBLIC cannot score')
    require(flow.get('plan_sha256') == bundle['request']['experiment_plan_sha256'], 'closed child experiment plan differs')
    events = _read_ref(flow['physical_events_ref'],owner=closed['output_root']) if flow.get('physical_events_ref') else flow.get('physical_events')
    require(type(events) is list, 'closed child physical evidence absent')
    by_id = {e['event_id']: e for e in events}
    require(len(by_id) == len(events), 'duplicate closed physical event IDs')
    for row in bundle['artifact']['rows']:
        for compact in row['generations']:
            view = _read_ref(compact['receipt'])
            for event in view['physical_events']:
                require(by_id.get(event['event_id']) == event, 'PUBLIC physical event absent from closed durable child result')
