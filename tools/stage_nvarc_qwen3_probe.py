"""Offline immutable original Qwen3 probe package and exact preflight."""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools import irisx_build_backend as build
from tools.nvarc_qwen3_material import DEFAULT, inventory
from irisx.arc_nvarc_combined import atomic,sha
from irisx.arc_nvarc_packing import pack_sequences
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
from irisx.arc_nvarc_qwen3_packing_diagnostic import FORMAT as DIAGNOSTIC_FORMAT, schedule as diagnostic_schedule
from irisx.arc_nvarc_qwen3_operator_probe import FORMAT as OPERATOR_FORMAT, schedule as operator_schedule, MODES as OPERATOR_MODES
from irisx.arc_nvarc_qwen3_segmented_probe import FORMAT as SEGMENTED_FORMAT, schedule as segmented_schedule


def segmented_prerequisite():
    folder=ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-probe-003'
    proof=folder/'independent-verification.json';ledger=json.loads((folder/'execution-final/execution-ledger.json').read_bytes())
    if (sha(proof)!='a2514650b8b87ca7c0eddd53329e4a77b0216d4afd17edc053c6a63890c7e417' or
            ledger['terminal_observed'] is not True or ledger['retrieval_reserved']!=1 or
            ledger['events'][-1]['outcome']!='retrieved' or sha(folder/'execution-final/retrieved/gpu-preflight-result.zip')!=
            '3f54f470163a0b35a6baba75c3ebd57f9afca021542864b6768a9b3a09fb0f07'):
        raise ValidationError('exact complete once-retrieved first-layer linear localization required')
    return sha(proof)


def segmented_source(run,encoded,hashes):
    source=(ROOT/'tools/nvarc_qwen3_probe_notebook.py.tmpl').read_text(encoding='utf-8')
    source=source.replace('irisx.arc_nvarc_qwen3_probe','irisx.arc_nvarc_qwen3_segmented_probe')
    source=source.replace("plan['maximum_notebook_wall_seconds']!=1800","plan['maximum_notebook_wall_seconds']!=1200")
    for key,value in {'__RUN__':json.dumps(run),'__PAYLOADS__':json.dumps(encoded),'__HASHES__':json.dumps(hashes),
        '__HARDWARE_HELPER__':(ROOT/'src/irisx/arc_nvarc_hardware.py').read_text(encoding='utf-8')}.items():source=source.replace(key,value)
    return source


def operator_prerequisite():
    folder=ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-probe-002'
    path=folder/'independent-verification.json';ledger=json.loads((folder/'execution-final/execution-ledger.json').read_bytes())
    proof=json.loads(path.read_bytes())
    if (sha(path)!='13f56f4ebb7fef1f43b6fa911055fa8c7115d2337b1470be41c065adec058970' or
            ledger['terminal_observed'] is not True or ledger['retrieval_reserved']!=1 or
            ledger['events'][-1]['outcome']!='retrieved' or
            sha(folder/'execution-final/retrieved/gpu-preflight-result.zip')!='1a300e4a60ed062e1f3c6036910e47bcc464d3de2a4612def8472d997825de14' or
            proof['completed_outer_forwards']!=21 or proof['fixed_numerical_gate_passed'] is not False or
            proof['independently_recomputed_packed_isolation'] is not True or any(row['max_absolute_error']!=0 for row in
                proof['independently_recomputed_logit_comparisons']['single-varlen-vs-independent-flash-sdpa'])):
        raise ValidationError('exact closed merged-shape numerical failure required')
    return sha(path)


