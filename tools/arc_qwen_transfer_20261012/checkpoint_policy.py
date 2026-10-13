"""Closed transfer checkpoint schedules, independent of tiny model dimensions.

A tiny native model may exercise the production schedule; only the explicitly
selected fixture schedule admits updates 1/2. Legacy portfolio callers retain
that module's original <=16 contract. No caller-provided list can raise bounds.
"""
from pathlib import Path
from .protocol import PROTOCOL, digest, file_sha, require

GLOBAL = 'transfer-global-64-256-v1'
FIXTURE = 'transfer-fixture-1-2-v1'
TTT = 'transfer-ttt-0-8-16-v1'


def contract(schedule, branch_id):
    require(schedule in (GLOBAL, FIXTURE, TTT), 'unknown transfer checkpoint schedule')
    require(PROTOCOL['checkpoint_updates'] == [64, 256] and PROTOCOL['ttt_updates'] == [0, 8, 16],
            'transfer checkpoint protocol schedule differs')
    require(branch_id == ('representative_ttt' if schedule == TTT else 'global_grid'),
            'transfer checkpoint schedule/branch differs')
    root = Path(__file__).parent
    return {'format': 'irisx/transfer-checkpoint-schedule-v1', 'schedule_id': schedule,
            'scope': 'task' if schedule == TTT else 'global',
            'allowed_updates': [0, 8, 16] if schedule == TTT else [0, 1, 2] if schedule == FIXTURE else [0, 64, 256],
            'fixture_only': schedule == FIXTURE, 'branch_id': branch_id,
            'protocol_sha256': digest(PROTOCOL),
            'source_sha256': {p.name: file_sha(p) for p in (root/'checkpoint_policy.py', root/'protocol.py')}}


def validate_contract(value, branch_id, update=None):
    require(type(value) is dict and digest(value) == digest(contract(value.get('schedule_id'), branch_id)),
            'source-bound transfer checkpoint schedule differs')
    if update is not None:
        require(type(update) is int and update in value['allowed_updates'],
                'update outside source-bound transfer checkpoint schedule')
    return value


def bind(trainer, schedule, branch_id):
    from .backend import TransferTrainer
    require(isinstance(trainer, TransferTrainer), 'transfer checkpoint schedule requires TransferTrainer')
    value = contract(schedule, branch_id)
    require(schedule != FIXTURE or trainer.config['tiny_cpu'] is True,
            'fixture checkpoint schedule requires explicit tiny CPU trainer')
    return value


def for_run(config):
    updates = config.get('test_checkpoint_updates', [1, 2] if config.get('tiny_cpu') else PROTOCOL['checkpoint_updates'])
    require(type(updates) is list and all(type(u) is int for u in updates), 'exact integer checkpoint update list required')
    if updates == [1, 2]:
        require(config.get('tiny_cpu') is True and config.get('test_fixture_dataset') is True,
                'updates 1/2 require explicit tiny fixture run')
        return FIXTURE
    require(updates == PROTOCOL['checkpoint_updates'], 'closed transfer checkpoint schedule required')
    return GLOBAL
