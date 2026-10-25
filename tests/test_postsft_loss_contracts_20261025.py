"""Synthetic-only tests; no corpus, model or external calls."""
import unittest
from tools.postsft_loss_contracts_20261025 import query_spans as q
try:
    import torch
except ImportError:
    torch = None
if torch is not None:
    from tools.postsft_loss_contracts_20261025 import objectives as o


def frame(role, body):
    return [14, role, 10] + body + [15]


class Spans(unittest.TestCase):
    def setUp(self):
        self.prompt = (frame(11, [1]) + frame(12, [2]) + frame(11, [3]) + [14,12,10])
        self.ids = self.prompt + [4,15,13,13]
        self.mask = [1]*(len(self.ids)-2)+[0,0]

    def test_answer_eos_once_shift(self):
        r=q.query_response_view(self.ids,self.mask,query_prompt_ids=self.prompt)
        self.assertEqual(r['target_ids'],[4,15])
        self.assertEqual(r['prediction_positions'],[len(self.prompt)-1,len(self.prompt)])
        self.assertEqual(r['aligned_labels'][-2:],[-100,-100])
        self.assertTrue(all(x==-100 for x in r['aligned_labels'][:len(self.prompt)]))

    def test_bad_padding_and_double_shift(self):
        bad=self.ids[:];bad[-1]=0
        with self.assertRaises(ValueError):q.query_response_view(bad,self.mask,query_prompt_ids=self.prompt)
        with self.assertRaises(ValueError):
            q.validate_logprob_alignment(self.ids,self.mask,[len(self.prompt),len(self.prompt)+1],[4,15],query_prompt_ids=self.prompt)

    def test_injected_frame_cannot_move_query(self):
        ids=self.prompt+[4,15]+frame(11,[5])+frame(12,[6])
        with self.assertRaises(ValueError):q.query_response_view(ids,[1]*len(ids),query_prompt_ids=self.prompt)


@unittest.skipIf(torch is None,'Torch unavailable: optional tensor contracts NOT VERIFIED')
class Losses(unittest.TestCase):
    def test_global_token_mean_not_mean_of_means(self):
        a=torch.tensor([-1.],requires_grad=True);b=torch.tensor([-2.,-2.,-2.],requires_grad=True)
        total=o.winner_nll([a,b]);distributed=o.winner_nll([a],global_tokens=4)+o.winner_nll([b],global_tokens=4)
        torch.testing.assert_close(total,distributed)
        self.assertEqual(float(total),1.75)
        self.assertNotEqual(float(total),float((o.winner_nll([a])+o.winner_nll([b]))/2))

    def test_dpo_single_vs_four_replicated_sum_gradient(self):
        def calc(world):
            x=torch.tensor(-.8,requires_grad=True)
            c=x.expand(2);r=(2*x).expand(3)
            loss=sum(o.dpo([c],[r],[torch.full((2,),-.8)],[torch.full((3,),-1.6)],global_pairs=world) for _ in range(world))
            loss.backward();return loss.detach(),x.grad
        a=calc(1);b=calc(4)
        for x,y in zip(a,b):torch.testing.assert_close(x,y)

    def test_reference_must_be_frozen(self):
        x=torch.tensor([-.5],requires_grad=True)
        with self.assertRaises(ValueError):o.dpo([x],[x],[x],[x])

    def test_uniform_rewards_no_update(self):
        xs=[torch.tensor([-.5],requires_grad=True) for _ in range(4)]
        ref=[x.detach().clone() for x in xs]
        for reward in [torch.zeros(4),torch.ones(4)]:
            loss,meta=o.grpo(xs,ref,ref,reward)
            self.assertIsNone(loss);self.assertFalse(meta['optimizer_commit_allowed'])

    def test_mixed_g4_finite_gradient_and_invalid_reward(self):
        xs=[torch.tensor([-.5,-.4],requires_grad=True) for _ in range(4)]
        ref=[x.detach().clone() for x in xs]
        loss,meta=o.grpo(xs,ref,ref,torch.tensor([0.,1.,0.,1.]))
        self.assertTrue(meta['optimizer_commit_allowed']);loss.backward()
        self.assertTrue(all(bool(torch.isfinite(x.grad).all()) for x in xs))
        self.assertGreater(sum(float(x.grad.abs().sum()) for x in xs),0)
        with self.assertRaises(ValueError):o.grpo(xs,ref,ref,torch.tensor([0.,.5,0.,1.]))


if __name__=='__main__':
    unittest.main()
