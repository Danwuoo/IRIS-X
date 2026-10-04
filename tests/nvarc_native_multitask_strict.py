"""Actual tiny Qwen3/PEFT state and NLL controls; no Unsloth/GPU conclusion."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest

import numpy as np
import torch
from peft import LoraConfig,get_peft_model,get_peft_model_state_dict,set_peft_model_state_dict
from transformers import Qwen3Config,Qwen3ForCausalLM
from tools import nvarc_native_multitask as runtime
from tools import nvarc_native_multitask_render as render
from tools.nvarc_native_solve_runtime import load_sources,cache_controls,discard_optimizer_state,reset_control,CONTROL_PREFIXES


class NativeMultiTaskStrictTests(unittest.TestCase):
    def setUp(self):
        self.threads=torch.get_num_threads();torch.set_num_threads(1);torch.manual_seed(741)
        config=Qwen3Config(vocab_size=16,hidden_size=32,intermediate_size=64,num_hidden_layers=2,
            num_attention_heads=2,num_key_value_heads=1,head_dim=16,attention_dropout=0.,tie_word_embeddings=False,
            pad_token_id=13,bos_token_id=13,eos_token_id=15)
        config._attn_implementation='eager'
        self.model=Qwen3ForCausalLM(config).float().eval()
        self.temp=tempfile.TemporaryDirectory(prefix='iris-native-strict-')

    def tearDown(self):self.temp.cleanup();torch.set_num_threads(self.threads)

    def adapter(self,model,emit=lambda *_a,**_k:None):
        return runtime.EvidenceModel(model,torch,emit,forward_limits={'control':7,'generation':32,'verification':16},
            input_token_limit=10000,generation_deadline=time.time()+60)

    def test_raw_mutating_hf_cache_rejected_without_cache_deepcopy(self):
        with self.assertRaisesRegex(RuntimeError,'native cache branch control failed'):
            cache_controls(self.adapter(self.model))

    def test_actual_eight_view_scores_retained_nlls_match_independent_qwen_forward(self):
        _,solver,_=load_sources(Path(os.environ['IRIS_NATIVE_CODE_ONLY_DIR']),torch,np)
        class Tokens:
            def encode(self,text):return [int(t) for t in text.split(',')]
        queries=['14,11,10,1,15,14,12,10']*4;answers=['2,10,3,15']*4
        bindings=[{'source_view':'tiny_'+str(i),'query_ids':Tokens().encode(q),'answer_ids':Tokens().encode(a)}
                  for i,(q,a) in enumerate(zip(queries,answers))]
        events=[];adapter=self.adapter(self.model,lambda e,**kw:events.append({'event':e,**kw}))
        with torch.inference_mode(),adapter.scope('verification'):
            adapter.verification_rows=bindings
            scores=solver.calc_scores(queries,answers,Tokens(),adapter)
            adapter.verification_rows=bindings
            scores+=solver.calc_scores(queries,answers,Tokens(),adapter)
            ids=torch.tensor([r['query_ids']+r['answer_ids'] for r in bindings])
            logits=self.model(ids,use_cache=False).logits.float().cpu().log_softmax(-1)
            selected=logits[:,7:11].gather(-1,ids[:,8:12,None]).squeeze(-1)
            expected=-selected.sum(1)
        torch.testing.assert_close(torch.tensor(scores),torch.cat([expected,expected]),atol=0,rtol=0)
        observed=[e for e in events if e['event']=='verification_observed']
        self.assertEqual(len(observed),2)
        self.assertEqual([r['answer_log_probabilities'] for r in observed[0]['rows']],selected.tolist())
        self.assertEqual([r['score'] for r in observed[0]['rows']],expected.tolist())
        self.assertEqual(adapter.reserved['verification'],2)

    def test_native_derived_finalizer_restores_real_peft_after_success_and_failure(self):
        model=get_peft_model(self.model,LoraConfig(r=2,lora_alpha=4,lora_dropout=0.,
            target_modules=['q_proj','v_proj'],task_type='CAUSAL_LM'))
        defaults={k:v.detach().clone() for k,v in get_peft_model_state_dict(model).items()}
        def inventory(values,_torch):
            return [{'name':k,'sha256':hashlib.sha256(v.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()}
                    for k,v in sorted(values.items())]
        baseline=inventory(defaults,torch)
        with torch.inference_mode():reference=model(torch.tensor(CONTROL_PREFIXES),use_cache=True).logits[:,-1].float().tolist()
        main=next(n for n in ast.parse('def worker():\n'+render.TAIL).body[0].body if isinstance(n,ast.Try))
        observations=[]
        for failed,uncleared in ((False,False),(True,False),(False,True)):
            model.eval();adapter=self.adapter(model)
            with torch.inference_mode():before=model(torch.tensor(CONTROL_PREFIXES),use_cache=False).logits[:,-1].float().tolist()
            self.assertEqual(before,reference)
            optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=.01)
            scheduler=object();trainer=SimpleNamespace(optimizer=optimizer,lr_scheduler=scheduler,
                accelerator=SimpleNamespace(_optimizers=[optimizer],_schedulers=[scheduler]))
            budget=SimpleNamespace(optimizer=optimizer)
            model.train();ids=torch.tensor([[14,11,10,1,15,14,12,10,2,15]])
            for _ in range(2):
                optimizer.zero_grad(set_to_none=True);model(ids,labels=ids,use_cache=False).loss.backward();optimizer.step()
            self.assertNotEqual(inventory(get_peft_model_state_dict(model),torch),baseline)
            saved={};failures=[] if not failed else [{'phase':'pipeline','error_type':'RuntimeError','error_message':'injected'}]
            namespace={'release':(lambda:None) if uncleared else lambda:discard_optimizer_state(model,trainer,budget),
                'set_peft_model_state_dict':set_peft_model_state_dict,'get_peft_model_state_dict':get_peft_model_state_dict,
                'model':model,'defaults':defaults,'tensor_inventory':inventory,'torch':torch,'baseline':baseline,
                'require':runtime.require,'save':lambda name,value:saved.update({name:copy.deepcopy(value)}),
                'reset_verified':False,'control':{'baseline_prefill':reference},'post_reset':None,
                'FastLanguageModel':SimpleNamespace(for_inference=lambda m:m.eval()),'reset_control':reset_control,
                'adapter':adapter,'failures':failures,'trainer':trainer,'budget':budget,'mode':'baseline-only' if uncleared else 'solve',
                'training_complete':True,'tests':[],'binding':{'fixture':'actual-tiny-peft'},'elapsed':0.,
                'started':time.monotonic(),'time':time,'challenges':{'fixture':{'test':[{}]}},'task_id':'fixture'}
            exec(compile(ast.Module(body=main.finalbody,type_ignores=[]),'actual-native-multitask-finalizer','exec'),namespace)
            result=saved['result.json'];observations.append(result['outcome'])
            self.assertNotEqual(saved['pre-reset-inventory.json'],baseline)
            self.assertTrue(result['all_saved_tensors_restored']);self.assertTrue(result['post_reset_control_verified'])
            self.assertEqual(result['optimizer_discarded'],not uncleared)
            if not uncleared:
                self.assertEqual(optimizer.state,{})
                self.assertTrue(all(p.grad is None for p in model.parameters()))
                self.assertIsNone(trainer.lr_scheduler);self.assertFalse(trainer.accelerator._schedulers)
        self.assertEqual(observations,['inconclusive','failed','inconclusive'])

    def test_zero_grad_exception_preserves_reset_and_reports_cleanup_failure(self):
        model=get_peft_model(self.model,LoraConfig(r=2,lora_alpha=4,lora_dropout=0.,target_modules=['q_proj','v_proj'],task_type='CAUSAL_LM'))
        optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=.01)
        trainer=SimpleNamespace(optimizer=optimizer,lr_scheduler=object(),
            accelerator=SimpleNamespace(_optimizers=[optimizer],_schedulers=[object()]))
        budget=SimpleNamespace(optimizer=optimizer)
        def failed_zero(**_kw):raise RuntimeError('actual optimizer cleanup injection')
        optimizer.zero_grad=failed_zero
        with self.assertRaisesRegex(RuntimeError,'cleanup injection'):discard_optimizer_state(model,trainer,budget)
        self.assertEqual(optimizer.state,{})
        self.assertIsNone(trainer.optimizer);self.assertIsNone(budget.optimizer)
        self.assertFalse(trainer.accelerator._schedulers)


if __name__=='__main__':unittest.main()
