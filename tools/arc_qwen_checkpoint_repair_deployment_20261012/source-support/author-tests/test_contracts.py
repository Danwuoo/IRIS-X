from copy import deepcopy
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'worktree'))
from tools.arc_qwen_transfer_20261012 import checkpoint_policy as p
from tools.arc_qwen_portfolio_20261012.checkpoints import _check_update,CheckpointLimits
class Contracts(unittest.TestCase):
    def test_stored_transfer_schedule_required(self):
        b={'model':{'native_identity':{'profile_id':'qwen3-14b-native-bf16-r8-c4096-transfer-v1'}}}
        with self.assertRaisesRegex(ValueError,'stored TransferTrainer'):_check_update(0,b)
    def test_closed_global(self):
        b={'branch_id':'global_grid','checkpoint_schedule':p.contract(p.GLOBAL,'global_grid'),'config':{'tiny_cpu':True}}
        for update in (0,64,256):_check_update(update,b)
        for update in (None,True,64.0,1,2,8,16,65,257,-1,'64'):
            with self.assertRaises(ValueError):_check_update(update,b)
    def test_explicit_fixture(self):
        for c in ({'tiny_cpu':True},{'tiny_cpu':True,'test_checkpoint_updates':[1,2]}):
            with self.assertRaises(ValueError):p.for_run(c)
        c={'tiny_cpu':True,'test_fixture_dataset':True,'test_checkpoint_updates':[1,2]}
        self.assertEqual(p.for_run(c),p.FIXTURE)
        self.assertEqual(p.for_run({**c,'test_checkpoint_updates':[64,256]}),p.GLOBAL)
        self.assertEqual(p.for_run({}),p.GLOBAL)
        for updates in ([True,2],[1.,2],[64.,256],[64,256.],(64,256),[8,16]):
            with self.assertRaises(ValueError):p.for_run({**c,'test_checkpoint_updates':updates})
    def test_canonical_descriptor_types(self):
        original=p.contract(p.GLOBAL,'global_grid')
        for key,value in [('allowed_updates',[0.,64,256]),('fixture_only',0),('scope','task'),('protocol_sha256','0'*64)]:
            forged={**deepcopy(original),key:value}
            with self.assertRaises(ValueError):p.validate_contract(forged,'global_grid',64)
    def test_scope_branches(self):
        for name in (p.GLOBAL,p.FIXTURE):
            with self.assertRaises(ValueError):p.contract(name,'representative_ttt')
        with self.assertRaises(ValueError):p.contract(p.TTT,'global_grid')
        b={'branch_id':'representative_ttt','checkpoint_schedule':p.contract(p.TTT,'representative_ttt'),'config':{'tiny_cpu':False}}
        for n in (0,8,16):_check_update(n,b)
        for n in (1,2,64,256):
            with self.assertRaises(ValueError):_check_update(n,b)
    def test_legacy_not_broadened(self):
        for n in range(17):_check_update(n,{})
        for n in (17,64,256,True,None):
            with self.assertRaises(ValueError):_check_update(n,{})
    def test_existing_capacity_unchanged(self):
        c=CheckpointLimits();self.assertEqual((c.branches,c.versions_per_branch,c.shard_bytes,c.store_bytes,c.checkpoint_bytes),(2,3,32*1024**2,2*1024**3,768*1024**2))
    def test_frozen_unchanged_science_and_clocks(self):
        old=ROOT.parent/'portfolio63-transfer-repair-20261012/final-source-freeze-002'
        for name in ('protocol.py','child.py','runner.py','science_profiles.py','data.py','call_policy.py','timing_refresh.py','decoder.py'):
            self.assertEqual((old/'tools/arc_qwen_transfer_20261012'/name).read_bytes(),(ROOT/'worktree/tools/arc_qwen_transfer_20261012'/name).read_bytes(),name)
if __name__=='__main__':unittest.main(verbosity=2)
