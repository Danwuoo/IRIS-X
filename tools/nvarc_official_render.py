"""Reviewed minimal changes to the frozen native probe for full official input."""
from __future__ import annotations


def replace_once(text, old, new):
    if text.count(old)!=1:raise ValueError('frozen source anchor must occur exactly once: '+old[:100])
    return text.replace(old,new,1)


def worker(body):
    source=body.decode()
    source=replace_once(source,"['inventory'][0]['uuid']","['inventory'][spec['selected_gpu_index']]['uuid']")
    source=source.replace('actual worker UUID must bind parent rank zero','actual worker UUID must bind assigned parent L4')
    source=replace_once(source,"mode=attempt['mode'];spec=plan['task_specs'][task_id]",
        "mode=attempt['mode'];spec=plan['task_specs'][task_id]\n    require(mode=='solve' and plan['official_score_scope'] is True,'official solve only; no deliberate fault/control attempts')")
    # Remove the historical injected fault branch entirely from official bytes.
    start=source.index("            if mode=='fault-after-two-updates':")
    end=source.index('            start_training=',start)
    source=source[:start]+source[end:]
    source=replace_once(source,"from tools.nvarc_native_multitask import (Events, EvidenceModel, solve_test,\n        run_task_tests, training_deadline, write, digest as value_digest)",
        "from tools.nvarc_native_multitask import (Events, EvidenceModel, solve_test,\n        training_deadline, write, digest as value_digest)\n    from tools.nvarc_official_adapter import run_all_tests")
    source=replace_once(source,"tests,failure=run_task_tests(challenges,task_id,lambda index:solve_test(challenges,task_id,index,\n                    loader,solver,decoder,tokenizer,adapter,maximum_candidates=spec['maximum_candidate_sequences_per_test'],\n                    emit=events.emit),checkpoint)\n            if failure:failures.append({'phase':'solve',**failure})",
        "tests,errors=run_all_tests(challenges,task_id,lambda index:solve_test(challenges,task_id,index,\n                    loader,solver,decoder,tokenizer,adapter,maximum_candidates=spec['maximum_candidate_sequences_per_test'],\n                    emit=events.emit),checkpoint,adapter,adapter.generation_deadline,spec['per_test_seconds'])\n            failures.extend({'phase':'solve',**error} for error in errors)")
    source=source.replace("if mode!='baseline-only':","if mode=='solve':")
    source=source.replace("(mode=='baseline-only' or training_complete and len(tests)==len(challenges[task_id]['test']) and\n             all(t.get('native_complete') for t in tests))",
                          "(training_complete and len(tests)==len(challenges[task_id]['test']) and\n             all(t.get('native_complete') for t in tests))")
    compile(source,'official-native-worker','exec')
    return source.encode()


def bridge(body):
    source=body.decode()
    source=replace_once(source,"require(read(prefix+'hardware.json')['device_uuid']==devices[0]['uuid'],'task native UUID mapping differs')\n    spec=plan['task_specs'][task_id]",
        "spec=plan['task_specs'][task_id]\n    index=spec['selected_gpu_index']\n    require(type(index) is int and 0<=index<4 and\n        read(prefix+'hardware.json')['device_uuid']==devices[index]['uuid'],'task assigned native UUID mapping differs')")
    compile(source,'official-native-bridge','exec')
    return source.encode()
