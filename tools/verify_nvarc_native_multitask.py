"""Offline closed archive verification, native evidence replay and export recount."""
from __future__ import annotations
import argparse
from array import array
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.stage_nvarc_native_multitask import preflight,construct,FILES
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import digest,canonical,require,write
from tools.nvarc_native_submission import read_task_evidence,build_native_submission,reject_truth,check_events,task_binding
from tools.nvarc_native_solve_runtime import compare_vectors,CONTROL_PREFIXES


def verify_receipt(receipt,attempt,maximum_seconds):
    required={'task_id','attempt_id','status','launched','returncode','reset_inferred'}
    require(required<=set(receipt)<=required|{'reserved_seconds','error_type','error_message'} and
        (receipt['task_id'],receipt['attempt_id'])==(attempt['task_id'],attempt['attempt_id']) and
        receipt['status'] in {'complete','failed','worker_crash','timeout','oom','interrupted_pending',
            'not_executed','session_limit'} and type(receipt['launched']) is bool and
        receipt['reset_inferred'] is False and
        (receipt['returncode'] is None or type(receipt['returncode']) is int) and
        (receipt['launched'] or receipt['status'] in {'not_executed','session_limit'}),
        'closed actual worker receipt required')
    require(receipt['status']!='complete' or receipt['launched'] and receipt['returncode']==0,
        'complete receipt requires successful process exit')
    if receipt['launched']:
        require(type(receipt.get('reserved_seconds')) in (int,float) and math.isfinite(receipt['reserved_seconds']) and
            0<receipt['reserved_seconds']<=maximum_seconds,'bounded dispatch reservation required')


def verify_controls(content,prefix,events,result):
    """Recount six branch controls and the final reset call, separately from flags."""
    controls=[e for e in events if e['event']=='forward_reserved' and e['phase']=='control']
    completed={e['call_id']:e for e in events if e['event']=='forward_completed' and e['phase']=='control'}
    expected=[(CONTROL_PREFIXES,False,0),([[0]]*4,True,9),([[1]]*4,True,10),([[2]]*4,True,9),
        ([r+[0,1] for r in CONTROL_PREFIXES],False,0),([r+[2] for r in CONTROL_PREFIXES],False,0),
        (CONTROL_PREFIXES,False,0)]
    for event,(ids,cached,start) in zip(controls,expected):
        require(event['input_ids_digest']==digest(ids) and event['batch_shape']==[4,len(ids[0])] and
            event['cached'] is cached and event['position_start']==start and
            event['position_end']==start+len(ids[0])-1,'actual cache/reset control inputs differ')
    observed=[e for e in events if e['event']=='cache_control_result']
    cache=None;baseline=None;prefill=None
    if prefix+'cache-control.json' in content:
        cache=parse_json(content[prefix+'cache-control.json']);reject_truth(cache)
        require(set(cache)=={'comparisons','baseline_prefill','model_calls','synthetic_tokens_only',
            'full_numerical_parity_claim'} and cache['model_calls']==6 and type(cache['model_calls']) is int and
            cache['synthetic_tokens_only'] is True and cache['full_numerical_parity_claim'] is False and
            len(observed)==1 and len(controls)>=6 and all(e['call_id'] in completed for e in controls[:6]) and
            max(completed[e['call_id']]['sequence'] for e in controls[:6])<observed[0]['sequence'],
            'complete six-call raw cache transcript required')
        event=observed[0]
        recomputed={'deep':compare_vectors(event['deep_reference'],event['deep_cached']),
            'sibling_after_deep':compare_vectors(event['sibling_reference'],event['sibling_cached'])}
        require(event['comparisons']==cache['comparisons']==recomputed and
            event['baseline_prefill']==cache['baseline_prefill'] and
            all(v['gate_passed'] for v in recomputed.values()),'raw native cache branch control differs')
        compare_vectors(cache['baseline_prefill'],cache['baseline_prefill'])
        baseline=parse_json(content[prefix+'baseline-inventory.json']);prefill=cache['baseline_prefill']
    restored=result['all_saved_tensors_restored']
    if restored:
        require(parse_json(content[prefix+'baseline-inventory.json'])==
            parse_json(content[prefix+'reset-inventory.json']),'exact reset bytes differ')
    reset_call=(len(controls)==7 and len(completed)==7 and cache is not None and
        controls[-1]['sequence']>observed[0]['sequence'] and
        all(e['call_id'] in completed and completed[e['call_id']]['sequence']>e['sequence'] for e in controls) and
        sum(e['physical_input_tokens'] for e in controls)==168)
    if result['post_reset_control_verified']:
        post=parse_json(content[prefix+'post-reset-control.json']);reject_truth(post)
        require(cache is not None and set(post)=={'prefill_bitwise_equal','prefill','synthetic_tokens_only',
            'additional_model_calls'} and post['prefill']==cache['baseline_prefill'] and
            post['prefill_bitwise_equal'] is post['synthetic_tokens_only'] is True and
            type(post['additional_model_calls']) is int and post['additional_model_calls']==1,
            'reset actual logits/one-call contract differs')
    return {'cache_observed':cache is not None,'reset_call_observed':reset_call,
        'complete':reset_call and restored and result['post_reset_control_verified'] and result['optimizer_discarded'],
        'baseline':baseline,'prefill':prefill}


