"""Actual ARC SFT, disk-reloaded main controls and complete demo-only TTT.

No holdout scorer is called here. Sealed holdout outputs are scored only by the
outer process after verified model-owner closure. Public answers are never loaded.
"""
from __future__ import annotations
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import math
import time
from .protocol import PROTOCOL,require,digest,file_sha,checked_json
from .checkpoint_policy import GLOBAL, TTT, for_run as checkpoint_schedule_for_run
from .data import solver_case,pack_prompt,prepare_record,open_targets
from .arc_adaptation import Transform
from .science_profiles import counts,forecast,admission
from .transfer_selector import select_answers
from .timing_refresh import write_generation_timing, freeze_public_refresh, timing_sources
from tools.arc_learning_agent_20261011.budget import atomic_json,BudgetExceeded
from tools.arc_next_models import digest as native_digest
from tools.arc_learning_agent_20261011.grid_codec import decode_grid,encode_grid
from tools.arc_learning_agent_20261011.native_model import ContextLimitError
from tools.arc_qwen_portfolio_20261012.checkpoints import save_branch_checkpoint,load_branch_checkpoint,CheckpointLimits
from tools.arc_qwen_portfolio_20261012.fresh_reload import dispose_backend


def _deadline(deadline):
    if time.monotonic()>=deadline:raise BudgetExceeded('no further model work: transfer deadline')


def _list(grid):return [list(row) for row in grid]


def _shape(pred,target):
    return pred is not None and (len(pred),len(pred[0]))==(len(target),len(target[0]))


def _answers(generations):
    out=[]
    for row in generations:
        value=row['prediction']
        if value is not None and value not in out:out.append(value)
    return out[:2]


def _empty(case,reason):
    return {'case_id':case['case_id'],'answers':[],'generations':[],'complete':False,'reason':reason}


def generate_variant(model,case,operation,path,deadline,*,cap=1024,capture_timing=False):
    timing_started=time.monotonic()
    _deadline(deadline);transform=Transform(operation)
    demos=[{k:_list(transform.apply(d[k])) for k in ('input','output')} for d in case['demos']]
    query=_list(transform.apply(case['query_input']))
    messages,packing=pack_prompt(model,demos,query,task_id=case['case_id'])
    path=Path(path);atomic_json(path.with_suffix('.packing.json'),packing,exclusive=True)
    if messages is None:
        generation={'valid':False,'dispatched':False,'text':'','output_token_ids':[],'finish_reason':'context_excluded',
            'physical_event_id':None,'error':packing['reason'],'whole_example_excluded':True}
    else:
        generation=model.generate(messages,kind='grid',seed=PROTOCOL['seed'],max_new_tokens=cap,deadline=deadline)
        require(type(generation.get('dispatched')) is bool,'native generation dispatch receipt required')
    atomic_json(path,generation,exclusive=True)
    if capture_timing:
        write_generation_timing(path,generation,native_invoked=messages is not None,
            started=timing_started,persisted=time.monotonic())
    require(not generation.get('fatal_error',False),'fatal native generation: '+str(generation.get('error')))
    prediction=None
    if generation.get('valid'):
        try:prediction=_list(transform.inverse().apply(decode_grid(generation['text'])))
        except ValueError:pass
    return {'transform_d4':operation,'inverse_applied':True,'prediction':prediction,
        'dispatched':generation['dispatched'],'physical_event_id':generation.get('physical_event_id'),
        'receipt_sha256':file_sha(path),'receipt_path':str(path.absolute())}


def evaluate_cases(model,cases,output,deadline,*,cap=1024,rows=None,timing_sink=None):
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    rows=rows if rows is not None else [_empty(c,'not reached') for c in cases]
    for index,(case,row) in enumerate(zip(cases,rows)):
        _deadline(deadline)
        for operation in PROTOCOL['query_transforms']:
            row['generations'].append(generate_variant(model,case,operation,root/f'{index:03d}-{operation}.json',deadline,cap=cap,capture_timing=timing_sink is not None))
            row['answers']=_answers(row['generations']);atomic_json(root/f'{index:03d}-row.json',row)
            if timing_sink is not None:
                generation=row['generations'][-1]
                timing_sink.append({'receipt_path':generation['receipt_path'],
                    'timing_sha256':file_sha(Path(generation['receipt_path']).with_suffix('.timing.json')),
                    'completed_monotonic':time.monotonic()})
        row.update(complete=True,reason=None);atomic_json(root/f'{index:03d}-row.json',row)
        if timing_sink is not None:timing_sink[-1]['completed_monotonic']=time.monotonic()
    return rows


