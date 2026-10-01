"""Exact private free Goal package for accumulated source SFT and export."""
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
from tools import irisx_build_backend as build
from tools.stage_nvarc_gpu_preflight_v2 import select_samples
from irisx.arc_nvarc_datasets import sha_file
from irisx.arc_nvarc_gpu_preflight_v2 import BASE,CORPUS_SHA,RECIPE
from irisx.arc_nvarc_source_sft import check_plan,FrozenSequences,identity_for
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError

TRIAL=ROOT/'trials/arc-agi-2-qwen35-nvarc'


def render(payloads,hashes,run):
    source=(ROOT/'tools/nvarc_overnight_sft_notebook.py.tmpl').read_text(encoding='utf-8')
    for key,value in {'__PAYLOADS__':json.dumps(payloads),'__HASHES__':json.dumps(hashes,sort_keys=True),
        '__RUN__':json.dumps(run),'__HARDWARE_HELPER__':(ROOT/'src/irisx/arc_nvarc_hardware.py').read_text(encoding='utf-8')}.items():
        source=source.replace(key,value)
    compile(source,'overnight-sft','exec')
    return source


def stage(output:Path,run:str):
    if output.exists() or not re.fullmatch(r'nvarc-overnight-sft-\d{3}',run):
        raise ValidationError('new immutable overnight SFT package required')
    # Repeat the frozen eight whole rows for two accumulated optimizer steps.
    # This is an integration schedule, explicitly distinct from a corpus epoch.
    samples=select_samples()*2
    plan={'format':'irisx/nvarc-source-sft-v1','approved':True,'owner_decision':'Decision 0053',
        'run_id':run,'kernel_id':'danielwuu/'+run,'backend':'cuda-l4','world_size':4,
        'data_kind':'published-sample-integration','data_digest':digest_value(samples),
        'source_recipe':RECIPE,'base_material_digest':BASE,'corpus_manifest_sha256':CORPUS_SHA,
        'global_batch_size':8,'maximum_optimizer_steps':2,'checkpoint_steps':[1,2],
        'packing_execution':'isolated-segments','packing_capacity':256000,'packing_length_multiple':64,
        'scheduled_input_tokens':sum(len(row['input_ids']) for row in samples),
        'maximum_training_tokens':94156,'maximum_sequence_length':11196,'seed':24,
        'maximum_generations':0,'maximum_teacher_calls':0,'maximum_paid_usd':0,
        'maximum_notebook_wall_seconds':4500,'terminal_reserve_seconds':120,
        'minimum_free_scratch_bytes':60000000000,'minimum_host_available_bytes':140000000000,
        'datasets':{'base':'danielwuu/irisx-nvarc-m2-compact-4b-001','wheels':'danielwuu/irisx-arc-agi-2-trial-002-smoke-001'},
        'competition_sources':['arc-prize-2026-arc-agi-2'],
        'competition_mount_policy':'hardware entitlement only; no competition file reads',
        'material_policy':'original-reproduction namespace; exposure retained; no clean evaluation',
        'full_sft_completed':False,'fused_packing_verified':False,'original_qwen3_nemo_parity':False,
        'export_policy':'retain BF16 HF export; FP32 optimizer checkpoint ephemeral scratch',
        'execution_control':'private SAVE_AND_RUN_ALL, bounded monitoring and one terminal retrieval'}
    check_plan(plan,4)
    (output/'wheel').mkdir(parents=True)
    wheel=output/'wheel'/build.build_wheel(str(output/'wheel'))
    payloads={'plan':canonical_bytes(plan,newline=True),'samples':canonical_bytes(samples,newline=True),
        'wheel_manifest':(TRIAL/'configs/base-wheel-manifest.json').read_bytes(),'runtime_wheel':wheel.read_bytes()}
    hashes={key:hashlib.sha256(value).hexdigest() for key,value in payloads.items()}
    for name in ('plan','samples'):(output/(name+'.json')).write_bytes(payloads[name])
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},
        'cells':[{'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
            'source':render({key:base64.b64encode(value).decode() for key,value in payloads.items()},hashes,run).splitlines(keepends=True)}]}
    kernel=output/'kernel';kernel.mkdir()
    (kernel/'notebook.ipynb').write_bytes(canonical_bytes(notebook,newline=True))
    meta={'id':plan['kernel_id'],'title':run,'code_file':'notebook.ipynb','language':'python','kernel_type':'notebook',
        'is_private':True,'enable_gpu':True,'enable_tpu':False,'enable_internet':False,'machine_shape':'NvidiaL4',
        'dataset_sources':list(plan['datasets'].values()),'competition_sources':plan['competition_sources'],
        'kernel_sources':[],'model_sources':[]}
    (kernel/'kernel-metadata.json').write_bytes(canonical_bytes(meta,newline=True))
    summary={'format':'irisx/nvarc-overnight-stage-v1','run_id':run,'plan_digest':digest_value(plan),
        'payload_sha256':hashes,'inventory':{p.relative_to(output).as_posix():sha_file(p) for p in sorted(output.rglob('*')) if p.is_file()},
        'external_calls':0}
    (output/'stage-summary.json').write_bytes(canonical_bytes(summary,newline=True))
    return summary


