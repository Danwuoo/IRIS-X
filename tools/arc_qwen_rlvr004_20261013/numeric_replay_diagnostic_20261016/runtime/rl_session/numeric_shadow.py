"""Bounded, read-only decomposition of the first owned training replay.

This is diagnostic evidence only. No value returned here is an update/gate input.
The original actor owns all tokens, supports, clocks and physical events. A
missing precondition yields incomplete evidence, never replacement samples.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import inspect
import math
from pathlib import Path
import time

import torch

from .common import canonical, digest, need, rl_math, tensor_signature, tree_sha


SCHEMA = 'numeric-shadow-training-only-v1'
MAX_SECONDS = 120.
MAX_FORWARD_SECONDS = 30.
MAX_ALLOCATED = 72 * 1024**3
MAX_RESERVED = 80 * 1024**3
MAX_REPORT_BYTES = 65536
PARENT_ORDINALS = (0, 7)


def _source_binding(actor):
    """Record original admitted forward provenance without modifying execution.

    The actor's existing loader/source/function/recipe guards remain authoritative.
    No hidden-state capture is requested: pinned HF 5.8.1 implements that feature
    with persistent hooks, which are forbidden by the original actor contract.
    """
    actor._check_live()
    need(not getattr(actor.model.config, 'output_hidden_states', False) and
         not getattr(actor.model.config, 'output_attentions', False),
         'shadow cannot enable native output-capture hooks')
    forwards = []
    for module in (actor.model, actor.model.get_base_model()):
        function = inspect.unwrap(module.forward)
        path = Path(inspect.getsourcefile(function)).resolve(strict=True)
        forwards.append({'qualified_name': function.__qualname__,
                         'function_source_sha256': hashlib.sha256(inspect.getsource(function).encode()).hexdigest(),
                         'module_source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'original_admitted_forward': True, 'forward_sources': forwards,
            'native_identity_sha256': digest(actor.native.identity),
            'actor_source_sha256': digest(actor._sources),
            'hidden_state_capture': False, 'extra_head_projections': 0,
            'original_cache_mode': actor.cache_mode,
            'original_head_dtype': str(actor.model.get_output_embeddings().weight.dtype),
            'original_head_shape': list(actor.model.get_output_embeddings().weight.shape),
            'decomposition_limit': 'teacher-versus-prefix combines hidden-state and head-row-shape differences'}


def _memory(actor):
    if actor.device.type != 'cuda':
        return {'allocated_bytes': None, 'reserved_bytes': None,
                'peak_allocated_bytes': None, 'peak_reserved_bytes': None}
    result = {'allocated_bytes': torch.cuda.memory_allocated(actor.device),
              'reserved_bytes': torch.cuda.memory_reserved(actor.device),
              'peak_allocated_bytes': torch.cuda.max_memory_allocated(actor.device),
              'peak_reserved_bytes': torch.cuda.max_memory_reserved(actor.device)}
    need(max(result['allocated_bytes'], result['peak_allocated_bytes']) <= MAX_ALLOCATED and
         max(result['reserved_bytes'], result['peak_reserved_bytes']) <= MAX_RESERVED,
         'shadow memory ceiling reached')
    return result


def _state(actor):
    """Use the actor's versioned ownership contract; never copy the frozen base."""
    actor._check_live()
    actor._check_optimizer()
    return {'parameters': tensor_signature(actor.model.named_parameters()),
            'buffers': tensor_signature(actor.model.named_buffers()),
            'gradients': tensor_signature((n, p.grad) for n, p in actor.model.named_parameters()
                                          if p.grad is not None),
            'gradient_inventory': tuple((n, p.grad is None) for n, p in actor.model.named_parameters()),
            'adapter': actor.trainer.fingerprint()['sha256'],
            'hooks': actor._hooks(), 'functions': actor._functions(),
            'structure': digest(actor._structure()),
            'modes': tuple((n, m.training) for n, m in actor.model.named_modules()),
            'optimizer_execution': deepcopy(actor._optimizer_signature()),
            'counters': deepcopy(actor.counters), 'policy_version': actor.policy_version,
            'generation_epoch': actor._generation_epoch,
            'owned': digest({k: hashlib.sha256(v).hexdigest() for k, v in actor._owned.items()}),
            'batches': digest({k: hashlib.sha256(v).hexdigest() for k, v in actor._batch_registry.items()})}


