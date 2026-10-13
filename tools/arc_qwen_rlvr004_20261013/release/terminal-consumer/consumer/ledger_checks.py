"""Independent event-union, whole-phase, original-clock and durable-chain replay."""
from collections import Counter
from copy import deepcopy
import hashlib,hmac
from .safe_io import need,integer,finite,digest,canonical,sha,same,is_sha,parse_json

OFFSETS={'inner':42000.,'outer':42180.,'provider':42300.,'absolute':43200.}
FINAL={'complete','failed','excluded','excluded-recovered'}
PHASES={'checkpoint-save','checkpoint-reload','anchor-sft-forward-backward','control-sft-forward-backward',
        'optimizer-commit','continuation-optimizer-setup','sample-forward','causal-replay','ddis-backward',
        'strict-reward','restore','evaluation-generation','public-generation','session-cleanup',
        'environment-admission','snapshot','owned-sft-step','native-load','native-model-load','model-load','sample','generation','prediction','calibration','calibration-generation','calibration-operation','rollout-generation','rl-update'}
FORWARD={'sample-forward','causal-replay','anchor-sft-forward-backward','control-sft-forward-backward','evaluation-generation','public-generation'}
IMMUTABLE={'event_id','op_id','parent_op_id','phase','started','deadline','soft_deadline','hard_deadline','kind','clock','device_time_measured'}

def interval(row):
    need(all(finite(row.get(k)) for k in ('started','ended','seconds')), 'finite complete physical interval required')
    need(row['ended']>=row['started'] and abs(row['seconds']-(row['ended']-row['started']))<=.001, 'physical interval ordering/duration differs')

def event_union(*collections):
    result={}
    for rows in collections:
        need(type(rows) is list, 'physical event list required')
        local=set()
        for row in rows:
            eid=row.get('event_id')
            need(integer(eid) and eid not in local, 'duplicate/noninteger physical event ID');local.add(eid)
            if eid in result:
                need(same(result[eid],row), 'conflicting physical event identity across evidence')
            result[eid]=row
    need(sorted(result)==list(range(len(result))), 'missing physical event in dense session sequence')
    return result

def resolved_events(root,container,original_root):
    need(type(container) is dict,'physical ledger container missing')
    if 'physical_events_ref' in container:
        need('physical_events' not in container,'ambiguous duplicated physical stream')
        from .prediction_checks import reference
        events=reference(root,container['physical_events_ref'],original_root)
        need(type(events) is list,'physical stream must be complete event list')
        if 'physical_events_sha256' in container:need(container['physical_events_sha256']==digest(events),'physical stream content hash differs')
        return events
    return container.get('physical_events')