def seal_scope(root,scope,dataset,methods,*,selection=None):
    cases=[c['case_id'] for c in dataset['cases'] if c['scope']==scope]
    for rows in methods.values():require([r['case_id'] for r in rows]==cases,'full fixed denominator required before seal')
    payload={'format':'irisx/transfer-sealed-predictions-v1','scope':scope,'case_ids':cases,
        'plan_sha256':dataset['plan']['plan_sha256'],'methods':methods,'selection':selection,'query_targets_used':False}
    path=Path(root)/(scope+'-predictions-sealed.json');atomic_json(path,payload,exclusive=True)
    seal={'sealed':True,'scope':scope,'path':str(path.absolute()),'file_sha256':file_sha(path),
        'payload_sha256':digest(payload),'sealed_monotonic':time.monotonic()}
    atomic_json(Path(root)/(scope+'-prediction-seal.json'),seal,exclusive=True)
    return seal


def select_sft(dataset,seal,candidate_updates,*,include_base=False):
    payload=checked_json(seal['path'],seal['file_sha256']);targets=open_targets(dataset,'dev',seal)
    rows=[]
    for update in ([0]+list(candidate_updates) if include_base else candidate_updates):
        name='base' if update==0 else 'sft'+str(update);preds=payload['methods'][name]
        require(all(r['complete'] for r in preds),'incomplete SFT dev comparison cannot select')
        exact=sum(any(p==targets[r['case_id']] for p in r['answers']) for r in preds)
        shape=sum(any(_shape(p,targets[r['case_id']]) for p in r['answers']) for r in preds)
        valid=sum(bool(r['answers']) for r in preds)
        rows.append({'candidate_id':name,'update':update,'exact':exact,'shape':shape,'valid':valid,'denominator':16})
    rows.sort(key=lambda r:(-r['exact'],-r['shape'],-r['valid'],r['update']))
    return {'format':'irisx/transfer-frozen-sft-selection-v1','candidate_id':rows[0]['candidate_id'],'rankings':rows,
        'dev_prediction_file_sha256':seal['file_sha256'],'selection_uses_holdout_targets':False,'includes_frozen_base':include_base}


class SessionBackend:
    """Own one live native backend; each global checkpoint reconstructs fresh PEFT."""
    def __init__(self,model,trainer,ledger,factory,policy,calibration,manifest):
        self.model,self.trainer,self.ledger=model,trainer,ledger
        self.factory,self.policy,self.calibration,self.manifest=factory,policy,calibration,manifest
        self.reload_receipts=[];self.training_receipts=[]
        self.checkpoint_schedule=GLOBAL

    def reload(self,saved,records,provenance,deadline):
        from .decoder import authorize_calibration_reload
        _deadline(deadline);before=dict(self.ledger.used)
        counters=(self.model._counter,self.trainer._counter)
        identity=deepcopy(self.model.identity)
        self.training_receipts.extend(self.trainer.training_receipts)
        disposal=dispose_backend(self.model,self.trainer)
        self.model,self.trainer=self.factory()
        require(self.model.ledger is self.ledger and self.trainer.ledger is self.ledger,'fresh reload must retain physical ledger')
        require(self.model._counter==self.trainer._counter==0,'fresh wrappers must be unused')
        self.model._counter,self.trainer._counter=counters
        authorize_calibration_reload(self.model,self.calibration,identity)
        self.trainer.trainer.freeze_decoder_identity(self.policy)
        self.trainer.trainer.config['split_manifest']=self.manifest
        loaded=load_branch_checkpoint(self.trainer,saved['path'],branch_id='global_grid',records=records,
            expected_manifest_sha256=saved['manifest_sha256'],provenance=provenance,checkpoint_schedule=self.checkpoint_schedule)
        require(loaded['state_sha256']==saved['state_sha256'],'fresh global full-state reload differs')
        require(all(self.ledger.used[k]>=v for k,v in before.items()),'physical work refunded during reload')
        _deadline(deadline)
        result={'fresh_backend_reload_verified':True,'disposal':disposal,'loaded':loaded,'physical_counters_retained':list(counters)}
        self.reload_receipts.append(result);return result


