from pathlib import Path
import tempfile,unittest,json
from experiment_flow.controlled_batched import run_simulation
from owned_runtime.policy import measured_batch_forecast
from owned_runtime.storage import storage_plan
class BatchedTests(unittest.TestCase):
    def run_case(self,**kwargs):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        return run_simulation(Path(tmp.name)/'run',**kwargs)
    def test_full_real_shape_source_bound_simulation(self):
        r,b,d,p=self.run_case()
        self.assertEqual(r['status'],'owned-comparison-complete-PUBLIC-sealed',r.get('error'))
        self.assertEqual(r['arms']['A']['updates']['anchor_updates'],256)
        self.assertEqual(r['arms']['B']['updates']['rl_updates'],4)
        self.assertEqual(r['full_panel_audit']['planned_attempts'],256)
        self.assertTrue(r['full_panel_audit']['all32_coverage_complete'])
        self.assertEqual([x['summary']['planned_attempts'] for x in r['audit_batches']],[64]*4)
        self.assertEqual(b.predictions,288+334)
        self.assertLess(b.phase_order.index('public'),b.phase_order.index('holdout'))
        self.assertEqual(d.opened,['dev','holdout'])
        self.assertTrue(r['time_matching']['matched'])
        self.assertEqual(len(list((Path(r['result_artifact']).parent/'checkpoints').glob('*/manifest.json'))),7)
    def test_zero_and_one_continue_all_four_without_updates(self):
        for branch in ('zero','one'):
            with self.subTest(branch=branch):
                r,b,d,p=self.run_case(branch=branch)
                self.assertEqual(r['status'],'owned-comparison-complete-PUBLIC-sealed',r.get('error'))
                self.assertEqual(b.update_calls,0);self.assertEqual(len(b.batches),4)
                self.assertEqual(r['arms']['B']['adapter_sha256'],r['arms']['A']['adapter_sha256'])
                self.assertEqual(r['full_panel_audit']['all_zero_panel'],branch=='zero')
    def test_partial_batch_preserves_prior_commit_and_all_slots(self):
        r,b,d,p=self.run_case(branch='partial')
        self.assertEqual(r['arms']['B']['updates']['rl_updates'],1)
        self.assertEqual(len(r['audit_batches']),4)
        self.assertEqual([x['status'] for x in r['audit_batches'][2:]],['not-reached']*2)
        self.assertFalse(r['full_panel_audit']['all_zero_panel'])
        self.assertFalse(r['full_panel_audit']['all32_coverage_complete'])
        self.assertEqual(r['full_panel_audit']['summary']['not_reached'],187)
    def test_numeric_failure_preserves_prior_commit(self):
        r,b,d,p=self.run_case(branch='numeric')
        self.assertEqual(r['arms']['B']['updates']['rl_updates'],1)
        self.assertEqual(len(b.batches),2)
        self.assertEqual(r['audit_batches'][1]['update_status'],'numeric-nonadmission-no-update')
    def test_cost_prefix_is_not_panel_zero(self):
        r,b,d,p=self.run_case(branch='partial-zero',generation_seconds=45.)
        self.assertLess(len(b.batches),4)
        self.assertFalse(r['full_panel_audit']['all_zero_panel'])
        self.assertGreater(r['full_panel_audit']['summary']['not_reached'],0)
    def test_partial_held_retains_PUBLIC_eligibility_without_held_score(self):
        r,b,d,p=self.run_case(branch='partial-held')
        self.assertEqual(r['status'],'owned-partial-comparison-PUBLIC-sealed',r.get('error'))
        self.assertTrue(r['public']['coverage']['complete_prediction_coverage'])
        self.assertIsNone(r['holdout']['scores']);self.assertEqual(d.opened,['dev'])
    def test_forecast_is_cost_only_and_failed_calls_count(self):
        before=measured_batch_forecast([])
        after=measured_batch_forecast([{'phase':'rollout-generation','event_id':i,'dispatched':True,'seconds':180.,'status':'failed'} for i in range(64)])
        self.assertGreater(after['seconds'],before['seconds'])
        self.assertEqual(len(after['observations']),64)
    def test_seven_state_bound_under_fourGiB(self):
        p=storage_plan();self.assertEqual(p['maximum_checkpoint_count'],7)
        self.assertLess(p['estimated_checkpoint_upper_bytes'],4*1024**3)
if __name__=='__main__':unittest.main()
