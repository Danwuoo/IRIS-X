"""Complete synthetic224-slot production freeze/ledger binding tests; CPU only."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_timing_refresh import row, calibration, ORIGINAL, ROOT
from tools.arc_qwen_transfer_20261012 import timing_refresh as tr
from tools.arc_learning_agent_20261011.budget import WorkLedger,atomic_json
from tools.arc_qwen_transfer_20261012.protocol import file_sha

class FreezeBindings(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root=Path(self.tmp.name);self.ledger=WorkLedger(self.root/'ledger.jsonl');self.sources=tr.timing_sources()
        self.cal=calibration()
        for rung in self.cal['observations']:
            for state in rung['states'].values():
                for f in state['cache']['forwards']:
                    self.ledger.reserve(f['event_id'],{'scoring_forwards':1,'input_tokens':1})
                    self.ledger.complete(f['event_id'],{'scoring_forwards':1,'input_tokens':1})
        self.main_event_start=len(self.ledger.events)
        self.slots=tr.main_slots(self.root,[64,256]);self.bounds=[]
        for i,slot in enumerate(self.slots):
            r=row(1000+2*i,slot['mode'],slot['method'])['timing'];event=f'qwen14b-generation-{i+1}'
            self.ledger.reserve(event,{'generation_calls':1,'input_tokens':10000,'output_tokens':1024})
            self.ledger.complete(event,{'generation_calls':1,'input_tokens':r['forward_input_tokens'],'output_tokens':r['output_tokens']},status='failed' if i==0 else 'complete')
            r['physical_event_id']=event;r['wrapper_timing']['ledger_head_sha256']=self.ledger._previous
            r.update(valid=i!=0,finish_reason='length' if i==0 else 'eos',text='this opaque text is never inspected',target='opaque canary')
            path=slot['path'];atomic_json(path,r,exclusive=True)
            side=tr.write_generation_timing(path,r,native_invoked=True,started=1000+2*i,persisted=1000+2*i+.5)
            self.bounds.append({'receipt_path':str(path.absolute()),'timing_sha256':side['sha256'],'completed_monotonic':1000+2*i+.6})
        self.write_bounds()
    def tearDown(self):self.tmp.cleanup()
    def write_bounds(self):
        atomic_json(self.root/'main-timing-boundaries.json',{'format':'irisx/transfer-main-timing-boundaries-v1',
            'source_sha256':self.sources,'main_event_start':self.main_event_start,'main_started_monotonic':999,'calls':self.bounds})
    def freeze(self,**kw):
        with patch('time.monotonic',return_value=2000):
            return tr.freeze_public_refresh(self.root,updates=[64,256],calibration=self.cal,original=ORIGINAL,
                ledger=self.ledger,main_event_start=self.main_event_start,main_started=999,expected_sources=self.sources,**kw)[0]
    def mutate_side(self,index,fn):
        path=self.slots[index]['path'].with_suffix('.timing.json');r=json.loads(path.read_text());fn(r);atomic_json(path,r)
        self.bounds[index]['timing_sha256']=file_sha(path);self.write_bounds()
    def test_complete_224_with_failed_attempt_refreshes_and_freezes_once(self):
        r=self.freeze();self.assertEqual(r['status'],'MAIN_TIMING_REFRESHED',r['reason'])
        self.assertEqual(r['coverage']['main_slots'],224);self.assertEqual(len(r['receipt_bindings']),224)
        self.assertEqual(r['ledger']['physical_usage']['generation_calls'],224)
        self.assertEqual(r['original_measurements'],ORIGINAL)
        self.assertEqual(r['selected_estimate']['output_cap_reserved'],1024)
        self.assertFalse(r['target_outcomes_used']);self.assertFalse(r['outcome_filtering'])
        with self.assertRaises((FileExistsError,ValueError)):self.freeze()
    def test_opaque_receipt_tampering_forces_exact_baseline_fallback(self):
        self.slots[0]['path'].write_text('{}')
        r=self.freeze();self.assertEqual(r['status'],'CALIBRATION_FALLBACK')
        self.assertEqual(r['selected_measurements'],ORIGINAL);self.assertEqual(r['selected_estimate'],r['original_estimate'])
    def test_sidecar_event_cannot_be_duplicated(self):
        self.mutate_side(1,lambda r:r.update(physical_event_id='qwen14b-generation-1'))
        self.assertEqual(self.freeze()['status'],'CALIBRATION_FALLBACK')
    def test_sidecar_event_head_must_match_exact_charge(self):
        self.mutate_side(0,lambda r:r['wrapper_timing'].update(ledger_head_sha256='0'*64))
        self.assertEqual(self.freeze()['status'],'CALIBRATION_FALLBACK')
    def test_missing_boundary_cannot_omit_a_slot(self):
        self.bounds.pop();self.write_bounds()
        self.assertEqual(self.freeze()['status'],'CALIBRATION_FALLBACK')
    def test_extra_physical_generation_cannot_be_omitted(self):
        self.ledger.reserve('unreported',{'generation_calls':1});self.ledger.complete('unreported',{'generation_calls':1},status='failed')
        self.assertEqual(self.freeze()['status'],'CALIBRATION_FALLBACK')
    def test_pending_unknown_cannot_be_refunded_or_ignored(self):
        self.ledger.reserve('unknown',{'generation_calls':1});self.ledger.unknown('unknown','synthetic')
        r=self.freeze();self.assertEqual(r['status'],'CALIBRATION_FALLBACK');self.assertTrue(self.ledger.pending)
        self.assertEqual(self.ledger.used['generation_calls'],225)
    def test_wrong_source_uses_no_cheap_subset(self):
        self.mutate_side(100,lambda r:r['source_sha256'].update({'tools/arc_qwen_transfer_20261012/backend.py':'0'*64}))
        r=self.freeze();self.assertEqual(r['status'],'CALIBRATION_FALLBACK');self.assertEqual(r['selected_measurements'],ORIGINAL)

if __name__=='__main__':unittest.main(verbosity=2)
