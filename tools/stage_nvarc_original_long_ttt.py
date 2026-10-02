"""Precisely bound published-Qwen3 full long-task epoch, staged offline."""
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
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools import irisx_build_backend as build
from tools.acquire_nvarc_qwen3_sft import DEFAULT as MODEL
from tools.verify_nvarc_qwen3_sft import verified_inventory
from tools.stage_nvarc_overnight_ttt import selected_long_task
from tools.publish_nvarc_original_runtime import REF as RUNTIME_REF
from irisx.arc_nvarc_combined import atomic,sha
from irisx.arc_nvarc_qwen3_long_ttt import FORMAT,MATERIAL,adaptation_config,check_plan
from irisx.arc_nvarc_source_bundle import build_bundle,verify_bundle
from irisx.arc_nvarc_training import task_local_sequences
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError

RUNTIME=ROOT/'.irisx/nvarc-original/materials/qwen3-original-ttt-runtime-wheels-20261002-001'
SOURCE=ROOT/'.irisx/arc-agi-2/qwen35-nvarc/source'
MODEL_REF='sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1'


def render(payloads,hashes,run):
    source=(ROOT/'tools/nvarc_qwen3_long_ttt_notebook.py.tmpl').read_text(encoding='utf-8')
    for key,value in {'__RUN__':json.dumps(run),'__PAYLOADS__':json.dumps(payloads),'__HASHES__':json.dumps(hashes),
            '__HARDWARE_HELPER__':(ROOT/'src/irisx/arc_nvarc_hardware.py').read_text(encoding='utf-8')}.items():
        source=source.replace(key,value)
    compile(source,'original-qwen3-long-epoch','exec');return source


def runtime():
    manifest=json.loads((RUNTIME/'manifest.json').read_bytes());ledger=json.loads((RUNTIME/'dataset-ledger.json').read_bytes())
    if (ledger['dataset_id']!=RUNTIME_REF or ledger['create_reserved']!=1 or ledger['dataset_version']!=1 or
            ledger['state']!='accepted-private-version-1' or ledger.get('last_status')!={'status':'ready','current_version_number':1} or
            digest_value(manifest['inventory'])!=manifest['material_digest'] or
            sha(RUNTIME/'dataset-receipt.json')!=ledger['receipt_sha256']):
        raise ValidationError('exact verified private runtime Dataset version 1 ready required')
    for name,row in manifest['inventory'].items():
        if (RUNTIME/name).stat().st_size!=row['bytes'] or sha(RUNTIME/name)!=row['sha256']:
            raise ValidationError('fixed runtime wheel bytes differ')
    return manifest


