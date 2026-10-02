"""Exact epoch reservations and independent cost reconstruction attacks."""
from collections import Counter
import copy
import math
import unittest

from irisx.arc_nvarc_qwen3_long_ttt import FORMAT,MATERIAL,adaptation_config,check_plan,reserve_row,row_digest
from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.verify_nvarc_original_long_ttt import validate_progress


def ledger():
    return {'outer_forwards_reserved':0,'input_tokens_reserved':0,'optimizer_steps_completed':0,
        'generation_calls':0,'teacher_calls':0,'verification_calls':0,'maximum_paid_usd':0,'forward_row_digests':[]}


class OriginalLongTTTTests(unittest.TestCase):
    def test_relabelled_repeated_and_overbudget_row_rejected_before_reservation(self):
        row={'input_ids':[14,1,15],'labels':[-100,1,15]};identity=row_digest(row)
        for altered,ceiling in (({**row,'labels':[-100,2,15]},3),(row,2)):
            state=ledger();remaining=Counter({identity:1});before=copy.deepcopy(state)
            with self.assertRaises(ValidationError):reserve_row(state,remaining,altered,ceiling)
            self.assertEqual(state,before);self.assertEqual(remaining[identity],1)
        state=ledger();remaining=Counter({identity:1});reserve_row(state,remaining,row,3)
        before=copy.deepcopy(state)
        with self.assertRaises(ValidationError):reserve_row(state,remaining,row,6)
        self.assertEqual(state,before)

    def test_reader_reconciles_all_duplicates_and_rejects_rehashed_step_cost(self):
        rows=[{'input_ids':[14,i%10,15],'labels':[-100,i%10,15]} for i in range(128)]
        state=ledger();remaining=Counter(row_digest(row) for row in rows);events=[]
        for i,row in enumerate(rows):
            reserve_row(state,remaining,row,384);state['optimizer_steps_completed']=i+1
            events.append({'event':'ttt-optimizer-returned','completed_steps':i+1,'source_view_index':i,
                'training_tokens':3*(i+1),'loss':1.,'learning_rate':5e-5*(i/13 if i<13 else
                    .5*(1+math.cos(math.pi*(i-13)/115)))})
        self.assertEqual(len(validate_progress(state,events,rows,True)),128)
        for key,value in (('training_tokens',4),('source_view_index',1),('learning_rate',5e-5)):
            bad=copy.deepcopy(events);bad[0][key]=value
            with self.assertRaises(ValidationError):validate_progress(state,bad,rows,True)
        for key in ('generation_calls','teacher_calls','verification_calls','maximum_paid_usd'):
            bad={**state,key:True}
            with self.assertRaises(ValidationError):validate_progress(bad,events,rows,True)
        prefix={**state,'outer_forwards_reserved':2,'input_tokens_reserved':6,
            'optimizer_steps_completed':1,'forward_row_digests':state['forward_row_digests'][:2]}
        self.assertEqual(len(validate_progress(prefix,events[:1],rows)),1)
        with self.assertRaises(ValidationError):validate_progress(prefix,events[:1],rows,True)

    def test_boolean_and_float_plan_budgets_cannot_alias_exact_integer_limits(self):
        config=adaptation_config();tasks=[{'task_id':'public-fixture','train':[
            {'input':[[1]],'output':[[1]]}],'test':[{'input':[[2]]}]}]
        plan={'format':FORMAT,'owner_decision':'Decision 0054','run_id':'nvarc-original-qwen3-long-ttt-002',
            'config_digest':digest_value(config),'visible_digest':digest_value(tasks),'model_material_digest':MATERIAL,
            'approved':True,'embedding_head_tied':False,'retain_export':False,'source_max_sequence_length':7464,
            'source_input_tokens':955392,'maximum_tasks':1,'maximum_optimizer_steps':128,'maximum_outer_forwards':128,
            'maximum_training_tokens':1048576,'maximum_generations':0,'maximum_verifications':0,'maximum_teacher_calls':0,
            'maximum_paid_usd':0,'maximum_notebook_wall_seconds':10800,'maximum_worker_wall_seconds':10560,
            'source_view_count':128,'model_instance_version_id':627758,'runtime_dataset_version':1,
            'competition_files_opened':0,'augmentation_count':16,'source_augmentation_seed':1,'reference_epoch_seed':42}
        check_plan(plan,config,tasks)
        for key,value in (('maximum_tasks',True),('maximum_generations',False),('maximum_optimizer_steps',128.),
                ('source_input_tokens',955392.),('source_max_sequence_length',7464.)):
            with self.assertRaises(ValidationError):check_plan({**plan,key:value},config,tasks)
        bad={**config,'gradient_checkpointing':1}
        with self.assertRaises(ValidationError):check_plan({**plan,'config_digest':digest_value(bad)},bad,tasks)


if __name__=='__main__':unittest.main()
