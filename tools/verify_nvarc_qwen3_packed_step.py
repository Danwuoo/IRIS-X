"""Independent closed result/input/cost reader for the one-step CUDA probe."""
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
from irisx.arc_nvarc_combined import atomic,sha
from irisx.arc_nvarc_qwen3_packed_step import check_plan
from irisx.canonical import digest_value,canonical_bytes
from irisx.errors import ValidationError


def verify(archive,package):
    plan=json.loads((package/'plan.json').read_bytes());rows=json.loads((package/'samples.json').read_bytes())
    expected=check_plan(plan,rows);summary=json.loads((package/'stage-summary.json').read_bytes())
    data={}
    with zipfile.ZipFile(archive) as stream:
        manifest=json.loads(stream.read('manifest.json'));names=[r['path'] for r in manifest['members']]
        if (manifest['run_id']!=plan['run_id'] or manifest['plan_digest']!=digest_value(plan) or
                len(names)!=len(set(names)) or len(stream.namelist())!=len(names)+1 or
                set(stream.namelist())!=set(names)|{'manifest.json'} or
                sum(r['bytes'] for r in manifest['members'])>64*1024**2):
            raise ValidationError('closed bounded one-step result identity differs')
        for member in manifest['members']:
            raw=stream.read(member['path'])
            if len(raw)!=member['bytes'] or hashlib.sha256(raw).hexdigest()!=member['sha256']:
                raise ValidationError('one-step result member bytes differ')
            data[member['path']]=raw
    def read(name):return json.loads(data[name])
    if read('plan.json')!=plan or read('payload-bindings.json')!=summary['payload_sha256']:
        raise ValidationError('returned exact one-step input/payload differs')
    terminal=read('terminal.json')
    if terminal['run_id']!=plan['run_id'] or terminal.get('contains_evaluator_truth') is not False:
        raise ValidationError('truth-free one-step terminal required')
    reserved=[]
    for rank in range(4):
        path=f'worker/rank-{rank}-reservation.json'
        if path not in data:continue
        row=read(path);r=expected['ranks'][rank]
        want={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'optimizer_steps_reserved':1,
            'outer_forwards_reserved':expected['collective_slots_per_rank'],'input_tokens_reserved':r['input_tokens'],
            'dummy_input_tokens_reserved':2*(expected['collective_slots_per_rank']-len(r['physical_digests'])),
            'generation_calls':0,'teacher_calls':0,'maximum_paid_usd':0}
        if canonical_bytes(row)!=canonical_bytes(want):raise ValidationError('one-step rank cost reservation differs')
        reserved.append(rank)
    proof={'run_id':plan['run_id'],'outcome':terminal['outcome'],'archive_sha256':sha(archive),
        'plan_digest':digest_value(plan),'closed_members':len(data),'reserved_training_ranks':reserved,
        'generations':0,'teacher_calls':0,'full_sft_completed':False,'checkpoint_exported':False,
        'historical_nemo_unsloth_parity':False,'correctness_scored':False,'maximum_paid_usd':0,
        'numeric_scope':'worker-observed CUDA/FSDP step; local reader reconstructs closed bytes, identities, layout and every reserved cost'}
    if terminal['outcome']=='complete':
        inventory=read('hardware.json')
        hardware=inventory['inventory']
        if (inventory['torch']!='2.10.0+cu128' or len(hardware)!=4 or
                len({r['uuid'] for r in hardware})!=4 or any(r['name']!='NVIDIA L4' or not r['bf16'] for r in hardware) or
                reserved!=list(range(4)) or read('material-verification.json')!={'all_files_verified':True,'material_digest':plan['model_material_digest']}):
            raise ValidationError('exact complete four-L4 material/reservation gate required')
        worker=read('worker/worker-result.json')
        if any(terminal.get(k)!=v for k,v in worker.items()):raise ValidationError('parent/worker one-step result differs')
        if (worker['plan_digest']!=digest_value(plan) or worker['optimizer_steps']!=1 or
                worker['input_tokens']!=plan['scheduled_input_tokens'] or
                worker['supervised_tokens']!=plan['scheduled_supervised_tokens'] or
                worker['outer_forwards']!=plan['maximum_outer_forwards'] or worker['generation_calls']!=0 or
                worker['teacher_calls']!=0 or worker['model_material_digest']!=plan['model_material_digest'] or
                any(worker[k] is not False for k in ('checkpoint_exported','optimizer_checkpoint_exported',
                    'full_sft_completed','historical_nemo_unsloth_parity'))):
            raise ValidationError('bounded successful one-step result differs')
        for key in ('weight_fingerprint_before','weight_fingerprint_after'):
            if len(worker[key])!=2 or any(not math.isfinite(v) for v in worker[key]):
                raise ValidationError('finite global weight fingerprints required')
        if worker['weight_fingerprint_before']==worker['weight_fingerprint_after']:
            raise ValidationError('full-parameter global fingerprint is unchanged')
        observations=worker['rank_observations']
        if len(observations)!=4 or [r['rank'] for r in observations]!=list(range(4)):
            raise ValidationError('all four rank observations required')
        if len({r['hardware']['device_uuid'] for r in observations})!=4 or any(
                r['hardware']['device_uuid'] not in {h['uuid'] for h in hardware} for r in observations):
            raise ValidationError('four distinct actual worker UUIDs differ')
        for rank,r in enumerate(observations):
            p=expected['ranks'][rank]
            if (read(f'worker/rank-{rank}-step.json')!=r or r['checkpointed_layers']!=36 or
                    r['world_size']!=4 or r['global_sequence_count']!=256 or
                    r['packing_layout_digests']!=p['logical_digests'] or
                    r['physical_packing_layout_digests']!=p['physical_digests'] or
                    r['maximum_packed_input_tokens']!=32768 or
                    r['real_forward_calls']!=len(p['physical_digests']) or
                    r['dummy_forward_calls']!=expected['collective_slots_per_rank']-len(p['physical_digests']) or
                    r['collective_slots']!=expected['collective_slots_per_rank'] or
                    r['global_input_tokens']!=worker['input_tokens'] or
                    r['global_supervised_tokens']!=worker['supervised_tokens'] or
                    r['missing_owned_gradient_shards'] or r['owned_parameter_shards']!=r['accumulated_parameter_shards'] or
                    r['owned_parameter_shards']<1 or r['finite_nonzero_shards']<1 or
                    r['packing_execution']!='torch-varlen-flash' or r['fused_packing_verified'] is not True):
                raise ValidationError('full whole-sequence packing/gradient/collective coverage differs')
            for key in ('global_token_mean_loss','gradient_norm_before_clip','learning_rate','synchronized_step_wall_seconds'):
                if not math.isfinite(r[key]) or r[key]<=0:raise ValidationError('finite positive training observation required')
            for kind in ('parameter_bytes','gradient_bytes','optimizer_bytes'):
                residency=r['state_residency'][kind]
                if any(v>0 and k!='cpu/torch.float32' for k,v in residency.items()):
                    raise ValidationError('actual FP32 CPU state residency differs')
        elapsed=max(r['synchronized_step_wall_seconds'] for r in observations)
        if worker['step_wall_seconds']!=elapsed or worker['timing_repetitions']!=1:
            raise ValidationError('one cold synchronized timing observation required')
        proof.update(optimizer_steps=1,input_tokens=worker['input_tokens'],supervised_tokens=worker['supervised_tokens'],
            step_wall_seconds=elapsed,input_tokens_per_second=worker['input_tokens']/elapsed,
            physical_real_forwards=expected['real_outer_forwards'],dummy_forwards=expected['dummy_outer_forwards'],
            actual_original_family_full_gradient_step_observed=True)
    elif terminal['outcome']=='failed':
        proof.update(failure_phase=terminal['phase'],error_type=terminal['error_type'],error_message=terminal['error_message'])
    else:raise ValidationError('known one-step terminal outcome required')
    return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('archive','package','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();proof=verify(args.archive,args.package);atomic(args.output,proof);print(json.dumps(proof))
