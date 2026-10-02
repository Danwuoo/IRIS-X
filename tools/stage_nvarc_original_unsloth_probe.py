"""Original dependency GPU prefill/cache comparison, with four observed calls."""
from __future__ import annotations
import argparse
import ast
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
from tools.acquire_nvarc_original_environment import DOCKER,REF,PACKAGES
from tools.stage_nvarc_original_environment import binding,TOKENIZER,BINDING

FORMAT='irisx/nvarc-original-qwen3-unsloth-probe-v1'
MODEL_REF='sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1'
MATERIAL='sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03'
IDS=[14,11,10,0,1,15,14,12,10,1,0,15]
WORKER='''import importlib.metadata as metadata
import json
from pathlib import Path
import sys,time
mode,model_path,output_path,dependency_path=sys.argv[1:]
output=Path(output_path);dependency=Path(dependency_path).resolve()
expected=__VERSIONS__;ids=__IDS__
versions={name:metadata.version(name) for name in expected}
if versions!=expected:raise RuntimeError('original distribution versions differ')
import torch
if not Path(torch.__file__).resolve().is_relative_to(dependency):raise RuntimeError('Torch import escapes original output')
events=[];active=None;original_call=torch.nn.Module._call_impl
def bounded_call(self,*args,**kwargs):
    if type(self).__name__=='Qwen3ForCausalLM':
        if active is None:raise RuntimeError('model constructor attempted an unbudgeted forward')
        values=kwargs.get('input_ids',args[0] if args else None)
        actual=values.detach().cpu().tolist() if values is not None else None
        if len(events)>=2 or actual!=[ids if len(events)==0 else [0]]:
            raise RuntimeError('exact two-call original input budget differs')
        events.append({'stage':active,'input_ids':actual,'outer_forwards_reserved':1,
            'input_tokens_reserved':len(actual[0])})
        (output/(mode+'-ledger.json')).write_text(json.dumps(events,separators=(',',':')),encoding='utf-8')
    return original_call(self,*args,**kwargs)
torch.nn.Module._call_impl=bounded_call
started=time.monotonic()
if mode=='unsloth':
    from unsloth import FastLanguageModel
    model,tokenizer=FastLanguageModel.from_pretrained(model_name=model_path,full_finetuning=False,
        load_in_4bit=False,local_files_only=True,use_gradient_checkpointing=False,max_seq_length=8192,fast_inference=False)
    FastLanguageModel.for_inference(model)
else:
    from transformers import AutoModelForCausalLM,AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(model_path,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(model_path,local_files_only=True,torch_dtype=torch.bfloat16,
        attn_implementation='sdpa').to('cuda:0')
if tokenizer.encode('<|im_start|>user\\n01<|im_end|><|im_start|>assistant\\n10<|im_end|>')!=ids:
    raise RuntimeError('exact original tokenizer sequence differs')
if model.config.model_type!='qwen3' or model.config.vocab_size!=16 or model.config.tie_word_embeddings:
    raise RuntimeError('original untied sixteen-row Qwen3 checkpoint required')
if model.get_input_embeddings().weight.data_ptr()==model.get_output_embeddings().weight.data_ptr():
    raise RuntimeError('original separate embedding/head storage required')
for parameter in model.parameters():
    if parameter.dtype==torch.float32:parameter.data=parameter.data.to(torch.bfloat16)
parameter_dtypes=sorted({str(parameter.dtype) for parameter in model.parameters()})
if parameter_dtypes!=['torch.bfloat16']:raise RuntimeError('original post-load BF16 parameter policy required')
model.eval();torch.cuda.reset_peak_memory_stats();vectors=[];shapes=[]
with torch.inference_mode():
    active='prefill';first=model(input_ids=torch.tensor([ids],device='cuda:0'),use_cache=True)
    vectors.append(first.logits[0,-1].float().cpu().tolist());shapes.append(list(first.logits.shape))
    active='cached-token';second=model(input_ids=torch.tensor([[0]],device='cuda:0'),past_key_values=first.past_key_values,use_cache=True)
    vectors.append(second.logits[0,-1].float().cpu().tolist());shapes.append(list(second.logits.shape))
active=None
if len(events)!=2 or any(len(row)!=16 or not all(__import__('math').isfinite(x) for x in row) for row in vectors):
    raise RuntimeError('finite exact original numeric vectors/cost required')
result={'mode':mode,'versions':versions,'torch':torch.__version__,'cuda':torch.version.cuda,
    'python':sys.version.split()[0],'vectors':vectors,'output_shapes':shapes,'outer_forwards':len(events),
    'input_tokens':sum(row['input_tokens_reserved'] for row in events),'untied_storage_observed':True,
    'model_class':type(model).__name__,'parameter_dtypes':parameter_dtypes,'cuda_peak_allocated_bytes':torch.cuda.max_memory_allocated(),
    'wall_seconds':time.monotonic()-started,'optimizer_steps':0,'generations':0,'teacher_calls':0}
(output/(mode+'-result.json')).write_text(json.dumps(result,sort_keys=True,separators=(',',':')),encoding='utf-8')
'''


