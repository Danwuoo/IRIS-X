"""Bind a complete source epoch to a verified immutable overnight SFT export."""
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
from irisx.arc_nvarc_complete_ttt import check_plan,complete_config
from irisx.arc_nvarc_data import visible_task
from irisx.arc_nvarc_datasets import sha_file
from irisx.arc_nvarc_representation import verify_model_material
from irisx.arc_nvarc_source_bundle import build_bundle,verify_bundle
from irisx.arc_nvarc_training import task_local_sequences
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError

TRIAL=ROOT/'trials/arc-agi-2-qwen35-nvarc'
SOURCE=ROOT/'.irisx/arc-agi-2/qwen35-nvarc/source'


def render(payloads,hashes,files,run):
    source=(ROOT/'tools/nvarc_overnight_ttt_notebook.py.tmpl').read_text(encoding='utf-8')
    for key,value in {'__RUN__':json.dumps(run),'__PAYLOADS__':json.dumps(payloads),'__HASHES__':json.dumps(hashes,sort_keys=True),
        '__FILES__':json.dumps(files,sort_keys=True),'__HARDWARE_HELPER__':(ROOT/'src/irisx/arc_nvarc_hardware.py').read_text(encoding='utf-8')}.items():
        source=source.replace(key,value)
    compile(source,'complete-ttt','exec')
    return source


def source_export(run,*,remote_reference=False):
    if not re.fullmatch(r'nvarc-overnight-sft-\d{3}',run):raise ValidationError('exact new SFT identity required')
    folder=ROOT/'.irisx/nvarc-original/runs'/run
    ledger=json.loads((folder/'execution-final/execution-ledger.json').read_bytes())
    retrieval=ledger['events'][-1]
    if (ledger.get('accepted') is not True or ledger.get('provider_version')!=1 or
            ledger.get('retrieval_reserved')!=1 or retrieval.get('archive_downloads')!=1 or
            (not remote_reference and (retrieval.get('outcome')!='retrieved' or not retrieval.get('export_verified')))):
        raise ValidationError('sole SFT terminal retrieval and exact export proof required')
    archive_path=folder/'execution-final/retrieved/gpu-preflight-result.zip'
    if (retrieval.get('retained_inventory') is not None and
            sha_file(archive_path)!=retrieval['retained_inventory']['gpu-preflight-result.zip']):
        raise ValidationError('retained SFT terminal archive bytes differ')
    with zipfile.ZipFile(archive_path) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        if manifest['run_id']!=run or manifest['plan_digest']!=ledger['bindings']['plan_digest']:
            raise ValidationError('source SFT archive identity differs')
        names=[item['path'] for item in manifest['members']]
        if len(set(names))!=len(names) or len(archive.namelist())!=len(names)+1 or set(archive.namelist())!=set(names)|{'manifest.json'}:
            raise ValidationError('source SFT archive closed inventory differs')
        for item in manifest['members']:
            raw=archive.read(item['path'])
            if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:
                raise ValidationError('source SFT archive member differs')
        if (json.loads(archive.read('plan.json'))!=json.loads((folder/'package-l4/plan.json').read_bytes()) or
                json.loads(archive.read('payload-bindings.json'))!=json.loads((folder/'package-l4/stage-summary.json').read_bytes())['payload_sha256']):
            raise ValidationError('source SFT exact returned input bindings differ')
        chain=json.loads(archive.read('worker/export-chain.json'))
        final=json.loads(archive.read('worker/final-result.json'))
        terminal=json.loads(archive.read('terminal.json'))
        material=json.loads(archive.read('retained-export-manifest.json'))
    if (terminal['outcome']!='complete' or chain['identity_digest']!=final['identity_digest'] or
            chain['export_material_digest']!=terminal['export_material_digest'] or
            material['training_identity_digest']!=chain['identity_digest'] or
            digest_value(material)!=chain['export_material_digest'] or
            not chain['reload_tensor_bytes_identical']):
        raise ValidationError('source SFT export chain differs')
    model=folder/'execution-final/retrieved/export'
    if not remote_reference:verify_model_material(model,chain['export_material_digest'])
    chain['source_terminal_archive_sha256']=sha_file(archive_path)
    return model,chain,final


