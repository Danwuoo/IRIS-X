"""Independent sealed-dev ranking and exact project-goal boundary checks."""
from copy import deepcopy
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'worktree'))
from tools.arc_qwen_transfer_20261012 import data as d,experiment as e,public_evaluation as p

class SelectionGoal(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.ds=d.build_dataset({'tiny_cpu':True},self.root/'data')
        self.cases=[c for c in self.ds['cases'] if c['scope']=='dev']
        self.methods={k:[{'case_id':c['case_id'],'answers':[],'generations':[],'complete':True} for c in self.cases] for k in ['base','sft64','sft256']}
    def select(self,include=True):
        seal=e.seal_scope(self.root,'dev',self.ds,self.methods)
        checked=d.checked_json;reads=[]
        def read(path,*a,**k):
            reads.append(str(path))
            if 'holdout-target' in str(path):raise AssertionError('holdout targets opened in dev selection')
            return checked(path,*a,**k)
        with patch.object(d,'checked_json',side_effect=read): result=e.select_sft(self.ds,seal,[64,256],include_base=include)
        self.assertTrue(any('dev-target' in x for x in reads));return result
    def test_base_wins_all_zero_tie_but_primary_remains_sft_only(self):
        public=self.select();self.assertEqual(public['candidate_id'],'base')
        self.assertEqual([r['candidate_id'] for r in public['rankings']],['base','sft64','sft256'])
        self.assertTrue(public['includes_frozen_base'])
        seal={'sealed':True,'scope':'dev','path':str(self.root/'dev-predictions-sealed.json'),'file_sha256':d.file_sha(self.root/'dev-predictions-sealed.json')}
        primary=e.select_sft(self.ds,seal,[64,256]);self.assertEqual(primary['candidate_id'],'sft64')
        self.assertFalse(primary['includes_frozen_base'])
    def test_sft256_can_win_exact_rank_without_holdout_gold(self):
        # Explicit authored CPU fixture truth is used only to author this test's predictions.
        targets=d.checked_json(self.ds['escrow']['dev']['path'],self.ds['escrow']['dev']['sha256'])
        self.methods['sft256'][0]['answers']=[targets[self.cases[0]['case_id']]]
        self.assertEqual(self.select()['candidate_id'],'sft256')
    def test_incomplete_competitor_fails_instead_of_selecting_others(self):
        self.methods['sft256'][3]['complete']=False
        with self.assertRaisesRegex(ValueError,'incomplete'):self.select()
    def test_goal_requires_exact_full_denominators_and_real_eligibility(self):
        def metric(n,d=167,tasks=120,tests=167):return {'tasks':tasks,'tests':tests,'metrics':{'pass_at_2':{'numerator':n,'denominator':d}}}
        self.assertTrue(p.goal_met(True,metric(151)));self.assertTrue(p.goal_met(True,metric(167)))
        for eligibility,metrics in [(False,metric(167)),(1,metric(167)),(True,metric(150)),(True,metric(168)),(True,metric(151.,167)),(True,metric(True)),(True,metric(151,166)),(True,metric(151,167,119)),(True,metric(151,167,120,166))]:
            with self.subTest(eligibility=eligibility,metrics=metrics):self.assertFalse(p.goal_met(eligibility,metrics))
    def test_scorer_pins_match_current_unchanged_source(self):
        actual=p.source_identity()
        self.assertGreaterEqual(len(p.SCORER_PINS),2)
        for name,value in p.SCORER_PINS.items():self.assertEqual(actual[name],value)

if __name__=='__main__':unittest.main(verbosity=2)
