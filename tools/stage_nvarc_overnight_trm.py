"""Immutable bounded TRM pretraining prefix with full source embedding axis."""
from __future__ import annotations
import argparse,ast,base64,hashlib,json,re,sys,zipfile,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools import irisx_build_backend as build
from tools.nvarc_source import verify as verify_source
from irisx.arc_nvarc_trm_runtime import build_runtime_bundle,verify_runtime_bundle
from irisx.arc_nvarc_trm_training import build_training_reference,reference_functions,REFERENCE_HASHES,training_config,training_model_config
from irisx.arc_nvarc_datasets import sha_file
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
SOURCE=ROOT/'.irisx/arc-agi-2/qwen35-nvarc/source'
TRIAL=ROOT/'trials/arc-agi-2-qwen35-nvarc'
AUDIT=ROOT/'.irisx/nvarc-original/manifests/trm-published-train-audit-20261002-001'


def render(payloads,hashes,files,run):
    source=(ROOT/'tools/nvarc_overnight_trm_notebook.py.tmpl').read_text(encoding='utf-8')
    for key,value in {'__RUN__':json.dumps(run),'__PAYLOADS__':json.dumps(payloads),'__HASHES__':json.dumps(hashes,sort_keys=True),
        '__FILES__':json.dumps(files,sort_keys=True),'__HARDWARE_HELPER__':(ROOT/'src/irisx/arc_nvarc_hardware.py').read_text(encoding='utf-8')}.items():
        source=source.replace(key,value)
    compile(source,'source-trm-training','exec')
    return source


def stage(output,run):
    if output.exists() or not re.fullmatch(r'nvarc-overnight-trm-\d{3}',run):raise ValidationError('new Goal TRM identity required')
    verify_source(SOURCE,json.loads((TRIAL/'source-manifest.json').read_bytes()))
    audit=json.loads((AUDIT/'audit.json').read_bytes())
    first=json.loads((AUDIT/'group-lineage.jsonl').open(encoding='utf-8').readline())
    prefix=AUDIT/'training-prefix.npz'
    if (audit['training_prefix_sha256']!=sha_file(prefix) or audit['prefix_supervised_tokens']!=792 or
        audit['prefix_input_tokens']!=7200 or first['base']!='8b28cd80' or first['example_range']!=[0,1799] or
        first['exposure_tags']!=['public-training-only']):raise ValidationError('verified public-training TRM prefix required')
    source_binding=build_runtime_bundle(SOURCE/'NVARC/external/TinyRecursiveModels',output/'trm-source-bundle')
    ref_digest=build_training_reference(SOURCE/'NVARC',output/'training-reference')
    config=training_config();model_config=training_model_config()
    identity={'config':config,'model_config':model_config,'prefix_sha256':sha_file(prefix),
        'source_bundle_digest':source_binding['bundle_digest'],'training_reference_digest':ref_digest,'parent_lineage':first}
    optimizer=ROOT/'.irisx/nvarc-original/materials/trm-runtime-wheels-20261002-001/adam_atan2_pytorch-0.2.4-py3-none-any.whl'
    plan={'format':'irisx/nvarc-source-trm-training-v1','run_id':run,'kernel_id':'danielwuu/'+run,'approved':True,
        'owner_decision':'Decision 0053','maximum_paid_usd':0,'maximum_teacher_calls':0,'maximum_generations':0,
        'maximum_optimizer_steps':2,'maximum_notebook_wall_seconds':2700,'config':config,'model_config':model_config,
        'identity_digest':digest_value(identity),**{key:value for key,value in identity.items() if key not in {'config','model_config'}},
        'audit_sha256':sha_file(AUDIT/'audit.json'),'optimizer_wheel_sha256':sha_file(optimizer),
        'datasets':{'wheels':'danielwuu/irisx-arc-agi-2-trial-002-smoke-001'},'kernel_sources':[],
        'competition_sources':['arc-prize-2026-arc-agi-2'],'retain_export':True,'contains_evaluator_truth':False,
        'full_scale_training_verified':False,'correctness_scored':False,'evaluation_members_staged':False,
        'sample_policy':'repeat the verified first eight training-array rows for two steps; not the source shuffled epoch',
        'original_recipe_gap':'one L4/global batch 8/two steps/uncompiled; not eight H100/global 3072/10000 epochs'}
    (output/'wheel').mkdir();wheel=output/'wheel'/build.build_wheel(str(output/'wheel'))
    raw={'plan':canonical_bytes(plan,newline=True),'wheel_manifest':(TRIAL/'configs/base-wheel-manifest.json').read_bytes(),
        'training_prefix':prefix.read_bytes(),'runtime_wheel':wheel.read_bytes(),'optimizer_wheel':optimizer.read_bytes()}
    files={'plan':'plan.json','wheel_manifest':'wheel_manifest.json','training_prefix':'training-prefix.npz',
        'runtime_wheel':wheel.name,'optimizer_wheel':optimizer.name}
    for key in ('plan','wheel_manifest','training_prefix','optimizer_wheel'):(output/files[key]).write_bytes(raw[key])
    for folder in ('trm-source-bundle','training-reference'):
        for index,path in enumerate(sorted((output/folder).rglob('*'))):
            if path.is_file():
                key=folder.replace('-','_')+'_'+str(index);raw[key]=path.read_bytes();files[key]=path.relative_to(output).as_posix()
    hashes={key:hashlib.sha256(value).hexdigest() for key,value in raw.items()}
    source=render({key:base64.b64encode(zlib.compress(value,9)).decode() for key,value in raw.items()},hashes,files,run)
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},
        'cells':[{'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':source.splitlines(keepends=True)}]}
    kernel=output/'kernel';kernel.mkdir();(kernel/'notebook.ipynb').write_bytes(canonical_bytes(notebook,newline=True))
    meta={'id':plan['kernel_id'],'title':run,'code_file':'notebook.ipynb','language':'python','kernel_type':'notebook',
        'is_private':True,'enable_gpu':True,'enable_tpu':False,'enable_internet':False,'machine_shape':'NvidiaL4',
        'dataset_sources':list(plan['datasets'].values()),'kernel_sources':[],'competition_sources':plan['competition_sources'],'model_sources':[]}
    (kernel/'kernel-metadata.json').write_bytes(canonical_bytes(meta,newline=True))
    summary={'format':'irisx/nvarc-overnight-stage-v1','run_id':run,'plan_digest':digest_value(plan),'payload_sha256':hashes,
        'inventory':{path.relative_to(output).as_posix():sha_file(path) for path in output.rglob('*') if path.is_file()},'external_calls':0}
    (output/'stage-summary.json').write_bytes(canonical_bytes(summary,newline=True));return summary


