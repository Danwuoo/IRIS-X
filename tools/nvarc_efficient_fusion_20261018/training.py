"""Actual compact-2B matched CE versus bounded group-routed fusion.

No replacement behavior probabilities, stale RL pools, invented positive
rewards, dropped zero-signal groups, or silent tiny-model production fallback.
The original full-policy hashes, cached/full preflight and per-group full replay
remain. Initial preflight is amortized once, not mistaken for pool admission.
"""
from __future__ import annotations
import copy
import math
import time
import torch
from tools.arc2_goal_sprint_20261017.model import (
    PhaseDeadline, adapter_state, check_deadline, make_optimizer, state_digest,
)
from tools.nvarc_posttrain_20261017 import convergence as cv, matched_controls as mc
from tools.nvarc_posttrain_20261017.codec import parse_completion
from tools.nvarc_posttrain_20261017.engine import CompactEngine
from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY, probability_tolerance
from .contracts import (ARMS, DEFAULT_CONFIG, LOSS_CONTRACT, ROUTES, CoverageChooser,
                        category, json_safe_nonfinite, physical_bounds, require, sha, validate_config)
from .panels import validate_prepared


def collection_config(cfg, slot=0):
    return {**mc.DEFAULT_CONFIG, 'seed': (cfg['seed'] + slot) % (2**63), 'max_groups': 1,
        'target_mixed_groups': 1, **{k: cfg[k] for k in ('microbatch', 'context_tokens', 'generation_tokens', 'learning_rate')}}


