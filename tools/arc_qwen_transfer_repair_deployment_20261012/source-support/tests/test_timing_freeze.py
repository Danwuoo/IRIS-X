"""Synthetic CPU contracts for the complete source/event/clock refresh boundary."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'worktree'),str(ROOT/'worktree'/'src')]
from tools.arc_qwen_transfer_20261012 import timing_refresh as t, science_profiles as sp
from tools.arc_qwen_transfer_20261012.call_policy import policy,generation_window
from tools.arc_learning_agent_20261011.budget import WorkLedger,atomic_json

STATS={'training_seconds_per_step':1.,'prefill_seconds_per_input':.001,
       'decode_seconds_per_call':.08,'full_seconds_per_input':.001,'backend_load_seconds':150.}

class Fixture:
    def __init__(self,root,*,exclude=None,nondispatch=None,cap=3):
        self.root=Path(root);self.sources=t.timing_sources();self.ledger=WorkLedger(self.root/'physical-work.jsonl')
        self.cal={'completed_lengths':[128,512,2048,4096],'full_context_measured':True,
            'behavioral_cache_admitted':True,'full_state_restoration_verified':True,'observations':[]}
        for j,length in enumerate(self.cal['completed_lengths']):
            rung={'length':length,'states':{}}
            for k,mode in enumerate(('base','updated','restored')):
                event='ladder-%d-%s-numeric-cached'%(length,mode);s=10+j*10+k
                self.ledger.reserve(event,{'scoring_forwards':1,'input_tokens':1})
                self.ledger.complete(event,{'scoring_forwards':1,'input_tokens':1})
                row={'event_id':event,'use_cache':True,'past_supplied':True,'input_tokens':1,
                    'history_tokens':length,'started_monotonic':s,'native_started_monotonic':s+.2,
                    'completed_monotonic':s+.22,'status':'complete','late':False,'finite_full_head':True,
                    'deadline_monotonic':s+120,'work_deadline_monotonic':10000.,'elapsed_seconds':s+.22-s}
                rung['states'][mode]={'cache':{'forwards':[row]}}
            self.cal['observations'].append(rung)
        self.start=len(self.ledger.events);self.bound=[];self.slots=t.main_slots(self.root,[64,256])
        for index,slot in enumerate(self.slots):
            native=index!=exclude;dispatch=native and index!=nondispatch
            event='qwen14b-generation-'+str(index+1) if native else None;s=1000+index*3
            window=generation_window(10000.,now=s+.1)
            traces=[]
            for i in range(cap if dispatch else 0):
                began=s+.5+i*.1;end=began+.02
                traces.append({'input_tokens':10 if i==0 else 1,'attention_mask_tokens':10+i,
                    'position_start':0 if i==0 else 9+i,'position_end':9+i,'cache_before':0 if i==0 else 9+i,
                    'cache_after':10+i,'use_cache':True,'started_monotonic':began,'completed_monotonic':end,
                    'deadline_monotonic':window['work_deadline_monotonic']})
            gen={'text':'arbitrary invalid output','valid':False,'finish_reason':'length','dispatched':dispatch,
                 'physical_event_id':event,'adapter_execution_mode':slot['mode'],'decoder_mode':'cached',
                 'generation_call_policy':policy(),'call_window':window,'forward_trace':traces,
                 'forward_calls':len(traces),'input_tokens':10 if dispatch else 0,
                 'forward_input_tokens':10+len(traces)-1 if dispatch else 0,'output_tokens':len(traces),
                 'native_timing':{'clock':'time.monotonic','entered_monotonic':s+.3,'returned_monotonic':s+1,
                    'forward_completion_synchronized':True,'forward_trace_source':'tools/arc_qwen_probe_20261012/decoder.py'},
                 'wrapper_timing':{'clock':'time.monotonic','started_monotonic':s+.1,
                    'native_entered_monotonic':s+.2,'native_returned_monotonic':s+1.1,'completed_monotonic':s+1.2}}
            if native:
                self.ledger.reserve(event,{'generation_calls':1,'input_tokens':4000,'output_tokens':1024})
                self.ledger.complete(event,{'generation_calls':int(dispatch),'input_tokens':gen['forward_input_tokens'],
                    'output_tokens':gen['output_tokens']},status='failed' if dispatch else 'excluded')
                gen['wrapper_timing']['ledger_head_sha256']=self.ledger._previous
            path=slot['path'];atomic_json(path,gen,exclusive=True)
            ref=t.write_generation_timing(path,gen,native_invoked=native,started=s,persisted=s+1.3)
            self.bound.append({'receipt_path':str(path.absolute()),'timing_sha256':ref['sha256'],'completed_monotonic':s+1.4})
        self.write_bound()
    def write_bound(self):
        atomic_json(self.root/'main-timing-boundaries.json',{'format':'irisx/transfer-main-timing-boundaries-v1',
            'source_sha256':self.sources,'main_event_start':self.start,'main_started_monotonic':1000.,'calls':self.bound})
    def modify(self,index,edit):
        p=self.slots[index]['path'].with_suffix('.timing.json');r=json.loads(p.read_bytes());edit(r);atomic_json(p,r)
        self.bound[index]['timing_sha256']=t.file_sha(p);self.write_bound()
    def freeze(self):
        with patch('time.monotonic',return_value=2000.):
            return t.freeze_public_refresh(self.root,updates=[64,256],calibration=self.cal,original=STATS,
                ledger=self.ledger,main_event_start=self.start,main_started=1000.,expected_sources=self.sources)[0]

class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tmp');self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_all224_linked_invalid_truncated_attempts_refresh(self):
        f=Fixture(self.root);r=f.freeze()
        self.assertEqual(r['status'],'MAIN_TIMING_REFRESHED',r['reason'])
        self.assertEqual(r['coverage']['main_slots'],224)
        self.assertEqual(r['coverage']['adjacent_completion_samples'],448)
        self.assertEqual(r['selected_estimate']['generations'],334)
        self.assertEqual(r['selected_estimate']['output_cap_reserved'],1024)
        self.assertEqual(r['selected_estimate']['safety_multiplier'],1.5)
        self.assertEqual(r['coverage']['calibration']['context_max'],4096)
        self.assertFalse(r['outcome_filtering']);self.assertFalse(r['forecast_is_guarantee'])
        self.assertEqual(r['original_estimate'],sp.forecast(STATS,updates=0,generations=334,reloads=2))
        self.assertEqual(len(r['receipt_bindings']),224)
        self.assertLess(r['coverage']['fixed_per_call_seconds'],2)
        self.assertTrue(all(row['event_sha256'] for row in r['receipt_bindings']))
    def test_context_exclusion_and_native_nondispatch_accounted(self):
        r=Fixture(self.root,exclude=0,nondispatch=32).freeze()
        self.assertEqual(r['status'],'MAIN_TIMING_REFRESHED',r['reason'])
        self.assertEqual(r['coverage']['native_invoked_calls'],223)
        self.assertIsNone(r['receipt_bindings'][0]['physical_event_id'])
    def test_missing_sidecar_preserves_original_forecast(self):
        f=Fixture(self.root);f.slots[0]['path'].with_suffix('.timing.json').unlink();r=f.freeze()
        self.assertEqual(r['status'],'CALIBRATION_FALLBACK')
        self.assertEqual(r['selected_estimate'],r['original_estimate']);self.assertIsNone(r['refreshed_estimate'])
    def test_missing_event_has_no_cheaper_fallback(self):
        f=Fixture(self.root);f.modify(0,lambda r:r.update(physical_event_id='missing'));r=f.freeze()
        self.assertEqual(r['status'],'CALIBRATION_FALLBACK');self.assertEqual(r['selected_measurements'],STATS)
    def test_extra_unrepresented_native_event_rejected(self):
        f=Fixture(self.root);f.ledger.reserve('extra',{'generation_calls':1});f.ledger.complete('extra',{'generation_calls':1})
        self.assertEqual(f.freeze()['status'],'CALIBRATION_FALLBACK')
    def test_incomplete_forward_trace_rejected(self):
        f=Fixture(self.root);f.modify(0,lambda r:r['forward_trace'].pop())
        self.assertEqual(f.freeze()['status'],'CALIBRATION_FALLBACK')
    def test_future_clock_rejected(self):
        f=Fixture(self.root);f.bound[0]['completed_monotonic']=3000;f.write_bound()
        self.assertEqual(f.freeze()['status'],'CALIBRATION_FALLBACK')
    def test_late_native_clock_rejected(self):
        f=Fixture(self.root);f.modify(0,lambda r:r['call_window'].update(work_deadline_monotonic=1000.9))
        self.assertEqual(f.freeze()['status'],'CALIBRATION_FALLBACK')
    def test_original_uninstrumented_calibration_falls_back(self):
        f=Fixture(self.root)
        del f.cal['observations'][0]['states']['base']['cache']['forwards'][0]['native_started_monotonic']
        r=f.freeze();self.assertEqual(r['status'],'CALIBRATION_FALLBACK')
        self.assertEqual(r['selected_estimate'],r['original_estimate'])
    def test_missing_long_calibration_context_falls_back(self):
        f=Fixture(self.root);f.cal['completed_lengths']=[128,512];f.cal['full_context_measured']=False
        self.assertEqual(f.freeze()['status'],'CALIBRATION_FALLBACK')
    def test_calibration_order_replays_from_canonical_json(self):
        f=Fixture(self.root);f.cal=json.loads(json.dumps(f.cal,sort_keys=True))
        self.assertEqual(f.freeze()['status'],'MAIN_TIMING_REFRESHED')
    def test_unknown_keeps_reservation_and_denies_refresh(self):
        f=Fixture(self.root);f.ledger.reserve('hung',{'generation_calls':1,'input_tokens':100})
        f.ledger.unknown('hung','synthetic timeout');before=dict(f.ledger.used)
        r=f.freeze();self.assertEqual(r['status'],'CALIBRATION_FALLBACK')
        self.assertEqual(f.ledger.used,before);self.assertTrue(f.ledger.pending)
    def test_immutable_freeze_cannot_be_reselected(self):
        f=Fixture(self.root);f.freeze()
        with self.assertRaises(ValueError):f.freeze()

if __name__=='__main__':unittest.main(verbosity=2)
