"""Real tiny CPU execution of the GPU control flow, with explicit local shims."""
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import torch
from transformers import Qwen3Config,Qwen3ForCausalLM
from irisx.arc_nvarc_qwen3_packing import packed_forward
from irisx.arc_nvarc_qwen3_segmented_probe import run,schedule,FORMAT
from irisx.canonical import digest_value


class SegmentedProbeStrictTests(unittest.TestCase):
    def test_actual_control_flow_has_thirteen_calls_two_backwards_and_restores_guards(self):
        torch.set_num_threads(2);torch.manual_seed(54)
        config=Qwen3Config(vocab_size=16,hidden_size=32,intermediate_size=64,num_hidden_layers=36,
            num_attention_heads=4,num_key_value_heads=2,head_dim=8,rope_theta=5000000,
            tie_word_embeddings=True,attention_dropout=0.0)
        config._attn_implementation='sdpa';model=Qwen3ForCausalLM(config).to(torch.bfloat16).eval()
        rows=[{'input_ids':[14,11,10,i,15,14,12,10,2,15],
            'labels':[-100]*8+[2,15],'parent_ids':['toy-'+str(i)]} for i in range(8)]
        plan={'format':FORMAT,'owner_decision':'Decision 0054','forward_schedule':schedule(rows),
            'data_digest':digest_value(rows),'atol':.25,'rtol':.03,'tiny_gradient_backwards':2,
            'maximum_outer_forwards':13,'maximum_input_tokens':sum(row['input_tokens'] for row in schedule(rows)),
            'maximum_worker_wall_seconds':900,'maximum_optimizer_steps':0,'maximum_generations':0,
            'maximum_teacher_calls':0,'maximum_paid_usd':0,'run_id':'literal-cpu-fixture'}
        original_to=torch.nn.Module.to;original_tensor=torch.tensor;original_zeros=torch.zeros
        before=(torch.nn.Module._call_impl,torch.autograd.backward,torch.autograd.grad,torch.optim.Optimizer.__init__)
        def cpu_kwargs(kwargs):
            kwargs=dict(kwargs)
            if 'device' in kwargs:kwargs['device']='cpu'
            return kwargs
        def module_to(module,*args,**kwargs):
            args=tuple('cpu' if isinstance(arg,torch.device) and arg.type=='cuda' else arg for arg in args)
            return original_to(module,*args,**cpu_kwargs(kwargs))
        def tensor(*args,**kwargs):return original_tensor(*args,**cpu_kwargs(kwargs))
        def zeros(*args,**kwargs):return original_zeros(*args,**cpu_kwargs(kwargs))
        def dense(module,layout,**kwargs):
            previous=module.config._attn_implementation;module.config._attn_implementation='sdpa'
            try:return packed_forward(module,layout,backend='dense-sdpa-reference')
            finally:module.config._attn_implementation=previous
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(torch,'__version__','2.10.0+cu128'),patch.object(torch.nn.Module,'to',module_to),\
                patch.object(torch,'tensor',tensor),patch.object(torch,'zeros',zeros),\
                patch.object(torch.cuda,'synchronize'),patch.object(torch.cuda,'empty_cache'),\
                patch('torch.nn.attention.sdpa_kernel',lambda *args:nullcontext()),\
                patch('irisx.arc_nvarc_qwen3_segmented_probe.register_torch_varlen'),\
                patch('irisx.arc_nvarc_qwen3_segmented_probe.packed_forward',dense),\
                patch('tokenizers.Tokenizer.from_file',return_value=SimpleNamespace(
                    encode=lambda text:SimpleNamespace(ids=[14,11,10,1,2,15,14,12,10,3,4,15]))),\
                patch.object(Qwen3ForCausalLM,'from_pretrained',return_value=model):
                result=run(plan,rows,Path(directory),Path(directory))
            self.assertEqual(result['actual_outer_forwards'],13)
            self.assertEqual(result['actual_input_tokens'],284)
            self.assertEqual(result['actual_backwards'],2)
            self.assertEqual(result['decoder_layers_executed'],36)
            self.assertEqual(result['optimizer_steps'],0)
            self.assertEqual(result['generation_calls'],0)
            self.assertTrue(result['later_samples_bitwise_isolated'])
            metadata=json.loads((Path(directory)/'vectors.json').read_bytes())
            self.assertEqual(len(metadata),55)
            self.assertEqual(metadata['packed-states']['shape'],[38,8,3,32])
            for name,expected in [('tiny-linear-policy.json',30),('full-linear-policy.json',2024),
                ('isolation-linear-policy.json',2024)]:
                policy=json.loads((Path(directory)/name).read_bytes())
                self.assertEqual(policy['segment_gemm_calls'],expected)
                self.assertTrue(all(count==1 for count in policy['linear_calls_by_name'].values()))
            self.assertTrue(all(row['completed'] for row in json.loads((Path(directory)/'worker-ledger.json').read_bytes())))
        self.assertEqual(before,(torch.nn.Module._call_impl,torch.autograd.backward,torch.autograd.grad,torch.optim.Optimizer.__init__))
        self.assertTrue(all('forward' not in module.__dict__ for module in model.modules() if isinstance(module,torch.nn.Linear)))
        self.assertTrue(all(not module._forward_hooks for module in model.modules()))
        # Dense CPU attention and tiny 32-wide weights explicitly do not qualify
        # the actual CUDA reader, whose required width is 2,560 on four L4s.


if __name__=='__main__':unittest.main()