def stage(output:Path,run:str,sft_run:str,*,remote_reference=False,joint_trm=False):
    if output.exists() or not re.fullmatch(r'nvarc-overnight-ttt-\d{3}',run):raise ValidationError('new complete TTT package required')
    model,chain,final=source_export(sft_run,remote_reference=remote_reference)
    binding=build_bundle(SOURCE,TRIAL/'source-manifest.json',output/'source-bundle')
    raw=json.loads((SOURCE/'NVARC/external/ARC-AGI-2/data/training/00576224.json').read_bytes())
    task=visible_task('00576224',raw)
    visible={task['task_id']:{'train':task['train'],'test':task['test']}}
    config=complete_config()
    rows=task_local_sequences(task,seed=42,augmentation_count=16,source_qwen=True,source_augmentation_seed=1,source_max_length=8192)
    if len(rows)!=128:raise ValidationError('full public task source epoch differs')
    plan={'format':'irisx/nvarc-complete-ttt-v1','run_id':run,'kernel_id':'danielwuu/'+run,
        'backend':'cuda-l4','approved':True,'owner_decision':'Decision 0053','maximum_paid_usd':0,'maximum_teacher_calls':0,
        'config_digest':digest_value(config),'visible_digest':digest_value([task]),'maximum_tasks':1,
        'maximum_generations':16,'maximum_optimizer_steps':128,'maximum_verifications':34,'maximum_outer_model_forwards':66000,
        'material_digest':chain['export_material_digest'],'training_identity_digest':chain['identity_digest'],
        'source_bundle_digest':binding['bundle_digest'],'source_kernel':'danielwuu/'+sft_run,'source_kernel_version':1,
        'source_terminal_archive_sha256':chain['source_terminal_archive_sha256'],
        'local_export_bytes_verified_at_stage':not remote_reference,'runtime_export_bytes_verification_required':True,
        'sft_optimizer_steps':final['step'],'sft_input_tokens':final['input_tokens'],
        'source_epoch_input_tokens':sum(len(row['input_ids']) for row in rows),
        'source_epoch_max_sequence_length':max(len(row['input_ids']) for row in rows),
        'datasets':{'wheels':'danielwuu/irisx-arc-agi-2-trial-002-smoke-001'},
        'competition_sources':['arc-prize-2026-arc-agi-2'],'maximum_notebook_wall_seconds':4500,
        'retain_export':False,'contains_evaluator_truth':False,'correctness_scored':False,'full_scale_sft_verified':False,
        'exposure':'repeated public tuning parent; original-source exposure retained; not a fresh holdout',
        'demonstration_probe_policy':'two public-demo outputs scored under eight views; never model candidates or solutions'}
    if joint_trm:
        from irisx.arc_nvarc_trm_runtime import build_runtime_bundle
        from irisx.arc_nvarc_trm_checkpoint import published_model_config
        from tools.nvarc_source import verify as verify_source
        verify_source(SOURCE,json.loads((TRIAL/'source-manifest.json').read_bytes()))
        trm_binding=build_runtime_bundle(SOURCE/'NVARC/external/TinyRecursiveModels',output/'trm-source-bundle')
        optimizer_wheel=ROOT/'.irisx/nvarc-original/materials/trm-runtime-wheels-20261002-001/adam_atan2_pytorch-0.2.4-py3-none-any.whl'
        plan['joint_trm']={'dataset':'cpmpml/arc-prize-trm-031/1','file':'step_220708',
            'checkpoint_sha256':'dbf771737d9799b84faf009c24c5376831f095d2cfd66debbe9a505a445bfc31',
            'source_bundle_digest':trm_binding['bundle_digest'],'model_config':published_model_config(device_dtype='bfloat16'),
            'maximum_optimizer_steps':1,'maximum_views':8,'maximum_act_forwards':80,'maximum_candidates':8,
            'joint_verification_state':'same adapted Qwen state before task reset',
            'optimizer_wheel_sha256':sha_file(optimizer_wheel),'optimizer_version':'0.2.4',
            'workload_variant':'one public demo update; eight D4 views; no color augmentation; not original 2000-epoch TTT'}
        plan['maximum_verifications']=42
        plan['datasets']['trm']='cpmpml/arc-prize-trm-031'
    check_plan(plan,config,[task])
    (output/'wheel').mkdir()
    wheel=output/'wheel'/build.build_wheel(str(output/'wheel'))
    payloads={'plan':canonical_bytes(plan,newline=True),'config':canonical_bytes(config,newline=True),
        'visible':canonical_bytes(visible,newline=True),'wheel_manifest':(TRIAL/'configs/base-wheel-manifest.json').read_bytes(),
        'runtime_wheel':wheel.read_bytes()}
    files={key:key+'.json' for key in payloads};files['runtime_wheel']=wheel.name
    if joint_trm:
        payloads['trm_optimizer_wheel']=optimizer_wheel.read_bytes()
        files['trm_optimizer_wheel']=optimizer_wheel.name
        (output/optimizer_wheel.name).write_bytes(payloads['trm_optimizer_wheel'])
    for key in ('plan','config','visible','wheel_manifest'):(output/files[key]).write_bytes(payloads[key])
    for index,path in enumerate(sorted((output/'source-bundle').rglob('*'))):
        if path.is_file():
            key='bundle_'+str(index);payloads[key]=path.read_bytes();files[key]='source-bundle/'+path.relative_to(output/'source-bundle').as_posix()
    if joint_trm:
        for index,path in enumerate(sorted((output/'trm-source-bundle').rglob('*'))):
            if path.is_file():
                key='trm_bundle_'+str(index);payloads[key]=path.read_bytes();files[key]='trm-source-bundle/'+path.relative_to(output/'trm-source-bundle').as_posix()
    hashes={key:hashlib.sha256(value).hexdigest() for key,value in payloads.items()}
    source=render({key:base64.b64encode(zlib.compress(value,9)).decode() for key,value in payloads.items()},hashes,files,run)
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},
        'cells':[{'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':source.splitlines(keepends=True)}]}
    kernel=output/'kernel';kernel.mkdir()
    (kernel/'notebook.ipynb').write_bytes(canonical_bytes(notebook,newline=True))
    meta={'id':plan['kernel_id'],'title':run,'code_file':'notebook.ipynb','language':'python','kernel_type':'notebook',
        'is_private':True,'enable_gpu':True,'enable_tpu':False,'enable_internet':False,'machine_shape':'NvidiaL4',
        'dataset_sources':[plan['datasets'][key] for key in sorted(plan['datasets'])],'kernel_sources':[plan['source_kernel']],
        'competition_sources':plan['competition_sources'],'model_sources':[]}
    (kernel/'kernel-metadata.json').write_bytes(canonical_bytes(meta,newline=True))
    summary={'format':'irisx/nvarc-overnight-stage-v1','run_id':run,'plan_digest':digest_value(plan),
        'payload_sha256':hashes,'inventory':{path.relative_to(output).as_posix():sha_file(path) for path in output.rglob('*') if path.is_file()},'external_calls':0}
    (output/'stage-summary.json').write_bytes(canonical_bytes(summary,newline=True))
    return summary


