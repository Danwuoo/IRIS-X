"""Independent target-blind timing projection tests using synthetic scalar clocks."""
import copy
import os
from pathlib import Path
import sys
import unittest
ROOT=Path(os.environ.get('REVIEW_RUNTIME_ROOT',str(Path(__file__).resolve().parents[1]/'worktree'))).resolve()
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.arc_qwen_transfer_20261012 import timing_refresh as tr,call_policy as cp

ORIGINAL={'prefill_seconds_per_input':.001648618543307619,'decode_seconds_per_call':.070458,
          'full_seconds_per_input':.00050171168,'training_seconds_per_step':2.65468,'backend_load_seconds':157.9029}

def calibration():
    observations=[]
    for length in (128,512,2048,4096):
        states={}
        for name in ('base','updated','restored'):
            states[name]={'cache':{'forwards':[{'use_cache':True,'past_supplied':True,'started_monotonic':5.,
                'native_started_monotonic':5.1,'completed_monotonic':5.15,'input_tokens':1,
                'history_tokens':length,'event_id':f'{length}-{name}','status':'complete','late':False,'finite_full_head':True,
                'deadline_monotonic':125.,'work_deadline_monotonic':500.,'elapsed_seconds':5.15-5.}]}}
        observations.append({'length':length,'states':states})
    return {'completed_lengths':[128,512,2048,4096],'full_context_measured':True,
        'behavioral_cache_admitted':True,'full_state_restoration_verified':True,'observations':observations}

def row(t=1000., mode='base',method='base', count=3):
    window=cp.generation_window(100000,now=t+.01)
    trace=[]
    for i in range(count):
        begin=t+.1+i*.1
        trace.append({'input_tokens':4 if i==0 else 1,'attention_mask_tokens':4+i,
            'position_start':0 if i==0 else 3+i,'position_end':3+i,'cache_before':0 if i==0 else 3+i,
            'cache_after':4+i,'use_cache':True,'started_monotonic':begin,'completed_monotonic':begin+.05,
            'deadline_monotonic':window['work_deadline_monotonic']})
    r={'format':tr.TIMING_FORMAT,'native_invoked':True,'physical_event_id':f'event{t}',
        'evidence_timing':{'clock':'time.monotonic','started_monotonic':t,'receipt_persisted_monotonic':t+.5},
        'generation_call_policy':cp.policy(),'call_window':window,
        'wrapper_timing':{'clock':'time.monotonic','started_monotonic':t+.01,'native_entered_monotonic':t+.02,
            'native_returned_monotonic':t+.42,'completed_monotonic':t+.45},
        'native_timing':{'clock':'time.monotonic','entered_monotonic':t+.03,'returned_monotonic':t+.41,
            'forward_completion_synchronized':True,'forward_trace_source':'tools/arc_qwen_probe_20261012/decoder.py'},
        'adapter_execution_mode':mode,'decoder_mode':'cached','forward_calls':count,
        'forward_input_tokens':4+count-1 if count else 0,'input_tokens':4,'output_tokens':count,'forward_trace':trace}
    return {'timing':r,'mode':mode,'method':method,'scope':'dev','accounted_through_monotonic':t+.6}

def rows():return [row(1000,'base','base'),row(1001,'trained','sft64'),row(1002,'trained','sft256')]

