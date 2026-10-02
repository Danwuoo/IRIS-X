"""Independently bind original training distribution/source bytes; no imports."""
from __future__ import annotations
import argparse
import ast
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.errors import ValidationError
from tools.acquire_nvarc_original_environment import FILES,PACKAGES

EXTRA={'accelerate':'1.11.0','trl':'0.22.2','datasets':'3.6.0','tokenizers':'0.21.4',
    'huggingface_hub':'0.36.0','safetensors':'0.6.2','numpy':'2.2.6','triton':'3.4.0',
    'torchao':'0.14.1','cut_cross_entropy':'25.1.1'}
GROUPS={
    'qwen3-historical-dependency-files-20261002-001':FILES,
    'qwen3-original-training-environment-20261002-001':[f'{k}-{v}.dist-info/METADATA' for k,v in EXTRA.items()]+[
        'accelerate/data_loader.py','trl/trainer/sft_trainer.py','transformers/trainer.py','unsloth_zoo/training_utils.py'],
    'qwen3-original-training-patches-20261002-001':['unsloth_zoo/compiler.py','unsloth/models/_utils.py',
        'trl/trainer/sft_config.py','transformers/trainer_pt_utils.py','transformers/training_args.py','unsloth/__init__.py'],
    'qwen3-original-training-state-20261002-001':['peft/utils/save_and_load.py','torch/nn/modules/module.py']}


def require(value,message):
    if not value:raise ValidationError(message)


def metadata_version(raw,name,version):
    header=BytesParser().parsebytes(raw)
    normalize=lambda value:re.sub(r'[-_.]+','-',value).lower()
    require(normalize(header['Name'] or '')==normalize(name) and header['Version']==version,
        'exact original distribution name/version required')
    return {'name':header['Name'],'version':header['Version']}


def audit(output):
    require(not output.exists(),'new immutable native training-environment audit required')
    materials=ROOT/'.irisx/nvarc-original/materials';files={};bindings={}
    for group,names in GROUPS.items():
        folder=materials/group;ledger=json.loads((folder/'acquisition.json').read_bytes())
        require(ledger['state']=='complete-exact-public-dependency-files' and ledger['version_number']==2 and
            ledger['expected_script_version_id']==272622465 and ledger['requests_reserved']==ledger['files_completed']==len(names) and
            [e['file_name'] for e in ledger['events']]==names and ledger['model_calls']==ledger['source_program_executions']==ledger['paid_usd']==0,
            'complete exact-version zero-execution acquisition required')
        bindings[group]=sha(folder/'acquisition.json')
        for event in ledger['events']:
            path=folder/event['file_name']
            require(event['state']=='retained' and event['path_kernel_version_ids']==[272622465] and
                event['download_host']=='www.kaggleusercontent.com' and path.stat().st_size==event['bytes'] and sha(path)==event['sha256'],
                'exact original dependency bytes/version required')
            files[event['file_name']]={'path':path,'sha256':event['sha256'],'bytes':event['bytes']}
    distributions={}
    for name,version in {**PACKAGES,**EXTRA}.items():
        distributions[name]=metadata_version(files[f'{name}-{version}.dist-info/METADATA']['path'].read_bytes(),name,version)
    modules={name:ast.parse(item['path'].read_text(encoding='utf-8')) for name,item in files.items() if name.endswith('.py')}
    config_text=files['trl/trainer/sft_config.py']['path'].read_text(encoding='utf-8')
    config=next(node for node in modules['trl/trainer/sft_config.py'].body if isinstance(node,ast.ClassDef) and node.name=='SFTConfig')
    maximum=next(node for node in config.body if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) and node.target.id=='max_length')
    require(isinstance(maximum.value,ast.Call),'native maximum-length configuration required')
    default=next(ast.literal_eval(k.value) for k in maximum.value.keywords if k.arg=='default')
    require(default==1024 and 'max_seq_length' not in config_text,'original TRL default/legacy length spelling differs')
    state_text=files['peft/utils/save_and_load.py']['path'].read_text(encoding='utf-8')
    state=next(node for node in modules['peft/utils/save_and_load.py'].body if isinstance(node,ast.FunctionDef) and node.name=='get_peft_model_state_dict')
    selected=ast.get_source_segment(state_text,state)
    require('state_dict = model.state_dict()' in selected and '"lora_" in k' in selected and
        'k.replace(f".{adapter_name}", ""): v' in selected and '.clone(' not in selected and 'deepcopy(' not in selected,
        'original returned adapter tensor-reference policy differs')
    module_text=files['torch/nn/modules/module.py']['path'].read_text(encoding='utf-8')
    require('The returned object is a shallow copy. It contains references' in module_text,
        'original PyTorch shallow state-dictionary policy differs')
    notebook=ROOT/'.irisx/arc-agi-2/qwen35-nvarc/source/kaggle-qwen/arc2-qwen3-unsloth-flash-lora-batch4-queue.ipynb'
    require(sha(notebook)=='506b85db66f9949022e87935ccb06a73fd78cb690883bd600bfb5c7d36c2b3af',
        'original notebook binding differs')
    solver=next(''.join(c['source']).split('\n',1)[1] for c in json.loads(notebook.read_bytes())['cells']
        if ''.join(c.get('source',[])).startswith('%%writefile arc_solver.py'))
    require('default_weights = get_peft_model_state_dict(model, adapter_name="default")' in solver and
        'default_weights.copy()' in solver and 'max_seq_length = 8192' in solver,
        'original declared context/default-reset source differs')
    require('default_weights = {k: v.clone().detach() for k, v in default_weights.items()}' in solver,
        'original independent snapshot clone policy differs')
    result={'format':'irisx/nvarc-original-training-environment-audit-v1','outcome':'complete-exact-source-audit',
        'dependency_script_version_id':272622465,'original_notebook_sha256':sha(notebook),
        'acquisition_bindings':bindings,'file_inventory':{name:{k:v for k,v in item.items() if k!='path'} for name,item in files.items()},
        'verified_file_count':len(files),'parsed_python_modules':len(modules),'distribution_versions':distributions,
        'original_declared_max_sequence_length':8192,'native_trl_default_max_length':default,
        'native_effective_context_runtime_verified':False,
        'source_adapter_state_returns_tensor_references':True,'original_default_reset_uses_dictionary_shallow_copy':True,
        'original_snapshot_clones_and_detaches_every_tensor_before_dictionary_copy':True,
        'actual_original_adapter_snapshot_aliasing_runtime_verified':False,
        'source_state_function_ast_sha256':hashlib.sha256(ast.dump(state,include_attributes=False).encode()).hexdigest(),
        'complete_environment_file_inventory_verified':False,'source_package_imports':0,'source_program_executions':0,
        'model_calls':0,'optimizer_steps':0,'generation_calls':0,'teacher_calls':0,'external_calls':0,'paid_usd':0,
        'proof_scope':'exact installed metadata and native training/config/state source; effective patched Trainer and actual adapter behavior remain unobserved'}
    atomic(output,result)
    return {'outcome':result['outcome'],'proof_sha256':sha(output),'verified_files':len(files),
        'verified_distributions':len(distributions),'model_calls':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(audit(parser.parse_args().output)))