def _native_admission(model,records,train_ids):
    admitted=[];rows=[]
    for record in records:
        try:
            prepared=prepare_record(model,record)
            rows.append({'record_id':record['record_id'],'parent_id':record['task_id'],'eligible':True,
                **{k:prepared[k] for k in ('prompt_tokens','completion_tokens','input_tokens','prepared_sha256')}})
            admitted.append(record)
        except ValueError as exc:
            if not isinstance(exc,ContextLimitError) and str(exc) not in ('context: no whole training demonstration fits','completion context: full target exceeds1024; never truncate','completion context exceeds4096'):raise
            rows.append({'record_id':record['record_id'],'parent_id':record['task_id'],'eligible':False,'reason':str(exc)})
    require({r['task_id'] for r in admitted}==set(train_ids),'one or more fixed32 parents has no complete target/prompt; no replacement')
    return admitted,{'rows':rows,'whole_target_truncation':False,'full_record_denominator':len(records),'eligible_records':len(admitted),
        'records_sha256':native_digest(admitted),'record_ids':[r['record_id'] for r in admitted],
        'records_count':len(admitted)}


def export_checkpoint_metadata(root, label, saved):
    """Compact source-hash-bound resume/inference metadata; never tensor bytes."""
    for filename in ('manifest.json', 'resume/state.json', 'inference/adapter_model.safetensors.index.json'):
        source=Path(saved['path'])/filename
        value=checked_json(source,file_sha(source),cap=8*1024**2)
        atomic_json(Path(root)/'checkpoint-metadata'/label/filename,
            {'source_path':str(source),'source_sha256':file_sha(source),'payload':value},exclusive=True)


def train_updates(trainer,records,steps,path,deadline):
    _deadline(deadline)
    try:result=trainer.train(records,max_steps=steps,deadline=deadline)
    except BaseException as exc:
        atomic_json(path,{'error':type(exc).__name__+': '+str(exc),'failure_receipt':getattr(exc,'receipt',None)},exclusive=True);raise
    atomic_json(path,result,exclusive=True)
    require(result.get('status')=='complete' and result.get('optimizer_steps')==steps and time.monotonic()<deadline,'complete requested optimizer updates required')
    return result


def _ttt_candidate_policy(task,checkpoint_sha,fold_context,candidate_hashes):
    return {'format':'irisx/demo-only-grid-portfolio-v1','candidate_order':['ttt0','ttt8','ttt16'],
        'candidate_specs':{name:{'role':'global_sft' if name=='ttt0' else 'task_ttt','checkpoint_sha256':sha,
            'adaptation_scope':'none' if name=='ttt0' else 'task-demonstrations'} for name,sha in candidate_hashes.items()},
        'fold_conditioning_demo_ids':fold_context,'transform_order':['d4:0','d4:1'],'maximum_answers':2,
        'reference_candidate_id':'ttt0','reference_role':'global_sft','frozen_global_checkpoint_sha256':checkpoint_sha}


