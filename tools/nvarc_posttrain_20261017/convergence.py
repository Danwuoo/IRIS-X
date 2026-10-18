"""Finite compact curriculum -> SFT/positive-CE/DDIS/hybrid continuation.

This is executable research glue, not a reproduction of RLVE, RAFT or DAPO.
RLVE inspiration is empirical exact difficulty with uniform exploration on an
admitted natural-parent panel; no new generator family is asserted. RAFT
inspiration is exact-positive CE, here success-conditioned prompt weighting
because compact targets are unique. DAPO inspiration is bounded resampling for
complete mixed groups, NOT DAPO's token-level reduction, asymmetric clipping or
length shaping. RL calls the genuine pinned upstream AF3/DDIS sequence-token
mean with exact-centered (not variance-normalized) rewards and .2/.2 clipping.

Four finite optimizer slots per arm, a shared same-anchor first pool, then fresh
current-policy windows. Later pools are NOT matched data: policies and sampled
curricula diverge. Every window invokes the unchanged cached/full probability
preflight AND independent full-pool gate before any loss. Old pools and probe
samples cannot be substituted. All work is charged, including no-signal groups.
"""
from __future__ import annotations

from collections import Counter
import copy
import math
import time

import torch

from tools.arc2_goal_sprint_20261017.model import (
    PhaseDeadline, adapter_state, check_deadline, make_optimizer, restore_state, state_digest,
)
from . import matched_controls as mc
from .codec import parse_completion
from .engine import CompactEngine, FatalUpdateError
from .probability_probe import probe
from .precision_contract import FP32_HEAD_POLICY, FP32_BACKBONE_POLICY, probability_tolerance, stable_probe_admission

FORMAT = 'irisx/compact-convergence-training-v1'
ARMS = (*mc.ARMS, 'finite_hybrid')
SCHEDULES = {
    'anchor': (),
    'known_target_ce': ('known_target_ce',) * 4,
    'exact_positive_ce': ('exact_positive_ce',) * 4,
    'exact_centered_ddis': ('exact_centered_ddis',) * 4,
    'finite_hybrid': ('known_target_ce', 'exact_positive_ce', 'exact_centered_ddis', 'known_target_ce'),
}
DEFAULT_CONFIG = {
    'collection': {**mc.DEFAULT_CONFIG, 'max_groups': 8, 'target_mixed_groups': 2},
    'training_seconds': 2400, 'window_seconds': 180,
    'max_model_forward_attempts': 65536,
}
LOSS_CONTRACT = {
    'known_target_ce': 'mean complete-group mean target-token NLL; every complete prompt weight1/G',
    'exact_positive_ce': 'mean positive-trajectory mean completion-token NLL; unique-target compression weight positive_count/total_positives',
    'exact_centered_ddis': 'actual AF3/DDIS; advantage exact_reward-group_mean; divisor mixed_groups*8*completion_length; clip .2/.2; no std, referenceKL, entropy mask, OPSM or DAPO token-mean',
    'finite_hybrid': 'predeclared targetCE,positiveCE,DDIS,targetCE; one persistent fresh optimizer within arm',
}


def validate_config(config=None):
    cfg = copy.deepcopy(DEFAULT_CONFIG if config is None else config)
    mc._schema(cfg, DEFAULT_CONFIG, 'convergence configuration')
    cfg['collection'] = mc._config(cfg['collection'])
    for key, maximum in (('training_seconds', 2400), ('window_seconds', 180),
                         ('max_model_forward_attempts', 65536)):
        mc._need(type(cfg[key]) is int and 1 <= cfg[key] <= maximum, 'finite bounded ' + key + ' required')
    mc._need(cfg['window_seconds'] <= cfg['training_seconds'], 'window must fit training bound')
    return cfg


