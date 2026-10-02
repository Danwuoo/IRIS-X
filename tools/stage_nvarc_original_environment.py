"""Bound CPU-only original-version import/tokenizer probe; no model weights."""
from __future__ import annotations
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
from tools.acquire_nvarc_original_environment import DOCKER,REF,PACKAGES,verify as verify_binding

MATERIAL=ROOT/'.irisx/nvarc-original/materials'
BINDING=ROOT/'.irisx/nvarc-original/manifests/original-environment-binding-20261002-001/result.json'
TOKENIZER=MATERIAL/'qwen3-published-sft139-20261002-001/model'
TOKENIZER_FILES=('added_tokens.json','config.json','special_tokens_map.json','tokenizer_config.json','tokenizer.json','vocab.json')
FORMAT='irisx/nvarc-original-qwen3-environment-probe-v1'
WORKER='''import importlib.metadata as metadata
import json
from pathlib import Path
import sys
root=Path(sys.argv[3]).resolve()
expected=__VERSIONS__
import torch
import transformers
import tokenizers
from transformers import AutoTokenizer
versions={name:metadata.version(name) for name in expected}
if versions!=expected:raise RuntimeError('original import distribution versions differ')
paths={name:str(Path(module.__file__).resolve()) for name,module in
    [('torch',torch),('transformers',transformers),('tokenizers',tokenizers)]}
if any(not Path(value).is_relative_to(root) for value in paths.values()):
    raise RuntimeError('imported package escapes exact dependency output')
tokenizer=AutoTokenizer.from_pretrained(sys.argv[1],local_files_only=True)
chat='<|im_start|>user\\n01<|im_end|><|im_start|>assistant\\n10<|im_end|>'
tokens=tokenizer.encode(chat)
roles={name:tokenizer.encode(name) for name in ('user','assistant')}
result={'python':sys.version.split()[0],'versions':versions,'imported_paths':paths,
    'torch_cuda':torch.version.cuda,'cuda_available':torch.cuda.is_available(),
    'tokenizer_class':type(tokenizer).__name__,'roles':roles,'chat_tokens':tokens,
    'model_calls':0,'optimizer_steps':0,'generations':0,'package_installs':0}
Path(sys.argv[2]).write_text(json.dumps(result,sort_keys=True,separators=(',',':')),encoding='utf-8')
if tokens!=[14,11,10,0,1,15,14,12,10,1,0,15] or roles!={'user':[11],'assistant':[12]}:
    raise RuntimeError('original AutoTokenizer role/chat mapping differs')
if torch.cuda.is_available():raise RuntimeError('CPU-only probe unexpectedly has CUDA hardware')
'''


def require(condition,message):
    if not condition:raise ValidationError(message)


def binding():
    notebook=ROOT/'.irisx/arc-agi-2/qwen35-nvarc/source/kaggle-qwen/arc2-qwen3-unsloth-flash-lora-batch4-queue.ipynb'
    actual=verify_binding(MATERIAL/'qwen3-historical-dependency-files-20261002-001',
        MATERIAL/'qwen3-historical-environment-source-20261002-001',
        MATERIAL/'qwen3-historical-environment-output-metadata-20261002-002',notebook)
    require(actual==json.loads(BINDING.read_bytes()),'exact independently verified original dependency binding differs')
    return actual


def render(run,payloads,hashes):
    revision=json.loads(base64.b64decode(payloads['plan'],validate=True)).get('transport_revision',1)
    require(type(revision) is int and revision in (1,2),'reviewed immutable environment transport revision required')
    name='nvarc_original_environment_notebook.py.tmpl' if revision==1 else 'nvarc_original_environment_notebook_v2.py.tmpl'
    source=(ROOT/'tools'/name).read_text(encoding='utf-8')
    for key,value in {'__RUN__':json.dumps(run),'__PAYLOADS__':json.dumps(payloads),'__HASHES__':json.dumps(hashes)}.items():
        source=source.replace(key,value)
    compile(source,'original-environment-probe','exec');return source


