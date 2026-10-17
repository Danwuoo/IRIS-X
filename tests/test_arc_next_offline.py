import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest import mock
from tools import arc_next_offline_bundle as bundle
from tools import stage_arc_next_offline as stage
from tests.platform_requirements import requires_linux


def pins():
    return {role:{'reference':'danielwuu/iris-test-'+role+'/3','private':True,'manifest_sha256':'a'*64}
            for role in ('runtime','model','wheels')}


def small_runtime(root):
    body=b'print("must not execute")\n';p=root/'runtime/tools/example.py';p.parent.mkdir(parents=True);p.write_bytes(body)
    obj={'format':bundle.FORMAT,'source_commit':'a'*40,'contains_model_weights':False,'contains_wheels':False,
         'files':{'runtime/tools/example.py':{'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}}}
    (root/'bundle-manifest.json').write_bytes(bundle.canonical(obj)+b'\n')
    return bundle.sha_file(root/'bundle-manifest.json')


class OfflineBundleTests(unittest.TestCase):
    def test_closed_manifest_and_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);digest=small_runtime(root)
            self.assertEqual(bundle.verify_runtime(root,digest)['source_commit'],'a'*40)
            (root/'runtime/tools/example.py').write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'changed'):bundle.verify_runtime(root,digest)

    def test_missing_extra_and_wrong_manifest_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);digest=small_runtime(root)
            with self.assertRaisesRegex(ValueError,'notebook pin'):bundle.verify_runtime(root,'0'*64)
            (root/'extra').write_text('unexpected')
            with self.assertRaisesRegex(ValueError,'unexpected'):bundle.verify_runtime(root,digest)

    def test_symlink_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);digest=small_runtime(root)
            try:
                (root/'alias').symlink_to(root/'runtime',target_is_directory=True)
            except OSError as error:
                if os.name == 'nt' and getattr(error, 'winerror', None) == 1314:
                    self.skipTest('Windows symlink creation privilege unavailable')
                raise
            with self.assertRaisesRegex(ValueError,'symlinks'):bundle.verify_runtime(root,digest)

    def test_safe_member_rejects_escape(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ('../escape','/etc/passwd','runtime\\evil',''):
                with self.assertRaises(ValueError):bundle.safe_file(Path(d),name)

    def test_version_pin_required(self):
        for ref in ('danielwuu/test','someone/test/1','danielwuu/test/latest','danielwuu/test/0','danielwuu/test/-1'):
            with self.assertRaises(ValueError):bundle.validate_reference(ref)
        self.assertEqual(bundle.validate_reference('danielwuu/test/2'),'danielwuu/test/2')

    def test_explicit_mount_no_latest_discovery(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'test').mkdir()
            self.assertEqual(bundle.resolve_mount('danielwuu/test/4',input_root=root),root/'test')
            (root/'datasets/danielwuu/test').mkdir(parents=True)
            with self.assertRaisesRegex(ValueError,'Exactly one'):bundle.resolve_mount('danielwuu/test/4',input_root=root)

    def test_all_notebook_defaults_inert_with_network_blocked(self):
        nb=stage.notebook(pins());old=os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                values={}
                with mock.patch('socket.socket',side_effect=AssertionError('network attempted')),contextlib.redirect_stdout(io.StringIO()):
                    for cell in nb['cells']:
                        if cell['cell_type']=='code':exec(compile(''.join(cell['source']),'notebook','exec'),values)
                self.assertTrue(all(values[x] is False for x in stage.FLAGS));self.assertEqual(list(Path(d).iterdir()),[])
            finally:os.chdir(old)

    def test_missing_mount_fails_before_import_or_network(self):
        nb=stage.notebook(pins());cells=[''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code'];values={}
        exec(cells[0],values);values['VERIFY_OFFLINE_INPUTS']=True
        values['RUNTIME_ROOT']='/definitely-missing-iris-runtime'
        with mock.patch('socket.socket',side_effect=AssertionError('network attempted')):
            with self.assertRaisesRegex(ValueError,'mount'):exec(cells[1],values)

    def test_notebook_metadata_pins_and_manual_guards(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'package';result=stage.stage_notebook(root,pins())
            metadata=json.loads((root/'kernel-metadata.json').read_bytes())
            self.assertFalse(metadata['enable_internet']);self.assertFalse(metadata['enable_gpu'])
            self.assertEqual(metadata['dataset_sources'],[pins()[r]['reference'] for r in ('runtime','model','wheels')])
            self.assertEqual(metadata['competition_sources'],['arc-prize-2026-arc-agi-3'])
            self.assertEqual(metadata['kernel_sources'],[]);self.assertEqual(metadata['model_sources'],[])
            nb=json.loads((root/'notebook.ipynb').read_bytes())
            self.assertEqual(nb['metadata']['irisx_preserved_competition_sources'],['arc-prize-2026-arc-agi-3'])
            for cell in nb['cells']:
                if cell['cell_type']=='code':self.assertNotIn('arc-prize-2026-arc-agi-3',''.join(cell['source']))
            self.assertTrue(result['all_defaults_inert'])

    @requires_linux("offline runtime imports Linux SIGKILL process-group dispatch stages")
    def test_disabled_driver_performs_no_work(self):
        from tools import arc_next_offline_runtime as runtime
        with mock.patch('subprocess.run',side_effect=AssertionError('process')):
            self.assertEqual(runtime.launch_phase('anything',{},enabled=False)['status'],'disabled')
        with self.assertRaises(ValueError):runtime.launch_phase('anything',{},enabled='true')

    def test_writable_runtime_bootstrap_does_not_add_bytecode(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);root=base/'runtime-mount';root.mkdir()
            raw={'runtime/tools/__init__.py':b'', 'runtime/tools/arc_next_offline_bundle.py':Path(bundle.__file__).read_bytes()}
            for name,body in raw.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
            manifest={'format':bundle.FORMAT,'source_commit':'a'*40,'contains_model_weights':False,'contains_wheels':False,
                'files':{name:{'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()} for name,body in raw.items()}}
            (root/'bundle-manifest.json').write_bytes(bundle.canonical(manifest))
            references=pins();references['runtime']['manifest_sha256']=bundle.sha_file(root/'bundle-manifest.json')
            nb=stage.notebook(references);cells=[''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code']
            script=base/'bootstrap.py'
            script.write_text(cells[0]+'\nVERIFY_OFFLINE_INPUTS=True\nRUNTIME_ROOT='+repr(str(root))+'\nMODEL_ROOT='+repr(str(base))+'\nWHEELS_ROOT='+repr(str(base))+'\n'+cells[1])
            result=subprocess.run([sys.executable,str(script)],cwd=base,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(list(root.rglob('__pycache__')))
            bundle.verify_runtime(root,references['runtime']['manifest_sha256'])

    @requires_linux("mock target imports arc_next_training and its POSIX resource dependency")
    def test_runtime_training_check_does_not_open_evaluator_answers(self):
        task={'train':[{'input':[[0]],'output':[[1]]},{'input':[[1]],'output':[[2]]}]}
        selection={'training_ids':['train'],'development_ids':['dev'],'source_files':{'train':{'git_blob_sha1':'a','bytes':1},'dev':{'git_blob_sha1':'b','bytes':2}}}
        manifest={'task_partition':{'train':['train'],'dev':['dev']}}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'task-groups.json').write_bytes(bundle.canonical(selection))
            (root/'development-challenges.json').write_bytes(bundle.canonical({'dev':{'train':task['train'][:-1],'test':[{'input':[[1]]}]}}))
            (root/'source-receipts.json').write_bytes(bundle.canonical({key:dict(value,original_test_fields_retained=False) for key,value in selection['source_files'].items()}))
            # No evaluator directory exists: a semantic read would fail.
            with mock.patch('tools.arc_next_materials.groups',return_value=selection),mock.patch('tools.arc_next_training.load_training_material',return_value=({'train':task,'dev':task},manifest)):
                result=bundle.verify_runtime_training({},root)
            self.assertFalse(result['evaluator_answers_parsed'])

    @unittest.skipUnless(sys.version_info[:2]==(3,12) and sys.platform=='linux','Selected Linux CPython3.12 required')
    @requires_linux("requires the selected Linux CPython environment and SIGKILL runtime")
    def test_installed_receipt_fixed_command_and_tamper_rejected(self):
        from tools import arc_next_offline_runtime as runtime
        from tests.test_arc_next_offline_environment import Wheelhouse
        from tools.arc_next_offline_environment import install_offline, NETWORK_GUARD_HOOK_RELATIVE
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fixture=Wheelhouse(root);env=root/'env'
            result=install_offline(fixture.source,fixture.root,env,enabled=True)
            config={'environment_dir':str(env),'wheels_root':str(fixture.root),'pins':{'wheels':{'manifest_sha256':bundle.sha_file(fixture.root/'wheel-lock.json')}}}
            with mock.patch.object(runtime,'_source_lock',return_value=fixture.source):
                self.assertEqual(runtime._runtime_environment(config),result)
                receipt=env/'installation-receipt.json'
                changed=dict(result,python_command=[str(env/'bin/python'),'-c','print("unexpected")'])
                receipt.write_bytes(bundle.canonical(changed))
                with self.assertRaisesRegex(ValueError,'command'):runtime._runtime_environment(config)
                receipt.write_bytes(bundle.canonical(result))
                hook=env/NETWORK_GUARD_HOOK_RELATIVE
                hook_bytes=hook.read_bytes()
                hook.write_text('import sys\n')
                with self.assertRaisesRegex(ValueError,'startup hook'):runtime._runtime_environment(config)
                hook.write_bytes(hook_bytes)
                changed=dict(result);changed.pop('network_guard_startup')
                receipt.write_bytes(bundle.canonical(changed))
                with self.assertRaisesRegex(ValueError,'startup hook'):runtime._runtime_environment(config)
                receipt.write_bytes(bundle.canonical(result))
                (env/'offline-run.py').write_text('print("changed launcher")')
                with self.assertRaisesRegex(ValueError,'launcher'):runtime._runtime_environment(config)

    @requires_linux("offline runtime imports Linux SIGKILL process-group dispatch stages")
    def test_cpu_guard_probe_requires_marker_before_attempt(self):
        from tools import arc_next_offline_runtime as runtime
        import socket
        with mock.patch.object(socket,'_irisx_offline_guard',False,create=True),mock.patch.object(socket,'socket',side_effect=AssertionError('unguarded probe attempted')):
            with self.assertRaisesRegex(RuntimeError,'guard is not active'):runtime.cpu_import_check({}, {})

    @requires_linux("offline runtime imports Linux SIGKILL process-group dispatch stages")
    def test_cpu_guard_probe_does_not_accept_os_sandbox_denial(self):
        from tools import arc_next_offline_runtime as runtime
        import socket
        with mock.patch.object(socket,'_irisx_offline_guard',True,create=True),mock.patch.object(socket,'socket',side_effect=PermissionError('OS restriction')):
            with self.assertRaisesRegex(PermissionError,'OS restriction'):runtime.cpu_import_check({}, {})

    @requires_linux("offline runtime imports Linux SIGKILL process-group dispatch stages")
    def test_repeat_model_phase_checks_exact_manifest_pin_before_imports(self):
        from tools import arc_next_offline_runtime as runtime
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'irisx-model-material.json').write_text('{}')
            config={'model_root':str(root),'pins':{'model':{'manifest_sha256':'0'*64}}}
            with mock.patch.object(runtime,'_validate',return_value=config),mock.patch.object(runtime,'_runtime_environment',side_effect=AssertionError('interpreter before model pin')):
                for phase in ('CHECK_CPU_IMPORTS','RUN_CALIBRATION','RUN_ARCHITECTURE_PILOT'):
                    with self.assertRaisesRegex(ValueError,'pinned Dataset'):runtime.execute_phase(phase,config)

    @requires_linux("offline runtime imports Linux SIGKILL process-group dispatch stages")
    def test_output_and_environment_cannot_mutate_mounted_inputs(self):
        from tools import arc_next_offline_runtime as runtime
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            config=dict(runtime_root=str(root/'runtime'),model_root=str(root/'model'),wheels_root=str(root/'wheels'),environment_dir=str(root/'env'),output_root=str(root/'out'),pins=pins(),run_tag='test-001',training_profile='smoke2',enable_training_pilot=False,max_wall_seconds=10,approved_max_cost_usd=None,estimated_hourly_cost_usd=None,adapter_path=None)
            for input_key in ('runtime_root','model_root','wheels_root'):
                for output_key in ('environment_dir','output_root'):
                    bad=dict(config);bad[output_key]=str(Path(config[input_key])/'accidental-write')
                    with self.assertRaisesRegex(ValueError,'immutable Dataset'):runtime._validate(bad)

    def test_notebook_render_is_independent_of_pin_mapping_order(self):
        forward=pins();reverse=dict(reversed(list(forward.items())))
        reverse={k:dict(reversed(list(v.items()))) for k,v in reverse.items()}
        self.assertEqual(stage.notebook(forward),stage.notebook(reverse))

    def test_no_online_prepare_cells(self):
        text=json.dumps(stage.notebook(pins()))
        for token in ('snapshot_download','pip download','PREPARE_PUBLIC_MATERIALS','PREPARE_ENVIRONMENT','https://'):
            self.assertNotIn(token,text)

    def test_unknown_and_multiple_phase_rejected(self):
        nb=stage.notebook(pins());cells=[''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code'];values={}
        exec(cells[0],values);values.update(VERIFY_OFFLINE_INPUTS=True,RUN_CALIBRATION=True)
        with self.assertRaisesRegex(ValueError,'phase'):exec(cells[1],values)


if __name__=='__main__':unittest.main()
