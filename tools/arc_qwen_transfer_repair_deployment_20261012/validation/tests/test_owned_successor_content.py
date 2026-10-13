"""Exact owned tiny successor bytes and explicit synthetic delete/rehash fixtures.

Does not execute a model. Original owner outputs/source are never modified.
"""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
VALIDATION=Path(__file__).resolve().parents[1];ROOT=VALIDATION.parent
sys.path.insert(0,str(VALIDATION))
import validate_transfer_outputs as v
OWNER=ROOT/'cpu-owner-001';SOURCE=ROOT/'cpu-source-freeze-001'

class OwnedSuccessor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (OWNER/'terminal-receipt.json').is_file():raise unittest.SkipTest('actual successor tiny owner has not reached terminal yet')
        cls.mapping=v.json_file(ROOT/'author-evidence/cpu-source-freeze-001.json')['source_identity']
        with zipfile.ZipFile(OWNER/'evidence.zip') as z:cls.members={n:z.read(n) for n in z.namelist() if n!='archive-manifest.json'}
        cls.terminal=v.json_file(OWNER/'terminal-receipt.json')
        if v.strict_json(cls.members['request.json'])['config'].get('tiny_cpu') is not True:raise AssertionError('test seed must remain genuinely tiny')
    def validate(self,root=OWNER,allow_synthetic=True):return v.validate_content(root,self.mapping,source_root=SOURCE,allow_synthetic=allow_synthetic)
    def rejected(self,mutate):
        with tempfile.TemporaryDirectory(dir=VALIDATION/'tests') as temp:
            root=Path(temp);members=deepcopy(self.members);terminal=deepcopy(self.terminal);mutate(members,terminal)
            self.assertIs(v.strict_json(members['request.json'])['config']['tiny_cpu'],True)
            inventory={'format':'irisx/qwen14b-probe-archive-v1','files':{n:{'bytes':len(raw),'sha256':v.raw_sha(raw)} for n,raw in sorted(members.items())},'owned_process_closed':True,'public_score':None}
            with zipfile.ZipFile(root/'evidence.zip','x',zipfile.ZIP_DEFLATED) as z:
                for n,raw in members.items():z.writestr(n,raw)
                z.writestr('archive-manifest.json',v.canonical(inventory))
            terminal['archive'].update(sha256=v.file_sha(root/'evidence.zip'),bytes=(root/'evidence.zip').stat().st_size,files=len(members)+1)
            (root/'terminal-receipt.json').write_bytes(v.canonical(terminal))
            (root/'SYNTHETIC-FIXTURE.json').write_bytes(v.canonical({'synthetic':True,'production_evidence':False,'source_owner_archive_sha256':v.file_sha(OWNER/'evidence.zip')}))
            with self.assertRaises(ValueError):self.validate(root)
    def test_actual_tiny_successor(self):
        r=self.validate();self.assertTrue(r['valid']);self.assertTrue(r['synthetic']);self.assertFalse(r['goal_met']);self.assertFalse(r['science_complete']);self.assertFalse(r['operational_success']);self.assertGreater(r['call_budget']['generation_receipts'],224)
    def test_production_content_rejects_tiny(self):
        with self.assertRaisesRegex(ValueError,'synthetic'):self.validate(allow_synthetic=False)
    def test_deleted_rehashed_refresh(self):self.rejected(lambda m,t:m.pop('experiment/public-cost-refresh.json'))
    def test_deleted_rehashed_boundary(self):self.rejected(lambda m,t:m.pop('experiment/main-timing-boundaries.json'))
    def test_deleted_rehashed_main_sidecar(self):self.rejected(lambda m,t:m.pop('experiment/dev/base/000-0.timing.json'))
    def test_deleted_rehashed_active_marker(self):self.rejected(lambda m,t:m.pop('active-call.json'))
    def test_rehashed_forecast_policy(self):
        def edit(m,t):
            r=v.strict_json(m['feasibility.json']);r['generation_call_policy']['generation_normal_soft_seconds']=115.;m['feasibility.json']=v.canonical(r)
        self.rejected(edit)
    def test_rehashed_refresh_baseline(self):
        def edit(m,t):
            r=v.strict_json(m['experiment/public-cost-refresh.json']);r['selected_estimate']['forecast_seconds']=0.;m['experiment/public-cost-refresh.json']=v.canonical(r)
        self.rejected(edit)
    def test_gold_never_parsed(self):
        old=v.ClosedArchive.json
        def checked(obj,name):
            if 'target-escrow' in name:raise AssertionError('target escrow parsed')
            return old(obj,name)
        v.ClosedArchive.json=checked
        try:self.assertTrue(self.validate()['valid'])
        finally:v.ClosedArchive.json=old

if __name__=='__main__':unittest.main()
