"""Local save-only wrapper and closed diagnostic evidence, no real dispatch."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools.nvarc_posttrain_20261017 import stability_controller as sc, stability_package as sp
from tests.test_nvarc_posttrain_package import closure as legacy_fixture_closure
from tools.arc2_goal_sprint_20261017.launch import write_new
from tests.test_nvarc_posttrain_controller import model_identity


def closure():
    return {**legacy_fixture_closure(), 'forced': False}


class StabilityDeliveryTests(unittest.TestCase):
    def kwargs(self):
        return dict(run_id='synthetic-stability-source', session_id='synthetic-stability-session',
            notebook_ref='danielwuu/synthetic-stability-new', source_dataset='danielwuu/synthetic-source/1',
            solver_dataset='danielwuu/synthetic-solver/1', source_manifest_sha256='a'*64,
            source_payload_sha256='b'*64, started_epoch=time.time()-1)

    def test_build_is_independent_offline_private_manual_clock_and_no_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'new'
            result=sp.build_notebook(root, **self.kwargs())
            metadata=json.loads((root/'kernel-metadata.json').read_bytes())
            notebook=json.loads((root/metadata['code_file']).read_bytes())
            request=json.loads((root/'frozen-source-request.json').read_bytes())
            self.assertFalse(result['run_launched']);self.assertFalse(result['published'])
            self.assertEqual(result['save_mode_required'],'QUICK_SAVE')
            self.assertTrue(metadata['is_private']);self.assertFalse(metadata['enable_internet'])
            self.assertEqual(metadata['competition_sources'],[])
            self.assertEqual(metadata['title'].lower().replace(' ','-'), metadata['id'].split('/')[1])
            self.assertEqual(len(metadata['model_sources']),2)
            self.assertEqual(request['workflow'],sc.WORKFLOW)
            self.assertIn('claim_manual_request(',notebook['cells'][1]['source'])
            self.assertEqual(notebook['cells'][1]['outputs'],[])
            compile(notebook['cells'][1]['source'],'synthetic-only','exec')
            self.assertEqual(notebook['metadata']['irisx_execution_mode'],'QUICK_SAVE_ONLY_NO_AGENT_RUN')

    def test_old_active_notebook_and_evaluator_bearing_data_rejected(self):
        for change in ({'notebook_ref':'danielwuu/iris-x-nvarc-dual-posttrain-20261017'},
                       {'solver_dataset':sp.REFERENCES['public']}, {'source_manifest_sha256':'wrong'}):
            with tempfile.TemporaryDirectory() as temp, self.subTest(change=change), self.assertRaises(ValueError):
                sp.build_notebook(Path(temp)/'new', **{**self.kwargs(),**change})

    def test_closed_diagnostic_is_not_public_seal_or_provider_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);output=root/'solver';output.mkdir();control=root/'control';control.mkdir()
            config={'run_id':'synthetic','source_identity':'a'*64,'output_root':str(output)}
            write_new(control/'owner-closure.json',closure())
            write_new(output/'run-summary.json',{'run_id':'synthetic','source_identity':'a'*64,
                'workflow':sc.WORKFLOW,'completed':True})
            result=sc.close_diagnostic(config,control,closure())
            self.assertTrue(result['completed']);self.assertEqual(result['status'],'CLOSED_DIAGNOSTIC')
            self.assertFalse(result['provider_terminal_verified']);self.assertIsNone(result['public_score'])
            self.assertFalse(result['generation_may_resume']);self.assertFalse((control/'sealed').exists())

    def test_missing_or_failed_diagnostic_cannot_claim_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);control=root/'control';control.mkdir()
            proof=closure();proof['worker_returncode']=1
            write_new(control/'owner-closure.json',proof)
            result=sc.close_diagnostic({'run_id':'synthetic','source_identity':'a'*64,'output_root':str(root/'missing')},control,proof)
            self.assertFalse(result['completed']);self.assertEqual(result['files'],{})

    def test_forced_descendant_cleanup_cannot_claim_normal_scientific_completion(self):
        for changes in ({'returncode':125}, {'forced':True}, {'returncode':125,'forced':True}):
            with tempfile.TemporaryDirectory() as temp, self.subTest(changes=changes):
                root=Path(temp);out=root/'solver';out.mkdir();control=root/'control';control.mkdir()
                proof={**closure(),**changes}
                write_new(control/'owner-closure.json',proof)
                write_new(out/'run-summary.json',{'run_id':'synthetic','source_identity':'a'*64,
                    'workflow':sc.WORKFLOW,'completed':True})
                result=sc.close_diagnostic({'run_id':'synthetic','source_identity':'a'*64,'output_root':str(out)},control,proof)
                self.assertEqual(result['status'],'CLOSED_DIAGNOSTIC')
                self.assertFalse(result['completed'])

    def test_foreign_diagnostic_summary_is_not_sealed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'solver';out.mkdir();control=root/'control';control.mkdir()
            write_new(control/'owner-closure.json',closure())
            write_new(out/'run-summary.json',{'run_id':'foreign','source_identity':'a'*64,'workflow':sc.WORKFLOW,'completed':True})
            with self.assertRaisesRegex(ValueError,'identity differs'):
                sc.close_diagnostic({'run_id':'synthetic','source_identity':'a'*64,'output_root':str(out)},control,closure())

    def test_full_owned_controller_path_requests_only_two_stability_workers(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);start=time.time()-1
            config={'workflow':sc.WORKFLOW,'started_epoch':start,'deadline_epoch':start+43200,
                'source_root':str(root),'output_root':str(root/'solver'),'input_root':str(root/'input'),
                'allowed_input_roots':[],'runtime_env':{},'python':'python','parameters':{},
                'source_identity':'a'*64,'run_id':'fixture','model_roots':{'2b':'two','4b':'four'},
                'training_root':'train','training_manifest_path':'manifest','public_path':'solver-only'}
            topology={'device_count':1,'device_identity':'device','free_bytes':64*1024**3}
            called=[]
            def execute(jobs,**kwargs):
                self.assertEqual(len(jobs),1);job=jobs[0];called.append(job)
                result={key:job[key] for key in ('job_id','source_identity','workload_identity','device_identity')}
                result.update(mode='stability',model_identity=model_identity(job['variant']),
                    stability={'complete':True,'protocol_sha256':'fixed'},completed=True)
                return {'completed':True,'wall_seconds':1.,'jobs':[{'job_id':job['job_id'],
                    'status':'completed','closure_verified':True,'result':result}]}
            with patch.object(sc,'check_dataset_separation'),patch.object(sc,'progress'),\
                    patch.object(sc.subprocess,'run',return_value=SimpleNamespace(stdout=json.dumps(topology))),\
                    patch.object(sc,'run_wave',side_effect=execute):
                result=sc.run(config)
            self.assertEqual([job['variant'] for job in called],['2b','4b'])
            self.assertTrue(all(job['mode']=='stability' and 'checkpoint' not in job for job in called))
            self.assertTrue(result['completed']);self.assertFalse(result['public_inference_performed'])
            self.assertFalse(result['automatic_following_run']);self.assertIsNone(result['public_score'])
            self.assertEqual([job['parameters'] for job in called],[{},{}])

    def test_unknown_workflow_or_training_overrides_fail_before_execution(self):
        with patch.object(sc,'run_wave') as launch:
            with self.assertRaises(ValueError):sc.run({'workflow':'unknown'})
            now=time.time()
            with self.assertRaises(ValueError):
                sc.run({'workflow':sc.WORKFLOW,'started_epoch':now-1,'deadline_epoch':now-1+43200,
                        'parameters':{'ttt_lr':1e-4}})
            launch.assert_not_called()


if __name__=='__main__':unittest.main()