def collect_group(engine, task, entry, *, admission_sha, cfg, slot, allocation, deadline,
                  persist=lambda record: None):
    """One fresh frozen eight-rollout group; persist failed numerical vectors."""
    cc = collection_config(cfg, slot); cost = {'calls': 0, 'tensor_bytes': 0, 'wall_seconds': 0.0}
    engine._checkpoint_admission(); meter = mc._Meter(engine); before = meter.snapshot(); started = time.monotonic()
    policy = mc.full_policy_sha256(engine, cost)
    lineage = {'policy_sha256': policy, 'anchor_sha256': state_digest(adapter_state(engine.model)),
               'model_identity_sha256': sha(mc._model_identity(engine)), 'admission_sha256': admission_sha}
    example, target = mc._example(task, entry, cc)
    group = {'group_id': 'g' + str(slot), 'parent_id': entry['parent_id'], 'allocation': allocation,
        'prompt_ids': example['prompt_ids'], 'training_target': target, 'demos_dropped': example['demos_dropped'],
        'rows': [], 'batches': [], 'status': 'running', 'category': None}
    result = {'format': 'irisx/efficient-fusion-group-v1', 'slot': slot, 'status': 'running', 'config': cc,
        'lineage': lineage, 'group': group, 'hash_cost': cost, 'deadline_epoch': deadline,
        'verification': {'observed_rows': 0, 'verified_rows': 0, 'max_logp_gap': None, 'rows': [], 'failed_row': None, 'nonfinite_replay_observed': False},
        'behavior_probabilities_replaced': False, 'partial_groups_used_for_loss': False,
        'sealed_before_updates': True, 'full_policy_after_sha256': None}
    generator = torch.Generator(device=engine.device).manual_seed(cc['seed']); primary = None
    try:
        for offset in range(0, 8, cc['microbatch']):
            check_deadline(deadline)
            count = min(cc['microbatch'], 8-offset)
            batch = {'requested': count, 'returned': 0, 'accepted': 0, 'status': 'running'}
            group['batches'].append(batch); persist(result)
            rows = engine.generate(example['prompt_ids'], count=count, sample=True,
                max_new_tokens=cc['generation_tokens'], deadline=deadline, generator=generator)
            require(type(rows) is list and len(rows) <= count, 'bounded native generation result required')
            batch['returned'] = len(rows)
            for raw in rows:
                mc._schema(raw, ('input_ids', 'prompt_length', 'completion_ids', 'behavior_log_probs',
                    'text', 'completion_tokens', 'stop'), 'engine rollout')
                row = {**copy.deepcopy(raw), **lineage,
                    **{k: entry[k] for k in ('parent_id', 'family_id', 'variant_group', 'task_sha256')},
                    'training_target': copy.deepcopy(target), 'group_id': group['group_id'],
                    'sample_id': group['group_id'] + ':s' + str(len(group['rows'])),
                    'reward': float(parse_completion(raw['completion_ids']) == target)}
                mc._validate_row(row, group, entry, lineage, engine, cc)
                group['rows'].append(row); batch['accepted'] += 1
            require(len(rows) == count, 'partial group cannot be replaced or used for any loss')
            batch['status'] = 'complete'; persist(result)
        group.update(status='complete', category=category([r['reward'] for r in group['rows']]))
        verification = result['verification']; tolerance = probability_tolerance(engine)
        with torch.no_grad():
            for row in group['rows']:
                check_deadline(deadline)
                replay = engine.completion_logps(row['input_ids'], row['prompt_length'])
                behavior = torch.tensor(row['behavior_log_probs'], device=engine.device)
                gap = (replay-behavior).abs().max().item()
                values = replay.detach().cpu().tolist()
                nonfinite = [{'index': i, 'value': str(v)} for i, v in enumerate(values) if not math.isfinite(v)]
                measured = {'sample_id': row['sample_id'], 'replay_log_probs': [v if math.isfinite(v) else None for v in values],
                            'nonfinite_values': nonfinite, 'max_abs_logp_gap': gap if math.isfinite(gap) else None}
                verification['rows'].append(measured); verification['observed_rows'] += 1
                if math.isfinite(gap):
                    verification['max_logp_gap'] = gap if verification['max_logp_gap'] is None else max(gap, verification['max_logp_gap'])
                else:
                    verification['nonfinite_replay_observed'] = True
                if not math.isfinite(gap) or gap > tolerance:
                    verification['failed_row'] = measured; persist(result)
                    raise ValueError('actual full-policy replay differs from original behavior probabilities')
                verification['verified_rows'] += 1
        result['full_policy_after_sha256'] = mc.full_policy_sha256(engine, cost)
        require(result['full_policy_after_sha256'] == policy, 'full frozen policy changed during collection/replay')
        require(engine.optimizer_attempts == before['optimizer_attempts'] and engine.optimizer_steps == before['optimizer_steps'],
                'collection must be optimizer-free')
        check_deadline(deadline); result['status'] = 'complete'
    except BaseException as error:
        primary = error; result.update(status='deadline' if isinstance(error, PhaseDeadline) else 'failed',
                                       error={'type': type(error).__name__, 'message': str(error)[:1024]})
        if group['status'] == 'running': group['status'] = result['status']
        if group['batches'] and group['batches'][-1]['status'] == 'running':
            group['batches'][-1]['status'] = result['status']
        error.fusion_group_result = result
        raise
    finally:
        try:
            engine.sync()
        except BaseException as error:
            result.update(status='failed', synchronization_error=type(error).__name__)
            if primary is None: error.fusion_group_result = result; raise
        finally:
            result.update(physical=mc._delta(meter.snapshot(), before), wall_seconds=time.monotonic()-started)
            meter.close()
            result['seal_sha256'] = sha({k: v for k, v in result.items() if k != 'seal_sha256'})
            persist(result)
    if time.time() >= deadline:
        result.update(status='deadline', stop_reason='late_group_finalization')
        result['seal_sha256'] = sha({k: v for k, v in result.items() if k != 'seal_sha256'}); persist(result)
        error = PhaseDeadline('group finalization exceeded original deadline'); error.fusion_group_result = result; raise error
    return result


