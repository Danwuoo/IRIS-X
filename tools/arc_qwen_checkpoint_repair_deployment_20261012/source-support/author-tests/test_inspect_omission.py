from pathlib import Path
import json,sys,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'worktree'))
from tools.arc_qwen_portfolio_20261012.checkpoints import inspect_checkpoint
from tools.arc_next_models import digest,canonical
source=ROOT/'evidence/native-production-schedule-final/checkpoints/global_grid/update-00000000'
target=ROOT/'evidence/final002-inspect-omission';shutil.copytree(source,target)
manifest=json.loads((target/'manifest.json').read_bytes());manifest['binding'].pop('checkpoint_schedule');manifest['binding_sha256']=digest(manifest['binding'])
(target/'manifest.json').write_bytes(canonical(manifest)+b'\n')
try:inspect_checkpoint(target)
except ValueError as e:
    assert 'stored TransferTrainer' in str(e),str(e)
    result={'status':'passed','rejected':'schedule omission in actual freeze001 base checkpoint manifest','error':str(e),
        'tested_inspector_source':'worktree checkpoint.py final002 negative guard','model_or_state_relabelled':False}
else:raise AssertionError('missing transfer schedule accepted')
(ROOT/'evidence/final002-inspect-omission-receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
