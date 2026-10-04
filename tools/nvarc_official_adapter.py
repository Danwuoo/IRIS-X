"""Full runtime challenge adapter for the single Stage 3 official score.

No provider or evaluator IO. Public demonstrations alone determine the native
128-row epoch. The runtime challenge identity replaces the visible preview.
"""
from __future__ import annotations
import copy
import math
import time

from tools.nvarc_native_multitask import (digest, require, validate_challenges,
    public_training_material, failure_status)


def allocate(specs, available_seconds):
    """Longest estimated jobs first; every job has a whole epoch and every test.

    The 008 measurement was 955392 tokens in 862 seconds. Reserve 800 tokens/s
    plus 100 seconds per epoch, 120 seconds fresh preparation, 60 seconds reset
    and 180 seconds for EACH test. These are engineering allowances, not a
    promise of throughput. Reject an infeasible input instead of skipping it.
    """
    require(type(available_seconds) in (int, float) and available_seconds > 0,
            'positive remaining four-worker budget required')
    queues=[[] for _ in range(4)];loads=[0.0]*4
    for key in sorted(specs, key=lambda k:(-specs[k]['child_seconds'],k)):
        index=min(range(4), key=lambda n:(loads[n],n))
        specs[key]['selected_gpu_index']=index
        queues[index].append(key);loads[index]+=specs[key]['child_seconds']
    require(max(loads)<=available_seconds,
            'full-input native epochs and test allowances do not fit remaining official runtime')
    return {'queues':queues,'lane_reserved_seconds':loads,'available_seconds':available_seconds,
            'allocation':'LPT by public token/test cost; no answer/difficulty selection',
            'intentionally_skipped_tasks':0}


def runtime_plan(candidate, challenges, loader, tokenizer, available_seconds):
    counts=validate_challenges(challenges)
    materials={key:public_training_material(loader,tokenizer,key,task)
               for key,task in challenges.items()}
    specs={}
    for key, material in materials.items():
        rows=material['rows'];count=counts[key]
        require(len(rows)==128,'complete original 128-step task epoch required')
        tokens=sum(row['input_tokens'] for row in rows)
        training_seconds=100+tokens/800
        inference_seconds=180*count
        child_seconds=math.ceil(120+training_seconds+inference_seconds+60)
        specs[key]={'test_count':count,'training_forwards':128,'optimizer_steps':128,
            'training_input_tokens':tokens,
            'training_supervised_tokens':sum(r['supervised_tokens'] for r in rows),
            'maximum_sequence_tokens':max(r['input_tokens'] for r in rows),
            'expected_rows_digest':digest(rows),'texts_digest':digest(material['texts']),
            'source_learning_rates':candidate['native_source_learning_rates'],
            'inference_forward_limits':{'control':7,'generation':4096*count,'verification':128*count},
            'maximum_inference_input_tokens':5*1024**2*count,
            'maximum_candidate_sequences_per_test':64,
            'per_test_limits':{'generation':4096,'verification':128,'input_tokens':5*1024**2},
            'training_seconds':training_seconds,'inference_seconds':inference_seconds,
            'per_test_seconds':180,'reset_reserve_seconds':60,'preparation_seconds':120,
            'inference_reserve_seconds':inference_seconds,
            'task_seconds':training_seconds+inference_seconds,'child_seconds':child_seconds}
    allocation=allocate(specs,available_seconds)
    plan=copy.deepcopy(candidate)
    plan.update(challenges_digest=digest(challenges),task_order=list(counts),task_specs=specs,
        worker_attempts=[{'attempt_id':key,'task_id':key,'mode':'solve'} for key in counts],
        runtime_input={'tasks':len(counts),'tests':sum(counts.values()),
            'selection':'all actual mounted test challenges, including replacement on hidden rerun',
            'test_answers_opened':False},allocation=allocation,
        maximum_training_forwards=128*len(counts),maximum_optimizer_steps=128*len(counts),
        maximum_training_microsteps=128*len(counts),maximum_generations=4*sum(counts.values()),
        maximum_training_tokens=sum(s['training_input_tokens'] for s in specs.values()),
        maximum_supervised_tokens=sum(s['training_supervised_tokens'] for s in specs.values()),
        maximum_outer_forwards=128*len(counts)+7*len(counts)+4224*sum(counts.values()))
    return plan,materials


def run_all_tests(challenges, task_id, solve, checkpoint, adapter, deadline,
                  per_test_seconds, *, now=time.time):
    """Each actual test gets its own clock, including after a partial search.

    Previous committed tests survive a later exception. Later tests are attempted
    after ordinary local failures; an interrupt preserves the full denominator.
    """
    count=validate_challenges(challenges)[task_id]
    tests=[{'test_index':i,'status':'not_executed','attempts':[],'missing_attempts':2}
           for i in range(count)]
    failures=[]
    for index in range(count):
        adapter.generation_deadline=min(deadline,now()+per_test_seconds)
        try:
            tests[index]=solve(index)
        except BaseException as error:
            tests[index]={'test_index':index,'status':failure_status(error),
                          'attempts':[],'missing_attempts':2}
            failures.append({'test_index':index,'error_type':type(error).__name__,
                             'error_message':str(error)[:1200]})
            checkpoint(tests)
            if not isinstance(error,Exception):break
        else:checkpoint(tests)
    return tests,failures


def receipt_for(task_id):
    return {'task_id':task_id,'attempt_id':task_id,'status':'not_executed',
            'launched':False,'returncode':None,'reset_inferred':False}


def coverage_summary(root,plan,receipts):
    """Count observed coverage and resets, without deriving correctness."""
    import json
    from pathlib import Path
    root=Path(root);rows=[]
    for receipt in receipts:
        key=receipt['task_id'];directory=root/'tasks'/key/'native'
        result=json.loads((directory/'result.json').read_bytes()) if (directory/'result.json').is_file() else {}
        cp=json.loads((directory/'checkpoint.json').read_bytes()) if (directory/'checkpoint.json').is_file() else {}
        started=[]
        if (directory/'events.jsonl').is_file():
            for line in (directory/'events.jsonl').read_bytes().splitlines(keepends=True):
                if not line.endswith(b'\n'):break
                event=json.loads(line)
                if event['event']=='test_started':started.append(event['test_index'])
        rows.append({'task_id':key,'launched':receipt['launched'],'status':receipt['status'],
            'training_complete':result.get('training_complete',False),
            'reset_verified':result.get('all_saved_tensors_restored',False),
            'post_reset_control_verified':result.get('post_reset_control_verified',False),
            'optimizer_discarded':result.get('optimizer_discarded',False),
            'tests_expected':plan['task_specs'][key]['test_count'],
            'tests_started':sorted(set(started)),
            'model_candidates':sum(len(t.get('attempts',[])) for t in cp.get('tests',[]))})
    return {'task_count':len(rows),'test_count':sum(r['tests_expected'] for r in rows),
        'tasks_launched':sum(r['launched'] for r in rows),
        'full_epochs':sum(r['training_complete'] for r in rows),
        'tests_started':sum(len(r['tests_started']) for r in rows),
        'all_resets_verified':all(r['reset_verified'] and r['post_reset_control_verified'] and
                                 r['optimizer_discarded'] for r in rows),
        'rows':rows,'correctness_scored':False,'strict_portable_gpu_gate':False}
