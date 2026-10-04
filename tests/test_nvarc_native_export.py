"""Real process/hash-seed regressions; all generated evidence is tiny CPU only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import stage_nvarc_native_multitask as stage
from tools.nvarc_native_multitask import canonical

ROOT=Path(__file__).resolve().parents[1]


class NativeExportProcessTests(unittest.TestCase):
    def run_python(self,code,seed,*args):
        environment=dict(os.environ,PYTHONHASHSEED=seed,CUDA_VISIBLE_DEVICES='',
            PYTHONPATH=str(ROOT),HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1',
            TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='1',PYTHONIOENCODING='utf-8')
        result=subprocess.run([sys.executable,'-c',code,*map(str,args)],cwd=ROOT,
            env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
            encoding='utf-8',timeout=120)
        self.assertEqual(result.returncode,0,result.stderr)
        return result

    def test_in_process_environment_change_cannot_pass_startup_guard(self):
        code="""
import json,os,sys
from tools.nvarc_native_export import startup_context
os.environ['PYTHONHASHSEED']='0'
try:startup_context()
except RuntimeError as error:
 print(json.dumps({'startup_flag':sys.flags.hash_randomization,'error':str(error)}))
else:raise AssertionError('changing environment must not change startup hash')
"""
        observed=json.loads(self.run_python(code,'1').stdout)
        self.assertEqual(observed['startup_flag'],1)
        self.assertIn('fresh interpreter',observed['error'])
        good=json.loads(self.run_python(
            "import json;from tools.nvarc_native_export import startup_context;print(json.dumps(startup_context()))",'0').stdout)
        self.assertEqual(good['hash_randomization_flag'],0);self.assertEqual(good['new_model_calls'],0)

    def test_mixed_seed_parent_exports_real_tiny_cpu_evidence_in_fresh_child(self):
        # Only fixture provenance/readout is substituted. Actual source DFS,
        # eight-view token verification, ranking and exporter all run unchanged.
        fixture_builder="""
import json,pathlib,shutil,sys
from tests.test_nvarc_native_multitask import MultiTaskTests as Fixture
from tools import nvarc_native_submission as bridge,stage_nvarc_native_multitask as stage
target=pathlib.Path(sys.argv[1]);Fixture.setUpClass()
try:
 Fixture.plan['approved']=True
 evidence,_=Fixture.produce()
 for name,key in stage.files_for(Fixture.raw).items():
  destination=target/name;destination.parent.mkdir(parents=True,exist_ok=True)
  shutil.copyfile(Fixture.directory/name,destination)
 values={'plan.json':Fixture.plan,'challenges.json':Fixture.challenges,
  'worker-receipts.json':[e['receipt'] for e in evidence],'fixture-evidence.json':evidence}
 submission,audit=bridge.build_native_submission(Fixture.challenges,Fixture.plan,evidence,
  target,Fixture.tokenizer,allow_fixture=True)
 values['expected-submission.json']=submission
 for name,value in values.items():(target/name).write_text(json.dumps(value),encoding='utf-8')
finally:Fixture.tearDownClass()
"""
        parent_driver="""
import json,os,pathlib,subprocess,sys,time
from tools import nvarc_native_multitask_render as render,nvarc_native_submission as bridge
from tools.stage_nvarc_native_multitask import MODEL
from tokenizers import Tokenizer
work=pathlib.Path(sys.argv[1]);repository=pathlib.Path.cwd()
plan=json.loads((work/'plan.json').read_bytes());challenges=json.loads((work/'challenges.json').read_bytes())
evidence=json.loads((work/'fixture-evidence.json').read_bytes())
tok=Tokenizer.from_file(str(MODEL/'model/tokenizer.json'))
class Tokens:
 def encode(self,text):return tok.encode(text).ids
 def decode(self,values):return tok.decode(values,skip_special_tokens=False)
os.environ['PYTHONHASHSEED']='0'
assert sys.flags.hash_randomization==1
try:bridge.build_native_submission(challenges,plan,evidence,work,Tokens(),allow_fixture=True)
except RuntimeError as error:assert str(error)=='eight-view actual source verification input/answer differs',str(error)
else:raise AssertionError('mixed-seed in-process export must fail')
# Explicit synthetic CPU adapter: no native/GPU provenance or admission is
# asserted. The production helper keeps its real startup and token/DFS gates.
runner='import json,pathlib,sys\\n'
runner+='sys.path.insert(0,'+repr(str(repository))+')\\n'
runner+='from tools import nvarc_native_export as actual,nvarc_native_submission as bridge\\n'
runner+='root=pathlib.Path(sys.argv[sys.argv.index("--root")+1])\\n'
runner+='actual.read_task_evidence=lambda *_:json.loads((root/"fixture-evidence.json").read_bytes())\\n'
runner+='actual.build_native_submission=lambda *args:bridge.build_native_submission(*args,allow_fixture=True)\\n'
runner+='actual.main()\\n'
(work/'tools/nvarc_native_export.py').write_text(runner,encoding='utf-8')
scope={'plan':plan,'START':time.monotonic(),'time':time,'os':os,'sys':sys,
 'subprocess':subprocess,'work':work,'model':MODEL/'model','dependency':work/'unused-dependency'}
exec(render.ISOLATED_EXPORT,scope);scope['final_export']()
actual=json.loads((work/'submission.json').read_bytes())
assert actual==json.loads((work/'expected-submission.json').read_bytes())
context=json.loads((work/'export-process.json').read_bytes())
audit=json.loads((work/'submission-audit.json').read_bytes())
assert all(s in {'tiny_cpu_model','filler'} for r in audit['rows'] for s in r['attempt_sources'])
print(json.dumps({'parent_startup_flag':sys.flags.hash_randomization,'child_context':context,
 'task_count':audit['task_count'],'test_output_count':audit['test_output_count'],'fixture':'tiny-cpu-model'}))
"""
        with tempfile.TemporaryDirectory(prefix='iris-native-export-fixture-') as temp:
            self.run_python(fixture_builder,'0',temp)
            result=json.loads(self.run_python(parent_driver,'1',temp).stdout.splitlines()[-1])
        self.assertEqual(result['parent_startup_flag'],1)
        self.assertEqual(result['child_context']['hash_randomization_flag'],0)
        self.assertEqual(result['child_context']['new_model_calls'],0)
        self.assertTrue(result['child_context']['cpu_only'])
        self.assertEqual((result['task_count'],result['test_output_count']),(2,3))

    def test_legacy_review_bytes_stay_frozen_and_new_export_proposal_is_inert(self):
        old,raw_old,notebook,_=stage.construct('nvarc-original-qwen3-native-multitask-007')
        new,raw_new,notebook_new,_=stage.construct('nvarc-original-qwen3-native-multitask-009')
        self.assertEqual(hashlib.sha256(canonical(notebook)).hexdigest(),
            'a4d9d481fa2693f8b9a1d79a363e804532171d396d3fbf1dc6b0cac7131e1e19')
        self.assertFalse(new['approved']);self.assertFalse(new['agent_execution_authorized'])
        self.assertIsNone(new['controller_admission'])
        self.assertEqual({k:v for k,v in raw_old.items() if k!='plan'},
            {k:v for k,v in raw_new.items() if k not in {'plan','native_export'}})
        self.assertEqual(old['task_specs'],new['task_specs'])
        source=''.join(notebook_new['cells'][0]['source'])
        self.assertIn("CUDA_VISIBLE_DEVICES=''",source)
        self.assertIn("timeout=limit,check=True",source)
        self.assertEqual(new['maximum_export_process_seconds'],240)


if __name__=='__main__':unittest.main()
