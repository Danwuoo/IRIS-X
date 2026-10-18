"""Paired train-derived task-adaptation diagnosis, never PUBLIC selection.

Runs the admitted compact engine at identical views before and after 32 demo-only
updates. This is a full-model callable, not a claim of completed GPU validation.
The prior selection panel is excluded, but inherited weight exposure remains.
"""
from __future__ import annotations

import hashlib
import math
import random
import time

from tools.arc2_goal_sprint_20261017.data import canonical, digest, inference_views, loo_example, transform, view_inputs
from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, adapter_state, check_deadline, restore_state, state_digest
from src.irisx.arc_nvarc_data import known_variant_group
from .codec import encode_example, parse_completion
from .experiment import adapt_task, infer_query, panel_ids

PROTOCOL = 'compact-paired-ttt-stability-v1'
# Fixed engineering acceptance bounds, not empirically calibrated GPU error bars.
# A violation denies the comparison; it never silently loosens this protocol.
RESET_PROBE_ATOL = 1e-6
RESET_PROBE_RTOL = 1e-5
COUNTERS = ('forward_calls', 'sampled_tokens', 'optimizer_steps', 'optimizer_attempts',
            'generation_forward_attempts', 'generation_input_tokens', 'generation_row_token_slots',
            'generation_finished_row_token_slots', 'generation_padding_tokens')


def select_panel(dev, *, count=32, previous_count=24):
    if (type(count) is not int or not 1 <= count <= 64 or type(previous_count) is not int
            or not 0 <= previous_count < len(dev)):
        raise ValueError('bounded new development panel required')
    excluded = set(panel_ids(dev, previous_count)) if previous_count else set()
    groups = {key: _variant_group(dev[key]) for key in dev}
    unavailable = {groups[key] for key in excluded}
    eligible = [key for key in dev if key not in excluded and len(dev[key]['train']) >= 2
                and all(pair['input'] != dev[key]['train'][0]['input'] for pair in dev[key]['train'][1:])]
    ordered = sorted(eligible, key=lambda key: hashlib.sha256((PROTOCOL + ':' + key).encode()).hexdigest())
    chosen = []
    for key in ordered:
        if groups[key] not in unavailable:
            chosen.append(key)
            unavailable.add(groups[key])
    if len(chosen) < count:
        raise ValueError('insufficient unused known-variant groups with TTT demonstrations')
    return chosen[:count], sorted(excluded)


def _variant_group(task):
    # Match the admitted corpus split, using demonstrations only. This is a
    # bounded syntactic overlap class, not proof of semantic independence.
    return known_variant_group({'train': task['train'], 'test': []})


def _physical(engine):
    result = {key: getattr(engine, key) for key in COUNTERS}
    if any(type(value) is not int or value < 0 for value in result.values()):
        raise ValueError('nonnegative real engine counters required')
    return result


def _stats(values):
    if not values:
        return {'count': 0, 'mean': None, 'maximum': None}
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        raise ValueError('finite observed statistics required')
    return {'count': len(values), 'mean': math.fsum(values) / len(values), 'maximum': max(values)}


def verify_prediction(result, task, query, cfg, *, task_id, views):
    """Rebuild tokens, prompts, inverse transforms and rank without any target."""
    specs = inference_views(views, seed=cfg.get('evaluation_seed', 20261017), task_id=task_id,
                            demo_count=len(task['train']))
    candidates = []
    seen = set()
    for record in result['views']:
        index = record['view']
        if type(index) is not int or not 0 <= index < views or index != len(seen):
            raise ValueError('unique configured view index required')
        seen.add(index)
        evidence = record['token_evidence']
        demos, transformed = view_inputs(task, query, specs[index])
        encoded = encode_example(demos, transformed, context=cfg['context_tokens'], generation=cfg['generation_tokens'])
        ids, logps = evidence['completion_ids'], evidence['completion_log_probs']
        if (evidence['view_spec'] != specs[index] or evidence['prompt_ids'] != encoded['prompt_ids']
                or record['demos_dropped'] != encoded['demos_dropped'] or not ids
                or record['tokens'] != len(ids) or len(ids) != len(logps)
                or any(type(token) is not int or not 0 <= token < 16 for token in ids)
                or 15 in ids[:-1] or record['stop'] not in {'completed', 'length'}
                or (record['stop'] == 'completed') != (ids[-1] == 15)
                or record['stop'] == 'length' and len(ids) != cfg['generation_tokens']
                or any(type(v) not in (int, float) or not math.isfinite(v) or v > 1e-6 for v in logps)):
            raise ValueError('retained raw completion/prompt/log probability identity differs')
        grid = parse_completion(ids)
        if type(record['valid']) is not bool or record['valid'] != (grid is not None):
            raise ValueError('parser result differs from raw completion')
        if grid is None:
            continue
        original = transform(grid, **specs[index]['transform'], inverse=True)
        found = next((i for i, row in enumerate(candidates) if row['grid'] == original), None)
        if found is None:
            found = len(candidates)
            candidates.append({'grid': original, 'votes': 0, 'nll_sum': 0., 'views': []})
        row = candidates[found]
        row['votes'] += 1; row['nll_sum'] += -sum(logps) / len(ids); row['views'].append(index)
        if record.get('candidate') != found:
            raise ValueError('inverse candidate identity differs')
    order = sorted(range(len(candidates)), key=lambda i: (-candidates[i]['votes'],
                   candidates[i]['nll_sum'] / candidates[i]['votes'], i))
    if (result['candidates'] != candidates or result['ranked_candidate_indices'] != order
            or result['ranked_grids'] != [candidates[i]['grid'] for i in order[:2]]
            or result['complete'] != (len(seen) == views)):
        raise ValueError('fixed view/ranking reconstruction differs')
    return {'verified': True, 'completed_views': len(seen), 'candidate_count': len(candidates),
            'result_sha256': hashlib.sha256(canonical(result)).hexdigest()}


