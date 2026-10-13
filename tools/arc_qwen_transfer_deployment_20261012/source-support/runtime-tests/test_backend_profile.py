"""Offline successor bounds; stdlib tests make no native/GPU-fit claims."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.arc_qwen_transfer_20261012 import model_profile as p
from tools.arc_qwen_transfer_20261012.backend import TransferMeteredModel, TransferTrainer, create_backend
from tools.arc_qwen_transfer_20261012.decoder import TransferPromptContract, TransferModel, CACHE_POLICY
from tools.arc_learning_agent_20261011.qwen14b_contract import NativePromptContract, canonical
from tools.arc_learning_agent_20261011.qwen14b_training import Qwen14BTrainer
from tools.arc_learning_agent_20261011.metering import MeteredTrainer
from tools.arc_learning_agent_20261011.budget import WorkLedger

ROOT = Path(__file__).resolve().parents[1]


def config(**changes):
    return {'model_key': p.MODEL_KEY, 'profile_id': p.PROFILE_ID,
            'material_addendum_sha256': p.MATERIAL_ADDENDUM_SHA256, 'tiny_cpu': True, **changes}


class SyntheticTokenizer:
    """Explicit synthetic text fixture; cannot impersonate native tokenizers."""
    eos_token_id, eos_token = 151645, '<|im_end|>'
    all_special_ids = [151645, 151643]
    chat_template = 'synthetic-character-template-v1'
    def get_vocab(self):
        return {**{chr(i): i for i in range(128)}, self.eos_token: self.eos_token_id,
                '<|endoftext|>': 151643}
    def encode(self, text, add_special_tokens=False):
        out = []
        while text:
            if text.startswith(self.eos_token):
                out.append(self.eos_token_id); text = text[len(self.eos_token):]
            else:
                out.append(ord(text[0])); text = text[1:]
        return out
    def decode(self, ids, **kwargs):
        return ''.join(self.eos_token if i == self.eos_token_id else chr(i) for i in ids)
    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt, enable_thinking):
        if add_generation_prompt:
            return messages[-1]['content']
        return messages[-2]['content'] + messages[-1]['content'] + self.eos_token + '\n'


def contract():
    return TransferPromptContract(SyntheticTokenizer(), vocab_size=p.VOCAB_SIZE,
                                  eos_ids=p.EOS_IDS, synthetic=True)


class ProfileTests(unittest.TestCase):
    def test_profile_is_distinct_and_unmeasured(self):
        value = p.profile()
        self.assertEqual((value['context_limit'], value['prompt_cap'], value['output_cap']), (4096, 3072, 1024))
        self.assertFalse(value['production_admitted'])
        self.assertFalse(value['g4_fit_measured'])
        self.assertEqual(value['full_vocabulary_rows'], 151936)

    def test_exact_material_addendum_digest(self):
        self.assertEqual(hashlib.sha256(canonical(p.material_addendum())).hexdigest(), p.MATERIAL_ADDENDUM_SHA256)
        copy = p.material_addendum(); copy['successor_profile']['context_limit'] = 8192
        self.assertEqual(p.material_addendum()['successor_profile']['context_limit'], 4096)

    def test_wrong_model_or_profile_or_addendum_rejected(self):
        for override in ({'profile_id': 'old'}, {'model_key': 'granite'}, {'material_addendum_sha256': '0' * 64}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                p.validate_model_config(config(**override))

    def test_changed_bound_or_precision_rejected(self):
        for key, value in [('context_limit',2048), ('context_limit',8192), ('context_limit',True),
                           ('prompt_cap',3073), ('output_cap',1025), ('tensor_parallel_size',4), ('precision','fp8')]:
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                p.validate_model_config(config(**{key:value}))

    def test_pretrained_default_off(self):
        with self.assertRaises(ValueError):
            p.select_deployment(config(tiny_cpu=False))

    def test_exact_material_selection_never_claims_measurement(self):
        c=config(tiny_cpu=False, enabled=True, reviewed_deployment_id=p.DEPLOYMENT_ID,
                 contract_path=str(ROOT/'materials/qwen14b/material-contract.json'))
        result=p.select_deployment(c)
        self.assertFalse(result['context4096_measured'])
        self.assertFalse(result['production_admitted'])

    def test_exact4096_memory_bound(self):
        cfg=json.loads((ROOT/'materials/qwen14b/hf-overlay/config.json').read_bytes())
        inv=json.loads((ROOT/'materials/qwen14b/expected-tensor-inventory.json').read_bytes())['tensors']
        estimate=p.memory_estimate(cfg,inv)
        self.assertEqual(estimate['estimated_required_bytes'],60201170944)
        self.assertEqual(estimate['full_logits_loss_bytes'],4096*151936*12)
        self.assertFalse(estimate['measured'])
        with self.assertRaises(ValueError):p.memory_estimate(cfg,inv,sequence_length=2048)
        inv.pop(next(iter(inv)))
        with self.assertRaises(ValueError):p.memory_estimate(cfg,inv)

    def test_explicit_clock_and_cache_overrides(self):
        overrides=p.material_addendum()['overrides']
        self.assertEqual(overrides['probe_bounds.maximum_probe_seconds'],{'before':10800,'after':43200})
        self.assertIn('exact unconstrained argmax',overrides['hardware.cache_tolerance_scope']['after'])
        self.assertEqual(p.material_addendum()['calibration']['atol'],0.01)

    def test_task_digest_matches_inherited_training(self):
        from tools.arc_next_models import digest as inherited_digest
        records=[{'scope':'demo-only'}]
        trainer=TransferTrainer.__new__(TransferTrainer)
        trainer._task_id='task';trainer._task_seed=19;trainer.config={'task_augmentations':1}
        def train(rows,**kwargs):
            self.assertEqual(trainer._task_records_digest,inherited_digest(rows));return {'status':'complete'}
        trainer.train=train;trainer.end_task=lambda:None
        with patch('tools.arc_qwen_transfer_20261012.data.build_task_records',return_value=records), patch('tools.arc_qwen_transfer_20261012.data.validate_task_records'):
            self.assertEqual(trainer.adapt_task('task',[],max_steps=1,deadline=10)['task_id'],'task')

    def test_no_unverified_load_evidence(self):
        with self.assertRaises(ValueError):p.consume_load_evidence(SyntheticTokenizer(),SyntheticTokenizer(),config())


class PromptTests(unittest.TestCase):
    def test_complete4096_row_and_causal_mask(self):
        c=contract(); row=c.prepare_completion([{'role':'user','content':'x'*3072}],'1'*1023)
        self.assertEqual(row['input_tokens'],4096)
        self.assertEqual(row['supervised_tokens'],1024)
        self.assertEqual(row['labels'],[-100]*3072+row['input_ids'][3072:])
        self.assertEqual(c.validate_prepared(row),row)
        row['labels'][0]=1
        with self.assertRaises(ValueError):c.validate_prepared(row)

    def test_mutated_live_contract_bounds_rejected(self):
        for key,value in [('context_limit',8192),('output_cap',2048)]:
            c=contract();setattr(c,key,value)
            with self.assertRaises(ValueError):c.prepare_completion([{'role':'user','content':'x'}],'1'*1024)

    def test_output1025_excluded_whole(self):
        with self.assertRaises(ValueError):contract().prepare_completion([{'role':'user','content':'x'}],'1'*1024)

    def test_prompt3073_excluded_whole(self):
        with self.assertRaises(ValueError):contract().prompt([{'role':'user','content':'x'*3073}])

    def test_largest_grid930_including_eos_fits(self):
        text='\n'.join('1234567890'*3 for _ in range(30))
        row=contract().prepare_completion([{'role':'user','content':'x'}],text)
        self.assertEqual(row['supervised_tokens'],930)

    def test_old_contract_remains2048(self):
        with self.assertRaises(ValueError):
            NativePromptContract(SyntheticTokenizer(),vocab_size=151936,eos_ids=p.EOS_IDS,
                                 context_limit=4096,output_cap=1024,synthetic=True)

    def test_old_prepared_cannot_cross_successor_identity(self):
        tok=SyntheticTokenizer()
        old=NativePromptContract(tok,vocab_size=151936,eos_ids=p.EOS_IDS,synthetic=True)
        row=old.prepare_completion([{'role':'user','content':'x'}],'1')
        with self.assertRaises(ValueError):contract().validate_prepared(row)

    def test_calibration_and_state_methods_preserved(self):
        self.assertEqual(CACHE_POLICY['length_ladder'],[128,512,2048,4096])
        self.assertIs(TransferTrainer.restore_training_state,Qwen14BTrainer.restore_training_state)
        self.assertIs(TransferTrainer.load_checkpoint,Qwen14BTrainer.load_checkpoint)
        bare=TransferModel.__new__(TransferModel);bare._calibration_receipt=None
        with self.assertRaises(ValueError):bare.lock_decoder_policy({'selected_mode':'cached'})


class MeterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.ledger=WorkLedger(Path(self.temp.name)/'physical.jsonl')
    def native(self, **methods):
        return SimpleNamespace(prompt_cap=3072,output_cap=1024,**methods)
    def test_actual_generation_forward_tokens(self):
        def generate(*a,**k):
            return {'valid':True,'dispatched':True,'forward_input_tokens':4095,'output_tokens':1024}
        model=TransferMeteredModel(self.native(generate=generate),self.ledger)
        model.generate([],kind='grid',seed=0,max_new_tokens=1024,deadline=time.monotonic()+60)
        self.assertEqual(self.ledger.used['input_tokens'],4095)
        self.assertEqual(self.ledger.used['output_tokens'],1024)
    def test_unknown_generation_charges_reservation_and_closes_marker(self):
        def generate(*a,**k):raise RuntimeError('injected')
        model=TransferMeteredModel(self.native(generate=generate),self.ledger)
        with self.assertRaises(RuntimeError):model.generate([],kind='grid',seed=0,max_new_tokens=1024,deadline=time.monotonic()+60)
        self.assertEqual(self.ledger.used['input_tokens'],sum(3072+i for i in range(1024)))
        self.assertEqual(json.loads((Path(self.temp.name)/'active-call.json').read_bytes())['status'],'closed')
    def test_score4096_reservation_and_failed_cleanup(self):
        def score(*a,**k):raise RuntimeError('injected')
        model=TransferMeteredModel(self.native(score_completion=score),self.ledger)
        with self.assertRaises(RuntimeError):model.score_completion([], 'x',deadline=time.monotonic()+60)
        self.assertEqual(self.ledger.used['input_tokens'],4096)
        self.assertEqual(json.loads((Path(self.temp.name)/'active-call.json').read_bytes())['status'],'closed')
    def test_training_reserves4096(self):
        def train(*a,**k):raise RuntimeError('injected')
        metered=MeteredTrainer(SimpleNamespace(train=train),self.ledger,max_sequence_tokens=4096)
        with self.assertRaises(RuntimeError):metered.train([],max_steps=2)
        self.assertEqual(self.ledger.used['input_tokens'],8192)
        self.assertEqual(self.ledger.used['training_steps'],2)
    def test_factory_sets4096_and_closes_on_error(self):
        native=self.native(close=lambda:None)
        with patch('tools.arc_qwen_transfer_20261012.backend.TransferModel.from_config',return_value=native), patch('tools.arc_qwen_transfer_20261012.backend.TransferTrainer',return_value=object()):
            model,trainer=create_backend(config(),{},ledger=self.ledger)
            self.assertEqual(trainer.max_sequence_tokens,4096)
        called=[];native.close=lambda:called.append(True)
        with patch('tools.arc_qwen_transfer_20261012.backend.TransferModel.from_config',return_value=native), patch('tools.arc_qwen_transfer_20261012.backend.TransferTrainer',side_effect=ValueError('injected')):
            with self.assertRaises(ValueError):create_backend(config(),{},ledger=self.ledger)
        self.assertEqual(called,[True])


@unittest.skipUnless(all(importlib.util.find_spec(x) is not None for x in ('torch','transformers','peft','tokenizers')),
                     'optional real CPU native dependencies absent')
class NativeCPUTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        torch.set_num_threads(2)
        cls.temp=tempfile.TemporaryDirectory()
        cls.ledger=WorkLedger(Path(cls.temp.name)/'native.jsonl')
        cls.model,cls.trainer=create_backend(config(tokenizer_path=str(ROOT/'materials/qwen14b/hf-overlay'),
            tiny_hidden_size=8,seed=1917,do_sample=False),{'seed':1917},ledger=cls.ledger)
    @classmethod
    def tearDownClass(cls):
        cls.model.close();cls.temp.cleanup()
    def test_native_four_lengths_and930_grid(self):
        from tools.arc_qwen_transfer_20261012.decoder import prepare_length_control
        self.assertEqual([prepare_length_control(self.model,n)['input_tokens'] for n in p.LENGTH_LADDER],list(p.LENGTH_LADDER))
        text='\n'.join('1234567890'*3 for _ in range(30))
        self.assertEqual(self.model.prepare_completion([{'role':'user','content':'Return the grid.'}],text)['completion_tokens'],930)
    def test_native_peft_bf16_full_head(self):
        import torch
        self.assertEqual(self.model.vocab_size,151936)
        self.assertEqual(len(self.trainer.target_names),7)
        self.assertTrue(all(x.dtype==torch.bfloat16 for x in self.model.model.parameters() if not x.requires_grad))
        self.assertTrue(all(x.dtype==torch.float32 for x in self.trainer.parameters.values()))
    def test_native_finite_update_complete_restore(self):
        from tools.arc_qwen_transfer_20261012.decoder import prepare_length_control
        row=prepare_length_control(self.model,128)
        snap=self.trainer.snapshot_training_state('native-test-start')
        try:
            self.ledger.reserve('native-unit-update',{'training_steps':1,'input_tokens':128})
            raw=self.trainer.trainer;raw._make_optimizer();update=raw._step(row)
            self.ledger.complete('native-unit-update',{'training_steps':1,'input_tokens':128})
            self.assertTrue(update['finite_gradients']);self.assertGreater(update['changed_adapter_tensors'],0)
        finally:self.trainer.restore_training_state(snap)
        check=self.trainer.snapshot_training_state('native-test-restored')
        try:self.assertEqual(check['state_sha256'],snap['state_sha256'])
        finally:self.trainer.release_training_state(check);self.trainer.release_training_state(snap)


if __name__=='__main__':unittest.main()
