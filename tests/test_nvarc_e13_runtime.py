"""E13 worker sequencing and full128 evidence replay with literal CPU boundaries."""
import copy
import contextlib
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from tools import nvarc_e13_runtime as runtime
from tools import nvarc_e13_answer_evidence as evidence
from tools import nvarc_e13_admission as admission
from tools import nvarc_e13_cleanup as cleanup
from tools.nvarc_native_multitask import digest,write
from tests.nvarc_e13_cpu_fixture import fixture,LiteralEngine
from tests import test_nvarc_e12_training as hooks_fixture
from tests.test_nvarc_e12_training import Engine as HookEngine
from tests.test_nvarc_e10_ttt_probe import Engine as InventoryEngine,Trainer as OldTrainer,guard,schedule_fixture


def rng(value):
    return dict(python=digest(['p',value]),numpy=digest(['n',value]),torch_cpu=digest(['t',value]),torch_cuda=[digest(['c',value])])


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hooks=hooks_fixture.HookTests();cls.hooks.setUp()
        with patch.object(HookEngine,'inventory',InventoryEngine.inventory):
            cls.engine,cls.trainer,cls.budget,cls.moments,cls.trace=cls.hooks.run_arm('ttt128')
        cls.saved=copy.deepcopy(cls.hooks.saved)
    @classmethod
    def tearDownClass(cls):cls.hooks.tearDown()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.plan=fixture(self.root)
        self.training=self.root/'workers/0/training';self.training.mkdir(parents=True)
        key=self.plan['task_order'][0];contract=copy.deepcopy(self.budget.contract)
        rows=[dict(r,row=i,source_view=str(i),original_text_sha256='c'*64) for i,r in enumerate(contract['prepared_rows'])]
        texts=[dict(text='synthetic-'+str(i),key=str(i)) for i in range(128)]
        write(self.root/'materials'/f'{key}.json',dict(rows=rows,texts=texts))
        self.plan['task_specs'][key].update(expected_rows_digest=digest(rows),texts_digest=digest(texts))
        self.plan.update(native_source_learning_rates=contract['learning_rates'],original_training_arguments={'synthetic':True},
            dependency_readproof_digest=digest('synthetic-dependency'),native_checkpoint_flags=[],native_trainer_origins=[])
        sampler=copy.deepcopy(self.saved['sampler.json']);sources=runtime.training_sources(self.plan,key)
        sources['native_sampler_digest']=digest({k:v for k,v in sampler.items() if k!='order'})
        contract['sources']=sources;trace=copy.deepcopy(self.trace);trace['contract_digest']=digest(contract)
        for name,value in self.saved.items():write(self.training/name,value)
        write(self.training/'prefix-contract.json',contract);write(self.training/'prefix-trace.json',trace)
        write(self.training/'native-schedule.json',self.budget.schedule);write(self.training/'optimizer-state.json',self.moments)
        write(self.training/'preparation.json',dict(checkpoint_flags=[],trainer_origins=[]))
        write(self.training/'prepared-rows.json',[dict(r,row=i,collator_preserved_input_ids=True,source_input_ids_equal=True,source_labels_equal=True)
            for i,r in enumerate(contract['prepared_rows'])])
        with patch.object(HookEngine,'inventory',InventoryEngine.inventory):
            self.engine.restore();baseline=self.engine.inventory();self.engine.model.changed=True;trained=self.engine.inventory();self.engine.restore()
        write(self.root/'workers/0/baseline-inventory.json',baseline)
        for name,value in [('baseline-inventory.json',baseline),('reset-inventory.json',baseline),('trained-inventory.json',trained),
            ('training-before-metadata.json',{}),('training-after-metadata.json',{}),('trained-inference-transition.json',{}),('reset-inference-transition.json',{})]:
            write(self.training/name,value)
        self.addCleanup(self.temp.cleanup)
    def verify(self):
        with patch.object(runtime,'unchanged_model_layout'),patch.object(runtime.native_epoch,'verify_inference_transition'):
            return runtime.verify_training(self.root,self.plan,0)
    def mutate(self,name,fn):
        p=self.training/name;value=json.loads(p.read_bytes());fn(value);write(p,value)
    def test_actual_unchanged128_hooks_replay_full_native_horizon(self):
        contract,trace=self.verify();self.assertEqual(len(trace['steps']),128)
        self.assertEqual(len(contract['prepared_rows']),128);self.assertEqual(trace['profile'],'E12-TTT128-CONTROL')
    def test_second_optimizer_and_64step_substitution_rejected(self):
        self.mutate('training-ledger.json',lambda v:v['optimizer_constructions'].append({'completed':True}))
        with self.assertRaisesRegex(RuntimeError,'one optimizer'):self.verify()
    def test_zero_lr_update_cannot_disappear_from_moments(self):
        self.mutate('optimizer-state.json',lambda v:v[0].update(step=127))
        with self.assertRaisesRegex(RuntimeError,'506'):self.verify()
    def test_rehashed_native_sampler_or_source_label_changes_rejected(self):
        self.mutate('sampler.json',lambda v:v['order'].reverse())
        with self.assertRaisesRegex(RuntimeError,'sampler'):self.verify()
    def test_prepared_labels_and_unreturned_update_rejected(self):
        self.mutate('prepared-rows.json',lambda v:v[0].update(labels_digest=digest('forged')))
        with self.assertRaisesRegex(RuntimeError,'collator'):self.verify()
    def test_unreturned_update_rejected(self):
        self.mutate('training-ledger.json',lambda v:v['optimizer_steps'][-1].update(completed=False))
        with self.assertRaisesRegex(RuntimeError,'ledger'):self.verify()


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.plan=fixture(self.root)
        self.plan.update(original_training_arguments={'synthetic':True},dependency_readproof_digest=digest('synthetic'))
        self.plan['native_source_learning_rates']=runtime.prefix.scalar_reference();self.materials={}
        for key in runtime.TASK_COUNTS:
            rows=[dict(row=i,source_view=str(i),input_tokens=3,supervised_tokens=2,input_ids_digest=digest([i]*3),
                labels_digest=digest([-100,i,i]),original_text_sha256='c'*64) for i in range(128)]
            texts=[dict(text='literal'+str(i),key=str(i)) for i in range(128)]
            self.materials[key]=dict(rows=rows,texts=texts);write(self.root/'materials'/f'{key}.json',self.materials[key])
            self.plan['task_specs'][key].update(expected_rows_digest=digest(rows),texts_digest=digest(texts))
        self.plan['owner_editor_admission']=admission.admission(self.plan)
        self.engines=[];self.trainers=[];self.starts=[];self.collectors=[];self.addCleanup(self.temp.cleanup)
    def run_worker(self,rank=0,*,fail_second=False,mutate_first=False,fail_training=False):
        (self.root/'workers'/str(rank)).mkdir(parents=True);test=self
        literal=LiteralEngine();original_solve=evidence.solve_task
        class Engine(InventoryEngine):
            def __init__(self,*args):
                super().__init__(*args);self.rng=7;self.restores=0;self.torch.cuda.empty_cache=lambda:None
                self.loader=literal.loader;self.tokenizer=literal.tokenizer;self.solver=literal.solver;self.decoder=literal.decoder
                test.engines.append(self)
            def restore(self):self.restores+=1;super().restore()
            def trainer(self,texts,rows,output):
                trainer=OldTrainer(self.model,{'texts':texts,'rows':rows},self.plan['native_source_learning_rates'])
                original=trainer.train
                def train():
                    if fail_training:raise RuntimeError('literal training failure')
                    original();self.rng+=128
                trainer.train=train;test.trainers.append(trainer);return trainer
        class Budget:
            def __init__(self,engine,trainer,*args):
                self.engine=engine;self.trainer=trainer;self.optimizer=None;self.output=Path(args[-3])
                test.assertEqual(args[-1],'ttt128')
            @contextlib.contextmanager
            def installed(self):
                try:yield self
                finally:self.optimizer=self.trainer.optimizer
            def complete(self):return [{'literal_fake_only':True} for _ in range(506)]
            def finish(self):
                write(self.output/'prefix-contract.json',{'literal_fake_only':True})
                write(self.output/'prefix-trace.json',{'literal_fake_only':True});return {'literal_fake_only':True}
        def solve(engine,*args,**kwargs):
            self.assertTrue(engine.model.changed);self.assertEqual(engine.model.updates,128)
            self.assertEqual(engine.restores,0);self.assertIsNone(self.trainers[0].optimizer)
            self.starts.append((kwargs['arm_id'],engine.model.updates,engine.rng,digest(engine.inventory())))
            self.collectors.append(args[4])
            if fail_second and len(self.starts)==2:raise RuntimeError('literal second inference failure')
            value=original_solve(engine,*args,**kwargs);engine.rng+=19
            if mutate_first and len(self.starts)==1:engine.model.changed=False
            return value
        with patch.object(runtime,'NativeEngine',Engine),patch.object(runtime,'PrefixBudget',Budget),\
            patch.object(runtime,'install_owner_guard'),patch.object(runtime,'require_worker_receipt'),\
            patch.object(runtime.native_training,'preparation_guard',side_effect=guard),\
            patch.object(runtime.native_training,'wait_for_release',return_value=time.time()+1200),\
            patch.object(runtime,'public_training_material',side_effect=lambda _l,_t,key,_c:self.materials[key]),\
            patch.object(runtime,'native_schedule',return_value=(self.plan['native_source_learning_rates'],schedule_fixture(self.plan['native_source_learning_rates']))),\
            patch.object(runtime,'capture_rng',side_effect=lambda e:e.rng),\
            patch.object(runtime,'restore_rng',side_effect=lambda e,state:setattr(e,'rng',state)),\
            patch.object(runtime,'rng_observation',side_effect=rng),\
            patch.object(runtime,'model_metadata',return_value={'literal_fake_only':True}),\
            patch.object(runtime,'verify_model_metadata'),patch.object(runtime,'unchanged_model_layout'),\
            patch.object(runtime.native_epoch,'inference_transition'),\
            patch.object(evidence,'solve_task',side_effect=solve),patch.object(runtime.native_epoch,'verify_inference_transition'),\
            patch('tools.nvarc_native_multitask.test_views',side_effect=literal.views):
            rc=runtime.worker(self.root,self.root,self.root,rank,time.time()+2500,os.getpid(),
                runtime_api=NS(verify_runtime=lambda *_a,**_kw:self.plan),expected_plan_sha256=digest(self.plan)[7:])
        result=json.loads((self.root/'workers'/str(rank)/'result.json').read_bytes())
        return rc,result
    def test_one128training_shared_actual_inventory_rng_and_seven_controls(self):
        rc,result=self.run_worker();self.assertEqual(rc,0,result['errors'])
        self.assertEqual(len(self.engines),1);self.assertEqual(len(self.trainers),1)
        self.assertEqual(self.engines[0].model.updates,128);self.assertEqual(self.engines[0].restores,1)
        self.assertEqual([v[:3] for v in self.starts],[('search120',128,135),('search240',128,135)])
        self.assertEqual(self.starts[0][3],self.starts[1][3]);self.assertIsNot(self.collectors[0],self.collectors[1])
        self.assertEqual(result['controls']['completed_forwards'],7);self.assertEqual(result['completed_training_updates'],128)
        self.assertTrue(result['shared_training_verified']);self.assertTrue(result['paired_rng_restored'])
        self.assertEqual(result['post_training_rng'],rng(135));self.assertEqual(self.engines[0].rng,135)
        self.assertFalse(self.engines[0].model.changed)
        self.assertEqual(result['telemetry']['tests'],{})
        answers={a:json.loads((self.root/'workers/0/arms'/a/'answer-checkpoint.json').read_bytes()) for a in runtime.ARMS}
        runtime.verify_inference_telemetry(result['inference_telemetry'],answers)
    def test_reversed_order_still_uses_single_training(self):
        rc,result=self.run_worker(rank=1);self.assertEqual(rc,0,result['errors'])
        self.assertEqual([r[0] for r in self.starts],['search240','search120']);self.assertEqual(len(self.trainers),1)
        self.assertEqual(self.starts[0][1:],self.starts[1][1:])
    def test_second_arm_fault_keeps_first_snapshot_and_final_reset(self):
        rc,result=self.run_worker(fail_second=True);self.assertEqual(rc,1)
        self.assertEqual(len(self.trainers),1);self.assertEqual(self.engines[0].restores,1)
        self.assertEqual(result['arms']['search120']['status'],'complete');self.assertEqual(result['arms']['search240']['status'],'failed')
        self.assertFalse(result['shared_training_verified']);self.assertTrue(result['paired_rng_restored'])
        self.assertTrue(result['training']['trace_complete']);self.assertEqual(result['controls']['completed_forwards'],7)
        self.assertEqual(set(result['inference_telemetry']['arms']['search120']['tests']),{'0','1'})
    def test_model_mutation_never_becomes_shared_pair(self):
        rc,result=self.run_worker(mutate_first=True);self.assertEqual(rc,1)
        self.assertEqual(len(self.starts),1);self.assertFalse(result['shared_training_verified'])
        self.assertEqual(self.engines[0].restores,1);self.assertEqual(result['controls']['completed_forwards'],7)
    def test_training_failure_never_starts_search_and_still_resets(self):
        rc,result=self.run_worker(fail_training=True);self.assertEqual(rc,1)
        self.assertEqual(self.starts,[]);self.assertEqual(result['completed_training_updates'],0)
        self.assertEqual(result['controls']['completed_forwards'],7);self.assertEqual(self.engines[0].restores,1)


class CoordinatorTests(unittest.TestCase):
    def test_last_startup_launch_retains_full_original_envelope(self):
        with tempfile.TemporaryDirectory() as folder:
            plan=fixture(Path(folder))
            for spawn in (0.,100.,899.):
                deadline=runtime.worker_deadline_monotonic(plan,0.,spawn)
                self.assertGreaterEqual(deadline-900,2220);self.assertLessEqual(deadline,3290)
            with self.assertRaises(RuntimeError):runtime.worker_deadline_monotonic(plan,0.,900.)
    def test_inert_api_rejects_before_any_model_preparation(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(runtime,'prepare') as prepare:
            with self.assertRaisesRegex(RuntimeError,'denied'):
                runtime.execute(folder,folder,time.monotonic(),runtime_api=NS(SCOPE={},
                    verify_runtime=lambda *_a,**_k:(_ for _ in ()).throw(RuntimeError('denied'))))
            prepare.assert_not_called()


if __name__=='__main__':unittest.main()
