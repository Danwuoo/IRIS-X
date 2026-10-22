"""Focused actual JAX/NNX tests; these are not 35B or TPU evidence."""
import json
from pathlib import Path
import tempfile
import unittest
import jax
import jax.numpy as jnp
import numpy as np
import optax
from flax import nnx
import orbax.checkpoint as ocp
from tools.qwen35_bf16_optimizer_20261021.optimizer import (
    BF16StochasticOptimizer, POLICY, round_bf16, stochastic_apply_updates, policy_binding, validate_policy_binding)

class ArrayModel(nnx.Module):
    def __init__(self):
        self.weight = nnx.Param(jnp.full((32, 32), 0.02, dtype=jnp.bfloat16))
        self.native_fp32 = nnx.Param(jnp.array([0.25, -0.125], dtype=jnp.float32))
    def __call__(self, x):
        return jnp.matmul(x.astype(jnp.bfloat16), self.weight[...]).astype(jnp.float32) + self.native_fp32[0]

def loss(model, x, y):
    return jnp.mean(jnp.square(model(x) - y))

def create(seed=1751):
    model = ArrayModel()
    tx = optax.adamw(1e-5, b1=.9, b2=.95, eps=1e-8, weight_decay=0., mu_dtype=jnp.bfloat16)
    return model, BF16StochasticOptimizer(model, tx, seed=seed)

def pure_checkpoint(model, optimizer):
    return {'params': nnx.as_pure(nnx.state(model, nnx.Param)),
            'opt_state': nnx.as_pure(optimizer.opt_state), 'step': optimizer.step[...]}

def restore(model, optimizer, state):
    nnx.update(model, state['params'])
    nnx.update(optimizer.opt_state, nnx.state(state['opt_state'], graph=optimizer.graph))
    optimizer.step[...] = state['step']

def assert_tree_equal(case, a, b):
    case.assertEqual(jax.tree.structure(a), jax.tree.structure(b))
    for x,y in zip(jax.tree.leaves(a),jax.tree.leaves(b),strict=True):
        np.testing.assert_array_equal(np.asarray(x),np.asarray(y))

class Tests(unittest.TestCase):
    def test_resume_policy_bound_before_restore(self):
        saved=policy_binding(1751);validate_policy_binding(saved,1751)
        with self.assertRaises(ValueError):validate_policy_binding(saved,1752)
        changed=dict(saved,jax='different')
        with self.assertRaises(ValueError):validate_policy_binding(changed,1751)

    def test_exact_and_adjacent_negative(self):
        a=jnp.array([.02,-.02,0.,-0.,1.,-1.],jnp.float32)
        bits=jax.lax.bitcast_convert_type(a,jnp.uint32)
        zeros=jnp.zeros(a.shape,jnp.uint32);ones=jnp.full(a.shape,65535,jnp.uint32)
        away=round_bf16(a,zeros);toward=round_bf16(a,ones)
        np.testing.assert_array_equal(jax.lax.bitcast_convert_type(toward,jnp.uint16),bits>>16)
        np.testing.assert_array_equal(jax.lax.bitcast_convert_type(away,jnp.uint16),(bits>>16)+((bits&65535)>0))
        exact=a.astype(jnp.bfloat16).astype(jnp.float32)
        np.testing.assert_array_equal(round_bf16(exact,zeros),round_bf16(exact,ones))

    def test_same_key_and_global_shape_reproducible(self):
        p={'weight':jnp.full((64,64),.02,jnp.bfloat16)}
        u={'weight':jnp.full((64,64),1e-5,jnp.float32)}
        f=jax.jit(lambda p,u:stochastic_apply_updates(p,u,seed=9,step=jnp.uint32(4)))
        a,valid=f(p,u);b,valid2=f(p,u)
        self.assertTrue(bool(valid & valid2));assert_tree_equal(self,a,b)
        self.assertGreater(np.count_nonzero(np.asarray(a['weight']!=p['weight'])),50)
        np.testing.assert_array_equal(optax.apply_updates(p,u)['weight'],p['weight'])

    def test_native_fp32_preserved_and_dtype_rejected(self):
        p={'island':jnp.array([.02],jnp.float32)};u={'island':jnp.array([1e-5],jnp.float32)}
        out,valid=stochastic_apply_updates(p,u,seed=1,step=0)
        self.assertTrue(bool(valid));self.assertEqual(out['island'].dtype,jnp.float32)
        np.testing.assert_array_equal(out['island'],p['island']+u['island'])
        with self.assertRaises(TypeError):
            stochastic_apply_updates({'x':jnp.ones(2,jnp.float16)},{'x':jnp.ones(2,jnp.float16)},seed=1,step=0)

    def test_actual_gradients_and_jitted_update(self):
        model,opt=create();x=jnp.eye(32);y=jnp.zeros((32,32))
        @nnx.jit
        def step(model,opt,x,y):
            value,grads=nnx.value_and_grad(loss)(model,x,y)
            receipt=opt.update(model,grads)
            return value,receipt
        before=np.asarray(model.weight[...]).copy();first=float(loss(model,x,y))
        receipts=[]
        for _ in range(8):
            value,receipt=step(model,opt,x,y);self.assertTrue(bool(receipt['accepted']));receipts.append(float(value))
        self.assertEqual(int(opt.step[...]),8)
        self.assertGreater(np.count_nonzero(before!=np.asarray(model.weight[...])),0)
        self.assertLess(float(loss(model,x,y)),first)
        self.assertEqual(model.weight[...].dtype,jnp.bfloat16)
        self.assertEqual(model.native_fp32[...].dtype,jnp.float32)
        state=nnx.as_pure(opt.opt_state)
        adam=jax.tree.leaves(state)
        self.assertTrue(any(x.dtype==jnp.bfloat16 for x in adam if hasattr(x,'dtype')))

    def test_rejected_nonfinite_never_mutates(self):
        model,opt=create();before=pure_checkpoint(model,opt)
        grads=nnx.grad(loss)(model,jnp.eye(32),jnp.zeros((32,32)))
        grads['weight'][...]=jnp.full((32,32),jnp.nan,jnp.bfloat16)
        receipt=opt.update(model,grads)
        self.assertFalse(bool(receipt['accepted']));assert_tree_equal(self,before,pure_checkpoint(model,opt))

    def test_orbax_checkpoint_resume_next_real_update(self):
        model,opt=create();x=jnp.eye(32);y=jnp.zeros((32,32))
        def step(m,o):
            g=nnx.grad(loss)(m,x,y);return o.update(m,g)
        step(model,opt)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state';checkpointer=ocp.PyTreeCheckpointer()
            checkpointer.save(str(path),pure_checkpoint(model,opt))
            binding=policy_binding(opt.sr_seed)
            restored=checkpointer.restore(str(path),item=pure_checkpoint(model,opt))
            step(model,opt);expected=pure_checkpoint(model,opt)
            model2,opt2=create();validate_policy_binding(binding,opt2.sr_seed);restore(model2,opt2,restored);step(model2,opt2)
            assert_tree_equal(self,expected,pure_checkpoint(model2,opt2))
            model3,opt3=create(seed=1752);restore(model3,opt3,restored);step(model3,opt3)
            self.assertFalse(np.array_equal(np.asarray(model.weight[...]),np.asarray(model3.weight[...])))

if __name__=='__main__':unittest.main()
