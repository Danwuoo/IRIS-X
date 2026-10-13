"""Prospective 63-case experiment, disk-reloaded candidates, and sealed scoring.

Only the final score_sealed_predictions function consumes held-out target escrow.
All generator/VM/selector arguments are closed target-free projections. Physical
work is never restored when a logical branch or checkpoint is restored.
"""
from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
import math
from pathlib import Path
import time

from .protocol import PROTOCOL, digest, require, file_sha
from .panel_contract import DENOMINATORS, solver_case, context_eligibility
from .selection import (rank_checkpoints, select_program_portfolio, seal_selection,
                        verify_selection_seal, source_digest, VERIFIER_SHA256,
                        QUERY_VERIFIER_SHA256)
from .checkpoints import (save_branch_checkpoint, load_branch_checkpoint,
                          load_inference_adapter, inspect_checkpoint)
from tools.arc_learning_agent_20261011.budget import atomic_json, BudgetExceeded
from tools.arc_learning_agent_20261011.grid_codec import (grid_messages, program_messages,
                                                         decode_grid, encode_grid)
from tools.arc_learning_agent_20261011.program_tools import verify_program, execute_queries
from tools.arc_qwen_probe_20261012.science_profiles import BranchLedger
from tools.arc_qwen_probe_20261012.experiment import run_ladder

CANDIDATE_ORDER = ('base', 'grid8', 'grid16', 'program8', 'program16')


def delta(before, after):
    require(all(after[k] >= v for k, v in before.items()), 'physical ledger regressed')
    return {k: after[k] - before.get(k, 0) for k in after}


def _deadline(deadline):
    if time.monotonic() >= deadline:
        raise BudgetExceeded('experiment deadline; no further model or VM work dispatched')


def _messages(case, kind):
    case = solver_case(case)
    if kind == 'grid':
        return grid_messages(case['demos'], case['query_input'])
    require(kind == 'program', 'unknown generation kind')
    return program_messages({'train': case['demos'], 'test': [{'input': case['query_input']}]})


def _missing_generation(reason):
    return {'valid': False, 'dispatched': False, 'text': '', 'output_token_ids': [],
            'finish_reason': 'not_run', 'error': reason, 'omitted': True}


def _empty_row(case, reason='checkpoint not reached'):
    return {'case_id': case['case_id'], 'scope': case['scope'],
            'grid_generation': _missing_generation(reason),
            'program_generation': _missing_generation(reason),
            'grid_prediction': None, 'program_prediction': None,
            'program_demo_proof': None, 'program_query_receipt': None,
            'program_all_demos_fit': False, 'canary_grid_score': None,
            'row_complete': False, 'omission_reason': reason}


def _generate(model, messages, kind, deadline):
    _deadline(deadline)
    caps = model.config.get('probe_fixture_generation_caps', {}) if model.config.get('tiny_cpu') is True else {}
    cap = caps.get(kind, PROTOCOL[kind + '_output_cap'])
    result = model.generate(messages, kind=kind, seed=PROTOCOL['seed'], max_new_tokens=cap, deadline=deadline)
    require(type(result.get('dispatched')) is bool, 'generation physical dispatch receipt required')
    return result


def _vm(ledger, event, operation):
    ledger.reserve(event, {'cpu_checks': 1, 'gas': 200000})
    try:
        result = operation()
        ledger.complete(event, {'cpu_checks': int(result.get('receipt', result).get('dispatched', 0)),
                                'gas': result['gas_charged']})
        return result
    except BaseException as exc:
        if event in ledger.pending:
            ledger.unknown(event, type(exc).__name__)
        raise


def _canary_score(model, case, canary_targets, deadline):
    require(case['scope'] == 'canary' and case['case_id'] in canary_targets,
            'teacher forcing restricted to approved canaries before sealing')
    messages = _messages(case, 'grid')
    completion = encode_grid(canary_targets[case['case_id']])
    binding = digest({'messages': messages, 'completion': completion})
    try:
        prepared = model.prepare_completion(messages, completion)
        require(prepared['prompt_tokens'] <= 1792 and prepared['completion_tokens'] <= 256
                and prepared['input_tokens'] <= 2048, 'context: whole canary completion exceeds bounds')
    except ValueError as exc:
        if not any(s in str(exc).lower() for s in ('context', 'prompt', 'length', 'completion')):
            raise
        return {'valid': False, 'dispatched': False, 'error': str(exc),
                'whole_example_excluded': True, 'example_sha256': binding}
    _deadline(deadline)
    result = model.score_completion(messages, completion, deadline=deadline)
    require(type(result.get('dispatched')) is bool, 'scoring physical dispatch receipt required')
    return {**result, 'example_sha256': binding}