@contextmanager
def _work(actor, report, phase, deadline, cost, *, trajectory_id=None):
    """The original durable ledger owns reservation, dispatch, sync and failure."""
    with actor.ledger.work(phase, deadline) as event:
        report['physical_event_ids'].append(event['event_id'])
        event.update(update_batch_id=report['update_batch_id'], trajectory_id=trajectory_id,
                     reserved_cost=cost, dispatched=True,
                     **({'input_tokens': cost['input_tokens']} if 'input_tokens' in cost else {}))
        actor._deadline(min(deadline, event.get('soft_deadline', deadline)))
        report['memory'] = _memory(actor)
        yield event
        report['memory'] = _memory(actor)
        actor._deadline(min(deadline, event.get('soft_deadline', deadline)))
        event['actual_cost'] = cost


def _select(actor, batch, replay_reports, report):
    actor._check_batch(batch)
    need(batch['batch_index'] == 0, 'shadow only admits the first batch')
    need(not any(e['phase'] == 'numeric-shadow' and e['event_id'] not in report['physical_event_ids']
                 for e in actor.ledger.events), 'shadow already attempted; no diagnostic retry')
    need(type(replay_reports) is list, 'original replay reports required')
    by_id = {}
    for replay in replay_reports:
        identifier = replay.get('trajectory_id')
        need(identifier not in by_id, 'duplicate original replay report')
        by_id[identifier] = replay
    selected = []
    for ordinal in PARENT_ORDINALS:
        result = {'parent_ordinal': ordinal, 'slot': 0, 'status': 'missing', 'points': []}
        report['rows'].append(result)
        if ordinal >= len(batch['parent_ids']):
            continue
        parent = batch['parent_ids'][ordinal]
        candidates = [r for r in batch['rows'] if r['parent_id'] == parent and r['slot'] == 0]
        if len(candidates) != 1 or not candidates[0].get('trajectory'):
            continue
        row = candidates[0]['trajectory']
        result.update(parent_id=parent, trajectory_id=row['trajectory_id'])
        if not candidates[0].get('eligible') or candidates[0].get('status') != 'eligible':
            result['status'] = 'excluded-original-trajectory'
            continue
        actor._admit(row)
        length = len(row['generated_ids'])
        need(len(row['steps']) == length and length > 0, 'complete original token-step layout required')
        old = by_id.get(row['trajectory_id'])
        if old is None:
            result['status'] = 'missing-original-replay'
            continue
        need(old.get('original_token_replay') is True and old.get('training_mode') is True and
             old.get('update_batch_id') == batch['id'] and old.get('parent_id') == parent and
             len(old.get('log_pi', [])) == length and len(old.get('log_mu', [])) == length,
             'original replay binding differs')
        need(old['log_mu'] == [step['log_mu'] for step in row['steps']],
             'original replay/actor behavior log probabilities differ')
        need(all(type(x) in (float, int) and math.isfinite(x) and x <= 1e-6
                 for x in old['log_pi'] + old['log_mu']), 'finite original replay probabilities required')
        event_id = old.get('replay_event_id')
        events = {e['event_id']: e for e in actor.ledger.events}
        need(event_id in events and events[event_id].get('phase') == 'causal-replay' and
             events[event_id].get('status') == 'complete' and
             events[event_id].get('trajectory_id') == row['trajectory_id'] and
             events[event_id].get('update_batch_id') == batch['id'],
             'original replay needs a completed owned physical event')
        offsets = list(dict.fromkeys((0, 1, length - 1)))
        for offset in offsets:
            if offset >= length:
                result['points'].append({'offset': offset, 'status': 'missing-offset'})
                continue
            support = row['steps'][offset]['support']
            result['points'].append({'offset': offset, 'support_size': len(support),
                                     'status': 'forced-no-substitution' if len(support) == 1 else 'pending'})
        result.update(status='selected', original_replay_event_id=event_id,
                      original_generated_length=length)
        selected.append((row, old, result))
    need(len(selected) == 2, 'fixed shadow selection or original replay missing')
    need(not any(p['status'] == 'missing-offset' for r in report['rows'] for p in r['points']),
         'fixed shadow offset missing')
    return selected


