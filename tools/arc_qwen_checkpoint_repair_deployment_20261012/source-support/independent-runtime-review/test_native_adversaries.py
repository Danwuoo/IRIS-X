"""Independent native payload/binding adversaries against replayed real checkpoints.
CPU only, authored one-pixel controls, no network/provider/PUBLIC data access.
"""
from copy import deepcopy
import json,os
from pathlib import Path
import sys,tempfile,time,unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
SOURCE=Path(os.environ.get('REVIEW_SOURCE',str(HERE.parent/'worktree'))).resolve()
ARTIFACTS=Path(os.environ.get('REVIEW_NATIVE_ARTIFACTS',str(HERE/'native-replay'))).resolve()
sys.path[:0]=[str(SOURCE),str(SOURCE/'src')]
os.environ.update(CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
import torch
torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
from tools.arc_qwen_transfer_20261012.backend import create_backend
from tools.arc_qwen_transfer_20261012 import model_profile as p
from tools.arc_qwen_transfer_20261012.checkpoint_policy import GLOBAL,TTT,FIXTURE
from tools.arc_learning_agent_20261011.data import create_split_manifest,build_records
from tools.arc_learning_agent_20261011.budget import WorkLedger
from tools.arc_learning_agent_20261011.training import _fingerprint_tree
from tools.arc_qwen_portfolio_20261012 import checkpoints as cp

tasks={'authored-train':{'train':[{'input':[[1]],'output':[[7]]},{'input':[[2]],'output':[[7]]}]},
       'unused-split-only':{'train':[{'input':[[1,2],[3,4]],'output':[[1,2],[3,4]]},{'input':[[5,6],[7,8]],'output':[[5,6],[7,8]]}]}}
manifest=create_split_manifest(tasks,fixed_splits={'train':['authored-train'],'dev':['unused-split-only']},source_identity={'kind':'authored-checkpoint-correctness-control'})
records=[r for r in build_records(tasks,manifest,augmentations=1,seed=1917) if r['split']=='train']

class NativeAdversaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt=json.loads((ARTIFACTS/'receipt.json').read_text());cls.testdir=Path(tempfile.mkdtemp(prefix='native-adversaries-',dir=HERE))
        cls.ledger=WorkLedger(cls.testdir/'physical-work.jsonl')
        cls.model_config={'model_key':p.MODEL_KEY,'profile_id':p.PROFILE_ID,'material_addendum_sha256':p.MATERIAL_ADDENDUM_SHA256,
          'tiny_cpu':True,'tokenizer_path':str(SOURCE/'materials/qwen14b/hf-overlay'),'tiny_hidden_size':8,'seed':1917,'do_sample':False}
        cls.trainer_config=cls.receipt['config']
        cls.model,cls.trainer=create_backend(cls.model_config,cls.trainer_config,ledger=cls.ledger)
        cls.saved=cls.receipt['results'][1]['saved'];cls.checkpoint=Path(cls.saved['path'])
        cp.load_branch_checkpoint(cls.trainer,cls.checkpoint,branch_id='global_grid',records=records,
          expected_manifest_sha256=cls.saved['manifest_sha256'],checkpoint_schedule=GLOBAL)
        cls.raw=cls.trainer.trainer
        cls.handle=cls.raw.snapshot_training_state('independent-valid64')
        cls.payload=deepcopy(cls.raw._training_snapshots[cls.handle['snapshot_id']]['payload'])
        cls.binding=json.loads((cls.checkpoint/'manifest.json').read_text())['binding']
        cls.events=[]
    @classmethod
    def tearDownClass(cls):
        cls.raw.release_training_state(cls.handle);cls.model.close()
        (HERE/'native-adversaries-receipt.json').write_text(json.dumps({'status':'completed','artifact_path':str(ARTIFACTS),
          'tests':cls.events,'physical_ledger':cls.ledger.summary(),'source_root':str(SOURCE)},indent=2)+'\n')
    def tearDown(self):self.events.append(self.id())
    def assert_rejects_payload(self,mutate,pattern=None):
        payload=deepcopy(self.payload);mutate(payload);handle=deepcopy(self.handle)
        handle['state_sha256']=_fingerprint_tree(payload,torch)
        physical=deepcopy(self.ledger.summary());fingerprint=self.raw.fingerprint();names={k:id(v) for k,v in self.raw.parameters.items()}
        with self.assertRaises(ValueError):cp._check_payload(self.raw,payload,handle,self.binding,64,records)
        self.assertEqual(self.ledger.summary(),physical);self.assertEqual(self.raw.fingerprint(),fingerprint)
        self.assertEqual({k:id(v) for k,v in self.raw.parameters.items()},names)
    def test_00_nominal_loaded64_full_state(self):
        self.assertEqual(self.raw._run_state['steps'],64)
        self.assertEqual({int(float(s['step'])) for s in self.raw.optimizer.state.values()},{64})
        self.assertEqual(self.raw.scheduler.last_epoch,64)
        cp._check_payload(self.raw,self.payload,self.handle,self.binding,64,records)
    def test_01_resealed_adam_counter_rejected(self):
        self.assert_rejects_payload(lambda p:next(iter(p['optimizer']['state'].values()))['step'].fill_(63))
    def test_02_resealed_adam_moment_rejected(self):
        self.assert_rejects_payload(lambda p:next(iter(p['optimizer']['state'].values()))['exp_avg_sq'].fill_(-1))
    def test_03_resealed_scheduler_counter_rejected(self):
        self.assert_rejects_payload(lambda p:p['scheduler'].update(last_epoch=63))
    def test_04_resealed_scheduler_lr_rejected(self):
        self.assert_rejects_payload(lambda p:p['optimizer']['param_groups'][0].update(lr=.1))
    def test_05_resealed_scope_rejected(self):
        self.assert_rejects_payload(lambda p:p.update(task_id='foreign-task'))
    def test_06_resealed_rng_rejected(self):
        self.assert_rejects_payload(lambda p:p['rng'].update(torch=torch.tensor([1],dtype=torch.uint8)))
    def test_07_resealed_record_order_rejected(self):
        self.assert_rejects_payload(lambda p:p['run_state'].update(order=[]))
    def test_08_resealed_run_steps_rejected(self):
        self.assert_rejects_payload(lambda p:p['run_state'].update(steps=63))
    def test_09_resealed_scaler_rejected(self):
        self.assert_rejects_payload(lambda p:p.update(scaler={}))
    def test_10_loader_binding_rejections_are_nonmutating(self):
        nominal={'branch_id':'global_grid','records':records,'checkpoint_schedule':GLOBAL}
        cases=[{'checkpoint_schedule':None},{'checkpoint_schedule':FIXTURE},{'checkpoint_schedule':TTT},
          {'branch_id':'representative_ttt'},{'records':records[:-1]},{'provenance':{'changed':True}}]
        for change in cases:
            with self.subTest(change=list(change)):
                physical=deepcopy(self.ledger.summary());fingerprint=self.raw.fingerprint()
                with self.assertRaises(ValueError):cp.load_branch_checkpoint(self.trainer,self.checkpoint,**{**nominal,**change})
                self.assertEqual(self.ledger.summary(),physical);self.assertEqual(self.raw.fingerprint(),fingerprint)
    def test_11_loader_source_mismatch_rejected(self):
        value=self.raw._source_identity();value[next(iter(value))]='0'*64
        with patch.object(self.raw,'_source_identity',return_value=value),self.assertRaises(ValueError):
            cp.load_branch_checkpoint(self.trainer,self.checkpoint,branch_id='global_grid',records=records,checkpoint_schedule=GLOBAL)
    def test_12_inspection_receipt_hash_required_when_supplied(self):
        with self.assertRaises(ValueError):cp.inspect_checkpoint(self.checkpoint,expected_manifest_sha256='0'*64)
    def test_13_no_implicit_new_branch_or_update(self):
        for branch,update,schedule in [('global_grid',65,GLOBAL),('representative_ttt',64,GLOBAL),('global_grid',1,FIXTURE),('global_grid',64,None)]:
            # The fixture1 test has real64 state and must fail claimed-state equality.
            with self.subTest(branch=branch,update=update,schedule=schedule),self.assertRaises(ValueError):
                cp.save_branch_checkpoint(self.trainer,self.testdir/f'rejected-{branch}-{update}-{schedule}',branch_id=branch,update=update,records=records,checkpoint_schedule=schedule)
    def test_14_inference_missing_update_rejected(self):
        import shutil
        copied=self.testdir/'inference-missing-update';shutil.copytree(self.saved['inference_path'],copied)
        index=copied/'adapter_model.safetensors.index.json';value=json.loads(index.read_text());value.pop('update');index.write_text(json.dumps(value))
        model,trainer=create_backend(self.model_config,self.trainer_config,ledger=self.ledger)
        try:
            initial=trainer.fingerprint();physical=deepcopy(self.ledger.summary())
            with self.assertRaises(ValueError):cp.load_inference_adapter(trainer,copied,branch_id='global_grid',records=records,checkpoint_schedule=GLOBAL)
            self.assertEqual(trainer.fingerprint(),initial);self.assertEqual(self.ledger.summary(),physical)
        finally:model.close()

if __name__=='__main__':unittest.main(verbosity=2)
