"""Author adversaries: actual sealed tiny bytes plus explicit synthetic full-shape controls."""
import copy,hashlib,hmac,json,os,pickle,shutil,tempfile,unittest,zipfile
from pathlib import Path
from validation.safe_io import *
from validation.tensor_checks import *
from validation.audit_checks import summary,trajectory,validate_update
from validation.prediction_checks import generation,exact_scores
from validation.ledger_checks import replay_journal,validate_clock
from validation.public_checks import scorer_rows
from validation.validate_owned_outputs import validate_local_content

HERE=Path(__file__).resolve().parents[2]
WORKSPACE=HERE.parent
LEGACY=WORKSPACE/'portfolio63-rl-session-20261012'
NATIVE=LEGACY/'experiment_flow/evidence/native-003'
SOURCE='26a5b38d56239463ce94434a2d9cf126434484b5e6da3e8ed6004496b589ee50'
CORE='0e135a1915154d9f8f2385edf9601ed88fd0ca0c8758fe3146a54ba7f000e104'

def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(value)+b'\n')

class CoreSafetyTests(unittest.TestCase):
    def test_strict_json(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}',b'{"x":1e999}',b'[] garbage'):
            with self.subTest(raw=raw),self.assertRaises(EvidenceError):parse_json(raw)
    def test_path_controls(self):
        for value in ('../x','/tmp/a','a/../b','a//b','a\\b','a\x00b'):
            with self.subTest(value=value),self.assertRaises(EvidenceError):relative(value)
    def test_symlink_member(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'x').symlink_to('/etc/passwd')
            with self.assertRaises(EvidenceError):Root(root).inventory()
    def test_unknown_pickle_never_executes(self):
        torch=torch_module()
        with tempfile.TemporaryDirectory() as td:
            marker=Path(td)/'EXECUTED'
            class Unsafe:
                def __reduce__(self):return (eval,(f"__import__('pathlib').Path({str(marker)!r}).write_text('bad')",))
            path=Path(td)/'state.pt';torch.save({'x':Unsafe()},path)
            with self.assertRaises(EvidenceError):safe_load_state(path)
            self.assertFalse(marker.exists())
    def test_ambient_custom_globals_rejected(self):
        torch=torch_module()
        with torch.serialization.safe_globals([eval]):
            with self.assertRaises(EvidenceError):safe_load_state(NATIVE/'experiment/checkpoints/A/state.pt')
    def test_actual_safe_tensor_replay(self):
        for label in ('base','A','B','C'):
            with self.subTest(label=label):
                result=validate_checkpoint(Root(NATIVE/'experiment'),label,anchor_updates=1,expected_core_source_sha256=CORE,synthetic=True)
                self.assertTrue(is_sha(result['state_sha256']))
    def test_schedule_counter_mutations(self):
        source=safe_load_state(NATIVE/'experiment/checkpoints/A/state.pt')
        variants=[('scheduler',lambda s:s['scheduler'].__setitem__('last_epoch',True)),
                  ('step',lambda s:s['optimizer']['state'][0]['step'].fill_(2)),
                  ('recipe',lambda s:s.__setitem__('schedule_recipe','control-constant-2e4-v1')),
                  ('rate',lambda s:s['optimizer']['param_groups'][0].__setitem__('lr',1e-6)),
                  ('callable',lambda s:s['scheduler'].__setitem__('lr_lambdas',[{}])),
                  ('sampler',lambda s:s['counters'].__setitem__('sampler_cursor',2)),
                  ('source',lambda s:s.__setitem__('source_sha256','0'*64)),
                  ('nan',lambda s:next(iter(s['adapters'].values())).fill_(float('nan'))),
                  ('bool',lambda s:s['counters'].__setitem__('anchor_updates',True))]
        for name,mutate in variants:
            state=copy.deepcopy(source);mutate(state)
            with self.subTest(name=name),self.assertRaises(EvidenceError):validate_state(state,label='A',anchor_updates=1,expected_source_sha256=CORE,synthetic=True)
    def test_rehashed_tensor_corruption_not_metadata_proof(self):
        torch=torch_module()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);shutil.copytree(NATIVE/'experiment/checkpoints/A',root/'checkpoints/A');shutil.copy(NATIVE/'experiment/A-checkpoint-proof.json',root/'A-checkpoint-proof.json')
            state=safe_load_state(root/'checkpoints/A/state.pt');state['scheduler']['last_epoch']=0
            torch.save(state,root/'checkpoints/A/state.pt')
            manifest=parse_json((root/'checkpoints/A/manifest.json').read_bytes());manifest['files']['state.pt']=sha((root/'checkpoints/A/state.pt').read_bytes());manifest['state_sha256']=tree_sha(state);dump(root/'checkpoints/A/manifest.json',manifest)
            proof=parse_json((root/'A-checkpoint-proof.json').read_bytes());proof['manifest_file_sha256']=sha((root/'checkpoints/A/manifest.json').read_bytes());proof['save']=manifest;proof['reload']['state_sha256']=manifest['state_sha256'];dump(root/'A-checkpoint-proof.json',proof)
            with self.assertRaises(EvidenceError):validate_checkpoint(Root(root),'A',anchor_updates=1,expected_core_source_sha256=CORE,synthetic=True)

