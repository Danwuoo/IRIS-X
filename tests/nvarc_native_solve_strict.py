"""Strict CPU actual-Qwen3 controls; no target GPU or native Unsloth claim."""
import ast
import copy
import hashlib
import os
from pathlib import Path
import time
from types import SimpleNamespace
import unittest

import numpy as np
import torch
from peft import LoraConfig, get_peft_model, get_peft_model_state_dict, set_peft_model_state_dict
from transformers import Qwen3Config, Qwen3ForCausalLM

from tools import nvarc_native_solve_runtime as runtime
from tools import nvarc_native_solve_render as render


class IsolatedTupleModel:
    def __init__(self, model): self.model, self.device = model, model.device
    def __call__(self, **kwargs):
        # Emulate a position-isolated source cache on a tiny real HF model.
        # This does not verify Unsloth's native cache implementation.
        if kwargs.get('past_key_values') is not None:
            kwargs['past_key_values'] = copy.deepcopy(kwargs['past_key_values'])
        value = self.model(**kwargs)
        return value.logits, value.past_key_values


class NativeSolveStrictTests(unittest.TestCase):
    def setUp(self):
        self.threads = torch.get_num_threads(); torch.set_num_threads(1); torch.manual_seed(741)
        config = Qwen3Config(vocab_size=16, hidden_size=32, intermediate_size=64,
            num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1,
            head_dim=16, attention_dropout=0., tie_word_embeddings=False,
            pad_token_id=13, bos_token_id=13, eos_token_id=15)
        config._attn_implementation = 'eager'
        self.model = Qwen3ForCausalLM(config).float().eval()

    def tearDown(self):
        torch.set_num_threads(self.threads)

    def adapter(self, model):
        return runtime.SourceModel(model, torch, lambda *_a, **_k: None,
            forward_limits={'control':7,'generation':16,'verification':16},
            input_token_limit=10000, generation_deadline=time.time()+60)

    def test_real_logits_tuple_bridge_cached_deep_and_fresh_sibling_match_full_prefix(self):
        adapter = self.adapter(IsolatedTupleModel(self.model))
        controls = runtime.cache_controls(adapter)
        self.assertTrue(all(r['gate_passed'] for r in controls['comparisons'].values()))
        self.assertFalse(controls['full_numerical_parity_claim'])
        self.assertEqual(adapter.completed['control'],6)
        self.assertTrue(runtime.reset_control(adapter,controls)['prefill_bitwise_equal'])
        self.assertEqual(adapter.input_by_phase['control'],168)

    def test_actual_mutable_hf_cache_is_rejected_before_training(self):
        model = get_peft_model(self.model,LoraConfig(r=2,lora_alpha=4,lora_dropout=0.,
            target_modules=['q_proj','v_proj'],task_type='CAUSAL_LM'))
        with self.assertRaisesRegex(RuntimeError,'native cache branch control failed before training'):
            runtime.cache_controls(self.adapter(model))

    def test_actual_source_verifier_matches_independent_eos_inclusive_nll(self):
        directory = Path(os.environ['IRIS_NATIVE_CODE_ONLY_DIR'])
        _, solver, _ = runtime.load_sources(directory,torch,np)
        adapter = self.adapter(self.model)
        class Tokens:
            def encode(self,text): return [int(v) for v in text.split(',')]
        queries = ['14,11,10,1,15,14,12,10']*4
        answers = ['2,10,3,15']*4
        with torch.inference_mode(),adapter.scope('verification'):
            actual = solver.calc_scores(queries,answers,Tokens(),adapter)
            ids = torch.tensor([Tokens().encode(queries[0]+','+answers[0])]*4)
            logits = self.model(ids,use_cache=False).logits.log_softmax(-1)
            expected = -logits[:,7:11].gather(-1,ids[:,8:12,None]).sum((1,2))
        torch.testing.assert_close(torch.tensor(actual),expected,atol=0,rtol=0)
        self.assertEqual(adapter.completed['verification'],1)
        self.assertEqual(adapter.input_by_phase['verification'],48)

    def test_actual_peft_second_task_reset_after_success_and_pipeline_exception(self):
        model = get_peft_model(self.model,LoraConfig(r=2,lora_alpha=4,lora_dropout=0.,
            target_modules=['q_proj','v_proj'],task_type='CAUSAL_LM'))
        defaults = {k:v.detach().clone() for k,v in get_peft_model_state_dict(model).items()}
        def inventory(values,_torch):
            return [{'name':k,'sha256':hashlib.sha256(v.detach().cpu().numpy().tobytes()).hexdigest()}
                    for k,v in sorted(values.items())]
        baseline = inventory(defaults,torch)
        body = ast.parse('def worker():\n'+render.TAIL).body[0].body
        original = next(n for n in body if isinstance(n,ast.Try))
        observations = []
        reference = None
        for failed in (False,True):
            model.eval(); adapter = self.adapter(IsolatedTupleModel(model))
            controls = runtime.cache_controls(adapter)
            if reference is None: reference = controls['baseline_prefill']
            self.assertEqual(controls['baseline_prefill'],reference)
            optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=.01)
            trainer = SimpleNamespace(optimizer=optimizer,lr_scheduler=object(),
                accelerator=SimpleNamespace(_optimizers=[optimizer],_schedulers=[object()]))
            budget = SimpleNamespace(optimizer=optimizer,state={'forwards':[],'optimizer_steps':[]})
            model.train(); ids = torch.tensor([[14,11,10,1,15,14,12,10,2,15]])
            model(ids,labels=ids,use_cache=False).loss.backward(); optimizer.step()
            self.assertNotEqual(inventory(get_peft_model_state_dict(model),torch),baseline)
            saved = {}
            ns = {'release_optimizer':lambda:runtime.discard_optimizer_state(model,trainer,budget),
                'set_peft_model_state_dict':set_peft_model_state_dict,'get_peft_model_state_dict':get_peft_model_state_dict,
                'model':model,'defaults':defaults,'tensor_inventory':inventory,'torch':torch,'baseline':baseline,
                'require':runtime.require,'save':lambda name,value:saved.update({name:copy.deepcopy(value)}),
                'reset_verified':False,'control':controls,'FastLanguageModel':SimpleNamespace(for_inference=lambda m:m.eval()),
                'reset_control':runtime.reset_control,'adapter':adapter,'failures':[],'pending_error':None,
                'solve':{'outcome':'complete'},'post_reset':None,'plan':{'run_id':'synthetic'},
                'digest':lambda _p:'synthetic','training_complete':True,'trainer':trainer,'elapsed':0.,
                'started':time.monotonic(),'time':time,'budget':budget}
            primary = [ast.Raise(exc=ast.Call(func=ast.Name(id='RuntimeError',ctx=ast.Load()),
                args=[ast.Constant(value='synthetic-after-update')],keywords=[]),cause=None)] if failed else [ast.Pass()]
            attempt = ast.Try(body=primary,handlers=original.handlers,orelse=[],finalbody=original.finalbody)
            program = ast.fix_missing_locations(ast.Module(body=[attempt]+body[body.index(original)+1:],type_ignores=[]))
            if failed:
                with self.assertRaisesRegex(RuntimeError,'synthetic-after-update'):
                    exec(compile(program,'actual-peft-finalizer','exec'),ns)
            else:
                exec(compile(program,'actual-peft-finalizer','exec'),ns)
            result = saved['pipeline-result.json']; observations.append(result['outcome'])
            self.assertTrue(result['all_saved_tensors_restored'])
            self.assertTrue(result['post_reset_control_verified'])
            self.assertTrue(result['optimizer_discarded'])
            self.assertEqual(optimizer.state,{})
            self.assertTrue(all(p.grad is None for p in model.parameters()))
        self.assertEqual(observations,['complete','failed'])


if __name__ == '__main__': unittest.main()
