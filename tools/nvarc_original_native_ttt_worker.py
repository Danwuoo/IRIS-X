# Original portions/source flow: sorokin's Kaggle notebook Version10,
# arc2-qwen3-unsloth-flash-lora-batch4-queue, Apache-2.0.
# https://www.kaggle.com/code/sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue
# IRIS-X adaptations: native preparation/training flow with reviewed-source and finite guards.
# See notices/NOTICE-native.txt and notices/LICENSE-Apache-2.0.txt.
# This does not relicense independently authored portions or the entire file.
"""Original-runtime complete 128-view Trainer epoch; no generation or export."""
import argparse
import importlib.metadata
import inspect
import json
from pathlib import Path
import sys
import time
from types import ModuleType
from typing import Any,Union

from inspection_helpers import (digest,require,zero_work_guard,original_definitions,
    source_snapshot,prepared_evidence,tensor_inventory)
from nvarc_native_ttt_budget import EpochBudget
from hardware_helpers import normalize_gpu_uuid

FORMAT='irisx/nvarc-original-native-long-ttt-v1'
PARAMETERS=528564224


def run(plan,model_path,dependency,solver_path,texts,rows,output):
    require(plan['format']==FORMAT and plan['owner_decision']=='Decision 0054' and plan['approved'] is True and
        plan['maximum_outer_forwards']==plan['maximum_optimizer_steps']==128 and
        plan['maximum_generations']==plan['maximum_teacher_calls']==plan['maximum_paid_usd']==0,
        'approved complete native epoch required')
    parent=json.loads((output.parent/'parent-verification.json').read_bytes())
    require(parent['plan_digest']==digest(plan) and parent['source_inventory_verified'] is True and
        parent['four_distinct_bf16_l4s'] is True and parent['model_material_digest']==plan['model_material_digest'],
        'exact native parent required')
    started=time.monotonic();budget=None
    def save(name,value):
        path=output/name;temporary=path.with_suffix(path.suffix+'.tmp')
        temporary.write_text(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False),encoding='utf-8')
        temporary.replace(path)
    blocked=[]
    def denied(row):blocked.append(row);save('prohibited-preparation.json',blocked)
    sys.path.insert(0,str(dependency))
    require({name:importlib.metadata.version(name) for name in plan['versions']}==plan['versions'],
        'exact native training versions required')
    import torch
    require(torch.__version__=='2.8.0+cu128' and Path(torch.__file__).resolve().is_relative_to(dependency.resolve()) and
        torch.cuda.device_count()==1 and torch.cuda.get_device_name(0)=='NVIDIA L4','native single-L4 worker required')
    uuid=normalize_gpu_uuid(str(torch.cuda.get_device_properties(0).uuid))
    require(uuid==json.loads((output.parent/'hardware.json').read_bytes())['inventory'][0]['uuid'],
        'actual worker UUID must bind parent rank zero')
    save('hardware.json',{'device_uuid':uuid,'name':torch.cuda.get_device_name(0),'torch':torch.__version__})
    with zero_work_guard(torch,denied) as verify_guard:
        from unsloth import FastLanguageModel,UnslothTrainer,UnslothTrainingArguments
        from transformers import DataCollatorForLanguageModeling
        from peft import get_peft_model_state_dict,set_peft_model_state_dict
        from datasets import Dataset
        import numpy as np
        verify_guard()
        namespace=ModuleType('irisx_verified_original_solver');namespace.__file__=str(solver_path)
        sys.modules[namespace.__name__]=namespace
        namespace.__dict__.update(UnslothTrainer=UnslothTrainer,DataCollatorForLanguageModeling=DataCollatorForLanguageModeling,
            np=np,torch=torch,Any=Any,Union=Union)
        source=solver_path.read_text(encoding='utf-8')
        import hashlib
        require(hashlib.sha256(source.encode()).hexdigest()==plan['solver_cell_sha256'],'exact original solver required')
        tree=original_definitions(source,namespace.__dict__,plan['original_class_ast_sha256'])
        model,tokenizer=FastLanguageModel.from_pretrained(model_name=str(model_path),full_finetuning=False,
            load_in_4bit=False,local_files_only=True,use_gradient_checkpointing=False,max_seq_length=8192)
        model=FastLanguageModel.get_peft_model(model,**plan['original_peft_parameters'])
        for parameter in model.parameters():
            if parameter.dtype==torch.float32:parameter.data=parameter.data.to(torch.bfloat16)
        trainable=[{'name':name,'shape':list(p.shape),'dtype':str(p.dtype),'elements':p.numel()}
            for name,p in model.named_parameters() if p.requires_grad]
        require(sum(row['elements'] for row in trainable)==PARAMETERS and
            {row['name']:row['shape'] for row in trainable}==plan['source_inferred_trainable_layout'] and
            all(row['dtype']=='torch.bfloat16' for row in trainable),'exact native BF16 adapter layout required')
        save('adapter-topology.json',trainable)
        raw=get_peft_model_state_dict(model,adapter_name='default');defaults=source_snapshot(tree,raw)
        require(all(defaults[k].data_ptr()!=raw[k].data_ptr() and not defaults[k].requires_grad for k in defaults),
            'independent cloned/detached baseline required')
        baseline=tensor_inventory(defaults,torch);save('baseline-inventory.json',baseline)
        del raw
        model=FastLanguageModel.for_training(model)
        collator=namespace.QwenDataCollatorForCompletionOnlyLM(tokenizer=tokenizer,mlm=False)
        args=UnslothTrainingArguments(**plan['original_training_arguments'])
        trainer=namespace.UnslothFixedTrainer(model=model,tokenizer=tokenizer,data_collator=collator,
            train_dataset=Dataset.from_list(texts),dataset_text_field='text',max_seq_length=8192,args=args)
        verify_guard()
        require(trainer.optimizer is None and model._compiled_call_impl is None and trainer.args.torch_compile is False and
            trainer.args.max_length==trainer.args.max_seq_length==8192 and
            trainer.args.adam_beta1==.9 and trainer.args.adam_beta2==.999 and trainer.args.adam_epsilon==1e-8 and
            trainer.args.max_steps==-1 and trainer.args.dataloader_drop_last is False and trainer.args.label_smoothing_factor==0,
            'complete source epoch/native defaults must survive preprocessing')
        with (output/'prepared-tokens.i16le').open('xb') as binary:
            prepared=prepared_evidence(trainer,collator,rows,binary)
        require(all(row['source_input_ids_equal'] and row['source_labels_equal'] and row['collator_preserved_input_ids'] for row in prepared),
            'every complete native source view must match before training')
        save('prepared-rows.json',prepared)
        flags=[{'module':name,'value':module.gradient_checkpointing} for name,module in model.named_modules()
            if hasattr(module,'gradient_checkpointing')]
        require(len(flags)==37 and all(row['value'] is True for row in flags),'all native checkpoint flags required')
        origins=[]
        for cls in type(trainer).__mro__:
            try:path=inspect.getsourcefile(cls)
            except TypeError:path=None
            if path is not None and Path(path).is_file():
                origins.append({'class':cls.__name__,'module':cls.__module__,
                    'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()})
        require(origins==plan['native_trainer_origins'],'exact original prepared native Trainer implementations required')
        save('preparation.json',{'checkpoint_flags':flags,'trainer_origins':origins,'max_length':8192,'max_seq_length':8192,
            'prepared_rows_digest':digest(prepared),'blocked_attempts':len(blocked)})
    budget=EpochBudget(torch,model,trainer,rows,plan['source_learning_rates'],lambda value:save('training-ledger.json',value),
        expected_parameters=PARAMETERS,expected_dtype='torch.bfloat16')
    training_start=time.monotonic()
    with budget.installed():
        metrics=trainer.train()
        moments=budget.complete()
    torch.cuda.synchronize();elapsed=time.monotonic()-training_start
    require(trainer.state.global_step==128 and trainer.state.epoch==1,'native Trainer must complete one entire epoch')
    trained=tensor_inventory(get_peft_model_state_dict(model,adapter_name='default'),torch)
    require(trained!=baseline,'full native epoch must change at least one saved tensor')
    save('trained-inventory.json',trained);save('optimizer-state.json',moments)
    # Preserve the original task boundary: discard optimizer and restore all saved state.
    budget.optimizer.zero_grad(set_to_none=True)
    budget.optimizer.state.clear()
    require(not budget.optimizer.state,'all native optimizer tensor state must be discarded')
    trainer.optimizer=None;trainer.lr_scheduler=None
    trainer.accelerator._optimizers.clear();trainer.accelerator._schedulers.clear()
    budget.optimizer=None
    set_peft_model_state_dict(model,defaults.copy(),adapter_name='default')
    restored=tensor_inventory(get_peft_model_state_dict(model,adapter_name='default'),torch)
    require(restored==baseline,'all original saved tensors must reset after the complete epoch')
    save('reset-inventory.json',restored)
    result={'run_id':plan['run_id'],'plan_digest':digest(plan),'outcome':'complete','model_forwards':128,'optimizer_steps':128,
        'input_tokens':sum(row['input_tokens'] for row in budget.state['forwards']),
        'supervised_tokens':sum(row['supervised_tokens'] for row in budget.state['forwards']),
        'gradient_tensors_per_step':len(budget.parameters),'all_saved_tensors_restored':True,
        'training_wall_seconds':elapsed,'worker_wall_seconds':time.monotonic()-started,
        'cuda_peak_allocated_bytes':torch.cuda.max_memory_allocated(),'cuda_peak_reserved_bytes':torch.cuda.max_memory_reserved(),
        'trainer_global_step':trainer.state.global_step,'trainer_epoch':trainer.state.epoch,
        'optimizer_discarded':True,'full_native_long_ttt_completed':True,'generations':0,'teacher_calls':0,'paid_usd':0,
        'contains_evaluator_truth':False,'correctness_scored':False,'checkpoint_exported':False,
        'scope':'one complete native task-local training epoch; no solve, native clock parity, ARC quality or full-method claim'}
    require(result['input_tokens']==955392 and result['supervised_tokens']==476160,'every complete native input/label required')
    save('training-result.json',result)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('plan','model','dependency','solver','texts','rows','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(exist_ok=False)
    run(json.loads(args.plan.read_bytes()),args.model,args.dependency,args.solver,json.loads(args.texts.read_bytes()),
        json.loads(args.rows.read_bytes()),args.output)
