"""Independent closed-byte, whole-view and cost reader; no model or scoring."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.arc_nvarc_data import visible_task
from irisx.arc_nvarc_qwen3_long_ttt import check_plan,row_digest
from irisx.arc_nvarc_training import task_local_sequences
from irisx.arc_nvarc_upstream import source_bundle
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError


def require(condition,message):
    if not condition:raise ValidationError(message)


def integer(value):return type(value) is int


def validate_progress(ledger,events,rows,complete=False):
    """Reconstruct approved row multiplicity and every returned step prefix."""
    identities=[row_digest(row) for row in rows]
    lengths={identity:len(row['input_ids']) for identity,row in zip(identities,rows)}
    actual=ledger['forward_row_digests'];steps=ledger['optimizer_steps_completed']
    require(all(integer(ledger[k]) for k in ('outer_forwards_reserved','input_tokens_reserved',
        'optimizer_steps_completed','generation_calls','teacher_calls','verification_calls','maximum_paid_usd')),
        'integer actual long-epoch cost ledger required')
    require(len(actual)==ledger['outer_forwards_reserved']<=128 and 0<=steps<=len(actual) and
        not Counter(actual)-Counter(identities) and
        ledger['input_tokens_reserved']==sum(lengths[identity] for identity in actual) and
        all(ledger[k]==0 for k in ('generation_calls','teacher_calls','verification_calls','maximum_paid_usd')),
        'approved row multiplicity/input/step/zero-call ledger differs')
    returned=[event for event in events if event['event']=='ttt-optimizer-returned']
    require(len(returned)<=steps<=len(returned)+(0 if complete else 1),'returned optimizer event prefix differs')
    indices=[];tokens=0
    for position,event in enumerate(returned):
        index=event['source_view_index'];step=position+1
        require(integer(index) and 0<=index<len(rows) and index not in indices and
            integer(event['completed_steps']) and event['completed_steps']==step and
            actual[position]==identities[index],'step/source-view/forward digest correspondence differs')
        tokens+=len(rows[index]['input_ids']);indices.append(index)
        expected_rate=5e-5*(position/13 if position<13 else .5*(1+math.cos(math.pi*(position-13)/115)))
        require(integer(event['training_tokens']) and event['training_tokens']==tokens and
            type(event['loss']) in (int,float) and math.isfinite(event['loss']) and event['loss']>=0 and
            type(event['learning_rate']) in (int,float) and
            math.isclose(event['learning_rate'],expected_rate,rel_tol=1e-12,abs_tol=1e-15),
            'complete-row token/loss/original warmup-cosine schedule differs')
    if complete:
        require(steps==128 and len(actual)==128 and Counter(actual)==Counter(identities) and
            sorted(indices)==list(range(128)),'complete original 128-view epoch required')
    return returned


def verify(archive,package):
    plan=json.loads((package/'plan.json').read_bytes());config=json.loads((package/'config.json').read_bytes())
    raw=json.loads((package/'visible.json').read_bytes());summary=json.loads((package/'stage-summary.json').read_bytes())
    require({p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file() and
        p.name!='stage-summary.json'}==summary['inventory'],'frozen closed long-epoch package differs')
    tasks=[visible_task(key,value) for key,value in sorted(raw.items())];check_plan(plan,config,tasks)
    require(digest_value(plan)==summary['plan_digest'],'frozen long-epoch plan digest differs')
    with source_bundle(package/'source-bundle',plan['source_bundle_digest']):
        rows=task_local_sequences(tasks[0],seed=42,augmentation_count=16,source_qwen=True,
            source_augmentation_seed=1,source_max_length=8192)
    require(len(rows)==128 and digest_value(rows)==plan['source_rows_digest'] and
        sum(len(row['input_ids']) for row in rows)==plan['source_input_tokens'] and
        max(len(row['input_ids']) for row in rows)==plan['source_max_sequence_length'],
        'independently reconstructed complete public-demo views differ')
    data={}
    with zipfile.ZipFile(archive) as stream:
        require(stream.getinfo('manifest.json').file_size<=1024**2,'bounded archive index required')
        manifest=json.loads(stream.read('manifest.json'));entries=manifest['members'];names=[r['path'] for r in entries]
        require(manifest['format']=='irisx/nvarc-gpu-preflight-archive-v1' and
            manifest['run_id']==plan['run_id'] and manifest['plan_digest']==digest_value(plan) and
            len(names)==len(set(names)) and len(stream.namelist())==len(names)+1 and
            set(stream.namelist())==set(names)|{'manifest.json'} and
            all(integer(r['bytes']) and r['bytes']>=0 for r in entries) and
            sum(r['bytes'] for r in entries)<=64*1024**2,'closed bounded long-epoch archive identity differs')
        for item in entries:
            name=item['path']
            require('\\' not in name and ':' not in name and not any(x in {'','.','..'} for x in name.split('/')),
                'unsafe long-epoch archive member')
            require(stream.getinfo(name).file_size==item['bytes'],'archive physical member size differs')
            member=stream.read(name)
            require(len(member)==item['bytes'] and hashlib.sha256(member).hexdigest()==item['sha256'],
                'long-epoch archive member bytes differ')
            data[name]=member
    def read(name):return json.loads(data[name])
    require(canonical_bytes(read('plan.json'))==canonical_bytes(plan) and
        read('payload-bindings.json')==summary['payload_sha256'],'returned exact long-epoch inputs differ')
    terminal=read('terminal.json');complete=terminal['outcome']=='complete'
    require(terminal['outcome'] in {'complete','failed'} and terminal['run_id']==plan['run_id'] and
        terminal['contains_evaluator_truth'] is False,'known truth-free long-epoch terminal required')
    ledger=read('worker/ledger.json') if 'worker/ledger.json' in data else None
    events=[json.loads(line) for line in data.get('worker/events.jsonl',b'').splitlines()]
    returned=[]
    if ledger is not None:
        require(ledger['run_id']==plan['run_id'] and ledger['plan_digest']==digest_value(plan),'worker ledger identity differs')
        returned=validate_progress(ledger,events,rows,complete)
    proof={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'archive_sha256':sha(archive),
        'outcome':terminal['outcome'],'closed_members':len(data),'model_material_digest':plan['model_material_digest'],
        'approved_source_views':128,'approved_input_tokens':plan['source_input_tokens'],
        'reserved_outer_forwards':0 if ledger is None else ledger['outer_forwards_reserved'],
        'completed_optimizer_steps':0 if ledger is None else ledger['optimizer_steps_completed'],
        'generation_calls':0,'teacher_calls':0,'correctness_scored':False,'maximum_paid_usd':0,
        'full_long_task_epoch_completed':False,'full_sft_completed':False,'checkpoint_exported':False,
        'historical_unsloth_parity':False,'historical_task_clock_parity':False,
        'numeric_scope':'worker-observed training/reset; reader reconstructs exact public rows, step events and cost bindings'}
    if not complete:
        proof.update(failure_phase=terminal['phase'],error_type=terminal['error_type'],error_message=terminal['error_message'])
        return proof
    require(ledger is not None and ledger['phase']=='complete','complete worker ledger required')
    worker=read('worker/worker-result.json');observation=worker['observation']
    require(all(canonical_bytes(terminal.get(k))==canonical_bytes(v) for k,v in worker.items()),
        'parent/worker long-epoch results differ')
    hardware=read('hardware.json');devices=hardware['inventory']
    require(hardware['torch']=='2.10.0+cu128' and len(devices)==4 and len({r['uuid'] for r in devices})==4 and
        all(r['name']=='NVIDIA L4' and r['bf16'] is True for r in devices) and
        worker['hardware']['rank']==0 and worker['hardware']['name']=='NVIDIA L4' and worker['hardware']['bf16'] is True and
        worker['hardware']['device_uuid'] in {r['uuid'] for r in devices},'four-L4/actual training worker identity differs')
    require(read('material-verification.json')=={'all_files_verified':True,'material_digest':plan['model_material_digest']} and
        read('mount-policy.json')['competition_files_opened']==0,'exact truth-free material/mount verification required')
    exact={'plan_digest':digest_value(plan),'model_material_digest':plan['model_material_digest'],
        'source_rows_digest':plan['source_rows_digest'],'transformers_version':'4.53.3','peft_version':'0.21.0',
        'torch_version':'2.10.0+cu128','embedding_head_tied':False,'adapter_target_count':254,
        'outer_forwards':128,'optimizer_steps':128,'input_tokens':plan['source_input_tokens'],
        'generation_calls':0,'teacher_calls':0,'verification_calls':0,'checkpoint_exported':False,
        'full_sft_completed':False,'historical_unsloth_parity':False,'historical_task_clock_parity':False,
        'full_long_task_epoch_completed':True,'adapter_reset_verified':True}
    require(all(canonical_bytes(worker.get(k))==canonical_bytes(v) for k,v in exact.items()),
        'bounded complete long-epoch observation differs')
    require(worker['initial_adapter_digest']==worker['reset_adapter_digest']!=worker['adapted_adapter_digest'] and
        all(isinstance(worker[k],str) and len(worker[k])==71 and worker[k].startswith('sha256:') for k in
            ('initial_adapter_digest','adapted_adapter_digest','reset_adapter_digest')),'changed/reset adapter byte digest differs')
    require(observation['task_id']==tasks[0]['task_id'] and observation['status']=='complete' and
        observation['training_schedule']=='source-one-epoch' and observation['steps']==128 and
        observation['training_tokens']==plan['source_input_tokens'] and observation['source_view_count']==128 and
        observation['complete_epoch'] is True and observation['warmup_steps']==13 and
        observation['consumed_view_indices']==[event['source_view_index'] for event in returned] and
        observation['losses_by_step']==[event['loss'] for event in returned] and
        observation['learning_rates_by_step']==[event['learning_rate'] for event in returned] and
        observation['source_sequence_keys']==[row['source'] for row in rows] and
        observation['last_loss']==returned[-1]['loss'] and observation['gradient_checkpointing'] is True and
        observation['optimizer_state_device']=='cpu' and observation['trainable_parameter_count']==529801216 and
        len(observation['targets'])==len(set(observation['targets']))==254,'whole source epoch/runtime/adapter coverage differs')
    groups=observation['gradient_groups_by_step']
    require(len(groups)==128 and all(set(row)=={'attention','delta','embedding','head','other'} and
        all(integer(v) and v>=0 for v in row.values()) and row['delta']==0 and
        all(row[k]>0 for k in ('attention','embedding','head','other')) for row in groups),
        'every step requires finite nonzero original gradient groups')
    require(all(integer(observation[k]) and observation[k]>0 for k in
        ('peak_cuda_allocated_bytes','peak_cuda_reserved_bytes')) and
        math.isfinite(worker['worker_wall_seconds']) and 0<worker['worker_wall_seconds']<=10560,
        'finite complete CUDA memory/time observation required')
    proof.update(full_long_task_epoch_completed=True,adapter_reset_verified=True,
        input_tokens=worker['input_tokens'],worker_wall_seconds=worker['worker_wall_seconds'],
        peak_cuda_allocated_bytes=observation['peak_cuda_allocated_bytes'],
        peak_cuda_reserved_bytes=observation['peak_cuda_reserved_bytes'])
    return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('archive','package','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();proof=verify(args.archive,args.package);atomic(args.output,proof);print(json.dumps(proof))
