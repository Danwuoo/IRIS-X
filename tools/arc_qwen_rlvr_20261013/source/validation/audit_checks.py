"""Recompute fixed sweep denominators and original-token update admission."""
from collections import Counter
import math
from .safe_io import need, integer, finite, digest, same, is_sha
from .grid_checks import decode

def summary(batch, parents, group_size):
    need(type(batch) is dict and type(batch.get('rows')) is list, 'actual audit batch required')
    rows=batch['rows']
    need(all(type(r.get('parent_id')) is str and r['parent_id'] and integer(r.get('slot'),0,group_size-1) for r in rows),'strict fixed parent/slot identities')
    need([(r.get('parent_id'),r.get('slot')) for r in rows]==[(p,k) for p in parents for k in range(group_size)], 'fixed audit slot order/coverage differs')
    need(integer(batch.get('planned_attempts')) and batch['planned_attempts']==len(rows), 'planned denominator differs')
    groups=[]
    for parent in parents:
        rs=[r for r in rows if r['parent_id']==parent]
        for r in rs:
            need(type(r.get('eligible')) is bool, 'strict reward eligibility')
            need(integer(r.get('reward'),0,1) if r['eligible'] else r.get('reward') is None, 'binary eligible reward or nullable exclusion required')
            need(r.get('status') in ('eligible','model-invalid','truncated','context-excluded','infrastructure-excluded','not-reached'), 'closed audit status')
            if r['status']=='not-reached':
                need(r.get('trajectory') is None and not r['eligible'], 'not-reached slot cannot contain trajectory/reward')
            if r['status'] in ('context-excluded','infrastructure-excluded'):
                need(not r['eligible'], 'excluded trajectory cannot receive reward')
            if r['status'] in ('model-invalid','truncated'):
                need(r['eligible'] and r['reward']==0, 'model-invalid trajectory reward must be zero')
        es=[r for r in rs if r['eligible']]; successes=sum(r['reward'] for r in es)
        groups.append({'parent_id':parent,'planned':group_size,'eligible':len(es),'successes':successes,
                       'mixed':0<successes<len(es),'all_zero':bool(es) and successes==0,'all_one':bool(es) and successes==len(es),
                       'pass_at_8':int(successes>0) if group_size==8 and len(es)==8 else None,
                       'fixture_full_group_success':int(successes>0) if len(es)==group_size else None})
    counts=Counter(r['status'] for r in rows)
    eligible=sum(r['eligible'] for r in rows)
    context=sum(r['status']=='context-excluded' or bool((r.get('trajectory') or {}).get('context_excluded')) for r in rows)
    dispatched=sum(bool(r.get('trajectory') and (r['trajectory'].get('dispatched') or r['trajectory'].get('steps'))) for r in rows)
    excluded=sum(not r['eligible'] and r['status']!='not-reached' for r in rows)-context
    return {'planned_attempts':len(rows),'actual_dispatched_attempts':dispatched,'reward_eligible_attempts':eligible,
            'infrastructure_exclusions':excluded,'context_exclusions':context,'not_reached':counts['not-reached'],
            'eligible_mean_reward':sum(r['reward'] for r in rows if r['eligible'])/eligible if eligible else None,
            'eligible_mean_denominator':eligible,'complete':counts['not-reached']==0 and excluded==0 and context==0,
            'all_slots_reached':counts['not-reached']==0,'mixed_groups':sum(g['mixed'] for g in groups),
            'groups':groups,'pass_at_8_coverage':sum(g['pass_at_8'] is not None for g in groups),
            'status_counts':dict(counts),'fatal_native_state':batch.get('fatal_native_state',False)}

