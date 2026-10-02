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
from irisx.arc_nvarc_qwen3_packed_step import check_plan,SEGMENTED_FORMAT,call_schedule
from irisx.arc_nvarc_packing import pack_sequences
from irisx.arc_nvarc_qwen3_packing import execution_slices
from irisx.canonical import digest_value,canonical_bytes
from irisx.errors import ValidationError


def verify(archive,package):
    from tools.stage_nvarc_qwen3_packed_step import preflight
    preflight(package)
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
    if plan['format']==SEGMENTED_FORMAT:
        actual=[]
        for rank in range(4):
            name=f'worker/rank-{rank}-forward-ledger.json';events=read(name) if name in data else []
            wanted=call_schedule(rows,rank)
            if not isinstance(events,list) or len(events)>len(wanted):raise ValidationError('bounded actual rank forward prefix required')
            for i,event in enumerate(events):
                if (set(event)!=set(wanted[i])|{'completed'} or canonical_bytes({k:event[k] for k in wanted[i]})!=canonical_bytes(wanted[i]) or
                        type(event['completed']) is not bool or (event['completed'] is False and i!=len(events)-1)):
                    raise ValidationError('actual forward input/position/causal/completion prefix differs')
            if terminal['outcome']=='complete' and (len(events)!=len(wanted) or not all(e['completed'] for e in events)):
                raise ValidationError('every approved actual rank forward must complete')
            actual.append({'rank':rank,'reserved_outer_forwards':len(events),'completed_outer_forwards':sum(e['completed'] for e in events),
                'reserved_input_tokens':sum(e['input_tokens'] for e in events)})
        proof['actual_rank_forward_prefixes']=actual
    if terminal['outcome']=='complete':
        inventory=read('hardware.json')
        hardware=inventory['inventory']
        if (inventory['torch']!='2.10.0+cu128' or len(hardware)!=4 or
                len({r['uuid'] for r in hardware})!=4 or any(r['name']!='NVIDIA L4' or not r['bf16'] for r in hardware) or
                reserved!=list(range(4)) or read('material-verification.json')!={'all_files_verified':True,'material_digest':plan['model_material_digest']}):
            raise ValidationError('exact complete four-L4 material/reservation gate required')
        worker=read('worker/worker-result.json')
        if any(type(worker[k]) is not int for k in ('optimizer_steps','input_tokens','supervised_tokens',
                'outer_forwards','generation_calls','teacher_calls')):
            raise ValidationError('integer actual full-gradient work required')
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
            integer_fields=('rank','world_size','global_sequence_count','real_forward_calls','dummy_forward_calls',
                'collective_slots','global_input_tokens','global_supervised_tokens','owned_parameter_shards',
                'accumulated_parameter_shards','finite_nonzero_shards','cpu_accumulation_bytes','checkpointed_layers')
            if any(type(r[key]) is not int for key in integer_fields):
                raise ValidationError('integer actual rank work/shard counts required')
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
                if type(r[key]) not in {int,float} or not math.isfinite(r[key]) or r[key]<=0:raise ValidationError('finite positive training observation required')
            from irisx.arc_nvarc_source_recipe import source_sft_lr
            if r['learning_rate']!=source_sft_lr(plan['source_recipe'],0):
                raise ValidationError('exact first source optimizer learning rate required')
            for kind in ('parameter_bytes','gradient_bytes','optimizer_bytes'):
                residency=r['state_residency'][kind]
                if any(type(v) is not int or v<0 or (v>0 and k!='cpu/torch.float32') for k,v in residency.items()):
                    raise ValidationError('actual FP32 CPU state residency differs')
            if r['cpu_accumulation_bytes']!=r['state_residency']['gradient_bytes'].get('cpu/torch.float32',0) or r['cpu_accumulation_bytes']<1:
                raise ValidationError('all actual gradient bytes must cover the accumulated CPU shards')
            if plan['format']==SEGMENTED_FORMAT:
                logical=pack_sequences(rows[rank::4],capacity=256000,length_multiple=64)
                physical=[piece for pack in logical for piece in execution_slices(pack,32768)]
                dummy=pack_sequences([{'input_ids':[14,15],'labels':[-100,15]}],capacity=256000,length_multiple=64)[0]
                physical.extend([dummy]*(expected['collective_slots_per_rank']-len(physical)))
                policies=r.get('segmented_linear_policies',[])
                if r.get('packed_linear_policy')!=plan['packed_linear_policy'] or len(policies)!=len(physical):
                    raise ValidationError('all real and dummy segmented backward scopes required')
                from tools.verify_nvarc_qwen3_segmented import linear_names
                canonical_names=set(linear_names(36));gemms=0
                for policy,pack in zip(policies,physical):
                    offsets=[0]
                    for segment in pack['segments']:offsets.append(offsets[-1]+segment['valid_end']-segment['start'])
                    normalize=lambda name:name.replace('_fsdp_wrapped_module.','').replace('_checkpoint_wrapped_module.','')
                    names=policy['module_names'];counts=policy['linear_calls_by_name'];n=len(offsets)-1
                    if (policy['offsets']!=offsets or len(names)!=253 or len(set(names))!=253 or
                            {normalize(name) for name in names}!=canonical_names or set(counts)!=set(names) or
                            any(type(count) is not int or count not in (1,2) for count in counts.values()) or
                            type(policy['maximum_invocations_per_module']) is not int or policy['maximum_invocations_per_module']!=2 or type(policy['segment_gemm_calls']) is not int or
                            not 253*n<=policy['segment_gemm_calls']<=sum(counts.values())*n or
                            type(policy['weight_or_dtype_casts']) is not int or policy['weight_or_dtype_casts']!=0 or policy['weights_modified'] is not False or
                            set(policy['weight_dtypes'])!=set(names) or
                            any(dtype not in {'torch.float32','torch.bfloat16'} for dtype in policy['weight_dtypes'].values())):
                        raise ValidationError('exact per-sample unchanged linear/checkpoint accounting differs')
                    gemms+=policy['segment_gemm_calls']
                if type(r['segment_gemm_invocations_including_checkpoint']) is not int or r['segment_gemm_invocations_including_checkpoint']!=gemms:
                    raise ValidationError('segmented checkpoint GEMM total differs')
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
