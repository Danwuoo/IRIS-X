"""Synthetic CPU qualification orchestration; no native/model/GPU attestation."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import nvarc_e10_screen as runtime
from tools import nvarc_native_export as exporter
from tools import nvarc_calibration_gate as gates
from tools.stage_nvarc_e10_screen import full_task_gate_ids
from tools.nvarc_native_multitask import canonical,write


class FullTaskQualificationTests(unittest.TestCase):
    def test_all24_tasks_include18_noncalibration_tasks_and_reject_omission(self):
        tasks=['synthetic-'+str(i) for i in range(24)];challenges={task:{'test':[{'input':[[1]]}]} for task in tasks}
        self.assertEqual(full_task_gate_ids({'task_order':tasks},challenges),tasks)
        for subset in (tasks[:6],tasks[:-1],tasks+[tasks[-1]]):
            with self.assertRaisesRegex(RuntimeError,'every actual task exactly once'):
                full_task_gate_ids({'task_order':subset},challenges)

    def test_final_cpu_export_requires_all_bound_tasks_and_keeps300second_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);directory=root/'interleaved-r1';directory.mkdir()
            tasks=['control','empty-noncontrol'];write(directory/'plan.json',{'task_order':tasks})
            write(directory/'challenges.json',{task:{'test':[{'input':[[1]]}]} for task in tasks})
            screen={'maximum_notebook_wall_seconds':18000,'maximum_export_process_seconds':300}
            with patch.object(runtime.subprocess,'run') as run:
                runtime.cpu_export(root,'interleaved-r1',screen,Path('synthetic-model'),Path('synthetic-dependency'),
                    time.monotonic(),'a'*64,mandatory_tasks=tasks)
                command=run.call_args.args[0]
                self.assertEqual([command[i+1] for i,arg in enumerate(command) if arg=='--require-task-gates'],tasks)
                self.assertEqual(run.call_args.kwargs['timeout'],300)
                for subset in (None,tasks[:1]):
                    with self.assertRaisesRegex(RuntimeError,'all actual task gates'):
                        runtime.cpu_export(root,'interleaved-r1',screen,Path('synthetic-model'),Path('synthetic-dependency'),
                            time.monotonic(),'a'*64,mandatory_tasks=subset)
                self.assertEqual(run.call_count,1)
                # Earlier calibration is still permitted to check only controls.
                runtime.cpu_export(root,'interleaved-r1',screen,Path('synthetic-model'),Path('synthetic-dependency'),
                    time.monotonic(),'a'*64,validate_only=True,mandatory_tasks=tasks[:1])

    def export_fixture(self,root):
        challenges={task:{'train':[{'input':[[1]],'output':[[2]]}],'test':[{'input':[[3]]}]}
            for task in ('control','empty-noncontrol')}
        plan={'pythonhashseed':0,'approved':True,'export_verification_process':'fresh-cpu-startup-hashseed-0',
            'export_helper_sha256':hashlib.sha256(Path(exporter.__file__).read_bytes()).hexdigest(),
            'output_lifecycle_sha256':hashlib.sha256(Path(exporter.__file__).with_name('nvarc_output_lifecycle.py').read_bytes()).hexdigest(),
            'run_id':'synthetic-full-task-qualification','producer_sha256':'synthetic-no-native-source',
            'model_material_digest':'synthetic-no-model','source_inventory_digest':'synthetic-no-source',
            'task_order':list(challenges)}
        from tools.nvarc_native_multitask import digest
        plan['challenges_digest']=digest(challenges)
        evidence=[{'task_id':task,'checkpoint':{'tests':[{'attempts':[]}]}} for task in challenges]
        write(root/'plan.json',plan);write(root/'challenges.json',challenges);write(root/'worker-receipts.json',[])
        def qualified(_root,p,ch,ev,_tokenizer,context,**_kwargs):
            context.update(run_id=p['run_id'],plan_digest=digest(p),base_key_hashes={})
            bindings=exporter.native_bindings(root,p,ch,ev)
            return bindings,{'native-evidence.json':ev,'submission-audit.json':{'synthetic':True},
                'submission.json':{task:[] for task in ch},'export-process.json':context}
        tokenizer=SimpleNamespace(Tokenizer=SimpleNamespace(from_file=lambda _path:SimpleNamespace()))
        return plan,evidence,qualified,tokenizer

    def test_empty_noncontrol_gate_failure_prevents_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,evidence,qualified,tokenizer=self.export_fixture(root)
            seen=[]
            def fail(_root,_plan,_ch,_evidence,_tokens,tasks):
                seen.extend(tasks);raise RuntimeError('synthetic empty-noncontrol epoch failure')
            with patch.dict(sys.modules,{'tokenizers':tokenizer}),patch.object(exporter,'read_task_evidence',return_value=evidence), \
                 patch.object(exporter,'qualified_values',side_effect=qualified),patch.object(gates,'require_task_gates',side_effect=fail), \
                 self.assertRaisesRegex(RuntimeError,'empty-noncontrol epoch failure'):
                exporter.export(root,Path('synthetic-tokenizer'),require_tasks=plan['task_order'])
            self.assertEqual(seen,['control','empty-noncontrol']);self.assertFalse((root/'output-commit.json').exists())

    def test_producer_and_committed_readonly_replay_have_identical_full_task_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,evidence,qualified,tokenizer=self.export_fixture(root)
            def checked(_root,_plan,_ch,_evidence,_tokens,tasks):return {task:{'synthetic_stub_only':True} for task in tasks}
            with patch.dict(sys.modules,{'tokenizers':tokenizer}),patch.object(exporter,'read_task_evidence',return_value=evidence), \
                 patch.object(exporter,'qualified_values',side_effect=qualified),patch.object(gates,'require_task_gates',side_effect=checked):
                produced=exporter.export(root,Path('synthetic-tokenizer'),require_tasks=plan['task_order'])
                committed=(root/'output-commit.json').read_bytes()
                replayed=exporter.export(root,Path('synthetic-tokenizer'),require_tasks=plan['task_order'],
                    validate_only=True,verify_committed=True)
                self.assertEqual(produced['mandatory_task_gates'],replayed['mandatory_task_gates'])
                self.assertTrue(replayed['committed_projection_verified']);self.assertEqual((root/'output-commit.json').read_bytes(),committed)
                with self.assertRaisesRegex(RuntimeError,'committed native export identity differs'):
                    exporter.export(root,Path('synthetic-tokenizer'),require_tasks=plan['task_order'][:1],
                        validate_only=True,verify_committed=True)


if __name__=='__main__':unittest.main()