def require(value,message):
    if not value:raise ValidationError(message)


def inventory():
    proof=json.loads((TOKENIZER.parent/'independent-verification.json').read_bytes())
    entries=proof['inventory'];require(len(entries)==10 and digest_value(entries)==MATERIAL and
        proof['material_digest']==MATERIAL,'exact published independently verified model inventory required')
    return entries


def prerequisites():
    proof=json.loads((ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-environment-002/independent-verification.json').read_bytes())
    require(proof['outcome']=='complete' and proof['runtime_observation']['versions']==PACKAGES and proof['model_calls']==0,
        'complete original CPU import/tokenizer prerequisite required')
    return sha(ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-environment-002/independent-verification.json')


def render(run,payloads,hashes):
    source=(ROOT/'tools/nvarc_original_unsloth_probe.py.tmpl').read_text(encoding='utf-8')
    for key,value in {'__RUN__':json.dumps(run),'__PAYLOADS__':json.dumps(payloads),'__HASHES__':json.dumps(hashes),
        '__HARDWARE_HELPER__':(ROOT/'src/irisx/arc_nvarc_hardware.py').read_text(encoding='utf-8')}.items():source=source.replace(key,value)
    compile(source,'original-unsloth-numerics','exec');return source


def stage(package,run):
    require(not package.exists() and re.fullmatch(r'nvarc-original-qwen3-unsloth-probe-\d{3}',run),'new immutable original Unsloth probe required')
    entries=inventory();proof=binding();worker=WORKER.replace('__VERSIONS__',repr(PACKAGES)).replace('__IDS__',repr(IDS))
    compile(worker,'original-unsloth-worker','exec')
    plan={'format':FORMAT,'approved':True,'owner_decision':'Decision 0054','run_id':run,'kernel_id':'danielwuu/'+run,
        'maximum_notebook_wall_seconds':1200,'maximum_child_wall_seconds':450,'maximum_outer_forwards':4,
        'maximum_input_tokens':26,'maximum_optimizer_steps':0,'maximum_generations':0,'maximum_teacher_calls':0,
        'maximum_paid_usd':0,'retain_export':False,'docker_image':DOCKER,'dependency_ref':REF,
        'dependency_binding_sha256':sha(BINDING),'cpu_environment_proof_sha256':prerequisites(),
        'model_material_digest':MATERIAL,'model_instance_version_id':627758,'model_sources':[MODEL_REF],
        'competition_sources':['arc-prize-2026-arc-agi-2'],'competition_files_opened':0,
        'hardware_gate':'four distinct BF16 L4s; sequential isolated rank-zero workers',
        'input_ids':IDS,'cached_input_ids':[0],'transient_tensorflow_uninstall':True,
        'lora_adaptation':False,'historical_full_solver_parity':False,'correctness_scored':False,
        'comparison':'reported original Unsloth versus same-runtime SDPA prefill/cache logits; no ARC score'}
    raw={'plan':canonical_bytes(plan,newline=True),'binding':canonical_bytes(proof,newline=True),
        'model_inventory':canonical_bytes(entries,newline=True),'worker':worker.encode('utf-8')}
    payloads={k:base64.b64encode(v).decode() for k,v in raw.items()};hashes={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    (package/'kernel').mkdir(parents=True);(package/'plan.json').write_bytes(raw['plan'])
    atomic(package/'kernel/notebook.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{
        'display_name':'Python 3','language':'python','name':'python3'}},'cells':[{'cell_type':'code','execution_count':None,
        'metadata':{},'outputs':[],'source':render(run,payloads,hashes).splitlines(keepends=True)}]})
    atomic(package/'kernel/kernel-metadata.json',{'id':plan['kernel_id'],'title':run,'code_file':'notebook.ipynb',
        'language':'python','kernel_type':'notebook','is_private':True,'enable_gpu':True,'enable_internet':False,
        'docker_image':DOCKER,'dataset_sources':[],'kernel_sources':[REF],
        'competition_sources':plan['competition_sources'],'model_sources':plan['model_sources']})
    atomic(package/'stage-summary.json',{'run_id':run,'plan_digest':digest_value(plan),'payload_sha256':hashes,
        'inventory':{p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    summary=json.loads((package/'stage-summary.json').read_bytes());plan=json.loads((package/'plan.json').read_bytes())
    require({p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file() and p.name!='stage-summary.json'}==summary['inventory'] and
        digest_value(plan)==summary['plan_digest'],'closed immutable original numerical package differs')
    require(plan['format']==FORMAT and plan['owner_decision']=='Decision 0054' and plan['approved'] is True and
        all(type(plan[k]) is int and plan[k]==v for k,v in {'maximum_notebook_wall_seconds':1200,'maximum_child_wall_seconds':450,
            'maximum_outer_forwards':4,'maximum_input_tokens':26,'maximum_optimizer_steps':0,'maximum_generations':0,
            'maximum_teacher_calls':0,'maximum_paid_usd':0,'competition_files_opened':0}.items()) and
        plan['input_ids']==IDS and plan['cached_input_ids']==[0] and plan['lora_adaptation'] is False and
        plan['retain_export'] is False and plan['model_material_digest']==MATERIAL,'exact four-forward zero-training bounds differ')
    source=''.join(json.loads((package/'kernel/notebook.ipynb').read_bytes())['cells'][0]['source'])
    values={node.targets[0].id:ast.literal_eval(node.value) for node in ast.parse(source).body if isinstance(node,ast.Assign)
        and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'RUN','PAYLOADS','HASHES'}}
    require(values['RUN']==plan['run_id'] and source==render(values['RUN'],values['PAYLOADS'],values['HASHES']) and
        values['HASHES']==summary['payload_sha256'] and set(values['PAYLOADS'])=={'plan','binding','model_inventory','worker'},
        'exact original numerical template differs')
    raw={k:base64.b64decode(v,validate=True) for k,v in values['PAYLOADS'].items()}
    require(all(len(v)<2*1024**2 and hashlib.sha256(v).hexdigest()==values['HASHES'][k] for k,v in raw.items()) and
        raw['plan']==(package/'plan.json').read_bytes() and json.loads(raw['binding'])==binding() and
        json.loads(raw['model_inventory'])==inventory() and
        raw['worker']==WORKER.replace('__VERSIONS__',repr(PACKAGES)).replace('__IDS__',repr(IDS)).encode('utf-8') and
        plan['cpu_environment_proof_sha256']==prerequisites() and plan['dependency_binding_sha256']==sha(BINDING),
        'exact original material/worker/prerequisite payload differs')
    meta=json.loads((package/'kernel/kernel-metadata.json').read_bytes())
    require(meta['id']==plan['kernel_id']=='danielwuu/'+plan['run_id'] and meta['title']==plan['run_id'] and
        meta['is_private'] is True and meta['enable_gpu'] is True and meta['enable_internet'] is False and
        meta['docker_image']==plan['docker_image']==DOCKER and meta['dataset_sources']==[] and meta['kernel_sources']==[REF] and
        meta['competition_sources']==plan['competition_sources']==['arc-prize-2026-arc-agi-2'] and
        meta['model_sources']==plan['model_sources']==[MODEL_REF],'private exact original GPU transport differs')
    return {'run_id':plan['run_id'],'plan_digest':summary['plan_digest'],'offline_package_verified':True,
        'external_calls':0,'maximum_outer_forwards':4,'maximum_input_tokens':26,'maximum_generations':0}


def verify_archive(path,package):
    checked=preflight(package);plan=json.loads((package/'plan.json').read_bytes());content={}
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist();require(len(names)==len(set(names)) and sum(row.file_size for row in archive.infolist())<=8*1024**2,
            'closed bounded original numerical archive required')
        index=json.loads(archive.read('manifest.json'))
        require(len(index['members'])==len({row['path'] for row in index['members']}) and
            index['run_id']==plan['run_id'] and index['plan_digest']==checked['plan_digest'] and
            set(names)=={row['path'] for row in index['members']}|{'manifest.json'},'exact original numerical archive/plan differs')
        for row in index['members']:
            body=archive.read(row['path']);require(len(body)==row['bytes'] and hashlib.sha256(body).hexdigest()==row['sha256'],
                'original numerical archive member differs');content[row['path']]=body
    def read(name):return json.loads(content[name])
    require(read('plan.json')==plan and read('payload-bindings.json')==json.loads((package/'stage-summary.json').read_bytes())['payload_sha256'],
        'returned exact numerical payload differs')
    terminal=read('terminal.json');require(terminal['contains_evaluator_truth'] is False and terminal['run_id']==plan['run_id'] and
        type(terminal['wall_seconds']) in (int,float) and math.isfinite(terminal['wall_seconds']) and
        0<=terminal['wall_seconds']<=1200 and all(type(terminal[k]) is int and terminal[k]==0 for k in
            ('optimizer_steps','generations','teacher_calls','paid_usd')),'original numerical terminal cost differs')
    calls=tokens=0;results={}
    for mode in ('reference','unsloth'):
        ledger=read(mode+'-ledger.json') if mode+'-ledger.json' in content else []
        require(len(ledger)<=2,'extra original model forwards observed')
        for i,row in enumerate(ledger):
            require(canonical_bytes(row)==canonical_bytes({'stage':('prefill','cached-token')[i],'input_ids':[IDS if i==0 else [0]],
                'outer_forwards_reserved':1,'input_tokens_reserved':12 if i==0 else 1}),'exact original forward reservation prefix differs')
            calls+=1;tokens+=row['input_tokens_reserved']
        if mode+'-result.json' in content:
            result=read(mode+'-result.json');require(len(ledger)==2 and result['mode']==mode and result['versions']==PACKAGES and
                result['python']=='3.11.13' and result['torch']=='2.8.0+cu128' and result['cuda']=='12.8' and
                result['outer_forwards']==2 and result['input_tokens']==13 and result['untied_storage_observed'] is True and
                result['parameter_dtypes']==['torch.bfloat16'] and result['model_class']=='Qwen3ForCausalLM' and
                all(type(result[k]) is int and result[k]==0 for k in ('optimizer_steps','generations','teacher_calls')) and
                len(result['vectors'])==2 and all(len(row)==16 and all(type(x) in (int,float) and math.isfinite(x) for x in row)
                    for row in result['vectors']),'finite original numeric observation/cost differs')
            results[mode]=result
    if terminal['outcome']=='complete':
        hardware=read('hardware.json');gpu=hardware['inventory']
        require(len(gpu)==4 and len({row['uuid'] for row in gpu})==4 and all(row['name']=='NVIDIA L4' and row['bf16'] for row in gpu) and
            hardware['torch']=='2.8.0+cu128' and hardware['cuda']=='12.8' and calls==4 and tokens==26 and len(results)==2 and
            read('model-verification.json')['all_ten_files_verified'] is True and
            read('model-verification.json')['model_material_digest']==MATERIAL and
            read('dependency-verification.json')['inventory']==binding()['inventory'],'complete original hardware/material/cost differs')
    comparisons={}
    if len(results)==2:
        for i,stage in enumerate(('prefill','cached-token')):
            reference,actual=results['reference']['vectors'][i],results['unsloth']['vectors'][i]
            comparisons[stage]={'maximum_absolute_logit_difference':max(abs(a-b) for a,b in zip(reference,actual)),
                'bitwise_equal':reference==actual,'argmax_equal':max(range(16),key=reference.__getitem__)==max(range(16),key=actual.__getitem__)}
    return {'run_id':plan['run_id'],'outcome':terminal['outcome'],'terminal':terminal,'archive_sha256':sha(path),
        'plan_digest':checked['plan_digest'],'reserved_outer_forwards':calls,'reserved_input_tokens':tokens,
        'comparisons':comparisons,'optimizer_steps':0,'generations':0,'correctness_scored':False,
        'historical_full_solver_parity':False,'full_environment_inventory_verified':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight','verify'))
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--run-id')
    parser.add_argument('--archive',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.action=='stage':result=stage(args.package,args.run_id)
    elif args.action=='preflight':result=preflight(args.package)
    else:
        require(args.output is not None and not args.output.exists(),'new independent original numerical proof required')
        result=verify_archive(args.archive,args.package);atomic(args.output,result)
    print(json.dumps(result))
