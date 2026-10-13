"""Actual completed persistence and outcome-blind measured batch admission."""
from .safe_io import Root,need,same,digest,finite,integer
from .ledger_checks import interval


def persistence_and_budget(root,result,plan,events,*,source_root,synthetic):
    rows=result.get('persistence_intervals');need(type(rows) is list and len(rows)>=4,'mandatory complete persistence intervals')
    labels=[r.get('label') for r in rows]
    entered=sum(ref['status']!='not-reached' for ref in result['audit_sweeps'])
    expected=['base','A']+([f'B-batch-{i}' for i in range(entered)] if entered else ['B'])+['C']
    need(labels==expected,'actual persistence label/order inventory differs')
    previous=plan['global_started']
    for row in rows:
        interval(row);need(row['started']>=previous and type(row.get('completed')) is bool
                           and row['completed'] is (row['ended']<=row['deadline']),'persistence honest actual clock/completion differs')
        need(row['completed'],'complete flow cannot hide failed finalization');previous=row['ended']
        proof=root.json(row['label']+'-checkpoint-proof.json')
        need(row.get('checkpoint_manifest_sha256')==proof.get('manifest_file_sha256'),'persistence actual manifest binding differs')
        actual=[e for e in events.values() if e['phase'] in ('checkpoint-save','checkpoint-reload')
                and e['dispatched'] and e['status']=='complete' and row['started']<=e['started']<=e['ended']<=row['ended']]
        need([e['phase'] for e in actual]==['checkpoint-save','checkpoint-reload'],'whole persistence omitted physical save/reload')
        need(all(e['deadline']<=row['deadline']+.001 for e in actual),'persistence actual call deadline expanded')
        need(proof['save'].get('physical_event_id')==actual[0]['event_id'] and proof['reload'].get('physical_event_id')==actual[1]['event_id'],'actual checkpoint save/reload physical identities differ')
        for e in actual:
            need(e.get('checkpoint_path')==proof['checkpoint_path'] and e.get('manifest_sha256')==proof['manifest_file_sha256'] and e.get('state_sha256')==proof['save']['state_sha256'],'physical checkpoint operation target/manifest/state differs')
        need(proof['reload'].get('checkpoint_path')==proof['checkpoint_path'] and proof['reload'].get('manifest_sha256')==proof['manifest_file_sha256'],'reload receipt target differs')
    estimator=result.get('C_finalization_estimator');need(type(estimator) is dict,'actual late C finalization estimator required')
    observations=[r for r in rows if r['label']=='A' or r['label']=='B' or r['label'].startswith('B-batch-')]
    estimate=plan['forecast']['persist_reload_seconds'] if synthetic else 1.25*max(r['seconds'] for r in observations)
    expected_est={'seconds':estimate,'factor':None if synthetic else 1.25,'inputs':observations,
                  'inputs_sha256':digest(observations),'unmeasured_global_reserve_seconds':plan['forecast']['persist_reload_seconds'],
                  'outcomes_used':False,'actual_seconds':rows[-1]['seconds'],'actual_minus_estimate_seconds':rows[-1]['seconds']-estimate}
    need(same(estimator,expected_est),'C finalization estimate must retain all completed A/B persistence and actual C error')
    if synthetic:return {'persistence_intervals':len(rows),'C_finalization_estimate_seconds':estimate,'synthetic':True}
    policy=Root(source_root).json('design/MEASURED-POLICY.json');costs=Root(source_root).json('design/COST-EVIDENCE.json')
    initial=1.25*costs['public']['observed_generation_metrics']['elapsed_seconds']['sum']/costs['public']['views']
    bphase=next(r for r in result['phase_intervals'] if r['phase']=='B')
    admissions=result.get('admissions');need(type(admissions) is list,'mandatory actual admission sequence')
    bs=[r for r in admissions if r.get('phase')=='B'];cs=[r for r in admissions if r.get('phase')=='C']
    need(len(bs) in (entered,entered+1) and all(type(r.get('admitted')) is bool for r in admissions)
         and all(r.get('phase') in ('B','C') for r in admissions),'fixed-prefix admission sequence differs')
    for index,row in enumerate(bs):
        need(row.get('batch_index')==row.get('sweep')==index and row.get('parent_ids')==result['batch_schedule'][index],
             'batch admission exact schedule differs')
        for key in ('remaining_seconds','projected_B_seconds','projected_C_growth_seconds','required_seconds','protected_seconds','phase_deadline','whole_B_spent_seconds'):
            need(finite(row.get(key)),'finite actual batch admission '+key)
        decision_at=plan['global_started']+42000-row['remaining_seconds']
        observed=[{'event_id':e['event_id'],'seconds':e['seconds'],'status':e['status']} for e in events.values()
                  if e['phase']=='rollout-generation' and e['dispatched'] and e['ended']<=decision_at]
        sample=initial;total=0.
        need(len(observed) in (0,64,128,192,256),'only completed fixed64-slot histories admit another batch')
        for n,item in enumerate(observed,1):
            total+=item['seconds']
            if n%64==0:sample=max(sample,1.25*total/n)
        forecast={'seconds':64*(sample+4)+30,'rollout_seconds':sample,'observations':observed,'completed_batch_boundaries':len(observed)//64,'incomplete_dispatched_cost_count':len(observed)%64,'outcome_conditioning':False,
                  'policy_sha256':plan['measured_policy_sha256'],'cost_evidence_sha256':policy['evidence_sha256']}
        need(same(row.get('cost_forecast'),forecast),'cost forecast erased failed calls or monotone prefix high-water')
        protected=sum(plan['forecast'][k] for k in ('evaluation_seconds','public_seconds','failure_margin_seconds','closure_seconds'))
        increment=forecast['seconds']+plan['forecast']['persist_reload_seconds']
        projected=row['whole_B_spent_seconds']+increment;epsilon=min(120.,max(5.,.05*projected));c=min(7200.,projected+epsilon)
        need(same(row['projected_B_seconds'],projected) and same(row['projected_C_growth_seconds'],c)
             and same(row['required_seconds'],increment+c+protected) and row['protected_seconds']==protected,
             'actual B/C/reserve disjoint forecast arithmetic differs')
        need(row['phase_deadline']<=min(bphase['started']+7200.,plan['global_started']+42000-protected)
             and abs(decision_at-(bphase['started']+row['whole_B_spent_seconds']))<.1,'admission original whole-B clock differs')
        # Actual check and logged remaining are sampled moments apart: admissions
        # at a boundary are conservatively accepted only if all strict scalar
        # headroom conditions are satisfied to the logged decision instant.
        possible=projected<=7080. and projected+epsilon<=7200. and increment+c+protected<=row['remaining_seconds']
        if row['admitted']:need(possible and index<entered,'inadmissible batch dispatched or no matching attempt')
        else:need(index==entered and index==len(bs)-1,'rejected admission did not terminate prefix')
    need(sum(r['admitted'] for r in bs)==entered,'missing actual batch admission')
    return {'persistence_intervals':len(rows),'C_finalization_estimate_seconds':estimate,'batch_admissions':len(bs),
            'control_admissions':len(cs),'failed_sampling_costs_retained':True,'forecast_high_water_verified':True}
