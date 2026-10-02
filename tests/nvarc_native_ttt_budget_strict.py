"""Actual CPU NN/AdamW exercise of native-epoch guards, not native Unsloth parity."""
import copy
import math
import unittest
import torch
from types import SimpleNamespace
from tools.nvarc_native_ttt_budget import EpochBudget,digest


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__();self.embed=torch.nn.Embedding(16,4);self.head=torch.nn.Linear(4,16,bias=False)
    def forward(self,input_ids,labels):
        return {'loss':torch.nn.functional.cross_entropy(self.head(self.embed(input_ids)).reshape(-1,16),labels.reshape(-1))}


class Trainer:
    def __init__(self,model):self.model=model
    def training_step(self,batch):
        loss=self.model(**batch)['loss'];loss.backward();return loss.detach()


class NativeEpochStrictTests(unittest.TestCase):
    def budget(self):
        torch.manual_seed(42);model=Model();trainer=Trainer(model)
        batches=[{'input_ids':torch.tensor([[14,11,2,15]]),'labels':torch.tensor([[-100,-100,2,15]])},
            {'input_ids':torch.tensor([[14,11,3,15]]),'labels':torch.tensor([[-100,-100,3,15]])}]
        rows=[{'input_ids_digest':digest(batch['input_ids'][0].tolist()),'labels_digest':digest(batch['labels'][0].tolist())} for batch in batches]
        retained=[];budget=EpochBudget(torch,model,trainer,rows,[0.,5e-5,0.],lambda value:retained.append(copy.deepcopy(value)),
            expected_parameters=sum(p.numel() for p in model.parameters()),expected_dtype='torch.float32')
        return model,trainer,batches,budget,retained

    def test_real_epoch_tracks_zero_lr_moments_and_restores_all_patched_calls(self):
        model,trainer,batches,budget,retained=self.budget();constructor,step=torch.optim.AdamW.__init__,torch.optim.AdamW.step
        before=[p.detach().clone() for p in model.parameters()]
        with budget.installed():
            optimizer=torch.optim.AdamW(model.parameters(),lr=5e-5,betas=(.9,.999),eps=1e-8,weight_decay=0)
            scheduler=torch.optim.lr_scheduler.LambdaLR(optimizer,lambda i:[0.,1.,0.][i])
            for i,batch in enumerate(batches):
                trainer.training_step(batch);torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
                optimizer.step()
                if i==0:
                    self.assertTrue(all(torch.equal(a,p) for a,p in zip(before,model.parameters())))
                    self.assertTrue(any(torch.count_nonzero(s['exp_avg']) for s in optimizer.state.values()))
                optimizer.zero_grad(set_to_none=True);scheduler.step()
            self.assertEqual(len(budget.complete()),2)
            with self.assertRaises(RuntimeError):trainer.training_step(batches[0])
            with self.assertRaises(RuntimeError):model.generate()
        self.assertIs(torch.optim.AdamW.__init__,constructor);self.assertIs(torch.optim.AdamW.step,step)
        self.assertEqual(len(retained[-1]['optimizer_steps']),2)
        self.assertTrue(all(row['completed'] for row in retained[-1]['optimizer_steps']))
        self.assertTrue(any(not torch.equal(a,p) for a,p in zip(before,model.parameters())))

    def test_bad_row_and_unreserved_optimizer_fail_before_nn_or_update(self):
        model,trainer,batches,budget,_=self.budget();entered=[]
        hook=model.register_forward_hook(lambda *args:entered.append(1))
        original=torch.optim.AdamW.step
        with self.assertRaises(RuntimeError),budget.installed():
            bad={**batches[0],'input_ids':batches[0]['input_ids']+1};trainer.training_step(bad)
        hook.remove();self.assertEqual(entered,[]);self.assertIs(torch.optim.AdamW.step,original)
        _,_,_,budget,_=self.budget()
        with budget.installed():
            optimizer=torch.optim.AdamW(budget.model.parameters(),lr=5e-5,betas=(.9,.999),weight_decay=0)
            with self.assertRaises(RuntimeError):optimizer.step()
            with self.assertRaises(RuntimeError):torch.optim.AdamW(budget.model.parameters())

    def test_actual_bf16_moments_and_zero_lr_step_without_a_master_cast(self):
        model,trainer,batches,old,_=self.budget();model=model.to(torch.bfloat16)
        with torch.no_grad():model.head.weight.zero_()
        rows=[{'input_ids_digest':digest(batch['input_ids'][0].tolist()),'labels_digest':digest(batch['labels'][0].tolist())} for batch in batches]
        budget=EpochBudget(torch,model,trainer,rows,[0.,5e-5,0.],lambda value:None,
            expected_parameters=sum(p.numel() for p in model.parameters()),expected_dtype='torch.bfloat16')
        with budget.installed():
            optimizer=torch.optim.AdamW(model.parameters(),lr=5e-5,betas=(.9,.999),eps=1e-8,weight_decay=0)
            scheduler=torch.optim.lr_scheduler.LambdaLR(optimizer,lambda i:[0.,1.,0.][i])
            for i,batch in enumerate(batches):
                trainer.training_step(batch);torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
                optimizer.step();optimizer.zero_grad(set_to_none=True);scheduler.step()
                if i==0:self.assertEqual(torch.count_nonzero(model.head.weight).item(),0)
            states=budget.complete()
            self.assertTrue(all(row['parameter_dtype']=='torch.bfloat16' and row['moment_bytes']==row['elements']*4 for row in states))
            self.assertGreater(torch.count_nonzero(model.head.weight).item(),0)
            optimizer.state.clear();self.assertFalse(optimizer.state)

    def test_portable_render_records_an_actual_rejected_rate_before_optimizer_work(self):
        from tools.stage_nvarc_native_long_ttt import portable_budget
        namespace={};exec(compile(portable_budget(),'trusted-native-portable-budget','exec'),namespace)
        model,trainer,batches,old,retained=self.budget()
        budget=namespace['EpochBudget'](torch,model,trainer,old.rows,old.rates,
            lambda value:retained.append(copy.deepcopy(value)),
            expected_parameters=sum(p.numel() for p in model.parameters()),expected_dtype='torch.float32')
        with budget.installed():
            optimizer=torch.optim.AdamW(model.parameters(),lr=5e-5,betas=(.9,.999),eps=1e-8,weight_decay=0)
            scheduler=torch.optim.lr_scheduler.LambdaLR(optimizer,lambda i:[0.,1.,0.][i])
            trainer.training_step(batches[0]);torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
            optimizer.param_groups[0]['lr']=math.nextafter(0.,math.inf)
            with self.assertRaisesRegex(RuntimeError,'exact native cosine'):optimizer.step()
            self.assertEqual(retained[-1]['last_learning_rate_check'],{'index':0,'expected':0.,'actual_rates':[math.nextafter(0.,math.inf)]})
            self.assertEqual(retained[-1]['optimizer_steps'],[]);self.assertFalse(optimizer.state)


if __name__=='__main__':unittest.main()
