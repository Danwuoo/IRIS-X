"""Final-source tiny native 0/1/2 fixture + task0/8/16 persistence validation.
Offline authored correctness control only. No pretrained weights, ARC evaluation,
PUBLIC answers, scientific effectiveness or GPU claim. Never changes recipes.
"""
from copy import deepcopy
import hashlib,json,os,sys,time
from pathlib import Path
ROOT=Path('/workspace/scratch/3c2b2502fb1e/portfolio63-checkpoint-repair-20261012');SOURCE=Path('/workspace/scratch/3c2b2502fb1e/portfolio63-checkpoint-repair-20261012/final-source-freeze-002')
sys.path[:0]=[str(SOURCE),str(SOURCE/'src')]
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
import torch
torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
from tools.arc_qwen_transfer_20261012.backend import create_backend
from tools.arc_qwen_transfer_20261012 import model_profile as p,data as d
from tools.arc_learning_agent_20261011.data import create_split_manifest,build_records
from tools.arc_learning_agent_20261011.budget import WorkLedger,atomic_json
from tools.arc_qwen_portfolio_20261012.checkpoints import save_branch_checkpoint,load_branch_checkpoint,load_inference_adapter,inspect_checkpoint
from tools.arc_qwen_transfer_20261012.checkpoint_policy import FIXTURE as GLOBAL,TTT

out=Path('/workspace/scratch/3c2b2502fb1e/portfolio63-checkpoint-repair-20261012/independent-runtime-review/native-final-fixture');out.mkdir(parents=True,exist_ok=False)
ledger=WorkLedger(out/'physical-work.jsonl')
tasks={'authored-train':{'train':[{'input':[[1]],'output':[[7]]},{'input':[[2]],'output':[[7]]}]},
       'unused-split-only':{'train':[{'input':[[1,2],[3,4]],'output':[[1,2],[3,4]]},{'input':[[5,6],[7,8]],'output':[[5,6],[7,8]]}]}}
manifest=create_split_manifest(tasks,fixed_splits={'train':['authored-train'],'dev':['unused-split-only']},source_identity={'kind':'authored-checkpoint-correctness-control'})
records=[r for r in build_records(tasks,manifest,augmentations=1,seed=1917) if r['split']=='train']
model_config={'model_key':p.MODEL_KEY,'profile_id':p.PROFILE_ID,'material_addendum_sha256':p.MATERIAL_ADDENDUM_SHA256,
    'tiny_cpu':True,'tokenizer_path':str(SOURCE/'materials/qwen14b/hf-overlay'),'tiny_hidden_size':8,'seed':1917,'do_sample':False}
trainer_config={'split_manifest':manifest,'seed':1917,'learning_rate':.0002,'task_learning_rate':.00005,
    'gradient_checkpointing':True,'stability_mode':True,'accumulation_target_tokens':1024,'accumulation_max_microbatches':1,
    'warmup_steps':4,'schedule_steps':256,'task_schedule_steps':16,'task_warmup_steps':1,'task_augmentations':1,
    'objective_cycle':['grid'],'max_supervised_tokens':4000000,'max_input_tokens':16000000}
provenance={'test_backend':False,'tiny_random_model':True,'authored_control':True,'scientific_effectiveness_claim':False}
report={'fixture_schedule_only':True,'source_root':str(SOURCE),'status':'running','actual_update_schedule':[0,1,2],'tiny_cpu_only':True,'pretrained_or_gpu_claim':False,
    'training_data':'two authored one-pixel constant-output examples; unused independent split manifest only',
    'config':trainer_config,'results':[],'task_results':[],'started_monotonic':time.monotonic()}
atomic_json(out/'receipt.json',report)
def factory():
    m,t=create_backend(model_config,trainer_config,ledger=ledger)
    m._counter=t._counter=len(ledger.events)+1
    return m,t
def observe(model):
    values=[]
    for r in records:
        score=model.score_completion(r['messages'],r['completion'],deadline=time.monotonic()+150)
        gen=model.generate(r['messages'],kind='grid',seed=1917,max_new_tokens=4,deadline=time.monotonic()+150)
        assert score['valid'] and score['token_count']>0,score
        values.append({'nll_sum':score['nll_sum'],'token_count':score['token_count'],'tokens':gen['output_token_ids'],'valid':gen['valid']})
    return values
