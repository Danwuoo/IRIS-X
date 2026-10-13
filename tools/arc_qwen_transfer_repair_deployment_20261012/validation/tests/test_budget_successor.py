"""Explicit synthetic interface tests. No model/provider/scorer execution."""
import copy
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import unittest

VALIDATION=Path(__file__).resolve().parents[1]
ROOT=VALIDATION.parent
OLD=ROOT.parent/'portfolio63-next-20261012'
sys.path.insert(0,str(VALIDATION))
import validate_transfer_outputs as v
import budget_checks as b

class Archive:
    synthetic=True
    def __init__(self):self.members={}
    def read(self,name):
        if 'target-escrow' in name:raise AssertionError('gold read attempted')
        v.need(name in self.members,'missing evidence member: '+name)
        return self.members[name]
    def json(self,name):return v.strict_json(self.read(name))
    def put(self,name,value):self.members[name]=v.canonical(value)

def window(start=10.0,branch=5000.0):
    hard=min(branch,start+180.0)
    return {'call_kind':'generation','call_policy_sha256':b.digest(b.POLICY),'started_monotonic':start,
        'branch_deadline_monotonic':branch,'work_deadline_monotonic':hard-min(5.0,(hard-start)*.1),'deadline_monotonic':hard}

def timing_fixture():
    a=Archive();sources={n:'a'*64 for n in b.TIMING_SOURCES}
    request={'source_identity':sources,'output_root':'/synthetic/owner','work_deadline':5000.,'config':{'tiny_cpu':False}}
    stats={'training_seconds_per_step':.1,'prefill_seconds_per_input':.001,'decode_seconds_per_call':.08,'full_seconds_per_input':.001,'backend_load_seconds':20.}
    calibration={'completed_lengths':[128,512,2048,4096],'full_context_measured':True,'behavioral_cache_admitted':True,'full_state_restoration_verified':True,'observations':[]}
    for length in calibration['completed_lengths']:
        calibration['observations'].append({'length':length,'states':{state:{'cache':{'forwards':[{'event_id':str(length)+'-'+state,'use_cache':True,'past_supplied':True,'started_monotonic':2.,'native_started_monotonic':2.1,'completed_monotonic':2.11,'input_tokens':1,'history_tokens':length}]}} for state in ('base','updated','restored')}})
    a.put('calibration/calibration.json',calibration)
    events=[{'event':'opened','caps':v.CAPS}];bound=[];bindings=[];timings=[];previous='0'*64
    def event(row):
        nonlocal previous
        row.update(index=len(events),previous=previous);row['sha256']=v.digest(row);previous=row['sha256'];events.append(row);return row
    events[0].update(index=0,previous=previous);events[0]['sha256']=v.digest(events[0]);previous=events[0]['sha256']
    groups=[('dev','base',16,'base'),('dev','sft64',16,'trained'),('dev','sft256',16,'trained'),('holdout','base',32,'base'),('holdout','selected-sft',32,'trained')]
    i=0
    for scope,method,n,mode in groups:
        for index in range(n):
            for op in (0,1):
                start=100.+i;eid='qwen14b-generation-'+str(i+1);i+=1;w=window(start);soft=w['work_deadline_monotonic']
                amount={'generation_calls':1,'input_tokens':4,'output_tokens':2};event({'event':'reserved','event_id':eid,'amounts':amount});closed=event({'event':'complete','event_id':eid,'amounts':amount})
                trace=[{'input_tokens':3 if step==0 else 1,'attention_mask_tokens':3+step,'position_start':0 if step==0 else 3,'position_end':2+step,'cache_before':0 if step==0 else 3,'cache_after':3+step,'use_cache':True,'started_monotonic':start+.03+step*.02,'completed_monotonic':start+.04+step*.02,'deadline_monotonic':soft} for step in (0,1)]
                native={'physical_event_id':eid,'adapter_execution_mode':mode,'decoder_mode':'cached','generation_call_policy':b.POLICY,'call_window':w,
                    'wrapper_timing':{'clock':'time.monotonic','started_monotonic':start,'native_entered_monotonic':start+.01,'native_returned_monotonic':start+.08,'completed_monotonic':start+.09,'ledger_head_sha256':closed['sha256']},
                    'native_timing':{'clock':'time.monotonic','entered_monotonic':start+.02,'returned_monotonic':start+.07,'forward_completion_synchronized':True,'forward_trace_source':'tools/arc_qwen_probe_20261012/decoder.py'},
                    'forward_calls':2,'forward_input_tokens':4,'input_tokens':3,'output_tokens':2,'forward_trace':trace,'valid':False,'dispatched':True,'text':'not an outcome input'}
                path='%s/%s/%03d-%d.json'%(scope,method,index,op);member='experiment/'+path;side=member[:-5]+'.timing.json';a.put(member,native)
                r={k:native[k] for k in ('physical_event_id','adapter_execution_mode','decoder_mode','generation_call_policy','call_window','wrapper_timing','native_timing','forward_calls','forward_input_tokens','input_tokens','output_tokens','forward_trace')}
                r.update(format='irisx/transfer-native-generation-timing-v1',source_sha256=sources,receipt_sha256=v.raw_sha(a.read(member)),native_invoked=True,evidence_timing={'clock':'time.monotonic','started_monotonic':start-.01,'receipt_persisted_monotonic':start+.1});a.put(side,r)
                bound.append({'receipt_path':request['output_root']+'/'+member,'timing_sha256':v.raw_sha(a.read(side)),'completed_monotonic':start+.11})
                bindings.append({'path':path,'sha256':r['receipt_sha256'],'timing_sha256':v.raw_sha(a.read(side)),'physical_event_id':eid,'event_sha256':closed['sha256']})
                timings.append({'timing':r,'mode':mode,'method':scope+'/'+method,'accounted_through_monotonic':start+.11})
    a.members['physical-work.jsonl']=b''.join(v.canonical(r) for r in events);ledger=v.ledger_replay(a.read('physical-work.jsonl'),require_closed=True)
    a.put('experiment/main-timing-boundaries.json',{'format':'irisx/transfer-main-timing-boundaries-v1','source_sha256':sources,'main_event_start':1,'main_started_monotonic':99.,'calls':bound})
    selected,coverage=b.derive_timing_measurements(timings,calibration,stats,1000.)
    refresh={'format':'irisx/transfer-public-cost-refresh-v1','frozen_monotonic':1000.,'main_started_monotonic':99.,'target_outcomes_used':False,'outcome_filtering':False,'forecast_is_guarantee':False,
        'original_measurements':stats,'original_estimate':b.public_estimate(stats),'refreshed_measurements':selected,'refreshed_estimate':b.public_estimate(selected),'selected_measurements':selected,'selected_estimate':b.public_estimate(selected),
        'status':'MAIN_TIMING_REFRESHED','reason':'complete-source-event-clock-context-coverage','coverage':coverage,'source_sha256':sources,'source_identity_sha256':b.digest(sources),'calibration_sha256':b.digest(calibration),'main_event_start':1,
        'receipt_bindings':bindings,'receipt_bindings_sha256':b.digest(bindings),'ledger':{'path':request['output_root']+'/physical-work.jsonl','sha256':v.raw_sha(a.read('physical-work.jsonl')),'head_sha256':ledger['last_sha256'],'event_count':len(events),'physical_usage':ledger['used']},
        'boundaries':{'path':request['output_root']+'/experiment/main-timing-boundaries.json','sha256':v.raw_sha(a.read('experiment/main-timing-boundaries.json'))},'cpu_fixture_only':False}
    a.put('experiment/public-cost-refresh.json',refresh)
    return a,request,ledger,stats

