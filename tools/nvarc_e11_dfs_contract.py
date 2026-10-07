"""Closed E11 arm contracts. No native imports and no execution authority."""
import math

FORMAT = 'irisx/stage4-e11-paired-dfs-floor-v1'
RUN_ID = 'stage4-e11-probe-paired-dfs-floor-20261007-001'
RUN_ID_45 = 'stage4-e11-probe-paired-dfs-floor-20261007-002'
OWNER_RUN_ID = 'stage4-e11-probe-paired-dfs-floor-20261007-003'
PROFILE = 'paired-dfs-floor-v9'
ALLOCATION = 'irisx/nvarc-dfs-floor-test-allocation-v1'
ARMS = ('p02', 'p01')
FLOORS = {'p02': 0.2, 'p01': 0.1}


def arm_contract(arm_id):
    if type(arm_id) is not str or arm_id not in ARMS:
        raise RuntimeError('explicit closed E11 p02/p01 arm required')
    floor = FLOORS[arm_id]
    return dict(experiment=PROFILE, arm_id=arm_id, schedule='interleaved',
        dfs_probability_floor=floor, dfs_max_score=-math.log(floor))


def validate_binding(binding, arm_id=None):
    """Check exact typed arm/factor/run fields; full plan binding is caller-owned."""
    if type(binding) is not dict:
        raise RuntimeError('exact E11 arm binding required')
    expected = arm_contract(binding.get('arm_id') if arm_id is None else arm_id)
    if binding.get('run_id') not in (RUN_ID,RUN_ID_45,OWNER_RUN_ID) or any(
        type(binding.get(k)) is not type(v) or binding[k] != v for k, v in expected.items()
    ):
        raise RuntimeError('exact E11 arm/floor/max_score/schedule binding differs')
    return expected


def source_max_score(arm_id, allocation):
    """Legacy is p=.2; a treatment needs a separate caller-owned E11 allocation."""
    e11 = isinstance(allocation, dict) and allocation.get('format') == ALLOCATION
    if arm_id is None:
        if e11:
            raise RuntimeError('E11 source call requires its explicit caller arm')
        return -math.log(0.2)
    if not e11:
        raise RuntimeError('E11 source call requires its exact caller allocation')
    return validate_binding(allocation.get('binding'), arm_id)['dfs_max_score']
