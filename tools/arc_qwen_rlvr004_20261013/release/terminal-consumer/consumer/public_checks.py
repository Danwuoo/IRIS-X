"""Target-free PUBLIC pool/seal and original pinned scorer-row replay. No gold I/O."""
from collections import Counter
from .safe_io import need,integer,finite,digest,canonical,sha,same
from .prediction_checks import reference,generation
from .grid_checks import grid

SCORER_PINS = {'tools/arc_offline_evaluation.py': '3df3fd40c0a4db82dc6ad5c568102e45ad10efad8529412eae0623bd9f4ba016', 'tools/arc_kaggle_submission.py': 'cdd570c99614d5eb326f9f07d86b36f80e4f5e53ec197370b5a0e03f262366bf', 'src/irisx/arc_agi2.py': '0af942df40b76f208546a88864e84ddf521168bdb8f1fa4ce24232c36f3034a1', 'tools/nvarc_native_multitask.py': '274cc5391ee45ee098cba4f002e31425d5bed88993c2b9319b0320c17a08fbdb', 'tools/nvarc_native_solve_runtime.py': '56380d7c5fbb9219acfc846af275d6a334ed9460b6b6448e6feacf78be77b1c1', 'src/irisx/__init__.py': '3ca8d59be8dae69d75bd92b279cdab54a5c411162d78544578f924264905702e', 'src/irisx/artifacts.py': '28a7a48cbabd0f8556a1f976aebeaec3cc0824a380ab8bb4c12ba5cdfc762c95', 'src/irisx/canonical.py': 'd2bacf5548440c865a64cb7cdfbbefcb995ec47e4e53ddfa4457964a83740a6a', 'src/irisx/contracts.py': 'afb58a3fefe0c5482616d4cd219779c5bc9dacb30be44ea153ab85496b9af6b1', 'src/irisx/errors.py': '45c10f3c10c958cb3cca97a26a3a0f79925ed5818ce591327d9ef1a851a6ffa4', 'src/irisx/engine.py': 'bd08a6d9740d7696c6663410a450323c0c00cc5320bce184339ea4a98717d283', 'src/irisx/bindings.py': 'cc0bb9698ab8803c3c951cd88d7c233661dd2a38c6f1066f7d86ac8be98f7601', 'tools/__init__.py': 'f5ed985f7ed9e31ea3be113e86b11a7b44313f467c2e468a034ff789c7b85c76', 'src/irisx/admission.py': '0520aa0b966ea7b2bd7f88330f6c3e0e407e428cf144458a1fda89317c38bb63'}
SOLVER_MANIFEST_SHA256='549019b4b5cb47176f3abd3fcd9ca516e91b7d6e581dfc414a5a6452ff7b1f7f'
SOLVER_CHALLENGES_FILE_SHA256='8cade36130fdf1fa8fbab00cfcdfb5be8e74acbf04140f6fe18c5f502f0639be'
# Derived offline only from the above original manifest-pinned target-free member.
SOLVER_CHALLENGES_CANONICAL_SHA256='93d3e1b76403937ce5424ae507a37d62a94c0d0e74c8fa01314c0e5572061d98'
METHOD='rl-abc/dev-selected-frozen-primaryTTT0-transform01-top2'

def scorer_digest(value):return 'sha256:'+digest(value)

def public_dispatch_cutoff(view,request,ended):
    """Bind actual new PUBLIC work to its exact protected request cutoff.

    Finishing an already dispatched call after this cutoff is retained as an
    honest overrun; the global owner deadline/clean closure is checked separately.
    """
    deadline=request['deadline'];started=request['generation_started']
    need(finite(deadline) and finite(started) and finite(ended),'finite PUBLIC dispatch interval required')
    for event in view['physical_events']:
        need(event.get('deadline')==deadline and started<=event['started']<=event['ended']<=ended,
             'PUBLIC physical operation differs from selected request cutoff/interval')
        if event['dispatched']:
            dispatch=event.get('dispatched_at')
            need(finite(dispatch) and event['started']<=dispatch<deadline,
                 'new PUBLIC physical dispatch after selected request cutoff')
    generation=view['receipt']['generation']
    for forward in generation.get('forward_trace',[]):
        need(finite(forward.get('started_monotonic')) and forward['started_monotonic']<deadline,
             'new PUBLIC native forward after selected request cutoff')


