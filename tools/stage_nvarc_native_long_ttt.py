"""Offline original-runtime full-epoch package, gated by consumed native preparation."""
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
from tools import stage_nvarc_original_training_inspection as inspection
from tools.audit_nvarc_native_ttt_optimizer import MATERIAL as OPTIMIZER,EXACT

FORMAT='irisx/nvarc-original-native-long-ttt-v1'
WORKER=ROOT/'tools/nvarc_original_native_ttt_worker.py'
BUDGET=ROOT/'tools/nvarc_native_ttt_budget.py'
HARDWARE=ROOT/'src/irisx/arc_nvarc_hardware.py'
OPTIMIZER_PROOF=ROOT/'.irisx/nvarc-original/manifests/native-ttt-optimizer-20261002-001/result.json'
OPTIMIZER_PROOF_SHA='e519d70b696c9bbcb76102a53c4cde3a3cd68bf560a8769879f1856e2eec4031'
PREPARATION=ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-training-inspect-003'


def require(value,message):
    if not value:raise ValidationError(message)


def native_inventory():
    binding=inspection.source_inventory()
    ledger=json.loads((OPTIMIZER/'acquisition.json').read_bytes())
    require(ledger['state']=='complete-exact-public-dependency-files' and ledger['expected_script_version_id']==272622465 and
        ledger['requests_reserved']==ledger['files_completed']==4,'exact optimizer acquisition required')
    for name,expected in EXACT.items():
        path=OPTIMIZER/name;require(sha(path)==expected,'native optimizer source bytes differ')
        binding[name]={'bytes':path.stat().st_size,'sha256':expected}
    require(len(binding)==41,'all forty-one original source/metadata files required')
    return binding


def plan_for(run,session_seconds=10800):
    require(re.fullmatch(r'nvarc-original-qwen3-native-ttt-\d{3}',run),'new distinct native full-epoch identity required')
    require(type(session_seconds) is int and session_seconds in (1300,10800),'reviewed finite native epoch envelope required')
    observed=inspection.verify(PREPARATION/'execution-final/retrieved/gpu-preflight-result.zip',PREPARATION/'package-l4')
    require(observed['source_long_ttt_prerequisite_qualified'] is True and sha(OPTIMIZER_PROOF)==OPTIMIZER_PROOF_SHA,
        'qualified native preparation and exact scalar recipe required')
    native=json.loads((PREPARATION/'package-l4/plan.json').read_bytes())
    policy=json.loads(OPTIMIZER_PROOF.read_bytes())
    with zipfile.ZipFile(PREPARATION/'execution-final/retrieved/gpu-preflight-result.zip') as archive:
        result=json.loads(archive.read('native/native-inspection.json'))
    plan=dict(native)
    plan.update(format=FORMAT,run_id=run,kernel_id='danielwuu/'+run,
        maximum_notebook_wall_seconds=session_seconds,maximum_child_wall_seconds=session_seconds-300,
        maximum_outer_forwards=128,maximum_optimizer_steps=128,
        native_preparation_archive_sha256=observed['archive_sha256'],native_preparation_plan_digest=observed['plan_digest'],
        native_preparation_run_id=observed['run_id'],native_preparation_verified=True,
        source_inventory_digest=digest_value(native_inventory()),
        hardware_gate='four distinct BF16 L4s; one sequential rank-zero native epoch worker',
        native_optimizer_proof_sha256=OPTIMIZER_PROOF_SHA,source_learning_rates=policy['scheduler_rates_for_indices_0_through_128'],
        native_checkpoint_flags=result['gradient_checkpoint_flags'],native_adapter_topology=result['trainable_after_trainer'],
        native_trainer_origins=[{'class':row['class'],'module':row['module'],'source_sha256':row['sha256']}
            for row in result['trainer_origins'] if 'sha256' in row],
        maximum_training_tokens=955392,maximum_supervised_tokens=476160,full_long_ttt_completed=False,
        scope='complete native 128-view source epoch plus exact adapter reset; no solve, clock parity, export or ARC score')
    require(len(plan['source_learning_rates'])==129 and len(plan['native_trainer_origins'])==5,
        'all native scheduler indices and prepared Trainer origins required')
    return plan


def raw_payloads(plan):
    native=json.loads((PREPARATION/'package-l4/plan.json').read_bytes())
    payload=inspection.payloads_for(native)
    binding=native_inventory()
    require(digest_value(binding)==plan['source_inventory_digest'],'complete native source plan binding required')
    payload.update(plan=canonical_bytes(plan,newline=True),source_inventory=canonical_bytes(binding,newline=True),
        helper=payload['worker'],worker=WORKER.read_bytes(),budget=BUDGET.read_bytes(),hardware=HARDWARE.read_bytes())
    return payload


