"""Torch-free fixed recipe and deterministic bounded train-only allocation."""
from __future__ import annotations
from collections import Counter
import copy
import hashlib
import math
import random
from tools.arc2_goal_sprint_20261017.data import canonical
from tools.arc2_goal_sprint_20261017.launch import require

PROTOCOL = 'compact-efficient-fusion-v1'
ARMS = ('anchor', 'matched_target_ce', 'routed_fusion')
STRATA = ('all_wrong', 'mixed', 'all_correct')
ROUTES = {'all_wrong': 'known_target_ce', 'mixed': 'exact_centered_ddis',
          'all_correct': 'exact_positive_ce'}
DEFAULT_CONFIG = {'updates': 96, 'seed': 20261018, 'adapter_seed': 731,
    'microbatch': 2, 'context_tokens': 8192, 'generation_tokens': 931,
    'learning_rate': 2e-5, 'training_seconds': 7200, 'group_seconds': 180,
    'max_model_forward_attempts': 131072, 'max_parent_visits': 3,
    'stratum_repeat_slots': 8, 'evaluation_seed': 20261018, 'views': 2, 'ttt_steps': 0}
SELECTION_RULE = ('All declared optimizer slots, three checkpoints and full identical two-view/no-TTT '
    'development panels must complete before selection. Only a unique strict generated-exact pass2 '
    'improvement over the unchanged anchor can select a provisional train-derived candidate. '
    'Any tie, partial work, failed gate, poison or late closure retains anchor. No PUBLIC or NLL selection.')
LOSS_CONTRACT = {'matched_target_ce': 'One mean target-token CE per identical selected prompt, separate persistent fresh AdamW.',
    'routed_fusion': 'All-wrong: known-target CE; all-correct: one deduplicated exact-positive CE; mixed: actual upstream AF3/DDIS.',
    'ddis': 'Eight complete raw trajectories; binary reward minus group mean; sequence-token mean; clip .2/.2; no std normalization, KL, OPSM, entropy masking or DAPO token reduction.',
    'positive_ce': 'Canonical compact targets are unique: eight equal positives collapse to one exact identical CE graph, not novel reasoning traces.',
    'controls': 'Identical prompts and optimizer slots, not equal GPU wall/FLOPs. Collection follows fusion only; no claim to isolate curriculum efficacy or reproduce full RAFT/DAPO/RLVE.'}


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def json_safe_nonfinite(value):
    """Retain every NaN/Inf location/classification, never make it admissible."""
    classified = []
    def visit(item, path):
        if isinstance(item, float) and not math.isfinite(item):
            classified.append({'path': path, 'value': str(item)}); return None
        if isinstance(item, dict): return {key: visit(v, path+[key]) for key, v in item.items()}
        if isinstance(item, list): return [visit(v, path+[i]) for i, v in enumerate(item)]
        return item
    return visit(value, []), classified


def validate_config(config=None):
    cfg = copy.deepcopy(DEFAULT_CONFIG if config is None else config)
    require(type(cfg) is dict and set(cfg) == set(DEFAULT_CONFIG), 'exact fusion config required')
    for key, lower, upper in (('updates', 1, 96), ('seed', 0, 2**63-1), ('adapter_seed', 0, 2**63-1),
            ('microbatch', 1, 8), ('context_tokens', 3, 8192), ('generation_tokens', 1, 931),
            ('max_model_forward_attempts', 1, 131072), ('stratum_repeat_slots', 0, 8),
            ('evaluation_seed', 0, 2**63-1)):
        require(type(cfg[key]) is int and lower <= cfg[key] <= upper, 'bounded ' + key + ' required')
    for key, upper in (('learning_rate', 1e-3), ('training_seconds', 7200), ('group_seconds', 180)):
        require(type(cfg[key]) in (int, float) and math.isfinite(cfg[key]) and 0 < cfg[key] <= upper,
                'finite bounded ' + key + ' required')
    require(cfg['generation_tokens'] < cfg['context_tokens'] and cfg['group_seconds'] <= cfg['training_seconds'],
            'generation/window exceeds enclosing bound')
    require(type(cfg['max_parent_visits']) is int and cfg['max_parent_visits'] == 3
            and type(cfg['views']) is int and cfg['views'] == 2
            and type(cfg['ttt_steps']) is int and cfg['ttt_steps'] == 0, 'fixed visit cap and no-TTT two-view protocol required')
    return cfg