def scorer_rows(report,pool,*,synthetic):
    tasks={r['task_id']:r for r in pool['records']}
    need(len(tasks)==len(pool['records']) and tasks,'unique nonempty PUBLIC pool task inventory')
    tests={(r['task_id'],t['test_index']):t for r in pool['records'] for t in r['tests']}
    need(len(tests)==sum(len(r['tests']) for r in pool['records']),'duplicate PUBLIC pool query')
    if not synthetic:need(len(tasks)==120 and len(tests)==167,'full original120/167 score coverage required')
    rows=report.get('rows');need(type(rows) is list and len(rows)==len(tests),'sealed scorer row coverage differs')
    seen=set();counts=Counter();solved=Counter()
    for row in rows:
        ident=(row['task_id'],row['test_index']);need(ident in tests and ident not in seen,'unknown/duplicate sealed scorer row');seen.add(ident)
        rec=tasks[ident[0]];test=tests[ident];counts[ident[0]]+=1
        need(row['task_digest']==rec['task_digest'] and row['input_digest']==test['input_digest'] and row['pool_size']==len(test['ranked_grids']) and row['status']==test['status'],'sealed scorer/pool projection differs')
        for key in ('pass1','pass2','oracle','coverage','empty_pool','pool_miss','ranking_miss','record_observed'):
            need(type(row.get(key)) is bool,'strict original scorer result booleans required')
        need(row['record_observed'] is True and row['coverage'] is bool(row['pool_size']) and row['empty_pool'] is (row['pool_size']==0),'scorer record/coverage differs')
        need(not row['pass1'] or row['pass2'],'pass1 exceeds pass2')
        need(row['oracle'] is row['pass2'] and row['ranking_miss'] is False and row['pool_miss'] is (row['coverage'] and not row['oracle']),'top2 scorer attribution differs')
        need(sum(row[k] for k in ('pass2','empty_pool','pool_miss','ranking_miss'))==1,'exclusive original scorer failure attribution differs')
        solved[ident[0]]+=row['pass2']
    for task,n in counts.items():need({index for key,index in seen if key==task}==set(range(n)), 'non-contiguous original query index')
    n=len(tests);nt=len(tasks)
    metric=lambda num,den,unit='test':{'numerator':num,'denominator':den,'value':num/den,'unit':unit}
    metrics={name:metric(sum(r[field] for r in rows),n) for name,field in (('pass_at_1','pass1'),('pass_at_2','pass2'),('candidate_oracle','oracle'),('candidate_coverage','coverage'),('empty_pool','empty_pool'),('pool_miss','pool_miss'),('ranking_miss','ranking_miss'))}
    metrics.update(partial_pool=metric(sum(r['pool_size']==1 for r in rows),n),unobserved_test_record=metric(0,n),task_average_pass_at_2=metric(sum(solved[k]/v for k,v in counts.items()),nt,'task'),tasks_all_tests_pass_at_2=metric(sum(solved[k]==v for k,v in counts.items()),nt,'task'))
    expected={'tasks':nt,'tests':n,'aggregation':'test-micro, task-macro and whole-task success reported separately','metrics':metrics,'candidate_total':sum(r['pool_size'] for r in rows)}
    need(same(report.get('development_metrics'),expected),'scorer rows and aggregate metrics differ')
    need(report.get('run_id')==pool['run_id'] and report.get('method')==pool['method'] and report.get('source_digest')==pool['challenges_digest'],'original scorer pool/source identity differs')
    return expected


def metric_threshold(metrics,*,real):
    # This consumes independently reaggregated original scorer rows. Generation
    # coverage is a separate axis; absent predictions remain wrong in167 rows.
    metric=metrics.get('metrics',{}).get('pass_at_2',{})
    need(type(metric.get('denominator')) is int and metric['denominator']==167 and integer(metric.get('numerator'),0,167) and metric.get('unit')=='test' and finite(metric.get('value')) and abs(metric['value']-metric['numerator']/167)<=1e-12,'full original167-query metric required for PUBLIC threshold')
    return bool(real and metric['numerator']>=151)


def public_view_complete(receipt):
    return receipt['dispatched'] is True and receipt['status'] not in ('infrastructure-excluded','not-reached')


