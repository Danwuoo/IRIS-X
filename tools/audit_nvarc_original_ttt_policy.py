"""Read exact original training code; distinguish source inference from runtime."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.errors import ValidationError


def require(value,message):
    if not value:raise ValidationError(message)


def literal_dictionary(node):
    if isinstance(node,ast.Dict):
        result=ast.literal_eval(node)
        require(len(result)==len(node.keys),'unique source literal dictionary keys required')
        return result
    require(isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='dict' and
        node.args==[] and all(keyword.arg is not None for keyword in node.keywords),
        'source literal dictionary constructor required')
    result={keyword.arg:ast.literal_eval(keyword.value) for keyword in node.keywords}
    require(len(result)==len(node.keywords),'unique source literal dictionary keys required')
    return result


def audit(output):
    require(not output.exists(),'new immutable original TTT policy observation required')
    materials=ROOT/'.irisx/nvarc-original/materials'
    expected=[['torch/optim/adam.py','torch/optim/adamw.py','unsloth/trainer.py','unsloth/models/llama.py'],
        ['unsloth/models/loader.py']]
    files={};bindings={}
    for suffix,names in zip(('001','002'),expected):
        folder=materials/('qwen3-original-training-source-20261002-'+suffix)
        ledger=json.loads((folder/'acquisition.json').read_bytes())
        require(ledger['state']=='complete-exact-public-dependency-files' and ledger['version_number']==2 and
            ledger['expected_script_version_id']==272622465 and ledger['requests_reserved']==ledger['files_completed']==len(names) and
            [row['file_name'] for row in ledger['events']]==names and ledger['model_calls']==ledger['source_program_executions']==ledger['paid_usd']==0,
            'exact zero-execution original training-source acquisition required')
        bindings[folder.name]=sha(folder/'acquisition.json')
        for row in ledger['events']:
            path=folder/row['file_name']
            require(row['path_kernel_version_ids']==[272622465] and row['state']=='retained' and
                row['download_host']=='www.kaggleusercontent.com' and path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],
                'exact original training-source bytes/version differ')
            files[row['file_name']]={'path':path,'sha256':row['sha256'],'text':path.read_text(encoding='utf-8')}
    notebook=ROOT/'.irisx/arc-agi-2/qwen35-nvarc/source/kaggle-qwen/arc2-qwen3-unsloth-flash-lora-batch4-queue.ipynb'
    manifest=json.loads((ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes())
    require(sha(notebook)==manifest['notebooks']['qwen']['sha256'],'exact original notebook bytes differ')
    cells=json.loads(notebook.read_bytes())['cells']
    solver=next(''.join(cell['source']).split('\n',1)[1] for cell in cells
        if ''.join(cell.get('source',[])).startswith('%%writefile arc_solver.py'))
    module=ast.parse(solver);worker=next(node for node in module.body if isinstance(node,ast.FunctionDef) and node.name=='worker')
    dictionaries={node.targets[0].id:literal_dictionary(node.value) for node in ast.walk(worker) if isinstance(node,ast.Assign) and
        len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('peft_params','train_args')}
    peft,trainer=dictionaries['peft_params'],dictionaries['train_args']
    require(peft['r']==256 and peft['lora_alpha']==32 and peft['use_rslora'] is True and peft['use_gradient_checkpointing'] is False and
        trainer['optim']=='adamw_torch' and trainer['gradient_checkpointing'] is False and trainer['bf16'] is True,
        'frozen original TTT recipe differs')
    projections=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']
    require(peft['target_modules']==projections+['embed_tokens','lm_head'],'original nine target declarations differ')
    llama=files['unsloth/models/llama.py']['text'];loader=ast.parse(files['unsloth/models/loader.py']['text'])
    language=next(node for node in loader.body if isinstance(node,ast.ClassDef) and node.name=='FastLanguageModel')
    require(any(isinstance(node,ast.Name) and node.id=='FastLlamaModel' for node in language.bases) and
        not any(isinstance(node,ast.FunctionDef) and node.name=='get_peft_model' for node in language.body),
        'original FastLanguageModel inherited adapter route differs')
    library=ast.parse(llama);base=next(node for node in library.body if isinstance(node,ast.ClassDef) and node.name=='FastLlamaModel')
    adapter=next(node for node in base.body if isinstance(node,ast.FunctionDef) and node.name=='get_peft_model')
    loop=next(node for node in ast.walk(adapter) if isinstance(node,ast.For) and isinstance(node.target,ast.Name) and
        node.target.id=='module' and isinstance(node.iter,ast.Name) and node.iter.id=='target_modules')
    segment=ast.get_source_segment(llama,loop)
    require(all(value in segment for value in ('module == "lm_head"','module == "embed_tokens"',
        'modules_to_save.append("lm_head")','modules_to_save.append("embed_tokens")','final_modules.append(module)')) and
        'target_modules      = final_modules' in llama and 'modules_to_save     = modules_to_save' in llama,
        'original complete embedding/head save-module rewrite differs')
    require('if param.dtype == torch.float32:' in solver and 'param.data = param.data.to(torch.bfloat16)' in solver and
        'model = FastLanguageModel.for_training(model)' in solver,'original BF16 snapshot/training transition differs')
    training=next(node for node in base.body if isinstance(node,ast.FunctionDef) and node.name=='for_training')
    require([arg.arg for arg in training.args.args]==['model','use_gradient_checkpointing'] and
        len(training.args.defaults)==1 and ast.literal_eval(training.args.defaults[0]) is True and
        'module.gradient_checkpointing = use_gradient_checkpointing' in ast.get_source_segment(llama,training),
        'original for_training checkpoint-enable default differs')
    adam=files['torch/optim/adam.py']['text'];unsloth_trainer=files['unsloth/trainer.py']['text']
    require('state["exp_avg"] = torch.zeros_like(' in adam and 'state["exp_avg_sq"] = torch.zeros_like(' in adam and
        'if embedding_learning_rate is None: return super().create_optimizer()' in unsloth_trainer,
        'original default optimizer state/trainer route differs')
    checkpoint=materials/'qwen3-published-sft139-20261002-001'
    checkpoint_proof=json.loads((checkpoint/'independent-verification.json').read_bytes())
    config_path=checkpoint/'model/config.json'
    require(checkpoint_proof['material_digest']=='sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03' and
        sha(config_path)==checkpoint_proof['inventory']['config.json']['sha256'] and
        config_path.stat().st_size==checkpoint_proof['inventory']['config.json']['bytes'],
        'independently verified exact published checkpoint configuration required')
    config=json.loads(config_path.read_bytes())
    hidden=config['hidden_size'];head=config['head_dim'];q=config['num_attention_heads']*head;kv=config['num_key_value_heads']*head
    intermediate=config['intermediate_size'];layers=config['num_hidden_layers'];vocab=config['vocab_size'];rank=peft['r']
    projected=rank*layers*((hidden+q)+(hidden+kv)*2+(q+hidden)+(hidden+intermediate)*3)
    save_modules=2*vocab*hidden;inferred=projected+save_modules
    compatibility_path=ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-adapter-material-001/result.json'
    compatibility=json.loads(compatibility_path.read_bytes())
    require(compatibility['trainable_parameter_count']==projected+2*rank*(vocab+hidden) and
        compatibility['trainable_parameters_by_dtype']=={'torch.float32':529801216},'retained compatibility topology differs')
    result={'format':'irisx/nvarc-original-ttt-source-policy-v1','outcome':'complete-source-audit',
        'original_notebook_sha256':sha(notebook),'dependency_script_version_id':272622465,'acquisition_bindings':bindings,
        'published_checkpoint_material_digest':checkpoint_proof['material_digest'],
        'published_checkpoint_proof_sha256':sha(checkpoint/'independent-verification.json'),
        'published_checkpoint_config_sha256':sha(config_path),'compatibility_observation_sha256':sha(compatibility_path),
        'file_sha256':{name:row['sha256'] for name,row in files.items()},'peft_parameters':peft,'training_arguments':trainer,
        'projection_lora_target_count_inferred':layers*7,'full_save_modules':['embed_tokens','lm_head'],
        'projection_lora_parameters_inferred':projected,'save_module_parameters_inferred':save_modules,
        'total_trainable_parameters_inferred':inferred,'trainable_count_runtime_observed':False,
        'source_snapshot_parameter_cast':'all float32 parameters to bfloat16 before retained default snapshot',
        'for_training_default_gradient_checkpointing':True,'notebook_training_call_overrides_default':False,
        'original_effective_checkpoint_backend_runtime_verified':False,
        'adam_state_source_policy':'zeros_like current parameter; actual trainer-time parameter/moment dtype remains unobserved',
        'target_rewrite_ast_sha256':hashlib.sha256(ast.dump(loop,include_attributes=False).encode()).hexdigest(),
        'compatibility_observed_trainable_parameters':compatibility['trainable_parameter_count'],
        'compatibility_observed_parameter_dtype':'float32','compatibility_topology_matches_original_source':False,
        'compatibility_long_task_002_remains_inert':True,'model_calls':0,'optimizer_steps':0,'generated_program_executions':0,
        'source_package_imports':0,'external_calls':0,'paid_usd':0,
        'proof_scope':'exact source policy and parameter-count inference; not an actual original Unsloth adapter or training observation'}
    atomic(output,result)
    return {'outcome':result['outcome'],'proof_sha256':sha(output),'source_trainable_count_inferred':inferred,
        'compatibility_trainable_count_observed':compatibility['trainable_parameter_count'],'model_calls':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(audit(parser.parse_args().output)))