def validate_metering(root,result,plan,original_root=None):
    bridge=root.json('physical-metering-closure.json');closure=result.get('model_closure')
    need(type(closure) is dict, 'inner model closure artifact required')
    original_root=original_root or str(root.path)
    flow_events=resolved_events(root,result,original_root);closed_events=resolved_events(root,closure,original_root);bridge_events=resolved_events(root,bridge.get('model_closure'),original_root)
    events=event_union(flow_events,closed_events,bridge_events)
    need(all(same(flow_events,x) for x in (closed_events,bridge_events)), 'complete physical ledger union differs')
    need(same(bridge.get('model_closure'),closure),'metering/inner closure differs')
    for e in events.values():
        interval(e);need(e.get('status') in FINAL and type(e.get('dispatched')) is bool, 'unsettled/unknown physical work')
        need(e.get('phase') in PHASES and e.get('clock')=='synchronized-wall-time' and e.get('device_time_measured') is False, 'physical event class/clock differs')
        if e['phase'] in FORWARD and e['dispatched']:
            need(integer(e.get('input_tokens')), 'known forward token ledger required')
        need(e['started']>=plan['global_started'] and e['ended']<=plan['global_started']+43200+.001, 'physical work outside original absolute deadline')
    for key in ('closed','future_operations_blocked','model_references_released','device_synchronized','model_stopped','ledger_settled'):
        need(closure.get(key) is True, 'unsafe owner closure: '+key)
    need(closure.get('fatal_native_state') is None, 'fatal model closure cannot establish settled success')
    need(finite(closure.get('closed_monotonic')) and max((e['ended'] for e in events.values()),default=0)<=closure['closed_monotonic']+.001, 'model work after inner closure')
    need(closure.get('original_global_deadline')==plan['global_started']+42000, 'inner closure reset original deadline')
    rows=list(events.values())
    derived={'event_ids':list(events),'event_count':len(events),'events_sha256':digest(rows),'actual_dispatched_events':sum(e['dispatched'] for e in rows),
             'status_counts':dict(Counter(e['status'] for e in rows)),
             'known_forward_input_tokens':sum(e.get('input_tokens',0) for e in rows if e['phase'] in FORWARD and e['dispatched'])+sum(e.get('forward_input_tokens',0) for e in rows if e['phase']=='rollout-generation' and e['dispatched'])+sum(e.get('actual_cost',{}).get('input_tokens',0) for e in rows if e['phase'].startswith('calibration-') and e['dispatched'])}
    for key,value in derived.items():
        need(same(bridge.get(key),value), 'physical bridge not derived: '+key)
    need(bridge.get('nested_event_duration_sum_used') is False and bridge.get('logical_rollback_can_refund_cost') is False, 'invalid physical wall/cost policy')
    phases=result.get('phase_intervals');need(type(phases) is list and [p.get('phase') for p in phases][:3]==['common-base-anchor','B','C'], 'mandatory whole phase inventory')
    need(same(bridge.get('whole_arm_intervals'),phases), 'whole interval bridge differs')
    for index,row in enumerate(phases):
        interval(row);need(row.get('status')=='complete' and row.get('clock')=='synchronized-model-phase-wall' and row.get('device_kernel_time') is False, 'whole-phase timing contract differs')
        if index:need(phases[index-1]['ended']<=row['started']+.001, 'whole phases overlap/reordered')
    for e in rows:
        need(any(p['started']-.001<=e['started']<=e['ended']<=p['ended']+.001 for p in phases) or e['phase'] in ('native-load','calibration-generation','calibration-operation','environment-admission') and e['ended']<=phases[0]['started'], 'physical work omitted from whole phase intervals')
    b,c=phases[1]['seconds'],phases[2]['seconds'];eps=min(120.,max(5.,.05*b))
    need(b<=7200 and c<=7200, 'whole continuation exceeds7200s cap')
    matching={'B_seconds':b,'C_seconds':c,'epsilon_seconds':eps,'matched':abs(b-c)<=eps,
              'includes_failures_rollback_setup_save_reload_verification':True,'clock':'whole-synchronized-model-phase-wall','idle_padding':False}
    need(same(result.get('time_matching'),matching), 'matched B/C wall not independently derived')
    common=phases[0]
    common_events=[e for e in rows if common['started']<=e['started']<=e['ended']<=common['ended'] and e['dispatched'] and e['status']=='complete']
    need(sum(e['phase']=='checkpoint-save' for e in common_events)>=2 and sum(e['phase']=='checkpoint-reload' for e in common_events)>=2,'actual base and A save/reload physical phases required')
    # Each whole arm must contain real restore, optimizer setup and save/reload work.
    for phase in phases[1:3]:
        actual={e['phase'] for e in rows if phase['started']<=e['started'] and e['ended']<=phase['ended']}
        need({'checkpoint-reload','continuation-optimizer-setup','checkpoint-save'}<=actual, 'whole continuation omitted setup/durability')
    for label,index,forward,counter in (('A',0,'anchor-sft-forward-backward','anchor_updates'),('C',2,'control-sft-forward-backward','control_updates')):
        phase=phases[index];counts=result.get('arms',{}).get(label,{}).get('updates',{})
        n=counts.get(counter);need(integer(n),'actual committed SFT count required')
        done=[e for e in rows if e['dispatched'] and e['status']=='complete' and phase['started']<=e['started']<=e['ended']<=phase['ended']]
        forwards=[e for e in done if e['phase']==forward];commits=[e for e in done if e['phase']=='optimizer-commit']
        need(len(forwards)>=n and len(commits)>=n,'committed '+label+' lacks actual forward/backward and optimizer work')
        for i in range(n):need(forwards[i]['ended']<=commits[i]['started']+.001,'committed SFT physical causal ordering differs')
    return events,{'events':len(events),'known_forward_input_tokens':derived['known_forward_input_tokens'],'time_matching':matching,'closed_monotonic':closure['closed_monotonic']}


