"""Keep the unchanged evaluator compact schema; main-only timing capture."""
from pathlib import Path
import sys,tempfile,time,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'worktree'),str(ROOT/'worktree'/'src')]
from tools.arc_qwen_transfer_20261012 import experiment as e

class Fake:
    def generate(self,*a,**kw):
        return {'valid':False,'dispatched':True,'physical_event_id':'qwen14b-generation-1','text':'bad',
                'forward_calls':0,'forward_input_tokens':0,'input_tokens':0,'output_tokens':0}
class Bindings(unittest.TestCase):
    def test_public_compact_keys_unchanged_and_no_timing_sidecar(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as td:
            p=Path(td)/'gen.json';case={'demos':[{'input':[[1]],'output':[[2]]}],'query_input':[[3]],'case_id':'fixture'}
            with patch.object(e,'pack_prompt',return_value=([{'role':'user','content':'x'}],{})):
                r=e.generate_variant(Fake(),case,0,p,time.monotonic()+10)
            self.assertEqual(set(r),{'transform_d4','inverse_applied','prediction','dispatched','physical_event_id','receipt_sha256','receipt_path'})
            self.assertFalse(p.with_suffix('.timing.json').exists())
    def test_main_context_exclusion_is_timed_without_invented_forward(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as td:
            p=Path(td)/'gen.json';case={'demos':[{'input':[[1]],'output':[[2]]}],'query_input':[[3]],'case_id':'fixture'}
            with patch.object(e,'pack_prompt',return_value=(None,{'reason':'synthetic context exclusion'})):
                r=e.generate_variant(Fake(),case,0,p,time.monotonic()+10,capture_timing=True)
            import json
            timing=json.loads(p.with_suffix('.timing.json').read_bytes())
            self.assertFalse(timing['native_invoked']);self.assertEqual(timing['forward_trace'],[])
            self.assertIsNone(timing['physical_event_id']);self.assertFalse(r['dispatched'])
            for key in ('text','valid','finish_reason','prediction','target','answers'):self.assertNotIn(key,timing)
if __name__=='__main__':unittest.main(verbosity=2)
