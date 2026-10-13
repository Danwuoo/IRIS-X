"""Independent checkpoint-policy boundary tests; no model or external service."""
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get('REVIEW_SOURCE', str(HERE.parent/'worktree'))).resolve()
BASELINE = HERE.parent.parent/'portfolio63-transfer-repair-20261012/final-source-freeze-002'
sys.path[:0] = [str(SOURCE), str(SOURCE/'src')]
from tools.arc_qwen_transfer_20261012 import checkpoint_policy as policy
from tools.arc_qwen_transfer_20261012.protocol import PROTOCOL, digest, validate_config
from tools.arc_qwen_portfolio_20261012 import checkpoints as cp


def binding(schedule, branch=None, tiny=True):
    branch = branch or ('representative_ttt' if schedule == policy.TTT else 'global_grid')
    return {'branch_id':branch, 'config':{'tiny_cpu':tiny}, 'checkpoint_schedule':policy.contract(schedule, branch)}


class CheckpointContract(unittest.TestCase):
    def test_closed_global_values_do_not_depend_on_tiny_dimensions(self):
        for tiny in (True, False):
            b = binding(policy.GLOBAL, tiny=tiny)
            for update in (0,64,256):
                cp._check_update(update, b, SimpleNamespace(config={'tiny_cpu':tiny},_task_id=None))
            for update in (None,False,True,0.0,64.0,'64',-1,1,2,8,16,63,65,255,257,1024):
                with self.subTest(tiny=tiny,update=update), self.assertRaises(ValueError):
                    cp._check_update(update,b)

    def test_stored_transfer_identity_cannot_fall_back_to_legacy(self):
        b={'branch_id':'global_grid','model':{'native_identity':{'profile_id':'qwen3-14b-native-bf16-r8-c4096-transfer-v1'}},'config':{'tiny_cpu':True}}
        for update in (0,1,8,16):
            with self.subTest(update=update),self.assertRaises(ValueError):cp._check_update(update,b)

    def test_fixture_requires_tiny_and_cannot_expand(self):
        b=binding(policy.FIXTURE)
        for update in (0,1,2):cp._check_update(update,b)
        for update in (8,16,64,256,None,True):
            with self.subTest(update=update),self.assertRaises(ValueError):cp._check_update(update,b)
        with self.assertRaises(ValueError):cp._check_update(1,binding(policy.FIXTURE,tiny=False))

    def test_ttt_scope_and_values(self):
        b=binding(policy.TTT)
        for update in (0,8,16):cp._check_update(update,b,SimpleNamespace(_task_id='authored'))
        for update in (None,True,1,2,64,256,-1):
            with self.subTest(update=update),self.assertRaises(ValueError):cp._check_update(update,b)
        with self.assertRaises(ValueError):cp._check_update(16,b,SimpleNamespace(_task_id=None))
        with self.assertRaises(ValueError):cp._check_update(64,binding(policy.GLOBAL),SimpleNamespace(_task_id='task'))

    def test_source_bound_metadata_mutations_reject(self):
        original=binding(policy.GLOBAL)
        mutations=[('allowed_updates',[0,64,256,257]),('scope','task'),('fixture_only',True),
                   ('branch_id','representative_ttt'),('schedule_id','arbitrary'),('protocol_sha256','0'*64),
                   ('source_sha256',{}),('format','other'),('allowed_updates',[0.0,64.0,256.0]),('fixture_only',0)]
        for field,value in mutations:
            b=deepcopy(original);b['checkpoint_schedule'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):cp._check_update(64,b)
        b=deepcopy(original);b['checkpoint_schedule']['extra']=1
        with self.assertRaises(ValueError):cp._check_update(64,b)
        b=deepcopy(original);b['branch_id']='another_branch'
        with self.assertRaises(ValueError):cp._check_update(64,b)

    def test_run_schedule_explicit_fixture_only(self):
        self.assertEqual(policy.for_run({}),policy.GLOBAL)
        self.assertEqual(policy.for_run({'tiny_cpu':True,'test_fixture_dataset':True}),policy.FIXTURE)
        self.assertEqual(policy.for_run({'tiny_cpu':True,'test_fixture_dataset':True,'test_checkpoint_updates':[64,256]}),policy.GLOBAL)
        for c in ({'test_checkpoint_updates':[1,2]}, {'tiny_cpu':True}, {'test_checkpoint_updates':[16,256]},
                  {'tiny_cpu':True,'test_fixture_dataset':True,'test_checkpoint_updates':[64,257]},
                  {'tiny_cpu':True,'test_fixture_dataset':True,'test_checkpoint_updates':[True,2]},
                  {'test_checkpoint_updates':[64.0,256.0]}):
            with self.subTest(config=c),self.assertRaises(ValueError):policy.for_run(c)

    def test_branch_schedule_matrix(self):
        for schedule,branch in ((policy.GLOBAL,'representative_ttt'),(policy.TTT,'global_grid'),
                               (policy.FIXTURE,'arbitrary'),('caller-controlled','global_grid')):
            with self.subTest(schedule=schedule,branch=branch),self.assertRaises(ValueError):policy.contract(schedule,branch)

    def test_legacy_bounds_preserved(self):
        b={'branch_id':'legacy'}
        for tiny in (True,False):
            trainer=SimpleNamespace(config={'tiny_cpu':tiny})
            for update in (0,8,16):cp._check_update(update,b,trainer)
            for update in (-1,17,64,256,None,False,16.0):
                with self.subTest(tiny=tiny,update=update),self.assertRaises(ValueError):cp._check_update(update,b,trainer)
            for update in (1,2,7,9,15):
                if tiny:cp._check_update(update,b,trainer)
                else:
                    with self.subTest(update=update),self.assertRaises(ValueError):cp._check_update(update,b,trainer)

    def test_inspect_rejects_bad_update_and_contract(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root=Path(name)
            b=binding(policy.GLOBAL)
            m={'format':cp.FORMAT,'binding':b,'binding_sha256':cp.digest(b),'update':64,'files':{},'payload_file_bytes':0}
            path=root/'manifest.json'
            path.write_text(json.dumps(m));self.assertEqual(cp.inspect_checkpoint(root)['update'],64)
            for update in (None,False,1,16,257):
                v=deepcopy(m);v['update']=update;path.write_text(json.dumps(v))
                with self.subTest(update=update),self.assertRaises(ValueError):cp.inspect_checkpoint(root)
            v=deepcopy(m);v['binding']['checkpoint_schedule']['allowed_updates'].append(257)
            v['binding_sha256']=cp.digest(v['binding']);path.write_text(json.dumps(v))
            with self.assertRaises(ValueError):cp.inspect_checkpoint(root)

    def test_unchanged_hard_byte_limits(self):
        limits=cp.CheckpointLimits()
        self.assertEqual(limits.__dict__,{'shard_bytes':32*1024**2,'checkpoint_bytes':768*1024**2,
            'store_bytes':2*1024**3,'json_bytes':8*1024**2,'files':128,'tensors':10000,
            'branches':2,'versions_per_branch':3,'reserve_bytes':4*1024**3})
        for args in ({'shard_bytes':32*1024**2+1},{'store_bytes':2*1024**3+1},{'json_bytes':32*1024**2+1}):
            with self.subTest(args=args),self.assertRaises(ValueError):cp.CheckpointLimits(**args)

    def test_protocol_science_and_call_budgets_byte_identical(self):
        paths=['tools/arc_qwen_transfer_20261012/'+n for n in ['protocol.py','data.py','science_profiles.py','call_policy.py','model_profile.py','decoder.py','timing_refresh.py','transfer_selector.py','demo_selector.py','runner.py']]
        for name in paths:
            with self.subTest(path=name):self.assertEqual((SOURCE/name).read_bytes(),(BASELINE/name).read_bytes())
        self.assertEqual((PROTOCOL['train_parents'],PROTOCOL['dev_parents'],PROTOCOL['holdout_parents']),(32,16,32))
        self.assertEqual(PROTOCOL['checkpoint_updates'],[64,256]);self.assertEqual(PROTOCOL['ttt_updates'],[0,8,16])
        self.assertEqual((PROTOCOL['maximum_session_seconds'],PROTOCOL['provider_runtime_seconds'],PROTOCOL['execution_cutoff_seconds']),(43200,42300,42000))

    def test_every_transfer_checkpoint_call_has_explicit_schedule(self):
        tree=ast.parse((SOURCE/'tools/arc_qwen_transfer_20261012/experiment.py').read_text())
        seen=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('save_branch_checkpoint','load_branch_checkpoint','load_inference_adapter'):
                seen.append((n.func.id,n.lineno))
                self.assertIn('checkpoint_schedule',[kw.arg for kw in n.keywords],str(seen[-1]))
        self.assertGreaterEqual(len(seen),5)

if __name__=='__main__':unittest.main(verbosity=2)
