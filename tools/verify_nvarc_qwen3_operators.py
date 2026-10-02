"""Independently recount partial-layer calls and every operator vector."""
from __future__ import annotations
import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_qwen3_operator_probe import FORMAT,MODES,OPERATORS,schedule,parameter_layout
from irisx.arc_nvarc_qwen3_packing_diagnostic import ordered_rows
from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.stage_nvarc_qwen3_probe import preflight
from tools.verify_nvarc_qwen3_packing_diagnostic import f32

WIDTHS={'embedding':2560,'input-norm':2560,'q-projection':4096,'k-projection':1024,
    'v-projection':1024,'q-norm':4096,'k-norm':1024,'attention-before-o-projection':4096,
    'o-projection':2560,'post-attention-norm':2560,'gate-projection':9728,'up-projection':9728,
    'product-before-down-projection':9728,'down-projection':2560,'layer-0-output':2560,'final-norm':2560}


def require(value,message):
    if not value:raise ValidationError(message)


def verify(path,package):
    checked=preflight(package);plan=json.loads((package/'plan.json').read_bytes())
    rows=json.loads((package/'samples.json').read_bytes());expected=schedule(rows)
    require(plan['format']==FORMAT and plan['retained_decoder_layers']==[0] and
        plan['whole_model_numerical_qualification'] is False,'partial-layer diagnostic plan required')
    content={}
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist();index=json.loads(archive.read('manifest.json'));entries=index['members']
        require(len(names)<=160 and len(names)==len(set(names)) and len(entries)==len({r['path'] for r in entries}) and
            set(names)=={r['path'] for r in entries}|{'manifest.json'} and index['run_id']==plan['run_id'] and
            index['plan_digest']==checked['plan_digest'] and sum(r['bytes'] for r in entries)<=64*1024**2,
            'closed bounded exact first-layer archive required')
        for row in entries:
            name=row['path'];require(not name.startswith('/') and '\\' not in name and
                not any(part in {'','.','..'} for part in name.split('/')) and type(row['bytes']) is int and
                0<=row['bytes']<=32*1024**2 and archive.getinfo(name).file_size==row['bytes'],
                'bounded operator member path/size required')
            body=archive.read(name);require(hashlib.sha256(body).hexdigest()==row['sha256'],'operator member bytes differ')
            content[name]=body
    def read(name):return json.loads(content[name])
    require(read('plan.json')==plan and read('payload-bindings.json')==
        json.loads((package/'stage-summary.json').read_bytes())['payload_sha256'],'exact returned operator plan/payload differs')
    terminal=read('terminal.json');require(terminal['run_id']==plan['run_id'] and
        terminal['outcome'] in {'complete','failed'} and terminal['contains_evaluator_truth'] is False and
        type(terminal['wall_seconds']) in (int,float) and math.isfinite(terminal['wall_seconds']) and
        0<=terminal['wall_seconds']<=plan['maximum_notebook_wall_seconds'],'finite truth-free first-layer terminal required')
    ledger=read('worker/worker-ledger.json') if 'worker/worker-ledger.json' in content else []
    calls=tokens=completed=0
    require(isinstance(ledger,list) and len(ledger)<=len(expected),'bounded operator forward prefix required')
    for index,(event,wanted) in enumerate(zip(ledger,expected)):
        calls+=1;tokens+=wanted['input_tokens']
        require(set(event)==set(wanted)|{'completed','cumulative_forwards','cumulative_input_tokens'} and
            all(event[k]==v for k,v in wanted.items()) and type(event['completed']) is bool and
            (event['completed'] or index==len(ledger)-1) and type(event['input_tokens']) is int and
            type(event['cumulative_forwards']) is int and event['cumulative_forwards']==calls and
            type(event['cumulative_input_tokens']) is int and event['cumulative_input_tokens']==tokens,
            'exact operator actual input/order/completion prefix differs')
        completed+=event['completed']
    result={'format':FORMAT+'-verification','run_id':plan['run_id'],'outcome':terminal['outcome'],
        'archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'plan_digest':checked['plan_digest'],
        'reserved_outer_forwards':calls,'completed_outer_forwards':completed,'reserved_input_tokens':tokens,
        'partial_model_scope':True,'maximum_decoder_layers_per_forward':1,'whole_model_numerical_gate_passed':False,
        'full_sft_completed':False,'correctness_scored':False,'external_calls':0}
    if terminal['outcome']=='failed':result.update(failure_phase=terminal['phase'],error_type=terminal['error_type'])
    if terminal['outcome']=='complete':
        hardware=read('hardware.json');gpu=hardware['inventory'];worker=read('worker/worker-result.json')
        require(len(gpu)==len({r['uuid'] for r in gpu})==4 and all(r['name']=='NVIDIA L4' and r['bf16'] is True for r in gpu) and
            hardware['torch']=='2.10.0+cu128' and read('material-verification.json')['all_files_verified'] is True and
            read('material-verification.json')['material_digest']==plan['model_material_digest'] and
            calls==completed==len(expected)==21 and tokens==plan['maximum_input_tokens'] and
            type(worker['actual_outer_forwards']) is int and worker['actual_outer_forwards']==calls and
            type(worker['actual_input_tokens']) is int and worker['actual_input_tokens']==tokens and
            worker['format']==FORMAT and worker['run_id']==plan['run_id'] and worker['plan_digest']==checked['plan_digest'] and
            worker['outcome']=='complete' and worker['contains_evaluator_truth'] is False and
            worker['full_sft_completed'] is False and worker['correctness_scored'] is False and
            worker['partial_model'] is True and type(worker['decoder_layers_executed']) is int and worker['decoder_layers_executed']==1 and
            worker['whole_model_numerical_gate_passed'] is False and all(type(worker[k]) is int and worker[k]==0 for k in
                ('optimizer_steps','backwards','generation_calls','teacher_calls')),
            'complete partial-model cost/hardware/material differs')
        subset=read('worker/retained-model-subset.json')
        config=read('worker/original-loaded-config.json')
        require(all(config.get(name)==value for name,value in {'num_hidden_layers':36,'vocab_size':16,
            'hidden_size':2560,'head_dim':128,'num_attention_heads':32,'num_key_value_heads':8,
            'intermediate_size':9728}.items()),'exact original decoder architecture required')
        require(subset['original_decoder_layers']==36 and subset['retained_decoder_layers']==[0] and
            subset['whole_model'] is False and subset['weights_modified'] is False and
            config['num_hidden_layers']==36 and config['tie_word_embeddings'] is True and
            len(subset['parameters'])==len(parameter_layout(config)) and
            {row['name']:row['shape'] for row in subset['parameters']}==parameter_layout(config) and
            all(row['dtype']=='torch.bfloat16' for row in subset['parameters']),
            'only the original first decoder layer may execute')
        _,ordered=ordered_rows(rows);offsets=[0]
        for row in ordered:offsets.append(offsets[-1]+len(row['input_ids']))
        require(read('worker/capture-policy.json')=={'operators':list(OPERATORS),
            'local_positions':[[0,len(row['input_ids'])//2,len(row['input_ids'])-1] for row in ordered],
            'offsets':offsets,'whole_model_qualification':False,'additional_forwards_from_hooks':0},
            'fixed first-layer capture policy differs')
        settings=read('worker/compute-settings.json');require(set(settings)==set(MODES),'all fixed compute modes required')
        for mode,setting in settings.items():
            fp32='fp32-linear' in mode
            require(type(setting['bf16_reduced_precision_reduction']) is bool and
                setting['bf16_reduced_precision_reduction']==(not ('no-reduced' in mode or fp32)) and
                setting['linear_compute']==('float32 with output cast to input dtype' if fp32 else 'stored bfloat16') and
                setting['rewritten_linear_modules']==(8 if fp32 else 0) and
                (not fp32 or setting['float32_matmul_precision']=='highest') and
                setting['attention']==('sdpa' if mode.startswith('independent') else
                    'irisx_qwen3_torch_varlen_native_gqa' if 'native-gqa' in mode else 'irisx_qwen3_torch_varlen'),
                'actual fixed precision/head-layout setting differs')
        metadata=read('worker/vectors.json');decoded={}
        wanted={mode+'-'+name for mode in MODES for name in (*OPERATORS,'logits')}
        require(set(metadata)==wanted and {n for n in content if n.endswith('.f32le')}==
            {'worker/'+name+'.f32le' for name in wanted},'closed complete first-layer vectors required')
        for mode in MODES:
            for operator in (*OPERATORS,'logits'):
                name=mode+'-'+operator;shape=[1,offsets[-1],16] if operator=='logits' else [8,3,WIDTHS[operator]]
                require(metadata[name]=={'path':name+'.f32le','shape':shape,'dtype':'float32-le'},'fixed operator vector shape differs')
                body=content['worker/'+name+'.f32le'];require(len(body)==math.prod(shape)*4,'operator vector count differs')
                values=array('f');values.frombytes(body)
                if sys.byteorder!='little':values.byteswap()
                require(all(math.isfinite(x) for x in values),'finite operator vector required');decoded[name]=values
        comparisons={};first={}
        for mode in MODES[2:]:
            reference='independent-fp32-linear' if 'fp32-linear' in mode else 'independent-flash-sdpa'
            comparisons[mode]={}
            for operator in (*OPERATORS,'logits'):
                lhs,rhs=decoded[reference+'-'+operator],decoded[mode+'-'+operator]
                comparisons[mode][operator]={'max_absolute_error':max(f32(abs(a-b)) for a,b in zip(lhs,rhs)),
                    'bitwise_equal':lhs==rhs}
            first[mode]=next((name for name in OPERATORS if not comparisons[mode][name]['bitwise_equal']),None)
        require(comparisons==read('worker/operator-comparisons.json'),'reported first-layer differences contradict retained vectors')
        result.update(independently_recomputed_operator_comparisons=comparisons,first_nonbitwise_operator=first,
            partial_model_observed=True,decoder_layers_executed=1,
            observed_gpu_count=4,distinct_gpu_uuids=4,backwards=0,optimizer_steps=0,generation_calls=0,teacher_calls=0)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('archive','package','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();require(not args.output.exists(),'new immutable operator verification required')
    result=verify(args.archive,args.package);atomic(args.output,result);print(json.dumps(result))