def physical_bounds(cfg=None):
    cfg = validate_config(cfg)
    return {'group_attempts': cfg['updates'], 'rollout_slots': 8 * cfg['updates'],
        'initial_preflight_slots': cfg['microbatch'], 'optimizer_slots_per_updating_arm': cfg['updates'],
        'optimizer_attempts_max': 2 * cfg['updates'], 'max_parent_visits': cfg['max_parent_visits'],
        'model_forward_attempts': cfg['max_model_forward_attempts'], 'training_seconds': cfg['training_seconds'],
        'group_seconds': cfg['group_seconds'], 'failed_partial_and_no_signal_work_charged': True,
        'physical_counters_are_not_measured_flops': True}


def category(rewards):
    require(type(rewards) is list and len(rewards) == 8 and all(type(x) in (int, float) and x in (0, 1) for x in rewards),
            'complete eight binary exact rewards required')
    return 'all_wrong' if not sum(rewards) else 'all_correct' if sum(rewards) == 8 else 'mixed'


class CoverageChooser:
    """Visit every parent once, then feasible stratum floors and mixed priority.

    First-visit strata are measured under the evolving fusion policy, not an
    independent frozen-anchor difficulty estimate. No dev observations enter.
    Missing/cap-exhausted strata reallocate to least-visited exploration; the
    requested/achieved strata and every fallback remain explicit.
    """
    def __init__(self, ids, cfg=None):
        self.cfg = validate_config(cfg)
        self.ids = tuple(sorted(ids)); self.rng = random.Random(self.cfg['seed'])
        require(self.ids and len(set(self.ids)) == len(self.ids), 'unique training IDs required')
        require(len(self.ids) <= self.cfg['updates'] <= len(self.ids) * self.cfg['max_parent_visits'],
                'slots must cover all parents and fit hard visit cap')
        self.order = list(self.ids); self.rng.shuffle(self.order)
        self.stats = {p: {'groups': 0, 'positives': 0, 'first_stratum': None} for p in self.ids}
        self.allocations = []; self.pending = None

    def choose(self):
        require(self.pending is None, 'previous group must be observed before another allocation')
        index = len(self.allocations)
        require(index < self.cfg['updates'], 'finite allocation slots exhausted')
        requested, fallback = None, False
        if index < len(self.ids):
            parent, mode = self.order[index], 'coverage-first'
        else:
            eligible = [p for p in self.ids if self.stats[p]['groups'] < self.cfg['max_parent_visits']]
            require(eligible, 'hard per-parent visit cap exhausted')
            repeat = index - len(self.ids)
            if repeat < 3 * self.cfg['stratum_repeat_slots']:
                requested = STRATA[repeat % 3]
                candidates = [p for p in eligible if self.stats[p]['first_stratum'] == requested]
                fallback = not candidates
                candidates = candidates or eligible
                low = min(self.stats[p]['groups'] for p in candidates)
                parent = self.rng.choice([p for p in candidates if self.stats[p]['groups'] == low])
                mode = 'stratum-floor' if not fallback else 'unavailable-stratum-coverage-fallback'
            else:
                weights = []
                for p in eligible:
                    s = self.stats[p]; probability = (s['positives'] + 1) / (8 * s['groups'] + 2)
                    weights.append(.05 + 4 * probability * (1-probability))
                parent = self.rng.choices(eligible, weights=weights, k=1)[0]
                mode = 'bounded-mixed-priority'
        row = {'slot': index, 'parent_id': parent, 'mode': mode,
               'requested_stratum': requested, 'unavailable_stratum_fallback': fallback,
               'prior_visits': self.stats[parent]['groups'], 'first_stratum': self.stats[parent]['first_stratum']}
        self.pending = row
        return parent, copy.deepcopy(row)

    def observe(self, parent, rewards):
        require(self.pending is not None and parent == self.pending['parent_id'], 'observed parent differs from allocation')
        kind = category(rewards); stats = self.stats[parent]
        stats['groups'] += 1; stats['positives'] += int(sum(rewards))
        if stats['first_stratum'] is None: stats['first_stratum'] = kind
        self.allocations.append({**self.pending, 'observed_stratum': kind})
        self.pending = None
        return kind

    def report(self):
        return {'parents': len(self.ids), 'parents_observed': sum(s['groups'] > 0 for s in self.stats.values()),
            'groups_complete': len(self.allocations), 'stats': copy.deepcopy(self.stats),
            'stratum_floor_requests': dict(Counter(a['requested_stratum'] for a in self.allocations if a['requested_stratum'])),
            'stratum_floor_achieved': dict(Counter(a['requested_stratum'] for a in self.allocations
                if a['requested_stratum'] and not a['unavailable_stratum_fallback'])),
            'unavailable_stratum_fallbacks': sum(a['unavailable_stratum_fallback'] for a in self.allocations),
            'first_visit_strata_are_evolving_policy_measurements': True,
            'curriculum_efficiency_established': False, 'public_or_dev_feedback_used': False}