def _persist_row(path, row):
    # Raw bytes do not contain their own digest. The compact seal binds this file.
    atomic_json(path, {k:v for k,v in row.items() if k not in ('receipt_path','receipt_sha256')})
    row['receipt_path'] = str(Path(path).absolute())
    row['receipt_sha256'] = file_sha(path)


def _compact_observation(observation):
    """Bind full on-disk receipts while avoiding repeated per-token forward traces."""
    result = {k: deepcopy(v) for k,v in observation.items() if k != 'rows'}
    result['rows'] = []
    for source in observation['rows']:
        row = {k: deepcopy(v) for k,v in source.items()
               if k not in ('grid_generation', 'program_generation', 'program_demo_proof', 'program_query_receipt')}
        for kind in ('grid', 'program'):
            generation = source[kind + '_generation']
            row[kind + '_generation'] = {k: deepcopy(generation[k]) for k in (
                'valid','dispatched','text','output_token_ids','finish_reason','error','physical_event_id',
                'input_tokens','output_tokens','whole_example_excluded','omitted') if k in generation}
            row[kind + '_generation']['full_receipt_sha256'] = digest(generation)
        for key in ('program_demo_proof', 'program_query_receipt'):
            value = source[key]
            row[key + '_sha256'] = digest(value) if value is not None else None
        result['rows'].append(row)
    return result


def evaluate_candidate(model, ledger, cases, canary_targets, eligibility, output,
                       candidate_id, deadline, observation):
    """Populate observation incrementally; never receives held-out target escrow."""
    root = Path(output) / candidate_id
    root.mkdir(parents=True, exist_ok=False)
    before = dict(ledger.used); started = time.monotonic()
    eligible = {r['case_id']: r['representations'] for r in eligibility['rows']}
    observation.update(candidate_id=candidate_id, rows=[_empty_row(c) for c in cases],
                       complete=False, heldout_targets_accessed=False)
    try:
        for index, (case, row) in enumerate(zip(cases, observation['rows'])):
            _deadline(deadline)
            case = solver_case(case)
            path = root / ('case-%03d.json' % index)
            for kind in ('grid', 'program'):
                if not eligible[case['case_id']][kind]['eligible']:
                    row[kind + '_generation'] = {**_missing_generation(eligible[case['case_id']][kind]['exclusion_reason']),
                                                'finish_reason': 'context_excluded', 'omitted': False,
                                                'whole_example_excluded': True}
                else:
                    row[kind + '_generation'] = _generate(model, _messages(case, kind), kind, deadline)
                _persist_row(path, row)
                generation = row[kind + '_generation']
                require(not generation.get('fatal_error', False), 'fatal ' + kind + ' generation')
                if kind == 'grid' and generation.get('valid'):
                    try:
                        row['grid_prediction'] = decode_grid(generation['text'])
                    except ValueError:
                        pass
                if kind == 'program' and generation.get('valid'):
                    _deadline(deadline)
                    event = 'portfolio-' + digest(str(root.absolute()))[:20] + '-vm-' + str(index)
                    proof = _vm(ledger, event, lambda: verify_program(generation['text'], case['demos'],
                                root / 'vm', str(index) + '-demos', deadline=deadline))
                    row['program_demo_proof'] = proof
                    row['program_all_demos_fit'] = bool(proof['all_demos_fit'])
                    _persist_row(path, row)
                    if proof['all_demos_fit']:
                        _deadline(deadline)
                        query = _vm(ledger, event + '-query', lambda: execute_queries(proof,
                                    [case['query_input']], root / 'vm', str(index) + '-query', deadline=deadline))
                        row['program_query_receipt'] = query
                        if query['results'] and query['results'][0]['status'] == 'valid':
                            row['program_prediction'] = query['results'][0]['output']
            row.update(row_complete=True, omission_reason=None)
            _persist_row(path, row)
        # Teacher forcing only the development canaries. No held-out gold is in scope.
        for index, (case, row) in enumerate(zip(cases, observation['rows'])):
            if case['scope'] == 'canary':
                row['canary_grid_score'] = _canary_score(model, case, canary_targets, deadline)
                _persist_row(root / ('case-%03d.json' % index), row)
        _deadline(deadline)
        observation['complete'] = True
    finally:
        # A failure between generation, decoding and VM dispatch still seals the
        # latest known row, not stale pre-decoding bytes. No new model work here.
        for row in observation['rows']:
            if 'receipt_path' in row:
                _persist_row(Path(row['receipt_path']), row)
        observation.update(physical_usage=delta(before, ledger.used), elapsed_seconds=time.monotonic() - started)
        atomic_json(root / 'diagnostics.json', _compact_observation(observation))
    return observation


