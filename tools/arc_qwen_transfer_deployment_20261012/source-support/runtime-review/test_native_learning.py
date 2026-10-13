"""One preregistered 8-update authored one-pixel LoRA learning control.
Uses the previously frozen exact native source and tokenizer. No search/retry.
Learning rate .002 is a CPU correctness-control setting, not production efficacy.
"""
from pathlib import Path
import os,sys,json,tempfile,time,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime-review/frozen-worktree-v2'))
import torch
torch.set_num_threads(1)
from tools.arc_qwen_transfer_20261012.backend import create_backend
from tools.arc_qwen_transfer_20261012 import model_profile as p,data as d
from tools.arc_learning_agent_20261011.budget import WorkLedger
with tempfile.TemporaryDirectory() as td:
    root=Path(td);ds=d.build_dataset({'tiny_cpu':True},root/'data');ledger=WorkLedger(root/'ledger.jsonl')
    config={'model_key':p.MODEL_KEY,'profile_id':p.PROFILE_ID,'tiny_cpu':True,'tokenizer_path':os.environ['REVIEW_TOKENIZER_ROOT'],
            'tiny_hidden_size':8,'material_addendum_sha256':p.MATERIAL_ADDENDUM_SHA256,'seed':1917,'do_sample':False}
    trainer_config={'split_manifest':ds['manifest'],'seed':1917,'task_augmentations':1,'objective_cycle':['grid'],
        'gradient_checkpointing':False,'learning_rate':.002,'task_learning_rate':.002,'stability_mode':False,'max_sequence_tokens':4096}
    model,trainer=create_backend(config,trainer_config,ledger=ledger)
    report={'cpu_fixture_only':True,'pretrained_or_gpu_claim':False,'seed':1917,'fixed_max_steps':8,'learning_rate':.002,
            'learning_rate_scope':'authored tiny correctness control only; not the production recipe','source_manifest':'frozen-copy-manifest-v2.json'}
    try:
        demos=[{'input':[[1]],'output':[[7]]},{'input':[[2]],'output':[[7]]}]
        trainer.freeze_global();trainer.begin_task('authored-fixed-one-pixel')
        records=d.build_task_records('authored-fixed-one-pixel',demos,augmentations=1,seed=trainer.trainer._task_seed)
        assert len(records)==2
        def observe():
            out=[]
            for record in records:
                nll=model.score_completion(record['messages'],record['completion'],deadline=time.monotonic()+90)
                assert nll['valid'] and nll['token_count']>0,nll
                generation=model.generate(record['messages'],kind='grid',seed=1917,max_new_tokens=4,deadline=time.monotonic()+90)
                out.append({'record_id':record['record_id'],'target':record['completion'],'nll':nll,'generation':generation,
                            'exact':generation.get('valid') is True and generation['text']==record['completion']})
            return out
        before=observe();trained=trainer.adapt_task('authored-fixed-one-pixel',demos,max_steps=8,deadline=time.monotonic()+110)
        after=observe()
        before_mean=sum(x['nll']['nll_sum'] for x in before)/sum(x['nll']['token_count'] for x in before)
        after_mean=sum(x['nll']['nll_sum'] for x in after)/sum(x['nll']['token_count'] for x in after)
        report.update(before=before,after=after,before_mean_nll=before_mean,after_mean_nll=after_mean,
            nll_declined=after_mean<before_mean,exact_before=sum(x['exact'] for x in before),exact_after=sum(x['exact'] for x in after),
            updates=trained,physical=ledger.summary())
        trainer.end_task();report['status']='passed' if after_mean<before_mean else 'no-positive-learning-signal'
        assert trained['optimizer_steps']==8 and trained['total_steps']==8
        assert ledger.used['training_steps']==8 and not ledger.pending
    finally:
        model.close()
        (ROOT/'runtime-review/native-learning-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['before','after','updates','physical']},indent=2))
if not report['nll_declined']:raise SystemExit(1)
