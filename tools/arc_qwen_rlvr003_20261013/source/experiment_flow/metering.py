"""Explicit bridge receipt, not compatibility with the old BudgetLedger validator."""
from collections import Counter
import math
from .contracts import require, digest


def close_metering(events, phase_intervals, *, model_closure=None):
    ids = [e['event_id'] for e in events]
    require(len(ids) == len(set(ids)), 'physical event identity reused')
    require(all(e.get('ended') is not None and e.get('seconds', -1) >= 0 for e in events), 'physical event not settled')
    for e in [*events, *phase_intervals]:
        require(all(type(e.get(k)) in (int,float) and math.isfinite(e[k]) for k in ('started','ended','seconds')), 'finite event interval')
        require(e['ended'] >= e['started'] and abs(e['seconds'] - (e['ended'] - e['started'])) <= .001, 'ordered consistent event interval')
        require(e['status'] not in ('started','reserved','unclosed-device-error','unsettled-device-state','unknown'), 'unsettled physical event')
    status = Counter(e['status'] for e in events)
    # Only source-designated forward events contribute forward token totals.
    # Parent update/save/phase intervals are never added to these durations.
    forward_phases = {'sample-forward', 'causal-replay', 'anchor-sft-forward-backward',
                      'control-sft-forward-backward', 'evaluation-generation'}
    forward_events = [e for e in events if e['phase'] in forward_phases and e.get('dispatched')]
    tokens = sum(e.get('input_tokens', 0) for e in forward_events)
    tokens += sum(e.get('forward_input_tokens',0) for e in events if e['phase']=='rollout-generation' and e.get('dispatched'))
    tokens += sum(e.get('actual_cost',{}).get('input_tokens',0) for e in events if e['phase'].startswith('calibration-') and e.get('dispatched'))
    return {'format': 'rl-session-metering-bridge-v1', 'event_identity_namespace': 'owned-session-physical-event-id',
            'event_ids': ids, 'event_count': len(events), 'events_sha256': digest(events),
            'actual_dispatched_events': sum(bool(e.get('dispatched')) for e in events),
            'status_counts': dict(status), 'known_forward_input_tokens': tokens,
            'token_accounting_scope': 'recorded forward-event input tokens only; not backward/recompute FLOPs',
            'whole_arm_intervals': phase_intervals, 'nested_event_duration_sum_used': False,
            'logical_rollback_can_refund_cost': False, 'model_closure': model_closure,
            'historical_BudgetLedger_or_MeteredTrainer_compatible': False,
            'production_validator_admitted': False,
            'required_RL_validator_inputs': ['source/protocol/forecast seals', 'all owned physical events',
                'whole-arm synchronized intervals and original session origin', 'actual checkpoint manifests and reload proofs',
                'fixed-slot rollout/audit/update receipts', 'sealed per-transform and per-case predictions',
                'dev decision before holdout escrow', 'model closure and unchanged original PUBLIC scorer binding']}


def compact_event_projections(value,reference):
    """One full event union file; nested receipts retain byte-bound references."""
    if isinstance(value,dict):
        return {('physical_events_ref' if k=='physical_events' else k):
                (dict(reference) if k=='physical_events' else compact_event_projections(v,reference))
                for k,v in value.items()}
    if isinstance(value,list):return [compact_event_projections(v,reference) for v in value]
    return value
