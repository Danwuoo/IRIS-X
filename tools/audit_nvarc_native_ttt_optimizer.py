"""Bind native TTT optimizer sources and replay only two reviewed scalar schedules.

This does not import ML packages, construct an optimizer or run a model.
The acquired original dependency files and consumed native inspection stay frozen.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.stage_nvarc_original_training_inspection import verify

MATERIAL=ROOT/'.irisx/nvarc-original/materials/qwen3-original-ttt-optimizer-20261002-001'
EXACT={
    'transformers/optimization.py':'41b08ffb29c2691626b225ed389a694cc8e61480818214a35f215b5c39167bfb',
    'accelerate/optimizer.py':'a79a9f08e322f03023bf1e9e102ca9a387a3de9be643f53f6e09ab10029ce216',
    'accelerate/accelerator.py':'d8d685282f6bee8a7d1b8ad3da4b6d17114f08fbe3fe01dea621b60c84c82fcb',
    'torch/nn/utils/clip_grad.py':'534f39d7308c6ab4fa9e5994a177803abe958ce53d5681e66049a9917e0115c1'}


def require(value,message):
    if not value:raise ValidationError(message)


def function(tree,name,*,module_last_binding=False):
    if module_last_binding:
        values=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==name]
        require(len(values)==2,'exact two module-level native cosine definitions required')
        return values[-1]
    values=[node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name==name]
    require(len(values)==1,'one exact reviewed scalar source function required')
    return values[0]


def scalar_functions(warmup,cosine):
    """Review calls before compiling the two fixed vendor scalar functions."""
    for node in ast.walk(ast.Module(body=[warmup,cosine],type_ignores=[])):
        require(not isinstance(node,(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal,ast.With,ast.Try,ast.Raise)),
            'scalar fixture cannot import, perform IO or change global state')
        if isinstance(node,ast.Call):
            valid=(isinstance(node.func,ast.Name) and node.func.id in {'float','max'} or
                isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and
                node.func.value.id=='math' and node.func.attr in {'ceil','cos'})
            require(valid,'only reviewed scalar arithmetic calls permitted')
    namespace={'math':math,'__builtins__':{'float':float,'max':max,'int':int}}
    exec(compile(ast.Module(body=[warmup,cosine],type_ignores=[]),'verified-original::scalar-schedules','exec'),namespace)
    return namespace['get_warmup_steps'],namespace['_get_cosine_schedule_with_warmup_lr_lambda']


def audit(output):
    require(not output.exists(),'new immutable native optimizer audit required')
    ledger=json.loads((MATERIAL/'acquisition.json').read_bytes())
    require(ledger['state']=='complete-exact-public-dependency-files' and ledger['ref']=='sorokin/pip-install-unsloth-flash-patch' and
        ledger['version_number']==2 and ledger['expected_script_version_id']==272622465 and
        ledger['requests_reserved']==ledger['files_completed']==4 and ledger['model_calls']==ledger['source_program_executions']==ledger['paid_usd']==0 and
        [row['file_name'] for row in ledger['events']]==list(EXACT),'exact four-file public acquisition required')
    inventory={};sources={}
    require({p.relative_to(MATERIAL).as_posix() for p in MATERIAL.rglob('*') if p.is_file()}==set(EXACT)|{'acquisition.json'},
        'closed native optimizer material required')
    for row in ledger['events']:
        name=row['file_name'];path=MATERIAL/name
        require(row['state']=='retained' and row['download_host']=='www.kaggleusercontent.com' and
            row['path_kernel_version_ids']==[272622465] and row['sha256']==EXACT[name]==sha(path) and
            row['bytes']==path.stat().st_size,'pinned native optimizer source bytes differ')
        inventory[name]={'bytes':row['bytes'],'sha256':row['sha256']};sources[name]=path.read_text(encoding='utf-8')
    run=ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-training-inspect-003'
    native=verify(run/'execution-final/retrieved/gpu-preflight-result.zip',run/'package-l4')
    require(native['source_long_ttt_prerequisite_qualified'] is True,'completed independently read native preparation required')
    plan=json.loads((run/'package-l4/plan.json').read_bytes());args=plan['original_training_arguments']
    require(args['optim']=='adamw_torch' and args['learning_rate']==5e-5 and args['warmup_ratio']==.1 and
        args['warmup_steps']==0 and args['lr_scheduler_type']=='cosine' and args['num_train_epochs']==1 and
        args['per_device_train_batch_size']==args['gradient_accumulation_steps']==1 and
        args['max_grad_norm']==1 and args['weight_decay']==0 and args['bf16'] is True and args['fp16'] is False,
        'exact native full-epoch training arguments differ')
    existing=ROOT/'.irisx/nvarc-original/materials'
    paths={
        'training_args':existing/'qwen3-original-training-patches-20261002-001/transformers/training_args.py',
        'trainer':existing/'qwen3-original-training-environment-20261002-001/transformers/trainer.py',
        'adam':existing/'qwen3-original-training-source-20261002-001/torch/optim/adam.py'}
    texts={name:path.read_text(encoding='utf-8') for name,path in paths.items()}
    tree=ast.parse(texts['training_args']);cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='TrainingArguments')
    defaults={}
    for node in cls.body:
        if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) and node.target.id in {'adam_beta1','adam_beta2','adam_epsilon','label_smoothing_factor','torch_compile','dataloader_drop_last'}:
            require(isinstance(node.value,ast.Call),'native default field declaration required')
            defaults[node.target.id]=next(ast.literal_eval(item.value) for item in node.value.keywords if item.arg=='default')
    require(defaults=={'adam_beta1':.9,'adam_beta2':.999,'adam_epsilon':1e-8,'label_smoothing_factor':0.,'torch_compile':False,'dataloader_drop_last':False},
        'source default optimizer/smoothing/compile/drop policy differs')
    warmup=function(tree,'get_warmup_steps')
    cosine=function(ast.parse(sources['transformers/optimization.py']),'_get_cosine_schedule_with_warmup_lr_lambda',module_last_binding=True)
    warmup_fn,cosine_fn=scalar_functions(warmup,cosine)
    steps=plan['source_view_count'];warm=warmup_fn(SimpleNamespace(**args),steps)
    require(steps==128 and warm==13,'complete native epoch and ceil warmup required')
    factors=[cosine_fn(i,num_warmup_steps=warm,num_training_steps=steps,num_cycles=.5) for i in range(steps+1)]
    require(all(type(value) in (int,float) and math.isfinite(value) and 0<=value<=1 for value in factors) and
        factors[0]==factors[-1]==0 and factors[13]==1,'complete bounded native cosine schedule differs')
    rates=[args['learning_rate']*value for value in factors]
    require('"betas": (args.adam_beta1, args.adam_beta2)' in texts['trainer'] and
        'from torch.optim import AdamW' in texts['trainer'] and 'optimizer_cls = AdamW' in texts['trainer'],
        'native AdamW argument routing differs')
    for name in ('exp_avg','exp_avg_sq'):
        require(f'state["{name}"] = torch.zeros_like(' in texts['adam'],'native moment dtype/device inheritance differs')
    require('if self.gradient_state.sync_gradients:' in sources['accelerate/optimizer.py'] and
        'self.optimizer.step(closure)' in sources['accelerate/optimizer.py'] and
        'return torch.nn.utils.clip_grad_norm_(parameters, max_norm, norm_type=norm_type)' in sources['accelerate/accelerator.py'],
        'native synchronous optimizer/clipping delegate differs')
    require('total_norm = _get_total_norm(' in sources['torch/nn/utils/clip_grad.py'] and
        '_clip_grads_with_norm_(parameters, max_norm, total_norm, foreach)' in sources['torch/nn/utils/clip_grad.py'],
        'native whole-gradient clipping source differs')
    elements=528564224
    result={'format':'irisx/nvarc-native-ttt-optimizer-audit-v1','outcome':'complete-source-and-scalar-audit',
        'dependency_script_version_id':272622465,'acquisition_sha256':sha(MATERIAL/'acquisition.json'),
        'file_inventory':inventory,'existing_source_sha256':{name:sha(path) for name,path in paths.items()},
        'native_preparation_archive_sha256':native['archive_sha256'],'native_preparation_plan_digest':native['plan_digest'],
        'training_arguments':args,'default_arguments':defaults,'epoch_steps_from_fixed_data':steps,'warmup_steps':warm,
        'cosine_binding_policy':'last of two module-level definitions; default min_lr_rate 0.0',
        'reviewed_scalar_function_sha256':{node.name:hashlib.sha256(ast.get_source_segment(
            texts['training_args'] if node is warmup else sources['transformers/optimization.py'],node).encode()).hexdigest()
            for node in (warmup,cosine)},
        'scheduler_factors_for_indices_0_through_128':factors,'scheduler_rates_for_indices_0_through_128':rates,
        'first_optimizer_learning_rate':rates[0],'last_optimizer_learning_rate':rates[-2],
        'post_epoch_learning_rate':rates[-1],'first_zero_lr_step_still_updates_optimizer_moments':True,
        'trainable_bf16_bytes':elements*2,'two_adam_moments_bf16_bytes_source_derived':elements*4,
        'gradient_and_optimizer_runtime_verified':False,'optimizer_memory_runtime_measured':False,
        'full_native_long_ttt_completed':False,'executed_scalar_fixture_functions':2,'source_package_imports':0,
        'model_calls':0,'optimizer_constructions':0,'optimizer_steps':0,'generations':0,'teacher_calls':0,'external_calls':0,'paid_usd':0,
        'scope':'exact vendor scalar schedule/source routing and consumed native preprocessing; not a native training epoch or memory/time observation'}
    atomic(output,result)
    return {'outcome':result['outcome'],'proof_sha256':sha(output),'warmup_steps':warm,'optimizer_steps':0,
        'first_optimizer_learning_rate':rates[0],'last_optimizer_learning_rate':rates[-2]}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(audit(parser.parse_args().output)))