def trajectory(t, row, batch, *, expected_seed, events):
    need(type(t) is dict, 'eligible trajectory evidence missing')
    need(t.get('parent_id')==row['parent_id'] and t.get('policy_version')==batch['policy_version'], 'trajectory parent/policy differs')
    need(type(t.get('seed')) is int and t['seed']==expected_seed, 'frozen sampling seed differs')
    need(t.get('generation_epoch')==batch.get('generation_epoch'), 'trajectory generation epoch differs')
    need(is_sha(t.get('messages_sha256')) and is_sha(t.get('identity')), 'actual prompt/actor identity missing')
    sample=t.get('sampling',{})
    need(sample.get('temperature')==1. and sample.get('top_p')==1. and sample.get('dfa') is True and sample.get('cache_mode') in ('cached','full_prefix'), 'fixed sampling policy differs')
    prompt, tokens, steps=t.get('prompt_ids'),t.get('generated_ids'),t.get('steps')
    need(type(prompt) is list and prompt and all(integer(x,0,151935) for x in prompt), 'actual prompt token IDs required')
    need(type(tokens) is list and type(steps) is list and len(tokens)==len(steps) and all(integer(x,0,151935) for x in tokens), 'original actor tokens/steps differ')
    need(t.get('original_ids')==prompt+tokens and t.get('attention_mask')==[1]*(len(prompt)+len(tokens)), 'causal original sequence differs')
    need(t.get('origins')==['prompt']*len(prompt)+['assistant_generated']*len(tokens), 'assistant loss origins differ')
    state=(0,1,0);decoded='';eos_seen=False
    for i,(token,s) in enumerate(zip(tokens,steps)):
        need(not eos_seen,'actor tokens continue after EOS')
        width,nrows,column=state
        allowed=list(range(15,25)) if column<(width or 30) else []
        if column>0 and nrows<30 and (not width or column==width):allowed.append(198)
        if column>0 and (not width or column==width):allowed += [151643,151645]
        need(s.get('support')==sorted(allowed) and s.get('dfa_state')==list(state),'actor exact legal DFA support/state differs')
        if token in (151643,151645):eos_seen=True
        elif token==198:state=(width or column,nrows+1,0);decoded+='\n'
        elif integer(token,15,24):state=(width,nrows,column+1);decoded+=str(token-15)
        else:need(False,'actor token outside pinned grid alphabet')
        support=s.get('support')
        need(type(support) is list and support==sorted(set(support)) and token in support and all(integer(x,0,151935) for x in support), 'recorded action/support differs')
        need(s.get('token')==token and s.get('position')==len(prompt)+i-1 and s.get('prefix_sha256')==digest(prompt+tokens[:i]), 'causal position/prefix differs')
        need(finite(s.get('log_mu')) and s['log_mu']<=1e-6, 'finite original actor log probability required')
        event=events.get(s.get('actor_event_id'))
        need(event is not None and event.get('phase') in ('sample-forward','rollout-generation') and event.get('dispatched') is True, 'actor forward absent from physical event union')
        if event['phase']=='rollout-generation':
            need(s.get('actor_forward_index')==i and type(s.get('actor_forward_index')) is int, 'dense original actor forward indices required')
    compact=t.get('physical_accounting')=='one-durable-generation-with-dense-original-forward-indices'
    ids=[s['actor_event_id'] for s in steps]
    if compact:
        need(len(set(ids))==1 and t.get('physical_event_ids')==[ids[0]], 'one durable parent per trajectory')
        parent=events[ids[0]]
        tokens_in=len(prompt)+len(steps)-1 if sample['cache_mode']=='cached' else sum(len(prompt)+i for i in range(len(steps)))
        need(parent.get('forward_calls')==len(steps) and parent.get('forward_input_tokens')==tokens_in and parent.get('trajectory_id')==t['trajectory_id'], 'durable generation aggregate differs from original forwards')
    else:
        need(t.get('physical_event_ids')==ids, 'actor event coverage differs')
    need(t.get('dispatched_forwards')==len(steps), 'original forward denominator differs')
    if t.get('finish_reason')=='eos':
        need(eos_seen and t.get('format_text')==decoded,'actor original tokens/EOS/format text differ')
    else:need(not eos_seen,'actor EOS/finish reason differ')
    if row['eligible']:
        need(not t.get('infrastructure_excluded') and tokens, 'eligible trajectory must retain physical model work')
        if t.get('finish_reason')!='eos':
            need(row['reward']==0, 'truncated model output must receive zero reward')
    return [s['log_mu'] for s in steps]

