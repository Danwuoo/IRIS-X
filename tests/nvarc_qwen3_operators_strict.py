"""Actual tiny CPU hooks/precision/entry guard; no GPU backend claim."""
import copy
import unittest

import torch
from transformers import Qwen3Config, Qwen3ForCausalLM
from irisx.arc_nvarc_qwen3_operator_probe import (OperatorCapture, OperatorBudget,
    MODES, OPERATORS, parameter_layout, precision_mode, schedule)
from irisx.arc_nvarc_qwen3_packing_diagnostic import ordered_rows
from irisx.errors import ValidationError


class FirstLayerOperatorStrictTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2); torch.manual_seed(713)
        config=Qwen3Config(vocab_size=16,hidden_size=32,intermediate_size=64,
            num_hidden_layers=2,num_attention_heads=4,num_key_value_heads=2,head_dim=8,
            tie_word_embeddings=True,attention_dropout=0.0)
        config._attn_implementation='sdpa'
        self.model=Qwen3ForCausalLM(config).to(torch.bfloat16).eval()
        self.original_config=config.to_dict()
        del self.model.model.layers[1:]
        config.num_hidden_layers=1;config.layer_types=config.layer_types[:1]
        self.rows=[{'input_ids':[14,11,10,i,15,14,12,10,2,15],
            'labels':[-100]*8+[2,15],'parent_ids':['toy-'+str(i)]} for i in range(8)]

    def test_all_seven_modes_capture_real_operators_with_exact_guarded_partial_calls(self):
        model=self.model
        self.assertEqual({name:list(p.shape) for name,p in model.named_parameters()},parameter_layout(self.original_config))
        self.assertEqual(len(parameter_layout(self.original_config)),13)
        layout,ordered=ordered_rows(self.rows);allowed=schedule(self.rows)
        journal=[];budget=OperatorBudget(self.rows,{'maximum_outer_forwards':21,
            'maximum_input_tokens':sum(row['input_tokens'] for row in allowed),'maximum_worker_wall_seconds':900},
            lambda name,value:journal.append(copy.deepcopy(value)))
        original=torch.nn.Module._call_impl
        torch.nn.Module._call_impl=lambda module,*args,**kwargs:budget.guard_call(module,args,kwargs,original)
        capture=OperatorCapture(model)
        try:
            with torch.inference_mode():
                for mode in MODES:
                    with precision_mode(model,torch,mode) as setting:
                        self.assertEqual(setting['rewritten_linear_modules'],8 if 'fp32-linear' in mode else 0)
                        if mode.startswith('independent'):
                            for row in ordered:
                                capture.positions=[0,5,9]
                                result=budget.perform(mode,lambda:model(input_ids=torch.tensor([row['input_ids']]),use_cache=False))
                                self.assertEqual(result.logits.shape,(1,10,16))
                                self.assertEqual(set(capture.values),set(OPERATORS))
                                self.assertEqual(capture.values['k-norm'].shape,(3,16))
                        else:
                            # CPU dense block mask only validates hooks/precision;
                            # native varlen/GQA execution remains a GPU question.
                            capture.positions=[10*i+p for i in range(8) for p in (0,5,9)]
                            positions=torch.arange(10).repeat(8)[None]
                            ids=torch.tensor([[x for row in ordered for x in row['input_ids']]])
                            index=torch.arange(80);allowed_mask=(index[:,None]//10==index[None,:]//10)&(index[:,None]>=index[None,:])
                            mask=torch.zeros((1,1,80,80),dtype=torch.bfloat16).masked_fill(~allowed_mask[None,None],float('-inf'))
                            result=budget.perform(mode,lambda:model(input_ids=ids,position_ids=positions,
                                attention_mask=mask,use_cache=False))
                            self.assertEqual(result.logits.shape,(1,80,16))
                            self.assertEqual(capture.values['q-norm'].shape,(24,32))
                            self.assertEqual(capture.values['product-before-down-projection'].shape,(24,64))
                        self.assertTrue(all(torch.isfinite(value).all() for value in capture.values.values()))
                with self.assertRaises(ValidationError):model(input_ids=torch.tensor([[14]]),use_cache=False)
            self.assertEqual(len(budget.events),21)
            self.assertEqual(sum(row['input_tokens'] for row in budget.events),560)
            self.assertTrue(all(row['completed'] for row in budget.events))
            self.assertTrue(all(not row[-1]['completed'] for row in journal[::2]))
            self.assertTrue(all(row[-1]['completed'] for row in journal[1::2]))
        finally:
            capture.remove();torch.nn.Module._call_impl=original
        self.assertTrue(all(not module._forward_hooks and not module._forward_pre_hooks for module in model.modules()))

    def test_precision_methods_storage_and_global_flags_restore_after_failure(self):
        model=self.model;linear=model.model.layers[0].self_attn.q_proj
        linear.forward=linear.forward  # Preserve an existing instance override too.
        methods={id(module):dict(module.__dict__) for module in model.modules() if isinstance(module,torch.nn.Linear)}
        weights={name:p.detach().clone() for name,p in model.named_parameters()}
        old_flag=torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction
        old_precision=torch.get_float32_matmul_precision()
        with self.assertRaisesRegex(RuntimeError,'injected'):
            with precision_mode(model,torch,'packed-fp32-linear'):
                self.assertFalse(torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction)
                self.assertEqual(torch.get_float32_matmul_precision(),'highest')
                value=linear(torch.zeros(1,3,32,dtype=torch.bfloat16))
                self.assertEqual(value.dtype,torch.bfloat16)
                raise RuntimeError('injected compute failure')
        self.assertEqual(torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction,old_flag)
        self.assertEqual(torch.get_float32_matmul_precision(),old_precision)
        for module in model.modules():
            if isinstance(module,torch.nn.Linear):
                self.assertEqual('forward' in module.__dict__,'forward' in methods[id(module)])
                if 'forward' in module.__dict__:self.assertIs(module.forward,methods[id(module)]['forward'])
        self.assertTrue(all(torch.equal(weights[name],p) for name,p in model.named_parameters()))

    def test_original_output_extractor_accepts_real_model_output_and_cached_tuple(self):
        from tools.stage_nvarc_original_unsloth_probe import OUTPUT_HELPER, IDS
        scope={'torch':torch,'contracts':[]}
        exec(compile(OUTPUT_HELPER,'source-bound-original-output-extractor','exec'),scope)
        with torch.inference_mode():
            first=self.model(input_ids=torch.tensor([IDS]),position_ids=torch.arange(12)[None],use_cache=True)
            logits,cache=scope['observed_output'](first,12)
            second=self.model(input_ids=torch.tensor([[0]]),position_ids=torch.tensor([[12]]),
                past_key_values=cache,use_cache=True,return_dict=False)
            cached_logits,cached_values=scope['observed_output'](second,1)
        self.assertEqual(scope['contracts'],['model-output-logits-cache','tuple-logits-cache'])
        self.assertTrue(torch.isfinite(logits).all() and torch.isfinite(cached_logits).all())
        self.assertIsNotNone(cached_values)


if __name__=='__main__':unittest.main()
