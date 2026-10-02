"""Offline immutable original Qwen3 probe package and exact preflight."""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools import irisx_build_backend as build
from tools.nvarc_qwen3_material import DEFAULT, inventory
from irisx.arc_nvarc_combined import atomic,sha
from irisx.arc_nvarc_packing import pack_sequences
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError


def stage(output,run):
    if output.exists() or not re.fullmatch(r'nvarc-original-qwen3-probe-\d{3}',run):
        raise ValidationError('new immutable original-family probe required')
    material=json.loads((DEFAULT/'conversion.json').read_bytes())
    proof=json.loads((DEFAULT/'independent-verification.json').read_bytes())
    if proof['material_digest']!=material['material_digest'] or inventory(DEFAULT/'compact')!=material['compact_inventory']:
        raise ValidationError('independently byte-verified original material required')
    prefix=ROOT/'.irisx/nvarc-original/materials/source-shuffle-prefix-20261002-001'
    rows=json.loads((prefix/'samples.json').read_bytes())[:8]
    pack_sequences(rows)
    count=sum(len(row['input_ids']) for row in rows)
    plan={'format':'irisx/nvarc-original-qwen3-probe-v1','approved':True,'owner_decision':'Decision 0054',
        'run_id':run,'kernel_id':'danielwuu/'+run,'backend':'torch-2.10-native-varlen-flash',
        'maximum_notebook_wall_seconds':1800,'maximum_worker_wall_seconds':1200,
        'maximum_outer_forwards':13,'maximum_input_tokens':count*3+44,'maximum_optimizer_steps':0,
        'maximum_generations':0,'maximum_teacher_calls':0,'maximum_paid_usd':0,'retain_export':False,
        'actual_model_sample_count':8,'actual_model_input_tokens_per_pass':count,'actual_model_passes':3,
        'tiny_gradient_rows':2,'tiny_gradient_input_tokens':44,'tiny_gradient_backwards':2,
        'data_digest':digest_value(rows),'source_prefix_sha256':sha(prefix/'samples.json'),
        'model_material_digest':material['material_digest'],'material_manifest_sha256':sha(DEFAULT/'conversion.json'),
        'model_repo':material['repo'],'model_revision':material['revision'],
        'model_dataset_version':1,'datasets':{'base':'danielwuu/irisx-nvarc-original-qwen3-001',
            'wheels':'danielwuu/irisx-arc-agi-2-trial-002-smoke-001'},
        'competition_sources':['arc-prize-2026-arc-agi-2'],'competition_files_opened':0,
        'hardware_gate':'four distinct BF16 L4s; single rank-zero model worker',
        'original_sft_checkpoint':False,'historical_base_commit_known':False,'full_sft_completed':False,
        'original_nemo_version':None,'original_unsloth_version':None,
        'material_policy':'original-reproduction; retain all source parent/exposure tags; no evaluator answers',
        'execution_control':'private Internet-disabled SAVE_AND_RUN_ALL; finite status checks; one terminal retrieval'}
    (output/'wheel').mkdir(parents=True)
    wheel=output/'wheel'/build.build_wheel(str(output/'wheel'))
    payload={'plan':canonical_bytes(plan,newline=True),'samples':canonical_bytes(rows,newline=True),
        'runtime_wheel':wheel.read_bytes(),'wheel_manifest':(ROOT/'trials/arc-agi-2-qwen35-nvarc/configs/base-wheel-manifest.json').read_bytes()}
    hashes={key:hashlib.sha256(value).hexdigest() for key,value in payload.items()}
    source=(ROOT/'tools/nvarc_qwen3_probe_notebook.py.tmpl').read_text(encoding='utf-8')
    for key,value in {'__RUN__':json.dumps(run),'__PAYLOADS__':json.dumps({k:base64.b64encode(zlib.compress(v,9)).decode() for k,v in payload.items()}),
        '__HASHES__':json.dumps(hashes),'__HARDWARE_HELPER__':(ROOT/'src/irisx/arc_nvarc_hardware.py').read_text(encoding='utf-8')}.items():
        source=source.replace(key,value)
    compile(source,'original-qwen3-probe','exec')
    (output/'kernel').mkdir()
    atomic(output/'plan.json',plan);(output/'samples.json').write_bytes(payload['samples'])
    atomic(output/'kernel/notebook.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},
        'cells':[{'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':source.splitlines(keepends=True)}]})
    atomic(output/'kernel/kernel-metadata.json',{'id':'danielwuu/'+run,'title':run,'code_file':'notebook.ipynb','language':'python',
        'kernel_type':'notebook','is_private':True,'enable_gpu':True,'enable_internet':False,
        'dataset_sources':list(plan['datasets'].values()),'competition_sources':plan['competition_sources'],'kernel_sources':[]})
    entries={p.relative_to(output).as_posix():sha(p) for p in output.rglob('*') if p.is_file()}
    atomic(output/'stage-summary.json',{'run_id':run,'plan_digest':digest_value(plan),'payload_sha256':hashes,'inventory':entries})
    return preflight(output)


