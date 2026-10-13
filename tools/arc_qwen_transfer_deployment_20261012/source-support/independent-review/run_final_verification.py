"""Re-run all CPU suites, archive audit, and bind results to unchanged source bytes."""
import ast
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
FILES=[ROOT/'selection/demo_selector.py',ROOT/'selection/prompt_budget.py',
       ROOT/'data-adaptation/arc_adaptation.py',ROOT/'data-adaptation/audit_archive.py',
       ROOT/'data-adaptation/artifact.schema.json',ROOT/'data-adaptation/README.md',
       HERE/'test_independent_contracts.py']
def hashes(): return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES}
before=hashes()
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
suites=[]
for optimized in (False,True):
    interpreter=[sys.executable]+(['-O'] if optimized else [])
    for name,cwd,command in [
        ('independent',HERE,['test_independent_contracts.py']),
        ('author-selection',ROOT/'selection',['-m','unittest','discover','-v']),
        ('author-data',ROOT/'data-adaptation',['-m','unittest','discover','-s','tests','-v'])]:
        log=HERE/(name+('-optimized' if optimized else '')+'-final.txt')
        run=subprocess.run(interpreter+command,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        log.write_text(run.stdout)
        if run.returncode: raise SystemExit(f'{name}: failed ({log})')
        count=int(re.search(r'Ran (\d+) tests',run.stdout).group(1))
        suites.append({'suite':name,'optimized':optimized,'tests':count,'status':'passed','log':log.name})
archive=Path('/workspace/scratch/3c2b2502fb1e/portfolio63-user-20261012/inputs/evidence(1).zip')
audit_out=HERE/'audit-archived32-independent.json'
run=subprocess.run([sys.executable,str(ROOT/'data-adaptation/audit_archive.py'),str(archive),'--output',str(audit_out)],
                   cwd=HERE,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(HERE/'archive-audit-final.txt').write_text(run.stdout)
if run.returncode: raise SystemExit('Archive audit failed')
if audit_out.read_bytes()!=(ROOT/'data-adaptation/audit-archived32.json').read_bytes(): raise SystemExit('Archive output differs')
for path in FILES:
    if path.suffix=='.py': ast.parse(path.read_text())
json.loads((ROOT/'data-adaptation/artifact.schema.json').read_text())
after=hashes()
if after!=before: raise SystemExit('Source changed during verification; rerun required')
audit=json.loads(audit_out.read_text())
report={
    'reviewed_at_utc':datetime.now(timezone.utc).isoformat(),
    'scope':'Standalone CPU/stdlib component review only; no production or GPU admission.',
    'status':'passed_with_explicit_runtime_integration_requirements',
    'source_files_unchanged_during_final_verification':True,
    'reviewed_files_sha256':before,'suites':suites,
    'archive_audit':{k:audit[k] for k in ['parent_count','demonstration_count','inverse_checks','loo_records_validated',
        'outer_ttt_folds_validated','outer_ttt_records_validated','source_original_bytes_revalidated','fresh_panels_selected']},
    'archive_audit_sha256':hashlib.sha256(audit_out.read_bytes()).hexdigest(),
    'audit_output_matches_author':True,
    'no_network_install_gpu_or_source_implementation_edits':True,
    'runtime_admission':False,
    'required_before_runtime':['Independently pinned complete inventory and PUBLIC120 canonical/alias exclusions.',
        'Original runtime/source restoration and actual reviewed tokenizer/renderer, target/output cap validation.',
        'Bind candidate/checkpoint/policy, packed prompt, intended fold scope, supervised record and partition hashes to authenticated native execution evidence.',
        'Restore independent adapter and optimizer state for every TTT parent and outer fold.',
        'Physical all-call ledger, source provenance, checkpoint reload, GPU/context/memory/time admission and complete denominators.'],
}
(HERE/'verification-summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps({'status':report['status'],'suites':suites,'archive_audit':report['archive_audit'],
                  'summary':'verification-summary.json'},indent=2))