def guarded_af3_update(engine, group, optimizer, *, deadline, slot, persist):
    """Gate the actual upstream train-gradient replay, not a second surrogate.

    The scoped instance wrappers restore in finally. Every gradient-bearing
    replay is checked before AF3 sees it, and commit requires all eight rows.
    This preserves the upstream loss and avoids an extra full gradient pass.
    """
    original_logps, original_commit = engine.completion_logps, engine.commit
    had_logps, had_commit = 'completion_logps' in engine.__dict__, 'commit' in engine.__dict__
    evidence = {'format': 'irisx/efficient-fusion-gradient-replay-v1', 'slot': slot,
        'group_id': group['group_id'], 'status': 'running', 'tolerance': probability_tolerance(engine),
        'observed_rows': 0, 'verified_rows': 0, 'max_logp_gap': None,
        'nonfinite_replay_observed': False, 'failed_row': None, 'rows': [], 'commit_admitted': False}
    def checked_logps(ids, n):
        index = evidence['observed_rows']; require(index < 8 and torch.is_grad_enabled(), 'actual train-gradient replay required')
        row = group['rows'][index]
        require(list(ids) == row['input_ids'] and n == row['prompt_length'], 'upstream train replay order/token path differs')
        values = original_logps(ids, n)
        gap = (values.detach()-torch.tensor(row['behavior_log_probs'], device=engine.device)).abs().max().item()
        vector = values.detach().cpu().tolist()
        measured = {'sample_id': row['sample_id'], 'replay_log_probs': [v if math.isfinite(v) else None for v in vector],
            'nonfinite_values': [{'index': i, 'value': str(v)} for i, v in enumerate(vector) if not math.isfinite(v)],
            'max_abs_logp_gap': gap if math.isfinite(gap) else None}
        evidence['rows'].append(measured); evidence['observed_rows'] += 1
        if math.isfinite(gap):
            evidence['max_logp_gap'] = gap if evidence['max_logp_gap'] is None else max(gap, evidence['max_logp_gap'])
        else: evidence['nonfinite_replay_observed'] = True
        if not math.isfinite(gap) or gap > evidence['tolerance']:
            evidence['failed_row'] = measured; persist(evidence)
            raise ValueError('actual train-gradient replay differs from original behavior probabilities')
        evidence['verified_rows'] += 1
        return values
    def checked_commit(value):
        require(value is optimizer and evidence['verified_rows'] == 8 and evidence['failed_row'] is None,
                'all actual gradient replay rows must pass before optimizer commit')
        evidence['commit_admitted'] = True; persist(evidence)
        return original_commit(value)
    engine.completion_logps, engine.commit = checked_logps, checked_commit
    try:
        result = engine.af3_update(group['rows'], optimizer, expected_groups=[group['group_id']], group_size=8, deadline=deadline)
        evidence['status'] = 'complete'
        return result
    except BaseException as error:
        evidence.update(status='deadline' if isinstance(error, PhaseDeadline) else 'failed', error=type(error).__name__)
        raise
    finally:
        if had_logps: engine.completion_logps = original_logps
        else: del engine.completion_logps
        if had_commit: engine.commit = original_commit
        else: del engine.commit
        evidence['seal_sha256'] = sha({k: v for k, v in evidence.items() if k != 'seal_sha256'})
        persist(evidence)


def _summary(record):
    return {k: copy.deepcopy(record[k]) for k in ('slot', 'status', 'seal_sha256', 'lineage', 'hash_cost', 'physical', 'wall_seconds')} | {
        'parent_id': record['group']['parent_id'], 'category': record['group']['category'],
        'rollouts_retained': len(record['group']['rows']),
        'rollouts_requested': sum(b['requested'] for b in record['group']['batches']),
        'verification': {k: v for k, v in record['verification'].items() if k not in ('rows', 'failed_row')}}