def _parity_probe(model, case, canary_targets, output, deadline):
    """Small fixed canary only. Actual token sequences and exact NLL, never gold choice."""
    generations = {}
    for kind in ('grid', 'program'):
        value = _generate(model, _messages(case, kind), kind, deadline)
        generations[kind] = value
        atomic_json(Path(output) / (kind + '-generation.json'), value, exclusive=True)
        require(value.get('dispatched') and value.get('output_token_ids')
                and not value.get('fatal_error', False), 'reload parity generation incomplete')
    score = _canary_score(model, case, canary_targets, deadline)
    atomic_json(Path(output) / 'grid-score.json', score, exclusive=True)
    require(score.get('valid') and math.isfinite(score.get('nll_sum', float('nan'))),
            'fixed canary reload NLL unavailable')
    return {'case_id': case['case_id'],
            'output_token_ids': {k: v['output_token_ids'] for k, v in generations.items()},
            'finish_reasons': {k: v.get('finish_reason') for k, v in generations.items()},
            'nll_sum': score['nll_sum'], 'token_count': score['token_count']}


def _shape_equal(prediction, target):
    return prediction is not None and (len(prediction), len(prediction[0])) == (len(target), len(target[0]))


def _canary_rankings(cases, observations, canary_targets):
    canaries = [c for c in cases if c['scope'] == 'canary']
    rankings = []
    for branch in ('grid', 'program'):
        rows = []
        for update in (0, 8, 16):
            candidate = 'base' if update == 0 else branch + str(update)
            indexed = {r['case_id']: r for r in observations[candidate]['rows']}
            for case in canaries:
                row = indexed[case['case_id']]; target = canary_targets[case['case_id']]
                item = {'branch': branch, 'scope': 'canary', 'case_id': case['case_id'],
                        'checkpoint_update': update}
                if branch == 'grid':
                    score = row.get('canary_grid_score')
                    nll = ({k: score[k] for k in ('nll_sum', 'token_count', 'example_sha256')}
                           if score and score.get('valid') else None)
                    item.update(grid_exact=row['grid_prediction'] == target,
                                grid_shape_correct=_shape_equal(row['grid_prediction'], target),
                                grid_valid=row['grid_prediction'] is not None, grid_nll=nll)
                else:
                    item.update(program_exact=row['program_prediction'] == target,
                                program_all_demos_fit=row['program_all_demos_fit'],
                                program_valid_query=row['program_prediction'] is not None)
                rows.append(item)
        rankings.append(rank_checkpoints(branch, rows, [c['case_id'] for c in canaries], minimum_canaries=8))
    return rankings


def _project_program(case, row, candidate_id, checkpoint_sha256):
    """Project verified bounded-VM receipts, without fabricating proof claims."""
    generation = row['program_generation']
    valid = generation.get('valid') is True
    result = {'candidate_id': candidate_id, 'checkpoint_sha256': checkpoint_sha256,
              'generation_status': 'valid' if valid else 'invalid' if generation.get('dispatched') else 'unavailable',
              'source_sha256': source_digest(generation['text']) if valid else None,
              'proof': None, 'query': None}
    if not valid:
        return result
    proof = row['program_demo_proof']
    if proof is None:
        return result
    receipt = proof['receipt']
    matched = [i for i, r in enumerate(receipt.get('demos', [])) if r.get('status') == 'match']
    result['proof'] = {'source_sha256': proof['source_sha256'], 'demos_sha256': digest(case['demos']),
                       'verifier_sha256': VERIFIER_SHA256, 'proof_sha256': proof['proof_sha256'],
                       'known': receipt['known'], 'all_demos_fit': proof['all_demos_fit'],
                       'demo_count': len(case['demos']), 'matched_demo_indices': matched,
                       'owned_descendants_stopped': receipt['owned_descendants_stopped']}
    query = row['program_query_receipt']
    if query is not None and query['results']:
        item = query['results'][0]
        valid_query = item['status'] == 'valid'
        result['query'] = {'source_sha256': proof['source_sha256'], 'demos_sha256': digest(case['demos']),
            'query_input_sha256': digest(case['query_input']), 'demo_proof_sha256': proof['proof_sha256'],
            'verifier_sha256': QUERY_VERIFIER_SHA256,
            'status': 'valid' if valid_query else 'invalid' if item['dispatched'] else 'unavailable',
            'output': item['output'] if valid_query else None,
            'demo_replay_verified': bool(valid_query and query['demo_replay_in_each_query']
                and (item.get('verifier') or {}).get('all_demonstrations_exact', False)),
            'owned_descendants_stopped': item['owned_descendants_stopped']}
    return result


