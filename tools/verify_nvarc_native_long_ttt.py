"""Independent closed bytes, source-view/actual cost and native reset reader."""
from argparse import ArgumentParser
from array import array
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.canonical import digest_value,canonical_bytes
from tools.stage_nvarc_native_long_ttt import preflight,raw_payloads,native_inventory,PREPARATION,PORTABLE_FORMAT,require
from tools.nvarc_native_ttt_schedule import SOURCES,FUNCTIONS,ulp_distance


def verify(archive,package):
    plan=json.loads((package/'plan.json').read_bytes())
    if plan.get('owner_editor_only') is True:
        from tools.stage_nvarc_native_editor import preflight as editor_preflight,raw_payloads as editor_payloads
        checked=editor_preflight(package);raw=editor_payloads(plan)
    else:
        checked=preflight(package);raw=raw_payloads(plan)
    data={}
    with zipfile.ZipFile(archive) as stream:
        require(len(stream.namelist())==len(set(stream.namelist())) and sum(row.file_size for row in stream.infolist())<=16*1024**2,
            'closed bounded native epoch archive required')
        manifest=json.loads(stream.read('manifest.json'));names=[row['path'] for row in manifest['members']]
        require(manifest['run_id']==plan['run_id'] and manifest['plan_digest']==checked['plan_digest'] and
            len(names)==len(set(names)) and set(stream.namelist())==set(names)|{'manifest.json'},'exact native result identity required')
        for row in manifest['members']:
            body=stream.read(row['path']);require(len(body)==row['bytes'] and hashlib.sha256(body).hexdigest()==row['sha256'],
                'native result member bytes differ');data[row['path']]=body
    def read(name):return json.loads(data[name])
    require(read('plan.json')==plan and read('payload-bindings.json')=={key:hashlib.sha256(value).hexdigest() for key,value in raw.items()},
        'returned exact native epoch inputs differ')
    terminal=read('terminal.json');require(terminal['run_id']==plan['run_id'] and terminal['outcome'] in {'complete','failed'} and
        terminal['contains_evaluator_truth'] is False and all(type(terminal[key]) is int and terminal[key]==0
            for key in ('generations','teacher_calls','paid_usd')) and
        type(terminal['wall_seconds']) in (int,float) and math.isfinite(terminal['wall_seconds']) and
        0<=terminal['wall_seconds']<=plan['maximum_notebook_wall_seconds'],
        'bounded truth-free native terminal required')
    state=read('native/training-ledger.json') if 'native/training-ledger.json' in data else {
        'forwards':[],'optimizer_steps':[],'training_steps':[],'optimizer_constructions':[],'generation_calls':0,'teacher_calls':0}
    rates=plan['source_learning_rates'];portable=plan.get('format')==PORTABLE_FORMAT
    if portable and 'native/native-schedule.json' in data:
        schedule=read('native/native-schedule.json');actual=schedule['rates']
        require(data['nvarc_native_ttt_schedule.py']==raw['schedule'] and len(actual)==129 and
            schedule['source_sha256']==SOURCES and schedule['function_sha256']==FUNCTIONS and
            type(schedule['warmup_steps']) is int and schedule['warmup_steps']==13 and
            type(schedule['epoch_steps']) is int and schedule['epoch_steps']==128 and
            all(type(schedule[key]) is int and schedule[key]==0 for key in ('model_calls','optimizer_steps')) and
            schedule['reference_rates_sha256']==hashlib.sha256(json.dumps(rates,separators=(',',':')).encode()).hexdigest(),
            'exact retained native scalar oracle required')
        distances=[ulp_distance(a,b) for a,b in zip(actual,rates)]
        require(max(distances)<=4 and schedule['reference_ulp_distances']==distances and
            schedule['maximum_reference_ulp_distance']==max(distances) and actual[0]==actual[-1]==0 and actual[13]==5e-5,
            'unchanged native scalar recipe within cross-platform ULP bound required')
        rates=actual
    elif portable:
        require(not state['forwards'] and not state['training_steps'] and not state['optimizer_steps'],
            'same-platform scalar oracle required before any training work')
    expected=json.loads(raw['expected_rows']);remaining=Counter((row['input_ids_digest'],row['labels_digest']) for row in expected)
    expected_counts={(row['input_ids_digest'],row['labels_digest']):(row['input_tokens'],row['supervised_tokens']) for row in expected}
    for key in ('forwards','training_steps','optimizer_steps'):
        events=state[key];require(isinstance(events,list) and len(events)<=128 and all(type(row['completed']) is bool for row in events) and
            all(row['completed'] for row in events[:-1]),'bounded native actual work prefix required')
    for row in state['forwards']:
        pair=(row['input_ids_digest'],row['labels_digest']);require(remaining[pair]>0,'unconsumed original source row required')
        remaining[pair]-=1
        require(type(row['input_tokens']) is int and type(row['supervised_tokens']) is int and
            (row['input_tokens'],row['supervised_tokens'])==expected_counts[pair],'actual complete source token/label counts differ')
        if row['completed']:require(type(row['loss']) in (int,float) and math.isfinite(row['loss']),'finite completed native loss required')
    for i,row in enumerate(state['optimizer_steps']):
        require(type(row['learning_rate']) is float and row['learning_rate']==rates[i] and
            type(row['gradient_tensors']) is int and row['gradient_tensors']==506 and
            type(row['gradient_norm_after_clip']) in (int,float) and math.isfinite(row['gradient_norm_after_clip']) and
            0<=row['gradient_norm_after_clip']<=1.05,'actual source learning-rate/gradient gate differs')
    require(len(state['optimizer_constructions'])<=1 and all(type(row['completed']) is bool for row in state['optimizer_constructions']) and
        all(type(state[key]) is int and state[key]==0 for key in ('generation_calls','teacher_calls')) and
        len(state['optimizer_steps'])<=len(state['training_steps'])<=len(state['forwards'])+1,
        'one native optimizer/ordered steps/no generation required')
    cost={'model_forwards':sum(row['completed'] for row in state['forwards']),
        'optimizer_steps':sum(row['completed'] for row in state['optimizer_steps']),
        'model_forwards_reserved':len(state['forwards']),'optimizer_steps_reserved':len(state['optimizer_steps']),
        'training_steps_reserved':len(state['training_steps'])}
    require(all(type(terminal[key]) is int and terminal[key]==value for key,value in cost.items()),'parent/actual work prefixes differ')
    proof={'run_id':plan['run_id'],'outcome':terminal['outcome'],'plan_digest':checked['plan_digest'],'archive_sha256':sha(archive),
        **cost,'closed_members':len(data),'generations':0,'teacher_calls':0,'paid_usd':0,'full_native_long_ttt_completed':False,
        'correctness_scored':False,'checkpoint_exported':False,'scope':'closed original-runtime epoch/material/actual work/reset evidence; no native clock, ARC score or full-method parity'}
    proof.update(completed_training_steps=sum(row['completed'] for row in state['training_steps']),
        completed_input_tokens=sum(row['input_tokens'] for row in state['forwards'] if row['completed']),
        completed_supervised_tokens=sum(row['supervised_tokens'] for row in state['forwards'] if row['completed']),
        native_preparation_verified=False)
    if terminal['outcome']=='failed':
        proof.update(failure_phase=terminal['phase'],error_type=terminal['error_type'],error_message=terminal['error_message'])
        if 'native/preparation.json' not in data:
            require(cost['model_forwards_reserved']==cost['optimizer_steps_reserved']==cost['training_steps_reserved']==0,
                'verified native preparation must precede any reserved training work')
            return proof
    for name,key in [('inspection.py','worker'),('inspection_helpers.py','helper'),('nvarc_native_ttt_budget.py','budget'),
        ('hardware_helpers.py','hardware'),('solver.py','solver'),('expected-rows.json','expected_rows')]:
        require(data[name]==raw[key],'exact retained trusted program/source data differs')
    hardware=read('hardware.json');gpus=hardware['inventory']
    require(hardware['torch']=='2.8.0+cu128' and hardware['cuda']=='12.8' and len(gpus)==len({row['uuid'] for row in gpus})==4 and
        all(row['name']=='NVIDIA L4' and row['bf16'] is True for row in gpus) and
        read('native/hardware.json')['device_uuid']==gpus[0]['uuid'] and
        read('source-verification.json')['inventory']==native_inventory() and
        read('model-verification.json')['model_material_digest']==plan['model_material_digest'] and
        read('model-verification.json')['all_ten_files_verified'] is True,'exact native model/source/four-L4 envelope differs')
    prep=read('native/preparation.json');prepared=read('native/prepared-rows.json');tokens=data['native/prepared-tokens.i16le'];offset=0
    require(prep['max_length']==prep['max_seq_length']==8192 and prep['trainer_origins']==plan['native_trainer_origins'] and
        prep['prepared_rows_digest']==digest_value(prepared) and prep['blocked_attempts']==0 and
        canonical_bytes(prep['checkpoint_flags'])==canonical_bytes(plan['native_checkpoint_flags']) and
        read('native/adapter-topology.json')==plan['native_adapter_topology'] and len(prepared)==128,
        'actual native Trainer/context/checkpoint/preparation differs')
    for row,wanted in zip(prepared,expected):
        n=wanted['input_tokens'];size=4*n
        require(row['retained_byte_offset']==offset and row['retained_token_bytes']==size and offset+size<=len(tokens),
            'complete bounded native token vectors required')
        values=array('h');values.frombytes(tokens[offset:offset+size]);offset+=size
        if sys.byteorder!='little':values.byteswap()
        ids,labels=list(values[:n]),list(values[n:])
        require(digest_value(ids)==wanted['input_ids_digest']==row['input_ids_digest'] and
            digest_value(labels)==wanted['labels_digest']==row['labels_digest'] and
            sum(value>=0 for value in labels[1:])==wanted['supervised_tokens'],'raw actual native source inputs/labels differ')
    require(offset==len(tokens),'no unlisted native token bytes allowed')
    proof.update(native_preparation_verified=True)
    if terminal['outcome']=='failed':return proof
    require(not +remaining and all(len(state[key])==128 and all(row['completed'] for row in state[key]) for key in
        ('forwards','optimizer_steps','training_steps')) and len(state['optimizer_constructions'])==1 and
        state['optimizer_constructions'][0]['completed'],'every native source row/backward/step must complete')
    if portable:
        last=state['last_learning_rate_check']
        require(last['index']==127 and last['expected']==rates[127] and last['actual_rates'] and
            all(value==rates[127] for value in last['actual_rates']),'exact same-platform optimizer oracle must complete')
    with zipfile.ZipFile(PREPARATION/'execution-final/retrieved/gpu-preflight-result.zip') as original:
        baseline=json.loads(original.read('native/baseline-inventory.json'))
    require(read('native/baseline-inventory.json')==read('native/reset-inventory.json')==baseline,
        'every exact original saved tensor must restore its observed seeded baseline')
    trained=read('native/trained-inventory.json');require(len(trained)==len(baseline) and trained!=baseline and
        all({key:row[key] for key in ('name','shape','dtype','elements','finite')}=={key:ref[key] for key in ('name','shape','dtype','elements','finite')}
            and row['finite'] is True and isinstance(row['sha256'],str) and re.fullmatch('[0-9a-f]{64}',row['sha256']) for row,ref in zip(trained,baseline)),
        'finite changed complete saved native topology required')
    moments=read('native/optimizer-state.json')
    require(len(moments)==506 and [row['elements'] for row in moments]==[row['elements'] for row in plan['native_adapter_topology']] and
        sum(row['elements'] for row in moments)==528564224 and all(
        type(row['elements']) is int and row['elements']>0 and type(row['moment_bytes']) is int and
        type(row['step']) is int and row['step']==128 and row['parameter_dtype']=='torch.bfloat16' and row['parameter_device']=='cuda:0' and
        row['moment_bytes']==row['elements']*4 and row['finite'] is True for row in moments),'every finite original BF16 Adam moment required')
    result=read('native/training-result.json')
    require(result['run_id']==plan['run_id'] and result['plan_digest']==checked['plan_digest'] and result['outcome']=='complete' and
        all(type(result[key]) is int and result[key]==value for key,value in {'model_forwards':128,'optimizer_steps':128,'input_tokens':955392,
            'supervised_tokens':476160,'trainer_global_step':128,'gradient_tensors_per_step':506,'generations':0,'teacher_calls':0,'paid_usd':0}.items()) and
        type(result['trainer_epoch']) in (int,float) and result['trainer_epoch']==1 and
        all(result[key] is True for key in ('full_native_long_ttt_completed','optimizer_discarded','all_saved_tensors_restored')) and
        all(result[key] is False for key in ('checkpoint_exported','correctness_scored','contains_evaluator_truth')),
        'complete bounded native epoch result required')
    require(all(type(result[key]) in (int,float) and math.isfinite(result[key]) for key in ('training_wall_seconds','worker_wall_seconds')) and
        0<result['training_wall_seconds']<=result['worker_wall_seconds']<=plan['maximum_child_wall_seconds'] and
        all(type(result[key]) is int and 0<result[key]<=gpus[0]['total_memory_bytes'] for key in
            ('cuda_peak_allocated_bytes','cuda_peak_reserved_bytes')) and
        result['cuda_peak_allocated_bytes']<=result['cuda_peak_reserved_bytes'],'finite complete native epoch timing/memory required')
    proof.update(full_native_long_ttt_completed=True,input_tokens=955392,supervised_tokens=476160,
        training_wall_seconds=result['training_wall_seconds'],cuda_peak_allocated_bytes=result['cuda_peak_allocated_bytes'],
        cuda_peak_reserved_bytes=result['cuda_peak_reserved_bytes'],all_saved_tensors_restored=True)
    return proof


if __name__=='__main__':
    parser=ArgumentParser()
    for name in ('archive','package','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();require(not args.output.exists(),'new immutable native epoch proof required')
    proof=verify(args.archive,args.package);atomic(args.output,proof);print(json.dumps(proof))
