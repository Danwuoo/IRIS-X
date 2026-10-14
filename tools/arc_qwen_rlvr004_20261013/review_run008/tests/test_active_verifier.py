"""Synthetic-only tests; no emitted approval, provider or real clock."""
from pathlib import Path
import copy,hashlib,json,sys,tempfile,types,unittest
from unittest.mock import patch
ROOT=Path(__file__).absolute().parents[4]
(ROOT/'.irisx/run008-launch-review/public-test-scratch').mkdir(parents=True,exist_ok=True)
VERIFIER=ROOT/'tools/arc_qwen_rlvr004_20261013/review_run008/verify_active_wire.py'
v=types.ModuleType('independent_active_review_test');v.__file__=str(VERIFIER)
exec(compile(VERIFIER.read_bytes(),str(VERIFIER),'exec',dont_inherit=True,optimize=sys.flags.optimize),vars(v))
DRAFT=ROOT/'.irisx/run008-admission/draft-0001';EPOCH=1790000000
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def put(path,value):
 raw=value if isinstance(value,bytes) else v.encoded(value);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);return {'path':str(path),'sha256':sha(raw),'bytes':len(raw)}
class ActiveVerifierTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'.irisx/run008-launch-review/public-test-scratch');self.root=Path(self.tmp.name);self.candidate=self.root/'candidate';self.state=self.root/'state';self.state.mkdir()
  m=json.loads((DRAFT/'publication-manifest.json').read_bytes());m['run_authorized']=True
  for row in m['notebooks']:
   if row['role']=='rlvr004':row['run_authorized']=True
  release=json.loads((DRAFT/'notebook-release.json').read_bytes());release['production_admitted']=True
  put(self.candidate/'notebook-release.json',release)
  for name in ('assembly/finalize.py','code-payload/deployment/notebook_builder.py','code-payload/deployment/source_loader.py'):
   put(self.candidate/name,(DRAFT/name).read_bytes())
  m['jit']['dependencies'][0].update({k:x for k,x in put(self.candidate/'notebook-release.json',release).items() if k!='path'})
  md=put(self.candidate/'publication-manifest.json',m);self.m=m
  fmodule=types.ModuleType('test_fixed_finalizer');exec(compile((self.candidate/'assembly/finalize.py').read_bytes(),'<fixed-fixture-finalizer>','exec'),vars(fmodule));docs=fmodule.finalize(self.candidate,EPOCH)
  descriptors={name:put(self.state/name,raw) for name,raw in docs.items()};n=next(x for x in m['notebooks'] if x['role']=='rlvr004')
  self.clock={'dispatch_epoch':EPOCH,'predispatch_epoch':EPOCH,'deadline_epoch':EPOCH+43200,'global_deadline_epoch':EPOCH+43200,'execution_deadline_epoch':EPOCH+42000,'outer_deadline_epoch':EPOCH+42180,'provider_timeout_seconds':42300}
  self.final={'format':'irisx/rlvr-finalization-v1','manifest_sha256':md['sha256'],'template_sha256':n['sha256'],'finalized_sha256':sha(docs['active-finalized.ipynb']),'documents':descriptors,'finalizer_sha256':m['jit']['entry']['sha256'],**self.clock};fd=put(self.state/'finalization.json',self.final)
  config={'candidate_root':str(self.candidate),'state_root':str(self.state),'publication_manifest_sha256':md['sha256']};cd=put(self.root/'config.json',config)
  code={'dataset_id':12504696,'version':21,'is_private':True,'exact_byte_roundtrip':True,'manifest_sha256':md['sha256']};cod=put(self.state/'dataset-code-v21-receipt.json',code)
  inactive={'kernel_id':138123872,'version':40,'status':'COMPLETE','normalized_source_exact':True,'manifest_sha256':md['sha256']};ind=put(self.state/'notebook-inactive-receipt.json',inactive)
  self.pins={'format':v.FORMAT,'status':'SOURCE_AND_PRELAUNCH_READBACKS_REVIEWED','synthetic_test_only':False,'verifier_sha256':sha(VERIFIER.read_bytes()),'candidate_root':str(self.candidate),'state_root':str(self.state),'publication_manifest_sha256':md['sha256'],'local_config_sha256':cd['sha256'],'prelaunch_files':{'local_config':cd},'code_receipt_sha256':cod['sha256'],'inactive_receipt_sha256':ind['sha256']}
  for k in ('material_approval_sha256','transport_review_sha256','monitor_review_sha256','mount_receipt_sha256','persisted_audit_sha256'):self.pins[k]='a'*64
  wire={'id':138123872,'slug':v.REF,'new_title':'IRIS-X Learning Agent 20261011','text':docs['active-finalized.ipynb'].decode(),'language':'python','kernel_type':'notebook','dataset_data_sources':n['dataset_sources'],'model_data_sources':['qwen-lm/qwen-3/transformers/14b/1'],'competition_data_sources':['arc-prize-2026-arc-agi-3'],'kernel_data_sources':[],'is_private':True,'enable_gpu':True,'enable_tpu':False,'enable_internet':False,'docker_image':n['docker_image'],'kernel_execution_type':1,'session_timeout_seconds':42300,'machine_shape':'NvidiaRtxPro6000'}
  self.wire=wire;wd=put(self.state/'notebook-rlvr004-wire.json',(json.dumps(wire,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode())
  claim={'stage':'claimed','save_calls':0,'expected_version':41,'kernel_id':138123872,'reference':v.REF,'manifest_sha256':md['sha256'],'stop_after_submit_readback':False,'provider_monitoring_authorized':True}
  for key in ('material_approval_sha256','transport_review_sha256','monitor_review_sha256','mount_receipt_sha256','persisted_audit_sha256','code_receipt_sha256','inactive_receipt_sha256'):claim[key]=self.pins[key]
  cld=put(self.state/'notebook-rlvr004.claim.json',claim)
  self.journal={**claim,**self.clock,'stage':'wire_prepared','claim_sha256':cld['sha256'],'source_sha256':sha(docs['active-finalized.ipynb']),'wire_sha256':wd['sha256'],'finalization_sha256':fd['sha256']};put(self.state/'notebook-rlvr004-journal.json',self.journal)
 def tearDown(self):self.tmp.cleanup()
 def verify(self,now=EPOCH+2):
  d=put(self.root/'synthetic-pins.json',self.pins)
  with patch.object(v.time,'time',return_value=now):return v.verify(d['path'],d['sha256'])
 def test_exact_four_documents_in_memory_only(self):
  result=self.verify();self.assertEqual(result['status'],'PASS');self.assertTrue(result['exact_four_document_reconstruction']);self.assertEqual(result['provider_calls'],0)
 def test_synthetic_flag_rejected(self):
  self.pins['synthetic_test_only']=True
  with self.assertRaisesRegex(ValueError,'actual independently'):self.verify()
 def test_stale_and_future_epoch_rejected(self):
  for now in (EPOCH+61,EPOCH-1):
   with self.assertRaisesRegex(ValueError,'fresh immutable'):self.verify(now)
 def test_clock_reset_rejected(self):
  self.final['deadline_epoch']+=1;put(self.state/'finalization.json',self.final)
  with self.assertRaisesRegex(ValueError,'absolute original clock'):self.verify()
 def test_mutated_document_rejected(self):
  p=self.state/'operator.json';p.write_bytes(p.read_bytes()+b' ')
  with self.assertRaises(ValueError):self.verify()
 def test_changed_wire_even_boolean_coercion_rejected(self):
  self.wire['enable_gpu']=1;put(self.state/'notebook-rlvr004-wire.json',(json.dumps(self.wire,sort_keys=True,separators=(',',':'))+'\n').encode())
  with self.assertRaisesRegex(ValueError,'serialized bytes'):self.verify()
 def test_consumed_claim_rejected(self):
  self.journal['save_calls']=1;self.journal['stage']='save_intent';put(self.state/'notebook-rlvr004-journal.json',self.journal)
  with self.assertRaisesRegex(ValueError,'unsent'):self.verify()
 def test_changed_prelaunch_receipt_rejected(self):
  p=self.state/'notebook-inactive-receipt.json';p.write_bytes(p.read_bytes()+b' ')
  with self.assertRaises(ValueError):self.verify()
if __name__=='__main__':unittest.main(verbosity=2)