def verify_training(content,prefix,spec,mode,plan,material):
    def read(name):return parse_json(content[prefix+name])
    if prefix+'training-ledger.json' not in content:
        return {'training_gate':False,'forwards':0,'steps':0,'reserved_forwards':0,'reserved_steps':0,'tokens':0}
    ledger=read('training-ledger.json');rows=read('prepared-rows.json')
    expected=material[next(a['task_id'] for a in plan['worker_attempts'] if prefix=='tasks/'+a['attempt_id']+'/native/')]['rows']
    require(len(rows)==len(expected)==spec['training_forwards'],'actual task-derived row denominator differs')
    tokens=content[prefix+'prepared-tokens.i16le'];offset=0
    for row,wanted in zip(rows,expected):
        count=wanted['input_tokens'];size=count*4
        require(row['retained_byte_offset']==offset and row['retained_token_bytes']==size and offset+size<=len(tokens),
                'prepared native token slice differs')
        values=array('h');values.frombytes(tokens[offset:offset+size]);offset+=size
        if sys.byteorder!='little':values.byteswap()
        ids,labels=list(values[:count]),list(values[count:])
        require(digest(ids)==wanted['input_ids_digest']==row['input_ids_digest'] and
                digest(labels)==wanted['labels_digest']==row['labels_digest'] and
                sum(x>=0 for x in labels[1:])==wanted['supervised_tokens'] and
                row['source_input_ids_equal'] is row['source_labels_equal'] is row['collator_preserved_input_ids'] is True,
                'native prepared row/token/label binding differs')
    require(offset==len(tokens),'extra prepared token bytes')
    preparation=read('preparation.json')
    require(preparation['trainer_origins']==plan['native_trainer_origins'] and
        preparation['checkpoint_flags']==plan['native_checkpoint_flags'] and
        preparation['prepared_rows_digest']==digest(rows) and preparation['blocked_attempts']==0,
        'exact native preparation origins/flags differ')
    expected_counts=Counter((r['input_ids_digest'],r['labels_digest']) for r in expected)
    for key in ('forwards','training_steps','optimizer_steps'):
        require(len(ledger[key])<=len(rows) and all(type(r['completed']) is bool for r in ledger[key]),'finite training prefix required')
    actual_counts=Counter((r['input_ids_digest'],r['labels_digest']) for r in ledger['forwards'])
    require(not +(actual_counts-expected_counts),'training rows replayed/cross-task/mismatched')
    require(all(1<=r['input_tokens']<=spec['maximum_sequence_tokens'] and
                (r['input_tokens'],r['supervised_tokens'])==next((x['input_tokens'],x['supervised_tokens']) for x in expected
                if x['input_ids_digest']==r['input_ids_digest'] and x['labels_digest']==r['labels_digest'])
                for r in ledger['forwards']),'training physical token recount differs')
    schedule=read('native-schedule.json')
    from tools.nvarc_native_ttt_schedule import ulp_distance
    require(schedule['epoch_steps']==len(rows) and schedule['warmup_steps']==13 and
            schedule['maximum_reference_ulp_distance']<=4 and len(schedule['rates'])==len(rows)+1 and
            all(ulp_distance(a,b)<=4 for a,b in zip(schedule['rates'],spec['source_learning_rates'])),
            'task-derived native schedule differs')
    import math
    for i,r in enumerate(ledger['optimizer_steps']):
        require(r['learning_rate']==schedule['rates'][i] and r['gradient_tensors']==506 and
                type(r['gradient_norm_after_clip']) in (int,float) and math.isfinite(r['gradient_norm_after_clip']) and
                0<=r['gradient_norm_after_clip']<=1.05,'native optimizer recipe differs')
    result=read('result.json') if prefix+'result.json' in content else None
    complete=result is not None and result['training_complete']
    if complete:
        require(mode=='solve' and all(len(ledger[k])==len(rows) and all(r['completed'] for r in ledger[k])
                for k in ('forwards','optimizer_steps','training_steps')) and actual_counts==expected_counts,
                'complete epoch must consume every exact public row once')
        before,after=read('baseline-inventory.json'),read('trained-inventory.json')
        require(len(before)==len(after)==506 and [r['name'] for r in before]==[r['name'] for r in after] and
                all(r['finite'] is True and r['dtype']=='torch.bfloat16' for r in before+after) and before!=after,
                'finite changed exact native BF16 tensor topology required')
        moments=read('optimizer-state.json')
        require(len(moments)==506 and all(r['step']==len(rows) and r['finite'] is True and
                r['parameter_dtype']=='torch.bfloat16' for r in moments),'complete finite same-dtype Adam moments required')
    if mode=='fault-after-two-updates':
        require(len(ledger['forwards'])<=2 and len(ledger['optimizer_steps'])<=2,'injected fault exceeded two-update bound')
    return {'training_gate':bool(complete),'forwards':sum(r['completed'] for r in ledger['forwards']),
            'steps':sum(r['completed'] for r in ledger['optimizer_steps']),
            'reserved_forwards':len(ledger['forwards']),'reserved_steps':len(ledger['optimizer_steps']),
            'tokens':sum(r['input_tokens'] for r in ledger['forwards'])}