def scorer_detail_metadata(saved,detail,*,modern):
    owner={'owner_inner_closure_sha256','owner_request_sha256','owner_outer_closure','scoring_started_monotonic','scoring_finished_monotonic'}
    if modern or owner.intersection(detail):
        need(owner<=set(detail) and all(same(detail[k],saved.get(k)) for k in owner),'scorer detail owner/chronology differs from actual sealed summary')
    need(same({k:v for k,v in saved.items() if k not in owner|{'detail'}},{k:v for k,v in detail.items() if k not in owner|{'report'}}),'sealed original scorer detail/summary differs')


def validate_public(root,handle,*,proof,source_files,original_root,synthetic,closure_time,score=None):
    seal=reference(root,handle,original_root)
    need(handle.get('format')==seal.get('format')=='irisx/rl-public-successor-seal-v1' and handle.get('status')=='PUBLIC_SUCCESSOR_PREDICTIONS_SEALED','PUBLIC successor seal schema')
    need(seal.get('source_sha256')==proof['source_sha256'] and seal.get('generation_closed') is True,'PUBLIC source/generation closure differs')
    request=reference(root,seal['request'],original_root);artifact=reference(root,seal['artifact'],original_root);pool=reference(root,seal['pool'],original_root)
    need(request.get('format')=='irisx/rl-public-successor-request-v1' and artifact.get('format')=='irisx/rl-public-successor-predictions-v1','PUBLIC request/prediction schema')
    need(request.get('source_sha256')==proof['source_sha256'] and same(request.get('source_files'),source_files) and request.get('experiment_plan_sha256')==proof['plan_sha256'],'PUBLIC exact source/plan binding')
    selected=proof['evaluation']['selected_arm'];checkpoint=proof['checkpoints'][selected]
    need(request.get('selected_arm')==artifact.get('selected_arm')==seal.get('selected_arm')==handle.get('selected_arm')==selected and request.get('adapter_sha256')==artifact.get('adapter_sha256')==checkpoint['adapter_sha256'],'PUBLIC arm differs from frozen dev selection')
    need(request.get('selected_state_sha256')==checkpoint['state_sha256'] and request.get('selected_reload',{}).get('state_sha256')==checkpoint['state_sha256'],'PUBLIC actual selected full-state checkpoint differs')
    selected_manifest=reference(root,request['selected_checkpoint_manifest'],original_root)
    need(selected_manifest.get('state_sha256')==checkpoint['state_sha256'],'PUBLIC checkpoint manifest alias')
    dev_selection=reference(root,request['dev_selection'],original_root)
    need(same(dev_selection,root.json('experiment/dev-selection.json')),'PUBLIC current-run dev selection differs')
    dev_seal=reference(root,request['dev_predictions'],original_root)
    dev_payload=root.json('experiment/dev-predictions-sealed.json')
    # request.dev_predictions is the prediction seal handle, so reference opens
    # the sealed payload rather than the separate handle JSON.
    need(same(dev_seal,dev_payload),'PUBLIC dev prediction authority differs')
    dev_ids=[]
    for arm_rows in dev_payload['methods'].values():
        for row in arm_rows:
            for ref in row['generations']:
                need(ref is not None,'PUBLIC selection requires complete actual dev')
                raw=reference(root,ref,original_root)
                if raw['dispatched']:dev_ids.append(raw['generation']['physical_event_id'])
    last_dev=max((proof['events'][i]['ended'] for i in dev_ids),default=proof['plan']['global_started'])
    selected_reload=request['selected_reload'];reload_skipped=selected_reload.get('PUBLIC_reload_not_reached') is True
    if reload_skipped:
        actual_proof=root.json('experiment/'+selected+'-checkpoint-proof.json')['reload']
        need(same(selected_reload.get('prior_durable_checkpoint_proof'),actual_proof)
             and same({k:v for k,v in selected_reload.items() if k not in ('PUBLIC_reload_not_reached','prior_durable_checkpoint_proof')},actual_proof),
             'unreached PUBLIC reload must retain exact prior proof without inventing a new restore')
    else:
        reload_event=proof['events'].get(selected_reload.get('physical_event_id'))
        need(reload_event is not None and reload_event.get('phase')=='checkpoint-reload'
             and reload_event.get('dispatched') is True and reload_event.get('status')=='complete'
             and last_dev<=reload_event['started']<=reload_event['ended']<=request['generation_started'],
             'PUBLIC dispatch requires new actual selected reload after sealed dev')
        need(reload_event.get('checkpoint_path')==selected_reload.get('checkpoint_path')
             and reload_event.get('manifest_sha256')==selected_reload.get('manifest_sha256')==request['selected_checkpoint_manifest']['file_sha256']
             and reload_event.get('state_sha256')==checkpoint['state_sha256'],
             'PUBLIC actual reload selected checkpoint target differs')

    expected_inf={**proof['plan']['inference'],'do_sample':False,'temperature':1.,'top_p':1.}
    need(same(request.get('inference_contract'),expected_inf),'PUBLIC fixed greedy two-view inference differs')
    challenges=reference(root,request['challenge_ref'],original_root)['challenges']
    need(digest(challenges)==request.get('challenge_sha256'),'PUBLIC target-free challenge projection commitment differs')
    cases=[]
    for task,data in sorted(challenges.items()):
        need(type(data) is dict and set(data)=={'train','test'} and data['train'] and data['test'],'closed target-free PUBLIC task')
        need(all(set(d)=={'input','output'} for d in data['train']) and all(set(t)=={'input'} for t in data['test']),'PUBLIC query targets leaked')
        for d in data['train']:grid(d['input']);grid(d['output'])
        for index,test in enumerate(data['test']):
            grid(test['input']);cases.append({'case_id':f'public:{task}:{index}','parent_id':task,'scope':'public','demos':data['train'],'query_input':test['input'],'index':index})
    real=request.get('evidence_mode')=='public-development'
    if real:
        need(len(challenges)==120 and len(cases)==167 and request.get('solver',{}).get('manifest_sha256')==SOLVER_MANIFEST_SHA256,'full pinned PUBLIC solver identity/coverage')
        # Actual challenge bytes still need source-authenticated solver manifest linkage.
        need(request['challenge_sha256']==SOLVER_CHALLENGES_CANONICAL_SHA256,'original manifest/member-derived PUBLIC challenge identity differs')
        need(proof.get('public_challenges_sha256') in (None,SOLVER_CHALLENGES_CANONICAL_SHA256),'caller cannot override original PUBLIC challenge pin')
    else:need(synthetic and request.get('evidence_mode')=='synthetic-test-only' and 1<=len(cases)<=4 and request.get('solver') is None,'explicit bounded synthetic PUBLIC origin required')
    need(request.get('planned_queries')==artifact.get('query_count')==len(cases) and request.get('planned_views')==artifact.get('view_count')==2*len(cases),'PUBLIC original query/view denominator differs')
    need(same(artifact.get('request'),seal['request']) and request.get('query_targets_used') is False and artifact.get('query_targets_used') is False,'PUBLIC target-free request link')
    need(finite(request.get('generation_started')) and finite(artifact.get('generation_ended')) and request['generation_started']<=artifact['generation_ended']<=closure_time and request['deadline']<=proof['plan']['global_started']+42000 and artifact['generation_ended']<=proof['plan']['global_started']+42000,'PUBLIC generation must finish before original inner deadline and owner closure')
    need(type(artifact.get('deadline_exceeded')) is bool and artifact['deadline_exceeded'] is (artifact['generation_ended']>request['deadline']),'PUBLIC actual deadline overrun must be retained honestly')
    rows=artifact['rows'];need(len(rows)==len(cases),'complete PUBLIC prediction rows required')
    records={task:{'task_id':task,'task_digest':scorer_digest(data),'tests':[],'timings':{}} for task,data in sorted(challenges.items())};events=set();calls=0;completed=0
    for index,(row,case) in enumerate(zip(rows,cases)):
        need(row.get('case_id')==case['case_id'] and row.get('parent_id')==case['parent_id'] and type(row.get('test_index')) is int and row['test_index']==case['index'] and row.get('input_sha256')==digest(case['query_input']),'PUBLIC query identity/order differs')
        need(type(row.get('generations')) is list and len(row['generations'])==2,'exact PUBLIC two view slots')
        answers=[];complete=True
        for op,ref in enumerate(row['generations']):
            need(type(ref.get('transform')) is int and ref['transform']==op,'PUBLIC fixed transform slot order')
            view=reference(root,ref['receipt'],original_root)
            need(view.get('format')=='irisx/rl-public-successor-view-v1' and view.get('case_id')==case['case_id'] and view.get('transform')==op and view.get('input_sha256')==digest(case['query_input']) and view.get('selected_arm')==selected and view.get('adapter_sha256')==checkpoint['adapter_sha256'],'PUBLIC raw view identity differs')
            need(view.get('seed')==1917 and view.get('do_sample') is False and view.get('TTT') is False and view.get('max_new_tokens')==expected_inf['max_new_tokens'],'PUBLIC raw inference policy differs')
            public_dispatch_cutoff(view,request,artifact['generation_ended'])
            raw=view['receipt'];need(view.get('native_receipt') is True,'full PUBLIC content replay requires actual native token/packing receipts; controlled non-native views are schema-only')
            pred=generation(raw,case=case,operation=op,adapter=checkpoint,events=proof['events'],inference=expected_inf,synthetic=synthetic,codec=proof.get("codec"))
            if raw['status']=='not-reached':need(view['physical_events']==[],'unreached PUBLIC slot invented work')
            for e in view['physical_events']:
                need(e['event_id'] not in events and same(proof['events'].get(e['event_id']),e),'PUBLIC physical work reused or omitted from owned union');events.add(e['event_id'])
            calls+=raw['dispatched'];complete &= public_view_complete(raw)
            if pred is not None and pred not in answers:answers.append(pred)
        need(same(row.get('answers'),answers),'PUBLIC deduplicated pool not derived from raw views');completed+=complete
        records[case['parent_id']]['tests'].append({'test_index':case['index'],'input_digest':scorer_digest(case['query_input']),'ranked_grids':answers,'status':'complete' if complete else 'partial' if answers else 'failed'})
    need(not reload_skipped or calls==0,'PUBLIC generated views without actual selected reload')
    expected_pool={'format':pool.get('format'),'run_id':'rl-public-'+seal['request']['file_sha256'][:24],'method':METHOD,'challenges_digest':scorer_digest(challenges),'records':list(records.values()),'parent_wall_seconds':artifact['generation_ended']-request['generation_started']}
    need(pool.get('format')=='irisx/arc-offline-pools-v1' and same(pool,expected_pool),'PUBLIC scorer pool differs from raw native generation projection')
    coverage={'planned_queries':len(cases),'observed_queries':len(cases),'planned_views':2*len(cases),'observed_views':2*len(cases),'actual_generation_calls':calls,'complete_prediction_coverage':completed==len(cases),'deadline_exceeded':artifact['deadline_exceeded'],'query_targets_used':False}
    need(same(seal.get('coverage'),coverage) and same(handle.get('coverage'),coverage),'PUBLIC coverage not derived')
    result={'coverage':coverage,'selected_arm':selected,'scientific_goal_met':False,'status':'PREDICTIONS_SEALED_NOT_SCORED'}
    if score is not None:
        saved=reference(root,score,original_root);detail=reference(root,saved['detail'],original_root)
        need(same(saved,{k:v for k,v in score.items() if k not in ('path','file_sha256')}),'actual sealed scorer summary differs from outer score handle')
        need(saved.get('format')=='irisx/rl-public-successor-evaluation-v1' and saved.get('source_sha256')==proof['source_sha256'] and saved.get('selected_arm')==selected and same(saved.get('prediction_seal'),handle),'PUBLIC scorer source/seal/selection binding differs')
        need(same(saved.get('scorer_pins'),SCORER_PINS) and saved.get('scorer_sha256')==SCORER_PINS['tools/arc_offline_evaluation.py'] and all(source_files.get('baseline/'+n)==h for n,h in SCORER_PINS.items()),'PUBLIC scorer must remain unchanged original source closure')
        need(all(row.get('demonstrations_digest')==scorer_digest(challenges[row['task_id']]['train']) for row in detail['report']['rows']),'original scorer demonstration digest differs')
        metrics=scorer_rows(detail['report'],pool,synthetic=synthetic)
        need(same(saved.get('development_metrics'),metrics),'original scorer aggregate differs')
        scorer_detail_metadata(saved,detail,modern='physical_events_ref' in proof['result'])
        need(saved.get('goal_met') is False and saved.get('official_score') is None and saved.get('production_admitted') is False,'unadmitted source/fixture cannot claim scientific goal')
        threshold=metric_threshold(metrics,real=True) if real else False
        result.update(status='SEALED_SCORER_ROWS_REPLAYED',scorer_rows_complete=True,micro_pass_at_2=metrics['metrics']['pass_at_2'],metric_threshold_reached=threshold,threshold_reached=threshold)
    return result
