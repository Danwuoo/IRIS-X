"""Actual tensor/gradient/checkpoint and exception restoration; no CUDA claim."""
import copy
import unittest
import torch
from torch.utils.checkpoint import checkpoint

from irisx.arc_nvarc_segmented_linear import segmented_linear
from irisx.errors import ValidationError


class SegmentedLinearStrictTests(unittest.TestCase):
    def test_independent_gradients_match_with_unequal_samples_and_checkpoint(self):
        torch.manual_seed(881)
        reference=torch.nn.Sequential(torch.nn.Linear(7,11),torch.nn.SiLU(),torch.nn.Linear(11,5))
        packed=copy.deepcopy(reference)
        rows=[torch.randn(1,n,7,requires_grad=True) for n in (3,5,2)]
        value=torch.cat([row.detach() for row in rows],1).requires_grad_()
        wanted=torch.cat([reference(row) for row in rows],1)
        wanted.square().sum().backward()
        before={name:parameter.detach().clone() for name,parameter in packed.named_parameters()}
        with segmented_linear(packed,[0,3,8,10]) as state:
            actual=checkpoint(packed,value,use_reentrant=False)
            torch.testing.assert_close(actual,wanted,atol=0,rtol=0)
            actual.square().sum().backward()
            self.assertTrue(all(count==2 for count in state['linear_calls_by_name'].values()))
            self.assertEqual(state['segment_gemm_calls'],12)
        for (name,left),(_,right) in zip(packed.named_parameters(),reference.named_parameters()):
            torch.testing.assert_close(left.grad,right.grad,atol=1e-6,rtol=1e-6)
            torch.testing.assert_close(left,before[name],atol=0,rtol=0)
        torch.testing.assert_close(value.grad,torch.cat([row.grad for row in rows],1),atol=1e-6,rtol=1e-6)
        self.assertTrue(all('forward' not in module.__dict__ for module in packed if isinstance(module,torch.nn.Linear)))

    def test_failure_offsets_dtype_and_preexisting_override_do_not_leak_methods(self):
        model=torch.nn.Sequential(torch.nn.Linear(3,4),torch.nn.Linear(4,2))
        for offsets in ([1,3],[0,3,2],[0,True,3],[0,0,3],range(10)):
            with self.assertRaises(ValidationError):
                with segmented_linear(model,offsets):pass
        for value in (torch.ones(2,3,3),torch.ones(1,2,3),torch.ones(1,3,3,dtype=torch.float64)):
            with self.assertRaises(ValidationError):
                with segmented_linear(model,[0,3]):model(value)
            self.assertNotIn('forward',model[0].__dict__)
            self.assertNotIn('forward',model[1].__dict__)
        original=lambda value:value
        model[1].forward=original
        with self.assertRaises(ValidationError):
            with segmented_linear(model,[0,3]):pass
        self.assertNotIn('forward',model[0].__dict__)
        self.assertIs(model[1].forward,original)


if __name__=='__main__':unittest.main()