class TimingReview(unittest.TestCase):
    def test_empirical_envelope_uses_maxima_and_full_cap(self):
        stats,cov=tr.derive_measurements(rows(),calibration(),ORIGINAL,now=2000)
        self.assertGreaterEqual(stats['prefill_seconds_per_input'],ORIGINAL['prefill_seconds_per_input'])
        self.assertAlmostEqual(stats['prefill_seconds_per_input'],.05/4)
        self.assertAlmostEqual(stats['decode_seconds_per_call'],.1)
        self.assertAlmostEqual(stats['generation_fixed_seconds'],.35)
        self.assertEqual(cov['calibration']['context_max'],4096)
        self.assertEqual(cov['output_tokens_max'],3)
        self.assertFalse(cov['target_outcomes_used']);self.assertFalse(cov['outcome_filtering'])
    def test_unrelated_training_reload_gaps_do_not_multiply_per_call_cost(self):
        before,_=tr.derive_measurements(rows(),calibration(),ORIGINAL,now=4000)
        after,_=tr.derive_measurements([row(1000,'base','base'),row(2001,'trained','sft64'),row(3002,'trained','sft256')],calibration(),ORIGINAL,now=4000)
        for key in ('generation_fixed_seconds','prefill_seconds_per_input','decode_seconds_per_call'):
            self.assertAlmostEqual(before[key],after[key])
    def test_quality_text_and_target_fields_are_never_used(self):
        baseline=tr.derive_measurements(rows(),calibration(),ORIGINAL,now=2000)
        for value in (True,False,None,'a'*5000):
            changed=rows()
            for item in changed:
                item['timing'].update(valid=value,correct=value,text=value,prediction=value,target=value,finish_reason=value)
            self.assertEqual(tr.derive_measurements(changed,calibration(),ORIGINAL,now=2000),baseline)
    def test_every_slower_attempt_is_included_even_failed(self):
        changed=rows();r=changed[-1]['timing'];r['valid']=False;r['finish_reason']='length'
        r['forward_trace'][-1]['started_monotonic']+=.02;r['forward_trace'][-1]['completed_monotonic']+=.02
        stats,cov=tr.derive_measurements(changed,calibration(),ORIGINAL,now=2000)
        self.assertAlmostEqual(stats['decode_seconds_per_call'],.12)
    def test_no_rows_or_no_adjacent_steps_cannot_refresh(self):
        for changed in ([],[row(1000,'base',count=1),row(1001,'trained',count=1)]):
            with self.assertRaises(ValueError):tr.derive_measurements(changed,calibration(),ORIGINAL,now=2000)
    def test_context_output_and_cache_corruption_reject(self):
        mutations=[('output_tokens',1025),('forward_calls',0),('input_tokens',3073),('decoder_mode','full_prefix')]
        for key,value in mutations:
            changed=rows();changed[0]['timing'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):tr.derive_measurements(changed,calibration(),ORIGINAL,now=2000)
        for key,value in [('cache_after',0),('position_end',99),('attention_mask_tokens',999),('input_tokens',3),('use_cache',False)]:
            changed=rows();changed[0]['timing']['forward_trace'][1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):tr.derive_measurements(changed,calibration(),ORIGINAL,now=2000)
    def test_nonfinite_future_or_unordered_clock_reject(self):
        for bad in (float('nan'),float('inf'),99999,999):
            changed=rows();changed[0]['timing']['forward_trace'][0]['completed_monotonic']=bad
            with self.subTest(bad=bad),self.assertRaises(ValueError):tr.derive_measurements(changed,calibration(),ORIGINAL,now=2000)
    def test_missing_calibration_context_or_timing_reject(self):
        for which in ('rung','native'):
            cal=calibration()
            if which=='rung':cal['completed_lengths']=[128,512,2048]
            else:del cal['observations'][-1]['states']['restored']['cache']['forwards'][0]['native_started_monotonic']
            with self.subTest(which=which),self.assertRaises((ValueError,KeyError,TypeError)):
                tr.derive_measurements(rows(),cal,ORIGINAL,now=2000)
    def test_no_measured_trained_forwards_cannot_satisfy_mode_coverage(self):
        changed=[row(1000,'base'),row(1001,'trained',count=0)]
        with self.assertRaises(ValueError):tr.derive_measurements(changed,calibration(),ORIGINAL,now=2000)
    def test_operationally_late_wrapper_cannot_refresh(self):
        changed=rows();r=changed[-1]['timing'];r['wrapper_timing']['completed_monotonic']=1200
        r['evidence_timing']['receipt_persisted_monotonic']=1200.1;changed[-1]['accounted_through_monotonic']=1200.2
        with self.assertRaises(ValueError):tr.derive_measurements(changed,calibration(),ORIGINAL,now=2000)
    def test_complete_fixed_main_slot_inventory(self):
        slots=tr.main_slots(Path('/tmp/synthetic'),[64,256]);self.assertEqual(len(slots),224)
        self.assertEqual(len({s['path'] for s in slots}),224)
        from collections import Counter
        self.assertEqual(Counter(s['method'] for s in slots),{'base':96,'sft64':32,'sft256':32,'selected-sft':64})

if __name__=='__main__':unittest.main(verbosity=2)
