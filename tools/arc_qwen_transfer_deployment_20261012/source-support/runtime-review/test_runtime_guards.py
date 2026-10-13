"""Independent focused successor review; standard-library tests, no native imports.

Actual neural execution and pretrained/GPU evidence are explicitly out of scope.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'worktree'))
from tools.arc_qwen_transfer_20261012 import model_profile as p
from tools.arc_qwen_transfer_20261012.decoder import TransferPromptContract
from tools.arc_qwen_transfer_20261012.backend import TransferMeteredModel
from tools.arc_learning_agent_20261011.budget import WorkLedger

class FixtureTokenizer:
    """Exact character fixture, never impersonates actual native tokenization."""
    eos_token_id = 151645
    eos_token = '<eos>'
    all_special_ids = [151645, 151643]
    chat_template = 'fixture template'
    def get_vocab(self):
        return {**{chr(i):i for i in range(128)}, '<eos>':151645, '<pad>':151643}
    def get_added_vocab(self): return {'<eos>':151645, '<pad>':151643}
    def encode(self, text, add_special_tokens=False):
        if text.endswith(self.eos_token):
            return [ord(c) for c in text[:-len(self.eos_token)]] + [self.eos_token_id]
        return [ord(c) for c in text]
    def decode(self, ids, **kwargs):
        return ''.join(self.eos_token if i == self.eos_token_id else chr(i) for i in ids)
    def apply_chat_template(self, messages, *, tokenize=False, add_generation_prompt, enable_thinking=False):
        if add_generation_prompt:
            return ''.join(m['role']+':'+m['content']+'\n' for m in messages)+'assistant:'
        return self.apply_chat_template(messages[:-1], add_generation_prompt=True) + messages[-1]['content'] + self.eos_token+'\n'

def contract():
    return TransferPromptContract(FixtureTokenizer(), vocab_size=151936, eos_ids=[151645,151643], synthetic=True)

def config():
    return {'model_key':p.MODEL_KEY, 'profile_id':p.PROFILE_ID, 'tiny_cpu':True,
            'material_addendum_sha256':p.MATERIAL_ADDENDUM_SHA256}

class ProfileAndPrompt(unittest.TestCase):
    def test_context_contract_rejects_each_legacy_or_expanded_layer(self):
        good = p.validate_model_config(config())
        self.assertEqual([good[k] for k in ('context_limit','prompt_cap','output_cap')],[4096,3072,1024])
        for key,bad in [('profile_id','qwen3-14b-native-bf16-r8-c2048-probe-v1'),
                        ('context_limit',2048),('context_limit',8192),('prompt_cap',1792),
                        ('output_cap',256),('output_cap',1025),('tensor_parallel_size',True),
                        ('precision','fp8'),('material_addendum_sha256','0'*64)]:
            with self.subTest(key=key,bad=bad), self.assertRaises(ValueError):
                p.validate_model_config({**config(),key:bad})

    def test_all_legal_grid_cells_and_eos_are_supervised_without_truncation(self):
        c = contract(); text='\n'.join('0123456789'*3 for _ in range(30))
        row=c.prepare_completion([{'role':'user','content':'x'}],text)
        self.assertEqual(row['supervised_tokens'],930)
        self.assertEqual(row['completion'],text)
        self.assertEqual(row['labels'][:row['prompt_tokens']],[-100]*row['prompt_tokens'])
        self.assertEqual(row['labels'][row['prompt_tokens']:],row['input_ids'][row['prompt_tokens']:])
        self.assertEqual(row['labels'][-1],151645)
        self.assertEqual(c.validate_prepared(row),row)
        for mutate in ('mask','terminal','count','truncated'):
            changed=deepcopy(row)
            if mutate=='mask': changed['labels'][0]=changed['input_ids'][0]
            if mutate=='terminal': changed['input_ids'][-1]=49
            if mutate=='count': changed['supervised_tokens']-=1
            if mutate=='truncated': changed['completion']=changed['completion'][:-1]
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): c.validate_prepared(changed)

    def test_completion_cap_is_exact_and_failure_does_not_return_prefix(self):
        c=contract(); m=[{'role':'user','content':'x'}]
        self.assertEqual(c.prepare_completion(m,'1'*1023)['supervised_tokens'],1024)
        with self.assertRaisesRegex(ValueError,'no truncation'): c.prepare_completion(m,'1'*1024)

    def test_prompt_contract_live_limit_mutation_is_rejected(self):
        c=contract(); c.output_cap=2048
        with self.assertRaises(ValueError):
            c.prepare_completion([{'role':'user','content':'x'}],'1'*1024)

    def test_analytic_memory_is_exact_but_never_measured(self):
        cfg={'model_type':'qwen3','num_hidden_layers':40,'hidden_size':5120,'intermediate_size':17408,
             'vocab_size':151936,'num_attention_heads':40,'num_key_value_heads':8,'head_dim':128}
        inv={str(i):{'dtype':'BF16','elements':1} for i in range(443)}
        inv['0']['elements']=14768307200-442
        estimate=p.memory_estimate(cfg,inv)
        self.assertEqual(estimate['estimated_required_bytes'],60201170944)
        self.assertEqual(estimate['full_logits_loss_bytes'],4096*151936*12)
        self.assertFalse(estimate['measured']); self.assertFalse(estimate['memory_fit_guaranteed'])
        for change in ({'sequence_length':2048},{'sequence_length':True},{'adapter_rank':16},{'batch_size':2}):
            with self.subTest(change=change),self.assertRaises(ValueError): p.memory_estimate(cfg,inv,**change)

class NativeRaises:
    prompt_cap=3072
    output_cap=1024
    def generate(self,*args,**kwargs): raise RuntimeError('dispatched native failure')
    def score_completion(self,*args,**kwargs): raise RuntimeError('dispatched score failure')

class PhysicalFailureCleanup(unittest.TestCase):
    def test_generation_unknown_work_stays_charged_and_watchdog_closes(self):
        with tempfile.TemporaryDirectory() as td:
            ledger=WorkLedger(Path(td)/'ledger.jsonl'); model=TransferMeteredModel(NativeRaises(),ledger)
            with self.assertRaisesRegex(RuntimeError,'native failure'):
                model.generate([],kind='grid',seed=0,max_new_tokens=1024,deadline=time.monotonic()+30)
            self.assertEqual(ledger.used['generation_calls'],1)
            self.assertEqual(ledger.used['input_tokens'],sum(3072+i for i in range(1024)))
            self.assertEqual(ledger.used['output_tokens'],1024)
            self.assertEqual(len(ledger.pending),1)  # Unknown reservations intentionally remain held.
            self.assertEqual(json.loads((Path(td)/'active-call.json').read_text())['status'],'closed')

    def test_scoring_unknown_work_stays_charged_and_watchdog_closes(self):
        with tempfile.TemporaryDirectory() as td:
            ledger=WorkLedger(Path(td)/'ledger.jsonl'); model=TransferMeteredModel(NativeRaises(),ledger)
            with self.assertRaisesRegex(RuntimeError,'score failure'):
                model.score_completion([], '1', deadline=time.monotonic()+30)
            self.assertEqual(ledger.used['scoring_forwards'],1)
            self.assertEqual(ledger.used['input_tokens'],4096)
            self.assertEqual(len(ledger.pending),1)  # Unknown reservations intentionally remain held.
            self.assertEqual(json.loads((Path(td)/'active-call.json').read_text())['status'],'closed')

if __name__=='__main__': unittest.main(verbosity=2)
