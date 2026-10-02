"""Actual Qwen3/Adam differential with scoped checkpoint recomputation."""
import copy
from contextlib import contextmanager
import unittest
from unittest.mock import patch

import torch
from transformers import Qwen3Config,Qwen3ForCausalLM
from irisx.arc_nvarc_gpu_preflight_v2 import RECIPE
from irisx.arc_nvarc_segmented_linear import segmented_linear
from irisx.arc_nvarc_sft_step import source_optimizer,train_source_step


class SegmentedSFTStrictTests(unittest.TestCase):
    def test_previous_scope_is_restored_before_different_length_dummy_backward(self):
        torch.set_num_threads(2);torch.manual_seed(51)
        config=Qwen3Config(vocab_size=16,hidden_size=32,intermediate_size=64,num_hidden_layers=2,
            num_attention_heads=4,num_key_value_heads=2,head_dim=8,rope_theta=5000000,tie_word_embeddings=True)
        config._attn_implementation='sdpa';model=Qwen3ForCausalLM(config).float()
        model.clip_grad_norm_=lambda maximum:torch.nn.utils.clip_grad_norm_(model.parameters(),maximum)
        optimizer,scheduler=source_optimizer(model,RECIPE);entered=[];exited=[]
        @contextmanager
        def scope(pack):
            offsets=[0]
            for segment in pack['segments']:offsets.append(offsets[-1]+segment['valid_end']-segment['start'])
            entered.append(offsets[-1])
            with segmented_linear(model,offsets,maximum_segments=64,maximum_invocations_per_module=2):yield
            exited.append(offsets[-1])
        def control_reduce(tensor,*args,**kwargs):
            if tuple(tensor.shape)==(3,):tensor.mul_(2)
            elif tuple(tensor.shape)==(1,):tensor.fill_(2)
        row={'input_ids':[14,11,10,1,15,14,12,10,2,15],'labels':[-100]*8+[2,15]}
        # Only control collectives are artificial; real Linear, loss,
        # backward and Adam run for the real and zero-loss dummy forwards.
        with patch('torch.distributed.is_initialized',return_value=True),patch('torch.distributed.get_backend',return_value='gloo'),\
                patch('torch.distributed.get_rank',return_value=0),patch('torch.distributed.get_world_size',return_value=2),\
                patch('torch.distributed.all_reduce',side_effect=control_reduce):
            result=train_source_step(model,optimizer,scheduler,[row],device=torch.device('cpu'),recipe=RECIPE,
                distributed=True,packed_backend='dense-sdpa-reference',packed_linear_context=scope)
        self.assertEqual((result['real_forward_calls'],result['dummy_forward_calls']),(1,1))
        self.assertEqual(entered,[10,2]);self.assertEqual(exited,entered)
        self.assertTrue(all('forward' not in layer.__dict__ for layer in model.modules() if isinstance(layer,torch.nn.Linear)))

    def test_full_gradient_step_and_adam_match_isolated_oracle_with_checkpoint(self):
        torch.set_num_threads(2);torch.manual_seed(72)
        config=Qwen3Config(vocab_size=16,hidden_size=32,intermediate_size=64,num_hidden_layers=2,
            num_attention_heads=4,num_key_value_heads=2,head_dim=8,rope_theta=5000000,tie_word_embeddings=True)
        config._attn_implementation='sdpa';oracle=Qwen3ForCausalLM(config).float()
        actual=copy.deepcopy(oracle)
        from torch.distributed.algorithms._checkpoint.checkpoint_wrapper import (
            apply_activation_checkpointing,checkpoint_wrapper,CheckpointImpl)
        from functools import partial
        layer_type=type(actual.model.layers[0])
        apply_activation_checkpointing(actual,checkpoint_wrapper_fn=partial(checkpoint_wrapper,
            checkpoint_impl=CheckpointImpl.NO_REENTRANT),check_fn=lambda layer:isinstance(layer,layer_type))
        rows=[{'input_ids':[14,11,10,i%10,15,14,12,10,2,15],
            'labels':[-100]*8+[2,15]} for i in range(12)]
        expected_optimizer,expected_scheduler=source_optimizer(oracle,RECIPE)
        optimizer,scheduler=source_optimizer(actual,RECIPE)
        reference_supervised=24
        for row in reversed(rows):
            logits=oracle(input_ids=torch.tensor([row['input_ids']]),use_cache=False).logits
            torch.nn.functional.cross_entropy(logits[:,:-1].reshape(-1,16),torch.tensor(row['labels'][1:]),
                ignore_index=-100,reduction='sum').div(reference_supervised).backward()
        torch.nn.utils.clip_grad_norm_(oracle.parameters(),RECIPE['clip_grad_norm'])
        expected_optimizer.step();expected_scheduler.step()
        policies=[];exits=[]
        @contextmanager
        def scope(pack):
            offsets=[0]
            for segment in pack['segments']:offsets.append(offsets[-1]+segment['valid_end']-segment['start'])
            with segmented_linear(actual,offsets,maximum_segments=64,maximum_invocations_per_module=2) as policy:
                policies.append(policy);yield policy
            exits.append(True)
        observation=train_source_step(actual,optimizer,scheduler,rows,device=torch.device('cpu'),recipe=RECIPE,
            capacity=256,length_multiple=4,distributed=False,packed_backend='dense-sdpa-reference',
            maximum_packed_input_tokens=80,packed_linear_context=scope)
        self.assertEqual((observation['global_sequence_count'],observation['global_input_tokens'],
            observation['global_supervised_tokens']),(12,120,24))
        self.assertEqual(len(policies),len(exits));self.assertEqual(len(policies),observation['real_forward_calls'])
        self.assertTrue(any(2 in row['linear_calls_by_name'].values() for row in policies))
        self.assertTrue(all('forward' not in layer.__dict__ for layer in actual.modules() if isinstance(layer,torch.nn.Linear)))
        for name,value in oracle.state_dict().items():
            torch.testing.assert_close(value,actual.state_dict()[name],atol=2e-7,rtol=2e-5)
        for (_,a),(_,b) in zip(oracle.named_parameters(),actual.named_parameters()):
            for key in ('exp_avg','exp_avg_sq','step'):
                torch.testing.assert_close(expected_optimizer.state[a][key],optimizer.state[b][key],atol=2e-8,rtol=3e-5)


if __name__=='__main__':unittest.main()
