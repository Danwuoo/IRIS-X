"""Offline two-step original Qwen3 restart/export package with retained state.

The output-storage gate accounts for full FP32 model plus both Adam moments.
Scratch-only checkpoints cannot satisfy this distinct integration question.
"""
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.arc_nvarc_qwen3_sft import FORMAT,check_plan,verify_model
from irisx.arc_nvarc_qwen3_packed_step import BASE,PREFIX_SHA,schedule
from irisx.arc_nvarc_gpu_preflight_v2 import RECIPE
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
from tools.nvarc_qwen3_material import DEFAULT
from tools.stage_nvarc_qwen3_packed_step import prerequisite
from tools import irisx_build_backend as build

TEMPLATE=ROOT/'tools/nvarc_qwen3_sft_notebook.py.tmpl'
PREFIX=ROOT/'.irisx/nvarc-original/materials/source-shuffle-prefix-20261002-001'


def require(value,message):
    if not value:raise ValidationError(message)


def storage_bound(parameter_elements,steps=2):
    require(type(parameter_elements) is int and parameter_elements>0 and type(steps) is int and steps>=2,
            'positive full-parameter storage accounting required')
    return {'parameter_elements':parameter_elements,'fp32_model_bytes':parameter_elements*4,
        'fp32_adam_moment_bytes':parameter_elements*8,'checkpoint_bytes_per_transaction':parameter_elements*12,
        'live_checkpoint_transactions':min(steps,3),'bf16_export_bytes':parameter_elements*2,
        'reserve_bytes':4*1024**3,
        'minimum_free_working_bytes':parameter_elements*(12*min(steps,3)+2)+4*1024**3,
        'checkpoint_destination':'retained /kaggle/working; no ephemeral scratch substitution'}


