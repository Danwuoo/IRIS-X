"""Read-only, no-model verification of a completed consolidated CPU result.

Usage: python audit_cpu_result.py SOURCE_ROOT RESULT_JSON OUTPUT_JSON
       [--run-root RELOCATED_RUN] [--archive ORIGINAL_ZIP]
SOURCE_ROOT is the exact portable source snapshot that produced RESULT_JSON.
No verifier or candidate execution is performed here; no evaluator is read.
"""
import collections
import argparse
import hashlib
import json
import pathlib
import sys
import zipfile

if sys.flags.optimize:
    raise SystemExit('Audit requires normal Python; optimized assertions are not accepted.')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source_root', type=pathlib.Path)
parser.add_argument('result_json', type=pathlib.Path)
parser.add_argument('output_json', type=pathlib.Path)
parser.add_argument('--run-root', type=pathlib.Path, help='Relocated extracted run with final ledger')
parser.add_argument('--archive', type=pathlib.Path, help='Relocated original evidence ZIP')
args = parser.parse_args()
source, result_path, output_path = args.source_root, args.result_json, args.output_json
sys.path.insert(0, str(source.resolve()))
from tools.arc_consolidated_20261010 import arc_object_ir as ir, assets

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def canon(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()

result = json.loads(result_path.read_text())
r = result['report']
c = r['coverage']
plans = ir.base_inventory() if r['profile'] == 'FULL' else ir.smoke_inventory()
plan_by_id = {ir.digest(plan): plan for plan in plans}
assert len(plan_by_id) == len(plans) == c['candidate_count']
assert c['task_ids'] == list(assets.ENGINEERING_IDS)
tasks = assets.load_demos()
task_by_id = {t['task_id']: t for t in tasks}
status, demo_status, demo_reason = collections.Counter(), collections.Counter(), collections.Counter()
rows, all_receipts, witness_details = [], [], []
for task in c['tasks']:
    tid = task['task_id']
    records = task['results']
    ids = [row['candidate_id'] for row in records]
    assert len(ids) == len(set(ids)) and set(ids) <= set(plan_by_id)
    if task['complete']:
        assert set(ids) == set(plan_by_id)
    counts = collections.Counter(row['status'] for row in records)
    witnesses = [row for row in records if row['all_demos_fit']]
    assert [row['candidate_id'] for row in witnesses] == task['witness_ids']
    assert bool(witnesses) == task['demo_fit']
    for row in records:
        status[row['status']] += 1
        assert row['task_sha256'] == assets.digest(task_by_id[tid])
        for demo in row.get('demos', []):
            demo_status[demo['status']] += 1
            if demo['status'] != 'match' and demo['status'] != 'mismatch':
                demo_reason[demo['reason']] += 1
        if row['all_demos_fit']:
            assert row['known'] and all(d['match'] for d in row['demos'])
            witness_details.append({'task_id': tid, 'demo_count': len(task_by_id[tid]['demos']),
                'candidate_id': row['candidate_id'], 'plan': plan_by_id[row['candidate_id']],
                'source_sha256': row['source_sha256'], 'gas': row['gas']})
    all_receipts.extend(records)
    rows.append({'task_id': tid, 'demo_count': len(task_by_id[tid]['demos']),
        'planned': task['planned'], 'executed': task['executed'], 'missing': task['missing'],
        'unknown': task['unknown'], 'status_counts': dict(counts),
        'witness_count': len(witnesses), 'complete': task['complete']})
controls = r['controls']['controls']
assert len(controls) == 128
assert all(x['as_expected'] and x['receipt']['status'] == x['expected_status'] for x in controls)
all_receipts += [x['receipt'] for x in controls]
assert len(all_receipts) == r['ledger']['charged']['cpu_checks']
assert sum(x['gas_charged'] for x in all_receipts) == r['ledger']['charged']['gas']
run_root = args.run_root or pathlib.Path(result['output_root'])
previous = '0' * 64
events = collections.Counter()
responses = {}
reserved, finished = set(), set()
for sequence, line in enumerate((run_root / 'ledger/journal.jsonl').open('rb')):
    record = json.loads(line)
    assert record['seq'] == sequence and record['prev'] == previous
    body = {key: record[key] for key in ('seq', 'prev', 'event', 'data')}
    assert hashlib.sha256(canon(body)).hexdigest() == record['sha256']
    assert canon(record) + b'\n' == line
    previous = record['sha256']
    event, data = record['event'], record['data']
    events[event] += 1
    if event == 'reserve':
        assert data['id'] not in reserved
        reserved.add(data['id'])
    if event == 'response':
        assert data['id'] in reserved and data['file'] not in responses
        responses[data['file']] = data['sha256']
    if event == 'finish':
        assert data['id'] in reserved and data['id'] not in finished
        finished.add(data['id'])
actual_response_files = {p.name for p in (run_root / 'ledger/responses').iterdir()}
assert set(responses) == actual_response_files
for filename, expected in responses.items():
    assert sha(run_root / 'ledger/responses' / filename) == expected
archive = args.archive or pathlib.Path(result['archive']['archive'])
assert sha(archive) == result['archive']['sha256']
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist()) == len(set(z.namelist()))
out = {'schema': 'independent-consolidated-cpu-audit-v1', 'read_only': True,
    'new_verifier_calls': 0, 'model_calls': 0, 'gold_read': False,
    'result_sha256': sha(result_path), 'source_sha256': r['source_sha256'],
    'profile': r['profile'], 'status': r['status'], 'coverage_complete': c['complete'],
    'candidate_count': len(plans), 'task_count': len(rows), 'tasks': rows,
    'status_counts': dict(status), 'demo_status_counts': dict(demo_status),
    'demo_domain_reasons': dict(demo_reason), 'witnesses': witness_details,
    'controls': {'count': len(controls), 'all_expected': True},
    'gate': r['gate'], 'charged': r['final_accounting']['charged'],
    'cpu_phase_seconds': r['cpu_phase_seconds'], 'checks_per_second': r['checks_per_second'],
    'archive_sha256': result['archive']['sha256'], 'archive_bytes': archive.stat().st_size,
    'journal_final_sha256': previous, 'journal_records': sequence + 1,
    'journal_event_counts': dict(events), 'response_files_verified': len(responses),
    'reserved_count': len(reserved), 'finished_count': len(finished),
    'processes': r['processes'], 'reservation_overrun': r['final_accounting']['reservation_overrun'],
    'ordering_diagnostics': r['ordering_diagnostics'],
    'limitations': ['Exposed engineering demonstrations only; no query or held-out score.',
        'No witness is bounded by this finite inventory and gas/runtime domain.',
        'Synthetic controls do not establish GPU, weights or tokenizer acceptance.']}
output_path.write_text(json.dumps(out, sort_keys=True, indent=2) + '\n')
print(json.dumps({k: out[k] for k in ['profile', 'coverage_complete', 'status_counts',
    'controls', 'cpu_phase_seconds', 'response_files_verified', 'archive_bytes']}))