def run_training(engine, prepared, *, deadline, config=None, persist=lambda result: None,
                 persist_group=lambda result: None, persist_probe=lambda result: None,
                 persist_gradient=lambda result: None):
    cfg = validate_config(config); validate_prepared(prepared)
    from .architecture import admit_engine
    admit_engine(engine, require_fp32=True)
    require(type(deadline) in (int, float) and math.isfinite(deadline), 'finite original training deadline required')
    if engine.contract['variant'] != 'tiny':
        require(engine.contract['variant'] == '2b' and cfg == DEFAULT_CONFIG
                and len(prepared['training']) == 64 and len(prepared['development']) == 96,
                'official2B fixed64/96 and96-slot recipe required')
    engine._checkpoint_admission(); stop = min(deadline, time.time()+cfg['training_seconds'])
    chooser = CoverageChooser(prepared['protocol']['training_parent_ids'], cfg)
    entries = {row['parent_id']: row for row in prepared['admission']['parents']}
    anchor = adapter_state(engine.model); anchor_sha = state_digest(anchor); mode = engine.model.training
    cost = {'calls': 0, 'tensor_bytes': 0, 'wall_seconds': 0.0}
    policy = mc.full_policy_sha256(engine, cost); meter = mc._Meter(engine); before = meter.snapshot(); started = time.monotonic()
    states = {arm: anchor for arm in ARMS}
    result = {'format': 'irisx/efficient-fusion-training-v1', 'status': 'running', 'config': cfg,
        'bounds': physical_bounds(cfg), 'loss_contract': LOSS_CONTRACT, 'anchor_state_sha256': anchor_sha,
        'anchor_policy_sha256': policy, 'states': states, 'groups': [], 'preflight': None,
        'arms': {arm: {'slots': [], 'status': 'running' if arm != 'anchor' else 'complete',
                      'optimizer_initial_state_entries': 0} for arm in ARMS},
        'hash_cost_outside_groups': cost, 'deadline_epoch': stop, 'anchor_restored': False,
        'equal_compute_claimed': False, 'public_or_dev_feedback_used': False, 'efficacy_claimed': False,
        'same_prompt_order_claimed': True, 'optimizer_resume_claimed': False,
        'collection_policy': 'fresh current routed_fusion policy; supervised control follows identical prompts',
        'initial_preflight_amortized': True, 'full_pool_replay_required_every_group': True}
    optimizers = {arm: make_optimizer(engine.model, cfg['learning_rate']) for arm in ARMS[1:]}
    require(all(not optimizer.state for optimizer in optimizers.values()), 'fresh distinct optimizers required')
    primary = None
    def guard(module, args, kwargs):
        if meter.attempts >= cfg['max_model_forward_attempts']:
            raise PhaseDeadline('finite total training top-level forward budget exhausted')
    handle = engine.model.register_forward_pre_hook(guard, with_kwargs=True, prepend=True)
    try:
        first = chooser.order[0]; example, _ = mc._example(prepared['training'][first], entries[first], collection_config(cfg))
        probe_before, probe_start = meter.snapshot(), time.monotonic()
        probe = cv._preflight(engine, example['prompt_ids'], collection_config(cfg),
            deadline=min(stop, time.time()+cfg['group_seconds']), policy_sha=policy, hash_cost=cost)
        probe, classified = json_safe_nonfinite(probe)
        if classified: probe.update(passed=False, nonfinite_fields=classified)
        persist_probe(probe)
        result['preflight'] = {'passed': probe['passed'], 'tolerance': probe['tolerance'],
            'sha256': sha(probe), 'policy_before_sha256': probe['policy_before_sha256'],
            'physical': mc._delta(meter.snapshot(), probe_before), 'wall_seconds': time.monotonic()-probe_start,
            'extra_projection_attempts': probe['probe'].get('extra_projection_attempts', 0),
            'extra_projection_successes': probe['probe'].get('extra_projection_successes', 0)}
        persist(result)
        require(probe['passed'], 'unchanged cached/full/eval/train-gradient preflight required')
        for slot in range(cfg['updates']):
            check_deadline(stop)
            cv.reset(engine, states['routed_fusion'], state_digest(states['routed_fusion']))
            parent, allocation = chooser.choose(); group_record = None
            try:
                group_record = collect_group(engine, prepared['training'][parent], entries[parent],
                    admission_sha=prepared['pins']['admission_sha256'], cfg=cfg, slot=slot,
                    allocation=allocation, deadline=min(stop, time.time()+cfg['group_seconds']), persist=persist_group)
            except BaseException as error:
                group_record = getattr(error, 'fusion_group_result', None); raise
            finally:
                if group_record is not None: result['groups'].append(_summary(group_record)); persist(result)
            group = group_record['group']; chooser.observe(parent, [r['reward'] for r in group['rows']])
            # Fusion consumes its just-verified policy before any state switch.
            # CE can use the same prompt off-policy because it is supervised CE,
            # never relabeled RL or a second behavior-policy denominator.
            for arm in ('routed_fusion', 'matched_target_ce'):
                check_deadline(stop)
                state = states[arm]; current = state_digest(state)
                cv.reset(engine, state, current)
                if arm == 'routed_fusion':
                    require(mc.full_policy_sha256(engine, cost) == group_record['lineage']['policy_sha256'],
                            'DDIS current policy differs from freshly verified group')
                objective = ROUTES[group['category']] if arm == 'routed_fusion' else 'known_target_ce'
                record = {'slot': slot, 'parent_id': parent, 'objective': objective,
                    'group_seal_sha256': group_record['seal_sha256'], 'prompt_sha256': sha(group['prompt_ids']),
                    'before_state_sha256': current, 'status': 'running', 'update_returned': False}
                result['arms'][arm]['slots'].append(record)
                step_before, step_start = meter.snapshot(), time.monotonic()
                try:
                    if objective == 'exact_centered_ddis':
                        def gradient_receipt(value):
                            persist_gradient(value)
                            record['gradient_replay'] = {k: copy.deepcopy(v) for k, v in value.items() if k not in ('rows', 'failed_row')}
                        update = guarded_af3_update(engine, group, optimizers[arm], deadline=stop,
                                                    slot=slot, persist=gradient_receipt)
                    else:
                        update = mc._ce_update(engine, [(group, 1.0)], optimizers[arm], stop,
                                               positive=objective == 'exact_positive_ce')
                    states[arm] = adapter_state(engine.model); after = state_digest(states[arm])
                    require(bool(update['updated']) == (current != after), 'optimizer result/state delta differs')
                    record.update(update, status='complete', update_returned=True, after_state_sha256=after,
                        exact_positive_duplicate_graphs_avoided=7 if objective == 'exact_positive_ce' else 0)
                    check_deadline(stop)
                except BaseException as error:
                    record.update(status='deadline' if isinstance(error, PhaseDeadline) else 'failed', error=type(error).__name__)
                    raise
                finally:
                    engine.sync(); record.update(physical=mc._delta(meter.snapshot(), step_before),
                                                  wall_seconds=time.monotonic()-step_start)
                    result['curriculum'] = chooser.report(); persist(result)
        require(chooser.report()['parents_observed'] == len(entries), 'complete initial parent coverage required')
        for arm in ARMS[1:]:
            result['arms'][arm].update(status='complete', optimizer_final_state_entries=len(optimizers[arm].state),
                state_sha256=state_digest(states[arm]))
        result['status'] = 'complete'
    except PhaseDeadline as error:
        primary = error; result.update(status='partial', stop_reason=str(error))
    except BaseException as error:
        primary = error; result.update(status='failed', error={'type': type(error).__name__, 'message': str(error)[:1024]})
        error.fusion_training_result = result; raise
    finally:
        for optimizer in optimizers.values(): optimizer.zero_grad(set_to_none=True)
        try:
            cv.reset(engine, anchor, anchor_sha)
            require(mc.full_policy_sha256(engine, cost) == policy, 'full entry policy not restored')
            result['anchor_restored'] = True; engine.model.train(mode); engine.sync()
        except BaseException as error:
            engine._fatal_update = True
            result.update(status='failed', restoration_error=type(error).__name__, anchor_restored=False)
            if primary is None or isinstance(primary, PhaseDeadline): error.fusion_training_result = result; raise
        finally:
            handle.remove(); result.update(physical=mc._delta(meter.snapshot(), before),
                wall_seconds=time.monotonic()-started, curriculum=chooser.report(), engine_poisoned=bool(engine._fatal_update),
                returned_after_deadline=time.time() >= stop)
            meter.close()
            if result['status'] == 'complete' and result['returned_after_deadline']: result['status'] = 'partial'
            persist(result)
            if time.time() >= stop and not result['returned_after_deadline']:
                result.update(returned_after_deadline=True, status='partial' if result['status'] == 'complete' else result['status'])
                persist(result)
    return result
