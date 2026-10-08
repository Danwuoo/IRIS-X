import unittest
import json
from pathlib import Path
import tempfile
from tools.arc_next_workflow import ArchitectureConfig,validate_config,run_architecture,normalize_messages,four_l4_contract,_run_architecture
class WorkflowTests(unittest.TestCase):
    def config(self,**kw): return ArchitectureConfig('missing','missing','missing','missing',**kw)
    def test_inert(self):
        self.assertEqual(run_architecture(self.config())['model_calls'],0)
    def test_budget_required(self):
        with self.assertRaises(ValueError):validate_config(self.config(enabled=True))
        with self.assertRaises(ValueError):validate_config(self.config(enabled=True,approved_max_cost_usd=1,estimated_hourly_cost_usd=10))
        validate_config(self.config(enabled=True,approved_max_cost_usd=10,estimated_hourly_cost_usd=10))
    def test_common_seed_compatible_messages(self):
        result=normalize_messages([{'role':'system','content':'a'},{'role':'user','content':'b'}])
        self.assertEqual(len(result),1);self.assertEqual(result[0]['role'],'user');self.assertIn('SYSTEM',result[0]['content'])
    def test_path_like_task_id_rejected_before_model_load(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'tasks.json';p.write_text(json.dumps({'../escape':{'train':[{'input':[[1]],'output':[[2]]}],'test':[{'input':[[3]]}]}}))
            c=ArchitectureConfig('missing','missing',str(p),str(Path(d)/'out'),enabled=True,approved_max_cost_usd=10,estimated_hourly_cost_usd=1)
            with self.assertRaisesRegex(ValueError,'eight-hex'):
                _run_architecture(c,loader=lambda *a,**k:self.fail('model load occurred'))
            self.assertFalse((Path(d)/'out').exists())
    def test_no_memory_pool_claim(self):
        contract=four_l4_contract('granite-4.2-8b')
        self.assertTrue(contract['aggregate_memory_is_not_pooled']);self.assertFalse(contract['gpu_runtime_verified'])
if __name__=='__main__':unittest.main()
