"""Offline numeric diagnostic packaging and wrapper tests; no launch authority.

Public source reconstruction is exact. Invented proof/approval documents below
are temporary CPU fixtures, never authentic private candidate inputs.
"""
import ast
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from tools.arc_qwen_rlvr004_20261013.numeric_replay_diagnostic_20261016 import assemble as a
from tools.arc_qwen_rlvr004_20261013.admission_run008.test_preparation_repair import consumed_runtime, consumed_deployment
from tools.arc_qwen_rlvr004_20261013.wrapper_observation_repair import test_wrapper_observation_repair as predecessor


def module(path, raw=None):
    m = types.ModuleType('numeric_packaging_' + path.stem)
    m.__file__ = str(path)
    exec(compile(path.read_bytes() if raw is None else raw, str(path), 'exec',
                 dont_inherit=True, optimize=sys.flags.optimize), vars(m))
    return m


def namespaces(raw):
    for before, after in ((a.s.RUN, a.RUN), (a.s.SOURCE, a.SOURCE), (a.s.ENV, a.ENV)):
        raw = raw.replace(before.encode(), after.encode())
    return raw


class PackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original, cls.environment = consumed_runtime()

    def test_exact_published_baselines_unchanged(self):
        self.assertEqual(a.sha((a.TOOL / 'admission_run008/assemble.py').read_bytes()),
                         '2e8bb0e13123376f88720373f13658640ca7c17c09a57f367d8689c5a2fe9388')
        self.assertEqual(a.sha((a.TOOL / 'wrapper_observation_repair/verify_parent_wrappers.py').read_bytes()), a.BASE_WRAPPER_SHA)
        self.assertEqual(a.sha((a.TOOL / 'support/deployment/parent_entry.py').read_bytes()), a.BASE_PARENT_ENTRY_SHA)
        self.assertEqual(a.sha(a.canonical(sorted((n, a.sha(b)) for n, b in self.original.items()))), a.ORIGINAL_SOURCE_SHA)
        guarded, archive, _ = a.repaired_runtime(self.original, self.environment)
        self.assertEqual(a.sha(archive), a.ARCHIVE_SHA)
        self.assertEqual(a.sha(a.canonical(sorted((n, a.sha(b)) for n, b in guarded.items()))), a.SOURCE_SHA)

    def synthetic_overlay(self):
        # Inert bodies only test deterministic packaging, not numeric correctness.
        return {n: b'"""Synthetic packaging-only body; never a runtime candidate."""\n'
                   + ('TARGET = ' + repr(n) + '\n').encode() for n in a.RUNTIME_TARGETS}

    def test_source_overlay_before_new_source_pin(self):
        environment = a.projected_environment(self.environment)
        overlay = self.synthetic_overlay()
        source, archive, normalized = a.diagnostic_runtime(self.original, self.environment, environment, overlay)
        self.assertEqual(len(source), 260)
        self.assertEqual(set(source) - set(self.original), {'rl_session/numeric_shadow.py'})
        self.assertEqual({n for n in self.original if self.original[n] != source[n]},
            a.RUNTIME_TARGETS - {'rl_session/numeric_shadow.py'} | {'owned_runtime/parent_scoring.py', 'owned_runtime/release.py'})
        self.assertEqual(sum(n.startswith('baseline/') for n in source), 200)
        self.assertTrue(all(source[n] == self.original[n] for n in self.original if n.startswith('baseline/')))
        normalized_source = dict(source)
        normalized_source['owned_runtime/release.py'], count = re.subn(
            rb"(?m)^NORMALIZED_SOURCE_CONTRACT_SHA256 = '[0-9a-f]{64}'$",
            b'NORMALIZED_SOURCE_CONTRACT_SHA256 = None', source['owned_runtime/release.py'])
        self.assertEqual(count, 1)
        self.assertEqual(a.sha(a.canonical(sorted((n, a.sha(b)) for n, b in normalized_source.items()))), normalized)
        self.assertIn(a.sha(environment).encode(), source['owned_runtime/release.py'])
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            self.assertEqual(set(z.namelist()), set(source))
            self.assertTrue(all(z.read(n) == b for n, b in source.items()))
        self.assertEqual((source, archive, normalized),
                         a.diagnostic_runtime(self.original, self.environment, environment, overlay))

    def test_overlay_requires_exact_seven_changed_bodies(self):
        environment = a.projected_environment(self.environment)
        for kind in ('missing', 'extra', 'unchanged', 'invalid'):
            overlay = self.synthetic_overlay()
            if kind == 'missing': del overlay['rl_session/numeric_shadow.py']
            if kind == 'extra': overlay['arbitrary.py'] = b'x=1\n'
            if kind == 'unchanged': overlay['rl_session/runtime.py'] = self.original['rl_session/runtime.py']
            if kind == 'invalid': overlay['rl_session/runtime.py'] = b'! not valid Python'
            with self.subTest(kind=kind), self.assertRaises((ValueError, SyntaxError)):
                a.diagnostic_runtime(self.original, self.environment, environment, overlay)

    def test_environment_projection_is_only_three_paths(self):
        raw = a.projected_environment(self.environment)
        self.assertEqual(raw.count(a.SOURCE.encode()), 3)
        self.assertEqual(raw.replace(a.SOURCE.encode(), a.s.SOURCE.encode()), self.environment)
        with self.assertRaises(ValueError): a.projected_environment(self.environment.replace(a.s.SOURCE.encode(), b'/unreviewed'))

    def test_exact_guard_callers_then_distinct_namespace(self):
        original = consumed_deployment()
        # Public helper provides run004 builder; project it exactly as frozen
        # run007/run008 assembly does before testing the new successor.
        original['notebook_builder.py'] = original['notebook_builder.py'].replace(
            b'/kaggle/working/irisx-qwen14b-rlvr-20261012-run004', a.s.RUN.encode()).replace(
            b'/kaggle/working/irisx-qwen14b-rlvr-20261012-source004', a.s.SOURCE.encode())
        result = a.diagnostic_deployment(original)
        self.assertEqual(result['source_loader.py'], original['source_loader.py'])
        self.assertEqual(result['parent_entry.py'], (HERE / 'deployment/parent_entry.py').read_bytes())
        guarded = a.repaired_preparation(original)
        for name in ('launch_notebook.py', 'prepare_entry.py', 'notebook_builder.py'):
            self.assertEqual(result[name], namespaces(guarded[name]))
            compile(result[name], name, 'exec')
        bad = dict(original); bad['parent_entry.py'] += b'\n'
        with self.assertRaises(ValueError): a.diagnostic_deployment(bad)

    def test_assembler_binds_every_new_body_before_reviews(self):
        tree = ast.parse(Path(a.__file__).read_bytes())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'assemble')
        assignments = {t.id: n for n in fn.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
        self.assertLess(assignments['overlay'].lineno, assignments['proposal'].lineno)
        self.assertLess(assignments['wrapper'].lineno, assignments['proposal'].lineno)
        self.assertLess(assignments['source_sha'].lineno, assignments['proposal'].lineno)
        for key in ('source_sha256', 'source_archive_sha256', 'normalized_source_contract_sha256',
                    'numeric_overlay_inventory', 'deployment_inventory', 'parent_wrapper_verifier_sha256',
                    'collector_sha256', 'assembler_source_sha256', 'run_purpose'):
            self.assertIn(key, a.BINDING_KEYS)
        text = ast.get_source_segment(Path(a.__file__).read_text(), fn)
        self.assertIn("'source.zip': archive", text)
        self.assertIn("release['dataset_references'][1:] == obj(original['notebook-release.json'])['dataset_references'][1:]", text)
        self.assertNotIn("'source.zip': original['code-payload/source.zip']", text)

    def test_proposal_cannot_be_replaced_by_old_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal = {key: 'synthetic-' + key for key in a.BINDING_KEYS}
            path = root / 'proposal.json'; path.write_bytes(a.encoded(proposal))
            old = root / 'old-review.json'; old.write_bytes(a.encoded({'format': 'irisx/run008-solver-namespace-review-v1', 'status': 'PASS'}))
            with self.assertRaisesRegex(ValueError, 'independent exact two-path'):
                a.review_inputs(proposal, proposal_path=path, proposal_sha=a.sha(path.read_bytes()),
                    solver_review_path=old, solver_review_sha=a.sha(old.read_bytes()),
                    runtime_review_path=None, runtime_review_sha=None, material_review_path=None, material_review_sha=None,
                    original_solver=b'CPU fixture', new_solver=b'CPU projected fixture')
            changed = dict(proposal, run_purpose='unapproved-generic-mode')
            with self.assertRaisesRegex(ValueError, 'differs from independently reviewed proposal'):
                a.review_inputs(changed, proposal_path=path, proposal_sha=a.sha(path.read_bytes()),
                    solver_review_path=None, solver_review_sha=None, runtime_review_path=None, runtime_review_sha=None,
                    material_review_path=None, material_review_sha=None, original_solver=b'', new_solver=b'')

    def test_missing_authentic_candidate_inputs_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = REPO / '.irisx/numeric-diagnostic-20261016/uncreated-missing-input-fixture'
            with self.assertRaises(FileNotFoundError):
                a.assemble(repository_root=REPO, source_proposal_root=root/'missing-private-proposal',
                    base_root=root/'missing-private-base', observation_root=root/'missing-observation', observation_sha='0'*64,
                    owner_direction_path=root/'missing-owner', owner_direction_sha='0'*64,
                    collector_path=root/'missing-collector', collector_sha='0'*64, output_root=output)
            self.assertFalse(output.exists())


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='numeric-wrapper-')
        self.addCleanup(self.tmp.cleanup)
        self.v = module(HERE/'assembly/verify_parent_wrappers.py')
        # The old fixture is reused only after a three-namespace test projection.
        fixture_module = module(Path(predecessor.__file__), namespaces(Path(predecessor.__file__).read_bytes()))
        self.f = fixture_module.Fixture(self.tmp.name, self.v)
        self.f.owned.update(status='owned-numeric-diagnostic-complete-no-update',
            run_purpose=a.RUN_PURPOSE, diagnostic_complete=True, comparison_complete=False,
            public_benchmark_evidence_eligible=False, scientific_goal_met=False,
            production_admitted=False, ARC_or_14B_efficacy_claim=False, PUBLIC_score=None,
            parent_scoring_ref=None, checkpoint_export=None, terminal_error=None, source_integrity_error=None)
        self.f.outer.update(worker_returncode=0, inner_closure={'status':'complete', 'model_closure':{
            **{key:True for key in ('closed','future_operations_blocked','model_references_released',
                'device_synchronized','model_stopped','ledger_settled')}, 'fatal_native_state':None}})
        self.f.terminal.update(status='diagnostic', model_closed=False)
        self.refresh()

    def refresh(self):
        self.f.refresh_runtime()
        self.f.terminal['authorization']['kind'] = 'live-owned-process-termination'
        self.f.terminal_raw = predecessor.enc(self.f.terminal)
        self.f.refresh_result()

    def check(self): return self.v.verify_wrappers(self.f.root, **self.f.kwargs())

    def test_exact_completed_diagnostic_clean_exit_is_operational(self):
        result = self.check()
        self.assertTrue(result['closure_valid']); self.assertTrue(result['operational'])
        self.assertEqual(result['terminal_status'], 'diagnostic')
        self.assertFalse(result['model_closure_verified_by_this_helper'])
        self.assertEqual([r['pid'] for r in result['nested_observation_difference']['installed_parent_only']], [23,25])

    def test_success_predicate_mutations_reject_clean_exit(self):
        changes = ((self.f.owned, 'run_purpose', 'generic-mode'), (self.f.owned,'diagnostic_complete',False),
                   (self.f.owned,'comparison_complete',True), (self.f.owned,'scientific_goal_met',True),
                   (self.f.owned,'PUBLIC_score',{}), (self.f.owned,'status','owned-numeric-diagnostic-incomplete'),
                   (self.f.outer,'safe_closure',False), (self.f.outer,'worker_returncode',1),
                   (self.f.outer['inner_closure']['model_closure'],'ledger_settled',False))
        for document, key, value in changes:
            old = document[key]; document[key] = value; self.refresh()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'successful parent return'):
                self.check()
            document[key] = old; self.refresh()

    def test_incomplete_nonzero_remains_clean_but_not_operational(self):
        self.f.owned.update(status='owned-numeric-diagnostic-incomplete', diagnostic_complete=False)
        self.refresh()
        for stage in ('preparation','installed-parent'):
            self.f.proof_edit(stage, lambda d:d.update(returncode=1,worker_returncode=1), True)
        result = self.check()
        self.assertTrue(result['closure_valid']); self.assertFalse(result['operational'])

    def test_actual_raw_checks_are_unchanged(self):
        old = ast.parse(namespaces((a.TOOL/'wrapper_observation_repair/verify_parent_wrappers.py').read_bytes()))
        new = ast.parse((HERE/'assembly/verify_parent_wrappers.py').read_bytes())
        new.body = [n for n in new.body if not (isinstance(n, ast.FunctionDef) and n.name == 'diagnostic_success')]
        fn = next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == 'verify_wrappers')
        fn.body = [n for n in fn.body if not (isinstance(n, ast.Assign) and isinstance(n.value, ast.BoolOp)
            and isinstance(n.value.op, ast.Or) and any(isinstance(t, ast.Name) and t.id == 'success' for t in n.targets))]
        self.assertEqual(ast.dump(old), ast.dump(new))

    def test_changed_raw_scope_clock_and_archive_member_reject(self):
        original = (self.f.root/'installed-parent/owned-tree/launch.json').read_bytes()
        self.f.edit('installed-parent/owned-tree/launch.json', lambda d:d.update(worker_argv=['foreign']))
        with self.assertRaisesRegex(ValueError,'argv'): self.check()
        (self.f.root/'installed-parent/owned-tree/launch.json').write_bytes(original)
        self.f.terminal['authorization']['original_deadlines'] = {'absolute':999999}
        self.f.terminal_raw = predecessor.enc(self.f.terminal); self.f.refresh_result()
        with self.assertRaisesRegex(ValueError,'deadlines'): self.check()
        self.refresh()
        self.f.terminal['archive']['members']['owned-result.json']['sha256'] = '0'*64
        self.f.terminal_raw = predecessor.enc(self.f.terminal); self.f.refresh_result()
        with self.assertRaisesRegex(ValueError,'sealed runtime'): self.check()



class ParentEntryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='numeric-parent-entry-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root/'output'; self.output.mkdir()
        loader = module(a.TOOL/'support/deployment/source_loader.py')
        tree = ast.parse((HERE/'deployment/parent_entry.py').read_bytes())
        functions = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef)
            and node.name in ('diagnostic_success','diagnostic_completed','main')], type_ignores=[])
        self.entry = types.ModuleType('CPU_parent_entry_fixture')
        self.entry.__dict__.update({name:getattr(loader,name) for name in
            ('read_regular','digest','need','parse','clean_path','encoded')})
        self.entry.__dict__.update(Path=Path, sys=sys, source_import_paths=lambda _:None)
        exec(compile(functions,'CPU-parent-entry-functions','exec',dont_inherit=True,optimize=sys.flags.optimize), self.entry.__dict__)
        self.outer = {'launch_source_sha256':'a'*64, 'output_root':str(self.output),
            'safe_closure':True,'model_stopped':True,'worker_exited':True,'worker_session_empty':True,
            'worker_returncode':0,'inner_closure':{'status':'complete','model_closure':{
                **{key:True for key in ('closed','future_operations_blocked','model_references_released',
                    'device_synchronized','model_stopped','ledger_settled')},'fatal_native_state':None}}}
        outer_raw = a.encoded(self.outer); (self.output/'outer-closure.json').write_bytes(outer_raw)
        self.owned = {'format':'owned-rl-result-v1','status':'owned-numeric-diagnostic-complete-no-update',
            'run_purpose':a.RUN_PURPOSE,'source_sha256':'a'*64,'diagnostic_complete':True,
            'comparison_complete':False,'public_benchmark_evidence_eligible':False,'scientific_goal_met':False,
            'production_admitted':False,'ARC_or_14B_efficacy_claim':False,'PUBLIC_score':None,
            'parent_scoring_ref':None,'checkpoint_export':None,'terminal_error':None,'source_integrity_error':None,
            'outer_closure_ref':{'path':str(self.output/'outer-closure.json'),'file_sha256':a.sha(outer_raw)}}
        owned_raw = a.encoded(self.owned); (self.output/'owned-result.json').write_bytes(owned_raw)
        self.archive = Path(str(self.output)+'.evidence.zip')
        with zipfile.ZipFile(self.archive,'x',compression=zipfile.ZIP_STORED) as z:
            z.writestr('outer-closure.json',outer_raw); z.writestr('owned-result.json',owned_raw)
        archive_raw = self.archive.read_bytes()
        terminal = {'status':'diagnostic','archive_complete':True,'model_closed':False,
            'model_success_claim':False,'scientific_goal_met':False,'production_admitted':False,
            'authorization':{'kind':'live-owned-process-termination','source_sha256':'a'*64,
                'output_root':str(self.output),'outer_closure_ref':self.owned['outer_closure_ref']},
            'archive':{'path':str(self.archive),'bytes':len(archive_raw),'sha256':a.sha(archive_raw),
                'members':{name:{'bytes':len(raw),'sha256':a.sha(raw)} for name,raw in
                    (('outer-closure.json',outer_raw),('owned-result.json',owned_raw))}}}
        self.terminal_path = Path(str(self.output)+'.evidence.zip.terminal.json')
        terminal_raw = a.encoded(terminal); self.terminal_path.write_bytes(terminal_raw)
        self.result = {**self.owned,'terminal_export':{**terminal,'terminal_receipt':{
            'path':str(self.terminal_path),'bytes':len(terminal_raw),'sha256':a.sha(terminal_raw)}}}

    def test_actual_diagnostic_documents_and_archive_allow_completion(self):
        self.assertTrue(self.entry.diagnostic_completed(self.result,str(self.output)))

    def test_actual_missing_or_changed_outputs_reject(self):
        for path in (self.output/'outer-closure.json',self.output/'owned-result.json',self.terminal_path,self.archive):
            raw = path.read_bytes()
            path.write_bytes(raw+b'changed')
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                self.entry.diagnostic_completed(self.result,str(self.output))
            path.write_bytes(raw)
        self.archive.unlink()
        with self.assertRaises(FileNotFoundError): self.entry.diagnostic_completed(self.result,str(self.output))

    def test_incomplete_is_not_upgraded_by_archive(self):
        result = copy.deepcopy(self.result)
        result.update(status='owned-numeric-diagnostic-incomplete',diagnostic_complete=False)
        self.assertFalse(self.entry.diagnostic_completed(result,str(self.output)))

    def test_success_predicate_is_identical_to_archived_verifier(self):
        def predicate(path):
            return ast.dump(next(n for n in ast.parse(path.read_bytes()).body
                if isinstance(n,ast.FunctionDef) and n.name=='diagnostic_success'))
        self.assertEqual(predicate(HERE/'deployment/parent_entry.py'), predicate(HERE/'assembly/verify_parent_wrappers.py'))

    def test_real_main_control_flow_zero_only_for_completed_diagnostic(self):
        release = types.ModuleType('owned_runtime.release')
        release.inventory = lambda:{}; release.source_digest = lambda _:'a'*64
        bootstrap = types.ModuleType('owned_runtime.bootstrap')
        bootstrap.reviewed_bootstrap = lambda *_args,**_kwargs:self.result
        for complete in (True,False):
            if not complete:self.result.update(status='owned-numeric-diagnostic-incomplete',diagnostic_complete=False)
            target = self.root/('parent-result-'+str(complete)+'.json')
            request = {'format':'irisx/rlvr-installed-parent-request-v1','source_root':str(self.root/'runtime'),
                'source_sha256':'a'*64,'config':{},'output_root':str(self.output),'paths':{},'result_path':str(target)}
            path = self.root/'request.json'; path.write_bytes(a.encoded(request))
            with (self.subTest(complete=complete), patch.dict(sys.modules,{
                'owned_runtime.release':release,'owned_runtime.bootstrap':bootstrap}),
                patch.object(sys,'argv',['parent_entry.py',str(path),a.sha(path.read_bytes())]),
                patch('sys.stdout',new=io.StringIO())):
                if complete:self.entry.main()
                else:
                    with self.assertRaises(SystemExit) as caught:self.entry.main()
                    self.assertEqual(caught.exception.code,1)
            self.assertEqual(json.loads(target.read_bytes()),self.result)



class PublicationSpecializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = a.TOOL/'publication_windows_bridge_20261015'
        cls.transport_tree = ast.parse((HERE/'publication/rl_transport.py').read_bytes())
        cls.wire = module(HERE/'publication/verify_active_wire.py')

    def owner(self):
        return {'format':'irisx/numeric-diagnostic-owner-direction-v1','owner_id':'danielwuu',
            'request_id':'synthetic-CPU-only-not-a-request','instruction':'Synthetic CPU packaging fixture only; no publication or execution authorization.',
            'run_purpose':a.RUN_PURPOSE,'training_only':True,'rl_optimizer_commit_authorized':False,
            'later_B_C_dev_holdout_PUBLIC_authorized':False,'one_accepted_run_per_distinct_reviewed_candidate':True,
            'continuous_monitoring_authorized':True,'result_retrieval_authorized':True,'session_limit_seconds':43200,
            'original_public_task_count':120,'original_public_query_denominator':167,
            **{key:False for key in ('gpu_quota_query_authorized','new_resource_or_paid_provisioning_authorized',
                'official_competition_submission_authorized','legal_agreement_acceptance_authorized',
                'credential_or_permission_changes_authorized_by_this_file','runtime_or_scientific_success_claim')}}

    def scope(self,owner):
        node = next(n for n in self.transport_tree.body if isinstance(n,ast.FunctionDef) and n.name=='diagnostic_owner_scope')
        ns = {'need':a.need,'RUN_PURPOSE':a.RUN_PURPOSE}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'CPU-owner-scope','exec',dont_inherit=True,optimize=sys.flags.optimize),ns)
        ns['diagnostic_owner_scope'](owner)

    def test_exact_original_transport_and_wire_unchanged(self):
        self.assertEqual(a.sha((self.baseline/'rl_transport.py').read_bytes()),a.BASE_TRANSPORT_SHA)
        self.assertEqual(a.sha((self.baseline/'verify_active_wire.py').read_bytes()),a.BASE_ACTIVE_WIRE_SHA)

    def test_real_runtime_hashes_match_fixed_wire_and_helper_bindings(self):
        original,environment = consumed_runtime()
        source,archive,_ = a.diagnostic_runtime(original,environment,a.projected_environment(environment),a.runtime_overlay())
        source_sha = a.sha(a.canonical(sorted((n,a.sha(b)) for n,b in source.items())))
        self.assertEqual(self.wire.SOURCE,source_sha)
        self.assertEqual(self.wire.ARCHIVE,a.sha(archive))
        helpers = a.publication_helpers(source_sha,a.sha(archive))
        self.assertEqual(set(helpers),{'rl_transport.py','verify_active_wire.py'})
        self.assertIn('publication_helper_inventory',a.BINDING_KEYS)
        with self.assertRaisesRegex(ValueError,'fixed publication helper pin differs'):
            a.publication_helpers('0'*64,a.sha(archive))

    def test_fixed_owner_scope_rejects_broader_or_old_authority(self):
        owner = self.owner(); self.scope(owner)
        for key,value in (('run_purpose','generic'),('training_only',False),('rl_optimizer_commit_authorized',True),
            ('later_B_C_dev_holdout_PUBLIC_authorized',True),('format','irisx/run008-native-owner-direction-v1'),
            ('session_limit_seconds',43201),('original_public_query_denominator',166),
            ('official_competition_submission_authorized',True)):
            with self.subTest(key=key),self.assertRaises(ValueError):self.scope(dict(owner,**{key:value}))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'synthetic-owner.json';p.write_bytes(a.encoded(owner))
            self.assertEqual(a.owner_inputs(p,a.sha(p.read_bytes()))[0],owner)
            bad=dict(owner,rl_optimizer_commit_authorized=True);p.write_bytes(a.encoded(bad))
            with self.assertRaises(ValueError):a.owner_inputs(p,a.sha(p.read_bytes()))

    def test_all_unrelated_transport_functions_and_imports_retained(self):
        old = ast.parse((self.baseline/'rl_transport.py').read_bytes())
        old_f={n.name:n for n in old.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        new_f={n.name:n for n in self.transport_tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        self.assertEqual(set(new_f)-set(old_f),{'diagnostic_owner_scope'})
        changed={n for n in old_f if ast.dump(old_f[n])!=ast.dump(new_f[n])}
        self.assertEqual(changed,{'current_predecessor_proof','contract'})
        old_imports=[ast.dump(n) for n in old.body if isinstance(n,(ast.Import,ast.ImportFrom))]
        new_imports=[ast.dump(n) for n in self.transport_tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
        self.assertEqual(old_imports,new_imports)
        for name in ('configure_local','publication_guard','publication_preflight','review_gate','load_contract',
                     'finalized_documents','submit','monitor_gate'):
            if name in old_f:self.assertEqual(ast.dump(old_f[name]),ast.dump(new_f[name]))
        text=(HERE/'publication/rl_transport.py').read_text()
        self.assertIn("COMMON_SOURCE_SHA256 = '88faa050b8cd7564e2d46552091773df4025b0589bd37771f79ea8648f2c053a'",text)
        self.assertIn("CONFIG.scratch_root/'state-run008'",text)
        self.assertIn("CONFIG.scratch_root/'evidence-run008'",text)
        self.assertNotIn('/kaggle/working/irisx-qwen14b-rlvr-20261013-run008',text)

    def test_wire_retains_all_other_guards_and_legacy_schema(self):
        old=ast.parse((self.baseline/'verify_active_wire.py').read_bytes())
        new=ast.parse((HERE/'publication/verify_active_wire.py').read_bytes())
        old_f={n.name:n for n in old.body if isinstance(n,ast.FunctionDef)}
        new_f={n.name:n for n in new.body if isinstance(n,ast.FunctionDef)}
        self.assertEqual(set(old_f),set(new_f))
        self.assertEqual({n for n in old_f if ast.dump(old_f[n])!=ast.dump(new_f[n])},{'verify'})
        self.assertEqual(self.wire.RUN,a.RUN);self.assertEqual(self.wire.SOURCE_ROOT,a.SOURCE)
        self.assertEqual(self.wire.RUN_PURPOSE,a.RUN_PURPOSE)
        self.assertEqual(a.FORMAT,'irisx/qwen14b-rlvr-run008-publication-contract-v1')
        verify=ast.get_source_segment((HERE/'publication/verify_active_wire.py').read_text(),new_f['verify'])
        self.assertIn("manifest.get('run_purpose') == RUN_PURPOSE",verify)
        self.assertIn("0 <= time.time() - epoch <= 60",verify)


if __name__ == '__main__': unittest.main()
