"""Offline RLVR content validator. Source read as bytes; production remains unbound.

Caller-supplied hashes are expectations for local replay, never release approval.
This in-payload checker never authenticates review authority. A separately
reviewed outside-in wrapper verifies bytes before import and controls admission.
"""
from pathlib import Path
import argparse, json
from .safe_io import Root,EvidenceError,need,same,digest,is_sha,finite,integer
from .tensor_checks import validate_checkpoint
from .checkpoint_metadata import validate_checkpoint_metadata
from .audit_checks import validate_sweeps
from .training_checks import reward_panel
from .native_identity import NativeTokenCodec
from .prediction_checks import validate_scope,validate_scores,reference
from .ledger_checks import validate_metering,validate_clock,replay_journal,resolved_events

# This in-payload module is permanently content-only. Review authority lives
# in the separately published offline_review wrapper, outside runtime inventory.
VALIDATOR_SCHEMA='irisx/owned-rl-batched-offline-validation-v1'


def source_identity(source_root,files,expected):
    need(type(files) is dict and files and is_sha(expected), 'independent expected source digest required')
    need(digest(sorted(files.items()))==expected, 'source inventory not expected independent source release')
    root=Root(source_root)
    owned=any(n.startswith('owned_runtime/') for n in files)
    directories=('baseline','rl_session','reviewed','experiment_flow','owned_runtime','validation') if owned else ('baseline','rl_session','reviewed','experiment_flow')
    found=set()
    for directory in directories:
        for path in (root.path/directory).rglob('*'):
            need(not path.is_symlink(),'symlink in archived source boundary')
            if path.is_file() and '__pycache__' not in path.parts and (path.suffix=='.py' or owned and directory=='baseline'):
                found.add(path.relative_to(root.path).as_posix())
    found.update(n for n in ('design/LEAD-EXPERIMENT-DECISIONS.json','independent-protocol-review/PROVISIONAL-DEFAULTS.json','independent-protocol-review/PROTOCOL-REVIEW.md','design/MEASURED-POLICY.json','design/COST-EVIDENCE.json') if (root.path/n).is_file())
    need(found==set(files),'complete archived source inventory has unknown/missing members')
    for name,h in files.items():
        need(is_sha(h) and root.file_sha(name)==h, 'archived source bytes differ: '+name)
    if any(n.startswith('owned_runtime/') for n in files):
        return digest({name:h for name,h in files.items() if name.endswith('.py') or name in ('design/LEAD-EXPERIMENT-DECISIONS.json','independent-protocol-review/PROVISIONAL-DEFAULTS.json','independent-protocol-review/PROTOCOL-REVIEW.md','design/MEASURED-POLICY.json','design/COST-EVIDENCE.json')})
    return digest({name:h for name,h in files.items() if name.startswith(('baseline/','rl_session/','reviewed/')) and name.endswith('.py')})


def modern_protocol(source_root,files):
    # Compatibility follows independently checked source bytes, never evidence flags.
    name='owned_runtime/storage.py'
    return name in files and b'def summarize_state(' in Root(source_root).read(name)


def source_closure(result,files,expected):
    for key in ('initial_source_closure','source_closure'):
        row=result.get(key)
        need(type(row) is dict and row.get('source_sha256')==expected and same(row.get('inventory'),files), 'complete execution source inventory differs')
        need(row.get('execution_history_closure_verified') is True, 'actual local execution history guard missing')
        guard=row.get('execution_guard');need(type(guard) is dict and guard.get('rejected')==[], 'source execution rejected or missing')
        observed=guard.get('observed_file_executions');need(type(observed) is dict, 'local executed-file inventory missing')
        for name,h in observed.items():need(files.get(name)==h, 'unarchived/changed local code executed')
        imports=row.get('observed_loaded_local_imports');need(type(imports) is dict, 'loaded source inventory missing')
        for record in imports.values():need(files.get(record.get('file'))==record.get('sha256'), 'unarchived/changed local import')


