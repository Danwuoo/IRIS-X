"""Closed end-to-end timing profiles; identity never grants execution authority.

Legacy replay keeps its exact twenty/ten-second allocation. The distinct v7
candidate adopts the inert future budget and requires host forward observation.
"""
from tools.nvarc_e10_future_budget import proposal, validate
from tools.nvarc_native_solve_runtime import require

HISTORICAL = 'historical-v6'
LONGER = 'longer-generation-v7'
HISTORICAL_RUN_ID = 'stage4-e10-probe-end-to-end-20261007-002'
LONGER_RUN_ID = 'stage4-e10-probe-end-to-end-20261007-003'
PROFILES = (HISTORICAL, LONGER)
TIMING_FIELDS = ('generation_seconds', 'verification_reserve_seconds', 'per_test_seconds',
    'inference_reserve_seconds', 'maximum_training_seconds', 'maximum_worker_seconds',
    'startup_seconds', 'reset_reserve_seconds', 'finalization_reserve_seconds',
    'maximum_notebook_wall_seconds')
LEGACY = dict(generation_seconds=20, verification_reserve_seconds=10, per_test_seconds=30,
    inference_reserve_seconds=60, maximum_training_seconds=1800, maximum_worker_seconds=2100,
    startup_seconds=900, reset_reserve_seconds=180, finalization_reserve_seconds=600,
    maximum_notebook_wall_seconds=3600)


def profile(name):
    require(name in PROFILES, 'explicit reviewed end-to-end generation profile required')
    if name == HISTORICAL:
        return dict(profile_id=name, run_id=HISTORICAL_RUN_ID, notebook_version=6,
            previous_version=5, previous_script_version_id=355913407,
            forward_observer_required=False, **LEGACY)
    budget = proposal(); validate(budget)
    return dict(profile_id=name, run_id=LONGER_RUN_ID, notebook_version=7,
        previous_version=6, previous_script_version_id=355924733,
        forward_observer_required=True, **{key:budget[key] for key in TIMING_FIELDS})


def for_plan(plan=None):
    """Return only the profile exactly bound to the caller's reviewed plan.

The absent-plan default exists solely for the historical event replay API.
New-runtime callers always supply their digest-bound plan.
    """
    if plan is None:
        return profile(HISTORICAL)
    require(isinstance(plan, dict), 'bound end-to-end generation plan required')
    if plan.get('format') == 'irisx/stage4-e11-paired-dfs-floor-v1':
        from tools.nvarc_e11_paired_floor import profile_for_plan
        return profile_for_plan(plan)
    if plan.get('format') == 'irisx/stage4-e10-paired-schedule-v1':
        from tools.nvarc_e10_paired_schedule import profile_for_plan
        return profile_for_plan(plan)
    if plan.get('run_id') == LONGER_RUN_ID:
        value = profile(LONGER)
        require(plan.get('screen_id') == LONGER_RUN_ID and
            plan.get('generation_budget_profile') == LONGER and
            plan.get('forward_observer_required') is True and
            type(plan.get('expected_notebook_version')) is int and plan['expected_notebook_version'] == 7 and
            type(plan.get('expected_previous_version')) is int and plan['expected_previous_version'] == 6 and
            type(plan.get('expected_previous_script_version_id')) is int and
            plan['expected_previous_script_version_id'] == 355924733,
            'exact distinct v7 profile, notebook lineage and mandatory observer required')
        validate(plan.get('future_generation_budget'))
    else:
        require(plan.get('run_id') == HISTORICAL_RUN_ID and
            plan.get('generation_budget_profile') in (None, HISTORICAL) and
            plan.get('forward_observer_required') in (None, False),
            'historical replay cannot adopt another identity or generation profile')
        value = profile(HISTORICAL)
    require(all(type(plan.get(key)) is int and plan[key] == value[key] for key in TIMING_FIELDS),
        'exact reviewed generation, verifier, training and resource ceilings required')
    return value
