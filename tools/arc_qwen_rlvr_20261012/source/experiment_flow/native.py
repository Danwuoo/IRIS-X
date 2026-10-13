"""Exact owned Session adapter and authenticated frozen-baseline data bridge.

Imports stay lazy so adversarial controller tests need no torch/model resources.
This module cannot construct a production Session or authorize any GPU work.
"""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import json
from .contracts import (require, digest, canonical, file_sha, RecoverableWorkError,
                        FatalStateError)


class AuthenticatedBaselineDataset:
    scope = 'native-tiny-CPU-fixture'
    _construction = object()

    def __init__(self, dataset, token):
        require(token is self._construction, 'use authenticated baseline build factory')
        self._dataset = deepcopy(dataset)
        self._identity = digest(dataset)
        self.plan_sha256 = dataset['plan']['plan_sha256']
        self.opened_scopes = []

    @classmethod
    def build_tiny(cls, output, *, dev_cases=2, holdout_cases=2):
        from tools.arc_qwen_transfer_20261012.data import build_dataset
        from rl_session.data import RewardPanel
        dataset = build_dataset({'tiny_cpu': True}, output)
        panel = RewardPanel(dataset)
        require(all(p.exclusion is None for p in panel.prompts), 'authenticated fixture training source')
        require(1 <= dev_cases <= 16 and 1 <= holdout_cases <= 32, 'bounded explicit native fixture subset')
        dataset['cases'] = [c for scope, count in (('dev',dev_cases),('holdout',holdout_cases))
                            for c in [x for x in dataset['cases'] if x['scope'] == scope][:count]]
        dataset['native_fixture_subset'] = {'selection': 'first fixed metadata order, before outcomes',
                                           'dev': dev_cases, 'holdout': holdout_cases}
        return cls(dataset, cls._construction)

    def verify(self):
        require(digest(self._dataset) == self._identity, 'authenticated dataset changed')

    def cases(self, scope):
        self.verify()
        return tuple(deepcopy(c) for c in self._dataset['cases'] if c['scope'] == scope)

    def bind_evaluator(self, authority):
        from .evaluation import PredictionAuthority
        require(type(authority) is PredictionAuthority and authority.dataset is self and
                not hasattr(self, '_authority'), 'one owned evaluator authority')
        self._authority = authority

    def open_targets(self, scope, seal, *, selection, authority=None):
        self.verify()
        require(authority is not None and authority is getattr(self, '_authority', None), 'registered evaluator required')
        authority.verify_escrow(scope, seal, selection)
        require(scope not in self.opened_scopes, 'escrow opens once per scope')
        if scope == 'holdout':
            require(selection is not None and selection['selected_arm'] in ('A', 'B', 'C') and
                    file_sha(selection['path']) == selection['file_sha256'], 'sealed dev selection before holdout labels')
        from tools.arc_qwen_transfer_20261012.data import open_targets
        values = open_targets(self._dataset, scope, seal)
        self.opened_scopes.append(scope)
        return values


class NativeTinyRewardPanel:
    """The exact existing G2 core smoke fixture, explicitly not train32 ARC."""
    scope = 'native-tiny-CPU-fixture'
    parent_ids = ('fabricated',)

    def __init__(self, dataset):
        require(type(dataset) is AuthenticatedBaselineDataset, 'owned authenticated data')
        from rl_session.data import RewardPanel
        self.authenticated_panel = RewardPanel(dataset._dataset)

    def receipt(self, successful_exposure):
        return {'scope': 'fabricated-G2-core-mechanics-only', 'sample_seeds': [7, 8],
                'training_target': '16', 'anchor_target': '1',
                'actual_reward_parent_count': 1, 'actual_group_size': 2,
                'production_train32_reward_panel_executed': False,
                'authenticated_train32_panel_sha256': self.authenticated_panel.panel_sha256,
                'successful_exposure': list(successful_exposure),
                'seeds_independent_of_exposure': True}


