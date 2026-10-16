"""A/B/C phase controller with immutable artifacts and honest stop branches.

This is a local fixture execution API. The typed production plan interface has
no release token, provider or network hook; production admission stays closed.
"""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import time
from .contracts import (require, digest, write_json, file_sha, tolerance,
                        RecoverableWorkError, FatalStateError, ExperimentPlan, SourceExecutionGuard)
from .audit import empty_batch, summarize
from .metering import close_metering, compact_event_projections
from .evaluation import (evaluate_scope, select_dev, score_holdout, read_predictions,
                         public_integration_request, deterministic_prediction_signature, verify_common_deterministic_views, PredictionAuthority, safe_closure)


def production_admission(plan):
    require(type(plan) is ExperimentPlan, 'typed frozen plan required')
    return {'production_admitted': False, 'status': 'not-admitted', 'plan_sha256': plan.sha256,
            'blockers': ['integrated-source-review', 'protocol-review', 'conditional-in-session-numeric-memory-admission',
                         'source-bound-v25-phase-forecast', 'monitor-review', 'release-review'],
            'new_diagnostics_only_GPU_run_required': False}


class WholePhaseLedger:
    """One synchronized interval per arm; nested event durations are not summed."""
    def __init__(self, backend, clock):
        self.backend, self.clock = backend, clock
        self.events = []
        self.active = None

    @contextmanager
    def phase(self, name):
        require(self.active is None, 'whole-arm intervals may not overlap')
        self.backend.sync()
        event = {'phase': name, 'started': self.clock(), 'status': 'started',
                 'clock': 'synchronized-model-phase-wall', 'device_kernel_time': False}
        self.events.append(event)
        self.active = event
        try:
            yield event
            self.backend.sync()
            event['status'] = 'complete'
        except BaseException as exc:
            event.update(status='failed', error=type(exc).__name__ + ': ' + str(exc))
            try:
                self.backend.sync()
            except BaseException as sync_error:
                event.update(status='unsettled-device-state', sync_error=str(sync_error))
                raise FatalStateError('phase synchronization failed') from sync_error
            raise
        finally:
            event['ended'] = self.clock()
            event['seconds'] = event['ended'] - event['started']
            self.active = None

    def elapsed(self):
        return self.clock() - self.active['started'] if self.active else 0.


