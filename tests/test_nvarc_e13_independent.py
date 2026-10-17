"""Independent E13 CPU protocol/fault checks; no credentials, provider or model calls."""
from tests.platform_requirements import requires_linux
import ast
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import nvarc_e13_admission as admission
from tools import nvarc_e13_answer_evidence as evidence
from tools import nvarc_e13_entry as entry

ROOT = Path(__file__).resolve().parents[1]


def _load_linux_runtime():
    global runtime, stage
    from tools import stage_nvarc_e13_search_budget as stage
    from tools import nvarc_e13_runtime as runtime

def snapshot(now=100000., remaining=6139.2461):
    stamp = datetime.fromtimestamp(now, timezone.utc)
    return dict(format='irisx/stage4-quota-observation-v1', provider='kaggle', account='danielwuu',
        observed_at=stamp.isoformat(), refresh_at=(stamp + timedelta(days=2)).isoformat(),
        primary_sha256='a'*64, typed_projection_sha256='b'*64,
        used_seconds=108000-remaining, reserved_seconds=0, total_seconds=108000,
        remaining_free_seconds=remaining, pay_to_scale_enabled=False,
        duration_units='provider charged quota seconds', permission_granted=False)


def plan_fixture(automatic=True):
    body=(ROOT/'tests/fixtures/e12/frozen-inert-001-plan.json').read_bytes()
    assert hashlib.sha256(body).hexdigest()=='f8000ab7db2a40795e93ff7482ad17ffa7fc817057207da7a9aadd6266739349'
    p=admission.parse(body)
    p.update(format=runtime.FORMAT, run_id=runtime.RUN_ID, screen_id=runtime.RUN_ID,
        source_commit='a'*40, resource_budget_profile=admission.RUN_BUDGET_PROFILE if automatic else runtime.BUDGET_PROFILE,
        generation_budget_profile=runtime.PROFILE, **runtime.TIMING, **runtime.CAPS,
        arm_contracts={a:runtime.arm_contract(a) for a in runtime.ARMS},
        arm_order=runtime.counterbalanced_order(runtime.TASK_COUNTS), per_arm_caps=dict(runtime.PER_ARM_CAPS),
        retained_model_layout=dict(runtime.MODEL_LAYOUT),e13_process_policy=dict(runtime.PROCESS_POLICY),
        verification_schedule='interleaved',verification_schedules=['interleaved'],cleanup_reserve_seconds=310,
        maximum_training_forwards=512, maximum_training_backwards=512, optimizer_steps=512,
        per_worker_training_steps=128,maximum_control_forwards=28,per_worker_forwards=7,
        expected_notebook_version=12,expected_previous_version=11,test_executions=12,
        owner_editor_only=not automatic,kernel_execution_type='RUN' if automatic else 'INERT',
        owner_editor_admission=None,resource_admission=None,
        **{k:automatic and k in admission.RUN_TRUE_FIELDS for k in admission.FALSE_FIELDS})
    if automatic:
        p['resource_admission']=admission.run_admission(p,snapshot(),admission.AUTHORIZATION_REF,
            quota_policy=admission.WAIVER_POLICY,current=False)
    else:p['owner_editor_admission']=admission.admission(p)
    return p


@requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
class IndependentProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _load_linux_runtime()

    def test_only_time_differs_between_search_contracts(self):
        short=runtime.arm_contract('search120');long=runtime.arm_contract('search240')
        self.assertEqual({k for k in short if short[k]!=long[k]},
            {'arm_id','generation_seconds','per_test_seconds'})
        self.assertEqual(short['training_updates'],128)
        self.assertEqual((short['generation_seconds'],short['per_test_seconds'],short['verification_reserve_seconds']),(120,150,30))
        self.assertEqual((long['generation_seconds'],long['per_test_seconds'],long['verification_reserve_seconds']),(240,270,30))
        self.assertEqual(short['dfs_probability_floor'],.2)
        self.assertEqual(short['schedule'],'interleaved')

    def test_counterbalance_is_exact_within_test_count_strata(self):
        order=runtime.counterbalanced_order(runtime.TASK_COUNTS)
        self.assertEqual(order,{'a47bf94d':['search120','search240'],'aa4ec2a5':['search240','search120'],
            '195c6913':['search120','search240'],'a25697e4':['search240','search120']})
        for count in (1,2):
            first=[order[k][0] for k,v in runtime.TASK_COUNTS.items() if v==count]
            self.assertCountEqual(first,runtime.ARMS)
        with self.assertRaises(RuntimeError):runtime.counterbalanced_order(dict(runtime.TASK_COUNTS,aa4ec2a5=2))

    def test_limits_are_not_doubled_for_long_search(self):
        self.assertEqual(evidence.PER_TEST,{'generation':4096,'verification':128,'input_tokens':5242880})
        for key,cap in runtime.PER_ARM_CAPS.items():self.assertEqual(runtime.CAPS[key],2*cap)
        p=plan_fixture();runtime.profile_for_plan(p)
        self.assertEqual((p['optimizer_steps'],p['test_executions']),(512,12))
        self.assertEqual((p['maximum_notebook_wall_seconds'],p['maximum_worker_seconds']),(3600,3120))

    def test_arm_allocations_reject_truncation_wrong_arm_and_bool_counters(self):
        for arm,seconds in [('search120',120),('search240',240)]:
            bound=dict(run_id=runtime.RUN_ID,**runtime.arm_contract(arm))
            value=runtime.paired_allocation(bound,0,100.,100.+seconds+30)
            self.assertEqual(runtime.allocation_deadlines(value,bound,0),(100.+seconds,130.+seconds))
            for field,bad in [('generation_seconds',seconds+1),('total_seconds',seconds),
                ('verification_reserve_seconds',0),('session_deadline_epoch',129.+seconds),
                ('test_index',False),('started_epoch',float('nan')),('extra',1)]:
                with self.subTest(arm=arm,field=field),self.assertRaises(RuntimeError):
                    runtime.allocation_deadlines(dict(value,**{field:bad}),bound,0)
            other=dict(run_id=runtime.RUN_ID,**runtime.arm_contract('search240' if arm=='search120' else 'search120'))
            with self.assertRaises(RuntimeError):runtime.allocation_deadlines(value,other,0)

    def test_training_cutoff_reserves_both_searches_and_terminal_reset(self):
        p=plan_fixture()
        for key,count in runtime.TASK_COUNTS.items():
            self.assertEqual(runtime.training_phase_deadline(p,key,3000.,1000.),min(2200.,3000.-180-count*420))
            for index,arm in enumerate(p['arm_order'][key]):
                future=sum(runtime.arm_contract(a)['per_test_seconds'] for a in p['arm_order'][key][index+1:])
                self.assertEqual(runtime.arm_inference_deadline(p,key,index,3000.),3000.-180-count*future)
            with self.assertRaises(RuntimeError):runtime.training_phase_deadline(p,key,1000.,1000.)

    def test_scope_mutation_breaks_admission_and_profile(self):
        original=plan_fixture()
        for key,bad in [('optimizer_steps',768),('per_worker_training_steps',192),
            ('maximum_generation_forwards',98304),('maximum_training_seconds',1201),
            ('expected_previous_version',10),('maximum_notebook_wall_seconds',3601),
            ('official_submission_authorized',True),('correctness_scored',True)]:
            p=copy.deepcopy(original);p[key]=bad
            with self.subTest(key=key),self.assertRaises(RuntimeError):runtime.profile_for_plan(p)
        p=copy.deepcopy(original);p['arm_contracts']['search240']['dfs_probability_floor']=.1
        with self.assertRaises(RuntimeError):runtime.profile_for_plan(p)

    def test_waiver_only_relaxes_conservative_quota_not_safety_gates(self):
        p=plan_fixture()
        with self.assertRaisesRegex(RuntimeError,'four-GPU-hour'):
            admission.run_admission(p,snapshot(),admission.AUTHORIZATION_REF,current=False)
        for field,bad in [('pay_to_scale_enabled',True),('remaining_free_seconds',0),
            ('remaining_free_seconds',True),('reserved_seconds',1),('account','other'),
            ('permission_granted',True),('used_seconds',float('inf')),('total_seconds',1),
            ('primary_sha256','unavailable')]:
            value=snapshot();value[field]=bad
            with self.subTest(field=field),self.assertRaises((RuntimeError,ValueError)):
                admission.run_admission(p,value,admission.AUTHORIZATION_REF,quota_policy=admission.WAIVER_POLICY,current=False)
        with self.assertRaises(RuntimeError):
            admission.run_admission(p,snapshot(),'prior-user-message',quota_policy=admission.WAIVER_POLICY,current=False)

    def test_freshness_enforced_at_send_but_not_fabricated_at_runtime(self):
        p=plan_fixture()
        admission.validate_resource_snapshot(snapshot(),now=lambda:100900.)
        for now in (99999.,100900.001,272800.):
            with self.assertRaises(RuntimeError):admission.validate_resource_snapshot(snapshot(),now=lambda:now)
        admission.validate_plan(p,current_resource=False)
        with self.assertRaises(RuntimeError):admission.validate_plan(p,current_resource=True,now=lambda:100901.)
        fields=admission.run_start_fields(p)
        self.assertIs(fields['quota_current_at_runtime'],False)
        self.assertIs(fields['owner_edited_notebook_config'],False)
        self.assertIs(fields['owner_minimum_four_hour_declaration'],False)

    def test_distinct_run_receipt_is_exclusive_and_old_receipt_cannot_admit(self):
        p=plan_fixture()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            value=admission.write_run_start(root,p,10.,now=lambda:100.,monotonic=lambda:10.)
            self.assertEqual(admission.verify_execution(root,p,now=lambda:101.,monotonic=lambda:11.),value)
            with self.assertRaises(FileExistsError):admission.write_run_start(root,p,10.,now=lambda:100.,monotonic=lambda:10.)
            for field,bad in [('run_id','stage4-e12-probe-prefix-20261008-003'),
                ('source_commit','b'*40),('plan_digest','sha256:'+'0'*64),('owner_edited_notebook_config',True)]:
                with self.subTest(field=field),self.assertRaises(RuntimeError):
                    admission.verify_start_value(dict(value,**{field:bad}),p,current=False)

    def test_entry_guard_checks_source_before_native_import(self):
        p=plan_fixture();raw={name:(ROOT/name).read_bytes() for name in stage.NEW_FILES}
        hashes={name:hashlib.sha256(body).hexdigest() for name,body in raw.items()}
        p['source_files_sha256']=hashes.copy();p['payload_sha256']=hashes
        raw['plan.json']=raw['screen.json']=admission.canonical(p)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,body in raw.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
            admission.write_run_start(root,p,time.monotonic())
            (root/'tools/nvarc_e13_runtime.py').write_text('raise AssertionError("tripwire")\n')
            import builtins
            original=builtins.__import__;seen=[]
            def guarded(name,*a,**kw):
                seen.append(name)
                if name in ('tools','tools.nvarc_e13_runtime','torch','numpy'):raise AssertionError('premature native import')
                return original(name,*a,**kw)
            with patch('builtins.__import__',side_effect=guarded),self.assertRaisesRegex(RuntimeError,'payload differs'):
                entry.main(['--root',str(root),'--dependency',str(root),'--expected-plan-sha256',admission.digest(p)[7:]])
            self.assertNotIn('tools.nvarc_e13_runtime',seen)

    def test_inert_default_notebook_is_really_inert(self):
        p=plan_fixture(False);raw={name:(ROOT/name).read_bytes() for name in stage.NEW_FILES}
        p['source_files_sha256']={name:hashlib.sha256(body).hexdigest() for name,body in raw.items()}
        p['payload_sha256']=p['source_files_sha256'].copy();raw['plan.json']=raw['screen.json']=admission.canonical(p)
        notebook=stage.render(p,raw);env={}
        with patch('builtins.__import__',side_effect=AssertionError('no import')),\
            patch('builtins.open',side_effect=AssertionError('no files')),patch('sys.stdout',new=io.StringIO()):
            for cell in notebook['cells'][1:]:exec(compile(''.join(cell['source']),'e13-inert-independent','exec'),env)
        self.assertIs(env[admission.CONFIG_NAME],False)
        self.assertNotIn('START',env);self.assertNotIn('PACKED',env)


@requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
class IndependentIsolationFaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _load_linux_runtime()

    def test_worker_has_one_training_site_and_no_reset_within_arm_loop(self):
        tree=ast.parse((ROOT/'tools/nvarc_e13_runtime.py').read_text())
        worker=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='worker')
        calls=[n for n in ast.walk(worker) if isinstance(n,ast.Call)]
        self.assertEqual(sum(isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name)
            and n.func.value.id=='trainer' and n.func.attr=='train' for n in calls),1)
        self.assertEqual(sum(isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name)
            and n.func.value.id=='engine' and n.func.attr=='trainer' for n in calls),1)
        loop=next(n for n in ast.walk(worker) if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple)
            and [t.id for t in n.target.elts if isinstance(t,ast.Name)]==['ordinal','arm_id'])
        arm_calls=[n for n in ast.walk(loop) if isinstance(n,ast.Call)]
        self.assertFalse(any(isinstance(n.func,ast.Attribute) and n.func.attr in ('restore','train','trainer') for n in arm_calls))
        restored=[n for n in arm_calls if isinstance(n.func,ast.Name) and n.func.id=='restore_rng']
        self.assertEqual(len(restored),1)
        self.assertEqual(ast.unparse(restored[0].args[1]),'post_state')

    def test_isolation_proof_rejects_state_rng_metadata_or_cache_drift(self):
        trained=[{'name':'synthetic','sha256':'a'*64}];metadata={'model_identity':123,'synthetic':True}
        rng=dict(python='sha256:'+'1'*64,numpy='sha256:'+'2'*64,torch_cpu='sha256:'+'3'*64,
            torch_cuda=['sha256:'+'4'*64])
        receipt=dict(before_inventory_digest=runtime.digest(trained),after_inventory_digest=runtime.digest(trained),
            model_before_metadata_digest=runtime.digest(metadata),model_after_metadata_digest=runtime.digest(metadata),
            generation_rng_before=rng,generation_rng_after=rng,model_identity_preserved=True,fresh_adapter=True,fresh_caches=True)
        rows=[dict(event='forward_reserved',phase='generation',test_index=i,input_ids_digest='sha256:'+'5'*64,
            batch_shape=[4,42],cached=False,position_start=0) for i in range(2)]
        files={'trained-before-inventory.json':trained,'trained-after-inventory.json':trained,
            'model-before-metadata.json':metadata,'model-after-metadata.json':metadata,'adapter-entry.json':runtime.adapter_entry()}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,value in files.items():(root/name).write_bytes(admission.canonical(value))
            self.assertEqual(set(runtime.verify_arm_isolation(root,trained,metadata,rng,receipt,2,rows)),{0,1})
            for field,bad in [('before_inventory_digest','sha256:'+'0'*64),('model_identity_preserved',False),
                ('fresh_adapter',1),('fresh_caches',False),('generation_rng_before',dict(rng,python='sha256:'+'9'*64))]:
                with self.subTest(field=field),self.assertRaises(RuntimeError):
                    runtime.verify_arm_isolation(root,trained,metadata,rng,dict(receipt,**{field:bad}),2,rows)
            for name,bad in [('trained-after-inventory.json',trained+[{}]),('model-after-metadata.json',dict(metadata,model_identity=456)),
                ('adapter-entry.json',dict(runtime.adapter_entry(),input_tokens=1))]:
                (root/name).write_bytes(admission.canonical(bad))
                try:
                    with self.subTest(file=name),self.assertRaises(RuntimeError):runtime.verify_arm_isolation(root,trained,metadata,rng,receipt,2,rows)
                finally:(root/name).write_bytes(admission.canonical(files[name]))
            for mutated in (rows[:1],[dict(rows[0],cached=True),rows[1]],[dict(rows[0],position_start=1),rows[1]]):
                with self.assertRaises(RuntimeError):runtime.verify_arm_isolation(root,trained,metadata,rng,receipt,2,mutated)

    def test_arm_telemetry_is_frozen_without_aliasing(self):
        snapshots={}
        with runtime.arm_inference_telemetry(snapshots,'search120') as first:
            first.begin_test(0,10.,40.)
        prior=copy.deepcopy(snapshots['search120'])
        first.tests['0']['termination_reason']='mutated-after-close'
        with runtime.arm_inference_telemetry(snapshots,'search240') as second:
            second.begin_test(0,20.,50.)
        self.assertEqual(snapshots['search120'],prior)
        self.assertIsNot(snapshots['search120']['tests'],snapshots['search240']['tests'])
        with self.assertRaises(RuntimeError):
            with runtime.arm_inference_telemetry(snapshots,'search120'):pass


if __name__=='__main__':unittest.main()
