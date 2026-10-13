"""Genuine subprocess cleanup/charge preservation, no neural/GPU work."""
import json
from pathlib import Path
import sys
import time
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'worktree'),str(ROOT/'worktree'/'src')]
from tools.arc_qwen_transfer_20261012.runner import run_owned_transfer

class HungWatchdog(unittest.TestCase):
    def test_late_hung_native_is_stopped_and_reserved_work_stays(self):
        root=ROOT/'author-evidence'/('hung-owner-'+str(time.time_ns()))
        config={'enabled':True,'tiny_cpu':True,'test_fixture_dataset':True,
                'started_epoch':time.time(),'maximum_seconds':180}
        report=run_owned_transfer(config,root,python_command=[sys.executable,'-I','-B',str(ROOT/'tests/hung_child_fixture.py')])
        self.assertEqual(report['status'],'TRANSFER_FAILED',report)
        self.assertTrue(report['timed_out'],report)
        self.assertTrue(report['owned_process_closed'],report)
        self.assertFalse(report['closure_proof']['remaining'])
        self.assertLess(report['elapsed_seconds'],15)
        rows=[json.loads(line) for line in (root/'physical-work.jsonl').read_bytes().splitlines()]
        self.assertEqual([r['event'] for r in rows],['opened','reserved'])
        self.assertEqual(rows[-1]['amounts'],{'generation_calls':1,'input_tokens':3670016,'output_tokens':1024})
        self.assertEqual(json.loads((root/'active-call.json').read_bytes())['status'],'active')
        (ROOT/'author-evidence'/'hung-watchdog-owner-ref.json').write_text(json.dumps({'root':str(root),'report':report},indent=2)+'\n')
if __name__=='__main__':unittest.main(verbosity=2)