model,trainer=factory();previous=0
try:
    for update in (0,1,2):
        if update:
            trained=trainer.train(records,max_steps=update-previous,deadline=time.monotonic()+1800)
            assert trained['status']=='complete' and trained['optimizer_steps']==update-previous and trained['total_steps']==update,trained
            atomic_json(out/f'training-{update}.json',trained)
        before=observe(model);state=trainer.snapshot_training_state('observed-'+str(update))
        trainer.release_training_state(state)
        saved=save_branch_checkpoint(trainer,out/'checkpoints',branch_id='global_grid',update=update,records=records,provenance=provenance,checkpoint_schedule=GLOBAL)
        metadata=inspect_checkpoint(saved['path'],expected_manifest_sha256=saved['manifest_sha256'])
        assert metadata['binding']['checkpoint_schedule']['allowed_updates']==[0,1,2]
        physical=deepcopy(ledger.summary());old_params={k:id(v) for k,v in trainer.trainer.parameters.items()}
        # Real disk resume into the same backend validates exact state, live bindings and ledger.
        loaded=load_branch_checkpoint(trainer,saved['path'],branch_id='global_grid',records=records,provenance=provenance,
            expected_manifest_sha256=saved['manifest_sha256'],checkpoint_schedule=GLOBAL)
        assert loaded['state_sha256']==state['state_sha256'] and ledger.summary()==physical
        assert old_params=={k:id(v) for k,v in trainer.trainer.parameters.items()}
        assert observe(model)==before
        # Fresh native base + PEFT, standalone adapter only; optimizer not read.
        fresh,inference=factory();physical=deepcopy(ledger.summary())
        infer=load_inference_adapter(inference,saved['inference_path'],branch_id='global_grid',records=records,provenance=provenance,
            expected_inference_manifest_sha256=saved['inference_manifest_sha256'],checkpoint_schedule=GLOBAL)
        assert ledger.summary()==physical and infer['optimizer_shards_read'] is False
        assert inference.trainer.optimizer is None and inference.trainer._run_state is None
        assert observe(fresh)==before
        fresh.close()
        # Fresh native full-state resume, then continue the same actual fixture optimizer schedule.
        fresh,resumed=factory();physical=deepcopy(ledger.summary())
        reloaded=load_branch_checkpoint(resumed,saved['path'],branch_id='global_grid',records=records,provenance=provenance,
            expected_manifest_sha256=saved['manifest_sha256'],checkpoint_schedule=GLOBAL)
        assert ledger.summary()==physical and reloaded['state_sha256']==state['state_sha256']
        if update:
            assert {int(float(s['step'])) for s in resumed.trainer.optimizer.state.values()}=={update}
            assert resumed.trainer.scheduler.last_epoch==update
        assert observe(fresh)==before
        model.close();model,trainer=fresh,resumed
        row={'update':update,'saved':saved,'reload':loaded,'fresh_resume':reloaded,'inference':infer,
            'observed':before,'exact_token_nll_parity':True,'actual_adam_and_scheduler_step':update}
        report['results'].append(row);atomic_json(out/'receipt.json',report)
        print(json.dumps({'checkpoint':update,'status':'passed','mean_nll':sum(x['nll_sum'] for x in before)/sum(x['token_count'] for x in before)}),flush=True)
        previous=update
    # Actual selected-global -> reset-isolated TTT 0/8/16 and safe task checkpoints.
    selected=trainer.fingerprint()['sha256'];trainer.freeze_global();trainer.begin_task('authored-ttt')
    demos=tasks['authored-train']['train']
    task_records=d.build_task_records('authored-ttt',demos,augmentations=1,seed=trainer.trainer._task_seed)
    for update in (0,8,16):
        if update:
            tr=trainer.adapt_task('authored-ttt',demos,max_steps=8,deadline=time.monotonic()+300)
            assert tr['total_steps']==update
        saved=save_branch_checkpoint(trainer,out/'checkpoints',branch_id='representative_ttt',update=update,records=task_records,
            provenance={'selected_global_adapter_sha256':selected},checkpoint_schedule=TTT)
        physical=deepcopy(ledger.summary())
        loaded=load_branch_checkpoint(trainer,saved['path'],branch_id='representative_ttt',records=task_records,
            expected_manifest_sha256=saved['manifest_sha256'],checkpoint_schedule=TTT)
        assert ledger.summary()==physical and loaded['state_sha256']==saved['state_sha256']
        report['task_results'].append({'update':update,'saved':saved,'loaded':loaded})
    physical=deepcopy(ledger.summary());reset=trainer.end_task()
    assert reset['adapter_sha256']==selected and ledger.summary()==physical and not ledger.pending
    assert ledger.used['training_steps']==18
    nll=lambda xs:sum(x['nll_sum'] for x in xs)/sum(x['token_count'] for x in xs)
    report.update(status='passed',physical=ledger.summary(),selected_global_reset_verified=True,
        nll_before=nll(report['results'][0]['observed']),nll_after=nll(report['results'][-1]['observed']),
        elapsed_seconds=time.monotonic()-report['started_monotonic'])
    report['nll_declined']=report['nll_after']<report['nll_before']
finally:
    model.close();atomic_json(out/'receipt.json',report)
print(json.dumps({k:v for k,v in report.items() if k not in ('results','task_results','physical','config')},indent=2))
