"""Source differential and tiny actual-model method reference acceptance."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

import torch
from datasets import Dataset

from irisx.arc_nvarc_corpus import SOURCES, freeze_source_corpus, FrozenSourceSequenceStore, sha_file
from irisx.arc_nvarc_data import source_qwen_views, source_qwen_training_views
from irisx.arc_nvarc_candidates import QwenCandidateBackend, configure_candidate_backend, solve_task
from irisx.arc_nvarc_source_recipe import cut_source_dataset, SourceTextTokenizer
from irisx.arc_nvarc_training import TaskLocalAdapter, task_local_sequences, train_torch_sft, collate
from irisx.arc_nvarc_upstream import qwen_cell
from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError
from tests.nvarc_source_differential import source_text_ids
from tests import test_arc_nvarc_ml as ml_tests

TASK = {"task_id": "synthetic-method",
        "train": [{"input": [[1, 2]], "output": [[2, 1]]},
                  {"input": [[3, 4]], "output": [[4, 3]]}],
        "test": [{"input": [[5, 6]]}, {"input": [[7, 8]]}]}


class MethodStrictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.threads)

    def test_context_cut_matches_original_and_rejects_impossible_last_example(self):
        loader = qwen_cell('arc_loader.py')
        class OracleTokenizer:
            def encode(self, text):
                return source_text_ids(text)
        formatter = loader.QwenFormatter(OracleTokenizer())
        source = loader.ArcDataset(queries={'view': {'train': TASK['train'], 'test': TASK['test']}},
                                   keys=['view'])
        for name, bound in (('text', 20), ('input', 24)):
            expected = source.cut_to_len(formatter, name, bound)
            observed = cut_source_dataset(source, name=name, max_length=bound)
            self.assertEqual(expected.queries, observed.queries)
            self.assertEqual(expected.keys, observed.keys)
            for key in observed.keys:
                self.assertLessEqual(observed.get_length(key, formatter, name), bound)
        for name in ('text', 'input'):
            with self.assertRaises(ValidationError):
                cut_source_dataset(source, name=name, max_length=2)
        with self.assertRaises(ValidationError):
            cut_source_dataset(source, name='input', max_length=14)
        training = source_qwen_training_views(TASK, seed=1, color_repeats=16, max_length=20)
        self.assertEqual(128, len(training))
        self.assertTrue(all(len(x['train']) == 1 for x in training))
        for test_index in (0, 1):
            views = source_qwen_views(TASK, test_index, seed=2, color_repeats=2, max_length=24)
            self.assertEqual(16, len(views))
            self.assertTrue(all(len(x['task']['train']) == 1 for x in views))
            verification = source_qwen_views(TASK, test_index, seed=17,
                color_repeats=1, answer=[[6, 5]], max_length=14)
            self.assertEqual(8, len(verification))
            self.assertTrue(all(not x['task']['train'] for x in verification))

    def test_rank256_consumes_all_128_views_with_cosine_and_resets(self):
        from peft import get_peft_model_state_dict
        model = ml_tests.NvarcMLTests()._tiny_qwen()
        model.resize_token_embeddings(16)
        config = {'rank': 256, 'alpha': 32, 'seed': 42, 'use_rslora': True,
            'training_schedule': 'source-one-epoch', 'source_qwen': True,
            'augmentation_count': 16, 'source_augmentation_seed': 1,
            'max_sequence_length': 8192, 'learning_rate': 5e-5, 'warmup_ratio': .1,
            'maximum_optimizer_steps': 128, 'maximum_training_tokens': 1048576}
        adapter = TaskLocalAdapter(model, config)
        adapter.adapt(TASK)
        observed = adapter.last_observation
        self.assertEqual((128, 128, 13), (observed['steps'], observed['source_view_count'], observed['warmup_steps']))
        self.assertTrue(observed['complete_epoch'])
        self.assertEqual(set(range(128)), set(observed['consumed_view_indices']))
        self.assertEqual(0, observed['learning_rates_by_step'][0])
        self.assertAlmostEqual(5e-5, max(observed['learning_rates_by_step']))
        self.assertGreater(max(observed['learning_rates_by_step']), observed['learning_rates_by_step'][-1])
        self.assertTrue(all(all(group[k] for k in ('attention','delta','embedding','head'))
                            for group in observed['gradient_groups_by_step']))
        self.assertTrue(any(not torch.equal(value.cpu(), adapter.initial[key])
                            for key, value in get_peft_model_state_dict(adapter.model).items()))
        adapter.reset(clear_observation=False)
        self.assertTrue(all(torch.equal(value.cpu(), adapter.initial[key])
                            for key, value in get_peft_model_state_dict(adapter.model).items()))
        adapter.config['maximum_optimizer_steps'] = 1
        with self.assertRaises(ValidationError):
            adapter.adapt(TASK)

    def test_actual_generation_context_and_eight_view_verification_match_source(self):
        model = ml_tests.NvarcMLTests()._tiny_qwen()
        model.resize_token_embeddings(16)
        model.eval()
        backend = QwenCandidateBackend(model, dfs_max_expansions=4)
        config = {'augmentation':'source-qwen','representation':'source-qwen',
            'ranking':'source-kgmon','source_context_tokens':28,'maximum_new_tokens':4,
            'maximum_calls_per_task':4,'beams_per_call':2,'seed':2,'color_repeats':2}
        results = solve_task(TASK, backend, config)
        self.assertEqual(2, len(results))
        self.assertEqual(4, sum(len(row['generation_observations']) for row in results))
        self.assertTrue(all(obs['query_tokens'] <= 24 for row in results
                            for obs in row['generation_observations']))
        # Small verification context permits removing all demos because get()
        # has an explicit candidate reply; compare logits from the source text.
        configure_candidate_backend(backend, {**config, 'source_context_tokens':18})
        answer = [[6, 5]]
        observed = backend.verify(TASK, 1, answer)
        loader = qwen_cell('arc_loader.py')
        source = loader.ArcDataset(queries={'synthetic-method_1':{
            'train':TASK['train'],'test':[TASK['test'][1]]}},
            replies={'synthetic-method_1':[answer]})
        class OracleTokenizer:
            def encode(self, text):
                return source_text_ids(text)
        formatter = loader.QwenFormatter(OracleTokenizer())
        source = source.augment(n=1,shfl_keys=True,seed=17).cut_to_len(formatter,'input',14)
        losses = []
        with torch.inference_mode():
            for key in sorted(source.keys):
                text = source.get(key,formatter)
                prefix, target = source_text_ids(text['input']), source_text_ids(text['reply'])
                logits = model(input_ids=torch.tensor([prefix+target]),use_cache=False).logits
                losses.append(torch.nn.functional.cross_entropy(
                    logits[0,len(prefix)-1:-1,:],torch.tensor(target),reduction='sum').item())
        self.assertAlmostEqual(sum(losses)/len(losses),observed,places=5)

    def _corpus(self, root):
        sources = []
        for index, source_id in enumerate(SOURCES):
            dataset = root / source_id
            messages = [{'role': 'user', 'content': '1'},
                        {'role': 'assistant', 'content': '2' * (index + 1)}]
            Dataset.from_list([{'puzzle_name': source_id + '-view', 'messages': messages}]).save_to_disk(dataset)
            lineage = root / (source_id + '.jsonl')
            lineage.write_bytes(canonical_bytes({'puzzle_name': source_id + '-view',
                'parent_id': source_id + '-parent'}, newline=True))
            sources.append({'source_id': source_id, 'dataset_path': source_id,
                'records': 1, 'exposure': 'public-training-only', 'lineage_path': lineage.name,
                'lineage_sha256': sha_file(lineage), 'members': [
                    {'path': p.relative_to(dataset).as_posix(), 'sha256': sha_file(p)}
                    for p in sorted(dataset.rglob('*')) if p.is_file()]})
        spec = {'format': 'irisx/nvarc-source-corpus-spec-v1', 'policy': 'clean-research',
                'material_class': 'synthetic-fixture',
                'excluded_parent_ids': ['development-parent'], 'max_sequence_length': 128,
                'sources': sources}
        path = root / 'spec.json'
        path.write_bytes(canonical_bytes(spec, newline=True))
        return path, spec

    def test_six_source_store_token_weighted_gradient_and_exact_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec_path, spec = self._corpus(root)
            manifest = freeze_source_corpus(spec_path, root / 'frozen', shard_records=2)
            store = FrozenSourceSequenceStore(root / 'frozen')
            self.assertEqual(6, len(store))
            self.assertEqual('synthetic-fixture', store.manifest['material_class'])
            self.assertEqual({x:1 for x in SOURCES}, manifest['source_counts'])
            # Rehashing a corrupted mask cannot make it assistant-only again.
            shard_path = root/'frozen'/'sequences-00000.jsonl'
            original_shard = shard_path.read_bytes()
            rows = [json.loads(line) for line in original_shard.splitlines()]
            rows[0]['labels'][3] = rows[0]['input_ids'][3]
            shard_path.write_bytes(b''.join(canonical_bytes(row,newline=True) for row in rows))
            altered = copy.deepcopy(manifest)
            altered['shards'][0]['sha256'] = sha_file(shard_path)
            (root/'frozen'/'manifest.json').write_bytes(canonical_bytes(altered,newline=True))
            with self.assertRaises(ValidationError):
                FrozenSourceSequenceStore(root/'frozen')
            shard_path.write_bytes(original_shard)
            (root/'frozen'/'manifest.json').write_bytes(canonical_bytes(manifest,newline=True))
            self.assertEqual(6,len(FrozenSourceSequenceStore(root/'frozen')))
            torch.manual_seed(24)
            model = ml_tests.NvarcMLTests()._tiny_qwen()
            model.resize_token_embeddings(16)
            continuous_model, oracle = copy.deepcopy(model), copy.deepcopy(model)
            config = {'mode':'full-sft','packing':False,'device':'cpu','seed':24,
                'learning_rate':1e-4,'minimum_learning_rate':1e-7,'warmup_initial_learning_rate':1e-4,
                'warmup_steps':0,'schedule_steps':2,'scheduler':'source-linear',
                'optimizer_betas':[.9,.98],'optimizer_eps':1e-8,'weight_decay':.1,
                'clip_grad_norm':.5,'loss_reduction':'supervised-token-mean',
                'max_steps':2,'maximum_training_tokens':1000,'max_sequence_length':128,
                'gradient_accumulation':2,'checkpoint_every':1}
            # Independent oracle concatenates token losses across variable-length
            # samples, rather than reusing the trainer's microbatch weighting.
            optimizer = torch.optim.AdamW(oracle.parameters(), lr=1e-4, betas=(.9,.98), weight_decay=.1)
            logits, labels = [], []
            oracle.train()
            for index in (0, 1):
                batch = {k:torch.tensor(v) for k,v in collate([store[index]],128).items()}
                logits.append(oracle(**batch, use_cache=False).logits[:,:-1,:].reshape(-1,16))
                labels.append(batch['labels'][:,1:].reshape(-1))
            torch.nn.functional.cross_entropy(torch.cat(logits), torch.cat(labels), ignore_index=-100).backward()
            torch.nn.utils.clip_grad_norm_(oracle.parameters(), .5)
            optimizer.step()
            first = train_torch_sft(model,store,root/'resumed',config,
                model_identity_digest='sha256:'+'1'*64,stop_after_steps=1)
            for name, value in model.state_dict().items():
                torch.testing.assert_close(value, oracle.state_dict()[name], atol=3e-6, rtol=1e-5)
            train_torch_sft(model,store,root/'resumed',config,model_identity_digest='sha256:'+'1'*64,resume=True)
            train_torch_sft(continuous_model,store,root/'continuous',config,model_identity_digest='sha256:'+'1'*64)
            self.assertEqual(1,first['steps'])
            for name,value in model.state_dict().items():
                self.assertTrue(torch.equal(value,continuous_model.state_dict()[name]),name)
            spec['excluded_parent_ids'].append('mini-parent')
            spec_path.write_bytes(canonical_bytes(spec,newline=True))
            with self.assertRaises(ValidationError):
                freeze_source_corpus(spec_path,root/'excluded')
            (root/'frozen'/'sequences-00000.jsonl').write_text('{}\n',encoding='utf-8')
            with self.assertRaises(ValidationError):
                FrozenSourceSequenceStore(root/'frozen')


if __name__ == '__main__':
    unittest.main()