def frozen_plan(plan,synthetic):
    need(type(plan) is dict and set(plan)=={'format','source_sha256','forecast','global_started','measured_policy_sha256','batch_semantics','clock_chain','arm_cap_seconds','shape','numeric_gate','inference','anchor_lr','B_lr','C_lr','anchor_schedule','historical_v25_tensor_equivalence_claim','continuation_schedule','comparison','selection','production_admitted'},'closed source-owned frozen plan schema')
    need(plan.get('format')=='local-intervention-plan-v1' and same(plan.get('clock_chain'),[42000.,42180.,42300.,43200.]), 'fixed original clock chain')
    need(finite(plan.get('global_started')) and plan.get('arm_cap_seconds')==7200., 'original phase clock/cap')
    shape=plan.get('shape');need(type(shape) is dict and set(shape)=={'anchor_updates','parents','group_size','dev_cases','holdout_cases','max_sweeps','max_control_updates','batch_parents'}, 'explicit workload shape')
    for k,maxval in {'anchor_updates':256,'parents':32,'group_size':8,'dev_cases':16,'holdout_cases':32,'max_sweeps':4,'max_control_updates':8192}.items():
        need(integer(shape[k],1,maxval),'bounded workload shape: '+k)
    need(integer(shape['batch_parents'],0,8),'bounded fixed batch parent count')
    if not synthetic:
        need(shape['batch_parents']==8 and plan.get('batch_semantics')=='disjoint-fixed-prefix' and plan.get('measured_policy_sha256')=='3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda','exact reviewed fixed-disjoint batching policy')
        need(all(shape[k]==v for k,v in {'anchor_updates':256,'parents':32,'group_size':8,'dev_cases':16,'holdout_cases':32}.items()), 'production workload cannot shrink')
    need(plan.get('B_lr')==1e-6 and plan.get('C_lr')==plan.get('anchor_lr')==2e-4 and plan.get('continuation_schedule')=='fresh-constant', 'frozen A/B/C optimizer policy')
    inference=plan.get('inference',{})
    need(set(inference)=={'TTT','decoder','max_new_tokens','maximum_answers','packing','precision','seed','transforms'} and inference.get('decoder')=='unchanged-native-grid-DFA' and inference.get('packing')=='frozen-native-whole-demo' and inference.get('precision')=='bf16-base-fp32-lora','closed fixed native inference contract')
    need(inference.get('TTT') is False and inference.get('transforms')==[0,1] and inference.get('seed')==1917 and inference.get('maximum_answers')==2 and integer(inference.get('max_new_tokens'),1,1024), 'fixed two-view primary inference')
    if not synthetic:need(inference['max_new_tokens']==1024 and shape['max_sweeps']==4 and shape['max_control_updates']==8192,'complete production inference/sweep/control caps')
    need(same(plan.get('anchor_schedule'),{'base_lr':2e-4,'warmup':4,'cosine_steps':256,'min_lr_ratio':.1}) and plan.get('comparison')=='intervention-package','fixed source anchor schedule/comparison')
    need(plan.get('historical_v25_tensor_equivalence_claim') is False and plan.get('selection')=='dev-exact-fixed-tie-A-B-C', 'historical equivalence/selection policy differs')
    gate=plan.get('numeric_gate');need(type(gate) is dict, 'pre-audit numeric gate missing')
    for k in ('maximum_absolute_gap','maximum_p95_gap','maximum_replay_seconds','minimum_unclipped_fraction'):
        need(finite(gate.get(k)), 'finite fixed numerical bound')
    if not synthetic:
        need(finite(gate.get('maximum_batch_replay_backward_seconds')) and gate['maximum_batch_replay_backward_seconds']==600,'production cumulative replay/backward budget is not frozen')
        need(gate.get('fixture_only') is False and gate['maximum_absolute_gap']==.2 and gate['maximum_p95_gap']==.05 and gate['minimum_unclipped_fraction']==1. and gate['maximum_replay_seconds']==30. and gate.get('maximum_peak_bytes')==72*1024**3 and gate.get('maximum_reserved_bytes')==80*1024**3, 'production numeric/memory admission must be source-fixed')
    return shape