def run_ttt_case(session,case,checkpoint,root,deadline,*,cap=1024,persist_representative=False):
    model,trainer=session.model,session.trainer;root=Path(root);root.mkdir(parents=True,exist_ok=False)
    demos=case['demos'];require(2<=len(demos)<=10,'complete TTT requires at least2 visible demos')
    task={'task_id':case['case_id'],'demonstrations':[{'demo_id':str(i),**d} for i,d in enumerate(demos)],'query_input':case['query_input']}
    candidates={name:{'candidate_id':name,'task_id':case['case_id'],'checkpoint_sha256':None,
        'adaptation_scope':'none' if name=='ttt0' else 'task-demonstrations','folds':[],'query_predictions':[]} for name in ('ttt0','ttt8','ttt16')}
    contexts={};state_bindings={name:[] for name in candidates};training=[]
    global_hash=trainer.fingerprint()['sha256'];before=dict(session.ledger.used)
    for held,demo in enumerate(demos):
        others=[d for i,d in enumerate(demos) if i!=held]
        fold={'case_id':case['case_id']+':fold'+str(held),'demos':others,'query_input':demo['input']}
        messages,packing=pack_prompt(model,others,demo['input'],task_id=fold['case_id'])
        require(messages is not None,'whole outer-fold prompt unavailable; retain TTT denominator')
        original_ids=[str(i) for i in range(len(demos)) if i!=held]
        contexts[str(held)]=[original_ids[int(i)] for i in packing['selected_demo_ids']]
        task_key=fold['case_id'];trainer.begin_task(task_key)
        try:
            for update in (0,8,16):
                if update:
                    result=trainer.adapt_task(task_key,others,max_steps=8,deadline=deadline)
                    atomic_json(root/f'fold-{held}-train-{update}.json',result,exclusive=True)
                    require(result.get('status')=='complete' and result.get('optimizer_steps')==8,'incomplete outer-fold update')
                    training.append(result)
                gen=generate_variant(model,fold,0,root/f'fold-{held}-gen-{update}.json',deadline,cap=cap)
                _deadline(deadline);score=model.score_completion(messages,encode_grid(demo['output']),deadline=deadline)
                atomic_json(root/f'fold-{held}-score-{update}.json',score,exclusive=True)
                require(score.get('valid') and score.get('dispatched') and score.get('token_count',0)>0,'complete demo-only NLL required')
                name='ttt'+str(update);state=trainer.fingerprint()['sha256'];state_bindings[name].append(state)
                binding={'generation':gen,'score_sha256':digest(score),'state_sha256':state,'trained_demo_ids':original_ids if update else [],
                    'heldout_demo_id':str(held),'source':case['source'],'training_receipts_sha256':digest(training)}
                atomic_json(root/f'fold-{held}-binding-{update}.json',binding,exclusive=True)
                candidates[name]['folds'].append({'heldout_demo_id':str(held),'conditioning_demo_ids':contexts[str(held)],
                    'adaptation_demo_ids':original_ids if update else [],'prediction':gen['prediction'],'nll_sum':score['nll_sum'],
                    'token_count':score['token_count'],'receipt_sha256':digest(binding)})
        finally:
            reset=trainer.end_task();require(reset['adapter_sha256']==global_hash,'outer fold did not reset selectedSFT')
            atomic_json(root/f'fold-{held}-reset.json',reset,exclusive=True)
    trainer.begin_task(case['case_id']+':query-full-demo')
    representative=None;representative_reload=None;representative_record_identity=None
    try:
        for update in (0,8,16):
            if update:
                result=trainer.adapt_task(case['case_id']+':query-full-demo',demos,max_steps=8,deadline=deadline)
                atomic_json(root/f'full-demo-train-{update}.json',result,exclusive=True)
                require(result.get('status')=='complete' and result.get('optimizer_steps')==8,'incomplete full-demo query refit')
                training.append(result)
            name='ttt'+str(update);state_bindings[name].append(trainer.fingerprint()['sha256'])
            for operation in PROTOCOL['query_transforms']:
                gen=generate_variant(model,case,operation,root/f'query-{update}-{operation}.json',deadline,cap=cap)
                candidates[name]['query_predictions'].append({'transform_id':'d4:'+str(operation),'grid':gen['prediction'],
                    'inverse_applied':True,'receipt_sha256':gen['receipt_sha256']})
            if update==16 and persist_representative:
                from .data import build_task_records
                raw=trainer.trainer
                records=build_task_records(raw._task_id,demos,augmentations=raw.config['task_augmentations'],seed=raw._task_seed)
                representative=save_branch_checkpoint(trainer,root.parents[1]/'checkpoint-assets',branch_id='representative_ttt',update=16,
                    records=records,provenance={'source':case['source'],'global_checkpoint_sha256':checkpoint['manifest_sha256']},checkpoint_schedule=TTT)
                # Exact complete-state disk reload at one fixed representative only.
                loaded=load_branch_checkpoint(trainer,representative['path'],branch_id='representative_ttt',records=records,
                    expected_manifest_sha256=representative['manifest_sha256'],provenance={'source':case['source'],'global_checkpoint_sha256':checkpoint['manifest_sha256']},checkpoint_schedule=TTT)
                require(loaded['state_sha256']==representative['state_sha256'],'representative TTT persisted state mismatch')
                representative_reload=loaded
                representative_record_identity={'records_sha256':native_digest(records),'records_count':len(records),
                    'record_ids':[r['record_id'] for r in records],'task_id':raw._task_id,
                    'case_id':case['case_id'],'source':case['source'],'global_checkpoint_sha256':checkpoint['manifest_sha256']}
                atomic_json(root/'checkpoint-records.json',{**representative_record_identity,'records':records},exclusive=True)
                atomic_json(root/'representative-reload.json',loaded,exclusive=True)
                export_checkpoint_metadata(root.parents[1],'representative_ttt',representative)
    finally:
        reset=trainer.end_task();require(reset['adapter_sha256']==global_hash,'full-demo refit did not reset selectedSFT')
        atomic_json(root/'full-demo-reset.json',reset,exclusive=True)
    hashes={name:checkpoint['manifest_sha256'] if name=='ttt0' else digest({'global_checkpoint':checkpoint['manifest_sha256'],
        'task_id':case['case_id'],'candidate_id':name,'native_state_hashes':state_bindings[name]}) for name in candidates}
    for name in candidates:candidates[name]['checkpoint_sha256']=hashes[name]
    policy=_ttt_candidate_policy(task,checkpoint['manifest_sha256'],contexts,hashes)
    atomic_json(root/'selector-inputs.json',{'task':task,'policy':policy,'candidates':list(candidates.values())},exclusive=True)
    selected=select_answers(task,policy,list(candidates.values()))
    result={'case_id':case['case_id'],'answers':[r['grid'] for r in selected['answers']],'complete':True,'selection':selected,
        'policy':policy,'candidate_state_hashes':state_bindings,'global_reset_verified':True,'representative_checkpoint':representative,
        'representative_reload':representative_reload,'representative_record_identity':representative_record_identity,
        'physical_usage':{k:session.ledger.used[k]-v for k,v in before.items()},'outer_folds':len(demos),
        'full_demo_retrains':1,'training_receipt_count':len(training),'reference_role':'selected_global_sft'}
    atomic_json(root/'result.json',result,exclusive=True);return result


