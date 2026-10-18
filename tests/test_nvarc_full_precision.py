"""Actual tiny-Qwen3 CPU proof, not official 2B/4B or CUDA validation."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.nvarc_posttrain_20261017.precision_contract import (
    LEGACY_POLICY, FP32_HEAD_POLICY, FP32_BACKBONE_POLICY, probability_tolerance,
    full_precision_execution_contract,
)
MISSING = [n for n in ('torch','transformers','peft','tokenizers','safetensors','pydantic')
           if importlib.util.find_spec(n) is None]
if not MISSING:
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine, example, origin, pin
    from tools.nvarc_posttrain_20261017.precision import (
        active_head, validate_policy, execution_receipt, full_precision_compute,
    )
    from tools.nvarc_posttrain_20261017.probability_trace import validate_trace, PAD_ID
    from tools.arc2_goal_sprint_20261017.model import adapter_state, state_digest, make_optimizer


def _cached(engine, trace, *, detach_cache=False, wrong_position=False):
    """Test-only attached graph, including original padding and EOS filler."""
    engine.model.eval()
    cache, values = None, []
    width, count = trace['padding_width'], trace['batch_size']
    lengths = trace['prompt_lengths']
    tokens = torch.tensor([[PAD_ID]*(width-len(p))+p for p in trace['prompts']])
    attention = torch.tensor([[0]*(width-len(p))+[1]*len(p) for p in trace['prompts']])
    positions = (attention.cumsum(-1)-1).clamp(min=0)
    for step, row in enumerate(trace['steps']):
        with engine.autocast():
            output = engine.model(input_ids=tokens, attention_mask=attention, position_ids=positions,
                                  past_key_values=cache, use_cache=True, logits_to_keep=1)
        cache = output.past_key_values
        if detach_cache:
            for layer in cache.layers:
                layer.keys, layer.values = layer.keys.detach(), layer.values.detach()
        logits = output.logits[:,-1,:].float()
        selected = torch.tensor(row['selected_ids'])[:,None]
        values.append(logits.gather(1,selected).squeeze(1)-torch.logsumexp(logits,-1))
        tokens = selected
        attention = torch.cat((attention,attention.new_ones((count,1))),1)
        positions = torch.tensor([[n+step+int(wrong_position)] for n in lengths])
    return torch.stack(values,1)


@unittest.skipIf(bool(MISSING), 'Optional actual model dependencies unavailable: '+', '.join(MISSING))
class FullPrecisionPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def engine(self, policy=FP32_BACKBONE_POLICY):
        return tiny_engine(dtype=torch.bfloat16, probability_policy=policy)

    def test_exact_bf16_source_and_adapter_values_and_rng_preserved(self):
        before = torch.random.get_rng_state().clone()
        old = self.engine(FP32_HEAD_POLICY)
        after_old = torch.random.get_rng_state().clone()
        full = self.engine()
        self.assertTrue(torch.equal(before, after_old))
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))
        a, b = dict(old.model.named_parameters()), dict(full.model.named_parameters())
        self.assertEqual(set(a),set(b))
        for name in a:
            self.assertEqual(a[name].requires_grad,b[name].requires_grad,name)
            self.assertEqual(b[name].dtype,torch.float32,name)
            self.assertTrue(torch.equal(a[name].float(),b[name]),name)
        self.assertEqual(full.base_dtype,torch.float32)
        self.assertEqual(full.source_base_dtype,torch.bfloat16)
        self.assertEqual(full.base_identity,old.base_identity)
        self.assertTrue(torch.equal(full.generator.get_state(),old.generator.get_state()))
        self.assertEqual(state_digest(adapter_state(full.model)),state_digest(adapter_state(old.model)))

    def test_source_fp32_is_not_silently_admitted(self):
        with self.assertRaisesRegex(ValueError,'original BF16'):
            tiny_engine(dtype=torch.float32,probability_policy=FP32_BACKBONE_POLICY)

    def test_active_backend_receipt_and_scope_restoration(self):
        engine=self.engine()
        old=(torch.get_float32_matmul_precision(),torch.backends.cuda.matmul.allow_tf32,
             torch.backends.cudnn.allow_tf32,torch.backends.cuda.flash_sdp_enabled(),
             torch.backends.cuda.mem_efficient_sdp_enabled(),torch.backends.cuda.cudnn_sdp_enabled())
        with torch.autocast('cpu',dtype=torch.bfloat16):
            with engine.autocast():
                receipt=execution_receipt(engine.model,engine.probability_policy,'cpu')
                self.assertFalse(torch.is_autocast_enabled('cpu'))
                self.assertEqual(receipt['sdpa_backends'],{'math':True,'flash':False,'memory_efficient':False,'cudnn':False})
                self.assertEqual(receipt['resident_parameter_dtypes'],['torch.float32'])
            self.assertTrue(torch.is_autocast_enabled('cpu'))
        new=(torch.get_float32_matmul_precision(),torch.backends.cuda.matmul.allow_tf32,
             torch.backends.cudnn.allow_tf32,torch.backends.cuda.flash_sdp_enabled(),
             torch.backends.cuda.mem_efficient_sdp_enabled(),torch.backends.cuda.cudnn_sdp_enabled())
        self.assertEqual(old,new)
        self.assertEqual(engine.probability_execution_receipt()['source_base_dtype'],'torch.bfloat16')
        self.assertEqual(engine.probability_execution_receipt(),full_precision_execution_contract())
        with self.assertRaisesRegex(ValueError,'active FP32/math'):
            execution_receipt(engine.model,engine.probability_policy,'cpu')
        with self.assertRaisesRegex(RuntimeError,'injected'):
            with engine.autocast():raise RuntimeError('injected')
        self.assertEqual(old,(torch.get_float32_matmul_precision(),torch.backends.cuda.matmul.allow_tf32,
             torch.backends.cudnn.allow_tf32,torch.backends.cuda.flash_sdp_enabled(),
             torch.backends.cuda.mem_efficient_sdp_enabled(),torch.backends.cuda.cudnn_sdp_enabled()))

    def test_actual_dtype_attention_and_checkpoint_mutations_fail_closed(self):
        engine=self.engine();frozen=next(p for p in engine.model.parameters() if not p.requires_grad)
        frozen.data=frozen.data.bfloat16()
        with self.assertRaisesRegex(ValueError,'FP32 backbone'):engine._checkpoint_admission()
        engine=self.engine();engine.model.config._attn_implementation='eager'
        with self.assertRaisesRegex(ValueError,'FP32 backbone'):engine._checkpoint_admission()
        engine=self.engine();engine.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
        with self.assertRaisesRegex(ValueError,'recomputation policy'):engine._checkpoint_admission()

    def test_checkpoint_recomputation_reenters_policy_after_forward_scope(self):
        engine=self.engine();observed=[]
        module=engine.model.get_base_model().model.layers[0].self_attn.q_proj
        def capture(*args):
            observed.append((torch.backends.cuda.flash_sdp_enabled(),torch.backends.cuda.matmul.allow_tf32,
                             torch.is_autocast_enabled('cpu')))
        handle=module.register_forward_pre_hook(capture)
        try:
            item=example();values=engine.completion_logps(item['prompt_ids']+item['completion_ids'],len(item['prompt_ids']))
            forwards=len(observed)
            values.sum().backward()  # Deliberately outside the forward context.
        finally:handle.remove()
        self.assertGreater(len(observed),forwards)
        self.assertTrue(all(value==(False,False,False) for value in observed),observed)

    def test_fixed_tolerances_do_not_relax_old_policy(self):
        self.assertEqual(probability_tolerance(self.engine()),1e-5)
        self.assertEqual(probability_tolerance(SimpleNamespace(probability_policy=FP32_BACKBONE_POLICY,
                         contract={'variant':'2b'},base_dtype=torch.float32)),.05)
        self.assertEqual(probability_tolerance(self.engine(FP32_HEAD_POLICY)),.05)
        self.assertEqual(probability_tolerance(tiny_engine()),1e-5)

    def test_sampled_cached_full_gradients_and_detached_cache_negative_control(self):
        engine=self.engine()
        # Nonzero B exercises gradients into A as well as B, embedding and head.
        with torch.random.fork_rng(),torch.no_grad():
            torch.manual_seed(182)
            for name,p in engine.model.named_parameters():
                if '.lora_B.' in name:p.normal_(0,.002)
            active_head(engine.model).weight.mul_(24)
        prompt=example()['prompt_ids']+[1,2,3,4,5,6,7,8]*6
        trace={}
        with torch.no_grad():
            rows=engine._generate_batch([prompt,prompt[9:]],max_new_tokens=32,sample=True,
                                        deadline=time.time()+30,trace=trace)
        validate_trace(trace,expected_trace_sha256=trace['sha256'])
        self.assertGreater(trace['work']['generation_padding_tokens'],0)
        self.assertGreater(trace['work']['generation_finished_row_token_slots'],0)
        old=torch.tensor([s['selected_log_probs'] for s in trace['steps']]).T
        def gradients():return {n:p.grad.detach().clone() for n,p in engine.model.named_parameters()
                               if p.requires_grad and p.grad is not None}
        with engine.autocast():
            values=_cached(engine,trace)
            self.assertTrue(torch.equal(values.detach(),old))
            (-sum(values[i,:len(r['completion_ids'])].mean() for i,r in enumerate(rows))).backward()
        exact=gradients();engine.model.zero_grad(set_to_none=True)
        full=[]
        with engine.autocast():
            for row in rows:
                full.append(engine.completion_logps(row['input_ids'],row['prompt_length'])[row['prompt_length']:])
            (-sum(v.mean() for v in full)).backward()
        reference=gradients()
        for i,v in enumerate(full):torch.testing.assert_close(v,old[i,:len(v)],atol=1e-5,rtol=0)
        for name,value in exact.items():
            self.assertTrue(bool(torch.isfinite(value).all()),name)
            torch.testing.assert_close(value,reference[name],atol=1e-5,rtol=1e-5)
        for fragment in ('lora_A','lora_B','embed_tokens','lm_head'):
            self.assertGreater(sum(v.abs().sum().item() for n,v in exact.items() if fragment in n),0)
        engine.model.zero_grad(set_to_none=True)
        with engine.autocast():
            detached=_cached(engine,trace,detach_cache=True)
            self.assertTrue(torch.equal(detached.detach(),old))
            (-sum(detached[i,:len(r['completion_ids'])].mean() for i,r in enumerate(rows))).backward()
        wrong=gradients()
        self.assertGreater(max((exact[n]-wrong[n]).abs().max().item() for n in exact),.1)
        with torch.no_grad():
            displaced=_cached(engine,trace,wrong_position=True)
        self.assertGreater((displaced-old).abs().max().item(),1e-4)
        # Fresh likelihood remains dependent on current weights, not old logps.
        with torch.no_grad():active_head(engine.model).weight[1].add_(.2)
        with torch.no_grad():changed=_cached(engine,trace)
        self.assertGreater((changed-old).abs().max().item(),1e-4)

    def test_real_update_and_checkpoint_identity_remain_policy_bound(self):
        engine=self.engine();before=state_digest(adapter_state(engine.model))
        frozen={n:p.detach().clone() for n,p in engine.model.named_parameters() if not p.requires_grad}
        report=engine.sft_step(example(),make_optimizer(engine.model,1e-3),deadline=time.time()+30)
        self.assertTrue(report['updated']);self.assertNotEqual(before,state_digest(adapter_state(engine.model)))
        for n,p in engine.model.named_parameters():
            if n in frozen:self.assertTrue(torch.equal(p,frozen[n]),n)
        with tempfile.TemporaryDirectory() as directory:
            saved=engine.save_checkpoint(Path(directory)/'full',origin=origin())
            manifest=json.loads((Path(saved['root'])/'manifest.json').read_text())
            self.assertEqual(manifest['trainable_contract']['probability_policy'],FP32_BACKBONE_POLICY)
            self.assertEqual(manifest['trainable_contract']['frozen_dtype'],'torch.float32')
            self.assertEqual(self.engine().load_checkpoint(pin(saved))['state_sha256'],saved['state_sha256'])
            with self.assertRaisesRegex(ValueError,'contract differs'):
                self.engine(FP32_HEAD_POLICY).load_checkpoint(pin(saved))

    def test_actual_ddis_update_and_full_policy_hash(self):
        from tools.nvarc_posttrain_20261017.matched_controls import full_policy_sha256
        engine=self.engine();anchor=full_policy_sha256(engine)
        engine.probability_execution_receipt()
        self.assertEqual(anchor,full_policy_sha256(engine))
        rows=engine.generate(example()['prompt_ids'],count=4,max_new_tokens=4,sample=True)
        for index,row in enumerate(rows):
            row.update(sample_id=f's{index}',group_id=f'g{index//2}',reward=float(index%2))
        report=engine.af3_update(rows,make_optimizer(engine.model,1e-3),
                                 expected_groups=['g0','g1'],group_size=2,deadline=time.time()+30)
        self.assertTrue(report['updated'])
        self.assertEqual(report['replayed'],4)
        self.assertEqual(report['mixed_groups'],2)
        self.assertLess(report['max_replay_logp_gap'],1e-5)
        self.assertNotEqual(anchor,full_policy_sha256(engine))

if __name__=='__main__':unittest.main()