def _forward(actor, report, row, tokens, positions, deadline, check_state):
    need(report['model_forward_calls'] < 8, 'shadow model forward ceiling')
    phase = 'numeric-shadow-forward'
    bounded = min(deadline, time.monotonic() + MAX_FORWARD_SECONDS)
    with _work(actor, report, phase, bounded,
               {'forward_calls': 1, 'input_tokens': len(tokens)},
               trajectory_id=row['trajectory_id']) as event:
        check_state()
        ids = torch.tensor([tokens], device=actor.device, dtype=torch.long)
        pos = torch.arange(len(tokens), device=actor.device)
        report['model_forward_calls'] += 1
        out = actor.model(input_ids=ids, attention_mask=torch.ones_like(ids),
                          position_ids=pos[None, :], cache_position=pos, past_key_values=None,
                          use_cache=False, logits_to_keep=positions, return_dict=True)
        need(out.past_key_values is None, 'shadow cannot retain KV cache')
        need(not out.logits.requires_grad and bool(torch.isfinite(out.logits).all()),
             'finite inference-only shadow logits required')
        check_state()
        return out, event['event_id']


def _scalar(value):
    result = float(value)
    need(math.isfinite(result), 'nonfinite shadow scalar')
    return result


def _diagnose_row(actor, row, old, result, report, deadline, check_state):
    points = [p for p in result['points'] if p['status'] == 'pending']
    if not points:
        result['status'] = 'all-selected-points-forced'
        return
    tokens = row['original_ids'][:-1]
    positions = torch.arange(len(row['prompt_ids']) - 1, len(tokens), device=actor.device)
    out, teacher_event = _forward(actor, report, row, tokens, positions, deadline, check_state)
    logits = out.logits[0]
    need(logits.shape == (len(row['generated_ids']), actor.native.vocab_size),
         'exact original generated causal head row layout required')
    result.update(teacher_event_id=teacher_event, teacher_logits_shape=list(out.logits.shape),
                  teacher_input_shape=[1, len(tokens)], logits_dtype=str(logits.dtype),
                  inferred_teacher_head_input_shape=[1, len(row['generated_ids']),
                                                    actor.model.get_output_embeddings().weight.shape[1]],
                  hidden_shape_provenance='inferred-from-original-head-and-selected-row-count; no-hidden-capture',
                  reduction_dtype='torch.float32', training=False, autograd=False,
                  hidden_state_capture=False, extra_head_projections=0)
    with _work(actor, report, 'numeric-shadow-reduce', deadline, {'host_operations': 1},
               trajectory_id=row['trajectory_id']):
        allowed = torch.zeros_like(logits, dtype=torch.bool)
        for i, step in enumerate(row['steps']):
            allowed[i, step['support']] = True
        chosen = torch.tensor(row['generated_ids'], device=actor.device, dtype=torch.long)
        multi = rl_math.selected_log_probs(logits, allowed, chosen)
        # Preserve original M=N, and isolate reduction-shape effects by reducing
        # one row of those identical logits. This is not an M=1 head projection.
        for point in points:
            i = point['offset']
            single = rl_math.selected_log_probs(logits[i:i+1], allowed[i:i+1], chosen[i:i+1])[0]
            point.update(train_log_pi=_scalar(old['log_pi'][i]), actor_log_mu=_scalar(old['log_mu'][i]),
                         eval_multirow_log_pi=_scalar(multi[i]), same_logits_single_row_log_pi=_scalar(single),
                         train_vs_eval_gap=_scalar(old['log_pi'][i] - multi[i].double()),
                         softmax_row_shape_gap=_scalar(multi[i].double() - single.double()))
    # The full logits matrix is no longer needed. Retain only bounded scalars and
    # per-point legal masks while each original full-prefix forward is evaluated.
    del out, logits, multi
    for point in points:
        i = point['offset']
        position = row['steps'][i]['position']
        prefix, prefix_event = _forward(actor, report, row, row['original_ids'][:position+1],
                                        1, deadline, check_state)
        with _work(actor, report, 'numeric-shadow-reduce', deadline, {'host_operations': 1},
                   trajectory_id=row['trajectory_id']):
            need(prefix.logits.shape == (1, 1, actor.native.vocab_size), 'exact prefix M1 head shape required')
            pi = rl_math.selected_log_probs(prefix.logits[0], allowed[i:i+1], chosen[i:i+1])[0]
            point.update(prefix_event_id=prefix_event, prefix_m1_log_pi=_scalar(pi),
                         teacher_vs_prefix_gap=_scalar(point['eval_multirow_log_pi'] - pi.double()),
                         single_reduction_teacher_vs_prefix_gap=_scalar(point['same_logits_single_row_log_pi'] - pi.double()),
                         prefix_vs_actor_gap=_scalar(pi.double() - old['log_mu'][i]),
                         prefix_logits_shape=list(prefix.logits.shape), prefix_logits_dtype=str(prefix.logits.dtype),
                         inferred_prefix_head_input_shape=[1, 1, actor.model.get_output_embeddings().weight.shape[1]],
                         prefix_input_tokens=position+1, status='complete')
        del prefix, pi
    result['status'] = 'complete'