def stage(output,run,diagnostic=False,operator=False,segmented=False):
    if sum((diagnostic,operator,segmented))>1:raise ValidationError('one distinct probe purpose required')
    if output.exists() or not re.fullmatch(r'nvarc-original-qwen3-probe-\d{3}',run):
        raise ValidationError('new immutable original-family probe required')
    material=json.loads((DEFAULT/'conversion.json').read_bytes())
    proof=json.loads((DEFAULT/'independent-verification.json').read_bytes())
    if proof['material_digest']!=material['material_digest'] or inventory(DEFAULT/'compact')!=material['compact_inventory']:
        raise ValidationError('independently byte-verified original material required')
    prefix=ROOT/'.irisx/nvarc-original/materials/source-shuffle-prefix-20261002-001'
    rows=json.loads((prefix/'samples.json').read_bytes())[:8]
    pack_sequences(rows)
    count=sum(len(row['input_ids']) for row in rows)
    plan={'format':'irisx/nvarc-original-qwen3-probe-v1','approved':True,'owner_decision':'Decision 0054',
        'run_id':run,'kernel_id':'danielwuu/'+run,'backend':'torch-2.10-native-varlen-flash',
        'maximum_notebook_wall_seconds':1800,'maximum_worker_wall_seconds':1200,
        'maximum_outer_forwards':13,'maximum_input_tokens':count*3+44,'maximum_optimizer_steps':0,
        'maximum_generations':0,'maximum_teacher_calls':0,'maximum_paid_usd':0,'retain_export':False,
        'actual_model_sample_count':8,'actual_model_input_tokens_per_pass':count,'actual_model_passes':3,
        'tiny_gradient_rows':2,'tiny_gradient_input_tokens':44,'tiny_gradient_backwards':2,
        'data_digest':digest_value(rows),'source_prefix_sha256':sha(prefix/'samples.json'),
        'model_material_digest':material['material_digest'],'material_manifest_sha256':sha(DEFAULT/'conversion.json'),
        'model_repo':material['repo'],'model_revision':material['revision'],
        'model_dataset_version':1,'datasets':{'base':'danielwuu/irisx-nvarc-original-qwen3-001',
            'wheels':'danielwuu/irisx-arc-agi-2-trial-002-smoke-001'},
        'competition_sources':['arc-prize-2026-arc-agi-2'],'competition_files_opened':0,
        'hardware_gate':'four distinct BF16 L4s; single rank-zero model worker',
        'original_sft_checkpoint':False,'historical_base_commit_known':False,'full_sft_completed':False,
        'original_nemo_version':None,'original_unsloth_version':None,
        'material_policy':'original-reproduction; retain all source parent/exposure tags; no evaluator answers',
        'execution_control':'private Internet-disabled SAVE_AND_RUN_ALL; finite status checks; one terminal retrieval'}
    if diagnostic:
        scheduled=diagnostic_schedule(rows)
        plan.update(format=DIAGNOSTIC_FORMAT, predecessor_run_id='nvarc-original-qwen3-probe-001',
            predecessor_archive_sha256='be6cfbb2e0608e9d328c8eec9b8d3a3df562aa00a6e36e8a06f40c32aee33025',
            maximum_outer_forwards=len(scheduled),maximum_input_tokens=sum(x['input_tokens'] for x in scheduled),
            actual_model_passes=4,forward_schedule=scheduled,atol=0.25,rtol=0.03,
            sdpa_backend='FLASH_ATTENTION only; no math/cuDNN fallback',
            numerical_modes=['independent-flash-sdpa','single-varlen','packed-varlen','packed-isolation'],
            retain_full_logits=True,retain_sampled_states={'layers':38,'rows':8,'positions_per_row':3,'hidden_size':2560},
            extra_model_calls_from_hooks=0,maximum_attention_reference_calls=0,
            diagnostic_scope='backend and physical batch-shape decomposition; unchanged fixed numerical gate')
    if operator:
        prerequisite=operator_prerequisite();scheduled=operator_schedule(rows)
        plan.update(format=OPERATOR_FORMAT,predecessor_run_id='nvarc-original-qwen3-probe-002',
            maximum_notebook_wall_seconds=1200,maximum_worker_wall_seconds=900,
            predecessor_archive_sha256='1a300e4a60ed062e1f3c6036910e47bcc464d3de2a4612def8472d997825de14',
            predecessor_verification_sha256=prerequisite,maximum_outer_forwards=len(scheduled),
            maximum_input_tokens=sum(x['input_tokens'] for x in scheduled),actual_model_passes=7,
            forward_schedule=scheduled,original_decoder_layers=36,retained_decoder_layers=[0],
            maximum_decoder_layer_invocations=len(scheduled),tiny_gradient_rows=0,tiny_gradient_input_tokens=0,
            tiny_gradient_backwards=0,numerical_modes=list(OPERATOR_MODES),whole_model_numerical_qualification=False,
            weights_modified=False,retain_full_first_layer_logits=True,retain_all_sampled_operator_vectors=True,
            extra_model_calls_from_hooks=0,maximum_attention_reference_calls=0,
            precision_source_reference='https://docs.pytorch.org/docs/2.10/notes/numerical_accuracy.html',
            diagnostic_scope='one-layer operator localization only; fixed whole-model numerical gate remains unsatisfied')
    if segmented:
        scheduled=segmented_schedule(rows)
        plan.update(format=SEGMENTED_FORMAT,maximum_notebook_wall_seconds=1200,maximum_worker_wall_seconds=900,
            predecessor_run_id='nvarc-original-qwen3-probe-003',
            predecessor_archive_sha256='3f54f470163a0b35a6baba75c3ebd57f9afca021542864b6768a9b3a09fb0f07',
            predecessor_verification_sha256=segmented_prerequisite(),forward_schedule=scheduled,
            maximum_outer_forwards=len(scheduled),maximum_input_tokens=sum(row['input_tokens'] for row in scheduled),
            atol=0.25,rtol=0.03,sdpa_backend='FLASH_ATTENTION only; no math/cuDNN fallback',
            linear_policy='one unchanged BF16 GEMM per whole sample; attention remains native varlen',
            full_model_decoder_layers=36,full_model_linear_modules=253,tiny_linear_modules=15,
            maximum_segment_gemm_calls=4078,retain_full_logits=True,
            retain_sampled_states={'layers':38,'rows':8,'positions_per_row':3,'hidden_size':2560},
            extra_model_calls_from_hooks=0,weights_modified=False,stored_and_compute_dtype='bfloat16',
            diagnostic_scope='whole-model fixed numerical gate plus tiny native varlen gradients and sample isolation')
    (output/'wheel').mkdir(parents=True)
    wheel=output/'wheel'/build.build_wheel(str(output/'wheel'))
    payload={'plan':canonical_bytes(plan,newline=True),'samples':canonical_bytes(rows,newline=True),
        'runtime_wheel':wheel.read_bytes(),'wheel_manifest':(ROOT/'trials/arc-agi-2-qwen35-nvarc/configs/base-wheel-manifest.json').read_bytes()}
    hashes={key:hashlib.sha256(value).hexdigest() for key,value in payload.items()}
    source=(ROOT/'tools/nvarc_qwen3_probe_notebook.py.tmpl').read_text(encoding='utf-8')
    if diagnostic:
        source=source.replace('irisx.arc_nvarc_qwen3_probe','irisx.arc_nvarc_qwen3_packing_diagnostic')
    if operator:
        source=source.replace('irisx.arc_nvarc_qwen3_probe','irisx.arc_nvarc_qwen3_operator_probe')
        source=source.replace("plan['maximum_notebook_wall_seconds']!=1800", "plan['maximum_notebook_wall_seconds']!=1200")
    if segmented:
        source=source.replace('irisx.arc_nvarc_qwen3_probe','irisx.arc_nvarc_qwen3_segmented_probe')
        source=source.replace("plan['maximum_notebook_wall_seconds']!=1800", "plan['maximum_notebook_wall_seconds']!=1200")
    for key,value in {'__RUN__':json.dumps(run),'__PAYLOADS__':json.dumps({k:base64.b64encode(zlib.compress(v,9)).decode() for k,v in payload.items()}),
        '__HASHES__':json.dumps(hashes),'__HARDWARE_HELPER__':(ROOT/'src/irisx/arc_nvarc_hardware.py').read_text(encoding='utf-8')}.items():
        source=source.replace(key,value)
    compile(source,'original-qwen3-probe','exec')
    (output/'kernel').mkdir()
    atomic(output/'plan.json',plan);(output/'samples.json').write_bytes(payload['samples'])
    atomic(output/'kernel/notebook.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},
        'cells':[{'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':source.splitlines(keepends=True)}]})
    atomic(output/'kernel/kernel-metadata.json',{'id':'danielwuu/'+run,'title':run,'code_file':'notebook.ipynb','language':'python',
        'kernel_type':'notebook','is_private':True,'enable_gpu':True,'enable_internet':False,
        'dataset_sources':list(plan['datasets'].values()),'competition_sources':plan['competition_sources'],'kernel_sources':[]})
    entries={p.relative_to(output).as_posix():sha(p) for p in output.rglob('*') if p.is_file()}
    atomic(output/'stage-summary.json',{'run_id':run,'plan_digest':digest_value(plan),'payload_sha256':hashes,'inventory':entries})
    return preflight(output)


