"""Original-family one-step package; requires actual prior CUDA differential."""
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
from tools.nvarc_qwen3_material import DEFAULT,inventory
from tools.verify_nvarc_qwen3_probe import verify
from irisx.arc_nvarc_combined import atomic,sha
from irisx.arc_nvarc_gpu_preflight_v2 import RECIPE
from irisx.arc_nvarc_qwen3_packed_step import FORMAT,BASE,PREFIX_SHA,check_plan,schedule
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError


def prerequisite(folder):
    ledger=json.loads((folder/'execution-final/execution-ledger.json').read_bytes())
    if (not re.fullmatch(r'nvarc-original-qwen3-probe-\d{3}',folder.name) or
            ledger.get('run_id')!=folder.name or ledger.get('accepted') is not True or ledger.get('push_reserved')!=1 or
            ledger.get('owner_decision')!='Decision 0054' or ledger.get('retrieval_reserved')!=1 or
            ledger.get('provider_version')!=1 or not ledger.get('terminal_observed') or
            ledger['events'][-1].get('outcome')!='retrieved'):
        raise ValidationError('sole verified terminal retrieval of the distinct native probe required')
    archive=folder/'execution-final/retrieved/gpu-preflight-result.zip'
    proof=verify(archive,folder/'package-l4')
    if (proof['outcome']!='complete' or proof.get('native_varlen_gpu_differential_observed') is not True or
            proof.get('model_material_digest')!=BASE):
        raise ValidationError('actual exact-material native CUDA numeric prerequisite has not passed')
    return {'run_id':folder.name,'archive_sha256':sha(archive),
        'plan_digest':ledger['bindings']['plan_digest'],'model_material_digest':BASE,
        'native_cuda_differential_observed':True}


def render(payloads,hashes,run):
    source=(ROOT/'tools/nvarc_qwen3_packed_step_notebook.py.tmpl').read_text(encoding='utf-8')
    replacements={'__RUN__':json.dumps(run),'__PAYLOADS__':json.dumps(payloads),'__HASHES__':json.dumps(hashes),
        '__HARDWARE_HELPER__':(ROOT/'src/irisx/arc_nvarc_hardware.py').read_text(encoding='utf-8')}
    for key,value in replacements.items():source=source.replace(key,value)
    compile(source,'original-qwen3-packed-step','exec');return source


def stage(output,run,probe):
    if output.exists() or not re.fullmatch(r'nvarc-original-qwen3-packed-step-\d{3}',run):
        raise ValidationError('new immutable original-family one-step package required')
    dependency=prerequisite(probe)
    material=json.loads((DEFAULT/'conversion.json').read_bytes())
    proof=json.loads((DEFAULT/'independent-verification.json').read_bytes())
    if proof['material_digest']!=BASE or material['material_digest']!=BASE or inventory(DEFAULT/'compact')!=material['compact_inventory']:
        raise ValidationError('byte-verified original base required')
    prefix=ROOT/'.irisx/nvarc-original/materials/source-shuffle-prefix-20261002-001'
    source_proof=json.loads((prefix/'verification.json').read_bytes())
    samples=json.loads((prefix/'samples.json').read_bytes())
    if (sha(prefix/'samples.json')!=PREFIX_SHA or source_proof['samples_sha256']!=PREFIX_SHA or
            source_proof['cursor']!=512 or len(samples)!=512 or digest_value(samples)!=source_proof['sample_digest']):
        raise ValidationError('exact complete original first two shuffled batches required')
    rows=samples[:256];placement=schedule(rows)
    total=sum(len(r['input_ids']) for r in rows)
    plan={'format':FORMAT,'approved':True,'owner_decision':'Decision 0054','run_id':run,'kernel_id':'danielwuu/'+run,
        'world_size':4,'backend':'torch-2.10-native-varlen-flash-fsdp-cpu-state',
        'maximum_notebook_wall_seconds':4500,'maximum_worker_wall_seconds':4200,
        'maximum_optimizer_steps':1,'maximum_paid_usd':0,'maximum_generations':0,'maximum_teacher_calls':0,
        'retain_export':False,'source_recipe':RECIPE,'global_batch_size':256,
        'packing_capacity':256000,'packing_length_multiple':64,'maximum_physical_input_tokens':32768,
        'physical_schedule':placement,'maximum_outer_forwards':placement['collective_slots_per_rank']*4,
        'scheduled_input_tokens':total,'maximum_input_tokens':total+2*placement['dummy_outer_forwards'],
        'scheduled_supervised_tokens':sum(sum(v>=0 for v in r['labels'][1:]) for r in rows),
        'data_digest':digest_value(rows),'source_prefix_sha256':PREFIX_SHA,
        'source_prefix_verification_sha256':sha(prefix/'verification.json'),
        'model_material_digest':BASE,'material_manifest_sha256':sha(DEFAULT/'conversion.json'),
        'model_repo':material['repo'],'model_revision':material['revision'],'model_dataset_version':1,
        'datasets':{'base':'danielwuu/irisx-nvarc-original-qwen3-001','wheels':'danielwuu/irisx-arc-agi-2-trial-002-smoke-001'},
        'competition_sources':['arc-prize-2026-arc-agi-2'],'competition_files_opened':0,
        'hardware_gate':'four distinct BF16 L4s; one FSDP rank on each; CPU host state',
        'cuda_differential_prerequisite':dependency,'filtered_records':0,'truncated_records':0,
        'full_sft_completed':False,'historical_base_commit_known':False,'original_sft_checkpoint':False,
        'original_nemo_version':None,'original_unsloth_version':None,'historical_parameter_tying_known':False,
        'parameter_tying_policy':'retain acquired HF base tying; published SFT is separately untied',
        'material_policy':'retain every source/dual parent/exposure; no evaluator answers',
        'execution_control':'private offline one-step SAVE_AND_RUN_ALL, finite monitoring, one terminal retrieval'}
    check_plan(plan,rows);(output/'wheel').mkdir(parents=True)
    wheel=output/'wheel'/build.build_wheel(str(output/'wheel'))
    raw={'plan':canonical_bytes(plan,newline=True),'samples':canonical_bytes(rows,newline=True),
        'runtime_wheel':wheel.read_bytes(),
        'wheel_manifest':(ROOT/'trials/arc-agi-2-qwen35-nvarc/configs/base-wheel-manifest.json').read_bytes()}
    hashes={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    payloads={k:base64.b64encode(zlib.compress(v,9)).decode() for k,v in raw.items()}
    (output/'kernel').mkdir();atomic(output/'plan.json',plan);(output/'samples.json').write_bytes(raw['samples'])
    atomic(output/'kernel/notebook.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':
        {'display_name':'Python 3','language':'python','name':'python3'}},'cells':[{'cell_type':'code',
        'execution_count':None,'metadata':{},'outputs':[],'source':render(payloads,hashes,run).splitlines(keepends=True)}]})
    atomic(output/'kernel/kernel-metadata.json',{'id':plan['kernel_id'],'title':run,'code_file':'notebook.ipynb',
        'language':'python','kernel_type':'notebook','is_private':True,'enable_gpu':True,'enable_internet':False,
        'dataset_sources':list(plan['datasets'].values()),'competition_sources':plan['competition_sources'],'kernel_sources':[]})
    atomic(output/'stage-summary.json',{'run_id':run,'plan_digest':digest_value(plan),'payload_sha256':hashes,
        'inventory':{p.relative_to(output).as_posix():sha(p) for p in output.rglob('*') if p.is_file()}})
    return preflight(output)


