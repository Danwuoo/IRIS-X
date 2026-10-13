"""Only the verified owned launcher dispatches this worker."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import time
if __package__ in (None,''):
    sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).resolve().parents[2]/'src')]
from tools.arc_qwen_portfolio_20261012.protocol import PROTOCOL,require,checked_json,digest,validate_config
from tools.arc_qwen_portfolio_20261012.runner import source_check,project
from tools.arc_learning_agent_20261011.budget import WorkLedger,atomic_json

def run(request):
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2))
    root=Path(request['output_root']);deadline=request['work_deadline'];config=validate_config(request['config'])
    model=trainer=None;report=None;error=None;cleanup=None;ledger=WorkLedger(root/'physical-work.jsonl')
    start=time.monotonic();stage='source-admission';prior_training_receipts=[];prior_optimizer_steps=0;prior_trainer=None
    def mark(name,end=deadline):
        nonlocal stage
        stage=name;atomic_json(root/'active-stage.json',{'stage':name,'status':'active','deadline_monotonic':end})
    try:
        require(time.monotonic()<deadline,'worker deadline expired')
        source_check(request['source_identity'])
        from tools.arc_qwen_probe_20261012.data import load_development
        from tools.arc_qwen_portfolio_20261012.data import build_dataset
        from tools.arc_qwen_probe_20261012.experiment import run_ladder
        from tools.arc_qwen_portfolio_20261012.experiment import run_experiment
        from tools.arc_qwen_portfolio_20261012.backend import create_backend
        from tools.arc_qwen_portfolio_20261012.science_profiles import decide,make_policy
        mark('load',min(deadline,time.monotonic()+1800))
        if config.get('test_failure')=='before_load':raise RuntimeError('injected before_load boundary')
        if config.get('tiny_cpu'):
            model_config={'model_key':'qwen3-14b','tiny_cpu':True,'tokenizer_path':config['tokenizer_path'],
                          'tiny_hidden_size':config.get('tiny_hidden_size',16),'seed':PROTOCOL['seed'],'do_sample':False,'probe_fixture_generation_caps':{'grid':4,'program':8}}
        else:
            model_config={**config['model'],'tiny_cpu':False,'do_sample':False,
                          '_owned_probe_deadline':min(deadline,time.monotonic()+1790),
                          '_owned_probe_supervisor_pid':os.getppid(),'_owned_probe_scope':'qwen14b-capability-only'}
        import torch
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        trainer_config={'seed':PROTOCOL['seed'],'learning_rate':PROTOCOL['learning_rate'],
            'gradient_checkpointing':True,'stability_mode':True,'accumulation_target_tokens':1024,'accumulation_max_microbatches':1,
            'warmup_steps':4,'schedule_steps':32,'max_supervised_tokens':32768,'max_input_tokens':32*2048}
        model,trainer=create_backend(model_config,trainer_config,ledger=ledger)
        if config.get('test_failure')=='after_load':raise RuntimeError('injected after_load boundary')
        model.model.eval()
        atomic_json(root/'model-admission.json',{'identity':model.identity,'hardware':model.hardware,'load_elapsed_seconds':time.monotonic()-start},exclusive=True)
        mark('memory-cache-reset-ladder')
        ladder=run_ladder(model,trainer,ledger,root/'ladder',deadline)
        atomic_json(root/'ladder-report.json',ladder,exclusive=True)
        mark('preregistered-data-admission')
        development=None if config.get('tiny_cpu') else load_development(config)
        dataset=build_dataset(development,root/'dataset',deadline,ledger,
            training_root=config.get('training_root'),tiny_cpu=config.get('tiny_cpu',False))
        atomic_json(root/'dataset'/'dataset.json',dataset,exclusive=True)
        mark('decoder-cost-decision')
        feasibility=decide(model,{'solver_cases':dataset['solver_cases']},ladder,ledger,deadline,tiny=config.get('tiny_cpu',False))
        atomic_json(root/'feasibility.json',feasibility,exclusive=True)
        policy=make_policy(ladder,feasibility)
        atomic_json(root/'decoder-policy.json',{'policy':policy,'policy_sha256':digest(policy)},exclusive=True)
        if not feasibility['admitted']:
            report={'format':'irisx/qwen14b-portfolio-report-v1','status':'PORTFOLIO_DIAGNOSTICS_ONLY',
                'science_complete':False,'operational_success':False,'reason':feasibility['reason'],
                'science_profile':None,'decoder_mode':None,'decoder_policy_sha256':digest(policy),
                'profile_sha256':None,'protocol':PROTOCOL,'protocol_sha256':digest(PROTOCOL),
                'feasibility':feasibility,'decoder_policy':policy,'branches':{},'selected_case_ids':[],
                'omitted_case_ids':[c['case_id'] for c in dataset['solver_cases']],
                'denominators':dataset['denominators'],'public_score':None,'public_solving_admitted':False,
                'cpu_fixture_only':bool(config.get('tiny_cpu'))}
        else:
            trainer.trainer.freeze_decoder_identity(policy)
            trainer.trainer.config['split_manifest']=dataset['manifest']
            mark('paired-checkpoint-portfolio')
            report=run_experiment(model,trainer,ledger,dataset,root/'experiment',deadline,
                feasibility=feasibility,fail_before_train=config.get('test_failure')=='before_train')
        if report['status']=='PORTFOLIO_COMPLETE':
            mark('fresh-backend-disk-reload',min(deadline,time.monotonic()+1800))
            prior_trainer=trainer
            prior_training_receipts=list(trainer.training_receipts)
            prior_optimizer_steps=trainer.completed_optimizer_steps
            from tools.arc_qwen_portfolio_20261012.fresh_reload import verify_fresh_reload
            def factory():
                c=dict(model_config)
                if not config.get('tiny_cpu'):c['_owned_probe_deadline']=min(deadline,time.monotonic()+1790)
                return create_backend(c,trainer_config,ledger=ledger)
            model,trainer,fresh=verify_fresh_reload(model,trainer,factory=factory,dataset=dataset,
                report=report,policy=policy,ledger=ledger,output=root/'fresh-reload',deadline=deadline)
            report['fresh_backend_reload_verified']=fresh['verified']
            report['fresh_backend_reload_receipt']=fresh
            report['physical_usage_including_fresh_reload']=dict(ledger.used)
        report['ladder']=ladder;report['model_identity']=model.identity
        if config.get('test_failure')=='output':raise RuntimeError('injected output boundary')
        source_check(request['source_identity'])
        atomic_json(root/'full-diagnostics.json',report,exclusive=True)
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc)[:1024],'stage':stage}
    finally:
        # Capture failures before cleanup, including MeteredTrainer-raised receipts.
        try:
            if trainer is not None:
                atomic_json(root/'training-receipts-at-exit.json',{'receipts':([] if trainer is prior_trainer else prior_training_receipts)+trainer.training_receipts,'completed_optimizer_steps':(0 if trainer is prior_trainer else prior_optimizer_steps)+trainer.completed_optimizer_steps,
                    'physical_usage':dict(ledger.used),'run_state':trainer.trainer._run_state,
                    'decoder_policy_sha256':model._decoder_policy_sha256,'decoder_policy':model.decoder_policy},exclusive=True)
        except BaseException as exc:
            if error is None:error={'type':type(exc).__name__,'message':str(exc)[:512],'stage':'receipt-output'}
        try:
            if model is not None:model.close()
            if trainer is not None:
                trainer.trainer.model=None;trainer.trainer.parameters.clear()
                trainer.trainer.optimizer=None;trainer.trainer.scheduler=None
                trainer.trainer._training_snapshots.clear();trainer.trainer._snapshots.clear()
            cleanup={'model_close_called':model is not None,'trainer_references_cleared':trainer is not None}
        except BaseException as exc:
            cleanup={'error':type(exc).__name__+': '+str(exc)[:512]}
            if error is None:error={'type':type(exc).__name__,'message':str(exc)[:512],'stage':'cleanup'}
        # Even an output write failure cannot bypass native close or owned tree closure.
        summary=project(report) if report is not None and error is None else {'status':'PORTFOLIO_FAILED','science_complete':False,'operational_success':False,'failure':error,'public_score':None}
        summary.update(cleanup=cleanup,physical_usage=dict(ledger.used),physical_pending=deepcopy_pending(ledger.pending),
            elapsed_seconds=time.monotonic()-start,model_stopped_in_child=bool(cleanup is not None and 'error' not in cleanup),child_cleanup_complete=bool(cleanup is not None and 'error' not in cleanup),public_solving_admitted=False)
        atomic_json(root/'child-summary.json',summary,exclusive=True)
        atomic_json(root/'active-stage.json',{'stage':stage,'status':'closed','deadline_monotonic':deadline})
    if error:raise RuntimeError(error['stage']+': '+error['message'])
    return summary

def deepcopy_pending(pending):return json.loads(json.dumps(pending))

if __name__=='__main__':
    require(len(sys.argv)==3,'owned request and exact digest required')
    request=checked_json(sys.argv[1],sys.argv[2],cap=2*1024**2)
    require(request.get('format')=='irisx/qwen14b-portfolio-request-v1','exact owned request required')
    run(request)
