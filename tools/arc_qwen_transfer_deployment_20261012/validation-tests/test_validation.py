"""Explicitly synthetic stdlib unit fixtures. Never scientific evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'validation'))
import validate_transfer_outputs as v
import selector_replay

class StaticFixtures(unittest.TestCase):
    synthetic=True
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def archive(self,files=None,mutate=None):
        files=files or {'request.json':b'{"synthetic":true}\n'}
        inv={'format':'irisx/qwen14b-probe-archive-v1','files':{k:{'bytes':len(raw),'sha256':v.raw_sha(raw)} for k,raw in files.items()},'owned_process_closed':True,'public_score':None}
        if mutate:mutate(inv)
        path=self.root/'evidence.zip'
        with zipfile.ZipFile(path,'w') as z:
            for k,raw in files.items():z.writestr(k,raw)
            z.writestr('archive-manifest.json',v.canonical(inv))
        return path
    def test_exact_archive(self):
        a=v.ClosedArchive(self.archive());self.assertEqual(a.json('request.json'),{'synthetic':True});a.close()
    def test_archive_inventory_sha(self):
        with self.assertRaises(v.ValidationError):v.ClosedArchive(self.archive(mutate=lambda i:i['files']['request.json'].update(sha256='0'*64)))
    def test_archive_inventory_length(self):
        with self.assertRaises(v.ValidationError):v.ClosedArchive(self.archive(mutate=lambda i:i['files']['request.json'].update(bytes=1)))
    def test_archive_extra_file(self):
        p=self.archive()
        with zipfile.ZipFile(p,'a') as z:z.writestr('unlisted.json','{}')
        with self.assertRaises(v.ValidationError):v.ClosedArchive(p)
    def test_archive_duplicate(self):
        p=self.archive()
        with zipfile.ZipFile(p,'a') as z:z.writestr('request.json','{}')
        with self.assertRaises(v.ValidationError):v.ClosedArchive(p)
    def test_archive_path_traversal(self):
        with self.assertRaises(v.ValidationError):v.ClosedArchive(self.archive({'../target':b'x'}))
    def test_archive_encrypted_flag(self):
        p=self.archive();raw=bytearray(p.read_bytes());start=raw.index(b'PK\x01\x02');raw[start+8]|=1;p.write_bytes(raw)
        with self.assertRaises(v.ValidationError):v.ClosedArchive(p)
    def test_archive_crc(self):
        p=self.archive();raw=bytearray(p.read_bytes());start=raw.index(b'{"synthetic"');raw[start+3]^=1;p.write_bytes(raw)
        with self.assertRaises(v.ValidationError):v.ClosedArchive(p)
    def test_archive_symlink(self):
        p=self.archive();link=self.root/'link.zip';link.symlink_to(p)
        with self.assertRaises(v.ValidationError):v.ClosedArchive(link)
    def test_duplicate_json(self):
        with self.assertRaises(v.ValidationError):v.strict_json(b'{"a":1,"a":2}')
    def test_nonfinite_json(self):
        for x in ('NaN','Infinity','-Infinity'):
            with self.subTest(x=x),self.assertRaises(v.ValidationError):v.strict_json(('{"x":'+x+'}').encode())
    def test_foreign_path(self):
        with self.assertRaises(v.ValidationError):v.local_reference('/other/request.json','/owner')
    def test_bool_not_integer(self):self.assertFalse(v.integer(True));self.assertFalse(v.number(True))
    def clock(self):
        r={'config':{'started_epoch':1000,'maximum_seconds':43200},'hard_deadline':50000,'work_deadline':49400}
        t={'status':'TRANSFER_COMPLETE','predispatch_started_epoch':1000,'maximum_seconds':43200,'global_deadline_epoch':44200,'effective_deadline_epoch':43000,'execution_cutoff_seconds':42000,'provider_runtime_seconds':42300,'completed_epoch':42000,'within_probe_deadline':True,'within_absolute_deadline':True,'elapsed_seconds':41000,'work_reserve_seconds':600,'owner_stop_reserve_seconds':540}
        return r,t
    def test_clock_order(self):r,t=self.clock();self.assertEqual(v.validate_clocks(r,t,synthetic=False)['deadline_epoch'],43000)
    def test_clock_reset(self):
        r,t=self.clock();t['predispatch_started_epoch']+=1
        with self.assertRaises(v.ValidationError):v.validate_clocks(r,t,synthetic=False)
    def test_clock_late_but_provider_incomplete(self):
        r,t=self.clock();t['completed_epoch']=43001
        with self.assertRaises(v.ValidationError):v.validate_clocks(r,t,synthetic=False)
    def test_clock_provider_wrong(self):
        r,t=self.clock();t['provider_runtime_seconds']=43200
        with self.assertRaises(v.ValidationError):v.validate_clocks(r,t,synthetic=False)
    def test_clock_program_unchanged(self):
        r,t=self.clock();r['config']['maximum_seconds']=42000
        with self.assertRaises(v.ValidationError):v.validate_clocks(r,t,synthetic=False)
    def proof(self):
        root={'pid':101,'birth':11,'session':101,'state':'Z'}
        return {'format':'irisx/owned-process-closure-v1','root_identity':root,'scope':'dedicated-subreaper-tree','ownership_complete':True,'closed':True,'owned_identities':[root],'remaining':[],'returncode':0,'worker_returncode':0,'forced':False,'reaped_identities':[root],'errors':[]}
    def test_closure_valid(self):v.closure(self.proof(),clean=True)
    def test_closure_unowned(self):
        p=self.proof();p['root_identity']['birth']=12;p['owned_identities']=[]
        with self.assertRaises(v.ValidationError):v.closure(p,clean=True)
    def test_closure_remaining(self):
        p=self.proof();p['remaining']=[p['root_identity']]
        with self.assertRaises(v.ValidationError):v.closure(p,clean=True)
    def test_closure_forced(self):
        p=self.proof();p['forced']=True
        with self.assertRaises(v.ValidationError):v.closure(p,clean=True)
    def ledger(self,open_work=False):
        rows=[{'event':'opened','caps':v.CAPS},{'event':'reserved','event_id':'event1','amounts':{'input_tokens':100}}]
        if not open_work:rows.append({'event':'complete','event_id':'event1','amounts':{'input_tokens':90}})
        previous='0'*64
        for i,r in enumerate(rows):r.update(index=i,previous=previous);r['sha256']=v.digest(r);previous=r['sha256']
        return b''.join(v.canonical(r) for r in rows)
    def test_physical_ledger(self):self.assertEqual(v.ledger_replay(self.ledger(),require_closed=True)['used']['input_tokens'],90)
    def test_pending_physical_work(self):
        with self.assertRaises(v.ValidationError):v.ledger_replay(self.ledger(True),require_closed=True)
    def test_physical_chain_tamper(self):
        with self.assertRaises(v.ValidationError):v.ledger_replay(self.ledger().replace(b'90',b'80'),require_closed=True)
    def test_native_clock_late(self):
        with self.assertRaises(v.ValidationError):v.bounds_recursive({'started_monotonic':1,'completed_monotonic':5,'deadline_monotonic':5,'valid':True,'late':True})
    def test_native_clock_flag(self):
        with self.assertRaises(v.ValidationError):v.bounds_recursive({'started_monotonic':1,'completed_monotonic':4,'deadline_monotonic':5,'valid':True,'late':True})
    def test_native_model_old_profile(self):
        with self.assertRaises(v.ValidationError):v.validate_model_identity({'profile_id':'qwen3-14b-native-bf16-r8-c2048-probe-v1'},False)
    def test_source_protocol_static(self):
        root=ROOT/'worktree';mapping=v.source_identity(root)
        s=v.SourceSnapshot(root,mapping);self.assertEqual(s.protocol['context_limit'],4096);s.close()
    def test_source_exact_sha(self):
        mapping={v.PACKAGE+'protocol.py':'0'*64}
        with self.assertRaises(v.ValidationError):v.SourceSnapshot(ROOT/'worktree',mapping)
    def test_selector_source_hash(self):
        root=ROOT/'worktree';mapping=v.source_identity(root);mapping[v.PACKAGE+'transfer_selector.py']='0'*64
        with self.assertRaises(v.ValidationError):v.SourceSnapshot(root,mapping)

if __name__=='__main__':unittest.main()
