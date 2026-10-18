"""Real CPU mechanism tests. Synthetic tensors are not official accuracy evidence."""
from __future__ import annotations
import copy
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

MISSING=[n for n in ('torch','transformers','peft','tokenizers','safetensors') if importlib.util.find_spec(n) is None]
if not MISSING:
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine,example,origin,pin
    from tools.nvarc_width_20261018 import model as w,expansion as x
    from tools.nvarc_posttrain_20261017.engine import FatalUpdateError
    from tools.arc2_goal_sprint_20261017.model import make_optimizer,adapter_state,state_digest


def dense():
    return tiny_engine(dtype=torch.bfloat16,probability_policy='fp32-backbone-math-v1',adapter_seed=731,sample_seed=20261018)

def engine(treatment='width8192'):
    return w.from_dense(dense(),treatment)


@unittest.skipIf(bool(MISSING),'optional ML dependencies missing')
class WidthModelCPU(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_exact_official_count_and_active_cost(self):
        expected={'initial_anchor':(1409475584,69795840,1479271424),'baseline':(1409475584,69795840,1479271424),
                  'width8192':(1761797120,80805888,1842603008)}
        for t,counts in expected.items():
            a=w.official_accounting(t)
            self.assertEqual(tuple(a[k] for k in ('frozen_parameters','trainable_parameters','total_resident_parameters')),counts)
        a,b=w.official_accounting('baseline'),w.official_accounting('width8192')
        self.assertEqual(b['added_native_parameters'],352321536)
        self.assertEqual(b['trainable_parameters']-a['trainable_parameters'],11010048)
        self.assertGreater(b['linear_forward_flops_per_token'],a['linear_forward_flops_per_token'])
        self.assertFalse(b['equal_compute_claimed']);self.assertIsNone(b['actual_peak_memory_bytes'])

    def test_mapped_source_and_PEFT_and_global_rng_unchanged(self):
        d=dense();raw=d.model.get_base_model();original={n:p.detach().clone() for n,p in d.model.named_parameters()}
        before_rng=torch.random.get_rng_state().clone()
        e=w.from_dense(d,'width8192');self.assertTrue(torch.equal(before_rng,torch.random.get_rng_state()))
        current=dict(e.model.named_parameters())
        for name,value in original.items():
            if '.mlp.' not in name:self.assertTrue(torch.equal(value,current[name]),name)
        for i,layer in enumerate(raw.model.layers):
            ids,_=x.replica_indices(64,85,i);m=layer.mlp
            stem=f'base_model.model.model.layers.{i}.mlp.'
            g=original[stem+'gate_proj.base_layer.weight'];u=original[stem+'up_proj.base_layer.weight'];down=original[stem+'down_proj.base_layer.weight']
            self.assertTrue(torch.equal(m.gate_proj.base_layer.weight[:64],g))
            self.assertTrue(torch.equal(m.gate_proj.base_layer.weight[64:],g[ids]))
            self.assertTrue(torch.equal(m.up_proj.base_layer.weight[ids]+m.up_proj.base_layer.weight[64:],2*u[ids]))
            self.assertTrue(torch.equal(m.down_proj.base_layer.weight[:,ids]*2,down[:,ids]))
            self.assertTrue(torch.equal(m.down_proj.base_layer.weight[:,64:],m.down_proj.base_layer.weight[:,ids]))
            self.assertTrue(torch.equal(m.down_proj.lora_A['default'].weight[:,:64],original[stem+'down_proj.lora_A.default.weight']))
            self.assertTrue(torch.equal(m.down_proj.lora_A['default'].weight[:,64:],m.down_proj.lora_A['default'].weight[:,64:].bfloat16().float()))
        self.assertEqual(e.initial_function_receipt['greedy_tokens_equal'],True)
        self.assertLess(e.initial_function_receipt['full_and_cached_max_absolute_logit_gap'],1e-5)

    def test_initial_anchor_and_baseline_are_exact_same_native_and_adapter_bytes(self):
        a,b=engine('initial_anchor'),engine('baseline')
        self.assertEqual(w._digest(dict(a.model.named_parameters())),w._digest(dict(b.model.named_parameters())))
        self.assertEqual(a.initial_function_receipt['full_and_cached_max_absolute_logit_gap'],0.)
        self.assertEqual(b.initial_function_receipt['full_and_cached_max_absolute_logit_gap'],0.)

    def test_forward_and_input_gradient_preservation_and_real_specialization(self):
        d=dense();m=d.model.get_base_model().model.layers[0].mlp
        g=torch.Generator().manual_seed(20261018)
        values=torch.randn((1,24,32),generator=g,requires_grad=True)
        target=torch.randn((1,24,32),generator=g)
        before=m(values);grad=torch.autograd.grad((before-target).square().mean(),values)[0]
        x.widen_mlp(m,85,layer_index=0);after=m(values)
        agrad=torch.autograd.grad((after-target).square().mean(),values)[0]
        self.assertLess(float((before-after).detach().abs().max()),1e-5)
        self.assertLess(float((grad-agrad).abs().max()),1e-6)
        frozen=w._digest({n:p for n,p in m.named_parameters() if not p.requires_grad})
        ids,_=x.replica_indices(64,85,0)
        optimizer=torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],lr=2e-5,weight_decay=.01)
        for step in range(2):
            optimizer.zero_grad(set_to_none=True)
            loss=(m(values)-target).square().mean();loss.backward()
            for n,p in m.named_parameters():
                if p.requires_grad:
                    self.assertTrue(torch.isfinite(p.grad).all())
                    self.assertEqual(bool(p.grad.count_nonzero()),step>0 or '.lora_B.' in n,n)
                else:self.assertIsNone(p.grad)
            bg=m.gate_proj.lora_B['default'].weight.grad
            self.assertTrue(((bg[ids]-bg[64:]).norm(dim=1)>0).all())
            optimizer.step()
            b=m.gate_proj.lora_B['default'].weight
            self.assertTrue(((b[ids]-b[64:]).norm(dim=1)>0).all())
        self.assertEqual(frozen,w._digest({n:p for n,p in m.named_parameters() if not p.requires_grad}))

    def test_nonzero_adapter_or_used_or_wrong_precision_inputs_rejected(self):
        d=dense()
        with torch.no_grad():d.model.get_base_model().model.layers[0].mlp.gate_proj.lora_B['default'].weight[0,0]=1e-3
        with self.assertRaisesRegex(ValueError,'zero-B'):w.from_dense(d,'width8192')
        d=dense();d.forward_calls=1
        with self.assertRaisesRegex(ValueError,'unused'):w.from_dense(d,'width8192')
        d=dense();m=d.model.get_base_model().model.layers[0].mlp;m.bfloat16()
        with self.assertRaisesRegex(ValueError,'FP32'):x.widen_mlp(m,85,layer_index=0)
        with self.assertRaisesRegex(ValueError,'bounded'):w.from_dense(dense(),'width8192',fixture_width=129)

    def test_failed_initial_function_gate_poisons_consumed_engine_without_relaxation(self):
        d=dense();original=w._probe;calls=0
        def broken(model):
            nonlocal calls
            row=list(original(model));calls+=1
            if calls==2:row[0]=row[0]+1.
            return tuple(row)
        with patch.object(w,'_probe',side_effect=broken),self.assertRaisesRegex(ValueError,'function preservation'):
            w.from_dense(d,'width8192')
        self.assertTrue(d._fatal_update)

    def test_tampered_frozen_geometry_precision_and_receipt_fail_closed(self):
        for key in ('frozen','shape','config','receipt'):
            e=engine()
            if key=='frozen':
                with torch.no_grad():e.model.get_base_model().model.layers[0].mlp.up_proj.base_layer.weight[0,0]+=1
            elif key=='shape':e.model.get_base_model().model.layers[0].mlp.up_proj.in_features+=1
            elif key=='config':e.model.config.hidden_size+=1
            else:e.contract['width_v1']['construction']['delta_fraction']=.1
            with self.assertRaises(ValueError):e._checkpoint_admission()

    def test_serialization_after_real_update_reloads_exact_and_cross_arm_rejected(self):
        e=engine();opt=make_optimizer(e.model,2e-5)
        result=e.sft_step(example(),opt,deadline=time.time()+20);self.assertTrue(result['updated'])
        opt.zero_grad(set_to_none=True)
        with tempfile.TemporaryDirectory() as directory:
            saved=e.save_checkpoint(Path(directory)/'width',origin=origin())
            fresh=engine();fresh.load_checkpoint(pin(saved))
            self.assertEqual(state_digest(adapter_state(e.model)),state_digest(adapter_state(fresh.model)))
            for model in (e.model,fresh.model):model.eval()
            ids=torch.tensor([[14,11,10,1,15,10,14,12,10]])
            with torch.no_grad():self.assertTrue(torch.equal(e.model(ids).logits,fresh.model(ids).logits))
            with self.assertRaisesRegex(ValueError,'contract|identity'):engine('baseline').load_checkpoint(pin(saved))

    def test_nonfinite_update_poison_preserves_inherited_abort_contract(self):
        e=engine();opt=make_optimizer(e.model,2e-5)
        original=opt.step
        def bad(*args,**kwargs):
            out=original(*args,**kwargs)
            with torch.no_grad():e.parameters[0].view(-1)[0]=float('nan')
            return out
        opt.step=bad
        with self.assertRaises(FatalUpdateError):e.sft_step(example(),opt,deadline=time.time()+20)
        self.assertTrue(e._fatal_update)
        with self.assertRaises(FatalUpdateError):e._healthy()
