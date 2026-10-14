"""Independent CPU receipt transition, with synthetic provider responses only."""
from pathlib import Path
import sys,unittest
from unittest import mock
ROOT=Path(__file__).absolute().parents[3]
(ROOT/'.irisx/run008-launch-review/public-test-scratch').mkdir(parents=True,exist_ok=True)
DIRECTORY=ROOT/'tools/arc_qwen_rlvr004_20261013/publication_run008'
sys.path.insert(0,str(DIRECTORY/'tests'))
import test_native_transport as fixtures
class Transition(unittest.TestCase):
 def setUp(self):
  self.fixture=fixtures.NativeTransportTests('test_stage_requires_new_review_and_sends_once');self.fixture.setUp()
 def tearDown(self):self.fixture.doCleanups()
 def prepare(self):
  fx=self.fixture;m,docs,p=fx.active_fixture();t=fx.t;fx.args.monitor_sha='9'*64
  with fx.save_patches(docs) as patched,mock.patch.object(t.time,'time',return_value=2000):
   patched['run_prerequisites'].return_value={'monitor_review_sha256':fx.args.monitor_sha}
   patched['predecessor'].return_value={'version':40,'status':'COMPLETE'};patched['finalized_documents'].return_value=docs
   t.save(p,m,fx.args,'rlvr004')
  review={'format':'irisx/run008-active-wire-review-v1','status':'PASS','synthetic_test_only':False,'publication_manifest_sha256':fx.args.manifest_sha,'material_approval_sha256':fx.args.material_sha,'transport_review_sha256':fx.args.review_sha,'local_config_sha256':fx.args.local_config_sha,'wire_sha256':fixtures.sha(t.STATE/'notebook-rlvr004-wire.json'),'finalization_sha256':fixtures.sha(t.STATE/'finalization.json'),'finalized_source_sha256':fixtures.sha(t.STATE/'active-finalized.ipynb'),'prepared_journal_sha256':fixtures.sha(t.STATE/'notebook-rlvr004-journal.json'),'predispatch_epoch':2000,'numeric_notebook_version':41}
  path=fx.root/'SYNTHETIC-REVIEW-NOT-FOR-PUBLICATION.json';path.write_bytes(fixtures.encoded(review));fx.args.active_review=str(path);fx.args.active_review_sha=fixtures.sha(path)
  with fx.dispatch_patches(docs):receipt=t.activate(p,m,fx.args)
  p.ensure_read_auth=mock.Mock()
  c=fixtures.load('independent_transition_collector',DIRECTORY/'rl_collect.py');c.transport=t;c._common=t._common
  return fx,t,c,m,docs,p,receipt
 def test_prepare_dispatch_receipt_collector_poll_chain(self):
  fx,t,c,m,docs,p,receipt=self.prepare()
  initial=fixtures.sha(t.STATE/'active-readback.claim.json')
  self.assertFalse(receipt['stop_after_submit_readback']);self.assertTrue(receipt['provider_monitoring_authorized']);self.assertFalse(receipt['single_post_submit_readback'])
  with mock.patch.object(t,'load_contract',return_value=m),mock.patch.object(t,'monitor_gate',return_value={}),mock.patch.object(t,'finalized_documents',return_value=docs):
   actual,l,j,f=c.bindings(fx.args)
  self.assertEqual(j['dispatch_epoch'],2010);self.assertEqual(f['predispatch_epoch'],2000);self.assertEqual(f['deadline_epoch'],45200)
  p.status.return_value.status.name='COMPLETE';snapshot=c.poll(p,m,receipt)
  self.assertEqual(snapshot['status'],'COMPLETE');self.assertEqual(snapshot['version'],41)
  self.assertEqual(p.save.call_count,1);self.assertEqual(fixtures.sha(t.STATE/'active-readback.claim.json'),initial)
 def test_collector_rejects_clock_reset_in_real_staged_receipt(self):
  fx,t,c,m,docs,p,receipt=self.prepare()
  journal=t.obj(t.STATE/'notebook-rlvr004-journal.json');journal['deadline_epoch']+=1
  (t.STATE/'notebook-rlvr004-journal.json').write_bytes(fixtures.encoded(journal))
  receipt['launch_journal_sha256']=fixtures.sha(t.STATE/'notebook-rlvr004-journal.json');(t.STATE/'notebook-rlvr004-receipt.json').write_bytes(fixtures.encoded(receipt))
  with mock.patch.object(t,'load_contract',return_value=m),mock.patch.object(t,'monitor_gate',return_value={}),mock.patch.object(t,'finalized_documents',return_value=docs):
   with self.assertRaisesRegex(ValueError,'clock_envelope_link'):c.bindings(fx.args)
  self.assertEqual(p.save.call_count,1)
if __name__=='__main__':unittest.main(verbosity=2)