def stage(package,run):
    require(not package.exists() and re.fullmatch(r'nvarc-original-qwen3-environment-\d{3}',run),
        'new immutable original environment probe required')
    proof=binding()
    inventory=json.loads((TOKENIZER.parent/'independent-verification.json').read_bytes())['inventory']
    for name in TOKENIZER_FILES:
        require(sha(TOKENIZER/name)==inventory[name]['sha256'],'exact published tokenizer file differs')
    worker=WORKER.replace('__VERSIONS__',repr(PACKAGES));compile(worker,'environment-worker','exec')
    plan={'format':FORMAT,'approved':True,'owner_decision':'Decision 0054','run_id':run,
        'kernel_id':'danielwuu/'+run,'maximum_notebook_wall_seconds':600,'maximum_worker_wall_seconds':420,
        'maximum_model_calls':0,'maximum_optimizer_steps':0,'maximum_generations':0,'maximum_teacher_calls':0,
        'maximum_paid_usd':0,'retain_export':False,'hardware':'CPU only; no GPU/TPU allocation',
        'docker_image':DOCKER,'dependency_ref':REF,'dependency_script_version_id':272622465,
        'dependency_binding_sha256':sha(BINDING),'kernel_sources':[REF],
        'tokenizer_inventory':{name:inventory[name] for name in TOKENIZER_FILES},
        'model_weight_files_opened':0,'evaluation_files_opened':0,'competition_sources':[], 'transport_revision':2,
        'historical_cuda_numerical_parity':False,'source_program_executions':0}
    raw={'plan':canonical_bytes(plan,newline=True),'binding':canonical_bytes(proof,newline=True),
        'tokenizer':canonical_bytes({name:base64.b64encode((TOKENIZER/name).read_bytes()).decode() for name in TOKENIZER_FILES},newline=True),
        'worker':worker.encode('utf-8')}
    payloads={k:base64.b64encode(v).decode() for k,v in raw.items()}
    hashes={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    (package/'kernel').mkdir(parents=True);(package/'plan.json').write_bytes(raw['plan'])
    atomic(package/'kernel/notebook.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{
        'display_name':'Python 3','language':'python','name':'python3'}},'cells':[{'cell_type':'code','execution_count':None,
        'metadata':{},'outputs':[],'source':render(run,payloads,hashes).splitlines(keepends=True)}]})
    atomic(package/'kernel/kernel-metadata.json',{'id':plan['kernel_id'],'title':run,'code_file':'notebook.ipynb',
        'language':'python','kernel_type':'notebook','is_private':True,'enable_gpu':False,'enable_tpu':False,
        'enable_internet':False,'docker_image':DOCKER,'dataset_sources':[],
        'competition_sources':[],'kernel_sources':[REF],'model_sources':[]})
    atomic(package/'stage-summary.json',{'run_id':run,'plan_digest':digest_value(plan),'payload_sha256':hashes,
        'inventory':{p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    summary=json.loads((package/'stage-summary.json').read_bytes());plan=json.loads((package/'plan.json').read_bytes())
    require({p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file() and
        p.name!='stage-summary.json'}==summary['inventory'] and digest_value(plan)==summary['plan_digest'],
        'closed immutable environment probe inventory differs')
    require(plan['format']==FORMAT and plan['owner_decision']=='Decision 0054' and plan['approved'] is True and
        plan['maximum_notebook_wall_seconds']==600 and plan['maximum_worker_wall_seconds']==420 and
        all(type(plan[k]) is int and plan[k]==0 for k in ('maximum_model_calls','maximum_optimizer_steps',
            'maximum_generations','maximum_teacher_calls','maximum_paid_usd','model_weight_files_opened',
            'evaluation_files_opened','source_program_executions')),'finite zero-model CPU environment bounds differ')
    source=''.join(json.loads((package/'kernel/notebook.ipynb').read_bytes())['cells'][0]['source'])
    values={node.targets[0].id:ast.literal_eval(node.value) for node in ast.parse(source).body if isinstance(node,ast.Assign)
        and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'RUN','PAYLOADS','HASHES'}}
    require(values['RUN']==plan['run_id'] and source==render(values['RUN'],values['PAYLOADS'],values['HASHES']) and
        values['HASHES']==summary['payload_sha256'] and set(values['PAYLOADS'])=={'plan','binding','tokenizer','worker'},
        'exact reviewed environment probe source/payload differs')
    raw={k:base64.b64decode(v,validate=True) for k,v in values['PAYLOADS'].items()}
    require(all(len(v)<2*1024**2 and hashlib.sha256(v).hexdigest()==values['HASHES'][k] for k,v in raw.items()) and
        raw['plan']==(package/'plan.json').read_bytes() and json.loads(raw['binding'])==binding() and
        raw['worker']==WORKER.replace('__VERSIONS__',repr(PACKAGES)).encode('utf-8'), 'bound environment payload bytes differ')
    require(plan['dependency_binding_sha256']==sha(BINDING) and plan['docker_image']==DOCKER and
        plan['kernel_sources']==[REF] and plan['retain_export'] is False,'original dependency/Docker bounds differ')
    tokenizer=json.loads(raw['tokenizer']);require(set(tokenizer)==set(TOKENIZER_FILES),'closed tokenizer files required')
    for name,encoded in tokenizer.items():
        body=base64.b64decode(encoded,validate=True)
        require(body==(TOKENIZER/name).read_bytes() and hashlib.sha256(body).hexdigest()==plan['tokenizer_inventory'][name]['sha256'],
            'exact source tokenizer payload differs')
    meta=json.loads((package/'kernel/kernel-metadata.json').read_bytes())
    require(meta['id']==plan['kernel_id']=='danielwuu/'+plan['run_id'] and meta['title']==plan['run_id'] and
        meta['is_private'] is True and meta['enable_gpu'] is False and meta['enable_tpu'] is False and
        meta['enable_internet'] is False and meta['docker_image']==DOCKER and meta['kernel_sources']==[REF] and
        all(meta[k]==[] for k in ('dataset_sources','model_sources','competition_sources')), 'CPU-only private transport differs')
    return {'run_id':plan['run_id'],'plan_digest':summary['plan_digest'],'offline_package_verified':True,
        'external_calls':0,'model_calls':0,'maximum_notebook_wall_seconds':600,'hardware':'CPU only'}


def verify_archive(archive_path,package):
    checked=preflight(package);plan=json.loads((package/'plan.json').read_bytes())
    with zipfile.ZipFile(archive_path) as archive:
        names=archive.namelist();require(len(names)==len(set(names)) and
            sum(row.file_size for row in archive.infolist())<=8*1024**2,'closed bounded CPU environment archive required')
        index=json.loads(archive.read('manifest.json'))
        require(index['run_id']==plan['run_id'] and index['plan_digest']==checked['plan_digest'] and
            set(names)=={row['path'] for row in index['members']}|{'manifest.json'},'environment archive/plan binding differs')
        for row in index['members']:
            body=archive.read(row['path']);require(len(body)==row['bytes'] and hashlib.sha256(body).hexdigest()==row['sha256'],
                'environment archive member differs')
        require(json.loads(archive.read('plan.json'))==plan and json.loads(archive.read('payload-bindings.json'))==
            json.loads((package/'stage-summary.json').read_bytes())['payload_sha256'],'saved exact environment package differs')
        terminal=json.loads(archive.read('terminal.json'))
        require(terminal['run_id']==plan['run_id'] and terminal['contains_evaluator_truth'] is False and
            all(type(terminal[k]) is int and terminal[k]==0 for k in ('model_calls','optimizer_steps','generations',
                'source_program_executions','paid_usd')) and terminal['wall_seconds']<=600,'zero-model environment cost differs')
        result=None
        if terminal['outcome']=='complete':
            dependency=json.loads(archive.read('dependency-verification.json'))
            require(dependency['all_eight_files_verified'] is True and dependency['script_version_id']==272622465 and
                dependency['inventory']==binding()['inventory'],'runtime exact original dependency files differ')
            result=json.loads(archive.read('worker-result.json'))
            require(result['python']=='3.11.13' and result['versions']==PACKAGES and result['cuda_available'] is False and
                result['roles']=={'user':[11],'assistant':[12]} and result['chat_tokens']==[14,11,10,0,1,15,14,12,10,1,0,15] and
                all(result[k]==0 for k in ('model_calls','optimizer_steps','generations','package_installs')),
                'original-version import/tokenizer observation differs')
            root=Path(dependency['dependency_root'])
            require(all(Path(value).is_relative_to(root) for value in result['imported_paths'].values()),
                'runtime package import paths escape verified dependency')
        return {'run_id':plan['run_id'],'outcome':terminal['outcome'],'terminal':terminal,
            'runtime_observation':result,'archive_sha256':sha(archive_path),'plan_digest':checked['plan_digest'],
            'model_calls':0,'historical_cuda_numerical_parity':False,'paid_usd':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight','verify'))
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--run-id')
    parser.add_argument('--archive',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.action=='stage':result=stage(args.package,args.run_id)
    elif args.action=='preflight':result=preflight(args.package)
    else:
        require(args.output is not None and not args.output.exists(),'new independent CPU runtime proof required')
        result=verify_archive(args.archive,args.package);atomic(args.output,result)
    print(json.dumps(result))
