"""Legacy plain PortfolioTrainer 0/8/16 API regression on real tiny Qwen+PEFT.
No transfer schedule argument is supplied, no remote or public data is used.
"""
from copy import deepcopy
import json,os
from pathlib import Path
import sys,tempfile,time,unittest
HERE=Path(__file__).resolve().parent
SOURCE=Path(os.environ.get('REVIEW_SOURCE',str(HERE.parent/'worktree'))).resolve()
sys.path[:0]=[str(SOURCE),str(SOURCE/'src')]
os.environ.update(CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
import torch
torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
from tools.arc_qwen_portfolio_20261012.backend import create_backend
from tools.arc_learning_agent_20261011.data import create_split_manifest,build_records
from tools.arc_learning_agent_20261011.budget import WorkLedger
from tools.arc_qwen_portfolio_20261012 import checkpoints as cp

class LegacyNative(unittest.TestCase):
    def test_legacy_native_schedule_and_inference(self):
        out=Path(tempfile.mkdtemp(prefix='legacy-native-',dir=HERE));ledger=WorkLedger(out/'physical-work.jsonl')
        tasks={'authored-train':{'train':[{'input':[[1]],'output':[[7]]},{'input':[[2]],'output':[[7]]}]},
               'unused-dev':{'train':[{'input':[[1,2]],'output':[[2,1]]},{'input':[[3,4]],'output':[[4,3]]}]}}
        manifest=create_split_manifest(tasks,fixed_splits={'train':['authored-train'],'dev':['unused-dev']},source_identity={'kind':'authored-legacy-checkpoint-control'})
        records=[r for r in build_records(tasks,manifest,augmentations=1,seed=1917) if r['split']=='train']
        mc={'model_key':'qwen3-14b','tiny_cpu':True,'tokenizer_path':str(SOURCE/'materials/qwen14b/hf-overlay'),'tiny_hidden_size':8,'seed':1917,'do_sample':False}
        tc={'split_manifest':manifest,'seed':1917,'learning_rate':.0002,'stability_mode':True,'accumulation_target_tokens':1024,
            'accumulation_max_microbatches':1,'warmup_steps':4,'schedule_steps':32,'objective_cycle':['grid'],
            'max_supervised_tokens':4000000,'max_input_tokens':16000000}
        model,trainer=create_backend(mc,tc,ledger=ledger);rows=[]
        try:
            for update in (0,8,16):
                if update:
                    train=trainer.train(records,max_steps=8,deadline=time.monotonic()+120)
                    self.assertEqual(train['total_steps'],update)
                saved=cp.save_branch_checkpoint(trainer,out/'checkpoints',branch_id='grid_lora',update=update,records=records)
                manifest_saved=cp.inspect_checkpoint(saved['path'])
                self.assertNotIn('checkpoint_schedule',manifest_saved['binding'])
                self.assertNotIn('update',json.loads((Path(saved['inference_path'])/'adapter_model.safetensors.index.json').read_text()))
                before=deepcopy(ledger.summary())
                loaded=cp.load_branch_checkpoint(trainer,saved['path'],branch_id='grid_lora',records=records,expected_manifest_sha256=saved['manifest_sha256'])
                self.assertEqual(loaded['state_sha256'],saved['state_sha256']);self.assertEqual(before,ledger.summary())
                fresh,inference=create_backend(mc,tc,ledger=ledger)
                try:
                    loaded_inference=cp.load_inference_adapter(inference,saved['inference_path'],branch_id='grid_lora',records=records,
                        expected_inference_manifest_sha256=saved['inference_manifest_sha256'])
                    self.assertEqual(inference.fingerprint(),trainer.fingerprint());self.assertFalse(loaded_inference['optimizer_shards_read'])
                    self.assertEqual(before,ledger.summary())
                finally:fresh.close()
                rows.append({'update':update,'saved':saved,'loaded':loaded,'inference':loaded_inference})
            with self.assertRaises(ValueError):cp.save_branch_checkpoint(trainer,out/'bad64',branch_id='grid_lora',update=64,records=records)
            self.assertEqual(ledger.used['training_steps'],16);self.assertFalse(ledger.pending)
            (HERE/'legacy-native-receipt.json').write_text(json.dumps({'status':'passed','rows':rows,'physical':ledger.summary(),
               'compatibility':'legacy API/artifacts generated with repaired source; historical source-bound bytes remain intentionally incompatible',
               'tiny_random_model_only':True},indent=2)+'\n')
        finally:model.close()

if __name__=='__main__':unittest.main(verbosity=2)
