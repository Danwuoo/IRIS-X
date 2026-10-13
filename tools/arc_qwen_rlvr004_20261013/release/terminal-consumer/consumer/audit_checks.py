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
                       'mixed':0<successes<len(es),'all_zero':len(es)==group_size and successes==0,'all_one':len(es)==group_size and successes==len(es),
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
        if len(support)==1:need(s['log_mu']==0.,'forced token original log probability must be zero')
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


def failed_update_work(update,batch,replays,derived,events):
    """Preserve executed partial work without fabricating a completed numeric gate."""
    need(update.get('status')=='update-failed' and update.get('optimizer_committed') is False,
         'partial replay path cannot claim committed policy')
    need(update.get('update_batch_id')==update.get('batch_id')==batch['id'],'failed logical update batch identity differs')
    rollback=update.get('rollback',{})
    need(rollback.get('restored') is True and rollback.get('logical_counters_restored') is True
         and integer(rollback.get('physical_attempted_batches'),1,4), 'failed update requires actual logical rollback with physical attempts retained')
    candidates=[e for e in events.values() if e.get('update_batch_id')==batch['id']]
    need(update.get('physical_update_event_ids')==[e['event_id'] for e in candidates],
         'failed update erased dispatched/failed physical work')
    commits=[e for e in candidates if e['phase']=='optimizer-commit' and e['dispatched']]
    need(type(update.get('rolled_back_optimizer_commit')) is bool
         and update['rolled_back_optimizer_commit'] is any(e['status']=='complete' for e in commits)
         and update.get('optimizer_dispatched') is bool(commits), 'failed physical optimizer history differs from rollback report')
    started,finished,deadline=(update.get(k) for k in ('batch_started_monotonic','batch_finished_monotonic','batch_deadline'))
    need(all(finite(x) for x in (started,finished,deadline)) and started<=finished,'actual partial update interval required')
    need(all(started<=e['started']<=e['ended']<=finished+.001 and e['deadline']==deadline for e in candidates),
         'failed update physical intervals/deadlines differ')
    eligible=[r for r in batch['rows'] if r['eligible']];used=set();last=0.
    for row,diagnostic in zip(eligible,replays):
        t=row['trajectory'];e=events.get(diagnostic.get('replay_event_id'))
        need(e is not None and e['phase']=='causal-replay' and e['dispatched'] and e['status']=='complete'
             and e.get('trajectory_id')==t['trajectory_id']==diagnostic.get('trajectory_id')
             and e.get('update_batch_id')==batch['id']==diagnostic.get('update_batch_id')
             and e['event_id'] not in used,'actual completed prefix replay receipt required')
        used.add(e['event_id']);need(last<=e['started'] and e['input_tokens']==len(t['original_ids'])-1
                                   and e.get('checkpointing') is True,'partial original-token replay order/input differs')
        need(all(i in events and events[i]['ended']<=e['started'] for i in t['physical_event_ids']),'partial replay precedes original actor work')
        last=e['ended'];backward=None
        if diagnostic.get('backward_event_id') is not None:
            backward=events.get(diagnostic['backward_event_id'])
            need(backward is not None and backward['phase']=='ddis-backward' and backward['dispatched'] and backward['status']=='complete'
                 and backward.get('trajectory_id')==t['trajectory_id'] and backward.get('update_batch_id')==batch['id']
                 and backward['event_id'] not in used and e['ended']<=backward['started'], 'partial completed backward receipt differs')
            used.add(backward['event_id']);last=backward['ended']
            need(abs(diagnostic.get('backward_seconds',-1)-backward['seconds'])<=1e-6,'partial backward duration differs')
        else:
            need(diagnostic.get('backward_seconds') is None,'missing backward cannot invent completed duration')
        need(abs(diagnostic['seconds']-(e['seconds']+(backward['seconds'] if backward else 0)))<=1e-6,
             'partial actual replay/backward duration differs')
    return used