def physical_bounds(config=None):
    cfg = validate_config(config); collection = cfg['collection']
    windows = 1 + sum(max(0, len(schedule) - 1) for schedule in SCHEDULES.values())
    return {'collection_windows': windows, 'group_attempts': windows * collection['max_groups'],
        'training_trajectory_slots': windows * collection['max_groups'] * mc.GROUP_SIZE,
        'preflight_trajectory_slots': windows * collection['microbatch'],
        'maximum_extra_diagnostic_head_projections': windows * (4 * collection['generation_tokens'] + 6 * collection['microbatch']),
        'training_optimizer_attempts': sum(map(len, SCHEDULES.values())),
        'model_forward_attempts': cfg['max_model_forward_attempts'],
        'completion_tokens_per_trajectory': collection['generation_tokens'],
        'context_tokens': collection['context_tokens'], 'training_wall_seconds': cfg['training_seconds'],
        'window_wall_seconds': cfg['window_seconds'],
        'count_includes_failed_and_no_signal': True, 'model_forwards_are_not_FLOPs': True}


def _projection_counts(windows):
    """Extra diagnostic head-only GEMMs are not backbone model forwards."""
    probes = [(window.get('preflight') or {}).get('probe') or {} for window in windows]
    return {'diagnostic_head_projection_attempts': sum(p.get('extra_projection_attempts', 0) for p in probes),
            'diagnostic_head_projection_successes': sum(p.get('extra_projection_successes', 0) for p in probes)}


def reset(engine, state, expected):
    restore_state(engine.model, state)
    for parameter in engine.parameters:
        parameter.grad = None
    mc._need(state_digest(adapter_state(engine.model)) == expected, 'exact named-trainable reset differs')


def _preflight(engine, prompt, cfg, *, deadline, policy_sha, hash_cost):
    raw = probe(engine, prompt, count=cfg['microbatch'], max_new_tokens=cfg['generation_tokens'],
                deadline=deadline, seed=cfg['seed'])
    after = mc.full_policy_sha256(engine, hash_cost)
    tolerance = probability_tolerance(engine)
    gaps = [raw.get(key) for key in ('cached_max_abs_logp_gap', 'full_max_abs_logp_gap')]
    cached = raw.get('cached_replay') or {}
    passed = (raw['status'] == 'completed' and policy_sha == after and not engine._fatal_update
        and len(raw['rows']) == len(raw['full_replay']) == cfg['microbatch']
        and cached.get('status') == 'completed'
        and 0 < len(cached['steps']) == len(raw['trace']['steps'])
        and raw['full_metrics']['tokens'] == sum(r['completion_tokens'] for r in raw['rows'])
        and raw['training_authorized'] is False
        and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= tolerance for v in gaps))
    additional, admission_error = None, None
    if engine.probability_policy in (FP32_HEAD_POLICY, FP32_BACKBONE_POLICY):
        try:
            additional, extra_passed = stable_probe_admission(raw, tolerance=tolerance, count=cfg['microbatch'])
            passed = passed and extra_passed
        except (ValueError, TypeError, KeyError) as error:
            passed = False
            admission_error = {'type': type(error).__name__, 'message': str(error)[:1024]}
    return {'passed': passed, 'tolerance': tolerance, 'additional_stable_admission': additional,
        'additional_admission_error': admission_error, 'gpu_backward_validated': False, 'policy_before_sha256': policy_sha,
        'policy_after_sha256': after, 'used_for_loss': False, 'full_pool_gate_still_required': True, 'probe': raw}