def _validate_fixture_content(root,*,source_root,expected_source_sha256,dataset_root,expected_dataset_sha256,original_root,synthetic,checkpoint_mode="full-materialized"):
    result=root.json('result.json');plan=root.json('frozen-plan.json');inventory=root.json('source-inventory.json')
    need(result.get('TTT') is False and set(result.get('arms',{}))=={'A','B','C'},'exact unchanged A/B/C comparison inventory')
    if synthetic:need(result.get('production_admitted') is False and result.get('ARC_or_PUBLIC_efficacy_claim') is False,'fixture cannot claim production or ARC efficacy')
    need(result.get('scope') in ('native-tiny-CPU-fixture','controlled-adapter-fixture','owned-native-production'), 'explicit fixture/production evidence scope')
    need(result.get('plan_sha256')==digest(plan) and inventory.get('source_sha256')==plan.get('source_sha256')==expected_source_sha256, 'exact plan/source linkage')
    shape=frozen_plan(plan,synthetic)
    core=source_identity(source_root,inventory.get('files'),expected_source_sha256)
    modern=modern_protocol(source_root,inventory['files'])
    if modern:
        policy=Root(source_root).json('design/MEASURED-POLICY.json')
        if not synthetic:
            need(plan['numeric_gate'].get('maximum_batch_replay_backward_seconds')==policy['gates']['proposed_cumulative_replay_backward_commit_batch_seconds']==600,'actual cumulative batch gate differs from pinned source policy')
        for label in ('base','A','B','C'):
            from .tensor_checks import checkpoint_root
            checkpoint_root(root,label).member('state-summary.json')
        bridge=root.json('physical-metering-closure.json')
        expected_ref=result.get('physical_events_ref')
        need(type(expected_ref) is dict and root.remap(expected_ref.get('path'),original_root)=='physical-events.json','current source requires canonical sole physical event stream')
        for container in (result,result.get('model_closure',{}),bridge.get('model_closure',{})):
            need('physical_events' not in container and same(container.get('physical_events_ref'),expected_ref),'current source cannot use historical inline physical streams')
    source_closure(result,inventory['files'],expected_source_sha256)
    need(checkpoint_mode in ('full-materialized','runtime-reload-bound'),'explicit checkpoint verification mode')
    check=validate_checkpoint if checkpoint_mode=='full-materialized' else validate_checkpoint_metadata
    checkpoints={label:check(root,label,anchor_updates=shape['anchor_updates'],expected_core_source_sha256=core,synthetic=synthetic) for label in ('base','A','B','C')}
    for name in ('base_identity_sha256','structure_sha256','training_identity'):
        need(len({json.dumps(c[name],sort_keys=True) for c in checkpoints.values()})==1, 'checkpoint branch/base/source training identity differs: '+name)
    need(checkpoints['A']['sft_exposed']==checkpoints['B']['sft_exposed'] and checkpoints['C']['sft_exposed'][:shape['anchor_updates']]==checkpoints['A']['sft_exposed'], 'C did not continue A committed SFT cursor')
    if checkpoints['B']['counts']['rl_updates']==0:
        need(checkpoints['B']['adapter_sha256']==checkpoints['A']['adapter_sha256'], 'no-update B must be actual A tensor state')
    for label in ('base','A','B','C'):
        actual=root.json(label+'-checkpoint-proof.json')
        aggregate=result.get('base') if label=='base' else result.get('arms',{}).get(label)
        need(type(aggregate) is dict and all(same(aggregate.get(k),v) for k,v in actual.items()),'aggregate actual checkpoint proof differs: '+label)
    need(result['arms']['B'].get('no_update') is (checkpoints['B']['counts']['rl_updates']==0), 'B no-update flag differs from actual tensors/counters')
    events,meter=validate_metering(root,result,plan,original_root)
    dsroot=Root(dataset_root)
    need(is_sha(expected_dataset_sha256) and dsroot.file_sha('solver-dataset.json')==expected_dataset_sha256, 'independently expected dataset bytes required')
    dataset=dsroot.json('solver-dataset.json')
    need(dataset.get('public_answers_read') is False and dataset.get('original_test_fields_retained') is False, 'target-free source data contract')
    if synthetic:need(dataset.get('cpu_fixture_only') is True, 'synthetic fixture dataset declaration missing')
    else:need(dataset.get('cpu_fixture_only') is False, 'toydata cannot be production evidence')
    codec=NativeTokenCodec(source_root)
    scope_payloads={};scope_seals={};targets={};generation_events=set()
    for scope in ('dev','holdout'):
        cases=[c for c in dataset['cases'] if c['scope']==scope][:shape[scope+'_cases']]
        need(len(cases)==shape[scope+'_cases'], 'authenticated fixed case count differs')
        payload,seal,ids=validate_scope(root,scope,cases=cases,checkpoints=checkpoints,plan=plan,events=events,original_root=original_root,synthetic=synthetic,codec=codec)
        need(payload['plan_sha256']==dataset['plan']['plan_sha256'], 'sealed dataset plan binding differs')
        need(not generation_events.intersection(ids),'generation reused between scopes');generation_events.update(ids)
        scope_payloads[scope]=payload;scope_seals[scope]=seal
        complete=all(r['complete'] for rows in payload['methods'].values() for r in rows)
        if scope=='holdout' and not complete:
            need(dsroot.file_sha('holdout-target-escrow.json')==dataset['escrow']['holdout']['sha256'],'authenticated unopened held escrow bytes differ')
            targets[scope]=None
            continue
        escrow=dataset['escrow'][scope]
        # Only dev and holdout targets are opened. This function has no PUBLIC target path.
        name=scope+'-target-escrow.json';need(dsroot.file_sha(name)==escrow['sha256'],'authenticated dev/holdout escrow bytes differ')
        values=dsroot.json(name);targets[scope]={c['case_id']:values[c['case_id']] for c in cases}
    scoring=validate_scores(root,scope_payloads['dev'],scope_payloads['holdout'],scope_seals['dev'],scope_seals['holdout'],targets,result=result)
    rewards=reward_panel(dataset,checkpoints,result,synthetic=synthetic)
    audit=validate_sweeps(root,result,plan,checkpoints,events,panel_plan_sha256=dataset['plan']['plan_sha256'],synthetic=synthetic,reward_targets=rewards,codec=codec,require_modern=modern,checkpoint_mode=checkpoint_mode)
    expected_stage={'common-base-anchor':'complete','B':'complete','C':'complete','dev':'complete',
        'PUBLIC':('complete' if result.get('public',{}).get('coverage',{}).get('complete_prediction_coverage') is True else 'partial'),
        'holdout':'complete' if scoring['comparison_complete'] else 'partial','closure':'complete'}
    need(same(result.get('stage_status'),expected_stage),'mandatory phase statuses differ from actual complete/partial evidence')
    expected_schedule=[list(rewards)[i:i+(shape['batch_parents'] or shape['parents'])] for i in range(0,len(rewards),shape['batch_parents'] or shape['parents'])]
    need(result.get('batch_schedule')==expected_schedule and result.get('measured_policy_sha256')==plan.get('measured_policy_sha256'),'actual source-fixed batch schedule/policy declaration differs')
    from .budget_checks import persistence_and_budget
    meter['batch_budget']=persistence_and_budget(root,result,plan,events,source_root=source_root,synthetic=synthetic)
    need(result.get('status') in ('local-comparison-complete-PUBLIC-integration-pending','owned-comparison-complete-PUBLIC-sealed','local-partial-comparison-PUBLIC-integration-pending','owned-partial-comparison-PUBLIC-sealed'), 'aggregate completion differs from complete replay')
    return {'checkpoints':checkpoints,'metering':meter,'audit':audit,'evaluation':scoring,'generation_count':len(generation_events),
            'codec':codec,'checkpoint_verification':{'mode':checkpoint_mode,'independent_checkpoint_tensor_verification':checkpoint_mode=='full-materialized','runtime_reload_receipts_verified':True},
            'dataset_file_sha256':expected_dataset_sha256,'dataset_escrow_sha256':{s:dataset['escrow'][s]['sha256'] for s in ('dev','holdout')},
            'dataset_content_sha256':None if targets['holdout'] is None else digest({**{k:dataset[k] for k in ('plan','manifest','records','cases')},'dev_targets':targets['dev'],'holdout_targets':targets['holdout']}),
            'structural_projection_required':modern and b"'structural_projection':" in Root(source_root).read('owned_runtime/factory.py'),
            'comparison_complete':scoring['comparison_complete'],'scope':result['scope'],'source_sha256':expected_source_sha256,'plan_sha256':digest(plan),'result':result,'plan':plan,'events':events}


