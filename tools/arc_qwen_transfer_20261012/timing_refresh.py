"""Target-blind PUBLIC cost refresh from the complete fixed main timing panel.

Only allowlisted timing sidecars enter the estimator. Full native receipts are
hashed as opaque bytes, never parsed here. Correctness, text, validity, EOS and
selection rankings are deliberately absent from this interface.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import time
from .protocol import PROTOCOL, require, digest, file_sha, checked_json
from .call_policy import policy as call_policy, generation_window, finite_clock
from tools.arc_learning_agent_20261011.budget import atomic_json, digest as ledger_digest

ROOT = Path(__file__).resolve().parents[2]
TIMING_FORMAT = 'irisx/transfer-native-generation-timing-v1'
SOURCE_NAMES = tuple('tools/' + name for name in (
    'arc_qwen_transfer_20261012/backend.py', 'arc_qwen_transfer_20261012/decoder.py',
    'arc_qwen_transfer_20261012/experiment.py', 'arc_qwen_transfer_20261012/call_policy.py',
    'arc_qwen_transfer_20261012/science_profiles.py', 'arc_qwen_transfer_20261012/timing_refresh.py',
    'arc_qwen_transfer_20261012/protocol.py', 'arc_qwen_probe_20261012/decoder.py',
    'arc_learning_agent_20261011/native_model.py', 'arc_learning_agent_20261011/qwen14b_model.py',
    'arc_learning_agent_20261011/budget.py', 'arc_learning_agent_20261011/metering.py'))
TRACE_FIELDS = ('input_tokens', 'attention_mask_tokens', 'position_start', 'position_end',
                'cache_before', 'cache_after', 'use_cache', 'started_monotonic',
                'completed_monotonic', 'deadline_monotonic')


def timing_sources():
    return {name: file_sha(ROOT / name) for name in SOURCE_NAMES}


def write_generation_timing(path, generation, *, native_invoked, started, persisted):
    """Project timing at its producer, before any prediction/scoring logic."""
    path = Path(path)
    payload = {'format': TIMING_FORMAT, 'source_sha256': timing_sources(),
        'receipt_sha256': file_sha(path), 'native_invoked': native_invoked,
        'physical_event_id': generation.get('physical_event_id'),
        'evidence_timing': {'clock': 'time.monotonic', 'started_monotonic': started,
                           'receipt_persisted_monotonic': persisted},
        'adapter_execution_mode': generation.get('adapter_execution_mode'),
        'decoder_mode': generation.get('decoder_mode'),
        'generation_call_policy': generation.get('generation_call_policy'),
        'call_window': generation.get('call_window'),
        'wrapper_timing': generation.get('wrapper_timing'),
        'native_timing': generation.get('native_timing'),
        'forward_calls': generation.get('forward_calls', 0),
        'forward_input_tokens': generation.get('forward_input_tokens', 0),
        'input_tokens': generation.get('input_tokens', 0),
        'output_tokens': generation.get('output_tokens', 0),
        'forward_trace': [{k: row.get(k) for k in TRACE_FIELDS}
                          for row in generation.get('forward_trace', [])]}
    # evaluate_cases records completion after this evidence write and row
    # persistence in a timing-only boundary record, without timing a write
    # from inside that same write or subtracting guessed IO costs.
    target = path.with_suffix('.timing.json')
    atomic_json(target, payload, exclusive=True)
    return {'path': str(target.absolute()), 'sha256': file_sha(target)}


def main_slots(root, updates):
    """Fixed source-declared panel; no outcome/path discovery filters."""
    root = Path(root)
    groups = [('dev', 'base', 16, 'base')]
    groups += [('dev', 'sft' + str(u), 16, 'trained') for u in updates]
    groups += [('holdout', 'base', 32, 'base'), ('holdout', 'selected-sft', 32, 'trained')]
    return [{'path': root / scope / name / ('%03d-%d.json' % (i, op)), 'mode': mode,
             'scope': scope, 'method': name}
            for scope, name, count, mode in groups for i in range(count)
            for op in PROTOCOL['query_transforms']]


def _integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, 'invalid ' + name)
    return value


def _clocks(values, *, now, name):
    require(values, 'clock coverage required: ' + name)
    for value in values:
        finite_clock(value, name)
        require(value <= now, 'future timing timestamp: ' + name)
    require(all(a <= b for a, b in zip(values, values[1:])), 'unordered timing clocks: ' + name)


def _ledger_snapshot(ledger):
    """Replay the persisted chain; unknown work is never refunded or omitted."""
    require(not ledger.pending, 'pending ledger work prevents timing refresh')
    raw = ledger.path.read_bytes()
    require(len(raw) <= 16 * 1024**2, 'bounded timing ledger required')
    rows = [json.loads(line) for line in raw.splitlines()]
    require(rows == ledger.events and rows, 'persisted/live ledger differs')
    previous = '0' * 64; pending = {}; used = dict.fromkeys(ledger.caps, 0)
    for index, row in enumerate(rows):
        require(row.get('index') == index and row.get('previous') == previous and
                row.get('sha256') == ledger_digest({k: v for k, v in row.items() if k != 'sha256'}),
                'timing ledger chain differs')
        previous = row['sha256']; kind = row.get('event'); event = row.get('event_id')
        if kind == 'opened':
            require(index == 0 and row['caps'] == ledger.caps, 'timing ledger opening differs')
        elif kind == 'reserved':
            require(event not in pending, 'duplicate pending event')
            pending[event] = row['amounts']
            for key, value in row['amounts'].items(): used[key] += value
        elif kind in ('complete', 'failed', 'excluded'):
            reservation = pending.pop(event)
            require(set(row['amounts']) == set(reservation), 'timing ledger amount keys differ')
            for key, value in row['amounts'].items():
                require(type(value) is int and 0 <= value <= reservation[key], 'invalid ledger charge')
                used[key] -= reservation[key] - value
        elif kind == 'unknown':
            require(event in pending and row['charged'] == pending[event], 'unknown charge differs')
        else: raise ValueError('unexpected timing ledger event')
    require(not pending and used == ledger.used and previous == ledger._previous,
            'timing ledger totals/head differ')
    return rows, {'path': str(ledger.path.absolute()), 'sha256': file_sha(ledger.path),
                  'head_sha256': previous, 'event_count': len(rows), 'physical_usage': dict(ledger.used)}


def _calibration_native_floor(calibration, *, now):
    """Use explicitly timed native intervals, never estimated IO subtraction."""
    require(calibration.get('completed_lengths') == [128, 512, 2048, 4096] and
            calibration.get('full_context_measured') is True and
            calibration.get('behavioral_cache_admitted') is True and
            calibration.get('full_state_restoration_verified') is True,
            'complete production calibration context coverage required')
    samples = []; event_ids = []; histories = []
    observations = calibration['observations']
    require([r['length'] for r in observations] == [128, 512, 2048, 4096], 'calibration observations differ')
    for rung in observations:
        require(set(rung['states']) == {'base', 'updated', 'restored'}, 'calibration states incomplete')
        for state_name in ('base','updated','restored'):
            state=rung['states'][state_name]
            found = []
            for f in state['cache']['forwards']:
                # Full calibration is independently admitted above; no filtering
                # on correctness, validity, sequence length success or targets.
                if f['use_cache'] and f['past_supplied']:
                    _clocks([f['started_monotonic'], f.get('native_started_monotonic'),
                             f['completed_monotonic']], now=now, name='calibration-native')
                    require(f['status']=='complete' and f['late'] is False and f['finite_full_head'] is True and
                            f['completed_monotonic']<f['deadline_monotonic']<=f['started_monotonic']+120 and
                            f['deadline_monotonic']<=f['work_deadline_monotonic'] and
                            f['elapsed_seconds']==f['completed_monotonic']-f['started_monotonic'],
                            'calibration native interval/deadline coverage differs')
                    require(f['input_tokens'] == 1 and f['history_tokens'] <= rung['length'],
                            'calibration cached context coverage differs')
                    samples.append(f['completed_monotonic'] - f['native_started_monotonic'])
                    event_ids.append(f['event_id']); histories.append(f['history_tokens']); found.append(f)
            require(found and max(f['history_tokens'] for f in found) == rung['length'],
                    'calibration exact rung context missing')
    require(samples, 'calibration native decode samples missing')
    return max(samples), {'sample_count': len(samples), 'event_ids': event_ids,
                         'context_min': min(histories), 'context_max': max(histories),
                         'clock': 'time.monotonic', 'synchronized_completion': True}


def derive_measurements(timing_rows, calibration, original, *, now):
    """Pure timing interface. Caller already binds every slot, source and event."""
    fixed = []; prefill = []; intervals = []; gaps = []; prompts = []; contexts = []; outputs = []
    modes = set(); method_samples = {}; expected_methods = set(); previous_end = None; invoked = 0
    for item in timing_rows:
        r = item['timing']; e = r['evidence_timing'];method=item['method']
        expected_methods.add(method)
        _clocks([e['started_monotonic'], e['receipt_persisted_monotonic'], item['accounted_through_monotonic']],
                now=now, name='generation-evidence')
        require(e['clock'] == 'time.monotonic', 'wrong evidence clock')
        if previous_end is not None:
            require(e['started_monotonic'] >= previous_end, 'overlapping main timing calls')
        previous_end = item['accounted_through_monotonic']
        if not r['native_invoked']:
            require(r['physical_event_id'] is None and not r['forward_trace'] and r['forward_calls'] == 0,
                    'uninvoked generation has physical work')
            fixed.append(item['accounted_through_monotonic'] - e['started_monotonic'])
            continue
        invoked += 1
        w, n, window = r['wrapper_timing'], r['native_timing'], r['call_window']
        require(r['generation_call_policy'] == call_policy() and
                window == generation_window(window['branch_deadline_monotonic'], now=window['started_monotonic']),
                'generation timing call policy differs')
        require(w['clock'] == n['clock'] == 'time.monotonic' and
                n['forward_completion_synchronized'] is True and
                n['forward_trace_source'] == 'tools/arc_qwen_probe_20261012/decoder.py', 'unsupported native timing clock/source')
        _clocks([e['started_monotonic'], w['started_monotonic'], w['native_entered_monotonic'],
                 n['entered_monotonic'], n['returned_monotonic'], w['native_returned_monotonic'],
                 w['completed_monotonic'], e['receipt_persisted_monotonic']], now=now, name='native-wrapper')
        require(w['started_monotonic'] == window['started_monotonic'], 'window/wrapper start differs')
        require(n['returned_monotonic']<=w['native_returned_monotonic']<window['work_deadline_monotonic'] and
                w['completed_monotonic']<window['deadline_monotonic'] and
                item['accounted_through_monotonic']<=window['branch_deadline_monotonic'],
                'late operational main call cannot support timing refresh')
        require(r['adapter_execution_mode'] == item['mode'], 'main adapter timing state differs')
        require(r['decoder_mode'] == 'cached', 'native cached mode timing required')
        trace = r['forward_trace']; count = _integer(r['forward_calls'], 'forward count')
        require(type(trace) is list and len(trace) == count, 'incomplete native forward trace')
        _integer(r['forward_input_tokens'], 'forward token count'); _integer(r['output_tokens'], 'output count')
        require(r['output_tokens'] <= count <= PROTOCOL['grid_output_cap'], 'forward/output count exceeds cap')
        require(sum(t['input_tokens'] for t in trace) == r['forward_input_tokens'], 'native forward totals differ')
        if not trace:
            fixed.append(item['accounted_through_monotonic'] - e['started_monotonic'])
            continue
        modes.add(r['adapter_execution_mode'])
        if len(trace)>1:method_samples[method]=method_samples.get(method,0)+len(trace)-1
        prompt = _integer(r['input_tokens'], 'prompt count', 1)
        require(prompt <= PROTOCOL['prompt_cap'], 'main prompt exceeds cap')
        last = n['entered_monotonic']
        for i, t in enumerate(trace):
            _clocks([last, t['started_monotonic'], t['completed_monotonic'], n['returned_monotonic']],
                    now=now, name='native-forward')
            require(t['deadline_monotonic'] == window['work_deadline_monotonic'], 'trace call deadline differs')
            require(t['use_cache'] is True and t['input_tokens'] == (prompt if i == 0 else 1) and
                    t['cache_before'] == (0 if i == 0 else prompt + i - 1) and
                    t['cache_after'] == t['attention_mask_tokens'] == prompt + i and
                    t['position_start'] == (0 if i == 0 else prompt + i - 1) and
                    t['position_end'] == prompt + i - 1, 'incomplete cached context/position coverage')
            if i:
                intervals.append(t['completed_monotonic'] - last)
                gaps.append(t['started_monotonic'] - last)
            last = t['completed_monotonic']; contexts.append(t['attention_mask_tokens'])
        prefill.append((trace[0]['completed_monotonic'] - trace[0]['started_monotonic']) / prompt)
        # Everything before the first forward and after the last completion is
        # fixed per-call overhead. Actual adjacent completions include all loop
        # work, synchronization and sampling between forwards without subtraction.
        fixed.append(trace[0]['started_monotonic'] - e['started_monotonic'] +
                     item['accounted_through_monotonic'] - trace[-1]['completed_monotonic'])
        prompts.append(prompt); outputs.append(r['output_tokens'])
    require(modes == {'base', 'trained'} and intervals and prefill and fixed and
            set(method_samples)==expected_methods,
            'base/trained/per-method cached main timing coverage incomplete')
    native_floor, calibration_coverage = _calibration_native_floor(calibration, now=now)
    refreshed = deepcopy(original)
    refreshed.update(generation_fixed_seconds=max(fixed),
        prefill_seconds_per_input=max(original['prefill_seconds_per_input'], max(prefill)),
        decode_seconds_per_call=max(max(intervals), native_floor + max(gaps)))
    coverage = {'main_slots': len(timing_rows), 'native_invoked_calls': invoked,
        'adapter_modes': sorted(modes),'method_adjacent_samples':method_samples, 'adjacent_completion_samples': len(intervals),
        'prompt_tokens_min': min(prompts), 'prompt_tokens_max': max(prompts),
        'cached_context_min': min(contexts), 'cached_context_max': max(contexts),
        'output_tokens_min': min(outputs), 'output_tokens_max': max(outputs),
        'calibration': calibration_coverage, 'maximum_adjacent_completion_seconds': max(intervals),
        'maximum_main_interstep_gap_seconds': max(gaps), 'maximum_calibration_native_decode_seconds': native_floor,
        'fixed_per_call_seconds': max(fixed),
        'extrapolation': 'full3072-prefill-and1023-cached-steps; max-calibrated-native-plus-max-main-gap floor',
        'limitations': ['Finite empirical forecast, not a worst-case mathematical guarantee.',
            'Calibration covers native cache contexts through4096; main prompt/output ranges are recorded above.',
            'Unobserved longer production output tails can have different sampling/constraint/host overhead.',
            'No output-tail speed, EOS savings, validity savings or correctness savings is assumed.',
            'Per-call evidence/row writes are measured through separate timing-only boundaries; panel-level freeze IO is consumed before admission.'],
        'target_outcomes_used': False, 'outcome_filtering': False}
    return refreshed, coverage


def freeze_public_refresh(root, *, updates, calibration, original, ledger, main_event_start,
                          main_started, expected_sources, tiny=False):
    """Freeze one immutable choice before PUBLIC input access or admission."""
    from .science_profiles import forecast
    root = Path(root); now = time.monotonic()
    baseline = forecast(original, updates=0, generations=334, reloads=2)
    result = {'format': 'irisx/transfer-public-cost-refresh-v1', 'frozen_monotonic': now,
        'main_started_monotonic': main_started, 'target_outcomes_used': False, 'outcome_filtering': False,
        'forecast_is_guarantee': False, 'original_measurements': deepcopy(original),
        'original_estimate': baseline, 'refreshed_measurements': None, 'refreshed_estimate': None,
        'selected_estimate': baseline, 'selected_measurements': deepcopy(original),
        'status': 'CALIBRATION_FALLBACK', 'reason': None, 'coverage': None,
        'source_sha256': expected_sources, 'source_identity_sha256': digest(expected_sources),
        'calibration_sha256': digest(calibration), 'main_event_start': main_event_start,
        'receipt_bindings': [], 'ledger': None, 'boundaries':None, 'cpu_fixture_only': tiny}
    try:
        require(timing_sources() == expected_sources, 'timing source changed during main')
        _clocks([main_started, now], now=now, name='main')
        events, result['ledger'] = _ledger_snapshot(ledger)
        _integer(main_event_start, 'main event start', 1)
        require(main_event_start <= len(events), 'main event interval differs')
        reserved = {r['event_id']: r for r in events[main_event_start:]
                    if r['event'] == 'reserved' and 'generation_calls' in r['amounts']}
        closed = {r['event_id']: r for r in events[main_event_start:]
                  if r['event'] in ('complete', 'failed', 'excluded') and 'generation_calls' in r['amounts']}
        require(set(reserved) == set(closed), 'main native generation events incompletely closed')
        boundary_path=root/'main-timing-boundaries.json'
        boundary=checked_json(boundary_path,file_sha(boundary_path))
        require(boundary['format']=='irisx/transfer-main-timing-boundaries-v1' and
                boundary['source_sha256']==expected_sources and boundary['main_event_start']==main_event_start and
                boundary['main_started_monotonic']==main_started,'main boundary identity differs')
        boundaries={row['receipt_path']:row for row in boundary['calls']}
        require(len(boundaries)==len(boundary['calls'])==len(main_slots(root,updates)),'fixed main timing boundary coverage differs')
        result['boundaries']={'path':str(boundary_path.absolute()),'sha256':file_sha(boundary_path)}
        rows = []; seen = set()
        for slot in main_slots(root, updates):
            path = slot['path']; side = path.with_suffix('.timing.json')
            require(path.is_file() and side.is_file() and not path.is_symlink() and not side.is_symlink(),
                    'fixed main receipt/timing coverage missing')
            r = checked_json(side, file_sha(side), cap=2 * 1024**2)
            require(r['format'] == TIMING_FORMAT and r['source_sha256'] == expected_sources and
                    r['receipt_sha256'] == file_sha(path), 'main source/opaque-receipt timing binding differs')
            require(type(r['native_invoked']) is bool, 'native invocation clock coverage required')
            event = r['physical_event_id']
            if r['native_invoked']:
                require(event in closed and event not in seen, 'main timing generation event absent/duplicate')
                seen.add(event); charge = closed[event]['amounts']
                require(charge == {'generation_calls': int(r['forward_calls'] > 0),
                    'input_tokens': r['forward_input_tokens'], 'output_tokens': r['output_tokens']},
                    'main generation receipt/ledger charge differs')
                require(r['wrapper_timing']['ledger_head_sha256'] == closed[event]['sha256'],
                        'generation receipt event head differs')
            else:
                require(event is None, 'non-native main call has event')
            require(r['evidence_timing']['started_monotonic'] >= main_started, 'main call before interval')
            bound=boundaries.pop(str(path.absolute()))
            require(bound['timing_sha256']==file_sha(side),'main boundary/sidecar binding differs')
            rows.append({'timing': r, 'mode': slot['mode'],'method':slot['scope']+'/'+slot['method'],
                         'accounted_through_monotonic':bound['completed_monotonic']})
            result['receipt_bindings'].append({'path': path.relative_to(root).as_posix(),
                'sha256': r['receipt_sha256'], 'timing_sha256': file_sha(side), 'physical_event_id': event,
                'event_sha256': closed[event]['sha256'] if event is not None else None})
        require(not boundaries and seen == set(reserved), 'main generation timing omitted physical events')
        rows.sort(key=lambda r: r['timing']['evidence_timing']['started_monotonic'])
        refreshed, coverage = derive_measurements(rows, calibration, original, now=now)
        all_closed={r['event_id']:r for r in events if r['event'] in ('complete','failed','excluded')}
        calibration_bindings=[]
        for event in coverage['calibration']['event_ids']:
            row=all_closed[event]
            require(row['amounts']=={'scoring_forwards':1,'input_tokens':1},'calibration native event charge differs')
            calibration_bindings.append({'event_id':event,'event_sha256':row['sha256']})
        coverage['calibration']['event_bindings']=calibration_bindings
        estimate = forecast(refreshed, updates=0, generations=334, reloads=2)
        result.update(status='MAIN_TIMING_REFRESHED', reason='complete-source-event-clock-context-coverage',
            refreshed_measurements=refreshed, refreshed_estimate=estimate, selected_measurements=refreshed,
            selected_estimate=estimate, coverage=coverage)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        # Missing instrumentation is not a cheaper estimate. Keep the exact
        # original conservative forecast; never discard inconvenient samples.
        result['reason'] = 'unsupported-timing-coverage: ' + type(exc).__name__ + ': ' + str(exc)[:512]
    result['receipt_bindings_sha256'] = digest(result['receipt_bindings'])
    path = root / 'public-cost-refresh.json'
    atomic_json(path, result, exclusive=True)
    return result, {'path': str(path.absolute()), 'sha256': file_sha(path)}