def collect_window(engine, training, admission, *, expected_admission_sha256, config,
                   deadline, window_id, persist=lambda result: None):
    """Fresh immutable behavior window; exceptions carry full partial evidence."""
    cfg = mc._config(config)
    panel = mc.admit_panel(training, admission, expected_admission_sha256=expected_admission_sha256)
    engine._checkpoint_admission()
    started = time.monotonic(); meter = mc._Meter(engine); before = meter.snapshot()
    hash_cost = {'calls': 0, 'tensor_bytes': 0, 'wall_seconds': 0.0}
    policy_sha = mc.full_policy_sha256(engine, hash_cost)
    lineage = {'policy_sha256': policy_sha, 'anchor_sha256': state_digest(adapter_state(engine.model)),
        'model_identity_sha256': mc._sha(mc._model_identity(engine)), 'admission_sha256': expected_admission_sha256}
    capture = {'config': cfg, 'lineage': lineage, 'groups': [], 'status': 'failed', 'seal_sha256': ''}
    result = {'window_id': window_id, 'status': 'running', 'capture': capture, 'preflight': None,
        'verification': {'observed_rows': 0, 'verified_rows': 0, 'max_logp_gap': None, 'failed_row': None, 'rows': []},
        'collection': {}, 'hash_cost': hash_cost, 'deadline_epoch': deadline,
        'behavior_probabilities_replaced': False, 'partial_groups_used_for_loss': False}
    chooser = mc._Chooser(panel, cfg['seed'])
    generator = torch.Generator(device=engine.device).manual_seed(cfg['seed'])
    examples = {key: mc._example(training[key], row, cfg) for key, row in panel.items()}
    primary = None
    try:
        first, _ = mc._Chooser(panel, cfg['seed']).choose()
        result['preflight'] = _preflight(engine, examples[first][0]['prompt_ids'], cfg,
            deadline=deadline, policy_sha=policy_sha, hash_cost=hash_cost)
        persist(result)  # Actual failed vectors survive denial before collection.
        if result['preflight']['probe']['status'] == 'deadline':
            raise PhaseDeadline('convergence probability preflight reached original deadline')
        mc._need(result['preflight']['passed'], 'unchanged cached/full probability preflight failed')
        for index in range(cfg['max_groups']):
            parent, allocation = chooser.choose(); example, target = examples[parent]
            group = {'group_id': f'g{index}', 'parent_id': parent, 'allocation': allocation,
                'prompt_ids': list(example['prompt_ids']), 'training_target': target,
                'demos_dropped': example['demos_dropped'], 'rows': [], 'batches': [],
                'status': 'failed', 'category': None}
            capture['groups'].append(group)
            try:
                check_deadline(deadline)
                for offset in range(0, mc.GROUP_SIZE, cfg['microbatch']):
                    count = min(cfg['microbatch'], mc.GROUP_SIZE - offset)
                    batch = {'requested': count, 'returned': 0, 'accepted': 0, 'status': 'failed'}
                    group['batches'].append(batch)
                    try:
                        rows = engine.generate(group['prompt_ids'], count=count, sample=True,
                            max_new_tokens=cfg['generation_tokens'], deadline=deadline, generator=generator)
                        mc._need(type(rows) is list and len(rows) <= count, 'bounded native generation rows required')
                        batch['returned'] = len(rows)
                        for raw in rows:
                            mc._schema(raw, ('input_ids', 'prompt_length', 'completion_ids', 'behavior_log_probs',
                                             'text', 'completion_tokens', 'stop'), 'engine rollout')
                            row = {**copy.deepcopy(raw), **lineage,
                                **{key: panel[parent][key] for key in ('parent_id', 'family_id', 'variant_group', 'task_sha256')},
                                'training_target': copy.deepcopy(target), 'group_id': group['group_id'],
                                'sample_id': f'g{index}:s{len(group["rows"])}',
                                'reward': float(parse_completion(raw['completion_ids']) == target)}
                            mc._validate_row(row, group, panel[parent], lineage, engine, cfg)
                            group['rows'].append(row); batch['accepted'] += 1
                        mc._need(len(rows) == count, 'partial generation cannot be replaced')
                        batch['status'] = 'complete'
                    except PhaseDeadline:
                        batch['status'] = 'deadline'; raise
                check_deadline(deadline)
                group['category'] = chooser.observe(parent, group['rows']); group['status'] = 'complete'
            except PhaseDeadline:
                group['status'] = 'deadline'; raise
            persist(result)
            if sum(g['category'] == 'mixed' for g in capture['groups']) == cfg['target_mixed_groups']:
                capture['status'] = 'target_reached'; break
        else:
            capture['status'] = 'budget_exhausted'
        capture['seal_sha256'] = mc._sha({k: v for k, v in capture.items() if k != 'seal_sha256'})
        mc.validate_capture(capture, training, admission, expected_admission_sha256=expected_admission_sha256,
                            engine=engine, hash_cost=hash_cost)
        mc._need(engine.optimizer_attempts == before['optimizer_attempts']
            and engine.optimizer_steps == before['optimizer_steps'], 'frozen window attempted an optimizer update')
        verify = result['verification']; tolerance = probability_tolerance(engine)
        with torch.no_grad():
            for group in capture['groups']:
                for row in group['rows']:
                    check_deadline(deadline)
                    replay = engine.completion_logps(row['input_ids'], row['prompt_length'])
                    behavior = torch.tensor(row['behavior_log_probs'], device=engine.device)
                    gap = (replay - behavior).abs().max().item()
                    verify['rows'].append({'sample_id': row['sample_id'], 'group_id': row['group_id'],
                        'input_ids_sha256': mc._sha(row['input_ids']), 'prompt_length': row['prompt_length'],
                        'replay_log_probs': replay.detach().cpu().tolist()})
                    verify['observed_rows'] += 1
                    verify['max_logp_gap'] = gap if verify['max_logp_gap'] is None else max(gap, verify['max_logp_gap'])
                    if not math.isfinite(gap) or gap > tolerance:
                        verify['failed_row'] = {'sample_id': row['sample_id'], 'tolerance': tolerance,
                            'max_abs_logp_gap': gap if math.isfinite(gap) else None,
                            'replay_log_probs': replay.detach().cpu().tolist()}
                        persist(result)
                        raise ValueError('captured behavior differs from full current frozen policy')
                    verify['verified_rows'] += 1
        check_deadline(deadline)
        mc._need(mc.full_policy_sha256(engine, hash_cost) == policy_sha, 'frozen window changed complete policy')
        result['status'] = 'complete'
    except BaseException as error:
        primary = error
        result['status'] = 'deadline' if isinstance(error, PhaseDeadline) else 'failed'
        if capture['status'] == 'failed' and isinstance(error, PhaseDeadline):
            capture['status'] = 'deadline'
        result['error'] = {'type': type(error).__name__, 'message': str(error)[:1024]}
        error.convergence_window_result = result
        raise
    finally:
        capture['seal_sha256'] = mc._sha({k: v for k, v in capture.items() if k != 'seal_sha256'})
        result['collection'] = {'groups_attempted': len(capture['groups']),
            'categories': dict(Counter(g['category'] or 'partial' for g in capture['groups'])),
            'trajectories_requested': sum(b['requested'] for g in capture['groups'] for b in g['batches']),
            'trajectories_retained': sum(len(g['rows']) for g in capture['groups']),
            'distinct_mixed_parents': len({g['parent_id'] for g in capture['groups'] if g['category'] == 'mixed'}),
            'parent_stats': {key: {**dict(s), 'empirical_exact': s['positive']/s['trajectories'] if s['trajectories'] else None,
                'smoothed_exact': (s['positive']+1)/(s['trajectories']+2)} for key, s in chooser.parents.items()},
            'family_stats': {key: dict(s) for key, s in chooser.families.items()},
            'uniform_only_control_run': False, 'adaptive_efficiency_established': False}
        try:
            engine.sync()
        except BaseException as error:
            result.update(status='failed', synchronization_error=type(error).__name__)
            if primary is None:
                error.convergence_window_result = result; raise
        finally:
            result['physical'] = {**mc._delta(meter.snapshot(), before), **_projection_counts([result])}
            result['wall_seconds'] = time.monotonic() - started
            meter.close(); persist(result)
    if time.time() >= deadline:
        result.update(status='deadline', stop_reason='deadline_during_window_finalization')
        persist(result)
        error = PhaseDeadline('window finalization exceeded its original finite deadline')
        error.convergence_window_result = result
        raise error
    return result


