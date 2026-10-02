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
POSITION_FORMAT='irisx/nvarc-original-qwen3-unsloth-positions-probe-v1'
OUTPUT_FORMAT='irisx/nvarc-original-qwen3-unsloth-output-probe-v1'
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


OUTPUT_HELPER='''def observed_output(value, expected_length):
    if isinstance(value, tuple):
        if len(value)<2:raise RuntimeError('original cached tuple requires logits and past values')
        logits,cache=value[:2];contract='tuple-logits-cache'
    else:
        logits,cache=value.logits,value.past_key_values;contract='model-output-logits-cache'
    if not isinstance(logits,torch.Tensor) or list(logits.shape)!=[1,expected_length,16] or cache is None:
        raise RuntimeError('exact original output tensor/cache contract differs')
    contracts.append(contract)
    return logits,cache
'''


def worker_source(explicit_positions=False,tuple_outputs=False):
    require(not tuple_outputs or explicit_positions,'tuple-output repair retains exact positions')
    source=WORKER
    if explicit_positions:
        source=source.replace("        events.append({'stage':active", "        positions=kwargs.get('position_ids')\n        actual_positions=positions.detach().cpu().tolist() if positions is not None else None\n        wanted_positions=[list(range(len(ids))) if len(events)==0 else [len(ids)]]\n        if actual_positions!=wanted_positions:raise RuntimeError('exact original cached position IDs required')\n        events.append({'completed':False,'position_ids':actual_positions,'stage':active")
        source=source.replace('    return original_call(self,*args,**kwargs)', "    result=original_call(self,*args,**kwargs)\n    if type(self).__name__=='Qwen3ForCausalLM':\n        events[-1]['completed']=True\n        (output/(mode+'-ledger.json')).write_text(json.dumps(events,separators=(',',':')),encoding='utf-8')\n    return result")
        source=source.replace('model(input_ids=torch.tensor([ids],device=\'cuda:0\'),use_cache=True)',
            "model(input_ids=torch.tensor([ids],device='cuda:0'),position_ids=torch.arange(len(ids),device='cuda:0').unsqueeze(0),use_cache=True)")
        source=source.replace("    active='cached-token';second=model", "    if not all(__import__('math').isfinite(x) for x in vectors[0]):raise RuntimeError('nonfinite prefill vector')\n    (output/(mode+'-prefill.json')).write_text(json.dumps({'mode':mode,'vector':vectors[0],'shape':shapes[0]},allow_nan=False),encoding='utf-8')\n    active='cached-token';second=model")
        source=source.replace("past_key_values=first.past_key_values,use_cache=True)",
            "position_ids=torch.tensor([[len(ids)]],device='cuda:0'),past_key_values=first.past_key_values,use_cache=True)")
    if tuple_outputs:
        source=source.replace('model.eval();torch.cuda.reset_peak_memory_stats();vectors=[];shapes=[]',
            OUTPUT_HELPER+'\nmodel.eval();torch.cuda.reset_peak_memory_stats();vectors=[];shapes=[];contracts=[]')
        source=source.replace('    vectors.append(first.logits[0,-1].float().cpu().tolist());shapes.append(list(first.logits.shape))',
            '    first_logits,first_cache=observed_output(first,len(ids))\n    vectors.append(first_logits[0,-1].float().cpu().tolist());shapes.append(list(first_logits.shape))')
        source=source.replace('past_key_values=first.past_key_values,use_cache=True)', 'past_key_values=first_cache,use_cache=True)')
        source=source.replace('    vectors.append(second.logits[0,-1].float().cpu().tolist());shapes.append(list(second.logits.shape))',
            '    second_logits,second_cache=observed_output(second,1)\n    vectors.append(second_logits[0,-1].float().cpu().tolist());shapes.append(list(second_logits.shape))')
        source=source.replace("'input_tokens':sum(row['input_tokens_reserved'] for row in events)",
            "'observed_output_contracts':contracts,'input_tokens':sum(row['input_tokens_reserved'] for row in events)")
    return source.replace('__VERSIONS__',repr(PACKAGES)).replace('__IDS__',repr(IDS))


