import contextlib,copy,hashlib,io,json,sys,tempfile,time,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
SRC=Path(__file__).resolve().parents[1]/'src';sys.path.insert(0,str(SRC))
import arc_suite as s
TASK={'train':[{'input':[[1,2]],'output':[[2,1]]},{'input':[[5,6]],'output':[[6,5]]}],'test':[{'input':[[3,4]]}]}
PROGRAM='def transform(grid):\n    return [row[::-1] for row in grid]\n'
IR='{"steps":[{"op":"flip_horizontal"}]}'
class Tokenizer:
 def apply_chat_template(self,messages,**kwargs):return json.dumps(messages,sort_keys=True)
 def encode(self,text,**kwargs):return list(hashlib.sha256(text.encode()).digest())
class Fixture:
 def __init__(self,root):
  self.root=Path(root);self.original=copy.deepcopy(s.read(SRC/'solver-manifest-reference.json'))
  self.ch={tid:copy.deepcopy(TASK) for tid in self.original['core']['tuning_ids']}
  self.truth=self.root/'truth.json';s.write(self.truth,{tid:[[[4,3]]] for tid in self.ch})
  self.original['core']['solutions_sha256']=s.file_sha(self.truth)
  self.original['challenge_sha256']={tid:s.digest(value) for tid,value in self.ch.items()}
  self.original_read=s.read;self.audit={'prompts':{}}
  tok=Tokenizer()
  for tid in self.ch:
   self.audit['prompts'][tid]={}
   for p in ['direct_grid','detailed_contract','host_toolbox','host_python','typed_ir','proposal_pool','generic_static','precise_static','raw_grid','raw_plus_objects','redacted_demo','true_demo','independent_roots','best_first_memory']:
    r=s.render_initial(self.ch[tid],p,tok);self.audit['prompts'][tid][p]={k:r[k] for k in ('prompt_tokens','input_token_ids_sha256','rendered_text_sha256')}
 def read(self,path):
  if Path(path)==SRC/'solver-manifest-reference.json':return copy.deepcopy(self.original)
  if Path(path)==SRC/'visible-token-audit.json':return copy.deepcopy(self.audit)
  return self.original_read(path)
 def manifest(self,run_id,policy=None):
  ids=self.original['core']['tuning_ids'][8:40] if run_id=='N14' else s.ENGINEERING_TASKS
  ch={t:self.ch[t] for t in ids};return s.make_manifest(run_id,self.original,ch,selected_policy=policy),ch
 def run(self,run_id,*,policy=None,generate=None):
  out=self.root/run_id;out.mkdir();m,ch=self.manifest(run_id,policy);byid={r['record_id']:r for r in m['records']}
  s.write(out/'manifest.json',m);s.write(out/'challenges.json',ch)
  calls=[]
  def gen(req):
   calls.append(req);p=m['core']['policies'][byid[req['record_id']]['arm']]
   text='[[4,3]]' if p=='direct_grid' else IR if p in ('typed_ir','proposal_pool') else PROGRAM
   return {'text':text,'model_id':'mock-base','prompt_tokens':len(req['input_token_ids']),'generated_tokens':20,'finish_reason':'stop','generation_wall_seconds':0.001}
  with contextlib.redirect_stdout(io.StringIO()):s.run_records(m,ch,out,Tokenizer(),generate or gen,'mock-base',time.monotonic()+600)
  s.seal(out,m,{'confirmed_stopped':True,'returncode':0,'timed_out':False});r=s.score(out,m,self.truth)
  return out,m,r,calls

class CoreTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.fx=Fixture(cls.tmp.name)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def setUp(self):self.p=patch.object(s,'read',side_effect=self.fx.read);self.p.start()
 def tearDown(self):self.p.stop()
 def test_disabled_is_inert(self):
  with patch.object(s,'verify_sources',side_effect=AssertionError):
   for x in range(5,15):self.assertEqual(s.launch({},'N'+str(x),enabled=False)['files_written'],0)
  with self.assertRaises(ValueError):s.launch({},'N6',enabled=1)
 def test_exact672_call_suite(self):self.assertEqual(sum(x['max_model_calls'] for x in s.design()['runs']),672)
 def test_frozen_exposure(self):
  m,ch=self.fx.manifest('N14','true_demo');self.assertEqual(m['core']['tasks'],self.fx.original['core']['tuning_ids'][8:40]);self.assertFalse(set(m['core']['tasks'])&set(s.ENGINEERING_TASKS));s.verify_manifest(m,ch)
 def test_rehashed_budget_and_policy_rejected(self):
  m,ch=self.fx.manifest('N6')
  for key,value in [('max_new_tokens',4096),('max_context_tokens',16384),('sampling',{'do_sample':False}),('policies',{'detailed_contract':'typed_ir','host_toolbox':'typed_ir'}),('tasks',list(reversed(m['core']['tasks']))),('record_arms',['typed_ir','host_toolbox'])]:
   bad=copy.deepcopy(m);bad['core'][key]=value;bad['core_sha256']=s.digest(bad['core']);bad['records']=s.identities(bad['core'])
   with self.assertRaises(ValueError,msg=key):s.verify_manifest(bad,ch)
 def test_truth_rejected_in_solver_task(self):
  bad=copy.deepcopy(TASK);bad['test'][0]['output']=[[4,3]]
  with self.assertRaises(ValueError):s.task(bad)
 def test_independent_gates_block_before_calls(self):
  self.assertEqual(s.resolve_gate('N9',{})['status'],'blocked');self.assertEqual(s.resolve_gate('N14',{})['status'],'blocked')
 def test_N6_full64_real_verifier(self):
  out,m,r,calls=self.fx.run('N6');self.assertEqual(len(calls),64)
  for g in r['groups'].values():self.assertEqual(g['top1_exact'],8);self.assertEqual(g['stages']['ast_admitted'],32);self.assertEqual(g['known_generated_tokens'],640)
  s.write(out/'report.json',r);s.write(out/'summary.json',{'status':'complete','processes_ok':True});archive=s.finalize(out)
  _,rr,_=s.verified_prior(out,'N6');self.assertEqual(rr,r)
  _,rr,_=s.verified_prior(archive['path'],'N6');self.assertEqual(rr,r)
  self.assertEqual(s.resolve_gate('N9',{'N6':out})['status'],'passed')
  data=s.read(out/'report.json');data['groups']['host_toolbox']['top1_exact']=0;(out/'report.json').write_bytes(s.canonical(data))
  with self.assertRaises(ValueError):s.verified_prior(out,'N6')
 def test_N7_typed_compiler_real_verifier(self):
  _,_,r,calls=self.fx.run('N7');self.assertEqual(len(calls),64);self.assertEqual(r['groups']['typed_ir']['top2_exact'],8)
 def test_N8_same_initial_root(self):
  _,_,r,_=self.fx.run('N8');self.assertTrue(all(x['prompt_ids_equal'] and x['seeds_equal'] and x['response_text_equal'] for x in r['first_root_reproducibility']))
 def test_N9_exact_view_no_new_calls(self):
  _,_,r,calls=self.fx.run('N9');self.assertEqual(len(calls),64);self.assertEqual(r['groups']['raw_plus_objects']['top2_exact'],8)
 def test_N10_and_N11_full_contract(self):
  for run in ('N10','N11'):
   _,_,r,calls=self.fx.run(run);self.assertEqual(len(calls),64);self.assertEqual(r['physical_model_usage']['unknown_usage'],0)
 def test_N12_shared_cost_fixed_cpu_denominators(self):
  ir=s.component('arc_typed_ir');original=ir.order_candidates
  def limited(*args,**kwargs):return original(*args,**kwargs)[:2]
  with patch.object(ir,'order_candidates',side_effect=limited):_,_,r,calls=self.fx.run('N12')
  self.assertEqual(len(calls),32);self.assertEqual(r['physical_model_usage']['known_generate_calls'],32)
  for g in r['groups'].values():self.assertEqual(g['slot_denominator'],512);self.assertEqual(g['known_generate_calls'],32);self.assertGreater(g['excluded_slots'],0)
 def test_N14_mock256_real_verifier(self):
  _,_,r,calls=self.fx.run('N14',policy='true_demo');self.assertEqual(len(calls),256);self.assertEqual(r['groups']['selected_agent']['top2_exact'],32);self.assertEqual(r['paired_top2_interval']['point_delta'],0)
 def test_seal_required_before_gold(self):
  with tempfile.TemporaryDirectory() as td:
   m,ch=self.fx.manifest('N6');out=Path(td)
   with self.assertRaises(FileNotFoundError):s.score(out,m,Path('/this-gold-must-not-be-read'))
 def test_seal_tampering_rejected_before_gold(self):
  with tempfile.TemporaryDirectory() as td:
   m,ch=self.fx.manifest('N6');out=Path(td);s.write(out/'a.json',{});s.seal(out,m,{'confirmed_stopped':True});(out/'a.json').write_text('changed')
   with self.assertRaises(ValueError):s.score(out,m,Path('/this-gold-must-not-be-read'))
 def test_response_known_but_verification_incomplete(self):
  with tempfile.TemporaryDirectory() as td:
   m,ch=self.fx.manifest('N6');out=Path(td);s.write(out/'challenges.json',ch);rec=m['records'][0];folder=out/'records'/rec['record_id']
   s.write(folder/'identity.json',rec);s.write(folder/'attempted.json',{'model_id':'mock'})
   s.write(folder/'response.json',{'text':PROGRAM,'generated_tokens':20,'prompt_tokens':32,'generation_wall_seconds':.01})
   seal=s.seal(out,m,{'confirmed_stopped':True});r=s.score(out,m,self.fx.truth)
   self.assertEqual(len(seal['states']['verification_incomplete']),1);self.assertEqual(len(seal['states']['unknown']),0)
   self.assertEqual(r['physical_model_usage']['known_generate_calls'],1);self.assertEqual(r['physical_model_usage']['unknown_usage'],0)
   self.assertEqual(r['groups'][rec['arm']]['verification_incomplete_slots'],1)
 def test_search_interruption_preserves_prefix_and_reserved_work(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td);m,ch=self.fx.manifest('N12');s.write(out/'challenges.json',ch);v=s.component('arc_program_v2');old=v.verify_program;count=0
   def failing(*args,**kwargs):
    nonlocal count
    count+=1
    if count==4:raise RuntimeError('injected verifier interruption')
    return old(*args,**kwargs)
   def gen(req):return {'text':IR,'model_id':'mock-base','prompt_tokens':len(req['input_token_ids']),'generated_tokens':20,'finish_reason':'stop','generation_wall_seconds':.001}
   with patch.object(v,'verify_program',side_effect=failing),contextlib.redirect_stdout(io.StringIO()):
    with self.assertRaisesRegex(RuntimeError,'injected'):s.run_records(m,ch,out,Tokenizer(),gen,'mock-base',time.monotonic()+600)
   s.seal(out,m,{'confirmed_stopped':True,'returncode':1});r=s.score(out,m,self.fx.truth)
   self.assertFalse(r['search_ledger_complete']);self.assertEqual(r['physical_model_usage']['known_generate_calls'],32)
   self.assertEqual(sum(g['cpu_verification_reservations'] for g in r['groups'].values()),4)
   self.assertEqual(sum(g['cpu_unknown_work_reservations'] for g in r['groups'].values()),1)
   self.assertGreaterEqual(sum(g['program_steps'] for g in r['groups'].values()),200000)
   self.assertEqual(sum(g['completed_slots'] for g in r['groups'].values()),3)
 def test_empty_neural_prior_equals_uniform(self):
  ir=s.component('arc_typed_ir');self.assertEqual(ir.order_candidates([],mode='uniform'),ir.order_candidates([],mode='smoothed'))
 def test_N5_cpu_reservations_and_interrupted_charge(self):
  m,ch=self.fx.manifest('N5')
  with tempfile.TemporaryDirectory() as td:
   out=Path(td);s.write(out/'challenges.json',ch)
   for rec in m['records']:
    folder=out/'records'/rec['record_id'];s.write(folder/'identity.json',rec);s.write(folder/'attempted.json',{'kind':'cpu-verification','reserved_program_steps':200000})
    s.write(folder/'result.json',{'status':'completed','score_eligible':False,'candidate':None,'program_steps':12})
   s.seal(out,m,{'confirmed_stopped':True});r=s.score(out,m,self.fx.truth)
   for g in r['groups'].values():self.assertEqual(g['cpu_verification_reservations'],61);self.assertEqual(g['program_steps'],732)
   self.assertEqual(r['physical_model_usage']['known_generate_calls'],0)
  with tempfile.TemporaryDirectory() as td:
   out=Path(td);s.write(out/'challenges.json',ch);rec=m['records'][0];folder=out/'records'/rec['record_id']
   s.write(folder/'attempted.json',{'kind':'cpu-verification','reserved_program_steps':200000});s.seal(out,m,{'confirmed_stopped':True})
   r=s.score(out,m,self.fx.truth);g=r['groups'][rec['arm']]
   self.assertEqual(g['cpu_verification_reservations'],1);self.assertEqual(g['cpu_unknown_work_reservations'],1);self.assertEqual(g['program_steps'],200000)
   self.assertEqual(r['physical_model_usage']['unknown_usage'],0)
 def test_bad_archive_path(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'bad.zip'
   with zipfile.ZipFile(p,'w') as z:z.writestr('../escape','x')
   with self.assertRaises(ValueError):s.materialize_prior(p)
 def test_unknown_policy_rejected(self):
  with self.assertRaises(ValueError):s.render_initial(TASK,'mistyped-policy',Tokenizer())
 def test_response_source_is_not_host_executed(self):
  for text in ('import os\ndef transform(g):\n return g','def transform(g):\n return g.__class__','def transform(g):\n return open(g)'):
   r=s.verify_candidate(text,TASK,'host_python');self.assertIsNone(r['candidate']);self.assertFalse(r['ast_admitted'])

if __name__=='__main__':unittest.main(verbosity=2)
