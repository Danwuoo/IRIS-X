import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools import nvarc_official_adapter as adapter
from tools import nvarc_official_render as render
from tools import run_nvarc_official_cli as transport


def challenges():
    return {'new-task-a':{'train':[{'input':[[1]],'output':[[2]]}],
                          'test':[{'input':[[3]]},{'input':[[4]]}]},
            'unseen-task-b':{'train':[{'input':[[5]],'output':[[6]]}],
                             'test':[{'input':[[7]]}]}}


class FullInputAdapterTests(unittest.TestCase):
    def test_runtime_replaces_preview_and_keeps_all_multi_tests(self):
        def material(loader,tok,key,task):
            return {'rows':[{'input_tokens':50,'supervised_tokens':10} for _ in range(128)],
                    'texts':[{'text':'public-demo-only'} for _ in range(128)]}
        with patch.object(adapter,'public_training_material',material):
            plan,materials=adapter.runtime_plan({'native_source_learning_rates':[0.0]*129},challenges(),None,None,5000)
        self.assertEqual(plan['task_order'],['new-task-a','unseen-task-b'])
        self.assertEqual(plan['runtime_input']['tests'],3)
        self.assertEqual(plan['maximum_optimizer_steps'],256)
        self.assertEqual(plan['maximum_generations'],12)
        self.assertEqual(set(materials),set(challenges()))
        self.assertEqual(sorted(sum(plan['allocation']['queues'],[])),sorted(challenges()))
        self.assertTrue(all(a['mode']=='solve' for a in plan['worker_attempts']))

    def test_test_truth_is_rejected_before_material_preparation(self):
        data=challenges();data['new-task-a']['test'][0]['output']=[[9]]
        with patch.object(adapter,'public_training_material') as prepare:
            with self.assertRaises(ValueError):adapter.runtime_plan({},data,None,None,5000)
        prepare.assert_not_called()

    def test_infeasible_full_workload_rejects_without_skipping(self):
        specs={'a':{'child_seconds':500},'b':{'child_seconds':400}}
        with self.assertRaises(RuntimeError):adapter.allocate(specs,100)

    def test_partial_first_search_does_not_skip_second_test(self):
        checkpoints=[];deadlines=[];state=SimpleNamespace(generation_deadline=0)
        def solve(index):
            deadlines.append(state.generation_deadline)
            return {'test_index':index,'termination_reason':'source_dfs_deadline' if index==0 else 'all_source_batches_completed',
                    'attempts':[[[index]]],'missing_attempts':1}
        values,errors=adapter.run_all_tests(challenges(),'new-task-a',solve,
            lambda value:checkpoints.append(json.loads(json.dumps(value))),state,500,180,now=lambda:100)
        self.assertEqual([v['test_index'] for v in values],[0,1]);self.assertEqual(errors,[])
        self.assertEqual(len(checkpoints),2);self.assertEqual(deadlines,[280,280])

    def test_later_failure_preserves_prior_commit_and_denominator(self):
        checkpoints=[];state=SimpleNamespace(generation_deadline=0)
        def solve(index):
            if index:raise RuntimeError('retained real task failure')
            return {'test_index':0,'attempts':[[[2]]],'missing_attempts':1}
        values,errors=adapter.run_all_tests(challenges(),'new-task-a',solve,
            lambda value:checkpoints.append(json.loads(json.dumps(value))),state,500,180,now=lambda:100)
        self.assertEqual(values[0]['attempts'],[[[2]]]);self.assertEqual(values[1]['status'],'failed')
        self.assertEqual(values[1]['attempts'],[]);self.assertEqual(len(checkpoints[-1]),2)
        self.assertEqual(errors[0]['test_index'],1)

    def test_bridge_changes_only_assigned_uuid_gate(self):
        original=(Path(__file__).resolve().parents[1]/'tools/nvarc_native_submission.py').read_bytes()
        body=render.bridge(original).decode()
        self.assertIn("devices[index]['uuid']",body)
        self.assertIn('type(index) is int and 0<=index<4',body)
        self.assertIn('original source DFS token/beam/clock replay differs',body)
        self.assertIn('eight-view actual source verification input/answer differs',body)
        self.assertNotIn('--diagnostic-only',body)


class SingleWriteTransportTests(unittest.TestCase):
    def test_exclusive_reservation_survives_reopen(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'reserved.json'
            transport.reserve(path,{'candidate':'one','version':1})
            with self.assertRaises(FileExistsError):transport.reserve(path,{'candidate':'two','version':2})
            self.assertEqual(json.loads(path.read_bytes()),{'candidate':'one','version':1})

    def test_timeout_cannot_repeat_kernel_write(self):
        import subprocess
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);package=root/'package';package.mkdir()
            (package/'candidate-plan.json').write_text(json.dumps({'run_id':'nvarc-stage3-official-001'}))
            (package/'manifest.json').write_bytes(b'{}')
            with patch.object(transport,'JOURNAL',root),patch.object(transport,'preflight',return_value={'candidate_digest':'sha256:test'}),\
                 patch.object(transport.subprocess,'run',side_effect=subprocess.TimeoutExpired('kaggle',240)) as invoke:
                result=transport.push(package)
                self.assertTrue(result['unknown_outcome_for_write'])
                with self.assertRaises(FileExistsError):transport.push(package)
                self.assertEqual(invoke.call_count,1)
            self.assertTrue((root/'kernel-push.reserved.json').is_file())

    def test_formal_submission_uses_kernel_version_output_route_once(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);proof={'kernel':'danielwuu/nvarc-stage3-official-001','candidate_digest':'sha256:12345678'}
            def invoke(command,label,**kwargs):
                if label=='submissions-final-before':
                    (root/(label+'.stdout')).write_text('No submissions found');return {'returncode':0}
                return {'returncode':None,'unknown_outcome_for_write':True,'command':command}
            with patch.object(transport,'JOURNAL',root),patch.object(transport,'preflight'),\
                 patch.object(transport,'completion_preflight',return_value=proof),patch.object(transport,'invoke',side_effect=invoke) as call:
                result=transport.submit(root,root)
                self.assertIn('-k',result['command']);self.assertIn('--version',result['command'])
                self.assertNotIn('-v',result['command'])
                self.assertEqual(result['command'][result['command'].index('-f')+1],'submission.json')
                with self.assertRaises(FileExistsError):transport.submit(root,root)
                self.assertEqual(sum(c.args[1]=='formal-submit' for c in call.call_args_list),1)


if __name__=='__main__':unittest.main()
