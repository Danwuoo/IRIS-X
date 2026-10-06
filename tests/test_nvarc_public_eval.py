"""Public lifecycle tests: fixtures/tiny CPU models never establish GPU parity."""
import copy
from contextlib import contextmanager, redirect_stdout
import io
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
import zlib
import base64
import ast

from tools import nvarc_public_eval as core
from tools import nvarc_public_eval_runtime as runtime
from tools import nvarc_public_eval_parent as parent
from tools import stage_nvarc_public_eval as stage
from tools import score_nvarc_public_eval as scorer
from tools.nvarc_native_multitask import digest, write


@contextmanager
def fixture_modules(values):
    # Restore only our injected aliases, preserving PyTorch's lazy C++ registrations.
    old = {k: sys.modules.get(k) for k in values}; sys.modules.update(values)
    try: yield
    finally:
        for key, value in old.items():
            if value is None: sys.modules.pop(key, None)
            else: sys.modules[key] = value


def fixture(profile='BASE-30'):
    data = {'a': {'train': [{'input': [[1]], 'output': [[2]]}], 'test': [{'input': [[3]]}, {'input': [[4]]}]},
            'b': {'train': [{'input': [[5]], 'output': [[6]]}], 'test': [{'input': [[7]]}]}}
    plan = {'format': core.FORMAT, 'profile': profile, 'run_id': core.RUNS[profile],
        'approved': True, 'owner_editor_only': True, 'agent_execution_authorized': False,
        'kernel_execution_type': 'QUICK_SAVE', 'owner_decision': 'Decision 0060',
        'local_fixture': True, 'maximum_paid_usd': 0, 'maximum_teacher_calls': 0,
        'parallel_workers': 4, 'per_test_seconds': 30,
        'maximum_notebook_wall_seconds': 3600 if profile == 'BASE-30' else 14400,
        'startup_seconds': 900, 'export_reserve_seconds': 300,
        'challenges_digest': digest(data), 'task_counts': {'a': 2, 'b': 1},
        'model_material_digest': 'fixture-tiny-cpu-not-sft139', 'challenges_sha256': core.INPUT_SHA,
        'download_archive': core.RUNS[profile]+'.zip',
        'task_materials': {k: {'training_input_tokens': 100} for k in data}}
    return plan, data


def record(plan, data, key, candidate=None):
    tests = core.empty_tests(len(data[key]['test']))
    if candidate is not None:
        tests[0].update(attempts=[candidate], ranked_grids=[candidate], missing_attempts=1,
            status='missing-candidate', termination_reason='all_source_batches_completed',
            candidate_evidence={digest(candidate): {'scores': [1.]*8, 'rows': [
                {'source_view': key+'_0.r'+str(i), 'query_digest': digest([1]), 'answer_digest': digest([2]), 'score': 1.}
                for i in range(8)]}})
    return {'binding': core.task_binding(plan, data, key), 'baseline_verified': True,
            'training_complete': plan['profile'] == 'TTT128-30', 'training_steps': 128 if plan['profile'] == 'TTT128-30' else 0,
            'tests': tests, 'outcome': 'partial', 'reset_verified': None, 'timings': {}}