def validate_local_content(experiment_root,*,source_root,expected_source_sha256,dataset_root,
                           expected_dataset_sha256,original_root=None,allow_synthetic=False,checkpoint_mode="full-materialized"):
    """Replay inner evidence only. Never returns production/scientific success.

    The expected hashes must come from a separately reviewed source/fixture pin,
    not be recomputed from the candidate's own assertions by the caller.
    """
    report={'format':VALIDATOR_SCHEMA,'evidence_valid':False,'status':'EVIDENCE_REJECTED','production_admitted':False,
            'scientific_goal_met':False,'errors':[],'qualifications':[]}
    try:
        root=Root(experiment_root);result=root.json('result.json')
        synthetic=result.get('scope') in ('native-tiny-CPU-fixture','controlled-adapter-fixture')
        need(not synthetic or allow_synthetic is True, 'synthetic/tiny evidence rejected by default; explicit fixture hook required')
        if not synthetic:
            need(False,'production requires complete owned-envelope content replay; inner-only API has no admission authority')
        proof=_validate_fixture_content(root,source_root=source_root,expected_source_sha256=expected_source_sha256,dataset_root=dataset_root,
                                        expected_dataset_sha256=expected_dataset_sha256,original_root=original_root or str(root.path),synthetic=synthetic,checkpoint_mode=checkpoint_mode)
        for key in ('result','plan','events','codec'):proof.pop(key)
        report.update(evidence_valid=True,status='FIXTURE_MECHANICS_COMPLETE' if synthetic else 'INNER_CONTENT_VALIDATED',**proof)
        report['qualifications']=['Actual tensor/Adam/schedule replay is not a rerun or proof of causal training execution.',
            'Inner content replay alone does not authenticate outer owner termination, append-only history, or PUBLIC scoring.',
            'Reduced tiny mechanics and controlled full-shape fixtures establish no14B efficacy, fit, timing or production authority.']
    except (EvidenceError,KeyError,TypeError,ValueError,OSError,IndexError,OverflowError) as exc:
        report['errors'].append(type(exc).__name__+': '+str(exc))
    return report