def group_weight_evidence(replay,row,group,mixed_count):
    """Reconstruct emitted detached clipped DDIS scalar using exact raw tokens."""
    mu=replay['log_mu'];pi=replay['log_pi'];length=len(pi)
    need(length>0 and group['eligible']>0,'original generated length/group denominator required')
    advantage=row['reward']-group['successes']/group['eligible']
    weight=1/(mixed_count*group['eligible']*length) if advantage!=0 else 0.
    need(replay.get('group_advantage')==advantage and replay.get('eligible_group_size')==group['eligible']
         and replay.get('mixed_group_count')==mixed_count and replay.get('original_generated_length')==length,
         'actual group-centered advantage/group/token denominator differs')
    need(finite(replay.get('gradient_weight')) and abs(replay['gradient_weight']-weight)<=1e-12,
         'actual equal mixed-group gradient weight differs')
    ratios=[math.exp(max(-20.,min(20.,p-m))) for p,m in zip(pi,mu)]
    loss=-sum(ratio*advantage*p for ratio,p in zip(ratios,pi) if .8<ratio<1.28)*weight
    got=replay.get('detached_DDIS_loss')
    need(finite(got) and abs(got-loss)<=max(1e-6,abs(loss)*1e-5),'actual detached strict-DDIS scalar loss differs')
    return {'advantage':advantage,'gradient_weight':weight,'detached_DDIS_loss':loss}


def validate_update(update, batch, derived, *, gate, synthetic, events, require_modern=False):
    if update is None:
        return False
    need(type(update.get('optimizer_committed')) is bool and type(update.get('optimizer_dispatched')) is bool, 'explicit optimizer state required')
    committed=update['optimizer_committed'];failed=update.get('status')=='update-failed'
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
    if failed:failed_update_work(update,batch,replays,derived,events)
    elif replays or committed:physical_replays(update,batch,replays,derived,events,require_modern=require_modern)
    passed=True
    for r,replay in zip(rs,replays):
        t=r['trajectory']; mu=[s['log_mu'] for s in t['steps']];pi=replay.get('log_pi')
        need(replay.get('parent_id')==r['parent_id'] and same(replay.get('log_mu'),mu), 'replay must use exact original actor probabilities')
        need(type(pi) is list and len(pi)==len(mu) and all(finite(x) and x<=1e-6 for x in pi), 'replay log probability coverage')
        group=next(g for g in derived['groups'] if g['parent_id']==r['parent_id'])
        group_weight_evidence(replay,r,group,derived['mixed_groups'])
        gaps=[p-m for p,m in zip(pi,mu)]; nf=[g for g,s in zip(gaps,t['steps']) if len(s['support'])>1]
        _compare_stats(replay.get('all_tokens'),_stats(gaps));_compare_stats(replay.get('nonforced_tokens'),_stats(nf))
        need(replay.get('forced_tokens')==len(gaps)-len(nf), 'forced token denominator differs')
        need(all(replay.get(k) is True for k in ('original_token_replay','prompt_and_tool_loss_masked','training_mode','checkpointing_active')), 'actual replay/backward recipe differs')
        need(finite(replay.get('seconds')) and replay['seconds']>=0, 'actual replay+backward time required')
        if r['parent_id'] in [g['parent_id'] for g in derived['groups'] if g['mixed']] and not (failed and replay.get('backward_event_id') is None):
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
            if not failed or update.get('whole_replay_backward_seconds') is not None:
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

