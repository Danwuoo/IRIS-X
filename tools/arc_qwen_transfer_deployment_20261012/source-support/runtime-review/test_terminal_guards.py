"""Independent terminal/control-flow fault injection, explicitly simulated owner.

Real process-closure proof is covered by the separate owner tests; these tests
ensure later export/scoring errors cannot overwrite final status truthfully.
"""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'worktree'))
from tools.arc_qwen_transfer_20261012 import runner as r,public_evaluation as pe
from tools.arc_learning_agent_20261011.budget import atomic_json

class FakeGuard:
    def __init__(self,proof):self.proof=proof
    def poll(self):return self.proof['worker_returncode']
    def closed_proof(self):return self.proof

class TerminalGuards(unittest.TestCase):
    def run_fault(self,fault):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name)/'run'
        proof={'closed':True,'returncode':0,'worker_returncode':2 if fault=='owner_failure' else 0,'forced':False}
        child={'status':'TRANSFER_COMPLETE','science_complete':True,'operational_success':True,
               'public_branch':{'status':'PUBLIC_PREDICTIONS_SEALED'},'provider_status':'COMPLETE'}
        def spawn(*args,**kwargs):
            atomic_json(root/'child-summary.json',child);return FakeGuard(proof)
        cfg={'enabled':True,'tiny_cpu':True,'test_fixture_dataset':True,'started_epoch':time.time(),'maximum_seconds':120,
             'public_solver_root':str(Path(temp.name)/'solver'),'public_solver_manifest_sha256':'a'*64,
             'public_evaluator_root':str(Path(temp.name)/'evaluator'),'public_evaluator_manifest_sha256':'b'*64}
        with ExitStack() as stack:
            stack.enter_context(patch.object(r,'source_identity',return_value={'review': 'c'*64}))
            stack.enter_context(patch.object(r,'source_check'))
            stack.enter_context(patch.object(r,'verify_closed_proof'))
            stack.enter_context(patch.object(r.OwnedProcessGuard,'spawn',side_effect=spawn))
            stack.enter_context(patch.object(r,'checkpoint_inventory',return_value={'complete_store':True,'files':{},'bytes':0}))
            stack.enter_context(patch.object(pe,'seal_predictions',return_value={'sha256':'d'*64}))
            evaluator=stack.enter_context(patch.object(pe,'evaluate_sealed',side_effect=RuntimeError('injected public scorer failure') if fault=='public_failure' else None,return_value={'status':'fixture'}))
            archive=stack.enter_context(patch.object(r,'archive_closed',side_effect=RuntimeError('injected archive failure') if fault=='archive_failure' else None,return_value={'path':'fixture'}))
            out=r.run_owned_transfer(cfg,root)
        return out,json.loads((root/'terminal-receipt.json').read_text()),evaluator,archive

    def test_public_failure_cannot_be_promoted_to_operational_success(self):
        out,terminal,_,_=self.run_fault('public_failure')
        for result in (out,terminal):
            self.assertIn('injected public scorer failure',result['public_evaluation_error'])
            self.assertFalse(result['operational_success'])

    def test_archive_failure_cannot_promote_complete_child(self):
        out,terminal,_,_=self.run_fault('archive_failure')
        for result in (out,terminal):
            self.assertEqual(result['status'],'TRANSFER_FAILED')
            self.assertFalse(result['science_complete']);self.assertFalse(result['operational_success'])

    def test_owner_failure_cannot_promote_provider_complete(self):
        out,terminal,evaluator,_=self.run_fault('owner_failure')
        for result in (out,terminal):
            self.assertEqual(result['status'],'TRANSFER_FAILED')
            self.assertFalse(result['science_complete']);self.assertFalse(result['operational_success'])
        evaluator.assert_not_called()

    def test_archive_stream_checks_deadline_inside_each_chunk(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'large.bin';path.write_bytes(b'x'*(2*1024**2));sha=hashlib.sha256(path.read_bytes()).hexdigest()
            with zipfile.ZipFile(Path(td)/'bounded.zip','w') as archive:
                with patch.object(r.time,'monotonic',side_effect=[0.,0.,2.]):
                    with self.assertRaisesRegex(ValueError,'archive stream deadline'):
                        r._zip_member(archive,path,'large.bin',sha,1.)
            with zipfile.ZipFile(Path(td)/'bounded.zip') as archive:
                self.assertEqual(archive.getinfo('large.bin').file_size,1024**2)

if __name__=='__main__':unittest.main(verbosity=2)