def preflight(output:Path):
    summary=json.loads((output/'stage-summary.json').read_bytes())
    actual={p.relative_to(output).as_posix():sha_file(p) for p in output.rglob('*') if p.is_file() and p.name!='stage-summary.json'}
    if actual!=summary['inventory']:raise ValidationError('overnight closed package differs')
    source=''.join(json.loads((output/'kernel/notebook.ipynb').read_bytes())['cells'][0]['source'])
    values={}
    for node in ast.parse(source).body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'PAYLOADS','HASHES','RUN'}:
            values[node.targets[0].id]=ast.literal_eval(node.value)
    if source!=render(values['PAYLOADS'],values['HASHES'],values['RUN']):raise ValidationError('overnight notebook differs from template')
    decoded={key:base64.b64decode(value,validate=True) for key,value in values['PAYLOADS'].items()}
    if {key:hashlib.sha256(value).hexdigest() for key,value in decoded.items()}!=values['HASHES'] or values['HASHES']!=summary['payload_sha256']:
        raise ValidationError('overnight payload hashes differ')
    plan=json.loads(decoded['plan']);check_plan(plan,4)
    if plan['run_id']!=values['RUN'] or plan['run_id']!=summary['run_id']:
        raise ValidationError('overnight identity differs')
    if digest_value(plan)!=summary['plan_digest']:raise ValidationError('overnight plan digest differs')
    for key in ('plan','samples'):
        if decoded[key]!=(output/(key+'.json')).read_bytes():raise ValidationError('overnight reviewed data differs')
    identity=identity_for(plan,FrozenSequences(output/'samples.json',plan))
    wheel=next((output/'wheel').glob('*.whl'))
    if wheel.read_bytes()!=decoded['runtime_wheel']:raise ValidationError('overnight wheel payload differs')
    with zipfile.ZipFile(wheel) as archive:
        for name in ('arc_nvarc_source_sft.py','arc_nvarc_sft_step.py','arc_nvarc_packing.py'):
            if archive.read('irisx/'+name)!=(ROOT/'src/irisx'/name).read_bytes():raise ValidationError('overnight implementation binding differs')
        if archive.read('irisx/licenses/NeMo-RL-LICENSE.txt')!=(ROOT/'src/irisx/licenses/NeMo-RL-LICENSE.txt').read_bytes():
            raise ValidationError('packing reference license missing')
    from irisx.arc_nvarc_fsdp_sft import _verify_compact_base
    _verify_compact_base(ROOT/'.irisx/arc-agi-2/qwen35-nvarc/m2-m3/fsdp-approved-003/model-dataset',BASE)
    meta=json.loads((output/'kernel/kernel-metadata.json').read_bytes())
    if (meta['id']!=plan['kernel_id'] or meta['title']!=plan['run_id'] or meta['is_private'] is not True or
            meta['enable_internet'] is not False or meta['machine_shape']!='NvidiaL4' or
            meta['dataset_sources']!=list(plan['datasets'].values()) or meta['competition_sources']!=plan['competition_sources']):
        raise ValidationError('overnight provider metadata differs')
    return {'run_id':plan['run_id'],'plan_digest':digest_value(plan),'identity_digest':identity,
        'offline_package_verified':True,'external_calls':0,'runtime_verified':False,
        'maximum_optimizer_steps':2,'scheduled_input_tokens':plan['scheduled_input_tokens'],'maximum_paid_usd':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--run')
    args=parser.parse_args()
    print(json.dumps(stage(args.output,args.run) if args.action=='stage' else preflight(args.output),indent=2))
