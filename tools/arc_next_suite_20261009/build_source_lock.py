from pathlib import Path
import hashlib,json
root=Path(__file__).parent/'src'
names=['arc_suite.py','arc_suite_policy.py','arc_bounded_v1.py','arc_bounded_v2.py','arc_n4_program.py','arc_program_v2.py','arc_typed_ir.py','arc_curriculum.py','DESIGN-FROZEN.json','n4-replay-payload.json','solver-manifest-reference.json','visible-token-audit.json','SECURITY-RELEASE.json']
missing=[n for n in names if not (root/n).is_file()]
if missing:raise SystemExit('Missing source artifacts: '+str(missing))
lock={'format':'irisx/nextphase-source-lock-v1','files':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}}
(root/'source-lock.json').write_text(json.dumps(lock,indent=2)+'\n')
print(hashlib.sha256((root/'source-lock.json').read_bytes()).hexdigest())
