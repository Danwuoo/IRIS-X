"""Complete source TTT/search/rank runtime over an exact trained export.

Public demonstration outputs may independently probe the verifier. They never
enter the model's candidate pool or count as a solution/correctness observation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import time

from .arc_nvarc_candidates import QwenCandidateBackend, solve_task, candidate_score_limit
from .arc_nvarc_data import visible_task
from .arc_nvarc_representation import verify_model_material
from .arc_nvarc_source_bundle import verify_bundle
from .arc_nvarc_training import TaskLocalAdapter,load_compact_model
from .arc_nvarc_upstream import source_bundle
from .canonical import canonical_bytes,digest_value
from .errors import ValidationError


def complete_config():
    return {'adaptation':{'rank':256,'alpha':32,'seed':42,'use_rslora':True,
        'training_schedule':'source-one-epoch','source_qwen':True,'augmentation_count':16,
        'source_augmentation_seed':1,'max_sequence_length':8192,'learning_rate':5e-5,
        'warmup_ratio':.1,'clip_grad_norm':1.,'maximum_optimizer_steps':128,
        'maximum_training_tokens':1048576,'gradient_checkpointing':True},
        'candidate':{'seed':2,'source_generation_seed':2,'color_repeats':2,
            'maximum_calls_per_task':16,'beams_per_call':2,'maximum_new_tokens':931,
            'source_context_tokens':8192,'dfs_max_expansions':4096,
            'cumulative_probability_threshold':.2,'augmentation':'source-qwen',
            'representation':'source-qwen','ranking':'source-kgmon'}}


def check_plan(plan,config,tasks):
    joint = plan.get('joint_trm')
    maximum_verifications = 42 if joint is not None else 34
    if (plan.get('format')!='irisx/nvarc-complete-ttt-v1' or
            not re.fullmatch(r'nvarc-overnight-ttt-\d{3}',plan.get('run_id','')) or
            plan.get('maximum_paid_usd')!=0 or plan.get('maximum_teacher_calls')!=0 or
            plan.get('config_digest')!=digest_value(config) or plan.get('visible_digest')!=digest_value(tasks) or
            plan.get('maximum_tasks')!=len(tasks) or len(tasks)!=1 or plan.get('maximum_generations')!=16 or
            plan.get('maximum_optimizer_steps')!=128 or plan.get('maximum_verifications')!=maximum_verifications or
            plan.get('maximum_outer_model_forwards')!=66000):
        raise ValidationError('complete source TTT immutable plan differs')
    if config!=complete_config():
        raise ValidationError('complete source rank-256 epoch settings differ')
    if joint is not None:
        from .arc_nvarc_trm_checkpoint import published_model_config
        from .arc_nvarc_trm_runtime import SOURCE_HASHES
        if joint.get('kernel_source'):
            valid_checkpoint=(re.fullmatch(r'danielwuu/nvarc-overnight-trm-\d{3}',joint['kernel_source']) is not None and
                joint.get('kernel_source_version')==1 and joint.get('source_training_steps')==2 and
                joint.get('file')=='trm-ema.pt' and joint.get('checkpoint_format')=='source-ema-unwrapped' and
                'dataset' not in joint and
                all(re.fullmatch(r'[0-9a-f]{64}',joint.get(key,'')) is not None for key in ('checkpoint_sha256','source_terminal_archive_sha256')) and
                all(re.fullmatch(r'sha256:[0-9a-f]{64}',joint.get(key,'')) is not None for key in ('export_material_digest','training_identity_digest')))
        else:
            valid_checkpoint=(joint.get('dataset')=='cpmpml/arc-prize-trm-031/1' and joint.get('file')=='step_220708' and
                joint.get('checkpoint_sha256')=='dbf771737d9799b84faf009c24c5376831f095d2cfd66debbe9a505a445bfc31')
        if (not valid_checkpoint or
                joint.get('source_bundle_digest')!=digest_value(SOURCE_HASHES) or
                joint.get('model_config')!=published_model_config(device_dtype='bfloat16') or
                joint.get('maximum_optimizer_steps')!=1 or joint.get('maximum_views')!=8 or
                joint.get('maximum_act_forwards')!=80 or joint.get('maximum_candidates')!=8 or
                joint.get('joint_verification_state')!='same adapted Qwen state before task reset'):
            raise ValidationError('joint published TRM immutable settings differ')
    candidate=config.get('candidate',{})
    if (candidate.get('augmentation')!='source-qwen' or candidate.get('representation')!='source-qwen' or
            candidate.get('ranking')!='source-kgmon' or candidate.get('maximum_calls_per_task')!=16 or
            candidate.get('maximum_new_tokens')!=931 or candidate.get('source_context_tokens')!=8192 or
            candidate.get('dfs_max_expansions')!=4096 or candidate.get('cumulative_probability_threshold')!=.2 or
            candidate.get('beams_per_call')!=2 or candidate.get('color_repeats')!=2 or
            any(key in candidate for key in ('token_probability_floor','required_shape','required_colors'))):
        raise ValidationError('source DFS/ranking factors differ')
    if any(len(task['test'])!=1 or len(task['train'])<2 or 'output' in task['test'][0] for task in tasks):
        raise ValidationError('one truth-free visible test and public demos required')
    if plan.get('backend')=='cuda-l4':
        if plan.get('approved') is not True or plan.get('owner_decision')!='Decision 0053':
            raise ValidationError('free Kaggle Goal authority required')
    elif plan.get('backend')!='cpu-fixture':
        raise ValidationError('complete source TTT backend differs')


def run(plan_path:Path,model_path:Path,visible_path:Path,config_path:Path,bundle:Path,output:Path,
        *,trm_result_path:Path|None=None):
    import torch
    from peft import get_peft_model_state_dict
    plan=json.loads(plan_path.read_bytes());config=json.loads(config_path.read_bytes())
    raw=json.loads(visible_path.read_bytes())
    if not isinstance(raw,dict) or any(set(item)!= {'input'} for task in raw.values() for item in task.get('test',[])):
        raise ValidationError('runtime visible bytes cannot contain test answers')
    tasks=[visible_task(key,value) for key,value in sorted(raw.items())]
    check_plan(plan,config,tasks)
    joint=None
    if plan.get('joint_trm') is not None:
        from .arc_nvarc_trm_runtime import verify_joint_trm_result
        if trm_result_path is None:raise ValidationError('joint TRM result required before Qwen work')
        joint=json.loads(trm_result_path.read_bytes())
        verify_joint_trm_result(plan,joint)
    elif trm_result_path is not None:
        raise ValidationError('unplanned TRM result forbidden')
    material=verify_model_material(model_path,plan['material_digest'])
    if material.get('training_identity_digest')!=plan['training_identity_digest']:
        raise ValidationError('complete TTT export training binding differs')
    verify_bundle(bundle,plan['source_bundle_digest'])
    if output.exists():raise ValidationError('complete TTT output must be new')
    output.mkdir(parents=True)
    started=time.monotonic()
    ledger={'outer_model_forwards_reserved':0,'generation_calls_reserved':0,'generation_calls_completed':0,
        'ttt_optimizer_steps_observed':0,'verification_calls_reserved':0,'verification_calls_completed':0,
        'maximum_outer_model_forwards':66000,'phase':'model-load'}
    def emit(event,**details):
        with (output/'events.jsonl').open('ab') as stream:
            stream.write(canonical_bytes({'event':event,'elapsed_seconds':time.monotonic()-started,**details},newline=True))
            stream.flush()
    def forward_observer(module,args):
        if ledger['outer_model_forwards_reserved']>=66000:
            raise ValidationError('complete TTT outer model forward ceiling reached')
        ledger['outer_model_forwards_reserved']+=1
    def generation_observer(event):
        kind,status=event['kind'],event['status']
        if kind=='generation':
            if status=='reserved':
                if ledger['generation_calls_reserved']>=16:raise ValidationError('source generation call ceiling reached')
                ledger['generation_calls_reserved']+=1
            else:ledger['generation_calls_completed']+=1
        elif kind=='verification':
            if status=='reserved':
                if ledger['verification_calls_reserved']>=plan['maximum_verifications']-2:raise ValidationError('model candidate verification ceiling reached')
                ledger['verification_calls_reserved']+=1
            else:ledger['verification_calls_completed']+=1
        else:raise ValidationError('source call observer kind differs')
        emit(kind+'-'+status,details=event)
    def step_observer(event):
        ledger['ttt_optimizer_steps_observed']=event['completed_steps']
        emit('ttt-optimizer-returned',**event)
    hook=None
    model=adapter=None
    try:
        with source_bundle(bundle,plan['source_bundle_digest']):
            gpu=plan['backend']=='cuda-l4'
            if gpu and not torch.cuda.is_available():raise ValidationError('CUDA required for complete TTT port probe')
            model=load_compact_model(model_path,dtype='bfloat16' if gpu else 'float32')
            if gpu:model.to(torch.device('cuda',0))
            hook=model.register_forward_pre_hook(forward_observer)
            adapter=TaskLocalAdapter(model,config['adaptation'],step_observer=step_observer)
            class ObservedBackend(QwenCandidateBackend):
                def begin_task(self,task):
                    ledger['phase']='complete-source-epoch'
                    emit(ledger['phase'])
                    super().begin_task(task)
                    ledger['ttt_optimizer_steps_observed']=self.adapter.last_observation['steps']
                    emit('complete-source-epoch-returned',observation=self.adapter.last_observation)
                    ledger['phase']='eight-view-demonstration-probes'
                    self.probes=[]
                    self.augmentation='source-qwen';self.representation='source-qwen'
                    self.source_context_length=8192;self.source_reply_reserve=931
                    for index,pair in enumerate(task['train'][:2]):
                        score=self.verify(task,0,pair['output'])
                        if not math.isfinite(score):raise ValidationError('public demonstration verifier score nonfinite')
                        self.probes.append({'provenance':'public-demonstration-output','demo_index':index,
                            'grid_digest':digest_value(pair['output']),'eight_view_nll_sum_mean':score,
                            'model_candidate':False,'correctness_scored':False})
                    ledger['phase']='source-dfs-and-model-candidate-ranking'
                    emit(ledger['phase'])
            backend=ObservedBackend(model,task_adapter=adapter,dfs_max_score=candidate_score_limit(config['candidate']),dfs_max_expansions=4096)
            if joint is not None:
                backend.supplemental_candidates=lambda task,test_index:joint['candidates']
            # Configuration is also applied by solve_task before begin_task.
            results=solve_task(tasks[0],backend,config['candidate'],call_observer=generation_observer)
            observed_generations=sum(len(row['generation_observations']) for row in results)
            observation=adapter.last_observation
            if (observation['steps']!=128 or not observation['complete_epoch'] or
                    ledger['generation_calls_reserved']!=16 or ledger['generation_calls_completed']!=16 or
                    observed_generations!=16 or backend.verification_calls>plan['maximum_verifications']):
                raise ValidationError('complete TTT returned workload differs')
            reset_equal=all(torch.equal(value.detach().cpu(),adapter.initial[name])
                for name,value in get_peft_model_state_dict(adapter.model).items())
            if not reset_equal:raise ValidationError('complete TTT task adapter did not reset exactly')
            result={'format':'irisx/nvarc-complete-ttt-result-v1','run_id':plan['run_id'],
                'plan_digest':digest_value(plan),'config_digest':digest_value(config),'material_digest':plan['material_digest'],
                'training_identity_digest':plan['training_identity_digest'],'source_bundle_digest':plan['source_bundle_digest'],
                'ttt':observation,'ledger':ledger,'results':results,'demonstration_verifier_probes':backend.probes,
                'candidate_verification_calls':backend.verification_calls-2,'demonstration_probe_calls':2,
                'explicit_inference_forwards':backend.forward_calls,'adapter_reset_exact':True,
                'contains_evaluator_truth':False,'correctness_scored':False,'full_scale_sft_verified':False,
                'original_qwen3_unsloth_parity':False,'wall_seconds':time.monotonic()-started}
            if joint is not None:
                result['joint_trm']={'result_digest':digest_value(joint),
                    'raw_candidates':len(joint['candidates']),'supplemental_sequences':results[0]['supplemental_sequences'],
                    'verification_state':plan['joint_trm']['joint_verification_state'],
                    'published_checkpoint_sha256':plan['joint_trm']['checkpoint_sha256']}
            (output/'result.json').write_bytes(canonical_bytes(result,newline=True))
            emit('complete',outer_model_forwards=ledger['outer_model_forwards_reserved'])
            return result
    except BaseException as error:
        failure={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'ledger':ledger,
            'error_type':type(error).__name__,'error_message':str(error)[:1200],
            'ttt':None if adapter is None else adapter.last_observation,'contains_evaluator_truth':False}
        (output/'failure.json').write_bytes(canonical_bytes(failure,newline=True))
        raise
    finally:
        if hook is not None:hook.remove()
        if adapter is not None:adapter.reset(clear_observation=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('plan','model','visible','config','bundle','output'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--trm-result',type=Path)
    args=parser.parse_args()
    run(args.plan,args.model,args.visible,args.config,args.bundle,args.output,trm_result_path=args.trm_result)
