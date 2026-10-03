"""Closed original source-SFT reader and one-shot retained-byte transport.

Local checks reconstruct source placement, actual-call prefixes and every byte
binding. CUDA loss/gradient/moment observations remain worker observations.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.arc_nvarc_fsdp_sft import verify_checkpoint
from irisx.arc_nvarc_gpu_preflight_v2 import require_cpu_residency
from irisx.arc_nvarc_packing import pack_sequences
from irisx.arc_nvarc_qwen3_packing import execution_slices
from irisx.arc_nvarc_qwen3_sft import file_inventory
from irisx.canonical import digest_value
from irisx.errors import ValidationError


def require(value,message):
    if not value:raise ValidationError(message)


def safe_name(name,prefix=None):
    require(isinstance(name,str) and name and '\\' not in name and ':' not in name and
        all(part not in {'','.','..'} for part in name.split('/')) and (prefix is None or name.startswith(prefix)),
        'safe closed retained material path required')


def read_archive(archive,package):
    from tools.stage_nvarc_qwen3_sft import preflight
    preflight(package)
    plan=json.loads((package/'plan.json').read_bytes());data={}
    with zipfile.ZipFile(archive) as stream:
        require(stream.getinfo('manifest.json').file_size<8*1024**2,'bounded archive manifest required')
        manifest=json.loads(stream.read('manifest.json'));members=manifest['members'];names=[r['path'] for r in members]
        require(manifest['run_id']==plan['run_id'] and manifest['plan_digest']==digest_value(plan) and
            len(names)==len(set(names)) and len(stream.namelist())==len(names)+1 and
            set(stream.namelist())==set(names)|{'manifest.json'} and
            all(type(r['bytes']) is int and 0<=r['bytes']<=8*1024**2 for r in members) and
            sum(r['bytes'] for r in members)<=64*1024**2,'closed bounded original SFT archive required')
        for row in members:
            safe_name(row['path'])
            require(stream.getinfo(row['path']).file_size==row['bytes'],'declared diagnostic size differs')
            raw=stream.read(row['path'])
            require(hashlib.sha256(raw).hexdigest()==row['sha256'],'diagnostic member digest differs')
            data[row['path']]=raw
    read=lambda name:json.loads(data[name])
    require(read('plan.json')==plan and read('payload-bindings.json')==json.loads(
        (package/'stage-summary.json').read_bytes())['payload_sha256'],'exact saved original SFT bindings required')
    terminal=read('terminal.json')
    require(terminal['run_id']==plan['run_id'] and terminal['outcome'] in {'complete','failed'} and
        terminal['contains_evaluator_truth'] is False and terminal['generation_calls']==terminal['teacher_calls']==0 and
        terminal['full_sft_completed'] is False,'truth-free bounded original SFT result required')
    return plan,data,terminal


def expected_calls(rows,rank,slots):
    packs=pack_sequences(rows[rank::4],capacity=256000,length_multiple=64)
    pieces=[p for pack in packs for p in execution_slices(pack,32768)]
    dummy=pack_sequences([{'input_ids':[14,15],'labels':[-100,15]}],capacity=256000,length_multiple=64)[0]
    result=[]
    for pack in pieces+[dummy]*(slots-len(pieces)):
        ids,positions,offsets=[],[],[0]
        for segment in pack['segments']:
            values=pack['input_ids'][segment['start']:segment['valid_end']]
            ids.extend(values);positions.extend(range(len(values)));offsets.append(len(ids))
        result.append({'input_ids_digest':digest_value([ids]),'position_ids_digest':digest_value([positions]),
            'cu_seqlens':offsets,'input_tokens':len(ids)})
    return result


def verify(archive,package,retained=None):
    plan,data,terminal=read_archive(archive,package)
    read=lambda name:json.loads(data[name])
    rows=json.loads((package/'samples.json').read_bytes())
    stream_identity=digest_value({'kind':plan['data_kind'],'rows_digest':plan['data_digest']})
    identity=digest_value({'plan':plan,'source_stream_identity':stream_identity})
    counts=[]
    for step,placement in enumerate(plan['physical_schedules']):
        for rank in range(4):
            stem=f'worker/rank-{rank}-'
            reservation=stem+f'call-reservation-{step:05d}.json'
            ledger=stem+f'forward-ledger-{step:05d}.json'
            wanted=expected_calls(rows[step*256:(step+1)*256],rank,placement['collective_slots_per_rank'])
            events=read(ledger) if ledger in data else []
            require(isinstance(events,list) and len(events)<=len(wanted),'finite original forward prefix required')
            for index,event in enumerate(events):
                require(set(event)==set(wanted[index])|{'completed'} and type(event['completed']) is bool and
                    {k:event[k] for k in wanted[index]}==wanted[index] and
                    (event['completed'] or index==len(events)-1),'exact original actual input/position/causal prefix required')
            if reservation in data:
                item=read(reservation);rankplan=placement['ranks'][rank]
                require(item['plan_digest']==digest_value(plan) and item['outer_forwards']==len(wanted) and
                    item['input_tokens']==sum(r['input_tokens'] for r in wanted) and
                    item['source_input_tokens']==rankplan['input_tokens'] and type(item['completed']) is bool,
                    'exact cumulative source/dummy reservation required')
                if item['completed']:
                    require(len(events)==len(wanted) and all(e['completed'] for e in events) and
                        item['real_forwards']==len(rankplan['physical_digests']) and
                        item['dummy_forwards']==len(wanted)-item['real_forwards'],'complete original rank calls required')
            else:require(not events,'actual forward cannot precede reservation')
            if terminal['outcome']=='complete':require(reservation in data and read(reservation)['completed'],
                'all eight original rank/step reservations must complete')
            counts.append({'step':step+1,'rank':rank,'entered_forwards':len(events),
                'completed_forwards':sum(e['completed'] for e in events)})
    allowed={f'worker/rank-{rank}-call-reservation-{step:05d}.json' for rank in range(4) for step in range(2)}
    require({name for name in data if '-call-reservation-' in name}<=allowed,'extra original reservation denied')
    allowed_ledgers={name.replace('call-reservation','forward-ledger') for name in allowed}
    require({name for name in data if '-forward-ledger-' in name}<=allowed_ledgers,'extra original forward ledger denied')
    if terminal['outcome']=='complete':
        pause=read('worker/pause-result.json');final=read('worker/final-result.json');chain=read('worker/export-chain.json')
        hardware=read('hardware.json')['inventory']
        require(len(hardware)==4 and len({x['uuid'] for x in hardware})==4 and
            all(x['name']=='NVIDIA L4' and x['bf16'] for x in hardware),'four distinct BF16 L4s required')
        for index,result in enumerate((pause,final)):
            subset=rows[:256*(index+1)]
            require(result['identity_digest']==identity and result['plan_digest']==digest_value(plan) and
                result['source_stream_identity']==stream_identity and result['step']==index+1 and
                result['cursor']==len(subset) and result['input_tokens']==sum(len(r['input_ids']) for r in subset) and
                result['supervised_tokens']==sum(sum(v>=0 for v in r['labels'][1:]) for r in subset) and
                result['forwards']==sum(p['real_outer_forwards'] for p in plan['physical_schedules'][:index+1]) and
                result['full_sft_completed'] is False and result['model_family']=='qwen3' and
                result['optimizer_checkpoints_retained'] is True and result['contains_evaluator_truth'] is False and
                result['generation_calls']==result['teacher_calls']==0 and
                result['weight_fingerprint_before']!=result['weight_fingerprint_after'] and
                all(math.isfinite(v) for v in result['weight_fingerprint_after']),
                'complete original source step identity/counts required')
            observations=result['observations']
            require(len(observations)==1 and len(observations[0])==4,'exact restart phase observations required')
            placement=plan['physical_schedules'][index]
            for rank,observed in enumerate(observations[0]):
                require(observed['rank']==rank and observed['step']==index+1 and
                    observed['hardware']['device_uuid']==hardware[rank]['uuid'] and observed['checkpointed_layers']==36 and
                    observed['packing_execution']=='torch-varlen-flash' and observed['fused_packing_verified'] is True and
                    not observed['missing_owned_gradient_shards'] and observed['finite_nonzero_shards']>0 and
                    observed['owned_parameter_shards']==observed['accumulated_parameter_shards'] and
                    observed['physical_packing_layout_digests']==placement['ranks'][rank]['physical_digests'] and
                    observed['real_forward_calls']==len(placement['ranks'][rank]['physical_digests']) and
                    observed['dummy_forward_calls']==placement['collective_slots_per_rank']-observed['real_forward_calls'] and
                    observed['global_sequence_count']==256 and
                    observed['global_input_tokens']==sum(p['input_tokens'] for p in placement['ranks']) and
                    observed['global_supervised_tokens']==sum(p['supervised_tokens'] for p in placement['ranks']) and
                    observed['source_lineage']==[{k:v for k,v in row.items() if k not in {'input_ids','labels'}}
                        for row in rows[index*256+rank:(index+1)*256:4]] and
                    math.isfinite(observed['global_token_mean_loss']) and math.isfinite(observed['gradient_norm_before_clip']),
                    'complete original packed gradient/residency observation required')
                require_cpu_residency(observed['state_residency'])
        require(final['restored_fingerprint']==pause['weight_fingerprint_after'] and
            chain['identity_digest']==identity and chain['checkpoint_step']==2 and
            chain['checkpoint_manifest_digest']==final['checkpoint']['manifest_digest'] and
            chain['reload_tensor_bytes_identical'] is True and chain['export_material_digest']==terminal['export_material_digest'] and
            terminal['identity_digest']==identity,'exact process restart and original export chain required')
    proof={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'archive_sha256':sha(archive),
        'closed_diagnostic_members':len(data),'outcome':terminal['outcome'],'actual_call_prefixes':counts,
        'full_sft_completed':False,'historical_nemo_parity':False,'stable_sft_rate_verified':False,'correctness_scored':False,
        'generation_calls':0,'teacher_calls':0,'maximum_paid_usd':0,'retained_optimizer_bytes_verified':False}
    if retained is not None:
        entries=read('checkpoint-inventory.json')
        if entries:
            latest=json.loads((retained/'checkpoints/latest.json').read_bytes())
            safe_name(latest['path']);require('/' not in latest['path'],'checkpoint transaction basename required')
            manifest=verify_checkpoint(retained/'checkpoints'/latest['path'],identity,4)
            require(digest_value(manifest)==latest['manifest_digest'] and manifest['state']['step']==latest['step'],
                'exact local retained checkpoint pointer required')
            actual={p.relative_to(retained).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)}
                for p in (retained/'checkpoints').rglob('*') if p.is_file()}
            require(actual=={r['path']:{'bytes':r['bytes'],'sha256':r['sha256']} for r in entries},
                'all retained local checkpoint bytes required')
            prefix='checkpoints/'+latest['path']+'/'
            require(set(actual)=={prefix+r['path'] for r in manifest['files']}|
                {prefix+'manifest.json','checkpoints/latest.json'},'only the complete latest transaction may be transferred')
            proof.update(retained_optimizer_bytes_verified=True,retained_checkpoint_step=latest['step'])
        if terminal['outcome']=='complete':
            material=read('export-material.json');inventory=file_inventory(retained/'export')
            require(inventory==material['inventory'] and digest_value(inventory)==material['material_digest']==terminal['export_material_digest'] and
                material['training_identity_digest']==identity and material['model_family']=='qwen3',
                'exact local original-family export bytes required')
            proof.update(retained_export_bytes_verified=True,export_material_digest=material['material_digest'])
            require(proof['retained_optimizer_bytes_verified'],'complete run must retain optimizer checkpoint bytes')
    return proof


def material_entries(data,terminal):
    read=lambda name:json.loads(data[name])
    checkpoints=read('checkpoint-inventory.json')
    exports=read('export-inventory.json') if terminal['outcome']=='complete' else []
    require(isinstance(checkpoints,list) and isinstance(exports,list),'closed retained inventories required')
    entries=checkpoints+exports
    require(len(entries)==len({r['path'] for r in entries}) and len(entries)<=80 and
        sum(r['bytes'] for r in checkpoints)<=64*1024**3 and sum(r['bytes'] for r in exports)<=9*1024**3,
        'bounded full checkpoint/export transfer required')
    for item in checkpoints:
        safe_name(item['path'],'checkpoints/')
        require(type(item['bytes']) is int and 0<=item['bytes']<=16*1024**3,'bounded checkpoint shard required')
    transactions={r['path'].split('/')[1] for r in checkpoints if r['path']!='checkpoints/latest.json'}
    require(not checkpoints or (len(transactions)==1 and
        re.fullmatch(r'checkpoint-step-\d{4}-attempt-\d{4}',next(iter(transactions))) and
        any(r['path']=='checkpoints/latest.json' for r in checkpoints) and
        all(len(r['path'].split('/'))>=3 for r in checkpoints if r['path']!='checkpoints/latest.json')),
        'one complete latest transaction and pointer required')
    for item in exports:
        safe_name(item['path'],'export/')
        require(type(item['bytes']) is int and 0<=item['bytes']<=3*1024**3,'bounded export shard required')
    return entries


def retrieve_materials(archive,package,destination,urls,reserve):
    import requests
    plan,data,terminal=read_archive(archive,package)
    verify(archive,package)
    entries=material_entries(data,terminal)
    require(shutil.disk_usage(destination).free>sum(r['bytes'] for r in entries)+2*1024**3,'complete local retention capacity required')
    event={'downloads':[],'full_sft_completed':False}
    for item in entries:
        name=plan['run_id']+'/'+item['path'];require(name in urls and urls[name].startswith('https://'),'listed exact material URL required')
        target=destination/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
        event['downloads'].append({'path':item['path'],'bytes_expected':item['bytes'],'reserved':True});reserve(event)
        size=0;digest=hashlib.sha256()
        with requests.get(urls[name],stream=True,timeout=(15,120)) as response:
            response.raise_for_status()
            with target.open('xb') as stream:
                for chunk in response.iter_content(1024**2):
                    size+=len(chunk);require(size<=item['bytes'],'retained member exceeds exact bound')
                    digest.update(chunk);stream.write(chunk)
                stream.flush();import os;os.fsync(stream.fileno())
        require(size==item['bytes'] and digest.hexdigest()==item['sha256'],'retained material byte digest differs')
        event['downloads'][-1].update(verified=True,sha256=digest.hexdigest());reserve(event)
        print(json.dumps({'original_sft_member_verified':item['path'],'bytes':size}),flush=True)
    event['proof']=verify(archive,package,destination);reserve(event)
    return event


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--retained',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    require(not args.output.exists(),'new immutable original SFT verification required')
    result=verify(args.archive,args.package,args.retained);atomic(args.output,result);print(json.dumps(result))