def make_plan(run):
    require(re.fullmatch(r'nvarc-original-qwen3-sft-\d{3}',run),'new original SFT identity required')
    dependency=prerequisite(ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-probe-004')
    material=json.loads((DEFAULT/'conversion.json').read_bytes())
    verify_model(DEFAULT/'compact',{'model_inventory':material['compact_inventory'],'base_material_digest':BASE})
    require(sha(PREFIX/'samples.json')==PREFIX_SHA,'all exact two-batch source prefix bytes required')
    rows=json.loads((PREFIX/'samples.json').read_bytes())
    require(len(rows)==512 and [r['shuffle_position'] for r in rows]==list(range(512)),'unfiltered first 512 source rows required')
    placements=[schedule(rows[i:i+256]) for i in (0,256)]
    index=json.loads((DEFAULT/'compact/model.safetensors.index.json').read_bytes())
    require(index['metadata']['total_size']%2==0,'BF16 original unique tensor bytes required')
    storage=storage_bound(index['metadata']['total_size']//2)
    upload=DEFAULT/'upload'
    sidecars={name:{'bytes':(upload/name).stat().st_size,'sha256':sha(upload/name)}
        for name in ('material-manifest.json','dataset-metadata.json')}
    plan={'format':FORMAT,'model_family':'qwen3','approved':True,'owner_decision':'Decision 0054','run_id':run,
        'kernel_id':'danielwuu/'+run,'backend':'cuda-l4','world_size':4,'global_batch_size':256,
        'source_recipe':RECIPE,'data_kind':'original-source-prefix','data_digest':digest_value(rows),
        'source_prefix_sha256':PREFIX_SHA,'source_prefix_verification_sha256':sha(PREFIX/'verification.json'),
        'model_inventory':material['compact_inventory'],'base_material_digest':BASE,'model_sidecars':sidecars,
        'material_manifest_sha256':sha(DEFAULT/'conversion.json'),'model_repo':material['repo'],'model_revision':material['revision'],
        'model_dataset_version':1,'datasets':{'base':'danielwuu/irisx-nvarc-original-qwen3-001',
            'wheels':'danielwuu/irisx-arc-agi-2-trial-002-smoke-001'},
        'competition_sources':['arc-prize-2026-arc-agi-2'],'competition_files_opened':0,
        'maximum_notebook_wall_seconds':3600,'maximum_worker_wall_seconds':3000,'maximum_optimizer_steps':2,
        'terminal_reserve_seconds':120,'minimum_host_available_bytes':64*1024**3,
        'maximum_training_tokens':sum(len(r['input_ids']) for r in rows),
        'scheduled_input_tokens':sum(len(r['input_ids']) for r in rows),
        'scheduled_supervised_tokens':sum(sum(v>=0 for v in r['labels'][1:]) for r in rows),
        'maximum_input_tokens':sum(len(r['input_ids']) for r in rows)+2*sum(p['dummy_outer_forwards'] for p in placements),
        'maximum_outer_forwards':sum(p['collective_slots_per_rank']*4 for p in placements),
        'maximum_sequence_length':max(len(r['input_ids']) for r in rows),'maximum_physical_input_tokens':32768,
        'packing_capacity':256000,'packing_length_multiple':64,'packing_execution':'segmented-gemm-whole-sample-packing',
        'physical_schedules':placements,'checkpoint_steps':[1,2],'checkpoint_keep_last':2,'checkpoint_storage':'durable-retained',
        'checkpoint_storage_bound':storage,'seed':24,'maximum_paid_usd':0,'maximum_generations':0,'maximum_teacher_calls':0,
        'cuda_differential_prerequisite':dependency,'retain_export':True,'retain_optimizer_checkpoint':True,
        'full_sft_completed':False,'historical_nemo_version':None,'historical_megatron_version':None,
        'scope':'two complete global-256 original-family steps with process restart, retained model/Adam state and HF export; no full SFT, stable rate or historical backend claim'}
    check_plan(plan,4)
    return plan,rows


def render(run,payloads,hashes):
    source=TEMPLATE.read_text(encoding='utf-8')
    for key,value in {'__RUN__':json.dumps(run),'__PAYLOADS__':json.dumps(payloads),'__HASHES__':json.dumps(hashes),
        '__HARDWARE_HELPER__':(ROOT/'src/irisx/arc_nvarc_hardware.py').read_text(encoding='utf-8')}.items():
        source=source.replace(key,value)
    compile(source,'original-sft-notebook','exec')
    return source


def metadata(plan):
    return {'id':plan['kernel_id'],'title':plan['run_id'],'code_file':'notebook.ipynb','language':'python',
        'kernel_type':'notebook','is_private':True,'enable_gpu':True,'enable_internet':False,
        'dataset_sources':list(plan['datasets'].values()),'competition_sources':plan['competition_sources'],'kernel_sources':[]}


def stage(package,run):
    require(not package.exists(),'new immutable original SFT package required')
    plan,rows=make_plan(run)
    (package/'wheel').mkdir(parents=True)
    wheel=package/'wheel'/build.build_wheel(str(package/'wheel'))
    raw={'plan':canonical_bytes(plan,newline=True),'samples':canonical_bytes(rows,newline=True),'runtime_wheel':wheel.read_bytes(),
        'wheel_manifest':(ROOT/'trials/arc-agi-2-qwen35-nvarc/configs/base-wheel-manifest.json').read_bytes()}
    hashes={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    payloads={k:base64.b64encode(zlib.compress(v,9)).decode() for k,v in raw.items()}
    (package/'kernel').mkdir();atomic(package/'plan.json',plan);(package/'samples.json').write_bytes(raw['samples'])
    atomic(package/'kernel/notebook.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':
        {'display_name':'Python 3','language':'python','name':'python3'}},'cells':[{'cell_type':'code',
        'execution_count':None,'metadata':{},'outputs':[],'source':render(run,payloads,hashes).splitlines(keepends=True)}]})
    atomic(package/'kernel/kernel-metadata.json',metadata(plan))
    atomic(package/'stage-summary.json',{'run_id':run,'plan_digest':digest_value(plan),'payload_sha256':hashes,
        'inventory':{p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    plan=json.loads((package/'plan.json').read_bytes());summary=json.loads((package/'stage-summary.json').read_bytes())
    expected,rows=make_plan(plan['run_id'])
    require(plan==expected and digest_value(plan)==summary['plan_digest'] and
        {p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file() and p.name!='stage-summary.json'}==summary['inventory'],
        'exact original SFT package bindings required')
    require(json.loads((package/'kernel/kernel-metadata.json').read_bytes())==metadata(plan),
            'exact private offline original SFT transport required')
    source=''.join(json.loads((package/'kernel/notebook.ipynb').read_bytes())['cells'][0]['source'])
    values={node.targets[0].id:ast.literal_eval(node.value) for node in ast.parse(source).body if isinstance(node,ast.Assign)
        and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'RUN','PAYLOADS','HASHES'}}
    raw={k:zlib.decompress(base64.b64decode(v,validate=True)) for k,v in values['PAYLOADS'].items()}
    require(set(raw)=={'plan','samples','runtime_wheel','wheel_manifest'} and values['RUN']==plan['run_id'] and
        raw['wheel_manifest']==(ROOT/'trials/arc-agi-2-qwen35-nvarc/configs/base-wheel-manifest.json').read_bytes() and
        raw['plan']==canonical_bytes(plan,newline=True) and
        raw['samples']==canonical_bytes(rows,newline=True) and values['HASHES']==summary['payload_sha256']==
        {k:hashlib.sha256(v).hexdigest() for k,v in raw.items()} and source==render(plan['run_id'],values['PAYLOADS'],values['HASHES']),
        'exact original parent/data/runtime payload required')
    with zipfile.ZipFile(package/'wheel/irisx-0.2.0-py3-none-any.whl') as wheel:
        require(raw['runtime_wheel']==(package/'wheel/irisx-0.2.0-py3-none-any.whl').read_bytes(),'embedded original wheel differs')
        for name in ('arc_nvarc_qwen3_sft','arc_nvarc_source_sft','arc_nvarc_source_stream','arc_nvarc_fsdp_sft',
                     'arc_nvarc_sft_step','arc_nvarc_qwen3_packing','arc_nvarc_segmented_linear'):
            require(wheel.read('irisx/'+name+'.py')==(ROOT/'src/irisx'/ (name+'.py')).read_bytes(),'exact original runner implementation required')
    return {'run_id':plan['run_id'],'plan_digest':digest_value(plan),'offline_package_verified':True,'external_calls':0,
        'optimizer_steps':2,'source_input_tokens':plan['scheduled_input_tokens'],'maximum_outer_forwards':plan['maximum_outer_forwards'],
        'minimum_free_working_bytes':plan['checkpoint_storage_bound']['minimum_free_working_bytes']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--run-id')
    args=parser.parse_args();print(json.dumps(stage(args.package,args.run_id) if args.action=='stage' else preflight(args.package)))
