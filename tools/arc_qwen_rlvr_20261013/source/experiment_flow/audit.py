"""Audit reporting never turns an unattempted slot into a rewarded attempt."""
from collections import Counter
from .contracts import require


def empty_batch(parent_ids, group_size, sweep, reason):
    return {'sweep': sweep, 'batch_index': sweep, 'parent_ids': list(parent_ids), 'policy_version': None, 'planned_attempts': len(parent_ids) * group_size,
            'rows': [{'parent_id': parent, 'slot': slot, 'trajectory': None, 'reward': None,
                      'eligible': False, 'status': 'not-reached', 'reason': reason}
                     for parent in parent_ids for slot in range(group_size)],
            'closed': True, 'all_slots_reached': False, 'fatal_native_state': False}


def summarize(batch, parent_ids, group_size):
    rows = batch['rows']
    require([(r['parent_id'], r['slot']) for r in rows] ==
            [(parent, slot) for parent in parent_ids for slot in range(group_size)], 'fixed audit slots/order differ')
    require(batch['planned_attempts'] == len(rows), 'planned audit denominator differs')
    groups = []
    for parent in parent_ids:
        group = [r for r in rows if r['parent_id'] == parent]
        eligible = [r for r in group if r['eligible']]
        for row in group:
            require(type(row['eligible']) is bool, 'boolean reward eligibility')
            require((type(row['reward']) is int and row['reward'] in (0, 1)) if row['eligible'] else row['reward'] is None,
                    'eligible exact reward or null infrastructure reward required')
            if row['status'] == 'not-reached':
                require(row['trajectory'] is None and row['reward'] is None and not row['eligible'], 'unattempted slot mutated')
        successes = sum(r['reward'] for r in eligible)
        groups.append({'parent_id': parent, 'planned': group_size, 'eligible': len(eligible), 'successes': successes,
                       'mixed': 0 < successes < len(eligible),
                       'all_zero': len(eligible)==group_size and successes == 0,
                       'all_one': len(eligible)==group_size and successes == len(eligible),
                       'pass_at_8': int(successes > 0) if group_size == 8 and len(eligible) == 8 else None,
                       'fixture_full_group_success': int(successes > 0) if len(eligible) == group_size else None})
    counts = Counter(r['status'] for r in rows)
    eligible_count = sum(r['eligible'] for r in rows)
    context = sum(r['status'] == 'context-excluded' or
                  bool(r.get('trajectory', {}).get('context_excluded')) if r.get('trajectory') else r['status'] == 'context-excluded'
                  for r in rows)
    dispatched = sum(bool(r.get('trajectory') and (r['trajectory'].get('dispatched') or r['trajectory'].get('steps')))
                     for r in rows)
    infrastructure = sum(not r['eligible'] and r['status'] != 'not-reached' for r in rows) - context
    return {'planned_attempts': len(rows), 'actual_dispatched_attempts': dispatched,
            'reward_eligible_attempts': eligible_count, 'infrastructure_exclusions': infrastructure,
            'context_exclusions': context, 'not_reached': counts['not-reached'],
            'eligible_mean_reward': sum(r['reward'] for r in rows if r['eligible']) / eligible_count if eligible_count else None,
            'eligible_mean_denominator': eligible_count,
            'complete': counts['not-reached'] == 0 and infrastructure == 0 and context == 0,
            'all_slots_reached': counts['not-reached'] == 0,
            'mixed_groups': sum(g['mixed'] for g in groups), 'groups': groups,
            'pass_at_8_coverage': sum(g['pass_at_8'] is not None for g in groups),
            'status_counts': dict(counts), 'fatal_native_state': batch.get('fatal_native_state', False)}


def full_panel_summary(entries,parent_ids,group_size):
    """A complete fixed denominator, with no zero-success inference from absence."""
    parent_ids=tuple(parent_ids)
    rows=[r for entry in entries for r in entry['batch']['rows']]
    merged={'rows':rows,'planned_attempts':len(parent_ids)*group_size,
            'fatal_native_state':any(bool(entry['batch'].get('fatal_native_state')) for entry in entries)}
    summary=summarize(merged,parent_ids,group_size)
    return {'format':'fixed-disjoint-panel-audit-v1','parent_ids':list(parent_ids),
            'planned_parents':len(parent_ids),'planned_attempts':len(parent_ids)*group_size,
            'group_size':group_size,'planned_batches':len(entries),
            'batch_parent_ids':[entry['parent_ids'] for entry in entries],
            'batch_statuses':[entry['status'] for entry in entries],
            'physical_attempted_batches':sum(entry['status']!='not-reached' for entry in entries),
            'optimizer_updates':sum(entry['status']=='updated' and entry.get('update') is not None and entry['update'].get('optimizer_committed') is True for entry in entries),
            'physical_optimizer_commit_attempts':sum(entry.get('update') is not None and entry['update'].get('optimizer_dispatched') is True for entry in entries),
            'all32_coverage_complete':len(parent_ids)==32 and summary['complete'],
            'all_zero_panel':summary['complete'] and summary['reward_eligible_attempts']==len(parent_ids)*group_size and summary['eligible_mean_reward']==0.,
            'partial_is_not_zero_signal':True,'summary':summary}
