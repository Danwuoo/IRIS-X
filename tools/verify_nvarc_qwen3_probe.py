"""Independent closed-archive, material, cost and numeric-report reconciliation.

CUDA differential tolerances are worker-internal observations. This reader
does not claim to reproduce CUDA kernels locally or score an ARC answer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.canonical import digest_value
from irisx.errors import ValidationError


def check_architecture(config):
    expected={'model_type':'qwen3','vocab_size':16,'num_hidden_layers':36,'hidden_size':2560,
        'num_attention_heads':32,'num_key_value_heads':8,'head_dim':128,'intermediate_size':9728,
        'tie_word_embeddings':True,'attention_dropout':0}
    parameters=config.get('rope_parameters')
    theta=[]
    if config.get('rope_theta') is not None:theta.append(config['rope_theta'])
    if parameters is not None:
        if not isinstance(parameters,dict) or parameters.get('rope_type')!='default':
            raise ValidationError('original unscaled rotary contract differs')
        theta.append(parameters.get('rope_theta'))
    if any(config.get(key)!=value for key,value in expected.items()) or not theta or any(x!=5000000 for x in theta):
        raise ValidationError('original compact architecture differs')


def verify(archive_path,package):
    plan=json.loads((package/'plan.json').read_bytes());rows=json.loads((package/'samples.json').read_bytes())
    summary=json.loads((package/'stage-summary.json').read_bytes())
    with zipfile.ZipFile(archive_path) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or 'manifest.json' not in names:
            raise ValidationError('closed archive member uniqueness differs')
        manifest=json.loads(archive.read('manifest.json'))
        entries={item['path']:item for item in manifest['members']}
        if (len(entries)!=len(manifest['members']) or set(names)!=set(entries)|{'manifest.json'} or
                manifest['run_id']!=plan['run_id'] or manifest['plan_digest']!=digest_value(plan)):
            raise ValidationError('closed archive plan identity differs')
        content={}
        for name,item in entries.items():
            if name.startswith('/') or '\\' in name or any(p in {'','.','..'} for p in name.split('/')):
                raise ValidationError('archive path differs')
            raw=archive.read(name)
            if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:
                raise ValidationError('diagnostic member bytes differ')
            content[name]=raw
    def read(name):return json.loads(content[name])
    if read('plan.json')!=plan or read('payload-bindings.json')!=summary['payload_sha256']:
        raise ValidationError('returned payload identity differs')
    terminal=read('terminal.json')
    if terminal['run_id']!=plan['run_id'] or terminal['contains_evaluator_truth'] is not False:
        raise ValidationError('terminal envelope differs')
    proof={'format':'irisx/nvarc-original-qwen3-probe-verification-v1','run_id':plan['run_id'],
        'plan_digest':digest_value(plan),'archive_sha256':hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        'verified_members':len(entries),'outcome':terminal['outcome'],'correctness_scored':False,
        'full_sft_completed':False,'historical_nemo_unsloth_parity':False,'external_calls':0}
    if 'hardware.json' in content:
        hardware=read('hardware.json');inventory=hardware['inventory']
        proof['observed_gpu_count']=len(inventory)
        proof['distinct_gpu_uuids']=len({item['uuid'] for item in inventory})
    ledger=read('worker/worker-ledger.json') if 'worker/worker-ledger.json' in content else []
    expected=[('tiny-independent-gradients',2,22),('tiny-packed-gradients',1,22),
        ('actual-weights-independent',8,plan['actual_model_input_tokens_per_pass']),
        ('actual-weights-packed',1,plan['actual_model_input_tokens_per_pass']),
        ('actual-weights-isolation',1,plan['actual_model_input_tokens_per_pass'])]
    if len(ledger)>len(expected):raise ValidationError('returned cost ledger has extra stages')
    calls=tokens=0
    for row,(stage,n,length) in zip(ledger,expected):
        calls+=n;tokens+=length
        if ((row['stage'],row['reserved_forwards'],row['reserved_input_tokens'])!=(stage,n,length) or
                row['cumulative_forwards']!=calls or row['cumulative_input_tokens']!=tokens or
                calls>plan['maximum_outer_forwards'] or tokens>plan['maximum_input_tokens']):
            raise ValidationError('reserved cost prefix differs')
    if ledger:
        if ledger[-1]['cumulative_forwards']>plan['maximum_outer_forwards'] or ledger[-1]['cumulative_input_tokens']>plan['maximum_input_tokens']:
            raise ValidationError('returned cost exceeds plan')
        proof['reserved_outer_forwards']=ledger[-1]['cumulative_forwards']
        proof['reserved_input_tokens']=ledger[-1]['cumulative_input_tokens']
    if terminal['outcome']=='complete':
        if (len(inventory)!=4 or len({item['uuid'] for item in inventory})!=4 or
                any(item['name']!='NVIDIA L4' or not item['bf16'] for item in inventory) or
                hardware['torch']!='2.10.0+cu128' or terminal['plan_digest']!=digest_value(plan) or
                terminal['model_material_digest']!=plan['model_material_digest'] or
                terminal['optimizer_steps']!=0 or terminal['generation_calls']!=0 or
                terminal['reserved_outer_forwards']!=13 or terminal['reserved_input_tokens']!=plan['maximum_input_tokens'] or
                read('material-verification.json')!={'all_files_verified':True,'material_digest':plan['model_material_digest']}):
            raise ValidationError('successful original probe envelope differs')
        if [(r['stage'],r['reserved_forwards'],r['reserved_input_tokens']) for r in ledger]!=expected:
            raise ValidationError('independent forward ledger reconstruction differs')
        calls=tokens=0
        for row in ledger:
            calls+=row['reserved_forwards'];tokens+=row['reserved_input_tokens']
            if row['cumulative_forwards']!=calls or row['cumulative_input_tokens']!=tokens:
                raise ValidationError('cost prefix differs')
        numerical=read('worker/actual-weight-differential.json')
        supervised=sum(sum(label>=0 for label in row['labels'][1:]) for row in rows)
        if numerical['input_tokens']!=sum(len(r['input_ids']) for r in rows) or numerical['supervised_tokens']!=supervised:
            raise ValidationError('whole original-prefix supervision differs')
        if len(numerical['max_absolute_logit_errors'])!=8 or any(not math.isfinite(x) or x<0 for x in numerical['max_absolute_logit_errors']):
            raise ValidationError('numeric observation differs')
        gradient=read('worker/tiny-gradient-differential.json')
        if (len(gradient['gradient_tensors'])!=24 or len({r['name'] for r in gradient['gradient_tensors']})!=24 or
                gradient['atol']!=0.006 or gradient['rtol']!=0.06 or
                any(not math.isfinite(r['max_absolute_error']) or r['max_absolute_error']<0 for r in gradient['gradient_tensors']) or
                numerical['atol']!=0.25 or numerical['rtol']!=0.03 or
                any(not math.isfinite(value) for value in (numerical['packed_token_mean_loss'],
                    gradient['packed_token_mean_loss'],gradient['independent_token_mean_loss']))):
            raise ValidationError('all tiny Qwen3 gradient observations required')
        config=read('worker/loaded-config.json')
        check_architecture(config)
        if any(terminal[key] is not True for key in ('tiny_gradient_differential',
                'actual_qwen3_weight_forward_differential','actual_qwen3_packed_isolation','native_varlen_flash_verified')):
            raise ValidationError('original compact architecture or successful differential observation differs')
        isolation=read('worker/isolation.json')
        if isolation['unchanged_later_samples_bitwise_equal'] is not True or isolation['original_prefix_digest']!=digest_value(rows):
            raise ValidationError('actual-weight isolation observation differs')
        proof.update(model_material_digest=plan['model_material_digest'],source_input_tokens=numerical['input_tokens'],
            source_supervised_tokens=supervised,native_varlen_gpu_differential_observed=True,
            numeric_verification_scope='worker-internal CUDA differential; local reader independently checks closed bytes, inputs/material identity and every reserved cost',
            max_absolute_logit_errors=numerical['max_absolute_logit_errors'],inference_timings=numerical['timings'])
    else:
        proof['failure_phase']=terminal['phase'];proof['error_type']=terminal['error_type']
        proof['error_message']=terminal['error_message']
    return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('archive','package','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();result=verify(args.archive,args.package);atomic(args.output,result);print(json.dumps(result))