def preflight(package):
    summary=json.loads((package/'stage-summary.json').read_bytes())
    if {p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file() and p.name!='stage-summary.json'}!=summary['inventory']:
        raise ValidationError('closed one-step package differs')
    plan=json.loads((package/'plan.json').read_bytes());rows=json.loads((package/'samples.json').read_bytes())
    check_plan(plan,rows)
    probe=ROOT/'.irisx/nvarc-original/runs'/plan['cuda_differential_prerequisite']['run_id']
    if prerequisite(probe)!=plan['cuda_differential_prerequisite']:
        raise ValidationError('successful actual CUDA prerequisite binding differs')
    if digest_value(plan)!=summary['plan_digest']:raise ValidationError('one-step plan binding differs')
    source=''.join(json.loads((package/'kernel/notebook.ipynb').read_bytes())['cells'][0]['source'])
    values={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(source).body if isinstance(n,ast.Assign)
        and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in {'RUN','HASHES','PAYLOADS'}}
    if source!=render(values['PAYLOADS'],values['HASHES'],values['RUN']) or values['HASHES']!=summary['payload_sha256']:
        raise ValidationError('exact one-step notebook template differs')
    for key,encoded in values['PAYLOADS'].items():
        decoder=zlib.decompressobj();raw=decoder.decompress(base64.b64decode(encoded,validate=True),32*1024**2+1)
        if len(raw)>32*1024**2 or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or hashlib.sha256(raw).hexdigest()!=values['HASHES'][key]:
            raise ValidationError('bounded payload bytes differ')
        if key in {'plan','samples'} and raw!=(package/(key+'.json')).read_bytes():raise ValidationError('embedded inputs differ')
        if key=='runtime_wheel' and raw!=next((package/'wheel').glob('*.whl')).read_bytes():raise ValidationError('runtime wheel differs')
    with zipfile.ZipFile(next((package/'wheel').glob('*.whl'))) as archive:
        for name in ('arc_nvarc_qwen3_packed_step.py','arc_nvarc_sft_step.py','arc_nvarc_qwen3_packing.py','arc_nvarc_packing.py'):
            if archive.read('irisx/'+name)!=(ROOT/'src/irisx'/name).read_bytes():raise ValidationError('reviewed source wheel binding differs')
    meta=json.loads((package/'kernel/kernel-metadata.json').read_bytes())
    if (meta['id']!=plan['kernel_id'] or meta['title']!=plan['run_id'] or meta['is_private'] is not True or
            meta['enable_internet'] is not False or meta['kernel_sources'] or
            meta['dataset_sources']!=list(plan['datasets'].values()) or meta['competition_sources']!=plan['competition_sources']):
        raise ValidationError('private exact offline provider metadata differs')
    return {'offline_package_verified':True,'run_id':plan['run_id'],'plan_digest':digest_value(plan),
        'maximum_optimizer_steps':1,'scheduled_input_tokens':plan['scheduled_input_tokens'],'external_calls':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--run-id');parser.add_argument('--probe',type=Path)
    args=parser.parse_args();print(json.dumps(stage(args.package,args.run_id,args.probe) if args.action=='stage' else preflight(args.package)))