def _portfolio_decisions(cases, observations, checkpoint_receipts):
    indexed = {name: {r['case_id']: r for r in observation['rows']}
               for name, observation in observations.items()}
    decisions = []
    for case in cases:
        candidates = []
        for name in ('base', 'program8', 'program16'):
            receipt = checkpoint_receipts.get(name)
            # An omitted checkpoint still has an explicit immutable omission identity.
            checkpoint_sha = receipt['manifest_sha256'] if receipt else digest({'checkpoint': name, 'omitted': True})
            candidates.append(_project_program(case, indexed[name][case['case_id']], name, checkpoint_sha))
        decisions.append(select_program_portfolio({'task_id': case['case_id'], 'demos': case['demos'],
                                                  'query_input': case['query_input']}, candidates))
    return decisions


def seal_predictions(root, cases, observations, decisions, rankings):
    """Durable full-candidate commitment before any held-out target is opened."""
    selection = seal_selection(decisions, rankings, digest(PROTOCOL))
    atomic_json(Path(root) / 'selection-sealed.json', selection, exclusive=True)
    payload = {'format': 'irisx/qwen-all-candidate-predictions-v1',
               'case_ids': [c['case_id'] for c in cases], 'candidate_order': list(CANDIDATE_ORDER),
               'denominators': DENOMINATORS,
               'candidate_predictions': {k: _compact_observation(v) for k,v in observations.items()},
               'selection': selection, 'heldout_targets_accessed': False}
    atomic_json(Path(root) / 'predictions-sealed.json', payload, exclusive=True)
    seal = {'format': 'irisx/qwen-prediction-seal-v1', 'sealed': True,
            'case_ids': payload['case_ids'], 'prediction_sha256': digest(payload),
            'selection_sha256': selection['selection_sha256'],
            'prediction_file_sha256': file_sha(Path(root) / 'predictions-sealed.json'),
            'artifact_path': str((Path(root) / 'predictions-sealed.json').absolute()),
            'sealed_monotonic': time.monotonic(), 'heldout_targets_accessed': False}
    atomic_json(Path(root) / 'prediction-seal.json', seal, exclusive=True)
    # Phase receipt is itself exclusively durable. No target loader has run yet.
    atomic_json(Path(root) / 'phase-predictions-sealed.json', seal, exclusive=True)
    verify_selection_seal(selection, seal['selection_sha256'], digest(PROTOCOL))
    require(digest(payload) == seal['prediction_sha256'], 'prediction commitment differs')
    return seal, payload


def _method_summary(cases, predictions, targets, reference):
    result = {}
    for scope, denominator in DENOMINATORS.items():
        ids = [c['case_id'] for c in cases if c['scope'] == scope]
        require(len(ids) == denominator, 'fixed scoring denominator changed')
        def hits(mapping, key):
            values = mapping[key]
            return bool(values and values[0] == targets[key]), any(v == targets[key] for v in values[:2])
        first = second = gains1 = losses1 = gains2 = losses2 = 0
        for key in ids:
            one, two = hits(predictions, key); base1, base2 = hits(reference, key)
            first += one; second += two
            gains1 += one and not base1; losses1 += base1 and not one
            gains2 += two and not base2; losses2 += base2 and not two
        result[scope] = {'denominator': denominator, 'pass_at_1_count': first, 'pass_at_2_count': second,
            'pass_at_1': first / denominator, 'pass_at_2': second / denominator,
            'abstentions': sum(not predictions[key] for key in ids),
            'paired_vs_frozen_base': {'pass_at_1_gains': gains1, 'pass_at_1_losses': losses1,
                                    'pass_at_2_gains': gains2, 'pass_at_2_losses': losses2}}
    return result


