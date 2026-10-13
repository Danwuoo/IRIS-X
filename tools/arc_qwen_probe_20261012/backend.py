"""Callable reviewed backend with the added probe source closure in state identity."""
from pathlib import Path
from .protocol import file_sha,require
from tools.arc_learning_agent_20261011.qwen14b_training import Qwen14BTrainer
from .decoder import ProbeModel
from tools.arc_learning_agent_20261011.qwen14b_backend import Qwen14BMeteredModel
from tools.arc_learning_agent_20261011.metering import MeteredTrainer

class ProbeTrainer(Qwen14BTrainer):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._clean_preflight_fingerprint=self.fingerprint()

    def freeze_decoder_identity(self, policy):
        require(not self._training_snapshots and self._run_state is None,'decoder freeze requires released preflight state')
        require(self.optimizer is None and self.scheduler is None and all(p.grad is None for p in self.parameters.values()),'decoder freeze requires cleared optimizer/gradients')
        require(self.fingerprint()==self._clean_preflight_fingerprint,'decoder freeze requires exact clean preflight adapter')
        self.native.native.lock_decoder_policy(policy)
        self.config['decoder_policy_sha256']=self.native.native._decoder_policy_sha256
        self._base_identity=self._model_identity()

    def _assert_adapter_recipe(self):
        self.native.assert_decoder_policy()
        if self.native.decoder_policy is not None and 'decoder_policy_sha256' in self.config:
            require(self.config['decoder_policy_sha256']==self.native._decoder_policy_sha256,'training decoder identity differs')
        return super()._assert_adapter_recipe()

    def _source_identity(self):
        result=super()._source_identity()
        root=Path(__file__).resolve().parents[2]
        result.update({p.relative_to(root).as_posix():file_sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))})
        return result

def create_backend(model_config,trainer_config,*,ledger):
    native=ProbeModel.from_config(model_config)
    try:
        model=Qwen14BMeteredModel(native,ledger)
        trainer=ProbeTrainer(model,trainer_config)
        return model,MeteredTrainer(trainer,ledger,max_sequence_tokens=2048)
    except BaseException:
        native.close();raise