def _stats(gaps):
    if not gaps:
        return {'tokens':0,'max_abs_gap':0.,'p95_abs_gap':0.,'clipped_tokens':0,'unclipped_fraction':1.}
    values=sorted(abs(v) for v in gaps); pos=.95*(len(values)-1);lo=int(pos);hi=min(lo+1,len(values)-1)
    clipped=sum(not(.8<math.exp(max(-20,min(20,v)))<1.28) for v in gaps)
    return {'tokens':len(gaps),'max_abs_gap':max(values),'p95_abs_gap':values[lo]+(values[hi]-values[lo])*(pos-lo),
            'clipped_tokens':clipped,'unclipped_fraction':1-clipped/len(gaps)}

def _compare_stats(got,wanted):
    need(type(got) is dict and set(got)==set(wanted), 'closed replay statistics')
    for k,v in wanted.items():
        need(finite(got[k]) and abs(got[k]-v)<=1e-6, 'replay statistic not derived: '+k)

def physical_replays(update,batch,replays,derived,events,*,require_modern=False):
    need(type(events) is dict,'complete physical event map required for update admission')
    modern=require_modern or 'update_batch_id' in update
    if modern:
        need(update.get('update_batch_id')==update.get('batch_id')==batch['id'],'logical update batch identity differs')
        candidates=[e for e in events.values() if e.get('update_batch_id')==batch['id']]
    else:
        actor_ids=[i for r in batch['rows'] if r.get('trajectory') for i in r['trajectory']['physical_event_ids']]
        need(actor_ids and all(i in events for i in actor_ids),'actual actor work required before replay')
        last=max(events[i]['ended'] for i in actor_ids)
        candidates=[e for e in events.values() if e.get('started',0)>=last]
    mixed={g['parent_id'] for g in derived['groups'] if g['mixed']};used=set();prior_end=0
    replay_events=[e for e in candidates if e.get('phase')=='causal-replay']
    eligible=[r for r in batch['rows'] if r['eligible']]
    need(len(replay_events)>=len(replays),'actual causal replay operations missing')
    for i,(row,diagnostic) in enumerate(zip(eligible,replays)):
        t=row['trajectory'];e=events.get(diagnostic.get('replay_event_id')) if modern else replay_events[i]
        need(e is not None and e['phase']=='causal-replay' and e.get('dispatched') is True and e.get('status')=='complete' and e['event_id'] not in used,'distinct completed physical replay required')
        used.add(e['event_id']);need(e['input_tokens']==len(t['original_ids'])-1 and e.get('checkpointing') is True,'physical replay original input/checkpointing differs')
        need(e['started']>=prior_end and max(events[x]['ended'] for x in t['physical_event_ids'])<=e['started'],'physical replay precedes actor or overlaps previous replay/backward')
        if modern:need(e.get('trajectory_id')==diagnostic.get('trajectory_id')==t['trajectory_id'] and e.get('update_batch_id')==diagnostic.get('update_batch_id')==batch['id'],'replay operation trajectory/batch identity differs')
        prior_end=e['ended'];backward=None
        if row['parent_id'] in mixed:
            options=[x for x in candidates if x.get('phase')=='ddis-backward' and x['started']>=e['ended'] and x['event_id'] not in used]
            backward=events.get(diagnostic.get('backward_event_id')) if modern else (options[0] if options else None)
            need(backward is not None and backward['phase']=='ddis-backward' and backward.get('dispatched') is True and backward.get('status')=='complete' and backward['event_id'] not in used and e['ended']<=backward['started'],'actual distinct ordered mixed-trajectory backward required')
            if modern:need(backward.get('trajectory_id')==t['trajectory_id'] and backward.get('update_batch_id')==batch['id'],'backward operation trajectory/batch differs')
            used.add(backward['event_id']);prior_end=backward['ended']
            need(abs(diagnostic.get('backward_seconds',-1)-backward['seconds'])<=1e-6,'reported backward duration differs from physical operation')
        elif modern:need(diagnostic.get('backward_event_id') is None,'unmixed trajectory cannot invent backward')
        need(abs(diagnostic['seconds']-(e['seconds']+(backward['seconds'] if backward else 0)))<=1e-6,'actual replay/backward duration differs from physical operations')
    if update.get('optimizer_committed'):
        commits=[e for e in candidates if e['phase']=='optimizer-commit' and e.get('dispatched') is True and e.get('status')=='complete' and e['started']>=prior_end]
        need(commits,'committed batch lacks subsequent physical optimizer operation')
        if modern:need(len(commits)==1 and update.get('optimizer_event_id')==commits[0]['event_id'],'one complete fixed-policy batch must cause exactly one physical update')
    if modern and replays:
        started,finished,deadline=update.get('batch_started_monotonic'),update.get('batch_finished_monotonic'),update.get('batch_deadline')
        replay_start=update.get('batch_replay_started');whole=update.get('whole_replay_backward_seconds')
        need(all(finite(x) for x in (started,finished,deadline,replay_start,whole)) and started<=replay_start<=finished and whole>=0,'actual logical cumulative replay timing missing')
        need(replay_start<=min(events[i]['started'] for i in used) and max(events[i]['ended'] for i in used)-replay_start<=whole+.001 and whole<=finished-replay_start+.001,'cumulative replay wall interval differs from physical history')
        need(all(events[i]['deadline']==deadline for i in used),'per-operation replay deadline differs from admitted batch deadline')
        if update.get('optimizer_committed'):need(finished<=deadline+.001,'committed complete batch exceeded cumulative deadline')
    return used