class NativeSessionAdapter:
    scope = 'native-tiny-CPU-fixture'

    def __init__(self, session):
        from rl_session.runtime import Session
        require(type(session) is Session and session.fixture and session.device.type == 'cpu', 'exact tiny CPU Session only')
        self.session = session
        self._source = deepcopy(session._sources)
        self._inference_config = deepcopy(session.native.config)
        require(self._inference_config.get('do_sample') is False and self._inference_config.get('temperature') == 1. and
                self._inference_config.get('top_p') == 1., 'fixed greedy native inference settings')
        self._closure = None

    def sync(self):
        self.session.ledger.sync()

    def assert_safe(self):
        session = self.session
        if self._closure is not None:
            from .evaluation import safe_closure
            safe_closure(self._closure)
            return
        require(session.native.config == self._inference_config, 'inference config drift')
        require(session.fatal_error is None, 'fatal native state: ' + str(session.fatal_error))
        require(all(e.get('status') not in ('reserved', 'unclosed-device-error','unknown') for e in session.ledger.events), 'unsettled native work')
        session._check_live()

    def assert_settled(self):
        if self._closure is not None:
            from .evaluation import safe_closure
            safe_closure(self._closure)
            return
        require(self.session.fatal_error is None and
                all(e.get('status') not in ('started','reserved','unclosed-device-error','unknown') for e in self.session.ledger.events),
                'fatal/unsettled native work')
        require(self.session.native.config == self._inference_config, 'inference config drift')

    def identity(self):
        if getattr(self, '_closure', None) is not None:
            return deepcopy(self._final_identity)
        return self.session.policy_identity()

    def counts(self):
        return deepcopy(self.session.counters)

    def successful_exposure(self):
        return tuple(self.session.sft_exposed)

    def physical_events(self):
        return self.session.ledger.events

    def bind_training(self, dataset, panel):
        require(type(dataset) is AuthenticatedBaselineDataset and type(panel) is NativeTinyRewardPanel, 'owned native fixture bridge')
        dataset.verify()
        # The core smoke fixture deliberately trains fabricated target1. Its
        # trained records are not mislabeled as authenticated ARC exposure.
        self.dataset = dataset

    def sft_step(self, *, deadline):
        try:
            return self.session.fixture_sft(deadline=deadline)
        except TimeoutError as exc:
            self.assert_safe()
            raise RecoverableWorkError(str(exc)) from exc

    def begin(self, kind, *, deadline):
        return self.session.begin_continuation(kind, deadline=deadline)

    def set_phase_deadline(self, deadline):
        return self.session.set_phase_deadline(deadline)

    def snapshot(self, label, *, deadline=None):
        return self.session.snapshot(label, deadline=deadline)

    def restore(self, handle, *, deadline):
        return self.session.restore(handle, deadline=deadline)

    def release_snapshot(self, handle):
        return self.session.release_snapshot(handle)

    def close(self):
        if self._closure is not None:
            return deepcopy(self._closure)
        try:
            self._final_identity = self.identity()
        except Exception:
            self._final_identity = None
        self._closure = self.session.close()
        if self._final_identity is None:
            self._final_identity = self._closure.get('final_policy_identity')
        return deepcopy(self._closure)

    def collect(self, panel, *, sweep, max_new_tokens, deadline):
        require(sweep == 0, 'native G2 core fixture has exactly one fixed sweep')
        return self.session.fixture_group(deadline=deadline)

    def acknowledge_batch(self, batch, *, status):
        return self.session.acknowledge_batch(batch,status=status)

    def update(self, batch, *, gate_json, deadline):
        from rl_session.plan import NumericGate
        gate = NumericGate(**json.loads(gate_json))
        try:
            return self.session.update(batch, gate=gate, deadline=deadline)
        except Exception as exc:
            if not isinstance(exc,TimeoutError) and getattr(exc,'update_report',None) is None:raise
            self.assert_safe()
            if getattr(exc,'update_report',{}).get('rollback_error'):raise
            raise RecoverableWorkError(str(exc),batch=batch,update_report=deepcopy(getattr(exc,'update_report',None))) from exc

    def save(self, path, *, deadline):
        return self.session.save(path, deadline=deadline)

    def reload(self, path, *, deadline):
        return self.session.reload(path, deadline=deadline)

    def predict(self, case, *, transform, seed, max_new_tokens, deadline):
        from tools.arc_qwen_transfer_20261012.data import solver_case, pack_prompt
        from tools.arc_qwen_transfer_20261012.arc_adaptation import Transform
        from tools.arc_learning_agent_20261011.grid_codec import decode_grid
        case = solver_case(case)
        operation = Transform(transform)
        lists = lambda grid: [list(row) for row in grid]
        demos = [{k: lists(operation.apply(d[k])) for k in ('input', 'output')} for d in case['demos']]
        query = lists(operation.apply(case['query_input']))
        self.assert_settled()
        messages, packing = pack_prompt(self.session.native, demos, query, task_id=case['case_id'])
        if messages is None:
            generation = {'dispatched': False, 'valid': False, 'finish_reason': 'context_excluded'}
            status = 'context-excluded'
            self.assert_safe()
            identity = self.identity()
        else:
            generation = self.session.evaluate(messages, seed=seed, max_new_tokens=max_new_tokens, deadline=deadline)
            identity = generation['rl_policy_identity']
            if generation.get('fatal_error') or generation.get('fatal_native_state'):
                raise FatalStateError('native inference reported fatal state')
            status = 'complete' if generation.get('valid') else 'invalid'
            if generation.get('finish_reason') in ('deadline', 'error', 'rejected'):
                status = 'infrastructure-excluded'
        prediction = None
        if generation.get('valid'):
            prediction = lists(operation.inverse().apply(decode_grid(generation['text'])))
        self.assert_settled()
        return {'case_id': case['case_id'], 'transform': transform, 'prediction': prediction,
                'status': status, 'dispatched': generation['dispatched'], 'packing': packing,
                'generation': generation, 'adapter_sha256': identity['adapter_sha256'], 'query_targets_used': False}