def preflight(package):
    summary=json.loads((package/'stage-summary.json').read_bytes())
    actual={p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file() and p.name!='stage-summary.json'}
    if actual!=summary['inventory']:raise ValidationError('closed package bytes differ')
    plan=json.loads((package/'plan.json').read_bytes());rows=json.loads((package/'samples.json').read_bytes())
    diagnostic=plan['format']==DIAGNOSTIC_FORMAT
    operator=plan['format']==OPERATOR_FORMAT
    segmented=plan['format']==SEGMENTED_FORMAT
    expected_schedule=segmented_schedule(rows) if segmented else operator_schedule(rows) if operator else diagnostic_schedule(rows) if diagnostic else None
    expected_calls=len(expected_schedule) if expected_schedule is not None else 13
    expected_tokens=sum(x['input_tokens'] for x in expected_schedule) if expected_schedule is not None else sum(len(row['input_ids']) for row in rows)*3+44
    if (plan['owner_decision']!='Decision 0054' or plan['format'] not in {'irisx/nvarc-original-qwen3-probe-v1',DIAGNOSTIC_FORMAT,OPERATOR_FORMAT,SEGMENTED_FORMAT} or
            not re.fullmatch(r'nvarc-original-qwen3-probe-\d{3}',plan['run_id']) or
            plan['maximum_notebook_wall_seconds']!=(1200 if operator or segmented else 1800) or
            plan['maximum_worker_wall_seconds']!=(900 if operator or segmented else 1200) or
            plan['maximum_generations']!=0 or plan['maximum_teacher_calls']!=0 or plan['maximum_optimizer_steps']!=0 or
            plan['maximum_paid_usd']!=0 or plan['retain_export'] is not False or
            len(rows)!=8 or digest_value(rows)!=plan['data_digest'] or plan['maximum_outer_forwards']!=expected_calls or
            plan['maximum_input_tokens']!=expected_tokens or
            digest_value(plan)!=summary['plan_digest']):raise ValidationError('bounded owner probe plan differs')
    if diagnostic and (plan['forward_schedule']!=expected_schedule or plan['atol']!=0.25 or plan['rtol']!=0.03 or
            plan['sdpa_backend']!='FLASH_ATTENTION only; no math/cuDNN fallback' or
            plan['actual_model_passes']!=4 or plan['retain_full_logits'] is not True or
            plan['extra_model_calls_from_hooks']!=0 or plan['maximum_attention_reference_calls']!=0 or
            plan['retain_sampled_states']!={'layers':38,'rows':8,'positions_per_row':3,'hidden_size':2560} or
            plan['predecessor_run_id']!='nvarc-original-qwen3-probe-001' or
            plan['predecessor_archive_sha256']!='be6cfbb2e0608e9d328c8eec9b8d3a3df562aa00a6e36e8a06f40c32aee33025'):
        raise ValidationError('fixed numerical diagnostic boundaries differ')
    if operator and (plan['forward_schedule']!=expected_schedule or plan['actual_model_passes']!=7 or
            plan['original_decoder_layers']!=36 or plan['retained_decoder_layers']!=[0] or
            plan['maximum_decoder_layer_invocations']!=expected_calls or plan['tiny_gradient_rows']!=0 or
            plan['tiny_gradient_input_tokens']!=0 or plan['tiny_gradient_backwards']!=0 or
            plan['whole_model_numerical_qualification'] is not False or plan['weights_modified'] is not False or
            plan['numerical_modes']!=list(OPERATOR_MODES) or plan['retain_full_first_layer_logits'] is not True or
            plan['retain_all_sampled_operator_vectors'] is not True or plan['extra_model_calls_from_hooks']!=0 or
            plan['maximum_attention_reference_calls']!=0 or plan['predecessor_run_id']!='nvarc-original-qwen3-probe-002' or
            plan['predecessor_archive_sha256']!='1a300e4a60ed062e1f3c6036910e47bcc464d3de2a4612def8472d997825de14' or
            plan['predecessor_verification_sha256']!=operator_prerequisite()):
        raise ValidationError('exact partial-model operator boundaries differ')
    if operator and any(type(plan[k]) is not int for k in ('maximum_notebook_wall_seconds','maximum_worker_wall_seconds',
            'maximum_outer_forwards','maximum_input_tokens','maximum_generations','maximum_teacher_calls',
            'maximum_optimizer_steps','maximum_paid_usd','tiny_gradient_backwards','tiny_gradient_input_tokens',
            'maximum_decoder_layer_invocations','extra_model_calls_from_hooks','maximum_attention_reference_calls')):
        raise ValidationError('integer partial-model workload ceilings required')
    if segmented and (plan['forward_schedule']!=expected_schedule or plan['atol']!=0.25 or plan['rtol']!=0.03 or
            plan['linear_policy']!='one unchanged BF16 GEMM per whole sample; attention remains native varlen' or
            plan['sdpa_backend']!='FLASH_ATTENTION only; no math/cuDNN fallback' or
            plan['predecessor_run_id']!='nvarc-original-qwen3-probe-003' or
            plan['predecessor_archive_sha256']!='3f54f470163a0b35a6baba75c3ebd57f9afca021542864b6768a9b3a09fb0f07' or
            plan['predecessor_verification_sha256']!=segmented_prerequisite() or plan['weights_modified'] is not False or
            plan['stored_and_compute_dtype']!='bfloat16' or plan['full_model_decoder_layers']!=36 or
            plan['full_model_linear_modules']!=253 or plan['tiny_linear_modules']!=15 or
            plan['maximum_segment_gemm_calls']!=4078 or plan['retain_full_logits'] is not True or
            plan['tiny_gradient_rows']!=2 or plan['tiny_gradient_input_tokens']!=44 or plan['tiny_gradient_backwards']!=2 or
            plan['actual_model_passes']!=3 or plan['actual_model_sample_count']!=8 or
            plan['actual_model_input_tokens_per_pass']!=sum(len(row['input_ids']) for row in rows) or
            plan['extra_model_calls_from_hooks']!=0 or
            plan['retain_sampled_states']!={'layers':38,'rows':8,'positions_per_row':3,'hidden_size':2560}):
        raise ValidationError('fixed whole-model segmented-linear workload differs')
    if segmented:
        prefix=ROOT/'.irisx/nvarc-original/materials/source-shuffle-prefix-20261002-001/samples.json'
        material=json.loads((DEFAULT/'conversion.json').read_bytes())
        if (rows!=json.loads(prefix.read_bytes())[:8] or plan['source_prefix_sha256']!=sha(prefix) or
                any(plan[k]!=material[v] for k,v in [('model_material_digest','material_digest'),('model_repo','repo'),('model_revision','revision')]) or
                plan['material_manifest_sha256']!=sha(DEFAULT/'conversion.json') or
                any(type(plan[k]) is not int for k in ('maximum_notebook_wall_seconds','maximum_worker_wall_seconds',
                    'maximum_outer_forwards','maximum_input_tokens','maximum_optimizer_steps','maximum_generations',
                    'maximum_teacher_calls','maximum_paid_usd','maximum_segment_gemm_calls','full_model_decoder_layers',
                    'full_model_linear_modules','tiny_linear_modules','tiny_gradient_backwards','extra_model_calls_from_hooks'))):
            raise ValidationError('exact source/material and integer whole-model bounds required')
    pack_sequences(rows)
    notebook=json.loads((package/'kernel/notebook.ipynb').read_bytes())
    source=''.join(notebook['cells'][0]['source']);tree=ast.parse(source)
    values={node.targets[0].id:ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
        and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'RUN','PAYLOADS','HASHES'}}
    if values['RUN']!=plan['run_id'] or values['HASHES']!=summary['payload_sha256']:raise ValidationError('notebook payload binding differs')
    if diagnostic and "'irisx.arc_nvarc_qwen3_packing_diagnostic'" not in source:
        raise ValidationError('diagnostic worker differs')
    if operator and "'irisx.arc_nvarc_qwen3_operator_probe'" not in source:
        raise ValidationError('first-layer operator worker differs')
    if segmented and "'irisx.arc_nvarc_qwen3_segmented_probe'" not in source:
        raise ValidationError('whole-model segmented-linear worker differs')
    if segmented and source!=segmented_source(values['RUN'],values['PAYLOADS'],values['HASHES']):
        raise ValidationError('exact reviewed segmented parent bytes differ')
    for key,encoded in values['PAYLOADS'].items():
        raw=zlib.decompress(base64.b64decode(encoded,validate=True))
        if hashlib.sha256(raw).hexdigest()!=values['HASHES'][key]:raise ValidationError('embedded payload bytes differ')
        if key=='plan' and json.loads(raw)!=plan:raise ValidationError('embedded plan differs')
        if key=='samples' and json.loads(raw)!=rows:raise ValidationError('embedded samples differ')
    meta=json.loads((package/'kernel/kernel-metadata.json').read_bytes())
    if meta['id']!=plan['kernel_id'] or not meta['is_private'] or meta['enable_internet'] or meta['kernel_sources'] or meta['dataset_sources']!=list(plan['datasets'].values()):
        raise ValidationError('private offline exact material transport differs')
    if segmented and (meta['is_private'] is not True or meta['enable_internet'] is not False or meta['enable_gpu'] is not True or
            meta['competition_sources']!=['arc-prize-2026-arc-agi-2'] or plan['competition_sources']!=meta['competition_sources'] or
            plan['competition_files_opened']!=0 or plan['approved'] is not True or
            plan['datasets']!={'base':'danielwuu/irisx-nvarc-original-qwen3-001','wheels':'danielwuu/irisx-arc-agi-2-trial-002-smoke-001'}):
        raise ValidationError('exact offline private segmented transport required')
    return {'offline_package_verified':True,'external_calls':0,'run_id':plan['run_id'],'plan_digest':digest_value(plan),
        'maximum_input_tokens':plan['maximum_input_tokens'],'maximum_outer_forwards':expected_calls}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--run-id')
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--diagnostic',action='store_true');group.add_argument('--operator',action='store_true')
    group.add_argument('--segmented',action='store_true')
    args=parser.parse_args();print(json.dumps(stage(args.package,args.run_id,args.diagnostic,args.operator,args.segmented) if args.action=='stage' else preflight(args.package)))
