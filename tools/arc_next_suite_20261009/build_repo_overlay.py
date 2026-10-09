"""Build add-only source overlay. No Git operations and no external writes."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).parent
TARGET='tools/arc_next_suite_20261009'
OUT=ROOT/'repo-overlay-tools';destination=OUT/TARGET
if destination.exists():raise SystemExit('Immutable overlay destination already exists')
lock=json.loads((ROOT/'src/source-lock.json').read_text())
relative=['README.zh-TW.md','README.md','VALIDATION.md','.gitignore','build_source_lock.py','build_notebooks.py','audit_tokens.py','run_cpu_replay.py','build_repo_overlay.py','publication-manifest.json']
relative += ['src/'+n for n in lock['files']]+['src/source-lock.json','src/solver-challenges-reference.json']
relative += [str(p.relative_to(ROOT)) for folder in ('notebooks','publication','docs') for p in sorted((ROOT/folder).rglob('*')) if p.is_file()]
relative += ['tests/test_suite.py','tests/test_notebooks.py','tests/test_typed_ir.py','tests/arc_ir_coverage.py','tests/evidence/known-witness-coverage-reviewed.json']
relative += ['evidence/final-release-focused-tests.txt','evidence/notebook-tests-release.txt','evidence/token-audit-console.txt','evidence/N5-CPU-REPORT.json','evidence/N5-CPU-SUMMARY.json','evidence/N13-CPU-SUMMARY.json','evidence/COMPONENT-RESULTS-REVIEWED.json']
relative += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'evidence/review').glob('*')) if p.is_file()]
entries=[]
for name in sorted(set(relative)):
 source=ROOT/name
 if not source.is_file() or source.is_symlink():raise ValueError('Missing/unsafe overlay member: '+name)
 if source.suffix in ('.zip','.safetensors','.pt','.pth') or '__pycache__' in source.parts:raise ValueError('Excluded bulk/binary member')
 data=source.read_bytes();target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 entries.append({'source':str(target.resolve()),'path':TARGET+'/'+name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
manifest={'format':'irisx/add-only-main-overlay-v1','target_prefix':TARGET,'source_lock_sha256':hashlib.sha256((ROOT/'src/source-lock.json').read_bytes()).hexdigest(),
          'independent_review_sha256':hashlib.sha256((ROOT/'evidence/review/TEN-SUITE-FINAL-INDEPENDENT-REVIEW.json').read_bytes()).hexdigest(),
          'source_file_count':len(entries),'total_bytes':sum(e['bytes'] for e in entries),'files':entries,
          'excluded':['evaluator query gold','weights','credentials','ZIP archives','bulk synthetic training payload','mutable scratch/validation directories'],
          'existing_repository_edits':False,'external_publication_performed_by_builder':False}
(ROOT/'repo-overlay-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:v for k,v in manifest.items() if k!='files'},indent=2))