def verify(archive,package):
    checked=preflight(package);admission=package/'controller-admission.json'
    plan,raw,_,_=construct(checked['run_id'],admission if admission.is_file() else None);content={}
    with zipfile.ZipFile(archive) as stream:
        names=stream.namelist();require(len(names)==len(set(names))==len({n.casefold() for n in names}) and
            sum(r.file_size for r in stream.infolist())<=plan['maximum_result_uncompressed_bytes'],'closed bounded ZIP required')
        manifest=parse_json(stream.read('manifest.json'));members=manifest['members']
        require(manifest['run_id']==plan['run_id'] and manifest['plan_digest']==digest(plan) and
            len(members)==len({r['path'] for r in members}) and set(names)=={r['path'] for r in members}|{'manifest.json'},
            'exact closed archive identity required')
        for row in members:
            path=PurePosixPath(row['path']);require(not path.is_absolute() and '..' not in path.parts and
                '\\' not in row['path'] and path.as_posix()==row['path'] and
                all(':' not in part and not part.endswith((' ','.')) and
                    part.split('.')[0].upper() not in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],
                        *[f'LPT{i}' for i in range(1,10)]} for part in path.parts),'unsafe/ambiguous ZIP path')
            body=stream.read(row['path']);require(len(body)==row['bytes'] and hashlib.sha256(body).hexdigest()==row['sha256'],
                'ZIP member digest differs');content[row['path']]=body
    def read(name):return parse_json(content[name])
    require(read('plan.json')==plan and read('payload-bindings.json')==
            {k:hashlib.sha256(v).hexdigest() for k,v in raw.items()},'returned exact input bindings differ')
    terminal=read('terminal.json');reject_truth(terminal)
    require(terminal['run_id']==plan['run_id'] and terminal['outcome'] in {'failed','complete'} and
        type(terminal['wall_seconds']) in (int,float) and 0<=terminal['wall_seconds']<=plan['maximum_notebook_wall_seconds'],
        'finite parent terminal required')
    proof={'run_id':plan['run_id'],'plan_digest':digest(plan),'archive_sha256':hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
        'closed_members':len(content),'parent_outcome':terminal['outcome'],'gpu_validation_gate':False,
        'gpu_runtime':'unverified','correctness_scored':False,'official_score':None,'digest_is_execution_attestation':False}
    if 'worker-receipts.json' not in content:
        require(terminal['outcome']=='failed','success needs worker dispatch evidence')
        proof.update(outcome='failed-before-dispatch',failure_phase=terminal['phase']);return proof
    require(plan['approved'] is True,'an inert package cannot have native runtime evidence')
    for name,key in FILES.items():require(content[name]==raw[key],'actual retained producer source differs: '+name)
    receipts=read('worker-receipts.json');attempts=plan['worker_attempts']
    require(len(receipts)<=len(attempts) and [(r['task_id'],r['attempt_id']) for r in receipts]==
        [(a['task_id'],a['attempt_id']) for a in attempts[:len(receipts)]],'parent sequential attempt order/denominator differs')
    for attempt,receipt in zip(attempts,receipts):verify_receipt(receipt,attempt,plan['maximum_child_wall_seconds'])
    if 'worker_receipts_digest' in terminal:
        require(terminal['worker_receipts_digest']==digest(receipts),'parent terminal receipt binding differs')
    hardware=read('hardware.json');devices=hardware['inventory']
    require(hardware['torch']=='2.8.0+cu128' and hardware['cuda']=='12.8' and
        len(devices)==len({r['uuid'] for r in devices})==4 and
        all(r['name']=='NVIDIA L4' and r['bf16'] is True for r in devices) and
        read('model-verification.json')['all_ten_files_verified'] is True and
        read('model-verification.json')['model_material_digest']==plan['model_material_digest'] and
        read('source-verification.json')['inventory']==json.loads(raw['source_inventory']),
        'exact native source/model/four-L4 gate differs')
    proofs=[];baselines=[];prefills=[];inference_reserved=0;inference_completed=0;generation_batches=0
    material=json.loads(__import__('gzip').decompress(raw['task_materials_gzip']))
    for attempt,receipt in zip(attempts,receipts):
        prefix='tasks/'+attempt['attempt_id']+'/native/'
        if prefix+'hardware.json' in content:
            require(read(prefix+'hardware.json')['device_uuid']==devices[0]['uuid'],'worker UUID mapping differs')
        p=verify_training(content,prefix,plan['task_specs'][attempt['task_id']],attempt['mode'],plan,material)
        p.update(attempt_id=attempt['attempt_id'],mode=attempt['mode'],process_status=receipt['status'],
            returncode=receipt['returncode'],cache_observed=False,reset_call_observed=False,
            cache_reset_gate=False,result_qualified=False,attempt_gate=False);proofs.append(p)
        if prefix+'result.json' in content:
            r=read(prefix+'result.json');reject_truth(r)
            require(set(r)=={'binding','mode','outcome','failures','training_complete','all_saved_tensors_restored',
                'post_reset_control_verified','optimizer_discarded','worker_wall_seconds','training_wall_seconds',
                'inference_forwards_reserved','inference_forwards_completed','inference_input_tokens_by_phase','tests',
                'contains_evaluator_truth','correctness_scored','teacher_calls','paid_usd'} and
                r['contains_evaluator_truth'] is r['correctness_scored'] is False and
                type(r['teacher_calls']) is type(r['paid_usd']) is int and r['teacher_calls']==r['paid_usd']==0 and
                type(r['worker_wall_seconds']) in (int,float) and math.isfinite(r['worker_wall_seconds']) and
                0<=r['worker_wall_seconds']<=receipt['reserved_seconds'] and
                (r['training_wall_seconds'] is None or type(r['training_wall_seconds']) in (int,float) and
                 math.isfinite(r['training_wall_seconds']) and 0<=r['training_wall_seconds']<=r['worker_wall_seconds']) and
                (r['training_complete'] is not True or r['training_wall_seconds'] is not None),
                'closed bounded truth-free worker result required')
            e=[parse_json(x) for x in content[prefix+'events.jsonl'].splitlines()]
            binding=task_binding(plan,json.loads(raw['challenges']),attempt['task_id']);binding['attempt_id']=attempt['attempt_id']
            _,counts,tokens=check_events(e,binding,plan['task_specs'][attempt['task_id']])
            done={k:sum(x['event']=='forward_completed' and x['phase']==k for x in e) for k in counts}
            require(r['binding']==binding and r['inference_forwards_reserved']==counts and
                    r['inference_forwards_completed']==done and r['inference_input_tokens_by_phase']==tokens and
                    all(type(r[k]) is bool for k in ('training_complete','all_saved_tensors_restored',
                        'post_reset_control_verified','optimizer_discarded')), 'exact worker work/identity/qualification flags required')
            require(r['mode']==attempt['mode'] and r['outcome'] in {'complete','failed','inconclusive'} and
                isinstance(r['failures'],list) and (receipt['status']!='complete' or r['outcome']!='failed'),
                'child failure cannot become parent success')
            controls=verify_controls(content,prefix,e,r)
            p.update(cache_observed=controls['cache_observed'],reset_call_observed=controls['reset_call_observed'],
                cache_reset_gate=controls['complete'],worker_outcome=r['outcome'])
            if controls['cache_observed']:
                baselines.append(controls['baseline']);prefills.append(controls['prefill'])
            normal=(receipt['launched'] and receipt['status']=='complete' and receipt['returncode']==0 and
                r['outcome']=='complete' and r['failures']==[])
            if attempt['mode']=='solve':
                checkpoint=read(prefix+'checkpoint.json') if prefix+'checkpoint.json' in content else None
                p['result_qualified']=(normal and p['training_gate'] and checkpoint is not None and
                    r['tests']==checkpoint['tests'] and len(r['tests'])==plan['task_specs'][attempt['task_id']]['test_count'] and
                    all(t.get('native_complete') is True for t in r['tests']))
            elif attempt['mode']=='baseline-only':
                p['result_qualified']=(normal and r['training_complete'] is False and r['tests']==[] and
                    p['reserved_forwards']==p['reserved_steps']==0 and counts['generation']==counts['verification']==0)
            elif attempt['mode']=='fault-after-two-updates':
                expected_failure=[{'phase':'pipeline','error_type':'RuntimeError',
                    'error_message':'planned isolation fault after two native updates'}]
                p['result_qualified']=(receipt['launched'] and receipt['status']=='failed' and receipt['returncode']==1 and
                    r['outcome']=='failed' and r['failures']==expected_failure and r['training_complete'] is False and
                    r['tests']==[] and p['forwards']==p['reserved_forwards']==p['steps']==p['reserved_steps']==2 and
                    counts['generation']==counts['verification']==0 and
                    read(prefix+'pre-reset-inventory.json')!=read(prefix+'baseline-inventory.json'))
            p['attempt_gate']=p['result_qualified'] and p['cache_reset_gate']
        if prefix+'events.jsonl' in content:
            e=[]
            for line in content[prefix+'events.jsonl'].splitlines(keepends=True):
                if not line.endswith(b'\n'):break
                e.append(parse_json(line))
            inference_reserved+=sum(x['event']=='forward_reserved' for x in e)
            inference_completed+=sum(x['event']=='forward_completed' for x in e)
            generation_batches+=sum(x['event']=='generation_reserved' for x in e)
    require(sum(p['reserved_forwards'] for p in proofs)<=plan['maximum_training_forwards'] and
        sum(p['reserved_steps'] for p in proofs)<=plan['maximum_optimizer_steps'] and
        sum(p['tokens'] for p in proofs)<=plan['maximum_training_tokens'],'session training reservations differ')
    require(terminal['model_forwards']==sum(p['forwards'] for p in proofs)+inference_completed and
        terminal['model_forwards_reserved']==sum(p['reserved_forwards'] for p in proofs)+inference_reserved<=plan['maximum_outer_forwards'] and
        terminal['optimizer_steps']==sum(p['steps'] for p in proofs) and
        terminal['optimizer_steps_reserved']==sum(p['reserved_steps'] for p in proofs) and
        terminal['generations']==generation_batches<=plan['maximum_generations'], 'parent session reserved/completed cost differs')
    challenges=json.loads(raw['challenges'])
    with tempfile.TemporaryDirectory(prefix='iris-native-reader-') as temp:
        directory=Path(temp)
        for name,body in content.items():
            path=directory/name;require(path.resolve().is_relative_to(directory.resolve()),'reader scratch escape')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        from tokenizers import Tokenizer
        tok=Tokenizer.from_file(str(__import__('tools.stage_nvarc_native_multitask',fromlist=['MODEL']).MODEL/'model/tokenizer.json'))
        class Tokens:
            def encode(self,text):return tok.encode(text).ids
            def decode(self,ids):return tok.decode(ids,skip_special_tokens=False)
        evidence=read_task_evidence(directory,plan,challenges,receipts)
        submission,audit=build_native_submission(challenges,plan,evidence,directory,Tokens())
        require(read('native-evidence.json')==evidence and read('submission.json')==submission and
                read('submission-audit.json')==audit,'retained producer/export/audit differs')
    ordinary=proofs[:len(plan['task_order'])]
    nonempty=all(e['checkpoint'] is not None and all(t.get('ranked_grids') for t in e['checkpoint']['tests']) for e in evidence)
    complete_tests=all(e['checkpoint'] is not None and all(t.get('native_complete') for t in e['checkpoint']['tests']) for e in evidence)
    isolation=len(baselines)==len(prefills)==4 and all(b==baselines[0] for b in baselines) and all(p==prefills[0] for p in prefills)
    fault=next((p for p in proofs if p['attempt_id']=='fault-first'),None)
    fault_gate=fault is not None and fault['attempt_gate']
    all_attempts=(len(receipts)==len(attempts)==len(proofs)==4 and all(p['attempt_gate'] for p in proofs))
    parent_finalized=(terminal['outcome']=='failed' and terminal['phase']=='terminal' and
        terminal.get('worker_receipts_digest')==digest(receipts) and 'error' not in terminal)
    proof.update(outcome=terminal['outcome'],gpu_runtime='observed',attempts=proofs,
        nonempty_all_tests=nonempty,complete_all_tests=complete_tests,isolation_baseline_gate=isolation,expected_injected_failure_observed=fault_gate,
        all_expected_attempts_gate=all_attempts,parent_finalization_gate=parent_finalized,
        model_attempt_slots_missing=audit['model_attempt_slots_missing'],task_count=audit['task_count'],
        test_output_count=audit['test_output_count'],submission_sha256=hashlib.sha256(canonical(submission)).hexdigest(),
        gpu_validation_gate=nonempty and complete_tests and isolation and fault_gate and all_attempts and parent_finalized and
            len(ordinary)==2 and all(p['training_gate'] and p['process_status']=='complete' for p in ordinary))
    return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('archive','package','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();require(not args.output.exists(),'new immutable proof required')
    proof=verify(args.archive,args.package);write(args.output,proof);print(json.dumps(proof))
