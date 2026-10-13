"""Bounded archived-byte replay; no subprocess, model, provider or held-target reads.

Historical v29 runs the successor helper through an explicit identity-only adapter.
The complete-export case is an actual historical tiny fixture, never production.
"""
from pathlib import Path
import copy,hashlib,json,shutil,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent
PRIOR=BASE/'portfolio63-rl-bootstrap-repair-20261013'
DOWNLOAD=PRIOR/'publication/run-evidence/downloads'
NAME='irisx-qwen14b-rlvr-20261012-run002'
HELPER=ROOT/'assembly/verify_parent_wrappers.py'
REPLACEMENTS=(('run004','run002'),('source004','source002'),('environment004','environment002'))
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def adapted():
    raw=HELPER.read_bytes();text=raw.decode()
    for old,new in REPLACEMENTS:
        if old not in text:raise ValueError('missing exact historical identity adaptation')
        text=text.replace(old,new)
    n={'__name__':'archived_v29_identity_only_adapter'};exec(compile(text,str(HELPER)+'[identity-only-v29]','exec'),n)
    return n,text.encode()
def arguments():
    return dict(expected_jit={x:(PRIOR/'publication/state'/x).read_bytes() for x in ('active-finalized.ipynb','original-request.json','operator.json','parent-private-scorer.json')},
        notebook_release=json.loads((PRIOR/'release-candidate-001/notebook-release.json').read_bytes()),
        reviewed_environment=json.loads((PRIOR/'release-candidate-001/consumer-release/environment.json').read_bytes()),
        runtime_outer_raw=(DOWNLOAD/NAME/'outer-closure.json').read_bytes(),
        runtime_owned_result_raw=(DOWNLOAD/NAME/'owned-result.json').read_bytes(),
        runtime_terminal_raw=(DOWNLOAD/(NAME+'.evidence.zip.terminal.json')).read_bytes())