def run_local_experiment(backend, dataset, reward_panel, plan, output, *, clock=time.monotonic, public_bridge=None):
    """Execute explicit controlled/native CPU fixtures. No fake production proof.

    Backend methods operate only on target-free cases or authenticated training
    data. Dataset alone owns escrow; labels are opened after prediction seals.
    All backend failures must prove recovery or stop the complete flow safely.
    Type/scope checks and exclusive output-directory acquisition are pre-entry
    validation; on those exceptions the caller still owns backend cleanup. Once
    that new directory is acquired, this function owns cleanup on every branch.
    """
    require(type(plan) is ExperimentPlan, 'typed frozen experiment plan')
    if backend.scope=='owned-native-production':
        from owned_runtime.backend import NativeOwnedAdapter
        require(type(backend) is NativeOwnedAdapter and not backend.session.fixture,'source-owned production backend required')
        from owned_runtime.admission import public_receipt
        public_receipt(backend.session._owned_grant)
        require(public_bridge is not None,'production PUBLIC continuation required')
    else:
        require(backend.scope in ('controlled-adapter-fixture','native-tiny-CPU-fixture'),'closed backend scope')
    require(dataset.scope == backend.scope and reward_panel.scope == backend.scope, 'fixture/data/backend scopes differ')
    require(plan.forecast.evidence_kind == ('v25-source-bound-pending-review' if backend.scope=='owned-native-production' else 'controlled-fixture'),'source-bound forecast scope')
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    plan_sha = plan.sha256
    ledger = WholePhaseLedger(backend, clock)
    arms, sweeps, admissions = {}, [], []
    batch_parents = plan.shape.batch_parents or plan.shape.parents
    parent_batches = [tuple(reward_panel.parent_ids[i:i+batch_parents]) for i in range(0, len(reward_panel.parent_ids), batch_parents)] if plan.shape.batch_parents else [tuple(reward_panel.parent_ids)] * plan.shape.max_sweeps
    measured = plan.policy_sha256 is not None
    if measured:
        from owned_runtime.policy import load_policy, measured_batch_forecast
        measured_policy, _ = load_policy()
    result = {'format': 'local-intervention-result-v2', 'status': 'started', 'scope': backend.scope,
              'production_admitted': False, 'ARC_or_PUBLIC_efficacy_claim': False,
              'plan_sha256': plan_sha, 'arms': arms, 'audit_sweeps': sweeps, 'admissions': admissions,
              'phase_intervals': ledger.events, 'dev_selection': None, 'holdout': None, 'public': None,
              'comparison': 'intervention-packages-B-LR1e-6-C-LR2e-4', 'TTT': False,
              'measured_policy_sha256': plan.policy_sha256, 'batch_schedule': [list(p) for p in parent_batches],
              'persistence_intervals':[], 'stage_status': {k:'not-reached' for k in ('common-base-anchor','B','C','dev','PUBLIC','holdout','closure')}}

    def remaining():
        return plan.deadline - clock()

    def verify_plan():
        require(plan.sha256 == plan_sha, 'plan changed after work started')
        plan.sources.verify()
        backend.assert_safe()

    def persist(label, *, deadline):
        persistence_started=clock()
        before = deepcopy(backend.identity())
        path = root / 'checkpoints' / label
        saved = backend.save(path, deadline=deadline)
        loaded = backend.reload(path, deadline=deadline)
        backend.assert_safe()
        after = backend.identity()
        require(loaded.get('reload_verified') is True and loaded.get('same_source') is True, 'owned durable reload verification required')
        require(before['adapter_sha256'] == after['adapter_sha256'], 'saved/reloaded adapter differs')
        require(saved['state_sha256'] == loaded['state_sha256'], 'full saved/reloaded state differs')
        require(saved['counts'] == backend.counts(), 'saved/reloaded counters differ')
        proof = {'checkpoint_path': str(path.resolve()), 'manifest_file_sha256': file_sha(path / 'manifest.json'),
                 'adapter_sha256': after['adapter_sha256'], 'policy_identity': after, 'save': saved, 'reload': loaded,
                 'updates': backend.counts(), 'production_admitted': False}
        if (path/'state-summary.json').is_file():
            import json
            proof['state_summary_ref']=write_json(root/'checkpoint-summaries'/(label+'.json'),json.loads((path/'state-summary.json').read_text()))
            proof['manifest_ref']=write_json(root/'checkpoint-manifests'/(label+'.json'),json.loads((path/'manifest.json').read_text()))
        write_json(root / (label + '-checkpoint-proof.json'), proof)
        persistence_ended=clock()
        result['persistence_intervals'].append({'label':label,'started':persistence_started,
            'ended':persistence_ended,'seconds':persistence_ended-persistence_started,'deadline':deadline,
            'checkpoint_manifest_sha256':proof['manifest_file_sha256'],'completed':persistence_ended<=deadline})
        require(persistence_ended<=deadline,'whole checkpoint finalization exceeded admitted deadline')
        return proof

    execution_guard = None
    try:
        execution_guard = SourceExecutionGuard(plan.sources)
        plan.sources.verify()
        result['initial_source_closure'] = plan.sources.close_imports(execution_guard)
        write_json(root / 'frozen-plan.json', plan.receipt())
        write_json(root / 'source-inventory.json', {'source_sha256': plan.sources.sha256, 'files': dict(plan.sources.files)})
        require(clock() < plan.deadline, 'original session inner deadline expired')
        require(len(reward_panel.parent_ids) == plan.shape.parents, 'fixed reward parent count')
        with ledger.phase('common-base-anchor'):
            result['stage_status']['common-base-anchor']='started'
            backend.bind_training(dataset, reward_panel)
            result['base'] = persist('base', deadline=plan.deadline)
            for _ in range(plan.shape.anchor_updates):
                backend.sft_step(deadline=plan.deadline)
                backend.assert_safe()
            require(backend.counts()['anchor_updates'] == plan.shape.anchor_updates, 'exact requested anchor updates')
            arms['A'] = persist('A', deadline=plan.deadline)
            result['reward_panel'] = reward_panel.receipt(backend.successful_exposure())
            verify_plan()
            result['stage_status']['common-base-anchor']='complete'

        # Every complete disjoint batch has a separately durable continuation.
        # The last durable batch is B: no duplicate final tensor save is needed.
        b_status = 'not-admitted'; last_b = None
        with ledger.phase('B'):
            result['stage_status']['B']='started'
            b_start=ledger.active['started']
            b_deadline=min(plan.deadline-plan.forecast.protected,b_start+plan.arm_cap_seconds)
            if measured:
                # Even an unexpected slow batch leaves C its whole-B target plus
                # maximum120s tolerance, and the unchanged downstream reserves.
                b_deadline=min(b_deadline,b_start+(remaining()-plan.forecast.protected-120.)/2.)
            require(clock()<b_deadline,'B entry lacks protected phase window')
            if hasattr(backend,'set_phase_deadline'): backend.set_phase_deadline(b_deadline)
            backend.reload(arms['A']['checkpoint_path'], deadline=b_deadline)
            backend.begin('rl', deadline=b_deadline)
            for sweep, parents in enumerate(parent_batches):
                spent = ledger.elapsed()
                cost=measured_batch_forecast(backend.physical_events()) if measured else {'seconds':plan.forecast.sweep_seconds}
                if measured:require(len(cost['observations'])==64*sweep,'only complete fixed prior batches may enter cost admission')
                increment = cost['seconds'] + plan.forecast.persist_reload_seconds
                projected_b = spent + increment
                projected_c=min(plan.arm_cap_seconds,projected_b+tolerance(projected_b))
                need = increment + projected_c + plan.forecast.protected
                ceiling=measured_policy['rl']['planned_B_ceiling_seconds'] if measured else plan.arm_cap_seconds
                admitted = (projected_b <= ceiling and projected_b+tolerance(projected_b)<=plan.arm_cap_seconds and
                            need <= remaining() and clock()+increment<=b_deadline)
                admission = {'phase': 'B', 'sweep': sweep, 'batch_index':sweep, 'parent_ids':list(parents),
                             'admitted': admitted, 'remaining_seconds': remaining(),
                             'projected_B_seconds': projected_b, 'projected_C_growth_seconds': projected_c,
                             'required_seconds': need, 'protected_seconds': plan.forecast.protected,
                             'forecast_sha256': plan.forecast.evidence_sha256, 'cost_forecast':cost,
                             'phase_deadline':b_deadline, 'whole_B_spent_seconds':spent}
                if backend.scope=='owned-native-production':
                    from owned_runtime.storage import before_batch
                    admission['disk_admission']=before_batch(root.parent,fixture=False)
                    admitted=admitted and admission['disk_admission']['admitted']
                    admission['admitted']=admitted
                admissions.append(admission)
                if not admitted:
                    b_status='not-admitted' if not sweeps else 'cost-prefix-stop'
                    break
                work_deadline=min(b_deadline-plan.forecast.persist_reload_seconds,
                                  plan.deadline-plan.forecast.protected-projected_c-plan.forecast.persist_reload_seconds)
                before_identity=deepcopy(backend.identity())
                boundary = backend.snapshot('B-before-batch-' + str(sweep))
                batch = None; update=None; entry=None
                try:
                    batch = backend.collect(reward_panel, sweep=sweep, max_new_tokens=plan.output_cap, deadline=work_deadline)
                    backend.assert_safe()
                    summary = summarize(batch, parents, plan.shape.group_size)
                    require(not summary['fatal_native_state'], 'fatal batch cannot enter fallback evaluation')
                    if not summary['complete']:
                        b_status = 'incomplete-audit'
                        if hasattr(backend,'acknowledge_batch'):backend.acknowledge_batch(batch,status=b_status)
                    elif not summary['mixed_groups']:
                        b_status = 'zero-signal'
                        if hasattr(backend,'acknowledge_batch'):backend.acknowledge_batch(batch,status=b_status)
                    else:
                        update = backend.update(batch, gate_json=plan.numerical_gate_json, deadline=work_deadline)
                        backend.assert_safe()
                        b_status = 'updated' if update.get('optimizer_committed') is True else update['status']
                    entry = {'batch': batch, 'summary': summary, 'update': update, 'status': b_status}
                except RecoverableWorkError as exc:
                    backend.assert_safe()
                    backend.restore(boundary, deadline=b_deadline)
                    backend.assert_safe()
                    batch = exc.batch if exc.batch is not None else batch
                    require(batch is not None, 'recoverable sampling failure needs actual partial audit receipt')
                    entry = {'batch': batch, 'summary': summarize(batch, parents, plan.shape.group_size),
                             'update': getattr(exc,'update_report',None), 'status': 'incomplete-audit',
                             'error': str(exc), 'rollback_verified': True}
                    b_status = 'incomplete-audit'
                except BaseException as exc:
                    if batch is not None:
                        entry={'batch':batch,'summary':summarize(batch,parents,plan.shape.group_size),
                            'update':getattr(exc,'update_report',None),'status':'failed-no-safe-continuation',
                            'error':type(exc).__name__+': '+str(exc),'batch_index':sweep,
                            'parent_ids':list(parents),'policy_before':before_identity,'policy_after':None,'admission':admission}
                        write_json(root/'audit'/f'sweep-{sweep}.json',entry);sweeps.append(entry)
                    raise
                finally:
                    backend.release_snapshot(boundary)
                entry.update(batch_index=sweep,parent_ids=list(parents),policy_before=before_identity,
                             policy_after=deepcopy(backend.identity()),admission=admission)
                # Persist the actual partial audit before potentially failing disk
                # work. Its separate durability reference is added in the index.
                audit_ref=write_json(root/'audit'/f'sweep-{sweep}.json',entry)
                sweeps.append(entry)
                last_b=persist('B-batch-'+str(sweep),deadline=b_deadline)
                entry['durable_checkpoint']=last_b
                write_json(root/'audit'/f'batch-{sweep}-durability.json',
                           {'batch_index':sweep,'audit_ref':audit_ref,'checkpoint':last_b,
                            'whole_B_elapsed_seconds':ledger.elapsed()})
                verify_plan()
                if b_status not in ('updated','zero-signal'):
                    break
            if last_b is None:
                last_b=persist('B',deadline=b_deadline)
            arms['B']=deepcopy(last_b)
            arms['B']['audit_status']=b_status
            arms['B']['no_update']=arms['B']['updates']['rl_updates']==0
            if arms['B']['no_update']:
                require(arms['B']['adapter_sha256']==arms['A']['adapter_sha256'],'no-update B must be exact A adapter')
            if Path(arms['B']['checkpoint_path']).name!='B':
                write_json(root/'B-checkpoint-proof.json',arms['B'])
            verify_plan()
            result['stage_status']['B']='complete'
        b_seconds = ledger.events[-1]['seconds']
        require(b_seconds <= plan.arm_cap_seconds, 'B actual phase exceeded hard cap')

        finalization_observations=[deepcopy(r) for r in result['persistence_intervals'] if r['completed'] is True and (r['label']=='A' or r['label']=='B' or r['label'].startswith('B-batch-'))]
        finish_estimate=(1.25*max(r['seconds'] for r in finalization_observations)) if measured else plan.forecast.persist_reload_seconds
        result['C_finalization_estimator']={'seconds':finish_estimate,'factor':1.25 if measured else None,
            'inputs':finalization_observations,'inputs_sha256':digest(finalization_observations),
            'unmeasured_global_reserve_seconds':plan.forecast.persist_reload_seconds,'outcomes_used':False}
        with ledger.phase('C'):
            result['stage_status']['C']='started'
            epsilon = tolerance(b_seconds)
            c_deadline=min(plan.deadline-plan.forecast.protected,ledger.active['started']+min(plan.arm_cap_seconds,b_seconds+epsilon))
            if hasattr(backend,'set_phase_deadline'):backend.set_phase_deadline(c_deadline)
            backend.reload(arms['A']['checkpoint_path'], deadline=c_deadline)
            backend.begin('control', deadline=c_deadline)
            c_status = 'time-target-reached'
            for _ in range(plan.shape.max_control_updates):
                spent = ledger.elapsed()
                finish = finish_estimate
                if spent + finish >= b_seconds:
                    break
                next_total = spent + plan.forecast.control_step_seconds + finish
                admitted = next_total <= min(plan.arm_cap_seconds, b_seconds + epsilon) and \
                    plan.forecast.control_step_seconds + finish + plan.forecast.protected <= remaining()
                admissions.append({'phase': 'C', 'admitted': admitted, 'C_projected_seconds_including_finalization': next_total,
                                   'B_seconds': b_seconds, 'tolerance_seconds': epsilon})
                if not admitted:
                    c_status = 'bounded-unmatched'
                    break
                try:
                    backend.sft_step(deadline=min(plan.deadline - plan.forecast.protected - finish,
                                                ledger.active['started'] + min(plan.arm_cap_seconds, b_seconds + epsilon) - finish))
                    backend.assert_safe()
                except RecoverableWorkError as exc:
                    backend.assert_safe()
                    c_status = 'recoverable-control-failure'
                    result['control_failure'] = str(exc)
                    break
            else:
                c_status = 'control-step-cap'
            arms['C'] = persist('C', deadline=min(plan.deadline - plan.forecast.protected,
                                                ledger.active['started'] + min(plan.arm_cap_seconds, b_seconds + epsilon)))
            arms['C']['control_status'] = c_status
            verify_plan()
            result['stage_status']['C']='complete'
        c_seconds = ledger.events[-1]['seconds']
        c_finalization=next(r for r in result['persistence_intervals'] if r['label']=='C')
        result['C_finalization_estimator'].update(actual_seconds=c_finalization['seconds'],
            actual_minus_estimate_seconds=c_finalization['seconds']-finish_estimate)
        require(c_seconds <= plan.arm_cap_seconds, 'C actual phase exceeded hard cap')
        result['time_matching'] = {'B_seconds': b_seconds, 'C_seconds': c_seconds, 'epsilon_seconds': tolerance(b_seconds),
                                   'matched': b_seconds<=plan.arm_cap_seconds and c_seconds<=plan.arm_cap_seconds and abs(b_seconds - c_seconds) <= tolerance(b_seconds),
                                   'includes_failures_rollback_setup_save_reload_verification': True,
                                   'clock': 'whole-synchronized-model-phase-wall', 'idle_padding': False}
        authority = PredictionAuthority(dataset, plan, arms)
        if hasattr(backend,'set_phase_deadline'):backend.set_phase_deadline(plan.deadline)
        with ledger.phase('paired-evaluation'):
            result['stage_status']['dev']='started'
            held_reserve=measured_policy['reserves_seconds']['paired_holdout_component'] if measured else plan.forecast.evaluation_seconds/2
            dev_deadline=plan.deadline-plan.forecast.public_seconds-held_reserve-plan.forecast.failure_margin_seconds-plan.forecast.closure_seconds
            result['dev_seal'] = evaluate_scope(backend, dataset, 'dev', arms, root, plan, clock=clock, authority=authority,deadline=dev_deadline)
            result['dev_selection'] = select_dev(dataset, result['dev_seal'], root, authority=authority)
            result['stage_status']['dev']='complete'
            # Dev choice is immutable before PUBLIC or current-run held labels.
            # PUBLIC consumes at most its own18000s and protects held+common+closure.
            if public_bridge is not None:
                from owned_runtime.public_bridge import PublicSuccessorBridge
                require(type(public_bridge) is PublicSuccessorBridge,'source-owned PUBLIC bridge required')
                public_deadline=min(clock()+plan.forecast.public_seconds,
                    plan.deadline-held_reserve-plan.forecast.failure_margin_seconds-plan.forecast.closure_seconds)
                result['stage_status']['PUBLIC']='started'
                result['public']=public_bridge.generate(backend,selection=result['dev_selection'],selection_authority=authority,
                    arms=arms,plan=plan,deadline=public_deadline,clock=clock)
                result['stage_status']['PUBLIC']='complete' if result['public']['coverage']['complete_prediction_coverage'] else 'partial'
            result['stage_status']['holdout']='started'
            result['holdout_seal'] = evaluate_scope(backend, dataset, 'holdout', arms, root, plan, clock=clock, authority=authority,
                deadline=plan.deadline-plan.forecast.closure_seconds)
            if arms['B']['no_update']:
                for scope in ('dev', 'holdout'):
                    payload = read_predictions(result[scope + '_seal'])
                    for a, b in zip(payload['methods']['A'], payload['methods']['B']):
                        verify_common_deterministic_views(a,b)
            result['model_closure'] = backend.close()
            safe_closure(result['model_closure'])
            result['stage_status']['closure']='complete'
            authority.register_closure(result['model_closure'])
            held_payload=read_predictions(result['holdout_seal'])
            held_complete=all(r['complete'] for rows in held_payload['methods'].values() for r in rows)
            result['comparison_complete']=held_complete
            if held_complete:
                result['holdout'] = score_holdout(dataset, result['holdout_seal'], result['dev_selection'], root, authority=authority)
                result['stage_status']['holdout']='complete'
            else:
                result['holdout']={'status':'incomplete-predictions-no-score','scores':None,'targets_opened':False,
                    'scope':'reused-experiment-heldout-not-pristine-confirmation','prediction_file_sha256':result['holdout_seal']['file_sha256']}
                result['stage_status']['holdout']='partial'
        if public_bridge is None:
            result['public'] = public_integration_request(result['dev_selection'], arms, plan, root)
        result['status'] = (('owned-comparison-complete-PUBLIC-sealed' if result.get('comparison_complete') else 'owned-partial-comparison-PUBLIC-sealed')
                            if public_bridge is not None else 'local-comparison-complete-PUBLIC-integration-pending' if result.get('comparison_complete') else 'local-partial-comparison-PUBLIC-integration-pending')
    except BaseException as exc:
        # No evaluation after unknown/fatal device state. Partial artifacts stay
        # visible, and an absent score remains null rather than fabricated zero.
        result['status'] = 'stopped-incomplete'
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        try:
            backend.assert_safe()
            result['device_state'] = 'settled'
        except BaseException as state_error:
            result['device_state'] = 'fatal-or-unknown'
            result['state_error'] = str(state_error)
    finally:
        if result.get('model_closure') is None:
            try:
                result['model_closure'] = backend.close()
            except BaseException as exc:
                result['model_closure'] = {'closed': False, 'error': str(exc)}
        try:
            result['physical_events'] = deepcopy(backend.physical_events())
        except BaseException as exc:
            result['physical_events'] = []
            result['physical_events_error'] = str(exc)
            result['status'] = 'stopped-incomplete'
        physical_ref=write_json(root/'physical-events.json',result['physical_events'])
        result['model_closure']=compact_event_projections(result['model_closure'],physical_ref)
        try:
            result['metering_bridge'] = close_metering(result['physical_events'], ledger.events, model_closure=result['model_closure'])
            write_json(root / 'physical-metering-closure.json', result['metering_bridge'])
        except BaseException as exc:
            result['status'] = 'stopped-incomplete'
            result['metering_bridge'] = {'verified': False, 'error': str(exc)}
        result.pop('physical_events',None)
        result['physical_events_ref']=physical_ref
        result['global_elapsed_seconds'] = clock() - plan.global_started
        result['final_adapter_identity'] = None
        if result.get('device_state') != 'fatal-or-unknown':
            try:
                result['final_adapter_identity'] = deepcopy(backend.identity())
            except BaseException as exc:
                result['identity_error'] = str(exc)
                result['status'] = 'stopped-incomplete'
        try:
            result['source_closure'] = plan.sources.close_imports(execution_guard)
        except BaseException as exc:
            result['status'] = 'stopped-incomplete'
            result['source_closure'] = {'verified': False, 'error': str(exc)}
        # Keep every declared batch, including unentered ones, and distinguish
        # full-panel256 intent from one complete64-slot update denominator.
        for i in range(len(sweeps),len(parent_batches)):
            batch=empty_batch(parent_batches[i],plan.shape.group_size,i,'not-entered-after-'+str(result.get('error',{}).get('type',arms.get('B',{}).get('audit_status','stop'))))
            entry={'batch_index':i,'parent_ids':list(parent_batches[i]),'batch':batch,
                   'summary':summarize(batch,parent_batches[i],plan.shape.group_size),'update':None,
                   'status':'not-reached','policy_before':None,'policy_after':None,'admission':None}
            sweeps.append(entry)
            if not (root/'audit'/f'sweep-{i}.json').exists():write_json(root/'audit'/f'sweep-{i}.json',entry)
        result['audit_sweeps']=[{'path':str((root/'audit'/f'sweep-{i}.json').resolve()),
            'file_sha256':file_sha(root/'audit'/f'sweep-{i}.json'),'batch_index':i,'parent_ids':list(parent_batches[i]),
            'summary':entry['summary'],'status':entry['status'],
            'durability_ref':({'path':str((root/'audit'/f'batch-{i}-durability.json').resolve()),
                'file_sha256':file_sha(root/'audit'/f'batch-{i}-durability.json')} if (root/'audit'/f'batch-{i}-durability.json').is_file() else None),
            'update_status':None if entry['update'] is None else entry['update']['status']}
            for i,entry in enumerate(sweeps) if (root/'audit'/f'sweep-{i}.json').is_file()]
        result['audit_batches']=deepcopy(result['audit_sweeps'])
        if plan.shape.batch_parents:
            from .audit import full_panel_summary
            result['full_panel_audit']=full_panel_summary(sweeps,reward_panel.parent_ids,plan.shape.group_size)
            write_json(root/'full-panel-audit.json',result['full_panel_audit'])
        result['result_artifact'] = str((root / 'result.json').resolve())
        try:
            write_json(root / 'result.json', result)
        finally:
            if execution_guard is not None:
                execution_guard.stop()
    return result