def validate_sweeps(root, result, plan, checkpoints, events, *, panel_plan_sha256, synthetic, reward_targets=None,codec=None,require_modern=False,checkpoint_mode="runtime-reload-bound"):
    """Validate exactly one fixed disjoint parent batch per possible update."""
    from .checkpoint_metadata import validate_checkpoint_metadata
    refs=result.get('audit_sweeps');need(type(refs) is list and same(refs,result.get('audit_batches')),'complete batch index aliases differ')
    shape=plan['shape'];partition=shape['batch_parents'] or shape['parents']
    parents=list(reward_targets) if type(reward_targets) is dict else []
    need(len(parents)==shape['parents'] and len(set(parents))==len(parents),'authenticated fixed session parent denominator')
    expected_parents=[parents[i:i+partition] for i in range(0,len(parents),partition)]
    need(len(refs)==len(expected_parents)==shape['max_sweeps'],'all planned batches including not-reached required')
    if not synthetic:need(parents==result.get('reward_panel',{}).get('parent_ids'),'fixed original reward parent order differs')
    policy_hash=plan.get('measured_policy_sha256');entries=[];all_events=set();batch_ids=set();committed=0;entered=0
    previous=None;stopped=False;actor_start=[];batch_end=[];durabilities=[];history=[];trajectory_ids=set()
    core=root.json('A-checkpoint-proof.json')['policy_identity']['source_sha256']
    for index,(ref,batch_parents) in enumerate(zip(refs,expected_parents)):
        name=f'audit/sweep-{index}.json';need(root.file_sha(name)==ref.get('file_sha256'),'durable batch reference bytes differ')
        entry=root.json(name);batch=entry.get('batch');entries.append(entry)
        need(ref.get('batch_index')==entry.get('batch_index')==index and type(entry.get('batch_index')) is int
             and ref.get('parent_ids')==entry.get('parent_ids')==batch_parents,'fixed disjoint batch partition/order differs')
        need(same(ref.get('summary'),entry.get('summary')) and ref.get('status')==entry.get('status')
             and ref.get('update_status')==(entry.get('update') or {}).get('status'),'compact batch index projection differs')
        need(batch.get('sweep')==batch.get('batch_index')==index and batch.get('parent_ids')==batch_parents,'batch ordinal/parents differ')
        derived=summary(batch,batch_parents,shape['group_size'])
        need(same(derived,entry.get('summary')) and batch.get('closed') is True
             and batch.get('all_slots_reached') is derived['all_slots_reached'],'batch summary/coverage not independently derived')
        if entry['status']=='not-reached':
            need(entry.get('update') is None and entry.get('policy_before') is None and entry.get('policy_after') is None
                 and entry.get('admission') is None and ref.get('durability_ref') is None
                 and batch.get('policy_version') is None and derived['not_reached']==derived['planned_attempts'],
                 'not-entered fixed batch cannot invent work/reward/policy')
            stopped=True;continue
        need(not stopped,'later batch entered after stopped/incomplete prefix')
        entered+=1;need(entered==index+1,'physical fixed batch prefix differs')
        need(batch.get('group_size')==shape['group_size'] and batch.get('planned_parents')==shape['parents']
             and batch.get('session_planned_attempts')==shape['parents']*shape['group_size']
             and batch.get('sampling_policy_sha256')==policy_hash and batch.get('attempted_batches')==entered,
             'batch64/session256/policy/physical attempt identities differ')
        before=entry.get('policy_before');after=entry.get('policy_after')
        need(type(before) is dict and type(after) is dict and before.get('policy_version')==batch.get('policy_version')
             and before.get('generation_epoch')==batch.get('generation_epoch') and before.get('source_sha256')==after.get('source_sha256')==core,
             'fixed original batch policy identity differs')
        need(type(before['policy_version']) is str and before['policy_version'].startswith('rl:'),'fresh RL branch-owned policy identity required')
        expected_adapter=checkpoints['A']['adapter_sha256'] if previous is None else previous['adapter_sha256']
        need(before.get('adapter_sha256')==expected_adapter,'batch must start from last durable committed adapter')
        if previous is not None:need(before['policy_version']==previous['policy_version'],'batch restarted or reused stale policy')
        need(type(batch.get('id')) is str and batch['id'] not in batch_ids,'unique actual fixed batch identity');batch_ids.add(batch['id'])
        ids=[];actor_identity=None
        for row in batch['rows']:
            t=row.get('trajectory')
            if t is None:
                need(not row['eligible'],'eligible row lacks actual original trajectory');continue
            seed=7+row['slot'] if synthetic and parents==['fabricated'] else int(digest([
                'rl-fixed-batch-sampling-v1',policy_hash,panel_plan_sha256,index,row['parent_id'],row['slot']])[:15],16)
            trajectory(t,row,batch,expected_seed=seed,events=events)
            need(type(t.get('trajectory_id')) is str and t['trajectory_id'] not in trajectory_ids,'unique original trajectory identity required')
            trajectory_ids.add(t['trajectory_id'])
            if actor_identity is None:actor_identity=t['identity']
            need(t['identity']==actor_identity,'actual actor identity changed within fixed-policy batch')
            target=reward_targets[row['parent_id']]
            if codec is not None:need(t.get('prompt_ids')==codec.actor_prompt(target['messages']),'actual fixed reward prompt tokens differ')
            need(t.get('record_id')==target['record_id'] and t.get('messages_sha256')==target['messages_sha256'],'actor prompt not fixed train-only reward record')
            if row['eligible']:
                try:grid=decode(t['format_text']) if t.get('finish_reason')=='eos' else None
                except ValueError:grid=None
                need(row['reward']==int(grid is not None and grid==target['target']),'training reward not exact authenticated target equality')
            t_ids=t['physical_event_ids'];need(not all_events.intersection(t_ids),'physical actor work reused across slots/batches')
            all_events.update(t_ids);ids+=t_ids
        update=entry.get('update')
        did=validate_update(update,batch,derived,gate=plan['numeric_gate'],synthetic=synthetic,events=events,require_modern=require_modern)
        if update is not None:
            need(update.get('batch_index')==index and update.get('parent_ids')==batch_parents
                 and update.get('session_planned_attempts')==shape['parents']*shape['group_size'],'update batch/session denominator changed')
        if did:
            committed+=1;need(entry['status']=='updated' and after['policy_version']==update['policy_version']
                              and after['policy_version']!=before['policy_version'] and after['adapter_sha256']!=before['adapter_sha256'],
                              'committed batch must change actual adapter and policy exactly once')
        else:
            need(entry['status']!='updated' and after['adapter_sha256']==before['adapter_sha256']
                 and after['policy_version']==before['policy_version'],'noncommitted batch changed durable policy')
            if entry['status']=='zero-signal':need(derived['complete'] and derived['mixed_groups']==0,'partial/failed batch relabeled clean zero/constant signal')
            else:stopped=True
        previous={'policy_version':after['policy_version'],'adapter_sha256':after['adapter_sha256']}
        durability_name=f'audit/batch-{index}-durability.json';durability_ref=ref.get('durability_ref')
        need(type(durability_ref) is dict and root.file_sha(durability_name)==durability_ref.get('file_sha256'),
             'entered batch requires separately durable checkpoint/reload receipt')
        durable=root.json(durability_name);label=f'B-batch-{index}';proof=root.json(label+'-checkpoint-proof.json')
        need(durable.get('batch_index')==index and same(durable.get('checkpoint'),proof)
             and durable.get('audit_ref',{}).get('file_sha256')==root.file_sha(name), 'durable batch checkpoint/audit binding differs')
        from .tensor_checks import validate_checkpoint
        verify_checkpoint=validate_checkpoint if checkpoint_mode=='full-materialized' else validate_checkpoint_metadata
        cp=verify_checkpoint(root,label,anchor_updates=shape['anchor_updates'],expected_core_source_sha256=core,synthetic=synthetic)
        need(cp['adapter_sha256']==after['adapter_sha256'] and cp['policy_version']==after['policy_version']
             and cp['counts']['rl_updates']==committed and cp['base_identity_sha256']==checkpoints['A']['base_identity_sha256']
             and cp['sft_exposed']==checkpoints['A']['sft_exposed'],'durable batch state/base/sampler differs')
        reload=proof['reload'];history=reload.get('batch_history')
        need(reload.get('physical_attempted_batches')==entered and type(history) is list and len(history)==entered,
             'reload erased monotonic physical attempted batches/history')
        h=history[-1]
        need(h.get('batch_id')==batch['id'] and h.get('batch_index')==index and h.get('parent_ids')==batch_parents
             and h.get('before_policy_version')==before['policy_version'] and h.get('after_policy_version')==after['policy_version']
             and h.get('rl_updates')==committed and h.get('physical_attempted_batches')==entered,
             'actual acknowledged batch history differs')
        if update is not None:need(same(update.get('batch_acknowledgment'),h),'update/physical acknowledgment differs')
        for old,d in zip(history[:-1],durabilities):need(same(old,d),'reload rewrote earlier physical batch history')
        durabilities.append(h)
        actor_start.append(min((events[i]['started'] for i in ids),default=float('inf')))
        related=[e for e in events.values() if e.get('update_batch_id')==batch['id'] or e['event_id'] in ids]
        batch_end.append(max((e['ended'] for e in related),default=0.))
    if previous is None:
        need(checkpoints['B']['counts']['rl_updates']==0 and checkpoints['B']['adapter_sha256']==checkpoints['A']['adapter_sha256'],'no-entered B must retain A adapter')
    else:
        need(checkpoints['B']['adapter_sha256']==previous['adapter_sha256'] and checkpoints['B']['policy_version']==previous['policy_version'],
             'arm B is not the last durable batch checkpoint')
    need(checkpoints['B']['counts']['rl_updates']==committed,'B final committed update count differs')
    actual_labels={p.name for p in (root.path/'checkpoints').iterdir() if p.is_dir()}
    required_labels={'base','A','C'}|({f'B-batch-{i}' for i in range(entered)} if entered else {'B'})
    need(actual_labels==required_labels and len(actual_labels)<=7,'unplanned or missing raw checkpoint stores')
    closure=result['model_closure'];need(closure.get('physical_attempted_batches')==entered and same(closure.get('batch_history'),history),
                                       'closure lost physical batch attempts/history')
    bphase=next(p for p in result['phase_intervals'] if p['phase']=='B')
    within=[e for e in events.values() if bphase['started']<=e['started']<=e['ended']<=bphase['ended']]
    saves=[e for e in within if e['phase']=='checkpoint-save' and e['dispatched'] and e['status']=='complete']
    reloads=[e for e in within if e['phase']=='checkpoint-reload' and e['dispatched'] and e['status']=='complete']
    need(len(saves)==max(1,entered) and len(reloads)==max(1,entered)+1,'every entered batch must be saved/reloaded exactly once within B')
    for i in range(entered):
        need(batch_end[i]<=saves[i]['started']<=saves[i]['ended']<=reloads[i+1]['started']<=reloads[i+1]['ended'],
             'batch update/rollback precedes actual durable save/reload')
        if i+1<entered:need(reloads[i+1]['ended']<=actor_start[i+1],'next policy batch sampled before previous durability')
    merged={'rows':[r for e in entries for r in e['batch']['rows']],
            'planned_attempts':len(parents)*shape['group_size'],
            'fatal_native_state':any(bool(e['batch'].get('fatal_native_state')) for e in entries)}
    total=summary(merged,parents,shape['group_size'])
    if shape['batch_parents']:
        full={'format':'fixed-disjoint-panel-audit-v1','parent_ids':parents,'planned_parents':len(parents),
            'planned_attempts':len(parents)*shape['group_size'],'group_size':shape['group_size'],'planned_batches':len(entries),
            'batch_parent_ids':[e['parent_ids'] for e in entries],'batch_statuses':[e['status'] for e in entries],
            'physical_attempted_batches':entered,'optimizer_updates':committed,'all32_coverage_complete':len(parents)==32 and total['complete'],
            'all_zero_panel':total['complete'] and total['reward_eligible_attempts']==len(parents)*shape['group_size'] and total['eligible_mean_reward']==0.,
            'partial_is_not_zero_signal':True,'summary':total}
        need(same(full,result.get('full_panel_audit')) and same(full,root.json('full-panel-audit.json')),
             'full32/256 panel denominator and partial-zero distinction differ')
    return {'planned_batches':len(entries),'physical_attempted_batches':entered,'planned_parents':len(parents),
            'planned_attempts':len(parents)*shape['group_size'],'committed_updates':committed,'actor_events':len(all_events),
            'full_panel_summary':total,'all_zero_panel':total['complete'] and total['eligible_mean_reward']==0.}