def run_public(session,config,selection,checkpoint,output,deadline,stats,*,records,provenance,return_checkpoint,cap=1024,cost_refresh=None):
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    if not config.get('public_solver_root'):
        result={'status':'PUBLIC_NOT_RUN','reason':'no-source-bound-public-solver-assets','cost_refresh':cost_refresh};atomic_json(root/'phase.json',result,exclusive=True);return result
    from tools.arc_public_research_20261010.public_data import load_solver_tasks
    loaded=load_solver_tasks(config['public_solver_root'],config['public_solver_manifest_sha256'])
    estimate=forecast(stats,updates=0,generations=334,reloads=2)
    if cost_refresh is not None:
        frozen=checked_json(cost_refresh['path'],cost_refresh['sha256'])
        require(frozen['selected_estimate']==estimate,'PUBLIC forecast differs from frozen timing choice')
    cost=admission(estimate,session.ledger,deadline)
    cost['cost_refresh']=cost_refresh
    atomic_json(root/'forecast.json',cost,exclusive=True)
    if not cost['admitted']:
        result={'status':'PUBLIC_NOT_RUN','reason':cost['reason'],'forecast':cost,'cost_refresh':cost_refresh};atomic_json(root/'phase.json',result,exclusive=True);return result
    require(not session.ledger.pending,'pending work prevents public phase')
    different=checkpoint['manifest_sha256']!=return_checkpoint['manifest_sha256']
    if different:session.reload(checkpoint,records,provenance,deadline)
    method={'candidate_id':selection['candidate_id'],'checkpoint_manifest_sha256':checkpoint['manifest_sha256'],'adapter_sha256':checkpoint['adapter_sha256'],'role':'frozen_base' if selection['candidate_id']=='base' else 'global_sft'}
    atomic_json(root/'frozen-method.json',{'method':method,'selection_sha256':selection['selection_sha256'],
        'query_targets_used':False,'frozen_monotonic':time.monotonic(),'selected_before_public_queries':True,
        'main_selection':{'path':str((root.parent/'public-selection.json').absolute()),'sha256':file_sha(root.parent/'public-selection.json')}},exclusive=True)
    predictions={};receipts=[];calls=0
    with session.model.adapter_branch('base') if selection['candidate_id']=='base' else nullcontext():
        for parent,queries in sorted(loaded['query_inputs'].items()):
            predictions[parent]=[]
            for index,query in enumerate(queries):
                case={'case_id':'public:'+parent+':'+str(index),'demos':loaded['demos_tasks'][parent]['demos'],'query_input':query}
                gens=[generate_variant(session.model,case,op,root/'native'/f'{parent}-{index}-{op}.json',deadline,cap=1024) for op in (0,1)]
                answers=_answers(gens);calls+=sum(g['dispatched'] for g in gens)
                predictions[parent].append({'attempt_1':answers[0] if answers else None,'attempt_2':answers[1] if len(answers)>1 else None})
                receipts.append({'parent_id':parent,'test_index':index,'input_sha256':digest(query),'generations':gens})
    require(len(receipts)==167 and not session.ledger.pending,'complete167 public slots without pending work required')
    payload={'format':'irisx/transfer-public-predictions-v1','solver_manifest_sha256':config['public_solver_manifest_sha256'],
        'method':method,'predictions':predictions,'case_receipts':receipts,'case_count':167,'test_answers_read':False,
        'physical_pending':{},'plan_sha256':digest(PROTOCOL)}
    path=root/'predictions.json';atomic_json(path,payload,exclusive=True)
    result={'status':'PUBLIC_PREDICTIONS_SEALED','artifact_path':str(path.absolute()),'artifact_sha256':file_sha(path),
        'solver_manifest_sha256':config['public_solver_manifest_sha256'],'method':method,'cases':167,'generation_calls':calls,
        'actual_generation_calls':calls,'planned_generation_calls':334,'frozen_method_path':str((root/'frozen-method.json').absolute()),
        'frozen_method_sha256':file_sha(root/'frozen-method.json'),'forecast':cost,'cost_refresh':cost_refresh}
    atomic_json(root/'phase.json',result,exclusive=True)
    if different:session.reload(return_checkpoint,records,provenance,deadline)
    return result