def preflight(package):
    summary=json.loads((package/'stage-summary.json').read_bytes())
    actual={p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file() and p.name!='stage-summary.json'}
    if actual!=summary['inventory']:raise ValidationError('closed package bytes differ')
    plan=json.loads((package/'plan.json').read_bytes());rows=json.loads((package/'samples.json').read_bytes())
    if (plan['owner_decision']!='Decision 0054' or plan['format']!='irisx/nvarc-original-qwen3-probe-v1' or
            not re.fullmatch(r'nvarc-original-qwen3-probe-\d{3}',plan['run_id']) or
            plan['maximum_notebook_wall_seconds']!=1800 or plan['maximum_worker_wall_seconds']!=1200 or
            plan['maximum_generations']!=0 or plan['maximum_teacher_calls']!=0 or plan['maximum_optimizer_steps']!=0 or
            plan['maximum_paid_usd']!=0 or plan['retain_export'] is not False or
            len(rows)!=8 or digest_value(rows)!=plan['data_digest'] or plan['maximum_outer_forwards']!=13 or
            plan['maximum_input_tokens']!=sum(len(row['input_ids']) for row in rows)*3+44 or
            digest_value(plan)!=summary['plan_digest']):raise ValidationError('bounded owner probe plan differs')
    pack_sequences(rows)
    notebook=json.loads((package/'kernel/notebook.ipynb').read_bytes())
    source=''.join(notebook['cells'][0]['source']);tree=ast.parse(source)
    values={node.targets[0].id:ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
        and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'RUN','PAYLOADS','HASHES'}}
    if values['RUN']!=plan['run_id'] or values['HASHES']!=summary['payload_sha256']:raise ValidationError('notebook payload binding differs')
    for key,encoded in values['PAYLOADS'].items():
        raw=zlib.decompress(base64.b64decode(encoded,validate=True))
        if hashlib.sha256(raw).hexdigest()!=values['HASHES'][key]:raise ValidationError('embedded payload bytes differ')
        if key=='plan' and json.loads(raw)!=plan:raise ValidationError('embedded plan differs')
        if key=='samples' and json.loads(raw)!=rows:raise ValidationError('embedded samples differ')
    meta=json.loads((package/'kernel/kernel-metadata.json').read_bytes())
    if meta['id']!=plan['kernel_id'] or not meta['is_private'] or meta['enable_internet'] or meta['kernel_sources'] or meta['dataset_sources']!=list(plan['datasets'].values()):
        raise ValidationError('private offline exact material transport differs')
    return {'offline_package_verified':True,'external_calls':0,'run_id':plan['run_id'],'plan_digest':digest_value(plan),
        'maximum_input_tokens':plan['maximum_input_tokens'],'maximum_outer_forwards':13}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--run-id')
    args=parser.parse_args();print(json.dumps(stage(args.package,args.run_id) if args.action=='stage' else preflight(args.package)))
