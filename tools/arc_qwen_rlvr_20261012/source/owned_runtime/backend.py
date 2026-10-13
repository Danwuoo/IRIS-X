"""Exact owned Session bridge; no callbacks or caller model objects admitted."""
from copy import deepcopy
from experiment_flow.native import AuthenticatedBaselineDataset,NativeTinyRewardPanel,NativeSessionAdapter
from experiment_flow.contracts import require,RecoverableWorkError,canonical,digest

class OwnedDataset(AuthenticatedBaselineDataset):
    scope='owned-native-production'
    @classmethod
    def build(cls,config,output):
        from tools.arc_qwen_transfer_20261012.data import build_dataset
        value=build_dataset(config,output)
        require(value.get('cpu_fixture_only') is False,'authenticated production source required')
        return cls(value,cls._construction)

class OwnedRewardPanel:
    scope='owned-native-production'
    def __init__(self,dataset,training_root):
        from rl_session.data import RewardPanel
        require(type(dataset) is OwnedDataset,'owned full dataset required')
        self.panel=RewardPanel(dataset._dataset,training_root=training_root)
        self.parent_ids=tuple(p.parent_id for p in self.panel.prompts)
        self.training_root=training_root
    def receipt(self,successful_exposure):
        exposure=set(successful_exposure)
        rows=[{**row,'exposed_in_same_session_sft256':row['record_id'] in exposure} for row in self.panel.rows]
        return {'scope':'authenticated-training-LOO-rewards-only','panel_sha256':self.panel.panel_sha256,
                'rows':rows,'exact_reward_records_previously_committed':sum(r['exposed_in_same_session_sft256'] for r in rows),
                'denominator':32,'successful_exposure':list(successful_exposure),'seeds_independent_of_exposure':True,
                'historical4_of32_inherited':False,'generalization_measure':False}

class NativeOwnedAdapter(NativeSessionAdapter):
    def __init__(self,session):
        from rl_session.runtime import Session
        from .admission import _REGISTRY
        require(type(session) is Session and session._owned_grant is not None,'source-factory Session required')
        grant=_REGISTRY.get(id(session._owned_grant))
        require(grant is not None and grant['consumed'] and grant['native'] is session.native and grant['trainer'] is session.trainer,'active consumed owned grant')
        self.session=session
        self.scope='native-tiny-CPU-fixture' if session.fixture else 'owned-native-production'
        self._source=deepcopy(session._sources);self._inference_config=deepcopy(session.native.config);self._closure=None
        require(self._inference_config.get('do_sample') is False and self._inference_config.get('temperature')==1. and self._inference_config.get('top_p')==1.,'fixed greedy native inference')
    def bind_training(self,dataset,panel):
        if self.session.fixture:return super().bind_training(dataset,panel)
        require(type(dataset) is OwnedDataset and type(panel) is OwnedRewardPanel,'owned production training bridge')
        dataset.verify();self.dataset=dataset
        self.session.bind_training_data(dataset._dataset,training_root=panel.training_root)
    def sft_step(self,*,deadline):
        if self.session.fixture:return super().sft_step(deadline=deadline)
        try:return self.session.next_sft(deadline=deadline)
        except TimeoutError as exc:
            self.assert_safe();raise RecoverableWorkError(str(exc)) from exc
    def collect(self,panel,*,sweep,max_new_tokens,deadline):
        if self.session.fixture:return super().collect(panel,sweep=sweep,max_new_tokens=max_new_tokens,deadline=deadline)
        require(type(panel) is OwnedRewardPanel,'source-owned reward panel')
        return self.session.collect_batch(panel.panel,batch_index=sweep,max_new_tokens=max_new_tokens,deadline=deadline)
    def set_phase_deadline(self,deadline):
        return self.session.set_phase_deadline(deadline)
    def snapshot(self,label,*,deadline=None):
        return self.session.snapshot(label,deadline=deadline)
    def acknowledge_batch(self,batch,*,status):
        return self.session.acknowledge_batch(batch,status=status)
    def update(self,batch,*,gate_json,deadline):
        if self.session.fixture:return super().update(batch,gate_json=gate_json,deadline=deadline)
        from rl_session.plan import production_numeric_gate
        gate=production_numeric_gate()
        require(canonical(vars(gate))==gate_json,'caller plan cannot replace numeric gate')
        try:return self.session.update(batch,gate=gate,deadline=deadline)
        except Exception as exc:
            if not isinstance(exc,TimeoutError) and getattr(exc,'update_report',None) is None:raise
            self.assert_safe()
            if getattr(exc,'update_report',{}).get('rollback_error'):raise
            error=RecoverableWorkError(str(exc),batch=batch)
            error.update_report=deepcopy(getattr(exc,'update_report',None))
            raise error from exc