def validate_clock(clock,request=None):
    need(clock.get('format')=='owned-rl-original-clock-v1' and same(clock.get('offsets'),OFFSETS), 'original clock schema/offsets differ')
    need(all(finite(clock.get(k)) for k in ('original_epoch','origin_monotonic','observed_epoch','observed_monotonic')), 'finite original clock mapping')
    need(0<clock['original_epoch']<=clock['observed_epoch'], 'future/reset original dispatch epoch')
    need(abs(clock['origin_monotonic']-(clock['observed_monotonic']-(clock['observed_epoch']-clock['original_epoch'])))<=1e-6, 'epoch to monotonic mapping differs')
    need(type(clock.get('fixture')) is bool and type(clock.get('session_id')) is str and clock['session_id'], 'clock session/scope identity')
    if request is not None:
        need(request.get('original_epoch')==clock['original_epoch'] and request.get('session_id')==clock['session_id'], 'owner request/clock identity differs')
    return clock['origin_monotonic']


def replay_journal(root,*,clock,key=None):
    path=root.member('physical-journal.jsonl')
    need(0<path.stat().st_size<=8192*400000,'bounded complete durable journal')
    def lines():
        with path.open('rb') as handle:
            count=0
            while True:
                line=handle.readline(8193)
                if not line:break
                need(count<400000 and len(line)<=8192 and line.endswith(b'\n'),'torn/overlarge durable journal record')
                count+=1;yield line
    events=[];head='0'*64;journal_id=None;closed=False;record_count=0;artifacts=[];op_ids=set();active=set()
    for seq,line in enumerate(lines()):
        envelope=parse_json(line);need(set(envelope)=={'payload','mac'}, 'closed journal envelope')
        row=envelope['payload'];need(type(row) is dict and is_sha(envelope['mac']), 'journal record/mac structure')
        need(row.get('schema')=='owned-physical-journal-v1' and type(row.get('seq')) is int and row['seq']==seq and row.get('previous')==head, 'durable sequence/hash chain differs')
        if key is not None:
            need(type(key) is bytes and len(key)>=32, 'separately authenticated parent key required')
            need(hmac.compare_digest(envelope['mac'],hmac.new(key,canonical(row),hashlib.sha256).hexdigest()), 'durable journal HMAC differs')
        head=sha(canonical(envelope));record_count+=1
        action=row.get('action')
        if seq==0:
            need(action=='open' and type(row.get('journal_id')) is str, 'initial durable open required');journal_id=row['journal_id'];continue
        need(row.get('journal_id')==journal_id, 'durable session journal identity changed')
        if action=='reserve':
            need(not closed, 'model work reserved after durable closure')
            e=row.get('event');need(type(e) is dict and type(e.get('event_id')) is int and e['event_id']==len(events), 'dense durable event identity')
            need(type(e.get('op_id')) is str and len(e['op_id'])==32 and e['op_id'] not in op_ids and all(c in '0123456789abcdef' for c in e['op_id']), 'unique immutable durable operation ID')
            need(e.get('status')=='reserved' and e.get('dispatched') is False, 'durable reservation precedes dispatch')
            parent=e.get('parent_op_id')
            need(parent is None or parent in active, 'nested operation lacks active parent')
            need(e.get('phase') in PHASES, 'unknown durable phase')
            kind='native-load' if e['phase'] in ('native-load','native-model-load','model-load') else 'generation' if e['phase'] in ('generation','sample','sample-forward','prediction','public-generation','rollout-generation','evaluation-generation','calibration-generation') else 'operation'
            need(e.get('kind')==kind, 'native call misclassified to enlarge deadline')
            soft,hard={'generation':(175.,180.),'operation':(115.,120.),'native-load':(1795.,1800.)}[kind]
            need(all(finite(e.get(k)) for k in ('started','deadline','soft_deadline','hard_deadline')), 'finite original-call deadlines')
            need(e['deadline']<=clock['origin_monotonic']+42000 and e['soft_deadline']<=min(e['deadline'],e['started']+soft)+.001 and e['hard_deadline']<=min(clock['origin_monotonic']+42180,e['started']+hard)+.001, 'original deadline/call cap expanded')
            events.append(deepcopy(e));op_ids.add(e['op_id']);active.add(e['op_id'])
        elif action in ('patch','dispatch','finish','recover'):
            need(not closed,'physical operation changed after journal closure')
            eid=row.get('event_id');need(integer(eid,0,len(events)-1), 'patch unknown operation')
            e=events[eid];need(row.get('op_id')==e['op_id'] and 'ended' not in e, 'durable terminal/operation identity changed')
            changes=row.get('changes');need(type(changes) is dict and not IMMUTABLE.intersection(changes), 'immutable durable fields changed')
            need(not(e['dispatched'] and set(changes).intersection({'reserved_forward_calls','reserved_input_tokens','reserved_cost'})), 'reserved failed-work cost changed after dispatch')
            need(not(e['dispatched'] and changes.get('dispatched') is False), 'failed/rollback physical work refunded')
            need(not(changes.get('dispatched') is True and not e['dispatched'] and action!='dispatch'), 'dispatch bypassed durable transition')
            need(not(e['dispatched'] and str(changes.get('status','')).startswith('excluded')), 'dispatched operation erased as exclusion')
            for association in ('actual_cost','trajectory_id','update_batch_id'):
                if association in changes and association in e:need(same(changes[association],e[association]),'immutable quantitative cost/trajectory/batch association changed')
            e.update(changes)
            if 'ended' in e:
                active.discard(e['op_id']);interval(e);need(e.get('status') in FINAL|{'unknown','unclosed-device-error'}, 'closed durable status')
        elif action=='close':
            need(not closed, 'duplicate durable closure');closed=True
        elif action=='artifact':
            need(closed, 'closure artifact bound before ledger close');artifacts.append(row)
        else:
            need(False,'unknown durable journal action')
    anchor=root.json('physical-journal.jsonl.anchor');need(set(anchor)=={'payload','mac'}, 'durable high-water anchor missing')
    a=anchor['payload'];need(a.get('seq')==record_count-1 and a.get('head')==head and a.get('journal_id')==journal_id, 'durable journal truncation/high-water mismatch')
    if key is not None:need(hmac.compare_digest(anchor['mac'],hmac.new(key,canonical(a),hashlib.sha256).hexdigest()),'durable anchor HMAC differs')
    charges=[]
    for e in events:
        row={'op_id':e['op_id'],'status':e['status']}
        if 'actual_cost' in e:
            need(type(e.get('reserved_cost')) is dict and all(finite(v) and v>=0 for v in e['reserved_cost'].values()) and type(e['actual_cost']) is dict and set(e['actual_cost'])==set(e['reserved_cost']) and all(type(k) is str and finite(v) and 0<=v<=e['reserved_cost'][k] for k,v in e['actual_cost'].items()),'finite typed nonnegative actual cost within immutable reservation required')
        if 'reserved_cost' in e:
            need(type(e['reserved_cost']) is dict and all(type(k) is str and finite(v) and v>=0 for k,v in e['reserved_cost'].items()),'finite quantitative cost reservations')
            row['charged_cost']=e.get('actual_cost',e['reserved_cost']) if e['status']=='complete' else e['reserved_cost']
        if 'reserved_input_tokens' in e:
            need(integer(e['reserved_input_tokens']) and integer(e.get('reserved_forward_calls')),'quantitative forward reservation required')
            row['charged_input_tokens']=e.get('forward_input_tokens',e['reserved_input_tokens']) if e['status']=='complete' else e['reserved_input_tokens']
            row['charged_forward_calls']=e.get('forward_calls',e['reserved_forward_calls']) if e['status']=='complete' else e['reserved_forward_calls']
            need(integer(row['charged_input_tokens']) and row['charged_input_tokens']<=e['reserved_input_tokens'] and integer(row['charged_forward_calls']) and row['charged_forward_calls']<=e['reserved_forward_calls'],'actual forward cost exceeds reservation')
        if len(row)>2:charges.append(row)
    unknown=[e['op_id'] for e in events if 'ended' not in e or e.get('status') not in FINAL]
    return {'journal_id':journal_id,'head_sha256':head,'record_count':record_count,'event_count':len(events),
            'closed':closed,'settled':closed and not unknown,'unknown_operation_ids':unknown,'physical_events':events,
            'cryptographically_authenticated':key is not None,'artifact_bindings':artifacts,'cost_charges':charges}
