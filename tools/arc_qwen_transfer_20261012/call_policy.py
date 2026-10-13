"""Transfer-only generation budget; inherited non-generation windows are unchanged.

The deadline supplied by the owner already includes the global/branch cutoff.
Cleanup is reserved *inside* that deadline, including when little time remains.
"""
import math
import re
import time
from .protocol import digest, require
from tools.arc_learning_agent_20261011.budget import BudgetExceeded

GENERATION_HARD_SECONDS = 180.0
GENERATION_SOFT_SECONDS = 175.0
OTHER_HARD_SECONDS = 120.0
OTHER_SOFT_SECONDS = 115.0


def policy():
    return {'format': 'irisx/transfer-generation-call-policy-v1',
            'generation_hard_seconds': GENERATION_HARD_SECONDS,
            'generation_normal_soft_seconds': GENERATION_SOFT_SECONDS,
            'non_generation_hard_seconds': OTHER_HARD_SECONDS,
            'non_generation_normal_soft_seconds': OTHER_SOFT_SECONDS,
            'cleanup_seconds': 5.0, 'short_remaining_cleanup_fraction': 0.1,
            'deadline_policy': 'min-owner-branch-deadline-and-call-hard-cap'}


def finite_clock(value, name):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            'finite nonnegative ' + name + ' required')
    return value


def generation_window(deadline, *, now=None):
    now = time.monotonic() if now is None else now
    finite_clock(now, 'monotonic start'); finite_clock(deadline, 'branch deadline')
    hard = min(deadline, now + GENERATION_HARD_SECONDS)
    if hard <= now:
        raise BudgetExceeded('no time for new generation work')
    soft = hard - min(5.0, (hard - now) * 0.1)
    return {'call_kind': 'generation', 'call_policy_sha256': digest(policy()),
            'started_monotonic': now, 'branch_deadline_monotonic': deadline,
            'work_deadline_monotonic': soft, 'deadline_monotonic': hard}


def check_active_call(state, *, now, owner_deadline):
    """Fail closed on malformed clocks; a forecast rejection is never a timeout."""
    finite_clock(now, 'watchdog clock'); finite_clock(owner_deadline, 'owner deadline')
    require(type(state) is dict and state.get('status') in ('active', 'closed'),
            'valid active-call state required')
    hard = finite_clock(state.get('deadline_monotonic'), 'call hard deadline')
    work = finite_clock(state.get('work_deadline_monotonic'), 'call work deadline')
    event=state.get('event_id')
    require(type(event) is str and event,'call event identity required')
    require(state.get('call_kind') in (None,'generation'),'unsupported call kind')
    require(work<=owner_deadline,'call work deadline exceeds owner deadline')
    require(hard <= owner_deadline, 'call deadline exceeds owner deadline')
    if state.get('call_kind') == 'generation' or str(state.get('event_id', '')).startswith('qwen14b-generation-'):
        require(re.fullmatch(r'qwen14b-generation-[1-9][0-9]*',event) is not None,
                'exact generation event identity required')
        start = finite_clock(state.get('started_monotonic'), 'call start')
        require(start <= now, 'future call start forbidden')
        expected = generation_window(state.get('branch_deadline_monotonic'), now=start)
        require(all(state.get(k) == v for k, v in expected.items()), 'generation call policy/window differs')
        require(expected['branch_deadline_monotonic'] <= owner_deadline,
                'generation branch exceeds owner deadline')
    else:
        require(not any(k in state for k in ('call_policy_sha256','started_monotonic','branch_deadline_monotonic')),
                'generation policy fields cannot masquerade as a non-generation marker')
        scoring=re.fullmatch(r'qwen14b-c4096-likelihood-[1-9][0-9]*',event) is not None
        calibration=re.fullmatch(r'ladder-(128|512|2048|4096)(-(base|updated|restored)-[a-z0-9-]+)?',event) is not None
        require(scoring or calibration,'unknown transfer native call identity')
        require(work<=hard if scoring else hard<=work,'non-generation work/hard deadline ordering differs')
        # Historical scoring/cache/update markers have no start field. They keep
        # their original 120-second bounds; none can acquire the generation cap.
        if state['status']=='active':
            require(hard <= now + OTHER_HARD_SECONDS, 'non-generation hard cap differs')
    if state['status'] == 'active' and now >= hard:
        raise TimeoutError('owned native call hard deadline reached')
