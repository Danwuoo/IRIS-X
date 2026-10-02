"""Closed, dependency-free recount of actual calls and complete numeric vectors.

No CUDA, model import, generation, evaluator answer or provider call is needed.
The reader recomputes the unchanged numeric gate even for a failed session.
"""
from __future__ import annotations

import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_qwen3_packing_diagnostic import FORMAT,ATOL,RTOL,ordered_rows,changed_rows,schedule
from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.verify_nvarc_qwen3_probe import check_architecture


def f32(value):
    return struct.unpack('<f',struct.pack('<f',value))[0]


def measurements(reference, actual, offsets, width=16):
    result = []
    for start,stop in zip(offsets,offsets[1:]):
        maximum = 0.0; outside = disagreements = 0
        for token in range(start,stop):
            begin = token*width
            lhs = reference[begin:begin+width]; rhs = actual[begin:begin+width]
            disagreements += max(range(width),key=lhs.__getitem__) != max(range(width),key=rhs.__getitem__)
            for a,b in zip(lhs,rhs):
                error = f32(abs(b-a)); maximum = max(maximum,error)
                outside += error > f32(ATOL+f32(f32(RTOL)*abs(a)))
        result.append({'max_absolute_error':maximum,'outside_tolerance':outside,
            'elements':(stop-start)*width,'argmax_disagreements':disagreements})
    return result


