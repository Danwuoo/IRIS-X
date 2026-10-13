"""Same native Qwen/PEFT implementation, additionally bound to portfolio source."""
from pathlib import Path
from tools.arc_qwen_probe_20261012.backend import ProbeTrainer
from tools.arc_qwen_probe_20261012.decoder import ProbeModel
from tools.arc_learning_agent_20261011.qwen14b_backend import Qwen14BMeteredModel
from tools.arc_learning_agent_20261011.metering import MeteredTrainer
from .protocol import file_sha

class PortfolioTrainer(ProbeTrainer):
    def _source_identity(self):
        result=super()._source_identity();root=Path(__file__).resolve().parents[2]
        result.update({p.relative_to(root).as_posix():file_sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))})
        return result

def create_backend(model_config,trainer_config,*,ledger):
    native=ProbeModel.from_config(model_config)
    try:
        model=Qwen14BMeteredModel(native,ledger)
        trainer=PortfolioTrainer(model,trainer_config)
        return model,MeteredTrainer(trainer,ledger,max_sequence_tokens=2048)
    except BaseException:
        native.close();raise