class ActualArchivedTerminal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api,cls.adapter=adapted()
    def setUp(self):self.kw=arguments();self.root=DOWNLOAD/(NAME+'-launcher')
    def run_actual(self):return self.api['verify_wrappers'](self.root,**self.kw)
    def reject_terminal(self,change):
        t=json.loads(self.kw['runtime_terminal_raw']);change(t);self.kw['runtime_terminal_raw']=enc(t)
        with self.assertRaises((ValueError,KeyError,TypeError)):self.run_actual()
    def test_actual_v29_wrapper_termination_not_model_closure(self):
        result=self.run_actual();self.assertTrue(result['closure_valid']);self.assertFalse(result['operational'])
        self.assertEqual(result['terminal_status'],'diagnostic');self.assertFalse(result['model_closure_verified_by_this_helper'])
        outer=json.loads(self.kw['runtime_outer_raw']);self.assertFalse(outer['safe_closure']);self.assertIsNone(outer['inner_closure'])
        self.assertTrue(all(x['returncode']==1 for x in result['stages']))
    def test_unadapted_successor_rejects_historical_paths(self):
        n={'__name__':'exact_successor'};exec(compile(HELPER.read_bytes(),str(HELPER),'exec'),n)
        with self.assertRaises(ValueError):n['verify_wrappers'](self.root,**self.kw)
    def test_missing_authorization(self):self.reject_terminal(lambda t:t.pop('authorization'))
    def test_forged_flat_authority(self):
        def f(t):t.update(original_clock=t['authorization']['original_clock'],source_sha256=t['authorization']['source_sha256'])
        self.reject_terminal(f)
    def test_wrong_kind(self):self.reject_terminal(lambda t:t['authorization'].update(kind='live-owned-model-closure'))
    def test_false_complete_relabel(self):self.reject_terminal(lambda t:t.update(status='complete',model_closed=True))
    def test_interrupted_export_rejected(self):self.reject_terminal(lambda t:t.update(status='interrupted',archive_complete=False))
    def test_wrong_source(self):self.reject_terminal(lambda t:t['authorization'].update(source_sha256='0'*64))
    def test_wrong_request_hash(self):self.reject_terminal(lambda t:t['authorization']['owner_request_ref'].update(file_sha256='0'*64))
    def test_wrong_request_path(self):self.reject_terminal(lambda t:t['authorization']['owner_request_ref'].update(path='/different/owner-request.json'))
    def test_wrong_outer_hash(self):self.reject_terminal(lambda t:t['authorization']['outer_closure_ref'].update(file_sha256='0'*64))
    def test_wrong_output(self):self.reject_terminal(lambda t:t['authorization'].update(output_root='/different'))
    def test_wrong_worker(self):self.reject_terminal(lambda t:t['authorization'].update(worker_pid=99999))
    def test_unexited_worker(self):self.reject_terminal(lambda t:t['authorization'].update(worker_exited=False))
    def test_live_worker_session(self):self.reject_terminal(lambda t:t['authorization'].update(worker_session_empty=False))
    def test_wrong_epoch(self):self.reject_terminal(lambda t:t['authorization']['original_clock'].update(original_epoch=1))
    def test_shortened_deadline(self):self.reject_terminal(lambda t:t['authorization']['original_deadlines'].update(outer=1))
    def test_inflated_deadline(self):self.reject_terminal(lambda t:t['authorization']['original_deadlines'].update(outer=1e12))
    def test_wrong_export_interval(self):self.reject_terminal(lambda t:t.update(started_monotonic=0))
    def test_late_parent_export(self):self.reject_terminal(lambda t:t.update(finished_monotonic=1e12))
    def test_forged_authority_claim(self):self.reject_terminal(lambda t:t.update(scientific_goal_met=True))
    def test_archive_member_changed(self):self.reject_terminal(lambda t:t['archive']['members']['owned-result.json'].update(sha256='0'*64))
    def test_actual_raw_proof_negatives(self):
        changes=[('installed-parent/owned-tree/launch.json',lambda d:d.update(worker_argv=['different'])),
          ('installed-parent/owned-tree/worker-launch.json',lambda d:d['worker_identity'].update(birth=0)),
          ('installed-parent/owned-tree/closure.json',lambda d:d.update(errors=['failure'])),
          ('installed-parent/closure.json',lambda d:d.update(proof={})),
          ('installed-parent/closure.json',lambda d:d.update(deadline_epoch=1)),
          ('result.json',lambda d:d.update(status='unrelated'))]
        with tempfile.TemporaryDirectory(prefix='archived-wrapper-mutations-') as tmp:
            for i,(path,change) in enumerate(changes):
                root=Path(tmp)/str(i);shutil.copytree(self.root,root);p=root/path;d=json.loads(p.read_bytes());change(d);p.write_bytes(enc(d))
                with self.subTest(path=path),self.assertRaises((ValueError,KeyError,TypeError)):self.api['verify_wrappers'](root,**self.kw)
            root=Path(tmp)/'missing';shutil.copytree(self.root,root);(root/'installed-parent/owned-tree/launch.json').unlink()
            with self.assertRaises(FileNotFoundError):self.api['verify_wrappers'](root,**self.kw)
    def test_actual_complete_tiny_export_schema_only(self):
        proof=BASE/'portfolio63-rl-batched-20261012/proof-output';raw=(proof/'outer-closure.json').read_bytes()
        outer=json.loads(raw);owned=json.loads((proof/'owned-result.json').read_bytes())
        terminal=json.loads(proof.with_name(proof.name+'.evidence.zip.terminal.json').read_bytes())
        self.assertTrue(owned['fixture']);self.assertEqual(terminal['status'],'complete')
        authority=self.api['verify_terminal_authority'](terminal,runtime_outer=outer,owned=owned,output=str(proof),
            source_sha256=owned['source_sha256'],epoch=owned['clock']['original_epoch'],outer_raw=raw)
        self.assertEqual(authority['kind'],'live-owned-model-closure')
    def test_consistently_forged_clock_rejected(self):
        for mode in ('offset','mapping'):
            with self.subTest(mode=mode):
                outer=json.loads(self.kw['runtime_outer_raw']);owned=json.loads(self.kw['runtime_owned_result_raw']);t=json.loads(self.kw['runtime_terminal_raw'])
                for c in (outer['original_clock'],owned['clock'],t['authorization']['original_clock']):
                    if mode=='offset':c['offsets']['outer']=43000
                    else:c['origin_monotonic']+=1
                with self.assertRaises(ValueError):self.api['verify_terminal_authority'](t,runtime_outer=outer,owned=owned,output=outer['output_root'],source_sha256=owned['source_sha256'],epoch=owned['clock']['original_epoch'],outer_raw=self.kw['runtime_outer_raw'])
if __name__=='__main__':unittest.main(verbosity=2)
