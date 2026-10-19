"""Schema/counterexample tests, never evidence of model capability."""
import copy
import unittest
from tools.nvarc_full800_fusion_20261019 import acceptance as a


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.p=a.make_protocol(corpus_sha256='a'*64,exposure_sha256='b'*64,
            inference_contract_sha256='c'*64,training_parent_ids=['t'+str(i) for i in range(800)],
            development_pool_parent_ids=['d'+str(i) for i in range(200)],
            development_parent_ids=['d'+str(i) for i in range(96)],seeds=[1,2,3],
            architectures=['baseline','depth32'],created_at=100.)

    def evaluate(self, receipts):
        return a.evaluate(self.p,receipts,expected_protocol_sha256=self.p['protocol_sha256'],
                          expected_receipt_sha256=a.digest(receipts))

    def fixture(self):
        # Deliberately synthetic normalized receipts for acceptance logic only.
        e=dict(actual_official_model=True,all800_training_complete=True,checkpoint_reload_exact=True,
            optimizer_rng_resume_verified=True,strict_probability_gates_passed=True,
            full192_evaluation_complete=True,owned_worker_closed_within_original_budget=True,
            same_inference_contract=True,source_and_model_pins_verified=True,
            corpus_sha256='a'*64,inference_contract_sha256='c'*64,
            committed_training_parent_ids=self.p['training_parent_ids'],
            development_parent_ids=self.p['development_parent_ids'],optimizer_updates=100,
            original_runtime_receipt_sha256='d'*64)
        runs=[]
        for arch in self.p['architectures']:
            for seed in self.p['seeds']:
                runs.append(dict(seed=seed,architecture=arch,development_parent_ids=self.p['development_parent_ids'],
                    training_parent_ids=self.p['training_parent_ids'],corpus_sha256='a'*64,
                    inference_contract_sha256='c'*64,training_pool_sha256='0'*64,
                    executions={role:dict(seed=seed,run_id=f'{arch}-{seed}-{role}',
                        runtime_receipt_sha256=a.digest([arch,seed,role,'runtime']),
                        checkpoint_sha256=a.digest([arch,seed,role,'checkpoint']),
                        initial_trainable_state_sha256=a.digest([arch,seed,'initial']),source_sha256='a'*64)
                        for role in ('candidate','control')},
                    complete=True,protocol_sha256=self.p['protocol_sha256'],preregistered_before_outcome=True,
                    sealed_predictions_sha256='e'*64,candidate_pass2=[1]*16+[0]*80,
                    control_pass2=[1]*8+[0]*88,cost=dict(matrix_accounting_complete=True,
                        same_update_and_padded_input_budget=True,strong_sft_control=True,
                        method='model_accounted_padded_training_matrix_flops',
                        scope=a.MATRIX_SCOPE,excluded_operations=a.MATRIX_EXCLUSIONS,
                        equal_total_method_compute_claimed=False,all_charged_matrix_work_returned=True,
                        shared_collection_charged_once=True,full_collection_attributed_to_fusion_method=True,
                        candidate_valid_target_tokens=900,control_valid_target_tokens=920,collection_physical_tokens=1024,
                        candidate_training_wall_seconds=100.,control_training_wall_seconds=90.,collection_wall_seconds=20.,
                        candidate_training_matmul_flops=100.,control_training_matmul_flops=100.,
                        candidate_charged_training_input_tokens=1000,control_charged_training_input_tokens=1000,
                        candidate_known_target_input_tokens=800,control_known_target_input_tokens=800,fixed_replay_parent_ids=['t'+str(i) for i in range(16)],
                        candidate_updates=100,control_updates=100)))
        formal=[dict(seed=s,score=91.+s,status='COMPLETE',score_field='publicScore',unit='0_to_100',
            fixed_recipe_sha256=self.p['protocol_sha256'],preregistered_before_any_formal_feedback=True,
            leaderboard_selected=False,provider_receipt_sha256='f'*64,
            model_checkpoint_sha256=a.digest(['baseline',s,'candidate','checkpoint']),inference_contract_sha256='c'*64,
            submission_id=s,competition_ref=self.p['competition_ref'],architecture='baseline') for s in self.p['seeds']]
        return dict(engineering={x:copy.deepcopy(e) for x in self.p['architectures']},paired_runs=runs,formal_runs=formal)

    def test_empty_evidence_blocks_all_levels(self):
        r=self.evaluate(dict(engineering={},paired_runs=[],formal_runs=[]))
        for k in ('engineering_merge','scientific_adoption','gcp_scaling_plan_ready','stable_official_above90','new_methods_or_agent_harness_gate'):
            self.assertFalse(r[k])

    def test_synthetic_complete_contract_and_no_authorization(self):
        r=self.evaluate(self.fixture())
        self.assertTrue(r['engineering_merge']);self.assertTrue(r['scientific_adoption'])
        self.assertTrue(r['new_methods_or_agent_harness_gate'])
        self.assertFalse(r['gcp_resource_creation_authorized'])
        self.assertTrue(r['no_new_run_authorized_by_this_receipt'])

    def test_one_question_improvement_is_not_adoption(self):
        r=self.fixture()
        for x in r['paired_runs']:x['candidate_pass2']=[1]*9+[0]*87
        self.assertFalse(self.evaluate(r)['scientific_adoption'])

    def test_one_seed_cannot_be_repeated_as_three(self):
        r=self.fixture();r['paired_runs'][1]['seed']=1
        self.assertFalse(self.evaluate(r)['architecture_results']['baseline']['passed'])

    def test_relabeling_identical_execution_is_not_three_seeds(self):
        r=self.fixture()
        for x in r['paired_runs']:
            for role in ('candidate','control'):
                x['executions'][role]['checkpoint_sha256']='8'*64
        self.assertFalse(self.evaluate(r)['scientific_adoption'])

    def test_formal_checkpoint_must_be_selected_development_model(self):
        r=self.fixture();r['formal_runs'][0]['model_checkpoint_sha256']='7'*64
        self.assertFalse(self.evaluate(r)['stable_official_above90'])

    def test_incomplete_dev_not_zero_filled(self):
        r=self.fixture();r['paired_runs'][0]['candidate_pass2']=[1]*95
        with self.assertRaises(ValueError):self.evaluate(r)

    def test_same_steps_not_compute_matching(self):
        for key,value in [('matrix_accounting_complete',False),('same_update_and_padded_input_budget',False),
                          ('candidate_training_matmul_flops',106.),('candidate_charged_training_input_tokens',1051),
                          ('equal_total_method_compute_claimed',True),('all_charged_matrix_work_returned',False),
                          ('full_collection_attributed_to_fusion_method',False),('collection_wall_seconds',0),
                          ('scope','total_flops'),('excluded_operations',[])]:
            with self.subTest(key=key):
                r=self.fixture()
                for x in r['paired_runs']:x['cost'][key]=value
                self.assertFalse(self.evaluate(r)['scientific_adoption'])

    def test_baseline_also_requires_fixed_primary_and_replay_budget(self):
        for key,value in [('candidate_known_target_input_tokens',None),
                          ('control_known_target_input_tokens',None),
                          ('candidate_known_target_input_tokens',0),
                          ('control_known_target_input_tokens',801),
                          ('fixed_replay_parent_ids',None),('fixed_replay_parent_ids',[]),
                          ('candidate_charged_training_input_tokens',1),
                          ('candidate_valid_target_tokens',1001),('candidate_valid_target_tokens',799)]:
            with self.subTest(key=key,value=value):
                r=self.fixture()
                for row in r['paired_runs']:
                    if value is None:row['cost'].pop(key,None)
                    else:row['cost'][key]=value
                result=self.evaluate(r)
                self.assertFalse(result['scientific_adoption'])
                self.assertFalse(result['new_methods_or_agent_harness_gate'])

    def test_negative_expansion_not_required_to_be_adopted(self):
        r=self.fixture()
        for x in r['paired_runs']:
            if x['architecture']=='depth32':x['candidate_pass2']=[0]*96
        result=self.evaluate(r)
        self.assertTrue(result['scientific_adoption']);self.assertEqual(result['selected_architecture'],'baseline')

    def test_expansion_gain_over_weak_control_not_dense_gain(self):
        r=self.fixture()
        for x in r['paired_runs']:
            if x['architecture']=='depth32':
                x['candidate_pass2']=[1]*12+[0]*84
                x['control_pass2']=[0]*96
        result=self.evaluate(r)
        self.assertTrue(result['architecture_results']['depth32']['passed'])
        self.assertFalse(result['expansion_versus_dense_results']['depth32']['passed'])
        self.assertEqual(result['selected_architecture'],'baseline')

    def test_expansion_adoption_requires_dense_gain_not_equal_flops(self):
        r=self.fixture()
        for x in r['paired_runs']:
            if x['architecture']=='depth32':
                x['candidate_pass2']=[1]*24+[0]*72
                x['cost']['candidate_training_matmul_flops']=x['cost']['control_training_matmul_flops']=120.
        result=self.evaluate(r)
        self.assertEqual(result['selected_architecture'],'depth32')
        self.assertFalse(result['expansion_versus_dense_results']['depth32']['equal_flops_claimed'])
        self.assertFalse(result['stable_official_above90']) # original formal models were baseline

    def test_full200_roster_and96_subset_required(self):
        p=copy.deepcopy(self.p);p['development_pool_parent_ids']=p['development_pool_parent_ids'][:199]
        p['protocol_sha256']=a.digest({k:v for k,v in p.items() if k!='protocol_sha256'})
        with self.assertRaises(ValueError):a.validate_protocol(p,p['protocol_sha256'])

    def test_expansion_different_pool_or_extra_tokens_rejected(self):
        for mutation in ('pool','tokens','parents'):
            r=self.fixture()
            for x in r['paired_runs']:
                if x['architecture']=='depth32':
                    x['candidate_pass2']=[1]*24+[0]*72
                    if mutation=='pool':x['training_pool_sha256']='9'*64
                    if mutation=='tokens':
                        x['cost']['candidate_charged_training_input_tokens']=2000
                        x['cost']['control_charged_training_input_tokens']=2000
                    if mutation=='parents':x['cost']['fixed_replay_parent_ids']=['t'+str(i) for i in range(16,32)]
            result=self.evaluate(r)
            self.assertFalse(result['expansion_versus_dense_results']['depth32']['passed'])
            self.assertEqual(result['selected_architecture'],'baseline')

    def test_old_full800_zero_updates_not_engineering_merge(self):
        r=self.fixture();r['engineering']['baseline']['optimizer_updates']=0
        r['engineering']['baseline']['committed_training_parent_ids']=[]
        self.assertFalse(self.evaluate(r)['engineering_merge'])

    def test_formal1792_or90_or_nan_never_stable(self):
        for value in (17.92,90.,float('nan')):
            with self.subTest(value=value):
                r=self.fixture();r['formal_runs'][0]['score']=value
                if value!=value:
                    with self.assertRaises(ValueError):self.evaluate(r)
                else:self.assertFalse(self.evaluate(r)['stable_official_above90'])

    def test_mixed_score_fields_and_duplicate_models_rejected(self):
        r=self.fixture();r['formal_runs'][0]['score_field']='privateScore'
        self.assertFalse(self.evaluate(r)['stable_official_above90'])

    def test_consistent_wrong_competition_or_population_rejected(self):
        for field,value in [('competition_ref','unrelated-competition'),('score_field','privateScore')]:
            r=self.fixture()
            for row in r['formal_runs']:row[field]=value
            self.assertFalse(self.evaluate(r)['stable_official_above90'])
        r=self.fixture();r['formal_runs'][0]['model_checkpoint_sha256']=r['formal_runs'][1]['model_checkpoint_sha256']
        self.assertFalse(self.evaluate(r)['stable_official_above90'])

    def test_feedback_selection_rejected(self):
        r=self.fixture();r['formal_runs'][0]['leaderboard_selected']=True
        self.assertFalse(self.evaluate(r)['new_methods_or_agent_harness_gate'])

    def test_changed_protocol_or_evidence_pin_rejected(self):
        r=self.fixture()
        with self.assertRaises(ValueError):a.evaluate(self.p,r,expected_protocol_sha256='a'*64,expected_receipt_sha256=a.digest(r))
        with self.assertRaises(ValueError):a.evaluate(self.p,r,expected_protocol_sha256=self.p['protocol_sha256'],expected_receipt_sha256='a'*64)


if __name__=='__main__':unittest.main()
