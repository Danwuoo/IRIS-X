"""Independent explicit non-neural full167 public-base reload/branch test."""
from pathlib import Path
from contextlib import contextmanager
import importlib.util,sys,tempfile,time,json,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'worktree'),str(Path(__file__).parent)]
from test_runtime_execution import EchoNative
from tools.arc_qwen_transfer_20261012 import experiment as e
from tools.arc_qwen_transfer_20261012.backend import TransferMeteredModel
from tools.arc_learning_agent_20261011.budget import WorkLedger,atomic_json
spec=importlib.util.spec_from_file_location('authored_public_assets',ROOT/'worktree/tests/test_public_evaluation.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
class PublicBaseOrchestration(unittest.TestCase):
 def test_complete_base_selected_public_reloads_then_returns_selected_sft(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);assets,_,_=f.assets(root);ledger=WorkLedger(root/'ledger.jsonl');calls=[]
   def require(ok,message):
    if not ok:raise ValueError(message)
   class Native(EchoNative):
    active=False
    @contextmanager
    def adapter_branch(self,name):
     require(name=='base' and not self.active,'base branch identity');self.active=True;calls.append('enter-base')
     try:yield
     finally:self.active=False;calls.append('leave-base')
    def generate(self,messages,**kwargs):
     require(self.active,'public base must disable adapter for every generation')
     return super().generate(messages,**kwargs)
   class Session:
    def __init__(self):self.model=TransferMeteredModel(Native(),ledger);self.ledger=ledger
    def reload(self,checkpoint,*args):
     require(not self.model.native.active,'reload must be outside disabled-adapter context')
     calls.append(checkpoint['manifest_sha256'])
   session=Session();base={'manifest_sha256':'a'*64,'adapter_sha256':'b'*64};selected={'manifest_sha256':'c'*64,'adapter_sha256':'d'*64}
   selection={'candidate_id':'base','selection_sha256':'e'*64};(root/'experiment').mkdir();atomic_json(root/'experiment/public-selection.json',selection)
   config={'public_solver_root':assets['solver_root'],'public_solver_manifest_sha256':assets['solver_manifest_sha256']}
   with patch.object(e,'forecast',return_value={}),patch.object(e,'admission',return_value={'admitted':True}):
    result=e.run_public(session,config,selection,base,root/'experiment/public',time.monotonic()+30,{},records=[],provenance={},return_checkpoint=selected)
   self.assertEqual(calls,['a'*64,'enter-base','leave-base','c'*64])
   self.assertEqual(result['method']['role'],'frozen_base');self.assertEqual(result['cases'],167)
   self.assertEqual(ledger.used['generation_calls'],334);self.assertFalse(ledger.pending)
   payload=json.loads(Path(result['artifact_path']).read_bytes());self.assertEqual(len(payload['predictions']),120)
   self.assertEqual(len(payload['case_receipts']),167)
   for case in payload['case_receipts']:self.assertEqual([g['transform_d4'] for g in case['generations']],[0,1])
if __name__=='__main__':unittest.main(verbosity=2)