def stage(package,run):
    if package.exists() or not re.fullmatch(r'nvarc-original-qwen3-long-ttt-\d{3}',run):
        raise ValidationError('new immutable original-checkpoint long epoch identity required')
    wheels=runtime();inventory=verified_inventory(MODEL)
    proof=json.loads((MODEL/'independent-verification.json').read_bytes())
    if digest_value(inventory)!=MATERIAL or proof['material_digest']!=MATERIAL:
        raise ValidationError('exact independently verified original untied SFT checkpoint required')
    topology=ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-adapter-material-001/result.json'
    observed=json.loads(topology.read_bytes())
    if (observed['outcome']!='complete' or observed['model_material_digest']!=MATERIAL or
            observed['adapter_target_count']!=254 or observed['adapter_rank']!=256 or
            observed['reset_state_bitwise_verified'] is not True or observed['outer_forwards_observed']!=0):
        raise ValidationError('actual original 4B adapter topology/reset prerequisite required')
    task,_,selection=selected_long_task();config=adaptation_config()
    rows=task_local_sequences(task,seed=42,augmentation_count=16,source_qwen=True,
        source_augmentation_seed=1,source_max_length=8192)
    if len(rows)!=128:raise ValidationError('every original source long-task view required')
    binding=build_bundle(SOURCE,ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json',package/'source-bundle')
    visible={task['task_id']:{'train':task['train'],'test':task['test']}}
    plan={'format':FORMAT,'approved':True,'owner_decision':'Decision 0054','run_id':run,'kernel_id':'danielwuu/'+run,
        'config_digest':digest_value(config),'visible_digest':digest_value([task]),'source_rows_digest':digest_value(rows),
        'source_input_tokens':sum(len(row['input_ids']) for row in rows),
        'source_max_sequence_length':max(len(row['input_ids']) for row in rows),'source_view_count':128,
        'maximum_tasks':1,'maximum_optimizer_steps':128,'maximum_outer_forwards':128,'maximum_training_tokens':1048576,
        'maximum_generations':0,'maximum_verifications':0,'maximum_teacher_calls':0,'maximum_paid_usd':0,
        'maximum_notebook_wall_seconds':10800,'maximum_worker_wall_seconds':10560,'retain_export':False,
        'model_material_digest':MATERIAL,'published_model_ref':MODEL_REF,'model_instance_version_id':627758,
        'model_inventory_sha256':sha(MODEL/'independent-verification.json'),
        'actual_adapter_topology_sha256':sha(topology),'runtime_material_digest':wheels['material_digest'],
        'runtime_dataset_version':1,'datasets':{'wheels':RUNTIME_REF},'model_sources':[MODEL_REF],
        'competition_sources':['arc-prize-2026-arc-agi-2'],'competition_files_opened':0,
        'hardware_gate':'four distinct BF16 L4s; one rank-zero model worker',
        'source_bundle_digest':binding['bundle_digest'],'public_task_selection':selection,
        'augmentation_count':16,'source_augmentation_seed':1,'reference_epoch_seed':42,
        'embedding_head_tied':False,'full_sft_completed':False,'historical_unsloth_version':None,
        'historical_task_clock_parity':False,'original_teacher_regeneration':False,
        'material_policy':'public training demonstrations only; all parent/exposure tags retained; no clean score',
        'execution_control':'private Internet-disabled bounded SAVE_AND_RUN_ALL; one terminal retrieval'}
    check_plan(plan,config,[task]);(package/'wheel').mkdir()
    wheel=package/'wheel'/build.build_wheel(str(package/'wheel'))
    files={p.relative_to(package/'source-bundle').as_posix():base64.b64encode(p.read_bytes()).decode()
        for p in (package/'source-bundle').rglob('*') if p.is_file()}
    raw={'plan':canonical_bytes(plan,newline=True),'config':canonical_bytes(config,newline=True),
        'visible':canonical_bytes(visible,newline=True),'model_inventory':canonical_bytes({'inventory':inventory,'material_digest':MATERIAL},newline=True),
        'source_files':canonical_bytes(files,newline=True),'runtime_wheel':wheel.read_bytes(),'wheel_manifest':canonical_bytes(wheels,newline=True)}
    hashes={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    for key in ('plan','config','visible'):(package/(key+'.json')).write_bytes(raw[key])
    (package/'kernel').mkdir()
    atomic(package/'kernel/notebook.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':
        {'display_name':'Python 3','language':'python','name':'python3'}},'cells':[{'cell_type':'code','execution_count':None,
        'metadata':{},'outputs':[],'source':render({k:base64.b64encode(zlib.compress(v,9)).decode() for k,v in raw.items()},hashes,run).splitlines(keepends=True)}]})
    atomic(package/'kernel/kernel-metadata.json',{'id':plan['kernel_id'],'title':run,'code_file':'notebook.ipynb',
        'language':'python','kernel_type':'notebook','is_private':True,'enable_gpu':True,'enable_internet':False,
        'dataset_sources':[RUNTIME_REF],'competition_sources':plan['competition_sources'],'kernel_sources':[],
        'model_sources':[MODEL_REF]})
    atomic(package/'stage-summary.json',{'run_id':run,'plan_digest':digest_value(plan),'payload_sha256':hashes,
        'inventory':{p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    summary=json.loads((package/'stage-summary.json').read_bytes());plan=json.loads((package/'plan.json').read_bytes())
    config=json.loads((package/'config.json').read_bytes());visible=json.loads((package/'visible.json').read_bytes())
    if {p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file() and p.name!='stage-summary.json'}!=summary['inventory']:
        raise ValidationError('closed original long-epoch package differs')
    from irisx.arc_nvarc_data import visible_task
    tasks=[visible_task(key,value) for key,value in sorted(visible.items())];check_plan(plan,config,tasks)
    if digest_value(plan)!=summary['plan_digest']:raise ValidationError('original long plan digest differs')
    verify_bundle(package/'source-bundle',plan['source_bundle_digest'])
    rows=task_local_sequences(tasks[0],seed=42,augmentation_count=16,source_qwen=True,
        source_augmentation_seed=1,source_max_length=8192)
    if digest_value(rows)!=plan['source_rows_digest'] or sum(len(r['input_ids']) for r in rows)!=plan['source_input_tokens']:
        raise ValidationError('full exact source long-task views differ')
    source=''.join(json.loads((package/'kernel/notebook.ipynb').read_bytes())['cells'][0]['source'])
    values={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(source).body if isinstance(n,ast.Assign)
        and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in {'RUN','HASHES','PAYLOADS'}}
    if (source!=render(values['PAYLOADS'],values['HASHES'],values['RUN']) or
            values['RUN']!=plan['run_id'] or values['HASHES']!=summary['payload_sha256']):
        raise ValidationError('exact reviewed long-epoch template differs')
    expected_keys={'plan','config','visible','model_inventory','source_files','runtime_wheel','wheel_manifest'}
    if set(values['PAYLOADS'])!=expected_keys or set(values['HASHES'])!=expected_keys:
        raise ValidationError('closed long-epoch payload keys differ')
    wheel=next((package/'wheel').glob('*.whl'))
    for key,encoded in values['PAYLOADS'].items():
        decoder=zlib.decompressobj();raw=decoder.decompress(base64.b64decode(encoded,validate=True),32*1024**2+1)
        if len(raw)>32*1024**2 or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or hashlib.sha256(raw).hexdigest()!=values['HASHES'][key]:
            raise ValidationError('bounded exact long payload bytes differ')
        if key in ('plan','config','visible') and raw!=(package/(key+'.json')).read_bytes():raise ValidationError('reviewed input payload differs')
        if key=='wheel_manifest' and json.loads(raw)!=runtime():raise ValidationError('exact runtime manifest payload differs')
        if key=='runtime_wheel' and raw!=wheel.read_bytes():raise ValidationError('embedded/local runtime wheel bytes differ')
        if key=='source_files':
            expected={p.relative_to(package/'source-bundle').as_posix():base64.b64encode(p.read_bytes()).decode()
                for p in (package/'source-bundle').rglob('*') if p.is_file()}
            if json.loads(raw)!=expected:raise ValidationError('embedded/local complete source bundle differs')
        if key=='model_inventory':
            material=json.loads(raw)
            if (material['material_digest']!=MATERIAL or digest_value(material['inventory'])!=MATERIAL or
                    material['inventory']!=verified_inventory(MODEL)):
                raise ValidationError('independently verified embedded model inventory differs')
    with zipfile.ZipFile(wheel) as archive:
        for name in ('arc_nvarc_qwen3_long_ttt.py','arc_nvarc_training.py','arc_nvarc_source_recipe.py','arc_nvarc_qwen3_adapter.py'):
            if archive.read('irisx/'+name)!=(ROOT/'src/irisx'/name).read_bytes():raise ValidationError('reviewed original training wheel differs')
    meta=json.loads((package/'kernel/kernel-metadata.json').read_bytes())
    if (meta['id']!=plan['kernel_id'] or meta['title']!=plan['run_id'] or meta['is_private'] is not True or
            meta['enable_gpu'] is not True or meta['enable_internet'] is not False or
            meta['model_sources']!=[MODEL_REF] or meta['dataset_sources']!=[RUNTIME_REF] or
            meta['competition_sources']!=['arc-prize-2026-arc-agi-2'] or meta['kernel_sources'] or
            plan['competition_sources']!=meta['competition_sources'] or plan['model_sources']!=meta['model_sources'] or
            plan['datasets']!={'wheels':RUNTIME_REF} or plan['published_model_ref']!=MODEL_REF or
            plan['runtime_material_digest']!=runtime()['material_digest']):
        raise ValidationError('private exact original model/runtime source metadata differs')
    return {'offline_package_verified':True,'run_id':plan['run_id'],'plan_digest':digest_value(plan),
        'source_views':128,'source_input_tokens':plan['source_input_tokens'],'maximum_optimizer_steps':128,
        'maximum_generations':0,'external_calls':0,'gpu_epoch_verified':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--run-id')
    args=parser.parse_args();print(json.dumps(stage(args.package,args.run_id) if args.action=='stage' else preflight(args.package)))