def validate_owned_outputs(output_root,*,source_root,expected_source_sha256,expected_dataset_sha256=None,
                           expected_artifact_inventory_sha256=None,journal_auth_key=None,
                           public_challenges_sha256=None,allow_synthetic=False,checkpoint_mode="runtime-reload-bound",checkpoint_archive_observation=None,release_root=None,expected_launch_envelope_sha256=None,expected_release_manifest_sha256=None):
    """Reconstruct complete/failed/unknown local content, never live authority.

    Generic content replay never authenticates production review authority.
    Optional artifact SHA and HMAC key must come from a separate authenticated
    owner envelope, never from this evidence directory. No provider API is used.
    """
    from .outer_checks import artifact_inventory,parent_envelope
    from .public_checks import validate_public
    report={'format':VALIDATOR_SCHEMA,'status':'EVIDENCE_REJECTED','evidence_valid':False,'diagnostic_evidence_valid':False,
            'production_admitted':False,'scientific_goal_met':False,'errors':[],'omissions':[],
            'external_owner_envelope_verified':False,'qualifications':[]}
    try:
        root=Root(output_root)
        owned=root.json('owned-result.json');synthetic=owned.get('fixture') is True
        need(not synthetic or allow_synthetic is True,'synthetic/tiny evidence rejected by default; explicit fixture hook required')
        if not synthetic:
            need(release_root is not None and is_sha(expected_release_manifest_sha256) and is_sha(expected_launch_envelope_sha256),'production content replay requires independently expected release and launch documents; caller values alone confer no authority')
        inv=artifact_inventory(root,expected_artifact_inventory_sha256,checkpoint_mode=checkpoint_mode,checkpoint_archive_observation=checkpoint_archive_observation)
        envelope=parent_envelope(root,expected_source_sha256=expected_source_sha256,journal_auth_key=journal_auth_key)
        source_identity(source_root,envelope['source']['files'],expected_source_sha256)
        from .storage_checks import storage_contract
        report['storage_contract']=storage_contract(root,source_root)
        modern=modern_protocol(source_root,envelope['source']['files'])
        if modern and envelope['safe_closure']:
            need('checkpoints.zip' in root.json('artifact-inventory.json')['files'],'current source requires complete checkpoint ZIP descriptor/inventory')
            root.member('checkpoint-zip-descriptor.json');root.member('session-admission.json')
            expected_ref=envelope['inner']['model_closure'].get('physical_events_ref')
            need(type(expected_ref) is dict and root.remap(expected_ref.get('path'),envelope['original_root'])=='experiment/physical-events.json','current owner requires canonical final physical stream')
            need('physical_events' not in envelope['outer']['journal'] and same(envelope['outer']['journal'].get('physical_events_ref'),expected_ref),'current outer journal must bind sole final union')
        release=None
        if not synthetic:
            from .release_checks import release_binding
            need(release_root is not None and is_sha(expected_launch_envelope_sha256),'independently authenticated per-run launch envelope required')
            release=release_binding(root,source_root,envelope,release_root=release_root,release_sha256=expected_release_manifest_sha256,launch_sha256=expected_launch_envelope_sha256,source_sha256=expected_source_sha256,inventory_sha256=inv['inventory_sha256'])
            need(release['documents']['material_review'].get('format')=='owned-rl-reviewed-material-v1','reviewed material schema required')
            launch=Root(release_root).json('launch.json')
            need(launch.get('checkpoint_archive_observation_sha256')==(digest(checkpoint_archive_observation) if checkpoint_archive_observation is not None else None),'independent collector ZIP observation binding differs')
            report['release_content_binding_valid']=True
        report['artifact_inventory']=inv
        report['journal']={k:v for k,v in envelope['journal'].items() if k not in ('physical_events','artifact_bindings')}
        report['phase_status']={'owner_process_closed':envelope['safe_closure'],'inner_status':envelope['inner']['status'],'public':'NOT_VALIDATED'}
        if not envelope['safe_closure']:
            need(owned.get('status')=='stopped-incomplete','unsettled/failed owner cannot claim complete')
            need(owned.get('PUBLIC_score') is None,'failed/unknown owner cannot claim scorer output')
            report.update(status='STOPPED_INCOMPLETE',diagnostic_evidence_valid=True)
            report['failed_work']={'error':envelope['inner'].get('error'),'hard_stop':envelope['outer'].get('hard_stop'),
                                   'unknown_operation_ids':envelope['journal']['unknown_operation_ids'],
                                   'cost_charges':envelope['outer']['journal'].get('cost_charges')}
            report['omissions']=['Safe complete owner closure and complete A/B/C/PUBLIC evidence were not established.']
            return report
        need(owned.get('status') in ('owned-mechanics-complete-PUBLIC-sealed','owned-mechanics-partial-comparison-PUBLIC-sealed'),'owner terminal status differs')
        original=envelope['original_root']
        flow=reference(root,envelope['inner']['result_ref'],original)
        need(same(envelope['inner']['result_ref'],owned.get('result_ref')) and same(flow,root.json('experiment/result.json')),'outer/inner/actual experiment result linkage')
        need(same(resolved_events(root,flow,original),envelope['journal']['physical_events']),'durable and in-process complete event union differs')
        dsname='authenticated-fixture-data' if synthetic else 'dataset';ds=Root(root.path/dsname)
        need(expected_dataset_sha256 is not None,'independently pinned dataset digest is required for content replay')
        proof=_validate_fixture_content(Root(root.path/'experiment'),source_root=source_root,expected_source_sha256=expected_source_sha256,dataset_root=ds.path,
                                         expected_dataset_sha256=expected_dataset_sha256,original_root=original+'/experiment',synthetic=synthetic,checkpoint_mode=checkpoint_mode)
        if (root.path/'experiment/checkpoints/base/state-summary.json').is_file():
            from .release_checks import session_receipt
            report['session_identity']=session_receipt(root,envelope,proof,synthetic=synthetic)
        if not synthetic:
            from .release_checks import source_policy,model_admission
            source_policy(proof['plan'],release['documents']['phase_policy'],release['release']['phase_policy_sha256'],source_root=source_root)
            material=release['documents']['material_review']
            need(material.get('format')=='owned-rl-reviewed-material-v1','reviewed actual material schema')
            need(material.get('dataset_file_sha256')==proof['dataset_file_sha256'] and same(material.get('dataset_escrow_sha256'),proof['dataset_escrow_sha256']),'independently reviewed exact target-free dataset and escrow byte hashes required')
            if material.get('dataset_content_sha256') is not None and proof['dataset_content_sha256'] is not None:
                need(material['dataset_content_sha256']==proof['dataset_content_sha256'],'optional complete dataset semantic digest differs from reviewed material')
            report['model_admission']=model_admission(root,envelope,proof,release['documents']['environment'])
        proof['public_challenges_sha256']=public_challenges_sha256
        public=validate_public(root,flow.get('public'),proof=proof,source_files=envelope['source']['files'],original_root=original,synthetic=synthetic,
                               closure_time=proof['metering']['closed_monotonic'],score=owned.get('PUBLIC_score'))
        if owned.get('PUBLIC_score') is not None:
            score=owned['PUBLIC_score'];outer=envelope['outer'];inner=envelope['inner']
            need(score.get('owner_request_sha256')==outer['request_sha256'] and score.get('owner_inner_closure_sha256')==root.file_sha('inner-closure.json') and same(reference(root,score['owner_outer_closure'],original),outer),'scorer owner/request/closure linkage differs')
            need(finite(score.get('scoring_started_monotonic')) and finite(score.get('scoring_finished_monotonic')) and outer['exit_observed_monotonic']<=score['scoring_started_monotonic']<=score['scoring_finished_monotonic']<=envelope['clock']['origin_monotonic']+43200,'scorer chronology must follow actual owner exit within original absolute clock')
        report.update(status='FIXTURE_OWNED_CONTENT_COMPLETE' if synthetic else 'OWNED_CONTENT_COMPLETE_UNADMITTED',evidence_valid=True,diagnostic_evidence_valid=True,
                      comparison_complete=proof['comparison_complete'],checkpoint_verification=proof['checkpoint_verification'],checkpoints=proof['checkpoints'],metering=proof['metering'],audit=proof['audit'],evaluation=proof['evaluation'],generation_count=proof['generation_count'],public=public)
        if report.get('session_identity',{}).get('independent_admission_structure_cross_domain_verification') is False:
            report['status']='FIXTURE_CONTENT_COMPLETE_STRUCTURE_BRIDGE_UNAVAILABLE'
            report['omissions'].append('Admission structural projection was not emitted by this exact historical producer; cross-domain structure hash linkage unavailable. Production remains blocked.')
        report['phase_status'].update(anchor='COMPLETE',B='COMPLETE',C='COMPLETE',paired='COMPLETE' if proof['comparison_complete'] else 'PARTIAL',public=public['status'])
        report['qualifications']=['Offline tensor/receipt replay is not a neural rerun or proof of causal execution.',
            'Journal semantic/hash-chain replay does not authenticate HMAC without a separately delivered parent key.',
            'A source-consistent receipt cannot recreate the live owner capability. External operator/provider envelope admission remains separate.',
            'Generic content validation never authenticates an external owner or admits production; only the separately reviewed outside-in wrapper may supply that authority.']
    except (EvidenceError,KeyError,TypeError,ValueError,OSError,IndexError,OverflowError) as exc:
        report['errors'].append(type(exc).__name__+': '+str(exc))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('experiment_root');p.add_argument('--source-root',required=True);p.add_argument('--source-sha256',required=True)
    p.add_argument('--dataset-root');p.add_argument('--dataset-sha256',required=True);p.add_argument('--original-root');p.add_argument('--allow-synthetic',action='store_true')
    p.add_argument('--owned',action='store_true');p.add_argument('--checkpoint-mode',choices=['full-materialized','runtime-reload-bound'])
    args=p.parse_args()
    if args.owned:
        result=validate_owned_outputs(args.experiment_root,source_root=args.source_root,expected_source_sha256=args.source_sha256,
                                      expected_dataset_sha256=args.dataset_sha256,allow_synthetic=args.allow_synthetic,checkpoint_mode=args.checkpoint_mode or 'runtime-reload-bound')
    else:
        if args.dataset_root is None:p.error('--dataset-root is required for inner-only replay')
        result=validate_local_content(args.experiment_root,source_root=args.source_root,expected_source_sha256=args.source_sha256,dataset_root=args.dataset_root,
                                      expected_dataset_sha256=args.dataset_sha256,original_root=args.original_root,allow_synthetic=args.allow_synthetic,checkpoint_mode=args.checkpoint_mode or 'full-materialized')
    print(json.dumps(result,sort_keys=True,indent=2,allow_nan=False));return 0 if result['evidence_valid'] else 2

if __name__=='__main__':raise SystemExit(main())
