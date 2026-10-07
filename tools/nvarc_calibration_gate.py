"""Independent mandatory calibration gates, including zero-candidate tasks."""
import math
from pathlib import Path
from types import SimpleNamespace
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import digest,require
from tools.nvarc_native_solve_runtime import load_sources
from tools.nvarc_native_submission import reject_truth,task_binding,verify_native_training_gate
from tools.nvarc_public_eval import PhaseTelemetry


def verify_epoch_ledger(ledger,schedule,spec,expected_rows,parameter_count):
    from collections import Counter
    from tools.nvarc_native_ttt_schedule import SOURCES,FUNCTIONS,ulp_distance
    require(set(ledger)=={'forwards','training_steps','optimizer_steps','optimizer_constructions','generation_calls','teacher_calls'} and
        ledger['generation_calls']==ledger['teacher_calls']==0 and ledger['optimizer_constructions']==[{'completed':True}] and
        len(expected_rows)==128 and all(len(ledger[key])==128 for key in ('forwards','training_steps','optimizer_steps')) and
        all(row=={'completed':True} for row in ledger['training_steps']), 'closed complete calibration optimizer construction/step ledger required')
    require(schedule['source_sha256']==SOURCES and schedule['function_sha256']==FUNCTIONS and
        schedule['warmup_steps']==13 and schedule['epoch_steps']==128 and len(schedule['rates'])==129 and
        all(ulp_distance(a,b)<=4 for a,b in zip(schedule['rates'],spec['source_learning_rates'])) and
        schedule['rates'][0]==schedule['rates'][-1]==0 and schedule['rates'][13]==5e-5,
        'unchanged same-platform native scalar schedule/reference bound required')
    fields=('input_ids_digest','labels_digest','input_tokens','supervised_tokens')
    require(Counter(tuple(row[key] for key in fields) for row in ledger['forwards'])==
        Counter(tuple(row[key] for key in fields) for row in expected_rows) and
        all(set(row)==set(fields)|{'completed','loss'} and row['completed'] is True and
            type(row['loss']) in (int,float) and math.isfinite(row['loss']) for row in ledger['forwards']),
        'exact full source-row/token multiset and finite native loss closure required')
    for index,row in enumerate(ledger['optimizer_steps']):
        require(set(row)=={'learning_rate','gradient_tensors','gradient_norm_after_clip','completed'} and
            row['completed'] is True and row['learning_rate']==schedule['rates'][index] and
            row['gradient_tensors']==parameter_count and type(row['gradient_norm_after_clip']) in (int,float) and
            math.isfinite(row['gradient_norm_after_clip']) and 0<=row['gradient_norm_after_clip']<=1.05,
            'calibration exact optimizer LR/gradient/step closure differs')


def verify_host_telemetry(value,test_count):
    template=PhaseTelemetry().snapshot();expected=set(template)
    require(isinstance(value,dict) and set(value)==expected and value['format']=='irisx/nvarc-host-telemetry-v1' and
        value['gpu_kernel_seconds'] is None and value['added_device_synchronizations']==0 and
        value['per_token_telemetry_writes']==0 and value['detailed_profiling'] is False,
        'closed native calibration host telemetry required')
    require(all(value[key]==template[key] for key in ('clock','gpu_timing_semantics','aggregation','unobserved_phase_policy')) and
        value['detail_inclusive_host_seconds'] is None,'fixed host observation clock/overlap/unknown semantics required')
    exclusive=value['exclusive_host_seconds'];inclusive=value['inclusive_host_seconds']
    require(set(exclusive)==set(inclusive)==set(PhaseTelemetry.PHASES) and
        all(v is None or type(v) in (int,float) and math.isfinite(v) and v>=0 for v in list(exclusive.values())+list(inclusive.values())) and
        all(inclusive[phase] is not None for phase in ('preparation','training','reset','control','generation')) and
        type(value['elapsed_host_seconds']) in (int,float) and math.isfinite(value['elapsed_host_seconds']) and
        type(value['unscoped_host_seconds']) in (int,float) and value['unscoped_host_seconds']>=0 and
        math.isclose(sum(v or 0 for v in exclusive.values())+value['unscoped_host_seconds'],value['elapsed_host_seconds'],abs_tol=1e-6) and
        set(value['tests'])=={str(i) for i in range(test_count)},'calibration phase partition/test observations differ')
    require(all((exclusive[phase] is None)==(inclusive[phase] is None) and
        (exclusive[phase] is None or exclusive[phase]<=inclusive[phase]+1e-9) for phase in PhaseTelemetry.PHASES) and
        all(exclusive[phase] is not None for phase in ('preparation','training','reset','control','generation')),
        'exclusive calibration phase cannot exceed its inclusive observation or claim an unknown phase')


def require_task_gates(root,plan,challenges,evidence,tokenizer,tasks):
    import numpy as np
    require(isinstance(tasks,list) and tasks and len(set(tasks))==len(tasks) and set(tasks)<=set(challenges),
            'distinct actual mandatory calibration task list required')
    loader,_,_=load_sources(root,SimpleNamespace(no_grad=lambda:lambda function:function),np)
    checked={}
    for key in tasks:
        record=next(row for row in evidence if row['task_id']==key)
        require(record['provenance']=='native-model' and record['receipt']['status']=='complete' and
            record['receipt']['launched'] is True and record['receipt']['returncode']==0,
            'calibration needs completed actual native process')
        # Deliberately unconditional, even when every candidate pool is empty.
        training=verify_native_training_gate(root,plan,challenges,key,loader,tokenizer)
        directory=Path(root)/'tasks'/key/'native'
        def read(name):
            value=parse_json((directory/name).read_bytes());reject_truth(value);return value
        before=read('baseline-inventory.json');after=read('reset-inventory.json')
        from tools.nvarc_native_multitask import public_training_material
        expected=public_training_material(loader,tokenizer,key,challenges[key])['rows']
        verify_epoch_ledger(read('training-ledger.json'),read('native-schedule.json'),plan['task_specs'][key],
                            expected,len(plan['source_inferred_trainable_layout']))
        control=read('cache-control.json');reset=read('post-reset-control.json');result=read('result.json')
        require(before==after and reset['prefill']==control['baseline_prefill'] and
            reset['prefill_bitwise_equal'] is True and reset['additional_model_calls']==1 and
            result['binding']==task_binding(plan,challenges,key) and result['training_complete'] is True and
            result['all_saved_tensors_restored'] is result['post_reset_control_verified'] is result['optimizer_discarded'] is True,
            'independent calibration reset/source result binding differs')
        count=len(challenges[key]['test']);verify_host_telemetry(result['telemetry'],count)
        checkpoint=record['checkpoint'];require(checkpoint is not None and len(checkpoint['tests'])==count,
                                               'calibration full actual-test checkpoint required')
        for test in checkpoint['tests']:
            require('telemetry' in test and result['telemetry']['tests'][str(test['test_index'])]==test['telemetry'],
                    'root calibration telemetry differs from independently replayed test evidence')
        checked[key]={'training':training,'reset_inventory_digest':digest(after),'host_telemetry_digest':digest(result['telemetry'])}
    return checked