def score_sealed_predictions(dataset, seal, payload):
    """Offline scoring only: this function is the sole noncanary-gold consumer."""
    from .data import open_target_escrow
    require(seal['sealed'] and digest(payload) == seal['prediction_sha256'], 'unsealed scoring denied')
    targets = open_target_escrow(dataset, {**seal, 'payload': payload,
        'artifact_path': seal['artifact_path'], 'artifact_sha256': seal['prediction_file_sha256']})
    targets = {**targets, **dataset['canary_targets']}
    cases = dataset['solver_cases']
    require(set(targets) == {c['case_id'] for c in cases}, 'escrow target coverage differs')
    methods = {}
    for name, observation in payload['candidate_predictions'].items():
        for kind in ('grid', 'program'):
            methods[name + ':' + kind] = {r['case_id']: [r[kind + '_prediction']] if r[kind + '_prediction'] is not None else []
                                          for r in observation['rows']}
    rankings = payload['selection']['payload']['rankings']
    for ranking in rankings:
        branch = ranking['branch']; update = ranking['best_checkpoint_update']
        name = 'base' if update == 0 else branch + str(update)
        methods['canary_selected:' + branch] = deepcopy(methods[name + ':' + branch])
    methods['fixed_program_portfolio'] = {d['task_id']: d['top2'] for d in payload['selection']['payload']['decisions']}
    summaries = {}
    for name, predictions in methods.items():
        reference_kind = 'grid' if name.endswith(':grid') else 'program'
        summaries[name] = _method_summary(cases, predictions, targets, methods['base:' + reference_kind])
    oracle = {}
    for scope, denominator in DENOMINATORS.items():
        ids = [c['case_id'] for c in cases if c['scope'] == scope]
        oracle[scope] = {'denominator': denominator, 'any_fixed_program_candidate_correct': sum(
            any(targets[key] in methods[name + ':program'][key] for name in ('base', 'program8', 'program16')) for key in ids)}
    return {'format': 'irisx/qwen-post-seal-scoring-v1', 'prediction_sha256': seal['prediction_sha256'],
            'scoring_started_monotonic': time.monotonic(), 'summaries': summaries,
            'posthoc_oracle_diagnostic': {'used_for_selection': False, 'scope': 'upper bound over all three fixed program candidates; not achieved pass@2', 'strata': oracle},
            'full_denominators_retained': True, 'holdout_teacher_forcing_performed': False}


def train_checkpoint(trainer, records, steps, deadline, path):
    """Persist charged work including rejected late/failed optimizer boundaries."""
    try:
        receipt = trainer.train(records, max_steps=steps, deadline=deadline)
    except BaseException as exc:
        atomic_json(path, {'checkpoint_admissible': False, 'error': type(exc).__name__ + ': ' + str(exc),
                          'failure_receipt': getattr(exc, 'receipt', None)}, exclusive=True)
        raise
    late = time.monotonic() >= deadline
    result = {**receipt, 'completed_after_deadline': late,
              'checkpoint_admissible': not late and receipt.get('status') == 'complete'}
    atomic_json(path, result, exclusive=True)
    require(not late and result['checkpoint_admissible'], 'late or incomplete training checkpoint')
    return result


def native_matching(model, records, cases):
    rows = []
    for record in records:
        try:
            prepared = model.prepare_completion(record['messages'], record['completion'])
            rows.append({'record_id': record['record_id'], 'kind': record['kind'], 'eligible': True,
                         **{k: prepared[k] for k in ('prompt_tokens', 'completion_tokens', 'input_tokens', 'prepared_sha256')}})
        except ValueError as exc:
            if not any(s in str(exc).lower() for s in ('context', 'prompt', 'length', 'completion')):
                raise
            rows.append({'record_id': record['record_id'], 'kind': record['kind'], 'eligible': False, 'reason': str(exc)})
    return {'training_records': rows, 'evaluation_prompts': context_eligibility(cases, model),
            'full_training_denominator': len(records), 'full_evaluation_case_denominator': len(cases),
            'heldout_targets_inspected': False, 'training_source': 'authored families only; real ARC training stage disabled'}