def failed_position_prerequisite():
    folder=ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-unsloth-probe-001'
    archive=folder/'execution-final/retrieved/gpu-preflight-result.zip'
    ledger=json.loads((folder/'execution-final/execution-ledger.json').read_bytes())
    require(ledger.get('accepted') is True and ledger.get('retrieval_reserved')==1 and ledger.get('terminal_observed') is True and
        ledger['events'][-1].get('outcome')=='retrieved' and sha(archive)=='4d367632ebd6cd60fc2bf6f420ef3f6b5ff85f222a53eef8ce93c460eaec5cc6',
        'exact consumed original position-failure version required')
    proof=verify_archive(archive,folder/'package-l4')
    with zipfile.ZipFile(archive) as stream:stderr=stream.read('unsloth-stderr.log').decode('utf-8')
    require(proof['outcome']=='failed' and proof['terminal']['phase']=='unsloth-two-forwards' and
        proof['reserved_outer_forwards']==4 and proof['reserved_input_tokens']==26 and
        "AttributeError: 'NoneType' object has no attribute 'device'" in stderr and 'active=\'cached-token\'' in stderr,
        'verified original cached-position failure required')
    return sha(archive)


def failed_output_prerequisite():
    folder=ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-unsloth-probe-002'
    archive=folder/'execution-final/retrieved/gpu-preflight-result.zip'
    ledger=json.loads((folder/'execution-final/execution-ledger.json').read_bytes())
    require(ledger['accepted'] is True and ledger['terminal_observed'] is True and ledger['retrieval_reserved']==1 and
        ledger['events'][-1]['outcome']=='retrieved' and sha(archive)=='74868ffbb99de934dbc6713b5af6846d478227cee4d231e7a86024b995238cd7',
        'exact consumed tuple-output failure required')
    proof=verify_archive(archive,folder/'package-l4')
    with zipfile.ZipFile(archive) as stream:stderr=stream.read('unsloth-stderr.log').decode('utf-8')
    require(proof['outcome']=='failed' and proof['completed_outer_forwards']==4 and proof['reserved_input_tokens']==26 and
        "AttributeError: 'tuple' object has no attribute 'logits'" in stderr and 'second.logits' in stderr,
        'verified cached tuple extraction failure required')
    return sha(archive)


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


