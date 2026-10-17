"""Finite CPU checks for E12 worker/coordinator integration and strict replay."""
import copy
import contextlib
import os
import hashlib
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools import nvarc_e12_runtime as runtime
from tools import nvarc_e12_admission as admission
from tools import nvarc_e12_answer_evidence as evidence
from tools import nvarc_e12_cleanup as cleanup
from tools.nvarc_native_multitask import digest,write
from tools.nvarc_e12_output_lifecycle import GenerationStore
from tests.nvarc_e12_cpu_fixture import fixture
from tests import test_nvarc_e12_training as hooks_fixture
from tests.test_nvarc_e12_training import Engine as HookEngine
from tests.test_nvarc_e10_ttt_probe import Engine as InventoryEngine,Trainer as OldTrainer,guard,schedule_fixture


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hooks=hooks_fixture.HookTests();cls.hooks.setUp()
        # Use the original 506-tensor synthetic inventory for strict byte/count
        # replay; actual installed hooks still run on the 506 fake parameters.
        with patch.object(HookEngine,'inventory',InventoryEngine.inventory):
            cls.engine,cls.trainer,cls.budget,cls.moments,cls.trace=cls.hooks.run_arm('ttt64')
        cls.saved=copy.deepcopy(cls.hooks.saved)
    @classmethod
    def tearDownClass(cls):cls.hooks.tearDown()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.plan=fixture(self.root)
        self.arm=self.root/'workers/0/arms/ttt64';self.arm.mkdir(parents=True)
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
        for name,value in self.saved.items():write(self.arm/name,value)
        write(self.arm/'prefix-contract.json',contract);write(self.arm/'prefix-trace.json',trace)
        write(self.arm/'native-schedule.json',self.budget.schedule);write(self.arm/'optimizer-state.json',self.moments)
        write(self.arm/'preparation.json',dict(checkpoint_flags=[],trainer_origins=[]))
        write(self.arm/'prepared-rows.json',[dict(r,row=i,collator_preserved_input_ids=True,source_input_ids_equal=True,source_labels_equal=True)
            for i,r in enumerate(contract['prepared_rows'])])
        with patch.object(HookEngine,'inventory',InventoryEngine.inventory):
            self.engine.restore();baseline=self.engine.inventory();self.engine.model.changed=True;trained=self.engine.inventory();self.engine.restore()
        write(self.root/'workers/0/baseline-inventory.json',baseline)
        for name,value in [('baseline-inventory.json',baseline),('reset-inventory.json',baseline),('trained-inventory.json',trained),
            ('training-before-metadata.json',{}),('training-after-metadata.json',{}),('trained-inference-transition.json',{}),('reset-inference-transition.json',{})]:
            write(self.arm/name,value)
    def tearDown(self):self.temp.cleanup()
    def verify(self):
        # Model/cache layout and AMP transition have separate original fixture
        # coverage; this fixture independently replays all installed training
        # hook, sampler, 506-moment and128prepared-row artifacts.
        with patch.object(runtime,'unchanged_model_layout'),patch.object(runtime.native_epoch,'verify_inference_transition'):
            return runtime.verify_arm_training(self.root,self.plan,0,'ttt64')
    def mutate(self,name,fn):
        p=self.arm/name;value=json.loads(p.read_bytes());fn(value);write(p,value)
    def test_installed64_hook_artifacts_replay_independently(self):
        contract,trace=self.verify();self.assertEqual(len(trace['steps']),64)
        self.assertEqual(len(contract['prepared_rows']),128)
    def test_rehashed_fullhorizon_or_sampler_deviation_rejected(self):
        self.mutate('sampler.json',lambda v:v['order'].reverse())
        with self.assertRaisesRegex(RuntimeError,'sampler'):self.verify()
    def test_zero_lr_update_cannot_disappear_from_moments(self):
        self.mutate('optimizer-state.json',lambda v:v[0].update(step=63))
        with self.assertRaisesRegex(RuntimeError,'506'):self.verify()
    def test_prepared_label_digest_cannot_be_replaced_by_true_flag(self):
        self.mutate('prepared-rows.json',lambda v:v[0].update(labels_digest=digest('forged')))
        with self.assertRaisesRegex(RuntimeError,'collator'):self.verify()
    def test_training_reservation_without_return_rejected(self):
        self.mutate('training-ledger.json',lambda v:v['optimizer_steps'][-1].update(completed=False))
        with self.assertRaisesRegex(RuntimeError,'ledger'):self.verify()
    def test_old64_recomputed_scheduler_rejected(self):
        self.mutate('native-schedule.json',lambda v:v.update(epoch_steps=64))
        with self.assertRaises(RuntimeError):self.verify()


class WorkerSequenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.plan=fixture(self.root)
        self.plan.update(original_training_arguments={'synthetic':True},dependency_readproof_digest=digest('synthetic'))
        self.plan['native_source_learning_rates']=runtime.prefix.scalar_reference()
        self.plan['owner_editor_admission']=admission.admission(self.plan)
        self.materials={key:json.loads((self.root/'materials'/f'{key}.json').read_bytes()) for key in runtime.TASK_COUNTS}
        (self.root/'workers/0').mkdir(parents=True);self.engines=[];self.trainers=[];self.inference=[]
    def tearDown(self):self.temp.cleanup()
    def run_worker(self,fail_inference=False):
        test=self
        class Engine(InventoryEngine):
            def __init__(self,*args):
                super().__init__(*args);self.rng=0;self.torch.cuda.empty_cache=lambda:None;test.engines.append(self)
            def trainer(self,texts,rows,output):
                self.limit=64 if output.name=='ttt64' else 128
                trainer=OldTrainer(self.model,{'texts':texts,'rows':rows[:self.limit]},self.plan['native_source_learning_rates'])
                test.trainers.append(trainer);return trainer
        class Budget:
            def __init__(self,engine,trainer,*args):
                self.engine=engine;self.trainer=trainer;self.optimizer=None;self.output=Path(args[-3])
            @contextlib.contextmanager
            def installed(self):
                try:yield self
                finally:self.optimizer=self.trainer.optimizer
            def complete(self):return [{'literal_fake_only':True} for _ in range(506)]
            def finish(self):
                write(self.output/'prefix-contract.json',{'literal_fake_only':True})
                write(self.output/'prefix-trace.json',{'literal_fake_only':True})
                return {'literal_fake_only':True}
        def solve(engine,*args,**kwargs):
            self.assertTrue(engine.model.changed);self.assertTrue(all(p.grad is None for p in engine.model.params))
            self.assertTrue(all(t.optimizer is t.lr_scheduler is None for t in test.trainers))
            test.inference.append((kwargs['arm_id'],engine.model.updates,engine.rng))
            if fail_inference:raise RuntimeError('literal inference failure')
            return {'literal_fake_only':True}
        api=NS(verify_runtime=lambda *_a,**_kw:self.plan)
        with patch.object(runtime,'NativeEngine',Engine),patch.object(runtime,'PrefixBudget',Budget),\
            patch.object(runtime,'install_owner_guard'),patch.object(runtime,'require_worker_receipt'),\
            patch.object(runtime.native_training,'preparation_guard',side_effect=guard),\
            patch.object(runtime.native_training,'wait_for_release',return_value=time.time()+1200),\
            patch.object(runtime,'public_training_material',side_effect=lambda _l,_t,key,_c:self.materials[key]),\
            patch.object(runtime,'native_schedule',return_value=(self.plan['native_source_learning_rates'],schedule_fixture(self.plan['native_source_learning_rates']))),\
            patch.object(runtime,'capture_rng',side_effect=lambda e:e.rng),\
            patch.object(runtime,'restore_rng',side_effect=lambda e,state:setattr(e,'rng',state)),\
            patch.object(runtime,'rng_observation',side_effect=lambda state:{'literal':state}),\
            patch.object(runtime,'model_metadata',return_value={'literal_fake_only':True}),\
            patch.object(runtime,'verify_model_metadata'),patch.object(runtime,'unchanged_model_layout'),\
            patch.object(runtime.native_epoch,'inference_transition'),patch.object(runtime.prefix,'validate_pair'),\
            patch.object(evidence,'solve_task',side_effect=solve):
            return runtime.worker(self.root,self.root,self.root,0,time.time()+2500,os.getpid(),runtime_api=api,
                expected_plan_sha256=digest(self.plan).removeprefix('sha256:'))
    def test_resident_single_engine_independent_trainers192updates_seven_controls(self):
        self.assertEqual(self.run_worker(),0)
        self.assertEqual(len(self.engines),1);self.assertEqual(len(self.trainers),2)
        self.assertIsNot(self.trainers[0],self.trainers[1])
        self.assertEqual(self.engines[0].model.updates,192)
        self.assertEqual(self.inference,[('ttt64',64,0),('ttt128',192,0)])
        result=json.loads((self.root/'workers/0/result.json').read_bytes())
        self.assertEqual(result['controls']['completed_forwards'],7)
        self.assertEqual(result['completed_training_updates'],192)
        self.assertTrue(all(r['baseline_restored'] and r['optimizer_discarded'] for r in result['arms'].values()))
        self.assertFalse(self.engines[0].model.changed)
    def test_inference_fault_still_restores_disposes_and_runs_exact_seventh_control(self):
        self.assertEqual(self.run_worker(fail_inference=True),1)
        self.assertEqual(len(self.engines),1);self.assertEqual(len(self.trainers),1)
        self.assertFalse((self.root/'workers/0/arms/ttt128').exists())
        result=json.loads((self.root/'workers/0/result.json').read_bytes())
        self.assertEqual(result['outcome'],'failed');self.assertEqual(result['controls']['completed_forwards'],7)
        self.assertTrue(result['arms']['ttt64']['optimizer_discarded']);self.assertTrue(result['arms']['ttt64']['baseline_restored'])
        self.assertIsNone(self.trainers[0].optimizer);self.assertFalse(self.engines[0].model.changed)


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.plan=fixture(self.root)
        write(self.root/'plan.json',self.plan);write(self.root/'screen.json',self.plan)
        write(self.root/runtime.RECEIPT_FILE,{'synthetic':True})
        # Synthetic unit-test declaration only, never a retained owner receipt.
        admission.write_confirmation(self.root,self.plan,True,time.monotonic())
    def tearDown(self):self.temp.cleanup()
    def test_latest900second_startup_retains_all2160seconds_of_work(self):
        for spawned in (0.,100.,899.):
            end=runtime.worker_deadline_monotonic(self.plan,0.,spawned)
            self.assertGreaterEqual(end-900,2160)
            self.assertLessEqual(end,3290)
        with self.assertRaises(RuntimeError):runtime.worker_deadline_monotonic(self.plan,0.,900.)
    def test_remaining_reset_and_full_test_windows_are_reserved_for_each_arm(self):
        for key,count in runtime.TASK_COUNTS.items():
            first,inference=runtime.arm_phase_deadlines(self.plan,key,0,3060.,900.,0.)
            self.assertEqual(first,min(2100.,3060.-360.-count*300.))
            self.assertEqual(inference,2700.)
            second,inference=runtime.arm_phase_deadlines(self.plan,key,1,3060.,1600.,400.)
            self.assertEqual(second,min(2400.,3060.-180.-count*150.))
            self.assertEqual(inference,2880.)
        with self.assertRaises(RuntimeError):runtime.arm_phase_deadlines(self.plan,'195c6913',0,3060.,2100.,0.)
        with self.assertRaises(RuntimeError):runtime.arm_phase_deadlines(self.plan,'195c6913',1,3060.,2000.,1200.)
    def test_empty_failure_seals_six_slots_per_arm_without_fake_training(self):
        value=runtime.seal_outputs(self.root,self.plan,{},[{'message':'literal startup failure'}])
        self.assertEqual(value['planned_training_updates'],768);self.assertEqual(value['verified_completed_training_updates'],0)
        self.assertIsNone(value['actual_training_updates_all_workers']);self.assertIsNone(value['total_cost_reduction'])
        for arm in runtime.ARMS:
            self.assertEqual(value['per_arm'][arm]['test_cases'],6);self.assertEqual(value['per_arm'][arm]['missing_attempts'],12)
            self.assertFalse(value['per_arm'][arm]['output_qualified'])
        GenerationStore(self.root,'e12-prefix-pilot',dict(run_id=runtime.RUN_ID,plan_digest=digest(self.plan),
            challenges_digest=self.plan['challenges_digest'])).read()
    def test_complete_pilot_seals_two_six_case_arms_without_quality_or_cost_claim(self):
        results={}
        for rank,key in enumerate(self.plan['task_order']):
            tests=[dict(attempts=[[[1]],[[2]]],ranked_grids=[[[1]],[[2]]],status='complete',output_qualified=True)
                for _ in range(self.plan['test_counts'][key])]
            results[str(rank)]={'completed_training_updates':192,'verified_inference':{arm:{'tests':tests} for arm in runtime.ARMS}}
        summary=runtime.seal_outputs(self.root,self.plan,results,[])
        self.assertEqual(summary['verified_completed_training_updates'],768)
        self.assertTrue(all(v['output_qualified'] for v in summary['per_arm'].values()))
        self.assertFalse(summary['quality_comparison_qualified']);self.assertIsNone(summary['total_cost_reduction'])
        self.assertFalse(summary['base0_causal_claim']);self.assertFalse(summary['correctness_scored'])
        for arm in runtime.ARMS:
            output=json.loads((self.root/(arm+'-answers.json')).read_bytes())
            self.assertEqual(sum(len(t) for t in output['tasks'].values()),6)
    def test_launch_failure_stops_registered_workers_and_archives_honest_failure(self):
        launches=[];stopped=[]
        def launch(command,**kwargs):
            if len(launches)==1:raise OSError('literal second worker spawn failure')
            process=NS(pid=51000+len(launches),poll=lambda:None);launches.append(process);return process
        def stop(resources,*args,**kwargs):
            stopped.extend(resources)
            for r in resources:
                for s in r['streams'].values():s.close()
            return dict(all_producers_stopped=True,complete_before_deadline=True)
        api=NS(verify_runtime=lambda *_a,**_k:self.plan,SCOPE={},WORKER_PATH='tools/nvarc_e12_entry.py',
            record_worker_launch=runtime.record_worker_launch,seal_outputs=runtime.seal_outputs)
        with patch.object(runtime,'verify_before_prepare'),patch.object(runtime,'verify_mount',return_value={}),\
            patch.object(runtime,'prepare',return_value=(self.root,[{'uuid':'fake'+str(i)} for i in range(4)])),\
            patch.object(runtime.subprocess,'Popen',side_effect=launch),patch.object(cleanup,'cleanup_workers',side_effect=stop),\
            patch.object(runtime.signal,'signal'),patch('builtins.print'):
            result=runtime.execute(self.root,self.root,time.monotonic(),runtime_api=api,
                expected_plan_sha256=digest(self.plan).removeprefix('sha256:'))
        self.assertEqual(result,1);self.assertEqual(len(launches),1);self.assertEqual(len(stopped),2)
        reserve=json.loads((self.root/'workers/0/launch-reservation.json').read_bytes())
        self.assertEqual(reserve['training_updates'],192);self.assertEqual(reserve['control_forwards'],7)
        terminal=json.loads((self.root/'terminal.json').read_bytes());self.assertEqual(terminal['outcome'],'failed')
        self.assertEqual(terminal['results'],{});self.assertIsNone(terminal['total_cost_reduction'])
        self.assertEqual(terminal['sealed_output']['verified_completed_training_updates'],0)
    def test_inert_entry_rejects_before_model_preparation(self):
        api=NS(SCOPE={},verify_runtime=lambda *_a,**_k:(_ for _ in ()).throw(RuntimeError('missing explicit owner config')))
        with patch.object(runtime,'prepare') as prepare,self.assertRaisesRegex(RuntimeError,'explicit owner'):
            runtime.execute(self.root,self.root,time.monotonic(),runtime_api=api)
        prepare.assert_not_called()


if __name__=='__main__':unittest.main()