def run_experiment(model, trainer, ledger, dataset, output, deadline, *, feasibility,
                   checkpoints=None, fail_before_train=False):
    root = Path(output); root.mkdir(parents=True, exist_ok=False)
    require(checkpoints is None or list(checkpoints) == [8, 16], 'fixed checkpoint updates8/16 required')
    require(model.decoder_policy['selected_profile'] == 'portfolio-cached-63', 'locked portfolio profile required')
    require(model.decoder_policy['selected_mode'] == 'cached', 'cached-only prospective experiment')
    cases = [solver_case(c) for c in dataset['solver_cases']]
    require(len({c['case_id'] for c in cases}) == 63, 'exact63 distinct fixed cases required')
    require({scope: sum(c['scope'] == scope for c in cases) for scope in DENOMINATORS} == DENOMINATORS,
            'fixed panel denominators differ')
    canaries = [c for c in cases if c['scope'] == 'canary']
    canary_targets = deepcopy(dataset['canary_targets'])
    require(set(canary_targets) == {c['case_id'] for c in canaries}, 'closed eight-canary target map required')
    records = {kind: [r for r in dataset['records'] if r['kind'] == kind] for kind in ('grid', 'program')}
    require(all(rows and all(r['split'] == 'train' for r in rows) for rows in records.values()), 'train-only branch records required')
    require(PROTOCOL['real_arc_training_stage_enabled'] is False, 'undeclared realARC training stage forbidden')
    matching = native_matching(model, dataset['records'], cases)
    atomic_json(root / 'native-matching.json', matching, exclusive=True)
    eligibility = matching['evaluation_prompts']
    allowances = {'seconds': feasibility['per_branch_allowance_seconds'],
                  'input_tokens': feasibility['per_branch_allowance_input_tokens']}
    require(allowances['seconds'] > 0 and allowances['input_tokens'] > 0, 'positive paired branch allowances required')
    atomic_json(root / 'branch-allowances.json', {'grid_lora': allowances, 'program_lora': allowances,
                                               'budget_transfer_allowed': False}, exclusive=True)
    physical = ledger; before_all = dict(physical.used); started = time.monotonic()
    original = trainer.snapshot_training_state('portfolio-clean-original')
    observations = {name: {'candidate_id': name, 'rows': [_empty_row(c) for c in cases],
                           'complete': False, 'heldout_targets_accessed': False,
                           'checkpoint': {'available': False, 'candidate_id': name,
                               'manifest_sha256': digest({'checkpoint': name, 'omitted': True})}} for name in CANDIDATE_ORDER}
    checkpoints_saved = {}; branches = {}; reset_receipts = []; parity_receipts = {}
    error = None; clean_reset = False; behavior_parity = False; base_reference = None
    raw = trainer.trainer
    provenance = {'protocol_sha256': digest(PROTOCOL), 'case_ids_sha256': digest([c['case_id'] for c in cases]),
                  'training_source': 'authored only', 'holdout_gold_accessed': False,
                  'shared_update0_reference_for': ['grid_lora','program_lora']}

    def restore_original(label):
        before = dict(physical.used)
        result = trainer.restore_training_state(original)
        check = trainer.snapshot_training_state(label)
        try:
            require(check['state_sha256'] == original['state_sha256'], 'complete clean original state differs')
        finally:
            trainer.release_training_state(check)
        require(dict(physical.used) == before, 'logical restore changed physical accounting')
        reset_receipts.append({'label': label, **result})
        return result

    def persist_and_evaluate(candidate_id, branch, kind, update, local_deadline):
        nonlocal base_reference
        _deadline(local_deadline)
        saved = save_branch_checkpoint(trainer, root / 'checkpoint-assets', branch_id=branch,
                                       update=update, records=records[kind], provenance=provenance)
        checkpoints_saved[candidate_id] = saved
        observations[candidate_id]['checkpoint'] = {'available': True, 'candidate_id': candidate_id,
            **{k:saved[k] for k in ('manifest_sha256','state_sha256','adapter_sha256','branch_id','update')}}
        atomic_json(root / 'checkpoint-receipts.json', checkpoints_saved)
        context = model.adapter_branch('base') if candidate_id == 'base' else nullcontext()
        with context:
            before = _parity_probe(model, canaries[0], canary_targets,
                                   root / 'reload-parity' / candidate_id / 'before', local_deadline)
        restore_original(candidate_id + '-pre-inference-clean')
        loaded = load_inference_adapter(trainer, saved['path'], branch_id=branch, records=records[kind],
                                        expected_manifest_sha256=saved['manifest_sha256'], provenance=provenance)
        with model.adapter_branch('base') if candidate_id == 'base' else nullcontext():
            after = _parity_probe(model, canaries[0], canary_targets,
                                  root / 'reload-parity' / candidate_id / 'after', local_deadline)
            require(before == after, 'exact disk inference token/NLL canary parity differs')
            if candidate_id == 'base':
                base_reference = deepcopy(after)
            parity_receipts[candidate_id] = {'inference_load': loaded, 'before': before, 'after': after,
                'output_token_parity': True, 'nll_exact_parity': True, 'clean_reset_verified': True,
                'fresh_backend_reload_verified': False}
            atomic_json(root / 'reload-parity' / candidate_id / 'parity.json', parity_receipts[candidate_id], exclusive=True)
            evaluate_candidate(model, model.ledger, cases, canary_targets, eligibility, root / 'candidates',
                               candidate_id, local_deadline, observations[candidate_id])
        # A separate complete disk load restores Adam/scheduler/RNG/sampler for the next update.
        restore_original(candidate_id + '-pre-resume-clean')
        resume = load_branch_checkpoint(trainer, saved['path'], branch_id=branch, records=records[kind],
                                        expected_manifest_sha256=saved['manifest_sha256'], provenance=provenance)
        require(resume['state_sha256'] == saved['state_sha256'], 'disk resume state differs')
        parity_receipts[candidate_id]['complete_resume_load'] = resume
        atomic_json(root / 'reload-parity' / candidate_id / 'resume.json', resume, exclusive=True)

    try:
        persist_and_evaluate('base', 'grid_lora', 'grid', 0, deadline)
        # Retain equal predeclared allowances. Never enlarge the second after the first finishes.
        remaining = deadline - time.monotonic()
        reserve = feasibility.get('common_reserve_seconds', 0)
        require(remaining >= 2 * allowances['seconds'] + reserve,
                'base work overran common forecast; equal paired branch budgets no longer fit')
        for branch, kind in (('grid_lora', 'grid'), ('program_lora', 'program')):
            restore_original(branch + '-initial')
            branch_ledger = BranchLedger(physical, input_tokens=allowances['input_tokens'],
                                         seconds=allowances['seconds'], name=branch)
            model.ledger = trainer.ledger = branch_ledger
            local_deadline = min(deadline, branch_ledger.deadline)
            branch_before = dict(physical.used); training_receipts = []
            report = {'status': 'incomplete', 'objective': kind, 'checkpoint_ids': ['base'],
                      'initial_state_sha256': original['state_sha256'],
                      'training_receipts': training_receipts, 'optimizer_updates': 0,
                      'supervised_tokens': 0, 'training_input_tokens': 0,
                      'shared_update0_checkpoint': checkpoints_saved['base']}
            branches[branch] = report
            try:
                if fail_before_train:
                    raise RuntimeError('injected before_train boundary')
                for update in (8, 16):
                    _deadline(local_deadline)
                    receipt = train_checkpoint(trainer, records[kind], update - report['optimizer_updates'],
                                               local_deadline, root / branch / ('training-' + str(update) + '.json'))
                    training_receipts.append(receipt)
                    report['optimizer_updates'] += receipt['optimizer_steps']
                    report['supervised_tokens'] += receipt['supervised_tokens']
                    report['training_input_tokens'] += receipt['input_tokens']
                    require(report['optimizer_updates'] == update and report['optimizer_updates'] <= 16,
                            'checkpoint optimizer count differs')
                    require(report['supervised_tokens'] <= 32768 and report['training_input_tokens'] <= 32768,
                            'branch physical training token cap exceeded')
                    persist_and_evaluate(kind + str(update), branch, kind, update, local_deadline)
                    report['checkpoint_ids'].append(kind + str(update))
                report['status'] = 'complete'
            finally:
                report.update(branch_budget=branch_ledger.receipt(), physical_usage=delta(branch_before, physical.used))
                atomic_json(root / branch / 'branch-report.json', report)
                model.ledger = trainer.ledger = physical
                restore_original(branch + '-final')
        restore_original('final-clean-before-behavior')
        with model.adapter_branch('base'):
            final_reference = _parity_probe(model, canaries[0], canary_targets, root / 'final-clean-parity', deadline)
        require(final_reference == base_reference, 'final clean frozen-base token/NLL behavior differs')
        behavior_parity = True
    except Exception as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)[:2048]}
    finally:
        model.ledger = trainer.ledger = physical
        try:
            restore_original('cleanup-exact-original')
            clean_reset = True
        except Exception as exc:
            clean_reset = False
            error = {'type': type(exc).__name__, 'message': 'cleanup restore failed: ' + str(exc)[:2048], 'previous': error}
        finally:
            trainer.release_training_state(original)
    # Even an interrupted branch produces an all-candidate, full-denominator seal.
    rankings = _canary_rankings(cases, observations, canary_targets)
    decisions = _portfolio_decisions(cases, observations, checkpoints_saved)
    seal, payload = seal_predictions(root, cases, observations, decisions, rankings)
    scoring = score_sealed_predictions(dataset, seal, payload)
    atomic_json(root / 'post-seal-scoring.json', scoring, exclusive=True)
    complete = error is None and clean_reset and behavior_parity and all(o['complete'] for o in observations.values())
    manifests = {name: inspect_checkpoint(r['path'], expected_manifest_sha256=r['manifest_sha256'])
                 for name, r in checkpoints_saved.items()}
    disk_assets = {'root': str((root / 'checkpoint-assets').absolute()), 'archive_exclusion_required': True,
                   'checkpoint_receipts': checkpoints_saved, 'manifests': manifests,
                   'all_candidates_preserved': len(checkpoints_saved) == 5,
                   'disk_resume_verified': sorted(k for k,v in parity_receipts.items() if 'complete_resume_load' in v)}
    atomic_json(root / 'disk-assets.json', disk_assets, exclusive=True)
    report = {'format': 'irisx/qwen14b-prospective-portfolio-experiment-v1',
        'status': 'PORTFOLIO_COMPLETE' if complete else 'PORTFOLIO_PARTIAL',
        'science_complete': complete, 'operational_success': complete, 'error': error,
        'cpu_fixture_only': model.config.get('tiny_cpu') is True,
        'protocol': PROTOCOL, 'protocol_sha256': digest(PROTOCOL),
        'science_profile': model.decoder_policy['selected_profile'], 'decoder_policy': model.decoder_policy,
        'decoder_policy_sha256': model._decoder_policy_sha256,
        'feasibility': feasibility, 'native_matching': matching, 'branches': branches,
        'denominators': DENOMINATORS, 'selected_case_ids': [c['case_id'] for c in cases],
        'omitted_case_ids': [], 'candidate_completion': {k: v['complete'] for k,v in observations.items()},
        'candidate_omissions': {k: [r['case_id'] for r in v['rows'] if not r['row_complete']] for k,v in observations.items()},
        'all_candidate_predictions_path': str(root / 'predictions-sealed.json'),
        'prediction_seal': seal, 'rankings': rankings, 'scoring': scoring,
        'disk_assets': disk_assets, 'checkpoint_reload_parity': parity_receipts,
        'reset_receipts': reset_receipts, 'final_clean_reset_exact': clean_reset,
        'final_clean_behavior_parity': behavior_parity,
        'fresh_backend_reload_verified': False,
        'reload_scope': 'same live native Qwen/PEFT backend after exact clean reset; disk inference tensors and complete disk resume verified separately',
        'reload_reference': ({'checkpoint': checkpoints_saved['program16'], 'branch_id': 'program_lora',
            'records_sha256': digest(records['program']), 'records_count': len(records['program']),
            'canary_case': canaries[0], 'canary_target': canary_targets[canaries[0]['case_id']],
            'expected': parity_receipts['program16']['after'],
            'expected_receipt_directory': str((root / 'reload-parity' / 'program16' / 'after').absolute()),
            'provenance': provenance} if 'program16' in parity_receipts else None),
        'physical_usage': delta(before_all, physical.used), 'elapsed_seconds': time.monotonic() - started,
        'branch_work_matched_by': 'fixed case/checkpoint order, equal independent budgets, exact16optimizer-update ceilings',
        'base_full_panel_generated_once': True, 'selected_checkpoint_full_panel_replayed': False,
        'real_arc_training_stage_enabled': False,
        'interpretation': 'transfer from authored training; full14B prospective accuracy untested until manual GPU run',
        'public_score': None, 'public_solving_admitted': False, 'production_effectiveness_gate_changed': False}
    atomic_json(root / 'full-report.json', report, exclusive=True)
    atomic_json(root / 'compact-report.json', {k: report[k] for k in ('status', 'science_complete', 'operational_success',
        'cpu_fixture_only', 'error', 'denominators', 'candidate_completion', 'prediction_seal', 'scoring',
        'physical_usage', 'elapsed_seconds', 'final_clean_reset_exact', 'interpretation')}, exclusive=True)
    return report