NUMERIC_DIAGNOSTIC_PURPOSE = 'training-only-numeric-diagnostic-v1'
NUMERIC_DIAGNOSTIC_COMPLETE = 'owned-numeric-diagnostic-complete-no-update'
NUMERIC_DIAGNOSTIC_INCOMPLETE = 'owned-numeric-diagnostic-incomplete'


def numeric_diagnostic_budget(plan, *, b_started, observed, batch_seconds, planned_ceiling):
    """Project only requested work; the frozen ABC plan and clock stay intact."""
    from .contracts import finite_nonnegative
    require(type(plan) is ExperimentPlan, 'typed frozen diagnostic plan')
    for name, value in (('B start', b_started), ('observation', observed),
                        ('batch forecast', batch_seconds), ('planned ceiling', planned_ceiling)):
        finite_nonnegative(value, name)
    require(observed >= b_started and batch_seconds > 0 and
            0 < planned_ceiling <= plan.arm_cap_seconds, 'bounded diagnostic projection')
    # Retain the full conservative persistence margin and closure reserve.
    # C and evaluation are absent from this source-fixed entrypoint, not deferred.
    protected = plan.forecast.failure_margin_seconds + plan.forecast.closure_seconds
    shadow_seconds = 120.  # Same fixed maximum as rl_session.numeric_shadow.MAX_SECONDS.
    increment = batch_seconds + shadow_seconds + plan.forecast.persist_reload_seconds
    spent = observed - b_started
    projected_b = spent + increment
    phase_deadline = min(plan.deadline - protected, b_started + plan.arm_cap_seconds)
    required = increment + protected
    remaining = plan.deadline - observed
    checks = {'original_clock_unexpired': observed < plan.deadline,
              'phase_window_open': observed < phase_deadline,
              'planned_B_ceiling': projected_b <= planned_ceiling,
              'conservative_arm_ceiling': projected_b + tolerance(projected_b) <= plan.arm_cap_seconds,
              'whole_remaining_window': required <= remaining,
              'batch_fits_phase': observed + increment <= phase_deadline}
    return {'budget_scope': NUMERIC_DIAGNOSTIC_PURPOSE, 'admitted': all(checks.values()),
            'time_checks': checks, 'remaining_seconds': remaining,
            'projected_B_seconds': projected_b, 'projected_C_growth_seconds': 0.,
            'required_seconds': required, 'protected_seconds': protected,
            'retained_reserves_seconds': {'persistence_margin': plan.forecast.failure_margin_seconds,
                                         'closure': plan.forecast.closure_seconds},
            'excluded_reserves_seconds': {'paired_ABC': plan.forecast.evaluation_seconds,
                                         'PUBLIC': plan.forecast.public_seconds},
            'numeric_shadow_seconds': shadow_seconds,
            'persist_reload_seconds': plan.forecast.persist_reload_seconds,
            'phase_deadline': phase_deadline,
            'work_deadline': phase_deadline - plan.forecast.persist_reload_seconds,
            'whole_B_spent_seconds': spent}


