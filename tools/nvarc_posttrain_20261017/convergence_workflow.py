"""Executable bounded official2B convergence and paired held-demo evaluation.

No network, provider, PUBLIC prediction/scorer or automatic next experiment.
The CLI is an explicit local execution entrypoint, not a replacement for owned
worker/source-closure admission in a provider package. Its original absolute
session deadline must be supplied by the caller; no resumed clock is invented.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
from pathlib import Path
import random
import shutil
import time

import torch

from tools.arc2_goal_sprint_20261017.data import canonical, digest, load_data, loo_example
from tools.arc2_goal_sprint_20261017.launch import (
    TRAINING_MANIFEST_SHA256, SOLVER_MANIFEST_SHA256, require, verify_inventory, write_new,
)
from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, adapter_state, check_deadline, state_digest
from tools.arc2_goal_sprint_20261017.run import Audit, atomic_json
from . import convergence as cv, matched_controls as mc, matched_workflow as mw
from .codec import encode_example
from .engine import CompactEngine, FatalUpdateError
from .experiment import adapt_task, infer_query
from .materials import verify_model
from .precision_contract import LEGACY_POLICY, FP32_HEAD_POLICY
from .stability import RESET_PROBE_ATOL, RESET_PROBE_RTOL, verify_prediction

PROTOCOL = 'compact-convergence-screen-v1'
FORMAT = 'irisx/compact-convergence-workflow-v1'
WINDOW_EVIDENCE_LIMIT_BYTES = 32 * 1024**2
DEFAULT_EVALUATION = {'views': 2, 'ttt_steps': 32, 'ttt_lr': 5e-5, 'evaluation_seed': 20261018}


def prepare_panels(*args, **kwargs):
    """Reuse independently pinned train-only source and all heldout exclusions.

    This first executable screen deliberately keeps the existing16-parent bound.
    No claim that these syntactic groups cover semantic families or that four
    updates establish efficacy. A broader prospective panel is a distinct trial.
    """
    return mw.prepare_panels(*args, **kwargs)


def _json_training(result, artifacts):
    return {**{k: v for k,v in result.items() if k not in ('states','windows')},
        'state_sha256': {k: state_digest(v) for k,v in result['states'].items()},
        'windows': [{k:v for k,v in w.items() if k not in ('capture','preflight','verification')}
            | {'verification': {k: v for k, v in w['verification'].items() if k not in ('rows', 'failed_row')}
               | {'failed_row': None if not w['verification'].get('failed_row') else
                   {k: v for k, v in w['verification']['failed_row'].items() if k != 'replay_log_probs'}},
               'capture_sha256': w['capture']['seal_sha256'], 'policy_sha256': w['capture']['lineage']['policy_sha256'],
               'preflight_passed': (w.get('preflight') or {}).get('passed'),
               'artifact': artifacts.get('windows/'+w['window_id']+'.json')} for w in result['windows']]}


def _evaluation(config):
    cfg=copy.deepcopy(DEFAULT_EVALUATION if config is None else config)
    mc._schema(cfg,DEFAULT_EVALUATION,'convergence evaluation')
    require(type(cfg['views']) is int and cfg['views']==2,'identical fixed two-view treatments required')
    require(type(cfg['ttt_steps']) is int and 1<=cfg['ttt_steps']<=32,'bounded positive TTT steps required')
    require(type(cfg['evaluation_seed']) is int and 0<=cfg['evaluation_seed']<2**63,'bounded evaluation seed required')
    require(type(cfg['ttt_lr']) in (int,float) and math.isfinite(cfg['ttt_lr']) and 0<cfg['ttt_lr']<=1e-3,'bounded TTT LR required')
    return cfg


def run_workflow(engine, prepared, *, deadline, training_deadline, output, source_identity,
                 config=None, evaluation=None, audit=lambda *args,**kwargs: None, job_id='2b-S'):
    """Five same-anchor recipes, fixed complete dev denominator, paired0/32TTT.

    Checkpoint selection uses noTTT generated exact pass@2 only, after EVERY
    declared arm and paired treatment completes. Unique strict improvement or
    retain anchor; TTT comparisons never choose weights or change this protocol.
    Missing/incomplete rows retain denominator16 and an unknown full-panel score.
    """
    require(type(engine) is CompactEngine,'actual admitted compact engine required')
    cfg=cv.validate_config(config); ev=_evaluation(evaluation)
    require(all(type(v) in (int,float) and math.isfinite(v) for v in (deadline,training_deadline))
        and training_deadline<deadline,'finite original deadlines and evaluation/closure reserve required')
    require(mc._is_sha(source_identity),'independently identified source SHA required')
    if engine.contract['variant']!='tiny':
        require(cfg==cv.DEFAULT_CONFIG and ev==DEFAULT_EVALUATION,'official screen settings are fixed')
    require(job_id=='2b-S','one owned official2B work slot required')
    mw._validate_prepared(prepared)
    require(prepared['protocol'].get('probability_policy',LEGACY_POLICY)==engine.probability_policy,
        'declared numerical policy differs from actual convergence engine')
    prepared=copy.deepcopy(prepared); output=Path(output)
    require(not output.exists() or not any(output.iterdir()),'new empty convergence destination required')
    output.mkdir(parents=True,exist_ok=True); (output/'windows').mkdir()
    anchor=adapter_state(engine.model); anchor_sha=state_digest(anchor); policy_sha=mc.full_policy_sha256(engine)
    started=time.monotonic(); mode=engine.model.training
    ids=prepared['protocol']['development_parent_ids']; denominator=len(ids)
    bytes_per_state=sum(t.numel()*t.element_size() for t in anchor.values())
    disk_required=6*bytes_per_state+1024**3
    require(shutil.disk_usage(output).free>=disk_required,'five exports plus staging and1GiB evidence reserve required')
    protocol={'version':PROTOCOL,'source_panel_protocol_sha256':prepared['pins']['protocol_sha256'],
        'source_binding_sha256':prepared['pins']['source_binding_sha256'],
        'training_admission_sha256':prepared['pins']['admission_sha256'],
        'arms':list(cv.ARMS),'schedules':{a:list(s) for a,s in cv.SCHEDULES.items()},
        'training_config':cfg,'training_bounds':cv.physical_bounds(cfg),'loss_contract':cv.LOSS_CONTRACT,
        'evaluation':ev,'development_parent_ids':ids,
        'development_target_digests':prepared['protocol']['development_target_digest'],
        'development_task_sha256':prepared['protocol']['development_task_sha256'],
        'full_requested_denominator':denominator,'paired_treatments':['no_ttt','ttt'],
        'requested_view_generations':len(cv.ARMS)*denominator*2*ev['views'],
        'maximum_ttt_optimizer_attempts':len(cv.ARMS)*denominator*ev['ttt_steps'],
        'selection_rule':'all five recipes and all paired treatments complete; unique strict noTTT generated-exact-pass2 improvement over anchor, otherwise retain anchor',
        'ttt_factor_use':'paired mechanism diagnostic only; no TTT-based weight selection',
        'same_data_control_scope':'first optimizer slot only; subsequent fresh policy windows diverge',
        'public_feedback_used':False,'initial_weight_cleanliness_claimed':False,'efficacy_claimed':False,
        'equal_compute_claimed':False,'capacity_treatment':getattr(engine,'capacity_receipt',None),
        'probability_policy':getattr(engine,'probability_policy','legacy-unrepaired'),
        'source_identity':source_identity,'job_id':job_id}
    write_new(output/'protocol.json',protocol); write_new(output/'panel-admission.json',prepared['admission'])
    write_new(output/'source-binding.json',prepared['source_binding'])
    write_new(output/'source-panel-protocol.json',prepared['protocol'])
    write_new(output/'training-panel.json',prepared['training'])
    write_new(output/'development-panel.json',prepared['development'])
    artifacts={name:mw._file(output/name,output) for name in ('protocol.json','panel-admission.json','source-binding.json','source-panel-protocol.json','training-panel.json','development-panel.json')}
    cells={arm:{t:{'complete':False,'full_requested_denominator':denominator,'pass1':None,'pass2':None,
        'observed_pass1':0,'observed_pass2':0,'completed_parents':0,
        'records':[{'parent_id':p,'complete':False,'status':'not_executed','pass1':None,'pass2':None,
            'target_digest':protocol['development_target_digests'][p]} for p in ids]} for t in ('no_ttt','ttt')} for arm in cv.ARMS}
    report={'format':FORMAT,'status':'running','complete':False,'protocol_sha256':mc._sha(protocol),
        'anchor_state_sha256':anchor_sha,'anchor_policy_sha256':policy_sha,'training':None,'evaluation':cells,
        'exports':{arm:{'status':'not_executed'} for arm in cv.ARMS},'paired_ttt':{},
        'selected_arm':'anchor','candidate_selected':False,'selection_label':'retain-anchor','anchor_restored':False,
        'full_requested_denominator':denominator,'private_artifacts':artifacts,
        'source_identity':source_identity,'job_id':job_id,'training_deadline_epoch':training_deadline,'deadline_epoch':deadline,
        'disk_admission':{'state_bytes':bytes_per_state,'required_bytes':disk_required},
        'public_predictions_performed':False,'public_answers_used':False,'public_scoring_performed':False,
        'equal_compute_claimed':False,'efficacy_claimed':False,'capacity_gain_claimed':False,
        'limitation':'Small inherited-exposure held-demo screen; neither clean generalization nor provider-owned execution proof.'}
    training_result=None; primary=None
    def persist():
        require(len(canonical(report))<=4*1024**2,'bounded4MiB convergence summary required')
        atomic_json(output/'report.json',report)
    def persist_window(window):
        raw=canonical(window)
        require(len(raw)<=WINDOW_EVIDENCE_LIMIT_BYTES,'bounded32MiB per-window evidence required')
        path=output/'windows'/(window['window_id']+'.json')
        atomic_json(path,window); artifacts[path.relative_to(output).as_posix()]=mw._file(path,output)
    def persist_training(result):
        report['training']=_json_training(result,artifacts); persist()
    def summarize():
        for arm in cv.ARMS:
            for cell in cells[arm].values():
                rows=cell['records']; done=[r for r in rows if r['complete']]
                cell['completed_parents']=len(done); cell['complete']=len(done)==denominator
                cell['observed_pass1']=sum(r['pass1'] or 0 for r in rows)
                cell['observed_pass2']=sum(r['pass2'] or 0 for r in rows)
                cell['pass1']=cell['observed_pass1'] if cell['complete'] else None
                cell['pass2']=cell['observed_pass2'] if cell['complete'] else None
    meter=mc._Meter(engine); before=meter.snapshot()
    try:
        persist()
        training_result=cv.run_training(engine,prepared['training'],prepared['admission'],
            expected_admission_sha256=prepared['pins']['admission_sha256'],deadline=training_deadline,
            config=cfg,persist=persist_training,persist_window=persist_window)
        require(training_result['anchor_restored'] and not engine._fatal_update,'healthy exact restored training anchor required')
        params={**ev,'context_tokens':cfg['collection']['context_tokens'],
            'generation_tokens':cfg['collection']['generation_tokens'],'retain_token_evidence':True}
        for arm in cv.ARMS:
            state=training_result['states'].get(arm)
            if state is None: continue
            state_sha=state_digest(state)
            check_deadline(deadline); cv.reset(engine,state,state_sha)
            checkpoint=engine.save_checkpoint(output/'checkpoints'/arm,origin={'phase':'pre_public',
                'public_ttt_applied':False,'public_labels_used':False,'workflow':PROTOCOL,'arm':arm,
                'source_identity':source_identity,'job_id':job_id,'protocol_sha256':report['protocol_sha256'],
                'selected':False,'multi_update_screen':True})
            require(checkpoint['state_sha256']==state_sha,'exported exact state differs')
            report['exports'][arm]={'status':'complete','checkpoint':checkpoint}; cv.reset(engine,anchor,anchor_sha); persist()
            for index,parent in enumerate(ids):
                task=prepared['development'][parent]
                demos,query,target=loo_example(task,random.Random(0),augment=False,held_index=0)
                demo_task={'train':demos}
                held_probe=encode_example(demos,query,target,context=params['context_tokens'],generation=params['generation_tokens'])
                check_deadline(deadline); cv.reset(engine,state,state_sha)
                nll_before=engine.nll(held_probe)
                require(math.isfinite(nll_before),'finite no-gradient restoration probe required')
                for treatment in ('no_ttt','ttt'):
                    row=cells[arm][treatment]['records'][index]
                    phase_before,phase_started=meter.snapshot(),time.monotonic()
                    try:
                        check_deadline(deadline); cv.reset(engine,state,state_sha)
                        row.update(status='running',starting_state_sha256=state_sha)
                        if treatment=='ttt':
                            row['adaptation']=adapt_task(engine,demo_task,params,task_id=parent,steps=ev['ttt_steps'],deadline=deadline,audit=audit)
                            row['adaptation']['held_target_used_for_gradient']=False
                            if not row['adaptation']['all_requested_complete']:
                                raise PhaseDeadline('incomplete declared demo-only TTT steps')
                        prediction=infer_query(engine,demo_task,query,params,task_id=parent,views=ev['views'],deadline=deadline)
                        verification=verify_prediction(prediction,demo_task,query,params,task_id=parent,views=ev['views'])
                        ranked=prediction['ranked_grids']; row['ending_state_sha256']=state_digest(adapter_state(engine.model))
                        if treatment=='no_ttt':
                            require(row['ending_state_sha256']==state_sha,'noTTT generation changed trainables')
                        path=output/'predictions'/arm/treatment/(parent+'.json'); path.parent.mkdir(parents=True,exist_ok=True)
                        write_new(path,prediction); artifact=mw._file(path,output); artifacts[artifact['path']]=artifact
                        row.update(prediction_artifact=artifact,verification=verification,
                            pass1=int(bool(ranked) and ranked[0]==target),pass2=int(target in ranked),
                            complete=prediction['complete'],status='complete' if prediction['complete'] else 'partial')
                        if not prediction['complete']: raise PhaseDeadline('incomplete fixed held-demo views')
                        if treatment=='ttt':
                            row.update(complete=False,status='awaiting_functional_reset')
                    except BaseException as error:
                        row.update(complete=False,status='deadline' if isinstance(error,PhaseDeadline) else 'failed',error=type(error).__name__)
                        raise
                    finally:
                        cv.reset(engine,state,state_sha)
                        row['reset_state_sha256']=state_sha
                        engine.sync()
                        row.update(physical=mc._delta(meter.snapshot(),phase_before),wall_seconds=time.monotonic()-phase_started)
                        summarize(); persist()
                ttt_row=cells[arm]['ttt']['records'][index]
                try:
                    restored=engine.nll(held_probe)
                    require(math.isfinite(restored),'finite restored no-gradient probe required')
                    tolerance=RESET_PROBE_ATOL+RESET_PROBE_RTOL*max(abs(nll_before),abs(restored))
                    reset_ok=abs(restored-nll_before)<=tolerance
                    ttt_row['functional_reset']={'verified':reset_ok,'nll_before':nll_before,
                        'nll_restored':restored,'tolerance':tolerance,'held_probe_used_for_gradient':False}
                    require(reset_ok,'restored held-target no-gradient probe drift denies paired comparison')
                except BaseException as error:
                    ttt_row.update(complete=False,status='failed_functional_reset',error=type(error).__name__)
                    ttt_row.setdefault('functional_reset',{'verified':False,'nll_before':nll_before,
                        'nll_restored':None,'tolerance':None,'held_probe_used_for_gradient':False,
                        'error':type(error).__name__})
                    raise
                ttt_row.update(complete=True,status='complete')
                cv.reset(engine,anchor,anchor_sha); persist()
                audit('convergence_held_parent',arm=arm,parent_id=parent,complete=True)
            no=cells[arm]['no_ttt']['records']; yes=cells[arm]['ttt']['records']
            report['paired_ttt'][arm]={'complete':all(r['complete'] for r in no+yes),'denominator':denominator,
                'wins':sum(a['pass2']==0 and b['pass2']==1 for a,b in zip(no,yes)),
                'losses':sum(a['pass2']==1 and b['pass2']==0 for a,b in zip(no,yes)),
                'ties':sum(a['pass2']==b['pass2'] for a,b in zip(no,yes)),
                'ttt_used_for_weight_selection':False}
            persist()
        summarize(); check_deadline(deadline)
        report['complete']=(training_result['status']=='complete' and all(c['complete'] for a in cells.values() for c in a.values())
            and all(e['status']=='complete' for e in report['exports'].values()))
        report['status']='complete' if report['complete'] else 'partial'
        if report['complete']:
            scores={a:cells[a]['no_ttt']['pass2'] for a in cv.ARMS}; best=max(scores.values())
            winners=[a for a in cv.ARMS if scores[a]==best]
            if len(winners)==1 and best>scores['anchor']:
                report.update(selected_arm=winners[0],candidate_selected=True)
        report['selection_label']='provisional-small-panel-candidate' if report['candidate_selected'] else 'retain-anchor'
    except PhaseDeadline as error:
        primary=error; report.update(status='partial',stop_reason=str(error))
    except BaseException as error:
        primary=error; report.update(status='failed',error=type(error).__name__)
        error.convergence_workflow_result=report; raise
    finally:
        try:
            cv.reset(engine,anchor,anchor_sha)
            require(mc.full_policy_sha256(engine)==policy_sha,'full entry policy not restored')
            engine.model.train(mode); engine.sync(); report['anchor_restored']=True
        except BaseException as error:
            engine._fatal_update=True
            report.update(status='failed',complete=False,anchor_restored=False,restoration_error=type(error).__name__)
            if primary is None or isinstance(primary,PhaseDeadline):
                error.convergence_workflow_result=report; raise
        finally:
            summarize()
            report.update(engine_poisoned=bool(engine._fatal_update),physical=mc._delta(meter.snapshot(),before),
                wall_seconds=time.monotonic()-started,returned_after_deadline=time.time()>=deadline)
            report['physical'].update({key: (report.get('training') or {}).get('physical', {}).get(key, 0)
                for key in ('diagnostic_head_projection_attempts', 'diagnostic_head_projection_successes')})
            meter.close()
            if report['status']!='complete' or report['returned_after_deadline'] or engine._fatal_update:
                report.update(complete=False,candidate_selected=False,selected_arm='anchor',selection_label='retain-anchor')
                if report['status']=='complete': report['status']='partial'
            persist()
            if time.time()>=deadline and not report['returned_after_deadline']:
                report.update(returned_after_deadline=True,complete=False,candidate_selected=False,selected_arm='anchor',selection_label='retain-anchor')
                if report['status']=='complete':
                    report.update(status='partial',stop_reason='deadline_during_final_report_persistence')
                persist()
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-root',type=Path,required=True)
    parser.add_argument('--training-root',type=Path,required=True)
    parser.add_argument('--training-manifest',type=Path,required=True)
    parser.add_argument('--public-challenges',type=Path,required=True,help='Answer-free exclusion projection only, never an evaluator')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-sha256',required=True)
    parser.add_argument('--deadline-epoch',type=float,required=True,help='Original session absolute UTC deadline; never reset on retry')
    parser.add_argument('--training-deadline-epoch',type=float,required=True)
    parser.add_argument('--capacity',choices=('baseline','identity-depth32'),default='baseline')
    parser.add_argument('--execute-official',action='store_true',help='Explicit local-only actual model execution; never inferred by imports')
    args=parser.parse_args(argv)
    require(args.execute_official,'explicit --execute-official required; no automatic GPU launch')
    require(torch.cuda.is_available() and torch.cuda.device_count()==1,'one actual available CUDA device required')
    require(math.isfinite(args.deadline_epoch) and time.time()<args.training_deadline_epoch<args.deadline_epoch,
        'unconsumed original finite session deadlines required')
    require(args.deadline_epoch-time.time()<=7200,'bounded at-most7200s remaining local session required')
    require(args.deadline_epoch-args.training_deadline_epoch>=600,'at-least600s heldout/export/closure reserve required')
    free,total=torch.cuda.mem_get_info(0)
    minimum=20*1024**3 if args.capacity=='baseline' else 24*1024**3
    require(free>=minimum,'conservative free-memory admission unavailable; actual peak remains unverified')
    verify_inventory(args.public_challenges.parent,SOLVER_MANIFEST_SHA256)
    train,dev,public,split=load_data(args.training_root,args.training_manifest,args.public_challenges,
        expected_manifest_sha256=TRAINING_MANIFEST_SHA256)
    prepared=prepare_panels(train,dev,public,split,training_root=args.training_root,training_manifest_path=args.training_manifest,
        probability_policy=FP32_HEAD_POLICY)
    if args.capacity=='baseline':
        identity=verify_model(args.model_root,'2b')
        engine=CompactEngine.load(args.model_root,base_identity=identity,variant='2b',seed=0,adapter_seed=731,
                                  probability_policy='fp32-compact-head-v1')
    else:
        from tools.nvarc_capacity_20261017.factory import load_depth_engine
        engine=load_depth_engine(args.model_root,device='cuda',seed=0,adapter_seed=731,
                                probability_policy='fp32-compact-head-v1')
    report=run_workflow(engine,prepared,deadline=args.deadline_epoch,training_deadline=args.training_deadline_epoch,
        output=args.output,source_identity=args.source_sha256)
    print(json.dumps({'status':report['status'],'complete':report['complete'],'candidate_selected':report['candidate_selected'],
        'selected_arm':report['selected_arm'],'public_scoring_performed':False},sort_keys=True))
    return 0 if report['complete'] else 2


if __name__=='__main__':
    raise SystemExit(main())