def validate_update(update, batch, derived, *, gate, synthetic, events, require_modern=False):
    if update is None:
        return False
    need(type(update.get('optimizer_committed')) is bool and type(update.get('optimizer_dispatched')) is bool, 'explicit optimizer state required')
    committed=update['optimizer_committed']
    for key,wanted in {'planned_attempts':derived['planned_attempts'],'eligible_attempts':derived['reward_eligible_attempts'],'not_reached':derived['not_reached'],'infrastructure_excluded':derived['infrastructure_exclusions']+derived['context_exclusions'],'actually_dispatched':derived['actual_dispatched_attempts']}.items():
        need(type(update.get(key)) is int and update[key]==wanted,'update audit denominator differs: '+key)
    expected_groups=[{'group':g['parent_id'],'total':g['planned'],'eligible':g['eligible'],'infrastructure_excluded':g['planned']-g['eligible'],'successes':g['successes'],'mean_reward':g['successes']/g['eligible'] if g['eligible'] else None,'mixed':g['mixed'],'all_zero':g['all_zero'],'all_one':g['all_one'],'pass_at_8':g['pass_at_8']} for g in derived['groups']]
    need(same(update.get('groups'),expected_groups),'update exact group-center denominator differs')
    if committed:
        need(derived['complete'] and derived['mixed_groups']>0 and not derived['fatal_native_state'], 'optimizer commit without complete eligible mixed sweep')
        need(update['optimizer_dispatched'] and update.get('status')=='committed', 'commit/dispatch status differs')
        need(finite(update.get('gradient_norm')) and update['gradient_norm']>0, 'finite nonzero gradient required')
        need(update.get('gradient_divisor')=='mixed-groups * eligible-group-size * original-generated-length', 'DDIS denominator differs')
    rs=[r for r in batch['rows'] if r['eligible']]
    replays=update.get('replays',[])
    need(type(replays) is list and len(replays)<=len(rs),'unplanned/repeated unchanged-policy replay')
    if committed:
        need(len(replays)==len(rs), 'complete unchanged-policy replay coverage required')
    if replays or committed:physical_replays(update,batch,replays,derived,events,require_modern=require_modern)
    passed=True
    for r,replay in zip(rs,replays):
        t=r['trajectory']; mu=[s['log_mu'] for s in t['steps']];pi=replay.get('log_pi')
        need(replay.get('parent_id')==r['parent_id'] and same(replay.get('log_mu'),mu), 'replay must use exact original actor probabilities')
        need(type(pi) is list and len(pi)==len(mu) and all(finite(x) and x<=1e-6 for x in pi), 'replay log probability coverage')
        gaps=[p-m for p,m in zip(pi,mu)]; nf=[g for g,s in zip(gaps,t['steps']) if len(s['support'])>1]
        _compare_stats(replay.get('all_tokens'),_stats(gaps));_compare_stats(replay.get('nonforced_tokens'),_stats(nf))
        need(replay.get('forced_tokens')==len(gaps)-len(nf), 'forced token denominator differs')
        need(all(replay.get(k) is True for k in ('original_token_replay','prompt_and_tool_loss_masked','training_mode','checkpointing_active')), 'actual replay/backward recipe differs')
        need(finite(replay.get('seconds')) and replay['seconds']>=0, 'actual replay+backward time required')
        if r['parent_id'] in [g['parent_id'] for g in derived['groups'] if g['mixed']]:
            need(finite(replay.get('backward_seconds')) and 0<=replay['backward_seconds']<=replay['seconds'], 'mixed trajectory backward evidence required')
        st=_stats(nf)
        passed &= st['max_abs_gap']<=gate['maximum_absolute_gap']+1e-7 and st['p95_abs_gap']<=gate['maximum_p95_gap']+1e-7
        passed &= st['unclipped_fraction']>=gate['minimum_unclipped_fraction'] and replay['seconds']<=gate['maximum_replay_seconds']
        for name,maximum in [('peak_memory_bytes','maximum_peak_bytes'),('peak_reserved_bytes','maximum_reserved_bytes')]:
            value=replay.get(name)
            need((synthetic and value is None) or integer(value,0,2**50), 'actual backward allocated/reserved peak required')
            if value is not None:
                passed &= value<=gate.get(maximum,2**63-1)
    if require_modern or 'update_batch_id' in update:
        budget=gate.get('maximum_batch_replay_backward_seconds')
        need(same(update.get('maximum_batch_replay_backward_seconds'),budget),'source-fixed cumulative replay budget differs')
        need(synthetic or finite(budget) and 0<budget<=7200,'finite production cumulative replay budget requires source freeze')
        if budget is not None and replays:
            passed &= update['whole_replay_backward_seconds']<=budget
            need(update['batch_deadline']<=update['batch_replay_started']+budget+.001,'batch deadline exceeds source budget')
    if update.get('numerical_gate') is not None:
        report=update['numerical_gate']; planned={**gate,'maximum_reserved_bytes':gate.get('maximum_reserved_bytes',2**63-1)}
        if require_modern or 'update_batch_id' in update:planned['maximum_batch_replay_backward_seconds']=gate.get('maximum_batch_replay_backward_seconds')
        need(same(report.get('gate'),planned) and same(report.get('per_trajectory'),replays), 'frozen numerical gate or actual per-trajectory evidence differs')
        need(report.get('admitted') is bool(passed), 'numerical admission not derived')
    if committed:
        need(passed and update.get('numerical_gate',{}).get('admitted') is True, 'optimizer commit bypassed numeric/backward/memory gate')
        need(integer(update.get('backward_calls')) and update['backward_calls']==sum(g['eligible'] for g in derived['groups'] if g['mixed']), 'DDIS backward count differs')
    return committed