class NativeEvidenceTests(unittest.TestCase):
    def replay(self,root=None,allow=True):
        ds=Root(NATIVE/'authenticated-fixture-data')
        return validate_local_content(root or NATIVE/'experiment',source_root=LEGACY,expected_source_sha256=SOURCE,dataset_root=ds.path,expected_dataset_sha256=ds.file_sha('solver-dataset.json'),original_root=str((NATIVE/'experiment').resolve()),allow_synthetic=allow)
    def test_actual24_not288(self):
        r=self.replay();self.assertTrue(r['evidence_valid'],r['errors']);self.assertEqual(r['generation_count'],24);self.assertEqual(r['metering']['events'],83);self.assertFalse(r['production_admitted']);self.assertFalse(r['scientific_goal_met'])
    def test_default_synthetic_reject(self):
        r=self.replay(allow=False);self.assertFalse(r['evidence_valid']);self.assertIn('rejected by default',r['errors'][0])
    def test_required_artifact_omissions(self):
        for name in ('frozen-plan.json','source-inventory.json','base-checkpoint-proof.json','A-checkpoint-proof.json','B-checkpoint-proof.json','C-checkpoint-proof.json','checkpoints/A/state.pt','checkpoints/B/adapter/adapter_model.safetensors','audit/sweep-0.json','dev/A/000-0.json','dev/A/000-prediction.json','dev-predictions-sealed.json','dev-prediction-seal.json','dev-selection.json','holdout/C/001-1.json','holdout-scores.json','physical-metering-closure.json'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as td:
                root=Path(td)/'experiment';shutil.copytree(NATIVE/'experiment',root);(root/name).unlink();r=self.replay(root);self.assertFalse(r['evidence_valid'])
    def test_false_completion_and_wall(self):
        for field,value in [('status','complete'),('time_matching',{'matched':True}),('physical_events',[]),('model_closure',{'closed':True})]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as td:
                root=Path(td)/'experiment';shutil.copytree(NATIVE/'experiment',root);r=Root(root).json('result.json');r[field]=value;dump(root/'result.json',r);self.assertFalse(self.replay(root)['evidence_valid'])
    def test_raw_token_prediction_fabrication(self):
        root=Root(NATIVE/'experiment');result=root.json('result.json');case=Root(NATIVE/'authenticated-fixture-data').json('solver-dataset.json')['cases'][0]
        raw=root.json('dev/A/000-0.json');adapter=validate_checkpoint(root,'A',anchor_updates=1,expected_core_source_sha256=CORE,synthetic=True);events={e['event_id']:e for e in result['physical_events']};plan=root.json('frozen-plan.json')
        for field in ('token','text','prediction','status','prompt','adapter','physical'):
            r=copy.deepcopy(raw)
            if field=='token':r['generation']['output_token_ids']=[17];r['generation']['output_sha256']=digest([17])
            if field=='text':r['generation']['text']='9'
            if field=='prediction':r['prediction']=[[1]]
            if field=='status':r['status']='complete'
            if field=='prompt':r['packing']['prompt']+='hidden target'
            if field=='adapter':r['generation']['adapter_state_sha256']='0'*64
            if field=='physical':r['generation']['physical_event_id']=0
            with self.subTest(field=field),self.assertRaises((EvidenceError,ValueError)):generation(r,case=case,operation=0,adapter=adapter,events=events,inference=plan['inference'],synthetic=True)

class AuditFullShapeTests(unittest.TestCase):
    def fixture(self):
        parents=[f'p{i:02}' for i in range(32)];rows=[{'parent_id':p,'slot':k,'trajectory':{'dispatched':True},'eligible':True,'reward':int(k==0),'status':'eligible'} for p in parents for k in range(8)]
        return parents,{'sweep':0,'planned_attempts':256,'rows':rows,'closed':True,'all_slots_reached':True,'fatal_native_state':None}
    def test_controlled_full32x8_denominators(self):
        p,b=self.fixture();s=summary(b,p,8);self.assertEqual(s['planned_attempts'],256);self.assertEqual(s['eligible_mean_denominator'],256);self.assertEqual(s['pass_at_8_coverage'],32);self.assertEqual(s['mixed_groups'],32);self.assertEqual(s['eligible_mean_reward'],.125)
    def test_incomplete_never_zero_signal(self):
        p,b=self.fixture();b['rows'][-1].update(trajectory=None,eligible=False,reward=None,status='not-reached');s=summary(b,p,8);self.assertFalse(s['complete']);self.assertEqual(s['eligible_mean_denominator'],255);self.assertEqual(s['pass_at_8_coverage'],31)
    def test_reward_slot_mutations(self):
        for mutate in (lambda b:b['rows'].pop(),lambda b:b['rows'][0].update(slot=True),lambda b:b['rows'][0].update(eligible=False,reward=0),lambda b:b['rows'][0].update(status='not-reached'),lambda b:b['rows'][0].update(reward=True),lambda b:b['rows'][0].update(status='model-invalid')):
            p,b=self.fixture();mutate(b)
            with self.assertRaises(EvidenceError):summary(b,p,8)
    def test_full16_32_288_predictions_score_fixture(self):
        # Schema-only controlled grids, never relabeled actual neural generations.
        total=0
        for scope,n in [('dev',16),('holdout',32)]:
            ids=[f'{scope}:{i}' for i in range(n)];targets={cid:[[1]] for cid in ids}
            payload={'case_ids':ids,'methods':{a:[{'case_id':cid,'complete':True,'answers':[[[1]]] if i < {'A':0,'B':n,'C':n//2}[a] else []} for i,cid in enumerate(ids)] for a in 'ABC'}}
            scores=exact_scores(payload,targets);self.assertEqual(scores['B']['exact'],n);self.assertEqual(max('ABC',key=lambda a:scores[a]['exact']),'B');total+=n*3*2
        self.assertEqual(total,288)

class OwnedEvidenceTests(unittest.TestCase):
    source='1006de9d85a4cf6ca5502ec94f3ddd250bd77da0afc8c4fb9fe9fa028caac774'
    original=WORKSPACE/'portfolio63-rl-owned-proof-002'
    snapshot=HERE/'lineage/native-proof-002-source'
    def replay(self,root=None,allow=True):
        from validation.validate_owned_outputs import validate_owned_outputs
        ds=Root(self.original/'authenticated-fixture-data')
        return validate_owned_outputs(root or self.original,source_root=self.snapshot,expected_source_sha256=self.source,expected_dataset_sha256=ds.file_sha('solver-dataset.json'),allow_synthetic=allow,checkpoint_mode="full-materialized")
    def reseal(self,root):
        value=Root(root).json('artifact-inventory.json');files={};evidence=checkpoints=0
        for p in sorted(Path(root).rglob('*')):
            if not p.is_file() or p.name=='artifact-inventory.json':continue
            name=p.relative_to(root).as_posix();size=p.stat().st_size;files[name]={'bytes':size,'sha256':sha(p.read_bytes())}
            if name.startswith('experiment/checkpoints/'):checkpoints+=size
            else:evidence+=size
        value.update(files=files,evidence_bytes=evidence,checkpoint_bytes=checkpoints);dump(Path(root)/'artifact-inventory.json',value)
    def test_owned_actual28views67events(self):
        r=self.replay();self.assertTrue(r['evidence_valid'],r['errors']);self.assertEqual(r['generation_count'],24);self.assertEqual(r['public']['coverage']['observed_views'],4);self.assertEqual(r['metering']['events'],67);self.assertEqual(r['public']['micro_pass_at_2']['denominator'],2);self.assertFalse(r['scientific_goal_met'])
    def test_default_owned_fixture_reject(self):self.assertFalse(self.replay(allow=False)['evidence_valid'])
    def test_rehashed_required_omissions(self):
        for name in ('owner-clock.json','owner-request.json','release-source-inventory.json','inner-closure.json','outer-closure.json','physical-journal.jsonl','physical-journal.jsonl.anchor','experiment/A-checkpoint-proof.json','experiment/audit/sweep-0.json','experiment/public/views/000-0.json','experiment/public/predictions.json','experiment/public/pool.json','experiment/public/prediction-seal.json','public-scoring/evaluator-detail.json'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as td:
                root=Path(td)/'run';shutil.copytree(self.original,root);(root/name).unlink();self.reseal(root);r=self.replay(root);self.assertFalse(r['evidence_valid']);self.assertFalse(r['scientific_goal_met'])
    def test_torn_or_forged_journal(self):
        for mutation in ('truncate','mac','swap','refund','phase','hardcap'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as td:
                root=Path(td)/'run';shutil.copytree(self.original,root);path=root/'physical-journal.jsonl';rows=[parse_json(l) for l in path.read_bytes().splitlines()]
                if mutation=='truncate':path.write_bytes(path.read_bytes()[:-1])
                elif mutation=='mac':rows[1]['mac']='0'*64;path.write_bytes(b''.join(canonical(r)+b'\n' for r in rows))
                else:
                    if mutation=='swap':rows[1],rows[2]=rows[2],rows[1]
                    if mutation=='refund':next(r for r in rows if r['payload']['action']=='dispatch')['payload']['changes']['dispatched']=False
                    if mutation=='phase':next(r for r in rows if r['payload']['action']=='reserve')['payload']['event']['phase']='idle-padding'
                    if mutation=='hardcap':next(r for r in rows if r['payload']['action']=='reserve')['payload']['event']['hard_deadline']+=10000
                    path.write_bytes(b''.join(canonical(r)+b'\n' for r in rows))
                self.reseal(root);self.assertFalse(self.replay(root)['evidence_valid'])
    def test_actual_failure_is_diagnostic_not_success(self):
        from validation.validate_owned_outputs import validate_owned_outputs
        root=WORKSPACE/'portfolio63-rl-owned-proof-001';source=Root(root).json('release-source-inventory.json')['source_sha256']
        r=validate_owned_outputs(root,source_root=HERE/'lineage/native-proof-001-source',expected_source_sha256=source,allow_synthetic=True)
        self.assertEqual(r['status'],'STOPPED_INCOMPLETE',r['errors']);self.assertTrue(r['diagnostic_evidence_valid']);self.assertFalse(r['evidence_valid']);self.assertFalse(r['scientific_goal_met'])
    def test_original_clock_strict(self):
        clock=Root(self.original).json('owner-clock.json')
        for field,value in [('origin_monotonic',0.),('original_epoch',True),('offsets',{'inner':43200.}),('fixture',1)]:
            c=copy.deepcopy(clock);c[field]=value
            with self.subTest(field=field),self.assertRaises(EvidenceError):validate_clock(c)

class OriginalScorerRowsTests(unittest.TestCase):
    root=WORKSPACE/'portfolio63-next-20261012/validation-tests/public-fixture/run/owner'
    def fixture(self):
        pool=Root(self.root).json('public-prediction-seal/pool.json');report=Root(self.root).json('public-evaluation/evaluator-detail.json')['report'];return report,pool
    def test_controlled_full167_original_scorer_rows(self):
        report,pool=self.fixture();m=scorer_rows(report,pool,synthetic=True);self.assertEqual(m['tests'],167);self.assertEqual(m['tasks'],120);self.assertEqual(m['metrics']['pass_at_2']['numerator'],167)
    def test_score_row_adversaries(self):
        for mutate in (lambda r:r['rows'].pop(),lambda r:r['rows'].append(copy.deepcopy(r['rows'][0])),lambda r:r['rows'][0].update(pass2=1),lambda r:r['rows'][0].update(pool_size=2),lambda r:r['rows'][0].update(record_observed=False),lambda r:r['rows'][0].update(input_digest='sha256:'+'0'*64),lambda r:r['development_metrics']['metrics']['pass_at_2'].update(numerator=151),lambda r:r.update(source_digest='sha256:'+'0'*64)):
            report,pool=self.fixture();mutate(report)
            with self.assertRaises(EvidenceError):scorer_rows(report,pool,synthetic=True)

class ActualControlledScheduleTests(unittest.TestCase):
    def test_actual_cpu_adam_historical64_schedule(self):
        # Actual tensor/Adam operations with prescribed synthetic gradients, no model forward/backward.
        torch=torch_module();original_globals=list(torch.serialization.get_safe_globals())
        def restore_globals():
            torch.serialization.clear_safe_globals();torch.serialization.add_safe_globals(original_globals)
        self.addCleanup(restore_globals)
        state=safe_load_state(NATIVE/'experiment/checkpoints/A/state.pt')
        params={n:v.clone().requires_grad_() for n,v in state['adapters'].items()}
        optimizer=torch.optim.AdamW(list(params.values()),lr=2e-4,betas=(.9,.999),eps=1e-8,weight_decay=0.,foreach=False)
        scheduler=torch.optim.lr_scheduler.LambdaLR(optimizer,anchor_multiplier)
        for _ in range(64):
            for p in params.values():p.grad=torch.full_like(p,.01)
            optimizer.step();scheduler.step();optimizer.zero_grad(set_to_none=True)
        state.update(adapters={n:p.detach() for n,p in params.items()},optimizer=optimizer.state_dict(),optimizer_defaults=optimizer.defaults,scheduler=scheduler.state_dict(),schedule_recipe='historical-anchor-2e4-w4-c256-min01-v1',policy_version='anchor:controlled64',sft_exposed=['prescribed-gradient-fixture']*64,
                     counters={'anchor_updates':64,'rl_updates':0,'control_updates':0,'optimizer_steps':64,'scheduler_steps':64,'backward_calls':64,'sampler_cursor':64})
        result=validate_state(state,label='A',anchor_updates=64,expected_source_sha256=CORE,synthetic=True)
        self.assertEqual(result['counts']['optimizer_steps'],64);self.assertEqual(result['schedule_recipe'],'historical-anchor-2e4-w4-c256-min01-v1')

class RuntimeMetadataModeTests(unittest.TestCase):
    def prepare(self,td):
        from validation.checkpoint_metadata import FORMAT
        root=Path(td);shutil.copytree(NATIVE/'experiment/checkpoints/A',root/'checkpoints/A');shutil.copy(NATIVE/'experiment/A-checkpoint-proof.json',root/'A-checkpoint-proof.json')
        state=safe_load_state(root/'checkpoints/A/state.pt')
        summary={'format':FORMAT,'state_sha256':tree_sha(state),'adapter_sha256':adapter_sha(state['adapters']),'state_tree':tree_descriptor(state),'optimizer_step_values':{str(k):float(v['step']) for k,v in state['optimizer']['state'].items()},'optimizer_parameter_names':list(state['adapters']),'cleared_gradients':True}
        dump(root/'checkpoints/A/state-summary.json',summary)
        manifest=Root(root/'checkpoints/A').json('manifest.json');manifest['files']['state-summary.json']=Root(root/'checkpoints/A').file_sha('state-summary.json');dump(root/'checkpoints/A/manifest.json',manifest)
        proof=Root(root).json('A-checkpoint-proof.json');proof['save']=manifest;proof['manifest_file_sha256']=Root(root/'checkpoints/A').file_sha('manifest.json');proof['reload'].update(state_summary_verified=True,state_summary_file_sha256=manifest['files']['state-summary.json']);dump(root/'A-checkpoint-proof.json',proof)
        return root
    def test_metadata_mode_does_not_claim_independent_tensors(self):
        from validation.checkpoint_metadata import validate_checkpoint_metadata
        with tempfile.TemporaryDirectory() as td:
            root=self.prepare(td)
            for name in ('state.pt','adapter/adapter_model.safetensors','adapter/README.md'):(root/'checkpoints/A'/name).unlink()
            result=validate_checkpoint_metadata(Root(root),'A',anchor_updates=1,expected_core_source_sha256=CORE,synthetic=True)
            self.assertFalse(result['independent_checkpoint_tensor_verification']);self.assertEqual(len(result['unmaterialized_assets']),3)
    def test_full_mode_adds_actual_tensor_verification(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.prepare(td);result=validate_checkpoint(Root(root),'A',anchor_updates=1,expected_core_source_sha256=CORE,synthetic=True)
            self.assertTrue(result['independent_checkpoint_tensor_verification'])
    def test_compact_missing_or_corrupt_scalars_fail(self):
        from validation.checkpoint_metadata import replay_state_summary
        with tempfile.TemporaryDirectory() as td:
            root=self.prepare(td);original=Root(root/'checkpoints/A').json('state-summary.json')
            for mutate in (lambda s:s.pop('optimizer_parameter_names'),lambda s:s['optimizer_step_values'].update({'0':2.}),lambda s:s['state_tree']['scheduler'].update(last_epoch=0),lambda s:s['state_tree']['counters'].update(anchor_updates=True),lambda s:s.update(cleared_gradients=False),lambda s:s['state_tree']['optimizer']['state']['0']['exp_avg'].update(shape=[1,1])):
                value=copy.deepcopy(original);mutate(value);value['state_sha256']=digest(value['state_tree'])
                with self.assertRaises((EvidenceError,KeyError)):replay_state_summary(value,label='A',anchor_updates=1,expected_core_source_sha256=CORE,synthetic=True)
