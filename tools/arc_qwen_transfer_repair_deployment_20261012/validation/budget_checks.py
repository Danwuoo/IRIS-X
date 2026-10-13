"""Independent stdlib replay of transfer-only call budgets and timing refresh.

No runtime import, execution, target escrow parsing, network, or model access.
"""
import hashlib
import json
import math
import re

POLICY={'format':'irisx/transfer-generation-call-policy-v1',
        'generation_hard_seconds':180.0,'generation_normal_soft_seconds':175.0,
        'non_generation_hard_seconds':120.0,'non_generation_normal_soft_seconds':115.0,
        'cleanup_seconds':5.0,'short_remaining_cleanup_fraction':0.1,
        'deadline_policy':'min-owner-branch-deadline-and-call-hard-cap'}
PACKAGE='tools/arc_qwen_transfer_20261012/'


def require(ok,message):
    if not ok:raise ValueError(message)


def canonical(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def number(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
def integer(value):return type(value) is int and value>=0

def validate_source_policy(source,*,synthetic=False):
    require(PACKAGE+'call_policy.py' in source.mapping,'generation-budget successor source required; historical source is not relabeled')
    for key,expected in (('GENERATION_HARD_SECONDS',180.0),('GENERATION_SOFT_SECONDS',175.0),('OTHER_HARD_SECONDS',120.0),('OTHER_SOFT_SECONDS',115.0)):
        value=source.assignment(PACKAGE+'call_policy.py',key)
        require(type(value) is float and value==expected,'source call-budget constant differs: '+key)
    cap=source.assignment(PACKAGE+'runner.py','MAX_TOTAL_BYTES')
    require(type(cap) is int and cap in ((256*1024**2,512*1024**2) if synthetic else (512*1024**2,)),'source evidence aggregate capacity differs')
    return cap


def validate_window(window,owner_deadline=None):
    keys={'call_kind','call_policy_sha256','started_monotonic','branch_deadline_monotonic','work_deadline_monotonic','deadline_monotonic'}
    require(type(window) is dict and keys<=set(window),'generation call window missing')
    require(window['call_kind']=='generation' and window['call_policy_sha256']==digest(POLICY),'generation call policy identity differs')
    start,branch,soft,hard=(window[k] for k in ('started_monotonic','branch_deadline_monotonic','work_deadline_monotonic','deadline_monotonic'))
    require(all(number(x) for x in (start,branch,soft,hard)) and branch>start,'invalid generation call clocks')
    require(hard==min(branch,start+180.0) and soft==hard-min(5.0,(hard-start)*0.1),'generation hard/soft window arithmetic differs')
    if owner_deadline is not None:require(number(owner_deadline) and branch<=owner_deadline,'generation branch exceeds owner work deadline')
    return start,soft,hard


def validate_admission_window(value,gen,score,generations,scores):
    require(value.get('generation_call_policy')==POLICY,'forecast generation policy differs')
    now=value.get('decision_monotonic');branch=value.get('branch_deadline_monotonic')
    require(number(now) and number(branch),'forecast decision and branch clocks required')
    remaining=max(0,branch-now)
    require(value['remaining_seconds']==remaining,'forecast remaining window differs')
    hard=min(branch,now+180.0)
    generation_work=max(0,hard-min(5.0,(hard-now)*0.1)-now) if remaining else 0
    score_hard=min(120.0,remaining);score_work=score_hard-min(5.0,score_hard*.1)
    require(value.get('generation_work_seconds_available')==generation_work and value.get('score_work_seconds_available')==score_work,'forecast available call work differs')
    gf=not generations or 1.5*gen<=generation_work;sf=not scores or 1.5*score<=score_work
    require(value.get('generation_per_call_admitted') is gf and value.get('score_per_call_admitted') is sf,'forecast separate generation/scoring admission differs')
    require(value.get('actual_timeout_observed') is False,'forecast rejection is not an observed timeout')
    return gf and sf


def validate_generation_receipt(receipt,ledger,owner_deadline):
    event=receipt.get('physical_event_id')
    require(type(event) is str and re.fullmatch(r'qwen14b-generation-[1-9][0-9]*',event) is not None and event in ledger['events'],'generation event identity differs')
    require(receipt.get('generation_call_policy')==POLICY,'native generation policy differs')
    start,soft,hard=validate_window(receipt.get('call_window'),owner_deadline)
    timing=receipt.get('wrapper_timing');native=receipt.get('native_timing')
    require(type(timing) is dict and timing.get('clock')=='time.monotonic','generation wrapper timing required')
    clocks=[timing.get(k) for k in ('started_monotonic','native_entered_monotonic','native_returned_monotonic','completed_monotonic')]
    require(all(number(x) for x in clocks) and clocks==sorted(clocks) and clocks[0]==start,'generation wrapper clock order differs')
    require(timing.get('ledger_head_sha256')==ledger['events'][event]['sha256'],'generation wrapper ledger event differs')
    require(type(native) is dict and native.get('clock')=='time.monotonic' and native.get('forward_completion_synchronized') is True and native.get('forward_trace_source')=='tools/arc_qwen_probe_20261012/decoder.py','native timing source/synchronization differs')
    entered,returned=native.get('entered_monotonic'),native.get('returned_monotonic')
    require(number(entered) and number(returned) and clocks[1]<=entered<=returned<=clocks[2],'native generation timing order differs')
    if receipt.get('valid') is True:
        require(clocks[2]<soft and clocks[3]<hard,'valid generation exceeds work/hard deadline')
    if clocks[2]>=soft or clocks[3]>=hard:
        require(receipt.get('valid') is False and receipt.get('fatal_error') is True and receipt.get('finish_reason')=='deadline','late generation lacks fatal deadline disposition')
    return {'event_id':event,'started_monotonic':start,'completed_monotonic':clocks[3]}


def validate_calls(archive,request,ledger):
    seen={};non_generation=[];legacy={}
    def visit(value):
        if type(value) is list:
            for item in value:visit(item)
        elif type(value) is dict:
            event=value.get('physical_event_id')
            if type(event) is str and event.startswith('qwen14b-generation-') and 'forward_input_tokens' in value:
                if event in seen:require(seen[event]==value,'generation receipt duplicate differs')
                else:validate_generation_receipt(value,ledger,request['work_deadline']);seen[event]=value
            if {'started_monotonic','completed_monotonic','deadline_monotonic'}<=set(value) and value.get('call_kind')!='generation':
                # Cache/scoring/update receipt clocks retain their unchanged cap.
                if 'work_deadline_monotonic' in value:
                    require(value['deadline_monotonic']<=value['started_monotonic']+120,'non-generation native call exceeds120-second cap')
                    non_generation.append(value)
            legacy_event=value.get('event_id',value.get('physical_event_id'))
            if type(legacy_event) is str and not legacy_event.startswith('qwen14b-generation-') and legacy_event in ledger['events'] and {'started_monotonic','deadline_monotonic'}<=set(value):legacy[legacy_event]=value
            for item in value.values():visit(item)
    for name in archive.members:
        if name.endswith('.json') and not name.endswith('.timing.json') and 'target-escrow' not in name and '/upstream/data/evaluation/' not in name:visit(archive.json(name))
    actual={eid for eid,event in ledger['events'].items() if eid.startswith('qwen14b-generation-') and event['event']!='unknown'}
    require(actual==set(seen),'returned generation policy/clock receipt coverage differs')
    marker=None
    if 'active-call.json' in archive.members:
        marker=archive.json('active-call.json')
        require(marker.get('status')=='closed' and marker.get('event_id') in ledger['events'],'terminal active-call marker is not closed/event-bound')
        event=marker['event_id'];hard=marker.get('deadline_monotonic');soft=marker.get('work_deadline_monotonic')
        require(number(hard) and number(soft) and hard<=request['work_deadline'] and soft<=request['work_deadline'],'active-call clock exceeds owner work deadline')
        if event.startswith('qwen14b-generation-') or marker.get('call_kind')=='generation':
            validate_window(marker,request['work_deadline'])
            require(ledger['events'][event]['event']=='unknown' or event in seen and all(marker.get(k)==value for k,value in seen[event]['call_window'].items()),'closed generation marker differs from actual receipt')
        else:
            require(marker.get('call_kind') is None and not any(k in marker for k in ('call_policy_sha256','started_monotonic','branch_deadline_monotonic')),'non-generation marker acquired generation policy')
            scoring=re.fullmatch(r'qwen14b-c4096-likelihood-[1-9][0-9]*',event) is not None
            calibration=re.fullmatch(r'ladder-(128|512|2048|4096)(-(base|updated|restored)-[a-z0-9-]+)?',event) is not None
            require(scoring or calibration,'unknown legacy native call marker identity')
            require(soft<=hard if scoring else hard<=soft,'legacy native marker deadline order differs')
            if scoring:require(0<hard-soft<=5.0,'likelihood cleanup window differs')
            if event in legacy:
                value=legacy[event]
                require(hard==min(soft,value['started_monotonic']+120),'legacy marker differs from actual native start/branch')
                require(value['deadline_monotonic'] in (hard,soft),'legacy receipt/marker deadlines differ')
    elif actual:require(False,'generation work omitted active-call marker')
    return {'generation_receipts':len(seen),'generation_policy_sha256':digest(POLICY),
            'non_generation_clock_receipts':len(non_generation),'terminal_active_call_checked':marker is not None,'legacy_marker_qualification':'Legacy likelihood receipts have no independently recorded wrapper start; exact source, event namespace, owner bound and cleanup order are checked. Calibration/cache start clocks are checked when present.'}

TIMING_SOURCES=tuple('tools/'+n for n in (
    'arc_qwen_transfer_20261012/backend.py','arc_qwen_transfer_20261012/decoder.py',
    'arc_qwen_transfer_20261012/experiment.py','arc_qwen_transfer_20261012/call_policy.py',
    'arc_qwen_transfer_20261012/science_profiles.py','arc_qwen_transfer_20261012/timing_refresh.py',
    'arc_qwen_transfer_20261012/protocol.py','arc_qwen_probe_20261012/decoder.py',
    'arc_learning_agent_20261011/native_model.py','arc_learning_agent_20261011/qwen14b_model.py',
    'arc_learning_agent_20261011/budget.py','arc_learning_agent_20261011/metering.py'))
TRACE_FIELDS=('input_tokens','attention_mask_tokens','position_start','position_end','cache_before',
              'cache_after','use_cache','started_monotonic','completed_monotonic','deadline_monotonic')
LIMITATIONS=['Finite empirical forecast, not a worst-case mathematical guarantee.',
    'Calibration covers native cache contexts through4096; main prompt/output ranges are recorded above.',
    'Unobserved longer production output tails can have different sampling/constraint/host overhead.',
    'No output-tail speed, EOS savings, validity savings or correctness savings is assumed.',
    'Per-call evidence/row writes are measured through separate timing-only boundaries; panel-level freeze IO is consumed before admission.']


def public_estimate(stats):
    fixed=stats.get('generation_fixed_seconds',0)
    for key in ('training_seconds_per_step','prefill_seconds_per_input','decode_seconds_per_call','full_seconds_per_input','backend_load_seconds'):
        require(number(stats.get(key)),'finite measured PUBLIC estimate required')
    require(number(fixed),'finite fixed PUBLIC overhead required')
    generation=fixed+3072*stats['prefill_seconds_per_input']+1023*stats['decode_seconds_per_call']
    score=max(4096*stats['full_seconds_per_input'],stats['training_seconds_per_step'])
    return {'updates':0,'generations':334,'scores':0,'fresh_reloads':2,
        'forecast_seconds':1.5*(334*generation+2*max(150,stats['backend_load_seconds'])),
        'input_tokens':334*4095,'generation_seconds':generation,'generation_fixed_seconds':fixed,
        'score_seconds':score,'safety_multiplier':1.5,'output_cap_reserved':1024,
        'forecast_is_guarantee':False,'target_outcomes_used':False}


def ordered(values,now,name):
    require(bool(values) and all(number(x) and x<=now for x in values) and values==sorted(values),'invalid/late/ unordered '+name+' timing')


def derive_timing_measurements(rows,calibration,original,now):
    """Independent arithmetic, consuming every row without outcome predicates."""
    fixed=[];prefill=[];intervals=[];gaps=[];prompts=[];contexts=[];outputs=[];modes=set();methods={};expected_methods=set();invoked=0;previous=None
    for row in rows:
        r=row['timing'];e=r['evidence_timing'];end=row['accounted_through_monotonic'];method=row['method'];expected_methods.add(method)
        ordered([e['started_monotonic'],e['receipt_persisted_monotonic'],end],now,'evidence')
        require(e['clock']=='time.monotonic','timing evidence clock differs')
        if previous is not None:require(e['started_monotonic']>=previous,'overlapping main timing calls')
        previous=end
        if r['native_invoked'] is False:
            require(r['physical_event_id'] is None and r['forward_trace']==[] and r['forward_calls']==0,'uninvoked main slot has physical work')
            fixed.append(end-e['started_monotonic']);continue
        require(r['native_invoked'] is True,'main invocation type differs');invoked+=1
        w=r['wrapper_timing'];n=r['native_timing'];window=r['call_window'];validate_window(window)
        require(r['generation_call_policy']==POLICY and w['clock']==n['clock']=='time.monotonic' and n['forward_completion_synchronized'] is True and n['forward_trace_source']=='tools/arc_qwen_probe_20261012/decoder.py','unsupported native timing policy/source')
        ordered([e['started_monotonic'],w['started_monotonic'],w['native_entered_monotonic'],n['entered_monotonic'],n['returned_monotonic'],w['native_returned_monotonic'],w['completed_monotonic'],e['receipt_persisted_monotonic']],now,'native-wrapper')
        require(w['started_monotonic']==window['started_monotonic'] and r['adapter_execution_mode']==row['mode'] and r['decoder_mode']=='cached','timing state/decoder differs')
        require(n['returned_monotonic']<=w['native_returned_monotonic']<window['work_deadline_monotonic'] and w['completed_monotonic']<window['deadline_monotonic'] and end<=window['branch_deadline_monotonic'],'late main generation cannot refresh cost')
        trace=r['forward_trace']
        require(type(trace) is list and integer(r['forward_calls']) and len(trace)==r['forward_calls'] and integer(r['output_tokens']) and r['output_tokens']<=len(trace)<=1024 and integer(r['forward_input_tokens']),'main trace/count bounds differ')
        require(sum(t['input_tokens'] for t in trace)==r['forward_input_tokens'],'main trace token totals differ')
        if not trace:fixed.append(end-e['started_monotonic']);continue
        modes.add(r['adapter_execution_mode'])
        if len(trace)>1:methods[method]=methods.get(method,0)+len(trace)-1
        prompt=r['input_tokens'];require(integer(prompt) and 1<=prompt<=3072,'main prompt cap differs')
        last=n['entered_monotonic']
        for i,t in enumerate(trace):
            require(set(t)==set(TRACE_FIELDS) and all(integer(t[k]) for k in ('input_tokens','attention_mask_tokens','position_start','position_end','cache_before','cache_after')),'main timing trace unknown/noninteger field')
            ordered([last,t['started_monotonic'],t['completed_monotonic'],n['returned_monotonic']],now,'native-forward')
            require(t['deadline_monotonic']==window['work_deadline_monotonic'] and t['use_cache'] is True and t['input_tokens']==(prompt if i==0 else 1) and t['cache_before']==(0 if i==0 else prompt+i-1) and t['cache_after']==t['attention_mask_tokens']==prompt+i and t['position_start']==(0 if i==0 else prompt+i-1) and t['position_end']==prompt+i-1,'cached context/position coverage differs')
            if i:intervals.append(t['completed_monotonic']-last);gaps.append(t['started_monotonic']-last)
            last=t['completed_monotonic'];contexts.append(t['attention_mask_tokens'])
        prefill.append((trace[0]['completed_monotonic']-trace[0]['started_monotonic'])/prompt)
        fixed.append(trace[0]['started_monotonic']-e['started_monotonic']+end-trace[-1]['completed_monotonic'])
        prompts.append(prompt);outputs.append(r['output_tokens'])
    require(modes=={'base','trained'} and intervals and prefill and fixed and set(methods)==expected_methods,'main base/trained/per-method cached timing coverage incomplete')
    require(calibration.get('completed_lengths')==[128,512,2048,4096] and calibration.get('full_context_measured') is True and calibration.get('behavioral_cache_admitted') is True and calibration.get('full_state_restoration_verified') is True,'complete production calibration context coverage required')
    obs=calibration['observations'];require([r['length'] for r in obs]==[128,512,2048,4096],'calibration observations differ')
    native=[];ids=[];histories=[]
    for rung in obs:
        require(set(rung['states'])=={'base','updated','restored'},'calibration state coverage differs')
        for state in ('base','updated','restored'):
            found=[]
            for f in rung['states'][state]['cache']['forwards']:
                if f['use_cache'] and f['past_supplied']:
                    ordered([f['started_monotonic'],f.get('native_started_monotonic'),f['completed_monotonic']],now,'calibration-native')
                    require(type(f['input_tokens']) is int and f['input_tokens']==1 and integer(f['history_tokens']) and f['history_tokens']<=rung['length'],'calibration native context differs')
                    native.append(f['completed_monotonic']-f['native_started_monotonic']);ids.append(f['event_id']);histories.append(f['history_tokens']);found.append(f)
            require(found and max(f['history_tokens'] for f in found)==rung['length'],'calibration rung context absent')
    require(native,'calibration native decode samples absent')
    selected=dict(original);selected.update(generation_fixed_seconds=max(fixed),prefill_seconds_per_input=max(original['prefill_seconds_per_input'],max(prefill)),decode_seconds_per_call=max(max(intervals),max(native)+max(gaps)))
    coverage={'main_slots':len(rows),'native_invoked_calls':invoked,'adapter_modes':sorted(modes),'method_adjacent_samples':methods,'adjacent_completion_samples':len(intervals),
        'prompt_tokens_min':min(prompts),'prompt_tokens_max':max(prompts),'cached_context_min':min(contexts),'cached_context_max':max(contexts),
        'output_tokens_min':min(outputs),'output_tokens_max':max(outputs),'calibration':{'sample_count':len(native),'event_ids':ids,'context_min':min(histories),'context_max':max(histories),'clock':'time.monotonic','synchronized_completion':True},
        'maximum_adjacent_completion_seconds':max(intervals),'maximum_main_interstep_gap_seconds':max(gaps),'maximum_calibration_native_decode_seconds':max(native),
        'fixed_per_call_seconds':max(fixed),'extrapolation':'full3072-prefill-and1023-cached-steps; max-calibrated-native-plus-max-main-gap floor',
        'limitations':LIMITATIONS,'target_outcomes_used':False,'outcome_filtering':False}
    return selected,coverage


def validate_public_refresh(archive,request,ledger,original):
    name='experiment/public-cost-refresh.json';refresh=archive.json(name);calibration=archive.json('calibration/calibration.json')
    sources={n:request['source_identity'][n] for n in TIMING_SOURCES}
    require(refresh.get('format')=='irisx/transfer-public-cost-refresh-v1' and refresh.get('source_sha256')==sources and refresh.get('source_identity_sha256')==digest(sources),'PUBLIC refresh source identity differs')
    require(refresh.get('calibration_sha256')==digest(calibration) and refresh.get('original_measurements')==original and refresh.get('original_estimate')==public_estimate(original),'PUBLIC refresh calibration baseline differs')
    require(refresh.get('target_outcomes_used') is False and refresh.get('outcome_filtering') is False and refresh.get('forecast_is_guarantee') is False and refresh.get('cpu_fixture_only') is request['config'].get('tiny_cpu',False),'PUBLIC refresh scientific/origin claim differs')
    now=refresh['frozen_monotonic'];start=refresh['main_started_monotonic'];ordered([start,now],now,'main freeze')
    require(now<=request['work_deadline'],'PUBLIC refresh frozen after work cutoff')
    if 'experiment/holdout-prediction-seal.json' in archive.members:
        require(archive.json('experiment/holdout-prediction-seal.json')['sealed_monotonic']<=now,'PUBLIC timing frozen before main seal')
    baseline=public_estimate(original);status=refresh['status']
    require(status in ('MAIN_TIMING_REFRESHED','CALIBRATION_FALLBACK'),'unknown PUBLIC refresh disposition')
    require(refresh.get('receipt_bindings_sha256')==digest(refresh['receipt_bindings']),'PUBLIC timing receipt binding digest differs')
    if status=='CALIBRATION_FALLBACK':
        require(refresh['refreshed_measurements'] is None and refresh['refreshed_estimate'] is None and refresh['coverage'] is None and refresh['selected_measurements']==original and refresh['selected_estimate']==baseline and type(refresh['reason']) is str and refresh['reason'].startswith('unsupported-timing-coverage: '),'unsupported timing failed to preserve full calibration fallback')
    raw=archive.read('physical-work.jsonl');lines=raw.splitlines(keepends=True);events=[json.loads(x) for x in lines]
    snapshot=refresh['ledger'];main_start=refresh['main_event_start'];require(integer(main_start) and main_start>=1,'main event interval invalid')
    if snapshot is not None:
        count=snapshot['event_count'];require(integer(count) and main_start<=count<=len(events),'PUBLIC refresh ledger prefix count differs')
        head=events[count-1]['sha256'];prefix=ledger['prefixes'].get(head)
        require(snapshot['path']==request['output_root']+'/physical-work.jsonl' and snapshot['head_sha256']==head and snapshot['sha256']==hashlib.sha256(b''.join(lines[:count])).hexdigest() and prefix is not None and prefix['pending'] is False and snapshot['physical_usage']==prefix['used'],'PUBLIC refresh exact closed ledger prefix differs')
    else:require(status=='CALIBRATION_FALLBACK','refreshed PUBLIC missing ledger snapshot')
    if status=='MAIN_TIMING_REFRESHED':require(refresh['reason']=='complete-source-event-clock-context-coverage','PUBLIC refreshed reason differs')
    complete_bindings=refresh['boundaries'] is not None and len(refresh['receipt_bindings'])==224
    require(complete_bindings or status=='CALIBRATION_FALLBACK','PUBLIC refresh all224 bindings required')
    if complete_bindings:
        boundary=archive.json('experiment/main-timing-boundaries.json');remote=request['output_root']+'/experiment'
        require(refresh['boundaries']=={'path':remote+'/main-timing-boundaries.json','sha256':hashlib.sha256(archive.read('experiment/main-timing-boundaries.json')).hexdigest()},'main timing boundary hash differs')
        require(boundary['format']=='irisx/transfer-main-timing-boundaries-v1' and boundary['source_sha256']==sources and boundary['main_event_start']==main_start and boundary['main_started_monotonic']==start,'main timing boundary identity differs')
        bounds={r['receipt_path']:r for r in boundary['calls']};require(len(bounds)==len(boundary['calls'])==224,'all224 main timing boundaries required')
        interval=events[main_start:count];reserved={r['event_id']:r for r in interval if r['event']=='reserved' and 'generation_calls' in r['amounts']};closed={r['event_id']:r for r in interval if r['event'] in ('complete','failed','excluded') and 'generation_calls' in r['amounts']}
        require(set(reserved)==set(closed),'main timing ledger events incompletely closed')
        updates=request['config'].get('test_checkpoint_updates',[1,2]) if request['config'].get('tiny_cpu') else [64,256]
        groups=[('dev','base',16,'base')]+[('dev','sft'+str(u),16,'trained') for u in updates]+[('holdout','base',32,'base'),('holdout','selected-sft',32,'trained')]
        rows=[];bindings=[];seen=set()
        for scope,method,n,mode in groups:
            for i in range(n):
                for op in (0,1):
                    path='%s/%s/%03d-%d.json'%(scope,method,i,op);member='experiment/'+path;side=member[:-5]+'.timing.json';r=archive.json(side);receipt=archive.json(member)
                    require(r['format']=='irisx/transfer-native-generation-timing-v1' and r['source_sha256']==sources and r['receipt_sha256']==hashlib.sha256(archive.read(member)).hexdigest(),'main timing source/native receipt binding differs')
                    require(type(r['native_invoked']) is bool,'timing native invocation type differs')
                    projection={k:receipt.get(k) for k in ('physical_event_id','adapter_execution_mode','decoder_mode','generation_call_policy','call_window','wrapper_timing','native_timing')}
                    projection.update({k:receipt.get(k,0) for k in ('forward_calls','forward_input_tokens','input_tokens','output_tokens')})
                    projection['forward_trace']=[{k:t.get(k) for k in TRACE_FIELDS} for t in receipt.get('forward_trace',[])]
                    require(all(r.get(k)==value for k,value in projection.items()),'timing-only projection differs from native receipt')
                    allowed={'format','source_sha256','receipt_sha256','native_invoked','evidence_timing'}|set(projection)
                    require(set(r)==allowed,'timing sidecar contains unknown/outcome field')
                    event=r['physical_event_id']
                    if r['native_invoked']:
                        require(event in closed and event not in seen,'main timing event absent/duplicated');seen.add(event)
                        require(closed[event]['amounts']=={'generation_calls':int(r['forward_calls']>0),'input_tokens':r['forward_input_tokens'],'output_tokens':r['output_tokens']} and r['wrapper_timing']['ledger_head_sha256']==closed[event]['sha256'],'main timing event cost/head differs')
                    else:require(event is None,'uninvoked main call owns event')
                    require(r['evidence_timing']['started_monotonic']>=start,'main timing predates main interval')
                    bound=bounds.pop(remote+'/'+path);side_sha=hashlib.sha256(archive.read(side)).hexdigest();require(bound['timing_sha256']==side_sha,'main timing boundary/sidecar differs')
                    rows.append({'timing':r,'mode':mode,'method':scope+'/'+method,'accounted_through_monotonic':bound['completed_monotonic']})
                    bindings.append({'path':path,'sha256':r['receipt_sha256'],'timing_sha256':side_sha,'physical_event_id':event,'event_sha256':closed[event]['sha256'] if event is not None else None})
        require(not bounds and seen==set(reserved) and bindings==refresh['receipt_bindings'],'PUBLIC refresh all-main receipt/event coverage differs')
        rows.sort(key=lambda r:r['timing']['evidence_timing']['started_monotonic'])
        try:selected,coverage=derive_timing_measurements(rows,calibration,original,now)
        except ValueError:
            require(status=='CALIBRATION_FALLBACK','unsupported timing coverage claimed refreshed estimate')
        else:
            require(status=='MAIN_TIMING_REFRESHED','complete supported timing unexpectedly claimed unsupported fallback')
            require(refresh['refreshed_measurements']==refresh['selected_measurements']==selected and refresh['refreshed_estimate']==refresh['selected_estimate']==public_estimate(selected) and refresh['coverage']==coverage,'independent PUBLIC timing arithmetic/coverage differs')
    if 'experiment/public/phase.json' in archive.members:
        phase=archive.json('experiment/public/phase.json')
        reference=phase.get('cost_refresh',phase.get('forecast',{}).get('cost_refresh'))
        require(reference=={'path':request['output_root']+'/'+name,'sha256':hashlib.sha256(archive.read(name)).hexdigest()},'PUBLIC phase omitted exact frozen refresh reference')
    if 'experiment/public/forecast.json' in archive.members:
        public=archive.json('experiment/public/forecast.json')
        require(public.get('cost_refresh')=={'path':request['output_root']+'/'+name,'sha256':hashlib.sha256(archive.read(name)).hexdigest()} and number(public.get('decision_monotonic')) and now<=public['decision_monotonic'],'PUBLIC admission not bound to prior immutable refresh')
        require(all(public.get(k)==value for k,value in refresh['selected_estimate'].items()),'PUBLIC forecast differs from frozen selected estimate')
        if snapshot is not None:require(public['ledger_head_sha256']==snapshot['head_sha256'] and public['physical_usage_at_decision']==snapshot['physical_usage'],'PUBLIC call work began before immutable cost admission')
    for member in archive.members:
        if member.startswith('experiment/public/native/') and member.endswith('.timing.json'):
            require(archive.json(member)['evidence_timing']['started_monotonic']>=now,'PUBLIC generation precedes frozen timing choice')
    return refresh['selected_measurements']