def parent_template():
    source=(ROOT/'tools/nvarc_original_training_inspection.py.tmpl').read_text(encoding='utf-8')
    anchor="def save(name,value):"
    helper="""def counts():
    path=work/'native/training-ledger.json'
    ledger=json.loads(path.read_bytes()) if path.is_file() else {'forwards':[],'optimizer_steps':[],'training_steps':[]}
    return {'model_forwards':sum(row['completed'] for row in ledger['forwards']),
        'optimizer_steps':sum(row['completed'] for row in ledger['optimizer_steps']),
        'model_forwards_reserved':len(ledger['forwards']),
        'optimizer_steps_reserved':len(ledger['optimizer_steps']),
        'training_steps_reserved':len(ledger['training_steps'])}

"""
    require(source.count(anchor)==1,'reviewed native parent anchor required')
    source=source.replace(anchor,helper+anchor)
    source=source.replace("('inspection.py','worker')","('inspection.py','worker'),('inspection_helpers.py','helper'),('nvarc_native_ttt_budget.py','budget'),('hardware_helpers.py','hardware')")
    source=source.replace("phase='zero-work-native-inspection'","phase='complete-native-source-epoch'")
    require(source.count("'model_forwards':0,'optimizer_steps':0")==2,
        'exact successful and failed native terminal count anchors required')
    source=source.replace("'model_forwards':0,'optimizer_steps':0","**counts()")
    require("'model_forwards':0" not in source,'both parent outcomes must retain actual training cost')
    return source


def render(run,payloads,hashes):
    source=parent_template()
    for key,value in {'__RUN__':json.dumps(run),'__PAYLOADS__':json.dumps(payloads),'__HASHES__':json.dumps(hashes),
        '__HARDWARE_HELPER__':HARDWARE.read_text(encoding='utf-8')}.items():source=source.replace(key,value)
    compile(source,'native-full-epoch-parent','exec');return source


def stage(package,run,session_seconds=10800):
    require(not package.exists(),'new immutable native epoch package required')
    plan=plan_for(run,session_seconds);raw=raw_payloads(plan)
    hashes={key:hashlib.sha256(value).hexdigest() for key,value in raw.items()}
    (package/'kernel').mkdir(parents=True);(package/'plan.json').write_bytes(raw['plan'])
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},
        'cells':[{'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
            'source':render(run,{key:base64.b64encode(value).decode() for key,value in raw.items()},hashes).splitlines(keepends=True)}]}
    atomic(package/'kernel/notebook.ipynb',notebook)
    atomic(package/'kernel/kernel-metadata.json',{'id':plan['kernel_id'],'title':run,'code_file':'notebook.ipynb','language':'python',
        'kernel_type':'notebook','is_private':True,'enable_gpu':True,'enable_internet':False,'docker_image':inspection.DOCKER,
        'dataset_sources':[],'kernel_sources':[inspection.REF],'competition_sources':plan['competition_sources'],'model_sources':plan['model_sources']})
    atomic(package/'stage-summary.json',{'run_id':run,'plan_digest':digest_value(plan),'payload_sha256':hashes,
        'inventory':{p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    plan=json.loads((package/'plan.json').read_bytes());summary=json.loads((package/'stage-summary.json').read_bytes())
    require(plan==plan_for(plan['run_id'],plan['maximum_notebook_wall_seconds']) and digest_value(plan)==summary['plan_digest'] and
        {p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file() and p.name!='stage-summary.json'}==summary['inventory'],
        'exact immutable native epoch plan/package required')
    source=''.join(json.loads((package/'kernel/notebook.ipynb').read_bytes())['cells'][0]['source'])
    values={node.targets[0].id:ast.literal_eval(node.value) for node in ast.parse(source).body if isinstance(node,ast.Assign)
        and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'RUN','PAYLOADS','HASHES'}}
    raw={key:base64.b64decode(value,validate=True) for key,value in values['PAYLOADS'].items()}
    require(raw==raw_payloads(plan) and values['HASHES']==summary['payload_sha256']=={key:hashlib.sha256(value).hexdigest() for key,value in raw.items()} and
        values['RUN']==plan['run_id'] and source==render(values['RUN'],values['PAYLOADS'],values['HASHES']),
        'exact original full-epoch parent/worker/budget bytes required')
    metadata=json.loads((package/'kernel/kernel-metadata.json').read_bytes())
    require(metadata=={'id':plan['kernel_id'],'title':plan['run_id'],'code_file':'notebook.ipynb','language':'python','kernel_type':'notebook',
        'is_private':True,'enable_gpu':True,'enable_internet':False,'docker_image':inspection.DOCKER,'dataset_sources':[],
        'kernel_sources':[inspection.REF],'competition_sources':plan['competition_sources'],'model_sources':plan['model_sources']},
        'private original-runtime transport differs')
    return {'run_id':plan['run_id'],'plan_digest':summary['plan_digest'],'offline_package_verified':True,'external_calls':0,
        'maximum_optimizer_steps':128,'source_input_tokens':955392,'maximum_notebook_wall_seconds':plan['maximum_notebook_wall_seconds']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--run-id')
    parser.add_argument('--session-seconds',type=int,choices=(1300,10800),default=10800)
    args=parser.parse_args();print(json.dumps(stage(args.package,args.run_id,args.session_seconds) if args.action=='stage' else preflight(args.package)))