def preflight(output:Path):
    summary=json.loads((output/'stage-summary.json').read_bytes())
    actual={path.relative_to(output).as_posix():sha_file(path) for path in output.rglob('*') if path.is_file() and path.name!='stage-summary.json'}
    if actual!=summary['inventory']:raise ValidationError('complete TTT closed package differs')
    source=''.join(json.loads((output/'kernel/notebook.ipynb').read_bytes())['cells'][0]['source']);values={}
    for node in ast.parse(source).body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'RUN','PAYLOADS','HASHES','FILES'}:
            values[node.targets[0].id]=ast.literal_eval(node.value)
    if source!=render(values['PAYLOADS'],values['HASHES'],values['FILES'],values['RUN']):raise ValidationError('complete TTT template differs')
    decoded={key:zlib.decompress(base64.b64decode(value,validate=True)) for key,value in values['PAYLOADS'].items()}
    if {key:hashlib.sha256(value).hexdigest() for key,value in decoded.items()}!=values['HASHES'] or values['HASHES']!=summary['payload_sha256']:
        raise ValidationError('complete TTT payload hashes differ')
    plan=json.loads(decoded['plan']);config=json.loads(decoded['config']);visible=json.loads(decoded['visible'])
    check_plan(plan,config,[visible_task(key,value) for key,value in sorted(visible.items())])
    if digest_value(plan)!=summary['plan_digest'] or plan['run_id']!=values['RUN']:raise ValidationError('complete TTT plan identity differs')
    for key,path in values['FILES'].items():
        if key=='runtime_wheel':target=next((output/'wheel').glob('*.whl'))
        else:target=output/path
        if target.read_bytes()!=decoded[key]:raise ValidationError('complete TTT file bytes differ')
    with zipfile.ZipFile(next((output/'wheel').glob('*.whl'))) as archive:
        for name in ('arc_nvarc_complete_ttt.py','arc_nvarc_training.py','arc_nvarc_source_recipe.py','arc_nvarc_candidates.py'):
            if archive.read('irisx/'+name)!=(ROOT/'src/irisx'/name).read_bytes():raise ValidationError('complete TTT implementation differs')
        if plan.get('joint_trm') is not None:
            from irisx.arc_nvarc_trm_runtime import verify_runtime_bundle
            verify_runtime_bundle(output/'trm-source-bundle',plan['joint_trm']['source_bundle_digest'])
            if (hashlib.sha256(decoded['trm_optimizer_wheel']).hexdigest()!=plan['joint_trm']['optimizer_wheel_sha256'] or
                    archive.read('irisx/arc_nvarc_trm_runtime.py')!=(ROOT/'src/irisx/arc_nvarc_trm_runtime.py').read_bytes()):
                raise ValidationError('joint TRM optimizer/runtime differs')
    verify_bundle(output/'source-bundle',plan['source_bundle_digest'])
    _,chain,_=source_export(plan['source_kernel'].split('/')[1],remote_reference=not plan['local_export_bytes_verified_at_stage'])
    if chain['export_material_digest']!=plan['material_digest'] or chain['identity_digest']!=plan['training_identity_digest']:
        raise ValidationError('complete TTT source export differs')
    if chain['source_terminal_archive_sha256']!=plan['source_terminal_archive_sha256'] or not plan['runtime_export_bytes_verification_required']:
        raise ValidationError('complete TTT source archive/onsite material verification differs')
    meta=json.loads((output/'kernel/kernel-metadata.json').read_bytes())
    if (meta['id']!=plan['kernel_id'] or meta['title']!=plan['run_id'] or meta['is_private'] is not True or
            meta['enable_internet'] is not False or meta['machine_shape']!='NvidiaL4' or
            meta['dataset_sources']!=list(plan['datasets'].values()) or meta['kernel_sources']!=[plan['source_kernel']] or
            meta['competition_sources']!=plan['competition_sources']):raise ValidationError('complete TTT private transport differs')
    return {'run_id':plan['run_id'],'plan_digest':digest_value(plan),'offline_package_verified':True,'external_calls':0,
        'runtime_verified':False,'maximum_optimizer_steps':128,'maximum_generations':16,'maximum_paid_usd':0,
        'joint_trm_enabled':plan.get('joint_trm') is not None,'maximum_verifications':plan['maximum_verifications']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--run');parser.add_argument('--sft-run')
    parser.add_argument('--remote-export-proof',action='store_true',help='Use the exact retrieved export manifest; verify all mounted weight bytes before model work on Kaggle.')
    parser.add_argument('--joint-trm',action='store_true')
    args=parser.parse_args()
    print(json.dumps(stage(args.output,args.run,args.sft_run,remote_reference=args.remote_export_proof,joint_trm=args.joint_trm) if args.action=='stage' else preflight(args.output),indent=2))