def run_stability(engine, dev, cfg, *, deadline, audit, count=32, previous_count=24, views=2,
                  persist=None):
    """Fresh optimizer per task; held demo target is measurement-only.

    Full raw-token evidence stays in the private result. No PUBLIC result or
    development score is used to change the frozen treatment/panel mid-run.
    """
    if views != 2 or cfg.get('ttt_steps') != 32 or cfg.get('ttt_lr') != 5e-5:
        raise ValueError('v1 fixes two views, 0-versus32 TTT and original5e-5 learning rate')
    if 'inference_batch_size' in cfg:
        raise ValueError('stabilityv1 retains original serial decoder; batching is a separate factor')
    ids, excluded = select_panel(dev, count=count, previous_count=previous_count)
    params = {**cfg, 'retain_token_evidence': True}
    protocol = {'version': PROTOCOL, 'parent_ids': ids, 'excluded_previous_panel': excluded,
        'known_variant_groups': {key: _variant_group(dev[key]) for key in ids},
        'excluded_previous_variant_groups': sorted({_variant_group(dev[key]) for key in excluded}),
        'deduplication': 'known D4/color-renaming/demo-shuffle demonstrations only; not semantic independence',
        'reset_probe_atol': RESET_PROBE_ATOL, 'reset_probe_rtol': RESET_PROBE_RTOL,
        'views': views, 'ttt_steps': [0, 32], 'ttt_lr': cfg['ttt_lr'], 'held_demo_index': 0,
        'context_tokens': cfg['context_tokens'], 'generation_tokens': cfg['generation_tokens'],
        'evaluation_seed': cfg.get('evaluation_seed', 20261017), 'ranking': 'votes-descending-mean-own-view-nll-tie-v1',
        'public_feedback_used': False, 'initial_weight_cleanliness_claimed': False}
    anchor = adapter_state(engine.model); anchor_sha = state_digest(anchor)
    before = _physical(engine); started = time.time(); records = []; stop_reason = None
    try:
        for parent in ids:
            check_deadline(deadline)
            task = dev[parent]
            demos, query, target = loo_example(task, random.Random(0), augment=False, held_index=0)
            demo_task = {'train': demos}
            probe = encode_example(demos, query, target, context=cfg['context_tokens'], generation=cfg['generation_tokens'])
            restore_state(engine.model, anchor)
            if state_digest(adapter_state(engine.model)) != anchor_sha:
                raise RuntimeError('pre-parent reset differs from frozen anchor')
            nll_before = engine.nll(probe)
            check_deadline(deadline)
            if not math.isfinite(nll_before):
                raise FloatingPointError('nonfinite no-gradient anchor probe')
            record = {'parent_id': parent, 'target_digest': digest(target), 'phases': {}, 'complete': False}
            records.append(record)
            baseline = infer_query(engine, demo_task, query, params, task_id=parent, views=views, deadline=deadline)
            verified = verify_prediction(baseline, demo_task, query, params, task_id=parent, views=views)
            ranked = baseline['ranked_grids']
            record['phases']['no_ttt'] = {'prediction': baseline, 'verification': verified,
                'pass1': int(bool(ranked) and ranked[0] == target), 'pass2': int(target in ranked), 'valid': bool(ranked)}
            if not baseline['complete']:
                stop_reason = 'incomplete_no_ttt_views'; break
            norms, losses = [], []
            def capture(event, **fields):
                if event == 'ttt_step':
                    norms.append(fields['gradient_norm']); losses.append(fields['loss'])
                audit(event, **fields)
            adaptation = adapt_task(engine, demo_task, params, task_id=parent, steps=32, deadline=deadline, audit=capture)
            record['adaptation'] = {**adaptation, 'gradient_norm': _stats(norms), 'loss': _stats(losses),
                'clipped_steps': sum(v > 1. for v in norms), 'held_target_used_for_gradient': False}
            record['adapted_state_sha256'] = state_digest(adapter_state(engine.model))
            adapted = infer_query(engine, demo_task, query, params, task_id=parent, views=views, deadline=deadline)
            verified = verify_prediction(adapted, demo_task, query, params, task_id=parent, views=views)
            ranked = adapted['ranked_grids']
            record['phases']['ttt32'] = {'prediction': adapted, 'verification': verified,
                'pass1': int(bool(ranked) and ranked[0] == target), 'pass2': int(target in ranked), 'valid': bool(ranked)}
            restore_state(engine.model, anchor)
            reset_sha = state_digest(adapter_state(engine.model))
            if reset_sha != anchor_sha:
                raise RuntimeError('post-TTT trainable reset differs from frozen anchor')
            restored_nll = engine.nll(probe)
            check_deadline(deadline)
            if not math.isfinite(restored_nll):
                raise FloatingPointError('nonfinite restored no-gradient probe')
            drift = abs(restored_nll - nll_before)
            tolerance = RESET_PROBE_ATOL + RESET_PROBE_RTOL * max(abs(nll_before), abs(restored_nll))
            functional_reset = drift <= tolerance
            record['reset'] = {'state_sha256': reset_sha, 'verified': functional_reset,
                'parameter_state_verified': True, 'functional_probe_verified': functional_reset,
                'absolute_probe_nll_tolerance': tolerance,
                'probe_nll_before': nll_before, 'probe_nll_restored': restored_nll,
                'absolute_probe_nll_drift': drift, 'probe_used_for_gradient': False}
            record['complete'] = adapted['complete'] and adaptation['all_requested_complete'] and functional_reset
            if persist is not None:
                persist(records)
            audit('stability_parent', parent_id=parent, complete=record['complete'],
                pass2_before=record['phases']['no_ttt']['pass2'], pass2_after=record['phases']['ttt32']['pass2'],
                restored_state_verified=True, functional_probe_verified=functional_reset)
            if not record['complete']:
                stop_reason = 'functional_anchor_reset_drift' if not functional_reset else 'incomplete_ttt_or_views'; break
    except PhaseDeadline:
        stop_reason = 'original_phase_deadline'
    finally:
        restore_state(engine.model, anchor)
        if state_digest(adapter_state(engine.model)) != anchor_sha:
            raise RuntimeError('stability exit failed exact anchor reset')
        if persist is not None:
            persist(records)
    after = _physical(engine)
    paired = [row for row in records if row['complete']]
    summary = {name: {metric: sum(row['phases'][name][metric] for row in paired)
                     for metric in ('pass1', 'pass2', 'valid')} for name in ('no_ttt', 'ttt32')}
    paired_change = {metric: {'wins': sum(row['phases']['ttt32'][metric] > row['phases']['no_ttt'][metric] for row in paired),
                             'losses': sum(row['phases']['ttt32'][metric] < row['phases']['no_ttt'][metric] for row in paired),
                             'ties': sum(row['phases']['ttt32'][metric] == row['phases']['no_ttt'][metric] for row in paired)}
                     for metric in ('pass1', 'pass2')}
    return {'format': 'irisx/nvarc-ttt-stability-v1', 'protocol': protocol,
        'protocol_sha256': hashlib.sha256(canonical(protocol)).hexdigest(), 'anchor_state_sha256': anchor_sha,
        'requested_parents': len(ids), 'complete_parents': len(paired),
        'complete': len(paired) == len(ids), 'stop_reason': stop_reason, 'summary': summary,
        'paired_change': paired_change, 'records': records, 'wall_seconds': time.time() - started,
        'physical_work': {key: after[key] - before[key] for key in COUNTERS},
        'matched_views': True, 'public_scoring_performed': False, 'clean_generalization_claimed': False,
        'numerators_apply_to_complete_pairs_only': True, 'full_requested_denominator': len(ids),
        'causal_comparison_eligible': len(paired) == len(ids), 'architecture_expansion_tested': False}