def preflight(output):
    summary=json.loads((output/'stage-summary.json').read_bytes());plan=json.loads((output/'plan.json').read_bytes())
    actual={path.relative_to(output).as_posix():sha_file(path) for path in output.rglob('*') if path.is_file() and path.name!='stage-summary.json'}
    if actual!=summary['inventory'] or digest_value(plan)!=summary['plan_digest']:raise ValidationError('closed TRM package differs')
    source=''.join(json.loads((output/'kernel/notebook.ipynb').read_bytes())['cells'][0]['source']);values={}
    for node in ast.parse(source).body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'RUN','PAYLOADS','HASHES','FILES'}:
            values[node.targets[0].id]=ast.literal_eval(node.value)
    if source!=render(values['PAYLOADS'],values['HASHES'],values['FILES'],values['RUN']):raise ValidationError('TRM runtime template differs')
    decoded={key:zlib.decompress(base64.b64decode(value,validate=True)) for key,value in values['PAYLOADS'].items()}
    if {key:hashlib.sha256(value).hexdigest() for key,value in decoded.items()}!=summary['payload_sha256'] or values['HASHES']!=summary['payload_sha256']:
        raise ValidationError('TRM embedded bytes differ')
    if (json.loads(decoded['plan'])!=plan or plan['config']!=training_config() or plan['model_config']!=training_model_config() or
        plan['maximum_optimizer_steps']!=2 or plan['maximum_generations']!=0 or plan['maximum_paid_usd']!=0 or
        plan['prefix_sha256']!=hashlib.sha256(decoded['training_prefix']).hexdigest() or
        plan['optimizer_wheel_sha256']!=hashlib.sha256(decoded['optimizer_wheel']).hexdigest()):raise ValidationError('TRM workload/material differs')
    for key,path in values['FILES'].items():
        target=next((output/'wheel').glob('*.whl')) if key=='runtime_wheel' else output/path
        if target.read_bytes()!=decoded[key]:raise ValidationError('TRM saved versus embedded payload differs')
    verify_runtime_bundle(output/'trm-source-bundle',plan['source_bundle_digest']);reference_functions(output/'training-reference')
    if digest_value(REFERENCE_HASHES)!=plan['training_reference_digest']:raise ValidationError('TRM reference digest differs')
    with zipfile.ZipFile(next((output/'wheel').glob('*.whl'))) as archive:
        for name in ('arc_nvarc_trm_training.py','arc_nvarc_trm_runtime.py','arc_nvarc_m3_trm.py'):
            if archive.read('irisx/'+name)!=(ROOT/'src/irisx'/name).read_bytes():raise ValidationError('TRM implementation differs')
    meta=json.loads((output/'kernel/kernel-metadata.json').read_bytes())
    if (meta['id']!=plan['kernel_id'] or meta['title']!=plan['run_id'] or meta['is_private'] is not True or meta['enable_internet'] is not False or
        meta['machine_shape']!='NvidiaL4' or meta['kernel_sources']!=[] or meta['dataset_sources']!=list(plan['datasets'].values()) or
        meta['competition_sources']!=plan['competition_sources']):raise ValidationError('TRM private transport differs')
    return {'run_id':plan['run_id'],'plan_digest':digest_value(plan),'offline_package_verified':True,'external_calls':0,
        'maximum_optimizer_steps':2,'maximum_generations':0,'maximum_paid_usd':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight'));parser.add_argument('--output',type=Path,required=True);parser.add_argument('--run')
    args=parser.parse_args();print(json.dumps(stage(args.output,args.run) if args.action=='stage' else preflight(args.output),indent=2))
