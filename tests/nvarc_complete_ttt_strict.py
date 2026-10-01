"""Actual tiny trained export through complete TTT and source inference ledger."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import torch
from irisx.arc_nvarc_complete_ttt import run,complete_config
from irisx.arc_nvarc_long_ttt import run as run_resource,resource_config
from irisx.arc_nvarc_m2 import create_tiny_qwen_material
from irisx.arc_nvarc_representation import export_trained_model
from irisx.arc_nvarc_source_sft import tensor_inventory
from irisx.arc_nvarc_training import task_local_sequences
from irisx.arc_nvarc_source_bundle import build_bundle
from irisx.arc_nvarc_data import visible_task
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
from tests import nvarc_method_strict as method_tests
from tools.verify_nvarc_overnight_run import verify_export_tensors,verify_ttt,verify_long_resource

ROOT=Path(__file__).resolve().parents[1]


class CompleteTTTStrictTests(unittest.TestCase):
    def test_trained_export_complete_epoch_16_calls_probes_and_reset(self):
        threads=torch.get_num_threads();torch.set_num_threads(1)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                model,base=create_tiny_qwen_material(root/'base')
                optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4)
                ids=torch.tensor([[14,11,1,12,2,15]])
                loss=model(input_ids=ids,labels=ids,use_cache=False).loss
                loss.backward();optimizer.step();optimizer.zero_grad(set_to_none=True)
                identity=digest_value({'fixture':'one actual tiny optimizer step','base':base,'rows':ids.tolist()})
                material=export_trained_model(model,root/'base',root/'trained',training_identity_digest=identity)
                self.assertEqual(len(tensor_inventory(model)),verify_export_tensors(root/'trained',tensor_inventory(model)))
                del model,optimizer
                binding=build_bundle(ROOT/'.irisx/arc-agi-2/qwen35-nvarc/source',
                    ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json',root/'bundle')
                task=copy.deepcopy(method_tests.TASK);task['test']=task['test'][:1]
                raw={task['task_id']:{'train':task['train'],'test':task['test']}}
                tasks=[visible_task(key,value) for key,value in raw.items()]
                config=complete_config()
                rows=task_local_sequences(tasks[0],seed=42,augmentation_count=16,source_qwen=True,
                    source_augmentation_seed=1,source_max_length=8192)
                plan={'format':'irisx/nvarc-complete-ttt-v1','run_id':'nvarc-overnight-ttt-000','backend':'cpu-fixture',
                    'maximum_paid_usd':0,'maximum_teacher_calls':0,'config_digest':digest_value(config),
                    'visible_digest':digest_value(tasks),'maximum_tasks':1,'maximum_generations':16,
                    'maximum_optimizer_steps':128,'maximum_verifications':34,'maximum_outer_model_forwards':66000,
                    'material_digest':material,'training_identity_digest':identity,'source_bundle_digest':binding['bundle_digest'],
                    'source_epoch_input_tokens':sum(len(row['input_ids']) for row in rows)}
                for name,value in (('plan',plan),('visible',raw),('config',config)):
                    (root/(name+'.json')).write_bytes(canonical_bytes(value,newline=True))
                report=run(root/'plan.json',root/'trained',root/'visible.json',root/'config.json',root/'bundle',root/'output')
                self.assertEqual((128,16,16),(report['ttt']['steps'],report['ledger']['generation_calls_reserved'],report['ledger']['generation_calls_completed']))
                self.assertEqual(128,report['ledger']['ttt_optimizer_steps_observed'])
                self.assertEqual(128,len([event for event in (root/'output/events.jsonl').read_text().splitlines() if json.loads(event)['event']=='ttt-optimizer-returned']))
                self.assertTrue(report['adapter_reset_exact'])
                self.assertFalse(report['correctness_scored'])
                self.assertEqual(2,len(report['demonstration_verifier_probes']))
                self.assertTrue(all(not probe['model_candidate'] for probe in report['demonstration_verifier_probes']))
                # An independent terminal reader reconstructs source inputs and
                # reconciles actual optimizer/call events without model calls.
                package=root/'package-l4';package.mkdir()
                (package/'visible.json').write_bytes(canonical_bytes(raw,newline=True))
                import shutil
                shutil.copytree(root/'bundle',package/'source-bundle')
                independent=verify_ttt(root,plan,{'worker/result.json':(root/'output/result.json').read_bytes(),
                    'worker/events.jsonl':(root/'output/events.jsonl').read_bytes()})
                self.assertEqual(128,independent['optimizer_steps'])
                self.assertEqual(16,independent['generation_calls'])
                altered=copy.deepcopy(report);altered['ledger']['outer_model_forwards_reserved']+=1
                with self.assertRaisesRegex(ValidationError,'model forward ledger'):
                    verify_ttt(root,plan,{'worker/result.json':canonical_bytes(altered),
                        'worker/events.jsonl':(root/'output/events.jsonl').read_bytes()})
                resource=resource_config()
                resource_rows=task_local_sequences(tasks[0],seed=42,augmentation_count=1,source_qwen=True,
                    source_augmentation_seed=1,source_max_length=8192)
                resource_plan={**plan,'format':'irisx/nvarc-long-ttt-resource-v1','approved':True,'owner_decision':'Decision 0053',
                    'config_digest':digest_value(resource),'maximum_optimizer_steps':8,'maximum_generations':0,
                    'maximum_verifications':0,'maximum_outer_model_forwards':8,
                    'source_epoch_input_tokens':sum(len(row['input_ids']) for row in resource_rows),
                    'source_epoch_max_sequence_length':max(len(row['input_ids']) for row in resource_rows)}
                (root/'resource-plan.json').write_bytes(canonical_bytes(resource_plan,newline=True))
                (root/'resource-config.json').write_bytes(canonical_bytes(resource,newline=True))
                resource_report=run_resource(root/'resource-plan.json',root/'trained',root/'visible.json',
                    root/'resource-config.json',root/'bundle',root/'resource-output')
                resource_data={'worker/result.json':(root/'resource-output/result.json').read_bytes(),
                    'worker/events.jsonl':(root/'resource-output/events.jsonl').read_bytes()}
                proof=verify_long_resource(root,resource_plan,resource_data)
                self.assertEqual((8,0,0),(proof['optimizer_steps'],proof['generation_calls'],proof['verification_calls']))
                self.assertTrue(resource_report['adapter_reset_exact'])
                self.assertFalse(resource_report['original_128_view_epoch_verified'])
                altered=copy.deepcopy(resource_report);altered['ledger']['outer_model_forwards_reserved']=9
                with self.assertRaisesRegex(ValidationError,'forward/reset/claim'):
                    verify_long_resource(root,resource_plan,{**resource_data,'worker/result.json':canonical_bytes(altered)})
                raw[task['task_id']]['test'][0]['output']=[[1]]
                (root/'visible.json').write_bytes(canonical_bytes(raw,newline=True))
                with self.assertRaisesRegex(ValidationError,'test answers'):
                    run(root/'plan.json',root/'trained',root/'visible.json',root/'config.json',root/'bundle',root/'rejected')
                self.assertFalse((root/'rejected').exists())
        finally:torch.set_num_threads(threads)


if __name__=='__main__':unittest.main()
