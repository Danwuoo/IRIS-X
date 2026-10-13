"""Acyclic external release content controls. Synthetic bytes confer no authority."""
import copy,tempfile,unittest,zipfile
from pathlib import Path
from validation.safe_io import Root,canonical,digest,sha,EvidenceError
from validation.release_checks import release_binding,source_policy
from validation.validate_owned_outputs import frozen_plan

HERE=Path(__file__).resolve().parents[2]
def put(root,name,obj):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(canonical(obj)+b'\n');return sha(p.read_bytes())

class ReleaseContentTests(unittest.TestCase):
    def test_actual_release_launch_bytes_and_rehashed_attacks(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'out';out.mkdir();ext=Path(td)/'ext';ext.mkdir();src=Path(td)/'src';src.mkdir()
            policy={'phase_constants':{}};ph=put(src,'independent-protocol-review/PROVISIONAL-DEFAULTS.json',policy)
            files={'a.py':sha(b'x=1\n')};source=digest(sorted(files.items()))
            with zipfile.ZipFile(ext/'source.zip','w') as z:z.writestr('a.py',b'x=1\n')
            owner={'format':'owned-rl-original-owner-request-v1','scope':'production-rl-abc','role':'rl-abc','original_epoch':100.,'request_id':'fresh1','owner_id':'owner1','instruction':'Run fixed experiment'}
            oh=put(ext,'original.json',owner)
            mh=put(ext,'material_review.json',{'format':'owned-rl-reviewed-material-v1'})
            eh=put(ext,'environment.json',{'format':'owned-rl-reviewed-environment-v1'})
            self.assertEqual(put(ext,'phase_policy.json',policy),ph)
            prh=put(ext,'owner_protocol.json',{'format':'owned-rl-reviewed-owner-protocol-v1','scope':'production-rl-abc','role':'rl-abc'})
            archive=Root(ext).file_sha('source.zip')
            op={'format':'owned-rl-reviewed-operator-v1','scope':'production-rl-abc','role':'rl-abc','raw_source_sha256':source,'source_archive_sha256':archive,'material_review_sha256':mh,'original_request_sha256':oh,'original_epoch':100.,'original_request_id':'fresh1','owner_id':'owner1'}
            oph=put(ext,'operator.json',op);nbh=put(ext,'notebook.json',{'metadata':{'owned_rl_release':{'format':'owned-rl-outer-notebook-v1','operator_sha256':oph}}})
            refs={n:{'path':p,'file_sha256':h} for n,p,h in [('original_request','original.json',oh),('operator','operator.json',oph),('outer_notebook','notebook.json',nbh),('source_archive','source.zip',archive)]}
            boot={**refs,'material_review':{'file_sha256':mh},'scope':'production-rl-abc','role':'rl-abc','original_epoch':100.,'original_request_id':'fresh1','owner_id':'owner1'}
            request={'config':{'fixture':False,'environment_path':'/original/env.json','policy_path':'/original/policy.json'},'bootstrap':boot}
            clock={'original_epoch':100.};rh=put(out,'owner-request.json',request);ch=put(out,'owner-clock.json',clock)
            release={'format':'owned-rl-independent-release-v1','source_sha256':source,'material_review_sha256':mh,'environment_sha256':eh,'phase_policy_sha256':ph,'owner_protocol_sha256':prh}
            rlh=put(ext,'release.json',release)
            launch={'format':'owned-rl-independent-launch-v1','release_sha256':rlh,'files':refs,'owner_request_sha256':rh,'owner_clock_sha256':ch,'artifact_inventory_sha256':'a'*64,'review_inputs':{'environment':{'path':'/original/env.json','file_sha256':eh},'phase_policy':{'path':'/original/policy.json','file_sha256':ph}},'checkpoint_archive_observation_sha256':None}
            lh=put(ext,'launch.json',launch);env={'request':request,'clock':clock,'source':{'files':files}}
            def check(lh=lh):return release_binding(Root(out),src,env,release_root=ext,release_sha256=rlh,launch_sha256=lh,source_sha256=source,inventory_sha256='a'*64)
            self.assertEqual(check()['independent_release_sha256'],rlh)
            for key,val in [('owner_request_sha256','f'*64),('owner_clock_sha256','e'*64),('artifact_inventory_sha256','d'*64)]:
                bad=copy.deepcopy(launch);bad[key]=val;bh=put(ext,'launch.json',bad)
                with self.subTest(key=key),self.assertRaises(EvidenceError):check(bh)
            put(ext,'launch.json',launch);env['clock']={'original_epoch':101.}
            with self.assertRaises(EvidenceError):check()
    def test_exact_production_shape_and_source_policy(self):
        plan=Root(HERE.parent/'portfolio63-rl-owned-proof-002/experiment').json('frozen-plan.json')
        plan['shape'].update(anchor_updates=64,parents=32,group_size=8,dev_cases=16,holdout_cases=32,max_sweeps=4,max_control_updates=8192)
        plan['inference']['max_new_tokens']=1024
        plan['numeric_gate'].update(maximum_batch_replay_backward_seconds=600.,fixture_only=False,maximum_peak_bytes=72*1024**3,maximum_reserved_bytes=80*1024**3)
        frozen_plan(plan,False)
        bad=copy.deepcopy(plan);bad['inference']['max_new_tokens']=1
        with self.assertRaises(EvidenceError):frozen_plan(bad,False)
        bad=copy.deepcopy(plan);bad['anchor_schedule']['warmup']=0
        with self.assertRaises(EvidenceError):frozen_plan(bad,False)
        policy=Root(HERE).json('independent-protocol-review/PROVISIONAL-DEFAULTS.json');c=policy['phase_constants'];ph=Root(HERE).file_sha('independent-protocol-review/PROVISIONAL-DEFAULTS.json')
        plan['forecast']={'evidence_sha256':ph,'evidence_kind':'v25-source-bound-pending-review','setup_seconds':float(c['common_setup_calibration_anchor_forecast_seconds']),'sweep_seconds':float(32*8*45+30),'control_step_seconds':float(c['control_step_forecast_seconds']),'persist_reload_seconds':float(c['arm_finalization_forecast_seconds']),'evaluation_seconds':float(c['ABC_reserve_seconds']),'public_seconds':float(c['selected_PUBLIC_reserve_seconds']),'failure_margin_seconds':float(c['future_reload_persistence_reserve_seconds']),'closure_seconds':float(c['cleanup_reserve_seconds'])}
        source_policy(plan,policy,ph)
        plan['forecast']['public_seconds']=1.
        with self.assertRaises(EvidenceError):source_policy(plan,policy,ph)
    def test_original_targetfree_public_identity(self):
        from validation.public_checks import SOLVER_MANIFEST_SHA256,SOLVER_CHALLENGES_FILE_SHA256,SOLVER_CHALLENGES_CANONICAL_SHA256
        root=Root(HERE.parent/'portfolio63-next-20261012/materials/public120-solver/solver')
        self.assertEqual(root.file_sha('manifest.json'),SOLVER_MANIFEST_SHA256)
        self.assertEqual(root.file_sha('public-challenges.json'),SOLVER_CHALLENGES_FILE_SHA256)
        self.assertEqual(digest(root.json('public-challenges.json')),SOLVER_CHALLENGES_CANONICAL_SHA256)