def run_numeric_shadow(actor, batch, replay_reports, *, deadline):
    """Return bounded private evidence; never consume a batch or update state.

    Call before the original rollback/commit/acknowledgment, even when its numeric
    gate failed. The caller must intentionally perform no optimizer commit.
    """
    report = {'schema': SCHEMA, 'complete': False, 'status': 'incomplete',
              'update_batch_id': batch.get('id'), 'batch_index': batch.get('batch_index'),
              'selection': {'parent_ordinals': list(PARENT_ORDINALS), 'slot': 0,
                            'offsets': ['0', '1', 'last'], 'substitution': False},
              'rows': [], 'physical_event_ids': [], 'model_forward_calls': 0,
              'head_projection_calls': 0, 'state_preserved': False,
              'optimizer_commit_allowed': False, 'gate_inputs_replaced': False,
              'limits': {'model_forwards': 8, 'head_projections': 0, 'seconds': MAX_SECONDS,
                         'forward_seconds': MAX_FORWARD_SECONDS,
                         'allocated_bytes': MAX_ALLOCATED, 'reserved_bytes': MAX_RESERVED},
              'interpretation': {'train_vs_eval': 'mode-autograd-checkpointing-combined',
                                 'teacher_vs_prefix': 'hidden-state-and-head-row-shape-combined',
                                 'prefix_vs_actor': 'full-prefix-versus-original-actor-same-M1',
                                 'head_shape_causality_isolated': False}}
    started = time.monotonic()
    end = min(deadline, actor._phase_deadline, actor.global_deadline, started + MAX_SECONDS)
    before = rng = None
    event_start = len(actor.ledger.events)
    try:
        with actor._lock, _work(actor, report, 'numeric-shadow', end, {'diagnostics': 1}):
            try:
                with _work(actor, report, 'numeric-shadow-preflight', end, {'host_operations': 1}):
                    before = _state(actor)
                    rng = actor.trainer._get_rng()
                    selected = _select(actor, batch, replay_reports, report)
                    report['source_binding'] = _source_binding(actor)
                def check_state():
                    current = _state(actor)
                    need(all(not mode for _, mode in current['modes']), 'shadow left eval mode')
                    current['modes'] = before['modes']
                    need(current == before, 'shadow changed owned training state')
                    need(tree_sha(actor.trainer._get_rng()) == tree_sha(rng),
                         'shadow changed caller RNG state')
                with actor._mode(False), torch.inference_mode():
                    for row, old, result in selected:
                        _diagnose_row(actor, row, old, result, report, end, check_state)
                report.update(complete=True, status='complete')
            finally:
                # Always restore the caller's RNG and exact mixed training modes.
                # Never clear gradients or restore adapter/optimizer tensors here.
                if rng is not None:
                    unchanged_rng = tree_sha(actor.trainer._get_rng()) == tree_sha(rng)
                    actor.trainer._set_rng(rng)
                    need(unchanged_rng and tree_sha(actor.trainer._get_rng()) == tree_sha(rng),
                         'shadow changed caller RNG state')
                if before is not None:
                    need(_state(actor) == before, 'shadow changed owned training state')
                    report['state_preserved'] = True
    except Exception as exc:
        report.update(complete=False, status='incomplete', error_type=type(exc).__name__,
                      reason=str(exc)[:240])
    # Includes a reservation whose pre-yield synchronize/deadline check failed.
    report['physical_event_ids'] = [e['event_id'] for e in actor.ledger.events[event_start:]
                                    if e['phase'].startswith('numeric-shadow')]
    report['seconds'] = time.monotonic() - started
    need(len(canonical(report)) <= MAX_REPORT_BYTES, 'bounded private shadow report exceeded')
    return report
