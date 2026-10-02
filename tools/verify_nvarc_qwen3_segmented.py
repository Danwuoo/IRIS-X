"""Independently recount every full logit, tiny gradient and segmented GEMM."""
from __future__ import annotations
import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_qwen3_segmented_probe import FORMAT,schedule
from irisx.arc_nvarc_qwen3_packing_diagnostic import ordered_rows,TINY
from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.stage_nvarc_qwen3_probe import preflight
from tools.verify_nvarc_qwen3_probe import check_architecture
from tools.verify_nvarc_qwen3_packing_diagnostic import measurements,f32


def require(value,message):
    if not value:raise ValidationError(message)


def linear_names(layers):
    names=[]
    for i in range(layers):
        names.extend(f'model.layers.{i}.self_attn.{name}' for name in ('q_proj','k_proj','v_proj','o_proj'))
        names.extend(f'model.layers.{i}.mlp.{name}' for name in ('gate_proj','up_proj','down_proj'))
    return names+['lm_head']


def tiny_shapes():
    result={'model.embed_tokens.weight':[16,64],'model.norm.weight':[64]}
    for i in range(2):
        prefix=f'model.layers.{i}.'
        for name in ('input_layernorm','post_attention_layernorm'):result[prefix+name+'.weight']=[64]
        for name,shape in {'q_proj':[64,64],'k_proj':[32,64],'v_proj':[32,64],'o_proj':[64,64],
            'q_norm':[16],'k_norm':[16]}.items():result[prefix+'self_attn.'+name+'.weight']=shape
        for name,shape in {'gate_proj':[128,64],'up_proj':[128,64],'down_proj':[64,128]}.items():
            result[prefix+'mlp.'+name+'.weight']=shape
    return result


def within(left,right,atol,rtol):
    return all(f32(abs(a-b))<=f32(f32(atol)+f32(f32(rtol)*abs(a))) for a,b in zip(left,right))