def run_training_numeric_diagnostic(backend, dataset, reward_panel, plan, output, *, clock=time.monotonic):
    """Source-fixed training-only successor: original A and first64, never evaluation.

    The inherited full plan remains the immutable cap/reference. Its budget is
    projected onto the requested first batch plus bounded shadow and cleanup;
    later192 slots and all comparison/evaluation stages are outside this
    diagnostic. This entrypoint has no runtime mode.
    """
    require(type(plan) is ExperimentPlan, 'typed frozen experiment plan')
    if backend.scope=='owned-native-production':
        from owned_runtime.backend import NativeOwnedAdapter
        require(type(backend) is NativeOwnedAdapter and not backend.session.fixture,'source-owned production backend required')
        from owned_runtime.admission import public_receipt
        public_receipt(backend.session._owned_grant)
    else:
        require(backend.scope in ('controlled-adapter-fixture','native-tiny-CPU-fixture'),'closed backend scope')
    require(dataset.scope == backend.scope and reward_panel.scope == backend.scope, 'fixture/data/backend scopes differ')
    require(plan.forecast.evidence_kind == ('v25-source-bound-pending-review' if backend.scope=='owned-native-production' else 'controlled-fixture'),'source-bound forecast scope')
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    plan_sha = plan.sha256
    ledger = WholePhaseLedger(backend, clock)
    arms, sweeps, admissions = {}, [], []
    batch_parents = plan.shape.batch_parents or plan.shape.parents
    parent_batches = [tuple(reward_panel.parent_ids[i:i+batch_parents]) for i in range(0, len(reward_panel.parent_ids), batch_parents)] if plan.shape.batch_parents else [tuple(reward_panel.parent_ids)] * plan.shape.max_sweeps
    measured = plan.policy_sha256 is not None
    if measured:
        from owned_runtime.policy import load_policy, measured_batch_forecast
        measured_policy, _ = load_policy()
    result = {'format': 'owned-training-numeric-diagnostic-v1', 'status': 'started', 'scope': backend.scope,
              'production_admitted': False, 'ARC_or_PUBLIC_efficacy_claim': False,
              'plan_sha256': plan_sha, 'arms': arms, 'audit_sweeps': sweeps, 'admissions': admissions,
              'phase_intervals': ledger.events, 'dev_selection': None, 'holdout': None, 'public': None,
              'comparison': None, 'comparison_complete': False, 'diagnostic_complete': False,
              'run_purpose': NUMERIC_DIAGNOSTIC_PURPOSE,
              'original_planned_attempts': plan.shape.parents*plan.shape.group_size,
              'no_C_dev_holdout_PUBLIC': True,
              'requested_attempts': 64 if backend.scope=='owned-native-production' else batch_parents*plan.shape.group_size,
              'unrequested_original_panel_attempts': 192 if backend.scope=='owned-native-production' else max(0,plan.shape.parents-batch_parents)*plan.shape.group_size, 'TTT': False,
              'measured_policy_sha256': plan.policy_sha256, 'batch_schedule': [list(p) for p in parent_batches],
              'persistence_intervals':[], 'stage_status': {k:('not-requested-by-diagnostic' if k in ('C','dev','PUBLIC','holdout') else 'not-reached') for k in ('common-base-anchor','B','C','dev','PUBLIC','holdout','closure')}}

    def remaining():
        return plan.deadline - clock()

    def verify_plan():
        require(plan.sha256 == plan_sha, 'plan changed after work started')
        plan.sources.verify()
        backend.assert_safe()

    def persist(label, *, deadline):
        persistence_started=clock()
        before = deepcopy(backend.identity())
        path = root / 'checkpoints' / label
        saved = backend.save(path, deadline=deadline)
        loaded = backend.reload(path, deadline=deadline)
        backend.assert_safe()
        after = backend.identity()
        require(loaded.get('reload_verified') is True and loaded.get('same_source') is True, 'owned durable reload verification required')
        require(before['adapter_sha256'] == after['adapter_sha256'], 'saved/reloaded adapter differs')
        require(saved['state_sha256'] == loaded['state_sha256'], 'full saved/reloaded state differs')
        require(saved['counts'] == backend.counts(), 'saved/reloaded counters differ')
        proof = {'checkpoint_path': str(path.resolve()), 'manifest_file_sha256': file_sha(path / 'manifest.json'),
                 'adapter_sha256': after['adapter_sha256'], 'policy_identity': after, 'save': saved, 'reload': loaded,
                 'updates': backend.counts(), 'production_admitted': False}
        if (path/'state-summary.json').is_file():
            import json
            proof['state_summary_ref']=write_json(root/'checkpoint-summaries'/(label+'.json'),json.loads((path/'state-summary.json').read_text()))
            proof['manifest_ref']=write_json(root/'checkpoint-manifests'/(label+'.json'),json.loads((path/'manifest.json').read_text()))
        write_json(root / (label + '-checkpoint-proof.json'), proof)
        persistence_ended=clock()
        result['persistence_intervals'].append({'label':label,'started':persistence_started,
            'ended':persistence_ended,'seconds':persistence_ended-persistence_started,'deadline':deadline,
            'checkpoint_manifest_sha256':proof['manifest_file_sha256'],'completed':persistence_ended<=deadline})
        require(persistence_ended<=deadline,'whole checkpoint finalization exceeded admitted deadline')
        return proof

    def retain_shadow(update):
        if update is not None and 'numeric_shadow' in update:
            reference=write_json(root/'numeric-shadow.json',update.pop('numeric_shadow'))
            result['numeric_shadow_ref']=reference
            update['numeric_shadow_ref']=deepcopy(reference)

    execution_guard = None
    try:
        execution_guard = SourceExecutionGuard(plan.sources)
        plan.sources.verify()
        result['initial_source_closure'] = plan.sources.close_imports(execution_guard)
        write_json(root / 'frozen-plan.json', plan.receipt())
        write_json(root / 'source-inventory.json', {'source_sha256': plan.sources.sha256, 'files': dict(plan.sources.files)})
        require(clock() < plan.deadline, 'original session inner deadline expired')
        require(len(reward_panel.parent_ids) == plan.shape.parents, 'fixed reward parent count')
        with ledger.phase('common-base-anchor'):
            result['stage_status']['common-base-anchor']='started'
            backend.bind_training(dataset, reward_panel)
            result['base'] = persist('base', deadline=plan.deadline)
            for _ in range(plan.shape.anchor_updates):
                backend.sft_step(deadline=plan.deadline)
                backend.assert_safe()
            require(backend.counts()['anchor_updates'] == plan.shape.anchor_updates, 'exact requested anchor updates')
            arms['A'] = persist('A', deadline=plan.deadline)
            result['reward_panel'] = reward_panel.receipt(backend.successful_exposure())
            verify_plan()
            result['stage_status']['common-base-anchor']='complete'

        # Every complete disjoint batch has a separately durable continuation.
        # The last durable batch is B: no duplicate final tensor save is needed.
        b_status = 'not-admitted'; last_b = None; update = None
        with ledger.phase('B'):
            result['stage_status']['B']='started'
            b_start=ledger.active['started']
            ceiling=measured_policy['rl']['planned_B_ceiling_seconds'] if measured else plan.arm_cap_seconds
            b_deadline=numeric_diagnostic_budget(plan,b_started=b_start,observed=clock(),
                batch_seconds=plan.forecast.sweep_seconds,planned_ceiling=ceiling)['phase_deadline']
            require(clock()<b_deadline,'B entry lacks protected phase window')
            if hasattr(backend,'set_phase_deadline'): backend.set_phase_deadline(b_deadline)
            backend.reload(arms['A']['checkpoint_path'], deadline=b_deadline)
            backend.begin('rl', deadline=b_deadline)
            for sweep, parents in enumerate(parent_batches[:1]):
                cost=measured_batch_forecast(backend.physical_events()) if measured else {'seconds':plan.forecast.sweep_seconds}
                if measured:require(len(cost['observations'])==64*sweep,'only complete fixed prior batches may enter cost admission')
                admission = numeric_diagnostic_budget(plan,b_started=b_start,observed=clock(),
                    batch_seconds=cost['seconds'],planned_ceiling=ceiling)
                admission.update(phase='B',sweep=sweep,batch_index=sweep,parent_ids=list(parents),
                    forecast_sha256=plan.forecast.evidence_sha256,cost_forecast=cost)
                admitted = admission['admitted']
                if backend.scope=='owned-native-production':
                    from owned_runtime.storage import before_batch
                    admission['disk_admission']=before_batch(root.parent,fixture=False)
                    admitted=admitted and admission['disk_admission']['admitted']
                    admission['admitted']=admitted
                admissions.append(admission)
                if not admitted:
                    b_status='not-admitted' if not sweeps else 'cost-prefix-stop'
                    break
                work_deadline=admission['work_deadline']
                before_identity=deepcopy(backend.identity())
                boundary = backend.snapshot('B-before-batch-' + str(sweep))
                batch = None; update=None; entry=None
                try:
                    batch = backend.collect(reward_panel, sweep=sweep, max_new_tokens=plan.output_cap, deadline=work_deadline)
                    backend.assert_safe()
                    summary = summarize(batch, parents, plan.shape.group_size)
                    require(not summary['fatal_native_state'], 'fatal batch cannot enter fallback evaluation')
                    if not summary['complete']:
                        b_status = 'incomplete-audit'
                        if hasattr(backend,'acknowledge_batch'):backend.acknowledge_batch(batch,status=b_status)
                    elif not summary['mixed_groups']:
                        b_status = 'zero-signal'
                        if hasattr(backend,'acknowledge_batch'):backend.acknowledge_batch(batch,status=b_status)
                    else:
                        update = backend.update(batch, gate_json=plan.numerical_gate_json, deadline=work_deadline)
                        backend.assert_safe()
                        b_status = 'updated' if update.get('optimizer_committed') is True else update['status']
                    entry = {'batch': batch, 'summary': summary, 'update': update, 'status': b_status}
                except RecoverableWorkError as exc:
                    backend.assert_safe()
                    backend.restore(boundary, deadline=b_deadline)
                    backend.assert_safe()
                    batch = exc.batch if exc.batch is not None else batch
                    require(batch is not None, 'recoverable sampling failure needs actual partial audit receipt')
                    entry = {'batch': batch, 'summary': summarize(batch, parents, plan.shape.group_size),
                             'update': getattr(exc,'update_report',None), 'status': 'incomplete-audit',
                             'error': str(exc), 'rollback_verified': True}
                    b_status = 'incomplete-audit'
                except BaseException as exc:
                    if batch is not None:
                        entry={'batch':batch,'summary':summarize(batch,parents,plan.shape.group_size),
                            'update':getattr(exc,'update_report',None),'status':'failed-no-safe-continuation',
                            'error':type(exc).__name__+': '+str(exc),'batch_index':sweep,
                            'parent_ids':list(parents),'policy_before':before_identity,'policy_after':None,'admission':admission}
                        retain_shadow(entry['update'])
                        write_json(root/'audit'/f'sweep-{sweep}.json',entry);sweeps.append(entry)
                    raise
                finally:
                    backend.release_snapshot(boundary)
                entry.update(batch_index=sweep,parent_ids=list(parents),policy_before=before_identity,
                             policy_after=deepcopy(backend.identity()),admission=admission)
                # Persist the actual partial audit before potentially failing disk
                # work. Its separate durability reference is added in the index.
                retain_shadow(entry['update'])
                audit_ref=write_json(root/'audit'/f'sweep-{sweep}.json',entry)
                sweeps.append(entry)
                last_b=persist('B-batch-'+str(sweep),deadline=b_deadline)
                entry['durable_checkpoint']=last_b
                write_json(root/'audit'/f'batch-{sweep}-durability.json',
                           {'batch_index':sweep,'audit_ref':audit_ref,'checkpoint':last_b,
                            'whole_B_elapsed_seconds':ledger.elapsed()})
                verify_plan()
                if b_status not in ('updated','zero-signal'):
                    break
            if last_b is None:
                last_b=persist('B',deadline=b_deadline)
            arms['B']=deepcopy(last_b)
            arms['B']['audit_status']=b_status
            arms['B']['no_update']=arms['B']['updates']['rl_updates']==0
            if arms['B']['no_update']:
                require(arms['B']['adapter_sha256']==arms['A']['adapter_sha256'],'no-update B must be exact A adapter')
            if Path(arms['B']['checkpoint_path']).name!='B':
                write_json(root/'B-checkpoint-proof.json',arms['B'])
            verify_plan()
            result['stage_status']['B']='complete'
        b_seconds = ledger.events[-1]['seconds']
        require(b_seconds <= plan.arm_cap_seconds, 'B actual phase exceeded hard cap')

        result['model_closure'] = backend.close()
        safe_closure(result['model_closure'])
        result['stage_status']['closure']='complete'
        complete = (update is not None and update.get('status')=='intentionally-no-update' and
                    update.get('optimizer_committed') is False and update.get('optimizer_dispatched') is False and
                    len(update.get('replays',[])) == batch_parents*plan.shape.group_size and
                    update.get('rollback',{}).get('restored') is True and
                    update.get('numeric_shadow_complete') is True and
                    arms['A']['adapter_sha256']==arms['B']['adapter_sha256'] and
                    arms['B']['updates']['rl_updates']==0 and arms['B']['updates']['control_updates']==0)
        result['diagnostic_complete']=complete
        result['status']=NUMERIC_DIAGNOSTIC_COMPLETE if complete else NUMERIC_DIAGNOSTIC_INCOMPLETE
        result['diagnostic_stop_reason']=b_status
    except BaseException as exc:
        # No evaluation after unknown/fatal device state. Partial artifacts stay
        # visible, and an absent score remains null rather than fabricated zero.
        result['status'] = NUMERIC_DIAGNOSTIC_INCOMPLETE
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        try:
            backend.assert_safe()
            result['device_state'] = 'settled'
        except BaseException as state_error:
            result['device_state'] = 'fatal-or-unknown'
            result['state_error'] = str(state_error)
    finally:
        if result.get('model_closure') is None:
            try:
                result['model_closure'] = backend.close()
            except BaseException as exc:
                result['model_closure'] = {'closed': False, 'error': str(exc)}
        try:
            result['physical_events'] = deepcopy(backend.physical_events())
        except BaseException as exc:
            result['physical_events'] = []
            result['physical_events_error'] = str(exc)
            result['status'] = NUMERIC_DIAGNOSTIC_INCOMPLETE
        physical_ref=write_json(root/'physical-events.json',result['physical_events'])
        result['model_closure']=compact_event_projections(result['model_closure'],physical_ref)
        try:
            result['metering_bridge'] = close_metering(result['physical_events'], ledger.events, model_closure=result['model_closure'])
            write_json(root / 'physical-metering-closure.json', result['metering_bridge'])
        except BaseException as exc:
            result['status'] = NUMERIC_DIAGNOSTIC_INCOMPLETE
            result['metering_bridge'] = {'verified': False, 'error': str(exc)}
        result.pop('physical_events',None)
        result['physical_events_ref']=physical_ref
        result['global_elapsed_seconds'] = clock() - plan.global_started
        result['final_adapter_identity'] = None
        if result.get('device_state') != 'fatal-or-unknown':
            try:
                result['final_adapter_identity'] = deepcopy(backend.identity())
            except BaseException as exc:
                result['identity_error'] = str(exc)
                result['status'] = NUMERIC_DIAGNOSTIC_INCOMPLETE
        try:
            result['source_closure'] = plan.sources.close_imports(execution_guard)
        except BaseException as exc:
            result['status'] = NUMERIC_DIAGNOSTIC_INCOMPLETE
            result['source_closure'] = {'verified': False, 'error': str(exc)}
        # Keep every declared batch, including unentered ones, and distinguish
        # full-panel256 intent from one complete64-slot update denominator.
        for i in range(len(sweeps),len(parent_batches)):
            batch=empty_batch(parent_batches[i],plan.shape.group_size,i,'not-requested-by-diagnostic' if i>0 else 'diagnostic-first-batch-not-entered')
            entry={'batch_index':i,'parent_ids':list(parent_batches[i]),'batch':batch,
                   'summary':summarize(batch,parent_batches[i],plan.shape.group_size),'update':None,
                   'status':'not-requested-by-diagnostic' if i>0 else 'not-reached','policy_before':None,'policy_after':None,'admission':None}
            sweeps.append(entry)
            if not (root/'audit'/f'sweep-{i}.json').exists():write_json(root/'audit'/f'sweep-{i}.json',entry)
        result['audit_sweeps']=[{'path':str((root/'audit'/f'sweep-{i}.json').resolve()),
            'file_sha256':file_sha(root/'audit'/f'sweep-{i}.json'),'batch_index':i,'parent_ids':list(parent_batches[i]),
            'summary':entry['summary'],'status':entry['status'],
            'durability_ref':({'path':str((root/'audit'/f'batch-{i}-durability.json').resolve()),
                'file_sha256':file_sha(root/'audit'/f'batch-{i}-durability.json')} if (root/'audit'/f'batch-{i}-durability.json').is_file() else None),
            'update_status':None if entry['update'] is None else entry['update']['status']}
            for i,entry in enumerate(sweeps) if (root/'audit'/f'sweep-{i}.json').is_file()]
        result['audit_batches']=deepcopy(result['audit_sweeps'])
        if plan.shape.batch_parents:
            from .audit import full_panel_summary
            result['full_panel_audit']=full_panel_summary(sweeps,reward_panel.parent_ids,plan.shape.group_size)
            # Diagnostic-only unrequested placeholders are not physical attempts.
            # Keep the inherited ABC summary and every fixed-denominator row intact.
            result['full_panel_audit']['physical_attempted_batches']=sum(
                entry['status'] not in ('not-reached','not-requested-by-diagnostic') for entry in sweeps)
            write_json(root/'full-panel-audit.json',result['full_panel_audit'])
        if result['status'] != NUMERIC_DIAGNOSTIC_COMPLETE:
            result['diagnostic_complete']=False
        result['result_artifact'] = str((root / 'result.json').resolve())
        try:
            write_json(root / 'result.json', result)
        finally:
            if execution_guard is not None:
                execution_guard.stop()
    return result
