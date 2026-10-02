"""Full 128-view long-demo epoch on the published original Qwen3 checkpoint.

The precisely pinned Transformers backend is a resource adaptation; the
unknown historical Unsloth version and per-task clock are not reproduced.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import time

from .arc_nvarc_combined import atomic
from .arc_nvarc_complete_ttt import complete_config
from .arc_nvarc_data import visible_task
from .arc_nvarc_source_bundle import verify_bundle
from .arc_nvarc_training import TaskLocalAdapter,task_local_sequences
from .arc_nvarc_upstream import source_bundle
from .canonical import digest_value
from .canonical import canonical_bytes
from .errors import ValidationError

FORMAT='irisx/nvarc-original-qwen3-long-ttt-v1'
MATERIAL='sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03'


def adaptation_config():
    config=complete_config()['adaptation'];config['optimizer_state_device']='cpu';return config


def row_digest(row):return digest_value({key:row[key] for key in ('input_ids','labels')})


def reserve_row(ledger,remaining,row,maximum_tokens):
    """Reserve one exact approved row before the model receives its tensors."""
    identity=row_digest(row);length=len(row['input_ids'])
    if (ledger['outer_forwards_reserved']>=128 or remaining[identity]<1 or
            len(row['labels'])!=length or ledger['input_tokens_reserved']+length>maximum_tokens):
        raise ValidationError('unapproved or exhausted source row/label budget differs')
    remaining[identity]-=1
    ledger['outer_forwards_reserved']+=1;ledger['input_tokens_reserved']+=length
    ledger['forward_row_digests'].append(identity)


def check_plan(plan,config,tasks):
    exact={'maximum_tasks':1,'maximum_optimizer_steps':128,'maximum_outer_forwards':128,
        'maximum_training_tokens':1048576,'maximum_generations':0,'maximum_verifications':0,
        'maximum_teacher_calls':0,'maximum_paid_usd':0,'maximum_notebook_wall_seconds':10800,
        'maximum_worker_wall_seconds':10560,'source_view_count':128,'model_instance_version_id':627758,
        'runtime_dataset_version':1,'competition_files_opened':0,'augmentation_count':16,
        'source_augmentation_seed':1,'reference_epoch_seed':42}
    if (any(type(plan.get(key)) is not int or plan[key]!=value for key,value in exact.items()) or
            type(plan.get('source_max_sequence_length')) is not int or
            type(plan.get('source_input_tokens')) is not int or
            not 0<plan['source_input_tokens']<=1048576 or plan.get('approved') is not True or
            plan.get('embedding_head_tied') is not False):
        raise ValidationError('exact integer long-epoch budgets and untied approval required')
    if (plan.get('format')!=FORMAT or plan.get('owner_decision')!='Decision 0054' or
            not re.fullmatch(r'nvarc-original-qwen3-long-ttt-\d{3}',plan.get('run_id','')) or
            canonical_bytes(config)!=canonical_bytes(adaptation_config()) or plan.get('config_digest')!=digest_value(config) or
            plan.get('visible_digest')!=digest_value(tasks) or len(tasks)!=1 or
            len(tasks[0]['test'])!=1 or set(tasks[0]['test'][0])!={'input'} or
            plan.get('model_material_digest')!=MATERIAL or plan.get('maximum_tasks')!=1 or
            plan.get('maximum_optimizer_steps')!=128 or plan.get('maximum_outer_forwards')!=128 or
            plan.get('maximum_generations')!=0 or plan.get('maximum_verifications')!=0 or
            plan.get('maximum_teacher_calls')!=0 or plan.get('maximum_paid_usd')!=0 or
            plan.get('maximum_notebook_wall_seconds')!=10800 or plan.get('maximum_worker_wall_seconds')!=10560 or
            plan.get('retain_export') is not False or not 6000<=plan.get('source_max_sequence_length',0)<=8192):
        raise ValidationError('exact full original-family long-epoch resource envelope required')


def run(plan,config,raw,model_path,bundle,output):
    import torch
    import transformers
    import peft
    from transformers import Qwen3ForCausalLM
    from peft import get_peft_model_state_dict
    from tokenizers import Tokenizer
    if any(set(value)!={'train','test'} or any(set(test)!={'input'} for test in value['test']) for value in raw.values()):
        raise ValidationError('visible-only public demonstrations and test inputs required')
    tasks=[visible_task(key,value) for key,value in sorted(raw.items())]
    check_plan(plan,config,tasks);verify_bundle(bundle,plan['source_bundle_digest'])
    if (output.exists() or torch.__version__!='2.10.0+cu128' or transformers.__version__!='4.53.3' or
            peft.__version__!='0.21.0' or not torch.cuda.is_available()):
        raise ValidationError('new exact pinned CUDA runtime observation required')
    output.mkdir();started=time.monotonic();device=torch.device('cuda',0)
    torch.cuda.set_device(device)
    from .arc_nvarc_hardware import normalize_gpu_uuid
    properties=torch.cuda.get_device_properties(device)
    hardware={'rank':0,'name':properties.name,'device_uuid':normalize_gpu_uuid(properties.uuid),
        'bf16':torch.cuda.is_bf16_supported()}
    if hardware['name']!='NVIDIA L4' or hardware['bf16'] is not True:
        raise ValidationError('actual model worker requires BF16 L4')
    ledger={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'outer_forwards_reserved':0,
        'input_tokens_reserved':0,'optimizer_steps_completed':0,'generation_calls':0,'teacher_calls':0,
        'verification_calls':0,'maximum_paid_usd':0,'phase':'row-gate','forward_row_digests':[]}
    atomic(output/'ledger.json',ledger);adapter=hook=None
    def emit(event,**fields):
        with (output/'events.jsonl').open('ab') as stream:
            from .canonical import canonical_bytes
            stream.write(canonical_bytes({'event':event,'elapsed_seconds':time.monotonic()-started,**fields},newline=True))
            stream.flush()
    try:
        with source_bundle(bundle,plan['source_bundle_digest']):
            rows=task_local_sequences(tasks[0],seed=42,augmentation_count=16,source_qwen=True,
                source_augmentation_seed=1,source_max_length=8192)
            if (len(rows)!=128 or digest_value(rows)!=plan['source_rows_digest'] or
                    sum(len(r['input_ids']) for r in rows)!=plan['source_input_tokens'] or
                    max(len(r['input_ids']) for r in rows)!=plan['source_max_sequence_length']):
                raise ValidationError('all complete 128 original source views must match before model load')
            remaining=Counter(row_digest(row) for row in rows)
            ids=Tokenizer.from_file(str(model_path/'tokenizer.json')).encode(
                '<|im_start|>user\n12<|im_end|><|im_start|>assistant\n34<|im_end|>').ids
            if ids!=[14,11,10,1,2,15,14,12,10,3,4,15]:raise ValidationError('original WordLevel source role map differs')
            ledger['phase']='model-load';atomic(output/'ledger.json',ledger);emit('model-load')
            base=Qwen3ForCausalLM.from_pretrained(model_path,local_files_only=True,
                torch_dtype=torch.bfloat16,attn_implementation='sdpa').to(device).eval()
            if (base.config.model_type!='qwen3' or base.config.num_hidden_layers!=36 or base.config.vocab_size!=16 or
                    base.get_input_embeddings().weight.data_ptr()==base.get_output_embeddings().weight.data_ptr()):
                raise ValidationError('original untied published 4B checkpoint required')
            def reserve(module,args,kwargs):
                if (ledger['outer_forwards_reserved']>=128 or time.monotonic()-started>=10500 or
                        kwargs['input_ids'].shape[0]!=1):
                    raise ValidationError('long-epoch finite outer-forward/time bound reached')
                core={key:kwargs[key].detach().cpu().tolist()[0] for key in ('input_ids','labels')}
                reserve_row(ledger,remaining,core,plan['source_input_tokens']);atomic(output/'ledger.json',ledger)
            def observe(event):
                ledger['optimizer_steps_completed']=event['completed_steps'];atomic(output/'ledger.json',ledger)
                emit('ttt-optimizer-returned',**event)
            hook=base.register_forward_pre_hook(reserve,with_kwargs=True)
            adapter=TaskLocalAdapter(base,config,step_observer=observe)
            if len(adapter.targets)!=254:raise ValidationError('all 254 original adapter targets required')
            def state_digest():
                return digest_value({name:{'shape':list(value.shape),'dtype':str(value.dtype),
                    'sha256':hashlib.sha256(value.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()}
                    for name,value in get_peft_model_state_dict(adapter.model).items()})
            initial=state_digest();ledger['phase']='complete-source-long-epoch';atomic(output/'ledger.json',ledger)
            emit('model-ready',adapter_targets=254,model_material_digest=MATERIAL)
            adapter.adapt(tasks[0]);observation=adapter.last_observation
            if (observation['steps']!=128 or observation['training_tokens']!=plan['source_input_tokens'] or
                    not observation['complete_epoch'] or any(remaining.values()) or
                    ledger['outer_forwards_reserved']!=128 or ledger['optimizer_steps_completed']!=128):
                raise ValidationError('full 128-view long-task source epoch did not complete')
            adapted=state_digest()
            if adapted==initial:raise ValidationError('full task-local epoch did not change the adapter state')
            adapter.reset(clear_observation=False);restored=state_digest()
            if restored!=initial:raise ValidationError('original task-local adapter reset bytes differ')
            result={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'outcome':'complete',
                'model_material_digest':MATERIAL,'source_rows_digest':plan['source_rows_digest'],
                'transformers_version':transformers.__version__,'peft_version':peft.__version__,'torch_version':torch.__version__,
                'embedding_head_tied':False,'adapter_target_count':254,'observation':observation,'hardware':hardware,
                'initial_adapter_digest':initial,'adapted_adapter_digest':adapted,'reset_adapter_digest':restored,
                'full_long_task_epoch_completed':True,'adapter_reset_verified':True,'outer_forwards':128,
                'optimizer_steps':128,'input_tokens':plan['source_input_tokens'],'generation_calls':0,
                'teacher_calls':0,'verification_calls':0,'checkpoint_exported':False,'full_sft_completed':False,
                'historical_unsloth_parity':False,'historical_task_clock_parity':False,
                'contains_evaluator_truth':False,'worker_wall_seconds':time.monotonic()-started}
            atomic(output/'worker-result.json',result);ledger['phase']='complete';atomic(output/'ledger.json',ledger)
            return result
    except BaseException as error:
        ledger.update(phase='failed',error_type=type(error).__name__);atomic(output/'ledger.json',ledger)
        atomic(output/'failure.json',{'error_type':type(error).__name__,'message':str(error)[:1200]});raise
    finally:
        if hook is not None:hook.remove()
        if adapter is not None:adapter.reset(clear_observation=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('plan','config','visible','model','bundle','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(json.loads(args.plan.read_bytes()),json.loads(args.config.read_bytes()),
        json.loads(args.visible.read_bytes()),args.model,args.bundle,args.output)