def stage(package,run,explicit_positions=False,tuple_outputs=False):
    require(not package.exists() and re.fullmatch(r'nvarc-original-qwen3-unsloth-probe-\d{3}',run),'new immutable original Unsloth probe required')
    entries=inventory();proof=binding();worker=worker_source(explicit_positions,tuple_outputs)
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
    if explicit_positions:
        plan.update(format=POSITION_FORMAT,explicit_position_ids=True,prefill_position_ids=list(range(len(IDS))),
            cached_position_ids=[len(IDS)],retain_completed_forward_prefix=True,retain_prefill_before_cached_call=True,
            predecessor_run_id='nvarc-original-qwen3-unsloth-probe-001',predecessor_archive_sha256=failed_position_prerequisite())
    if tuple_outputs:
        plan.update(format=OUTPUT_FORMAT,accept_original_tuple_output=True,
            output_contract='logits and cache via attributes or tuple indices zero and one; exact shapes required',
            output_contract_source_sha256=sha(ROOT/'.irisx/nvarc-original/materials/qwen3-original-training-source-20261002-001/unsloth/models/llama.py'),
            predecessor_run_id='nvarc-original-qwen3-unsloth-probe-002',predecessor_archive_sha256=failed_output_prerequisite())
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
    outputs=plan['format']==OUTPUT_FORMAT
    positions=plan['format'] in {POSITION_FORMAT,OUTPUT_FORMAT}
    require(plan['format'] in {FORMAT,POSITION_FORMAT,OUTPUT_FORMAT} and plan['owner_decision']=='Decision 0054' and plan['approved'] is True and
        all(type(plan[k]) is int and plan[k]==v for k,v in {'maximum_notebook_wall_seconds':1200,'maximum_child_wall_seconds':450,
            'maximum_outer_forwards':4,'maximum_input_tokens':26,'maximum_optimizer_steps':0,'maximum_generations':0,
            'maximum_teacher_calls':0,'maximum_paid_usd':0,'competition_files_opened':0}.items()) and
        plan['input_ids']==IDS and plan['cached_input_ids']==[0] and plan['lora_adaptation'] is False and
        plan['retain_export'] is False and plan['model_material_digest']==MATERIAL,'exact four-forward zero-training bounds differ')
    if positions:
        require(plan['explicit_position_ids'] is True and plan['prefill_position_ids']==list(range(len(IDS))) and
            plan['cached_position_ids']==[len(IDS)] and plan['retain_completed_forward_prefix'] is True and
            plan['retain_prefill_before_cached_call'] is True,'exact original position repair differs')
        require(plan['predecessor_run_id']==('nvarc-original-qwen3-unsloth-probe-002' if outputs else 'nvarc-original-qwen3-unsloth-probe-001') and
            plan['predecessor_archive_sha256']==(failed_output_prerequisite() if outputs else failed_position_prerequisite()),
            'exact original predecessor failure differs')
    if outputs:require(plan['accept_original_tuple_output'] is True and
        plan['output_contract_source_sha256']==sha(ROOT/'.irisx/nvarc-original/materials/qwen3-original-training-source-20261002-001/unsloth/models/llama.py') and
        plan['output_contract']=='logits and cache via attributes or tuple indices zero and one; exact shapes required',
        'exact original tuple extraction repair differs')
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
        raw['worker']==worker_source(positions,outputs).encode('utf-8') and
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
    outputs=plan.get('format')==OUTPUT_FORMAT
    positions=plan.get('format') in {POSITION_FORMAT,OUTPUT_FORMAT}
    calls=tokens=completed=0;results={};prefills={}
    for mode in ('reference','unsloth'):
        ledger=read(mode+'-ledger.json') if mode+'-ledger.json' in content else []
        require(len(ledger)<=2,'extra original model forwards observed')
        for i,row in enumerate(ledger):
            expected={'stage':('prefill','cached-token')[i],'input_ids':[IDS if i==0 else [0]],
                'outer_forwards_reserved':1,'input_tokens_reserved':12 if i==0 else 1}
            if positions:
                require(type(row.get('completed')) is bool and (row['completed'] or i==len(ledger)-1),
                    'closed completed-forward prefix required')
                expected.update(position_ids=[list(range(len(IDS))) if i==0 else [len(IDS)]],completed=row['completed'])
                completed+=row['completed']
            require(canonical_bytes(row)==canonical_bytes(expected),'exact original forward reservation prefix differs')
            calls+=1;tokens+=row['input_tokens_reserved']
        if mode+'-prefill.json' in content:
            prefill=read(mode+'-prefill.json')
            require(positions and ledger and ledger[0]['completed'] is True and set(prefill)=={'mode','vector','shape'} and
                prefill['mode']==mode and prefill['shape']==[1,12,16] and len(prefill['vector'])==16 and
                all(type(x) in (int,float) and math.isfinite(x) for x in prefill['vector']),
                'finite completed prefill vector required')
            prefills[mode]=prefill['vector']
        if mode+'-result.json' in content:
            result=read(mode+'-result.json');require(len(ledger)==2 and result['mode']==mode and result['versions']==PACKAGES and
                result['python']=='3.11.13' and result['torch']=='2.8.0+cu128' and result['cuda']=='12.8' and
                result['outer_forwards']==2 and result['input_tokens']==13 and result['untied_storage_observed'] is True and
                result['parameter_dtypes']==['torch.bfloat16'] and result['model_class']=='Qwen3ForCausalLM' and
                all(type(result[k]) is int and result[k]==0 for k in ('optimizer_steps','generations','teacher_calls')) and
                len(result['vectors'])==2 and all(len(row)==16 and all(type(x) in (int,float) and math.isfinite(x) for x in row)
                    for row in result['vectors']),'finite original numeric observation/cost differs')
            results[mode]=result
            if outputs:require(result['output_shapes']==[[1,12,16],[1,1,16]] and
                len(result['observed_output_contracts'])==2 and all(value in
                    {'tuple-logits-cache','model-output-logits-cache'} for value in result['observed_output_contracts']),
                'retained original output contracts/shapes differ')
            if positions:require(all(e['completed'] for e in ledger) and prefills.get(mode)==result['vectors'][0],
                'complete result must match its persisted completed prefill')
    if terminal['outcome']=='complete':
        hardware=read('hardware.json');gpu=hardware['inventory']
        require(len(gpu)==4 and len({row['uuid'] for row in gpu})==4 and all(row['name']=='NVIDIA L4' and row['bf16'] for row in gpu) and
            hardware['torch']=='2.8.0+cu128' and hardware['cuda']=='12.8' and calls==4 and tokens==26 and len(results)==2 and
            read('model-verification.json')['all_ten_files_verified'] is True and
            read('model-verification.json')['model_material_digest']==MATERIAL and
            read('dependency-verification.json')['inventory']==binding()['inventory'],'complete original hardware/material/cost differs')
        if positions:require(completed==4,'complete original four-forward completion count required')
    comparisons={}
    if len(results)==2:
        for i,stage in enumerate(('prefill','cached-token')):
            reference,actual=results['reference']['vectors'][i],results['unsloth']['vectors'][i]
            comparisons[stage]={'maximum_absolute_logit_difference':max(abs(a-b) for a,b in zip(reference,actual)),
                'bitwise_equal':reference==actual,'argmax_equal':max(range(16),key=reference.__getitem__)==max(range(16),key=actual.__getitem__)}
    elif len(prefills)==2:
        reference,actual=prefills['reference'],prefills['unsloth']
        comparisons['prefill']={'maximum_absolute_logit_difference':max(abs(a-b) for a,b in zip(reference,actual)),
            'bitwise_equal':reference==actual,'argmax_equal':max(range(16),key=reference.__getitem__)==max(range(16),key=actual.__getitem__)}
    proof={'run_id':plan['run_id'],'outcome':terminal['outcome'],'terminal':terminal,'archive_sha256':sha(path),
        'plan_digest':checked['plan_digest'],'reserved_outer_forwards':calls,'reserved_input_tokens':tokens,
        'comparisons':comparisons,'optimizer_steps':0,'generations':0,'correctness_scored':False,
        'historical_full_solver_parity':False,'full_environment_inventory_verified':False}
    if positions:proof.update(completed_outer_forwards=completed,explicit_position_ids_observed=True,
        retained_prefill_modes=sorted(prefills))
    if outputs:proof['observed_output_contracts']={mode:value['observed_output_contracts'] for mode,value in results.items()}
    if 'hardware.json' in content:
        hardware=read('hardware.json');gpu=hardware['inventory']
        proof.update(observed_gpu_count=len(gpu),distinct_gpu_uuids=len({x['uuid'] for x in gpu}),
            four_bf16_l4_hardware_observed=len(gpu)==len({x['uuid'] for x in gpu})==4 and
                all(x['name']=='NVIDIA L4' and x['bf16'] is True for x in gpu))
    if 'model-verification.json' in content:
        observation=read('model-verification.json')
        require(observation['all_ten_files_verified'] is True and observation['model_material_digest']==MATERIAL,
            'retained original model binding differs')
        proof['exact_original_model_material_observed']=True
    return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight','verify'))
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--run-id')
    parser.add_argument('--explicit-positions',action='store_true')
    parser.add_argument('--tuple-outputs',action='store_true')
    parser.add_argument('--archive',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.action=='stage':result=stage(args.package,args.run_id,args.explicit_positions,args.tuple_outputs)
    elif args.action=='preflight':result=preflight(args.package)
    else:
        require(args.output is not None and not args.output.exists(),'new independent original numerical proof required')
        result=verify_archive(args.archive,args.package);atomic(args.output,result)
    print(json.dumps(result))