def verify(archive_path, package):
    plan = json.loads((package/'plan.json').read_bytes()); rows = json.loads((package/'samples.json').read_bytes())
    summary = json.loads((package/'stage-summary.json').read_bytes()); expected = schedule(rows)
    if (plan['format'] != FORMAT or plan['owner_decision'] != 'Decision 0054' or len(rows) != 8 or
            plan['data_digest'] != digest_value(rows) or plan['forward_schedule'] != expected or
            plan['atol'] != ATOL or plan['rtol'] != RTOL or plan['maximum_outer_forwards'] != len(expected) or
            plan['maximum_input_tokens'] != sum(x['input_tokens'] for x in expected) or
            any(type(plan[key]) is not int or plan[key] != 0 for key in
                ('maximum_optimizer_steps','maximum_generations','maximum_teacher_calls','maximum_paid_usd'))):
        raise ValidationError('fixed finite diagnostic plan differs')
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) > 64 or len(names) != len(set(names)) or 'manifest.json' not in names:
            raise ValidationError('closed diagnostic inventory differs')
        manifest = json.loads(archive.read('manifest.json'))
        entries = {x['path']:x for x in manifest['members']}
        if (len(entries) != len(manifest['members']) or set(names) != set(entries)|{'manifest.json'} or
                manifest['run_id'] != plan['run_id'] or manifest['plan_digest'] != digest_value(plan) or
                sum(x['bytes'] for x in entries.values()) > 96*1024**2):
            raise ValidationError('closed diagnostic plan/byte ceiling differs')
        content = {}
        for name,item in entries.items():
            if (name.startswith('/') or '\\' in name or any(p in {'','.','..'} for p in name.split('/')) or
                    type(item['bytes']) is not int or not 0 <= item['bytes'] <= 32*1024**2 or
                    archive.getinfo(name).file_size != item['bytes']):
                raise ValidationError('bounded member path/size differs')
            raw = archive.read(name)
            if hashlib.sha256(raw).hexdigest() != item['sha256']: raise ValidationError('member bytes differ')
            content[name] = raw
    def read(name): return json.loads(content[name])
    if read('plan.json') != plan or read('payload-bindings.json') != summary['payload_sha256']:
        raise ValidationError('returned exact plan/payload differs')
    terminal = read('terminal.json')
    if (terminal['run_id'] != plan['run_id'] or terminal['contains_evaluator_truth'] is not False or
            terminal['outcome'] not in {'complete','failed'}):
        raise ValidationError('terminal envelope differs')
    proof = {'format':'irisx/nvarc-original-qwen3-packing-diagnostic-verification-v1',
        'run_id':plan['run_id'],'plan_digest':digest_value(plan),'outcome':terminal['outcome'],
        'archive_sha256':hashlib.sha256(archive_path.read_bytes()).hexdigest(),'verified_members':len(entries),
        'correctness_scored':False,'full_sft_completed':False,'historical_nemo_unsloth_parity':False,'external_calls':0}
    hardware = read('hardware.json') if 'hardware.json' in content else None
    if hardware is not None:
        inventory = hardware['inventory']
        proof.update(observed_gpu_count=len(inventory),distinct_gpu_uuids=len({x['uuid'] for x in inventory}))
    ledger = read('worker/worker-ledger.json') if 'worker/worker-ledger.json' in content else []
    if not isinstance(ledger,list) or len(ledger) > len(expected): raise ValidationError('extra actual forward')
    calls = tokens = completed = 0
    for index,(event,wanted) in enumerate(zip(ledger,expected)):
        calls += 1; tokens += wanted['input_tokens']
        if (set(event) != set(wanted)|{'cumulative_forwards','cumulative_input_tokens','completed'} or
                any(event[key] != value for key,value in wanted.items()) or
                type(event['input_tokens']) is not int or type(event['cumulative_forwards']) is not int or
                type(event['cumulative_input_tokens']) is not int or
                event['cumulative_forwards'] != calls or event['cumulative_input_tokens'] != tokens or
                type(event['completed']) is not bool or not event['completed'] and index != len(ledger)-1):
            raise ValidationError('actual reserved input/order/completion prefix differs')
        completed += event['completed']
    proof.update(reserved_outer_forwards=calls,completed_outer_forwards=completed,reserved_input_tokens=tokens)
    layout,ordered = ordered_rows(rows); offsets = [0]
    for row in ordered: offsets.append(offsets[-1]+len(row['input_ids']))
    vectors = read('worker/vectors.json') if 'worker/vectors.json' in content else {}
    allowed = {'independent-flash-sdpa-logits','single-varlen-logits','packed-varlen-logits','isolation-logits',
        'independent-flash-sdpa-states','single-varlen-states','packed-varlen-states'}
    if set(vectors)-allowed: raise ValidationError('unexpected numerical vector')
    decoded = {}
    for name,meta in vectors.items():
        if (meta != {'path':name+'.f32le','shape':meta['shape'],'dtype':'float32-le'} or
                any(type(x) is not int or x < 1 for x in meta['shape'])):
            raise ValidationError('closed numerical vector schema differs')
        stage = 'actual-'+name.removesuffix('-logits').removesuffix('-states')
        if stage == 'actual-isolation': stage = 'actual-packed-isolation'
        done = sum(e['completed'] and e['stage'] == stage for e in ledger)
        if name.startswith(('independent','single')):
            prefix = done
            shape = [38,prefix,3,2560] if name.endswith('-states') else [1,offsets[prefix],16]
        else:
            shape = [38,8,3,2560] if name.endswith('-states') else [1,offsets[-1],16]
            if done != 1: raise ValidationError('vector precedes its completed forward')
        if meta['shape'] != shape: raise ValidationError('vector source prefix/shape differs')
        raw = content['worker/'+meta['path']]
        if len(raw) != math.prod(shape)*4: raise ValidationError('vector element count differs')
        values = array('f'); values.frombytes(raw)
        if sys.byteorder != 'little': values.byteswap()
        if not all(math.isfinite(x) for x in values): raise ValidationError('nonfinite numerical vector')
        decoded[name] = values
    if {name for name in content if name.endswith('.f32le')} != {'worker/'+meta['path'] for meta in vectors.values()}:
        raise ValidationError('undeclared numerical vector')
    if any(name.endswith('-states') for name in decoded):
        policy = read('worker/sampled-states-policy.json')
        if policy != {'row_indices':[s['row_index'] for s in layout['segments']],
                'local_token_positions':[[0,len(r['input_ids'])//2,len(r['input_ids'])-1] for r in ordered],
                'layers':['embed_tokens']+[f'layer-{i}' for i in range(36)]+['norm'],
                'shape':[38,8,3,2560],'no_additional_forward':True}:
            raise ValidationError('fixed sampled hidden-state locations differ')
        if all(name+'-states' in decoded and vectors[name+'-states']['shape'] == [38,8,3,2560]
                for name in ('independent-flash-sdpa','single-varlen','packed-varlen')):
            layered = {}
            stride = 8*3*2560
            for lhs,rhs in [('independent-flash-sdpa','single-varlen'),('single-varlen','packed-varlen')]:
                a = decoded[lhs+'-states']; b = decoded[rhs+'-states']
                errors = [max(abs(x-y) for x,y in zip(a[i*stride:(i+1)*stride],b[i*stride:(i+1)*stride])) for i in range(38)]
                layered[rhs+'-vs-'+lhs] = {'max_absolute_errors':errors,
                    'first_nonbitwise_sampled_layer':next((policy['layers'][i] for i,x in enumerate(errors) if x != 0),None)}
            proof['independently_recomputed_sampled_state_comparisons'] = layered
    if 'worker/actual-weight-differential.json' in content:
        if not {'independent-flash-sdpa-logits','single-varlen-logits','packed-varlen-logits'} <= set(decoded):
            raise ValidationError('complete primary vectors required')
        report = read('worker/actual-weight-differential.json')
        if (report['atol'] != ATOL or report['rtol'] != RTOL or report['offsets'] != offsets or
                report['all_logits_retained'] is not True or not math.isfinite(report['packed_token_mean_loss']) or
                len(report['timings']) != 3 or any(type(x['seconds']) not in {int,float} or
                not math.isfinite(x['seconds']) or x['seconds'] < 0 for x in report['timings'])):
            raise ValidationError('numeric report/gate differs')
        comparisons = {}
        for lhs,rhs in [('independent-flash-sdpa','single-varlen'),('single-varlen','packed-varlen'),
                ('independent-flash-sdpa','packed-varlen')]:
            comparisons[rhs+'-vs-'+lhs] = measurements(decoded[lhs+'-logits'],decoded[rhs+'-logits'],offsets)
        if report['comparisons'] != comparisons: raise ValidationError('independently recomputed numeric errors differ')
        for name,items in comparisons.items():
            for actual,wanted in zip(report['comparisons'][name],items):
                if any(type(actual[key]) is not type(value) for key,value in wanted.items()):
                    raise ValidationError('numerical count/value types differ')
        proof.update(independently_recomputed_logit_comparisons=comparisons,
            fixed_numerical_gate_passed=not any(x['outside_tolerance'] for x in
                comparisons['packed-varlen-vs-independent-flash-sdpa']))
    if 'worker/isolation.json' in content:
        if not {'packed-varlen-logits','isolation-logits'} <= set(decoded): raise ValidationError('isolation vectors required')
        isolation = read('worker/isolation.json'); tail = offsets[1]*16
        equal = decoded['packed-varlen-logits'][tail:] == decoded['isolation-logits'][tail:]
        if (type(isolation['unchanged_later_samples_bitwise_equal']) is not bool or
                isolation['unchanged_later_samples_bitwise_equal'] != equal or
                isolation['original_prefix_digest'] != digest_value(rows) or
                isolation['changed_prefix_digest'] != digest_value(changed_rows(rows))):
            raise ValidationError('independently recomputed isolation differs')
        proof['independently_recomputed_packed_isolation'] = equal
    if terminal['outcome'] == 'complete':
        if (hardware is None or len(hardware['inventory']) != 4 or proof['distinct_gpu_uuids'] != 4 or
                hardware['torch'] != '2.10.0+cu128' or any(x['name'] != 'NVIDIA L4' or x['bf16'] is not True for x in hardware['inventory']) or
                completed != len(expected) or set(decoded) != allowed or not proof.get('fixed_numerical_gate_passed') or
                not proof.get('independently_recomputed_packed_isolation') or
                terminal['plan_digest'] != digest_value(plan) or any(type(terminal[key]) is not int or terminal[key] != 0
                    for key in ('generation_calls','optimizer_steps')) or
                terminal['reserved_outer_forwards'] != calls or terminal['reserved_input_tokens'] != tokens or
                terminal['model_material_digest'] != plan['model_material_digest'] or
                read('material-verification.json') != {'all_files_verified':True,'material_digest':plan['model_material_digest']}):
            raise ValidationError('complete diagnostic envelope differs')
        check_architecture(read('worker/loaded-config.json'))
        gradient = read('worker/tiny-gradient-differential.json')
        if (gradient['atol'] != 0.006 or gradient['rtol'] != 0.06 or len(gradient['gradient_tensors']) != 24 or
                len({x['name'] for x in gradient['gradient_tensors']}) != 24 or any(not math.isfinite(x['max_absolute_error']) or
                    x['max_absolute_error'] < 0 for x in gradient['gradient_tensors'])):
            raise ValidationError('tiny gradient observation differs')
        proof['native_varlen_gpu_differential_observed'] = True
        proof.update(model_material_digest=plan['model_material_digest'],source_input_tokens=offsets[-1],
            source_supervised_tokens=sum(sum(x>=0 for x in row['labels'][1:]) for row in rows),
            numeric_verification_scope='complete retained CUDA logits, sampled states, isolation and actual-call costs independently recomputed')
    else:
        proof.update(failure_phase=terminal['phase'],error_type=terminal['error_type'],error_message=terminal['error_message'])
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('archive','package','output'): parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args(); result = verify(args.archive,args.package); atomic(args.output,result)
    print(json.dumps(result))