def validate_sweeps(root, result, plan, checkpoints, events, *, panel_plan_sha256, synthetic, reward_targets=None,codec=None,require_modern=False):
    entries=result.get('audit_sweeps')
    if type(entries) is list and entries and 'batch' not in entries[0]:
        resolved=[]
        for i,ref in enumerate(entries):
            name='audit/sweep-'+str(i)+'.json'
            need(root.file_sha(name)==ref.get('file_sha256'), 'durable audit reference bytes differ')
            raw=root.json(name)
            need(same(ref.get('summary'),raw.get('summary')) and ref.get('status')==raw.get('status') and ref.get('update_status')==(raw.get('update') or {}).get('status'), 'compact audit projection differs')
            resolved.append(raw)
        entries=resolved
    need(type(entries) is list and 1<=len(entries)<=plan['shape']['max_sweeps']<=4, 'attempted sweep inventory')
    parents=list(dict.fromkeys(r['parent_id'] for r in entries[0]['batch']['rows']))
    need(len(parents)==plan['shape']['parents'], 'fixed reward parent denominator')
    need(type(reward_targets) is dict and list(reward_targets)==parents, 'independently authenticated fixed reward panel required')
    if not synthetic:
        need(parents==result['reward_panel']['parent_ids'], 'frozen reward parent order')
    policy=checkpoints['A']['policy_version']; committed=0;stopped=False;batch_ids=set();all_event_ids=set()
    for index,entry in enumerate(entries):
        need(not stopped, 'collection continued after terminal audit condition')
        need(same(root.json('audit/sweep-'+str(index)+'.json'),entry), 'durable audit differs from aggregate')
        batch=entry['batch']; need(batch.get('sweep')==index and type(batch.get('sweep')) is int, 'fixed sweep ordinal')
        derived=summary(batch,parents,plan['shape']['group_size'])
        need(same(entry.get('summary'),derived), 'audit summary not independently derived')
        need(batch.get('closed') is True and batch.get('all_slots_reached') is derived['all_slots_reached'], 'audit terminal coverage differs')
        if any(r['trajectory'] for r in batch['rows']):
            need(batch.get('policy_version')==policy, 'sweep changed/stale policy')
            need(batch.get('id') not in batch_ids and type(batch.get('id')) is str, 'reused batch identity');batch_ids.add(batch['id'])
        for row in batch['rows']:
            if row.get('trajectory') is None:
                need(not row['eligible'], 'eligible missing trajectory')
                continue
            seed=(7+row['slot']) if synthetic and parents==['fabricated'] else int(digest(['rl-fixed-sampling-v1',panel_plan_sha256,index,row['parent_id'],row['slot']])[:15],16)
            trajectory(row['trajectory'],row,batch,expected_seed=seed,events=events)
            t=row['trajectory'];target=reward_targets[row['parent_id']]
            if codec is not None:need(t.get('prompt_ids')==codec.actor_prompt(target['messages']),'actual sampled actor prompt token sequence differs')
            need(t.get('record_id')==target['record_id'] and t.get('messages_sha256')==target['messages_sha256'], 'actor prompt not exact fixed reward record')
            if row['eligible']:
                try: grid=decode(t['format_text']) if t.get('finish_reason')=='eos' else None
                except ValueError: grid=None
                need(row['reward']==int(grid is not None and grid==target['target']), 'reward not exact authenticated training-target equality')
            ids=row['trajectory']['physical_event_ids']
            need(not all_event_ids.intersection(ids), 'actor physical work reused between slots/sweeps');all_event_ids.update(ids)
        did=validate_update(entry.get('update'),batch,derived,gate=plan['numeric_gate'],synthetic=synthetic,events=events,require_modern=require_modern)
        if did:
            committed+=1;policy=entry['update']['policy_version'];need(entry.get('status')=='updated','committed sweep status differs')
        else:
            stopped=True;need(entry.get('status')!='updated','false updated status')
    bphase=next(p for p in result['phase_intervals'] if p['phase']=='B')
    bcommits=[e for e in events.values() if e['phase']=='optimizer-commit' and e.get('dispatched') and e.get('status')=='complete' and bphase['started']<=e['started']<=e['ended']<=bphase['ended']]
    need(len(bcommits)>=committed,'claimed RL commits absent from complete physical ledger')
    need(committed==checkpoints['B']['counts']['rl_updates'] and policy==checkpoints['B']['policy_version'], 'B actual checkpoint not last committed policy')
    return {'sweeps':len(entries),'committed_updates':committed,'actor_events':len(all_event_ids),'last_summary':derived}
