"""Diagnostic reproductions: accepted=True indicates a remaining structural gap."""
from dataclasses import replace
import json
from test_independent_contracts import d, data_fixture

inv, partition, blobs = data_fixture()
parent = partition.excluded_inventory_ids[0]
# Swap excluded parent into optimizer, and remove its excluded membership.
results = []
try:
    forged = replace(partition, optimizer_ids=partition.optimizer_ids+(parent,),
                     excluded_inventory_ids=tuple(p for p in partition.excluded_inventory_ids if p != parent))
    d.assert_sprint_contract(forged,inventory=inv,archived_optimizer_ids=partition.prior_optimizer_ids,
        archived_regression_ids=partition.exclusions.old_regression_ids,
        archived_exposed_ids=partition.exclusions.old_exposed_ids,
        public120_exclusion_sha256=d.digest(partition.exclusions.public120_ids))
    task = d.project_source_bytes(blobs[parent],inv,parent)
    records = d.loo_records(task,purpose='optimizer',partition=forged)
    results.append({'id':'partition-exclusion-bypass','accepted':True,'forbidden_parent':parent,'optimizer_records':len(records)})
except ValueError as exc:
    results.append({'id':'partition-exclusion-bypass','accepted':False,'error':str(exc)})

records=[]
for parent in partition.optimizer_ids[:2]:
    task=d.project_source_bytes(blobs[parent],inv,parent)
    records.extend(d.loo_records(task,purpose='ttt'))
try:
    schedule=d.budgeted_schedule(records,max_records=4,seed='scope-mix')
    results.append({'id':'mixed-parent-ttt-schedule','accepted':True,'scheduled_parents':schedule.parent_ids})
except ValueError as exc:
    results.append({'id':'mixed-parent-ttt-schedule','accepted':False,'error':str(exc)})
print(json.dumps(results,indent=2))