def run_experiment(session,dataset,output,deadline,*,feasibility,config):
    root=Path(output);root.mkdir(parents=True,exist_ok=False);start=time.monotonic();physical=session.ledger
    dev=[solver_case(c) for c in dataset['cases'] if c['scope']=='dev'];hold=[solver_case(c) for c in dataset['cases'] if c['scope']=='holdout']
    updates=config.get('test_checkpoint_updates',[1,2] if config.get('tiny_cpu') else PROTOCOL['checkpoint_updates']);cap=config.get('test_generation_cap',1024)
    session.checkpoint_schedule=checkpoint_schedule_for_run(config)
    names=['base']+['sft'+str(u) for u in updates]
    dev_rows={name:[_empty(c,'checkpoint not reached') for c in dev] for name in names}
    hold_rows={name:[_empty(c,'method not reached') for c in hold] for name in ('base','selected_sft')}
    error=None;selection=None;checkpoint=None;checkpoints={};training=[];main_complete=False
    ttt={'status':'TTT_NOT_RUN','reason':'main results incomplete','denominators':{'dev':8,'holdout':8},'rows':[]}
    public={'status':'PUBLIC_NOT_RUN','reason':'main results incomplete'}
    provenance={'protocol_sha256':digest(PROTOCOL),'plan_sha256':dataset['plan']['plan_sha256'],'task_balanced':True,'query_targets_used':False}
    records=[];main_timing=[];main_event_start=len(physical.events);main_sources=timing_sources()
    try:
        records,match=_native_admission(session.model,dataset['records'],dataset['plan']['train_ids'])
        atomic_json(root/'training-admission.json',match,exclusive=True)
        checkpoints['base']=save_branch_checkpoint(session.trainer,root/'checkpoint-assets',branch_id='global_grid',update=0,records=records,provenance=provenance,checkpoint_schedule=session.checkpoint_schedule)
        with session.model.adapter_branch('base'):evaluate_cases(session.model,dev,root/'dev'/'base',deadline,cap=cap,rows=dev_rows['base'],timing_sink=main_timing)
        previous=0
        for update in updates:
            if config.get('test_failure')=='before_train':raise RuntimeError('injected before_train')
            result=train_updates(session.trainer,records,update-previous,root/f'train-{update}.json',deadline);training.append(result)
            name='sft'+str(update);saved=save_branch_checkpoint(session.trainer,root/'checkpoint-assets',branch_id='global_grid',update=update,records=records,provenance=provenance,checkpoint_schedule=session.checkpoint_schedule)
            checkpoints[name]=saved;session.reload(saved,records,provenance,deadline)
            atomic_json(root/f'fresh-reload-{update}.json',session.reload_receipts[-1],exclusive=True)
            evaluate_cases(session.model,dev,root/'dev'/name,deadline,cap=cap,rows=dev_rows[name],timing_sink=main_timing);previous=update
        dev_seal=seal_scope(root,'dev',dataset,dev_rows)
        selection=select_sft(dataset,dev_seal,updates);checkpoint=checkpoints[selection['candidate_id']]
        selection['checkpoint']=checkpoint;selection['plan_sha256']=dataset['plan']['plan_sha256'];selection['selection_sha256']=digest(selection)
        atomic_json(root/'frozen-selection.json',selection,exclusive=True)
        public_selection=select_sft(dataset,dev_seal,updates,include_base=True)
        public_selection['checkpoint']=checkpoints[public_selection['candidate_id']]
        public_selection['plan_sha256']=dataset['plan']['plan_sha256'];public_selection['selection_sha256']=digest(public_selection)
        atomic_json(root/'public-selection.json',public_selection,exclusive=True)
        if selection['candidate_id']!=names[-1]:session.reload(checkpoint,records,provenance,deadline)
        with session.model.adapter_branch('base'):evaluate_cases(session.model,hold,root/'holdout'/'base',deadline,cap=cap,rows=hold_rows['base'],timing_sink=main_timing)
        evaluate_cases(session.model,hold,root/'holdout'/'selected-sft',deadline,cap=cap,rows=hold_rows['selected_sft'],timing_sink=main_timing)
        hold_seal=seal_scope(root,'holdout',dataset,hold_rows,selection=selection)
        main_complete=True
        atomic_json(root/'main-complete.json',{'complete':True,'dev_seal':dev_seal,'holdout_seal':hold_seal,'selection':selection},exclusive=True)
        atomic_json(root/'main-timing-boundaries.json',{'format':'irisx/transfer-main-timing-boundaries-v1',
            'source_sha256':main_sources,'main_event_start':main_event_start,'main_started_monotonic':start,
            'calls':main_timing},exclusive=True)
        refreshed,refresh_ref=freeze_public_refresh(root,updates=updates,calibration=session.calibration,
            original=feasibility['measurements'],ledger=physical,main_event_start=main_event_start,
            main_started=start,expected_sources=main_sources,tiny=config.get('tiny_cpu',False))
        public={'status':'PUBLIC_PARTIAL','reason':'public phase interrupted','cost_refresh':refresh_ref}
        public=run_public(session,config,public_selection,checkpoints[public_selection['candidate_id']],root/'public',deadline,refreshed['selected_measurements'],
            records=records,provenance=provenance,return_checkpoint=checkpoint,cap=cap,cost_refresh=refresh_ref)
        chosen=dataset['plan']['ttt_dev_ids']+dataset['plan']['ttt_holdout_ids'];stats=counts(dataset['cases'],chosen)
        cost=admission(forecast(feasibility['measurements'],updates=stats['training_updates'],generations=stats['generation_calls'],scores=stats['fold_scores'],tiny=config.get('tiny_cpu',False),generation_cap=cap),physical,deadline,tiny=config.get('tiny_cpu',False))
        eligible=all(len(c['demos'])>=2 for c in dataset['cases'] if c['parent_id'] in chosen)
        ttt.update(reason='fixture-skip-requested' if config.get('test_skip_ttt') else 'insufficient-visible-demonstrations' if not eligible else cost['reason'],forecast=cost,planned_counts=stats)
        if cost['admitted'] and eligible and not config.get('test_skip_ttt'):
            session.trainer.freeze_global();ttt['status']='TTT_PARTIAL';ttt['reason']=None
            for case in dataset['cases']:
                if case['parent_id'] in chosen:
                    ttt['rows'].append(run_ttt_case(session,case,checkpoint,root/'ttt'/case['parent_id'],deadline,cap=cap,
                        persist_representative=case['parent_id']==dataset['plan']['representative_ttt_parent']))
            require(len(ttt['rows'])==16,'TTT complete denominator')
            ttt['status']='TTT_COMPLETE'
    except Exception as exc:error={'type':type(exc).__name__,'message':str(exc)[:2048]}
    # Preserve main completion even when optional work fails. Every unseen query
    # stays an explicit abstention in the sealed fixed panel.
    if not (root/'dev-prediction-seal.json').exists():dev_seal=seal_scope(root,'dev',dataset,dev_rows)
    if not (root/'holdout-prediction-seal.json').exists():hold_seal=seal_scope(root,'holdout',dataset,hold_rows,selection=selection)
    chosen_ids=dataset['plan']['ttt_dev_ids']+dataset['plan']['ttt_holdout_ids'];byid={r['case_id']:r for r in ttt['rows']}
    ttt['rows']=[byid.get(c['case_id'],_empty(c,ttt['reason'] or 'TTT interrupted')) for c in dataset['cases'] if c['parent_id'] in chosen_ids]
    atomic_json(root/'ttt-predictions-sealed.json',ttt,exclusive=True)
    atomic_json(root/'checkpoint-receipts.json',checkpoints,exclusive=True)
    for name,saved in checkpoints.items():
        export_checkpoint_metadata(root,name,saved)
    report={'format':'irisx/true-arc-transfer-experiment-v1','status':'TRANSFER_COMPLETE' if main_complete else 'TRANSFER_PARTIAL',
        'science_complete':main_complete,'operational_success':main_complete and error is None,'error':error,
        'cpu_fixture_only':config.get('tiny_cpu',False),'denominators':dataset['denominators'],'main_complete':main_complete,
        'selection':selection,'dev_seal':dev_seal,'holdout_seal':hold_seal,'ttt':ttt,'public_branch':public,
        'physical_usage':dict(physical.used),'pending_work':deepcopy(physical.pending),'training_receipts':training,
        'fresh_backend_reload_receipts':session.reload_receipts,'checkpoints':checkpoints,'elapsed_seconds':time.monotonic()-start,
        'dataset_path':str((root.parent/'dataset'/'solver-dataset.json').absolute()),
        'ttt_predictions_path':str((root/'ttt-predictions-sealed.json').absolute()),'ttt_predictions_sha256':file_sha(root/'ttt-predictions-sealed.json'),
        'interpretation':'new to this Qwen experiment; historical-project/pretraining cleanliness not claimed',
        'compute_matched_comparison':False,'holdout_gold_opened':False,'public_gold_opened':False}
    atomic_json(root/'full-report.json',report,exclusive=True);return report


