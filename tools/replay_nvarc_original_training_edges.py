"""Explicit source-level constructor/state fixtures, without original model work."""
from __future__ import annotations
import argparse
import ast
from dataclasses import dataclass
import dataclasses
from functools import wraps
import inspect
import json
from pathlib import Path
import sys
import types
import warnings

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.errors import ValidationError


def source_snapshot(raw,notebook_solver):
    tree=ast.parse(notebook_solver)
    worker=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='worker')
    candidates=[n for n in worker.body if isinstance(n,ast.Assign) and len(n.targets)==1 and
        isinstance(n.targets[0],ast.Name) and n.targets[0].id=='default_weights' and isinstance(n.value,ast.DictComp)]
    if len(candidates)!=1 or ast.dump(candidates[0],include_attributes=False)!=ast.dump(ast.parse(
            'default_weights = {k: v.clone().detach() for k, v in default_weights.items()}').body[0],include_attributes=False):
        raise ValidationError('exact original independent snapshot assignment required')
    scope={'default_weights':raw}
    exec(compile(ast.Module(body=candidates,type_ignores=[]),'original-worker::snapshot-assignment','exec'),scope)
    return scope['default_weights']


def replay(output):
    if output.exists():raise ValidationError('new immutable source-edge fixture required')
    import torch
    from packaging.version import Version
    materials=ROOT/'.irisx/nvarc-original/materials'
    environment=ROOT/'.irisx/nvarc-original/manifests/original-training-environment-20261002-002/result.json'
    if sha(environment)!='bf0f748811d96c110152ab0f38e203a080e3252b7e05b6772441d281520b368a':
        raise ValidationError('exact native source/environment audit required')
    binding=json.loads(environment.read_bytes())
    state_path=materials/'qwen3-original-training-state-20261002-001/peft/utils/save_and_load.py'
    if sha(state_path)!=binding['file_inventory']['peft/utils/save_and_load.py']['sha256']:
        raise ValidationError('exact PEFT state source required')
    state=next(n for n in ast.parse(state_path.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='get_peft_model_state_dict')
    namespace={'PeftType':types.SimpleNamespace(LORA='LORA',ADALORA='ADALORA',TRAINABLE_TOKENS='TRAINABLE_TOKENS'),
        'AuxiliaryTrainingWrapper':type('ArtificialUnusedAuxiliaryWrapper',(),{}),'warnings':warnings,
        'EMBEDDING_LAYER_NAMES':['embed_tokens','lm_head']}
    exec(compile(ast.Module(body=[state],type_ignores=[]),str(state_path)+'::get_peft_model_state_dict','exec'),namespace)
    class ArtificialTensorModule(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lora_A=torch.nn.ModuleDict({'default':torch.nn.Linear(2,2,bias=False).to(dtype=torch.bfloat16)})
            self.peft_config={'default':types.SimpleNamespace(peft_type='LORA',bias='none',use_dora=False,target_modules=['q_proj'])}
    tensor_module=ArtificialTensorModule();parameter=tensor_module.lora_A['default'].weight
    # Embedding save routing is excluded from this explicit projection-only fixture.
    snapshot=namespace['get_peft_model_state_dict'](tensor_module,save_embedding_layers=False)
    if set(snapshot)!= {'lora_A.weight'}:raise ValidationError('original state fixture key mapping differs')
    notebook=ROOT/'.irisx/arc-agi-2/qwen35-nvarc/source/kaggle-qwen/arc2-qwen3-unsloth-flash-lora-batch4-queue.ipynb'
    if sha(notebook)!=binding['original_notebook_sha256']:raise ValidationError('exact original snapshot notebook required')
    solver=next(''.join(c['source']).split('\n',1)[1] for c in json.loads(notebook.read_bytes())['cells']
        if ''.join(c.get('source',[])).startswith('%%writefile arc_solver.py'))
    defaults=source_snapshot(snapshot,solver)
    saved=snapshot['lora_A.weight'];cloned=defaults['lora_A.weight'];before=float(saved[0,0].detach())
    if saved.data_ptr()!=parameter.data_ptr():raise ValidationError('expected source shallow projection-state storage differs')
    if cloned.data_ptr()==parameter.data_ptr() or cloned.requires_grad:
        raise ValidationError('original cloned/detached default snapshot fixture differs')
    with torch.no_grad():parameter[0,0].add_(1)
    after=float(parameter[0,0].detach())
    if after==before or float(snapshot.copy()['lora_A.weight'][0,0].detach())!=after or float(cloned[0,0].detach())!=before:
        raise ValidationError('original dictionary-copy reference fixture differs')
    if float(defaults.copy()['lora_A.weight'][0,0])!=before:
        raise ValidationError('original cloned default dictionary preserves baseline required')
    with torch.no_grad():parameter[0,0].copy_(cloned[0,0])
    # Replay the literal compatibility wrapper with explicit dependency/sink stubs.
    trainer_path=materials/'qwen3-original-training-source-20261002-001/unsloth/trainer.py'
    policy=ROOT/'.irisx/nvarc-original/manifests/original-ttt-policy-20261002-003/result.json'
    if sha(policy)!='3a061806fd40202a4494ce5f35a46d3b6be8b8018990487f59d8167df83ae31f':
        raise ValidationError('exact original target/Trainer policy audit required')
    if sha(trainer_path)!=json.loads(policy.read_bytes())['file_sha256']['unsloth/trainer.py']:
        raise ValidationError('exact original Trainer wrapper source required')
    tree=ast.parse(trainer_path.read_bytes())
    wrapper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_backwards_compatible_trainer')
    arguments=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='UnslothTrainingArguments')
    class ArtificialTrainingArguments:pass
    @dataclass
    class ArtificialSFTConfig(ArtificialTrainingArguments):
        max_length:int=1024
        dataset_text_field:str='text'
        seed:int=42
    class ArtificialTrainerSink:
        def __init__(self,model,args=None,processing_class=None):
            self.observed_args=args;self.processing_class=processing_class
    namespace={'TrainingArguments':ArtificialSFTConfig,'dataclasses':dataclasses,'wraps':wraps,
        'inspect':inspect,'Version':Version,'trl':types.SimpleNamespace(__version__='0.22.2')}
    exec(compile(ast.Module(body=[arguments,wrapper],type_ignores=[]),str(trainer_path)+'::source-fixtures','exec'),namespace)
    args=namespace['UnslothTrainingArguments'](seed=42)
    initializer=namespace['_backwards_compatible_trainer'](ArtificialTrainerSink,ArtificialSFTConfig)
    sink=ArtificialTrainerSink.__new__(ArtificialTrainerSink)
    stub=types.ModuleType('transformers');stub.TrainingArguments=ArtificialTrainingArguments
    previous=sys.modules.get('transformers');sys.modules['transformers']=stub
    try:initializer(sink,model='artificial-no-model',args=args,tokenizer='artificial-tokenizer',max_seq_length=8192,dataset_text_field='text')
    finally:
        if previous is None:del sys.modules['transformers']
        else:sys.modules['transformers']=previous
    if sink.observed_args is not args or sink.observed_args.max_length!=1024 or sink.processing_class!='artificial-tokenizer':
        raise ValidationError('original existing-argument wrapper fixture differs')
    result={'format':'irisx/nvarc-original-training-edge-fixtures-v1','outcome':'complete-explicit-source-fixtures',
        'environment_audit_sha256':sha(environment),'target_policy_sha256':sha(policy),
        'state_source_sha256':sha(state_path),'trainer_source_sha256':sha(trainer_path),'torch':torch.__version__,
        'state_fixture':{'actual_original_adapter':False,'projection_only':True,'save_embedding_layers_override':False,
            'parameter_dtype':'bfloat16','manual_perturbed_elements':1,'parameter_before':before,'parameter_after':after,
            'returned_snapshot_shares_parameter_storage':True,'dictionary_copy_preserves_shared_tensor':True,
            'original_default_snapshot_clones_and_detaches_each_tensor':True,
            'cloned_default_dictionary_copy_preserves_original_scalar':True,
            'separate_clone_preserves_original_scalar':True,'fixture_scalar_restored':True},
        'constructor_fixture':{'actual_original_trainer':False,'dependency_classes_and_trainer_sink':'explicit artificial stubs',
            'declared_legacy_max_seq_length':8192,'existing_argument_max_length_before':1024,
            'existing_argument_max_length_after':sink.observed_args.max_length,'same_argument_object_retained':True,
            'tokenizer_kwarg_renamed_to_processing_class':True,'effective_original_patched_context_runtime_verified':False},
        'original_adapter_task_reset_runtime_verified':False,'model_forwards':0,'optimizer_steps':0,'generation_calls':0,
        'teacher_calls':0,'external_calls':0,'generated_program_executions':0,'paid_usd':0,
        'proof_scope':'literal trusted source functions on explicitly artificial constructor/tensor fixtures; not original GPU adapter, patched Trainer preprocessing or task-reset behavior'}
    atomic(output,result)
    return {'outcome':result['outcome'],'proof_sha256':sha(output),'model_forwards':0,'optimizer_steps':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(replay(parser.parse_args().output)))
