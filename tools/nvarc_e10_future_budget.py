"""Inert, local-only future generation budget; never stage or admit a RUN.

The frozen v6 allocation/verifier remains unchanged. A future runtime must
separately adopt these validated bounds under a new identity and admission.
"""
from __future__ import annotations
import math

from tools.nvarc_native_solve_runtime import require

PROPOSAL_ID = 'stage4-e10-generation-window-proposal-001'
BOUNDS = dict(generation_seconds=120,verification_reserve_seconds=30,per_test_seconds=150,
    startup_seconds=900,maximum_training_seconds=1200,inference_reserve_seconds=300,
    reset_reserve_seconds=180,finalization_reserve_seconds=600,
    maximum_worker_seconds=2700,maximum_notebook_wall_seconds=3600,
    parallel_workers=4,task_cases=4,test_cases=6,maximum_tests_per_worker=2,
    maximum_training_updates=512,maximum_generation_forwards_per_test=4096,
    maximum_verification_forwards_per_test=128,maximum_inference_input_tokens_per_test=5242880,
    maximum_processed_sequences_per_test=64,maximum_teacher_calls=0,
    maximum_formal_submissions=0,paid_usd_ceiling=0,charged_gpu_seconds_ceiling=14400)


def proposal():
    return dict(BOUNDS,format='irisx/e10-future-generation-budget-proposal-v1',
        proposal_id=PROPOSAL_ID,inert=True,agent_execution_authorized=False,
        publication_authorized=False,official_submission_authorized=False,
        verification_schedule='interleaved',forward_observer_required=True,
        no_automatic_retry=True)


def validate(value):
    expected=proposal()
    require(isinstance(value,dict) and set(value)==set(expected), 'closed inert future budget required')
    require(all(type(value[k]) is type(v) and value[k]==v for k,v in expected.items()),
        'exact inert proposal identity, bounds and authority required')
    require(all(type(value[k]) is int and math.isfinite(value[k]) and value[k]>=0 for k in BOUNDS),
        'finite integer future resource ceilings required')
    require(value['generation_seconds']+value['verification_reserve_seconds']==value['per_test_seconds'],
        'future generation and protected verifier reserve must partition the test ceiling')
    require(value['maximum_tests_per_worker']*value['per_test_seconds']==value['inference_reserve_seconds'],
        'future inference reserve must cover every real test on the busiest worker')
    pipeline=sum(value[k] for k in ('startup_seconds','maximum_training_seconds',
        'inference_reserve_seconds','reset_reserve_seconds'))
    parent=value['maximum_notebook_wall_seconds']-value['finalization_reserve_seconds']
    require(pipeline<=value['maximum_worker_seconds']<=parent and
        pipeline+value['finalization_reserve_seconds']<=value['maximum_notebook_wall_seconds'],
        'coherent future worker, parent, reset and finalization ceilings required')
    require(value['charged_gpu_seconds_ceiling']==value['parallel_workers']*value['maximum_notebook_wall_seconds'],
        'full-session four-GPU quota reservation required')
    return dict(proposal_id=value['proposal_id'],phase_seconds=pipeline+value['finalization_reserve_seconds'],
        notebook_margin_seconds=value['maximum_notebook_wall_seconds']-pipeline-value['finalization_reserve_seconds'],
        worker_phase_seconds=pipeline,worker_margin_seconds=value['maximum_worker_seconds']-pipeline,
        parent_worker_cutoff_seconds=parent,gpu_hours_ceiling=value['charged_gpu_seconds_ceiling']/3600,
        inert=True,execution_admitted=False)