def _update(engine, capture, objective, optimizer, deadline):
    groups = capture['groups']
    if objective in ('known_target_ce', 'exact_positive_ce'):
        weighted = mc._weights(groups, objective)
        result = mc._ce_update(engine, weighted, optimizer, deadline, positive=objective == 'exact_positive_ce')
        result['prompt_weights'] = [{'group_id': g['group_id'], 'parent_id': g['parent_id'], 'weight': w} for g, w in weighted]
    else:
        mixed = [g for g in groups if g['status'] == 'complete' and g['category'] == 'mixed']
        if mixed:
            result = engine.af3_update([r for g in mixed for r in g['rows']], optimizer,
                expected_groups=[g['group_id'] for g in mixed], group_size=mc.GROUP_SIZE, deadline=deadline)
        else:
            result = {'updated': False, 'reason': 'no_complete_mixed_groups', 'replayed': 0}
        result['prompt_weights'] = [{'group_id': g['group_id'], 'parent_id': g['parent_id'], 'weight': 1/len(mixed)} for g in mixed]
    return result


def run_training(engine, training, admission, *, expected_admission_sha256, deadline,
                 config=None, persist=lambda result: None, persist_window=lambda result: None):
    """Execute at most sixteen real optimizer attempts, restore exact entry policy.

    Returned states are exact named trainables, not resume/optimizer checkpoints.
    A zero-signal slot is consumed, never replaced by more sampling or fake reward.
    The persistent optimizer is fresh for EACH arm; it is shared across the four
    declared slots within that arm including hybrid objective transitions.
    """
    mc._need(type(engine) is CompactEngine, 'actual CompactEngine required')
    cfg = validate_config(config)
    mc._need(type(deadline) in (int, float) and math.isfinite(deadline), 'finite original deadline required')
    if engine.contract['variant'] != 'tiny':
        mc._need(cfg == DEFAULT_CONFIG and engine.contract['variant'] in ('2b', '2b-depth32'), 'fixed official2B convergence settings required')
        expected_policy = FP32_HEAD_POLICY if engine.contract['variant'] == '2b-depth32' else FP32_BACKBONE_POLICY
        mc._need(getattr(engine, 'probability_policy', None) == expected_policy, 'separately admitted baseline/capacity computation policy required')
    mc.admit_panel(training, admission, expected_admission_sha256=expected_admission_sha256)
    training, admission = copy.deepcopy(training), copy.deepcopy(admission)
    engine._checkpoint_admission()
    started = time.monotonic(); stop = min(deadline, time.time() + cfg['training_seconds'])
    mode = engine.model.training; anchor = adapter_state(engine.model); anchor_sha = state_digest(anchor)
    policy_sha = mc.full_policy_sha256(engine); meter = mc._Meter(engine); before = meter.snapshot()
    result = {'format': FORMAT, 'status': 'running', 'config': cfg, 'bounds': physical_bounds(cfg),
        'schedules': {k: list(v) for k, v in SCHEDULES.items()}, 'loss_contract': LOSS_CONTRACT,
        'anchor_state_sha256': anchor_sha, 'anchor_policy_sha256': policy_sha,
        'states': {'anchor': anchor}, 'arms': {arm: {'status': 'not_executed', 'slots': []} for arm in ARMS},
        'windows': [], 'anchor_restored': False, 'deadline_epoch': stop,
        'same_pool_scope': 'first slot only; every later slot freshly collected from its own unchanged current policy',
        'equal_compute_claimed': False, 'efficacy_claimed': False, 'public_or_dev_feedback_used': False,
        'optimizer_resume_claimed': False, 'engine_poisoned': False}
    optimizer = None; primary = None
    def guard(module, args, kwargs):
        if meter.attempts >= cfg['max_model_forward_attempts']:
            raise PhaseDeadline('finite physical top-level model forward budget exhausted')
    guard_handle = engine.model.register_forward_pre_hook(guard, with_kwargs=True, prepend=True)
    def collect(arm, slot):
        check_deadline(stop)
        # Identical seed per slot, not global-RNG draw reuse across distinct policies.
        cc = {**cfg['collection'], 'seed': (cfg['collection']['seed'] + slot) % (2**63)}
        identifier = 'shared-anchor' if arm == 'shared' else f'{arm}-slot{slot}'
        record = None
        try:
            record = collect_window(engine, training, admission, expected_admission_sha256=expected_admission_sha256,
                config=cc, deadline=min(stop, time.time()+cfg['window_seconds']), window_id=identifier, persist=persist_window)
            return record
        except BaseException as error:
            record = getattr(error, 'convergence_window_result', None); raise
        finally:
            if record is not None:
                result['windows'].append(record); persist(result)
    try:
        shared = collect('shared', 0)
        result['shared_anchor_collection_physical'] = dict(shared['physical'])
        result['arms']['anchor'].update(status='complete', state_sha256=anchor_sha, optimizer_attempts=0)
        for arm in ARMS[1:]:
            reset(engine, anchor, anchor_sha)
            mc._need(mc.full_policy_sha256(engine) == policy_sha, 'complete same-anchor policy differs')
            optimizer = make_optimizer(engine.model, cfg['collection']['learning_rate'])
            mc._need(not optimizer.state, 'each objective requires fresh optimizer state')
            record = result['arms'][arm]
            arm_before, arm_started = meter.snapshot(), time.monotonic()
            record.update(status='running', before_state_sha256=anchor_sha,
                optimizer_initial_state_entries=0, optimizer_scope='fresh-per-arm-persistent-within-four-slots')
            try:
                for slot, objective in enumerate(SCHEDULES[arm]):
                    check_deadline(stop)
                    window = shared if slot == 0 else collect(arm, slot)
                    capture = window['capture']
                    current = state_digest(adapter_state(engine.model))
                    mc._need(current == capture['lineage']['anchor_sha256'], 'pool does not belong to current update policy')
                    step = {'slot': slot, 'objective': objective, 'window_id': window['window_id'],
                        'pool_sha256': capture['seal_sha256'], 'before_state_sha256': current, 'status': 'running'}
                    record['slots'].append(step)
                    step_before, step_started = meter.snapshot(), time.monotonic()
                    try:
                        update = _update(engine, capture, objective, optimizer, stop)
                        after = state_digest(adapter_state(engine.model))
                        mc._need(bool(update['updated']) == (after != current), 'optimizer parameter delta differs')
                        step.update(update, after_state_sha256=after, status='complete')
                        check_deadline(stop)
                    except BaseException as error:
                        step.update(status='deadline' if isinstance(error, PhaseDeadline) else 'failed', error=type(error).__name__)
                        raise
                    finally:
                        engine.sync()
                        step.update(physical=mc._delta(meter.snapshot(), step_before), wall_seconds=time.monotonic()-step_started)
                        persist(result)
                result['states'][arm] = adapter_state(engine.model)
                record.update(status='complete', state_sha256=state_digest(result['states'][arm]),
                    optimizer_final_state_entries=len(optimizer.state))
            finally:
                optimizer.zero_grad(set_to_none=True); optimizer = None
                record.update(physical={**mc._delta(meter.snapshot(), arm_before),
                    **_projection_counts([w for w in result['windows'] if w['window_id'].startswith(arm+'-slot')])},
                    wall_seconds=time.monotonic()-arm_started,
                    first_slot_shared_collection_charged_separately=True)
                persist(result)
        check_deadline(stop)
        result['status'] = 'complete'
    except PhaseDeadline as error:
        primary = error; result.update(status='partial', stop_reason=str(error))
    except BaseException as error:
        primary = error; result.update(status='failed', error=type(error).__name__)
        error.convergence_training_result = result; raise
    finally:
        if optimizer is not None:
            optimizer.zero_grad(set_to_none=True)
        try:
            reset(engine, anchor, anchor_sha)
            mc._need(mc.full_policy_sha256(engine) == policy_sha, 'full policy changed after mandatory anchor reset')
            result['anchor_restored'] = True
            engine.model.train(mode); engine.sync()
        except BaseException as error:
            engine._fatal_update = True
            result.update(status='failed', anchor_restored=False, restoration_error=type(error).__name__)
            if primary is None or isinstance(primary, PhaseDeadline):
                error.convergence_training_result = result; raise
        finally:
            guard_handle.remove()
            result.update(physical={**mc._delta(meter.snapshot(), before), **_projection_counts(result['windows'])}, wall_seconds=time.monotonic()-started,
                          engine_poisoned=bool(engine._fatal_update))
            meter.close()
            result['returned_after_deadline'] = time.time() >= stop
            if result['status'] == 'complete' and result['returned_after_deadline']:
                result.update(status='partial', stop_reason='deadline_during_training_finalization')
            persist(result)
            if time.time() >= stop and not result['returned_after_deadline']:
                result['returned_after_deadline'] = True
                if result['status'] == 'complete':
                    result.update(status='partial', stop_reason='deadline_during_training_persistence')
                persist(result)
    return result
