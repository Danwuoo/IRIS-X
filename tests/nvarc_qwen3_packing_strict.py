"""Real tiny Qwen3 independent-sequence oracle; strict ML environment only."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

import torch
from transformers import Qwen3Config, Qwen3ForCausalLM

from irisx.arc_nvarc_packing import pack_sequences
from irisx.arc_nvarc_qwen3_packing import TORCH_VARLEN, packed_forward, register_torch_varlen
from irisx.arc_nvarc_qwen3_packing import TORCH_VARLEN_GQA,native_gqa_inputs,register_torch_varlen_gqa
from irisx.errors import ValidationError
from irisx.arc_nvarc_qwen3_packing_diagnostic import TINY,ForwardBudget,schedule


class OriginalQwen3PackingTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(731)
        config = Qwen3Config(vocab_size=16, hidden_size=64, intermediate_size=128,
            num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
            head_dim=16, max_position_embeddings=262144, rope_theta=5000000,
            attention_dropout=0.0, tie_word_embeddings=True, pad_token_id=13,
            bos_token_id=13, eos_token_id=15)
        config._attn_implementation = 'sdpa'
        self.model = Qwen3ForCausalLM(config).float().eval()
        self.rows = [
            {'input_ids': [14, 11, 10, 1, 2, 15, 14, 12, 10, 3, 4, 15],
             'labels': [-100] * 9 + [3, 4, 15], 'parents': ['a', 'b'], 'exposure': ['evaluation']},
            {'input_ids': [14, 11, 10, 8, 15, 14, 12, 10, 7, 15],
             'labels': [-100] * 8 + [7, 15], 'parents': ['c']},
            {'input_ids': [14, 11, 10, 0, 2, 1, 15, 14, 12, 10, 1, 2, 0, 15],
             'labels': [-100] * 10 + [1, 2, 0, 15], 'parents': ['d']}]

    def test_diagnostic_budget_hooks_actual_qwen3_entry_without_extra_forward(self):
        rows=[copy.deepcopy(self.rows[i%3]) for i in range(8)];allowed=schedule(rows);journal=[]
        budget=ForwardBudget(rows,{'maximum_outer_forwards':len(allowed),
            'maximum_input_tokens':sum(x['input_tokens'] for x in allowed),'maximum_worker_wall_seconds':1200},
            lambda name,value:journal.append(copy.deepcopy(value)))
        original=torch.nn.Module._call_impl
        observed=[]
        def guarded(module,*args,**kwargs):
            if type(module).__name__=='Qwen3ForCausalLM':observed.append('outer-entry')
            return budget.guard_call(module,args,kwargs,original)
        torch.nn.Module._call_impl=guarded
        try:
            with self.assertRaises(ValidationError):self.model(torch.tensor([TINY[0]['input_ids']]),use_cache=False)
            for row in TINY:
                logits=budget.perform('tiny-independent-gradients',lambda:
                    self.model(torch.tensor([row['input_ids']]),use_cache=False).logits)
                self.assertEqual(list(logits.shape),[1,len(row['input_ids']),16])
            self.assertEqual([e['completed'] for e in journal[0]],[False])
            self.assertEqual([e['completed'] for e in budget.events],[True,True])
            self.assertEqual(len(observed),3)  # One rejected entry and two actual model forwards.
        finally:torch.nn.Module._call_impl=original

    def test_native_gqa_cpu_layout_arithmetic_gradients_and_boundaries(self):
        q=torch.randn(1,4,9,16,requires_grad=True)
        k=torch.randn(1,2,9,16,requires_grad=True)
        v=torch.randn(1,2,9,16,requires_grad=True)
        query,key,value=native_gqa_inputs(q,k,v)
        self.assertEqual(tuple(query.shape),(9,4,16))
        self.assertEqual(tuple(key.shape),(9,2,16))
        self.assertEqual(tuple(value.shape),(9,2,16))
        torch.testing.assert_close(key.transpose(0,1).unsqueeze(0),k,atol=0,rtol=0)
        # Explicit CPU per-segment arithmetic is not the CUDA varlen operator.
        chunks=[]
        for start,stop in ((0,4),(4,9)):
            chunks.append(torch.nn.functional.scaled_dot_product_attention(
                query[start:stop].transpose(0,1).unsqueeze(0),
                key[start:stop].transpose(0,1).unsqueeze(0),
                value[start:stop].transpose(0,1).unsqueeze(0),is_causal=True,enable_gqa=True))
        grouped=torch.cat(chunks,dim=2)
        independent=torch.cat([torch.nn.functional.scaled_dot_product_attention(
            q[:,:,start:stop],k[:,:,start:stop].repeat_interleave(2,dim=1),
            v[:,:,start:stop].repeat_interleave(2,dim=1),is_causal=True)
            for start,stop in ((0,4),(4,9))],dim=2)
        torch.testing.assert_close(grouped,independent,atol=2e-6,rtol=2e-5)
        actual_grad=torch.autograd.grad(grouped.square().sum(),(q,k,v),retain_graph=True)
        reference_grad=torch.autograd.grad(independent.square().sum(),(q,k,v))
        for actual,reference in zip(actual_grad,reference_grad):
            torch.testing.assert_close(actual,reference,atol=3e-6,rtol=3e-5)
        with self.assertRaises(ValidationError):native_gqa_inputs(q[:,:3],k,v)
        with self.assertRaises(ValidationError):native_gqa_inputs(q,k,v[:,:,:8])
        with self.assertRaises(ValidationError):native_gqa_inputs(q.expand(2,-1,-1,-1),k,v)
        register_torch_varlen_gqa();config=copy.deepcopy(self.model.config)
        config._attn_implementation=TORCH_VARLEN_GQA;model=Qwen3ForCausalLM(config)
        with self.assertRaises(ValidationError):
            packed_forward(model,pack_sequences(self.rows,capacity=256)[0],backend='torch-varlen-flash-gqa')

    def test_real_logits_global_loss_and_every_gradient(self):
        pack = pack_sequences(self.rows, capacity=256)[0]
        oracle = copy.deepcopy(self.model)
        outputs = []
        total = torch.tensor(0.0)
        for segment in pack['segments']:
            row = self.rows[segment['row_index']]
            logits = oracle(torch.tensor([row['input_ids']]), use_cache=False).logits
            labels = torch.tensor(row['labels'][1:])
            total = total + torch.nn.functional.cross_entropy(logits[0, :-1].float(), labels,
                reduction='sum', ignore_index=-100)
            outputs.append(logits)
        actual = packed_forward(self.model, pack)
        for i, expected in enumerate(outputs):
            start, stop = actual['offsets'][i:i + 2]
            torch.testing.assert_close(actual['logits'][:, start:stop], expected, atol=2e-6, rtol=2e-5)
        torch.testing.assert_close(actual['loss_sum'], total, atol=2e-6, rtol=2e-5)
        (actual['loss_sum'] / actual['supervised_tokens']).backward()
        (total / pack['supervised_tokens']).backward()
        for (name, actual_param), (_, expected) in zip(self.model.named_parameters(), oracle.named_parameters()):
            self.assertIsNotNone(actual_param.grad, name)
            torch.testing.assert_close(actual_param.grad, expected.grad, atol=2e-6, rtol=3e-5, msg=name)
        self.assertEqual(actual['outer_model_forwards'], 1)
        self.assertEqual(actual['physical_input_tokens'], sum(len(r['input_ids']) for r in self.rows))
        self.assertLess(actual['physical_input_tokens'], actual['logical_padded_tokens'])
        self.assertEqual(pack['segments'][0]['lineage']['parents'], ['a', 'b'])

    def test_prior_sample_change_and_unsafe_flat_control(self):
        pack = pack_sequences(self.rows, capacity=256)[0]
        reference = packed_forward(self.model, pack)
        changed = copy.deepcopy(self.rows)
        changed[0]['input_ids'][3:5] = [9, 8]
        result = packed_forward(self.model, pack_sequences(changed, capacity=256)[0])
        start = reference['offsets'][1]
        torch.testing.assert_close(result['logits'][:, start:], reference['logits'][:, start:], rtol=0, atol=0)
        ids = torch.tensor([[v for row in self.rows for v in row['input_ids']]])
        unsafe = self.model(ids, use_cache=False).logits
        self.assertGreater(float((unsafe[:, start:] - reference['logits'][:, start:]).abs().max().detach()), 1e-4)

    def test_backend_and_dense_memory_gates_fail_closed(self):
        pack = pack_sequences(self.rows, capacity=256)[0]
        with self.assertRaises(ValidationError):
            packed_forward(self.model, pack, backend='flash-attention-2-varlen')
        with self.assertRaises(ValidationError):
            packed_forward(self.model, pack, maximum_dense_tokens=10)
        self.model.config.model_type = 'qwen3_5'
        with self.assertRaises(ValidationError):
            packed_forward(self.model, pack)

    def test_public_transformers_backend_registration(self):
        register_torch_varlen()
        config = copy.deepcopy(self.model.config)
        config._attn_implementation = TORCH_VARLEN
        model = Qwen3ForCausalLM(config)
        self.assertEqual(model.config._attn_implementation, TORCH_VARLEN)
        with self.assertRaises(ValidationError):
            packed_forward(model, pack_sequences(self.rows, capacity=256)[0], backend='torch-varlen-flash')

    def test_packed_source_optimizer_matches_independent_global_token_oracle(self):
        from irisx.arc_nvarc_gpu_preflight_v2 import RECIPE
        from irisx.arc_nvarc_sft_step import source_optimizer, train_source_step
        oracle=copy.deepcopy(self.model)
        reference_optimizer,reference_scheduler=source_optimizer(oracle,RECIPE)
        tokens=sum(sum(label>=0 for label in row['labels'][1:]) for row in self.rows)
        loss=torch.tensor(0.0)
        for row in self.rows:
            logits=oracle(torch.tensor([row['input_ids']]),use_cache=False).logits
            loss=loss+torch.nn.functional.cross_entropy(logits[:, :-1].float().reshape(-1,16),
                torch.tensor(row['labels'][1:]),ignore_index=-100,reduction='sum')
        (loss/tokens).backward()
        torch.nn.utils.clip_grad_norm_(oracle.parameters(),RECIPE['clip_grad_norm'])
        reference_optimizer.step();reference_scheduler.step()
        for ceiling,calls in ((None,1),(24,2)):
            with self.subTest(physical_token_ceiling=ceiling):
                model=copy.deepcopy(self.model);optimizer,scheduler=source_optimizer(model,RECIPE)
                result=train_source_step(model,optimizer,scheduler,self.rows,device=torch.device('cpu'),
                    recipe=RECIPE,capacity=256,distributed=False,packed_backend='dense-sdpa-reference',
                    maximum_packed_input_tokens=ceiling)
                self.assertEqual(result['real_forward_calls'],calls)
                self.assertEqual(len(result['packing_layout_digests']),1)
                self.assertEqual(len(result['physical_packing_layout_digests']),calls)
                self.assertEqual(result['global_sequence_count'],3)
                self.assertEqual(result['global_supervised_tokens'],tokens)
                self.assertFalse(result['fused_packing_verified'])
                self.assertEqual(result['missing_owned_gradient_shards'],[])
                self.assertEqual(result['owned_parameter_shards'],result['accumulated_parameter_shards'])
                for (_,actual),(_,expected) in zip(model.named_parameters(),oracle.named_parameters()):
                    torch.testing.assert_close(actual,expected,atol=1e-7,rtol=2e-5)
                    for key in ('exp_avg','exp_avg_sq'):
                        torch.testing.assert_close(optimizer.state[actual][key],reference_optimizer.state[expected][key],atol=1e-7,rtol=3e-5)

    def test_unequal_packed_slots_global_token_loss_and_zero_dummy_ddp(self):
        self._distributed_packing('ddp')

    def test_unequal_packed_fsdp_shards_match_global_weight_and_adam_oracle(self):
        self._distributed_packing('fsdp')

    def test_physical_fsdp_chunks_preserve_one_logical_pack_per_rank(self):
        self._distributed_packing('fsdp-physical')

    def _distributed_packing(self,mode):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            environment={**os.environ,'OMP_NUM_THREADS':'2','USE_LIBUV':'0','PYTHONIOENCODING':'utf-8'}
            processes=[];streams=[]
            try:
                for rank in range(2):
                    log=(Path(directory)/f'rank-{rank}.log').open('w',encoding='utf-8');streams.append(log)
                    processes.append(subprocess.Popen([sys.executable,'-m','tests.nvarc_qwen3_packing_strict',
                        'worker',directory,str(rank),str(port),mode],env=environment,stdout=log,stderr=subprocess.STDOUT))
                deadline=time.monotonic()+120
                while any(p.poll() is None for p in processes):
                    if time.monotonic()>deadline or any(p.poll() not in {None,0} for p in processes):
                        self.fail('Worker exit codes: '+str([p.poll() for p in processes])+'\n'+
                            '\n'.join(p.read_text(errors='replace')[-9000:] for p in Path(directory).glob('*.log')))
                    time.sleep(.2)
                self.assertEqual([0,0],[p.returncode for p in processes],
                    '\n'.join(p.read_text(errors='replace')[-9000:] for p in Path(directory).glob('*.log')))
            finally:
                for p in processes:
                    if p.poll() is None:p.kill()
                    p.wait(timeout=10)
                for stream in streams:stream.close()
            proof=json.loads((Path(directory)/'proof.json').read_bytes())
            self.assertEqual(proof['real_calls'],[1,3])
            self.assertEqual(proof['dummy_calls'],[2,0])
            self.assertEqual(proof['collective_slots'],[3,3])
            self.assertTrue(proof['all_model_and_adam_moments_match_independent_global_oracle'])
            if mode=='fsdp-physical':self.assertEqual(proof['logical_pack_counts'],[1,1])

    def test_original_untied_source_epoch_checkpoint_and_cpu_adam_differential(self):
        from collections import Counter
        from peft import get_peft_model_state_dict
        from irisx.arc_nvarc_training import TaskLocalAdapter,task_local_sequences
        from irisx.arc_nvarc_qwen3_long_ttt import reserve_row,row_digest
        from tools.verify_nvarc_original_long_ttt import validate_progress
        # Published SFT differs from the tied base. Keep that distinction in
        # the real original-family adapter differential and exact reset.
        config=copy.deepcopy(self.model.config);config.tie_word_embeddings=False
        torch.manual_seed(19);base=Qwen3ForCausalLM(config).float()
        adaptation={'rank':2,'alpha':4,'seed':42,'use_rslora':True,'source_qwen':True,
            'training_schedule':'source-one-epoch','augmentation_count':16,'source_augmentation_seed':1,
            'max_sequence_length':8192,'learning_rate':5e-5,'warmup_ratio':.1,
            'clip_grad_norm':1.,'maximum_optimizer_steps':128,'maximum_training_tokens':1048576}
        task={'task_id':'original-tiny-public-fixture','train':[
            {'input':[[1,2]],'output':[[2,1]]},{'input':[[3,4]],'output':[[4,3]]}],
            'test':[{'input':[[5,6]]}]}
        reference=TaskLocalAdapter(copy.deepcopy(base),adaptation)
        actual=TaskLocalAdapter(copy.deepcopy(base),{**adaptation,'gradient_checkpointing':True,
            'optimizer_state_device':'cpu'})
        rows=task_local_sequences(task,seed=42,augmentation_count=16,source_qwen=True,
            source_augmentation_seed=1,source_max_length=8192)
        ledger={'outer_forwards_reserved':0,'input_tokens_reserved':0,'optimizer_steps_completed':0,
            'generation_calls':0,'teacher_calls':0,'verification_calls':0,'maximum_paid_usd':0,
            'forward_row_digests':[]}
        remaining=Counter(row_digest(row) for row in rows);events=[]
        def reserve(module,args,kwargs):
            reserve_row(ledger,remaining,{k:kwargs[k].tolist()[0] for k in ('input_ids','labels')},
                sum(len(row['input_ids']) for row in rows))
        def observe(event):
            ledger['optimizer_steps_completed']=event['completed_steps']
            events.append({'event':'ttt-optimizer-returned',**event})
        hook=actual.model.base_model.model.register_forward_pre_hook(reserve,with_kwargs=True)
        actual.step_observer=observe
        reference.adapt(task);actual.adapt(task)
        hook.remove();validate_progress(ledger,events,rows,True)
        self.assertFalse(any(remaining.values()))
        self.assertEqual(reference.last_observation['steps'],128)
        self.assertEqual(actual.last_observation['losses_by_step'],reference.last_observation['losses_by_step'])
        self.assertEqual(actual.last_observation['learning_rates_by_step'],reference.last_observation['learning_rates_by_step'])
        self.assertTrue(all(row['delta']==0 and all(row[k]>0 for k in ('attention','embedding','head','other'))
            for row in actual.last_observation['gradient_groups_by_step']))
        self.assertEqual(len(actual.targets),16)
        expected=get_peft_model_state_dict(reference.model)
        for name,value in get_peft_model_state_dict(actual.model).items():
            torch.testing.assert_close(value,expected[name],atol=0,rtol=0)
        actual.reset(clear_observation=False)
        for name,value in get_peft_model_state_dict(actual.model).items():
            torch.testing.assert_close(value,actual.initial[name],atol=0,rtol=0)


def ddp_worker(output,rank,port,mode):
    from datetime import timedelta
    import torch.distributed as dist
    from torch.nn.parallel import DistributedDataParallel as DDP
    from irisx.arc_nvarc_gpu_preflight_v2 import RECIPE
    from irisx.arc_nvarc_sft_step import source_optimizer,train_source_step
    os.environ.update(MASTER_ADDR='127.0.0.1',MASTER_PORT=str(port),RANK=str(rank),WORLD_SIZE='2',USE_LIBUV='0')
    dist.init_process_group('gloo',timeout=timedelta(seconds=90));torch.set_num_threads(2)
    fixture=OriginalQwen3PackingTests();fixture.setUp()
    short=fixture.rows[:2]
    long=[]
    for color in (1,2,3):
        ids=[14,11,10]+[color]*120+[15,14,12,10,4,15]
        long.append({'input_ids':ids,'labels':[-100]*(len(ids)-2)+[4,15]})
    rows=short if dist.get_rank()==0 else long
    if mode.startswith('fsdp'):
        from torch.distributed.fsdp import FullyShardedDataParallel as FSDP
        from torch.distributed.fsdp.wrap import ModuleWrapPolicy
        model=FSDP(copy.deepcopy(fixture.model),device_id=torch.device('cpu'),use_orig_params=True,
            auto_wrap_policy=ModuleWrapPolicy({type(fixture.model.model.layers[0])}),backward_prefetch=None)
    else:model=DDP(copy.deepcopy(fixture.model))
    # CPU DDP controls averaging; CPU FSDP additionally reconstructs shard
    # weights and moments. Neither establishes CUDA memory or throughput.
    model.config=model.module.config
    if mode=='ddp':model.clip_grad_norm_=lambda limit:torch.nn.utils.clip_grad_norm_(model.parameters(),limit)
    optimizer,scheduler=source_optimizer(model,RECIPE)
    observation=train_source_step(model,optimizer,scheduler,rows,device=torch.device('cpu'),
        recipe=RECIPE,capacity=768 if mode=='fsdp-physical' else 256,distributed=True,
        packed_backend='dense-sdpa-reference',maximum_packed_input_tokens=140 if mode=='fsdp-physical' else None)
    observations=[None,None];dist.all_gather_object(observations,observation)
    actual_model=actual_optimizer=None
    if mode.startswith('fsdp'):
        from torch.distributed.checkpoint.state_dict import StateDictOptions,get_state_dict
        actual_model,actual_optimizer=get_state_dict(model,optimizer,
            options=StateDictOptions(full_state_dict=True,cpu_offload=False))
    if dist.get_rank()==0:
        oracle=copy.deepcopy(fixture.model)
        ref_optimizer,ref_scheduler=source_optimizer(oracle,RECIPE)
        all_rows=short+long;supervised=sum(sum(x>=0 for x in row['labels'][1:]) for row in all_rows)
        loss=torch.tensor(0.0)
        for row in all_rows:
            logits=oracle(torch.tensor([row['input_ids']]),use_cache=False).logits
            loss=loss+torch.nn.functional.cross_entropy(logits[:, :-1].float().reshape(-1,16),
                torch.tensor(row['labels'][1:]),ignore_index=-100,reduction='sum')
        (loss/supervised).backward();torch.nn.utils.clip_grad_norm_(oracle.parameters(),RECIPE['clip_grad_norm'])
        ref_optimizer.step();ref_scheduler.step()
        if mode.startswith('fsdp'):
            from torch.distributed.checkpoint.state_dict import get_optimizer_state_dict
            for name,value in oracle.state_dict().items():
                torch.testing.assert_close(actual_model[name],value,atol=1e-7,rtol=2e-5)
            expected_optimizer=get_optimizer_state_dict(oracle,ref_optimizer)
            for name,state in expected_optimizer['state'].items():
                for key,value in state.items():
                    torch.testing.assert_close(actual_optimizer['state'][name][key],value,atol=1e-7,rtol=4e-5)
        else:
            for (_,actual),(_,expected) in zip(model.module.named_parameters(),oracle.named_parameters()):
                torch.testing.assert_close(actual,expected,atol=1e-7,rtol=2e-5)
                for key in ('exp_avg','exp_avg_sq'):
                    torch.testing.assert_close(optimizer.state[actual][key],ref_optimizer.state[expected][key],atol=1e-7,rtol=4e-5)
        proof={'real_calls':[r['real_forward_calls'] for r in observations],
            'logical_pack_counts':[len(r['packing_layout_digests']) for r in observations],
            'dummy_calls':[r['dummy_forward_calls'] for r in observations],
            'collective_slots':[r['collective_slots'] for r in observations],
            'all_model_and_adam_moments_match_independent_global_oracle':True,'global_supervised_tokens':supervised,
            'backend':mode,'gpu_evidence':False}
        (output/'proof.json').write_text(json.dumps(proof),encoding='utf-8')
    dist.barrier();dist.destroy_process_group()


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='worker':ddp_worker(Path(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),sys.argv[5])
    else:unittest.main()
