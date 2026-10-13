"""Independent orchestration probes with explicit non-neural test doubles.

These exercise the actual generation/inverse, LOO, selection and physical wrapper
code. They complement, and do not replace, the real-native state test.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'worktree'))
from tools.arc_qwen_transfer_20261012 import experiment as e
from tools.arc_qwen_transfer_20261012.backend import TransferMeteredModel
from tools.arc_learning_agent_20261011.budget import WorkLedger
from tools.arc_learning_agent_20261011.grid_codec import decode_grid

class TestTokenizer:
    def apply_chat_template(self,messages,**kw):return '\n'.join(m['content'] for m in messages)
    def encode(self,text,**kw):return list(text.encode())

class EchoNative:
    prompt_cap=3072;output_cap=1024
    tokenizer=TestTokenizer()
    def _prompt(self,messages):
        text=self.tokenizer.apply_chat_template(messages);return text,self.tokenizer.encode(text)
    def generate(self,messages,**kwargs):
        text=messages[-1]['content'].rsplit('Query\nInput:\n',1)[1].split('\nOutput:')[0]
        return {'valid':True,'dispatched':True,'model_forward_started':True,'text':text,
            'finish_reason':'eos','output_token_ids':list(text.encode())+[151645],
            'output_tokens':len(text)+1,'input_tokens':self._prompt(messages)[1].__len__(),
            'forward_input_tokens':self._prompt(messages)[1].__len__(),'fatal_error':False}
    def score_completion(self,messages,completion,**kwargs):
        return {'valid':True,'dispatched':True,'input_tokens':len(self._prompt(messages)[1])+len(completion)+1,
            'nll_sum':float(len(completion)+1),'token_count':len(completion)+1}

class IsolatedTrainerDouble:
    def __init__(self,ledger):
        self.ledger=ledger;self.task=None;self.steps=0;self.total_updates=0;self.calls=[];self._counter=0
    def fingerprint(self):return {'sha256':hashlib.sha256(('global-selected' if self.task is None or self.steps==0 else self.task+':'+str(self.steps)).encode()).hexdigest()}
    def begin_task(self,task):
        if self.task is not None:raise ValueError('task carried over')
        self.task=task;self.steps=0;self.calls.append(('begin',task,self.fingerprint()['sha256']))
    def adapt_task(self,task,demos,*,max_steps,deadline):
        if self.task!=task:raise ValueError('different task')
        self.calls.append(('adapt',task,deepcopy(demos),max_steps))
        self._counter+=1;event='fixture-training-'+str(self._counter)
        charge={'training_steps':max_steps,'input_tokens':max_steps*4}
        self.ledger.reserve(event,charge);self.ledger.complete(event,charge)
        self.steps+=max_steps;self.total_updates+=max_steps
        return {'status':'complete','optimizer_steps':max_steps,'total_steps':self.steps,'physical_event_id':event}
    def end_task(self):
        self.calls.append(('end',self.task));self.task=None;self.steps=0
        return {'adapter_sha256':self.fingerprint()['sha256']}

class RuntimeExecution(unittest.TestCase):
    def test_actual_generate_variant_inverse_recovers_nonsquare_query(self):
        with tempfile.TemporaryDirectory() as td:
            ledger=WorkLedger(Path(td)/'ledger.jsonl');model=TransferMeteredModel(EchoNative(),ledger)
            query=[[0,1,2],[3,4,5]]
            case={'case_id':'review-query','demos':[{'input':[[1,2]],'output':[[1,2]]}], 'query_input':query}
            for op in (0,1):
                out=e.generate_variant(model,case,op,Path(td)/f'gen-{op}.json',time.monotonic()+30)
                self.assertEqual(out['prediction'],query)
                self.assertIs(out['inverse_applied'],True)
                self.assertIsNotNone(out['physical_event_id'])
            self.assertEqual(ledger.used['generation_calls'],2)
            self.assertFalse(ledger.pending)

    def test_real_ttt_loop_charges_every_fold_and_independent_final_refit(self):
        with tempfile.TemporaryDirectory() as td:
            ledger=WorkLedger(Path(td)/'ledger.jsonl');model=TransferMeteredModel(EchoNative(),ledger)
            trainer=IsolatedTrainerDouble(ledger);session=SimpleNamespace(model=model,trainer=trainer,ledger=ledger)
            demos=[{'input':[[1,2]],'output':[[1,2]]},{'input':[[3],[4]],'output':[[3],[4]]}]
            case={'case_id':'dev:review','demos':demos,'query_input':[[5,6,7]],'source':{'review_fixture_only':True}}
            out=e.run_ttt_case(session,case,{'manifest_sha256':'a'*64},Path(td)/'ttt',time.monotonic()+90)
            self.assertEqual(trainer.total_updates,16*(len(demos)+1))
            self.assertEqual(ledger.used['training_steps'],48)
            self.assertEqual(ledger.used['generation_calls'],3*2+6)
            self.assertEqual(ledger.used['scoring_forwards'],3*2)
            self.assertFalse(ledger.pending);self.assertIsNone(trainer.task)
            begins=[r for r in trainer.calls if r[0]=='begin']
            self.assertEqual(len(begins),3);self.assertEqual(len({r[2] for r in begins}),1)
            adapt=[r for r in trainer.calls if r[0]=='adapt']
            self.assertEqual(len(adapt),6)
            for held in range(2):
                calls=[r for r in adapt if r[1].endswith(':fold'+str(held))]
                self.assertEqual(len(calls),2)
                self.assertTrue(all(r[2]==[demos[1-held]] and r[3]==8 for r in calls))
            full=[r for r in adapt if r[1].endswith(':query-full-demo')]
            self.assertEqual(len(full),2);self.assertTrue(all(r[2]==demos for r in full))
            self.assertEqual(out['outer_folds'],2);self.assertEqual(out['full_demo_retrains'],1)
            self.assertEqual(out['answers'],[[[5,6,7]]])
            self.assertEqual(out['reference_role'],'selected_global_sft')
            self.assertEqual(out['selection']['rankings'][0]['candidate_id'],'ttt0')

if __name__=='__main__':unittest.main(verbosity=2)