def verify(path,package):
    checked=preflight(package);plan=json.loads((package/'plan.json').read_bytes())
    rows=json.loads((package/'samples.json').read_bytes());expected=schedule(rows);content={}
    require(plan['format']==FORMAT,'exact segmented-linear format required')
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist();index=json.loads(archive.read('manifest.json'));entries=index['members']
        require(len(names)<=96 and len(names)==len(set(names)) and len(entries)==len({r['path'] for r in entries}) and
            set(names)=={r['path'] for r in entries}|{'manifest.json'} and index['run_id']==plan['run_id'] and
            index['plan_digest']==checked['plan_digest'] and sum(r['bytes'] for r in entries)<=64*1024**2,
            'closed exact bounded segmented archive required')
        for row in entries:
            name=row['path'];require(not name.startswith('/') and '\\' not in name and ':' not in name and
                not any(part in {'','.','..'} for part in name.split('/')) and type(row['bytes']) is int and
                0<=row['bytes']<=16*1024**2 and archive.getinfo(name).file_size==row['bytes'],'bounded member path/size required')
            body=archive.read(name);require(hashlib.sha256(body).hexdigest()==row['sha256'],'exact member bytes required');content[name]=body
    def read(name):return json.loads(content[name])
    require(read('plan.json')==plan and read('payload-bindings.json')==
        json.loads((package/'stage-summary.json').read_bytes())['payload_sha256'],'exact returned plan/payload required')
    terminal=read('terminal.json');require(terminal['run_id']==plan['run_id'] and terminal['outcome'] in {'complete','failed'} and
        terminal['contains_evaluator_truth'] is False and type(terminal['wall_seconds']) in {int,float} and
        math.isfinite(terminal['wall_seconds']) and 0<=terminal['wall_seconds']<=1200,'finite truth-free terminal required')
    events=read('worker/worker-ledger.json') if 'worker/worker-ledger.json' in content else []
    calls=tokens=completed=0;require(isinstance(events,list) and len(events)<=13,'closed actual forward prefix required')
    for i,(event,wanted) in enumerate(zip(events,expected)):
        calls+=1;tokens+=wanted['input_tokens']
        require(set(event)==set(wanted)|{'completed','cumulative_forwards','cumulative_input_tokens'} and
            all(event[k]==v for k,v in wanted.items()) and type(event['completed']) is bool and
            (event['completed'] or i==len(events)-1) and type(event['cumulative_forwards']) is int and
            type(event['cumulative_input_tokens']) is int and event['cumulative_forwards']==calls and
            event['cumulative_input_tokens']==tokens,'exact actual forward input/order/completion required')
        completed+=event['completed']
    backwards=read('worker/backward-ledger.json') if 'worker/backward-ledger.json' in content else []
    require(isinstance(backwards,list) and len(backwards)<=2,'at most two tiny backwards required')
    for i,event in enumerate(backwards):require(set(event)=={'stage','completed'} and
        event['stage']==('tiny-independent','tiny-packed')[i] and type(event['completed']) is bool and
        (event['completed'] or i==len(backwards)-1),'exact tiny backward completion prefix required')
    result={'format':FORMAT+'-verification','run_id':plan['run_id'],'outcome':terminal['outcome'],
        'plan_digest':checked['plan_digest'],'archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'reserved_outer_forwards':calls,'completed_outer_forwards':completed,'reserved_input_tokens':tokens,
        'reserved_tiny_backwards':len(backwards),'completed_tiny_backwards':sum(row['completed'] for row in backwards),
        'native_varlen_gpu_differential_observed':False,'whole_model_fixed_numerical_gate_passed':False,
        'full_sft_completed':False,'historical_nemo_unsloth_parity':False,'correctness_scored':False,'external_calls':0}
    if terminal['outcome']=='failed':result.update(failure_phase=terminal['phase'],error_type=terminal['error_type']);return result
    gpu=read('hardware.json');inventory=gpu['inventory'];worker=read('worker/worker-result.json')
    require(len(inventory)==len({r['uuid'] for r in inventory})==4 and all(r['name']=='NVIDIA L4' and r['bf16'] is True for r in inventory) and
        gpu['torch']=='2.10.0+cu128' and read('material-verification.json')=={'all_files_verified':True,'material_digest':plan['model_material_digest']} and
        calls==completed==13 and tokens==plan['maximum_input_tokens'] and len(backwards)==2 and all(row['completed'] for row in backwards),
        'exact complete calls/hardware/material required')
    check_architecture(read('worker/loaded-config.json'))
    layout,ordered=ordered_rows(rows);offsets=[0]
    for row in ordered:offsets.append(offsets[-1]+len(row['input_ids']))
    _,tiny_ordered=ordered_rows(TINY);tiny_offsets=[0]
    for row in tiny_ordered:tiny_offsets.append(tiny_offsets[-1]+len(row['input_ids']))
    gemms=0
    for name,layers,bounds in [('tiny-linear-policy.json',2,tiny_offsets),('full-linear-policy.json',36,offsets),
        ('isolation-linear-policy.json',36,offsets)]:
        policy=read('worker/'+name);wanted=linear_names(layers)
        require(all(type(value) is int for value in policy['linear_calls_by_name'].values()) and
            type(policy['maximum_invocations_per_module']) is int and type(policy['segment_gemm_calls']) is int and
            type(policy['weight_or_dtype_casts']) is int and all(type(value) is int for value in policy['offsets']) and
            policy=={'offsets':bounds,'module_names':wanted,'linear_calls_by_name':{n:1 for n in wanted},
            'segment_gemm_calls':len(wanted)*(len(bounds)-1),'weight_or_dtype_casts':0,'weights_modified':False,
            'maximum_invocations_per_module':1,'weight_dtypes':{n:'torch.bfloat16' for n in wanted}},'exact unchanged BF16 per-sample GEMM accounting required')
        gemms+=policy['segment_gemm_calls']
    require(gemms==plan['maximum_segment_gemm_calls']==4078,'exact internal segmented GEMM total required')
    shapes=tiny_shapes();gradients=read('worker/tiny-gradient-differential.json');metadata=read('worker/vectors.json');decoded={}
    require(gradients['atol']==0.006 and gradients['rtol']==0.06 and gradients['original_scale'] is False and len(gradients['gradients'])==24 and
        {r['name']:r['shape'] for r in gradients['gradients']}==shapes,'all exact tiny gradient shapes required')
    expected_shapes={name:[1,offsets[-1],16] for name in ('independent-logits','packed-logits','isolation-logits')}
    expected_shapes.update({name:[38,8,3,2560] for name in ('independent-states','packed-states')})
    expected_shapes.update({name:[1,22,16] for name in ('tiny-reference-logits','tiny-packed-logits')})
    for row in gradients['gradients']:
        expected_shapes[row['reference_vector']]=row['shape'];expected_shapes[row['packed_vector']]=row['shape']
    require(len(expected_shapes)==55 and set(metadata)==set(expected_shapes) and
        {name for name in content if name.endswith('.f32le')}=={'worker/'+name+'.f32le' for name in expected_shapes},'closed complete numerical vector inventory required')
    for name,shape in expected_shapes.items():
        require(all(type(value) is int for value in metadata[name]['shape']) and
            metadata[name]=={'path':name+'.f32le','shape':shape,'dtype':'float32-le'},'exact fixed vector shape required')
        body=content['worker/'+name+'.f32le'];require(len(body)==math.prod(shape)*4,'exact vector length required')
        values=array('f');values.frombytes(body)
        if sys.byteorder!='little':values.byteswap()
        require(all(math.isfinite(value) for value in values),'finite actual vectors required');decoded[name]=values
    gradient_pass=True
    for row in gradients['gradients']:
        passed=within(decoded[row['reference_vector']],decoded[row['packed_vector']],0.006,0.06)
        require(type(row['within_fixed_tolerance']) is bool and row['within_fixed_tolerance']==passed,'recomputed tiny gradient tolerance differs')
        gradient_pass=gradient_pass and passed
    tiny_pass=within(decoded['tiny-reference-logits'],decoded['tiny-packed-logits'],0.006,0.06)
    stats=measurements(decoded['independent-logits'],decoded['packed-logits'],offsets)
    numeric=not any(row['outside_tolerance'] for row in stats);tail=offsets[1]*16
    isolated=decoded['packed-logits'][tail:]==decoded['isolation-logits'][tail:]
    qualified=gradient_pass and tiny_pass and numeric and isolated
    require(gradients['all_gradients_passed'] is gradient_pass and gradients['all_logits_passed'] is tiny_pass and
        worker['outcome']=='complete' and worker['format']==FORMAT and worker['run_id']==plan['run_id'] and
        worker['plan_digest']==checked['plan_digest'] and all(type(worker[k]) is int for k in
            ('actual_outer_forwards','actual_input_tokens','actual_backwards','decoder_layers_executed')) and worker['actual_outer_forwards']==calls and
        worker['actual_input_tokens']==tokens and worker['actual_backwards']==2 and worker['decoder_layers_executed']==36 and
        worker['weights_modified'] is False and worker['stored_and_compute_dtype']=='bfloat16' and
        all(type(worker[k]) is int and worker[k]==0 for k in ('optimizer_steps','generation_calls','teacher_calls')) and
        worker['tiny_gradients_passed'] is gradient_pass and worker['tiny_logits_passed'] is tiny_pass and
        worker['whole_model_fixed_numerical_gate_passed'] is numeric and worker['later_samples_bitwise_isolated'] is isolated and
        worker['native_varlen_gpu_differential_observed'] is qualified and worker['full_sft_completed'] is False and
        worker['historical_nemo_unsloth_parity'] is False and
        worker['correctness_scored'] is False and worker['contains_evaluator_truth'] is False,
        'independent actual counters/numerical/qualification envelope differs')
    require(all(terminal[k]==v for k,v in worker.items()),'parent and actual worker envelope differ')
    policy=read('worker/sampled-states-policy.json');require(policy=={'layers':['embed_tokens']+[f'layer-{i}' for i in range(36)]+['norm'],
        'local_positions':[[0,len(r['input_ids'])//2,len(r['input_ids'])-1] for r in ordered],'offsets':offsets,
        'shape':[38,8,3,2560],'no_additional_forward':True},'all original sampled states required')
    stride=8*3*2560;a=decoded['independent-states'];b=decoded['packed-states']
    state_errors=[max(abs(x-y) for x,y in zip(a[i*stride:(i+1)*stride],b[i*stride:(i+1)*stride])) for i in range(38)]
    result.update(native_varlen_gpu_differential_observed=qualified,whole_model_fixed_numerical_gate_passed=numeric,
        model_material_digest=plan['model_material_digest'],stored_and_compute_dtype='bfloat16',segmented_linear_observed=True,
        internal_segment_gemm_calls=gemms,independently_recomputed_logit_comparisons=stats,
        independently_recomputed_sampled_state_max_errors=state_errors,tiny_gradients_passed=gradient_pass,
        tiny_logits_passed=tiny_pass,later_samples_bitwise_isolated=isolated,observed_gpu_count=4,distinct_gpu_uuids=4)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('archive','package','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();require(not args.output.exists(),'new immutable independent segmented proof required')
    result=verify(args.archive,args.package);atomic(args.output,result);print(json.dumps(result))