class PublicCoreTests(unittest.TestCase):
    def test_complete_denominator_and_incremental_survival(self):
        plan, data = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            store = core.ResultStore(Path(tmp), plan, data, allow_fixture=True)
            first = record(plan, data, 'a', [[2]]); store.commit(first)
            later = copy.deepcopy(first); later['outcome'] = 'failed'
            later['tests'][1]['termination_reason'] = 'worker_crash'; store.commit(later)
            saved = json.loads((Path(tmp)/'submission.json').read_bytes())
            self.assertEqual(set(saved), {'a', 'b'}); self.assertEqual(sum(map(len, saved.values())), 3)
            self.assertEqual(saved['a'][0], {'attempt_1': [[2]], 'attempt_2': [[2]]})
            self.assertEqual(saved['a'][1]['attempt_1'], [[0]])
            self.assertEqual(json.loads((Path(tmp)/'coverage.json').read_bytes())['tests_with_model_candidates'], 1)
            lost = copy.deepcopy(first); lost['tests'][0] = core.empty_tests(1)[0]
            with self.assertRaisesRegex(RuntimeError, 'disappear'): store.commit(lost)

    def test_truth_foreign_identity_incomplete_ttt_and_partial_verifier_rejected(self):
        plan, data = fixture('TTT128-30'); good = record(plan, data, 'a', [[2]])
        for mutation in ('truth', 'profile', 'epoch', 'views', 'score'):
            bad = copy.deepcopy(good)
            if mutation == 'truth': bad['tests'][0]['answer_key'] = [[2]]
            if mutation == 'profile': bad['binding']['profile'] = 'BASE-30'
            if mutation == 'epoch': bad['training_steps'] = 127
            proof = bad['tests'][0]['candidate_evidence'][digest([[2]])]
            if mutation == 'views': proof['rows'].pop()
            if mutation == 'score': proof['scores'][0] = 2.
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError): core.validate_record(plan, data, bad)

    def test_test_zero_deadline_does_not_skip_test_one(self):
        plan, data = fixture(); rec = record(plan, data, 'a'); seen = []; commits = []
        def solve(i, deadline):
            seen.append((i, deadline))
            if not i: raise runtime.InferenceLimitReached('inference_deadline')
            t = core.empty_tests(1)[0]; t.update(test_index=1, status='missing-candidate', termination_reason='all_source_batches_completed')
            return t
        runtime.solve_all_tests(plan, data, 'a', solve, lambda r: commits.append(copy.deepcopy(r)), rec,
            now=lambda: 100, deadline=300)
        self.assertEqual(seen, [(0, 130), (1, 130)]); self.assertEqual(len(commits), 2)
        self.assertEqual(rec['tests'][0]['termination_reason'], 'inference_deadline')

    def test_source_sensitive_metrics_keep_missing_and_filler_separate(self):
        plan, data = fixture(); records = {'a': record(plan, data, 'a', [[2]])}
        result = scorer.score(plan, data, records, {'a': [[[2]], [[0]]], 'b': [[[8]]]}, allow_fixture=True)
        self.assertEqual(result['test_pass2'], 1/3); self.assertEqual(result['raw_submission_test_pass2'], 2/3)
        self.assertEqual(result['task_average_pass2'], .25); self.assertEqual(result['tasks_all_tests_pass2'], 0)
        self.assertEqual(result['model_test_coverage'], 1/3)

    def test_zip_is_run_named_closed_and_digest_verified(self):
        plan, data = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'work'; root.mkdir(); write(root/'plan.json', plan); write(root/'challenges.json', data)
            core.ResultStore(root, plan, data, allow_fixture=True)
            worker = root/'workers/0'; worker.mkdir(parents=True)
            write(worker/'ready.json', {'rank': 0, 'fixture': True})
            (root/'dependency-setup.log').write_text('fixture setup diagnostics', encoding='utf-8')
            destination = Path(tmp)/plan['download_archive']; core.write_archive(root, destination, plan)
            manifest, payloads = core.read_archive(destination, expected_run=plan['run_id'])
            self.assertEqual(manifest['plan_digest'], digest(plan)); self.assertIn('submission.json', payloads)
            self.assertIn('workers/0/ready.json', payloads)
            self.assertIn('parent-dependency-setup.log.tail.json', payloads)
            with self.assertRaises(RuntimeError): core.write_archive(root, Path(tmp)/'結果.zip', plan)
            broken = Path(tmp)/'broken.zip'
            with zipfile.ZipFile(destination) as src, zipfile.ZipFile(broken, 'w') as dst:
                for name in src.namelist(): dst.writestr(name, b'changed' if name == 'submission.json' else src.read(name))
            with self.assertRaisesRegex(RuntimeError, 'digest'): core.read_archive(broken)

    def test_process_mailboxes_single_dispatch_and_cleanup(self):
        plan, data = fixture()
        body = '''import argparse,json,time
from pathlib import Path
p=argparse.ArgumentParser()
for k in ('root','model','dependency','rank','deadline','parent-pid'):p.add_argument('--'+k)
a=p.parse_args();root=Path(a.root);rank=int(a.rank);d=root/'workers'/str(rank)
def save(path,value):
 t=path.with_suffix('.tmp');t.write_text(json.dumps(value));t.replace(path)
plan=json.loads((root/'plan.json').read_bytes());ch=json.loads((root/'challenges.json').read_bytes())
import sys
sys.path.insert(0,plan['fixture_repository'])
from tools.nvarc_public_eval import task_binding,empty_tests
save(d/'ready.json',{'rank':rank,'uuid':'fixture-'+str(rank),'model_material_digest':plan['model_material_digest']})
last=0
while True:
 path=d/'job.json'
 if not path.exists():time.sleep(.02);continue
 job=json.loads(path.read_bytes())
 if job.get('stop'):break
 if job['sequence']<=last:time.sleep(.02);continue
 last=job['sequence'];key=job['task_id'];out=root/'tasks'/key;out.mkdir()
 tests=empty_tests(len(ch[key]['test']))
 for t in tests:t.update(status='missing-candidate',termination_reason='all_source_batches_completed')
 save(out/'checkpoint.json',{'binding':task_binding(plan,ch,key),'baseline_verified':True,'training_complete':False,
  'training_steps':0,'tests':tests,'outcome':'complete','timings':{},'reset_verified':True})
 save(d/'done.json',{'sequence':last,'task_id':key,'outcome':'complete','retired':False})
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan['fixture_repository'] = str(Path(__file__).resolve().parents[1])
            write(root/'plan.json', plan); write(root/'challenges.json', data)
            script = root/'fixture_worker.py'; script.write_text(body, encoding='utf-8')
            store = core.ResultStore(root, plan, data, allow_fixture=True); processes = []
            def launch(*a, **kw):
                proc = subprocess.Popen(*a, **kw); processes.append(proc); return proc
            result = parent.run_workers(root, plan, data, root, root,
                [{'uuid': 'fixture-'+str(i)} for i in range(4)], store, time.monotonic(),
                launch=launch, worker_command=[sys.executable, str(script)])
            self.assertEqual(result['dispatched_tasks'], 2); self.assertEqual(result['finished_tasks'], 2)
            self.assertEqual(result['worker_failures'], []); self.assertTrue(all(p.poll() is not None for p in processes))
            self.assertEqual(set(store.records), {'a', 'b'})


try:
    import numpy as np
    import torch
    from tokenizers import Tokenizer
    HAS_ML = stage.INPUT.is_file()
except ImportError:
    HAS_ML = False


@unittest.skipUnless(HAS_ML, 'optional cached source/tokenizer and tiny CPU runtime')
class PublicTinySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.root = Path(cls.temp.name)
        cls.plan, cls.raw, cls.notebook, cls.meta = stage.construct('BASE-30', '0'*40)
        for name, key in stage.FILES.items():
            path = cls.root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(cls.raw[key])
        from tools.nvarc_native_solve_runtime import load_sources
        cls.loader, cls.solver, cls.decoder = load_sources(cls.root, torch, np)
        tokpath = Path(__file__).resolve().parents[1]/'.irisx/nvarc-original/materials/qwen3-published-sft139-20261002-001/model/tokenizer.json'
        tok = Tokenizer.from_file(str(tokpath))
        class Tokens:
            def encode(self, text): return tok.encode(text).ids
            def decode(self, ids): return tok.decode(ids, skip_special_tokens=False)
        cls.tokenizer = Tokens(); cls.threads = torch.get_num_threads(); torch.set_num_threads(1)
        import importlib.util
        spec = importlib.util.spec_from_file_location('public_fixture_budget', cls.root/'nvarc_native_ttt_budget.py')
        cls.budget_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.budget_module)
        spec = importlib.util.spec_from_file_location('public_fixture_helpers', cls.root/'inspection_helpers.py')
        cls.helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.helper)

    @classmethod
    def tearDownClass(cls): torch.set_num_threads(cls.threads); cls.temp.cleanup()

    def engine(self, plan, *, fail_after=None):
        class Tiny(torch.nn.Module):
            def __init__(self):
                super().__init__(); self.embedding = torch.nn.Embedding(16, 8); self.head = torch.nn.Linear(8, 16)
            @property
            def device(self): return self.embedding.weight.device
            def forward(self, input_ids, labels=None, **kwargs):
                logits = self.head(self.embedding(input_ids))
                if labels is not None:
                    return {'loss': torch.nn.functional.cross_entropy(logits[:, :-1].reshape(-1, 16), labels[:, 1:].reshape(-1), ignore_index=-100)}
                return SimpleNamespace(logits=logits, past_key_values=object())
        torch.manual_seed(909); model = Tiny(); optimizer = torch.optim.AdamW(model.parameters(), lr=.06)
        for _ in range(120):
            optimizer.zero_grad(); logits = model(torch.tensor([[10, 0]])).logits
            torch.nn.functional.cross_entropy(logits.reshape(-1, 16), torch.tensor([0, 15])).backward(); optimizer.step()
        owner = self
        class Engine(runtime.NativeEngine):
            def __init__(self): pass
            def trainer(self, texts, rows, output):
                engine = self
                class Trainer:
                    def __init__(self):
                        self.optimizer = self.lr_scheduler = None
                        self.accelerator = SimpleNamespace(_optimizers=[], _schedulers=[], unwrap_model=lambda m, **k: m)
                        self.args = SimpleNamespace(); self.state = SimpleNamespace(global_step=0, epoch=0)
                    def training_step(self, ids, labels):
                        if fail_after is not None and self.state.global_step == fail_after: raise RuntimeError('planned tiny fault')
                        out = engine.model(input_ids=ids, labels=labels); out['loss'].backward(); return out['loss']
                    def train(self):
                        self.optimizer = torch.optim.AdamW(engine.model.parameters(), lr=plan['native_source_learning_rates'][0], weight_decay=0)
                        self.lr_scheduler = object(); self.accelerator._optimizers.append(self.optimizer)
                        self.accelerator._schedulers.append(self.lr_scheduler)
                        for i, text in enumerate(texts):
                            ids = engine.tokenizer.encode(text['text']); labels = [-100]*len(ids)
                            starts = sorted(n for n, t in enumerate(ids) if t in (11, 12)); ends = [n for n, t in enumerate(ids) if t == 15]
                            for j, (start, end) in enumerate(zip(starts, ends)):
                                if j % 2: labels[start+2:end+1] = ids[start+2:end+1]
                            self.optimizer.zero_grad(set_to_none=True)
                            self.training_step(torch.tensor([ids]), torch.tensor([labels]))
                            torch.nn.utils.clip_grad_norm_(engine.model.parameters(), 1.)
                            for group in self.optimizer.param_groups: group['lr'] = plan['native_source_learning_rates'][i]
                            self.optimizer.step(); self.state.global_step += 1
                        self.state.epoch = 1
                return Trainer()
        engine = Engine(); engine.model = model; engine.torch = torch; engine.np = np
        engine.loader, engine.solver, engine.decoder, engine.tokenizer = self.loader, self.solver, self.decoder, self.tokenizer
        engine.get_state = lambda m, **kw: m.state_dict(); engine.set_state = lambda m, values, **kw: m.load_state_dict(values)
        engine.defaults = {k: v.detach().clone() for k, v in model.state_dict().items()}
        engine.tensor_inventory = self.helper.tensor_inventory; engine.baseline = engine.inventory()
        engine.fast = SimpleNamespace(for_inference=lambda m: m.eval()); engine.dependency = self.root
        from tools.nvarc_native_solve_runtime import cache_controls
        engine.initial_control = cache_controls(engine.adapter(lambda *_a, **_k: None))
        return engine

    def test_real_source_base_generation_and_eight_view_binding_without_logits_dump(self):
        plan, data = fixture(); engine = self.engine(plan)
        with tempfile.TemporaryDirectory() as tmp:
            rec, retired = runtime.run_one_task(engine, plan, data, 'a', Path(tmp)/'a', time.time()+600)
            self.assertFalse(retired); self.assertTrue(rec['reset_verified'])
            self.assertTrue(all(t['ranked_grids'] for t in rec['tests']))
            self.assertTrue(all(len(p['rows']) == 8 for t in rec['tests'] for p in t['candidate_evidence'].values()))
            self.assertEqual(rec['training_steps'], 0); self.assertEqual(engine.inventory(), engine.baseline)

    def test_verification_uses_reserved_tail_with_one_shared_final_deadline(self):
        plan, _ = fixture(); engine = self.engine(plan); adapter = engine.adapter(lambda *_a, **_k: None)
        rows = [{'source_view': 'a_0.r'+str(i), 'query_ids': [14, 11, 10, 1, 15, 14, 12, 10], 'answer_ids': [2, 15]} for i in range(4)]
        adapter.verification_rows = rows; adapter.generation_deadline = time.time()-1
        adapter.verification_deadline = time.time()+30
        with torch.inference_mode(), adapter.scope('verification'):
            value = adapter(input_ids=torch.tensor([r['query_ids']+r['answer_ids'] for r in rows]), use_cache=True)
        self.assertEqual(len(adapter.observed[1]), 4)
        with torch.inference_mode(), adapter.scope('generation'), self.assertRaises(runtime.InferenceLimitReached):
            adapter(input_ids=torch.tensor([[10]]*4), use_cache=True)

    def test_full_128_real_cpu_updates_and_fault_reset_do_not_contaminate_next_task(self):
        plan, data = fixture('TTT128-30'); plan['native_source_learning_rates'] = self.plan['native_source_learning_rates']
        for key in data:
            material = runtime.public_training_material(self.loader, self.tokenizer, key, data[key])
            plan['task_materials'][key].update(rows_digest=digest(material['rows']), texts_digest=digest(material['texts']))
        real_budget = self.budget_module.EpochBudget
        def budget_factory(*a, **kwargs):
            kwargs.update(expected_parameters=sum(p.numel() for p in a[1].parameters()), expected_dtype='torch.float32')
            return real_budget(*a, **kwargs)
        modules = {'nvarc_native_ttt_budget': SimpleNamespace(EpochBudget=budget_factory),
                   'nvarc_native_ttt_schedule': SimpleNamespace(native_schedule=lambda *a: (plan['native_source_learning_rates'], {'fixture': 'tiny-cpu'}))}
        with fixture_modules(modules), patch.object(torch.cuda, 'synchronize', lambda: None), tempfile.TemporaryDirectory() as tmp:
            engine = self.engine(plan)
            completed, retired = runtime.run_one_task(engine, plan, data, 'a', Path(tmp)/'complete', time.time()+600)
            self.assertFalse(retired); self.assertTrue(completed['training_complete']); self.assertEqual(completed['training_steps'], 128)
            self.assertEqual(completed['training_forwards_completed'], 128); self.assertTrue(completed['reset_verified'])
            self.assertEqual(engine.inventory(), engine.baseline)
            self.assertIsNotNone(completed['telemetry']['exclusive_host_seconds']['training'])
            self.assertEqual(completed['telemetry']['training_forwards']['completed'], 128)
            profiled, retired = runtime.run_one_task(engine, plan, data, 'a', Path(tmp)/'profiled', time.time()+600,
                                                     detailed_profiling=True)
            self.assertFalse(retired); self.assertEqual(profiled['training_steps'], 128)
            self.assertEqual(json.loads((Path(tmp)/'complete/training-ledger.json').read_bytes()),
                             json.loads((Path(tmp)/'profiled/training-ledger.json').read_bytes()))
            self.assertEqual(json.loads((Path(tmp)/'complete/trained-inventory.json').read_bytes()),
                             json.loads((Path(tmp)/'profiled/trained-inventory.json').read_bytes()))
            self.assertEqual(engine.inventory(), engine.baseline)
            self.assertIn('training_ledger_io', profiled['telemetry']['detail_inclusive_host_seconds'])
            next_task, retired = runtime.run_one_task(engine, plan, data, 'b', Path(tmp)/'next', time.time()+600)
            self.assertFalse(retired); self.assertEqual(next_task['training_steps'], 128)
            self.assertEqual(engine.inventory(), engine.baseline)
            broken = self.engine(plan, fail_after=10)
            failed, retired = runtime.run_one_task(broken, plan, data, 'a', Path(tmp)/'fault', time.time()+600)
            self.assertTrue(retired); self.assertFalse(failed['training_complete']); self.assertEqual(failed['training_steps'], 10)
            self.assertTrue(failed['reset_verified']); self.assertEqual(broken.inventory(), broken.baseline)
            self.assertTrue(all(not t['ranked_grids'] for t in failed['tests']))
            self.assertEqual(failed['telemetry']['training_forwards']['completed'], 10)
            self.assertTrue(any(e['phase'] == 'training' for e in failed['telemetry']['events']))
            poisoned = self.engine(plan, fail_after=10); poisoned.restore = lambda: None
            bad, retired = runtime.run_one_task(poisoned, plan, data, 'a', Path(tmp)/'bad-reset', time.time()+600)
            self.assertTrue(retired); self.assertFalse(bad['reset_verified'])
            self.assertTrue(any(e['phase'] == 'reset' for e in bad['telemetry']['events']))

    def test_two_rendered_profiles_compile_bind_source_and_have_distinct_zip_names(self):
        second, raw, notebook, meta = stage.construct('TTT128-30', '0'*40)
        self.assertNotEqual(second['download_archive'], self.plan['download_archive'])
        self.assertEqual(second['maximum_optimizer_steps'], 15360)
        self.assertEqual(self.plan['maximum_optimizer_steps'], 0)
        self.assertEqual(raw['challenges'], self.raw['challenges']); self.assertEqual(second['per_test_seconds'], 30)
        for nb in (self.notebook, notebook):
            for cell in nb['cells']:
                if cell['cell_type'] == 'code': compile(''.join(cell['source']), 'rendered-public-cell', 'exec')
        self.assertNotIn('scorer', raw); self.assertFalse(second['agent_execution_authorized'])

    def test_rendered_payloads_and_early_failure_keep_full_skeleton_and_named_zip(self):
        source = ''.join(self.notebook['cells'][1]['source'])
        tree = ast.parse(source)
        packed = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'PACKED' for t in n.targets))
        self.assertEqual({k: zlib.decompress(base64.b64decode(v)) for k, v in packed.items()}, self.raw)
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            location = Path(tmp)
            code = source.replace("Path('/kaggle/working')", 'Path('+repr(str(location))+')')
            namespace = {}; previous = list(sys.path)
            try:
                exec(compile(code, 'fixture-notebook-bootstrap', 'exec'), namespace)
                work = namespace['work']
                with self.assertRaisesRegex(RuntimeError, 'already exists'): exec(code, {})
                with patch.object(parent, 'prepare', side_effect=RuntimeError('fixture early hardware failure')):
                    result = parent.execute(work, self.plan, location, time.monotonic())
                self.assertEqual(result, 1)
                manifest, payloads = core.read_archive(location/self.plan['download_archive'])
                self.assertEqual(manifest['run_id'], self.plan['run_id'])
                self.assertEqual(json.loads(payloads['terminal.json'])['outcome'], 'failed')
                skeleton = json.loads(payloads['submission.json'])
                self.assertEqual(len(skeleton), 120); self.assertEqual(sum(map(len, skeleton.values())), 172)
                package = location/'local-package'; stage.stage(package, 'BASE-30', '0'*40)
                bound, challenges, _ = scorer.bind_returned_archive(manifest, payloads, package)
                self.assertEqual(bound, self.plan); self.assertEqual(len(challenges), 120)
                tampered = dict(payloads); tampered['tools/nvarc_public_eval_runtime.py'] += b'\n# altered\n'
                with self.assertRaisesRegex(RuntimeError, 'payload binding'):
                    scorer.bind_returned_archive(manifest, tampered, package)
            finally: sys.path[:] = previous


@unittest.skipUnless(stage.INPUT.is_file() and importlib.util.find_spec('kagglesdk'),
                     'optional cached frozen source and Kaggle SDK; no provider IO')
class PublicSaveTests(unittest.TestCase):
    def test_preflight_survives_fresh_interpreter_hash_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)/'package'; stage.stage(package, 'BASE-30', '0'*40)
            original_sha = core.sha(package/'kernel/notebook.ipynb')
            for seed in ('13', '71'):
                command = [sys.executable, str(stage.ROOT/'tools/stage_nvarc_public_eval.py'),
                           'preflight', '--package', str(package)]
                result = subprocess.run(command, cwd=stage.ROOT,
                    env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONUTF8='1'),
                    capture_output=True, text=True, encoding='utf-8', timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)['offline_package_verified'])
                self.assertEqual(core.sha(package/'kernel/notebook.ipynb'), original_sha)

    def test_actual_sdk_save_only_wire_and_reservation_before_credentials_no_retry(self):
        from tools import save_nvarc_public_eval as transport
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            location = Path(tmp)
            for profile in core.RUNS:
                run = core.RUNS[profile]; parent_path = location/'.irisx/nvarc-public-eval/runs'/run
                package, journal = parent_path/'package-l4', parent_path/'editor-save'
                stage.stage(package, profile, '0'*40)
                req, wire = transport.request(package)
                self.assertEqual(wire['kernelExecutionType'], 'QUICK_SAVE')
                self.assertEqual(wire['sessionTimeoutSeconds'], 3600 if profile == 'BASE-30' else 14400)
                self.assertTrue(wire['isPrivate']); self.assertFalse(wire.get('enableInternet', False))
                self.assertEqual(wire['machineShape'], 'NvidiaL4')
                self.assertFalse(any(c.get('outputs') for c in json.loads(wire['text'])['cells']))
                def credential_fault():
                    self.assertTrue((journal/'save-reserved.json').is_file())
                    self.assertEqual(json.loads((journal/'save-ledger.json').read_bytes())['push_reserved'], 1)
                    raise RuntimeError('planned pre-provider credential fault')
                with (patch.object(transport, 'ROOT', location),
                      patch.object(transport, 'token', side_effect=credential_fault) as credentials,
                      patch.object(transport, 'client_for') as clients):
                    transport.execute('init', package, journal)
                    with self.assertRaises(SystemExit): transport.execute('save', package, journal)
                    with self.assertRaisesRegex(RuntimeError, 'consumed'): transport.execute('save', package, journal)
                    self.assertEqual(credentials.call_count, 1); clients.assert_not_called()
                ledger = json.loads((journal/'save-ledger.json').read_bytes())
                self.assertEqual(ledger['sends'], 0)
                self.assertEqual(ledger['status_checks_reserved'], 0); self.assertEqual(ledger['retrieval_reserved'], 0)


if __name__ == '__main__': unittest.main()
