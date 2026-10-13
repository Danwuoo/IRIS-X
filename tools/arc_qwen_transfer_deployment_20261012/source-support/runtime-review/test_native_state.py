"""Independent compact real-PEFT CPU test. Requires approved quiet window.

Run explicitly with REVIEW_TOKENIZER_ROOT and the verified CPU Python. No network,
pretrained weights, full4096 forward or GPU is requested by this file.
"""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime-review/frozen-worktree-v2'))

@unittest.skipUnless(os.environ.get('REVIEW_TOKENIZER_ROOT'),'explicit real tokenizer path required')
class RealNativeState(unittest.TestCase):
    def test_fullhead_alignment_and_sft_to_ttt_isolation(self):
        import torch
        torch.set_num_threads(1)
        from tools.arc_qwen_transfer_20261012.backend import create_backend
        from tools.arc_qwen_transfer_20261012 import model_profile as p, data as d
        from tools.arc_learning_agent_20261011.budget import WorkLedger
        from tools.arc_learning_agent_20261011.training import _fingerprint_tree
        from tools.arc_learning_agent_20261011.grid_codec import grid_messages
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ds=d.build_dataset({'tiny_cpu':True},root/'data')
            ledger=WorkLedger(root/'ledger.jsonl')
            config={'model_key':p.MODEL_KEY,'profile_id':p.PROFILE_ID,'tiny_cpu':True,
                'tokenizer_path':os.environ['REVIEW_TOKENIZER_ROOT'],'tiny_hidden_size':8,
                'material_addendum_sha256':p.MATERIAL_ADDENDUM_SHA256,'seed':1917,'do_sample':False}
            trainer_config={'split_manifest':ds['manifest'],'seed':1917,'task_augmentations':1,
                'objective_cycle':['grid'],'gradient_checkpointing':False,'learning_rate':2e-4,
                'task_learning_rate':5e-5,'stability_mode':False,'max_sequence_tokens':4096}
            model,trainer=create_backend(config,trainer_config,ledger=ledger);raw=trainer.trainer
            report={'cpu_fixture_only':True,'pretrained_or_gpu_claim':False}
            try:
                # Actual native template, full151936 logits, causal shift, no prompt labels.
                messages=grid_messages([{'input':[[1]],'output':[[2]]}],[[3]])
                row=model.prepare_completion(messages,'4\n5')
                ids=torch.tensor([row['input_ids']],dtype=torch.long)
                labels=torch.tensor([row['labels']],dtype=torch.long)
                raw.model.eval()
                with torch.no_grad():
                    result=raw.model(input_ids=ids,attention_mask=torch.ones_like(ids),labels=labels,use_cache=False)
                    active=labels[:,1:]!=-100
                    shifted=result.logits[:,:-1,:][active].float();targets=labels[:,1:][active]
                    expected=torch.nn.functional.cross_entropy(shifted,targets,reduction='sum')
                self.assertEqual(result.logits.shape[-1],151936)
                self.assertEqual(int(active.sum()),row['supervised_tokens'])
                self.assertAlmostEqual(float(result.loss)*row['supervised_tokens'],float(expected),places=4)
                raw._make_optimizer();raw.optimizer.zero_grad(set_to_none=True)
                accumulation=raw._accumulate(row)
                self.assertAlmostEqual(accumulation['loss_sum'],float(expected),places=4)
                self.assertEqual(accumulation['supervised_tokens'],row['supervised_tokens'])
                raw._clear()
                report['teacher_forcing']={'head_rows':151936,'completion_tokens':row['supervised_tokens'],
                    'causal_loss_sum':float(expected),'observed_loss_sum':accumulation['loss_sum'],
                    'prompt_loss_tokens':sum(v!=-100 for v in row['labels'][:row['prompt_tokens']])}
                # One actual global update, then exact selected-SFT initialization.
                base=trainer.fingerprint()['sha256']
                global_result=trainer.train(ds['records'],max_steps=1,deadline=time.monotonic()+90)
                self.assertEqual(global_result['optimizer_steps'],1)
                selected=trainer.fingerprint()['sha256'];self.assertNotEqual(selected,base)
                global_state=trainer.snapshot_training_state('selected-global-complete')
                trainer.freeze_global()
                self.assertEqual(trainer.fingerprint()['sha256'],selected)
                self.assertIsNone(raw.optimizer);self.assertIsNone(raw.scheduler);self.assertIsNone(raw._run_state)
                branches=[]
                for name,demo in [('outer-a',{'input':[[1]],'output':[[2]]}),('outer-b',{'input':[[3]],'output':[[4]]})]:
                    before_rng=_fingerprint_tree(raw._get_rng(),torch); before=deepcopy(ledger.used)
                    reset=trainer.begin_task(name)
                    self.assertEqual(reset['adapter_sha256'],selected)
                    self.assertIsNone(raw.optimizer);self.assertIsNone(raw.scheduler);self.assertIsNone(raw._run_state)
                    r=trainer.adapt_task(name,[demo],max_steps=1,deadline=time.monotonic()+90)
                    self.assertEqual(r['optimizer_steps'],1);self.assertEqual(r['total_steps'],1)
                    self.assertEqual({int(float(s['step'])) for s in raw.optimizer.state.values()},{1})
                    self.assertNotEqual(trainer.fingerprint()['sha256'],selected)
                    after_update=deepcopy(ledger.used);end=trainer.end_task()
                    self.assertEqual(trainer.fingerprint()['sha256'],selected)
                    self.assertEqual(ledger.used,after_update)
                    self.assertEqual(_fingerprint_tree(raw._get_rng(),torch),before_rng)
                    self.assertIsNone(raw.optimizer);self.assertIsNone(raw.scheduler);self.assertIsNone(raw._run_state)
                    self.assertTrue(all(p.grad is None for p in raw.parameters.values()))
                    self.assertEqual(ledger.used['training_steps'],before['training_steps']+1)
                    branches.append({'name':name,'start_adapter_sha256':reset['adapter_sha256'],
                        'adam_step':r['updates'][-1]['adam_step'],'total_steps':r['total_steps'],
                        'physical_event_id':r['physical_event_id'],'reset':end})
                physical=deepcopy(ledger.summary());trainer.restore_training_state(global_state)
                self.assertEqual(ledger.summary(),physical)
                self.assertEqual(trainer.fingerprint()['sha256'],selected)
                self.assertEqual({int(float(s['step'])) for s in raw.optimizer.state.values()},{1})
                trainer.release_training_state(global_state)
                report.update(selected_global_adapter_sha256=selected,global_result=global_result,
                    task_branches=branches,physical_after_all_branches=ledger.summary(),
                    physical_ledger_never_rolled_back=True,status='passed')
                (ROOT/'runtime-review/native-state-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
            finally:model.close()

if __name__=='__main__':unittest.main(verbosity=2)
