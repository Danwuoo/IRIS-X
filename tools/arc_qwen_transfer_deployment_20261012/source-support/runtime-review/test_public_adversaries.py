"""Independent native-receipt adversaries using authored120/167 synthetic fixtures.

No real public evaluation data, neural imports, or provider resources are used.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'worktree'))
spec=importlib.util.spec_from_file_location('review_author_public_fixture',ROOT/'worktree/tests/test_public_evaluation.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
pe=f.pe
from tools.arc_learning_agent_20261011.budget import WorkLedger

class PublicAdversaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner=f.PublicEvaluationTests();cls.owner.setUpClass()
    @classmethod
    def tearDownClass(cls):cls.owner.tearDownClass()
    def check(self,fixture):
        events,_=pe._ledger((fixture['owner']/'physical-work.jsonl').read_bytes())
        return pe.make_pool(self.owner.challenges,fixture['artifact'],read=lambda p:Path(p).read_bytes(),events=events,
                            run_id='independent-adversary',elapsed_seconds=1,tiny=True)
    def native_change(self,fixture,changes):
        compact=fixture['artifact']['case_receipts'][0]['generations'][0]
        path=Path(compact['receipt_path']);receipt=json.loads(path.read_bytes());receipt.update(changes)
        path.write_text(json.dumps(receipt));compact['receipt_sha256']=pe.sha256(path.read_bytes())
    def test_valid_boolean_cannot_admit_truncated_native_completion(self):
        fixture=self.owner.fixture();self.native_change(fixture,{'valid':True,'finish_reason':'length'})
        with self.assertRaisesRegex(ValueError,'native EOS'):self.check(fixture)
    def test_changed_adapter_cannot_be_self_declared_selected(self):
        fixture=self.owner.fixture();self.native_change(fixture,{'adapter_state_sha256':'e'*64})
        with self.assertRaisesRegex(ValueError,'selected adapter'):self.check(fixture)
    def test_swapped_true_receipt_cannot_impersonate_another_query(self):
        fixture=self.owner.fixture();cases=fixture['artifact']['case_receipts']
        cases[0]['generations'][0]=deepcopy(cases[2]['generations'][0])
        with self.assertRaisesRegex(ValueError,'query packing|transformed query'):self.check(fixture)
    def test_unknown_work_chain_cannot_be_scored_as_complete(self):
        with tempfile.TemporaryDirectory() as td:
            ledger=WorkLedger(Path(td)/'physical.jsonl');ledger.reserve('attempt',{'generation_calls':1,'input_tokens':4096,'output_tokens':1024})
            ledger.unknown('attempt','killed after dispatch')
            with self.assertRaisesRegex(ValueError,'unknown or unresolved'):pe._ledger(ledger.path.read_bytes())
    def test_no_receipts_retains_all167_query_denominator(self):
        fixture=self.owner.fixture();artifact=fixture['artifact']
        artifact['case_receipts']=[];artifact['case_count']=0;artifact['predictions']={}
        pool,coverage=self.check(fixture)
        self.assertEqual(len(pool['records']),120)
        self.assertEqual(coverage['observed_queries'],0);self.assertFalse(coverage['complete_coverage'])
        # Scorer receives every task plus the unmodified full challenge set;
        # omitted tests remain missing, never filtered from challenge denominator.
        self.assertEqual(sum(len(t['test']) for t in self.owner.challenges.values()),167)
        self.assertTrue(all(r['tests']==[] for r in pool['records']))

if __name__=='__main__':unittest.main(verbosity=2)
