"""Independently reconcile saved inputs, terminal ledgers and exported tensors.

This command makes no provider/model calls and never scores test answers.
Checkpoint manifests bind ephemeral optimizer bytes; their bytes are not
pretended to be retained after the Kaggle session.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_datasets import sha_file
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError


def require(condition,message):
    if not condition:raise ValidationError(message)


def closed_archive(folder,run):
    package=folder/'package-l4';journal=folder/'execution-final'
    ledger=json.loads((journal/'execution-ledger.json').read_bytes())
    event=ledger['events'][-1]
    require(ledger['accepted'] and ledger['provider_version']==1 and ledger['retrieval_reserved']==1 and
        event['action']=='terminal-output' and event['outcome']=='retrieved','sole terminal retrieval required')
    require(sha_file(journal/'save-request.json')==ledger['request_sha256'],'saved provider request differs')
    actual={p.relative_to(package).as_posix():sha_file(p) for p in package.rglob('*') if p.is_file() and p.name!='stage-summary.json'}
    require(actual==ledger['bindings']['inventory'],'saved closed package differs')
    plan=json.loads((package/'plan.json').read_bytes())
    summary=json.loads((package/'stage-summary.json').read_bytes())
    archive_path=journal/'retrieved/gpu-preflight-result.zip'
    require(sha_file(archive_path)==event['retained_inventory']['gpu-preflight-result.zip'],'retained terminal archive differs')
    with zipfile.ZipFile(archive_path) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        require(manifest['run_id']==run and manifest['plan_digest']==digest_value(plan)==ledger['bindings']['plan_digest'],'archive plan binding differs')
        names=[item['path'] for item in manifest['members']]
        require(len(names)==len(set(names)) and len(archive.namelist())==len(names)+1 and
            set(archive.namelist())==set(names)|{'manifest.json'},'archive closed member inventory differs')
        data={}
        for item in manifest['members']:
            name=item['path']
            require('\\' not in name and ':' not in name and not any(x in {'','.','..'} for x in name.split('/')),'unsafe archive name')
            raw=archive.read(name)
            require(len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'],'archive member digest differs')
            data[name]=raw
    require(json.loads(data['plan.json'])==plan and json.loads(data['payload-bindings.json'])==summary['payload_sha256'],'returned payload binding differs')
    return plan,event,data,sha_file(archive_path)


def verify_export_tensors(model,expected):
    import torch
    from safetensors import safe_open
    seen={}
    for path in sorted(model.glob('*.safetensors')):
        with safe_open(path,framework='pt',device='cpu') as archive:
            for name in archive.keys():
                require(name not in seen and name in expected,'export tensor name differs')
                tensor=archive.get_tensor(name)
                value=tensor.contiguous().reshape(-1).view(torch.uint8).numpy()
                seen[name]={'shape':list(tensor.shape),'dtype':str(tensor.dtype),
                    'sha256':hashlib.sha256(memoryview(value).cast('B')).hexdigest()}
                del value,tensor
    material=json.loads((model/'material-manifest.json').read_bytes())
    if material['tied_embeddings'] and 'lm_head.weight' not in seen:
        require(expected.get('lm_head.weight')==seen.get('model.language_model.embed_tokens.weight'),'tied export alias differs')
        seen['lm_head.weight']=seen['model.language_model.embed_tokens.weight']
    require(seen==expected,'independent exact exported tensor bytes differ')
    return len(seen)


def verify_sft(folder,plan,event,data):
    from irisx.arc_nvarc_representation import verify_model_material
    rows=json.loads((folder/'package-l4/samples.json').read_bytes())
    require(digest_value(rows)==plan['data_digest'],'frozen input rows differ')
    identity=digest_value({'plan':plan,'source_stream_identity':digest_value({'kind':plan['data_kind'],'rows_digest':plan['data_digest']})})
    pause=json.loads(data['worker/pause-result.json']);final=json.loads(data['worker/final-result.json'])
    chain=json.loads(data['worker/export-chain.json'])
    batch=plan['global_batch_size'];world=plan['world_size'];steps=plan['maximum_optimizer_steps']
    require(steps==2 and len(rows)==batch*steps,'bounded two-step schedule differs')
    require(pause['step']==1 and final['step']==2 and final['restored_fingerprint']==pause['weight_fingerprint_after'],'process restart fingerprint differs')
    require(pause['weight_fingerprint_after']!=pause['weight_fingerprint_before'] and final['weight_fingerprint_after']!=final['restored_fingerprint'],'optimizer weight change differs')
    uuids=set();peak_allocated=[];peak_reserved=[];microseconds=[]
    for result in (pause,final):
        step=result['step'];prefix=rows[:step*batch]
        supervised=sum(sum(label!=-100 for label in row['labels'][1:]) for row in prefix)
        tokens=sum(len(row['input_ids']) for row in prefix)
        require(result['identity_digest']==identity and result['plan_digest']==digest_value(plan),'returned runtime identity differs')
        require((result['cursor'],result['input_tokens'],result['supervised_tokens'],result['forwards'])==(step*batch,tokens,supervised,step*batch),'whole input/label/cursor ledger differs')
        checkpoint=json.loads(data[f'worker/checkpoint-{step}-manifest.json'])
        require(digest_value(checkpoint)==result['checkpoint']['manifest_digest'] and checkpoint['state']['identity_digest']==identity,'checkpoint inventory binding differs')
        require(checkpoint['state']['cursor']==step*batch and checkpoint['state']['weight_fingerprint_after']==result['weight_fingerprint_after'],'checkpoint cursor/weight state differs')
        require(len(result['observations'])==1 and len(result['observations'][0])==world,'rank observation coverage differs')
        observations=result['observations'][0]
        selected=rows[(step-1)*batch:step*batch]
        global_supervised=sum(sum(label!=-100 for label in row['labels'][1:]) for row in selected)
        for rank,observation in enumerate(observations):
            lineage=[{key:value for key,value in row.items() if key not in {'input_ids','labels'}} for row in selected[rank::world]]
            require(observation['rank']==rank and observation['step']==step and observation['source_lineage']==lineage,'rank input lineage differs')
            require(observation['real_forward_calls']==len(lineage) and observation['dummy_forward_calls']==0 and
                observation['collective_slots']==batch//world and observation['global_sequence_count']==batch,'rank accumulation slots differ')
            require(observation['global_input_tokens']==sum(len(row['input_ids']) for row in selected) and
                observation['global_supervised_tokens']==global_supervised,'global normalization token count differs')
            require(math.isfinite(observation['global_token_mean_loss']) and observation['finite_nonzero_shards']>0 and
                math.isfinite(observation['gradient_norm_before_clip']) and observation['cpu_accumulation_bytes']>0,'finite gradient observation differs')
            require(observation['checkpointed_layers']==32 and observation['hardware']['name']=='NVIDIA L4','decoder/hardware gate differs')
            uuids.add(observation['hardware']['device_uuid'])
            memory=observation['state_residency']
            for key in ('parameter_bytes','gradient_bytes','optimizer_bytes'):
                require(all(name=='cpu/torch.float32' for name in memory[key]),'FP32 CPU residency differs')
            peak_allocated.append(memory['cuda_peak_allocated_bytes']);peak_reserved.append(memory['cuda_peak_reserved_bytes'])
            microseconds.append(observation['wall_seconds'])
        require(len({item['global_token_mean_loss'] for item in observations})==1,'rank global token-mean loss differs')
    require(len(uuids)==4 and chain['identity_digest']==identity and chain['checkpoint_manifest_digest']==final['checkpoint']['manifest_digest'],'four-rank export chain differs')
    require(chain['reload_tensor_bytes_identical'] and chain['fp32_saved_fingerprint']==final['weight_fingerprint_after'],'checkpoint/export fingerprint differs')
    require(all(abs(a-b)<=1e-9*max(1.,abs(b)) for a,b in zip(chain['fp32_consolidated_fingerprint'],chain['fp32_saved_fingerprint'])),'FP32 consolidation differs')
    model=folder/'execution-final/retrieved/export'
    material=verify_model_material(model,chain['export_material_digest'])
    require(material['training_identity_digest']==identity and event['export_verified'] and event['export_material_digest']==chain['export_material_digest'],'retained export identity differs')
    tensor_count=verify_export_tensors(model,chain['export_tensor_inventory'])
    return {'optimizer_steps':steps,'global_batch_size':batch,'input_tokens':final['input_tokens'],
        'supervised_tokens':final['supervised_tokens'],'whole_sequences':len(rows),'maximum_sequence_length':max(len(row['input_ids']) for row in rows),
        'rank_count':4,'distinct_l4_uuids':sorted(uuids),'accumulation_microsteps_per_rank_per_step':batch//world,
        'process_restart_fingerprint_exact':True,'finite_token_mean_and_gradients':True,
        'export_material_digest':chain['export_material_digest'],'training_identity_digest':identity,
        'export_state_tensor_count':tensor_count,'independent_export_tensor_bytes_verified':True,
        'cuda_peak_allocated_bytes_range':[min(peak_allocated),max(peak_allocated)],
        'cuda_peak_reserved_bytes_range':[min(peak_reserved),max(peak_reserved)],
        'rank_step_seconds_range':[min(microseconds),max(microseconds)],
        'optimizer_checkpoint_bytes_retained':False,'full_sft_completed':False,'original_qwen3_nemo_parity':False}


def verify_ttt(folder,plan,data):
    from irisx.arc_nvarc_data import visible_task
    from irisx.arc_nvarc_source_bundle import verify_bundle
    from irisx.arc_nvarc_training import task_local_sequences
    from irisx.arc_nvarc_upstream import source_bundle
    result=json.loads(data['worker/result.json']);ttt=result['ttt'];ledger=result['ledger']
    require(result['plan_digest']==digest_value(plan) and result['material_digest']==plan['material_digest'] and
        result['training_identity_digest']==plan['training_identity_digest'],'complete TTT training identity differs')
    raw=json.loads((folder/'package-l4/visible.json').read_bytes())
    require(all(set(item)=={'input'} for task in raw.values() for item in task['test']),'visible test answer present')
    tasks=[visible_task(key,value) for key,value in sorted(raw.items())]
    require(digest_value(tasks)==plan['visible_digest'] and len(tasks)==1,'complete TTT public input binding differs')
    bundle=folder/'package-l4/source-bundle';verify_bundle(bundle,plan['source_bundle_digest'])
    with source_bundle(bundle,plan['source_bundle_digest']):
        rows=task_local_sequences(tasks[0],seed=42,augmentation_count=16,source_qwen=True,
            source_augmentation_seed=1,source_max_length=8192)
    require(ttt['status']=='complete' and ttt['steps']==128 and ttt['source_view_count']==128 and ttt['complete_epoch'] and
        sorted(ttt['consumed_view_indices'])==list(range(128)),'complete source epoch consumption differs')
    require(ttt['training_tokens']==plan['source_epoch_input_tokens']==sum(len(row['input_ids']) for row in rows) and
        ttt['source_sequence_keys']==[row['source'] for row in rows],'source TTT sequence/token ledger differs')
    require(all(math.isfinite(value) for value in ttt['losses_by_step']) and len(ttt['losses_by_step'])==128 and
        all(all(group[key]>0 for key in ('attention','delta','embedding','head')) for group in ttt['gradient_groups_by_step']),
        'full-epoch finite loss/gradient coverage differs')
    require(ledger['ttt_optimizer_steps_observed']==128 and ledger['generation_calls_reserved']==ledger['generation_calls_completed']==16 and
        ledger['verification_calls_reserved']==ledger['verification_calls_completed']==result['candidate_verification_calls']<=plan['maximum_verifications']-2,
        'generation/verification reserved-completed ledger differs')
    require(result['adapter_reset_exact'] and result['demonstration_probe_calls']==2 and
        len(result['demonstration_verifier_probes'])==2 and all(not item['model_candidate'] and not item['correctness_scored']
        for item in result['demonstration_verifier_probes']),'task reset/demonstration separation differs')
    calls=result['results'][0]
    require(len(result['results'])==1 and len(calls['generation_observations'])==16 and
        calls['generation_calls_so_far']==16 and calls['verification_calls_so_far']==len(calls['ranked'])==result['candidate_verification_calls'],
        'source model candidate pool differs')
    require(calls['attempts']==[item['grid'] for item in calls['ranked'][:2]] and calls['missing_attempts']==2-len(calls['attempts']),
        'selected top-two candidates differ')
    supplemental=calls.get('supplemental_sequences',0)
    require(calls['returned_sequences']+supplemental==sum(item['votes'] for item in calls['ranked'])+sum(calls['parse_rejections'].values()),
        'candidate parse and vote ledger differs')
    joint_proof=None
    if plan.get('joint_trm') is not None:
        from irisx.arc_nvarc_trm_runtime import verify_joint_trm_result
        trm=json.loads(data['trm-worker/result.json'])
        joint_proof=verify_joint_trm_result(plan,trm)
        require(result['joint_trm']['result_digest']==digest_value(trm) and
            result['joint_trm']['raw_candidates']==supplemental==len(trm['candidates']) and
            result['joint_trm']['verification_state']==plan['joint_trm']['joint_verification_state'],
            'joint TRM result/pool bindings differ')
        reconstructed={}
        for item in calls['ranked']:
            require(item['votes']==len(item['sources']) and all(source.startswith(('qwen:','trm:')) for source in item['sources']),
                'joint model vote provenance differs')
            for source in item['sources']:
                if source.startswith('trm:'):
                    require(source not in reconstructed,'joint TRM view counted twice')
                    reconstructed[source]=item['grid']
        require(reconstructed=={'trm:'+item['source']:item['grid'] for item in trm['candidates']},
            'joint TRM inverse-mapped model views differ')
        with source_bundle(bundle,plan['source_bundle_digest']):
            from irisx.arc_nvarc_upstream import qwen_cell
            getter=qwen_cell('arc_decoder.py').getter_kgmon
            for item in calls['ranked']:
                score=float(getter([{'score_aug':[item['mean_verification_nll']]}]*item['votes']))
                require(math.isclose(score,item['score'],rel_tol=1e-9,abs_tol=1e-9),'joint source ranking differs')
        trm_events=[json.loads(line) for line in data['trm-worker/events.jsonl'].splitlines()]
        require(len([item for item in trm_events if item['event']=='optimizer-complete'])==1 and
            len([item for item in trm_events if item['event']=='view-complete'])==8,
            'joint TRM returned workload events differ')
    else:
        require(supplemental==0,'unplanned supplemental candidates present')
    events=[json.loads(line) for line in data['worker/events.jsonl'].splitlines()]
    steps=[item for item in events if item['event']=='ttt-optimizer-returned']
    require(len(steps)==128 and [item['completed_steps'] for item in steps]==list(range(1,129)),
        'actual optimizer-returned event coverage differs')
    require(ledger['outer_model_forwards_reserved']==128+result['explicit_inference_forwards']<=66000,
        'independent model forward ledger differs')
    require(not result['contains_evaluator_truth'] and not result['correctness_scored'] and not result['original_qwen3_unsloth_parity'],
        'unearned correctness/parity claim present')
    return {'optimizer_steps':128,'source_epoch_training_tokens':ttt['training_tokens'],
        'generation_calls':16,'candidate_verification_calls':result['candidate_verification_calls'],
        'public_demonstration_probe_calls':2,'public_probes_in_candidate_pool':False,
        'unique_model_candidates':len(calls['ranked']),'selected_attempts':len(calls['attempts']),
        'outer_model_forwards':ledger['outer_model_forwards_reserved'],'adapter_reset_exact':True,
        'cuda_peak_allocated_bytes':ttt['peak_cuda_allocated_bytes'],
        'cuda_peak_reserved_bytes':ttt['peak_cuda_reserved_bytes'],
        'trainable_parameter_count':ttt['trainable_parameter_count'],
        'full_scale_sft_verified':False,'original_qwen3_unsloth_parity':False,
        'joint_trm':joint_proof}


def verify(run):
    require(re.fullmatch(r'nvarc-overnight-(?:sft|ttt)-\d{3}',run),'exact Goal run identity required')
    folder=ROOT/'.irisx/nvarc-original/runs'/run
    plan,event,data,archive_sha=closed_archive(folder,run)
    terminal=json.loads(data['terminal.json'])
    report={'format':'irisx/nvarc-overnight-independent-verification-v1','run_id':run,
        'plan_digest':digest_value(plan),'archive_sha256':archive_sha,'closed_archive_verified':True,
        'terminal':terminal,'external_calls':0,'model_calls':0,'contains_evaluator_truth':False,'correctness_scored':False}
    if terminal['outcome']=='complete' and plan['format']=='irisx/nvarc-source-sft-v1':
        report['runtime']=verify_sft(folder,plan,event,data)
    elif terminal['outcome']=='complete' and plan['format']=='irisx/nvarc-complete-ttt-v1':
        report['runtime']=verify_ttt(folder,plan,data)
    elif terminal['outcome']=='failed':
        report['claim']='digest-bound failure only; no absent runtime work is inferred'
    else:
        raise ValidationError('terminal kind needs its separate independent verifier')
    output=folder/'independent-terminal-verification.json'
    require(not output.exists(),'independent terminal record is immutable')
    output.write_bytes(canonical_bytes(report,newline=True))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True)
    print(json.dumps(verify(parser.parse_args().run),indent=2))
