"""Explicit E13 literal CPU inputs; no historical fixture replacement or truth."""
import copy
import math
from types import SimpleNamespace as NS
from tools import nvarc_e13_admission as admission
from tools import nvarc_e13_runtime as runtime
from tools.nvarc_native_multitask import digest,write
from tests.test_nvarc_e13_run_admission import fixture as admission_fixture
from tests.test_nvarc_e10_probe import FakeTensor as BaseTensor,FakeTorch


def fixture(root):
    plan=admission_fixture(automatic=False)
    (root/'materials').mkdir(exist_ok=True)
    challenges={k:{'train':[{'input':[[1]],'output':[[1]]}],
        'test':[{'input':[[i+1]]} for i in range(n)]} for k,n in runtime.TASK_COUNTS.items()}
    write(root/'challenges.json',challenges);plan['challenges_digest']=digest(challenges)
    plan['owner_editor_admission']=admission.admission(plan)
    return plan


class Tensor(BaseTensor):
    def numel(self):return math.prod(self.shape)


class Array:
    def __init__(self,value):self.value=copy.deepcopy(value)
    def tolist(self):return copy.deepcopy(self.value)


class LiteralEngine:
    """Real adapter/ledger around explicit fake logits and empty native returns."""
    def __init__(self):
        self.clock=100.;self.calls=[];self.fail_after=None;self.deadlines=[];self.scores=[]
        self.torch=FakeTorch();self.tokenizer=NS(encode=lambda _:[10])
        self.model=NS(device='literal-cpu',__class__=None)
        engine=self
        class Model:
            device='literal-cpu'
            def __call__(self,input_ids,**kwargs):
                if engine.fail_after is not None and len(engine.calls)>=engine.fail_after:
                    raise RuntimeError('literal model failure')
                engine.calls.append(dict(ids=input_ids.tolist(),cached=kwargs.get('past_key_values') is not None))
                rows,width=input_ids.shape
                return NS(logits=Tensor([[[0.]*16 for _ in range(width)] for _ in range(rows)]),past_key_values=object())
        self.model=Model();self.loader=NS();self.decoder=NS(score_kgmon=lambda _votes:[])
        def generate(adapter,prefixes,length,max_score,deadline):
            self.deadlines.append(deadline);self.scores.append(max_score)
            adapter(input_ids=Tensor(prefixes),use_cache=True);self.clock+=1.
            return [(0,[])]
        self.solver=NS(inference_turbo_dfs=generate,turbo_dfs=None)
    def now(self):return self.clock
    def views(self,_challenges,key,index,*_args):
        keys=[f'{key}.{index}.{i:02}' for i in range(16)]
        views=NS(keys=keys,get=lambda *_:{'input':'literal'})
        return key,None,views,None,[keys[i:i+4] for i in range(0,16,4)]
