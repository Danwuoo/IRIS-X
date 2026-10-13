"""Independent source-to-native-record and scoped-gold integration tests."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'worktree'))
from tools.arc_qwen_transfer_20261012 import data as d
from tools.arc_learning_agent_20261011.data import validate_records
from tools.arc_learning_agent_20261011.budget import atomic_json

class DataIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.dataset=d.build_dataset({'tiny_cpu':True},Path(cls.temp.name)/'data')
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_global_native_validator_accepts_exact32_only(self):
        ds=self.dataset
        result=validate_records(ds['records'],ds['manifest'],())
        self.assertEqual(result['kind_counts'],{'grid':len(ds['records'])})
        train=set(ds['plan']['train_ids'])
        self.assertEqual(len(train),32)
        self.assertEqual({r['task_id'] for r in ds['records']},train)
        self.assertFalse(train & set(ds['plan']['dev_ids']+ds['plan']['holdout_ids']))
        changed=deepcopy(ds['records']); changed[0]['completion']='9'
        changed[0]['record_id']=d.native_digest({k:v for k,v in changed[0].items() if k!='record_id'})
        with self.assertRaises(ValueError): validate_records(changed,ds['manifest'],())

    def test_train_query_gold_stays_out_of_solver_and_manifest(self):
        ds=self.dataset
        self.assertEqual(ds['denominators'],{'dev':16,'holdout':32,'ttt_dev':8,'ttt_holdout':8})
        for c in ds['cases']:
            self.assertEqual(set(c),{'case_id','parent_id','scope','demos','query_input','source'})
            self.assertEqual(ds['manifest']['tasks'][c['parent_id']]['demonstrations'],c['demos'])
            self.assertEqual(len(c['demos']),2)
            self.assertNotIn('query_target',c)
            changed=deepcopy(c);changed['query_target']=[[9]]
            with self.assertRaises(ValueError): d.solver_case(changed)

    def test_dev_open_cannot_read_holdout_escrow(self):
        ds=self.dataset; scope='dev'
        payload={'case_ids':[c['case_id'] for c in ds['cases'] if c['scope']==scope],
                 'plan_sha256':ds['plan']['plan_sha256']}
        path=Path(self.temp.name)/'dev-seal.json'; atomic_json(path,payload,exclusive=True)
        seal={'sealed':True,'scope':scope,'path':str(path),'file_sha256':d.file_sha(path)}
        checked=d.checked_json; reads=[]
        def guarded(path,*args,**kwargs):
            reads.append(str(path))
            if 'holdout-target' in str(path): raise AssertionError('holdout gold was opened during dev selection')
            return checked(path,*args,**kwargs)
        with patch.object(d,'checked_json',side_effect=guarded): result=d.open_targets(ds,scope,seal)
        self.assertEqual(set(result),set(payload['case_ids']))
        self.assertEqual(len(result),16)
        self.assertTrue(any('dev-target' in path for path in reads))
        self.assertFalse(any('holdout' in path for path in reads))
        wrong={**seal,'scope':'holdout'}
        with self.assertRaises(ValueError): d.open_targets(ds,'dev',wrong)

    def test_single_demo_outer_fold_is_complete_zero_context_supervision(self):
        demos=[{'input':[[0,1,2],[3,4,5]],'output':[[0,6],[7,8],[9,1]]}]
        rows=d.build_task_records('a-fold',demos,augmentations=8,seed=1917)
        self.assertEqual(len(rows),8)
        for r in rows:
            self.assertEqual(r['provenance']['visible_demo_indices'],[])
            self.assertNotIn('Demonstration 1',r['messages'][-1]['content'])
            self.assertEqual(r['provenance']['held_out_demo'],0)
            self.assertEqual(r['provenance']['transfer_record']['demo_count'],1)
            self.assertEqual(r['parent_ids'],['a-fold'])
        d.validate_task_records(rows,'a-fold')
        with self.assertRaises(ValueError): d.validate_task_records(rows,'other-fold')

    def test_each_view_applies_inverse_to_the_full_grid(self):
        source=[[0,1,2],[3,4,5]]
        for transform in d.transforms(1917):
            transformed=transform.apply(source)
            self.assertEqual(d._lists(transform.inverse().apply(transformed)),source)
            spec=d._transform_spec(transform)
            self.assertEqual(d.transform_grid(source,spec),d._lists(transformed))

if __name__=='__main__':unittest.main(verbosity=2)
