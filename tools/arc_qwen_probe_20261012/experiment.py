"""Matched native branches, full logical resets, and monotone physical costs."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import math
import time
from .protocol import PROTOCOL,require,digest
from tools.arc_learning_agent_20261011.budget import atomic_json
from tools.arc_learning_agent_20261011.grid_codec import grid_messages,program_messages,decode_grid,encode_grid
from tools.arc_learning_agent_20261011.program_tools import verify_program,execute_queries
from tools.arc_learning_agent_20261011.qwen14b_probe import prepare_length_control,measure_cache_parity


def delta(before,after): return {k:after[k]-before[k] for k in after}

def active_profile(model):
    require(model.decoder_policy is not None,'science requires locked decoder policy')
    return model.decoder_policy['profile']

def _generation(model,messages,kind,deadline):
    if time.monotonic()>=deadline:
        return {'valid':False,'dispatched':False,'error':'probe deadline; no generation dispatched','text':'','output_token_ids':[]}
    fixture_caps=model.config.get('probe_fixture_generation_caps',{}) if model.config.get('tiny_cpu') is True else {}
    return model.generate(messages,kind=kind,seed=PROTOCOL['seed'],max_new_tokens=fixture_caps.get(kind,active_profile(model)[kind+'_output_cap']),deadline=deadline)

def _vm(ledger,event,operation):
    ledger.reserve(event,{'cpu_checks':1,'gas':200000})
    try:
        result=operation()
        ledger.complete(event,{'cpu_checks':int(result.get('receipt',result).get('dispatched',0)),
                               'gas':result['gas_charged']})
        return result
    except BaseException as exc:
        if event in ledger.pending: ledger.unknown(event,type(exc).__name__)
        raise

def _shape_equal(grid,target):
    return grid is not None and (len(grid),len(grid[0]))==(len(target),len(target[0]))

def evaluate(model,ledger,cases,output,label,deadline):
    """Every generation precedes any target-scoring call for this checkpoint."""
    root=Path(output)/label;root.mkdir(parents=True,exist_ok=False)
    began=time.monotonic(); before=dict(ledger.used);rows=[]
    for i,case in enumerate(cases):
        task={'train':deepcopy(case['demos']),'test':[{'input':deepcopy(case['query_input'])}]}
        grid_gen=_generation(model,grid_messages(task['train'],case['query_input']),'grid',deadline)
        atomic_json(root/('case-'+str(i)+'-grid-generation.json'),{'case_id':case['case_id'],'kind':'grid','generation':grid_gen})
        require(not grid_gen.get('fatal_error',False),'fatal grid generation in science')
        pred=None
        if grid_gen.get('valid'):
            try: pred=decode_grid(grid_gen['text'])
            except ValueError: pass
        program_gen=_generation(model,program_messages(task),'program',deadline)
        atomic_json(root/('case-'+str(i)+'-program-generation.json'),{'case_id':case['case_id'],'kind':'program','generation':program_gen})
        require(not program_gen.get('fatal_error',False),'fatal program generation in science')
        proof=query=None;program_pred=None
        if program_gen.get('valid') and time.monotonic()<deadline:
            # Shared ledger spans branches; labels alone are not unique.
            event='evaluation-'+digest(str(root.absolute()))+'-vm-'+str(i)
            proof=_vm(ledger,event,lambda:verify_program(program_gen['text'],task['train'],root/'vm',str(i)+'-demos',deadline=deadline))
            if proof['all_demos_fit'] and time.monotonic()<deadline:
                query=_vm(ledger,event+'-query',lambda:execute_queries(proof,[case['query_input']],root/'vm',str(i)+'-query',deadline=deadline))
                if query['results'] and query['results'][0]['status']=='valid':program_pred=query['results'][0]['output']
        rows.append({'case_id':case['case_id'],'scope':case['scope'],'grid_generation':grid_gen,'program_generation':program_gen,
            'grid_prediction':pred,'program_prediction':program_pred,'program_demo_proof':proof,'program_query_receipt':query,
            'grid_exact':pred==case['target'],'grid_shape_correct':_shape_equal(pred,case['target']),
            'program_all_demos_fit':bool(proof and proof['all_demos_fit']),'program_exact':program_pred==case['target'],
            'program_shape_correct':_shape_equal(program_pred,case['target'])})
    # Targets are used only by these diagnostic full-native-head scores; never fed to either generator.
    for i,(row,case) in enumerate(zip(rows,cases)):
        if time.monotonic()<deadline:
            row['grid_score']=model.score_completion(grid_messages(case['demos'],case['query_input']),encode_grid(case['target']),deadline=deadline)
        else:row['grid_score']={'valid':False,'dispatched':False,'error':'probe deadline; no teacher forcing dispatched'}
        atomic_json(root/('case-'+str(i)+'-score.json'),{'case_id':case['case_id'],'score':row['grid_score']},exclusive=True)
    summary={}
    for scope in ('authored_train_control','authored_disjoint_query','exposed_development'):
        selected=[r for r in rows if r['scope']==scope]
        scores=[r['grid_score'] for r in selected if r['grid_score'].get('valid')]
        tokens=sum(s['token_count'] for s in scores)
        expected_nll_ids=active_profile(model)['dev_nll_eligible_case_ids'] if scope=='exposed_development' else [r['case_id'] for r in selected]
        scored_ids=[r['case_id'] for r in selected if r['grid_score'].get('valid')]
        summary[scope]={'denominator':len(selected),'nll_expected_eligible_cases':len(expected_nll_ids),
            'nll_expected_eligible_case_ids':expected_nll_ids,'nll_scored_case_ids':scored_ids,
            'nll_matching_complete':set(scored_ids)==set(expected_nll_ids),'grid_exact':sum(r['grid_exact'] for r in selected),
            'grid_valid':sum(r['grid_prediction'] is not None for r in selected),
            'grid_shape_correct':sum(r['grid_shape_correct'] for r in selected),
            'program_exact':sum(r['program_exact'] for r in selected),
            'program_valid_query':sum(r['program_prediction'] is not None for r in selected),
            'program_all_demo_fit':sum(r['program_all_demos_fit'] for r in selected),
            'grid_generation_exclusions':sum(not r['grid_generation'].get('dispatched',False) for r in selected),
            'program_generation_exclusions':sum(not r['program_generation'].get('dispatched',False) for r in selected),
            'nll_scored_cases':len(scores),'nll_denominator_cases':len(selected),
            'nll_completion_tokens':tokens,'mean_nll':sum(s['nll_sum'] for s in scores)/tokens if tokens else None}
    result={'label':label,'rows':rows,'summary':summary,'physical_usage':delta(before,ledger.used),
            'elapsed_seconds':time.monotonic()-began,'deadline_exhausted':time.monotonic()>=deadline,
            'all_generations_precede_teacher_forcing':True,'generation_is_greedy':True,
            'same_native_tokenizer_all_branches':True,'public_accuracy_claim':False,
            'decoder_mode':model.decoder_policy['selected_mode'],'decoder_policy_sha256':model._decoder_policy_sha256,
            'science_profile':model.decoder_policy['selected_profile'],'profile_sha256':model.decoder_policy['profile_sha256']}
    atomic_json(root/'diagnostics.json',result,exclusive=True)
    require(all(x['nll_matching_complete'] for x in summary.values()),'incomplete profile NLL scoring; checkpoint inadmissible')
    return result

def semantic_behavior(observation):
    return [{k:r[k] for k in ('case_id','grid_prediction','program_prediction','grid_exact','program_exact','program_all_demos_fit')} |
            {'grid_output_token_ids':r['grid_generation'].get('output_token_ids'),
             'program_output_token_ids':r['program_generation'].get('output_token_ids'),
             'nll_sum':r['grid_score'].get('nll_sum'),'token_count':r['grid_score'].get('token_count')}
            for r in observation['rows']]

def rank(observation,update):
    s=observation['summary'];d=s['exposed_development'];t=s['authored_train_control']
    nll=d['mean_nll']
    if d['nll_scored_cases']!=d.get('nll_expected_eligible_cases',d['denominator']) or not d.get('nll_matching_complete',True) or nll is None or not math.isfinite(nll):
        return (-1,-math.inf,-update)
    return (d['grid_exact']+d['program_exact'],
            -(nll if nll is not None and d['nll_scored_cases']==d.get('nll_expected_eligible_cases',d['denominator']) else math.inf),-update)

def native_matching(model,records,cases):
    rows=[]
    for r in records:
        try:
            p=model.prepare_completion(r['messages'],r['completion'])
            rows.append({'record_id':r['record_id'],'kind':r['kind'],'family_id':r['family_id'],
                         'eligible':True,'prompt_tokens':p['prompt_tokens'],'completion_tokens':p['completion_tokens'],
                         'input_tokens':p['input_tokens'],'prepared_sha256':p['prepared_sha256']})
        except ValueError as exc:
            if 'context' not in str(exc).lower():raise
            rows.append({'record_id':r['record_id'],'kind':r['kind'],'family_id':r['family_id'],'eligible':False,'reason':str(exc)})
    prompts=[];targets=[]
    for c in cases:
        task={'train':c['demos'],'test':[{'input':c['query_input']}]}
        for kind,messages in (('grid',grid_messages(c['demos'],c['query_input'])),('program',program_messages(task))):
            try:
                _,ids=model._prompt(messages)
                prompts.append({'case_id':c['case_id'],'kind':kind,'eligible':len(ids)+active_profile(model)[kind+'_output_cap']<=model.context_limit,
                                'prompt_tokens':len(ids),'generation_reservation':active_profile(model)[kind+'_output_cap'],'prompt_sha256':digest(messages)})
            except ValueError as exc:
                if 'context' not in str(exc).lower():raise
                prompts.append({'case_id':c['case_id'],'kind':kind,'eligible':False,'reason':str(exc),'prompt_sha256':digest(messages)})
        messages=grid_messages(c['demos'],c['query_input']);rendered,prefix=model._prompt(messages)
        completed=model.tokenizer.encode(rendered+encode_grid(c['target']),add_special_tokens=False)
        require(completed[:len(prefix)]==prefix,'native target tokenization boundary differs')
        counts=[len(prefix),len(completed)-len(prefix)+1,len(completed)+1]
        eligible=counts[1]<=256 and counts[2]<=2048 and counts[0]<=1792
        if c['scope']=='exposed_development':
            require(counts==PROTOCOL['dev_native_lengths'][c['case_id']],'predeclared native dev lengths differ')
            require(eligible==(c['case_id'] in active_profile(model)['dev_nll_eligible_case_ids']),'predeclared NLL eligibility differs')
        targets.append({'case_id':c['case_id'],'prompt_tokens':counts[0],'target_tokens_including_eos':counts[1],
            'combined_tokens':counts[2],'teacher_forcing_eligible':eligible,'direct_grid_target_representable_under_cap':counts[1]<=active_profile(model)['grid_output_cap'] and counts[2]<=2048 and counts[0]<=1792,
            'active_grid_generation_cap':active_profile(model)['grid_output_cap'],
            'exclusion':None if eligible else 'whole native completion exceeds fixed256cap; no truncation'})
    return {'training_records':rows,'target_representability':targets,'predeclared_dev_nll_eligible_case_ids':active_profile(model)['dev_nll_eligible_case_ids'],'evaluation_prompts':prompts,'full_training_denominator':len(records),
            'full_evaluation_case_denominator':len(cases),'tokenizer_identity':model.identity,
            'matching':'identical examples, masks and native tokenizer across base/grid/program; actual branch completion tokens differ'}

def run_ladder(model,trainer,ledger,output,deadline,*,atol=0.01,rtol=0.01):
    from .cache_policy import token_cache_panel,CACHE_POLICY
    import torch
    require(atol==.01 and rtol==.01,'unchanged diagnostic tolerance required')
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    initial=trainer.snapshot_training_state('before-memory-ladder');raw=trainer.trainer
    prompt=[{'role':'user','content':'Return the digit 1.'}];observations=[]
    cuda=next(model.model.parameters()).device.type=='cuda'
    try:
        for length in PROTOCOL['length_ladder']:
            item={'length':length,'status':'running','states':{},'update':None,'full_state_reset_exact':False}
            path=root/('length-'+str(length)+'.json');atomic_json(path,item)
            before=dict(ledger.used);start=time.monotonic();event='ladder-'+str(length)
            try:
                require(time.monotonic()<deadline,'memory ladder deadline')
                trainer.restore_training_state(initial);row=prepare_length_control(model,length)
                if cuda:torch.cuda.reset_peak_memory_stats(0)
                item.update(prompt_tokens=row['prompt_tokens'],completion_tokens=row['completion_tokens'],prepared_sha256=row['prepared_sha256'])
                def observe(suffix):
                    state={'status':'running','cache_receipt_path':str(length)+'-'+suffix+'-cache.json'}
                    item['states'][suffix]=state;atomic_json(path,item)
                    cache=token_cache_panel(model,ledger,row['input_ids'],event+'-'+suffix,deadline,root/state['cache_receipt_path'])
                    state['cache']=cache;atomic_json(path,item)
                    generation=model.generate(prompt,kind='grid',seed=0,max_new_tokens=8,deadline=deadline)
                    state['generation']=generation;atomic_json(path,item)
                    score=model.score_completion(prompt,'1',deadline=deadline)
                    state['score']=score;atomic_json(path,item)
                    require(generation.get('dispatched') and generation.get('output_tokens',0)>0 and generation.get('finish_reason') in ('eos','length') and score.get('valid'),'memory ladder reference generation/scoring failed')
                    state['status']='complete';atomic_json(path,item)
                    return state
                with model.adapter_branch('base'):baseline=observe('base')
                try:
                    ledger.reserve(event,{'training_steps':1,'input_tokens':length})
                    t=time.monotonic();raw._make_optimizer();update=raw._step(row)
                    if cuda:torch.cuda.synchronize(0)
                    completed=time.monotonic()
                    ledger.complete(event,{'training_steps':1,'input_tokens':length})
                    item['update']={**update,'started_monotonic':t,'completed_monotonic':completed,
                        'elapsed_seconds':completed-t,'deadline_monotonic':deadline,'late':completed>=deadline,'input_tokens':length,'event_id':event}
                    atomic_json(path,item)
                    require(completed<deadline,'late memory update charged but rung inadmissible')
                    after=observe('updated')
                except BaseException as exc:
                    if event in ledger.pending:ledger.unknown(event,type(exc).__name__)
                    raise
                finally:
                    item['reset']=trainer.restore_training_state(initial);atomic_json(path,item)
                restored=observe('restored')
                require(baseline['generation']['output_token_ids']==restored['generation']['output_token_ids'] and baseline['score']['nll_sum']==restored['score']['nll_sum'],'exact memory-ladder reference behavior restoration failed')
                check=trainer.snapshot_training_state('ladder-reset-check')
                try:
                    item['initial_state_sha256']=initial['state_sha256'];item['restored_state_sha256']=check['state_sha256']
                    require(check['state_sha256']==initial['state_sha256'],'full ladder state differs')
                finally:trainer.release_training_state(check)
                require(time.monotonic()<deadline,'late full-state reset analysis')
                item.update(full_state_reset_exact=True,status='complete')
                if cuda:item.update(peak_allocated_bytes=int(torch.cuda.max_memory_allocated(0)),peak_reserved_bytes=int(torch.cuda.max_memory_reserved(0)))
            except BaseException as exc:
                item.update(status='fatal',error=type(exc).__name__+': '+str(exc)[:512]);raise
            finally:
                item.update(physical_usage=delta(before,ledger.used),elapsed_seconds=time.monotonic()-start)
                atomic_json(path,item)
            observations.append(item)
    finally:
        try:trainer.restore_training_state(initial)
        finally:trainer.release_training_state(initial)
    panels=[s['cache'] for r in observations for s in r['states'].values()]
    return {'format':'irisx/qwen14b-cache-ladder-v2','status':'complete','completed_lengths':[r['length'] for r in observations],
        'observations':observations,'full_context_measured':cuda and len(observations)==3,
        'strict_numerical_allclose':all(p['strict_numerical_allclose'] for p in panels),
        'behavioral_cache_admitted':all(p['behavioral_cache_admitted'] for p in panels),
        'cache_policy_sha256':digest(CACHE_POLICY),'cpu_fixture_only':not cuda,'public_admission':False}

def run_experiment(model,trainer,ledger,dataset,output,deadline,*,feasibility,checkpoints=None,fail_before_train=False):
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    from .science_profiles import BranchLedger,SELECTABLE_PROFILES
    require(model.decoder_policy['selected_profile'] in SELECTABLE_PROFILES,'science restricted to preregistered13-case pilots')
    checkpoints=checkpoints or active_profile(model)['checkpoint_updates'];raw=trainer.trainer
    global_deadline=deadline;physical_ledger=ledger
    candidate=feasibility['candidates'][model.decoder_policy['selected_profile']]
    identity={'science_profile':model.decoder_policy['selected_profile'],'decoder_mode':model.decoder_policy['selected_mode'],
              'decoder_policy_sha256':model._decoder_policy_sha256,'profile_sha256':model.decoder_policy['profile_sha256']}
    atomic_json(root/'branch-allowances.json',{'grid_lora':{'seconds':candidate['per_branch_allowance_seconds'],'input_tokens':candidate['per_branch_allowance_input_tokens']},
               'program_lora':{'seconds':candidate['per_branch_allowance_seconds'],'input_tokens':candidate['per_branch_allowance_input_tokens']},'budget_transfer_allowed':False},exclusive=True)
    matching=native_matching(model,dataset['records'],dataset['cases'])
    atomic_json(root/'native-matching.json',matching,exclusive=True)
    state_identity={'model':raw._base_identity,'config':raw.config,'source':raw._source_identity()}
    atomic_json(root/'science-state-identity.json',{**state_identity,'identity_sha256':digest(state_identity),**identity},exclusive=True)
    original=trainer.snapshot_training_state('clean-initial-state');branches={};handles=[];science_complete=False
    before_all=dict(ledger.used)
    try:
        with model.adapter_branch('base'):
            representation=representation_probe(model,ledger,dataset['cases'],deadline,root/'base-representation-calls') if active_profile(model)['base_representation'] else {'status':'not_in_pilot_profile','rows':[],'denominator':0,'used_for_adapter_selection':False}
            base=evaluate(model,ledger,dataset['cases'],root,'frozen-base',deadline)
        for item,compact in zip(representation['rows'],base['rows']):
            item['compact_reference']={'prompt_sha256':digest(grid_messages(next(c for c in dataset['cases'] if c['case_id']==item['case_id'])['demos'],next(c for c in dataset['cases'] if c['case_id']==item['case_id'])['query_input'])), 'generation':compact['grid_generation'],'prediction':compact['grid_prediction'],'shape_correct':compact['grid_shape_correct'],'exact':compact['grid_exact']}
        atomic_json(root/'base-representation.json',representation,exclusive=True)
        require(not base['deadline_exhausted'],'base panel did not complete before deadline')
        require(rank(base,0)[0]>=0,'fixed tokenizer-eligible baseline NLL panel incomplete')
        from .science_profiles import paired_admission
        paired=paired_admission(candidate,feasibility,global_deadline,time.monotonic())
        atomic_json(root/'paired-admission.json',paired,exclusive=True)
        require(paired['admitted'],'common panel overran forecast; equal paired allocations no longer fit')
        for branch,kind in (('grid_lora','grid'),('program_lora','program')):
            branch_root=root/branch;branch_root.mkdir()
            trainer.restore_training_state(original)
            branch_check=trainer.snapshot_training_state(branch+'-initial')
            require(branch_check['state_sha256']==original['state_sha256'],'branch initial optimizer/scheduler/RNG/counters differ')
            trainer.release_training_state(branch_check)
            ledger=BranchLedger(physical_ledger,input_tokens=candidate['per_branch_allowance_input_tokens'],seconds=candidate['per_branch_allowance_seconds'],name=branch)
            model.ledger=trainer.ledger=ledger;deadline=min(global_deadline,ledger.deadline)
            branch_before=dict(ledger.used);started=time.monotonic();receipts=[];observations={0:base}
            records=[r for r in dataset['records'] if r['kind']==kind]
            require(records and all(r['split']=='train' for r in records),'train-only branch records required')
            best=original;best_update=0;early=final=None;updates=0;completion_tokens=0
            try:
                if fail_before_train:raise RuntimeError('injected before_train boundary')
                for target in checkpoints:
                    require(time.monotonic()<deadline,'branch training deadline')
                    # Accumulation has one microbatch, so the ceiling is also an optimizer ceiling.
                    receipt=train_checkpoint(trainer,records,target-updates,deadline,branch_root/('training-'+str(target)+'.json'))
                    receipts.append(receipt);updates+=receipt['optimizer_steps'];completion_tokens+=receipt['supervised_tokens']
                    require(updates<=PROTOCOL['maximum_updates_per_branch'] and completion_tokens<=32768,'branch physical training cap exceeded')
                    require(time.monotonic()<deadline,'late optimizer work charged; checkpoint is inadmissible')
                    require(receipt['status']=='complete' and updates==target,'incomplete branch checkpoint')
                    snap=trainer.snapshot_training_state(branch+'-'+str(updates));handles.append(snap)
                    observation=evaluate(model,ledger,dataset['cases'],branch_root,'update-'+str(updates),deadline)
                    require(not observation['deadline_exhausted'],'incomplete checkpoint panel')
                    observations[updates]=observation
                    if early is None:early=snap
                    if rank(observation,updates)>rank(observations[best_update],best_update):best,best_update=snap,updates
                    final=snap
                selected_before=dict(ledger.used)
                selected=trainer.restore_training_state(best)
                replay=evaluate(model,ledger,dataset['cases'],branch_root,'selected-restore',deadline)
                require(not replay['deadline_exhausted'],'selected replay did not complete')
                require(semantic_behavior(replay)==semantic_behavior(observations[best_update]),'selected native generation/NLL replay differs')
                state_check=trainer.snapshot_training_state(branch+'-selected-check')
                try:require(state_check['state_sha256']==best['state_sha256'],'selected full optimizer/scheduler/RNG/counters differ')
                finally:trainer.release_training_state(state_check)
                branches[branch]={'status':'complete',**identity,'branch_budget':ledger.receipt(),'science_complete':True,'objective':kind,'initial_state_sha256':original['state_sha256'],
                    'early':early,'best':best,'final':final,'best_update':best_update,'optimizer_updates':updates,
                    'completion_tokens':completion_tokens,'training_receipts':receipts,
                    'selection_status':'selected-on-source-declared-profile-exact-and-eligible-NLL' if rank(observations[best_update],best_update)[0]>=0 else 'inconclusive-default-frozen-base',
                    'checkpoint_summaries':{str(k):v['summary'] for k,v in observations.items()},
                    'restore':selected,'selected_replay_exact':True,'selected_replay_cost':delta(selected_before,ledger.used),
                    'physical_usage':delta(branch_before,ledger.used),'elapsed_seconds':time.monotonic()-started}
                atomic_json(branch_root/'branch-report.json',branches[branch],exclusive=True)
            except BaseException as exc:
                atomic_json(branch_root/'incomplete-branch.json',{'status':'incomplete','science_complete':False,**identity,
                    'error':type(exc).__name__+': '+str(exc)[:512],'branch_budget':ledger.receipt(),
                    'fully_evaluated_checkpoint_updates':sorted(observations),'training_receipts':receipts},exclusive=True)
                raise
            finally:
                trainer.restore_training_state(original)
                for handle in handles:trainer.release_training_state(handle)
                handles.clear()
                ledger=physical_ledger;model.ledger=trainer.ledger=physical_ledger;deadline=global_deadline
        restored=evaluate(model,ledger,dataset['cases'],root,'final-clean-restore',deadline)
        require(not restored['deadline_exhausted'] and semantic_behavior(restored)==semantic_behavior(base),'final clean-base behavior differs')
        check=trainer.snapshot_training_state('final-clean-check')
        try:require(check['state_sha256']==original['state_sha256'],'final full logical state differs')
        finally:trainer.release_training_state(check)
        report={'format':'irisx/qwen14b-native-learning-probe-v2','status':'PROBE_PILOT_COMPLETE',
            **identity,'science_complete':True,'operational_success':True,
            'selected_case_ids':dataset['selected_case_ids'],'omitted_case_ids':dataset['omitted_case_ids'],
            'strict_numerical_allclose':model.decoder_policy['strict_numerical_allclose'],
            'bounded_empirical_cache_fidelity':model.decoder_policy['bounded_empirical_cache_fidelity'],
            'cache_fidelity_scope':model.decoder_policy['claim'],
            'decoder_policy':model.decoder_policy,'feasibility':feasibility,
            'protocol':PROTOCOL,'protocol_sha256':digest(PROTOCOL),'base_representation_comparison':representation,'native_matching':matching,'baseline':base['summary'],'branches':branches,
            'denominators':dataset['denominators'],'physical_usage':delta(before_all,ledger.used),
            'final_clean_reset_exact':True,'branch_work_matched_by':'same examples and optimizer-update ceilings; actual tokens/time reported separately',
            'public_solving_admitted':False,'public_score':None,'confirmation_evaluated':False,'ttt_executed':False,
            'checkpoint_selection_is_development_exposed':True,'production_effectiveness_gate_changed':False}
        atomic_json(root/'full-report.json',report,exclusive=True)
        science_complete=True
        return report
    finally:
        try:
            cleanup_reset=trainer.restore_training_state(original)
            atomic_json(root/'cleanup-restore.json',{'restore':cleanup_reset,**identity,'science_complete':science_complete})
        finally:
            for handle in handles:trainer.release_training_state(handle)
            trainer.release_training_state(original)

def dimensional_messages(case):
    """Base-only input representation diagnostic. Output language stays compact."""
    def shown(grid):
        return 'Rows: '+str(len(grid))+'; columns: '+str(len(grid[0]))+'\n'+'\n'.join(' '.join(map(str,r)) for r in grid)
    demos='\n\n'.join('Demonstration '+str(i+1)+'\nInput:\n'+shown(p['input'])+'\nOutput:\n'+shown(p['output']) for i,p in enumerate(case['demos']))
    messages=grid_messages(case['demos'],case['query_input'])
    return [messages[0],{'role':'user','content':demos+'\n\nQuery\nInput:\n'+shown(case['query_input'])+'\nOutput (compact digits, newline between rows; no spaces):'}]

def representation_probe(model,ledger,cases,deadline,output):
    before=dict(ledger.used);rows=[]
    for case in cases:
        messages=dimensional_messages(case);r=_generation(model,messages,'grid',deadline);pred=None
        atomic_json(Path(output)/(case['case_id'].replace(':','-')+'.json'),{'case_id':case['case_id'],'generation':r},exclusive=True)
        require(not r.get('fatal_error',False),'fatal representation generation')
        if r.get('valid'):
            try:pred=decode_grid(r['text'])
            except ValueError:pass
        rows.append({'case_id':case['case_id'],'scope':case['scope'],'representation':'explicit-dimensions-cell-delimited-input',
                     'prompt_sha256':digest(messages),'generation':r,'prediction':pred,
                     'shape_correct':_shape_equal(pred,case['target']),'exact':pred==case['target']})
    return {'format':'irisx/qwen14b-base-representation-diagnostic-v1','rows':rows,'denominator':len(cases),
            'physical_usage':delta(before,ledger.used),'used_for_adapter_selection':False,'changes_training_representation':False,
            'requested_output':'unchanged compact digits/newlines/native EOS/max256','additional_generation_call_ceiling':16}

def train_checkpoint(trainer,records,steps,deadline,path):
    """Persist actual work even when a late/failed return cannot become a checkpoint."""
    try:
        receipt=trainer.train(records,max_steps=steps,deadline=deadline)
    except BaseException as exc:
        failed=getattr(exc,'receipt',None)
        if failed is not None:
            policy=trainer.native.decoder_policy
            atomic_json(path,{'checkpoint_admissible':False,'failure_receipt':failed,
                'decoder_policy_sha256':trainer.native._decoder_policy_sha256,'decoder_mode':policy['selected_mode'],
                'science_profile':policy['selected_profile'],'profile_sha256':policy['profile_sha256']},exclusive=True)
        raise
    late=time.monotonic()>=deadline
    policy=trainer.native.decoder_policy
    result={**receipt,'decoder_policy_sha256':trainer.native._decoder_policy_sha256,'decoder_mode':policy['selected_mode'],
        'science_profile':policy['selected_profile'],'profile_sha256':policy['profile_sha256'],'completed_after_deadline':late,'checkpoint_admissible':not late and receipt.get('status')=='complete'}
    atomic_json(path,result,exclusive=True)
    require(not late,'late optimizer work charged; checkpoint is inadmissible')
    return result
