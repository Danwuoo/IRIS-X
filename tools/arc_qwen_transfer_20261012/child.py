"""Owned model process. Evaluator roots/answers are absent from its request."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import time
if __package__ in (None,''):
    sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).resolve().parents[2]/'src')]
from tools.arc_qwen_transfer_20261012.protocol import PROTOCOL,require,checked_json,digest,file_sha,validate_config
from tools.arc_qwen_transfer_20261012.runner import source_check,project
from tools.arc_learning_agent_20261011.budget import WorkLedger,atomic_json


def run(request):
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2))
    root=Path(request['output_root']);deadline=request['work_deadline'];config=validate_config(request['config'])
    require(not any('evaluator' in k for k in config),'evaluator configuration forbidden inside model owner')
    ledger=WorkLedger(root/'physical-work.jsonl');model=trainer=session=None;report=None;error=None;cleanup=None
    start=time.monotonic();stage='source-admission';runtime_evidence={}
    def mark(name,end=deadline):
        nonlocal stage
        stage=name;atomic_json(root/'active-stage.json',{'stage':name,'status':'active','deadline_monotonic':end})
    def ref(path):return {'path':str(path.absolute()),'sha256':file_sha(path)}
    try:
        require(time.monotonic()<deadline,'worker deadline expired');source_check(request['source_identity'])
        from tools.arc_qwen_transfer_20261012.data import build_dataset
        from tools.arc_qwen_transfer_20261012.backend import create_backend
        from tools.arc_qwen_transfer_20261012.model_profile import PROFILE_ID,MATERIAL_ADDENDUM_SHA256
        from tools.arc_qwen_transfer_20261012.decoder import run_calibration
        from tools.arc_qwen_transfer_20261012.science_profiles import decide,make_policy
        from tools.arc_qwen_transfer_20261012.experiment import SessionBackend,run_experiment
        mark('metadata-split-and-source-verification')
        dataset=build_dataset(config,root/'dataset')
        mark('native-load',min(deadline,time.monotonic()+1800))
        if config.get('test_failure')=='before_load':raise RuntimeError('injected before_load')
        if config.get('tiny_cpu'):
            model_config={'model_key':'qwen3-14b','profile_id':PROFILE_ID,'material_addendum_sha256':MATERIAL_ADDENDUM_SHA256,'tiny_cpu':True,'tokenizer_path':config['tokenizer_path'],
                'tiny_hidden_size':config.get('tiny_hidden_size',16),'seed':PROTOCOL['seed'],'do_sample':False}
        else:
            model_config={**config['model'],'tiny_cpu':False,'do_sample':False,'_owned_probe_deadline':min(deadline,time.monotonic()+1790),
                '_owned_probe_supervisor_pid':os.getppid(),'_owned_probe_scope':'qwen14b-capability-only'}
        import torch
        torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
        if torch.cuda.is_available():torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        trainer_config={'seed':PROTOCOL['seed'],'learning_rate':PROTOCOL['learning_rate'],'task_learning_rate':PROTOCOL['task_learning_rate'],
            'gradient_checkpointing':True,'stability_mode':True,'accumulation_target_tokens':1024,'accumulation_max_microbatches':1,
            'warmup_steps':4,'schedule_steps':256,'task_schedule_steps':16,'task_warmup_steps':1,'task_augmentations':8,
            'objective_cycle':['grid'],'max_supervised_tokens':4_000_000,'max_input_tokens':16_000_000}
        def factory():
            c=dict(model_config)
            if not config.get('tiny_cpu'):c['_owned_probe_deadline']=min(deadline,time.monotonic()+1790)
            return create_backend(c,trainer_config,ledger=ledger)
        load_started=time.monotonic();model,trainer=factory();load_seconds=time.monotonic()-load_started
        if config.get('test_failure')=='after_load':raise RuntimeError('injected after_load')
        model.model.eval();atomic_json(root/'model-admission.json',{'identity':model.identity,'hardware':model.hardware,
            'load_elapsed_seconds':load_seconds},exclusive=True);runtime_evidence['model_admission']=ref(root/'model-admission.json')
        mark('fresh4096-native-calibration',min(deadline,time.monotonic()+1800))
        calibration=run_calibration(model,trainer,ledger,root/'calibration',deadline,fixture_lengths=config.get('test_calibration_lengths'))
        runtime_evidence['calibration']=ref(root/'calibration'/'calibration.json')
        mark('fixed-main-cost-admission')
        feasibility=decide(model,dataset,calibration,ledger,deadline,tiny=config.get('tiny_cpu',False),checkpoints=config.get('test_checkpoint_updates'),generation_cap=config.get('test_generation_cap'),backend_load_seconds=load_seconds)
        atomic_json(root/'feasibility.json',feasibility,exclusive=True)
        if not feasibility['admitted']:
            report={'format':'irisx/true-arc-transfer-report-v1','status':'TRANSFER_NOT_ADMITTED','science_complete':False,
                'operational_success':False,'reason':feasibility['reason'],'feasibility':feasibility,
                'denominators':dataset['denominators'],'public_branch':{'status':'PUBLIC_NOT_RUN','reason':'main-not-admitted'},
                'cpu_fixture_only':config.get('tiny_cpu',False)}
        else:
            policy=make_policy(calibration,feasibility);atomic_json(root/'decoder-policy.json',policy,exclusive=True)
            trainer.trainer.freeze_decoder_identity(policy);trainer.trainer.config['split_manifest']=dataset['manifest']
            session=SessionBackend(model,trainer,ledger,factory,policy,calibration,dataset['manifest'])
            mark('true-arc-main-then-conditional-public-then-ttt')
            report=run_experiment(session,dataset,root/'experiment',deadline,feasibility=feasibility,config=config)
            model,trainer=session.model,session.trainer
            if report.get('public_branch',{}).get('status')=='PUBLIC_PREDICTIONS_SEALED':
                runtime_evidence['frozen_selection']=ref(root/'experiment'/'public'/'frozen-method.json')
                runtime_evidence['checkpoint_manifest']=ref(Path(report['checkpoints'][report['public_branch']['method']['candidate_id']]['path'])/'manifest.json')
        report['model_identity']=deepcopy_json(model.identity);report['runtime_evidence']=runtime_evidence
        if config.get('test_failure')=='output':raise RuntimeError('injected output')
        source_check(request['source_identity']);atomic_json(root/'full-diagnostics.json',report,exclusive=True)
    except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)[:2048],'stage':stage}
    finally:
        if session is not None:model,trainer=session.model,session.trainer
        identity=deepcopy_json(model.identity) if model is not None else None
        try:
            if trainer is not None:
                atomic_json(root/'training-receipts-at-exit.json',{'receipts':(session.training_receipts if session else [])+trainer.training_receipts,
                    'physical_usage':dict(ledger.used),'run_state':trainer.trainer._run_state},exclusive=True)
        except BaseException as exc:
            if error is None:error={'type':type(exc).__name__,'message':str(exc)[:512],'stage':'receipt-output'}
        try:
            if model is not None:model.close()
            if trainer is not None:
                raw=trainer.trainer;raw.model=None;raw.parameters.clear();raw.optimizer=raw.scheduler=None
                raw._training_snapshots.clear();raw._snapshots.clear()
            cleanup={'model_close_called':model is not None,'trainer_references_cleared':trainer is not None}
        except BaseException as exc:
            cleanup={'error':type(exc).__name__+': '+str(exc)[:512]}
            if error is None:error={'type':type(exc).__name__,'message':str(exc)[:512],'stage':'cleanup'}
        summary=project(report) if report is not None and error is None else {'status':'TRANSFER_FAILED','science_complete':False,'operational_success':False,'failure':error,'denominators':{'dev':16,'holdout':32,'ttt_dev':8,'ttt_holdout':8}}
        stopped=bool(cleanup is not None and 'error' not in cleanup)
        summary.update(cleanup=cleanup,physical_usage=dict(ledger.used),pending_work=deepcopy_json(ledger.pending),
            elapsed_seconds=time.monotonic()-start,model_stopped=stopped,child_cleanup_complete=stopped,
            model_identity=identity,production_model=bool(model is not None and config.get('tiny_cpu') is not True),runtime_evidence=runtime_evidence,request_sha256=request['_request_sha256'],
            source_identity_sha256=digest(request['source_identity']),public_gold_opened=False)
        atomic_json(root/'child-summary.json',summary,exclusive=True)
        atomic_json(root/'active-stage.json',{'stage':stage,'status':'closed','deadline_monotonic':deadline})
    if error:raise RuntimeError(error['stage']+': '+error['message'])
    return summary


def deepcopy_json(value):return json.loads(json.dumps(value))

if __name__=='__main__':
    require(len(sys.argv)==3,'owned request and exact digest required')
    request=checked_json(sys.argv[1],sys.argv[2],cap=2*1024**2)
    require(request.get('format')=='irisx/true-arc-transfer-request-v1','exact owned request required')
    request['_request_sha256']=sys.argv[2];run(request)