def _wilson(hits,n):
    z=1.959963984540054;p=hits/n;d=1+z*z/n
    mid=(p+z*z/(2*n))/d;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,mid-half),min(1,mid+half)]


def score_closed(dataset,report,owner_proof):
    from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof
    verify_closed_proof(owner_proof);require(owner_proof.get('closed') is True,'model owner must be closed before holdout scoring')
    result={}
    for scope in ('dev','holdout'):
        seal=report[scope+'_seal'];targets=open_targets(dataset,scope,seal);payload=checked_json(seal['path'],seal['file_sha256'])
        base={r['case_id']:r['answers'] for r in payload['methods']['base']}
        methods=dict(payload['methods'])
        ttt=checked_json(report['ttt_predictions_path'],report['ttt_predictions_sha256'])
        subset=[r for r in ttt['rows'] if r['case_id'].startswith(scope+':')]
        if subset:methods['selected_ttt_subset']=subset
        summaries={}
        for name,rows in methods.items():
            n=len(rows);hits=first_hits=valid=shape=gains=losses=0
            for row in rows:
                target=targets[row['case_id']];yes=any(p==target for p in row['answers']);reference=any(p==target for p in base[row['case_id']])
                hits+=yes;first_hits+=bool(row['answers'] and row['answers'][0]==target);valid+=bool(row['answers']);shape+=any(_shape(p,target) for p in row['answers']);gains+=yes and not reference;losses+=reference and not yes
            summaries[name]={'status':ttt['status'] if name=='selected_ttt_subset' else 'complete' if all(r['complete'] for r in rows) else 'partial','denominator':n,'pass_at_1_count':first_hits,'pass_at_1':first_hits/n,'pass_at_2_count':hits,'pass_at_2':hits/n,'wilson95':_wilson(hits,n),
                'valid_count':valid,'shape_correct_count':shape,'abstentions':n-valid,'paired_gains_vs_base':gains,'paired_losses_vs_base':losses}
        result[scope]=summaries
    return {'format':'irisx/transfer-after-owner-closure-scores-v1','scopes':result,'all_denominators_retained':True,'model_owner_closed':True,'public_score':None}