class GenerationBudget(unittest.TestCase):
    def test_api_frozen(self):self.assertEqual(str(inspect.signature(v.validate_outputs)), '(download_root, *, manifest, finalization, launch_journal, launch_receipt, retrieval_receipt, finalized_notebook, allow_synthetic=False)')
    def test_historical_bytes_preserved(self):
        if not (OLD/'validation/VALIDATION-ARTIFACTS.json').exists():self.skipTest('historical sibling fixture not included in portable subset')
        entries=v.json_file(OLD/'validation/VALIDATION-ARTIFACTS.json')['validator_files']
        for row in entries:self.assertEqual(v.file_sha(OLD/row['path']),row['sha256'])
    def test_exact_normal_window(self):self.assertEqual(b.validate_window(window()),(10.,185.,190.))
    def test_short_remaining_cleanup(self):self.assertEqual(b.validate_window(window(10.,12.)),(10.,11.8,12.))
    def test_bad_window(self):
        for key,value in [('deadline_monotonic',130.),('work_deadline_monotonic',186.),('branch_deadline_monotonic',True),('call_policy_sha256','0'*64),('started_monotonic',float('nan'))]:
            with self.subTest(key=key),self.assertRaises(ValueError):b.validate_window({**window(),key:value})
    def test_owner_deadline(self):
        with self.assertRaises(ValueError):b.validate_window(window(),1000.)
    def test_old120_call_policy_rejected(self):
        w=window();w['deadline_monotonic']=130.;w['work_deadline_monotonic']=125.
        with self.assertRaises(ValueError):b.validate_window(w)
    def test_source_no_relabel(self):
        if not (OLD/'worktree').is_dir():self.skipTest('historical sibling source not included in portable subset')
        source=v.SourceSnapshot(OLD/'worktree',v.source_identity(OLD/'worktree'))
        try:
            with self.assertRaises(ValueError):b.validate_source_policy(source)
        finally:source.close()
    def test_successor_source(self):
        if not (ROOT/'worktree').is_dir():self.skipTest('exact runtime source not included beside portable validator subset')
        source=v.SourceSnapshot(ROOT/'worktree',v.source_identity(ROOT/'worktree'))
        try:b.validate_source_policy(source,synthetic=True)
        finally:source.close()
    def test_admission_generation175_score115(self):
        x={'generation_call_policy':b.POLICY,'decision_monotonic':10.,'branch_deadline_monotonic':5000.,'remaining_seconds':4990.,'generation_work_seconds_available':175.,'score_work_seconds_available':115.,'generation_per_call_admitted':True,'score_per_call_admitted':False,'actual_timeout_observed':False}
        self.assertFalse(b.validate_admission_window(x,100.,80.,1,1))
        x['score_per_call_admitted']=True;self.assertTrue(b.validate_admission_window(x,100.,75.,1,1))
    def test_forecast_is_not_timeout(self):
        with self.assertRaises(ValueError):b.validate_admission_window({'generation_call_policy':b.POLICY},1,1,1,1)

class RefreshEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=timing_fixture()
    def setUp(self):self.a,self.request,self.ledger,self.stats=copy.deepcopy(self.original)
    def validate(self):return b.validate_public_refresh(self.a,self.request,self.ledger,self.stats)
    def mutate(self,name,fn):value=self.a.json(name);fn(value);self.a.put(name,value)
    def test_positive_all224_timing_only(self):
        selected=self.validate();self.assertLess(selected['decode_seconds_per_call'],self.stats['decode_seconds_per_call']);self.assertEqual(self.a.json('experiment/public-cost-refresh.json')['coverage']['main_slots'],224)
    def test_missing_sidecar(self):
        self.a.members.pop('experiment/dev/base/000-0.timing.json')
        with self.assertRaises(ValueError):self.validate()
    def test_exact_generation_calls_and_active_marker(self):
        last=self.a.json('experiment/holdout/selected-sft/031-1.json')
        self.a.put('active-call.json',{**last['call_window'],'event_id':last['physical_event_id'],'status':'closed'})
        self.assertEqual(b.validate_calls(self.a,self.request,self.ledger)['generation_receipts'],224)
    def test_generation_active_marker_budget_tamper(self):
        last=self.a.json('experiment/holdout/selected-sft/031-1.json')
        self.a.put('active-call.json',{**last['call_window'],'event_id':last['physical_event_id'],'status':'closed','deadline_monotonic':4999.})
        with self.assertRaises(ValueError):b.validate_calls(self.a,self.request,self.ledger)
    def test_call_policy_receipt_missing(self):
        self.mutate('experiment/dev/base/000-0.json',lambda r:r.pop('generation_call_policy'))
        with self.assertRaises(ValueError):b.validate_calls(self.a,self.request,self.ledger)
    def test_wrapper_late_receipt_rejected(self):
        row=self.a.json('experiment/dev/base/000-0.json');row['wrapper_timing']['completed_monotonic']=row['call_window']['deadline_monotonic']
        with self.assertRaises(ValueError):b.validate_generation_receipt(row,self.ledger,self.request['work_deadline'])
    def test_all_invalid_outcomes_are_still_timed(self):
        self.assertTrue(all(self.a.json('experiment/'+r['path'])['valid'] is False for r in self.a.json('experiment/public-cost-refresh.json')['receipt_bindings']))
        self.assertEqual(self.a.json('experiment/public-cost-refresh.json')['coverage']['native_invoked_calls'],224)
        self.validate()
    def test_full_cap_no_early_eos_discount(self):
        estimate=self.a.json('experiment/public-cost-refresh.json')['selected_estimate']
        self.assertEqual(estimate['output_cap_reserved'],1024);self.assertEqual(estimate['input_tokens'],334*4095)
    def test_public_admission_requires_exact_refresh_ref(self):
        refresh=self.a.json('experiment/public-cost-refresh.json')
        self.a.put('experiment/public/forecast.json',{**refresh['selected_estimate'],'decision_monotonic':1001.,'cost_refresh':{'path':self.request['output_root']+'/experiment/public-cost-refresh.json','sha256':'0'*64}})
        with self.assertRaises(ValueError):self.validate()
    def test_bad_opaque_receipt(self):
        self.mutate('experiment/dev/base/000-0.json',lambda r:r.update(text='different'))
        with self.assertRaises(ValueError):self.validate()
    def test_outcome_field_in_timing(self):
        self.mutate('experiment/dev/base/000-0.timing.json',lambda r:r.update(valid=True))
        with self.assertRaises(ValueError):self.validate()
    def test_sidecar_clock_tamper(self):
        self.mutate('experiment/dev/base/000-0.timing.json',lambda r:r['wrapper_timing'].update(native_returned_monotonic=101.))
        with self.assertRaises(ValueError):self.validate()
    def test_delete_rehash_receipt_binding(self):
        def edit(r):r['receipt_bindings'].pop();r['receipt_bindings_sha256']=b.digest(r['receipt_bindings'])
        self.mutate('experiment/public-cost-refresh.json',edit)
        with self.assertRaises(ValueError):self.validate()
    def test_refresh_cannot_lower_arbitrary_rate(self):
        self.mutate('experiment/public-cost-refresh.json',lambda r:r['selected_measurements'].update(decode_seconds_per_call=0.))
        with self.assertRaises(ValueError):self.validate()
    def test_missing_boundary(self):
        self.a.members.pop('experiment/main-timing-boundaries.json')
        with self.assertRaises(ValueError):self.validate()
    def test_ledger_prefix_hash_tamper(self):
        self.mutate('experiment/public-cost-refresh.json',lambda r:r['ledger'].update(sha256='0'*64))
        with self.assertRaises(ValueError):self.validate()
    def test_freeze_before_main_is_rejected(self):
        self.mutate('experiment/public-cost-refresh.json',lambda r:r.update(frozen_monotonic=90.))
        with self.assertRaises(ValueError):self.validate()
    def test_fallback_retains_exact_baseline(self):
        def edit(r):r.update(status='CALIBRATION_FALLBACK',reason='unsupported-timing-coverage: ValueError: test fixture',coverage=None,refreshed_measurements=None,refreshed_estimate=None,selected_measurements=r['original_measurements'],selected_estimate=r['original_estimate'])
        self.mutate('calibration/calibration.json',lambda r:r.update(completed_lengths=[128,512],full_context_measured=False))
        self.mutate('experiment/public-cost-refresh.json',lambda r:r.update(calibration_sha256=b.digest(self.a.json('calibration/calibration.json'))))
        self.mutate('experiment/public-cost-refresh.json',edit);self.assertEqual(self.validate(),self.stats)
    def test_fallback_cannot_cheapen_forecast(self):
        def edit(r):r.update(status='CALIBRATION_FALLBACK',reason='unsupported-timing-coverage: test',refreshed_measurements=None,refreshed_estimate=None,coverage=None)
        self.mutate('experiment/public-cost-refresh.json',edit)
        with self.assertRaises(ValueError):self.validate()

if __name__=='__main__':unittest.main()
